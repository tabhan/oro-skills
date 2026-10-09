"""atlas-build driver."""
import argparse
import os
import sys
import time

from . import extractors, index, raw, store
from .common import AtlasError, Context, ensure_ignored, find_project_root


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock_owner(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return int(fh.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def acquire_lock(path):
    """O_EXCL lock file holding our pid; a lock left by a dead build is taken over."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            owner = _lock_owner(path)
            if owner and _pid_alive(owner):
                raise AtlasError("another atlas-build (pid %d) is running; lock %s" % (owner, path))
            os.remove(path)
            continue
        with os.fdopen(fd, "w") as fh:
            fh.write(str(os.getpid()))
        return path
    raise AtlasError("could not acquire build lock %s" % path)


def release_lock(path):
    if _lock_owner(path) == os.getpid():
        os.remove(path)


LOCK_NAME = ".lock"
MAX_PASSES = 3


def lock_path(out_dir):
    return os.path.join(out_dir, LOCK_NAME)


def build_running(out_dir):
    """True while a live build process holds the lock."""
    owner = _lock_owner(lock_path(out_dir))
    return bool(owner) and _pid_alive(owner)


def _run(ctx, mods, names, only, out):
    if not only:
        raw.clear(ctx)
    # Snapshot before extracting: an edit landing mid-build must still show as stale afterwards.
    pre = index.current_stamps(ctx.root, names)
    built = {}
    for name in names:
        t0, memo0 = time.time(), ctx.memo_seconds
        built[name] = store.write_shard(ctx.out_dir, name, mods[name].extract(ctx))
        took = time.time() - t0
        out.write("%-12s %7d records  %.1fs\n" % (name, built[name], took))
        # Memoised vendor scans are a one-off cost; the steady-state time is what predicts a cheap refresh.
        index.update_index(ctx.root, ctx.out_dir, {name: built[name]}, {name: took - (ctx.memo_seconds - memo0)}, {name: pre[name]})
    return built


def build(ctx, only=None, out=sys.stdout):
    """Build in place under the lock; each shard and index.json are replaced atomically, so readers never see a partial file."""
    mods = extractors.load_all()
    names = extractors.ordered(mods, only)
    ensure_ignored(ctx.out_dir)
    lock = acquire_lock(lock_path(ctx.out_dir))
    try:
        built = _run(ctx, mods, names, only, out)
    finally:
        if ctx._locator is not None:
            ctx._locator.save()
        release_lock(lock)
    return built


def build_incremental(ctx, out=sys.stdout, background=False):
    """Rebuild stale or missing shards (plus dependents) until none is left; returns {shard: count}.

    background=True skips silently when another build runs: that build re-checks before it exits.
    """
    ensure_ignored(ctx.out_dir)
    built = {}
    for _ in range(MAX_PASSES):
        status = index.shard_status(ctx.root, ctx.out_dir)
        todo = [n for n, st in status.items() if st["state"] != "fresh"]
        if not todo:
            if not built:
                out.write("all %d shards fresh; nothing to rebuild\n" % len(status))
            break
        if background and build_running(ctx.out_dir):
            break
        try:
            built.update(build(ctx, todo, out))
        except AtlasError:
            if not background:
                raise
            break
    return built


def main(argv=None):
    ap = argparse.ArgumentParser(prog="atlas-build", description="Generate the oro-atlas index")
    ap.add_argument("--project", help="project root (default: walk up from cwd)")
    ap.add_argument("--only", help="comma-separated categories to (re)build")
    ap.add_argument("--incremental", action="store_true", help="rebuild only stale or missing shards")
    ap.add_argument("--background", action="store_true", help="with --incremental: exit quietly when a build is already running")
    ap.add_argument("--refresh-raw", action="store_true", help="re-dump container/events even if cached")
    args = ap.parse_args(argv)
    code = 0
    try:
        ctx = Context(find_project_root(args.project), refresh_raw=args.refresh_raw)
        only = [n for n in (args.only or "").split(",") if n]
        t0 = time.time()
        if args.incremental and only:
            raise AtlasError("--incremental and --only are exclusive")
        build_incremental(ctx, background=args.background) if args.incremental else build(ctx, only)
        sys.stdout.write("done in %.1fs -> %s\n" % (time.time() - t0, ctx.out_dir))
    except AtlasError as exc:
        sys.stderr.write("atlas-build: %s\n" % exc)
        code = 1
    return code
