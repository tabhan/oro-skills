#!/usr/bin/env python3
"""PreToolUse hook (Read|Edit|Write|MultiEdit): show titles of anchored project notes that cover the touched file, once per file per session."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402
from atlas import index, notesindex  # noqa: E402
from atlas.common import atlas_dir  # noqa: E402

MAX_NOTES = 5
NS = re.compile(r"^\s*namespace\s+([\w\\]+)\s*;", re.M)
CLS = re.compile(r"^\s*(?:(?:final|abstract|readonly)\s+)*(?:class|interface|trait|enum)\s+(\w+)", re.M)


def record_for(root, path):
    """Atlas-like hit for a file: project-relative path, plus the FQCN of a PHP file so class/entity anchors match."""
    rec = {"file": os.path.relpath(path, root).replace(os.sep, "/")}
    if path.endswith(".php"):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                head = fh.read(6000)
            ns, cls = NS.search(head), CLS.search(head)
            if cls:
                rec["class"] = (ns.group(1) + "\\" if ns else "") + cls.group(1)
        except OSError:
            pass
    return rec


def decide(payload):
    ti = payload.get("tool_input", {}) or {}
    path = ti.get("file_path", "")
    out = None
    root = c.project_root(path) if path and os.path.isabs(path) else None
    if root and notesindex.note_files(root):
        sid = payload.get("session_id")
        pth, st = c.session_state(sid)
        seen = st.setdefault("notes_files", [])
        rec = record_for(root, path)
        out_dir = atlas_dir(root)
        notes = notesindex.load(out_dir)
        if rec["file"] not in seen:
            text = None
            if not notes:
                if not st.get("notes_hint"):
                    st["notes_hint"] = True
                    text = "project notes not indexed; build: %s atlas build --project %s --only notes" % (c.CLI, root)
            else:
                hits = notesindex.anchored_for_path(notes, rec["file"], (index.read_index(out_dir) or {}).get("oro_version"))
                if rec.get("class"):
                    hits += [n for n in notesindex.anchored_for_hit(notes, rec) if n not in hits]
                if hits:
                    text = "Notes for this file: " + "; ".join("%s - %s" % (n["id"], n["title"]) for n in hits[:MAX_NOTES])
                    if len(hits) > MAX_NOTES:
                        text += "; +%d more" % (len(hits) - MAX_NOTES)
                    text += " (read .oro-ai/notes/<slug>.md)"
            seen.append(rec["file"])
            c.save_state(pth, st)
            if text:
                out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "[notes] " + c.clip(text, 800)}}
    return out


def main():
    out = None
    try:
        out = decide(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 - never block a tool call
        pass
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
