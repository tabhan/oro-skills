# Process and review rules: rationale

The synced `CLAUDE_project.md` blocks ("Ticket process", "Review rules") keep each rule to a checkable line. This file
holds the why and the detail; open it when a rule is disputed or a reviewer needs the reasoning.

## Ticket process

- **Fast paths.** A command's fast path may skip plan documents, phase lists and approvals; it never skips the numbered
  steps, because the commit, push and Stop hooks read their evidence (`task check`, `architect-gate.md`, `review.md`).
- **Step 5, Stop hook.** Once the ticket's code is committed and the tree is clean, Claude cannot end its turn until
  `/aaxis-oro:review` has run (or `changes-requested` findings are fixed and re-reviewed). `git push` and
  `aaxis-oro task check` fail until an approved verdict covers HEAD; a new code commit needs a new review.
- **Step 6, root cause before fix.** For every problem handled (bug, CI or test failure, review finding, data issue),
  before proposing a fix state the root cause with evidence (file:line, log, reproduction) and the layer it lives in:
  code / test / data / environment / config / upstream. The fix changes that layer. Making the symptom disappear
  elsewhere (skip, suppress, catch-all, retry, loosened assertion, mocking away the failing dependency, special-cased
  data) is a workaround: label it so and get the user's approval. "Out of scope" never justifies fixing a symptom
  instead of the cause; say so and let the user decide. A delegated diagnosis returns the layer and a root-cause fix
  recommendation. After three fix attempts for the same problem that did not resolve it, stop and report: what failed,
  what was tried, and the current root-cause hypothesis. Never weaken an assertion, skip a test or delete a test to
  make a run pass; if the test itself is wrong, say why in `plan.md` and get approval.
- **Step 7.** Standard deploy steps (cache clear/warmup, `oro:migration:load`, `oro:migration:data:load`, assets
  build, cron/consumers) are never listed; only the reviewers' Deploy notes are.

## Review rules: the failure each prevents

1. Cited extension points: prevents reinventing an OOTB hook.
2. Interceptor instead of `decorates:` / class swap: prevents container TypeErrors where a consumer typehints the
   concrete class.
3. `entity_extend.yml` for standard-entity schema, index, unique or repository changes: prevents drifting duplicates of
   what the Aaxis mechanism already does.
4. `entity_configs.yml` plus an `AbstractSetEntityConfigs` fixture with a version bump: prevents config that never
   reaches existing databases.
5. No project namespace under `src/Aaxis/`: prevents Aaxis bundles that cannot be reused in other projects.
6. Nothing under `AppBundle/`: prevents leaking spike code.
7. File I/O through the Oro/Gaufrette file manager: prevents breakage on shared or remote storage.
