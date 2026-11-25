# Form Handler — `oro_form.form.handler` tag

`UpdateHandlerFacade` resolves the per-form handler by string alias: register the handler as a service tagged
`oro_form.form.handler` with an `alias`, and pass that alias as the 5th argument to `update()`.

## Interface

```php
namespace Oro\Bundle\FormBundle\Form\Handler;

interface FormHandlerInterface
{
    public function process(mixed $data, FormInterface $form, Request $request): bool;
}
```

Return `true` on successful save, `false` if not submitted or invalid.

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

Oro's default `FormHandler` does `$form->setData($data)` before `submitPostPutRequest`, assuming the form's
`data_class` is the entity. If your form binds to an array (e.g. later mapped via
`$submission->setFormData((array) $form->getData())`), `setData(Submission)` tries to read `$submission->message` and
blows up. Skip `setData`; just `handleRequest`.

## Service registration

```yaml
# Resources/config/services.yml
services:
    # Alias "acme_xyz_form" is what the controller passes to UpdateHandlerFacade::update(...).
    acme_xyz.form.handler.xyz_form:
        class: Acme\Bundle\XyzBundle\Form\Handler\XyzFormHandler
        arguments:
            - '@oro_entity.doctrine_helper'
        tags:
            - { name: oro_form.form.handler, alias: acme_xyz_form }
```

## What `UpdateHandlerFacade` accepts as `$formHandler`

```php
$update = $this->updateFactory->createUpdate($data, $form, $formHandler, $resultProvider);
```

- `null`: the `default` handler (`Oro\Bundle\FormBundle\Form\Handler\FormHandler`, full event lifecycle with transaction support).
- `string`: alias lookup via the `oro_form.form.handler` tag registry.
- `callable`: invoked as `($data, $form, $request)`.
- `FormHandlerInterface`: used directly.

For dialog forms use the string alias: the handler usually has domain duties (async jobs, integration records) the
default event-based handler doesn't cover.
