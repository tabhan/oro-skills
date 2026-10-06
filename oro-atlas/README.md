# oro-atlas

Python 3 (stdlib only) generator and query CLI for an index of Oro extension points.

## Build

```bash
oro-atlas/bin/atlas-build --project /path/to/oro-project            # all categories
oro-atlas/bin/atlas-build --project /path/to/oro-project --only events,tags
```

Reads `vendor/oro*`, `vendor/oroinc`, `vendor/aaxisdigital`, `node_modules/@oroinc` and `src/`, plus
`php bin/console debug:container` / `debug:event-dispatcher` (`--env=prod`, JSON, cached once per
build in `var/atlas/raw/`). Output goes to `<project>/var/atlas/`: one `<category>.jsonl` shard per
extractor and `index.json` (composer.lock sha256, oro/platform version, timestamp, counts).
`var/atlas/` must be git-ignored in the project.

## Setup (once per project)

```bash
oro-atlas/bin/atlas-setup /path/to/oro-project             # register hooks + build index
oro-atlas/bin/atlas-setup /path/to/oro-project --no-build  # hooks only
```

Idempotently merges the PreToolUse (Edit/Write), PostToolUse (Bash) and UserPromptSubmit hooks
into `<project>/.claude/settings.local.json`, then runs `atlas-build`.

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
