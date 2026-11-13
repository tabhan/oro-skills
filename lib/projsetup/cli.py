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
BLOCKS = ("review-rules", "plan-rules")  # template file stem == block name
CONFIG = {"spec": {"id-pattern": "[A-Z][A-Z0-9-]*:AC-[0-9]+"}}
GITIGNORE = "*\n!.gitignore\n!config.json\n"
OWN_FILES = (".oro-ai/config.json", ".oro-ai/.gitignore")
MIGRATED, KEPT = "migrated-rules", "kept-rules"
BACKUP_REL = os.path.join(".oro-ai", "setup", "CLAUDE.original.md")
RULES_REL = os.path.join(".oro-ai", "setup", "rules.md")
ASK = "usage: aaxis-oro setup <status|sync|rules|apply-rules> [--project P] [--dry-run] [--json] [--plan FILE]\n"


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


def tracked_plan(root):
    tracked = [t for t in git_tracked(root, ".oro-ai") if t not in OWN_FILES]
    return tracked


def plan_lines(n, have_gitignore):
    out = ["  git rm -r --cached -q .oro-ai"]
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
    add("project-md", pm + ("" if ok else "; run: aaxis-oro setup sync"), ok)
    cfg = os.path.isfile(os.path.join(root, ".oro-ai", "config.json"))
    add("config", "ok" if cfg else "missing; run: aaxis-oro setup sync", cfg)
    gi = os.path.isfile(os.path.join(root, ".oro-ai", ".gitignore"))
    tracked = tracked_plan(root)
    parts = ["ok" if gi else "missing" + ("" if tracked else "; run: aaxis-oro setup sync")] + (["%d tracked files, see plan" % len(tracked)] if tracked else [])
    add("oro-ai-gitignore", ", ".join(parts), gi and not tracked)
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
        write(os.path.join(root, ".oro-ai", "setup", "rules.json"), json.dumps(items, ensure_ascii=False, indent=1))
    print("%d rules from hand-written CLAUDE.md; table: %s; original kept at %s" % (len(items), RULES_REL, BACKUP_REL))
    return 0


def apply_rules(root, plan_path, dry):
    plan = json.load(sys.stdin if plan_path == "-" else open(plan_path, encoding="utf-8"))
    items = {i["id"]: i for i in json.load(open(os.path.join(root, ".oro-ai", "setup", "rules.json"), encoding="utf-8"))}
    acts = {int(x["id"]): x["action"] for x in plan["items"]}
    missing = sorted(set(items) - set(acts))
    bad = sorted(k for k, a in acts.items() if a not in ("keep", "move", "drop") or k not in items)
    if missing or bad:
        sys.stderr.write("plan must give keep|move|drop for every rule id; missing %s, invalid %s\n" % (missing, bad))
        return 64
    section = lambda act, title: "\n\n".join(["## " + title] + [items[k]["text"] for k in sorted(items) if acts[k] == act])
    counts = {a: sum(1 for v in acts.values() if v == a) for a in ("keep", "move", "drop")}
    moved = marker(MIGRATED) + "\n" + section("move", "Project rules") + "\n" + marker(MIGRATED, True)
    kept = marker(KEPT) + "\n" + section("keep", "Kept rules") + "\n" + marker(KEPT, True)
    pm, cm = os.path.join(root, "CLAUDE_project.md"), os.path.join(root, "CLAUDE.md")
    ptext = read(pm) or read(os.path.join(TEMPLATES, "CLAUDE_project.md"))
    ctext = read(cm)
    if ctext is None or "@CLAUDE_base.md" not in ctext:
        sys.stderr.write("run orocommerce-foundation:setup (--force) first: CLAUDE.md must import CLAUDE_base.md\n")
        return 3
    new_p = sync_block(ptext, MIGRATED, moved) if counts["move"] else ptext
    new_c = sync_block(ctext, KEPT, kept) if counts["keep"] else ctext
    if not dry:
        write(pm, new_p)
        write(cm, new_c)
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
