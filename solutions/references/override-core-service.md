# Solution approach and overriding a core service

## 1. Solution-approach hierarchy

When solving a form-rendering / option-shaping problem, prefer in this order:

1. **Entity config** (`entity_configs.yml` `form.type` / `form.form_options`) — declarative, no PHP.
2. **Symfony form-type extension** — configure the type itself to accept/transform options.
3. **Service decorator** — last resort.

A decorator that strips a form type's `choices`/`configs` options to force a render is a bad
solution — do it instead via `form.type` in `entity_configs.yml` (e.g. forcing a boolean extend
field to `CheckboxType`) plus a small type extension calling `setDefined(['choices', 'configs'])`.

For overriding an Oro **core service method** (a different domain than form/config), the ranking
is **aspect interceptor > Symfony decorator** — see below.

## 2. Overriding an Oro core service — prefer the aspect interceptor

When you want to wrap / filter / mutate the behaviour of an Oro core service method, default to
the project's `aaxis_aspect.interceptor` pattern (Aaxis AspectBundle) before reaching for
Symfony's `decorates:`. Use a Symfony decorator only when **no downstream consumer typehints the
concrete class** of the decorated service. Check with `aaxis-oro atlas unsafe <Class>` (e.g. `aaxis-oro atlas unsafe ProductRepository`) (atlas skill). Run atlas first even for investigation, before reading vendor/.

**Why decorators bite on Oro:** many Oro consumers typehint the **concrete class**
(e.g. `WorkflowAclExtension::__construct(... WorkflowAclMetadataProvider $provider)`). A
composition-based decorator (clean interface approach) fails the type contract at container
compile time — `TypeError: Argument #N must be of type Foo, FooDecorator given` on first page
load. Forcing the decorator to `extends` the original works but couples you to forwarding the
parent constructor signature, which breaks on every Oro upgrade that adds a dependency.

The aspect interceptor's compiler pass generates a proxy that **extends the target class**, so
the type contract holds automatically and you never reference the original class or its ctor:

Put the interceptor in the folder mirroring the intercepted class, never a generic
`Interceptor/`.

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

**Interceptors must be stateless.** The generated proxy reuses ONE interceptor instance for every call of the
intercepted method, so never keep per-call data (arguments, results, flags) in properties; use locals and the
`MethodInvocation` only. Constructor-injected collaborators are fine.

Test it directly: instantiate the interceptor in PHPUnit, mock `MethodInvocation` to return the
payload, assert on the output — no container needed.

