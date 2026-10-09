"""Cross-shard rollup for one entity: grids, operations, repository, Doctrine listeners, same-bundle MQ topics."""
import os
import re

from . import store
from .common import MissingShard

CAP = 5
ENTITY_KINDS = ("Entity", "MappedSuperclass")
_BUNDLE_RE = re.compile(r"^(\w+\\(?:Bundle\\)?\w+Bundle)\\")


def bundle_of(fqcn):
    m = _BUNDLE_RE.match(fqcn or "")
    return m.group(1) if m else None


def _records(out_dir, shard):
    try:
        return list(store.read_shard(out_dir, shard))
    except MissingShard:
        return []


def _short(fqcn):
    return (fqcn or "").rsplit("\\", 1)[-1]


def _listener_line(rec):
    return "%s %s::%s%s" % (rec["event"], _short(rec["class"]), rec["method"], " " + rec["file"] + ":" + str(rec["line"]) if rec.get("file") else "")


FLUSH_EVENTS = ("preFlush", "onFlush", "postFlush")


def _references(root, rel, fqcn):
    """Cheap static check: the class source imports the entity or names it with ::class."""
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return False
    short = re.escape(_short(fqcn))
    return bool(re.search(r"^use\s+\\?%s(?:\s+as\s+\w+)?;" % re.escape(fqcn), text, re.M)
                or re.search(r"\\?%s::class\b" % re.escape(fqcn), text)
                or (re.search(r"\b%s::class\b" % short, text) and re.search(r"^use\s+\\?%s;" % re.escape(fqcn), text, re.M)))


def flush_listeners(out_dir, fqcn):
    """Global flush listeners that filter by entity inside; src first, vendor only when they reference it too."""
    root = os.path.dirname(os.path.dirname(out_dir))
    seen, found = set(), []
    cands = [e for e in _records(out_dir, "events") if e.get("kind") == "doctrine_listener" and not e.get("entity")
             and e.get("event") in FLUSH_EVENTS and e.get("file")]
    for e in sorted(cands, key=lambda e: not e["file"].startswith("src/")):
        if e["class"] not in seen and _references(root, e["file"], fqcn):
            seen.add(e["class"])
            found.append("%s::%s %s:%s" % (_short(e["class"]), e["method"], e["file"], e.get("line")))
    return found


def build(out_dir, ent):
    """{section: [str]} for an entity record; empty sections are omitted."""
    fqcn, table = ent["id"], ent.get("table")
    grids = [g for g in _records(out_dir, "grids") if g.get("kind") == "grid" and g.get("entity") in (fqcn, table)]
    grid_ids = {g["id"] for g in grids}
    ops = [o for o in _records(out_dir, "operations")
           if o.get("kind") == "operation" and (fqcn in (o.get("entities") or []) or grid_ids & set(o.get("datagrids") or []))]
    listeners = [e for e in _records(out_dir, "events") if e.get("kind") == "doctrine_listener" and e.get("entity") == fqcn]
    bundle = bundle_of(fqcn)
    topics = [t["id"] for t in _records(out_dir, "mq") if t.get("kind") == "topic" and bundle and bundle_of(t.get("class")) == bundle]
    repo = []
    if ent.get("repository"):
        repo.append("repository " + ent["repository"])
    if ent.get("repository_override"):
        repo.append("override %s (%s)" % (ent["repository_override"], ent.get("extend_override_file") or "?"))
    sections = {
        "repository": repo,
        "grids": ["%s %s:%s" % (g["id"], g.get("file"), g.get("line")) for g in grids],
        "operations": ["%s %s:%s" % (o["id"], o.get("file"), o.get("line")) for o in ops],
        "doctrine": [_listener_line(e) for e in listeners],
        "flush listeners (references entity)": flush_listeners(out_dir, fqcn),
        "mq (same bundle)": topics,
    }
    return {k: v for k, v in sections.items() if v}


def render(sections, out):
    for name, items in sections.items():
        extra = len(items) - CAP
        out.write("    %s: %s%s\n" % (name, "; ".join(items[:CAP]) if name != "repository" else "; ".join(items),
                                    " (+%d more)" % extra if extra > 0 and name != "repository" else ""))
