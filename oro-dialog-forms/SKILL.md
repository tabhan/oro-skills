---
name: oro-dialog-forms
description: >
  When building OroCommerce frontend forms that open in a dialog (drawer/modal)
  AND/OR are embedded on a landing page via a content widget, you MUST use this
  skill to consult the dialog-form knowledge base instead of relying on memory.

  Trigger scenarios:
  - Adding a "click a button → open a dialog with a form → AJAX submit" flow
  - Building a CTA / contact / request form rendered via ContentWidget and also
    openable as a DialogWidget from a trigger button
  - Wiring a Symfony form into Oro's UpdateHandlerFacade with a custom
    FormHandlerInterface tagged `oro_form.form.handler`
  - Writing a frontend controller that must respond correctly in BOTH dialog
    (widget / `_wid`) and non-dialog (landing page / POST-redirect) contexts
  - Closing the dialog + flashing a success message after save using Oro's
    `orofrontend/js/app/components/widget-form-component`
  - Setting `input_action` on a form so non-AJAX submits redirect back to the
    original embed page instead of the entity view route

  Read documentation BEFORE writing the controller, layout, Twig, or JS. The
  failure modes in this flow are interconnected and hard to debug in isolation.

  Skip this skill if the form is a simple full-page form with no dialog / widget
  context and no content-widget embed.
---

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
| Overview of the full pipeline | [references/README.md](references/README.md) |
| Controller: UpdateHandlerFacade + referer-safe non-widget redirect | [references/controller.md](references/controller.md) |
| FormHandler: `oro_form.form.handler` tag + alias + `@.inner` wiring | [references/form-handler.md](references/form-handler.md) |
| Layout YAML + `_widget_content_widget` block override + `widget-form-component` | [references/layout.md](references/layout.md) |
| Form template: `form-dialog` class, `.widget-actions`, `input_action` hidden field | [references/form-template.md](references/form-template.md) |
| JS trigger: `UI.renderWidgetAttributes({type: 'dialog', ...})` | [references/javascript-trigger.md](references/javascript-trigger.md) |
| Known pitfalls and how to diagnose them (dialog/widget-specific; generic cache-clear advice trimmed — see the official plugin's backend.md) | [references/pitfalls.md](references/pitfalls.md) |

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

1. Read [references/README.md](references/README.md) for a 2-minute tour of which
   files you will need to touch and why.
2. For the controller pattern, see [references/controller.md](references/controller.md).
3. Copy the structural pieces from [references/form-template.md](references/form-template.md)
   — the `form-dialog` class, `data-collect`, `widget-actions` wrapper, and
   `input_action` hidden field are all load-bearing.
