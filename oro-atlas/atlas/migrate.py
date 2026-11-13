"""Move the index from its legacy locations to <project>/.oro-ai/atlas/ (rebuild, then delete the old directory)."""
import json
import os
import shutil
import subprocess
import sys

from . import build, extractors, index, store
from .common import LEGACY_SUBDIRS, AtlasError, Context, atlas_dir

LOCK_REL = os.path.join(".oro-ai", "atlas-migrate.lock")
OLD_PATHS = tuple(p.replace(os.sep, "/") for p in LEGACY_SUBDIRS)
NEW_PATH = ".oro-ai/atlas"
ROOT_IGNORE = "*\n!.gitignore\n!config.json\n"


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
    return bool(build._lock_owner(os.path.join(root, LOCK_REL))) and build._pid_alive(build._lock_owner(os.path.join(root, LOCK_REL)))


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
                    new = new.replace(old, NEW_PATH)
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


def run(root, out=sys.stdout):
    """0 migrated or nothing to do, 1 build failed (old index kept), 3 another migration is running."""
    legacy = legacy_dirs(root)
    ensure_data_root_ignore(root)
    if not legacy:
        return 0
    try:
        lock = build.acquire_lock(os.path.join(root, LOCK_REL))
    except AtlasError:
        return 3
    try:
        legacy = legacy_dirs(root)  # a concurrent run may have finished while we waited for the lock
        ctx = Context(root)
        if legacy and not _complete(root, ctx.out_dir):
            build.build(ctx, None, out)
        if not _complete(root, ctx.out_dir):
            raise AtlasError("new index incomplete; keeping %s" % ", ".join(legacy))
        for path in legacy:
            shutil.rmtree(path, ignore_errors=True)
        rewrite_hook_paths(root)
        out.write("atlas index moved to %s (removed %s)\n" % (NEW_PATH, ", ".join(os.path.relpath(p, root) for p in legacy)))
        return 0
    except AtlasError as exc:
        sys.stderr.write("atlas migrate: %s\n" % exc)
        return 1
    finally:
        build.release_lock(lock)


def spawn(root):
    """Detached migration (a rebuild outlasts a hook's timeout); output goes to .oro-ai/atlas-migrate.log."""
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "atlas")
    os.makedirs(os.path.join(root, ".oro-ai"), exist_ok=True)
    with open(os.path.join(root, ".oro-ai", "atlas-migrate.log"), "ab") as log:
        subprocess.Popen([sys.executable, script, "--project", root, "migrate"], stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, start_new_session=True)
