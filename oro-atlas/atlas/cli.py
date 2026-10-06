"""atlas query CLI: compact one-line-per-hit lookups over the JSONL shards."""
import argparse
import json
import re
import sys

from . import index, store
from .common import AtlasError, MissingShard, find_project_root

# subcommand -> shard filename stem
SHARDS = {
    "event": "events",
    "tag": "tags",
    "service": "services",
    "unsafe": "unsafe",
    "grid": "grids",
    "layout": "layouts",
    "workflow": "workflows",
    "operation": "operations",
    "mq": "mq",
    "config": "config",
    "entity": "entities",
    "js": "js",
}
# Agents often guess the plural form; accept it rather than fail on argparse.
PLURALS = {c: c + "s" for c in ("operation", "event", "tag", "service", "grid", "layout", "workflow", "config")}
PLURALS["entity"] = "entities"
CANONICAL = {v: k for k, v in PLURALS.items()}


PRIMARY_FIELDS = ("id", "keys", "file")
_SLASHES = re.compile(r"\\+")


def normalize(text):
    """Collapse backslash runs so 'Oro\\\\Bundle', 'Oro\\Bundle' and '\\Oro\\Bundle' all compare equal."""
    return _SLASHES.sub("\\\\", str(text).lower()).lstrip("\\")


def _flatten(value):
    if isinstance(value, dict):
        return [s for v in value.values() for s in _flatten(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _flatten(v)]
    return [] if value is None else [normalize(value)]


def _haystack(rec, fields=None):
    # Plain values, not json.dumps: JSON escaping doubles backslashes and breaks FQCN queries.
    picked = rec if fields is None else {f: rec.get(f) for f in fields}
    return "\n".join(_flatten(picked))


def score(rec, terms):
    """Lower is better; None when any term is missing from the record."""
    best = None
    if all(t in _haystack(rec) for t in terms):
        keys = _flatten([rec.get("id", "")] + list(rec.get("keys", [])))
        q = " ".join(terms)
        primary = _haystack(rec, PRIMARY_FIELDS)
        if q in keys:
            best = 0
        elif any(k.startswith(q) for k in keys):
            best = 1
        elif any(q in k for k in keys):
            best = 2
        else:
            # The summary text and list fields (e.g. exclude_datagrids) can echo huge lists, so rank them last.
            text = _haystack(rec, PRIMARY_FIELDS + ("text",))
            best = 3 if all(t in primary for t in terms) else (4 if all(t in text for t in terms) else 5)
        # Dynamic mediator names are just a literal prefix, so they match too eagerly.
        best += 2 if rec.get("dynamic") else 0
    return best


def search_records(records, query, limit):
    terms = [normalize(t) for t in query.split()]
    scored = [(s, i, r) for i, r in enumerate(records) for s in [score(r, terms)] if s is not None]
    scored.sort(key=lambda x: (x[0], x[1]))
    return [r for _, _, r in scored[:limit]], len(scored)


def format_hit(rec, shard=None):
    loc = ""
    if rec.get("file"):
        loc = "  %s%s" % (rec["file"], ":%s" % rec["line"] if rec.get("line") else "")
    head = "[%s] " % shard if shard else ""
    return "%s%s  %s%s" % (head, rec.get("id", "?"), rec.get("text", ""), loc)


def collect(out_dir, shards, query, limit):
    """[(shard, hits, total)] for every shard with at least one hit."""
    found = [(shard,) + search_records(store.read_shard(out_dir, shard), query, max(1, limit)) for shard in shards]
    return [row for row in found if row[1]]


def render_text(rows, query, scope, tagged, out):
    for shard, hits, total in rows:
        out.writelines(format_hit(rec, shard if tagged else None) + "\n" for rec in hits)
        if total > len(hits):
            out.write(("[%s] ... %d more\n" % (shard, total - len(hits))) if tagged else "... %d more (use --limit)\n" % (total - len(hits)))
    if not rows:
        out.write("no hits for '%s' in %s\n" % (query, scope))


def run_lookup(out_dir, shards, query, limit):
    if not shards:
        raise MissingShard("no shards in %s; run atlas-build" % out_dir)
    return collect(out_dir, shards, query, limit)


def run_status(root, out_dir, out, as_json=False):
    idx = index.read_index(out_dir)
    if not idx:
        raise MissingShard("no index in %s; run atlas-build" % out_dir)
    stale = set(index.stale_shards(root, out_dir))
    wanted = sorted(set(SHARDS.values()) - set(idx["shards"]))
    if as_json:
        json.dump({"index": idx, "stale": sorted(stale), "not_built": wanted}, out, ensure_ascii=False)
        out.write("\n")
        return
    out.write("oro/platform %s  generated %s  lock %s\n" % (idx.get("platform_version"), idx.get("generated_at"), idx["composer_lock_sha256"][:12]))
    for name, meta in sorted(idx["shards"].items()):
        out.write("  %-12s %7d  %s%s\n" % (name, meta["count"], meta["generated_at"], "  STALE" if name in stale else ""))
    if wanted:
        out.write("  not built: %s\n" % ",".join(wanted))



EPILOG = "Exit status: 0 on hits, 1 when a query finds no hits or the index is missing."


def _common_flags(suppress):
    """Global flags, also accepted after the subcommand (SUPPRESS keeps the pre-subcommand value)."""
    p = argparse.ArgumentParser(add_help=False)
    default = argparse.SUPPRESS if suppress else None
    p.add_argument("--project", default=default, help="project root (default: walk up from cwd)")
    p.add_argument("--json", action="store_true", default=default if suppress else False, help="machine-readable JSON output")
    return p


def build_parser():
    ap = argparse.ArgumentParser(prog="atlas", description="Query the oro-atlas extension-point index",
                                 epilog=EPILOG, parents=[_common_flags(False)])
    sub = ap.add_subparsers(dest="cmd", required=True)
    late = _common_flags(True)
    for cmd in list(SHARDS) + ["search"]:
        p = sub.add_parser(cmd, aliases=[PLURALS[cmd]] if cmd in PLURALS else [], help="search the %s shard" % SHARDS.get(cmd, "all"), parents=[late], epilog=EPILOG)
        p.add_argument("query", nargs="+")
        p.add_argument("--limit", type=int, default=5)
    sub.add_parser("status", help="show shard counts and staleness", parents=[late])
    return ap


def _query(root, out_dir, args, out):
    query = " ".join(args.query)
    shards = store.list_shards(out_dir) if args.cmd == "search" else [SHARDS[args.cmd]]
    rows = run_lookup(out_dir, shards, query, args.limit)
    if args.json:
        json.dump({"query": query, "results": [{"shard": s, "total": t, "hits": h} for s, h, t in rows]}, out, ensure_ascii=False)
        out.write("\n")
    else:
        render_text(rows, query, "all shards" if args.cmd == "search" else shards[0], args.cmd == "search", out)
    return shards, (0 if rows else 1)


def main(argv=None, out=None):
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    args.cmd = CANONICAL.get(args.cmd, args.cmd)
    code = 0
    try:
        root = find_project_root(args.project)
        out_dir = root + "/var/atlas"
        if args.cmd == "status":
            run_status(root, out_dir, out, args.json)
            used = None
        else:
            used, code = _query(root, out_dir, args, out)
        line = index.stale_line(root, out_dir, used)
        if line:
            (sys.stderr if args.json else out).write(line + "\n")
    except AtlasError as exc:
        sys.stderr.write("atlas: %s\n" % exc)
        code = 1
    return code
