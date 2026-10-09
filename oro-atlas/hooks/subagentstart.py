#!/usr/bin/env python3
"""SubagentStart hook: tell every subagent in an indexed Oro project to query atlas before grepping vendor/.

UserPromptSubmit only reaches the main session; this is the one nudge that reaches implementers.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402

ATLAS = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin", "atlas")
TEXT = (
    "[oro-atlas] Before grepping vendor/ or reading core code, query the extension-point index: "
    "`%(atlas)s --project %(root)s <sub> <term>`, <sub> = entity|operation|grid|event|mq|service|config|tags|layout|workflow|js|search (0.1s, file:line). "
    "Run `unsafe <Class>` before any `decorates:`. Cite hits as file:line. "
    "If `atlas status` exits 2 the index is stale: run `%(atlas)s build --project %(root)s --incremental` first."
)


def decide(payload):
    root = c.project_root(payload.get("cwd") or os.getcwd())
    out, verdict = None, "skip"
    if root and c.index_state(root) != "missing":
        text = TEXT % {"atlas": ATLAS, "root": root}
        out = {"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": c.clip(text, 900)}}
        verdict = "inject"
    return out, verdict


def main():
    payload = {}
    out, verdict = None, "error"
    try:
        payload = json.load(sys.stdin)
        out, verdict = decide(payload)
    except Exception as exc:  # noqa: BLE001 - never block a subagent
        verdict = "error:%s" % type(exc).__name__
    c.log_decision(payload.get("session_id"), "SubagentStart", payload.get("agent_type", ""), verdict)
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
