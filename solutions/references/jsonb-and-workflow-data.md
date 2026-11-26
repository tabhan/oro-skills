# Postgres jsonb coercion and workflow data

## Postgres `jsonb` migration coercion

Oro's migration diff pipeline (DBAL 3.10 + Oro 7) **drops** the jsonb flag: `addColumn('x','json',['customSchemaOptions'=>['jsonb'=>true]])`
and the ORM `options:['jsonb'=>true]` both yield a physical `json` column (Oro's own `oro_workflow_definition.metadata`
is declared jsonb yet physically `json`). A `GIN (jsonb_path_ops)` index and the `@>` operator require jsonb. What works:

- **Entity:** plain `#[ORM\Column(type: Types::JSON)]` (no jsonb option). Postgres reverse-maps both `json` and
  `jsonb` to `Types::JSON`, so a physical jsonb column introspects drift-free.
- **Migration + Installer:** add the column as plain `'json'`, then raw `ALTER TABLE t ALTER COLUMN c TYPE jsonb USING c::jsonb`,
  then `CREATE INDEX IF NOT EXISTS ... USING gin (c jsonb_path_ops)` (a successful GIN create proves jsonb). Always
  update the bundle Installer too (bump `getMigrationVersion()`).

## Oro workflow data is base64(serialize()), not jsonb

`oro_workflow_item.data` is a **text** column owned by Oro. Oro JSON-encodes the envelope, but every attribute of
`type: array`/`type: object` goes through `StandardAttributeNormalizer::serialize()` = `base64_encode(serialize($value))`.
Workflows have **no `type: json`**. App code reads `$workflowItem->getData()->get(...)` after Oro deserializes, and
production never SQL-queries it. Do **not** migrate workflow-data attributes to jsonb or override the core
normalizer; use your own jsonb column (above) only for data you must query in SQL.
