# OroCommerce Datagrid Configuration Reference

> Source: https://doc.oroinc.com/master/backend/entities/data-grids/

## AGENT QUERY HINTS

This file answers questions like:
- How do I create a datagrid in OroCommerce?
- What is the full YAML structure for a datagrid?
- How do I configure columns, filters, sorters, and actions?
- How do I use the ORM datasource with custom DQL queries?
- How do I use the array datasource?
- How do I protect a datagrid with ACL?
- How do I add export functionality to a grid?
- How do I configure pagination?
- What are all the column frontend_type options?
- How do I add row actions (view, edit, delete)?
- How do I configure mass actions?
- How do I pass URL parameters to a grid?
- How do I use grid scopes to show multiple grids on one page?
- How do I configure grid mixins for reusable config?
- How do I add sorting defaults?
- How do I configure toolbar options and page size?
- What is parameter binding and how do I use it?

---

## Overview

Datagrids provide tabular displays of entity data with built-in filtering, sorting, pagination, export, and row actions. They are the standard way to display lists of entities in OroCommerce backend and storefront.

**Configuration files:**
- Backend (admin): `<Bundle>/Resources/config/oro/datagrids.yml`
- Storefront: `<Bundle>/Resources/views/layouts/<theme>/config/datagrids.yml`

**Architecture components:**
- `Datagrid\Manager` — Prepares grid and configuration
- `Datagrid\Builder` — Creates datagrid objects and attaches datasources
- `Datagrid\Datagrid` — Main grid object managing datasource interaction
- `Datasource\DatasourceInterface` — Bridge between data and grid display

---

## Top-Level YAML Structure

```yaml
datagrids:
    your-grid-name:                  # Unique grid identifier (used in templates, controllers)
        # --- MIXIN (optional) ---
        mixins:
            - some-reusable-mixin-grid

        # --- EXTEND (optional) ---
        extends: parent-grid-name    # Inherit from another grid definition

        # --- SCOPE (optional) ---
        scope: my-scope              # Default scope name

        # --- ACL PROTECTION ---
        acl_resource: acme_entity_view   # Required ACL permission to view grid

        # --- DATA SOURCE ---
        source:
            type: orm                # 'orm' or 'array'
            acl_resource: acme_entity_view
            query:
                select: []
                from: []
                join: {}
                where: {}
                groupBy: ~
                orderBy: []
                having: ~
            hints: []
            bind_parameters: []

        # --- COLUMNS ---
        columns:
            column_name:
                label: ~
                type: ~              # backend formatter type
                frontend_type: ~     # frontend display type
                data_name: ~
                editable: false
                renderable: true
                order: ~
                required: false
                manageable: true
                disabled: false
                inline_editing: {}

        # --- PROPERTIES (non-displayed row data) ---
        properties:
            id: ~
            view_link:
                type: url
                route: entity_view
                params: [id]

        # --- SORTERS ---
        sorters:
            columns:
                column_name:
                    data_name: alias.field
                    type: ~
                    apply_callback: ~
                    disabled: false
            default:
                column_name: ASC   # or DESC
            toolbar_sorting: false
            multiple_sorting: false
            disable_default_sorting: false
            disable_not_selected_option: false

        # --- FILTERS ---
        filters:
            columns:
                column_name:
                    type: string     # string|number|date|datetime|choice|entity|boolean|...
                    data_name: alias.field
                    label: ~
                    enabled: true
                    force_like: false
                    min_length: 0
                    max_length: ~
                    options: {}
            default: {}

        # --- ACTIONS (per-row) ---
        actions:
            view:
                type: navigate     # navigate|ajax|delete
                label: oro.grid.action.view
                icon: eye
                link: view_link    # references a property
                rowAction: true
                acl_resource: acme_entity_view
            edit:
                type: navigate
                label: oro.grid.action.edit
                icon: pencil
                link: edit_link
                acl_resource: acme_entity_edit
            delete:
                type: delete
                label: oro.grid.action.delete
                icon: trash-o
                link: delete_link
                confirmation: true
                acl_resource: acme_entity_delete

        # --- MASS ACTIONS ---
        mass_actions:
            delete:
                type: delete       # delete|ajax
                label: oro.grid.action.delete
                icon: trash-o
                data_identifier: e.id
                acl_resource: acme_entity_delete
                handler: Acme\Bundle\Handler\MassDeleteHandler
                route: oro_datagrid_mass_action
                allowedRequestTypes: [POST]
                requestType: POST

        # --- OPTIONS ---
        options:
            entity_pagination: true
            export: true           # or: { csv: { label: oro.grid.export.csv } }
            gridViews:
                allLabel: acme.bundle.all_label
            toolbarOptions:
                hide: false
                pageSize:
                    hide: false
                    items: [10, 25, 50, 100]
                    default_per_page: 25
                pagination:
                    hide: false
                    onePage: false  # show all rows (max 1000)

        # --- INLINE EDITING ---
        inline_editing:
            enable: true
            behaviour: enable_all  # enable_all|enable_selected
            entity_name: Acme\Entity\MyEntity
            acl_resource: acme_entity_edit
            save_api_accessor:
                http_method: PATCH
                route: acme_entity_update

        # --- TOTALS ---
        totals:
            grand_total:
                columns:
                    amount:
                        label: 'Grand Total'
                        expr: 'SUM(o.amount)'
                        formatter: decimal
            page_total:
                extends: grand_total
                per_page: true
                hide_if_one_page: true
                columns:
                    amount:
                        label: 'Page Total'

        # --- FIELD ACL ---
        fields_acl:
            columns:
                name:
                    data_name: e.name
```

---

## Source Section — ORM Datasource

The ORM datasource translates YAML into a Doctrine QueryBuilder.

```yaml
source:
    type: orm
    acl_resource: acme_entity_view    # optional — blocks entire grid from unauthorized users

    query:
        select:
            - e.id
            - e.name
            - e.status
            - IDENTITY(e.category) AS category_id
            - c.name AS category_name

        from:
            - { table: Acme\Bundle\Entity\MyEntity, alias: e }

        join:
            left:
                - { join: e.category, alias: c }
                - { join: e.tags, alias: t, conditionType: WITH, condition: 't.active = true' }
            inner:
                - { join: e.owner, alias: o }

        where:
            and:
                - e.deleted = false
                - e.type IN (:types)
            or:
                - e.status = 'active'

        groupBy: e.id
        having: 'COUNT(t.id) > 0'

        orderBy:
            - { column: e.name, dir: asc }

    # Bind datagrid parameters to query named parameters
    bind_parameters:
        - holder_entity_id              # simple: same name in grid and query

    # Or with name mapping (grid param name => query param name)
    bind_parameters:
        holder_entity_id: holderId      # query has :holderId, grid passes holder_entity_id

    # Extended bind_parameters format
    bind_parameters:
        data_in:
            path: _parameters.groupId  # dot-path into datagrid parameters
            default: [0]               # fallback if not provided
            type: array                # Doctrine type for conversion

    # Doctrine query hints
    hints:
        - HINT_FORCE_PARTIAL_LOAD
        - { name: HINT_CUSTOM_OUTPUT_WALKER, value: Gedmo\Translatable\Query\TreeWalker\TranslationWalker }
        - { name: HINT_PRECISE_ORDER_BY, value: false }  # disable precise order (enabled by default)

    # Service-based QueryBuilder (alternative to inline query)
    query_builder: "@acme.service->getQueryBuilder"
```

### ORM Query Configuration Notes

- By default, `HINT_PRECISE_ORDER_BY` is always added so sort order is stable across pages.
- Use `convertAssociationJoinToSubquery()` via `$config->getOrmQuery()` in PHP for performance on many-to-many joins.
- `getRootAlias()`, `getRootEntity()` helpers are available in extensions/listeners via `OrmQueryConfiguration`.

---

## Source Section — Array Datasource

Use when data comes from PHP arrays rather than the database (config lists, computed data, etc.).

```yaml
source:
    type: array
    # No query config — data is provided via event listener
```

**Populating data via event listener:**

```php
// services.yml
acme.listener.my_grid:
    class: Acme\Bundle\EventListener\MyGridListener
    tags:
        - { name: kernel.event_listener,
            event: oro_datagrid.datagrid.build.after.acme-my-grid,
            method: onBuildAfter }

// MyGridListener.php
public function onBuildAfter(BuildAfter $event): void
{
    $datagrid   = $event->getDatagrid();
    $datasource = $datagrid->getDatasource();

    if ($datasource instanceof ArrayDatasource) {
        $datasource->setArraySource([
            ['id' => 1, 'name' => 'Item A', 'status' => 'active'],
            ['id' => 2, 'name' => 'Item B', 'status' => 'inactive'],
        ]);
    }
}
```

---

## Columns Section

Each key under `columns` is the column identifier (matches select alias or data_name).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `label` | string | No | column key | Translation key for column header |
| `type` | string | No | `field` | Backend formatter type (field, url, link, twig, translatable, callback) |
| `frontend_type` | string | No | `string` | Frontend display type (see list below) |
| `data_name` | string | No | column key | Field name in result set |
| `editable` | bool | No | `false` | Allow inline editing in this cell |
| `renderable` | bool | No | `true` | Show/hide column (user can toggle if manageable) |
| `order` | int | No | — | Column position weight (lower = left) |
| `required` | bool | No | `false` | Column cannot be hidden by user |
| `manageable` | bool | No | `true` | Appears in column management settings |
| `disabled` | bool | No | `false` | Remove column completely (overrides manageable) |
| `align` | string | No | — | Cell alignment: `left`, `center`, `right` |
| `shortenableString` | bool | No | — | Allow text truncation |

### Frontend Types (frontend_type)

| Value | Description |
|-------|-------------|
| `string` | Plain text (default) |
| `html` | Rendered HTML |
| `integer` | Integer number |
| `decimal` | Decimal number |
| `number` | Generic number |
| `currency` | Formatted currency |
| `percent` | Percentage |
| `boolean` | Yes/No display |
| `date` | Formatted date |
| `datetime` | Formatted datetime |
| `time` | Formatted time |
| `select` | Select list value |
| `multi-select` | Multi-select values |
| `array` | Array of values |
| `simple-array` | Simple array |
| `relation` | Related entity |
| `multi-relation` | Multiple relations |

### Backend Formatter Types (type)

| Value | Description |
|-------|-------------|
| `field` | Default — reads field value from result |
| `url` | Generates URL using router |
| `link` | Generates HTML `<a>` tag (needs `frontend_type: html`) |
| `twig` | Renders a Twig template |
| `translatable` | Translates value via Symfony translator |
| `callback` | Custom formatting via service method |
| `localized_number` | NumberFormatter (currency, decimal, percent) |

---

## Properties Section

Properties provide per-row data to the frontend (e.g., action URLs) without creating visible columns.

```yaml
properties:
    id: ~                            # Expose the id field as-is (required for entity_pagination)
    view_link:
        type: url
        route: acme_entity_view
        params: [id]                 # Route parameters pulled from row data
    edit_link:
        type: url
        route: acme_entity_edit
        params: [id]
    delete_link:
        type: url
        route: acme_entity_delete
        params: [id]
```

---

## Sorters Section

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `columns.<name>.data_name` | string | Yes | — | Property in result set to sort on |
| `columns.<name>.type` | string | No | — | Type hint for toolbar sorting labels |
| `columns.<name>.apply_callback` | callable | No | — | Custom sort logic instead of ORDER BY |
| `columns.<name>.disabled` | bool | No | `false` | Disable sorting for this column |
| `default.<column>` | string | No | — | Default sort column and direction (ASC/DESC) |
| `toolbar_sorting` | bool | No | `false` | Show sorting controls in toolbar |
| `multiple_sorting` | bool | No | `false` | Allow sorting by multiple columns |
| `disable_default_sorting` | bool | No | `false` | Prevent automatic default sort |
| `disable_not_selected_option` | bool | No | `false` | Hide "Please select" in toolbar sort |

---

## Filters Section

Filter types are registered with the `oro_filter.extension.orm_filter.filter` service tag.

### Filter Common Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | — | Filter type identifier |
| `data_name` | string | Yes | — | Field/alias to filter on |
| `label` | string | No | column label | Filter label |
| `enabled` | bool | No | `true` | Show filter by default |
| `options` | array | No | — | Type-specific options |

### String Filter

```yaml
filters:
    columns:
        name:
            type: string
            data_name: e.name
            force_like: false    # force LIKE even for exact match
            min_length: 0        # minimum search string length
            max_length: ~        # maximum search string length
```

### Number / Integer Filter

```yaml
filters:
    columns:
        price:
            type: number          # or: integer, decimal, currency, percent
            data_name: e.price
            options:
                data_type: Oro\Bundle\FilterBundle\Form\Type\Filter\NumberFilterType::DATA_DECIMAL
```

### Date / Datetime Filter

```yaml
filters:
    columns:
        created_at:
            type: date            # or: datetime, time
            data_name: e.createdAt
```

### Choice Filter

```yaml
filters:
    columns:
        status:
            type: choice
            data_name: e.status
            options:
                field_options:
                    choices:
                        Active: active
                        Inactive: inactive
                    multiple: false   # true for multi-select
```

### Entity Filter

```yaml
filters:
    columns:
        category:
            type: entity
            data_name: e.category
            options:
                field_options:
                    class: Acme\Bundle\Entity\Category
                    choice_label: name
                    multiple: true
```

### Boolean Filter

```yaml
filters:
    columns:
        active:
            type: boolean
            data_name: e.active
```

### Setting Filter Defaults

```yaml
filters:
    columns:
        status:
            type: choice
            data_name: e.status
    default:
        status:
            value: active          # pre-select this filter value
```

---

## Actions Section

Per-row actions appear in the last column of the grid.

### Navigate Action (link to another page)

```yaml
actions:
    view:
        type: navigate
        label: oro.grid.action.view
        icon: eye
        link: view_link            # Property name containing the URL
        rowAction: true            # Clicking the row triggers this action
        acl_resource: acme_entity_view
```

### Ajax Action (background HTTP call)

```yaml
actions:
    activate:
        type: ajax
        label: Activate
        icon: check
        link: activate_link
        acl_resource: acme_entity_edit
```

### Delete Action

```yaml
actions:
    delete:
        type: delete
        label: oro.grid.action.delete
        icon: trash-o
        link: delete_link
        confirmation: true         # Show confirm dialog before deleting
        acl_resource: acme_entity_delete
```

---

## Mass Actions Section

Mass actions operate on multiple selected rows.

### Built-in Delete Mass Action

```yaml
mass_actions:
    delete:
        type: delete
        label: oro.grid.action.delete
        icon: trash-o
        data_identifier: e.id
        acl_resource: acme_entity_delete
```

### Custom Ajax Mass Action

```yaml
mass_actions:
    activate:
        type: ajax
        label: Activate Selected
        icon: check
        handler: Acme\Bundle\Handler\ActivateMassHandler
        route: oro_datagrid_mass_action
        data_identifier: e.id
        acl_resource: acme_entity_edit
        allowedRequestTypes: [POST]
        requestType: POST
        defaultMessages:
            confirm_title: Confirm Activation
            confirm_content: Activate selected items?
            confirm_ok: Activate
```

**Handler implementation:**

```php
class ActivateMassHandler implements MassActionHandlerInterface
{
    public function handle(MassActionHandlerArgs $args): MassActionResponse
    {
        // Process $args->getResults() in batches
        return new MassActionResponse(true, $this->translator->trans('acme.activated'));
    }
}
```

To disable an inherited mass action:

```yaml
mass_actions:
    delete:
        disabled: true
```

---

## Options Section

```yaml
options:
    # Enable entity pagination (prev/next navigation when viewing an entity)
    entity_pagination: true

    # Export (simple)
    export: true

    # Export (multi-format with custom page_size)
    export:
        csv:
            label: oro.grid.export.csv
            page_size: 500
        xlsx:
            label: acme.grid.export.xlsx

    # Grid views "All" label
    gridViews:
        allLabel: acme.bundle.translation.all

    # Toolbar
    toolbarOptions:
        hide: false
        pageSize:
            hide: false
            items: [10, 25, 50, 100]
            default_per_page: 25
        pagination:
            hide: false
            onePage: false     # true = show all rows (max 1000), no pagination
```

---

## Scopes

**WHY:** When the same grid needs to appear multiple times on one page (e.g., order history for each customer in a list), scopes prevent naming conflicts so each instance is independent.

```yaml
# YAML: define default scope
datagrids:
    acme-customer-order-grid:
        scope: orders
        source: ...
```

**Twig: render with unique per-instance scope**

```twig
{% import '@OroDataGrid/macros.html.twig' as dataGrid %}

{% for customer in customers %}
    {{ dataGrid.renderGrid(
        oro_datagrid_build_fullname('acme-customer-order-grid', customer.id),
        { id: customer.id }
    ) }}
{% endfor %}
```

**Name format:** `gridname:scope` — the `NameStrategy` service (`oro_datagrid.datagrid.name_strategy`) parses this format.

**PHP access:** `$datagrid->getScope()` returns the current scope.

---

## Parameter Binding

**WHY:** Pass context-specific values (entity IDs, user-specific data) from the page into the grid's datasource query without hardcoding values.

### How It Works

1. Render the grid with parameters in Twig
2. `bind_parameters` maps grid parameters → query named parameters
3. `DatasourceBindParametersListener` applies values to the datasource

**Requirement:** The datasource must implement `BindParametersInterface` (ORM datasource does).

### Simple Binding (same name)

```yaml
source:
    type: orm
    query:
        select: [e]
        from:
            - { table: Acme\Entity\Order, alias: e }
        where:
            and:
                - e.customer = :customer_id
    bind_parameters:
        - customer_id
```

```twig
{{ dataGrid.renderGrid('acme-order-grid', { customer_id: customer.id }) }}
```

### Mapping Mismatched Names

```yaml
bind_parameters:
    customer_id: customerId    # query uses :customer_id, grid receives customerId
```

```twig
{{ dataGrid.renderGrid('acme-order-grid', { customerId: customer.id }) }}
```

### Extended Format (with default and type)

```yaml
bind_parameters:
    data_in:
        path: _parameters.selectedIds   # dot-notation path into datagrid params
        default: [0]                    # fallback if parameter absent
        type: array                     # Doctrine type for parameter conversion
```

### Event Listener Alternative (for complex logic)

```php
// Listen to oro_datagrid.datagrid.build.after event
public function onBuildAfter(BuildAfter $event): void
{
    $datagrid = $event->getDatagrid();
    $param    = $datagrid->getParameters()->get('customerId');

    /** @var OrmDatasource $datasource */
    $datasource = $datagrid->getDatasource();
    $datasource->getQueryBuilder()->setParameter('customer_id', $param);
}
```

---

## ACL Protection

**WHY:** Prevent unauthorized users from seeing or interacting with grids containing sensitive data.

### Grid-Level ACL (blocks the entire grid)

```yaml
datagrids:
    acme-sensitive-grid:
        acl_resource: acme_entity_view
        source:
            type: orm
            ...
```

### Datasource-Level ACL (identical effect, on the source)

```yaml
source:
    type: orm
    acl_resource: acme_entity_view
    query: ...
```

### Action-Level ACL (hide specific actions)

```yaml
actions:
    edit:
        type: navigate
        link: edit_link
        acl_resource: acme_entity_edit     # only shown if user has this permission
```

### Field ACL (column-level access control)

```yaml
fields_acl:
    columns:
        sensitive_field:
            data_name: e.sensitiveField    # path to field on root entity
        price:
            data_name: e.price
```

**Limitation:** Only root entity fields are supported — not joined entity fields.

---

## Mixins (Reusable Configurations)

**WHY:** Share common column/filter/action groups across multiple grids without duplication.

```yaml
datagrids:
    # Define the mixin
    acme-ownership-mixin:
        source:
            query:
                select:
                    - owner.name AS owner_name
                join:
                    left:
                        - { join: __root_entity__.owner, alias: owner }
        columns:
            owner_name:
                label: Owner
        filters:
            columns:
                owner_name:
                    type: string
                    data_name: owner.name

    # Apply the mixin
    acme-product-grid:
        mixins:
            - acme-ownership-mixin
        source:
            type: orm
            query:
                select: [p.id, p.name]
                from:
                    - { table: Acme\Entity\Product, alias: p }
        columns:
            name:
                label: Product Name
```

**Note:** `__root_entity__` in mixin queries is substituted with the consuming grid's root entity alias at build time.

---

## Entity Pagination

Allows navigating prev/next through entities from the datagrid when viewing individual records.

```yaml
datagrids:
    acme-product-grid:
        options:
            entity_pagination: true     # enable prev/next navigation
        properties:
            id: ~                       # REQUIRED: must expose the ID
        source:
            type: orm
            query:
                select:
                    - e.id              # REQUIRED: ID must be in select
                from:
                    - { table: Acme\Entity\Product, alias: e }
```

**System configuration:**
- Admin: System Configuration > General Setup > Display Settings > Data Grid Settings
- "Record Pagination" toggle (default: enabled)
- "Record Pagination limit" (default: 1000 — disables if exceeded)

---

## Rendering in Twig

```twig
{# Import the macro #}
{% import '@OroDataGrid/macros.html.twig' as dataGrid %}

{# Simple render #}
{{ dataGrid.renderGrid('acme-product-grid') }}

{# With parameters #}
{{ dataGrid.renderGrid('acme-order-grid', { customer_id: customer.id }) }}

{# With scope for multiple instances on same page #}
{{ dataGrid.renderGrid(
    oro_datagrid_build_fullname('acme-order-grid', customer.id),
    { customer_id: customer.id }
) }}
```

---

## Complete Annotated Example

```yaml
datagrids:
    acme-product-grid:
        # ACL: only users with this permission see the grid
        acl_resource: acme_product_view

        source:
            type: orm
            query:
                select:
                    - p.id
                    - p.sku
                    - p.name
                    - p.price
                    - p.status
                    - p.createdAt
                    - IDENTITY(p.category) AS category_id
                    - c.name AS category_name
                from:
                    - { table: Acme\Bundle\Entity\Product, alias: p }
                join:
                    left:
                        - { join: p.category, alias: c }
                where:
                    and:
                        - p.deleted = false

        columns:
            sku:
                label: acme.product.sku.label
                frontend_type: string
                order: 10
            name:
                label: acme.product.name.label
                frontend_type: string
                order: 20
            category_name:
                label: acme.product.category.label
                frontend_type: string
                order: 30
            price:
                label: acme.product.price.label
                frontend_type: currency
                order: 40
            status:
                label: acme.product.status.label
                frontend_type: select
                order: 50
            createdAt:
                label: acme.product.created_at.label
                frontend_type: datetime
                order: 60

        properties:
            id: ~
            view_link:
                type: url
                route: acme_product_view
                params: [id]
            edit_link:
                type: url
                route: acme_product_edit
                params: [id]
            delete_link:
                type: url
                route: acme_product_delete
                params: [id]

        sorters:
            columns:
                sku:
                    data_name: p.sku
                name:
                    data_name: p.name
                price:
                    data_name: p.price
                createdAt:
                    data_name: p.createdAt
            default:
                createdAt: DESC

        filters:
            columns:
                sku:
                    type: string
                    data_name: p.sku
                name:
                    type: string
                    data_name: p.name
                category_name:
                    type: string
                    data_name: c.name
                price:
                    type: number
                    data_name: p.price
                status:
                    type: choice
                    data_name: p.status
                    options:
                        field_options:
                            choices:
                                Active: active
                                Inactive: inactive
                createdAt:
                    type: datetime
                    data_name: p.createdAt

        actions:
            view:
                type: navigate
                label: oro.grid.action.view
                icon: eye
                link: view_link
                rowAction: true
                acl_resource: acme_product_view
            edit:
                type: navigate
                label: oro.grid.action.edit
                icon: pencil
                link: edit_link
                acl_resource: acme_product_edit
            delete:
                type: delete
                label: oro.grid.action.delete
                icon: trash-o
                link: delete_link
                confirmation: true
                acl_resource: acme_product_delete

        mass_actions:
            delete:
                type: delete
                label: oro.grid.action.delete
                icon: trash-o
                data_identifier: p.id
                acl_resource: acme_product_delete

        options:
            entity_pagination: true
            export: true
            toolbarOptions:
                pageSize:
                    default_per_page: 25
                    items: [10, 25, 50, 100]

        fields_acl:
            columns:
                price:
                    data_name: p.price
```

---

## Custom Datasource Implementation

When ORM and Array datasources are insufficient (e.g., search engine, external API):

```php
// 1. Implement DatasourceInterface
class MyCustomDatasource implements DatasourceInterface
{
    public function process(DatagridInterface $grid, array $config): void
    {
        // Configure the datasource from $config
        $grid->setDatasource($this);
    }

    public function getResults(): array
    {
        // Return array of ResultRecord objects
        return array_map(
            fn($row) => new ResultRecord($row),
            $this->fetchData()
        );
    }
}

// 2. Register as service
// services.yml:
acme.datasource.custom:
    class: Acme\Bundle\Datasource\MyCustomDatasource
    tags:
        - { name: oro_datagrid.datasource, type: my_custom }
```

```yaml
# 3. Use in datagrid config
source:
    type: my_custom
    # ... custom options
```

---

## Datagrid Events for Customization

| Event | When | Use For |
|-------|------|---------|
| `oro_datagrid.datagrid.build.before` | Before grid is built | Modify config (add columns, joins) |
| `oro_datagrid.datagrid.build.after` | After datasource attached | Set array data, add parameters |
| `oro_datagrid.datagrid.build.after.<grid-name>` | After specific grid built | Grid-specific modifications |
| `oro_datagrid.orm_datasource.result.before` | Before ORM query runs | Modify QueryBuilder |
| `oro_datagrid.orm_datasource.result.after` | After results fetched | Attach extra data to records |

---

## Selected Fields Performance Optimization

For grids with large tables, unnecessary joins slow queries. OroCommerce includes providers that detect which fields are actually needed:

- `SelectedFieldsFromColumnsProvider` — fields needed for visible columns
- `SelectedFieldsFromSortersProvider` — fields needed by active sorters

These are automatically used by the `SelectedFieldsProvider` composite service. For custom behavior, implement `SelectedFieldsProviderInterface` and tag with `oro_datagrid.selected_fields_provider`.

---

## State Providers

State providers implement `DatagridStateProviderInterface` and return per-user state arrays for grid components.

Built-in providers:
- `ColumnsStateProvider` (`oro_datagrid.provider.state.columns`) — column visibility and order
- `SortersStateProvider` (`oro_datagrid.provider.state.sorters`) — current sort direction

State is fetched from (in priority order): request parameters → current view → default view → grid configuration.
