"""index.json: per-shard input stamps and counts; each shard is stale only when its own inputs changed."""
import datetime
import functools
import glob
import hashlib
import json
import os
import time

from . import __version__, extractors
from .common import sha256_file

INDEX_NAME = "index.json"
SRC_EXTS = (".php", ".yml", ".yaml", ".xml")
_PKG = os.path.dirname(os.path.abspath(__file__))
# Stamp key -> label shown to the user.
LABELS = {"lock": "composer.lock", "vendor": "vendor", "src": "src", "cache": "container cache", "extractor": "extractor code"}


def composer_lock_sha(root):
    return sha256_file(os.path.join(root, "composer.lock"))


def _walk_sources(root):
    """(relpath, mtime_ns, size) of every file under src/ and config/."""
    found = []
    for top in ("src", "config"):
        for d, _, files in os.walk(os.path.join(root, top)):
            for f in files:
                path = os.path.join(d, f)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                found.append((os.path.relpath(path, root), st.st_mtime_ns, st.st_size))
    return sorted(found)


def _hash_sources(files, exts):
    h = hashlib.sha256()
    for rel, mtime, size in files:
        if rel.endswith(exts):
            h.update(("%s\0%d\0%d\n" % (rel, mtime, size)).encode())
    return h.hexdigest()


def source_fingerprint(root):
    """mtime+size hash of src/**/*.{php,yml,yaml,xml} and config/**; cheap enough to run per query."""
    files = _walk_sources(root)
    h = hashlib.sha256()
    for rel, mtime, size in files:
        if rel.startswith("config" + os.sep) or rel.endswith(SRC_EXTS):
            h.update(("%s\0%d\0%d\n" % (rel, mtime, size)).encode())
    return h.hexdigest()


def vendor_state(root):
    """Install state of vendor/ (composer rewrites installed.json on every install/update)."""
    try:
        st = os.stat(os.path.join(root, "vendor", "composer", "installed.json"))
        state = "%d:%d" % (st.st_mtime_ns, st.st_size)
    except OSError:
        state = None
    return state


def cache_state(root):
    """Newest compiled prod container: it changes whenever service wiring is rebuilt (src, config or vendor)."""
    stamps = []
    for p in glob.glob(os.path.join(root, "var", "cache", "prod", "*Container*.php")):
        try:
            stamps.append(os.stat(p).st_mtime_ns)
        except OSError:
            pass
    return str(max(stamps)) if stamps else None


@functools.lru_cache(maxsize=1)
def extractor_sha():
    """Hash of the atlas code that shapes records, so upgrading an extractor invalidates what it built."""
    paths = sorted(glob.glob(os.path.join(_PKG, "extractors", "*.py")))
    paths += [os.path.join(_PKG, n) for n in ("common.py", "miniyaml.py", "raw.py")]
    h = hashlib.sha256()
    for p in paths:
        h.update(sha256_file(p).encode())
    return h.hexdigest()


def current_stamps(root, names):
    """{shard: {input: value}} for the project as it is now; None marks an input the shard does not use."""
    files = _walk_sources(root)
    lock, vendor, cache, ext = composer_lock_sha(root), vendor_state(root), cache_state(root), extractor_sha()
    by_exts = {}
    result = {}
    for name in names:
        spec = extractors.inputs_of(name)
        exts = tuple(spec["src"])
        if exts and exts not in by_exts:
            by_exts[exts] = _hash_sources(files, exts)
        result[name] = {
            "lock": lock, "vendor": vendor, "extractor": ext,
            "src": by_exts.get(exts) if exts else None,
            "cache": cache if spec["cache"] else None,
        }
    return result


def platform_version(root):
    """Version of oro/platform from composer.lock, or None."""
    with open(os.path.join(root, "composer.lock"), encoding="utf-8") as fh:
        data = json.load(fh)
    pkgs = data.get("packages", []) + data.get("packages-dev", [])
    return next((p["version"] for p in pkgs if p.get("name") == "oro/platform"), None)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_index(out_dir):
    path = os.path.join(out_dir, INDEX_NAME)
    result = None
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            result = json.load(fh)
    return result


def update_index(root, out_dir, built, durations=None, pre=None):
    """Merge freshly built {shard: count} into index.json, stamping each shard with its own inputs."""
    idx = read_index(out_dir) or {"shards": {}}
    sha = composer_lock_sha(root)
    stamps = current_stamps(root, built)
    for name, before in (pre or {}).items():
        # Inputs snapshotted before extraction, so an edit made mid-build still reads as stale; the
        # container cache is re-read because dumping it may legitimately (re)create it.
        if name in stamps:
            stamps[name] = dict(before, cache=stamps[name]["cache"])
    stamp = now_iso()
    for name, count in built.items():
        idx["shards"][name] = {
            "count": count, "generated_at": stamp, "built_ns": time.time_ns(),
            "inputs": stamps[name], "build_seconds": round((durations or {}).get(name, 0), 2) or None,
            "composer_lock_sha256": sha,
        }
    idx.update(
        atlas_version=__version__,
        composer_lock_sha256=sha,
        platform_version=platform_version(root),
        generated_at=stamp,
    )
    idx.pop("src_fingerprint", None)
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, INDEX_NAME + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(idx, fh, indent=2, sort_keys=True)
    os.replace(tmp, os.path.join(out_dir, INDEX_NAME))
    return idx


def known_shards():
    return sorted(extractors.load_all())


def _own_reasons(meta, now):
    saved = meta.get("inputs")
    if saved is None:
        return ["index format"]
    return [LABELS[k] for k in LABELS if saved.get(k) != now.get(k)]


def shard_status(root, out_dir, names=None, check_files=True):
    """{shard: {"state": fresh|stale|missing, "reasons": [...]}} for the requested (default: all known) shards."""
    from . import store
    idx = read_index(out_dir) or {"shards": {}}
    wanted = sorted(set(names) if names is not None else set(known_shards()) | set(idx["shards"]))
    scope = sorted(set(wanted) | set(idx["shards"]))
    now = current_stamps(root, scope)
    result = {}
    for name in wanted:
        meta = idx["shards"].get(name)
        if meta is None or (check_files and not os.path.isfile(store.shard_path(out_dir, name))):
            result[name] = {"state": "missing", "reasons": ["not built"]}
        else:
            reasons = _own_reasons(meta, now[name])
            result[name] = {"state": "stale" if reasons else "fresh", "reasons": reasons}
    _propagate(idx, result)
    return result


def _propagate(idx, result):
    """A shard built from another shard is stale when that shard is stale or was rebuilt after it."""
    mods = extractors.load_all()
    changed = True
    while changed:
        changed = False
        for name, st in result.items():
            if st["state"] != "fresh" or name not in mods:
                continue
            for dep in extractors.depends_of(mods, name):
                dep_meta, meta = idx["shards"].get(dep, {}), idx["shards"].get(name, {})
                dep_st = result.get(dep, {"state": "fresh"})["state"]
                newer = dep_meta.get("built_ns", 0) > meta.get("built_ns", 0)
                if dep_st != "fresh" or newer:
                    result[name] = {"state": "stale", "reasons": ["shard " + dep]}
                    changed = True


def stale_reasons(root, out_dir, names=None):
    """{shard: [reason, ...]} for built shards whose own inputs changed (missing shards are not listed)."""
    idx = read_index(out_dir) or {"shards": {}}
    picked = [n for n in idx["shards"] if names is None or n in names]
    status = shard_status(root, out_dir, picked, check_files=False)
    return {n: s["reasons"] for n, s in sorted(status.items()) if s["state"] == "stale"}


def stale_shards(root, out_dir, names=None):
    return sorted(stale_reasons(root, out_dir, names))


def stale_line(root, out_dir, names=None):
    reasons = stale_reasons(root, out_dir, names)
    by_reason = {}
    for name, rs in reasons.items():
        by_reason.setdefault(" and ".join(rs), []).append(name)
    parts = ["%s changed since %s built" % (r, ",".join(ns)) for r, ns in sorted(by_reason.items())]
    return ("STALE: %s; run atlas-build --incremental" % "; ".join(parts)) if parts else None
