"""Doctrine entities: table, repository, #[Config] scopes, entity_config.yml scopes, extend repository overrides."""
import os
import re

from ..common import read_text
from ..miniyaml import LDict, parse

NAME = "entities"

ROOTS = ("src", "vendor/oro", "vendor/oroinc", "vendor/aaxisdigital")
KIND_RE = re.compile(r"(?:#\[\s*(?:ORM\\)?|@ORM\\)(Entity|MappedSuperclass)\b")
NS_RE = re.compile(r"^namespace\s+([\w\\]+)\s*;", re.M)
CLASS_RE = re.compile(r"^(?:(?:final|abstract|readonly)\s+)*class\s+(\w+)", re.M)
USE_RE = re.compile(r"^use\s+([\w\\]+?)(?:\s+as\s+(\w+))?\s*;", re.M)
TABLE_OPEN_RE = re.compile(r"(?:#\[\s*(?:ORM\\)?Table\(|@ORM\\Table\()")
TABLE_NAME_RE = re.compile(r"(?:^\(\s*|\bname\s*[:=]\s*)['\"]([^'\"]+)['\"]")
REPO_ATTR_RE = re.compile(r"repositoryClass\s*:\s*([\w\\]+)::class")
REPO_ANN_RE = re.compile(r"repositoryClass\s*=\s*['\"]([\w\\]+)['\"]")
SCOPE_KEY_RE = re.compile(r"['\"](\w+)['\"]\s*=>")
# Test-framework bundles and stub/fixture dirs define entities that never exist in a real install.
TEST_PATH_RE = re.compile(r"[/\\](?:\w*TestFramework\w*Bundle|Stubs?|Fixtures?|Tests?)[/\\]")


def _balanced(text, start, open_ch, close_ch):
    """Substring from text[start]==open_ch to its match, skipping quoted strings."""
    depth, i, quote = 0, start, None
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    return text[start:]


def _top_level_keys(body):
    """Top-level `'key' =>` names of a PHP array literal (depth 1 only)."""
    keys, depth, i, quote = [], 0, 0, None
    while i < len(body):
        ch = body[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"":
            m = SCOPE_KEY_RE.match(body, i) if depth == 1 else None
            if m:
                keys.append(m.group(1))
                i = m.end() - 1
            else:
                quote = ch
        elif ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        i += 1
    return keys


def config_scopes(header):
    """Map scope -> list of its keys from the #[Config(defaultValues: [...])] attribute."""
    scopes = {}
    m = re.search(r"#\[\s*Config\(", header)
    dv = re.search(r"defaultValues\s*:\s*\[", header[m.end():]) if m else None
    if dv:
        arr = _balanced(header, m.end() + dv.end() - 1, "[", "]")
        for scope in _top_level_keys(arr):
            sm = re.search(r"['\"]%s['\"]\s*=>\s*\[" % scope, arr)
            inner = _balanced(arr, sm.end() - 1, "[", "]") if sm else ""
            scopes[scope] = _top_level_keys(inner)
    return scopes


def table_name(header):
    """Table name from #[ORM\\Table('x')], #[ORM\\Table(name: 'x', ...)] or @ORM\\Table(name="x")."""
    m = TABLE_OPEN_RE.search(header)
    args = _balanced(header, m.end() - 1, "(", ")") if m else ""
    # Nested Index(name: ...) args must not win over the table's own name.
    flat, n = args[1:-1], 1
    while n:
        flat, n = re.subn(r"[(\[][^()\[\]]*[)\]]", "", flat)
    flat = "(" + flat
    nm = TABLE_NAME_RE.search(flat)
    return nm.group(1) if nm else None


def _resolve(name, uses, ns):
    """Resolve a class reference from attribute text to an FQCN (PHP name rules)."""
    head = name.lstrip("\\").split("\\", 1)[0]
    if name.startswith("\\"):
        full = name[1:]
    elif head in uses:
        full = uses[head] + name[len(head):]
    else:
        full = ns + "\\" + name if ns else name
    return full


def parse_php(text):
    """Return a dict describing the entity declared in `text`, or None."""
    km, cm = KIND_RE.search(text), CLASS_RE.search(text)
    if not km or not cm or km.start() > cm.start():
        return None
    nm = NS_RE.search(text)
    ns = nm.group(1) if nm else ""
    uses = {(m.group(2) or m.group(1).rsplit("\\", 1)[-1]): m.group(1) for m in USE_RE.finditer(text[:cm.start()])}
    header = text[:cm.start()]
    rm = REPO_ATTR_RE.search(header)
    ann = None if rm else REPO_ANN_RE.search(header)
    repo = _resolve(rm.group(1), uses, ns) if rm else (ann.group(1).lstrip("\\") if ann else None)
    return {
        "class": (ns + "\\" if ns else "") + cm.group(1),
        "kind": km.group(1),
        "table": table_name(header),
        "repository": repo,
        "scopes": config_scopes(header),
        "line": text.count("\n", 0, cm.start()) + 1,
    }


def _section(text, name):
    tree = parse(text)
    sec = tree.get(name) if isinstance(tree, dict) else None
    return sec if isinstance(sec, LDict) else LDict()


def parse_extend_overrides(text):
    """[(fqcn, repo_or_None, line)] per class in an aaxis entity_extend.yml."""
    sec = _section(text, "aaxis_entity_extend")
    return [(fqcn, _repo(body), sec.lines[fqcn]) for fqcn, body in sec.items() if "\\" in str(fqcn)]


def _repo(body):
    repo = body.get("customRepositoryClassName") if isinstance(body, dict) else None
    return repo if isinstance(repo, str) else None


def _items(scope_body, section):
    sec = scope_body.get(section) if isinstance(scope_body, dict) else None
    items = sec.get("items") if isinstance(sec, dict) else None
    return [str(k) for k in items] if isinstance(items, dict) else []


def parse_scope_defs(text):
    """Return {scope: {"entity": [items], "field": [items]}} from an entity_config.yml."""
    return {str(scope): {"entity": _items(body, "entity"), "field": _items(body, "field")}
            for scope, body in _section(text, "entity_config").items()}


def _walk(root, rel_root, suffix):
    skip = {"Tests", "node_modules", "public", ".git"}
    for dirpath, dirs, files in os.walk(os.path.join(root, rel_root)):
        dirs[:] = sorted(d for d in dirs if d not in skip)
        for f in sorted(files):
            if f.endswith(suffix):
                yield os.path.join(dirpath, f)


def _short(fqcn):
    return fqcn.rsplit("\\", 1)[-1]


def _text(rec):
    parts = [rec["kind"]]
    if rec["table"]:
        parts.append("table=%s" % rec["table"])
    if rec["repository"]:
        parts.append("repo=%s" % _short(rec["repository"]))
    if rec["repository_override"]:
        parts.append("repo_override=%s" % _short(rec["repository_override"]))
    if rec["scopes"]:
        parts.append("scopes=%s" % ",".join(sorted(rec["scopes"])))
    return " ".join(parts)


def _collect_entities(ctx):
    seen = {}
    for rel_root in ROOTS:
        for path in _walk(ctx.root, rel_root, ".php"):
            text = "" if TEST_PATH_RE.search(os.path.relpath(path, ctx.root)) else read_text(path)
            if "Entity" not in text and "MappedSuperclass" not in text:
                continue
            info = parse_php(text)
            if info and info["class"] not in seen:
                info["file"] = ctx.rel(path)
                seen[info["class"]] = info
    return seen


def _collect_overrides(ctx):
    overrides = {}
    for rel_root in ROOTS:
        for path in _walk(ctx.root, rel_root, "entity_extend.yml"):
            text = read_text(path)
            if "aaxis_entity_extend" in text:
                for fqcn, repo, line in parse_extend_overrides(text):
                    overrides[fqcn] = {"repo": repo, "file": ctx.rel(path), "line": line}
    return overrides


def _scope_records(ctx):
    merged = {}
    for rel_root in ROOTS:
        for path in _walk(ctx.root, rel_root, "entity_config.yml"):
            for scope, items in parse_scope_defs(read_text(path)).items():
                rec = merged.setdefault(scope, {"entity_items": set(), "field_items": set(), "sources": []})
                rec["entity_items"].update(items["entity"])
                rec["field_items"].update(items["field"])
                rec["sources"].append(ctx.rel(path))
    for scope in sorted(merged):
        rec = merged[scope]
        ei, fi = sorted(rec["entity_items"]), sorted(rec["field_items"])
        yield {
            "id": "scope:" + scope,
            "keys": [scope],
            "kind": "config-scope",
            "scope": scope,
            "entity_items": ei,
            "field_items": fi,
            "sources": rec["sources"],
            "file": rec["sources"][0],
            "text": "entity_config.yml scope; entity items: %s; field items: %s" % (",".join(ei) or "-", ",".join(fi) or "-"),
        }


def extract(ctx):
    entities = _collect_entities(ctx)
    overrides = _collect_overrides(ctx)
    for fqcn in sorted(entities):
        e = entities[fqcn]
        ov = overrides.get(fqcn) or {}
        rec = {
            "id": fqcn,
            "keys": [k for k in (e["table"], _short(fqcn)) if k],
            "kind": e["kind"],
            "table": e["table"],
            "repository": e["repository"],
            "repository_override": ov.get("repo"),
            "extend_override_file": "%s:%s" % (ov["file"], ov["line"]) if ov else None,
            "scopes": e["scopes"],
            "file": e["file"],
            "line": e["line"],
        }
        rec["text"] = _text(rec)
        yield rec
    for fqcn in sorted(set(overrides) - set(entities)):
        ov = overrides[fqcn]
        yield {
            "id": fqcn,
            "keys": [_short(fqcn)],
            "kind": "extend-override",
            "repository_override": ov["repo"],
            "file": ov["file"],
            "line": ov["line"],
            "text": "entity_extend override only (class not scanned) repo_override=%s" % (_short(ov["repo"]) if ov["repo"] else "-"),
        }
    yield from _scope_records(ctx)
