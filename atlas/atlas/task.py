"""`aaxis-oro task`: per-ticket process evidence under `.oro-ai/task/<KEY>/`, shared by the CLI, `review check` and hooks.

Only setup projects (`.oro-ai/config.json` present) are in scope; everything else is a no-op.
Mechanics and the escape hatch: README "Ticket process".
"""
import argparse
import os
import re
import subprocess
import sys

KEY = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9]+-\d+)(?![0-9])")
WORDS = r"(approved|pass(?:ed)?|rejected?|fail(?:ed)?|skipped)"
# A `Verdict: <word>` line anywhere, or the verdict word alone opening the file (older gate output wrote bare "PASS").
VERDICT = re.compile(r"^[\s>*_#-]*verdict[\s*_]*:[\s*_`]*%s\b[ \t*_`]*([^\n]*)" % WORDS, re.I | re.M)
LEAD = re.compile(r"\A\s*[>*_#` \t]*%s\b[ \t*_`]*([^\n]*)" % WORDS, re.I)
CANON = {"pass": "approved", "passed": "approved", "reject": "rejected", "fail": "rejected", "failed": "rejected"}
E2E_FILE = re.compile(r"(?:\.feature|\.steps\.ts)$")
PROD_FILE = re.compile(r"^src/.+\.(?:php|ya?ml|xml|twig|js|ts|scss)$")
NOT_PROD = re.compile(r"/(?:Tests|Migrations/Data/Demo)/|/translations/")
BASES = ("origin/develop", "develop", "origin/main", "main", "origin/master", "master")
STATUS_STUB = "# %s status\n\nOne line per milestone (date, step, result).\n\n- [ ] plan written (plan.md)\n" \
              "- [ ] architect-gate verdict saved (architect-gate.md)\n- [ ] e2e scenario red\n- [ ] implementation green\n" \
              "- [ ] review check / verification\n"
PLAN_STUB = "# %s plan\n\n## Extension points\n\nFor each choice: mechanism, source (`aaxis-oro atlas <sub> <term>` -> file:line, " \
            "an `aaxis-oro:solutions` reference, an Oro docs URL).\n\n## Tests\n\nThe e2e scenario(s) written first.\n"


def git(root, *args):
    p = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, errors="ignore")
    return p.stdout.strip() if p.returncode == 0 else None


def is_setup(root):
    return bool(root) and os.path.isfile(os.path.join(root, ".oro-ai", "config.json"))


NOT_TICKET = {"UTF", "ISO", "SHA", "RFC", "PSR", "HTTP", "TLS", "SSL", "ES", "ECMA", "MD", "CVE", "IEC"}


def key_from(text):
    """First ticket-like key in text, skipping standards names such as UTF-8 or ISO-8601."""
    keys = [k for k in KEY.findall(text or "") if k.split("-")[0] not in NOT_TICKET]
    return keys[0] if keys else None


def branch_key(root):
    return key_from(git(root, "rev-parse", "--abbrev-ref", "HEAD"))


def task_dir(root, key):
    return os.path.join(root, ".oro-ai", "task", key)


def gate_state(root, key):
    """('missing'|'unreadable'|'no-verdict'|'approved'|'rejected'|'skipped', reason) from architect-gate.md."""
    path = os.path.join(task_dir(root, key), "architect-gate.md")
    state, reason = "missing", ""
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
            m = VERDICT.search(text) or LEAD.search(text)
            word = m.group(1).lower() if m else None
            state, reason = (CANON.get(word, word), m.group(2).strip(" -:—")) if m else ("no-verdict", "")
        except OSError:
            state = "unreadable"
        if state == "skipped" and not reason:
            state = "no-verdict"
    return state, reason


def branch_files(root):
    """Files changed on this branch vs the first base ref that exists (committed part only); [] when none resolves."""
    for base in BASES:
        if git(root, "rev-parse", "--verify", "-q", base) is not None:
            out = git(root, "diff", "--name-only", "%s...HEAD" % base)
            return [x for x in (out or "").splitlines() if x]
    return []


def is_prod(path):
    return bool(PROD_FILE.search(path)) and not NOT_PROD.search(path) and not E2E_FILE.search(path)


def evidence(root, key, paths):
    """Lines describing missing per-ticket evidence for the given changed paths (gate handled by the caller)."""
    lines = []
    if not os.path.isfile(os.path.join(task_dir(root, key), "STATUS.md")):
        lines.append("no .oro-ai/task/%s/STATUS.md; run: aaxis-oro task init %s" % (key, key))
    if any(is_prod(p) for p in paths) and not any(E2E_FILE.search(p) for p in paths):
        lines.append("production code changed but no e2e *.feature/*.steps.ts on the branch (test-first, aaxis-oro:e2e)")
    return lines


def init(root, key):
    d = task_dir(root, key)
    os.makedirs(d, exist_ok=True)
    made = []
    for name, stub in (("STATUS.md", STATUS_STUB), ("plan.md", PLAN_STUB)):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(stub % key)
            made.append(name)
    return made


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aaxis-oro task", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=("init", "check"))
    ap.add_argument("key", nargs="?", help="ticket key; default: from the branch name")
    ap.add_argument("--project", default=os.getcwd())
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    root = git(a.project, "rev-parse", "--show-toplevel") or os.path.abspath(a.project)
    key = a.key or branch_key(root)
    if not key:
        sys.stderr.write("aaxis-oro task: no ticket key given or in the branch name\n")
        return 64
    if a.action == "init":
        made = init(root, key)
        print("task %s: %s" % (key, ("created " + ", ".join(made)) if made else "exists"))
        return 0
    state, reason = gate_state(root, key)
    staged = (git(root, "diff", "--cached", "--name-only") or "").splitlines()
    problems = evidence(root, key, branch_files(root) + staged)
    if state not in ("approved", "skipped"):
        problems.insert(0, "architect-gate: %s (.oro-ai/task/%s/architect-gate.md needs 'Verdict: approved')" % (state, key))
    print("\n".join(problems + ["task %s: %s (gate %s%s)" % (key, "incomplete" if problems else "ok", state,
                                                            ": " + reason if reason else "")]))
    return 1 if problems else 0
