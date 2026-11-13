# The rules


1. **Data fixtures first.** Load new test data with Nelmio **Alice YAML fixtures** via a
   `@fixture-<Bundle>:<file>.yml` feature tag (e.g. `@fixture-AcmeProductBundle:product_filters.yml`);
   the harness loads them in the test env before the feature runs. Prefer setting an entity's
   **native columns/JSON directly in the fixture** over driving runtime side effects — fixtures
   purge cleanly and are deterministic. Fall back to a **test-support action** only when the state
   can't be expressed as stored data (e.g. an Oro **workflow transition log**, which needs real
   transitions to exist; a datagrid export; a reindex through Oro's real delete/duplicate handlers;
   impersonating a user to read its scope).

   The action pattern (replacing one console command per bundle): each bundle drops an action class
   under `Tests/E2e/Action/` implementing a shared `E2eTestActionInterface` (`getName()` /
   `configure(InputDefinition)` / `execute()`), registered as a plain service in
   `Tests/E2e/Resources/config/actions.yml` — **no tag, no `_instanceof`, no per-bundle extension
   wiring**. An extension auto-discovers that one file in every bundle (test env only) and a compiler
   pass tags + indexes the services by `getName()`; a single entry command then runs them by name
   (`bin/console <prefix>:test:action <name> [args] --env=test --no-interaction`). Check the project's
   TestBundle for the exact command prefix and interface FQCN. (Supersedes the older
   `Tests/E2e/Command/*` console-command-per-bundle approach; migrate any such command into an action.)

2. **Always apply a filter when testing a grid.** A shared DB holds many pre-existing rows. Every
   grid scenario must first narrow the grid with a filter — typically a **stable code/SKU prefix the
   fixture owns** — so present/absent assertions are deterministic and the fixture rows are pinned
   to page 1. Never assert on an unfiltered grid.

3. **Purge before AND after each feature — but SAFELY on a shared DB.** Re-runnability comes from the
   loader's **natural-key upsert**: on load it deletes the rows matching each fixture object's unique
   key (sku, username, product+localization, …) and re-persists them, so re-running never stacks
   duplicates. Give every fixture entity a **natural/unique key** so this "purge-before" is scoped to
   the fixture's own rows.
   ⚠️ **Do NOT use a "fresh"/truncate purge tag (e.g. `@fixture-fresh`) for fixtures that contain
   real/shared entities (Product, User, Role, Localization, …).** On a shared DB such a tag typically
   runs `DELETE <Entity>` with **no WHERE — a full table truncation** — and because the Playwright
   harness has **no DB isolation/rollback**, it would permanently wipe the entire catalog / all users.
   A truncating tag is only safe for **test-only entities that have no natural key** (autoincrement-id
   only) and whose table you genuinely want emptied. For a clean post-feature state of real entities,
   delete only the fixture's own rows by key — never truncate.
   Even in that sanctioned case, **`@fixture-fresh` MUST be paired with `@serial`** — the harness
   throws on an unpaired one (`support/hooks.ts`), because emptying whole tables is only safe while
   no other worker is running. An unpaired tag aborts the feature at runtime, it does not degrade.

4. **Log out after each feature.** End every feature signed out so the next feature (and any live
   browser the developer is watching) starts from a clean, unauthenticated session — never inherit a
   cached or wrong-role session. Use the suite's sign-out step / `page.context().clearCookies()`; if a
   scenario logs in as a restricted user, it MUST sign out, and the feature MUST end logged out.

5. **Always close the Change History dialog in any scenario that opens it.** Change History is a
   special Oro **dialog** (the audit popup, opened via an `a[data-url*="/audit/history/"]` link →
   `.ui-dialog`). Because the suite typically shares **one long-lived browser with NO per-scenario
   isolation**, a Change History dialog left open lingers into the next scenario/feature and blocks
   its interactions (and stays stuck on the live browser the developer watches). Assertion steps that
   read the audit history usually return with the dialog **still open**, so every scenario that opens
   Change History must end with an **explicit, idempotent close step** that closes
   `.ui-dialog .ui-dialog-titlebar-close`. Applies to any new e2e that opens Change History.

## More rules

6. **Test through the real trigger.** When correctness rides an event plus flush ordering (a listener that
   materializes denormalized data by re-reading a durable log, e.g. on a workflow transition), a test that
   seeds the end state cannot catch the bug and stays falsely green. Write at least one scenario that
   drives the REAL transition or action end to end, red before the fix and green after; unit tests on
   complete inputs are necessary but not sufficient.
7. **Empty by construction.** A "zero results" assertion must be true regardless of the rest of the data: first
   narrow to the fixture's own rows with a keyword they own, then apply a facet or filter value those rows
   provably do not carry. Ask "would this still pass with ten thousand more rows?". The inverse holds too:
   assert that the fixture's rows came back, never a bare total.
8. **No ambient data.** A feature runs on a freshly installed environment plus its own fixtures. If it needs
   data its own fixture or action does not create, that is a defect in the feature, never to be fixed by
   restoring a data dump or reinstalling dev.
9. **Scoped operations only.** No unscoped `DELETE`, no full-catalog reindex, no whole cache-pool clear to reach a
   known state: they hit every concurrent worker and are what keeps features on `@serial`. Reindex and
   purge by explicit id or natural key; accept `@serial` only when the feature under test IS the shared
   global state.
10. **One console helper.** Steps never hard-code `--env=...`; every console or Oro command goes through the
    single shared harness helper that picks the env and clears config caches when it writes global config.
11. **Wide admin grids.** Pin the headless viewport at 1920 wide: at 1280 a wide grid collapses responsively
    and hides its `<thead>`. When a grid is wider than the viewport, Oro's sticky-header plugin moves the live
    header into a separate sticky table and leaves a hidden, handler-less clone, so `table.grid thead ...`
    selectors hit the clone. Select rows with the row-checkbox hook, and exercise a mass action through
    its endpoint rather than the header UI when the header is unreachable.
12. **Test first.** Write the scenario, watch it fail for the right reason, implement until green. Never write the
    e2e last to rubber-stamp finished code.

