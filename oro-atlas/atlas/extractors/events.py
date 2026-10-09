"""Event name -> registered listeners (runtime) joined with static dispatch sites."""
import os
import re
import subprocess

from ..common import AtlasError, read_text

NAME = "events"
ORDER = 50

SCAN_DIRS = ["vendor/oro", "vendor/oroinc", "vendor/aaxisdigital", "vendor/symfony", "src"]
# Symfony's form dispatches through a per-form dispatcher; its events never reach kernel listeners.
# Its other unresolved sites are generic forwarders (traceable/immutable dispatchers), pure noise.
SKIP_PREFIXES = ("vendor/symfony/form/",)
FORWARDER_PREFIX = "vendor/symfony/"
DYNAMIC = "dynamic"

_NS_RE = re.compile(r"^namespace\s+([\w\\]+)\s*;", re.M)
_USE_RE = re.compile(r"^use\s+([\w\\]+)(?:\s+as\s+(\w+))?\s*;", re.M)
_CLASS_RE = re.compile(r"^\s*(?:(?:final|abstract|readonly)\s+)*(?:class|interface|trait|enum)\s+(\w+)(?:\s+extends\s+([\w\\]+))?", re.M)
_CONST_RE = re.compile(r"\bconst\s+(?:[\w?|\\]+\s+)?([A-Z][A-Z0-9_]*)\s*=\s*([^;]+);")
_LITERAL_RE = re.compile(r"""^(?:'([^'\\]*)'|"([^"$\\]*)")$""")
_CONSTREF_RE = re.compile(r"^\\?([\w\\]+)::(\w+)$")
_NEW_RE = re.compile(r"^new\s+\\?([\w\\]+)")
_RECEIVER_WINDOW = 120
# Only the Symfony dispatcher; wrappers like MassActionDispatcher share the method name.
_RECEIVER_RE = re.compile(r"(?:\beventDispatcher|\bdispatcher|getEventDispatcher\(\)|get\((?:EventDispatcherInterface::class|'event_dispatcher')\))\s*\??$")
_VARCONST_RE = re.compile(r"^(\$\w+)::([A-Z][A-Z0-9_]*)$")
_MAX_DEPTH = 6


class FileInfo:
    """Namespace, imports, declared class and constants of one PHP source."""

    def __init__(self, src):
        ns = _NS_RE.search(src)
        self.ns = ns.group(1) if ns else ""
        self.uses = {(m.group(2) or m.group(1).rsplit("\\", 1)[-1]): m.group(1) for m in _USE_RE.finditer(src)}
        cls = _CLASS_RE.search(src)
        self.cls = (self.ns + "\\" + cls.group(1)) if cls else ""
        self.parent = self.fq(cls.group(2)) if cls and cls.group(2) else None
        self.consts = {m.group(1): m.group(2).strip() for m in _CONST_RE.finditer(src)}

    def fq(self, name):
        """Resolve a class reference as written in this file to an FQCN."""
        first = name.split("\\", 1)[0]
        if name.startswith("\\"):
            out = name[1:]
        elif first in self.uses:
            out = self.uses[first] + name[len(first):]
        else:
            out = (self.ns + "\\" if self.ns else "") + name
        return out


class Resolver:
    """Evaluates event-name expressions against constants found via the class locator."""

    def __init__(self, locator, read=None):
        self.locator = locator
        self._read = read or self._read_file
        self._info = {}

    @staticmethod
    def _read_file(path):
        return read_text(path)

    def info_for_class(self, fqcn):
        if fqcn not in self._info:
            path = self.locator.file_of(fqcn)
            self._info[fqcn] = FileInfo(self._read(path)) if path and os.path.isfile(path) else None
        return self._info[fqcn]

    def const_value(self, fqcn, name, depth=0):
        """Resolve Class::NAME through the parent chain; None when not a plain string."""
        info = self.info_for_class(fqcn) if depth < _MAX_DEPTH else None
        value = None
        if info is not None:
            if name in info.consts:
                value = self.expr(info.consts[name], info, depth + 1)
            elif info.parent:
                value = self.const_value(info.parent, name, depth + 1)
        return value

    def expr(self, text, info, depth=0):
        """Resolve a literal, Class::CONST or Class::class expression to a string."""
        text = text.strip()
        lit = _LITERAL_RE.match(text)
        ref = _CONSTREF_RE.match(text)
        value = None
        if lit:
            value = lit.group(1) if lit.group(1) is not None else lit.group(2)
        elif ref:
            value = self._ref(ref.group(1), ref.group(2), info, depth)
        return value

    def _ref(self, cname, const, info, depth):
        owner = info.cls if cname in ("self", "static") else (info.parent if cname == "parent" else info.fq(cname))
        if const == "class":
            value = owner
        else:
            value = self.const_value(owner, const, depth) if owner else None
        return value


def split_args(text):
    """Split a call's argument source on top-level commas, honouring quotes and nesting."""
    args, depth, cur, quote = [], 0, [], None
    for ch in text:
        if quote:
            cur.append(ch)
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
            cur.append(ch)
        elif ch in "([{":
            depth += 1
            cur.append(ch)
        elif ch in ")]}":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    tail = "".join(cur).strip()
    if tail:
        args.append(tail)
    return args


def call_args(src, open_idx):
    """Return the text between the parenthesis at open_idx and its match, or None."""
    depth, quote, i, end = 0, None, open_idx, None
    while end is None and i < len(src):
        ch = src[i]
        if quote:
            quote = None if ch == quote and src[i - 1] != "\\" else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            end = i if depth == 0 else None
        i += 1
    return src[open_idx + 1:end] if end is not None else None


def _event_class_of_var(var, src, upto, info):
    """Class of $var from `$var = new X` or a typed parameter, nearest before the call."""
    name = re.escape(var)
    found = None
    for m in re.finditer(r"%s\s*=\s*new\s+\\?([\w\\]+)" % name, src[:upto]):
        found = m.group(1)
    if found is None:
        for m in re.finditer(r"([\w\\?]+)\s+%s\b\s*[,)=]" % name, src[:upto]):
            if m.group(1).lstrip("?\\") not in ("array", "string", "int", "bool", "mixed", "return"):
                found = m.group(1)
    return info.fq(found.lstrip("?")) if found and found.lstrip("?") not in ("self", "static") else (info.cls if found else None)


def resolve_site(args, src, upto, info, resolver):
    """Return (event_name or None, expr_text) for the argument list of one dispatch call."""
    name = None
    shown = ", ".join(args)
    if len(args) >= 2:
        name = resolver.expr(args[1], info)
        vc = _VARCONST_RE.match(args[1].strip())
        if name is None and vc:
            owner = _event_class_of_var(vc.group(1), src, upto, info)
            name = resolver.const_value(owner, vc.group(2)) if owner else None
        shown = args[1]
    elif args:
        # `dispatch($e = new X(...))` names the event as plainly as `dispatch(new X(...))`.
        first = re.sub(r"^\$\w+\s*=\s*(?=new\b)", "", args[0])
        new = _NEW_RE.match(first)
        if new:
            name = info.fq(new.group(1)) if new.group(1) not in ("self", "static") else info.cls
        elif first.startswith("$") and re.match(r"^\$\w+$", first):
            name = _event_class_of_var(first, src, upto, info)
    return name, shown[:120]


def find_dispatch_sites(src, relpath, resolver):
    """Yield (name_or_None, expr, line) for every event-dispatcher ->dispatch( call in src."""
    info = FileInfo(src)
    for m in re.finditer(r"->\s*dispatch\s*\(", src):
        window = src[max(0, m.start() - _RECEIVER_WINDOW):m.start()]
        args_src = call_args(src, m.end() - 1)
        if args_src is not None and _RECEIVER_RE.search(window.rstrip()):
            name, shown = resolve_site(split_args(args_src), src, m.start(), info, resolver)
            yield name, shown, src.count("\n", 0, m.start()) + 1


def _grep_files(root, dirs):
    paths = [d for d in dirs if os.path.isdir(os.path.join(root, d))]
    out = []
    if paths:
        cmd = ["grep", "-rlE", "--include=*.php", "--exclude-dir=Tests", "--exclude-dir=Test", "--exclude-dir=node_modules", "-e", "->[[:space:]]*dispatch[[:space:]]*\\("] + paths
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        if proc.returncode > 1:
            raise AtlasError("grep failed: " + proc.stderr[-300:])
        out = sorted(p for p in proc.stdout.splitlines() if p and not p.startswith(SKIP_PREFIXES))
    return out


def collect_sites(ctx, resolver=None, files=None):
    """Return ({event: [site]}, [dynamic site]) over all scanned PHP files."""
    resolver = resolver or Resolver(ctx.locator)
    resolved, dynamic = {}, []
    for rel in files if files is not None else _grep_files(ctx.root, SCAN_DIRS):
        src = resolver._read(os.path.join(ctx.root, rel))
        for name, expr, line in find_dispatch_sites(src, rel, resolver):
            site = {"file": rel, "line": line}
            if name:
                resolved.setdefault(name, []).append(site)
            elif not rel.startswith(FORWARDER_PREFIX):
                dynamic.append(dict(site, expr=expr))
    return resolved, dynamic


def _listener_index(container):
    """(class, event, method) -> service ids from kernel.event_listener tags; class -> subscribers."""
    exact, subs = {}, {}
    for sid, d in container["definitions"].items():
        for t in d.get("tags", []):
            p = t.get("parameters", {})
            if t["name"] == "kernel.event_listener" and p.get("event"):
                exact.setdefault((d.get("class"), p["event"], p.get("method")), []).append(sid)
            elif t["name"] == "kernel.event_subscriber":
                subs.setdefault(d.get("class"), []).append(sid)
    return exact, subs


def _listener(ctx, ev, l, exact, subs):
    cls, method = l.get("class"), l.get("name")
    services = exact.get((cls, ev, method)) or exact.get((cls, ev, None)) or subs.get(cls) or []
    rel, line = ctx.locator.locate(cls) if cls else (None, None)
    return {"class": cls, "method": method, "priority": l.get("priority", 0),
            "services": sorted(set(services)), "file": rel, "line": line}


def build_record(ctx, ev, listeners, sites, exact, subs):
    lis = sorted((_listener(ctx, ev, l, exact, subs) for l in listeners), key=lambda x: -x["priority"])
    is_class = "\\" in ev
    rel, line = ctx.locator.locate(ev) if is_class else (None, None)
    first = sites[0] if sites else None
    parts = ["%d listener%s" % (len(lis), "" if len(lis) == 1 else "s"), "%d dispatch site%s" % (len(sites), "" if len(sites) == 1 else "s")]
    if not lis and sites:
        parts.append("FREE HOOK (dispatched, no listener)")
    if not sites:
        parts.append("no static dispatch site found (dynamic or external)")
    rec = {
        "id": ev,
        "keys": [ev.rsplit("\\", 1)[-1]] if is_class else [],
        "kind": "class" if is_class else "string",
        "listeners": lis,
        "dispatch_sites": sites[:20],
        "dispatch_count": len(sites),
        "free_hook": bool(sites) and not lis,
        "event_class": ev if is_class and rel else None,
        "text": "; ".join(parts) + _listener_hint(lis),
        "file": first["file"] if first else rel,
        "line": first["line"] if first else line,
    }
    return rec


def _listener_hint(lis):
    shown = ["%s::%s@%s" % (l["class"].rsplit("\\", 1)[-1], l["method"], l["priority"]) for l in lis[:3] if l["class"]]
    return (" [" + ", ".join(shown) + (", +%d" % (len(lis) - 3) if len(lis) > 3 else "") + "]") if shown else ""


DOCTRINE_TAGS = {
    "doctrine.event_listener": "event_listener",
    "doctrine.event_subscriber": "event_subscriber",
    "doctrine.orm.entity_listener": "entity_listener",
}
_SUBSCRIBED_RE = re.compile(r"function\s+getSubscribedEvents\s*\([^)]*\)[^{]*\{(.*?)\n\s{0,4}\}", re.S)
_DOCTRINE_EVENT_RE = re.compile(r"(?:Events::|['\"])(\w+)['\"]?")
DOCTRINE_EVENTS = frozenset((
    "prePersist", "postPersist", "preUpdate", "postUpdate", "preRemove", "postRemove", "preFlush", "onFlush",
    "postFlush", "onClear", "postLoad", "loadClassMetadata", "onClassMetadataNotFound", "postGenerateSchemaTable",
    "postGenerateSchema",
))


def subscribed_doctrine_events(src):
    """Doctrine event names a subscriber's getSubscribedEvents() returns, in source order."""
    m = _SUBSCRIBED_RE.search(src)
    names = [n for n in _DOCTRINE_EVENT_RE.findall(m.group(1))] if m else []
    return [n for n in dict.fromkeys(names) if n in DOCTRINE_EVENTS]


def _method_line(ctx, cls, method, cache):
    """(relpath, line of `function method`) falling back to the class declaration."""
    if (cls, method) not in cache:
        rel, line = ctx.locator.locate(cls) if cls else (None, None)
        path = ctx.locator.file_of(cls) if cls else None
        found = re.search(r"function\s+%s\s*\(" % re.escape(method), read_text(path)) if path and method else None
        if found:
            line = read_text(path).count("\n", 0, found.start()) + 1
        cache[(cls, method)] = (rel, line)
    return cache[(cls, method)]


def _doctrine_entries(defs):
    """[(service id, class, tag kind, event or None, params)] for every Doctrine-tagged service."""
    return [
        (sid, d.get("class") or "", DOCTRINE_TAGS[t["name"]], (t.get("parameters") or {}).get("event"), t.get("parameters") or {})
        for sid, d in sorted(defs.items())
        for t in d.get("tags", []) if t["name"] in DOCTRINE_TAGS
    ]


def doctrine_records(ctx, defs):
    """One record per (event, listener, entity): Doctrine listeners/subscribers from vendor and src alike."""
    cache, rows = {}, []
    for sid, cls, kind, event, p in _doctrine_entries(defs):
        events = [event] if event else (
            subscribed_doctrine_events(read_text(ctx.locator.file_of(cls) or "")) if kind == "event_subscriber" and cls else [])
        for ev in events:
            # Doctrine calls a method named after the event unless the tag names another one.
            method = p.get("method") or ev
            rel, line = _method_line(ctx, cls, method, cache)
            rows.append({
                "event": ev, "type": kind, "class": cls, "method": method, "priority": p.get("priority", 0),
                "entity": p.get("entity"), "service": sid, "connection": p.get("connection") or p.get("entity_manager"),
                "file": rel, "line": line,
            })
    rows.sort(key=lambda r: (r["event"], -int(r["priority"] or 0), r["class"], r["entity"] or ""))
    seen = {}
    for r in rows:
        base = "doctrine:%s:%s::%s%s" % (r["event"], r["class"], r["method"], "@" + r["entity"] if r["entity"] else "")
        seen[base] = seen.get(base, 0) + 1
        yield _doctrine_record(r, base if seen[base] == 1 else "%s#%d" % (base, seen[base]))


def _doctrine_record(r, rid):
    short = lambda c: c.rsplit("\\", 1)[-1] if c else ""  # noqa: E731
    text = "doctrine %s %s::%s priority=%s%s" % (
        r["type"], short(r["class"]), r["method"], r["priority"], " entity=" + short(r["entity"]) if r["entity"] else " (all entities)")
    keys = [k for k in (r["event"], short(r["class"]), r["class"], short(r["entity"]), r["entity"], r["service"]) if k]
    return dict(r, id=rid, keys=list(dict.fromkeys(keys)), kind="doctrine_listener", listeners=[], dispatch_sites=[],
                dispatch_count=0, free_hook=False, text=text)


def _all_sites(ctx):
    """Dispatch sites: vendor/ memoised until composer changes, src/ rescanned each build."""
    vendor = ctx.vendor_memo("events-sites", None, lambda: dict(zip(("resolved", "dynamic"), collect_sites(ctx, files=_grep_files(ctx.root, SCAN_DIRS[:-1])))))
    resolved, dynamic = collect_sites(ctx, files=_grep_files(ctx.root, SCAN_DIRS[-1:]))
    merged = {ev: list(sites) for ev, sites in vendor["resolved"].items()}
    for ev, sites in resolved.items():
        merged.setdefault(ev, []).extend(sites)
    return merged, vendor["dynamic"] + dynamic


def extract(ctx):
    runtime = ctx.events()
    exact, subs = _listener_index(ctx.container())
    resolved, dynamic = _all_sites(ctx)
    for ev in sorted(set(runtime) | set(resolved)):
        yield build_record(ctx, ev, runtime.get(ev, []), resolved.get(ev, []), exact, subs)
    yield from doctrine_records(ctx, ctx.container()["definitions"])
    by_file = {}
    for s in dynamic:
        by_file.setdefault(s["file"], []).append(s)
    for rel, sites in sorted(by_file.items()):
        exprs = sorted({s["expr"] for s in sites})
        yield {"id": "dynamic:" + rel, "keys": [], "kind": DYNAMIC, "dispatch_sites": sites[:20],
               "dispatch_count": len(sites), "free_hook": False, "listeners": [],
               "text": "UNRESOLVED dynamic event name(s): " + "; ".join(exprs[:3]),
               "file": rel, "line": sites[0]["line"]}
