<!-- aaxis-oro:review-rules:start -->
## Review rules

Authors and reviewers apply these to every plan and diff; each is checkable from the text of the plan or diff and
names the failure it prevents.

1. The plan cites a source for every extension-point choice (event, DI tag, service override, datagrid,
   workflow/operation, MQ, config, layout, JS): an `aaxis-oro atlas` hit (`file:line`), an `aaxis-oro:solutions`
   reference or an Oro docs page. A choice without a citation is a finding (`architect-gate`, `aaxis-oro review check
   --plan`). Prevents reinventing an OOTB hook.
2. An Oro core service method is overridden with a stateless `aaxis_aspect.interceptor`. A `decorates:` entry or class
   swap is a finding unless `aaxis-oro atlas unsafe <Class>` lists no concrete-class consumer. Prevents container
   TypeErrors where a consumer typehints the concrete class.
3. A schema, index, unique-constraint or repository change on a standard Oro entity is made in
   `Resources/config/aaxis/entity_extend.yml`, not a hand-written migration or ORM override. Prevents drifting
   duplicates of what the Aaxis mechanism already does.
4. An entity config change is made in `entity_configs.yml` applied by an `AbstractSetEntityConfigs` fixture with a
   version bump; a bare `config`/migration edit is a finding. Prevents config that never reaches existing databases.
5. Code under `src/Aaxis/` does not `use` the project's own namespace. Prevents Aaxis bundles that cannot be reused
   in other projects.
6. Nothing under an `AppBundle/` path is committed or referenced. Prevents leaking spike code.
7. File I/O goes through the Oro/Gaufrette file manager, never raw paths, `file_put_contents` or
   `%kernel.project_dir%`. Prevents breakage on shared or remote storage.

`aaxis-oro review check` verifies rules 2, 5, 6 and 7 mechanically; the others need judgment.
<!-- aaxis-oro:review-rules:end -->
