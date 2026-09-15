# Oro Skills for Claude Code

Reusable [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for OroCommerce development. Each skill is a self-contained knowledge base that Claude Code consults automatically when working on relevant tasks.

**Why so little content:** this repo used to carry a near-complete mirror of generic Oro/OroCommerce documentation. As of 2026-09-10 that generic material was removed — it duplicated the official [`oroinc/ai-dev-platform`](https://github.com/oroinc/ai-dev-platform) plugin suite's own reference docs, which `install.sh` now installs alongside these skills (see Installation). What's left here is only content tied to a real incident/gotcha hit on this project, that the official plugin doesn't cover.

**Adding a skill:** a skill earns its place only once there is a concrete incident to record (symptom → root cause → fix). An empty placeholder skill is worse than no skill: its description is resident in every session and routes work to a body that has nothing to say. There is deliberately no frontend skill here for that reason — until a real frontend incident lands that the official plugin doesn't cover, the plugin is the answer.

**Skill vs. repo README:** a skill holds the *judgment* calls (what to tag, what never to truncate). Mechanics that mirror code — CLI flags, config keys, setup steps — stay in the README that ships beside that code, and the skill points at it. A copy here cannot be updated by whoever changes that code, and a stale copy loaded into context is worse than no copy.

## Available Skills

| Skill | Description |
|-------|-------------|
| [oro-backend-docs](oro-backend-docs/) | Buckman-specific backend gotchas (entity-extend schema drift, serialized enum-extend storage) not covered by the official plugin |
| [oro-e2e-testing](oro-e2e-testing/) | Playwright-BDD e2e authoring rules for OroCommerce/OroPlatform (Alice fixtures, grid filters, purge/re-runnability, shared-DB safety) |
| [oro-dialog-forms](oro-dialog-forms/) | Building frontend dialog/drawer forms that also work as landing-page content widgets (controller → handler → layout → Twig → JS trigger → locale URLs) |
| [oro-workflow](oro-workflow/) | Dev-loop conventions specific to this project: shell aliases, cache invalidation, service overrides, system-config groups |
| [oro-conventions](oro-conventions/) | Buckman-specific Oro conventions & gotchas: aspect-interceptor overrides, storefront localization traps, entity-config seeding, PHPUnit entity stubs, datagrid pitfalls, jsonb migrations, workflow-data encoding, asset versioning |

## Installation

The repo checkout and the installed skills are kept separate: `install.sh` never edits this repo's content, it only manages symlinks under `~/.claude/skills` that point back at whichever checkout you ran it from.

### 1. Clone

With SSH access to this repo:

```bash
git clone git@github.com:tabhan/oro-skills.git /opt/projects/oro-skills
```

Without SSH access — using a read-only HTTPS token from the repo owner instead:

```bash
ORO_SKILLS_TOKEN=<token> ./bootstrap.sh /opt/projects/oro-skills   # if you already have this file
# or, one-liner without a prior checkout:
ORO_SKILLS_TOKEN=<token> bash -c "$(curl -fsSL -H "Authorization: Basic $(printf 'x-access-token:%s' "$ORO_SKILLS_TOKEN" | base64)" https://raw.githubusercontent.com/tabhan/oro-skills/main/bootstrap.sh)" -- /opt/projects/oro-skills
```

The token is only used for the clone itself (passed as a one-off `git -c` header) — it is never written into `.git/config`. Keep it and pass it again for future updates (`ORO_SKILLS_TOKEN=<token> install.sh`); `install.sh` warns if it detects an HTTPS remote and no token is set.

### 2. Install

```bash
/opt/projects/oro-skills/install.sh
```

This symlinks every `oro-*/` skill directory into `~/.claude/skills/`. Re-running it later also `git pull`s the checkout first (pass `--no-update` to skip that). To remove the symlinks: `install.sh --uninstall`.

This repo dropped its generic Oro/OroCommerce reference content (see "Why so little content" at the top) in favor of the official [`oroinc/ai-dev-platform`](https://github.com/oroinc/ai-dev-platform) plugin suite. So by default `install.sh` also registers that marketplace and installs `orocommerce-development`, `orocommerce-review`, `orocommerce-testing`, and `orocommerce-maintenance` via the `claude plugin` CLI. Skip that with `--no-official-plugins`, or override the list with `ORO_SKILLS_OFFICIAL_PLUGINS="orocommerce-development orocommerce-review" ./install.sh`. `orocommerce-orchestrator` is deliberately not installed by default — it duplicates the plan→build→review→verify flow some projects already run via the `ai-sdlc-c1` plugin; install it yourself if a project actually wants it.

### 3. Verify

Start a new Claude Code session. The skill should appear in the available skills list automatically. You can verify by asking Claude Code to write a Playwright-BDD e2e test -- it will consult the skill's documentation.

## Skill Structure

Each skill follows the Claude Code skill convention:

```
skill-name/
  SKILL.md              # Metadata (name, description, triggers) + document index
  references/
    README.md           # Quick-start overview
    topic-1.md          # Reference document
    topic-2.md          # Reference document
    ...
```

- `SKILL.md` has YAML frontmatter with `name`, `description` (including trigger scenarios). The
  `name` MUST equal the directory name.
- `references/` is optional and holds the knowledge-base documents when a skill has enough to
  warrant splitting. A single-file skill (`oro-conventions`, `oro-e2e-testing`) has none.
- Claude Code auto-discovers skills from `~/.claude/skills/*/SKILL.md`

## Adding New Skills

1. Create a new directory: `oro-<topic>/`
2. Add `SKILL.md` with frontmatter and document index
3. Add reference docs in `references/`
4. Re-run `install.sh` to pick it up

## License

MIT
