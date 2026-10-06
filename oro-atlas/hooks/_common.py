"""Shared helpers for the atlas hooks: decision log, project lookup, shard queries."""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

from atlas import cli, index, store  # noqa: E402

LOG_PATH = os.path.expanduser("~/.claude/atlas-hook.log")
MAX_CONTEXT = 2000


def log_decision(session_id, tool, file, verdict, **extra):
    """Never raises: logging must not be able to break a tool call."""
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "session_id": session_id, "tool": tool, "file": file, "verdict": verdict}
    rec.update(extra)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def project_root(path):
    """Oro project containing `path`, or None."""
    cur = os.path.abspath(path) if os.path.isdir(path) else os.path.dirname(os.path.abspath(path))
    found = None
    while found is None and cur != os.path.dirname(cur):
        if os.path.isfile(os.path.join(cur, "composer.lock")) and os.path.isfile(os.path.join(cur, "bin", "console")):
            found = cur
        cur = os.path.dirname(cur)
    return found


STATE_DIR = os.path.expanduser("~/.claude/atlas-hook-state")
BUILD = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "bin", "atlas-build")


def session_state(session_id):
    """Per-session dict persisted under ~/.claude; {} when unreadable."""
    path = os.path.join(STATE_DIR, "%s.json" % re.sub(r"[^\w.-]", "_", str(session_id or "none")))
    data = {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        pass
    return path, data


def save_state(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except OSError:
        pass


def build_hint(root, state):
    return "atlas index is %s: run `%s --project %s` before relying on it." % (state.upper(), BUILD, root)


def index_state(root):
    """'missing', 'stale' or 'ok' for the project's atlas index."""
    out_dir = os.path.join(root, "var", "atlas")
    state = "missing"
    if index.read_index(out_dir):
        state = "stale" if index.stale_shards(root, out_dir) else "ok"
    return state


def query(root, shard_cmd, text, limit=3):
    """One-line hits for `text` in a shard subcommand ('tag', 'event', ...); [] when unavailable."""
    out_dir = os.path.join(root, "var", "atlas")
    hits = []
    try:
        recs = list(store.read_shard(out_dir, cli.SHARDS[shard_cmd]))
        found, _ = cli.search_records(recs, text, limit)
        hits = [cli.format_hit(r) for r in found]
    except Exception:  # noqa: BLE001 - hook must degrade silently
        pass
    return hits


def unsafe_for(root, target):
    """The unsafe-shard record whose id/keys/services equal `target`, or None."""
    out_dir = os.path.join(root, "var", "atlas")
    found = None
    try:
        for rec in store.read_shard(out_dir, "unsafe"):
            if target in rec.get("keys", []) or target == rec.get("id") or target in rec.get("services", []):
                found = rec
                break
    except Exception:  # noqa: BLE001
        pass
    return found


def clip(text, limit=MAX_CONTEXT):
    return text if len(text.encode("utf-8")) <= limit else text.encode("utf-8")[: limit - 4].decode("utf-8", "ignore") + " ..."
