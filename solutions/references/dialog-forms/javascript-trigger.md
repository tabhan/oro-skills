# JavaScript Trigger — `UI.renderWidgetAttributes`

**Do NOT write a custom `DialogWidget` subclass.** Attach Oro's built-in `oroui/js/app/components/widget-component` to
the trigger button via the `UI.renderWidgetAttributes` Twig macro; it handles the click, loads the URL, instantiates
`oro/dialog-widget` and (with `widget-form-component` on the response) closes on save.

## Canonical Twig trigger

```twig
{% import '@OroUI/macros.html.twig' as UI %}

<button class="btn btn--outlined"
    {{ UI.renderWidgetAttributes({
        type: 'dialog',
        createOnEvent: 'click',
        options: {
            url: path('acme_xyz_form', {widgetName: 'ask-question'}),
            dialogOptions: {
                modal: true,
                resizable: false,
                draggable: false,
                autoResize: false,
                width: 476,
                dialogClass: 'acme-xyz-drawer ask-question-drawer',
                title: 'Ask A Question'|trans
            }
        }
    }) }}>
    {{ 'Ask A Question'|trans }}
</button>
```

What the macro emits:

```html
<button
    data-page-component-module="oroui/js/app/components/widget-component"
    data-page-component-options='{"type":"dialog","createOnEvent":"click",
        "options":{"url":"/us-en/xyz/form/ask-question",
                   "dialogOptions":{"modal":true,"width":476,…}}}'>
    Ask A Question
</button>
```

On bind, `widget-component` prevents default on `click`, resolves `loadModules(mapWidgetModuleName('dialog'))` to
`oro/dialog-widget`, runs `new DialogWidget(options.options).render()`, and the dialog's `loadContent()` fetches the
controller URL. Form submits go through `AbstractWidget._onAdoptedFormSubmit`, which posts with `_wid` and relies on
the server-rendered `widget-content` wrapper to close on `savedId`.

## When you need a thin JS wrapper

Only when the trigger needs logic the Twig macro can't express, e.g. closing a *previous* dialog first:

```js
// product-options-dialog-view.js
import BaseView from 'oroui/js/app/views/base/view';
import routing from 'routing';
import mediator from 'oroui/js/mediator';
import DialogWidget from 'oro/dialog-widget';
import __ from 'orotranslation/js/translator';

const CTA_CONFIGS = {
    'get-quote':      {widget: 'cta-form-get-a-quote',      dialogClass: 'get-a-quote-drawer',      titleKey: 'acme.xyz.get_a_quote'},
    'ask-question':   {widget: 'cta-form-contact-us',       dialogClass: 'ask-question-drawer',     titleKey: 'acme.xyz.ask_a_question'},
};

export default BaseView.extend({
    events: {
        'click [data-action="get-quote"]':    'onCtaClick',
        'click [data-action="ask-question"]': 'onCtaClick',
    },

    onCtaClick(e) {
        e.preventDefault();
        const cfg = CTA_CONFIGS[$(e.currentTarget).data('action')];
        if (!cfg) return;

        mediator.trigger('parent-dialog:close');   // close the currently-open dialog

        new DialogWidget({
            title: __(cfg.titleKey),
            url: routing.generate('acme_xyz_form', {widgetName: cfg.widget}),
            dialogOptions: {
                modal: true, resizable: false, draggable: false, autoResize: false,
                width: 476, dialogClass: 'acme-xyz-drawer ' + cfg.dialogClass
            }
        }).render();
    }
});
```

**Rules of thumb:**

- Don't subclass `DialogWidget` for drawer width/positioning; pass `dialogOptions` + CSS. Overriding `loadContent` /
  `_onContentLoad` breaks Oro's submit pipeline (drops `_wid`).
- `routing.generate(...)` reads `frontend_routes.json`, produced by
  `php bin/console fos:js-routing:dump --target=public/media/js/frontend_routes.json`. Run it whenever you add or
  rename a route (or add a parameter to one called via `routing.generate()`) before expecting the frontend to see it.

## Diagnosing "the button isn't opening anything"

```js
// Run in DevTools console after clicking the button
document.querySelector('[data-action="ask-question"]').dataset
// should show bound-component after binding; if not bound, jsmodules.yml
// probably doesn't export the component in this page's dynamic-imports.
```

If the button has `data-bound-component="oroui/js/app/components/widget-component"` but clicking does nothing, the
likely cause is an empty `options.url`: check that the Twig `path()` resolves (the route must exist and be dumped
into `frontend_routes.json` if referenced from JS).
