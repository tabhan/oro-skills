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
    def test_legacy_index_is_moved(self):
        root = make_project()
        legacy = os.path.join(root, "var", "atlas")
        store.write_shard(legacy, "grids", [{"id": "g"}])
        out = atlas_dir(root)
        self.assertEqual(out, os.path.join(root, ".claude", "atlas"))
        self.assertTrue(os.path.isfile(os.path.join(out, "grids.jsonl")))
        self.assertFalse(os.path.exists(legacy))

    def test_existing_new_location_wins(self):
        root = make_project()
        store.write_shard(os.path.join(root, ".claude", "atlas"), "grids", [])
        os.makedirs(os.path.join(root, "var", "atlas"))
        self.assertEqual(atlas_dir(root), os.path.join(root, ".claude", "atlas"))
        self.assertTrue(os.path.isdir(os.path.join(root, "var", "atlas")))


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


class LazyRefreshTest(unittest.TestCase):
    def setUp(self):
        self.root, self.out = project({"grids": [{"id": "g"}]})
        meta = index.read_index(self.out)
        meta["shards"]["grids"]["build_seconds"] = 0.3
        json.dump(meta, open(os.path.join(self.out, "index.json"), "w"))
        os.makedirs(os.path.join(self.root, "src", "A"))
        open(os.path.join(self.root, "src", "A", "datagrids.yml"), "w").write("x")

    def test_cheap_src_change_rebuilds_inline_and_prints_nothing(self):
        err = io.StringIO()
        with mock.patch.object(build, "build", return_value={"grids": 1}) as b, mock.patch.object(cli, "spawn_background") as sp:
            cli._heal(self.root, self.out, ["grids"], err)
        b.assert_called_once()
        sp.assert_not_called()
        self.assertEqual(err.getvalue(), "")

    def test_expensive_or_lock_change_goes_to_background(self):
        meta = index.read_index(self.out)
        meta["shards"]["grids"]["build_seconds"] = 30
        json.dump(meta, open(os.path.join(self.out, "index.json"), "w"))
        err = io.StringIO()
        with mock.patch.object(build, "build") as b, mock.patch.object(cli, "spawn_background") as sp:
            cli._heal(self.root, self.out, ["grids"], err)
        b.assert_not_called()
        sp.assert_called_once()
        self.assertEqual(err.getvalue().count("\n"), 1)

    def test_background_not_respawned_while_build_runs(self):
        open(os.path.join(self.root, "composer.lock"), "w").write('{"packages":[{}]}')
        os.makedirs(self.out, exist_ok=True)
        open(build.lock_path(self.out), "w").write(str(os.getpid()))
        with mock.patch.object(cli, "spawn_background") as sp:
            cli._heal(self.root, self.out, ["grids"], io.StringIO())
        sp.assert_not_called()


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


class TriggerTest(unittest.TestCase):
    def hook(self, root, path, env=None):
        payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": path}, "cwd": root})
        return subprocess.run([sys.executable, os.path.join(ROOT, "hooks", "posttooluse_edit.py")], input=payload,
                              capture_output=True, text=True, env=dict(os.environ, **(env or {})))

    def test_posttooluse_trigger_is_silent_and_spawns_for_watched_files(self):
        root = make_project()
        env = {"ATLAS_NO_AUTOBUILD": ""}
        proc = self.hook(root, os.path.join(root, "src", "A", "x.yml"), env)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))
        proc = self.hook(root, os.path.join(root, "README.md"), env)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))

    def test_posttooluse_trigger_silent_on_garbage_input(self):
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "hooks", "posttooluse_edit.py")], input="not json", capture_output=True, text=True)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))

    def test_setup_installs_git_hooks_without_clobbering(self):
        root = make_project()
        subprocess.run(["git", "init", "-q", root], check=True)
        existing = os.path.join(root, ".git", "hooks", "post-merge")
        open(existing, "w").write("#!/bin/sh\necho mine\n")
        out = subprocess.run([sys.executable, os.path.join(ROOT, "bin", "atlas-setup"), root, "--no-build"], capture_output=True, text=True, check=True).stdout
        self.assertEqual(open(existing).read(), "#!/bin/sh\necho mine\n")
        self.assertIn("post-merge exists", out)
        for name in ("post-checkout", "post-rewrite"):
            path = os.path.join(root, ".git", "hooks", name)
            self.assertTrue(os.access(path, os.X_OK))
            self.assertIn("--incremental --background", open(path).read())
            self.assertIn(">/dev/null 2>&1", open(path).read())
        subprocess.run([sys.executable, os.path.join(ROOT, "bin", "atlas-setup"), root, "--no-build"], capture_output=True, check=True)


class DoctrineExtractorTest(unittest.TestCase):
    def test_listener_subscriber_and_entity_listener_records(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "src"))
        php = os.path.join(root, "src", "Sub.php")
        open(php, "w").write("<?php\nclass Sub {\n    public function onFlush() {}\n    public static function getSubscribedEvents(): array\n    {\n        return [Events::postPersist];\n    }\n}\n")
        loc = mock.Mock()
        loc.locate.return_value = ("src/Sub.php", 2)
        loc.file_of.side_effect = lambda c: php if c == "Sub" else None
        ctx = mock.Mock(root=root, locator=loc)
        defs = {
            "a": {"class": "Sub", "tags": [{"name": "doctrine.event_listener", "parameters": {"event": "onFlush", "priority": 10}}]},
            "b": {"class": "Sub", "tags": [{"name": "doctrine.event_subscriber"}]},
            "c": {"class": "Ent", "tags": [{"name": "doctrine.orm.entity_listener", "parameters": {"event": "onFlush", "entity": "App\\Entity\\Redirect"}}]},
        }
        recs = list(events.doctrine_records(ctx, defs))
        by = {(r["event"], r["type"]): r for r in recs}
        self.assertEqual(set(by), {("onFlush", "event_listener"), ("postPersist", "event_subscriber"), ("onFlush", "entity_listener")})
        first = by[("onFlush", "event_listener")]
        self.assertEqual((first["method"], first["priority"], first["file"], first["line"]), ("onFlush", 10, "src/Sub.php", 3))
        self.assertEqual(by[("onFlush", "entity_listener")]["entity"], "App\\Entity\\Redirect")
        self.assertIn("redirect", [k.lower() for k in by[("onFlush", "entity_listener")]["keys"]])

    def test_event_query_returns_doctrine_listeners(self):
        recs = [dict(id="doctrine:onFlush:A::onFlush", kind="doctrine_listener", event="onFlush", keys=["onFlush", "A"], text="doctrine event_listener A::onFlush", file="a.php", line=3)]
        root, _ = project({"events": recs})
        code, text, _ = run(["--project", root, "event", "onFlush"])
        self.assertEqual(code, 0)
        self.assertIn("a.php:3", text)


ENTITY = "Oro\\Bundle\\RedirectBundle\\Entity\\Redirect"


class RollupAndUnsafeTest(unittest.TestCase):
    def setUp(self):
        repo = "Oro\\Bundle\\RedirectBundle\\Entity\\Repository\\RedirectRepository"
        self.root, _ = project({
            "entities": [{"id": ENTITY, "keys": ["oro_redirect", "Redirect"], "kind": "Entity", "table": "oro_redirect",
                          "repository": repo, "repository_override": "Buckman\\RedirectRepository",
                          "extend_override_file": "src/entity_extend.yml:3", "text": "Entity", "file": "e.php", "line": 1}],
            "grids": [{"id": "redirect-grid", "kind": "grid", "entity": ENTITY, "text": "grid", "file": "g.yml", "line": 2}],
            "operations": [{"id": "op1", "kind": "operation", "entities": [ENTITY], "datagrids": [], "file": "a.yml", "line": 4, "text": "op"},
                           {"id": "op2", "kind": "operation", "entities": [], "datagrids": ["redirect-grid"], "file": "a.yml", "line": 9, "text": "op"},
                           {"id": "other", "kind": "operation", "entities": ["X"], "datagrids": [], "file": "a.yml", "line": 1, "text": "op"}],
            "events": [{"id": "doctrine:prePersist:L::prePersist@E", "kind": "doctrine_listener", "event": "prePersist", "class": "L",
                        "method": "prePersist", "entity": ENTITY, "file": "l.php", "line": 7, "keys": [], "text": "d"}],
            "mq": [{"id": "oro.other.topic", "kind": "topic", "class": "Oro\\Bundle\\ApiBundle\\Topic\\T", "keys": [], "text": "t"},
                   {"id": "oro.redirect.regenerate", "kind": "topic", "class": "Oro\\Bundle\\RedirectBundle\\Async\\Topic\\T", "keys": [], "text": "t"}],
            "unsafe": [{"id": repo, "keys": ["RedirectRepository"], "text": "typehinted", "file": "r.php", "line": 1}],
            "services": [],
        })

    def test_entity_rollup_text(self):
        code, text, _ = run(["--project", self.root, "entity", "Redirect"])
        self.assertEqual(code, 0)
        for needle in ("repository Oro", "override Buckman", "redirect-grid g.yml:2", "op1", "op2", "prePersist L::prePersist", "oro.redirect.regenerate"):
            self.assertIn(needle, text)
        self.assertNotIn("other", text)
        self.assertNotIn("oro.other.topic", text)

    def test_entity_rollup_json(self):
        _, text, _ = run(["--project", self.root, "entity", "Redirect", "--json"])
        hit = json.loads(text)["results"][0]["hits"][0]
        self.assertEqual(sorted(hit["rollup"]), ["doctrine", "grids", "mq (same bundle)", "operations", "repository"])

    def test_unsafe_accepts_fqcn_with_or_without_backslash(self):
        fq = "Oro\\Bundle\\RedirectBundle\\Entity\\Repository\\RedirectRepository"
        for q in (fq, "\\" + fq, fq.replace("\\", "\\\\"), "RedirectRepository"):
            code, text, _ = run(["--project", self.root, "unsafe", q])
            self.assertEqual(code, 0, q)
            self.assertIn("typehinted", text)

    def test_unsafe_unknown_fqcn_explains(self):
        code, text, _ = run(["--project", self.root, "unsafe", "\\Nope\\Missing"])
        self.assertEqual(code, 1)
        self.assertIn("not a known", text)

    def test_unsafe_follows_entity_extend_override(self):
        root, _ = project({"entities": [{"id": ENTITY, "keys": [], "text": "e", "repository": "Oro\\R\\Repo", "repository_override": "Buckman\\Repo"}],
                           "unsafe": [], "services": []})
        code, text, _ = run(["--project", root, "unsafe", "\\Oro\\R\\Repo"])
        self.assertEqual(code, 1)
        self.assertIn("replaced via entity_extend by Buckman\\Repo", text)


class RankingAndLocationTest(unittest.TestCase):
    def test_src_hits_rank_first_and_survive_truncation(self):
        recs = [dict(id="v%d" % i, keys=["onFlush"], text="t", file="vendor/x/%d.php" % i) for i in range(8)]
        recs += [dict(id="p%d" % i, keys=["onFlush"], text="t", file="src/A/%d.php" % i) for i in range(3)]
        found, total = cli.search_records(recs, "onFlush", 2)
        self.assertEqual([r["id"] for r in found], ["p0", "p1", "v0", "p2"][:0] or ["p0", "p1", "p2"])
        self.assertEqual(total, 11)

    def test_better_vendor_match_still_beats_src_fuzzy(self):
        recs = [dict(id="a", keys=["xonflushx"], text="t", file="src/a.php"), dict(id="b", keys=["onflush"], text="t", file="vendor/b.php")]
        self.assertEqual(cli.search_records(recs, "onflush", 5)[0][0]["id"], "b")

    def test_uncommitted_class_resolves_via_composer_json_psr4(self):
        from atlas.common import ClassLocator
        root = make_project()
        os.makedirs(os.path.join(root, "src", "Foo"))
        open(os.path.join(root, "composer.json"), "w").write('{"autoload":{"psr-4":{"":"src/"}}}')
        open(os.path.join(root, "src", "Foo", "New.php"), "w").write("<?php\nnamespace Foo;\n\nclass New {}\n")
        self.assertEqual(ClassLocator(root).locate("Foo\\New"), (os.path.join("src", "Foo", "New.php"), 4))

    def test_build_subcommand_delegates(self):
        with mock.patch.object(build, "main", return_value=0) as m:
            self.assertEqual(cli.main(["build", "--project", "/x", "--incremental"]), 0)
        m.assert_called_once_with(["--project", "/x", "--incremental"])

    def test_global_flush_listener_referencing_entity_in_rollup(self):
        root = make_project()
        os.makedirs(os.path.join(root, "src", "L"))
        open(os.path.join(root, "src", "L", "Fl.php"), "w").write("<?php\nuse %s;\nclass Fl {}\n" % ENTITY)
        open(os.path.join(root, "src", "L", "Other.php"), "w").write("<?php\nclass Other {}\n")
        out = atlas_dir(root)
        lis = lambda c, f: dict(id="d:" + c, kind="doctrine_listener", event="onFlush", **{'class': c}, method="onFlush", entity=None, file=f, line=5, keys=[], text="x")
        store.write_shard(out, "events", [lis("L\\Fl", "src/L/Fl.php"), lis("L\\Other", "src/L/Other.php")])
        from atlas import rollup
        self.assertEqual(rollup.flush_listeners(out, ENTITY), ["Fl::onFlush src/L/Fl.php:5"])


if __name__ == "__main__":
    unittest.main()
