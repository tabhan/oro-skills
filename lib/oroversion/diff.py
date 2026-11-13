"""Which units of guidance activate or deactivate when a project moves between two Oro versions."""
import os
import re

from . import resolve as R
from .lint import _registry_units

_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*$")
_SKIP = {"docs"}


def _units(root, version):
    out = {}
    for p in R.walk(root, skip_tests=True):
        if set(os.path.relpath(p, root).split(os.sep)) & _SKIP:
            continue
        if os.path.basename(p) == "checks.yml":
            found = [(u, R.status(u.range_text, version)) for u in _registry_units(p)]
        else:
            found = R.resolve(p, version)
        for u, s in found:
            out[(u.path, u.kind, u.start, getattr(u, "label", ""))] = (u, s)
    return out


def _title(u, lines_of):
    if u.kind == "check":
        return u.label
    lines = lines_of(u.path)
    if u.kind == "file" and not u.path.endswith(".md"):
        return os.path.basename(u.path)
    if u.kind == "file":
        m = R._FM.match("\n".join(lines))
        name = re.search(r"^name:\s*(.+)$", m.group(1), re.M) if m else None
        head = next((h.group(1) for h in map(_HEADING.match, lines) if h), None)
        return (name.group(1).strip() if name else head) or os.path.basename(u.path)
    if u.kind == "row":
        return re.split(r"(?<!\\)\|", lines[u.start - 1].strip().strip("|"))[0].strip()[:90]
    head = next((h.group(1) for h in (_HEADING.match(l) for l in reversed(lines[:u.start - 1])) if h), None)
    first = next((l.strip() for l in lines[u.start:u.end] if l.strip() and not R._CLOSE.search(l)), "")
    return (head + " > " if head else "") + first[:70]


def diff(root, v_from, v_to):
    """[{change, kind, topic, title, path, lines, oro}] for units whose status differs between the versions."""
    cache = {}

    def lines_of(path):
        if path not in cache:
            with open(path, encoding="utf-8", errors="replace") as fh:
                cache[path] = fh.read().splitlines()
        return cache[path]

    a, b = _units(root, v_from), _units(root, v_to)
    flipped_files = {k[0] for k, (u, s) in b.items() if u.kind == "file" and a.get(k, (u, s))[1] != s}
    rows = []
    for key, (u, s_to) in b.items():
        s_from = a.get(key, (u, s_to))[1]
        if s_from == s_to or (u.kind != "file" and u.path in flipped_files):
            continue
        rows.append({"change": "activates" if s_to == R.ACTIVE else "deactivates", "kind": u.kind, "topic": u.topic,
                     "title": _title(u, lines_of), "path": os.path.relpath(u.path, root),
                     "lines": [u.start, u.end], "oro": u.effective_range})
    return sorted(rows, key=lambda r: (r["change"], r["path"], r["lines"]))


def format_table(rows):
    if not rows:
        return "no guidance changes between these versions"
    head = ("change", "kind", "topic", "title", "path")
    body = [(r["change"], r["kind"], r["topic"] or "-", r["title"], r["path"] + ("" if r["kind"] == "file" else ":%d-%d" % tuple(r["lines"]))) for r in rows]
    widths = [max(len(str(x[i])) for x in [head] + body) for i in range(5)]
    return "\n".join("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)).rstrip() for row in [head] + body)
