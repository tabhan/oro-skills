# Entity-config seeding and changes

## 4. Entity-config seeding — one `entity_configs.yml` per bundle

For seeding entity-config values (form type/options, scopes), use the established
`AbstractSetEntityConfigs` mechanism (Aaxis EntityExtendBundle) — do not fork a parallel YAML
with a one-off fixture.

- Edit the bundle's `Migrations/Data/ORM/data/entity_configs.yml`, adding scope keys under
  `EntityClass: fields: fieldName:`.
- Bump `getVersion()` on the global `SetEntityConfigs` data fixture so
  `oro:migration:data:load` re-runs it.
- For a new entity-config scope schema, declare it in the bundle's
  `Resources/config/oro/entity_config.yml`.

A single global loader fixture merges every bundle's file, so each bundle contributes just its
own slice.

**Changing config on an EXISTING database (e.g. flipping `dataaudit.auditable`, `form.is_enabled`,
`importexport.order`) uses this SAME mechanism — NOT a hand-written schema migration.** Do not
write an `UpdateEntityConfigEntityValueQuery` / `UpdateEntityConfigFieldValueQuery` migration under
`Migrations/Schema/vX_Y/` for config changes; that is the raw Oro primitive this project has
already wrapped. Instead:

- `entity_configs.yml` sets config on ANY class, not just `Product`, and at BOTH levels. A
  top-level class key with scope keys sets entity-level config; a `fields:` block sets field-level
  config. `AbstractSetEntityConfigs::processClass` treats every top-level key other than `fields`
  as an entity scope:
  ```yaml
  Acme\Bundle\FooBundle\Entity\Bar:        # entity-level scope
      dataaudit:
          auditable: true
      fields:                              # field-level scope
          name:
              dataaudit:
                  auditable: true
  ```
- The PHP attribute defaults (`#[Config(defaultValues: …)]` / `#[ConfigField(defaultValues: …)]`)
  only seed config when an entity/field is FIRST registered — they never update an existing
  `oro_entity_config` row. So a code-only attribute edit silently no-ops on populated DBs. The
  repo's pattern is **dual**: keep the attribute default (mirrors Oro core, seeds fresh installs)
  AND add the same value to `entity_configs.yml` + bump the `SetEntityConfigs` version (applies to
  existing DBs on `oro:migration:data:load`). Set both.
- After the fixture runs, clear the cache (`cache:clear --env=prod`) so `ConfigManager`/the audit
  gate re-reads the updated snapshot. The model classes that consume the config (e.g.
  `AuditConfigProvider::isAuditableEntity` + `isAuditableField`) read the persisted DB config, not
  the attributes, at runtime.

