# OroCommerce Feature Toggle System — Complete Developer Reference

> Source: https://doc.oroinc.com/master/backend/feature-toggle/

## AGENT QUERY HINTS

Use this file when asked about:
- "How do I create a feature toggle in Oro?"
- "How do I enable/disable a feature?"
- "How do I check if a feature is enabled in PHP?"
- "How do I check feature state in Twig?"
- "What is features.yml?"
- "How do I attach routes/commands/entities to a feature?"
- "How do I create a feature voter?"
- "What is FeatureChecker?"
- "How do I make a service aware of a feature toggle?"
- "How do I conditionally show a form field based on a feature?"
- "What decision strategies are available (affirmative, consensus, unanimous)?"

---

## 1. Concept

The **OroFeatureToggleBundle** provides a centralized way to enable or disable application features at the scope level (global, per-website, per-user). Features gate:

- Routes
- System configuration groups and fields
- Console commands
- Cron jobs
- Entities / API resources
- Workflows, processes, operations
- Dashboard and sidebar widgets
- Navigation items, placeholder items
- Message queue topics

A feature is defined in `features.yml` and may be tied to a system configuration toggle that end-users can flip in the admin UI.

---

## 2. Defining a Feature — `features.yml`

Create the file at:
```
src/<Bundle>/Resources/config/oro/features.yml
```

### Minimal Example

```yaml
features:
    bridge_vm2_integration:
        label: bridge.feature.vm2_integration.label
```

### Full Example with All Supported Keys

```yaml
features:
    bridge_vm2_integration:
        # Required: translation key for the feature's display name
        label: bridge.feature.vm2_integration.label

        # Optional: longer description shown in admin UI
        description: bridge.feature.vm2_integration.description

        # Optional: system config key (boolean) that acts as the on/off switch.
        # When this config value is false, the feature is disabled.
        toggle: bridge_integration.vm2_enabled

        # Optional: features that must ALSO be enabled for this one to work
        dependencies:
            - bridge_base_integration

        # Routes disabled when feature is off (returns 404)
        routes:
            - bridge_customer_catalog_index
            - bridge_customer_catalog_view

        # System configuration groups and fields hidden when feature is off
        configuration:
            - bridge_integration_vm2_group
            - bridge_integration.vm2_api_url

        # Workflows disabled with feature
        workflows:
            - bridge_vm2_order_flow

        # Processes disabled with feature
        processes:
            - bridge_vm2_sync_process

        # Operations disabled with feature
        operations:
            - bridge_vm2_manual_sync

        # Entity classes available via JSON:API only when feature is on
        api_resources:
            - Bridge\Bundle\BridgeIntegrationBundle\Entity\Vm2SyncLog

        # Entity classes available via storefront JSON:API only when feature is on
        frontend_api_resources:
            - Bridge\Bundle\BridgeIntegrationBundle\Entity\Vm2SyncLog

        # Console commands disabled when feature is off
        commands:
            - oro:cron:bridge-vm2
            - oro:cron:bridge-customer

        # Entity classes hidden from admin entity management when feature is off
        entities:
            - Bridge\Bundle\BridgeIntegrationBundle\Entity\Vm2CatalogItem

        # Dashboard widget names disabled with feature
        dashboard_widgets:
            - vm2_sync_status_widget

        # Sidebar widget names disabled with feature
        sidebar_widgets:
            - bridge_vm2_sidebar_widget

        # Cron commands skipped by oro:cron when feature is off
        cron_jobs:
            - oro:cron:bridge-vm2
            - oro:cron:bridge-customer

        # Navigation menu items hidden when feature is off
        navigation_items:
            - application_menu.bridge_tab.vm2_catalog_list

        # Placeholder items hidden when feature is off
        placeholder_items:
            - bridge_vm2_manual_sync_button

        # MQ topics disabled when feature is off (messages are not processed)
        mq_topics:
            - bridge.integration.sync_vm2_catalog
```

**View the full configuration reference:**
```bash
php bin/console oro:feature-toggle:config:dump-reference
```

---

## 3. Linking to a System Configuration Toggle

To let admins flip the feature via the UI, create a boolean system config setting and reference it in `toggle:`.

### Step 1 — Define the config option in `DependencyInjection/Configuration.php`

```php
<?php
namespace Bridge\Bundle\BridgeIntegrationBundle\DependencyInjection;

use Oro\Bundle\ConfigBundle\DependencyInjection\SettingsBuilder;
use Symfony\Component\Config\Definition\Builder\TreeBuilder;
use Symfony\Component\Config\Definition\ConfigurationInterface;

class Configuration implements ConfigurationInterface
{
    public function getConfigTreeBuilder(): TreeBuilder
    {
        $treeBuilder = new TreeBuilder('bridge_integration');

        SettingsBuilder::append($treeBuilder->getRootNode(), [
            'vm2_enabled' => [
                'value' => true,      // Default: on
                'type'  => 'boolean',
            ],
        ]);

        return $treeBuilder;
    }
}
```

### Step 2 — Show it in the UI via `system_configuration.yml`

```yaml
# Resources/config/oro/system_configuration.yml
system_configuration:
    fields:
        bridge_integration.vm2_enabled:
            type: checkbox
            options:
                label: bridge.config.vm2_enabled.label
            priority: 10

    groups:
        bridge_integration_vm2_group:
            title: bridge.config.group.vm2.title
            icon: fa-exchange

    tree:
        system_configuration:
            platform:
                children:
                    bridge_integration_vm2_group:
                        children:
                            - bridge_integration.vm2_enabled
```

### Step 3 — Reference it in `features.yml`

```yaml
features:
    bridge_vm2_integration:
        label: bridge.feature.vm2_integration.label
        toggle: bridge_integration.vm2_enabled
```

**WHY this pattern:** The admin can enable/disable the feature from **System > Configuration** without touching code or redeploying. The `FeatureChecker` reads the toggle value through the config manager.

---

## 4. Checking Feature State in PHP

### Injecting FeatureChecker

```php
<?php
namespace Bridge\Bundle\BridgeIntegrationBundle\Service\VM2;

use Oro\Bundle\FeatureToggleBundle\Checker\FeatureChecker;

class Vm2ApiService
{
    public function __construct(
        private readonly FeatureChecker $featureChecker,
    ) {}

    public function syncCatalog(): int
    {
        // Check if the whole feature is enabled
        if (!$this->featureChecker->isFeatureEnabled('bridge_vm2_integration')) {
            return 0;
        }

        // ... do the sync
        return 100;
    }

    public function isRouteAccessible(string $route): bool
    {
        // Check if a specific resource type is enabled
        return $this->featureChecker->isResourceEnabled($route, 'routes');
    }
}
```

### `FeatureChecker` API

| Method | Signature | Returns |
|---|---|---|
| `isFeatureEnabled` | `isFeatureEnabled(string $feature, $scopeIdentifier = null): bool` | `true` if enabled |
| `isResourceEnabled` | `isResourceEnabled(string $resource, string $type, $scopeIdentifier = null): bool` | `true` if resource's feature is enabled |

**Resource types for `isResourceEnabled`:**
`routes`, `commands`, `entities`, `api_resources`, `frontend_api_resources`, `workflows`, `processes`, `operations`, `dashboard_widgets`, `sidebar_widgets`, `cron_jobs`, `navigation_items`, `placeholder_items`, `mq_topics`

### Making a Service "Feature-Aware" with `FeatureToggleableInterface`

For services that should automatically be skipped when their feature is off, use the trait pattern:

```php
<?php
namespace Bridge\Bundle\BridgeIntegrationBundle\Form\Extension;

use Oro\Bundle\FeatureToggleBundle\Checker\FeatureCheckerHolderTrait;
use Oro\Bundle\FeatureToggleBundle\Checker\FeatureToggleableInterface;
use Symfony\Component\Form\AbstractTypeExtension;
use Symfony\Component\Form\FormBuilderInterface;

/**
 * Adds VM2 catalog fields to the product form when the VM2 integration is enabled.
 */
class ProductVm2FormExtension extends AbstractTypeExtension implements FeatureToggleableInterface
{
    use FeatureCheckerHolderTrait; // Provides $this->isFeaturesEnabled()

    public static function getExtendedTypes(): iterable
    {
        return ['oro_product'];
    }

    public function buildForm(FormBuilderInterface $builder, array $options): void
    {
        // isFeaturesEnabled() checks the features declared in the service tag
        if (!$this->isFeaturesEnabled()) {
            return;
        }

        $builder->add('vm2CatalogId', /* ... */);
    }
}
```

Register with the feature tag:

```yaml
# Resources/config/services.yml
services:
    Bridge\Bundle\BridgeIntegrationBundle\Form\Extension\ProductVm2FormExtension:
        tags:
            - { name: form.type_extension }
            - { name: oro_featuretogle.feature, feature: bridge_vm2_integration }
```

**WHY the tag approach:** The DI compiler pass automatically injects `FeatureChecker` into any service tagged with `oro_featuretogle.feature`. The `isFeaturesEnabled()` method checks all features listed in tags on that service.

### Feature Checking in Console Commands

```php
<?php
use Oro\Bundle\FeatureToggleBundle\Checker\FeatureCheckerAwareInterface;
use Oro\Bundle\FeatureToggleBundle\Checker\FeatureCheckerHolderTrait;

class BridgeVm2Command extends Command implements FeatureCheckerAwareInterface
{
    use FeatureCheckerHolderTrait;

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        if (!$this->featureChecker->isResourceEnabled($this->getName(), 'commands')) {
            $output->writeln('<comment>VM2 integration feature is disabled. Skipping.</comment>');
            return Command::SUCCESS;
        }

        // ... proceed
        return Command::SUCCESS;
    }
}
```

---

## 5. Checking Feature State in Twig

```twig
{# Check a named feature #}
{% if feature_enabled('bridge_vm2_integration') %}
    <a href="{{ path('bridge_customer_catalog_index') }}">VM2 Catalog</a>
{% endif %}

{# Check a specific resource (e.g., a route) #}
{% if feature_resource_enabled('bridge_customer_catalog_index', 'routes') %}
    {# show link #}
{% endif %}

{# With scope identifier (e.g., per-website) #}
{% if feature_enabled('bridge_vm2_integration', app.request.get('website_id')) %}
    {# show for this website only #}
{% endif %}
```

---

## 6. Checking Feature State in Layouts

```yaml
layout:
    actions:
        - '@add':
            id: vm2_catalog_block
            parentId: page_content
            blockType: datagrid
            options:
                grid_name: vm2-catalog-grid
                visible: '=data["feature"].isFeatureEnabled("bridge_vm2_integration")'
```

---

## 7. Checking Feature State in Workflows / Processes / Operations

```yaml
# In workflow.yml or process.yml
conditions:
    '@feature_enabled':
        feature: bridge_vm2_integration
        scope_identifier: $.website

# Check a specific resource type
conditions:
    '@feature_resource_enabled':
        resource: 'bridge_customer_catalog_index'
        resource_type: 'routes'
        scope_identifier: $.websiteId
```

---

## 8. Extending Feature Configuration

Add custom keys to the `features.yml` schema by implementing `ConfigurationExtensionInterface`:

```php
<?php
namespace Bridge\Bundle\BridgeIntegrationBundle\Config;

use Oro\Bundle\FeatureToggleBundle\Configuration\ConfigurationExtensionInterface;
use Symfony\Component\Config\Definition\Builder\NodeBuilder;

/**
 * Adds 'bridge_processors' as a valid key in features.yml.
 * Allows listing custom processor class names that are feature-gated.
 */
class BridgeFeatureConfigExtension implements ConfigurationExtensionInterface
{
    public function extendConfigurationTree(NodeBuilder $node): void
    {
        $node
            ->arrayNode('bridge_processors')
                ->prototype('scalar')
                ->end()
            ->end();
    }
}
```

```yaml
# Resources/config/services.yml
services:
    Bridge\Bundle\BridgeIntegrationBundle\Config\BridgeFeatureConfigExtension:
        tags:
            - { name: oro_feature.config_extension }
```

Now you can use `bridge_processors:` in any feature definition in `features.yml`.

---

## 9. Custom Feature Voters

Voters let you implement arbitrary logic for determining if a feature is on or off. Each voter returns one of three constants: `FEATURE_ENABLED`, `FEATURE_DISABLED`, or `FEATURE_ABSTAIN`.

```php
<?php
namespace Bridge\Bundle\BridgeIntegrationBundle\Voter;

use Oro\Bundle\FeatureToggleBundle\Checker\Voter\VoterInterface;

/**
 * Disables the VM2 integration feature after the go-live date,
 * since Edge integration is a temporary migration feature.
 */
class EdgeIntegrationExpiryVoter implements VoterInterface
{
    public function __construct(
        private readonly \DateTimeInterface $goLiveDate,
    ) {}

    public function vote(string $feature, $scopeIdentifier = null): int
    {
        if ($feature !== 'bridge_edge_integration') {
            return self::FEATURE_ABSTAIN; // Not our concern
        }

        if (new \DateTimeImmutable() > $this->goLiveDate) {
            return self::FEATURE_DISABLED;
        }

        return self::FEATURE_ABSTAIN; // Let other voters decide
    }
}
```

```yaml
# Resources/config/services.yml
services:
    Bridge\Bundle\BridgeIntegrationBundle\Voter\EdgeIntegrationExpiryVoter:
        arguments:
            - '@bridge_integration.go_live_date'
        tags:
            - { name: oro_featuretogle.voter }
```

---

## 10. Decision Strategies

When multiple voters disagree, a **decision strategy** resolves the conflict.

| Strategy | Behavior |
|---|---|
| `unanimous` **(default)** | Feature is enabled only if ALL voters say ENABLED (or ABSTAIN) |
| `affirmative` | Feature is enabled if ANY voter says ENABLED |
| `consensus` | Feature is enabled if more voters say ENABLED than DISABLED |

Configure globally:

```yaml
# Resources/config/oro/app.yml
oro_featuretoggle:
    strategy: affirmative
    allow_if_all_abstain: true          # Default: false
    allow_if_equal_granted_denied: false # Default: true (consensus only)
```

Configure per feature:

```yaml
features:
    bridge_vm2_integration:
        label: bridge.feature.vm2_integration.label
        strategy: affirmative
        allow_if_all_abstain: true
```

**WHY `unanimous` is the default:** It is the most conservative and safe option. If any voter says "no", the feature is off. Use `affirmative` for features that should be on unless explicitly blocked.

---

## 11. Scope-Aware Feature Checking

Features can be evaluated per scope (e.g., per-website). Pass the scope identifier as the second argument:

```php
// Check for a specific website
$website = $this->websiteManager->getCurrentWebsite();
$enabled = $this->featureChecker->isFeatureEnabled('bridge_vm2_integration', $website);
```

```twig
{# Twig — pass the website entity or its ID #}
{% if feature_enabled('bridge_vm2_integration', current_website) %}
    ...
{% endif %}
```

This enables per-website feature flags when the system config scope is set to "website".
