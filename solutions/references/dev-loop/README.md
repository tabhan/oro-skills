# OroCommerce Dev-Loop Conventions

This is about the development loop — caches, aliases, service wiring. For Oro's
**workflow engine** (state machines, transitions, publication lanes) see [../decision-tables.md](../decision-tables.md).

Complements the entity, e2e and dialog-form references
(APIs/configuration) with day-to-day dev-loop conventions accumulated across multiple
OroCommerce projects.

## Available References

| Topic | File | When to consult |
|-------|------|-----------------|
| **Shell aliases** | `aliases.md` | Before invoking `c`, `cc`, `ccw`, `ctran`, `cup`, `cab`, `cai`, `caw`, etc. |
| **Cache invalidation** | `cache-invalidation.md` | After editing Twig / YAML / SCSS / entities — pick the narrowest clear |
| **Service overrides** | `service-overrides.md` | Overriding an OOTB Oro service method (aspect interceptor) or extending a repository |
| **System config groups** | `system-config-groups.md` | Adding `*_cron_definition` or shared system-config fields |

## Usage Rules

1. **Read before doing.** Open the matching reference file before acting on a trigger above.
2. **Use aliases, don't guess commands.** `c` is `time php /oroapp/bin/console`; never
   type the full path when the alias exists.
3. **Cache-clear surgically.** Full `ccw` takes ~30s. For Twig edits, delete
   `/oroapp/var/cache/prod/twig/` only. See `cache-invalidation.md`.
4. **Never use `autowire: true`.** Always declare arguments explicitly in services.yml.
5. **Repositories live in their own class.** Never inline DQL/QueryBuilder in services,
   listeners, or commands. See `service-overrides.md`.
6. **Atlas first, even for investigation.** Before reading `vendor/` to see how Oro wires
   something, run `aaxis-oro atlas <event|tag|service|grid|...> <term>` (see the atlas skill).

## After switching branch or pulling

Run `aaxis-oro dev refresh` (`--dry-run` to preview): it maps the changed files to composer, cache, migration, entity,
translation, routes-dump and asset steps for both stacks and `aaxis-oro test` refuses a stale tree. See `env/README.md`.
