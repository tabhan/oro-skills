#!/usr/bin/env python3
"""PostToolUse hook for Bash: flag unsafe `decorates` written by sed/heredoc/cat into src/ or config/.

Edit/Write are guarded before the fact; Bash writes can only be caught afterwards from the git diff.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402
import _decorates as d  # noqa: E402

WATCHED = re.compile(r"^(?:src|config)/.*\.(?:ya?ml|php|xml)$")


def git(root, *args):
    p = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=10)
    return p.stdout if p.returncode == 0 else ""


def file_changes(root):
    """{relpath: (added_text, removed_text)} for watched files, untracked ones counted as all-added."""
    changes = {}
    current = None
    for line in git(root, "diff", "HEAD", "-U0", "--no-color", "--", "src", "config").splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
        elif current and WATCHED.match(current) and line[:1] in "+-" and not line.startswith("--- "):
            add, rem = changes.get(current, ("", ""))
            changes[current] = (add + line[1:] + "\n", rem) if line[0] == "+" else (add, rem + line[1:] + "\n")
    for rel in filter(WATCHED.match, git(root, "ls-files", "--others", "--exclude-standard", "--", "src", "config").splitlines()):
        changes[rel] = (read(os.path.join(root, rel)), "")
    return changes


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def unsafe_findings(root):
    """[(relpath, target, reason)] for newly introduced decorates of unsafe services."""
    found = [
        (rel, t) for rel, (add, rem) in file_changes(root).items()
        for t in d.new_targets(add, rem, read(os.path.join(root, rel)))
    ]
    return [(rel, t, r) for rel, t, r in ((rel, t, d.deny_reason(root, t)) for rel, t in found) if r]


def decide(payload):
    root = c.project_root(payload.get("cwd") or os.getcwd())
    out, verdict = None, "skip"
    if payload.get("tool_name") == "Bash" and root and c.index_state(root) != "missing":
        path, state = c.session_state(payload.get("session_id"))
        seen = set(state.get("bash_flagged", []))
        fresh = [f for f in unsafe_findings(root) if "%s|%s" % f[:2] not in seen]
        verdict = "silent"
        if fresh:
            state["bash_flagged"] = sorted(seen | {"%s|%s" % f[:2] for f in fresh})
            c.save_state(path, state)
            msg = "[oro-atlas] The Bash command introduced an unsafe decorates in %s. %s Revert it and use an interceptor." % (
                ", ".join(sorted({f[0] for f in fresh})), fresh[0][2])
            out, verdict = {"decision": "block", "reason": c.clip(msg, 1500)}, "block"
    return out, verdict


def main():
    payload = {}
    out, verdict = None, "error"
    try:
        payload = json.load(sys.stdin)
        out, verdict = decide(payload)
    except Exception as exc:  # noqa: BLE001 - a broken hook must not disturb the session
        verdict = "error:%s" % type(exc).__name__
    if verdict != "skip":
        c.log_decision(payload.get("session_id"), "Bash", payload.get("cwd", ""), verdict)
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
