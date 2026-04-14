# Page Components

PageComponents are controller-like components attached to DOM elements. They handle specific functionality for parts of a page and are initialized from HTML data attributes.

---

## Summary

- **PageComponent** = Mini-controller for a specific UI feature
- Initialized from DOM via `data-page-component-*` attributes
- Automatically disposed when page changes (memory-safe)
- Can be extended from `BaseComponent` or be a simple function

---

## How It Works

```
┌────────────────────────────────────────────────────────────────┐
│                         HTML Template                           │
│  <div data-page-component-module="mybundle/js/app/components/  │
│       my-component"                                             │
│       data-page-component-options='{"foo": "bar"}'>             │
│      Content...                                                 │
│  </div>                                                         │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                    Page Lifecycle                               │
│  1. PageController loads page                                   │
│  2. page:update event fires                                     │
│  3. PageLayoutView updates DOM                                  │
│  4. initPageComponents() scans for data-attributes              │
│  5. Loads and initializes each component                        │
│  6. Returns promise for all components                          │
│  7. page:afterChange fires when all promises resolve            │
└────────────────────────────────────────────────────────────────┘
```

---

## Definition in Twig Templates

### Basic Definition

```twig
{% set componentOptions = {
    productId: product.id,
    productName: product.name
} %}

<div data-page-component-module="acmedemo/js/app/components/product-component"
     data-page-component-options="{{ componentOptions|json_encode }}">
    <!-- Component content -->
</div>
```

### With Component Name (for access)

```twig
<div data-page-component-module="acmedemo/js/app/components/grid-component"
     data-page-component-name="product-grid"
     data-page-component-options="{{ gridOptions|json_encode }}">
    <!-- Grid content -->
</div>
```

### Lazy Initialization (Performance Optimization)

```twig
{# Initialize only on click #}
<button data-page-component-init-on="click"
        data-page-component-module="acmedemo/js/app/components/popup-component"
        data-page-component-options="{{ popupOptions|json_encode }}">
    Open Popup
</button>

{# Initialize on click OR focus #}
<input data-page-component-init-on="click,focusin"
       data-page-component-module="acmedemo/js/app/components/autocomplete-component" />

{# Initialize on click for container, but ASAP for specific child #}
<form data-page-component-init-on="click,focusin">
    <input data-page-component-module="acmedemo/js/app/components/field-component" />
    <div data-page-component-init-on="asap"
         data-page-component-view="acmedemo/js/app/views/form-view"></div>
</form>
```

### Event Delegation

```twig
{# Delegate init event to parent element #}
<form id="my-form">
    <input data-page-component-init-on="click,focusin #my-form"
           data-page-component-module="acmedemo/js/app/components/field-component" />
</form>
```

---

## Extending BaseComponent

BaseComponent provides:
- `initialize(options)` - Called on creation
- `dispose()` - Called on destruction, cleans up resources
- `delegateListeners()` - Support for `listen` property
- `_deferredInit()` / `_resolveDeferredInit()` - For async initialization

### Basic Component

```javascript
// js/app/components/product-component.js
import BaseComponent from 'oroui/js/app/components/base/component';
import ProductModel from '../models/product-model';
import ProductView from '../views/product-view';

const ProductComponent = BaseComponent.extend({
    /**
     * Property names automatically extracted from options
     */
    optionNames: BaseComponent.prototype.optionNames.concat(['productId']),
    
    productId: null,
    
    /**
     * Initialize the component
     * @param {Object} options - Passed from data-page-component-options
     */
    initialize: function(options) {
        ProductComponent.__super__.initialize.call(this, options);
        
        // Create model with passed options
        this.model = new ProductModel({
            id: this.productId
        });
        
        // Create view bound to the DOM element
        this.view = new ProductView({
            el: options._sourceElement,
            model: this.model
        });
    },
    
    /**
     * Clean up when component is disposed
     */
    dispose: function() {
        if (this.disposed) return;
        
        // Dispose owned objects
        if (this.view) {
            this.view.dispose();
        }
        if (this.model) {
            this.model.dispose();
        }
        
        // Call parent dispose
        ProductComponent.__super__.dispose.call(this);
    }
});

export default ProductComponent;
```

### Async Component (Deferred Initialization)

```javascript
import BaseComponent from 'oroui/js/app/components/base/component';
import loadModules from 'oroui/js/app/services/load-modules';

const AsyncComponent = BaseComponent.extend({
    initialize: function(options) {
        AsyncComponent.__super__.initialize.call(this, options);
        
        // Mark as async - return promise to PageController
        this._deferredInit();
        
        // Load modules dynamically
        loadModules(['./heavy-module', './another-module'], (HeavyModule, AnotherModule) => {
            if (this.disposed) {
                this._resolveDeferredInit();
                return;
            }
            
            // Initialize with loaded modules
            this.heavyModule = new HeavyModule(options);
            this.anotherModule = new AnotherModule(options);
            
            // Signal initialization complete
            this._resolveDeferredInit();
        });
    }
});

export default AsyncComponent;
```

### Component with Sibling Dependencies

```javascript
import BaseComponent from 'oroui/js/app/components/base/component';

const FilterComponent = BaseComponent.extend({
    /**
     * Declare dependencies on sibling components by name
     * These will be automatically injected as properties
     */
    relatedSiblingComponents: {
        grid: 'product-grid',       // this.grid will be set to component named 'product-grid'
        builder: 'filter-builder'   // this.builder will be set to component named 'filter-builder'
    },
    
    initialize: function(options) {
        FilterComponent.__super__.initialize.call(this, options);
        
        // this.grid and this.builder are already set by now
        if (this.grid) {
            this.listenTo(this.grid, 'row:selected', this.onRowSelected);
        }
    },
    
    onRowSelected: function(row) {
        // Handle row selection from grid component
    }
});

export default FilterComponent;
```

---

## Function as Component (Simple Cases)

For trivial cases that don't need disposal or extension:

```javascript
// js/app/components/simple-widget-component.js
import $ from 'jquery';

/**
 * Simple component - just a function
 * @param {Object} options - Component options
 */
export default function(options) {
    // options._sourceElement is the DOM element
    $(options._sourceElement).somePlugin(options.pluginOptions);
    
    // No disposal needed - plugin handles its own cleanup
}
```

---

## ViewComponent (Common Pattern)

ViewComponent creates a view and binds it to the element:

```twig
<div data-page-component-view="acmedemo/js/app/views/product-view"
     data-page-component-options="{{ viewOptions|json_encode }}">
</div>
```

### Equivalent to:

```javascript
import ViewComponent from 'oroui/js/app/components/view-component';

// ViewComponent is built-in and handles:
// 1. Loading the view module
// 2. Creating the view with options
// 3. Binding to _sourceElement
// 4. Disposing the view when component is disposed
```

---

## JqueryWidgetComponent

Wraps jQuery UI widgets as components:

```twig
<div data-page-component-module="oroui/js/app/components/jquery-widget-component"
     data-page-component-options='{
         "widgetModule": "oroui/js/widget/collapse-widget",
         "widgetName": "collapse"
     }'>
    Collapsible content
</div>
```

### Custom jQuery Widget Component

```javascript
// js/app/components/datepicker-component.js
import JqueryWidgetComponent from 'oroui/js/app/components/jquery-widget-component';

const DatepickerComponent = JqueryWidgetComponent.extend({
    initialize: function(options) {
        // Add default options
        options = Object.assign({
            dateFormat: 'yy-mm-dd',
            changeYear: true
        }, options);
        
        DatepickerComponent.__super__.initialize.call(this, options);
    }
});

export default DatepickerComponent;
```

---

## Component Shortcuts

Simplified syntax for common components:

```twig
{# Shortcut for collapse widget #}
<div data-page-component-collapse>
    Collapsible content
</div>

{# Shortcut with options #}
<div data-page-component-collapse='{"storageKey": "my-collapse"}'>
    Collapsible content
</div>

{# Shortcut for jQuery widget #}
<div data-page-component-jquery="oroui/js/widget/collapse-widget">
    Content
</div>
```

### Registering Shortcuts

```javascript
// In an AppModule
import ComponentShortcutsManager from 'oroui/js/component-shortcuts-manager';

// Empty value shortcut
ComponentShortcutsManager.add('collapse', {
    moduleName: 'oroui/js/app/components/jquery-widget-component',
    options: {
        widgetModule: 'oroui/js/widget/collapse-widget'
    }
});

// Scalar value shortcut
ComponentShortcutsManager.add('jquery', {
    moduleName: 'oroui/js/app/components/jquery-widget-component',
    scalarOption: 'widgetModule'
});
```

---

## Built-in Components

| Component | Purpose |
|-----------|---------|
| `view-component` | Creates a view from `view` option |
| `jquery-widget-component` | Wraps jQuery UI widgets |
| `widget-component` | Loads and displays widgets |
| `tabs-component` | Tab management |
| `viewport-component` | Viewport-specific behavior |
| `ajax-button` | Button with AJAX action |
| `post-button` | Button that posts data |
| `hidden-redirect-component` | Redirects via JavaScript |

---

## Accessing Components

### By Name

```javascript
// In another component or view
const gridComponent = layout.get('product-grid');

// Or if you have reference to component manager
componentManager.get('product-grid');
```

### From View

```javascript
const MyView = BaseView.extend({
    initialize: function(options) {
        // Access sibling components
        this.component = options._sourceElement.data('page-component');
    }
});
```

---

## Best Practices

### DO

- ✅ Extend `BaseComponent` for complex components
- ✅ Use function components for simple, self-cleaning cases
- ✅ Always call super in `initialize` and `dispose`
- ✅ Use `_deferredInit()` for async initialization
- ✅ Declare sibling dependencies with `relatedSiblingComponents`
- ✅ Use component shortcuts for frequently used patterns

### DON'T

- ❌ Access DOM directly in components (use views)
- ❌ Forget to dispose owned objects
- ❌ Create circular dependencies between components
- ❌ Use global variables to pass data between components

---

## Common Pitfalls

### Memory Leak - Not Disposing

```javascript
// WRONG - Memory leak
const MyComponent = BaseComponent.extend({
    initialize: function(options) {
        this.interval = setInterval(() => this.poll(), 1000);
    }
    // Missing dispose!
});

// CORRECT
const MyComponent = BaseComponent.extend({
    initialize: function(options) {
        this.interval = setInterval(() => this.poll(), 1000);
    },
    dispose: function() {
        if (this.disposed) return;
        clearInterval(this.interval);
        MyComponent.__super__.dispose.call(this);
    }
});
```

### Using Wrong Element

```javascript
// WRONG - Using wrong element reference
const MyComponent = BaseComponent.extend({
    initialize: function(options) {
        this.$el = $('.my-element'); // Could be wrong element!
    }
});

// CORRECT - Using _sourceElement
const MyComponent = BaseComponent.extend({
    initialize: function(options) {
        this.$el = options._sourceElement; // The element from data-attribute
    }
});
```

---

## Example: Complete Component with View

```javascript
// js/app/components/shopping-list-component.js
import _ from 'underscore';
import BaseComponent from 'oroui/js/app/components/base/component';
import mediator from 'oroui/js/mediator';
import ShoppingListModel from '../models/shopping-list-model';
import ShoppingListView from '../views/shopping-list-view';

const ShoppingListComponent = BaseComponent.extend({
    optionNames: BaseComponent.prototype.optionNames.concat([
        'shoppingListId',
        'items',
        'editable'
    ]),
    
    shoppingListId: null,
    items: [],
    editable: false,
    
    /**
     * Related sibling components
     */
    relatedSiblingComponents: {
        cart: 'shopping-cart'
    },
    
    initialize: function(options) {
        ShoppingListComponent.__super__.initialize.call(this, options);
        
        // Create model
        this.model = new ShoppingListModel({
            id: this.shoppingListId,
            items: this.items
        });
        
        // Create view
        this.view = new ShoppingListView({
            el: options._sourceElement,
            model: this.model,
            editable: this.editable
        });
        
        // Listen to view events
        this.listenTo(this.view, 'item:add', this.onItemAdd);
        this.listenTo(this.view, 'item:remove', this.onItemRemove);
        
        // Listen to cart component
        if (this.cart) {
            this.listenTo(this.cart, 'item:added', this.syncWithCart);
        }
    },
    
    onItemAdd: function(item) {
        this.model.addItem(item);
        mediator.execute('showFlashMessage', 'success', 'Item added');
        this.trigger('item:added', item);
    },
    
    onItemRemove: function(itemId) {
        this.model.removeItem(itemId);
        mediator.execute('showFlashMessage', 'success', 'Item removed');
        this.trigger('item:removed', itemId);
    },
    
    syncWithCart: function(item) {
        // Sync shopping list with cart
        this.model.updateFromCart(item);
    },
    
    dispose: function() {
        if (this.disposed) return;
        
        this.stopListening();
        
        if (this.view) {
            this.view.dispose();
            delete this.view;
        }
        
        if (this.model) {
            this.model.dispose();
            delete this.model;
        }
        
        ShoppingListComponent.__super__.dispose.call(this);
    }
});

export default ShoppingListComponent;
```