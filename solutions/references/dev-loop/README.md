# OroCommerce dev-loop conventions

Caches, aliases, service wiring. For Oro's **workflow engine** see [../decision-tables.md](../decision-tables.md).
Open the matching file before acting on a trigger.

| Topic | File | When to consult |
|-------|------|-----------------|
| Shell aliases | `aliases.md` | Before invoking `c`, `cc`, `ccw`, `ctran`, `cup`, `cab`, `cai`, `caw`, etc. (`c` is `time php /oroapp/bin/console`; never type the full path) |
| Cache invalidation | `cache-invalidation.md` | After editing Twig / YAML / SCSS / entities: pick the narrowest clear (full `ccw` ~30s; Twig edits need only `/oroapp/var/cache/prod/twig/`) |
| Service overrides | `service-overrides.md` | `autowire: true` ban, `@doctrine` injection, repositories (never inline DQL/QueryBuilder in services, listeners, commands) |
| System config groups | `system-config-groups.md` | Adding `*_cron_definition` or shared system-config fields |

Overriding an Oro service method: [../override-core-service.md](../override-core-service.md). Atlas first, even for
investigation, before reading `vendor/`: `aaxis-oro atlas <event|tag|service|grid|...> <term>` (atlas skill).

## After switching branch or pulling

Run `aaxis-oro dev refresh` (`--dry-run` to preview): it maps the changed files to composer, cache, migration,
entity, translation, routes-dump and asset steps for both stacks, and `aaxis-oro test` refuses a stale tree. See `env/README.md`.
