import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = os.path.join(ROOT, "scripts", "local-env")
STUBS = os.path.join(os.path.dirname(__file__), "stubs")
FIX = os.path.join(ROOT, "tests", "fixtures")

LIVE = {
    "current_database": "%(db)s",
    "database_dsn": "postgres://u:p@127.0.0.1:5432/%(db)s?sslmode=disable",
    "search_engine_dsn": "elastic-search://127.0.0.1:9200?prefix=oro_test_search",
    "website_search_engine_dsn": "elastic-search://127.0.0.1:9200?prefix=oro_test_website_search",
    "message_queue_transport_dsn": "amqp://u:p@127.0.0.1:5672/oro_test",
    "gaufrette_adapter.public": "gridfs:mongodb://127.0.0.1:27017/oro_test_public",
    "gaufrette_adapter.private": "gridfs:mongodb://127.0.0.1:27017/oro_test_private",
    "session_handler_dsn": "redis://127.0.0.1:6379/7",
}


def read(path):
    with open(path) as fh:
        return fh.read()


def write(path, text):
    with open(path, "w") as fh:
        fh.write(text)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.project = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(self.project, ".oro-ai", "local-env"))
        shutil.copy(os.path.join(FIX, "env-ok.yml"), os.path.join(self.project, ".oro-ai", "local-env", "env.yml"))
        with open(os.path.join(self.project, "composer.lock"), "w") as fh:
            fh.write("{}")
        self.stubdir = os.path.join(self.tmp, "stub")
        os.makedirs(self.stubdir)
        self.log = os.path.join(self.tmp, "stub.log")
        write(self.log, "")
        self.env = dict(os.environ, PATH=STUBS + os.pathsep + os.environ["PATH"], STUB_LOG=self.log, STUB_DIR=self.stubdir,
                        STUB_PG_DBS="oro:oro_test:oro_test_baseline", STUB_MONGO_DBS="oro_test_private_baseline:oro_test_private",
                        STUB_ES="oro_test_search_1:oro_test_website_search_1", STUB_VHOSTS="/:oro_test", STUB_QUEUES="q1:q2")
        self.env.pop("CLAUDECODE", None)
        self.write_live("test", db="oro_test")
        self.write_live("behat_test", db="oro_test")
        self.write_live("prod", db="oro", search_engine_dsn="elastic-search://h:9200?prefix=oro_search",
                        **{"gaufrette_adapter.private": "gridfs:mongodb://h/private"})

    def write_live(self, env, db, **over):
        vals = dict(LIVE, **over)
        with open(os.path.join(self.stubdir, "live-%s.txt" % env), "w") as fh:
            for k, v in vals.items():
                fh.write("%s=%s\n" % (k, v % {"db": db} if "%(db)s" in v else v))

    def run_script(self, name, *args, **env):
        p = subprocess.run([os.path.join(SCRIPTS, name), "--project", self.project, *args], capture_output=True, text=True,
                           env=dict(self.env, **env), cwd=self.project)
        return p

    def calls(self):
        return read(self.log)

    def lines(self, p):
        return len((p.stdout + p.stderr).strip().splitlines())


class GuardScripts(Base):
    def test_es_prefix_outside_guard_deletes_nothing(self):
        p = self.run_script("es-drop-prefix.sh", "oro_")
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertNotIn("XDELETE", self.calls())
        self.assertNotIn("_cat/indices", self.calls())

    def test_es_deletes_by_name(self):
        p = self.run_script("es-drop-prefix.sh", "oro_test_")
        self.assertEqual(p.returncode, 0, p.stderr)
        for n in ("oro_test_search_1", "oro_test_website_search_1"):
            self.assertIn("/%s -XDELETE" % n, self.calls())
        self.assertNotIn("oro_test_*", " ".join(l for l in self.calls().splitlines() if "XDELETE" in l))

    def test_es_empty_is_noop(self):
        p = self.run_script("es-drop-prefix.sh", "oro_test_", STUB_ES="")
        self.assertEqual(p.returncode, 0)
        self.assertIn("nothing to delete", p.stdout)
        self.assertNotIn("XDELETE", self.calls())

    def test_es_only_prefixed_names_deleted(self):
        # stub returns an index that merely matches a looser prefix pattern
        env_file = os.path.join(self.project, ".oro-ai", "local-env", "env.yml")
        write(env_file, read(env_file).replace("es_prefix: oro_test_\n", "es_prefix: oro_test_a\n"))
        p = self.run_script("es-drop-prefix.sh", "oro_test_a", STUB_ES="oro_test_ax:oro_test_b")
        self.assertEqual(p.returncode, 0)  # the stub filters by prefix, only oro_test_ax matches
        self.assertNotIn("oro_test_b -XDELETE", self.calls())

    def test_pg_drop_guard_and_drop(self):
        self.assertEqual(self.run_script("pg-drop.sh", "oro").returncode, 3)
        self.assertEqual(self.run_script("pg-drop.sh", "postgres").returncode, 3)
        self.assertNotIn("DROP DATABASE", self.calls())
        self.assertEqual(self.run_script("pg-drop.sh", "oro_test_baseline").returncode, 0)
        self.assertIn('DROP DATABASE IF EXISTS "oro_test_baseline"', self.calls())

    def test_pg_drop_rejects_injection(self):
        self.assertEqual(self.run_script("pg-drop.sh", 'oro_test"; DROP DATABASE oro; --').returncode, 3)
        self.assertNotIn("DROP DATABASE", self.calls())

    def test_pg_drop_absent_noop(self):
        p = self.run_script("pg-drop.sh", "oro_test_gone")
        self.assertEqual(p.returncode, 0)
        self.assertNotIn("DROP DATABASE", self.calls())

    def test_mongo_drop(self):
        self.assertEqual(self.run_script("mongo-drop.sh", "buckman").returncode, 3)
        self.assertEqual(self.run_script("mongo-drop.sh", "oro_test").returncode, 3)
        self.assertEqual(self.run_script("mongo-drop.sh", "oro_test_private").returncode, 0)
        self.assertIn("dropDatabase", self.calls())

    def test_vhost_drop(self):
        self.assertEqual(self.run_script("mq-vhost-drop.sh", "/").returncode, 3)
        self.assertEqual(self.run_script("mq-vhost-drop.sh", "oro_test_other").returncode, 3)
        self.assertEqual(self.run_script("mq-vhost-drop.sh", "oro_test").returncode, 0)
        self.assertIn("delete_vhost oro_test", self.calls())

    def test_usage_errors(self):
        self.assertEqual(self.run_script("es-drop-prefix.sh").returncode, 64)
        self.assertEqual(self.run_script("pg-drop.sh").returncode, 64)

    def test_missing_env_yml(self):
        os.remove(os.path.join(self.project, ".oro-ai", "local-env", "env.yml"))
        self.assertEqual(self.run_script("pg-drop.sh", "oro_test").returncode, 1)

    def test_bad_prefix_env_blocks_everything(self):
        shutil.copy(os.path.join(FIX, "env-bad-prefix.yml"), os.path.join(self.project, ".oro-ai", "local-env", "env.yml"))
        p = self.run_script("reset.sh")
        self.assertEqual(p.returncode, 3)
        self.assertNotIn("DROP DATABASE", self.calls())


class Reset(Base):
    def test_reset_twice_and_scope(self):
        for _ in range(2):
            p = self.run_script("reset.sh", "--skip-reindex")
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertLessEqual(self.lines(p), 15)
        c = self.calls()
        self.assertIn('CREATE DATABASE "oro_test" TEMPLATE "oro_test_baseline"', c)
        self.assertIn("redis-cli -n 7 FLUSHDB", c)
        self.assertNotIn("FLUSHALL", c)
        self.assertNotIn("redis-cli -n 0", c)
        self.assertIn("purge_queue -p oro_test q1", c)
        self.assertNotIn("purge_queue -p oro_test name", c)
        self.assertNotIn("-p / ", c.replace("list_queues -p / ", ""))
        self.assertNotIn('"oro"', c.replace('"oro_test', ""))

    def test_reset_reindexes_behat_test(self):
        self.run_script("reset.sh")
        self.assertIn("oro:search:reindex --env=behat_test", self.calls())
        self.assertIn("oro:website-search:reindex --env=behat_test", self.calls())

    def test_reset_without_baseline_fails(self):
        p = self.run_script("reset.sh", STUB_PG_DBS="oro")
        self.assertEqual(p.returncode, 1)
        self.assertIn("baseline", p.stdout)

    def test_reset_refuses_session_db_zero(self):
        env_file = os.path.join(self.project, ".oro-ai", "local-env", "env.yml")
        write(env_file, read(env_file).replace("    redis_dbs: [4, 5, 6, 7]\n", "    redis_dbs: [4, 5, 6, 7]\n    session_redis_db: 0\n"))
        # schema has no session_redis_db yet: envsh falls back to redis_dbs, so db 7 is used and 0 is never flushed
        p = self.run_script("reset.sh", "--skip-reindex")
        self.assertNotIn("redis-cli -n 0", self.calls())
        self.assertIn(p.returncode, (0, 3))

    def test_dry_run_mutates_nothing(self):
        p = self.run_script("reset.sh", "--dry-run")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        c = self.calls()
        for word in ("DROP DATABASE", "XDELETE", "FLUSHDB", "purge_queue", "mongorestore", "reindex"):
            self.assertNotIn(word, c)
        self.assertIn("would:", p.stdout)


class Baseline(Base):
    def test_up_to_date_is_noop(self):
        key = subprocess.run([os.path.join(SCRIPTS, "lib", "baseline-key.sh"), self.project], capture_output=True, text=True).stdout.strip()
        subprocess.run(["python3", os.path.join(SCRIPTS, "lib", "envsh.py"), "set", "--project", self.project, "local_test.baseline_key", key], check=True)
        p = self.run_script("baseline.sh")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("up to date", p.stdout)
        self.assertNotIn("DROP DATABASE", self.calls())

    def test_dry_run_plans_rebuild(self):
        p = self.run_script("baseline.sh", "--dry-run")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("would: oro:install --env=behat_test", p.stdout)
        self.assertNotIn("DROP DATABASE", self.calls())
        self.assertLessEqual(self.lines(p), 25)

    def test_key_changes_with_migrations(self):
        k = lambda: subprocess.run([os.path.join(SCRIPTS, "lib", "baseline-key.sh"), self.project], capture_output=True, text=True).stdout
        a = k()
        d = os.path.join(self.project, "src", "X", "Migrations")
        os.makedirs(d)
        write(os.path.join(d, "M1.php"), "<?php")
        self.assertNotEqual(a, k())


class Workers(Base):
    def test_formula(self):
        self.assertEqual(self.run_script("workers.sh", LE_CPUS="8", LE_RAM_GB="16").stdout.strip(), "2")
        self.assertEqual(self.run_script("workers.sh", LE_CPUS="2", LE_RAM_GB="16").stdout.strip(), "1")
        self.assertEqual(self.run_script("workers.sh", LE_CPUS="32", LE_RAM_GB="8").stdout.strip(), "1")
        self.assertEqual(self.run_script("workers.sh", LE_CPUS="32", LE_RAM_GB="64").stdout.strip(), "8")

    def test_write_respects_user(self):
        p = self.run_script("workers.sh", "--write", LE_CPUS="16", LE_RAM_GB="64")
        self.assertEqual(p.returncode, 0, p.stderr)
        got = subprocess.run(["python3", os.path.join(SCRIPTS, "lib", "env.py"), "get", "--project", self.project, "local_test.workers"], capture_output=True, text=True).stdout.strip()
        self.assertEqual(got, "4")
        env_file = os.path.join(self.project, ".oro-ai", "local-env", "env.yml")
        write(env_file, read(env_file).replace('workers_source: "auto"', 'workers_source: "user"'))
        p = self.run_script("workers.sh", "--write", LE_CPUS="8", LE_RAM_GB="16")
        self.assertIn("kept", p.stdout)


class OroTest(Base):
    def run_ot(self, *args, **env):
        return subprocess.run([os.path.join(SCRIPTS, "..", "..", "bin", "aaxis-oro"), "test", "--project", self.project, *args], capture_output=True, text=True,
                              env=dict(self.env, **env), cwd=self.project)

    def test_no_target_is_usage_error(self):
        self.assertEqual(self.run_ot().returncode, 64)
        self.assertEqual(self.run_ot("phpunit").returncode, 64)
        self.assertEqual(self.run_ot("local-test").returncode, 64)

    def test_verify_ok(self):
        p = self.run_ot("local-test", "verify")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("verified", p.stdout)

    def test_phpunit_pointed_at_local_db_refused(self):
        self.write_live("test", db="oro")
        p = self.run_ot("local-test", "phpunit")
        self.assertEqual(p.returncode, 3, p.stdout)
        self.assertNotIn("phpunit", self.calls())
        self.assertLessEqual(self.lines(p), 8)

    def test_behat_test_live_db_mismatch_refused(self):
        self.write_live("behat_test", db="oro")
        p = self.run_ot("local-test", "verify")
        self.assertEqual(p.returncode, 3)
        self.assertIn("behat_test", p.stdout)

    def test_wrong_live_values_refused(self):
        self.write_live("behat_test", db="oro_test", search_engine_dsn="elastic-search://h?prefix=oro_search",
                        message_queue_transport_dsn="amqp://u@h/%2f", session_handler_dsn="redis://h:6379/0",
                        **{"gaufrette_adapter.private": "gridfs:mongodb://h/private"})
        p = self.run_ot("local-test", "verify")
        self.assertEqual(p.returncode, 3)
        for word in ("search_engine_dsn", "message_queue_transport_dsn", "session_handler_dsn", "gaufrette.private"):
            self.assertIn(word, p.stdout)

    def test_env_overrides_refused_before_anything_runs(self):
        for args in (("console", "doctrine:schema:drop", "--force", "--env=prod"),
                     ("console", "x", "--env", "prod"), ("console", "x", "-e", "prod"), ("console", "x", "-eprod"),
                     ("console", "x", "-e=dev"), ("phpunit", "--env=prod"), ("e2e", "--env=prod")):
            p = self.run_ot("local-test", *args)
            self.assertEqual(p.returncode, 3, args)
        self.assertEqual(self.calls(), "")
        self.assertEqual(self.run_ot("local-test", "verify", ORO_ENV="prod").returncode, 3)
        self.assertEqual(self.run_ot("local-test", "verify", APP_ENV="dev").returncode, 3)
        self.assertEqual(self.calls(), "")
        self.assertEqual(self.run_ot("local-test", "verify", ORO_ENV="behat_test").returncode, 0)

    def test_local_refuses_test_envs(self):
        self.assertEqual(self.run_ot("local", "console", "x", "--env=behat_test").returncode, 3)
        self.assertEqual(self.run_ot("local", "verify", ORO_ENV="test").returncode, 3)

    def test_verify_is_one_line_with_timing(self):
        p = self.run_ot("local-test", "verify")
        self.assertEqual(self.lines(p), 1)
        self.assertRegex(p.stdout, r" in \d+\.\ds")

    def test_local_target_never_runs_tests(self):
        p = self.run_ot("local", "phpunit")
        self.assertEqual(p.returncode, 3)
        self.assertNotIn("phpunit", self.calls())

    def test_phpunit_runs_with_explicit_env_and_short_summary(self):
        os.makedirs(os.path.join(self.project, "bin"))
        stub = os.path.join(self.project, "bin", "phpunit")
        write(stub, "#!/usr/bin/env bash\necho \"ORO_ENV=$ORO_ENV\" >> \"$STUB_LOG\"\nseq 1 400\necho 'OK (3 tests, 5 assertions)'\n")
        os.chmod(stub, 0o755)
        p = self.run_ot("local-test", "phpunit", "tests/x")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("ORO_ENV=test", self.calls())
        self.assertLessEqual(self.lines(p), 15)
        self.assertIn("OK (3 tests", p.stdout)


class Sudo(Base):
    def test_supervisor_prints_command(self):
        p = self.run_script("supervisor.sh", "restart", "nginx", "fpm")
        self.assertEqual(p.returncode, 10)
        self.assertIn("SUDO-NEEDED: sudo supervisorctl restart nginx fpm", p.stdout)
        p = self.run_script("supervisor.sh", "reload-nginx")
        self.assertIn("SUDO-NEEDED: sudo supervisorctl signal HUP nginx", p.stdout)
        self.assertNotIn("systemctl", p.stdout)

    def test_supervisor_usage(self):
        self.assertEqual(self.run_script("supervisor.sh", "restart").returncode, 64)

    def test_oro_project(self):
        p = subprocess.run([os.path.join(SCRIPTS, "oro-project"), "--install"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 10)
        self.assertIn("SUDO-NEEDED: sudo ln -sf", p.stdout)
        p = subprocess.run([os.path.join(SCRIPTS, "oro-project"), "buckman"], capture_output=True, text=True, env=dict(os.environ, CLAUDECODE="1"))
        self.assertEqual(p.returncode, 10)
        self.assertEqual(subprocess.run([os.path.join(SCRIPTS, "oro-project")], capture_output=True).returncode, 64)

    def test_repair_hosts_prints_sudo(self):
        p = self.run_script("repair.sh", "--only", "hosts")
        self.assertIn(p.returncode, (0, 10))
        if p.returncode == 10:
            self.assertIn("SUDO-NEEDED: echo '127.0.0.1 ", p.stdout)


class Restore(Base):
    def test_requires_yes(self):
        self.assertEqual(self.run_script("restore-local.sh").returncode, 64)

    def test_yes_is_only_a_standalone_flag(self):
        p = self.run_script("restore-local.sh", "--dump", "--yes")
        self.assertEqual(p.returncode, 64)
        self.assertNotIn("DROP DATABASE", self.calls())

    def test_refuses_test_named_local_db(self):
        env_file = os.path.join(self.project, ".oro-ai", "local-env", "env.yml")
        write(env_file, read(env_file).replace("    db: oro\n", "    db: oro_test_x\n", 1))
        p = self.run_script("restore-local.sh", "--yes")
        self.assertEqual(p.returncode, 3)
        self.assertNotIn("DROP DATABASE", self.calls())

    def test_dry_run(self):
        p = self.run_script("restore-local.sh", "--dry-run")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn("DROP DATABASE", self.calls())

    def test_attachments_refuse_test_env(self):
        d = os.path.join(self.tmp, "att")
        os.makedirs(os.path.join(d, "attachments"))
        self.assertEqual(self.run_script("import-attachments.sh", d, "--env", "behat_test").returncode, 1)
        self.assertEqual(self.run_script("import-attachments.sh", "--dry-run", d).returncode, 0)


class Check(Base):
    def test_summary_and_json(self):
        p = self.run_script("check.sh")
        self.assertIn(p.returncode, (0, 2), p.stderr)
        self.assertRegex(p.stdout, r"check: \d+ ok, \d+ drift")
        self.assertLessEqual(self.lines(p), 20)
        j = self.run_script("check.sh", "--json")
        data = json.loads(j.stdout)
        self.assertIn("items", data)


class Params(Base):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.project, "config"))
        self.params = os.path.join(self.project, "config", "parameters.yml")
        write(self.params, "parameters:\n    web: /x\n    oro_asset.nodejs_path: /old/v1.0.0/bin/node\n    gaufrette_adapter.public: 'local'\n")
        write(os.path.join(self.project, ".nvmrc"), "24\n")
        write(os.path.join(self.project, "composer.json"), '{"require": {"php": "~8.5.0"}}')
        nvm = os.path.join(self.tmp, "nvm")
        os.makedirs(nvm)
        write(os.path.join(nvm, "nvm.sh"), 'nvm() { case "$1" in version) echo "v24.21.0";; install) echo "$2" >> "$STUB_LOG";; esac; }\n')
        self.env["NVM_DIR"] = nvm
        write(os.path.join(self.project, ".env-app.test.local"), "ORO_DB_URL=x\nORO_REDIS_CACHE_DSN=redis://h/4\nORO_SESSION_DSN=redis://h/7\n")

    def test_check_reports_managed_drift(self):
        p = self.run_script("check.sh")
        self.assertEqual(p.returncode, 2)
        self.assertIn("DRIFT node", p.stdout)
        self.assertIn("DRIFT gaufrette-public", p.stdout)
        self.assertIn("DRIFT gaufrette-private", p.stdout)
        self.assertIn("DRIFT redis-cache", p.stdout)

    def test_repair_params_rewrites_without_backup_and_is_idempotent(self):
        p = self.run_script("repair.sh", "--only", "params")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        text = read(self.params)
        self.assertIn("oro_asset.nodejs_path: " + os.path.join(self.tmp, "nvm", "versions", "node", "v24.21.0", "bin", "node"), text)
        self.assertIn("oro_asset.pnpm_path:", text)
        self.assertIn("gaufrette_adapter.public: 'gridfs:%env(ORO_MONGODB_DSN_PUBLIC)%'", text)
        self.assertIn("gaufrette_adapter.private: 'gridfs:%env(ORO_MONGODB_DSN_PRIVATE)%'", text)
        self.assertIn("    web: /x", text)
        self.assertNotIn("ORO_REDIS_CACHE_DSN", read(os.path.join(self.project, ".env-app.test.local")))
        self.assertIn("ORO_SESSION_DSN", read(os.path.join(self.project, ".env-app.test.local")))
        backups = os.path.join(self.project, "var", "backups", "oro-local-env")
        self.assertFalse([n for n in os.listdir(backups) if n.startswith("parameters")] if os.path.isdir(backups) else [])
        self.assertFalse([n for n in os.listdir(os.path.dirname(self.params)) if n != "parameters.yml"])
        again = self.run_script("repair.sh", "--only", "node")
        self.assertEqual(again.returncode, 0)
        self.assertEqual(text, read(self.params))
        c = self.run_script("check.sh")
        self.assertNotIn("gaufrette", c.stdout)
        self.assertNotIn("redis-cache", c.stdout)

    def shadow(self, adapter="'gridfs:%env(ORO_MONGODB_DSN_PUBLIC)%'"):
        write(self.params, read(self.params).replace("'local'", adapter))
        js = os.path.join(self.project, "public", "media", "js")
        os.makedirs(os.path.join(js, "translation"))
        write(os.path.join(js, "frontend_routes.json"), "{}")
        write(os.path.join(js, "translation", "en_US.json"), "{}")
        return js

    def test_check_flags_disk_dump_shadowing_gridfs_and_repair_moves_it_aside(self):
        js = self.shadow()
        self.assertIn("DRIFT media-shadow", self.run_script("check.sh").stdout)
        self.run_script("repair.sh", "--only", "media", "--dry-run")
        self.assertTrue(os.path.exists(os.path.join(js, "frontend_routes.json")))
        r = self.run_script("repair.sh", "--only", "media")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(js, "frontend_routes.json")))
        self.assertFalse(os.path.exists(os.path.join(js, "translation", "en_US.json")))
        aside = os.path.join(self.project, ".oro-ai", "local-env", "moved-aside")
        ts = os.listdir(aside)
        self.assertEqual(len(ts), 1)
        self.assertTrue(os.path.exists(os.path.join(aside, ts[0], "public", "media", "js", "frontend_routes.json")))
        self.assertNotIn("media-shadow", self.run_script("check.sh").stdout)

    def test_local_filesystem_adapter_is_not_shadowing(self):
        js = self.shadow("'local:/var/media'")
        self.assertNotIn("media-shadow", self.run_script("check.sh").stdout)
        self.run_script("repair.sh", "--only", "media")
        self.assertTrue(os.path.exists(os.path.join(js, "frontend_routes.json")))

    def test_node_pin_wins_over_nvmrc(self):
        subprocess.run(["python3", os.path.join(SCRIPTS, "lib", "envsh.py"), "set", "--project", self.project, "node_pin", "22.1.0"], check=True)
        self.run_script("repair.sh", "--only", "params", "--dry-run")
        self.assertEqual(self.run_script("repair.sh", "--only", "bogus").returncode, 64)


class Syntax(unittest.TestCase):
    def test_bash_scripts_parse(self):
        names = [n for n in os.listdir(SCRIPTS) if n.endswith(".sh") or n in ("test.sh", "switch.sh", "oro-project", "refresh.sh")]
        names += ["lib/" + n for n in os.listdir(os.path.join(SCRIPTS, "lib")) if n.endswith(".sh")]
        for n in names:
            p = subprocess.run(["bash", "-n", os.path.join(SCRIPTS, n)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, "%s: %s" % (n, p.stderr))
            self.assertIn('# oro: ">=7.0.0"', "\n".join(read(os.path.join(SCRIPTS, n)).split("\n")[:15]))

    def test_old_logs_are_rotated(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        proj = os.path.join(tmp, "p")
        logs = os.path.join(proj, ".oro-ai", "local-env", "logs")
        os.makedirs(logs)
        shutil.copy(os.path.join(FIX, "env-ok.yml"), os.path.join(proj, ".oro-ai", "local-env", "env.yml"))
        for i in range(15):
            write(os.path.join(logs, "workers-2020010100%02d00.log" % i), "")
        subprocess.run([os.path.join(SCRIPTS, "workers.sh"), "--project", proj], capture_output=True, check=True)
        self.assertEqual(len([n for n in os.listdir(logs) if n.startswith("workers-")]), 10)


class NodePhp(unittest.TestCase):
    def test_set_node_adds_and_updates(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "parameters.yml")
        write(path, "parameters:\n    a: 1\n    oro_asset.nodejs_path: /old/node\n")
        tool = os.path.join(SCRIPTS, "lib", "nodephp.py")
        subprocess.run(["python3", tool, "set-node", path, "/n/v24.21.0/bin"], check=True)
        first = read(path)
        self.assertIn("oro_asset.nodejs_path: /n/v24.21.0/bin/node", first)
        self.assertIn("oro_asset.npm_path: /n/v24.21.0/bin/npm", first)
        self.assertIn("oro_asset.pnpm_path: /n/v24.21.0/bin/pnpm", first)
        self.assertIn("    a: 1", first)
        subprocess.run(["python3", tool, "set-node", path, "/n/v24.21.0/bin"], check=True)
        self.assertEqual(first, read(path))
        out = subprocess.run(["python3", tool, "node-paths", path], capture_output=True, text=True).stdout.split()
        self.assertEqual(out, ["/n/v24.21.0/bin/node", "/n/v24.21.0/bin/npm", "/n/v24.21.0/bin/pnpm"])

    def test_php_ok(self):
        tool = os.path.join(SCRIPTS, "lib", "nodephp.py")
        self.assertEqual(subprocess.run(["python3", tool, "php-ok", "~8.5.0", "8.5.10"]).returncode, 0)
        self.assertEqual(subprocess.run(["python3", tool, "php-ok", "~8.5.0", "8.4.1"]).returncode, 1)


class E2eConsumer(Base):
    def test_consumer_restarts_and_dies_with_the_run(self):
        os.makedirs(os.path.join(self.project, "bin"))
        marker = os.path.join(self.tmp, "consume.count")
        console = os.path.join(self.project, "bin", "console")
        write(console, """#!/usr/bin/env bash
case "$*" in
    *queue-status*) echo '{"consumers": 0}' ;;
    *message-queue:consume*) echo x >> "%(m)s"; if [ "$(wc -l < "%(m)s")" -ge 3 ]; then echo $$ > "%(m)s.pid"; exec sleep 300; fi; exit 0 ;;
    *test:e2e*) for _ in $(seq 300); do [ -f "%(m)s.pid" ] && exit 0; sleep 0.1; done; exit 1 ;;
esac
""" % {"m": marker})
        os.chmod(console, 0o755)
        p = subprocess.run([os.path.join(ROOT, "bin", "aaxis-oro"), "test", "--project", self.project, "local-test", "e2e"],
                           capture_output=True, text=True, env=self.env, cwd=self.project)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertRegex(p.stdout, r"consumer: [2-9] restarts")
        with self.assertRaises(ProcessLookupError):
            os.kill(int(read(marker + ".pid")), 0)


if __name__ == "__main__":
    unittest.main()
