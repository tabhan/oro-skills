# OroCommerce API — Processors and Customization

> Source: https://doc.oroinc.com/master/backend/api/processors/

## AGENT QUERY HINTS

Use this file when asked:
- "How do I add a custom API processor?"
- "How do I add a computed field to an API response?"
- "How do I modify API response data after it loads?"
- "How do I validate form data before saving via API?"
- "What is customize_loaded_data?"
- "What is customize_form_data?"
- "How do I use processor tags and priorities?"
- "How do I run a processor only for a specific entity?"
- "How do I run a processor only for specific request types?"
- "How do I handle errors in a processor?"
- "How do I add a validation error in a processor?"
- "How do I test an API endpoint in OroCommerce?"
- "How do I write a REST API test?"
- "How do I use RestJsonApiTestCase?"
- "What are API test fixtures?"
- "How do I add an association with a custom query?"
- "How do I add a custom entity identifier (e.g., 'mine')?"
- "How do I disable HATEOAS?"
- "How do I create a custom API type (e.g., ERP integration)?"

---

## Part 1: Processors

### What Is a Processor?

A **processor** is a small PHP class that implements `ProcessorInterface` and performs one specific step in the API request pipeline. Processors are the primary extension mechanism in OroCommerce API.

Every API action (get, create, update, etc.) runs a **chain of processors** organized into named groups (e.g., `initialize`, `build_query`, `normalize_data`). You can inject your own processors at any point in the chain.

**Core principle:** One processor = one responsibility. Keep processors small and focused.

---

### Creating a Custom Processor

#### Step 1: Implement ProcessorInterface

```php
<?php

namespace Acme\Bundle\DemoBundle\Api\Processor;

use Oro\Bundle\ApiBundle\Processor\Context;
use Oro\Component\ChainProcessor\ContextInterface;
use Oro\Component\ChainProcessor\ProcessorInterface;

class DoSomethingWithProduct implements ProcessorInterface
{
    public function process(ContextInterface $context): void
    {
        /** @var Context $context */

        // Always check if work is already done by a higher-priority processor
        if ($context->hasResult()) {
            // Another processor already handled this — skip
            return;
        }

        // Your business logic here
    }
}
```

**Naming convention:** Class names start with verbs and omit the "Processor" suffix.
Examples: `LoadProductPrice`, `ValidateOrderStatus`, `SetDefaultCurrency`

#### Step 2: Register as a Service with a Tag

```yaml
# Resources/config/services.yml

services:
    acme.api.do_something_with_product:
        class: Acme\Bundle\DemoBundle\Api\Processor\DoSomethingWithProduct
        tags:
            - {
                name: oro.api.processor,
                action: get,
                group: normalize_data,
                class: Acme\Bundle\DemoBundle\Entity\Product,
                priority: 10
              }
```

---

### Processor Tag Attributes

| Attribute | Required | Description |
|-----------|----------|-------------|
| `name` | Yes | Always `oro.api.processor` |
| `action` | Yes | The API action (get, get_list, create, update, delete, customize_loaded_data, etc.) |
| `group` | Recommended | The processor group within the action chain |
| `class` | No | Limit to a specific entity class |
| `priority` | No | Execution order (default: 0) |
| `requestType` | No | Limit to specific request types |
| `parentClass` | No | For subresource processors: the parent entity class |
| `association` | No | For subresource processors: the association name |
| `collection` | No | For customize_loaded_data: process whole collection at once |
| `identifier_only` | No | For relationship loading: null/true/false |

---

### Priority System

- **Range:** -255 to 255 (some groups may use wider ranges)
- **Higher number = runs first**
- **Default:** 0
- Processors with equal priority have unpredictable order relative to each other

**Strategy:**
- Use positive priorities to run BEFORE the default implementation
- Use negative priorities to run AFTER the default implementation
- Use 0 for processors that don't care about relative order

```yaml
# Run before default processors
tags:
    - { name: oro.api.processor, action: get, group: initialize, priority: 100 }

# Run after default processors
tags:
    - { name: oro.api.processor, action: get, group: initialize, priority: -50 }
```

---

### Processor Conditions (Filtering Execution)

Control when a processor runs using tag attributes instead of if-statements inside the processor:

```yaml
# Run only for a specific action
- { name: oro.api.processor, action: get_list }

# Run for specific action AND group
- { name: oro.api.processor, action: get_list, group: initialize }

# Run only for REST requests
- { name: oro.api.processor, requestType: rest }

# Exclude a request type
- { name: oro.api.processor, requestType: '!rest' }

# Both conditions (logical AND)
- { name: oro.api.processor, requestType: rest&json_api }

# Either condition (logical OR)
- { name: oro.api.processor, requestType: rest|json_api }

# Exclude combined types
- { name: oro.api.processor, requestType: rest&!json_api }

# Limit to specific entity class
- { name: oro.api.processor, class: Oro\Bundle\UserBundle\Entity\User }

# Only run when a context attribute exists
- { name: oro.api.processor, someAttribute: exists }

# Only run when a context attribute does NOT exist
- { name: oro.api.processor, someAttribute: '!exists' }

# Subresource processor: specific parent and association
- {
    name: oro.api.processor,
    action: get_subresource,
    group: build_query,
    parentClass: Acme\Bundle\DemoBundle\Entity\Account,
    association: contacts,
    priority: -90
  }
```

---

### Processor Groups by Action

#### For get and get_list
```
initialize → resource_check → normalize_input → security_check
→ build_query → load_data → data_security_check
→ normalize_data → finalize → normalize_result
```

#### For create and update
```
initialize → resource_check → normalize_input → security_check
→ load_data → data_security_check → transform_data → save_data
→ normalize_data → finalize → normalize_result
```

#### For delete
```
initialize → resource_check → normalize_input → security_check
→ load_data → data_security_check → delete_data
→ finalize → normalize_result
```

**Debug tip:** View all processors for an action with priorities:
```bash
php bin/console oro:api:debug get
php bin/console oro:api:debug create
php bin/console oro:api:debug customize_loaded_data
```

---

### Error Handling in Processors

Processors handle three categories of errors:

#### Throwing Exceptions (Unexpected Errors)
```php
throw new \RuntimeException('Something went wrong');
throw new \Symfony\Component\Security\Core\Exception\AccessDeniedException('Access denied');
```

#### Adding Validation Errors (User-Facing)
```php
use Oro\Bundle\ApiBundle\Model\Error;
use Oro\Bundle\ApiBundle\Model\ErrorSource;
use Oro\Bundle\ApiBundle\Request\Constraint;

// Simple validation error
$context->addError(
    Error::createValidationError(
        Constraint::ENTITY_ID,
        'The identifier must be set.'
    )
);

// Error pointing to a specific field
$error = Error::createValidationError(
    Constraint::VALUE,
    'The price must be greater than zero.'
);
$error->setSource(ErrorSource::createByPropertyPath('price'));
$context->addError($error);

// Error pointing to a query parameter
$error = Error::createValidationError(
    Constraint::FILTER,
    'Invalid filter value.'
);
$error->setSource(ErrorSource::createByParameter('filter[name]'));
$context->addError($error);
```

#### Error Class Factory Methods

| Method | Use Case |
|--------|---------|
| `Error::create(title, detail)` | General errors |
| `Error::createValidationError(title, detail)` | Validation constraint violations |
| `Error::createByException(exception)` | Wrap a PHP exception as an API error |

#### ErrorSource Factory Methods

| Method | Meaning |
|--------|---------|
| `ErrorSource::createByPropertyPath(path)` | Points to an entity property |
| `ErrorSource::createByPointer(pointer)` | JSON document pointer (RFC 6901) |
| `ErrorSource::createByParameter(parameter)` | URI query parameter |

**Key behavior:** When errors are added to the context, the chain skips to `normalize_result`, which always runs and formats the error response.

---

## Part 2: Common Customization Patterns

### Pattern 1: Add a Computed Field

Use this pattern when you need to add a field to the API response that is NOT a real entity property (e.g., a calculated price, an external data lookup).

#### Step 1: Declare the virtual field in api.yml
```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            fields:
                currentPrice:
                    data_type: money
                    property_path: _         # Underscore = virtual/computed
                    depends_on: [priceList]  # Ensure priceList is always loaded
```

#### Step 2: Create a customize_loaded_data processor
```php
<?php

namespace Acme\Bundle\DemoBundle\Api\Processor;

use Oro\Bundle\ApiBundle\Processor\CustomizeLoadedData\CustomizeLoadedDataContext;
use Oro\Component\ChainProcessor\ContextInterface;
use Oro\Component\ChainProcessor\ProcessorInterface;

class ComputeProductCurrentPrice implements ProcessorInterface
{
    private PriceRepository $priceRepository;

    public function __construct(PriceRepository $priceRepository)
    {
        $this->priceRepository = $priceRepository;
    }

    public function process(ContextInterface $context): void
    {
        /** @var CustomizeLoadedDataContext $context */
        $data = $context->getData();

        // Get the field name as it appears in the response
        // (may differ from config due to renaming)
        $priceFieldName = $context->getResultFieldName('currentPrice');

        // Only compute if the client actually requested this field
        // (respects sparse fieldsets)
        if (!$context->isFieldRequested($priceFieldName, $data)) {
            return;
        }

        // Get the entity ID from loaded data
        $idFieldName = $context->getResultFieldName('id');
        if (!$idFieldName || empty($data[$idFieldName])) {
            return;
        }

        // Compute and set the value
        $data[$priceFieldName] = $this->priceRepository->getCurrentPrice(
            (int) $data[$idFieldName]
        );
        $context->setData($data);
    }
}
```

#### Step 3: Register the processor
```yaml
services:
    acme.api.compute_product_current_price:
        class: Acme\Bundle\DemoBundle\Api\Processor\ComputeProductCurrentPrice
        arguments:
            - '@acme.repository.price'
        tags:
            - {
                name: oro.api.processor,
                action: customize_loaded_data,
                class: Acme\Bundle\DemoBundle\Entity\Product
              }
```

#### Processing a Collection at Once
For efficiency when loading multiple entities, use `collection: true`:
```yaml
tags:
    - {
        name: oro.api.processor,
        action: customize_loaded_data,
        collection: true,
        class: Acme\Bundle\DemoBundle\Entity\Product
      }
```

With `collection: true`, `$context->getData()` returns an array of all loaded entities. Use this to batch-load computed data (e.g., one DB query for all prices instead of N queries).

```php
public function process(ContextInterface $context): void
{
    /** @var CustomizeLoadedDataContext $context */
    $data = $context->getData();
    $priceFieldName = $context->getResultFieldName('currentPrice');

    // Collect IDs of all entities that need the price
    $productIds = [];
    foreach ($data as $index => $item) {
        if ($context->isFieldRequested($priceFieldName, $item)) {
            $idFieldName = $context->getResultFieldName('id');
            $productIds[$index] = $item[$idFieldName];
        }
    }

    if (empty($productIds)) {
        return;
    }

    // Single batch query
    $prices = $this->priceRepository->getPricesByIds(array_values($productIds));

    // Apply prices back to the data array
    foreach ($productIds as $index => $productId) {
        $data[$index][$priceFieldName] = $prices[$productId] ?? null;
    }

    $context->setData($data);
}
```

---

### Pattern 2: Validate or Transform Form Data (customize_form_data)

Use this pattern to validate or modify submitted data during create/update **before** it is saved to the database.

#### Event Order in customize_form_data

| Event | When It Fires | Typical Use |
|-------|---------------|------------|
| `pre_submit` | Before form data is bound | Modify raw input data |
| `submit` | During data binding | Rare |
| `post_submit` | After data binding | Validate field combinations |
| `pre_validate` | Before Symfony validation | Add custom constraints |
| `post_validate` | After Symfony validation | Conditional validation |
| `pre_flush_data` | Before DB flush | Compute derived fields |
| `post_flush_data` | After DB flush | Trigger side effects |
| `post_save_data` | After full save | Send notifications |
| `rollback_validated_request` | When `enable_validation: true` | Clean up after dry-run |

#### Example: Validate a Required Virtual Field

```php
<?php

namespace Acme\Bundle\DemoBundle\Api\Processor;

use Oro\Bundle\ApiBundle\Form\FormUtil;
use Oro\Bundle\ApiBundle\Processor\CustomizeFormData\CustomizeFormDataContext;
use Oro\Bundle\ApiBundle\Request\ApiAction;
use Oro\Component\ChainProcessor\ContextInterface;
use Oro\Component\ChainProcessor\ProcessorInterface;
use Symfony\Component\Validator\Constraints\NotBlank;

class ValidateProductSku implements ProcessorInterface
{
    public function process(ContextInterface $context): void
    {
        /** @var CustomizeFormDataContext $context */

        // Find the form field for 'sku'
        $form = $context->findFormField('sku');
        if (null === $form) {
            return;
        }

        // On CREATE: sku is required even if not submitted
        if ($context->getParentAction() === ApiAction::CREATE && !$form->isSubmitted()) {
            FormUtil::addFormConstraintViolation($form, new NotBlank());
            return;
        }

        // On UPDATE: if submitted, must not be blank
        if ($form->isSubmitted() && (null === $form->getData() || '' === $form->getData())) {
            FormUtil::addFormConstraintViolation($form, new NotBlank());
        }
    }
}
```

#### Register the processor

```yaml
services:
    acme.api.validate_product_sku:
        class: Acme\Bundle\DemoBundle\Api\Processor\ValidateProductSku
        tags:
            - {
                name: oro.api.processor,
                action: customize_form_data,
                event: post_submit,
                class: Acme\Bundle\DemoBundle\Entity\Product
              }
```

---

### Pattern 3: Add an Association with a Custom Query

Use this when the relationship between two entities is mediated by a link table or has business conditions (e.g., only enabled contacts).

#### Step 1: Configure the virtual field in api.yml
```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Account:
            fields:
                contacts:
                    target_class: Acme\Bundle\DemoBundle\Entity\Contact
                    target_type: to-many
                    property_path: _    # Virtual: no direct ORM association
```

#### Step 2: Set a custom query for get/get_list via get_config processor

```php
<?php

namespace Acme\Bundle\DemoBundle\Api\Processor;

use Acme\Bundle\DemoBundle\Entity\Account;
use Oro\Bundle\ApiBundle\Processor\GetConfig\ConfigContext;
use Oro\Bundle\ApiBundle\Util\DoctrineHelper;
use Oro\Component\ChainProcessor\ContextInterface;
use Oro\Component\ChainProcessor\ProcessorInterface;

class SetAccountContactsAssociationQuery implements ProcessorInterface
{
    public function __construct(private DoctrineHelper $doctrineHelper)
    {
    }

    public function process(ContextInterface $context): void
    {
        /** @var ConfigContext $context */
        $definition = $context->getResult();
        $contactsField = $definition->getField('contacts');

        if (null === $contactsField
            || $contactsField->isExcluded()
            || null !== $contactsField->getAssociationQuery()
        ) {
            return;
        }

        // Define JOIN query: only enabled contacts
        $contactsField->setAssociationQuery(
            $this->doctrineHelper
                ->createQueryBuilder(Account::class, 'e')
                ->innerJoin('e.contactLinks', 'links')
                ->innerJoin('links.contact', 'r')
                ->where('links.enabled = :contacts_enabled')
                ->setParameter('contacts_enabled', true)
        );
    }
}
```

```yaml
services:
    acme.api.set_account_contacts_association_query:
        class: Acme\Bundle\DemoBundle\Api\Processor\SetAccountContactsAssociationQuery
        arguments:
            - '@oro_api.doctrine_helper'
        tags:
            - {
                name: oro.api.processor,
                action: get_config,
                extra: '!identifier_fields_only',
                class: Acme\Bundle\DemoBundle\Entity\Account,
                priority: -35
              }
```

#### Step 3: Build a custom subresource query

```php
<?php

namespace Acme\Bundle\DemoBundle\Api\Processor;

use Acme\Bundle\DemoBundle\Entity\AccountContactLink;
use Acme\Bundle\DemoBundle\Entity\Contact;
use Oro\Bundle\ApiBundle\Collection\Join;
use Oro\Bundle\ApiBundle\Processor\Subresource\Shared\AddParentEntityIdToQuery;
use Oro\Bundle\ApiBundle\Processor\Subresource\SubresourceContext;
use Oro\Bundle\ApiBundle\Util\DoctrineHelper;
use Oro\Component\ChainProcessor\ContextInterface;
use Oro\Component\ChainProcessor\ProcessorInterface;

class BuildAccountContactsSubresourceQuery implements ProcessorInterface
{
    public function __construct(private DoctrineHelper $doctrineHelper)
    {
    }

    public function process(ContextInterface $context): void
    {
        /** @var SubresourceContext $context */

        // Skip if another processor already set the query
        if ($context->hasQuery()) {
            return;
        }

        $query = $this->doctrineHelper
            ->createQueryBuilder(Contact::class, 'e')
            ->innerJoin(
                AccountContactLink::class,
                'links',
                Join::WITH,
                'links.contact = e AND links.enabled = true'
            )
            ->where('links.account = :' . AddParentEntityIdToQuery::PARENT_ENTITY_ID_QUERY_PARAM_NAME)
            ->setParameter(
                AddParentEntityIdToQuery::PARENT_ENTITY_ID_QUERY_PARAM_NAME,
                $context->getParentId()
            );

        $context->setQuery($query);
    }
}
```

```yaml
services:
    acme.api.build_account_contacts_subresource_query:
        class: Acme\Bundle\DemoBundle\Api\Processor\BuildAccountContactsSubresourceQuery
        arguments:
            - '@oro_api.doctrine_helper'
        tags:
            - {
                name: oro.api.processor,
                action: get_subresource,
                group: build_query,
                association: contacts,
                parentClass: Acme\Bundle\DemoBundle\Entity\Account,
                priority: -90
              }
            - {
                name: oro.api.processor,
                action: get_relationship,
                group: build_query,
                association: contacts,
                parentClass: Acme\Bundle\DemoBundle\Entity\Account,
                priority: -90
              }
```

---

### Pattern 4: Add a Predefined Entity Identifier (e.g., "mine")

Allow clients to use a reserved keyword like `mine` instead of a numeric ID.

#### Step 1: Create an EntityIdResolver

```php
<?php

namespace Acme\Bundle\DemoBundle\Api;

use Oro\Bundle\ApiBundle\Request\EntityIdResolverInterface;
use Oro\Bundle\SecurityBundle\Authentication\TokenAccessorInterface;
use Oro\Bundle\UserBundle\Entity\User;

class MineUserEntityIdResolver implements EntityIdResolverInterface
{
    public function __construct(private TokenAccessorInterface $tokenAccessor)
    {
    }

    public function getDescription(): string
    {
        return <<<MARKDOWN
**mine** can be used to identify the current authenticated user.
MARKDOWN;
    }

    public function resolve(): mixed
    {
        $user = $this->tokenAccessor->getUser();
        return $user instanceof User ? $user->getId() : null;
    }
}
```

#### Step 2: Register the resolver

```yaml
services:
    acme.api.mine_user_entity_id_resolver:
        class: Acme\Bundle\DemoBundle\Api\MineUserEntityIdResolver
        arguments:
            - '@oro_security.token_accessor'
        tags:
            - {
                name: oro.api.entity_id_resolver,
                id: mine,
                class: Oro\Bundle\UserBundle\Entity\User
              }
```

Now `GET /api/users/mine` returns the current user's data.

---

### Pattern 5: Create a Custom API Type (e.g., ERP Integration)

Create a distinct API variant accessible via a custom HTTP header, with its own configuration file.

#### Step 1: Configure in app.yml (config/config.yml)
```yaml
oro_api:
    config_files:
        erp:
            file_name: [api_erp.yml, api.yml]    # ERP overrides, fallback to standard
            request_type: ['erp']

    api_doc_views:
        erp_rest_json_api:
            label: ERP Integration
            underlying_view: rest_json_api
            headers:
                X-Integration-Type: ERP
            request_type: ['rest', 'json_api', 'erp']
```

#### Step 2: Create a processor to detect the custom request type

```php
<?php

namespace Acme\Bundle\DemoBundle\Api\Processor;

use Oro\Bundle\ApiBundle\Processor\Context;
use Oro\Component\ChainProcessor\ContextInterface;
use Oro\Component\ChainProcessor\ProcessorInterface;

class CheckErpRequestType implements ProcessorInterface
{
    private const HEADER_NAME = 'X-Integration-Type';
    private const HEADER_VALUE = 'ERP';
    private const REQUEST_TYPE = 'erp';

    public function process(ContextInterface $context): void
    {
        /** @var Context $context */
        $requestType = $context->getRequestType();
        if (!$requestType->contains(self::REQUEST_TYPE)
            && self::HEADER_VALUE === $context->getRequestHeaders()->get(self::HEADER_NAME)
        ) {
            $requestType->add(self::REQUEST_TYPE);
        }
    }
}
```

```yaml
services:
    acme.api.erp.check_erp_request_type:
        class: Acme\Bundle\DemoBundle\Api\Processor\CheckErpRequestType
        tags:
            - { name: oro.api.processor, action: get, group: initialize, priority: 250 }
            - { name: oro.api.processor, action: get_list, group: initialize, priority: 250 }
            - { name: oro.api.processor, action: create, group: initialize, priority: 250 }
            - { name: oro.api.processor, action: update, group: initialize, priority: 250 }
            - { name: oro.api.processor, action: delete, group: initialize, priority: 250 }
```

#### Step 3: Create ERP-specific api_erp.yml
```yaml
# Resources/config/oro/api_erp.yml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            fields:
                erpCode:
                    exclude: false    # Expose ERP code only for ERP integration
```

---

### Pattern 6: Create an API Endpoint for a Non-Entity (Registration, etc.)

Use when you need an API endpoint that doesn't map to an ORM entity.

#### Step 1: Create a plain PHP model class

```php
<?php

namespace Acme\Bundle\DemoBundle\Api\Model;

class RegistrationRequest
{
    private ?string $name = null;
    private ?string $email = null;

    public function getName(): ?string { return $this->name; }
    public function setName(?string $name): void { $this->name = $name; }
    public function getEmail(): ?string { return $this->email; }
    public function setEmail(?string $email): void { $this->email = $email; }
}
```

#### Step 2: Configure in api.yml
```yaml
api:
    entity_aliases:
        Acme\Bundle\DemoBundle\Api\Model\RegistrationRequest:
            alias: registeraccount
            plural_alias: registeraccount

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

#### Step 3: Register a custom route
```yaml
# Resources/config/oro/routing.yml
acme_rest_api_register_account:
    path: '%oro_api.rest.prefix%registeraccount'
    controller: Oro\Bundle\ApiBundle\Controller\RestApiController::itemWithoutIdAction
    defaults:
        entity: registeraccount
    options:
        group: rest_api
```

#### Step 4: Create a save_data processor
```php
<?php

namespace Acme\Bundle\DemoBundle\Api\Processor;

use Acme\Bundle\DemoBundle\Api\Model\RegistrationRequest;
use Acme\Bundle\DemoBundle\Service\AccountRegistrationService;
use Oro\Component\ChainProcessor\ContextInterface;
use Oro\Component\ChainProcessor\ProcessorInterface;

class ProcessRegistrationRequest implements ProcessorInterface
{
    public function __construct(
        private AccountRegistrationService $registrationService
    ) {
    }

    public function process(ContextInterface $context): void
    {
        /** @var RegistrationRequest $request */
        $request = $context->getResult();
        $this->registrationService->register($request->getName(), $request->getEmail());
    }
}
```

```yaml
services:
    acme.api.process_registration_request:
        class: Acme\Bundle\DemoBundle\Api\Processor\ProcessRegistrationRequest
        arguments:
            - '@acme.service.account_registration'
        tags:
            - {
                name: oro.api.processor,
                action: create,
                group: save_data,
                class: Acme\Bundle\DemoBundle\Api\Model\RegistrationRequest
              }
```

---

## Part 3: Testing REST API

### Test Base Classes

| Class | Use Case |
|-------|---------|
| `RestJsonApiTestCase` | Standard REST API endpoint tests |
| `RestJsonApiUpdateListTestCase` | Asynchronous batch operations (needs message queue) |
| `RestJsonApiSyncUpdateListTestCase` | Synchronous batch API tests |

All are functional test cases — they boot the full Symfony kernel and execute real HTTP requests.

### Available Request Methods

```php
// Single resource
$response = $this->get(['entity' => 'products', 'id' => '<@product->id>']);
$response = $this->post(['entity' => 'products'], 'create_product.yml');
$response = $this->patch(['entity' => 'products', 'id' => '<@product->id>'], 'update_product.yml');
$response = $this->delete(['entity' => 'products', 'id' => '<@product->id>']);

// List
$response = $this->cget(['entity' => 'products']);                          // GET collection
$response = $this->cdelete(['entity' => 'products'], ['filter[status]' => 'draft']);

// Subresources
$response = $this->getSubresource(['entity' => 'products', 'id' => '1', 'association' => 'category']);
$response = $this->postSubresource(['entity' => 'products', 'id' => '1', 'association' => 'images'], '...');
$response = $this->patchSubresource([...], '...');
$response = $this->deleteSubresource([...], '...');

// Relationships
$response = $this->getRelationship(['entity' => 'products', 'id' => '1', 'association' => 'category']);
$response = $this->postRelationship([...], '...');
$response = $this->patchRelationship([...], '...');
$response = $this->deleteRelationship([...], '...');
```

### Writing a Basic Test

```php
<?php

namespace Acme\Bundle\DemoBundle\Tests\Functional\Api\Rest;

use Oro\Bundle\ApiBundle\Tests\Functional\RestJsonApiTestCase;

class ProductApiTest extends RestJsonApiTestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        $this->loadFixtures([
            '@AcmeDemoBundle/Tests/Functional/Api/Rest/DataFixtures/LoadProductData.yml'
        ]);
    }

    public function testGetProduct(): void
    {
        $response = $this->get(
            ['entity' => 'products', 'id' => '<@product1->id>']
        );

        $this->assertResponseContains(
            '@AcmeDemoBundle/Tests/Functional/Api/Rest/responses/get_product.yml',
            $response
        );
    }

    public function testGetProductList(): void
    {
        $response = $this->cget(
            ['entity' => 'products'],
            ['filter[status]' => 'active']
        );

        $this->assertResponseCount(2, $response);
    }

    public function testCreateProduct(): void
    {
        $response = $this->post(
            ['entity' => 'products'],
            '@AcmeDemoBundle/Tests/Functional/Api/Rest/requests/create_product.yml'
        );

        $this->assertResponseContains(
            '@AcmeDemoBundle/Tests/Functional/Api/Rest/responses/create_product.yml',
            $response
        );
    }

    public function testCreateProductValidationError(): void
    {
        $response = $this->post(
            ['entity' => 'products'],
            ['data' => ['type' => 'products', 'attributes' => ['name' => '']]],
            [],
            false    // Do not assert response is successful
        );

        $this->assertResponseValidationError(
            ['title' => 'not blank constraint', 'source' => ['pointer' => '/data/attributes/name']],
            $response
        );
    }
}
```

### YAML Fixture Format (Alice)

```yaml
# Tests/Functional/Api/Rest/DataFixtures/LoadProductData.yml

Acme\Bundle\DemoBundle\Entity\Product:
    product1:
        name: 'Test Product 1'
        sku: 'SKU-001'
        status: 'active'
        createdAt: '<(new \DateTime("-1 day"))>'

    product2:
        name: 'Test Product 2'
        sku: 'SKU-002'
        status: 'draft'
        createdAt: '<(new \DateTime())>'

Acme\Bundle\DemoBundle\Entity\Category:
    category1:
        name: 'Electronics'

# Use @reference for relationships
Acme\Bundle\DemoBundle\Entity\ProductCategory:
    productCategory1:
        product: '@product1'
        category: '@category1'
```

### YAML Request/Response Template Format

Request template (`requests/create_product.yml`):
```yaml
data:
    type: products
    attributes:
        name: 'New Product'
        sku: 'NEW-001'
        status: 'draft'
    relationships:
        category:
            data:
                type: categories
                id: '<toString(@category1->id)>'
```

Response template (`responses/get_product.yml`):
```yaml
data:
    type: products
    id: '<toString(@product1->id)>'
    attributes:
        name: 'Test Product 1'
        sku: 'SKU-001'
        status: 'active'
    relationships:
        category:
            data:
                type: categories
                id: '<toString(@category1->id)>'
```

### Alice Reference Syntax in Templates

| Syntax | Meaning |
|--------|---------|
| `<@reference->id>` | Get the `id` of a fixture reference |
| `<toString(@reference->id)>` | Convert ID to string |
| `@reference->method()` | Call a method on a fixture reference |
| `@reference->property->format('Y-m-d')` | Chain access and method calls |

### Assertion Methods Reference

| Method | Purpose |
|--------|---------|
| `assertResponseContains(expected, response)` | Validates response matches expected YAML/array |
| `assertResponseCount(count, response)` | Checks number of items in `data` array |
| `assertResponseValidationError(error, response)` | Validates a single validation error |
| `assertResponseValidationErrors(errors, response)` | Validates multiple validation errors |
| `assertAllowResponseHeader(response, methods)` | Checks `Allow` header |
| `assertMethodNotAllowedResponse(response, methods)` | Checks 405 response |

### Development Helper: Dump Response to YAML

During development, use this to capture a real response as a YAML template:

```php
public function testGetProduct(): void
{
    $response = $this->get(['entity' => 'products', 'id' => '1']);
    $this->dumpYmlTemplate($response);   // Writes YAML to console — copy and save as fixture
}
```

### Unit Testing Individual Processors

For testing processors in isolation (without full HTTP stack):

```php
<?php

namespace Acme\Bundle\DemoBundle\Tests\Unit\Api\Processor;

use Acme\Bundle\DemoBundle\Api\Processor\ComputeProductCurrentPrice;
use Oro\Bundle\ApiBundle\Tests\Unit\Processor\CustomizeLoadedData\CustomizeLoadedDataProcessorTestCase;

class ComputeProductCurrentPriceTest extends CustomizeLoadedDataProcessorTestCase
{
    private ComputeProductCurrentPrice $processor;
    private PriceRepository $priceRepository;

    protected function setUp(): void
    {
        parent::setUp();
        $this->priceRepository = $this->createMock(PriceRepository::class);
        $this->processor = new ComputeProductCurrentPrice($this->priceRepository);
    }

    public function testComputePrice(): void
    {
        $this->context->setData(['id' => 1, 'currentPrice' => null]);
        $this->context->setConfig($this->createConfigObject([
            'fields' => ['id' => null, 'currentPrice' => null]
        ]));

        $this->priceRepository
            ->expects(self::once())
            ->method('getCurrentPrice')
            ->with(1)
            ->willReturn(99.99);

        $this->processor->process($this->context);

        self::assertEquals(99.99, $this->context->getData()['currentPrice']);
    }
}
```

Specialized processor test case base classes exist for each action type:
- `GetProcessorTestCase`
- `GetListProcessorTestCase`
- `CreateProcessorTestCase`
- `UpdateProcessorTestCase`
- `DeleteProcessorTestCase`
- `CustomizeLoadedDataProcessorTestCase`
- `CustomizeFormDataProcessorTestCase`

---

## Part 4: Miscellaneous How-Tos

### Disable HATEOAS for a Request

HATEOAS links cannot be disabled globally. To suppress them for a specific request, send:
```
X-Include: noHateoas
```

### Enable Case-Insensitive Filtering

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Customer:
            filters:
                fields:
                    email:
                        options:
                            case_insensitive: true   # Wraps LOWER() in SQL
```

Or normalize the value in application code:
```yaml
                    email:
                        options:
                            value_transformer: strtoupper  # Transform value before filtering
```

### Use a Non-Primary-Key as Entity Identifier

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Product:
            identifier_field_names: ['uuid']
            identifier_description: 'The UUID of the product'
            fields:
                id:
                    exclude: true    # Hide the numeric PK
                uuid:
                    data_type: guid
```

### Configure Nested Objects (Group Fields)

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Reminder:
            fields:
                interval:
                    data_type: nestedObject
                    form_options:
                        inherit_data: true    # No setter needed on the entity
                    fields:
                        number:
                            property_path: intervalNumber
                        unit:
                            property_path: intervalUnit
                # Hide the original fields
                intervalNumber:
                    exclude: true
                intervalUnit:
                    exclude: true
```

API response:
```json
{
  "data": {
    "type": "reminders",
    "id": "1",
    "attributes": {
      "interval": {
        "number": 2,
        "unit": "H"
      }
    }
  }
}
```

### Configure Nested Associations (Polymorphic Two-Field References)

```yaml
api:
    entities:
        Acme\Bundle\DemoBundle\Entity\Order:
            fields:
                source:
                    data_type: nestedAssociation
                    fields:
                        __class__:
                            property_path: sourceEntityClass
                        id:
                            property_path: sourceEntityId
```

API response:
```json
{
  "data": {
    "type": "orders",
    "id": "1",
    "relationships": {
      "source": {
        "data": { "type": "contacts", "id": "123" }
      }
    }
  }
}
```

---

## WHY: Design Rationale

**WHY small processors instead of one large class?**
Single Responsibility Principle applied at the framework level. Each processor is independently testable, and the chain can be modified without touching other processors. Multiple bundles can contribute processors to the same action.

**WHY use customize_loaded_data instead of modifying entity getters?**
Keeps API concerns out of the domain model. The entity doesn't need to know about API formatting. Computed fields can be loaded from external systems (e.g., price engines) without coupling entities to those systems.

**WHY use YAML response templates in tests instead of inline assertions?**
Separates test data from test logic. Response templates can be generated automatically via `dumpYmlTemplate()` and versioned alongside code. They're easier to read and update than inline array assertions.

**WHY `collection: true` on customize_loaded_data processors?**
Prevents the N+1 query problem. When loading a list of 50 products, you want ONE price lookup query for all 50, not 50 individual queries. The `collection: true` flag gives the processor access to all loaded entities at once.
