# oro-atlas

Python 3 (stdlib only) generator and query CLI for an index of Oro extension points.

## Build

```bash
oro-atlas/bin/atlas-build --project /path/to/oro-project            # all categories
oro-atlas/bin/atlas-build --project /path/to/oro-project --only events,tags
```

Reads `vendor/oro*`, `vendor/oroinc`, `vendor/aaxisdigital`, `node_modules/@oroinc` and `src/`, plus
`php bin/console debug:container` / `debug:event-dispatcher` (`--env=prod`, JSON, cached once per
build in `.claude/atlas/raw/`). Output goes to `<project>/.claude/atlas/`: one `<category>.jsonl` shard per
extractor and `index.json` (composer.lock sha256, oro/platform version, timestamp, counts).
The directory carries its own `.gitignore` (`*`), so nothing needs ignoring in the project; an index
left at the old `var/atlas/` is moved on first use.

## Staying fresh (no daemon, no token cost)
- Staleness is per shard: a shard is STALE only when an input it ingests changed (composer.lock/vendor
  state, the src files of its kind, the compiled container cache, or the extractor code).
  `atlas status` lists each shard and exits 0 (fresh) or 2 (STALE/MISSING); `--quiet` prints nothing.
- `atlas-build --incremental` rebuilds only stale/missing shards (full build stays the default);
  vendor scans are memoised in `cache/`, so one edited file refreshes in ~2-3s.
- Queries refresh a src-stale shard inline when the last build was under 5s (silent); anything bigger
  (composer/vendor/cache changes) starts a background rebuild, prints one stderr line and answers from
  the old index. `--no-rebuild` / `ATLAS_NO_AUTOBUILD=1` disables it.
- `atlas-setup` also registers a silent PostToolUse hook (Edit/Write/MultiEdit on src/config) and
  post-checkout/post-merge/post-rewrite git hooks (never overwriting a foreign hook); they run
  `atlas-build --incremental --background`, which skips when a build holds `.claude/atlas/.lock`.

## Setup (once per project)

```bash
oro-atlas/bin/atlas-setup /path/to/oro-project             # register hooks + build index
oro-atlas/bin/atlas-setup /path/to/oro-project --no-build  # hooks only
```

Idempotently merges the PreToolUse (Edit/Write), PostToolUse (Bash), UserPromptSubmit and
SubagentStart hooks into `<project>/.claude/settings.local.json` (existing settings and entries are
kept, nothing is duplicated), then runs `atlas-build`.

## Hooks

- `userpromptsubmit.py`: one nudge per session on Oro extension prompts; main session only. When the
  index is stale the nudge carries the `atlas-build --incremental` command.
- `subagentstart.py`: injects a short (<1 KB) "query atlas before grepping vendor/" instruction into
  every subagent of an indexed Oro project (Claude Code delivers `additionalContext` from
  `SubagentStart` to the subagent). Silent without an index; never blocks.
- `pretooluse_edit.py` / `posttooluse_bash.py`: deny unsafe `decorates:` and add context at edit time.

## Staleness and incremental builds

`atlas status` exits 0 when the index is fresh, 2 when stale (per-shard: only the shards whose inputs
changed need rebuilding) and non-zero otherwise when no index exists. Refresh a stale index with
`atlas-build --project <root> --incremental`; a plain `atlas-build` rebuilds everything.

## Query

```bash
atlas [--project ROOT] <event|tag|service|unsafe|grid|layout|workflow|operation|mq|config|entity|js|search> <query> [--limit N]
atlas status
atlas [--project ROOT] <command> <query> --json   # {"query", "results": [{shard, total, hits}]}
atlas status --json                               # {"index", "stale", "not_built"}
```

With `--json`, the STALE line goes to stderr so stdout stays parseable. `atlas status` exits
non-zero when no project/index is found; prompts use that to gate the citation rule.

Run from anywhere inside the project, or pass `--project`. A `STALE` line is printed when
composer.lock differs from the one the index was built from.

## Pre-commit gate (opt-in)

`bin/atlas-precommit` reads the staged diff (`git diff --cached`) of `src/**` and `config/**`
`.yml/.yaml/.xml/.php` files and exits 1, printing the deny reason, when it adds a `decorates:` /
`decorates="..."` / `#[AsDecorator]` on a target the `unsafe` shard flags. `install.sh` puts it on PATH but never
wires it; do that per checkout, e.g. in an untracked `.git/hooks/pre-commit`:

```bash
#!/bin/sh
atlas-precommit || exit 1
```

or as a `repo: local` entry (`entry: atlas-precommit`,
`pass_filenames: false`) in a personal pre-commit config. Without a built index it passes.

## Install

`install.sh` symlinks this skill into `~/.claude/skills/` like the others, links
`agents/*.md` (the `oro-architect-gate` subagent) into `~/.claude/agents/` (override with
`CLAUDE_AGENTS_DIR`), and links `bin/atlas`, `bin/atlas-build`, `bin/atlas-setup` and `bin/atlas-precommit` into
`~/.local/bin` (override with `ORO_ATLAS_BIN_DIR`). `install.sh --uninstall` removes them all.
If that directory is not on PATH, call `$ORO_SKILLS_DIR/oro-atlas/bin/atlas` directly. After
upgrading, re-run `atlas-setup <project>` per Oro project/worktree (see the top-level README).

## Tests

```bash
cd oro-atlas && python3 -m unittest discover -s tests
```

Extractors live in `atlas/extractors/<category>.py`, one module each.
