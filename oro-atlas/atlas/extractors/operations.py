"""Operations and action_groups (actions.yml); YAML reading and merge helpers live in workflows.py."""
from .workflows import _bundle, _entries, _first, _kids, _merge, _short, _union, _where

NAME = "operations"
ORDER = 51


def _op_text(rec):
    parts = [rec["kind"]]
    for field in ("extends", "label"):
        if rec.get(field):
            parts.append("%s=%s" % (field, rec[field]))
    for field in ("applications", "entities", "routes", "datagrids", "exclude_datagrids"):
        if rec.get(field):
            parts.append("%s=%s" % (field, _short(rec[field])))
    return " ".join(parts)


def _build_op(kind, name, main, overlays, defs):
    node, rel = main
    rec = {
        "id": name,
        "kind": kind,
        "label": _first(defs, "label"),
        "extends": _first(defs, "extends"),
        "applications": _union(defs, "applications"),
        "entities": _union(defs, "entities"),
        "routes": _union(defs, "routes"),
        "datagrids": _union(defs, "datagrids"),
        "exclude_datagrids": _union(defs, "exclude_datagrids"),
        "for_all_entities": _first(defs, "for_all_entities"),
        "for_all_datagrids": _first(defs, "for_all_datagrids"),
        "acl_resource": _first(defs, "acl_resource"),
        "parameters": [k.key for k in _kids(node, "parameters")],
        "bundle": _bundle(rel),
        "parts": [_where(r, n.line) for n, r in overlays],
        "file": rel,
        "line": node.line,
    }
    rec["keys"] = [k for k in [rec["extends"]] + rec["entities"] if k]
    rec["text"] = _op_text(rec)
    return rec


def extract(ctx):
    for kind, section, primary in (("operation", "operations", "label"), ("action_group", "action_groups", "actions")):
        for name, main, overlays, defs in _merge(_entries(ctx, "actions.yml", section), primary):
            yield _build_op(kind, name, main, overlays, defs)
