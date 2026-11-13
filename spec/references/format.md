# Spec format and tags

## File

`spec/spec-<purpose>-<feature>.md`, `purpose` one of schema|tool|data|infrastructure|process|architecture|design
(official `create-spec` naming). Keep the official template sections; add to the front matter:

```
id: CART          # uppercase, [A-Z0-9_-], unique, never reused
status: active    # active|draft|retired (retired: all its ACs are retired)
```

Specs without `id` are ignored by the CLI (plain official specs stay valid).

## Acceptance criteria (section 5)

```
### AC-3: Guest cannot see price
Layer: e2e                      # optional: e2e|functional; omitted = either
- Given a guest, When the PLP loads, Then no price is shown.
```

- Numbers per spec, immutable, never reused or renumbered. Changed obligation = new number.
- Retired ACs go under a `## Retired` heading, title kept, `superseded by AC-n` optional.
- Each active AC needs Given, When and Then.

## Tags

- Playwright-BDD: `@spec:CART:AC-3` on the Feature or Scenario line.
- PHPUnit Functional: `#[Group('spec:CART:AC-3')]` on class or method.
- Static scan covers `*.feature|ts|js|php` under `--tests` (default `src`); kind from path:
  `Tests/E2e` or `.feature` = e2e, `Tests/Functional` = functional, `Tests/Unit` = never counts.

## Report inputs

`aaxis-oro spec report [--e2e results.json] [--junit phpunit.xml ...] [--groups-xml F] [--sha S] [--ids A,B] [--out md]`.
Default e2e input: newest `var/e2e-results/<ts>/results.json` (Playwright JSON; tags appear as `spec:ID:AC-n`).
PHPUnit JUnit carries no groups: also pass `phpunit --list-tests-xml F` output as `--groups-xml`.
A report covers only what the run executed: pass `--ids` for a partial run, otherwise untested ACs read "not run".
