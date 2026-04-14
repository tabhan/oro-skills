# OroCommerce: Migration Patterns (Installer + Versioned)

> Source: Project convention + OroMigrationBundle behavior

## AGENT QUERY HINTS

This file answers:
- How do I structure installer vs versioned migration scripts?
- When should I create a new versioned migration vs modify the installer?
- What should the migration class name be?
- How do I bump the installer version?
- What happens on fresh install vs existing database?

---

## Two Types of Schema Migrations

Oro uses **two** migration types that must BOTH be maintained in sync:

### 1. Installer (fresh database)

- Implements `Installation` interface
- Contains **ALL** fields — the complete schema
- `getMigrationVersion()` returns the **latest** version (e.g., `v1_2`)
- On fresh install, Oro runs ONLY the installer, skips all versioned scripts
- One per bundle: `Migrations/Schema/{Bundle}Installer.php`

```php
class BuckmanLocaleBundleInstaller implements Installation, ExtendExtensionAwareInterface
{
    public function getMigrationVersion(): string
    {
        return 'v1_1'; // Must match latest versioned script
    }

    public function up(Schema $schema, QueryBag $queries): void
    {
        // ALL fields from v1_0 + v1_1 + ... go here
    }
}
```

### 2. Versioned Scripts (existing database)

- Implements `Migration` interface
- Contains **ONLY the delta** — new fields for this version
- On existing DB, Oro runs only scripts newer than current version
- One directory per version: `Migrations/Schema/v1_1/`
- **Class name MUST be the bundle class name** (e.g., `BuckmanLocaleBundle`)

```php
namespace Buckman\Bundle\LocaleBundle\Migrations\Schema\v1_1;

class BuckmanLocaleBundle implements Migration
{
    public function up(Schema $schema, QueryBag $queries): void
    {
        // ONLY new fields added in v1_1
    }
}
```

---

## Directory Structure

```
Migrations/Schema/
├── BuckmanLocaleBundleInstaller.php   ← ALL fields, version = v1_1
└── v1_1/
    └── BuckmanLocaleBundle.php        ← Only new v1_1 fields
```

---

## When Adding New Fields

**Always do all three steps:**

1. **Add to installer** — so fresh installs get everything
2. **Create versioned migration** — so existing databases get the delta
3. **Bump installer version** — so Oro knows the installer is current

### Example: Adding url_code to Localization

**Step 1 — Installer** (add url_code alongside existing fields):
```php
// BuckmanLocaleBundleInstaller.php
public function getMigrationVersion(): string
{
    return 'v1_1'; // Bumped from v1_0
}

public function up(Schema $schema, QueryBag $queries): void
{
    $table = $schema->getTable('oro_localization');

    // Existing v1_0 fields
    $this->extendExtension->addEnumField($schema, $table, 'salesOrgs', ...);
    $this->extendExtension->addEnumField($schema, $table, 'region', ...);

    // New v1_1 fields
    $table->addColumn('url_code', 'string', [...]);
    $table->addUniqueIndex(['url_code'], 'uniq_...');
}
```

**Step 2 — Versioned migration** (only new fields):
```php
// v1_1/BuckmanLocaleBundle.php
class BuckmanLocaleBundle implements Migration
{
    public function up(Schema $schema, QueryBag $queries): void
    {
        $table = $schema->getTable('oro_localization');
        $table->addColumn('url_code', 'string', [...]);
        $table->addUniqueIndex(['url_code'], 'uniq_...');
    }
}
```

---

## Why Both Are Required

| Scenario | What Runs | Result if missing |
|----------|-----------|-------------------|
| Fresh install | Installer only | If versioned-only: fields missing on fresh DB |
| Existing DB upgrade | Versioned scripts only | If installer-only: existing DB never gets new fields |
| Re-install (drop + create) | Installer only | Same as fresh install |

---

## Class Naming Rules

| Type | Class Name | Example |
|------|-----------|---------|
| Installer | `{Bundle}Installer` | `BuckmanLocaleBundleInstaller` |
| Versioned | Bundle class name (no suffix) | `BuckmanLocaleBundle` |

**Never use descriptive names** like `AddUrlCodeColumn` for versioned scripts. Oro identifies migrations by class name + version directory.

---

## Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| Only adding to installer | Existing databases never get new fields | Also create versioned script |
| Only creating versioned script | Fresh installs miss fields | Also add to installer |
| Forgetting to bump installer version | Oro thinks installer is outdated | Set `getMigrationVersion()` to latest `v1_X` |
| Using descriptive class names | Breaks Oro's migration tracking | Always use bundle class name |
| Adding fields to wrong installer | Fields end up on wrong entity | Verify table name in `$schema->getTable()` |