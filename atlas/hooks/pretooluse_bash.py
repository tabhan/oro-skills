#!/usr/bin/env python3
"""PreToolUse hook for Bash: Claude must never set the human-only ORO_ATLAS_ENFORCE switch."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402

# Any mention that is not a plain read (`$VAR` / `${VAR}`) is treated as an attempt to set it.
MENTION = re.compile(r"(?<![$\w{])%s\b|\$\{%s:?=" % (c.OVERRIDE_VAR, c.OVERRIDE_VAR))


def flat(text):
    """Quotes, backslashes and whitespace removed so ORO_ATLAS_"ENFORCE" and split strings still match."""
    return re.sub(r"[\"'\\\s+]", "", text).upper()


def attempts_override(cmd):
    direct = c.OVERRIDE_VAR in cmd and MENTION.search(cmd)
    # Obfuscated assembly is only judged when the command also touches a settings/rc/.env file.
    assembled = c.ENV_TARGET_CMD.search(cmd) and ("ATLAS_ENF" in flat(cmd) or c.OVERRIDE_VAR in flat(cmd))
    return bool(direct or assembled)


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
