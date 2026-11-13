"""Shared helpers for the atlas hooks: decision log, project lookup, shard queries."""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

from atlas import cli, index, store  # noqa: E402
from atlas.common import atlas_dir, new_atlas_dir  # noqa: E402

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
    flag = " --incremental" if state == "stale" else ""
    return "atlas index is %s: run `%s --project %s%s` before relying on it." % (state.upper(), BUILD, root, flag)


def index_state(root):
    """'missing', 'stale' or 'ok' for the project's atlas index."""
    out_dir = atlas_dir(root)
    state = "missing"
    if index.read_index(out_dir):
        state = "stale" if index.stale_shards(root, out_dir) else "ok"
    return state


def query(root, shard_cmd, text, limit=3):
    """One-line hits for `text` in a shard subcommand ('tag', 'event', ...); [] when unavailable."""
    out_dir = atlas_dir(root)
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
    out_dir = atlas_dir(root)
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


PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
OVERRIDE_VAR = "ORO_ATLAS_ENFORCE"
BUILD_TIMEOUT = 120

EXTENSION_FILE = re.compile(
    r"(?:/Resources/config/|/Resources/views/layouts/|/layouts/[^/]+/|"
    r"/[^/]*(?:EventListener|Listener|Subscriber|Interceptor)[^/]*\.php$|/[^/]*Extension\.php$|/entity_extend\.ya?ml$)"
)
# Files through which a human-only switch could be flipped behind a Bash deny.
ENV_FILE = re.compile(r"(?:/settings(?:\.local)?\.json|/\.claude/|/\.(?:zsh|bash)rc|/\.z?profile|/\.env[^/]*)$")
QUERY_CMD = re.compile(
    r"(?:^|[\s/;&|(])atlas(?:\.py)?\s+(?:--project\s+\S+\s+)?(?:entity|operation|grid|event|mq|service|config|tags?|layout|workflow|js|search|unsafe|notes)\b"
)


def enforcement_off():
    """Only the process env counts: Claude cannot change it for a running hook."""
    return os.environ.get(OVERRIDE_VAR) == "0"


def is_extension_file(path):
    return bool(EXTENSION_FILE.search(path.replace("\\", "/")))


def check_verdict(root, check_id):
    """'run', 'warn' or 'skip' from `oro-applies --check`; any failure degrades to 'warn', never to a block."""
    verdict = "warn"
    try:
        p = subprocess.run([sys.executable, os.path.join(PLUGIN_ROOT, "bin", "oro-applies"), "--project", root, "--check", check_id, "--json"],
                           capture_output=True, text=True, timeout=5)
        verdict = json.loads(p.stdout).get("verdict", "warn")
    except Exception:  # noqa: BLE001
        pass
    return verdict


def gate(root, check_id, reason, session_id, tool, file):
    """Turn a would-be deny into (permissionDecision, text): deny, or warn when the check, the version or the human override says so."""
    verdict = check_verdict(root, check_id)
    decision, text = "deny", reason
    if verdict == "skip":
        decision, text = None, None
    elif verdict == "warn":
        decision, text = None, "WARNING (not enforced): " + reason
    if decision and enforcement_off():
        path, st = session_state(session_id)
        st["bypassed"] = st.get("bypassed", 0) + 1
        save_state(path, st)
        log_decision(session_id, tool, file, "bypass", check=check_id, reason=reason[:200])
        decision, text = None, "%s=0 is set by the user: enforcement off, this would be denied: %s" % (OVERRIDE_VAR, reason)
    return decision, text


def run_build(root, incremental, log_dir=None):
    """Foreground atlas build; (ok, seconds, log_path_or_None). Output goes to a log, never into the context."""
    start = time.time()
    build = os.environ.get("ORO_ATLAS_BUILD_BIN") or BUILD
    cmd = [sys.executable, build, "--project", root] + (["--incremental"] if incremental else [])
    log = os.path.join(new_atlas_dir(root), "session-build.log")
    ok = False
    try:
        os.makedirs(new_atlas_dir(root), exist_ok=True)
        with open(log, "wb") as fh:
            ok = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=BUILD_TIMEOUT).returncode == 0
    except Exception:  # noqa: BLE001 - timeout, missing php, unwritable dir
        ok = False
    return ok, int(time.time() - start), log
