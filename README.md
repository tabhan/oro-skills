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
| `/aaxis-oro:notes-migrate` | Project auto-memory to `.oro-ai/notes` (classify, confirm, apply). |

## Hooks

Shipped in `hooks/hooks.json`, never per project; each injects a few lines at most:
SessionStart (atlas freshness, notes, version, legacy/memory migration prompts), UserPromptSubmit and SubagentStart
(atlas-first hints), PreToolUse (atlas/decorator checks on edits, Bash guard for the enforcement switch, memory-write
block, anchored notes), PostToolUse Bash, Stop (end-of-session reminders).
`ORO_ATLAS_ENFORCE=0` is a human-only escape hatch; Claude never sets it.

Upgrading from the pre-plugin install: stale `oro-atlas/hooks/*.py` entries in Claude settings keep resolving to
shims in `oro-atlas/hooks/` that remove those entries from project and `~/.claude` settings (atlas entries only),
print nothing and exit 0. `install.sh` and `atlas setup --cleanup-only` do the same cleanup.

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
