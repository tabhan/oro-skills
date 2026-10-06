import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas.extractors import config  # noqa: E402
from atlas.miniyaml import parse  # noqa: E402

BUNDLE_A = """\
system_configuration:
    groups:
        calendar_settings:
            title: oro.calendar.groups.title  # trailing comment
    fields:
        oro_calendar.colors:
            data_type: array
            type: Oro\\Bundle\\FormBundle\\Form\\Type\\OroColorTableType
            priority: 10
            ui_only: true
            options:
                label: oro.calendar.fields.colors.label
                constraints:
                    - NotBlank: ~
                    - Range:
                        min: 1
        oro_calendar.orphan:
            data_type: string
    tree:
        system_configuration:
            platform:
                children:
                    look_and_feel:
                        children:
                            calendar_settings:
                                children:
                                    - oro_calendar.colors
        website_configuration:
            platform:
                children:
                    look_and_feel:
                        children:
                            calendar_settings:
                                children:
                                    - oro_calendar.colors
    api_tree:
        look-and-feel:
            oro_calendar.colors: ~
"""

BUNDLE_B = """\
system_configuration:
    fields:
        oro_calendar.colors:
            data_type: array
"""


class FakeCtx:
    def __init__(self, root):
        self.root = root

    def rel(self, path):
        return os.path.relpath(path, self.root)


def write(root, rel, text):
    path = os.path.join(root, rel, "Resources", "config", "oro", "system_configuration.yml")
    os.makedirs(os.path.dirname(path))
    open(path, "w").write(text)


class MiniYamlTest(unittest.TestCase):
    def test_lines_lists_and_flow(self):
        d = parse("a:\n  b: 1\n  c: [x, y]\n  d:\n    - p\n    - q\n  e: ~\n")
        self.assertEqual(d["a"]["b"], 1)
        self.assertEqual(d["a"]["c"], ["x", "y"])
        self.assertEqual(list(d["a"]["d"]), ["p", "q"])
        self.assertEqual(d["a"]["d"].lines, [5, 6])
        self.assertEqual(d["a"].lines["c"], 3)
        self.assertIsNone(d["a"]["e"])

    def test_block_scalar_and_quoted_key(self):
        d = parse("x:\n  'data-k': 'v # not comment'\n  t: |\n    free\n    text\n  z: 2\n")
        self.assertEqual(d["x"]["data-k"], "v # not comment")
        self.assertEqual(d["x"]["z"], 2)


    def test_wrapped_scalar_does_not_truncate_siblings(self):
        d = parse("f:\n  a:\n    l: 'foo\n      bar'\n    t: x\n  b:\n    t: y\n")
        self.assertEqual(d["f"]["a"]["t"], "x")
        self.assertEqual(d["f"]["b"]["t"], "y")

    def test_anchor_does_not_hide_nested_block(self):
        self.assertEqual(parse("a: &x\n  b: 1\n")["a"]["b"], 1)


class ConfigExtractorTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        write(self.root, "vendor/oro/calendar", BUNDLE_A)
        write(self.root, "src/App/Bundle", BUNDLE_B)
        write(self.root, "vendor/oro/calendar/Tests/Fixtures", BUNDLE_B)
        self.recs = {r["id"]: r for r in config.extract(FakeCtx(self.root))}

    def test_field_basics(self):
        r = self.recs["oro_calendar.colors"]
        self.assertEqual(r["data_type"], "array")
        self.assertEqual(r["form_type"].rsplit("\\", 1)[-1], "OroColorTableType")
        self.assertTrue(r["ui_only"])
        self.assertTrue(r["file"].startswith("src/") or "vendor/oro" in r["file"])
        self.assertIn("oro_calendar__colors", r["keys"])

    def test_scopes_tree_and_titles(self):
        r = self.recs["oro_calendar.colors"]
        self.assertEqual(r["scopes"], ["global", "website"])
        self.assertEqual(r["tree_path"], "platform > look_and_feel > calendar_settings")
        self.assertEqual(r["group_titles"], {"calendar_settings": "oro.calendar.groups.title"})
        self.assertEqual(r["api_section"], "look-and-feel")

    def test_multiple_definitions_and_tests_dir_skipped(self):
        self.assertEqual(len(self.recs["oro_calendar.colors"]["defined_in"]), 2)

    def test_non_mapping_document_does_not_crash(self):
        path = os.path.join(self.root, "list.yml")
        open(path, "w").write("- a\n- b\n")
        self.assertEqual(config._load(path, "list.yml"), ({}, {}, {}, {}))

    def test_unplaced_field(self):
        r = self.recs["oro_calendar.orphan"]
        self.assertEqual(r["scopes"], [])
        self.assertIn("unplaced", r["text"])
        self.assertIsInstance(r["line"], int)


if __name__ == "__main__":
    unittest.main()
