# OroCommerce Scopes — Complete Developer Reference

> Source: https://doc.oroinc.com/master/backend/scopes/

## AGENT QUERY HINTS

Use this file when asked about:
- "What is a scope in OroCommerce?"
- "How do scopes work with pricing / visibility?"
- "How do I create a scope criteria provider?"
- "How do I find a scope by website or customer?"
- "What is ScopeCriteriaProviderInterface?"
- "How does ScopeManager work?"
- "How do I apply scope criteria to a Doctrine query?"
- "Why does ProductVisibility use scopes?"
- "How do I add a scope association via migration?"
- "What is a scope type?"
- "How do scopes interact with system configuration?"
- "When should I use scopes vs system config?"

---

## 1. What is a Scope?

A **Scope** is "a set of application parameters with different values in different requests." It is a data object that captures the current context — which website the request is on, which customer is logged in, which customer group they belong to, etc.

Scopes exist to solve a fundamental OroCommerce problem: **the same entity (a product, a price, a page slug) may behave differently depending on who is asking and from where.**

### Real-world scope uses in OroCommerce:

| Use case | Criteria in scope |
|---|---|
| Product visibility per customer | customer, customer group, website |
| Price list assignment | customer, customer group, website |
| Web content (CMS pages, slugs) | website |
| System configuration values | website, user |
| Shopping list rules | customer, website |

---

## 2. Core Architecture

### The Scope Entity

A `Scope` is a database record with nullable columns — one for each registered scope criterion. The combination of non-null columns identifies a unique context.

```
scope table:
| id | website_id | customer_id | customer_group_id | user_id | ... |
|----|------------|-------------|-------------------|---------|-----|
|  1 |          1 |        NULL |              NULL |    NULL |     |  <- website-only scope
|  2 |          1 |          5 |              NULL |    NULL |     |  <- website + customer scope
|  3 |       NULL |       NULL |              NULL |    NULL |     |  <- default (all NULL) scope
```

### Key Services

| Service | Responsibility |
|---|---|
| `ScopeManager` (`oro_scope.scope_manager`) | Find, create, and query scopes |
| `ScopeCriteriaProviderInterface` | Contribute one criterion to the scope (e.g., current website) |
| `ScopeCriteria` | Value object carrying the current context; applied to queries |

---

## 3. Scope Criteria Providers

A **Scope Criteria Provider** calculates the value of one scope field based on the current request context.

### Interface

```php
namespace Oro\Bundle\ScopeBundle\Manager;

interface ScopeCriteriaProviderInterface
{
    /**
     * Returns the field name this provider contributes to the scope.
     * Must match the column added via migration (see Section 7).
     */
    public function getCriteriaField(): string;

    /**
     * Returns the current value of this criterion.
     * Called at query time to build the current scope context.
     * Return null if this criterion is not applicable in the current request.
     */
    public function getCriteriaValue(): mixed;

    /**
     * Returns the FQCN of the criterion's value type (e.g., Website::class).
     * Used to generate the correct Doctrine join condition.
     */
    public function getCriteriaValueType(): string;
}
```

### Example — Website Criteria Provider

```php
<?php
namespace Oro\Bundle\WebsiteBundle\Provider;

use Oro\Bundle\ScopeBundle\Manager\ScopeCriteriaProviderInterface;
use Oro\Bundle\WebsiteBundle\Entity\Website;
use Oro\Bundle\WebsiteBundle\Manager\WebsiteManager;

class ScopeWebsiteCriteriaProvider implements ScopeCriteriaProviderInterface
{
    public const WEBSITE = 'website';

    public function __construct(
        private readonly WebsiteManager $websiteManager,
    ) {}

    public function getCriteriaField(): string
    {
        return self::WEBSITE; // field name in the Scope entity
    }

    public function getCriteriaValue(): ?Website
    {
        return $this->websiteManager->getCurrentWebsite();
    }

    public function getCriteriaValueType(): string
    {
        return Website::class;
    }
}
```

### Example — Customer Criteria Provider

```php
<?php
namespace Oro\Bundle\CustomerBundle\Provider;

use Oro\Bundle\CustomerBundle\Entity\Customer;
use Oro\Bundle\ScopeBundle\Manager\ScopeCriteriaProviderInterface;
use Symfony\Component\Security\Core\Authentication\Token\Storage\TokenStorageInterface;

class ScopeCustomerCriteriaProvider implements ScopeCriteriaProviderInterface
{
    public const CUSTOMER = 'customer';

    public function __construct(
        private readonly TokenStorageInterface $tokenStorage,
    ) {}

    public function getCriteriaField(): string
    {
        return self::CUSTOMER;
    }

    public function getCriteriaValue(): ?Customer
    {
        $token = $this->tokenStorage->getToken();
        if ($token === null) {
            return null;
        }
        $user = $token->getUser();
        return ($user instanceof \Oro\Bundle\CustomerBundle\Entity\CustomerUser)
            ? $user->getCustomer()
            : null;
    }

    public function getCriteriaValueType(): string
    {
        return Customer::class;
    }
}
```

### Registering a Criteria Provider

```yaml
# Resources/config/services.yml
services:
    Oro\Bundle\CustomerBundle\Provider\ScopeCustomerCriteriaProvider:
        arguments:
            - '@security.token_storage'
        tags:
            - { name: oro_scope.provider, scopeType: web_content, priority: 200 }
            - { name: oro_scope.provider, scopeType: price_list,  priority: 200 }
```

**Key tag parameters:**

| Parameter | Description |
|---|---|
| `scopeType` | Identifies which scope consumer this provider serves. One provider can serve multiple scope types. |
| `priority` | Higher value = higher importance. Providers with higher priority are evaluated first when resolving scope matches. |

---

## 4. Scope Types

A **scope type** is a named grouping that tells the scope system which providers to include. Each feature that uses scopes defines its own scope type.

| Scope Type | Used by | Typical criteria |
|---|---|---|
| `web_content` | CMS pages, slugs, content nodes | website, customer, customer group |
| `price_list` | Price list assignment | website, customer, customer group |
| `product_visibility` | Product visibility rules | website, customer, customer group |
| `segment` | Customer segments | customer, customer group |

A single provider can participate in multiple scope types (via multiple tags).

---

## 5. ScopeManager Operations

The `ScopeManager` is the central service for scope operations. Inject it as `oro_scope.scope_manager`.

```php
<?php
use Oro\Bundle\ScopeBundle\Manager\ScopeManager;
use Oro\Bundle\WebsiteBundle\Provider\ScopeWebsiteCriteriaProvider;
use Oro\Bundle\CustomerBundle\Provider\ScopeCustomerCriteriaProvider;

class ProductVisibilityProvider
{
    public function __construct(
        private readonly ScopeManager $scopeManager,
    ) {}

    /**
     * Find an existing scope matching the given context.
     * Returns null if no matching scope record exists.
     */
    public function findScopeForWebsite(Website $website): ?Scope
    {
        return $this->scopeManager->find('product_visibility', [
            ScopeWebsiteCriteriaProvider::WEBSITE => $website,
        ]);
    }

    /**
     * Find an existing scope or create one if it doesn't exist.
     * Use when you need to assign an entity to a scope.
     */
    public function findOrCreateScope(Website $website, Customer $customer): Scope
    {
        return $this->scopeManager->findOrCreate('product_visibility', [
            ScopeWebsiteCriteriaProvider::WEBSITE    => $website,
            ScopeCustomerCriteriaProvider::CUSTOMER  => $customer,
        ]);
    }

    /**
     * Get the default scope — all criteria are NULL.
     * Represents global/fallback settings.
     */
    public function getDefaultScope(): Scope
    {
        return $this->scopeManager->findDefaultScope();
    }

    /**
     * Find ALL scopes that match the current request context,
     * ordered by priority (most specific first).
     */
    public function findRelatedScopes(): array
    {
        return $this->scopeManager->findRelatedScopes('product_visibility');
    }

    /**
     * Use current request context (providers auto-evaluate their values).
     * No second argument = use getCriteriaValue() from each registered provider.
     */
    public function findCurrentScope(): ?Scope
    {
        return $this->scopeManager->find('product_visibility');
    }
}
```

### Using a Custom Context (Override Providers)

Pass a context array to override what the providers would normally return:

```php
// Force a specific customer context regardless of the current user
$scope = $this->scopeManager->find('price_list', [
    'website'  => $specificWebsite,
    'customer' => $specificCustomer,
]);
```

---

## 6. Applying Scope Criteria to Doctrine Queries

The most important use of scopes is filtering database queries so the most specific matching record is returned.

```php
<?php
use Doctrine\ORM\QueryBuilder;

class SlugRepository extends \Doctrine\ORM\EntityRepository
{
    public function findSlugByUrlAndScope(
        string $url,
        \Oro\Bundle\ScopeBundle\Manager\ScopeManager $scopeManager
    ): ?Slug {
        $qb = $this->createQueryBuilder('slug');
        $qb
            ->innerJoin('slug.scopes', 'scopes')
            ->where('slug.url = :url')
            ->setParameter('url', $url)
            ->setMaxResults(1);

        // Get the criteria object for the current request context
        $scopeCriteria = $scopeManager->getCriteria('web_content');

        // Apply scope filtering with priority ordering.
        // Generates SQL like:
        //   ORDER BY
        //     CASE WHEN scopes.website_id = ? THEN 1 ELSE 0 END +
        //     CASE WHEN scopes.customer_id = ? THEN 1 ELSE 0 END DESC
        //   WHERE (scopes.website_id = ? OR scopes.website_id IS NULL)
        //     AND (scopes.customer_id = ? OR scopes.customer_id IS NULL)
        $scopeCriteria->applyToJoinWithPriority($qb, 'scopes');

        return $qb->getQuery()->getOneOrNullResult();
    }
}
```

**WHY `applyToJoinWithPriority`:** It generates SQL that returns the most specific match first. A record scoped to both `website=1` AND `customer=5` ranks higher than one scoped to `website=1` only, which ranks higher than an unscoped default. This is the core of Oro's "waterfall" configuration model.

---

## 7. Adding a Scope Column via Migration

When you create a new bundle that uses scopes, you must add your entity's reference column to the `oro_scope` table via a Doctrine migration.

```php
<?php
namespace Bridge\Bundle\BridgeCustomerBundle\Migrations\Schema\v1_0;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;
use Oro\Bundle\ScopeBundle\Migration\Extension\ScopeExtensionAwareInterface;
use Oro\Bundle\ScopeBundle\Migration\Extension\ScopeExtensionAwareTrait;

/**
 * Adds a 'division' association to the scope table,
 * enabling per-division scoped configurations.
 */
class AddDivisionScopeRelation implements Migration, ScopeExtensionAwareInterface
{
    use ScopeExtensionAwareTrait;

    public function up(Schema $schema, QueryBag $queries): void
    {
        $this->scopeExtension->addScopeAssociation(
            $schema,
            'division',                                   // Field name in the scope
            'bridge_division',                            // Target table name
            'name'                                        // Target table display column
        );
    }
}
```

This adds a `division_id` (nullable FK) column to `oro_scope`, enabling scope criteria tied to a division entity.

---

## 8. Scopes vs System Configuration — When to Use Which

| Concern | Use Scopes | Use System Config |
|---|---|---|
| **Per-entity data** (visibility, pricing per product) | Yes — scopes attach to entity records | No |
| **Per-website settings** (URL, logo, locale) | No — use config scope manager | Yes |
| **Request-time resolution** (what data does this user see?) | Yes | Sometimes |
| **Admin-configurable options** | No | Yes |
| **Complex priority fallback** (customer > group > website > default) | Yes | Partially (website > global) |

**Rule of thumb:** If you need to associate a **record** (price, visibility rule, slug) with a context, use scopes. If you need a **setting** (a boolean flag, a string value) that varies by website or globally, use system configuration.

---

## 9. Complete Custom Scope Provider Example

This example adds a "Division" scope criterion to the `price_list` scope type for the Braskem project:

### Provider

```php
<?php
namespace Bridge\Bundle\BridgeCustomerBundle\Provider;

use Bridge\Bundle\BridgeEntityBundle\Entity\Division;
use Bridge\Bundle\BridgeCommonBundle\Service\DivisionService;
use Oro\Bundle\ScopeBundle\Manager\ScopeCriteriaProviderInterface;

/**
 * Provides the current customer's division as a scope criterion.
 * Used to resolve division-specific price lists.
 */
class ScopeDivisionCriteriaProvider implements ScopeCriteriaProviderInterface
{
    public const DIVISION = 'division';

    public function __construct(
        private readonly DivisionService $divisionService,
    ) {}

    public function getCriteriaField(): string
    {
        return self::DIVISION;
    }

    public function getCriteriaValue(): ?Division
    {
        return $this->divisionService->getCurrentCustomerDivision();
    }

    public function getCriteriaValueType(): string
    {
        return Division::class;
    }
}
```

### Service Registration

```yaml
# Resources/config/services.yml
services:
    Bridge\Bundle\BridgeCustomerBundle\Provider\ScopeDivisionCriteriaProvider:
        arguments:
            - '@Bridge\Bundle\BridgeCommonBundle\Service\DivisionService'
        tags:
            - { name: oro_scope.provider, scopeType: price_list, priority: 250 }
```

**Priority 250** ranks this criterion above the standard customer (200) and website (100) providers, making division the most specific scope factor for price list resolution.

### Query Usage

```php
$scopeCriteria = $this->scopeManager->getCriteria('price_list');
// Now includes: division > customer > customer_group > website > (default)
$scopeCriteria->applyToJoinWithPriority($queryBuilder, 'priceLists');
```

---

## 10. Scope-Aware Repositories — Pattern Summary

```php
// 1. Get criteria for the current request
$criteria = $scopeManager->getCriteria('price_list');

// 2. Build your query
$qb = $em->createQueryBuilder()
    ->select('pl')
    ->from(PriceList::class, 'pl')
    ->innerJoin('pl.scopes', 'scope');

// 3. Apply scope filtering (adds WHERE + ORDER BY for priority)
$criteria->applyToJoinWithPriority($qb, 'scope');

// 4. Execute — the first result is the most specific match
$priceList = $qb->setMaxResults(1)->getQuery()->getOneOrNullResult();
```

This pattern is the foundation of all multi-website, multi-customer data resolution in OroCommerce.
