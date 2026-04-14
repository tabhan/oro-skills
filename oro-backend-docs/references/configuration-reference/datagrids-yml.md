# OroCommerce datagrids.yml — Data Grid Configuration

> Source: https://doc.oroinc.com/master/backend/configuration/yaml/datagrids/

---

## AGENT QUERY HINTS

Use this file when:
- "How do I create a datagrid in OroCommerce?"
- "What is the structure of datagrids.yml?"
- "How do I configure columns, filters, and sorters in a datagrid?"
- "How do I add actions (view, edit, delete) to a datagrid?"
- "What datasource types are available (ORM, array)?"
- "How do I configure mass actions in datagrids?"
- "How do I bind parameters to a datagrid query?"
- "How do I enable inline editing in a datagrid?"
- "How do I configure export functionality for a datagrid?"

---

## Core Concept: WHY datagrids.yml Exists

OroCommerce provides a powerful, configuration-driven data grid system. Instead of building HTML tables manually with pagination, sorting, and filtering logic, you declare the grid's structure in YAML and Oro handles:

1. **Data retrieval** — via ORM queries or array sources
2. **ACL integration** — row-level permissions, action visibility
3. **UI components** — pagination, filters, sorters, mass actions
4. **Export** — CSV, Excel out of the box
5. **Inline editing** — cell-by-cell modification

**WHY YAML over PHP:** Grids are declarative by nature. YAML configuration allows non-developers (via UI) to customize grids, and configurations can be merged/overridden across bundles without code conflicts.

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
                        └── datagrids.yml    ← place here
```

---

## Minimal Datagrid Configuration

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/datagrids.yml
datagrids:
    acme-demo-document-grid:           # Unique grid identifier
        source:
            type: orm                   # Data source type
            query:
                select:
                    - d.id
                    - d.subject
                    - d.description
                    - d.createdAt
                from:
                    - { table: 'Acme\Bundle\DemoBundle\Entity\Document', alias: d }
        columns:
            id:
                label: ID
            subject:
                label: Subject
            description:
                label: Description
            createdAt:
                label: Created At
                frontend_type: datetime
        properties:
            id: ~                        # Expose ID for action links
        actions:
            view:
                type: navigate
                label: View
                link: view_link
                rowAction: true
        options:
            entityHint: documents
```

---

## Complete Configuration Structure

```yaml
datagrids:
    grid-name:
        acl_resource: ~                 # Optional ACL check for whole grid
        source:                         # REQUIRED - data retrieval
            type: orm|array
            query: { ... }
            query_builder: @service->method
            bind_parameters: [ ... ]
            skip_acl_apply: false
        columns: { ... }                # REQUIRED - column definitions
        filters:
            columns: { ... }
            default: { ... }
        sorters:
            columns: { ... }
            default: { ... }
            multiple_sorting: true
        properties: { ... }             # Virtual properties for actions
        actions: { ... }                # Row-level actions
        action_configuration: ~         # Per-row action visibility
        mass_actions: { ... }           # Bulk operations
        options: { ... }                # Toolbar, export, pagination
        inline_editing: { ... }         # Cell editing configuration
        fields_acl: { ... }             # Field-level ACL
        scope: ~                        # Scope restriction
        totals: { ... }                 # Summary rows
        views_list: { ... }             # Predefined grid views
        extends: parent-grid-name       # Inheritance
```

---

## Source Configuration (Datasources)

### ORM Datasource (Most Common)

```yaml
datagrids:
    acme-demo-document-grid:
        source:
            type: orm
            query:
                select:
                    - d.id
                    - d.subject
                    - d.description
                    - d.createdAt
                    - p.label as priorityLabel    # Join field
                from:
                    - { table: 'Acme\Bundle\DemoBundle\Entity\Document', alias: d }
                join:
                    left:
                        - { join: d.priority, alias: p }
                where:
                    and:
                        - d.status = :status
                orderBy:
                    - { column: d.createdAt, dir: DESC }
            bind_parameters:
                - status                      # Pass from controller/request
```

### Query with Complex Conditions

```yaml
source:
    type: orm
    query:
        select:
            - u.id
            - u.username
            - u.email
            - u.enabled
            - GROUP_CONCAT(r.name SEPARATOR ', ') as roles
        from:
            - { table: 'Oro\Bundle\UserBundle\Entity\User', alias: u }
        join:
            inner:
                - { join: u.roles, alias: r }
        where:
            and:
                - u.enabled = true
            or:
                - u.username LIKE :search
                - u.email LIKE :search
        groupBy:
            - u.id
```

### Array Datasource (Static Data)

```yaml
datagrids:
    acme-demo-status-grid:
        source:
            type: array
        columns:
            code:
                label: Code
            label:
                label: Label
```

Use array datasource when data comes from an external API or computed values.

### Parameter Binding

Pass dynamic values from controller or request:

```yaml
source:
    type: orm
    query:
        where:
            and:
                - d.organization = :organizationId
                - d.status = :status
    bind_parameters:
        - organizationId              # From request or security context
        - status: documentStatus      # Rename parameter (key: external name)
```

**In controller:**
```php
public function indexAction(Request $request)
{
    $grid = $this->get('oro_datagrid.datagrid.manager')->getDatagrid('acme-demo-document-grid');
    $grid->getParameters()->set('organizationId', $this->getUser()->getOrganization()->getId());
    // ...
}
```

### Skip ACL Apply

Disable automatic ACL filtering (use with caution):

```yaml
source:
    type: orm
    skip_acl_apply: true              # Disables ownership filtering
    query:
        # ...
```

---

## Columns Configuration

### Basic Column Types

```yaml
columns:
    id:
        label: ID
        frontend_type: integer
        renderable: false              # Hide from display but keep in data

    subject:
        label: Subject
        frontend_type: string
        required: true

    description:
        label: Description
        frontend_type: textarea

    createdAt:
        label: Created At
        frontend_type: datetime

    dueDate:
        label: Due Date
        frontend_type: date

    amount:
        label: Amount
        frontend_type: money
        currency: USD

    rating:
        label: Rating
        frontend_type: percent

    isActive:
        label: Active
        frontend_type: boolean

    status:
        label: Status
        frontend_type: select
        choices:
            pending: Pending
            active: Active
            closed: Closed

    priority:
        label: Priority
        type: string
        data_name: p.label              # Use alias from query
```

### Column with Template

```yaml
columns:
    actions:
        label: Actions
        type: html
        template: '@AcmeDemo/Datagrid/Column/actions.html.twig'
        frontend_type: html
```

### Column Order

```yaml
columns:
    subject:
        label: Subject
        order: 10                       # Lower = appears first
    description:
        label: Description
        order: 20
    createdAt:
        label: Created At
        order: 30
```

### Inline Editing

Enable per-column inline editing:

```yaml
columns:
    subject:
        label: Subject
        inline_editing:
            enable: true
            save_api_accessor:
                route: acme_demo_api_put_document
                http_method: PUT
                default_route_parameters:
                    id: id

    priority:
        label: Priority
        inline_editing:
            enable: true
            editor:
                view: oroui/js/app/views/editor/select-editor-view
                view_options:
                    value_field_name: priority
                component: oroui/js/app/components/select-editor-component
                component_options:
                    placeholder: 'Choose priority...'
            save_api_accessor:
                route: acme_demo_api_patch_document
```

### Inline Editing at Grid Level

```yaml
inline_editing:
    enable: true
    acl_resource: acme_demo_document_edit
    entity_name: 'Acme\Bundle\DemoBundle\Entity\Document'
    behaviour: enable_all              # enable_all|disable_all
    save_api_accessor:
        route: acme_demo_api_patch_document
        http_method: PATCH
        default_route_parameters:
            id: id
```

---

## Filters Configuration

### Filter Types

```yaml
filters:
    columns:
        subject:
            type: string
            label: Subject
            data_name: d.subject

        status:
            type: choice
            label: Status
            data_name: d.status
            options:
                field_options:
                    choices:
                        '': All
                        pending: Pending
                        active: Active
                        closed: Closed

        priority:
            type: entity
            label: Priority
            data_name: d.priority
            options:
                field_options:
                    class: 'Acme\Bundle\DemoBundle\Entity\Priority'
                    property: label

        createdAt:
            type: datetime
            label: Created At
            data_name: d.createdAt

        amount:
            type: number
            label: Amount
            data_name: d.amount

        isActive:
            type: boolean
            label: Active
            data_name: d.isActive

        tags:
            type: multi_enum            # Multi-select enum filter
            label: Tags
            data_name: d.tags
```

### Default Filter Values

```yaml
filters:
    columns:
        status:
            type: string
            data_name: d.status
    default:
        status:
            value: active               # Pre-set filter value
```

### Filter Configuration Options

```yaml
filters:
    columns:
        search:
            type: string
            data_name: d.subject
            force_like: true            # Use LIKE instead of exact match
            case_insensitive: true      # Case-insensitive search
            min_length: 3               # Minimum characters before filtering
```

---

## Sorters Configuration

```yaml
sorters:
    columns:
        id:
            data_name: d.id
        subject:
            data_name: d.subject
        createdAt:
            data_name: d.createdAt
    default:
        createdAt: DESC                 # Default sort column and direction
    multiple_sorting: true              # Allow multi-column sort
    disable_default_sorting: false      # Set true to require explicit sort
```

---

## Properties (Virtual Fields for Actions)

Properties are computed fields not in the database, used for action links:

```yaml
properties:
    id: ~                               # Simple pass-through
    view_link:
        type: url
        route: acme_demo_document_view
        params:
            - id
    edit_link:
        type: url
        route: acme_demo_document_update
        params:
            - id
    delete_link:
        type: url
        route: acme_demo_api_delete_document
        params:
            - id
    custom_link:
        type: url
        route: acme_demo_custom_action
        params:
            id: id
            type: 'someType'
```

---

## Actions Configuration

### Action Types

```yaml
actions:
    view:
        type: navigate                  # Redirects to URL
        label: View
        link: view_link
        icon: eye
        rowAction: true                 # Clicking row triggers this
        acl_resource: acme_demo_document_view

    edit:
        type: navigate
        label: Edit
        link: edit_link
        icon: edit
        acl_resource: acme_demo_document_edit

    delete:
        type: delete                    # AJAX DELETE request
        label: Delete
        link: delete_link
        icon: trash
        confirmation: true              # Show confirmation dialog
        acl_resource: acme_demo_document_delete

    clone:
        type: ajax                      # AJAX GET/POST request
        label: Clone
        link: clone_link
        icon: copy
        acl_resource: acme_demo_document_create
```

### Row-Level Action Configuration

Control action visibility per row:

```yaml
datagrids:
    acme-demo-document-grid:
        action_configuration:
            - ['@acme_demo.datagrid.action_config', getActionPermissions]
```

**Service class:**
```php
namespace Acme\Bundle\DemoBundle\Datagrid;

use Oro\Bundle\DataGridBundle\Datasource\ResultRecordInterface;

class ActionConfig
{
    public function getActionPermissions(ResultRecordInterface $record): array
    {
        return [
            'edit' => $record->getValue('isEditable') === true,
            'delete' => $record->getValue('isDeletable') === true,
        ];
    }
}
```

**Service registration:**
```yaml
# services.yml
services:
    acme_demo.datagrid.action_config:
        class: Acme\Bundle\DemoBundle\Datagrid\ActionConfig
```

---

## Mass Actions

### Built-in Mass Actions

```yaml
datagrids:
    acme-demo-document-grid:
        options:
            mass_actions:
                delete:
                    type: delete
                    label: Delete
                    entity_name: 'Acme\Bundle\DemoBundle\Entity\Document'
                    acl_resource: acme_demo_document_delete
                    icon: trash

                change_status:
                    type: change_status
                    label: Change Status
                    entity_name: 'Acme\Bundle\DemoBundle\Entity\Document'
                    acl_resource: acme_demo_document_edit
                    options:
                        statuses:
                            active: Active
                            pending: Pending
                            closed: Closed
```

### Custom Mass Action

```yaml
mass_actions:
    export:
        type: export
        label: Export
        icon: download
        acl_resource: acme_demo_document_view

    custom_action:
        type: window                    # Opens modal
        label: Custom Action
        route: acme_demo_mass_action
        route_parameters:
            id: id
        acl_resource: acme_demo_document_edit
        icon: cog
        options:
            dialogOptions:
                title: 'Custom Action'
                width: 800
```

---

## Options Configuration

### Toolbar Options

```yaml
options:
    entityHint: documents               # Entity name for messages
    routerEnabled: true                 # Enable URL state management
    requestMethod: GET                  # HTTP method for data fetching
    
    toolbarOptions:
        hideToolbar: false
        addDatagridSettingsManager: true
        itemsCounter:
            transTemplate: 'Total: %count% documents'
        onePage: false                  # Show all rows on one page?

    export:
        label: Export
        csv:
            label: CSV Export
            show_export: true
        xlsx:
            label: Excel Export
            show_export: true

    jsmodules:                          # Custom JS modules
        - acmedemo/js/custom-grid-module

    rowSelection: true                  # Enable checkbox selection
    cellSelection: false                # Enable cell selection

    mode:
        enabled: false                  # Grid mode (board, etc.)

    gridViews:
        enable: true                    # Allow saved views

    noDataMessages:
        empty: 'No documents found'
        filtered: 'No documents match your criteria'
```

### Pagination

```yaml
options:
    entity_pagination:
        enable: true                    # Enable prev/next navigation from view
```

---

## ACL (Access Control) Integration

### Grid-Level ACL

```yaml
datagrids:
    acme-demo-document-grid:
        acl_resource: acme_demo_document_view    # User must have this permission
        # Grid is hidden if user lacks permission
```

### Action-Level ACL

```yaml
actions:
    view:
        type: navigate
        label: View
        link: view_link
        acl_resource: acme_demo_document_view    # Per-action control

    edit:
        type: navigate
        label: Edit
        link: edit_link
        acl_resource: acme_demo_document_edit
```

### Field-Level ACL

```yaml
fields_acl:
    columns:
        subject:
            data_name: d.subject
            permissions:
                view: ['VIEW', 'EDIT']           # Permission levels
        internal_notes:
            data_name: d.internalNotes
            permissions:
                view: ['ROLE_ADMIN']             # Role-based
```

---

## Grid Inheritance

Reuse and extend existing grid configurations:

```yaml
datagrids:
    acme-demo-base-grid:
        source:
            type: orm
            query:
                select:
                    - d.id
                    - d.subject
                from:
                    - { table: 'Acme\Bundle\DemoBundle\Entity\Document', alias: d }
        columns:
            id: { label: ID }
            subject: { label: Subject }

    acme-demo-extended-grid:
        extends: acme-demo-base-grid
        source:
            query:
                select:
                    - d.description            # Add field
        columns:
            description:
                label: Description             # Add column
```

---

## Common Patterns

### Entity List Grid with CRUD Actions

```yaml
datagrids:
    acme-demo-document-grid:
        source:
            type: orm
            query:
                select:
                    - d.id
                    - d.subject
                    - d.createdAt
                from:
                    - { table: 'Acme\Bundle\DemoBundle\Entity\Document', alias: d }
                orderBy:
                    - { column: d.createdAt, dir: DESC }
        columns:
            id:
                label: ID
            subject:
                label: Subject
            createdAt:
                label: Created
                frontend_type: datetime
        properties:
            id: ~
            view_link:
                type: url
                route: acme_demo_document_view
                params: [id]
            edit_link:
                type: url
                route: acme_demo_document_update
                params: [id]
            delete_link:
                type: url
                route: acme_demo_api_delete_document
                params: [id]
        actions:
            view:
                type: navigate
                label: View
                link: view_link
                icon: eye
                rowAction: true
            edit:
                type: navigate
                label: Edit
                link: edit_link
                icon: edit
            delete:
                type: delete
                label: Delete
                link: delete_link
                icon: trash
                confirmation: true
        sorters:
            columns:
                subject: { data_name: d.subject }
                createdAt: { data_name: d.createdAt }
            default:
                createdAt: DESC
        filters:
            columns:
                subject:
                    type: string
                    label: Subject
                    data_name: d.subject
        options:
            entityHint: documents
            mass_actions:
                delete:
                    type: delete
                    label: Delete
                    entity_name: 'Acme\Bundle\DemoBundle\Entity\Document'
                    acl_resource: acme_demo_document_delete
```

### Grid with Filtered Join

```yaml
datagrids:
    acme-demo-order-grid:
        source:
            type: orm
            query:
                select:
                    - o.id
                    - o.orderNumber
                    - o.total
                    - c.name as customerName
                    - COUNT(oi.id) as itemCount
                from:
                    - { table: 'Acme\Bundle\DemoBundle\Entity\Order', alias: o }
                join:
                    left:
                        - { join: o.customer, alias: c }
                        - { join: o.items, alias: oi }
                where:
                    and:
                        - o.status = :status
                groupBy:
                    - o.id
            bind_parameters:
                - status
        columns:
            orderNumber:
                label: Order #
            customerName:
                label: Customer
            total:
                label: Total
                frontend_type: money
            itemCount:
                label: Items
                frontend_type: integer
```

---

## Best Practices

### 1. Naming Convention

```yaml
datagrids:
    acme-demo-document-grid:           # bundle-entity-grid
    acme-demo-user-roles-grid:         # bundle-entity-related-grid
```

### 2. Always Use Query Aliases

```yaml
# BAD
query:
    select: [id, subject]

# GOOD
query:
    select:
        - d.id
        - d.subject
    from:
        - { table: 'Acme\Bundle\DemoBundle\Entity\Document', alias: d }
```

### 3. Use data_name for Join Fields

```yaml
columns:
    priority:
        label: Priority
        data_name: p.label              # Use join alias
```

### 4. Keep Grids Focused

- One grid = one primary entity
- Complex queries should use custom repositories
- Avoid deeply nested joins — denormalize if needed

### 5. ACL Always

- Protect grids with `acl_resource`
- Protect actions individually
- Use `action_configuration` for row-level decisions

---

## Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Missing `id` property | Actions cannot reference row | Add `properties: id: ~` |
| Wrong `data_name` | Column shows wrong data | Use correct query alias |
| No `bind_parameters` | Query fails with undefined parameter | Add parameter binding |
| ACL omitted | Users see unauthorized data | Add `acl_resource` to grid and actions |
| `frontend_type` mismatch | Data displays incorrectly | Use correct type (datetime, money, etc.) |
| Forgetting `orderBy` | Random sort order | Define default sorter |

---

## Related Files

- `services-yml.md` — Register datagrid extensions
- `acls-yml.md` — Define ACL resources
- `routing-yml.md` — Routes for actions
- `navigation-yml.md` — Link grids in menu