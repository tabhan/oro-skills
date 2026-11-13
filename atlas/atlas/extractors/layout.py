"""Layout block types (+extensions), data providers, themes with parents, layout update files."""
import os
import re

from ..common import read_text
from ..miniyaml import parse

NAME = "layouts"
ORDER = 50

SOURCE_ROOTS = ("src", "vendor/oro", "vendor/oroinc", "vendor/aaxisdigital")
# Skipped so the walk stays fast and fixtures never pose as real themes.
PRUNE = {"Tests", "node_modules", ".git", "public", "translations", "docs", "Resources_public"}
LAYOUTS_SUFFIX = os.path.join("Resources", "views", "layouts")
SPECIAL_DIRS = {"config", "imports", "page", "optimized", "email-templates"}

_INLINE_ID_RE = re.compile(r"^['\"]?([\w\-.:]+)['\"]?\s*$")
_PARENT_RE = re.compile(r"function\s+getParent\s*\(\s*\)\s*(?::\s*\??\w+)?\s*\{\s*return\s+([\w\\]+)::(\w+)")
_USE_RE = re.compile(r"^use\s+([\w\\]+)(?:\s+as\s+(\w+))?;", re.M)
_NS_RE = re.compile(r"^namespace\s+([\w\\]+);", re.M)
_OPT_CALL_RE = re.compile(r"setDefined\(\s*(\[[^\]]*\]|'[^']*')|setRequired\(\s*(\[[^\]]*\]|'[^']*')|setDefault\(\s*'(\w+)'")
_DEFAULTS_RE = re.compile(r"setDefaults\(\s*\[(.*?)\]\s*\)\s*;", re.S)
_QUOTED_RE = re.compile(r"'(\w+)'")
_KEY_RE = re.compile(r"^\s*'(\w+)'\s*=>", re.M)


def _bundle_of(layouts_dir):
    """Bundle dir name without its Resources/views/layouts tail, e.g. FrontendBundle."""
    base = os.path.dirname(os.path.dirname(os.path.dirname(layouts_dir)))
    return os.path.basename(base), base


def find_dirs(root, suffix):
    """Every dir ending in `suffix` outside tests/fixtures under the source roots."""
    found = []
    for top in SOURCE_ROOTS:
        start = os.path.join(root, top)
        for dirpath, dirnames, _files in os.walk(start):
            if dirpath.endswith(suffix):
                found.append(dirpath)
                dirnames[:] = []
            else:
                dirnames[:] = [d for d in dirnames if d not in PRUNE]
    return sorted(found)


def find_layout_dirs(root):
    return find_dirs(root, LAYOUTS_SUFFIX)


_SVC_RE = re.compile(r"^    ([\w.\\-]+):\s*$")
_PARENT_SVC_RE = re.compile(r"^\s+parent:\s*['\"]?([\w.\\-]+)")
_SETPARENT_RE = re.compile(r"setParent['\"]?\s*,\s*\[\s*['\"]([\w-]+)")
_CFG_OPT_RE = re.compile(r"(?<![\w'\"])(\w+):\s*(?:\{|~)")
_OPT_RESERVED = {"default", "required", "allowed_types", "allowed_values", "normalizer", "deprecated"}


def _service_chunks(path):
    """{service id: (line, chunk text)} for a services yml; chunks split on 4-space keys."""
    out, cur, start, buf = {}, None, 0, []
    for n, line in enumerate(read_text(path).splitlines(), 1):
        m = _SVC_RE.match(line)
        if m:
            if cur:
                out[cur] = (start, "\n".join(buf))
            cur, start, buf = m.group(1), n, []
        elif cur:
            buf.append(line)
    if cur:
        out[cur] = (start, "\n".join(buf))
    return out


def configurable_index(root):
    """Service id -> {file,line,chunk} for services declared in bundle config yml files."""
    index = {}
    for cdir in find_dirs(root, os.path.join("Resources", "config")):
        for fname in sorted(os.listdir(cdir)):
            full = os.path.join(cdir, fname)
            if fname.endswith(".yml") and "layout.block_type" in read_text(full) + "":
                for sid, (line, chunk) in _service_chunks(full).items():
                    index.setdefault(sid, {"file": os.path.relpath(full, root), "line": line, "chunk": chunk})
    return index


def _cfg_parent_alias(index, sid, depth=0):
    """setParent value from the service or the nearest abstract parent service."""
    entry = index.get(sid)
    found = None
    if entry and depth < 6:
        m = _SETPARENT_RE.search(entry["chunk"])
        pm = _PARENT_SVC_RE.search(entry["chunk"])
        found = m.group(1) if m else (_cfg_parent_alias(index, pm.group(1), depth + 1) if pm else None)
    return found


def _cfg_options(entry):
    chunk = entry["chunk"] if entry else ""
    head = chunk.split("setName")[0]
    names = _CFG_OPT_RE.findall(head.split("setOptionsConfig", 1)[1]) if "setOptionsConfig" in head else []
    return sorted(set(names) - _OPT_RESERVED)


def parse_theme_yml(text):
    """Top-level scalar keys of a theme.yml (label, parent, ...)."""
    tree = parse(text)
    items = tree.items() if isinstance(tree, dict) else ()
    return {str(k): str(v) for k, v in items if v is not None and not isinstance(v, (dict, list, bool))}


def _action_ids(value):
    """Block ids an action touches: `id:` of its options, or the bare/first positional argument."""
    first = value[0] if isinstance(value, list) and value else value
    found = value.get("id") if isinstance(value, dict) else first
    return [found] if isinstance(found, str) and _INLINE_ID_RE.match(found) else []


def parse_layout_yml(text):
    """Action counts and block ids per action from a layout update."""
    tree = parse(text)
    body = tree.get("layout") if isinstance(tree, dict) else None
    body = body if isinstance(body, dict) else {}
    actions = body.get("actions") if isinstance(body.get("actions"), list) else []
    pairs = [(str(k).lstrip("@"), v) for item in actions if isinstance(item, dict) for k, v in item.items()
             if str(k).startswith("@")]
    counts, ids = {}, {}
    for act, value in pairs:
        counts[act] = counts.get(act, 0) + 1
        ids.setdefault(act, []).extend(_action_ids(value))
    cond = body.get("conditions")
    return {"actions": counts, "ids": {k: sorted(set(v)) for k, v in ids.items() if v},
            "conditions": cond if isinstance(cond, str) else None}


def _update_text(info):
    parts = ["%s×%d" % (k, v) for k, v in sorted(info["actions"].items())]
    for act in ("add", "remove", "move", "setOption"):
        if info["ids"].get(act):
            parts.append("%s:%s" % (act, ",".join(info["ids"][act][:6])))
    return " ".join(parts)


def _classify(rel_in_theme):
    parts = rel_in_theme.split(os.sep)
    name = parts[-1]
    kind = "layout_update"
    if parts[0] == "config":
        kind = "theme_config"
    elif name.endswith(".twig"):
        kind = "block_theme"
    elif name == "theme.yml" and len(parts) == 1:
        kind = "theme_yml"
    elif not name.endswith((".yml", ".php")):
        kind = "other"
    return kind


def _scope(rel_in_theme):
    parts = rel_in_theme.split(os.sep)[:-1]
    return "/".join(parts)


def _route(scope):
    first = scope.split("/")[0] if scope else ""
    return first if first and first not in SPECIAL_DIRS else ""


def scan_layouts(root, layout_dirs):
    """Walk every layouts dir; return {theme: {'files': [...]}} with parsed theme.yml/updates."""
    themes = {}
    for ldir in layout_dirs:
        bundle, bpath = _bundle_of(ldir)
        project = os.path.relpath(bpath, root).startswith("src")
        for theme in sorted(os.listdir(ldir)):
            tdir = os.path.join(ldir, theme)
            if not os.path.isdir(tdir):
                continue
            entry = themes.setdefault(theme, {"files": [], "theme_ymls": []})
            for dirpath, _dn, files in os.walk(tdir):
                for fname in sorted(files):
                    full = os.path.join(dirpath, fname)
                    rel = os.path.relpath(full, tdir)
                    entry["files"].append({
                        "path": os.path.relpath(full, root), "rel": rel, "bundle": bundle,
                        "project": project, "kind": _classify(rel),
                    })
    return themes


def _theme_records(themes, root):
    ymls = {}
    for name, entry in themes.items():
        ymls[name] = [f for f in entry["files"] if f["kind"] == "theme_yml"]
    parsed = {n: [(f, parse_theme_yml(read_text(os.path.join(root, f["path"])))) for f in fs] for n, fs in ymls.items()}
    parents = {}
    for name, items in parsed.items():
        parents[name] = next((d["parent"] for _f, d in items if d.get("parent")), None)
    return parsed, parents


def _chain(name, parents):
    chain, seen, cur = [], {name}, parents.get(name)
    while cur and cur not in seen:
        chain.append(cur)
        seen.add(cur)
        cur = parents.get(cur)
    return chain


def _theme_label(items):
    return next((d["label"] for _f, d in items if d.get("label")), "")


def _theme_rec(name, entry, parsed, parents):
    items = parsed.get(name, [])
    children = sorted(c for c, p in parents.items() if p == name)
    kinds = {}
    for f in entry["files"]:
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    chain = _chain(name, parents)
    # Many bundles contribute a theme.yml; the one declaring label/parent is the canonical definition.
    first = next((f for f, d in items if d.get("label") or d.get("parent")), items[0][0] if items else None)
    fixture = any("TestFrameworkBundle" in f["bundle"] for f in entry["files"]) and not any(
        f["project"] or "TestFramework" not in f["bundle"] for f in entry["files"])
    text = " ".join(filter(None, [
        "theme", "parent=%s" % parents[name] if parents.get(name) else "root",
        "chain=%s" % ">".join([name] + chain) if chain else "",
        "children=%s" % ",".join(children) if children else "",
        "label='%s'" % _theme_label(items) if _theme_label(items) else "",
        "files=%d" % len(entry["files"]),
        "fixture-only" if fixture else "",
    ]))
    return {
        "id": "theme:%s" % name, "kind": "theme", "keys": [name], "text": text, "theme": name,
        "parent": parents.get(name), "chain": chain, "children": children,
        "label": _theme_label(items), "has_theme_yml": bool(items), "fixture_only": fixture,
        "theme_yml_files": [f["path"] for f, _d in items],
        "bundles": sorted({f["bundle"] for f in entry["files"]}),
        "file_kinds": kinds, "file": first["path"] if first else None, "line": 1 if first else None,
    }


def _update_rec(theme, f, chain, root):
    scope = _scope(f["rel"])
    rec = {
        "id": "%s/%s@%s" % (theme, f["rel"], f["bundle"]), "kind": f["kind"], "theme": theme,
        "theme_chain": chain, "scope": scope, "route": _route(scope), "bundle": f["bundle"],
        "project": f["project"], "file": f["path"], "line": 1, "keys": [],
    }
    info = None
    if f["kind"] == "layout_update" and f["path"].endswith(".yml"):
        info = parse_layout_yml(read_text(os.path.join(root, f["path"])))
        rec.update(actions=info["actions"], block_ids=info["ids"], conditions=info["conditions"])
    base = "%s %s theme=%s bundle=%s" % (f["kind"], "route=%s" % rec["route"] if rec["route"] else "scope=%s" % (scope or "/"),
                                          theme, f["bundle"])
    rec["text"] = (base + " " + _update_text(info)).strip() if info else base
    if rec["route"]:
        rec["keys"].append(rec["route"])
    return rec


def _short_classes(php):
    ns = _NS_RE.search(php)
    uses = {(m.group(2) or m.group(1).rsplit("\\", 1)[-1]): m.group(1) for m in _USE_RE.finditer(php)}
    return (ns.group(1) if ns else ""), uses


def _own_options(php):
    names = set()
    for m in _OPT_CALL_RE.finditer(php):
        for grp in m.groups():
            names.update(_QUOTED_RE.findall(grp or ""))
    for m in _DEFAULTS_RE.finditer(php):
        names.update(_KEY_RE.findall(m.group(1)))
    return sorted(names)


def _parent_class(php):
    m = _PARENT_RE.search(php)
    fq = None
    if m:
        ns, uses = _short_classes(php)
        short = m.group(1)
        fq = short.lstrip("\\") if "\\" in short else uses.get(short) or (ns + "\\" + short if ns else short)
    return fq


def _tagged(defs, tag):
    for sid in sorted(defs):
        for t in defs[sid].get("tags", []):
            if t["name"] == tag:
                yield sid, defs[sid], t.get("parameters", {})


def _block_records(ctx):
    cfg = configurable_index(ctx.root)
    defs = ctx.container()["definitions"]
    types = list(_tagged(defs, "layout.block_type"))
    class_alias = {}
    for sid, d, p in types:
        class_alias.setdefault(d.get("class"), p.get("alias"))
    exts = {}
    for sid, d, p in _tagged(defs, "layout.block_type_extension"):
        cls = d.get("class") or ""
        rel, line = ctx.locator.locate(cls)
        opts = _own_options(read_text(ctx.locator.file_of(cls) or ""))
        exts.setdefault(p.get("alias"), []).append(
            {"service": sid, "class": cls, "file": rel, "line": line, "options": opts})
    for sid, d, p in types:
        yield _block_rec(ctx, sid, d, p, class_alias, exts, cfg)


def _block_rec(ctx, sid, d, p, class_alias, exts, cfg):
    alias, cls = p.get("alias"), d.get("class") or ""
    rel, line = ctx.locator.locate(cls)
    php = read_text(ctx.locator.file_of(cls) or "")
    pcls = _parent_class(php)
    pal = class_alias.get(pcls)
    configurable = cls.endswith("ConfigurableType")
    entry = cfg.get(sid) if configurable else None
    if entry:
        pal, rel, line = _cfg_parent_alias(cfg, sid), entry["file"], entry["line"]
    myext = exts.get(alias, [])
    text = " ".join(filter(None, [
        "block_type", "class=%s" % cls, "parent=%s" % pal if pal else "",
        "configurable" if configurable else "",
        "extensions=%d" % len(myext) if myext else "",
    ]))
    return {
        "id": "block:%s" % alias, "kind": "block_type", "alias": alias, "service": sid, "class": cls,
        "parent_alias": pal, "parent_class": pcls, "configurable": configurable,
        "own_options": _cfg_options(entry) if configurable else _own_options(php), "extensions": myext,
        "keys": [k for k in [alias, cls, sid] if k], "text": text, "file": rel, "line": line,
    }


def _provider_records(ctx):
    defs = ctx.container()["definitions"]
    for sid, d, p in _tagged(defs, "layout.data_provider"):
        cls = d.get("class") or ""
        rel, line = ctx.locator.locate(cls)
        alias = p.get("alias") or sid
        yield {
            "id": "data:%s" % alias, "kind": "data_provider", "alias": alias, "service": sid, "class": cls,
            "method": p.get("method"), "keys": [k for k in [alias, cls, sid] if k],
            "text": "data_provider usage=data['%s'] class=%s" % (alias, cls), "file": rel, "line": line,
        }


def _all_theme_records(ctx):
    root = ctx.root
    themes = scan_layouts(root, find_layout_dirs(root))
    parsed, parents = _theme_records(themes, root)
    seen = set()
    for name in sorted(themes):
        yield _theme_rec(name, themes[name], parsed, parents)
        chain = _chain(name, parents)
        for f in themes[name]["files"]:
            if f["kind"] != "theme_yml":
                rec = _update_rec(name, f, chain, root)
                # Same theme/file/bundle name can exist in src/ and vendor/; ids must stay unique.
                if rec["id"] in seen:
                    rec["id"] += "#" + "/".join(f["path"].split("/")[:3])
                seen.add(rec["id"])
                yield rec


def extract(ctx):
    yield from _block_records(ctx)
    yield from _provider_records(ctx)
    yield from _all_theme_records(ctx)
