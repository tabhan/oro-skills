# OroCommerce services.yml — Symfony DI in Oro Context

> Source: https://doc.oroinc.com/master/backend/configuration/yaml/bundles-config/

## AGENT QUERY HINTS

Use this file when:
- "How do I register a service in Oro?"
- "What tag do I use for a form type extension / datagrid extension / voter?"
- "How do I listen to an Oro event?"
- "What is the oro_featuretogle.feature tag?"
- "How do I decorate/override a vendor service?"
- "What are the most common Oro-specific DI tags?"
- "How do I inject the doctrine entity manager / config manager / security?"
- "How do I register an import/export strategy or processor?"

---

## Overview

`services.yml` is a standard Symfony DI file loaded from each bundle's
`DependencyInjection/Extension.php`. In Oro, it is the primary place to:

1. Register your own services with Symfony's container.
2. Tag services so Oro subsystems (navigation, security, datagrids, etc.) can
   discover them automatically.
3. Decorate or alias vendor services.
4. Configure compiler passes.

**File location per bundle:**
```
YourBundle/Resources/config/services.yml
```

Loaded in `DependencyInjection/YourBundleExtension.php`:
```php
public function load(array $configs, ContainerBuilder $container): void
{
    $loader = new YamlFileLoader($container, new FileLocator(__DIR__ . '/../Resources/config'));
    $loader->load('services.yml');
    // Often split into multiple files for large bundles:
    $loader->load('form_types.yml');
    $loader->load('importexport.yml');
}
```

---

## Core Service Definition Patterns

### 1. Basic Service (FQCN as ID — preferred)

```yaml
services:
    Acme\DemoBundle\Service\ProductSync:
        arguments:
            - '@doctrine.orm.entity_manager'
            - '@oro_config.manager'
            - '%acme_demo.api_url%'
```

### 2. Service with Calls and Properties

```yaml
services:
    Acme\DemoBundle\Service\OrderImporter:
        arguments:
            - '@Acme\DemoBundle\Repository\OrderRepository'
        calls:
            - [ setLogger, [ '@logger' ] ]
        properties:
            batchSize: '%acme_demo.import_batch_size%'
        tags:
            - { name: monolog.logger, channel: acme_demo }
```

### 3. Abstract / Parent Service

```yaml
services:
    # Abstract base — never instantiated directly
    acme_demo.abstract_sync:
        abstract: true
        arguments:
            - '@doctrine'
            - '@logger'

    Acme\DemoBundle\Service\ProductSync:
        parent: acme_demo.abstract_sync
        arguments:
            $configManager: '@oro_config.manager'
```

### 4. Service Alias (shorthand ID)

```yaml
services:
    Acme\DemoBundle\Service\ProductSync: ~   # auto-wired

    # Short alias for injection by string ID
    acme_demo.product_sync:
        alias: Acme\DemoBundle\Service\ProductSync
        public: true
```

### 5. Decorating a Vendor Service

```yaml
services:
    Acme\DemoBundle\Decorator\CustomEmailSender:
        decorates: oro_email.email_sender
        arguments:
            - '@.inner'   # the original service
            - '@logger'
```

---

## Auto-Wiring and Auto-Configuration

Oro bundles increasingly use Symfony's autowiring. Enable for a directory:

```yaml
services:
    _defaults:
        autowire: true
        autoconfigure: true

    Acme\DemoBundle\:
        resource: '../../'
        exclude:
            - '../../DependencyInjection/'
            - '../../Entity/'
            - '../../Migrations/'
            - '../../Tests/'
```

---

## Common Oro-Specific Service Tags

### Security Tags

| Tag | Purpose | Required attributes |
|-----|---------|-------------------|
| `oro_security.voter` | Custom ACL voter | — |
| `security.voter` | Symfony standard voter | — |
| `oro_security.acl_helper` | ACL helper registration | — |
| `oro_featuretogle.feature` | Hide service behind feature flag | `feature` (string) |

```yaml
services:
    Acme\DemoBundle\Security\ProductVoter:
        tags:
            - { name: oro_security.voter }

    Acme\DemoBundle\Service\PremiumFeature:
        tags:
            - { name: oro_featuretogle.feature, feature: acme_demo_premium }
```

### Datagrid Tags

| Tag | Purpose | Required attributes |
|-----|---------|-------------------|
| `oro_datagrid.extension` | Adds behavior to all grids | — |
| `oro_datagrid.datasource` | Registers a datasource type | `type` |

```yaml
services:
    Acme\DemoBundle\Datagrid\Extension\ProductGridExtension:
        tags:
            - { name: oro_datagrid.extension }
```

### Form Tags

| Tag | Purpose | Required attributes |
|-----|---------|-------------------|
| `form.type` | Register a form type | — |
| `form.type_extension` | Extend an existing form type | `extended_type` |
| `oro_form.extension` | Oro-enhanced form type extension | `extended_type` |

```yaml
services:
    Acme\DemoBundle\Form\Type\ProductType:
        tags:
            - { name: form.type }

    Acme\DemoBundle\Form\Extension\ProductTypeExtension:
        tags:
            - name: form.type_extension
              extended_type: Oro\Bundle\ProductBundle\Form\Type\ProductType
```

### Navigation Tags

| Tag | Purpose | Required attributes |
|-----|---------|-------------------|
| `oro_navigation.item.builder` | Programmatic menu builder | `alias` |

```yaml
services:
    Acme\DemoBundle\Menu\ProductMenuBuilder:
        tags:
            - { name: oro_navigation.item.builder, alias: application_menu }
```

A menu builder class must implement `Knp\Menu\ItemInterface` building logic.

### Event Tags

| Tag | Purpose | Required attributes |
|-----|---------|-------------------|
| `kernel.event_listener` | Listen to Symfony/Oro events | `event`, `method` |
| `kernel.event_subscriber` | Subscribe to multiple events | — |
| `oro_workflow.changes.subscriber` | Workflow change subscriber | — |

```yaml
services:
    Acme\DemoBundle\EventListener\OrderListener:
        tags:
            - name: kernel.event_listener
              event: oro.order.create.after
              method: onOrderCreate

    Acme\DemoBundle\EventSubscriber\ProductSubscriber:
        tags:
            - { name: kernel.event_subscriber }
```

### Import/Export Tags

| Tag | Purpose | Required attributes |
|-----|---------|-------------------|
| `oro_importexport.strategy` | Import strategy | `alias` |
| `oro_importexport.processor` | Import/export processor | `type`, `entity`, `alias` |
| `oro_importexport.template_fixture` | Provides template data | `entity` |

```yaml
services:
    Acme\DemoBundle\ImportExport\Strategy\ProductImportStrategy:
        parent: oro_importexport.strategy.configurable_add_or_replace
        tags:
            - { name: oro_importexport.strategy, alias: acme_demo_product_import }

    Acme\DemoBundle\ImportExport\Processor\ProductImportProcessor:
        parent: oro_importexport.processor.import
        calls:
            - [setStrategy, ['@Acme\DemoBundle\ImportExport\Strategy\ProductImportStrategy']]
        tags:
            - name: oro_importexport.processor
              type: import
              entity: Acme\DemoBundle\Entity\Product
              alias: acme_demo_product.import
            - name: oro_importexport.processor
              type: import_validation
              entity: Acme\DemoBundle\Entity\Product
              alias: acme_demo_product.import_validation
```

### Entity Config Tags

| Tag | Purpose | Required attributes |
|-----|---------|-------------------|
| `oro_entity_config.attribute_type` | Custom attribute type | `type` |
| `oro_entity.virtual_field_provider` | Virtual field provider | `scope` |
| `oro_entity.virtual_relation_provider` | Virtual relation provider | `scope` |

```yaml
services:
    Acme\DemoBundle\Provider\ProductVirtualFieldProvider:
        tags:
            - { name: oro_entity.virtual_field_provider, scope: acme_demo }
```

### Integration Tags

| Tag | Purpose | Required attributes |
|-----|---------|-------------------|
| `oro.integration.channel_type` | Integration channel type | `type` |
| `oro.integration.transport` | Integration transport | `type`, `channel_type` |
| `oro.integration.connector` | Integration connector | `type`, `channel_type` |
| `oro.integration.two_way_sync_strategy` | Sync conflict strategy | `type` |

```yaml
services:
    Acme\DemoBundle\Integration\Channel\ExternalChannel:
        tags:
            - { name: oro.integration.channel_type, type: acme_external }

    Acme\DemoBundle\Integration\Connector\ProductConnector:
        tags:
            - { name: oro.integration.connector, type: product, channel_type: acme_external }
```

### Search Tags

| Tag | Purpose | Required attributes |
|-----|---------|-------------------|
| `oro_search.extension.search_filter_builder` | Custom search filter | `type` |
| `oro_api.query.criteria_connector` | API query criteria | `operator_type`, `data_type` |

### Cron / Message Queue Tags

| Tag | Purpose | Required attributes |
|-----|---------|-------------------|
| `oro_cron.command` | Register a cron command | `cronExpression` |
| `oro_message_queue.client.message_processor` | Message processor | `topicName` |

```yaml
services:
    Acme\DemoBundle\Async\SyncProductsProcessor:
        tags:
            - name: oro_message_queue.client.message_processor
              topicName: acme_demo.sync_products

    Acme\DemoBundle\Command\SyncProductsCommand:
        tags:
            - name: oro_cron.command
              cronExpression: '0 2 * * *'
```

### Twig / UI Tags

| Tag | Purpose | Required attributes |
|-----|---------|-------------------|
| `twig.extension` | Register a Twig extension | — |
| `oro_ui.configuration_provider` | Provide UI config data | — |
| `oro_dashboard.widget_data_provider` | Provide dashboard widget data | — |

```yaml
services:
    Acme\DemoBundle\Twig\ProductExtension:
        tags:
            - { name: twig.extension }
```

### Validation Tags

| Tag | Purpose | Required attributes |
|-----|---------|-------------------|
| `validator.constraint_validator` | Custom constraint validator | `alias` |

```yaml
services:
    Acme\DemoBundle\Validator\UniqueSKUValidator:
        tags:
            - { name: validator.constraint_validator, alias: acme_demo_unique_sku }
```

---

## Commonly Injected Oro Services

| Service ID | Purpose |
|-----------|---------|
| `@doctrine` | Doctrine registry (get entity managers, repos) |
| `@doctrine.orm.entity_manager` | Default ORM entity manager |
| `@oro_config.manager` | Read/write system configuration values |
| `@oro_security.acl_helper` | Apply ACL filtering to Doctrine queries |
| `@oro_security.token_accessor` | Get current user/organization |
| `@oro_entity.entity_name_resolver` | Resolve entity display names |
| `@oro_entity.doctrine_helper` | Entity manager helper utilities |
| `@event_dispatcher` | Dispatch and listen to events |
| `@logger` | PSR-3 logger |
| `@translator` | Symfony translator |
| `@router` | URL generator |
| `@request_stack` | Current HTTP request |
| `@oro_featuretogle.checker.feature_checker` | Check if feature is enabled |
| `@oro_message_queue.client.message_producer` | Send messages to queue |
| `@oro_importexport.handler.export` | Trigger export jobs |
| `@oro_importexport.handler.import` | Trigger import jobs |

---

## Compiler Passes

Used in `DependencyInjection/YourBundleExtension.php` or `YourBundle.php` to
manipulate the container at build time:

```php
// In YourBundle.php
class AcmeDemoBundle extends Bundle
{
    public function build(ContainerBuilder $container): void
    {
        parent::build($container);
        $container->addCompilerPass(new RegisterProductTypesPass());
    }
}
```

Common Oro compiler pass patterns:
- Collecting tagged services into a registry (chain/factory pattern)
- Setting parameters based on configuration
- Replacing service definitions conditionally

```php
// Example compiler pass
class RegisterProductTypesPass implements CompilerPassInterface
{
    public function process(ContainerBuilder $container): void
    {
        if (!$container->has('acme_demo.product_type_registry')) {
            return;
        }

        $registry = $container->findDefinition('acme_demo.product_type_registry');
        $taggedServices = $container->findTaggedServiceIds('acme_demo.product_type');

        foreach ($taggedServices as $id => $tags) {
            foreach ($tags as $attributes) {
                $registry->addMethodCall('addType', [
                    new Reference($id),
                    $attributes['type'],
                ]);
            }
        }
    }
}
```

---

## Feature Flags

Oro's feature toggle system can hide services, routes, and navigation behind
a feature flag configured in System > Configuration:

**1. Register the feature in `features.yml`:**
```yaml
features:
    acme_demo_premium:
        label: acme.demo.feature.premium.label
        toggle: acme_demo.premium_enabled    # system config key
```

**2. Tag services with the feature:**
```yaml
services:
    Acme\DemoBundle\Service\PremiumService:
        tags:
            - { name: oro_featuretogle.feature, feature: acme_demo_premium }
```

**3. Check feature programmatically:**
```php
$this->featureChecker->isFeatureEnabled('acme_demo_premium')
```

---

## Parameters

Define bundle-level parameters at the top of `services.yml` or in a separate `parameters.yml`:

```yaml
parameters:
    acme_demo.api_url: 'https://api.example.com'
    acme_demo.import_batch_size: 100
    acme_demo.supported_locales:
        - en
        - pt_BR

services:
    Acme\DemoBundle\Service\ApiClient:
        arguments:
            $apiUrl: '%acme_demo.api_url%'
            $batchSize: '%acme_demo.import_batch_size%'
```

Override parameters in `config/services.yaml` (app level) without changing bundle code.

---

## Anti-Patterns to Avoid

| Anti-pattern | Problem | Correct approach |
|-------------|---------|-----------------|
| `public: true` on every service | Breaks DI encapsulation | Only make public if accessed from `$container->get()` (legacy) |
| Injecting `@service_container` | Service locator anti-pattern | Inject specific services |
| Hard-coded entity manager `@doctrine.orm.entity_manager` | Breaks multi-EM setups | Use `@doctrine` registry and call `getManagerForClass()` |
| Not tagging services | Oro won't discover the service | Always tag subsystem-specific services |
| Duplicate service IDs across bundles | Last bundle silently wins | Use FQCN as ID to avoid collisions |
