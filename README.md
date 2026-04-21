# Oro Skills for Claude Code

Reusable [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for OroCommerce development. Each skill is a self-contained knowledge base that Claude Code consults automatically when working on relevant tasks.

## Available Skills

| Skill | Description |
|-------|-------------|
| [oro-behat-testing](oro-behat-testing/) | Writing, debugging, and optimizing Behat acceptance tests for OroCommerce |
| [oro-dialog-forms](oro-dialog-forms/) | Building frontend dialog/drawer forms that also work as landing-page content widgets (controller → handler → layout → Twig → JS trigger → locale URLs) |

## Installation

### 1. Clone or download

```bash
git clone https://github.com/tabhan/oro-skills.git
```

### 2. Symlink skills into Claude Code's skills directory

```bash
# Create the skills directory if it doesn't exist
mkdir -p ~/.claude/skills

# Symlink individual skills
ln -s /path/to/oro-skills/oro-behat-testing ~/.claude/skills/oro-behat-testing
```

Or to install all skills at once:

```bash
for skill in /path/to/oro-skills/oro-*/; do
  ln -sf "$skill" ~/.claude/skills/$(basename "$skill")
done
```

### 3. Verify

Start a new Claude Code session. The skill should appear in the available skills list automatically. You can verify by asking Claude Code to write a Behat test -- it will consult the skill's documentation.

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
4. Symlink into `~/.claude/skills/`

## License

MIT
