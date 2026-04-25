---
name: oro-jira-workflow
description: End-to-end workflow for implementing a JIRA ticket against an OroCommerce project — fetch ticket, analyze ACs, implement, manually test in Chrome (DevTools MCP), capture screenshots, generate a PDF test report, and write Behat coverage. Trigger when the user asks to "implement <JIRA-KEY>" or "cover all ACs by Behat" on this project.
---

# Oro JIRA Implementation Workflow

This skill encodes the standard "implement a JIRA ticket" loop on the Buckman / Oro project.

## Steps

1. **Fetch the ticket.** Use `mcp__atlassian__getJiraIssue` with `cloudId: aaxisdigital.atlassian.net` and the ticket key. Read description + Acceptance Criteria carefully.
2. **Map ACs to code.** Identify the smallest change that satisfies each AC. Datagrid changes usually live in `src/Buckman/Bundle/<Bundle>/Resources/config/oro/datagrids.yml`. Check Oro's vendor grid (`vendor/oro/.../datagrids.yml`) to understand inheritance (`extends:`) before editing.
3. **Implement the change.** Edit YAML / PHP / Twig in `src/Buckman/...` only (never `vendor/`, `node_modules/`, `public/bundles/`).
4. **Clear cache.**
   ```bash
   php bin/console cache:clear --env=prod
   ```
   For deeper invalidation: `php bin/console oro:cache:clear --env=prod`. Datagrid YAML lives in `var/cache/<env>/oro/datagrids/<grid-name>.php` — inspecting that file confirms whether config merged correctly.
5. **Manually test with Chrome DevTools MCP.** Admin URL: `https://local.aaxisdev.net/control-center/` — credentials `admin/admin` (per user). Navigate, log in, exercise the feature, take a screenshot at every meaningful state.
   - Save screenshots to `var/<TICKET>-test/` with numbered prefixes (`01-`, `02-`, ...).
   - On reload after YAML changes, also `Reset grid action` if the chip area looks stale.
   - **MANDATORY**: for every AC, capture a screenshot proving it works in the browser AFTER the change. "Compiled YAML contains the filter" is not proof — Oro extensions strip filters/sorters at runtime. If a filter doesn't appear in the chip bar, do **not** call AC1 PASS until you've actually applied the filter through the URL or chip and seen the record count change.
6. **Generate a PDF test report.** Build it with `fpdf2` (see `references/make_pdf.py`). Write the file to `/mnt/e/tmp/<TICKET>-test-report.pdf`. Cover page lists ACs vs. result; remaining pages embed the screenshots. Use ASCII-only text — the default Helvetica font does not support em-dash, bullets, or arrows.
   - **Keep it tight.** Aim for 3-5 screenshots total — one per AC plus a default-state shot. Multiple shots of the same screen with minor variations are noise. After capturing, delete duplicates before generating the PDF.
   - **Document known limitations on the cover page.** If the implementation has a deliberate trade-off (e.g., search hits default locale only, not user's current locale), call it out explicitly — do not let a known gap surface as a bug report later.
7. **Write Behat coverage.** One scenario per AC in `src/Buckman/Bundle/<Bundle>/Tests/Behat/Features/<feature>.feature`. Tag with `@buckman`. Login uses `Given I login as "admin" user` (admin password is `123abcABC` for Behat fixture; the live admin/admin only applies to manual testing). Prefer pre-existing OOTB step definitions from `vendor/oro/platform/.../GridContext.php`:
   - Sort: `When I sort grid by "Created At"` (toggles direction; append `again` for second click).
   - Order assertion: `Then Created At in 1 row must be lower then in 2 row`.
   - Filter: `When I filter Title as contains "Homepage"`.
   - Default-grid presence: `Then I should see "X" in grid` / `Then number of records should be N`.
8. **Run Behat (optional this loop).** `vendor/bin/behat --tags @buckman <feature>` from project root with `--config behat.yml.dist` if applicable. (Skip-isolators speed-up flags live in the `oro-behat-testing` skill.)
9. **Commit only when the user asks.** Default to staging the YAML + feature file together. Co-Author footer per project convention.

## Project conventions to remember

- Buckman admin URL: `https://local.aaxisdev.net/control-center/` (admin / admin manually; `123abcABC` for AdminLoginTrait in Behat).
- Datagrid title filter on `cms-page-grid` is registered server-side via the merged Oro config; the chip area only auto-renders filters that exist. If a chip doesn't appear, verify in `var/cache/prod/oro/datagrids/<grid>.php` first.
- Default-sort key `default: { updatedAt: DESC }` lives under `sorters:` (not under `columns:`).
- Localized columns (e.g., `title` on `Page`) inherit from `properties: { title: { type: localized_value, data_name: titles } }` in the base grid; never re-declare in the override.

## Footgun: LocalizedValueExtension strips your filter / sorter silently

`Oro\Bundle\LocaleBundle\Datagrid\Extension\LocalizedValueExtension::processConfigs()`
unconditionally **unsets** `filters[columns][X]` and `sorters[columns][X]` for every
`X` that appears as a `localized_value` property — whenever the current user has a
localization assigned (i.e., always, in the admin backend). This is why a
`title` filter on `cms-page-grid` is in the compiled YAML, but never renders
in the chip bar.

To filter / sort a localized field on a grid the user actually uses:

1. Choose a filter/sorter **key that does not collide** with the localized property name.
   E.g., `titleSearch` instead of `title`.
2. Add an explicit join to the localized values table in the grid's source query:
   ```yaml
   source:
     query:
       join:
         left:
           - { join: page.titles, alias: pageTitle }
   ```
3. Point `data_name` at the joined string column:
   ```yaml
   filters:
     columns:
       titleSearch:
         type: string
         data_name: pageTitle.string
         label: oro.cms.page.titles.singular_label
   ```
4. Keep `groupBy: page.id` in the source query so the LEFT JOIN against the
   `*_titles` table doesn't multiply rows.

The chip will then render with the label text, and Behat's
`When I filter Title as contains "X"` step matches the visible label, not the
internal filter key — so existing step definitions keep working.

## Generating the PDF report

`fpdf2`'s default Helvetica font is latin-1 only — em-dash, bullet, arrow,
and curly quotes will throw `FPDFUnicodeEncodingException`. Either pre-replace
those characters (`s/—/-/g`, `s/•/*/g`, `s/→/->/g`) or load a Unicode TTF font
with `pdf.add_font(...)`. The reference template in this skill uses ASCII to
keep things simple.

## References

- `references/make_pdf.py` — fpdf2 template that ingests numbered screenshots and outputs a single PDF report.
- `references/cheatsheet.md` — common Behat steps and their `data_name` requirements for sort/filter coverage.
