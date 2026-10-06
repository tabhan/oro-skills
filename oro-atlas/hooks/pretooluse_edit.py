#!/usr/bin/env python3
"""PreToolUse hook for Edit/Write/MultiEdit on src|config/**/*.yml|xml|php.

Adds atlas context for the extension point being touched and denies a new
`decorates:` whose target is concretely typehinted elsewhere (unsafe shard).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402
import _decorates as d  # noqa: E402

WATCHED = re.compile(r"/(?:src|config)/.*\.(?:ya?ml|php|xml)$")

TAG_NAME = re.compile(r"(?:name:\s*|tag:\s*|tags:\s*\[?\s*)['\"]?([a-z][\w]*(?:[.][\w]+)+)['\"]?")
EVENT_NAME = re.compile(r"(?:event:\s*|AsEventListener\(\s*event:\s*)['\"]?([\w.\\\-]+)['\"]?")


def read_file(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def added_text(tool, ti):
    """(new_text, old_text) the tool call would introduce / replace."""
    if tool == "Write":
        new, old = ti.get("content", ""), read_file(ti.get("file_path", ""))
    elif tool == "MultiEdit":
        edits = ti.get("edits", [])
        new, old = "\n".join(e.get("new_string", "") for e in edits), "\n".join(e.get("old_string", "") for e in edits)
    else:
        new, old = ti.get("new_string", ""), ti.get("old_string", "")
    return new, old


def context_lines(root, path, new):
    lines = []
    base = os.path.basename(path)
    for name in sorted(set(TAG_NAME.findall(new)))[:3]:
        lines += ["tag " + h for h in c.query(root, "tag", name, 1)]
    if "kernel.event_listener" in new or "kernel.event_subscriber" in new or "getSubscribedEvents" in new or "AsEventListener" in new:
        for ev in sorted(set(EVENT_NAME.findall(new)))[:3]:
            lines += ["event " + h for h in c.query(root, "event", ev, 1)]
        lines.append("Prefer an existing listener/free-hook event over a new dispatch; check 'atlas event <name>'.")
    if "aaxis_aspect.interceptor" in new or "Interceptor" in base:
        lines += ["interceptor " + h for h in c.query(root, "tag", "aaxis_aspect.interceptor", 1)]
    if base in ("datagrids.yml", "datagrids.yaml"):
        lines.append("Datagrid: extend/override via 'atlas grid <name>' (also_defined/listeners) before defining a new grid.")
    if base in ("workflows.yml", "actions.yml"):
        lines.append("Workflow/operation: check 'atlas workflow <name>' / 'atlas operation <name>' for clones and disable_operations.")
    return lines


def decide(payload):
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input", {}) or {}
    path = ti.get("file_path", "")
    out, verdict = None, "skip"
    if tool in ("Edit", "Write", "MultiEdit") and WATCHED.search(path):
        root = c.project_root(path)
        if root:
            out, verdict = analyse(root, path, tool, ti)
    return out, verdict, path


def analyse(root, path, tool, ti):
    new, old = added_text(tool, ti)
    state = c.index_state(root)
    notes, reason = [], None
    if state != "ok":
        notes.append(c.build_hint(root, state))
    # A stale index still knows the unsafe services; only a missing one cannot judge.
    if state != "missing":
        found = d.new_targets(new, old, read_file(path) + "\n" + new)
        reason = next(filter(None, (d.deny_reason(root, t) for t in found)), None)
        notes += context_lines(root, path, new)
        if found and not reason:
            notes.append("decorates: target not in the unsafe shard; confirm with 'atlas unsafe <service>'.")
    hso = {"hookEventName": "PreToolUse"}
    verdict = "silent"
    if reason:
        hso.update(permissionDecision="deny", permissionDecisionReason=c.clip(reason, 1500))
        verdict = "deny"
    if notes:
        hso["additionalContext"] = c.clip("[oro-atlas] " + "\n".join(notes))
        verdict = verdict if reason else "context"
    return ({"hookSpecificOutput": hso} if verdict != "silent" else None), verdict


def main():
    payload = {}
    out, verdict, path, tool = None, "error", "", ""
    try:
        payload = json.load(sys.stdin)
        tool = payload.get("tool_name", "")
        out, verdict, path = decide(payload)
    except Exception as exc:  # noqa: BLE001 - never block an edit because the hook broke
        verdict = "error:%s" % type(exc).__name__
    c.log_decision(payload.get("session_id"), tool, path, verdict)
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
