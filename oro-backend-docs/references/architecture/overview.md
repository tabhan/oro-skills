# OroCommerce Architecture Overview

> Source: https://doc.oroinc.com/master/backend/architecture/tech-stack/ | https://doc.oroinc.com/master/backend/architecture/structure/ | https://doc.oroinc.com/master/backend/architecture/framework/ | https://doc.oroinc.com/master/backend/architecture/differences/ | https://doc.oroinc.com/master/backend/architecture/bundle-less-structure/

---

## AGENT QUERY HINTS

This file answers questions like:
- "What technology stack does OroCommerce use?"
- "What version of PHP/Symfony does Oro use?"
- "What databases does OroCommerce support?"
- "How does OroCommerce differ from standard Symfony?"
- "What is the directory structure of an Oro application?"
- "How does message queuing work in Oro?"
- "How does caching work in OroCommerce?"
- "What search engines are supported?"
- "How does OroCommerce handle routing differently from Symfony?"
- "How does ACL work in OroCommerce?"
- "What is OroPlatformBundle and OroDistributionBundle?"

---

## Technology Stack

### Client-Side Architecture

OroCommerce uses a client-server architecture. The frontend communicates with the server via HTTP and WebSocket connections.

**Supported browsers:** Firefox, Chrome, Edge, Safari (all latest versions)

**Frontend characteristics:**
- Responsive and adaptive UI (mobile-friendly)
- WebSocket connections for real-time features (notifications, alerts)
- Supports API clients: custom apps, mobile apps, ERP systems, ETL services

### Server-Side Components

#### PHP Application Core

The Oro PHP application is built on:
- **Symfony Framework** — dependency injection, event system, routing, security
- **Doctrine ORM** — object-relational mapping and database abstraction (DBAL)
- **Oro Doctrine Extensions** — additional database functions extending Doctrine (PostgreSQL-focused)

WHY: Symfony provides a mature, well-tested foundation. Doctrine decouples the application from the raw database, enabling schema migrations and testability. Oro extends both rather than replacing them, preserving upgrade paths.

#### Web Server / PHP Runtime

- **Apache or Nginx** — HTTP request handling and proxying
- **PHP-FPM** — PHP request processing

#### Database (RDBMS)

| Edition | Supported Database |
|---------|--------------------|
| CE (Community) | PostgreSQL |
| EE (Enterprise) | PostgreSQL |

WHY: OroCommerce is PostgreSQL-only. The Oro Doctrine Extensions library adds PostgreSQL-specific functions (e.g., `CAST`, array operations). Do NOT attempt MySQL/MariaDB; they are unsupported.

#### File Storage

Two configurable storage types:

| Type | Contents |
|------|----------|
| Private | Attachments, import/export files, protected media cache |
| Public | Product images, sitemaps, directly web-accessible content |

File storage backends are configurable (local filesystem, S3-compatible, etc.) via Gaufrette or Flysystem adapters.

#### Session Storage

PHP sessions preserve user state between requests. Can be configured to use Redis or filesystem.

#### Message Queue (Async Processing)

| Edition | Available MQ Backends |
|---------|----------------------|
| CE | Proprietary DB-based MQ |
| EE | Proprietary DB-based MQ + RabbitMQ |

The MQ consumer runs as a daemon:
```bash
php bin/console oro:message-queue:consume --env=prod
```

WHY: Heavy operations (imports, email sending, search index updates) are offloaded to async jobs. Without the consumer running, many operations silently queue but never execute — including admin panel login in some configurations.

The consumer scales horizontally across multiple servers (EE + RabbitMQ).

#### Search Engine

| Edition | Available Search Backends |
|---------|--------------------------|
| CE | DB full-text search |
| EE | DB full-text search + Elasticsearch |

WHY: Elasticsearch provides better relevance ranking and performance for large catalogs (EE). CE uses PostgreSQL full-text search as a simpler alternative.

#### Cache Storage

Three distinct cache layers exist:

| Cache Type | Backend | Purpose |
|------------|---------|---------|
| Data Cache | Redis (with Sentinel or Cluster) | Application data caching (entities, queries) |
| System Cache | Filesystem + PHP OPcache | Framework/DI container compilation artifacts |
| Content Cache | Redis | HTML page caching alongside PHP-FPM + Nginx |

WHY: These layers are separated because they have different invalidation patterns. System cache rarely changes; data cache changes with content edits; content cache changes on every page modification.

#### Deployment Models

- **Single-server**: All services on one machine (development, small deployments)
- **Multi-instance**: Load balancers + multiple app servers + shared services (production, high-load)

---

## Application Structure

### Repository Types (GitHub)

Oro organizes code into three repository categories:

| Type | Description | Examples |
|------|-------------|---------|
| Applications | Complete installable solutions | OroCommerce, OroCRM, OroPlatform |
| Packages | Reusable feature modules (Composer dependencies) | `oro/commerce`, `oro/platform` |
| Components | Generic libraries (no Oro-specific dependencies) | `oro/doctrine-extensions` |

WHY: This separation allows packages to be versioned and reused independently. Applications pin specific package versions via `composer.lock`.

### Root Directory Layout

```
project-root/
├── bin/            # Executable scripts (bin/console)
├── config/         # Application-level configuration (services, packages, routes)
├── public/         # Web server document root
│   ├── bundles/    # Static assets published from bundle Resources/public/
│   ├── css/        # Compiled stylesheets
│   ├── js/         # Compiled JavaScript
│   ├── images/     # Pre-processed media
│   ├── media/      # Application media cache
│   ├── uploads/    # User-submitted files
│   └── index.php   # Application entry point (front controller)
├── src/            # Custom application code (YOUR customizations go here)
├── templates/      # Custom Twig template overrides
├── translations/   # Custom translation file overrides
├── var/            # Generated runtime files (never commit contents)
│   ├── cache/      # Compiled DI container, routes, Twig templates
│   ├── data/       # Private adapter files (attachments, imports/exports)
│   ├── logs/       # Application log output
│   └── sessions/   # User session data
└── vendor/         # Composer-installed dependencies (never edit directly)
```

### File System Permissions

| Resource | Permission | Owner | Group |
|----------|------------|-------|-------|
| Directories | 755 | deployer user | www-data |
| Files | 644 | deployer user | www-data |
| Writable dirs (`var/`, `public/media/`) | — | www-data | www-data |

WHY: The web server (www-data) needs write access to cache, logs, sessions, and media. The owner is a non-www-data user to prevent the web server from modifying source code.

### Package Directory Layout

Oro packages (installable via Composer) contain:

```
package-root/
├── composer.json           # Metadata, dependencies, autoloading
├── LICENSE
├── README.md
├── UPGRADE.md              # Upgrade notes between versions
├── CHANGELOG.md
├── phpunit.xml.dist        # Test configuration template
└── src/
    ├── Bundle/             # Symfony bundles
    ├── Bridge/             # Integration bridges
    └── Component/          # Framework-agnostic libraries
```

---

## Application Framework Principles

### Foundation: Symfony + Oro Extensions

OroCommerce extends Symfony through two key bundles:

- **OroPlatformBundle** — Core platform services, event system, configuration management
- **OroDistributionBundle** — Bundle auto-discovery, extension marketplace integration

Everything in OroCommerce is Symfony-compatible. Symfony knowledge transfers directly; Oro adds conventions on top.

### Core Architectural Patterns

#### HTTP Request Flow

Standard Symfony HTTP kernel flow applies. Requests pass through:
1. Web server (Nginx/Apache)
2. PHP-FPM → `public/index.php`
3. Symfony Kernel → Event dispatcher (`kernel.request`)
4. Router → Controller
5. Controller → Response
6. Event dispatcher (`kernel.response`) → Web server

#### Inversion of Control (IoC) / Dependency Injection

All services are defined in the DI container. Oro follows Symfony's service container conventions:
- Services declared in `Resources/config/services.yml` (or `.xml`)
- Constructor injection preferred
- Service IDs follow snake_case convention (e.g., `oro_catalog.manager.category`)

#### Event-Driven Architecture

OroCommerce uses Symfony's event dispatcher extensively. Events are the primary customization hook.

To list all registered events:
```bash
php bin/console debug:event-dispatcher
```

#### Bundle System

All functionality is encapsulated in Symfony bundles. Bundles are the unit of feature delivery in Oro.

---

## Key Differences from Standard Symfony

### 1. Automatic Bundle Discovery

**Standard Symfony:** Bundles must be manually registered in `config/bundles.php` (Symfony 4+) or `AppKernel.php` (Symfony 3).

**OroCommerce:** Bundles are auto-discovered. The Oro kernel scans `src/` and `vendor/` for any bundle containing:
```
Resources/config/oro/bundles.yml
```

The `bundles.yml` file declares the bundle class:
```yaml
# Resources/config/oro/bundles.yml
bundles:
  - Acme\Bundle\DemoBundle\AcmeDemoBundle
```

With optional load priority (LOWER number = loads FIRST):
```yaml
bundles:
  - { name: Acme\Bundle\DemoBundle\AcmeDemoBundle, priority: 10 }
```

WHY: With dozens of Oro packages each containing multiple bundles, manual registration would be unmanageable. Auto-discovery eliminates boilerplate and makes package installation via Composer work automatically.

GOTCHA: Priority is counterintuitive — priority 10 loads BEFORE priority 100.

### 2. Automatic Routing Discovery

**Standard Symfony:** Routes must be imported in the application's `config/routes.yaml`.

**OroCommerce:** Routing is auto-discovered from:
```
Resources/config/oro/routing.yml
```

If this file exists in a bundle, routes are registered automatically — no application-level import needed.

WHY: Same reason as bundle discovery — reduces boilerplate when many bundles each define routes.

### 3. Simplified Access Control Lists (ACL)

**Standard Symfony:** ACL implementation requires working with ACL providers, object identities, access control entries (ACEs), and mask builders — complex and verbose.

**OroCommerce:** ACLs are declared directly on controller actions using PHP attributes:

```php
use Oro\Bundle\SecurityBundle\Attribute\Acl;
use Oro\Bundle\SecurityBundle\Attribute\AclAncestor;

// Define a new ACL resource:
#[Acl(
    id: 'acme_demo.blog_post_view',
    type: 'entity',
    class: 'Acme\Bundle\DemoBundle\Entity\BlogPost',
    permission: 'VIEW'
)]
public function indexAction(): Response
{
    // ...
}

// Reuse an existing ACL on another action:
#[AclAncestor('acme_demo.blog_post_view')]
public function viewAction(int $id): Response
{
    // ...
}
```

ACL `type` values:
- `entity` — permission on a Doctrine entity class
- `action` — permission on a non-entity action (e.g., "run report")

WHY: The `#[Acl]` attribute approach integrates ACL definition with the code that needs it, making it easier to audit and maintain access controls.

### 4. Extension Marketplace Integration

**Standard Symfony:** Extensions are Composer packages installed via CLI.

**OroCommerce:** Via `OroDistributionBundle`, administrators can install extensions through the admin UI (Oro Extensions Store) without CLI access. Under the hood, Composer is still used.

WHY: OroCommerce targets non-developer administrators who need to add features without SSH access.

---

## Bundle-less Structure (Oro 7.0+)

Starting from OroPlatform v5.1, you can organize OroPlatform-based application code within **Symfony bundles** OR **plain directories** (bundle-less structure). The bundle-less structure follows Symfony best practices and lowers the entry level for new developers.

**When to use bundle-less:**
- Application-level customizations
- Single feature or small extension
- Internal project customization

**When to use bundle-based:**
- Reusable package for distribution
- Multiple related features with shared code
- Need to share code across Oro applications

For detailed migration guide and configuration, see `bundle-less-structure.md`.

---

## Customization Strategies

### Golden Rule: Never Modify Vendor Code

All customizations go in `src/` — never in `vendor/`. Modifying vendor code breaks on `composer update`.

### Strategy 1: Source Code Customization

Place custom bundles in `src/`:
```
src/
└── Acme/
    └── Bundle/
        └── DemoBundle/
```

Register the bundle:
```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/bundles.yml
bundles:
  - Acme\Bundle\DemoBundle\AcmeDemoBundle
```

### Strategy 2: Service Decoration

Replace a core service's behavior without modifying it:
```yaml
# services.yml
acme_demo.decorated_price_calculator:
    class: Acme\Bundle\DemoBundle\Service\CustomPriceCalculator
    decorates: oro_pricing.calculator.product_price
    arguments:
        - '@acme_demo.decorated_price_calculator.inner'
```

WHY: Decoration preserves the original service (available as `.inner`) while substituting the implementation. Survives Oro upgrades because vendor code is untouched.

### Strategy 3: Dependency Injection Tags

Register custom implementations of extension points:
```yaml
# services.yml
acme_demo.payment_method_provider:
    class: Acme\Bundle\DemoBundle\Method\Provider\CustomPaymentProvider
    tags:
      - { name: oro_payment.payment_method_provider }
```

Common DI tags in OroCommerce:
- `oro_payment.payment_method_provider` — payment methods
- `oro_shipping.shipping_method_provider` — shipping methods
- `kernel.event_listener` — event listeners
- `oro_datagrid.extension` — datagrid extensions

### Strategy 4: Event Listeners

Hook into the application flow:
```yaml
# services.yml
acme_demo.event_listener.order_created:
    class: Acme\Bundle\DemoBundle\EventListener\OrderCreatedListener
    tags:
      - { name: kernel.event_listener, event: oro_order.order.created, method: onOrderCreated }
```

### Strategy 5: Configuration-Based Customization

Extend features via YAML configuration files inside your bundle's `Resources/config/oro/`:

| File | What it customizes |
|------|--------------------|
| `system_configuration.yml` | Admin system config UI options |
| `workflows.yml` | Business process workflows |
| `datagrids.yml` | Data grid definitions and columns |
| `navigation.yml` | Admin menu structure |
| `placeholders.yml` | Twig template injection points |

### Strategy 6: Twig Placeholders

Inject content into vendor templates without overriding them:
```yaml
# Resources/config/oro/placeholders.yml
placeholders:
    product_view_additional_info:
        items:
            acme_custom_product_section:
                template: '@AcmeDemo/Product/custom_section.html.twig'
                order: 100
```

WHY: Overriding entire Twig templates breaks when the core template changes. Placeholders inject into specific named slots, reducing upgrade friction.

### Strategy 7: Database Schema Migrations

Use `MigrationBundle` to modify the schema:
```php
// Migrations/Schema/v1_0/AddCustomerRatingColumn.php
class AddCustomerRatingColumn implements Migration
{
    public function up(Schema $schema, QueryBag $queries): void
    {
        $table = $schema->getTable('oro_customer');
        $table->addColumn('rating', 'integer', ['notnull' => false]);
    }
}
```

WHY: Migrations are version-controlled and run sequentially, making schema changes reproducible across environments.

### UI Customization (Avoid for Production)

The back-office provides UI tools for entity and workflow management. However:
> Results of UI customization are stored in the database, not as code.

This means UI changes cannot be version-controlled or reliably promoted to production via deployment pipelines. Use source code customization instead.

---

## Development Workflow Reference

```bash
# After schema/entity changes:
php bin/console oro:platform:update --force

# Clear application cache:
php bin/console cache:clear

# Build frontend assets:
php bin/console oro:assets:build
php bin/console assets:install --symlink

# Discover and debug events:
php bin/console debug:event-dispatcher

# Discover and debug routes:
php bin/console debug:router

# Discover and debug services:
php bin/console debug:container
```
