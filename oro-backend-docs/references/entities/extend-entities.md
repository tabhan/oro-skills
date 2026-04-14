# OroCommerce: Extending Entities

> Source: https://doc.oroinc.com/master/backend/entities/extend-entities/

## AGENT QUERY HINTS

This file answers:
- How do I make an entity extendable in OroCommerce?
- What is ExtendEntityInterface and ExtendEntityTrait?
- How do I add enum/option-set (select/multi-select) fields?
- What is the difference between OWNER_CUSTOM and OWNER_SYSTEM?
- How do I add serialized fields (without schema changes)?
- How do I add extended associations (ManyToOne, OneToMany, ManyToMany)?
- What are multi-target associations and when do I use them?
- How do I add validation to extended fields?
- How do I define a custom form type for an extended field?
- What console commands manage the extended entity cache?
- What are the limitations of serialized fields?

---

## Core Concept: WHY Entity Extension Exists

OroCommerce supports two layers of entity customization:

1. **Developer-controlled extension** — migrations add fields that appear in the Entity Management UI
2. **Admin-controlled extension** — admin users add fields themselves via UI (no code required)

The `EntityExtendBundle` powers both layers. It uses:
- `ExtendEntityInterface` + `ExtendEntityTrait` — magic `__get`/`__set` for dynamic fields
- Migration-time `ExtendExtension` — creates extend-aware columns with Oro metadata
- A code generation cache — Doctrine sees a generated "Extend" class, not the magic interface

> CRITICAL CAVEAT: "It is not recommended to rely on the existence of dynamic fields in your business logic since they can be removed by administrative users."

---

## Step 1: Make an Entity Extendable

```php
<?php
// src/Acme/Bundle/DemoBundle/Entity/Document.php

namespace Acme\Bundle\DemoBundle\Entity;

use Doctrine\ORM\Mapping as ORM;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\Config;
use Oro\Bundle\EntityExtendBundle\Entity\ExtendEntityInterface;
use Oro\Bundle\EntityExtendBundle\Entity\ExtendEntityTrait;

#[ORM\Entity]
#[ORM\Table(name: 'acme_demo_document')]

// #[Config] is REQUIRED for any entity that participates in EntityConfigBundle.
// WHY: Without it, ExtendBundle cannot register the entity in its config store,
// and the extend system simply won't work for this class.
#[Config]
class Document implements ExtendEntityInterface
{
    // WHY ExtendEntityTrait:
    // Provides magic __get() / __set() / __isset() / __unset() methods
    // that delegate to dynamically-generated extend fields stored in
    // the Oro cache. Without this trait, accessing an extended field
    // throws a "method not found" error.
    use ExtendEntityTrait;

    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column(type: 'integer')]
    private ?int $id = null;

    // ... standard fields ...
}
```

---

## Step 2: Add Extended Fields via Migration

### Basic extended column

```php
<?php
namespace Acme\Bundle\DemoBundle\Migrations\Schema\v1_1;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\EntityBundle\EntityConfig\DatagridScope;
use Oro\Bundle\EntityExtendBundle\EntityConfig\ExtendScope;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;

class AddDocumentRatingColumn implements Migration
{
    public function up(Schema $schema, QueryBag $queries): void
    {
        $table = $schema->getTable('acme_demo_document');

        $table->addColumn(
            'document_rating',
            'integer',
            [
                'notnull' => false,
                'oro_options' => [
                    'extend' => [
                        'is_extend' => true,   // required for extend system
                        'owner' => ExtendScope::OWNER_CUSTOM,  // auto-rendered in UI
                        'nullable' => true,
                    ],
                    'entity' => [
                        'label' => 'acme.demo.document.document_rating.label',
                    ],
                    'datagrid' => [
                        'is_visible' => DatagridScope::IS_VISIBLE_TRUE,
                    ],
                ],
            ]
        );
    }
}
```

---

## Owner Types Explained

| Constant | UI behavior | When to use |
|----------|-------------|-------------|
| `ExtendScope::OWNER_CUSTOM` | Oro automatically renders the field in grids, forms, and view pages | Most custom fields — the common choice |
| `ExtendScope::OWNER_SYSTEM` | Developer must manually configure rendering in datagrid YAML, form types, and view templates | Fields that need custom rendering logic |

---

## Enum / Option Set Fields (Select / Multi-Select)

Enums create a "select one" or "select many" field from a fixed list of options.

### Adding an enum field via migration

```php
<?php
namespace Acme\Bundle\DemoBundle\Migrations\Schema\v1_2;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\EntityExtendBundle\EntityConfig\ExtendScope;
use Oro\Bundle\EntityExtendBundle\Migration\Extension\ExtendExtensionAwareInterface;
use Oro\Bundle\EntityExtendBundle\Migration\Extension\ExtendExtensionAwareTrait;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;

class AddStatusEnumField implements Migration, ExtendExtensionAwareInterface
{
    use ExtendExtensionAwareTrait;

    public function up(Schema $schema, QueryBag $queries): void
    {
        $this->extendExtension->addEnumField(
            $schema,
            'acme_demo_document',  // table name (not entity class)
            'status',              // field name — MAX 27 characters
            'document_status',     // enum_code — MAX 21 characters, GLOBALLY UNIQUE across app
            false,                 // false = single select (enum), true = multi-select (multiEnum)
            false,                 // false = admin cannot modify available options
            [
                'extend' => ['owner' => ExtendScope::OWNER_CUSTOM],
                'entity' => ['label' => 'acme.demo.document.status.label'],
            ]
        );
    }
}
```

**Constraint table**:

| Parameter | Constraint | Reason |
|-----------|-----------|--------|
| Field name | MAX 27 chars | Oro appends suffixes to build internal method names |
| Enum code | MAX 21 chars | Used in dynamic table names; DB identifier limits |
| Enum code | Globally unique | Shared across all entities in the application |

### Loading enum options via data fixture

```php
<?php
namespace Acme\Bundle\DemoBundle\Migrations\Data\ORM;

use Doctrine\Common\DataFixtures\DependentFixtureInterface;
use Doctrine\Persistence\ObjectManager;
use Oro\Bundle\EntityExtendBundle\Entity\EnumOption;
use Oro\Bundle\EntityExtendBundle\Tools\ExtendHelper;

class LoadDocumentStatusData implements DependentFixtureInterface
{
    private const STATUSES = [
        'draft'    => ['label' => 'Draft',     'priority' => 1, 'default' => true],
        'active'   => ['label' => 'Active',    'priority' => 2, 'default' => false],
        'archived' => ['label' => 'Archived',  'priority' => 3, 'default' => false],
    ];

    public function load(ObjectManager $manager): void
    {
        $enumRepo = $manager->getRepository(EnumOption::class);

        foreach (self::STATUSES as $key => $data) {
            $enumOption = $enumRepo->createEnumOption(
                'document_status',                              // enum_code
                ExtendHelper::buildEnumInternalId($data['label']),  // 32-char internal ID
                $data['label'],                                 // display name
                $data['priority'],                              // sort order
                $data['default']                                // is this the default?
            );
            $manager->persist($enumOption);
        }

        $manager->flush();
    }

    public function getDependencies(): array
    {
        // Depend on migrations being complete before this fixture runs
        return [];
    }
}
```

### ExtendHelper utility methods

| Method | Description |
|--------|-------------|
| `buildEnumCode(string $name)` | Generates a safe enum code from a name |
| `buildEnumInternalId(string $name)` | Creates the 32-char option identifier |
| `isEnumerableType(string $type)` | Returns true for `enum` and `multiEnum` |
| `isSingleEnumType(string $type)` | Returns true for `enum` only |
| `isMultiEnumType(string $type)` | Returns true for `multiEnum` only |
| `getEnumTranslationKey(string $prefix, string $enumCode, string $key)` | Builds translation key |

### Twig filters for enum display

```twig
{# Sort enum options by priority #}
{% for option in entity.status|sort_enum %}
    {{ option.name }}
{% endfor %}

{# Translate a single enum option ID #}
{{ enumOptionId|trans_enum('document_status') }}
```

---

## Serialized Fields (No Schema Change Required)

Serialized fields store data in the entity's `serialized_data` JSON column instead of a dedicated database column. No migration schema update needed — just add the column via `SerializedFieldsExtension`.

### Adding a serialized field

```php
<?php
namespace Acme\Bundle\DemoBundle\Migrations\Schema\v1_3;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\EntityExtendBundle\EntityConfig\ExtendScope;
use Oro\Bundle\EntitySerializedFieldsBundle\Migration\Extension\SerializedFieldsExtensionAwareInterface;
use Oro\Bundle\EntitySerializedFieldsBundle\Migration\Extension\SerializedFieldsExtensionAwareTrait;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;

class AddSerializedField implements Migration, SerializedFieldsExtensionAwareInterface
{
    use SerializedFieldsExtensionAwareTrait;

    public function up(Schema $schema, QueryBag $queries): void
    {
        $this->serializedFieldsExtension->addSerializedField(
            $schema->getTable('acme_demo_document'),
            'internal_notes',       // field name
            'string',               // type (see supported types below)
            [
                'extend' => ['owner' => ExtendScope::OWNER_CUSTOM],
                'entity' => ['label' => 'acme.demo.document.internal_notes.label'],
            ]
        );
    }
}
```

### Supported serialized field types

`BigInt`, `Boolean`, `Date`, `DateTime`, `Decimal`, `Float`, `Integer`, `Select`, `Multi-select`, `Money`, `Percent`, `SmallInt`, `String`, `Text`, `WYSIWYG`

### Serialized field limitations

| Feature | Supported? |
|---------|-----------|
| Grid filtering and sorting | NO |
| Segments and reports | NO |
| Charts | NO |
| Search indexing | NO |
| Relations and option sets | NO |
| Data audit tracking | NO |
| Doctrine query builder | NO |
| Simple storage and retrieval | YES |

> WHY use serialized fields: When you need to store ancillary data quickly without a schema migration. Ideal for rarely-queried, non-filterable metadata.

---

## Extended Associations

Extended associations use `ExtendExtension` to create Doctrine relationships between tables where at least one side is extendable.

### Many-to-One association

```php
<?php
namespace Acme\Bundle\DemoBundle\Migrations\Schema\v1_4;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\EntityExtendBundle\EntityConfig\ExtendScope;
use Oro\Bundle\EntityExtendBundle\Migration\Extension\ExtendExtensionAwareInterface;
use Oro\Bundle\EntityExtendBundle\Migration\Extension\ExtendExtensionAwareTrait;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;

class AddCategoryRelation implements Migration, ExtendExtensionAwareInterface
{
    use ExtendExtensionAwareTrait;

    public function up(Schema $schema, QueryBag $queries): void
    {
        // addManyToOneRelation(schema, ownerTable, fieldName, targetTable, targetColumn, options)
        // WHY ownerTable holds the FK: Many documents belong to one category.
        $this->extendExtension->addManyToOneRelation(
            $schema,
            'acme_demo_document',    // owner table (holds FK column)
            'category',              // field name
            'acme_demo_category',    // target table
            'name',                  // target column for display
            [
                'extend' => [
                    'owner' => ExtendScope::OWNER_CUSTOM,
                    'on_delete' => 'SET NULL',
                    'nullable' => true,
                ],
            ]
        );
    }
}
```

### Available relation methods

| Method | Relationship |
|--------|-------------|
| `addManyToOneRelation()` | Many-to-One, unidirectional |
| `addManyToOneInverseRelation()` | Many-to-One, adds inverse side |
| `addManyToManyRelation()` | Many-to-Many, unidirectional |
| `addManyToManyInverseRelation()` | Many-to-Many, adds inverse side |
| `addOneToManyRelation()` | One-to-Many, unidirectional |
| `addOneToManyInverseRelation()` | One-to-Many, adds inverse side |

### The `without_default` option

```php
$this->extendExtension->addManyToManyRelation(
    $schema,
    'acme_demo_document',
    'tags',
    'acme_demo_tag',
    ['name'],       // title columns
    ['name'],       // detail columns
    ['name'],       // grid columns
    [
        'extend' => [
            'owner' => ExtendScope::OWNER_CUSTOM,
            'without_default' => true,  // do NOT auto-create a default entity record
        ],
    ]
);
```

---

## Multi-Target Associations

Multi-target associations link an entity to **multiple kinds of target entities** when the target type is unknown at design time (e.g., a Comment can belong to an Account OR a Contact OR a Task).

### Step 1: Make entity extendable (same as above)

### Step 2: Implement EntityFieldExtension

```php
<?php
namespace Oro\Bundle\CommentBundle\EntityExtend;

use Oro\Bundle\EntityExtendBundle\EntityExtend\AbstractAssociationEntityFieldExtension;
use Oro\Bundle\EntityExtendBundle\EntityExtend\EntityFieldProcessTransport;
use Oro\Bundle\EntityExtendBundle\Tools\AssociationNameGenerator;
use Oro\Bundle\EntityExtendBundle\Tools\RelationType;

class CommentEntityFieldExtension extends AbstractAssociationEntityFieldExtension
{
    protected function isApplicable(EntityFieldProcessTransport $transport): bool
    {
        return $transport->getClass() === Comment::class
            && AssociationNameGenerator::extractAssociationKind($transport->getName())
               === $this->getRelationKind();
    }

    protected function getRelationKind(): ?string
    {
        return 'comment';  // identifies this association family
    }

    protected function getRelationType(): string
    {
        return RelationType::MANY_TO_ONE;
    }
}
```

Register with tag `oro_entity_extend.entity_field_extension`.

### Generated methods (from ExtendEntityTrait)

| Method pattern | Description |
|----------------|-------------|
| `support{Kind}Target(string $class)` | Returns true if this entity supports the given target class |
| `get{Kind}Target()` | Returns the current target entity |
| `set{Kind}Target($entity)` | Sets the target (many-to-one) |
| `has{Kind}Target($entity)` | Checks if target is set |
| `add{Kind}Target($entity)` | Adds target (many-to-many) |
| `remove{Kind}Target($entity)` | Removes target (many-to-many) |
| `get{Kind}Targets(string $class)` | Returns all targets of given class |

---

## Validation for Extended Fields

By default, extended fields have no validation. Add type-level validation via a compiler pass:

```php
<?php
namespace Acme\Bundle\DemoBundle\DependencyInjection\Compiler;

use Symfony\Component\DependencyInjection\Compiler\CompilerPassInterface;
use Symfony\Component\DependencyInjection\ContainerBuilder;

class AcmeExtendValidationPass implements CompilerPassInterface
{
    // Constraint applied to ALL extended integer fields app-wide.
    // WHY compiler pass: service definitions run at container build time,
    // not at runtime, making this the correct extension point.
    private const INTEGER_CONSTRAINT = [
        'Regex' => [
            'pattern' => '/^(-?[1-9]\d*|0)$/',
            'message' => 'This value should contain only numbers!',
        ]
    ];

    public function process(ContainerBuilder $container): void
    {
        if (!$container->has('oro_entity_extend.validation_loader')) {
            return;
        }

        $definition = $container->findDefinition('oro_entity_extend.validation_loader');
        $definition->addMethodCall(
            'addConstraints',
            ['integer', [self::INTEGER_CONSTRAINT]]
        );
    }
}
```

Register in your bundle class:

```php
class AcmeDemoBundle extends Bundle
{
    public function build(ContainerBuilder $container): void
    {
        parent::build($container);
        $container->addCompilerPass(new AcmeExtendValidationPass());
    }
}
```

> WARNING: Constraints registered this way apply to **every** extended field of that type across the entire application. Use with care.

---

## Custom Form Types for Extended Fields

Three approaches to override the default form rendering:

### Option 1: Compiler pass to add type mapping

```php
$guesser = $container->findDefinition('oro_entity_extend.provider.extend_field_form_type');
$guesser->addMethodCall('addExtendTypeMapping', [
    'time',              // extend field type
    TimeType::class,     // Symfony form type
    ['model_timezone' => 'UTC'],  // form options
]);
```

### Option 2: Custom form options provider

```php
class ExtendFieldCustomFormOptionsProvider implements ExtendFieldFormOptionsProviderInterface
{
    public function getOptions(string $className, string $fieldName): array
    {
        if ($className === Document::class && $fieldName === 'priority') {
            return ['expanded' => true, 'multiple' => false];
        }
        return [];
    }
}
```

Register with tag `acme_entity_extend.form_options_provider`.

### Option 3: Custom guesser with priority

Default guesser priorities:
- `FormConfigGuesser`: 20 (highest)
- `ExtendFieldTypeGuesser`: 15
- `DoctrineTypeGuesser`: 10 (lowest)

To override, register with priority > 20:

```yaml
acme.form.guesser.my_field:
    class: Acme\Bundle\DemoBundle\Form\Guesser\MyFieldGuesser
    tags:
        - { name: form.type_guesser, priority: 25 }
```

---

## Console Commands

| Command | Description | Options |
|---------|-------------|---------|
| `oro:entity-extend:cache:clear` | Clear extended entity cache | `--no-warmup` (skip cache warming) |
| `oro:entity-extend:cache:warmup` | Regenerate extend class cache | `--cache-dir=<path>` |
| `oro:entity-extend:update-schema` | Apply schema for extend fields | `--dry-run` (preview only) |
| `oro:migration:load` | Run pending migrations | `--bundles=X`, `--dry-run` |

```bash
# Typical workflow after adding extend fields:
php bin/console oro:migration:load
php bin/console oro:entity-extend:update-schema
php bin/console oro:entity-extend:cache:warmup
php bin/console cache:clear
```

---

## Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Missing `#[Config]` on entity | Extend system ignores the entity | Add `#[Config]` attribute to class |
| Missing `ExtendEntityTrait` | `__get`/`__set` for extended fields not available | Add `use ExtendEntityTrait;` |
| Relying on extend field in business logic | Admin deletes field, code breaks | Use explicit columns for required business fields |
| Enum code > 21 chars | DB table name truncation, naming conflicts | Keep enum codes under 21 characters |
| Field name > 27 chars | Internal method name overflow | Keep field names under 27 characters |
| Not clearing cache after migration | Old cached extend classes still used | Run `cache:clear` + `entity-extend:cache:warmup` |
| Serialized field in Doctrine query | SQL query fails (field not a real column) | Use serialized fields only for display, not querying |
| Global validation constraint | Applies to all entities, not just yours | Scope constraint in `isApplicable()` check |
