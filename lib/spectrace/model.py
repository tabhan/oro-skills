"""Spec files (spec/*.md with an `id` front-matter key) and the AC tags carried by tests."""
import os
import re

AC_HEAD = re.compile(r"^(#{2,4})\s+AC-(\d+)\b[:\s-]*(.*)$")
HEAD = re.compile(r"^(#{1,6})\s+(.*)$")
RETIRED_HEAD = re.compile(r"^(?:\d+\.\s*)?retired\b", re.I)
LAYER = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?Layer:?(?:\*\*)?:?\s*(e2e|functional)\s*$", re.I)
TAG = re.compile(r"spec:([A-Za-z0-9_-]+):AC-(\d+)")
TEST_EXT = (".feature", ".ts", ".js", ".php")


class Ac:
    def __init__(self, spec, num, title, retired):
        self.spec, self.num, self.title, self.retired = spec, num, title, retired
        self.layer, self.has_gwt, self.body = None, False, []

    @property
    def key(self):
        return "%s:AC-%s" % (self.spec, self.num)


class Spec:
    def __init__(self, path, meta):
        self.path, self.meta, self.acs, self.errors = path, meta, [], []
        self.id = meta.get("id", "")
        self.retired = meta.get("status", "").lower() == "retired"


def front_matter(text):
    meta = {}
    lines = text.splitlines()
    if lines[:1] == ["---"]:
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip("'\"")
    return meta


def parse_spec(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    spec = Spec(path, front_matter(text))
    retired_level, cur = None, None
    for line in text.splitlines():
        m = HEAD.match(line)
        if m:
            level = len(m.group(1))
            if retired_level is not None and level <= retired_level:
                retired_level = None
            if retired_level is None and RETIRED_HEAD.match(m.group(2)):
                retired_level = level
            am = AC_HEAD.match(line)
            cur = None
            if am:
                cur = Ac(spec.id, am.group(2), am.group(3).strip(), spec.retired or retired_level is not None)
                spec.acs.append(cur)
            continue
        if cur is not None:
            cur.body.append(line)
            lm = LAYER.match(line)
            if lm:
                cur.layer = lm.group(1).lower()
    for ac in spec.acs:
        text_body = "\n".join(ac.body)
        ac.has_gwt = all(re.search(r"\b%s\b" % w, text_body, re.I) for w in ("given", "when", "then"))
    return spec


def load_specs(spec_dir, ids=None):
    specs = []
    for name in sorted(os.listdir(spec_dir)) if os.path.isdir(spec_dir) else []:
        if name.endswith(".md"):
            s = parse_spec(os.path.join(spec_dir, name))
            if s.id and (not ids or s.id in ids):
                specs.append(s)
    return specs


def kind_of(path):
    p = path.replace("\\", "/")
    if "/Tests/Unit/" in p or "\\Unit\\" in path:
        return "unit"
    if p.endswith(".feature") or "/Tests/E2e/" in p:
        return "e2e"
    if "/Tests/Functional/" in p or "\\Functional\\" in path:
        return "functional"
    return "other"


def scan_tags(tests_dir):
    """Return {(spec_id, ac_num): [(kind, relpath)]} for every tag found under tests_dir."""
    found = {}
    for base, dirs, files in os.walk(tests_dir):
        dirs[:] = [d for d in dirs if d not in ("vendor", "node_modules", ".git", "var")]
        for name in files:
            if not name.endswith(TEST_EXT):
                continue
            path = os.path.join(base, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            for m in TAG.finditer(text):
                found.setdefault((m.group(1), m.group(2)), set()).add((kind_of(path), os.path.relpath(path, tests_dir)))
    return {k: sorted(v) for k, v in found.items()}
