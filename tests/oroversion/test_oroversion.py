import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from oroversion import Constraint, ConstraintError, detect, parse_version  # noqa: E402

CLI = os.path.join(ROOT, "bin", "aaxis-oro")


def project(fixture):
    d = tempfile.mkdtemp()
    if fixture:
        shutil.copy(os.path.join(HERE, "fixtures", fixture + ".lock.json"), os.path.join(d, "composer.lock"))
    return d


class ConstraintTest(unittest.TestCase):
    def check(self, rng, yes=(), no=()):
        c = Constraint(rng)
        for v in yes:
            self.assertTrue(c.matches(v), "%s should match %s" % (rng, v))
        for v in no:
            self.assertFalse(c.matches(v), "%s should not match %s" % (rng, v))

    def test_default_when_missing(self):
        self.check(None, yes=["7.0.0", "8.1.2"], no=["6.1.9"])

    def test_patch_granularity(self):
        self.check(">=7.0.5", yes=["7.0.5", "7.0.6", "8.0.0"], no=["7.0.4"])
        self.check(">=7.0.0 <7.0.5", yes=["7.0.0", "7.0.4"], no=["7.0.5", "6.9.9"])

    def test_caret_tilde(self):
        self.check("^7.0", yes=["7.0.0", "7.9.9"], no=["8.0.0", "6.9.9"])
        self.check("~7.0.5", yes=["7.0.5", "7.0.9"], no=["7.1.0", "7.0.4"])
        self.check("~7.0", yes=["7.5.0"], no=["8.0.0"])
        self.check("^0.3.1", yes=["0.3.5"], no=["0.4.0"])

    def test_or_and_comma(self):
        self.check("^6.1 || >=7.0.5", yes=["6.1.2", "7.0.5", "8.0.0"], no=["7.0.4", "6.0.0"])
        self.check(">=7.0, <8.0", yes=["7.2.0"], no=["8.0.0"])

    def test_wildcard_and_bare(self):
        self.check("7.0.*", yes=["7.0.3"], no=["7.1.0"])
        self.check("7.0.5", yes=["7.0.5"], no=["7.0.6"])

    def test_prerelease_below_release(self):
        self.check(">=8.0.0", yes=["8.0.0"], no=["8.0.0-beta1"])

    def test_prerelease_belongs_to_its_major(self):
        self.check("^8.0", yes=["8.0.0-beta1", "8.0.0-rc2", "8.1.0"], no=["9.0.0-beta1", "7.9.0"])
        self.check("^7.0", yes=["7.0.5"], no=["8.0.0-beta1"])
        self.check(">=7.0.0 <8.0.0", no=["8.0.0-beta1"])
        self.check("<8.0.0", no=["8.0.0-beta1"], yes=["7.9.9"])
        self.check("8.0.*", yes=["8.0.0-beta1"])

    def test_prerelease_in_constraints(self):
        self.check(">=8.0.0-beta", yes=["8.0.0-beta1", "8.0.0", "8.0.0-rc1"], no=["8.0.0-alpha1"])
        self.check(">=8.0.0-beta1 <8.0.0-rc1", yes=["8.0.0-beta2"], no=["8.0.0-rc1"])
        with self.assertRaises(ConstraintError):
            Constraint("^8.0.0-beta")

    def test_or_keyword(self):
        self.check("^7.0 or ^8.0", yes=["7.1.0", "8.0.0-beta1"], no=["6.1.0", "9.0.0"])

    def test_unparsable(self):
        for bad in ("abc", ">=", "^", "7.0.5 ||", ">=7.0.5 <<"):
            with self.assertRaises(ConstraintError, msg=bad):
                Constraint(bad)

    def test_version_ordering(self):
        self.assertTrue(parse_version("7.0.10") > parse_version("7.0.9"))


class DetectTest(unittest.TestCase):
    def test_705(self):
        r = detect(project("lock-705"))
        self.assertEqual((str(r.version), r.source_pkg), ("7.0.5", "oro/platform"))
        self.assertEqual(r.warnings, [])

    def test_beta(self):
        r = detect(project("lock-800beta"))
        self.assertEqual(str(r.version), "8.0.0-beta1")

    def test_mismatch_warns(self):
        r = detect(project("lock-mismatch"))
        self.assertTrue(r.known)
        self.assertTrue(any("disagree" in w for w in r.warnings))

    def test_dev_master_unknown(self):
        r = detect(project("lock-devmaster"))
        self.assertFalse(r.known)

    def test_dev_branch_warns(self):
        r = detect(project("lock-devbranch"))
        self.assertEqual(str(r.version), "7.0.0")
        self.assertTrue(r.warnings)

    def test_no_oro_and_no_lock(self):
        self.assertFalse(detect(project("lock-nooro")).known)
        self.assertFalse(detect(project(None)).known)

    def test_fallback_package(self):
        r = detect(project("lock-fallback"))
        self.assertEqual((str(r.version), r.source_pkg), ("6.1.2", "oro/crm"))

    def test_cache_and_redetect(self):
        d = project("lock-705")
        r = detect(d)
        self.assertFalse(r.cached)
        cache = os.path.join(d, ".oro-ai", "version.json")
        with open(cache) as fh:
            data = json.load(fh)
        self.assertEqual(data["lock_sha256"], r.lock_sha256)
        self.assertEqual(sorted(data), ["lock_sha256", "source_pkg", "version", "warnings"])
        with open(cache) as fh:
            before = fh.read()
        os.utime(os.path.join(d, "composer.lock"))
        detect(d, use_cache=False)
        with open(cache) as fh:
            self.assertEqual(fh.read(), before)
        self.assertTrue(detect(d).cached)
        with open(os.path.join(d, "composer.lock"), "w") as fh:
            fh.write('{"packages":[{"name":"oro/platform","version":"7.0.6"}]}')
        r2 = detect(d)
        self.assertEqual((str(r2.version), r2.cached), ("7.0.6", False))
        with open(cache) as fh:
            self.assertNotEqual(json.load(fh)["lock_sha256"], data["lock_sha256"])


class CliTest(unittest.TestCase):
    def run_cli(self, d, *args):
        return subprocess.run([sys.executable, CLI, "version", "--project", d, *args], capture_output=True, text=True)

    def test_exit_codes(self):
        p = self.run_cli(project("lock-705"))
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "7.0.5"))
        self.assertEqual(self.run_cli(project("lock-devmaster")).returncode, 4)
        self.assertEqual(self.run_cli(project(None)).returncode, 4)
        self.assertEqual(self.run_cli(project("lock-705"), "--bogus").returncode, 64)

    def test_json(self):
        data = json.loads(self.run_cli(project("lock-705"), "--json").stdout)
        self.assertEqual(data["version"], "7.0.5")


if __name__ == "__main__":
    unittest.main()
