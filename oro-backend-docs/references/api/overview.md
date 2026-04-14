# OroCommerce API — Overview

> Source: https://doc.oroinc.com/master/backend/api/

## AGENT QUERY HINTS

Use this file when asked:
- "How does the Oro REST API work?"
- "What is JSON:API in OroCommerce?"
- "How is API auto-generated from entities?"
- "What are actions, processors, filters in the API layer?"
- "What is the API resource lifecycle?"
- "What endpoint does the API use?"
- "How do I enable the API for my entity?"
- "What are the available API actions?"
- "How do I debug API processors?"

---

## What Is the OroCommerce API Layer?

OroCommerce provides a **fully auto-generated REST API** built on top of the **JSON:API specification** (http://jsonapi.org/format/). Developers define entity exposure through YAML configuration files (`api.yml`), and the framework handles routing, serialization, validation, security, and documentation automatically.

The API is NOT hand-coded endpoint by endpoint. Instead:
1. You configure an entity in `api.yml`
2. The framework registers routes, generates documentation, and applies a processor chain
3. CRUD operations are immediately available

Interactive API documentation and a sandbox are accessible at `/api/doc`.

---

## Core Architecture Components

The API framework is built on three foundational pillars:

| Component | Role |
|-----------|------|
| **ChainProcessor** | Organizes data processing into sequential, prioritized steps (the processor pipeline) |
| **EntitySerializer** | Efficiently reads entity data and serializes it to arrays for JSON output |
| **Symfony Form** | Maps incoming request data onto entities during create/update operations |

Additional infrastructure:
- **FOSRestBundle** — HTTP layer, routing, and REST conventions
- **NelmioApiDocBundle** — Auto-generates `/api/doc` documentation from configuration

---

## API Types and Formats

### Primary: JSON:API REST API
- Conforms to the JSON:API specification
- Base URL prefix: `/api/`
- All requests/responses use `Content-Type: application/vnd.api+json`
- Supports CRUD operations on ORM entities
- Supports filtering, sorting, pagination, sparse fieldsets, and relationship inclusion

### Storefront API
- Separate API for customer-facing operations
- Different security context (customer users vs. admin users)

### Back-office API
- Default API target in most documentation
- Secured by stateless firewall with token-based authentication

---

## What Is Accessible by Default?

By default, the API exposes **only**:
- Custom entities (created via Oro's entity manager)
- Dictionary entities
- Enumeration entities

All other platform entities (Users, Orders, Products, etc.) require explicit opt-in via `api.yml` configuration. This prevents accidental exposure of sensitive data.

---

## API Resource Lifecycle (How a Request Is Processed)

Every API request passes through a **processor chain** — a series of small, single-responsibility processors organized into named groups. Each action (get, create, update, etc.) has its own chain.

### Processor Group Order for Data-Reading Actions (get, get_list)

```
initialize
    → Sets up context, prepares documentation
resource_check
    → Confirms the entity/resource exists and is accessible
normalize_input
    → Parses and normalizes request parameters (filters, pagination, etc.)
security_check
    → Verifies user has permission (VIEW, EDIT, DELETE, etc.)
build_query
    → Constructs the Doctrine query based on filters/sorters
load_data
    → Executes query and loads entity data
data_security_check
    → Validates data-level access (row-level security)
normalize_data
    → Converts entity objects to arrays (serialization)
finalize
    → Sets response headers
normalize_result
    → Builds the final JSON:API response (runs even on errors)
```

### Processor Group Order for Data-Writing Actions (create, update, delete)

```
initialize → resource_check → normalize_input → security_check
    → load_data (loads existing entity or creates new)
    → data_security_check
    → transform_data
        → Submits data through Symfony Form
        → Validates entity
    → save_data
        → Flushes to database
    → normalize_data → finalize → normalize_result
```

**Key insight**: `normalize_result` always executes, even if a previous processor throws an exception. This ensures error responses are always properly formatted.

---

## Available API Actions

OroCommerce API supports 17 public actions:

### Data Retrieval
| Action | HTTP Method | URL Pattern |
|--------|-------------|-------------|
| `get` | GET | `/api/{entity}/{id}` |
| `get_list` | GET | `/api/{entity}` |
| `get_subresource` | GET | `/api/{entity}/{id}/{association}` |
| `get_relationship` | GET | `/api/{entity}/{id}/relationships/{association}` |

### Data Modification
| Action | HTTP Method | URL Pattern |
|--------|-------------|-------------|
| `create` | POST | `/api/{entity}` |
| `update` | PATCH | `/api/{entity}/{id}` |
| `update_list` | PATCH | `/api/{entity}` (async batch) |
| `delete` | DELETE | `/api/{entity}/{id}` |
| `delete_list` | DELETE | `/api/{entity}` (filters required) |

### Relationship Management
| Action | HTTP Method | Description |
|--------|-------------|-------------|
| `update_relationship` | PATCH | Replace to-one or to-many members |
| `add_relationship` | POST | Add to a to-many relationship |
| `delete_relationship` | DELETE | Remove from a to-many relationship |
| `update_subresource` | PATCH | Modify related entities |
| `add_subresource` | POST | Connect entities to an association |
| `delete_subresource` | DELETE | Disconnect entities from an association |

### Utility
| Action | HTTP Method | Description |
|--------|-------------|-------------|
| `options` | OPTIONS | CORS preflight and allowed methods |

### Important Constraints
- `delete_list` **requires at least one filter** — prevents accidental bulk deletion
- `update_list` is **asynchronous** — returns an operation ID, not the final result
- `update_list` defaults to a max of 100 entities per request

---

## Auxiliary Actions (Customization Hooks)

These internal actions are not HTTP endpoints — they are processor chains used for extending behavior:

| Auxiliary Action | When It Runs | Purpose |
|------------------|--------------|---------|
| `customize_loaded_data` | After data is loaded from DB | Add computed fields, transform data |
| `customize_form_data` | During form processing | Validate or modify submitted data |
| `get_config` | Config resolution | Retrieve entity configuration |
| `get_metadata` | Metadata resolution | Obtain entity metadata |
| `normalize_value` | Value conversion | Convert values to specified types |
| `collect_resources` | Resource listing | List all API-accessible resources |
| `collect_subresources` | Subresource listing | List subresources for an entity |
| `batch_update` | Batch processing | Manage batch operations |
| `batch_update_item` | Per-item in batch | Process individual batch items |

### customize_loaded_data Events
Used for computed fields and data transformations after DB load.

### customize_form_data Events
Dispatches events in this order during write operations:
1. `pre_submit` — Before form data binding
2. `submit` — During form data binding
3. `post_submit` — After form data binding
4. `pre_validate` — Before validation
5. `post_validate` — After validation
6. `pre_flush_data` — Before DB flush
7. `post_flush_data` — After DB flush
8. `post_save_data` — After full save
9. `rollback_validated_request` — When `enable_validation: true` is set (validate-only mode)

---

## Key Concepts

### Processors
Small PHP classes implementing `ProcessorInterface`. Each processor handles one specific step. They are registered via service tags with `name: oro.api.processor`. Processors are the primary extension mechanism.

### Filters
Query parameter handlers. Filters are auto-enabled for indexed database fields. Additional filter operators or custom filters require explicit configuration in `api.yml`.

### Sorters
Control which fields can be used in `sort` query parameters. Auto-enabled for indexed fields; others need explicit configuration.

### Post-Processors
Applied after serialization to transform field values in responses (e.g., formatting, type conversion).

### Request Types
Tag-based conditions on processors. Common types:
- `rest` — Any REST request
- `json_api` — JSON:API formatted request
- `rest&json_api` — Both conditions must match (logical AND)
- Custom types can be registered (e.g., `erp` for a custom integration)

### Entity Aliases
Control how entity class names appear in URLs and JSON:API type fields. Example: `Acme\Bundle\DemoBundle\Entity\Product` → `products`.

---

## Security Model

### Default ACL Permissions by Action

| Action | Required Permissions |
|--------|---------------------|
| `get`, `get_list` | VIEW |
| `create` | CREATE + VIEW |
| `update` | EDIT + VIEW |
| `delete`, `delete_list` | DELETE |

ACL can be customized per action or disabled entirely (set `acl_resource: ~`).

### Authentication
- Stateless security firewalls (token-based)
- Feature-dependent authenticators
- CORS configuration supported

---

## Helper/Provider Classes

| Class | Purpose |
|-------|---------|
| `ConfigProvider` | Retrieve entity API configuration at runtime |
| `MetadataProvider` | Obtain entity metadata (fields, associations) |
| `ValueNormalizer` | Convert input values to correct types |
| `ResourcesProvider` | List all API-accessible resources |
| `SubresourcesProvider` | List subresources for a specific entity |
| `DoctrineHelper` | Utilities for Doctrine ORM checks (e.g., `isManageableEntityClass()`) |

---

## Useful CLI Commands

```bash
# Clear API configuration cache (run after api.yml changes)
php bin/console oro:api:cache:clear

# Clear API documentation cache
php bin/console oro:api:doc:cache:clear

# View all processors for a specific action with their priorities
php bin/console oro:api:debug {action_name}
# Example:
php bin/console oro:api:debug get

# Dump the full api.yml configuration reference
php bin/console oro:api:config:dump-reference --max-nesting-level=0

# Dump final resolved configuration for a specific entity
php bin/console oro:api:config:dump 'Acme\Bundle\DemoBundle\Entity\Product'

# Check which entities support upsert
php bin/console oro:api:dump --upsert

# Check which entities support validate operation
php bin/console oro:api:dump --validate
```

---

## Auto-Generation Flow Summary

```
1. Developer creates api.yml
       ↓
2. Framework reads and merges all bundle api.yml files
       ↓
3. Entity configuration is resolved (inheritance, merging)
       ↓
4. Routes are auto-registered for all enabled actions
       ↓
5. API documentation is generated at /api/doc
       ↓
6. On each HTTP request → processor chain executes
       ↓
7. JSON:API response returned
```

---

## Multi-Website / Multi-Scope Considerations

OroCommerce supports 4 localized websites (BR, MX, US, EU). The API respects website scope. Custom API types (e.g., `erp`) can be registered as separate API views with different configurations, accessed via custom HTTP headers.

---

## WHY: Design Rationale

**WHY processors instead of one big controller?**
Each processor has a single responsibility, making the pipeline testable, replaceable, and extensible. You can inject behavior at any stage without modifying core code.

**WHY JSON:API?**
JSON:API provides standardized conventions for filtering, sorting, pagination, sparse fieldsets, and relationship inclusion — eliminating bespoke API design decisions.

**WHY auto-generate from config?**
Prevents the N-endpoint problem where every entity needs hand-coded controllers. Configuration-driven exposure scales to hundreds of entities with minimal code.
