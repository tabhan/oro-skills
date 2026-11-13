"""System configuration fields: type, tree placement, scope hints, defining file:line."""
import os

from ..miniyaml import LDict, LList, parse_file

NAME = "config"

SCAN_DIRS = ["src", "vendor/oro", "vendor/oroinc", "vendor/aaxisdigital"]
SKIP_DIRS = {"node_modules", "Tests", ".git"}
FILE_SUFFIX = os.path.join("Resources", "config", "oro", "system_configuration.yml")

# Tree roots are the scopes in which a field is editable.
SCOPE_NAMES = {
    "system_configuration": "global",
    "organization_configuration": "organization",
    "website_configuration": "website",
    "user_configuration": "user",
    "customer_configuration": "customer",
    "customer_group_configuration": "customer_group",
}


def find_files(root):
    seen, found = set(), []
    for base in SCAN_DIRS:
        for cur, dirs, files in os.walk(os.path.join(root, base)):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            path = os.path.join(cur, "system_configuration.yml")
            if "system_configuration.yml" in files and path.endswith(FILE_SUFFIX):
                real = os.path.realpath(path)
                if real not in seen:
                    seen.add(real)
                    found.append(path)
    return sorted(found)


def _children(node):
    """Yield (name, child_node, line) for a `children` value given as map or list."""
    items = []
    if isinstance(node, LDict):
        items = [(k, v, node.lines.get(k)) for k, v in node.items()]
    elif isinstance(node, LList):
        items = [(k, None, ln) for k, ln in zip(node, node.lines) if isinstance(k, str)]
    return items


def _walk(node, scope, path, out, rel):
    """Collect (name -> placements); `node` is a tree entry dict holding optional `children`."""
    if isinstance(node, LDict):
        for name, child, line in _children(node.get("children")):
            out.setdefault(name, []).append(
                {"scope": scope, "path": list(path), "file": rel, "line": line}
            )
            _walk(child, scope, path + [name], out, rel)


def _walk_roots(tree, rel, out):
    for scope_key, top in (tree or {}).items():
        if isinstance(top, LDict):
            for name, child in top.items():
                _walk(child, SCOPE_NAMES.get(scope_key, scope_key), [name], out, rel)


def _load(path, rel):
    doc = parse_file(path)
    section = doc.get("system_configuration") if isinstance(doc, LDict) else None
    fields, groups, placements, api = {}, {}, {}, {}
    if isinstance(section, LDict):
        for name, spec in (section.get("fields") or {}).items():
            fields[name] = (spec if isinstance(spec, LDict) else {}, section["fields"].lines[name])
        for name, spec in (section.get("groups") or {}).items():
            groups[name] = spec if isinstance(spec, LDict) else {}
        _walk_roots(section.get("tree"), rel, placements)
        for sect, names in (section.get("api_tree") or {}).items():
            for n in names if isinstance(names, LDict) else []:
                api[n] = sect
    return fields, groups, placements, api


def _text(rec):
    parts = [rec["data_type"] or "?"]
    if rec["form_type"]:
        parts.append(rec["form_type"].rsplit("\\", 1)[-1])
    if rec["scopes"]:
        parts.append("scopes=" + ",".join(rec["scopes"]))
    else:
        parts.append("unplaced")
    if rec["tree_path"]:
        parts.append("tree=" + rec["tree_path"])
    if rec["ui_only"]:
        parts.append("ui_only")
    if len(rec["defined_in"]) > 1:
        parts.append("defined_x%d" % len(rec["defined_in"]))
    return " ".join(parts)


def _record(name, defs, groups, placements, api):
    _, rel, line = defs[0]
    # Overriding definitions often repeat only a few keys; fill gaps from the others.
    spec = {}
    for d, _, _ in reversed(defs):
        spec.update(d)
    opts = spec.get("options") if isinstance(spec.get("options"), LDict) else {}
    places = placements.get(name, [])
    primary = places[0] if places else None
    group_titles = {
        g: groups[g].get("title") for p in places for g in p["path"] if g in groups and groups[g].get("title")
    }
    rec = {
        "id": name,
        "keys": [name.split(".", 1)[-1], name.replace(".", "__")],
        "data_type": spec.get("data_type"),
        "form_type": spec.get("type"),
        "priority": spec.get("priority"),
        "label": opts.get("label"),
        "tooltip": opts.get("tooltip"),
        "ui_only": bool(spec.get("ui_only")),
        "page_reload": bool(spec.get("page_reload")),
        "scopes": sorted({p["scope"] for p in places}),
        "tree_path": " > ".join(primary["path"]) if primary else "",
        "placements": [
            {"scope": p["scope"], "path": p["path"], "file": p["file"], "line": p["line"]} for p in places
        ],
        "group_titles": group_titles,
        "api_section": api.get(name),
        "defined_in": ["%s:%s" % (r, ln) for _, r, ln in defs],
        "file": rel,
        "line": line,
    }
    rec["text"] = _text(rec)
    return rec


def extract(ctx):
    defs, groups, placements, api = {}, {}, {}, {}
    for path in find_files(ctx.root):
        rel = ctx.rel(path)
        f, g, p, a = _load(path, rel)
        for name, (spec, line) in f.items():
            defs.setdefault(name, []).append((spec, rel, line))
        for name, spec in g.items():
            groups.setdefault(name, spec)
        for name, items in p.items():
            placements.setdefault(name, []).extend(items)
        api.update(a)
    for name in sorted(defs):
        yield _record(name, defs[name], groups, placements, api)
