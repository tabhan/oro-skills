import hashlib
import json
import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TPL = os.path.join(ROOT, "templates", "claude-project")
RATIONALE = os.path.join(ROOT, "solutions", "references", "process-rules-rationale.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class RuleTemplatesTest(unittest.TestCase):
    def test_every_numbered_rule_survives_the_trim(self):
        process, review = read(os.path.join(TPL, "process-rules.md")), read(os.path.join(TPL, "review-rules.md"))
        self.assertEqual(re.findall(r"^(\d)\. ", process, re.M), list("1234567"))
        self.assertEqual(re.findall(r"^(\d)\. ", review, re.M), list("1234567"))

    def test_enforcement_facts_stay_in_the_synced_block(self):
        process = read(os.path.join(TPL, "process-rules.md"))
        for needle in ("aaxis-oro task init", "architect-gate.md", "seen red", "task check", "review check", "git push",
                       "covers HEAD", "Stop hook", "Verdict: skipped", "## Root cause", "three failed fix attempts",
                       "Never weaken,", "Deploy notes"):
            self.assertIn(needle, process)
        review = read(os.path.join(TPL, "review-rules.md"))
        for needle in ("aaxis_aspect.interceptor", "atlas unsafe", "entity_extend.yml", "AbstractSetEntityConfigs",
                       "src/Aaxis/", "AppBundle/", "Gaufrette", "rules 2, 5, 6 and 7"):
            self.assertIn(needle, review)

    def test_rationale_reference_exists_and_blocks_point_to_it(self):
        text = read(RATIONALE)
        for needle in ("code / test / data / environment / config / upstream", "prevents reinventing an OOTB hook", "prevents leaking spike code"):
            self.assertIn(needle, text)
        for name in ("process-rules.md", "review-rules.md"):
            self.assertIn("process-rules-rationale.md", read(os.path.join(TPL, name)))
        self.assertIn("process-rules-rationale.md", read(os.path.join(ROOT, "solutions", "SKILL.md")))


class RuleInventoryTest(unittest.TestCase):
    """Regression guard for the trimmed blocks: nothing enforceable may be lost, only moved to the rationale reference."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(os.path.dirname(__file__), "rule_inventory.json"), encoding="utf-8") as fh:
            cls.inv = json.load(fh)
        cls.blocks = {n: read(os.path.join(TPL, n + ".md")) for n in ("process-rules", "review-rules", "plan-rules")}

    @staticmethod
    def flat(text):
        return re.sub(r"\s+", " ", text)

    def test_every_command_token_of_the_old_blocks_is_still_present(self):
        have = self.flat("".join(self.blocks.values()) + read(RATIONALE))
        missing = [t for t in self.inv["tokens"] if t not in have]
        self.assertEqual(missing, [])

    def test_enforcement_tokens_stay_in_the_synced_blocks_not_only_the_rationale(self):
        have = self.flat("".join(self.blocks.values()))
        for t in self.inv["tokens"]:
            if t.startswith(("aaxis-oro ", "/aaxis-oro:", ".oro-ai/", "Verdict:", "Range:", "Resources/config", "ORO_")):
                self.assertIn(t, have, t)

    def test_key_phrases_of_the_non_standard_practices_remain(self):
        have = self.flat("".join(self.blocks.values())).lower()
        self.assertEqual([p for p in self.inv["phrases"] if p.lower() not in have], [])

    def test_blocks_are_byte_stable(self):
        for name, text in self.blocks.items():
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            self.assertEqual(digest, self.inv["sha256"][name], "%s changed: %s" % (name, self.inv["sha256_note"]))


if __name__ == "__main__":
    unittest.main()
