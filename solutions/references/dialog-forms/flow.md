# Dialog form: overview and flow

A Symfony form renders inside a jQuery UI dialog via `DialogWidget`, submits via AJAX and closes on save. The same
form is typically also embedded on a landing page through a `ContentWidget`, where it falls back to a normal
POST-redirect-flash flow. One controller + one handler + one form template serve both modes; correctness depends on
a few small interacting details (a wrong one gives a page refresh, "Invalid server response", a redirect to an
admin-only URL or a missing submit button; see [pitfalls.md](pitfalls.md)).

| Task | Document |
|------|----------|
| Controller: `UpdateHandlerFacade`, referer-safe non-widget redirect | [controller.md](controller.md) |
| FormHandler: `oro_form.form.handler` tag, alias | [form-handler.md](form-handler.md) |
| Layout YAML, `_widget_content_widget` override, `widget-form-component` | [layout.md](layout.md) |
| Form template: `form-dialog`, `.widget-actions`, `input_action`, `widget.yml` vars | [form-template.md](form-template.md) |
| JS trigger: `UI.renderWidgetAttributes({type: 'dialog', ...})` | [javascript-trigger.md](javascript-trigger.md) |
| Symptoms and root causes | [pitfalls.md](pitfalls.md) |

## The six moving parts

| # | Piece | File type | Responsibility |
|---|-------|-----------|----------------|
| 1 | **Trigger** | Twig macro `UI.renderWidgetAttributes({type: 'dialog', ...})` | Attaches `widget-component` to a button; click opens `oro/dialog-widget` on the form URL |
| 2 | **Controller** | `Controller/Frontend/XyzController.php`, `#[Layout]` + `#[Route]` | Build the form, call `UpdateHandlerFacade::update()`, return a layout data array |
| 3 | **Form handler** | Class implementing `Oro\Bundle\FormBundle\Form\Handler\FormHandlerInterface` | `handleRequest()` + `isValid()` + persist; tagged `oro_form.form.handler` with an alias |
| 4 | **Layout YAML + Twig** | `layouts/default/{route_name}/layout.yml` + `layout.html.twig` | `widget-form-component` attrs on the `widget_content` block so the dialog auto-closes on `savedId` |
| 5 | **Form template** | The content widget's `widget.html.twig` | `form_start()` with `form-dialog` class and `data-collect="true"`; submit inside `.widget-actions`; `input_action` hidden field |
| 6 | **Content widget type** | `ContentWidget/XyzContentWidgetType.php` | Build the form with the route `action` URL; pass `inputAction` JSON (embed-page URL) to the Twig |

## The two flows

**Dialog mode (AJAX).** The trigger GETs the controller's `#[Route /.../{widgetName}]` + `#[Layout]` action. The
response HTML is wrapped in `<div class="widget-content" data-page-component-module="orofrontend/js/app/components/widget-form-component" data-page-component-options="{_wid,savedId,message}">`
and `DialogWidget` opens it. Submitting POSTs with `_wid`, `_widgetContainer=dialog`, `_widgetInit=1` in the body
(added by `AbstractWidget._getWidgetData()`) to the same controller/handler (`FormHandler.process()`: validate,
persist, dispatch MQ via `UpdateHandlerFacade`). `UpdateHandlerFacade` sees `_wid` and returns an **array** with
`savedId`; `#[Layout]` renders `.widget-content`; `widget-form-component` reads `savedId`, flashes the success
message, fires `formSave` and removes the dialog.

**Content-widget mode (POST redirect).** No `_wid`. The facade's `Router::redirect($entity)` reads the `input_action`
hidden field (`{redirectUrl: "/us-en/landing-page"}`) and returns a `RedirectResponse`; the browser follows the 302
and shows the flash message on the landing page. Without `input_action` it falls back to `$request->getUri()` (the
form URL, which is wrong), so always set it.

**Shared contract.** Same controller and same form template for both. The controller does not branch on `_wid`
itself: `UpdateHandlerFacade` decides from the request. The controller builds the form, calls `update()` and returns
the layout data array or the `RedirectResponse`.

## Checklist before you write code

1. Content-widget template: `form_start(form, {attr: {class: 'cta-form__form form-dialog', 'data-collect': 'true', ...}})`.
2. Submit button inside `<div class="widget-actions">` so `AbstractWidget._adoptWidgetActions()` moves it into the dialog's action bar.
3. The layout's `_widget_content_widget` block override emits `data-page-component-module="orofrontend/js/app/components/widget-form-component"` with `_wid` + `savedId` + `message` in the options.
4. A hidden `<input name="input_action" value="{...}">` for the non-dialog redirect.

Copy the structural pieces from [form-template.md](form-template.md): the `form-dialog` class, `data-collect`,
`widget-actions` wrapper and `input_action` field are all load-bearing.
