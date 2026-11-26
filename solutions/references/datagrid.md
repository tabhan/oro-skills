# Custom datagrid and report grid pitfalls

Unit tests pass while the live grid is broken; check these:

- **Rebuild the right cache.** `datagrids.yml` compiles into `var/cache/<env>/oro/datagrids/<grid>.php`; the web app
  serves **prod**, so run `bin/console cache:clear --env=prod` or the OLD grid shows. Test-only console commands need
  the **test** cache. A stale `var/cache/tes_` can keep the old command set even after `cache:clear --env=test`:
  `rm -rf var/cache/test var/cache/tes_` then `cache:warmup --env=test`.
- **`apply_callback`** (a `sorters:` node only, not columns or filters) must be the array form
  `['@service_id', 'method']`. The string form `'@service->method'` is eager-resolved by `SystemAwareResolver` at
  config-compile time (called with the grid *name*) -> `TypeError`/500.
- **Never `GROUP BY` a `json` column** (Postgres 42883 "no equality operator for type json"). The pager COUNT query
  inherits the SELECT, so the count 500s and the grid shows 0 rows. For to-one joins, bind the scalar directly.
- **The grid TOOLBAR is a sibling of `.grid-container`, not a child.** Filters (`toggle-filters-action` `fa-filter`
  button), sorters, pagination `.totals-label` and the CSV export launcher live in `.grid-toolbar`; selectors scoped
  under `.grid-container` miss them. Read grid metadata from the raw server HTML (`fetch(location.href)`), not the
  live DOM: Oro consumes `data-page-component-*` attrs after init.
- **Serialized enum** columns/filters: copy `oro_product.inventory_status` (full-id storage, `frontend_type: select`
  + `getEnumChoicesByCode`, `type: enum` filter with `enum_code`); see
  [entities/extend-entities.md](entities/extend-entities.md).
