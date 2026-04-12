# OroCommerce Behat Testing - Quick Start

## What It Is

OroCommerce uses Behat 3.x for behavior-driven functional tests. Tests run against a real
Symfony kernel with a browser (ChromeDriver/Selenium), hitting the actual database and UI.

## File Structure

```
src/Acme/Bundle/{BundleName}/Tests/Behat/
  behat.yml                          # Suite config: contexts, elements, paths
  parameters.yml                     # Optional: expose private services for tests
  ReferenceRepositoryInitializer.php # Optional: pre-load entity references
  Context/
    MyContext.php                     # Custom step definitions
  Features/
    my_feature.feature               # Gherkin feature files
    Fixtures/
      my_data.yml                    # Alice YAML fixture data
```

## Running Tests

```bash
# Run a specific suite (REQUIRED: use the behat alias with ORO_ENV=behat_test)
behat --suite=AcmeLocaleBundle

# Run a single feature file
behat --suite=AcmeLocaleBundle src/Acme/Bundle/LocaleBundle/Tests/Behat/Features/locale_url_prefix.feature

# Run a single scenario by line number
behat --suite=AcmeLocaleBundle src/.../locale_url_prefix.feature:10
```

## Key Concepts

- **Feature isolation**: Database/cache/kernel reset between FEATURES (not scenarios)
- **Scenario ordering**: Scenarios within a feature run top-to-bottom, sharing state
- **Elements**: YAML-defined form field mappings for `I fill "Element" with:` tables
- **Contexts**: PHP classes with step definitions (Given/When/Then)
- **Fixtures**: Alice YAML files loaded via `@fixture-BundleName:filename.yml` tags
- **Built-in steps**: Oro provides 300+ reusable steps via OroMainContext, FormContext, GridContext

## Oro Test Framework Base Classes

| Class | Purpose |
|-------|---------|
| `OroFeatureContext` | Base context with kernel access, element factory |
| `Element` | Base page element (CSS/XPath selectors) |
| `Form` | Element subclass for form field mapping |
| `Page` | Abstract page object with navigation |
| `OroElementFactory` | Creates/finds elements by name |

## Traits for Context Classes

| Trait | Provides |
|-------|----------|
| `AppKernelAwareTrait` | `getAppKernel()`, `getAppContainer()` for service access |
| `AssertTrait` | `assertTrue()`, `assertEquals()`, custom assertions |
| `SpinTrait` | `spin()` for polling/retry logic (flaky element waits) |
| `ScreenshotTrait` | `saveScreenshot()` for failure debugging |
| `PageObjectDictionary` | `createElement()`, `elementFactory` shortcuts |
| `FixtureLoaderDictionary` | Fixture loading shortcuts |

## Cache Clearing Before Tests

Always clear both caches before running tests after code changes:

```bash
ccw                        # Clear + warm prod cache
cc --env=behat_test        # Clear behat_test cache
```
