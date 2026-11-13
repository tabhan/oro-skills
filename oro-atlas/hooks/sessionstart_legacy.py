#!/usr/bin/env python3
"""SessionStart hook: warn when the project still carries pre-plugin atlas hooks (they would fire twice)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from atlas import legacy  # noqa: E402

SETUP = os.path.join(os.path.dirname(HERE), "bin", "atlas-setup")


def decide(payload):
    project = os.path.abspath(payload.get("cwd") or os.getcwd())
    out = None
    if legacy.project_has_legacy(project):
        text = ("[oro-atlas] %s still registers atlas hooks from the pre-plugin install; they now fire twice. "
                "Remove them (only atlas entries are touched): `%s --cleanup-only %s`" % (legacy.settings_path(project), SETUP, project))
        out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
    return out


def main():
    out = None
    try:
        out = decide(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 - never block a session
        pass
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
