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


def read_shard(out_dir, name, terms=None):
    """Yield the shard's records. `terms` (already case-folded query terms) skips, before json decoding, every line that
    cannot match: the raw line is lower-cased and stripped of backslashes (JSON escapes) and each term must occur in it.
    This is only a necessary condition, so callers still score the records they get."""
    path = shard_path(out_dir, name)
    if not os.path.isfile(path):
        raise MissingShard("shard '%s' not built; run: aaxis-oro atlas build --only %s" % (name, name))
    needles = [t.replace("\\", "") for t in (terms or [])]
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if needles:
                flat = line.lower().replace("\\", "")
                if not all(n in flat for n in needles):
                    continue
            line = line.strip()
            if line:
                yield json.loads(line)


def list_shards(out_dir):
    if not os.path.isdir(out_dir):
        return []
    return sorted(f[:-6] for f in os.listdir(out_dir) if f.endswith(".jsonl"))
