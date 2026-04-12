# Writing Custom Context Classes

## Base Pattern

```php
<?php

namespace Acme\Bundle\MyBundle\Tests\Behat\Context;

use Behat\MinkExtension\Context\RawMinkContext;
use Doctrine\ORM\EntityManagerInterface;
use Oro\Bundle\TestFrameworkBundle\Behat\Context\AppKernelAwareInterface;
use Oro\Bundle\TestFrameworkBundle\Behat\Context\AppKernelAwareTrait;
use Oro\Bundle\TestFrameworkBundle\Behat\Element\OroPageObjectAware;
use Oro\Bundle\TestFrameworkBundle\Tests\Behat\Context\PageObjectDictionary;
use PHPUnit\Framework\Assert;

class MyContext extends RawMinkContext implements
    AppKernelAwareInterface,
    OroPageObjectAware
{
    use AppKernelAwareTrait;
    use PageObjectDictionary;

    /**
     * @Given product :sku has localization :formattingCode
     */
    public function productHasLocalization(string $sku, string $formattingCode): void
    {
        $em = $this->getEntityManager();
        $product = $em->getRepository(Product::class)->findOneBy(['sku' => $sku]);
        Assert::assertNotNull($product, sprintf('Product "%s" not found', $sku));

        $localization = $em->getRepository(Localization::class)->findOneBy([
            'formattingCode' => $formattingCode,
        ]);
        Assert::assertNotNull($localization, sprintf('Localization "%s" not found', $formattingCode));

        $product->addLocalization($localization);
        $em->flush();
    }

    private function getEntityManager(): EntityManagerInterface
    {
        return $this->getAppContainer()->get('doctrine.orm.entity_manager');
    }
}
```

## Step Definition Annotations

Use PHPDoc annotations with regex patterns:

```php
/**
 * @Given I visit the storefront page with locale :locale and path :path
 */
public function iVisitTheStorefrontPageWithLocaleAndPath(string $locale, string $path): void

/**
 * @Then the current URL should start with :prefix
 */
public function theCurrentUrlShouldStartWith(string $prefix): void

/**
 * @When I switch locale to :code via the localization switcher
 */
public function iSwitchLocaleViaTheSwitcher(string $code): void
```

### Parameter Types

| Pattern | Captures | Example |
|---------|----------|---------|
| `:param` | Quoted string | `"value"` |
| `"([^"]*)"` | Quoted regex | `"any text"` |
| `(\d+)` | Integer | `42` |
| `(.+)` | Any text | `some text` |

### Step Keywords

- `@Given` - Preconditions and setup
- `@When` - Actions
- `@Then` - Assertions and verification

In Gherkin, `And` / `But` inherit the keyword of the preceding step.

## Accessing Services

```php
// Get the Symfony container
$container = $this->getAppContainer();

// Get a service
$provider = $container->get('acme_locale.provider.localization_access');

// Get the entity manager
$em = $container->get('doctrine.orm.entity_manager');

// Run a Doctrine query
$result = $em->getRepository(Product::class)->findOneBy(['sku' => 'PROD-1']);
```

**Important:** Private services are not accessible by default. Expose them in
`Tests/Behat/parameters.yml` (see behat-yml.md).

## Browser Interactions (Mink Session)

```php
// Get the browser session
$session = $this->getSession();

// Visit a URL
$session->visit('https://example.com/page');

// Get current URL
$url = $session->getCurrentUrl();

// Wait for AJAX
$session->getDriver()->waitForAjax();

// Execute JavaScript
$session->executeScript("document.querySelector('.btn').click();");

// Evaluate JavaScript (returns value)
$result = $session->evaluateScript("return document.title;");

// Find element by CSS
$element = $session->getPage()->find('css', '.my-class');

// Find element by XPath
$element = $session->getPage()->find('xpath', '//div[@id="main"]');

// Get page HTML
$html = $session->getPage()->getContent();

// Check HTTP status
$statusCode = $session->getStatusCode();
```

## Using Elements from Context

```php
// Create a named element (defined in behat.yml)
$form = $this->elementFactory->createElement('Acme Localization Form');

// Check if element exists
if ($this->elementFactory->hasElement('My Widget')) { ... }

// Find element containing text
$element = $this->elementFactory->findElementContains('Grid Row', 'Product Name');
```

## Assertions

Use PHPUnit's Assert class:

```php
use PHPUnit\Framework\Assert;

Assert::assertNotNull($entity, 'Entity not found');
Assert::assertEquals('expected', $actual, 'Values do not match');
Assert::assertTrue($condition, 'Condition should be true');
Assert::assertStringContainsString('needle', $haystack);
Assert::assertCount(3, $collection);
Assert::assertEmpty($array);
```

## Shared Traits

Extract common step logic into traits:

```php
trait StorefrontNavigationTrait
{
    protected function visitStorefrontPage(string $locale, string $path): void
    {
        $baseUrl = $this->getStorefrontBaseUrl();
        $this->getSession()->visit($baseUrl . '/' . $locale . $path);
        $this->getSession()->getDriver()->waitForAjax();
    }
}
```

Use in multiple contexts:
```php
class LocaleUrlPrefixContext extends RawMinkContext implements AppKernelAwareInterface
{
    use AppKernelAwareTrait;
    use StorefrontNavigationTrait;
}
```

## Waiting and Polling

For elements that appear asynchronously:

```php
// Wait for AJAX (preferred)
$this->getSession()->getDriver()->waitForAjax();

// Wait for specific element
$this->spin(function () {
    return $this->getSession()->getPage()->find('css', '.loaded');
}, 'Element did not appear within timeout');

// Fixed sleep (avoid when possible)
sleep(2);
```

## Context Registration Checklist

1. Create the PHP class in `Tests/Behat/Context/`
2. Implement `AppKernelAwareInterface` and use `AppKernelAwareTrait`
3. Add step definitions with `@Given/@When/@Then` annotations
4. Register the context in `Tests/Behat/behat.yml` under `contexts:`
5. If using private services, expose them in `Tests/Behat/parameters.yml`
6. Clear behat_test cache: `cc --env=behat_test`
