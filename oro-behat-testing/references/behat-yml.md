# behat.yml Configuration

## Location

Each bundle with Behat tests has its own `behat.yml` at:
```
src/Acme/Bundle/{BundleName}/Tests/Behat/behat.yml
```

Oro's `OroTestFrameworkExtension` auto-discovers all bundle `behat.yml` files.

## Suite Configuration

```yaml
oro_behat_extension:
    suites:
        AcmeLocaleBundle:                       # Suite name (convention: bundle name)
            contexts:                           # Step definition classes
                - Acme\Bundle\LocaleBundle\Tests\Behat\Context\LocaleUrlPrefixContext
                - Acme\Bundle\LocaleBundle\Tests\Behat\Context\LocalizationRestrictionContext
                - Oro\Bundle\TestFrameworkBundle\Tests\Behat\Context\OroMainContext
                - Oro\Bundle\TestFrameworkBundle\Tests\Behat\Context\ConsoleContext
                - Oro\Bundle\FormBundle\Tests\Behat\Context\FormContext
                - Oro\Bundle\DataGridBundle\Tests\Behat\Context\GridContext
            paths:
                - '@AcmeLocaleBundle/Tests/Behat/Features'
```

### Standard Oro Contexts to Include

Always include these unless you have a reason not to:

| Context | Provides |
|---------|----------|
| `OroMainContext` | Login, navigation, buttons, flash messages, assertions |
| `FormContext` | Form filling, saving, field operations |
| `GridContext` | Grid operations, filtering, sorting, inline editing |
| `ConsoleContext` | Symfony command execution |

### Cross-Bundle Context Sharing

Contexts from other bundles can be registered in your suite:
```yaml
contexts:
    - Acme\Bundle\LocaleBundle\Tests\Behat\Context\LocaleUrlPrefixContext
    # ^ Used by ProductBundle suite for storefront URL testing
```

## Elements Configuration

Elements define named form field mappings for use with `I fill "Element" with:` steps.

```yaml
oro_behat_extension:
    elements:
        Acme Localization Form:
            selector: 'form[name="oro_localization"]'
            class: Oro\Bundle\TestFrameworkBundle\Behat\Element\Form
            options:
                mapping:
                    URL Code: 'oro_localization[url_code]'
                    Visible on Storefront: 'oro_localization[visible_on_storefront]'
```

### Element Fields

| Field | Required | Description |
|-------|----------|-------------|
| `selector` | Yes | CSS selector or XPath locator |
| `class` | No | Element class (defaults to `Element`, use `Form` for form mapping) |
| `options.mapping` | No | Field label -> form field name mapping |

### Selector Formats

**CSS selector (default):**
```yaml
selector: 'form[name="oro_localization"]'
```

**XPath selector:**
```yaml
selector:
    type: 'xpath'
    locator: '//form[@name="oro_localization"]'
```

### When to Define Elements

Define elements when:
- You have custom form fields added via entity-extend or form extensions
- The form field names don't match their labels (e.g., `oro_localization[url_code]` for "URL Code")
- You want to use `I fill "Element Name" with:` table syntax

Do NOT define elements when:
- Oro's built-in form elements already handle it (e.g., `ProductForm`, `Localization Form`)
- Fields can be filled by label with `I fill in "Label" with "value"`

### Using Elements in Features

```gherkin
# Fill fields on a named element
And I fill "Acme Localization Form" with:
  | URL Code | test-001 |

# Assert element exists
Then I should see a "Acme Localization Form" element

# Assert element contains values
Then "Acme Localization Form" must contain values:
  | URL Code | test-001 |
```

### Oro Built-in Elements (Commonly Used)

These are already registered by Oro bundles - do NOT redefine:

| Element Name | Bundle | Description |
|-------------|--------|-------------|
| `ProductForm` | ProductBundle | Product edit form |
| `ProductForm Step One` | ProductBundle | Product creation wizard step 1 |
| `Localization Form` | LocaleBundle | Oro's localization form |
| `Grid` | DataGridBundle | Generic datagrid |

### Custom Element Classes

For advanced interactions beyond form filling, create a custom Element class:

```php
namespace Acme\Bundle\MyBundle\Tests\Behat\Element;

use Oro\Bundle\TestFrameworkBundle\Behat\Element\Element;

class MyWidget extends Element
{
    public function doSomething(): void
    {
        $this->find('css', '.widget-button')->click();
    }
}
```

Register it:
```yaml
elements:
    My Widget:
        selector: '.my-widget'
        class: Acme\Bundle\MyBundle\Tests\Behat\Element\MyWidget
```

Use in Context:
```php
$widget = $this->elementFactory->createElement('My Widget');
$widget->doSomething();
```

## Parameters Configuration

Expose private services for Behat test access:

```yaml
# Tests/Behat/parameters.yml
services:
    Acme\Bundle\LocaleBundle\Resolver\LocalePrefixResolver:
        alias: acme_locale.resolver.locale_prefix
        public: true
```

This makes the service accessible via `$this->getAppContainer()->get(...)` in contexts.
