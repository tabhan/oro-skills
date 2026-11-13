# Postgres jsonb coercion and workflow data

## 8. Postgres `jsonb` migration coercion

Oro's migration diff pipeline (DBAL 3.10 + Oro 7) **drops** the jsonb flag —
`addColumn('x','json',['customSchemaOptions'=>['jsonb'=>true]])` and the ORM `options:['jsonb'=>true]`
both yield a physical `json` column (proof: Oro's own `oro_workflow_definition.metadata` is
declared jsonb yet is physically `json`). A `GIN (jsonb_path_ops)` index and the `@>` operator
require jsonb. Pattern that works:

- **Entity:** plain `#[ORM\Column(type: Types::JSON)]` (no jsonb option) — Postgres reverse-maps
  both `json` and `jsonb` to `Types::JSON`, so a physical jsonb column introspects drift-free.
- **Migration + Installer:** add the column as plain `'json'`, then a raw
  `ALTER TABLE t ALTER COLUMN c TYPE jsonb USING c::jsonb`, then
  `CREATE INDEX IF NOT EXISTS ... USING gin (c jsonb_path_ops)`. A successful GIN create is itself
  proof the column is jsonb. Always update the bundle Installer too (bump `getMigrationVersion()`).

## 9. Oro workflow data is base64(serialize()), not jsonb

`oro_workflow_item.data` is a **text** column owned by Oro. Oro JSON-encodes the envelope, but
every attribute declared `type: array`/`type: object` is run through
`StandardAttributeNormalizer::serialize()` = `base64_encode(serialize($value))`. Oro workflows
have **no `type: json`** — arrays are always base64+PHP-serialized at rest. App code never sees
this (it reads `$workflowItem->getData()->get(...)` after Oro deserializes), and production never
SQL-queries it. Do **not** migrate workflow-data attributes to jsonb or override the core
normalizer; leave round-scoped, never-SQL-queried workflow state on the standard mechanism. Use
your own jsonb column (jsonb section above) only for data you actually need to query in SQL.

