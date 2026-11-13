#!/usr/bin/env python3
"""Stop hook: remind the user, once per new bypass, that ORO_ATLAS_ENFORCE=0 let edits through unchecked."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402


def decide(payload):
    path, st = c.session_state(payload.get("session_id"))
    out = None
    bypassed = st.get("bypassed", 0)
    if bypassed > st.get("bypass_reminded", 0):
        st["bypass_reminded"] = bypassed
        c.save_state(path, st)
        out = {"systemMessage": "[oro-atlas] %s=0 was set: %d edit(s) skipped atlas enforcement this session (see ~/.claude/atlas-hook.log). "
                                "Unset it and rebuild/query atlas before shipping." % (c.OVERRIDE_VAR, bypassed)}
    return out


def main():
    out = None
    try:
        out = decide(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 - never block stopping
        pass
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
