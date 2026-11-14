<!-- aaxis-oro:process-rules:start -->
## Ticket process

Required for every ticket in this project. These steps override any command's or workflow's "fast path": a fast path
may skip plan documents, phase lists and approvals, never the steps below.

1. `aaxis-oro task init <TICKET>` creates `.oro-ai/task/<TICKET>/` (`STATUS.md`, `plan.md`); update `STATUS.md` at
   each milestone.
2. An extension-point choice (event, DI tag, service override, datagrid, workflow/operation, MQ, config, layout, JS)
   goes into `plan.md` with its sources (Extension design rules), then through `aaxis-oro:architect-gate`, whose
   verdict is saved to `.oro-ai/task/<TICKET>/architect-gate.md` before Execute. A trivial change records
   `Verdict: skipped - <reason>` instead.
3. Test-first Playwright-BDD e2e (`aaxis-oro:e2e`) for production code: the scenario is written and seen red before
   the fix. Behat is deprecated; a unit test supplements, never replaces, the e2e scenario.
4. Before commit: `aaxis-oro task check` and `aaxis-oro review check`. The commit hook denies an extension-point
   commit on a ticket branch without an approved or skipped gate verdict, and warns on missing `STATUS.md` or e2e.
5. Supplementary review (aaxis-oro) before push: `/aaxis-oro:review` runs the official `orocommerce-review` pack plus
   the Aaxis lenses and writes `.oro-ai/task/<TICKET>/review.md` (`Verdict:` and `Range: <base>..<head>`). The
   `git push` hook and `aaxis-oro task check` fail until an approved verdict covers HEAD; new code commits need a new
   review. A Stop hook enforces it: once the ticket's code is committed and the tree is clean, Claude cannot end its
   turn until `/aaxis-oro:review` has run (or `changes-requested` findings are fixed and re-reviewed). A trivial
   change records `Verdict: skipped - <reason>` instead.
6. Root cause before fix, for every problem handled (bug, CI or test failure, review finding, data issue): before
   proposing a fix, state the root cause with evidence (file:line, log, reproduction) and the layer it lives in (code /
   test / data / environment / config / upstream); the fix changes that layer. Making the symptom disappear elsewhere
   (skip, suppress, catch-all, retry, loosened assertion, mocking away the failing dependency, special-cased data) is a
   workaround: label it so and get the user's approval. "Out of scope" never justifies fixing a symptom instead of the
   cause; say so and let the user decide. A delegated diagnosis returns the layer and a root-cause fix recommendation.
   `plan.md` records it under `## Root cause` (`n/a - feature` when there is no defect).
7. When reporting work, do not list standard deploy steps; mention deploy actions only when `review.md` has Deploy
   notes.
<!-- aaxis-oro:process-rules:end -->
