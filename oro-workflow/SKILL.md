---
name: oro-workflow
description: >
  OroCommerce DEV-LOOP conventions — not Oro's workflow engine: shell aliases, cache
  invalidation strategy, service override patterns (aspect interceptor, repository), and
  system-config grouping rules. Project-tested guidance that complements the official
  OroCommerce docs with practical, cross-project patterns.

  Trigger scenarios:
  - Clearing Symfony cache, rebuilding assets, reloading translations, loading migrations
  - Overriding or extending an OOTB Oro service / repository
  - Adding a *_cron_definition system-config field
  - Declaring services.yml (autowire policy, argument declarations)

  For any of these, read the relevant reference FIRST — don't guess command names or
  naming patterns.
---

# OroCommerce Dev-Loop Conventions

This is about the development loop — caches, aliases, service wiring. For Oro's
**workflow engine** (state machines, transitions, publication lanes) see `oro-conventions`.

Complements `oro-backend-docs`, `oro-e2e-testing`, and `oro-dialog-forms`
(APIs/configuration) with day-to-day dev-loop conventions accumulated across multiple
OroCommerce projects.

## Available References

| Topic | File | When to consult |
|-------|------|-----------------|
| **Shell aliases** | `references/aliases.md` | Before invoking `c`, `cc`, `ccw`, `ctran`, `cup`, `cab`, `cai`, `caw`, etc. |
| **Cache invalidation** | `references/cache-invalidation.md` | After editing Twig / YAML / SCSS / entities — pick the narrowest clear |
| **Service overrides** | `references/service-overrides.md` | Overriding an OOTB Oro service method (aspect interceptor) or extending a repository |
| **System config groups** | `references/system-config-groups.md` | Adding `*_cron_definition` or shared system-config fields |

## Usage Rules

1. **Read before doing.** Open the matching reference file before acting on a trigger above.
2. **Use aliases, don't guess commands.** `c` is `time php /oroapp/bin/console`; never
   type the full path when the alias exists.
3. **Cache-clear surgically.** Full `ccw` takes ~30s. For Twig edits, delete
   `/oroapp/var/cache/prod/twig/` only. See `cache-invalidation.md`.
4. **Never use `autowire: true`.** Always declare arguments explicitly in services.yml.
5. **Repositories live in their own class.** Never inline DQL/QueryBuilder in services,
   listeners, or commands. See `service-overrides.md`.
