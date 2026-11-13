import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SKILL = os.path.join(HERE, "fixtures", "skill")
sys.path.insert(0, os.path.join(ROOT, "lib"))

CLI = os.path.join(ROOT, "bin", "oro-version")
HOOK = os.path.join(ROOT, "oro-atlas", "hooks", "sessionstart_version.py")


def diff(*args):
    return subprocess.run([sys.executable, CLI, "diff", "--root", SKILL, *args], capture_output=True, text=True)


def lock(version):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, ".oro-ai"))
    write_lock(d, version)
    return d


def write_lock(d, version):
    with open(os.path.join(d, "composer.lock"), "w") as fh:
        json.dump({"packages": [{"name": "oro/platform", "version": version}]}, fh)


def hook(project):
    r = subprocess.run([sys.executable, HOOK], input=json.dumps({"cwd": project}), capture_output=True, text=True)
    return json.loads(r.stdout) if r.stdout else None


class DiffTest(unittest.TestCase):
    def rows(self, a, b):
        r = diff("--from", a, "--to", b, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_upgrade_activates_v8_and_deactivates_v7(self):
        rows = self.rows("7.0.5", "8.0.0")
        got = {(r["change"], r["path"]) for r in rows}
        self.assertIn(("activates", "references/v8/workflow.md"), got)
        self.assertIn(("deactivates", "references/v7/workflow.md"), got)
        self.assertIn(("activates", "references/sectioned.md"), got)
        wf = [r for r in rows if r["topic"] == "wf"]
        self.assertEqual({r["change"] for r in wf}, {"activates", "deactivates"})

    def test_downgrade_reverses(self):
        self.assertIn(("deactivates", "references/v8/workflow.md"), {(r["change"], r["path"]) for r in self.rows("8.0.0", "7.0.5")})

    def test_patch_granularity(self):
        self.assertEqual([r["title"] for r in self.rows("7.0.3", "7.0.5")], ["since 7.0.5"])
        self.assertEqual(self.rows("7.0.5", "7.0.9"), [])

    def test_table_output_lists_topic_title_path(self):
        out = diff("--from", "7.0.5", "--to", "8.0.0").stdout
        self.assertIn("references/v8/workflow.md", out)
        self.assertIn("topic", out.splitlines()[0])

    def test_leading_v_accepted(self):
        self.assertEqual(self.rows("v7.0.5", "v8.0.0"), self.rows("7.0.5", "8.0.0"))

    def test_bad_version_is_usage_error(self):
        self.assertEqual(diff("--from", "x", "--to", "8.0.0").returncode, 64)


class SessionStartVersionTest(unittest.TestCase):
    def test_silent_first_time_then_announces_once_on_change(self):
        d = lock("7.0.5")
        self.assertIsNone(hook(d))
        self.assertIsNone(hook(d))
        write_lock(d, "8.0.0")
        out = hook(d)
        self.assertIn("7.0.5 -> 8.0.0", out["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(hook(d))

    def test_marker_not_written_when_project_has_no_oro_ai_dir(self):
        d = tempfile.mkdtemp()
        write_lock(d, "7.0.5")
        hook(d)
        self.assertFalse(os.path.exists(os.path.join(d, ".oro-ai")))

    def test_marker_kept_when_diff_fails(self):
        d = lock("7.0.5")
        hook(d)
        with open(os.path.join(d, ".oro-ai", "version-announced.json"), "w") as fh:
            json.dump({"version": "garbage"}, fh)
        write_lock(d, "8.0.0")
        hook(d)
        with open(os.path.join(d, ".oro-ai", "version-announced.json")) as fh:
            self.assertEqual(json.load(fh)["version"], "garbage")


if __name__ == "__main__":
    unittest.main()
