# OroCommerce: Advanced Entity Topics

> Source: https://doc.oroinc.com/master/backend/entities/doctrine-field-types/

## AGENT QUERY HINTS

This file answers:
- How do I define entity aliases in OroCommerce?
- How are entity aliases auto-generated (what is the naming rule)?
- How do I override the default alias for an entity?
- How do I exclude an entity from alias generation?
- What is the entity name resolver and why does it exist?
- How do I implement an entity name provider?
- What events does OroEntityBundle fire?
- What is EntityStructureOptionsEvent and when is it triggered?
- What are Oro's custom Doctrine field types (money, percent, duration, config_object)?
- How do I use the `money` Doctrine column type?
- How do I define an entity repository as a Symfony service?
- How do I inject a repository via constructor injection (autowiring)?
- What is the EntityManager and how do I use it in Oro services?
- How do I write a custom entity repository class?
- What is `oro:entity-alias:debug` console command?

---

## Entity Aliases

### WHY Entity Aliases Exist

Entity aliases provide **short, human-readable names** for entity classes. Instead of referencing `Oro\Bundle\CalendarBundle\Entity\CalendarEvent`, you use `calendarevent`. Aliases are used in:

- JSON:API endpoints (e.g., `GET /api/calendarevents`)
- ACL resource identifiers
- Search index type names
- Internal configuration references

### Auto-Generated Alias Rules

Oro automatically derives aliases from class names:

| Entity type | Rule | Example |
|-------------|------|---------|
| Oro entities (class starts with `Oro`) | Lowercase short class name | `Oro\...\CalendarEvent` → `calendarevent` |
| Third-party entities | Bundle name + lowercase class name | `Acme\...\DemoBundle\Entity\MyEntity` → `demomyentity` |
| Enum entities | Enum code with underscores removed | `document_status` → `documentstatus` |
| Custom entities (admin-created) | `extend` + lowercase class name | → `extendmyentity` |
| Hidden entities | Excluded automatically | — |

> WHY the bundle prefix for third-party: avoids naming collisions when multiple bundles define entities with the same short class name.

### Custom Aliases via YAML

Override auto-generated aliases in `Resources/config/oro/entity.yml`:

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/entity.yml

oro_entity:
    entity_aliases:
        # Use this when the auto-generated alias is too long or ambiguous.
        # alias: singular form (used in JSON:API type, route params)
        # plural_alias: plural form (used in collection endpoints)
        Acme\Bundle\DemoBundle\Entity\Document:
            alias: document
            plural_alias: documents

        Acme\Bundle\DemoBundle\Entity\Priority:
            alias: documentpriority
            plural_alias: documentpriorities

    # Exclude internal/helper entities from alias generation.
    # WHY: These entities should not appear in APIs or search results.
    entity_alias_exclusions:
        - Acme\Bundle\DemoBundle\Entity\InternalCache
        - Oro\Bundle\ConfigBundle\Entity\Config
```

### Custom Alias Provider (PHP)

For dynamic alias resolution (e.g., when the entity class is determined at runtime):

```php
<?php
namespace Acme\Bundle\DemoBundle\Provider;

use Oro\Bundle\EntityBundle\Model\EntityAlias;
use Oro\Bundle\EntityBundle\Provider\EntityAliasProviderInterface;

class EmailEntityAliasProvider implements EntityAliasProviderInterface
{
    public function __construct(
        private readonly string $emailAddressProxyClass
    ) {}

    /**
     * Return an EntityAlias for the given class, or null to let other providers handle it.
     * WHY: Allows dynamic alias assignment that YAML cannot express.
     */
    public function getEntityAlias(string $entityClass): EntityAlias|null|false
    {
        if ($entityClass === $this->emailAddressProxyClass) {
            // EntityAlias(singular, plural)
            return new EntityAlias('emailaddress', 'emailaddresses');
        }

        // Return null to pass control to the next provider.
        // Return false to exclude the entity from alias generation entirely.
        return null;
    }
}
```

Register with DI tag:

```yaml
services:
    acme_demo.provider.email_entity_alias:
        class: Acme\Bundle\DemoBundle\Provider\EmailEntityAliasProvider
        arguments:
            - '%acme_demo.email_address_proxy_class%'
        tags:
            # priority: higher priority providers are checked first (default: 0)
            - { name: oro_entity.alias_provider, priority: 10 }
```

### Viewing All Aliases

```bash
# Display all registered entity aliases in a table
php bin/console oro:entity-alias:debug
```

---

## Entity Name Resolver and Providers

### WHY the Name Resolver Exists

When Oro displays an entity reference in the UI (e.g., "Created by John Smith", "Related to Invoice #1234"), it needs a **human-readable string** for the entity. The `EntityNameResolver` service provides this by delegating to registered `EntityNameProviderInterface` implementations.

### EntityNameResolver: Getting a Name

```php
<?php
use Oro\Bundle\EntityBundle\Provider\EntityNameResolver;

class MyService
{
    public function __construct(
        private readonly EntityNameResolver $entityNameResolver
    ) {}

    public function getDisplayName(object $entity, string $locale = null): string
    {
        // resolve(entity, format, locale)
        // format: 'full' (default) or 'short'
        // WHY format: 'short' is used in autocompletes, 'full' in views and emails.
        return $this->entityNameResolver->getName($entity, 'full', $locale);
    }
}
```

### Implementing a Custom Name Provider

```php
<?php
namespace Acme\Bundle\DemoBundle\Provider;

use Acme\Bundle\DemoBundle\Entity\Document;
use Oro\Bundle\EntityBundle\Provider\EntityNameProviderInterface;

class DocumentNameProvider implements EntityNameProviderInterface
{
    /**
     * Return a display name for the entity, or false if this provider
     * does not handle the given class/format combination.
     *
     * @param string      $format   'full' or 'short'
     * @param string|null $locale   BCP 47 locale string
     * @param object      $entity   the entity to name
     */
    public function getName(string $format, ?string $locale, object $entity): string|false
    {
        if (!$entity instanceof Document) {
            return false; // let another provider handle it
        }

        if ($format === EntityNameProviderInterface::SHORT) {
            // Short format: just the subject, truncated
            return mb_strimwidth($entity->getSubject(), 0, 50, '...');
        }

        // Full format: subject + due date
        $name = $entity->getSubject();
        if ($entity->getDueDate()) {
            $name .= ' (due: ' . $entity->getDueDate()->format('Y-m-d') . ')';
        }
        return $name;
    }

    /**
     * Return a DQL expression for name resolution in bulk queries,
     * or false if DQL is not supported for this entity.
     * WHY: Bulk name resolution (e.g., in a datagrid) should avoid N+1 queries.
     */
    public function getNameDQL(string $format, ?string $locale, string $className, string $alias): string|false
    {
        if ($className !== Document::class) {
            return false;
        }

        // Return a DQL CONCAT expression using the entity alias
        return sprintf('%s.subject', $alias);
    }
}
```

Register with DI tag:

```yaml
services:
    acme_demo.provider.document_name:
        class: Acme\Bundle\DemoBundle\Provider\DocumentNameProvider
        tags:
            # priority: higher priority providers are tried first (default: 0)
            - { name: oro_entity.name_provider, priority: 100 }
```

### EntityNameProviderInterface constants

| Constant | Value | Use case |
|----------|-------|---------|
| `SHORT` | `'short'` | Autocomplete results, inline references |
| `FULL` | `'full'` | View pages, emails, audit entries |

---

## Entity Events

### WHY Events Exist

OroEntityBundle fires events at key points in entity lifecycle processing, allowing other bundles to inject additional data or modify behavior without modifying core code.

### EntityStructureOptionsEvent

**Class:** `Oro\Bundle\EntityBundle\Event\EntityStructureOptionsEvent`
**Event name:** `oro_entity.structure.options`

**Fires when:** `EntityStructureDataProvider` has populated or updated entity structure data.

**Use case:** Add custom options to entity structure metadata (used by the entity field chooser UI, relations picker, etc.).

```php
<?php
namespace Acme\Bundle\DemoBundle\EventListener;

use Oro\Bundle\EntityBundle\Event\EntityStructureOptionsEvent;
use Oro\Bundle\EntityBundle\Model\EntityStructure;

class DocumentStructureOptionsListener
{
    /**
     * Called when entity structure data is built.
     * Use this to inject custom metadata into entity field definitions.
     */
    public function onEntityStructureOptions(EntityStructureOptionsEvent $event): void
    {
        $data = $event->getData(); // EntityStructure[]

        foreach ($data as $entityStructure) {
            if ($entityStructure->getClassName() !== Document::class) {
                continue;
            }

            // Add a custom option to the entity structure
            $entityStructure->addOption('my_bundle_enabled', true);
        }
    }
}
```

Register as an event listener:

```yaml
services:
    acme_demo.event_listener.document_structure_options:
        class: Acme\Bundle\DemoBundle\EventListener\DocumentStructureOptionsListener
        tags:
            - { name: kernel.event_listener,
                event: oro_entity.structure.options,
                method: onEntityStructureOptions }
```

---

## Doctrine Field Types (Oro Custom Types)

Oro registers custom Doctrine column types that provide automatic formatting across the application. Use these in entity mappings when you need the semantic meaning and UI formatting they provide.

### `money` — Monetary Values

```php
// Stored as: DECIMAL(19, 4)
// Auto-formatted: displayed with currency formatter in views and grids
// WHY: Consistent precision for financial calculations; 4 decimal places
//      handles most currency conventions worldwide.

#[ORM\Column(name: 'tax_amount', type: 'money')]
protected ?string $taxAmount = null;

// In a migration:
$table->addColumn('tax_amount', 'money', ['notnull' => false]);
```

### `percent` — Percentage Values

```php
// Stored as: FLOAT
// Auto-formatted: displayed with % symbol and percent formatter in views/grids
// WHY: Using float for percent allows fractional percentages (e.g., 12.5%).

#[ORM\Column(name: 'discount_rate', type: 'percent')]
protected ?float $discountRate = null;
```

### `duration` — Time Duration

```php
// Stored as: INTEGER (seconds)
// Auto-formatted: displayed as HH:MM:SS in views
// WHY: Storing as seconds makes arithmetic simple; formatting is done at display time.

#[ORM\Column(name: 'call_duration', type: 'duration')]
protected ?int $callDuration = null;
```

### `config_object` — Configuration Objects

```php
// Stored as: JSON-serialized string (TEXT)
// Converted to: Oro\Component\Config\Common\ConfigObject instances
// WHY: Use for structured config data that isn't a simple scalar.
//      ConfigObject provides dot-notation access to nested keys.

#[ORM\Column(name: 'settings', type: 'config_object', nullable: true)]
protected ?ConfigObject $settings = null;
```

### Using custom types in extended fields

These types are available when creating extended fields via UI (Entity Management) or migrations, allowing non-developers to add money/percent/duration fields with proper formatting automatically applied.

### Full Doctrine type reference

| Oro type | PHP type | DB type | Auto-formatted? |
|----------|----------|---------|----------------|
| `money` | string | DECIMAL(19,4) | YES — currency formatter |
| `percent` | float | FLOAT | YES — percent formatter |
| `duration` | int | INTEGER | YES — HH:MM:SS |
| `config_object` | ConfigObject | TEXT (JSON) | NO |

---

## Repositories as Services

### WHY Repositories as Services

By default, Doctrine repositories are retrieved via `$entityManager->getRepository(Entity::class)`. Defining them as Symfony services allows:

- **Constructor injection** — inject repositories directly into other services
- **Autowiring** — no need to inject the EntityManager just to get a repository
- **Testability** — mock the repository interface without Doctrine

### Method 1: Service definition (YAML)

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/services.yml

services:
    # Define the repository as a service using the ManagerRegistry factory.
    Acme\Bundle\DemoBundle\Entity\Repository\DocumentRepository:
        # factory: calls ManagerRegistry::getRepository() to build the service.
        # WHY factory: Doctrine repositories cannot be instantiated with `new`
        #              without a properly configured EntityManager.
        factory: ['@doctrine', 'getRepository']
        arguments:
            - Acme\Bundle\DemoBundle\Entity\Document
```

### Method 2: Entity attribute (Doctrine 2.4+)

```php
<?php
// src/Acme/Bundle/DemoBundle/Entity/Document.php

#[ORM\Entity(repositoryClass: DocumentRepository::class)]
#[ORM\Table(name: 'acme_demo_document')]
class Document
{
    // ...
}
```

Then define the repository class:

```php
<?php
// src/Acme/Bundle/DemoBundle/Entity/Repository/DocumentRepository.php

namespace Acme\Bundle\DemoBundle\Entity\Repository;

use Acme\Bundle\DemoBundle\Entity\Document;
use Doctrine\Bundle\DoctrineBundle\Repository\ServiceEntityRepository;
use Doctrine\Persistence\ManagerRegistry;

// WHY ServiceEntityRepository: provides the same API as Doctrine's default
// repository, plus it works correctly when defined as a service.
class DocumentRepository extends ServiceEntityRepository
{
    public function __construct(ManagerRegistry $registry)
    {
        parent::__construct($registry, Document::class);
    }

    /**
     * Find all documents due before a given date, ordered by due date.
     * WHY custom method: keeps query logic in the repository, not in services/controllers.
     */
    public function findOverdue(\DateTimeInterface $asOf): array
    {
        return $this->createQueryBuilder('d')
            ->where('d.dueDate < :asOf')
            ->andWhere('d.dueDate IS NOT NULL')
            ->setParameter('asOf', $asOf)
            ->orderBy('d.dueDate', 'ASC')
            ->getQuery()
            ->getResult();
    }

    /**
     * Find documents by priority label using a JOIN.
     */
    public function findByPriorityLabel(string $label): array
    {
        return $this->createQueryBuilder('d')
            ->innerJoin('d.priority', 'p')
            ->where('p.label = :label')
            ->setParameter('label', $label)
            ->getQuery()
            ->getResult();
    }
}
```

Register as a service so it can be autowired:

```yaml
services:
    Acme\Bundle\DemoBundle\Entity\Repository\DocumentRepository:
        factory: ['@doctrine', 'getRepository']
        arguments:
            - Acme\Bundle\DemoBundle\Entity\Document
```

### Injecting the repository

```php
<?php
namespace Acme\Bundle\DemoBundle\Service;

use Acme\Bundle\DemoBundle\Entity\Repository\DocumentRepository;

class DocumentService
{
    public function __construct(
        // Autowired because the repository is defined as a service
        private readonly DocumentRepository $documentRepository
    ) {}

    public function getOverdueDocuments(): array
    {
        return $this->documentRepository->findOverdue(new \DateTime());
    }
}
```

---

## EntityManager Usage in Services

In OroCommerce services, use `Doctrine\ORM\EntityManagerInterface` for persistence operations:

```php
<?php
namespace Acme\Bundle\DemoBundle\Service;

use Acme\Bundle\DemoBundle\Entity\Document;
use Doctrine\ORM\EntityManagerInterface;

class DocumentPersistenceService
{
    public function __construct(
        private readonly EntityManagerInterface $entityManager
    ) {}

    public function create(Document $document): void
    {
        // persist(): registers a NEW entity with the Unit of Work.
        // WHY: Without persist(), flush() ignores the entity entirely.
        $this->entityManager->persist($document);
        $this->entityManager->flush();
    }

    public function update(Document $document): void
    {
        // No persist() needed for a managed entity (already retrieved from DB).
        // Doctrine tracks changes to managed entities automatically.
        $this->entityManager->flush();
    }

    public function delete(Document $document): void
    {
        $this->entityManager->remove($document);
        $this->entityManager->flush();
    }

    public function findById(int $id): ?Document
    {
        // find(): uses the identity map (no query if already loaded in this request).
        return $this->entityManager->find(Document::class, $id);
    }

    public function findAll(): array
    {
        // getRepository(): returns the repository for an entity class.
        // WHY: Use this when you don't have the repository injected.
        return $this->entityManager->getRepository(Document::class)->findAll();
    }

    public function transactional(callable $callback): void
    {
        // WHY transactional: groups multiple operations so they all succeed or all fail.
        // Automatically commits on success, rolls back on exception.
        $this->entityManager->transactional($callback);
    }
}
```

### EntityManager method reference

| Method | Description |
|--------|-------------|
| `persist($entity)` | Register a new entity for insertion |
| `flush()` | Write all pending changes to the database |
| `remove($entity)` | Schedule a managed entity for deletion |
| `find($class, $id)` | Find entity by primary key (uses identity map cache) |
| `getRepository($class)` | Get the repository for an entity class |
| `refresh($entity)` | Reload entity state from the database (discard local changes) |
| `detach($entity)` | Stop tracking an entity (changes won't be persisted) |
| `merge($entity)` | Re-attach a detached entity |
| `clear()` | Detach all entities (reset the identity map) |
| `contains($entity)` | Check if entity is managed by this EntityManager |
| `transactional($callback)` | Execute callback inside a DB transaction |
| `beginTransaction()` | Manually begin a transaction |
| `commit()` | Commit the current transaction |
| `rollback()` | Roll back the current transaction |

---

## Common Pitfalls

### Entity Aliases
| Pitfall | Problem | Fix |
|---------|---------|-----|
| Auto-generated alias collision | Two entities get the same alias | Define explicit alias in `entity.yml` with a unique value |
| Enum code > 21 chars affects alias | Dynamic table name truncation | Keep enum codes short |
| Not running debug command | Unknown what alias Oro generated | Run `oro:entity-alias:debug` to inspect |

### Name Resolver
| Pitfall | Problem | Fix |
|---------|---------|-----|
| Provider returns wrong type | TypeError at runtime | Return `string` or `false`, not `null` |
| No `getNameDQL()` implementation | N+1 queries in bulk operations | Implement DQL version for entities used in grids |
| Priority too low | Another provider's name returned instead | Increase tag priority |

### Repositories as Services
| Pitfall | Problem | Fix |
|---------|---------|-----|
| Not extending `ServiceEntityRepository` | Repository instantiation fails when used as service | Extend `ServiceEntityRepository` instead of `EntityRepository` |
| Injecting `EntityManager` instead of repository | Tests harder to mock | Inject the specific repository interface instead |
| Using `$em->getRepository()` in tests | Test bypasses service container | Define repository as service and inject it |

### Doctrine Field Types
| Pitfall | Problem | Fix |
|---------|---------|-----|
| Using `decimal` instead of `money` | No auto-formatting in views/grids | Use `money` type for monetary columns |
| Storing money as `float` | Floating point precision errors | Use `money` (DECIMAL) for all monetary values |
| Storing duration as string | Cannot sort numerically | Use `duration` (INTEGER seconds) |
