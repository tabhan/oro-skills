# Storefront localization

## 3. Storefront localization — never `getDefault*()`

On the storefront (frontend layouts, Twig, JS) never read localized-fallback-value fields via
`getDefaultName()` / `getDefaultDescription()` / etc. Use the locale-aware accessor:

```yaml
# layout YAML
productName: '=data["locale"].getLocalizedValue(data["product"].getNames())'
```
```twig
{{ product.names|localized_value }}
```

`getDefaultName()` returns the LFV row where `localization === null` and ignores the customer's
current locale — wrong language on a multi-locale site, and an outright `null`→`.getString()`
500 if a snapshot/overlay path has no default row. Grep frontend layout/Twig/JS for
`getDefault*()` on any `LocalizedFallbackValueAwareInterface` entity (Product, Category,
ContentNode, …) and replace it. Admin-only datagrids/forms and backend slug/typeahead handlers
may keep `getDefault*()` — admins see the source default row; the rule is storefront-only.

