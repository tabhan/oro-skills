import json
import os
import subprocess
import unittest

from test_scripts import ROOT, Base, read, write

REFRESH = os.path.join(ROOT, "scripts", "local-env", "lib", "refresh.py")


def categories(path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("refresh", REFRESH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.categories_of(path)


class Mapping(unittest.TestCase):
    def test_change_to_category(self):
        cases = {
            "composer.lock": {"composer"},
            "src/A/Bundle/XBundle/Migrations/Schema/v1_0/X.php": {"migrations", "code"},
            "src/A/Bundle/XBundle/Resources/config/oro/entity_extend.yml": {"entity", "code"},
            "src/A/Bundle/XBundle/Resources/translations/messages.en.yml": {"translations"},
            "src/A/Bundle/XBundle/Resources/config/oro/routing.yml": {"routing", "code"},
            "src/A/Bundle/XBundle/Controller/FooController.php": {"routing", "code"},
            "src/A/Bundle/XBundle/Tests/DataFixtures/X.php": set(),
            "src/A/Bundle/XBundle/Migrations/Data/ORM/LoadX.php": {"migrations", "code"},
            "src/A/Bundle/XBundle/DataFixtures/X.php": {"fixtures", "code"},
            "src/A/Bundle/XBundle/Resources/public/img/a.png": {"assets"},
            "src/A/Bundle/XBundle/Resources/views/layouts/b/theme.yml": {"assets"},
            "src/A/Bundle/XBundle/Resources/views/layouts/b/styles.scss": {"assets"},
            "src/A/Bundle/XBundle/Resources/config/oro/jsmodules.yml": {"assets", "code"},
            "package.json": {"assets"},
            "config/config.yml": {"code"},
            "src/A/Service/Foo.php": {"code"},
            "src/A/Tests/Unit/FooTest.php": set(),
            "README.md": set(),
        }
        for path, want in cases.items():
            self.assertEqual(categories(path), want, path)


class Refresh(Base):
    def setUp(self):
        super().setUp()
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.test")
        self.git("config", "user.name", "t")
        write(os.path.join(self.project, ".gitignore"), ".oro-ai/\n")
        for rel in ("src/B/Resources/translations/messages.en.yml", "src/B/Foo.php", "src/B/Migrations/Schema/M.php"):
            os.makedirs(os.path.join(self.project, os.path.dirname(rel)), exist_ok=True)
            write(os.path.join(self.project, rel), "a\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")
        self.set_baseline_key()

    def baseline_key(self):
        return subprocess.run([os.path.join(ROOT, "scripts", "local-env", "lib", "baseline-key.sh"), self.project],
                              capture_output=True, text=True).stdout.strip()

    def set_baseline_key(self):
        path = os.path.join(self.project, ".oro-ai", "local-env", "env.yml")
        with open(path) as fh:
            text = fh.read()
        with open(path, "w") as fh:
            fh.write(text.replace("baseline_key: null", "baseline_key: %s" % self.baseline_key()))

    def git(self, *args):
        subprocess.run(["git", "-C", self.project, *args], check=True, capture_output=True)

    def refresh(self, *args, **env):
        return self.run_script("refresh.sh", *args, **env)

    def gate(self, target="local-test", *extra):
        return subprocess.run([os.path.join(ROOT, "bin", "aaxis-oro"), "test", "--project", self.project, *extra, target, "verify"],
                              capture_output=True, text=True, env=self.env, cwd=self.project)

    def test_dry_run_without_record_plans_everything_and_writes_nothing(self):
        p = self.refresh("--dry-run")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("steps since none", p.stdout)
        for s in ("composer", "cache-local", "cache-test", "migrate", "baseline-stale", "entity", "translations", "routing-local", "routing-test", "assets"):
            self.assertIn("would run %s" % s, p.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.project, ".oro-ai", "local-env", "refresh.json")))
        self.assertEqual(self.calls(), "")

    def test_real_refresh_records_then_is_up_to_date(self):
        p = self.refresh()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertLessEqual(self.lines(p), 15)
        with open(os.path.join(self.project, ".oro-ai", "local-env", "refresh.json")) as fh:
            rec = json.load(fh)
        self.assertEqual(len(rec["commit"]), 40)
        self.assertIn("composer install --no-interaction", self.calls())
        self.assertIn("oro:migration:load --force --env=prod", self.calls())
        self.assertIn("cache:warmup --env=behat_test", self.calls())
        self.assertIn("fos:js-routing:dump --env=prod", self.calls())
        self.assertIn("fos:js-routing:dump --env=behat_test", self.calls())
        self.assertNotIn("oro:migration:load --force --env=behat_test", self.calls())
        self.assertIn("up to date", self.refresh().stdout)

    def test_only_needed_steps_run(self):
        self.refresh()
        write(os.path.join(self.project, "src/B/Resources/translations/messages.en.yml"), "b\n")
        p = self.refresh("--dry-run")
        self.assertIn("would run translations", p.stdout)
        self.assertEqual(p.stdout.count("would run"), 1)
        write(os.path.join(self.project, "src/B/Foo.php"), "changed\n")
        p = self.refresh("--dry-run")
        for s in ("cache-local", "cache-test", "translations"):
            self.assertIn("would run %s" % s, p.stdout)
        self.assertNotIn("would run migrate", p.stdout)

    def test_migration_change_marks_baseline_stale_without_migrating_test(self):
        self.refresh()
        write(os.path.join(self.project, "src/B/Migrations/Schema/M.php"), "new\n")
        p = self.refresh()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("baseline-stale", p.stdout)
        self.assertIn("migrate", p.stdout)
        self.assertNotIn("behat_test oro:migration", self.calls())

    def test_committing_does_not_make_tree_stale(self):
        self.refresh()
        write(os.path.join(self.project, "src/B/Foo.php"), "changed\n")
        self.git("commit", "-qam", "edit")
        self.refresh()
        self.git("commit", "-qm", "empty", "--allow-empty")
        self.assertIn("up to date", self.refresh().stdout)

    def test_failure_stops_and_keeps_record_untouched(self):
        p = self.refresh(**{"STUB_COMPOSER_RC": "1"})
        self.assertEqual(p.returncode, 1)
        self.assertIn("composer", p.stdout)
        self.assertIn("FAIL", p.stdout)
        self.assertNotIn("cache:warmup", self.calls())
        self.assertFalse(os.path.exists(os.path.join(self.project, ".oro-ai", "local-env", "refresh.json")))

    def test_gate_refuses_without_record_and_after_edit(self):
        p = self.gate()
        self.assertEqual(p.returncode, 3, p.stdout)
        self.assertRegex(p.stdout.strip(), r"^tree not refreshed since none; run: aaxis-oro dev refresh$")
        self.assertEqual(self.calls(), "")
        self.refresh()
        self.assertEqual(self.gate().returncode, 0)
        self.assertEqual(self.gate("local").returncode, 0)
        write(os.path.join(self.project, "src/B/Foo.php"), "changed\n")
        p = self.gate()
        self.assertEqual(p.returncode, 3)
        self.assertIn("tree not refreshed since ", p.stdout)

    def test_gate_only_for_steps_of_the_target_and_escape_hatch(self):
        self.refresh()
        write(os.path.join(self.project, "src/B/Resources/translations/messages.en.yml"), "z\n")  # local-only step
        self.assertEqual(self.gate("local-test").returncode, 0)
        p = self.gate("local")
        self.assertEqual(p.returncode, 3)
        self.assertEqual(self.gate("local", "--no-refresh-check").returncode, 0)

    def test_routing_change_runs_dump_per_stack_and_gates_both(self):
        self.refresh()
        write(os.path.join(self.project, "src/B/FooController.php"), "x\n")
        for target in ("local", "local-test"):
            self.assertEqual(self.gate(target).returncode, 3, target)
        p = self.refresh("--dry-run")
        for s in ("routing-local", "routing-test", "cache-local", "cache-test"):
            self.assertIn("would run %s" % s, p.stdout)
        self.assertNotIn("would run assets", p.stdout)

    def test_stale_baseline_refuses_local_test_only(self):
        self.refresh()
        self.assertEqual(self.gate().returncode, 0)
        write(os.path.join(self.project, ".oro-ai", "local-env", "env.yml"),
              open(os.path.join(self.project, ".oro-ai", "local-env", "env.yml")).read().replace(self.baseline_key(), "a" * 64))
        p = self.gate()
        self.assertEqual(p.returncode, 3)
        self.assertEqual(p.stdout.strip(), "baseline stale; run: aaxis-oro env baseline")
        self.assertEqual(self.gate("local").returncode, 0)
        self.assertEqual(self.gate("local-test", "--no-refresh-check").returncode, 0)

    def test_migration_change_makes_baseline_stale_even_after_refresh(self):
        self.refresh()
        write(os.path.join(self.project, "src/B/Migrations/Schema/M.php"), "new\n")
        self.assertEqual(self.refresh().returncode, 0)
        p = self.gate()
        self.assertEqual(p.returncode, 3)
        self.assertIn("baseline stale", p.stdout)

    def test_baseline_key_is_cached_until_inputs_change(self):
        import time
        cmd = [os.path.join(ROOT, "scripts", "local-env", "lib", "refresh.py"), "baseline-key", "--project", self.project]
        first = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
        t = time.time()
        self.assertEqual(subprocess.run(cmd, capture_output=True, text=True).stdout.strip(), first)
        self.assertLess(time.time() - t, 1.0)

    def test_test_cache_warms_behat_test_only(self):
        os.makedirs(os.path.join(self.project, "var", "cache", "test"))
        self.refresh()
        self.assertIn("cache:warmup --env=behat_test", self.calls())
        self.assertNotIn("cache:warmup --env=test", self.calls())
        self.assertFalse(os.path.exists(os.path.join(self.project, "var", "cache", "test")))

    def test_composer_without_scripts_and_configured_platform_ignores(self):
        path = os.path.join(self.project, ".oro-ai", "local-env", "env.yml")
        write(path, read(path) + "composer_ignore_platform_reqs: [ext-mongodb, ext-foo]\n")
        self.refresh()
        self.assertIn("composer install --no-interaction --no-scripts --ignore-platform-req=ext-mongodb --ignore-platform-req=ext-foo", self.calls())

    def test_no_ignore_flag_without_config(self):
        self.refresh()
        self.assertIn("composer install --no-interaction --no-scripts", self.calls())
        self.assertNotIn("ignore-platform-req", self.calls())

    def test_newly_modified_tracked_files_are_warned_not_reverted(self):
        target = os.path.join(self.project, "src", "B", "Foo.php")
        p = self.refresh(STUB_COMPOSER_TOUCH=target)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertRegex(p.stdout, r"WARN tracked file modified: \s*M src/B/Foo.php")
        self.assertIn("touched", read(target))

    def test_routing_warns_when_disk_files_shadow_gridfs(self):
        os.makedirs(os.path.join(self.project, "config"))
        write(os.path.join(self.project, "config", "parameters.yml"), "parameters:\n    gaufrette_adapter.public: 'gridfs:x'\n")
        os.makedirs(os.path.join(self.project, "public", "media", "js"))
        write(os.path.join(self.project, "public", "media", "js", "frontend_routes.json"), "{}")
        p = self.refresh()
        self.assertIn("WARN stale public/media/js files shadow", p.stdout)

    def test_non_git_project_is_not_gated(self):
        import shutil
        shutil.rmtree(os.path.join(self.project, ".git"))
        self.assertEqual(self.gate().returncode, 0)


if __name__ == "__main__":
    unittest.main()
