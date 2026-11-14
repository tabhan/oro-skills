#!/usr/bin/env python3
"""SessionStart dispatcher: one process for what used to be five hooks, same order, same outputs.

- source startup|resume: legacy cleanup, atlas index migration, version-change announcement.
- source startup|resume|compact: atlas status line, always-tier notes.
Each step's `decide(payload)` may return a SessionStart output; contexts are joined, never dropped. A failing step is
skipped so a session can always start. `clear` is not registered, so it never reaches this script.
"""
import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

ONCE = ("sessionstart_legacy", "sessionstart_migrate", "sessionstart_version")
ALWAYS = ("sessionstart_atlas", "sessionstart_notes")


def steps(source):
    """Module names to run for a SessionStart `source` (what the old matchers selected); none for any other source."""
    plan = ()
    if source in (None, "startup", "resume"):
        plan = ONCE + ALWAYS
    elif source == "compact":
        plan = ALWAYS
    return plan


def merge(outputs):
    contexts, messages = [], []
    for out in outputs:
        hso = (out or {}).get("hookSpecificOutput") or {}
        if hso.get("additionalContext"):
            contexts.append(hso["additionalContext"])
        if out and out.get("systemMessage"):
            messages.append(out["systemMessage"])
    merged = None
    if contexts or messages:
        merged = {}
        if contexts:
            merged["hookSpecificOutput"] = {"hookEventName": "SessionStart", "additionalContext": "\n".join(contexts)}
        if messages:
            merged["systemMessage"] = "\n".join(messages)
    return merged


def run(payload):
    outputs = []
    for name in steps(payload.get("source")):
        try:
            outputs.append(importlib.import_module(name).decide(payload))
        except Exception:  # noqa: BLE001 - never block a session
            pass
    return merge(outputs)


def main():
    out = None
    try:
        out = run(json.load(sys.stdin))
    except Exception:  # noqa: BLE001
        pass
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
