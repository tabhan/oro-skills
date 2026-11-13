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
        # default-range content stays; ranges containing the highest supported version are advisory-active;
        # a pinned-old range (<8) is inactive.
        files = rel(R.active_files(SKILL, None))
        self.assertIn("references/v8/workflow.md", files)
        self.assertIn("scripts/plain.sh", files)
        self.assertNotIn("references/v7/workflow.md", files)


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
        self.assertEqual((d["run"], d["severity"]), (True, "deny"))  # default-range rule: unaffected
        d = R.check_decision(self.reg, "eight-only", None)
        self.assertEqual((d["run"], d["severity"]), (True, "warn"))
        self.assertFalse(R.check_decision(self.reg, "seven-only", None)["run"])

    def test_unregistered_check_runs_by_default(self):
        self.assertTrue(R.check_decision(self.reg, "nope", parse_version("7.0.5"))["run"])


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
        self.assertEqual(p.returncode, 4)

    def test_list_inactive(self):
        p = cli(project("7.0.5"), "--list-inactive", SKILL)
        self.assertIn("references/v8/workflow.md", p.stdout)
        self.assertNotIn("references/v7/workflow.md", p.stdout)


if __name__ == "__main__":
    unittest.main()
