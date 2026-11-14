import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))

import posttooluse_bash as pb  # noqa: E402


class ReadOnlyCommandTest(unittest.TestCase):
    def test_read_only_lines_skip_the_post_hoc_diff(self):
        for cmd in ("ls -la src", "git status && git log -3", "grep -r foo src | head", "aaxis-oro atlas event foo",
                    "cd /x && cat a.yml"):
            self.assertTrue(pb.read_only(cmd), cmd)

    def test_anything_that_can_write_keeps_the_diff(self):
        for cmd in ("sed -i s/a/b/ f.yml", "echo x > f", "cat a | tee b", "ls; rm x", "php bin/console cache:clear",
                    "git diff --output=x", "grep a f $(touch z)", "find . -exec rm {} +", "", "python3 w.py"):
            self.assertFalse(pb.read_only(cmd), cmd)


if __name__ == "__main__":
    unittest.main()
