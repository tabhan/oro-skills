import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from atlas import index  # noqa: E402


class OroVersionStampTest(unittest.TestCase):
    def project(self, version):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "composer.lock"), "w") as fh:
            fh.write('{"packages":[{"name":"oro/platform","version":"%s"}]}' % version)
        return d

    def test_normalised_detected_version(self):
        self.assertEqual(index.detected_version(self.project("v7.0.5")), "7.0.5")

    def test_dev_branch_is_normalised_not_copied(self):
        d = self.project("7.0.x-dev")
        self.assertEqual(index.platform_version(d), "7.0.x-dev")
        self.assertEqual(index.detected_version(d), "7.0.0")

    def test_no_cache_file_written(self):
        d = self.project("7.0.5")
        index.detected_version(d)
        self.assertFalse(os.path.exists(os.path.join(d, ".oro-ai")))


if __name__ == "__main__":
    unittest.main()
