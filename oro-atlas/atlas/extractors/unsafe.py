"""Concrete classes typehinted in constructors: services of these classes must not be `decorates:`-ed."""
import os
import re

NAME = "unsafe"
ORDER = 10

SCAN_ROOTS = ("vendor/oro", "vendor/oroinc", "vendor/aaxisdigital", "src")
SKIP_DIRS = {"Tests", "tests", "Behat", "node_modules", ".git"}
PREFIXES = ("Oro\\", "Aaxis\\", "Buckman\\")
DECORATOR_TAG = "container.decorator"
INNER = ".inner"
ADVICE = ("do NOT decorates:, use aaxis_aspect.interceptor"
          " (final/static/private methods are skipped by its proxy - pick a public non-final method)")
FINAL_ADVICE = ("do NOT decorates:; aaxis_aspect.interceptor cannot proxy a final class either -"
                " use an event listener, a compiler-pass class swap, or another extension point")

# Concrete vendor classes that exist only to be subclassed (not abstract, so the kind check misses them).
EXTENSION_BASES = {"Symfony\\Component\\Console\\Command\\Command"}

_NS = re.compile(r"^namespace\s+([\w\\]+)\s*;", re.M)
_USE = re.compile(r"^use\s+(?!function\b|const\b)([\w\\]+?)(?:\s+as\s+(\w+))?\s*;", re.M)
_GROUP_USE = re.compile(r"^use\s+(?!function\b|const\b)([\w\\]+?)\\\{([^}]*)\}\s*;", re.M)
_DECL = re.compile(
    r"^\s*((?:(?:abstract|final|readonly)\s+)*)(class|interface|trait|enum)\s+(\w+)(?:\s+extends\s+([\w\\]+))?", re.M
)
_CTOR = re.compile(r"function\s+__construct\s*\(")
_SETTER = re.compile(r"function\s+(?:__construct|set[A-Z_]\w*)\s*\(")
_REQUIRED_PROP = re.compile(
    r"#\[\s*(?:\\?[\w\\]*\\)?Required\s*\]\s*(?:(?:public|protected|private|readonly)\s+)+(\??[\w\\|&]+)\s+\$"
)
_PARAM = re.compile(r"^(?:(?:public|protected|private|readonly|final)\s+)*(?P<type>[^$.]*?)\s*(?:&|\.\.\.)?\s*\$\w+")
_COMMENT = re.compile(r"/\*.*?\*/|(?<![:\w])//[^\n]*|#(?!\[)[^\n]*", re.S)
_SYMBOLS = {"self", "static", "parent"}


def _strip_attributes(text):
    out, i = [], 0
    while i < len(text):
        if text.startswith("#[", i):
            depth, i = 0, i + 1
            while i < len(text):
                depth += (text[i] == "[") - (text[i] == "]")
                i += 1
                if depth == 0:
                    break
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _balanced(text, start):
    """Text between the paren at start-1 and its match, or None when unbalanced."""
    depth, i = 1, start
    while i < len(text) and depth:
        depth += (text[i] == "(") - (text[i] == ")")
        i += 1
    return text[start:i - 1] if depth == 0 else None


def _split_top(text):
    parts, depth, cur = [], 0, []
    for ch in text:
        depth += ch in "([{"
        depth -= ch in ")]}"
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _imports(src):
    uses = {}
    for m in _USE.finditer(src):
        uses[m.group(2) or m.group(1).rsplit("\\", 1)[-1]] = m.group(1)
    for m in _GROUP_USE.finditer(src):
        for item in filter(None, (s.strip() for s in m.group(2).split(","))):
            name, _, alias = item.partition(" as ")
            uses[(alias or name).strip().rsplit("\\", 1)[-1]] = m.group(1) + "\\" + name.strip()
    return uses


def _resolve(name, ns, uses):
    head, _, rest = name.partition("\\")
    if name.startswith("\\"):
        fq = name[1:]
    elif head in uses:
        fq = uses[head] + ("\\" + rest if rest else "")
    else:
        fq = (ns + "\\" if ns else "") + name
    return fq


def _type_names(type_text, ns, uses):
    tokens = re.split(r"[|&()\s?]+", type_text)
    return [
        _resolve(t, ns, uses) for t in tokens
        if t and not (t[0].islower() and "\\" not in t) and t not in _SYMBOLS
    ]


def _param_types(body, ns, uses):
    found = []
    for param in _split_top(_COMMENT.sub("", _strip_attributes(body))):
        pm = _PARAM.match(param.split("=", 1)[0].strip())
        found += _type_names(pm.group("type"), ns, uses) if pm else []
    return found


def _ns_uses(src):
    ns_m = _NS.search(src)
    return (ns_m.group(1) if ns_m else ""), _imports(src)


def resolve_short_name(content, short):
    """Resolve a class name as written in a PHP file through its namespace and `use` imports."""
    ns, uses = _ns_uses(content)
    return _resolve(short.strip(), ns, uses)


def ctor_types(src):
    """Return (ctor line, [type FQCNs]) of the first constructor, or (None, [])."""
    m = _CTOR.search(src)
    body = _balanced(src, m.end()) if m else None
    found = _param_types(body, *_ns_uses(src)) if body is not None else []
    line = src.count("\n", 0, m.start()) + 1 if m else None
    return line, found


def injection_types(src):
    """Return (first line, [type FQCNs]) over constructors, set* methods and #[Required] typed properties."""
    ns, uses = _ns_uses(src)
    hits = []
    for m in _SETTER.finditer(src):
        body = _balanced(src, m.end())
        if body is not None:
            hits.append((m.start(), _param_types(body, ns, uses)))
    hits += [(m.start(), _type_names(m.group(1), ns, uses)) for m in _REQUIRED_PROP.finditer(_COMMENT.sub("", src))]
    hits = [h for h in hits if h[1]]
    first = min((h[0] for h in hits), default=None)
    line = src.count("\n", 0, first) + 1 if first is not None else None
    return line, [t for _, types in hits for t in types]


def declaration(src):
    """Return (fqcn, kind) of the first declaration in the file, kind in class/abstract/final/..."""
    return declaration_full(src)[:2]


def declaration_full(src):
    """Return (fqcn, kind, parent fqcn or None) of the first declaration in the file."""
    d = _DECL.search(src)
    ns_m = _NS.search(src)
    result = (None, None, None)
    if d:
        ns = ns_m.group(1) + "\\" if ns_m else ""
        parent = _resolve(d.group(4), *_ns_uses(src)) if d.group(4) else None
        kind = d.group(2)
        if kind == "class" and "abstract" in d.group(1):
            kind = "abstract"
        elif kind == "class" and "final" in d.group(1):
            kind = "final"
        result = (ns + d.group(3), kind, parent)
    return result


def _php_files(root):
    for sub in SCAN_ROOTS:
        for dp, dirs, files in os.walk(os.path.join(root, sub)):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if f.endswith(".php"):
                    yield os.path.join(dp, f)


def scan(root, parents=None, paths=None):
    """Return (kinds, uses {typehinted fqcn: [consumer]}); fills `parents` {fqcn: parent} and `paths` {fqcn: relpath}."""
    kinds, uses = {}, {}
    parents = {} if parents is None else parents
    paths = {} if paths is None else paths
    for path in _php_files(root):
        with open(path, encoding="utf-8", errors="ignore") as fh:
            src = fh.read()
        fqcn, kind, parent = declaration_full(src)
        if fqcn is None:
            continue
        kinds[fqcn] = kind
        paths[fqcn] = os.path.relpath(path, root)
        if parent:
            parents[fqcn] = parent
        line, types = injection_types(src) if "function" in src or "Required" in src else (None, [])
        rel = os.path.relpath(path, root)
        for t in dict.fromkeys(types):
            if t != fqcn:
                uses.setdefault(t, []).append({"class": fqcn, "file": rel, "line": line})
    return kinds, uses


def _ancestors(fqcn, parents):
    chain, seen = [], {fqcn}
    cur = parents.get(fqcn)
    while cur and cur not in seen:
        chain.append(cur)
        seen.add(cur)
        cur = parents.get(cur)
    return chain


def _kind_of(fqcn, kinds, ctx, paths=None):
    """Kind from the scan, else from the class file the locator finds (Symfony/third-party services)."""
    if fqcn not in kinds:
        rel, _ = ctx.locator.locate(fqcn)
        kinds[fqcn] = None
        if paths is not None:
            paths[fqcn] = rel
        if rel:
            with open(os.path.join(ctx.root, rel), encoding="utf-8", errors="ignore") as fh:
                kinds[fqcn] = declaration(fh.read())[1]
    return kinds[fqcn]


def _decorator_index(services):
    """Map original class -> {service ids, decorator ids}, resolved through container.decorator tags."""
    by_id = {r["id"]: r for r in services}
    decorators = {}
    for r in services:
        for t in r["tags"]:
            if t["name"] == DECORATOR_TAG:
                decorators.setdefault(t["attrs"].get("id"), []).append((r["id"], t["attrs"].get("inner")))
    return by_id, decorators


def join_services(services):
    """Map class -> {"ids": [...], "decorated_by": [...]} for non-abstract service definitions."""
    by_id, decorators = _decorator_index(services)
    inner_of = {}
    for decorated, pairs in decorators.items():
        for dec_id, inner in pairs:
            tagged = any(t["name"] == DECORATOR_TAG for t in by_id.get(inner, {"tags": []})["tags"])
            if inner in by_id and not tagged:
                inner_of[inner] = (decorated, [d for d, _ in pairs])
    out = {}
    for r in services:
        if r["abstract"] or not r["class"]:
            continue
        sid, decorated_by = inner_of.get(r["id"], (r["id"], []))
        entry = out.setdefault(r["class"], {"ids": [], "decorated_by": [], "decorator_classes": []})
        entry["decorator_classes"] += [by_id[d]["class"] for d in decorated_by if d in by_id]
        if sid not in entry["ids"]:
            entry["ids"].append(sid)
        entry["decorated_by"] += [d for d in decorated_by if d not in entry["decorated_by"]]
    return out


def _text(rec):
    shown = ", ".join("%s" % c["class"].rsplit("\\", 1)[-1] for c in rec["consumers"][:3])
    more = len(rec["consumers"]) - 3
    parts = ["concrete %s typehinted by %d ctor(s): %s%s" % (rec["kind"], rec["consumer_count"], shown, " +%d" % more if more > 0 else "")]
    if rec["services"]:
        parts.append("services=" + ",".join(rec["services"][:3]))
    if rec["decorated_by"]:
        parts.append("ALREADY decorated by " + ",".join(rec["decorated_by"]))
    parts.append(FINAL_ADVICE if rec["kind"] == "final class" else ADVICE)
    return "; ".join(parts)


def _contract_filter(kinds, paths, ctx):
    """Predicate: is this ancestor a vendor abstract base (Command, ConstraintValidator, ...)?"""
    def is_contract(fqcn):
        kind = _kind_of(fqcn, kinds, ctx, paths)
        rel = (paths.get(fqcn) or "").replace(os.sep, "/")
        return fqcn in EXTENSION_BASES or (kind == "abstract" and not rel.startswith("src/"))
    return is_contract


def _typed_ancestors(fqcn, parents, is_contract):
    # Vendor abstract bases are consumed polymorphically by design; a project abstract base is not.
    return [a for a in _ancestors(fqcn, parents) if not is_contract(a)]


def _candidates(uses, joined, ancestors):
    """Own-prefix typehinted classes, plus service classes typehinted directly or via an ancestor."""
    direct = {t for t in uses if t.startswith(PREFIXES) or t in joined}
    via_parent = {c for c in joined if any(a in uses for a in ancestors(c))}
    return sorted(direct | via_parent)


def extract(ctx):
    parents, paths = {}, {}
    kinds, uses = scan(ctx.root, parents, paths)
    joined = join_services(ctx.shard("services"))
    is_contract = _contract_filter(kinds, paths, ctx)
    memo = {}

    def ancestors(fqcn):
        if fqcn not in memo:
            memo[fqcn] = _typed_ancestors(fqcn, parents, is_contract)
        return memo[fqcn]

    for fqcn in _candidates(uses, joined, ancestors):
        kind = _kind_of(fqcn, kinds, ctx)
        if kind not in ("class", "final"):
            continue
        svc = joined.get(fqcn, {"ids": [], "decorated_by": [], "decorator_classes": []})
        # Consumers typehinting a parent break too: the decorator is not an instance of that parent.
        pool = uses.get(fqcn, []) + [dict(c, via=a) for a in ancestors(fqcn) for c in uses.get(a, [])]
        # A decorator takes its inner service by this type, which says nothing about other consumers.
        consumers = sorted(
            (c for c in pool if c["class"] not in svc["decorator_classes"] and c["class"] != fqcn),
            key=lambda c: (c["file"], c["class"]),
        )
        if not consumers:
            continue
        rel, line = ctx.locator.locate(fqcn)
        rec = {
            "id": fqcn,
            "keys": [fqcn.rsplit("\\", 1)[-1]] + svc["ids"],
            "kind": "final class" if kind == "final" else "class",
            "services": svc["ids"],
            "decorated_by": svc["decorated_by"],
            "consumer_count": len(consumers),
            "consumers": consumers,
            "file": rel,
            "line": line,
        }
        rec["text"] = _text(rec)
        yield rec


def src_decorates(root):
    """Project `decorates:` declarations as (service id, decorated id, relpath, line)."""
    sid, found = None, []
    for path in _yaml_files(root):
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for n, text in enumerate(fh, 1):
                m = re.match(r"^ {4}(\S[^:]*):\s*$", text.rstrip("\n")) or re.match(r"^ {4}(\S[^:]*):\s", text)
                if m:
                    sid = m.group(1).strip("'\"")
                d = re.match(r"^\s{8}decorates:\s*['\"]?([\w.\\]+)", text)
                if d:
                    found.append((sid, d.group(1), os.path.relpath(path, root), n))
    return found


def _yaml_files(root):
    for dp, dirs, files in os.walk(os.path.join(root, "src")):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith((".yml", ".yaml")):
                yield os.path.join(dp, f)
