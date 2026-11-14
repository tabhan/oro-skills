# Changelog

## 0.27.3

- Token/time economy, no behaviour change to any gate: atlas staleness check walks `src/`+`config/` with `scandir` (about 2.3x faster; it runs in the SessionStart, Edit/Write and Bash hooks), `atlas` queries skip the backslash regex for plain strings, the PostToolUse Bash hook skips its post-hoc `git diff` scan for command lines made only of read-only tools, SubagentStart no longer injects the atlas reminder into this plugin's own agents, and the atlas and ticket-process prompt reminders are shorter (the process one no longer repeats the Ticket process block).

## 0.27.2

- `dev refresh`: a `Migrations/` change now also runs `oro:migration:data:load` (new `data-load` step, prod kernel) and reports the fixtures it loaded; `migrate` alone is schema only.
- `env check` / `env repair --only media`: new `sitemap-shadow` item. With a remote public gaufrette adapter, stale files under `public/media/sitemaps/` are served by nginx instead of the generated GridFS sitemap; repair moves them to `moved-aside/`.
- `aaxis-oro test` guard: an empty `database_dsn` from a kernel booted right after a cache clear is retried once, and `live-target.php` falls back to the live connection's parameters instead of reporting an empty DSN.
