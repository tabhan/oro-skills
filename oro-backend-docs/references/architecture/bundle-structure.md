# OroCommerce Bundle Structure

> Source: https://doc.oroinc.com/master/backend/architecture/structure/

---

## AGENT QUERY HINTS

This file answers questions like:
- "How do I create a new bundle in OroCommerce?"
- "What is the directory structure inside an Oro bundle?"
- "Where do I put controllers, entities, services in a bundle?"
- "What files are required for an Oro bundle to be discovered?"
- "What is bundles.yml and where does it go?"
- "How does the DependencyInjection extension work in Oro?"
- "How do I register routes in an Oro bundle?"
- "What goes in Resources/config/oro/?"
- "How does bundle priority work?"
- "How do I verify my bundle is loaded?"
- "What is the difference between Bundle, Bridge, and Component in Oro?"
- "What Oro-specific YAML configuration files exist in a bundle?"

---

## Core Concepts

### Bundle vs Bridge vs Component

Oro organizes reusable code into three types:

| Type | Description | Location |
|------|-------------|----------|
| **Bundle** | Symfony bundle — integrates with the DI container, routing, events, and templates | `src/Acme/Bundle/DemoBundle/` |
| **Bridge** | Lightweight glue connecting two independent bundles without creating a hard dependency | `src/Acme/Bridge/SymfonyTwig/` |
| **Component** | Framework-agnostic PHP library, no Symfony/Oro dependency | `src/Acme/Component/Math/` |

WHY: Bridges let you integrate optional packages without forcing every project to install both. Components can be unit-tested in isolation without bootstrapping the Symfony container.

---

## Bundle Auto-Discovery: How Oro Finds Your Bundle

Unlike standard Symfony (where you register bundles in `config/bundles.php`), OroCommerce automatically discovers bundles.

### Discovery Mechanism

The Oro kernel scans `src/` and `vendor/` for directories containing:
```
Resources/config/oro/bundles.yml
```

If this file exists, the bundle is loaded automatically after `cache:clear`.

### bundles.yml Format

Minimal registration:
```yaml
# Resources/config/oro/bundles.yml
bundles:
  - Acme\Bundle\DemoBundle\AcmeDemoBundle
```

With explicit load priority:
```yaml
bundles:
  - { name: Acme\Bundle\DemoBundle\AcmeDemoBundle, priority: 255 }
```

CRITICAL PRIORITY NOTE: **Lower priority value = loads EARLIER**.
- Priority 0 loads before priority 100
- Priority 255 is a common default (loads late, after platform bundles)
- Platform bundles typically use priority 0-100
- Custom application bundles should use 200+ to load after platform bundles

WHY: Bundles loaded earlier can be overridden by bundles loaded later (e.g., for service decoration and compiler pass ordering). Platform bundles need to be established before custom bundles extend them.

---

## Complete Bundle Directory Structure

### Minimum Required Structure

```
src/Acme/Bundle/DemoBundle/
├── AcmeDemoBundle.php                          # Bundle class (REQUIRED)
├── DependencyInjection/
│   └── AcmeDemoExtension.php                   # DI loader (loads services.yml)
└── Resources/
    └── config/
        ├── services.yml                         # Service definitions
        └── oro/
            └── bundles.yml                      # Oro bundle registration (REQUIRED)
```

### Full Production Bundle Structure

```
src/Acme/Bundle/DemoBundle/
│
├── AcmeDemoBundle.php                          # Bundle entry point
│
├── DependencyInjection/
│   ├── AcmeDemoExtension.php                   # Loads config files into DI container
│   └── Compiler/
│       └── CustomCompilerPass.php              # DI compiler passes (optional)
│
├── Controller/
│   ├── Api/
│   │   └── Rest/
│   │       └── ProductController.php           # REST API controllers
│   └── ProductController.php                   # Standard web controllers
│
├── Entity/
│   └── Product.php                             # Doctrine entities
│
├── Repository/
│   └── ProductRepository.php                   # Doctrine repositories
│
├── Form/
│   ├── Type/
│   │   └── ProductType.php                     # Symfony form types
│   └── Extension/
│       └── ProductFormExtension.php            # Extensions to existing forms
│
├── EventListener/
│   └── OrderCreatedListener.php                # Event listeners
│
├── Model/
│   └── ProductModel.php                        # Non-entity domain models
│
├── Provider/
│   └── ProductProvider.php                     # Data providers (tagged services)
│
├── Handler/
│   └── ProductHandler.php                      # Request/form handlers
│
├── Manager/
│   └── ProductManager.php                      # Business logic managers
│
├── Migrations/
│   └── Schema/
│       └── v1_0/
│           └── CreateProductTable.php          # Database schema migrations
│
├── Placeholder/
│   └── PlaceholderFilter.php                   # Template placeholder filters
│
├── Twig/
│   └── ProductExtension.php                    # Custom Twig functions/filters
│
└── Resources/
    ├── config/
    │   ├── services.yml                        # Primary service definitions
    │   ├── controllers.yml                     # Controller service definitions
    │   ├── form.yml                            # Form type service definitions
    │   └── oro/
    │       ├── bundles.yml                     # Bundle registration (auto-discovery)
    │       ├── routing.yml                     # Route auto-discovery
    │       ├── datagrids.yml                   # Datagrid definitions
    │       ├── system_configuration.yml        # Admin system config UI
    │       ├── workflows.yml                   # Workflow definitions
    │       ├── navigation.yml                  # Admin menu/navigation
    │       ├── placeholders.yml                # Twig placeholder slots
    │       ├── acls.yml                        # ACL resource definitions
    │       └── api.yml                         # API resource configuration
    ├── public/
    │   ├── js/                                 # JavaScript assets
    │   └── css/                                # Stylesheet assets
    ├── translations/
    │   ├── messages.en.yml                     # English translations
    │   └── messages.pt_BR.yml                  # Portuguese (BR) translations
    └── views/
        └── Product/
            ├── index.html.twig                 # List view
            └── view.html.twig                  # Detail view
```

---

## Core Bundle Files Explained

### 1. Bundle Main Class

Every bundle requires a main PHP class extending Symfony's `Bundle`:

```php
// src/Acme/Bundle/DemoBundle/AcmeDemoBundle.php
namespace Acme\Bundle\DemoBundle;

use Symfony\Component\HttpKernel\Bundle\Bundle;

class AcmeDemoBundle extends Bundle
{
}
```

The class name must end in `Bundle` and match the directory name.

For bundles with compiler passes, override `build()`:

```php
use Symfony\Component\DependencyInjection\ContainerBuilder;

class AcmeDemoBundle extends Bundle
{
    #[\Override]
    public function build(ContainerBuilder $container): void
    {
        parent::build($container);
        $container->addCompilerPass(new Compiler\CustomCompilerPass());
    }
}
```

WHY: Compiler passes run during container compilation and allow you to manipulate service definitions — for example, collecting all services tagged with a custom tag and passing them to a registry.

### 2. DependencyInjection Extension

The DI extension is responsible for loading the bundle's service definitions into the container:

```php
// src/Acme/Bundle/DemoBundle/DependencyInjection/AcmeDemoExtension.php
namespace Acme\Bundle\DemoBundle\DependencyInjection;

use Symfony\Component\Config\FileLocator;
use Symfony\Component\DependencyInjection\ContainerBuilder;
use Symfony\Component\DependencyInjection\Loader\YamlFileLoader;
use Symfony\Component\HttpKernel\DependencyInjection\Extension;

class AcmeDemoExtension extends Extension
{
    #[\Override]
    public function load(array $configs, ContainerBuilder $container): void
    {
        $loader = new YamlFileLoader(
            $container,
            new FileLocator(__DIR__ . '/../Resources/config')
        );

        // Load all config files needed by this bundle:
        $loader->load('services.yml');
        $loader->load('form.yml');
        $loader->load('controllers.yml');
    }
}
```

Naming convention: `[BundleName]Extension` in namespace `[BundleNamespace]\DependencyInjection`.

WHY: Symfony automatically locates this class by convention (strips `Bundle` suffix, appends `Extension` in `DependencyInjection\`). Without it, `services.yml` is NOT loaded into the container.

### 3. Services Configuration

```yaml
# Resources/config/services.yml
services:
    # Service with constructor injection:
    acme_demo.manager.product:
        class: Acme\Bundle\DemoBundle\Manager\ProductManager
        arguments:
            - '@doctrine'
            - '@oro_security.token_accessor'

    # Service tagged as an event listener:
    acme_demo.listener.order_created:
        class: Acme\Bundle\DemoBundle\EventListener\OrderCreatedListener
        arguments:
            - '@acme_demo.manager.product'
        tags:
            - { name: kernel.event_listener, event: oro_order.order.created, method: onOrderCreated }

    # Service registered as a payment method provider:
    acme_demo.payment_method_provider:
        class: Acme\Bundle\DemoBundle\Method\Provider\CustomPaymentProvider
        tags:
            - { name: oro_payment.payment_method_provider }
```

Service ID naming convention: `[bundle_alias].[type].[name]`
- Bundle alias: `acme_demo` (from `AcmeDemoBundle` → snake_case without `bundle`)
- Type: `manager`, `listener`, `provider`, `handler`, `form`, `twig`
- Name: descriptive name of what the service does

---

## Resources/config/oro/ — Oro-Specific Configuration Files

This subdirectory is the heart of Oro's convention-over-configuration system. Files here are auto-discovered.

### bundles.yml — Bundle Registration

```yaml
bundles:
  - { name: Acme\Bundle\DemoBundle\AcmeDemoBundle, priority: 255 }
```

Required for auto-discovery. Without this, the bundle does not load.

### routing.yml — Route Auto-Discovery

```yaml
# Resources/config/oro/routing.yml
acme_demo_product:
    resource: '@AcmeDemoBundle/Controller/ProductController.php'
    type: attribute
    prefix: /acme/product

# Or import a separate routing file:
acme_demo_api:
    resource: '@AcmeDemoBundle/Resources/config/oro/api_routing.yml'
    prefix: /api
```

WHY: Placing routing here means it is discovered automatically. You do NOT need to add imports to the application's `config/routes/` directory.

### datagrids.yml — Data Grid Definitions

```yaml
# Resources/config/oro/datagrids.yml
datagrids:
    acme-product-grid:
        source:
            type: orm
            query:
                select:
                    - p.id
                    - p.name
                    - p.sku
                from:
                    - { table: Acme\Bundle\DemoBundle\Entity\Product, alias: p }
        columns:
            name:
                label: acme_demo.product.name.label
            sku:
                label: acme_demo.product.sku.label
        sorters:
            columns:
                name:
                    data_name: p.name
        filters:
            columns:
                name:
                    type: string
                    data_name: p.name
```

### system_configuration.yml — Admin System Config

```yaml
# Resources/config/oro/system_configuration.yml
system_configuration:
    groups:
        acme_demo_settings:
            title: acme_demo.system_configuration.groups.settings.title
    fields:
        acme_demo.enable_feature:
            data_type: boolean
            type: Oro\Bundle\ConfigBundle\Form\Type\ConfigCheckbox
            options:
                label: acme_demo.system_configuration.fields.enable_feature.label
    tree:
        system_configuration:
            platform:
                children:
                    acme_demo_settings:
                        children:
                            - acme_demo.enable_feature
```

### navigation.yml — Admin Menu

```yaml
# Resources/config/oro/navigation.yml
navigation:
    menu_config:
        items:
            acme_demo_product_list:
                label: acme_demo.menu.product_list
                route: acme_demo_product_index
                extras:
                    routes: [acme_demo_product_*]
        tree:
            application_menu:
                children:
                    acme_demo_product_list: ~
```

### placeholders.yml — Template Injection Points

```yaml
# Resources/config/oro/placeholders.yml
placeholders:
    items:
        acme_product_custom_section:
            template: '@AcmeDemo/Product/custom_section.html.twig'
    placeholders:
        product_view_additional_info:
            items:
                acme_product_custom_section:
                    order: 100
```

WHY: Placeholders allow injecting content into vendor templates without overriding them. This is the preferred method over template inheritance when you only need to add content to one slot.

### acls.yml — ACL Resource Definitions

```yaml
# Resources/config/oro/acls.yml
acls:
    acme_demo_product_view:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Product
        group_name: commerce
        label: acme_demo.acl.product.view
```

---

## Entity Organization and YAML Mapping

OroCommerce uses YAML-based Doctrine mapping (not annotations on entities by default in Oro bundles, though attributes are supported in PHP 8+).

### Entity Class

```php
// Entity/Product.php
namespace Acme\Bundle\DemoBundle\Entity;

class Product
{
    private ?int $id = null;
    private string $name = '';
    private string $sku = '';

    // Getters and setters...
}
```

### YAML Mapping (Traditional Oro Style)

```yaml
# Resources/config/doctrine/Product.orm.yml
Acme\Bundle\DemoBundle\Entity\Product:
    type: entity
    table: acme_product
    id:
        id:
            type: integer
            generator:
                strategy: AUTO
    fields:
        name:
            type: string
            length: 255
        sku:
            type: string
            length: 64
            unique: true
```

WHY: YAML mapping keeps entity classes clean (no annotation imports) and separates persistence concerns from domain logic.

---

## Naming Conventions Summary

| Artifact | Convention | Example |
|----------|------------|---------|
| Bundle class | `[Vendor][Name]Bundle` | `AcmeDemoBundle` |
| Bundle namespace | `Vendor\Bundle\NameBundle` | `Acme\Bundle\DemoBundle` |
| DI Extension | `[Name]Extension` in `DependencyInjection\` | `AcmeDemoExtension` |
| Service IDs | `[bundle_alias].[type].[name]` | `acme_demo.manager.product` |
| Route names | `[bundle_alias]_[resource]_[action]` | `acme_demo_product_index` |
| Translation keys | `[bundle_alias].[domain].[key]` | `acme_demo.product.name.label` |
| Table names | `[vendor_prefix]_[entity_name]` | `acme_product` |
| Config parameters | `[bundle_alias].[param]` | `acme_demo.enable_feature` |

---

## Bundle Registration Verification

After creating a bundle, verify it is discovered:

```bash
# 1. Clear the cache (required after any structural changes):
php bin/console cache:clear

# 2. Verify the bundle appears in the kernel:
php bin/console debug:container --parameter=kernel.bundles --format=json | grep AcmeDemoBundle

# Expected output:
# "AcmeDemoBundle": "Acme\\Bundle\\DemoBundle\\AcmeDemoBundle"

# 3. Verify services are loaded:
php bin/console debug:container acme_demo

# 4. Verify routes are loaded:
php bin/console debug:router | grep acme_demo
```

---

## Common Patterns from Oro Platform Bundles

### Service Decoration (Override Core Behavior)

```yaml
# services.yml
acme_demo.decorated_price_list_manager:
    class: Acme\Bundle\DemoBundle\Manager\CustomPriceListManager
    decorates: oro_pricing.manager.price_list
    arguments:
        - '@acme_demo.decorated_price_list_manager.inner'
        - '@doctrine'
```

The original service is available as `.inner`. This survives Oro upgrades because vendor code is never touched.

### Tagged Service Collection (Registry Pattern)

Define a registry service that collects all tagged services at compile time:

```yaml
# services.yml — the registry:
acme_demo.provider_registry:
    class: Acme\Bundle\DemoBundle\Registry\ProviderRegistry
    # Providers are injected via compiler pass or Symfony's !tagged_iterator

# A provider:
acme_demo.provider.default:
    class: Acme\Bundle\DemoBundle\Provider\DefaultProvider
    tags:
        - { name: acme_demo.provider }
```

```php
// DependencyInjection/Compiler/ProviderRegistryPass.php
class ProviderRegistryPass implements CompilerPassInterface
{
    public function process(ContainerBuilder $container): void
    {
        if (!$container->has('acme_demo.provider_registry')) {
            return;
        }

        $registry = $container->findDefinition('acme_demo.provider_registry');
        $providers = $container->findTaggedServiceIds('acme_demo.provider');

        foreach ($providers as $id => $tags) {
            $registry->addMethodCall('addProvider', [new Reference($id)]);
        }
    }
}
```

### Loading Bundle Configuration at Container Compile Time

```php
// DependencyInjection/AcemeDemoExtension.php
public function load(array $configs, ContainerBuilder $container): void
{
    $configuration = new Configuration();
    $config = $this->processConfiguration($configuration, $configs);

    $container->setParameter('acme_demo.some_param', $config['some_param']);

    $loader = new YamlFileLoader($container, new FileLocator(__DIR__ . '/../Resources/config'));
    $loader->load('services.yml');
}
```

---

## Key Oro Platform Bundles Reference

The following core Oro bundles are commonly referenced when building custom bundles:

| Bundle | Alias | Purpose |
|--------|-------|---------|
| `OroPlatformBundle` | `oro_platform` | Core platform services, kernel extensions |
| `OroEntityBundle` | `oro_entity` | Entity management, extended fields, virtual fields |
| `OroEntityConfigBundle` | `oro_entity_config` | Entity/field configuration metadata |
| `OroEntityExtendBundle` | `oro_entity_extend` | Extend entities with custom fields |
| `OroSecurityBundle` | `oro_security` | ACL, token accessor, permission system |
| `OroDataGridBundle` | `oro_datagrid` | Grid definitions, filters, sorters |
| `OroUIBundle` | `oro_ui` | Twig extensions, placeholders, layout |
| `OroConfigBundle` | `oro_config` | System configuration management |
| `OroTranslationBundle` | `oro_translation` | Translation management |
| `OroActionBundle` | `oro_action` | Operations and action groups |
| `OroWorkflowBundle` | `oro_workflow` | Workflow engine |
| `OroApiBundle` | `oro_api` | JSON:API and REST API layer |
| `OroPricingBundle` | `oro_pricing` | Price lists, calculation, strategies |
| `OroOrderBundle` | `oro_order` | Order management |
| `OroCustomerBundle` | `oro_customer` | Customer/account management |
| `OroProductBundle` | `oro_product` | Product catalog |
| `OroCheckoutBundle` | `oro_checkout` | Checkout process/workflow |
| `OroInventoryBundle` | `oro_inventory` | Inventory management |
| `OroShippingBundle` | `oro_shipping` | Shipping method integration |
| `OroPaymentBundle` | `oro_payment` | Payment method integration |
| `OroTaxBundle` | `oro_tax` | Tax calculation |
| `OroCatalogBundle` | `oro_catalog` | Product categories |
| `OroWebsiteBundle` | `oro_website` | Multi-website management |
| `OroLocaleBundle` | `oro_locale` | Localization, currencies, number formats |

---

## Checklist: Creating a New Custom Bundle

- [ ] Create bundle directory under `src/[Vendor]/Bundle/[Name]Bundle/`
- [ ] Create `AcmeDemoBundle.php` extending `Symfony\Component\HttpKernel\Bundle\Bundle`
- [ ] Create `DependencyInjection/AcmeDemoExtension.php` loading `services.yml`
- [ ] Create `Resources/config/services.yml` (even if empty initially)
- [ ] Create `Resources/config/oro/bundles.yml` with bundle class and priority
- [ ] Run `php bin/console cache:clear`
- [ ] Verify with `php bin/console debug:container --parameter=kernel.bundles --format=json | grep YourBundle`
- [ ] Add `Resources/config/oro/routing.yml` if the bundle has controllers
- [ ] Add translations to `Resources/translations/messages.en.yml`
- [ ] Add entity YAML mapping files in `Resources/config/doctrine/` if using entities
- [ ] Run `php bin/console oro:platform:update --force` after adding entities
