# OroCommerce placeholders.yml — Complete Reference

> Source: https://doc.oroinc.com/master/backend/configuration/yaml/placeholders/

## AGENT QUERY HINTS

Use this file when:
- "How do I inject content into an Oro Twig template without editing the template?"
- "What is placeholders.yml in Oro?"
- "How does the Oro placeholder system work?"
- "How do I add a widget/block to an existing Oro page?"
- "What is the difference between template and action in a placeholder item?"
- "How do I control placeholder item rendering order?"
- "How do I restrict a placeholder item with ACL?"
- "How do I use `placeholder()` in Twig?"
- "What is `applicable` in a placeholder item?"
- "How do I add content to a view page without touching vendor templates?"

---

## Overview

The Oro placeholder system (`OroUIBundle`) allows bundles to **inject rendered
content into named slots in existing Twig templates** without modifying those
templates. This is the primary extension mechanism for inserting blocks, widgets,
and actions into views owned by other bundles.

**File location:** `Resources/config/oro/placeholders.yml` in each bundle.

**Loading:** Discovered by `OroUIBundle` at container warmup. All bundles'
`placeholders.yml` files are deep-merged.

**Root node:** `placeholders`

---

## How It Works

1. A Twig template (in any bundle, including vendor) calls `{{ placeholder('slot_name') }}`.
2. Oro looks up all items assigned to `slot_name` in the merged `placeholders.yml`.
3. For each item (sorted by `order`), it checks:
   - Does the current user have the required `acl`?
   - Does the `applicable` expression evaluate to true?
4. If checks pass, Oro renders either:
   - A **template** — includes a Twig template file.
   - An **action** — calls a Symfony controller action and embeds its response.
5. All rendered outputs are concatenated and returned.

---

## Full Schema Reference

```yaml
placeholders:

    # ─────────────────────────────────────────────────────────────
    # items: define reusable content blocks
    # ─────────────────────────────────────────────────────────────
    items:
        acme_demo_product_sidebar_widget:
            # Option A: include a Twig template
            template: '@AcmeDemo/Product/Placeholder/sidebar_widget.html.twig'

            # Option B: call a controller action (use either template OR action, not both)
            # action: acme_demo_product_sidebar    # route name or controller::action

            # Access control — item is skipped if user lacks this permission
            acl: acme_demo_product_view                # ACL resource ID from acls.yml

            # Runtime applicability expression (checked after ACL)
            # Uses ExpressionLanguage; can access request parameters
            applicable: '!context["entity"] or context["entity"] instanceof Acme\DemoBundle\Entity\Product'

        acme_demo_order_summary_block:
            template: '@AcmeDemo/Order/Placeholder/summary.html.twig'
            acl: acme_demo_order_view

        acme_demo_complex_panel:
            # Controller action — useful for complex logic that needs a service
            action: acme_demo_render_complex_panel
            # The route/controller::method must return a Response object
            acl: acme_demo_panel_view

    # ─────────────────────────────────────────────────────────────
    # placeholders: assign items to named slots
    # ─────────────────────────────────────────────────────────────
    placeholders:
        # Slot name — must match what the Twig template calls:
        # {{ placeholder('product_sidebar') }}
        product_sidebar:
            items:
                acme_demo_product_sidebar_widget:
                    order: 100          # lower = rendered first; omit or use ~ for unordered
                acme_demo_complex_panel:
                    order: 200

        # Adding to a vendor slot (e.g., the entity view page header)
        entity_view_after_content:
            items:
                acme_demo_order_summary_block: ~    # ~ = no explicit order
```

---

## Parameters Reference

### `items.*` Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `template` | string | no* | — | Twig template path (use `@BundleName/...` notation) |
| `action` | string | no* | — | Route name or `Controller::method` — called and embedded |
| `acl` | string | no | — | ACL resource ID; item hidden if user lacks permission |
| `applicable` | string | no | — | ExpressionLanguage expression; false = item skipped |

*Provide either `template` or `action`, not both. At least one is required.

### `placeholders.*` Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `items` | map | yes | — | Map of item keys assigned to this slot |

### `placeholders.*.items.*` Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `order` | integer | no | `0` | Render order; lower numbers render first |

Use `~` (YAML null) when you don't need a specific order:
```yaml
placeholders:
    my_slot:
        items:
            my_item: ~
```

---

## Template vs Action — When to Use Which

| Use `template` when... | Use `action` when... |
|------------------------|----------------------|
| Simple HTML rendering with passed context | Complex PHP logic needed before rendering |
| Only needs Twig variables from current context | Needs to call services, run queries |
| Static or view-only content | Content depends on entity state or external calls |
| Better performance (no HTTP sub-request) | Reusable controller logic already exists |

---

## Using `{{ placeholder() }}` in Twig

To create a new slot in your own templates:

```twig
{# In your Twig template #}
<div class="sidebar">
    {{ placeholder('my_custom_sidebar_slot') }}
</div>

{# With context variables passed to items #}
{{ placeholder('product_actions', {entity: product, user: app.user}) }}
```

Context variables are available in item templates and in `applicable` expressions.

---

## The `applicable` Expression

The `applicable` field uses Symfony's ExpressionLanguage. Available variables:

| Variable | Description |
|---------|-------------|
| `context` | Map of variables passed to `{{ placeholder() }}` |
| `app` | Symfony's `AppVariable` (user, request, session) |

Examples:
```yaml
# Only show for a specific entity type
applicable: 'context["entity"] instanceof Acme\DemoBundle\Entity\Product'

# Only show if entity has a specific property true
applicable: 'context["entity"].isActive() == true'

# Only show in certain conditions
applicable: '!context["readonly"]'

# Always applicable (default if not specified)
# applicable: not set
```

---

## Practical Examples

### Example 1: Add a Widget to an Entity View Page

**Step 1: Find the placeholder slot in the vendor template**

OroCommerce's entity view templates typically call:
```twig
{{ placeholder('view_content_data_after', {entity: entity}) }}
```

**Step 2: Create your template**

```twig
{# src/Acme/DemoBundle/Resources/views/Product/Placeholder/custom_info.html.twig #}
<div class="widget-content">
    <h5>{{ 'acme.demo.product.custom_info.label'|trans }}</h5>
    <p>{{ entity.customData }}</p>
</div>
```

**Step 3: Register in placeholders.yml**

```yaml
placeholders:
    items:
        acme_demo_product_custom_info:
            template: '@AcmeDemo/Product/Placeholder/custom_info.html.twig'
            acl: acme_demo_product_view
            applicable: 'context["entity"] instanceof Acme\DemoBundle\Entity\Product'

    placeholders:
        view_content_data_after:
            items:
                acme_demo_product_custom_info:
                    order: 50
```

---

### Example 2: Add a Controller-Backed Panel

**Step 1: Create the controller action**

```php
// src/Acme/DemoBundle/Controller/PlaceholderController.php
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;

class PlaceholderController extends AbstractController
{
    #[Route('/acme/demo/order-panel/{id}', name: 'acme_demo_order_panel')]
    public function orderPanelAction(int $id): Response
    {
        // complex service calls here
        $data = $this->orderService->getSummary($id);

        return $this->render('@AcmeDemo/Order/Placeholder/panel.html.twig', [
            'data' => $data,
        ]);
    }
}
```

**Step 2: Register in placeholders.yml**

```yaml
placeholders:
    items:
        acme_demo_order_panel:
            action: acme_demo_order_panel    # route name
            acl: acme_demo_order_view

    placeholders:
        order_view_header:
            items:
                acme_demo_order_panel:
                    order: 10
```

---

### Example 3: Add Items to Multiple Slots

```yaml
placeholders:
    items:
        acme_demo_status_badge:
            template: '@AcmeDemo/Common/status_badge.html.twig'
            acl: acme_demo_view

    placeholders:
        # Show on both list and view pages
        product_list_row_after:
            items:
                acme_demo_status_badge:
                    order: 100

        product_view_header_after:
            items:
                acme_demo_status_badge:
                    order: 50
```

---

## Known Vendor Placeholder Slots

These are commonly used slots in OroCommerce. Check vendor templates for current list.

| Slot Name | Location | Context Variables |
|-----------|---------|-------------------|
| `entity_view_after_content` | After entity view body | `entity` |
| `view_content_data_after` | After view content data | `entity` |
| `datagrid_toolbar_before` | Before datagrid toolbar | `gridName` |
| `datagrid_action_before` | Before datagrid row actions | — |
| `login_page_before_form` | Above login form | — |
| `dashboard_before_widgets` | Above dashboard widgets | — |
| `user_profile_data` | User profile view | `entity` |

**Tip:** Search vendor templates to find available slots:
```bash
grep -r "placeholder(" vendor/oro --include="*.twig" -l
```

---

## Merge Behavior

When multiple bundles assign items to the same slot:

```yaml
# Bundle A placeholders.yml
placeholders:
    placeholders:
        product_sidebar:
            items:
                bundle_a_widget:
                    order: 100

# Bundle B placeholders.yml
placeholders:
    placeholders:
        product_sidebar:
            items:
                bundle_b_widget:
                    order: 200

# Result: both items appear; bundle_a_widget first (lower order)
```

---

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Wrong slot name | Nothing appears | Find exact slot name in vendor Twig template |
| `template` path format wrong | Twig exception | Use `@BundleName/path/file.html.twig` notation |
| Both `template` and `action` set | Unpredictable behavior | Use only one |
| `applicable` expression syntax error | Item never renders | Test expression in a Symfony console command |
| ACL ID doesn't exist | Item always hidden | Verify ACL ID in `acls.yml` |
| Missing `items:` declaration | YAML parse / merge error | Declare the item in `items:` before using in `placeholders:` |
| Missing cache clear | Changes not visible | Run `php bin/console cache:clear` |
