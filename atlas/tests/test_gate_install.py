import os
import re
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(ATLAS_DIR)
PIPELINE = "/opt/projects/cc/commands/tab-pipeline.md"
REVIEW = "/opt/projects/cc/commands/tab-review.md"
ATLAS_BIN = "/opt/projects/oro-skills/bin/aaxis-oro"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text):
    return text.split("---\n")[1]


class InstallScriptTest(unittest.TestCase):
    def run_install(self, home, *args):
        env = dict(os.environ, CLAUDE_SKILLS_DIR=home + "/skills", CLAUDE_AGENTS_DIR=home + "/agents",
                   ORO_ATLAS_BIN_DIR=home + "/bin")
        return subprocess.run([REPO + "/install.sh", "--no-update", "--no-official-plugins", "--no-plugin", *args],
                              env=env, capture_output=True, text=True, check=True)

    def test_legacy_symlinks_removed_and_bins_linked(self):
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(home + "/skills")
            os.makedirs(home + "/agents")
            os.symlink(ATLAS_DIR, home + "/skills/oro-atlas")
            os.symlink(ATLAS_DIR + "/agents/architect-gate.md", home + "/agents/oro-architect-gate.md")
            self.run_install(home)
            self.assertEqual(os.listdir(home + "/skills") + os.listdir(home + "/agents"), [])
            self.assertTrue(os.path.islink(home + "/bin/aaxis-oro"))
            self.run_install(home, "--uninstall")
            self.assertEqual(os.listdir(home + "/bin"), [])


class SkillFrontmatterTest(unittest.TestCase):
    def test_description_within_listing_limit(self):
        fm = frontmatter(read(ATLAS_DIR + "/SKILL.md"))
        body = re.search(r"description: >-\n((?:  .*\n)+)", fm).group(1)
        description = " ".join(line.strip() for line in body.splitlines())
        self.assertLessEqual(len(description), 1536)
        self.assertNotIn("when_to_use", fm)

    def test_no_paths_filter_so_it_loads_at_design_time(self):
        self.assertNotIn("paths:", frontmatter(read(ATLAS_DIR + "/SKILL.md")))


@unittest.skipUnless(os.path.isfile(PIPELINE), "cc prompts not checked out")
class PromptGateTest(unittest.TestCase):
    def test_pipeline_gates_on_index_and_uses_absolute_cli(self):
        text = read(PIPELINE)
        self.assertIn("const USE_ATLAS = IS_ORO && HAS_ATLAS", text)
        self.assertIn("const ATLAS = `${ATLAS_BIN} --project ${REPO}`", text)
        self.assertNotIn(ATLAS_BIN + " --project", text)
        for step in ("command -v aaxis-oro", "$ORO_SKILLS_DIR/bin/aaxis-oro", ATLAS_BIN):
            self.assertIn(step, text)
        self.assertIn("ATLAS UNAVAILABLE", text)
        js = re.search(r"```js\n(.*?)```", text, re.S).group(1)
        self.assertNotIn("${IS_ORO ? `ATLAS GATE", js)
        self.assertIsNone(re.search(r"\\`atlas ", js), "bare atlas call in workflow JS")

    def test_pipeline_workflow_js_parses(self):
        js = re.search(r"```js\n(.*?)```", read(PIPELINE), re.S).group(1)
        js = js.replace("<true|false>", "true").replace("<resolved atlas path>", "/x/atlas").replace("export const meta", "const meta")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write("async function wf() {\n%s\n}\n" % js)
        try:
            subprocess.run(["node", "--check", fh.name], check=True, capture_output=True)
        finally:
            os.unlink(fh.name)

    def test_review_resolves_cli_and_status_gate(self):
        text = read(REVIEW)
        for step in ("command -v aaxis-oro", "$ORO_SKILLS_DIR/bin/aaxis-oro", ATLAS_BIN):
            self.assertIn(step, text)
        self.assertIn("atlas unavailable", text)

    def test_gate_agent_resolves_cli_and_degrades(self):
        text = read(ATLAS_DIR + "/agents/architect-gate.md")
        for step in ("command -v aaxis-oro", "$ORO_SKILLS_DIR/bin/aaxis-oro", ATLAS_BIN):
            self.assertIn(step, text)
        self.assertIn("atlas unavailable", text)


if __name__ == "__main__":
    unittest.main()
