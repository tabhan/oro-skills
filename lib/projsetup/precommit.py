"""Managed git pre-commit hook for Oro projects: discover static/quality checks, render, install, report drift.

- Steps come from CI config first (bitbucket-pipelines.yml, .gitlab-ci.yml, .github/workflows), then composer/package
  scripts, then vendor/bin defaults; one step per tool, only for tools the project has.
- Installs where git looks: the configured core.hooksPath, else the git hooks dir; never touches tracked files.
- An unmanaged hook is backed up to pre-commit.bak-<ts> and replaced; a git-tracked one is left alone (refused); the
  old hook's steps with no managed equivalent are listed first.
- `.stylelintignore` (repo root, tracked) is the only exclusion list for every linter: stylelint reads it natively, the generated
  CI script turns it into PHPCS `--ignore` / PHPMD `--exclude` patterns, the hook passes it to ESLint as quoted `--ignore-pattern`
  arguments. Only plain paths and `*`/`**` globs are supported; a negation or anything else fails loudly. Git-ignored and
  untracked paths are NOT excluded automatically (a local-only AppBundle is linted like any other code).
- PHPCS and PHPMD run through one generated, tracked script (`.bitbucket/lint-php.sh` for Bitbucket; `.gitlab/`, `.github/`
  or `.ci/` for the others) that CI and the hook both call. The PHPCS standard is `lint.phpcs-standard` in `.oro-ai/config.json`,
  filled by sync only when missing (detected from CI or the old hook, else PSR12).
"""
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", ".."))
TEMPLATE = os.path.join(ROOT, "templates", "git-hooks", "pre-commit.sh")
LINT_TEMPLATE = os.path.join(ROOT, "templates", "lint", "lint-php.sh")
IGNORE_LIB = os.path.join(ROOT, "templates", "lint", "ignore-lib.sh")
MARK = "# aaxis-oro:managed-pre-commit"
LINT_MARK = "# aaxis-oro:managed-lint-php"
LINT_NAME = "lint-php.sh"
# Where the shared lint script lives, by the CI system that runs it; no CI file at all falls back to .ci/.
LINT_DIRS = (("bitbucket-pipelines.yml", ".bitbucket"), (".gitlab-ci.yml", ".gitlab"), (".github/workflows", ".github"))
LINT_FALLBACK_DIR = ".ci"
DEFAULT_STANDARD = "PSR12"
DEFAULT_SRC = "./src"
DEFAULT_RULESET = "./vendor/oro/platform/build/phpmd.xml"
LINT_BINS = ("vendor/squizlabs/php_codesniffer/bin/phpcs", "vendor/phpmd/phpmd/src/bin/phpmd")
DIRECT_TOOL = re.compile(r"^(php\s+)?(\S*/)?(phpcs|phpmd)(\s|$)")
CI_FILES = ("bitbucket-pipelines.yml", ".gitlab-ci.yml", ".github/workflows/*.yml", ".github/workflows/*.yaml")
# (key, label, command regex); order is the hook's step order. Coverage, Sonar, installs and deploys never match.
TOOLS = (
    ("phpcs", "PHP CodeSniffer", r"(^|[\s/])phpcs(\s|$)"),
    ("php-cs-fixer", "PHP-CS-Fixer", r"(^|[\s/])php-cs-fixer(\s|$)"),
    ("phpmd", "PHP Mess Detector", r"(^|[\s/])phpmd(\s|$)"),
    ("phpstan", "PHPStan", r"(^|[\s/])phpstan(\s|$)"),
    ("psalm", "Psalm", r"(^|[\s/])psalm(\s|$)"),
    ("phpunit", "PHPUnit", r"(^|[\s/])phpunit(\s|$)"),
    ("eslint", "ESLint", r"(^|[\s/])eslint(\s|$)|\brun\s+eslint\b"),
    ("stylelint", "Stylelint", r"(^|[\s/])stylelint(\s|$)|\brun\s+stylelint\b"),
    ("yamllint", "YamlLint", r"^yamllint(\s|$)"),
)
NODE_TOOLS = ("eslint", "stylelint")
DRIFT = "schema-drift"
DRIFT_LABEL = "Doctrine schema drift"
# Staged-file gate (ERE) per step: a commit with no matching staged path cannot change that step's result.
_IGN = r"|(^|/)\.stylelintignore$"
_PHP_GATE = r"\.(php|xml|neon|dist)$|(^|/)composer\.(json|lock)$"
_LINT_GATE = _PHP_GATE + _IGN + r"|(^|/)lint-php\.sh$"
# The ESLint gate's two halves, reused by run_eslint: files that may need linting, and the configs that can change every file's result.
_ESLINT_CFG_GATE = r"(^|/)(\.eslint[^/]*|eslint\.config\.[^/]*|package\.json)$" + _IGN
GATES = {
    "phpcs": _LINT_GATE, "php-cs-fixer": _PHP_GATE, "phpmd": _LINT_GATE, "phpstan": _PHP_GATE, "psalm": _PHP_GATE,
    "phpunit": _PHP_GATE,
    "eslint": r"\.(js|jsx|mjs|cjs|ts|tsx|vue)$|" + _ESLINT_CFG_GATE,
    "stylelint": r"\.(scss|sass|css)$|(^|/)(\.stylelint[^/]*|stylelint\.config\.[^/]*|package\.json)$",
    "yamllint": r"\.ya?ml$|(^|/)\.yamllint[^/]*$",
    DRIFT: r"/(Entity|Migrations)/.*\.php$|(^|/)entity_(extend|configs)\.yml$|(^|/)composer\.lock$",
}
SKIP_CI = re.compile(r"^(pipe:|npm i|npm install|pnpm install|yarn install|composer (install|update|config)|git )")
YAMLLINT_INSTALL = (("pipx", ["pipx", "install", "yamllint"]),
                    ("pip", ["python3", "-m", "pip", "install", "--user", "--quiet", "yamllint"]))


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def git(root, *args):
    p = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def is_oro(root):
    text = _read(os.path.join(root, "composer.json")) or ""
    return bool(re.search(r'"oro/(platform|commerce|crm|commerce-enterprise|platform-enterprise)[^"]*"\s*:', text))


def config(root):
    try:
        cfg = json.loads(_read(os.path.join(root, ".oro-ai", "config.json")) or "{}").get("precommit") or {}
    except ValueError:
        cfg = {}
    return cfg if isinstance(cfg, dict) else {}


def ci_commands(text):
    """Shell lines of `script:` lists and `run:` keys, without a YAML parser (none is guaranteed on the host)."""
    out, in_script, indent = [], False, 0
    for raw in text.splitlines():
        line = raw.split(" #")[0].rstrip() if not raw.lstrip().startswith("- pipe") else raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        ind = len(line) - len(line.lstrip())
        m = re.match(r"-?\s*run:\s*(\S.*)$", stripped)
        if m and m.group(1) not in ("|", ">", "|-", ">-"):
            out.append(m.group(1).strip("'\""))
            continue
        if re.match(r"-?\s*script:\s*$", stripped):
            in_script, indent = True, ind
            continue
        if in_script and ind <= indent and not stripped.startswith("-"):
            in_script = False
        if in_script and stripped.startswith("- "):
            out.append(stripped[2:].strip())
        elif in_script and ind <= indent:
            in_script = False
    return [c for c in out if not SKIP_CI.match(c)]


def classify(cmd):
    for key, label, rx in TOOLS:
        if re.search(rx, cmd):
            return key, label
    return None


def from_ci(root):
    found = {}
    for pattern in CI_FILES:
        for path in sorted(glob.glob(os.path.join(root, pattern))):
            for cmd in ci_commands(_read(path) or ""):
                if LINT_NAME in cmd:  # the shared lint script stands for both PHPCS and PHPMD
                    for key in ("phpcs", "phpmd"):
                        found.setdefault(key, (dict((k, lb) for k, lb, _ in TOOLS)[key], cmd, os.path.relpath(path, root)))
                    continue
                hit = classify(cmd)
                if hit and hit[0] not in found:
                    found[hit[0]] = (hit[1], cmd, os.path.relpath(path, root))
    return found


def lint_script_rel(root, ci):
    """Repo-relative path of the shared lint script: the one CI already names, else the CI system's directory, else .ci/."""
    for key in ("phpcs", "phpmd"):
        for tok in shlex.split(ci[key][1]) if key in ci else ():
            if tok.endswith(LINT_NAME):
                return os.path.normpath(tok)
    for ci_file, directory in LINT_DIRS:
        if any(glob.glob(os.path.join(root, ci_file))) or os.path.isdir(os.path.join(root, ci_file)):
            return "%s/%s" % (directory, LINT_NAME)
    return "%s/%s" % (LINT_FALLBACK_DIR, LINT_NAME)


def uses_lint_script(ci):
    """True when CI runs PHPCS/PHPMD directly or through the shared script (a wrapper such as composer is left alone)."""
    return any(k in ci and (DIRECT_TOOL.match(ci[k][1]) or LINT_NAME in ci[k][1]) for k in ("phpcs", "phpmd"))


def _scripts(root, name):
    try:
        data = json.loads(_read(os.path.join(root, name)) or "{}")
    except ValueError:
        return {}
    s = data.get("scripts") or {}
    return s if isinstance(s, dict) else {}


def _any(root, *patterns):
    return any(glob.glob(os.path.join(root, p)) for p in patterns)


def defaults(root):
    """Per-tool fallbacks when CI names no command: project scripts, else a vendor/bin tool that has its config."""
    found, comp, npm = {}, _scripts(root, "composer.json"), _scripts(root, "package.json")
    src = "src/" if os.path.isdir(os.path.join(root, "src")) else "."
    vb = lambda t: os.path.isfile(os.path.join(root, "vendor", "bin", t))  # noqa: E731
    for key, label, _ in TOOLS:
        if key in comp:
            found[key] = (label, "composer run-script %s" % key, "composer.json")
        elif key in NODE_TOOLS and key in npm and _any(root, ".%src*" % key, ".%s.config.*" % key, "%s.config.*" % key):
            target = src if key == "eslint" else "'%s**/*.scss'" % src
            found[key] = (label, "npm run %s %s" % (key, target), "package.json")
    php = {"phpcs": ("phpcs.xml*", ".phpcs.xml*"), "php-cs-fixer": (".php-cs-fixer*.php",), "phpstan": ("phpstan.neon*",),
           "psalm": ("psalm.xml*",), "phpunit": ("phpunit.xml*",), "phpmd": ("phpmd.xml*",)}
    for key, cfgs in php.items():
        if key in found or not vb(key) or not _any(root, *cfgs):
            continue
        label = dict((k, lb) for k, lb, _ in TOOLS)[key]
        cmd = {"phpmd": "vendor/bin/phpmd %s ansi %s" % (src.rstrip("/"), (glob.glob(os.path.join(root, "phpmd.xml*")) or ["phpmd.xml"])[0][len(root) + 1:]),
               "php-cs-fixer": "vendor/bin/php-cs-fixer fix --dry-run --diff",
               "phpstan": "vendor/bin/phpstan analyse --no-progress"}.get(key, "vendor/bin/%s" % key)
        found[key] = (label, cmd, "vendor/bin")
    if "yamllint" not in found and _any(root, ".yamllint", ".yamllint.y*ml"):
        found["yamllint"] = ("YamlLint", "yamllint %s" % src, ".yamllint")
    return found


def steps(root):
    """[(key, label, command, source)] in TOOLS order, minus `precommit.skip`, plus the schema-drift step and the opt-in atlas gate."""
    cfg, ci, dflt = config(root), from_ci(root), defaults(root)
    skip = set(cfg.get("skip") or [])
    rel = lint_script_rel(root, ci)
    out = []
    for key, _, _ in TOOLS:
        hit = ci.get(key) or dflt.get(key)
        if hit and key in ("phpcs", "phpmd") and key in ci and (DIRECT_TOOL.match(hit[1]) or LINT_NAME in hit[1]):
            hit = (hit[0], "run_lint_php %s %s" % (shlex.quote(rel), key), hit[2])
        if hit and key not in skip:
            out.append((key, hit[0], hit[1], hit[2]))
    if DRIFT not in skip and is_oro(root) and os.path.isfile(os.path.join(root, "bin", "console")):
        out.append((DRIFT, DRIFT_LABEL, "run_schema_drift", "aaxis-oro:schema-drift"))
    if cfg.get("atlas"):
        out.append(("atlas", "Atlas review check", "aaxis-oro atlas precommit", "precommit.atlas"))
    return out


def node_block(root, cfg):
    prefix = cfg.get("path-prefix")
    if prefix:
        return '\n# Project Node from precommit.path-prefix.\nexport PATH=%s:"$PATH"\n' % shlex.quote(prefix)
    if not os.path.isfile(os.path.join(root, ".nvmrc")):
        return ""
    return ('\n# Project Node from .nvmrc via nvm, when nvm is installed (else the PATH node is used).\n'
            'NVM_SH="${NVM_DIR:-$HOME/.nvm}/nvm.sh"\n'
            'if [[ -s "$NVM_SH" ]]; then\n'
            '    . "$NVM_SH" --no-use && nvm use --silent >/dev/null 2>&1 || echo "!!! nvm use failed; using $(node -v 2>/dev/null)" >&2\n'
            'fi\n')


def _flag_value(cmd, flag):
    """Match `--flag=VALUE` / `--flag VALUE` (VALUE as written, quotes included)."""
    return re.search(r"(?<=\s)%s(?:=|\s+)(\"[^\"]*\"|'[^']*'|\S+)" % re.escape(flag), cmd)


# ESLint 8 expands directories to *.js only; --ext is the one way a command widens that.
_ESLINT_DEFAULT_FILES_ERE = r"\.js$"
# The command shapes whose single positional target run_eslint can swap for the staged files; anything else keeps the full scan.
_ESLINT_TARGETED = re.compile(
    r"^(?P<head>(?:(?:npm|pnpm|yarn)\s+run\s+)?(?:\S*/)?eslint)"
    r"\s+(?P<target>(?:\./)?[A-Za-z0-9_][A-Za-z0-9_./-]*)"
    r"(?:\s+(?P<tail>--(?:\s.*)?))?$")


def eslint_files_ere(cmd):
    """ERE for the staged files the command's full scan would lint: its --ext list, else ESLint's directory default (.js)."""
    m = _flag_value(cmd, "--ext")
    if not m:
        return _ESLINT_DEFAULT_FILES_ERE
    exts = [re.escape(e.strip().lstrip(".")) for e in m.group(1).strip("\"'").split(",") if e.strip(". \t")]
    return r"\.(%s)$" % "|".join(exts) if exts else _ESLINT_DEFAULT_FILES_ERE


def eslint_split(cmd):
    """(command without the target, target) for the shapes staged-file linting understands; None keeps the full-scan rendering."""
    m = _ESLINT_TARGETED.match(cmd.strip())
    if not m:
        return None
    head, tail = m.group("head"), m.group("tail")
    return ("%s %s" % (head, tail)) if tail else head, m.group("target")


# run_step executes its arguments directly, so a CI command with shell operators must run through one shell of its
# own -- rendered bare, the operators would apply to run_step itself (a pipe eats its skip message, for example).
_SHELL_OPS = re.compile(r"[|;&<>]")


def shell_wrapped(cmd):
    return "bash -c %s" % shlex.quote(cmd) if _SHELL_OPS.search(cmd) else cmd


def with_ignores(key, cmd):
    """ESLint gets the shared exclusion list (the hook's ESLINT_IGN array); every other command is rendered as written.

    PHPCS/PHPMD read .stylelintignore inside the generated script and stylelint reads it natively, so neither takes arguments.
    An ESLint command with shell operators runs through its own shell instead and gets no exclusion arguments (an array
    expansion cannot cross `bash -c` quoting); such a command manages its own exclusions.
    """
    if _SHELL_OPS.search(cmd):
        return shell_wrapped(cmd)
    if key == "eslint":
        sep = " --" if re.match(r"^npm\s+run\b", cmd) and not re.search(r"\s--(\s|$)", cmd) else ""
        return '%s%s "${ESLINT_IGN[@]}"' % (cmd, sep)
    return cmd


def lint_needs_script(root):
    return any(cmd.startswith("run_lint_php ") for _, _, cmd, _ in steps(root))


def _positionals(cmd, binary):
    toks = shlex.split(cmd)
    idx = next((i for i, t in enumerate(toks) if t.endswith(binary)), None)
    return [] if idx is None else [t for t in toks[idx + 1:] if not t.startswith("-")]


def lint_params(root):
    """(src dir, phpmd ruleset): a direct CI command wins, else the values in the installed script, else the defaults."""
    src, ruleset = DEFAULT_SRC, DEFAULT_RULESET
    cur = _read(os.path.join(root, lint_script_rel(root, from_ci(root)))) or ""
    m = re.search(r"^SRC_DIR='([^']*)'", cur, re.M)
    src = m.group(1) if m else src
    m = re.search(r"^PHPMD_RULESET='([^']*)'", cur, re.M)
    ruleset = m.group(1) if m else ruleset
    ci = from_ci(root)
    if "phpcs" in ci and DIRECT_TOOL.match(ci["phpcs"][1]):
        pos = _positionals(ci["phpcs"][1], "phpcs")
        src = pos[0] if pos else src
    if "phpmd" in ci and DIRECT_TOOL.match(ci["phpmd"][1]):
        pos = _positionals(ci["phpmd"][1], "phpmd")
        src = pos[0] if pos else src
        ruleset = pos[2] if len(pos) > 2 else ruleset
    return src, ruleset


def render_lint_script(root):
    src, ruleset = lint_params(root)
    return (_read(LINT_TEMPLATE).replace("@@IGNORE_LIB@@", _read(IGNORE_LIB).rstrip("\n"))
            .replace("@@SRC@@", src).replace("@@PHPMD_RULESET@@", ruleset))


def lint_state(root):
    """(state, rel path): skipped (no PHPCS/PHPMD through the script) | missing | ok | outdated | foreign."""
    if not lint_needs_script(root):
        return "skipped", ""
    rel = lint_script_rel(root, from_ci(root))
    cur = _read(os.path.join(root, rel))
    if cur is None:
        return "missing", rel
    if LINT_MARK not in cur:
        return "foreign", rel
    return ("ok" if cur == render_lint_script(root) else "outdated"), rel


def detect_standard(root):
    """The PHPCS standard in use today: CI's `--standard`, else the installed hook's, else the default."""
    ci = from_ci(root)
    texts = [ci["phpcs"][1]] if "phpcs" in ci else []
    texts.append(_read(hook_path(root)) or "")
    for text in texts:
        m = re.search(r"--standard(?:=|\s+)[\"']?([A-Za-z0-9_./,-]+)", text)
        if m:
            return m.group(1)
    return DEFAULT_STANDARD


def ensure_lint(root, dry):
    """Fill `lint.phpcs-standard` when missing (never overwrite) and write/refresh the shared lint script. Returns lines."""
    lines = []
    if not lint_needs_script(root):
        return lines
    cfg_path = os.path.join(root, ".oro-ai", "config.json")
    try:
        data = json.loads(_read(cfg_path) or "{}")
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return ["lint: .oro-ai/config.json is not a JSON object; fix it, then set \"lint\": {\"phpcs-standard\": \"...\"}"]
    lint = data.get("lint")
    if isinstance(lint, dict) and lint.get("phpcs-standard"):
        lines.append("lint.phpcs-standard: %s (left as is)" % lint["phpcs-standard"])
    elif isinstance(lint, dict) or lint is None:
        std = detect_standard(root)
        data["lint"] = dict(lint or {}, **{"phpcs-standard": std})
        if not dry:
            os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
            with open(cfg_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        lines.append("lint.phpcs-standard: %s %s" % ("would set" if dry else "set to", std))
    else:
        lines.append("lint: \"lint\" in .oro-ai/config.json is not an object; fix it by hand")
    state, rel = lint_state(root)
    path = os.path.join(root, rel) if rel else ""
    if state == "foreign":
        lines.append("%s: exists and is not managed by aaxis-oro (left as is)" % rel)
    elif state in ("missing", "outdated"):
        if not dry:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(render_lint_script(root))
            os.chmod(path, 0o755)
        lines.append("%s: %s" % (rel, {"missing": "created", "outdated": "updated"}[state]))
    elif state == "ok":
        lines.append("%s: unchanged" % rel)
    if isinstance(cfg_ex := config(root).get("exclude"), list) and cfg_ex:
        lines.append("note: precommit.exclude is no longer used; move its entries to .stylelintignore (the only exclusion list)")
    return lines


def render(root):
    st = steps(root)
    cfg = config(root)
    lines = []
    for key, label, cmd, _ in st:
        gate = GATES.get(key)
        prefix = "GATE=%s " % shlex.quote(gate) if gate else ""
        split = eslint_split(cmd) if key == "eslint" and not _SHELL_OPS.search(cmd) else None
        if key == "yamllint":
            lines.append('%srun_step "%s" run_yamllint %s' % (prefix, label, cmd[len("yamllint"):].strip()))
        elif split:
            rest, target = split
            lines.append('%srun_step "%s" run_eslint %s %s %s %s' % (
                prefix, label, shlex.quote(eslint_files_ere(cmd)), shlex.quote(_ESLINT_CFG_GATE),
                shlex.quote(target), with_ignores(key, rest)))
        else:
            lines.append('%srun_step "%s" %s' % (prefix, label, with_ignores(key, cmd)))
    node = node_block(root, cfg) if any(k in NODE_TOOLS for k, *_ in st) else ""
    sources = ", ".join(sorted({s for *_, s in st})) or "none (no checks discovered)"
    text = _read(TEMPLATE)
    return (text.replace("@@SOURCES@@", sources).replace("@@NODE@@", node).replace("@@IGNORE_LIB@@", _read(IGNORE_LIB).rstrip("\n"))
            .replace("@@STEPS@@", "\n".join(lines) or "true"))


def hook_path(root):
    hp = git(root, "config", "core.hooksPath")
    d = os.path.join(root, hp) if hp else git(root, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    return os.path.join(d, "pre-commit")


def state(root):
    """(state, detail): skipped | missing | ok | outdated | foreign | foreign-tracked."""
    if git(root, "rev-parse", "--git-dir") is None:
        return "skipped", "not a git repository"
    if not is_oro(root):
        return "skipped", "not an Oro project"
    path = hook_path(root)
    cur = _read(path)
    if cur is None:
        return "missing", path
    if MARK not in cur:
        rel = os.path.relpath(path, root)
        tracked = not rel.startswith("..") and git(root, "ls-files", rel)
        return ("foreign-tracked" if tracked else "foreign"), path
    return ("ok" if cur == render(root) else "outdated"), path


def old_hook_gaps(text, managed):
    """Names of the steps in an unmanaged hook that no managed step (keys in `managed`) replaces."""
    logical = re.sub(r"\\\n\s*", " ", text).splitlines()
    blocks, current = [], None  # [(name, [command lines])]
    for line in logical:
        stripped = line.strip()
        run = re.match(r"""run_step\s+(?:"([^"]+)"|'([^']+)')\s*(.*)$""", stripped)
        echo = re.match(r"""echo\s+["']==>\s*(.+?)["']\s*$""", stripped)
        if run:
            current = None
            blocks.append((run.group(1) or run.group(2), [run.group(3)]))
        elif echo:
            current = (echo.group(1), [])
            blocks.append(current)
        elif current is not None and stripped and not stripped.startswith("#"):
            current[1].append(stripped)
        elif "doctrine:schema:" in stripped:
            blocks.append((DRIFT_LABEL, [stripped]))
    gaps = []
    for name, cmds in blocks:
        cmd = " ".join(cmds)
        hit = classify(cmd)
        key = hit[0] if hit else None
        if key is None and "doctrine:schema:" in cmd:
            key = DRIFT
        elif key is None and re.search(r"(^|[\s/])yamllint(:|\s|$)", cmd):
            key = "yamllint"  # docker run ... cytopia/yamllint
        if "$" not in name and key not in managed and name not in gaps:
            gaps.append(name)
    return gaps


def install(root, dry):
    st, path = state(root)
    if st == "skipped":
        return "pre-commit: skipped (%s)" % path
    if st == "ok":
        return "pre-commit: unchanged (%s)" % path
    if st == "foreign-tracked":
        return "pre-commit: NOT installed, %s is tracked by the project (team-owned); add the steps there or remove it" % path
    msg = {"missing": "created", "outdated": "updated", "foreign": "replaced"}[st]
    gaps_note = ""
    if st == "foreign":
        bak = "%s.bak-%s" % (path, time.strftime("%Y%m%d%H%M%S"))
        msg += ", unmanaged hook backed up to %s" % bak
        gaps = old_hook_gaps(_read(path) or "", {k for k, *_ in steps(root)})
        if gaps:
            gaps_note = "\npre-commit: old hook steps with no managed equivalent (kept in the backup, re-add or drop deliberately): %s" % ", ".join(gaps)
        if not dry:
            shutil.copy2(path, bak)
    if not dry:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render(root))
        os.chmod(path, 0o755)
    return "pre-commit: %s (%s; %d steps)%s" % (msg, path, len(steps(root)), gaps_note)


def yamllint_state():
    if shutil.which("yamllint"):
        return "native", True
    if shutil.which("docker"):
        return "docker fallback (cytopia/yamllint)", True
    return "missing", False


def ensure_yamllint(root, dry):
    """Install yamllint user-level (pipx, then pip --user) when a yamllint step exists; never sudo."""
    if not any(k == "yamllint" for k, *_ in steps(root)) or shutil.which("yamllint"):
        return None
    if dry or os.environ.get("AAXIS_ORO_NO_TOOL_INSTALL"):
        return "yamllint: missing; would install with: %s" % fix_yamllint()
    for name, cmd in YAMLLINT_INSTALL:
        usable = shutil.which(cmd[0]) and (name != "pip" or subprocess.run(cmd[:3] + ["--version"], capture_output=True).returncode == 0)
        if usable and subprocess.run(cmd, capture_output=True).returncode == 0:
            return "yamllint: installed with %s" % " ".join(cmd)
    st, _ = yamllint_state()
    return "yamllint: no pipx/pip; hook uses %s" % st if st != "missing" else "yamllint: missing; install pipx or docker, then: pipx install yamllint"


def fix_yamllint():
    if shutil.which("pipx"):
        return "pipx install yamllint"
    return "python3 -m pip install --user yamllint (or pipx install yamllint, or install docker)"


def missing_tools(root):
    """[(tool, fix)] for each step whose tool is absent."""
    out = []
    if lint_needs_script(root):
        out += [(b, "composer install") for b in LINT_BINS if not os.path.exists(os.path.join(root, b))]
    for key, _, cmd, _ in steps(root):
        if key == "yamllint" and not yamllint_state()[1]:
            out.append(("yamllint", fix_yamllint()))
        elif key in NODE_TOOLS and not (shutil.which("node") or os.path.isdir(os.path.expanduser("~/.nvm"))):
            out.append(("node", "install Node per .nvmrc (nvm install) or set precommit.path-prefix"))
        for tok in cmd.split():
            if tok.lstrip("./").startswith("vendor/") and not os.path.exists(os.path.join(root, tok)):
                out.append((tok.lstrip("./"), "composer install"))
    return sorted(set(out))
