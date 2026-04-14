# OroCommerce system_configuration.yml — Complete Reference

> Source: https://doc.oroinc.com/master/backend/configuration/yaml/system-configuration/

## AGENT QUERY HINTS

Use this file when:
- "How do I add a setting to System > Configuration in Oro?"
- "What is the system_configuration.yml schema?"
- "How do I read a system config value in PHP?"
- "How do I read a system config value in Twig?"
- "What is the difference between fields, groups, tree in system configuration?"
- "How do I make a system setting available via API?"
- "What form types can I use for system config fields?"
- "How does Oro store system configuration values?"
- "What is the api_tree in system_configuration.yml?"
- "How do I scope a config value to organization / website / user?"

---

## Overview

`system_configuration.yml` lives at `Resources/config/oro/system_configuration.yml`
in each bundle. It is discovered and deep-merged by `OroConfigBundle`.

The file controls the **System > Configuration** admin panel — the UI where
administrators set application-wide settings like API URLs, feature toggles,
notification preferences, display options, etc.

**Root node:** `system_configuration`

---

## Full Schema Reference

```yaml
system_configuration:

    # ──────────────────────────────────────────────
    # fields: define individual configuration keys
    # ──────────────────────────────────────────────
    fields:
        # Key format: bundle_prefix.config_key
        # This becomes the config "key" used in PHP/Twig retrieval.
        acme_demo.feature_enabled:
            data_type: boolean            # Storage type: boolean | string | array
            type: Oro\Bundle\ConfigBundle\Form\Type\ConfigCheckbox  # form type class
            search_type: text             # optional; for config search indexing
            options:                      # passed directly to the form type
                label: acme.demo.system_config.feature_enabled.label
                tooltip: acme.demo.system_config.feature_enabled.tooltip
                required: false

        acme_demo.api_endpoint:
            data_type: string
            type: Symfony\Component\Form\Extension\Core\Type\TextType
            options:
                label: acme.demo.system_config.api_endpoint.label
                constraints:
                    - NotBlank: ~
                    - Url: ~

        acme_demo.max_results:
            data_type: string            # always string for choice fields
            type: Symfony\Component\Form\Extension\Core\Type\ChoiceType
            options:
                label: acme.demo.system_config.max_results.label
                choices:
                    acme.demo.system_config.max_results.choice.10: '10'
                    acme.demo.system_config.max_results.choice.25: '25'
                    acme.demo.system_config.max_results.choice.50: '50'
                constraints:
                    - NotBlank: ~

        acme_demo.notification_emails:
            data_type: array
            type: Oro\Bundle\ConfigBundle\Form\Type\ConfigFileType
            options:
                label: acme.demo.system_config.notification_emails.label

    # ──────────────────────────────────────────────
    # groups: logical containers for fields in the UI
    # ──────────────────────────────────────────────
    groups:
        acme_demo_integration_settings:
            title: acme.demo.system_config.group.integration.label
            icon: fa-plug                     # Font Awesome icon (optional)
            page_reload: false                # force full reload after save

        acme_demo_notification_settings:
            title: acme.demo.system_config.group.notification.label
            icon: fa-bell

    # ──────────────────────────────────────────────
    # tree: position fields/groups in the config UI
    # ──────────────────────────────────────────────
    tree:
        # Root: system_configuration (the System > Configuration menu)
        system_configuration:
            # Top-level sections (tabs in left sidebar)
            platform:
                children:
                    general_setup:                 # existing Oro branch
                        children:
                            acme_demo_integration_settings:    # our group
                                children:
                                    - acme_demo.feature_enabled
                                    - acme_demo.api_endpoint
                                    - acme_demo.max_results
                            acme_demo_notification_settings:
                                children:
                                    - acme_demo.notification_emails

    # ──────────────────────────────────────────────
    # api_tree: expose fields via REST API
    # ──────────────────────────────────────────────
    api_tree:
        acme_demo_integration:            # logical grouping name for API
            acme_demo.feature_enabled: ~
            acme_demo.api_endpoint: ~
        acme_demo_notification:
            acme_demo.notification_emails: ~
```

---

## Parameters Reference

### `fields.*` Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `data_type` | string | yes | — | Storage type: `boolean`, `string`, `array` |
| `type` | string | yes | — | Fully qualified form type class name |
| `search_type` | string | no | — | Search indexing type for config search |
| `options` | map | no | — | Passed directly to the form type constructor |
| `options.label` | string | no | — | Translation key for field label |
| `options.tooltip` | string | no | — | Translation key for help tooltip |
| `options.required` | boolean | no | `false` | Whether field is required |
| `options.constraints` | list | no | — | Symfony validation constraints |
| `options.choices` | map | no | — | For choice types: label => value |

### `groups.*` Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `title` | string | yes | — | Translation key for group heading |
| `icon` | string | no | — | Font Awesome icon name |
| `page_reload` | boolean | no | `false` | Force full page reload after save |

### `tree.*` Node Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `children` | list/map | yes | — | Child group/field keys |
| `priority` | integer | no | `0` | Merge priority; higher = merged first |

### `api_tree.*` Parameters

The `api_tree` section is a flat map of logical group names to field keys:
```yaml
api_tree:
    my_group:
        my.config.key: ~     # ~ = include with no extra options
```

---

## Standard Oro Tree Branches

Place your groups under these existing branches to integrate into the standard config UI:

| Branch path | Location in UI |
|-------------|---------------|
| `system_configuration > platform > general_setup` | System > General Setup |
| `system_configuration > platform > look_and_feel` | System > Look and Feel |
| `system_configuration > platform > email_settings` | System > Email Configuration |
| `system_configuration > platform > integrations` | System > Integrations |
| `system_configuration > commerce > catalog` | Commerce > Catalog |
| `system_configuration > commerce > sales` | Commerce > Sales |
| `system_configuration > commerce > orders` | Commerce > Orders |
| `system_configuration > commerce > shipping` | Commerce > Shipping |
| `system_configuration > commerce > payment` | Commerce > Payment |
| `system_configuration > commerce > customer` | Commerce > Customer |
| `system_configuration > crm` | CRM configuration |

---

## Data Types

| `data_type` | PHP storage | When to use |
|-------------|------------|-------------|
| `boolean` | `bool` | Feature toggles, on/off switches |
| `string` | `string` | Text, URLs, API keys, choice values |
| `array` | `array` | Lists of values (email lists, JSON, etc.) |

**Important:** Even numeric or enum values should use `data_type: string` unless
the value is a true boolean. Oro stores config values serialized and the type
only controls UI validation, not DB storage format.

---

## Common Form Types

| Form Type | Package | Use case |
|-----------|---------|---------|
| `Oro\Bundle\ConfigBundle\Form\Type\ConfigCheckbox` | OroConfigBundle | Boolean toggle |
| `Symfony\Component\Form\Extension\Core\Type\TextType` | Symfony | Single-line text |
| `Symfony\Component\Form\Extension\Core\Type\TextareaType` | Symfony | Multi-line text |
| `Symfony\Component\Form\Extension\Core\Type\ChoiceType` | Symfony | Dropdown select |
| `Symfony\Component\Form\Extension\Core\Type\IntegerType` | Symfony | Integer input |
| `Oro\Bundle\FormBundle\Form\Type\OroEncodedPlaceholderPasswordType` | OroFormBundle | Masked password |
| `Oro\Bundle\LocaleBundle\Form\Type\LanguageType` | OroLocaleBundle | Language picker |
| `Oro\Bundle\LocaleBundle\Form\Type\TimezoneType` | OroLocaleBundle | Timezone picker |
| `Oro\Bundle\EmailBundle\Form\Type\EmailTemplateSelectType` | OroEmailBundle | Email template picker |

---

## Reading Config Values in PHP

### In a Service (Recommended)

```php
use Oro\Bundle\ConfigBundle\Config\ConfigManager;

class MyService
{
    public function __construct(
        private readonly ConfigManager $configManager
    ) {}

    public function doSomething(): void
    {
        // Read a value (current scope: system or website or organization)
        $apiUrl = $this->configManager->get('acme_demo.api_endpoint');

        // Read with explicit scope
        $value = $this->configManager->get(
            'acme_demo.feature_enabled',
            false,           // use parent scope if not set locally
            false,           // return full object (not just value)
            $scopeIdentifier // e.g. $website object or null for global
        );

        // Write a value
        $this->configManager->set('acme_demo.api_endpoint', 'https://api.example.com');
        $this->configManager->flush();
    }
}
```

Service injection:
```yaml
services:
    Acme\DemoBundle\Service\MyService:
        arguments:
            - '@oro_config.manager'
```

### Using the Global Config Manager

```php
// Scope-aware manager (respects current website/org scope):
$this->configManager->get('acme_demo.feature_enabled');

// Always read global (system) scope:
$globalManager = $this->configManager->getScopeManager('global');
$value = $globalManager->getSettingValue('acme_demo.feature_enabled');
```

---

## Reading Config Values in Twig

```twig
{# Read a system config value #}
{% set apiUrl = oro_config_value('acme_demo.api_endpoint') %}

{# Conditional rendering #}
{% if oro_config_value('acme_demo.feature_enabled') %}
    <div class="premium-widget">...</div>
{% endif %}

{# With default fallback #}
{% set maxResults = oro_config_value('acme_demo.max_results') ?? '25' %}
```

The `oro_config_value()` Twig function reads from the current scope (website or
global, depending on context).

---

## Scope Hierarchy

Oro supports layered configuration scopes. Values cascade from most-specific to least:

```
User scope          (per-user override, if enabled)
    ↓
Website scope       (per-website override)
    ↓
Organization scope  (per-organization override)
    ↓
Global scope        (system-wide default — what System > Configuration sets)
```

To support website-level config, register the field in the website config tree too:

```yaml
system_configuration:
    tree:
        website_configuration:   # website-level tree (different from system_configuration)
            general:
                children:
                    acme_demo_settings:
                        children:
                            - acme_demo.feature_enabled
```

---

## API Access

Fields listed in `api_tree` are accessible via the Config REST API:

```
GET  /api/config/acme_demo_integration
PATCH /api/config/acme_demo_integration
```

Request body:
```json
{
    "acme_demo.feature_enabled": {
        "value": true,
        "use_parent_scope_value": false
    }
}
```

---

## Complete Working Example

This example adds a "Acme Integration" settings page under System > Integrations:

```yaml
# src/Acme/DemoBundle/Resources/config/oro/system_configuration.yml
system_configuration:
    fields:
        acme_demo.integration_enabled:
            data_type: boolean
            type: Oro\Bundle\ConfigBundle\Form\Type\ConfigCheckbox
            options:
                label: acme.demo.config.integration_enabled.label

        acme_demo.integration_api_url:
            data_type: string
            type: Symfony\Component\Form\Extension\Core\Type\TextType
            options:
                label: acme.demo.config.integration_api_url.label
                constraints:
                    - NotBlank: ~
                    - Url: ~

        acme_demo.integration_api_key:
            data_type: string
            type: Oro\Bundle\FormBundle\Form\Type\OroEncodedPlaceholderPasswordType
            options:
                label: acme.demo.config.integration_api_key.label

    groups:
        acme_demo_integration_group:
            title: acme.demo.config.group.integration.label
            icon: fa-plug

    tree:
        system_configuration:
            platform:
                children:
                    integrations:
                        children:
                            acme_demo_integration_group:
                                children:
                                    - acme_demo.integration_enabled
                                    - acme_demo.integration_api_url
                                    - acme_demo.integration_api_key

    api_tree:
        acme_demo:
            acme_demo.integration_enabled: ~
            acme_demo.integration_api_url: ~
```
