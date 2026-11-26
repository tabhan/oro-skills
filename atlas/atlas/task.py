"""`aaxis-oro task`: per-ticket process evidence under `.oro-ai/task/<KEY>/`, shared by the CLI, `review check` and hooks.

Only setup projects (`.oro-ai/config.json` present) are in scope; everything else is a no-op.
Mechanics and the escape hatch: README "Ticket process".
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys

KEY = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9]+-\d+)(?![0-9])")
WORDS = r"(approved|pass(?:ed)?|rejected?|fail(?:ed)?|changes[- ]requested|skipped|in[- ]progress)"
# A `Verdict: <word>` line anywhere, or the verdict word alone opening the file (older gate output wrote bare "PASS").
VERDICT = re.compile(r"^[\s>*_#-]*verdict[\s*_]*:[\s*_`]*%s\b[ \t*_`]*([^\n]*)" % WORDS, re.I | re.M)
LEAD = re.compile(r"\A\s*[>*_#` \t]*%s\b[ \t*_`]*([^\n]*)" % WORDS, re.I)
CANON = {"pass": "approved", "passed": "approved", "reject": "rejected", "fail": "rejected", "failed": "rejected",
         "changes-requested": "changes-requested", "changes requested": "changes-requested",
         "in progress": "in-progress"}
# `Range: <base>..<head>` in review.md: the commits the supplementary review covered.
RANGE = re.compile(r"^[\s>*_#-]*range[\s*_]*:[\s*_`]*([0-9a-f]{7,40})\.\.\.?([0-9a-f]{7,40})", re.I | re.M)
# `Started: <ISO-8601 UTC>` on the in-progress marker /aaxis-oro:review writes before dispatching its lenses.
STARTED = re.compile(r"^[\s>*_#-]*started[\s*_]*:[\s*_`]*(\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d)?(?:\.\d+)?(?:Z|[+-]\d\d:?\d\d)?)", re.I | re.M)
IN_PROGRESS_TTL = 2 * 3600
# An approved review still covers HEAD while the branch's own commits since its Range head change at most this many
# production lines (added + deleted); see review_delta.
SMALL_DELTA_LINES = 20
TASK_ONLY = re.compile(r"^\.oro-ai/")
E2E_FILE = re.compile(r"(?:\.feature|\.steps\.ts)$")
PROD_FILE = re.compile(r"^src/.+\.(?:php|ya?ml|xml|twig|js|ts|scss)$")
NOT_PROD = re.compile(r"/(?:Tests|Migrations/Data/Demo)/|/translations/")
# User-visible behaviour: the only production changes that need a test-first e2e scenario (process rule 3). Storefront/admin UI
# (twig, JS/TS, SCSS/CSS, layouts, public assets), controllers/routes, API, datagrids, workflows/operations/actions, emails,
# navigation/system-config screens, and translations shown to users. Pure backend (services, listeners, DI/config wiring,
# migrations, entities, MQ processors) is optional for e2e: a unit/functional test is enough.
USER_VISIBLE = re.compile(
    r"^src/.+(?:\.(?:twig|js|ts|scss|css)$|/(?:Controller|Api|Layout|layouts|views|public|translations|EmailTemplates|Mailer)/"
    r"|/Resources/config/oro/(?:datagrids|layouts|routing|api|workflows|actions|operations|navigation|system_configuration|"
    r"emails|email_templates)[^/]*\.ya?ml$|/Resources/config/(?:routing|oro/routing)[^/]*\.ya?ml$|/Resources/views/)")
USER_VISIBLE_EXCLUDE = re.compile(r"/Tests/|/Migrations/Data/Demo/")
# SMALL change (no architect-gate agent, no verdict file needed): at most SMALL_FILES changed files outside `.oro-ai/` and
# none on a risk path (same list /aaxis-oro:review uses to pick opus) or adding a risk construct.
SMALL_FILES = 3
RISK_PATH = re.compile(r"/Migrations/|acl|security|workflows?\.ya?ml|/workflows/|Interceptor", re.I)
RISK_CONTENT = re.compile(r"^\+.*(?:decorates:|aaxis_aspect\.interceptor|acl_resource|permission)", re.M)
BASES = ("origin/develop", "develop", "origin/main", "main", "origin/master", "master")
STATUS_STUB = "# %s status\n\nOne line per milestone (date, step, result).\n\n- [ ] plan written (plan.md)\n" \
              "- [ ] architect-gate verdict saved (architect-gate.md)\n- [ ] e2e scenario red (user-visible changes; else n/a)\n- [ ] implementation green\n" \
              "- [ ] review check / verification\n"
PLAN_STUB = "# %s plan\n\n## Root cause\n\nEvidence (file:line, log, reproduction), the layer it lives in (code / test / data / environment / " \
            "config / upstream) and why the change fixes that layer, not a symptom (process rule \"Root cause before " \
            "fix\"). A feature with no defect writes `n/a - feature`.\n\n## Extension points\n\nFor each choice: mechanism, source (`aaxis-oro atlas <sub> <term>` -> file:line, " \
            "an `aaxis-oro:solutions` reference, an Oro docs URL).\n\n## Tests\n\nThe e2e scenario(s) written first for user-visible behaviour; for a pure backend change, the unit/functional test or `n/a - no user-visible change`.\n"


def git(root, *args):
    p = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, errors="ignore")
    return p.stdout.strip() if p.returncode == 0 else None


def is_setup(root):
    return bool(root) and os.path.isfile(os.path.join(root, ".oro-ai", "config.json"))


NOT_TICKET = {"UTF", "ISO", "SHA", "RFC", "PSR", "HTTP", "TLS", "SSL", "ES", "ECMA", "MD", "CVE", "IEC"}


def key_from(text):
    """First ticket-like key in text, skipping standards names such as UTF-8 or ISO-8601."""
    keys = [k for k in KEY.findall(text or "") if k.split("-")[0] not in NOT_TICKET]
    return keys[0] if keys else None


def branch_key(root):
    return key_from(git(root, "rev-parse", "--abbrev-ref", "HEAD"))


def task_dir(root, key):
    return os.path.join(root, ".oro-ai", "task", key)


def read_text(path):
    """File text, '' when missing, None when unreadable."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""
    except OSError:
        return None


def verdict_of(text):
    """('missing'|'unreadable'|'no-verdict'|'approved'|'rejected'|'changes-requested'|'skipped'|'in-progress', reason) of a verdict file."""
    state, reason = ("unreadable" if text is None else "missing"), ""
    if text:
        m = VERDICT.search(text) or LEAD.search(text)
        word = m.group(1).lower() if m else None
        state, reason = (CANON.get(word, word), m.group(2).strip(" -:\u2014")) if m else ("no-verdict", "")
        if state == "skipped" and not reason:
            state = "no-verdict"
    return state, reason


def gate_state(root, key):
    """Verdict of .oro-ai/task/<KEY>/architect-gate.md (see verdict_of)."""
    return verdict_of(read_text(os.path.join(task_dir(root, key), "architect-gate.md")))


APPROVED_SECTION = re.compile(r"^Approved-Section:[ \t]*(.+?)[ \t]*=[ \t]*([0-9a-f]{12})[ \t]*$", re.M)
HEADING = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", re.M)


def plan_sections(text):
    """{heading: 12-hex hash of the section body} of a plan.md (text before the first heading is skipped)."""
    marks = list(HEADING.finditer(text or ""))
    found = {}
    for i, m in enumerate(marks):
        body = text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        found[m.group(1).strip()] = hashlib.sha256(" ".join(body.split()).encode()).hexdigest()[:12]
    return found


def gate_diff(root, key):
    """(approved?, {'changed': [...], 'new': [...], 'removed': [...], 'unchanged': [...]}) of plan.md against the sections
    recorded in architect-gate.md by the last approved verdict. approved? is False when nothing was recorded: gate the
    whole plan then; otherwise the architect-gate re-reviews only 'changed' and 'new' sections."""
    gate = read_text(os.path.join(task_dir(root, key), "architect-gate.md")) or ""
    before = {h: d for h, d in APPROVED_SECTION.findall(gate)}
    now = plan_sections(read_text(os.path.join(task_dir(root, key), "plan.md")) or "")
    diff = {"changed": [h for h in now if h in before and before[h] != now[h]], "new": [h for h in now if h not in before],
            "removed": [h for h in before if h not in now], "unchanged": [h for h in now if before.get(h) == now[h]]}
    return bool(before), diff


def record_gate_sections(root, key):
    """Replace the `Approved-Section:` lines of an approved architect-gate.md with the current plan.md sections; True on success."""
    path = os.path.join(task_dir(root, key), "architect-gate.md")
    text = read_text(path)
    if verdict_of(text)[0] != "approved":
        return False
    text = APPROVED_SECTION.sub("", text).rstrip("\n") + "\n"
    lines = "".join("Approved-Section: %s = %s\n" % (h, d) for h, d in plan_sections(read_text(os.path.join(task_dir(root, key), "plan.md")) or "").items())
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n" + lines)
    return True


def review_delta(root, reviewed):
    """Production lines (added + deleted) the branch's OWN commits changed in reviewed..HEAD; None when git fails.

    Merge-aware: `--first-parent --no-merges` walks only the branch's own line of commits, so merge commits (e.g.
    merging develop) and everything they bring in are ignored, and the per-commit numstat of the remaining commits is
    summed over production files only (is_prod: tests, translations, demo data, e2e and .oro-ai/ never count).
    """
    out = git(root, "log", "--first-parent", "--no-merges", "--no-renames", "--numstat", "--format=", "%s..HEAD" % reviewed)
    if out is None:
        return None
    total = 0
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3 and is_prod(parts[2]):
            total += sum(int(n) for n in parts[:2] if n.isdigit())
    # A merge's own edits are invisible above: a conflict resolution that hand-edits prod code is a change nobody
    # reviewed. `git show --cc` prints only the combined diff, whose line prefix has one column per parent; a line
    # whose every column is +/- differs from ALL parents, i.e. the resolution itself. Lines taken verbatim from one
    # parent have a blank column and a clean merge prints no hunks at all, so both count 0.
    for merge in (git(root, "rev-list", "--first-parent", "--merges", "%s..HEAD" % reviewed) or "").split():
        diff = git(root, "show", "--cc", "--format=", "-U0", "--no-renames", merge)
        if diff is None:
            return None
        path, cols = None, 0
        for line in diff.splitlines():
            if line.startswith("diff --cc "):
                path, cols = line[10:], 0
            elif line.startswith("@@"):
                cols = line.split(" ")[0].count("@") - 1  # one prefix column per parent
            elif cols and path and is_prod(path) and len(line) > cols and all(c in "+-" for c in line[:cols]):
                total += 1
    return total


def review_state(root, key):
    """(state, reason) of .oro-ai/task/<KEY>/review.md; an approved review is 'stale' unless its Range head covers HEAD.

    Covers = the head is HEAD, or an ancestor of HEAD (a rebase makes it stale) whose branch-own, non-merge commits since
    changed at most SMALL_DELTA_LINES production lines (review_delta); merge-only and non-production changes are free.
    """
    text = read_text(os.path.join(task_dir(root, key), "review.md"))
    state, reason = verdict_of(text)
    if state == "approved":
        m = RANGE.search(text)
        head = git(root, "rev-parse", "HEAD")
        reviewed = m and git(root, "rev-parse", "--verify", "-q", m.group(2) + "^{commit}")
        delta = reviewed and reviewed != head and git(root, "merge-base", "--is-ancestor", reviewed, "HEAD") is not None \
            and review_delta(root, reviewed)
        covered = bool(reviewed) and (reviewed == head or (delta is not None and delta is not False and delta <= SMALL_DELTA_LINES))
        state, reason = ("approved", reason) if covered else (
            "stale", "no Range: <base>..<head> line" if not m else "reviewed %s, HEAD is %s (not an ancestor, or over %d "
            "production lines changed by the branch's own commits)" % (m.group(2)[:10], (head or "?")[:10], SMALL_DELTA_LINES))
    return state, reason


def in_progress(root, key, now=None):
    """(fresh, started, why) for an in-progress review.md marker; None when review.md is not in-progress.

    Fresh = its Range head is HEAD and Started is younger than IN_PROGRESS_TTL; otherwise `why` says what is stale.
    """
    from datetime import datetime, timezone
    text = read_text(os.path.join(task_dir(root, key), "review.md"))
    if verdict_of(text)[0] != "in-progress":
        return None
    m, s = RANGE.search(text), STARTED.search(text)
    reviewed = m and git(root, "rev-parse", "--verify", "-q", m.group(2) + "^{commit}")
    try:
        started = datetime.fromisoformat(s.group(1).replace("Z", "+00:00")) if s else None
        started = started and (started if started.tzinfo else started.replace(tzinfo=timezone.utc))
    except ValueError:
        started = None
    age = started and ((now or datetime.now(timezone.utc)) - started).total_seconds()
    why = ("no Range head" if not reviewed else "Range head is not HEAD" if reviewed != git(root, "rev-parse", "HEAD")
           else "no valid Started time" if not started else "started over %dh ago" % (IN_PROGRESS_TTL // 3600)
           if age > IN_PROGRESS_TTL else "")
    return not why, s.group(1) if s else "?", why


def review_problem(root, key):
    """One line when this branch's committed code needs a fresh approved/skipped review.md, else None."""
    if not any(not TASK_ONLY.match(f) for f in branch_files(root)):
        return None
    state, reason = review_state(root, key)
    if state == "in-progress":
        return ("review in progress (.oro-ai/task/%s/review.md says 'Verdict: in-progress'; not approved until "
                "/aaxis-oro:review writes its final verdict)" % key)
    return None if state in ("approved", "skipped") else (
        "review: %s%s (run /aaxis-oro:review; .oro-ai/task/%s/review.md needs 'Verdict: approved' and a "
        "'Range: <base>..<head>' covering HEAD, or 'Verdict: skipped - <reason>')" % (state, ": " + reason if reason else "", key))


def branch_files(root):
    """Files changed on this branch vs the first base ref that exists (committed part only); [] when none resolves."""
    for base in BASES:
        if git(root, "rev-parse", "--verify", "-q", base) is not None:
            out = git(root, "diff", "--name-only", "%s...HEAD" % base)
            return [x for x in (out or "").splitlines() if x]
    return []


def branch_added_text(root):
    """Added lines of the branch's committed diff vs the first base ref that exists ('' when none resolves)."""
    for base in BASES:
        if git(root, "rev-parse", "--verify", "-q", base) is not None:
            return git(root, "diff", "-U0", "%s...HEAD" % base) or ""
    return ""


def untracked(root):
    """(paths, added_text) of untracked, non-ignored files: their contents count as added lines (a new file is all additions)."""
    paths = [x for x in (git(root, "ls-files", "-o", "--exclude-standard") or "").splitlines() if x]
    text = []
    for p in paths:
        try:
            with open(os.path.join(root, p), encoding="utf-8", errors="replace") as fh:
                text.extend("+" + l for l in fh.read(200000).splitlines())
        except OSError:
            pass
    return paths, "\n".join(text)


def small_reason(root, paths, added_text=""):
    """'' for a SMALL change, else why not: at most SMALL_FILES files (ignoring `.oro-ai/`), no risk path, no risk construct
    in the added lines (`added_text`, the branch's committed diff, and untracked files, which count as paths and content)."""
    up, ut = untracked(root)
    files = sorted({p for p in list(paths) + up if not TASK_ONLY.match(p)})
    if len(files) > SMALL_FILES:
        return "%d files changed (max %d)" % (len(files), SMALL_FILES)
    hit = [p for p in files if RISK_PATH.search(p)]
    if hit:
        return "risk path: %s" % hit[0]
    if files and RISK_CONTENT.search(added_text + "\n" + branch_added_text(root) + "\n" + ut):
        return "adds a risk construct (decorates:, aspect interceptor, acl_resource, permission)"
    return ""


def is_small_change(root, paths, added_text=""):
    """True for a SMALL change (see small_reason); SMALL changes are exempt from the architect-gate."""
    return not small_reason(root, paths, added_text)


def is_prod(path):
    return bool(PROD_FILE.search(path)) and not NOT_PROD.search(path) and not E2E_FILE.search(path)


def is_user_visible(path):
    """A changed file that alters user-visible behaviour (see USER_VISIBLE); tests, demo data and e2e files never do."""
    return bool(USER_VISIBLE.search(path)) and not USER_VISIBLE_EXCLUDE.search(path) and not E2E_FILE.search(path)


def evidence(root, key, paths):
    """Lines describing missing per-ticket evidence for the given changed paths (gate handled by the caller)."""
    lines = []
    if not os.path.isfile(os.path.join(task_dir(root, key), "STATUS.md")):
        lines.append("no .oro-ai/task/%s/STATUS.md; run: aaxis-oro task init %s" % (key, key))
    if any(is_user_visible(p) for p in paths) and not any(E2E_FILE.search(p) for p in paths):
        lines.append("user-visible behaviour changed (UI/controller/API/email/workflow/datagrid/translation) but no e2e "
                     "*.feature/*.steps.ts on the branch (test-first, aaxis-oro:e2e)")
    return lines


ROOT_CAUSE = re.compile(r"^#{1,6}[ \t]*root[ \t]+cause[ \t]*#*[ \t]*$", re.I | re.M)
NEXT_HEADING = re.compile(r"^#{1,6}[ \t]", re.M)
STUB_PROSE = re.compile(r"^Evidence \(file:line, log, reproduction\).*?A feature with no defect writes `n/a - feature`\.$",
                        re.S | re.M)


def root_cause_problem(root, key):
    """A warning when plan.md exists, the branch has committed code and its `## Root cause` section is missing or empty."""
    text = read_text(os.path.join(task_dir(root, key), "plan.md"))
    if not text or not any(not TASK_ONLY.match(f) for f in branch_files(root)):
        return None
    m = ROOT_CAUSE.search(text)
    nxt = m and NEXT_HEADING.search(text, m.end())
    body = m and STUB_PROSE.sub("", text[m.end():nxt.start() if nxt else len(text)]).strip()
    return None if body else ("warning: .oro-ai/task/%s/plan.md has %s '## Root cause' section (evidence + layer, or "
                              "'n/a - feature'; process rule \"Root cause before fix\")" % (key, "an empty" if m else "no"))


def init(root, key):
    d = task_dir(root, key)
    os.makedirs(d, exist_ok=True)
    made = []
    for name, stub in (("STATUS.md", STATUS_STUB), ("plan.md", PLAN_STUB)):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(stub % key)
            made.append(name)
    return made



def _require_project(explicit):
    lib = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import projroot
    root = None
    try:
        root = projroot.require(explicit)
    except projroot.NotOroProject as exc:
        sys.stderr.write("aaxis-oro: %s\n" % exc)
    return root


def _timing_path(root, key):
    return os.path.join(task_dir(root, key), "timing.jsonl")


def phase_event(root, key, name, event, note=None):
    """Append {phase, event, ts, head[, note]} to .oro-ai/task/<KEY>/timing.jsonl."""
    import json
    import time
    rec = {"phase": name, "event": event, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "head": git(root, "rev-parse", "HEAD") or ""}
    if note:
        rec["note"] = note
    os.makedirs(task_dir(root, key), exist_ok=True)
    with open(_timing_path(root, key), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def timing_report(root, key):
    """Lines of per-phase total durations (repeated phases summed, an unterminated start counted to the last event) + total."""
    import json
    from datetime import datetime, timezone
    events = []
    for line in read_text(_timing_path(root, key)).splitlines():
        try:
            e = json.loads(line)
            e["_t"] = datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
            events.append(e)
        except (ValueError, KeyError, TypeError):
            continue
    if not events:
        return ["task %s: no timing recorded" % key]
    last = max(e["_t"] for e in events)
    open_at, totals, runs, order, unfinished = {}, {}, {}, [], set()
    for e in events:
        n = e.get("phase")
        if n not in totals:
            totals[n], runs[n] = 0.0, 0
            order.append(n)
        if e.get("event") == "start":
            if n in open_at:
                unfinished.add(n)
            open_at[n] = e["_t"]
        elif e.get("event") == "end" and n in open_at:
            totals[n] += e["_t"] - open_at.pop(n)
            runs[n] += 1
    for n, t0 in open_at.items():
        totals[n] += last - t0
        runs[n] += 1
        unfinished.add(n)
    fmt = lambda s: "%dm%02ds" % divmod(int(round(s)), 60)
    out = ["%-20s %s x%d%s" % (n, fmt(totals[n]), runs[n], " (no end: counted to the last event)" if n in unfinished else "") for n in order]
    out.append("%-20s %s (first to last event %s)" % ("total (phases)", fmt(sum(totals.values())), fmt(last - min(e["_t"] for e in events))))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aaxis-oro task", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=("init", "check", "gate-diff", "gate-record", "small", "phase", "timing"))
    ap.add_argument("key", nargs="?", help="ticket key; default: from the branch name")
    ap.add_argument("rest", nargs="*", help="phase: <name> start|end; timing: none")
    ap.add_argument("--note")
    ap.add_argument("--project")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    root = _require_project(a.project)
    if root is None:
        return 0 if a.action in ("phase", "timing") else 64
    if a.action in ("phase", "timing"):  # never fail the caller
        try:
            key = a.key or branch_key(root)
            if a.action == "timing":
                print("\n".join(timing_report(root, key))) if key else sys.stderr.write("aaxis-oro task: no ticket key\n")
            elif not key or len(a.rest) != 2 or a.rest[1] not in ("start", "end"):
                sys.stderr.write("aaxis-oro task: warning: usage: task phase <KEY> <name> start|end [--note T]\n")
            else:
                phase_event(root, key, a.rest[0], a.rest[1], a.note)
        except Exception as exc:
            sys.stderr.write("aaxis-oro task: warning: %s\n" % exc)
        return 0
    key = a.key or branch_key(root)
    if a.action == "small":
        staged = (git(root, "diff", "--cached", "--name-only") or "").splitlines()
        why = small_reason(root, branch_files(root) + staged, git(root, "diff", "--cached", "-U0") or "")
        print("not SMALL: " + why if why else "SMALL")
        return 1 if why else 0
    if not key:
        sys.stderr.write("aaxis-oro task: no ticket key given or in the branch name\n")
        return 64
    if a.action == "init":
        made = init(root, key)
        print("task %s: %s" % (key, ("created " + ", ".join(made)) if made else "exists"))
        return 0
    if a.action == "gate-record":
        ok = record_gate_sections(root, key)
        print("task %s: %s" % (key, "recorded the approved plan sections in architect-gate.md" if ok else "architect-gate.md is not approved; nothing recorded"))
        return 0 if ok else 1
    if a.action == "gate-diff":
        recorded, diff = gate_diff(root, key)
        if not recorded:
            print("task %s: no approved sections recorded: gate the whole plan" % key)
        else:
            print("task %s: re-gate only changed/new sections\n" % key + "\n".join("%s: %s" % (k, "; ".join(v) or "-") for k, v in diff.items()))
        return 0
    state, reason = gate_state(root, key)
    staged = (git(root, "diff", "--cached", "--name-only") or "").splitlines()
    problems = evidence(root, key, branch_files(root) + staged)
    rp = review_problem(root, key)
    problems += [rp] if rp else []
    warning = root_cause_problem(root, key)
    if state not in ("approved", "skipped") and not is_small_change(root, branch_files(root) + staged,
                                                                    git(root, "diff", "--cached", "-U0") or ""):
        problems.insert(0, "architect-gate: %s (.oro-ai/task/%s/architect-gate.md needs 'Verdict: approved'; SMALL changes of at most 3 files with no risk path are exempt)" % (state, key))
    print("\n".join(problems + ([warning] if warning else []) + ["task %s: %s (gate %s%s)" % (key, "incomplete" if problems else "ok", state,
                                                            ": " + reason if reason else "")]))
    return 1 if problems else 0
