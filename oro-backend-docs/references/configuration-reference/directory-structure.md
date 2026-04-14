# OroCommerce Configuration File Directory Structure

> Source: https://doc.oroinc.com/master/backend/architecture/structure/

## AGENT QUERY HINTS

Use this file when:
- "Where do I put config X in Oro?"
- "What config files does Oro load from a bundle?"
- "When is navigation.yml / acls.yml / datagrids.yml loaded?"
- "What is the difference between services.yml and oro/app.yml?"
- "How does Oro merge YAML from multiple bundles?"
- "What file controls ACLs / menus / system settings / workflows?"

---

## Overview

Oro's configuration is split across Symfony-standard DI files and Oro-specific resource files.
Every bundle contributes its own slice; Oro merges them all at kernel warmup.

```
YourBundle/
└── Resources/
    └── config/
        ├── services.yml            # Symfony DI — services, parameters, tags
        ├── validation.yml          # Symfony validation constraints
        └── oro/                    # Oro-specific resource configs (all optional)
            ├── app.yml             # Bundle-level Symfony config (kernel extensions)
            ├── routing.yml         # Route definitions for this bundle
            ├── acls.yml            # ACL resource definitions
            ├── datagrids.yml       # Datagrid definitions
            ├── navigation.yml      # Menu items, trees, breadcrumbs, page titles
            ├── system_configuration.yml  # System settings groups, fields, tree
            ├── actions.yml         # Operations / action buttons
            ├── workflows.yml       # Workflow state machines
            ├── assets.yml          # Sass/CSS asset inputs
            ├── search.yml          # Search index mappings
            ├── entity.yml          # Entity config scope definitions (entity_config.yml)
            └── placeholders.yml    # Placeholder item + slot assignments
```

---

## Loading Mechanism

Oro uses a **resource loading + merge** strategy:

1. At kernel boot, `OroConfigExtension` (and bundle-specific extensions) scan **all registered bundles** for `Resources/config/oro/*.yml` files.
2. Files of the same type (e.g., all `navigation.yml`) are **deep-merged** in bundle registration order. Later bundles override earlier ones for scalar values; sequences are concatenated.
3. `services.yml` is loaded via each bundle's `DependencyInjection/Extension.php` using `$loader->load('services.yml')`. It is **not** auto-discovered.
4. The merged configuration is compiled into the DI container and cached under `var/cache/<env>/`.

**Triggering a reload after changes:**
```bash
php bin/console cache:clear
# For entity/config changes:
php bin/console oro:platform:update --force
```

---

## File-by-File Reference

---

### `Resources/config/services.yml`

**Purpose:** Symfony Dependency Injection — defines services, parameters, compiler passes, and tagged services for this bundle.

**Loading mechanism:** Called explicitly from `DependencyInjection/YourBundleExtension.php`:
```php
public function load(array $configs, ContainerBuilder $container): void
{
    $loader = new YamlFileLoader($container, new FileLocator(__DIR__ . '/../Resources/config'));
    $loader->load('services.yml');
}
```

**Merge behavior:** Not merged — each bundle loads its own file independently. Services with duplicate IDs in different bundles will **override** each other (last bundle wins).

**Skeleton:**
```yaml
parameters:
    acme_demo.some_param: 'value'

services:
    # Explicit ID style (preferred for public/tagged services)
    Acme\DemoBundle\Service\MyService:
        arguments:
            - '@doctrine'
            - '%acme_demo.some_param%'
        tags:
            - { name: oro_featuretogle.feature, feature: acme_demo_feature }

    # Alias style
    acme_demo.my_service:
        alias: Acme\DemoBundle\Service\MyService
        public: true

    # Auto-wired controllers
    Acme\DemoBundle\Controller\:
        resource: '../../Controller/'
        tags: ['controller.service_arguments']
```

**Common Oro-specific tags** (see `services-yml.md` for the full list):

| Tag | Purpose |
|-----|---------|
| `oro_datagrid.extension` | Register a datagrid extension |
| `oro_form.extension` | Register a form type extension |
| `oro_navigation.item.builder` | Custom menu builder |
| `oro_security.voter` | Custom ACL voter |
| `oro_importexport.strategy` | Import/export strategy |
| `oro_entity_config.attribute_type` | Custom attribute type |
| `oro.integration.channel_type` | Integration channel type |
| `kernel.event_listener` | Symfony event listener |
| `kernel.event_subscriber` | Symfony event subscriber |

---

### `Resources/config/oro/app.yml`

**Purpose:** Provides bundle-level **Symfony semantic configuration** — the same values you would put in `config/packages/*.yaml` at the app level, but scoped to this bundle.

**Loading mechanism:** Discovered automatically by Oro's `OroConfigExtension`. Merged into the Symfony container's extension configuration for the specified bundle alias.

**Merge behavior:** Deep-merged with other bundles' `app.yml` values. Useful for extending platform defaults without editing vendor files.

**When to use:** When you need to set `oro_api:`, `oro_entity:`, `oro_message_queue:`, or other bundle configuration from within your own bundle.

**Skeleton:**
```yaml
# Extends oro_entity global config from your bundle
oro_entity:
    exclusions:
        - { entity: Acme\DemoBundle\Entity\InternalLog, field: rawData }

# Add a custom message processor
oro_message_queue:
    transport:
        default: 'amqp'

# Configure API exposure
oro_api:
    entities:
        Acme\DemoBundle\Entity\Product:
            fields:
                internalCode:
                    exclude: true
```

---

### `Resources/config/oro/routing.yml`

**Purpose:** Registers Symfony routes for this bundle's controllers.

**Loading mechanism:** Imported into the main application `config/routes.yaml` (or discovered via bundle auto-loading in some Oro setups). Standard Symfony routing.

**Merge behavior:** Additive — routes accumulate across bundles. Route name conflicts cause errors.

**Skeleton:**
```yaml
acme_demo:
    resource: '@AcmeDemoBundle/Controller/'
    type: attribute          # uses PHP #[Route] attributes

# Or explicit routes:
acme_demo_index:
    path: /acme/demo
    defaults:
        _controller: Acme\DemoBundle\Controller\DemoController::indexAction
    methods: [GET]

# API routes
acme_demo_api:
    resource: '@AcmeDemoBundle/Resources/config/oro/routing_api.yml'
    prefix: /api/
```

---

### `Resources/config/oro/acls.yml`

**Purpose:** Declares ACL resources (permissions) that can be assigned in the role management UI.

**Loading mechanism:** Discovered by `OroSecurityBundle`'s configuration loader at container compilation. All bundles' `acls.yml` files are merged.

**Merge behavior:** Additive — each ACL ID must be unique across the application. Duplicate IDs cause compilation errors.

**Skeleton:**
```yaml
acls:
    # Action ACL — protects a UI action (not tied to a specific entity)
    acme_demo_manage:
        label: 'Acme Demo Management'
        type: action
        group_name: ''           # empty string = no group (shown at top level)
        category: acme_demo      # optional: groups in role management UI

    # Entity ACL — protects CRUD on a domain object
    acme_demo_product_view:
        label: 'View Acme Products'
        type: entity
        class: Acme\DemoBundle\Entity\Product
        permission: VIEW         # VIEW | CREATE | EDIT | DELETE | SHARE

    # With controller binding (auto-checks ACL on route access)
    acme_demo_product_create:
        label: 'Create Acme Products'
        type: entity
        class: Acme\DemoBundle\Entity\Product
        permission: CREATE
        bindings:
            - { class: Acme\DemoBundle\Controller\ProductController, method: createAction }
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `label` | string | yes | — | Human-readable name in role UI |
| `type` | string | yes | — | `action` or `entity` |
| `class` | string | entity only | — | FQCN of protected entity |
| `permission` | string | entity only | — | `VIEW`, `CREATE`, `EDIT`, `DELETE`, `SHARE` |
| `group_name` | string | no | — | Grouping in role management UI |
| `category` | string | no | — | Category for UI organization |
| `bindings` | list | no | — | Controller class + method auto-binding |

---

### `Resources/config/oro/assets.yml`

**Purpose:** Declares Sass/CSS input files that Oro's asset pipeline should compile and bundle.

**Loading mechanism:** Discovered by `OroAssetBundle` during `oro:assets:build`. All bundles' `assets.yml` files are merged; inputs are concatenated.

**Merge behavior:** Inputs are combined across all bundles. Order follows bundle registration order.

**Skeleton:**
```yaml
assets:
    css:
        inputs:
            # Path relative to bundle's public directory (after assets:install)
            - 'acmedemo/css/main.scss'
            - 'acmedemo/css/components/widget.scss'
            # Import from node_modules with ~ prefix
            - '~some-npm-package/dist/styles.css'
        auto_rtl_inputs:
            # Glob patterns — these files get RTL (right-to-left) processing
            - 'acmedemo/css/**'
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `css.inputs` | list | no | — | Sass/CSS files to compile and include |
| `css.auto_rtl_inputs` | list | no | — | Glob patterns for RTL plugin processing |

**After changes:**
```bash
php bin/console oro:assets:build
# or with symlinks for dev:
php bin/console assets:install --symlink && php bin/console oro:assets:build
```

---

### `Resources/config/oro/datagrids.yml`

**Purpose:** Defines data grids — server-rendered sortable, filterable, paginated tables used throughout the Oro admin UI.

**Loading mechanism:** Discovered and merged by `OroDataGridBundle`. All bundles' `datagrids.yml` files are deep-merged.

**Merge behavior:** Grids with the same name are merged (useful for extending vendor grids). New grid names are additive.

**Skeleton:**
```yaml
datagrids:
    acme-demo-product-grid:
        acl_resource: acme_demo_product_view    # ACL gate
        source:
            type: orm
            query:
                select:
                    - p.id
                    - p.name
                    - p.sku
                    - p.active
                from:
                    - { table: Acme\DemoBundle\Entity\Product, alias: p }
                where:
                    and:
                        - p.deleted = false
                orderBy:
                    - { column: p.name, dir: ASC }
        columns:
            name:
                label: acme.demo.product.name.label
                frontend_type: string
            sku:
                label: acme.demo.product.sku.label
                frontend_type: string
            active:
                label: acme.demo.product.active.label
                frontend_type: boolean
        sorters:
            columns:
                name:
                    data_name: p.name
                sku:
                    data_name: p.sku
            default:
                name: ASC
        filters:
            columns:
                name:
                    type: string
                    data_name: p.name
                active:
                    type: boolean
                    data_name: p.active
        properties:
            id: ~
            view_link:
                type: url
                route: acme_demo_product_view
                params: [id]
            edit_link:
                type: url
                route: acme_demo_product_edit
                params: [id]
        actions:
            view:
                type: navigate
                label: oro.grid.action.view
                link: view_link
                icon: eye
                rowAction: true
            edit:
                type: navigate
                label: oro.grid.action.edit
                link: edit_link
                icon: pencil
                acl_resource: acme_demo_product_edit
        options:
            export: true
            entity_pagination: true
```

---

### `Resources/config/oro/navigation.yml`

**Purpose:** Defines menu items, organizes them into menu trees, registers page title templates, and configures breadcrumbs.

**Loading mechanism:** Discovered by `OroNavigationBundle`. All bundles' `navigation.yml` files are deep-merged.

**Merge behavior:** Items and tree children are merged additively. A bundle can inject children into an existing vendor menu tree.

**Skeleton:**
```yaml
menu_config:
    # Step 1: Define individual menu items
    items:
        acme_demo_root:
            label: 'acme.demo.menu.root.label'
            uri: '#'
            extras:
                position: 250
                icon: fa-cube

        acme_demo_products:
            label: 'acme.demo.menu.products.label'
            route: acme_demo_product_index
            extras:
                position: 10

    # Step 2: Place items into named menu trees
    tree:
        # Built-in Oro menus: application_menu, usermenu, shortcuts, frontend_menu
        application_menu:
            children:
                acme_demo_root:
                    children:
                        acme_demo_products: ~

# Page title templates (keyed by route name)
titles:
    acme_demo_product_index: 'acme.demo.title.product_index'
    acme_demo_product_view: '%name% - acme.demo.title.product_view'
    acme_demo_product_edit: 'Edit %name%'
```

---

### `Resources/config/oro/system_configuration.yml`

**Purpose:** Adds fields and groups to the System > Configuration UI — allows users to manage application-wide settings through the admin panel.

**Loading mechanism:** Discovered by `OroConfigBundle`. All bundles' `system_configuration.yml` files are merged.

**Merge behavior:** Fields and groups are additive. Tree nodes are deep-merged; a bundle can inject its group into an existing vendor tree branch.

**Skeleton:**
```yaml
system_configuration:
    # Define configuration keys
    fields:
        acme_demo.feature_enabled:
            data_type: boolean
            type: Oro\Bundle\ConfigBundle\Form\Type\ConfigCheckbox
            options:
                label: acme.demo.system_config.feature_enabled.label
                tooltip: acme.demo.system_config.feature_enabled.tooltip
                required: false

        acme_demo.api_url:
            data_type: string
            type: Symfony\Component\Form\Extension\Core\Type\TextType
            options:
                label: acme.demo.system_config.api_url.label
                constraints:
                    - NotBlank: ~
                    - Url: ~

    # Logical groupings
    groups:
        acme_demo_settings:
            title: acme.demo.system_config.group.settings.label
            icon: fa-cube

    # Position in the tree
    tree:
        system_configuration:
            platform:
                children:
                    general_setup:
                        children:
                            acme_demo_settings:
                                children:
                                    - acme_demo.feature_enabled
                                    - acme_demo.api_url

    # Which fields are accessible via REST API
    api_tree:
        acme_demo:
            acme_demo.feature_enabled: ~
            acme_demo.api_url: ~
```

---

### `Resources/config/oro/actions.yml`

**Purpose:** Defines Operations — configurable buttons/links that appear in the UI for entities, datagrids, or views. Also known as "action buttons."

**Loading mechanism:** Discovered by `OroActionBundle`. All bundles' `actions.yml` files are merged.

**Merge behavior:** Operations are additive; same-name operations are merged.

**Skeleton:**
```yaml
operations:
    acme_demo_product_activate:
        label: 'acme.demo.operation.activate.label'
        enabled: true
        entities:
            - Acme\DemoBundle\Entity\Product
        routes:
            - acme_demo_product_view
        acl_resource: acme_demo_product_edit
        button_options:
            icon: fa-check
            class: btn-success
        frontend_options:
            confirmation:
                title: 'acme.demo.operation.activate.confirm.title'
                message: 'acme.demo.operation.activate.confirm.message'
        actions:
            - '@assign_value':
                attribute: $.data.active
                value: true
            - '@flush_entity':
                entity: $.data
```

---

### `Resources/config/oro/workflows.yml`

**Purpose:** Defines workflow state machines — multi-step processes with transitions, forms, and ACL controls for a given entity.

**Loading mechanism:** Discovered by `OroWorkflowBundle`. All bundles' `workflows.yml` files are merged.

**Merge behavior:** Workflow definitions are additive by name. Same-name workflows in multiple bundles cause conflicts.

**Skeleton:**
```yaml
workflows:
    acme_demo_order_flow:
        entity: Acme\DemoBundle\Entity\Order
        entity_attribute: order      # variable name inside workflow
        is_system: false             # true = cannot be disabled via UI
        start_step: pending
        steps_display_ordered: true

        attributes:
            notes:
                type: string
                property_path: entity.notes

        steps:
            pending:
                label: acme.demo.workflow.step.pending
                allowed_transitions: [approve, reject]
                order: 10
            approved:
                label: acme.demo.workflow.step.approved
                is_final: true
                order: 20
            rejected:
                label: acme.demo.workflow.step.rejected
                is_final: true
                order: 30

        transitions:
            approve:
                label: acme.demo.workflow.transition.approve
                step_to: approved
                acl_resource: acme_demo_order_approve
                display_type: dialog
                frontend_options:
                    icon: fa-check
                    class: btn-success
            reject:
                label: acme.demo.workflow.transition.reject
                step_to: rejected
                acl_resource: acme_demo_order_reject
                display_type: dialog

        transition_definitions:
            approve_definition:
                actions:
                    - '@assign_value':
                        attribute: $.data.approvedAt
                        value: '@now'
```

---

### `Resources/config/oro/search.yml`

**Purpose:** Defines which entity fields are indexed in Oro's search engine (Elasticsearch or ORM-based).

**Loading mechanism:** Discovered by `OroSearchBundle`. All bundles' `search.yml` files are merged.

**Skeleton:**
```yaml
search:
    Acme\DemoBundle\Entity\Product:
        alias: acme_demo_product
        search_template: '@AcmeDemo/Search/result.html.twig'
        title_fields: [name]
        route:
            name: acme_demo_product_view
            parameters:
                id: id
        fields:
            - { name: name, target_type: text, target_fields: [name, all_text] }
            - { name: sku, target_type: text, target_fields: [sku, all_text] }
            - { name: active, target_type: integer }
            - { name: createdAt, target_type: datetime }
```

---

### `Resources/config/oro/entity.yml`

**Purpose:** Declares custom entity configuration scopes and their item schemas. Used by `OroEntityConfigBundle` to register what options are available on entities/fields via `#[Config]` / `#[ConfigField]`.

**Loading mechanism:** Discovered by `OroEntityConfigBundle`. All bundles' `entity.yml` files are merged.

**Merge behavior:** Scopes and items within scopes are merged additively.

**Skeleton:**
```yaml
entity_config:
    acme_demo:                   # scope name — used as key in #[Config(defaultValues:)]
        entity:
            items:
                is_synced:
                    options:
                        priority: 10
                        auditable: false
                    form:
                        type: Symfony\Component\Form\Extension\Core\Type\CheckboxType
                        options:
                            label: 'Is Synced?'
                    grid:
                        type: boolean

        field:
            items:
                sync_field:
                    options:
                        priority: 5
                    form:
                        type: Symfony\Component\Form\Extension\Core\Type\TextType
```

---

### `Resources/config/oro/placeholders.yml`

**Purpose:** Inserts rendered content (templates or controller actions) into named placeholder slots in Oro's Twig layouts. Allows bundles to inject content without modifying vendor templates.

**Loading mechanism:** Discovered by `OroUIBundle`. All bundles' `placeholders.yml` files are merged.

**Merge behavior:** Items are additive. Same placeholder slot receives items from all bundles in order.

**Skeleton:**
```yaml
placeholders:
    items:
        acme_demo_product_sidebar_widget:
            template: '@AcmeDemo/Product/sidebar_widget.html.twig'
            acl: acme_demo_product_view
        acme_demo_complex_block:
            action: acme_demo_product_block    # calls controller action
            acl: acme_demo_product_view

    placeholders:
        # The slot name — referenced in Twig with {{ placeholder('product_sidebar') }}
        product_sidebar:
            items:
                acme_demo_product_sidebar_widget:
                    order: 100         # lower = rendered first
                acme_demo_complex_block:
                    order: 200
```

---

## Quick Reference: Which File for What Task?

| Task | File |
|------|------|
| Register a service / event listener / form type | `services.yml` |
| Override vendor Symfony config (API, cache, etc.) | `oro/app.yml` |
| Add a URL route | `oro/routing.yml` |
| Protect a controller or action with permissions | `oro/acls.yml` |
| Add a page to the admin menu | `oro/navigation.yml` |
| Add a setting to System > Configuration | `oro/system_configuration.yml` |
| Create a sortable/filterable data table | `oro/datagrids.yml` |
| Define a state machine process | `oro/workflows.yml` |
| Add a button to an entity view/edit page | `oro/actions.yml` |
| Include CSS/Sass in the asset build | `oro/assets.yml` |
| Make an entity/field searchable | `oro/search.yml` |
| Add custom config to entities via #[Config] | `oro/entity.yml` |
| Inject content into a Twig layout slot | `oro/placeholders.yml` |

---

## Cache Invalidation

| Change type | Required command |
|-------------|-----------------|
| `services.yml` | `php bin/console cache:clear` |
| `oro/*.yml` (most) | `php bin/console cache:clear` |
| Entity schema / migrations | `php bin/console oro:platform:update --force` |
| Entity config (#[Config]) | `php bin/console oro:entity-config:update` then `cache:clear` |
| Assets | `php bin/console oro:assets:build` |
| Search index | `php bin/console oro:search:reindex` |
