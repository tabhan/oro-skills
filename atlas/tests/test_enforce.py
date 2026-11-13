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
        self.build_marker = os.path.join(self.tmp.name, "build-ran")
        with open(path, "w") as fh:
            fh.write("import sys\nopen(%r, 'w').close()\nsys.exit(%d)\n" % (self.build_marker, exit_code))
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
        self.bash("aaxis-oro atlas status")
        self.assertEqual(self.decision(self.edit_ext()), "deny")
        self.bash("/x/bin/aaxis-oro atlas --project /p service foo.bar | head")
        self.assertIsNone(self.decision(self.edit_ext()))

    def test_marker_is_per_session_and_shared_by_subagents_using_the_parent_id(self):
        self.bash("aaxis-oro atlas event kernel.request", sid="parent")
        self.assertIsNone(self.decision(self.edit_ext(sid="parent")))
        self.assertEqual(self.decision(self.edit_ext(sid="other")), "deny")

    def test_non_extension_file_is_never_denied(self):
        ti = {"file_path": self.file, "new_string": "a: 1", "old_string": ""}
        _, out = run("pretooluse_edit.py", {"session_id": "s1", "tool_name": "Edit", "tool_input": ti}, self.home)
        self.assertNotEqual(self.decision(out), "deny")

    def test_stale_index_denies_even_after_query_and_names_build(self):
        self.bash("aaxis-oro atlas service x")
        self.make_stale()
        out = self.edit_ext()
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("atlas build", out["hookSpecificOutput"]["permissionDecisionReason"])

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


class StalenessKindTest(EnforceBase):
    def touch_src(self):
        with open(os.path.join(self.root, "src", "Foo", "New.php"), "w") as fh:
            fh.write("<?php")

    def test_own_src_edits_never_deny_and_warn_once_per_session(self):
        self.bash("aaxis-oro atlas service x")
        self.touch_src()
        first = self.edit_ext()
        self.assertNotEqual(self.decision(first), "deny")
        self.assertIn("behind your src edits", first["hookSpecificOutput"]["additionalContext"])
        self.assertIn("--incremental", first["hookSpecificOutput"]["additionalContext"])
        again = self.edit_ext()
        self.assertNotIn("behind", json.dumps(again))

    def test_composer_lock_change_still_denies_with_command(self):
        self.bash("aaxis-oro atlas service x")
        self.make_stale()
        self.touch_src()
        out = self.edit_ext()
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("rebuild:", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_extractor_change_is_soft(self):
        self.bash("aaxis-oro atlas service x")
        idx = os.path.join(self.root, ".oro-ai", "atlas", "index.json")
        data = json.load(open(idx))
        for meta in data["shards"].values():
            meta["inputs"]["extractor"] = "old"
        json.dump(data, open(idx, "w"))
        self.assertNotEqual(self.decision(self.edit_ext()), "deny")

    def test_missing_index_still_denies(self):
        self.bash("aaxis-oro atlas service x")
        os.remove(os.path.join(self.root, ".oro-ai", "atlas", "index.json"))
        self.assertEqual(self.decision(self.edit_ext()), "deny")


class ExtensionFileTest(EnforceBase):
    def denied(self, rel):
        path = os.path.join(self.root, rel)
        ti = {"file_path": path, "new_string": "x", "old_string": ""}
        _, out = run("pretooluse_edit.py", {"session_id": "m3", "tool_name": "Edit", "tool_input": ti}, self.home)
        return self.decision(out) == "deny"

    def test_real_extension_points_are_enforced(self):
        for rel in ("src/A/Resources/config/services.yml", "src/A/Resources/config/services_test.yml", "src/A/Resources/config/oro/datagrids.yml",
                    "src/A/Resources/config/oro/workflows.yml", "src/A/Resources/config/oro/actions.yml", "src/A/Resources/config/oro/system_configuration.yml",
                    "src/A/Resources/config/oro/app.yml", "src/A/Resources/config/oro/jsmodules.yml", "src/A/Resources/config/oro/entity_extend.yml",
                    "src/A/Resources/views/layouts/default/config/page.yml", "src/A/EventListener/XListener.php", "src/A/Grid/FooExtension.php",
                    "src/A/Aspect/FooDecorator.php", "src/A/Resources/config/services/more.yml"):
            self.assertTrue(self.denied(rel), rel)

    def test_other_files_are_not(self):
        for rel in ("src/A/Resources/config/oro/routing.yml", "src/A/Resources/config/validation.yml", "src/A/Resources/translations/messages.en.yml",
                    "src/A/Resources/config/oro/search.yml", "src/A/Twig/FooExtension.php", "src/A/Entity/Foo.php", "src/A/Tests/Unit/FooListenerTest.php",
                    "src/A/Resources/views/page/x.html.twig"):
            self.assertFalse(self.denied(rel), rel)


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
        for cmd in ("echo $ORO_ATLAS_ENFORCE", "printf %s \"${ORO_ATLAS_ENFORCE}\"", "ls -la", "aaxis-oro atlas service foo"):
            self.assertIsNone(self.bash(cmd, script="pretooluse_bash.py"), cmd)

    def test_read_only_mentions_pass(self):
        for cmd in ("grep -rn ORO_ATLAS_ENFORCE README.md", "rg ORO_ATLAS_ENFORCE atlas/", "cat atlas/README.md | grep ORO_ATLAS_ENFORCE",
                    "git log -S ORO_ATLAS_ENFORCE --oneline", "git diff origin/main -- atlas/hooks/_common.py",
                    "echo 'ORO_ATLAS_ENFORCE=0 disables the gate'", "grep -n ORO_ATLAS_ENFORCE ~/.zshrc", "grep -n ORO_ATLAS_ENFORCE ~/.bashrc",
                    "grep 'ORO_ATLAS_ENFORCE=0' docs.md", "python3 -m unittest atlas.tests.test_enforce -k ORO_ATLAS_ENFORCE"):
            self.assertIsNone(self.bash(cmd, script="pretooluse_bash.py"), cmd)

    def test_setting_or_persisting_the_switch_is_denied(self):
        for cmd in ("echo 'export ORO_ATLAS_ENFORCE=0' >> ~/.zshrc", "ORO_ATLAS_ENFORCE=0 claude", "FOO=1 ORO_ATLAS_ENFORCE=0 claude",
                    "set -a; ORO_ATLAS_ENFORCE=0; set +a", "typeset -x ORO_ATLAS_ENFORCE=0",
                    "printf 'ORO_ATLAS_ENFORCE=0\\n' | tee -a ~/.config/environment.d/x.conf",
                    "cd /x && export ORO_ATLAS_ENFORCE=0", "echo ORO_ATLAS_ENFORCE=0 >> .env.local",
                    "echo 'export ORO_ATLAS_ENFORCE=0' >> ~/.bashrc", "echo 'export ORO_ATLAS_ENFORCE=0' >> ~/.bash_profile",
                    "echo 'ORO_ATLAS_ENFORCE=0' >> ~/.profile", "echo 'export ORO_ATLAS_ENFORCE=0' >> ~/.zshenv",
                    "echo 'set -x ORO_ATLAS_ENFORCE 0' >> ~/.config/fish/config.fish", "echo 'ORO_ATLAS_ENFORCE=0' | sudo tee -a /etc/environment",
                    "echo 'ORO_ATLAS_ENFORCE=0' >> ~/.pam_environment", "echo 'export ORO_ATLAS_ENFORCE=0' >> .envrc",
                    "sed -i '$a export ORO_ATLAS_ENFORCE=0' /etc/profile.d/x.sh"):
            self.assertEqual(self.decision(self.bash(cmd, script="pretooluse_bash.py")), "deny", cmd)

    def test_obfuscated_assembly_into_settings_or_rc_is_denied(self):
        for cmd in ("jq '.env.ORO_ATLAS_\"ENFORCE\"=\"0\"' ~/.claude/settings.json > /tmp/x",
                    "python3 -c \"import json;d['env']['ORO_ATLAS_'+'ENFORCE']='0'\" ~/.claude/settings.local.json",
                    "echo 'export ORO_ATLAS_EN''FORCE=0' >> ~/.bashrc", "sed -i 's/x/ATLAS_ENFORCE/' .env.local"):
            self.assertEqual(self.decision(self.bash(cmd, script="pretooluse_bash.py")), "deny", cmd)

    def test_obfuscated_write_tool_content_is_denied(self):
        ti = {"file_path": os.path.join(self.home, ".claude", "settings.json"), "content": '{"env":{"ORO_ATLAS_" "ENFORCE":"0"}}'}
        _, out = run("pretooluse_edit.py", {"session_id": "w", "tool_name": "Write", "tool_input": ti}, self.home)
        self.assertEqual(self.decision(out), "deny")

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


class ComposerHintTest(EnforceBase):
    def test_composer_update_hints_the_command_and_never_builds(self):
        self.make_stale()
        out = self.bash("composer update oro/platform", extra_env=self.fake_build(0))
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("rebuild:", ctx)
        self.assertIn("--incremental", ctx)
        self.assertFalse(os.path.exists(self.build_marker))

    def test_composer_with_fresh_index_is_silent(self):
        self.assertIsNone(self.bash("composer install"))


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

    def test_stale_index_is_reported_with_exact_command_and_never_rebuilt(self):
        self.make_stale()
        ctx = self.start(self.fake_build(0))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("atlas index stale (composer.lock changed); rebuild: ", ctx)
        self.assertIn("atlas build --project %s --incremental" % self.root, ctx)
        self.assertFalse(os.path.exists(self.build_marker))

    def test_stale_deny_message_carries_the_command(self):
        self.make_stale()
        self.start()
        reason = self.edit_ext(sid="ss", text="x")["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("--incremental", reason)

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
