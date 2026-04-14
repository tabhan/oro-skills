# CSS/SCSS Architecture

OroCommerce uses SCSS with a structured three-folder system (components, settings, variables) for maintainable styling. Themes can inherit from parent themes and override specific values.

---

## Summary

- **SCSS** is the CSS preprocessor (not plain CSS)
- **Three-folder structure**: `components/`, `settings/`, `variables/`
- **Theme inheritance**: Child themes override parent variables
- **Build system**: Webpack compiles all inputs into single CSS file
- **RTL support**: Automatic RTL generation for specified files

---

## File Structure

### Bundle-Level Structure

```
BundleName/Resources/public/{theme-name}/scss/
├── components/               # Component-specific styles
│   ├── button.scss
│   ├── input.scss
│   ├── modal.scss
│   └── table.scss
├── settings/                 # Global settings, mixins, functions
│   ├── global-settings.scss
│   └── mixins/
│       ├── _clearfix.scss
│       └── _breakpoints.scss
├── variables/                # Configuration variables
│   ├── button-config.scss
│   ├── input-config.scss
│   └── modal-config.scss
└── styles.scss              # Main entry point (optional)
```

### Theme Structure

```
application/
└── public/
    └── build/
        └── {theme-name}/
            └── css/
                ├── styles.css        # Main compiled CSS
                ├── critical.css      # Critical CSS for fast render
                └── styles-print.css  # Print styles
```

---

## Configuration (assets.yml)

### Basic Configuration

```yaml
# BundleName/Resources/views/layouts/{theme}/config/assets.yml
css:
    inputs:
        # 1. Settings (load first)
        - 'bundles/mybundle/default/scss/settings/global-settings.scss'
        
        # 2. Variables
        - 'bundles/mybundle/default/scss/variables/button-config.scss'
        - 'bundles/mybundle/default/scss/variables/input-config.scss'
        
        # 3. Components
        - 'bundles/mybundle/default/scss/components/button.scss'
        - 'bundles/mybundle/default/scss/components/input.scss'
        
        # 4. External npm modules (prefix with ~)
        - '~prismjs/themes/prism-coy.css'
    
    # Output file
    output: 'css/styles.css'
    
    # Files to process for RTL
    auto_rtl_inputs:
        - 'bundles/oro*/**'
```

### Loading Order

**Critical**: Files are loaded in order. Variables must come before components that use them.

```yaml
css:
    inputs:
        # ORDER MATTERS:
        # 1. Settings (mixins, functions available everywhere)
        - 'bundles/oroui/default/scss/settings/global-settings.scss'
        
        # 2. Variables (can use settings)
        - 'bundles/oroui/default/scss/variables/variables.scss'
        
        # 3. Component styles (use variables and settings)
        - 'bundles/oroui/default/scss/main.scss'
```

---

## SCSS Functions

### get-color()

Get colors from the color palette:

```scss
.element {
    color: get-color('text', 'primary');           // #333
    background: get-color('neutral', 'grey2');     // #f5f5f5
    border-color: get-color('primary', 'main');    // #0064cd
}
```

### get-var-color()

Get CSS variable-based colors (for theming):

```scss
.element {
    color: get-var-color('text', 'primary');
    background: get-var-color('neutral', 'grey2');
}
```

### spacing()

Get spacing values based on multipliers:

```scss
.element {
    padding: spacing('sm');      // Small padding
    margin: spacing('base');     // Base spacing
    gap: spacing('md');          // Medium gap
}
```

**Available sizes**: `xs`, `sm`, `base`, `md`, `lg`, `xl`, `xxl`

### z()

Manage z-index values centrally:

```scss
.modal {
    z-index: z('popup');              // Standard popup z-index
}

.modal-overlay {
    z-index: z('popup') - 1;          // Below popup
}

.dropdown {
    z-index: z('dropdown');           // Standard dropdown z-index
}
```

### breakpoint()

Responsive media queries:

```scss
.container {
    width: 100%;
    
    @include breakpoint('tablet') {
        width: 75%;
    }
    
    @include breakpoint('desktop') {
        width: 50%;
    }
}
```

---

## SCSS Mixins

### Common Mixins

```scss
// Clearfix
.container {
    @include clearfix;
}

// Ellipsis text
.text-truncate {
    @include ellipsis;
}

// Visually hidden (accessible)
.skip-link {
    @include visually-hidden;
    
    &:focus {
        @include visually-hidden-reset;
    }
}

// Pseudo-elements
.element {
    @include before {
        content: '';
        display: block;
    }
    
    @include after {
        content: '';
        clear: both;
    }
}

// Fixed positioning
.overlay {
    @include fixed-cover;
}
```

---

## Variable Configuration

### Defining Variables

```scss
// variables/button-config.scss

// Use !default to allow overrides
$button-padding: spacing('sm') spacing('base') !default;
$button-font-size: $base-font-size !default;
$button-border-radius: 4px !default;
$button-color: get-color('primary', 'main') !default;
$button-bg: get-color('neutral', 'white') !default;

// Hover state
$button-hover-color: get-color('primary', 'active') !default;
$button-hover-bg: get-color('primary', 'light') !default;
```

### Overriding Variables

In a child theme:

```scss
// child-theme/scss/variables/button-config.scss
$button-padding: spacing('md') spacing('lg');  // Larger padding
$button-border-radius: 8px;                    // More rounded
```

---

## Component Styles

### BEM Naming Convention

```scss
// components/button.scss

// Block
.button {
    display: inline-block;
    padding: $button-padding;
    font-size: $button-font-size;
    border-radius: $button-border-radius;
    color: $button-color;
    background: $button-bg;
    cursor: pointer;
    
    // Element
    &__icon {
        margin-right: spacing('xs');
    }
    
    &__text {
        vertical-align: middle;
    }
    
    // Modifier
    &--primary {
        color: get-color('neutral', 'white');
        background: get-color('primary', 'main');
        
        &:hover {
            background: get-color('primary', 'active');
        }
    }
    
    &--secondary {
        color: get-color('primary', 'main');
        background: transparent;
        border: 1px solid get-color('primary', 'main');
    }
    
    &--large {
        padding: spacing('base') spacing('lg');
        font-size: $font-size-lg;
    }
    
    &--disabled,
    &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
}
```

### Nesting Depth Limit

**Maximum 2 levels of nesting**:

```scss
// GOOD - 2 levels
.block {
    &__element { }
    &--modifier { }
}

// BAD - Too deep
.block {
    &__element {
        &__nested {      // Too deep!
            &__deeper {  // Way too deep!
            }
        }
    }
}
```

---

## Media Queries

### At File End

Place media queries at the end of the file, not inline:

```scss
// GOOD
.element {
    width: 50%;
    padding: spacing('base');
}

.element__item {
    margin-bottom: spacing('sm');
}

// Media queries at the end
@include breakpoint('tablet') {
    .element {
        width: 75%;
    }
}

@include breakpoint('mobile') {
    .element {
        width: 100%;
        padding: spacing('sm');
    }
    
    .element__item {
        margin-bottom: 0;
    }
}
```

---

## Theme Inheritance

### Parent Theme Configuration

```yaml
# parent-theme/theme.yml
name: Parent Theme
```

### Child Theme Configuration

```yaml
# child-theme/theme.yml
name: Child Theme
parent: default  # Inherit from parent
```

### Inherited Assets

Child theme automatically inherits:
- All SCSS variables
- All mixins and functions
- All component styles

### Override Mechanism

```yaml
# child-theme/config/assets.yml
css:
    inputs:
        # Override parent variables (loaded before parent components)
        - 'bundles/childtheme/scss/variables/button-config.scss'
        
        # Override parent styles
        - 'bundles/oroui/default/scss/styles.scss': 'bundles/childtheme/scss/styles.scss'
        
        # Remove parent file entirely
        - 'bundles/oroui/default/scss/old-component.scss': ~
```

---

## RTL Support

### Automatic RTL Processing

Files matching `auto_rtl_inputs` patterns are automatically processed:

```yaml
css:
    auto_rtl_inputs:
        - 'bundles/oro*/**'
```

### RTL-Safe CSS

Write CSS that works for both LTR and RTL:

```scss
// Use logical properties
.element {
    margin-inline-start: spacing('sm');  // Works for both
    padding-inline-end: spacing('base'); // Works for both
}

// Or use mixins
.element {
    @include margin-left(spacing('sm'));
    @include padding-right(spacing('base'));
}
```

---

## Best Practices

### DO

- ✅ Use `!default` for configurable variables
- ✅ Follow BEM naming (`block__element--modifier`)
- ✅ Keep nesting to 2 levels maximum
- ✅ Place media queries at file end
- ✅ Use Oro functions: `spacing()`, `get-color()`, `z()`
- ✅ Use logical properties for RTL support

### DON'T

- ❌ Hardcode colors (use `get-color()`)
- ❌ Use magic numbers for spacing (use `spacing()`)
- ❌ Deep nesting (>2 levels)
- ❌ Inline media queries
- ❌ Use `!important` (avoid)
- ❌ Mix LTR-specific properties

---

## Common Pitfalls

### Wrong Loading Order

```yaml
# WRONG - Variables used before defined
css:
    inputs:
        - 'bundles/mybundle/scss/components/button.scss'    # Uses $button-color
        - 'bundles/mybundle/scss/variables/button-config.scss'  # Defines $button-color

# CORRECT
css:
    inputs:
        - 'bundles/mybundle/scss/variables/button-config.scss'
        - 'bundles/mybundle/scss/components/button.scss'
```

### Hardcoded Values

```scss
// WRONG - Not themeable
.element {
    padding: 15px;
    color: #333;
    margin-bottom: 20px;
}

// CORRECT - Themeable
.element {
    padding: spacing('base');
    color: get-color('text', 'primary');
    margin-bottom: spacing('lg');
}
```

---

## Example: Complete Component

```scss
// variables/product-card-config.scss
$product-card-padding: spacing('base') !default;
$product-card-border-radius: 4px !default;
$product-card-border: 1px solid get-color('neutral', 'grey2') !default;
$product-card-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !default;
$product-card-bg: get-color('neutral', 'white') !default;

// components/product-card.scss
.product-card {
    padding: $product-card-padding;
    border-radius: $product-card-border-radius;
    border: $product-card-border;
    box-shadow: $product-card-shadow;
    background: $product-card-bg;
    transition: box-shadow 0.2s ease;
    
    &:hover {
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
    }
    
    &__image {
        width: 100%;
        aspect-ratio: 1;
        object-fit: cover;
        margin-bottom: spacing('sm');
    }
    
    &__name {
        font-size: $font-size-lg;
        font-weight: $font-weight-semibold;
        color: get-color('text', 'primary');
        margin-bottom: spacing('xs');
    }
    
    &__price {
        font-size: $font-size-xl;
        font-weight: $font-weight-bold;
        color: get-color('primary', 'main');
    }
    
    &__price--sale {
        color: get-color('destructive', 'main');
    }
    
    &--featured {
        border-color: get-color('primary', 'main');
    }
}

// Media queries at end
@include breakpoint('tablet') {
    .product-card {
        padding: spacing('sm');
    }
    
    .product-card__name {
        font-size: $font-size-base;
    }
}

@include breakpoint('mobile') {
    .product-card {
        padding: spacing('xs');
    }
}
```