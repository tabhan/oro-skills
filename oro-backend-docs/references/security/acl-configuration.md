# OroCommerce ACL Configuration Reference

> Source: https://doc.oroinc.com/master/backend/configuration/yaml/acls/

## AGENT QUERY HINTS

Use this file when answering questions like:
- "How do I define an ACL in Oro?"
- "What parameters does the #[Acl] attribute accept?"
- "How do I use acls.yml to protect a controller action?"
- "What is AclAncestor and when should I use it?"
- "How do I protect an entity with ACL?"
- "How do I restrict a datagrid with ACL?"
- "How do I configure ownership on an entity?"
- "How do I protect a non-entity action with ACL?"
- "How do I check permissions in a DQL query?"
- "What is the difference between #[Acl] and #[AclAncestor]?"
- "How do I configure entity security in config/oro/acls.yml?"

---

## Two Ways to Define ACL Resources

Oro supports two equivalent approaches to declaring ACL resources:

1. **PHP attributes** — `#[Acl]` and `#[AclAncestor]` directly on controller methods.
2. **YAML configuration** — `Resources/config/oro/acls.yml` inside a bundle.

Both produce the same result. The YAML approach is preferred for keeping security declarations separate from business logic and for defining ACLs that apply to multiple controllers.

---

## Entity-Level Security Configuration

Before an entity can be protected by ACLs, it must declare itself as ACL-enabled using the `#[Config]` attribute.

### Minimal Entity Config (All permissions, no ownership)

```php
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\Config;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\ConfigField;

#[Config(
    defaultValues: [
        'security' => [
            'type'        => 'ACL',     // Required: marks entity as ACL-protected
            'permissions' => 'All',     // All standard permissions enabled
            'group_name'  => '',        // Application scope group (empty = default)
            'category'    => ''         // Category for role configuration UI
        ]
    ]
)]
class Favorite
{
    // ...
}
```

### Restricting Available Permissions

To limit which permissions are shown in the role editor (e.g., only VIEW and EDIT):

```php
#[Config(
    defaultValues: [
        'security' => [
            'type'        => 'ACL',
            'permissions' => 'VIEW;EDIT',  // Semicolon-separated list
        ]
    ]
)]
class ReadOnlyEntity { }
```

**WHY restrict permissions:** Some entities should never be deleted by roles (e.g., customer records that require an audit trail). Restricting to `VIEW;EDIT` removes the DELETE option from the role configuration UI entirely.

### Security Config Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | string | — | Must be `'ACL'` to enable ACL protection |
| `permissions` | string | `'All'` | Semicolon-separated permission list or `'All'` |
| `group_name` | string | `''` | Application group scope (e.g., `'commerce'` for storefront) |
| `category` | string | `''` | Category label shown in the role editor UI |

---

## Ownership Configuration

Ownership declares *who* owns a record and which fields store that relationship. This must be defined alongside the security config for entity-level ACL to work correctly.

### User Ownership (most common)

```php
#[Config(
    defaultValues: [
        'security' => ['type' => 'ACL', 'permissions' => 'All'],
        'ownership' => [
            'owner_type'               => 'USER',
            'owner_field_name'         => 'owner',          // PHP property name
            'owner_column_name'        => 'user_owner_id',  // DB column name
            'organization_field_name'  => 'organization',   // PHP property name
            'organization_column_name' => 'organization_id' // DB column name
        ]
    ]
)]
class Task
{
    private User $owner;
    private Organization $organization;
}
```

### Business Unit Ownership

```php
'ownership' => [
    'owner_type'               => 'BUSINESS_UNIT',
    'owner_field_name'         => 'owner',
    'owner_column_name'        => 'owner_id',
    'organization_field_name'  => 'organization',
    'organization_column_name' => 'organization_id'
]
```

### Organization Ownership

```php
'ownership' => [
    'owner_type'       => 'ORGANIZATION',
    'owner_field_name' => 'owner',
    'owner_column_name'=> 'owner_id'
    // No organization fields needed — the owner IS the organization
]
```

### No Ownership (system-wide entities)

```php
// Simply omit the 'ownership' key, or declare:
'ownership' => [
    'owner_type' => 'NONE'
]
```

**Important:** `USER` and `BUSINESS_UNIT` ownership types require both owner fields AND organization fields. `ORGANIZATION` ownership only requires owner fields. `NONE` requires no fields.

---

## Protecting Controller Actions

### Method 1: #[Acl] PHP Attribute

The `#[Acl]` attribute is placed directly on controller action methods (or the controller class for class-wide protection).

```php
use Oro\Bundle\SecurityBundle\Attribute\Acl;
use Oro\Bundle\SecurityBundle\Attribute\AclAncestor;
use Symfony\Component\Routing\Attribute\Route;

#[Route(path: '/favorite', name: 'acme_demo_favorite_')]
class FavoriteController extends AbstractController
{
    /**
     * List all favorites — requires VIEW permission on Favorite entity.
     */
    #[Route(path: '/', name: 'index')]
    #[Acl(
        id:         'acme_demo_favorite_index',  // Unique ACL resource ID
        type:       'entity',                    // 'entity' or 'action'
        class:      Favorite::class,             // Entity class (entity type only)
        permission: 'VIEW'                       // Permission being checked
    )]
    public function indexAction(): array
    {
        return ['entity_class' => Favorite::class];
    }

    /**
     * Create a new favorite — requires CREATE permission.
     */
    #[Route(path: '/new', name: 'new')]
    #[Acl(
        id:         'acme_demo_favorite_create',
        type:       'entity',
        class:      Favorite::class,
        permission: 'CREATE'
    )]
    public function newAction(): Response { /* ... */ }

    /**
     * Edit a favorite — requires EDIT permission.
     */
    #[Route(path: '/{id}/edit', name: 'edit')]
    #[Acl(
        id:         'acme_demo_favorite_edit',
        type:       'entity',
        class:      Favorite::class,
        permission: 'EDIT'
    )]
    public function editAction(Favorite $favorite): Response { /* ... */ }

    /**
     * Delete — requires DELETE permission.
     */
    #[Route(path: '/{id}/delete', name: 'delete')]
    #[Acl(
        id:         'acme_demo_favorite_delete',
        type:       'entity',
        class:      Favorite::class,
        permission: 'DELETE'
    )]
    public function deleteAction(int $id): Response { /* ... */ }

    /**
     * Alternative edit route that reuses the edit ACL definition.
     * WHY use AclAncestor: avoids defining a duplicate ACL resource;
     * this action is governed by the same permission as editAction.
     */
    #[Route(path: '/new-edit', name: 'new_edit')]
    #[AclAncestor('acme_demo_favorite_edit')]
    public function newEditAction(): Response { /* ... */ }
}
```

### #[Acl] Parameter Reference

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Unique identifier for this ACL resource across the application |
| `type` | string | Yes | `'entity'` for entity-level checks; `'action'` for capability checks |
| `class` | string | If type=entity | Fully qualified entity class name |
| `permission` | string | If type=entity | One of: `VIEW`, `CREATE`, `EDIT`, `DELETE`, `ASSIGN`, `SHARE` |

**WHY the `id` must be unique:** The ACL system uses the ID to look up which roles have been granted this permission. Duplicate IDs would merge permissions unexpectedly.

### #[AclAncestor] Parameter Reference

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | The `id` of an existing `#[Acl]` definition to inherit from |

**When to use `#[AclAncestor]`:** When two different routes (e.g., `/edit` and `/quick-edit`) should be governed by the same ACL check. One route defines the `#[Acl]`, the other references it with `#[AclAncestor]`.

---

## Method 2: YAML ACL Configuration

Define ACLs in `Resources/config/oro/acls.yml` inside your bundle.

### Complete Annotated acls.yml Example

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/acls.yml

acls:
    # -------------------------------------------------------
    # Entity permission: VIEW on Favorite
    # -------------------------------------------------------
    acme_demo_favorite_index:
        type:       entity                                  # 'entity' or 'action'
        class:      Acme\Bundle\DemoBundle\Entity\Favorite  # Full entity class
        permission: VIEW                                    # Permission being checked

    # -------------------------------------------------------
    # Entity permission: EDIT with controller binding
    # The binding associates this ACL resource with a specific
    # controller method without using PHP attributes.
    # -------------------------------------------------------
    acme_demo_favorite_edit:
        type:       entity
        class:      Acme\Bundle\DemoBundle\Entity\Favorite
        permission: EDIT
        bindings:
            - class:  Acme\Bundle\DemoBundle\Controller\FavoriteController
              method: editAction      # Method name (without parentheses)
            - class:  Acme\Bundle\DemoBundle\Controller\FavoriteController
              method: newEditAction   # Multiple bindings are allowed

    # -------------------------------------------------------
    # Action permission: protects a non-entity capability.
    # Use this for features like "can export reports",
    # "can access integration settings", etc.
    # -------------------------------------------------------
    acme_demo_favorite_export:
        type: action                  # No 'class' or 'permission' needed
        bindings:
            - class:  Acme\Bundle\DemoBundle\Controller\FavoriteController
              method: exportAction

    # -------------------------------------------------------
    # Entity permission with group_name for storefront ACLs.
    # group_name scopes this ACL to a specific application area.
    # -------------------------------------------------------
    acme_demo_product_storefront_view:
        type:       entity
        class:      Acme\Bundle\DemoBundle\Entity\Product
        permission: VIEW
        group_name: commerce          # Scopes to OroCommerce storefront
```

### YAML acls.yml Top-Level Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | Yes | `'entity'` or `'action'` |
| `class` | string | If type=entity | Fully qualified entity class name |
| `permission` | string | If type=entity | `VIEW`, `CREATE`, `EDIT`, `DELETE`, `ASSIGN`, `SHARE` |
| `group_name` | string | No | Application group scope (`''` = backend, `'commerce'` = storefront) |
| `bindings` | array | No | Controller class+method pairs to associate with this ACL |
| `bindings[].class` | string | Yes (in binding) | Fully qualified controller class name |
| `bindings[].method` | string | Yes (in binding) | Action method name |

**WHY use bindings instead of attributes:** YAML bindings are useful when you cannot or do not want to modify the controller class (e.g., overriding a vendor controller without subclassing it).

---

## Protecting Action-Type Resources

Action ACLs protect capabilities that are not tied to a specific entity — for example, "access to the import/export menu" or "ability to view integration status."

### PHP Attribute Approach

```php
#[Route(path: '/protected', name: 'protected')]
#[Acl(
    id:   'acme_demo_protected_action',
    type: 'action'  // No class or permission parameters
)]
public function protectedAction(): Response
{
    // Only users with EXECUTE permission on this action can reach this
}
```

### Check an Action ACL in Code

```php
// Check by ACL resource ID (action type)
if (!$this->isGranted('acme_demo_protected_action')) {
    throw new AccessDeniedException();
}
```

---

## Datagrid Protection

Protect a datagrid by referencing an ACL resource ID:

```yaml
# Resources/config/oro/datagrids.yml
datagrids:
    acme-demo-favorite-grid:
        extended_entity_name: Acme\Bundle\DemoBundle\Entity\Favorite
        acl_resource: acme_demo_favorite_index  # References ACL resource ID
        source:
            type: orm
            query:
                select: [f]
                from:
                    - { table: Acme\Bundle\DemoBundle\Entity\Favorite, alias: f }
```

**WHY protect datagrids:** Without `acl_resource`, the datagrid data is accessible to anyone who knows the URL, even if the page itself is protected. The `acl_resource` check runs before query execution.

---

## Protecting DQL Queries with AclHelper

For repository queries, use `AclHelper` to automatically add ownership WHERE clauses based on the current user's access level:

```php
use Oro\Bundle\SecurityBundle\ORM\Walker\AclHelper;

class FavoriteRepository extends EntityRepository
{
    public function findAccessibleFavorites(AclHelper $aclHelper): array
    {
        $qb = $this->createQueryBuilder('f')
            ->where('f.viewCount > :count')
            ->setParameter('count', 0)
            ->orderBy('f.createdAt', 'DESC');

        // AclHelper modifies the query to only return records
        // the current user has VIEW permission for, based on their
        // access level (User/BU/Division/Org/Global).
        $query = $aclHelper->apply($qb, 'VIEW');

        return $query->getResult();
    }
}
```

**WHY use AclHelper:** Without it, a user with `LOCAL_LEVEL` VIEW could potentially retrieve records they should not see if the query lacks manual ownership filtering. `AclHelper` makes the filtering automatic and role-driven.

---

## Manual Access Checks in PHP

### In Controllers (using AbstractController shortcut)

```php
// Check entity instance access
if (!$this->isGranted('VIEW', $favoriteEntity)) {
    throw new AccessDeniedException();
}

// Check class-level access (no specific instance)
if (!$this->isGranted('CREATE', 'entity:' . Favorite::class)) {
    throw new AccessDeniedException();
}

// Check action ACL resource
if (!$this->isGranted('acme_demo_protected_action')) {
    throw new AccessDeniedException();
}
```

### Using AuthorizationChecker Service

```php
use Symfony\Component\Security\Core\Authorization\AuthorizationCheckerInterface;
use Symfony\Component\Security\Acl\Voter\FieldVote;

class FavoriteService
{
    public function __construct(
        private readonly AuthorizationCheckerInterface $authorizationChecker
    ) {}

    public function checkAccess(Favorite $favorite): void
    {
        // Check specific object instance
        if (!$this->authorizationChecker->isGranted('VIEW', $favorite)) {
            throw new AccessDeniedException();
        }

        // Check entity class (not a specific instance)
        if (!$this->authorizationChecker->isGranted(
            'VIEW',
            'entity:' . Favorite::class
        )) {
            throw new AccessDeniedException();
        }

        // Check field-level access
        if (!$this->authorizationChecker->isGranted(
            'VIEW',
            new FieldVote($favorite, 'secretField')
        )) {
            throw new AccessDeniedException('Field access denied');
        }
    }
}
```

### Authorization Check Sequence

When `isGranted()` is called with an entity object, Oro checks in this order:
1. **Object-scope** — Is there a specific ACL entry for this exact instance?
2. **Class-scope** — Is there an ACL entry for the entity class?
3. **Default permissions** — Fall back to configured defaults.

---

## Complete Real-World Entity Setup Example

This shows a complete implementation for a `CustomerNote` entity that belongs to a specific user within an organization.

### Entity Class

```php
<?php

namespace Acme\Bundle\DemoBundle\Entity;

use Doctrine\ORM\Mapping as ORM;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\Config;
use Oro\Bundle\OrganizationBundle\Entity\Organization;
use Oro\Bundle\UserBundle\Entity\User;

#[ORM\Entity]
#[ORM\Table(name: 'acme_customer_note')]
#[Config(
    defaultValues: [
        'security' => [
            'type'        => 'ACL',
            'permissions' => 'VIEW;CREATE;EDIT;DELETE',  // No ASSIGN or SHARE
            'group_name'  => '',
            'category'    => 'account_management'
        ],
        'ownership' => [
            'owner_type'               => 'USER',
            'owner_field_name'         => 'owner',
            'owner_column_name'        => 'user_owner_id',
            'organization_field_name'  => 'organization',
            'organization_column_name' => 'organization_id'
        ]
    ]
)]
class CustomerNote
{
    #[ORM\ManyToOne(targetEntity: User::class)]
    #[ORM\JoinColumn(name: 'user_owner_id', referencedColumnName: 'id')]
    private ?User $owner = null;

    #[ORM\ManyToOne(targetEntity: Organization::class)]
    #[ORM\JoinColumn(name: 'organization_id', referencedColumnName: 'id')]
    private ?Organization $organization = null;

    // ... other fields
}
```

### Controller

```php
<?php

namespace Acme\Bundle\DemoBundle\Controller;

use Acme\Bundle\DemoBundle\Entity\CustomerNote;
use Oro\Bundle\SecurityBundle\Attribute\Acl;
use Oro\Bundle\SecurityBundle\Attribute\AclAncestor;
use Symfony\Component\Routing\Attribute\Route;

#[Route(path: '/customer-note', name: 'acme_demo_customer_note_')]
class CustomerNoteController extends AbstractController
{
    #[Route(path: '/', name: 'index')]
    #[Acl(id: 'acme_demo_customer_note_index', type: 'entity',
          class: CustomerNote::class, permission: 'VIEW')]
    public function indexAction(): array
    {
        return [];
    }

    #[Route(path: '/new', name: 'create')]
    #[Acl(id: 'acme_demo_customer_note_create', type: 'entity',
          class: CustomerNote::class, permission: 'CREATE')]
    public function createAction(): Response { /* ... */ }

    #[Route(path: '/{id}/edit', name: 'update')]
    #[Acl(id: 'acme_demo_customer_note_update', type: 'entity',
          class: CustomerNote::class, permission: 'EDIT')]
    public function updateAction(CustomerNote $note): Response { /* ... */ }

    // Reuses the update ACL — no new ACL resource needed
    #[Route(path: '/quick-edit', name: 'quick_update')]
    #[AclAncestor('acme_demo_customer_note_update')]
    public function quickUpdateAction(): Response { /* ... */ }
}
```

### acls.yml (equivalent YAML definition)

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/acls.yml
acls:
    acme_demo_customer_note_index:
        type:       entity
        class:      Acme\Bundle\DemoBundle\Entity\CustomerNote
        permission: VIEW

    acme_demo_customer_note_create:
        type:       entity
        class:      Acme\Bundle\DemoBundle\Entity\CustomerNote
        permission: CREATE

    acme_demo_customer_note_update:
        type:       entity
        class:      Acme\Bundle\DemoBundle\Entity\CustomerNote
        permission: EDIT
        bindings:
            - class:  Acme\Bundle\DemoBundle\Controller\CustomerNoteController
              method: updateAction
            - class:  Acme\Bundle\DemoBundle\Controller\CustomerNoteController
              method: quickUpdateAction  # Both methods share the same ACL
```

---

## Common Mistakes and How to Avoid Them

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Duplicate `id` values across bundles | ACLs silently merge, permissions behave unexpectedly | Always prefix IDs with bundle name: `acme_demo_*` |
| Missing `organization_field_name` with USER/BU ownership | Records not scoped to organization; cross-org data leaks | Always include both owner and organization fields for USER and BUSINESS_UNIT |
| Changing ownership type after entity creation | Data inconsistency; existing records have no owner in the new type's context | Treat ownership type as immutable; plan before first deployment |
| Not protecting the datagrid `acl_resource` | Grid data accessible even when the page is blocked | Always add `acl_resource` to datagrids that return protected entity data |
| Using `isGranted('VIEW', Favorite::class)` (string, not object) | Always passes — Symfony treats a plain class string as a role | Use `'entity:' . Favorite::class` for class-level checks |
