# Oro 7.0 Migration Guide

This document covers breaking changes and migration patterns for OroCommerce 7.0 LTS (scheduled for release in 2026).

---

## Overview

OroCommerce 7.0 introduces several frontend incompatibilities that require code migration:

1. **AMD/CJS → ES Modules** - Legacy module formats must be converted to ESM
2. **jQuery Deferred → Native Promise** - Use standard Promises instead of jQuery's implementation
3. **Window Scheduler** - New scheduler API usage
4. **Validation Rules** - Updated jquery.validate registration

---

## 1. Migrating AMD to ES Modules

### AMD Pattern (Deprecated)

```javascript
// BEFORE - AMD format (Oro 6.x)
define(['jquery', 'oroui/js/app/views/base/view'], function($, BaseView) {
    'use strict';
    
    const MyView = BaseView.extend({
        initialize: function(options) {
            MyView.__super__.initialize.call(this, options);
        }
    });
    
    return MyView;
});
```

### ES Module Pattern (Required)

```javascript
// AFTER - ES Module format (Oro 7.0+)
import $ from 'jquery';
import BaseView from 'oroui/js/app/views/base/view';

const MyView = BaseView.extend({
    initialize: function(options) {
        MyView.__super__.initialize.call(this, options);
    }
});

export default MyView;
```

### CommonJS Pattern (Deprecated)

```javascript
// BEFORE - CommonJS format
define(function(require) {
    'use strict';
    
    const $ = require('jquery');
    const BaseView = require('oroui/js/app/views/base/view');
    
    const MyView = BaseView.extend({...});
    
    return MyView;
});
```

### CommonJS → ES Module

```javascript
// AFTER - ES Module format
import $ from 'jquery';
import BaseView from 'oroui/js/app/views/base/view';

const MyView = BaseView.extend({...});

export default MyView;
```

### Direct module.exports (Deprecated)

```javascript
// BEFORE - CommonJS with module.exports
const $ = require('jquery');
const BaseView = require('oroui/js/app/views/base/view');

const MyView = BaseView.extend({...});

module.exports = MyView;
```

### Direct exports → ES Module

```javascript
// AFTER - ES Module format
import $ from 'jquery';
import BaseView from 'oroui/js/app/views/base/view';

const MyView = BaseView.extend({...});

export default MyView;
```

---

## 2. Importing ESM from Legacy CJS Code

If you must keep some modules in CommonJS but need to import ESM modules:

```javascript
// CJS code importing ESM module
define(function(require) {
    'use strict';
    
    const $ = require('jquery');
    const BaseView = require('oroui/js/app/views/base/view');
    
    // IMPORTANT: Access .default property for ESM default export
    const SomeESModule = require('path/to/esm').default;
    
    const MyView = BaseView.extend({
        useModule: SomeESModule
    });
    
    return MyView;
});
```

---

## 3. jQuery Deferred → Native Promise

### Method Mapping

| jQuery Deferred | Native Promise | Notes |
|-----------------|----------------|-------|
| `$.Deferred()` | `new Promise()` | Create promise |
| `promise.done(fn)` | `promise.then(fn)` | Success callback |
| `promise.fail(fn)` | `promise.catch(fn)` | Error callback |
| `promise.always(fn)` | `promise.finally(fn)` | Always runs |
| `$.when(a, b)` | `Promise.all([a, b])` | Wait for multiple |

### initLayout Migration

```javascript
// BEFORE - jQuery Deferred
const MyView = BaseView.extend({
    render: function() {
        this.initLayout().done(() => {
            this.doSomething();
        });
    }
});

// AFTER - Native Promise
const MyView = BaseView.extend({
    render: function() {
        this.initLayout().then(() => {
            this.doSomething();
        });
    }
});
```

### $.Deferred → Promise

```javascript
// BEFORE - jQuery Deferred
function loadData() {
    var d = $.Deferred();
    $.ajax({
        url: '/api/data',
        success: function(result) {
            d.resolve(result);
        },
        error: function() {
            d.reject('Request failed');
        }
    });
    return d.promise();
}

loadData()
    .done(function(result) {
        console.log('Loaded:', result);
    })
    .fail(function(err) {
        console.error(err);
    });

// AFTER - Native Promise
function loadData() {
    return new Promise(function(resolve, reject) {
        $.ajax({
            url: '/api/data',
            success: resolve,
            error: function() {
                reject('Request failed');
            }
        });
    });
}

loadData()
    .then(function(result) {
        console.log('Loaded:', result);
    })
    .catch(function(err) {
        console.error(err);
    });
```

### $.when → Promise.all

```javascript
// BEFORE - jQuery Deferred
$.when(loadUser(), loadSettings())
    .done(function(user, settings) {
        console.log(user, settings);
    })
    .fail(function() {
        console.error('Failed');
    });

// AFTER - Native Promise
Promise.all([loadUser(), loadSettings()])
    .then(function([user, settings]) {
        console.log(user, settings);
    })
    .catch(function() {
        console.error('Failed');
    });
```

### async/await Pattern (Recommended)

```javascript
// Modern async/await pattern
async function init() {
    try {
        const result = await loadData();
        console.log('Loaded:', result);
    } catch (err) {
        console.error(err);
    }
}

init();
```

---

## 4. Backward Compatibility Notes

### For Oro 6.x Projects

If your project is on Oro 6.x but you want to prepare for 7.0:

1. **Use ES Modules for all new code**
2. **Use native Promises instead of jQuery Deferred**
3. **Avoid AMD/CommonJS patterns in new files**
4. **Plan migration of existing AMD modules**

### Gradual Migration

You can migrate incrementally:

1. New modules → ES Modules immediately
2. High-traffic modules → Migrate first
3. Legacy modules → Migrate during refactoring
4. Use `.default` when CJS imports ESM temporarily

---

## Migration Checklist

Before upgrading to Oro 7.0:

- [ ] All `define()` → `import/export`
- [ ] All `require()` → `import`
- [ ] All `module.exports` → `export default`
- [ ] All `$.Deferred()` → `new Promise()`
- [ ] All `.done()` → `.then()`
- [ ] All `.fail()` → `.catch()`
- [ ] All `.always()` → `.finally()`
- [ ] All `$.when()` → `Promise.all()`
- [ ] Test all async operations
- [ ] Update unit tests for promise patterns

---

## Quick Reference

### ES Module Syntax

```javascript
// Named imports
import { something } from 'module';

// Default import
import Something from 'module';

// Named export
export const something = ...;
export function something() {}

// Default export
export default class Something {}
export default Something;
```

### Promise Syntax

```javascript
// Create promise
const p = new Promise((resolve, reject) => {
    // async work
    resolve(result);  // or reject(error);
});

// Use promise
p.then(result => { /* success */ })
 .catch(error => { /* failure */ })
 .finally(() => { /* cleanup */ });

// Multiple promises
Promise.all([p1, p2, p3])
    .then(([r1, r2, r3]) => { /* all done */ });

// Async/await
async function work() {
    try {
        const result = await p;
        // use result
    } catch (error) {
        // handle error
    }
}
```