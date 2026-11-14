#!/usr/bin/env python3
"""SessionStart hook: silently remove pre-plugin atlas hooks from settings files (they would fire twice)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from atlas import legacy  # noqa: E402

def decide(payload):
    legacy.cleanup_all(os.path.abspath(payload.get("cwd") or os.getcwd()))
    return None


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
