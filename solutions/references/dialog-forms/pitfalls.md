# Pitfalls: symptoms and root causes

## "Invalid server response"

`abstract-widget.js` throws `new Error('Invalid server response: ' + content)` because the response body has no
top-level `.widget-content` (`setContent()` does `$(content).filter('.widget-content').first()`). Causes, most common first:

1. **Any 30x on the POST** (auth, locale prefix, slug redirect listener): the browser follows it as a GET and drops the
   body; the dialog receives a fresh non-widget form. Make the form's `action` URL match the exact URL pattern the
   middleware considers final, so no listener wants to redirect it.
2. **Controller returned a `JsonResponse`.** `DialogWidget` consumes HTML with `.widget-content`: return an `array` from the `#[Layout]` action.
3. **Controller returned the facade's array as-is** (`['form' => FormView]` fails `FormContextConfigurator::configureContext()`):
   extract only `savedId` ([controller.md](controller.md)).

## Page refresh / redirect after submit

The whole page navigates (often home or the form route) instead of the dialog closing: the POST carried no `_wid`, so
`UpdateHandlerFacade::constructResponse()` took the non-widget branch and returned a `RedirectResponse`. Causes:

1. An upstream 302 dropped `_wid` (POST -> GET); same fix as case 1 above.
2. A custom `DialogWidget` subclass overrode `loadContent` / `_onContentLoad` and lost `_wid`: don't subclass ([javascript-trigger.md](javascript-trigger.md)).
3. Submit button not inside `.widget-actions`: `_adoptWidgetActions()` never set `this.form`, `_onAdoptedFormSubmit()`
   silently fails, and the browser does a normal HTML submit ([form-template.md](form-template.md)).

## Submit button is invisible

`DialogWidget` defaults to `moveAdoptedActions: true`, so the button lives in `.ui-dialog-buttonpane`, which your CSS
hides for this drawer class (common copy-paste from a dialog whose button sits in the form body). Style
`.ui-dialog-buttonpane` inside your drawer class and do NOT set `moveAdoptedActions: false` ([form-template.md](form-template.md), section 2).

## Redirect goes to the admin entity URL after a non-dialog submit

Content-widget form saves, then the user lands on `/admin/.../view/123` (404 or ACL error). `Router::redirect($entity)`
returns `$request->getUri()` with no `input_action`; with one it uses its `redirectUrl` or generates the `route` it
names. Oro's default save-and-close button supplies an `input_action` carrying an admin `route`, which is what the
storefront user lands on. `Router::redirect()` never reads the entity's `routeView`. Fix: emit an `input_action`
hidden field with `{"redirectUrl":"<localized page URL>"}` ([form-template.md](form-template.md), section 3).

## `inputAction is UNDEFINED` in Twig

`widget.yml` binds only listed `data[...]` keys to layout variables. Add `inputAction: '=data["inputAction"]'` under
`options: vars:` ([form-template.md](form-template.md), section 4).

## Form action lacks the widget name segment

`/us-en/cms/cta-form` instead of `/us-en/cms/cta-form/cta-form-contact-us`: the path parameter equals the route's
default (`string $widgetName = 'cta-form-contact-us'`) and Symfony's URL generator omits a trailing default value.
Usually fine (the server still matches), just confusing; a non-default widget includes the segment.

## Route cache stale after rename

`request.log` shows 404/500 for the old route name and `frontend_routes.json` (used by `routing.generate()`) still has
it. After the usual `cache:clear`, re-dump the JS route map (command in [javascript-trigger.md](javascript-trigger.md)).
