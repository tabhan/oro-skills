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


# Commands that cannot write a file: no redirect, substitution or in-place flag, every segment led by a read-only tool.
READ_ONLY_HEAD = r"(?:ls|cat|head|tail|wc|pwd|grep|egrep|rg|stat|file|which|date|echo|printf|test|true|jq|tree|du|df|cut|tr|diff|cmp|basename|dirname|realpath|id|whoami|ps|sleep|cd)"
READ_ONLY_GIT = r"git\s+(?:status|log|diff|show|branch|rev-parse|rev-list|ls-files|remote|config\s+--get|blame|describe|fetch)"
READ_ONLY_CLI = r"\S*aaxis-oro\s+(?:atlas|spec|review\s+check|task\s+check)"
READ_ONLY_SEGMENT = re.compile(r"\s*(?:%s|%s|%s)(?:\s|$)" % (READ_ONLY_HEAD, READ_ONLY_GIT, READ_ONLY_CLI))
WRITE_MARK = re.compile(r"[>`]|\$\(|<\(|\s-(?:i|-in-place|exec|delete|fprint)\b|\bsed\s+-\w*i|\btee\b|\bxargs\b|\bfind\b.*-(?:exec|delete)|--output")


def read_only(cmd):
    """True only when the whole command line is made of read-only tools, so the post-hoc git diff cannot find anything new."""
    segments = re.split(r"\s*(?:&&|\|\||;|\||\n)\s*", cmd.strip())
    return bool(cmd.strip()) and not WRITE_MARK.search(cmd) and all(READ_ONLY_SEGMENT.match(x) for x in segments if x)


COMPOSER_CHANGE = re.compile(r"(?:^|[\s;&|(])composer\s+(?:install|update|require|remove)\b")


def track(payload, root):
    """Mark the session as having queried atlas; hint the rebuild command after a composer change. Returns a one-line note or None."""
    cmd = (payload.get("tool_input") or {}).get("command", "")
    path, state = c.session_state(payload.get("session_id"))
    note = None
    if c.QUERY_CMD.search(cmd) and not state.get("queried"):
        state["queried"] = True
        c.save_state(path, state)
    if COMPOSER_CHANGE.search(cmd) and c.index_state(root) != "ok":
        note = "[atlas] composer changed dependencies; " + c.build_hint(root, c.index_state(root))
    return note


def decide(payload):
    root = c.project_root(payload.get("cwd") or os.getcwd())
    out, verdict = None, "skip"
    note = track(payload, root) if payload.get("tool_name") == "Bash" and root else None
    if note:
        out, verdict = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": note}}, "hint"
    cmd = (payload.get("tool_input") or {}).get("command", "")
    if payload.get("tool_name") == "Bash" and root and read_only(cmd):
        pass
    elif payload.get("tool_name") == "Bash" and root and c.index_state(root) != "missing":
        path, state = c.session_state(payload.get("session_id"))
        seen = set(state.get("bash_flagged", []))
        fresh = [f for f in unsafe_findings(root) if "%s|%s" % f[:2] not in seen]
        verdict = "silent"
        if fresh:
            state["bash_flagged"] = sorted(seen | {"%s|%s" % f[:2] for f in fresh})
            c.save_state(path, state)
            msg = "[atlas] The Bash command introduced an unsafe decorates in %s. %s Revert it and use an interceptor." % (
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
