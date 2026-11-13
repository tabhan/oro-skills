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
            json.dump({"permissions": {"allow": ["x"]}, "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "chk .claude/atlas/index.json"}]}]}}, fh)
        migrate.run(root, io.StringIO())
        data = json.load(open(cfg))
        self.assertEqual(data["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "chk .oro-ai/atlas/index.json")
        self.assertEqual(data["permissions"], {"allow": ["x"]})

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
