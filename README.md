# aaxis-oro

Claude Code plugin for OroCommerce teams: task-indexed solution knowledge, the atlas extension-point index, e2e and
local-environment tooling, and enforcement hooks. One CLI, `aaxis-oro`, fronts all deterministic work. It layers on
the official [`oroinc/ai-dev-platform`](https://github.com/oroinc/ai-dev-platform) plugins; it does not replace them.

## Install

```bash
claude plugin marketplace add git@github.com:tabhan/oro-skills.git
claude plugin install aaxis-oro@aaxis-oro
claude plugin list                                    # aaxis-oro@aaxis-oro enabled
```

Update: `claude plugin marketplace update aaxis-oro && claude plugin update aaxis-oro@aaxis-oro`.
`./install.sh` (in a clone) does the same plus the official plugins, a `~/.local/bin/aaxis-oro` link and the git
hook; flags are documented in its header. No SSH key: see `bootstrap.sh`. Local plugin dev:
`claude --plugin-dir <clone>`, validate with `claude plugin validate <clone>`.

First use in a project: run `/aaxis-oro:setup`.

## CLI

`aaxis-oro --help` is the reference (the plugin's `bin/` is on the Bash tool PATH while enabled).

```
atlas   <entity|event|service|tag|unsafe|grid|workflow|operation|mq|config|layout|js|search|notes|status> <term> | build | setup
memory  inventory|apply              project auto-memory -> .oro-ai/notes
env     setup|render|check|repair|reset|baseline|import-attachments|restore|workers|switch
test    [--project P] [--no-refresh-check] <local|local-test> <phpunit|e2e|console|verify>
review  check [--staged|--range A..B|--files F...]
task    init|check [KEY]             per-ticket evidence in .oro-ai/task/<KEY>/
version [diff|applies]               detected Oro version and which guidance applies
spec    coverage|report              spec AC traceability
setup   status|sync|rules|apply-rules
dev     lint | refresh [--all]       lint this plugin | refresh derived state after switch/pull
```

## Skills, agent, commands

| Name | Use |
|------|-----|
| [atlas](atlas/) | Index of events, tags, services, grids, workflows, MQ, config, layouts, JS; `unsafe <Class>` before any `decorates:`. Query before reading `vendor/`. |
| [solutions](solutions/) | Task-indexed knowledge: dialog/content-widget forms, core service overrides (interceptor), entity schema/config, enums, datagrids, migrations, dev loop, Aaxis bundles. |
| [e2e](e2e/) | Playwright-BDD authoring and run rules. |
| [spec](spec/) | Spec per feature under `/spec`, AC ids, test tags, coverage reports. |
| [env](env/) | Local and local-test stack: check, repair, reset, baseline, worker sizing. |
| agent `architect-gate` | Read-only PLAN-phase gate: every extension-point choice cited and appropriate. |
| `/aaxis-oro:setup` | Foundation setup, `CLAUDE_project.md` rules, `.oro-ai/config.json`, atlas and env hand-off. Idempotent. |
| `/aaxis-oro:review` | Mandatory supplementary review before push (official pack + Aaxis lenses), verdict in `.oro-ai/task/<KEY>/review.md`. |
| `/aaxis-oro:notes-migrate` | Project auto-memory to `.oro-ai/notes` (classify, confirm, apply). |

## Hooks

Shipped in `hooks/hooks.json`, never per project; each injects a few lines at most:
SessionStart (atlas freshness, notes, version, legacy/memory migration prompts), UserPromptSubmit and SubagentStart
(atlas-first hints), PreToolUse (atlas/decorator checks on edits, Bash guard for the enforcement switch, memory-write
block, anchored notes), PostToolUse Bash, Stop (end-of-session reminders, supplementary-review gate).
`ORO_ATLAS_ENFORCE=0` is a human-only escape hatch; Claude never sets it.

Upgrading from the pre-plugin install: stale `oro-atlas/hooks/*.py` entries in Claude settings keep resolving to
shims in `oro-atlas/hooks/` that remove those entries from project and `~/.claude` settings (atlas entries only),
print nothing and exit 0. `install.sh` and `atlas setup --cleanup-only` do the same cleanup.

## Git pre-commit hook

`aaxis-oro setup sync` installs a managed `pre-commit` (template `templates/git-hooks/pre-commit.sh`, header
`aaxis-oro:managed-pre-commit`) running static/quality checks only: PHPCS, PHP-CS-Fixer, PHPMD, PHPStan, Psalm, PHPUnit,
ESLint, Stylelint, YamlLint. Commands come from CI first (`bitbucket-pipelines.yml`, `.gitlab-ci.yml`,
`.github/workflows`; installs, Sonar and `pipe:` steps are ignored), else composer/package.json scripts, else
`vendor/bin` tools that have their config file. Non-git or non-Oro projects are skipped.

- Location: `core.hooksPath` when set (e.g. `.githooks`, keep it in `.git/info/exclude`), else `.git/hooks`. Setup never
  sets `core.hooksPath` and never writes tracked files.
- Speed: phpcs runs with `--parallel` (nproc, else getconf, else 1) and `--cache` in `<git dir>/phpcs.cache`, replacing CI's own
  values; PHPMD runs under `php -d error_reporting="E_ALL & ~E_DEPRECATED"` with a content-hash result cache in
  `<git dir>/phpmd.result-cache.php` (PHPMD >= 2.13). Older managed hooks are `outdated` and rewritten by sync.
- Foreign hook: an unmanaged hook is copied to `pre-commit.bak-<timestamp>` and replaced; a git-tracked one is left
  alone and reported. A managed hook that differs from the current render is `outdated` and rewritten.
- `.oro-ai/config.json` `precommit`: `path-prefix` (dir prepended to PATH, e.g. the project Node bin; default: `nvm use`
  from `.nvmrc` when nvm is installed), `skip` (step keys: the tool keys above plus `schema-drift`), `exclude` (list of
  repo-relative paths or globs kept out of the whole-tree steps, e.g. `["src/Legacy", "src/Gen/*.php"]`), `atlas: true`
  (adds `aaxis-oro atlas precommit`; off by default, the atlas review stays a Claude PreToolUse hook). There is no
  separate JSON schema file for this config; this list is the reference.
- Same result as CI: CI lints the tracked tree, so the hook keeps every path git ignores or excludes (`.gitignore`,
  `.git/info/exclude`, e.g. a local-only `src/Aaxis/Bundle/AppBundle`), every untracked path and every `precommit.exclude`
  entry out of PHPCS (`--ignore`, merged with the CI value), PHPMD (`--exclude`, merged), ESLint and Stylelint
  (`--ignore-pattern`; `--` is added to `npm run` commands). YamlLint has no ignore flag, so directory arguments become
  the tracked, non-excluded `*.yml`/`*.yaml` files under them. PHP-CS-Fixer, PHPStan, Psalm and PHPUnit read their own
  config and are not narrowed; use their config to exclude paths.
- Staged-type gate: a step runs only when the commit stages a file of its type (PHP tools: `.php`, `.xml`, `.neon`,
  `.dist`, `composer.json|lock`; ESLint: JS/TS/Vue and `package.json`; Stylelint: SCSS/CSS and `package.json`;
  YamlLint: `.yml`/`.yaml`; schema drift: `Entity/`, `Migrations/`, `entity_extend.yml`, `entity_configs.yml`,
  `composer.lock`). Nothing staged, or `AAXIS_ORO_PRECOMMIT_ALL=1`, runs every step.
- Schema drift (`schema-drift`, on by default for Oro projects that have `bin/console`; opt out with
  `"skip": ["schema-drift"]`): runs `php bin/console doctrine:schema:update --dump-sql --env=prod`, i.e. the LOCAL
  database. It refuses (exit 1) when `ORO_ENV`/`APP_ENV` is `test`/`behat_test` or the DSN names `oro_test*`, so it never
  measures the test stack. Blank lines, SQL comments and the "Nothing to update" banner are ignored; 50 or more
  `ADD CONSTRAINT` lines are reported as an incomplete database (install or migration still running), not as drift; a
  console that cannot run fails the step (unrun is not passed). Fixing real drift: `solutions/references/entities/entity-extend-indexes.md`.
- `setup sync` over an unmanaged hook first lists its steps that have no managed equivalent (printed with the backup path).
- yamllint: installed user-level with `pipx install yamllint`, else `python3 -m pip install --user yamllint`, never sudo;
  without either the hook uses the `cytopia/yamllint` docker image. `setup status` rows `pre-commit` and `hook-tools`
  report missing/outdated/foreign hooks and absent tools (yamllint, vendor tools, node) with the fix.

## Ticket process

`/aaxis-oro:setup` writes the `process-rules` block (`templates/claude-project/process-rules.md`) into the project's
`CLAUDE_project.md`; it states the per-ticket steps and that they override any command's fast path. Enforcement
applies only to setup projects (`.oro-ai/config.json` exists) on a branch whose name holds a ticket key
(`[A-Z][A-Z0-9]+-<n>`); elsewhere nothing changes.

- `aaxis-oro task init [KEY]` creates `.oro-ai/task/<KEY>/STATUS.md` and `plan.md` stubs (never overwrites);
  `aaxis-oro task check [KEY]` lists missing evidence (exit 1). KEY defaults to the branch's key. Once the branch has
  committed code, a `plan.md` whose `## Root cause` section is missing or empty (the stub's guidance prose alone counts
  as empty) prints a warning without changing the exit code; features write `n/a - feature`.
- `review check --staged` (and so the `git commit` PreToolUse hook): `review-ticket-gate` denies a staged
  extension-point file (same list as the atlas edit hook) unless `architect-gate.md` has a `Verdict: approved` or
  `Verdict: skipped - <reason>` line (a bare `PASS`/`REJECT` first line is read the same); `review-ticket-evidence` warns when `STATUS.md` is missing or production `src/`
  code changed on the branch (vs the first of `origin/develop`, `develop`, `origin/main`, `main`, ...) with no
  `*.feature`/`*.steps.ts`.
- Supplementary review (`/aaxis-oro:review`, agent `aaxis-oro:aaxis-reviewer`): invokes the official
  `orocommerce-review:review-changes` for the generic lenses and adds the Aaxis ones (reuse/OOTB via atlas, Aaxis rule
  judgment, plan.md/architect-gate drift, conditional performance), refuted with the official `finding-refuter`.
  It writes `.oro-ai/task/<KEY>/review.md` with `Verdict: approved|changes-requested|skipped - <reason>` and
  `Range: <base>..<head>`. An approved review covers HEAD when its head is HEAD, or an ancestor with only `.oro-ai/`
  files changed since (so committing the review itself keeps it fresh). Once the branch has committed code,
  `task check` fails without a covering approved/skipped review, and `review-ticket-push` (PreToolUse on Bash
  `git push`) denies the push; there is no git-side hook, so a human pushing from a shell is not gated.
- `review-ticket-stop` (Stop hook, `atlas/hooks/stop.py`) makes the review happen when coding finishes: with the
  same condition as the push gate, plus no uncommitted or untracked changes outside `.oro-ai/` (a dirty tree is
  mid-work), it returns `decision: block` telling Claude to run `/aaxis-oro:review` (or record a skipped verdict);
  a `changes-requested` review whose Range head is HEAD asks for the must-fix findings first. It blocks once per
  stop chain (`stop_hook_active` lets the next Stop through with a warning), exempts subagents (SubagentStop /
  `agent_id`: the main session owns the review), only warns under the human-only enforcement switch, and any
  error allows the stop (logged to `~/.claude/atlas-hook.log`). `/aaxis-oro:review` first writes a
  `Verdict: in-progress` marker (`Range: <base>..<HEAD>`, `Started: <ISO-8601 UTC>`): while its head is HEAD and it is
  younger than 2h (`task.IN_PROGRESS_TTL`) the Stop hook only warns "review in progress since <t>"; a stale marker
  blocks as usual. `in-progress` is never approved: push gate and `task check` still fail.
- UserPromptSubmit injects one reminder per ticket key per session (key from the prompt, else the branch). Keys
  inside harness wrappers (`<task-notification>`, `<system-reminder>`, text after `[SYSTEM NOTIFICATION`) are ignored:
  background-task notifications reach the hook as `prompt` text with no distinguishing payload field.
- Escape hatches: `Verdict: skipped - <reason>` for a trivial change (auditable in the task dir); the human-only
  `ORO_ATLAS_ENFORCE=0` downgrades the deny to a warning.

Existing projects pick up the block with `aaxis-oro setup sync` (`setup status` reports `blocks out of sync: process-rules`).

## Principles

- Token efficiency: deterministic work lives in scripts with quiet output (one line per step, documented exit codes,
  `--verbose`/`--json`, detail in `.oro-ai/.../logs`). Skills are short indexes of judgment; mechanics that mirror
  code stay in the README beside that code. Generic Oro documentation stays with the official plugins.
- Never copy: a skill states a decision and the incident behind it, then points at the docs.
- Shell-agnostic (bash/POSIX sh); idempotent commands; no prompts except documented asks.

## Versioning and contributing

Guidance can be scoped to Oro versions (`docs/VERSIONING.md`). Every push to `main` bumps `version` in
`.claude-plugin/plugin.json`; without a bump installed copies never update. The owner pushes `main` directly after
`git pull --rebase`, the unit suites (`python3 -m unittest discover -s <dir>` for `tests/*` and `atlas/tests`) and
`aaxis-oro dev lint` pass. Everyone else opens a PR; CI (`.github/workflows/lint.yml`) is the gate.
