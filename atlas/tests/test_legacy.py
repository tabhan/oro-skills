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


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(data, fh)


def legacy_settings(script):
    return {"model": "x", "hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": "python3 /o/oro-skills/oro-atlas/hooks/" + script},
        {"type": "command", "command": "keep-me"}]}]}}


class CleanupAllTest(unittest.TestCase):
    def test_every_settings_file_cleaned_and_others_kept(self):
        home, proj = tempfile.mkdtemp(), tempfile.mkdtemp()
        names = [os.path.join(r, ".claude", n) for r in (home, proj) for n in ("settings.json", "settings.local.json")]
        for path, script in zip(names, legacy.SCRIPTS):
            write(path, legacy_settings(script))
        with open(names[0] + ".bak", "w") as fh:
            fh.write("{bad")
        bad = os.path.join(proj, ".claude", "other.json")
        write(bad, legacy_settings("stop.py"))
        self.assertEqual(sorted(legacy.cleanup_all(proj, home)), sorted(names))
        for path in names:
            with open(path) as fh:
                raw = fh.read()
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(json.loads(raw), {"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "keep-me"}]}]}})
            self.assertIn('\n  "model"', raw)
        self.assertEqual(legacy.load_file(bad), legacy_settings("stop.py"))
        self.assertEqual(legacy.cleanup_all(proj, home), [])

    def test_invalid_and_missing_files_skipped(self):
        home, proj = tempfile.mkdtemp(), tempfile.mkdtemp()
        os.makedirs(os.path.join(home, ".claude"))
        with open(os.path.join(home, ".claude", "settings.json"), "w") as fh:
            fh.write("{nope")
        write(os.path.join(proj, ".claude", "settings.json"), {"hooks": "weird"})
        self.assertEqual(legacy.cleanup_all(proj, home), [])


class CompatShimTest(unittest.TestCase):
    def run_shim(self, name, stdin, home):
        return subprocess.run([sys.executable, os.path.join(REPO, "oro-atlas", "hooks", name)], input=stdin,
                              capture_output=True, text=True, env=dict(os.environ, HOME=home))

    def test_every_legacy_script_has_a_shim_that_cleans_and_stays_silent(self):
        for name in legacy.SCRIPTS:
            self.assertTrue(os.path.exists(os.path.join(REPO, "oro-atlas", "hooks", name)), name)
        home, proj = tempfile.mkdtemp(), tempfile.mkdtemp()
        write(os.path.join(home, ".claude", "settings.json"), legacy_settings("userpromptsubmit.py"))
        write(os.path.join(proj, ".claude", "settings.local.json"), legacy_settings("userpromptsubmit.py"))
        p = self.run_shim("userpromptsubmit.py", json.dumps({"cwd": proj}), home)
        self.assertEqual((p.returncode, p.stdout), (0, ""))
        self.assertEqual(legacy.cleanup_all(proj, home), [])

    def test_garbage_stdin_never_errors(self):
        p = self.run_shim("stop.py", "{no", tempfile.mkdtemp())
        self.assertEqual((p.returncode, p.stdout), (0, ""))

    def test_not_registered_as_plugin_hooks(self):
        with open(os.path.join(REPO, "hooks", "hooks.json")) as fh:
            self.assertNotIn("oro-atlas", fh.read())


class SessionStartHookTest(unittest.TestCase):
    def run_hook(self, cwd):
        p = subprocess.run([sys.executable, os.path.join(ATLAS, "hooks", "sessionstart_legacy.py")],
                           input=json.dumps({"cwd": cwd}), capture_output=True, text=True)
        return p

    def test_auto_cleans_silently(self):
        d = project()
        p = self.run_hook(d)
        self.assertEqual((p.returncode, p.stdout), (0, ""))
        self.assertFalse(legacy.project_has_legacy(d))
        self.assertEqual(legacy.load(d)["permissions"], {"allow": ["x"]})

    def test_silent_without_settings_and_on_garbage(self):
        self.assertEqual(self.run_hook(tempfile.mkdtemp()).stdout, "")
        p = subprocess.run([sys.executable, os.path.join(ATLAS, "hooks", "sessionstart_legacy.py")], input="{no", capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (0, ""))

    def test_registered_in_plugin_hooks(self):
        with open(os.path.join(REPO, "hooks", "hooks.json")) as fh:
            groups = json.load(fh)["hooks"]["SessionStart"]
        self.assertEqual(len(groups), 1)
        self.assertIn("sessionstart.py", groups[0]["hooks"][0]["command"])


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

    def test_install_cleans_user_level_settings(self):
        home, d = tempfile.mkdtemp(), tempfile.mkdtemp()
        write(os.path.join(home, ".claude", "settings.json"), legacy_settings("stop.py"))
        env = dict(os.environ, HOME=home, CLAUDE_SKILLS_DIR=home + "/skills", CLAUDE_AGENTS_DIR=home + "/agents",
                   ORO_ATLAS_BIN_DIR=home + "/bin")
        subprocess.run([os.path.join(REPO, "install.sh"), "--no-update", "--no-plugin", "--no-official-plugins", "--project", d],
                       env=env, capture_output=True, text=True, check=True)
        self.assertNotIn("oro-atlas", open(os.path.join(home, ".claude", "settings.json")).read())


if __name__ == "__main__":
    unittest.main()
