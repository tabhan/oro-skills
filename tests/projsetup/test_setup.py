import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BIN = os.path.join(ROOT, "bin", "aaxis-oro")
HAND = """# Proj

## Key Rules

- **NEVER** edit vendor/.
- `.oro-ai/` is fully tracked in git.
  Continuation line.

Plain paragraph rule.
"""
IMPORTS = "@CLAUDE_base.md\n@CLAUDE_project.md\n\n<!-- claude-notes -->\nmine\n<!-- /claude-notes -->\n"


def run(*args, cwd):
    env = dict(os.environ, HOME=cwd)
    p = subprocess.run([sys.executable, BIN, "setup"] + list(args) + ["--project", cwd], capture_output=True, text=True, env=env)
    return p.returncode, p.stdout + p.stderr


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        subprocess.run(["git", "init", "-q", self.d], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, rel, text):
        p = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(text)

    def test_sync_idempotent(self):
        code, out = run("sync", cwd=self.d)
        self.assertEqual(code, 0)
        self.assertIn("CLAUDE_project.md: created", out)
        self.assertEqual(open(os.path.join(self.d, ".oro-ai", ".gitignore")).read(), "*\n!.gitignore\n!config.json\n")
        self.assertEqual(json.load(open(os.path.join(self.d, ".oro-ai", "config.json")))["spec"]["id-pattern"], "[A-Z][A-Z0-9-]*:AC-[0-9]+")
        before = open(os.path.join(self.d, "CLAUDE_project.md")).read()
        self.assertIn("aaxis-oro:review-rules:start", before)
        self.assertIn("aaxis-oro:plan-rules:start", before)
        self.assertIn("aaxis-oro:process-rules:start", before)
        self.assertIn("override any command's", before)
        code, out = run("sync", cwd=self.d)
        self.assertIn("CLAUDE_project.md: unchanged", out)
        self.assertEqual(before, open(os.path.join(self.d, "CLAUDE_project.md")).read())

    def test_sync_updates_stale_block_keeps_user_text(self):
        run("sync", cwd=self.d)
        p = os.path.join(self.d, "CLAUDE_project.md")
        t = open(p).read().replace("Review rules", "Old rules") + "\nUser text\n"
        open(p, "w").write(t)
        run("sync", cwd=self.d)
        new = open(p).read()
        self.assertIn("## Review rules", new)
        self.assertIn("User text", new)
        self.assertEqual(new.count("aaxis-oro:review-rules:start"), 1)

    def test_sync_adds_process_block_to_project_set_up_before_it(self):
        run("sync", cwd=self.d)
        pm = os.path.join(self.d, "CLAUDE_project.md")
        text = open(pm).read()
        old = re.sub(r"<!-- aaxis-oro:process-rules:start -->.*?<!-- aaxis-oro:process-rules:end -->\n?", "", text, flags=re.S)
        self.put("CLAUDE_project.md", old)
        code, out = run("status", cwd=self.d)
        self.assertIn("blocks out of sync: process-rules", out)
        run("sync", cwd=self.d)
        self.assertEqual(open(pm).read().count("aaxis-oro:process-rules:start"), 1)

    def test_tracked_oro_ai_blocks_gitignore(self):
        self.put(".oro-ai/task/X/plan.md", "x")
        subprocess.run(["git", "-C", self.d, "add", "-A"], check=True)
        code, out = run("sync", cwd=self.d)
        self.assertIn("NOT created", out)
        self.assertIn("git rm -r --cached -q .oro-ai", out)
        self.assertFalse(os.path.exists(os.path.join(self.d, ".oro-ai", ".gitignore")))

    def test_rules_triage_roundtrip(self):
        self.put("CLAUDE.md", HAND)
        code, out = run("rules", cwd=self.d)
        self.assertIn("3 rules", out)
        self.assertEqual(open(os.path.join(self.d, ".oro-ai/setup/CLAUDE.original.md")).read(), HAND)
        self.put("CLAUDE.md", IMPORTS)  # as after foundation --force
        self.put("plan.json", json.dumps({"items": [{"id": 1, "action": "drop"}, {"id": 2, "action": "move"}, {"id": 3, "action": "keep"}]}))
        code, out = run("apply-rules", "--plan", os.path.join(self.d, "plan.json"), cwd=self.d)
        self.assertEqual(code, 0, out)
        self.assertIn("1 moved", out)
        pm = open(os.path.join(self.d, "CLAUDE_project.md")).read()
        self.assertIn("fully tracked", pm)
        self.assertNotIn("NEVER", pm)
        self.assertIn("Plain paragraph rule.", open(os.path.join(self.d, "CLAUDE.md")).read())
        run("apply-rules", "--plan", os.path.join(self.d, "plan.json"), cwd=self.d)
        self.assertEqual(open(os.path.join(self.d, "CLAUDE_project.md")).read().count("aaxis-oro:migrated-rules:start"), 1)

    def _triage(self):
        self.put("CLAUDE.md", HAND)
        run("rules", cwd=self.d)
        self.put("CLAUDE.md", IMPORTS)

    def test_keep_inside_sentinels_survives_force_rebuild(self):
        self._triage()
        self.put("plan.json", json.dumps({"items": [{"id": 1, "action": "drop"}, {"id": 2, "action": "move"}, {"id": 3, "action": "keep"}]}))
        run("apply-rules", "--plan", os.path.join(self.d, "plan.json"), cwd=self.d)
        text = open(os.path.join(self.d, "CLAUDE.md")).read()
        a, b = text.index("<!-- claude-notes -->"), text.index("<!-- /claude-notes -->")
        self.assertIn("Plain paragraph rule.", text[a:b])
        self.assertIn("## Key Rules", open(os.path.join(self.d, "CLAUDE_project.md")).read())
        # foundation --force keeps exactly the text between the sentinels
        lifted = text[a:b + len("<!-- /claude-notes -->")]
        rebuilt = "@CLAUDE_base.md\n\n" + lifted + "\n"
        self.assertIn("Plain paragraph rule.", rebuilt)

    def test_status_flags_pending_triage_until_applied(self):
        self._triage()
        code, out = run("status", cwd=self.d)
        self.assertIn("triage pending", out)
        code, out = run("rules", cwd=self.d)
        self.assertIn("triage pending", out)
        self.put("plan.json", json.dumps({"items": [{"id": i, "action": "keep"} for i in (1, 2, 3)]}))
        run("apply-rules", "--plan", os.path.join(self.d, "plan.json"), cwd=self.d)
        code, out = run("status", cwd=self.d)
        self.assertNotIn("triage pending", out)

    def test_apply_rejects_duplicate_ids(self):
        self._triage()
        self.put("plan.json", json.dumps({"items": [{"id": 1, "action": "keep"}, {"id": 1, "action": "drop"}, {"id": 2, "action": "keep"}, {"id": 3, "action": "keep"}]}))
        code, out = run("apply-rules", "--plan", os.path.join(self.d, "plan.json"), cwd=self.d)
        self.assertEqual(code, 64)
        self.assertIn("duplicate [1]", out)

    def test_dry_run_prints_text(self):
        self._triage()
        self.put("plan.json", json.dumps({"items": [{"id": 1, "action": "drop"}, {"id": 2, "action": "move"}, {"id": 3, "action": "keep"}]}))
        code, out = run("apply-rules", "--dry-run", "--plan", os.path.join(self.d, "plan.json"), cwd=self.d)
        self.assertIn("## Key Rules", out)
        self.assertFalse(os.path.exists(os.path.join(self.d, "CLAUDE_project.md")))

    def test_apply_rejects_incomplete_plan(self):
        self.put("CLAUDE.md", HAND)
        run("rules", cwd=self.d)
        self.put("CLAUDE.md", IMPORTS)
        self.put("plan.json", json.dumps({"items": [{"id": 1, "action": "move"}]}))
        code, _ = run("apply-rules", "--plan", os.path.join(self.d, "plan.json"), cwd=self.d)
        self.assertEqual(code, 64)

    def test_status_exit_codes(self):
        self.put("CLAUDE.md", HAND)
        code, out = run("status", cwd=self.d)
        self.assertEqual(code, 2)
        self.assertIn("handwritten", out)


if __name__ == "__main__":
    unittest.main()
