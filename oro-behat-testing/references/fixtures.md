# Fixtures and Test Data

## Alice YAML Fixtures

Fixtures use the Alice library to define test data in YAML format.

### Location
```
src/Acme/Bundle/{BundleName}/Tests/Behat/Features/Fixtures/{name}.yml
```

### Loading Fixtures

Add a fixture tag to the feature file:
```gherkin
@fixture-AcmeProductBundle:product_visibility.yml
Feature: Product visibility based on localization
```

### Basic Fixture Format

```yaml
Oro\Bundle\OrganizationBundle\Entity\BusinessUnit:
    bu_visibility_es:
        name: 'BU Visibility ES'
        organization: '@organization'    # Reference to pre-loaded entity
        owner: '@business_unit'          # Reference to default BU

Oro\Bundle\UserBundle\Entity\User:
    vis_user_es:
        firstName: 'VisUserEs'
        lastName: 'Test'
        username: 'vis_user_es'
        email: 'vis_user_es@test.com'
        owner: '@bu_visibility_es'       # Reference to fixture entity above
        businessUnits: ['@bu_visibility_es']
        userRoles: ['@adminRole']        # Reference to pre-loaded role
        organization: '@organization'
        organizations: ['@organization']
        password: <userPassword(@vis_user_es->username)>
        enabled: true
```

### Key Syntax

**References:**
- `@entity_name` - Reference another fixture entity
- `@organization` - Pre-loaded default organization
- `@business_unit` - Pre-loaded default business unit
- `@adminRole` - Pre-loaded admin role
- `@item` - Pre-loaded "item" product unit
- `@usProductsFamily` - Custom pre-loaded attribute family (via ReferenceRepositoryInitializer)

**Faker functions:**
- `<name()>` - Random name
- `<email()>` - Random email
- `<sentence()>` - Random sentence
- `<userPassword(@user->username)>` - Generate password hash for user

**Method calls (for add/set methods not exposed as properties):**
```yaml
product_vis_1:
    __calls:
        - addName: ['@product_name_spanish']
```

### Product Fixture Example

```yaml
Oro\Bundle\ProductBundle\Entity\ProductName:
    product_name_spanish:
        string: 'Spanish Product'

Oro\Bundle\ProductBundle\Entity\ProductUnitPrecision:
    precision_vis1:
        unit: '@item'
        precision: '0'

Oro\Bundle\ProductBundle\Entity\Product:
    product_vis_1:
        sku: 'PROD-VIS-1'
        type: 'configurable'
        status: 'enabled'
        organization: '@organization'
        owner: '@business_unit'
        attributeFamily: '@usProductsFamily'
        inventoryStatus: '@enumInventoryStatuses'
        primaryUnitPrecision: '@precision_vis1'
        __calls:
            - addName: ['@product_name_spanish']
```

## ReferenceRepositoryInitializer

Pre-loads entity references so fixtures can reference them by alias.
Runs once when the test suite bootstraps.

### Creating an Initializer

```php
<?php

namespace Acme\Bundle\ProductBundle\Tests\Behat;

use Doctrine\Bundle\DoctrineBundle\Registry;
use Doctrine\Persistence\ObjectManager;
use Oro\Bundle\LocaleBundle\Entity\Localization;
use Oro\Bundle\ProductBundle\Entity\AttributeFamily;
use Oro\Bundle\TestFrameworkBundle\Behat\Isolation\ReferenceRepositoryInitializerInterface;
use Oro\Bundle\TestFrameworkBundle\Test\DataFixtures\Collection;

class ReferenceRepositoryInitializer implements ReferenceRepositoryInitializerInterface
{
    public function init(Registry $doctrine, Collection $referenceRepository): void
    {
        $em = $doctrine->getManager();

        // Pre-load all localizations with localization_{code} prefix
        $localizations = $em->getRepository(Localization::class)->findAll();
        foreach ($localizations as $localization) {
            $referenceRepository->set(
                'localization_' . $localization->getFormattingCode(),
                $localization
            );
        }

        // Pre-load the US Products attribute family
        $family = $em->getRepository(AttributeFamily::class)
            ->findOneBy(['code' => 'us_products']);
        if ($family) {
            $referenceRepository->set('usProductsFamily', $family);
        }
    }
}
```

### Registering the Initializer

In `Tests/Behat/services.yml`:
```yaml
services:
    Acme\Bundle\ProductBundle\Tests\Behat\ReferenceRepositoryInitializer:
        tags:
            - { name: oro_behat.reference_repository_initializer }
```

Then in fixtures:
```yaml
product:
    attributeFamily: '@usProductsFamily'   # Works because initializer loaded it
```

## Inline Data Setup via Steps

For entity-extend fields or complex associations that can't be expressed in Alice:

```gherkin
Scenario: Set up entity-extend associations
  Given product "PROD-VIS-1" has localization "es_ES"
  And business unit "BU Visibility ES" has localization "es_ES"
  And localization "es_ES" has salesOrg "1030"
```

These steps are implemented in custom Context classes using Doctrine directly.
Use this pattern when:
- Entity-extend serialized_data fields need manipulation
- Many-to-many associations need to be added after entity creation
- The fixture format can't express the relationship (e.g., enum associations)

## Pre-loaded Test Data

The behat_test database already contains:
- Default organization and business unit
- Admin user (login with `I login as administrator`)
- System localizations (en_US, fr_CA, es_ES, etc.)
- Default roles and permissions
- Product units (item, set, etc.)

Query the database to check available data:
```bash
php /oroapp/bin/console doctrine:query:sql \
  "SELECT id, name, formatting_code FROM oro_localization" \
  --env=behat_test
```
