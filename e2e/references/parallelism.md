# Parallelism and shared-state flakiness


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
**Fix:** try the parallel-safe options first, roughly in this order, before reaching for `@serial`:
1. Key-scope + upsert the fixture (worker-scoped natural key, re-loadable without a purge).
2. Make seed/purge idempotent and own-rows-only (never a full-table/global sweep).
3. **Simulate the effect via the DOM/network layer instead of mutating shared DB state.** When the
   thing under test is really "what does the storefront render when X is absent/disabled" and X is a
   global singleton (a fixed-alias content block, a system-config flag with no per-request override),
   don't toggle the real row — intercept the response instead (`page.route()` to strip the marker
   attribute/element the real disabled-state would omit, or `page.addInitScript()` to remove it
   client-side) and assert the same DOM contract the disabled state produces. This reproduces the
   effect other workers would see as "disabled" without ever writing to the shared row. Only worth the
   residual gap (it stops covering the *toggle write path itself* — keep that one write-path
   assertion, if it must exist, in a PHP/functional test instead) when no parallel-safe write exists.
4. Only if none of the above apply — the feature genuinely reads/writes global singleton state (the
   one web-catalog tree, the root content node, the global message queue, a system-config value, a
   whole-table migration/repair action, a globally-keyed enum option with no per-worker dimension) —
   tag the **feature** `@serial` so it runs on the single serial worker, before the parallel lane, with
   nothing mutating shared state underneath it. Confirm it's actually unavoidable by naming the
   specific mechanism (quote the query/action), not by copy-pasting a neighboring feature's tag.

**Shared-fixture purge hazard.** Before adding a `BeforeAll`/`AfterAll` purge to a feature's steps
file, grep the fixture filename across every `.feature` file — if more than one feature loads the
same `@fixture-<Bundle>:<file>.yml`, do **not** add a purge hook scoped to just one of them. The
loader caches loaded spec-sets per worker (`loadedKeys` in `hooks.ts`) and skips reload on a cache
hit; purging the shared rows without invalidating that cache leaves the *next* feature sharing the
fixture believing it's still loaded, so its Background silently finds the rows gone. Either rely on
the fixture's own natural-key upsert (no purge needed) or, if a genuine per-feature purge is required,
first confirm the fixture is feature-exclusive.

