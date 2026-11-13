import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas.extractors import tags  # noqa: E402

KNOWN = {"app.handler", "app.other", "app.dyn"}

PASS = """<?php
namespace Acme\\Compiler;

class HandlerPass
{
    const TAG = 'app.handler';
    private string $dyn = 'app.dyn';

    public function process($container)
    {
        $container->findTaggedServiceIds(self::TAG);
        $container->findTaggedServiceIds('app.other', true);
    }
}
"""

BUNDLE = """<?php
namespace Acme;
class AcmeBundle {
    public function build($c) { $c->addCompilerPass(new PriorityTaggedLocatorCompilerPass('svc', 'app.handler')); }
}
"""

YAML = """services:
    acme.registry:
        class: Acme\\Registry
        arguments:
            - !tagged_iterator app.handler
    acme.other:
        arguments: [!tagged_locator { tag: 'app.other', index_by: key }]
other:
    x: !tagged_iterator app.dyn
"""


class ScanTest(unittest.TestCase):
    def test_php_constant_and_literal_calls(self):
        got = {(t, via, conf) for t, _, via, conf in tags.scan_php(PASS, KNOWN)}
        self.assertIn(("app.handler", "findTaggedServiceIds", "call"), got)
        self.assertIn(("app.other", "findTaggedServiceIds", "call"), got)

    def test_php_property_tag_is_file_confidence(self):
        got = {t: conf for t, _, _, conf in tags.scan_php(PASS, KNOWN)}
        self.assertEqual(got["app.dyn"], "file")

    def test_unknown_tag_ignored_and_plain_file_skipped(self):
        self.assertEqual(tags.scan_php("<?php $x = 'app.handler';", KNOWN), [])
        self.assertEqual(tags.scan_php(PASS, {"zzz"}), [])

    def test_bundle_pass_arg(self):
        got = tags.scan_php(BUNDLE, KNOWN)
        self.assertEqual([(t, c) for t, _, _, c in got], [("app.handler", "call")])

    def test_cross_class_constant_resolved(self):
        src = "<?php\nclass P { function f($c) { $c->findTaggedServiceIds(Util::PROC_TAG); } }"
        got = tags.scan_php(src, KNOWN, {("Util", "PROC_TAG"): "app.handler"})
        self.assertEqual([(t, c) for t, _, _, c in got], [("app.handler", "call")])
        self.assertEqual(tags.scan_php(src, KNOWN), [])

    def test_php_class_name(self):
        self.assertEqual(tags.php_class(PASS), "Acme\\Compiler\\HandlerPass")

    def test_yaml_quoted_hash_and_sections_outside_services(self):
        text = ("parameters:\n    p: '!tagged_iterator app.handler'\nservices:\n"
                "    a.svc:\n        arguments: ['#x', !tagged_iterator app.handler] # c\n"
                "when@test:\n    services:\n        c: [!tagged_iterator app.other]\n")
        self.assertEqual(tags.scan_yaml(text, KNOWN), [("app.handler", 5, "a.svc")])

    def test_yaml_owner_tracking(self):
        got = tags.scan_yaml(YAML, KNOWN)
        self.assertEqual([(t, o) for t, _, o in got], [("app.handler", "acme.registry"), ("app.other", "acme.other")])


class FakeLocator:
    def locate(self, cls):
        return ("src/%s.php" % cls, 3) if cls else (None, None)


class FakeCtx:
    locator = FakeLocator()


class ImplementersTest(unittest.TestCase):
    def test_grouping_and_attr_normalisation(self):
        defs = {
            "b": {"class": "B", "tags": [{"name": "t", "parameters": []}]},
            "a": {"class": "A", "tags": [{"name": "t", "parameters": {"alias": "x"}}, {"name": "u", "parameters": []}]},
            ".anon": {"class": "", "tags": [{"name": "t", "parameters": []}]},
        }
        by = tags.build_implementers(FakeCtx(), defs)
        self.assertEqual([i["id"] for i in by["t"]], ["a", "b"])
        self.assertEqual(by["t"][0]["attrs"], {"alias": "x"})
        self.assertEqual(by["t"][1]["attrs"], {})
        self.assertEqual(by["t"][0]["file"], "src/A.php")

    def test_text_summary(self):
        impls = [{"class": "N\\A"}, {"class": "N\\B"}]
        cons = [{"class": "N\\Pass", "confidence": "call", "file": "f", "line": 1}]
        self.assertEqual(tags._text("t", impls, cons), "2 services; e.g. A, B; consumed by Pass")
        self.assertIn("no static consumer", tags._text("t", impls, []))


if __name__ == "__main__":
    unittest.main()
