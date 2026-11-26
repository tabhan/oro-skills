# Form Template — class, wrapper, hidden fields

The content widget's Twig template renders the form. Items 1-3 are load-bearing.

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

- Do **not** set `action` to `app.request.uri`; use the `action` from the content widget's `getWidgetData()` (built
  via `UrlGeneratorInterface::generate`) so the URL is stable and shareable.
- `form-validate-view` is client-side validation only; `AbstractWidget` handles the submit.

## 2. Submit button wrapped in `.widget-actions`

```twig
<div class="acme-xyz-form__row widget-actions">
    <button type="submit" class="acme-xyz-form__submit">
        {{ 'acme.xyz.form.submit.label'|trans }}
    </button>
</div>
```

`.widget-actions` is the magic string. `AbstractWidget._adoptWidgetActions()` scans for it inside the widget
content, finds the wrapping form, sets `this.form`, and wires adopted submit clicks to `_onAdoptedFormSubmit()`,
which POSTs via `loadContent(form.serialize(), 'POST', url)` with `_wid` appended by `_getWidgetData()`.

`DialogWidget` defaults to `moveAdoptedActions: true`: the original submit button is removed and a copy placed in
the dialog's `.ui-dialog-buttonpane`. If your drawer CSS hides `.ui-dialog-buttonpane` (e.g. `display: none` copied
from another dialog class) the user sees no submit button. Fix the CSS:

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

**Do not set `moveAdoptedActions: false` to work around this**: `this.form` registration becomes unreliable and the AJAX submit breaks.

## 3. `input_action` hidden field (for non-dialog redirect)

```twig
{% if inputAction is defined and inputAction %}
    <input type="hidden" name="input_action" value="{{ inputAction }}">
{% endif %}
```

`inputAction` is a JSON string like `{"redirectUrl":"https://host/landing-page"}`, computed in `getWidgetData()`:

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

Use `$this->requestStack->getMainRequest()`, NOT `getCurrentRequest()`: content widgets render in a subrequest, and
the main request is the page URL (e.g. `/sustainability/xyz`) to redirect back to.

## 4. Wire the new variable through `widget.yml`

Every variable the content widget's Twig needs must be bound from `data[...]` in its `widget.yml`:

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

A new `getWidgetData()` key that is not bound here is silently undefined in Twig (`{% if foo is defined %}` is false).

## Security note on `input_action`

It is a client-controlled POST field and `Router::parseRedirectUrl` checks URL format only, so the controller must
force a same-host redirect target: see [controller.md](controller.md).
