"""index.json: composer.lock + source fingerprint stamps and per-shard counts, used for staleness."""
import datetime
import hashlib
import json
import os

from . import __version__
from .common import sha256_file

INDEX_NAME = "index.json"


def composer_lock_sha(root):
    return sha256_file(os.path.join(root, "composer.lock"))


SRC_EXTS = (".php", ".yml", ".yaml", ".xml")


def _fingerprint_files(root):
    src = [
        os.path.join(d, f)
        for d, _, files in os.walk(os.path.join(root, "src"))
        for f in files if f.endswith(SRC_EXTS)
    ]
    conf = [os.path.join(d, f) for d, _, files in os.walk(os.path.join(root, "config")) for f in files]
    return sorted(src + conf)


def source_fingerprint(root):
    """mtime+size hash of src/**/*.{php,yml,yaml,xml} and config/**; cheap enough to run per query."""
    h = hashlib.sha256()
    for path in _fingerprint_files(root):
        st = os.stat(path)
        h.update(("%s\0%d\0%d\n" % (os.path.relpath(path, root), st.st_mtime_ns, st.st_size)).encode())
    return h.hexdigest()


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


def update_index(root, out_dir, built):
    """Merge freshly built {shard: count} into index.json, stamping each shard."""
    idx = read_index(out_dir) or {"shards": {}}
    sha = composer_lock_sha(root)
    fp = source_fingerprint(root)
    stamp = now_iso()
    for name, count in built.items():
        idx["shards"][name] = {
            "count": count, "composer_lock_sha256": sha, "src_fingerprint": fp, "generated_at": stamp,
        }
    idx.update(
        atlas_version=__version__,
        composer_lock_sha256=sha,
        src_fingerprint=fp,
        platform_version=platform_version(root),
        generated_at=stamp,
    )
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, INDEX_NAME + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(idx, fh, indent=2, sort_keys=True)
    os.replace(tmp, os.path.join(out_dir, INDEX_NAME))
    return idx


def _reasons(meta, sha, fp):
    checks = (
        ("composer.lock", meta.get("composer_lock_sha256") != sha),
        ("src", meta.get("src_fingerprint") != fp),
    )
    return [label for label, changed in checks if changed]


def stale_reasons(root, out_dir, names=None):
    """{shard: [reason, ...]} for shards whose stamps no longer match the project."""
    idx = read_index(out_dir) or {"shards": {}}
    sha, fp = composer_lock_sha(root), source_fingerprint(root)
    picked = {n: m for n, m in idx["shards"].items() if names is None or n in names}
    found = {n: _reasons(m, sha, fp) for n, m in sorted(picked.items())}
    return {n: r for n, r in found.items() if r}


def stale_shards(root, out_dir, names=None):
    return sorted(stale_reasons(root, out_dir, names))


def stale_line(root, out_dir, names=None):
    reasons = stale_reasons(root, out_dir, names)
    by_reason = {}
    for name, rs in reasons.items():
        by_reason.setdefault(" and ".join(rs), []).append(name)
    parts = ["%s changed since %s built" % (r, ",".join(ns)) for r, ns in sorted(by_reason.items())]
    return ("STALE: %s; run atlas-build" % "; ".join(parts)) if parts else None
