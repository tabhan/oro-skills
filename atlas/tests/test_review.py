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

    def weak(self, rel, base, new):
        self.write(rel, base)
        self.git("add", ".")
        self.git("commit", "-qm", "t")
        self.write(rel, new)
        self.git("add", ".")
        data = json.loads(self.check("--json").stdout)
        return [f for f in data["findings"] if f["check"] == "review-test-weakening"], data

    def test_test_weakening_php_skip_markers(self):
        found, data = self.weak("src/A/Tests/Unit/FooTest.php", "<?php\n",
                                "<?php\n$this->markTestSkipped('x');\n#[RequiresPhpExtension('intl')]\n$this->expectNotToPerformAssertions();\n")
        self.assertEqual(len(found), 3)
        self.assertTrue(all(f["severity"] == "warn" for f in found))
        self.assertEqual(data["exit"], 0)
        self.assertIn("plan.md", found[0]["message"])

    def test_test_weakening_js_and_gherkin_skips(self):
        found, _ = self.weak("src/A/Tests/E2e/a.spec.ts", "x\n", "x\ntest.skip('a', f);\nit.only(\n")
        self.assertEqual(len(found), 2)
        found, _ = self.weak("src/A/Tests/E2e/a.feature", "Feature: x\n", "@wip\nFeature: x\n@skip\n")
        self.assertEqual(len(found), 2)

    def test_test_weakening_removed_assertions_only_when_not_replaced(self):
        base = "<?php\nself::assertSame(1, $a);\n$this->assertTrue($b);\n"
        found, _ = self.weak("src/A/Tests/Unit/BarTest.php", base, "<?php\nself::assertSame(1, $a);\n")
        self.assertEqual(len(found), 1)
        self.assertIn("1 assertion", found[0]["message"])
        found, _ = self.weak("src/A/Tests/Unit/BazTest.php", base, "<?php\nself::assertSame(2, $a);\nself::assertTrue($b);\n")
        self.assertEqual(found, [])
        found, _ = self.weak("src/A/Tests/E2e/b.steps.ts", "expect(a).toBe(1);\n", "foo();\n")
        self.assertEqual(len(found), 1)
        found, _ = self.weak("src/A/Tests/E2e/c.feature", "Feature: x\n  Then ok\n", "Feature: x\n")
        self.assertEqual(len(found), 1)

    def test_test_weakening_ignores_unrelated_diffs(self):
        found, _ = self.weak("src/A/Tests/Unit/QuxTest.php", "<?php\n", "<?php\nself::assertTrue(true);\n")
        self.assertEqual(found, [])
        found, _ = self.weak("src/A/Service.php", "<?php\nself::assertX();\n$a->markTestSkipped();\n", "<?php\n$b->markTestSkipped();\n")
        self.assertEqual(found, [])

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


class TicketBranchBase(ReviewBase):
    """Setup project on a ticket branch with one committed code change."""

    def setUp(self):
        super().setUp()
        self.git("checkout", "-qb", "feature/BUC-9")
        self.write(".oro-ai/config.json", "{}\n")
        self.write(".oro-ai/task/BUC-9/architect-gate.md", "Verdict: skipped - test\n")
        self.write(".oro-ai/task/BUC-9/STATUS.md", "x\n")
        self.write("src/Foo/Tests/E2e/x.feature", "Feature: x\n")
        self.write("src/Foo/A.php", "<?php\n")
        self.git("add", "src")
        self.git("commit", "-qm", "code")

    def sha(self, ref="HEAD"):
        return subprocess.run(["git", "-C", self.root, "rev-parse", ref], capture_output=True, text=True).stdout.strip()

    def review(self, text):
        self.write(".oro-ai/task/BUC-9/review.md", text)

    def task_check(self, env=None):
        return subprocess.run([sys.executable, EXE, "task", "check"], cwd=self.root, capture_output=True, text=True,
                              env=dict(os.environ, HOME=self.home, **(env or {})))

    def push(self, cmd="git push -u origin HEAD", env=None):
        return run("pretooluse_bash.py", {"session_id": "s", "tool_name": "Bash", "cwd": self.root, "tool_input": {"command": cmd}},
                   self.home, env)[1]


class SupplementaryReviewTest(TicketBranchBase):
    """review.md verdict + Range staleness, `task check` and the `git push` gate."""

    def test_verdict_parsing_and_staleness(self):
        from atlas import task
        head, base = self.sha(), self.sha("HEAD~1")
        cases = (("", "missing"), ("Verdict: changes-requested\nRange: %s..%s\n" % (base, head), "changes-requested"),
                 ("Verdict: approved\n", "stale"), ("Verdict: approved\nRange: %s..%s\n" % (base, base), "stale"),
                 ("Verdict: approved\nRange: %s..%s\n" % (base[:12], head[:12]), "approved"),
                 ("Verdict: skipped\n", "no-verdict"), ("Verdict: skipped - docs only\n", "skipped"))
        for text, state in cases:
            self.review(text)
            self.assertEqual(task.review_state(self.root, "BUC-9")[0], state, text)

    def test_committing_task_files_after_review_keeps_it_fresh_but_code_does_not(self):
        from atlas import task
        self.review("Verdict: approved\nRange: %s..%s\n" % (self.sha("HEAD~1"), self.sha()))
        self.git("add", "-f", ".oro-ai/task")
        self.git("commit", "-qm", "review evidence")
        self.assertEqual(task.review_state(self.root, "BUC-9")[0], "approved")
        self.write("src/Foo/B.php", "<?php\n")
        self.git("add", "src")
        self.git("commit", "-qm", "more")
        self.assertEqual(task.review_state(self.root, "BUC-9")[0], "stale")

    def test_task_check_requires_fresh_review(self):
        p = self.task_check()
        self.assertEqual(p.returncode, 1)
        self.assertIn("review: missing", p.stdout)
        self.review("Verdict: approved\nRange: %s..%s\n" % (self.sha("HEAD~1"), self.sha()))
        self.assertEqual(self.task_check().returncode, 0, self.task_check().stdout)

    def test_task_check_warns_on_missing_or_empty_root_cause_without_failing(self):
        from atlas import task
        self.review("Verdict: skipped - test\n")
        self.assertNotIn("Root cause", self.task_check().stdout)  # no plan.md: nothing to check
        task.init(self.root, "BUC-9")  # stub: heading + guidance prose only counts as empty
        for text, warned in ((None, "an empty"), ("# p\n\n## Tests\n\nx\n", "no"),
                             ("## Root cause\n\n## Tests\nx\n", "an empty"),
                             ("## Root cause\n\nn/a - feature\n", None),
                             ("## Root Cause\nCI image lacks ext-intl (log l.40); layer: environment\n## Tests\n", None)):
            if text is not None:
                self.write(".oro-ai/task/BUC-9/plan.md", text)
            p = self.task_check()
            self.assertEqual(p.returncode, 0, p.stdout)
            if warned:
                self.assertIn("has %s '## Root cause' section" % warned, p.stdout)
            else:
                self.assertNotIn("Root cause' section", p.stdout)

    def test_push_denied_without_review_allowed_with_fresh_or_skipped(self):
        out = self.push()
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("review-ticket-push", out["hookSpecificOutput"]["permissionDecisionReason"])
        self.review("Verdict: skipped - docs only\n")
        self.assertIsNone(self.push("cd . && git push"))
        self.review("Verdict: approved\nRange: %s..%s\n" % (self.sha("HEAD~1"), self.sha()))
        self.assertIsNone(self.push())
        self.assertIsNone(self.push("git status"))

    def test_in_progress_is_not_approved_for_push_or_task_check(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.review("Verdict: in-progress\nRange: %s..%s\nStarted: %s\n" % (self.sha("HEAD~1"), self.sha(), now))
        out = self.push()
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("review in progress", out["hookSpecificOutput"]["permissionDecisionReason"])
        p = self.task_check()
        self.assertEqual(p.returncode, 1)
        self.assertIn("review in progress", p.stdout)

    def test_push_override_warns_and_non_setup_or_non_ticket_is_noop(self):
        out = self.push(env={"ORO_ATLAS_ENFORCE": "0"})
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])
        self.assertIn("review-ticket-push", out["hookSpecificOutput"]["additionalContext"])
        os.remove(os.path.join(self.root, ".oro-ai", "config.json"))
        self.assertIsNone(self.push())
        self.write(".oro-ai/config.json", "{}\n")
        self.git("checkout", "-qb", "chore/cleanup")
        self.assertIsNone(self.push())


class StopReviewGateTest(TicketBranchBase):
    """stop.py blocks the main session's Stop until a fresh review covers finished (committed, clean) ticket code."""

    def stop(self, env=None, **extra):
        payload = dict({"session_id": "stop-s", "hook_event_name": "Stop", "cwd": self.root, "stop_hook_active": False}, **extra)
        return run("stop.py", payload, self.home, env)

    def test_blocks_finished_code_without_review(self):
        rc, out = self.stop()
        self.assertEqual(rc, 0)
        self.assertEqual(out["decision"], "block")
        self.assertIn("/aaxis-oro:review", out["reason"])
        self.assertIn("Verdict: skipped - <reason>", out["reason"])

    def test_fresh_approved_or_skipped_review_allows_stop(self):
        self.review("Verdict: approved\nRange: %s..%s\n" % (self.sha("HEAD~1"), self.sha()))
        self.assertIsNone(self.stop()[1])
        self.review("Verdict: skipped - docs only\n")
        self.assertIsNone(self.stop()[1])

    def test_stale_review_blocks_again(self):
        self.review("Verdict: approved\nRange: %s..%s\n" % (self.sha("HEAD~1"), self.sha()))
        self.write("src/Foo/B.php", "<?php\n")
        self.git("add", "src")
        self.git("commit", "-qm", "more")
        self.assertIn("stale", self.stop()[1]["reason"])

    def test_dirty_code_tree_is_mid_work_but_task_files_are_not(self):
        self.write("src/Foo/A.php", "<?php // wip\n")
        self.assertIsNone(self.stop()[1])
        self.git("checkout", "--", "src/Foo/A.php")
        self.write("src/Foo/New.php", "<?php\n")
        self.assertIsNone(self.stop()[1], "untracked code is mid-work too")
        os.remove(os.path.join(self.root, "src", "Foo", "New.php"))
        self.write(".oro-ai/task/BUC-9/STATUS.md", "changed\n")
        self.assertEqual(self.stop()[1]["decision"], "block")

    def test_no_committed_code_on_branch_is_noop(self):
        self.git("checkout", "-qb", "feature/BUC-10", "HEAD~1")
        self.assertIsNone(self.stop()[1])

    def test_changes_requested_on_head_asks_for_fixes(self):
        self.review("Verdict: changes-requested\nRange: %s..%s\n" % (self.sha("HEAD~1"), self.sha()))
        out = self.stop()[1]
        self.assertEqual(out["decision"], "block")
        self.assertIn("must-fix", out["reason"])
        self.review("Verdict: changes-requested\nRange: %s..%s\n" % (self.sha("HEAD~1"), self.sha("HEAD~1")))
        self.assertNotIn("must-fix", self.stop()[1]["reason"])

    def marker(self, head=None, started=None):
        from datetime import datetime, timezone
        started = started or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.review("Verdict: in-progress\nRange: %s..%s\nStarted: %s\n" % (self.sha("HEAD~1"), head or self.sha(), started))
        return started

    def test_fresh_in_progress_marker_does_not_block(self):
        started = self.marker()
        out = self.stop()[1]
        self.assertNotIn("decision", out)
        self.assertIn("review in progress since %s" % started, out["systemMessage"])

    def test_stale_in_progress_marker_blocks(self):
        self.marker(started="2020-01-01T00:00:00Z")
        out = self.stop()[1]
        self.assertEqual(out["decision"], "block")
        self.assertIn("stale in-progress marker", out["reason"])
        self.marker(head=self.sha("HEAD~1"))
        self.assertIn("Range head is not HEAD", self.stop()[1]["reason"])

    def test_loop_guard_allows_with_warning(self):
        out = self.stop(stop_hook_active=True)[1]
        self.assertNotIn("decision", out)
        self.assertIn("already asked once", out["systemMessage"])

    def test_enforcement_off_warns_only(self):
        out = self.stop(env={"ORO_ATLAS_ENFORCE": "0"})[1]
        self.assertNotIn("decision", out)
        self.assertIn("review-ticket-stop", out["systemMessage"])

    def test_subagent_stop_is_exempt(self):
        self.assertIsNone(self.stop(hook_event_name="SubagentStop", agent_id="a1")[1])
        self.assertIsNone(self.stop(agent_id="a1")[1])

    def test_non_setup_non_ticket_and_non_git_are_noop(self):
        os.remove(os.path.join(self.root, ".oro-ai", "config.json"))
        self.assertIsNone(self.stop()[1])
        self.write(".oro-ai/config.json", "{}\n")
        self.git("checkout", "-qb", "chore/cleanup")
        self.assertIsNone(self.stop()[1])
        import shutil
        shutil.rmtree(os.path.join(self.root, ".git"))
        self.assertIsNone(self.stop()[1])

    def test_exceptions_and_bad_input_allow_stop(self):
        p = subprocess.run([sys.executable, os.path.join(HOOKS, "stop.py")], input="not json", capture_output=True, text=True,
                           env=dict(os.environ, HOME=self.home))
        self.assertEqual((p.returncode, p.stdout), (0, ""))
        self.assertIsNone(self.stop(cwd=12345)[1])
