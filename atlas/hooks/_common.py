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
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
CLI = os.path.join(PLUGIN_ROOT, "bin", "aaxis-oro")


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


def build_command(root, state):
    return "%s atlas build --project %s%s" % (CLI, root, " --incremental" if state == "stale" else "")


def stale_reason(root, state):
    """Short why for the hint line: the changed inputs of the stale shards, or 'no index'."""
    reason = "no index"
    if state == "stale":
        try:
            reasons = index.stale_reasons(root, atlas_dir(root))
            reason = ", ".join(sorted({r for rs in reasons.values() for r in rs})) + " changed"
        except Exception:  # noqa: BLE001
            reason = "inputs changed"
    return reason


def build_hint(root, state):
    """One line naming the index state and the exact rebuild command; atlas never rebuilds on its own."""
    if state == "stale" and staleness_kind(root) == "soft":
        return "atlas index behind your src edits (%s); rebuild when convenient: %s" % (stale_reason(root, state), build_command(root, state))
    return "atlas index %s (%s); rebuild: %s" % (state, stale_reason(root, state), build_command(root, state))


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
        recs = list(store.read_shard(out_dir, cli.SHARDS[shard_cmd], [cli.normalize(t) for t in text.split()]))
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
        for rec in store.read_shard(out_dir, "unsafe", [str(target).lower()]):
            if target in rec.get("keys", []) or target == rec.get("id") or target in rec.get("services", []):
                found = rec
                break
    except Exception:  # noqa: BLE001
        pass
    return found


def clip(text, limit=MAX_CONTEXT):
    return text if len(text.encode("utf-8")) <= limit else text.encode("utf-8")[: limit - 4].decode("utf-8", "ignore") + " ..."


OVERRIDE_VAR = "ORO_ATLAS_ENFORCE"

# Real extension points only (see README "Enforcement"); routing, validation, translations, search.yml and Twig extensions are not.
EXTENSION_FILE = re.compile(
    r"/(?:services[^/]*\.ya?ml|entity_extend\.ya?ml|datagrids\.ya?ml|workflows\.ya?ml|actions\.ya?ml|operations\.ya?ml|"
    r"system_configuration\.ya?ml|jsmodules\.ya?ml|message_queue\.ya?ml|app\.ya?ml)$"
    r"|/Resources/config/(?:[^/]+/)*services/[^/]+\.ya?ml$|/workflows/[^/]+\.ya?ml$|/Resources/views/layouts/.+\.ya?ml$"
    r"|/[^/]*(?:Listener|Subscriber|Interceptor|Decorator|Extension)\.php$"
)
NOT_EXTENSION = re.compile(r"/(?:Tests|Twig)/")
# Files through which a human-only switch could be flipped behind a Bash deny.
ENV_FILE = re.compile(r"(?:/settings[^/]*\.json$|/\.claude/|/\.(?:ba|z|k|c|tc)?sh(?:rc|env)$"
                      r"|/\.(?:bash_profile|bash_login|bash_logout|zprofile|zlogin|zlogout|profile|pam_environment|envrc)$"
                      r"|/\.config/fish/|/etc/(?:profile|bash\.bashrc|zshenv|zprofile|zshrc|environment)|/\.env[^/]*$)")
ENV_TARGET_CMD = re.compile(r"settings[^\s/]*\.json|\.claude/|\.(?:ba|z|k|c|tc)?sh(?:rc|env)\b"
                            r"|\.(?:bash_profile|bash_login|bash_logout|zprofile|zlogin|zlogout|profile|pam_environment|envrc)\b"
                            r"|\.config/fish/|/etc/(?:profile|bash\.bashrc|zshenv|zprofile|zshrc|environment)|\.env\b")
QUERY_CMD = re.compile(
    r"(?:^|[\s/;&|(])aaxis-oro\s+atlas\s+(?:--project\s+\S+\s+)?(?:entity|operation|grid|event|mq|service|config|tags?|layout|workflow|js|search|unsafe|notes)\b"
)


def enforcement_off():
    """Only the process env counts: Claude cannot change it for a running hook."""
    return os.environ.get(OVERRIDE_VAR) == "0"


def is_extension_file(path):
    p = path.replace("\\", "/")
    return bool(EXTENSION_FILE.search(p)) and not NOT_EXTENSION.search(p)


# Index inputs whose change means the index is wrong, not merely behind Claude's own edits.
HARD_REASONS = {"composer.lock", "vendor", "index format"}


def staleness_kind(root):
    """'hard' for lock/vendor/format changes, 'soft' when only src/config/cache/notes/extractor inputs moved."""
    kind = "soft"
    try:
        reasons = index.stale_reasons(root, atlas_dir(root))
        if any(r in HARD_REASONS for rs in reasons.values() for r in rs):
            kind = "hard"
    except Exception:  # noqa: BLE001
        kind = "hard"
    return kind


def check_verdict(root, check_id):
    """'run', 'warn' or 'skip' from `aaxis-oro version applies --check`; any failure degrades to 'warn', never to a block."""
    verdict = "warn"
    try:
        p = subprocess.run([sys.executable, CLI, "version", "applies", "--project", root, "--check", check_id, "--json"],
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
