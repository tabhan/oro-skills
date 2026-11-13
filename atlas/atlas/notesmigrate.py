"""Project auto-memory -> .oro-ai/notes migration: locate the memory dir, inventory it, apply a confirmed plan.

Shared by the O7 hooks (detection, write block) and `aaxis-oro memory inventory|apply`.
A memory is "global" (kept in place) only when its top-level frontmatter says `scope: global`.
"""
import json
import os
import re
import subprocess
import sys
import tarfile
import time

from . import notesindex
from .common import ensure_ignored

INDEX = "MEMORY.md"
_LINK = re.compile(r"\]\(([^)\s]+\.md)\)")
DENY = ("Project knowledge goes to .oro-ai/notes/%s.md (frontmatter: title, kind gotcha|decision|recipe, "
        "surface always|anchored, anchors: [class:..|service:..|entity:..|workflow:..|bundle:..|path:..]; "
        "format: atlas/NOTES.md). Auto-memory is only for cross-project preferences, which need `scope: global` "
        "in the frontmatter.")


def slugify_path(path):
    """Claude Code's project directory name for an absolute path."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(path))


def memory_dirs(*paths, home=None):
    home = home or os.path.expanduser("~")
    seen, out = set(), []
    for p in filter(None, paths):
        d = os.path.join(home, ".claude", "projects", slugify_path(p), "memory")
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def inside(path, directory):
    p, d = os.path.abspath(path), os.path.abspath(directory)
    return p == d or p.startswith(d + os.sep)


def is_global_text(text):
    try:
        meta, _ = notesindex.split_frontmatter(text)
    except notesindex.NoteError:
        return False
    return str(meta.get("scope", "")).strip().lower() == "global"


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def memory_files(mdir):
    try:
        return sorted(n for n in os.listdir(mdir) if n.endswith(".md") and n != INDEX
                      and os.path.isfile(os.path.join(mdir, n)))
    except OSError:
        return []


def unmigrated(mdir):
    """Memory files that are not marked `scope: global`."""
    return [n for n in memory_files(mdir) if not is_global_text(_read(os.path.join(mdir, n)))]


def index_link_targets(text):
    return _LINK.findall(text)


def write_allowed(tool_input, tool, mdir):
    """True when a Write/Edit into the memory dir only touches global content (see module doc)."""
    path = os.path.abspath(tool_input.get("file_path", ""))
    new = tool_input.get("content", "") if tool == "Write" else tool_input.get("new_string", "")
    if os.path.basename(path) == INDEX:
        # The index may only list global memories (a link to a missing or non-global file is project knowledge).
        return all(is_global_text(_read(os.path.join(mdir, t))) for t in index_link_targets(new))
    return is_global_text(new) or is_global_text(_read(path))


# -- inventory ---------------------------------------------------------------------------------------------------

def _describe(text):
    try:
        meta, body = notesindex.split_frontmatter(text)
    except notesindex.NoteError:
        meta, body = {}, text
    first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
    kind = meta.get("type") or next((m.split(":", 1)[1].strip() for m in text.splitlines()
                                     if re.match(r"^\s+type:\s", m)), "")
    return {"name": str(meta.get("name") or ""), "description": str(meta.get("description") or first)[:160],
            "type": kind}


def inventory(mdir):
    rows = []
    for n in unmigrated(mdir):
        text = _read(os.path.join(mdir, n))
        rows.append(dict(_describe(text), file=n, bytes=len(text.encode("utf-8"))))
    return rows


def write_inventory(root, mdir, rows):
    """Full table to .oro-ai/notes/migrate/inventory.{json,md} (self-ignored); returns the short summary lines."""
    out = os.path.join(notesindex.notes_dir(root), "migrate")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, ".gitignore"), "w") as fh:
        fh.write("*\n")
    with open(os.path.join(out, "inventory.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    md = ["| file | name | type | description | bytes |", "|---|---|---|---|---|"]
    md += ["| %s | %s | %s | %s | %d |" % (r["file"], r["name"], r["type"], r["description"].replace("|", "/"), r["bytes"]) for r in rows]
    with open(os.path.join(out, "inventory.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    types = {}
    for r in rows:
        types[r["type"] or "untyped"] = types.get(r["type"] or "untyped", 0) + 1
    return ["memory dir: %s" % mdir, "%d to classify; by type: %s" % (len(rows), ", ".join("%s %d" % kv for kv in sorted(types.items()))),
            "table: %s" % os.path.join(out, "inventory.md"), "json:  %s" % os.path.join(out, "inventory.json"),
            "read the table in chunks (sed -n 'A,Bp'); open a memory file only when its line is not enough"]


# -- apply -------------------------------------------------------------------------------------------------------

def note_text(item):
    anchors = item.get("anchors") or []
    head = ["---", "title: %s" % json.dumps(item["title"], ensure_ascii=False), "kind: %s" % item["kind"],
            "surface: %s" % item["surface"]]
    if anchors:
        head.append("anchors: [%s]" % ", ".join(json.dumps(a, ensure_ascii=False) if "," in a else a
                                                for a in anchors))
    head.append("updated: %s" % (item.get("updated") or time.strftime("%Y-%m-%d")))
    return "\n".join(head + ["---", item.get("body", "").strip(), ""])


def _mark_global(path):
    text = _read(path)
    if is_global_text(text):
        return False
    if text.startswith("---"):
        text = text.replace("---\n", "---\nscope: global\n", 1)
    else:
        text = "---\nscope: global\n---\n" + text
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return True


def _backup(mdir, names):
    dest = os.path.join(os.path.expanduser("~"), ".claude", "backups")
    os.makedirs(dest, exist_ok=True)
    stamp, seq = "%s-%d" % (time.strftime("%Y%m%d-%H%M%S"), os.getpid()), 0
    while True:  # exclusive create: a backup is never overwritten, even by a rerun in the same second
        path = os.path.join(dest, "memory-%s%s.tgz" % (stamp, "-%d" % seq if seq else ""))
        try:
            raw = open(path, "xb")
            break
        except FileExistsError:
            seq += 1
    with raw, tarfile.open(fileobj=raw, mode="w:gz") as tar:
        for n in names + [INDEX]:
            if os.path.exists(os.path.join(mdir, n)):
                tar.add(os.path.join(mdir, n), arcname=n)
    return path


def _rewrite_index(mdir):
    path = os.path.join(mdir, INDEX)
    text = _read(path)
    dropped = 0
    if text:
        keep = []
        for line in text.splitlines():
            targets = index_link_targets(line)
            if targets and not any(os.path.exists(os.path.join(mdir, t)) for t in targets):
                dropped += 1
            else:
                keep.append(line)
        if dropped:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(keep) + "\n")
    return dropped


def apply_plan(root, mdir, plan, build=True):
    """Execute a confirmed plan; returns (summary lines, exit code). Items: file, action note|delete|global, +note fields."""
    errors, written, deleted, marked, suggestions = [], 0, [], 0, []
    nd = notesindex.notes_dir(root)
    def changes(i):
        f = os.path.join(mdir, os.path.basename(str(i.get("file", ""))))
        a = i.get("action")
        return os.path.isfile(f) and (a in ("delete", "note") or (a == "global" and not is_global_text(_read(f))))
    touched = [os.path.basename(str(i["file"])) for i in plan.get("items", []) if changes(i)]
    backup = _backup(mdir, touched) if touched else None
    for item in plan.get("items", []):
        name = os.path.basename(str(item.get("file", "")))
        src = os.path.join(mdir, name)
        action = item.get("action")
        if item.get("suggest"):
            suggestions.append("%s: %s" % (name, item["suggest"]))
        if not os.path.isfile(src):
            continue  # already migrated: re-running a plan is a no-op
        if action == "global":
            marked += int(_mark_global(src))
        elif action == "delete":
            deleted.append(name)
        elif action == "note":
            err = _write_note(nd, item)
            if err:
                errors.append("%s: %s" % (name, err))
            else:
                written += 1
                deleted.append(name)
        else:
            errors.append("%s: unknown action %r" % (name, action))
    for n in deleted:
        os.remove(os.path.join(mdir, n))
    dropped = _rewrite_index(mdir)
    lines = ["notes written %d, memories deleted %d, marked global %d, index lines dropped %d, errors %d"
             % (written, len(deleted), marked, dropped, len(errors))]
    lines += ["error: " + e for e in errors[:10]]
    lines += ["suggest: " + s for s in suggestions[:10]]
    if backup:
        lines.append("backup: " + backup)
    if build and written:
        lines.append(_build_shard(root))
    return lines, (1 if errors else 0)


def _write_note(nd, item):
    err = None
    slug = str(item.get("slug", ""))
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", slug):
        return "bad slug %r (lowercase, digits, hyphens)" % slug
    try:
        text = note_text(item)
        notesindex.parse_note(slug, text)
        path = os.path.join(nd, slug + ".md")
        if os.path.exists(path) and _read(path) != text:
            err = "note %s already exists with different content" % slug
        elif not os.path.exists(path):
            ensure_ignored(nd)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
    except (notesindex.NoteError, KeyError) as exc:
        err = str(exc)
    return err


def _build_shard(root):
    cli = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "bin", "aaxis-oro")
    try:
        p = subprocess.run([sys.executable, cli, "atlas", "build", "--project", root, "--only", "notes"],
                           capture_output=True, text=True, timeout=300)
        out = "notes shard rebuilt" if p.returncode == 0 else "notes shard build failed (exit %d); run: %s atlas build --project %s --only notes" % (p.returncode, cli, root)
    except Exception as exc:  # noqa: BLE001
        out = "notes shard build failed: %s" % exc
    return out


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="aaxis-oro memory", description="Migrate project auto-memory to .oro-ai/notes")
    ap.add_argument("action", choices=("inventory", "apply"))
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--plan", help="apply: plan JSON file ('-' = stdin)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args(argv)
    from .common import find_project_root
    root = find_project_root(a.project)
    mdir = memory_dirs(root)[0]
    code = 0
    if a.action == "inventory":
        rows = inventory(mdir)
        if a.json:
            print(json.dumps(rows, ensure_ascii=False))
        elif not rows:
            print("nothing to migrate")
        else:
            print("\n".join(write_inventory(root, mdir, rows)))
    else:
        if not a.plan:
            ap.error("apply needs --plan FILE")
        plan = json.load(sys.stdin if a.plan == "-" else open(a.plan, encoding="utf-8"))
        lines, code = apply_plan(root, mdir, plan, build=not a.no_build)
        print("\n".join(lines))
    return code
