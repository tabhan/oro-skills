#!/usr/bin/env python3
"""PreToolUse hook for Bash: Claude must never set the human-only ORO_ATLAS_ENFORCE switch."""
import json
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402

V = c.OVERRIDE_VAR
# Assignment in command position: `VAR=0 cmd`, `export VAR=..`, `env VAR=.. cmd`, `declare/typeset -x VAR=..`, `${VAR:=..}`.
ASSIGN = re.compile(r"(?:^|[;&|(]\s*)(?:(?:export|declare\s+-\w+|typeset\s+-\w+|env(?:\s+-\S+)*|[A-Za-z_]\w*=\S*)\s+)*%s=|\$\{%s:?=" % (V, V))
GUARDED = r"(?:%s|systemd|supervisor|/etc/environment|environment\.d|\.service\b)" % c.ENV_TARGET_CMD.pattern
REDIRECT_OR_TEE = re.compile(r">>?\s*[\"']?[^\s;&|]*%s|\btee\b[^;&|]*%s" % (GUARDED, GUARDED))
REWRITER = re.compile(r"\bsed\s+(?:-\w*i|--in-place)|\bjq\b|\bpython3?\b|\bperl\b|\bnode\b|\bruby\b|\bawk\s+-i\b|\b(?:cp|mv|install|dd)\b")


def flat(text):
    """Quotes, backslashes and whitespace removed so ORO_ATLAS_"ENFORCE" and split strings still match."""
    return re.sub(r"[\"'\\\s+]", "", text).upper()


def attempts_override(cmd):
    """True only for commands that set the switch or write it into persistent config; read-only mentions pass."""
    unquoted = re.sub(r"[\"'\\]", "", cmd)
    sets = ASSIGN.search(cmd) or ASSIGN.search(unquoted)
    mentions = V in cmd or "ATLAS_ENF" in flat(cmd)
    writes = mentions and re.search(GUARDED, cmd) and (REDIRECT_OR_TEE.search(cmd) or REWRITER.search(cmd))
    return bool(sets or writes)


GIT_COMMIT = re.compile(r"(?:^|[;&|(]\s*)git\b(?:\s+-[Cc]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*\s+commit\b")
GIT_PUSH = re.compile(r"(?:^|[;&|(]\s*)git\b(?:\s+-[Cc]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*\s+push\b")


HOOK_MAX_FILES = 300


def commit_message(cmd, cwd):
    """Message text of the `git commit` in cmd (-m/--message values and -F/--file contents), never the rest of the command line."""
    m = GIT_COMMIT.search(cmd)
    try:
        args = shlex.split(cmd[m.end():]) if m else []
    except ValueError:
        args = []
    parts, i = [], 0
    while i < len(args):
        a = args[i]
        if re.fullmatch(r"-[A-Za-z]*m|--message|-[A-Za-z]*F|--file", a) and i + 1 < len(args):
            val = args[i + 1]
            i += 1
            if a.endswith("F") or a == "--file":
                try:
                    with open(os.path.join(cwd, val), encoding="utf-8", errors="ignore") as fh:
                        val = fh.read()
                except OSError:
                    val = ""
            parts.append(val)
        elif a.startswith("--message=") or a.startswith("-m") and len(a) > 2 and not a.startswith("--"):
            parts.append(a.split("=", 1)[1] if a.startswith("--") else a[2:])
        i += 1
    return "\n".join(parts)


def staged_count(root):
    p = subprocess.run(["git", "-C", root, "diff", "--cached", "--name-only", "--diff-filter=ACMR"], capture_output=True, text=True, errors="ignore")
    return len([x for x in p.stdout.splitlines() if x])


def commit_review(payload, cmd):
    """(output, verdict) from the deterministic review checks on the staged diff; deny only on a deny finding."""
    root = c.project_root(payload.get("cwd") or os.getcwd())
    out, verdict = None, "skip"
    n_staged = staged_count(root) if root else 0
    if root and n_staged > HOOK_MAX_FILES:
        text = "review check skipped (%d files); run: aaxis-oro review check --staged" % n_staged
        out, verdict = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "[review] " + text}}, "skip-large"
    elif root:
        from atlas import review
        found, notes, n = review.run(root, "staged", message=commit_message(cmd, payload.get("cwd") or os.getcwd()))
        lines = review.render(root, found or [], notes, n, limit=6, clip=200)
        hso = {"hookEventName": "PreToolUse"}
        if any(f.severity == "deny" for f in found or []):
            hso.update(permissionDecision="deny", permissionDecisionReason=c.clip("\n".join(lines), 1500))
            out, verdict = {"hookSpecificOutput": hso}, "deny-review"
        elif found:
            hso["additionalContext"] = c.clip("[review] " + "\n".join(lines))
            out, verdict = {"hookSpecificOutput": hso}, "context-review"
    return out, verdict


def push_review(payload):
    """(output, verdict): setup project, ticket branch, code committed: deny the push without a fresh review.md verdict."""
    from atlas import review, task
    root = c.project_root(payload.get("cwd") or os.getcwd())
    key = task.branch_key(root) if root and task.is_setup(root) else None
    problem = task.review_problem(root, key) if key else None
    d = review.resolve.check_decision(review.resolve.load_registry(review.REGISTRY), "review-ticket-push",
                                      review.detect(root).version) if problem else {"run": False}
    out, verdict = None, "skip"
    if d["run"]:
        hso = {"hookEventName": "PreToolUse"}
        if c.enforcement_off() or d["severity"] == "warn":
            hso["additionalContext"] = "[review] review-ticket-push: " + problem
            out, verdict = {"hookSpecificOutput": hso}, "context-push"
        else:
            hso.update(permissionDecision="deny", permissionDecisionReason="review-ticket-push: " + problem)
            out, verdict = {"hookSpecificOutput": hso}, "deny-push"
    return out, verdict


def decide(payload):
    cmd = (payload.get("tool_input") or {}).get("command", "")
    out, verdict = None, "skip"
    if payload.get("tool_name") == "Bash" and GIT_COMMIT.search(cmd) and not attempts_override(cmd):
        out, verdict = commit_review(payload, cmd)
    elif payload.get("tool_name") == "Bash" and GIT_PUSH.search(cmd) and not attempts_override(cmd):
        out, verdict = push_review(payload)
    elif payload.get("tool_name") == "Bash" and attempts_override(cmd):
        reason = "%s is a human-only switch: the user sets it in their own shell. Claude must not set, export or write it anywhere." % c.OVERRIDE_VAR
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}
        verdict = "deny-override-set"
    return out, verdict


def main():
    payload = {}
    out, verdict = None, "error"
    try:
        payload = json.load(sys.stdin)
        out, verdict = decide(payload)
    except Exception as exc:  # noqa: BLE001 - never block a command because the hook broke
        verdict = "error:%s" % type(exc).__name__
    if verdict != "skip":
        c.log_decision(payload.get("session_id"), "Bash", payload.get("cwd", ""), verdict)
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
