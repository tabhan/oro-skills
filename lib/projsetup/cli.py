"""`aaxis-oro setup`: deterministic parts of /aaxis-oro:setup (status, idempotent sync, CLAUDE.md rule triage).

Never commits, never touches CLAUDE.md except through an explicitly confirmed `apply-rules` plan.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", ".."))
TEMPLATES = os.path.join(ROOT, "templates", "claude-project")
BIN = os.path.join(ROOT, "bin", "aaxis-oro")
BLOCKS = ("process-rules", "review-rules", "plan-rules")  # template file stem == block name
CONFIG = {"spec": {"id-pattern": "[A-Z][A-Z0-9-]*:AC-[0-9]+"}}
GITIGNORE = "*\n!.gitignore\n!config.json\n"
OWN_FILES = (".oro-ai/config.json", ".oro-ai/.gitignore")
MIGRATED, KEPT = "migrated-rules", "kept-rules"
BACKUP_REL = os.path.join(".oro-ai", "setup", "CLAUDE.original.md")
RULES_REL = os.path.join(".oro-ai", "setup", "rules.md")
RULES_JSON = os.path.join(".oro-ai", "setup", "rules.json")
APPLIED = os.path.join(".oro-ai", "setup", "applied")
NOTES_OPEN, NOTES_CLOSE = "<!-- claude-notes -->", "<!-- /claude-notes -->"
ASK = "aaxis-oro setup <status|sync|rules|apply-rules> [--project P] [--dry-run] [--json] [--plan FILE]\n"


class SetupError(Exception):
    pass


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def marker(name, end=False):
    return "<!-- aaxis-oro:%s:%s -->" % (name, "end" if end else "start")


def block_re(name):
    return re.compile(re.escape(marker(name)) + r".*?" + re.escape(marker(name, True)), re.S)


def sync_block(text, name, block):
    """Replace the named marked block in `text`, or append it. Raises on a half-present marker pair."""
    s, e = marker(name) in text, marker(name, True) in text
    if s != e:
        raise SetupError("%s: unbalanced %s markers" % ("CLAUDE_project.md", name))
    if s:
        return block_re(name).sub(lambda _: block, text, count=1)
    return text.rstrip("\n") + "\n\n" + block + "\n"


def template_block(name):
    text = read(os.path.join(TEMPLATES, name + ".md"))
    m = block_re(name).search(text or "")
    if not m:
        raise SetupError("template %s.md has no %s block" % (name, name))
    return m.group(0)


def git_tracked(root, rel):
    p = subprocess.run(["git", "-C", root, "ls-files", rel], capture_output=True, text=True)
    return [x for x in p.stdout.splitlines() if x] if p.returncode == 0 else []


def foundation_state(root):
    claude = read(os.path.join(root, "CLAUDE.md")) or ""
    base = os.path.isfile(os.path.join(root, "CLAUDE_base.md"))
    imports = "@CLAUDE_base.md" in claude
    if base and imports:
        return "done"
    return "partial (CLAUDE_base.md %s, CLAUDE.md import %s)" % ("present" if base else "missing", "present" if imports else "missing")


def claude_md_state(root):
    text = read(os.path.join(root, "CLAUDE.md"))
    if text is None:
        return "missing"
    return "imports" if "@CLAUDE_base.md" in text else "handwritten"


def triage_pending(root):
    return os.path.isfile(os.path.join(root, RULES_JSON)) and not os.path.isfile(os.path.join(root, APPLIED))


def tracked_plan(root):
    tracked = [t for t in git_tracked(root, ".oro-ai") if t not in OWN_FILES]
    return tracked


def plan_lines(n, have_gitignore):
    out = ["  WARNING: after this is committed and pulled, teammates' working copies lose these files (git deletes them);",
           "  tell them to back up or move .oro-ai/ first.",
           "  git rm -r --cached -q .oro-ai"]
    if not have_gitignore:
        out.append("  aaxis-oro setup sync")
    out.append("  git add .oro-ai/.gitignore .oro-ai/config.json")
    return out


def project_md_state(root):
    text = read(os.path.join(root, "CLAUDE_project.md"))
    if text is None:
        return "missing", False
    stale = [n for n in BLOCKS if template_block(n) not in text]
    return ("ok" if not stale else "blocks out of sync: " + ",".join(stale)), not stale


def sync(root, dry):
    """Idempotent writes of CLAUDE_project.md blocks, .oro-ai/config.json and .oro-ai/.gitignore. Returns (lines, code)."""
    lines, pm = [], os.path.join(root, "CLAUDE_project.md")
    text = read(pm)
    new = text if text is not None else read(os.path.join(TEMPLATES, "CLAUDE_project.md"))
    for name in BLOCKS:
        new = sync_block(new, name, template_block(name))
    state = "created" if text is None else ("updated" if new != text else "unchanged")
    if text is None and foundation_state(root) != "done":
        lines.append("note: foundation not run; run orocommerce-foundation:setup first so its Storefront themes and Area facts sections exist")
    if state != "unchanged" and not dry:
        write(pm, new)
    lines.append("CLAUDE_project.md: %s" % state)
    cfg = os.path.join(root, ".oro-ai", "config.json")
    if os.path.isfile(cfg):
        lines.append(".oro-ai/config.json: exists (left as is)")
    else:
        if not dry:
            write(cfg, json.dumps(CONFIG, indent=2) + "\n")
        lines.append(".oro-ai/config.json: created")
    gi = os.path.join(root, ".oro-ai", ".gitignore")
    tracked = tracked_plan(root)
    if os.path.isfile(gi):
        lines.append(".oro-ai/.gitignore: %s" % ("ok" if read(gi) == GITIGNORE else "exists (left as is)"))
    elif tracked:
        lines.append(".oro-ai/.gitignore: NOT created, %d files tracked under .oro-ai. Plan (run yourself):" % len(tracked))
        lines += plan_lines(len(tracked), False)
    else:
        if not dry:
            write(gi, GITIGNORE)
        lines.append(".oro-ai/.gitignore: created")
    from projsetup import precommit
    lines.append(precommit.install(root, dry))
    y = precommit.ensure_yamllint(root, dry)
    lines += [y] if y else []
    return lines, 0


def detect_version(root):
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    from oroversion.detect import detect
    r = detect(root, write_cache=False)
    return "%s (%s)" % (r.version, r.source_pkg) if r.known else "unknown (%s)" % (r.reason or "undetectable")


def atlas_line(root):
    p = subprocess.run([sys.executable, BIN, "atlas", "status", "--project", root], capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip()
    if p.returncode == 0:
        return "built", True
    if "STALE" not in out:
        return "missing; build: aaxis-oro atlas build --project %s" % root, False
    return "stale; refresh: aaxis-oro atlas build --project %s --incremental" % root, False


def memory_count(root):
    sys.path.insert(0, os.path.join(ROOT, "atlas"))
    from atlas import notesmigrate
    return len(notesmigrate.unmigrated(notesmigrate.memory_dirs(root)[0]))


def status(root, as_json):
    rows, todo = [], 0

    def add(key, value, ok):
        nonlocal todo
        rows.append((key, value, ok))
        todo += 0 if ok else 1

    f = foundation_state(root)
    add("foundation", f + ("" if f == "done" else "; run orocommerce-foundation:setup"), f == "done")
    cs = claude_md_state(root)
    add("claude-md", cs, cs != "handwritten")
    pm, ok = project_md_state(root)
    sync_hint = "; run: aaxis-oro setup sync" if f == "done" else "; after the foundation step run: aaxis-oro setup sync"
    add("project-md", pm + ("" if ok else sync_hint), ok)
    pend = triage_pending(root)
    add("rules", "triage pending; run: aaxis-oro setup apply-rules --plan <file>" if pend else "ok", not pend)
    cfg = os.path.isfile(os.path.join(root, ".oro-ai", "config.json"))
    add("config", "ok" if cfg else "missing; run: aaxis-oro setup sync", cfg)
    gi = os.path.isfile(os.path.join(root, ".oro-ai", ".gitignore"))
    tracked = tracked_plan(root)
    parts = ["ok" if gi else "missing" + ("" if tracked else "; run: aaxis-oro setup sync")] + (["%d tracked files, see plan" % len(tracked)] if tracked else [])
    add("oro-ai-gitignore", ", ".join(parts), gi and not tracked)
    from projsetup import precommit
    hs, hd = precommit.state(root)
    hint = {"missing": "missing; run: aaxis-oro setup sync", "outdated": "outdated; run: aaxis-oro setup sync",
            "foreign": "unmanaged hook at %s; run: aaxis-oro setup sync (backs it up, installs the managed one)" % hd,
            "foreign-tracked": "project-tracked hook at %s; left alone" % hd}.get(hs, "%s (%s)" % (hs, hd))
    add("pre-commit", hint, hs in ("ok", "skipped", "foreign-tracked"))
    if hs != "skipped":
        miss = precommit.missing_tools(root)
        add("hook-tools", "ok" if not miss else "; ".join("%s missing, fix: %s" % m for m in miss), not miss)
    add("oro-version", detect_version(root), True)
    a, aok = atlas_line(root)
    add("atlas", a, aok)
    env = os.path.isfile(os.path.join(root, ".oro-ai", "local-env", "env.yml"))
    add("env", "ok" if env else "missing; run: aaxis-oro env setup --project %s" % root, env)
    n = memory_count(root)
    add("memory", "ok" if not n else "%d unmigrated; run /aaxis-oro:notes-migrate" % n, not n)
    if as_json:
        print(json.dumps({k: {"value": v, "ok": o} for k, v, o in rows}, ensure_ascii=False))
    else:
        for k, v, o in rows:
            print("%-17s %s" % (k, v))
        if tracked:
            print("untrack plan (run yourself, never auto-run):")
            print("\n".join(plan_lines(len(tracked), gi)))
    return 0 if not todo else 2


# --- hand-written CLAUDE.md rule triage ---

def split_blocks(text):
    """(section, text) per paragraph, list item or fenced block; headings, blank lines and @imports are structure."""
    out, section, cur, fence = [], "", [], False

    def flush():
        if cur:
            out.append((section, "\n".join(cur).rstrip()))
            cur.clear()

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            cur.append(line)
            continue
        if fence:
            cur.append(line)
        elif re.match(r"#{1,6}\s", line):
            flush()
            section = line.lstrip("#").strip()
        elif not line.strip() or line.startswith("@"):
            flush()
        elif re.match(r"(?:[-*]|\d+\.)\s", line):
            flush()
            cur.append(line)
        else:
            cur.append(line)
    flush()
    return [(s, t) for s, t in out if t.strip()]


def rules(root, dry):
    path = os.path.join(root, "CLAUDE.md")
    text = read(path)
    if triage_pending(root) and (text is None or "@CLAUDE_base.md" in text):
        print("triage pending: %s; apply with: aaxis-oro setup apply-rules --plan <file>" % RULES_REL)
        return 0
    if text is None or "@CLAUDE_base.md" in text:
        print("nothing to triage (CLAUDE.md %s)" % ("missing" if text is None else "already imports CLAUDE_base.md"))
        return 0
    items = [{"id": i + 1, "section": s, "text": t} for i, (s, t) in enumerate(split_blocks(text))]
    table = ["| id | section | rule |", "|---|---|---|"] + ["| %d | %s | %s |" % (i["id"], i["section"], i["text"].replace("\n", " ").replace("|", "\\|")) for i in items]
    if not dry:
        bk = os.path.join(root, BACKUP_REL)
        if not os.path.isfile(bk):
            write(bk, text)
        write(os.path.join(root, RULES_REL), "\n".join(table) + "\n")
        write(os.path.join(root, RULES_JSON), json.dumps(items, ensure_ascii=False, indent=1))
        if os.path.isfile(os.path.join(root, APPLIED)):
            os.remove(os.path.join(root, APPLIED))
    print("%d rules from hand-written CLAUDE.md; table: %s; original kept at %s" % (len(items), RULES_REL, BACKUP_REL))
    return 0


def grouped(items, acts, act):
    """Rule texts of one action under their original section headings, in source order."""
    out, last = [], None
    for k in sorted(items):
        if acts[k] != act:
            continue
        if items[k]["section"] != last:
            last = items[k]["section"]
            out.append("## " + (last or "Rules"))
        out.append(items[k]["text"])
    return "\n\n".join(out)


def sync_kept(ctext, kept):
    """Keep rules live inside the foundation's claude-notes sentinels, the only part its --force rebuild preserves."""
    if marker(KEPT) in ctext or marker(KEPT, True) in ctext:
        return sync_block(ctext, KEPT, kept)
    if NOTES_OPEN in ctext and NOTES_CLOSE in ctext and ctext.index(NOTES_OPEN) < ctext.index(NOTES_CLOSE):
        k = ctext.index(NOTES_CLOSE)
        return ctext[:k].rstrip("\n") + "\n\n" + kept + "\n" + ctext[k:]
    return ctext.rstrip("\n") + "\n\n" + NOTES_OPEN + "\n" + kept + "\n" + NOTES_CLOSE + "\n"


def apply_rules(root, plan_path, dry):
    plan = json.load(sys.stdin if plan_path == "-" else open(plan_path, encoding="utf-8"))
    with open(os.path.join(root, RULES_JSON), encoding="utf-8") as fh:
        items = {i["id"]: i for i in json.load(fh)}
    ids = [int(x["id"]) for x in plan["items"]]
    acts = {int(x["id"]): x["action"] for x in plan["items"]}
    dups = sorted({k for k in ids if ids.count(k) > 1})
    missing = sorted(set(items) - set(acts))
    bad = sorted(k for k, a in acts.items() if a not in ("keep", "move", "drop") or k not in items)
    if missing or bad or dups:
        sys.stderr.write("plan must give keep|move|drop once per rule id; missing %s, invalid %s, duplicate %s\n" % (missing, bad, dups))
        return 64
    counts = {a: sum(1 for v in acts.values() if v == a) for a in ("keep", "move", "drop")}
    moved = marker(MIGRATED) + "\n" + grouped(items, acts, "move") + "\n" + marker(MIGRATED, True)
    kept = marker(KEPT) + "\n" + grouped(items, acts, "keep") + "\n" + marker(KEPT, True)
    pm, cm = os.path.join(root, "CLAUDE_project.md"), os.path.join(root, "CLAUDE.md")
    ptext = read(pm) or read(os.path.join(TEMPLATES, "CLAUDE_project.md"))
    ctext = read(cm)
    if ctext is None or "@CLAUDE_base.md" not in ctext:
        sys.stderr.write("run orocommerce-foundation:setup (--force) first: CLAUDE.md must import CLAUDE_base.md\n")
        return 3
    new_p = sync_block(ptext, MIGRATED, moved) if counts["move"] else ptext
    new_c = sync_kept(ctext, kept) if counts["keep"] else ctext
    if dry:
        for name, txt in (("CLAUDE_project.md", moved if counts["move"] else ""), ("CLAUDE.md", kept if counts["keep"] else "")):
            if txt:
                print("--- %s (first 40 lines)\n%s" % (name, "\n".join(txt.splitlines()[:40])))
    else:
        write(pm, new_p)
        write(cm, new_c)
        write(os.path.join(root, APPLIED), "applied\n")
    print("rules: %(move)d moved to CLAUDE_project.md, %(keep)d kept in CLAUDE.md, %(drop)d dropped" % counts)
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="aaxis-oro setup", usage=ASK)
    ap.add_argument("action", choices=("status", "sync", "rules", "apply-rules"))
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--plan")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.project)
    try:
        if a.action == "status":
            return status(root, a.json)
        if a.action == "sync":
            lines, code = sync(root, a.dry_run)
            print("\n".join(lines))
            return code
        if a.action == "rules":
            return rules(root, a.dry_run)
        if not a.plan:
            ap.error("apply-rules needs --plan FILE")
        return apply_rules(root, a.plan, a.dry_run)
    except SetupError as exc:
        sys.stderr.write("%s\n" % exc)
        return 3
