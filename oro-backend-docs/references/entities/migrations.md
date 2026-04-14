# OroCommerce: Database Structure Migrations

> Source: https://doc.oroinc.com/master/backend/entities/migration/

## AGENT QUERY HINTS

This file answers:
- How do I create a database migration in OroCommerce?
- How do I add/remove columns from existing tables?
- How do I create a new database table in a migration?
- How do I add an index to a table via migration?
- What is the migration versioning system in Oro?
- How do I run migrations (console commands)?
- What is MigrationQuery and when do I use it?
- How do I add extended/config fields in migrations?
- What is `oro_options` and how does it work?
- How do I add foreign key constraints?
- What is `QueryBag` and `ExtendExtension`?

---

## Core Concept: WHY Migrations Exist

OroMigrationBundle extends Doctrine DBAL to give developers a **code-based, version-controlled approach to database schema management**. Instead of running raw SQL scripts manually or relying on `doctrine:schema:update` (which is destructive and not safe for production), migrations:

- Track which changes have been applied per environment
- Are committed to source control alongside the code that needs them
- Support both schema changes (columns, tables, indexes) and data changes (fixtures)
- Integrate with Oro's extended entity system via `ExtendExtension`

> "OroMigrationBundle extends DBAL and provides the ability for developers to manage and deploy changes in the Oro application database schema programmatically in a consistent, structured way."

---

## Migration Versioning System

Migrations are organized by **bundle** and **version**. Each version is a PHP namespace that maps to a directory:

```
src/Acme/Bundle/DemoBundle/
└── Migrations/
    └── Schema/
        ├── v1_0/
        │   └── AcmeDemoBundle.php      ← initial schema (creates tables)
        ├── v1_1/
        │   └── AddRatingColumn.php     ← adds a column
        └── v1_2/
            └── AddIndexToSubject.php   ← adds an index
```

**WHY version directories**: Oro tracks which versions have been applied in the `oro_migrations` table. Each time you run `oro:migration:load`, only unapplied versions run. This makes incremental deploys safe.

---

## Migration Class Interface

Every migration implements `Oro\Bundle\MigrationBundle\Migration\Migration`:

```php
<?php
namespace Acme\Bundle\DemoBundle\Migrations\Schema\v1_0;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;

class AcmeDemoBundle implements Migration
{
    /**
     * The up() method defines what changes to apply.
     * WHY Schema + QueryBag: Schema handles DDL (CREATE TABLE, ALTER TABLE),
     * while QueryBag holds DML queries (INSERT, UPDATE) to run after DDL.
     */
    public function up(Schema $schema, QueryBag $queries): void
    {
        // All schema changes go here
    }
}
```

---

## Step-by-Step: Creating the Initial Schema (v1_0)

### Create tables for two entities

```php
<?php
namespace Acme\Bundle\DemoBundle\Migrations\Schema\v1_0;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;

class AcmeDemoBundle implements Migration
{
    public function up(Schema $schema, QueryBag $queries): void
    {
        $this->createPriorityTable($schema);
        $this->createDocumentTable($schema);
    }

    /**
     * Creates the acme_demo_priority lookup table.
     */
    private function createPriorityTable(Schema $schema): void
    {
        // createTable() returns a Table object for column/index definition.
        $table = $schema->createTable('acme_demo_priority');

        // addColumn(name, type, options)
        // WHY autoincrement: true: ORM\GeneratedValue requires auto-increment PK.
        $table->addColumn('id', 'integer', ['autoincrement' => true]);
        $table->addColumn('label', 'string', ['length' => 255]);

        // setPrimaryKey() is REQUIRED — Doctrine needs a PK on all tables.
        $table->setPrimaryKey(['id']);
    }

    /**
     * Creates the acme_demo_document table with a FK to priority.
     */
    private function createDocumentTable(Schema $schema): void
    {
        $table = $schema->createTable('acme_demo_document');
        $table->addColumn('id', 'integer', ['autoincrement' => true]);
        $table->addColumn('subject', 'string', ['length' => 255]);
        $table->addColumn('description', 'text', ['notnull' => false]);

        // nullable column: set notnull => false
        $table->addColumn('due_date', 'datetime', ['notnull' => false]);

        // FK column — stores the integer ID of the related priority
        $table->addColumn('priority_id', 'integer', ['notnull' => false]);

        $table->setPrimaryKey(['id']);

        // Index on FK column — speeds up JOIN queries significantly.
        // WHY: Without an index on priority_id, every query joining
        // documents to priorities does a full table scan.
        $table->addIndex(['priority_id'], 'idx_acme_demo_document_priority_id');

        // addForeignKeyConstraint(foreignTable, localColumns, foreignColumns, options)
        // WHY onDelete SET NULL: if a Priority is deleted, documents remain
        // with NULL priority rather than being deleted or causing an error.
        $table->addForeignKeyConstraint(
            $schema->getTable('acme_demo_priority'),
            ['priority_id'],
            ['id'],
            ['onDelete' => 'SET NULL']
        );
    }
}
```

---

## Step-by-Step: Adding a Column (v1_1)

```php
<?php
namespace Acme\Bundle\DemoBundle\Migrations\Schema\v1_1;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;

class AddRatingColumn implements Migration
{
    public function up(Schema $schema, QueryBag $queries): void
    {
        $table = $schema->getTable('acme_demo_document');

        // Adding a nullable column to existing data is SAFE.
        // WHY notnull => false: existing rows would violate NOT NULL
        // if you add a non-nullable column without a default.
        $table->addColumn('rating', 'integer', ['notnull' => false]);

        // Add an index on the new column if you'll filter/sort by it.
        $table->addIndex(['rating'], 'idx_acme_demo_document_rating');
    }
}
```

---

## Step-by-Step: Adding an Extended Field (with oro_options)

When a field should be visible in the Entity Management UI or managed by Oro's config system, add `oro_options` to the column definition:

```php
<?php
namespace Acme\Bundle\DemoBundle\Migrations\Schema\v1_2;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\EntityBundle\EntityConfig\DatagridScope;
use Oro\Bundle\EntityExtendBundle\EntityConfig\ExtendScope;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;

class AddExtendedFields implements Migration
{
    public function up(Schema $schema, QueryBag $queries): void
    {
        $table = $schema->getTable('acme_demo_document');

        $table->addColumn(
            'document_rating',
            'integer',
            [
                // oro_options: Oro-specific metadata for the EntityConfigBundle.
                // These options are NOT Doctrine options — they configure
                // how the field appears in Oro's Entity Management UI.
                'oro_options' => [
                    'extend' => [
                        // is_extend: true = this field participates in Oro's
                        // extend system (can be managed via Entity Config UI).
                        'is_extend' => true,

                        // owner: OWNER_CUSTOM = Oro auto-renders this field
                        // in grids, forms, and views without manual config.
                        // OWNER_SYSTEM = developer must configure rendering manually.
                        'owner' => ExtendScope::OWNER_CUSTOM,

                        // nullable: mirrors the DB notnull setting for Oro config.
                        'nullable' => true,
                    ],
                    'entity' => [
                        // label: human-readable name shown in Entity Management UI.
                        'label' => 'acme.demo.document.document_rating.label',
                    ],
                    'datagrid' => [
                        // Controls whether field appears in entity list grids.
                        'is_visible' => DatagridScope::IS_VISIBLE_TRUE,
                    ],
                ],
                'notnull' => false,
            ]
        );

        // Also add a datetime extended field example
        $table->addColumn(
            'partner_since',
            'datetime',
            [
                'notnull' => false,
                'oro_options' => [
                    'extend' => [
                        'is_extend' => true,
                        'owner' => ExtendScope::OWNER_CUSTOM,
                        'nullable' => true,
                        // on_delete: mirrors FK behavior for relation fields.
                        'on_delete' => 'SET NULL',
                    ],
                    'entity' => [
                        'label' => 'acme.demo.document.partner_since.label',
                    ],
                ],
            ]
        );
    }
}
```

---

## Step-by-Step: Removing a Column (v1_3)

```php
<?php
namespace Acme\Bundle\DemoBundle\Migrations\Schema\v1_3;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;

class RemoveObsoleteColumn implements Migration
{
    public function up(Schema $schema, QueryBag $queries): void
    {
        $table = $schema->getTable('acme_demo_document');

        // Drop the column — this is permanent and cannot be auto-rolled back.
        // ALWAYS back up data before dropping columns in production.
        if ($table->hasColumn('obsolete_field')) {
            $table->dropColumn('obsolete_field');
        }

        // Drop an index
        if ($table->hasIndex('idx_acme_demo_document_obsolete')) {
            $table->dropIndex('idx_acme_demo_document_obsolete');
        }
    }
}
```

---

## Data Queries via QueryBag

Use `QueryBag` to run SQL after schema changes (seed data, update records):

```php
<?php
namespace Acme\Bundle\DemoBundle\Migrations\Schema\v1_4;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;

class SeedPriorityData implements Migration
{
    public function up(Schema $schema, QueryBag $queries): void
    {
        // addQuery() runs AFTER all schema changes complete.
        // WHY: Schema changes (DDL) must commit before DML runs.
        $queries->addQuery(
            "INSERT INTO acme_demo_priority (label) VALUES ('Low'), ('Medium'), ('High')"
        );

        // For parameterized queries, implement SqlMigrationQuery instead.
        // See: Oro\Bundle\MigrationBundle\Migration\SqlMigrationQuery
    }
}
```

---

## Schema API Reference

| Method | Signature | Description |
|--------|-----------|-------------|
| `createTable` | `createTable(string $name): Table` | Creates a new table, returns Table object |
| `getTable` | `getTable(string $name): Table` | Retrieves existing table object |
| `dropTable` | `dropTable(string $name): void` | Drops a table |
| `hasTable` | `hasTable(string $name): bool` | Check if table exists |
| `addColumn` | `addColumn(string $name, string $type, array $options): Column` | Adds column to table |
| `dropColumn` | `dropColumn(string $name): void` | Removes column from table |
| `hasColumn` | `hasColumn(string $name): bool` | Check if column exists |
| `addIndex` | `addIndex(array $cols, string $name): void` | Adds non-unique index |
| `addUniqueIndex` | `addUniqueIndex(array $cols, string $name): void` | Adds unique index |
| `dropIndex` | `dropIndex(string $name): void` | Removes an index |
| `setPrimaryKey` | `setPrimaryKey(array $cols): void` | Sets primary key columns |
| `addForeignKeyConstraint` | `addForeignKeyConstraint(Table $foreign, array $localCols, array $foreignCols, array $opts): void` | Adds FK constraint |

### Column option reference

| Option | Type | Description |
|--------|------|-------------|
| `autoincrement` | bool | Auto-increment (use on PK integer columns) |
| `length` | int | Max length for string/varchar columns |
| `notnull` | bool | NOT NULL constraint (default: true) |
| `default` | mixed | Default value for the column |
| `precision` | int | Total digits for decimal types |
| `scale` | int | Decimal places for decimal types |
| `unsigned` | bool | Unsigned integer (PostgreSQL ignores this) |
| `fixed` | bool | Use CHAR instead of VARCHAR |
| `comment` | string | SQL column comment |
| `oro_options` | array | Oro config metadata (extend, entity, datagrid scopes) |

---

## `oro_options` Parameter Reference

| Key | Sub-key | Type | Description |
|-----|---------|------|-------------|
| `extend` | `is_extend` | bool | Include field in Oro's extend system |
| `extend` | `owner` | ExtendScope::* | `OWNER_CUSTOM` (auto-rendered) or `OWNER_SYSTEM` (manual config) |
| `extend` | `nullable` | bool | Field allows null (mirrors DB setting) |
| `extend` | `on_delete` | string | FK behavior: `'SET NULL'`, `'CASCADE'`, `'RESTRICT'` |
| `entity` | `label` | string | Translation key for field label in UI |
| `datagrid` | `is_visible` | DatagridScope::* | Visibility in entity grids |
| `form` | `is_enabled` | bool | Show field in entity edit forms |
| `view` | `is_displayable` | bool | Show field on entity view pages |

### ExtendScope constants

| Constant | Value | Meaning |
|----------|-------|---------|
| `ExtendScope::OWNER_CUSTOM` | `'Custom'` | Field auto-rendered in all contexts (grid, form, view) |
| `ExtendScope::OWNER_SYSTEM` | `'System'` | Developer manages rendering manually |

### DatagridScope constants

| Constant | Meaning |
|----------|---------|
| `DatagridScope::IS_VISIBLE_TRUE` | Visible in grid by default |
| `DatagridScope::IS_VISIBLE_FALSE` | Hidden in grid by default |
| `DatagridScope::IS_VISIBLE_HTML` | Visible but as HTML (not filterable) |

---

## Running Migrations

```bash
# Apply all unapplied migrations
php bin/console oro:migration:load

# Apply migrations for a specific bundle only
php bin/console oro:migration:load --bundles=AcmeDemoBundle

# Preview what would run (dry run)
php bin/console oro:migration:load --dry-run

# After migration, always clear cache
php bin/console cache:clear

# For extended entity schema updates specifically
php bin/console oro:entity-extend:update-schema
```

---

## Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Adding NOT NULL column to existing table | Migration fails on populated tables | Add as `notnull: false` or provide a `default` |
| Skipping `setPrimaryKey()` | Doctrine entity errors; some DBs reject the table | Always call `setPrimaryKey(['id'])` |
| Missing FK index | Slow JOIN queries | Add `addIndex(['fk_col_id'])` alongside the FK constraint |
| Using `doctrine:schema:update` | Destroys extended fields and config | Always use `oro:migration:load` instead |
| Same version directory used twice | Second migration never runs | Each change needs a new `v1_X` directory |
| Schema change without `oro_options` for extended fields | Field ignored by Entity Config system | Add `oro_options` with `extend.is_extend: true` |
| Running migration after entity class is deleted | Doctrine can't find entity class | Write migration before deleting the entity class |

---

## Migration with ExtendExtension (for Extended Associations)

When adding extended relation fields (enum, association), inject `ExtendExtension`:

```php
<?php
namespace Acme\Bundle\DemoBundle\Migrations\Schema\v1_5;

use Doctrine\DBAL\Schema\Schema;
use Oro\Bundle\EntityExtendBundle\EntityConfig\ExtendScope;
use Oro\Bundle\EntityExtendBundle\Migration\Extension\ExtendExtensionAwareInterface;
use Oro\Bundle\EntityExtendBundle\Migration\Extension\ExtendExtensionAwareTrait;
use Oro\Bundle\MigrationBundle\Migration\Migration;
use Oro\Bundle\MigrationBundle\Migration\QueryBag;

// WHY ExtendExtensionAwareInterface: tells the migration runner to inject
// ExtendExtension into this class before calling up().
class AddEnumField implements Migration, ExtendExtensionAwareInterface
{
    use ExtendExtensionAwareTrait;

    public function up(Schema $schema, QueryBag $queries): void
    {
        // addEnumField() creates both the column and the enum option table.
        $this->extendExtension->addEnumField(
            $schema,
            'acme_demo_document',   // table name
            'status',               // field name (max 27 chars)
            'document_status',      // enum code (max 21 chars, globally unique)
            false,                  // false = single select, true = multi-select
            false,                  // false = admin cannot modify options via UI
            [
                'extend' => ['owner' => ExtendScope::OWNER_CUSTOM],
                'entity' => ['label' => 'acme.demo.document.status.label'],
            ]
        );
    }
}
```

See `extend-entities.md` for full details on enum fields, serialized fields, and extended associations.
