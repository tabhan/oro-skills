# Harness docs and DB topology


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
recall — quote it from the README.

**This harness is bespoke.** Generic `playwright test` / playwright-cli references describe a
different setup: they do not know `aaxis:test:e2e`, the fixture tags, or the lane structure. If the
paths above do not exist in the current project, it uses a different harness — only the authoring
rules below apply, and the harness mechanics must be re-derived from that project's own config.

⚠️ **Know your DB topology first.** A local test stack has its own database; CI and some projects point the
`test` env at the **same database as dev/prod** (check `.env*.test*` for the DSN). When the e2e DB is **shared and non-isolated**
(no per-scenario transaction rollback, one long-lived browser), test-data hygiene is mandatory and
destructive purges are dangerous. The rules below assume that worst case; on a genuinely
isolated/throwaway test DB the safety caveats relax but the structure still applies.
