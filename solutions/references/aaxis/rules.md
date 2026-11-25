# Aaxis bundles

Aaxis bundles (`src/Aaxis/Bundle/<X>Bundle`) are shared across projects. Before writing custom code for a need,
check [catalogue.md](catalogue.md) (need -> bundle). Bundle mechanics (config keys, classes, commands) live in each
bundle's own `README.md`; read it, never restate it from recall.

## Presence check, then use or ask

1. `ls src/Aaxis/Bundle` (or `grep -R "Aaxis.Bundle.<X>Bundle" src/*/Bundle/*/Resources/config/oro/bundles.yml`).
2. Present: use its feature; read its README first.
3. Missing: follow "Aaxis bundles" in [../../SKILL.md](../../SKILL.md) (ask, never reimplement).

## MUST

- **Entity config** (dataaudit, form, importexport, enum, attachment scopes) on an existing entity or field:
  `entity_configs.yml` + a `SetEntityConfigs extends AbstractSetEntityConfigs` fixture with a bumped `getVersion()`
  ([../entity-config.md](../entity-config.md)). Never a hand-written schema migration or SQL on `oro_entity_config*`.
- **Doctrine mapping** of an Oro entity (custom repository, unique, index, column name, association order):
  `Resources/config/aaxis/entity_extend.yml`. Never a `loadClassMetadata` listener or a vendor edit.
- **Overriding an Oro service method**: [../override-core-service.md](../override-core-service.md).
- **Enum options**: `enum_values.yml` + the abstract enum fixture, insert-only, bump the version.
- **e2e data and actions**: the TestBundle harness (e2e skill); never a parallel mechanism.
- **External providers**: behind an interface with a DI-tag registry ([../design-rules.md](../design-rules.md)).

## MUST NOT

- An Aaxis bundle must never depend on a project bundle: no project class, entity, service id, translation key, or
  datagrid join. Add project-specific needs project-side through an interceptor, event subscriber or grid extension,
  never by editing Aaxis.
- No real feature in `AppBundle` and never depend on it ([../poc-appbundle.md](../poc-appbundle.md), which holds the `AppBundle` check).
- Never edit `vendor/` or fork an Aaxis bundle into the project; ask for a bundle fix.

## Review check (review and architect gate)

Read the project namespace from `.oro-ai/local-env/env.yml` (`project_namespace`), then:

```bash
grep -rn "use <ProjectNamespace>\\\\" src/Aaxis/    # must print nothing
grep -rln "<ProjectNamespace>" src/Aaxis/ --include=*.yml --include=*.twig --include=*.xlf
```

Any hit is a blocker. If `project_namespace` is not set, ask the user once and record it in env.yml.
