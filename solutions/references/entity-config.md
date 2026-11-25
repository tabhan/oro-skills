# Entity-config seeding and changes

Seed and change entity-config values (form type/options, `dataaudit.auditable`, `form.is_enabled`,
`importexport.order`, scopes), on fresh and EXISTING databases alike, with the `AbstractSetEntityConfigs` mechanism
(Aaxis EntityExtendBundle). Do not fork a parallel YAML or one-off fixture, and do not write an
`UpdateEntityConfigEntityValueQuery` / `UpdateEntityConfigFieldValueQuery` migration under `Migrations/Schema/vX_Y/`
(the raw Oro primitive this project already wrapped).

- Edit the bundle's `Migrations/Data/ORM/data/entity_configs.yml`; one global `SetEntityConfigs` loader fixture merges
  every bundle's file, so each bundle contributes only its own slice.
- Bump `getVersion()` on that `SetEntityConfigs` fixture so `oro:migration:data:load` re-runs it.
- A new entity-config scope schema is declared in the bundle's `Resources/config/oro/entity_config.yml`.
- The file configures ANY class at BOTH levels. `AbstractSetEntityConfigs::processClass` treats every top-level key
  other than `fields` as an entity scope:
  ```yaml
  Acme\Bundle\FooBundle\Entity\Bar:        # entity-level scope
      dataaudit:
          auditable: true
      fields:                              # field-level scope
          name:
              dataaudit:
                  auditable: true
  ```
- PHP attribute defaults (`#[Config(defaultValues: ...)]` / `#[ConfigField(defaultValues: ...)]`) seed config only when
  an entity/field is FIRST registered and never update an existing `oro_entity_config` row, so a code-only edit
  silently no-ops on populated DBs. Set **both**: keep the attribute default (mirrors Oro core, seeds fresh installs)
  AND add the value to `entity_configs.yml` + bump the version.
- After the fixture runs, `cache:clear --env=prod` so `ConfigManager` and the audit gate re-read the snapshot (e.g.
  `AuditConfigProvider::isAuditableEntity` / `isAuditableField` read the persisted DB config, not the attributes).
