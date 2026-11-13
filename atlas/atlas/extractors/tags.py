"""DI tag -> implementing services (from the container dump) + statically detectable consumers."""
import hashlib
import os
import re
import subprocess
from collections import Counter

from ..common import read_text, strip_comment
from ..miniyaml import LDict, parse

NAME = "tags"
ORDER = 10

STRICT = (
    "findTaggedServiceIds|findAndSortTaggedServices|TaggedIteratorArgument|AutowireIterator|"
    "AutowireLocator|TaggedIterator|TaggedLocator|PriorityTaggedLocator|PriorityTaggedServiceTrait"
)
CALL_RE = re.compile(r"\b(findTaggedServiceIds|findAndSortTaggedServices\w*|TaggedIteratorArgument|AutowireIterator|"
                     r"AutowireLocator|TaggedIterator|TaggedLocator|\w*CompilerPass)\s*\(")
LITERAL_RE = re.compile(r"""['"]([\w.\-:]+)['"]""")
CONST_DEF_RE = re.compile(r"\bconst\s+(?:[\w\\?]+\s+)?(\w+)\s*=\s*['\"]([^'\"]*)['\"]")
CONST_REF_RE = re.compile(r"\b(\w+)::([A-Z][A-Z0-9_]*)\b")
TAG_CONST_RE = r"const[[:space:]]+[A-Za-z0-9_]*TAG[A-Za-z0-9_]*[[:space:]]*="
NS_RE = re.compile(r"^namespace\s+([\w\\]+)\s*;", re.M)
CLASS_RE = re.compile(r"^\s*(?:(?:final|abstract|readonly)\s+)*(?:class|trait)\s+(\w+)", re.M)
YAML_TAGGED_RE = re.compile(r"!tagged_(?:iterator|locator)\s+(?:\{[^}]*?\btag:\s*)?['\"]?([\w.\-:]+)")
MAX_ARGS = 500
MAX_CONSUMERS = 20
SKIP_DIRS = ("Tests", "Test", "tests", "node_modules", "Fixtures")


def _balanced_args(text, start):
    """Text of a call's parentheses starting right after '(' at `start`, capped."""
    depth, i, end = 1, start, min(len(text), start + MAX_ARGS)
    while i < end and depth:
        depth += {"(": 1, ")": -1}.get(text[i], 0)
        i += 1
    return text[start:i]


def php_class(text):
    cls = CLASS_RE.search(text)
    ns = NS_RE.search(text)
    return ((ns.group(1) + "\\") if ns else "") + cls.group(1) if cls else None


def scan_php(text, known, global_consts=None):
    """Return [(tag, line, via, confidence)]; 'call' = tag is an argument of a tag-consuming call."""
    consts = dict(CONST_DEF_RE.findall(text))
    global_consts = global_consts or {}
    found, seen = [], set()

    def add(tag, pos, via, conf):
        line = text.count("\n", 0, pos) + 1
        if tag in known and (tag, line) not in seen:
            seen.add((tag, line))
            found.append((tag, line, via, conf))

    for m in CALL_RE.finditer(text):
        args = _balanced_args(text, m.end())
        for lit in LITERAL_RE.findall(args):
            add(lit, m.start(), m.group(1), "call")
        for owner, ref in CONST_REF_RE.findall(args):
            local = consts.get(ref) if owner in ("self", "static") else None
            add(local or global_consts.get((owner, ref)), m.start(), m.group(1), "call")
    if re.search(STRICT, text):
        # Tag held in a property/variable: only the file-level co-occurrence is knowable.
        for m in LITERAL_RE.finditer(text):
            if (m.group(1), text.count("\n", 0, m.start()) + 1) not in seen and m.group(1) in known:
                if not any(t == m.group(1) for t, _, _, _ in found):
                    add(m.group(1), m.start(), "file-mention", "file")
    return found


def _service_ranges(text):
    """(first, last) line of the `services:` section plus sorted [(line, service id)] inside it."""
    tree = parse(text)
    top = tree.lines if isinstance(tree, LDict) else {}
    services = tree.get("services") if "services" in top else None
    first = top.get("services", 0)
    last = min((ln for ln in top.values() if ln > first), default=float("inf"))
    starts = sorted((ln, sid) for sid, ln in getattr(services, "lines", {}).items())
    return (first, last, starts) if starts else (0, 0, [])


def scan_yaml(text, known):
    """Return [(tag, line, owner_service_id)] for !tagged_iterator / !tagged_locator arguments."""
    first, last, starts = _service_ranges(text)
    # The YAML reader drops `!tag` markers, so match them per line and attribute by service line ranges.
    hits = [(m.group(1), n) for n, raw in enumerate(text.splitlines(), 1) if first < n < last
            for m in YAML_TAGGED_RE.finditer(strip_comment(raw)) if m.group(1) in known]
    return [(tag, n, next((sid for ln, sid in reversed(starts) if ln <= n), None)) for tag, n in hits]


def _grep_files(root, dirs, pattern, include):
    dirs = [d for d in dirs if os.path.isdir(d)]
    cmd = ["grep", "-rlE", pattern] + ["--include=" + i for i in include]
    cmd += ["--exclude-dir=" + d for d in SKIP_DIRS] + dirs
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return sorted(p for p in proc.stdout.splitlines() if p)


def collect_tag_constants(dirs, known):
    """{(ShortClass, CONST): tag} for tag-named constants, so `Util::PROCESSOR_TAG` resolves across files."""
    out = {}
    for path in _grep_files(None, dirs, TAG_CONST_RE, ["*.php"]):
        text = read_text(path)
        cls = php_class(text)
        for name, value in CONST_DEF_RE.findall(text):
            if cls and value in known:
                out[(_short(cls), name)] = value
    return out


def _scan_dirs(ctx, dirs, known, global_consts):
    consumers = {}

    def put(tag, rec):
        consumers.setdefault(tag, []).append(rec)

    php_pat = STRICT + "|CompilerPass\\("
    for path in _grep_files(ctx.root, dirs, php_pat, ["*.php"]):
        text = read_text(path)
        cls = php_class(text)
        for tag, line, via, conf in scan_php(text, known, global_consts):
            put(tag, {"class": cls, "file": ctx.rel(path), "line": line, "via": via, "confidence": conf})
    for path in _grep_files(ctx.root, dirs, "!tagged_(iterator|locator)", ["*.yml", "*.yaml"]):
        for tag, line, owner in scan_yaml(read_text(path), known):
            put(tag, {"service": owner, "file": ctx.rel(path), "line": line, "via": "tagged_iterator", "confidence": "call"})
    return consumers


def _vendor_part(ctx, known):
    dirs = [os.path.join(ctx.root, "vendor")]
    consts = collect_tag_constants(dirs, known)
    return {"consts": [[c, n, v] for (c, n), v in consts.items()], "consumers": _scan_dirs(ctx, dirs, known, consts)}


def collect_consumers(ctx, known):
    """Vendor consumers are memoised (keyed by the tag set); src/ is rescanned every build."""
    key = hashlib.sha1("\n".join(sorted(known)).encode()).hexdigest()
    vendor = ctx.vendor_memo("tags-consumers", key, lambda: _vendor_part(ctx, known))
    src = [os.path.join(ctx.root, "src")]
    consts = {(c, n): v for c, n, v in vendor["consts"]}
    consts.update(collect_tag_constants(src, known))
    consumers = {t: list(recs) for t, recs in vendor["consumers"].items()}
    for tag, recs in _scan_dirs(ctx, src, known, consts).items():
        consumers.setdefault(tag, []).extend(recs)
    return consumers


def _clean_attrs(params):
    return params if isinstance(params, dict) else {}


def build_implementers(ctx, defs):
    by_tag = {}
    for sid in sorted(defs):
        d = defs[sid]
        cls = d.get("class") or ""
        if sid.startswith(".") and not cls:
            continue
        rel, line = ctx.locator.locate(cls) if cls else (None, None)
        for t in d.get("tags", []):
            by_tag.setdefault(t["name"], []).append({
                "id": sid, "class": cls, "attrs": _clean_attrs(t.get("parameters")), "file": rel, "line": line,
            })
    return by_tag


def _short(cls):
    return (cls or "?").rsplit("\\", 1)[-1]


def _consumer_label(c):
    return c.get("class") or c.get("service") or c["file"]


def _rank(cons):
    return sorted(cons, key=lambda c: (c["confidence"] != "call", c["file"], c["line"]))


def _text(tag, impls, cons):
    parts = ["%d services" % len(impls)]
    names = [_short(i["class"]) for i in impls[:3]]
    parts.append("e.g. " + ", ".join(names))
    if cons:
        labels = [_short(_consumer_label(c)) + ("?" if c["confidence"] == "file" else "") for c in cons[:3]]
        parts.append("consumed by " + ", ".join(labels) + (" (+%d)" % (len(cons) - 3) if len(cons) > 3 else ""))
    else:
        parts.append("no static consumer found")
    return "; ".join(parts)


def extract(ctx):
    defs = ctx.container()["definitions"]
    by_tag = build_implementers(ctx, defs)
    consumers = collect_consumers(ctx, set(by_tag))
    for tag in sorted(by_tag):
        impls = by_tag[tag]
        cons = _rank(consumers.get(tag, []))[:MAX_CONSUMERS]
        attr_keys = Counter(k for i in impls for k in i["attrs"])
        first = cons[0] if cons else (impls[0] if impls else {})
        yield {
            "id": tag,
            "keys": sorted({c["class"] for c in cons if c.get("class")}),
            "text": _text(tag, impls, cons),
            "file": first.get("file"),
            "line": first.get("line"),
            "internal": tag.startswith("container.") or tag.startswith("kernel."),
            "count": len(impls),
            "attr_keys": dict(attr_keys.most_common()),
            "consumers": cons,
            "implementers": impls,
        }
