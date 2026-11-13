#!/usr/bin/env python3
"""SessionStart hook (startup|resume|compact): refresh a stale atlas index, then inject one status line.

Enforcement lives in pretooluse_edit.py; this hook only keeps the index fresh and tells the model (and the user) the state.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402

sys.path.insert(0, os.path.join(c.PLUGIN_ROOT, "lib"))

from atlas import migrate  # noqa: E402


def is_oro(root):
    try:
        with open(os.path.join(root, "composer.lock"), "rb") as fh:
            return b'"oro/' in fh.read()
    except OSError:
        return False


def version_line(root):
    """'Oro 7.0.5 (composer.lock); suppressed: N rules' or the unknown-version advisory; '' when unavailable."""
    text = ""
    try:
        from oroversion import detect, resolve as R
        det = detect(root, write_cache=False)
        if det.known:
            inactive = [u for u, s in R.resolve(c.PLUGIN_ROOT, det.version, skip_tests=True) if s == R.INACTIVE]
            text = "Oro %s (composer.lock); suppressed: %d rules (oro-applies --list-inactive)" % (det.version, len(inactive))
        else:
            text = "Oro version unknown; version-specific rules advisory, deny checks downgrade to warn"
    except Exception:  # noqa: BLE001
        pass
    return text


def refresh(root, sid):
    """(status text, build_failed log or None); a migration in flight owns the rebuild."""
    state = c.index_state(root)
    text, failed = "index fresh", None
    if state != "ok" and migrate.pending(root):
        text = "index %s (migration rebuilding in background)" % state
    elif state != "ok":
        ok, secs, log = c.run_build(root, state == "stale")
        text = "index %s, rebuilt in %ds" % (state, secs) if ok else "index %s, BUILD FAILED (log: %s)" % (state, log)
        failed = None if ok else log
    path, st = c.session_state(sid)
    if failed:
        st["build_failed"] = failed
    else:
        st.pop("build_failed", None)
    c.save_state(path, st)
    return text, failed


def decide(payload):
    root = c.project_root(payload.get("cwd") or os.getcwd())
    out = None
    if root and is_oro(root):
        sid = payload.get("session_id")
        status, _ = refresh(root, sid)
        lines = ["[oro-atlas] %s. Atlas %s." % (version_line(root) or "Oro project", status),
                 "Edits to extension points (Resources/config, listeners, subscribers, Extension.php, entity_extend, layouts, "
                 "workflows, interceptors) are denied until an `atlas <sub> <term>` query has run this session."]
        hso = {"hookEventName": "SessionStart", "additionalContext": "\n".join(lines)}
        out = {"hookSpecificOutput": hso}
        if c.enforcement_off():
            out["systemMessage"] = "%s=0 is set: atlas enforcement is OFF this session (denies become warnings and are logged)." % c.OVERRIDE_VAR
            hso["additionalContext"] += "\n%s=0 set by the user: atlas enforcement is off." % c.OVERRIDE_VAR
            c.log_decision(sid, "SessionStart", root, "enforcement-off")
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
