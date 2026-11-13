import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas.extractors import grids  # noqa: E402

YML = """\
datagrids:
    base-grid:
        extended_entity_name: 'Oro\\Bundle\\ProductBundle\\Entity\\Product'
        source:
            type: orm
            acl_resource: oro_product_view
            query:
                from:
                    - { table: 'Other\\Entity', alias: o }
        columns:
            extends: not-a-parent
    child-grid:
        extends: base-grid
        options:
            x: 1
    from-grid:
        source:
            type: orm
            query:
                from:
                    - { table: Acme\\Entity\\Foo, alias: f }
other: 1
"""


class ParseTest(unittest.TestCase):
    def test_parse(self):
        got = {n: (l, i) for n, l, i in grids.parse_datagrids(YML)}
        self.assertEqual(set(got), {"base-grid", "child-grid", "from-grid"})
        self.assertEqual(got["base-grid"][0], 2)
        info = got["base-grid"][1]
        self.assertEqual(info["entity"], "Oro\\Bundle\\ProductBundle\\Entity\\Product")
        self.assertEqual(info["source_type"], "orm")
        self.assertEqual(info["acl_resource"], "oro_product_view")
        self.assertIsNone(info["extends"])
        self.assertEqual(got["child-grid"][1]["extends"], "base-grid")
        self.assertEqual(got["from-grid"][1]["entity"], "Acme\\Entity\\Foo")

    def test_two_space_indent_and_no_section(self):
        self.assertEqual(grids.parse_datagrids("foo: 1\n"), [])
        r = grids.parse_datagrids("datagrids:\n  g:\n    extends: h\n")
        self.assertEqual((r[0][0], r[0][2]["extends"]), ("g", "h"))

    def test_nested_type_and_null_entity_ignored(self):
        yml = ("datagrids:\n    g:\n        extended_entity_name: ~\n        source:\n"
               "            query:\n                select: [a]\n            bind_parameters:\n"
               "                - { name: x, type: integer }\n            type: orm\n")
        info = grids.parse_datagrids(yml)[0][2]
        self.assertEqual((info["source_type"], info["entity"]), ("orm", None))

    def test_split_event(self):
        names = {"a-grid", "x.y"}
        self.assertEqual(grids._split_grid_event("oro_datagrid.datagrid.build.after.a-grid", names),
                         ("oro_datagrid.datagrid.build.after", "a-grid"))
        self.assertEqual(grids._split_grid_event("oro_datagrid.datagrid.build.after.x.y", names),
                         ("oro_datagrid.datagrid.build.after", "x.y"))
        self.assertEqual(grids._split_grid_event("oro_datagrid.datagrid.build.after", names),
                         ("oro_datagrid.datagrid.build.after", None))

    def test_collect_listeners(self):
        ev = {
            "oro_datagrid.datagrid.build.after": [{"class": "A", "name": "m", "priority": 1}],
            "oro_datagrid.datagrid.build.after.g": [{"class": "B", "name": "n", "priority": 0}],
            "kernel.request": [{"class": "C", "name": "o", "priority": 0}],
        }
        out = grids.collect_listeners(ev, {"g"})
        self.assertEqual([(l["class"], l["grid"]) for l in out], [("A", None), ("B", "g")])


class ExtractTest(unittest.TestCase):
    def test_extract_links_listeners_and_overrides(self):
        root = tempfile.mkdtemp()
        for rel in ("vendor/oro/p/src/XBundle", "src/Buckman/YBundle"):
            d = os.path.join(root, rel, "Resources", "config", "oro")
            os.makedirs(d)
        open(os.path.join(root, "vendor/oro/p/src/XBundle/Resources/config/oro/datagrids.yml"), "w").write(YML)
        open(os.path.join(root, "src/Buckman/YBundle/Resources/config/oro/datagrids.yml"), "w").write(
            "datagrids:\n    base-grid:\n        options:\n            y: 1\n")

        class Loc:
            def locate(self, c):
                return (None, None)

        class Ctx:
            locator = Loc()

            def __init__(self, r):
                self.root = r

            def rel(self, p):
                return os.path.relpath(p, self.root)

            def container(self):
                return {"definitions": {}}

            def events(self):
                return {"oro_datagrid.datagrid.build.after.base-grid": [{"class": "L", "name": "go", "priority": 5}]}

        recs = {r["id"]: r for r in grids.extract(Ctx(root))}
        g = recs["base-grid"]
        self.assertTrue(g["file"].startswith("vendor/"))
        self.assertEqual(len(g["also_defined"]), 1)
        self.assertEqual(g["extended_by"], ["child-grid"])
        self.assertEqual(len(g["listeners"]), 1)
        lid = "oro_datagrid.datagrid.build.after.base-grid L::go"
        self.assertEqual(recs[lid]["grid"], "base-grid")
        # child inherits entity/source from its parent
        self.assertEqual(recs["child-grid"]["entity"], "Oro\\Bundle\\ProductBundle\\Entity\\Product")
        self.assertEqual(recs["child-grid"]["source_type"], "orm")

    def test_layout_grids_and_proxy_unwrap(self):
        root = tempfile.mkdtemp()
        d = os.path.join(root, "vendor/oro/p/src/XBundle/Resources/views/layouts/default/config")
        os.makedirs(d)
        open(os.path.join(d, "datagrids.yml"), "w").write("datagrids:\n    frontend-g:\n        source:\n            type: orm\n")
        self.assertEqual(len(grids.find_files(root)), 1)
        resolve = grids.proxy_resolver({"s": {"class": "Acme\\Foo\\MyListener"}})
        self.assertEqual(resolve("Container06xdvKi\\MyListenerProxy0a6f83a"), "Acme\\Foo\\MyListener")
        self.assertEqual(resolve("Plain\\Thing"), "Plain\\Thing")


if __name__ == "__main__":
    unittest.main()
