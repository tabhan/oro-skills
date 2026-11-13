# CI vs local parity gotchas

Judgment notes for failures that appear in only one environment. Version applies to all supported Oro releases.

| Symptom | Cause | Do | Never |
|---|---|---|---|
| Unit test green locally, red in the pipeline with `MethodNotImplementedException` from a `\Locale::*` call | The pipeline PHP image has no `ext-intl`; Symfony's polyfill throws for locale-parsing methods | Avoid `\Locale::`, `NumberFormatter` and friends in code covered by unit tests; `Symfony\Component\Intl` name lookups are fine (bundled data). Reproduce with `php -n` plus the needed extensions minus intl, and run the WHOLE unit suite before pushing | Assuming local green means pipeline green |
| Pre-commit schema-drift check prints hundreds of `ADD CONSTRAINT` lines on an unrelated commit | The check measures the database the prod env resolves to; while an install or migration is mid-run that database is incomplete | Confirm which database the check resolves (the local DB, never the test stack's), wait for the install to finish, then commit again. Real drift comes only from your own entity or `entity_extend.yml` changes | `--no-verify` |
| PHPCS fails the commit on a warning | The project ruleset treats warnings as failures | Fix the warning | Raising the threshold |
