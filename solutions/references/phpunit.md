# PHPUnit conventions

## 5. PHPUnit — stub classes for entities, not `createMock`

For Oro entities/models in unit tests, use **Stub classes**, not `createMock()`/`createStub()`.
Entity-extend weaves accessors (e.g. `Product::getLocalizations()`) onto the class at runtime,
but unit tests load the **un-extended** class — so `createMock(Product::class)->method('getLocalizations')`
throws `MethodCannotBeConfiguredException`. Same for final accessors like
`AbstractLocalizedFallbackValue::getLocalization()`.

- Keep shared stubs under `Tests/Unit/Stub/` (e.g. a `ProductStub` with `setId()`,
  `setStubbedLocalizations()`, array-returning `getLocalizations()`); for per-test variants wrap
  the stub in an anonymous subclass overriding `getId`/`getType`/`getAttributeFamily`.
- Set ids by reflection (`(new \ReflectionProperty(Localization::class, 'id'))->setValue(...)`)
  rather than mocking a getter where the sibling pattern already does so.
- Don't stub a method the code-under-test never calls when the collaborator is itself mocked —
  just make the object an `instanceof`.

## 12. Unit tests are a logic guard, never acceptance coverage

- No quota. A unit test aids TDD and guards logic; acceptance coverage comes only from e2e or Functional tests.
- Write it red first, then prove it can fail: after green, flip the production condition (a "flip probe")
  and confirm the test goes red. A test that cannot fail is noise.
- Put decision logic in pure classes (scalars/arrays in, value out) so the test needs no Oro/Doctrine mocks.
  More than 3 Oro/Doctrine mocks in one test means it should be a Functional test instead.
- No unit tests for wiring (service definitions, tags) or DTO getters/setters.
- Iterate on a single file or filter; run the whole unit suite before pushing.
- Event/flush-ordering behaviour (a listener that re-reads data flushed in the same request) is not provable by
  seeding the end state; drive the real trigger (see the e2e skill, "test through the real trigger").

