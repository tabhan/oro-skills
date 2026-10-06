# oro-atlas activation eval

Measures whether an agent, given a realistic Oro task in /opt/projects/buckman, reaches for `atlas`
and uses a sensible subcommand (`prompts.json` -> `expect` lists the acceptable ones).

Run (needs `claude` on PATH and a built index: `bin/atlas-build --project /opt/projects/buckman`):

    ./run_eval.py                      # smoke: first 3 prompts
    ./run_eval.py --ids slug-redirect,grid-x
    ./run_eval.py --all              # full 15 prompts (default budget $3/run)

Safety: `claude -p --permission-mode plan`, tools limited to Bash/Read/Grep/Glob/Skill, Edit/Write/NotebookEdit
disallowed, Bash allowlisted to atlas/grep/rg/ls/cat, per-run `--max-budget-usd`, no session persistence.
Results go to `results.jsonl` (gitignored by convention; one row per prompt).
Scoring: invoked = a Bash segment whose command word is `atlas` running a lookup subcommand (singular or plural; `status`, `--help`, atlas-build, `grep atlas` do not count); right_subcommand = at least one atlas call
used a subcommand from `expect`. Activation depends on the skill/CLAUDE.md that advertises atlas being present.
Runs that exit non-zero, time out, or stop on the budget/turn limit are `inconclusive` and excluded from the
activation and correct-subcommand rates printed at the end.
Each run's raw stream-json is kept at `runs/<prompt-id>-<n>.jsonl` (gitignored, never overwritten); every
results row records the `model` (from the init event, else `--model`) and its `transcript` path.
