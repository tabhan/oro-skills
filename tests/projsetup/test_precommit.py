import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BIN = os.path.join(ROOT, "bin", "aaxis-oro")
sys.path.insert(0, os.path.join(ROOT, "lib"))
from projsetup import precommit  # noqa: E402

COMPOSER = '{"require": {"oro/commerce": "7.0.*"}, "scripts": {"post-install-cmd": ["@x"]}}'
BITBUCKET = """definitions:
    steps:
        - step: &php
              script:
                  - composer install -n
                  - php ./vendor/squizlabs/php_codesniffer/bin/phpcs ./src --standard=PSR2
                  - php ./vendor/phpunit/phpunit/phpunit --configuration ./phpunit.xml
              cache:
                  - composer
        - step: &lint
              script:
                  - npm i -g pnpm@10.7.0
                  - npm run eslint src -- --ignore-pattern "src/OroLab/**"
        - step: &sonar
              script:
                  - pipe: sonarsource/sonarcloud-scan:4.1.0
        - step: &yaml
              script:
                  - yamllint ./src/
"""
WORKFLOW = """jobs:
  t:
    steps:
      - run: vendor/bin/phpstan analyse
      - run: |
          echo hi
"""


def run(*args, cwd):
    env = dict(os.environ, HOME=cwd, AAXIS_ORO_NO_TOOL_INSTALL="1")
    p = subprocess.run([sys.executable, BIN, "setup"] + list(args) + ["--project", cwd], capture_output=True, text=True, env=env)
    return p.returncode, p.stdout + p.stderr


class RepoCase(unittest.TestCase):
    """A throwaway git repo that looks like an Oro project."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        subprocess.run(["git", "init", "-q", self.d], check=True)
        self.put("composer.json", COMPOSER)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, rel, text):
        p = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(text)
        return p

    def hook(self):
        return precommit.hook_path(self.d)


class PrecommitTest(RepoCase):
    def test_ci_steps_in_tool_order_without_installs_or_sonar(self):
        self.put("bitbucket-pipelines.yml", BITBUCKET)
        st = precommit.steps(self.d)
        self.assertEqual([s[0] for s in st], ["phpcs", "phpunit", "eslint", "yamllint"])
        self.assertTrue(all(s[3] == "bitbucket-pipelines.yml" for s in st))
        self.assertIn('--ignore-pattern "src/OroLab/**"', st[2][2])

    def test_github_run_lines_and_vendor_defaults(self):
        self.put(".github/workflows/ci.yml", WORKFLOW)
        self.put("vendor/bin/phpmd", "")
        self.put("phpmd.xml", "<x/>")
        self.put("vendor/bin/phpunit", "")  # no phpunit.xml: no step
        self.put(".yamllint", "extends: default\n")
        self.put("src/.keep", "")
        st = {s[0]: s for s in precommit.steps(self.d)}
        self.assertEqual(sorted(st), ["phpmd", "phpstan", "yamllint"])
        self.assertEqual(st["phpstan"][2], "vendor/bin/phpstan analyse")
        self.assertEqual(st["phpmd"][2], "vendor/bin/phpmd src ansi phpmd.xml")
        self.assertEqual(st["yamllint"][3], ".yamllint")

    def test_package_scripts_need_config_and_skip_and_atlas_options(self):
        self.put("package.json", json.dumps({"scripts": {"eslint": "eslint", "stylelint": "stylelint"}}))
        self.put(".eslintrc.yml", "")
        self.assertEqual([s[0] for s in precommit.steps(self.d)], ["eslint"])
        self.put(".oro-ai/config.json", json.dumps({"precommit": {"skip": ["eslint"], "atlas": True}}))
        self.assertEqual([s[0] for s in precommit.steps(self.d)], ["atlas"])

    def test_render_yamllint_wrapper_and_node_prefix(self):
        self.put("bitbucket-pipelines.yml", BITBUCKET)
        self.put(".nvmrc", "24\n")
        text = precommit.render(self.d)
        self.assertTrue(text.startswith("#!/usr/bin/env bash\n" + precommit.MARK))
        self.assertIn('run_step "YamlLint" run_yamllint ./src/', text)
        self.assertIn("nvm use --silent", text)
        self.put(".oro-ai/config.json", json.dumps({"precommit": {"path-prefix": "/opt/node/bin"}}))
        text = precommit.render(self.d)
        self.assertIn("export PATH=/opt/node/bin:", text)
        self.assertNotIn("nvm use", text)
        self.assertEqual(subprocess.run(["bash", "-n"], input=text, text=True).returncode, 0)

    def test_sync_installs_idempotently_and_status_reports_drift(self):
        self.put("bitbucket-pipelines.yml", BITBUCKET)
        code, out = run("status", cwd=self.d)
        self.assertIn("pre-commit        missing", out)
        code, out = run("sync", cwd=self.d)
        self.assertIn("pre-commit: created", out)
        self.assertTrue(os.access(self.hook(), os.X_OK))
        self.assertEqual(precommit.state(self.d)[0], "ok")
        code, out = run("sync", cwd=self.d)
        self.assertIn("pre-commit: unchanged", out)
        self.put("bitbucket-pipelines.yml", BITBUCKET.replace("--standard=PSR2", "--standard=PSR12"))
        code, out = run("status", cwd=self.d)
        self.assertIn("pre-commit        outdated", out)
        run("sync", cwd=self.d)
        self.assertIn("PSR12", open(self.hook()).read())
        self.assertEqual(git_status(self.d), git_status(self.d))

    def test_render_adds_phpcs_speedup_once_and_only_to_direct_calls(self):
        self.put("bitbucket-pipelines.yml", BITBUCKET)
        text = precommit.render(self.d)
        self.assertEqual(text.count('--parallel="$(phpcs_jobs)"'), 1)
        self.assertEqual(text.count('--cache="$(git rev-parse --absolute-git-dir)/phpcs.cache"'), 1)
        own = BITBUCKET.replace("--standard=PSR2", "--standard=PSR2 --parallel=$(nproc) --cache=$HOME/.phpcs-cache/phpcs.cache")
        self.put("bitbucket-pipelines.yml", own)
        text = precommit.render(self.d)
        self.assertEqual(text.count("--parallel="), 1)
        self.assertEqual(text.count("--cache="), 1)
        self.assertNotIn(".phpcs-cache", text)
        self.assertNotIn("$(nproc)", text.split("run_step", 1)[1])
        self.assertEqual(precommit.with_phpcs_speedup("composer run-script phpcs"), "composer run-script phpcs")
        self.assertEqual(subprocess.run(["bash", "-n"], input=text, text=True).returncode, 0)

    def test_render_runs_phpmd_with_deprecations_hidden(self):
        q = precommit.PHPMD_QUIET
        self.assertEqual(precommit.with_phpmd_quiet("php ./vendor/phpmd/phpmd/src/bin/phpmd ./src ansi x.xml"),
                         q + " ./vendor/phpmd/phpmd/src/bin/phpmd ./src ansi x.xml")
        self.assertEqual(precommit.with_phpmd_quiet("vendor/bin/phpmd src ansi x.xml"), q + " vendor/bin/phpmd src ansi x.xml")
        once = precommit.with_phpmd_quiet("php -d error_reporting=E_ALL ./phpmd")
        self.assertEqual(once, "php -d error_reporting=E_ALL ./phpmd")
        self.assertEqual(precommit.with_phpmd_quiet("composer run-script phpmd"), "composer run-script phpmd")
        self.assertIn("--cache-strategy content", precommit.with_phpmd_cache("vendor/bin/phpmd src ansi x.xml"))
        self.assertEqual(precommit.with_phpmd_cache("phpmd src --cache"), "phpmd src --cache")
        self.assertEqual(precommit.with_phpmd_cache("composer run-script phpmd"), "composer run-script phpmd")
        self.put("bitbucket-pipelines.yml", CI_WHOLE_TREE)
        text = precommit.render(self.d)
        self.assertEqual(text.count("phpmd.result-cache.php"), 1)
        self.assertIn('"PHP Mess Detector" php -d error_reporting="E_ALL & ~E_DEPRECATED" ./vendor/phpmd/phpmd/src/bin/phpmd', text)

    def test_sync_repairs_an_hook_without_phpmd_error_reporting(self):
        self.put("bitbucket-pipelines.yml", CI_WHOLE_TREE)
        run("sync", cwd=self.d)
        current = open(self.hook()).read()
        old = current.replace(' -d error_reporting="E_ALL & ~E_DEPRECATED"', "").replace(precommit.PHPMD_CACHE, "")
        self.assertNotEqual(old, current)
        with open(self.hook(), "w") as fh:
            fh.write(old)
        self.assertEqual(precommit.state(self.d)[0], "outdated")
        run("sync", cwd=self.d)
        self.assertEqual(open(self.hook()).read(), current)

    def test_sync_repairs_an_installed_hook_without_parallel_and_cache(self):
        self.put("bitbucket-pipelines.yml", BITBUCKET)
        run("sync", cwd=self.d)
        current = open(self.hook()).read()
        old = current.replace(' --parallel="$(phpcs_jobs)"', "").replace(' --cache="$(git rev-parse --absolute-git-dir)/phpcs.cache"', "")
        self.assertNotEqual(old, current)
        with open(self.hook(), "w") as fh:
            fh.write(old)
        self.assertEqual(precommit.state(self.d)[0], "outdated")
        self.assertIn("pre-commit        outdated", run("status", cwd=self.d)[1])
        self.assertIn("pre-commit: updated", run("sync", cwd=self.d)[1])
        self.assertEqual(open(self.hook()).read(), current)
        self.assertEqual(precommit.state(self.d)[0], "ok")

    def test_foreign_hook_backed_up_under_hooks_path(self):
        self.put("bitbucket-pipelines.yml", BITBUCKET)
        subprocess.run(["git", "-C", self.d, "config", "core.hooksPath", ".githooks"], check=True)
        old = self.put(".githooks/pre-commit", "#!/bin/sh\necho mine\n")
        code, out = run("status", cwd=self.d)
        self.assertIn("unmanaged hook", out)
        self.assertEqual(code, 2)
        code, out = run("sync", cwd=self.d)
        self.assertIn("backed up to", out)
        baks = [f for f in os.listdir(os.path.dirname(old)) if f.startswith("pre-commit.bak-")]
        self.assertEqual(len(baks), 1)
        self.assertEqual(open(os.path.join(os.path.dirname(old), baks[0])).read(), "#!/bin/sh\necho mine\n")
        self.assertIn(precommit.MARK, open(old).read())
        run("sync", cwd=self.d)
        self.assertEqual(len([f for f in os.listdir(os.path.dirname(old)) if f.startswith("pre-commit.bak-")]), 1)

    def test_tracked_foreign_hook_is_left_alone(self):
        subprocess.run(["git", "-C", self.d, "config", "core.hooksPath", ".githooks"], check=True)
        self.put(".githooks/pre-commit", "#!/bin/sh\n")
        subprocess.run(["git", "-C", self.d, "add", ".githooks/pre-commit"], check=True)
        code, out = run("sync", cwd=self.d)
        self.assertIn("NOT installed", out)
        self.assertEqual(open(os.path.join(self.d, ".githooks/pre-commit")).read(), "#!/bin/sh\n")

    def test_skips_non_oro_and_non_git(self):
        os.remove(os.path.join(self.d, "composer.json"))
        self.assertEqual(precommit.state(self.d), ("skipped", "not an Oro project"))
        with tempfile.TemporaryDirectory() as plain:
            self.assertEqual(precommit.state(plain), ("skipped", "not a git repository"))

    def test_missing_vendor_tool_is_drift_with_fix(self):
        self.put("bitbucket-pipelines.yml", BITBUCKET)
        miss = dict(precommit.missing_tools(self.d))
        self.assertEqual(miss["vendor/squizlabs/php_codesniffer/bin/phpcs"], "composer install")
        code, out = run("status", cwd=self.d)
        self.assertIn("hook-tools", out)
        self.assertIn("fix: composer install", out)

    def test_hook_runs_steps_and_fails_on_a_failing_one(self):
        self.put("bitbucket-pipelines.yml", "pipelines:\n  default:\n    - step:\n        script:\n          - vendor/bin/phpunit\n")
        run("sync", cwd=self.d)
        os.chmod(self.put("vendor/bin/phpunit", "#!/bin/sh\nexit 1\n"), 0o755)
        p = subprocess.run([self.hook()], cwd=self.d, capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn("xxx PHPUnit FAILED", p.stderr)
        self.put("vendor/bin/phpunit", "#!/bin/sh\nexit 0\n")
        self.assertEqual(subprocess.run([self.hook()], cwd=self.d, capture_output=True).returncode, 0)


STUB = '#!/bin/sh\nprintf "%s\\n" "$@" >> "$STUB_LOG.$(basename "$0")"\nexit ${STUB_EXIT:-0}\n'
CI_WHOLE_TREE = """pipelines:
  default:
    - step:
        script:
          - php ./vendor/squizlabs/php_codesniffer/bin/phpcs ./src --extensions=php --standard=PSR2 --ignore=OroLab -q
          - php ./vendor/phpmd/phpmd/src/bin/phpmd ./src ansi ./phpmd.xml --suffixes php --exclude OroLab
          - npm run eslint src -- --ignore-pattern "src/OroLab/**"
          - npm run stylelint src/Buckman/**/*.scss
          - yamllint ./src/
"""


class HookRunBase(RepoCase):
    """Runs the rendered hook against stub tools that record their argv, in a real git repo."""

    def setUp(self):
        super().setUp()
        self.bin = os.path.join(self.d, ".stubs")
        self.log = os.path.join(self.d, ".stublog")
        os.makedirs(self.bin)
        for tool in ("npm", "yamllint", "php"):
            self.stub(os.path.join(self.bin, tool))

    def stub(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(STUB)
        os.chmod(path, 0o755)

    def git(self, *args):
        subprocess.run(["git", "-C", self.d, *args], check=True, capture_output=True)

    def hook_env(self, **extra):
        env = dict(os.environ, HOME=self.d, STUB_LOG=self.log, PATH=self.bin + os.pathsep + os.environ["PATH"])
        env.pop("ORO_ENV", None)
        env.pop("APP_ENV", None)
        env.pop("ORO_DB_URL", None)
        env.update(extra)
        return env

    def run_hook(self, **extra):
        p = subprocess.run([self.hook()], cwd=self.d, capture_output=True, text=True, env=self.hook_env(**extra))
        return p.returncode, p.stdout + p.stderr

    def argv(self, tool):
        path = "%s.%s" % (self.log, tool)
        if not os.path.exists(path):
            return None
        with open(path) as fh:
            return fh.read().split("\n")


class HookRunTest(HookRunBase):
    def whole_tree_project(self):
        self.put("bitbucket-pipelines.yml", CI_WHOLE_TREE)
        self.put("phpmd.xml", "<x/>")
        self.put("package.json", "{}")
        self.put(".yamllint", "extends: default\n")
        for tool in ("phpcs", "phpmd"):
            self.stub(os.path.join(self.d, "vendor", tool))
        self.put("bitbucket-pipelines.yml", CI_WHOLE_TREE.replace(
            "php ./vendor/squizlabs/php_codesniffer/bin/phpcs", "vendor/phpcs").replace(
            "php ./vendor/phpmd/phpmd/src/bin/phpmd", "vendor/phpmd"))
        self.put("src/Buckman/ok.php", "<?php\n")
        self.put("src/Buckman/ok.yml", "a: 1\n")
        self.put("src/Aaxis/Bundle/AppBundle/Bad.php", "<?php\n")
        self.put("src/Aaxis/Bundle/AppBundle/bad.yml", "a:  1\n")
        with open(os.path.join(self.d, ".git", "info", "exclude"), "a") as fh:
            fh.write("src/Aaxis/Bundle/AppBundle/\n")
        self.git("add", "src/Buckman", "composer.json", "package.json", "phpmd.xml", ".yamllint", "bitbucket-pipelines.yml")
        run("sync", cwd=self.d)

    def test_git_excluded_paths_never_reach_whole_tree_steps(self):
        self.whole_tree_project()
        code, out = self.run_hook()
        self.assertEqual(code, 0, out)
        ignore = "*/src/Aaxis/Bundle/AppBundle/*"
        phpcs = [a for a in self.argv("phpcs") if a.startswith("--ignore=")]
        self.assertEqual(len(phpcs), 1)
        self.assertTrue(phpcs[0].startswith("--ignore=OroLab,"), phpcs)
        self.assertIn(ignore, phpcs[0].split(","))
        phpmd = [a for a in self.argv("phpmd") if a.startswith("OroLab,")]
        self.assertIn(ignore, phpmd[0].split(","))
        eslint = self.argv("npm")
        self.assertIn("src/Aaxis/Bundle/AppBundle/**", eslint)
        self.assertIn("src/OroLab/**", eslint)

    def test_phpcs_runs_parallel_with_a_per_checkout_cache(self):
        self.whole_tree_project()
        code, out = self.run_hook()
        self.assertEqual(code, 0, out)
        argv = self.argv("phpcs")
        jobs = [a for a in argv if a.startswith("--parallel=")]
        self.assertEqual(len(jobs), 1, argv)
        self.assertGreaterEqual(int(jobs[0].split("=")[1]), 1)
        cache = [a for a in argv if a.startswith("--cache=")]
        self.assertEqual(cache, ["--cache=%s" % os.path.join(os.path.realpath(self.d), ".git", "phpcs.cache")])
        self.assertFalse([a for a in self.argv("phpmd") if "--parallel" in a])

    def test_hook_passes_error_reporting_to_php_for_phpmd(self):
        self.put("bitbucket-pipelines.yml", CI_WHOLE_TREE)
        self.put("phpmd.xml", "<x/>")
        run("sync", cwd=self.d)
        code, out = self.run_hook()
        self.assertEqual(code, 0, out)
        argv = self.argv("php")
        self.assertIn("error_reporting=E_ALL & ~E_DEPRECATED", argv)
        self.assertIn("./vendor/phpmd/phpmd/src/bin/phpmd", argv)
        self.assertIn("content", argv)
        self.assertIn(os.path.join(os.path.realpath(self.d), ".git", "phpmd.result-cache.php"), argv)

    def test_cpu_count_falls_back_to_getconf_then_one(self):
        self.whole_tree_project()
        bare = os.path.join(self.d, ".nonproc")
        os.makedirs(bare)
        for tool in ("bash", "git", "grep", "sort", "mktemp", "cat", "dirname", "basename", "rm"):
            os.symlink(subprocess.run(["which", tool], capture_output=True, text=True).stdout.strip(), os.path.join(bare, tool))
        for tool in ("phpcs", "phpmd"):
            pass
        env = self.hook_env(PATH=bare + os.pathsep + self.bin)
        subprocess.run([self.hook()], cwd=self.d, capture_output=True, text=True, env=env)
        self.assertIn("--parallel=1", self.argv("phpcs"))

    def test_yamllint_receives_only_tracked_files(self):
        self.whole_tree_project()
        self.run_hook()
        args = self.argv("yamllint")
        self.assertIn("src/Buckman/ok.yml", args)
        self.assertNotIn("src/Aaxis/Bundle/AppBundle/bad.yml", args)
        self.assertNotIn("./src/", args)

    def test_precommit_exclude_config_adds_paths_and_globs(self):
        self.whole_tree_project()
        self.put(".oro-ai/config.json", json.dumps({"precommit": {"exclude": ["src/Legacy", "src/Gen/*.php"]}}))
        run("sync", cwd=self.d)
        self.run_hook()
        phpcs = "".join(self.argv("phpcs")).split(",")
        self.assertIn("*/src/Legacy", phpcs)
        self.assertIn("*/src/Gen/*.php", phpcs)
        self.assertIn("src/Gen/*.php", self.argv("npm"))

    def test_steps_with_no_matching_staged_file_type_are_skipped(self):
        self.put("bitbucket-pipelines.yml", "pipelines:\n  default:\n    - step:\n        script:\n          - vendor/bin/phpunit\n          - yamllint ./src/\n")
        self.put("src/readme.md", "x\n")
        self.git("add", "src/readme.md")
        self.stub(os.path.join(self.d, "vendor", "bin", "phpunit"))
        run("sync", cwd=self.d)
        code, out = self.run_hook(STUB_EXIT="1")
        self.assertEqual(code, 0, out)
        self.assertIn("PHPUnit skipped", out)
        self.assertIsNone(self.argv("phpunit"))
        self.put("src/A.php", "<?php\n")
        self.git("add", "src/A.php")
        code, out = self.run_hook(STUB_EXIT="1")
        self.assertEqual(code, 1)
        self.assertIn("xxx PHPUnit FAILED", out)
        self.assertIn("YamlLint skipped", out)

    def test_run_all_env_overrides_the_staged_type_gate(self):
        self.put("bitbucket-pipelines.yml", "pipelines:\n  default:\n    - step:\n        script:\n          - vendor/bin/phpunit\n")
        self.stub(os.path.join(self.d, "vendor", "bin", "phpunit"))
        self.put("README.md", "x\n")
        self.git("add", "README.md")
        run("sync", cwd=self.d)
        self.assertEqual(self.run_hook(STUB_EXIT="1")[0], 0)
        self.assertEqual(self.run_hook(STUB_EXIT="1", AAXIS_ORO_PRECOMMIT_ALL="1")[0], 1)

    def test_nothing_staged_runs_every_step(self):
        self.put("bitbucket-pipelines.yml", "pipelines:\n  default:\n    - step:\n        script:\n          - vendor/bin/phpunit\n")
        self.stub(os.path.join(self.d, "vendor", "bin", "phpunit"))
        run("sync", cwd=self.d)
        self.assertEqual(self.run_hook(STUB_EXIT="1")[0], 1)


class SchemaDriftTest(HookRunBase):
    def drift_project(self, sql):
        self.put("bin/console", "")
        self.put("src/Acme/Entity/Thing.php", "<?php\n")
        self.git("add", "src/Acme/Entity/Thing.php")
        self.sql = sql
        with open(os.path.join(self.bin, "php"), "w") as fh:
            fh.write('#!/bin/sh\nprintf "%s\\n" "$@" >> "$STUB_LOG.php"\nprintf "%s" "$STUB_SQL"\n[ -n "$STUB_ERR" ] && { echo "$STUB_ERR" >&2; exit 2; }\nexit 0\n')
        run("sync", cwd=self.d)

    def test_step_added_for_oro_projects_with_console_and_opt_out_via_skip(self):
        self.assertNotIn("schema-drift", [s[0] for s in precommit.steps(self.d)])
        self.put("bin/console", "")
        self.assertIn("schema-drift", [s[0] for s in precommit.steps(self.d)])
        self.put(".oro-ai/config.json", json.dumps({"precommit": {"skip": ["schema-drift"]}}))
        self.assertNotIn("schema-drift", [s[0] for s in precommit.steps(self.d)])

    def test_real_drift_fails_with_the_statement_and_uses_the_local_prod_kernel(self):
        self.drift_project("")
        code, out = self.run_hook(STUB_SQL="DROP INDEX uniq_x;\n")
        self.assertEqual(code, 1, out)
        self.assertIn("DROP INDEX uniq_x;", out)
        self.assertIn("xxx Doctrine schema drift FAILED", out)
        args = self.argv("php")
        self.assertIn("doctrine:schema:update", args)
        self.assertIn("--dump-sql", args)
        self.assertIn("--env=prod", args)

    def test_in_sync_and_noise_only_output_passes(self):
        self.drift_project("")
        noise = "\n -- comment\n [OK] Nothing to update - your database is already in sync with the current entity metadata.\n\n"
        self.assertEqual(self.run_hook(STUB_SQL=noise)[0], 0)
        self.assertEqual(self.run_hook(STUB_SQL="")[0], 0)

    def test_incomplete_database_is_reported_as_such_not_as_drift(self):
        self.drift_project("")
        sql = "".join("ALTER TABLE t%d ADD CONSTRAINT FK_%d FOREIGN KEY (a) REFERENCES b (id);\n" % (i, i) for i in range(60))
        code, out = self.run_hook(STUB_SQL=sql)
        self.assertEqual(code, 1)
        self.assertIn("database looks incomplete", out)
        self.assertNotIn("FK_59", out)

    def test_console_failure_is_unrun_not_passed(self):
        self.drift_project("")
        code, out = self.run_hook(STUB_ERR="no database")
        self.assertEqual(code, 1)
        self.assertIn("could not run", out)
        self.assertIn("skip", out)

    def test_refuses_the_test_stack(self):
        self.drift_project("")
        for env in ({"ORO_ENV": "behat_test"}, {"APP_ENV": "test"}, {"ORO_DB_URL": "postgresql://u:p@h/oro_test"}):
            code, out = self.run_hook(**env)
            self.assertEqual(code, 1, env)
            self.assertIn("refusing", out)

    def test_skipped_when_no_entity_or_migration_file_is_staged(self):
        self.drift_project("")
        self.git("reset", "-q", "src/Acme/Entity/Thing.php")
        self.put("src/Acme/Util.php", "<?php\n")
        self.git("add", "src/Acme/Util.php")
        code, out = self.run_hook(STUB_SQL="DROP INDEX x;\n")
        self.assertEqual(code, 0, out)
        self.assertIn("Doctrine schema drift skipped", out)
        self.assertFalse(os.path.exists(self.log + ".php"))


class OldHookInventoryTest(RepoCase):
    def test_sync_lists_old_hook_steps_that_have_no_managed_equivalent(self):
        self.put("bitbucket-pipelines.yml", BITBUCKET)
        subprocess.run(["git", "-C", self.d, "config", "core.hooksPath", ".githooks"], check=True)
        self.put(".githooks/pre-commit", (
            '#!/usr/bin/env bash\nrun_step "PHP CodeSniffer (PSR2)" \\\n    php ./vendor/bin/phpcs ./src\n'
            'run_step "Translation parity" bin/check-translations\n'
            'echo "==> Doctrine schema drift"\nphp bin/console doctrine:schema:update --dump-sql\n'))
        code, out = run("sync", cwd=self.d)
        self.assertIn("no managed equivalent", out)
        self.assertIn("Translation parity", out)
        self.assertNotIn("PHP CodeSniffer", out.split("no managed equivalent")[1])
        self.assertIn("backed up to", out)

    def test_dry_run_lists_them_too_and_a_fully_covered_hook_prints_nothing(self):
        self.put("bitbucket-pipelines.yml", BITBUCKET)
        subprocess.run(["git", "-C", self.d, "config", "core.hooksPath", ".githooks"], check=True)
        self.put(".githooks/pre-commit", '#!/bin/sh\nrun_step "x" vendor/bin/phpunit\n')
        self.assertNotIn("no managed equivalent", run("sync", "--dry-run", cwd=self.d)[1])
        docker = '#!/bin/sh\nrun_step() { echo "==> ${name}"; }\nrun_step "YamlLint (docker)" \\\n    docker run --rm cytopia/yamllint:latest ./src/\n'
        self.put(".githooks/pre-commit", docker)
        self.assertNotIn("no managed equivalent", run("sync", "--dry-run", cwd=self.d)[1])
        self.put(".githooks/pre-commit", '#!/bin/sh\nrun_step "Lint SQL" bin/lint-sql\n')
        self.assertIn("Lint SQL", run("sync", "--dry-run", cwd=self.d)[1])


def git_status(d):
    return subprocess.run(["git", "-C", d, "status", "--porcelain"], capture_output=True, text=True).stdout


if __name__ == "__main__":
    unittest.main()
