"""Runtime dumps from the Symfony container, cached once per build."""
import glob
import json
import os
import time

from .common import run_php_json

DUMPS = {
    "container": ("container.json", ["debug:container", "--env=prod", "--format=json"]),
    "events": ("events.json", ["debug:event-dispatcher", "--env=prod", "--format=json"]),
}


def container_cache_mtime(root):
    """Newest compiled prod container; a cache:clear after the dump makes the dump outdated."""
    paths = glob.glob(os.path.join(root, "var", "cache", "prod", "*Container*.php"))
    return max(map(os.path.getmtime, paths), default=None)


def _outdated(ctx, path):
    built = container_cache_mtime(ctx.root)
    return not os.path.isfile(path) or (built is not None and built > os.path.getmtime(path))


def _cached(ctx, key):
    fname, args = DUMPS[key]
    path = os.path.join(ctx.raw_dir, fname)
    if ctx.refresh_raw or _outdated(ctx, path):
        data = run_php_json(ctx.root, args)
        os.makedirs(ctx.raw_dir, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    else:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    return data


def container(ctx):
    return _cached(ctx, "container")


def events(ctx):
    return _cached(ctx, "events")


def clear(ctx):
    """Drop cached dumps; called at the start of every full build."""
    for fname, _ in DUMPS.values():
        path = os.path.join(ctx.raw_dir, fname)
        if os.path.isfile(path):
            os.remove(path)


def age_seconds(ctx, key):
    path = os.path.join(ctx.raw_dir, DUMPS[key][0])
    return time.time() - os.path.getmtime(path) if os.path.isfile(path) else None
