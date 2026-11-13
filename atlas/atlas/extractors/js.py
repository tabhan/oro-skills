"""JS wiring: jsmodules.yml entries and mediator event names (trigger/execute/setHandler/on)."""
import json
import os
import re

from ..common import read_text
from ..miniyaml import line_map, parse

NAME = "js"

SECTIONS = ("aliases", "app-modules", "dynamic-imports", "configs", "entry", "map", "shim")
SKIP_DIRS = {"node_modules", "Tests", "tests", ".git", "test"}
MAX_SITES = 25
MAX_VALUE = 80

_CALL_RE = re.compile(
    r"\bmediator\.(trigger|execute|setHandler|on|once)\(\s*(['\"`])([^'\"`\n]*?)\2(\s*\+|(?=\s*[,)]))",
    re.S,
)
# Object form: mediator.execute({name: 'layout:init', silent: true}, ...)
_OBJ_CALL_RE = re.compile(r"\bmediator\.(trigger|execute)\(\s*\{\s*name\s*:\s*(['\"])([^'\"\n]+)\2")
# A dynamic prefix with this few literal characters matches nearly any query; it is noise.
MIN_DYNAMIC_PREFIX = 4
_ROLE = {"trigger": "triggers", "execute": "triggers", "setHandler": "handlers", "on": "listeners", "once": "listeners"}


def parse_yaml(text):
    """(tree, {path_tuple: line}) for a jsmodules.yml; a non-map document yields an empty tree."""
    tree = parse(text)
    return (tree if isinstance(tree, dict) else {}), line_map(tree)


def _short(value):
    s = value if isinstance(value, str) else json.dumps(value)
    return s if len(s) <= MAX_VALUE else s[: MAX_VALUE - 3] + "..."


class _Ids:
    def __init__(self):
        self.seen = {}

    def unique(self, base):
        n = self.seen.get(base, 0) + 1
        self.seen[base] = n
        return base if n == 1 else "%s#%d" % (base, n)


def yaml_records(tree, lines, rel, ids):
    for sec in SECTIONS:
        body = tree.get(sec)
        for rec in _SECTION_FN[sec](body, lambda *p, s=sec: lines.get((s,) + p, lines.get((s,))), rel, ids):
            yield rec


def _rec(ids, kind, ident, rel, line, text, keys, **extra):
    rec = {"id": ids.unique("%s:%s" % (kind, ident)), "kind": kind, "text": text, "file": rel, "line": line}
    rec["keys"] = [k for k in keys if k]
    rec.update(extra)
    return rec


def _aliases(body, ln, rel, ids):
    for name, target in sorted((body or {}).items()):
        if isinstance(target, str):
            yield _rec(ids, "alias", name, rel, ln(name), "alias %s -> %s" % (name, target), [name, target], target=target)


def _app_modules(body, ln, rel, ids):
    for i, mod in enumerate(body or []):
        yield _rec(ids, "app-module", mod, rel, ln(i), "app-module %s" % mod, [mod], module=mod)


def _dynamic(body, ln, rel, ids):
    for chunk, mods in sorted((body or {}).items()):
        for i, mod in enumerate(mods or []):
            yield _rec(ids, "dynamic-import", "%s:%s" % (chunk, mod), rel, ln(chunk, i),
                       "dynamic-import chunk=%s %s" % (chunk, mod), [mod], chunk=chunk, module=mod)


def _configs(body, ln, rel, ids):
    for mod, cfg in sorted((body or {}).items()):
        if isinstance(cfg, dict):
            shown = "{%s}" % ", ".join("%s=%s" % (k, _short(v)) for k, v in list(cfg.items())[:4])
            keys = list(cfg)
        else:
            shown, keys = _short(cfg) if cfg is not None else "{}", []
        yield _rec(ids, "config", mod, rel, ln(mod), "config %s %s" % (mod, shown), [mod], module=mod, config_keys=keys)


def _entry(body, ln, rel, ids):
    for name, mods in sorted((body or {}).items()):
        for i, mod in enumerate(mods if isinstance(mods, list) else []):
            yield _rec(ids, "entry", "%s:%s" % (name, mod), rel, ln(name, i), "entry %s %s" % (name, mod), [mod], entry=name, module=mod)


def _map(body, ln, rel, ids):
    for scope, repl in sorted((body or {}).items()):
        for src, dst in sorted((repl if isinstance(repl, dict) else {}).items()):
            yield _rec(ids, "map", "%s:%s" % (scope, src), rel, ln(scope, src),
                       "map scope=%s %s -> %s" % (scope, src, dst), [src, dst], scope=scope, target=dst)


def _shim(body, ln, rel, ids):
    for name, cfg in sorted((body or {}).items()):
        yield _rec(ids, "shim", name, rel, ln(name), "shim %s %s" % (name, _short(cfg)), [name], module=name)


_SECTION_FN = {
    "aliases": _aliases, "app-modules": _app_modules, "dynamic-imports": _dynamic,
    "configs": _configs, "entry": _entry, "map": _map, "shim": _shim,
}


_BLOCK_COMMENT_RE = re.compile(r"^[ \t]*/\*.*?\*/", re.S | re.M)


def _blank_block_comments(text):
    # Keep newlines so reported line numbers stay true to the source file.
    return _BLOCK_COMMENT_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def _literal_name(m):
    name, dynamic = m.group(3), bool(m.group(4).strip())
    if m.group(2) == "`" and "${" in name:
        # A template interpolation is a runtime part: keep only the literal prefix.
        name, dynamic = name.split("${", 1)[0], True
    return name, dynamic


def _is_noise(name, dynamic):
    return not name or (dynamic and len(re.sub(r"\W", "", name)) < MIN_DYNAMIC_PREFIX)


def mediator_calls(text):
    """Yield (op, event, dynamic, line) for each mediator call with a literal or templated name."""
    text = _blank_block_comments(text)
    found = [(m.start(), m.group(1)) + _literal_name(m) for m in _CALL_RE.finditer(text)]
    found += [(m.start(), m.group(1), m.group(3), False) for m in _OBJ_CALL_RE.finditer(text)]
    for start, op, name, dynamic in sorted(found):
        line_start = text.rfind("\n", 0, start) + 1
        if not _is_noise(name, dynamic) and not text[line_start:start].lstrip().startswith(("//", "*")):
            yield op, name, dynamic, text.count("\n", 0, start) + 1


def _walk(base, suffixes):
    for cur, dirs, files in os.walk(base, followlinks=True):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f.endswith(suffixes) and not f.endswith(".min.js"):
                yield os.path.join(cur, f)


def _roots(ctx):
    cands = ["vendor/oro", "vendor/oroinc", "vendor/aaxisdigital", "node_modules/@oroinc", "src"]
    return [os.path.join(ctx.root, c) for c in cands if os.path.isdir(os.path.join(ctx.root, c))]


def _event_records(events, ids):
    for name, dynamic in sorted(events):
        ev = events[(name, dynamic)]
        sites = {role: ev[role] for role in ("handlers", "triggers", "listeners") if ev[role]}
        first = (sites.get("handlers") or sites.get("triggers") or sites["listeners"])[0]
        file, line = first.rsplit(":", 1)
        counts = " ".join("%s=%d" % (r, len(ev[r])) for r in sites)
        # A runtime-built name is only a prefix: no exact keys, so it never outranks a real event.
        shown = name + "*" if dynamic else name
        yield {
            "id": ids.unique("mediator:%s" % shown), "kind": "mediator", "keys": [] if dynamic else [name],
            "event": name, "dynamic": dynamic,
            "text": "mediator %s %s%s" % (shown, counts, " (dynamic prefix)" if dynamic else ""),
            "file": file, "line": int(line),
            "handlers": ev["handlers"][:MAX_SITES], "triggers": ev["triggers"][:MAX_SITES],
            "listeners": ev["listeners"][:MAX_SITES],
        }


def extract(ctx):
    ids = _Ids()
    events = {}
    for root in _roots(ctx):
        for path in _walk(root, (".yml", ".js")):
            rel = ctx.rel(path)
            if path.endswith("jsmodules.yml"):
                tree, lines = parse_yaml(read_text(path))
                yield from yaml_records(tree, lines, rel, ids)
            elif path.endswith(".js"):
                for op, name, dynamic, line in mediator_calls(read_text(path)):
                    ev = events.setdefault((name, dynamic), {"handlers": [], "triggers": [], "listeners": []})
                    ev[_ROLE[op]].append("%s:%d" % (rel, line))
    yield from _event_records(events, ids)
