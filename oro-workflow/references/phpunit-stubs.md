# PHPUnit Stub Conventions

When unit-testing code that depends on an Oro entity or model, use a **stub** that
extends the real class. Stubs live alongside the test, not in production code.

## Locations

| Kind | Path | Pattern |
|------|------|---------|
| Entity stub | `Tests/Unit/Entity/<EntityName>Stub.php` | extends original entity |
| Model stub | `Tests/Unit/Model/<ModelName>Stub.php` | extends original model |

Both live in the **same bundle** as the class they stub.

## Why stubs, not mocks

Oro entities often have inherited getters/setters from extend fields. Mocking loses
those; stubs preserve them so tests exercise real behavior.

## Example

```php
// src/Foo/Bundle/BarBundle/Tests/Unit/Entity/ProductStub.php
namespace Foo\Bundle\BarBundle\Tests\Unit\Entity;

use Oro\Bundle\ProductBundle\Entity\Product;

class ProductStub extends Product
{
    // Expose extend-field setters that are only dynamically generated in prod
    public function setCustomAttribute(mixed $value): self
    {
        $this->customAttribute = $value;
        return $this;
    }
}
```

## Anti-patterns

- Putting stubs in `src/…/Stubs/` (production tree) — stubs are test-only.
- Creating stubs in a different bundle — breaks autoload ordering in CI.
- Using `createMock(Product::class)` when the test reads extend-field setters — those
  methods don't exist on the mock.
