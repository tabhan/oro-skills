import io
import json
import os
import unittest

os.environ["ATLAS_NO_AUTOBUILD"] = "1"

from atlas import cli, index, store
from tests.test_core import make_project


def _project(shards):
    root = make_project()
    out = os.path.join(root, ".oro-ai", "atlas")
    for name, recs in shards.items():
        store.write_shard(out, name, recs)
    index.update_index(root, out, {k: len(v) for k, v in shards.items()})
    return root


def _run(argv):
    buf = io.StringIO()
    code = cli.main(argv, out=buf)
    return code, buf.getvalue()


FQCN = "Oro\\Bundle\\ProductBundle\\Entity\\Repository\\ProductRepository"


class CliTest(unittest.TestCase):
    def setUp(self):
        self.root = _project({
            "services": [{"id": FQCN, "keys": [FQCN], "text": "class=" + FQCN, "file": "a.php"}],
            "operations": [
                {"id": "DELETE", "text": "op exclude_datagrids=product-grid", "exclude_datagrids": ["product-grid"]},
                {"id": "product-grid", "keys": ["product-grid"], "text": "op"},
            ],
            "js": [
                {"id": "mediator:grid", "keys": ["grid"], "dynamic": True, "text": "mediator grid*"},
                {"id": "mediator:grid-loaded", "keys": ["grid-loaded"], "dynamic": False, "text": "mediator"},
            ],
        })

    def test_fqcn_query_single_double_and_leading_backslash(self):
        for q in (FQCN, FQCN.replace("\\", "\\\\"), "\\" + FQCN):
            code, text = _run(["--project", self.root, "service", q])
            self.assertEqual(code, 0, q)
            self.assertTrue(text.startswith(FQCN), q)

    def test_search_no_hits_prints_and_exits_1(self):
        code, text = _run(["--project", self.root, "search", "zzqqxx"])
        self.assertEqual(code, 1)
        self.assertIn("no hits for 'zzqqxx'", text)

    def test_json_and_project_after_subcommand(self):
        code, text = _run(["operation", "product-grid", "--json", "--project", self.root])
        self.assertEqual(code, 0)
        data = json.loads(text)
        self.assertEqual(data["results"][0]["hits"][0]["id"], "product-grid")

    def test_json_before_subcommand(self):
        code, text = _run(["--json", "--project", self.root, "search", "zzqqxx"])
        self.assertEqual((code, json.loads(text)["results"]), (1, []))

    def test_key_match_beats_list_field_match(self):
        _, text = _run(["--project", self.root, "operation", "product-grid"])
        self.assertTrue(text.startswith("product-grid"))

    def test_plural_alias_matches_singular(self):
        self.assertEqual(_run(["--project", self.root, "operations", "product-grid"]),
                         _run(["--project", self.root, "operation", "product-grid"]))
        for plural in ("operations", "events", "tags", "services", "grids", "layouts", "workflows", "entities", "configs"):
            self.assertIn(cli.CANONICAL[plural], cli.SHARDS, plural)

    def test_dynamic_prefix_record_ranked_after_static(self):
        _, text = _run(["--project", self.root, "js", "grid"])
        self.assertTrue(text.startswith("mediator:grid-loaded"))


if __name__ == "__main__":
    unittest.main()


class RootGateTest(unittest.TestCase):
    """Every atlas entry point shares lib/projroot.py: no root -> exit 64 with its message, nothing created."""
    EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bin", "aaxis-oro")

    def run_cli(self, cwd, *args):
        import subprocess
        import sys
        return subprocess.run([sys.executable, self.EXE, "atlas", *args], cwd=cwd, capture_output=True, text=True)

    def test_outside_a_project_exits_64_and_creates_nothing(self):
        import tempfile
        for args in (["status"], ["service", "x"], ["notes"], ["build"], ["build", "--incremental"], ["migrate"], ["setup"]):
            with tempfile.TemporaryDirectory() as d:
                r = self.run_cli(d, *args)
                self.assertEqual(r.returncode, 64, "%s: %s" % (args, r.stdout + r.stderr))
                self.assertIn("no Oro project found from", r.stderr)
                self.assertEqual(os.listdir(d), [], args)

    def test_non_root_project_exits_64(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for args in (["status"], ["service", "x"], ["build"]):
                r = self.run_cli(d, *args, "--project", d)
                self.assertEqual(r.returncode, 64, "%s: %s" % (args, r.stdout + r.stderr))
                self.assertIn("is not an Oro application root", r.stderr)
            self.assertEqual(os.listdir(d), [])

    def test_root_and_subdirectory_resolve(self):
        sub = os.path.join(_project({}), "sub", "deep")
        r = self.run_cli(sub, "status")
        self.assertIn(r.returncode, (0, 2), r.stdout + r.stderr)
        self.assertIn("oro/platform", r.stdout)
