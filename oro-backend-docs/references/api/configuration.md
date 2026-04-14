# OroCommerce API — Configuration Reference (api.yml)

> Source: https://doc.oroinc.com/master/backend/api/configuration/

## AGENT QUERY HINTS

Use this file when asked:
- "How do I configure an entity for the API?"
- "How do I exclude a field from the API?"
- "How do I rename a field in the API response?"
- "How do I configure filters for an API entity?"
- "How do I disable an API action (delete, create, etc.)?"
- "How do I set ACL permissions for an API action?"
- "How do I configure subresources?"
- "What is exclusion_policy: all?"
- "How do I configure nested objects in the API?"
- "How do I limit results returned by the API?"
- "How do I configure form options for API create/update?"
- "What data_type values are available for API fields?"
- "How do I configure sorting in the API?"
- "How do I set a custom identifier for an entity?"

---

## Configuration File Location

All API configuration lives in:
```
src/{Vendor}/Bundle/{Name}Bundle/Resources/config/oro/api.yml
```

Multiple bundles can configure the same entity — configurations are **merged automatically**. Bundle-order determines merge priority.

After changing `api.yml`, clear the API cache:
```bash
php bin/console oro:api:cache:clear
```

---

## Top-Level Structure

```yaml
api:
    entity_aliases:     # Override URL slugs and JSON:API type names
        ...
    entities:           # Main entity configuration
        ...
```

---

## Section 1: entity_aliases

Controls how entity class names appear in API URLs and JSON:API `type` fields.

### Basic Alias Override
```yaml
api:
    entity_aliases:
        Acme\Bundle\DemoBundle\Entity\SomeEntity:
            alias: acmeentity          # Singular: used in /api/acmeentity/{id}
            plural_alias: acmeentities # Plural: used in /api/acmeentities
```

### Override Entity with an API Model
Use when you want to expose a model class (e.g., a DTO) instead of the real ORM entity.
The model class **must be a subclass** of the overridden entity.

```yaml
api:
    entity_aliases:
        Acme\Bundle\DemoBundle\Api\Model\SomeModel:
            alias: acmeentity
            plural_alias: acmeentities
            override_class: Acme\Bundle\DemoBundle\Entity\SomeEntity
```

---

## Section 2: entities

The primary section. Each key is a fully-qualified entity class name.

### Minimal: Enable an Entity with Defaults
```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product: ~
```
The tilde (`~`) means "use all defaults." This enables all standard actions (get, get_list, create, update, delete) with default ACL.

### Full Entity-Level Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `exclude` | boolean | false | Remove entity from API entirely |
| `inherit` | boolean | true | Merge config with parent entity class config |
| `exclusion_policy` | string | `none` | `none` = include all fields; `all` = exclude all, whitelist manually; `custom_fields` = exclude extended fields |
| `max_results` | integer | system default | Maximum entities returned. `-1` = unlimited |
| `order_by` | array | none | Default sort order. Key = field, value = `ASC` or `DESC` |
| `disable_inclusion` | boolean | false | Disable `?include=` query parameter |
| `disable_fieldset` | boolean | false | Disable sparse fieldsets (`?fields[]=`) |
| `disable_partial_load` | boolean | false | Disable Doctrine partial object loading |
| `enable_validation` | boolean | false | Enable validate-only mode (no DB write) |
| `hints` | array | none | Doctrine query hints |
| `form_type` | string | none | Custom Symfony form class for create/update |
| `form_options` | array | none | Options passed to the form |
| `form_event_subscriber` | string/array | none | Symfony form event subscriber service ID(s) |
| `identifier_field_names` | string[] | entity PK | Fields used as the API identifier |
| `identifier_description` | string | none | Documentation for the identifier field |
| `documentation_resource` | string | none | Path to a Markdown doc file (`@BundleName/path/file.md`) |
| `upsert` | boolean/array | system default | Configure upsert (update-or-insert) behavior |

### Entity Configuration Example (Annotated)

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            # Documentation: load from Markdown file
            documentation_resource: '@AcmeDemoBundle/Resources/doc/api/product.md'

            # Only expose fields explicitly listed (whitelist mode)
            exclusion_policy: all

            # Cap results to 25 per request in get_list
            max_results: 25

            # Default sort: newest first
            order_by:
                createdAt: DESC

            # Prevent clients from loading related entities inline
            disable_inclusion: false

            # Add Doctrine translatable hint
            hints:
                - HINT_TRANSLATABLE
                - { name: HINT_FILTER_BY_CURRENT_USER }

            # Use custom UUID as API identifier instead of numeric PK
            identifier_field_names: ['uuid']
            identifier_description: 'UUID of the product'

            fields:
                ...
            filters:
                ...
            sorters:
                ...
            actions:
                ...
```

---

## Section 3: fields

Configure how individual entity fields appear in the API.

### Field-Level Properties

| Property | Type | Description |
|----------|------|-------------|
| `exclude` | boolean | Remove field from API response and input |
| `description` | string | Documentation string for this field |
| `property_path` | string | Dot-notation path to actual data. Use `_` for computed/virtual fields |
| `collapse` | boolean | Return related entity as scalar value, not nested object |
| `form_type` | string | Custom Symfony form type for this field |
| `form_options` | array | Form field options (constraints, etc.) |
| `data_type` | string | Enforced data type (see Data Types table below) |
| `meta_property` | boolean | Place field in JSON:API `meta` section instead of `attributes` |
| `target_class` | string | For virtual associations: the related entity class |
| `target_type` | string | `to-one` or `to-many` (for virtual associations) |
| `depends_on` | string[] | Fields that must be loaded for a computed field |
| `post_processor` | string | Service ID of a post-processor to transform the value |

### Field Examples

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            fields:
                # Exclude a field entirely from API
                internalNotes:
                    exclude: true

                # Rename: expose 'firstName' as 'name' in the API
                name:
                    property_path: firstName
                    description: "The product display name"

                # Access nested object property via dot notation
                countryName:
                    property_path: address.country.name

                # Computed/virtual field (no real property path)
                # The value must be filled by a customize_loaded_data processor
                currentPrice:
                    data_type: money
                    property_path: _
                    depends_on: [priceList, currency]

                # Virtual to-one association (not a real ORM association)
                mainCategory:
                    data_type: integer
                    target_class: Acme\Bundle\DemoBundle\Entity\Category
                    target_type: to-one

                # Virtual to-many association
                relatedProducts:
                    data_type: integer
                    target_class: Acme\Bundle\DemoBundle\Entity\Product
                    target_type: to-many

                # Place in JSON:API meta section
                apiVersion:
                    data_type: string
                    meta_property: true

                # Apply validation constraint directly in config
                sku:
                    form_options:
                        constraints:
                            - NotBlank: ~
                            - Length: { max: 255 }
```

### Data Types Reference

#### Standard Types
| Type | Description |
|------|-------------|
| `string` | String value |
| `boolean` | True/false |
| `integer` | Integer number |
| `float` | Floating point |
| `decimal` | Decimal number |
| `money` | Monetary value |
| `percent` | Percentage (0.0–1.0) |
| `percent_100` | Percentage × 100 (0–100) |
| `date` | Date only (YYYY-MM-DD) |
| `datetime` | Date and time (ISO 8601) |
| `time` | Time only |
| `guid` | UUID/GUID string |

#### Array/Object Types
| Type | Description |
|------|-------------|
| `array` | Array data, or expose a to-many as an attribute |
| `object` | Associative array or object in attributes |
| `objects` | Alias for `object[]` |
| `strings` | Alias for `string[]` |
| `scalar` | Treat a to-one association as a scalar attribute |
| `data-type[]` | Array of any standard type (e.g., `integer[]`) |

#### Special/Extended Types
| Type | Description |
|------|-------------|
| `nestedObject` | Group multiple fields into a nested object in the response |
| `nestedAssociation` | Expose a two-field polymorphic reference as a relationship |
| `unidirectionalAssociation:fieldName` | Expose inverse side of unidirectional ORM association |
| `association:manyToOne` | Extended many-to-one association |
| `association:manyToMany` | Extended many-to-many association |
| `association:multipleManyToOne` | Extended multiple many-to-one association |
| `association:relationType:kind` | Custom association type with kind qualifier |

---

## Section 4: filters

Configure which fields support filtering in `GET /api/{entity}?filter[field]=value`.

### Filters Structure

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            filters:
                exclusion_policy: none  # 'none' or 'all'
                fields:
                    fieldName:
                        exclude: true/false
                        description: "Documentation"
                        property_path: someOtherProperty
                        data_type: string
                        allow_array: true     # Allow multiple values: ?filter[field][]=a&filter[field][]=b
                        allow_range: true     # Allow range: ?filter[field][from]=1&filter[field][to]=10
                        collection: true      # For collection-valued associations
                        type: customFilter    # Custom filter type name
                        options: {}           # Custom options for the filter
                        operators: ['=', '!=', '~', '^', '$', '*', '!*']
```

### Filter Properties

| Property | Type | Description |
|----------|------|-------------|
| `exclude` | boolean | Disable filtering on this field |
| `description` | string | Documentation |
| `property_path` | string | Dot-notation path to the filtered property |
| `data_type` | string | Value type for the filter |
| `allow_array` | boolean | Accept multiple filter values |
| `allow_range` | boolean | Accept `from`/`to` range values |
| `collection` | boolean | For collection-valued associations |
| `type` | string | Custom filter type name |
| `options` | array | Additional options for the filter implementation |
| `operators` | string[] | Allowed operators (see table below) |

### Filter Operators Reference

| Operator | Meaning | SQL Equivalent |
|----------|---------|----------------|
| `=` | Equal | `= value` |
| `!=` | Not equal | `!= value` |
| `<` | Less than | `< value` |
| `<=` | Less than or equal | `<= value` |
| `>` | Greater than | `> value` |
| `>=` | Greater than or equal | `>= value` |
| `*` | Exists (not null) | `IS NOT NULL` |
| `!*` | Not exists (null) | `IS NULL` |
| `~` | Contains | `LIKE '%value%'` |
| `!~` | Not contains | `NOT LIKE '%value%'` |
| `^` | Starts with | `LIKE 'value%'` |
| `!^` | Not starts with | `NOT LIKE 'value%'` |
| `$` | Ends with | `LIKE '%value'` |
| `!$` | Not ends with | `NOT LIKE '%value'` |
| `empty` | Empty or null | `IS NULL OR = ''` |

**Performance warning:** `~`, `^`, `$` operators use `LIKE` with wildcards, which may be slow on large tables. Use database indexes where possible.

### Filter Examples

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            filters:
                fields:
                    # Enable all string search operators
                    name:
                        operators: ['=', '!=', '*', '!*', '~', '!~', '^', '!^', '$', '!$', 'empty']

                    # Date range filter
                    createdAt:
                        data_type: datetime
                        allow_range: true

                    # Multiple value filter (IN clause)
                    status:
                        data_type: string
                        allow_array: true

                    # Case-insensitive filter
                    email:
                        options:
                            case_insensitive: true

                    # Disable a filter that was auto-enabled
                    internalCode:
                        exclude: true

                    # Custom filter type
                    searchQuery:
                        data_type: string
                        type: searchQueryFilter
                        operators: ['=']
                        property_path: _
```

---

## Section 5: sorters

Configure which fields support the `?sort=field,-otherField` query parameter.

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            sorters:
                exclusion_policy: none   # 'none' or 'all'
                fields:
                    name:
                        property_path: firstName   # Sort on underlying property
                    internalCode:
                        exclude: true              # Disable sorting on this field
```

### Sorter Properties

| Property | Type | Description |
|----------|------|-------------|
| `exclude` | boolean | Disable sorting on this field |
| `property_path` | string | Dot-notation path to the sortable property |

**Note:** Sorters on indexed database fields are auto-enabled. Non-indexed fields require explicit configuration.

---

## Section 6: actions

Control which HTTP operations are available and configure per-action behavior.

### Disable All Actions
```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\SomeEntity:
            actions: false
```

### Disable a Specific Action
```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\SomeEntity:
            actions:
                delete: false        # Short form
                # OR
                delete:
                    exclude: true    # Long form
```

### Action Properties

| Property | Type | Description |
|----------|------|-------------|
| `exclude` | boolean | Disable this action |
| `description` | string | Short documentation (appears in API docs) |
| `documentation` | string | Detailed documentation |
| `acl_resource` | string | ACL permission name. Set to `~` to disable ACL check |
| `max_results` | integer | Entity limit per request (`-1` = unlimited) |
| `page_size` | integer | Default page size (`-1` = disable pagination) |
| `disable_paging` | boolean | Disable pagination for this action |
| `disable_sorting` | boolean | Disable sorting for this action |
| `disable_inclusion` | boolean | Disable `?include=` for this action |
| `disable_fieldset` | boolean | Disable sparse fieldsets for this action |
| `form_type` | string | Custom form class (overrides entity-level) |
| `form_options` | array | Custom form options |
| `form_event_subscriber` | string/array | Event subscriber service ID(s) |
| `status_codes` | array | Document expected HTTP response codes |
| `fields` | array | Field-level overrides for this action only |
| `order_by` | array | Default sort order for this action |

### Default ACL Permissions

| Action | Required ACL Permission |
|--------|------------------------|
| `get` | VIEW |
| `get_list` | VIEW |
| `create` | CREATE + VIEW |
| `update` | EDIT + VIEW |
| `delete` | DELETE |
| `delete_list` | DELETE |

### Action Configuration Examples

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            actions:
                # Disable delete entirely
                delete:
                    exclude: true

                # Custom ACL resource for get_list
                get_list:
                    acl_resource: product_view_permission
                    max_results: 50
                    page_size: 20
                    order_by:
                        name: ASC

                # Disable ACL check for get (public access)
                get:
                    acl_resource: ~

                # Document custom error codes
                create:
                    status_codes:
                        201:
                            description: Created successfully
                        400:
                            description: Validation failed

                # Update: exclude a field for input only
                update:
                    fields:
                        sku:
                            exclude: true        # Can't change SKU via update
                        createdAt:
                            direction: output    # Read-only field (output only)

                # delete_list: extend max deletable entities
                delete_list:
                    max_results: 200
```

### Field Direction for Actions

Within `actions[action].fields`, you can control field visibility:
- `exclude: true` — Field not available in this action at all
- `direction: input` — Field accepted in requests but not returned in response
- `direction: output` — Field returned in response but not accepted in requests
- `direction: input-only` — Alias for `direction: input`

---

## Section 7: subresources

Configure access to related entities via URLs like `/api/products/1/category`.

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            subresources:
                category:
                    target_class: Acme\Bundle\DemoBundle\Entity\Category
                    target_type: to-one
                    actions:
                        get_subresource:
                            description: "Get the product category"
                        get_relationship: false
                        update_relationship: false

                relatedProducts:
                    target_class: Acme\Bundle\DemoBundle\Entity\Product
                    target_type: to-many
                    actions:
                        get_subresource: ~
                        get_relationship: ~
                        update_relationship: false
                    filters:
                        fields:
                            status:
                                data_type: string
                                operators: ['=']
                    sorters:
                        fields:
                            name: ~
```

### Subresource Properties

| Property | Type | Description |
|----------|------|-------------|
| `exclude` | boolean | Disable this subresource entirely |
| `target_class` | string | Fully-qualified class of the related entity |
| `target_type` | string | `to-one` or `to-many` (collection) |
| `actions` | array | Configure available subresource actions |
| `filters` | array | Filter configuration for this subresource |
| `sorters` | array | Sorter configuration for this subresource |

### Subresource-Specific Actions

| Action | Description |
|--------|-------------|
| `get_subresource` | `GET /api/{entity}/{id}/{association}` — Returns related entity data |
| `get_relationship` | `GET /api/{entity}/{id}/relationships/{association}` — Returns IDs only |
| `update_relationship` | `PATCH /api/{entity}/{id}/relationships/{association}` |
| `add_relationship` | `POST /api/{entity}/{id}/relationships/{association}` |
| `delete_relationship` | `DELETE /api/{entity}/{id}/relationships/{association}` |

**Important:** The target entity must itself be API-accessible (have its own API configuration).

---

## Section 8: exclude Option (Multi-Level)

`exclude` works at all configuration levels:

```yaml
api:
    entities:
        # Entity-level: remove entire entity from API
        Acme\Bundle\DemoBundle\Entity\SomeEntity:
            exclude: true

        Acme\Bundle\DemoBundle\Entity\Product:
            fields:
                # Field-level: hide this field from responses and requests
                internalCode:
                    exclude: true

            filters:
                fields:
                    # Filter-level: prevent filtering on this field
                    secretScore:
                        exclude: true

            sorters:
                fields:
                    # Sorter-level: prevent sorting on this field
                    secretScore:
                        exclude: true
```

### Overriding entity.yml Global Exclusions

If an entity or field is excluded globally in `entity.yml`, you can re-enable it for API:

```yaml
# In entity.yml (global exclusion)
oro_entity:
    exclusions:
        - { entity: Acme\Bundle\DemoBundle\Entity\SomeEntity1 }
        - { entity: Acme\Bundle\DemoBundle\Entity\SomeEntity2, field: field1 }

# In api.yml (override for API only)
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\SomeEntity1:
            exclude: false    # Re-enable for API
        Acme\Bundle\DemoBundle\Entity\SomeEntity2:
            fields:
                field1:
                    exclude: false    # Re-enable field for API
```

---

## Complete Annotated Example

The following is a comprehensive example showing most configuration options together:

```yaml
api:
    # --- Alias Override ---
    entity_aliases:
        Acme\Bundle\DemoBundle\Entity\Product:
            alias: product
            plural_alias: products

    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            # Link to Markdown documentation file
            documentation_resource: '@AcmeDemoBundle/Resources/doc/api/product.md'

            # Whitelist mode: only explicitly configured fields are exposed
            exclusion_policy: all

            # Maximum 100 results in get_list
            max_results: 100

            # Default sort order
            order_by:
                name: ASC

            # Use UUID instead of numeric ID
            identifier_field_names: ['uuid']
            identifier_description: 'The UUID of the product'

            # --- Fields ---
            fields:
                # Expose uuid (it's excluded by exclusion_policy: all)
                uuid:
                    data_type: guid
                    description: "Unique identifier"

                # Expose name
                name:
                    data_type: string
                    description: "Product name"
                    form_options:
                        constraints:
                            - NotBlank: ~

                # Expose price as a computed/virtual field
                currentPrice:
                    data_type: money
                    description: "Current price for active price list"
                    property_path: _           # Virtual: filled by processor
                    depends_on: [priceList]    # Requires priceList to be loaded

                # Nested object: group intervalNumber + intervalUnit
                renewalInterval:
                    data_type: nestedObject
                    form_options:
                        inherit_data: true
                    fields:
                        number:
                            property_path: intervalNumber
                        unit:
                            property_path: intervalUnit

                # Exclude the raw fields that are merged into renewalInterval
                intervalNumber:
                    exclude: true
                intervalUnit:
                    exclude: true

                # Relationship
                category:
                    description: "Primary category"

            # --- Filters ---
            filters:
                fields:
                    name:
                        operators: ['=', '!=', '~', '^', '$', '*', '!*']
                    status:
                        data_type: string
                        allow_array: true
                    createdAt:
                        data_type: datetime
                        allow_range: true
                    internalCode:
                        exclude: true    # Not filterable

            # --- Sorters ---
            sorters:
                exclusion_policy: all    # Only sort on explicitly listed fields
                fields:
                    name: ~
                    createdAt: ~

            # --- Actions ---
            actions:
                get:
                    description: "Retrieve a single product"

                get_list:
                    description: "Retrieve product list"
                    page_size: 25
                    max_results: 500

                create:
                    description: "Create a new product"
                    acl_resource: acme_product_create
                    form_options:
                        validation_groups: ['Default', 'api_create']

                update:
                    description: "Update a product"
                    fields:
                        uuid:
                            exclude: true    # UUID cannot be changed after creation

                delete:
                    exclude: true    # Products cannot be deleted via API

                delete_list:
                    exclude: true

            # --- Subresources ---
            subresources:
                category:
                    target_class: Acme\Bundle\DemoBundle\Entity\Category
                    target_type: to-one
                    actions:
                        get_subresource: ~
                        get_relationship: ~
                        update_relationship:
                            acl_resource: acme_product_manage_category
                        add_relationship: false
                        delete_relationship: false

                images:
                    target_class: Acme\Bundle\DemoBundle\Entity\ProductImage
                    target_type: to-many
                    actions:
                        get_subresource: ~
                        get_relationship: ~
                        update_relationship: ~
                        add_relationship: ~
                        delete_relationship: ~
```

---

## Configuration for Non-ORM Entities (API Models)

To expose a plain PHP class (e.g., for a registration endpoint with no persistent entity):

```yaml
api:
    entity_aliases:
        Acme\Bundle\DemoBundle\Api\Model\RegistrationRequest:
            alias: registeraccount
            plural_alias: registeraccount    # Same as alias for non-collection resources

    entities:
        Acme\Bundle\DemoBundle\Api\Model\RegistrationRequest:
            fields:
                name:
                    data_type: string
                    form_options:
                        constraints:
                            - NotBlank: ~
                email:
                    data_type: string
                    form_options:
                        constraints:
                            - NotBlank: ~
                            - Email: ~
            actions:
                create:
                    description: "Register a new account"
                get: false
                update: false
                delete: false
                get_list: false
```

---

## Upsert Configuration

Upsert allows create-or-update based on a unique field instead of the entity ID.

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            # Disable upsert
            upsert: false

            # Enable upsert with specific field sets
            upsert:
                add: [['sku'], ['name', 'category']]    # Add these identifier sets

            # Remove specific identifier sets from upsert
            upsert:
                remove: [['legacyCode']]

            # Replace all upsert identifiers
            upsert:
                replace: [['sku']]
```

---

## Validation Configuration

Enable validate-only mode (no DB write, just validation feedback):

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            enable_validation: true
```

When enabled, `rollback_validated_request` event fires instead of `post_flush_data`. Avoid side effects (emails, indexing) in processors that listen to `post_flush_data` for validated requests.

---

## Global Entity Exclusions (entity.yml vs api.yml)

The `entity.yml` file at `Resources/config/oro/entity.yml` sets global exclusions across the application. These are respected by the API unless explicitly overridden in `api.yml`:

```yaml
# entity.yml
oro_entity:
    exclusions:
        - { entity: Acme\Bundle\DemoBundle\Entity\InternalLog }
        - { entity: Acme\Bundle\DemoBundle\Entity\Product, field: costPrice }
```

---

## WHY: Configuration Design Rationale

**WHY `exclusion_policy: all`?**
Forces you to consciously whitelist every exposed field. This is the safer default for sensitive entities — you can't accidentally expose a new database column by upgrading the platform.

**WHY `property_path: _`?**
Signals that this field has no backing entity property. It must be filled by a `customize_loaded_data` processor. The underscore is a convention for virtual/computed fields.

**WHY configure filters separately from fields?**
Filtering is a query-layer concern. Configuring it separately allows fine-grained control: a field may be in the response but not filterable, or filterable but not in the response.

**WHY `depends_on` for computed fields?**
Tells the serializer to always load the listed properties, even if the client doesn't request them (e.g., via sparse fieldsets). Without this, the data needed to compute the virtual field might not be loaded.
