# Authoring checklist

Rule numbers are `rules.md`; conventions are `conventions.md`.

- [ ] Scenarios come from ticket/spec ACs (`@spec:<ID>:AC-n`), seen red first; the final green run is by an agent that did not write them (rule 12).
- [ ] Data: Alice fixtures, runtime-only state via a `Tests/E2e/Action/` action (rule 1); natural keys, `@fixture-fresh` only for keyless entities and paired with `@serial` (rule 3).
- [ ] Grid scenarios filter first and verify the actual rows, present and excluded (rules 2, 7).
- [ ] Feature ends logged out; any Change History dialog opened is closed (rules 4, 5).
- [ ] Real transition scenario for event/flush behaviour; no ambient data; no global clear/reindex (rules 6, 8, 9); console via the shared helper (rule 10); wide grids per rule 11.
- [ ] Audit/Change History assertions account for the async broker (RabbitMQ for browser saves, DBAL for test-env actions; `debugging-audit-mq.md` for the `AfterAll` drain-and-poison contract); a timeout on a hidden empty grid means no audit was recorded, not a selector bug.
- [ ] Parallel runs use an isolated-context browser (`chromium`), not a shared CDP jar; no stray `clearCookies`/anonymous-visitor steps in parallel-lane features; impersonation/preview steps drop the session, not just close the tab.
- [ ] Storefront list/search/facet assertions after a reindex retry/reload until the expected state appears (ES is eventually consistent); no single load plus fixed sleep.
- [ ] Parallel-safe where possible; `@serial` only for unavoidable global-singleton state. Passes alone, fails in the full run: cross-feature race, fix the sharing or use the serial lane, no sleeps (`parallelism.md`).
- [ ] Related e2e (new/changed scenarios + features sharing changed steps/fixtures) green in a non-debug run (conventions.md: debug mode can hide a parallel race). The full suite is on demand or scheduled by the project.
- [ ] Locators, env ids, wait ceilings (`@e2e/timeouts` consts) and `var/cache/test` clearing per conventions.md.
- [ ] Files are read and written only through the harness/Gaufrette storage, never by host path (solutions skill, design-rules.md).
