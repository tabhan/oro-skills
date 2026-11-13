"""Static checks for version-scoped guidance (run by bin/oro-skills-lint in pre-commit and CI).

Violations: unparsable `oro:` ranges, malformed or unbalanced section markers, a non-default variant without a
`topic:`, overlapping ranges or gaps inside one topic, and version numbers in skill/agent descriptions.
"""
import os
import re

from .constraint import Constraint, ConstraintError, DEFAULT_RANGE
from . import resolve as R

_MARKER_ANY = re.compile(r"<!--\s*/?oro\b")
_DESC_VERSION = re.compile(r"\b[vV]?\d+\.\d+(?:\.\d+)?\b|\b[vV]\d+\b|\bOro(?:Commerce|Platform)?\s+\d+(?:\.[xX*])?\b|\b\d+\.[xX*]\b")
_LOW, _HIGH = (-1, 0, 0, 0), (10 ** 9, 0, 0, 0)
_SKIP = {"docs"}


def _rank(v):
    """0 for a real pre-release (alpha/beta/rc), 1 for the release itself (`-dev` only marks an exclusive bound)."""
    return 0 if v.pre and not (v.pre == "dev" and not v.pre_n) else 1


def _discrete(interval):
    """Half-open [lo, hi) over patch releases; a real pre-release lower bound starts before its release,
    so `>=8.0.0-rc1` overlaps `<8.0.0`."""
    lo, lo_inc, hi, hi_inc = interval
    lo_t = _LOW if lo is None else (lo.major, lo.minor, lo.patch, _rank(lo))
    hi_t = _HIGH if hi is None else (hi.major, hi.minor, hi.patch, _rank(hi))
    if lo is not None and not lo_inc:
        lo_t = (lo_t[0], lo_t[1], lo_t[2] + 1, 1)
    if hi is not None and hi_inc:
        hi_t = (hi_t[0], hi_t[1], hi_t[2] + 1, 1)
    return lo_t, hi_t


def _fmt(t):
    return "-inf" if t == _LOW else "+inf" if t == _HIGH else "%d.%d.%d" % t[:3] + ("-pre" if t[3] == 0 else "")


def _frontmatter_description(text):
    m = R._FM.match(text)
    if not m:
        return None, 0
    lines = m.group(1).splitlines()
    for i, line in enumerate(lines):
        d = re.match(r"^description:\s*(.*)$", line)
        if not d:
            continue
        value, rest = d.group(1).strip(), []
        for nxt in lines[i + 1:]:
            if nxt[:1] in (" ", "\t") or not nxt.strip():
                rest.append(nxt.strip())
            else:
                break
        body = " ".join(([] if value in (">", ">-", "|", "|-", "") else [value]) + rest)
        return body, i + 2
    return None, 0


def _registry_units(path):
    out = []
    for cid, entry in R.load_registry(path).items():
        out.append(R.Unit(path, "check", 1, 1, entry.get("oro"), entry.get("topic")))
        out[-1].label = cid
    return out


def lint(root, scan_roots=None):
    """Sorted 'path:line: message' violations (errors only)."""
    return lint_all(root, scan_roots)[0]


def lint_all(root, scan_roots=None):
    """(errors, warnings); both are repo-relative and sorted."""
    problems, units, warns = [], [], []
    paths = []
    for base in scan_roots or [root]:
        if os.path.isfile(base):
            paths.append(base)
            continue
        for p in R.walk(base, skip_tests=True):
            if not (set(os.path.relpath(p, root).split(os.sep)) & _SKIP):
                paths.append(p)
    for p in paths:
        warnings = []
        if os.path.basename(p) == "checks.yml":
            units += _registry_units(p)
        else:
            units += R.scan_file(p, warnings)
        problems += ["%s: %s" % (w.split(": ", 1)[0], w.split(": ", 1)[1]) for w in warnings]
        if p.endswith(".md"):
            with open(p, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            for n, line in enumerate(text.splitlines(), 1):
                if _MARKER_ANY.search(line) and not (R._OPEN.search(line) or R._CLOSE.search(line)):
                    problems.append('%s:%d: malformed oro marker (expected <!-- oro: "RANGE" [topic: id] --> or <!-- /oro -->)' % (p, n))
            if os.path.basename(p) == "SKILL.md" or os.path.basename(os.path.dirname(p)) == "agents":
                desc, line = _frontmatter_description(text)
                hit = _DESC_VERSION.search(desc or "")
                if hit:
                    problems.append("%s:%d: description mentions a version (%r); descriptions load globally and must stay version-neutral" % (p, line, hit.group(0)))
    groups = {}
    for u in units:
        explicit = u.range_text is not None
        if explicit:
            try:
                Constraint(u.range_text)
            except ConstraintError as exc:
                problems.append("%s: unparsable oro range: %s" % (_ref(u), exc))
                continue
        if explicit and Constraint(u.range_text).text != DEFAULT_RANGE and not u.topic:
            problems.append("%s: variant with oro %r has no topic: id" % (_ref(u), u.range_text))
        if u.topic:
            groups.setdefault(u.topic, []).append(u)
    for topic, members in sorted(groups.items()):
        if len(members) > 1:
            problems += _check_topic(topic, members)
        elif _has_upper_bound(members[0]):
            warns.append("%s: topic %s: content disappears from %s with no successor" % (_ref(members[0]), topic, _upper(members[0])))
    prefix = root.rstrip(os.sep) + os.sep
    return [sorted({x.replace(prefix, "") for x in xs}) for xs in (problems, warns)]


def _has_upper_bound(u):
    return u.range_text is not None and any(iv[2] is not None for iv in Constraint(u.range_text).intervals())


def _upper(u):
    return ", ".join(sorted({_fmt(_discrete(iv)[1]) for iv in Constraint(u.range_text).intervals() if iv[2] is not None}))


def _ref(u):
    return u.path + (":%d" % u.start if u.kind != "file" else "") + (" (check %s)" % u.label if u.kind == "check" else "")


def _check_topic(topic, members):
    out, spans = [], []
    for u in members:
        c = Constraint(u.range_text)
        if "!=" in c.text:
            out.append("%s: topic %s: '!=' cannot be checked for adjoining ranges; split into explicit ranges" % (_ref(u), topic))
            return out
        for iv in c.intervals():
            lo, hi = _discrete(iv)
            if lo >= hi:
                out.append("%s: topic %s: empty range %r" % (_ref(u), topic, c.text))
            else:
                spans.append((lo, hi, u))
    spans.sort(key=lambda s: (s[0], s[1]))
    reach, holder = None, None
    for lo, hi, u in spans:
        if reach is not None and lo < reach:
            out.append("%s: topic %s: range %r overlaps %r (%s)" % (_ref(u), topic, u.effective_range, holder.effective_range, _ref(holder)))
        elif reach is not None and lo > reach:
            out.append("%s: topic %s: gap between %s and %s before range %r" % (_ref(u), topic, _fmt(reach), _fmt(lo), u.effective_range))
        if reach is None or hi > reach:
            reach, holder = hi, u
    return out
