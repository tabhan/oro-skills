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

`aaxis-oro version [--project P] [--json] [--no-cache]` reads `composer.lock`: the version of `oro/platform`,
falling back to `oro/commerce`, `oro/commerce-enterprise`, `oro/crm`. If several of those are present and
disagree on major.minor a warning is printed (the first package found wins). Normalisation:

- `7.0.5`, `8.0.0-beta1`: used as is.
- `7.0.x-dev`: dev branch, patch level unknowable; treated as `7.0.0` with a warning.
- `dev-master` or any other `dev-*`: unknown.

Exit codes: 0 known, 4 unknown or undetectable (no lock, no Oro package, dev branch), 64 usage.

The result is cached in `<project>/.oro-ai/version.json` as
`{version, source_pkg, lock_sha256, warnings}`; it holds nothing time-dependent, so it changes only when `composer.lock` does (a different hash triggers re-detection).

## Units and the resolver

`aaxis-oro version applies` decides which units apply to the project's detected version. A unit is:

| Unit | Where the range is written |
|---|---|
| file | markdown frontmatter `oro: ">=8.0.0"`; script header `# oro: ">=8.0.0"` (first 15 lines); or implicitly `^N.0` for files under a `vN/` directory (e.g. `references/v8/`) |
| section | `<!-- oro: ">=8.0" topic: some-id -->` ... `<!-- /oro -->` in markdown |
| table row | a column headed `Oro` (blank = default); optional `Topic` column |
| hook check | `atlas/hooks/checks.yml` entries `- id: ...`, `severity: deny`, `oro: "..."` |
| note | frontmatter, same as files |

`topic:` (frontmatter, section marker, `# topic:` header, `Topic` column) groups variants of the same guidance.

```bash
aaxis-oro version applies --project P <path-or-topic>...     # 0 all apply, 1 some out of range (listed), 4 version unknown, 64 usage
aaxis-oro version applies --project P --list-active <dir>    # files that apply, plus line spans of inactive sections/rows to skip
aaxis-oro version applies --project P --list-inactive <dir>
aaxis-oro version applies --project P --check <id>           # hook-check gate: run | warn | skip (exit 0 / 0 / 1; 4 unknown)
```

Higher-version content is inactive on lower projects. Unknown version: only version-neutral content stays active
(default range or unannotated, i.e. no upper bound and no lower bound above 7.0.0, such as `>=7.0.0`); everything
version-specific (`v7/`, `v8/`, `<8`, `>=8.0.0`, `==7.0.5`) is inactive and listed, never applied. stderr says
"Oro version unknown; only version-neutral rules are active, version-specific rules are inactive (advisory)".
`--check` follows the same rule: a version-neutral check runs, a version-specific one is `skip`, and every `deny`
check (annotated or not) that runs is downgraded to `warn` (never block on unknown); exit stays 4. An unclosed, nested or stray `<!-- oro -->` marker prints a
warning (the lint will fail on it). Skill descriptions load globally and stay version-neutral; a skill body
points at `aaxis-oro version applies --list-active <skill>` and reads only what it lists.

## Authoring a version-specific variant

1. Give the existing guidance a `topic:` id (frontmatter, section marker, `# topic:` header or `Topic` column) if it has none.
2. Add the new variant as a new file or section with the same `topic:` and its own `oro:` range.
3. Narrow the old variant's range so the two adjoin, e.g. `<7.0.5` and `>=7.0.5`; the lint rejects overlaps and gaps inside a topic, and a non-default `oro:` without a `topic:`.
4. Run `aaxis-oro dev lint` (pre-commit and CI run it) and `aaxis-oro version diff --from <old> --to <new>` to see what flips.

A hook check follows the same rule: give it `oro:` and `topic:` in `atlas/hooks/checks.yml`. Notes and templates accept `oro:` in frontmatter like any file.

## Lint

```bash
aaxis-oro dev lint [--root DIR] [PATH...]    # exit 0 clean, 1 violations, 64 usage
# install.sh sets core.hooksPath .githooks for the checkout; CI is the authoritative gate
```

It checks that every `oro:` parses, that section markers are well formed, balanced and not nested (unclosed or nested markers fail),
that ranges sharing a `topic:` adjoin at patch granularity, and that skill/agent descriptions carry no version numbers. A real pre-release lower bound (`>=8.0.0-rc1`) counts as starting before its release, so it overlaps `<8.0.0`. A topic with one member that has an upper bound only warns (stderr, exit 0): the content disappears with no successor. Paths are repo-relative; `docs/` and test fixtures are not scanned.

## Upgrade diff

`aaxis-oro version diff --from 7.0.5 --to 8.0.0 [--json] [--root DIR]` lists the units (file, section, row, hook check) that activate or deactivate, with topic, title and path.
The SessionStart hook (`atlas/hooks/sessionstart_version.py`) prints the same table once when the detected version differs from the last announced one
(kept in `.oro-ai/version-announced.json`, written only after the diff succeeded and only if `.oro-ai/` exists; the first run only records it; a leading `v` is accepted by `diff`). Not yet built: a skill that compares Oro changelogs with the stamped content.

## Library

`lib/oroversion` (`constraint.py`, `detect.py`) is stdlib-only Python 3; `Constraint(text).matches(version)`
and `detect(project)` are what the resolver, lint and hooks build on.

## Tests

```bash
python3 -m unittest discover -s tests/oroversion
python3 -m unittest discover -s atlas/tests
```
