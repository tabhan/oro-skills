import json
import os
import stat
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_hooks import Base, HOOKS, run  # noqa: E402

OFF = {"ORO_ATLAS_ENFORCE": "0"}


class EnforceBase(Base):
    def setUp(self):
        super().setUp()
        self.ext = os.path.join(self.root, "src", "Foo", "Resources", "config", "services.yml")
        os.makedirs(os.path.dirname(self.ext))
        self.build_index()

    def fake_build(self, exit_code):
        path = os.path.join(self.tmp.name, "fake-build.py")
        with open(path, "w") as fh:
            fh.write("import sys\nprint('x')\nsys.exit(%d)\n" % exit_code)
        return {"ORO_ATLAS_BUILD_BIN": path}

    def edit_ext(self, extra_env=None, sid="s1", text="services:\n  a: ~\n"):
        ti = {"file_path": self.ext, "new_string": text, "old_string": ""}
        return run("pretooluse_edit.py", {"session_id": sid, "tool_name": "Edit", "tool_input": ti}, self.home, extra_env)[1]

    def bash(self, cmd, sid="s1", script="posttooluse_bash.py", extra_env=None):
        return run(script, {"session_id": sid, "tool_name": "Bash", "cwd": self.root, "tool_input": {"command": cmd}}, self.home, extra_env)[1]

    def decision(self, out):
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    def make_stale(self):
        with open(os.path.join(self.root, "composer.lock"), "w") as fh:
            json.dump({"packages": [{"name": "oro/platform", "version": "7.0.6"}]}, fh)


class QueryFirstTest(EnforceBase):
    def test_denied_until_atlas_query_then_allowed(self):
        self.assertEqual(self.decision(self.edit_ext()), "deny")
        self.bash("atlas status")
        self.assertEqual(self.decision(self.edit_ext()), "deny")
        self.bash("/x/oro-atlas/bin/atlas --project /p service foo.bar | head")
        self.assertIsNone(self.decision(self.edit_ext()))

    def test_marker_is_per_session_and_shared_by_subagents_using_the_parent_id(self):
        self.bash("atlas event kernel.request", sid="parent")
        self.assertIsNone(self.decision(self.edit_ext(sid="parent")))
        self.assertEqual(self.decision(self.edit_ext(sid="other")), "deny")

    def test_non_extension_file_is_never_denied(self):
        ti = {"file_path": self.file, "new_string": "a: 1", "old_string": ""}
        _, out = run("pretooluse_edit.py", {"session_id": "s1", "tool_name": "Edit", "tool_input": ti}, self.home)
        self.assertNotEqual(self.decision(out), "deny")

    def test_stale_index_denies_even_after_query_and_names_build(self):
        self.bash("atlas service x")
        self.make_stale()
        out = self.edit_ext()
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("atlas-build", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_unknown_version_downgrades_deny_to_warn(self):
        os.remove(os.path.join(self.root, "composer.lock"))
        with open(os.path.join(self.root, "composer.lock"), "w") as fh:
            json.dump({"packages": []}, fh)
        out = self.edit_ext()
        self.assertNotEqual(self.decision(out), "deny")

    def test_non_oro_dir_is_silent(self):
        ti = {"file_path": os.path.join(self.tmp.name, "x", "Resources", "config", "services.yml"), "new_string": "a", "old_string": ""}
        _, out = run("pretooluse_edit.py", {"session_id": "s1", "tool_name": "Edit", "tool_input": ti}, self.home)
        self.assertIsNone(out)

    def test_listener_and_extension_names_are_extension_files(self):
        for name in ("FooListener.php", "BarSubscriber.php", "FooExtension.php", "entity_extend.yml", "XInterceptor.php"):
            ti = {"file_path": os.path.join(self.root, "src", "Foo", name), "new_string": "x", "old_string": ""}
            _, out = run("pretooluse_edit.py", {"session_id": "n", "tool_name": "Edit", "tool_input": ti}, self.home)
            self.assertEqual(self.decision(out), "deny", name)


class EscapeHatchTest(EnforceBase):
    def test_off_allows_logs_and_stop_reminds_once(self):
        out = self.edit_ext(OFF)
        self.assertNotEqual(self.decision(out), "deny")
        self.assertIn("ORO_ATLAS_ENFORCE=0", out["hookSpecificOutput"]["additionalContext"])
        self.assertIn("bypass", [r["verdict"] for r in self.log()])
        stop = run("stop.py", {"session_id": "s1"}, self.home)[1]
        self.assertIn("1 edit", stop["systemMessage"])
        self.assertIsNone(run("stop.py", {"session_id": "s1"}, self.home)[1])
        self.edit_ext(OFF)
        self.assertIn("2 edit", run("stop.py", {"session_id": "s1"}, self.home)[1]["systemMessage"])

    def test_off_still_denied_when_set_to_other_value(self):
        self.assertEqual(self.decision(self.edit_ext({"ORO_ATLAS_ENFORCE": "1"})), "deny")

    def test_no_stop_output_without_bypass(self):
        self.assertIsNone(run("stop.py", {"session_id": "clean"}, self.home)[1])

    def test_bash_cannot_set_the_switch(self):
        for cmd in ("export ORO_ATLAS_ENFORCE=0", "ORO_ATLAS_ENFORCE=0 claude", "env ORO_ATLAS_ENFORCE=0 x",
                    "echo 'ORO_ATLAS_ENFORCE=0' >> ~/.zshrc", "declare -x ORO_ATLAS_ENFORCE=0", "echo ${ORO_ATLAS_ENFORCE:=0}"):
            out = self.bash(cmd, script="pretooluse_bash.py")
            self.assertEqual(self.decision(out), "deny", cmd)

    def test_bash_reading_the_switch_or_other_commands_pass(self):
        for cmd in ("echo $ORO_ATLAS_ENFORCE", "printf %s \"${ORO_ATLAS_ENFORCE}\"", "ls -la", "atlas service foo"):
            self.assertIsNone(self.bash(cmd, script="pretooluse_bash.py"), cmd)

    def test_settings_and_rc_writes_are_denied_but_source_files_are_not(self):
        for path in (os.path.join(self.home, ".claude", "settings.json"), os.path.join(self.home, ".zshrc"), os.path.join(self.root, ".env.local")):
            ti = {"file_path": path, "content": '{"env": {"ORO_ATLAS_ENFORCE": "0"}}'}
            _, out = run("pretooluse_edit.py", {"session_id": "w", "tool_name": "Write", "tool_input": ti}, self.home)
            self.assertEqual(self.decision(out), "deny", path)
        ti = {"file_path": os.path.join(self.root, "docs", "notes.md"), "content": "ORO_ATLAS_ENFORCE"}
        self.assertIsNone(run("pretooluse_edit.py", {"session_id": "w", "tool_name": "Write", "tool_input": ti}, self.home)[1])

    def test_off_downgrades_decorates_deny_too(self):
        ti = {"file_path": self.ext, "new_string": "decorates: foo.mgr", "old_string": ""}
        _, out = run("pretooluse_edit.py", {"session_id": "d", "tool_name": "Edit", "tool_input": ti}, self.home, OFF)
        self.assertNotEqual(self.decision(out), "deny")
        _, out = run("pretooluse_edit.py", {"session_id": "d", "tool_name": "Edit", "tool_input": ti}, self.home)
        self.assertEqual(self.decision(out), "deny")


class ComposerBuildTest(EnforceBase):
    def test_composer_update_rebuilds_when_stale(self):
        self.make_stale()
        out = self.bash("composer update oro/platform", extra_env=self.fake_build(0))
        self.assertIn("done", out["hookSpecificOutput"]["additionalContext"])

    def test_failed_build_is_recorded_and_named_by_the_deny(self):
        self.make_stale()
        out = self.bash("composer install", extra_env=self.fake_build(1))
        self.assertIn("FAILED", out["hookSpecificOutput"]["additionalContext"])
        self.bash("atlas service x")
        self.assertIn("session-build.log", self.edit_ext()["hookSpecificOutput"]["permissionDecisionReason"])

    def test_composer_with_fresh_index_is_silent(self):
        self.assertIsNone(self.bash("composer install", extra_env=self.fake_build(1)))


class SessionStartTest(EnforceBase):
    def start(self, extra_env=None, cwd=None, sid="ss"):
        return run("sessionstart_atlas.py", {"session_id": sid, "cwd": cwd or self.root, "source": "startup"}, self.home, extra_env)[1]

    def test_fresh_index_one_short_context(self):
        out = self.start()
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Oro 7.0.5", ctx)
        self.assertIn("index fresh", ctx)
        self.assertLessEqual(len(ctx.splitlines()), 3)
        self.assertNotIn("systemMessage", out)

    def test_stale_index_is_rebuilt_in_foreground(self):
        self.make_stale()
        ctx = self.start(self.fake_build(0))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("rebuilt in", ctx)

    def test_failed_build_is_reported_and_kept_for_the_edit_deny(self):
        self.make_stale()
        ctx = self.start(self.fake_build(1))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("BUILD FAILED", ctx)
        self.assertIn("session-build.log", self.edit_ext(sid="ss", text="x")["hookSpecificOutput"]["permissionDecisionReason"])

    def test_non_oro_repo_is_silent(self):
        self.assertIsNone(self.start(cwd=self.tmp.name))
        other = os.path.join(self.tmp.name, "plain")
        os.makedirs(os.path.join(other, "bin"))
        open(os.path.join(other, "bin", "console"), "w").close()
        with open(os.path.join(other, "composer.lock"), "w") as fh:
            json.dump({"packages": [{"name": "symfony/symfony"}]}, fh)
        self.assertIsNone(self.start(cwd=other))

    def test_override_adds_user_warning_and_log(self):
        out = self.start(OFF)
        self.assertIn("OFF", out["systemMessage"])
        self.assertEqual(self.log()[-1]["verdict"], "enforcement-off")


class NeverBricksTest(EnforceBase):
    def test_garbage_stdin_exits_zero_silently_for_every_hook(self):
        for script in ("pretooluse_edit.py", "pretooluse_bash.py", "posttooluse_bash.py", "sessionstart_atlas.py", "stop.py"):
            p = subprocess.run([sys.executable, os.path.join(HOOKS, script)], input="{{nope", capture_output=True, text=True,
                               env=dict(os.environ, HOME=self.home))
            self.assertEqual((p.returncode, p.stdout), (0, ""), script)


if __name__ == "__main__":
    unittest.main()
