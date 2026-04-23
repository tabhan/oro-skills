# Service Overrides & Extension Patterns

## Rule 1: `autowire: true` is forbidden

Always declare arguments explicitly in `services.yml`. Autowiring hides the dependency
graph, makes upgrades fragile, and conflicts with Oro's service alias patterns.

```yaml
# BAD
my.service:
    class: App\MyService
    autowire: true

# GOOD
my.service:
    class: App\MyService
    arguments:
        - '@doctrine.orm.entity_manager'
        - '@oro_security.acl_helper'
```

## Rule 2: Never inject `@doctrine` directly

Use the doctrine helper service instead. ORM > QueryBuilder > DBAL > raw SQL.

```yaml
arguments:
    - '@oro_entity.doctrine_helper'   # preferred
    # NOT - '@doctrine'
```

Add `use` imports; never use inline full class paths in PHP.

## Rule 3: Extend OOTB services with the interceptor pattern

When changing behavior of an Oro service, prefer **interface implementation +
`decorates:`** over event listeners or voters.

```yaml
# Original service: oro_some.service (implements SomeInterface)
# Your interceptor:
app.some.service.decorator:
    class: App\SomeServiceDecorator
    decorates: oro_some.service
    arguments:
        - '@.inner'
        - '@other.dep'
```

Your decorator implements `SomeInterface`, accepts the original service as `$inner`,
and forwards or intercepts calls. Listeners/voters are too loose for most extension
needs — decoration expresses the contract precisely.

## Rule 4: Extract DB queries to repositories

Never inline DQL/QueryBuilder in services, listeners, or commands.

### For Oro entities (extended via EntityExtendBundle)

Declare `customRepositoryClassName` in `entity_extend.yml`:

```yaml
Oro\Bundle\SomeBundle\Entity\SomeEntity:
    customRepositoryClassName: App\Entity\Repository\SomeRepository
```

### For custom entities

Set the repository on the entity mapping directly (attribute or YAML).

### Repository service override (when Oro also registers it as a service)

Check whether Oro registers the repository as a Symfony service (e.g.
`oro_product.repository.product` → `Oro\…\ProductRepository`). If it does, the
custom repository service must:

1. Use `parent: oro_entity.abstract_repository` with the entity class as argument:
   ```yaml
   App\Entity\Repository\SomeRepository:
       parent: oro_entity.abstract_repository
       arguments:
           - 'Oro\Bundle\SomeBundle\Entity\SomeEntity'
   ```
2. Alias-override both the Oro FQCN and the short service ID:
   ```yaml
   oro_some.repository.some: '@App\Entity\Repository\SomeRepository'
   Oro\Bundle\SomeBundle\Entity\Repository\SomeRepository: '@App\Entity\Repository\SomeRepository'
   ```

Without the service alias override, the short service ID still resolves to Oro's
original repository class.
