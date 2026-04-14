# OroCommerce acls.yml — ACL Resource Configuration

> Source: https://doc.oroinc.com/master/backend/configuration/yaml/acls/

---

## AGENT QUERY HINTS

Use this file when:
- "How do I define ACL resources in YAML?"
- "What is the structure of acls.yml?"
- "How do I protect controller actions with YAML-based ACL?"
- "What is the difference between entity and action ACL types?"
- "How do I use bindings in acls.yml?"
- "How do I define ACL categories?"
- "What is the relationship between acls.yml and #[Acl] attribute?"

---

## Core Concept: WHY acls.yml Exists

While PHP 8 `#[Acl]` attributes can define ACL resources directly on controller methods, YAML-based ACL configuration offers advantages:

1. **Separation of concerns** — Security declarations are isolated from business logic
2. **Override capability** — ACLs can be modified without touching controller code
3. **Cross-bundle configuration** — Single file can define ACLs for multiple controllers
4. **Bulk configuration** — Easier to audit all security declarations in one place

**Recommendation:** Use YAML for complex ACL setups, when overriding vendor ACLs, or when security declarations should be managed separately from code.

---

## File Location

```
src/
└── Acme/
    └── Bundle/
        └── DemoBundle/
            └── Resources/
                └── config/
                    └── oro/
                        └── acls.yml           ← place here
```

---

## Minimal ACL Configuration

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/acls.yml
acls:
    acme_demo_document_view:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: VIEW
```

---

## Complete Configuration Structure

```yaml
acls:
    acl_resource_id:                       # Unique identifier across application
        type: entity|action                 # REQUIRED
        class: Entity\Class                 # REQUIRED if type=entity
        permission: VIEW|CREATE|EDIT|DELETE|ASSIGN|SHARE  # REQUIRED if type=entity
        label: acl.label.translation.key   # Optional: UI display label
        group_name: ''                      # Optional: Application group (commerce, etc.)
        category: category_name             # Optional: Category for role UI
        bindings:                           # Optional: Link to controller methods
            - class: Controller\Class
              method: methodName
```

---

## Entity ACL Type

Entity ACLs protect access to Doctrine entities. They check permissions at both class and instance level.

### Basic Entity ACL

```yaml
acls:
    acme_demo_document_view:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: VIEW
```

### Entity ACL with Bindings

```yaml
acls:
    acme_demo_document_edit:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: EDIT
        bindings:
            - class: Acme\Bundle\DemoBundle\Controller\DocumentController
              method: editAction
            - class: Acme\Bundle\DemoBundle\Controller\DocumentController
              method: quickEditAction
```

**WHY bindings:** Without bindings, the ACL exists but isn't automatically enforced on any controller. Bindings connect the ACL resource to specific controller methods, enabling automatic permission checks before the action executes.

### All CRUD Permissions

```yaml
acls:
    acme_demo_document_index:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: VIEW
        
    acme_demo_document_create:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: CREATE
        
    acme_demo_document_edit:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: EDIT
        
    acme_demo_document_delete:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: DELETE
        
    acme_demo_document_assign:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: ASSIGN
        
    acme_demo_document_share:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: SHARE
```

### Permission Types Reference

| Permission | Description | Typical Use |
|------------|-------------|-------------|
| `VIEW` | Read/list records | Index pages, view pages, datagrids |
| `CREATE` | Create new records | Create forms, new actions |
| `EDIT` | Modify existing records | Edit forms, update actions |
| `DELETE` | Remove records | Delete actions, mass delete |
| `ASSIGN` | Reassign ownership | Transfer to another user/BU |
| `SHARE` | Share with other users | Collaboration features |

---

## Action ACL Type

Action ACLs protect capabilities not tied to a specific entity — feature toggles, system operations, non-entity workflows.

```yaml
acls:
    acme_demo_system_configuration:
        type: action
        label: acme.demo.system_configuration.label
        category: system
        bindings:
            - class: Acme\Bundle\DemoBundle\Controller\ConfigurationController
              method: indexAction
              
    acme_demo_export_data:
        type: action
        label: acme.demo.export_data.label
        group_name: ''
        bindings:
            - class: Acme\Bundle\DemoBundle\Controller\ExportController
              method: exportAction
```

**WHY action type:** When a permission controls access to functionality rather than data (e.g., "can export reports", "can access integration settings"), use `type: action`. No entity class or permission level needed.

---

## Bindings Configuration

Bindings connect ACL resources to controller methods. Multiple bindings allow one ACL to protect multiple actions.

### Single Binding

```yaml
acls:
    acme_demo_document_edit:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: EDIT
        bindings:
            - class: Acme\Bundle\DemoBundle\Controller\DocumentController
              method: editAction
```

### Multiple Bindings (Shared Permission)

```yaml
acls:
    acme_demo_document_edit:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: EDIT
        bindings:
            # All these methods share the same EDIT permission check
            - class: Acme\Bundle\DemoBundle\Controller\DocumentController
              method: editAction
            - class: Acme\Bundle\DemoBundle\Controller\DocumentController
              method: quickEditAction
            - class: Acme\Bundle\DemoBundle\Controller\DocumentController
              method: inlineEditAction
```

### Cross-Controller Bindings

```yaml
acls:
    acme_demo_document_view:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: VIEW
        bindings:
            - class: Acme\Bundle\DemoBundle\Controller\DocumentController
              method: indexAction
            - class: Acme\Bundle\DemoBundle\Controller\DocumentController
              method: viewAction
            - class: Acme\Bundle\DemoBundle\Controller\Api\DocumentApiController
              method: cgetAction
            - class: Acme\Bundle\DemoBundle\Controller\Api\DocumentApiController
              method: getAction
```

---

## ACL Categories

Categories organize ACL resources in the role configuration UI. Without a category, ACLs appear in "General" or uncategorized sections.

```yaml
# First define categories in acl-categories.yml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/acl-categories.yml
acl-categories:
    document_management:
        label: Document Management
        
    system_tools:
        label: System Tools
```

```yaml
# Then reference categories in acls.yml
acls:
    acme_demo_document_view:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: VIEW
        category: document_management
        
    acme_demo_document_edit:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: EDIT
        category: document_management
        
    acme_demo_export_data:
        type: action
        label: Export Data
        category: system_tools
```

---

## Group Name (Application Scope)

The `group_name` parameter scopes ACLs to specific application areas. Primarily used for OroCommerce storefront vs backend separation.

```yaml
acls:
    # Backend/admin ACL
    acme_demo_order_view_backend:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Order
        permission: VIEW
        group_name: ''                    # Empty = backend/default
        
    # Storefront ACL
    acme_demo_order_view_storefront:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Order
        permission: VIEW
        group_name: commerce              # Storefront scope
```

---

## Comparison: YAML vs PHP Attribute

### YAML Approach (acls.yml)

```yaml
acls:
    acme_demo_document_edit:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: EDIT
        bindings:
            - class: Acme\Bundle\DemoBundle\Controller\DocumentController
              method: editAction
```

### PHP Attribute Approach

```php
#[Route(path: '/{id}/edit', name: 'edit')]
#[Acl(
    id: 'acme_demo_document_edit',
    type: 'entity',
    class: Document::class,
    permission: 'EDIT'
)]
public function editAction(Document $document): Response
{
    // ...
}
```

### When to Use Each

| Scenario | Recommended Approach |
|----------|---------------------|
| Simple CRUD ACLs | PHP Attribute (simpler, co-located) |
| Multiple controllers share one ACL | YAML (bindings across controllers) |
| Overriding vendor ACLs | YAML (no code modification needed) |
| Complex security configuration | YAML (easier to review/audit) |
| Quick prototyping | PHP Attribute |

---

## Common Patterns

### Full CRUD ACL Set

```yaml
acls:
    acme_demo_document_index:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: VIEW
        category: documents
        bindings:
            - { class: Acme\Bundle\DemoBundle\Controller\DocumentController, method: indexAction }
            
    acme_demo_document_view:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: VIEW
        category: documents
        bindings:
            - { class: Acme\Bundle\DemoBundle\Controller\DocumentController, method: viewAction }
            
    acme_demo_document_create:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: CREATE
        category: documents
        bindings:
            - { class: Acme\Bundle\DemoBundle\Controller\DocumentController, method: createAction }
            
    acme_demo_document_edit:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: EDIT
        category: documents
        bindings:
            - { class: Acme\Bundle\DemoBundle\Controller\DocumentController, method: editAction }
            
    acme_demo_document_delete:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: DELETE
        category: documents
        bindings:
            - { class: Acme\Bundle\DemoBundle\Controller\DocumentController, method: deleteAction }
```

### API ACL Pattern

```yaml
acls:
    acme_demo_api_document:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: VIEW
        bindings:
            - { class: Acme\Bundle\DemoBundle\Controller\Api\DocumentApiController, method: getAction }
            - { class: Acme\Bundle\DemoBundle\Controller\Api\DocumentApiController, method: cgetAction }
            
    acme_demo_api_document_create:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: CREATE
        bindings:
            - { class: Acme\Bundle\DemoBundle\Controller\Api\DocumentApiController, method: postAction }
            
    acme_demo_api_document_edit:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: EDIT
        bindings:
            - { class: Acme\Bundle\DemoBundle\Controller\Api\DocumentApiController, method: putAction }
            - { class: Acme\Bundle\DemoBundle\Controller\Api\DocumentApiController, method: patchAction }
            
    acme_demo_api_document_delete:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: DELETE
        bindings:
            - { class: Acme\Bundle\DemoBundle\Controller\Api\DocumentApiController, method: deleteAction }
```

### Feature Toggle ACL

```yaml
acls:
    acme_demo_feature_advanced_search:
        type: action
        label: Advanced Search Feature
        category: features
        
    acme_demo_feature_bulk_import:
        type: action
        label: Bulk Import Feature
        category: features
```

---

## Using ACLs in Code

### Check ACL in Controller

```php
// Check entity ACL
if (!$this->isGranted('VIEW', $document)) {
    throw $this->createAccessDeniedException();
}

// Check action ACL by ID
if (!$this->isGranted('acme_demo_feature_advanced_search')) {
    throw $this->createAccessDeniedException();
}
```

### Check ACL in Twig

```twig
{% if is_granted('VIEW', document) %}
    <a href="{{ path('document_view', {id: document.id}) }}">View</a>
{% endif %}

{% if is_granted('acme_demo_document_edit') %}
    <a href="{{ path('document_edit', {id: document.id}) }}">Edit</a>
{% endif %}
```

### Check ACL in Service

```php
use Symfony\Component\Security\Core\Authorization\AuthorizationCheckerInterface;

class DocumentService
{
    public function __construct(
        private AuthorizationCheckerInterface $authorizationChecker
    ) {}
    
    public function canView(Document $document): bool
    {
        return $this->authorizationChecker->isGranted('VIEW', $document);
    }
}
```

---

## Best Practices

### 1. Consistent Naming Convention

```yaml
# GOOD - Consistent pattern
acme_demo_document_view
acme_demo_document_create
acme_demo_document_edit
acme_demo_document_delete

# BAD - Inconsistent
document_view
create_document
editDoc
delete_document_action
```

### 2. Always Include Category

```yaml
# GOOD - Categorized for UI organization
acme_demo_document_view:
    type: entity
    class: Acme\Bundle\DemoBundle\Entity\Document
    permission: VIEW
    category: document_management
```

### 3. Use Bindings for Automatic Enforcement

```yaml
# GOOD - ACL automatically enforced on controller
acme_demo_document_edit:
    type: entity
    class: Acme\Bundle\DemoBundle\Entity\Document
    permission: EDIT
    bindings:
        - class: Acme\Bundle\DemoBundle\Controller\DocumentController
          method: editAction
```

### 4. Protect Both Page and Data Access

```yaml
# Protect the page
acls:
    acme_demo_document_index:
        type: entity
        class: Acme\Bundle\DemoBundle\Entity\Document
        permission: VIEW
        bindings:
            - { class: DocumentController, method: indexAction }

# ALSO protect the datagrid (in datagrids.yml)
datagrids:
    documents-grid:
        acl_resource: acme_demo_document_index
        # ... grid config
```

---

## Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Duplicate ACL IDs | ACLs merge unexpectedly | Use unique prefixed IDs: `bundle_entity_action` |
| Missing bindings | ACL exists but not enforced | Add bindings or use `#[Acl]` attribute |
| Wrong permission case | `view` vs `VIEW` | Use uppercase: `VIEW`, `CREATE`, `EDIT` |
| Missing category | ACLs appear uncategorized in UI | Always add `category` parameter |
| Forgetting datagrid protection | Grid shows data even without permission | Add `acl_resource` to datagrid config |

---

## Related Files

- `acl-configuration.md` — Complete ACL configuration reference
- `acl-overview.md` — ACL system concepts
- `datagrids-yml.md` — Protecting datagrids with `acl_resource`
- `navigation-yml.md` — Hiding menu items based on ACL