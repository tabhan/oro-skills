# OroCommerce: Creating Entities

> Source: https://doc.oroinc.com/master/backend/entities/create-entities/

## AGENT QUERY HINTS

This file answers:
- How do I create a new entity in OroCommerce/OroPlatform?
- What PHP attributes/annotations does an entity class need?
- How do I register an entity with Doctrine in an Oro bundle?
- What is the required directory structure for entity files?
- How do I define relationships (ManyToOne, OneToMany) between entities?
- What is the standard getter/setter pattern for Oro entities?
- How do I make an entity extendable via the UI?
- What comes after creating an entity class (migrations, config)?

---

## Core Concept: WHY Entity Classes Exist

OroCommerce follows standard Symfony/Doctrine conventions for entity creation. An entity class is a PHP class that maps to a database table. Oro adds layered concepts on top:

1. **Entity class** — defines fields and relationships (this file)
2. **Migration** — creates/alters the database schema (see `migrations.md`)
3. **Entity config** — metadata for UI, grid, form rendering (see `configure-entities.md`)
4. **Extend interface** — allows runtime field addition via UI (see `extend-entities.md`)

> "Creating entities and mapping them to the database is no different from doing the same in a common Symfony application." — Oro docs

---

## Directory Structure

Place entity files in the bundle's `Entity` namespace:

```
src/
└── Acme/Bundle/DemoBundle/
    ├── Entity/
    │   ├── Document.php      ← entity class
    │   └── Priority.php      ← related lookup entity
    ├── Migrations/
    │   └── Schema/
    │       └── v1_0/
    │           └── AcmeDemoBundle.php   ← creates tables
    └── Resources/
        └── config/
            └── oro/
                └── entity.yml           ← entity aliases (optional)
```

---

## Step-by-Step: Creating a Basic Entity

### Step 1 — Create the PHP entity class

```php
<?php
// src/Acme/Bundle/DemoBundle/Entity/Document.php

namespace Acme\Bundle\DemoBundle\Entity;

use Doctrine\ORM\Mapping as ORM;

// #[ORM\Entity] marks this class as a Doctrine-managed entity.
// WHY: Without this, Doctrine ignores the class entirely.
#[ORM\Entity]

// #[ORM\Table] sets the actual database table name.
// WHY: Explicit naming prevents collisions across bundles.
#[ORM\Table(name: 'acme_demo_document')]
class Document
{
    // Primary key — always required.
    // #[ORM\Id] marks it as the identity field.
    // #[ORM\GeneratedValue] tells Doctrine to auto-increment.
    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column(type: 'integer')]
    private ?int $id = null;

    // String column with max length.
    // WHY `length: 255`: prevents unbounded VARCHAR on some DB engines.
    #[ORM\Column(name: 'subject', type: 'string', length: 255)]
    private string $subject = '';

    // Text for longer content.
    #[ORM\Column(name: 'description', type: 'text', nullable: true)]
    private ?string $description = null;

    // Nullable datetime — use nullable: true for optional dates.
    #[ORM\Column(name: 'due_date', type: 'datetime', nullable: true)]
    private ?\DateTimeInterface $dueDate = null;

    // Many Documents can reference one Priority.
    // WHY targetEntity: Doctrine needs the FQCN of the related entity.
    // WHY JoinColumn nullable + onDelete SET NULL:
    //   If Priority is deleted, document records remain with null priority
    //   instead of triggering a foreign key violation.
    #[ORM\ManyToOne(targetEntity: Priority::class)]
    #[ORM\JoinColumn(name: 'priority_id', nullable: true, onDelete: 'SET NULL')]
    private ?Priority $priority = null;

    // --- Getters and Setters ---

    public function getId(): ?int
    {
        return $this->id;
    }

    public function getSubject(): string
    {
        return $this->subject;
    }

    // Return `self` from setters to enable method chaining.
    public function setSubject(string $subject): self
    {
        $this->subject = $subject;
        return $this;
    }

    public function getDescription(): ?string
    {
        return $this->description;
    }

    public function setDescription(?string $description): self
    {
        $this->description = $description;
        return $this;
    }

    public function getDueDate(): ?\DateTimeInterface
    {
        return $this->dueDate;
    }

    public function setDueDate(?\DateTimeInterface $dueDate): self
    {
        $this->dueDate = $dueDate;
        return $this;
    }

    public function getPriority(): ?Priority
    {
        return $this->priority;
    }

    public function setPriority(?Priority $priority): self
    {
        $this->priority = $priority;
        return $this;
    }
}
```

### Step 2 — Create the related lookup entity

```php
<?php
// src/Acme/Bundle/DemoBundle/Entity/Priority.php

namespace Acme\Bundle\DemoBundle\Entity;

use Doctrine\ORM\Mapping as ORM;

#[ORM\Entity]
#[ORM\Table(name: 'acme_demo_priority')]
class Priority
{
    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column(type: 'integer')]
    private ?int $id = null;

    // Human-readable label shown in UI dropdowns.
    #[ORM\Column(name: 'label', type: 'string', length: 255)]
    private string $label = '';

    public function getId(): ?int
    {
        return $this->id;
    }

    public function getLabel(): string
    {
        return $this->label;
    }

    public function setLabel(string $label): self
    {
        $this->label = $label;
        return $this;
    }

    // __toString enables the entity to display in Symfony form choices.
    public function __toString(): string
    {
        return $this->label;
    }
}
```

---

## ORM Mapping Attribute Reference

| Attribute | Scope | Required | Description |
|-----------|-------|----------|-------------|
| `#[ORM\Entity]` | Class | YES | Declares class as a Doctrine entity |
| `#[ORM\Table(name: '...')]` | Class | YES | Database table name (prefix with bundle name to avoid conflicts) |
| `#[ORM\Id]` | Property | YES (one per entity) | Marks the primary key field |
| `#[ORM\GeneratedValue]` | Property | YES (on ID) | Auto-increment strategy |
| `#[ORM\Column(type: '...')]` | Property | YES | Maps property to a DB column |
| `#[ORM\Column(name: '...')]` | Property | NO | Override column name (defaults to snake_case of property name) |
| `#[ORM\Column(length: N)]` | Property | NO | Max length for string columns |
| `#[ORM\Column(nullable: true)]` | Property | NO | Allows NULL in the database column |
| `#[ORM\ManyToOne(targetEntity: X::class)]` | Property | YES (for relation) | Many-to-one relationship |
| `#[ORM\OneToMany(targetEntity: X::class, mappedBy: '...')]` | Property | YES (for relation) | One-to-many relationship |
| `#[ORM\ManyToMany(targetEntity: X::class)]` | Property | YES (for relation) | Many-to-many relationship |
| `#[ORM\JoinColumn(name: '...', nullable: true, onDelete: '...')]` | Property | NO | Configures FK column behavior |

### Column `type` values (Doctrine built-in)

| Type | PHP type | DB type |
|------|----------|---------|
| `integer` | int | INT |
| `string` | string | VARCHAR |
| `text` | string | TEXT |
| `boolean` | bool | TINYINT/BOOL |
| `datetime` | \DateTimeInterface | DATETIME |
| `date` | \DateTimeInterface | DATE |
| `float` | float | FLOAT/DOUBLE |
| `decimal` | string | DECIMAL |
| `json` | array | JSON/TEXT |

### Oro-specific column types (see `advanced.md`)

| Type | Stored as | Purpose |
|------|-----------|---------|
| `money` | DECIMAL(19,4) | Monetary values with auto-formatting |
| `percent` | FLOAT | Percentage values with auto-formatting |
| `duration` | INTEGER | Time in seconds |
| `config_object` | JSON | Configuration objects |

---

## Making an Entity Extendable (UI Field Addition)

To allow admin users to add custom fields via System > Entities > Entity Management:

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

// #[Config] registers the entity with OroEntityConfigBundle.
// WHY: Required for any entity that needs entity management UI,
//      routing config, or extended fields.
#[Config(
    routeName: 'acme_demo_document_index',   // list page route
    routeView: 'acme_demo_document_view',    // view page route
    defaultValues: [
        'entity' => [
            'icon' => 'fa-file',             // FontAwesome icon in UI
        ],
        'ownership' => [
            'owner_type' => 'USER',
            'owner_field_name' => 'owner',
            'owner_column_name' => 'owner_id',
        ],
        'security' => [
            'type' => 'ACL',
            'group_name' => '',
        ],
    ]
)]
// WHY ExtendEntityInterface + ExtendEntityTrait:
//   These enable the dynamic field system. The trait provides
//   magic __get/__set for dynamically added fields via migrations
//   or the UI.
class Document implements ExtendEntityInterface
{
    use ExtendEntityTrait;

    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column(type: 'integer')]
    private ?int $id = null;

    // ... other fields ...
}
```

---

## Entity Registration Checklist

After creating the entity class:

- [ ] **Entity class** created in `src/[Vendor]/Bundle/[Name]Bundle/Entity/`
- [ ] All properties have `#[ORM\Column]` or relationship attributes
- [ ] Primary key has `#[ORM\Id]` + `#[ORM\GeneratedValue]`
- [ ] All nullable fields have `nullable: true` in the mapping
- [ ] Getters and setters exist for all properties
- [ ] **Migration created** to build the database table (see `migrations.md`)
- [ ] If entity needs UI management: implements `ExtendEntityInterface`, uses `ExtendEntityTrait`, has `#[Config]`
- [ ] Run `php bin/console oro:migration:load` to apply schema
- [ ] Run `php bin/console cache:clear` after any config changes

---

## Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Forgetting `#[ORM\Entity]` | Doctrine ignores the class | Add attribute to class declaration |
| No migration after entity creation | Entity class exists but no DB table | Create and run migration (see `migrations.md`) |
| Non-nullable property with no default | DB insert fails | Add `nullable: true` or set PHP default value |
| Missing `onDelete` on FK | Deleting related entity causes FK violation | Add `onDelete: 'SET NULL'` or `'CASCADE'` |
| Using `nullable: false` on new column in existing table | Migration fails (existing rows have no value) | Make nullable or provide default in migration |
| Forgetting `ExtendEntityTrait` | Extended fields silently fail | Add `use ExtendEntityTrait;` inside class body |

---

## Next Steps

1. Create a database migration: see `migrations.md`
2. Configure entity metadata (routing, icon, security): see `configure-entities.md`
3. Add extended/custom fields: see `extend-entities.md`
4. Build CRUD pages: see `crud-and-routing.md`
