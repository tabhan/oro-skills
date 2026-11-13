import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.dirname(HERE)
REPO = os.path.dirname(ATLAS)
sys.path.insert(0, ATLAS)

from atlas import legacy  # noqa: E402

LEGACY = "python3 /x/oro-skills/oro-atlas/hooks/pretooluse_edit.py"


def project(extra=None):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, ".claude"))
    settings = {"permissions": {"allow": ["x"]}, "hooks": {
        "PreToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": LEGACY}]}],
        "PostToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "git add"},
                                                      {"type": "command", "command": "python3 /o/oro-atlas/hooks/subagentstart.py"}]}]}}
    settings.update(extra or {})
    with open(os.path.join(d, ".claude", "settings.local.json"), "w") as fh:
        json.dump(settings, fh)
    return d


class CleanupTest(unittest.TestCase):
    def test_only_owned_entries_removed(self):
        d = project()
        self.assertTrue(legacy.cleanup(d))
        data = legacy.load(d)
        self.assertEqual(data["permissions"], {"allow": ["x"]})
        self.assertEqual(data["hooks"], {"PostToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "git add"}]}]})
        self.assertFalse(legacy.cleanup(d))

    def test_foreign_oro_atlas_path_without_script_kept(self):
        d = project({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo oro-atlas done"}]}]}})
        legacy.cleanup(d)
        self.assertEqual(legacy.load(d)["hooks"]["Stop"][0]["hooks"][0]["command"], "echo oro-atlas done")


class SessionStartHookTest(unittest.TestCase):
    def run_hook(self, cwd):
        p = subprocess.run([sys.executable, os.path.join(ATLAS, "hooks", "sessionstart_legacy.py")],
                           input=json.dumps({"cwd": cwd}), capture_output=True, text=True)
        return p

    def test_warns_with_exact_command_then_silent_after_cleanup(self):
        d = project()
        out = json.loads(self.run_hook(d).stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "SessionStart")
        self.assertIn("aaxis-oro atlas setup --cleanup-only " + d, out["additionalContext"])
        subprocess.run([sys.executable, os.path.join(REPO, "bin", "aaxis-oro"), "atlas", "setup", "--cleanup-only", d], check=True, capture_output=True)
        self.assertEqual(self.run_hook(d).stdout, "")

    def test_silent_without_settings_and_on_garbage(self):
        self.assertEqual(self.run_hook(tempfile.mkdtemp()).stdout, "")
        p = subprocess.run([sys.executable, os.path.join(ATLAS, "hooks", "sessionstart_legacy.py")], input="{no", capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (0, ""))

    def test_registered_in_plugin_hooks(self):
        with open(os.path.join(REPO, "hooks", "hooks.json")) as fh:
            groups = json.load(fh)["hooks"]["SessionStart"]
        self.assertIn("sessionstart_legacy.py", groups[0]["hooks"][0]["command"])


class InstallCleanupTest(unittest.TestCase):
    def test_install_cleans_project_and_survives_failing_claude(self):
        d, home, fake = project(), tempfile.mkdtemp(), tempfile.mkdtemp()
        with open(os.path.join(fake, "claude"), "w") as fh:
            fh.write("#!/bin/sh\nexit 1\n")
        os.chmod(os.path.join(fake, "claude"), 0o755)
        env = dict(os.environ, CLAUDE_SKILLS_DIR=home + "/skills", CLAUDE_AGENTS_DIR=home + "/agents",
                   ORO_ATLAS_BIN_DIR=home + "/bin", PATH=fake + ":" + os.environ["PATH"])
        p = subprocess.run([os.path.join(REPO, "install.sh"), "--no-update", "--project", d], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)  # failures reported, not aborted
        self.assertIn("claude plugin install aaxis-oro@aaxis-oro", p.stderr)
        self.assertTrue(os.path.islink(home + "/bin/aaxis-oro"))  # CLI still linked after the failure
        self.assertFalse(legacy.project_has_legacy(d))
        self.assertEqual(legacy.load(d)["permissions"], {"allow": ["x"]})


if __name__ == "__main__":
    unittest.main()
