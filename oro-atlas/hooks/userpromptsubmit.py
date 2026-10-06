#!/usr/bin/env python3
"""UserPromptSubmit hook: forced-eval nudge to consult oro-atlas on Oro extension work."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402

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
    "[oro-atlas] Oro extension work detected. Your FIRST step, before grep or reading vendor code, is to run "
    "the atlas index (%s --project %s search <term>; subcommands: "
    "event tag service unsafe grid layout workflow operation mq config entity js). "
    "Reuse an OOTB hook first; never `decorates:` a service in `atlas unsafe` - use aaxis_aspect.interceptor. "
    "State which atlas hit you used (or that none matched) before editing."
)
ATLAS = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin", "atlas")


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
