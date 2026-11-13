#!/usr/bin/env python3
"""Derived-state freshness for `aaxis-oro dev refresh` and the `aaxis-oro test` gate.

  plan   --project P [--all] [--target local|local-test]   print "<step>\\t<reason>" lines (all steps when --all or no record)
  gate   --project P --target local|local-test              exit 1 + one-line message when a step applicable to the target is due
  baseline-key --project P                                  baseline key, cached by a fingerprint of composer.lock + Migrations + DataFixtures
  record --project P                                        store HEAD + input hashes in .oro-ai/local-env/refresh.json
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

CATEGORIES = ("composer", "migrations", "entity", "translations", "routing", "fixtures", "assets", "code")
ASSET_NAMES = {"theme.yml", "assets.yml", "jsmodules.yml", "jsmodules_dev.yml", "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
ASSET_EXT = {".scss", ".css", ".js", ".ts", ".jsx", ".tsx"}
# id, stack (shared steps serve both stacks), triggering categories, execution order is list order.
STEPS = (
    ("composer", "shared", ("composer",)),
    ("cache-local", "local", ("code", "composer")),
    ("cache-test", "local-test", ("code", "composer")),
    ("migrate", "local", ("migrations",)),
    ("baseline-stale", "local-test", ("migrations", "composer")),
    ("entity", "local", ("entity",)),
    ("translations", "local", ("translations",)),
    # Oro writes the dump through the public gaufrette filesystem, which is per stack when it is gridfs.
    ("routing-local", "local", ("routing", "composer")),
    ("routing-test", "local-test", ("routing", "composer")),
    ("assets", "shared", ("assets",)),
)


def categories_of(path):
    parts = path.split("/")
    name = parts[-1]
    ext = os.path.splitext(name)[1]
    if "Tests" in parts or "node_modules" in parts or parts[0] == "tests":
        return set()
    out = set()
    in_src = parts[0] == "src"
    has_pair = any(parts[i] == "Resources" and parts[i + 1] == "config" for i in range(len(parts) - 1))
    if path == "composer.lock":
        out.add("composer")
    if "Migrations" in parts[:-1]:
        out.add("migrations")
    if ("config" in parts[:-1] and "oro" in parts[:-1] and re.match(r"^entity[^/]*\.ya?ml$", name)) or name in ("entity_extend.yml", "entity_configs.yml"):
        out.add("entity")
    if "DataFixtures" in parts[:-1]:
        out.add("fixtures")
    if "translations" in parts[:-1] and ext in (".yml", ".yaml", ".xlf"):
        out.add("translations")
    if re.match(r"^routing[^/]*\.ya?ml$", name) or (in_src and name.endswith("Controller.php")):
        out.add("routing")
    if (any(parts[i] == "Resources" and parts[i + 1] == "public" for i in range(len(parts) - 1)) or name in ASSET_NAMES
            or (in_src and ext in ASSET_EXT)):
        out.add("assets")
    if parts[0] == "config" or has_pair or (in_src and ext in (".php", ".twig")):
        out.add("code")
    return out


def git(project, *args):
    p = subprocess.run(["git", "-C", project, *args], capture_output=True)
    return p.returncode, p.stdout


def blob_hash(path):
    try:
        data = os.readlink(path).encode() if os.path.islink(path) else open(path, "rb").read()
    except OSError:
        return None
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def compute(project):
    """(head, {category: sha256}) from the index plus worktree edits; None when project is not a git work tree."""
    rc, out = git(project, "rev-parse", "HEAD")
    if rc != 0:
        return None
    head = out.decode().strip()
    files = {}
    for rec in git(project, "ls-files", "-s", "-z")[1].split(b"\0"):
        if rec and not rec.startswith(b"160000"):
            meta, _, path = rec.decode("utf-8", "replace").partition("\t")
            files[path] = meta.split()[1]
    deleted = set(git(project, "ls-files", "-d", "-z")[1].decode("utf-8", "replace").split("\0"))
    for path in deleted:
        files.pop(path, None)
    extra = git(project, "ls-files", "-m", "-z")[1] + b"\0" + git(project, "ls-files", "-o", "--exclude-standard", "-z")[1]
    for path in filter(None, extra.decode("utf-8", "replace").split("\0")):
        if path not in deleted and categories_of(path):
            files[path] = blob_hash(os.path.join(project, path)) or "unreadable"
    lines = {c: [] for c in CATEGORIES}
    for path in sorted(files):
        for cat in categories_of(path):
            lines[cat].append("%s\0%s" % (path, files[path]))
    return head, {c: hashlib.sha256("\n".join(v).encode()).hexdigest() for c, v in lines.items()}


def state_path(project):
    return os.path.join(project, ".oro-ai", "local-env", "refresh.json")


def load(project):
    try:
        with open(state_path(project), encoding="utf-8") as fh:
            rec = json.load(fh)
        return rec if isinstance(rec.get("inputs"), dict) else None
    except (OSError, ValueError):
        return None


def due(project, target=None, everything=False):
    """(stored record, [(step, reason)]) for steps applicable to the target (both stacks when None)."""
    cur = compute(project)
    if cur is None:
        return None, []
    rec = load(project)
    changed = set(CATEGORIES) if everything or rec is None else {c for c in CATEGORIES if rec["inputs"].get(c) != cur[1][c]}
    why = "no record" if rec is None else "all" if everything else None
    plan = []
    for step, stack, triggers in STEPS:
        if target in (None, stack) or stack == "shared":
            hit = [t for t in triggers if t in changed]
            if hit:
                plan.append((step, why or "+".join(hit)))
    return rec, plan


def baseline_key(project):
    """Prints the baseline key; baseline-key.sh walks vendor/ (over a second), so reuse it while its inputs are unchanged."""
    cur = compute(project)
    if cur is None:
        return 1
    fp = hashlib.sha256("".join(cur[1][c] for c in ("composer", "migrations", "fixtures")).encode()).hexdigest()
    cache = os.path.join(project, ".oro-ai", "local-env", "baseline-key-cache.json")
    try:
        with open(cache, encoding="utf-8") as fh:
            hit = json.load(fh)
        if hit.get("fp") == fp and hit.get("key"):
            print(hit["key"])
            return 0
    except (OSError, ValueError):
        pass
    p = subprocess.run([os.path.join(os.path.dirname(os.path.abspath(__file__)), "baseline-key.sh"), project], capture_output=True, text=True)
    key = p.stdout.strip()
    if p.returncode != 0 or not key:
        return 1
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w", encoding="utf-8") as fh:
        json.dump({"fp": fp, "key": key}, fh)
    print(key)
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("plan", "gate", "record", "baseline-key"))
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--target", choices=("local", "local-test"))
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    project = os.path.abspath(a.project)
    if a.cmd == "record":
        cur = compute(project)
        if cur is None:
            return 0
        os.makedirs(os.path.dirname(state_path(project)), exist_ok=True)
        tmp = state_path(project) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"commit": cur[0], "refreshed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "inputs": cur[1]}, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, state_path(project))
        return 0
    if a.cmd == "baseline-key":
        return baseline_key(project)
    rec, plan = due(project, a.target, a.all)
    if a.cmd == "plan":
        print("#since %s" % (rec["commit"][:10] if rec and rec.get("commit") else "none"))
        for step, why in plan:
            print("%s\t%s" % (step, why))
        return 0
    if plan:
        print("tree not refreshed since %s; run: aaxis-oro dev refresh" % (rec["commit"][:10] if rec and rec.get("commit") else "none"))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
