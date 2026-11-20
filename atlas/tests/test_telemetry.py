import http.server
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest

HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
REPO = os.path.abspath(os.path.join(HOOKS, "..", ".."))
sys.path.insert(0, HOOKS)

import telemetry as T  # noqa: E402

SCRIPT = os.path.join(HOOKS, "telemetry.py")
UUID4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
ISO = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
TOKEN = "ghp_SECRETTOKEN123"
# Contract fields (docs/TELEMETRY_API.md): the only keys an event may carry.
ALLOWED = {"event_id", "type", "occurred_at", "session_id", "user", "client", "project", "data"}
GROUPS = {"user": {"git_name", "git_email", "os_user"},
          "client": {"hostname", "os", "plugin_version", "claude_code_version", "model"},
          "project": {"repo_url", "branch", "commit", "oro_version"}}
DATA = {"session_start": {"source"}, "session_end": {"reason", "duration_s", "prompt_count", "tool_count"},
        "skill_used": {"name"}, "command_used": {"name"}}


def validate(test, event):
    """Assert `event` satisfies the contract: required fields, types, max lengths, no unknown keys."""
    test.assertLessEqual(set(event), ALLOWED)
    test.assertRegex(event["event_id"], UUID4)
    test.assertIn(event["type"], T.TYPES)
    test.assertRegex(event["occurred_at"], ISO)
    test.assertTrue(0 < len(event["session_id"]) <= 100)
    test.assertTrue(event["client"]["plugin_version"])
    for group, keys in GROUPS.items():
        test.assertLessEqual(set(event.get(group, {})), keys)
        for key, value in event.get(group, {}).items():
            test.assertIsInstance(value, str)
            test.assertLessEqual(len(value), T.LIMITS[key])
    test.assertLessEqual(set(event.get("data", {})), DATA[event["type"]])
    for key in ("duration_s", "prompt_count", "tool_count"):
        if key in event.get("data", {}):
            test.assertIsInstance(event["data"][key], int)


def sh(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, env=dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null",
                                                                            GIT_CONFIG_SYSTEM="/dev/null"))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(self.home)
        self.saved = {k: os.environ.get(k) for k in ("HOME", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM")}
        os.environ.update(HOME=self.home, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
        self.proj = os.path.join(self.tmp.name, "proj")
        os.makedirs(self.proj)
        sh(["git", "init", "-q", "-b", "feature/ABC-1"], self.proj)
        sh(["git", "config", "user.name", "Jane Doe"], self.proj)
        sh(["git", "config", "user.email", "jane@example.com"], self.proj)
        sh(["git", "remote", "add", "origin", "https://jane:%s@github.com/acme/shop.git" % TOKEN], self.proj)
        sh(["git", "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "x"], self.proj)
        os.makedirs(os.path.join(self.proj, "bin"))
        open(os.path.join(self.proj, "bin", "console"), "w").close()  # Oro root layout: bin/console + composer.lock
        with open(os.path.join(self.proj, "composer.lock"), "w") as fh:
            json.dump({"packages": [{"name": "oro/platform", "version": "6.1.2"}]}, fh)
        # a fake `claude` keeps the version lookup off the real binary
        self.bin = os.path.join(self.tmp.name, "bin")
        os.makedirs(self.bin)
        fake = os.path.join(self.bin, "claude")
        with open(fake, "w") as fh:
            fh.write("#!/bin/sh\necho '2.3.1 (Claude Code)'\n")
        os.chmod(fake, 0o755)
        self.path = os.environ["PATH"]
        os.environ["PATH"] = self.bin + os.pathsep + self.path
        self.endpoint = T.ENDPOINT

    def tearDown(self):
        T.ENDPOINT = self.endpoint
        os.environ["PATH"] = self.path
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def payload(self, **kw):
        base = {"session_id": "sess-1", "cwd": self.proj, "hook_event_name": "SessionStart", "source": "startup",
                "model": "claude-opus-5-5"}
        base.update(kw)
        return base

    def event_for(self, payload, now=None):
        job = T.build_job(payload, now)
        self.assertIsNotNone(job)
        return T.build_event(json.loads(json.dumps(job)), now)


class NormalizeTest(unittest.TestCase):
    def test_forms(self):
        n = T.normalize_repo_url
        self.assertEqual(n("https://github.com/acme/shop.git"), "https://github.com/acme/shop")
        self.assertEqual(n("https://u:%s@github.com/acme/shop" % TOKEN), "https://github.com/acme/shop")
        self.assertEqual(n("https://%s@github.com/acme/shop.git" % TOKEN), "https://github.com/acme/shop")
        self.assertEqual(n("git@github.com:acme/shop.git"), "https://github.com/acme/shop")
        self.assertEqual(n("ssh://git@github.com:22/acme/shop.git"), "https://github.com/acme/shop")
        self.assertEqual(n("https://x-token-auth:%s@bitbucket.org/acme/shop.git/" % TOKEN), "https://bitbucket.org/acme/shop")
        self.assertIsNone(n(""))
        self.assertIsNone(n(None))
        self.assertIsNone(n("/local/path/repo"))
        for url in ("https://u:%s@github.com/a/b?x=1#f" % TOKEN, "git@github.com:a/b.git"):
            self.assertNotIn(TOKEN, n(url))


class EventTypeTest(unittest.TestCase):
    def test_mapping(self):
        e = T.event_type
        self.assertEqual(e({"hook_event_name": "SessionStart", "source": "resume"}), ("session_start", {"source": "resume"}))
        self.assertEqual(e({"hook_event_name": "SessionEnd", "reason": "logout"}), ("session_end", {"reason": "logout"}))
        self.assertEqual(e({"hook_event_name": "PostToolUse", "tool_name": "Skill", "tool_input": {"skill": "tab-jira", "args": "SECRET"}}),
                         ("skill_used", {"name": "tab-jira"}))
        self.assertEqual(e({"hook_event_name": "UserPromptSubmit", "prompt": "/aaxis-oro:review ABC-1 secret text"}),
                         ("skill_used", {"name": "aaxis-oro:review"}))

    def test_bash_subcommand_only(self):
        def bash(cmd):
            return T.event_type({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}})
        self.assertEqual(bash("bin/aaxis-oro atlas search Foo --project /x"), ("command_used", {"name": "atlas"}))
        self.assertEqual(bash("cd x && FOO=1 aaxis-oro env status"), ("command_used", {"name": "env"}))
        self.assertEqual(bash("ls | aaxis-oro dev lint"), ("command_used", {"name": "dev"}))
        self.assertEqual(bash("ls -la"), (None, None))
        self.assertEqual(bash("echo aaxis-oro env"), (None, None))  # mention, not an invocation

    def test_not_reported(self):
        e = T.event_type
        self.assertEqual(e({"hook_event_name": "UserPromptSubmit", "prompt": "/clear"}), (None, None))
        self.assertEqual(e({"hook_event_name": "UserPromptSubmit", "prompt": "fix aaxis-oro:review"}), (None, None))
        self.assertEqual(e({"hook_event_name": "PostToolUse", "tool_name": "Read"}), (None, None))
        self.assertEqual(e({"hook_event_name": "Stop"}), (None, None))
        self.assertEqual(e({"hook_event_name": "PostToolUse", "tool_name": "Skill", "tool_input": {}}), (None, None))


class JobTest(Base):
    def test_job_carries_no_prompt_or_tool_input(self):
        p = self.payload(hook_event_name="UserPromptSubmit", prompt="/aaxis-oro:review my password is hunter2",
                         transcript_path="/t.jsonl")
        job = T.build_job(p)
        self.assertNotIn("hunter2", json.dumps(job))
        self.assertIsNone(job["transcript_path"])  # only session_end needs it
        p = self.payload(hook_event_name="PostToolUse", tool_name="Skill", tool_input={"skill": "x", "args": "hunter2"})
        self.assertNotIn("hunter2", json.dumps(T.build_job(p)))

    def test_hook_spawns_without_waiting_and_prints_nothing(self):
        got = []
        self.assertIsNone(T.decide(self.payload(), spawn=got.append))
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["type"], "session_start")
        T.decide(self.payload(hook_event_name="Stop"), spawn=got.append)  # not reportable: no spawn
        T.decide({"hook_event_name": "SessionStart"}, spawn=got.append)  # no session id: no spawn
        self.assertEqual(len(got), 1)

    def test_spawn_failure_is_silent(self):
        def boom(job):
            raise OSError("no fork")
        self.assertIsNone(T.decide(self.payload(), spawn=boom))

    def test_spawns_detached(self):
        calls = []
        orig = T.subprocess.Popen

        class Fake:
            class stdin:
                @staticmethod
                def write(b):
                    calls.append(("write", json.loads(b)))

                @staticmethod
                def close():
                    calls.append(("close",))

        def popen(cmd, **kw):
            calls.append(("popen", cmd, kw))
            return Fake()
        T.subprocess.Popen = popen
        try:
            T.spawn_sender({"type": "session_start"})
        finally:
            T.subprocess.Popen = orig
        _, cmd, kw = calls[0]
        self.assertEqual(cmd[1:], [os.path.realpath(SCRIPT), "--send"])
        self.assertTrue(kw["start_new_session"])
        self.assertTrue(kw["close_fds"])
        self.assertEqual((kw["stdout"], kw["stderr"]), (subprocess.DEVNULL, subprocess.DEVNULL))
        self.assertEqual(calls[-1], ("close",))


class EventTest(Base):
    def test_session_start_matches_contract(self):
        ev = self.event_for(self.payload())
        validate(self, ev)
        self.assertEqual(ev["session_id"], "sess-1")
        self.assertEqual(ev["user"]["git_name"], "Jane Doe")
        self.assertEqual(ev["user"]["git_email"], "jane@example.com")
        self.assertEqual(ev["project"], {"repo_url": "https://github.com/acme/shop", "branch": "feature/ABC-1",
                                         "commit": ev["project"]["commit"], "oro_version": "6.1.2"})
        self.assertEqual(ev["client"]["model"], "claude-opus-5-5")
        self.assertEqual(ev["client"]["claude_code_version"], "2.3.1")
        self.assertEqual(ev["client"]["plugin_version"], T.plugin_version())
        self.assertEqual(ev["data"], {"source": "startup"})
        self.assertNotIn(TOKEN, json.dumps(ev))

    def test_no_pii_beyond_contract(self):
        os.environ["SECRET_ENV"] = "hunter2-env"
        try:
            ev = self.event_for(self.payload(prompt="hunter2-prompt", transcript_path="/x", tool_input={"a": "hunter2-tool"}))
        finally:
            del os.environ["SECRET_ENV"]
        text = json.dumps(ev)
        for secret in ("hunter2", TOKEN, self.proj, self.tmp.name):
            self.assertNotIn(secret, text)

    def test_outside_git_repo_omits_project_fields(self):
        plain = os.path.join(self.tmp.name, "plain")
        os.makedirs(plain)
        ev = self.event_for(self.payload(cwd=plain))
        validate(self, ev)
        self.assertEqual(ev["project"], {})
        self.assertNotIn("git_email", ev["user"])

    def test_overlong_fields_are_clipped(self):
        ev = self.event_for(self.payload(model="m" * 500))
        self.assertEqual(len(ev["client"]["model"]), 100)
        validate(self, ev)

    def test_skill_and_command_events(self):
        validate(self, self.event_for(self.payload(hook_event_name="PostToolUse", tool_name="Skill", tool_input={"skill": "aaxis-oro:review"})))
        ev = self.event_for(self.payload(hook_event_name="PostToolUse", tool_name="Bash", tool_input={"command": "aaxis-oro env up"}))
        validate(self, ev)
        self.assertEqual(ev["data"], {"name": "env"})

    def test_session_end_duration_from_persisted_start_and_counts(self):
        t0 = 1_700_000_000
        self.event_for(self.payload(), now=t0)
        self.assertTrue(os.path.isfile(T.state_path("sess-1")))
        transcript = os.path.join(self.tmp.name, "t.jsonl")
        rows = [
            {"type": "user", "message": {"role": "user", "content": "SECRET prompt one"}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}, {"type": "tool_use", "name": "Bash"}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}, {"type": "tool_use", "name": "Read"}]}},
            {"type": "user", "isMeta": True, "message": {"content": "meta"}},
            {"type": "user", "message": {"content": [{"type": "text", "text": "prompt two"}]}},
            {"type": "assistant", "isSidechain": True, "message": {"content": [{"type": "tool_use"}]}},
        ]
        with open(transcript, "w") as fh:
            fh.write("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
        ev = self.event_for(self.payload(hook_event_name="SessionEnd", reason="logout", transcript_path=transcript), now=t0 + 125)
        validate(self, ev)
        self.assertEqual(ev["data"], {"reason": "logout", "duration_s": 125, "prompt_count": 2, "tool_count": 3})
        self.assertEqual(ev["client"]["model"], "claude-opus-5-5")  # carried over from the start record
        self.assertEqual(ev["client"]["claude_code_version"], "2.3.1")
        self.assertNotIn("SECRET", json.dumps(ev))
        self.assertFalse(os.path.exists(T.state_path("sess-1")))  # record dropped

    def test_session_end_without_start_or_transcript_omits_numbers(self):
        ev = self.event_for(self.payload(hook_event_name="SessionEnd", reason="other"))
        validate(self, ev)
        self.assertEqual(ev["data"], {"reason": "other"})

    def test_resume_keeps_the_original_start(self):
        t0 = 1_700_000_000
        self.event_for(self.payload(), now=t0)
        self.event_for(self.payload(source="compact"), now=t0 + 60)
        ev = self.event_for(self.payload(hook_event_name="SessionEnd", reason="other"), now=t0 + 100)
        self.assertEqual(ev["data"]["duration_s"], 100)

    def test_old_state_records_are_pruned(self):
        self.event_for(self.payload(session_id="old"))
        old = time.time() - T.STATE_TTL - 10
        os.utime(T.state_path("old"), (old, old))
        self.event_for(self.payload(session_id="new"))
        self.assertFalse(os.path.exists(T.state_path("old")))
        self.assertTrue(os.path.exists(T.state_path("new")))

    def test_state_lives_under_isolated_home(self):
        self.event_for(self.payload())
        self.assertTrue(T.state_dir().startswith(self.home))


class GateTest(Base):
    def outside(self):
        d = os.path.join(self.tmp.name, "plain")
        os.makedirs(d, exist_ok=True)
        return d

    def test_every_event_type_is_silent_and_unspawned_outside_an_oro_root(self):
        got = []
        for p in (self.payload(), self.payload(hook_event_name="SessionEnd", reason="other"),
                  self.payload(hook_event_name="PostToolUse", tool_name="Skill", tool_input={"skill": "x"}),
                  self.payload(hook_event_name="PostToolUse", tool_name="Bash", tool_input={"command": "aaxis-oro atlas x"}),
                  self.payload(hook_event_name="UserPromptSubmit", prompt="/aaxis-oro:review")):
            p["cwd"] = self.outside()
            self.assertIsNone(T.decide(p, spawn=got.append))
        self.assertEqual(got, [])
        self.assertFalse(os.path.exists(T.state_dir()))

    def test_fires_inside_root_and_from_a_subdirectory(self):
        got = []
        T.decide(self.payload(), spawn=got.append)
        sub = os.path.join(self.proj, "src", "Deep")
        os.makedirs(sub)
        T.decide(self.payload(hook_event_name="SessionEnd", reason="other", cwd=sub), spawn=got.append)
        self.assertEqual([j["type"] for j in got], ["session_start", "session_end"])

    def test_session_end_without_state_does_not_crash(self):
        self.assertIsNone(T.decide(self.payload(hook_event_name="SessionEnd", cwd=self.outside()), spawn=lambda j: 1 / 0))

    def test_subprocess_is_silent_in_and_out_of_root(self):
        env = dict(os.environ)
        for cwd in (self.outside(), self.proj):
            p = subprocess.run([sys.executable, SCRIPT], input=json.dumps(self.payload(cwd=cwd)), capture_output=True, text=True,
                               env=dict(env, PYTHONPATH=ProcessTest.env(self)["PYTHONPATH"]), timeout=20)
            self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))


class DedupeTest(Base):
    def skill(self, sid="s1", name="aaxis-oro:review", typed=False):
        if typed:
            return self.payload(session_id=sid, hook_event_name="UserPromptSubmit", prompt="/%s now" % name)
        return self.payload(session_id=sid, hook_event_name="PostToolUse", tool_name="Skill", tool_input={"skill": name})

    def test_typed_command_and_skill_tool_call_make_one_event(self):
        got = []
        T.decide(self.skill(typed=True), spawn=got.append, now=1000)
        T.decide(self.skill(), spawn=got.append, now=1008)  # the Skill call the typed command triggered
        self.assertEqual([j["data"]["name"] for j in got], ["aaxis-oro:review"])

    def test_either_order_and_repeated_tool_calls(self):
        got = []
        T.decide(self.skill(), spawn=got.append, now=1000)
        T.decide(self.skill(typed=True), spawn=got.append, now=1001)
        T.decide(self.skill(), spawn=got.append, now=1002)
        self.assertEqual(len(got), 1)

    def test_other_skill_other_session_and_later_use_still_count(self):
        got = []
        T.decide(self.skill(), spawn=got.append, now=1000)
        T.decide(self.skill(name="tab-jira"), spawn=got.append, now=1001)
        T.decide(self.skill(sid="s2"), spawn=got.append, now=1001)
        T.decide(self.skill(), spawn=got.append, now=1000 + T.DEDUPE_WINDOW + 1)
        self.assertEqual(len(got), 4)

    def test_other_event_types_are_never_deduped(self):
        got = []
        for _ in range(2):
            T.decide(self.payload(hook_event_name="PostToolUse", tool_name="Bash", tool_input={"command": "aaxis-oro atlas x"}),
                     spawn=got.append, now=1000)
        self.assertEqual(len(got), 2)

    def test_markers_live_under_isolated_home(self):
        T.decide(self.skill(), spawn=lambda j: None)
        names = os.listdir(T.state_dir())
        self.assertTrue(names and all(n.startswith("skill-") for n in names))
        self.assertTrue(T.state_dir().startswith(self.home))


class SendTest(Base):
    def test_posts_contract_body_through_injected_poster(self):
        sent = []
        job = json.loads(json.dumps(T.build_job(self.payload())))
        self.assertTrue(T.send(job, poster=sent.append))
        self.assertEqual(len(sent), 1)
        validate(self, sent[0])

    def test_failures_are_silent(self):
        job = T.build_job(self.payload())

        def boom(event):
            raise OSError("offline")
        self.assertFalse(T.send(job, poster=boom))
        self.assertFalse(T.send({"type": "bogus"}, poster=boom))
        self.assertFalse(T.send(None, poster=boom))

    def test_missing_git_and_claude_still_send(self):
        os.environ["PATH"] = self.bin  # no git, only the fake claude; `sh` is not needed
        try:
            sent = []
            self.assertTrue(T.send(T.build_job(self.payload()), poster=sent.append))
        finally:
            os.environ["PATH"] = self.bin + os.pathsep + self.path
        validate(self, sent[0])
        self.assertNotIn("git_email", sent[0]["user"])

    def test_real_http_post_has_no_origin_or_cookie(self):
        seen = {}

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                seen["path"] = self.path
                seen["headers"] = dict(self.headers)
                seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(202)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.handle_request, daemon=True).start()
        T.ENDPOINT = "http://127.0.0.1:%d/telemetry/events" % srv.server_port
        try:
            self.assertTrue(T.send(T.build_job(self.payload())))
        finally:
            srv.server_close()
        self.assertEqual(seen["path"], "/telemetry/events")
        lower = {k.lower() for k in seen["headers"]}
        self.assertNotIn("origin", lower)
        self.assertNotIn("cookie", lower)
        self.assertEqual(seen["headers"]["Content-Type"], "application/json")
        self.assertEqual(seen["body"]["schema"], 1)
        self.assertEqual(len(seen["body"]["events"]), 1)
        validate(self, seen["body"]["events"][0])

    def test_http_error_is_silent(self):
        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(500)
                self.end_headers()

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.handle_request, daemon=True).start()
        T.ENDPOINT = "http://127.0.0.1:%d/telemetry/events" % srv.server_port
        try:
            self.assertFalse(T.send(T.build_job(self.payload())))
        finally:
            srv.server_close()

    def test_endpoint_is_fixed_and_ignores_env(self):
        self.assertEqual(T.ENDPOINT, "https://acp-api.aaxis.io/telemetry/events")
        self.assertFalse(hasattr(T, "endpoint"))
        with open(SCRIPT, encoding="utf-8") as fh:
            self.assertNotIn("AAXIS_ORO_TELEMETRY_URL", fh.read())
        sent = []
        orig = T.request.urlopen
        T.request.urlopen = lambda req, timeout=None: sent.append((req.full_url, timeout)) or io.BytesIO(b"{}")
        os.environ["AAXIS_ORO_TELEMETRY_URL"] = "http://127.0.0.1:9"
        try:
            self.assertTrue(T.send(T.build_job(self.payload())))
        finally:
            T.request.urlopen = orig
            del os.environ["AAXIS_ORO_TELEMETRY_URL"]
        self.assertEqual(sent, [("https://acp-api.aaxis.io/telemetry/events", 3)])


class ProcessTest(Base):
    """The real script as a subprocess, HOME isolated, network disabled via sitecustomize."""

    def env(self):
        """Subprocess env whose urlopen always fails (sitecustomize on PYTHONPATH): no real network, no product override."""
        site = os.path.join(self.tmp.name, "site")
        os.makedirs(site, exist_ok=True)
        with open(os.path.join(site, "sitecustomize.py"), "w") as fh:
            fh.write("import urllib.request as r\n"
                     "def _no(*a, **k):\n    raise OSError('network disabled in tests')\n"
                     "r.urlopen = _no\n")
        return dict(os.environ, PYTHONPATH=site)

    def run_hook(self, payload, raw=None):
        env = self.env()
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, SCRIPT], input=raw if raw is not None else json.dumps(payload), capture_output=True,
                           text=True, env=env, timeout=20)
        return p, time.monotonic() - t0

    def test_silent_exit_zero_and_fast(self):
        for payload in (self.payload(), self.payload(hook_event_name="SessionEnd", reason="other"), self.payload(hook_event_name="Stop")):
            p, took = self.run_hook(payload)
            self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))
            self.assertLess(took, 2)

    def test_garbage_input_is_silent(self):
        for raw in ("", "not json", "[]", "null"):
            p, _ = self.run_hook(None, raw=raw)
            self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))

    def test_sender_mode_with_network_down_exits_zero(self):
        job = T.build_job(self.payload())
        env = self.env()
        p = subprocess.run([sys.executable, SCRIPT, "--send"], input=json.dumps(job), capture_output=True, text=True, env=env, timeout=20)
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))

    def test_nothing_written_outside_isolated_home(self):
        self.run_hook(self.payload())
        time.sleep(1)
        for root, _, files in os.walk(self.home):
            for f in files:
                self.assertTrue(root.startswith(os.path.join(self.home, ".claude")))


class WiringTest(unittest.TestCase):
    def test_hooks_json_registers_the_script(self):
        with open(os.path.join(REPO, "hooks", "hooks.json")) as fh:
            hooks = json.load(fh)["hooks"]

        def wired(event, matcher=None):
            return any("telemetry.py" in h["command"] for g in hooks.get(event, []) if g.get("matcher") == matcher for h in g["hooks"])
        self.assertTrue(wired("SessionStart"))  # no matcher: every source
        self.assertTrue(wired("SessionEnd"))
        self.assertTrue(wired("PostToolUse", "Skill"))
        self.assertTrue(wired("PostToolUse", "Bash"))
        self.assertTrue(any("telemetry.py" in h["command"] for g in hooks["UserPromptSubmit"] for h in g["hooks"]))
        for groups in hooks.values():
            for g in groups:
                for h in g["hooks"]:
                    if "telemetry.py" in h["command"]:
                        self.assertLessEqual(h["timeout"], 5)


if __name__ == "__main__":
    unittest.main()
