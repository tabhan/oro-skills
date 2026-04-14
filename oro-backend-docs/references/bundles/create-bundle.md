# OroCommerce: Creating a Custom Bundle

> Source: https://doc.oroinc.com/master/backend/extension/create-bundle/

## AGENT QUERY HINTS

This file answers:
- How do I create a new bundle in OroCommerce?
- What is the minimum required file structure for an Oro bundle?
- How does Oro auto-discover bundles?
- What is bundles.yml and where does it go?
- How do I register services in a bundle?
- How do I set up routing in a bundle?
- What is the bundle class (e.g., BridgeEntityBundle.php) and what does it contain?
- How do I namespace my bundle correctly?
- What is the difference between a Bridge bundle and an Aaxis bundle?
- How does PSR-4 autoloading work for custom bundles?
- What folder structure should I use for entities, services, and controllers?

---

## Core Concept: WHY Bundles Exist

A **bundle** is Symfony's unit of feature packaging. It groups related PHP classes, configuration, templates, and assets into a self-contained directory. In OroCommerce, every feature — from the product catalog to the customer portal — lives in a bundle.

**Custom bundles** let you add new entities, services, controllers, and UI without modifying vendor code. All customizations go in `src/`.

---

## Complete Bundle Directory Structure

This is the full structure for a production-ready bundle in the Braskem project style:

```
src/Bridge/Bundle/BridgeNewsBundle/
├── BridgeNewsBundle.php                    ← Bundle class (required)
├── Entity/
│   └── BridgeNewsArticle.php               ← Entity classes
├── Migrations/
│   └── Schema/
│       └── v1_0/
│           └── CreateBridgeNewsArticle.php ← Database migrations
├── Controller/
│   └── Admin/
│       └── BridgeNewsArticleController.php ← Admin CRUD controller
├── Form/
│   └── Type/
│       └── BridgeNewsArticleType.php       ← Symfony form type
└── Resources/
    ├── config/
    │   ├── services.yml                    ← Service definitions
    │   └── oro/
    │       ├── bundles.yml                 ← Bundle auto-discovery (required)
    │       ├── routing.yml                 ← Route auto-discovery
    │       ├── entity.yml                  ← Entity aliases
    │       ├── acls.yml                    ← ACL resource definitions
    │       ├── datagrids.yml               ← Datagrid definitions
    │       └── navigation.yml              ← Admin menu items
    └── views/
        └── BridgeNewsArticle/
            ├── index.html.twig             ← List page
            ├── view.html.twig              ← Detail view
            └── update.html.twig            ← Create/edit form
```

---

## Step 1: Create the Bundle Class

Every bundle needs a bundle class. This is the entry point Symfony uses.

```php
<?php
// src/Bridge/Bundle/BridgeNewsBundle/BridgeNewsBundle.php

namespace Bridge\Bundle\BridgeNewsBundle;

use Symfony\Component\HttpKernel\Bundle\Bundle;

/**
 * This class is the entry point for the BridgeNewsBundle.
 *
 * WHY extend Bundle: Symfony's kernel discovers bundle classes and calls
 * boot()/shutdown() lifecycle methods. Most bundles have no custom
 * boot logic, so a minimal extension of Bundle is sufficient.
 *
 * WHY the class name matches the directory: PSR-4 autoloading requires
 * the class name to match the filename. The directory name and class
 * name must match exactly (both BridgeNewsBundle).
 */
class BridgeNewsBundle extends Bundle
{
    // No additional code needed for a basic bundle.
    // Override build() here if you need to register compiler passes.
}
```

---

## Step 2: Register the Bundle for Auto-Discovery

OroCommerce auto-discovers bundles via this YAML file. Without it, the bundle is invisible to Oro.

```yaml
# src/Bridge/Bundle/BridgeNewsBundle/Resources/config/oro/bundles.yml

bundles:
    # The fully qualified class name of the bundle class.
    # WHY: Oro's kernel scanner reads this file from every bundle
    # and adds the listed classes to the application kernel.
    - Bridge\Bundle\BridgeNewsBundle\BridgeNewsBundle
```

With load priority (lower number loads first, before higher numbers):

```yaml
bundles:
    - { name: Bridge\Bundle\BridgeNewsBundle\BridgeNewsBundle, priority: 200 }
```

**WHY priority matters:** If your bundle overrides templates or services from another bundle, it must load AFTER the other bundle. Use a higher priority number to load later. Oro's own bundles typically use priority 0–100.

---

## Step 3: Configure PSR-4 Autoloading

Add your namespace to `composer.json` so PHP can find your classes:

```json
{
    "autoload": {
        "psr-4": {
            "Bridge\\Bundle\\BridgeNewsBundle\\": "src/Bridge/Bundle/BridgeNewsBundle/"
        }
    }
}
```

After editing `composer.json`, regenerate the autoloader:

```bash
composer dump-autoload
```

**WHY PSR-4**: The namespace `Bridge\Bundle\BridgeNewsBundle\Entity\BridgeNewsArticle` maps to the file path `src/Bridge/Bundle/BridgeNewsBundle/Entity/BridgeNewsArticle.php`. If the mapping is missing, PHP throws `Class not found` errors.

In the Braskem project, the top-level namespace maps are already configured:

```json
{
    "autoload": {
        "psr-4": {
            "Bridge\\": "src/Bridge/",
            "Aaxis\\": "src/Aaxis/"
        }
    }
}
```

---

## Step 4: Register Routes

Create the routing auto-discovery file:

```yaml
# src/Bridge/Bundle/BridgeNewsBundle/Resources/config/oro/routing.yml

# WHY: Oro's router scans every bundle's Resources/config/oro/routing.yml
# and imports the routes automatically — no application-level routing.yaml
# modification required.

BridgeNewsBundle_admin:
    resource:     "@BridgeNewsBundle/Controller/Admin/"
    type:         annotation
    prefix:       /admin
```

For PHP attribute-based routing (PHP 8+), use the `attribute` type:

```yaml
BridgeNewsBundle_admin:
    resource:     "@BridgeNewsBundle/Controller/Admin/"
    type:         attribute
    prefix:       /admin
```

---

## Step 5: Set Up Services

```yaml
# src/Bridge/Bundle/BridgeNewsBundle/Resources/config/services.yml

services:
    # _defaults applies to all services in this file.
    # WHY autowire: true: Symfony resolves constructor dependencies
    # automatically by type-hint — less manual wiring.
    # WHY autoconfigure: true: Services tagged as event_listeners,
    # command handlers, etc., are auto-registered.
    # WHY public: false: Services are private by default (best practice
    # for DI containers; only inject, never pull from container).
    _defaults:
        autowire: true
        autoconfigure: true
        public: false

    # Auto-register all classes in the bundle.
    # WHY: This eliminates the need to manually declare every controller,
    # listener, and service — they are discovered automatically.
    Bridge\Bundle\BridgeNewsBundle\:
        resource: '../../*'
        # WHY exclude: These directories contain non-service classes
        # (DI extension code and YAML config) that should not be
        # auto-registered as services.
        exclude: '../../{DependencyInjection,Resources}'
```

---

## Step 6: Clear Cache and Verify

After creating the bundle files:

```bash
# Regenerate autoloader (if you added namespace to composer.json)
composer dump-autoload

# Clear Symfony cache (re-reads bundle discovery, services, routes)
php bin/console cache:clear

# Verify the bundle is loaded
php bin/console debug:container | grep -i news

# Verify routes are registered
php bin/console debug:router | grep -i news
```

---

## Real Example: BridgeNewsBundle — Complete Walkthrough

This walkthrough creates a minimal but complete bundle for managing news articles.

### File 1: Bundle class

```php
<?php
// src/Bridge/Bundle/BridgeNewsBundle/BridgeNewsBundle.php

namespace Bridge\Bundle\BridgeNewsBundle;

use Symfony\Component\HttpKernel\Bundle\Bundle;

class BridgeNewsBundle extends Bundle {}
```

### File 2: bundles.yml

```yaml
# src/Bridge/Bundle/BridgeNewsBundle/Resources/config/oro/bundles.yml
bundles:
    - Bridge\Bundle\BridgeNewsBundle\BridgeNewsBundle
```

### File 3: Entity

```php
<?php
// src/Bridge/Bundle/BridgeNewsBundle/Entity/BridgeNewsArticle.php

namespace Bridge\Bundle\BridgeNewsBundle\Entity;

use Doctrine\ORM\Mapping as ORM;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\Config;
use Oro\Bundle\EntityExtendBundle\Entity\ExtendEntityInterface;
use Oro\Bundle\EntityExtendBundle\Entity\ExtendEntityTrait;

#[ORM\Entity]
#[ORM\Table(name: 'bridge_news_article')]
#[ORM\HasLifecycleCallbacks]
#[Config(
    routeName: 'bridge_news_article_index',
    routeView: 'bridge_news_article_view',
    routeUpdate: 'bridge_news_article_update',
    defaultValues: [
        'entity' => ['icon' => 'fa-newspaper-o'],
        'security' => ['type' => 'ACL', 'group_name' => ''],
        'dataaudit' => ['auditable' => true],
    ]
)]
class BridgeNewsArticle implements ExtendEntityInterface
{
    use ExtendEntityTrait;

    #[ORM\Id]
    #[ORM\GeneratedValue(strategy: 'AUTO')]
    #[ORM\Column(type: 'integer')]
    private ?int $id = null;

    #[ORM\Column(name: 'title', type: 'string', length: 255)]
    private string $title = '';

    #[ORM\Column(name: 'content', type: 'text', nullable: true)]
    private ?string $content = null;

    #[ORM\Column(name: 'published_at', type: 'datetime', nullable: true)]
    private ?\DateTimeInterface $publishedAt = null;

    #[ORM\Column(name: 'enabled', type: 'boolean', options: ['default' => true])]
    private bool $enabled = true;

    #[ORM\Column(name: 'created_at', type: 'datetime')]
    private ?\DateTimeInterface $createdAt = null;

    #[ORM\Column(name: 'updated_at', type: 'datetime')]
    private ?\DateTimeInterface $updatedAt = null;

    public function getId(): ?int { return $this->id; }

    public function getTitle(): string { return $this->title; }
    public function setTitle(string $title): self { $this->title = $title; return $this; }

    public function getContent(): ?string { return $this->content; }
    public function setContent(?string $content): self { $this->content = $content; return $this; }

    public function getPublishedAt(): ?\DateTimeInterface { return $this->publishedAt; }
    public function setPublishedAt(?\DateTimeInterface $publishedAt): self { $this->publishedAt = $publishedAt; return $this; }

    public function isEnabled(): bool { return $this->enabled; }
    public function setEnabled(bool $enabled): self { $this->enabled = $enabled; return $this; }

    public function getCreatedAt(): ?\DateTimeInterface { return $this->createdAt; }
    public function getUpdatedAt(): ?\DateTimeInterface { return $this->updatedAt; }

    // WHY #[ORM\PrePersist] / #[ORM\PreUpdate]: These lifecycle callbacks
    // automatically set timestamps without requiring the caller to do so.
    // Requires #[ORM\HasLifecycleCallbacks] on the class.
    #[ORM\PrePersist]
    public function prePersist(): void
    {
        $this->createdAt = new \DateTime('now', new \DateTimeZone('UTC'));
        $this->updatedAt = new \DateTime('now', new \DateTimeZone('UTC'));
    }

    #[ORM\PreUpdate]
    public function preUpdate(): void
    {
        $this->updatedAt = new \DateTime('now', new \DateTimeZone('UTC'));
    }

    public function __toString(): string
    {
        return $this->title;
    }
}
```

### File 4: Migration

```php
<?php
// src/Bridge/Bundle/BridgeNewsBundle/Migrations/Schema/v1_0/CreateBridgeNewsArticle.php

namespace Bridge\Bundle\BridgeNewsBundle\Migrations\Schema\v1_0;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;

class CreateBridgeNewsArticle implements Migration
{
    public function up(Schema $schema, QueryBag $queries): void
    {
        $table = $schema->createTable('bridge_news_article');

        $table->addColumn('id', 'integer', ['autoincrement' => true]);
        $table->addColumn('title', 'string', ['length' => 255]);
        $table->addColumn('content', 'text', ['notnull' => false]);
        $table->addColumn('published_at', 'datetime', ['notnull' => false]);
        $table->addColumn('enabled', 'boolean', ['default' => true]);
        $table->addColumn('created_at', 'datetime', ['notnull' => true]);
        $table->addColumn('updated_at', 'datetime', ['notnull' => true]);

        $table->setPrimaryKey(['id']);
        $table->addIndex(['enabled'], 'idx_bridge_news_article_enabled');
        $table->addIndex(['published_at'], 'idx_bridge_news_article_published_at');
    }
}
```

### File 5: services.yml

```yaml
# src/Bridge/Bundle/BridgeNewsBundle/Resources/config/services.yml
services:
    _defaults:
        autowire: true
        autoconfigure: true
        public: false

    Bridge\Bundle\BridgeNewsBundle\:
        resource: '../../*'
        exclude: '../../{DependencyInjection,Resources}'
```

### File 6: routing.yml

```yaml
# src/Bridge/Bundle/BridgeNewsBundle/Resources/config/oro/routing.yml
BridgeNewsBundle_admin:
    resource:     "@BridgeNewsBundle/Controller/Admin/"
    type:         attribute
    prefix:       /admin
```

---

## Bundle Naming Conventions (Braskem Project)

| Prefix | Namespace | Purpose |
|--------|-----------|---------|
| `Bridge\Bundle\Bridge*Bundle` | `src/Bridge/Bundle/` | Domain logic, entities, integrations |
| `Aaxis\Bundle\Aaxis*Bundle` | `src/Aaxis/Bundle/` | Infrastructure, messaging, React dashboard |

**WHY separate prefixes:** Bridge bundles contain business logic specific to the Braskem commerce portal. Aaxis bundles contain platform infrastructure (async messaging, storage, dashboard). The separation makes ownership and responsibility clear.

---

## Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Missing `bundles.yml` | Bundle never loads; entities, routes, and services are invisible | Create `Resources/config/oro/bundles.yml` with the bundle class name |
| Namespace mismatch in `composer.json` | `Class not found` errors | Ensure PSR-4 namespace maps to the correct `src/` path |
| Forgetting `cache:clear` after changes | Old DI container used; new services not found | Always run `php bin/console cache:clear` |
| Bundle class name doesn't match filename | PHP fatal error on load | Class name and file name must be identical |
| Services not auto-wired | Null injection or `ServiceNotFoundException` | Check `_defaults.autowire: true` and that the class is in the scanned path |
| Routes not visible | 404 on new controller actions | Check `routing.yml` exists in `Resources/config/oro/` and cache is cleared |

---

## Next Steps

1. Create the entity: see `../entities/create-entities.md`
2. Create the migration: see `../entities/migrations.md`
3. Build the CRUD controller and templates: see `../entities/crud-and-routing.md`
4. Configure navigation and grids: see `../configuration-reference/navigation.md` and `../entities/datagrids.md`
