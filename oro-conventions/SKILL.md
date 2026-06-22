---
name: oro-conventions
description: >-
  Practical, opinionated OroCommerce development conventions and hard-won gotchas, reusable
  across Oro projects. Covers Doctrine/repository access, the solution-approach hierarchy,
  service-override patterns (aspect interceptor vs Symfony decorator), Symfony form-type
  registration, storefront localization, entity-config seeding, PHPUnit entity stubs, runtime
  debugging, custom datagrid/report pitfalls, Postgres jsonb migration coercion, Oro
  workflow-data encoding, and asset-version cache busting. Use this skill WHEN writing or
  reviewing Oro PHP / YAML / Twig and you want the established pattern instead of guessing —
  especially before injecting Doctrine, overriding a core service, adding a form type, reading
  localized values on the storefront, seeding entity config, writing PHPUnit tests for
  entities, building a custom report grid, creating a jsonb column, or rebuilding assets.
  Complements oro-workflow (dev-loop commands) and oro-backend-docs (API reference).
---

# Oro Development Conventions

Distilled, cross-project conventions for OroCommerce work. These are decisions and gotchas that
cost real debugging time to discover; reach for the documented pattern rather than re-deriving it.
Examples reference the Aaxis/Buckman bundle family where a project-specific tool is involved —
substitute your project's equivalent, but the underlying Oro/Symfony behaviour is the same on
every Oro stack.

---

## 1. Doctrine access — always via `DoctrineHelper`

Never inject `@doctrine` or its `ManagerRegistry` directly into a service. Inject
`@oro_entity.doctrine_helper` (`Oro\Bundle\EntityBundle\ORM\DoctrineHelper`) and use its accessors:

- `getEntityManagerForClass(Foo::class)` — replaces `$registry->getManagerForClass(...)`
- `getEntityRepositoryForClass(Foo::class)` — replaces `$em->getRepository(...)`
- `getSingleEntityIdentifier($entity)` — single-call id resolution

```php
use Oro\Bundle\EntityBundle\ORM\DoctrineHelper;

public function __construct(private readonly DoctrineHelper $doctrineHelper) {}
```
```yaml
arguments: ['@oro_entity.doctrine_helper']
```

`@doctrine` *is* the `ManagerRegistry` service id, so injecting `ManagerRegistry` subverts the
rule. Prefer ORM/QueryBuilder over raw SQL, and keep DQL/QueryBuilder in repository classes —
never inline in services, listeners, or commands. Any existing `ManagerRegistry`/`@doctrine`
usage is a regression; replace it at first touch.

---

## 2. Solution-approach hierarchy

When solving a form-rendering / option-shaping problem, prefer in this order:

1. **Entity config** (`entity_configs.yml` `form.type` / `form.form_options`) — declarative, no PHP.
2. **Symfony form-type extension** — configure the type itself to accept/transform options.
3. **Service decorator** — last resort.

A decorator that strips a form type's `choices`/`configs` options to force a render is a bad
solution. Example done right: forcing a boolean extend field to render as `CheckboxType` via
`form.type` in `entity_configs.yml` plus a small type extension calling
`setDefined(['choices', 'configs'])` — not by decorating the options provider.

For overriding an Oro **core service method** (a different domain than form/config), the ranking
is **aspect interceptor > Symfony decorator** — see §3.

---

## 3. Overriding an Oro core service — prefer the aspect interceptor

When you want to wrap / filter / mutate the behaviour of an Oro core service method, default to
the project's `aaxis_aspect.interceptor` pattern (Aaxis AspectBundle) before reaching for
Symfony's `decorates:`. Use a Symfony decorator only when **no downstream consumer typehints the
concrete class** of the decorated service.

**Why decorators bite on Oro:** many Oro consumers typehint the **concrete class**
(e.g. `WorkflowAclExtension::__construct(... WorkflowAclMetadataProvider $provider)`). A
composition-based decorator (clean interface approach) fails the type contract at container
compile time — `TypeError: Argument #N must be of type Foo, FooDecorator given` on first page
load. Forcing the decorator to `extends` the original works but couples you to forwarding the
parent constructor signature, which breaks on every Oro upgrade that adds a dependency.

The aspect interceptor's compiler pass generates a proxy that **extends the target class**, so
the type contract holds automatically and you never reference the original class or its ctor:

```php
class FooBarInterceptor
{
    #[Pointcut]
    public function targetMethodName(MethodInvocation $invocation): SameTypeAsTarget
    {
        $result = $invocation->proceed();
        return /* filtered / mutated */ $result;
    }
}
```
```yaml
buckman_x.foo_bar_interceptor:
    class: Buckman\Bundle\XBundle\...\FooBarInterceptor
    tags:
        - { name: aaxis_aspect.interceptor, service: <oro_target_service_id> }
```

Test it directly: instantiate the interceptor in PHPUnit, mock `MethodInvocation` to return the
payload, assert on the output — no container needed. Use a Symfony decorator only for
interface-only contracts with no concrete-class typehints downstream.

---

## 4. Symfony form types — no service entry unless they inject

Do **not** register a `FormType` (or a `Constraint` attribute class) in `services.yml` unless it
has constructor dependencies. Symfony resolves dependency-less form types by FQCN via
auto-instantiation; a `form.type`-tagged entry for one is dead weight. Reference it directly by
FQCN in `form_type:` declarations. Add a service entry only when the type needs `@some_service`
in its constructor (then tag it `form.type`); only a Validator counterpart of a Constraint needs
a service when it injects.

**Leaf-type pattern:** when a custom type is just "a base type + a fixed set of constraints",
make it a leaf — `getParent()` returns the base type (e.g. `TextareaType::class`), no
`buildForm()`, constraints in `configureOptions()`. The field name belongs to the *outer* form /
workflow attribute, not inside the custom type. Declaring a same-named sub-field inside the
custom type creates a redundant compound form.

---

## 5. Storefront localization — never `getDefault*()`

On the storefront (frontend layouts, Twig, JS) never read localized-fallback-value fields via
`getDefaultName()` / `getDefaultDescription()` / etc. Use the locale-aware accessor:

```yaml
# layout YAML
productName: '=data["locale"].getLocalizedValue(data["product"].getNames())'
```
```twig
{{ product.names|localized_value }}
```

`getDefaultName()` returns the LFV row where `localization === null` and ignores the customer's
current locale — wrong language on a multi-locale site, and an outright `null`→`.getString()`
500 if a snapshot/overlay path has no default row. Grep frontend layout/Twig/JS for
`getDefault*()` on any `LocalizedFallbackValueAwareInterface` entity (Product, Category,
ContentNode, …) and replace it. Admin-only datagrids/forms and backend slug/typeahead handlers
may keep `getDefault*()` — admins see the source default row; the rule is storefront-only.

---

## 6. Entity-config seeding — one `entity_configs.yml` per bundle

For seeding entity-config values (form type/options, scopes), use the established
`AbstractSetEntityConfigs` mechanism (Aaxis EntityExtendBundle) — do not fork a parallel YAML
with a one-off fixture.

- Edit the bundle's `Migrations/Data/ORM/data/entity_configs.yml`, adding scope keys under
  `EntityClass: fields: fieldName:`.
- Bump `getVersion()` on the global `SetEntityConfigs` data fixture so
  `oro:migration:data:load` re-runs it.
- For a new entity-config scope schema, declare it in the bundle's
  `Resources/config/oro/entity_config.yml`.

A single global loader fixture walks every bundle for the named file and merges the parsed
results, so each bundle just contributes its own slice.

---

## 7. PHPUnit — stub classes for entities, not `createMock`

For Oro entities/models in unit tests, use **Stub classes**, not `createMock()`/`createStub()`.
Entity-extend weaves accessors (e.g. `Product::getLocalizations()`) onto the class at runtime,
but unit tests load the **un-extended** class — so `createMock(Product::class)->method('getLocalizations')`
throws `MethodCannotBeConfiguredException`. Same for final accessors like
`AbstractLocalizedFallbackValue::getLocalization()`.

- Keep shared stubs under `Tests/Unit/Stub/` (e.g. a `ProductStub` with `setId()`,
  `setStubbedLocalizations()`, array-returning `getLocalizations()`); for per-test variants wrap
  the stub in an anonymous subclass overriding `getId`/`getType`/`getAttributeFamily`.
- Set ids by reflection (`(new \ReflectionProperty(Localization::class, 'id'))->setValue(...)`)
  rather than mocking a getter where the sibling pattern already does so.
- Don't stub a method the code-under-test never calls when the collaborator is itself mocked —
  just make the object an `instanceof`.

---

## 8. Runtime debugging — logger + `oro:logger:level`, never edit monolog

To trace why a runtime behaviour misfires (precondition denying, voter rejecting, autocomplete
returning wrong rows):

1. Inject `Psr\Log\LoggerInterface` into the suspect class (real `@logger` in services.yml; pass
   `new NullLogger()` only in unit tests — do not default to `NullLogger`).
2. Add `$this->logger->debug('ClassName.event', [...inputs/outputs...])` at branching points,
   using stable `ClassName.event` label prefixes so greps stay clean across sessions. Log the
   inputs/outputs of decisions, not whole object graphs.
3. Toggle at runtime — **never** edit `config_prod.yml` fingers_crossed/min_level:
   ```bash
   c oro:logger:level debug '15 minutes'    # enable (a \DateInterval string)
   c oro:logger:level warning '0 seconds'   # revert immediately
   ```
   This flips a system-config setting Oro's monolog processor reads — no FPM restart, no cache clear.
4. Truncate the log, trigger the flow, `grep -E 'YourClass\.|YourLabel' var/logs/prod.log`.
5. Revert the level when done; keep the logger injection (good for next time).

---

## 9. Custom datagrid / report grid pitfalls

Found the hard way building admin report grids; unit tests pass while the live grid is broken:

- **Rebuild the right cache.** `datagrids.yml` compiles into
  `var/cache/<env>/oro/datagrids/<grid>.php`; the web app serves **prod**, so a change shows the
  OLD grid until `bin/console cache:clear --env=prod`. Test-only console commands need the
  **test** cache. A stale `var/cache/tes_` dir can persist the old command set even after
  `cache:clear --env=test` → `rm -rf var/cache/test var/cache/tes_` then `cache:warmup --env=test`.
- **`apply_callback` must be the array form** `['@service_id', 'method']`. The string form
  `'@service->method'` is eager-resolved by `SystemAwareResolver` at config-compile time (it calls
  the method with the grid *name*) → `TypeError`/500.
- **Never `GROUP BY` a `json` column** (Postgres 42883 "no equality operator for type json"). The
  pager COUNT query inherits the SELECT, so even a working display query 500s the count → grid
  shows 0 rows. For to-one joins, bind the scalar directly instead of aggregate+GROUP BY.
- **The grid TOOLBAR is a sibling of `.grid-container`, not a child.** Filters (behind the
  `toggle-filters-action` `fa-filter` button), sorters, pagination `.totals-label`, and the OOTB
  CSV export launcher all live in `.grid-toolbar`. Selectors scoped under `.grid-container` miss
  them. Read grid metadata from the raw server HTML (`fetch(location.href)`), not the live DOM —
  Oro consumes `data-page-component-*` attrs after init.

For **serialized enum** columns/filters, copy `oro_product.inventory_status` (full-id storage,
`frontend_type: select` + `getEnumChoicesByCode`, `type: enum` filter with `enum_code`) — see
oro-backend-docs § Working with Enum Values.

---

## 10. Postgres `jsonb` migration coercion

Oro's migration diff pipeline (DBAL 3.10 + Oro 7) **drops** the jsonb flag —
`addColumn('x','json',['customSchemaOptions'=>['jsonb'=>true]])` and the ORM `options:['jsonb'=>true]`
both yield a physical `json` column (proof: Oro's own `oro_workflow_definition.metadata` is
declared jsonb yet is physically `json`). A `GIN (jsonb_path_ops)` index and the `@>` operator
require jsonb. Pattern that works:

- **Entity:** plain `#[ORM\Column(type: Types::JSON)]` (no jsonb option) — Postgres reverse-maps
  both `json` and `jsonb` to `Types::JSON`, so a physical jsonb column introspects drift-free.
- **Migration + Installer:** add the column as plain `'json'`, then a raw
  `ALTER TABLE t ALTER COLUMN c TYPE jsonb USING c::jsonb`, then
  `CREATE INDEX IF NOT EXISTS ... USING gin (c jsonb_path_ops)`. A successful GIN create is itself
  proof the column is jsonb. Always update the bundle Installer too (bump `getMigrationVersion()`).

---

## 11. Oro workflow data is base64(serialize()), not jsonb

`oro_workflow_item.data` is a **text** column owned by Oro. Oro JSON-encodes the envelope, but
every attribute declared `type: array`/`type: object` is run through
`StandardAttributeNormalizer::serialize()` = `base64_encode(serialize($value))`. Oro workflows
have **no `type: json`** — arrays are always base64+PHP-serialized at rest. App code never sees
this (it reads `$workflowItem->getData()->get(...)` after Oro deserializes), and production never
SQL-queries it. Do **not** migrate workflow-data attributes to jsonb or override the core
normalizer; leave round-scoped, never-SQL-queried workflow state on the standard mechanism. Use
your own jsonb column (§10) only for data you actually need to query in SQL.

---

## 12. Asset-version cache busting after a build

After rebuilding webpack assets (`oro:assets:build` + `assets:install --symlink`), the
`?v=<hash>` in `public/build/build_version.txt` does **not** change automatically. Browsers keep
the old `app.js` under the stale `?v=`, and an SRI integrity mismatch then **blocks** the script
(`Failed to find a valid digest in the 'integrity' attribute` → `ReferenceError: loadModules is
not defined`). Fix: run `composer run set-assets-version` to bump the version so every asset URL
refetches with a consistent integrity hash. Separately, a native nginx `open_file_cache` can
serve stale precompressed bytes right after a build (transient SRI mismatch) — the version bump
is the durable cure.
