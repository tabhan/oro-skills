#!/usr/bin/env python3
"""UserPromptSubmit hook: forced-eval nudge to consult atlas on Oro extension work."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402
from atlas import task  # noqa: E402

# Oro-specific vocabulary is enough on its own; generic words need a second hit to avoid noise.
STRONG = re.compile(
    r"\b(oro\w*|ootb|datagrids?|workflows?|mediator|jsmodules|interceptor|extension points?|message queue|"
    r"mq|layouts?|layout updates?|block types?|system config\w*|service tags?|entity[- ]extend|compiler pass)\b",
    re.I,
)
KEYWORDS = re.compile(
    r"\b(decorat\w*|overrid\w*|aspect|events?|listen\w*|subscriber|grid|operations?|processors?|topics?|"
    r"cron|tags?|hook into|repository|entit(?:y|ies)|typehint\w*|data provider|console command)\b",
    re.I,
)
MIN_HITS = 2
NUDGE = (
    "[atlas] Oro extension work: before grepping vendor/, run `%s --project %s search <term>` "
    "(or event|tag|service|unsafe|grid|layout|workflow|operation|mq|config|entity|js). Reuse an OOTB hook; "
    "never `decorates:` a service listed by `atlas unsafe` (use aaxis_aspect.interceptor). "
    "State which atlas hit you used, or that none matched, before editing."
)
ATLAS = "%s atlas" % c.CLI
PROCESS = (
    "[aaxis-oro] Ticket %s: CLAUDE_project.md 'Ticket process' applies (overrides any fast path). "
    "Start with `%s task init %s`."
)


# Harness-injected text (background-task notifications, reminders) arrives in `prompt` too; Claude Code's payload has
# no field marking it, so ticket keys are read only from the user's own text outside these wrappers.
WRAPPED = re.compile(r"<(task-notification|system-reminder)\b[^>]*>.*?(?:</\1>|\Z)|\[SYSTEM NOTIFICATION.*\Z", re.S | re.I)


def user_text(prompt):
    return WRAPPED.sub(" ", prompt or "")


def decide(payload):
    """(output, verdict): nudge once per session when the prompt is clearly Oro extension work."""
    root = c.project_root(payload.get("cwd") or os.getcwd())
    prompt = payload.get("prompt", "")
    score = len({m.lower() for m in KEYWORDS.findall(prompt)}) + (MIN_HITS if STRONG.search(prompt) else 0)
    path, state = c.session_state(payload.get("session_id"))
    out, verdict = None, "skip"
    if root and score >= MIN_HITS and state.get("nudged"):
        verdict = "already-nudged"
    elif root and score >= MIN_HITS:
        status = c.index_state(root)
        text = NUDGE % (ATLAS, root) + ("" if status == "ok" else " " + c.build_hint(root, status))
        state["nudged"] = True
        c.save_state(path, state)
        out, verdict = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": c.clip(text)}}, "nudge"
    key = task.key_from(user_text(prompt)) or (task.branch_key(root) if root else None)
    if root and key and task.is_setup(root) and key not in state.get("process_keys", []):
        state["process_keys"] = state.get("process_keys", []) + [key]
        c.save_state(path, state)
        text = PROCESS % (key, c.CLI, key)
        prev = (out or {}).get("hookSpecificOutput", {}).get("additionalContext")
        out = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                      "additionalContext": c.clip(prev + "\n" + text if prev else text)}}
        verdict = "process" if verdict in ("skip", "already-nudged") else verdict + "+process"
    return out, verdict


def main():
    payload = {}
    out, verdict = None, "skip"
    try:
        payload = json.load(sys.stdin)
        out, verdict = decide(payload)
    except Exception as exc:  # noqa: BLE001
        verdict = "error:%s" % type(exc).__name__
    c.log_decision(payload.get("session_id"), "UserPromptSubmit", "", verdict)
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
