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
| `a \|\| b` | OR |

Pre-releases sort below their release (`8.0.0-beta1 < 8.0.0`). A unit with no `oro:` applies as
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
`{version, source_pkg, lock_sha256, detected_at}`; a different `composer.lock` hash triggers re-detection.

## Library

`lib/oroversion` (`constraint.py`, `detect.py`) is stdlib-only Python 3; `Constraint(text).matches(version)`
and `detect(project)` are what the resolver, lint and hooks build on.

## Tests

```bash
python3 -m unittest discover -s tests/oroversion
```
