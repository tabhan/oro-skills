#!/usr/bin/env python3
"""SessionStart hook: one-line notice when a newer aaxis-oro plugin version exists. Never updates anything.

The hook itself never touches the network. Installed version: this copy's .claude-plugin/plugin.json. Latest version:
the highest of the marketplace clone Claude Code keeps (~/.claude/plugins/marketplaces/<name>/.claude-plugin/plugin.json)
and the cached result of the last remote check (~/.claude/aaxis-oro-update-check.json).
When that cache is stale (24h after a success, 1h after a failure) the hook spawns a fully detached background refresher
(this script with --refresh) and returns at once. The refresher does a depth-1 `git fetch` of the clone's own origin (same
URL and credentials Claude Code cloned with) into a throwaway bare repo, within a ~30s budget, and writes the cache
atomically. A version found by the refresher is therefore announced on the next session. The repo carries no release
tags (the version lives only in plugin.json on main), so `ls-remote --tags` cannot answer.
Any failure is silent. A lock file keeps concurrent sessions from stacking refreshers. The marketplace clone is never
modified. Opt out with AAXIS_ORO_NO_UPDATE_CHECK=1.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

NAME = "aaxis-oro"
TTL = 24 * 3600
RETRY = 3600  # after a failed remote check (offline, no access) wait this long before trying again
BUDGET = 30  # refresher: total seconds for the whole fetch
CONNECT_TIMEOUT = 10
LOCK_TTL = 120  # a refresher lock older than this is stale (crashed refresher)
NOTICE = ("[aaxis-oro] version %s is available (installed %s). Upgrade: `claude plugin marketplace update aaxis-oro && "
          "claude plugin update aaxis-oro@aaxis-oro`, or run ./install.sh in your checkout.")


def parse(version):
    """(major, minor, patch) from 'X.Y.Z' (a leading v and any -pre/+build suffix are ignored), else None."""
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", str(version or "").strip())
    return tuple(int(g) for g in m.groups()) if m else None


def newer(latest, installed):
    a, b = parse(latest), parse(installed)
    return a is not None and b is not None and a > b


def claude_dir():
    return os.path.join(os.path.expanduser("~"), ".claude")


def cache_path():
    return os.path.join(claude_dir(), "aaxis-oro-update-check.json")


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def manifest_version(path):
    return read_json(path).get("version")


def write_cache(data):
    tmp = None
    try:
        os.makedirs(claude_dir(), exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".aaxis-oro-update-check.", dir=claude_dir())
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, cache_path())
        tmp = None
    except OSError:
        pass
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass


def lock_path():
    return os.path.join(claude_dir(), "aaxis-oro-update-check.lock")


def lock_fresh(now):
    try:
        return now - os.path.getmtime(lock_path()) < LOCK_TTL
    except OSError:
        return False


def acquire_lock(now):
    """True when this process now owns the refresher lock (a stale lock is taken over)."""
    try:
        os.makedirs(claude_dir(), exist_ok=True)
        if os.path.exists(lock_path()) and not lock_fresh(now):
            os.remove(lock_path())
        os.close(os.open(lock_path(), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        return True
    except OSError:
        return False


def release_lock():
    try:
        os.remove(lock_path())
    except OSError:
        pass


def marketplace_dir():
    plugins = os.path.join(claude_dir(), "plugins")
    known = read_json(os.path.join(plugins, "known_marketplaces.json")).get(NAME)
    loc = known.get("installLocation") if isinstance(known, dict) else None
    return loc or os.path.join(plugins, "marketplaces", NAME)


def git_env():
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="true", SSH_ASKPASS="true", GCM_INTERACTIVE="never")
    env.pop("DISPLAY", None)
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=%d" % CONNECT_TIMEOUT)
    return env


def git(args, cwd, deadline):
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError("budget used")
    out = subprocess.run(["git"] + args, cwd=cwd, env=git_env(), capture_output=True, text=True, timeout=left,
                         stdin=subprocess.DEVNULL)
    if out.returncode:
        raise RuntimeError("git %s failed" % args[0])
    return out.stdout


def remote_version(clone, deadline):
    """plugin.json version at the origin's HEAD, fetched into a throwaway bare repo (the clone is not touched)."""
    url = git(["remote", "get-url", "origin"], clone, deadline).strip()
    tmp = tempfile.mkdtemp(prefix="aaxis-oro-update-")
    try:
        git(["init", "-q", "--bare", tmp], None, deadline)
        git(["fetch", "-q", "--depth=1", "--no-tags", url, "HEAD"], tmp, deadline)
        return json.loads(git(["show", "FETCH_HEAD:.claude-plugin/plugin.json"], tmp, deadline)).get("version")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def stale(cache, now):
    try:
        age = now - float(cache.get("checked_at") or 0)
    except (TypeError, ValueError):
        return True
    return age >= (TTL if cache.get("ok", True) else RETRY)


def spawn_refresher():
    """Start `sessionstart_update.py --refresh` fully detached; the hook does not wait for it."""
    subprocess.Popen([sys.executable, os.path.realpath(__file__), "--refresh"], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)


def refresh(now=None, fetch=remote_version):
    """Background mode: one remote check, cache written atomically. Never raises."""
    now = time.time() if now is None else now
    clone = marketplace_dir()
    if not os.path.isdir(clone) or not acquire_lock(now):
        return
    try:
        cache = read_json(cache_path())
        try:
            got = fetch(clone, time.monotonic() + BUDGET)
            if parse(got) is None:
                raise ValueError("no version")
            write_cache({"checked_at": now, "ok": True, "latest": got})
        except Exception:  # noqa: BLE001 - offline, no access, timeout: stay quiet, retry later
            write_cache({"checked_at": now, "ok": False, "latest": cache.get("latest")})
    finally:
        release_lock()


def latest_version(now, spawn=spawn_refresher):
    """Highest version known from the local clone and the cache; spawns the refresher when the cache is stale."""
    clone = marketplace_dir()
    cache = read_json(cache_path())
    if stale(cache, now) and os.path.isdir(clone) and not lock_fresh(now):
        try:
            spawn()
        except Exception:  # noqa: BLE001 - cannot spawn: stay quiet
            pass
    known = [c for c in (manifest_version(os.path.join(clone, ".claude-plugin", "plugin.json")), cache.get("latest")) if parse(c)]
    return max(known, key=parse) if known else None


def decide(payload, root=ROOT, now=None, spawn=spawn_refresher):
    if os.environ.get("AAXIS_ORO_NO_UPDATE_CHECK"):
        return None
    if isinstance(payload, dict) and payload.get("source") == "compact":
        return None
    installed = manifest_version(os.path.join(root, ".claude-plugin", "plugin.json"))
    if parse(installed) is None:
        return None
    latest = latest_version(time.time() if now is None else now, spawn)
    if latest and newer(latest, installed):
        return {"systemMessage": NOTICE % (latest, installed)}
    return None


def main():
    if "--refresh" in sys.argv[1:]:
        try:
            if not os.environ.get("AAXIS_ORO_NO_UPDATE_CHECK"):
                refresh()
        except Exception:  # noqa: BLE001
            pass
        return 0
    out = None
    try:
        out = decide(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 - never block a session
        pass
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
