import os
import re
import subprocess
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BUNDLES = ("AiIntegration Aspect CMS Cron Email EntityExtend Filter Integration Layout "
           "RabbitMQMonitor Redirect RestClient Security Test UI").split()
FORBIDDEN = re.compile("oro-" + "common|oro-" + "tools", re.I)


class CatalogueTest(unittest.TestCase):
    def test_every_bundle_listed(self):
        text = open(os.path.join(ROOT, "solutions", "references", "aaxis", "catalogue.md")).read()
        for b in BUNDLES:
            self.assertIn(b + "Bundle", text, b)

    def test_skill_has_install_prompt_and_gate_check(self):
        skill = open(os.path.join(ROOT, "solutions", "SKILL.md")).read()
        self.assertIn("hantab@aaxis.io", skill)
        gate = open(os.path.join(ROOT, "atlas", "agents", "oro-architect-gate.md")).read()
        self.assertIn("project_namespace", gate)
        self.assertIn("src/Aaxis/", gate)
        self.assertIn("AppBundle/", gate)
        self.assertIn("stateless", gate)
        self.assertNotIn("AppBundle", open(os.path.join(ROOT, "solutions", "references", "aaxis", "catalogue.md")).read())

    def test_no_forbidden_names_in_repo(self):
        hits = []
        for d, dirs, files in os.walk(ROOT):
            dirs[:] = [x for x in dirs if x not in (".git", "__pycache__")]
            for f in files:
                p = os.path.join(d, f)
                try:
                    if FORBIDDEN.search(open(p, errors="ignore").read()):
                        hits.append(os.path.relpath(p, ROOT))
                except OSError:
                    pass
        self.assertEqual([], [h for h in hits if not h.startswith("tests/aaxis/")])


if __name__ == "__main__":
    unittest.main()
