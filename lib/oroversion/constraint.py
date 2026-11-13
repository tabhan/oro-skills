"""Composer-style version constraints at full major.minor.patch granularity.

Grammar: alternatives joined by `||` or ` or `; each alternative is comparators joined by whitespace or commas.
Comparators: `>=` `>` `<=` `<` `=` `==` `!=`, `^X.Y[.Z]`, `~X.Y[.Z]`, wildcard `X.Y.*` / `X.*`, bare `X.Y.Z`.
A missing constraint means DEFAULT_RANGE.
"""
import re

DEFAULT_RANGE = ">=7.0.0"


class ConstraintError(ValueError):
    pass


_VERSION = re.compile(r"^v?(\d+)(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?(?:[-.]?(alpha|a|beta|b|RC|rc|dev|patch|pl|p)\.?(\d*))?$")
_PRE_ORDER = {"dev": 0, "alpha": 1, "a": 1, "beta": 2, "b": 2, "rc": 3, "RC": 3}


class Version:
    """Ordered release tuple; a pre-release sorts below the same release (8.0.0-beta < 8.0.0)."""

    __slots__ = ("major", "minor", "patch", "pre", "pre_n")

    def __init__(self, major, minor=0, patch=0, pre=None, pre_n=0):
        self.major, self.minor, self.patch, self.pre, self.pre_n = major, minor, patch, pre, pre_n

    def key(self):
        pre_rank = _PRE_ORDER.get(self.pre, 99) if self.pre else 99
        return (self.major, self.minor, self.patch, pre_rank, self.pre_n)

    def __eq__(self, other):
        return isinstance(other, Version) and self.key() == other.key()

    def __lt__(self, other):
        return self.key() < other.key()

    def __le__(self, other):
        return self.key() <= other.key()

    def __gt__(self, other):
        return self.key() > other.key()

    def __ge__(self, other):
        return self.key() >= other.key()

    def __hash__(self):
        return hash(self.key())

    def __str__(self):
        base = "%d.%d.%d" % (self.major, self.minor, self.patch)
        return "%s-%s%s" % (base, self.pre, self.pre_n or "") if self.pre else base

    __repr__ = __str__


def parse_version(text):
    """Parse a concrete version; raises ConstraintError on anything that is not a release/pre-release."""
    m = _VERSION.match(str(text).strip())
    if not m or m.group(4) in ("patch", "pl", "p"):
        raise ConstraintError("unparsable version %r" % (text,))
    major, minor, patch, pre, pre_n = m.groups()
    if "*" in (minor, patch) or "x" in (minor or "").lower() or "x" in (patch or "").lower():
        raise ConstraintError("wildcard not allowed in a version: %r" % (text,))
    return Version(int(major), int(minor or 0), int(patch or 0), pre, int(pre_n or 0))


def _parts(text):
    """Return (major, minor|None, patch|None, pre|None, pre_n) for partially specified versions such as `7.0`."""
    m = _VERSION.match(text.strip())
    if not m or m.group(4) in ("patch", "pl", "p"):
        raise ConstraintError("unparsable version %r" % (text,))
    nums = [None if g is None or g in ("x", "X", "*") else int(g) for g in m.groups()[:3]]
    return nums[0], nums[1], nums[2], m.group(4), int(m.group(5) or 0)


def _bump(major, minor, patch, level):
    """Exclusive upper bound incrementing the component at `level`; `-dev` keeps pre-releases of the bound out."""
    if level == 0:
        return Version(major + 1, 0, 0, "dev")
    if level == 1:
        return Version(major, minor + 1, 0, "dev")
    return Version(major, minor, patch + 1, "dev")


def _lower(major, minor, patch):
    """Inclusive lower bound of ^/~/wildcard ranges; an N.M.0 range admits that release's pre-releases."""
    return Version(major, minor, patch, "dev" if patch == 0 else None)


def _comparator(token):
    """Expand one comparator token into a list of (op, Version) bounds."""
    m = re.match(r"^(>=|<=|==|!=|>|<|=|\^|~)?\s*(.+)$", token)
    if not m:
        raise ConstraintError("unparsable constraint %r" % (token,))
    op, rest = m.group(1) or "=", m.group(2)
    major, minor, patch, pre, pre_n = _parts(rest)
    if pre and (op in ("^", "~") or minor is None or patch is None):
        raise ConstraintError("pre-release needs a full version with a plain comparator: %r" % (token,))
    if op in ("^", "~"):
        lower = _lower(major, minor or 0, patch or 0)
        if op == "~":
            level = 1 if patch is not None else 0
            if minor is None:
                level = 0
            upper = _bump(major, minor or 0, patch or 0, level)
        else:
            if major > 0 or minor is None:
                upper = _bump(major, 0, 0, 0)
            elif minor > 0 or patch is None:
                upper = _bump(major, minor, 0, 1)
            else:
                upper = _bump(major, minor, patch, 2)
        return [(">=", lower), ("<", upper)]
    if op in ("=", "==") and (minor is None or patch is None):
        level = 0 if minor is None else 1
        return [(">=", _lower(major, minor or 0, 0)), ("<", _bump(major, minor or 0, 0, level))]
    if op == "!=" and (minor is None or patch is None):
        raise ConstraintError("!= needs a full version: %r" % (token,))
    bound = Version(major, minor or 0, patch or 0, pre, pre_n)
    if op == "<" and not pre:
        bound = Version(bound.major, bound.minor, bound.patch, "dev")  # `<8.0.0` excludes 8.0.0-beta
    return [("==" if op == "=" else op, bound)]


_OPS = {
    ">=": lambda v, b: v >= b,
    ">": lambda v, b: v > b,
    "<=": lambda v, b: v <= b,
    "<": lambda v, b: v < b,
    "==": lambda v, b: v == b,
    "!=": lambda v, b: v != b,
}


class Constraint:
    """OR of AND-groups of (op, Version) bounds."""

    def __init__(self, text=None):
        self.text = (text or DEFAULT_RANGE).strip() or DEFAULT_RANGE
        self.alternatives = [self._group(g) for g in re.split(r"\|\||\s+or\s+", self.text)]

    @staticmethod
    def _group(group):
        # `>= 7.0` (space after the operator) must stay one comparator.
        group = re.sub(r"(>=|<=|==|!=|>|<|=|\^|~)\s+", r"\1", group.strip())
        tokens = [t for t in re.split(r"[\s,]+", group) if t]
        if not tokens:
            raise ConstraintError("empty constraint alternative")
        bounds = []
        for token in tokens:
            bounds.extend(_comparator(token))
        return bounds

    def matches(self, version):
        v = version if isinstance(version, Version) else parse_version(version)
        return any(all(_OPS[op](v, bound) for op, bound in group) for group in self.alternatives)

    def intervals(self):
        """Each alternative as (low, low_inclusive, high, high_inclusive); None = unbounded. Used by lint/diff."""
        out = []
        for group in self.alternatives:
            lo, lo_inc, hi, hi_inc = None, True, None, True
            for op, b in group:
                if op in (">=", ">", "=="):
                    if lo is None or b > lo or (b == lo and op == ">"):
                        lo, lo_inc = b, op != ">"
                if op in ("<=", "<", "=="):
                    if hi is None or b < hi or (b == hi and op == "<"):
                        hi, hi_inc = b, op == "<=" or op == "=="
            out.append((lo, lo_inc, hi, hi_inc))
        return out

    def __str__(self):
        return self.text


def parse_constraint(text):
    return Constraint(text)
