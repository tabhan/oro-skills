# OroCommerce Datagrid Extensions Reference

> Source: https://doc.oroinc.com/master/backend/entities/customize-datagrids/

## AGENT QUERY HINTS

This file answers questions like:
- What extensions are available for OroCommerce datagrids?
- How do I add export to a datagrid?
- How do I configure row and mass actions?
- How do I add totals/aggregate rows to a grid?
- How do I enable inline cell editing?
- How do I configure pagination (pager)?
- How do I control column sorting in detail?
- How do I restrict column access by ACL?
- How do I add column formatters (URL, Twig, currency)?
- How do I create a custom datagrid extension?
- How do I add grid views (saved filters)?
- How do I configure the grid toolbar (page size, pagination)?
- When should I use which extension?

---

## Architecture

> A datagrid object only handles converting a datasource into a result set. All other
> operations (formatting, pagination, sorting, actions, export, etc.) are performed by extensions.

Extensions implement `ExtensionVisitorInterface`. Most extend `AbstractExtension` which provides default no-op methods. Extensions are registered as Symfony services tagged `oro_datagrid.extension`.

**Extension lifecycle hooks:**
- `processConfigs(DatagridConfiguration $config)` — modify grid configuration before build
- `visitDatasource(DatagridConfiguration $config, DatasourceInterface $datasource)` — modify datasource (e.g., add ORDER BY, LIMIT)
- `visitResult(DatagridConfiguration $config, ResultsObject $result)` — modify result set after fetch
- `visitMetadata(DatagridConfiguration $config, MetadataObject $result)` — modify metadata sent to frontend

**Creating a custom extension:**

```php
class MyExtension extends AbstractExtension
{
    public function isApplicable(DatagridConfiguration $config): bool
    {
        return $config->offsetGetByPath('[options][my_feature]', false);
    }

    public function processConfigs(DatagridConfiguration $config): void
    {
        // Modify config before datagrid is built
    }

    public function visitDatasource(DatagridConfiguration $config, DatasourceInterface $datasource): void
    {
        if ($datasource instanceof OrmDatasource) {
            $datasource->getQueryBuilder()->andWhere('...');
        }
    }
}
```

```yaml
# services.yml
acme.datagrid.extension.my_extension:
    class: Acme\Bundle\Extension\MyExtension
    tags:
        - { name: oro_datagrid.extension }
```

---

## 1. Action Extension

**WHY:** Provides per-row clickable actions (view, edit, delete, custom AJAX calls) in the actions column.

**Configuration node:** `actions`

### Action Types

#### Navigate (redirect to a URL)

```yaml
actions:
    view:
        type: navigate
        label: oro.grid.action.view    # translation key
        icon: eye                      # Font Awesome icon name (without fa- prefix)
        link: view_link                # name of a Property providing the URL
        rowAction: true                # clicking the row triggers this action
        acl_resource: acme_view        # optional permission check
```

#### Ajax (background HTTP request)

```yaml
actions:
    toggle:
        type: ajax
        label: Toggle Status
        icon: refresh
        link: toggle_link
        acl_resource: acme_edit
```

#### Delete (sends HTTP DELETE)

```yaml
actions:
    delete:
        type: delete
        label: oro.grid.action.delete
        icon: trash-o
        link: delete_link
        confirmation: true             # show confirmation dialog
        acl_resource: acme_delete
```

### Parameter Table

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | — | `navigate`, `ajax`, or `delete` |
| `label` | string | No | — | Display label (translation key) |
| `icon` | string | No | — | Font Awesome icon name |
| `link` | string | Yes | — | Property name containing target URL |
| `rowAction` | bool | No | `false` | Trigger on row click |
| `acl_resource` | string | No | — | ACL permission required to show action |
| `confirmation` | bool | No | `false` | Show confirm dialog (delete only) |

### Registering Custom Action Types

```php
class MyActionType extends AbstractAction
{
    protected function getAdditionalOptions(): array
    {
        return ['my_option'];
    }
}
```

```yaml
acme.datagrid.action.my_type:
    class: Acme\Bundle\Action\MyActionType
    tags:
        - { name: oro_datagrid.extension.action.type, type: my_type }
```

---

## 2. Export Extension

**WHY:** Lets users download all grid data (respecting filters and sorting) in CSV or other formats without navigating through pages.

**Configuration node:** `options.export`

### Basic Enable (CSV only)

```yaml
options:
    export: true
```

### Multi-Format Export

```yaml
options:
    export:
        csv:
            label: oro.grid.export.csv
            page_size: 500              # rows per batch (higher = more memory)
        xlsx:
            label: acme.grid.export.xlsx
            page_size: 200
```

### Parameter Table

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `export` | bool/array | No | — | `true` to enable CSV, or array for per-format config |
| `export.<format>.label` | string | No | — | Button label translation key |
| `export.<format>.page_size` | int | No | — | Rows per database batch (affects memory) |

### Adding Custom Export Formats

Register a writer service following the naming convention:

```yaml
oro_importexport.writer.echo.pdf:
    class: Acme\Bundle\Writer\PdfExportWriter
    # ... dependencies
```

Then reference `pdf` as a format key in the grid config.

---

## 3. Field ACL Extension

**WHY:** Protect individual columns from unauthorized access. Columns are hidden for users lacking the required field-level permission.

**Configuration node:** `fields_acl`

```yaml
fields_acl:
    columns:
        price:
            data_name: e.price         # dot-path to root entity field
        salary:
            data_name: e.salary
        credit_card:
            data_name: e.creditCardNumber
```

### Parameter Table

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `columns.<name>.data_name` | string | Yes | — | Entity field path (root entity only) |

**Important limitation:** Only fields from the **root entity** of the ORM query are supported. Fields from JOINed entities cannot be ACL-protected via this extension.

**How it works:** At render time, the extension checks ACL for each listed field. If the user lacks permission, the column is removed from the metadata sent to the frontend — the column simply does not appear.

---

## 4. Formatter Extension

**WHY:** Transforms raw database values into display-ready formats (formatted URLs, translated strings, currency values, rendered templates).

**Configuration node:** `columns` (via `type` parameter)

The Formatter Extension processes results after the datasource returns them. It applies backend formatters and passes column configuration to the frontend layer.

### Built-in Formatter Types

#### Field (default)

Standard field value pass-through with `frontend_type` hint for the frontend.

```yaml
columns:
    name:
        type: field          # implicit default
        frontend_type: string
```

#### URL

Generates a URL using the Symfony router.

```yaml
columns:
    entity_url:
        type: url
        route: acme_entity_view
        params: [id]
        frontend_type: string
```

#### Link

Generates an HTML `<a>` tag. Requires `frontend_type: html`.

```yaml
columns:
    entity_link:
        type: link
        route: acme_entity_view
        params: [id]
        frontend_type: html
```

#### Twig

Renders a Twig template. The `record` variable contains the row data.

```yaml
columns:
    status_badge:
        type: twig
        frontend_type: html
        template: '@AcmeBundle/Datagrid/statusBadge.html.twig'
        context:
            someStaticValue: 42        # extra context (cannot use 'record' or 'value')
```

#### Translatable

Translates the field value using Symfony translator.

```yaml
columns:
    status:
        type: translatable
        frontend_type: string
        domain: messages             # translation domain (optional)
        locale: ~                    # locale override (optional)
```

#### Callback

Delegates formatting to a custom service method.

```yaml
columns:
    computed_field:
        type: callback
        frontend_type: string
        callable: "@acme.service::formatField"   # service::method
```

The method receives `(DatagridInterface $datagrid, array $nodeConfig, ResultRecord $record)`.

#### Localized Number

Uses `Oro\Bundle\LocaleBundle\Formatter\NumberFormatter`.

```yaml
columns:
    price:
        type: localized_number
        method: formatCurrency       # formatCurrency|formatDecimal|formatPercent
        context:
            currency: USD
        context_resolver: "@acme.currency_resolver::resolve"  # dynamic context
```

### Creating Custom Formatters

```php
class MyFormatter extends AbstractProperty
{
    public function getValue(ResultRecord $record)
    {
        return strtoupper($record->getValue($this->get(self::DATA_NAME_KEY)));
    }
}
```

```yaml
acme.datagrid.formatter.my_type:
    class: Acme\Bundle\Formatter\MyFormatter
    tags:
        - { name: oro_datagrid.extension.formatter.property, type: my_type }
```

---

## 5. Grid Views Extension

**WHY:** Allows users to save custom filter/sort combinations as named views (like "My Active Products"), switch between them, and share them.

**Configuration node:** `options.gridViews`

### Setting the "All" View Label

**Method 1: Direct config**

```yaml
options:
    gridViews:
        allLabel: acme.product.entity_grid_all_view_label
```

**Method 2: Translation key convention**

The system automatically looks for: `<vendor>.<bundle>.<entity>.entity_grid_all_view_label`

For `Acme\Bundle\ProductBundle\Entity\Product`:
- `acme.product.product.entity_grid_all_view_label`
- If bundle and entity names match: `acme.product.entity_grid_all_view_label`

**Default behavior:** If no label is configured and no translation exists, the system generates "All {PluralEntityName}" (e.g., "All Products").

### Implementation

Grid views are managed by `Oro\Bundle\DataGridBundle\EventListener\DefaultGridViewLoadListener` and the corresponding JavaScript components. Users can:
- Save current filter state as a named view
- Set a view as default
- Share views with other users (based on permissions)

---

## 6. Inline Editing Extension

**WHY:** Allows users to edit cell values directly in the grid without navigating to a separate edit form, improving UX for bulk small edits.

**Configuration node:** `inline_editing`

### Enabling Grid-Level Inline Editing

```yaml
inline_editing:
    enable: true
    behaviour: enable_all              # enable_all (default) | enable_selected
    entity_name: Acme\Bundle\Entity\Product
    acl_resource: acme_product_edit
    save_api_accessor:
        http_method: PATCH
        route: acme_product_inline_update
        route_parameters:              # parameters to extract from row for route
            id: id
        headers:
            Content-Type: application/json
        query_parameters:              # additional query string params
            _format: json
```

### Column-Level Inline Editing Override

```yaml
columns:
    name:
        inline_editing:
            enable: true               # override grid-level enable
            editor:
                view: oroform/js/app/views/editor/text-editor-view
                view_options:
                    placeholder: 'Enter name...'
            save_api_accessor:
                route: acme_product_update_name
    status:
        inline_editing:
            enable: true
            editor:
                view: oroform/js/app/views/editor/select-editor-view
                view_options:
                    choices:
                        active: Active
                        inactive: Inactive
```

### Parameter Table

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `enable` | bool | No | `false` | Enable inline editing |
| `behaviour` | string | No | `enable_all` | `enable_all` or `enable_selected` |
| `entity_name` | string | No | — | Entity FQCN for data persistence |
| `acl_resource` | string | No | — | ACL permission for editing |
| `save_api_accessor.http_method` | string | No | `PATCH` | HTTP method for save request |
| `save_api_accessor.route` | string | Yes | — | Route for save requests |
| `save_api_accessor.route_parameters` | array | No | — | Row fields to use as route params |

### Supported Editor Views

| Editor View | Use For |
|-------------|---------|
| `text-editor-view` | Plain text, phone |
| `number-editor-view` | Numeric fields |
| `date-editor-view` | Date fields |
| `datetime-editor-view` | Datetime fields |
| `select-editor-view` | Single-select dropdowns |
| `multi-select-editor-view` | Multi-select |
| `related-id-relation-editor-view` | Single relation |
| `multi-relation-editor-view` | Multiple relations |

---

## 7. Mass Action Extension

**WHY:** Enables bulk operations on multiple selected rows (delete, status change, export, assign, etc.).

**Configuration node:** `mass_actions`

### Built-in Delete

```yaml
mass_actions:
    delete:
        type: delete
        label: oro.grid.action.delete
        icon: trash-o
        data_identifier: e.id          # field from SELECT used to identify rows
        acl_resource: acme_entity_delete
```

### Custom Ajax Mass Action

```yaml
mass_actions:
    activate:
        type: ajax
        label: acme.action.activate
        icon: check
        route: oro_datagrid_mass_action
        handler: Acme\Bundle\Handler\ActivateHandler
        data_identifier: e.id
        acl_resource: acme_entity_edit
        allowedRequestTypes: [POST]
        requestType: POST
        defaultMessages:
            confirm_title: acme.confirm.activate.title
            confirm_content: acme.confirm.activate.content
            confirm_ok: acme.confirm.activate.ok
            success: acme.action.activate.success
            error: acme.action.activate.error
            empty_selection: acme.action.activate.empty
```

### Handler Implementation

```php
class ActivateHandler implements MassActionHandlerInterface
{
    public function __construct(
        private readonly EntityManagerInterface $em,
        private readonly AclHelper $aclHelper,
        private readonly TranslatorInterface $translator,
    ) {}

    public function handle(MassActionHandlerArgs $args): MassActionResponse
    {
        $count = 0;

        foreach ($args->getResults() as $result) {
            $entity = $this->em->find(MyEntity::class, $result->getValue('id'));
            if ($entity) {
                $entity->setStatus('active');
                $count++;
            }
        }

        $this->em->flush();

        return new MassActionResponse(
            true,
            $this->translator->trans('acme.activated', ['%count%' => $count])
        );
    }
}
```

### Disabling an Inherited Mass Action

```yaml
mass_actions:
    delete:
        disabled: true
```

### Parameter Table

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | Yes | — | `delete` or `ajax` |
| `label` | string | No | — | Button label |
| `icon` | string | No | — | Font Awesome icon |
| `handler` | string | No | — | Handler class FQCN (ajax type) |
| `route` | string | No | — | Route for the request |
| `data_identifier` | string | Yes | — | SELECT alias used as entity identifier |
| `acl_resource` | string | No | — | Permission check |
| `allowedRequestTypes` | array | No | `[GET]` | Allowed HTTP methods server-side |
| `requestType` | string | No | `GET` | HTTP method used |
| `defaultMessages` | array | No | — | UI messages (confirm, success, error) |
| `disabled` | bool | No | `false` | Remove this action |

### Registering Custom Mass Action Types

```php
class MyMassAction extends AbstractMassAction
{
    protected function getOptions(): OptionsResolver
    {
        return parent::getOptions()->setRequired('my_option');
    }
}
```

```yaml
acme.datagrid.mass_action.my_type:
    class: Acme\Bundle\MassAction\MyMassAction
    tags:
        - { name: oro_datagrid.extension.mass_action.type, type: my_type }
```

---

## 8. Pager Extension

**WHY:** Controls pagination behavior — how many rows per page, whether to show all rows, etc.

**Configuration node:** `options.toolbarOptions.pagination` and `options.toolbarOptions.pageSize`

### Standard Pagination

```yaml
options:
    toolbarOptions:
        pageSize:
            hide: false
            items: [10, 25, 50, 100]
            default_per_page: 25
        pagination:
            hide: false
```

### One-Page Mode (show all rows)

Displays all results on a single page (capped at 1000 rows).

```yaml
options:
    toolbarOptions:
        pagination:
            onePage: true
```

### Parameter Table

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `toolbarOptions.pageSize.hide` | bool | No | `false` | Hide the page size selector |
| `toolbarOptions.pageSize.items` | array | No | `[10,25,50,100]` | Available page size options |
| `toolbarOptions.pageSize.default_per_page` | int | No | `25` | Initial page size |
| `toolbarOptions.pagination.hide` | bool | No | `false` | Hide pagination controls |
| `toolbarOptions.pagination.onePage` | bool | No | `false` | Show all rows (max 1000), disable paging |

**Notes:**
- ORM datasource always has paging enabled when the pager extension is active.
- Setting `hide: true` on pagination disables the paginator extension entirely.

---

## 9. Sorter Extension

**WHY:** Manages column sorting — which columns are sortable, default sort order, toolbar sort controls, and multi-column sorting.

**Configuration node:** `sorters`

```yaml
sorters:
    # Sortable columns
    columns:
        name:
            data_name: e.name                    # property in result set
            type: string                         # affects toolbar sort labels
            apply_callback: ~                    # custom sort logic (callable)
            disabled: false                      # prevent sorting this column
        price:
            data_name: e.price
            type: decimal
        created_at:
            data_name: e.createdAt

    # Default sort order (applied on first load)
    default:
        created_at: DESC                         # column: direction (ASC|DESC)

    # Global sorter options
    toolbar_sorting: false                       # show sort in toolbar area
    multiple_sorting: false                      # allow sort by multiple columns
    disable_default_sorting: false               # skip applying default sort
    disable_not_selected_option: false           # hide "Please select" in toolbar sort
```

### Custom Sort Callback

When standard ORDER BY is insufficient (e.g., sort by computed value):

```yaml
sorters:
    columns:
        relevance:
            data_name: relevance
            apply_callback: "@acme.grid.sorter::applyRelevanceSorter"
```

```php
class RelevanceSorter
{
    public function applyRelevanceSorter(
        OrmDatasource $datasource,
        string $sortKey,
        string $direction
    ): void {
        $datasource->getQueryBuilder()
            ->addOrderBy('FIELD(e.status, :order_values)', $direction)
            ->setParameter('order_values', ['active', 'pending', 'inactive']);
    }
}
```

### Parameter Table

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `columns.<name>.data_name` | string | Yes | — | Result set property to sort on |
| `columns.<name>.type` | string | No | — | Type hint for toolbar sort labels |
| `columns.<name>.apply_callback` | callable | No | — | Custom sort function |
| `columns.<name>.disabled` | bool | No | `false` | Disable sorting for this column |
| `default.<column>` | string | No | — | Default sort column = `ASC`\|`DESC` |
| `toolbar_sorting` | bool | No | `false` | Show toolbar sort widget |
| `multiple_sorting` | bool | No | `false` | Multi-column sort support |
| `disable_default_sorting` | bool | No | `false` | Skip default sort on load |
| `disable_not_selected_option` | bool | No | `false` | Hide empty option in toolbar |

---

## 10. Totals Extension

**WHY:** Displays aggregate rows (sum, count, min, max, average) in the grid footer — useful for financial grids or statistical summaries.

**Configuration node:** `totals`

```yaml
totals:
    # Row 1: Grand total (all pages)
    grand_total:
        columns:
            order_count:
                label: 'Total Orders'
                expr: 'COUNT(o.id)'
                formatter: integer
            total_amount:
                label: 'Grand Total'
                expr: 'SUM(o.amount)'
                formatter: decimal
                divisor: 100          # divide raw value before display
            first_order:
                label: 'First Order'
                expr: 'MIN(o.createdAt)'
                formatter: date
            last_order:
                label: 'Last Order'
                expr: 'MAX(o.createdAt)'
                formatter: datetime
            avg_amount:
                label: 'Avg Amount'
                expr: 'AVG(o.amount)'
                formatter: decimal

    # Row 2: Page total (current page only)
    page_total:
        extends: grand_total          # inherit column config from grand_total
        per_page: true                # only aggregate current page data
        hide_if_one_page: true        # hide when all data fits one page
        columns:
            order_count:
                label: 'Page Orders'
            total_amount:
                label: 'Page Total'

    # Disable a total row inherited from parent grid
    grand_total:
        disabled: true
```

### Column Parameter Table

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `label` | string | No | — | Column label for this total row |
| `expr` | string | No | — | SQL aggregate expression (COUNT, SUM, MIN, MAX, AVG) |
| `formatter` | string | No | — | `date`, `datetime`, `decimal`, `integer`, `percent` |
| `divisor` | int | No | — | Divide raw value by this before display |

### Row Parameter Table

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `extends` | string | No | — | Inherit column config from another total row |
| `per_page` | bool | No | `false` | Calculate totals only for current page |
| `hide_if_one_page` | bool | No | `false` | Hide row when data fits on one page |
| `disabled` | bool | No | `false` | Remove this total row |

**Output format:** Each cell displays as `"label: aggregated_value"` (when both label and expr are set).

---

## 11. Toolbar Extension

**WHY:** Controls the overall toolbar appearance — visibility, page size selector, pagination controls.

**Configuration node:** `options.toolbarOptions`

```yaml
options:
    toolbarOptions:
        hide: false                    # hide the entire toolbar
        pageSize:
            hide: false                # hide the page size dropdown
            items: [10, 25, 50, 100]   # available page sizes
            default_per_page: 25       # initial page size
        pagination:
            hide: false                # hide pagination controls
            onePage: false             # show all rows (max 1000)
```

### Parameter Table

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `hide` | bool | No | `false` | Hide the entire toolbar |
| `pageSize.hide` | bool | No | `false` | Hide page size selector |
| `pageSize.items` | array | No | `[10,25,50,100]` | Available page size options |
| `pageSize.default_per_page` | int | No | `25` | Default page size |
| `pagination.hide` | bool | No | `false` | Hide pagination |
| `pagination.onePage` | bool | No | `false` | Show all rows, disable paging |

---

## 12. Filter Extension

**WHY:** Adds the filter panel above the grid allowing users to narrow results by field values.

**Configuration node:** `filters`

Filters are registered with: `{ name: oro_filter.extension.orm_filter.filter, type: <type> }`

### All Built-in Filter Types

#### string

```yaml
name:
    type: string
    data_name: e.name
    force_like: false     # force LIKE regardless of operator selection
    min_length: 0         # minimum characters before filter applies
    max_length: ~         # maximum characters
```

#### number / integer / decimal / currency / percent

```yaml
price:
    type: number          # also: integer, decimal, currency, percent
    data_name: e.price
    options:
        data_type: Oro\Bundle\FilterBundle\Form\Type\Filter\NumberFilterType::DATA_DECIMAL
```

#### date / datetime / time

```yaml
created_at:
    type: date            # also: datetime, time
    data_name: e.createdAt
```

#### choice

```yaml
status:
    type: choice
    data_name: e.status
    options:
        field_options:
            choices:
                Active: active
                Inactive: inactive
            multiple: false           # true for multi-select
```

#### entity

```yaml
category:
    type: entity
    data_name: e.category
    options:
        field_options:
            class: Acme\Bundle\Entity\Category
            choice_label: name
            multiple: true
            query_builder: ~          # optional custom QueryBuilder callback
```

#### boolean

```yaml
is_active:
    type: boolean
    data_name: e.isActive
```

#### exists (checks for NULL vs not NULL)

```yaml
has_image:
    type: exists
    data_name: e.imageFile
```

#### many_to_many

```yaml
tags:
    type: many_to_many
    data_name: e.tags
    options:
        field_options:
            class: Oro\Bundle\TagBundle\Entity\Tag
```

### Filter Default Values

```yaml
filters:
    columns:
        status:
            type: choice
            data_name: e.status
    default:
        status:
            value: active
```

### Creating Custom Filters

```php
class MyCustomFilter extends AbstractFilter
{
    public function apply(FilterDatasourceAdapterInterface $ds, $data): bool
    {
        // Modify the datasource query based on $data
        $this->applyFilterToClause($ds, $ds->expr()->eq('e.field', ':value'));
        $ds->setParameter('value', $data['value']);
        return true;
    }

    public function getForm(): FormInterface
    {
        return $this->formFactory->create(MyFilterType::class);
    }
}
```

```yaml
acme.filter.my_filter:
    class: Acme\Bundle\Filter\MyCustomFilter
    tags:
        - { name: oro_filter.extension.orm_filter.filter, type: my_filter }
```

---

## Extension Execution Order

Extensions are executed in priority order (higher = earlier). Default priorities:

| Extension | Priority |
|-----------|----------|
| Formatter | — |
| Pager | — |
| Sorter | — |
| Filter | — |
| Action | — |
| Mass Action | — |
| Toolbar | — |
| Grid Views | — |
| Export | — |
| Field ACL | — |
| Board | — |

Custom extensions receive priority 0 by default. Set priority in service tag:

```yaml
tags:
    - { name: oro_datagrid.extension, priority: 200 }
```

---

## Extension Decision Guide

| Need | Use Extension/Config |
|------|---------------------|
| Per-row navigate/edit/delete links | Action Extension (`actions`) |
| Bulk operations on selected rows | Mass Action Extension (`mass_actions`) |
| Download data as CSV/XLSX | Export Extension (`options.export`) |
| Hide columns from unauthorized users | Field ACL Extension (`fields_acl`) |
| Format values (URLs, translated, currency) | Formatter Extension (column `type`) |
| Save/load filter presets | Grid Views Extension (`options.gridViews`) |
| Edit cell values in-place | Inline Editing Extension (`inline_editing`) |
| Aggregate footer rows (sum, count) | Totals Extension (`totals`) |
| Control page size / pagination | Pager + Toolbar Extensions (`toolbarOptions`) |
| Sort by column | Sorter Extension (`sorters`) |
| User filter panel | Filter Extension (`filters`) |
