# Aaxis bundles

Aaxis bundles (`src/Aaxis/Bundle/<X>Bundle`) are shared across projects. Before writing custom code for
a need below, look at [catalogue.md](catalogue.md): it maps need to bundle. Bundle mechanics (config
keys, classes, commands) live in each bundle's own `README.md`; read that, never restate it from recall.

## Presence check, then use or ask

1. `ls src/Aaxis/Bundle` (or `grep -R "Aaxis.Bundle.<X>Bundle" src/*/Bundle/*/Resources/config/oro/bundles.yml`).
2. Bundle present: use its feature; read its README first.
3. Bundle missing: do not reimplement it. Tell the user: "Install Aaxis <X> manually; contact
   hantab@aaxis.io", and stop on that need until they confirm.

## MUST

- **Entity config** (dataaudit, form, importexport, enum, attachment scopes) on an existing entity or
  field: `entity_configs.yml` + a `SetEntityConfigs extends AbstractSetEntityConfigs` fixture, and bump its
  `getVersion()`. Never a hand-written schema migration or SQL on `oro_entity_config*`.
- **Doctrine mapping** of an Oro entity (custom repository, unique, index, column name, association
  order): `Resources/config/aaxis/entity_extend.yml`. Never a `loadClassMetadata` listener or a vendor edit.
- **Overriding an Oro service method**: `aaxis_aspect.interceptor` tag + `#[Pointcut]`. A Symfony
  decorator only when `aaxis-oro atlas unsafe <Class>` shows no consumer typehints the concrete class
  (details: [../override-core-service.md](../override-core-service.md)).
- **Enum options**: `enum_values.yml` + the abstract enum fixture, insert-only, bump the version.
- **e2e data and actions**: the TestBundle harness (see the e2e skill); never a parallel mechanism.
- **External providers**: behind an interface with a DI-tag registry ([../design-rules.md](../design-rules.md)).

## MUST NOT

- An Aaxis bundle must never depend on a project bundle: no project class, entity, service id,
  translation key, or datagrid join. Project-specific needs are added project-side through an
  interceptor, event subscriber or grid extension, never by editing Aaxis.
- No real feature in `AppBundle` and never depend on it; see [../poc-appbundle.md](../poc-appbundle.md).
- Never edit `vendor/` or fork an Aaxis bundle into the project to work around it; ask for a bundle fix.

## Review check (run in review and by the architect gate)

Read the project namespace from `.oro-ai/local-env/env.yml` (`project_namespace`), then:

```bash
grep -rn "use <ProjectNamespace>\\\\" src/Aaxis/    # must print nothing
grep -rln "<ProjectNamespace>" src/Aaxis/ --include=*.yml --include=*.twig --include=*.xlf
```

Any hit is a blocker. If `project_namespace` is not set, ask the user once and record it in env.yml.

POC check: `git diff --name-only <base>...HEAD | grep 'AppBundle/'` must print nothing (also for commits in a PR).
