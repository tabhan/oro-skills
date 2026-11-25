# Entity and enum gotchas

Only incident-driven content lives here; generic Oro mechanics are not mirrored.

| Task | Document | Key content |
|------|----------|-------------|
| Doctrine schema drift on entity-extend indexes (`DROP INDEX`) | `entity-extend-indexes.md` | Aaxis `MetadataListener` + `entity_extend.yml` fix for custom unique/regular indexes on entity-extend fields |
| Serialized enum-extend fields | `extend-entities.md` | Stored format (`<enum_code>.<internal_id>`), `getEnumChoicesByCode` vs `getEnumInternalChoicesByCode`, datagrid pattern, pitfalls (filter "no results", `EntityNotFoundException`) |

Everything else (entities, bundles, ACL, datagrids, API, workflows, message queue, translations, setup): use the
official plugin docs (`orocommerce-development` `backend.md`/`sql-safety.md`, `orocommerce-foundation`
`override-points.md`/`ticket-layout.md`, `orocommerce-discovery` `backend.md`/`architecture.md`) or Oro's
documentation; do not re-derive generic mechanics here. Add content here only for a genuine environment-specific
incident (a real bug, class name, ticket or migration-ordering issue actually hit).
