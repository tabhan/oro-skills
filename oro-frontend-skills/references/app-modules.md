# App Modules

AppModules are initialization scripts that run before the application starts. They register handlers, extend global objects, and set up cross-bundle functionality.

---

## Summary

- **AppModule** = Initialization code executed once at application startup
- Registered in `jsmodules.yml` under the `app-modules` section
- Used to register mediator handlers, custom validators, global listeners
- Export nothing - they execute side effects

---

## Registration

### In jsmodules.yml

```yaml
# BundleName/Resources/config/oro/jsmodules.yml
app-modules:
    - mybundle/js/app/modules/messenger-module
    - mybundle/js/app/modules/validator-module
    - mybundle/js/app/modules/template-macros-module
```

### Loading Order

AppModules are loaded after all module configurations are processed, but before the application instance is created. This ensures handlers are available before any component needs them.

---

## AppModule Patterns

### Pattern 1: Mediator Handler Registration

```javascript
// js/app/modules/messenger-module.js
import mediator from 'oroui/js/mediator';
import messenger from 'oroui/js/messenger';

/**
 * Init messenger's handlers
 * Called automatically when app initializes
 */
mediator.setHandler('addMessage', messenger.addMessage, messenger);
mediator.setHandler('showMessage', messenger.notificationMessage, messenger);
mediator.setHandler('showProcessingMessage', messenger.showProcessingMessage, messenger);
mediator.setHandler('showFlashMessage', messenger.notificationFlashMessage, messenger);
mediator.setHandler('showErrorMessage', messenger.showErrorMessage, messenger);

// No export needed - side effects only
```

**Usage in components:**
```javascript
import mediator from 'oroui/js/mediator';

// Execute registered handler
mediator.execute('showMessage', 'success', 'Record saved!');
```

### Pattern 2: Custom Validator Registration

```javascript
// js/app/modules/validator-constraints-module.js
import $ from 'jquery.validate';

/**
 * Load custom validation methods
 */
$.validator.loadMethod([
    'mybundle/js/validator/custom-email',
    'mybundle/js/validator/phone-format',
    'mybundle/js/validator/sku-pattern'
]);
```

### Pattern 3: Template Macros Registration

```javascript
// js/app/modules/template-macros-module.js
import mediator from 'oroui/js/mediator';
import template from 'oroui/templates/macros.html';

/**
 * Register template macros for use in JS templates
 */
mediator.setTemplateMacro('formatDate', template.formatDate);
mediator.setTemplateMacro('formatCurrency', template.formatCurrency);
mediator.setTemplateMacro('renderLabel', template.renderLabel);
```

### Pattern 4: Global Event Listeners

```javascript
// js/app/modules/layout-module.js
import mediator from 'oroui/js/mediator';
import layout from 'oroui/js/layout';

/**
 * Initialize global layout handlers
 */
mediator.setHandler('layout:init', layout.init, layout);
mediator.setHandler('layout:dispose', layout.dispose, layout);

// Listen to page lifecycle events
mediator.on('page:beforeChange', function() {
    // Cleanup before page navigation
});

mediator.on('page:afterChange', function() {
    // Initialize after page loaded
});
```

### Pattern 5: Component Shortcuts Registration

```javascript
// js/app/modules/component-shortcuts-module.js
import ComponentShortcutsManager from 'oroui/js/component-shortcuts-manager';

/**
 * Register component shortcuts for simplified usage
 */
ComponentShortcutsManager.add('collapse', {
    moduleName: 'oroui/js/app/components/jquery-widget-component',
    options: {
        widgetModule: 'oroui/js/widget/collapse-widget'
    }
});

ComponentShortcutsManager.add('autocomplete', {
    moduleName: 'oroform/js/app/components/select2-autocomplete-component',
    scalarOption: 'autocompleteApi'
});
```

### Pattern 6: Plugin Registration

```javascript
// js/app/modules/datagrid-plugins-module.js
import mediator from 'oroui/js/mediator';

/**
 * Register DataGrid plugins
 */
mediator.on('datagrid:configure', function(grid) {
    grid.registerPlugin('myCustomPlugin', {
        module: 'mybundle/js/app/plugins/datagrid/custom-plugin',
        priority: 10
    });
});
```

---

## Mediator API

The mediator is the global event bus for cross-component communication.

### Setting Handlers

```javascript
import mediator from 'oroui/js/mediator';

// Register a handler (can be called with execute)
mediator.setHandler('handlerName', callback, context);

// Example
mediator.setHandler('product:load', function(productId) {
    return $.get('/api/products/' + productId);
});
```

### Executing Handlers

```javascript
import mediator from 'oroui/js/mediator';

// Execute a handler
mediator.execute('handlerName', arg1, arg2);

// Example
mediator.execute('product:load', 123);
```

### Event Subscription

```javascript
import mediator from 'oroui/js/mediator';

// Subscribe to events
mediator.on('event:name', callback, context);

// One-time subscription
mediator.once('event:name', callback, context);

// Unsubscribe
mediator.off('event:name', callback);
```

### Triggering Events

```javascript
import mediator from 'oroui/js/mediator';

// Trigger an event
mediator.trigger('event:name', data);

// Example
mediator.trigger('product:selected', { id: 123, name: 'Product A' });
```

### Common Mediator Events

| Event | When Fired |
|-------|-----------|
| `page:beforeChange` | Before page navigation |
| `page:request` | When requesting new page |
| `page:update` | When page content received |
| `page:afterChange` | After all components initialized |
| `route:change` | On URL route change |
| `layout:init` | When layout initialized |
| `layout:dispose` | When layout disposed |

---

## Best Practices

### DO

- ✅ Register mediator handlers in AppModules
- ✅ Load custom validators via AppModules
- ✅ Set up global listeners in AppModules
- ✅ Use mediator for cross-component communication
- ✅ Keep AppModules focused on single responsibility

### DON'T

- ❌ Export anything from AppModules
- ❌ Put component-specific logic in AppModules
- ❌ Create circular dependencies between AppModules
- ❌ Use AppModules for feature-specific initialization (use components instead)

---

## Common Pitfalls

### Handler Registration After Use

```javascript
// WRONG - Handler used before registration
mediator.execute('myHandler', data);

// In AppModule loaded later
mediator.setHandler('myHandler', callback);

// CORRECT - AppModule loads first, then component executes
// AppModule loads at app initialization
mediator.setHandler('myHandler', callback);

// Component uses handler later
mediator.execute('myHandler', data);
```

### Not Cleaning Up Listeners

```javascript
// WRONG - Listener persists forever
mediator.on('page:update', function() {
    // This runs on every page update
});

// CORRECT - Use component lifecycle
const MyComponent = BaseComponent.extend({
    initialize: function() {
        this.listenTo(mediator, 'page:update', this.onPageUpdate);
    },
    
    dispose: function() {
        // listenTo automatically cleaned up
        MyComponent.__super__.dispose.call(this);
    }
});
```

---

## Example: Complete AppModule

```javascript
// js/app/modules/customer-module.js
import mediator from 'oroui/js/mediator';
import CustomerService from '../services/customer-service';
import $ from 'jquery';

/**
 * Customer-related mediator handlers and listeners
 */

// Create service instance
const customerService = new CustomerService();

// Register handlers
mediator.setHandler('customer:getCurrent', function() {
    return customerService.getCurrentCustomer();
}, customerService);

mediator.setHandler('customer:loadOrders', function(customerId) {
    return customerService.loadOrders(customerId);
}, customerService);

mediator.setHandler('customer:updatePreferences', function(preferences) {
    return customerService.updatePreferences(preferences);
}, customerService);

// Set up global event listeners
mediator.on('customer:login', function(customerData) {
    customerService.setCurrentCustomer(customerData);
    mediator.trigger('customer:changed', customerData);
});

mediator.on('customer:logout', function() {
    customerService.clearCurrentCustomer();
    mediator.trigger('customer:changed', null);
});

// Listen to page lifecycle
mediator.on('page:afterChange', function() {
    // Refresh customer data on page navigation if needed
    if (customerService.needsRefresh()) {
        customerService.refresh();
    }
});

// No export - AppModule runs for side effects only
```

---

## Related Topics

- **Page Components**: Components that use mediator handlers
- **Configuration Reference**: How to register AppModules in jsmodules.yml
- **Mediator Pattern**: Cross-component communication