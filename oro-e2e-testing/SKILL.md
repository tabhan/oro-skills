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
   driving runtime side effects — fixtures purge cleanly and are deterministic. Only fall back to a
   **test-support action** when the state can't be expressed as stored data (e.g. an Oro **workflow
   transition log**, which needs real transitions to exist; a datagrid export; a reindex through
   Oro's real delete/duplicate handlers; impersonating a user to read its scope).

   The action pattern (rather than one console command per bundle): each bundle drops an action class
   under `Tests/E2e/Action/` implementing a shared `E2eTestActionInterface` (`getName()` /
   `configure(InputDefinition)` / `execute()`), and registers it as a plain service in
   `Tests/E2e/Resources/config/actions.yml` — **no tag, no `_instanceof`, no per-bundle extension
   wiring**. An extension auto-discovers that one file in every bundle (test env only) and a compiler
   pass tags + indexes the services by `getName()`; a single entry command then runs them by name
   (`bin/console <prefix>:test:action <name> [args] --env=test --no-interaction`). Check the project's
   TestBundle for the exact command prefix and interface FQCN. (This supersedes the older
   `Tests/E2e/Command/*` console-command-per-bundle approach; migrate any such command into an action.)

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
- **After adding/removing a test action (or any test service) or changing a service arg, `rm -rf
  var/cache/test`** — the test kernel caches a compiled container under a hash, and a stale one will
  throw on the changed service signature (and won't pick up a newly auto-discovered `actions.yml`).

## Debugging: async audit / message queue (Change History timeouts)

Oro **Data Audit is asynchronous** — a mutation enqueues an audit message that a consumer must
process before the audit row exists and the **Change History** grid shows it. The broker is
**env-specific**: the `test` env typically uses the **DBAL** transport (`message_queue_transport_dsn: 'dbal:'`
→ the `oro_message_queue` table), while the `prod` env (the one FPM serves the browser from) usually
uses **RabbitMQ** (`ORO_MQ_DSN=amqp://…`). So a **browser-driven** save enqueues on RabbitMQ, not
the DBAL table. A scenario must drain the broker its mutation actually used before asserting.

⚠️ **Poison audit messages on a shared dev broker.** In dev **no consumer runs**, so the prod
RabbitMQ queue (`oro.default`) accumulates a backlog. Worse, it fills with **poison messages**: an
audit for a `LocalizedFallbackValue` whose `Localization` an earlier feature created then **deleted**.
Processing it walks `ChangeSetToAuditFieldsConverter → EntityNameProvider →
LocalizedFallbackValueNameProvider->getName() → Localization->getName()` on a missing entity →
`EntityNotFoundException` → **the consumer crashes**. A harness consume step that swallows the error
then silently dies before reaching the scenario's own fresh audit message → the audit row never
appears → the Change History grid stays empty.

**Symptom signature:** the step times out on `locator.waitFor` for `.ui-dialog .grid-container` to
be **visible** (the grid mounts but stays *hidden* because it has **zero rows**) — NOT the step's own
"grid does not contain X" assertion. An empty/hidden audit grid means *no audit was recorded*, which
is an **async/broker** problem, not a selector, ACL, or `dataaudit.auditable` config problem. Confirm
the field/entity are auditable in the live `oro_entity_config[_field]` before suspecting config; if
they are, look at the queue.

**Fix to unblock a red resume run:** purge the broker queue, then resume —
`rabbitmqctl purge_queue oro.default` (run it in the RabbitMQ container; verify with
`rabbitmqctl list_queues name messages messages_ready messages_unacknowledged` → all 0. The plain
`messages` column can show a **stale cached count**; trust `messages_ready`). Because a debug/resume
run skips already-passed features, the poison-producing localization features don't re-run, so the
queue stays clean and the scenario's own audit processes. This is a **pure environment fix — no code
change**. The durable fix is to run a persistent consumer (so the broker never backs up) and/or have
localization-churning features drain their queue before deleting the localization.

## Parallelism & shared-state flakiness

The harness typically runs a **serial lane** (`@serial` scenarios, one worker) first, then a
**parallel lane** (everything else) across N workers. Two whole classes of failure come from state
shared across those workers — both look like ordinary assertion failures but are really isolation /
timing bugs, so **fixing them per-feature with sleeps or extra cleanup usually makes them worse.**

**1. The shared-session trap (CDP mode).** Browser isolation depends on the browser target:

- **Launched** (`chromium` / `chrome`): the `context` fixture is **per-test** — each scenario gets
  its own `BrowserContext` (own cookie jar, seeded with the cached admin `storageState`) that is
  closed after. Sessions never leak between workers → **parallel is session-safe.**
- **CDP** (attach to a real/standalone Chrome, e.g. WSL→host Chrome on `:9222`): every worker
  `connectOverCDP`s to the **same** browser and reuses `contexts()[0]` — **one shared cookie jar for
  all workers _and_ the developer's own session.** Any `login` / `clearCookies` / anonymous-visitor
  step from *any* worker (or a `@serial` feature, or a stale manual session) mutates that one
  session and bleeds into every concurrent scenario.

  Symptom signatures: authenticated-only navigation leaking onto an anonymous assertion (e.g. the
  customer "My Account" `/customer/*` menu — which carries **no** locale prefix — appearing on an
  anonymous storefront "all links carry the locale prefix" check); or an admin-needing scenario
  suddenly bounced to the login page mid-run (→ `waitFor` timeout) because a concurrent feature
  cleared cookies.

  **Rule:** a single shared cookie jar **cannot** host parallel scenarios with differing sessions.
  Run **CDP serial** (`workers=1`) for local watching/debugging; run the **parallel** suite in
  **`chromium`** (isolated per-test contexts). Do NOT scatter `clearCookies` / anonymous-visitor
  steps into parallel-lane features to "reset" state — on the shared jar that wipes other workers'
  sessions and multiplies the races.

  **Impersonation/preview features** (admin "Preview" → storefront via `ImpersonateUserBundle`) log
  an impersonation **frontend** session into the jar. Closing the preview *tab* is not enough — the
  step must also drop the session (`page.context().clearCookies()`), or that impersonated session
  lingers and renders the authenticated menu on later anonymous storefront features.

**2. ElasticSearch is eventually consistent — retry every storefront list/search/facet read.**
Storefront list/search/PLP pages read the website ES index. After a reindex (`oro:website-search:reindex`
or a project sync-index action), ES applies the writes only on its **next refresh** — a fixed
`waitForTimeout(2000)` is not enough under parallel load / a cold index. Any step that asserts
product or **facet** presence (or *absence*, e.g. a deleted "ghost" clone) on a storefront page must
**reload / re-request in a retry loop** until the expected state appears (or N attempts fail), the
same way the PDP / storefront-search steps already do. A single-load assertion right after a reindex
is inherently flaky — poll, don't sleep-once.

## Authoring checklist

- [ ] New data is in an Alice `@fixture-<Bundle>:<file>.yml` (native columns/JSON set directly where possible); runtime-only state goes through a `Tests/E2e/Action/` action (one `*:test:action` entry command), not a per-bundle console command.
- [ ] Re-runnable via natural-key upsert (every fixture entity has a unique key); a truncating "fresh" purge tag is used ONLY for keyless test-only entities, NEVER for Product/User/Role/etc. on a shared DB.
- [ ] Every grid scenario applies a filter before asserting rows.
- [ ] Feature ends logged out (and any restricted-user login signs out).
- [ ] Any scenario that opens the Change History dialog closes it with an explicit, idempotent step.
- [ ] Change History / audit assertions drain the correct broker (RabbitMQ for browser saves, DBAL for test-env actions); a Change-History timeout on a hidden empty grid means no audit was recorded — purge the broker (poison messages), don't chase selectors/config.
- [ ] Parallel runs use an **isolated-context** browser (`chromium`), not a shared CDP jar; no `clearCookies`/anonymous-visitor steps sprinkled into parallel-lane features; impersonation/preview steps drop the session, not just close the tab.
- [ ] Every storefront list/search/facet assertion after a reindex **retries/reloads** until the expected state appears (ES is eventually consistent) — never a single load + fixed sleep.
- [ ] Elements located by structural hooks, not labels; env-specific ids resolved via harness helpers, not hardcoded.
- [ ] Verified the filtered result set is correct (which rows remain / are excluded), not just that the page loads.
- [ ] After changing a test command/service arg, cleared `var/cache/test`.
