import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BIN = os.path.join(ROOT, "bin", "aaxis-oro")
sys.path.insert(0, os.path.join(ROOT, "lib"))
from projsetup.plugins import PLUGIN_KEYS, REL  # noqa: E402


def run(d):
    env = dict(os.environ, HOME=d)
    p = subprocess.run([sys.executable, BIN, "setup", "sync", "--project", d], capture_output=True, text=True, env=env)
    return p.returncode, p.stdout + p.stderr


class PluginsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        subprocess.run(["git", "init", "-q", self.d], check=True)
        self.put("composer.lock", "{}")
        self.put("bin/console", "")
        self.path = os.path.join(self.d, REL)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, rel, text):
        p = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(text)

    def load(self):
        return json.load(open(self.path))

    def exclude(self):
        return open(os.path.join(self.d, ".git", "info", "exclude")).read()

    def test_creates_file(self):
        code, out = run(self.d)
        self.assertEqual(code, 0)
        self.assertIn("enabled 7 plugins", out)
        self.assertEqual(self.load(), {"enabledPlugins": {k: True for k in PLUGIN_KEYS}})
        raw = open(self.path).read()
        self.assertTrue(raw.endswith("}\n"))
        self.assertIn('\n  "enabledPlugins"', raw)

    def test_merge_preserves_content(self):
        self.put(REL, json.dumps({"permissions": {"allow": ["Bash(ls)"]}, "enabledPlugins": {"other@x": True, PLUGIN_KEYS[0]: True}}))
        run(self.d)
        data = self.load()
        self.assertEqual(data["permissions"], {"allow": ["Bash(ls)"]})
        self.assertTrue(data["enabledPlugins"]["other@x"])
        for k in PLUGIN_KEYS:
            self.assertTrue(data["enabledPlugins"][k])

    def test_explicit_false_preserved_with_warning(self):
        self.put(REL, json.dumps({"enabledPlugins": {PLUGIN_KEYS[1]: False}}))
        _, out = run(self.d)
        self.assertIn("warning: %s is false" % PLUGIN_KEYS[1], out)
        data = self.load()["enabledPlugins"]
        self.assertIs(data[PLUGIN_KEYS[1]], False)
        self.assertIs(data[PLUGIN_KEYS[0]], True)

    def test_invalid_json_untouched(self):
        self.put(REL, "{nope")
        _, out = run(self.d)
        self.assertIn("not valid JSON", out)
        self.assertEqual(open(self.path).read(), "{nope")

    def test_exclude_added_only_when_needed(self):
        run(self.d)
        self.assertEqual(self.exclude().count(".claude/settings.local.json"), 1)
        run(self.d)
        self.assertEqual(self.exclude().count(".claude/settings.local.json"), 1)

    def test_already_ignored_not_appended(self):
        self.put(".gitignore", ".claude/settings.local.json\n")
        _, out = run(self.d)
        self.assertNotIn("info/exclude", out)
        self.assertNotIn(".claude/settings.local.json", self.exclude())

    def test_idempotent(self):
        run(self.d)
        before = open(self.path).read()
        _, out = run(self.d)
        self.assertIn("plugins unchanged", out)
        self.assertEqual(before, open(self.path).read())

    def test_not_a_git_repo_skips_exclude(self):
        subprocess.run(["rm", "-rf", os.path.join(self.d, ".git")], check=True)
        code, _ = run(self.d)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(self.path))

    def test_non_oro_dir_refused(self):
        with tempfile.TemporaryDirectory() as other:
            code, _ = run(other)
            self.assertNotEqual(code, 0)
            self.assertFalse(os.path.exists(os.path.join(other, REL)))


if __name__ == "__main__":
    unittest.main()
