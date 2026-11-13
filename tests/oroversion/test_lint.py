import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CLI = os.path.join(ROOT, "bin", "aaxis-oro")
LINT = os.path.join(HERE, "fixtures", "lint")


def run(*args):
    return subprocess.run([sys.executable, CLI, "dev", "lint", *args], capture_output=True, text=True)


def case(name):
    return run("--root", os.path.join(LINT, name))


class LintFixtureTest(unittest.TestCase):
    def assertViolation(self, name, needle):
        r = case(name)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(needle, r.stdout)

    def test_adjoining_variants_pass(self):
        r = case("ok")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_overlap(self):
        self.assertViolation("overlap", "overlaps")

    def test_gap(self):
        self.assertViolation("gap", "gap between 7.0.5 and 7.1.0")

    def test_unparsable_range(self):
        self.assertViolation("unparsable", "unparsable oro range")

    def test_variant_without_topic(self):
        self.assertViolation("missing_topic", "no topic")

    def test_unclosed_section(self):
        self.assertViolation("unclosed", "unclosed oro section")

    def test_nested_section(self):
        self.assertViolation("nested", "nested oro section")

    def test_malformed_marker(self):
        self.assertViolation("malformed", "malformed oro marker")

    def test_description_version(self):
        self.assertViolation("desc", "version-neutral")

    def test_registry_gap(self):
        self.assertViolation("registry", "gap between 8.0.0 and 8.1.0")

    def test_prerelease_lower_bound_overlaps_plain_upper_bound(self):
        self.assertViolation("prerelease", "overlaps")

    def test_lone_upper_bound_warns_without_failing(self):
        r = case("lone_upper")
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertIn("disappears from 7.0.5 with no successor", r.stderr)

    def test_paths_are_repo_relative(self):
        self.assertTrue(case("gap").stdout.startswith("a.md:"))

    def test_bad_path_is_usage_error(self):
        self.assertEqual(run("/no/such/path").returncode, 64)


class RepoLintTest(unittest.TestCase):
    def test_repo_is_clean(self):
        r = run()
        self.assertEqual((r.returncode, r.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
