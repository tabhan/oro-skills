# Solution approach and overriding a core service

## Solution-approach hierarchy (form rendering / option shaping)

1. **Entity config** (`entity_configs.yml` `form.type` / `form.form_options`): declarative, no PHP.
2. **Symfony form-type extension**: configure the type itself to accept/transform options.
3. **Service decorator**: last resort.

A decorator that strips a form type's `choices`/`configs` options to force a render is a bad solution. Use
`form.type` in `entity_configs.yml` (e.g. a boolean extend field forced to `CheckboxType`) plus a small type
extension calling `setDefined(['choices', 'configs'])`.

## Overriding an Oro core service method: aspect interceptor over decorator

This is the canonical statement of the rule. To wrap / filter / mutate an Oro core service method, default to the
project's `aaxis_aspect.interceptor` (Aaxis AspectBundle) before `decorates:`. Use a Symfony decorator only when **no
downstream consumer typehints the concrete class** of the decorated service; check with
`aaxis-oro atlas unsafe <Class>` (e.g. `ProductRepository`). Run atlas first even for investigation, before reading `vendor/`.

**Why decorators bite on Oro:** many consumers typehint the **concrete class** (e.g. `WorkflowAclExtension::__construct(... WorkflowAclMetadataProvider $provider)`).
A composition decorator fails at container compile time: `TypeError: Argument #N must be of type Foo, FooDecorator given`.
A decorator that `extends` the original works but must forward the parent constructor, which breaks on every Oro
upgrade that adds a dependency. The interceptor's compiler pass generates a proxy that **extends the target class**,
so the type contract holds and you never reference the original class or its constructor.

Put the interceptor in a folder mirroring the intercepted class, never a generic `Interceptor/`.

```php
use Aaxis\Bundle\AspectBundle\Annotations\Pointcut;

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
    class: Acme\Bundle\XBundle\...\FooBarInterceptor
    tags:
        - { name: aaxis_aspect.interceptor, service: <oro_target_service_id> }
```

**Interceptors must be stateless.** The generated proxy reuses ONE instance for every call, so keep per-call data
(arguments, results, flags) in locals and the `MethodInvocation`, never in properties. Constructor-injected
collaborators are fine. Listeners and voters are too loose for most extension needs; use them only when the
extension point genuinely is an event.

Test it directly: instantiate the interceptor in PHPUnit, mock `MethodInvocation` to return the payload, assert on
the output; no container needed.
