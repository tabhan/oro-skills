# OroCommerce: Enum-Extend Field Storage Convention (Buckman-specific)

> This file previously mirrored https://doc.oroinc.com/master/backend/entities/extend-entities/
> in full. That generic material (ExtendEntityInterface/Trait, migrations for extend fields,
> associations, validation, form types) duplicates the official oroinc/ai-dev-platform plugin's
> reference docs and Oro's own documentation, so it was removed. What remains below is a real,
> project-specific gotcha this environment hit with serialized enum fields.

## AGENT QUERY HINTS

This file answers:
- Why does an enum-extend filter return "no results" with no DQL error?
- Why does reading an enum-extend field throw `EntityNotFoundException`?
- What is the correct stored format for a serialized enum field's value?
- Which `ExtendHelper` / `EnumOptionsProvider` methods should I use vs. avoid?

---

## Working with Enum Values (Storage, Forms, Grids, Templates)

`addEnumField` defaults to `is_serialized: true`, so enum values live in the entity's
`serialized_data` JSON column rather than a dedicated FK column. Oro has one canonical
storage format and a small set of utilities — diverging from them breaks filters, grids,
and entity references.

### The one storage format

The serialized JSON value is the **full EnumOption id**: `<enum_code>.<internal_id>`.

```jsonc
// CORRECT — what Oro writes via getEnumChoicesByCode + setStatus($formValue)
{ "status": "document_status.draft" }

// WRONG — bare internal id; breaks Product-style filters and EnumOption references
{ "status": "draft" }
```

If a project ever wrote bare internal ids, every read site needs ad-hoc prefixing and
every grid filter has to be hand-rolled. Fix the form (use `getEnumChoicesByCode`) and
either reinstall (data fixtures rewrite) or write a one-shot
`UPDATE ... jsonb_set(serialized_data, '{field}', to_jsonb('code.' || (sd->>'field')))`.

### Forms — the right choice provider

```php
// FormType
$builder->add('status', ChoiceType::class, [
    'choices' => $this->enumOptionsProvider->getEnumChoicesByCode('document_status'),
    // returns [translatedLabel => 'document_status.draft', ...]
]);
```

Never use `getEnumInternalChoicesByCode` for an entity-bound form field — its values are
bare internal ids, which Oro then writes verbatim into `serialized_data`, drifting from
the convention. Reserve `getEnumInternalChoicesByCode` for non-persisted concerns
(toggling related form fields by chosen format, exposing internal ids to a layout, etc.).

### Setting / reading values from PHP

```php
use Oro\Bundle\EntityExtendBundle\Tools\ExtendHelper;

// Setting — always pass the full id; ExtendHelper builds it for you
$resource->setResourceFormat(
    ExtendHelper::buildEnumOptionId('buckman_resource_format', 'video')
);

// Reading — entity getter returns EnumOptionInterface; getId() is the full id
$fullId     = $resource->getResourceFormat()?->getId();          // 'buckman_resource_format.video'
$internalId = ExtendHelper::getEnumInternalId((string) $fullId); // 'video'
```

`ExtendHelper::buildEnumOptionId()` and `ExtendHelper::getEnumInternalId()` are the only
two utilities you should reach for — manual `'code.' . $internalId` concatenation and
`explode('.', ...)` are duplication.

### Datagrid pattern — copy `oro_product.inventory_status`

```yaml
# vendor/oro/commerce/src/Oro/Bundle/ProductBundle/Resources/config/oro/datagrids.yml
columns:
    inventory_status:
        label:         oro.product.inventory_status.label
        frontend_type: select                 # renders the matching choice label
        data_name:     inventory_status       # bare field name — matches the SELECT alias
        choices:       "@oro_entity_extend.enum_options_provider->getEnumChoicesByCode('prod_inventory_status')"
        translatable_options: false
filters:
    columns:
        inventory_status:
            type:      enum                   # NOT 'choice' — Oro's EnumFilter handles dictionaries
            data_name: inventory_status
            enum_code: prod_inventory_status
```

Why this works without a JOIN or custom DQL:

- The grid declares `extended_entity_name`, so `SerializedFieldsExtension` runs and
  appends `CAST(JSON_EXTRACT(p.serialized_data, 'inventory_status') AS varchar) AS inventory_status`
  to the SELECT for every serialized enum field on the entity.
- Column `data_name: inventory_status` matches that alias → the rendered cell value is the
  full id, which `frontend_type: select` maps to the translated label via `choices`.
- Filter `data_name: inventory_status` uses the same alias, and the `enum` filter type
  populates the dictionary from `enum_code`. The dictionary returns full ids, the column
  stores full ids, so the `IN (…)` comparison just works.
- Don't add a sorter for serialized enums — there's no real column to sort on.

### Twig — render and compare

```twig
{# Display: getId() is the full id; trans_enum looks up the translation directly #}
{{ entity.status.getId()|trans_enum }}

{# Compare to an internal id when you need to branch on it #}
{% set kind = entity.status.getId()|split('.')|last %}
{% if kind == 'video' %} … {% endif %}
```

### Common pitfalls actually hit in this project

- **Filter returns "no results"** with no DQL error → values were stored as bare internal
  ids; the form passed `getEnumInternalChoicesByCode` keys. Fix the form, then migrate
  existing rows (or reinstall).
- **`EntityNotFoundException` when reading** the enum → an EnumOption reference was created
  with a bare internal id. Same root cause; same fix.
- **`type: choice` in the filter** for a serialized enum → works only if you also hand-roll
  a JSON_EXTRACT data_name and provide internal-id choices. The OOTB `type: enum` path
  is shorter and the one Oro maintains.
- **Custom twig column template** that prepends `<enum_code>.` to `record.value(field)` →
  drop it, switch the column to `frontend_type: select` with `getEnumChoicesByCode`.
- **Column displays empty / wrong label** → choice keys/values don't match the stored
  format. Verify `serialized_data->>field` returns a full id.
