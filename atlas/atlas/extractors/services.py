"""Service id -> class, aliases, decoration chain, tags, defining file."""
NAME = "services"
ORDER = 0

DECORATOR_TAG = "container.decorator"


def _alias_map(aliases):
    out = {}
    for alias, target in aliases.items():
        out.setdefault(target.get("service"), []).append(alias)
    return out


def _tag_summary(tags):
    names = sorted({t["name"] for t in tags if not t["name"].startswith("container.")})
    return names[:3], max(0, len(names) - 3)


def _decorations(defs):
    """Map decorated id -> decorator ids outermost first, plus decorator id -> (decorated id, inner id)."""
    tagged = {
        sid: (t.get("parameters", {}).get("id"), t.get("parameters", {}).get("inner"))
        for sid, d in defs.items()
        for t in d.get("tags", [])
        if t["name"] == DECORATOR_TAG
    }
    by_target = {}
    for sid, (target, _) in sorted(tagged.items()):
        by_target.setdefault(target, []).append(sid)
    return {target: _chain(ids, tagged) for target, ids in by_target.items()}, tagged


def _chain(ids, tagged):
    # Each decorator's inner is the next one down; the outermost is nobody's inner.
    inners = {tagged[i][1] for i in ids}
    head = next((i for i in ids if i not in inners), ids[0])
    chain = []
    while head in ids and head not in chain:
        chain.append(head)
        head = tagged[head][1]
    return chain + [i for i in ids if i not in chain]


def _original_of(target, chain, tagged, defs):
    """The inner service left behind by the innermost decorator (or the target id itself)."""
    inner = tagged[chain[-1]][1] if chain else None
    return inner if inner in defs and inner not in tagged else target


def _text(sid, rec):
    parts = ["class=%s" % rec["class"]] if rec["class"] else []
    if rec["decorates"]:
        parts.append("decorates=%s" % rec["decorates"])
    if rec["decorated_by"]:
        parts.append("decorated_by=%s" % ">".join(rec["decorated_by"]))
    shown, more = _tag_summary(rec["tags"])
    if shown:
        parts.append("tags=%s%s" % (",".join(shown), "(+%d)" % more if more else ""))
    return " ".join(parts)


def extract(ctx):
    data = ctx.container()
    defs = data["definitions"]
    by_target = _alias_map(data.get("aliases", {}))
    chains, tagged = _decorations(defs)
    originals = {_original_of(t, c, tagged, defs): t for t, c in chains.items()}
    for sid in sorted(defs):
        d = defs[sid]
        if sid.startswith(".") and not d.get("class"):
            continue
        cls = d.get("class") or ""
        rel, line = ctx.locator.locate(cls) if cls else (None, None)
        target, inner = tagged.get(sid, (None, None))
        public_id = originals.get(sid)
        chain = chains.get(target or public_id, [])
        rec = {
            "id": sid,
            "class": cls,
            "aliases": sorted(by_target.get(sid, [])),
            "parent": d.get("parent"),
            "decorates": target,
            "inner": inner,
            "decoration_chain": chain,
            "decorated_by": _outer_of(sid, chain) if target else (chain if public_id else []),
            "inner_class": (defs.get(inner) or {}).get("class") if inner else None,
            "tags": [{"name": t["name"], "attrs": t.get("parameters", {})} for t in d.get("tags", [])],
            "public": bool(d.get("public")),
            "abstract": bool(d.get("abstract")),
            "synthetic": bool(d.get("synthetic")),
            "file": rel,
            "line": line,
        }
        extra = [public_id if public_id != sid else None, rec["parent"]]
        rec["keys"] = list(dict.fromkeys(k for k in [cls] + rec["aliases"] + extra if k))
        rec["text"] = _text(sid, rec)
        yield rec


def _outer_of(sid, chain):
    return chain[: chain.index(sid)] if sid in chain else []
