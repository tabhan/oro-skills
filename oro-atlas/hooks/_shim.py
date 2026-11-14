#!/usr/bin/env python3
"""Compat shim for settings written by the pre-plugin install (oro-atlas/hooks/<name>.py): self-heals, does no atlas work."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "atlas"))


def main():
    # The plugin's own hook already runs; stay silent and exit 0 so a stale entry never breaks a prompt.
    try:
        from atlas import legacy
        try:
            cwd = json.load(sys.stdin).get("cwd")
        except Exception:  # noqa: BLE001
            cwd = None
        legacy.cleanup_all(os.path.abspath(cwd or os.getcwd()))
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
