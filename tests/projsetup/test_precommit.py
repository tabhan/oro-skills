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


class PrecommitTest(unittest.TestCase):
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


def git_status(d):
    return subprocess.run(["git", "-C", d, "status", "--porcelain"], capture_output=True, text=True).stdout


if __name__ == "__main__":
    unittest.main()
