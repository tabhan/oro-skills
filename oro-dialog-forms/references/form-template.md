# Form Template — class, wrapper, hidden fields

The content-widget's Twig template renders the actual form. Three structural
things are load-bearing; getting any of them wrong breaks the flow.

## 1. `form-dialog` class + `data-collect="true"` on `<form>`

```twig
{{ form_start(form, {attr: {
    class: 'acme-xyz-form form-dialog',
    novalidate: 'novalidate',
    'data-collect': 'true',
    'data-page-component-module': 'oroui/js/app/components/view-component',
    'data-page-component-options': {view: 'oroform/js/app/views/form-validate-view'}|json_encode
}}) }}
```

- Do **not** set `action` explicitly to `app.request.uri`. Let the form use
  the `action` set by the content widget's `getWidgetData()` (built via
  `UrlGeneratorInterface::generate`) so the URL is stable and shareable.
- `form-validate-view` gives you client-side validation. It does NOT do
  anything with the submit; submission is handled by `AbstractWidget`.

## 2. Submit button wrapped in `.widget-actions`

```twig
<div class="acme-xyz-form__row widget-actions">
    <button type="submit" class="acme-xyz-form__submit">
        {{ 'acme.xyz.form.submit.label'|trans }}
    </button>
</div>
```

The `.widget-actions` wrapper is the magic string. `AbstractWidget._adoptWidgetActions()`
scans for this class inside the widget content, finds the form that wraps it,
sets `this.form = form`, and wires adopted submit clicks to `_onAdoptedFormSubmit()`
which POSTs via `loadContent(form.serialize(), 'POST', url)` with `_wid`
appended via `_getWidgetData()`.

By default `DialogWidget` has `moveAdoptedActions: true` — the original submit
button is removed and a copy is placed in the dialog's `.ui-dialog-buttonpane`.
If your drawer CSS hides `.ui-dialog-buttonpane` (e.g. you set `display: none`
to hide it on another dialog class), the user will see no submit button. Fix
the CSS:

```scss
.your-drawer-class {
    .ui-dialog-buttonpane {
        flex-shrink: 0;
        padding: 16px 24px 24px;
        border-top: 1px solid $border-color;
        margin: 0;

        .ui-dialog-buttonset {
            float: none;
            display: flex;
            justify-content: flex-end;
            gap: 12px;
        }

        .form-actions { margin: 0; }
    }
}
```

**Do not set `moveAdoptedActions: false` to work around this** — the original
button stays visible but `this.form` registration becomes unreliable, and the
AJAX submit path breaks.

## 3. `input_action` hidden field (for non-dialog redirect)

```twig
{% if inputAction is defined and inputAction %}
    <input type="hidden" name="input_action" value="{{ inputAction }}">
{% endif %}
```

`$inputAction` is a JSON string like `{"redirectUrl":"https://host/landing-page"}`,
computed in `getWidgetData()`:

```php
public function __construct(
    private readonly FormFactoryInterface $formFactory,
    private readonly UrlGeneratorInterface $urlGenerator,
    private readonly RequestStack $requestStack,
) {}

public function getWidgetData(ContentWidget $contentWidget): array
{
    $mainRequest = $this->requestStack->getMainRequest();
    $inputAction = $mainRequest !== null
        ? json_encode(['redirectUrl' => $mainRequest->getUri()], JSON_THROW_ON_ERROR)
        : null;

    $form = $this->formFactory->create($formTypeClass, null, [
        'action' => $this->urlGenerator->generate('acme_xyz_form', [
            'widgetName' => $contentWidget->getName(),
        ]),
    ]);

    return [
        'formType'    => $formType,
        'inputAction' => $inputAction,
        'form'        => $form->createView(),
    ];
}
```

Key point: use `$this->requestStack->getMainRequest()` — NOT
`getCurrentRequest()`. Content widgets render in a subrequest; the main
request is the actual page URL (e.g. `/sustainability/xyz`), which is what
we want to redirect back to.

## 4. Wire the new variable through `widget.yml`

Each variable you want available in the content-widget's Twig must be
explicitly bound from `data[…]` in the content widget's `widget.yml`:

```yaml
# Resources/views/layouts/default/content_widget/xyz_form/widget.yml
layout:
    actions:
        - '@setBlockTheme':
              themes: widget.html.twig
        - '@add':
              id: xyz_form
              blockType: block
              parentId: content_widget_container
              options:
                  vars:
                      form:        '=data["form"]'
                      formType:    '=data["formType"]'
                      formConfig:  '=data["formConfig"]'
                      title:       '=data["title"]'
                      inputAction: '=data["inputAction"]'   # ← easy to forget
```

If you add a new key to `getWidgetData()` and don't add it here, the Twig
`{% if foo is defined %}` check silently evaluates to false. Budget a
debugging cycle to remember this.

## Security note on `input_action`

`input_action` is a POST-body field under the client's control. `Oro\Bundle\UIBundle\Route\Router::parseRedirectUrl`
only validates URL format via `parse_url(…) !== false`, **not** same-origin.
An attacker who can cause a user to POST a crafted form (e.g. CSRF plus a
modified `input_action`) could redirect that user off-site.

Defense-in-depth: the controller wraps the facade's `RedirectResponse` and
validates the target is same-host before returning it. See `controller.md`.
