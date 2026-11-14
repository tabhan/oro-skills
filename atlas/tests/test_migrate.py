import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["ATLAS_NO_AUTOBUILD"] = "1"

from atlas import build, extractors, index, migrate, store  # noqa: E402
from atlas.common import atlas_dir  # noqa: E402
from tests.test_core import make_project  # noqa: E402

HOOK = os.path.join(os.path.dirname(__file__), "..", "hooks", "sessionstart_migrate.py")


def fake_build(ctx, only=None, out=None):
    """Stands in for the PHP-backed full build: every known shard gets one record."""
    names = sorted(extractors.load_all())
    for name in names:
        store.write_shard(ctx.out_dir, name, [{"id": name}])
    index.update_index(ctx.root, ctx.out_dir, {n: 1 for n in names})
    fake_build.calls += 1
    return {n: 1 for n in names}


fake_build.calls = 0


def legacy_project(rel=(".claude", "atlas")):
    root = make_project()
    old = os.path.join(root, *rel)
    store.write_shard(old, "grids", [{"id": "g"}])
    index.update_index(root, old, {"grids": 1})
    return root, old


class MigrateTest(unittest.TestCase):
    def setUp(self):
        fake_build.calls = 0
        p = mock.patch.object(build, "build", fake_build)
        p.start()
        self.addCleanup(p.stop)

    def test_rebuild_then_delete_and_single_run(self):
        root, old = legacy_project()
        self.assertTrue(migrate.pending(root))
        self.assertEqual(migrate.run(root, io.StringIO()), 0)
        self.assertFalse(os.path.exists(old))
        out = atlas_dir(root)
        self.assertEqual(out, os.path.join(root, ".oro-ai", "atlas"))
        self.assertFalse(any(st["state"] == "missing" for st in index.shard_status(root, out).values()))
        self.assertEqual(migrate.run(root, io.StringIO()), 0)
        self.assertEqual(fake_build.calls, 1)

    def test_var_atlas_is_migrated_too(self):
        root, old = legacy_project(("var", "atlas"))
        migrate.run(root, io.StringIO())
        self.assertFalse(os.path.exists(old))

    def test_failed_build_keeps_legacy(self):
        root, old = legacy_project()
        with mock.patch.object(build, "build", side_effect=build.AtlasError("php down")), mock.patch.object(sys, "stderr", io.StringIO()):
            self.assertEqual(migrate.run(root, io.StringIO()), 1)
        self.assertTrue(os.path.isdir(old))

    def test_stranger_directory_is_not_touched(self):
        root = make_project()
        os.makedirs(os.path.join(root, ".claude", "atlas"))
        open(os.path.join(root, ".claude", "atlas", "notes.txt"), "w").close()
        self.assertFalse(migrate.pending(root))

    def test_hook_paths_rewritten(self):
        root, old = legacy_project()
        os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
        cfg = os.path.join(root, ".claude", "settings.local.json")
        with open(cfg, "w") as fh:
            json.dump({"permissions": {"allow": ["x"]}, "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "chk .claude/atlas/index.json /x/var/atlas-tools /x/myvar/atlas"}]}]}}, fh)
        migrate.run(root, io.StringIO())
        data = json.load(open(cfg))
        self.assertEqual(data["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "chk .oro-ai/atlas/index.json /x/var/atlas-tools /x/myvar/atlas")
        self.assertEqual(data["permissions"], {"allow": ["x"]})

    def test_nothing_written_at_data_root(self):
        root, old = legacy_project()
        migrate.run(root, io.StringIO())
        self.assertEqual(sorted(os.listdir(os.path.join(root, ".oro-ai"))), [".gitignore", "atlas"])

    def test_reads_fall_back_to_legacy_until_new_is_complete(self):
        root, old = legacy_project()
        self.assertEqual(atlas_dir(root), old)
        migrate.run(root, io.StringIO())
        self.assertEqual(atlas_dir(root), os.path.join(root, ".oro-ai", "atlas"))

    def test_failure_backoff_and_give_up(self):
        root, old = legacy_project()
        self.assertTrue(migrate.may_auto_spawn(root))
        with mock.patch.object(build, "build", side_effect=build.AtlasError("php down")), mock.patch.object(sys, "stderr", io.StringIO()):
            migrate.run(root, io.StringIO())
            self.assertEqual(migrate.failures(root)["count"], 1)
            self.assertFalse(migrate.may_auto_spawn(root))
            with mock.patch.object(migrate.time, "time", return_value=migrate.time.time() + 7200):
                self.assertTrue(migrate.may_auto_spawn(root))
            os.makedirs(os.path.join(root, "src", "Foo"), exist_ok=True)
            with open(os.path.join(root, "src", "Foo", "New.php"), "w") as fh:
                fh.write("<?php")
            self.assertTrue(migrate.may_auto_spawn(root))
            migrate.run(root, io.StringIO())
            migrate.run(root, io.StringIO())
        self.assertTrue(migrate.gave_up(root))
        with mock.patch.object(migrate.time, "time", return_value=migrate.time.time() + 10**6):
            self.assertFalse(migrate.may_auto_spawn(root))
        self.assertEqual(migrate.run(root, io.StringIO()), 0)  # manual run succeeds and clears the marker
        self.assertIsNone(migrate.failures(root))
        self.assertTrue(os.path.isdir(old) is False)

    def test_data_root_gitignore_created_once_untracked_projects_only(self):
        root = make_project()
        subprocess.run(["git", "init", "-q", root], check=True)
        self.assertTrue(migrate.ensure_data_root_ignore(root))
        path = os.path.join(root, ".oro-ai", ".gitignore")
        self.assertEqual(open(path).read(), "*\n!.gitignore\n!config.json\n")
        open(path, "w").write("mine\n")
        self.assertFalse(migrate.ensure_data_root_ignore(root))
        self.assertEqual(open(path).read(), "mine\n")

    def test_tracked_data_root_gets_no_gitignore(self):
        root = make_project()
        subprocess.run(["git", "init", "-q", root], check=True)
        os.makedirs(os.path.join(root, ".oro-ai", "task"))
        open(os.path.join(root, ".oro-ai", "task", "plan.md"), "w").write("x")
        subprocess.run(["git", "-C", root, "add", ".oro-ai/task/plan.md"], check=True)
        self.assertFalse(migrate.ensure_data_root_ignore(root))
        self.assertFalse(os.path.exists(os.path.join(root, ".oro-ai", ".gitignore")))


class SpawnTest(unittest.TestCase):
    def test_entry_point_exists_and_command_is_runnable(self):
        root, old = legacy_project()
        cmd = migrate._command(root)
        self.assertTrue(os.path.isfile(cmd[1]), cmd[1])
        self.assertEqual(cmd[2:], ["atlas", "--project", root, "migrate"])
        p = subprocess.run(cmd[:2] + ["atlas", "--help"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_manual_command_is_shell_runnable_with_odd_paths(self):
        root = os.path.join(make_project(), "my proj")
        os.makedirs(root)
        import shlex
        self.assertEqual(shlex.split(migrate.manual_command(root)), migrate._command(root))

    def test_spawn_launches_existing_entry_and_runs_migrate(self):
        root, old = legacy_project()
        with mock.patch.object(subprocess, "Popen") as popen:
            migrate.spawn(root)
        self.assertEqual(popen.call_args[0][0], migrate._command(root))
        # a real child on a project the PHP build cannot index must reach migrate.run, not die on a missing file
        p = subprocess.run(migrate._command(root), capture_output=True, text=True, env=dict(os.environ, ATLAS_NO_AUTOBUILD="1"))
        self.assertNotIn("can't open file", p.stderr)

    def test_child_dying_at_startup_still_trips_the_gate(self):
        root, old = legacy_project()
        now = migrate.time.time()
        with mock.patch.object(subprocess, "Popen"):  # the child never reaches run(), so it records nothing itself
            for i in range(migrate.MAX_AUTO_FAILURES):
                with mock.patch.object(migrate.time, "time", return_value=now + 7200 * i):
                    self.assertTrue(migrate.may_auto_spawn(root))
                    migrate.spawn(root)
        with mock.patch.object(migrate.time, "time", return_value=now + 10**6):
            self.assertFalse(migrate.may_auto_spawn(root))
        self.assertTrue(migrate.gave_up(root))

    def test_one_spawn_blocks_immediate_respawn_and_success_clears_it(self):
        root, old = legacy_project()
        with mock.patch.object(subprocess, "Popen"):
            migrate.spawn(root)
        self.assertFalse(migrate.may_auto_spawn(root))
        with mock.patch.object(build, "build", fake_build):
            self.assertEqual(migrate.run(root, io.StringIO()), 0)
        self.assertIsNone(migrate.failures(root))

    def test_child_failure_after_spawn_is_not_double_counted(self):
        root, old = legacy_project()
        with mock.patch.object(subprocess, "Popen"):
            migrate.spawn(root)
        with mock.patch.object(build, "build", side_effect=build.AtlasError("php down")), mock.patch.object(sys, "stderr", io.StringIO()):
            migrate.run(root, io.StringIO())
        self.assertEqual(migrate.failures(root)["count"], 1)

    def test_log_is_capped(self):
        root, old = legacy_project()
        log = os.path.join(root, ".oro-ai", "atlas", migrate.LOG_NAME)
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "wb") as fh:
            fh.write(b"x" * (migrate.LOG_MAX_BYTES + 1))
        with mock.patch.object(subprocess, "Popen"):
            migrate.spawn(root)
        self.assertEqual(os.path.getsize(log), 0)


class HookTest(unittest.TestCase):
    def test_hook_announces_once_and_migrates(self):
        root, old = legacy_project()
        env = dict(os.environ, ORO_ATLAS_MIGRATE_SYNC="1")
        # No PHP in the unit environment: the sync run fails at the build and keeps the old index, still one line of output.
        p = subprocess.run([sys.executable, HOOK], input=json.dumps({"cwd": root}), capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0)
        self.assertIn(".oro-ai/atlas", json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_hook_silent_without_legacy(self):
        root = make_project()
        p = subprocess.run([sys.executable, HOOK], input=json.dumps({"cwd": root}), capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
