import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_hooks import Base, HOOKS, run  # noqa: E402

EXE = os.path.join(HOOKS, "..", "..", "bin", "aaxis-oro")


class ReviewBase(Base):
    def setUp(self):
        super().setUp()
        self.git("init", "-q")
        self.write("README.md", "x\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")

    def git(self, *args):
        subprocess.run(["git", "-C", self.root, "-c", "user.email=t@t", "-c", "user.name=t", *args], check=True, capture_output=True)

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)

    def ns(self, value="Demo"):
        self.write(".oro-ai/local-env/env.yml", "project_namespace: %s\n" % value if value else "project: x\n")

    def check(self, *args):
        return subprocess.run([sys.executable, EXE, "review", "check", *args], cwd=self.root, capture_output=True, text=True,
                              env=dict(os.environ, HOME=self.home))


class StagedChecksTest(ReviewBase):
    def test_clean_diff_passes_with_one_line(self):
        self.write("src/Foo/A.php", "<?php\nclass A {}\n")
        self.git("add", "src")
        p = self.check()
        self.assertEqual(p.returncode, 0)
        self.assertLessEqual(len(p.stdout.splitlines()), 2)
        self.assertIn("review check: ok", p.stdout)

    def test_appbundle_path_denied(self):
        self.write("src/Aaxis/Bundle/AppBundle/X.php", "<?php\n")
        self.git("add", "-f", "src")
        p = self.check()
        self.assertEqual(p.returncode, 1)
        self.assertIn("review-no-appbundle", p.stdout)

    def test_project_namespace_use_under_aaxis_denied_and_unset_skips_with_note(self):
        self.write("src/Aaxis/Bundle/FooBundle/A.php", "<?php\nuse Demo\\Thing;\nclass A {}\n")
        self.git("add", "src")
        self.ns()
        p = self.check()
        self.assertEqual(p.returncode, 1)
        self.assertIn("A.php:2", p.stdout)
        self.ns(None)
        p = self.check()
        self.assertEqual(p.returncode, 0)
        self.assertIn("project_namespace unset", p.stdout)

    def test_direct_io_is_warning_and_temp_paths_are_ignored(self):
        self.write("src/Foo/B.php", "<?php\nfile_put_contents('/var/www/x', 'a');\nunlink(sys_get_temp_dir().'/y');\n"
                   "// %kernel.project_dir%/var\n")
        self.git("add", "src")
        p = self.check("--json")
        data = json.loads(p.stdout)
        self.assertEqual(p.returncode, 0)
        self.assertEqual([f["severity"] for f in data["findings"]], ["warn", "warn"])

    def test_unsafe_decorates_denied(self):
        self.build_index()
        self.write("src/Foo/s.yml", "services:\n    a:\n        decorates: foo.mgr\n")
        self.git("add", "src")
        p = self.check()
        self.assertEqual(p.returncode, 1)
        self.assertIn("decorates-unsafe-target", p.stdout)

    def test_range_scope_and_commit_message(self):
        self.write("src/Foo/C.php", "<?php\n")
        self.git("add", "src")
        self.git("commit", "-qm", "touch src/Aaxis/Bundle/AppBundle/ stuff")
        p = self.check("--range", "HEAD~1..HEAD")
        self.assertEqual(p.returncode, 1)
        self.assertIn("commit", p.stdout)
        self.assertEqual(self.check("--range", "nope..alsono").returncode, 3)

    def test_usage_error_exit_64(self):
        self.assertEqual(self.check("--bogus").returncode, 64)


class CitationTest(ReviewBase):
    def test_missing_entry_and_bad_line_denied(self):
        self.build_index()
        plan = os.path.join(self.root, "plan.md")
        with open(plan, "w") as fh:
            fh.write("use `aaxis-oro atlas tags oro_foo.tag` -> a.php:1\nand `aaxis-oro atlas tags no.such.tag`\n")
        p = self.check("--plan", plan, "--files", "README.md")
        self.assertEqual(p.returncode, 1)
        self.assertIn("no.such.tag", p.stdout)
        self.assertNotIn("oro_foo.tag has no hit", p.stdout)


class HookTest(ReviewBase):
    def commit_hook(self, cmd="git commit -m x"):
        return run("pretooluse_bash.py", {"session_id": "s", "tool_name": "Bash", "cwd": self.root, "tool_input": {"command": cmd}}, self.home)[1]

    def test_commit_denied_on_deny_finding_and_silent_when_clean(self):
        self.assertIsNone(self.commit_hook())
        self.write("src/Aaxis/Bundle/AppBundle/X.php", "<?php\n")
        self.git("add", "-f", "src")
        out = self.commit_hook()
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_warning_only_adds_context(self):
        self.write("src/Foo/B.php", "<?php\nunlink('/data/x');\n")
        self.git("add", "src")
        out = self.commit_hook("cd . && git commit -m x")
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])
        self.assertIn("review-direct-io", out["hookSpecificOutput"]["additionalContext"])

    def test_non_commit_commands_skip(self):
        self.write("src/Aaxis/Bundle/AppBundle/X.php", "<?php\n")
        self.git("add", "-f", "src")
        self.assertIsNone(self.commit_hook("git status"))


if __name__ == "__main__":
    unittest.main()
