# OroCommerce: Configuring Entities

> Source: https://doc.oroinc.com/master/backend/entities/config-entities/

## AGENT QUERY HINTS

This file answers:
- What is the #[Config] attribute and what parameters does it accept?
- What is the #[ConfigField] attribute and what parameters does it accept?
- How do I configure entity routing (routeName, routeView, routeCreate)?
- How do I set the entity icon in the UI?
- How do I configure ownership (who owns an entity record)?
- How do I configure security/ACL for an entity?
- How do I configure data audit for an entity or field?
- How do I add custom config scopes/options to entities?
- How do I access entity configuration programmatically in PHP?
- What is EntityConfigBundle and what does it manage?
- How do I configure an entity for use in workflows?
- How do I configure routing for a custom entity?
- What is the entity.yml file and when do I need it?
- How do I give an entity a human-readable label?
- What is `entity_config` scope and how does it work?
- How do I make an entity show in the Entities management UI?

---

## Core Concept: WHY Entity Configuration Exists

OroCommerce wraps entities in a rich metadata layer managed by **OroEntityConfigBundle**. This metadata controls:
- How the entity appears in the admin UI (icon, label, description)
- How ownership and organization context apply to records
- Whether ACL protection is active
- What routes exist for the entity's CRUD pages
- Which features (data audit, notes, activities, comments) the entity participates in

Without this configuration, an entity is a plain Doctrine entity — it works in PHP but has no UI, no ACL, no ownership, and no place in the Oro admin.

---

## The `#[Config]` Attribute

The `#[Config]` PHP attribute from `Oro\Bundle\EntityConfigBundle\Metadata\Attribute\Config` is the primary way to configure entity metadata. It is placed on the entity class.

### Minimal Configuration (Public Entity with UI Pages)

```php
<?php
// src/Bridge/Bundle/BridgeNewsBundle/Entity/NewsArticle.php

namespace Bridge\Bundle\BridgeNewsBundle\Entity;

use Doctrine\ORM\Mapping as ORM;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\Config;

#[ORM\Entity]
#[ORM\Table(name: 'bridge_news_article')]
#[Config(
    // routeName: the route for the entity list (index) page.
    // WHY: Oro uses this to generate "View list" links in breadcrumbs
    // and entity management pages.
    routeName: 'bridge_news_article_index',

    // routeView: the route for viewing a single entity record.
    // WHY: Used for "View" links in grids and related entity displays.
    routeView: 'bridge_news_article_view',

    // routeCreate: the route for creating a new record (optional).
    // WHY: Shown as the "Create" button link in the entity list.
    routeCreate: 'bridge_news_article_create',

    defaultValues: [
        // 'entity' scope: controls labels and icons in the admin UI.
        'entity' => [
            // icon: FontAwesome 4.x icon class shown in entity grids/UI.
            'icon' => 'fa-newspaper-o',
        ],
    ]
)]
class NewsArticle
{
    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column(type: 'integer')]
    private ?int $id = null;

    #[ORM\Column(name: 'title', type: 'string', length: 255)]
    private string $title = '';

    // ... other fields ...
}
```

---

### Full Configuration (Owned Entity with ACL and Audit)

This is the pattern for a business entity that belongs to users, participates in ACL, and tracks changes:

```php
<?php
// src/Bridge/Bundle/BridgeCustomerBundle/Entity/CustomerComplaint.php

namespace Bridge\Bundle\BridgeCustomerBundle\Entity;

use Doctrine\ORM\Mapping as ORM;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\Config;
use Oro\Bundle\EntityExtendBundle\Entity\ExtendEntityInterface;
use Oro\Bundle\EntityExtendBundle\Entity\ExtendEntityTrait;

#[ORM\Entity]
#[ORM\Table(name: 'bridge_customer_complaint')]
#[Config(
    routeName: 'bridge_customer_complaint_index',
    routeView: 'bridge_customer_complaint_view',
    routeCreate: 'bridge_customer_complaint_create',
    defaultValues: [

        // --- Entity display settings ---
        'entity' => [
            'icon' => 'fa-exclamation-circle',
        ],

        // --- Ownership: who "owns" a complaint record ---
        // WHY: Determines which access levels (User/BU/Org/Global)
        //      are meaningful for ACL role configuration.
        'ownership' => [
            // owner_type: 'USER' means individual users own complaints.
            // Options: 'USER', 'BUSINESS_UNIT', 'ORGANIZATION', 'NONE'
            'owner_type' => 'USER',

            // owner_field_name: the PHP property name on this entity that
            // holds the owning User object.
            'owner_field_name' => 'owner',

            // owner_column_name: the DB column name for the FK to the owner.
            'owner_column_name' => 'owner_id',

            // organization_field_name / organization_column_name:
            // Required when owner_type is USER or BUSINESS_UNIT.
            // WHY: Oro needs to know which organization a record belongs to
            //      for multi-org isolation.
            'organization_field_name' => 'organization',
            'organization_column_name' => 'organization_id',
        ],

        // --- Security: enables ACL protection ---
        'security' => [
            // type: 'ACL' activates ACL checking for this entity.
            // Without this, no ACL protection is applied.
            'type' => 'ACL',

            // group_name: optional logical grouping in the role editor UI.
            // '' means the entity appears in the default group.
            'group_name' => '',

            // category: optional category in the role editor.
            // Common values: 'account_management', 'sales_data', etc.
            'category' => 'customer_management',
        ],

        // --- Data Audit: track all changes to this entity ---
        // WHY: When auditable: true, every create/update/delete is logged
        //      in oro_audit and visible at /admin/dataaudit.
        'dataaudit' => [
            'auditable' => true,
        ],
    ]
)]
class CustomerComplaint implements ExtendEntityInterface
{
    use ExtendEntityTrait;

    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column(type: 'integer')]
    private ?int $id = null;

    #[ORM\Column(name: 'subject', type: 'string', length: 255)]
    private string $subject = '';

    // The owner field: required when owner_type is USER.
    // WHY: Oro reads this field to determine who owns the record
    //      during ACL access level checks.
    #[ORM\ManyToOne(targetEntity: \Oro\Bundle\UserBundle\Entity\User::class)]
    #[ORM\JoinColumn(name: 'owner_id', nullable: true, onDelete: 'SET NULL')]
    private ?\Oro\Bundle\UserBundle\Entity\User $owner = null;

    // The organization field: required when owner_type is USER or BUSINESS_UNIT.
    #[ORM\ManyToOne(targetEntity: \Oro\Bundle\OrganizationBundle\Entity\Organization::class)]
    #[ORM\JoinColumn(name: 'organization_id', nullable: true, onDelete: 'SET NULL')]
    private ?\Oro\Bundle\OrganizationBundle\Entity\Organization $organization = null;

    public function getId(): ?int { return $this->id; }
    public function getSubject(): string { return $this->subject; }
    public function setSubject(string $subject): self { $this->subject = $subject; return $this; }
    public function getOwner(): ?\Oro\Bundle\UserBundle\Entity\User { return $this->owner; }
    public function setOwner(?\Oro\Bundle\UserBundle\Entity\User $owner): self { $this->owner = $owner; return $this; }
    public function getOrganization(): ?\Oro\Bundle\OrganizationBundle\Entity\Organization { return $this->organization; }
    public function setOrganization(?\Oro\Bundle\OrganizationBundle\Entity\Organization $organization): self { $this->organization = $organization; return $this; }
}
```

---

## Ownership Type Reference

| `owner_type` | Required Fields | Meaning |
|--------------|----------------|---------|
| `USER` | `owner_field_name`, `owner_column_name`, `organization_field_name`, `organization_column_name` | Individual user owns the record |
| `BUSINESS_UNIT` | `owner_field_name`, `owner_column_name`, `organization_field_name`, `organization_column_name` | A business unit owns the record |
| `ORGANIZATION` | `owner_field_name`, `owner_column_name` | An organization owns the record |
| `NONE` (or omit) | none | No owner — record is system-wide or organization-independent |

**WHY the organization field when owner_type is USER:** Even though a User already belongs to organizations, Oro stores the organization directly on the record for faster ACL queries — it avoids joining through the user-to-organization relationship on every access check.

---

## Entity Config Scopes Reference

The `defaultValues` array is keyed by **scope**. Each scope is managed by a different bundle:

| Scope | Bundle | Purpose |
|-------|--------|---------|
| `entity` | EntityConfigBundle | Icon, label, description in UI |
| `ownership` | SecurityBundle | Owner type, field names for ACL |
| `security` | SecurityBundle | ACL type, group, category |
| `dataaudit` | DataAuditBundle | Whether changes are logged |
| `activity` | ActivityBundle | Enable activities (calls, tasks, emails) on entity |
| `attachment` | AttachmentBundle | Allow file attachments on entity |
| `note` | NoteBundle | Allow text notes on entity |
| `tag` | TagBundle | Allow user-defined tags on entity |
| `comment` | CommentBundle | Allow comments on entity records |
| `extend` | EntityExtendBundle | Custom field configuration |

### Enabling Activities, Attachments, and Notes

```php
#[Config(
    defaultValues: [
        // Allow sales reps to log calls and emails against this entity:
        'activity' => [
            'activities' => ['Oro\Bundle\CallBundle\Entity\Call', 'Oro\Bundle\EmailBundle\Entity\Email'],
        ],

        // Allow file attachments (PDFs, images) to be linked to this entity:
        'attachment' => [
            'enabled' => true,
        ],

        // Allow freeform text notes:
        'note' => [
            'immutable' => false,
        ],
    ]
)]
```

---

## Field-Level Configuration with `#[ConfigField]`

Individual entity fields can also carry metadata using the `#[ConfigField]` attribute:

```php
<?php
// src/Bridge/Bundle/BridgeCustomerBundle/Entity/CustomerComplaint.php

use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\ConfigField;

// On the entity field:
#[ORM\Column(name: 'priority_level', type: 'integer', nullable: true)]
#[ConfigField(
    defaultValues: [
        // datagrid: controls field behavior in list grids
        'datagrid' => [
            'is_visible' => false, // Hidden in grid by default (user can enable)
        ],
        // dataaudit: track changes to this specific field
        'dataaudit' => [
            'auditable' => true,
        ],
        // importexport: control import/export behavior
        'importexport' => [
            'excluded' => false,        // Include this field in exports
            'identity' => false,        // Not used as unique identifier during import
        ],
    ]
)]
private ?int $priorityLevel = null;
```

---

## Entity Alias Configuration (entity.yml)

Entity aliases control how entity class names appear in:
- API URLs (e.g., `/api/complaints` instead of `/api/bridgecustomercomplaint`)
- ACL resource identifiers
- Search index type names

### Without entity.yml

By default, the alias is auto-derived from the class name. `CustomerComplaint` becomes `customercomplaint` in URLs.

### With entity.yml (explicit aliases)

```yaml
# src/Bridge/Bundle/BridgeCustomerBundle/Resources/config/oro/entity.yml
oro_entity:
    exclusions:
        # Exclude internal/helper entities from the API and datagrid
        - { entity: Bridge\Bundle\BridgeCustomerBundle\Entity\InternalHelper }

    entity_aliases:
        # Map the full class name to a clean alias
        Bridge\Bundle\BridgeCustomerBundle\Entity\CustomerComplaint:
            # alias: used in API URLs (singular form)
            alias: complaint
            # plural_alias: used in JSON:API type and collection endpoints
            plural_alias: complaints
```

Result: API endpoint becomes `/api/complaints` instead of `/api/bridgecustomercomplaint`.

---

## After Changing Entity Config

Entity config is cached. After adding or modifying `#[Config]` attributes:

```bash
# Reload entity config into the database (and clear cache)
php bin/console oro:entity-config:update

# Then clear the full application cache
php bin/console cache:clear

# If you added ownership/security config to a new entity,
# also update the ACL permission schema:
php bin/console oro:platform:update --force
```

---

## Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Omitting `organization_field_name` when `owner_type: USER` | Entity records cannot be isolated by organization | Add `organization_field_name` and `organization_column_name` |
| Setting `owner_type: USER` but not adding the `owner` DB column | Runtime error when saving records | Create migration to add `owner_id` column and FK |
| Changing `owner_type` after data is in the database | Existing records have wrong ownership structure | Migration required to backfill ownership data |
| Forgetting `php bin/console oro:entity-config:update` after #[Config] changes | Config not reflected in UI | Run the command and clear cache |
| Using a route name in `routeName` that does not exist | Broken links in entity management UI | Ensure the route is defined in routing.yml |

---

---

## Accessing Entity Configuration Programmatically

```php
<?php
namespace Acme\Bundle\DemoBundle\Service;

use Oro\Bundle\EntityConfigBundle\Config\ConfigManager;
use Oro\Bundle\EntityConfigBundle\Config\ConfigInterface;
use Acme\Bundle\DemoBundle\Entity\Document;

class DocumentService
{
    public function __construct(
        private readonly ConfigManager $configManager
    ) {}

    public function getEntityIcon(): string
    {
        // getEntityConfig(scope, entityClass)
        // WHY scope: config is namespaced by scope ('entity', 'security', etc.)
        $config = $this->configManager->getEntityConfig('entity', Document::class);
        return $config->get('icon', false, 'fa-file');
    }

    public function isFieldAuditable(string $fieldName): bool
    {
        // getFieldConfig(scope, entityClass, fieldName)
        $config = $this->configManager->getFieldConfig('dataaudit', Document::class, $fieldName);
        return (bool) $config->get('auditable', false, false);
    }

    public function isEntityAuditable(): bool
    {
        $config = $this->configManager->getEntityConfig('dataaudit', Document::class);
        return (bool) $config->get('auditable', false, false);
    }

    public function updateEntityConfig(): void
    {
        $config = $this->configManager->getEntityConfig('entity', Document::class);
        $config->set('icon', 'fa-star');

        // WHY persist + flush: analogous to Doctrine — stage then write.
        $this->configManager->persist($config);
        $this->configManager->flush();
    }
}
```

### ConfigManager service methods

| Method | Description |
|--------|-------------|
| `getEntityConfig(string $scope, string $class)` | Get entity-level config for a scope |
| `getFieldConfig(string $scope, string $class, string $field)` | Get field-level config |
| `hasConfig(string $class, ?string $field)` | Check if entity/field has config registered |
| `getProvider(string $scope)` | Get the `ConfigProvider` for a scope |
| `persist(ConfigInterface $config)` | Stage a config change |
| `flush()` | Write all staged changes to the database |

---

## Adding Custom Configuration Options

To introduce a new configuration scope (e.g., `my_bundle`), create an `entity_config.yml` file in your bundle:

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/entity_config.yml
entity_config:
    my_bundle:
        entity:
            items:
                is_enabled:
                    options:
                        default_value: false          # default when not set
                        require_schema_update: false  # true if schema must update on change
                        priority: 10                  # sort order in UI
                    form:
                        type: Symfony\Component\Form\Extension\Core\Type\CheckboxType
                        options:
                            required: false
                            label: acme.demo.entity_config.is_enabled.label

                target_class:
                    options:
                        default_value: ~
                        immutable: true   # admin cannot change via UI
```

Access your custom scope:

```php
$config = $this->configManager->getEntityConfig('my_bundle', Document::class);
$isEnabled = $config->get('is_enabled');
```

---

## Next Steps

1. Create CRUD pages and register routes: see `crud-and-routing.md`
2. Set up extended fields (enum, relation, serialized): see `extend-entities.md`
3. Configure the datagrid for entity list pages: see `../configuration-reference/datagrids.md`
