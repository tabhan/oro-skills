# Decision tables — situation, extension point, forbidden alternative, atlas check

Generic Oro framework lessons distilled from real incidents. Each row: what you are doing, the
right lever, the tempting wrong move, and the `aaxis-oro atlas` query that confirms the lever exists before
you write code. Run `aaxis-oro atlas` from the project root (it prints a STALE line if `composer.lock`
changed; rebuild with `aaxis-oro atlas build`). Source file is cited per row.

The `Oro` column holds a version range (blank = default `>=7.0.0`, see docs/VERSIONING.md); `Topic` groups same-topic variants.

Rows already covered in SKILL.md (service override via interceptor, `getDefault*()`, entity-config
seeding, jsonb, workflow data serialization, asset version, datagrid cache) are not repeated.

## 1. Entities, entity-config, audit

| Situation | Use | Forbidden | Confirm with | Source | Oro | Topic |
| --- | --- | --- | --- | --- | --- | --- |
| Added a mapped field to an entity that already has entity-config enabled; admin save 500s `Field ... is not configurable` | Run `oro:entity-config:update` after the schema migration | Assuming `oro:migration:load --force` registers the field in `oro_entity_config_field` | `atlas entity MenuUpdate` (scopes list shows it is config-enabled) | incident (Buckman) |  | entity-config-field-not-configurable |
| Field added through a form-type extension is invisible in an Oro admin edit form | Add an explicit `form_row()` in the project-level template override of that form | Debugging the form type; the field is in the DOM via `form_rest()` with 0 height | `atlas tag form.type_extension` then `atlas search MenuUpdateType` for the template | incident (Buckman) |  | form-type-extension-field-invisible |
| Product attribute change must appear in Change History | `dataaudit: auditable: true` per field in `entity_configs.yml` + bump `SetEntityConfigs` version + `cache:clear --env=prod` | Writing a bridge listener for serialized enum / multiEnum fields (`is_serialized=1`): Oro already audits them through config iteration (shows option code) | `atlas entity Product` (look for `dataaudit` in scopes) | incident (Buckman) |  | product-attribute-change-history |
| Bulk-normalising stored content (backfill) must not flood Change History | Write through DBAL on purpose in the data fixture so DataAudit is bypassed; make the formatter a fixed point | ORM flush for the backfill (emits one audit row per changed field) | `atlas event oro_importexport.strategy.process_after` for the import-side hook | incident (Buckman) |  | backfill-without-audit-flood |
| Rich-text (TinyMCE) save shows unrelated fields as changed | Store content in the exact shape the editor emits (round-trip stable) | Treating it as an audit bug; the values do genuinely change on re-serialize | n/a (round-trip test: save twice, second save must diff nothing) | incident (Buckman) |  | rich-text-save-shows-unrelated-changes |
| Seeding per-instance admin copy (label/text that varies per row) | A localized text field; render only when non-empty (presence is the switch) | Boolean show/hide toggle plus one fixed translated string | `atlas entity Product` to see existing LFV-style fields first | incident (Buckman) |  | per-instance-admin-copy |

## 2. Import, data fixtures, migrations

| Situation | Use | Forbidden | Confirm with | Source | Oro | Topic |
| --- | --- | --- | --- | --- | --- | --- |
| Listener creates new entities during import and fails `not configured to cascade persist` | Re-bind managed refs with `$em->getReference()` before persisting | Using the onFlush-captured entities: Oro clears the EM between import batches, so they are detached | `atlas event oro_importexport.strategy.process_after`; `atlas search ProcessAfter` | incident (Buckman) |  | import-listener-cascade-persist |
| `oro:migration:data:load` sits at 0% CPU on one fixture | Check for a `pre_flush` listener calling an external service per changed config model; patch the migration only (suspend that listener inside the fixture) | Killing and re-running (orphan child still flushing, concurrent runs deadlock on `oro_entity_config`) | `atlas event oro.entity_config.pre_flush`; diagnose with `/proc/<pid>/wchan`, `ss -tnp`, `pg_stat_activity` | incident (Buckman) |  | data-load-hangs-at-zero-cpu |
| Seeding a `ContentNode` with its own Scope in e2e/fixtures | Set `parentScopeUsed = false` | Leaving the default `true`: a concurrent root-node save recurses via `DefaultVariantScopesResolver` and strips the scope, then `SlugGenerator` deletes slugs (storefront 404) | `atlas entity ContentNode`; `grep -rn parentScopeUsed vendor/oro/commerce/src/Oro/Bundle/WebCatalogBundle` (fields are not indexed) | incident (Buckman) |  | contentnode-own-scope-seeding |

## 3. Build, deploy, cache

| Situation | Use | Forbidden | Confirm with | Source | Oro | Topic |
| --- | --- | --- | --- | --- | --- | --- |
| Deleted a service, listener or compiler-pass class and every request now fatals `Class ... not found` | `rm -rf var/cache/prod var/cache/dev` then `cache:warmup --env=prod` | `cache:clear` alone: it crashes mid-warmup on the same missing class and reuses the container hash | Before deleting: `atlas service oro_product.repository.product` and `atlas tag kernel.event_listener` to find remaining consumers | incident (Buckman) |  | deleted-service-class-not-found |
| `composer require` of a vendor package fails on a platform extension version the lock already tolerates | `--ignore-platform-req=<ext>` for that one extension | Changing the locked package or the host extension | `atlas status` (composer.lock hash) after the require | incident (Buckman) |  | composer-require-platform-ext-mismatch |
| A bundle ships TypeScript with no committed JS; `oro:assets:build` says `tsc not found` or webpack cannot resolve `<bundle>/js/...` | Add `typescript` at the pnpm workspace root (`pnpm add -D -w typescript`), commit `package.json` + lock, then re-run `oro:assets:install` after tsc compiled | Running `assets:install` before tsc (the public bundle dir is never created) | `atlas js orodatagrid` to see which jsmodules alias the bundle registers | incident (Buckman) |  | bundle-typescript-tsc-not-found |
| Oro upgrade adds bundles with new JS deps; CI fails `Module not found` but local passes | Regenerate and commit both `package.json` and `pnpm-lock.yaml` (`composer run-script install-npm-assets`, then `pnpm install --lockfile-only --no-frozen-lockfile`) | Trusting the local build: stale `node_modules` and non-frozen pnpm hide missing deps | `atlas status` (oro/platform version changed) | incident (Buckman) |  | upgrade-new-js-deps-module-not-found |
| Product is published everywhere yet missing from search/PLP | Check `oro_product_visibility` rows with `visibility='hidden'` (core `RestrictIndexProductsEventListener`), set to `config`, resync visibility cache, reindex | Re-running the reindex first | `atlas event restrict_index_entity.product` (lists the 6 restricting listeners) | incident (Buckman) |  | product-missing-from-search-hidden-visibility |

## 4. Frontend (Backbone / Chaplin)

| Situation | Use | Forbidden | Confirm with | Source | Oro | Topic |
| --- | --- | --- | --- | --- | --- | --- |
| Wiring DOM handlers in an Oro view | The view's `events: {}` hash (delegated on `$el`, auto-undelegated on dispose, survives child widget rebuilds such as jstree) | `this.$el.on(...)` / `this.$child.on(...)` inside `initialize()` | `atlas js mediator` for existing patterns to copy | incident (Buckman) |  | backbone-dom-handlers-events-hash |
| jstree lifecycle events (`move_node.jstree`, `select_node.jstree`, `open_node.jstree`, ...) | Bind them on the tree instance, not in the `events` hash (they are namespaced jQuery events fired on the tree element) | Putting them in the hash | `atlas js jstree` (alias `jquery.jstree`) | incident (Buckman) |  | jstree-lifecycle-events |
| Interactive feature with persisted state | Strict MVVM: handlers only mutate a Backbone Model/Collection; the model's own `change`/`add`/`remove` events persist to the backend and views re-render | Handler that calls AJAX then re-renders the DOM | `atlas js page-component`; reuse `BaseView`/`BaseModel`/`BaseCollection` and `data-page-component-view` | incident (Buckman) |  | interactive-feature-persisted-state |

## 5. Workflow and query-building

| Situation | Use | Forbidden | Confirm with | Source | Oro | Topic |
| --- | --- | --- | --- | --- | --- | --- |
| Branching, quorum, last-approver or per-step permission logic in a workflow | A `transition_service` PHP class (`TransitionServiceInterface::isPreConditionAllowed` / `execute`) | Nested `@and`/`@or` with custom alias conditions in YAML. YAML keeps only simple `@equal`, `@assign_value`, ACL strings, and a short `conditional_steps_to` | `atlas workflow <name>` and `atlas operation oro_workflow` for the existing definition and clone chain | incident (Buckman) |  | workflow-quorum-last-approver |
| Two clauses added to one DQL both embed the same helper-built subquery | Collapse into one clause so the subquery alias is declared once | Reusing a builder that hardcodes an alias twice (`'<alias>' is already defined`, 500) | `aaxis-oro atlas unsafe ProductRepository` before intercepting; then run the query through Doctrine's parser, not a string-fragment unit test | incident (Buckman) |  | dql-two-clauses-one-parameter |

## 6. Datagrid frontend metadata

| Situation | Use | Forbidden | Confirm with | Source | Oro | Topic |
| --- | --- | --- | --- | --- | --- | --- |
| Storefront product listing: hide facet options whose count is zero after another filter is applied | A small datagrid extension that runs after the counts extension (extensions sort by descending priority, so use a lower number) and sets the filter metadata `isDisableFiltersEnabled` to false; the stock frontend count helper then removes zero options instead of greying them | Pruning the filter `choices` server side: the count helper rebuilds options from the counts metadata and ignores pruned choices | `atlas grid frontend-product-search-grid`; `atlas tag oro_datagrid.extension` for the counts extension priority | incident (Buckman) |  | facet-zero-count-hide |
