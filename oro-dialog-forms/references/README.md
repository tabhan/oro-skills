# Dialog Form — Overview

A dialog form in OroCommerce frontend is a Symfony form that renders inside
a jQuery UI dialog via `DialogWidget`, submits via AJAX, and closes on save.
The same form is typically also embedded on a landing page through a
`ContentWidget`, where it must fall back to a normal POST-redirect-flash flow.

This document maps the moving parts to the files you will touch.

## The seven moving parts

| # | Piece | File type | Responsibility |
|---|-------|-----------|----------------|
| 1 | **Trigger** | Twig macro using `UI.renderWidgetAttributes({type: 'dialog', …})` | Attach `widget-component` to a button so clicking it opens `oro/dialog-widget` pointing at the form URL |
| 2 | **Controller** | `Controller/Frontend/XyzController.php` with `#[Layout]` and `#[Route]` | Build the Symfony form, call `UpdateHandlerFacade::update()`, return a layout data array |
| 3 | **Form handler** | Class implementing `Oro\Bundle\FormBundle\Form\Handler\FormHandlerInterface` | Do the actual `handleRequest()` + `isValid()` + persist, tagged `oro_form.form.handler` with an alias |
| 4 | **Layout YAML + Twig** | `layouts/default/{route_name}/layout.yml` + `layout.html.twig` | Put `widget-form-component` attrs on the `widget_content` block so the dialog auto-closes on `savedId` |
| 5 | **Form template** | The content-widget's `widget.html.twig` | Render `form_start()` with `form-dialog` class, `data-collect="true"`; wrap submit button in `.widget-actions` so AbstractWidget adopts it; emit an `input_action` hidden field for the non-dialog redirect |
| 6 | **Content widget type** | `ContentWidget/XyzContentWidgetType.php` | Build the form with a localized `action` URL; pass `inputAction` JSON with a localized `redirectUrl` to the Twig |
| 7 | **Locale URL prefix** | Router interceptor / helper | Ensure generated URLs carry `/us-en/` so AJAX POSTs don't trigger `LocalePrefixRedirectListener` (a 302 would drop the POST body and produce "Invalid server response") |

## The two flows, and how they differ

### Dialog mode (AJAX)

- Request carries `_wid`, `_widgetContainer=dialog`, `_widgetInit=1` in the body
  (added automatically by `AbstractWidget._getWidgetData()`).
- `UpdateHandlerFacade` sees `_wid` → returns **array** with `savedId` on success.
- `#[Layout]` renders HTML containing `<div class="widget-content">`.
- `widget-form-component` reads `savedId` from `data-page-component-options`,
  fires `formSave`, removes the dialog, and flashes the success message.

### Content-widget mode (POST redirect)

- Request has no `_wid`.
- Facade's `Router::redirect($entity)` reads the `input_action` hidden field.
- If set: redirects to that URL (and the browser shows the flash message on
  the next GET).
- If missing or malicious: falls back to `$request->getUri()` (the form URL
  itself, which is wrong) — so always set `input_action`.

## Shared contract

Both flows use the **same controller** and the **same form template**. The
controller does NOT branch on `_wid` by itself — `UpdateHandlerFacade` makes
that decision based on what the request contains. The controller's only job
is to build the form + call `update()` + return either the array (layout data)
or the `RedirectResponse`.

## One-line checklist before you write code

1. Is there an existing `RouterInterceptor` (or URL-generator decorator) that
   adds locale prefix to generated URLs? If not, your AJAX POSTs will break.
2. Is the form's content-widget template using `form_start(form, {attr: {
   class: 'cta-form__form form-dialog', 'data-collect': 'true', ...}})`?
3. Is the submit button inside `<div class="widget-actions">` so
   `AbstractWidget._adoptWidgetActions()` moves it into the dialog's action bar?
4. Does the layout's `_widget_content_widget` block override emit
   `data-page-component-module="orofrontend/js/app/components/widget-form-component"`
   with `_wid` + `savedId` + `message` in the options?
5. Is there a hidden `<input name="input_action" value="{…}">` field for the
   non-dialog redirect?

If all five answer "yes", the flow will work end to end.
