# Feature Files Guide

## Basic Structure

```gherkin
@acme
@fixture-BundleName:fixture_file.yml
Feature: Short feature title
  In order to [business value]
  As a [role]
  I should [expected capability]

  Background:
    Given I login as administrator
    And I go to System/Localization/Localizations

  Scenario: Descriptive scenario name
    When I click "Create Localization"
    Then I should see "Region"

  Scenario Outline: Parameterized scenario with Examples
    Given I visit the storefront page with locale "<locale>" and path "/"
    Then the current URL should start with "/<locale>/"

    Examples:
      | locale |
      | us-en  |
      | ca-fr  |
```

## Tags

### Required Tags
- `@acme` - Applied to all custom feature files for suite filtering

### Fixture Tags
Load Alice YAML data before the feature runs:
```gherkin
@fixture-AcmeProductBundle:product_visibility.yml
```

Format: `@fixture-{BundleName}:{filename}.yml`

Multiple fixtures can be stacked:
```gherkin
@fixture-AcmeProductBundle:products.yml
@fixture-AcmeOrganizationBundle:business_units.yml
Feature: ...
```

### Other Useful Tags
- `@not-automated` - Skip scenario (not yet implemented)
- `@wip` - Work in progress
- `@skip` - Skip execution

## Background Section

Runs before EVERY scenario in the feature. Use for shared setup.

**When to use:**
- Login steps repeated across all scenarios
- Navigation to a common page
- Common data setup needed by every scenario

**When NOT to use:**
- Setup only needed by some scenarios (put in the scenario itself)
- Data setup that changes between scenarios (use fixture or inline steps)

```gherkin
Background:
  Given I login as administrator
  And I go to System/Localization/Localizations
```

**Important:** Background runs for EVERY scenario including Scenario Outline rows.
The Oro test framework does NOT reset sessions between scenarios within a feature.

## Scenario Outline with Examples

Parameterize scenarios to avoid duplication. Use `<placeholder>` in steps,
define values in the Examples table.

```gherkin
Scenario Outline: Locale-restricted user sees matching and global products
  Given I login as "<user>" user
  And I go to Products/ Products
  And I open the all-products grid view
  Then I should see "<visible>" in grid
  And I should see "Global Product" in grid
  And there is no "<hidden>" in grid

  Examples:
    | user        | visible          | hidden          |
    | vis_user_es | Spanish Product  | French Product  |
    | vis_user_fr | French Product   | Spanish Product |
```

**When to use:**
- Two or more scenarios with identical steps but different data
- Testing the same flow for different users, locales, or entities
- Verifying symmetrical behavior (e.g., EN->FR and FR->EN locale switching)

**Tips:**
- Keep column count manageable (3-5 columns max)
- Use descriptive column names
- Each Examples row becomes a separate scenario execution
- If a scenario has unique setup steps, keep it standalone

## Data Tables in Steps

Pass structured data to steps:

```gherkin
When I fill "Localization Form" with:
  | Name       | Test Localization     |
  | Title      | Test                  |
  | Language   | English               |
  | Formatting | English (United States) |
```

The table is received as a `TableNode` in the step definition.

## Multi-line Text (PyStrings)

```gherkin
Given a CSV file at "var/data/types.csv" with content:
  """
  slug,localization,type
  industries,,industry
  resources,,resource
  """
```

## Scenario Ordering and Dependencies

Scenarios within a feature execute top-to-bottom and share database state.
This is by design in Oro's test isolation model.

**Common pattern:** Setup scenario first, then test scenarios:
```gherkin
Scenario: Set up entity associations
  Given product "PROD-1" has localization "es_ES"
  And business unit "BU-ES" has localization "es_ES"

Scenario: User sees filtered products
  Given I login as "user_es" user
  ...
```

**Warning:** If a setup scenario fails, all subsequent scenarios in the feature
will likely fail too (cascading failures). The database is only restored
between features, not between scenarios.

## Feature File Naming

- Use snake_case: `product_visibility.feature`, `locale_url_prefix.feature`
- Name should describe the feature being tested, not the ticket number
- Group related tests in a single feature file when they share fixtures

## Comments

```gherkin
# AC1: Autocomplete search handler excludes language-only localizations
Scenario: Assignable localization search handler returns only valid localizations
```

Use comments to link scenarios to acceptance criteria or ticket numbers.
