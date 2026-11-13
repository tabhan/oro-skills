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

## Rule 3: Override an Oro core service method with the aspect interceptor

To change the behavior of a method on an Oro core service, use the **aspect
interceptor** — not a class swap, and not `decorates:`.

```yaml
services:
    App\Interceptor\SomeServiceInterceptor:
        tags:
            - { name: aaxis_aspect.interceptor }
```

The interceptor declares a `#[Pointcut]` naming the target class and method, and the
AspectBundle weaves it in. Place it in the folder mirroring the intercepted class,
never a generic `Interceptor/`.

**Why not `decorates:`** — a Symfony decorator replaces the service with a different
concrete class. Any downstream consumer that typehints the ORIGINAL concrete class
(Oro core does this in places) then gets a `TypeError` at container compile time. A
decorator is acceptable ONLY when no consumer typehints the decorated concrete class;
the interceptor has no such failure mode because the original class is still what is
instantiated.

Listeners and voters remain too loose for most extension needs — reach for them only
when the extension point genuinely is an event.

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
