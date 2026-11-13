#!/usr/bin/env python3
"""SessionStart hook: print the guidance that (de)activates once when the project's Oro version changed."""
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from oroversion import detect, parse_version  # noqa: E402
from oroversion import diff as D  # noqa: E402

# Separate from version.json: other tools refresh that cache, which would swallow the change.
MARKER = os.path.join(".oro-ai", "version-announced.json")


def record(marker, version):
    # Only an existing .oro-ai/ is written to; hooks never create project files.
    try:
        if os.path.isdir(os.path.dirname(marker)):
            with open(marker, "w", encoding="utf-8") as fh:
                json.dump({"version": str(version)}, fh)
    except OSError:
        pass


def decide(payload, root=ROOT):
    project = os.path.abspath(payload.get("cwd") or os.getcwd())
    res = detect(project, write_cache=False)
    if not res.known:
        return None
    marker = os.path.join(project, MARKER)
    previous = None
    try:
        with open(marker, encoding="utf-8") as fh:
            previous = json.load(fh).get("version")
    except (OSError, ValueError):
        pass
    out = None
    if previous != str(res.version):
        if previous:
            rows = D.diff(root, parse_version(previous), res.version)
            text = "[oro-skills] Oro version changed %s -> %s. Guidance now (de)activated:\n%s" % (previous, res.version, D.format_table(rows))
            out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
        record(marker, res.version)
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
