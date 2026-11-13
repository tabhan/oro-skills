# Oro version awareness

Guidance in this plugin can be scoped to Oro versions. This file is the mechanics reference (grammar,
detection, CLI); skills only say *when* to consult it.

## Constraint grammar (`oro:`)

A composer subset, compared at full `major.minor.patch` granularity (Oro patch releases add features):

| Form | Meaning |
|---|---|
| `>=7.0.5`, `>7.0`, `<=7.1.0`, `<8`, `==7.0.5`, `!=7.0.3` | comparators |
| `>=7.0.0 <7.0.5` or `>=7.0.0, <7.0.5` | AND (space or comma) |
| `^7.0` | `>=7.0.0 <8.0.0` |
| `~7.0.5` | `>=7.0.5 <7.1.0` (`~7.0` = `>=7.0.0 <8.0.0`) |
| `7.0.*`, `7.*` | wildcard ranges |
| `a \|\| b` or `a or b` | OR |

Pre-releases sort below their release (`8.0.0-beta1 < 8.0.0`). `^`, `~` and wildcard ranges starting at `N.M.0` admit that
release's pre-releases (`8.0.0-beta1` satisfies `^8.0`, not `^7.0`); `<8.0.0` excludes `8.0.0-beta1`; a plain
`>=8.0.0` does not match `8.0.0-beta1` (write `>=8.0.0-beta` to include it).

In a markdown table cell the pipe must be escaped, so write OR as `^7.0 or ^8.0` (preferred) or `^7.0 \|\| ^8.0`. A unit with no `oro:` applies as
`oro: ">=7.0.0"` (the default range; everything shipped today applies to all 7.x).

## Detection

`bin/oro-version [--project P] [--json] [--no-cache]` reads `composer.lock`: the version of `oro/platform`,
falling back to `oro/commerce`, `oro/commerce-enterprise`, `oro/crm`. If several of those are present and
disagree on major.minor a warning is printed (the first package found wins). Normalisation:

- `7.0.5`, `8.0.0-beta1`: used as is.
- `7.0.x-dev`: dev branch, patch level unknowable; treated as `7.0.0` with a warning.
- `dev-master` or any other `dev-*`: unknown.

Exit codes: 0 known, 4 unknown or undetectable (no lock, no Oro package, dev branch), 64 usage.

The result is cached in `<project>/.oro-ai/version.json` as
`{version, source_pkg, lock_sha256, warnings}`; it holds nothing time-dependent, so it changes only when `composer.lock` does (a different hash triggers re-detection).

## Units and the resolver

`bin/oro-applies` decides which units apply to the project's detected version. A unit is:

| Unit | Where the range is written |
|---|---|
| file | markdown frontmatter `oro: ">=8.0.0"`; script header `# oro: ">=8.0.0"` (first 15 lines); or implicitly `^N.0` for files under a `vN/` directory (e.g. `references/v8/`) |
| section | `<!-- oro: ">=8.0" topic: some-id -->` ... `<!-- /oro -->` in markdown |
| table row | a column headed `Oro` (blank = default); optional `Topic` column |
| hook check | `oro-atlas/hooks/checks.yml` entries `- id: ...`, `severity: deny`, `oro: "..."` |
| note | frontmatter, same as files |

`topic:` (frontmatter, section marker, `# topic:` header, `Topic` column) groups variants of the same guidance.

```bash
oro-applies --project P <path-or-topic>...     # 0 all apply, 1 some out of range (listed), 4 version unknown, 64 usage
oro-applies --project P --list-active <dir>    # files that apply, plus line spans of inactive sections/rows to skip
oro-applies --project P --list-inactive <dir>
oro-applies --project P --check <id>           # hook-check gate: run | warn | skip (exit 0 / 0 / 1; 4 unknown)
```

Higher-version content is inactive on lower projects. Unknown version: default-range content and ranges
containing `HIGHEST_SUPPORTED` (`lib/oroversion/resolve.py`) stay active as advisory, the rest is inactive,
stderr says "Oro version unknown; version-specific rules shown as advisory", and every `deny` check (annotated or
not) is downgraded to `warn` (never block on unknown). An unclosed, nested or stray `<!-- oro -->` marker prints a
warning (the lint will fail on it). Skill descriptions load globally and stay version-neutral; a skill body
points at `oro-applies --list-active <skill>` and reads only what it lists.

## Library

`lib/oroversion` (`constraint.py`, `detect.py`) is stdlib-only Python 3; `Constraint(text).matches(version)`
and `detect(project)` are what the resolver, lint and hooks build on.

## Tests

```bash
python3 -m unittest discover -s tests/oroversion
```
