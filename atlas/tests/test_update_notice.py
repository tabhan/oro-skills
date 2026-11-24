import json
import os
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
        write(U.cache_path(), {"checked_at": 1_000_000.0 - DAY + 60, "ok": True, "latest": "0.28.6"})
        self.assertIn("0.28.6", self.decide()["systemMessage"])
        self.assertEqual(self.calls, [])

    def test_stale_cache_spawns_but_still_notifies_from_it(self):
        write(U.cache_path(), {"checked_at": 1_000_000.0 - DAY - 1, "ok": True, "latest": "0.28.6"})
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


if __name__ == "__main__":
    unittest.main()
