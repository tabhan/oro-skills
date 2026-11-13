import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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
            self.assertEqual((bin_dir / "aaxis-oro").resolve(), (ROOT / "bin" / "aaxis-oro").resolve())
            self.assertFalse((bin_dir / "atlas").is_symlink())
            self.assertFalse((bin_dir / "atlas-old").is_symlink())
            self.assertTrue((bin_dir / "atlas-foreign").is_symlink())
            self.assertTrue((bin_dir / "atlas-dangling-foreign").is_symlink())

    def test_empty_dirs_do_not_abort(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_install(Path(tmp))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue((Path(tmp) / ".local" / "bin" / "aaxis-oro").is_symlink())


if __name__ == "__main__":
    unittest.main()
