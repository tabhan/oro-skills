#!/usr/bin/env python3
"""PreToolUse hook for Bash: Claude must never set the human-only ORO_ATLAS_ENFORCE switch."""
import json
import os
import re
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


def commit_review(payload, cmd):
    """(output, verdict) from the deterministic review checks on the staged diff; deny only on a deny finding."""
    root = c.project_root(payload.get("cwd") or os.getcwd())
    out, verdict = None, "skip"
    if root:
        from atlas import review
        found, notes, n = review.run(root, "staged", message=cmd)
        lines = review.render(root, found or [], notes, n, limit=6, clip=200)
        hso = {"hookEventName": "PreToolUse"}
        if any(f.severity == "deny" for f in found or []):
            hso.update(permissionDecision="deny", permissionDecisionReason=c.clip("\n".join(lines), 1500))
            out, verdict = {"hookSpecificOutput": hso}, "deny-review"
        elif found:
            hso["additionalContext"] = c.clip("[review] " + "\n".join(lines))
            out, verdict = {"hookSpecificOutput": hso}, "context-review"
    return out, verdict


def decide(payload):
    cmd = (payload.get("tool_input") or {}).get("command", "")
    out, verdict = None, "skip"
    if payload.get("tool_name") == "Bash" and GIT_COMMIT.search(cmd) and not attempts_override(cmd):
        out, verdict = commit_review(payload, cmd)
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
