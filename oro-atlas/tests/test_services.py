import unittest

from atlas.extractors import services


class Locator:
    def locate(self, cls):
        return None, None


class Ctx:
    def __init__(self, defs, aliases=None):
        self.data = {"definitions": defs, "aliases": aliases or {}}
        self.locator = Locator()

    def container(self):
        return self.data


def dec(target, inner, cls):
    return {"class": cls, "tags": [{"name": "container.decorator", "parameters": {"id": target, "inner": inner}}]}


def run(defs, aliases=None):
    return {r["id"]: r for r in services.extract(Ctx(defs, aliases))}


class ServicesTest(unittest.TestCase):
    def test_decorates_uses_tag_id_not_inner(self):
        out = run(
            {"buck.dec": dec("oro.mgr", "buck.dec.inner", "B\\Dec"), "buck.dec.inner": {"class": "Oro\\Mgr"}},
            {"oro.mgr": {"service": "buck.dec"}},
        )
        self.assertEqual(out["buck.dec"]["decorates"], "oro.mgr")
        self.assertEqual(out["buck.dec"]["inner_class"], "Oro\\Mgr")
        self.assertEqual(out["buck.dec.inner"]["decorated_by"], ["buck.dec"])
        self.assertIn("oro.mgr", out["buck.dec.inner"]["keys"])
        self.assertIn("oro.mgr", out["buck.dec"]["keys"])

    def test_inner_id_not_derived_from_suffix(self):
        out = run({"a": dec("oro.x", "weird.id", "A"), "weird.id": {"class": "Oro\\X"}})
        self.assertEqual(out["weird.id"]["decorated_by"], ["a"])
        self.assertEqual(out["a"]["decorates"], "oro.x")

    def test_chain_ordered_outermost_first(self):
        out = run({
            "d1": dec("oro.x", "d1.inner", "D1"),
            "d2": dec("oro.x", "d1", "D2"),
            "d1.inner": {"class": "Oro\\X"},
        })
        self.assertEqual(out["d1.inner"]["decorated_by"], ["d2", "d1"])
        self.assertEqual(out["d1"]["decoration_chain"], ["d2", "d1"])
        self.assertEqual(out["d1"]["decorated_by"], ["d2"])
        self.assertEqual(out["d2"]["decorated_by"], [])
        self.assertIn("decorated_by=d2>d1", out["d1.inner"]["text"])

    def test_parent_exposed_in_keys(self):
        out = run({"child": {"class": "C", "parent": "oro.abstract"}})
        self.assertEqual(out["child"]["parent"], "oro.abstract")
        self.assertIn("oro.abstract", out["child"]["keys"])

    def test_undecorated_plain(self):
        out = run({"s": {"class": "S"}}, {"s.alias": {"service": "s"}})
        self.assertEqual(out["s"]["decorated_by"], [])
        self.assertIsNone(out["s"]["decorates"])
        self.assertEqual(out["s"]["keys"], ["S", "s.alias"])


if __name__ == "__main__":
    unittest.main()
