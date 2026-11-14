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

    def test_appbundle_only_in_commit_message_not_rest_of_command(self):
        self.write("src/Foo/A.php", "<?php\nclass A {}\n")
        self.git("add", "src")
        self.assertIsNone(self.commit_hook("ls src/Aaxis/Bundle/AppBundle/ && git commit -m ok"))
        self.assertIsNone(self.commit_hook("git commit -m ok && echo AppBundle/"))
        out = self.commit_hook("git commit -m 'touch AppBundle/ stuff'")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.write("msg.txt", "touch AppBundle/ stuff\n")
        out = self.commit_hook("git commit -F msg.txt")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_large_diff_skips_checks_with_one_line(self):
        for i in range(301):
            self.write("src/Foo/F%d.php" % i, "<?php\n")
        self.write("src/Aaxis/Bundle/AppBundle/X.php", "<?php\n")
        self.git("add", "-f", "src")
        out = self.commit_hook()
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])
        self.assertIn("review check skipped (302 files); run: aaxis-oro review check --staged", text)
        self.assertEqual(self.check().returncode, 1)

    def test_log_dir_is_self_ignoring_when_oro_ai_is_tracked(self):
        self.write(".oro-ai/task/T-1/plan.md", "plan\n")
        self.write("src/Foo/B.php", "<?php\n" + "unlink('/data/x');\n" * 20)
        self.git("add", "-A")
        self.git("commit", "-qm", "track")
        self.write("src/Foo/C.php", "\n".join("<?php unlink('/x%d');" % i for i in range(30)))
        self.git("add", "src")
        p = self.check()
        self.assertTrue(os.path.isdir(os.path.join(self.root, ".oro-ai", "review", "logs")), p.stdout)
        self.assertEqual(open(os.path.join(self.root, ".oro-ai", "review", ".gitignore")).read(), "*\n")
        status = subprocess.run(["git", "-C", self.root, "status", "--porcelain", "--", ".oro-ai/review"], capture_output=True, text=True).stdout
        self.assertEqual(status, "")

    def test_non_commit_commands_skip(self):
        self.write("src/Aaxis/Bundle/AppBundle/X.php", "<?php\n")
        self.git("add", "-f", "src")
        self.assertIsNone(self.commit_hook("git status"))


if __name__ == "__main__":
    unittest.main()


class TicketProcessTest(ReviewBase):
    def setUp(self):
        super().setUp()
        self.git("checkout", "-qb", "bugfix/BUC-7")
        self.write(".oro-ai/config.json", "{}\n")
        self.write("src/Foo/Resources/config/services.yml", "services: {}\n")
        self.git("add", "src")

    def gate(self, text):
        self.write(".oro-ai/task/BUC-7/architect-gate.md", text)

    def test_extension_change_without_gate_denied(self):
        p = self.check()
        self.assertEqual(p.returncode, 1)
        self.assertIn("review-ticket-gate", p.stdout)

    def test_rejected_or_bare_skip_denied_approved_and_reasoned_skip_pass(self):
        for text, code in (("Verdict: rejected\n", 1), ("Verdict: skipped\n", 1), ("**Verdict:** approved\n", 0),
                           ("Verdict: skipped - one-line yaml rename\n", 0), ("PASS\n\nGate: ...\n", 0), ("REJECT\n", 1),
                           ("notes only\n", 1)):
            self.gate(text)
            self.assertEqual(self.check().returncode, code, text)

    def test_evidence_warnings_and_task_init_check(self):
        self.gate("Verdict: approved\n")
        p = self.check()
        self.assertEqual(p.returncode, 0)
        self.assertIn("STATUS.md", p.stdout)
        self.assertIn("no e2e", p.stdout)
        run_task = lambda *a: subprocess.run([sys.executable, EXE, "task", *a], cwd=self.root, capture_output=True, text=True)
        self.assertIn("created STATUS.md, plan.md", run_task("init").stdout)
        self.assertIn("exists", run_task("init").stdout)
        self.write("src/Foo/Tests/E2e/x.feature", "Feature: x\n")
        self.git("add", "src")
        self.assertEqual(run_task("check").returncode, 0)
        self.assertNotIn("review-ticket-evidence", self.check().stdout)

    def test_non_setup_project_and_non_ticket_branch_unaffected(self):
        os.remove(os.path.join(self.root, ".oro-ai", "config.json"))
        self.assertEqual(self.check().returncode, 0)
        self.write(".oro-ai/config.json", "{}\n")
        self.git("checkout", "-qb", "chore/cleanup")
        self.assertEqual(self.check().returncode, 0)

    def test_human_override_downgrades(self):
        p = subprocess.run([sys.executable, EXE, "review", "check"], cwd=self.root, capture_output=True, text=True,
                           env=dict(os.environ, HOME=self.home, ORO_ATLAS_ENFORCE="0"))
        self.assertEqual(p.returncode, 0)
        self.assertIn("review-ticket-gate", p.stdout)
