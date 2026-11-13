# aaxis-oro

Claude Code plugin for OroCommerce teams: task-indexed solution knowledge, the atlas extension-point index, e2e and
local-environment tooling, and enforcement hooks. One CLI, `aaxis-oro`, fronts all tooling.

**Why little generic content:** generic Oro documentation is covered by the official
[`oroinc/ai-dev-platform`](https://github.com/oroinc/ai-dev-platform) plugins, which `install.sh` installs alongside
this plugin. A skill here records project decisions and real incidents, and points at Oro's docs for mechanics.
A skill holds judgment; mechanics that mirror code (flags, config keys, setup steps) stay in the README beside that
code, and deterministic work lives in scripts, not prose.

## Skills

| Skill | Use |
|-------|-----|
| [atlas](atlas/) | Generated index of Oro extension points (events, tags, services, grids, workflows, MQ, config, layouts, JS) plus `unsafe <Class>` for decorator safety. Run first, before reading `vendor/`. |
| [solutions](solutions/) | Task-indexed solution knowledge: dialog/content-widget forms, core service overrides (interceptor), entity schema/config, enums, datagrids, migrations, dev loop, Aaxis bundles catalogue, POC standard. |
| [e2e](e2e/) | Playwright-BDD authoring rules and decision list (fixtures, grid filters, purge, parallel lanes). |
| [env](env/) | Local and local-test environment: check, repair, reset, baseline, workers, host switch. |

Agent: `oro-architect-gate` (read-only plan/diff gate against the atlas index and the Aaxis rules).

## CLI

```
aaxis-oro atlas <sub> <term> | build | setup | precommit | status | notes | migrate
aaxis-oro env check|repair|reset|baseline|import-attachments|restore|workers|switch
aaxis-oro test [--project P] <local|local-test> <phpunit|e2e|console|verify> [args]
aaxis-oro version [diff|applies]
aaxis-oro dev lint
```

The plugin's `bin/` is on the Bash tool PATH while the plugin is enabled; `install.sh` links `aaxis-oro` into
`~/.local/bin` for normal shells (override with `ORO_ATLAS_BIN_DIR`). The team `oro-project` script
(`scripts/local-env/oro-project`) delegates to `aaxis-oro env switch`.

## Installation

Self-hosted plugin: skills, agent and hooks (`hooks/hooks.json`, commands use `${CLAUDE_PLUGIN_ROOT}`) come from the
plugin, never from per-project settings. The marketplace is this repo.

```bash
claude plugin marketplace add git@github.com:tabhan/oro-skills.git
claude plugin install aaxis-oro@aaxis-oro
claude plugin list                      # aaxis-oro@aaxis-oro enabled
```

Local development: `claude --plugin-dir /opt/projects/oro-skills`; validate with `claude plugin validate /opt/projects/oro-skills`.
Updates: `claude plugin marketplace update aaxis-oro`, then `claude plugin update aaxis-oro@aaxis-oro`.

Lint: `install.sh` sets `core.hooksPath .githooks` so `aaxis-oro dev lint` runs before each commit; CI
(`.github/workflows/lint.yml`) is the authoritative gate. See docs/VERSIONING.md.

Project requirement: `.oro-ai/.gitignore` containing `*`, `!.gitignore`, `!config.json` (the local data root: version
cache, announce marker, atlas). Hooks never create project files. Once per project: `aaxis-oro atlas setup <project>`
removes legacy atlas entries from `.claude/settings.local.json` and builds the index; when `aaxis-oro atlas status`
prints `STALE` (exit 2) refresh with `aaxis-oro atlas build --project <project> --incremental`.

Release rule: every push to `main` bumps `version` in `.claude-plugin/plugin.json`; without a bump installed copies
never update.

`install.sh` also removes the pre-plugin `~/.claude/skills/oro-*` symlinks, registers the marketplace, installs the
plugin and the official plugins (`--no-official-plugins` skips them; `--no-plugin` skips the plugin; `ORO_SKILLS_OFFICIAL_PLUGINS`
overrides the list; `ORO_SKILLS_MARKETPLACE` the marketplace source). `install.sh --uninstall` removes the CLI link.

Clone access: `git clone git@github.com:tabhan/oro-skills.git /opt/projects/oro-skills` (or `bootstrap.sh` with a
read-only `ORO_SKILLS_TOKEN` from the repo owner).
