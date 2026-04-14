# Best Practices & Constraints

This document covers coding standards, anti-patterns, security considerations, and common pitfalls for OroCommerce frontend development.

---

## Coding Standards

### JavaScript

#### File Naming
- **Lowercase** with **hyphens**: `product-gallery-component.js`
- **Suffix indicates type**: `-component.js`, `-view.js`, `-model.js`

#### Code Style
- **Indentation**: 4 spaces (no tabs)
- **Max line length**: 120 characters
- **Quotes**: Single quotes for strings, double for JSX/HTML
- **Semicolons**: Required
- **Trailing commas**: Required for multiline

```javascript
// Good
const ProductGalleryComponent = BaseComponent.extend({
    optionNames: ['productId', 'productName', 'imageUrls'],
    
    initialize: function(options) {
        ProductGalleryComponent.__super__.initialize.call(this, options);
        
        this.view = new ProductGalleryView({
            el: options._sourceElement,
            model: this.model,
            images: this.imageUrls,
        });
    },
});

// Bad
const ProductGalleryComponent = BaseComponent.extend({
  optionNames: ['productId','productName','imageUrls'],
  initialize(options) {
    // Missing super call
    this.view = new ProductGalleryView({el:options._sourceElement,model:this.model})
  }
})
```

### CSS/SCSS

#### Selector Naming
- **Lowercase** with **hyphens**
- **BEM pattern**: `block__element--modifier`

```scss
// Good
.product-card { }
.product-card__image { }
.product-card__name--highlighted { }

// Bad
.ProductCard { }
.productCard { }
.product_card { }
```

#### Property Order
1. Variables
2. Positioning
3. Box model
4. Typography
5. Visual
6. Other
7. Mixins

```scss
.element {
    // Variables
    $color: get-color('text', 'primary');
    
    // Positioning
    position: absolute;
    top: 0;
    z-index: z('popup');
    
    // Box model
    width: 100px;
    padding: spacing('base');
    
    // Typography
    font-size: $font-size-base;
    line-height: 1.5;
    
    // Visual
    background: get-color('neutral', 'white');
    border: 1px solid $color;
    
    // Other
    cursor: pointer;
    
    // Mixins (last)
    @include ellipsis;
}
```

---

## Anti-Patterns

### JavaScript

#### ❌ Type Suppression

```javascript
// WRONG
const value = data as any;
// @ts-ignore
const result = riskyOperation();

// CORRECT - Proper type handling
interface Data {
    value?: string;
}

const value = (data as Data).value ?? 'default';
```

#### ❌ Empty Catch Blocks

```javascript
// WRONG
try {
    doSomething();
} catch (e) {}

// CORRECT
try {
    doSomething();
} catch (e) {
    errorHandler.showError(e);
}
```

#### ❌ Console.log in Production

```javascript
// WRONG
console.log('Debug info:', data);

// CORRECT - Use proper logging
import logger from 'oroui/js/tools/logger';
logger.debug('Debug info:', data);

// Or remove entirely for production
```

#### ❌ Global Variables

```javascript
// WRONG
window.myGlobalData = data;

// CORRECT - Use mediator or registry
import mediator from 'oroui/js/mediator';
mediator.setHandler('getMyData', () => data);
```

#### ❌ DOM Manipulation Outside Views

```javascript
// WRONG - Component manipulating DOM
const MyComponent = BaseComponent.extend({
    initialize: function(options) {
        $('.my-element').addClass('active');
    },
});

// CORRECT - View handles DOM
const MyView = BaseView.extend({
    events: {
        'click .my-element': 'onElementClick',
    },
    
    onElementClick: function(e) {
        $(e.currentTarget).addClass('active');
    },
});
```

#### ❌ Missing Disposal

```javascript
// WRONG - Memory leak
const MyComponent = BaseComponent.extend({
    initialize: function(options) {
        this.interval = setInterval(this.poll, 1000);
        this.listener = mediator.on('event', this.handler);
    },
    // Missing dispose!
});

// CORRECT
const MyComponent = BaseComponent.extend({
    initialize: function(options) {
        this.interval = setInterval(this.poll, 1000);
        this.listenTo(mediator, 'event', this.handler);
    },
    
    dispose: function() {
        if (this.disposed) return;
        clearInterval(this.interval);
        MyComponent.__super__.dispose.call(this);
    },
});
```

### CSS/SCSS

#### ❌ Hardcoded Values

```scss
// WRONG
.element {
    padding: 15px;
    color: #333333;
    margin-bottom: 20px;
}

// CORRECT
.element {
    padding: spacing('base');
    color: get-color('text', 'primary');
    margin-bottom: spacing('lg');
}
```

#### ❌ Deep Nesting

```scss
// WRONG
.container {
    .row {
        .col {
            .card {
                .header {
                    .title {  // 5 levels deep!
                        color: red;
                    }
                }
            }
        }
    }
}

// CORRECT
.card__title {
    color: get-color('text', 'danger');
}
```

#### ❌ !important Abuse

```scss
// WRONG
.element {
    color: red !important;
}

// CORRECT - Fix specificity
.container .element {
    color: get-color('text', 'danger');
}
```

#### ❌ Inline Media Queries

```scss
// WRONG
.element {
    width: 50%;
    
    @media (max-width: 768px) {
        width: 100%;
    }
    
    padding: spacing('base');
}

// CORRECT
.element {
    width: 50%;
    padding: spacing('base');
}

@include breakpoint('tablet') {
    .element {
        width: 100%;
    }
}
```

---

## Security Guidelines

### XSS Prevention

#### Twig Auto-Escaping

```twig
{# SAFE - Auto-escaped #}
<p>{{ userInput }}</p>

{# DANGEROUS - Not escaped #}
<p>{{ userInput|raw }}</p>

{# ONLY use |raw when necessary and content is trusted #}
<p>{{ trustedContent|raw }}</p>
```

#### JavaScript Data Injection

```twig
{# WRONG - XSS vulnerability #}
<script>
    var productId = {{ product.id }};
    var productName = '{{ product.name }}';
</script>

{# CORRECT - Proper encoding #}
<div data-product-id="{{ product.id }}"
     data-product-name="{{ product.name|e('html_attr') }}">
</div>

{# Or use json_encode #}
<script>
    var productData = {{ product|json_encode|raw }};
</script>
```

### Input Validation

#### JavaScript

```javascript
// WRONG - No validation
function processUserInput(input) {
    return input.toUpperCase();
}

// CORRECT - Validate input
function processUserInput(input) {
    if (typeof input !== 'string') {
        throw new Error('Input must be a string');
    }
    return input.toUpperCase();
}
```

### CSRF Protection

Forms automatically include CSRF tokens. For AJAX requests:

```javascript
// Include CSRF token in requests
$.ajax({
    url: '/api/endpoint',
    method: 'POST',
    headers: {
        'X-CSRF-Token': $('meta[name="csrf-token"]').attr('content'),
    },
});
```

---

## Performance Guidelines

### JavaScript

#### Lazy Component Initialization

```twig
{# Initialize heavy components only when needed #}
<div data-page-component-init-on="click"
     data-page-component-module="mybundle/js/app/components/heavy-component">
    Click to load
</div>
```

#### Dynamic Imports

```yaml
# jsmodules.yml
dynamic-imports:
    heavy-charts:
        - mybundle/js/app/components/chart-component
```

```javascript
import loadModules from 'oroui/js/app/services/load-modules';

// Load on demand
loadModules('mybundle/js/app/components/chart-component').then(ChartComponent => {
    // Component loaded
});
```

### CSS

#### Avoid Deep Selectors

```scss
// BAD - Slow rendering
.container .row .col .card .header .title { }

// GOOD - Flat selector
.card__title { }
```

#### Minimize Repaints

```scss
// Use transform instead of position changes
.element {
    transform: translateX(0);
    
    &:hover {
        transform: translateX(10px);
    }
}
```

---

## Common Pitfalls

### JavaScript

#### Forgetting Super Call

```javascript
// WRONG
const MyComponent = BaseComponent.extend({
    initialize: function(options) {
        this.myInit(options);
        // Forgot super call!
    },
});

// CORRECT
const MyComponent = BaseComponent.extend({
    initialize: function(options) {
        MyComponent.__super__.initialize.call(this, options);
        this.myInit(options);
    },
});
```

#### Using Wrong jQuery

```javascript
// WRONG - Missing Oro extensions
import $ from 'jquery/dist/jquery';

// CORRECT - Uses Oro's extended jQuery
import $ from 'jquery';
```

#### Wrong Element Reference

```javascript
// WRONG - Could be wrong element
this.$el = $('.my-element');

// CORRECT - The element from data-attribute
this.$el = options._sourceElement;
```

### CSS

#### Wrong Variable Order

```yaml
# WRONG - Variable used before defined
css:
    inputs:
        - 'bundles/mybundle/scss/main.scss'  # Uses $color
        - 'bundles/mybundle/scss/variables.scss'  # Defines $color
```

#### Not Using Theme Functions

```scss
// WRONG - Not themeable
.element {
    color: #333;
}

// CORRECT - Themeable
.element {
    color: get-color('text', 'primary');
}
```

---

## Version-Specific Guidelines

### Oro 6.x (Current LTS)

- ES6 modules recommended for new code
- AMD/CommonJS still supported but discouraged
- jQuery Deferred still works but prefer native Promises

### Oro 7.0 (Upcoming - 2026)

- **ES Modules required** - AMD/CommonJS deprecated
- **Native Promises required** - jQuery Deferred deprecated
- See `migration-guide.md` for detailed migration patterns

---

## Checklist

Before committing frontend code:

### JavaScript
- [ ] ES6 modules for new code
- [ ] Proper disposal in components
- [ ] No `console.log` statements
- [ ] No type suppression (`as any`, `@ts-ignore`)
- [ ] Proper error handling
- [ ] Super calls in initialize/dispose

### CSS/SCSS
- [ ] BEM naming convention
- [ ] Max 2 levels nesting
- [ ] Media queries at file end
- [ ] Using Oro functions (`spacing()`, `get-color()`)
- [ ] No hardcoded values
- [ ] No `!important` without justification

### Templates
- [ ] Proper block naming (`_block_id_widget`)
- [ ] `block('block_attributes')` for attributes
- [ ] No complex logic in templates
- [ ] Proper escaping for user input
- [ ] Using `path()` for URLs

### General
- [ ] 4-space indentation
- [ ] Max 120 char line length
- [ ] Single quotes for strings
- [ ] Trailing commas in multiline
- [ ] Comments in English