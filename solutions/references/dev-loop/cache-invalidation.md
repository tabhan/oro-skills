# Cache invalidation strategy

Full `ccw` / `cc` take ~25-30s because they rebuild the whole Symfony container. Most edits invalidate one subsystem:
**reach for the narrowest invalidation that works.**

| Edited | Clear | How |
|--------|-------|-----|
| Twig template | twig cache only | `rm -rf /oroapp/var/cache/prod/twig` |
| Translation YAML (`messages.*.yml`) | translation DB + cache | `ctran` (translations load from DB, not from the YAML at runtime) |
| Datagrid YAML, routing, services, acls, api, navigation, config, DI tags (compiled container) | container | full `ccw` (= `cstop && cw && cstart`; unavoidable) |
| SCSS / JS under Resources/public | asset build | `cab` / `cai --symlink`, or rely on `caw` watch |
| Entity mapping / migration | schema | `cup` (includes migration, warm and restart, so not `ccw`: a container warm alone leaves the schema stale) |
| Frontend content only (layout updates, CSS tweaks already built) | browser hard reload | no backend clear |

- After a batch of edits run ONE clear at the end, not one per file; with several categories run the broadest needed
  (YAML + translation: `ccw && ctran`).
- When unsure between the `twig/` rm and `ccw`, try the targeted clear first; escalate if the browser still shows
  stale output. `cc` / `ccw` after pure Twig edits wastes 30s.
