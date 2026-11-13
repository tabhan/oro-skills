# Authoring checklist


- [ ] New data lives in an Alice `@fixture-<Bundle>:<file>.yml` (native columns/JSON set directly where possible); runtime-only state goes through a `Tests/E2e/Action/` action, not a per-bundle console command.
- [ ] Every fixture entity has a natural/unique key (re-runnable via upsert); a truncating "fresh" purge tag is used ONLY for keyless test-only entities, NEVER for Product/User/Role/etc. on a shared DB.
- [ ] Every grid scenario applies a filter before asserting rows.
- [ ] Feature ends logged out (any restricted-user login signs back out).
- [ ] Any scenario that opens the Change History dialog closes it with an explicit, idempotent step.
- [ ] Change History / audit assertions account for the async broker (RabbitMQ for browser saves, DBAL for test-env actions) — see the Debugging section for the `AfterAll` drain-and-poison-detection contract; a timeout on a hidden empty grid means no audit was recorded, not a selector/config bug.
- [ ] Parallel runs use an **isolated-context** browser (`chromium`), not a shared CDP jar; no stray `clearCookies`/anonymous-visitor steps in parallel-lane features; impersonation/preview steps drop the session, not just close the tab.
- [ ] Storefront list/search/facet assertions after a reindex **retry/reload** until the expected state appears (ES is eventually consistent) — never a single load + fixed sleep.
- [ ] Kept parallel-safe where possible (key-scoped upserting fixtures; idempotent own-rows-only seed/purge); tagged `@serial` ONLY for unavoidable global-singleton state. A scenario that passes alone but fails in the full parallel run is a cross-feature race — fix the sharing or route to the serial lane, don't add sleeps.
- [ ] Confirmed with a full **non-debug** run (the debug flag's reduced set can hide a parallel race).
- [ ] Elements located by structural hooks, not labels; env-specific ids resolved via harness helpers, not hardcoded.
- [ ] Wait ceilings use a named const from `@e2e/timeouts` (`VISIBLE_TIMEOUT`, `SETTLE_TIMEOUT`, …), not a hardcoded `timeout: <ms>` literal.
- [ ] Verified the filtered result set's actual rows (present/excluded), not just that the page loads.
- [ ] Cleared `var/cache/test` after changing a test command/service arg.
- [ ] Event/flush-ordering behaviour has a scenario driving the real transition (rule 6); empty-state scenarios are empty by construction (rule 7); no reliance on ambient data (rule 8); no global clear/reindex (rule 9).
- [ ] Files are read and written only through the harness/Gaufrette storage, never by path on the host disk (solutions skill, design-rules.md).

