import os
import re
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(ATLAS_DIR)


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
            self.assertTrue(os.path.isfile(home + "/bin/aaxis-oro"))
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


class PromptGateTest(unittest.TestCase):
    def test_gate_agent_resolves_cli_and_degrades(self):
        text = read(ATLAS_DIR + "/agents/architect-gate.md")
        for step in ("command -v aaxis-oro", "$ORO_SKILLS_DIR/bin/aaxis-oro", "${CLAUDE_PLUGIN_ROOT}/bin/aaxis-oro"):
            self.assertIn(step, text)
        self.assertIn("atlas unavailable", text)


class OwnedAgentTest(unittest.TestCase):
    def test_reviewer_agent_resolves_cli_and_degrades(self):
        text = read(ATLAS_DIR + "/agents/aaxis-reviewer.md")
        for step in ("command -v aaxis-oro", "$ORO_SKILLS_DIR/bin/aaxis-oro", "${CLAUDE_PLUGIN_ROOT}/bin/aaxis-oro"):
            self.assertIn(step, text)
        self.assertIn("atlas unavailable", text)


if __name__ == "__main__":
    unittest.main()
