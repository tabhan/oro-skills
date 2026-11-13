---
name: e2e
description: >
  Playwright-BDD (playwright-bdd) e2e authoring and running rules for OroCommerce/OroPlatform projects.
  USE WHENEVER writing, editing, reviewing or running e2e tests (any *.feature / *.steps.ts under a bundle's
  Tests/E2e, or the project's e2e harness command): fixtures and Alice tags, test-support actions, grid
  filters, purge/re-runnability, logout, Change History dialog, parallel-lane flakiness, async audit/MQ
  waits. Critical safety rule: on a shared DB never use a truncating purge tag for real entities.
---

# e2e

Automated coverage is Playwright-BDD; Behat is never run. Always run through the project's e2e wrapper with an
explicit target (`aaxis-oro test local-test e2e ...`), never a default. Browser driving by hand: use the official
`orocommerce-testing` skills. Harness mechanics are quoted from the harness READMEs, never from memory
(`references/harness.md`).

## Decide

| Question | Answer | Detail |
|---|---|---|
| Where does test data come from? | Alice `@fixture-<Bundle>:<file>.yml` with native columns/JSON; a `Tests/E2e/Action/` action only for state that is not stored data (transition logs, exports, reindex) | rules.md 1 |
| Grid scenario? | Filter on a key the fixture owns first; never assert on an unfiltered grid | rules.md 2 |
| Re-runnable? | Natural-key upsert on load; never a truncating `@fixture-fresh` for Product/User/Role/etc. | rules.md 3 |
| End of feature? | Signed out; Change History dialog closed with an explicit idempotent step | rules.md 4, 5 |
| Bug rides event + flush order? | Drive the REAL transition/action; seeded end state cannot catch it | rules.md 6 |
| "Zero results" assertion? | Empty by construction (own keyword + value the rows lack) | rules.md 7 |
| Needs data the fixture does not create? | That is a defect in the feature; no dumps, no reinstall | rules.md 8 |
| Need a clear/reindex/delete? | Scoped by id or natural key; no global DELETE, reindex or cache-pool clear | rules.md 9 |
| Running a console/Oro command in a step? | The single shared harness helper; never hard-code `--env` | rules.md 10 |
| Wide admin grid? | Viewport 1920; row-checkbox hook; mass action through its endpoint | rules.md 11 |
| New feature? | Scenario first, red for the right reason, then implement | rules.md 12 |
| Locators? | Structural hooks (class, `data-*`, column key), never label text | conventions.md |
| Audit / Change History assertion times out? | Async broker drain; a hidden empty grid means no audit recorded | debugging-audit-mq.md |
| Passes alone, fails in the full run? | Cross-feature race: fix the sharing or route to the serial lane, no sleeps | parallelism.md |
| Done? | Full non-debug run green; walk the checklist | checklist.md |

## Never

- Truncate or `DELETE` without a WHERE on a shared DB; `@fixture-fresh` only for keyless test-only entities.
- Read or write files by host path; go through the harness/Gaufrette storage.
- Rely on ambient dev data, fixed sleeps, hard-coded `timeout: <ms>` literals or env-specific ids.
- Run against the local data stack: tests target `local-test` only.

References (all under `references/`): `harness.md`, `rules.md`, `conventions.md`, `debugging-audit-mq.md`,
`parallelism.md`, `checklist.md`.
