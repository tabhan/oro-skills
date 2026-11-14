# Changelog

## 0.27.2

- `dev refresh`: a `Migrations/` change now also runs `oro:migration:data:load` (new `data-load` step, prod kernel) and reports the fixtures it loaded; `migrate` alone is schema only.
- `env check` / `env repair --only media`: new `sitemap-shadow` item. With a remote public gaufrette adapter, stale files under `public/media/sitemaps/` are served by nginx instead of the generated GridFS sitemap; repair moves them to `moved-aside/`.
- `aaxis-oro test` guard: an empty `database_dsn` from a kernel booted right after a cache clear is retried once, and `live-target.php` falls back to the live connection's parameters instead of reporting an empty DSN.
