# OroCommerce Dialog Form Knowledge Base

A form must work correctly in both of:

1. **Dialog mode** — a trigger button opens a modal/drawer, the form loads via
   AJAX into `DialogWidget`, submits via AJAX, closes the dialog on success.
2. **Content-widget mode** — the same form is embedded on a landing page via a
   `ContentWidget`; a normal POST submit should save the data, flash a success
   message, and redirect back to the embed page.

One controller + one handler + one form template serve both modes.
Correctness depends on ~6 small details that interact; getting any one of
them wrong produces confusing symptoms (page refresh, "Invalid server
response", redirect to an admin-only URL, missing submit button, etc).

---

## Available Documents (Task → Document)

| Task | Document |
|------|----------|
| Overview of the full pipeline | [README.md](README.md) |
| Controller: UpdateHandlerFacade + referer-safe non-widget redirect | [controller.md](controller.md) |
| FormHandler: `oro_form.form.handler` tag + alias + `@.inner` wiring | [form-handler.md](form-handler.md) |
| Layout YAML + `_widget_content_widget` block override + `widget-form-component` | [layout.md](layout.md) |
| Form template: `form-dialog` class, `.widget-actions`, `input_action` hidden field | [form-template.md](form-template.md) |
| JS trigger: `UI.renderWidgetAttributes({type: 'dialog', ...})` | [javascript-trigger.md](javascript-trigger.md) |
| Known pitfalls and how to diagnose them (dialog/widget-specific; generic cache-clear advice trimmed — see the official plugin's backend.md) | [pitfalls.md](pitfalls.md) |

---

## Canonical end-to-end flow

**Dialog mode:**
- Trigger button's `UI.renderWidgetAttributes({type: 'dialog', ...})` fires a
  GET at the controller's `#[Route /…/{widgetName}]` + `#[Layout]` action,
  which calls `FormHandler.process()` (validate, persist, dispatch MQ) via
  `UpdateHandlerFacade`.
- Response HTML is wrapped in `<div class="widget-content"
  data-page-component-module="orofrontend/js/app/components/widget-form-component"
  data-page-component-options="{_wid,savedId,message}">`.
- `DialogWidget` opens that form. Submitting inside it POSTs with `_wid` in
  the body to the same controller/handler, which returns HTML with `savedId`
  populated.
- `widget-form-component` sees `savedId` → flashes success + closes the
  dialog.

**Non-dialog flow** (content-widget embed on a landing page, e.g.
`/us-en/landing-page`):
- User submits without `_wid` → same controller → handler →
  `facade.update()` returns a `RedirectResponse` built from the
  `input_action` JSON hidden field (`{redirectUrl: "/us-en/landing-page"}`).
- Browser follows the 302 back to the landing page; flash message shown
  there.

---

## What to do first

1. Read [README.md](README.md) for a 2-minute tour of which
   files you will need to touch and why.
2. For the controller pattern, see [controller.md](controller.md).
3. Copy the structural pieces from [form-template.md](form-template.md)
   — the `form-dialog` class, `data-collect`, `widget-actions` wrapper, and
   `input_action` hidden field are all load-bearing.
