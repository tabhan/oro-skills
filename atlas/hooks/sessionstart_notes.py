#!/usr/bin/env python3
"""SessionStart hook: inject always-tier project notes (capped), flag unmigrated auto-memory, hint a missing notes shard.

Never builds anything; every failure path is silent so a session can always start.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402
from atlas import index, notesindex, notesmigrate  # noqa: E402
from atlas.common import atlas_dir  # noqa: E402


def lines_for(root, cwd):
    out = []
    files = notesindex.note_files(root)
    out_dir = atlas_dir(root)
    notes = notesindex.load(out_dir)
    if files and not notes:
        out.append("%d project note(s) not indexed; build: %s atlas build --project %s --only notes" % (len(files), c.CLI, root))
    if notes:
        version = (index.read_index(out_dir) or {}).get("oro_version")
        shown, held = notesindex.always_notes(notes, version)
        if shown:
            out.append("Project notes (always-tier):")
            out += ["- %s: %s%s" % (n["id"], n["title"], " (possibly stale)" if n.get("possibly_stale") else "") for n in shown]
        if held:
            out.append("%d more always-tier notes not shown (cap %d): run `%s atlas notes --always`; trim or anchor some."
                       % (held, notesindex.ALWAYS_CAP, c.CLI))
    pending = sum(len(notesmigrate.unmigrated(d)) for d in notesmigrate.memory_dirs(root, cwd) if os.path.isdir(d))
    if pending:
        out.append("%d project memories are not migrated: run /aaxis-oro:notes-migrate" % pending)
    return out


def decide(payload):
    cwd = payload.get("cwd") or os.getcwd()
    root = c.project_root(cwd)
    out = None
    if root:
        lines = lines_for(root, cwd if os.path.abspath(cwd) != root else None)
        if lines:
            out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "[notes] " + "\n".join(lines)}}
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
