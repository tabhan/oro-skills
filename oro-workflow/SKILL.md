---
name: oro-workflow
description: >
  OroCommerce dev-loop conventions: shell aliases, cache invalidation strategy, migration
  naming, service override patterns (interceptor, repository), PHPUnit stub conventions,
  and system-config grouping rules. Project-tested guidance that complements the official
  OroCommerce docs with practical, cross-project patterns.

  Trigger scenarios:
  - Clearing Symfony cache, rebuilding assets, reloading translations, loading migrations
  - Writing a new migration class (naming conventions)
  - Overriding or extending an OOTB Oro service / repository
  - Writing PHPUnit unit tests for entities/models in an Oro bundle
  - Adding a *_cron_definition system-config field
  - Declaring services.yml (autowire policy, argument declarations)

  For any of these, read the relevant reference FIRST — don't guess command names or
  naming patterns.
---

# OroCommerce Workflow Conventions

Project-tested dev-loop conventions accumulated across multiple OroCommerce projects.
The official docs (`oro-backend-docs`, `oro-frontend-skills`, `oro-behat-testing`,
`oro-dialog-forms`) cover APIs and configuration; this skill covers how work actually
gets done day-to-day.

## Available References

| Topic | File | When to consult |
|-------|------|-----------------|
| **Shell aliases** | `references/aliases.md` | Before invoking `c`, `cc`, `ccw`, `ctran`, `cup`, `cab`, `cai`, `caw`, etc. |
| **Cache invalidation** | `references/cache-invalidation.md` | After editing Twig / YAML / SCSS / entities — pick the narrowest clear |
| **Migration naming** | `references/migration-naming.md` | Creating a new migration file |
| **Service overrides** | `references/service-overrides.md` | Extending an OOTB Oro service, repository, or decorator |
| **PHPUnit stubs** | `references/phpunit-stubs.md` | Stubbing Oro entities/models in unit tests |
| **System config groups** | `references/system-config-groups.md` | Adding `*_cron_definition` or shared system-config fields |

## Usage Rules

1. **Read before doing.** When starting a task that matches a trigger above, open the
   matching reference file first.
2. **Use aliases, don't guess commands.** `c` is `time php /oroapp/bin/console`; never
   type the full path when the alias exists.
3. **Cache-clear surgically.** Full `ccw` takes ~30s. For Twig edits, delete
   `/oroapp/var/cache/prod/twig/` only. See `cache-invalidation.md`.
4. **Never use `autowire: true`.** Always declare arguments explicitly in services.yml.
5. **Repositories live in their own class.** Never inline DQL/QueryBuilder in services,
   listeners, or commands. See `service-overrides.md`.
