# Enum-extend field storage convention (Buckman-specific)

## Working with Enum Values (Storage, Forms, Grids, Templates)

`addEnumField` defaults to `is_serialized: true`, so enum values live in the entity's `serialized_data` JSON column,
not a dedicated FK column. Diverging from Oro's one storage format and utilities breaks filters, grids and entity
references.

### The one storage format

The serialized JSON value is the **full EnumOption id**: `<enum_code>.<internal_id>`.

```jsonc
// CORRECT — what Oro writes via getEnumChoicesByCode + setStatus($formValue)
{ "status": "document_status.draft" }

// WRONG — bare internal id; breaks Product-style filters and EnumOption references
{ "status": "draft" }
```

If bare internal ids were ever written, fix the form (use `getEnumChoicesByCode`) and either reinstall (data
fixtures rewrite) or run a one-shot
`UPDATE ... jsonb_set(serialized_data, '{field}', to_jsonb('code.' || (sd->>'field')))`.

### Forms — the right choice provider

```php
// FormType
$builder->add('status', ChoiceType::class, [
    'choices' => $this->enumOptionsProvider->getEnumChoicesByCode('document_status'),
    // returns [translatedLabel => 'document_status.draft', ...]
]);
```

Never use `getEnumInternalChoicesByCode` for an entity-bound form field: its values are bare internal ids that Oro
writes verbatim into `serialized_data`. Reserve it for non-persisted concerns (toggling related form fields by
chosen format, exposing internal ids to a layout).

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

Use only `ExtendHelper::buildEnumOptionId()` and `ExtendHelper::getEnumInternalId()`; manual `'code.' . $internalId`
concatenation and `explode('.', ...)` are duplication.

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

No JOIN or custom DQL is needed: the grid declares `extended_entity_name`, so `SerializedFieldsExtension` appends
`CAST(JSON_EXTRACT(p.serialized_data, 'inventory_status') AS varchar) AS inventory_status` to the SELECT for every
serialized enum field. The column and filter `data_name` match that alias; `frontend_type: select` maps the full id
to its label via `choices`, and the `enum` filter's dictionary (from `enum_code`) returns full ids, so `IN (...)`
works. Don't add a sorter for serialized enums (no real column to sort on).

### Twig — render and compare

```twig
{# Display: getId() is the full id; trans_enum looks up the translation directly #}
{{ entity.status.getId()|trans_enum }}

{# Compare to an internal id when you need to branch on it #}
{% set kind = entity.status.getId()|split('.')|last %}
{% if kind == 'video' %} … {% endif %}
```

### Pitfalls actually hit

- **Filter returns "no results"** with no DQL error: values were stored as bare internal ids (the form passed
  `getEnumInternalChoicesByCode` keys). Fix the form, then migrate existing rows (or reinstall).
- **`EntityNotFoundException` when reading**: an EnumOption reference was created with a bare internal id. Same root cause and fix.
- **`type: choice` in the filter** works only with a hand-rolled JSON_EXTRACT `data_name` and internal-id choices; use the OOTB `type: enum`.
- **Custom twig column template** prepending `<enum_code>.` to `record.value(field)`: drop it, use `frontend_type: select` with `getEnumChoicesByCode`.
- **Column empty / wrong label**: choice keys/values don't match the stored format. Verify `serialized_data->>field` returns a full id.
