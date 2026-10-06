"""JSONL shard storage; one file per category, written atomically."""
import json
import os

from .common import MissingShard


def shard_path(out_dir, name):
    return os.path.join(out_dir, name + ".jsonl")


def write_shard(out_dir, name, records):
    """Write records, return the count; a failing generator leaves the old shard intact."""
    os.makedirs(out_dir, exist_ok=True)
    path = shard_path(out_dir, name)
    tmp = path + ".tmp"
    count = 0
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
                count += 1
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return count


def read_shard(out_dir, name):
    path = shard_path(out_dir, name)
    if not os.path.isfile(path):
        raise MissingShard("shard '%s' not built; run: atlas-build --only %s" % (name, name))
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def list_shards(out_dir):
    if not os.path.isdir(out_dir):
        return []
    return sorted(f[:-6] for f in os.listdir(out_dir) if f.endswith(".jsonl"))
