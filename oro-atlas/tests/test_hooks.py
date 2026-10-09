import json
import os
import subprocess
import sys
import tempfile
import unittest

os.environ["ATLAS_NO_AUTOBUILD"] = "1"

HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
sys.path.insert(0, os.path.join(HOOKS, ".."))

from atlas import index  # noqa: E402

UNSAFE = {"id": "Foo\\Mgr", "keys": ["Mgr", "foo.mgr"], "services": ["foo.mgr"], "consumer_count": 1,
          "consumers": [{"class": "Foo\\Cmd", "file": "src/Foo/Cmd.php", "line": 9}]}
TAG = {"id": "oro_foo.tag", "keys": [], "text": "3 services; consumed by FooPass", "file": "a.php", "line": 1}


def run(script, payload, home):
    env = dict(os.environ, HOME=home)
    p = subprocess.run([sys.executable, os.path.join(HOOKS, script)], input=json.dumps(payload), capture_output=True, text=True, env=env)
    return p.returncode, (json.loads(p.stdout) if p.stdout.strip() else None)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "proj")
        os.makedirs(os.path.join(self.root, "bin"))
        os.makedirs(os.path.join(self.root, "src", "Foo"))
        open(os.path.join(self.root, "bin", "console"), "w").close()
        with open(os.path.join(self.root, "composer.lock"), "w") as fh:
            json.dump({"packages": []}, fh)
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(self.home)
        self.file = os.path.join(self.root, "src", "Foo", "services.yml")

    def tearDown(self):
        self.tmp.cleanup()

    def build_index(self):
        out = os.path.join(self.root, ".claude", "atlas")
        os.makedirs(out)
        for name, rec in (("unsafe", UNSAFE), ("tags", TAG)):
            with open(os.path.join(out, name + ".jsonl"), "w") as fh:
                fh.write(json.dumps(rec) + "\n")
        index.update_index(self.root, out, {"unsafe": 1, "tags": 1})

    def edit(self, new, old="", tool="Edit", path=None):
        ti = {"file_path": path or self.file, "new_string": new, "old_string": old}
        return run("pretooluse_edit.py", {"session_id": "s1", "tool_name": tool, "tool_input": ti}, self.home)

    def log(self):
        with open(os.path.join(self.home, ".claude", "atlas-hook.log")) as fh:
            return [json.loads(x) for x in fh]

class HookTest(Base):
    def test_deny_decorates_unsafe_target(self):
        self.build_index()
        code, out = self.edit("services:\n  x:\n    decorates: foo.mgr\n")
        hso = out["hookSpecificOutput"]
        self.assertEqual((code, hso["permissionDecision"]), (0, "deny"))
        self.assertIn("aaxis_aspect.interceptor", hso["permissionDecisionReason"])
        self.assertIn("Cmd", hso["permissionDecisionReason"])
        self.assertEqual(self.log()[-1]["verdict"], "deny")

    def test_deny_final_target_uses_final_advice(self):
        self.build_index()
        rec = dict(UNSAFE, id="Foo\\Fin", keys=["Fin", "foo.fin"], services=["foo.fin"], kind="final class")
        with open(os.path.join(self.root, ".claude", "atlas", "unsafe.jsonl"), "a") as fh:
            fh.write(json.dumps(rec) + "\n")
        _, out = self.edit("services:\n  x:\n    decorates: foo.fin\n")
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("cannot proxy a final class", reason)
        self.assertNotIn("Use the aaxis_aspect.interceptor tag instead", reason)

    def test_existing_decorates_not_denied_and_other_target_allowed(self):
        self.build_index()
        _, out = self.edit("decorates: foo.mgr\n  x: 1", old="decorates: foo.mgr")
        self.assertIsNone(out)
        _, out = self.edit("decorates: other.svc")
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])

    def test_tag_context_under_2kb(self):
        self.build_index()
        _, out = self.edit("    tags:\n      - { name: oro_foo.tag }\n")
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("oro_foo.tag", ctx)
        self.assertLessEqual(len(ctx.encode()), 2000)

    def test_missing_index_tells_model_to_build_without_blocking(self):
        _, out = self.edit("decorates: foo.mgr")
        hso = out["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("atlas-build", hso["additionalContext"])

    def test_stale_index(self):
        self.build_index()
        with open(os.path.join(self.root, "composer.lock"), "w") as fh:
            json.dump({"packages": [], "x": 1}, fh)
        _, out = self.edit("decorates: foo.mgr")
        self.assertIn("STALE", out["hookSpecificOutput"]["additionalContext"])

    def test_non_watched_file_and_garbage_stdin_are_silent(self):
        self.build_index()
        _, out = self.edit("decorates: foo.mgr", path=os.path.join(self.root, "templates", "a.yml"))
        self.assertIsNone(out)
        p = subprocess.run([sys.executable, os.path.join(HOOKS, "pretooluse_edit.py")], input="nope", capture_output=True, text=True, env=dict(os.environ, HOME=self.home))
        self.assertEqual((p.returncode, p.stdout), (0, ""))

    def test_config_dir_and_xml_are_scanned(self):
        self.build_index()
        _, out = self.edit("decorates: foo.mgr", path=os.path.join(self.root, "config", "services.yml"))
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        _, out = self.edit('<service id="x" decorates="foo.mgr"/>', path=os.path.join(self.root, "src", "Foo", "s.xml"))
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_quoted_at_and_escaped_targets(self):
        self.build_index()
        for new in ('decorates: "@foo.mgr"', "decorates: '@foo.mgr'", 'decorates: "Foo\\\\Mgr"', "{ decorates: Foo\\Mgr }"):
            _, out = self.edit(new)
            self.assertEqual(out["hookSpecificOutput"].get("permissionDecision"), "deny", new)

    def test_duplicate_decorates_counted(self):
        self.build_index()
        _, out = self.edit("decorates: foo.mgr\ndecorates: foo.mgr", old="decorates: foo.mgr")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_write_compares_with_existing_file(self):
        self.build_index()
        with open(self.file, "w") as fh:
            fh.write("services:\n  x:\n    decorates: foo.mgr\n")
        ti = {"file_path": self.file, "content": "services:\n  x:\n    decorates: foo.mgr\n  y: ~\n"}
        _, out = run("pretooluse_edit.py", {"tool_name": "Write", "tool_input": ti}, self.home)
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])

    def test_as_decorator_resolved_via_use_import(self):
        self.build_index()
        php = os.path.join(self.root, "src", "Foo", "Dec.php")
        new = "<?php\nnamespace App;\nuse Foo\\Mgr;\n#[AsDecorator(Mgr::class)]\nclass Dec {}\n"
        ti = {"file_path": php, "content": new}
        _, out = run("pretooluse_edit.py", {"tool_name": "Write", "tool_input": ti}, self.home)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        ti = {"file_path": php, "content": new.replace("use Foo\\Mgr;", "use Other\\Mgr;")}
        _, out = run("pretooluse_edit.py", {"tool_name": "Write", "tool_input": ti}, self.home)
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])

    def test_alias_resolved_via_services_shard(self):
        self.build_index()
        with open(os.path.join(self.root, ".claude", "atlas", "services.jsonl"), "w") as fh:
            fh.write(json.dumps({"id": "foo.mgr", "class": "Foo\\Mgr", "aliases": ["foo.mgr.alias"]}) + "\n")
        _, out = self.edit("decorates: foo.mgr.alias")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_multiedit_write(self):
        self.build_index()
        ti = {"file_path": self.file, "edits": [{"old_string": "a", "new_string": "decorates: foo.mgr"}]}
        _, out = run("pretooluse_edit.py", {"tool_name": "MultiEdit", "tool_input": ti}, self.home)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        ti = {"file_path": self.file, "content": "decorates: foo.mgr"}
        _, out = run("pretooluse_edit.py", {"tool_name": "Write", "tool_input": ti}, self.home)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def prompt(self, text, sid="s", cwd=None):
        return run("userpromptsubmit.py", {"session_id": sid, "prompt": text, "cwd": cwd or self.root}, self.home)[1]

    def test_prompt_nudge_needs_two_hits_once_per_session(self):
        self.build_index()
        self.assertIsNone(self.prompt("decorate the price provider service"))
        out = self.prompt("decorate the price provider or use an interceptor")
        self.assertIn(self.root, out["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("/opt/projects/buckman", out["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(self.prompt("override the datagrid listener"))
        self.assertIsNotNone(self.prompt("override the datagrid listener", sid="s2"))
        self.assertIsNone(self.prompt("override the datagrid listener", sid="s3", cwd=self.tmp.name))
        self.assertEqual([r["verdict"] for r in self.log()], ["skip", "nudge", "already-nudged", "nudge", "skip"])

    def test_prompt_nudge_oro_vocabulary_alone_is_enough(self):
        self.build_index()
        self.assertIsNotNone(self.prompt("Which mediator events exist?", sid="m1"))
        self.assertIsNotNone(self.prompt("Add a column to the products datagrid", sid="m2"))
        self.assertIsNotNone(self.prompt("What event should I listen to when an order is placed?", sid="m3"))
        self.assertIsNone(self.prompt("fix the typo in the README", sid="m4"))
        self.assertIsNone(self.prompt("decorate the price provider service", sid="m5"))

    def test_prompt_nudge_mentions_build_when_index_missing(self):
        out = self.prompt("override the datagrid listener")
        self.assertIn("atlas-build", out["hookSpecificOutput"]["additionalContext"])


class BashHookTest(Base):
    def git(self, *args):
        subprocess.run(["git", "-C", self.root, *args], check=True, capture_output=True)

    def bash(self, sid="b"):
        return run("posttooluse_bash.py", {"session_id": sid, "tool_name": "Bash", "cwd": self.root, "tool_input": {"command": "sed ..."}}, self.home)[1]

    def test_bash_introduced_unsafe_decorates_blocks_once(self):
        self.build_index()
        with open(self.file, "w") as fh:
            fh.write("services: {}\n")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "i")
        self.assertIsNone(self.bash())
        with open(self.file, "a") as fh:
            fh.write("  x:\n    decorates: foo.mgr\n")
        out = self.bash()
        self.assertEqual(out["decision"], "block")
        self.assertIn("src/Foo/services.yml", out["reason"])
        self.assertIsNone(self.bash())
        with open(os.path.join(self.root, "src", "Foo", "new.xml"), "w") as fh:
            fh.write('<service id="y" decorates="Foo\\Mgr"/>')
        self.assertIn("new.xml", self.bash(sid="c")["reason"])
        self.assertIsNone(self.bash(sid="c"))


class SetupTest(unittest.TestCase):
    def test_setup_merges_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "bin"))
            os.makedirs(os.path.join(tmp, ".claude"))
            open(os.path.join(tmp, "bin", "console"), "w").close()
            path = os.path.join(tmp, ".claude", "settings.local.json")
            with open(path, "w") as fh:
                json.dump({"permissions": {"allow": ["x"]}, "hooks": {"PostToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "git add"}]}]}}, fh)
            setup = os.path.join(HOOKS, "..", "bin", "atlas-setup")
            for _ in range(2):
                subprocess.run([sys.executable, setup, tmp, "--no-build"], check=True, capture_output=True)
            with open(path) as fh:
                data = json.load(fh)
            self.assertEqual(data["permissions"], {"allow": ["x"]})
            self.assertEqual(len(data["hooks"]["PostToolUse"]), 3)
            self.assertEqual([len(data["hooks"][e]) for e in ("PreToolUse", "UserPromptSubmit")], [1, 1])
            self.assertTrue(data["hooks"]["PreToolUse"][0]["hooks"][0]["command"].endswith("hooks/pretooluse_edit.py"))


class PrecommitTest(Base):
    def git(self, *args):
        subprocess.run(["git", "-C", self.root, "-c", "user.email=t@t", "-c", "user.name=t", *args],
                       check=True, capture_output=True)

    def precommit(self):
        exe = os.path.join(HOOKS, "..", "bin", "atlas-precommit")
        return subprocess.run([sys.executable, exe], cwd=self.root, capture_output=True, text=True,
                              env=dict(os.environ, HOME=self.home))

    def test_staged_new_decorates_on_unsafe_target_fails(self):
        self.build_index()
        self.git("init", "-q")
        with open(self.file, "w") as fh:
            fh.write("services:\n    a:\n        decorates: foo.mgr\n")
        self.git("add", "src")
        self.git("commit", "-qm", "base")
        self.assertEqual(self.precommit().returncode, 0)
        with open(self.file, "a") as fh:
            fh.write("    b:\n        decorates: other.svc\n")
        self.git("add", "src")
        self.assertEqual(self.precommit().returncode, 0)
        php = os.path.join(self.root, "config", "D.php")
        os.makedirs(os.path.dirname(php))
        with open(php, "w") as fh:
            fh.write("<?php\n#[AsDecorator('foo.mgr')]\nclass D {}\n")
        self.git("add", "config")
        p = self.precommit()
        self.assertEqual(p.returncode, 1)
        self.assertIn("config/D.php", p.stderr)
        self.assertIn("Do not decorate 'foo.mgr'", p.stderr)


if __name__ == "__main__":
    unittest.main()
