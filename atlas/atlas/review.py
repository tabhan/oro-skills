"""`aaxis-oro review check`: deterministic review checks for a diff, shared by the CLI, pre-commit, the commit hook and CI.

Exit: 0 pass (warnings allowed), 1 at least one deny finding, 3 the diff could not be read, 64 usage.
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, namedtuple

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "hooks"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))

import _common as c  # noqa: E402
import _decorates  # noqa: E402
from atlas import cli, index, miniyaml  # noqa: E402
from atlas.common import atlas_dir  # noqa: E402
from atlas.common import ensure_ignored as c_ensure  # noqa: E402
from oroversion import resolve  # noqa: E402
from oroversion.detect import detect  # noqa: E402

REGISTRY = os.path.join(HERE, "..", "hooks", "checks.yml")
CODE_EXT = (".yml", ".yaml", ".xml", ".php")
CONSOLE_CAP = 12

Finding = namedtuple("Finding", "severity check where message")
Change = namedtuple("Change", "path new old")

CITATION = re.compile(
    r"atlas\s+(?:--project\s+\S+\s+)?(entity|operation|grid|event|mq|service|config|tags?|layout|workflow|js|search|unsafe)\s+"
    r"([^\s`'\"|)>]+)(?:[^\n]{0,40}?->\s*`?([\w./\\-]+\.\w+):(\d+))?")
APPBUNDLE = re.compile(r"(?:^|[/\s'\"])AppBundle/")
IO_CALL = re.compile(r"\b(?:fopen|file_put_contents|unlink)\s*\(")
IO_SAFE = re.compile(r"sys_get_temp_dir|tempnam|tmpfile|php://|/tmp/")
PROJECT_DIR_PARAM = re.compile(r"%kernel\.project_dir%")


def git(root, *args):
    p = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, errors="ignore")
    return p.stdout if p.returncode == 0 else None


def project_root(path):
    return (git(path, "rev-parse", "--show-toplevel") or "").strip() or os.path.abspath(path)


def read_files(root, files):
    out = []
    for f in files:
        full = f if os.path.isabs(f) else os.path.join(root, f)
        try:
            with open(full, encoding="utf-8", errors="ignore") as fh:
                out.append(Change(os.path.relpath(full, root), fh.read(), ""))
        except OSError:
            pass
    return out


def changes(root, scope, arg):
    """(Change list, commit-message text) for the scope; (None, '') when git cannot answer."""
    if scope == "files":
        return read_files(root, arg), ""
    staged = scope == "staged"
    names = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z") if staged \
        else git(root, "diff", "--name-only", "--diff-filter=ACMR", "-z", arg)
    out, msgs = None, ""
    if names is not None:
        old_ref, new_ref = ("HEAD", "") if staged else (arg.split("..", 1) + ["HEAD"])[:2]
        out = []
        for rel in [n for n in names.split("\0") if n]:
            new = git(root, "show", ":" + rel) if staged else git(root, "show", "%s:%s" % (new_ref or "HEAD", rel))
            old = git(root, "show", "%s:%s" % (old_ref or "HEAD", rel))
            out.append(Change(rel, new or "", old or ""))
        msgs = "" if staged else (git(root, "log", "--format=%B", arg) or "")
    return out, msgs


def added_lines(change):
    """Lines present in the new text but not in the old one, with their 1-based line numbers."""
    old = Counter(change.old.splitlines())
    found = []
    for n, line in enumerate(change.new.splitlines(), 1):
        if old[line] > 0:
            old[line] -= 1
        else:
            found.append((n, line))
    return found


def project_namespace(root):
    value = None
    try:
        tree = miniyaml.parse_file(os.path.join(root, ".oro-ai", "local-env", "env.yml"))
        value = tree.get("project_namespace") if isinstance(tree, dict) else None
        value = getattr(value, "value", value)
    except Exception:  # noqa: BLE001
        pass
    return value if isinstance(value, str) and value.strip() else None


def check_decorates(root, ch, notes):
    found = []
    if ch.path.startswith(("src/", "config/")) and ch.path.endswith(CODE_EXT):
        for target in _decorates.new_targets(ch.new, ch.old, ch.new):
            reason = _decorates.deny_reason(root, target)
            found += [Finding("deny", "decorates-unsafe-target", ch.path, reason)] if reason else []
    return found


def check_appbundle(root, ch, notes):
    hit = APPBUNDLE.search(ch.path) or (ch.path.endswith(CODE_EXT) and any(APPBUNDLE.search(l) for _, l in added_lines(ch)))
    msg = "AppBundle/ is the git-ignored spike bundle; nothing may be committed from it or depend on it"
    return [Finding("deny", "review-no-appbundle", ch.path, msg)] if hit else []


def check_project_namespace(root, ch, notes):
    found, ns = [], project_namespace(root)
    if not ns:
        notes.add("project_namespace unset in .oro-ai/local-env/env.yml: Aaxis-independence check skipped")
    elif ch.path.startswith("src/Aaxis/") and ch.path.endswith(".php"):
        pat = re.compile(r"^\s*use\s+\\?%s\\" % re.escape(ns), re.M)
        found = [Finding("deny", "review-no-project-namespace", "%s:%d" % (ch.path, ch.new[:m.start()].count("\n") + 1),
                         "Aaxis bundles are reused across projects and must not use %s\\" % ns) for m in pat.finditer(ch.new)]
    return found


def check_direct_io(root, ch, notes):
    found = []
    if ch.path.startswith("src/") and ch.path.endswith(CODE_EXT) and "/Tests/" not in ch.path:
        for n, line in added_lines(ch):
            bad = (IO_CALL.search(line) and not IO_SAFE.search(line)) or PROJECT_DIR_PARAM.search(line)
            found += [Finding("warn", "review-direct-io", "%s:%d" % (ch.path, n),
                              "direct disk path I/O; use the Gaufrette/Oro file manager so it works on shared storage")] if bad else []
    return found


CHECKS = [("decorates-unsafe-target", check_decorates), ("review-no-appbundle", check_appbundle),
          ("review-no-project-namespace", check_project_namespace), ("review-direct-io", check_direct_io)]


def line_exists(root, rel, line):
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="ignore") as fh:
            return line <= sum(1 for _ in fh)
    except OSError:
        return False


def check_citations(root, plan_file, notes):
    """Every `atlas <sub> <term>` cited in a plan/markdown file must hit, and a cited file:line must exist."""
    found = []
    if not index.read_index(atlas_dir(root)):
        notes.add("no atlas index: citation check skipped")
        return found
    try:
        with open(plan_file, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return [Finding("deny", "review-atlas-citations", plan_file, "plan file unreadable")]
    for sub, term, cfile, cline in sorted(set(CITATION.findall(text))):
        try:
            code = cli.main([sub, term, "--project", root, "--limit", "1"], out=io.StringIO())
        except SystemExit:
            code = 64
        if code != 0:
            found.append(Finding("deny", "review-atlas-citations", plan_file, "atlas %s %s has no hit" % (sub, term)))
        elif cfile and not line_exists(root, cfile, int(cline)):
            found.append(Finding("deny", "review-atlas-citations", plan_file, "cited %s:%s does not exist" % (cfile, cline)))
    return found


def gate(root):
    """check id -> 'run'|'warn'|'skip' from the version registry (an unknown Oro version downgrades deny to warn)."""
    registry = resolve.load_registry(REGISTRY)
    version = detect(root).version
    verdicts = {}
    for cid in [i for i, _ in CHECKS] + ["review-atlas-citations"]:
        d = resolve.check_decision(registry, cid, version)
        verdicts[cid] = "skip" if not d["run"] else ("warn" if d["severity"] == "warn" else "run")
    return verdicts


def run(root, scope="staged", arg=None, plan=None, message=""):
    """(findings, notes, file_count); findings is None when the diff cannot be read."""
    chs, msgs = changes(root, scope, arg)
    if chs is None:
        return None, set(), 0
    verdicts, notes, found = gate(root), set(), []
    for cid, fn in CHECKS:
        if verdicts[cid] != "skip":
            for ch in chs:
                found += [f._replace(severity="warn" if verdicts[cid] == "warn" else f.severity) for f in fn(root, ch, notes)]
    if verdicts["review-no-appbundle"] != "skip" and APPBUNDLE.search(msgs + "\n" + message):
        found.append(Finding("deny", "review-no-appbundle", "commit", "commit message or command references AppBundle/"))
    if plan and verdicts["review-atlas-citations"] != "skip":
        found += check_citations(root, plan, notes)
    if c.enforcement_off():
        found = [f._replace(severity="warn") for f in found]
        notes.add("%s=0: deny findings reported as warnings" % c.OVERRIDE_VAR)
    return found, notes, len(chs)


def log_detail(root, lines):
    path = None
    try:
        d = os.path.join(root, ".oro-ai", "review", "logs")
        c_ensure(os.path.join(root, ".oro-ai", "review"))
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "check-%s.log" % time.strftime("%Y%m%d-%H%M%S"))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        path = None
    return path


def render(root, found, notes, nfiles, verbose=False, limit=CONSOLE_CAP, clip=240):
    """Console lines: capped findings, notes, one summary line (always last)."""
    full = ["%s  %s  %s: %s" % f for f in found]
    shown = full if verbose else [x if len(x) <= clip else x[:clip - 3] + "..." for x in full[:limit]]
    lines = list(shown) + ["note: " + n for n in sorted(notes)]
    deny = sum(1 for f in found if f.severity == "deny")
    if len(full) > len(shown):
        lines.append("... %d more (log: %s)" % (len(full) - len(shown), log_detail(root, full) or "unavailable"))
    lines.append("review check: %s (%d files, %d deny, %d warn)" % ("FAIL" if deny else "ok", nfiles, deny, len(found) - deny))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aaxis-oro review check", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=os.getcwd())
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true", help="the staged diff (default)")
    g.add_argument("--range", metavar="A..B")
    g.add_argument("--files", nargs="+", metavar="F")
    ap.add_argument("--plan", metavar="FILE", help="plan/markdown file whose atlas citations are verified")
    ap.add_argument("--message", default="", help="commit message or command text to scan for AppBundle/")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    root = project_root(a.project)
    scope, arg = ("range", a.range) if a.range else ("files", a.files) if a.files else ("staged", None)
    found, notes, n = run(root, scope, arg, a.plan, a.message)
    code = 3
    if found is None:
        sys.stderr.write("aaxis-oro review check: cannot read the diff in %s\n" % root)
    else:
        code = 1 if any(f.severity == "deny" for f in found) else 0
        if a.json:
            print(json.dumps({"exit": code, "files": n, "notes": sorted(notes), "findings": [f._asdict() for f in found]}))
        else:
            print("\n".join(render(root, found, notes, n, a.verbose)))
    return code
