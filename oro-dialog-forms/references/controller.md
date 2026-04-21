# Controller — `UpdateHandlerFacade` + dual-mode response

The controller uses `#[Layout]` and delegates the save to `UpdateHandlerFacade`.
**The same controller action serves both GET (dialog open) and POST (AJAX or
standard submit).** The facade decides the response shape based on `_wid`.

## Canonical structure

```php
<?php

namespace Acme\Bundle\XyzBundle\Controller\Frontend;

use Oro\Bundle\FormBundle\Model\UpdateHandlerFacade;
use Oro\Bundle\LayoutBundle\Attribute\Layout;
use Symfony\Component\HttpFoundation\RedirectResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;
use Symfony\Component\Form\FormFactoryInterface;
use Symfony\Contracts\Translation\TranslatorInterface;

class XyzFormController
{
    public function __construct(
        private readonly FormFactoryInterface $formFactory,
        private readonly UpdateHandlerFacade $updateHandlerFacade,
        private readonly TranslatorInterface $translator,
    ) {
    }

    #[Route(
        path: '/xyz/form/{widgetName}',
        name: 'acme_xyz_form',
        methods: ['GET', 'POST']
    )]
    #[Layout]
    public function form(Request $request, string $widgetName = 'default'): array|RedirectResponse
    {
        $entity = new Submission(); // or load by id
        $form   = $this->formFactory->create(XyzFormType::class, null, [/* options */]);

        $result = $this->updateHandlerFacade->update(
            $entity,
            $form,
            $this->translator->trans('acme.xyz.form.submitted.message'),
            $request,
            'acme_xyz_form'                 // handler alias registered via oro_form.form.handler tag
        );

        $isWidget = (bool) $request->get('_wid');

        // Never let the facade redirect in widget context — DialogWidget
        // expects a `.widget-content` HTML payload, not a 30x response.
        if ($result instanceof RedirectResponse && !$isWidget) {
            return $result;
        }

        return [
            'data' => [
                'widget_name' => $widgetName,
                'savedId'     => is_array($result) ? ($result['savedId'] ?? null) : null,
            ],
        ];
    }
}
```

## What `UpdateHandlerFacade::update()` does for you

1. Calls your `FormHandlerInterface::process($entity, $form, $request)`.
2. On success (handler returned `true`):
   - If `_wid` is in the request → returns `array` with `savedId` populated from
     the entity ID (via `DoctrineHelper::getSingleEntityIdentifier`), plus
     template data (`form` as FormView, `entity`, `isWidgetContext`).
   - Otherwise → adds the success message to the flash bag and returns
     `RedirectResponse` via `Oro\Bundle\UIBundle\Route\Router::redirect($entity)`.
3. On failure (handler returned `false`, e.g. GET or invalid form) → returns
   an `array` of template data for the layout to re-render.

## Pitfalls

- **Do not merge the facade's array into your layout data unchanged** —
  `$result` contains `'form' => Symfony\Component\Form\FormView`, and the
  layout engine will throw
  `InvalidArgumentException: The "form" must be a string, "FormInterface" …`
  (see `FormContextConfigurator::configureContext`). Extract only `savedId`
  and pass your own clean `['data' => [...]]` array.
- **Do not return `JsonResponse`.** `DialogWidget.setContent()` expects HTML
  containing `<div class="widget-content">`; anything else throws
  "Invalid server response".
- **Do not special-case `_wid` branching yourself** (e.g. "if widget return
  array, else return redirect"). The facade already branches; your job is
  just to stop it from redirecting when you're in widget context (which
  happens only if the POST loses `_wid` — e.g. through a locale redirect).

## Non-widget success redirect

`Router::redirect($entity)` redirects to whatever URL the `input_action`
form field says. If `input_action` is missing, it falls back to
`$request->getUri()` — i.e. the form POST URL, which is usually meaningless to
the end user. **Always emit `input_action` from the form template** so the
non-dialog path redirects to the page where the form was embedded. See
`form-template.md`.

`Router::parseRedirectUrl` validates only URL format, not same-origin. Since
`input_action` is POST-body data, an attacker can craft a malicious redirect.
If you care, wrap the facade's `RedirectResponse` in your controller:

```php
if ($result instanceof RedirectResponse && !$isWidget) {
    $target = $result->getTargetUrl();
    if (parse_url($target, PHP_URL_HOST) !== $request->getHost()) {
        $target = $this->urlGenerator->generate('oro_frontend_root');
    }
    return new RedirectResponse($target);
}
```
