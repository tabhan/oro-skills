import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas.extractors import layout  # noqa: E402

SERVICES = """services:
    acme.abstract:
        abstract: true
        class: Acme\\ConfigurableType
    acme.abstract_container:
        abstract: true
        parent: acme.abstract
        calls:
            - [setParent, ['container']]
    acme.block.box:
        parent: acme.abstract_container
        calls:
            - [setOptionsConfig, [{title: {default: ''}, size: {required: true}}]]
            - [setName, ['box']]
        tags:
            - { name: layout.block_type, alias: box }
"""

LAYOUT = """layout:
    actions:
        - '@add':
            id: hello
            parentId: page_content
        - '@remove': old_block
        - '@setOption':
            id: hello
    conditions: 'context["x"]'
"""


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


class FakeLocator:
    def locate(self, fqcn):
        return (None, None)

    def file_of(self, fqcn):
        return None


class FakeCtx:
    def __init__(self, root, defs):
        self.root = root
        self.locator = FakeLocator()
        self._defs = defs

    def container(self):
        return {"definitions": self._defs, "aliases": {}}


def make_root():
    root = tempfile.mkdtemp()
    base = os.path.join(root, "src", "Acme", "FooBundle", "Resources")
    write(os.path.join(base, "views", "layouts", "default", "theme.yml"), "label: Base\n")
    write(os.path.join(base, "views", "layouts", "child", "theme.yml"), "parent: default\nlabel: 'Kid'\n")
    write(os.path.join(base, "views", "layouts", "default", "my_route", "layout.yml"), LAYOUT)
    write(os.path.join(base, "views", "layouts", "default", "config", "jsmodules.yml"), "")
    write(os.path.join(base, "views", "layouts", "default", "blocks.html.twig"), "")
    write(os.path.join(base, "config", "block_types.yml"), SERVICES)
    # Fixture themes under Tests must never appear.
    write(os.path.join(root, "src", "Acme", "FooBundle", "Tests", "Resources", "views", "layouts", "bad", "theme.yml"))
    return root


class ParsersTest(unittest.TestCase):
    def test_theme_yml_top_level_only(self):
        d = layout.parse_theme_yml("label: 'Kid'\nparent: default\nfonts:\n    main:\n        family: x\n")
        self.assertEqual((d["label"], d["parent"]), ("Kid", "default"))
        self.assertNotIn("family", d)

    def test_layout_yml_actions_and_ids(self):
        info = layout.parse_layout_yml(LAYOUT)
        self.assertEqual(info["actions"], {"add": 1, "remove": 1, "setOption": 1})
        self.assertEqual(info["ids"]["add"], ["hello"])
        self.assertEqual(info["ids"]["remove"], ["old_block"])
        self.assertEqual(info["conditions"], 'context["x"]')

    def test_layout_yml_twig_refs_imports_and_quoted_conditions(self):
        text = ("layout:\n    actions:\n        - '@setBlockTheme':\n            themes: '@OroCheckout/layouts/x.html.twig'\n"
                "        - '@move': { id: a_block, parentId: b }\n"
                "    imports:\n        - id: imported_root\n    conditions: 'context[\"s\"]==\"pay\"'\n")
        info = layout.parse_layout_yml(text)
        self.assertEqual(info["actions"], {"setBlockTheme": 1, "move": 1})
        self.assertEqual(info["ids"], {"move": ["a_block"]})
        self.assertEqual(info["conditions"], 'context["s"]=="pay"')

    def test_classify(self):
        self.assertEqual(layout._classify(os.path.join("config", "assets.yml")), "theme_config")
        self.assertEqual(layout._classify("a/layout.html.twig"), "block_theme")
        self.assertEqual(layout._classify("theme.yml"), "theme_yml")
        self.assertEqual(layout._classify("r/layout.yml"), "layout_update")

    def test_chain_stops_on_cycle(self):
        self.assertEqual(layout._chain("a", {"a": "b", "b": "c", "c": "a"}), ["b", "c"])

    def test_service_chunks_and_parent_alias(self):
        root = make_root()
        index = layout.configurable_index(root)
        self.assertEqual(layout._cfg_parent_alias(index, "acme.block.box"), "container")
        self.assertEqual(layout._cfg_options(index["acme.block.box"]), ["size", "title"])


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root()
        defs = {"acme.block.box": {"class": "Acme\\ConfigurableType", "tags": [
            {"name": "layout.block_type", "parameters": {"alias": "box"}}]},
            "acme.provider": {"class": "Acme\\P", "tags": [
                {"name": "layout.data_provider", "parameters": {"alias": "acme_data"}}]}}
        self.defs = defs
        self.recs = {r["id"]: r for r in layout.extract(FakeCtx(self.root, defs))}

    def test_theme_parent_and_children(self):
        self.assertEqual(self.recs["theme:child"]["chain"], ["default"])
        self.assertEqual(self.recs["theme:default"]["children"], ["child"])
        self.assertNotIn("theme:bad", self.recs)

    def test_block_type_and_provider(self):
        box = self.recs["block:box"]
        self.assertEqual((box["parent_alias"], box["configurable"]), ("container", True))
        self.assertTrue(box["file"].endswith("block_types.yml"))
        self.assertIn("data['acme_data']", self.recs["data:acme_data"]["text"])

    def test_update_records(self):
        rec = self.recs["default/my_route/layout.yml@FooBundle"]
        self.assertEqual((rec["kind"], rec["route"], rec["project"]), ("layout_update", "my_route", True))
        self.assertEqual(rec["block_ids"]["remove"], ["old_block"])
        self.assertEqual(self.recs["default/config/jsmodules.yml@FooBundle"]["kind"], "theme_config")
        self.assertEqual(self.recs["default/blocks.html.twig@FooBundle"]["kind"], "block_theme")

    def test_route_is_first_dir_and_ids_unique(self):
        self.assertEqual(layout._route("my_route/page_template/tabs"), "my_route")
        self.assertEqual(layout._route("page/sub"), "")
        ids = [r["id"] for r in layout.extract(FakeCtx(self.root, self.defs))]
        self.assertEqual(len(ids), len(set(ids)))

    def test_names_unique(self):
        self.assertEqual(layout.NAME, "layouts")


if __name__ == "__main__":
    unittest.main()
