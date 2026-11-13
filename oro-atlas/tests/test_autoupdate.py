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

from atlas import build, cli, extractors, index, store  # noqa: E402
from atlas.common import Context, atlas_dir  # noqa: E402
from atlas.extractors import events  # noqa: E402
from tests.test_core import make_project  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def run(argv):
    buf, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "stderr", err):
        code = cli.main(argv, out=buf)
    return code, buf.getvalue(), err.getvalue()


def project(shards):
    root = make_project()
    out = atlas_dir(root)
    for name, recs in shards.items():
        store.write_shard(out, name, recs)
    index.update_index(root, out, {k: len(v) for k, v in shards.items()})
    return root, out


class LocationTest(unittest.TestCase):
    def test_index_lives_under_oro_ai(self):
        root = make_project()
        self.assertEqual(atlas_dir(root), os.path.join(root, ".oro-ai", "atlas"))


class PerShardStalenessTest(unittest.TestCase):
    def setUp(self):
        self.root, self.out = project({"grids": [{"id": "g"}], "services": [{"id": "s"}], "events": [{"id": "e"}]})

    def touch(self, rel, text="x"):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)

    def test_unrelated_src_save_stales_nothing(self):
        self.touch("src/Foo/Resources/config/services.yml")
        self.assertEqual(index.stale_shards(self.root, self.out), [])

    def test_only_the_shard_that_ingests_the_file_goes_stale(self):
        self.touch("src/Foo/Resources/config/oro/datagrids.yml")
        self.assertEqual(index.stale_shards(self.root, self.out), ["grids"])
        self.touch("src/Foo/Bar.php")
        self.assertEqual(index.stale_shards(self.root, self.out), ["events", "grids"])

    def test_composer_lock_stales_every_shard(self):
        self.touch("composer.lock", '{"packages":[{"name":"x"}]}')
        self.assertEqual(index.stale_shards(self.root, self.out), ["events", "grids", "services"])

    def test_container_cache_stales_container_shards_only(self):
        self.touch("var/cache/prod/AppKernelProdContainer.php", "<?php")
        self.assertEqual(index.stale_shards(self.root, self.out), ["events", "grids", "services"])
        root, out = project({"entities": [{"id": "x"}]})
        open(os.path.join(root, "var-cache-prod"), "w").close()
        self.assertEqual(index.stale_shards(root, out), [])

    def test_edit_during_build_is_not_stamped_fresh(self):
        pre = index.current_stamps(self.root, ["grids"])
        self.touch("src/Foo/Resources/config/oro/datagrids.yml")
        index.update_index(self.root, self.out, {"grids": 1}, None, pre)
        self.assertEqual(index.stale_shards(self.root, self.out), ["grids"])

    def test_missing_and_dependent_status(self):
        status = index.shard_status(self.root, self.out)
        self.assertEqual(status["js"]["state"], "missing")
        self.assertEqual(status["grids"]["state"], "fresh")


class StatusExitTest(unittest.TestCase):
    def test_fresh_is_zero_stale_and_missing_are_two(self):
        root, out = project({n: [{"id": n}] for n in cli.SHARDS.values()})
        code, text, _ = run(["--project", root, "status"])
        self.assertEqual((code, "STALE" in text), (0, False))
        os.remove(os.path.join(out, "js.jsonl"))
        code, text, _ = run(["--project", root, "status"])
        self.assertEqual(code, 2)
        self.assertIn("MISSING", text)
        index.update_index(root, out, {"js": 1})
        store.write_shard(out, "js", [{"id": "js"}])
        open(os.path.join(root, "composer.lock"), "w").write('{"packages":[{}]}')
        code, text, _ = run(["--project", root, "status"])
        self.assertEqual(code, 2)
        self.assertIn("STALE (composer.lock changed)", text)
        self.assertEqual(run(["--project", root, "status", "--quiet"]), (2, "", ""))

    def test_no_index_is_all_missing(self):
        self.assertEqual(run(["--project", make_project(), "status", "--quiet"])[0], 2)

    def test_query_on_stale_index_warns_on_stderr_only(self):
        root, out = project({"events": [{"id": "e", "keys": ["e"], "text": "t"}]})
        open(os.path.join(root, "composer.lock"), "w").write('{"packages":[{}]}')
        code, stdout, err = run(["--project", root, "event", "e", "--json"])
        self.assertEqual(code, 0)
        json.loads(stdout)
        self.assertIn("STALE", err)


class NoAutoRebuildTest(unittest.TestCase):
    def test_query_on_stale_shard_never_builds_and_names_the_command(self):
        root, out = project({"grids": [{"id": "g", "keys": ["g"]}]})
        os.makedirs(os.path.join(root, "src", "A"))
        open(os.path.join(root, "src", "A", "datagrids.yml"), "w").write("x")
        with mock.patch.object(build, "build") as b, mock.patch("subprocess.Popen") as sp:
            code, stdout, err = run(["--project", root, "grid", "g"])
        b.assert_not_called()
        sp.assert_not_called()
        self.assertEqual(code, 0)
        self.assertIn("rebuild (never automatic): atlas build --incremental", err)

    def test_no_heal_helpers_remain(self):
        self.assertFalse(hasattr(cli, "_heal") or hasattr(cli, "spawn_background"))


class IncrementalBuildTest(unittest.TestCase):
    def test_only_stale_shards_rebuilt_and_noop_is_quiet(self):
        root = make_project()
        ctx = Context(root)
        seen = []

        def mk(name):
            return mock.Mock(NAME=name, ORDER=0, DEPENDS=(), extract=lambda c: seen.append(name) or [{"id": name}])

        mods = {"grids": mk("grids"), "events": mk("events")}
        with mock.patch.object(extractors, "load_all", return_value=mods):
            build.build_incremental(ctx, io.StringIO())
            self.assertEqual(sorted(seen), ["events", "grids"])
            del seen[:]
            out = io.StringIO()
            build.build_incremental(ctx, out)
            self.assertEqual(seen, [])
            self.assertIn("nothing to rebuild", out.getvalue())
            os.makedirs(os.path.join(root, "src", "A"))
            open(os.path.join(root, "src", "A", "datagrids.yml"), "w").write("x")
            build.build_incremental(ctx, io.StringIO())
            self.assertEqual(seen, ["grids"])

    def test_background_skips_when_locked(self):
        root = make_project()
        ctx = Context(root)
        os.makedirs(ctx.out_dir)
        open(build.lock_path(ctx.out_dir), "w").write(str(os.getpid()))
        with mock.patch.object(build, "build") as b:
            build.build_incremental(ctx, io.StringIO(), background=True)
        b.assert_not_called()


class SetupTest(unittest.TestCase):
    def test_setup_installs_no_git_hooks_and_removes_ours_only(self):
        root = make_project()
        subprocess.run(["git", "init", "-q", root], check=True)
        hooks = os.path.join(root, ".git", "hooks")
        os.makedirs(hooks, exist_ok=True)
        open(os.path.join(hooks, "post-merge"), "w").write("#!/bin/sh\necho mine\n")
        open(os.path.join(hooks, "post-checkout"), "w").write("#!/bin/sh\n# oro-atlas: refresh index\n")
        out = subprocess.run([sys.executable, os.path.join(ROOT, "bin", "atlas-setup"), root, "--no-build"], capture_output=True, text=True, check=True).stdout
        self.assertEqual(open(os.path.join(hooks, "post-merge")).read(), "#!/bin/sh\necho mine\n")
        self.assertFalse(os.path.exists(os.path.join(hooks, "post-checkout")))
        self.assertFalse(os.path.exists(os.path.join(hooks, "post-rewrite")))
        self.assertIn("post-checkout: removed", out)

    def test_no_posttooluse_edit_hook_registered(self):
        with open(os.path.join(ROOT, "..", "hooks", "hooks.json")) as fh:
            self.assertNotIn("posttooluse_edit", fh.read())
