#!/usr/bin/env python3
"""SessionStart hook: keeps the aaxis-oro plugin current, and says so in one line.

Native autoUpdate was spiked and rejected: Claude Code runs it only in an interactive session, after a random 0-10 minute
delay on an unref'd timer, so short sessions and `-p` never update. This hook does the update itself, in the background.
The hook never touches the network. Installed version: this copy's .claude-plugin/plugin.json. Latest version: the
highest of the marketplace clone (~/.claude/plugins/marketplaces/<name>/.claude-plugin/plugin.json) and the cached result
of the last remote check (~/.claude/aaxis-oro-update-check.json, which also holds the last update result).
When that cache is stale (6h after a success, 1h after a failure) or an update is due, the hook spawns a fully detached
refresher (this script with --refresh) and returns at once. The refresher does a depth-1 `git fetch` of the clone's own
origin into a throwaway bare repo; when that is newer than the installed version and the plugin is installed through the
marketplace, it runs `claude plugin marketplace update` then `claude plugin update --scope S` for the user scope and for
the current project's local/project scope, and records {from,to,ok,ts,scopes} in the cache. The next session prints
"updated X->Y (restart to apply)" once. Old version directories are never deleted. Without a `claude` binary, without a
marketplace install, or after a failed update the plain upgrade notice (with the manual command) is shown instead, and
the update is retried after 1h. A lock file keeps concurrent sessions from stacking refreshers. Skipped in subagents.
Opt out: AAXIS_ORO_NO_AUTO_UPDATE=1 (notice only), AAXIS_ORO_NO_UPDATE_CHECK=1 (everything).
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
TTL = 6 * 3600
RETRY = 3600  # after a failed remote check (offline, no access) wait this long before trying again
BUDGET = 30  # refresher: total seconds for the whole fetch
UPDATE_TIMEOUT = 120  # refresher: hard limit per `claude plugin ...` call
PLUGIN_ID = NAME + "@" + NAME
CONNECT_TIMEOUT = 10
LOCK_TTL = 600  # a refresher lock older than this is stale (crashed refresher)
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


def find_claude():
    """The `claude` binary: PATH first, then the usual install spots. None when absent."""
    found = shutil.which("claude")
    if found:
        return found
    for rel in (".claude/local/claude", ".local/bin/claude"):
        path = os.path.join(os.path.expanduser("~"), rel)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def installs():
    """The marketplace install records of this plugin (installed_plugins.json), [] when there are none."""
    data = read_json(os.path.join(claude_dir(), "plugins", "installed_plugins.json")).get("plugins")
    entries = data.get(PLUGIN_ID) if isinstance(data, dict) else None
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def within(path, project):
    try:
        path, project = os.path.realpath(path), os.path.realpath(project)
    except (OSError, ValueError, TypeError):
        return False
    return path == project or path.startswith(project.rstrip(os.sep) + os.sep)


def scopes_for(cwd):
    """[(scope, project_dir_or_None)] to update: user, plus a local/project install recorded for the current project."""
    out = []
    for entry in installs():
        scope, project = entry.get("scope"), entry.get("projectPath")
        if scope == "user" and ("user", None) not in out:
            out.append(("user", None))
        elif scope in ("local", "project") and project and cwd and within(cwd, project) and (scope, project) not in out:
            out.append((scope, project))
    return out


def auto_update_on():
    return not os.environ.get("AAXIS_ORO_NO_AUTO_UPDATE")


def can_auto_update():
    """Auto-update is wanted, the plugin is installed through the marketplace and a `claude` binary exists."""
    return auto_update_on() and bool(installs()) and find_claude() is not None


def update_env():
    env = git_env()
    env["AAXIS_ORO_NO_UPDATE_CHECK"] = "1"
    return env


def claude_run(claude, args, cwd=None):
    """One `claude plugin ...` call: no stdin, no prompt, hard timeout. Returns the parsed last JSON line (or {})."""
    out = subprocess.run([claude, "plugin"] + args, cwd=cwd or None, env=update_env(), capture_output=True, text=True,
                         timeout=UPDATE_TIMEOUT, stdin=subprocess.DEVNULL)
    lines = [ln for ln in (out.stdout or "").splitlines() if ln.strip().startswith("{")]
    try:
        info = json.loads(lines[-1]) if lines else {}
    except ValueError:
        info = {}
    if out.returncode or info.get("outcome") not in (None, "ok"):
        raise RuntimeError("claude plugin %s failed (rc %s)" % (args[0], out.returncode))
    return info


def do_update(installed, cwd, now, run=claude_run, claude=None):
    """Refresh the marketplace clone, then update every applicable scope. Returns the state record; never raises."""
    rec = {"from": installed, "to": installed, "ok": False, "ts": now, "scopes": [], "announced": False}
    claude = claude or find_claude()
    scopes = scopes_for(cwd)
    if not claude:
        rec["error"] = "claude binary not found"
        return rec
    if not scopes:
        rec["error"] = "no user or current-project install"
        return rec
    try:
        run(claude, ["marketplace", "update", NAME])
        newest = installed
        for scope, project in scopes:
            info = run(claude, ["update", PLUGIN_ID, "--scope", scope, "--json"], cwd=project)
            rec["scopes"].append(scope)
            if parse(info.get("newVersion")) and newer(info.get("newVersion"), newest):
                newest = info["newVersion"]
        rec["to"], rec["ok"] = newest, newer(newest, installed)
        if not rec["ok"]:
            rec["error"] = "no newer version installed"
    except Exception as exc:  # noqa: BLE001 - timeout, offline, auth: the notice takes over, retry later
        rec["error"] = str(exc)[:200]
    return rec


def update_due(cache, latest, installed, now):
    """An update should be attempted: a newer version is known and no usable attempt (or a failed one past the backoff)."""
    if not newer(latest, installed):
        return False
    upd = cache.get("update") or {}
    try:
        age = now - float(upd.get("ts") or 0)
    except (TypeError, ValueError):
        age = RETRY
    if upd.get("ok") and not newer(latest, upd.get("to")):
        return False  # already updated to (at least) that version; restart pending
    return not upd or age >= (TTL if upd.get("ok") else RETRY)


def refresh(now=None, fetch=remote_version, update=do_update, cwd=None, root=ROOT):
    """Background mode: one remote check and, when newer and possible, the update. Cache written atomically. Never raises."""
    now = time.time() if now is None else now
    clone = marketplace_dir()
    if not os.path.isdir(clone) or not acquire_lock(now):
        return
    try:
        cache = read_json(cache_path())
        keep = {k: cache[k] for k in ("update",) if k in cache}
        try:
            got = fetch(clone, time.monotonic() + BUDGET)
            if parse(got) is None:
                raise ValueError("no version")
        except Exception:  # noqa: BLE001 - offline, no access, timeout: stay quiet, retry later
            write_cache(dict({"checked_at": now, "ok": False, "latest": cache.get("latest")}, **keep))
            return
        installed = manifest_version(os.path.join(root, ".claude-plugin", "plugin.json"))
        data = {"checked_at": now, "ok": True, "latest": got}
        target = max([v for v in (got, manifest_version(os.path.join(clone, ".claude-plugin", "plugin.json"))) if parse(v)], key=parse)
        if can_auto_update() and update_due(cache, target, installed, now):
            rec = update(installed, cwd if cwd is not None else os.getcwd(), now)
            keep["update"] = rec
            data["ok"] = rec["ok"]  # a failed update retries after RETRY, like a failed check
        write_cache(dict(data, **keep))
    finally:
        release_lock()


def known_latest(cache):
    """Highest version known locally: the marketplace clone's manifest and the cached remote check."""
    known = [c for c in (manifest_version(os.path.join(marketplace_dir(), ".claude-plugin", "plugin.json")), cache.get("latest")) if parse(c)]
    return max(known, key=parse) if known else None


def maybe_spawn(cache, now, spawn, due):
    """Start the refresher when the cache is stale or an update is due, unless one runs or there is no clone."""
    if (due or stale(cache, now)) and os.path.isdir(marketplace_dir()) and not lock_fresh(now):
        try:
            spawn()
        except Exception:  # noqa: BLE001 - cannot spawn: stay quiet
            pass


def announce(cache, installed):
    """One line for an update the background refresher finished and this user has not been told about yet."""
    upd = cache.get("update") or {}
    if not (upd.get("ok") and not upd.get("announced") and parse(upd.get("to"))):
        return None
    cache["update"] = dict(upd, announced=True)
    write_cache(cache)
    tail = " (restart to apply)" if newer(upd["to"], installed) else ""
    return "[aaxis-oro] updated %s\u2192%s%s" % (upd.get("from"), upd["to"], tail)


def decide(payload, root=ROOT, now=None, spawn=spawn_refresher):
    if os.environ.get("AAXIS_ORO_NO_UPDATE_CHECK"):
        return None
    payload = payload if isinstance(payload, dict) else {}
    if payload.get("source") == "compact" or payload.get("agent_id"):
        return None  # compact and subagents: nothing to say, nothing to start
    installed = manifest_version(os.path.join(root, ".claude-plugin", "plugin.json"))
    if parse(installed) is None:
        return None
    now = time.time() if now is None else now
    cache = read_json(cache_path())
    auto = can_auto_update()
    latest = known_latest(cache)
    maybe_spawn(cache, now, spawn, auto and update_due(cache, latest, installed, now))
    if auto:
        said = announce(cache, installed)
        if said:
            return {"systemMessage": said}
    upd = cache.get("update") or {}
    updating = auto and not (upd and not upd.get("ok"))  # a failed attempt hands over to the manual notice
    if latest and newer(latest, installed) and not updating:
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
