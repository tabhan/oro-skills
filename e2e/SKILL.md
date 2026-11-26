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

## Route (rules.md is canonical; numbers are its rules)

| Question | Go to |
|---|---|
| Where does test data come from (fixtures vs actions)? | rules.md 1 |
| Grid scenario; re-runnability and the truncating-tag danger | rules.md 2, 3 |
| End of feature: sign-out, Change History dialog | rules.md 4, 5 |
| Bug rides event + flush order; zero-result assertions; ambient data; scoped clear/reindex | rules.md 6, 7, 8, 9 |
| Console/Oro command in a step; wide admin grids | rules.md 10, 11 |
| New feature: scenarios from ACs (`@spec:<ID>:AC-n`), red first, green by another agent | rules.md 12 |
| Locators, env ids, debug flag, harness gotchas, test-cache clear, timeout consts | conventions.md |
| Audit / Change History assertion times out | debugging-audit-mq.md |
| Passes alone, fails in the full run | parallelism.md |
| Done? | Related features green in a non-debug run; checklist.md |

## Budget

- After fixes, re-run only the affected features; the full suite stays on demand (checklist.md).
- Before a long or token-heavy step (full suite, refresh/cache warm, a wave of agents), say so and offer the lighter
  option.

## Never

- Truncate or `DELETE` without a WHERE on a shared DB; `@fixture-fresh` only for keyless test-only entities.
- Read or write files by host path; go through the harness/Gaufrette storage.
- Rely on ambient dev data, fixed sleeps, hard-coded `timeout: <ms>` literals or env-specific ids.
- Run against the local data stack: tests target `local-test` only.

References (all under `references/`): `harness.md`, `rules.md`, `conventions.md`, `debugging-audit-mq.md`,
`parallelism.md`, `checklist.md`.
