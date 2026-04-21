# Form Handler — `oro_form.form.handler` tag

`UpdateHandlerFacade` resolves the per-form handler by string alias. You
register your handler as a service tagged `oro_form.form.handler` with an
`alias` attribute, then pass that alias as the 5th argument to `update()`.

## Interface

```php
namespace Oro\Bundle\FormBundle\Form\Handler;

interface FormHandlerInterface
{
    public function process(mixed $data, FormInterface $form, Request $request): bool;
}
```

Return `true` on successful save, `false` if the form was not submitted or was
invalid.

## Canonical implementation

```php
<?php

namespace Acme\Bundle\XyzBundle\Form\Handler;

use Oro\Bundle\EntityBundle\ORM\DoctrineHelper;
use Oro\Bundle\FormBundle\Form\Handler\FormHandlerInterface;
use Symfony\Component\Form\FormInterface;
use Symfony\Component\HttpFoundation\Request;

class XyzFormHandler implements FormHandlerInterface
{
    public function __construct(
        private readonly DoctrineHelper $doctrineHelper,
    ) {
    }

    #[\Override]
    public function process($data, FormInterface $form, Request $request): bool
    {
        if (!in_array($request->getMethod(), ['POST', 'PUT'], true)) {
            return false;
        }

        $form->handleRequest($request);

        if (!$form->isSubmitted() || !$form->isValid()) {
            return false;
        }

        // Your persist logic. Prefer separate EMs if the main save and the
        // downstream (e.g. integration-record) save must commit independently
        // — the MQ consumer needs the committed ID before the message is picked up.
        $em = $this->doctrineHelper->getEntityManagerForClass($data::class);
        $em->persist($data);
        $em->flush();

        return true;
    }
}
```

### Do NOT call `$form->setData($data)` if the form isn't bound to the entity

Oro's default `FormHandler` does `$form->setData($data)` before `submitPostPutRequest`.
That assumes the form's `data_class` matches the entity. If your form binds to
an array (e.g. mapped to `$submission->setFormData((array) $form->getData())`
downstream), calling `setData(Submission)` will try to read `$submission->message`
and blow up. Skip `setData` and just `handleRequest`.

## Service registration

```yaml
# Resources/config/services.yml
services:
    # Persists the submission, dispatches integration work, etc.
    # Alias "acme_xyz_form" is what the controller passes to
    # UpdateHandlerFacade::update(...).
    acme_xyz.form.handler.xyz_form:
        class: Acme\Bundle\XyzBundle\Form\Handler\XyzFormHandler
        arguments:
            - '@oro_entity.doctrine_helper'
        tags:
            - { name: oro_form.form.handler, alias: acme_xyz_form }
```

## What `UpdateHandlerFacade` does with the alias

```php
$update = $this->updateFactory->createUpdate($data, $form, $formHandler, $resultProvider);
```

`$formHandler` can be:

- `null` — use the `default` handler (`Oro\Bundle\FormBundle\Form\Handler\FormHandler`
  which dispatches the full event lifecycle with transaction support).
- `string` — alias lookup via the `oro_form.form.handler` tag registry.
- `callable` — invoked as `($data, $form, $request)`.
- `FormHandlerInterface` — used directly.

For dialog forms you almost always want the string-alias path, since your
handler usually has domain responsibilities (e.g. dispatch async jobs, emit
integration records) that the default event-based handler doesn't cover.
