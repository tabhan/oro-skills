# Oro Skills for Claude Code

Reusable [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for OroCommerce development. Each skill is a self-contained knowledge base that Claude Code consults automatically when working on relevant tasks.

**Why so little content:** this repo used to carry a near-complete mirror of generic Oro/OroCommerce documentation. As of 2026-09-10 that generic material was removed — it duplicated the official [`oroinc/ai-dev-platform`](https://github.com/oroinc/ai-dev-platform) plugin suite's own reference docs, which `install.sh` installs alongside this plugin (see Installation). What's left here is only content tied to a real incident/gotcha hit on this project, that the official plugin doesn't cover.

**Adding a skill:** a skill earns its place only once there is a concrete incident to record (symptom → root cause → fix). An empty placeholder skill is worse than no skill: its description is resident in every session and routes work to a body that has nothing to say. There is deliberately no frontend skill here for that reason — until a real frontend incident lands that the official plugin doesn't cover, the plugin is the answer.

**Skill vs. repo README:** a skill holds the *judgment* calls (what to tag, what never to truncate). Mechanics that mirror code — CLI flags, config keys, setup steps — stay in the README that ships beside that code, and the skill points at it. A copy here cannot be updated by whoever changes that code, and a stale copy loaded into context is worse than no copy.

## Available Skills

| Skill | Description |
|-------|-------------|
| [oro-backend-docs](oro-backend-docs/) | Buckman-specific backend gotchas (entity-extend schema drift, serialized enum-extend storage) not covered by the official plugin |
| [oro-e2e-testing](oro-e2e-testing/) | Playwright-BDD e2e authoring rules for OroCommerce/OroPlatform (Alice fixtures, grid filters, purge/re-runnability, shared-DB safety) |
| [oro-dialog-forms](oro-dialog-forms/) | Building frontend dialog/drawer forms that also work as landing-page content widgets (controller → handler → layout → Twig → JS trigger → locale URLs) |
| [oro-workflow](oro-workflow/) | Dev-loop conventions specific to this project: shell aliases, cache invalidation, service overrides, system-config groups |
| [oro-atlas](oro-atlas/) | Generated, queryable index of Oro extension points (events, tags, services, grids, workflows, MQ, config, layouts, JS) plus `atlas unsafe <Class>` for decorator safety; the plugin ships `atlas` on PATH |
| [oro-conventions](oro-conventions/) | Buckman-specific Oro conventions & gotchas: aspect-interceptor overrides, storefront localization traps, entity-config seeding, PHPUnit entity stubs, datagrid pitfalls, jsonb migrations, workflow-data encoding, asset versioning |

## Installation

oro-skills is a self-hosted Claude Code plugin: skills, the `oro-architect-gate` agent and the atlas hooks (`hooks/hooks.json`, commands use `${CLAUDE_PLUGIN_ROOT}`) all come from the plugin, never from per-project `settings.json`/`settings.local.json`. It is never published to a public or shared marketplace; the marketplace is this repo.

```bash
claude plugin marketplace add git@github.com:tabhan/oro-skills.git
claude plugin install oro-skills@oro-skills
claude plugin list                      # oro-skills@oro-skills enabled
```

Local development without installing: `claude --plugin-dir /opt/projects/oro-skills`. Validate manifests with `claude plugin validate /opt/projects/oro-skills`. Updates: `claude plugin marketplace update oro-skills`, then `claude plugin update oro-skills@oro-skills`.

Lint: `install.sh` sets `core.hooksPath .githooks` for this checkout (idempotent) so `bin/oro-skills-lint` runs before each commit; CI (`.github/workflows/lint.yml`) is the authoritative gate. See docs/VERSIONING.md.

Project requirement: every Oro project needs `.oro-ai/.gitignore` containing `*`, `!.gitignore`, `!config.json` (`.oro-ai/` is the local data root: version cache, announce marker, atlas). Hooks never create project files; they write into `.oro-ai/` only when it already exists. Setup (`atlas-setup`/local-env) is responsible for creating that file.

Release rule: every push to `main` bumps `version` in `.claude-plugin/plugin.json`; without a bump installed copies never update.

The `atlas`, `atlas-build`, `atlas-setup` and `atlas-precommit` CLIs are also in the plugin's `bin/` (on the Bash tool's PATH while the plugin is enabled). For a normal shell, `install.sh` links them into `~/.local/bin` (override with `ORO_ATLAS_BIN_DIR`).

### Migrating from the symlink install

`install.sh` is now a transition shim: it removes the old `~/.claude/skills/oro-*` and `~/.claude/agents/oro-architect-gate.md` symlinks (they would duplicate every skill next to the plugin's copy), keeps the CLIs on PATH, registers the marketplace and installs the plugin (`--no-plugin` skips that step; `ORO_SKILLS_MARKETPLACE` overrides the marketplace source). `install.sh --uninstall` removes the CLI links.

Then, once per Oro project: run `atlas-setup <project>`. It no longer registers hooks; it removes the old atlas entries from `.claude/settings.local.json` (otherwise every hook fires twice), installs the git refresh hooks and builds the index. Re-run it in every new checkout or worktree. When `atlas status` prints `STALE` (exit 2), refresh with `atlas-build --project <project> --incremental`.

The official [`oroinc/ai-dev-platform`](https://github.com/oroinc/ai-dev-platform) plugins (`orocommerce-development`, `-review`, `-testing`, `-maintenance`) are installed by `install.sh` as before; skip with `--no-official-plugins` or override with `ORO_SKILLS_OFFICIAL_PLUGINS`.

Clone access: `git clone git@github.com:tabhan/oro-skills.git /opt/projects/oro-skills` (or `bootstrap.sh` with a read-only `ORO_SKILLS_TOKEN` from the repo owner).
