#!/usr/bin/env python3
"""Activation eval: does an agent reach for `atlas`, and with a sensible subcommand?

Usage: run_eval.py [--ids a,b,c | --limit N | --all] [--budget USD] [--model M]
Read-only: Bash is limited to a read-only allowlist and Edit/Write tools are not exposed.
"""
import argparse, json, os, re, shlex, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ATLAS_BIN = HERE.parent / "bin"
PROJECT = "/opt/projects/buckman"
GUARD = ("This is a read-only evaluation: do NOT edit, write or create any file and do not run "
         "state-changing commands.")
ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
WRAPPERS = {"sudo", "env", "command", "exec", "time", "rtk", "proxy", "nice"}
SUBCMDS = {"event", "tag", "service", "unsafe", "grid", "layout", "workflow", "operation",
           "mq", "config", "entity", "js", "search"}
PLURALS = {"operations": "operation", "events": "event", "tags": "tag", "services": "service",
           "grids": "grid", "layouts": "layout", "workflows": "workflow", "entities": "entity",
           "configs": "config"}
RUNS = HERE / "runs"


def atlas_calls(events):
    """Return (command, subcommand) for every Bash tool_use that runs an atlas lookup."""
    calls = []
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        for blk in ev.get("message", {}).get("content", []):
            cmd = blk.get("input", {}).get("command", "") if blk.get("type") == "tool_use" and blk.get("name") == "Bash" else ""
            for seg in re.split(r"&&|\|\||;|\||\n|\$\(|`", cmd):
                try:
                    toks = shlex.split(seg)
                except ValueError:
                    toks = seg.split()
                toks = [t for t in toks if t.strip("()")]
                while toks and (ENV_RE.match(toks[0]) or toks[0] in WRAPPERS):
                    toks = toks[1:]
                # Only the command word counts, so `grep atlas` or atlas-build are not activations.
                if not toks or os.path.basename(toks[0].strip("()")) != "atlas":
                    continue
                sub = next((PLURALS.get(t, t) for t in toks[1:] if PLURALS.get(t, t) in SUBCMDS), None)
                # --help and status only show the CLI exists; they do not prove it was used.
                if sub and not {"-h", "--help"} & set(toks):
                    calls.append((cmd, sub))
    return calls


def verdict(rc, result):
    """Non-zero exits and budget/turn cut-offs cannot show non-activation, so they are inconclusive."""
    cut = result.get("subtype", "success") != "success" or result.get("is_error")
    return "inconclusive" if rc != 0 or not result or cut else "ok"


def summary(rows):
    done = [r for r in rows if r["status"] == "ok"]
    n = len(done)
    rate = lambda k: f"{sum(r[k] for r in done)}/{n} ({100 * sum(r[k] for r in done) / n:.0f}%)" if n else "n/a"
    return (f"conclusive {n}/{len(rows)}  activation {rate('invoked')}  "
            f"correct-subcommand {rate('right_subcommand')}")


def run_path(case_id, runs_dir=RUNS):
    """Next free eval/runs/<id>-<n>.jsonl so earlier transcripts are never overwritten."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    n = 1
    while (runs_dir / f"{case_id}-{n}.jsonl").exists():
        n += 1
    return runs_dir / f"{case_id}-{n}.jsonl"


def run_model(events, requested):
    init = next((e for e in events if e.get("type") == "system" and e.get("model")), {})
    return init.get("model") or requested


def run_one(case, args):
    env = dict(os.environ, PATH=f"{ATLAS_BIN}:{os.environ['PATH']}")
    cmd = ["claude", "-p", case["prompt"], "--output-format", "stream-json", "--verbose",
           "--permission-mode", "plan", "--no-session-persistence",
           "--tools", "Bash,Read,Grep,Glob,Skill",
           "--disallowedTools", "Edit", "Write", "NotebookEdit",
           "--allowedTools", "Bash(atlas:*)", "Bash(grep:*)", "Bash(rg:*)", "Bash(ls:*)", "Bash(cat:*)",
           "--append-system-prompt", GUARD + " The `atlas` CLI is on PATH.",
           "--max-budget-usd", str(args.budget)]
    if args.model:
        cmd += ["--model", args.model]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=PROJECT, env=env, capture_output=True, text=True, timeout=args.timeout)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout
        p = subprocess.CompletedProcess(cmd, -9, out or "", "")
    log = run_path(case["id"])
    log.write_text(p.stdout or "")
    events = []
    for line in p.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    calls = atlas_calls(events)
    subs = [s for _, s in calls]
    result = next((e for e in events if e.get("type") == "result"), {})
    return {"id": case["id"], "model": run_model(events, args.model), "transcript": str(log), "invoked": bool(calls),
            "right_subcommand": any(s in case["expect"] for s in subs),
            "status": verdict(p.returncode, result), "stop": result.get("subtype"),
            "first_atlas_call": calls[0][0] if calls else None,
            "subcommands": subs, "expected": case["expect"],
            "cost_usd": result.get("total_cost_usd"), "secs": round(time.time() - t0, 1),
            "rc": p.returncode}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--budget", type=float, default=3.0)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--model")
    ap.add_argument("--out", default=str(HERE / "results.jsonl"))
    args = ap.parse_args()
    cases = json.loads((HERE / "prompts.json").read_text())
    if args.ids:
        want = args.ids.split(",")
        cases = [c for c in cases if c["id"] in want]
    elif not args.all:
        cases = cases[: args.limit or 3]
    rows = []
    with open(args.out, "w") as out:
        for c in cases:
            r = run_one(c, args)
            rows.append(r)
            out.write(json.dumps(r) + "\n")
            out.flush()
            print(f"{r['id']:24} {r['status']:12} invoked={r['invoked']!s:5} right={r['right_subcommand']!s:5} subs={r['subcommands']} ${r['cost_usd']} {r['secs']}s")
    print("\n" + summary(rows))


if __name__ == "__main__":
    main()
