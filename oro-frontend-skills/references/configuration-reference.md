# Configuration Reference

Reference for key frontend configuration files: `jsmodules.yml` and `assets.yml`.

---

## jsmodules.yml

JavaScript module configuration for webpack bundling.

### Location

| Context | Path |
|---------|------|
| Back-office | `BundleName/Resources/config/oro/jsmodules.yml` |
| Storefront | `BundleName/Resources/views/layouts/{theme}/config/jsmodules.yml` |

### Complete Structure

```yaml
# BundleName/Resources/config/oro/jsmodules.yml

# Module name aliases (short names for imports)
aliases:
    backbone$: backbone/backbone
    jquery$: jquery/dist/jquery
    oroui/js/widget$: oroui/js/widget/widget-manager

# App modules - loaded before application starts
app-modules:
    - oroui/js/app/modules/messenger-module
    - oroui/js/app/modules/component-shortcuts-module
    - mybundle/js/app/modules/validator-module

# Module configurations (passed to module constructor)
configs:
    oroui/js/app:
        baseUrl: '/'
        debug: false
    oroui/js/app/views/page-layout-view: {}

# Dynamic imports - lazy-loaded modules
dynamic-imports:
    # Commons - loaded early, frequently used
    commons:
        - jquery
        - underscore
        - oroui/js/app/components/view-component
        - oroui/js/app/components/widget-component
    
    # Custom group - load on demand
    mybundle:
        - mybundle/js/app/components/heavy-component
        - mybundle/js/app/views/complex-view
    
    # jstree group - tree-related modules
    jstree:
        - oroui/js/app/views/jstree/base-tree-view

# Entry points - webpack build entries
entry:
    app:
        - oroui/js/app
        - oroui/js/app/services/app-ready-load-modules

# Module mapping (substitution)
map:
    # Global mapping
    '*':
        jquery: oroui/js/extend/jquery
        backbone: oroui/js/extend/backbone
    
    # Context-specific mapping
    oroui/js/extend/jquery:
        jquery: jquery

# Shim configuration (for non-AMD modules)
shim:
    jquery:
        expose:
            - $
            - jQuery
    
    jquery.select2:
        exports: single|Select2
        imports:
            - single|jquery|jQuery
```

### Configuration Sections Explained

#### aliases

Short names for module paths:

```yaml
aliases:
    # $ suffix means exact match
    backbone$: backbone/backbone
    # Without $, matches prefix too
    oro/widget: oroui/js/widget
```

```javascript
// With alias
import Backbone from 'backbone';

// Without alias
import Backbone from 'backbone/backbone';
```

#### app-modules

Modules that execute before app starts (side effects only):

```yaml
app-modules:
    - mybundle/js/app/modules/handler-module
```

```javascript
// handler-module.js - no export needed
import mediator from 'oroui/js/mediator';

mediator.setHandler('myHandler', callback);
```

#### configs

Runtime configuration passed to modules:

```yaml
configs:
    mybundle/js/app/views/my-view:
        autoRender: true
        refreshInterval: 30000
```

```javascript
// my-view.js
import BaseView from 'oroui/js/app/views/base/view';
import moduleConfig from 'module-config';

const MyView = BaseView.extend({
    initialize: function(options) {
        // Access config
        const config = moduleConfig.get('mybundle/js/app/views/my-view');
        this.refreshInterval = config.refreshInterval;
    },
});
```

#### dynamic-imports

Lazy-loaded module groups:

```yaml
dynamic-imports:
    commons:
        - jquery
        - oroui/js/app/components/view-component
    
    heavy:
        - mybundle/js/app/components/chart-component
```

```javascript
import loadModules from 'oroui/js/app/services/load-modules';

// Load specific module
loadModules('mybundle/js/app/components/chart-component').then(Component => {
    // Use component
});

// Load entire group
loadModules.import('heavy').then(modules => {
    // All modules in 'heavy' group loaded
});
```

#### map

Module substitution for dependencies:

```yaml
map:
    '*':
        # All modules using 'jquery' get Oro's extended version
        jquery: oroui/js/extend/jquery
    
    # For oroui/js/extend/jquery itself, use original jquery
    oroui/js/extend/jquery:
        jquery: jquery
```

#### shim

Configuration for non-module libraries:

```yaml
shim:
    jquery.plugin:
        # Export value
        exports: single|jQuery.plugin
        
        # Dependencies to load first
        imports:
            - single|jquery|jQuery
        
        # Expose to global scope
        expose:
            - $.plugin
```

---

## assets.yml

CSS/SCSS asset configuration.

### Location

| Context | Path |
|---------|------|
| Back-office | `BundleName/Resources/config/oro/assets.yml` |
| Storefront | `BundleName/Resources/views/layouts/{theme}/config/assets.yml` |

### Complete Structure

```yaml
# BundleName/Resources/views/layouts/default/config/assets.yml

css:
    # Input files (processed in order)
    inputs:
        # Settings first (mixins, functions)
        - 'bundles/oroui/default/scss/settings/global-settings.scss'
        
        # Variables next
        - 'bundles/oroui/default/scss/variables/variables.scss'
        - 'bundles/mybundle/default/scss/variables/component-config.scss'
        
        # Component styles last
        - 'bundles/mybundle/default/scss/main.scss'
        
        # External npm modules (prefix with ~)
        - '~prismjs/themes/prism-coy.css'
    
    # Output compiled CSS file
    output: 'css/styles.css'
    
    # Files to process for RTL support
    auto_rtl_inputs:
        - 'bundles/oro*/**'
        - 'bundles/mybundle/**'

# JavaScript assets (less common)
js:
    inputs:
        - 'bundles/mybundle/js/entry-point.js'
    output: 'js/bundle.js'

# Icon configuration
icons:
    inputs:
        - 'bundles/mybundle/svg-icons/*.svg'
```

### CSS Loading Order

**Critical**: Load order determines variable availability.

```yaml
# CORRECT ORDER
css:
    inputs:
        # 1. Settings (mixins, functions - no CSS output)
        - 'bundles/oroui/default/scss/settings/_functions.scss'
        - 'bundles/oroui/default/scss/settings/_mixins.scss'
        
        # 2. Variables (use settings, define values)
        - 'bundles/oroui/default/scss/variables/_colors.scss'
        - 'bundles/oroui/default/scss/variables/_spacing.scss'
        - 'bundles/mybundle/default/scss/variables/_overrides.scss'
        
        # 3. Styles (use variables and settings)
        - 'bundles/oroui/default/scss/main.scss'
        - 'bundles/mybundle/default/scss/components/*.scss'
```

### Overriding/Removing Files

```yaml
css:
    inputs:
        # Remove file entirely (use ~)
        - 'bundles/oroui/default/scss/old-component.scss': ~
        
        # Replace with custom file
        - 'bundles/oroui/default/scss/button.scss': 'bundles/mybundle/default/scss/button.scss'
        
        # Add new files
        - 'bundles/mybundle/default/scss/new-component.scss'
```

### Theme Inheritance

```yaml
# Parent theme: default/assets.yml
css:
    inputs:
        - 'bundles/oroui/default/scss/main.scss'
    output: 'css/styles.css'

# Child theme: custom/config/assets.yml
css:
    inputs:
        # Override variables before parent styles
        - 'bundles/custom/scss/variables/_overrides.scss'
        
        # Inherit parent styles
        - 'bundles/oroui/default/scss/main.scss'
        
        # Add custom styles
        - 'bundles/custom/scss/custom.scss'
    output: 'css/styles.css'
```

---

## Layout YAML Reference

### Basic Structure

```yaml
# layouts/default/page/layout.yml

layout:
    # Import reusable layout blocks
    imports:
        - id: header
          root: __root
        - id: footer
          root: __root
    
    # Define blocks
    actions:
        # Set block theme
        - '@setBlockTheme':
            themes: 'page.html.twig'
        
        # Add a block
        - '@add':
            id: my_block
            parentId: __root
            blockType: container
            options:
                attr:
                    class: my-container
        
        # Add tree of blocks
        - '@addTree':
            items:
                sidebar:
                    blockType: container
                sidebar_content:
                    blockType: text
                    options:
                        text: 'Sidebar Content'
            tree:
                __root:
                    sidebar:
                        sidebar_content: ~
        
        # Remove block
        - '@remove':
            id: unwanted_block
        
        # Move block
        - '@move':
            id: my_block
            parentId: new_parent
        
        # Set option
        - '@setOption':
            id: my_block
            optionName: visible
            optionValue: true
        
        # Change block type
        - '@changeBlockType':
            id: my_block
            blockType: text
```

### Conditional Actions

```yaml
layout:
    actions:
        - '@add':
            id: mobile_menu
            blockType: container
    conditions: 'context["is_mobile"] == true'
```

### Data Access

```yaml
# Access context data
options:
    text: '=context["page_title"]'

# Access data providers
options:
    product: '=data["product"]'
    url: '=data["back_to_url"]'

# Call methods
options:
    name: '=data["product"].getName()'
    price: '=data["product"].getFormattedPrice()'
```

---

## theme.yml

Theme definition file.

```yaml
# layouts/custom/theme.yml

name: Custom Theme
parent: default          # Inherit from parent theme
label: My Custom Theme
description: Custom storefront theme
groups: [commerce]       # Theme groups
```

---

## Quick Reference

### jsmodules.yml Sections

| Section | Purpose |
|---------|---------|
| `aliases` | Short names for modules |
| `app-modules` | Auto-loaded initialization |
| `configs` | Runtime configuration |
| `dynamic-imports` | Lazy-loaded groups |
| `entry` | Webpack entry points |
| `map` | Module substitution |
| `shim` | Non-AMD library config |

### assets.yml Sections

| Section | Purpose |
|---------|---------|
| `css.inputs` | SCSS files to compile |
| `css.output` | Output file path |
| `css.auto_rtl_inputs` | Files for RTL processing |
| `js.inputs` | JavaScript files |
| `icons.inputs` | SVG icon files |

### Common Layout Actions

| Action | Purpose |
|--------|---------|
| `@add` | Add single block |
| `@addTree` | Add block hierarchy |
| `@remove` | Remove block |
| `@move` | Move block |
| `@setOption` | Set block option |
| `@setBlockTheme` | Apply Twig template |
| `@setFormTheme` | Apply form theme |
| `@changeBlockType` | Change block type |

---

## Example: Complete Bundle Configuration

```yaml
# MyBundle/Resources/config/oro/jsmodules.yml
aliases:
    mybundle/component$: mybundle/js/app/components

app-modules:
    - mybundle/js/app/modules/handler-module

configs:
    mybundle/js/app/views/product-view:
        autoRefresh: true

dynamic-imports:
    commons:
        - mybundle/js/app/components/product-component
    heavy:
        - mybundle/js/app/components/chart-component

# MyBundle/Resources/config/oro/assets.yml
css:
    inputs:
        - 'bundles/mybundle/default/scss/settings/_mixins.scss'
        - 'bundles/mybundle/default/scss/variables/_variables.scss'
        - 'bundles/mybundle/default/scss/main.scss'
    output: 'css/styles.css'
    auto_rtl_inputs:
        - 'bundles/mybundle/**'

# MyBundle/Resources/views/layouts/default/layout.yml
layout:
    imports:
        - id: product_card
    
    actions:
        - '@setBlockTheme':
            themes: 'theme.html.twig'
        
        - '@add':
            id: product_gallery
            parentId: __root
            blockType: product_gallery
            options:
                product: '=data["product"]'
```