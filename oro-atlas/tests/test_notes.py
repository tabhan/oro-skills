import io
import json
import os
import sys
import tempfile
import unittest

os.environ["ATLAS_NO_AUTOBUILD"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from atlas import cli, index, notesindex, store  # noqa: E402
from atlas.common import Context  # noqa: E402
from atlas import build  # noqa: E402
from tests.test_core import make_project  # noqa: E402

SVC = "oro_product.live_service"
NOTE = "---\ntitle: %s\nkind: %s\nsurface: %s\nanchors: [%s]\nupdated: %s\n%s---\nbody text\n"


def write_note(root, slug, title="T", kind="gotcha", surface="anchored", anchors="", updated="2026-11-01", extra=""):
    path = os.path.join(root, ".oro-ai", "notes", slug + ".md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(NOTE % (title, kind, surface, anchors, updated, extra))


def project(version="7.0.3"):
    root = make_project('{"packages":[{"name":"oro/platform","version":"%s"}]}' % version)
    out = os.path.join(root, ".oro-ai", "atlas")
    shards = {
        "services": [{"id": SVC, "keys": ["Oro\\Live\\Svc"], "text": "svc", "file": "src/Acme/Bundle/LiveBundle/Svc.php", "line": 3}],
        "entities": [{"id": "Oro\\Live\\Entity", "keys": [], "text": "e", "file": "x.php"}],
        "workflows": [{"id": "live_flow", "keys": [], "text": "w", "file": "w.yml"}],
    }
    for name, recs in shards.items():
        store.write_shard(out, name, recs)
    index.update_index(root, out, {k: len(v) for k, v in shards.items()})
    return root


def run(argv):
    buf = io.StringIO()
    return cli.main(argv, out=buf), buf.getvalue()


def build_notes(root):
    return build.build(Context(root), ["notes"], out=io.StringIO())


class ParseTest(unittest.TestCase):
    def test_flow_and_block_anchors(self):
        meta, _ = notesindex.split_frontmatter("---\ntitle: x\nanchors:\n  - class:A\\B\n  - path:src/**/E*.php\n---\nb")
        self.assertEqual(meta["anchors"], ["class:A\\B", "path:src/**/E*.php"])
        meta, _ = notesindex.split_frontmatter("---\nanchors: [service:a, 'path:x, y']\n---\n")
        self.assertEqual(meta["anchors"], ["service:a", "path:x, y"])

    def test_rejections(self):
        bad = {
            "no frontmatter": "just text",
            "unknown kind": "---\ntitle: t\nkind: rant\nsurface: always\n---\n",
            "anchored needs anchors": "---\ntitle: t\nkind: gotcha\nsurface: anchored\n---\n",
            "bad anchor": "---\ntitle: t\nkind: gotcha\nsurface: anchored\nanchors: [thing:x]\n---\n",
            "secret": "---\ntitle: t\nkind: gotcha\nsurface: always\n---\npassword=hunter2\n",
            "bad oro range": "---\ntitle: t\nkind: gotcha\nsurface: always\noro: '>>>'\n---\n",
        }
        for name, text in bad.items():
            with self.assertRaises(notesindex.NoteError, msg=name):
                notesindex.parse_note("s", text, notesindex._constraint_check)

    def test_prose_mentioning_cookie_is_not_a_secret(self):
        notesindex.parse_note("s", "---\ntitle: t\nkind: gotcha\nsurface: always\n---\nclear the cookie first\n")

    def test_glob(self):
        rx = notesindex.glob_regex("src/Buckman/**/Export*.php")
        self.assertTrue(rx.match("src/Buckman/Bundle/X/Y/ExportFoo.php"))
        self.assertTrue(rx.match("src/Buckman/ExportFoo.php"))
        self.assertFalse(rx.match("src/Other/ExportFoo.php"))


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.root = project()
        write_note(self.root, "live", "Live one", anchors="service:%s" % SVC)
        write_note(self.root, "dead", "Dead one", anchors="service:gone.service, class:Nope\\Missing")
        write_note(self.root, "env", "Env fact", kind="recipe", surface="always", updated="2026-10-01")
        write_note(self.root, "broken", kind="nonsense")
        build_notes(self.root)

    def test_dead_anchored_demoted_with_flag(self):
        code, text = run(["--project", self.root, "notes", "--always"])
        self.assertEqual(code, 0)
        lines = text.strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("dead"))
        self.assertIn("possibly stale", lines[0])
        self.assertTrue(lines[1].startswith("env"))
        self.assertFalse(any(l.startswith("live") for l in lines))

    def test_invalid_note_skipped_and_linted(self):
        code, text = run(["--project", self.root, "notes", "--lint"])
        self.assertEqual(code, 1)
        self.assertIn("broken: unknown kind", text)
        self.assertNotIn("broken", run(["--project", self.root, "notes"])[1])

    def test_term_search_and_json(self):
        code, text = run(["--project", self.root, "notes", "env"])
        self.assertEqual((code, text.split()[0]), (0, "env"))
        code, text = run(["--project", self.root, "notes", "--anchored", "--json"])
        self.assertEqual([n["id"] for n in json.loads(text)["notes"]], ["live"])
        self.assertEqual(run(["--project", self.root, "notes", "zzzz"])[0], 1)

    def test_service_query_attaches_live_note_once(self):
        code, text = run(["--project", self.root, "service", SVC])
        self.assertEqual(code, 0)
        self.assertEqual(text.count("note: live - Live one"), 1)
        self.assertNotIn("Dead one", text)
        data = json.loads(run(["--project", self.root, "service", SVC, "--json"])[1])
        self.assertEqual(data["results"][0]["hits"][0]["notes"][0]["slug"], "live")

    def test_search_does_not_return_notes_shard(self):
        self.assertNotIn("Env fact", run(["--project", self.root, "search", "env"])[1])

    def test_notes_edit_makes_shard_stale_and_cli_does_not_refresh(self):
        out = os.path.join(self.root, ".oro-ai", "atlas")
        self.assertEqual(index.shard_status(self.root, out, ["notes"])["notes"]["state"], "fresh")
        write_note(self.root, "newer", "Newer", surface="always")
        self.assertEqual(index.shard_status(self.root, out, ["notes"])["notes"]["state"], "stale")
        code, text = run(["--project", self.root, "notes", "newer"])
        self.assertEqual(index.shard_status(self.root, out, ["notes"])["notes"]["state"], "stale")
        self.assertEqual(code, 1, text)


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.root = project("7.0.3")
        write_note(self.root, "p", "Path note", anchors="path:src/Acme/**/Svc*.php")
        write_note(self.root, "b", "Bundle note", anchors="bundle:LiveBundle")
        os.makedirs(os.path.join(self.root, "src", "Acme", "Bundle", "LiveBundle"))
        open(os.path.join(self.root, "src", "Acme", "Bundle", "LiveBundle", "Svc.php"), "w").close()
        open(os.path.join(self.root, "src", "Acme", "Bundle", "LiveBundle", "LiveBundle.php"), "w").close()
        write_note(self.root, "v8", "Eight only", surface="always", extra="oro: '>=8.0'\n")
        build_notes(self.root)
        self.notes = notesindex.load(os.path.join(self.root, ".oro-ai", "atlas"))

    def test_anchored_for_path_via_glob_and_bundle(self):
        got = notesindex.anchored_for_path(self.notes, "src/Acme/Bundle/LiveBundle/Svc.php", "7.0.3")
        self.assertEqual(sorted(n["id"] for n in got), ["b", "p"])
        self.assertEqual(notesindex.anchored_for_path(self.notes, "src/Other/Foo.php", "7.0.3"), [])

    def test_out_of_range_note_hidden_unless_all(self):
        self.assertNotIn("v8", run(["--project", self.root, "notes", "--always"])[1])
        code, text = run(["--project", self.root, "notes", "--always", "--all"])
        self.assertIn("v8", text)
        self.assertIn("inactive oro >=8.0", text)
        self.assertEqual(notesindex.always_notes(self.notes, "8.0.0")[0][0]["id"], "v8")

    def test_always_cap(self):
        notes = [{"id": "n%02d" % i, "surface": "always", "updated": "2026-01-%02d" % (i % 28 + 1), "oro": None} for i in range(45)]
        shown, more = notesindex.always_notes(notes, None)
        self.assertEqual((len(shown), more), (40, 5))
        self.assertEqual(shown[0]["updated"], "2026-01-28")


class EmptyTest(unittest.TestCase):
    def test_no_notes_dir_builds_empty_shard(self):
        root = project()
        self.assertEqual(build_notes(root), {"notes": 0})
        self.assertEqual(run(["--project", root, "notes", "--always"]), (1, "no notes\n"))


if __name__ == "__main__":
    unittest.main()
