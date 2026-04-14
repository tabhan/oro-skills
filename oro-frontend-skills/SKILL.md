---
name: oro-frontend-knowledge-base
description: >
  When working on OroCommerce frontend development (JavaScript, SCSS, Twig, configuration),
  you MUST use this skill to consult the local knowledge base documentation instead of
  relying on memory.
  
  Trigger scenarios:
  - Creating/modifying PageComponent, AppModule, View, Model, Collection
  - Writing SCSS styles, configuring CSS architecture, handling theme inheritance
  - Modifying Twig templates, defining layout blocks
  - Configuring jsmodules.yml, assets.yml
  - Handling data-page-component-* attributes
  - Using mediator, registry, BaseComponent
  - Following OroCommerce frontend best practices, avoiding anti-patterns
  - Migrating from Oro 6.x to 7.0 (AMD→ESM, jQuery Deferred→Promise)
  
  For any OroCommerce frontend API, configuration, naming conventions, architecture
  patterns, lifecycle management, or security considerations, read documentation first.
---

# OroCommerce Frontend Knowledge Base Skill

Local knowledge base index. When doing OroCommerce frontend development, **consult documentation first, then write code**.

---

## Available Documents (Task → Document Mapping)

| Task Type | Document File | Lines | Key Content |
|----------|--------------|------|-------------|
| **Project Overview** | `references/README.md` | 98 | Tech stack, file structure conventions, key concepts |
| **JS Architecture** | `references/javascript-architecture.md` | 405 | Chaplin/Backbone structure, mediator, registry, ES6 module patterns |
| **PageComponent** | `references/page-components.md` | 558 | BaseComponent extension, data-* attributes, initialization, dispose patterns |
| **AppModule** | `references/app-modules.md` | 346 | Pre-app initialization, mediator.setHandler, 6 patterns |
| **SCSS/CSS** | `references/css-architecture.md` | 576 | Three-folder structure, theme inheritance, SCSS functions/mixins |
| **Twig Templates** | `references/twig-templates.md` | 546 | Layout blocks, block themes, Twig functions |
| **Configuration Files** | `references/configuration-reference.md` | 526 | jsmodules.yml, assets.yml, theme.yml |
| **Best Practices** | `references/best-practices.md` | 554 | Naming conventions, security, anti-patterns, version differences |
| **Migration Guide** | `references/migration-guide.md` | 339 | AMD→ESM, jQuery Deferred→Promise |

---

## Usage Rules

### 1. Identify Task Type → Select Document

```
Task examples → Document mapping:

"Create a PageComponent"            → page-components.md (Extending BaseComponent)
"Configure jsmodules.yml"           → configuration-reference.md (jsmodules.yml)
"Write SCSS styles"                 → css-architecture.md (SCSS Functions)
"Use mediator for communication"    → javascript-architecture.md (Mediator Pattern)
"Handle data-page-component-options" → page-components.md (Definition in Twig Templates)
"Migrate AMD code to ES6"           → migration-guide.md (§1. Migrating AMD to ES Modules)
"Avoid memory leaks"                → page-components.md (Best Practices) + best-practices.md (Anti-Patterns)
"Register AppModule"                → app-modules.md (Registration + Patterns)
```

### 2. Read Documents (By Section, Avoid Full Loading)

**⚠️ For large documents (>300 lines), do NOT load the full file! Use offset + limit to read only relevant sections.**

```typescript
// CORRECT: Read specific section only
read({ 
  filePath: ".../references/page-components.md", 
  offset: 103,  // Start from "Extending BaseComponent" section
  limit: 100    // Read 100 lines
})

// WRONG: Loading full 558 lines (wastes context)
read({ filePath: ".../references/page-components.md" })  // ❌
```

**README.md (98 lines)** is the only document that can be fully loaded for a quick project overview.

### 3. Use Table of Contents to Locate Sections

Find the section's starting line number from the TOC below, then read with `offset`.

---

## Document Table of Contents (Line Number Index)

### references/README.md (98 lines) — Can be fully loaded

```
Line  Section
11    ## Overview
15    ### Technology Stack
30    ## Structure
45    ## Quick Reference
73    ### Key Concepts
82    ## Usage by Agents
93    ## Related Resources
```

### references/javascript-architecture.md (405 lines)

```
Line  Section                                   Content Summary
7     ## Summary                                 Architecture overview
18    ## Technology Stack                        jQuery/Backbone/Chaplin etc.
32    ## Application Lifecycle                   Lifecycle diagram, PageController
69    ## Naming Conventions                      File naming rules, suffix conventions
98    ## ES6 Module Pattern (Recommended)        import/export patterns ⭐
151   ## Legacy AMD Pattern (Avoid)              deprecated, see migration guide
172   ## Loading External Scripts                scriptjs usage
188   ## Mediator Pattern                        Cross-component communication ⭐
239   ## Registry Pattern                        Singleton management
279   ## Best Practices                          DO/DON'T
300   ## Common Pitfalls                         Memory leaks, wrong import paths
335   ## Example: Complete Module Structure      Full code example
```

**Common sections**:
- Create JS module → offset: 98, limit: 80 (ES6 Module Pattern)
- mediator communication → offset: 188, limit: 50 (Mediator Pattern)
- Memory leaks → offset: 300, limit: 40 (Common Pitfalls)

### references/page-components.md (558 lines)

```
Line  Section                                   Content Summary
7     ## Summary                                 Component overview
16    ## How It Works                            Initialization flow diagram
43    ## Definition in Twig Templates            data-* attribute definition ⭐
103   ## Extending BaseComponent                 Component base class extension ⭐
235   ## Function as Component                   Simple function components
257   ## ViewComponent                           View component shortcut
281   ## JqueryWidgetComponent                   jQuery UI wrapper
318   ## Component Shortcuts                     Shortcut syntax
362   ## Built-in Components                     Built-in component list
377   ## Accessing Components                    Access by name
402   ## Best Practices                          DO/DON'T
422   ## Common Pitfalls                         Memory leaks, wrong element
468   ## Example: Complete Component with View   Full code example ⭐
```

**Common sections**:
- Define component attributes → offset: 43, limit: 60 (Twig Templates)
- Extend BaseComponent → offset: 103, limit: 135 (Extending BaseComponent)
- Full example → offset: 468, limit: 90 (Example)

### references/app-modules.md (346 lines)

```
Line  Section                                   Content Summary
7     ## Summary                                 AppModule overview
16    ## Registration                            jsmodules.yml registration
34    ## AppModule Patterns                      6 patterns ⭐
      ├ 36  Pattern 1: Mediator Handler Registration
      ├ 64  Pattern 2: Custom Validator Registration
      ├ 80  Pattern 3: Template Macros Registration
      ├ 95  Pattern 4: Global Event Listeners
      ├ 118 Pattern 5: Component Shortcuts Registration
      └ 140 Pattern 6: Plugin Registration
159   ## Mediator API                            setHandler/execute/trigger
230   ## Best Practices                          DO/DON'T
249   ## Common Pitfalls                         Registration timing, listener cleanup
291   ## Example: Complete AppModule             Full code example
```

**Common sections**:
- Register AppModule → offset: 16, limit: 20 (Registration)
- 6 patterns → offset: 34, limit: 130 (Patterns)
- Mediator API → offset: 159, limit: 70

### references/css-architecture.md (576 lines)

```
Line  Section                                   Content Summary
7     ## Summary                                 SCSS architecture overview
17    ## File Structure                          Three-folder structure ⭐
55    ## Configuration (assets.yml)              CSS configuration ⭐
105   ## SCSS Functions                          get-color/spacing/z/breakpoint ⭐
182   ## SCSS Mixins                             Common mixins
227   ## Variable Configuration                  Variable definition and override
258   ## Component Styles                        BEM naming
337   ## Media Queries                           Responsive handling
375   ## Theme Inheritance                       Theme inheritance ⭐
417   ## RTL Support                             RTL auto-generation
449   ## Best Practices                          DO/DON'T
471   ## Common Pitfalls                         Loading order, hardcoded values
509   ## Example: Complete Component             Full style example
```

**Common sections**:
- File structure → offset: 17, limit: 40 (File Structure)
- assets.yml config → offset: 55, limit: 50 (Configuration)
- SCSS functions → offset: 105, limit: 80 (Functions)
- Theme inheritance → offset: 375, limit: 50 (Theme Inheritance)

### references/twig-templates.md (546 lines)

```
Line  Section                                   Content Summary
7     ## Summary                                 Twig overview
17    ## Twig Block Names                        Block naming rules
49    ## Block Themes                            Block theme definition
95    ## Passing Variables to Blocks             Variable passing
172   ## Twig Functions                          block_widget/merge_context ⭐
244   ## Data Providers                          Data providers
298   ## JavaScript Component Integration        data-* attributes ⭐
341   ## Form Themes                             Form themes
367   ## Debugging                               dump/template location
388   ## Template Overrides                      Template override paths
419   ## Best Practices                          DO/DON'T
439   ## Common Pitfalls                         Missing block_widget
473   ## Example: Complete Product View          Full example
```

**Common sections**:
- Twig functions → offset: 172, limit: 60
- JS component integration → offset: 298, limit: 45

### references/configuration-reference.md (526 lines)

```
Line  Section                                   Content Summary
7     ## jsmodules.yml                           JS config full structure ⭐
      ├ 11  Location
      ├ 18  Complete Structure
      ├ 90  Configuration Sections Explained
      └ 92  aliases (lines 92-112)
      └ 112 app-modules (lines 112-128)
      └ 128 configs (lines 128-153)
      └ 153 dynamic-imports (lines 153-181)
      └ 181 map (lines 181-196)
      └ 196 shim (lines 196-217)
217   ## assets.yml                               CSS config full structure ⭐
      ├ 221 Location
      ├ 228 Complete Structure
      └ 269 CSS Loading Order
      └ 291 Overriding/Removing Files
      └ 306 Theme Inheritance
331   ## Layout YAML Reference                    Layout YAML
427   ## theme.yml                                Theme configuration
443   ## Quick Reference                          Quick reference tables
482   ## Example: Complete Bundle Configuration   Full config example
```

**Common sections**:
- jsmodules.yml full structure → offset: 7, limit: 90
- jsmodules.yml config sections → offset: 90, limit: 130
- assets.yml full structure → offset: 217, limit: 90

### references/best-practices.md (554 lines)

```
Line  Section                                   Content Summary
7     ## Coding Standards                        JS/SCSS naming, formatting
107   ## Anti-Patterns                           Anti-pattern list ⭐
      ├ 109 JavaScript (type suppression, empty catch, console.log)
      └ 216 CSS/SCSS (hardcoded values, deep nesting, !important)
303   ## Security Guidelines                     XSS prevention, CSRF
376   ## Performance Guidelines                  Lazy loading, dynamic imports
435   ## Common Pitfalls                         Common mistakes
507   ## Version-Specific Guidelines             Oro 6.x vs 7.0
523   ## Checklist                               Checklist
```

**Common sections**:
- Anti-patterns → offset: 107, limit: 110 (Anti-Patterns)
- Security → offset: 303, limit: 75 (Security)
- Checklist → offset: 523, limit: 30

### references/migration-guide.md (339 lines)

```
Line  Section                                   Content Summary
7     ## Overview                                Migration overview
18    ## 1. Migrating AMD to ES Modules          AMD→ESM ⭐
      ├ 20  AMD Pattern (Deprecated)
      ├ 37  ES Module Pattern (Required)
      ├ 53  CommonJS Pattern (Deprecated)
      ├ 69  CommonJS → ES Module
      └ 81  Direct module.exports → ES Module
107   ## 2. Importing ESM from Legacy CJS       CJS compatibility
132   ## 3. jQuery Deferred → Native Promise     Promise migration ⭐
      ├ 134 Method Mapping
      ├ 144 initLayout Migration
      ├ 166 $.Deferred → Promise
      ├ 214 $.when → Promise.all
      └ 236 async/await Pattern
254   ## 4. Backward Compatibility Notes        Compatibility
276   ## Migration Checklist                     Migration checklist
293   ## Quick Reference                         Quick reference
```

**Common sections**:
- AMD→ESM → offset: 18, limit: 90
- Promise migration → offset: 132, limit: 125

---

## Examples: Reading by Section

### Scenario: Create PageComponent

```
1. Read Summary for concept understanding
   read({ filePath: ".../references/page-components.md", offset: 7, limit: 40 })

2. Read Extending BaseComponent for extension patterns
   read({ filePath: ".../references/page-components.md", offset: 103, limit: 135 })

3. Read full example for code structure reference
   read({ filePath: ".../references/page-components.md", offset: 468, limit: 90 })
```

### Scenario: Configure jsmodules.yml

```
1. Read Complete Structure for config format
   read({ filePath: ".../references/configuration-reference.md", offset: 18, limit: 75 })

2. Read aliases/app-modules sections for specific config
   read({ filePath: ".../references/configuration-reference.md", offset: 90, limit: 130 })
```

### Scenario: Write SCSS Styles

```
1. Read File Structure for file organization
   read({ filePath: ".../references/css-architecture.md", offset: 17, limit: 40 })

2. Read SCSS Functions for Oro-specific functions
   read({ filePath: ".../references/css-architecture.md", offset: 105, limit: 80 })

3. Read Best Practices for standards
   read({ filePath: ".../references/css-architecture.md", offset: 449, limit: 25 })
```

---

## Document Paths

All documents are located in `skills/references/` directory:

```
skills/
├── SKILL.md
└── references/
    ├── README.md                  (98 lines, can be fully loaded)
    ├── javascript-architecture.md (405 lines)
    ├── page-components.md         (558 lines)
    ├── app-modules.md             (346 lines)
    ├── css-architecture.md        (576 lines)
    ├── twig-templates.md          (546 lines)
    ├── configuration-reference.md (526 lines)
    ├── best-practices.md          (554 lines)
    └── migration-guide.md         (339 lines)
```

---

## Related Skills

This knowledge base works with the following user skills:

| Skill | Purpose | Use Together When |
|-------|---------|-------------------|
| `oro-frontend/oro-coding-standards` | OroCommerce frontend coding standards | When writing code |
| `oro-frontend/oro-js-creation` | Create JavaScript modules | Creating PageComponent/View/Model |
| `oro-frontend/oro-js-registration` | Register JS modules (jsmodules.yml) | Configuring jsmodules.yml |
| `oro-frontend/oro-css-creation` | Create SCSS styles | Writing style files |
| `oro-frontend/oro-css-registration` | Register CSS files (assets.yml) | Configuring assets.yml |

**Recommended approach**: Load corresponding skill + consult relevant documentation in this knowledge base.

---

## Important Reminders

**Do not rely on memory!** OroCommerce frontend has many specific conventions and anti-patterns:

- ❌ AMD `define()` is deprecated, must use ES6 `import/export`
- ❌ jQuery Deferred is deprecated, must use Promise
- ❌ Direct DOM manipulation (should be in Views)
- ❌ Forgetting to call `dispose()` (memory leaks)
- ❌ Wrong import paths (must use Oro extended versions)
- ❌ Hardcoded URLs (must use routing or data attributes)

Consulting documentation avoids these common mistakes.