# Layout — `widget_content` block + `widget-form-component`

The layout must render HTML wrapped in `<div class="widget-content">` carrying the page-component attributes that
tell `orofrontend/js/app/components/widget-form-component` to close the dialog when `savedId` is present.

## Directory layout

A route named `acme_xyz_form` auto-binds the layout at:

```
Resources/views/layouts/default/acme_xyz_form/
├── layout.yml
└── layout.html.twig
```

## `layout.yml`

Exposes controller data as layout variables for the Twig block.

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

Overrides `_widget_content_widget` to inject the page component attributes; `parent_block_widget(block)` keeps the
default `<div class="widget-content">` wrapper + body.

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

## `widget-form-component` is load-bearing

`vendor/oro/customer-portal/src/Oro/Bundle/FrontendBundle/Resources/public/js/app/components/widget-form-component.js`:

<!-- oro: ">=7.0.0" topic: widget-form-component-source -->
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
<!-- /oro -->

<!-- oro: "^6.1" topic: widget-form-component-source -->
On 6.1 the same component ships as an AMD module (same behaviour, plus a
default flash message when `options.message` is unset):

```js
define(
    ['oroui/js/widget-manager', 'oroui/js/messenger', 'oroui/js/mediator', 'orotranslation/js/translator', 'jquery'],
    function(widgetManager, messenger, mediator, __, $) {
        'use strict';

        return function(options) {
            if (options.savedId) {
                widgetManager.getWidgetInstance(options._wid, function(widget) {
                    if (!options.message) {
                        options.message = __('oro_frontend.widget_form_component.save_flash_success');
                    }
                    messenger.notificationFlashMessage('success', options.message);
                    mediator.trigger('widget_success:' + widget.getAlias(), options);
                    mediator.trigger('widget_success:' + widget.getWid(), options);
                    widget.trigger('formSave', options.savedId);
                    widget.remove();
                });
            }
        };
    }
);
```
<!-- /oro -->

A non-null `savedId` in the POST response makes it flash the success message, fire `widget_success:*` mediator
events, trigger `formSave` on the widget and call `widget.remove()` (dialog closes). A falsy `savedId` (validation
failure or GET) is a no-op: the dialog stays open with the re-rendered form.

## Pitfalls

- **`savedId` not mapped in `layout.yml`**: the block gets `savedId = null` even when the controller supplied it.
  Check the `@setOption` block.
- **Reading controller data directly as `formType`/`inputAction` in Twig**: `content_widget` rendering wraps the
  `getWidgetData` result under the `data` key, so bind keys via the layout's `vars:` ([form-template.md](form-template.md)).
- **Top-level node**: `AbstractWidget.setContent()` uses `$(content).filter('.widget-content').first()`; nested
  wrappers are fine but the TOP-level DOM node of the response MUST be `.widget-content`.
