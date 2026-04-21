# Pitfalls — symptoms and root causes

The dialog-form flow has many moving parts. Here are the failures we've hit
in practice, with the symptom → root cause → fix mapping.

## "Invalid server response"

**Symptom:** User submits the form, dialog closes or stays open showing a JS
error. `abstract-widget.js` throws `new Error('Invalid server response: ' + content)`.

**Root cause:** The response body did not start with a `.widget-content`
element at the top level. `setContent()` does
`$(content).filter('.widget-content').first()` and the result is empty.

**Most common causes, in order:**

1. **Locale 302 redirect swallowed the POST** — `LocalePrefixRedirectListener`
   redirected an unprefixed POST to the prefixed URL as a GET, losing the
   body. The subsequent GET returns a fresh form — but may render with a
   different wrapper or the browser surfaces the redirect as the "response"
   the widget sees. Fix: localize URL generation. See `locale-prefix.md`.

2. **Controller returned a `JsonResponse`** because you built it yourself.
   `DialogWidget` does not consume JSON; it consumes HTML with
   `.widget-content`. Fix: return `array` from the `#[Layout]` action.

3. **Controller returned the facade's array as-is** and the Layout system
   threw because `['form' => FormView]` doesn't match `FormInterface` expected
   by `FormContextConfigurator::configureContext()`. Fix: extract only
   `savedId` and return your own clean `['data' => […]]`. See `controller.md`.

## Page refresh / redirect after submit

**Symptom:** On submit, the whole page navigates somewhere (often home or
the form route itself) instead of the dialog closing.

**Root cause:** The POST didn't carry `_wid`, so `UpdateHandlerFacade::constructResponse()`
took the non-widget branch and returned `RedirectResponse`. The browser follows.

**Most common causes:**

1. **Locale redirect dropped `_wid` during 302** — same as above. Fix the
   URL generator.

2. **Submit handler bypass** — your custom `DialogWidget` subclass overrode
   `loadContent` / `_onContentLoad` and lost the `_wid` attachment. Fix:
   don't subclass; use `oro/dialog-widget` directly.

3. **Form not inside `.widget-actions` wrapper** — `AbstractWidget._adoptWidgetActions()`
   never set `this.form`, so `_onAdoptedFormSubmit()` silently fails to POST.
   The browser then does a normal HTML form submit. Fix: wrap the submit
   button in `<div class="widget-actions">`.

## Submit button is invisible

**Symptom:** The dialog opens, the form renders, but there is no visible
"Submit" button.

**Root cause:** `DialogWidget` default is `moveAdoptedActions: true`. The
original button is removed from the form and re-rendered inside
`.ui-dialog-buttonpane`. Your project's CSS hides `.ui-dialog-buttonpane`
for this drawer class (common copy-paste from another dialog where the
button lives in the form body).

**Fix:** Style `.ui-dialog-buttonpane` inside your drawer class. See
`form-template.md` §2.

**Do NOT set `moveAdoptedActions: false`.** The button becomes visible in
the form, but `this.form` registration becomes unreliable and the AJAX
submit path breaks.

## Redirect goes to the admin entity URL after successful non-dialog submit

**Symptom:** Content-widget-embedded form submits successfully, but the user
is redirected to `/admin/…/view/123` (entity view route) and either sees
404 or an ACL error.

**Root cause:** `UpdateHandlerFacade::constructResponse()` called
`Router::redirect($entity)`, which without `input_action` falls back to
`$request->getUri()`. Except in some wiring it calls the entity's configured
`routeView` — which is admin-only.

**Fix:** Emit an `input_action` hidden field from the form template with
`{"redirectUrl":"<localized page URL>"}`. See `form-template.md` §3.

## Redirect goes to an unprefixed URL, causing a 302 to the prefixed URL

**Symptom:** Submit works, but the browser does a double redirect: first to
`/landing-page`, then to `/us-en/landing-page`. Functional but sluggish.

**Root cause:** `input_action`'s `redirectUrl` was built from
`$mainRequest->getUri()` without re-adding the locale prefix that
`LocalePrefixRequestListener` stripped.

**Fix:** Wrap the URI with `$this->localePrefixHelper->addPrefixToUrl($uri)`
when building the `input_action` JSON.

## `inputAction is UNDEFINED` in Twig

**Symptom:** You added `inputAction` to your content widget's `getWidgetData()`
return array, but `{% if inputAction is defined %}` is false.

**Root cause:** The content widget's `widget.yml` layout explicitly binds keys
from `data[…]` to layout variables. New keys don't get bound automatically.

**Fix:** Add the mapping:

```yaml
# Resources/views/layouts/default/content_widget/xyz_form/widget.yml
options:
    vars:
        …
        inputAction: '=data["inputAction"]'
```

## Form action lacks the widget name segment

**Symptom:** Form action is `/us-en/cms/cta-form` instead of
`/us-en/cms/cta-form/cta-form-contact-us`.

**Root cause:** The route has a default value for the path parameter
(`public function form(..., string $widgetName = 'cta-form-contact-us')`),
and you're generating the URL for the exact default value. Symfony's URL
generator omits a trailing path parameter whose value equals the default.

**This is usually fine** — the server side routes match and resolve with the
default. But it's visually confusing when debugging. If a non-default widget
uses the same form, its URL will include the segment correctly.

## Route cache stale after rename

**Symptom:** You renamed a route. Server `request.log` shows 404 or 500 for
the old name; `frontend_routes.json` still has the old.

**Fix:**
```bash
php bin/console cache:clear
php bin/console fos:js-routing:dump --target=public/media/js/frontend_routes.json
```

Also re-dump routes whenever you add a parameter to an existing route that
the frontend calls via `routing.generate()`.

## Container has stale service definitions after refactor

**Symptom:** `Class "…\Routing\LocalizedRouter" not found` even though the file
was deleted. Oro's `var/cache/prod/ContainerXxx/*.php` still references it.

**Fix:** `rm -rf var/cache/prod && php bin/console cache:clear`. The soft
`cache:clear` sometimes leaves stale compiled container fragments.

Better long-term: put the project in dev mode locally so most changes pick
up without manual cache clears:

```dotenv
# .env-app.local (or equivalent)
ORO_ENV=dev
ORO_DEBUG=1
```
