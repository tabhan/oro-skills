import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_PY = os.path.join(ROOT, "scripts", "local-env", "lib", "env.py")
FIX = os.path.join(ROOT, "tests", "fixtures")
sys.path.insert(0, os.path.dirname(ENV_PY))
import env  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, ENV_PY, *args], capture_output=True, text=True)


class ValidateTest(unittest.TestCase):
    def test_ok(self):
        p = run("validate", os.path.join(FIX, "env-ok.yml"))
        self.assertEqual((p.returncode, p.stderr), (0, ""))

    def test_bad_prefix(self):
        p = run("validate", os.path.join(FIX, "env-bad-prefix.yml"))
        self.assertEqual(p.returncode, 1)
        self.assertIn("prefix must start with oro_test", p.stderr)

    def test_schema_errors(self):
        data = env.load(os.path.join(FIX, "env-ok.yml"))
        data["local_test"]["redis_dbs"] = ["x"]
        data["local_test"]["workers_source"] = "magic"
        del data["project"]
        errs = "\n".join(env.validate(data))
        self.assertIn("redis_dbs[0]", errs)
        self.assertIn("workers_source", errs)
        self.assertIn("missing required key 'project'", errs)

    def test_same_db_rejected(self):
        data = env.load(os.path.join(FIX, "env-ok.yml"))
        data["local"]["db"] = "oro_test"
        self.assertTrue(any("must differ" in e for e in env.validate(data)))

    def test_missing_domains_are_asks_not_errors(self):
        data = env.with_defaults({"project": "demo"})
        self.assertEqual(env.validate(data), [])
        self.assertIn("local_test.domain", env.missing_asks(data))
        self.assertNotIn("domain", str(env.DEFAULTS))


class MigrateTest(unittest.TestCase):
    def setUp(self):
        self.proj = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.proj, True)
        os.makedirs(os.path.dirname(env.old_path(self.proj)))
        shutil.copy(os.path.join(FIX, "env-legacy.yml"), env.old_path(self.proj))

    def test_moves_converts_and_is_idempotent(self):
        p = run("migrate", "--project", self.proj)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(os.path.exists(env.old_path(self.proj)))
        data = env.load(env.new_path(self.proj))
        self.assertEqual(data["local_test"]["baseline_key"], "abc123")
        self.assertEqual(data["local_test"]["es_prefix"], "oro_test_")
        self.assertEqual(data["local"]["domain"], "local.example.test")
        self.assertEqual(env.validate(data), [])
        before = open(env.new_path(self.proj)).read()
        self.assertEqual(run("migrate", "--project", self.proj).returncode, 0)
        self.assertEqual(open(env.new_path(self.proj)).read(), before)

    def test_conflict_exit_2(self):
        os.makedirs(os.path.dirname(env.new_path(self.proj)))
        with open(env.new_path(self.proj), "w") as fh:
            fh.write("project: other\n")
        p = run("migrate", "--project", self.proj)
        self.assertEqual(p.returncode, 2)
        self.assertTrue(os.path.exists(env.old_path(self.proj)))

    def test_identical_both_files_cleans_old(self):
        run("migrate", "--project", self.proj)
        os.makedirs(os.path.dirname(env.old_path(self.proj)))
        shutil.copy(os.path.join(FIX, "env-legacy.yml"), env.old_path(self.proj))
        self.assertEqual(run("migrate", "--project", self.proj).returncode, 0)
        self.assertFalse(os.path.exists(env.old_path(self.proj)))

    def test_get(self):
        run("migrate", "--project", self.proj)
        p = run("get", "--project", self.proj, "local_test.redis_dbs")
        self.assertEqual(p.stdout.strip(), "4,5,6,7")


if __name__ == "__main__":
    unittest.main()
