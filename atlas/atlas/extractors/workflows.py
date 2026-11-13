"""Workflow definitions (workflows.yml) and operations/action_groups (actions.yml).

Oro YAML is read with a small indentation scanner: stdlib has no YAML parser and we
only need names, a few scalar/list properties and the line each definition starts on.
"""
import glob
import os

from ..common import read_text
from ..miniyaml import LList, parse as parse_yaml

NAME = "workflows"
ORDER = 50

VENDOR_GLOBS = ("vendor/oro", "vendor/oroinc", "vendor/aaxisdigital")
CONFIG_DIR = os.path.join("Resources", "config", "oro")
TRANSLATIONS_DIR = os.path.join("Resources", "translations")


class Node:
    """Read-only view over a miniyaml value that keeps the key and its source line."""
    __slots__ = ("key", "value", "line")

    def __init__(self, key, value, line):
        self.key, self.value, self.line = key, value, line

    @property
    def kids(self):
        v = self.value
        return [Node(k, x, getattr(v, "lines", {}).get(k, self.line)) for k, x in v.items()] if isinstance(v, dict) else []

    def child(self, key):
        v = self.value
        found = None
        if isinstance(v, dict) and key in v:
            found = Node(key, v[key], getattr(v, "lines", {}).get(key, self.line))
        return found

    def names(self):
        return [k.key for k in self.kids]


def _text(value):
    return ("true" if value else "false") if isinstance(value, bool) else str(value)


def parse(text):
    """Return a root Node whose kids mirror the YAML mapping nesting."""
    return Node(None, parse_yaml(text), 0)


def as_list(node):
    """Scalar, flow list or block list -> list[str]."""
    val = node.value if node is not None else None
    items = val if isinstance(val, list) else [] if val is None or isinstance(val, dict) else [val]
    return [_text(i) for i in items if i is not None and not isinstance(i, (dict, list)) and _text(i)]


def scalar(node):
    val = node.value if node is not None else None
    if isinstance(val, list):
        val = "[%s]" % ", ".join(_text(v) for v in val)
    return _text(val) if val is not None and val != "" and not isinstance(val, dict) else None


def _config_files(root, filename):
    patterns = [os.path.join(root, "src", "**", CONFIG_DIR, filename)]
    patterns += [os.path.join(root, v, "**", CONFIG_DIR, filename) for v in VENDOR_GLOBS]
    found = {}
    for pat in patterns:
        for path in glob.glob(pat, recursive=True):
            if "/node_modules/" not in path and "/Tests/" not in path:
                found[os.path.realpath(path)] = path
    return sorted(found.values())


def _imports(tree):
    """[(item dict, line)] of the `imports:` list."""
    imps = tree.value.get("imports") if isinstance(tree.value, dict) else None
    imps = imps if isinstance(imps, LList) else []
    return [(i, imps.lines[n]) for n, i in enumerate(imps) if isinstance(i, dict)]


def _read_tree(path, seen=None):
    """Yield (path, root Node) for a file and everything it imports."""
    seen = seen if seen is not None else set()
    real = os.path.realpath(path)
    if real not in seen and os.path.isfile(path):
        seen.add(real)
        tree = parse(read_text(path))
        yield path, tree
        for imp, _ in _imports(tree):
            if isinstance(imp.get("resource"), str):
                yield from _read_tree(os.path.join(os.path.dirname(path), imp["resource"]), seen)


def _bundle(rel):
    parts = rel.split(os.sep)
    cut = parts.index("Resources") if "Resources" in parts else len(parts)
    return parts[cut - 1] if cut else ""


def _entries(ctx, filename, section):
    """Yield (name, node, relpath) for every definition under `section` in all files."""
    for top in _config_files(ctx.root, filename):
        for path, tree in _read_tree(top):
            sec = tree.child(section)
            rel = ctx.rel(path)
            for node in (sec.kids if sec else []):
                if node.key:
                    yield node.key, node, rel


def _where(rel, line):
    return "%s:%d" % (rel, line)


def _short(items, n=3):
    shown = ",".join(items[:n])
    return shown + ("(+%d)" % (len(items) - n) if len(items) > n else "")


def _merge(entries, primary_prop):
    """Group by name; primary = definition that carries `primary_prop`, others are overlays."""
    groups = {}
    for name, node, rel in entries:
        groups.setdefault(name, []).append((node, rel))
    for name, defs in groups.items():
        main = next((d for d in defs if d[0].child(primary_prop)), defs[0])
        yield name, main, [d for d in defs if d is not main], defs


def _union(defs, prop):
    out = []
    for node, _ in defs:
        out += [v for v in as_list(node.child(prop)) if v not in out]
    return out


def _transitions(wf_defs):
    steps, trans = [], {}
    for node, _ in wf_defs:
        st = node.child("steps")
        for s in (st.kids if st else []):
            if s.key not in steps:
                steps.append(s.key)
            for t in as_list(s.child("allowed_transitions")):
                frm = trans.setdefault(t, {"name": t, "from": [], "to": None})["from"]
                if s.key not in frm:
                    frm.append(s.key)
        tr = node.child("transitions")
        for t in (tr.kids if tr else []):
            rec = trans.setdefault(t.key, {"name": t.key, "from": [], "to": None})
            rec["to"] = scalar(t.child("step_to")) or rec["to"]
            if scalar(t.child("is_start")) == "true":
                rec["is_start"] = True
    # `__start__` in allowed_transitions is only a reference; it is a real transition only when defined
    return steps, [t for t in trans.values() if t["to"] or t["name"] != "__start__"]


def _clones(ctx):
    """Map alias -> (base workflow, relpath, line) for `{ workflow: X, as: Y }` imports."""
    return {
        imp["as"]: (imp["workflow"], ctx.rel(path), line)
        for top in _config_files(ctx.root, "workflows.yml")
        for path, tree in _read_tree(top)
        for imp, line in _imports(tree)
        if isinstance(imp.get("workflow"), str) and isinstance(imp.get("as"), str)
    }


def _flatten(value, prefix=""):
    items = value.items() if isinstance(value, dict) else ()
    out = {}
    for k, v in items:
        key = "%s.%s" % (prefix, k) if prefix else str(k)
        out.update(_flatten(v, key) if isinstance(v, dict) else {key: v})
    return out


def _translations(root):
    """English workflow translations as flat dotted keys; project files override vendor."""
    pats = [os.path.join(root, v, "**", TRANSLATIONS_DIR, "workflows.en.yml") for v in VENDOR_GLOBS]
    pats.append(os.path.join(root, "src", "**", TRANSLATIONS_DIR, "workflows.en.yml"))
    out = {}
    for path in (p for pat in pats for p in sorted(glob.glob(pat, recursive=True)) if "/Tests/" not in p):
        out.update(_flatten(parse_yaml(read_text(path))))
    return out


def _label_text(rec, trans):
    """Oro defaults an omitted workflow label to oro.workflow.<name>.label."""
    text = trans.get(rec["label"] or "oro.workflow.%s.label" % rec["id"])
    return text if isinstance(text, str) and text else None


def _merge_transitions(base, own):
    """A clone overrides the base per transition name; unmentioned base transitions stay."""
    merged = {t["name"]: dict(t) for t in base}
    for t in own:
        old = merged.get(t["name"], {})
        merged[t["name"]] = dict(t, to=t["to"] or old.get("to"), **{"from": t["from"] or old.get("from", [])})
    return list(merged.values())


def extract(ctx):
    recs = list(_workflow_records(ctx))
    by_id = {r["id"]: r for r in recs}
    for alias, (base, rel, line) in _clones(ctx).items():
        rec, src = by_id.get(alias), by_id.get(base)
        if src and rec is None:
            rec = dict(src, id=alias, parts=[])
            recs.append(rec)
            by_id[alias] = rec
        if rec and src:
            for field in ("entity", "entity_attribute", "start_step", "label"):
                rec[field] = rec[field] or src[field]
            rec["steps"] = src["steps"] + [x for x in rec["steps"] if x not in src["steps"]]
            rec["transitions"] = _merge_transitions(src["transitions"], rec["transitions"])
            rec.update(clone_of=base, file=rel, line=line, keys=[k for k in rec["keys"] + [base, src["entity"]] if k])
            rec["text"] = _wf_text(rec) + " clone_of=%s" % base
    trans = _translations(ctx.root)
    for rec in recs:
        rec["label_text"] = _label_text(rec, trans)
        rec["text"] += ' label="%s"' % rec["label_text"] if rec["label_text"] else ""
    return recs


def _workflow_records(ctx):
    for name, (node, rel), overlays, defs in _merge(_entries(ctx, "workflows.yml", "workflows"), "entity"):
        entity = scalar(node.child("entity")) or _first(defs, "entity")
        steps, trans = _transitions(defs)
        groups = _union(defs, "exclusive_active_groups")
        dgs = _union(defs, "datagrids")
        rec = {
            "id": name,
            "kind": "workflow",
            "entity": entity,
            "entity_attribute": _first(defs, "entity_attribute"),
            "start_step": _first(defs, "start_step"),
            "label": _first(defs, "label"),
            "applications": _union(defs, "applications"),
            "datagrids": dgs,
            "exclusive_active_groups": groups,
            "exclusive_record_groups": _union(defs, "exclusive_record_groups"),
            "disable_operations": [k.key for d, _ in defs for k in _kids(d, "disable_operations")],
            "steps": steps,
            "transitions": trans,
            "bundle": _bundle(rel),
            "parts": [_where(r, n.line) for n, r in overlays],
            "file": rel,
            "line": node.line,
            "keys": [k for k in [entity] + groups if k],
        }
        rec["text"] = _wf_text(rec)
        yield rec


def _kids(node, prop):
    child = node.child(prop)
    return child.kids if child else []


def _first(defs, prop):
    return next((v for v in (scalar(d.child(prop)) for d, _ in defs) if v), None)


def _wf_text(rec):
    parts = ["workflow", "entity=%s" % rec["entity"]] if rec["entity"] else ["workflow"]
    parts.append("steps=%s" % _short(rec["steps"], 6))
    parts.append("transitions=%d" % len(rec["transitions"]))
    if rec["exclusive_active_groups"]:
        parts.append("groups=%s" % _short(rec["exclusive_active_groups"]))
    return " ".join(parts)
