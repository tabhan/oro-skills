# OroCommerce: Bundle-less Structure

> Source: https://doc.oroinc.com/master/backend/architecture/bundle-less-structure/

---

## AGENT QUERY HINTS

This file answers questions like:
- "What is bundle-less structure in OroCommerce 7.0?"
- "How do I organize code without creating a Symfony bundle?"
- "What is the difference between bundle-based and bundle-less structure?"
- "How do I migrate an existing bundle to bundle-less structure?"
- "Where do I place entities, controllers, and configuration in bundle-less structure?"
- "When should I use bundle-less vs bundle-based structure?"
- "What configuration files are needed for bundle-less structure?"
- "How does asset handling work in bundle-less applications?"

---

## Summary

- **Optional alternative** to Symfony bundle structure for application-level code
- **Follows Symfony best practices** and lowers entry barriers for new developers
- **Flat directory structure** with application-level configuration in `config/oro/`
- **Same Oro features** available (ACLs, workflows, datagrids, API, etc.) without bundle boilerplate
- **Recommended** for individual customizations and when creating a new bundle is impractical

---

## Core Concept: WHY Bundle-less Structure Exists

Starting from OroPlatform v5.1, you can organize OroPlatform-based application code within **Symfony bundles** OR **plain directories**. The bundle-less structure follows Symfony best practices and lowers the entry level for new developers familiar with modern Symfony applications.

**WHY use bundle-less structure:**
- Less boilerplate code (no bundle class, no bundles.yml)
- Follows Symfony 5+ conventions (src/ directory for code)
- Easier for developers coming from standard Symfony applications
- Simpler for small-to-medium customizations
- Same Oro features available without bundle overhead

**WHEN to use bundle-based vs bundle-less:**

| Scenario | Recommended Approach |
|----------|---------------------|
| Reusable package for distribution | Bundle-based |
| Application-level customization | Bundle-less |
| Multiple related features with shared code | Bundle-based |
| Single feature or small extension | Bundle-less |
| Need to share code across Oro applications | Bundle-based |
| Internal project customization | Bundle-less |

---

## Application-level Structure

### Bundle-less Directory Layout

```
oro-application/
├── assets/
│   ├── your-assets-dir/           # SCSS, JS, images, fonts
│   └── ...
├── config/
│   ├── batch_jobs/                # Import/Export Configuration
│   │   └── jobs-config.yml
│   ├── doctrine.yml               # Doctrine DBAL Configuration
│   ├── oro/                       # All Oro advanced features configuration
│   │   ├── acl_categories/
│   │   │   └── acl_category_config.yml
│   │   ├── acls/
│   │   │   └── acls_config.yml
│   │   ├── api/
│   │   │   └── api_config.yml     # API configuration
│   │   ├── api_frontend/
│   │   │   └── api_frontend_config.yml
│   │   ├── cache_metadata/
│   │   ├── channels/
│   │   ├── charts/
│   │   ├── configurable_permissions/
│   │   ├── dashboards/
│   │   ├── datagrids/
│   │   │   └── datagrids_config.yml
│   │   ├── entity/
│   │   │   └── entity_config.yml
│   │   ├── entity_extend/
│   │   ├── entity_hidden_fields/
│   │   ├── features/
│   │   ├── help/
│   │   ├── locale_data/
│   │   ├── name_format/
│   │   ├── navigation/
│   │   │   └── navigation_config.yml
│   │   ├── permissions/
│   │   ├── placeholders/
│   │   │   └── placeholders_config.yml
│   │   ├── processes/
│   │   │   └── processes.yml
│   │   ├── search/
│   │   │   └── search_config.yml
│   │   ├── system_configuration/
│   │   ├── workflows/
│   │   │   ├── workflows_import/
│   │   │   └── workflows.yml
│   │   ├── assets.yml             # Admin theme assets
│   │   └── jsmodules.yml          # JS modules for admin
│   └── ...
├── src/
│   ├── Entity/                    # Doctrine entities
│   ├── Controller/                # Controllers
│   ├── Service/                   # Services
│   ├── Form/                      # Form types
│   └── Tests/                     # Application-level tests
│       ├── Behat/
│       ├── Unit/
│       └── Functional/
├── templates/                     # Twig templates
├── migrations/                    # Schema migrations and data fixtures
│   └── your_feature_name/
│       ├── Data/
│       └── Schema/
└── translations/                  # Translation files
```

---

## Migration Guide: Bundle-based → Bundle-less

### Overview

There is no automatic tool for migrating from bundle-based to bundle-less structure. You must move code following these guidelines:

### Migrations

```bash
# FROM
{BundleDir}/Migrations/Schema/

# TO
migrations/{EntityNameDir}/Schema/

# Example
Bundle/UserNamingBundle/Migrations/Schema/ → migrations/UserNaming/Schema/
```

### Data Fixtures

```bash
# FROM
{BundleDir}/Migrations/Data/

# TO
migrations/{EntityNameDir}/Data/

# Example
Bundle/UserNamingBundle/Migrations/Data/ → migrations/UserNaming/Data/
```

### Entities

```bash
# FROM
{BundleDir}/Entity/{YourEntity}.php

# TO
src/Entity/{YourEntity}.php

# Example
Bundle/UserNamingBundle/Entity/UserNamingType.php → src/Entity/UserNamingType.php
```

### Controllers

```bash
# FROM
{BundleDir}/Controller/{YourController}.php

# TO
src/Controller/{YourController}.php
```

**IMPORTANT**: Controllers must be declared as services in `config/services.yaml`:

```yaml
# config/services.yaml
App\Controller\UserNamingController:
    calls:
        - ['setContainer', ['@Psr\Container\ContainerInterface']]
    tags:
        - { name: container.service_subscriber }
```

### Templates (Views)

```bash
# FROM
{BundleDir}/Resources/views/{YourEntityName}/index.html.twig

# TO
templates/{entity_alias_underscore}/index.html.twig

# Example
Bundle/UserNamingBundle/Resources/views/UserNaming/index.html.twig → templates/user_naming/index.html.twig
```

### Translations

```bash
# FROM
{BundleDir}/Resources/translations/messages.en.yml

# TO
translations/messages.en.yml
```

### Datagrids

```bash
# FROM
{BundleDir}/Resources/config/oro/datagrids.yml

# TO
config/oro/datagrids/{name_your_feature}.yml

# Templates
{BundleDir}/Resources/views/{YourEntityName}/Datagrid/yourTemplate.html.twig
→ templates/{entity_alias_underscore}/Datagrid/yourTemplate.html.twig
```

### Search Configuration

```bash
# FROM
{BundleDir}/Resources/config/oro/search.yml

# TO
config/oro/search/{your_search_name}.yml

# Templates
{BundleDir}/Resources/views/{YourEntityName}/Search/yourTemplate.html.twig
→ templates/{entity_alias_underscore}/Search/yourTemplate.html.twig
```

### Navigation

```bash
# FROM
{BundleDir}/Resources/config/oro/navigation.yml

# TO
config/oro/navigation/{your_navigation_name}.yml
```

### Entity Configuration

```bash
# FROM
{BundleDir}/Resources/config/oro/entity.yml

# TO
config/oro/entity/{your_entity_name}.yml
```

### ACLs

```bash
# FROM
{BundleDir}/Resources/config/oro/acls.yml

# TO
config/oro/acls/{your_acls_name}.yml
```

### API Configuration

```bash
# FROM
{BundleDir}/Resources/config/oro/api.yml

# TO
config/oro/api/{your_api_name}.yml
```

**IMPORTANT**: In bundle-less structure, `documentation_resource` path must be defined as a **relative path from the App's root directory**:

```yaml
# File placed at appRoot/doc/api/frontend/user.md
api:
    entities:
        App\Entity\User:
            documentation_resource: '/doc/api/frontend/user.md'
            # ...
```

This feature is available as of OroPlatform version 6.0.3.

### Additional Configuration Migrations

| Feature | Bundle Path | Bundle-less Path |
|---------|-------------|------------------|
| Channels | `Resources/config/oro/channels.yml` | `config/oro/channels/` |
| Charts | `Resources/config/oro/charts.yml` | `config/oro/charts/` |
| Workflows | `Resources/config/oro/workflows.yml` | `config/oro/workflows/workflows.yml` |
| Processes | `Resources/config/oro/processes.yml` | `config/oro/processes/processes.yml` |
| ACL Categories | `Resources/config/oro/acl_categories.yml` | `config/oro/acl_categories/` |
| Address Format | `Resources/config/oro/address_format.yml` | `config/oro/address_format/` |
| Dashboards | `Resources/config/oro/dashboards.yml` | `config/oro/dashboards/` |
| Entity Extend | `Resources/config/oro/entity_extend.yml` | `config/oro/entity_extend/` |
| Locale Data | `Resources/config/oro/locale_data.yml` | `config/oro/locale_data/` |
| Permissions | `Resources/config/oro/permissions.yml` | `config/oro/permissions/` |
| Placeholders | `Resources/config/oro/placeholders.yml` | `config/oro/placeholders/` |
| System Configuration | `Resources/config/oro/system_configuration.yml` | `config/oro/system_configuration/` |

---

## Themes & Layouts

### Asset Handling in Application Development

In bundle-less structure, assets are stored in the `assets/` directory:

```
assets/
├── your-assets-dir/
│   ├── scss/
│   ├── js/
│   ├── images/
│   └── fonts/
└── ...
```

### Overriding SASS Variables

Create a `assets/your-assets-dir/scss/variables.scss` file to override Oro's default variables:

```scss
// assets/your-assets-dir/scss/variables.scss

// Override primary color
$primary-color: #0066cc;

// Override font family
$font-family-base: 'Open Sans', sans-serif;
```

### Referencing Assets Using the asset() Function in Twig

```twig
{# templates/your_entity/index.html.twig #}

<img src="{{ asset('bundles/yourbundle/images/logo.png') }}" alt="Logo">

{# For bundle-less #}
<img src="{{ asset('assets/your-assets-dir/images/logo.png') }}" alt="Logo">
```

### Placement of SVG Icons (Storefront)

Store SVG icons in:
```
assets/your-assets-dir/icons/
```

### JS Modules

Register JavaScript modules in `config/oro/jsmodules.yml`:

```yaml
# config/oro/jsmodules.yml

aliases:
    your-module$: ./assets/your-assets-dir/js/your-module

app-modules:
    - ./assets/your-assets-dir/js/app/modules/your-module
```

### Admin Theme Configuration

Configure admin theme assets in `config/oro/assets.yml`:

```yaml
# config/oro/assets.yml

css:
    inputs:
        - './assets/your-assets-dir/scss/main.scss'

output: '../public/css/oro.css'
```

---

## Tests

Application-level tests are placed in `src/Tests/`:

```
src/Tests/
├── Behat/           # End-to-end tests
├── Unit/            # Unit tests
└── Functional/      # Functional tests
```

Run tests with:

```bash
# Unit tests
php bin/phpunit src/Tests/Unit/

# Functional tests
php bin/phpunit src/Tests/Functional/

# Behat tests
vendor/bin/behat --suite=your_suite
```

---

## Best Practices

### DO

- ✅ Use bundle-less structure for application-level customizations
- ✅ Keep entities in `src/Entity/` following PSR-4
- ✅ Use `config/oro/` for all Oro-specific configuration
- ✅ Declare controllers as services with `container.service_subscriber` tag
- ✅ Use relative paths for `documentation_resource` in API config
- ✅ Keep migrations organized by feature in `migrations/{feature_name}/`

### DON'T

- ❌ Mix bundle-based and bundle-less structures for the same feature
- ❌ Create deep nesting in `config/oro/` subdirectories
- ❌ Forget to register controllers as services
- ❌ Use absolute paths in API `documentation_resource`
- ❌ Place entities outside `src/Entity/` (breaks Doctrine mapping)

---

## Common Pitfalls

### Controller Not Found

```yaml
# WRONG - Controller not registered as service
# (routes work but controller is not instantiated properly)

# CORRECT - Controller registered as service
App\Controller\YourController:
    calls:
        - ['setContainer', ['@Psr\Container\ContainerInterface']]
    tags:
        - { name: container.service_subscriber }
```

### API Documentation Resource Path

```yaml
# WRONG - Using bundle path (bundle-less structure)
api:
    entities:
        App\Entity\User:
            documentation_resource: '@AcmeBundle/Resources/doc/api/user.md'

# CORRECT - Using relative path from app root
api:
    entities:
        App\Entity\User:
            documentation_resource: '/doc/api/user.md'
```

### Asset Path in Twig Templates

```twig
<!-- WRONG - Bundle path in bundle-less structure -->
<link href="{{ asset('bundles/acme/css/styles.css') }}" rel="stylesheet">

<!-- CORRECT - Assets directory path -->
<link href="{{ asset('assets/your-assets-dir/css/styles.css') }}" rel="stylesheet">
```

---

## Related Resources

- [Oro Backend Architecture](https://doc.oroinc.com/master/backend/architecture/)
- [Create a Bundle](https://doc.oroinc.com/master/backend/extension/create-bundle/)
- [Application Structure](https://doc.oroinc.com/master/backend/architecture/structure/)
- [Symfony Best Practices](https://symfony.com/doc/current/best_practices.html)