# OroCommerce API — Developer Guide

> Source: https://doc.oroinc.com/master/backend/api/

## AGENT QUERY HINTS

Use this file when asked:
- "How do I expose a custom entity via the REST API?"
- "How do I write a custom API processor?"
- "How do I add a custom filter to an API endpoint?"
- "What does a complete api.yml look like?"
- "How do I test an OroCommerce API endpoint?"
- "What is the JSON:API request/response format?"
- "How do I rename or exclude fields in the API?"
- "How do I add a computed/virtual field to an API response?"
- "How do I register a processor with a specific priority?"
- "Why does processor priority matter?"
- "How do I restrict which actions are available on an entity?"

---

## Part 1: Configuring an Entity for the API (api.yml)

### Where api.yml Lives

Each bundle can declare its own `api.yml` file:

```
src/Acme/Bundle/DemoBundle/
└── Resources/
    └── config/
        └── oro/
            └── api.yml       ← entity API configuration
```

All `api.yml` files across all bundles are merged at runtime into a single resolved configuration. You can add to, override, or restrict any entity's API behavior from any bundle.

---

### Complete api.yml Example: ProductReview Entity

This example shows a realistic entity with field definitions, exclusions, renames, filters, sorters, and per-action configuration. Every option is commented with a WHY.

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/oro/api.yml

api:
    entities:
        Acme\Bundle\DemoBundle\Entity\ProductReview:

            # -------------------------------------------------------------------------
            # HUMAN-READABLE LABEL
            # Shown in /api/doc documentation. Uses translation key.
            # WHY: Makes the API documentation more discoverable for API consumers.
            # -------------------------------------------------------------------------
            label:        acme.demo.product_review.entity_label
            plural_label: acme.demo.product_review.entity_plural_label
            description:  acme.demo.product_review.api_description

            # -------------------------------------------------------------------------
            # ACTIONS
            # Restrict which HTTP operations are enabled for this entity.
            # If you omit 'actions' entirely, ALL actions are enabled by default.
            # WHY: Principle of least privilege — only expose what you intend.
            # -------------------------------------------------------------------------
            actions:
                get:          true    # GET /api/productreviews/{id}
                get_list:     true    # GET /api/productreviews
                create:       true    # POST /api/productreviews
                update:       true    # PATCH /api/productreviews/{id}
                delete:       true    # DELETE /api/productreviews/{id}
                delete_list:  false   # Disabled — bulk delete is too dangerous here
                update_list:  false   # Disabled — async batch not needed

                # Per-action ACL override.
                # WHY: Sometimes create needs a different permission than the default.
                create:
                    acl_resource: acme_product_review_create

                # Disable ACL on get_list entirely for public review browsing.
                # WARNING: Only do this for genuinely public data.
                get_list:
                    acl_resource: ~

            # -------------------------------------------------------------------------
            # FIELDS
            # Control exactly what the API exposes.
            # Fields not listed here ARE included by default (unless excluded globally).
            # -------------------------------------------------------------------------
            fields:

                # --- Simple inclusion (field name matches entity property) ---
                id:
                    description: Unique identifier of the product review.

                rating:
                    description: Star rating from 1 to 5.

                title:
                    description: Short title of the review.

                body:
                    description: Full review text submitted by the customer.

                createdAt:
                    description: ISO 8601 datetime when the review was created.

                # --- RENAME: expose internal field name under a public API name ---
                # The entity has a property called 'isApproved', but we expose it
                # as 'approved' so consumers don't need to know our internal naming.
                # WHY: Decouples the public API contract from internal PHP naming.
                approved:
                    property_path: isApproved
                    description:   Whether this review has been approved by a moderator.

                # --- EXCLUDE: hide internal fields consumers must not see ---
                # WHY: moderatorNotes is internal admin data; never expose to API.
                moderatorNotes:
                    exclude: true

                # WHY: internalScore is a raw ML score used internally; not for API.
                internalScore:
                    exclude: true

                # --- DATA TYPE OVERRIDE ---
                # Ensure the rating is serialized as an integer, not a string.
                # WHY: Without this, Doctrine may return the value as a string
                #      from the database driver.
                rating:
                    data_type: integer

                # --- RELATIONSHIP FIELD: expose the related product ---
                # 'product' is a ManyToOne relationship to OroCommerce's product entity.
                # Relationships are automatically serialized as JSON:API resource linkage.
                product:
                    description: The product this review is attached to.

                # --- RELATIONSHIP FIELD: customer user who wrote the review ---
                customerUser:
                    description: The customer user who submitted the review.

                # --- COMPUTED / VIRTUAL FIELD (no DB column) ---
                # 'helpfulCount' has no DB column; it is populated by a custom processor.
                # See Part 2 for the processor that fills this in.
                # WHY: Declaring it here tells the serializer to include it in responses.
                helpfulCount:
                    data_type:   integer
                    description: Number of users who marked this review as helpful.

            # -------------------------------------------------------------------------
            # FILTERS
            # Control which query parameters consumers can use to filter results.
            # Indexed DB columns are auto-enabled; non-indexed or custom filters
            # must be declared explicitly.
            # -------------------------------------------------------------------------
            filters:
                fields:

                    # Standard equality filter on a simple field.
                    # Consumer uses: GET /api/productreviews?filter[approved]=true
                    approved:
                        description: Filter by approval status.

                    # Range filter on rating.
                    # Consumer uses: GET /api/productreviews?filter[rating][gte]=4
                    rating:
                        description:    Filter by star rating. Supports eq, neq, gt, gte, lt, lte.
                        allow_array:    true   # Allow: filter[rating][]=4&filter[rating][]=5
                        allow_range:    true   # Allow: filter[rating][gte]=4&filter[rating][lte]=5

                    # Filter by related entity ID.
                    # Consumer uses: GET /api/productreviews?filter[product]=42
                    product:
                        description: Filter reviews for a specific product by product ID.

                    # Filter by createdAt range (date range queries).
                    createdAt:
                        description: Filter by creation date. Supports range operators.
                        allow_range: true

                    # Custom filter — see Part 3 for implementation.
                    # This filter is NOT auto-generated; it requires a custom processor.
                    # Consumer uses: GET /api/productreviews?filter[minHelpfulCount]=10
                    minHelpfulCount:
                        description:  Only return reviews with at least this many helpful votes.
                        data_type:    integer
                        type:         integer  # The filter value type passed to the processor

            # -------------------------------------------------------------------------
            # SORTERS
            # Control which fields can be used in the 'sort' query parameter.
            # Consumer uses: GET /api/productreviews?sort=-createdAt,rating
            # A leading '-' means descending order.
            # WHY: Explicit sorters prevent expensive sorts on non-indexed columns.
            # -------------------------------------------------------------------------
            sorters:
                fields:
                    createdAt:
                        description: Sort by creation date.
                    rating:
                        description: Sort by star rating.
                    approved:
                        description: Sort by approval status.

            # -------------------------------------------------------------------------
            # SUBRESOURCES
            # Define related resource sub-endpoints.
            # Consumer uses: GET /api/productreviews/42/product
            # -------------------------------------------------------------------------
            subresources:
                product:
                    actions:
                        get_subresource: true
                        get_relationship: true
                        update_relationship: false  # Reviews cannot re-link to another product
                        add_relationship: false
                        delete_relationship: false

                customerUser:
                    actions:
                        get_subresource:     true
                        get_relationship:    true
                        update_relationship: false  # Customer user is set at creation only
```

---

### Applying api.yml Changes

After modifying `api.yml`, always clear the API config cache:

```bash
# Clear API configuration cache (REQUIRED after every api.yml change)
php bin/console oro:api:cache:clear

# Also clear API documentation cache
php bin/console oro:api:doc:cache:clear

# Verify the final resolved configuration for your entity
php bin/console oro:api:config:dump 'Acme\Bundle\DemoBundle\Entity\ProductReview'
```

The `config:dump` output shows exactly what the framework will use at runtime — invaluable for debugging unexpected field exposure or missing configurations.

---

## Part 2: Writing a Custom Processor

### When to Write a Processor

Write a processor when you need to:
- Add a **computed field** to responses (virtual field not in the DB)
- Modify the **query** before it executes (e.g., add a JOIN)
- Enforce **custom business rules** during create/update
- Log, audit, or trigger side effects at a specific pipeline stage
- Apply **row-level access control** beyond the default ACL

### The Processor Pipeline (with priorities)

Processors are sorted by descending priority (higher number = runs first) within each processor group. Understanding priority is essential for inserting behavior at the right moment.

```
Action: get / get_list

Group                Priority range    Purpose
─────────────────────────────────────────────────────────────────────
initialize           -255 to 255      Context setup, parameter defaults
resource_check       -255 to 255      Verify entity/resource exists
normalize_input      -255 to 255      Parse request parameters (filters, etc.)
security_check       -255 to 255      ACL permission checks
build_query          -255 to 255      Construct Doctrine query
load_data            -255 to 255      Execute query, load entity objects
data_security_check  -255 to 255      Row-level security (filter by ownership)
normalize_data       -255 to 255      Convert entity objects → arrays
finalize             -255 to 255      Set response headers
normalize_result     -255 to 255      Build final JSON:API response structure
```

**For computed fields: target the `customize_loaded_data` auxiliary action**, not `normalize_data`. This auxiliary action runs specifically for post-load data transformation and avoids interfering with core serialization.

**Priority rule of thumb:**
- Use priority `0` (default) unless you need to run before or after a specific core processor
- Use positive priority (e.g., `10`) to run BEFORE the default processors in that group
- Use negative priority (e.g., `-10`) to run AFTER the default processors

```bash
# See all registered processors and their priorities for an action
php bin/console oro:api:debug get
php bin/console oro:api:debug customize_loaded_data
```

---

### Example: Processor That Adds a Computed Field (helpfulCount)

This processor populates the `helpfulCount` virtual field declared in `api.yml`.

**PHP class:**

```php
<?php
// src/Acme/Bundle/DemoBundle/Api/Processor/AddHelpfulCountToProductReview.php

namespace Acme\Bundle\DemoBundle\Api\Processor;

use Acme\Bundle\DemoBundle\Repository\HelpfulVoteRepository;
use Oro\Bundle\ApiBundle\Processor\CustomizeLoadedData\CustomizeLoadedDataContext;
use Oro\Component\ChainProcessor\ContextInterface;
use Oro\Component\ChainProcessor\ProcessorInterface;

/**
 * Adds the 'helpfulCount' computed field to ProductReview API responses.
 *
 * WHY this processor exists:
 * - 'helpfulCount' has no DB column on the ProductReview entity.
 * - It is calculated from a separate HelpfulVote table.
 * - The API framework cannot auto-serialize a field that does not exist as a
 *   property on the entity; a processor must inject the value after DB load.
 *
 * WHY customize_loaded_data:
 * - This auxiliary action runs after entities are loaded from the DB and
 *   converted to arrays, but BEFORE the final JSON:API structure is built.
 * - It receives data as a plain array, making modification straightforward.
 * - It is the official extension point for virtual/computed fields.
 *
 * WHY priority -10:
 * - We run AFTER the core Oro processors that have priority 0, ensuring
 *   the base field array is already populated before we add our field.
 * - We do NOT need to be early; we just need the data array to exist.
 */
class AddHelpfulCountToProductReview implements ProcessorInterface
{
    public function __construct(
        private readonly HelpfulVoteRepository $helpfulVoteRepository,
    ) {}

    public function process(ContextInterface $context): void
    {
        // Type-hint the context for IDE completion and safety.
        // WHY: ContextInterface is the base; CustomizeLoadedDataContext has
        //      the actual getData()/setData() methods we need.
        /** @var CustomizeLoadedDataContext $context */

        // getData() returns the already-serialized array for ONE entity (get action)
        // or an array-of-arrays (get_list action). The framework calls this
        // processor once per entity in a list.
        $data = $context->getData();

        // Guard: if 'helpfulCount' was explicitly excluded by the consumer
        // (via sparse fieldsets: fields[productreviews]=id,title), skip computation.
        // WHY: Avoid the DB query cost when the field is not requested.
        if (!$context->isFieldRequested('helpfulCount')) {
            return;
        }

        // Guard: if the field already has a value (e.g., another processor set it),
        // do not overwrite.
        // WHY: Immutable pattern — never overwrite data set by other processors
        //      unless you explicitly own that field.
        if (isset($data['helpfulCount'])) {
            return;
        }

        // Extract the entity ID from the already-serialized data array.
        // WHY: We use the ID (not the entity object) because at this stage the
        //      entity may have already been detached from the Doctrine UoW.
        $reviewId = $data['id'] ?? null;
        if ($reviewId === null) {
            return;
        }

        // Query the repository for the count.
        // WHY repository and not EntityManager directly: repository encapsulates
        //     the query, keeping this processor thin and testable.
        $count = $this->helpfulVoteRepository->countByReviewId((int) $reviewId);

        // Return a NEW array with the added field — do NOT mutate $data in place.
        // WHY immutability: the framework may pass the same array to other processors;
        //     in-place mutation causes hidden side effects.
        $context->setData(array_merge($data, ['helpfulCount' => $count]));
    }
}
```

**services.yml registration:**

```yaml
# src/Acme/Bundle/DemoBundle/Resources/config/services.yml

services:

    # -------------------------------------------------------------------------
    # PROCESSOR: AddHelpfulCountToProductReview
    #
    # Tag breakdown — every attribute matters:
    #
    #   name: oro.api.processor
    #       WHY: This is the Symfony DI tag the ChainProcessor scans to discover
    #            all processors. Without this tag, the processor is invisible to
    #            the API framework regardless of any other configuration.
    #
    #   action: customize_loaded_data
    #       WHY: This targets the post-load auxiliary action. If you used 'get'
    #            or 'get_list' here, the processor would run in the MAIN chain
    #            (before serialization) and would not have access to the
    #            serialized array — it would receive the Doctrine entity object
    #            instead, which cannot be directly modified and then re-serialized.
    #
    #   class: Acme\Bundle\DemoBundle\Entity\ProductReview
    #       WHY: Scopes this processor to run ONLY for ProductReview requests.
    #            Without this, the processor runs for EVERY entity's
    #            customize_loaded_data action — causing errors and wasted queries.
    #
    #   priority: -10
    #       WHY: Runs after Oro's default customize_loaded_data processors (priority 0).
    #            The default processors set up the base array structure; we add our
    #            field after that structure exists. Positive priority would run us
    #            FIRST — before the base data is ready — causing the merge to fail
    #            or produce incomplete results.
    #
    #   requestType: rest&json_api
    #       WHY: Limits execution to JSON:API REST requests only. If you have
    #            custom API types (e.g., 'erp'), this prevents the processor from
    #            running for those. Omit this attribute to run for ALL request types.
    # -------------------------------------------------------------------------
    acme_demo.api.processor.add_helpful_count_to_product_review:
        class: Acme\Bundle\DemoBundle\Api\Processor\AddHelpfulCountToProductReview
        arguments:
            - '@acme_demo.repository.helpful_vote'
        tags:
            -   name:        oro.api.processor
                action:      customize_loaded_data
                class:       Acme\Bundle\DemoBundle\Entity\ProductReview
                priority:    -10
                requestType: rest&json_api
```

---

### Example: Processor That Modifies the Query (build_query group)

This example adds a JOIN to the query to support the `minHelpfulCount` custom filter.

```php
<?php
// src/Acme/Bundle/DemoBundle/Api/Processor/ApplyMinHelpfulCountFilter.php

namespace Acme\Bundle\DemoBundle\Api\Processor;

use Doctrine\ORM\QueryBuilder;
use Oro\Bundle\ApiBundle\Filter\FilterValue;
use Oro\Bundle\ApiBundle\Processor\Context;
use Oro\Component\ChainProcessor\ContextInterface;
use Oro\Component\ChainProcessor\ProcessorInterface;

/**
 * Applies the 'minHelpfulCount' custom filter to the ProductReview query.
 *
 * WHY build_query group:
 * - The QueryBuilder has been created by the time build_query runs but has NOT
 *   been executed yet. This is the correct group to modify JOINs, WHERE clauses,
 *   GROUP BY, or HAVING conditions.
 * - If we ran in load_data, the query is already done — too late.
 * - If we ran in normalize_input, the QueryBuilder does not exist yet — too early.
 *
 * WHY priority -10:
 * - Core Oro processors that set up the base query run at priority 0.
 * - We run at -10 (after) so the base FROM/JOIN structure exists when we modify it.
 * - A processor that depends on ours would use priority -20 or lower.
 */
class ApplyMinHelpfulCountFilter implements ProcessorInterface
{
    public function process(ContextInterface $context): void
    {
        /** @var Context $context */

        // Check whether the consumer supplied our custom filter.
        // WHY: If the filter was not provided, there is nothing to do.
        //      Always check before modifying the query to avoid unintended filtering.
        $filterValues = $context->getFilterValues();
        $filterValue = $filterValues->get('minHelpfulCount');
        if ($filterValue === null) {
            return;
        }

        $minCount = (int) $filterValue->getValue();
        if ($minCount <= 0) {
            // Invalid value — skip silently or add a validation error.
            // For strict APIs, add an error to $context->addError() instead.
            return;
        }

        // Get the QueryBuilder from the context.
        // WHY: The framework builds and stores the QB in the context.
        //      Do not create a new QB — modify the existing one to preserve
        //      all filters, sorters, and pagination already applied.
        $queryBuilder = $context->getQuery();
        if (!$queryBuilder instanceof QueryBuilder) {
            return;
        }

        // Add a correlated subquery (HAVING clause with a count JOIN).
        // WHY subquery rather than a JOIN: Avoids multiplying rows in the result
        //     when reviews have many votes. A HAVING clause on a grouped result
        //     is correct and does not affect pagination counts.
        $queryBuilder
            ->join(
                'Acme\Bundle\DemoBundle\Entity\HelpfulVote',
                'hv',
                'WITH',
                'hv.productReview = e.id'   // 'e' is the root alias for ProductReview
            )
            ->groupBy('e.id')
            ->having('COUNT(hv.id) >= :minHelpfulCount')
            ->setParameter('minHelpfulCount', $minCount);
    }
}
```

**services.yml registration for the query filter processor:**

```yaml
services:

    # -------------------------------------------------------------------------
    # QUERY FILTER PROCESSOR
    #
    #   action: get_list
    #       WHY: Filtering applies to list queries, not single-entity GET.
    #            If you also need filtering on get (unlikely for a count filter),
    #            add a second tag with action: get.
    #
    #   group: build_query
    #       WHY: We must specify the group explicitly so ChainProcessor places us
    #            in the correct stage. Omitting the group runs the processor in
    #            the default group, which is wrong and causes unpredictable behavior.
    #
    #   priority: -10
    #       WHY: Same reasoning as above — let the base query form first.
    # -------------------------------------------------------------------------
    acme_demo.api.processor.apply_min_helpful_count_filter:
        class: Acme\Bundle\DemoBundle\Api\Processor\ApplyMinHelpfulCountFilter
        tags:
            -   name:        oro.api.processor
                action:      get_list
                group:       build_query
                class:       Acme\Bundle\DemoBundle\Entity\ProductReview
                priority:    -10
                requestType: rest&json_api
```

---

## Part 3: Adding a Custom Filter

Filters declared in `api.yml` with a `type` that matches an existing filter type are auto-wired. For custom behavior (like the `minHelpfulCount` filter above), the pattern is:

1. Declare the filter in `api.yml` under `filters.fields` (shown in Part 1)
2. The framework creates a `StandaloneFilter` for it automatically
3. Write a processor in the `build_query` group to read the filter value and modify the QueryBuilder

No additional filter class registration is required for simple value-based filters. The processor pattern is sufficient.

### Custom Filter with a Custom Filter Class

For complex filters (e.g., compound conditions, geo-distance), create a filter class:

```php
<?php
// src/Acme/Bundle/DemoBundle/Api/Filter/MinHelpfulCountFilter.php

namespace Acme\Bundle\DemoBundle\Api\Filter;

use Oro\Bundle\ApiBundle\Filter\FilterValue;
use Oro\Bundle\ApiBundle\Filter\StandaloneFilter;

/**
 * A named filter class for minHelpfulCount.
 * Extending StandaloneFilter makes it compatible with the API filter framework
 * without implementing the full FilterInterface from scratch.
 */
class MinHelpfulCountFilter extends StandaloneFilter
{
    // Override getDescription() to provide API doc text programmatically.
    // WHY: When the filter description needs to be dynamic or contain
    //      logic that cannot be expressed in static YAML.
    public function getDescription(): string
    {
        return 'Returns reviews with at least this many helpful votes. Integer >= 1.';
    }
}
```

Register the filter type and associate it with the field in a processor that runs in `initialize`:

```yaml
# api.yml — use the custom filter type name
filters:
    fields:
        minHelpfulCount:
            type: min_helpful_count   # maps to the registered filter class
            data_type: integer
```

For most use cases, the simpler approach (declare in `api.yml` + processor in `build_query`) is preferred over a custom filter class.

---

## Part 4: JSON:API Request and Response Format

All examples use `ProductReview` as the entity. The URL prefix is `/api/`.

### GET — Single Entity

**Request:**
```http
GET /api/productreviews/42 HTTP/1.1
Accept: application/vnd.api+json
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
    "data": {
        "type": "productreviews",
        "id": "42",
        "attributes": {
            "title": "Excellent quality",
            "body": "This product exceeded my expectations. Fast delivery too.",
            "rating": 5,
            "approved": true,
            "helpfulCount": 17,
            "createdAt": "2025-03-15T10:23:45Z"
        },
        "relationships": {
            "product": {
                "data": {
                    "type": "products",
                    "id": "101"
                }
            },
            "customerUser": {
                "data": {
                    "type": "customerusers",
                    "id": "8"
                }
            }
        },
        "links": {
            "self": "/api/productreviews/42"
        }
    }
}
```

**Key rules:**
- `type` is the entity alias (plural, lowercase) — defined in `entity.yml` or auto-generated
- `id` is always a **string** in JSON:API, even if the database column is an integer
- Scalar fields go in `attributes`; references to other entities go in `relationships`
- Excluded fields (`moderatorNotes`, `internalScore`) do NOT appear at all

---

### GET — List with Filters, Sorting, Pagination

**Request:**
```http
GET /api/productreviews?filter[approved]=true&filter[rating][gte]=4&sort=-createdAt&page[size]=2&page[number]=1 HTTP/1.1
Accept: application/vnd.api+json
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
    "data": [
        {
            "type": "productreviews",
            "id": "42",
            "attributes": {
                "title": "Excellent quality",
                "rating": 5,
                "approved": true,
                "helpfulCount": 17,
                "createdAt": "2025-03-15T10:23:45Z"
            },
            "relationships": {
                "product": { "data": { "type": "products", "id": "101" } },
                "customerUser": { "data": { "type": "customerusers", "id": "8" } }
            }
        },
        {
            "type": "productreviews",
            "id": "38",
            "attributes": {
                "title": "Great value",
                "rating": 4,
                "approved": true,
                "helpfulCount": 3,
                "createdAt": "2025-03-10T08:11:00Z"
            },
            "relationships": {
                "product": { "data": { "type": "products", "id": "101" } },
                "customerUser": { "data": { "type": "customerusers", "id": "14" } }
            }
        }
    ],
    "meta": {
        "totalCount": 47
    },
    "links": {
        "self":  "/api/productreviews?filter[approved]=true&filter[rating][gte]=4&sort=-createdAt&page[size]=2&page[number]=1",
        "first": "/api/productreviews?filter[approved]=true&filter[rating][gte]=4&sort=-createdAt&page[size]=2&page[number]=1",
        "next":  "/api/productreviews?filter[approved]=true&filter[rating][gte]=4&sort=-createdAt&page[size]=2&page[number]=2",
        "last":  "/api/productreviews?filter[approved]=true&filter[rating][gte]=4&sort=-createdAt&page[size]=2&page[number]=24"
    }
}
```

**Sparse fieldsets** — request only specific fields to reduce payload:
```http
GET /api/productreviews?fields[productreviews]=id,title,rating
```

**Include related resources** — embed related entity data in the same response:
```http
GET /api/productreviews/42?include=product,customerUser
```

Response will include a top-level `included` array with the related objects.

---

### POST — Create

**Request:**
```http
POST /api/productreviews HTTP/1.1
Content-Type: application/vnd.api+json
Accept: application/vnd.api+json
Authorization: Bearer <token>

{
    "data": {
        "type": "productreviews",
        "attributes": {
            "title": "Solid product",
            "body": "Arrived on time and matches the description.",
            "rating": 4
        },
        "relationships": {
            "product": {
                "data": { "type": "products", "id": "101" }
            },
            "customerUser": {
                "data": { "type": "customerusers", "id": "8" }
            }
        }
    }
}
```

**Response (201 Created):**
```json
{
    "data": {
        "type": "productreviews",
        "id": "51",
        "attributes": {
            "title": "Solid product",
            "body": "Arrived on time and matches the description.",
            "rating": 4,
            "approved": false,
            "helpfulCount": 0,
            "createdAt": "2026-03-28T14:05:00Z"
        },
        "relationships": {
            "product": { "data": { "type": "products", "id": "101" } },
            "customerUser": { "data": { "type": "customerusers", "id": "8" } }
        },
        "links": {
            "self": "/api/productreviews/51"
        }
    }
}
```

**Key rules:**
- Do NOT include `id` in the request body — the server assigns it
- The `type` must match exactly (case-sensitive)
- Required fields missing from the request body return a 422 Unprocessable Entity error
- The 201 response body contains the full created resource (same as a GET response)

---

### PATCH — Update

Only send fields you want to change. Fields omitted from the request are NOT modified.

**Request:**
```http
PATCH /api/productreviews/51 HTTP/1.1
Content-Type: application/vnd.api+json
Accept: application/vnd.api+json
Authorization: Bearer <token>

{
    "data": {
        "type": "productreviews",
        "id": "51",
        "attributes": {
            "approved": true
        }
    }
}
```

**Response (200 OK):**
```json
{
    "data": {
        "type": "productreviews",
        "id": "51",
        "attributes": {
            "title": "Solid product",
            "body": "Arrived on time and matches the description.",
            "rating": 4,
            "approved": true,
            "helpfulCount": 0,
            "createdAt": "2026-03-28T14:05:00Z"
        },
        "relationships": {
            "product": { "data": { "type": "products", "id": "101" } },
            "customerUser": { "data": { "type": "customerusers", "id": "8" } }
        },
        "links": {
            "self": "/api/productreviews/51"
        }
    }
}
```

**Key rules:**
- The `id` in the URL and in the request body `data.id` must match
- The `type` must match the entity alias
- Partial updates: only fields present in `attributes` are updated — all other fields retain their current values

---

### DELETE — Single Entity

**Request:**
```http
DELETE /api/productreviews/51 HTTP/1.1
Authorization: Bearer <token>
```

**Response (204 No Content):**
```
(empty body)
```

**Key rules:**
- No request body required
- Successful delete returns 204 with no response body
- If the entity does not exist or is not accessible, returns 404

---

### Error Responses

All errors use the JSON:API error format:

```json
{
    "errors": [
        {
            "status": "422",
            "title": "not blank constraint",
            "detail": "This value should not be blank.",
            "source": {
                "pointer": "/data/attributes/title"
            }
        }
    ]
}
```

- `status` — HTTP status code as a string
- `title` — Short error category
- `detail` — Human-readable explanation
- `source.pointer` — JSON Pointer to the field that caused the error (for validation errors)

---

## Part 5: Testing API Endpoints

### Functional Test Base Class

OroCommerce provides `WebTestCase` for API functional tests. Use the built-in API test client for JSON:API-aware assertions.

```php
<?php
// src/Acme/Bundle/DemoBundle/Tests/Functional/Api/Rest/ProductReviewApiTest.php

namespace Acme\Bundle\DemoBundle\Tests\Functional\Api\Rest;

use Oro\Bundle\ApiBundle\Tests\Functional\RestJsonApiTestCase;

/**
 * Functional tests for the ProductReview REST API.
 *
 * WHY RestJsonApiTestCase:
 * - Provides JSON:API-aware HTTP client methods (jsonRequest, get, post, patch, delete)
 * - Handles authentication tokens automatically
 * - Provides assertResponseContains() which validates response structure
 *   against a fixture file — the gold standard for API response testing
 * - Loads data fixtures via @dataFixtures annotation
 */
class ProductReviewApiTest extends RestJsonApiTestCase
{
    /**
     * Load test fixtures before each test.
     * Fixtures create predictable entities in the test database.
     */
    protected function setUp(): void
    {
        parent::setUp();
        $this->loadFixtures([
            '@AcmeDemoBundle/Tests/Functional/Api/DataFixtures/LoadProductReviewData.php',
        ]);
    }

    // -------------------------------------------------------------------------
    // GET SINGLE
    // -------------------------------------------------------------------------

    public function testGetProductReview(): void
    {
        // Get the entity ID from the fixture reference.
        // WHY: Never hardcode IDs — fixture-created IDs are not predictable.
        $review = $this->getReference('product_review_1');

        // Make the GET request using the test client.
        // WHY: cget() = collection GET, get() = single entity GET
        $response = $this->get(
            ['entity' => 'productreviews', 'id' => $review->getId()]
        );

        // Assert HTTP 200
        self::assertResponseStatusCodeEquals($response, 200);

        // Assert the response matches a fixture file.
        // WHY: assertResponseContains() compares the actual JSON response
        //      against a fixture YAML/JSON file that describes the expected structure.
        //      This prevents the test from encoding the full expected JSON inline,
        //      making tests readable and fixture files reusable.
        $this->assertResponseContains(
            '@AcmeDemoBundle/Tests/Functional/Api/Expected/get_product_review.yml',
            $response
        );
    }

    // -------------------------------------------------------------------------
    // GET LIST with filter
    // -------------------------------------------------------------------------

    public function testGetApprovedProductReviews(): void
    {
        $response = $this->cget(
            ['entity' => 'productreviews'],
            ['filter' => ['approved' => 'true']]
        );

        self::assertResponseStatusCodeEquals($response, 200);

        // Check the response contains at least one item and the expected fields.
        $this->assertResponseContains(
            '@AcmeDemoBundle/Tests/Functional/Api/Expected/get_list_approved_reviews.yml',
            $response
        );
    }

    // -------------------------------------------------------------------------
    // POST — Create
    // -------------------------------------------------------------------------

    public function testCreateProductReview(): void
    {
        $product = $this->getReference('product_1');
        $customerUser = $this->getReference('customer_user_1');

        $response = $this->post(
            ['entity' => 'productreviews'],
            [
                'data' => [
                    'type' => 'productreviews',
                    'attributes' => [
                        'title'  => 'Test review',
                        'body'   => 'Test body content.',
                        'rating' => 5,
                    ],
                    'relationships' => [
                        'product' => [
                            'data' => ['type' => 'products', 'id' => (string) $product->getId()],
                        ],
                        'customerUser' => [
                            'data' => ['type' => 'customerusers', 'id' => (string) $customerUser->getId()],
                        ],
                    ],
                ],
            ]
        );

        // Expect 201 Created
        self::assertResponseStatusCodeEquals($response, 201);

        // The response body should contain the created resource with a server-assigned ID.
        $responseData = $this->jsonToArray($response->getContent());
        self::assertNotEmpty($responseData['data']['id']);
        self::assertEquals('Test review', $responseData['data']['attributes']['title']);
        self::assertFalse($responseData['data']['attributes']['approved']); // default: not approved
    }

    // -------------------------------------------------------------------------
    // PATCH — Update
    // -------------------------------------------------------------------------

    public function testApproveProductReview(): void
    {
        $review = $this->getReference('product_review_1');

        $response = $this->patch(
            ['entity' => 'productreviews', 'id' => $review->getId()],
            [
                'data' => [
                    'type' => 'productreviews',
                    'id'   => (string) $review->getId(),
                    'attributes' => [
                        'approved' => true,
                    ],
                ],
            ]
        );

        self::assertResponseStatusCodeEquals($response, 200);

        $responseData = $this->jsonToArray($response->getContent());
        self::assertTrue($responseData['data']['attributes']['approved']);
    }

    // -------------------------------------------------------------------------
    // DELETE
    // -------------------------------------------------------------------------

    public function testDeleteProductReview(): void
    {
        $review = $this->getReference('product_review_1');
        $reviewId = $review->getId();

        $response = $this->delete(
            ['entity' => 'productreviews', 'id' => $reviewId]
        );

        // 204 No Content — success with empty body
        self::assertResponseStatusCodeEquals($response, 204);

        // Verify the entity was actually removed from the database.
        // WHY: HTTP 204 only confirms the request was accepted; check the DB
        //      to confirm the processor chain completed the delete.
        $em = $this->getEntityManager();
        $deleted = $em->find(\Acme\Bundle\DemoBundle\Entity\ProductReview::class, $reviewId);
        self::assertNull($deleted);
    }

    // -------------------------------------------------------------------------
    // VALIDATION ERROR
    // -------------------------------------------------------------------------

    public function testCreateProductReviewValidationError(): void
    {
        $response = $this->post(
            ['entity' => 'productreviews'],
            [
                'data' => [
                    'type' => 'productreviews',
                    'attributes' => [
                        // 'title' is intentionally omitted to trigger a validation error
                        'body'   => 'Some body text.',
                        'rating' => 5,
                    ],
                ],
            ]
        );

        // 422 Unprocessable Entity — validation failed
        self::assertResponseStatusCodeEquals($response, 422);

        $responseData = $this->jsonToArray($response->getContent());
        self::assertArrayHasKey('errors', $responseData);

        // Verify the error points to the correct field
        $errorPointers = array_column(
            array_column($responseData['errors'], 'source'),
            'pointer'
        );
        self::assertContains('/data/attributes/title', $errorPointers);
    }

    // -------------------------------------------------------------------------
    // CUSTOM FILTER: minHelpfulCount
    // -------------------------------------------------------------------------

    public function testFilterByMinHelpfulCount(): void
    {
        // Fixtures must set up some reviews with known helpful counts.
        $response = $this->cget(
            ['entity' => 'productreviews'],
            ['filter' => ['minHelpfulCount' => '5']]
        );

        self::assertResponseStatusCodeEquals($response, 200);

        $responseData = $this->jsonToArray($response->getContent());

        // All returned reviews must have helpfulCount >= 5.
        foreach ($responseData['data'] as $item) {
            self::assertGreaterThanOrEqual(
                5,
                $item['attributes']['helpfulCount'],
                'Review ID ' . $item['id'] . ' has helpfulCount below the filter threshold.'
            );
        }
    }
}
```

---

### Expected Response Fixture File

The `assertResponseContains()` method compares against YAML fixture files. This is the expected format:

```yaml
# src/Acme/Bundle/DemoBundle/Tests/Functional/Api/Expected/get_product_review.yml

data:
    type: productreviews
    id:   '@product_review_1->id'   # Reference to the fixture entity's ID
    attributes:
        title:        'Excellent quality'
        rating:       5
        approved:     true
        helpfulCount: 17
    relationships:
        product:
            data:
                type: products
                id:   '@product_1->id'
        customerUser:
            data:
                type: customerusers
                id:   '@customer_user_1->id'
```

The `@fixture_reference->field` syntax reads the value dynamically from the loaded fixture, making the test ID-independent.

---

### Running the Tests

```bash
# Run all API functional tests for the bundle
vendor/bin/phpunit --testsuite functional --filter ProductReviewApi

# Run with verbose output to see request/response details
vendor/bin/phpunit --testsuite functional --filter ProductReviewApi -v

# Run a single test method
vendor/bin/phpunit --filter testCreateProductReview

# Run with test database reset (slower but fully isolated)
APP_ENV=test php bin/console doctrine:database:drop --force
APP_ENV=test php bin/console doctrine:database:create
APP_ENV=test php bin/console oro:migration:load --force
vendor/bin/phpunit --testsuite functional
```

---

## Part 6: End-to-End Checklist

When adding a new entity to the API, work through these steps in order:

```
[ ] 1. Create or verify the entity class and its Doctrine mapping
[ ] 2. Create/update the database schema via a migration
[ ] 3. Add entity alias in entity.yml (controls the URL slug and JSON:API type)
[ ] 4. Create api.yml with fields, actions, filters, sorters
[ ] 5. Run: php bin/console oro:api:cache:clear
[ ] 6. Verify: php bin/console oro:api:config:dump 'Your\Entity\Class'
[ ] 7. Write functional tests (at minimum: get, get_list, create, update, delete)
[ ] 8. Write custom processors if computed fields or custom filters are needed
[ ] 9. Register processors in services.yml with correct tags and priorities
[ ] 10. Run: php bin/console oro:api:doc:cache:clear
[ ] 11. Open /api/doc and verify the entity appears with correct documentation
[ ] 12. Test with a real HTTP client (curl or Postman) against /api/<entity>
```

---

## Part 7: Common Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| Entity not visible in /api/doc | api.yml not loaded, or cache not cleared | Run `oro:api:cache:clear` and verify the bundle is registered |
| Processor runs for wrong entity | Missing `class:` tag attribute | Add `class: Your\Entity\Class` to the service tag |
| Computed field shows null | Processor runs before data array exists | Lower the priority (negative) so it runs after core serialization |
| POST returns 403 | ACL resource not granted to user | Check `acl_resource` in `api.yml` or grant the permission in security config |
| Filter has no effect | Processor is in wrong group or wrong action | Verify `group: build_query` and `action: get_list` on the service tag |
| Relationship not updating | `update_relationship: false` in api.yml | Set to `true` or use a custom processor to handle the update |
| id in request body mismatch | PATCH body `data.id` != URL `{id}` | Always include the same ID in both URL and request body |
| Unexpected fields exposed | Forgot to exclude internal fields | Add `exclude: true` under each field in `api.yml` |
| DELETE removes related entities | Cascade delete on ORM relationship | Check Doctrine cascade settings; use `orphanRemoval: false` if needed |
| Validation errors not in JSON:API format | Custom form type not integrated | Extend `AbstractApiType` or use standard Symfony form constraints |
