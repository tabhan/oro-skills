import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas.extractors import unsafe  # noqa: E402

SRC = """<?php
namespace Oro\\Bundle\\FooBundle\\Service;

use Oro\\Bundle\\BarBundle\\Manager\\BarManager;
use Oro\\Bundle\\BarBundle\\Repo\\{AlphaRepo, BetaRepo as Beta};
use Oro\\Bundle\\BarBundle\\Contract\\Thing as ThingContract;

class Consumer
{
    public function __construct(
        #[Autowire(service: 'x', args: [1, 2])]
        private readonly BarManager $bar,
        protected ?Beta $beta,
        \\Aaxis\\Bundle\\ZBundle\\Full $full,
        AlphaRepo|ThingContract $union,
        SiblingClass $sibling,
        string $name = 'a,b',
        array $opts = array(1, 2),
        self $me = null,
        callable ...$rest
    ) {
    }
}
"""


class ParseTest(unittest.TestCase):
    def test_ctor_types_resolves_imports_group_use_and_namespace(self):
        line, types = unsafe.ctor_types(SRC)
        self.assertEqual(line, 10)
        self.assertEqual(types, [
            "Oro\\Bundle\\BarBundle\\Manager\\BarManager",
            "Oro\\Bundle\\BarBundle\\Repo\\BetaRepo",
            "Aaxis\\Bundle\\ZBundle\\Full",
            "Oro\\Bundle\\BarBundle\\Repo\\AlphaRepo",
            "Oro\\Bundle\\BarBundle\\Contract\\Thing",
            "Oro\\Bundle\\FooBundle\\Service\\SiblingClass",
        ])

    def test_intersection_and_by_ref_types(self):
        src = "<?php\nnamespace Oro\\X;\nuse Oro\\A\\Foo;\nuse Oro\\A\\Bar;\nclass K {\n public function __construct(Foo&Bar $a, Foo &$b) {}\n}\n"
        self.assertEqual(unsafe.ctor_types(src)[1], ["Oro\\A\\Foo", "Oro\\A\\Bar", "Oro\\A\\Foo"])

    def test_no_constructor(self):
        self.assertEqual(unsafe.ctor_types("<?php class A {}"), (None, []))

    def test_declaration_kinds(self):
        pairs = {
            "abstract class A {}": "abstract",
            "final class A {}": "final",
            "interface A {}": "interface",
            "class A {}": "class",
            "trait A {}": "trait",
        }
        for code, kind in pairs.items():
            self.assertEqual(unsafe.declaration("<?php\nnamespace N;\n" + code), ("N\\A", kind))


def svc(sid, cls, tags=(), abstract=False):
    return {"id": sid, "class": cls, "tags": list(tags), "abstract": abstract}


class JoinTest(unittest.TestCase):
    def test_plain_service_maps_class_to_id(self):
        out = unsafe.join_services([svc("a", "Oro\\A"), svc("tpl", "Oro\\A", abstract=True)])
        self.assertEqual(out["Oro\\A"], {"ids": ["a"], "decorated_by": [], "decorator_classes": []})

    def test_decorated_original_is_reported_under_public_id(self):
        tag = {"name": "container.decorator", "attrs": {"id": "oro.pub", "inner": "dec.inner"}}
        out = unsafe.join_services([
            svc("dec", "Buckman\\Dec", [tag]),
            svc("dec.inner", "Oro\\Orig"),
        ])
        self.assertEqual(out["Oro\\Orig"]["ids"], ["oro.pub"])
        self.assertEqual(out["Oro\\Orig"]["decorated_by"], ["dec"])
        self.assertEqual(out["Oro\\Orig"]["decorator_classes"], ["Buckman\\Dec"])
        self.assertEqual(out["Buckman\\Dec"]["ids"], ["dec"])


class ExtractTest(unittest.TestCase):
    def test_only_concrete_typehinted_classes_are_emitted(self):
        import tempfile

        root = tempfile.mkdtemp()
        d = os.path.join(root, "src", "N")
        os.makedirs(d)
        files = {
            "Dep.php": "<?php\nnamespace Oro\\N;\nclass Dep {}\n",
            "Iface.php": "<?php\nnamespace Oro\\N;\ninterface Iface {}\n",
            "Abs.php": "<?php\nnamespace Oro\\N;\nabstract class Abs {}\n",
            "Use.php": "<?php\nnamespace Oro\\N;\nclass Use1 {\n function __construct(Dep $a, Iface $b, Abs $c) {}\n}\n",
        }
        for name, body in files.items():
            open(os.path.join(d, name), "w").write(body)

        class Loc:
            def locate(self, fqcn):
                return ("src/N/Dep.php", 3)

        class Ctx:
            vendor_memo = staticmethod(lambda name, key, compute: compute())

        ctx = Ctx()
        ctx.root = root
        ctx.locator = Loc()
        ctx.shard = lambda name: [svc("dep.svc", "Oro\\N\\Dep")]
        recs = list(unsafe.extract(ctx))
        self.assertEqual([r["id"] for r in recs], ["Oro\\N\\Dep"])
        self.assertEqual(recs[0]["services"], ["dep.svc"])
        self.assertEqual(recs[0]["consumers"][0]["class"], "Oro\\N\\Use1")
        self.assertEqual(recs[0]["consumers"][0]["line"], 4)
        self.assertIn("aaxis_aspect.interceptor", recs[0]["text"])

    def test_decorator_only_consumer_is_not_a_reason(self):
        import tempfile

        root = tempfile.mkdtemp()
        d = os.path.join(root, "src")
        os.makedirs(d)
        open(os.path.join(d, "A.php"), "w").write("<?php\nnamespace Oro;\nclass Orig {}\n")
        open(os.path.join(d, "B.php"), "w").write(
            "<?php\nnamespace Buckman;\nclass Dec {\n function __construct(\\Oro\\Orig $i) {}\n}\n"
        )
        tag = {"name": "container.decorator", "attrs": {"id": "pub", "inner": "dec.inner"}}
        rows = [svc("dec", "Buckman\\Dec", [tag]), svc("dec.inner", "Oro\\Orig")]

        class Ctx:
            vendor_memo = staticmethod(lambda name, key, compute: compute())
            locator = type("L", (), {"locate": lambda self, f: (None, None)})()

        ctx = Ctx()
        ctx.root = root
        ctx.shard = lambda name: rows
        self.assertEqual(list(unsafe.extract(ctx)), [])


def _ctx(root, rows, located=None):
    class Ctx:
        vendor_memo = staticmethod(lambda name, key, compute: compute())

    located = located or {}
    ctx = Ctx()
    ctx.root = root
    ctx.shard = lambda name: rows
    ctx.locator = type("L", (), {"locate": lambda self, f: located.get(f, (None, None))})()
    return ctx


def _tree(files):
    import tempfile

    root = tempfile.mkdtemp()
    for rel, body in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(body)
    return root


class GapTest(unittest.TestCase):
    def test_final_class_gets_non_interceptor_advice(self):
        root = _tree({
            "src/F.php": "<?php\nnamespace Oro\\N;\nfinal class Fin {}\n",
            "src/U.php": "<?php\nnamespace Oro\\N;\nclass U {\n function __construct(Fin $f) {}\n}\n",
            "src/D.php": "<?php\nnamespace Oro\\N;\nclass Dep {}\n",
            "src/V.php": "<?php\nnamespace Oro\\N;\nclass V {\n function __construct(Dep $f) {}\n}\n",
        })
        recs = {r["id"]: r for r in unsafe.extract(_ctx(root, []))}
        self.assertIn("cannot proxy a final class", recs["Oro\\N\\Fin"]["text"])
        self.assertNotIn("use aaxis_aspect.interceptor", recs["Oro\\N\\Fin"]["text"])
        self.assertIn("final/static/private methods are skipped", recs["Oro\\N\\Dep"]["text"])

    def test_parent_typehint_makes_subclass_service_unsafe(self):
        root = _tree({
            "src/P.php": "<?php\nnamespace Oro\\N;\nabstract class Base {}\n",
            "src/S.php": "<?php\nnamespace Oro\\N\\Sub;\nuse Oro\\N\\Base;\nclass Child extends Base {}\n",
            "src/U.php": "<?php\nnamespace Oro\\N;\nclass U {\n function __construct(Base $b) {}\n}\n",
        })
        recs = list(unsafe.extract(_ctx(root, [svc("child.svc", "Oro\\N\\Sub\\Child")])))
        self.assertEqual([r["id"] for r in recs], ["Oro\\N\\Sub\\Child"])
        self.assertEqual(recs[0]["consumers"][0]["via"], "Oro\\N\\Base")
        self.assertEqual(recs[0]["services"], ["child.svc"])

    def test_vendor_abstract_base_typehint_is_not_followed(self):
        root = _tree({
            "vendor/symfony/C.php": "<?php\nnamespace Symfony\\C;\nabstract class Command {}\n",
            "vendor/symfony/H.php": "<?php\nnamespace Symfony\\C;\nclass Help {}\n",
            "src/K.php": "<?php\nnamespace Aaxis\\N;\nuse Symfony\\C\\Command;\nfinal class Cmd extends Command {}\n",
            "src/L.php": "<?php\nnamespace Aaxis\\N;\nuse Symfony\\C\\Help;\nclass Sub extends Help {}\n",
            "src/A.php": "<?php\nnamespace Symfony\\C;\nclass App {\n function __construct(Command $c, Help $h) {}\n}\n",
        })
        rows = [svc("cmd", "Aaxis\\N\\Cmd"), svc("sub", "Aaxis\\N\\Sub")]
        located = {"Symfony\\C\\Command": ("vendor/symfony/C.php", 3)}
        ids = [r["id"] for r in unsafe.extract(_ctx(root, rows, located))]
        self.assertNotIn("Aaxis\\N\\Cmd", ids)
        self.assertIn("Aaxis\\N\\Sub", ids)

    def test_concrete_symfony_command_base_is_not_followed(self):
        root = _tree({
            "src/K.php": "<?php\nnamespace Aaxis\\N;\nuse Symfony\\Component\\Console\\Command\\Command;\n"
                         "final class Cmd extends Command {}\n",
            "src/E.php": "<?php\nnamespace Oro\\N;\nuse Symfony\\Component\\Console\\Command\\Command;\n"
                         "class Ev {\n function __construct(Command $c) {}\n}\n",
        })
        self.assertEqual(list(unsafe.extract(_ctx(root, [svc("cmd", "Aaxis\\N\\Cmd")]))), [])

    def test_project_abstract_parent_typehint_reaches_concrete_child(self):
        root = _tree({
            "src/P.php": "<?php\nnamespace Buckman\\N;\nabstract class Base {}\n",
            "src/S.php": "<?php\nnamespace Buckman\\N;\nclass Child extends Base {}\n",
            "vendor/oro/U.php": "<?php\nnamespace Oro\\N;\nuse Buckman\\N\\Base;\nclass U {\n function __construct(Base $b) {}\n}\n",
        })
        recs = list(unsafe.extract(_ctx(root, [svc("child", "Buckman\\N\\Child")])))
        self.assertEqual([r["id"] for r in recs], ["Buckman\\N\\Child"])
        self.assertEqual(recs[0]["consumers"][0]["via"], "Buckman\\N\\Base")

    def test_third_party_service_class_is_included(self):
        root = _tree({
            "vendor/symfony/RS.php": "<?php\nnamespace Symfony\\H;\nclass RequestStack {}\n",
            "src/U.php": "<?php\nnamespace Oro\\N;\nuse Symfony\\H\\RequestStack;\n"
                         "class U {\n function __construct(RequestStack $r) {}\n}\n",
        })
        rows = [svc("request_stack", "Symfony\\H\\RequestStack")]
        ctx = _ctx(root, rows, {"Symfony\\H\\RequestStack": ("vendor/symfony/RS.php", 3)})
        recs = list(unsafe.extract(ctx))
        self.assertEqual([r["id"] for r in recs], ["Symfony\\H\\RequestStack"])
        self.assertEqual(recs[0]["services"], ["request_stack"])

    def test_third_party_without_service_is_ignored(self):
        root = _tree({
            "src/U.php": "<?php\nnamespace Oro\\N;\nuse Vendor\\X;\nclass U {\n function __construct(X $r) {}\n}\n",
        })
        self.assertEqual(list(unsafe.extract(_ctx(root, []))), [])

    def test_setter_and_required_property_injection(self):
        src = (
            "<?php\nnamespace Oro\\N;\nuse Oro\\M\\A;\nuse Oro\\M\\B;\nuse Symfony\\Contracts\\Service\\Attribute\\Required;\n"
            "class C {\n    #[Required]\n    public B $b;\n    public function setA(A $a): void {}\n"
            "    public function getX(Oro\\M\\Z $z) {}\n}\n"
        )
        line, types = unsafe.injection_types(src)
        self.assertEqual(sorted(types), ["Oro\\M\\A", "Oro\\M\\B"])
        self.assertEqual(line, 7)

    def test_resolve_short_name(self):
        self.assertEqual(unsafe.resolve_short_name(SRC, "BarManager"), "Oro\\Bundle\\BarBundle\\Manager\\BarManager")
        self.assertEqual(unsafe.resolve_short_name(SRC, "Beta"), "Oro\\Bundle\\BarBundle\\Repo\\BetaRepo")
        self.assertEqual(unsafe.resolve_short_name(SRC, "Local"), "Oro\\Bundle\\FooBundle\\Service\\Local")
        self.assertEqual(unsafe.resolve_short_name(SRC, "\\X\\Y"), "X\\Y")


if __name__ == "__main__":
    unittest.main()
