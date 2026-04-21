# Locale Prefix — why AJAX POSTs break without it

OroCommerce storefronts with URL-prefixed localizations (`/us-en/…`,
`/fr-fr/…`) commonly implement a `LocalePrefixRequestListener` that strips
the prefix on the way in (so routing sees clean paths) and a
`LocalePrefixRedirectListener` that 302-redirects unprefixed frontend URLs
to the prefixed version.

The redirect listener is the killer for dialog forms. Here's why.

## Failure mode

1. User opens a dialog. The form is rendered via `{{ widget(widget_name) }}`,
   which runs the content widget in a Symfony subrequest.
2. The form's `action` attribute is built from
   `$urlGenerator->generate('acme_xyz_form', ['widgetName' => '...'])`.
3. If that URL generator is not locale-aware, the output is
   `/xyz/form/ask-question` — **without** the `/us-en/` prefix.
4. On submit, browser POSTs to `/xyz/form/ask-question`.
5. `LocalePrefixRedirectListener` fires, returns `302 Location: /us-en/xyz/form/ask-question`.
6. `AbstractWidget.loadContent()` is doing an XHR. The browser follows the
   redirect — but per RFC, a 302 response to a POST should fetch the new URL
   with GET. The POST body is dropped.
7. The GET to `/us-en/xyz/form/ask-question` re-renders the form (fresh).
8. `AbstractWidget.setContent()` does `$(content).filter('.widget-content').first()`.
   In happy cases this works, but it means the submit effectively did nothing
   (no persist happened, dialog renders fresh form) → confusing UX and no
   obvious error. In less happy cases the response doesn't start with
   `.widget-content` and the user sees **"Invalid server response"**.

## The fix: make URL generation locale-aware

Two options:

### Option A — Router interceptor (recommended for this codebase)

Intercept `generate()` on Oro's routing router and prepend the prefix. The
existing `RouterInterceptor` in this codebase does exactly this. Registered
via the aspect bundle:

```yaml
buckman_locale.interceptor.router:
    class: Buckman\Bundle\LocaleBundle\Interceptor\RouterInterceptor
    arguments:
        - '@buckman_locale.helper.locale_prefix'
        - '@buckman_locale.resolver.locale_prefix'
        - '@oro_locale.provider.current_localization'
        - '@request_stack'
    tags:
        - { name: aaxis_aspect.interceptor, service: oro_redirect.routing.router }
```

`oro_redirect.routing.router` is itself a decorator of Symfony's `router`
(`decorates: router`), so intercepting it covers every `@router` injection
in the container. You do NOT need to also intercept `router.default`; that's
the inner undecorated service and nothing normal injects it.

### Option B — Decorate `router.default` with a custom `RouterInterface` wrapper

Only needed if your project doesn't use the aspect bundle. You'd create a
decorator that wraps `router.default`, overrides `generate()` to prepend
the prefix via `LocalePrefixHelper::addPrefixToUrl`, and delegates everything
else. Register via Symfony's `decorates: router.default`. More boilerplate,
same effect.

## Diagnosing

```bash
curl -sk 'https://local.aaxisdev.net/us-en/xyz/form/ask-question' \
  | grep -oE 'action="[^"]*"' | head -1
```

- If output is `action="/us-en/xyz/form/ask-question"` — locale URL generation
  works, the AJAX submit will not trigger the redirect.
- If output is `action="/xyz/form/ask-question"` — your interceptor isn't
  running, your form will break on submit. Check:
  - Is the interceptor's target service (`oro_redirect.routing.router`) still
    the same in your Oro version?
  - Is the interceptor actually registered? `bin/console debug:container
    | grep router.interceptor`.
  - Is the service the form is injected into using `@router` (goes through
    decorator → interceptor applies) or `@router.default` (bypasses
    decorator)?

## Also: `input_action` needs the prefix too

`$this->requestStack->getMainRequest()->getUri()` returns the URI **after**
`LocalePrefixRequestListener` stripped the prefix. When you use it to build
`input_action`, you must re-add the prefix:

```php
$inputAction = json_encode([
    'redirectUrl' => $this->localePrefixHelper->addPrefixToUrl($mainRequest->getUri()),
]);
```

If you skip the `addPrefixToUrl()`, `input_action` says `redirectUrl: /landing-page`,
the browser follows it, `LocalePrefixRedirectListener` 302's to `/us-en/landing-page`
— functionally correct but adds a needless round-trip.

## What NOT to do

- **Don't add "skip on XHR" to `LocalePrefixRedirectListener`**. Tempting
  because it fixes the symptom (no redirect on AJAX), but it means every
  unprefixed frontend AJAX URL now silently serves against the default locale
  regardless of what the user has selected. The right fix is generating
  correct URLs in the first place.
- **Don't make the form `action` dynamic via JS** (e.g. `form.action =
  window.location.href`). It works for the dialog case but breaks the
  content-widget-on-landing-page case where the form action should be the
  route URL, not the landing-page URL.
