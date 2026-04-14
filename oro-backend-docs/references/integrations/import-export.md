# OroCommerce Import/Export System

> Source: https://doc.oroinc.com/master/backend/integrations/import-export/

## AGENT QUERY HINTS

Use this file when asked about:
- "How do I make an entity importable or exportable?"
- "How does the import/export system work in Oro?"
- "What is ConfigField importexport scope?"
- "How do I configure identity fields for import?"
- "How do I write a custom import strategy?"
- "What events fire during import/export?"
- "How do I create an import template fixture?"
- "How do I register an import/export processor?"
- "What is ConfigurableAddOrReplaceStrategy?"
- "How do I add import/export buttons to a list view?"
- "How do I speed up large imports?"
- "What are Readers, Processors, Writers in Oro?"

---

## Overview

The `OroImportExportBundle` provides a file-exchange import/export system for OroCommerce entities. It allows:
- Exporting entity records to CSV/XLSX files
- Importing records back from those files
- UI access for business users
- CLI commands for administrators and large datasets
- Field-level configuration via `#[ConfigField]` attributes on entity properties

**WHY this approach**: Import/export is the recommended pattern for bulk data operations where real-time sync is not required. It supports automated scheduling, flexible data transformation, and non-Oro developer maintenance.

---

## Architecture: The Pipeline

Every import or export operation runs as an **OroBatchBundle Job** with a pipeline of three components per step:

```
[Source] → Reader → Processor → Writer → [Destination]
```

### Reader
Extracts raw data from a source:
- `CsvFileReader` — reads CSV files with configurable delimiters
- `EntityReader` — reads Doctrine entities via buffered queries
- `TemplateFixtureReader` — reads template fixture data for downloadable templates

### Processor
Transforms data between raw format and domain objects. Contains three layers:
1. **Data Converter** — transforms reader output into serializer-friendly format (uses `:` delimiter for nested keys, e.g., `owner:firstName`)
2. **Serializer** — normalizes entities to arrays (export) or denormalizes arrays to entities (import); extends Symfony Serializer
3. **Strategy** — implements the actual import business logic (find existing, create new, handle conflicts)

### Writer
Persists the results:
- `CsvFileWriter` — writes export data to CSV
- `EntityWriter` — persists Doctrine entities to DB
- `DoctrineClearWriter` — clears cache (used during validation pass)

### Message Queue Processing (async)
For large datasets, operations run asynchronously:

**Import flow:**
1. `PreImportMessageProcessor` — splits the file into independent chunks
2. `ImportMessageProcessor` — processes each chunk; sends error emails

**Export flow:**
1. `PreExportMessageProcessor` — generates the list of record IDs
2. `ExportMessageProcessor` — handles individual chunks
3. `PostExportMessageProcessor` — merges chunks and sends completion notification

---

## Default Jobs

Three standard jobs handle CSV operations (configured in `OroImportExportBundle`):

| Job Name | Purpose |
|---|---|
| `entity_export_to_csv` | Exports entities to a CSV file |
| `entity_import_validation_from_csv` | Validates a CSV without persisting |
| `entity_import_from_csv` | Validates and persists CSV data |

---

## Entity Field Configuration: `#[ConfigField]`

To control how entity fields behave during import/export, apply `#[ConfigField]` with the `importexport` scope on each entity property.

**WHY**: The `ConfigurableEntityNormalizer` reads these annotations at runtime to decide which fields to include, which identify records, the column order, and how to handle relations.

### Import/Export Scope Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `identity` | boolean | `false` | Marks field as an identifier for finding existing records. Multiple identity fields allowed per entity. |
| `excluded` | boolean | `false` | Prevents the field from being exported or imported. |
| `order` | integer | `0` | Sets the column order in the exported CSV. Lower = first. |
| `full` | boolean | `false` | When `true` on a relation field, exports ALL related entity fields (not just identity fields). |
| `short` | boolean | `false` | When `true`, exports only identity fields of the related entity. |
| `process_as_scalar` | boolean | `false` | Treats a relation field as a scalar value during export (no nested expansion). |
| `header` | string | field label | Custom CSV column header. If not set, uses the field's entity config label. |
| `fallback_field` | string | `'string'` | Attribute name for localized fallback values (requires data converter extension). |
| `immutable` | boolean | `false` | Prevents changing the import/export association state via entity management UI. |

### Annotated Entity Example

```php
<?php

namespace Acme\Bundle\DemoBundle\Entity;

use Doctrine\ORM\Mapping as ORM;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\Config;
use Oro\Bundle\EntityConfigBundle\Metadata\Attribute\ConfigField;

#[ORM\Entity]
#[ORM\Table(name: 'acme_task')]
#[Config(
    defaultValues: [
        // Makes this entity configurable in entity management UI
        'importexport' => ['enabled' => true]
    ]
)]
class Task
{
    #[ORM\Id]
    #[ORM\Column(type: 'integer')]
    #[ORM\GeneratedValue(strategy: 'AUTO')]
    // No ConfigField needed for ID — it is auto-managed
    private ?int $id = null;

    #[ORM\Column(type: 'string', length: 255, unique: true)]
    #[ConfigField(
        defaultValues: [
            'importexport' => [
                // identity: true means this field is used to find existing records on import.
                // If a record with this code already exists, it will be updated; otherwise created.
                'identity' => true,
                // order: 10 means this column appears first in the CSV export.
                'order' => 10,
            ]
        ]
    )]
    private string $code = '';

    #[ORM\Column(type: 'string', length: 255)]
    #[ConfigField(
        defaultValues: [
            'importexport' => [
                'order' => 20,
                // header: sets a custom CSV column name instead of the field label
                'header' => 'Task Subject',
            ]
        ]
    )]
    private string $subject = '';

    #[ORM\Column(type: 'text', nullable: true)]
    #[ConfigField(
        defaultValues: [
            'importexport' => [
                'order' => 30,
            ]
        ]
    )]
    private ?string $description = null;

    #[ORM\Column(type: 'datetime', nullable: true)]
    #[ConfigField(
        defaultValues: [
            'importexport' => [
                'order' => 40,
            ]
        ]
    )]
    private ?\DateTimeInterface $dueDate = null;

    #[ORM\ManyToOne(targetEntity: Status::class)]
    #[ORM\JoinColumn(name: 'status_id', referencedColumnName: 'id', nullable: true)]
    #[ConfigField(
        defaultValues: [
            'importexport' => [
                'order' => 50,
                // full: false (default) means only the identity field(s) of Status are exported.
                // Set full: true to export all Status fields.
                'full' => false,
                // short: true exports the Status only if it has identity fields.
                'short' => true,
            ]
        ]
    )]
    private ?Status $status = null;

    #[ORM\Column(type: 'string', nullable: true)]
    #[ConfigField(
        defaultValues: [
            'importexport' => [
                // excluded: true means this internal field never appears in import/export.
                'excluded' => true,
            ]
        ]
    )]
    private ?string $internalNote = null;
}
```

---

## Making an Entity Support Import/Export: Step-by-Step

### Step 1: Add `#[ConfigField]` to entity fields
See the annotated example above. Ensure at least one field has `'identity' => true` so the import strategy can find existing records.

### Step 2: Create the bundle extension to load config

```php
// src/Acme/Bundle/DemoBundle/DependencyInjection/AcmeDemoExtension.php
namespace Acme\Bundle\DemoBundle\DependencyInjection;

use Symfony\Component\Config\FileLocator;
use Symfony\Component\DependencyInjection\ContainerBuilder;
use Symfony\Component\DependencyInjection\Extension\Extension;
use Symfony\Component\DependencyInjection\Loader;

class AcmeDemoExtension extends Extension
{
    public function load(array $configs, ContainerBuilder $container): void
    {
        $loader = new Loader\YamlFileLoader(
            $container,
            new FileLocator(__DIR__ . '/../Resources/config')
        );
        $loader->load('importexport.yml');
    }
}
```

### Step 3: Define import/export processor services

Create `src/Acme/Bundle/DemoBundle/Resources/config/importexport.yml`:

```yaml
services:
    # Data converter: transforms between flat CSV format and nested array format.
    # The configurable converter uses the ConfigField annotations automatically.
    acme_demo.importexport.data_converter:
        parent: oro_importexport.data_converter.configurable

    # Export processor: serializes entities to CSV rows
    acme_demo.importexport.processor.export:
        parent: oro_importexport.processor.export_abstract
        calls:
            - [setDataConverter, ['@acme_demo.importexport.data_converter']]
        tags:
            - name: oro_importexport.processor
              type: export
              entity: Acme\Bundle\DemoBundle\Entity\Task
              # alias: used in UI and CLI to reference this processor
              alias: acme_task

    # Import validation processor: runs validation without persisting
    acme_demo.importexport.processor.import_validation:
        parent: oro_importexport.processor.import_validation_abstract
        calls:
            - [setDataConverter, ['@acme_demo.importexport.data_converter']]
        tags:
            - name: oro_importexport.processor
              type: import_validation
              entity: Acme\Bundle\DemoBundle\Entity\Task
              alias: acme_task

    # Import processor: persists data to database
    acme_demo.importexport.processor.import:
        parent: oro_importexport.processor.import_abstract
        calls:
            - [setDataConverter, ['@acme_demo.importexport.data_converter']]
        tags:
            - name: oro_importexport.processor
              type: import
              entity: Acme\Bundle\DemoBundle\Entity\Task
              alias: acme_task
```

**Processor tag attributes:**

| Attribute | Required | Description |
|---|---|---|
| `name` | yes | Always `oro_importexport.processor` |
| `type` | yes | `export`, `import`, or `import_validation` |
| `entity` | yes | Fully qualified class name of the entity |
| `alias` | yes | Short name used in UI, CLI, and Twig |

### Step 4: Create a template fixture

A template fixture provides the downloadable sample CSV that users can fill in and import back.

```php
// src/Acme/Bundle/DemoBundle/ImportExport/TemplateFixture/TaskFixture.php
namespace Acme\Bundle\DemoBundle\ImportExport\TemplateFixture;

use Acme\Bundle\DemoBundle\Entity\Task;
use Oro\Bundle\ImportExportBundle\TemplateFixture\AbstractTemplateRepository;
use Oro\Bundle\ImportExportBundle\TemplateFixture\TemplateFixtureInterface;

class TaskFixture extends AbstractTemplateRepository implements TemplateFixtureInterface
{
    public function getEntityClass(): string
    {
        return Task::class;
    }

    public function getData(): \Iterator
    {
        return $this->getEntityData('example-task');
    }

    public function fillEntityData(string $key, mixed $entity): void
    {
        // Populate with realistic example data so the template is useful
        $entity->setCode('TASK-001');
        $entity->setSubject('Call customer');
        $entity->setDescription('Please contact the customer regarding future plans.');
        $entity->setDueDate(new \DateTime('+3 days'));
    }

    protected function createEntity(string $key): Task
    {
        return new Task();
    }
}
```

Register in `importexport.yml`:

```yaml
    acme_demo.importexport.template_fixture.task:
        class: Acme\Bundle\DemoBundle\ImportExport\TemplateFixture\TaskFixture
        tags:
            - { name: oro_importexport.template_fixture }
```

### Step 5: Add import/export buttons to the list view

In your entity's list Twig template:

```twig
{% block navButtons %}
    {% include '@OroImportExport/ImportExport/buttons.html.twig' with {
        entity_class: 'Acme\\Bundle\\DemoBundle\\Entity\\Task',
        exportProcessor: 'acme_task',
        exportTitle: 'Export',
        importProcessor: 'acme_task',
        importTitle: 'Import',
        datagridName: gridName
    } %}
{% endblock %}
```

---

## Import Strategy

The **strategy** is the component that decides what happens when an imported row matches (or doesn't match) an existing record.

### Default: `ConfigurableAddOrReplaceStrategy`

- Searches for existing entities using `identity` fields
- If found: updates the existing entity
- If not found: creates a new entity
- Handles relations, validates, and clears entity manager as needed

**WHY**: This is the standard "upsert" behavior that works for most cases. It reads all `#[ConfigField]` `identity` annotations to build the search criteria.

### Custom Strategy

For performance or complex business rules, implement a custom strategy:

```php
namespace Acme\Bundle\DemoBundle\ImportExport\Strategy;

use Oro\Bundle\ImportExportBundle\Strategy\Import\ConfigurableAddOrReplaceStrategy;

class TaskImportStrategy extends ConfigurableAddOrReplaceStrategy
{
    public function process(mixed $entity): mixed
    {
        // Custom pre-processing (e.g., field defaults, normalization)
        if ($entity instanceof Task && empty($entity->getCode())) {
            // Fail fast with a clear error — never silently accept bad data
            $this->addError('Task code is required for import.');
            return null;
        }

        return parent::process($entity);
    }
}
```

Register and wire the strategy:

```yaml
    acme_demo.importexport.strategy.task:
        class: Acme\Bundle\DemoBundle\ImportExport\Strategy\TaskImportStrategy
        parent: oro_importexport.strategy.configurable_add_or_replace

    # Override the import processor to use the custom strategy
    acme_demo.importexport.processor.import:
        parent: oro_importexport.processor.import_abstract
        calls:
            - [setDataConverter, ['@acme_demo.importexport.data_converter']]
            - [setStrategy, ['@acme_demo.importexport.strategy.task']]
        tags:
            - name: oro_importexport.processor
              type: import
              entity: Acme\Bundle\DemoBundle\Entity\Task
              alias: acme_task
```

---

## Context System

The `StepExecutionProxyContext` wraps `BatchBundle`'s `StepExecution` and tracks:
- Read/add/update/delete/replace/error counters
- Configuration options
- Custom key-value options

Access the context in strategy/processor via `$this->context`.

The `ContextRegistry` provides singleton context instances per step execution.

---

## Events

All events are dispatched by Symfony's EventDispatcher. Subscribe to them to inject custom logic without modifying core classes.

### General Events (`Oro\Bundle\ImportExportBundle\Event\Events`)

| Constant | When It Fires | Use For |
|---|---|---|
| `AFTER_ENTITY_PAGE_LOADED` | After a page of entities loads during export | Modify rows before processing |
| `BEFORE_NORMALIZE_ENTITY` | Before entity → array conversion | Pre-fill normalized data |
| `AFTER_NORMALIZE_ENTITY` | After entity → array conversion | Modify normalized array |
| `BEFORE_DENORMALIZE_ENTITY` | Before array → entity conversion | Pre-fill denormalized data |
| `AFTER_DENORMALIZE_ENTITY` | After array → entity conversion | Modify the entity before strategy |
| `AFTER_LOAD_ENTITY_RULES_AND_BACKEND_HEADERS` | After field rules/headers load | Add or modify column rules |
| `AFTER_LOAD_TEMPLATE_FIXTURES` | After template fixtures load | Modify fixture data |
| `BEFORE_EXPORT_FORMAT_CONVERSION` | Before export format conversion | Modify record pre-conversion |
| `AFTER_EXPORT_FORMAT_CONVERSION` | After export format conversion | Modify converted result |
| `BEFORE_IMPORT_FORMAT_CONVERSION` | Before import format conversion | Modify record pre-conversion |
| `AFTER_IMPORT_FORMAT_CONVERSION` | After import format conversion | Modify converted result |
| `AFTER_JOB_EXECUTION` | After entire job completes | Cache clearing, post-processing |

### Strategy Events (`Oro\Bundle\ImportExportBundle\Event\StrategyEvent`)

| Constant | When It Fires | Use For |
|---|---|---|
| `PROCESS_BEFORE` | Before entity is processed by strategy | Pre-processing, field defaults |
| `PROCESS_AFTER` | After entity strategy completes | Additional validation |

### Event Subscriber Example

```php
namespace Acme\Bundle\DemoBundle\EventListener;

use Oro\Bundle\ImportExportBundle\Event\StrategyEvent;
use Symfony\Component\EventDispatcher\EventSubscriberInterface;

class TaskImportSubscriber implements EventSubscriberInterface
{
    public static function getSubscribedEvents(): array
    {
        return [
            StrategyEvent::PROCESS_BEFORE => 'beforeStrategy',
            StrategyEvent::PROCESS_AFTER  => 'afterStrategy',
        ];
    }

    public function beforeStrategy(StrategyEvent $event): void
    {
        $entity = $event->getEntity();
        if (!$entity instanceof Task) {
            return;
        }
        // Normalize data before strategy runs, e.g., trim whitespace
        $entity->setCode(trim($entity->getCode()));
    }

    public function afterStrategy(StrategyEvent $event): void
    {
        $entity = $event->getEntity();
        if (!$entity instanceof Task) {
            return;
        }
        // Additional validation after strategy — add errors to context
        if ($entity->getDueDate() < new \DateTime()) {
            $event->getContext()->addError('Due date must be in the future.');
        }
    }
}
```

Register in `services.yml`:

```yaml
    acme_demo.event_listener.task_import_subscriber:
        class: Acme\Bundle\DemoBundle\EventListener\TaskImportSubscriber
        tags:
            - { name: kernel.event_subscriber }
```

---

## CLI Commands

```bash
# Import from file (recommended for large datasets)
php bin/console oro:import:file \
    --email=admin@example.com \
    --processor=acme_task \
    --jobName=entity_import_from_csv \
    ~/tasks.csv

# Import in production mode (faster, less logging)
php bin/console oro:import:file --email=admin@example.com ~/tasks.csv --env=prod

# Skip initial validation pass (still validates before saving)
php bin/console oro:import:file ~/tasks.csv \
    --email=admin@example.com \
    --processor=acme_task \
    --jobName=entity_import_from_csv \
    --no-interaction

# Disable optional listeners (speeds up import; disables search index, workflows, audit)
php bin/console oro:import:file ~/tasks.csv \
    --email=admin@example.com \
    --disabled-listeners=all
```

---

## Performance Tips for Large Imports

1. **Disable Xdebug** — check with `php -m | grep xdebug`; it causes severe slowdowns
2. **Use CLI** (`oro:import:file`) — the UI is limited to ~1000 entities
3. **Run with `--env=prod`** — reduces development overhead
4. **Use `--no-interaction`** — skips the first validation pass
5. **Disable optional listeners** — disables search re-indexing, workflow triggers, data audit
6. **Write a custom strategy** — the default `ConfigurableAddOrReplaceStrategy` is comprehensive but slow; a purpose-built strategy does only what's needed

---

## Data Converter: Flat ↔ Nested Key Format

The `DefaultDataConverter` transforms between:
- **Flat** (CSV row): `{'owner:firstName': 'John', 'owner:lastName': 'Doe'}`
- **Nested** (array): `{'owner': {'firstName': 'John', 'lastName': 'Doe'}}`

The `:` delimiter separates relation field paths. The `ConfigurableTableDataConverter` extends this with field rule helpers based on `#[ConfigField]` annotations.

---

## Supported File Formats

| Format | Reader | Writer |
|---|---|---|
| CSV | `CsvFileReader` | `CsvFileWriter` |
| XLSX | `XlsxFileReader` | `XlsxFileWriter` |
| Doctrine | `EntityReader` | `EntityWriter` |
| Direct DB | — | `InsertFromSelectWriter` |

---

## Complete Quick-Reference Checklist

To make a new entity support import/export:

- [ ] Add `#[ConfigField]` with `importexport` scope to all entity fields
- [ ] Mark at least one field with `'identity' => true`
- [ ] Set `'order'` on fields to control CSV column order
- [ ] Mark internal/system fields with `'excluded' => true`
- [ ] Create bundle extension `load()` method to load `importexport.yml`
- [ ] Define data converter service (parent: `oro_importexport.data_converter.configurable`)
- [ ] Define export processor service with `oro_importexport.processor` tag (type: `export`)
- [ ] Define import processor service with `oro_importexport.processor` tag (type: `import`)
- [ ] Define import validation processor service (type: `import_validation`)
- [ ] Create `TemplateFixture` class with realistic sample data
- [ ] Register template fixture with `oro_importexport.template_fixture` tag
- [ ] Add `buttons.html.twig` include to the entity list view
