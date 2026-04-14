# OroCommerce navigation.yml — Complete Reference

> Source: https://doc.oroinc.com/master/backend/configuration/yaml/navigation/

## AGENT QUERY HINTS

Use this file when:
- "How do I add a menu item to the Oro admin sidebar/menu?"
- "How do I add my bundle to the application_menu?"
- "What is the navigation.yml schema?"
- "How do I set the page title for a route in Oro?"
- "How do I add breadcrumbs?"
- "What menu trees exist in Oro by default?"
- "How do I control menu item order / position?"
- "What is the `extras` key in navigation items?"
- "How do I restrict a menu item with ACL?"
- "How do I add an item to the user dropdown menu?"
- "What is the #[TitleTemplate] attribute?"

---

## Overview

`navigation.yml` lives at `Resources/config/oro/navigation.yml` in each bundle.
It is discovered and deep-merged by `OroNavigationBundle` at container warmup.

**Root keys:**
```yaml
menu_config:        # menu items and tree structure
titles:             # page title templates per route
```

---

## Full Schema Reference

```yaml
# Root node
menu_config:

    # ─────────────────────────────────────────────
    # items: define all individual menu entries
    # ─────────────────────────────────────────────
    items:
        my_item_key:              # unique identifier — used in tree references
            label: 'translation.key.for.label'  # auto-translated
            translateDomain: messages            # optional; translation domain
            translateParameters: {}             # optional; parameters for translator

            # Navigation target — use ONE of:
            route: my_symfony_route_name        # Symfony route (preferred)
            uri: '#'                            # static URI or placeholder

            # Access control
            aclResourceId: my_acl_resource_id  # hides item if user lacks permission
            showNonAuthorized: false            # show even when not logged in

            # HTML attributes (applied to the <li> element)
            attributes:
                class: 'my-custom-class'
                data-id: 'some-value'

            # HTML attributes for the label/link element
            labelAttributes:
                class: 'nav-link-label'

            # HTML attributes for the <ul> children container
            childrenAttributes:
                class: 'dropdown-menu'

            # Oro-specific extras
            extras:
                position: 100           # integer; lower = appears first among siblings
                icon: fa-cube           # Font Awesome icon (fa- prefix)
                description: 'Human readable description'
                routes:                 # mark item as "active" when on these routes
                    - my_route
                    - my_route_edit
                safe_label: false       # set true to allow raw HTML in label

    # ─────────────────────────────────────────────
    # templates: rendering configuration for menus
    # ─────────────────────────────────────────────
    templates:
        my_template_key:
            template: '@OroNavigation/Menu/oro_menu.html.twig'
            allow_safe_labels: false        # enable unescaped HTML when safe_label=true
            currentClass: 'active'          # CSS class for the current active item
            currentAsLink: true             # allow clicking the current item
            ancestorClass: 'active'         # CSS class for ancestor items
            firstClass: 'first'             # CSS class for first item at each level
            lastClass: 'last'               # CSS class for last item at each level
            rootClass: 'nav'                # CSS class for root menu element

    # ─────────────────────────────────────────────
    # tree: map items into named menus
    # ─────────────────────────────────────────────
    tree:
        application_menu:       # the named menu (must match Oro's built-in or custom)
            type: navbar        # template key (root items only)
            children:
                my_root_item:
                    children:
                        my_child_item: ~        # ~ = leaf node, no children
                        my_other_child: ~

# ─────────────────────────────────────────────
# titles: page title templates, keyed by route name
# ─────────────────────────────────────────────
titles:
    my_route_index: 'My Entity List'
    my_route_view: '%name% - My Entity'    # %placeholder% filled via oro_title_set()
    my_route_create: 'Create My Entity'
    my_route_edit: 'Edit %name%'
```

---

## Parameters Reference

### `menu_config.items.*` Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `label` | string | yes | — | Translation key for item text |
| `translateDomain` | string | no | `messages` | Translation domain |
| `translateParameters` | map | no | `{}` | Parameters passed to translator |
| `route` | string | no* | — | Symfony route name for URL generation |
| `uri` | string | no* | — | Static URI (`#` for non-link parents) |
| `aclResourceId` | string | no | — | ACL ID; item hidden if user lacks permission |
| `showNonAuthorized` | boolean | no | `false` | Show item even when not authenticated |
| `attributes` | map | no | — | HTML attributes on the `<li>` element |
| `labelAttributes` | map | no | — | HTML attributes on the `<a>` or label element |
| `childrenAttributes` | map | no | — | HTML attributes on child `<ul>` |
| `extras.position` | integer | no | `0` | Sort order; lower = first |
| `extras.icon` | string | no | — | Font Awesome icon name (without `fa-` for some contexts) |
| `extras.description` | string | no | — | Human-readable description |
| `extras.routes` | list | no | — | Route patterns for active-state detection |
| `extras.safe_label` | boolean | no | `false` | Allow raw HTML in label |

*Either `route` or `uri` must be provided.

### `menu_config.templates.*` Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `template` | string | yes | — | Twig template path |
| `allow_safe_labels` | boolean | no | `false` | Enable HTML labels when item has `safe_label: true` |
| `currentClass` | string | no | — | CSS class for active item |
| `currentAsLink` | boolean | no | `true` | Allow clicking the current item |
| `ancestorClass` | string | no | — | CSS class for ancestors of active item |
| `firstClass` | string | no | — | CSS class for first sibling |
| `lastClass` | string | no | — | CSS class for last sibling |
| `rootClass` | string | no | — | CSS class for the root element |

### `menu_config.tree.*` Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `type` | string | no | — | Template identifier (root menu items only) |
| `children` | map | yes | — | Map of item keys to child configurations |

---

## Built-in Oro Menu Names

| Menu Name | Location | Usage |
|-----------|---------|-------|
| `application_menu` | Top horizontal navigation bar | Main nav for backend admin |
| `usermenu` | User avatar dropdown (top-right) | User actions, logout, profile |
| `shortcuts` | Shortcut bar above main menu | Quick-access shortcuts |
| `frontend_menu` | Storefront top navigation | Customer-facing primary nav |
| `frontend_customer_usermenu` | Storefront user dropdown | Customer account links |
| `frontend_quick_access_menu` | Storefront quick links | Cart, account quick links |
| `oro_customer_breadcrumbs_menu` | Storefront breadcrumbs | Breadcrumb source |

---

## Practical Examples

### Example 1: Add a Top-Level Section to Admin Menu

```yaml
menu_config:
    items:
        acme_demo_section:
            label: acme.demo.menu.section.label
            uri: '#'
            extras:
                position: 350
                icon: fa-cogs

        acme_demo_products:
            label: acme.demo.menu.products.label
            route: acme_demo_product_index
            aclResourceId: acme_demo_product_view
            extras:
                position: 10

        acme_demo_categories:
            label: acme.demo.menu.categories.label
            route: acme_demo_category_index
            aclResourceId: acme_demo_category_view
            extras:
                position: 20

    tree:
        application_menu:
            children:
                acme_demo_section:
                    children:
                        acme_demo_products: ~
                        acme_demo_categories: ~
```

### Example 2: Add Item to User Dropdown

```yaml
menu_config:
    items:
        acme_demo_my_profile:
            label: acme.demo.menu.my_profile.label
            route: acme_demo_user_profile
            extras:
                position: 50

    tree:
        usermenu:
            children:
                acme_demo_my_profile: ~
```

### Example 3: Inject Child into Existing Vendor Menu

```yaml
# Add under an existing "Catalog" section in OroCommerce:
menu_config:
    items:
        acme_demo_custom_catalog_item:
            label: acme.demo.menu.custom_catalog.label
            route: acme_demo_custom_catalog_index
            extras:
                position: 250

    tree:
        application_menu:
            children:
                catalog:          # existing Oro vendor item key
                    children:
                        acme_demo_custom_catalog_item: ~
```

---

## Page Titles

### Option A: `navigation.yml` titles section

```yaml
titles:
    acme_demo_product_index: 'acme.demo.title.product_index'
    acme_demo_product_view: '%name% - acme.demo.title.product'
    acme_demo_product_edit: 'acme.demo.title.product_edit'
```

WHY: The title is a translation key (Oro translates it automatically). Placeholders `%name%` are filled in Twig using `oro_title_set()`.

### Option B: #[TitleTemplate] PHP Attribute on Controller

```php
use Oro\Bundle\NavigationBundle\Attribute\TitleTemplate;

#[TitleTemplate('acme.demo.title.product_view')]
public function viewAction(Product $product): Response
{
    // Fill the %name% placeholder from the template:
    // {% oro_title_set({params: {"%name%": product.name}}) %}
}
```

### Setting Title Placeholders in Twig

```twig
{# In your view template: #}
{% oro_title_set({params: {"%name%": entity.name}}) %}
```

---

## Breadcrumbs

Breadcrumbs in Oro's backend are derived automatically from the menu tree structure.
For storefront (frontend) breadcrumbs, use layout updates:

```yaml
# In a layout update YAML:
layout:
    actions:
        - '@add':
            id: breadcrumbs
            parentId: page_main_header
            blockType: breadcrumbs
            options:
                menu_name: oro_customer_breadcrumbs_menu
```

Or with dynamic breadcrumb data:
```yaml
layout:
    actions:
        - '@add':
            id: product_breadcrumbs
            parentId: page_content
            blockType: breadcrumbs
            options:
                breadcrumbs: '=data["product_breadcrumbs"].getItems()'
```

---

## Merge Behavior

When two bundles both define children for `application_menu`:

```yaml
# Bundle A's navigation.yml
menu_config:
    tree:
        application_menu:
            children:
                section_a: ~

# Bundle B's navigation.yml
menu_config:
    tree:
        application_menu:
            children:
                section_b: ~

# Result after merge:
menu_config:
    tree:
        application_menu:
            children:
                section_a: ~
                section_b: ~
```

Both items are present. Order is controlled by `extras.position`, not file order.

---

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Missing `route` and `uri` | Item renders with no link or throws error | Add `uri: '#'` for parent items, `route:` for leaf items |
| Wrong `aclResourceId` | Item always hidden | Verify ACL ID matches exactly what is in `acls.yml` |
| Not registering item in `items:` | Tree reference fails silently | Always declare in `items:` before using in `tree:` |
| Duplicating an item key | Last definition wins | Use unique keys per bundle; prefix with bundle name |
| `position` not working | Items in wrong order | `position` is under `extras:`, not top-level |
| Title not showing | Page shows route name or empty | Add entry to `titles:` section keyed by exact route name |
