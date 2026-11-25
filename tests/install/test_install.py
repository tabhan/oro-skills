import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

import json


class ShimResolutionTest(unittest.TestCase):
    """The installed shim runs the installed plugin's CLI, not the clone that ran install.sh."""

    def fake_plugin(self, home, name):
        d = home / "cache" / name
        (d / "bin").mkdir(parents=True)
        cli = d / "bin" / "aaxis-oro"
        cli.write_text('#!/bin/sh\necho "%s $@"\n' % name)
        cli.chmod(0o755)
        return d

    def entry(self, d, version, scope):
        return {"scope": scope, "installPath": str(d), "version": version}

    def setup_home(self, tmp, entries):
        home = Path(tmp)
        plugins = home / ".claude" / "plugins"
        plugins.mkdir(parents=True)
        (plugins / "installed_plugins.json").write_text(
            json.dumps({"version": 2, "plugins": {"aaxis-oro@aaxis-oro": entries, "other@x": []}}))
        bin_dir = home / ".local" / "bin"
        r = subprocess.run(
            ["bash", str(ROOT / "install.sh"), "--no-update", "--no-plugin", "--no-official-plugins", "--project", str(home)],
            env={"HOME": str(home), "PATH": os.environ["PATH"]}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return bin_dir / "aaxis-oro"

    def run_shim(self, shim, home, **extra):
        env = {"HOME": str(home), "PATH": os.environ["PATH"], **extra}
        return subprocess.run([str(shim), "ping"], env=env, capture_output=True, text=True)

    def test_user_scope_wins_over_higher_local_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            a = self.fake_plugin(home, "v0.28.6")
            b = self.fake_plugin(home, "v0.29.2")
            shim = self.setup_home(tmp, [self.entry(b, "0.29.2", "local"), self.entry(a, "0.28.6", "user")])
            r = self.run_shim(shim, home)
            self.assertEqual(r.stdout.strip(), "v0.28.6 ping", r.stderr)
            self.assertEqual(r.stderr, "")

    def test_highest_version_when_no_user_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            a = self.fake_plugin(home, "v0.9.0")
            b = self.fake_plugin(home, "v0.10.0")
            shim = self.setup_home(tmp, [self.entry(a, "0.9.0", "project"), self.entry(b, "0.10.0", "local")])
            self.assertEqual(self.run_shim(shim, home).stdout.strip(), "v0.10.0 ping")

    def test_oro_skills_dir_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            a = self.fake_plugin(home, "plugin")
            dev = self.fake_plugin(home, "dev")
            shim = self.setup_home(tmp, [self.entry(a, "1.0.0", "user")])
            self.assertEqual(self.run_shim(shim, home, ORO_SKILLS_DIR=str(dev)).stdout.strip(), "dev ping")

    def test_fallback_to_clone_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            shim = self.setup_home(tmp, [])
            r = self.run_shim(shim, home)
            self.assertIn("no installed aaxis-oro plugin found", r.stderr)
            self.assertIn(str(ROOT), r.stderr)


class InstallLegacyLinksTest(unittest.TestCase):
    def run_install(self, home):
        env = {**os.environ, "HOME": str(home), "PATH": os.environ["PATH"]}
        for k in ("CLAUDE_SKILLS_DIR", "CLAUDE_AGENTS_DIR", "ORO_ATLAS_BIN_DIR"):
            env.pop(k, None)
        return subprocess.run(
            ["bash", str(ROOT / "install.sh"), "--no-update", "--no-plugin", "--no-official-plugins",
             "--project", str(home)],
            env=env, capture_output=True, text=True,
        )

    def test_reaches_cli_link_with_dangling_and_foreign_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            bin_dir = home / ".local" / "bin"
            (home / ".claude" / "skills").mkdir(parents=True)
            bin_dir.mkdir(parents=True)
            foreign = home / "foreign-tool"
            foreign.write_text("x")
            (bin_dir / "atlas").symlink_to(ROOT / "removed" / "gone" / "atlas")  # dangling, ours
            (bin_dir / "atlas-old").symlink_to(ROOT / "bin" / "aaxis-oro")  # live, ours
            (bin_dir / "atlas-foreign").symlink_to(foreign)  # foreign, kept
            (bin_dir / "atlas-dangling-foreign").symlink_to(home / "nope" / "x")  # foreign dangling, kept

            r = self.run_install(home)

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse((bin_dir / "aaxis-oro").is_symlink())
            self.assertTrue(os.access(bin_dir / "aaxis-oro", os.X_OK))
            self.assertFalse((bin_dir / "atlas").is_symlink())
            self.assertFalse((bin_dir / "atlas-old").is_symlink())
            self.assertTrue((bin_dir / "atlas-foreign").is_symlink())
            self.assertTrue((bin_dir / "atlas-dangling-foreign").is_symlink())

    def test_empty_dirs_do_not_abort(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_install(Path(tmp))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue((Path(tmp) / ".local" / "bin" / "aaxis-oro").is_file())


if __name__ == "__main__":
    unittest.main()
