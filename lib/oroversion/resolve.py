"""Resolve which version-scoped units of guidance apply to a project's Oro version.

A unit is one of: a whole file (frontmatter `oro:` / script header `# oro:` / implicit `vN/` directory),
a section (`<!-- oro: "RANGE" -->` ... `<!-- /oro -->`), or a decision-table row (`Oro` column).
Absent range = DEFAULT_RANGE. See docs/VERSIONING.md.
"""
import os
import re

from .constraint import Constraint, ConstraintError, DEFAULT_RANGE, Version

# With an unknown project version only version-neutral ranges (no upper bound, lower bound <= this) stay active.
NEUTRAL_FLOOR = Version(7, 0, 0)

ACTIVE, INACTIVE = "active", "inactive"

_SCRIPT_EXT = (".sh", ".py", ".bash")
_TEXT_EXT = (".md", ".yml", ".yaml") + _SCRIPT_EXT
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".oro-ai"}
_FM = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.S)
_KV = re.compile(r"^\s*(oro|topic)\s*:\s*(.*?)\s*$")
_OPEN = re.compile(r"""<!--\s*oro:\s*(?:"([^"]*)"|'([^']*)')(?:\s+topic:\s*(\S+))?\s*-->""")
_CLOSE = re.compile(r"<!--\s*/oro\s*-->")
_HDR_OPEN = re.compile(r"""^\s*#\s*oro:\s*(?:"([^"]*)"|'([^']*)'|(\S.*?))\s*$""")
_HDR_TOPIC = re.compile(r"^\s*#\s*topic:\s*(\S+)\s*$")
_VDIR = re.compile(r"^v(\d+)$")


class Unit:
    def __init__(self, path, kind, start, end, range_text, topic=None):
        self.path, self.kind, self.start, self.end = path, kind, start, end
        self.range_text, self.topic = range_text, topic

    @property
    def effective_range(self):
        return self.range_text or DEFAULT_RANGE

    def ref(self):
        return self.path if self.kind == "file" else "%s:%d-%d" % (self.path, self.start, self.end)

    def as_dict(self, status):
        return {"path": self.path, "kind": self.kind, "lines": [self.start, self.end], "oro": self.effective_range,
                "topic": self.topic, "status": status}


def _unquote(value):
    value = value.strip()
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'" else value


def status(range_text, version):
    """Classify a range for `version` (a Version, or None when the project version is unknown)."""
    c = Constraint(range_text)
    if version is not None:
        return ACTIVE if c.matches(version) else INACTIVE
    return ACTIVE if _is_neutral(c) else INACTIVE


def _is_neutral(constraint):
    return any(hi is None and (lo is None or lo <= NEUTRAL_FLOOR) for lo, _, hi, _ in constraint.intervals())


def _split_row(line):
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def _file_range(path, text):
    """(range, topic) declared for the whole file, or implicit from a `references/vN/` directory."""
    rng = topic = None
    if path.endswith(".md"):
        m = _FM.match(text)
        for line in (m.group(1).splitlines() if m else []):
            kv = _KV.match(line)
            if kv and kv.group(1) == "oro":
                rng = _unquote(kv.group(2))
            elif kv:
                topic = _unquote(kv.group(2))
    else:
        for line in text.splitlines()[:15]:
            h = _HDR_OPEN.match(line)
            if h and rng is None:
                rng = h.group(1) or h.group(2) or h.group(3)
            t = _HDR_TOPIC.match(line)
            if t:
                topic = t.group(1)
    if rng is None:
        for part in os.path.dirname(path).split(os.sep):
            v = _VDIR.match(part)
            if v:
                rng = "^%s.0" % v.group(1)
    return rng, topic


def scan_file(path, warnings=None):
    """All units in one file: the file itself first, then sections and table rows; marker problems go to `warnings`."""
    warnings = warnings if warnings is not None else []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return []
    rng, topic = _file_range(path, text)
    lines = text.splitlines()
    units = [Unit(path, "file", 1, max(len(lines), 1), rng, topic)]
    if not path.endswith(".md"):
        return units
    open_at = None
    col = tcol = None
    for i, line in enumerate(lines, 1):
        m = _OPEN.search(line)
        if m:
            if open_at:
                warnings.append("%s:%d: nested oro section (opened at line %d); sections cannot nest" % (path, i, open_at[0]))
                units.append(Unit(path, "section", open_at[0], i - 1, open_at[1], open_at[2]))
            open_at = (i, m.group(1) if m.group(1) is not None else m.group(2), m.group(3))
        elif _CLOSE.search(line):
            if open_at:
                units.append(Unit(path, "section", open_at[0], i, open_at[1], open_at[2]))
            else:
                warnings.append("%s:%d: <!-- /oro --> without an opening marker" % (path, i))
            open_at = None
        if line.lstrip().startswith("|"):
            cells = _split_row(line)
            lowered = [c.lower() for c in cells]
            if col is None and "oro" in lowered:
                col, tcol = lowered.index("oro"), lowered.index("topic") if "topic" in lowered else None
            elif col is not None and not re.match(r"^\|?[\s:|-]+\|?$", line.strip()):
                value = cells[col] if col < len(cells) else ""
                tv = cells[tcol] if tcol is not None and tcol < len(cells) else None
                units.append(Unit(path, "row", i, i, _unquote(value.strip("`")).replace("\\|", "|") or None, tv or None))
        else:
            col = tcol = None
    if open_at:
        warnings.append("%s:%d: unclosed oro section; it runs to end of file" % (path, open_at[0]))
        units.append(Unit(path, "section", open_at[0], len(lines), open_at[1], open_at[2]))
    return units


def walk(root, exts=_TEXT_EXT, skip_tests=False):
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not (skip_tests and d in ("tests", "fixtures")))
        for name in sorted(files):
            if name.endswith(exts):
                yield os.path.join(base, name)


def resolve(target, version, skip_tests=False, warnings=None):
    """[(Unit, status)] for a file or a directory tree. A unit inside an inactive file is inactive."""
    paths = [target] if os.path.isfile(target) else list(walk(target, skip_tests=skip_tests))
    out = []
    for p in paths:
        file_status = ACTIVE
        for u in scan_file(p, warnings):
            try:
                s = status(u.range_text, version)
            except ConstraintError as exc:
                raise ConstraintError("%s: %s" % (u.ref(), exc))
            if u.kind == "file":
                file_status = s
            elif file_status == INACTIVE:
                s = INACTIVE
            out.append((u, s))
    return out


def find_topic(topic, root, version):
    return [(u, s) for u, s in resolve(root, version, skip_tests=True) if u.topic == topic]


def active_files(target, version, warnings=None):
    """File paths that apply, each with the line spans of its inactive sections/rows to skip."""
    files = {}
    for u, s in resolve(target, version, warnings=warnings):
        if u.kind == "file":
            if s != INACTIVE:
                files[u.path] = []
        elif s == INACTIVE and u.path in files:
            files[u.path].append((u.start, u.end))
    return files


# --- hook-check registry (oro-atlas/hooks/checks.yml) -------------------------------------------------

def load_registry(path):
    """Parse the `checks:` list of flat maps (id, severity, oro, ...); minimal YAML, no external deps."""
    checks, cur = {}, None
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return checks
    for line in lines:
        line = line.split(" #")[0].rstrip()
        m = re.match(r"^\s*-\s+(\w+):\s*(.*)$", line)
        if m:
            cur = {m.group(1): _unquote(m.group(2))}
            if m.group(1) == "id":
                checks[cur["id"]] = cur
            continue
        m = re.match(r"^\s+(\w+):\s*(.*)$", line)
        if m and cur is not None:
            cur[m.group(1)] = _unquote(m.group(2))
            if m.group(1) == "id":
                checks[cur["id"]] = cur
    return checks


def check_decision(registry, check_id, version, default_severity="deny"):
    """Decide whether a hook check runs and at what severity. Never blocks on unknown versions."""
    entry = registry.get(check_id, {})
    unknown = version is None
    severity = entry.get("severity", default_severity)
    s = status(entry.get("oro"), version)
    reason = "check %s: oro %s, project %s" % (check_id, Constraint(entry.get("oro")).text, version or "unknown")
    run = s != INACTIVE
    if not run:
        reason += " -> skipped (out of range)"
    elif unknown and severity == "deny":
        severity, reason = "warn", reason + " -> deny downgraded to warn (version unknown)"
    return {"run": run, "severity": severity if run else None, "advisory": unknown, "reason": reason}
