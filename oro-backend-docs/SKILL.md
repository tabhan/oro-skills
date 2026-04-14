---
name: oro-backend-docs
description: >
  When working on OroCommerce backend development (PHP, Doctrine, Symfony, configuration),
  you MUST use this skill to consult the local knowledge base documentation instead of
  relying on memory.
  
  Trigger scenarios:
  - Creating/modifying entities, Doctrine mappings, migrations
  - Writing services, configuring dependency injection, using Oro-specific tags
  - Configuring ACL, permissions, access levels, ownership types
  - Designing REST API, configuring api.yml, customizing processors
  - Implementing message queue, cron jobs, background tasks
  - Creating bundles OR using bundle-less structure (Oro 7.0+)
  - Configuring datagrids, navigation, system configuration
  - Handling import/export, integrations with external systems
  - Managing workflows, operations, processes
  - Understanding Oro-specific architecture patterns and best practices
  
  For any OroCommerce backend API, configuration, entity config, security model,
  or architecture patterns, read documentation first. DO NOT rely on generic Symfony knowledge.
---

# OroCommerce Backend Documentation Skill

Local OroCommerce backend development knowledge base index. When doing OroCommerce
backend development, **consult documentation first, then write code**.

---

## Available Documents (Task → Document Mapping)

| Task Type | Document File | Lines | Key Content |
|----------|--------------|------|-------------|
| **Project Overview** | `references/README.md` | - | Tech stack, structure, what's new in Oro 7.0 |
| **Architecture Overview** | `architecture/overview.md` | 461 | Tech stack, application structure, bundle-less (7.0+) |
| **Bundle-less Structure** | `architecture/bundle-less-structure.md` | 350+ | NEW in 7.0, migration from bundle-based |
| **Create Bundle** | `bundles/create-bundle.md` | 446 | Bundle creation, registration |
| **Create Entity** | `entities/create-entities.md` | 340 | Entity class creation, Doctrine mapping |
| **Configure Entity** | `entities/configure-entities.md` | 459 | Entity config, UI display, grid, form |
| **Extend Entity** | `entities/extend-entities.md` | 570 | Dynamic fields, extended entities |
| **CRUD + Routing** | `entities/crud-and-routing.md` | 753 | CRUD controller, routing configuration |
| **Datagrids** | `entities/datagrids.md` | 1131 | Backend grid configuration ⚠️ Extra-large |
| **Migrations** | `entities/migrations.md` | 466 | Database migrations |
| **Migration Patterns** | `entities/migration-patterns.md` | 160 | Installer vs versioned scripts, class naming, when to use each |
| **Entity Extend Indexes** | `entities/entity-extend-indexes.md` | 130 | Schema drift fix, unique constraints on extend fields |
| **Workflows** | `entities-data-management/workflows.md` | 936 | Workflow configuration |
| **Operations** | `entities-data-management/operations.md` | 629 | Button-triggered operations |
| **Processes** | `entities-data-management/processes.md` | 454 | Automated data processing |
| **ACL Overview** | `security/acl-overview.md` | 242 | Access levels, ownership types ✓ Small |
| **ACL Config** | `security/acl-configuration.md` | 590 | ACL YAML configuration |
| **Field ACL** | `security/permissions-and-field-acl.md` | 717 | Field-level permissions |
| **Services/DI** | `configuration-reference/services-yml.md` | 483 | Symfony DI + Oro-specific tags |
| **Navigation** | `configuration-reference/navigation-yml.md` | 360 | Menu/navigation configuration |
| **Datagrids YAML** | `configuration-reference/datagrids-yml.md` | 950 | Datagrid YAML definition |
| **ACLs YAML** | `configuration-reference/acls-yml.md` | 571 | Permission definitions |
| **API Overview** | `api/overview.md` | 323 | API architecture, JSON:API |
| **API Config** | `api/configuration.md` | 878 | api.yml configuration |
| **API Processors** | `api/processors-and-customization.md` | 1262 | Processor customization ⚠️ Extra-large |
| **Integration** | `integrations/oro-integration-bundle.md` | 539 | External system integration |
| **Import/Export** | `integrations/import-export.md` | 591 | Import/export configuration |
| **Message Queue** | `message-queue/message-queue.md` | 701 | MQ overview, topics, processors |
| **Cron** | `message-queue/cron.md` | 383 | Scheduled commands |
| **Translations** | `translation/translations.md` | 1363 | Multi-language support ⚠️ Extra-large |
| **Feature Toggle** | `setup/feature-toggle.md` | 530 | Feature switches |
| **Scopes** | `setup/scopes.md` | 472 | Context scoping |

---

## Usage Rules

### 1. Identify Task Type → Select Document

```
Task examples → Document mapping:

"Create a new entity"                    → entities/create-entities.md + entities/migrations.md + entities/migration-patterns.md
"Add fields to existing entity"          → entities/migration-patterns.md + entities/migrations.md
"Configure entity permissions"           → security/acl-configuration.md + security/acl-overview.md
"Configure backend grid"                 → entities/datagrids.md + configuration-reference/datagrids-yml.md
"Expose REST API for entity"             → api/configuration.md + api/overview.md
"Create a new bundle"                    → bundles/create-bundle.md + architecture/bundle-structure.md
"Use bundle-less structure (7.0+)"       → architecture/bundle-less-structure.md
"Register a service with Oro tags"       → configuration-reference/services-yml.md
"Configure workflow"                     → entities-data-management/workflows.md
"Set up import/export"                   → integrations/import-export.md
"Create message queue processor"         → message-queue/message-queue.md
"Add backend menu item"                  → configuration-reference/navigation-yml.md
"Understand BASIC_LEVEL vs LOCAL_LEVEL"  → security/acl-overview.md (✓ 242 lines, can read fully)
```

### 2. Read AGENT QUERY HINTS First (First 15 Lines)

**Every file starts with AGENT QUERY HINTS**, listing specific questions the file answers.

```typescript
read({ filePath: "references/entities/create-entities.md", limit: 15 })
```

Confirm if the file matches your question to avoid reading irrelevant content.

### 3. Read Documents (By Section, Avoid Full Loading)

**⚠️ For large documents (>300 lines), do NOT load the full file! Use offset + limit to read only relevant sections.**

```typescript
// CORRECT: Read specific section only
read({ 
  filePath: "references/entities/datagrids.md", 
  offset: 100,  // Start from specific section
  limit: 100    // Read 100 lines
})

// WRONG: Loading full 1131 lines (wastes context)
read({ filePath: "references/entities/datagrids.md" })  // ❌
```

**Small files that can be read fully:**
- `security/acl-overview.md` (242 lines)
- `api/overview.md` (323 lines)
- `entities/create-entities.md` (340 lines)

### 4. Implement Based on Documentation

**DO NOT rely on memory or generic Symfony knowledge.** You must:
- Verify configuration item names (Oro has many custom YAML keys)
- Confirm tag names (e.g., `oro_featuretoggle.feature`)
- Check access level values (BASIC_LEVEL, LOCAL_LEVEL, GLOBAL_LEVEL)
- Confirm processor group order

---

## ⚠️ Large File Reading Strategy

| Line Count | Recommended Approach |
|------------|---------------------|
| < 300 lines | Can read fully |
| 300-600 lines | Read first 100 lines for structure, then segment as needed |
| > 600 lines | **MUST segment**—read AGENT QUERY HINTS first, then specific sections |
| > 1000 lines | Read AGENT QUERY HINTS (first 15 lines), confirm match, then read specific sections |

### Extra-Large Files (> 1000 lines)

| File | Lines | Recommendation |
|------|-------|----------------|
| `entities-data-management/workflows-operations-processes.md` | 1367 | Segment read only |
| `translation/translations.md` | 1363 | Segment read only |
| `api/processors-and-customization.md` | 1262 | Segment read only |
| `api/developer-guide.md` | 1224 | Segment read only |
| `entities/datagrids.md` | 1131 | Segment read only |
| `configuration-reference/bundle-config-files.md` | 1097 | Segment read only |

---

## What's New in Oro 7.0

- **Bundle-less Structure**: Optional alternative to Symfony bundles for application-level code.
  See `architecture/bundle-less-structure.md` for directory layout and migration guide.
- **Enhanced Search**: Query Builder, Elasticsearch Tuning, Fuzzy Search, Troubleshooting
- **PHP 8.4+ Compatibility**: Updated system requirements

---

## Trigger Scenario Examples

The following scenarios **MUST** consult documentation first:

### Entity Related
```
"Create a new ProductReview entity"
→ Read entities/create-entities.md (first read limit=15 to check match)
→ Then read entities/migrations.md

"Configure entity display in backend grid"
→ Read entities/datagrids.md (⚠️ 1131 lines, segment read)
→ Read configuration-reference/datagrids-yml.md (⚠️ 950 lines, segment read)

"Make entity support dynamic extension fields"
→ Read entities/extend-entities.md
```

### ACL/Permission Related
```
"Configure entity's VIEW/EDIT permissions"
→ Read security/acl-configuration.md
→ Read security/acl-overview.md (✓ 242 lines, can read fully)

"Understand BASIC_LEVEL vs LOCAL_LEVEL"
→ Read security/acl-overview.md (✓ 242 lines, can read fully)
```

### API Related
```
"Expose REST API for entity"
→ Read api/configuration.md (⚠️ 878 lines, first read limit=15)
→ Read api/overview.md (323 lines, can read fully)

"Customize API response processor"
→ Read api/processors-and-customization.md (⚠️ 1262 lines, segment read)
```

### Bundle/Architecture Related
```
"Create a new BridgeXxxBundle"
→ Read bundles/create-bundle.md
→ Read architecture/bundle-structure.md (619 lines, segment read)

"Use bundle-less structure for new feature"
→ Read architecture/bundle-less-structure.md (NEW in 7.0)

"Add backend menu item"
→ Read configuration-reference/navigation-yml.md (360 lines, can read fully)

"Configure feature toggle"
→ Read setup/feature-toggle.md
→ Read configuration-reference/services-yml.md (read tag section)
```

---

## Key Differences from Generic Symfony Knowledge

**MUST consult Oro documentation to confirm:**

| Domain | Generic Symfony | OroCommerce Specific |
|--------|----------------|----------------------|
| Service tags | `kernel.event_listener` | `oro_featuretoggle.feature`, `oro_datagrid.extension`, etc. |
| ACL | binary yes/no | multi-level (BASIC/LOCAL/GLOBAL) + ownership type |
| Entity config | Doctrine annotations | `entity.yml` + `EntityConfigInterface` |
| Datagrid | hand-coded tables | YAML-driven + extensions + actions |
| API | hand-coded endpoints | auto-generated from `api.yml` + processor chain |
| Routing | `routing.yml` | `routing.yml` + `oro_route` entity config |
| Workflow | none | WorkflowBundle + Operation + Process |
| Import/Export | none | `importexport.yml` + strategy/processor |
| Architecture | bundles only | bundles OR bundle-less (7.0+) |

**When encountering these domains, consult Oro documentation. DO NOT infer from Symfony generic knowledge.**

---

## Documentation Source

Generated from: https://doc.oroinc.com/master/backend/
OroCommerce Version: Master (Latest) | Enterprise 6.1 LTS

---

## Quick Consultation Workflow

```
1. Check task keywords → Locate document from table above
2. read({ filePath: "references/xxx.md", limit: 15 }) → Read AGENT QUERY HINTS
3. Confirm match → Segment-read specific section (use offset + limit for large files)
4. Implement based on documentation → Do not rely on memory
```