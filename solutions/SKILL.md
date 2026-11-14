---
name: solutions
description: >-
  Task-indexed OroCommerce solution knowledge, supplementing Oro's docs. Consult BEFORE designing, implementing or
  reviewing: dialog/drawer or content-widget forms; overriding a core service method (aspect interceptor vs
  `decorates:`); standard-entity schema/index/unique/repository changes (`entity_extend.yml`); entity config on
  existing DBs (`entity_configs.yml`); enum fields; datagrids and report grids; migrations, jsonb, workflow data;
  storefront localization; PHPUnit stubs; cache invalidation, aliases, dev loop; asset busting; cron config fields;
  external providers; Aaxis bundles (src/Aaxis); spikes and POC code.
---

# solutions

Pick the task, open the reference, then check Oro's docs for mechanics the reference does not cover. Cite the
reference and the Oro doc page in the plan. Run `aaxis-oro atlas ...` first for "which hook exists".

| Task | Reference (in `references/`) |
|---|---|
| Dialog/drawer form, content-widget form, AJAX submit | `dialog-forms/flow.md`, then `controller.md`, `form-handler.md`, `layout.md`, `form-template.md`, `javascript-trigger.md`, `pitfalls.md` |
| Override or wrap a core service method; decorator vs interceptor; repository swap | `override-core-service.md`, `dev-loop/service-overrides.md` |
| Change a standard entity's schema, index, unique, repository | `entities/entity-extend-indexes.md`, `aaxis/rules.md` |
| Entity config (dataaudit, form, importexport) on existing entity/field | `entity-config.md` |
| Enum options, serialized enum field storage/filter/grid | `entities/extend-entities.md` |
| Datagrid or report grid (cache, `apply_callback`, GROUP BY, toolbar) | `datagrid.md` |
| Migration, jsonb column, workflow item data | `jsonb-and-workflow-data.md` |
| Storefront localized values | `storefront-localization.md` |
| PHPUnit for entities, what unit tests are for | `phpunit.md` |
| Trace runtime behaviour with logger levels | `runtime-debugging.md` |
| Cache clear, aliases (`c`, `cc`, `ccw`), services.yml policy, cron config groups | `dev-loop/README.md` (aliases, cache-invalidation, system-config-groups) |
| Assets rebuilt but browser serves old/blocked JS | `asset-cache-busting.md` |
| File access, external providers, Aaxis independence, Oro precedent | `design-rules.md` |
| Situation -> lever -> forbidden move table (CI, import, Backbone, workflow, DQL) | `decision-tables.md` |
| Need an Aaxis bundle? (need -> bundle) | `aaxis/catalogue.md`, rules in `aaxis/rules.md` |
| Spike, experiment, one-off | `poc-appbundle.md` |
| Why a Ticket process or Review rule exists (root-cause detail, failure each rule prevents) | `process-rules-rationale.md` |

## Oro docs pointers

Mechanics the references skip (entities, ACL, API, MQ, bundles, layouts) live in Oro's official documentation and
the oroinc/ai-dev-platform plugin references. Open them for the API; use this skill for the project decisions.

## Aaxis bundles (`src/Aaxis/Bundle`)

Before custom code, check `aaxis/catalogue.md`, then `ls src/Aaxis/Bundle`. If the needed bundle is missing: name the
bundle and the task that needs it, say "install Aaxis <X> manually; contact hantab@aaxis.io", state the fallback and
its risk, and stop on that need until the user confirms. Never reimplement it silently.

## Rules that apply everywhere

- Core service method override: `aaxis_aspect.interceptor`; a decorator only when `aaxis-oro atlas unsafe <Class>`
  shows no concrete-class consumer. Interceptors must be stateless (one proxy instance serves every call).
- Entity config and mapping changes are declarative (`entity_configs.yml`, `aaxis/entity_extend.yml`), never hand SQL.
- Aaxis bundles never depend on project code.
- POC standard: spikes live in the git-ignored `src/Aaxis/Bundle/AppBundle` and are never committed or depended on.
  Review and the architect gate reject any diff or commit containing an `AppBundle/` path.
- Never edit `vendor/`.
