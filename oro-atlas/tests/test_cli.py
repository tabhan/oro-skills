import io
import json
import os
import unittest

from atlas import cli, index, store
from tests.test_core import make_project


def _project(shards):
    root = make_project()
    out = os.path.join(root, "var", "atlas")
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
