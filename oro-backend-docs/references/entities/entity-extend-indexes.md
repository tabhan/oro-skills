# Entity Extend: Indexes & Unique Constraints on Oro Entities

> Source: Aaxis EntityExtendBundle + project convention

## AGENT QUERY HINTS

This file answers:
- How do I fix "Doctrine schema drift detected" from the pre-commit hook?
- How do I add a unique constraint on an entity-extend field?
- How do I add an index on an entity-extend field?
- Why does `doctrine:schema:update --dump-sql` show DROP INDEX for my entity-extend index?
- How does the Aaxis MetadataListener register indexes on extended entities?

---

## Problem: Schema Drift on Entity-Extend Fields

When you add a unique index or regular index in a migration on an Oro entity's
entity-extend column, Doctrine's metadata does not know about it. Running
`doctrine:schema:update --dump-sql` will show a `DROP INDEX` statement — the
pre-commit hook catches this as "schema drift."

### Root Cause

Entity-extend fields are managed by Oro's `ExtendEntityTrait` — their Doctrine
metadata is generated at cache-warmup time, not declared in ORM attributes.
Indexes added in migrations exist only in the database; unless they are also
registered in metadata, Doctrine considers them orphaned.

---

## Fix: Declare in entity_extend.yml

The Aaxis `MetadataListener` (`src/Aaxis/Bundle/EntityExtendBundle/EventListener/Doctrine/MetadataListener.php`)
reads `Resources/config/aaxis/entity_extend.yml` from every bundle and applies
field mappings, indexes, and unique constraints to Doctrine ClassMetadata at runtime.

### Primary approach: fieldMappings with unique: true

For single-column unique constraints, set `unique: true` on the field mapping.
This is the simplest fix and the preferred approach:

```yaml
aaxis_entity_extend:
    Oro\Bundle\LocaleBundle\Entity\Localization:
        fieldMappings:
            url_code:
                unique: true
```

This merges into `$metadata->fieldMappings['url_code']`, and Doctrine
automatically generates the corresponding unique constraint.

### Alternative: explicit uniqueConstraints / indexes nodes

For multi-column indexes or when you need a specific index name:

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

### After adding the config

Clear cache and verify:

```bash
ccw                                          # Clear + warm cache
c doctrine:schema:update --dump-sql          # Should show "Nothing to update"
```

---

## Available YAML Nodes

| Node | Metadata target | Use case |
|------|----------------|----------|
| `fieldMappings` | `$metadata->fieldMappings` | `unique: true` for single-column unique |
| `uniqueConstraints` | `$metadata->table['uniqueConstraints']` | Multi-column unique or custom index name |
| `indexes` | `$metadata->table['indexes']` | Regular (non-unique) indexes |

---

## Quick Diagnosis

When the pre-commit hook reports drift:

1. Run `c doctrine:schema:update --dump-sql`
2. If output is `DROP INDEX <name>`:
   - The index exists in DB but not in Doctrine metadata
   - Add it to the owning bundle's `entity_extend.yml`
   - Use `fieldMappings.field.unique: true` for unique indexes
3. If output is `CREATE INDEX <name>`:
   - The index is in metadata but not in DB
   - Check entity config: `c oro:entity-config:debug 'Entity\Class'`
4. Clear cache and re-check

---

## Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Unique index (custom) | `uniq_buckman_{table}_{column}` | `uniq_buckman_localization_url_code` |
| Regular index (custom) | `idx_buckman_{table}_{column}` | `idx_buckman_product_ebs_id` |
| Oro auto-generated | `oro_idx_{entity}_{column}` | `oro_idx_localization_url_code` |
