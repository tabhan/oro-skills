# Controller — `UpdateHandlerFacade` + dual-mode response

The controller uses `#[Layout]` and delegates the save to `UpdateHandlerFacade`. **One action serves both GET
(dialog open) and POST (AJAX or standard submit)**; the facade picks the response shape from `_wid`.

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

## What `UpdateHandlerFacade::update()` does

1. Calls your `FormHandlerInterface::process($entity, $form, $request)`.
2. Handler returned `true` (success): with `_wid` in the request it returns an `array` with `savedId` (from
   `DoctrineHelper::getSingleEntityIdentifier`) plus template data (`form` as FormView, `entity`, `isWidgetContext`);
   without `_wid` it adds the success flash and returns a `RedirectResponse` via `Oro\Bundle\UIBundle\Route\Router::redirect($entity)`.
3. Handler returned `false` (GET or invalid form): returns an `array` of template data for the layout to re-render.

## Pitfalls

- **Do not merge the facade's array into your layout data unchanged.** `$result` contains `'form' => FormView`, and
  the layout engine throws `InvalidArgumentException: The "form" must be a string, "FormInterface" ...`
  (`FormContextConfigurator::configureContext`). Extract only `savedId` and pass your own clean `['data' => [...]]`.
- **Do not return `JsonResponse`.** `DialogWidget.setContent()` expects HTML containing `<div class="widget-content">`;
  anything else throws "Invalid server response".
- **Do not branch on `_wid` yourself.** Only stop the facade from redirecting in widget context (it happens when the
  POST loses `_wid`, e.g. through a locale redirect).

## Non-widget success redirect

`Router::redirect($entity)` redirects to the URL the `input_action` form field names; if missing it falls back to
`$request->getUri()` (the form POST URL, meaningless to the user). **Always emit `input_action` from the form
template** so the non-dialog path returns to the embedding page ([form-template.md](form-template.md)).

`Router::parseRedirectUrl` validates only URL format (`parse_url(...) !== false`), not same-origin, and
`input_action` is client-controlled POST data (CSRF plus a modified `input_action` could redirect off-site). Wrap
the facade's `RedirectResponse` in your controller and force a same-host target:

```php
if ($result instanceof RedirectResponse && !$isWidget) {
    $target = $result->getTargetUrl();
    if (parse_url($target, PHP_URL_HOST) !== $request->getHost()) {
        $target = $this->urlGenerator->generate('oro_frontend_root');
    }
    return new RedirectResponse($target);
}
```
