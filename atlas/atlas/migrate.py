"""Move the index from its legacy locations to <project>/.oro-ai/atlas/ (rebuild, then delete the old directory)."""
import json
import os
import re
import shlex
import shutil
import time
import subprocess
import sys

from . import build, extractors, index, store
from .common import LEGACY_SUBDIRS, AtlasError, Context, new_atlas_dir

# Lock, log and failure marker live inside the index dir, whose own .gitignore (`*`) keeps them out of git.
LOCK_NAME, LOG_NAME, FAIL_NAME = "migrate.lock", "migrate.log", "migrate-failed.json"
RETRY_AFTER_SECONDS = 3600
LOG_MAX_BYTES = 64 * 1024
SPAWNED = "spawned"
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAX_AUTO_FAILURES = 3
OLD_PATHS = tuple(p.replace(os.sep, "/") for p in LEGACY_SUBDIRS)
NEW_PATH = ".oro-ai/atlas"
ROOT_IGNORE = "*\n!.gitignore\n!config.json\n"


def _p(root, name):
    return os.path.join(new_atlas_dir(root), name)


def _fingerprint(root):
    return [index.composer_lock_sha(root), index.source_fingerprint(root)]


def failures(root):
    try:
        with open(_p(root, FAIL_NAME), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def record_failure(root, reason):
    prev = failures(root) or {"count": 0}
    # The parent already counted this attempt when it spawned the child; do not count it twice.
    count = prev["count"] if prev.get("reason") == SPAWNED and reason != SPAWNED else prev["count"] + 1
    os.makedirs(new_atlas_dir(root), exist_ok=True)
    with open(_p(root, FAIL_NAME), "w", encoding="utf-8") as fh:
        json.dump({"count": count, "ts": time.time(), "fingerprint": _fingerprint(root), "reason": reason}, fh)


def gave_up(root):
    return (failures(root) or {}).get("count", 0) >= MAX_AUTO_FAILURES


def may_auto_spawn(root):
    """No automatic retry for an hour after a failure unless composer.lock/src changed; none at all after three."""
    f = failures(root)
    if not f:
        return True
    if f["count"] >= MAX_AUTO_FAILURES:
        return False
    return time.time() - f["ts"] >= RETRY_AFTER_SECONDS or f.get("fingerprint") != _fingerprint(root)


def _command(root):
    return [sys.executable, os.path.join(PLUGIN_ROOT, "bin", "aaxis-oro"), "atlas", "--project", root, "migrate"]


def manual_command(root):
    return " ".join(shlex.quote(part) for part in _command(root))


def legacy_dirs(root):
    """Existing old index directories; a directory only counts when it holds an index or shards (never delete a stranger)."""
    found = []
    for rel in LEGACY_SUBDIRS:
        path = os.path.join(root, rel)
        if os.path.isdir(path) and (os.path.isfile(os.path.join(path, index.INDEX_NAME)) or store.list_shards(path)):
            found.append(path)
    return found


def pending(root):
    return bool(legacy_dirs(root))


def running(root):
    return bool(build._lock_owner(_p(root, LOCK_NAME))) and build._pid_alive(build._lock_owner(_p(root, LOCK_NAME)))


def rewrite_hook_paths(root):
    """Point hook commands in settings.local.json that name an old index path at the new one; True when changed."""
    path = os.path.join(root, ".claude", "settings.local.json")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        data = json.loads(text)
    except (OSError, ValueError):
        return False
    changed = False
    for groups in (data.get("hooks") or {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                new = cmd
                for old in OLD_PATHS:
                    # whole path segments only: `var/atlas-tools` and `myvar/atlas` stay as they are
                    new = re.sub(r"(?<![^\s/\"'=:])" + re.escape(old) + r"(?![\w.-])", NEW_PATH, new)
                if new != cmd:
                    hook["command"], changed = new, True
    if changed:
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(path + ".tmp", path)
    return changed


def ensure_data_root_ignore(root):
    """Create .oro-ai/.gitignore (everything untracked except config.json) once; never overwrite, never when .oro-ai/ is tracked.

    A project that still tracks .oro-ai/ content (plans, task logs) keeps committing it until it untracks it on purpose.
    """
    path = os.path.join(root, ".oro-ai", ".gitignore")
    if os.path.exists(path):
        return False
    tracked = subprocess.run(["git", "-C", root, "ls-files", "--", ".oro-ai"], capture_output=True, text=True)
    if tracked.returncode == 0 and tracked.stdout.strip():
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(ROOT_IGNORE)
    return True


def _complete(root, out_dir):
    status = index.shard_status(root, out_dir)
    return bool(status) and all(st["state"] != "missing" for st in status.values())


def _clear_failures(root):
    if os.path.exists(_p(root, FAIL_NAME)):
        os.remove(_p(root, FAIL_NAME))


def run(root, out=sys.stdout):
    """0 migrated or nothing to do, 1 build failed (old index kept), 3 another migration is running."""
    legacy = legacy_dirs(root)
    ensure_data_root_ignore(root)
    if not legacy:
        _clear_failures(root)
        return 0
    try:
        lock = build.acquire_lock(_p(root, LOCK_NAME))
    except AtlasError:
        return 3
    try:
        legacy = legacy_dirs(root)  # a concurrent run may have finished while we waited for the lock
        ctx = Context(root)
        if legacy and not _complete(root, ctx.out_dir):
            build.build(ctx, None, out)
        if not _complete(root, ctx.out_dir):
            raise AtlasError("new index incomplete; keeping %s" % ", ".join(legacy))
        _clear_failures(root)
        for path in legacy:
            shutil.rmtree(path, ignore_errors=True)
        rewrite_hook_paths(root)
        out.write("atlas index moved to %s (removed %s)\n" % (NEW_PATH, ", ".join(os.path.relpath(p, root) for p in legacy)))
        return 0
    except Exception as exc:  # noqa: BLE001 - any failure keeps the old index and is rate-limited
        sys.stderr.write("atlas migrate: %s\n" % exc)
        record_failure(root, str(exc))
        return 1
    finally:
        build.release_lock(lock)


def _cap_log(path):
    try:
        if os.path.getsize(path) > LOG_MAX_BYTES:
            open(path, "wb").close()
    except OSError:
        pass


def spawn(root):
    """Detached migration (a rebuild outlasts a hook's timeout); output goes to .oro-ai/atlas/migrate.log."""
    os.makedirs(new_atlas_dir(root), exist_ok=True)
    # Counted before Popen so a child that dies at startup still trips the retry gate.
    record_failure(root, SPAWNED)
    log_path = _p(root, LOG_NAME)
    _cap_log(log_path)
    with open(log_path, "ab") as log:
        subprocess.Popen(_command(root), stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
