# Cache Invalidation Strategy

Full `ccw` / `cc` take ~25–30 seconds because they rebuild the entire Symfony
container. Most edits only invalidate one subsystem. **Reach for the narrowest
invalidation that works.**

## Pick the narrowest clear

| Edited | Clear | How |
|--------|-------|-----|
| Twig template | twig cache only | `rm -rf /oroapp/var/cache/prod/twig` |
| Translation YAML (`messages.*.yml`) | translation DB + cache | `ctran` (DB load, not disk cache) |
| Datagrid YAML, routing, services, acls, api, config | container | full `ccw` (unavoidable) |
| SCSS / JS under Resources/public | asset build | `cab` / `cai --symlink`, or rely on `caw` watch |
| Entity mapping / migration | schema | `cup` (includes migration + warm + restart) |
| Frontend content only (layout updates, CSS tweaks already built) | browser hard reload | no backend clear needed |

## Principle

- After a batch of edits, run ONE clear at the end, not one per file.
- When multiple categories are edited, run the broadest needed — e.g. YAML + translation
  in same task: `ccw && ctran`.
- After schema changes: `cup` (skips `ccw`, includes it).
- When in doubt between `twig/` rm and `ccw`, try the targeted clear first — if the
  browser still shows stale output, escalate.

## Why full `ccw` exists

- `ccw` = `cstop && cw && cstart` — stops FPM/nginx, warms cache, restarts.
- Needed when compiled container state changes (DI tags, service definitions,
  acls, routing, datagrids, api.yml, navigation.yml).
- Twig templates are compiled but have their own cache subdir (`var/cache/prod/twig`)
  and don't require a full rebuild.

## Common mistakes

- Running `cc` / `ccw` after pure Twig edits → wastes 30s.
- Editing `messages.en.yml` and expecting the change without `ctran` → translations
  come from DB, not from the YAML file at runtime.
- Running `ccw` when `cup` is needed → container warms, but schema is still stale.
