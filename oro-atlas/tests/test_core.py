import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas import cli, index, store  # noqa: E402
from atlas.common import AtlasError, MissingShard, find_project_root, sha256_file  # noqa: E402
from atlas.extractors import load_all, ordered  # noqa: E402


def make_project(lock='{"packages":[{"name":"oro/platform","version":"7.0.3"}]}'):
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, "bin"))
    os.makedirs(os.path.join(root, "sub", "deep"))
    open(os.path.join(root, "bin", "console"), "w").close()
    open(os.path.join(root, "composer.lock"), "w").write(lock)
    return root


class CommonTest(unittest.TestCase):
    def test_root_detection_walks_up(self):
        root = make_project()
        self.assertEqual(find_project_root(os.path.join(root, "sub", "deep")), root)

    def test_root_missing_raises(self):
        with self.assertRaises(AtlasError):
            find_project_root(tempfile.mkdtemp())

    def test_sha256(self):
        root = make_project("abc")
        self.assertEqual(sha256_file(os.path.join(root, "composer.lock"))[:8], "ba7816bf")


class StoreTest(unittest.TestCase):
    def test_roundtrip_and_count(self):
        d = tempfile.mkdtemp()
        self.assertEqual(store.write_shard(d, "x", iter([{"id": "a"}, {"id": "b"}])), 2)
        self.assertEqual([r["id"] for r in store.read_shard(d, "x")], ["a", "b"])

    def test_failed_write_keeps_old_shard(self):
        d = tempfile.mkdtemp()
        store.write_shard(d, "x", [{"id": "a"}])

        def boom():
            yield {"id": "b"}
            raise ValueError("x")

        with self.assertRaises(ValueError):
            store.write_shard(d, "x", boom())
        self.assertEqual([r["id"] for r in store.read_shard(d, "x")], ["a"])

    def test_missing_shard(self):
        with self.assertRaises(MissingShard):
            list(store.read_shard(tempfile.mkdtemp(), "nope"))


class IndexTest(unittest.TestCase):
    def test_stamp_and_staleness(self):
        root = make_project()
        out = os.path.join(root, "var", "atlas")
        idx = index.update_index(root, out, {"services": 3})
        self.assertEqual(idx["platform_version"], "7.0.3")
        self.assertEqual(idx["shards"]["services"]["count"], 3)
        self.assertIsNone(index.stale_line(root, out))
        open(os.path.join(root, "composer.lock"), "w").write("{}")
        self.assertIn("STALE", index.stale_line(root, out))

    def test_partial_build_keeps_other_shards(self):
        root = make_project()
        out = os.path.join(root, "var", "atlas")
        index.update_index(root, out, {"a": 1})
        idx = index.update_index(root, out, {"b": 2})
        self.assertEqual(sorted(idx["shards"]), ["a", "b"])


class RegistryAndCliTest(unittest.TestCase):
    def test_registry_contract(self):
        mods = load_all()
        self.assertIn("services", mods)
        self.assertEqual(ordered(mods, ["services"]), ["services", "unsafe"])
        self.assertEqual(ordered(mods, ["unsafe"]), ["unsafe"])
        with self.assertRaises(AtlasError):
            ordered(mods, ["nope"])

    def test_cli_search_ranking_and_missing(self):
        root = make_project()
        out = os.path.join(root, "var", "atlas")
        store.write_shard(out, "services", [
            {"id": "other", "text": "uses foo.bar", "file": "a.php", "line": 3},
            {"id": "foo.bar", "keys": ["Foo\\Bar"], "text": "x", "file": "b.php", "line": 9},
        ])
        index.update_index(root, out, {"services": 2})
        buf = io.StringIO()
        cli.main(["--project", root, "service", "foo.bar"], out=buf)
        lines = buf.getvalue().splitlines()
        self.assertTrue(lines[0].startswith("foo.bar") and lines[0].endswith("b.php:9"))
        self.assertEqual(cli.main(["--project", root, "grid", "x"], out=io.StringIO()), 1)


if __name__ == "__main__":
    unittest.main()
