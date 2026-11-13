# Conventions


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
- **Harness gotchas.** `--grep <tag>` does NOT limit the serial lane: running any `@serial` feature drags the
  whole serial lane (use the parallel-only project selection for a single parallel feature). `cache:clear
  --env=test` with warmup can crash on generated test entities that do not exist yet: use `--no-warmup`.
  Alice fixtures reject a second top-level `ClassName:` key in one file ("Duplicate key"): add new objects
  INTO the existing block. Never pipe the e2e command into `tail`/`head`: the pipe hides the real exit code.
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

