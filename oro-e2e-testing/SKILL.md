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
  Complements oro-workflow.
---

# Oro e2e testing rules

Automated coverage is **Playwright-BDD** (`playwright-bdd`) — Behat is no longer used. The suite
runs via the project's e2e harness command against the `--env=test` kernel.

This skill covers authoring/running the **automated BDD suite** and its Buckman-specific gotchas
only. For interactively driving a browser (manual verification, screenshots, ad-hoc debugging,
storage-state/session management, tracing/video, request mocking, generic selector/locator
mechanics), use the official `oroinc/ai-dev-platform` `orocommerce-testing` plugin's
`test-in-browser` / `use-playwright` skills instead of duplicating that here.

## Where the harness itself is documented — read it, don't guess

This skill holds the *judgment* calls (what to tag, what to purge, what never to truncate). The
*mechanics* of the harness live next to its code and are the authority whenever the two could
disagree — flags, config keys, and setup steps change with the code, and the copy that ships beside
the code is the one that gets updated:

| Document | Owns |
|---|---|
| `src/Aaxis/Bundle/TestBundle/Resources/e2e/README.md` | The harness: `aaxis:test:e2e` and its `-d` loop, `aaxis:test:action` test-support actions, `@fixture-fresh` purge semantics, worker-scoped fixture data, Elasticsearch index + async-audit MQ drain, the parallelism model and `playwright.config.ts` projects, CDP attach, reporters, PHP-FPM tuning |
| `src/Aaxis/Bundle/TestBundle/README.md` | The bundle: Behat helpers, `UpsertAwareFixtureLoader`, `WorkerNamespace`, test-only commands and services |
| `src/Aaxis/Bundle/TestBundle/Resources/bin/README.md` | The `behat-each` runner |

Read the relevant section BEFORE changing harness configuration, adding a test-support action, or
reasoning about why a lane behaves the way it does. Never restate a flag or config value from
memory — quote it from the README.

**This harness is bespoke.** Generic `playwright test` / playwright-cli references describe a
different setup: they do not know `aaxis:test:e2e`, the fixture tags, or the lane structure. If the
paths above do not exist in the current project, it uses a different harness — only the authoring
rules below apply, and the harness mechanics must be re-derived from that project's own config.

⚠️ **Know your DB topology first.** Many Oro projects point the `test` env at the **same database
as dev/prod** (check `.env*.test*` for the DSN). When the e2e DB is **shared and non-isolated**
(no per-scenario transaction rollback, one long-lived browser), test-data hygiene is mandatory and
destructive purges are dangerous. The rules below assume that worst case; on a genuinely
isolated/throwaway test DB the safety caveats relax but the structure still applies.

## The rules

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

## Conventions (general Oro / playwright-bdd harness)

- **Locate elements by stable structural hooks** — class / `data-*` attributes / column key
  `td.grid-body-cell-<key>` — **never by visible label text** (label text is env-specific and can be
  overridden by a DB UI translation).
- **Resolve env-specific ids via harness helpers, never hardcode** — localization ids via the
  harness's localization map (e.g. `config.localizations[code]`), entity ids via the suite's
  entity-id resolver. Hardcoded ids break across environments.
- **Iterate with the debug flag, then confirm with a full non-debug run.** Chase a failure with the
  harness's debug flag + a grep on its tag to restrict the run to the impacted feature (debug mode
  usually means: stop on first failure, skip already-passed scenarios — check the project's harness
  for the exact flag names). Debug mode runs a *reduced, stop-on-first-fail* set, so its concurrency
  mix differs from a real run and can hide a cross-feature parallel race. **Always finish with a full
  run with the debug flag OFF** — a feature is only fixed once it is green in the full parallel suite.
- **After adding/removing a test action (or any test service) or changing a service arg, `rm -rf
  var/cache/test`** — the test kernel caches a compiled container under a hash, and a stale one will
  throw on the changed service signature (and won't pick up a newly auto-discovered `actions.yml`).
- **Never hardcode `timeout: <ms>` wait ceilings in steps — import a shared const.** The Aaxis test
  bundle exposes named timeout budgets at `support/timeouts.ts` (import via the `@e2e/timeouts`
  alias): `VISIBLE_TIMEOUT` (15s, the default element/assertion wait), `SETTLE_TIMEOUT` (20s, grid
  AJAX / ES aggregation lag), `JOB_TIMEOUT` (40s, reindex/mass-action jobs), `MEDIUM_TIMEOUT` (10s),
  `SHORT_TIMEOUT` (5s), `PROBE_TIMEOUT` (8s, optional `.catch()`-guarded "did it appear?" looks),
  `BRIEF_TIMEOUT` (2s, fast negative probes). Pick by intent, not raw number, and add a new named
  const there rather than reintroducing a literal. (Genuinely one-off waits — e.g. a 60s large-file
  upload — may stay inline with a comment. These are *ceilings* for web-first waits; a fixed
  `waitForTimeout` sleep is a separate anti-pattern to avoid, not a value to centralize.)

## Debugging: async audit / message queue (Change History timeouts)

Oro **Data Audit is asynchronous** — a mutation enqueues an audit message that a consumer must
process before the audit row exists and the **Change History** grid shows it. The broker is
**env-specific**: the `test` env typically uses the **DBAL** transport (`message_queue_transport_dsn: 'dbal:'`
→ the `oro_message_queue` table), while the `prod` env (the one FPM serves the browser from) usually
uses **RabbitMQ** (`ORO_MQ_DSN=amqp://…`). So a **browser-driven** save enqueues on RabbitMQ, not
the DBAL table — drain the broker the mutation actually used before asserting.

⚠️ **Poison audit messages on a shared dev broker.** In dev **no consumer runs**, so the prod
RabbitMQ queue (`oro.default`) accumulates a backlog. Worse, it fills with **poison messages**: an
audit for a `LocalizedFallbackValue` whose `Localization` an earlier feature created then **deleted**.
Processing it walks `ChangeSetToAuditFieldsConverter → EntityNameProvider →
LocalizedFallbackValueNameProvider->getName() → Localization->getName()` on a missing entity →
`EntityNotFoundException` → **the consumer crashes**. A harness consume step that swallows the error
silently dies before reaching the scenario's own fresh audit message → the audit row never appears →
the Change History grid stays empty.

**Symptom signature:** the step times out on `locator.waitFor` for `.ui-dialog .grid-container` to
be **visible** (the grid mounts but stays *hidden* because it has **zero rows**) — NOT the step's own
"grid does not contain X" assertion. An empty/hidden audit grid means *no audit was recorded*, which
is an **async/broker** problem, not a selector, ACL, or `dataaudit.auditable` config problem. Confirm
the field/entity are auditable in the live `oro_entity_config[_field]` before suspecting config; if
they are, look at the queue.

**In-harness durable fix (implemented):** each feature's `AfterAll` runs `drainProdQueue` — a
**single** `oro:message-queue:consume --time-limit="+12 seconds"` pass against the prod env, serving
as both settle window and drain. Oro flushes buffered audit messages on `kernel.terminate` (after
the HTTP response returns), so a benign audit can arrive on the broker tens of seconds after the
scenario step finishes; the consumer holds a **live subscription for the whole window** (its receive
loop keeps polling until the time limit), so a message landing mid-window is still received and
processed in the same pass — no separate wait needed. **Poison is detected by matching
`EntityNotFoundException` in the captured stdout+stderr** (not by exit code — the consumer also
exits non-zero on its normal time/message limit; a clean expiry prints only `"The limit time has
passed."`, never that exception). Only when poison is detected does the `AfterAll` call
`purgeProdQueue()` (`rabbitmqctl purge_queue oro.default`) and throw — the feature **fails**. Raw
queue depth is never a fail signal. There is **no purge-before guard** — a raw-depth purge before
consuming would race concurrent workers on the shared broker. `prodQueueDepth()` is a
manual-diagnostic helper only — the teardown no longer calls it. To clear a pre-existing backlog by
hand before a run: `docker exec buckman-rabbitmq-1 rabbitmqctl purge_queue oro.default` (verify with
`rabbitmqctl list_queues name messages_ready` → 0).

## Parallelism & shared-state flakiness

The harness runs a **serial lane** (`@serial` scenarios, one worker) before a **parallel lane**
(everything else) — the exact project definitions, worker counts, and fixture-load locking are in
the harness README's "Parallelism model"; read them there rather than assuming. What matters here is
the consequence: three whole classes of failure come from state shared across those workers — all
look like ordinary assertion failures but are really isolation / timing bugs, so **fixing them
per-feature with sleeps or extra cleanup usually makes them worse.**

**Prefer parallel; `@serial` is the fallback, not the default.** Parallel is what keeps the suite
fast — reach for the parallel-safe fix first (key-scoped upserting fixtures; idempotent, narrowly
scoped seed/purge that deletes only the feature's own rows; a filter on every grid/list assertion),
and tag a feature `@serial` only when it unavoidably reads or writes **global singleton state** (the
one web-catalog tree, the root content node, the global message queue, a system-config value) that
no key-scoping can isolate.

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

**3. Cross-feature shared-state race — passes in isolation, fails only in the full parallel run.**
The signature: a scenario is green under `--grep` / the serial lane / the debug flag's reduced set,
but fails in a full parallel run, and the failure looks like the data simply **isn't there at read
time** — a seeded storefront URL returns **404** (its slug was momentarily detached), an admin grid
shows **zero rows** / a seeded row is missing, or a value the feature created is gone mid-scenario.
This is almost never a selector/ACL/timing bug in the failing feature: while feature A asserts, a
*different* feature B on another worker mutates the same shared state — its `BeforeAll`/`AfterAll`
purge deletes A's rows, its re-seed upserts (delete-then-insert) the exact row A is reading, or its
queue drain runs the web-catalog `DirectUrlProcessor`, which regenerates and briefly detaches the
slug A's URL resolves through. A fixture-load file lock only serializes *loads* — it does not protect
a read in A from a write in B between loads.

**Diagnose:** (1) re-run the feature alone (`--grep "<title>"`, serial lane) — if it passes alone but
fails in the full run, it's a parallel race, not a feature bug; (2) open the HTML report trace for the
failing step and read the **actual HTTP response** (a `404` document, or a datagrid XHR with
`totalRecords: 0`) to confirm the data was absent, not mis-located.
**Fix:** first try the parallel-safe options (key-scope + upsert the fixture; make seed/purge
idempotent and own-rows-only). If the feature genuinely reads/writes global singleton state, tag the
**feature** `@serial` so it runs on the single serial worker, before the parallel lane, with nothing
mutating shared state underneath it.

## Authoring checklist

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
