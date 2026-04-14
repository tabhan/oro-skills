# OroCommerce Entity Configuration — Complete Reference

> Source: https://doc.oroinc.com/master/backend/configuration/yaml/entity-config/

## AGENT QUERY HINTS

Use this file when:
- "How do I make an entity configurable in Oro?"
- "What is the #[Config] attribute in Oro?"
- "What is the #[ConfigField] attribute?"
- "What scopes can I put in #[Config] defaultValues?"
- "How do I enable data audit (change tracking) on an entity/field?"
- "How do I control import/export behavior for a field?"
- "How do I make a field appear in the entity view/grid/form via config?"
- "What is entity_config.yml / entity.yml?"
- "How do I declare a custom entity config scope?"
- "What is the ownership scope in #[Config]?"
- "How do I set security / ACL on an entity via config?"
- "What does 'immutable: true' do in entity config?"
- "What CLI commands manage entity config?"

---

## Overview

Oro's `EntityConfigBundle` provides a **metadata layer on top of Doctrine ORM** —
it allows bundles to attach configurable metadata to entities and their fields
without modifying ORM mappings.

Configuration is stored in the database (`oro_entity_config` table) and cached.
Bundles define their scope schemas in `entity.yml` (formerly `entity_config.yml`).
Developers set default values on entities/fields using PHP attributes.

**Two levels:**
1. **Entity-level** — configured via `#[Config]` on the class
2. **Field-level** — configured via `#[ConfigField]` on a property

---

## Activating an Entity for Config

```php
use Doctrine\ORM\Mapping as ORM;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\Config;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\ConfigField;

#[ORM\Entity]
#[ORM\Table(name: 'acme_demo_product')]
#[Config(
    routeName: 'acme_demo_product_index',      // datagrid route
    routeView: 'acme_demo_product_view',        // view route
    routeCreate: 'acme_demo_product_create',    // create route
    routeUpdate: 'acme_demo_product_edit',      // edit route
    defaultValues: [
        'entity' => [
            'icon' => 'fa-cube',               // icon in UI
        ],
        'ownership' => [
            'owner_type' => 'USER',
            'owner_field_name' => 'owner',
            'owner_column_name' => 'owner_id',
            'organization_field_name' => 'organization',
            'organization_column_name' => 'organization_id',
        ],
        'security' => [
            'type' => 'ACL',
            'group_name' => '',
            'category' => 'account_management',
        ],
        'dataaudit' => [
            'auditable' => true,
        ],
    ]
)]
class Product
{
    #[ORM\Column(name: 'name', type: 'string', length: 255)]
    #[ConfigField(defaultValues: [
        'dataaudit' => ['auditable' => true],
        'importexport' => ['order' => 10, 'identity' => false],
        'entity' => ['label' => 'acme.demo.product.name.label'],
    ])]
    private string $name;
}
```

---

## #[Config] Attribute — All Parameters

```php
#[Config(
    routeName:   'route_for_entity_list',       // string — route showing datagrid
    routeView:   'route_for_entity_view',        // string — route showing record
    routeCreate: 'route_for_entity_create',      // string — route for create form
    routeUpdate: 'route_for_entity_edit',        // string — route for edit form
    defaultValues: [                             // array — scope => [key => value]
        // ... see scopes below
    ]
)]
```

### #[Config] `defaultValues` Scopes

#### `entity` Scope
Controls how the entity appears in UI metadata:

| Key | Type | Description |
|-----|------|-------------|
| `icon` | string | Font Awesome icon (e.g., `fa-cube`) |
| `label` | string | Translation key for entity singular label |
| `plural_label` | string | Translation key for entity plural label |
| `description` | string | Translation key for entity description |
| `contact_information` | map | Marks fields as phone/email contact info |
| `immutable` | boolean | Prevent changing via UI |

#### `ownership` Scope
Defines who owns records (required for ACL filtering):

| Key | Type | Description |
|-----|------|-------------|
| `owner_type` | string | `NONE`, `USER`, `BUSINESS_UNIT`, or `ORGANIZATION` |
| `owner_field_name` | string | Property name of the owner field |
| `owner_column_name` | string | DB column name for owner FK |
| `organization_field_name` | string | Property name of organization field |
| `organization_column_name` | string | DB column name for org FK |
| `frontend_owner_type` | string | Storefront owner type |
| `frontend_owner_field_name` | string | Storefront owner property |

#### `security` Scope
Controls ACL behavior:

| Key | Type | Description |
|-----|------|-------------|
| `type` | string | `ACL` (enables Oro ACL) |
| `permissions` | string | Comma-separated: `VIEW,CREATE,EDIT,DELETE` (default: `All`) |
| `group_name` | string | ACL group (empty = top-level) |
| `category` | string | ACL category in role management UI |
| `field_acl_supported` | boolean | Enable field-level ACL |
| `field_acl_enabled` | boolean | Enable field ACL by default |
| `share_scopes` | list | Sharing scope: `['organization', 'business_unit', 'user']` |
| `immutable` | boolean | Prevent security config changes via UI |

#### `dataaudit` Scope
Controls change tracking:

| Key | Type | Description |
|-----|------|-------------|
| `auditable` | boolean | Track all changes to this entity |
| `immutable` | boolean | Prevent changing auditable status via UI |

#### `extend` Scope
Controls OroMigrations extend functionality:

| Key | Type | Description |
|-----|------|-------------|
| `owner` | string | `Custom` or `System` |
| `is_extend` | boolean | Enable extend (custom field creation via UI) |
| `state` | string | `Active`, `Requires update`, `Deleted` |
| `table` | string | Override table name |
| `inherit` | string | Parent class for table inheritance |
| `schema` | map | Low-level schema descriptor |
| `immutable` | boolean | Prevent extension |

#### `activity` Scope
Register entity as an activity:

| Key | Type | Description |
|-----|------|-------------|
| `show_on_page` | constant | `\Oro\Bundle\ActivityBundle\EntityConfig\ActivityScope::UPDATE_PAGE` etc. |
| `route` | string | Route to create/view activity |
| `acl` | string | ACL resource for activity creation |
| `action_button_widget` | string | Widget template for action button |
| `action_link_widget` | string | Widget template for action link |
| `immutable` | boolean | Prevent changes |

#### `attachment` Scope
Controls file attachment support:

| Key | Type | Description |
|-----|------|-------------|
| `enabled` | boolean | Enable attachments for this entity |
| `auto_link_attachments` | boolean | Auto-link uploaded files |
| `maxsize` | integer | Max file size in MB |
| `mimetypes` | string | Allowed MIME types (newline-delimited) |
| `immutable` | boolean | Prevent changes |

#### `comment` Scope

| Key | Type | Description |
|-----|------|-------------|
| `enabled` | boolean | Enable comments for this entity |
| `immutable` | boolean | Prevent changes |

#### `tag` Scope

| Key | Type | Description |
|-----|------|-------------|
| `enabled` | boolean | Enable tagging for this entity |
| `enable_grid` | boolean | Show tags column in datagrid |
| `enable_default_rendering` | boolean | Render tags in default view |
| `immutable` | boolean | Prevent changes |

#### `merge` Scope
Controls entity merge feature:

| Key | Type | Description |
|-----|------|-------------|
| `enable` | boolean | Allow merging records |
| `cast_method` | string | Method to convert entity to string |
| `template` | string | Template for merge step display |
| `max_entities_count` | integer | Maximum entities to merge at once |
| `immutable` | boolean | Prevent changes |

#### `grid` Scope

| Key | Type | Description |
|-----|------|-------------|
| `default` | string | Default datagrid name for this entity |
| `context` | string | Datagrid for context/relationship views |

#### `form` Scope

| Key | Type | Description |
|-----|------|-------------|
| `form_type` | string | Custom form type class |
| `form_options` | map | Options passed to the form type |
| `grid_name` | string | Grid name for relation field |

#### `grouping` Scope

| Key | Type | Description |
|-----|------|-------------|
| `groups` | list | Entity group names (e.g., `['activity']`) |

#### `search` Scope

| Key | Type | Description |
|-----|------|-------------|
| `searchable` | boolean | Include entity in search results |

#### `workflow` Scope

| Key | Type | Description |
|-----|------|-------------|
| `show_step_in_grid` | boolean | Display workflow step column in grids |

#### `draft` Scope

| Key | Type | Description |
|-----|------|-------------|
| `draftable` | boolean | Enable draft functionality |

#### `attribute` Scope

| Key | Type | Description |
|-----|------|-------------|
| `has_attributes` | boolean | Enable dynamic attribute creation via UI |
| `immutable` | boolean | Prevent changes |

---

## #[ConfigField] Attribute — All Parameters

```php
#[ConfigField(
    defaultValues: [
        // scope => [key => value]
    ]
)]
private string $fieldName;
```

### #[ConfigField] `defaultValues` Scopes

#### `entity` Scope (field-level)

| Key | Type | Description |
|-----|------|-------------|
| `label` | string | Translation key for field label |
| `description` | string | Translation key for field description |
| `contact_information` | string | `'phone'` or `'email'` — marks contact info type |
| `actualize_owning_side_on_change` | boolean | Update timestamps on collection change |
| `immutable` | boolean | Prevent changing label/description via UI |

#### `dataaudit` Scope (field-level)

| Key | Type | Description |
|-----|------|-------------|
| `auditable` | boolean | Track changes to this specific field |
| `propagate` | boolean | Enable reverse-side audit for relations |
| `immutable` | boolean | Prevent changing auditable status |

#### `importexport` Scope

| Key | Type | Description |
|-----|------|-------------|
| `identity` | boolean | Used to identify entity during import (like a natural key) |
| `excluded` | boolean | Never export this field |
| `order` | integer | Column position in export |
| `full` | boolean | Export all related entity fields |
| `short` | boolean | Export if identity fields are present |
| `process_as_scalar` | boolean | Treat relation as scalar value |
| `header` | string | Custom column header (default: field label) |
| `fallback_field` | string | Localized fallback field attribute |
| `immutable` | boolean | Prevent changes |

#### `view` Scope

| Key | Type | Description |
|-----|------|-------------|
| `is_displayable` | boolean | Show this field on the entity view page |
| `priority` | integer | Display priority in view page |
| `type` | string | View type, e.g., `'html'` |
| `immutable` | boolean | Prevent changes |

#### `datagrid` Scope (field-level)

| Key | Type | Description |
|-----|------|-------------|
| `is_visible` | boolean | Show as datagrid column |
| `show_filter` | boolean | Show in datagrid filter bar |
| `order` | integer | Column position |
| `immutable` | boolean | Prevent changes |

#### `form` Scope (field-level)

| Key | Type | Description |
|-----|------|-------------|
| `is_enabled` | boolean | Show in entity form |
| `form_type` | string | Override form type class |
| `form_options` | map | Options for the form type |
| `immutable` | boolean | Prevent changes |

#### `attachment` Scope (field-level)

| Key | Type | Description |
|-----|------|-------------|
| `is_stored_externally` | boolean | File is stored externally |
| `acl_protected` | boolean | ACL check on file load |
| `file_applications` | list | Allowed apps, e.g., `['default']` |
| `use_dam` | boolean | Use Digital Asset Management |
| `maxsize` | integer | Max file size in MB |
| `width` | integer | Thumbnail width in pixels |
| `height` | integer | Thumbnail height in pixels |
| `mimetypes` | string | Allowed MIME types |
| `max_number_of_files` | integer | Max number of files |
| `immutable` | boolean | Prevent changes |

#### `attribute` Scope (field-level)

| Key | Type | Description |
|-----|------|-------------|
| `is_attribute` | boolean | This field is a dynamic attribute |
| `is_system` | boolean | Built-in — cannot be modified via UI |
| `searchable` | boolean | Searchable in storefront |
| `filterable` | boolean | Can be filtered in storefront |
| `filter_by` | string | `'exact_value'` or `'fulltext_search'` |
| `sortable` | boolean | Can be sorted |
| `is_global` | boolean | Created in global organization |
| `search_boost` | integer | Relevancy boost in search |
| `immutable` | boolean | Prevent changes |

#### `extend` Scope (field-level)

| Key | Type | Description |
|-----|------|-------------|
| `is_extend` | boolean | Enable ORM extend for this field |
| `is_serialized` | boolean | Store in JSON serialized_data column |
| `owner` | string | `Custom` or `System` |
| `state` | string | `Active`, `Requires update`, `Deleted` |
| `without_default` | boolean | Relation has no default value |
| `cascade` | list | Doctrine cascade ops: `persist`, `remove`, etc. |
| `on_delete` | string | `CASCADE`, `SET NULL`, or `RESTRICT` |
| `orphanRemoval` | boolean | Remove orphaned entities |
| `target_entity` | string | FQCN of related entity |
| `target_title` | list | Fields for relation display title |
| `target_detailed` | list | Fields for relation detailed view |
| `target_grid` | list | Fields for relation grid display |
| `fetch` | string | `lazy`, `extra_lazy`, or `eager` |
| `bidirectional` | boolean | Create bidirectional relation |

#### `merge` Scope (field-level)

| Key | Type | Description |
|-----|------|-------------|
| `display` | boolean | Show field in merge form |
| `readonly` | boolean | Read-only during merge |
| `merge_modes` | list | `['replace', 'unite']` |
| `is_collection` | boolean | Supports `unite` mode |
| `label` | string | Label in merge form (translatable) |

#### `email` Scope (field-level)

| Key | Type | Description |
|-----|------|-------------|
| `available_in_template` | boolean | Available in email templates |
| `immutable` | boolean | Prevent changes |

#### `security` Scope (field-level)

| Key | Type | Description |
|-----|------|-------------|
| `permissions` | string | `VIEW`, `EDIT` — field-level permissions |
| `immutable` | boolean | Prevent changes |

#### `frontend` Scope (field-level)

| Key | Type | Description |
|-----|------|-------------|
| `is_displayable` | boolean | Show in storefront views |
| `is_editable` | boolean | Editable in storefront forms |
| `immutable` | boolean | Prevent changes |

#### `search` Scope (field-level)

| Key | Type | Description |
|-----|------|-------------|
| `searchable` | boolean | Include field in search index |
| `immutable` | boolean | Prevent changes |

---

## Custom Scope Definition (entity.yml)

If your bundle introduces its own configurable scope, declare it:

```yaml
# Resources/config/oro/entity.yml
entity_config:
    acme_integration:                  # your scope name
        entity:
            items:
                sync_enabled:
                    options:
                        priority: 10
                        auditable: false
                    form:
                        type: Symfony\Component\Form\Extension\Core\Type\CheckboxType
                        options:
                            label: 'Sync Enabled'
                            required: false
                    grid:
                        type: boolean

        field:
            items:
                sync_field:
                    options:
                        priority: 5
                    form:
                        type: Symfony\Component\Form\Extension\Core\Type\TextType
                        options:
                            label: 'Sync Field'
                    grid:
                        type: string
                        filterable: true
```

Usage in PHP:
```php
#[Config(defaultValues: ['acme_integration' => ['sync_enabled' => true]])]
class Product {}

#[ConfigField(defaultValues: ['acme_integration' => ['sync_field' => 'name']])]
private string $name;
```

---

## CLI Commands

```bash
# Update entity configuration in DB from PHP attributes:
php bin/console oro:entity-config:update

# Debug entity configuration for a specific class:
php bin/console oro:entity-config:debug "Acme\DemoBundle\Entity\Product"

# Clear entity config cache:
php bin/console oro:entity-config:cache:clear

# Clear and warm entity config cache:
php bin/console oro:entity-config:cache:warmup

# Dump entity_config.yml reference for all scopes:
php bin/console oro:entity:config:dump-reference
```

---

## Reading Entity Config Values in PHP

```php
use Oro\Bundle\EntityConfigBundle\Config\ConfigManager;

class MyService
{
    public function __construct(
        private readonly ConfigManager $entityConfigManager
    ) {}

    public function check(string $className): bool
    {
        // Get entity-level config for a scope:
        $config = $this->entityConfigManager->getEntityConfig('security', $className);
        $aclType = $config->get('type');   // 'ACL' or null

        // Get field-level config:
        $fieldConfig = $this->entityConfigManager->getFieldConfig('dataaudit', $className, 'name');
        $isAuditable = $fieldConfig->get('auditable');   // true/false

        // Check if entity has a scope:
        $hasOwnership = $this->entityConfigManager->hasConfig($className)
            && $this->entityConfigManager->getEntityConfig('ownership', $className)->has('owner_type');

        return $isAuditable;
    }
}
```

---

## Practical Complete Example

```php
<?php

namespace Acme\DemoBundle\Entity;

use Doctrine\ORM\Mapping as ORM;
use Oro\Bundle\EntityBundle\EntityProperty\DatesAwareInterface;
use Oro\Bundle\EntityBundle\EntityProperty\DatesAwareTrait;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\Config;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\ConfigField;
use Oro\Bundle\OrganizationBundle\Entity\OrganizationInterface;
use Oro\Bundle\UserBundle\Entity\User;

#[ORM\Entity(repositoryClass: OrderRepository::class)]
#[ORM\Table(name: 'acme_demo_order')]
#[Config(
    routeName: 'acme_demo_order_index',
    routeView: 'acme_demo_order_view',
    routeCreate: 'acme_demo_order_create',
    routeUpdate: 'acme_demo_order_edit',
    defaultValues: [
        'entity' => ['icon' => 'fa-shopping-cart'],
        'ownership' => [
            'owner_type' => 'USER',
            'owner_field_name' => 'owner',
            'owner_column_name' => 'owner_id',
            'organization_field_name' => 'organization',
            'organization_column_name' => 'organization_id',
        ],
        'security' => [
            'type' => 'ACL',
            'group_name' => '',
            'category' => 'sales',
        ],
        'dataaudit' => ['auditable' => true],
        'tag' => ['enabled' => true],
        'comment' => ['enabled' => true],
        'workflow' => ['show_step_in_grid' => true],
    ]
)]
class Order implements DatesAwareInterface
{
    use DatesAwareTrait;

    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column(type: 'integer')]
    private ?int $id = null;

    #[ORM\Column(name: 'reference', type: 'string', length: 64)]
    #[ConfigField(defaultValues: [
        'entity' => ['label' => 'acme.demo.order.reference.label'],
        'dataaudit' => ['auditable' => true],
        'importexport' => ['order' => 10, 'identity' => true],
        'view' => ['is_displayable' => true, 'priority' => 10],
        'datagrid' => ['is_visible' => true, 'show_filter' => true, 'order' => 10],
        'form' => ['is_enabled' => true],
    ])]
    private string $reference = '';

    #[ORM\ManyToOne(targetEntity: User::class)]
    #[ORM\JoinColumn(name: 'owner_id', referencedColumnName: 'id', onDelete: 'SET NULL')]
    #[ConfigField(defaultValues: [
        'dataaudit' => ['auditable' => true],
        'importexport' => ['order' => 90, 'short' => true],
    ])]
    private ?User $owner = null;

    #[ORM\ManyToOne(targetEntity: OrganizationInterface::class)]
    #[ORM\JoinColumn(name: 'organization_id', referencedColumnName: 'id', onDelete: 'SET NULL')]
    private ?OrganizationInterface $organization = null;
}
```
