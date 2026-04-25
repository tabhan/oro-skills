# Behat / Oro grid cheat sheet

## Sorting (AC for "sortable column")
- `When I sort grid by "Created At"` — clicks header (first time = ASC).
- `When I sort grid by "Created At" again` — second click (DESC).
- Order assertion: `Then Created At in 1 row must be lower then in 2 row` / `greater then`.

## Filtering by string column (AC for "search by X")
- `When I filter Title as contains "Homepage"` — finds the chip-style filter and applies a contains filter.
- After filtering: `Then I should see "Homepage" in grid` and `And number of records should be 1`.

## Date range filter
- `When I filter Created At as between "2026-03-01" and "2026-03-31"`.

## CRITICAL: localized_value filters are stripped at runtime

`LocalizedValueExtension` removes any `filters[columns][X]` and
`sorters[columns][X]` whose key matches a `localized_value` property name
(e.g. `title` on `cms-page-grid`). Use a different filter key + explicit join:

```yaml
source:
  query:
    join:
      left:
        # Default fallback title only - matches what the Title column displays.
        # Without this WHERE clause, search hits localized titles that the user
        # never sees in the column (false positives, looks like a bug).
        - join: page.titles
          alias: pageTitle
          conditionType: WITH
          condition: 'pageTitle.localization IS NULL'
    groupBy: page.id           # prevents row multiplication across locales
filters:
  columns:
    titleSearch:               # NOT "title" - that key is stripped
      type: string
      data_name: pageTitle.string
      label: oro.cms.page.titles.singular_label
```

## When to denormalize instead

For grids over entities with millions of rows, mirror what `Product` does:
add a `denormalizedDefaultName` scalar column kept in sync by an entity
listener, then filter/sort directly on it (no join, no GROUP BY tricks).
See `vendor/oro/commerce/.../ProductBundle/Resources/config/oro/datagrids.yml`
for the canonical example.

Behat's `I filter Title as contains "X"` matches the visible label, so the
internal filter key does not affect the test.

## Required YAML to make these pass
```yaml
columns:
    createdAt:
        label: oro.ui.created_at
        frontend_type: datetime
sorters:
    columns:
        createdAt:
            data_name: page.createdAt   # data_name MUST be a real DQL alias.field
    default:
        updatedAt: DESC                  # default sort goes here, not under columns
filters:
    columns:
        title:
            type: string
            data_name: title             # `title` is resolved via localized_value extension
        createdAt:
            type: datetime
            data_name: page.createdAt
```

## Cache-clear order when changing datagrids.yml
1. `php bin/console cache:clear --env=prod`
2. If still stale: `php bin/console oro:cache:clear --env=prod`
3. Inspect compiled config: `cat var/cache/prod/oro/datagrids/<grid-name>.php`
4. In the browser, click `Reset grid action` to discard the user's saved view.

## Login steps
- Behat: `Given I login as "admin" user` (uses `AdminLoginTrait`).
- Manual / Chrome MCP: navigate to `/control-center/`, fill `admin` / `admin`.
