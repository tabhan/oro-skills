"""atlas-build driver."""
import argparse
import os
import shutil
import sys
import time

from . import extractors, index, raw, store
from .common import AtlasError, Context, find_project_root


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


def _swap(staging, final):
    """Two renames: readers see either the old or the new tree, never a half-written one."""
    old = "%s.old-%d" % (final, os.getpid())
    if os.path.isdir(final):
        os.rename(final, old)
    os.rename(staging, final)
    shutil.rmtree(old, ignore_errors=True)


def _run(ctx, mods, names, only, out):
    if not only:
        raw.clear(ctx)
    built = {}
    for name in names:
        t0 = time.time()
        built[name] = store.write_shard(ctx.out_dir, name, mods[name].extract(ctx))
        out.write("%-12s %7d records  %.1fs\n" % (name, built[name], time.time() - t0))
        index.update_index(ctx.root, ctx.out_dir, {name: built[name]})
    return built


def build(ctx, only=None, out=sys.stdout):
    mods = extractors.load_all()
    names = extractors.ordered(mods, only)
    final = ctx.out_dir
    lock = acquire_lock(final + ".lock")
    staging = "%s.tmp-%d" % (final, os.getpid())
    try:
        shutil.rmtree(staging, ignore_errors=True)
        if only and os.path.isdir(final):
            shutil.copytree(final, staging)
        os.makedirs(staging, exist_ok=True)
        ctx.out_dir, ctx.raw_dir = staging, os.path.join(staging, "raw")
        built = _run(ctx, mods, names, only, out)
        _swap(staging, final)
    finally:
        ctx.out_dir, ctx.raw_dir = final, os.path.join(final, "raw")
        shutil.rmtree(staging, ignore_errors=True)
        release_lock(lock)
    return built


def main(argv=None):
    ap = argparse.ArgumentParser(prog="atlas-build", description="Generate the oro-atlas index")
    ap.add_argument("--project", help="project root (default: walk up from cwd)")
    ap.add_argument("--only", help="comma-separated categories to (re)build")
    ap.add_argument("--refresh-raw", action="store_true", help="re-dump container/events even if cached")
    args = ap.parse_args(argv)
    code = 0
    try:
        ctx = Context(find_project_root(args.project), refresh_raw=args.refresh_raw)
        only = [n for n in (args.only or "").split(",") if n]
        t0 = time.time()
        build(ctx, only)
        sys.stdout.write("done in %.1fs -> %s\n" % (time.time() - t0, ctx.out_dir))
    except AtlasError as exc:
        sys.stderr.write("atlas-build: %s\n" % exc)
        code = 1
    return code
