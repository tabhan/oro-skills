#!/usr/bin/env python3
"""Stop hook: the enforcement-bypass reminder, and the supplementary-review gate when coding on a ticket is finished.

Review gate (check `review-ticket-stop`): a setup project on a ticket branch with committed code (outside .oro-ai/),
a tree with no uncommitted code and no approved/skipped review.md covering HEAD blocks the main session's Stop once
per stop chain (`stop_hook_active` lets the second Stop through). Subagents are exempt; the main session owns the review.
A fresh `Verdict: in-progress` marker (Range head == HEAD, Started within task.IN_PROGRESS_TTL) only warns.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _common as c  # noqa: E402


def dirty_code(root):
    """True when the working tree has uncommitted (or untracked) changes outside .oro-ai/; unknown counts as dirty."""
    from atlas import task
    out = task.git(root, "status", "--porcelain")
    paths = [ln[3:].split(" -> ")[-1].strip('"') for ln in (out or "").splitlines() if ln.strip()]
    return out is None or any(not task.TASK_ONLY.match(x) for x in paths)


def changes_requested_on_head(root, key):
    from atlas import task
    text = task.read_text(os.path.join(task.task_dir(root, key), "review.md")) or ""
    m = task.RANGE.search(text)
    head = task.git(root, "rev-parse", "HEAD")
    reviewed = m and task.git(root, "rev-parse", "--verify", "-q", m.group(2) + "^{commit}")
    return task.verdict_of(text)[0] == "changes-requested" and bool(reviewed) and reviewed == head


def review_gate(payload):
    """(output, verdict) for the supplementary-review gate; (None, 'skip') whenever it does not apply."""
    if payload.get("hook_event_name") == "SubagentStop" or payload.get("agent_id"):
        return None, "skip"
    from atlas import review, task
    root = c.project_root(payload.get("cwd") or os.getcwd())
    key = task.branch_key(root) if root and task.is_setup(root) else None
    problem = task.review_problem(root, key) if key and not dirty_code(root) else None
    d = review.resolve.check_decision(review.resolve.load_registry(review.REGISTRY), "review-ticket-stop",
                                      review.detect(root).version) if problem else {"run": False}
    if not d["run"]:
        return None, "skip"
    marker = task.in_progress(root, key)
    if marker and marker[0]:
        return {"systemMessage": "[review] review in progress since %s (%s); not blocking." % (
            marker[1], ".oro-ai/task/%s/review.md" % key)}, "in-progress"
    if marker:
        reason = ("review-ticket-stop: .oro-ai/task/%s/review.md holds a stale in-progress marker (started %s; %s). "
                  "Re-run /aaxis-oro:review to completion, then stop." % (key, marker[1], marker[2]))
    elif changes_requested_on_head(root, key):
        reason = ("review-ticket-stop: .oro-ai/task/%s/review.md is changes-requested for HEAD. Address its must-fix "
                  "findings, commit, re-run /aaxis-oro:review, then stop." % key)
    else:
        reason = ("review-ticket-stop: coding on %s looks finished (committed code, clean tree) but %s. Run "
                  "/aaxis-oro:review now, or for a trivial change record 'Verdict: skipped - <reason>' in "
                  ".oro-ai/task/%s/review.md, then stop." % (key, problem, key))
    if payload.get("stop_hook_active"):
        out, verdict = {"systemMessage": "[review] stopping without a supplementary review (already asked once). " + reason}, "warn-loop"
    elif c.enforcement_off() or d["severity"] == "warn":
        out, verdict = {"systemMessage": "[review] " + reason}, "warn-stop"
    else:
        out, verdict = {"decision": "block", "reason": reason}, "block-stop"
    return out, verdict


def bypass_reminder(payload):
    path, st = c.session_state(payload.get("session_id"))
    out = None
    bypassed = st.get("bypassed", 0)
    if bypassed > st.get("bypass_reminded", 0):
        st["bypass_reminded"] = bypassed
        c.save_state(path, st)
        out = {"systemMessage": "[atlas] %s=0 was set: %d edit(s) skipped atlas enforcement this session (see ~/.claude/atlas-hook.log). "
                                "Unset it and rebuild/query atlas before shipping." % (c.OVERRIDE_VAR, bypassed)}
    return out


def decide(payload):
    out = bypass_reminder(payload)
    gate, verdict = review_gate(payload)
    if gate:
        if out and "systemMessage" in gate:
            gate["systemMessage"] = out["systemMessage"] + "\n" + gate["systemMessage"]
        elif out:
            gate["systemMessage"] = out["systemMessage"]
        out = gate
    return out, verdict


def main():
    out, payload, verdict = None, {}, "skip"
    try:
        payload = json.load(sys.stdin)
        out, verdict = decide(payload)
    except Exception as exc:  # noqa: BLE001 - never block stopping
        out, verdict = None, "error:%s" % type(exc).__name__
    if verdict != "skip":
        c.log_decision(payload.get("session_id") if isinstance(payload, dict) else None, "Stop",
                       payload.get("cwd", "") if isinstance(payload, dict) else "", verdict)
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
