import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from oroversion import parse_version, resolve as R  # noqa: E402

CLI = os.path.join(ROOT, "bin", "oro-applies")
SKILL = os.path.join(HERE, "fixtures", "skill")
REGISTRY = os.path.join(HERE, "fixtures", "checks.yml")


def project(version):
    d = tempfile.mkdtemp()
    if version:
        with open(os.path.join(d, "composer.lock"), "w") as fh:
            json.dump({"packages": [{"name": "oro/platform", "version": version}]}, fh)
    return d


def rel(paths):
    return sorted(os.path.relpath(p, SKILL) for p in paths)


def cli(proj, *args):
    return subprocess.run([sys.executable, CLI, "--project", proj, *args], capture_output=True, text=True)


class ActiveSetTest(unittest.TestCase):
    def test_705_lists_v7_only(self):
        files = rel(R.active_files(SKILL, parse_version("7.0.5")))
        self.assertIn("references/v7/workflow.md", files)
        self.assertNotIn("references/v8/workflow.md", files)
        self.assertNotIn("references/v8/implicit.md", files)
        self.assertNotIn("scripts/new.sh", files)
        self.assertIn("scripts/plain.sh", files)

    def test_80_lists_v8_only(self):
        files = rel(R.active_files(SKILL, parse_version("8.0.0")))
        self.assertIn("references/v8/workflow.md", files)
        self.assertIn("references/v8/implicit.md", files)
        self.assertNotIn("references/v7/workflow.md", files)
        self.assertIn("scripts/new.sh", files)

    def test_sections_and_rows_become_skip_spans(self):
        files = R.active_files(SKILL, parse_version("7.0.5"))
        self.assertEqual(files[os.path.join(SKILL, "references", "sectioned.md")], [(3, 5)])
        self.assertEqual(files[os.path.join(SKILL, "references", "table.md")], [(5, 5)])
        files = R.active_files(SKILL, parse_version("8.0.0"))
        self.assertEqual(files[os.path.join(SKILL, "references", "table.md")], [])

    def test_unknown_policy(self):
        # only version-neutral content (no upper bound, lower bound <= 7.0.0) is active; v7/ and v8/ are both inactive.
        files = rel(R.active_files(SKILL, None))
        self.assertNotIn("references/v8/workflow.md", files)
        self.assertNotIn("references/v7/workflow.md", files)
        self.assertNotIn("scripts/new.sh", files)
        self.assertIn("scripts/plain.sh", files)

    def test_unknown_neutrality(self):
        for rng, active in ((">=7.0.0", True), ("^7.0 or >=8.0", False), (">=7.0.0 or >=9", True), (">=7.0.0 <8", False), ("<8", False),
                            (">=8.0.0", False), ("==7.0.5", False), ("^7.0", False), (">=7.0.5", False), (">=6.0", True)):
            self.assertEqual(R.status(rng, None) == R.ACTIVE, active, rng)


class CheckGateTest(unittest.TestCase):
    def setUp(self):
        self.reg = R.load_registry(REGISTRY)

    def test_out_of_range_check_not_run(self):
        d = R.check_decision(self.reg, "eight-only", parse_version("7.0.5"))
        self.assertFalse(d["run"])
        self.assertIn("skipped", d["reason"])
        self.assertTrue(R.check_decision(self.reg, "seven-only", parse_version("7.0.5"))["run"])

    def test_unknown_downgrades_deny(self):
        d = R.check_decision(self.reg, "always-deny", None)
        self.assertEqual((d["run"], d["severity"]), (True, "warn"))
        self.assertFalse(R.check_decision(self.reg, "eight-only", None)["run"])
        self.assertFalse(R.check_decision(self.reg, "seven-only", None)["run"])

    def test_unknown_downgrades_every_deny_annotated_or_not(self):
        reg = R.load_registry(REGISTRY)
        reg["bare"] = {"id": "bare", "severity": "deny"}
        for cid in ("bare", "always-deny"):
            d = R.check_decision(reg, cid, None)
            self.assertEqual((d["run"], d["severity"]), (True, "warn"), cid)
        self.assertEqual(R.check_decision(reg, "unregistered", None)["severity"], "warn")
        self.assertEqual(R.check_decision(reg, "always-deny", parse_version("7.0.5"))["severity"], "deny")

    def test_unregistered_check_runs_by_default(self):
        self.assertTrue(R.check_decision(self.reg, "nope", parse_version("7.0.5"))["run"])


class TableAndMarkerTest(unittest.TestCase):
    def write(self, text):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "t.md")
        with open(path, "w") as fh:
            fh.write(text)
        return path

    def test_or_in_table_rows(self):
        path = self.write("| Rule | Oro |\n|---|---|\n| a | ^6.1 or ^8.0 |\n| b | ^6.1 \\|\\| ^8.0 |\n| c | >=7.0 |\n")
        for v, expect in (("7.0.5", ["inactive", "inactive", "active"]), ("8.0.0", ["active", "active", "active"])):
            rows = [s for u, s in R.resolve(path, parse_version(v)) if u.kind == "row"]
            self.assertEqual(rows, expect, v)

    def test_marker_warnings(self):
        cases = {
            "unclosed": ("a\n<!-- oro: \">=8.0\" -->\nx\n", "unclosed"),
            "nested": ("<!-- oro: \">=8.0\" -->\n<!-- oro: \">=9.0\" -->\nx\n<!-- /oro -->\n", "nested"),
            "stray": ("x\n<!-- /oro -->\n", "without an opening"),
        }
        for name, (text, needle) in cases.items():
            w = []
            R.resolve(self.write(text), parse_version("7.0.5"), warnings=w)
            self.assertTrue(any(needle in x for x in w), name)
        w = []
        R.resolve(self.write("<!-- oro: \">=8.0\" -->\nx\n<!-- /oro -->\n"), parse_version("7.0.5"), warnings=w)
        self.assertEqual(w, [])

    def test_cli_prints_marker_warning(self):
        p = cli(project("7.0.5"), self.write("<!-- oro: \">=8.0\" -->\nx\n"))
        self.assertIn("unclosed", p.stderr)


class CliTest(unittest.TestCase):
    def test_list_active_705(self):
        p = cli(project("7.0.5"), "--list-active", SKILL)
        self.assertEqual(p.returncode, 0)
        self.assertIn("references/v7/workflow.md", p.stdout)
        self.assertNotIn("references/v8/workflow.md", p.stdout)

    def test_list_active_80(self):
        p = cli(project("8.0.0"), "--list-active", SKILL)
        self.assertIn("references/v8/workflow.md", p.stdout)
        self.assertNotIn("references/v7/workflow.md", p.stdout)

    def test_unknown_exit_4_with_advisory(self):
        p = cli(project(None), "--list-active", SKILL)
        self.assertEqual(p.returncode, 4)
        self.assertIn("advisory", p.stderr)
        self.assertIn("scripts/plain.sh", p.stdout)
        self.assertNotIn("v8/workflow.md", p.stdout)
        self.assertNotIn("v7/workflow.md", p.stdout)
        p = cli(project(None), "--list-inactive", SKILL)
        self.assertIn("v8/workflow.md", p.stdout)
        self.assertIn("v7/workflow.md", p.stdout)
        self.assertEqual(cli(project(None), os.path.join(SKILL, "SKILL.md")).returncode, 4)

    def test_applies_exit_codes(self):
        proj = project("7.0.5")
        self.assertEqual(cli(proj, os.path.join(SKILL, "SKILL.md")).returncode, 0)
        p = cli(proj, os.path.join(SKILL, "references", "v8", "workflow.md"))
        self.assertEqual(p.returncode, 1)
        self.assertIn("inactive", p.stdout)
        self.assertEqual(cli(proj).returncode, 64)
        self.assertEqual(cli(proj, "no-such-thing").returncode, 64)

    def test_topic_lookup(self):
        p = cli(project("7.0.5"), "--root", SKILL, "wf")
        self.assertEqual(p.returncode, 1)
        self.assertIn("v8/workflow.md", p.stdout)
        self.assertEqual(cli(project("8.0.0"), "--root", SKILL, "sec").returncode, 0)

    def test_check_mode(self):
        p = cli(project("7.0.5"), "--check", "eight-only", "--registry", REGISTRY)
        self.assertEqual((p.returncode, p.stdout.split()[0]), (1, "skip"))
        p = cli(project(None), "--check", "always-deny", "--registry", REGISTRY)
        self.assertEqual((p.returncode, p.stdout.split()[0]), (4, "warn"))
        p = cli(project(None), "--check", "eight-only", "--registry", REGISTRY)
        self.assertEqual((p.returncode, p.stdout.split()[0]), (4, "skip"))

    def test_list_inactive(self):
        p = cli(project("7.0.5"), "--list-inactive", SKILL)
        self.assertIn("references/v8/workflow.md", p.stdout)
        self.assertNotIn("references/v7/workflow.md", p.stdout)


if __name__ == "__main__":
    unittest.main()
