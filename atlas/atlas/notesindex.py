"""Project notes (.oro-ai/notes/<slug>.md): parsing, linting, anchor resolution and the query API.

Pure functions over plain dicts so the build extractor, the CLI and the O7 hooks share one implementation.
Format spec: NOTES.md.
"""
import fnmatch
import glob
import os
import re
import sys

NOTES_DIR = os.path.join(".oro-ai", "notes")
KINDS = ("gotcha", "decision", "recipe")
SURFACES = ("always", "anchored")
ANCHOR_TYPES = ("class", "service", "entity", "workflow", "bundle", "path")
ALWAYS_CAP = 40
BODY_MAX = 2000
NOTE_LINES_PER_QUERY = 5

_SECRET = re.compile(
    r"(?i)(?:\b(?:password|passwd|secret|token|cookie|api[_-]?key|session(?:id)?)\w*\s*=\s*\S+"
    r"|\b(?:password|passwd|secret|token|api[_-]?key)s?\s+(?:is|was)\s+\S+"
    r"|\b(?:password|passwd|secret|token|api[_-]?key)\w*\s*:\s*[A-Za-z0-9+/_\-.]{16,}\s*$"
    r"|\bbearer\s+[A-Za-z0-9._\-]{20,}|PHPSESSID=\S+)", re.M)
_SLASHES = re.compile(r"\\+")


class NoteError(ValueError):
    """A note that cannot be indexed; the message says why."""


def normalize(text):
    return _SLASHES.sub("\\\\", str(text).lower()).lstrip("\\")


def notes_dir(root):
    return os.path.join(root, NOTES_DIR)


def note_files(root):
    return sorted(glob.glob(os.path.join(notes_dir(root), "*.md")))


def fingerprint(root):
    """mtime+size stamp of the note files, or None when there are none (cheap enough per query)."""
    import hashlib
    h, seen = hashlib.sha256(), False
    for path in note_files(root):
        try:
            st = os.stat(path)
        except OSError:
            continue
        seen = True
        h.update(("%s\0%d\0%d\n" % (os.path.basename(path), st.st_mtime_ns, st.st_size)).encode())
    return h.hexdigest() if seen else None


def _split_flow(text):
    """Split a flow list body on commas outside quotes."""
    items, cur, quote = [], "", None
    for ch in text:
        if quote:
            cur += ch
            quote = None if ch == quote else quote
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch == ",":
            items.append(cur)
            cur = ""
        else:
            cur += ch
    items.append(cur)
    return [i.strip() for i in items if i.strip()]


def _unquote(value):
    value = value.strip()
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'" else value


def split_frontmatter(text):
    """(frontmatter dict, body); raises NoteError when the leading `---` block is absent or unterminated."""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        raise NoteError("missing frontmatter")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise NoteError("unterminated frontmatter")
    meta, key = {}, None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        top = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if item and key and isinstance(meta.get(key), list):
            meta[key].append(_unquote(item.group(1)))
        elif top and not line.startswith(" "):
            key, value = top.group(1), top.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                meta[key] = [_unquote(v) for v in _split_flow(value[1:-1])]
            elif value == "":
                meta[key] = []
            else:
                meta[key] = _unquote(value)
    return meta, "\n".join(lines[end + 1:]).strip()


def parse_anchor(raw):
    kind, sep, value = str(raw).partition(":")
    kind, value = kind.strip().lower(), value.strip()
    if not sep or kind not in ANCHOR_TYPES or not value:
        raise NoteError("bad anchor '%s' (types: %s)" % (raw, ", ".join(ANCHOR_TYPES)))
    return kind, value.lstrip("\\") if kind != "path" else value


def parse_note(slug, text, version_check=None):
    """Validated note dict (no anchor resolution); raises NoteError with the reason it is skipped."""
    meta, body = split_frontmatter(text)
    title = meta.get("title") if isinstance(meta.get("title"), str) else ""
    if not title:
        raise NoteError("missing title")
    if meta.get("kind") not in KINDS:
        raise NoteError("unknown kind '%s' (use %s)" % (meta.get("kind"), "|".join(KINDS)))
    if meta.get("surface") not in SURFACES:
        raise NoteError("surface must be %s" % "|".join(SURFACES))
    raw_anchors = meta.get("anchors") or []
    if isinstance(raw_anchors, str):
        raw_anchors = [raw_anchors]
    anchors = [dict(zip(("type", "value"), parse_anchor(a))) for a in raw_anchors]
    if meta["surface"] == "anchored" and not anchors:
        raise NoteError("surface: anchored needs anchors")
    oro = meta.get("oro") or None
    if oro and version_check:
        version_check(oro)
    if _SECRET.search(text):
        raise NoteError("looks like it contains a secret (password=/token/cookie); notes must not hold secrets")
    return {"id": slug, "keys": [slug], "title": title, "kind": meta["kind"], "declared": meta["surface"],
            "anchors": anchors, "oro": oro, "updated": str(meta.get("updated") or ""), "body": body[:BODY_MAX]}


def _constraint_check(text):
    lib = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    from oroversion.constraint import Constraint, ConstraintError
    try:
        Constraint(text)
    except ConstraintError as exc:
        raise NoteError("bad oro range '%s': %s" % (text, exc))


def read_notes(root):
    """([parsed notes], [(slug, reason)] skipped) for every .oro-ai/notes/*.md."""
    notes, skipped = [], []
    for path in note_files(root):
        slug = os.path.basename(path)[:-3]
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            note = parse_note(slug, text, _constraint_check)
            if not note["updated"]:
                note["updated"] = _mtime_date(path)
            notes.append(note)
        except NoteError as exc:
            skipped.append((slug, str(exc)))
    return notes, skipped


def _mtime_date(path):
    import datetime
    return datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()


# -- anchor resolution -------------------------------------------------------------------------------------------

def glob_regex(pattern):
    """`**` crosses directories, `*` and `?` do not."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile("^" + out + "$")


def _path_live(root, pattern):
    return any(os.path.isfile(p) for p in glob.glob(os.path.join(root, pattern), recursive=True))


def _bundle_dir(root, name):
    """Directory holding <name>.php under src/ (preferred) or vendor/, relative to root; None when absent."""
    found = None
    for top in ("src", "vendor"):
        for d, dirs, files in os.walk(os.path.join(root, top)):
            dirs[:] = [x for x in dirs if x not in ("Tests", "node_modules", "Resources", "Entity", "Controller")]
            if name + ".php" in files:
                found = os.path.relpath(d, root)
                break
        if found:
            break
    return found


class Resolver:
    """Resolves anchors against shard records (class/service/entity/workflow), the autoload map and the file tree."""

    def __init__(self, root, ids, locate=None):
        self.root, self.ids, self.locate = root, ids, locate
        self._bundles = {}

    def resolve(self, anchor):
        kind, value = anchor["type"], anchor["value"]
        out = dict(anchor, live=False)
        if kind == "path":
            out["live"] = _path_live(self.root, value)
        elif kind == "bundle":
            if value not in self._bundles:
                self._bundles[value] = _bundle_dir(self.root, value)
            out["live"] = bool(self._bundles[value])
            out["dir"] = self._bundles[value]
        else:
            pools = {"service": ("services",), "entity": ("entities",), "workflow": ("workflows",),
                     "class": ("services", "entities")}[kind]
            out["live"] = any(normalize(value) in self.ids.get(p, ()) for p in pools)
            if not out["live"] and kind in ("class", "entity") and self.locate:
                out["live"] = bool(self.locate(value)[0])
        return out


def resolve_note(note, resolver):
    """Effective surface: anchored notes whose anchors are all dead are demoted to always, flagged possibly_stale."""
    anchors = [resolver.resolve(a) for a in note["anchors"]]
    stale = note["declared"] == "anchored" and not any(a["live"] for a in anchors)
    rec = dict(note, anchors=anchors, surface="always" if stale or note["declared"] == "always" else "anchored",
               possibly_stale=stale, file=os.path.join(NOTES_DIR, note["id"] + ".md"), text=note["title"])
    return rec


# -- query API (used by the CLI and the O7 hooks) ----------------------------------------------------------------

def load(out_dir):
    """Records of the notes shard; [] when it is not built."""
    from . import store
    from .common import MissingShard
    try:
        return list(store.read_shard(out_dir, "notes"))
    except MissingShard:
        return []


def is_active(note, version):
    """False when the note's `oro:` range excludes `version` (a string, or None when unknown)."""
    rng = note.get("oro")
    active = True
    if rng:
        lib = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "lib")
        if lib not in sys.path:
            sys.path.insert(0, lib)
        from oroversion import parse_version
        from oroversion.resolve import ACTIVE, status
        try:
            active = status(rng, parse_version(version) if version else None) == ACTIVE
        except Exception:  # noqa: BLE001 - an unparsable stored version must not hide every note
            active = True
    return active


def active_notes(notes, version):
    return [n for n in notes if is_active(n, version)]


def by_recency(notes):
    return sorted(notes, key=lambda n: (n.get("updated", ""), n["id"]), reverse=True)


def always_notes(notes, version=None, cap=ALWAYS_CAP):
    """(notes to inject at SessionStart, number held back by the cap), newest first."""
    pool = by_recency([n for n in active_notes(notes, version) if n["surface"] == "always"])
    return pool[:cap], max(0, len(pool) - cap)


def _matches_hit(note, rec):
    keys = {normalize(rec.get("id", ""))} | {normalize(k) for k in rec.get("keys", [])}
    cls = rec.get("class")
    if cls:
        keys.add(normalize(cls))
    path = str(rec.get("file") or "")
    hit = False
    for a in note["anchors"]:
        if a["type"] == "path":
            hit = hit or bool(path and glob_regex(a["value"]).match(path))
        elif a["type"] == "bundle":
            hit = hit or bool(a.get("dir") and path.startswith(a["dir"] + "/"))
        else:
            hit = hit or normalize(a["value"]) in keys
    return hit


def anchored_for_hit(notes, rec, version=None):
    """Active anchored (not demoted) notes whose anchors match one atlas query hit."""
    return [n for n in active_notes(notes, version) if n["surface"] == "anchored" and _matches_hit(n, rec)]


def anchored_for_path(notes, relpath, version=None):
    """Active anchored notes that apply to a project-relative file path (path glob, bundle dir, or class file)."""
    relpath = relpath.lstrip("./") if relpath.startswith("./") else relpath
    return [n for n in active_notes(notes, version) if n["surface"] == "anchored"
            and _matches_hit(n, {"file": relpath})]


def search(notes, term, version=None, include_inactive=False):
    """Notes whose slug, title, kind, anchors or body contain every word of `term`; exact slug first."""
    words = [w.lower() for w in term.split()]
    pool = notes if include_inactive else active_notes(notes, version)

    def hay(n):
        return "\n".join([n["id"], n["title"], n["kind"], n.get("body", "")] +
                         ["%s:%s" % (a["type"], a["value"]) for a in n["anchors"]]).lower()
    hits = [n for n in pool if all(w in hay(n) for w in words)]
    return sorted(hits, key=lambda n: (n["id"] != term.strip().lower(), n["id"]))


def format_note(n, version=None):
    flags = []
    if n.get("possibly_stale"):
        flags.append("possibly stale")
    if not is_active(n, version):
        flags.append("inactive oro %s" % n["oro"])
    return "%s  [%s/%s] %s%s  %s" % (n["id"], n["kind"], n["surface"], n["title"],
                                     "  (%s)" % ", ".join(flags) if flags else "", n["file"])


def lint(root):
    """[(slug, reason)] for every note that would be skipped."""
    return read_notes(root)[1]
