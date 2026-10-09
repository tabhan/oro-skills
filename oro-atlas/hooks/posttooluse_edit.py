#!/usr/bin/env python3
"""PostToolUse hook for Edit/Write/MultiEdit: refresh the atlas index in the background.

Fully silent by design (no stdout, no stderr, no context): it must cost zero model tokens. A running build
holds the index lock, which is the debounce; that build re-checks for changes before it exits.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402
from atlas import build  # noqa: E402

WATCHED = re.compile(r"/(?:src|config)/.*\.(?:ya?ml|php|xml|js|twig)$")


def decide(payload):
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    root = c.project_root(path) if path and WATCHED.search(path) else None
    if root and not os.environ.get("ATLAS_NO_AUTOBUILD") and not build.build_running(c.atlas_dir(root)):
        c.cli.spawn_background(c.atlas_dir(root))


def main():
    try:
        decide(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 - never disturb the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
