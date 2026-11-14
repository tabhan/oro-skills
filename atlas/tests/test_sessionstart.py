import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_hooks import HOOKS, Base, run  # noqa: E402

sys.path.insert(0, HOOKS)
import sessionstart  # noqa: E402

SINGLES = ("sessionstart_legacy.py", "sessionstart_migrate.py", "sessionstart_version.py",
           "sessionstart_atlas.py", "sessionstart_notes.py")


class PlanTest(unittest.TestCase):
    def test_matcher_semantics_per_source(self):
        self.assertEqual(sessionstart.steps("startup"), sessionstart.ONCE + sessionstart.ALWAYS)
        self.assertEqual(sessionstart.steps("resume"), sessionstart.ONCE + sessionstart.ALWAYS)
        self.assertEqual(sessionstart.steps("compact"), sessionstart.ALWAYS)
        self.assertEqual(sessionstart.steps("clear"), ())
        self.assertEqual(sessionstart.steps(None), sessionstart.ONCE + sessionstart.ALWAYS)

    def test_merge_joins_contexts_and_messages(self):
        a = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "one"}}
        b = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "two"}, "systemMessage": "m"}
        self.assertEqual(sessionstart.merge([None, a, b]), {"hookSpecificOutput": {"hookEventName": "SessionStart",
                         "additionalContext": "one\ntwo"}, "systemMessage": "m"})
        self.assertIsNone(sessionstart.merge([None, None]))


class DispatcherTest(Base):
    def setUp(self):
        super().setUp()
        self.build_index()
        os.utime(os.path.join(self.root, "src", "Foo"), None)
        with open(os.path.join(self.root, "src", "Foo", "late.yml"), "w") as fh:
            fh.write("a: 1\n")  # makes the index stale: the atlas step reports it
        with open(os.path.join(self.root, ".oro-ai", "version-announced.json"), "w") as fh:
            json.dump({"version": "6.1.0"}, fh)

    def payload(self, source):
        return {"session_id": "ss", "hook_event_name": "SessionStart", "source": source, "cwd": self.root}

    def context(self, out):
        return ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")

    def test_startup_runs_every_step_and_equals_the_separate_hooks(self):
        _, out = run("sessionstart.py", self.payload("startup"), self.home)
        ctx = self.context(out)
        self.assertIn("[atlas]", ctx)
        self.assertIn("Oro version changed 6.1.0", ctx)
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
        # Re-arm the version marker, then compare with the five hooks run one by one, as they used to be registered.
        with open(os.path.join(self.root, ".oro-ai", "version-announced.json"), "w") as fh:
            json.dump({"version": "6.1.0"}, fh)
        parts = [self.context(run(s, self.payload("startup"), self.home)[1]) for s in SINGLES]
        self.assertEqual(ctx, "\n".join(p for p in parts if p))

    def test_compact_skips_the_once_per_session_steps(self):
        _, out = run("sessionstart.py", self.payload("compact"), self.home)
        ctx = self.context(out)
        self.assertIn("[atlas]", ctx)
        self.assertNotIn("Oro version changed", ctx)
        with open(os.path.join(self.root, ".oro-ai", "version-announced.json")) as fh:
            self.assertEqual(json.load(fh)["version"], "6.1.0")  # the version step did not run

    def test_resume_behaves_like_startup(self):
        _, out = run("sessionstart.py", self.payload("resume"), self.home)
        self.assertIn("Oro version changed", self.context(out))

    def test_clear_runs_nothing(self):
        self.assertEqual(run("sessionstart.py", self.payload("clear"), self.home), (0, None))

    def test_enforcement_off_message_is_kept(self):
        _, out = run("sessionstart.py", self.payload("compact"), self.home, {"ORO_ATLAS_ENFORCE": "0"})
        self.assertIn("atlas enforcement is OFF", out["systemMessage"])

    def test_fails_open_on_garbage_and_outside_oro(self):
        p = subprocess.run([sys.executable, os.path.join(HOOKS, "sessionstart.py")], input="{no", capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (0, ""))
        import tempfile
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(run("sessionstart.py", dict(self.payload("startup"), cwd=other), self.home), (0, None))

    def test_registered_once_with_all_three_sources(self):
        with open(os.path.join(HOOKS, "..", "..", "hooks", "hooks.json")) as fh:
            groups = json.load(fh)["hooks"]["SessionStart"]
        self.assertEqual([g["matcher"] for g in groups], ["startup|resume|compact"])
        self.assertEqual(len(groups[0]["hooks"]), 1)


if __name__ == "__main__":
    unittest.main()
