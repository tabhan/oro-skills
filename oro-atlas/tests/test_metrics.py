import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


adoption = load("atlas_adoption", os.path.join(ROOT, "bin", "atlas-adoption"))
sys.path.insert(0, os.path.join(ROOT, "eval"))
import run_eval  # noqa: E402

EDIT = "/opt/projects/buckman/src/Buckman/Bundle/ProductBundle/EventListener/SlugListener.php"


def transcript(tool_uses):
    return "".join(json.dumps({"type": "assistant", "timestamp": f"2026-01-01T00:00:{i:02d}",
                               "message": {"content": [{"type": "tool_use", "name": n, "input": inp}]}}) + "\n"
                   for i, (n, inp) in enumerate(tool_uses))


class AdoptionTest(unittest.TestCase):
    def test_only_real_atlas_invocations(self):
        self.assertEqual(adoption.atlas_argvs("bin/atlas event slug"), [["event", "slug"]])
        self.assertEqual(adoption.atlas_argvs("cd x && FOO=1 atlas service p"), [["service", "p"]])
        for cmd in ("bin/atlas-build --project x", "atlas-adoption", "grep atlas foo", "ls /x/atlas/"):
            self.assertEqual(adoption.atlas_argvs(cmd), [], cmd)

    def test_relevance(self):
        self.assertTrue(adoption.relevant(["event", "slug"], EDIT))
        self.assertFalse(adoption.relevant(["status"], EDIT))
        self.assertFalse(adoption.relevant(["event", "order"], EDIT))
        self.assertFalse(adoption.relevant(["service", "oro_bundle.listener"], EDIT))

    def test_relevance_skips_flags_and_help(self):
        self.assertTrue(adoption.relevant(["--project", "/x", "events", "slug", "--limit", "9"], EDIT))
        self.assertFalse(adoption.relevant(["--project", "/x", "status"], EDIT))
        self.assertFalse(adoption.relevant(["event", "slug", "--help"], EDIT))

    def collect(self, uses):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "s1.jsonl"), "w") as fh:
                fh.write(transcript(uses))
            return adoption.collect(d)["s1"]

    def test_coverage_requires_prior_relevant_lookup(self):
        edit = ("Edit", {"file_path": EDIT})
        self.assertEqual(self.collect([("Bash", {"command": "atlas status"}), edit])["covered"], 0)
        self.assertEqual(self.collect([edit, ("Bash", {"command": "atlas event slug"})])["covered"], 0)
        row = self.collect([("Bash", {"command": "atlas event slug"}), edit])
        self.assertEqual((row["covered"], row["atlas"]), (1, 1))

    def test_denies_from_structured_verdict(self):
        rows = {"abc": {"denies": 0}}
        lines = [{"session_id": "abc", "verdict": "deny"}, {"session_id": "abc", "verdict": "nudge",
                                                             "file": "/x/blocker.php"},
                 {"session_id": None, "verdict": "deny"}]
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as fh:
            fh.write("\n".join(json.dumps(x) for x in lines) + "\nnot json block\n")
        try:
            self.assertEqual(adoption.hook_denies(fh.name, rows), 2)
            self.assertEqual(rows["abc"]["denies"], 1)
        finally:
            os.unlink(fh.name)


class EvalTest(unittest.TestCase):
    def ev(self, cmd):
        return [{"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}]

    def test_atlas_calls_command_word_only(self):
        self.assertEqual(run_eval.atlas_calls(self.ev("grep -r atlas . | head")), [])
        self.assertEqual(run_eval.atlas_calls(self.ev("atlas-build --project x")), [])
        self.assertEqual([s for _, s in run_eval.atlas_calls(self.ev("ls; /p/bin/atlas grid products"))], ["grid"])

    def test_help_and_status_are_not_activation(self):
        for cmd in ("atlas --help", "atlas status", "atlas event --help", "atlas -h"):
            self.assertEqual(run_eval.atlas_calls(self.ev(cmd)), [], cmd)

    def test_plural_subcommands_accepted(self):
        subs = [s for _, s in run_eval.atlas_calls(self.ev("atlas --project /p entities product; atlas configs x"))]
        self.assertEqual(subs, ["entity", "config"])

    def test_run_path_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path
            first = run_eval.run_path("x", Path(d))
            first.write_text("{}")
            self.assertEqual((first.name, run_eval.run_path("x", Path(d)).name), ("x-1.jsonl", "x-2.jsonl"))

    def test_model_recorded_from_init_event(self):
        evs = [{"type": "system", "subtype": "init", "model": "claude-sonnet-x"}]
        self.assertEqual(run_eval.run_model(evs, None), "claude-sonnet-x")
        self.assertEqual(run_eval.run_model([], "opus"), "opus")

    def test_inconclusive_runs_excluded(self):
        self.assertEqual(run_eval.verdict(0, {"subtype": "success"}), "ok")
        self.assertEqual(run_eval.verdict(1, {"subtype": "success"}), "inconclusive")
        self.assertEqual(run_eval.verdict(0, {"subtype": "error_max_budget_usd"}), "inconclusive")
        self.assertEqual(run_eval.verdict(0, {}), "inconclusive")
        rows = [{"status": "ok", "invoked": True, "right_subcommand": False},
                {"status": "inconclusive", "invoked": False, "right_subcommand": False}]
        self.assertIn("activation 1/1 (100%)", run_eval.summary(rows))
        self.assertIn("correct-subcommand 0/1 (0%)", run_eval.summary(rows))

    def test_prompt_not_terse(self):
        self.assertNotIn("briefly", run_eval.GUARD.lower())


if __name__ == "__main__":
    unittest.main()
