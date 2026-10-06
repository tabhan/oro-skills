import io
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas import build, extractors, index, raw  # noqa: E402
from atlas.common import AtlasError, Context  # noqa: E402


def make_project():
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, "bin"))
    os.makedirs(os.path.join(root, "src", "Foo"))
    os.makedirs(os.path.join(root, "config"))
    open(os.path.join(root, "bin", "console"), "w").close()
    open(os.path.join(root, "composer.lock"), "w").write('{"packages":[]}')
    open(os.path.join(root, "src", "Foo", "A.php"), "w").write("<?php")
    open(os.path.join(root, "config", "config.yml"), "w").write("a: 1")
    return root


def fake_mods(seen=None, barrier=None):
    def ext(name, deps=()):
        def extract(ctx):
            if barrier:
                barrier()
            if seen is not None:
                seen.append((name, os.path.basename(ctx.out_dir)))
            return [{"name": name}]
        return types.SimpleNamespace(NAME=name, extract=extract, DEPENDS=deps, ORDER=0 if not deps else 10)
    return {"services": ext("services"), "unsafe": ext("unsafe", ("services",)), "js": ext("js")}


def touch_later(path, text):
    st = os.stat(path)
    with open(path, "w") as fh:
        fh.write(text)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))


class StalenessTest(unittest.TestCase):
    def setUp(self):
        self.root = make_project()
        self.out = os.path.join(self.root, "var", "atlas")
        index.update_index(self.root, self.out, {"services": 1})

    def test_fresh(self):
        self.assertIsNone(index.stale_line(self.root, self.out))

    def test_src_edit_is_stale_with_reason(self):
        touch_later(os.path.join(self.root, "src", "Foo", "A.php"), "<?php // x")
        self.assertEqual(index.stale_reasons(self.root, self.out), {"services": ["src"]})
        self.assertIn("src changed since services", index.stale_line(self.root, self.out))

    def test_config_and_new_src_file_are_stale(self):
        open(os.path.join(self.root, "config", "routes.php"), "w").write("x")
        self.assertEqual(index.stale_shards(self.root, self.out), ["services"])

    def test_non_tracked_src_ext_ignored(self):
        open(os.path.join(self.root, "src", "Foo", "a.js"), "w").write("x")
        self.assertIsNone(index.stale_line(self.root, self.out))

    def test_composer_lock_reason(self):
        open(os.path.join(self.root, "composer.lock"), "w").write('{"packages":[{}]}')
        self.assertIn("composer.lock changed", index.stale_line(self.root, self.out))


class RegistryDependsTest(unittest.TestCase):
    def test_only_pulls_in_dependents(self):
        mods = fake_mods()
        self.assertEqual(extractors.ordered(mods, ["services"]), ["services", "unsafe"])
        self.assertEqual(extractors.ordered(mods, ["js"]), ["js"])

    def test_real_registry_declares_unsafe_on_services(self):
        mods = extractors.load_all()
        self.assertIn("services", extractors.depends_of(mods, "unsafe"))

    def test_real_registry_only_services_rebuilds_unsafe(self):
        self.assertIn("unsafe", extractors.ordered(extractors.load_all(), ["services"]))


class RawRefreshTest(unittest.TestCase):
    def test_dump_older_than_container_cache_is_redumped(self):
        root = make_project()
        ctx = Context(root)
        os.makedirs(ctx.raw_dir)
        dump = os.path.join(ctx.raw_dir, "container.json")
        open(dump, "w").write('{"old": 1}')
        os.utime(dump, (1000, 1000))
        cache = os.path.join(root, "var", "cache", "prod")
        os.makedirs(cache)
        open(os.path.join(cache, "AppKernelProdContainer.php"), "w").close()
        with mock.patch.object(raw, "run_php_json", return_value={"new": 1}) as php:
            self.assertEqual(raw.container(ctx), {"new": 1})
            os.utime(dump, None)
            os.utime(os.path.join(cache, "AppKernelProdContainer.php"), (2000, 2000))
            self.assertEqual(raw.container(ctx), {"new": 1})
            self.assertEqual(php.call_count, 1)


class AtomicBuildTest(unittest.TestCase):
    def setUp(self):
        self.root = make_project()
        self.ctx = Context(self.root)

    def test_builds_in_staging_and_swaps(self):
        seen = []
        with mock.patch.object(extractors, "load_all", return_value=fake_mods(seen)):
            build.build(self.ctx, out=io.StringIO())
        self.assertTrue(all(d.startswith("atlas.tmp-") for _, d in seen))
        self.assertEqual(self.ctx.out_dir, os.path.join(self.root, "var", "atlas"))
        self.assertEqual(sorted(index.read_index(self.ctx.out_dir)["shards"]), ["js", "services", "unsafe"])
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "var"))), ["atlas"])

    def test_only_keeps_other_shards_and_failure_keeps_old_index(self):
        with mock.patch.object(extractors, "load_all", return_value=fake_mods()):
            build.build(self.ctx, out=io.StringIO())
        mods = fake_mods()
        mods["js"].extract = mock.Mock(side_effect=RuntimeError("boom"))
        with mock.patch.object(extractors, "load_all", return_value=mods):
            with self.assertRaises(RuntimeError):
                build.build(self.ctx, only=["js"], out=io.StringIO())
        self.assertEqual(len(index.read_index(self.ctx.out_dir)["shards"]), 3)
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "var"))), ["atlas"])
        with mock.patch.object(extractors, "load_all", return_value=fake_mods()):
            built = build.build(self.ctx, only=["services"], out=io.StringIO())
        self.assertEqual(sorted(built), ["services", "unsafe"])
        self.assertEqual(len(index.read_index(self.ctx.out_dir)["shards"]), 3)

    def test_index_visible_throughout_rebuild(self):
        with mock.patch.object(extractors, "load_all", return_value=fake_mods()):
            build.build(self.ctx, out=io.StringIO())
        visible = []
        probe = lambda: visible.append(index.read_index(os.path.join(self.root, "var", "atlas")) is not None)
        with mock.patch.object(extractors, "load_all", return_value=fake_mods(barrier=probe)):
            build.build(Context(self.root), out=io.StringIO())
        self.assertTrue(visible and all(visible))

    def test_concurrent_build_refused(self):
        lock = os.path.join(self.root, "var", "atlas.lock")
        os.makedirs(os.path.dirname(lock))
        open(lock, "w").write(str(os.getppid()))
        with mock.patch.object(extractors, "load_all", return_value=fake_mods()):
            with self.assertRaises(AtlasError):
                build.build(self.ctx, out=io.StringIO())
        self.assertTrue(os.path.isfile(lock))

    def test_stale_lock_of_dead_pid_taken_over(self):
        lock = os.path.join(self.root, "var", "atlas.lock")
        os.makedirs(os.path.dirname(lock))
        open(lock, "w").write("999999999")
        with mock.patch.object(extractors, "load_all", return_value=fake_mods()):
            build.build(self.ctx, out=io.StringIO())
        self.assertFalse(os.path.exists(lock))


if __name__ == "__main__":
    unittest.main()
