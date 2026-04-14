# JavaScript Architecture

OroCommerce client-side architecture is built on **Chaplin** (extended **Backbone.js**). The architecture supports distributed functionality across multiple bundles with a page-level controller (PageController) and feature-specific controllers (PageComponents).

---

## Summary

The JavaScript architecture enables:
- **Modular code organization** across bundles
- **Component-based page composition** with PageComponents
- **Application-level initialization** with AppModules
- **Event-driven communication** via mediator
- **Memory-safe lifecycle management** with dispose patterns

---

## Technology Stack

| Library | Role | Module ID |
|---------|------|-----------|
| jQuery | DOM manipulation, AJAX | `jquery` |
| Backbone.js | Models, Collections, Views | `backbone` |
| Chaplin | Application structure, Mediator | `chaplin` |
| Underscore.js | Utilities, templates | `underscore` |
| Bootstrap | UI components | `bootstrap` |

**Note:** Oro extends these libraries with custom behavior. Always import from Oro's paths (e.g., `oroui/js/extend/jquery`) to get the extended versions.

---

## Application Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Instance                       │
│  (oroui/js/app - singleton, exists throughout navigation)    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │   Router    │───▶│ Dispatcher │───▶│ PageController  │  │
│  └─────────────┘    └─────────────┘    └────────┬────────┘  │
│                                                   │           │
│                     ┌─────────────────────────────┘           │
│                     ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐│
│  │                    Page Lifecycle Events                  ││
│  │  page:beforeChange → page:request → page:update →        ││
│  │                                    page:afterChange       ││
│  └──────────────────────────────────────────────────────────┘│
│                     │                                         │
│                     ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐│
│  │              PageComponents (created per page)            ││
│  │  - Initialized from DOM data-attributes                   ││
│  │  - Disposed on page navigation                            ││
│  └──────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Page Lifecycle Events

1. **page:beforeChange** - Before navigation starts
2. **page:request** - When page content is requested
3. **page:update** - When new content is received, before DOM update
4. **page:afterChange** - After all components are initialized

---

## Naming Conventions

### File Naming

```
js/app/
├── components/
│   ├── grid-component.js      # PageComponent: *-component.js
│   └── dropdown-component.js
├── controllers/
│   └── page-controller.js     # Controller: *-controller.js
├── models/
│   ├── user-model.js          # Model: *-model.js
│   └── users-collection.js    # Collection: *-collection.js
├── modules/
│   └── messenger-module.js    # AppModule: *-module.js
└── views/
    ├── user-item-view.js      # View: *-view.js
    └── users-list-view.js
```

### Rules

- **Lowercase letters** with hyphen separators (`my-component.js`)
- **Suffix matches type**: `-component.js`, `-view.js`, `-model.js`, `-module.js`
- **Folder grouping**: Group by functionality within each folder

---

## ES6 Module Pattern (Recommended)

Oro 6.0+ uses ES6 modules. Always prefer ES6 over AMD/CommonJS.

### Basic Module Export

```javascript
// src/Acme/Bundle/DemoBundle/Resources/public/js/app/views/product-view.js
import BaseView from 'oroui/js/app/views/base/view';
import _ from 'underscore';

const ProductView = BaseView.extend({
    optionNames: BaseView.prototype.optionNames.concat(['productId', 'productName']),
    
    productId: null,
    productName: null,
    
    events: {
        'click .product-link': 'onProductClick'
    },
    
    initialize: function(options) {
        ProductView.__super__.initialize.call(this, options);
        this.render();
    },
    
    onProductClick: function(e) {
        e.preventDefault();
        this.trigger('product:selected', this.productId);
    }
});

export default ProductView;
```

### Module Import Paths

```javascript
// Core Oro modules - use short aliases
import $ from 'jquery';
import _ from 'underscore';
import Backbone from 'backbone';
import mediator from 'oroui/js/mediator';
import BaseView from 'oroui/js/app/views/base/view';
import BaseComponent from 'oroui/js/app/components/base/component';

// Bundle-specific modules - use full path
import ProductModel from 'acmedemo/js/app/models/product-model';
import ProductView from 'acmedemo/js/app/views/product-view';
```

---

## Legacy AMD Pattern (Avoid)

AMD is deprecated but still present in older code. **Do not use for new code.**

> **Note**: Oro 7.0 (2026) removes AMD/CommonJS support. See `migration-guide.md` for migration patterns.

```javascript
// LEGACY - DO NOT USE
define(function(require) {
    'use strict';
    const BaseView = require('oroui/js/app/views/base/view');
    const _ = require('underscore');
    
    return BaseView.extend({
        // ...
    });
});
```

---

## Loading External Scripts

For scripts not managed by Webpack, use `scriptjs`:

```javascript
import scriptjs from 'scriptjs';

// Load external script at runtime
scriptjs('https://example.com/external-lib.js', () => {
    // Script is ready
    window.ExternalLib.doSomething();
});
```

---

## Mediator Pattern

The mediator is a global event bus for cross-component communication.

### Setting Handlers (in AppModule)

```javascript
// js/app/modules/messenger-module.js
import mediator from 'oroui/js/mediator';
import messenger from 'oroui/js/messenger';

// Register handlers before app starts
mediator.setHandler('showMessage', messenger.notificationMessage, messenger);
mediator.setHandler('showFlashMessage', messenger.notificationFlashMessage, messenger);
```

### Using Mediator in Components

```javascript
import mediator from 'oroui/js/mediator';

const MyComponent = BaseComponent.extend({
    initialize: function(options) {
        // Execute a handler
        mediator.execute('showMessage', 'success', 'Record saved successfully');
        
        // Listen to events
        this.listenTo(mediator, 'page:update', this.onPageUpdate);
        
        // Trigger custom events
        mediator.trigger('myComponent:initialized', this);
    },
    
    onPageUpdate: function() {
        // Handle page update
    }
});
```

### Common Mediator Commands

| Command | Purpose |
|---------|---------|
| `mediator.execute('showMessage', type, message)` | Show notification |
| `mediator.execute('showFlashMessage', type, message)` | Show flash message |
| `mediator.trigger('page:request')` | Trigger page navigation |
| `mediator.on('event:name', handler)` | Subscribe to event |
| `mediator.off('event:name', handler)` | Unsubscribe from event |

---

## Registry Pattern

The registry provides singleton instance management with automatic cleanup.

```javascript
import registry from 'oroui/js/app/services/registry';

const SharedModel = BaseClass.extend({
    globalId: null,
    
    constructor: function(globalId) {
        this.globalId = globalId;
    }
}, {
    // Static method to get or create instance
    getInstance: function(globalId, applicant) {
        // Try to fetch existing
        let instance = registry.fetch(globalId, applicant);
        
        if (!instance) {
            // Create new and register
            instance = new SharedModel(globalId);
            registry.put(instance, applicant);
        }
        
        return instance;
    }
});

// Usage in component
const MyComponent = BaseComponent.extend({
    initialize: function(options) {
        // Get shared instance tied to this component's lifecycle
        this.sharedData = SharedModel.getInstance('shared-data-key', this);
    }
});
```

---

## Best Practices

### DO

- ✅ Use ES6 `import/export` syntax for all new modules
- ✅ Extend Oro's base classes (`BaseComponent`, `BaseView`, `BaseModel`)
- ✅ Call `super` methods in `initialize` and `dispose`
- ✅ Use mediator for cross-component communication
- ✅ Dispose resources properly to prevent memory leaks
- ✅ Use `data-page-component-*` attributes to instantiate components

### DON'T

- ❌ Use AMD `define()` syntax (deprecated)
- ❌ Create global variables
- ❌ Directly manipulate DOM outside of views
- ❌ Skip calling `dispose` on components/views
- ❌ Hardcode URLs (use routing or data attributes)

---

## Common Pitfalls

### Not Calling Super Dispose

```javascript
// WRONG - Memory leak
const MyComponent = BaseComponent.extend({
    dispose: function() {
        // Forgot to call super
        this.disposed = true;
    }
});

// CORRECT
const MyComponent = BaseComponent.extend({
    dispose: function() {
        if (this.disposed) return;
        // Custom cleanup
        MyComponent.__super__.dispose.call(this);
    }
});
```

### Using Wrong Import Path

```javascript
// WRONG - Missing Oro extensions
import $ from 'jquery/dist/jquery';

// CORRECT - Uses Oro's extended jQuery
import $ from 'jquery';
```

---

## Example: Complete Module Structure

```javascript
// js/app/components/product-selector-component.js
import $ from 'jquery';
import _ from 'underscore';
import BaseComponent from 'oroui/js/app/components/base/component';
import ProductModel from '../models/product-model';
import ProductSelectorView from '../views/product-selector-view';

const ProductSelectorComponent = BaseComponent.extend({
    /**
     * @property {Object} options - Component options
     */
    optionNames: BaseComponent.prototype.optionNames.concat([
        'productId',
        'productName',
        'productUrl'
    ]),
    
    productId: null,
    productName: null,
    productUrl: null,
    
    /**
     * Initialize component
     * @param {Object} options
     */
    initialize: function(options) {
        ProductSelectorComponent.__super__.initialize.call(this, options);
        
        // Create model
        this.model = new ProductModel({
            id: this.productId,
            name: this.productName,
            url: this.productUrl
        });
        
        // Create view
        this.view = new ProductSelectorView({
            el: options._sourceElement,
            model: this.model
        });
        
        // Listen to view events
        this.listenTo(this.view, 'product:selected', this.onProductSelected);
    },
    
    /**
     * Handle product selection
     * @param {number} productId
     */
    onProductSelected: function(productId) {
        this.trigger('selected', productId);
    },
    
    /**
     * Dispose component
     */
    dispose: function() {
        if (this.disposed) return;
        
        // Dispose view and model
        if (this.view) this.view.dispose();
        if (this.model) this.model.dispose();
        
        ProductSelectorComponent.__super__.dispose.call(this);
    }
});

export default ProductSelectorComponent;
```