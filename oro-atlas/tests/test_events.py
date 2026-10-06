import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas.extractors import events  # noqa: E402

CONSTS = """<?php
namespace Acme\\Event;
class Names { const A = 'acme.a'; const B = self::A; const C = 'x' . 'y'; const FQ = Other::class; }
class Child extends Names {}
"""

SITE = """<?php
namespace Acme\\Svc;
use Acme\\Event\\Names;
use Acme\\Event\\Child as K;
use Acme\\Event\\FooEvent;
class Svc {
    public function run(FooEvent $typed) {
        $this->eventDispatcher->dispatch($e, 'lit.name');
        $this->eventDispatcher->dispatch($e, Names::A);
        $this->eventDispatcher->dispatch($e, K::B);
        $this->eventDispatcher->dispatch($e, self::LOCAL);
        $this->eventDispatcher->dispatch(new FooEvent($x));
        $this->eventDispatcher->dispatch($typed);
        $this->eventDispatcher->dispatch($e, $name);
        $this->eventDispatcher->dispatch($e, Names::C);
        $this->bus->dispatch(new Msg());
    }
    const LOCAL = 'local.name';
}
"""


class FakeLocator:
    def __init__(self, files):
        self.files = files

    def file_of(self, fqcn):
        return self.files.get(fqcn)


def make():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "Names.php")
    open(p, "w").write(CONSTS)
    loc = FakeLocator({"Acme\\Event\\Names": p, "Acme\\Event\\Child": p})
    return events.Resolver(loc)


class SplitTest(unittest.TestCase):
    def test_split_respects_nesting_and_quotes(self):
        self.assertEqual(events.split_args("new A(1, 2), 'a,b', [1,2]"), ["new A(1, 2)", "'a,b'", "[1,2]"])

    def test_call_args_balanced(self):
        src = "x->dispatch(foo(')'), 'a'); y"
        self.assertEqual(events.call_args(src, src.index("(")), "foo(')'), 'a'")


class ResolveTest(unittest.TestCase):
    def test_const_chain_and_inheritance(self):
        r = make()
        self.assertEqual(r.const_value("Acme\\Event\\Names", "B"), "acme.a")
        self.assertEqual(r.const_value("Acme\\Event\\Child", "A"), "acme.a")
        self.assertEqual(r.const_value("Acme\\Event\\Names", "FQ"), "Acme\\Event\\Other")

    def test_concat_is_unresolved(self):
        self.assertIsNone(make().const_value("Acme\\Event\\Names", "C"))

    def test_sites(self):
        r = make()
        found = list(events.find_dispatch_sites(SITE, "x.php", r))
        names = [n for n, _, _ in found]
        self.assertEqual(names, ["lit.name", "acme.a", "acme.a", None,
                                 "Acme\\Event\\FooEvent", "Acme\\Event\\FooEvent", None, None])
        self.assertEqual(len(found), 8)  # bus->dispatch ignored; self::LOCAL unlocatable in fake


    def test_wrapper_receivers_ignored_and_var_const_resolved(self):
        src = """<?php
namespace Acme\\Svc;
use Acme\\Event\\Names;
class S {
    public function run() {
        $ev = new Names();
        $this->massActionDispatcher->dispatch($a, 'no.wrapper');
        $this->get(MassActionDispatcher::class)->dispatch($a, 'no.wrapper2');
        $this->typeRemovalEventDispatcher->dispatch($a, 'no.wrapper3');
        $this->getEventDispatcher()?->dispatch($ev, $ev::A);
    }
}
"""
        found = list(events.find_dispatch_sites(src, "x.php", make()))
        self.assertEqual([n for n, _, _ in found], ["acme.a"])


    def test_assigned_new_event_resolved(self):
        src = "<?php\nnamespace A;\nclass S { function f() { $this->eventDispatcher->dispatch($ok = new Done($x)); } }"
        self.assertEqual([n for n, _, _ in events.find_dispatch_sites(src, "x.php", make())], ["A\\Done"])


class SymfonyScanTest(unittest.TestCase):
    def test_symfony_scanned_form_skipped_forwarders_not_dynamic(self):
        root = tempfile.mkdtemp()
        body = "<?php\nnamespace S;\nclass K { function f() { $this->dispatcher->dispatch($e, %s); } }"
        for rel, arg in (("vendor/symfony/http-kernel/K.php", "'kernel.request'"),
                         ("vendor/symfony/form/F.php", "'form.pre_set_data'"),
                         ("vendor/symfony/event-dispatcher/T.php", "$eventName"),
                         ("src/App/A.php", "$name")):
            os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
            open(os.path.join(root, rel), "w").write(body % arg)

        class C:
            pass
        ctx = C()
        ctx.root, ctx.locator = root, FakeLocator({})
        resolved, dynamic = events.collect_sites(ctx)
        self.assertEqual(sorted(resolved), ["kernel.request"])
        self.assertEqual([d["file"] for d in dynamic], ["src/App/A.php"])

    def test_unreadable_file_reads_empty(self):
        self.assertEqual(events.Resolver._read_file(tempfile.mkdtemp()), "")


class RecordTest(unittest.TestCase):
    class Loc:
        def locate(self, c):
            return ("v/x.php", 3) if c.startswith("Acme") else (None, None)

    class Ctx:
        pass

    def ctx(self):
        c = self.Ctx()
        c.locator = self.Loc()
        return c

    def test_free_hook_and_priority_order(self):
        sites = [{"file": "a.php", "line": 9}]
        rec = events.build_record(self.ctx(), "e.x", [], sites, {}, {})
        self.assertTrue(rec["free_hook"])
        self.assertIn("FREE HOOK", rec["text"])
        self.assertEqual((rec["file"], rec["line"]), ("a.php", 9))

    def test_listeners_sorted_and_service_joined(self):
        ls = [{"class": "Acme\\L", "name": "lo", "priority": -5}, {"class": "Acme\\L", "name": "hi", "priority": 10}]
        exact = {("Acme\\L", "e.x", "hi"): ["svc.hi"]}
        rec = events.build_record(self.ctx(), "e.x", ls, [], exact, {})
        self.assertEqual([l["method"] for l in rec["listeners"]], ["hi", "lo"])
        self.assertEqual(rec["listeners"][0]["services"], ["svc.hi"])
        self.assertFalse(rec["free_hook"])
        self.assertIn("no static dispatch site", rec["text"])

    def test_class_event_gets_location_and_short_key(self):
        rec = events.build_record(self.ctx(), "Acme\\Event\\FooEvent", [], [], {}, {})
        self.assertEqual(rec["keys"], ["FooEvent"])
        self.assertEqual(rec["file"], "v/x.php")


if __name__ == "__main__":
    unittest.main()
