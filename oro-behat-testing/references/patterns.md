# Testing Patterns, Tips, and Debugging

## Test Isolation Model

### Feature-Level Isolation
- Database is **snapshotted before** and **restored after** each FEATURE file
- Elasticsearch indices are snapshotted and restored
- Cache directories are dumped and restored
- Kernel is rebooted between features

### Scenario-Level Sharing
- Scenarios within a feature share database state (no reset between scenarios)
- Sessions persist between scenarios (login carries over)
- This means scenario ORDER MATTERS within a feature

### Implications
- Setup data in the first scenario is available to all subsequent scenarios
- If scenario 2 depends on scenario 1's data, they must be in the same feature
- A failing scenario can cascade failures to all following scenarios
- Fixtures loaded via `@fixture` tags are loaded once per feature

## Common Patterns

### Setup-Then-Test Pattern
```gherkin
Scenario: Set up entity associations
  Given product "PROD-1" has localization "es_ES"
  And business unit "BU-ES" has localization "es_ES"

Scenario: User sees filtered data
  Given I login as "user_es" user
  Then I should see "Product" in grid
```

### Publish-Reindex-Test Pattern (for storefront tests)
```gherkin
Scenario: Publish and reindex products
  Given product "PROD-1" is published
  And I run Symfony "oro:website-search:reindex" command

Scenario: Storefront shows published products
  Given I visit the storefront page with locale "us-en" and path "product/"
  Then the storefront page should contain "Product Name"
```

### Background for Repeated Login
```gherkin
Background:
  Given I login as administrator
  And I go to System/Localization/Localizations

Scenario: View form
  When I click "Create Localization"
  Then I should see "Region"
```

### Scenario Outline for Parameterized Tests
```gherkin
Scenario Outline: Locale switcher works in both directions
  Given I visit the storefront page with locale "<from>" and path "/"
  When I switch locale to "<to_code>" via the localization switcher
  Then the current URL should start with "/<to_prefix>/"

  Examples:
    | from  | to_code | to_prefix |
    | us-en | fr_CA   | ca-fr     |
    | ca-fr | en_US   | us-en     |
```

## Anti-Patterns to Avoid

### 1. Debug Screenshots as Test Steps
```gherkin
# BAD - no assertion value, slows tests
Then I take screenshot

# GOOD - only use when actively debugging
# Remove before committing
```

### 2. Hardcoded Waits
```gherkin
# BAD
When I wait for 5 seconds

# GOOD - wait for specific condition
When I wait for "Grid" element to appear
```

In custom step definitions that navigate to a page with async-loaded content
(product grids, datagrids, widgets), **use Oro's `waitForAjax()` driver method**
instead of hand-rolled `$session->wait(...)` polling on CSS selectors or body text.

```php
// BAD - brittle CSS polling, may return before grid populates
$this->getSession()->wait(
    5000,
    "document.readyState === 'complete'"
    . " && !document.querySelector('.loading-mask')"
);

// GOOD - Oro's canonical wait: covers readyState, loader masks,
// jQuery.active, mediator isInAction, isRequestPending, etc.
$this->getSession()->getDriver()->waitForAjax();
```

`waitForAjax()` is defined on `OroSelenium2Driver` (see
`vendor/oro/platform/src/Oro/Bundle/TestFrameworkBundle/Behat/Driver/OroSelenium2Driver.php`)
and is the same check Oro's built-in steps use after clicks and navigation.
Reuse it whenever you write a custom "visit page" step.

#### Full page-ready check: `waitPageToLoad()` + `waitForAjax()`

For full-page navigation (not just an in-place XHR), `waitForAjax()` alone can
return early — the previous page's `readyState` may already be `complete`
before the new document has started. The robust pattern is to chain **both**:

```php
$driver = $this->getSession()->getDriver();
$driver->waitPageToLoad();   // readyState, title, .loading, .loader-mask.shown, .lazy-loading
$driver->waitForAjax();      // outstanding XHRs / in-flight renders
```

`waitPageToLoad()` and `waitForAjax()` both live on `OroSelenium2Driver`. Use
this combined call after `visitPath()` and before asserting on text content
rendered by PLP/search/widgets. Do **not** substitute `sleep()` or fixed
`$session->wait(N, ...)` timeouts — those are flaky and wasteful.

For storefront-specific assertions, prefer the shared helpers in
`Aaxis\Bundle\TestBundle\Tests\Behat\Context\StorefrontPageLoadTrait` and
`StorefrontAssertTrait` (the trait's `Then the storefront page should [not] contain`
steps already apply this wait before spinning on the text).

### 3. Duplicate Scenarios Instead of Outlines
```gherkin
# BAD - duplicated scenarios
Scenario: English page works
  Given I visit locale "us-en"
  Then URL starts with "/us-en/"

Scenario: French page works
  Given I visit locale "ca-fr"
  Then URL starts with "/ca-fr/"

# GOOD - use Scenario Outline
Scenario Outline: Localized pages work
  Given I visit locale "<locale>"
  Then URL starts with "/<locale>/"

  Examples:
    | locale |
    | us-en  |
    | ca-fr  |
```

### 4. Repeated Login Without Background
```gherkin
# BAD - login repeated in every scenario
Scenario: Test 1
  Given I login as administrator
  ...
Scenario: Test 2
  Given I login as administrator
  ...

# GOOD - extract to Background
Background:
  Given I login as administrator
```

### 5. Testing Implementation Details
```gherkin
# BAD - testing CSS selectors
Then I should see element "div.grid-container > table > tr:first-child"

# GOOD - testing user-visible behavior
Then I should see "Product Name" in grid
```

## Debugging Failed Tests

### 1. Check Screenshots
Failed scenarios automatically save screenshots to the configured artifacts directory.

### 2. Check Assertion Messages
The error message tells you what failed:
```
Table has no record with "Product Name" content
Failed asserting that null is not null.
```

### 3. Common Failure Causes

| Error | Likely Cause |
|-------|-------------|
| `Localization "xx_XX" not found` | Wrong formatting_code; check DB with `doctrine:query:sql` |
| `Table has no record with "X"` | Grid visibility filter, wrong grid view, or data not created |
| `Button "X" not found` | Page not loaded, wrong navigation path, or permissions |
| `Flash message "X" not found` | Form validation failed, check for validation errors |
| `Element "X" not found` | Element not defined in behat.yml, or wrong selector |
| `Step "X" is not defined` | Context class not registered in behat.yml |

### 4. Verify Database State
```bash
php /oroapp/bin/console doctrine:query:sql \
  "SELECT id, name, formatting_code, url_code FROM oro_localization" \
  --env=behat_test
```

### 5. Cache Issues
Always clear both caches after code changes:
```bash
ccw                     # Clear + warm prod cache
cc --env=behat_test     # Clear behat_test cache
```

### 6. Run Single Scenario
```bash
behat --suite=AcmeProductBundle path/to/feature.feature:42
# Line 42 = the scenario line number
```

## OroCommerce Conventions

### Localization Codes
- Always use `formattingCode` (e.g., `es_ES`, `fr_CA`) for entity lookups
- URL prefixes come from the `url_code` column (e.g., `latam-es`, `ca-fr`, `us-en`)
- These are NOT the same: `es_ES` (formatting) vs `latam-es` (URL prefix)
- Language-only codes (e.g., `en`, `fr`) are parent localizations for fallback only

### Entity-Extend Fields
Entity-extend fields stored in `serialized_data` (JSONB column) cannot be set via
Alice fixtures and require custom step definitions using Doctrine directly.

### Admin Login
Use `I login as administrator` for the default admin user.
For custom users, use `I login as "username" user`.

### Grid Views
The default products grid may have filters applied. Consider creating a custom step
to open an unfiltered grid view when testing product visibility.
