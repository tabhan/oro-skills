#!/usr/bin/env python3
"""PreToolUse hook (Write|Edit|MultiEdit): in an Oro project, deny writes into the project's own Claude auto-memory dir
unless the content is `scope: global`; project knowledge belongs in .oro-ai/notes/.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402
from atlas import notesmigrate as nm  # noqa: E402


def denied(payload):
    ti = payload.get("tool_input", {}) or {}
    path = ti.get("file_path", "")
    cwd = payload.get("cwd") or os.getcwd()
    root = c.project_root(cwd)
    deny = False
    if root and path:
        mdir = next((d for d in nm.memory_dirs(root, cwd) if nm.inside(path, d)), None)
        if mdir:
            edits = ti.get("edits") if payload.get("tool_name") == "MultiEdit" else None
            parts = [dict(ti, new_string=e.get("new_string", "")) for e in edits] if edits else [ti]
            tool = "Write" if payload.get("tool_name") == "Write" else "Edit"
            deny = not all(nm.write_allowed(p, tool, mdir) for p in parts)
    return deny


def main():
    out = None
    try:
        if denied(json.load(sys.stdin)):
            out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                          "permissionDecisionReason": nm.DENY % "<slug>"}}
    except Exception:  # noqa: BLE001 - a broken hook must not block writes
        pass
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
