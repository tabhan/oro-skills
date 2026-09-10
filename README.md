# Oro Skills for Claude Code

Reusable [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for OroCommerce development. Each skill is a self-contained knowledge base that Claude Code consults automatically when working on relevant tasks.

## Available Skills

| Skill | Description |
|-------|-------------|
| [oro-backend-docs](oro-backend-docs/) | OroCommerce backend API & configuration reference (entities, services, ACL, datagrids, API, MQ, migrations) |
| [oro-frontend-skills](oro-frontend-skills/) | OroCommerce frontend reference (page components, app modules, Twig, SCSS/CSS architecture, JS patterns) |
| [oro-e2e-testing](oro-e2e-testing/) | Playwright-BDD e2e authoring rules for OroCommerce/OroPlatform (Alice fixtures, grid filters, purge/re-runnability, shared-DB safety) |
| [oro-dialog-forms](oro-dialog-forms/) | Building frontend dialog/drawer forms that also work as landing-page content widgets (controller → handler → layout → Twig → JS trigger → locale URLs) |
| [oro-workflow](oro-workflow/) | Dev-loop conventions: shell aliases, cache invalidation strategy, migration naming, service overrides, PHPUnit stubs, system-config groups |
| [oro-conventions](oro-conventions/) | Opinionated cross-project Oro conventions & gotchas: Doctrine access, solution-approach hierarchy, aspect-interceptor overrides, form types, storefront localization, entity-config seeding, PHPUnit entity stubs, runtime debugging, datagrid pitfalls, jsonb migrations, workflow-data encoding, asset versioning |

## Installation

The repo checkout and the installed skills are kept separate: `install.sh` never edits this repo's content, it only manages symlinks under `~/.claude/skills` that point back at whichever checkout you ran it from.

### 1. Clone

```bash
git clone git@github.com:tabhan/oro-skills.git /opt/projects/oro-skills
```

### 2. Install

```bash
/opt/projects/oro-skills/install.sh
```

This symlinks every `oro-*/` skill directory into `~/.claude/skills/`. Re-running it later also `git pull`s the checkout first (pass `--no-update` to skip that). To remove the symlinks: `install.sh --uninstall`.

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

- `SKILL.md` has YAML frontmatter with `name`, `description` (including trigger scenarios)
- `references/` contains the actual knowledge base documents
- Claude Code auto-discovers skills from `~/.claude/skills/*/SKILL.md`

## Adding New Skills

1. Create a new directory: `oro-<topic>/`
2. Add `SKILL.md` with frontmatter and document index
3. Add reference docs in `references/`
4. Re-run `install.sh` to pick it up

## License

MIT
