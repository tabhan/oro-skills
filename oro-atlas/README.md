# oro-atlas

Python 3 (stdlib only) generator and query CLI for an index of Oro extension points.

## Build

```bash
oro-atlas/bin/atlas-build --project /path/to/oro-project            # all categories
oro-atlas/bin/atlas-build --project /path/to/oro-project --only events,tags
```

Reads `vendor/oro*`, `vendor/oroinc`, `vendor/aaxisdigital`, `node_modules/@oroinc` and `src/`, plus
`php bin/console debug:container` / `debug:event-dispatcher` (`--env=prod`, JSON, cached once per
build in `.oro-ai/atlas/raw/`). Output goes to `<project>/.oro-ai/atlas/`: one `<category>.jsonl` shard per
extractor and `index.json` (composer.lock sha256, oro/platform version, timestamp, counts).
The directory carries its own `.gitignore` (`*`), so nothing needs ignoring in the project; an index
left at the older `.claude/atlas/` or `var/atlas/` is migrated automatically: the SessionStart hook
(`hooks/sessionstart_migrate.py`, also `atlas migrate`) rebuilds into `.oro-ai/atlas/` in the background (about a
minute on a large project), then deletes the old directory, rewrites old index paths in hook commands of
`.claude/settings.local.json`, and creates `.oro-ai/.gitignore` (`*`, `!.gitignore`, `!config.json`) when that
file is missing and `.oro-ai/` has no tracked content. A failed build keeps the old index and retries next session.
Test directories (`**/Tests/**`) are not part of the staleness hash.

## Staying fresh (no daemon, no token cost)
- Staleness is per shard: a shard is STALE only when an input it ingests changed (composer.lock/vendor
  state, the src files of its kind, the compiled container cache, or the extractor code).
  `atlas status` lists each shard and exits 0 (fresh) or 2 (STALE/MISSING); `--quiet` prints nothing.
- `atlas-build --incremental` rebuilds only stale/missing shards (full build stays the default);
  vendor scans are memoised in `cache/`, so one edited file refreshes in ~2-3s.
- Atlas never rebuilds on its own: queries on a stale index answer from it and print one stderr line
  `STALE: ...; rebuild (never automatic): atlas build --incremental`; the hooks name the exact command too.
  The only automatic build left is the one-time legacy move to `.oro-ai/atlas/` (`atlas migrate`, below).
  `--no-rebuild` is a deprecated no-op.
- `atlas-setup` builds once when you run it and removes the background git hooks (post-checkout/post-merge/
  post-rewrite) that earlier versions installed; foreign hooks are left alone.

## Setup (once per project)

```bash
oro-atlas/bin/atlas-setup /path/to/oro-project             # legacy cleanup, build index
oro-atlas/bin/atlas-setup /path/to/oro-project --no-build  # without the build
```

The hooks themselves come from the plugin (`hooks/hooks.json` at the repo root). Setup removes any
atlas entries left in `<project>/.claude/settings.local.json` by older versions (they would fire twice;
other settings are kept), installs the git refresh hooks, then runs `atlas-build`.

## Hooks

- `userpromptsubmit.py`: one nudge per session on Oro extension prompts; main session only. When the
  index is stale the nudge carries the `atlas-build --incremental` command.
- `subagentstart.py`: injects a short (<1 KB) "query atlas before grepping vendor/" instruction into
  every subagent of an indexed Oro project (Claude Code delivers `additionalContext` from
  `SubagentStart` to the subagent). Silent without an index; never blocks.
- `pretooluse_edit.py` / `posttooluse_bash.py`: deny unsafe `decorates:` and add context at edit time.

### Enforcement

- `sessionstart_atlas.py` (startup|resume|compact): Oro projects only; injects one status line, and for a stale
  or missing index `atlas index stale (<reason>); rebuild: <exact command>` without building. `posttooluse_bash.py`
  marks the session as "queried" on any `atlas <sub>` command and prints the same hint after `composer
  install|update|require|remove`. The marker is keyed by `session_id`, so subagents share the parent's.
- `pretooluse_edit.py` denies edits to extension files when no atlas query ran this session, or when the index is
  missing or really out of date (composer.lock, vendor or index-format change; the deny names the exact rebuild
  command). Staleness caused only by project src/config edits, container cache, notes or extractor code never
  denies: one line per session, `atlas index behind your src edits (...); rebuild when convenient: <cmd>`.
  Each deny is gated by `oro-applies --check <id>` (`hooks/checks.yml`): out of range skips, unknown Oro version
  downgrades to warn. Hook errors are swallowed; nothing blocks on a broken hook.
- Extension files (the only ones enforced): `services*.yml`, `services/*.yml`, `entity_extend.yml`, `datagrids.yml`,
  `workflows.yml` and `workflows/*.yml`, `actions.yml`/`operations.yml`, `system_configuration.yml`, `jsmodules.yml`,
  `message_queue.yml`, `oro/app.yml`, layout update ymls under `Resources/views/layouts/`, and PHP classes named
  `*Listener|*Subscriber|*Interceptor|*Decorator|*Extension` (not under `Tests/` or `Twig/`). Routing, validation,
  translations, `search.yml`, entities and templates are not. Classes that are only tag-registered under another
  name are not detected (the atlas query-first habit covers them).
- Escape hatch: `ORO_ATLAS_ENFORCE=0` in the process environment (the human's shell, before `claude`) turns every
  deny into a warning, logs `bypass` to `~/.claude/atlas-hook.log` and makes `stop.py` print a reminder.
  `pretooluse_bash.py` and the edit hook deny any attempt by Claude to set it (commands, settings*.json/rc/.env files),
  including quote-split or concatenated spellings when a settings/rc/.env file is involved. Residual risk: a script
  that builds the name from encoded data, or a human-run command, is not caught; the hatch stays a trust boundary.

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

Installed as part of the oro-skills plugin (see the top-level README). The plugin's `bin/` puts `atlas`,
`atlas-build`, `atlas-setup` and `atlas-precommit` on the Bash tool PATH; `install.sh` also links them into
`~/.local/bin` (override with `ORO_ATLAS_BIN_DIR`) for normal shells.

## Notes

`.oro-ai/notes/*.md` project notes are indexed too (`atlas notes`, anchored notes shown under query hits); format and hook API in [NOTES.md](NOTES.md).

## Tests

```bash
cd oro-atlas && python3 -m unittest discover -s tests
```

Extractors live in `atlas/extractors/<category>.py`, one module each.
