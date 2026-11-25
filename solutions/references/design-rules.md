# Design rules: files, providers, Aaxis, precedent

## File access goes through Gaufrette

Code and tests never touch application data by path: no `%kernel.project_dir%`-based paths, no direct `fopen`,
`file_put_contents`, `unlink`. Use the Gaufrette filesystem or `FileManager` that owns the data (import/export,
attachments, generated JS translations, ...) so it works on any backend (GridFS, S3, local) and a test never depends
on, or leaves behind, host files. Only system temp (`sys_get_temp_dir()`) is exempt. A test action that produces a
file returns its content (or a storage key) and deletes it after the read.

Review check (flag, then judge each hit):

```bash
grep -rnE "file_put_contents|fopen|unlink|kernel.project_dir" src --include=*.php
```

## External providers sit behind an interface

An integration with an external service (LLM, payment, search, ERP) is designed interface first: a provider
interface, optional capability interfaces (batch, streaming), a DI-tag registry that resolves the provider by key,
per-provider configuration. The vendor SDK is imported only inside that provider's directory. Swapping or adding a
provider is a new class + tag + config and nothing else. Check every plan that adds an SDK for this. If an Aaxis
bundle already offers the registry, extend it ([aaxis/rules.md](aaxis/rules.md)).

## Aaxis bundles never depend on the project

Code under `src/Aaxis/` must not reference project classes, entities, services or translations. Run the check in
[aaxis/rules.md](aaxis/rules.md) on any diff touching `src/Aaxis/`.

## Follow Oro precedent

When a design question already has an Oro answer (audit, check-connection buttons, feature voters, notices,
integration channels), mirror core or vendor and propose it as the default; do not copy known core bugs. Look it up
with `atlas` before asking the user; ask only when there is no precedent or it conflicts with a requirement.
