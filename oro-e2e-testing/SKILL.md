---
name: oro-e2e-testing
description: >
  Playwright-BDD (playwright-bdd) e2e authoring rules for OroCommerce/OroPlatform projects.
  USE WHENEVER writing, editing, or running e2e tests (any *.feature / *.steps.ts under a
  bundle's Tests/E2e, or the project's e2e harness command). Enforces: load new test data via
  Alice data fixtures first; always apply a filter when testing a grid; purge data before AND
  after each feature so it is re-runnable; log out after each feature; always close the Change
  History dialog in any scenario that opens it. Critical safety rule: on a non-isolated shared
  DB never use a full-table-truncating purge tag for real entities (Product/User/Role/...) —
  re-runnability comes from natural-key upsert instead.
  Complements oro-behat-testing (Behat is deprecated for new work) and oro-workflow.
---

# Oro e2e testing rules

Automated coverage for new work is **Playwright-BDD** (`playwright-bdd`), not Behat (Behat is
deprecated for new work). The suite runs through the project's e2e harness command against the
`--env=test` kernel.

⚠️ **Know your DB topology first.** Many Oro projects point the `test` env at the **same database
as dev/prod** (check `.env*.test*` for the DSN). When the e2e DB is **shared and non-isolated**
(no per-scenario transaction rollback, one long-lived browser), test-data hygiene is mandatory and
destructive purges are dangerous. The rules below assume that worst case; if your project genuinely
has an isolated/throwaway test DB, the safety caveats relax but the structure still applies.

## The rules

1. **Data fixtures first.** Load new test data with Nelmio **Alice YAML fixtures**, referenced from
   the feature via a `@fixture-<Bundle>:<file>.yml` tag (e.g.
   `@fixture-AcmeProductBundle:product_filters.yml`). The harness loads them in the test env before
   the feature runs. Prefer setting an entity's **native columns/JSON directly in the fixture** over
   driving runtime side effects from a command — fixtures purge cleanly and are deterministic. Only
   fall back to a test command (a `Tests/E2e/Command/*` console command) when the state can't be
   expressed as stored data (e.g. an Oro **workflow transition log**, which needs real transitions
   to exist).

2. **Always apply a filter when testing a grid.** A shared DB holds many pre-existing rows. Every
   grid scenario must first narrow the grid with a filter — typically a **stable code/SKU prefix the
   fixture owns** — so assertions about which rows are present/absent are deterministic and the
   fixture rows are pinned to page 1. Never assert on an unfiltered grid.

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

## Conventions (general Oro / playwright-bdd harness)

- **Locate elements by stable structural hooks** — class / `data-*` attributes / column key
  `td.grid-body-cell-<key>` — **never by visible label text** (label text is env-specific and can be
  overridden by a DB UI translation).
- **Resolve env-specific ids via harness helpers, never hardcode** — localization ids via the
  harness's localization map (e.g. `config.localizations[code]`), entity ids via the suite's
  entity-id resolver. Hardcoded ids break across environments.
- **Run one feature** with the harness's debug flag + a grep on its tag, so you restrict the run to
  the impacted feature (debug mode usually means: stop on first failure, skip already-passed
  scenarios). Check the project's harness for the exact flag names.
- **After adding/removing a test command or changing a test service arg, `rm -rf var/cache/test`** —
  the test kernel caches a compiled container under a hash and a stale one will throw on the changed
  service signature.

## Authoring checklist

- [ ] New data is in an Alice `@fixture-<Bundle>:<file>.yml` (native columns/JSON set directly where possible).
- [ ] Re-runnable via natural-key upsert (every fixture entity has a unique key); a truncating "fresh" purge tag is used ONLY for keyless test-only entities, NEVER for Product/User/Role/etc. on a shared DB.
- [ ] Every grid scenario applies a filter before asserting rows.
- [ ] Feature ends logged out (and any restricted-user login signs out).
- [ ] Any scenario that opens the Change History dialog closes it with an explicit, idempotent step.
- [ ] Elements located by structural hooks, not labels; env-specific ids resolved via harness helpers, not hardcoded.
- [ ] Verified the filtered result set is correct (which rows remain / are excluded), not just that the page loads.
- [ ] After changing a test command/service arg, cleared `var/cache/test`.
