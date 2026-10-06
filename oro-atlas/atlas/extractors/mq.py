"""Message queue topics (name, class) and the processors subscribed to them."""
import re

from ..common import read_text

NAME = "mq"

TOPIC_TAG = "oro_message_queue.topic"
PROCESSOR_TAG = "oro_message_queue.client.message_processor"

_NS = re.compile(r"^\s*namespace\s+([\w\\]+)\s*;", re.M)
_USE = re.compile(r"^\s*use\s+([\w\\]+)(?:\s+as\s+(\w+))?\s*;", re.M)
_EXTENDS = re.compile(r"\bclass\s+\w+\s+extends\s+([\w\\]+)")
_CONST = re.compile(r"\bconst\s+(?:\w+\s+)?(\w+)\s*=\s*(?:'([^']*)'|\"([^\"]*)\")")
_STR = r"'([^'\\]*)'|\"([^\"\\]*)\""
_REF = re.compile(r"([\w\\]+)::(getName\(\)|\w+)")
_TOKEN = re.compile(r"([\w\\]+)::(getName\(\)|\w+)|" + _STR + r"|([\[\]])")


class PhpFile:
    """Just enough PHP source parsing for namespace, imports, parent and constants."""

    def __init__(self, text):
        self.text = text
        m = _NS.search(text)
        self.namespace = m.group(1) if m else ""
        self.uses = {}
        for full, alias in _USE.findall(text):
            self.uses[alias or full.rsplit("\\", 1)[-1]] = full
        m = _EXTENDS.search(text)
        self.parent = self.qualify(m.group(1)) if m else None
        self.consts = {k: a or b for k, a, b in _CONST.findall(text)}

    def qualify(self, name):
        head = name.split("\\", 1)[0]
        if name.startswith("\\"):
            full = name[1:]
        elif head in self.uses:
            full = self.uses[head] + name[len(head):]
        else:
            full = (self.namespace + "\\" if self.namespace else "") + name
        return full

    def method_body(self, name):
        m = re.search(r"function\s+" + name + r"\s*\([^)]*\)\s*(?::\s*[\w\\?|]+)?\s*\{", self.text)
        body = None
        if m:
            depth, i = 1, m.end()
            while i < len(self.text) and depth:
                depth += {"{": 1, "}": -1}.get(self.text[i], 0)
                i += 1
            body = self.text[m.end():i - 1]
        return body


class Resolver:
    def __init__(self, ctx):
        self.ctx = ctx
        self._files = {}

    def parse(self, fqcn):
        if fqcn not in self._files:
            path = self.ctx.locator.file_of(fqcn)
            text = read_text(path) if path else ""
            self._files[fqcn] = PhpFile(text) if text else None
        return self._files[fqcn]

    def chain(self, fqcn):
        """The class followed by its ancestors, stopping at unresolvable parents."""
        seen, cur = [], fqcn
        while cur and cur not in seen and self.parse(cur):
            seen.append(cur)
            cur = self.parse(cur).parent
        return seen

    def const(self, fqcn, name):
        found = None
        for cls in self.chain(fqcn):
            found = self.parse(cls).consts.get(name)
            if found is not None:
                break
        return found

    def method(self, fqcn, name):
        """First (PhpFile, body) defining `name` in the class or an ancestor."""
        hit = (None, None)
        for cls in self.chain(fqcn):
            body = self.parse(cls).method_body(name)
            if body is not None:
                hit = (self.parse(cls), body)
                break
        return hit

    def literal_return(self, fqcn, method):
        """Return value of a method that just returns a string or constant."""
        pf, body = self.method(fqcn, method)
        value = None
        if body is not None:
            m = re.search(r"return\s+(?:" + _STR + r"|(?:self|static)::(\w+)|([\w\\]+)::(\w+))\s*;", body)
            if m:
                value = self._return_value(fqcn, pf, m)
        return value

    def _return_value(self, fqcn, pf, m):
        a, b, own, cls, name = m.groups()
        value = a or b
        if own:
            value = self.const(fqcn, own)
        elif cls:
            value = self.const(pf.qualify(cls), name)
        return value

    def topic_name(self, fqcn):
        return self.literal_return(fqcn, "getName")

    def subscribed(self, fqcn):
        """Topic names a processor subscribes to; unresolved refs are reported separately."""
        pf, body = self.method(fqcn, "getSubscribedTopics")
        names, unresolved = [], []
        if body is not None:
            body = re.sub(r"//[^\n]*|#(?!\[)[^\n]*|/\*.*?\*/", "", body, flags=re.S)
            expr = re.search(r"return\s+(.*?);", body, re.S)
            names, unresolved = self._scan(pf, fqcn, expr.group(1) if expr else "")
        return names, unresolved

    def _scan(self, pf, fqcn, expr):
        names, unresolved, depth = [], [], 0
        for m in _TOKEN.finditer(expr):
            cls, member, a, b, bracket = m.groups()
            if bracket:
                depth += 1 if bracket == "[" else -1
            elif cls and member == "class":
                continue
            elif cls and depth <= 1:
                value = self._ref(pf, fqcn, cls, member)
                (names if value else unresolved).append(value or m.group(0))
            elif depth <= 1 and (a or b):
                names.append(a or b)
        return names, unresolved

    def _ref(self, pf, fqcn, cls, member):
        target = fqcn if cls in ("self", "static") else pf.qualify(cls)
        return self.topic_name(target) if member == "getName()" else self.const(target, member)


def _locate(ctx, cls):
    rel, line = ctx.locator.locate(cls) if cls else (None, None)
    return rel, line


def _processor_record(ctx, res, sid, d):
    cls = d.get("class") or ""
    names, unresolved = res.subscribed(cls)
    tags = [t for t in d.get("tags", []) if t["name"] == PROCESSOR_TAG]
    params = {}
    for t in tags:
        params.update(t.get("parameters") or {})
    names += [t["parameters"]["topicName"] for t in tags if (t.get("parameters") or {}).get("topicName")]
    rel, line = _locate(ctx, cls)
    return {
        "id": sid, "kind": "processor", "class": cls, "topics": sorted(set(names)),
        "unresolved_topics": unresolved, "tag_params": params, "file": rel, "line": line,
    }


def _topic_record(ctx, res, sid, d):
    cls = d.get("class") or ""
    desc = res.literal_return(cls, "getDescription")
    rel, line = _locate(ctx, cls)
    return {
        "id": res.topic_name(cls) or cls, "kind": "topic", "class": cls, "service": sid,
        "description": desc, "name_resolved": bool(res.topic_name(cls)), "file": rel, "line": line,
    }


def _link(topics, processors):
    by_topic = {}
    for p in processors:
        for t in p["topics"]:
            by_topic.setdefault(t, []).append(p)
    for t in topics.values():
        t["processors"] = [
            {"service": p["id"], "class": p["class"], "file": p["file"], "line": p["line"]}
            for p in sorted(by_topic.get(t["id"], []), key=lambda x: x["id"])
        ]
    return by_topic


def snake_keys(*names):
    """snake_case forms of CamelCase class names and dotted topic names, so `product_fallback` matches."""
    shorts = [n.rsplit("\\", 1)[-1] for n in names if n]
    snakes = [re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", s).lower() for s in shorts]
    return sorted({k for k in snakes + [n.replace(".", "_") for n in names if n and "." in n] if k not in names})


def _topic_text(t):
    procs = ", ".join(p["class"].rsplit("\\", 1)[-1] for p in t["processors"][:3]) or "no processor"
    more = len(t["processors"]) - 3
    cls = t["class"].rsplit("\\", 1)[-1]
    return "topic %s%s -> %s%s" % (
        cls, " - " + t["description"] if t["description"] else "", procs, " (+%d)" % more if more > 0 else ""
    )


def _processor_text(p):
    shown = ", ".join(p["topics"][:3]) or "(topics not statically resolvable)"
    return "processor %s subscribes %s%s" % (
        p["class"].rsplit("\\", 1)[-1], shown, " (+%d)" % (len(p["topics"]) - 3) if len(p["topics"]) > 3 else ""
    )


def extract(ctx):
    defs = ctx.container()["definitions"]
    res = Resolver(ctx)
    tagged = lambda tag: sorted(  # noqa: E731
        (sid, d) for sid, d in defs.items() if any(t["name"] == tag for t in d.get("tags", []))
    )
    topics = {}
    for sid, d in tagged(TOPIC_TAG):
        rec = _topic_record(ctx, res, sid, d)
        topics.setdefault(rec["id"], rec)
    processors = [_processor_record(ctx, res, sid, d) for sid, d in tagged(PROCESSOR_TAG)]
    _link(topics, processors)
    for t in topics.values():
        t["keys"] = [k for k in [t["class"], t["service"]] if k] + snake_keys(t["class"], t["id"])
        t["text"] = _topic_text(t)
        yield t
    for p in processors:
        p["keys"] = [p["class"]] + p["topics"] + snake_keys(p["class"], *p["topics"])
        p["text"] = _processor_text(p)
        yield p
