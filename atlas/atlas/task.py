"""`aaxis-oro task`: per-ticket process evidence under `.oro-ai/task/<KEY>/`, shared by the CLI, `review check` and hooks.

Only setup projects (`.oro-ai/config.json` present) are in scope; everything else is a no-op.
Mechanics and the escape hatch: README "Ticket process".
"""
import argparse
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
TASK_ONLY = re.compile(r"^\.oro-ai/")
E2E_FILE = re.compile(r"(?:\.feature|\.steps\.ts)$")
PROD_FILE = re.compile(r"^src/.+\.(?:php|ya?ml|xml|twig|js|ts|scss)$")
NOT_PROD = re.compile(r"/(?:Tests|Migrations/Data/Demo)/|/translations/")
BASES = ("origin/develop", "develop", "origin/main", "main", "origin/master", "master")
STATUS_STUB = "# %s status\n\nOne line per milestone (date, step, result).\n\n- [ ] plan written (plan.md)\n" \
              "- [ ] architect-gate verdict saved (architect-gate.md)\n- [ ] e2e scenario red\n- [ ] implementation green\n" \
              "- [ ] review check / verification\n"
PLAN_STUB = "# %s plan\n\n## Root cause\n\nEvidence (file:line, log, reproduction), the layer it lives in (code / test / data / environment / " \
            "config / upstream) and why the change fixes that layer, not a symptom (process rule \"Root cause before " \
            "fix\"). A feature with no defect writes `n/a - feature`.\n\n## Extension points\n\nFor each choice: mechanism, source (`aaxis-oro atlas <sub> <term>` -> file:line, " \
            "an `aaxis-oro:solutions` reference, an Oro docs URL).\n\n## Tests\n\nThe e2e scenario(s) written first.\n"


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


def review_state(root, key):
    """(state, reason) of .oro-ai/task/<KEY>/review.md; an approved review is 'stale' unless its Range head covers HEAD.

    Covers = the head is HEAD, or an ancestor of HEAD with only .oro-ai/ files changed since (committing review.md itself).
    """
    text = read_text(os.path.join(task_dir(root, key), "review.md"))
    state, reason = verdict_of(text)
    if state == "approved":
        m = RANGE.search(text)
        head = git(root, "rev-parse", "HEAD")
        reviewed = m and git(root, "rev-parse", "--verify", "-q", m.group(2) + "^{commit}")
        since = reviewed and git(root, "diff", "--name-only", "%s..HEAD" % reviewed)
        covered = bool(reviewed) and (reviewed == head or (
            since is not None and git(root, "merge-base", "--is-ancestor", reviewed, "HEAD") is not None
            and all(TASK_ONLY.match(f) for f in since.splitlines() if f)))
        state, reason = ("approved", reason) if covered else (
            "stale", "no Range: <base>..<head> line" if not m else "reviewed %s, HEAD is %s" % (m.group(2)[:10], (head or "?")[:10]))
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


def is_prod(path):
    return bool(PROD_FILE.search(path)) and not NOT_PROD.search(path) and not E2E_FILE.search(path)


def evidence(root, key, paths):
    """Lines describing missing per-ticket evidence for the given changed paths (gate handled by the caller)."""
    lines = []
    if not os.path.isfile(os.path.join(task_dir(root, key), "STATUS.md")):
        lines.append("no .oro-ai/task/%s/STATUS.md; run: aaxis-oro task init %s" % (key, key))
    if any(is_prod(p) for p in paths) and not any(E2E_FILE.search(p) for p in paths):
        lines.append("production code changed but no e2e *.feature/*.steps.ts on the branch (test-first, aaxis-oro:e2e)")
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aaxis-oro task", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=("init", "check"))
    ap.add_argument("key", nargs="?", help="ticket key; default: from the branch name")
    ap.add_argument("--project", default=os.getcwd())
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    root = git(a.project, "rev-parse", "--show-toplevel") or os.path.abspath(a.project)
    key = a.key or branch_key(root)
    if not key:
        sys.stderr.write("aaxis-oro task: no ticket key given or in the branch name\n")
        return 64
    if a.action == "init":
        made = init(root, key)
        print("task %s: %s" % (key, ("created " + ", ".join(made)) if made else "exists"))
        return 0
    state, reason = gate_state(root, key)
    staged = (git(root, "diff", "--cached", "--name-only") or "").splitlines()
    problems = evidence(root, key, branch_files(root) + staged)
    rp = review_problem(root, key)
    problems += [rp] if rp else []
    warning = root_cause_problem(root, key)
    if state not in ("approved", "skipped"):
        problems.insert(0, "architect-gate: %s (.oro-ai/task/%s/architect-gate.md needs 'Verdict: approved')" % (state, key))
    print("\n".join(problems + ([warning] if warning else []) + ["task %s: %s (gate %s%s)" % (key, "incomplete" if problems else "ok", state,
                                                            ": " + reason if reason else "")]))
    return 1 if problems else 0
