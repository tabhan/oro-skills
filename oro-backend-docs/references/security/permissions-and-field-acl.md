# OroCommerce: Custom Permissions, Field ACL, Configurable Permissions, Access Rules, and CSRF

> Source: https://doc.oroinc.com/master/backend/security/field-acl/

## AGENT QUERY HINTS

Use this file when answering questions like:
- "How do I define a custom permission in Oro?"
- "How do I restrict access to a specific field on an entity?"
- "What is field ACL and how do I enable it?"
- "How do I check if a user can see a specific field?"
- "What are configurable permissions?"
- "How do I hide a permission from the role editor UI?"
- "What are access rules and how do they differ from ACLs?"
- "How do I add a WHERE clause to queries based on access control?"
- "How do I protect AJAX endpoints from CSRF attacks?"
- "What is the #[CsrfProtection] attribute?"
- "How do I limit what permissions appear in the role editor?"
- "How do I create a custom permission that applies to specific entities?"
- "What is the permissions.yml file?"

---

## Part 1: Custom Permissions

### What Are Custom Permissions?

Custom permissions extend Oro's standard permission set (VIEW, CREATE, EDIT, DELETE, ASSIGN) with application-specific capabilities that can be tied to entities. They appear in the role editor alongside standard permissions.

**WHY custom permissions exist:** Standard CRUD permissions do not cover business-specific capabilities like "can approve orders", "can view pricing", or "can export customer data". Custom permissions let you model these domain concepts in the permission system without hacking the entity ACL.

### Defining Custom Permissions

Create `permissions.yml` in your bundle's `Resources/config/oro/` directory:

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/permissions.yml

oro_permissions:
    # -------------------------------------------------------
    # Basic custom permission applying to all entities by default.
    # -------------------------------------------------------
    APPROVE_ORDERS:
        label: 'Approve Orders'
        description: 'Ability to approve pending orders'
        apply_to_all: true          # Apply to all entities (default behavior)
        group_names:
            - default               # Appears in the backend role editor

    # -------------------------------------------------------
    # Permission scoped to specific entity classes only.
    # apply_to_all: false means it ONLY applies to listed entities.
    # -------------------------------------------------------
    VIEW_PRICING:
        label:            'View Pricing Information'
        description:      'Grants access to wholesale pricing data'
        apply_to_all:     false
        apply_to_entities:
            - 'Acme\Bundle\DemoBundle\Entity\PriceList'
            - 'Acme\Bundle\DemoBundle\Entity\ProductPrice'
        group_names:
            - default
            - frontend               # Also visible in storefront role editor

    # -------------------------------------------------------
    # Permission applied via interface — any entity implementing
    # ExportableInterface automatically gets this permission.
    # -------------------------------------------------------
    EXPORT_DATA:
        label: 'Export Data'
        apply_to_all:         false
        apply_to_interfaces:
            - 'Acme\Bundle\DemoBundle\Entity\ExportableInterface'
        exclude_entities:
            - 'Acme\Bundle\DemoBundle\Entity\SensitiveReport'
        group_names:
            - default

    # -------------------------------------------------------
    # Storefront-only permission (commerce group).
    # -------------------------------------------------------
    REORDER:
        label:      'Allow Reorder'
        apply_to_all: true
        group_names:
            - commerce              # Only in OroCommerce storefront roles
```

### permissions.yml Parameter Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | string | Required | Display name in the role editor UI |
| `description` | string | `''` | Optional tooltip/help text in role editor |
| `apply_to_all` | boolean | `true` | If true, applies to all entities; if false, only to listed entities |
| `apply_to_entities` | array | `[]` | Whitelist of entity class names to apply this permission to |
| `apply_to_interfaces` | array | `[]` | Interfaces — implementing entities automatically receive this permission |
| `exclude_entities` | array | `[]` | Blacklist of entity classes explicitly excluded from this permission |
| `group_names` | array | `['default']` | Role editor groups where this permission appears (`default`, `commerce`) |

**Permission Naming Rules:** Names must start with a letter, digit, or underscore, and may only contain letters, digits, numbers, underscores (`_`), hyphens (`-`), and colons (`:`).

### Configuration Merging

When multiple bundles define a permission with the same name, they are merged at boot time:
- **Scalar values** (label, description, apply_to_all): later bundle's value replaces earlier ones.
- **Array values** (apply_to_entities, exclude_entities, group_names): arrays are combined (union).

This allows a core bundle to define `VIEW_PRICING` and a commerce bundle to extend its `apply_to_entities` list without overriding.

### Loading Permissions into the Database

After defining permissions, load them with:

```bash
php bin/console security:permission:configuration:load

# Load specific permissions only:
php bin/console security:permission:configuration:load --permissions APPROVE_ORDERS,VIEW_PRICING
```

### Checking Custom Permissions in PHP

```php
use Symfony\Component\Security\Core\Authorization\AuthorizationCheckerInterface;

class OrderService
{
    public function __construct(
        private readonly AuthorizationCheckerInterface $authorizationChecker
    ) {}

    public function approveOrder(Order $order): void
    {
        // Check custom permission on a specific entity instance
        if (!$this->authorizationChecker->isGranted('APPROVE_ORDERS', $order)) {
            throw new AccessDeniedException('You cannot approve orders.');
        }
        // ... approval logic
    }
}
```

### Checking Custom Permissions in Twig

```twig
{% if is_granted('VIEW_PRICING', product) %}
    <span class="price">{{ product.price }}</span>
{% endif %}
```

---

## Part 2: Field-Level ACL

### What Is Field ACL?

Field ACL restricts access to individual fields within an entity. Even if a user can VIEW the entity, they may be blocked from seeing or editing specific fields (e.g., credit limit, internal notes, cost price).

Field ACL supports three permissions: **VIEW**, **CREATE**, and **EDIT**.

**WHY field ACL exists:** Entities often contain a mix of public and sensitive data. Rather than duplicating entities to create a "restricted version", field ACL lets you mark specific fields as protected and check access per field in templates and forms.

### Step 1: Enable Field ACL Support on the Entity

Add `field_acl_supported` to the entity's security config:

```php
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\Config;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\ConfigField;

#[Config(
    defaultValues: [
        'security' => [
            'type'                => 'ACL',
            'permissions'         => 'All',
            'field_acl_supported' => true,   // Enables field ACL for this entity
        ]
    ]
)]
class Favorite
{
    /**
     * This field is visible to all who can VIEW the entity.
     * No field-level restriction needed.
     */
    private string $name;

    /**
     * This field has restricted permissions.
     * Only VIEW and CREATE are available; EDIT is not.
     * WHY: The viewCount should be set on creation but not edited afterward.
     */
    #[ConfigField(
        defaultValues: [
            'security' => [
                'permissions' => 'VIEW;CREATE'  // Semicolon-separated
            ]
        ]
    )]
    private int $viewCount;

    /**
     * This field has full field ACL (all three: VIEW, CREATE, EDIT).
     * When field ACL is enabled without field-level restriction,
     * the default is to allow all three.
     */
    #[ConfigField(
        defaultValues: [
            'security' => [
                'permissions' => 'All'
            ]
        ]
    )]
    private string $secretNote;
}
```

### Step 2: Enable Field ACL on the Entity (via Migration)

For entities you don't control (vendor entities), enable field ACL via a migration:

```php
use Oro\Bundle\EntityBundle\Migrations\Schema\OroEntityExtendExtension;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;
use Oro\Bundle\EntityConfigBundle\Migration\UpdateEntityConfigEntityValueQuery;

class EnableFieldAcl implements Migration
{
    public function up(Schema $schema, QueryBag $queries): void
    {
        $queries->addPostQuery(
            new UpdateEntityConfigEntityValueQuery(
                'Vendor\Bundle\Entity\SomeEntity',
                'security',
                'field_acl_supported',
                true
            )
        );
    }
}
```

### Step 3: Check Field Access in PHP

Use `FieldVote` with the `security.authorization_checker` service:

```php
use Symfony\Component\Security\Acl\Voter\FieldVote;

class FavoriteService
{
    public function __construct(
        private readonly AuthorizationCheckerInterface $authorizationChecker
    ) {}

    public function getSecretNote(Favorite $favorite): ?string
    {
        if (!$this->authorizationChecker->isGranted(
            'VIEW',
            new FieldVote($favorite, 'secretNote')
        )) {
            return null; // or throw AccessDeniedException
        }

        return $favorite->getSecretNote();
    }
}
```

### Checking Field Access Without an Entity Instance

When you have only the class name and ID (not a loaded entity):

```php
use Oro\Bundle\SecurityBundle\Acl\Domain\DomainObjectReference;
use Symfony\Component\Security\Acl\Voter\FieldVote;

$entityReference = new DomainObjectReference(
    Favorite::class,  // class name
    $id,              // entity ID
    $ownerId,         // owner user ID
    $orgId            // organization ID
);

$isGranted = $this->authorizationChecker->isGranted(
    'VIEW',
    new FieldVote($entityReference, 'secretNote')
);
```

**WHY use DomainObjectReference:** Avoids loading the full entity from the database just to perform an ACL check. Useful in listings where you have IDs but not full objects.

### Step 4: Check Field Access in Twig Templates

```twig
{# Standard field access check #}
{% if is_granted('VIEW', entity, 'secretNote') %}
    <p>{{ entity.secretNote }}</p>
{% endif %}

{# Edit form field visibility #}
{% if is_granted('EDIT', entity, 'viewCount') %}
    {{ form_widget(form.viewCount) }}
{% else %}
    <span>{{ entity.viewCount }}</span>  {# Read-only display #}
{% endif %}
```

### Field ACL Behavior Options

Once field ACL is enabled on an entity, the admin UI gains two additional toggles per entity:

| Option | Effect |
|--------|--------|
| **Field Level ACL** | Master switch — enables/disables field-level protection on this entity |
| **Show Restricted** | If enabled, restricted fields appear as read-only on create/edit pages instead of being hidden entirely |

**WHY "Show Restricted" exists:** Completely hiding a field from an edit form can confuse users ("where did the credit limit field go?"). Showing it as read-only communicates that the field exists but they cannot edit it.

---

## Part 3: Configurable Permissions

### What Are Configurable Permissions?

Configurable Permissions control which permissions *appear in the role editor UI* for administrators. They do not add new permissions — they show or hide existing ones.

**WHY they exist:** On complex applications, the role editor can become overwhelming with hundreds of entity+permission combinations. Configurable permissions let you hide irrelevant options (e.g., hiding SHARE permission on all entities for a non-Enterprise install) to keep the UI manageable.

### Defining Configurable Permissions

Create `configurable_permissions.yml` in `Resources/config/oro/`:

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/configurable_permissions.yml

oro_configurable_permissions:
    # -------------------------------------------------------
    # Named configuration block. The name must be unique
    # across the application (prefix with bundle name).
    # -------------------------------------------------------
    acme_demo_permissions:

        # Master switch: if true, ALL permissions for this config
        # block are shown by default (unless overridden below).
        default: true

        # Per-entity overrides. Setting a permission to false
        # HIDES it from the role editor for that entity.
        entities:
            Acme\Bundle\DemoBundle\Entity\Favorite:
                VIEW:   true    # Show VIEW in role editor
                CREATE: true    # Show CREATE
                EDIT:   true    # Show EDIT
                DELETE: false   # HIDE DELETE from role editor
                ASSIGN: false   # HIDE ASSIGN from role editor

            Acme\Bundle\DemoBundle\Entity\ReadOnlyEntity:
                VIEW:   true
                CREATE: false   # Users cannot be given CREATE permission
                EDIT:   false
                DELETE: false

        # Capability-level overrides (non-entity action permissions)
        capabilities:
            oro_acme_some_capability: false    # Hide this action from role editor

        # Workflow permission overrides
        workflows:
            acme_order_approval_flow:
                PERFORM_TRANSIT: false         # Hide workflow transition permission
```

### Configurable Permissions Parameter Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `default` | boolean | `false` | If `true`, all permissions for this config block are shown by default |
| `entities` | object or boolean | `{}` | Map of entity class → permission → boolean visibility |
| `capabilities` | object | `{}` | Map of capability ID → boolean visibility |
| `workflows` | object or boolean | `{}` | Map of workflow identity → permission → boolean visibility |

### ConfigurablePermission Model Methods

The system exposes these programmatic checks:

```php
// Injected via service container
$configurablePermission = $container->get('oro_security.configurable_permission');

// Is this entity+permission combination shown in the role editor?
$show = $configurablePermission->isEntityPermissionConfigurable(
    Favorite::class,
    'DELETE'
);

// Is this workflow permission shown?
$show = $configurablePermission->isWorkflowPermissionConfigurable(
    'acme_order_approval_flow',
    'PERFORM_TRANSIT'
);

// Is this action capability shown?
$show = $configurablePermission->isCapabilityConfigurable(
    'oro_acme_some_capability'
);
```

### Configuration Merging

Multiple bundles can define configurations with the same name — they merge at boot:
- **Scalar values** (default): last bundle wins.
- **Array values** (entities, capabilities, workflows): arrays are merged (combined), not replaced.

---

## Part 4: Access Rules

### What Are Access Rules?

Access Rules are a programmatic mechanism that modifies ORM and search queries *before execution* to enforce access control at the database level. Instead of fetching data and then filtering it, Access Rules add WHERE clauses to prevent unauthorized records from ever being retrieved.

**WHY Access Rules exist:** Standard ACL checks on object instances require loading the objects first. For large datasets, this is expensive. Access Rules work at the query level — the database does the filtering, and only allowed records cross the wire.

**Difference from ACL checks:**
- ACL checks: "Can this user perform action X on this specific loaded object?"
- Access Rules: "What condition must be true in the WHERE clause for this user to see any records at all?"

### How Access Rules Work Internally

```
Repository query builder
    → AclHelper.apply()
        → AccessRuleWalker (modifies query AST)
            → Evaluates all registered AccessRule classes
                → Each rule adds expressions to Criteria
                    → Criteria expressions become WHERE clauses
```

The `AclHelper::apply()` call is what triggers the entire access rule pipeline.

### Creating a Custom Access Rule

Implement `AccessRuleInterface`:

```php
<?php

namespace Acme\Bundle\DemoBundle\AccessRule;

use Oro\Bundle\SecurityBundle\AccessRule\AccessRuleInterface;
use Oro\Bundle\SecurityBundle\AccessRule\Criteria;
use Oro\Bundle\SecurityBundle\AccessRule\Expr\Comparison;
use Oro\Bundle\SecurityBundle\AccessRule\Expr\CompositeExpression;
use Oro\Bundle\SecurityBundle\AccessRule\Expr\Path;
use Oro\Bundle\SecurityBundle\AccessRule\Expr\Value;

class FavoriteAccessRule implements AccessRuleInterface
{
    public function __construct(
        private readonly TokenStorageInterface $tokenStorage
    ) {}

    /**
     * Determines whether this rule should be applied to the given query criteria.
     * Return false to skip this rule entirely for certain query contexts.
     */
    public function isApplicable(Criteria $criteria): bool
    {
        // Only apply to ORM queries, not search queries
        return $criteria->getType() === Criteria::ORM_RULES_TYPE;
    }

    /**
     * Adds access restriction expressions to the criteria.
     * These become additional WHERE clause conditions.
     */
    public function process(Criteria $criteria): void
    {
        $token = $this->tokenStorage->getToken();
        if ($token === null) {
            return;
        }

        $user = $token->getUser();

        // Restrict results to Favorites owned by the current user
        // This adds: WHERE favorite.owner_id = :currentUserId
        $criteria->andExpression(
            new Comparison(
                new Path('owner'),   // Entity field path
                Comparison::EQ,
                new Value($user->getId())
            )
        );
    }
}
```

### Registering an Access Rule as a Service

```yaml
# Resources/config/services.yml
services:
    acme_demo.access_rule.favorite:
        class: Acme\Bundle\DemoBundle\AccessRule\FavoriteAccessRule
        arguments:
            - '@security.token_storage'
        tags:
            - name:        oro_security.access_rule
              type:        ORM                                       # ORM or Search
              entityClass: Acme\Bundle\DemoBundle\Entity\Favorite    # Target entity
```

### Service Tag Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `name` | Yes | Must be `oro_security.access_rule` |
| `type` | No | `ORM` (default) or `Search` — which query type this rule applies to |
| `permission` | No | Restrict rule to a specific permission (e.g., `VIEW`) |
| `entityClass` | No | Limit rule to a specific entity class |
| `loggedUserClass` | No | Limit rule to a specific user class type |

### Expression Types Available in Access Rules

| Expression | SQL Equivalent | Example |
|-----------|----------------|---------|
| `Comparison` (EQ) | `field = value` | `owner_id = 5` |
| `Comparison` (NEQ) | `field <> value` | `status <> 'deleted'` |
| `Comparison` (IN) | `field IN (...)` | `status IN ('active', 'pending')` |
| `Comparison` (NIN) | `field NOT IN (...)` | `type NOT IN ('draft')` |
| `Comparison` (CONTAINS) | `field LIKE '%value%'` | `name LIKE '%test%'` |
| `NullComparison` | `field IS NULL / IS NOT NULL` | `deleted_at IS NULL` |
| `CompositeExpression` | `AND / OR` | Multiple conditions |
| `AccessDenied` | Always-false condition | Deny all results |
| `Exists` | `EXISTS (subquery)` | Subquery existence check |

### Combining Expressions

```php
public function process(Criteria $criteria): void
{
    // AND: both conditions must be true
    $criteria->andExpression(
        new Comparison(new Path('status'), Comparison::EQ, new Value('active'))
    );

    // Multiple ANDs
    $criteria->andExpression(
        new CompositeExpression(
            CompositeExpression::TYPE_OR,  // OR within this composite
            [
                new Comparison(new Path('owner'), Comparison::EQ, new Value($userId)),
                new Comparison(new Path('shared'), Comparison::EQ, new Value(true))
            ]
        )
    );
}
```

**Important:** OR expressions should be added with the lowest priority (last) to prevent logical operation inversion with other rules' AND conditions.

### AccessRuleWalker Configuration Options

When calling `AclHelper::apply()`, you can pass options to control behavior:

```php
use Oro\Bundle\SecurityBundle\ORM\Walker\AclHelper;
use Oro\Bundle\SecurityBundle\ORM\Walker\AclWalkerContext;

$context = new AclWalkerContext();
$context->setOption('checkRootEntity', true);   // Check ACL on the root entity (default: true)
$context->setOption('checkRelations', false);    // Skip ACL on joined relations (default: true)

$query = $aclHelper->apply($queryBuilder, 'VIEW', $context);
```

### Access Rule Behavior Options

Custom options can be passed through criteria to modify rule behavior:

| Option | Description |
|--------|-------------|
| `aclDisable` | Disable ACL checking entirely for this query |
| `aclCheckOwner` | Override whether ownership is checked |
| `aclParentClass` | Use a parent entity's ACL for the current entity |
| `aclParentField` | Field on the current entity referencing the parent |
| `availableOwnerEnable` | Enable available-owner filtering |
| `availableOwnerTargetEntityClass` | Entity class for available-owner filtering |
| `availableOwnerCurrentOwner` | Current owner value for comparison |

---

## Part 5: CSRF Protection

### What Is CSRF and Why Does Oro Protect Against It?

Cross-Site Request Forgery (CSRF) tricks authenticated users into unknowingly submitting requests to the application. An attacker embeds a malicious link or form on another site; when the victim clicks it, their browser sends a valid session cookie — making the request appear legitimate.

**WHY Oro implements its own CSRF layer:** Standard Symfony CSRF uses form tokens embedded in HTML forms. AJAX requests (which Oro uses extensively for its admin interface) don't use traditional form submissions, requiring a different mechanism.

### Oro's CSRF Implementation: Double Submit Cookie

Oro uses the **Double Submit Cookie** pattern (OWASP standard):

1. A CSRF token is generated and stored in a cookie (`_csrf` for HTTP, `https-_csrf` for HTTPS).
2. Every AJAX request must include the same token value in the `X-CSRF-Header` HTTP header.
3. The server compares the cookie value with the header value. They must match.

Since cookies are same-origin only, an attacker site cannot read the cookie value and therefore cannot set the correct header.

**The `X-CSRF-Header` is added automatically to all Oro AJAX requests** — JavaScript does not need to do this manually for standard `$.ajax()` calls within Oro's framework.

### Protecting Controllers with #[CsrfProtection]

Import from `Oro\Bundle\SecurityBundle\Attribute\CsrfProtection`.

#### Class-Level Protection (all actions in controller)

```php
use Oro\Bundle\SecurityBundle\Attribute\CsrfProtection;
use Symfony\Component\Routing\Attribute\Route;

#[Route(path: '/favorite', name: 'acme_demo_favorite_')]
#[CsrfProtection]  // All actions in this controller require CSRF validation
class FavoriteController extends AbstractController
{
    #[Route(path: '/toggle', name: 'toggle', methods: ['POST'])]
    public function toggleAction(Request $request): JsonResponse
    {
        // CSRF automatically validated before reaching here
        return new JsonResponse(['success' => true]);
    }

    #[Route(path: '/bulk-delete', name: 'bulk_delete', methods: ['POST'])]
    public function bulkDeleteAction(Request $request): JsonResponse
    {
        // Also CSRF protected
        return new JsonResponse(['deleted' => true]);
    }
}
```

#### Action-Level Protection (single action)

```php
class FavoriteController extends AbstractController
{
    // This action has no CSRF protection
    #[Route(path: '/', name: 'index')]
    public function indexAction(): array
    {
        return [];
    }

    // Only this action requires CSRF validation
    #[Route(path: '/toggle', name: 'toggle', methods: ['POST'])]
    #[CsrfProtection]
    public function toggleAction(Request $request): JsonResponse
    {
        return new JsonResponse(['success' => true]);
    }
}
```

### CSRF Token Storage

| Connection Type | Cookie Name |
|----------------|-------------|
| HTTP | `_csrf` |
| HTTPS | `https-_csrf` |

The cookie is set automatically by Oro's security layer. The JavaScript layer reads it and injects it as `X-CSRF-Header` in every AJAX request.

### When to Apply CSRF Protection

Apply `#[CsrfProtection]` to:
- Any POST endpoint that changes state (create, update, delete, toggle)
- Any AJAX endpoint that performs sensitive operations
- API endpoints called from the browser (not server-to-server)

Do NOT apply to:
- GET endpoints (state-changing GETs are an anti-pattern; fix the route instead)
- Server-to-server API endpoints (use API key authentication instead)
- Webhooks from external services (they cannot read cookies)

### Combining ACL and CSRF Protection

Both attributes can be applied together:

```php
#[Route(path: '/delete/{id}', name: 'delete', methods: ['POST'])]
#[Acl(id: 'acme_demo_favorite_delete', type: 'entity',
      class: Favorite::class, permission: 'DELETE')]
#[CsrfProtection]
public function deleteAction(int $id): JsonResponse
{
    // ACL checked first (is user allowed to delete?)
    // CSRF validated second (is this a legitimate browser request?)
    // ...
}
```

---

## Quick Reference: Which Mechanism to Use?

| Scenario | Use |
|----------|-----|
| Block access to a controller action | `#[Acl]` attribute or `acls.yml` binding |
| Block access to an entity class | `#[Config]` with `security.type = ACL` + `#[Acl]` on controller |
| Block access to a specific field | Field ACL with `#[ConfigField]` + `FieldVote` check |
| Hide a permission from role editor | Configurable Permissions (`configurable_permissions.yml`) |
| Filter database query results by ownership | `AclHelper::apply()` |
| Add custom WHERE logic to all queries on an entity | Custom `AccessRuleInterface` implementation |
| Protect AJAX POST endpoints from CSRF | `#[CsrfProtection]` attribute |
| Add a non-CRUD business capability to roles | Custom Permissions (`permissions.yml`) |
