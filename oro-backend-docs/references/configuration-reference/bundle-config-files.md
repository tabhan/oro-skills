# OroCommerce Bundle Configuration Files

> Source: https://doc.oroinc.com/master/backend/configuration/yaml/bundles-config/

---

## AGENT QUERY HINTS

This file answers:
- "What YAML config files does an Oro bundle need?"
- "How do I define a system configuration field and read it in PHP?"
- "How do I add an admin menu item?"
- "How do I add a child menu under an existing parent tab?"
- "How do I hide an existing menu item?"
- "How do I register a route in Oro?"
- "How do I define ACLs in a config file (not PHP attributes)?"
- "How do I add columns to an existing datagrid?"
- "How do I create a new datagrid for a custom entity?"
- "What Oro-specific DI tags are available?"
- "How do I register a form type, autocomplete handler, or MQ processor?"
- "What is entity.yml and what does it do?"
- "How do system config values from multiple bundles get merged?"

---

## Complete Bundle Config Directory Layout

Every custom bundle that exposes admin UI, routes, menus, and services follows this layout:

```
src/Acme/Bundle/DemoBundle/
├── AcmeDemoBundle.php                          # Bundle class
├── DependencyInjection/
│   ├── AcmeDemoExtension.php                  # Loads services.yml
│   └── Configuration.php                      # DI config constants (optional)
└── Resources/
    └── config/
        ├── services.yml                        # Service definitions
        └── oro/
            ├── bundles.yml                     # Registers bundle with Oro auto-discovery
            ├── routing.yml                     # Route imports (auto-discovered)
            ├── navigation.yml                  # Admin menu structure
            ├── system_configuration.yml        # System settings UI fields
            ├── acls.yml                        # Non-entity ACL resources
            ├── datagrids.yml                   # Datagrid definitions and extensions
            └── entity.yml                      # Entity aliases for API/REST
```

WHY each file exists:
- `bundles.yml` — tells Oro's kernel to load this bundle without manual registration
- `routing.yml` — auto-discovered by `OroDistributionBundle`; no need to import in `config/routes.yaml`
- `navigation.yml` — merged by `OroNavigationBundle` across all bundles at runtime
- `system_configuration.yml` — merged by `OroConfigBundle` to build the System > Configuration UI
- `acls.yml` — defines non-entity ACL resources (action-type permissions)
- `datagrids.yml` — merged by `OroDataGridBundle`; can extend existing grids or define new ones
- `entity.yml` — registers entity short aliases used by the REST API and ACL descriptors

---

## bundles.yml

Registers the bundle for auto-discovery. Without this file, the bundle is ignored entirely.

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/bundles.yml

bundles:
  # Minimal form — just the FQCN
  - Acme\Bundle\DemoBundle\AcmeDemoBundle

  # With priority — lower number loads FIRST
  # WHY: Use priority when your bundle extends services defined in other bundles.
  #      The extending bundle must load AFTER the bundle it extends.
  - { name: Acme\Bundle\DemoBundle\AcmeDemoBundle, priority: 210 }
```

Priority guidelines:
- Most platform bundles use 0–200
- Custom application bundles typically use 200–250
- Higher priority (larger number) = loads later = can override earlier-loaded bundles

---

## routing.yml

Auto-discovered by Oro. All controllers in the bundle are automatically routed.

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/routing.yml

# Route name prefix (arbitrary, but use bundle-snake-case)
acme_demo:
    # PHP attribute-based routing — scans all controllers in the directory
    resource: "@AcmeDemoBundle/Controller"
    type: attribute

# For a single controller file:
acme_demo_api:
    resource: "@AcmeDemoBundle/Controller/Api/DocumentApiController.php"
    type: attribute
    # Optional: prefix all routes from this resource
    prefix: /api/acme
```

WHY `type: attribute`: OroCommerce 6.1 uses PHP 8 `#[Route]` attributes on controller methods. The `type: attribute` loader scans the controller directory and registers all `#[Route]`-annotated methods automatically.

Corresponding controller:

```php
<?php
// src/Acme/Bundle/DemoBundle/Controller/DocumentController.php

namespace Acme\Bundle\DemoBundle\Controller;

use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;
use Oro\Bundle\SecurityBundle\Attribute\Acl;
use Oro\Bundle\SecurityBundle\Attribute\AclAncestor;

class DocumentController extends AbstractController
{
    // Route name: acme_demo_document_index
    // WHY naming convention: match routes used in navigation.yml extras.routes[]
    #[Route('/documents', name: 'acme_demo_document_index')]
    #[Acl(id: 'acme_demo_document_view', type: 'entity',
          class: 'Acme\Bundle\DemoBundle\Entity\Document', permission: 'VIEW')]
    public function indexAction(): Response
    {
        return $this->render('@AcmeDemo/Document/index.html.twig');
    }

    #[Route('/documents/{id}', name: 'acme_demo_document_view', requirements: ['id' => '\d+'])]
    #[AclAncestor('acme_demo_document_view')]
    public function viewAction(int $id): Response
    {
        // ...
    }

    #[Route('/documents/create', name: 'acme_demo_document_create')]
    #[Acl(id: 'acme_demo_document_create', type: 'entity',
          class: 'Acme\Bundle\DemoBundle\Entity\Document', permission: 'CREATE')]
    public function createAction(): Response
    {
        // ...
    }
}
```

---

## navigation.yml

Builds the admin sidebar menu. All bundles' `navigation.yml` files are merged at runtime by `OroNavigationBundle`.

### Anatomy

The file has three sections:
1. `items` — declares each menu entry with its label, route, icon, and position
2. `tree` — assembles items into a hierarchy under a named root (`application_menu`)
3. `titles` — sets the browser page `<title>` for specific routes

### Minimal example: top-level tab + child page

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/navigation.yml

navigation:
    menu_config:
        items:
            # A top-level tab (clickable header in the sidebar)
            # WHY uri: '#' — the tab itself is not a link; its children are.
            acme_demo_tab:
                label: 'acme.demo.menu.tab.label'   # translation key
                uri: '#'
                position: 300                        # higher = further down the sidebar
                extras:
                    icon: fa-file-text-o             # FontAwesome 4.x icon class

            # A page link that lives under acme_demo_tab
            acme_demo_document_index:
                label: 'acme.demo.menu.documents.label'
                route: 'acme_demo_document_index'    # must match #[Route] name attribute
                position: 10
                extras:
                    # WHY routes[]: highlights this menu item as active when the current
                    # URL matches any of these route name patterns (wildcards supported).
                    routes: ['acme_demo_document_*']

        tree:
            # 'application_menu' is the root for the admin sidebar.
            # Other roots: 'shortcuts', 'user_menu'
            application_menu:
                children:
                    acme_demo_tab:
                        children:
                            acme_demo_document_index: ~   # ~ means no additional config

    # titles: maps route name → browser <title> string (translation key supported)
    titles:
        acme_demo_document_index: 'acme.demo.documents.page.title'
```

### Multi-level menu with submenus

```yaml
# Taken from BridgeThemeBundle / BridgeInsightBundle combination.
# Shows: top tab → submenu group → child pages

navigation:
    menu_config:
        items:
            # Tab defined in another bundle (BridgeCommonBundle)
            # bridge_tab:
            #     label: "bridge.menu.tab.label"
            #     uri: "#"
            #     position: 5
            #     extras:
            #         icon: fa-bold

            # Submenu group — a non-link header inside the tab
            bridge_insights_submenu:
                label: "bridge.menu.insights.label"
                uri: "#"
                position: 90
                extras:
                    icon: fa-lightbulb-o

            # Child pages under the submenu
            bridge_insight_index:
                label: "bridge.insight.menu.index.label"
                route: "oro_bridge_insight_index"
                position: 10
                extras:
                    routes: ["oro_bridge_insight_*"]

            bridge_insight_tag_index:
                label: "bridge.insight_tag.menu.index.label"
                route: "oro_bridge_insight_tag_index"
                position: 20
                extras:
                    routes: ["oro_bridge_insight_tag_*"]

            bridge_insight_author_index:
                label: "bridge.insight_author.menu.index.label"
                route: "oro_bridge_insight_author_index"
                position: 30
                extras:
                    routes: ["oro_bridge_insight_author_*"]

        tree:
            application_menu:
                children:
                    bridge_tab:              # parent tab (defined elsewhere)
                        children:
                            bridge_insights_submenu:    # submenu group
                                children:
                                    bridge_insight_index: ~
                                    bridge_insight_tag_index: ~
                                    bridge_insight_author_index: ~

    titles:
        oro_bridge_insight_index: "bridge.insight.page.title"
        oro_bridge_insight_tag_index: "bridge.insight_tag.page.title"
        oro_bridge_insight_author_index: "bridge.insight_author.page.title"
```

### Hiding existing menu items

To hide a menu item defined by a core Oro bundle or another custom bundle, override it with `display: false`. This is the correct approach — never remove items by editing vendor code.

```yaml
# src/Bridge/Bundle/BridgeCommonBundle/Resources/config/oro/navigation.yml

navigation:
    menu_config:
        items:
            # Hides the Taxes top-level tab entirely
            taxes_tab:
                display: false

            # Hides the Inventory top-level tab entirely
            inventory_tab:
                display: false

            # Hides individual Sales sub-menu items
            invoice_list:
                display: false
            sale_quote_list:
                display: false
            pricing_price_lists_list:
                display: false

            # Hides Marketing sub-menu items
            marketing_lists_list:
                display: false
            promotion_list:
                display: false
```

WHY this works: `OroNavigationBundle` merges all `navigation.yml` files. An `items` entry in any bundle can override the same-named entry from another bundle. Since Symfony loads bundles in priority order, higher-priority bundles override lower-priority ones.

### Adding items under an existing core tab

```yaml
# Add a child to the 'products_tab' which is defined in OroProductBundle
navigation:
    menu_config:
        items:
            bridge_product_information_list:
                label: 'bridge.product_information.entity_plural_label'
                route: bridge_product_information_index
                position: 1000
                extras:
                    routes: ['bridge_product_information_*']
                    icon: fa-bold
        tree:
            application_menu:
                children:
                    products_tab:              # pre-existing tab from OroProductBundle
                        children:
                            bridge_product_information_list: ~
```

### Page title patterns (oro_titles)

```yaml
# Also in navigation.yml — a different top-level key
oro_titles:
    # Simple static title
    acme_demo_document_index: 'acme.demo.documents.page.title'

    # Dynamic titles using entity field placeholders
    # %%entity_label%% = the entity's label (e.g. "Document")
    # %%title%% = a specific field (configured in entity #[Config])
    acme_demo_document_view: '%%entity_label%% - %%title%%'
    acme_demo_document_create: 'oro.ui.create_entity - %%entityName%%'
    acme_demo_document_update: '%%entity_label%% - %%title%% - oro.ui.edit'
```

---

## system_configuration.yml

Defines fields that appear in the admin System > Configuration panel. All bundles' files are merged at runtime.

### Structure

```yaml
system_configuration:
    groups:    # Section headers in the UI
    fields:    # Individual form fields
    tree:      # Hierarchy: where each group/field appears in the UI
    api_tree:  # Which fields are exposed via the Configuration REST API
```

### Complete realistic example (from BridgeIntegrationBundle + AaxisIntegrationBundle)

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/system_configuration.yml

system_configuration:
    # Groups are UI section headers — they group related fields together.
    # WHY define groups here: the tree references groups by key; they must exist before use.
    groups:
        acme_demo_integration:
            title: acme.system_configuration.groups.integration.title   # translation key
            icon: "fa-cog"                                               # FontAwesome icon
        acme_demo_api_settings:
            title: acme.system_configuration.groups.api_settings.title

    fields:
        # --- Boolean toggle (checkbox) ---
        # Key format: 'bundle_key.field_name'
        # WHY this format: ConfigManager uses 'bundle_key.field_name' as the lookup key.
        acme_demo.feature_enabled:
            data_type: boolean
            # WHY ConfigCheckbox instead of CheckboxType: ConfigCheckbox renders
            # the "Use Default" toggle that allows per-scope overriding.
            type: Oro\Bundle\ConfigBundle\Form\Type\ConfigCheckbox
            priority: 100         # higher = appears first within the group
            options:
                label: acme.system_configuration.fields.feature_enabled.label
                tooltip: acme.system_configuration.fields.feature_enabled.tooltip
                required: false

        # --- Plain text input ---
        acme_demo.api_endpoint:
            data_type: string
            type: Symfony\Component\Form\Extension\Core\Type\TextType
            priority: 90
            options:
                label: acme.system_configuration.fields.api_endpoint.label
                tooltip: acme.system_configuration.fields.api_endpoint.tooltip
                required: false
                constraints:
                    - Length:
                          max: 500    # prevent overly-long URLs

        # --- Integer with min/max validation ---
        acme_demo.api_timeout:
            data_type: integer
            type: Symfony\Component\Form\Extension\Core\Type\IntegerType
            priority: 80
            options:
                label: acme.system_configuration.fields.api_timeout.label
                tooltip: acme.system_configuration.fields.api_timeout.tooltip
                required: false
                constraints:
                    - Range:
                          min: 5
                          max: 300

        # --- Encrypted password field ---
        # WHY OroEncodedPlaceholderPasswordType: stores the value AES-encrypted in the DB.
        # The UI shows a placeholder instead of the plaintext value.
        # Use $crypter->decryptData($value) when reading in PHP.
        acme_demo.api_secret:
            data_type: string
            type: Oro\Bundle\FormBundle\Form\Type\OroEncodedPlaceholderPasswordType
            search_type: text     # needed so config search indexes this as text
            priority: 70
            options:
                label: acme.system_configuration.fields.api_secret.label
                tooltip: acme.system_configuration.fields.api_secret.tooltip
                resettable: true  # shows a "Reset to default" button
                required: false
                constraints:
                    - Length:
                          max: 255

    # tree: places groups and fields into the config UI hierarchy.
    # The standard path for custom integration settings is:
    #   system_configuration > platform > integrations > [your_group]
    tree:
        system_configuration:
            platform:
                children:
                    integrations:
                        children:
                            acme_demo_integration:
                                priority: 500      # higher = appears earlier in the list
                                children:
                                    acme_demo_api_settings:
                                        priority: 100
                                        children:
                                            - acme_demo.feature_enabled
                                            - acme_demo.api_endpoint
                                            - acme_demo.api_timeout
                                            - acme_demo.api_secret

    # api_tree: lists which fields can be read/written via the REST API.
    # Use ~ (null) to accept defaults. All listed fields become REST-accessible.
    api_tree:
        acme_demo.feature_enabled: ~
        acme_demo.api_endpoint: ~
        acme_demo.api_timeout: ~
        # api_secret intentionally omitted — never expose secrets via REST API
```

### How multiple bundles' configs merge

At runtime, Oro merges all `system_configuration.yml` files from all bundles using a deep array merge. The result is a single unified tree:

```
# BridgeIntegrationBundle defines:
system_configuration > platform > integrations > bridge_integration (priority: 1000)
    └── vm2_product_apis (priority: 40)
    └── sap_customer (priority: 30)
    └── sap_product (priority: 20)

# AaxisIntegrationBundle defines:
system_configuration > platform > integrations > aaxis_integration (priority: 1010)
    └── bucket_storage (priority: 100)

# Result after merge — both appear under 'integrations':
System > Configuration > Platform > Integrations
    ├── Aaxis Integration (priority 1010, shown first)
    │   └── Bucket Storage
    └── Bridge Integration (priority 1000, shown second)
        ├── VM2 Product APIs
        ├── SAP Customer
        └── SAP Product
```

WHY priority controls order: The `platform` and `integrations` keys are defined by `OroPlatformBundle`. Custom bundles inject their own subtrees into pre-existing nodes using `priority` to control relative position.

### Reading system config values in PHP

```php
<?php
// src/Acme/Bundle/DemoBundle/Service/DemoIntegrationService.php

namespace Acme\Bundle\DemoBundle\Service;

use Oro\Bundle\ConfigBundle\Config\ConfigManager;
use Oro\Bundle\SecurityBundle\Encoder\SymmetricCrypterInterface;

class DemoIntegrationService
{
    public function __construct(
        // Inject @oro_config.global for global (organization-independent) config.
        // Use @oro_config.user for user-scoped config.
        private readonly ConfigManager $configManager,
        private readonly SymmetricCrypterInterface $crypter,
    ) {}

    public function isEnabled(): bool
    {
        // Key format: 'bundle_key.field_name' — must match system_configuration.yml exactly.
        // WHY cast to bool: ConfigManager returns mixed; always cast to the expected type.
        return (bool) $this->configManager->get('acme_demo.feature_enabled');
    }

    public function getApiEndpoint(): string
    {
        return (string) ($this->configManager->get('acme_demo.api_endpoint') ?? '');
    }

    public function getApiTimeout(): int
    {
        return (int) ($this->configManager->get('acme_demo.api_timeout') ?? 30);
    }

    public function getApiSecret(): string
    {
        // Encrypted fields must be decrypted before use.
        // WHY: OroEncodedPlaceholderPasswordType stores AES-encrypted ciphertext.
        $encrypted = $this->configManager->get('acme_demo.api_secret');
        if (!$encrypted) {
            return '';
        }
        return $this->crypter->decryptData($encrypted);
    }
}
```

Corresponding service definition (wires the correct config manager instance):

```yaml
# services.yml
Acme\Bundle\DemoBundle\Service\DemoIntegrationService:
    arguments:
        $configManager: "@oro_config.global"
        $crypter: "@oro_security.encoder.default"
    public: true
```

Available `ConfigManager` service IDs:
| Service ID | Scope |
|------------|-------|
| `oro_config.global` | Global (organization-independent) settings |
| `oro_config.user` | Per-user settings |
| `oro_config.website` | Per-website settings (OroCommerce multi-site) |
| `oro_config.customer_group` | Per-customer-group settings |
| `oro_config.customer` | Per-customer settings |

---

## acls.yml

Defines non-entity ACL resources. Use this for action-type permissions that don't map to a specific entity (e.g., "can this user run the importer?", "can this user access the integration dashboard?").

Entity-type ACLs (VIEW, EDIT, CREATE, DELETE on an entity) are defined via `#[Acl]` attributes on controller methods — not in this file.

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/acls.yml

acls:
    # Non-entity action permission: grants/denies access to a feature area.
    # WHY type: action — there is no entity record to check ownership against.
    # Use this for: "Can this user see the integration dashboard?",
    #               "Can this role run this CLI command?"
    acme_demo_integration_view:
        type: action
        label: 'Acme Demo Integration Access'
        description: 'Grants access to the Acme Demo integration dashboard'
        group_name: "commerce"          # groups related ACLs in the role editor
        category: 'integration'         # sub-category within the group

    acme_demo_run_import:
        type: action
        label: 'Acme Demo Run Import'
        description: 'Allows triggering the Acme Demo import process'
        group_name: "commerce"
        category: 'integration'
```

Checking action ACL in a controller:

```php
// In a controller, check an action ACL defined in acls.yml:
#[AclAncestor('acme_demo_integration_view')]
public function dashboardAction(): Response { /* ... */ }

// Or programmatically in a service:
// $authorizationChecker->isGranted('acme_demo_integration_view')
```

ACL resource in acls.yml vs PHP attribute:
| Approach | When to use |
|----------|-------------|
| `acls.yml` | Non-entity action ACLs; permissions shared across multiple controllers |
| `#[Acl]` on controller method | Entity-type ACLs; or action ACLs used by a single controller |
| `#[AclAncestor]` | Reusing an ACL defined elsewhere (either yml or attribute) |

---

## datagrids.yml

Defines or extends admin data grid tables. All bundles' `datagrids.yml` files are merged.

### Creating a new datagrid for a custom entity

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/datagrids.yml

datagrids:
    acme-demo-document-grid:
        # WHY extended_entity_name: enables the "Manage columns" button in the UI,
        # which lets admins show/hide columns without code changes.
        extended_entity_name: Acme\Bundle\DemoBundle\Entity\Document

        source:
            type: orm                     # always 'orm' for Doctrine queries
            query:
                select:
                    - d.id
                    - d.subject
                    - d.description
                    - d.dueDate
                    - d.createdAt
                from:
                    - { table: Acme\Bundle\DemoBundle\Entity\Document, alias: d }
                # Optional: join related entities
                join:
                    left:
                        - { join: d.priority, alias: p }
                # Add to select if joining:
                # - p.label as priorityLabel

        columns:
            subject:
                label: acme.demo.document.subject.label
                # frontend_type default is 'string' — renders as plain text
            description:
                label: acme.demo.document.description.label
            dueDate:
                label: acme.demo.document.due_date.label
                frontend_type: datetime   # renders as formatted date/time
            createdAt:
                label: oro.ui.created_at
                frontend_type: datetime

        sorters:
            columns:
                subject:
                    data_name: d.subject
                dueDate:
                    data_name: d.dueDate
                createdAt:
                    data_name: d.createdAt
            default:
                dueDate: DESC             # sort newest due date first by default

        filters:
            columns:
                subject:
                    type: string
                    data_name: d.subject
                dueDate:
                    type: datetime
                    data_name: d.dueDate
                # Choice filter (dropdown) for status/enum fields:
                # status:
                #     type: choice
                #     data_name: d.status
                #     options:
                #         field_options:
                #             choices:
                #                 acme.demo.document.status.open: open
                #                 acme.demo.document.status.closed: closed

        # properties: defines computed columns (links) for row actions
        properties:
            id: ~                          # expose id so action URLs can use it
            view_link:
                type: url
                route: acme_demo_document_view
                params: [ id ]             # maps to route parameter {id}
            update_link:
                type: url
                route: acme_demo_document_update
                params: [ id ]
            delete_link:
                type: url
                route: oro_api_delete_acme_demo_document   # REST delete route
                params: [ id ]

        # actions: the row-level action buttons (view, edit, delete)
        actions:
            view:
                type: navigate
                label: oro.grid.action.view
                link: view_link
                icon: eye
                rowAction: true            # makes the entire row clickable
            update:
                type: navigate
                label: oro.grid.action.update
                link: update_link
                icon: edit
            delete:
                type: delete
                label: oro.grid.action.delete
                link: delete_link
                icon: trash
```

### Extending an existing core grid (adding columns)

Use the same grid key to extend — Oro deep-merges the definitions.

```yaml
# Taken from BridgeEntityBundle — extends the core 'customers-grid'

datagrids:
    # 'customers-grid' is defined by OroCustomerBundle.
    # Specifying the same key in your bundle's datagrids.yml EXTENDS it.
    # WHY: never edit vendor bundle files; extend via your own config instead.
    customers-grid:
        source:
            query:
                select:
                    # These selects are ADDED to the existing query, not replacing it.
                    # WHY: the merge is additive for arrays under 'select'.
                    - customer.bridgeUnique as bridge_unique
                    - customer.salesOrg as sales_org
        columns:
            bridge_unique:
                label: bridge.customer.bridge_unique.label
                order: 10                  # position within the column list
            name:
                order: 20                  # override position of existing 'name' column
            sales_org:
                label: bridge.customer.sales_org.label
                order: 30
        sorters:
            columns:
                bridge_unique:
                    data_name: customer.bridgeUnique
                sales_org:
                    data_name: customer.salesOrg
            default:
                bridge_unique: ASC
        filters:
            columns:
                bridge_unique:
                    type: string
                    data_name: customer.bridgeUnique
                sales_org:
                    type: string
                    data_name: customer.salesOrg
```

### Datagrid with Twig template column

Use this for custom rendering — status badges, icons, HTML content:

```yaml
# From BridgeInsightBundle

datagrids:
    bridge-insight-grid:
        source:
            type: orm
            query:
                select:
                    - i.id
                    - i.adminTitle
                    - i.status
                    - i.publishDate
                from:
                    - { table: Bridge\Bundle\BridgeInsightBundle\Entity\BridgeInsight, alias: i }
        columns:
            adminTitle:
                label: bridge.insight.admin_title.label
            status:
                label: bridge.insight.status.label
                # WHY type: twig + frontend_type: html:
                # Renders the column value using a Twig template, enabling
                # badges, icons, or any HTML output per row.
                type: twig
                template: '@BridgeInsight/BridgeInsight/Datagrid/status.html.twig'
                frontend_type: html
            publishDate:
                label: bridge.insight.publish_date.label
                frontend_type: datetime
            shareEnabled:
                label: bridge.insight.share_enabled.label
                frontend_type: boolean   # renders as a checkmark/X icon
```

### Datagrid with JOIN and COALESCE (localization-aware)

```yaml
# Handles localized strings: falls back to the default localization if no translation exists

datagrids:
    bridge-insight-tag-grid:
        source:
            type: orm
            query:
                select:
                    - t.id
                    # COALESCE handles fallback between string and text column types.
                    # WHY: OroLocalizationBundle stores translations in separate columns
                    # depending on the field type (short = string, long = text).
                    - COALESCE(nameLocalized.string, nameLocalized.text) as name
                    - COALESCE(descriptionLocalized.string, descriptionLocalized.text) as description
                from:
                    - { table: Bridge\Bundle\BridgeInsightBundle\Entity\BridgeInsightTag, alias: t }
                join:
                    left:
                        # conditionType: WITH + localization IS NULL = join the default locale row
                        - { join: t.names, alias: nameLocalized, conditionType: WITH, condition: 'nameLocalized.localization IS NULL' }
                        - { join: t.descriptions, alias: descriptionLocalized, conditionType: WITH, condition: 'descriptionLocalized.localization IS NULL' }
```

### Column `frontend_type` values

| Value | Renders as |
|-------|-----------|
| `string` | Plain text (default) |
| `html` | Raw HTML (use with `type: twig`) |
| `integer` | Integer (right-aligned) |
| `decimal` | Decimal number |
| `boolean` | Checkmark / X icon |
| `datetime` | Formatted date + time |
| `date` | Formatted date only |
| `currency` | Currency-formatted number |
| `select` | Translated choice label |

---

## entity.yml

Registers entity aliases used by the OroEntityBundle alias resolver. These aliases are required for:
1. The REST API (short entity name in endpoints)
2. ACL descriptor strings like `"entity:AcmeDemoBundle:Document"`
3. Some Oro form types that resolve entities by alias

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/entity.yml

oro_entity:
    entity_aliases:
        # Key: fully-qualified class name
        # alias: singular short name (used in URLs, API responses)
        # plural_alias: plural short name (used in list endpoints)
        Acme\Bundle\DemoBundle\Entity\Document:
            alias: acme_demo_document
            plural_alias: acme_demo_documents

        Acme\Bundle\DemoBundle\Entity\Priority:
            alias: acme_demo_priority
            plural_alias: acme_demo_priorities
```

WHY aliases matter: When the REST API generates endpoint paths like `/api/acme_demo_documents`, it uses the `plural_alias`. ACL check strings like `getOid('entity:AcmeDemo:Document')` resolve via bundle + short entity name.

---

## services.yml

Standard Symfony DI container configuration, with Oro-specific tags.

### Recommended structure

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/services.yml

services:
    _defaults:
        # autowire: inject constructor arguments by type automatically
        # WHY: reduces boilerplate for straightforward services
        autowire: true
        # autoconfigure: automatically add tags based on implemented interfaces
        # WHY: e.g., services implementing CommandInterface get console.command tag
        autoconfigure: true
        public: false    # private by default; set public: true only when needed

    # ----------------------------------------------------------------
    # 1. Bulk namespace registration (recommended for most classes)
    # ----------------------------------------------------------------
    Acme\Bundle\DemoBundle\:
        resource: '../../*'
        exclude: '../../{DependencyInjection,Resources,Entity,Migrations}'
        # WHY exclude DependencyInjection: those classes are loaded by the kernel,
        # not as regular services.
        # WHY exclude Entity: Doctrine entities are not services.

    # ----------------------------------------------------------------
    # 2. Explicit services that need specific config beyond autowiring
    # ----------------------------------------------------------------

    # Service reading system config values
    # WHY explicit: autowiring cannot distinguish between multiple ConfigManager services
    Acme\Bundle\DemoBundle\Service\DemoIntegrationService:
        arguments:
            $configManager: "@oro_config.global"
            $crypter: "@oro_security.encoder.default"
        public: true     # public because it may be fetched from container directly

    # ----------------------------------------------------------------
    # 3. Controllers (required tag for attribute-based routing to work)
    # ----------------------------------------------------------------
    Acme\Bundle\DemoBundle\Controller\DocumentController:
        tags:
            - { name: controller.service_arguments }

    # ----------------------------------------------------------------
    # 4. Form types
    # ----------------------------------------------------------------
    acme_demo.form.type.document:
        class: Acme\Bundle\DemoBundle\Form\Type\DocumentType
        tags:
            # WHY form.type: registers the class with Symfony's form registry.
            # Without this tag, the form type cannot be used by string alias.
            - { name: form.type }

    # ----------------------------------------------------------------
    # 5. Event listeners
    # ----------------------------------------------------------------
    acme_demo.event_listener.category_form:
        class: Acme\Bundle\DemoBundle\EventListener\CategoryFormListener
        tags:
            # kernel.event_listener: hook into any Symfony or Oro event
            - { name: kernel.event_listener, event: oro_ui.scroll_data.before.category-edit, method: onCategoryEdit }
            - { name: kernel.event_listener, event: oro_ui.scroll_data.before.category-create, method: onCategoryEdit }

    # ----------------------------------------------------------------
    # 6. Autocomplete search handlers (entity lookup in form fields)
    # ----------------------------------------------------------------
    acme_demo.autocomplete.document_search:
        class: Acme\Bundle\DemoBundle\Autocomplete\DocumentSearchHandler
        arguments:
            - 'Acme\Bundle\DemoBundle\Entity\Document'
            - ['subject']   # fields to search/display
        calls:
            - [initSearchIndexer, ['@oro_search.index', '@oro_search.provider.search_mapping']]
            - [initDoctrinePropertiesByManagerRegistry, ['@doctrine']]
            - [setAclHelper, ['@oro_security.acl_helper']]
            - [setPropertyAccessor, ['@property_accessor']]
        tags:
            # WHY oro_form.autocomplete.search_handler: registers this as the backend
            # for an autocomplete widget in forms.
            # alias: matches the 'autocomplete_alias' in the form type definition.
            # acl_resource: the ACL id checked before returning results.
            - { name: oro_form.autocomplete.search_handler, alias: acme_demo_documents, acl_resource: acme_demo_document_view }

    # ----------------------------------------------------------------
    # 7. Message Queue processors (async background jobs)
    # ----------------------------------------------------------------
    Acme\Bundle\DemoBundle\Async\DocumentSyncProcessor:
        arguments:
            - '@doctrine.orm.entity_manager'
            - '@logger'
        tags:
            # oro_message_queue.client.message_processor: registers as an MQ consumer.
            # queueName: which queue to consume from (default, integration, etc.)
            - { name: oro_message_queue.client.message_processor, queueName: integration }

    # MQ Topic definition (required for typed MQ messages in Oro 6.x)
    Acme\Bundle\DemoBundle\Async\Topic\DocumentSyncTopic:
        tags:
            - { name: oro_message_queue.topic }

    # ----------------------------------------------------------------
    # 8. Console commands
    # ----------------------------------------------------------------
    Acme\Bundle\DemoBundle\Command\ImportDocumentsCommand:
        tags:
            - { name: console.command }

    # ----------------------------------------------------------------
    # 9. Repository services (when needing direct injection of a repository)
    # ----------------------------------------------------------------
    acme_demo.repository.document:
        class: Acme\Bundle\DemoBundle\Entity\Repository\DocumentRepository
        factory: ['@doctrine.orm.entity_manager', getRepository]
        arguments:
            - 'Acme\Bundle\DemoBundle\Entity\Document'

    # ----------------------------------------------------------------
    # 10. Service decoration (replace a core service)
    # ----------------------------------------------------------------
    acme_demo.decorated_price_calculator:
        class: Acme\Bundle\DemoBundle\Service\CustomPriceCalculator
        # WHY decorates: substitutes the decorated service everywhere it is injected,
        # while the original service remains available as .inner.
        decorates: oro_pricing.calculator.product_price
        arguments:
            - '@acme_demo.decorated_price_calculator.inner'

    # ----------------------------------------------------------------
    # 11. Scope criteria providers (used for multi-scope content)
    # ----------------------------------------------------------------
    acme_demo.scope_criteria_provider.website:
        parent: oro_website.website_scope_criteria_provider
        tags:
            # scopeType: the scope type this provider applies to
            # priority: higher priority providers are evaluated first (after array_reverse)
            - { name: oro_scope.provider, scopeType: acme_demo_scope, priority: 20 }

    acme_demo.scope_criteria_provider.customer:
        parent: oro_customer.customer_scope_criteria_provider
        tags:
            - { name: oro_scope.provider, scopeType: acme_demo_scope, priority: 40 }

    # ----------------------------------------------------------------
    # 12. Interface-based auto-tagging with _instanceof
    # ----------------------------------------------------------------
    _instanceof:
        # WHY _instanceof: automatically tags/configures all classes that implement
        # a given interface, without requiring explicit per-class tags.
        Acme\Bundle\DemoBundle\Service\ExporterInterface:
            public: true
            tags: ['acme_demo.exporter']
```

### Common Oro-specific DI tags reference

| Tag | Purpose |
|-----|---------|
| `controller.service_arguments` | Required for controllers using PHP attributes for routing |
| `form.type` | Registers a Symfony form type |
| `kernel.event_listener` | Symfony/Oro event listener |
| `kernel.event_subscriber` | Symfony event subscriber |
| `console.command` | Registers a console command |
| `oro_message_queue.topic` | Declares a typed MQ message topic |
| `oro_message_queue.client.message_processor` | Registers an async MQ processor |
| `oro_datagrid.extension` | Adds behavior to all or specific grids |
| `oro_form.autocomplete.search_handler` | Backend for form autocomplete widgets |
| `oro_scope.provider` | Provides criteria for a scope type |
| `oro_payment.payment_method_provider` | Registers a payment method |
| `oro_shipping.shipping_method_provider` | Registers a shipping method |
| `oro_importexport.strategy` | Registers an import/export strategy |

---

## How Configs Are Merged at Runtime

### Merge process

1. Symfony kernel boots and discovers all bundles via `bundles.yml`
2. `OroDistributionBundle` scans all bundles for `Resources/config/oro/*.yml` files
3. Each config type (`navigation.yml`, `datagrids.yml`, etc.) is loaded and deep-merged
4. Result is cached in `var/cache/` as compiled PHP

### Deep merge rules

- **Scalar values** (strings, booleans, integers): later bundle wins
- **Associative arrays** (keyed YAML maps): keys are merged recursively
- **Indexed arrays** (YAML lists): concatenated (items from all bundles are combined)

Practical consequence:
- `columns` in a datagrid extend is merged — your columns are ADDED to the existing ones
- `select` in a datagrid source query is APPENDED — your selects are added to the existing query
- `items` in navigation are merged — your item overrides `display: false` on an existing item

### Cache invalidation

After any `*.yml` config change:
```bash
php bin/console cache:clear
```

After entity config changes (`entity.yml`, `entity_extend.yml`, `#[Config]` attributes):
```bash
php bin/console oro:platform:update --force
```

---

## Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Wrong config key format | ConfigManager returns null | Use `bundle_key.field_name` exactly matching `system_configuration.yml` field key |
| Not casting ConfigManager return | Type errors (returns mixed) | Always cast: `(bool)`, `(string)`, `(int)` |
| Encrypted field not decrypted | Garbled or encrypted string in service | Call `$crypter->decryptData($value)` for `OroEncodedPlaceholderPasswordType` fields |
| Missing `display: false` for menu hiding | Can't hide vendor menu items | Add `items: { existing_item_key: { display: false } }` in your navigation.yml |
| Datagrid extension missing `extended_entity_name` | "Manage columns" button missing | Add `extended_entity_name: Full\Class\Name` at the top of the grid config |
| Navigation item added but not in tree | Item defined but not visible | Every item must appear in `tree > application_menu > children > ...` |
| Routes not loading | Controller actions unreachable | Ensure `routing.yml` has `type: attribute` and correct bundle shortname |
| Forgetting to clear cache | Config changes have no effect | Run `php bin/console cache:clear` after any config file change |
