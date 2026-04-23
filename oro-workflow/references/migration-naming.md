# Migration Class Naming

Migration class names must match the **bundle class**, not describe the change.

## Rule

For bundle `Foo\Bundle\BarBundle\FooBarBundle`, migration files at
`Migrations/Schema/v1_N/` must be named `FooBarBundle.php` and contain a class named
`FooBarBundle`.

## Examples

| Bundle | Migration path | Class name |
|--------|----------------|------------|
| `Buckman\Bundle\CMSBundle\BuckmanCMSBundle` | `Migrations/Schema/v1_6/BuckmanCMSBundle.php` | `BuckmanCMSBundle` |
| `Buckman\Bundle\ProductBundle\BuckmanProductBundle` | `Migrations/Schema/v1_10/BuckmanProductBundle.php` | `BuckmanProductBundle` |
| `Aaxis\Bundle\IntegrationBundle\AaxisIntegrationBundle` | `Migrations/Schema/v1_1/AaxisIntegrationBundle.php` | `AaxisIntegrationBundle` |

## Anti-patterns

Do NOT use descriptive names like `AddUniqueIndexToIntegrationRecord.php` or
`FixEntityExtendSchema.php`. Oro's migration loader expects the bundle-name convention
and uses it to derive version order per bundle.

## Installer vs versioned

- `Migrations/Schema/<BundleName>Installer.php` — implements `Installation`, runs once
  on fresh installs; also declares `getMigrationVersion()` returning the highest
  version it covers.
- `Migrations/Schema/v1_N/<BundleName>.php` — implements `Migration`, runs on upgrades
  when current version < v1_N.

When bumping schema:
1. Update the `Installer.php` to include the final state (so fresh installs skip the
   upgrade migration).
2. Add a new `v1_N/<BundleName>.php` with just the delta so existing installs upgrade.
3. Update the installer's `getMigrationVersion()` to return `v1_N`.

## Data migrations

Parallel structure: `Migrations/Data/ORM/<BundleName>Fixture.php` or versioned
variants. Same naming convention — bundle class name, not description.
