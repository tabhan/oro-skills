"""Datagrid definitions (datagrids.yml) and the event listeners bound to them."""
import os
import re

from ..common import read_text
from ..miniyaml import LDict, parse

NAME = "grids"
ORDER = 50

ROOTS = ("vendor/oro", "vendor/oroinc", "vendor/aaxisdigital", "src")
SKIP_DIRS = {"node_modules", "Tests", ".git", "public"}
CONFIG_TAIL = os.path.join("Resources", "config", "oro", "datagrids.yml")
# Storefront grids live in theme layout config, not in the bundle's oro/ config.
LAYOUT_RE = re.compile(r"[/\\]Resources[/\\]views[/\\]layouts[/\\][^/\\]+[/\\]config$")
_PROXY_RE = re.compile(r"^Container\w+\\(\w+?)Proxy[0-9A-Za-z]{7}$")
EVENT_PREFIX = "oro_datagrid."
GLOBAL_EVENT_PARTS = 4  # oro_datagrid.<area>.<phase>.<when>



def _str(value):
    return value if isinstance(value, str) and value else None


def _first_table(node):
    """First `table:` under the source (the query's FROM root), depth-first in file order."""
    items = node.values() if isinstance(node, dict) else node if isinstance(node, list) else ()
    own = _str(node.get("table")) if isinstance(node, dict) else None
    return own or next((t for t in map(_first_table, items) if t), None)


def _info(body):
    body = body if isinstance(body, dict) else {}
    src = body.get("source") if isinstance(body.get("source"), dict) else {}
    return {
        "extends": _str(body.get("extends")),
        "entity": _str(body.get("extended_entity_name")) or _str(body.get("entity_name")) or _first_table(src),
        "source_type": _str(src.get("type")),
        "acl_resource": _str(src.get("acl_resource")),
    }


def parse_datagrids(text):
    """Return [(name, line, info)] for the top-level `datagrids:` map."""
    tree = parse(text)
    grids = tree.get("datagrids") if isinstance(tree, dict) else None
    grids = grids if isinstance(grids, LDict) else LDict()
    return [(str(name), grids.lines[name], _info(body)) for name, body in grids.items()]


def find_files(root):
    seen = {}
    for base in ROOTS:
        top = os.path.join(root, base)
        for dirpath, dirs, files in os.walk(top):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            if "datagrids.yml" in files and (dirpath.endswith(os.path.dirname(CONFIG_TAIL)) or LAYOUT_RE.search(dirpath)):
                p = os.path.join(dirpath, "datagrids.yml")
                seen.setdefault(os.path.realpath(p), p)
    # vendor first, project src last: later definitions override earlier ones in Oro's merge
    # theme layout files after bundle config so backend definitions stay primary
    return sorted(seen.values(), key=lambda p: (bool(LAYOUT_RE.search(os.path.dirname(p))),
                                                not os.path.relpath(p, root).startswith("vendor"), p))


def _split_grid_event(event, grid_names):
    """'oro_datagrid.datagrid.build.after.<grid>' -> (base event, grid) or (event, None)."""
    parts = event.split(".")
    found = (event, None)
    for i in range(1, len(parts)):
        if ".".join(parts[i:]) in grid_names:
            found = (".".join(parts[:i]), ".".join(parts[i:]))
            break
    if found[1] is None and len(parts) > GLOBAL_EVENT_PARTS:
        # Grid defined outside datagrids.yml (e.g. dynamic): still grid-scoped.
        found = (".".join(parts[:GLOBAL_EVENT_PARTS]), ".".join(parts[GLOBAL_EVENT_PARTS:]))
    return found


def proxy_resolver(definitions):
    """Map lazy-proxy class names (Container<hash>\\<Short>Proxy<hash>) back to the real class."""
    by_short = {}
    for d in definitions.values():
        cls = d.get("class") if isinstance(d, dict) else None
        if cls:
            by_short.setdefault(cls.rsplit("\\", 1)[-1], set()).add(cls)

    def resolve(cls):
        m = _PROXY_RE.match(cls or "")
        found = by_short.get(m.group(1), ()) if m else ()
        return next(iter(found)) if len(found) == 1 else cls
    return resolve


def collect_listeners(events, grid_names, resolve=lambda c: c):
    out = []
    for event, listeners in events.items():
        if not event.startswith(EVENT_PREFIX) or not isinstance(listeners, list):
            continue
        base, grid = _split_grid_event(event, grid_names)
        for lis in listeners:
            out.append({"event": event, "base_event": base, "grid": grid,
                        "class": resolve(lis.get("class")), "method": lis.get("name"),
                        "priority": lis.get("priority")})
    return out


def _merge_definitions(defs):
    primary = next((d for d in defs if d["info"]["source_type"] or d["info"]["extends"]), defs[0])
    merged = dict(primary["info"])
    for d in defs:
        for k, v in d["info"].items():
            if merged.get(k) is None and v is not None:
                merged[k] = v
    return primary, merged


def _loc(ctx, cls):
    return ctx.locator.locate(cls) if cls else (None, None)


def extract(ctx):
    by_name = {}
    for path in find_files(ctx.root):
        for name, line, info in parse_datagrids(read_text(path)):
            by_name.setdefault(name, []).append({"file": ctx.rel(path), "line": line, "info": info})
    resolve = proxy_resolver(ctx.container().get("definitions", {}))
    listeners = collect_listeners(ctx.events(), set(by_name), resolve)
    per_grid = {}
    for l in listeners:
        if l["grid"]:
            per_grid.setdefault(l["grid"], []).append(l)
    children = {}
    for name, defs in by_name.items():
        parent = _merge_definitions(defs)[1]["extends"]
        if parent:
            children.setdefault(parent, []).append(name)
    merged = {n: _merge_definitions(d) for n, d in by_name.items()}
    for name in sorted(by_name):
        primary, info = merged[name]
        rec = _grid_record(name, by_name[name], primary, info, per_grid.get(name, []), children.get(name, []))
        _inherit(rec, name, {n: m[1] for n, m in merged.items()})
        yield rec
    seen = {}
    for l in listeners:
        rec = _listener_record(ctx, l)
        # Same listener can be tagged twice on one event; keep ids unique.
        seen[rec["id"]] = seen.get(rec["id"], 0) + 1
        if seen[rec["id"]] > 1:
            rec["id"] += " #%d" % seen[rec["id"]]
        yield rec


def _inherit(rec, name, infos):
    """Children rarely repeat entity/source; walk `extends` so entity lookups find them."""
    cur, seen = infos[name]["extends"], {name}
    while cur and cur in infos and cur not in seen and not (rec["entity"] and rec["source_type"]):
        seen.add(cur)
        rec["entity"] = rec["entity"] or infos[cur]["entity"]
        rec["source_type"] = rec["source_type"] or infos[cur]["source_type"]
        cur = infos[cur]["extends"]
    rec["keys"] = [k for k in [rec["entity"]] if k]
    if rec["entity"] and "entity=" not in rec["text"]:
        rec["text"] += " entity=%s" % rec["entity"]


def _grid_record(name, defs, primary, info, lis, kids):
    lis_ids = ["%s::%s" % (l["class"], l["method"]) for l in sorted(lis, key=lambda x: x["event"])]
    rec = {
        "id": name,
        "kind": "grid",
        "extends": info["extends"],
        "extended_by": sorted(kids),
        "entity": info["entity"],
        "source_type": info["source_type"],
        "acl_resource": info["acl_resource"],
        "file": primary["file"],
        "line": primary["line"],
        "also_defined": ["%s:%d" % (d["file"], d["line"]) for d in defs if d is not primary],
        "listeners": ["%s %s" % (l["base_event"], i) for l, i in zip(sorted(lis, key=lambda x: x["event"]), lis_ids)],
    }
    rec["keys"] = [k for k in [info["entity"]] if k]
    bits = ["grid"]
    if info["extends"]:
        bits.append("extends=%s" % info["extends"])
    if info["source_type"]:
        bits.append("source=%s" % info["source_type"])
    if info["entity"]:
        bits.append("entity=%s" % info["entity"])
    if kids:
        bits.append("extended_by=%d" % len(kids))
    if lis:
        bits.append("listeners=%d" % len(lis))
    if defs[1:]:
        bits.append("defs=%d" % len(defs))
    rec["text"] = " ".join(bits)
    return rec


def _listener_record(ctx, l):
    rel, line = _loc(ctx, l["class"])
    scope = "grid=%s" % l["grid"] if l["grid"] else "all grids"
    return {
        "id": "%s %s::%s" % (l["event"], l["class"], l["method"]),
        "kind": "listener",
        "event": l["event"],
        "base_event": l["base_event"],
        "grid": l["grid"],
        "class": l["class"],
        "method": l["method"],
        "priority": l["priority"],
        "keys": [k for k in [l["class"], l["grid"]] if k],
        "text": "listener %s (%s) prio=%s" % (l["base_event"], scope, l["priority"]),
        "file": rel,
        "line": line,
    }
