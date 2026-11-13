import json
import os
import subprocess
import sys
import tempfile
import unittest

os.environ["ATLAS_NO_AUTOBUILD"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(HERE, "..", "hooks")
sys.path.insert(0, os.path.join(HERE, ".."))

from atlas import notesmigrate  # noqa: E402
from tests.test_notes import SVC, build_notes, project, write_note  # noqa: E402

CLI = os.path.join(HERE, "..", "..", "bin", "aaxis-oro")


def run(script, payload, home):
    env = dict(os.environ, HOME=home)
    p = subprocess.run([sys.executable, os.path.join(HOOKS, script)], input=payload if isinstance(payload, str) else json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=30)
    return p.returncode, (json.loads(p.stdout) if p.stdout.strip() else None)


def ctx(out):
    return (out or {}).get("hookSpecificOutput", {}).get("additionalContext", "")


class Base(unittest.TestCase):
    def setUp(self):
        self.root = project()
        self.home = tempfile.mkdtemp()
        self.mdir = notesmigrate.memory_dirs(self.root, home=self.home)[0]
        os.makedirs(self.mdir)

    def memory(self, name, text):
        with open(os.path.join(self.mdir, name), "w") as fh:
            fh.write(text)


class SessionStartTest(Base):
    def start(self):
        return run("sessionstart_notes.py", {"cwd": self.root, "session_id": "s"}, self.home)

    def test_always_cap_and_overflow(self):
        for i in range(41):
            write_note(self.root, "n%02d" % i, title="title %02d" % i, surface="always", updated="2026-10-%02d" % (i % 28 + 1))
        build_notes(self.root)
        _, out = self.start()
        lines = ctx(out).splitlines()
        self.assertEqual(sum(1 for ln in lines if ln.startswith("- ")), 40)
        self.assertIn("1 more always-tier notes", ctx(out))
        self.assertLessEqual(len(lines), 43)

    def test_missing_shard_prints_build_command_only(self):
        write_note(self.root, "a", surface="always")
        _, out = self.start()
        self.assertIn("atlas build --project", ctx(out))
        self.assertIn("--only notes", ctx(out))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".oro-ai", "atlas", "notes.jsonl")))

    def test_unmigrated_memory_prompt_and_global_exempt(self):
        self.memory("a.md", "---\nname: a\n---\nproject fact\n")
        self.memory("g.md", "---\nname: g\nscope: global\n---\nprefs\n")
        self.memory("MEMORY.md", "- [a](a.md) - x\n")
        _, out = self.start()
        self.assertIn("1 project memories are not migrated: run /aaxis-oro:notes-migrate", ctx(out))

    def test_silent_outside_oro_and_on_garbage(self):
        self.assertEqual(run("sessionstart_notes.py", {"cwd": tempfile.mkdtemp()}, self.home), (0, None))
        self.assertEqual(run("sessionstart_notes.py", "not json", self.home), (0, None))


class AnchoredTest(Base):
    def touch(self, rel):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "a").close()

    def read(self, rel, sid="s1"):
        return run("pretooluse_notes.py", {"session_id": sid, "tool_name": "Read", "cwd": self.root,
                                           "tool_input": {"file_path": os.path.join(self.root, rel)}}, self.home)

    def test_injects_once_per_file_per_session(self):
        write_note(self.root, "svc-note", title="Careful here", anchors="path:src/Acme/**/*.php")
        write_note(self.root, "other", title="Elsewhere", anchors="path:src/Zed/**")
        self.touch("src/Acme/Bundle/LiveBundle/Svc.php")
        self.touch("src/Zed/z.php")
        build_notes(self.root)
        _, first = self.read("src/Acme/Bundle/LiveBundle/Svc.php")
        self.assertIn("svc-note - Careful here", ctx(first))
        self.assertNotIn("Elsewhere", ctx(first))
        self.assertIsNone(self.read("src/Acme/Bundle/LiveBundle/Svc.php")[1])
        self.assertIn("svc-note", ctx(self.read("src/Acme/Bundle/LiveBundle/Svc.php", sid="s2")[1]))
        self.assertIsNone(self.read("src/Other/File.php")[1])

    def test_class_anchor_via_php_namespace(self):
        write_note(self.root, "cls", title="Class note", anchors="class:Oro\\Live\\Entity")
        build_notes(self.root)
        path = os.path.join(self.root, "src", "Entity.php")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write("<?php\nnamespace Oro\\Live;\n\nfinal class Entity {}\n")
        self.assertIn("cls - Class note", ctx(self.read("src/Entity.php")[1]))

    def test_missing_shard_hint_once(self):
        write_note(self.root, "a", anchors="path:src/**")
        self.assertIn("--only notes", ctx(self.read("src/A.php")[1]))
        self.assertIsNone(self.read("src/B.php")[1])


class MemoryBlockTest(Base):
    def write(self, name, **ti):
        ti.setdefault("file_path", os.path.join(self.mdir, name))
        tool = ti.pop("tool", "Write")
        return run("pretooluse_memory.py", {"tool_name": tool, "cwd": self.root, "tool_input": ti}, self.home)[1]

    def denied(self, out):
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_denies_project_memory_with_note_pointer(self):
        out = self.write("x.md", content="---\nname: x\ntype: project\n---\nfact")
        self.assertTrue(self.denied(out))
        self.assertIn(".oro-ai/notes/", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_allows_global_and_other_paths(self):
        self.assertFalse(self.denied(self.write("g.md", content="---\nname: g\nscope: global\n---\nx")))
        self.assertFalse(self.denied(self.write("n.md", file_path=os.path.join(self.root, "src", "n.md"), content="x")))

    def test_edit_follows_existing_scope(self):
        self.memory("g.md", "---\nscope: global\n---\nx")
        self.memory("p.md", "---\nname: p\n---\nx")
        self.assertFalse(self.denied(self.write("g.md", tool="Edit", old_string="x", new_string="y")))
        self.assertTrue(self.denied(self.write("p.md", tool="Edit", old_string="x", new_string="y")))

    def test_index_only_lists_global(self):
        self.memory("g.md", "---\nscope: global\n---\nx")
        self.assertFalse(self.denied(self.write("MEMORY.md", content="- [g](g.md) - pref\n")))
        self.assertTrue(self.denied(self.write("MEMORY.md", content="- [g](g.md)\n- [p](p.md)\n")))

    def test_other_project_memory_untouched_and_garbage_safe(self):
        other = notesmigrate.memory_dirs("/somewhere/else", home=self.home)[0]
        self.assertFalse(self.denied(self.write("x.md", file_path=os.path.join(other, "x.md"), content="fact")))
        self.assertEqual(run("pretooluse_memory.py", "{broken", self.home), (0, None))


class MigrateTest(Base):
    def cli(self, *args, stdin=None):
        p = subprocess.run([sys.executable, CLI, "memory", *args, "--project", self.root], capture_output=True, text=True,
                           env=dict(os.environ, HOME=self.home), input=stdin, timeout=120)
        return p.returncode, p.stdout

    def plan(self, items):
        path = os.path.join(self.home, "plan.json")
        json.dump({"items": items}, open(path, "w"))
        return path

    def test_inventory_apply_idempotent(self):
        self.memory("a.md", "---\nname: a\ndescription: d\nmetadata:\n  type: project\n---\nfact a\n")
        self.memory("b.md", "---\nname: b\n---\nstale\n")
        self.memory("c.md", "---\nname: c\n---\nprefers x\n")
        self.memory("MEMORY.md", "# idx\n- [a](a.md) - a\n- [b](b.md) - b\n- [c](c.md) - c\n")
        code, out = self.cli("inventory")
        self.assertEqual(out.count(".md |"), 3)
        plan = self.plan([
            {"file": "a.md", "action": "note", "slug": "fact-a", "title": "Fact A", "kind": "gotcha", "surface": "anchored",
             "anchors": ["path:src/**"], "body": "fact a", "suggest": "generalize"},
            {"file": "b.md", "action": "delete"}, {"file": "c.md", "action": "global"}])
        code, out = self.cli("apply", "--plan", plan, "--no-build")
        self.assertEqual(code, 0, out)
        self.assertIn("notes written 1, memories deleted 2, marked global 1", out)
        self.assertIn("suggest: a.md: generalize", out)
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".oro-ai", "notes", "fact-a.md")))
        self.assertEqual(sorted(os.listdir(self.mdir)), ["MEMORY.md", "c.md"])
        self.assertEqual(open(os.path.join(self.mdir, "MEMORY.md")).read(), "# idx\n- [c](c.md) - c\n")
        self.assertIn("scope: global", open(os.path.join(self.mdir, "c.md")).read())
        self.assertEqual(self.cli("inventory")[1].strip(), "nothing to migrate")
        code, out = self.cli("apply", "--plan", plan, "--no-build")
        self.assertEqual((code, "notes written 0, memories deleted 0, marked global 0" in out), (0, True))

    def test_secret_note_skipped_memory_kept(self):
        self.memory("s.md", "---\nname: s\n---\npassword=hunter2\n")
        plan = self.plan([{"file": "s.md", "action": "note", "slug": "s", "title": "S", "kind": "gotcha", "surface": "always",
                           "body": "password=hunter2"}])
        code, out = self.cli("apply", "--plan", plan, "--no-build")
        self.assertEqual(code, 1)
        self.assertIn("secret", out)
        self.assertTrue(os.path.isfile(os.path.join(self.mdir, "s.md")))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".oro-ai", "notes", "s.md")))

    def test_prose_secret_skipped_and_global_rewrite_backed_up(self):
        self.memory("s.md", "---\nname: s\n---\nthe admin password is hunter2\n")
        self.memory("g.md", "---\nname: g\n---\nprefers x\n")
        plan = self.plan([{"file": "s.md", "action": "note", "slug": "s", "title": "S", "kind": "gotcha", "surface": "always",
                           "body": "the admin password is hunter2"}, {"file": "g.md", "action": "global"}])
        code, out = self.cli("apply", "--plan", plan, "--no-build")
        self.assertEqual(code, 1)
        self.assertTrue(os.path.isfile(os.path.join(self.mdir, "s.md")))
        backups = os.listdir(os.path.join(self.home, ".claude", "backups"))
        import tarfile
        with tarfile.open(os.path.join(self.home, ".claude", "backups", backups[0])) as tar:
            self.assertIn("g.md", tar.getnames())

    def test_apply_builds_shard(self):
        self.memory("a.md", "---\nname: a\n---\nfact\n")
        plan = self.plan([{"file": "a.md", "action": "note", "slug": "fact-a", "title": "Fact A", "kind": "gotcha",
                           "surface": "always", "body": "fact"}])
        code, out = self.cli("apply", "--plan", plan)
        self.assertEqual(code, 0, out)
        self.assertIn("notes shard rebuilt", out)
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".oro-ai", "atlas", "notes.jsonl")))


if __name__ == "__main__":
    unittest.main()
