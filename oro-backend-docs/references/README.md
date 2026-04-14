# OroCommerce Backend Knowledge Base

A structured knowledge base for AI agents working with OroCommerce backend development.

**Generated from:** https://doc.oroinc.com/backend/
**OroCommerce Version:** Master (Latest) | Enterprise 6.1 LTS
**Last Updated:** 2026-03-30

---

## Structure

| Directory | Contents |
|-----------|----------|
| `architecture/` | Application architecture, technology stack, bundle structure, **bundle-less structure (NEW in 7.0)** |
| `bundles/` | Creating bundles, extensions |
| `entities/` | Entity creation, configuration, extension, CRUD, datagrids |
| `entities-data-management/` | Workflows, operations, processes, data audit |
| `security/` | ACL, permissions, access control |
| `translation/` | Localization, translations |
| `integrations/` | Import/export, API-based integrations |
| `configuration-reference/` | YAML configs: services, routing, datagrids, ACLs, etc. See `bundle-config-files.md` for the complete annotated reference. |
| `api/` | REST API developer guide |
| `message-queue/` | Message queue, cron, websockets |
| `setup/` | Installation, environment setup |

---

## Usage by Agents

Each file in this knowledge base follows a consistent format:
- **Summary**: What this feature/concept does and why it exists
- **Configuration**: How to configure with annotated examples
- **Best Practices**: Recommended patterns
- **Common Pitfalls**: What to avoid
- **Examples**: Real-world usage patterns

---

## What's New in Oro 7.0

- **Bundle-less Structure**: Optional alternative to Symfony bundles for application-level code. See `architecture/bundle-less-structure.md`.
- **Enhanced Search Documentation**: New subsections for Query Builder, Elasticsearch Tuning, Fuzzy Search, Troubleshooting
- **PHP 8.4+ Compatibility**: Updated system requirements

---

## Related Resources

- [Oro Backend Documentation](https://doc.oroinc.com/master/backend/)
- [Oro Frontend Knowledge Base](../oro-knowledge-fronted-base/)
- [OroCommerce Release Notes](https://doc.oroinc.com/master/community/release-process/)
