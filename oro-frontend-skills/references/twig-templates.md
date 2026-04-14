# Twig Templates

Twig templates render the layout blocks in OroCommerce. Each layout block is rendered by a Twig block, and blocks are organized into block theme files.

---

## Summary

- **Twig** is the server-side templating engine
- **Layout blocks** are rendered with Twig blocks
- **Block themes** are Twig files containing block definitions
- **Layout YAML** defines the block structure
- **Data attributes** connect HTML to JavaScript components

---

## Twig Block Names

### Resolution Order

When rendering a layout block, Oro searches for Twig blocks in this order:

1. **Block ID**: `{% block _<block_id>_widget %}`
2. **Block type**: `{% block <block_type>_widget %}`
3. **Parent block type**: `{% block <parent_type>_widget %}`

### Naming Rules

- Always ends with `_widget` suffix
- Block ID blocks start with underscore: `_header_widget`
- Block type blocks have no underscore: `container_widget`

```twig
{# For block with id="header" and blockType="container" #}

{# 1. First choice - block ID #}
{% block _header_widget %}
    <header>{{ block_widget(block) }}</header>
{% endblock %}

{# 2. Second choice - block type #}
{% block container_widget %}
    <div>{{ block_widget(block) }}</div>
{% endblock %}
```

---

## Block Themes

### Definition

Block themes are Twig files containing block definitions:

```twig
{# @AcmeDemo/layouts/default/product/product-view.html.twig #}

{% block _product_name_widget %}
    <h1 class="product__name">{{ text|trans }}</h1>
{% endblock %}

{% block _product_price_widget %}
    <div class="product__price">{{ value|oro_format_currency }}</div>
{% endblock %}

{% block _product_gallery_widget %}
    <div{{ block('block_attributes') }}>
        {{ block_widget(block) }}
    </div>
{% endblock %}
```

### Applying Block Themes

In layout YAML:

```yaml
# layouts/default/product/view/layout.yml
layout:
    actions:
        - '@setBlockTheme':
            themes: 'product-view.html.twig'

        # Multiple themes
        - '@setBlockTheme':
            themes: ['product-view.html.twig', 'product-gallery.html.twig']

        # From another bundle
        - '@setBlockTheme':
            themes: '@AcmeDemo/layouts/default/base.html.twig'
```

---

## Passing Variables to Blocks

### Block Type Options

Defined by the block type:

```yaml
layout:
    actions:
        - '@add':
            id: product_name
            blockType: text
            options:
                text: 'oro.product.name'
                escape: false
```

```twig
{% block _product_name_widget %}
    <h1>{{ text|trans }}</h1>
{% endblock %}
```

### HTML Attributes

```yaml
layout:
    actions:
        - '@add':
            id: product_button
            blockType: button
            options:
                text: 'Add to Cart'
                attr:
                    class: btn btn-primary
                    id: add-to-cart-btn
                    data-product-id: '=data["product"].getId()'
```

```twig
{% block _product_button_widget %}
    <button {{ block('block_attributes') }}>{{ text|trans }}</button>
{% endblock %}
```

### Custom Variables

Use `vars` for custom data:

```yaml
layout:
    actions:
        - '@add':
            id: product_header
            blockType: container
            options:
                vars:
                    productName: '=data["product"].getName()'
                    productSku: '=data["product"].getSku()'
                    isFeatured: '=data["product"].isFeatured()'
```

```twig
{% block _product_header_widget %}
    <div {{ block('block_attributes') }}>
        <h1>{{ productName }}</h1>
        <span class="sku">SKU: {{ productSku }}</span>
        {% if isFeatured %}
            <span class="badge">Featured</span>
        {% endif %}
        {{ block_widget(block) }}
    </div>
{% endblock %}
```

---

## Twig Functions

### block_widget()

Render child blocks:

```twig
{% block _container_widget %}
    <div class="container">
        {{ block_widget(block) }}
    </div>
{% endblock %}
```

### block_attributes()

Render HTML attributes:

```twig
{% block _element_widget %}
    <div {{ block('block_attributes') }}>
        Content
    </div>
{% endblock %}
```

### layout_attr_defaults()

Provide default attributes:

```twig
{% set attr = layout_attr_defaults(attr, {
    class: 'input',
    required: true,
    '~class': ' input--large'
}) %}

<input {{ block('block_attributes') }} />
```

The `~` prefix concatenates values.

### merge_context()

Merge context for iterations:

```twig
{% block _items_container_widget %}
    <ul class="items">
        {% for item in items %}
            {% do block|merge_context({'item': item}) %}
            {{ block('item_widget') }}
        {% endfor %}
    </ul>
{% endblock %}
```

### Accessing Layout Blocks

```twig
{% block root_widget %}
    {% if blocks.sidebar is defined and blocks.sidebar.children|length > 0 %}
        {% set attr = attr|merge({'class': 'has-sidebar'}) %}
    {% endif %}
    <html {{ block('block_attributes') }}>
        {{ block_widget(block) }}
    </html>
{% endblock %}
```

---

## Data Providers

### Layout Context (Shared Data)

```yaml
options:
    text: '=context["is_mobile"]'
```

### Data Providers (Page-Specific)

```yaml
options:
    url: '=data["back_to_url"]'
    product: '=data["product"]'
```

### Custom Data Providers

```php
// src/DataProvider/ProductDataProvider.php
namespace App\DataProvider;

class ProductDataProvider
{
    public function getName($product)
    {
        return $product->getName();
    }
    
    public function getFormattedPrice($product)
    {
        return '$' . number_format($product->getPrice(), 2);
    }
}
```

```yaml
# services.yml
services:
    App\DataProvider\ProductDataProvider:
        tags:
            - { name: layout.data_provider, alias: product }
```

```yaml
# layout.yml
options:
    name: '=data["product"].getName()'
    price: '=data["product"].getFormattedPrice()'
```

---

## JavaScript Component Integration

### data-page-component-module

```twig
<div data-page-component-module="mybundle/js/app/components/product-component"
     data-page-component-options="{{ componentOptions|json_encode }}">
    <!-- Content managed by component -->
</div>
```

### data-page-component-view

```twig
<div data-page-component-view="mybundle/js/app/views/product-view"
     data-page-component-options="{{ viewOptions|json_encode }}">
    <!-- View will be bound here -->
</div>
```

### Complex Options

```twig
{% set options = {
    productId: product.id,
    productName: product.name,
    urls: {
        add: path('product_add', {id: product.id}),
        remove: path('product_remove', {id: product.id})
    },
    settings: {
        allowEdit: is_granted('EDIT', product),
        maxQuantity: 99
    }
} %}

<div data-page-component-module="mybundle/js/app/components/product-component"
     data-page-component-options="{{ options|json_encode }}">
</div>
```

---

## Form Themes

Forms use separate theme system:

```yaml
layout:
    actions:
        - '@setFormTheme':
            themes: ['@AcmeDemo/Form/fields.html.twig']
```

```twig
{# @AcmeDemo/Form/fields.html.twig #}

{% block product_image_widget %}
    <div class="product-image-upload">
        {{ block('file_widget') }}
        {% if image_url is defined %}
            <img src="{{ image_url }}" alt="Preview" />
        {% endif %}
    </div>
{% endblock %}
```

---

## Debugging

### Dump Variables

```twig
{# Dump all variables #}
{{ dump(_context) }}

{# Dump to Symfony Profiler #}
{% dump(_context) %}

{# Dump single variable #}
{{ dump(productName) }}
```

### Find Template Location

Use [Twig Inspector](https://github.com/oroinc/twig-inspector) to navigate from browser to template.

---

## Template Overrides

### Back-Office Override

```
templates/bundles/OroDataGridBundle/Grid/widget/widget.html.twig
```

### Storefront Override

Create layout update with new block theme:

```yaml
# layouts/custom/layout.yml
layout:
    actions:
        - '@setBlockTheme':
            themes: 'theme-overrides.html.twig'
```

```twig
{# layouts/custom/theme-overrides.html.twig #}

{# Override specific block #}
{% block _product_name_widget %}
    <h1 class="product__name custom-class">{{ text|trans }}</h1>
{% endblock %}
```

---

## Best Practices

### DO

- ✅ Use `block('block_attributes')` for HTML attributes
- ✅ Use `vars` for custom variables
- ✅ Follow naming convention (`_block_id_widget`)
- ✅ Use data providers for complex logic
- ✅ Keep Twig blocks simple (logic in PHP)

### DON'T

- ❌ Put complex logic in templates
- ❌ Override block types when block ID works
- ❌ Hardcode URLs (use `path()`)
- ❌ Skip escaping for user input
- ❌ Mix layout structure with content

---

## Common Pitfalls

### Missing block_widget()

```twig
{# WRONG - Children not rendered #}
{% block _container_widget %}
    <div class="container"></div>
{% endblock %}

{# CORRECT - Children rendered #}
{% block _container_widget %}
    <div class="container">
        {{ block_widget(block) }}
    </div>
{% endblock %}
```

### Wrong Block Name

```twig
{# WRONG - Missing underscore for block ID #}
{% block header_widget %}
    <header>{{ block_widget(block) }}</header>
{% endblock %}

{# CORRECT - Block ID starts with underscore #}
{% block _header_widget %}
    <header>{{ block_widget(block) }}</header>
{% endblock %}
```

---

## Example: Complete Product View

```twig
{# layouts/default/product/view.html.twig #}

{# Product gallery #}
{% block _product_gallery_widget %}
    <div class="product-gallery" {{ block('block_attributes') }}>
        {% if images|length > 0 %}
            <div class="product-gallery__main">
                <img src="{{ images[0].url }}" alt="{{ images[0].alt }}" />
            </div>
            {% if images|length > 1 %}
                <div class="product-gallery__thumbnails">
                    {% for image in images %}
                        <img src="{{ image.thumbnail }}" alt="{{ image.alt }}" />
                    {% endfor %}
                </div>
            {% endif %}
        {% else %}
            <div class="product-gallery__placeholder">
                {{ 'oro.product.no_image'|trans }}
            </div>
        {% endif %}
    </div>
{% endblock %}

{# Product info #}
{% block _product_info_widget %}
    <div class="product-info" {{ block('block_attributes') }}>
        <h1 class="product-info__name">{{ productName }}</h1>
        
        <div class="product-info__sku">
            {{ 'oro.product.sku'|trans }}: {{ productSku }}
        </div>
        
        {% if isFeatured %}
            <span class="product-info__badge">{{ 'oro.product.featured'|trans }}</span>
        {% endif %}
        
        <div class="product-info__price">
            {% if hasDiscount %}
                <span class="product-info__price--original">{{ originalPrice|oro_format_currency }}</span>
                <span class="product-info__price--sale">{{ salePrice|oro_format_currency }}</span>
            {% else %}
                {{ price|oro_format_currency }}
            {% endif %}
        </div>
        
        {{ block_widget(block) }}
    </div>
{% endblock %}

{# Add to cart button #}
{% block _product_add_to_cart_widget %}
    {% set attr = layout_attr_defaults(attr, {
        'class': 'btn btn--primary btn--large',
        'data-product-id': productId
    }) %}
    
    <button {{ block('block_attributes') }} data-page-component-module="mybundle/js/app/components/add-to-cart-component">
        {{ 'oro.product.add_to_cart'|trans }}
    </button>
{% endblock %}

{# Product description #}
{% block _product_description_widget %}
    <div class="product-description" {{ block('block_attributes') }}>
        <h2 class="product-description__title">{{ 'oro.product.description'|trans }}</h2>
        <div class="product-description__content">
            {{ description|raw }}
        </div>
    </div>
{% endblock %}
```