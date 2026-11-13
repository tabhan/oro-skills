#!/usr/bin/env python3
"""SessionStart hook: move a legacy atlas index to .oro-ai/atlas in the background (rebuild, then delete the old one)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from atlas import migrate  # noqa: E402
from atlas.common import find_project_root  # noqa: E402


def decide(payload):
    root = find_project_root(payload.get("cwd") or os.getcwd())
    migrate.ensure_data_root_ignore(root)
    out = None
    if migrate.pending(root):
        if os.environ.get("ORO_ATLAS_MIGRATE_SYNC"):
            migrate.run(root, sys.stderr)  # tests: no detached process
        elif not migrate.running(root):
            migrate.spawn(root)
        text = ("[oro-atlas] The atlas index is moving to .oro-ai/atlas: rebuilding in the background (about a minute; "
                "atlas queries answer once it finishes), then the old directory is deleted.")
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
