"""atlas build driver."""
import argparse
import json
import os
import shutil
import sys
import time

from . import extractors, index, raw, store
from .common import CURRENT, GEN_DIR, AtlasError, Context, base_of, new_atlas_dir, NotOroProject, ensure_ignored, require_project_root


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
                raise AtlasError("another atlas build (pid %d) is running; lock %s" % (owner, path))
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
    return os.path.join(base_of(out_dir), LOCK_NAME)


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


FAIL_NAME = ".rebuild-failed.json"
STAGING_SUFFIX = ".staging"


def rebuild_failure(out_dir):
    """{'count', 'ts', 'reason'} of the last failed background rebuild, or None."""
    try:
        with open(os.path.join(base_of(out_dir), FAIL_NAME), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _record_failure(out_dir, reason):
    prev = rebuild_failure(out_dir) or {"count": 0}
    try:
        with open(os.path.join(base_of(out_dir), FAIL_NAME), "w", encoding="utf-8") as fh:
            json.dump({"count": prev["count"] + 1, "ts": time.time(), "reason": reason[:300]}, fh)
    except OSError:
        pass


def _swap_in(staging, base):
    """Publish the staged index as a new generation `<base>/gen/<id>`, then flip `<base>/current` to it with one atomic
    symlink os.replace. Readers resolve `current` once, so each sees one complete generation. The previous generation
    stays for in-flight readers; older ones (and a pre-generation flat index, once superseded) are removed."""
    gens = os.path.join(base, GEN_DIR)
    os.makedirs(gens, exist_ok=True)
    gen = "%020d-%d" % (time.time_ns(), os.getpid())
    for name in (LOCK_NAME, FAIL_NAME):
        try:
            os.remove(os.path.join(staging, name))
        except OSError:
            pass
    shutil.move(staging, os.path.join(gens, gen))
    link = os.path.join(base, CURRENT)
    try:
        prev = os.path.basename(os.readlink(link))
    except OSError:
        prev = None
    tmp = "%s.tmp-%d" % (link, os.getpid())
    try:
        os.remove(tmp)
    except OSError:
        pass
    os.symlink(os.path.join(GEN_DIR, gen), tmp)
    os.replace(tmp, link)
    for old in os.listdir(gens):
        if old not in (gen, prev):
            shutil.rmtree(os.path.join(gens, old), ignore_errors=True)
    if prev:  # flat files are only a live generation until the first flip
        for entry in os.listdir(base):
            if entry.endswith(".jsonl") or entry in (index.INDEX_NAME, "raw", "cache"):
                path = os.path.join(base, entry)
                shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path) else os.remove(path)


def build_staged(root, out=sys.stdout):
    """Background incremental rebuild that never touches the live index until it has fully succeeded.

    Takes the live index lock (another build running: returns 'running', nothing started), copies the live index to
    `<index>.staging`, rebuilds the stale/missing shards there, then publishes it as a new generation (_swap_in). Any failure
    removes the staging copy, leaves the live index untouched and records `.rebuild-failed.json`. Returns
    'built', 'fresh', 'running' or 'failed'.
    """
    base = new_atlas_dir(root)
    live = Context(root).out_dir  # current generation (or the flat index)
    staging = base + STAGING_SUFFIX
    try:
        lock = acquire_lock(lock_path(base))
    except AtlasError:
        return "running"
    result = "failed"
    try:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.copytree(live, staging, ignore=shutil.ignore_patterns(LOCK_NAME, FAIL_NAME, "*.tmp", GEN_DIR, CURRENT))
        ctx = Context(root)
        ctx.out_dir, ctx.raw_dir = staging, os.path.join(staging, "raw")
        built = build_incremental(ctx, out)
        if built:
            _swap_in(staging, base)
        result = "built" if built else "fresh"
        try:
            os.remove(os.path.join(base, FAIL_NAME))
        except OSError:
            pass
    except Exception as exc:  # noqa: BLE001 - the live index stays as it was
        _record_failure(base, "%s: %s" % (type(exc).__name__, exc))
        sys.stderr.write("atlas build: background rebuild failed, kept the old index: %s\n" % exc)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        release_lock(lock)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aaxis-oro atlas build", description="Generate the atlas index")
    ap.add_argument("--project", help="project root (default: walk up from cwd)")
    ap.add_argument("--only", help="comma-separated categories to (re)build")
    ap.add_argument("--incremental", action="store_true", help="rebuild only stale or missing shards")
    ap.add_argument("--background", action="store_true", help="with --incremental: exit quietly when a build is already running")
    ap.add_argument("--refresh-raw", action="store_true", help="re-dump container/events even if cached")
    args = ap.parse_args(argv)
    code = 0
    try:
        ctx = Context(require_project_root(args.project), refresh_raw=args.refresh_raw)
        only = [n for n in (args.only or "").split(",") if n]
        t0 = time.time()
        if args.incremental and only:
            raise AtlasError("--incremental and --only are exclusive")
        if args.incremental and args.background:
            code = 0 if build_staged(ctx.root) != "failed" else 1
            return code
        build_incremental(ctx) if args.incremental else build(ctx, only)
        sys.stdout.write("done in %.1fs -> %s\n" % (time.time() - t0, ctx.out_dir))
    except AtlasError as exc:
        sys.stderr.write("atlas build: %s\n" % exc)
        code = 1
    except NotOroProject as exc:
        sys.stderr.write("aaxis-oro: %s\n" % exc)
        code = 64
    return code
