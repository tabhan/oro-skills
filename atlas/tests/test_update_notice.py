import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
sys.path.insert(0, HOOKS)

import sessionstart_update as U  # noqa: E402

DAY = 24 * 3600


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(data, fh)


class CompareTest(unittest.TestCase):
    def test_semver_compare_is_numeric(self):
        self.assertTrue(U.newer("0.28.6", "0.28.5"))
        self.assertTrue(U.newer("0.30.0", "0.28.5"))
        self.assertTrue(U.newer("0.100.0", "0.99.9"))  # not a string compare
        self.assertTrue(U.newer("1.0.0", "0.99.99"))
        self.assertFalse(U.newer("0.28.5", "0.28.5"))
        self.assertFalse(U.newer("0.28.4", "0.28.5"))  # a dev checkout ahead of the remote stays quiet
        self.assertTrue(U.newer("v0.28.6", "0.28.5"))

    def test_garbage_never_compares_newer(self):
        for bad in (None, "", "abc", "1.2", 5, {}):
            self.assertFalse(U.newer(bad, "0.28.5"))
            self.assertFalse(U.newer("0.28.6", bad))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "home")
        self.root = os.path.join(self.tmp.name, "plugin")
        write(os.path.join(self.root, ".claude-plugin", "plugin.json"), {"version": "0.28.5"})
        self.clone = os.path.join(self.home, ".claude", "plugins", "marketplaces", "aaxis-oro")
        os.makedirs(self.clone)
        self._home, self._opt = os.environ.get("HOME"), os.environ.pop("AAXIS_ORO_NO_UPDATE_CHECK", None)
        os.environ["HOME"] = self.home
        self.calls = []

    def tearDown(self):
        os.environ["HOME"] = self._home
        if self._opt is not None:
            os.environ["AAXIS_ORO_NO_UPDATE_CHECK"] = self._opt
        self.tmp.cleanup()

    def cache(self):
        return U.read_json(U.cache_path())

    def spawner(self):
        def spawn():
            self.calls.append("spawn")
        return spawn

    def fetcher(self, version=None, error=None):
        def fetch(clone, deadline):
            self.calls.append(clone)
            if error:
                raise error
            return version
        return fetch

    def decide(self, now=1_000_000.0, payload=None):
        return U.decide(payload or {}, root=self.root, now=now, spawn=self.spawner())

    def refresh(self, fetch, now=1_000_000.0):
        U.refresh(now=now, fetch=fetch)


class DecideTest(Base):
    def test_notifies_with_upgrade_commands_from_cache(self):
        write(U.cache_path(), {"checked_at": 1_000_000.0, "ok": True, "latest": "0.28.6"})
        msg = self.decide()["systemMessage"]
        self.assertIn("0.28.6", msg)
        self.assertIn("claude plugin marketplace update aaxis-oro && claude plugin update aaxis-oro@aaxis-oro", msg)
        self.assertIn("./install.sh", msg)
        self.assertNotIn("\n", msg)
        self.assertEqual(self.calls, [])

    def test_silent_when_equal_or_older(self):
        write(U.cache_path(), {"checked_at": 1_000_000.0, "ok": True, "latest": "0.28.5"})
        self.assertIsNone(self.decide())
        write(U.cache_path(), {"checked_at": 1_000_000.0, "ok": True, "latest": "0.27.0"})
        self.assertIsNone(self.decide())

    def test_marketplace_clone_manifest_needs_no_network(self):
        write(os.path.join(self.clone, ".claude-plugin", "plugin.json"), {"version": "0.29.0"})
        write(U.cache_path(), {"checked_at": 1_000_000.0, "ok": True, "latest": "0.28.5"})
        self.assertIn("0.29.0", self.decide()["systemMessage"])
        self.assertEqual(self.calls, [])

    def test_opt_out_env_skips_everything(self):
        os.environ["AAXIS_ORO_NO_UPDATE_CHECK"] = "1"
        try:
            self.assertIsNone(self.decide())
        finally:
            del os.environ["AAXIS_ORO_NO_UPDATE_CHECK"]
        self.assertEqual(self.calls, [])
        self.assertEqual(self.cache(), {})

    def test_compact_is_skipped(self):
        self.assertIsNone(self.decide(payload={"source": "compact"}))
        self.assertEqual(self.calls, [])

    def test_no_marketplace_clone_means_no_spawn(self):
        os.rmdir(self.clone)
        self.assertIsNone(self.decide())
        self.assertEqual(self.calls, [])

    def test_bad_installed_manifest_is_silent(self):
        write(os.path.join(self.root, ".claude-plugin", "plugin.json"), {"version": "dev"})
        self.assertIsNone(self.decide())

    def test_hook_never_runs_git(self):
        real = subprocess.run
        subprocess.run = lambda *a, **k: self.fail("hook ran a subprocess")
        try:
            self.decide()
        finally:
            subprocess.run = real


class SpawnTest(Base):
    def test_no_cache_spawns_once_and_returns(self):
        self.assertIsNone(self.decide())
        self.assertEqual(self.calls, ["spawn"])

    def test_fresh_cache_does_not_spawn(self):
        write(U.cache_path(), {"checked_at": 1_000_000.0 - U.TTL + 60, "ok": True, "latest": "0.28.6"})
        self.assertIn("0.28.6", self.decide()["systemMessage"])
        self.assertEqual(self.calls, [])

    def test_stale_cache_spawns_but_still_notifies_from_it(self):
        write(U.cache_path(), {"checked_at": 1_000_000.0 - U.TTL - 1, "ok": True, "latest": "0.28.6"})
        self.assertIn("0.28.6", self.decide()["systemMessage"])
        self.assertEqual(self.calls, ["spawn"])

    def test_failure_backs_off_one_hour(self):
        write(U.cache_path(), {"checked_at": 1_000_000.0, "ok": False, "latest": None})
        self.decide(now=1_000_000.0 + 600)
        self.assertEqual(self.calls, [])
        self.decide(now=1_000_000.0 + 3601)
        self.assertEqual(self.calls, ["spawn"])

    def test_fresh_lock_prevents_a_second_spawn(self):
        os.makedirs(os.path.dirname(U.lock_path()), exist_ok=True)
        open(U.lock_path(), "w").close()
        os.utime(U.lock_path(), (1_000_000.0 - 10, 1_000_000.0 - 10))
        self.decide()
        self.assertEqual(self.calls, [])
        os.utime(U.lock_path(), (1_000_000.0 - U.LOCK_TTL - 1,) * 2)  # stale lock
        self.decide()
        self.assertEqual(self.calls, ["spawn"])

    def test_corrupt_cache_is_ignored(self):
        os.makedirs(os.path.dirname(U.cache_path()), exist_ok=True)
        with open(U.cache_path(), "w") as fh:
            fh.write("{not json")
        self.assertIsNone(self.decide())
        self.assertEqual(self.calls, ["spawn"])

    def test_spawn_failure_is_silent(self):
        def boom():
            raise OSError("no fork")
        self.assertIsNone(U.decide({}, root=self.root, now=1_000_000.0, spawn=boom))

    def test_real_spawner_is_detached_with_devnull(self):
        seen = {}

        class P:
            def __init__(self, cmd, **kw):
                seen.update(cmd=cmd, **kw)
        real = subprocess.Popen
        subprocess.Popen = P
        try:
            U.spawn_refresher()
        finally:
            subprocess.Popen = real
        self.assertEqual(seen["cmd"][-1], "--refresh")
        self.assertTrue(seen["start_new_session"] and seen["close_fds"])
        for k in ("stdin", "stdout", "stderr"):
            self.assertEqual(seen[k], subprocess.DEVNULL)


class RefreshTest(Base):
    def test_success_writes_cache_and_releases_lock(self):
        self.refresh(self.fetcher("0.28.6"))
        self.assertEqual(self.cache(), {"checked_at": 1_000_000.0, "ok": True, "latest": "0.28.6"})
        self.assertFalse(os.path.exists(U.lock_path()))
        self.assertEqual([f for f in os.listdir(os.path.dirname(U.cache_path())) if f.startswith(".aaxis")], [])
        self.assertIn("0.28.6", self.decide()["systemMessage"])

    def test_failures_are_silent_and_keep_known_latest(self):
        write(U.cache_path(), {"checked_at": 0, "ok": True, "latest": "0.28.6"})
        for err in (RuntimeError("no access"), TimeoutError("slow"), OSError("offline"), ValueError("x")):
            self.refresh(self.fetcher(error=err))
            self.assertEqual((self.cache()["ok"], self.cache()["latest"]), (False, "0.28.6"))
            self.assertFalse(os.path.exists(U.lock_path()))

    def test_garbage_version_is_a_failure(self):
        self.refresh(self.fetcher("not-a-version"))
        self.assertFalse(self.cache()["ok"])

    def test_live_lock_blocks_a_concurrent_refresher(self):
        self.assertTrue(U.acquire_lock(1_000_000.0))
        self.refresh(self.fetcher("0.28.6"))
        self.assertEqual((self.calls, self.cache()), ([], {}))

    def test_stale_lock_is_taken_over(self):
        self.assertTrue(U.acquire_lock(1_000_000.0))
        os.utime(U.lock_path(), (1_000_000.0 - U.LOCK_TTL - 1,) * 2)
        self.refresh(self.fetcher("0.28.6"))
        self.assertEqual(self.cache()["latest"], "0.28.6")

    def test_no_clone_does_nothing(self):
        os.rmdir(self.clone)
        self.refresh(self.fetcher("0.28.6"))
        self.assertEqual((self.calls, self.cache()), ([], {}))

    def test_unwritable_cache_does_not_raise(self):
        os.makedirs(os.path.dirname(U.cache_path()), exist_ok=True)
        os.makedirs(U.cache_path())  # a directory where the file should go
        self.refresh(self.fetcher("0.28.6"))
        self.assertFalse(os.path.exists(U.lock_path()))


class ProcessTest(Base):
    """Real process and real git against a local origin: no network, no credential prompt."""

    def run_hook(self, stdin="{}", args=()):
        env = dict(os.environ, HOME=self.home)
        env.pop("AAXIS_ORO_NO_UPDATE_CHECK", None)
        script = os.path.join(HOOKS, "sessionstart_update.py")
        return subprocess.run([sys.executable, script, *args], input=stdin, capture_output=True, text=True, env=env, timeout=60)

    def make_origin(self, version):
        origin = os.path.join(self.tmp.name, "origin")
        os.makedirs(origin)
        write(os.path.join(origin, ".claude-plugin", "plugin.json"), {"version": version})
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        for cmd in (["init", "-q"], ["add", "."], ["commit", "-qm", "v"]):
            subprocess.run(["git"] + cmd, cwd=origin, env=env, check=True, capture_output=True)
        subprocess.run(["git", "clone", "-q", origin, self.clone + "-tmp"], check=True, capture_output=True)
        os.rmdir(self.clone)
        os.rename(self.clone + "-tmp", self.clone)
        # the clone is stale: its own manifest says nothing newer, only the origin does
        write(os.path.join(self.clone, ".claude-plugin", "plugin.json"), {"version": "0.28.5"})

    def test_real_git_fetch_reads_the_origin_version(self):
        self.make_origin("0.28.9")
        self.assertEqual(U.remote_version(self.clone, time.monotonic() + 10), "0.28.9")

    def test_refresher_mode_runs_synchronously_against_a_local_origin(self):
        self.make_origin("0.28.9")
        p = self.run_hook("", args=("--refresh",))
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))
        self.assertEqual(self.cache()["latest"], "0.28.9")
        self.assertTrue(self.cache()["ok"])
        self.assertFalse(os.path.exists(U.lock_path()))
        # the marketplace clone itself was not modified
        self.assertEqual(U.manifest_version(os.path.join(self.clone, ".claude-plugin", "plugin.json")), "0.28.5")

    def test_broken_origin_refresher_exits_zero_and_records_failure(self):
        self.make_origin("0.28.9")
        subprocess.run(["git", "remote", "set-url", "origin", "/nonexistent/repo"], cwd=self.clone, check=True)
        p = self.run_hook("", args=("--refresh",))
        self.assertEqual((p.returncode, p.stdout), (0, ""))
        self.assertFalse(self.cache()["ok"])

    def test_hook_main_prints_one_json_line_from_cache_without_spawning(self):
        write(U.cache_path(), {"checked_at": time.time(), "ok": True, "latest": "0.99.0"})
        p = self.run_hook()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.count("\n"), 0)
        self.assertIn("0.99.0", json.loads(p.stdout)["systemMessage"])

    def test_garbage_stdin_exits_zero_silently(self):
        write(U.cache_path(), {"checked_at": time.time(), "ok": True, "latest": "0.1.0"})  # fresh: nothing spawned
        for stdin in ("", "not json", "[]"):
            p = self.run_hook(stdin)
            self.assertEqual((p.returncode, p.stdout), (0, ""))

    def test_dispatcher_stays_silent_without_a_marketplace_clone(self):
        os.rmdir(self.clone)
        p = subprocess.run([sys.executable, os.path.join(HOOKS, "sessionstart.py")], input=json.dumps({"source": "startup", "cwd": self.tmp.name}),
                           capture_output=True, text=True, env=dict(os.environ, HOME=self.home), timeout=30)
        self.assertEqual((p.returncode, p.stdout), (0, ""))


class AutoUpdateBase(Base):
    """The plugin is installed through the marketplace (user + local scope for self.proj) and a `claude` binary exists."""

    def setUp(self):
        super().setUp()
        self.proj = os.path.join(self.tmp.name, "proj")
        os.makedirs(self.proj)
        self.record("0.28.5")
        self._claude, self._noauto = U.find_claude, os.environ.pop("AAXIS_ORO_NO_AUTO_UPDATE", None)
        U.find_claude = lambda: "/stub/claude"
        self.runs = []

    def tearDown(self):
        U.find_claude = self._claude
        os.environ.pop("AAXIS_ORO_NO_AUTO_UPDATE", None)
        if self._noauto is not None:
            os.environ["AAXIS_ORO_NO_AUTO_UPDATE"] = self._noauto
        super().tearDown()

    def record(self, version, scopes=("user", "local")):
        entries = [{"scope": sc, "version": version, "installPath": "/x", **({"projectPath": self.proj} if sc == "local" else {})}
                   for sc in scopes]
        write(os.path.join(self.home, ".claude", "plugins", "installed_plugins.json"), {"version": 2, "plugins": {U.PLUGIN_ID: entries}})

    def updater(self, to="0.29.0", ok=True):
        def update(installed, cwd, now):
            self.runs.append((installed, cwd))
            return {"from": installed, "to": to if ok else installed, "ok": ok, "ts": now, "scopes": ["user"], "announced": False,
                    **({} if ok else {"error": "boom"})}
        return update

    def go(self, fetch_version="0.29.0", now=1_000_000.0, **kw):
        U.refresh(now=now, fetch=self.fetcher(fetch_version), cwd=self.proj, root=self.root, **kw)
        self.calls.clear()  # the fetcher's own call is not what the decide tests count


class AutoUpdateDecideTest(AutoUpdateBase):
    def test_update_due_spawns_even_with_a_fresh_cache_and_stays_quiet(self):
        write(U.cache_path(), {"checked_at": 1_000_000.0, "ok": True, "latest": "0.29.0"})
        self.assertIsNone(self.decide())  # the background update will handle it: no notice
        self.assertEqual(self.calls, ["spawn"])

    def test_success_is_announced_once_with_restart_hint(self):
        self.go(update=self.updater())
        self.assertEqual(self.cache()["update"]["to"], "0.29.0")
        msg = self.decide(now=1_000_100.0)["systemMessage"]
        self.assertEqual(msg, "[aaxis-oro] updated 0.28.5\u21920.29.0 (restart to apply)")
        self.assertIsNone(self.decide(now=1_000_200.0))  # told once, no notice either: restart pending
        self.assertEqual(self.calls, [])

    def test_no_restart_hint_when_this_session_already_runs_the_new_version(self):
        self.go(update=self.updater())
        write(os.path.join(self.root, ".claude-plugin", "plugin.json"), {"version": "0.29.0"})
        self.assertEqual(self.decide(now=1_000_100.0)["systemMessage"], "[aaxis-oro] updated 0.28.5\u21920.29.0")

    def test_failed_update_falls_back_to_the_manual_notice_and_retries_after_an_hour(self):
        self.go(update=self.updater(ok=False))
        self.assertFalse(self.cache()["ok"])
        msg = self.decide(now=1_000_600.0)["systemMessage"]
        self.assertIn("claude plugin marketplace update aaxis-oro", msg)
        self.assertEqual(self.calls, [])
        self.decide(now=1_000_000.0 + U.RETRY + 1)
        self.assertEqual(self.calls, ["spawn"])

    def test_opt_out_auto_update_keeps_the_notice_only(self):
        os.environ["AAXIS_ORO_NO_AUTO_UPDATE"] = "1"
        write(U.cache_path(), {"checked_at": 1_000_000.0, "ok": True, "latest": "0.29.0"})
        self.assertIn("0.29.0", self.decide()["systemMessage"])
        self.assertEqual(self.calls, [])
        self.go(update=self.updater())
        self.assertEqual(self.runs, [])
        self.assertNotIn("update", self.cache())

    def test_opt_out_update_check_does_nothing(self):
        os.environ["AAXIS_ORO_NO_UPDATE_CHECK"] = "1"
        try:
            self.assertIsNone(self.decide())
        finally:
            del os.environ["AAXIS_ORO_NO_UPDATE_CHECK"]
        self.assertEqual((self.calls, self.cache()), ([], {}))

    def test_subagents_are_skipped(self):
        write(U.cache_path(), {"checked_at": 0, "ok": True, "latest": "0.29.0"})
        self.assertIsNone(self.decide(payload={"agent_id": "a1"}))
        self.assertEqual(self.calls, [])

    def test_missing_claude_binary_keeps_the_notice(self):
        U.find_claude = lambda: None
        write(U.cache_path(), {"checked_at": 1_000_000.0, "ok": True, "latest": "0.29.0"})
        self.assertIn("0.29.0", self.decide()["systemMessage"])
        self.assertEqual(self.calls, [])
        self.go(update=self.updater())
        self.assertEqual(self.runs, [])

    def test_no_marketplace_install_keeps_the_notice(self):
        os.remove(os.path.join(self.home, ".claude", "plugins", "installed_plugins.json"))
        write(U.cache_path(), {"checked_at": 1_000_000.0, "ok": True, "latest": "0.29.0"})
        self.assertIn("0.29.0", self.decide()["systemMessage"])


class AutoUpdateRefreshTest(AutoUpdateBase):
    def test_rate_limit(self):
        up = {"ok": True, "to": "0.29.0", "ts": 1_000_000.0}
        self.assertFalse(U.update_due({"update": up}, "0.29.0", "0.28.5", 1_000_100.0))  # already there
        self.assertFalse(U.update_due({"update": up}, "0.29.1", "0.28.5", 1_000_100.0))  # newer, but inside the 6h window
        self.assertTrue(U.update_due({"update": up}, "0.29.1", "0.28.5", 1_000_000.0 + U.TTL))
        bad = {"ok": False, "ts": 1_000_000.0}
        self.assertFalse(U.update_due({"update": bad}, "0.29.0", "0.28.5", 1_000_000.0 + 60))
        self.assertTrue(U.update_due({"update": bad}, "0.29.0", "0.28.5", 1_000_000.0 + U.RETRY))
        self.assertFalse(U.update_due({}, "0.28.5", "0.28.5", 1_000_000.0))  # nothing newer

    def test_refresher_updates_once_and_not_again_inside_the_window(self):
        self.go(update=self.updater())
        self.go(fetch_version="0.29.0", now=1_000_000.0 + 60, update=self.updater())
        self.assertEqual(self.runs, [("0.28.5", self.proj)])

    def test_lock_blocks_a_second_update(self):
        self.assertTrue(U.acquire_lock(1_000_000.0))
        self.go(update=self.updater())
        self.assertEqual((self.runs, self.cache()), ([], {}))
        self.assertTrue(os.path.exists(U.lock_path()))

    def test_check_failure_keeps_the_last_update_record(self):
        self.go(update=self.updater())
        U.refresh(now=1_000_000.0 + U.TTL + 5, fetch=self.fetcher(error=OSError("offline")), cwd=self.proj, root=self.root)
        self.assertEqual(self.cache()["update"]["to"], "0.29.0")
        self.assertFalse(self.cache()["ok"])

    def test_current_clone_manifest_counts_as_target(self):
        write(os.path.join(self.clone, ".claude-plugin", "plugin.json"), {"version": "0.29.0"})
        self.go(fetch_version="0.28.5", update=self.updater())  # remote check lags, the clone already knows 0.29.0
        self.assertEqual(len(self.runs), 1)


class DoUpdateTest(AutoUpdateBase):
    def stub(self, new="0.29.0", fail_on=None):
        def run(claude, args, cwd=None):
            self.runs.append((args, cwd))
            if fail_on and args[0] == fail_on:
                raise RuntimeError("x")
            return {"newVersion": new} if args[0] == "update" else {}
        return run

    def test_marketplace_refresh_then_each_scope_with_its_project(self):
        rec = U.do_update("0.28.5", os.path.join(self.proj, "sub"), 5.0, run=self.stub(), claude="/c")
        self.assertEqual(self.runs, [(["marketplace", "update", "aaxis-oro"], None),
                                     (["update", "aaxis-oro@aaxis-oro", "--scope", "user", "--json"], None),
                                     (["update", "aaxis-oro@aaxis-oro", "--scope", "local", "--json"], self.proj)])
        self.assertEqual((rec["ok"], rec["from"], rec["to"], rec["scopes"]), (True, "0.28.5", "0.29.0", ["user", "local"]))

    def test_other_projects_local_scope_is_left_alone(self):
        rec = U.do_update("0.28.5", self.tmp.name, 5.0, run=self.stub(), claude="/c")
        self.assertEqual(rec["scopes"], ["user"])

    def test_failures_are_recorded_not_raised(self):
        self.assertFalse(U.do_update("0.28.5", self.proj, 5.0, run=self.stub(fail_on="marketplace"), claude="/c")["ok"])
        rec = U.do_update("0.28.5", self.proj, 5.0, run=self.stub(fail_on="update"), claude="/c")
        self.assertEqual((rec["ok"], rec["to"]), (False, "0.28.5"))
        self.assertFalse(U.do_update("0.28.5", self.proj, 5.0, run=self.stub(new="0.28.5"), claude="/c")["ok"])

    def test_claude_run_uses_no_prompt_no_stdin_and_a_timeout(self):
        seen = {}

        class R:
            returncode, stdout = 0, 'noise\n{"outcome":"ok","newVersion":"0.29.0"}\n'

        def fake(cmd, **kw):
            seen.update(cmd=cmd, **kw)
            return R()
        real = subprocess.run
        subprocess.run = fake
        try:
            info = U.claude_run("/c", ["update", "x"], cwd="/p")
        finally:
            subprocess.run = real
        self.assertEqual(info["newVersion"], "0.29.0")
        self.assertEqual((seen["cmd"], seen["cwd"], seen["stdin"], seen["timeout"]), (["/c", "plugin", "update", "x"], "/p", subprocess.DEVNULL, U.UPDATE_TIMEOUT))
        self.assertEqual(seen["env"]["GIT_TERMINAL_PROMPT"], "0")
        self.assertIn("BatchMode=yes", seen["env"]["GIT_SSH_COMMAND"])

    def test_nonzero_exit_raises(self):
        class R:
            returncode, stdout = 1, ""
        real = subprocess.run
        subprocess.run = lambda *a, **k: R()
        try:
            with self.assertRaises(RuntimeError):
                U.claude_run("/c", ["update", "x"])
        finally:
            subprocess.run = real


class StubClaudeProcessTest(AutoUpdateBase):
    """Real refresher process with a stub `claude` on PATH and a local git origin."""

    def test_refresher_updates_through_the_stub_and_the_next_session_says_so(self):
        origin = os.path.join(self.tmp.name, "origin")
        os.makedirs(origin)
        write(os.path.join(origin, ".claude-plugin", "plugin.json"), {"version": "0.29.0"})
        genv = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        for cmd in (["init", "-q"], ["add", "."], ["commit", "-qm", "v"]):
            subprocess.run(["git"] + cmd, cwd=origin, env=genv, check=True, capture_output=True)
        subprocess.run(["git", "clone", "-q", origin, self.clone + "-tmp"], check=True, capture_output=True)
        os.rmdir(self.clone)
        os.rename(self.clone + "-tmp", self.clone)
        bindir, log = os.path.join(self.tmp.name, "bin"), os.path.join(self.tmp.name, "calls.log")
        os.makedirs(bindir)
        stub = os.path.join(bindir, "claude")
        with open(stub, "w") as fh:
            fh.write("#!/bin/sh\necho \"$PWD|$*|$GIT_TERMINAL_PROMPT\" >> %s\n"
                     "case \"$2\" in update) echo '{\"outcome\":\"ok\",\"newVersion\":\"0.29.0\"}';; *) echo '{\"outcome\":\"ok\"}';; esac\n" % log)
        os.chmod(stub, 0o755)
        env = dict(os.environ, HOME=self.home, PATH=bindir + os.pathsep + os.environ["PATH"])
        for k in ("AAXIS_ORO_NO_UPDATE_CHECK", "AAXIS_ORO_NO_AUTO_UPDATE"):
            env.pop(k, None)
        script = os.path.join(HOOKS, "sessionstart_update.py")
        root_script = os.path.join(self.root, "atlas", "hooks")
        os.makedirs(root_script)
        shutil.copy(script, root_script)
        script = os.path.join(root_script, "sessionstart_update.py")
        p = subprocess.run([sys.executable, script, "--refresh"], cwd=self.proj, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))
        with open(log) as fh:
            calls = fh.read().splitlines()
        self.assertEqual([c.split("|")[1] for c in calls], ["plugin marketplace update aaxis-oro", "plugin update aaxis-oro@aaxis-oro --scope user --json",
                                                           "plugin update aaxis-oro@aaxis-oro --scope local --json"])
        self.assertTrue(all(c.endswith("|0") for c in calls))
        self.assertEqual(os.path.realpath(calls[2].split("|")[0]), os.path.realpath(self.proj))
        self.assertTrue(self.cache()["update"]["ok"])
        q = subprocess.run([sys.executable, script], input="{}", cwd=self.proj, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(json.loads(q.stdout)["systemMessage"], "[aaxis-oro] updated 0.28.5\u21920.29.0 (restart to apply)")


if __name__ == "__main__":
    unittest.main()
