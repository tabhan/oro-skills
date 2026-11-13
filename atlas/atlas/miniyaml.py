"""Tiny indentation-based YAML reader that keeps line numbers (PyYAML is not stdlib).

Every extractor reads YAML through this module so a quoting/comment fix lands in all shards.
"""
import re

from .common import read_text, strip_comment


class LDict(dict):
    def __init__(self):
        super().__init__()
        self.lines = {}


class LList(list):
    def __init__(self):
        super().__init__()
        self.lines = []


# A plain key never starts with a flow opener, so `- { a: b }` stays a flow map, not key "{ a".
_KEY_RE = re.compile(r"""^("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^\s'"#\[{][^:]*?|[^\s'"#\[{])\s*:(?:\s+(.*))?$""")
_BLOCK_SCALAR_RE = re.compile(r"^[|>][+-]?\d*[+-]?$")
_OPENERS = {"[": "]", "{": "}"}


def _tokens(text):
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        body = strip_comment(raw).rstrip()
        if body.strip() and body.strip() not in ("---", "..."):
            out.append((len(body) - len(body.lstrip(" ")), body.strip(), n))
    return out


def unquote(s):
    s = (s or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].replace("''", "'") if s[0] == "'" else s[1:-1]
    return s


def split_flow(inner):
    """Split a flow collection body on top-level commas, honouring quotes and nesting."""
    parts, depth, quote, start = [], 0, None, 0
    for i, ch in enumerate(inner):
        if quote:
            quote = None if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(inner[start:i])
            start = i + 1
    parts.append(inner[start:])
    return [p.strip() for p in parts if p.strip()]


def _balanced(s):
    depth, quote = 0, None
    for ch in s:
        if quote:
            quote = None if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
    return depth <= 0


def _flow_map(inner):
    d = LDict()
    for part in split_flow(inner):
        m = _KEY_RE.match(part) or re.match(r"^(.+?)\s*:\s*(.*)$", part)
        key, val = (unquote(m.group(1)), m.group(2) or "") if m else (unquote(part), "")
        d[key] = scalar(val)
    return d


def scalar(s):
    """Typed value of an inline YAML scalar / flow collection."""
    s = (s or "").strip()
    low = s.lower()
    result = unquote(s)
    if s in ("", "~") or low == "null":
        result = None
    elif low in ("true", "false"):
        result = low == "true"
    elif s.startswith("[") and s.endswith("]"):
        result = [scalar(p) for p in split_flow(s[1:-1])]
    elif s.startswith("{") and s.endswith("}"):
        result = _flow_map(s[1:-1])
    elif re.fullmatch(r"-?\d+", s):
        result = int(s)
    return result


def _is_item(text):
    return text == "-" or text.startswith("- ")


class _Parser:
    def __init__(self, text):
        self.t = _tokens(text)
        self.i = 0

    def block(self, indent):
        tok = self.t[self.i]
        return self.list(tok[0]) if _is_item(tok[1]) else self.map(tok[0])

    def _skip_deeper(self, indent):
        while self.i < len(self.t) and self.t[self.i][0] > indent:
            self.i += 1

    def _flow_rest(self, rest, indent):
        """Join continuation lines of a multi-line `[...]` / `{...}` value."""
        while not _balanced(rest) and self.i < len(self.t) and (
            self.t[self.i][0] > indent or self.t[self.i][1][0] in "]}"
        ):
            rest += " " + self.t[self.i][1]
            self.i += 1
        return rest

    def _value(self, rest, indent):
        """Parse what follows `key:` or `-`; cursor sits on the token after the line."""
        rest = re.sub(r"^[&!]\S*\s*", "", rest)  # anchors/tags carry no value of their own
        nxt = self.t[self.i] if self.i < len(self.t) else None
        value = None
        if _BLOCK_SCALAR_RE.match(rest):
            self._skip_deeper(indent)
            value = ""
        elif rest:
            value = scalar(self._flow_rest(rest, indent) if rest[0] in _OPENERS else rest)
            # Continuation lines of a wrapped scalar must not be mistaken for sibling keys.
            self._skip_deeper(indent)
        elif nxt and (nxt[0] > indent or (nxt[0] == indent and _is_item(nxt[1]))):
            value = self.block(nxt[0])
        return value

    def map(self, indent):
        d = LDict()
        while self.i < len(self.t) and self.t[self.i][0] >= indent:
            _, text, line = self.t[self.i]
            m = _KEY_RE.match(text)
            if _is_item(text) and self.t[self.i][0] == indent:
                break
            self.i += 1
            # Stray over-indented or unparseable lines are skipped instead of ending the map.
            if m and self.t[self.i - 1][0] == indent:
                key = unquote(m.group(1))
                d.lines[key] = line
                d[key] = self._value((m.group(2) or "").strip(), indent)
        return d

    def list(self, indent):
        lst = LList()
        while self.i < len(self.t) and self.t[self.i][0] == indent and _is_item(self.t[self.i][1]):
            _, text, line = self.t[self.i]
            rest = text[1:].strip()
            lst.lines.append(line)
            if rest and _KEY_RE.match(rest):
                self.t[self.i] = (indent + (len(text) - len(rest)), rest, line)
                lst.append(self.map(self.t[self.i][0]))
            else:
                self.i += 1
                lst.append(self._value(rest, indent))
        return lst


def parse(text):
    p = _Parser(text)
    result = p.block(p.t[0][0]) if p.t else LDict()
    # A dedent below the first line's indent would otherwise drop the rest of the file.
    while p.i < len(p.t) and isinstance(result, LDict):
        start = p.i
        more = p.block(p.t[p.i][0])
        p.i += 1 if p.i == start else 0
        result.update(more if isinstance(more, LDict) else {})
        result.lines.update(getattr(more, "lines", None) if isinstance(more, LDict) else {})
    return result


def parse_file(path):
    return parse(read_text(path))


def line_map(tree, path=()):
    """{path tuple: line} for every block map key and list item under `tree` (flow values have none)."""
    out = {}
    lines = getattr(tree, "lines", None)
    items = tree.items() if isinstance(tree, LDict) else enumerate(tree) if isinstance(tree, LList) else ()
    for k, v in items:
        line = lines.get(k) if isinstance(lines, dict) else lines[k] if k < len(lines) else None
        out.update({path + (k,): line} if line else {})
        out.update(line_map(v, path + (k,)))
    return out
