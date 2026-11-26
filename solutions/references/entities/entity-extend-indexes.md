# Entity Extend: indexes and unique constraints on Oro entities

## Problem: schema drift on entity-extend fields

A unique or regular index added in a migration on an Oro entity's entity-extend column is unknown to Doctrine
metadata: `doctrine:schema:update --dump-sql` shows `DROP INDEX`, which the pre-commit hook reports as "schema drift".
Cause: entity-extend fields are managed by Oro's `ExtendEntityTrait`; their metadata is generated at cache-warmup, so
DB-only indexes look orphaned.

## Fix: declare in `entity_extend.yml`

The Aaxis `MetadataListener` (`src/Aaxis/Bundle/EntityExtendBundle/EventListener/Doctrine/MetadataListener.php`) reads
`Resources/config/aaxis/entity_extend.yml` from every bundle and applies field mappings, indexes and unique
constraints to Doctrine ClassMetadata at runtime.

Single-column unique (preferred): `unique: true` on the field mapping. It merges into
`$metadata->fieldMappings['url_code']` and Doctrine generates the unique constraint.

```yaml
aaxis_entity_extend:
    Oro\Bundle\LocaleBundle\Entity\Localization:
        fieldMappings:
            url_code:
                unique: true
```

Multi-column indexes or a specific index name: explicit nodes.

```yaml
aaxis_entity_extend:
    Oro\Bundle\SomeBundle\Entity\SomeEntity:
        uniqueConstraints:
            uniq_buckman_some_table_col1_col2:
                columns: [col1, col2]
        indexes:
            idx_buckman_some_table_field:
                columns: [field_name]
```

| Node | Metadata target | Use case |
|------|----------------|----------|
| `fieldMappings` | `$metadata->fieldMappings` | `unique: true` for single-column unique |
| `uniqueConstraints` | `$metadata->table['uniqueConstraints']` | Multi-column unique or custom index name |
| `indexes` | `$metadata->table['indexes']` | Regular (non-unique) indexes |

Verify:

```bash
ccw                                          # Clear + warm cache
c doctrine:schema:update --dump-sql          # Should show "Nothing to update"
```

## Quick diagnosis (pre-commit `schema-drift` step, local database)

1. `c doctrine:schema:update --dump-sql`
2. `DROP INDEX <name>`: the index is in the DB but not in metadata. Add it to the owning bundle's `entity_extend.yml`
   (`fieldMappings.field.unique: true` for unique indexes).
3. `CREATE INDEX <name>`: in metadata but not in the DB. Check entity config: `c oro:entity-config:debug 'Entity\Class'`.
4. Clear cache and re-check.

## Naming conventions

| Type | Pattern | Example |
|------|---------|---------|
| Unique index (custom) | `uniq_buckman_{table}_{column}` | `uniq_buckman_localization_url_code` |
| Regular index (custom) | `idx_buckman_{table}_{column}` | `idx_buckman_product_ebs_id` |
| Oro auto-generated | `oro_idx_{entity}_{column}` | `oro_idx_localization_url_code` |

Postgres truncates identifiers at 63 characters: abbreviate the table/column segments when the full name would
overflow (e.g. `uniq_bkm_prod_loc_pub_prod_loc`). A truncated name still works but stops matching what the migration
declares, so the next schema diff looks like drift.
