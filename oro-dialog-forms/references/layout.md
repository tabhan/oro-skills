# Layout — `widget_content` block + `widget-form-component`

For a dialog form, the layout must render HTML wrapped in
`<div class="widget-content">` carrying the page-component attributes that tell
Oro's `orofrontend/js/app/components/widget-form-component` to close the
dialog when `savedId` is present.

## Directory layout

For a route named `acme_xyz_form`, Oro auto-binds the layout at:

```
Resources/views/layouts/default/acme_xyz_form/
├── layout.yml
└── layout.html.twig
```

## `layout.yml`

Exposes controller data as layout variables so the Twig block can read them.

```yaml
layout:
    actions:
        - '@setBlockTheme':
              themes: 'layout.html.twig'

        - '@addTree':
              items:
                  form_dialog_content:
                      blockType: container
              tree:
                  widget_content:
                      form_dialog_content: ~

        # widgetName drives which content widget is rendered inside the dialog
        - '@setOption':
              id: form_dialog_content
              optionName: vars
              optionValue:
                  widget_name: '=data["widget_name"]'

        # savedId is read by the widget-form-component we attach to widget_content
        - '@setOption':
              id: widget_content
              optionName: vars
              optionValue:
                  savedId: '=data["savedId"]'
```

## `layout.html.twig`

Overrides the `_widget_content_widget` block to inject the page component
attributes. `parent_block_widget(block)` keeps the default rendering (the
`<div class="widget-content">` wrapper + body).

```twig
{% block _widget_content_widget %}
    {% set pageComponentOptions = {
        '_wid':    app.request.get('_wid'),
        'savedId': savedId|default(null),
        'message': 'acme.xyz.form.submitted.message'|trans
    } %}
    {% set attr = {
        'data-page-component-module': 'orofrontend/js/app/components/widget-form-component'
    }|merge(attr)|merge({
        'data-page-component-options': pageComponentOptions|merge(attr['data-page-component-options']|default({}))
    }) %}
    {{ parent_block_widget(block) }}
{% endblock %}

{% block _form_dialog_content_widget %}
    <div class="form-dialog-wrapper">
        {{ widget(widget_name) }}
    </div>
{% endblock %}
```

## Why `widget-form-component` is the load-bearing piece

See `vendor/oro/customer-portal/src/Oro/Bundle/FrontendBundle/Resources/public/js/app/components/widget-form-component.js`:

```js
export default function(options) {
    if (options.savedId) {
        widgetManager.getWidgetInstance(options._wid, function(widget) {
            messenger.notificationFlashMessage('success', options.message);
            mediator.trigger('widget_success:' + widget.getAlias(), options);
            mediator.trigger('widget_success:' + widget.getWid(), options);
            widget.trigger('formSave', options.savedId);
            widget.remove();
        });
    }
}
```

When the controller's POST response includes a non-null `savedId`, this
component:

1. Flashes the success message.
2. Fires `widget_success:*` mediator events (useful if other views need to
   know the save happened).
3. Triggers `formSave` on the widget.
4. Calls `widget.remove()` — the dialog closes.

If `savedId` is falsy (validation failure or GET), the component is a no-op
and the dialog stays open with the re-rendered form.

## Pitfalls

- **Forgetting to map `savedId` in `layout.yml`** — the block gets the var
  `savedId = null` even when the controller supplied it. Check your `@setOption`
  block.
- **Accessing controller data directly as `formType`/`inputAction` in Twig** —
  the `content_widget` rendering wraps the `getWidgetData` result under the
  `data` key internally. You must explicitly bind keys via the layout's `vars:`
  mapping (see `form-template.md`).
- **Nesting a second `.widget-content` inside** — `AbstractWidget.setContent()`
  uses `$(content).filter('.widget-content').first()`. Nested wrappers are
  fine, but the TOP-level DOM node of the response MUST be `.widget-content`.
