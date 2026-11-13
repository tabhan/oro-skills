# Design rules: files, providers, Aaxis, precedent

## 13. File access goes through Gaufrette

Code and tests never touch files by path: no `%kernel.project_dir%`-based paths, no direct `fopen`,
`file_put_contents`, `unlink` on application data. Use the Gaufrette filesystem or `FileManager` that owns the
data (import/export, attachments, generated JS translations, ...), so the code works unchanged on any storage
backend (GridFS, S3, local) and a test never depends on, or leaves behind, files on the host disk.
System temp (`sys_get_temp_dir()`) is the only exception. A test action that produces a file returns its
content (or a storage key) and deletes it after the read.

Review check (flag, then judge each hit):

```bash
grep -rnE "file_put_contents|fopen|unlink|kernel.project_dir" src --include=*.php
```

## 14. External providers sit behind an interface

An integration with an external service (LLM, payment, search, ERP) is designed interface first: a provider
interface, optional capability interfaces (batch, streaming), a DI-tag registry that resolves the provider by
key, per-provider configuration. The vendor SDK is imported only inside that provider's directory. Swapping
or adding a provider must be a new class + tag + config and nothing else. Check every plan that adds an SDK
for this before implementing. If an Aaxis bundle already offers the registry, extend it ([aaxis/rules.md](aaxis/rules.md)).

## 15. Aaxis bundles never depend on the project

Code under `src/Aaxis/` must not reference project classes, entities, services or translations. The review
grep and the full rule set are in [aaxis/rules.md](aaxis/rules.md); run its check on any diff touching `src/Aaxis/`.

## 16. Follow Oro precedent

When a design question already has an Oro answer (audit, check-connection buttons, feature voters,
notices, integration channels), mirror what core or vendor does and propose it as the default. Do not
copy known core bugs. Look it up with `atlas` before asking the user a design question; ask only when there
is no precedent or it conflicts with a requirement.

