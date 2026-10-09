"""atlas query CLI: compact one-line-per-hit lookups over the JSONL shards."""
import argparse
import json
import re
import sys

import io
import os
import subprocess

from . import build, extractors, index, rollup, store
from .common import AtlasError, Context, MissingShard, atlas_dir, find_project_root

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


SRC_EXTRA_MAX = 20


def _is_project(rec):
    return str(rec.get("file") or "").startswith("src/")


def search_records(records, query, limit):
    """Best matches first, project (src/) before vendor on ties; every src hit survives truncation (capped)."""
    terms = [normalize(t) for t in query.split()]
    scored = [(s, not _is_project(r), i, r) for i, r in enumerate(records) for s in [score(r, terms)] if s is not None]
    scored.sort(key=lambda x: x[:3])
    ranked = [r for _, _, _, r in scored]
    shown = ranked[:limit]
    extra = [r for r in ranked[limit:] if _is_project(r)][:SRC_EXTRA_MAX]
    return shown + extra, len(ranked)


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


def render_text(rows, query, scope, tagged, out, rollups=None):
    for shard, hits, total in rows:
        for rec in hits:
            out.write(format_hit(rec, shard if tagged else None) + "\n")
            if rollups and rec["id"] in rollups:
                rollup.render(rollups[rec["id"]], out)
        if total > len(hits):
            out.write(("[%s] ... %d more\n" % (shard, total - len(hits))) if tagged else "... %d more (use --limit)\n" % (total - len(hits)))
    if not rows:
        out.write("no hits for '%s' in %s\n" % (query, scope))


def run_lookup(out_dir, shards, query, limit):
    if not shards:
        raise MissingShard("no shards in %s; run atlas-build" % out_dir)
    return collect(out_dir, shards, query, limit)


def _state_text(st):
    return {"fresh": "fresh", "missing": "MISSING"}.get(st["state"], "STALE (%s changed)" % " and ".join(st["reasons"]))


def run_status(root, out_dir, out, as_json=False, quiet=False):
    """Print per-shard freshness; returns 0 when every shard is fresh, 2 when any is STALE or MISSING."""
    idx = index.read_index(out_dir) or {"shards": {}}
    status = index.shard_status(root, out_dir, sorted(set(SHARDS.values()) | set(idx["shards"])))
    bad = {n: st for n, st in status.items() if st["state"] != "fresh"}
    if as_json:
        json.dump({"index": idx, "shards": status, "stale": sorted(n for n, s in bad.items() if s["state"] == "stale"),
                   "not_built": sorted(n for n, s in bad.items() if s["state"] == "missing")}, out, ensure_ascii=False)
        out.write("\n")
    elif not quiet:
        out.write("oro/platform %s  generated %s  lock %s\n" % (
            idx.get("platform_version"), idx.get("generated_at"), (idx.get("composer_lock_sha256") or "-")[:12]))
        for name, st in status.items():
            meta = idx["shards"].get(name, {})
            out.write("  %-12s %7s  %s  %s\n" % (name, meta.get("count", "-"), meta.get("generated_at", "-"), _state_text(st)))
        if bad:
            out.write("run: atlas-build --incremental\n")
    return 2 if bad else 0


EPILOG = ("`atlas build [args]` runs atlas-build. Exit status: 0 on hits, 1 when a query finds no hits or the index is missing; "
          "`status` exits 0 when every shard is fresh and 2 when any is STALE or MISSING.")


def _common_flags(suppress):
    """Global flags, also accepted after the subcommand (SUPPRESS keeps the pre-subcommand value)."""
    p = argparse.ArgumentParser(add_help=False)
    default = argparse.SUPPRESS if suppress else None
    p.add_argument("--project", default=default, help="project root (default: walk up from cwd)")
    p.add_argument("--json", action="store_true", default=default if suppress else False, help="machine-readable JSON output")
    p.add_argument("--no-rebuild", action="store_true", default=default if suppress else False,
                   help="never auto-rebuild a shard stale for src reasons (also: ATLAS_NO_AUTOBUILD=1)")
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
    st = sub.add_parser("status", help="show per-shard freshness (exit 2 when any shard is STALE/MISSING)", parents=[late])
    st.add_argument("--quiet", action="store_true", help="no output, exit status only")
    return ap


ROLLUP_MAX = 3
AUTO_BUDGET_SECONDS = 5.0


def _entity_rollups(out_dir, rows, query):
    """{record id: sections} for the best-matching entity hits: the top hit and any exact key match."""
    terms = [normalize(t) for t in query.split()]
    found = {}
    for shard, hits, _ in rows:
        for pos, rec in enumerate(hits):
            if shard == "entities" and rec.get("kind") in rollup.ENTITY_KINDS and len(found) < ROLLUP_MAX and (pos == 0 or score(rec, terms) == 0):
                found[rec["id"]] = rollup.build(out_dir, rec)
    return found


def _unsafe_hint(out_dir, query):
    """Explain an empty `unsafe` answer: unknown class vs known class nobody typehints."""
    q = normalize(query)
    hits = []
    for shard in ("services", "entities"):
        try:
            hits += [r for r in store.read_shard(out_dir, shard) if q in _flatten([r.get("id", "")] + list(r.get("keys", [])))]
        except MissingShard:
            pass
    try:
        entities = list(store.read_shard(out_dir, "entities"))
    except MissingShard:
        entities = []
    over = next((r["repository_override"] for r in entities if r.get("repository_override") and normalize(r.get("repository") or "") == q), None)
    hits += [r for r in entities if normalize(r.get("repository") or "") == q]
    if over:
        msg = "'%s' is replaced via entity_extend by %s; try: atlas unsafe %s" % (query.lstrip("\\"), over, over)
    elif hits:
        msg = "'%s' is a known class/service, but no consumer typehints it: not flagged by the index" % query.lstrip("\\")
    else:
        msg = "'%s' is not a known service/entity class; check the FQCN (leading backslash is optional)" % query.lstrip("\\")
    return msg


def _query(root, out_dir, args, out):
    query = " ".join(args.query)
    shards = store.list_shards(out_dir) if args.cmd == "search" else [SHARDS[args.cmd]]
    rows = run_lookup(out_dir, shards, query, args.limit)
    if args.cmd == "unsafe" and "\\" in query:
        # A fully qualified name is exact intent; other records only echo it inside their summary text.
        rows = [(s, [h for h in hits if score(h, [normalize(query)]) == 0] or hits, t) for s, hits, t in rows]
    rollups = _entity_rollups(out_dir, rows, query) if args.cmd == "entity" else {}
    if args.json:
        results = [{"shard": s, "total": t, "hits": [dict(h, rollup=rollups[h["id"]]) if h["id"] in rollups else h for h in hits]} for s, hits, t in rows]
        json.dump({"query": query, "results": results}, out, ensure_ascii=False)
        out.write("\n")
    else:
        render_text(rows, query, "all shards" if args.cmd == "search" else shards[0], args.cmd == "search", out, rollups)
        if not rows and args.cmd == "unsafe":
            out.write(_unsafe_hint(out_dir, query) + "\n")
    return shards, (0 if rows else 1)


def spawn_background(out_dir):
    """Detached incremental rebuild; its output goes to build.log beside the shards."""
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "atlas-build")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "build.log"), "ab") as log:
        subprocess.Popen([sys.executable, script, "--project", os.path.dirname(os.path.dirname(out_dir)), "--incremental", "--background"],
                         stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)


def _heal(root, out_dir, shards, err):
    """Refresh what a query is about to read: inline when only src changed and it is cheap, else in the background."""
    warned = False
    status = index.shard_status(root, out_dir, shards)
    todo = sorted(n for n, st in status.items() if st["state"] != "fresh")
    stale = [n for n in todo if status[n]["state"] == "stale"]
    if todo:
        meta = (index.read_index(out_dir) or {}).get("shards", {})
        names = extractors.ordered(extractors.load_all(), stale) if stale else []
        cost = sum(meta.get(n, {}).get("build_seconds") or AUTO_BUDGET_SECONDS + 1 for n in names)
        if len(stale) == len(todo) and all(status[n]["reasons"] == ["src"] for n in stale) and cost <= AUTO_BUDGET_SECONDS:
            try:
                build.build(Context(root), names, out=io.StringIO())
                todo = []
            except AtlasError:
                pass  # another build holds the lock: answer from the current shards
        if todo:
            if not build.build_running(out_dir):
                spawn_background(out_dir)
            err.write("atlas: %s stale; refreshing in the background, answering from the current index\n" % ",".join(todo))
            warned = True
    return warned


def main(argv=None, out=None):
    out = out or sys.stdout
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["build"]:
        # `atlas build ...` == atlas-build, so callers never derive the build script's path from atlas's.
        return build.main(argv[1:])
    args = build_parser().parse_args(argv)
    args.cmd = CANONICAL.get(args.cmd, args.cmd)
    code = 0
    try:
        root = find_project_root(args.project)
        out_dir = atlas_dir(root)
        if args.cmd == "status":
            code = run_status(root, out_dir, out, args.json, args.quiet)
        else:
            wanted = None if args.cmd == "search" else [SHARDS[args.cmd]]
            warned = False
            if not (args.no_rebuild or os.environ.get("ATLAS_NO_AUTOBUILD")) and index.read_index(out_dir):
                warned = _heal(root, out_dir, wanted or store.list_shards(out_dir), sys.stderr)
            used, code = _query(root, out_dir, args, out)
            line = None if warned else index.stale_line(root, out_dir, used)
            if line:
                sys.stderr.write(line + "\n")
    except AtlasError as exc:
        sys.stderr.write("atlas: %s\n" % exc)
        code = 1
    return code
