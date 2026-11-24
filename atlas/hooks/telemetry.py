#!/usr/bin/env python3
"""Usage telemetry hook, active only inside an Oro project root (lib/projroot.py) (SessionStart, SessionEnd, PostToolUse Skill|Bash, UserPromptSubmit). Contract: docs/TELEMETRY_API.md.

Reports who/which project/when, metadata only. Never sent: prompt text, file or code contents, environment variables,
transcripts, credentials (userinfo and tokens are stripped from the remote URL).

The hook itself does almost nothing: it reads the hook input, picks the few fields it needs and starts a fully detached
sender (this script with --send: own session, stdio to /dev/null) that gets the job on a pipe, then returns at once with no
output (no additionalContext, so no tokens are spent). The sender gathers git/host details, computes session_end numbers,
POSTs one event to the ingest endpoint within a few seconds (no Origin header, no cookies) and exits. Any failure
(offline, 4xx/5xx, bad data) drops the event silently; there is no retry and no queue.
Per-session state (start time, model, Claude Code version) lives in ~/.claude/aaxis-oro-telemetry/<session>.json; records
older than 14 days are pruned.
"""
import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from urllib import request

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import projroot  # noqa: E402

SCHEMA = 1
ENDPOINT = "https://acp-api.aaxis.io/telemetry/events"  # fixed; no environment override
TIMEOUT = 3  # seconds for the POST (contract)
CMD_TIMEOUT = 3  # seconds for each git / claude call in the sender
STATE_TTL = 14 * 24 * 3600
DEDUPE_WINDOW = 120  # seconds: a typed /aaxis-oro:x and the Skill call it triggers are one skill_used
MAX_TRANSCRIPT = 64 * 1024 * 1024  # bytes; a larger transcript gets no counts
LIMITS = {"git_name": 200, "git_email": 320, "os_user": 100, "hostname": 255, "os": 50, "plugin_version": 30,
          "claude_code_version": 30, "model": 100, "repo_url": 500, "branch": 255, "commit": 64, "oro_version": 30,
          "session_id": 100}
TYPES = ("session_start", "session_end", "skill_used", "command_used")
ORO_PACKAGES = ("oro/platform", "oro/commerce", "oro/commerce-enterprise", "oro/crm")
SEGMENT = re.compile(r"&&|\|\||[;|\n]")
CLI_CALL = re.compile(r"^\s*(?:[A-Za-z_]\w*=\S*\s+)*(?:\S*/)?aaxis-oro\s+([a-z][a-z0-9_-]*)")
SLASH = re.compile(r"^\s*/(aaxis-oro:[A-Za-z0-9_.-]+)")


def claude_dir():
    return os.path.join(os.path.expanduser("~"), ".claude")


def state_dir():
    return os.path.join(claude_dir(), "aaxis-oro-telemetry")


def clip(field, value):
    """String value cut to the contract's max length for `field`; None for empty or non-scalar values."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    text = str(value).strip()
    return text[:LIMITS[field]] if text else None


def plugin_version(root=ROOT):
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            return json.load(fh).get("version")
    except (OSError, ValueError, AttributeError):
        return None


def normalize_repo_url(url):
    """https://<host>/<owner>/<repo> from any git remote form, with userinfo, port, query and .git stripped; else None."""
    text = (url or "").strip()
    m = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://(?:[^/@]*@)?([^/:@]+)(?::\d+)?/(.+)$", text)  # scheme://[user[:tok]@]host[:port]/path
    if not m:
        m = re.match(r"^(?:[^/@:\s]+@)?([^/:@\s]+):(?!//)/?(.+)$", text)  # scp-like [user@]host:path
    if not m:
        return None
    host, path = m.group(1).lower(), re.split(r"[?#]", m.group(2))[0].strip("/")
    path = re.sub(r"\.git$", "", path)
    return "https://%s/%s" % (host, path) if path.count("/") >= 1 and not re.search(r"\s", path) else None


def event_type(payload):
    """(type, data) this hook input maps to, or (None, None) when it is not a reportable event."""
    name = payload.get("hook_event_name")
    if name == "SessionStart":
        return "session_start", {"source": str(payload.get("source") or "startup")[:20]}
    if name == "SessionEnd":
        return "session_end", {"reason": str(payload.get("reason") or "other")[:50]}
    if name == "PostToolUse" and payload.get("tool_name") == "Skill":
        skill = (payload.get("tool_input") or {}).get("skill")
        return ("skill_used", {"name": str(skill)[:100]}) if isinstance(skill, str) and skill.strip() else (None, None)
    if name == "PostToolUse" and payload.get("tool_name") == "Bash":
        cmd = (payload.get("tool_input") or {}).get("command")
        if isinstance(cmd, str) and "aaxis-oro" in cmd:
            for seg in SEGMENT.split(cmd):
                m = CLI_CALL.match(seg)
                if m:
                    return "command_used", {"name": m.group(1)}
        return None, None
    if name == "UserPromptSubmit":
        m = SLASH.match(payload.get("prompt") if isinstance(payload.get("prompt"), str) else "")
        return ("skill_used", {"name": m.group(1)[:100]}) if m else (None, None)
    return None, None


def build_job(payload, now=None):
    """What the sender needs, from the hook input. Only these fields leave the hook; prompt text and tool input never do."""
    kind, data = event_type(payload if isinstance(payload, dict) else {})
    if not kind or not isinstance(payload.get("session_id"), str) or not payload["session_id"]:
        return None
    model = payload.get("model")
    model = model.get("id") if isinstance(model, dict) else model
    return {"event_id": str(uuid.uuid4()), "type": kind, "data": data, "session_id": payload["session_id"],
            "occurred_at": datetime.fromtimestamp(time.time() if now is None else now).astimezone().isoformat(timespec="seconds"),
            "occurred_ts": time.time() if now is None else now, "cwd": payload.get("cwd") if isinstance(payload.get("cwd"), str) else None,
            "model": model if isinstance(model, str) else None,
            "agent_id": payload.get("agent_id") if isinstance(payload.get("agent_id"), str) else "",  # "" = main session; dedupe key only
            "transcript_path": payload.get("transcript_path") if kind == "session_end" else None}


def spawn_sender(job):
    """Start `telemetry.py --send` fully detached and hand it the job on a pipe; the hook does not wait for it."""
    proc = subprocess.Popen([sys.executable, os.path.realpath(__file__), "--send"], stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)
    try:
        proc.stdin.write(json.dumps(job).encode("utf-8"))
    finally:
        proc.stdin.close()


def duplicate_skill(job, now=None):
    """True when this skill_used repeats one seen for the same session, agent and skill within DEDUPE_WINDOW; else records it.

    UserPromptSubmit (typed /aaxis-oro:x) and PostToolUse Skill (the model loading that skill) can both fire for one
    invocation. A marker file per (session, agent, skill) under the state dir, judged by its mtime, drops the second one.
    PostToolUse also fires inside subagents, whose input carries an agent_id; the main session has none (its own bucket),
    so main and each subagent are counted separately.
    """
    now = time.time() if now is None else now
    key = hashlib.sha1(("%s\0%s\0%s" % (job["session_id"], job.get("agent_id") or "", job["data"]["name"])).encode("utf-8")).hexdigest()[:20]
    marker = os.path.join(state_dir(), "skill-" + key)
    try:
        if now - os.path.getmtime(marker) < DEDUPE_WINDOW:
            return True
    except OSError:
        pass
    try:
        os.makedirs(state_dir(), exist_ok=True)
        for name in os.listdir(state_dir()):  # stale markers go; nothing else is touched
            path = os.path.join(state_dir(), name)
            if name.startswith("skill-") and now - os.path.getmtime(path) > DEDUPE_WINDOW:
                os.remove(path)
        with open(marker, "w"):
            pass
        os.utime(marker, (now, now))
    except OSError:
        pass
    return False


def decide(payload, spawn=spawn_sender, now=None):
    """Hook entry: spawn the sender for a reportable event inside an Oro project. Never returns output."""
    if not isinstance(payload, dict):
        return None
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) and payload.get("cwd") else os.getcwd()
    if projroot.find(cwd) is None:  # not an Oro project: no event, no spawn
        return None
    job = build_job(payload, now)
    if job and job["type"] == "skill_used" and duplicate_skill(job, now):
        return None
    if job:
        try:
            spawn(job)
        except Exception:  # noqa: BLE001 - cannot spawn: drop the event
            pass
    return None


# ---- sender side (background) ----

def run(cmd, cwd=None):
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=CMD_TIMEOUT, stdin=subprocess.DEVNULL,
                             env=dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="true", SSH_ASKPASS="true"))
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def git(cwd, *args):
    return run(["git"] + list(args), cwd) if cwd and os.path.isdir(cwd) else None


def oro_version(cwd):
    """Version of the Oro platform package from the nearest composer.lock above `cwd`, or None."""
    cur = os.path.realpath(cwd) if cwd else None
    for _ in range(12):
        if not cur:
            return None
        path = os.path.join(cur, "composer.lock")
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    pkgs = {p.get("name"): p.get("version") for p in json.load(fh).get("packages", [])}
            except (OSError, ValueError, AttributeError):
                return None
            found = next((pkgs[n] for n in ORO_PACKAGES if pkgs.get(n)), None)
            return str(found).lstrip("v") if found else None
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
    return None


def claude_version():
    exe = shutil.which("claude")
    out = run([exe, "--version"]) if exe else None
    m = re.search(r"\d+\.\d+\.\d+\S*", out or "")
    return m.group(0) if m else None


def state_path(session_id):
    return os.path.join(state_dir(), re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)[:100] + ".json")


def read_state(session_id):
    try:
        with open(state_path(session_id), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(session_id, data):
    tmp = None
    try:
        os.makedirs(state_dir(), exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp.", dir=state_dir())
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, state_path(session_id))
        tmp = None
    except OSError:
        pass
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass


def drop_state(session_id):
    try:
        os.remove(state_path(session_id))
    except OSError:
        pass


def prune_state(now):
    try:
        for name in os.listdir(state_dir()):
            path = os.path.join(state_dir(), name)
            if now - os.path.getmtime(path) > STATE_TTL:
                os.remove(path)
    except OSError:
        pass


def transcript_counts(path):
    """(prompts, tool calls) counted locally from a transcript; nothing from it is ever sent. None when unavailable."""
    try:
        if not path or not os.path.isfile(path) or os.path.getsize(path) > MAX_TRANSCRIPT:
            return None
        prompts = tools = 0
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict) or rec.get("isSidechain") or rec.get("isMeta"):
                    continue
                content = (rec.get("message") or {}).get("content") if isinstance(rec.get("message"), dict) else None
                if rec.get("type") == "user":
                    if isinstance(content, str) or (isinstance(content, list) and any(
                            isinstance(b, dict) and b.get("type") in ("text", "image") for b in content)):
                        prompts += 1
                elif rec.get("type") == "assistant" and isinstance(content, list):
                    tools += sum(1 for b in content if isinstance(b, dict) and b.get("type") == "tool_use")
        return prompts, tools
    except (OSError, ValueError):
        return None


def build_event(job, now=None, version=None):
    """The contract Event for a job, with empty/unknown fields omitted. Reads and updates the per-session state file."""
    now = time.time() if now is None else now
    sid, kind, cwd = job["session_id"], job["type"], job.get("cwd")
    state = read_state(sid)
    if kind == "session_start":
        prune_state(now)
        state.setdefault("started_at", job.get("occurred_ts", now))  # resume/compact keep the original start
        state["model"] = job.get("model") or state.get("model")
        state["claude_code_version"] = claude_version() or state.get("claude_code_version")
        write_state(sid, state)
    model = job.get("model") or state.get("model")

    def group(fields):
        return {k: v for k, v in ((k, clip(k, v)) for k, v in fields.items()) if v is not None}

    try:
        os_user = getpass.getuser()
    except Exception:  # noqa: BLE001 - no passwd entry
        os_user = None
    data = dict(job.get("data") or {})
    if kind == "session_end":
        if state.get("started_at"):
            data["duration_s"] = max(0, int(job.get("occurred_ts", now) - float(state["started_at"])))
        counts = transcript_counts(job.get("transcript_path"))
        if counts:
            data["prompt_count"], data["tool_count"] = counts
    event = {
        "event_id": job["event_id"], "type": kind, "occurred_at": job["occurred_at"], "session_id": clip("session_id", sid),
        "user": group({"git_name": git(cwd, "config", "user.name"), "git_email": git(cwd, "config", "user.email"),
                       "os_user": os_user}),
        "client": group({"hostname": socket.gethostname(), "os": platform.system().lower(),
                         "plugin_version": version or plugin_version(), "claude_code_version": state.get("claude_code_version"),
                         "model": model}),
        "project": group({"repo_url": normalize_repo_url(git(cwd, "remote", "get-url", "origin")),
                          "branch": git(cwd, "rev-parse", "--abbrev-ref", "HEAD"),
                          "commit": git(cwd, "rev-parse", "--short", "HEAD"), "oro_version": oro_version(cwd)}),
        "data": data,
    }
    if kind == "session_end":
        drop_state(sid)
    return event


def post(event, url=None):
    """POST one event. No Origin header, no cookies (plain urllib opener); any error propagates."""
    body = json.dumps({"schema": SCHEMA, "events": [event]}).encode("utf-8")
    req = request.Request(url or ENDPOINT, data=body, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": "aaxis-oro-telemetry/%s" % (plugin_version() or "0")})
    with request.urlopen(req, timeout=TIMEOUT) as resp:
        resp.read(1024)


def send(job, poster=post):
    """Sender mode: build the event and POST it once. Never raises; any failure drops the event."""
    try:
        if not isinstance(job, dict) or job.get("type") not in TYPES or not job.get("session_id") or not job.get("event_id"):
            return False
        poster(build_event(job))
        return True
    except Exception:  # noqa: BLE001 - offline, 4xx/5xx, bad data: stay quiet
        return False


def main():
    if "--send" in sys.argv[1:]:
        try:
            send(json.load(sys.stdin))
        except Exception:  # noqa: BLE001
            pass
        return 0
    try:
        decide(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 - never block a session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
