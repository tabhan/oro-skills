<!-- aaxis-oro:review-rules:start -->
## Review rules

Reviewers and authors apply these rules to every change; each names the failure it prevents.

1. Cite the source of every extension-point choice (event, DI tag, service override, datagrid, workflow/operation,
   MQ, config, layout, JS) as an `aaxis-oro atlas` hit (`file:line`), an `aaxis-oro:solutions` reference or an Oro docs
   page. Prevents reinventing an OOTB hook and plans nobody can verify.
2. Override an Oro core service method with an `aaxis_aspect.interceptor` (stateless), never a class swap or
   `decorates:`, unless `aaxis-oro atlas unsafe <Class>` lists no concrete-class consumer. Prevents container
   TypeErrors where a consumer typehints the concrete class.
3. Use the Aaxis standard way when one exists (`entity_configs.yml`, `entity_extend.yml`, provider interface + DI-tag
   registry, bundles from the catalogue). Prevents hand-written migrations and drifting duplicates of Aaxis features.
4. Code under `src/Aaxis/` must not `use` the project's own namespace. Prevents Aaxis bundles that cannot be reused in
   other projects.
5. Never commit anything under an `AppBundle/` path, and do file I/O through the Oro/Gaufrette file manager, not raw
   paths or `%kernel.project_dir%`. Prevents leaking spike code and breakage on shared or remote storage.

`aaxis-oro review check` verifies rules 2, 4 and 5 mechanically; rules 1 and 3 need judgment.
<!-- aaxis-oro:review-rules:end -->
