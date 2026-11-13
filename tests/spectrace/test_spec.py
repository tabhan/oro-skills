import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CLI = os.path.join(ROOT, "bin", "aaxis-oro")
FIX = os.path.join(HERE, "fixtures")

PW = {"suites": [{"specs": [
    {"title": "add", "ok": True, "tags": ["spec:CART:AC-1"], "tests": [{"status": "expected"}]},
    {"title": "extra", "ok": False, "tags": ["@spec:CART:AC-1"], "tests": [{"status": "unexpected"}]},
], "suites": []}]}
JUNIT = """<testsuites><testsuite><testcase class="App\\Tests\\Functional\\TotalsTest" name="testSum" file="/s/Tests/Functional/TotalsTest.php"/></testsuite></testsuites>"""
LIST = """<tests><testCaseClass name="App\\Tests\\Functional\\TotalsTest"><testCaseMethod id="App\\Tests\\Functional\\TotalsTest::testSum#0" name="testSum" groups="default,spec:CART:AC-2"/></testCaseClass></tests>"""


def spec(*args):
    return subprocess.run([sys.executable, CLI, "spec", *args], capture_output=True, text=True)


class CoverageTest(unittest.TestCase):
    def run_case(self, name, *extra):
        return spec("coverage", "--root", os.path.join(FIX, name), *extra)

    def test_full_fixture_passes(self):
        r = self.run_case("ok")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2 AC, 0 problem", r.stdout)

    def test_unit_only_carrier_fails(self):
        r = self.run_case("unit")
        self.assertEqual(r.returncode, 1)
        self.assertIn("CART:AC-2 unit-only", r.stdout)

    def test_retired_tag_fails(self):
        r = self.run_case("retired")
        self.assertEqual(r.returncode, 1)
        self.assertIn("cites a retired AC", r.stdout)

    def test_orphan_tag_and_uncovered(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "src", "Tests", "E2e"))
            os.makedirs(os.path.join(d, "spec"))
            with open(os.path.join(d, "src", "Tests", "E2e", "a.feature"), "w") as fh:
                fh.write("@spec:CART:AC-9\n")
            with open(os.path.join(d, "spec", "spec-x.md"), "w") as fh:
                fh.write("---\nid: CART\n---\n### AC-1: a\nGiven a When b Then c\n")
            r = spec("coverage", "--root", d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("orphan tag spec:CART:AC-9", r.stdout)
        self.assertIn("CART:AC-1 uncovered", r.stdout)

    def test_spec_without_id_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "spec"))
            with open(os.path.join(d, "spec", "spec-official.md"), "w") as fh:
                fh.write("---\ntitle: Official\n---\n### AC-1: x\n")
            self.assertEqual(spec("coverage", "--root", d).returncode, 0)


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def w(self, name, content):
        p = os.path.join(self.tmp.name, name)
        with open(p, "w") as fh:
            fh.write(content if isinstance(content, str) else json.dumps(content))
        return p

    def report(self, pw, *extra):
        return spec("report", "--root", os.path.join(FIX, "ok"), "--e2e", self.w("r.json", pw), "--sha", "abc123",
                    "--junit", self.w("j.xml", JUNIT), "--groups-xml", self.w("l.xml", LIST), *extra)

    def test_failing_carrier_fails_ac(self):
        r = self.report(PW)
        self.assertEqual(r.returncode, 1)
        self.assertIn("| CART:AC-1 | Add item | failed |", r.stdout)
        self.assertIn("| CART:AC-2 | Totals | verified |", r.stdout)
        self.assertIn("abc123", r.stdout)

    def test_all_pass_verified(self):
        pw = {"suites": [{"specs": [PW["suites"][0]["specs"][0]], "suites": []}]}
        out = os.path.join(self.tmp.name, "o.md")
        r = self.report(pw, "--out", out)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("2/2 verified", r.stdout)
        self.assertIn("abc123", open(out).read())

    def test_not_run_is_gap(self):
        r = spec("report", "--root", os.path.join(FIX, "ok"), "--e2e", self.w("r.json", {"suites": []}), "--ids", "CART")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not run", r.stdout)


if __name__ == "__main__":
    unittest.main()
