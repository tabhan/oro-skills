import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = os.path.join(ROOT, "scripts", "local-env")
FIX = os.path.join(ROOT, "tests", "fixtures")
GOLDEN = os.path.join(os.path.dirname(__file__), "golden")

ENV_APP = "ORO_REDIS_URL=redis://127.0.0.1:6379\nORO_SEARCH_URL=orm:\nORO_MONGODB_SERVER=mongodb://127.0.0.1:27017\n"
ENV_LOCAL = """PROJECT_NAME=demo
NODE_VERSION=24.11.0
POSTGRES_USER=pguser
POSTGRES_PASSWORD=pgpass
RABBITMQ_DEFAULT_USER=mq
RABBITMQ_DEFAULT_PASS=mqpass
ORO_DB_URL=postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/oro?sslmode=disable&charset=utf8&serverVersion=17.6
ORO_SEARCH_URL=elastic-search://127.0.0.1:9200
SONAR_TOKEN=keepme
COMPOSE_PROFILES=dummy-profile
ORO_MONGODB_SERVER=mongodb://127.0.0.1:34043
"""
COMPOSE = "services:\n  rabbitmq:\n    image: oroinc/rabbitmq:4.2.5-alpine\n"


def read(path):
    with open(path) as fh:
        return fh.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


class RenderBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.project = os.path.join(self.tmp, "proj")
        self.nginx = os.path.join(self.tmp, "nginx")
        os.makedirs(self.nginx)
        write(os.path.join(self.project, ".nvmrc"), "24\n")
        write(os.path.join(self.project, ".env-app"), ENV_APP)
        write(os.path.join(self.project, ".env-app.local"), ENV_LOCAL)
        write(os.path.join(self.project, ".env-app.e2e.local"), "ORO_ENV=e2e\n")
        write(os.path.join(self.project, "docker-compose.yml"), COMPOSE)
        env_yml = read(os.path.join(FIX, "env-ok.yml")).replace("workers_source: auto", "workers_source: user")
        write(os.path.join(self.project, ".oro-ai", "local-env", "env.yml"), env_yml)
        subprocess.run(["git", "init", "-q", self.project], check=True)
        self.env = dict(os.environ, LE_NGINX_DIR=self.nginx, LE_SUPERVISOR_DIR=self.nginx)
        self.env.pop("CLAUDECODE", None)

    def run_script(self, name, *args):
        return subprocess.run([os.path.join(SCRIPTS, name), "--project", self.project, *args], capture_output=True, text=True, env=self.env)

    def golden(self, name):
        return read(os.path.join(GOLDEN, name)).replace("@PROJECT@", self.project)

    def installed_nginx(self):
        shutil.copy(os.path.join(self.project, ".oro-ai", "local-env", "rendered", "nginx-test.conf"), os.path.join(self.nginx, "e2e.example.test.conf"))


class Render(RenderBase):
    def test_setup_renders_golden_files_and_is_idempotent(self):
        p = self.run_script("setup.sh", "--non-interactive")
        self.assertEqual(p.returncode, 10, p.stdout + p.stderr)
        self.assertIn("SUDO-NEEDED: sudo cp", p.stdout)
        for name, rel in (("docker-compose.override.yml", "docker-compose.override.yml"), ("env-app.local", ".env-app.local"),
                          ("env-app.behat_test.local", ".env-app.behat_test.local"), ("env-app.test.local", ".env-app.test.local"),
                          ("nginx-test.conf", ".oro-ai/local-env/rendered/nginx-test.conf")):
            self.assertEqual(read(os.path.join(self.project, rel)), self.golden(name), rel)
        self.assertFalse(os.path.exists(os.path.join(self.project, ".env-app.e2e.local")))
        self.assertEqual(read(os.path.join(self.project, "src/Aaxis/Bundle/AppBundle/.gitignore")), "*\n")
        self.installed_nginx()
        before = {}
        for rel in (".env-app.local", ".env-app.test.local", "docker-compose.override.yml"):
            before[rel] = read(os.path.join(self.project, rel))
        p = self.run_script("setup.sh", "--non-interactive")
        self.assertIn("0 written", p.stdout)
        self.assertNotIn("SUDO-NEEDED: sudo cp", p.stdout)
        for rel, text in before.items():
            self.assertEqual(read(os.path.join(self.project, rel)), text)
        self.assertEqual(self.run_script("render.sh", "--check").returncode, 0)

    def test_dotenv_files_differ_only_in_env_specific_lines(self):
        self.run_script("render.sh")
        a = set(read(os.path.join(self.project, ".env-app.behat_test.local")).splitlines())
        b = set(read(os.path.join(self.project, ".env-app.test.local")).splitlines())
        self.assertEqual({l.split("=")[0] for l in a ^ b if "=" in l},
                         {"ORO_ENV", "ORO_DEBUG", "ORO_MQ_DSN", "ORO_SESSION_DSN", "ORO_ADMIN_USERNAME", "ORO_ADMIN_PASSWORD",
                          "ORO_TEST_INSTALL_ORGANIZATION_NAME", "ORO_TEST_INSTALL_USER_EMAIL", "ORO_TEST_INSTALL_APPLICATION_URL",
                          "ORO_TEST_INSTALL_LANGUAGE"})
        for text in (a, b):
            self.assertFalse([l for l in text if "REDIS_CACHE" in l or "REDIS_DOCTRINE" in l or "REDIS_LAYOUT" in l])

    def test_merge_keeps_unmanaged_lines(self):
        self.run_script("render.sh")
        text = read(os.path.join(self.project, ".env-app.local"))
        self.assertIn("SONAR_TOKEN=keepme", text)
        self.assertNotIn("NODE_VERSION", text)
        self.assertNotIn("COMPOSE_PROFILES", text)
        self.assertIn("ORO_MONGODB_SERVER=mongodb://127.0.0.1:27017", text)

    def test_check_names_a_removed_line(self):
        self.run_script("render.sh")
        self.installed_nginx()
        path = os.path.join(self.project, ".env-app.test.local")
        write(path, "".join(l for l in read(path).splitlines(True) if not l.startswith("ORO_SEARCH_ENGINE_DSN")))
        p = self.run_script("render.sh", "--check")
        self.assertEqual(p.returncode, 2)
        self.assertIn(".env-app.test.local: differs", p.stdout)
        c = self.run_script("check.sh")
        self.assertIn("DRIFT template: .env-app.test.local", c.stdout)
        self.assertEqual(c.returncode, 2)

    def test_diff_and_dry_run_change_nothing(self):
        p = self.run_script("render.sh", "--diff")
        self.assertIn("+++ b/docker-compose.override.yml", p.stdout)
        p = self.run_script("render.sh", "--dry-run")
        self.assertIn("would: ", p.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.project, "docker-compose.override.yml")))
        self.assertTrue(os.path.exists(os.path.join(self.project, ".env-app.e2e.local")))

    def test_backup_before_overwrite_and_exclude(self):
        write(os.path.join(self.project, "docker-compose.override.yml"), "old: 1\n")
        self.run_script("render.sh")
        backups = os.listdir(os.path.join(self.project, "var", "backups", "oro-local-env"))
        self.assertTrue([b for b in backups if b.startswith("docker-compose.override.yml.")])
        exclude = read(os.path.join(self.project, ".git", "info", "exclude"))
        self.assertIn("/docker-compose.override.yml", exclude)
        self.assertNotIn("gitignore", os.listdir(self.project))

    def test_setup_asks_for_missing_values_and_accepts_set(self):
        shutil.rmtree(os.path.join(self.project, ".oro-ai"))
        p = self.run_script("setup.sh", "--non-interactive")
        self.assertEqual(p.returncode, 64, p.stdout + p.stderr)
        for key in ("local.domain", "local.tls_cert", "local_test.domain", "project_namespace"):
            self.assertIn("ask: %s" % key, p.stdout)
        sets = []
        for kv in ("local.domain=a.test", "local.tls_cert=/c", "local.tls_key=/k", "local_test.domain=b.test", "local_test.tls_cert=/c",
                   "local_test.tls_key=/k", "project_namespace=Demo", "local_test.workers=2", "local_test.workers_source=user"):
            sets += ["--set", kv]
        p = self.run_script("setup.sh", "--non-interactive", *sets)
        self.assertEqual(p.returncode, 10, p.stdout + p.stderr)
        self.assertIn("server_name b.test;", read(os.path.join(self.project, ".oro-ai/local-env/rendered/nginx-test.conf")))

    def test_supervisor_program_is_optional(self):
        self.run_script("render.sh")
        self.assertFalse(os.path.exists(os.path.join(self.project, ".oro-ai/local-env/rendered/supervisor-mc_test.conf")))
        self.run_script("setup.sh", "--non-interactive", "--set", "local_test.supervisor_consumer=true")
        text = read(os.path.join(self.project, ".oro-ai/local-env/rendered/supervisor-mc_test.conf"))
        self.assertIn("autostart=false", text)
        self.assertIn("--env=behat_test", text)

    def test_existing_poc_bundle_is_not_overwritten(self):
        bundle = os.path.join(self.project, "src/Aaxis/Bundle/AppBundle/AaxisAppBundle.php")
        write(bundle, "<?php // mine\n")
        self.run_script("render.sh")
        self.assertEqual(read(bundle), "<?php // mine\n")
        self.assertEqual(read(os.path.join(os.path.dirname(bundle), ".gitignore")), "*\n")


if __name__ == "__main__":
    unittest.main()
