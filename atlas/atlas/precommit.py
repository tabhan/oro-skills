"""Pre-commit gate: `aaxis-oro review check --staged` (unsafe decorates, AppBundle paths, Aaxis independence, direct I/O)."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "hooks"))

import _decorates  # noqa: E402

EXTS = (".yml", ".yaml", ".xml", ".php")
DIRS = ("src/", "config/")


def git(root, *args):
    p = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, errors="ignore")
    return p.stdout if p.returncode == 0 else ""


def staged_files(root):
    out = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [f for f in out.split("\0") if f.startswith(DIRS) and f.endswith(EXTS)]


def reasons(root):
    found = []
    for rel in staged_files(root):
        new, old = git(root, "show", ":" + rel), git(root, "show", "HEAD:" + rel)
        for target in _decorates.new_targets(new, old, new):
            reason = _decorates.deny_reason(root, target)
            found += ["%s: %s" % (rel, reason)] if reason else []
    return found


def main(argv=None):
    from . import review
    root = git(os.getcwd(), "rev-parse", "--show-toplevel").strip() or os.getcwd()
    found, notes, n = review.run(root, "staged")
    code = 0
    if found is not None:
        for line in review.render(root, found, notes, n)[:-1]:
            sys.stderr.write("aaxis-oro atlas precommit: %s\n" % line)
        code = 1 if any(f.severity == "deny" for f in found) else 0
    return code
