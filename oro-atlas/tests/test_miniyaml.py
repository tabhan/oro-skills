import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas.common import read_text, strip_comment  # noqa: E402
from atlas.miniyaml import line_map, parse  # noqa: E402


class StripCommentTest(unittest.TestCase):
    def test_apostrophe_inside_plain_scalar_still_strips(self):
        self.assertEqual(strip_comment("label: don't do this  # note").rstrip(), "label: don't do this")

    def test_quoted_hash_and_escaped_quotes_kept(self):
        self.assertEqual(strip_comment("x: 'a # b' # c").rstrip(), "x: 'a # b'")
        self.assertEqual(strip_comment("x: 'it''s # no' # yes").rstrip(), "x: 'it''s # no'")
        self.assertEqual(strip_comment('x: "a\\" # b" # c').rstrip(), 'x: "a\\" # b"')
        self.assertEqual(strip_comment("url: a#b"), "url: a#b")


class ReadTextTest(unittest.TestCase):
    def test_missing_directory_and_none_read_empty(self):
        self.assertEqual(read_text(os.path.join(tempfile.mkdtemp(), "nope")), "")
        self.assertEqual(read_text(tempfile.mkdtemp()), "")
        self.assertEqual(read_text(None), "")

    def test_bom_and_bad_bytes(self):
        path = os.path.join(tempfile.mkdtemp(), "f.yml")
        with open(path, "wb") as fh:
            fh.write(b"\xef\xbb\xbfa: \xff\n")
        self.assertTrue(read_text(path).startswith("a: "))


class ParseTest(unittest.TestCase):
    def test_flow_map_list_item_is_not_a_key(self):
        tree = parse("imports:\n    - { resource: 'a.yml' }\n    - { workflow: w, as: c }\n")
        self.assertEqual(tree["imports"], [{"resource": "a.yml"}, {"workflow": "w", "as": "c"}])
        self.assertEqual(tree["imports"].lines, [2, 3])

    def test_flow_list_quoted_comma_and_nesting(self):
        self.assertEqual(parse("a: [p, 'q,r', [s, t]]\n")["a"], ["p", "q,r", ["s", "t"]])

    def test_multiline_flow_with_closer_at_key_indent(self):
        tree = parse("c:\n    m: {\n        k: 'v'\n    }\n    n: {}\n")
        self.assertEqual(tree["c"], {"m": {"k": "v"}, "n": {}})

    def test_stray_line_does_not_truncate_rest(self):
        tree = parse("a:\n    b: 1\n      stray\n    not a key\n    c: 2\nd: 3\n")
        self.assertEqual((tree["a"], tree["d"]), ({"b": 1, "c": 2}, 3))

    def test_dedent_below_first_line_keeps_going(self):
        self.assertEqual(parse("  a: 1\nb: 2\n"), {"a": 1, "b": 2})

    def test_line_map(self):
        tree = parse("x:\n    - a\n    - b: 1\n")
        self.assertEqual(line_map(tree), {("x",): 1, ("x", 0): 2, ("x", 1): 3, ("x", 1, "b"): 3})


if __name__ == "__main__":
    unittest.main()
