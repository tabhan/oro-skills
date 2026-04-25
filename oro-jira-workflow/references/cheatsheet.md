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
