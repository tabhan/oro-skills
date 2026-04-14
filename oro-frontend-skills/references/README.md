# OroCommerce Frontend Knowledge Base

A structured knowledge base for AI agents working with OroCommerce frontend development.

**Generated from:** https://doc.oroinc.com/frontend/
**OroCommerce Version:** Enterprise 6.1 / 7.0
**Last Updated:** 2025-03-30

---

## Overview

OroCommerce frontend is built on a modular JavaScript architecture based on **Chaplin** (an extension of **Backbone.js**), with **SCSS** for styling and **Twig** templates for server-side rendering. The frontend supports both Back-Office admin themes and Storefront customer-facing themes.

### Technology Stack

| Technology | Purpose | Notes |
|------------|---------|-------|
| jQuery + jQuery-UI | DOM manipulation, widgets | Extended with Oro customizations |
| Bootstrap 4+ | UI framework | Adjusted for Oro needs |
| Backbone.js | MVC foundation | Models, Collections, Views |
| Chaplin | Application structure | Controllers, Mediator, Layout |
| SCSS | Styling | Variables, mixins, functions |
| Twig | Server templates | Layout blocks, themes |
| Webpack | Build system | Module bundling, code splitting |
| PNPM | Package manager | Dependency management |

---

## Structure

| File | Contents |
|------|----------|
| `javascript-architecture.md` | JS application structure, modules, lifecycle, naming conventions |
| `page-components.md` | PageComponent patterns, BaseComponent, view-component, initialization |
| `app-modules.md` | AppModule registration, mediator handlers, initialization hooks |
| `css-architecture.md` | SCSS structure, variables, settings, theme inheritance |
| `twig-templates.md` | Twig blocks, block themes, layout integration |
| `configuration-reference.md` | jsmodules.yml, assets.yml configuration formats |
| `best-practices.md` | Coding standards, anti-patterns, security guidelines |
| `migration-guide.md` | Oro 7.0 breaking changes, AMD→ESM, jQuery Deferred→Promise |

---

## Quick Reference

### File Structure Convention

```
Acme/Bundle/DemoBundle/Resources/
├── public/
│   ├── {theme-name}/
│   │   ├── scss/
│   │   │   ├── components/      # Component styles
│   │   │   ├── settings/        # Global settings, mixins
│   │   │   └── variables/       # Configuration variables
│   │   └── js/
│   │       └── app/
│   │           ├── components/  # PageComponents
│   │           ├── modules/     # AppModules
│   │           ├── views/       # Chaplin Views
│   │           └── models/      # Backbone Models/Collections
│   └── templates/              # JS templates (Underscore.js)
├── views/
│   └── layouts/
│       └── {theme-name}/
│           ├── config/
│           │   ├── jsmodules.yml  # JS module registration
│           │   └── assets.yml     # CSS/JS asset registration
│           └── templates/         # Twig block themes
```

### Key Concepts

1. **PageComponent**: Controller-like component attached to DOM elements via `data-page-component-*` attributes
2. **AppModule**: Initialization code that runs before application starts, registers mediator handlers
3. **Layout Block**: Server-side rendered content block defined in YAML and rendered with Twig
4. **Theme**: Collection of styles, templates, and assets that can inherit from parent themes

---

## Usage by Agents

Each file in this knowledge base follows a consistent format:
- **Summary**: What this feature/concept does and why it exists
- **Configuration**: How to configure with annotated examples
- **Best Practices**: Recommended patterns
- **Common Pitfalls**: What to avoid
- **Examples**: Real-world usage patterns from vendor code

---

## Related Resources

- [Oro Frontend Documentation](https://doc.oroinc.com/frontend/)
- [Oro Frontend Stylebook](https://doc.oroinc.com/frontend/storefront/css/frontend-stylebook/)
- [Backbone.js Documentation](https://backbonejs.org/)
- [Chaplin.js Documentation](http://docs.chaplinjs.org/)
- [Twig Documentation](https://twig.symfony.com/)