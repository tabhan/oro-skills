---
name: oro-backend-docs
description: >
  Buckman-specific OroCommerce backend gotchas — real incidents this project hit that are
  NOT covered by the official oroinc/ai-dev-platform plugin's generic OroCommerce reference
  docs. For generic Oro/Symfony backend mechanics (entities, migrations, ACL, datagrids,
  API, workflows, message queue, bundle structure, etc.), use the official plugin's
  reference docs instead of this skill.

  Trigger scenarios:
  - Doctrine schema drift on entity-extend indexes/unique constraints
  - Serialized enum-extend field storage/filter/grid bugs (bare internal id vs full id)
---

# OroCommerce Backend Documentation Skill (Buckman-specific)

This skill used to be a near-complete mirror of Oro's own documentation (architecture,
bundles, entities, ACL, API, message queue, translations, setup, etc.). That generic
material duplicated the official `oroinc/ai-dev-platform` plugin's reference docs
(`orocommerce-development`, `orocommerce-foundation`, `orocommerce-discovery`), so it was
removed on 2026-09-10. What remains is only content tied to a real incident/gotcha
actually hit on this project.

---

## Available Documents

| Task Type | Document File | Key Content |
|-----------|---------------|--------------|
| **Doctrine schema drift on entity-extend indexes** | `references/entities/entity-extend-indexes.md` | Aaxis `MetadataListener` + `entity_extend.yml` fix for `DROP INDEX` drift on custom unique/regular indexes on entity-extend fields |
| **Serialized enum-extend field gotchas** | `references/entities/extend-entities.md` | Correct stored format (`<enum_code>.<internal_id>`), right choice-provider (`getEnumChoicesByCode` vs `getEnumInternalChoicesByCode`), datagrid pattern, and real pitfalls this project hit (filter "no results", `EntityNotFoundException`) |

For everything else — creating entities, bundles, ACL config, datagrids, API config,
workflows, message queue, bundle-less structure, translations, environment setup — use
the official plugin's docs (e.g. `orocommerce-development`'s `backend.md` and
`sql-safety.md`, `orocommerce-foundation`'s `override-points.md` and `ticket-layout.md`,
`orocommerce-discovery`'s `backend.md`/`architecture.md`) or Oro's own documentation.
Do not re-derive generic mechanics here.

---

## Usage Rules

1. Read the AGENT QUERY HINTS block at the top of a doc first to confirm it matches your task.
2. If your question isn't a schema-drift-on-entity-extend-index question or a
   serialized-enum-storage question, this skill has nothing for you — go to the official
   plugin's reference docs.
3. Only add new content here when it is a genuine incident/gotcha specific to this
   environment (a real bug, a real class name tied to that bug, a real ticket, a
   migration-ordering issue actually hit) — not generic "how Oro works" material.
