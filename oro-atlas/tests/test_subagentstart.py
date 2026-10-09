import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_hooks import HOOKS, Base, run  # noqa: E402


class SubagentStartTest(Base):
    def start(self, cwd=None):
        return run("subagentstart.py", {"session_id": "s1", "hook_event_name": "SubagentStart", "agent_type": "general-purpose",
                                        "cwd": cwd or self.root}, self.home)

    def test_injects_short_instruction_with_paths(self):
        self.build_index()
        code, out = self.start()
        hso = out["hookSpecificOutput"]
        self.assertEqual((code, hso["hookEventName"]), (0, "SubagentStart"))
        ctx = hso["additionalContext"]
        self.assertLess(len(ctx.encode()), 900)
        for needle in ("bin/atlas", "--project " + self.root, "unsafe", "file:line", "--incremental", "exits 2", "atlas build --project", "config|tags|layout|workflow|js"):
            self.assertIn(needle, ctx)

    def test_silent_without_index_or_outside_oro(self):
        self.assertEqual(self.start(), (0, None))
        self.build_index()
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(self.start(other), (0, None))

    def test_fails_open_on_garbage_stdin(self):
        p = subprocess.run([sys.executable, os.path.join(HOOKS, "subagentstart.py")], input="{nope", capture_output=True,
                           text=True, env=dict(os.environ, HOME=self.home))
        self.assertEqual((p.returncode, p.stdout), (0, ""))


class SetupRegistrationTest(unittest.TestCase):
    def test_subagentstart_registered_once_and_user_hooks_kept(self):
        setup = os.path.join(HOOKS, "..", "bin", "atlas-setup")
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "bin"))
            os.makedirs(os.path.join(tmp, ".claude"))
            open(os.path.join(tmp, "bin", "console"), "w").close()
            path = os.path.join(tmp, ".claude", "settings.local.json")
            user = {"hooks": {"SubagentStart": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}, "env": {"A": "1"}}
            with open(path, "w") as fh:
                json.dump(user, fh)
            for _ in range(3):
                subprocess.run([sys.executable, setup, tmp, "--no-build"], check=True, capture_output=True)
            with open(path) as fh:
                data = json.load(fh)
            cmds = [h["command"] for g in data["hooks"]["SubagentStart"] for h in g["hooks"]]
            self.assertEqual(len(cmds), 2)
            self.assertEqual(cmds[0], "echo mine")
            self.assertTrue(cmds[1].endswith("hooks/subagentstart.py"))
            self.assertEqual(data["env"], {"A": "1"})


if __name__ == "__main__":
    unittest.main()
