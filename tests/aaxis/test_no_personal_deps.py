import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERN = re.compile(r"/opt/projects/cc|(?<![\w-])tab-[a-z][a-z-]*|\.claude/commands")


class NoPersonalDependenciesTest(unittest.TestCase):
    def test_no_reference_to_cc_repo_or_tab_commands(self):
        files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.split("\n")
        hits = []
        for rel in files:
            if not rel or rel in ("CHANGELOG.md", "tests/aaxis/test_no_personal_deps.py") or rel.startswith("oro-atlas/eval/"):
                continue
            try:
                text = (ROOT / rel).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            hits += ["%s: %s" % (rel, m.group(0)) for m in PATTERN.finditer(text)]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
