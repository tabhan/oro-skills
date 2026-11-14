<!-- aaxis-oro:process-rules:start -->
## Ticket process

Required for every ticket. These steps override any command's or workflow's "fast path": a fast path may skip plan
documents, phase lists and approvals, never the steps below. Rationale and detail: `aaxis-oro:solutions`
`process-rules-rationale.md`.

1. `aaxis-oro task init <TICKET>` creates `.oro-ai/task/<TICKET>/` (`STATUS.md`, `plan.md`); update `STATUS.md` at
   each milestone.
2. An extension-point choice (event, DI tag, service override, datagrid, workflow/operation, MQ, config, layout, JS)
   goes into `plan.md` with its sources (Extension design rules), then through `aaxis-oro:architect-gate`; save the
   verdict to `.oro-ai/task/<TICKET>/architect-gate.md` before Execute. A trivial change records
   `Verdict: skipped - <reason>` instead.
3. Test-first Playwright-BDD e2e (`aaxis-oro:e2e`) for production code: the scenario is written and seen red before
   the fix. Behat is deprecated; a unit test supplements, never replaces, the e2e scenario.
4. Before commit: `aaxis-oro task check` and `aaxis-oro review check`. The commit hook denies an extension-point
   commit on a ticket branch without an approved or skipped gate verdict, and warns on missing `STATUS.md` or e2e.
5. Before push: `/aaxis-oro:review` (official `orocommerce-review` pack plus the Aaxis lenses) writes
      `.oro-ai/task/<TICKET>/review.md` (`Verdict:`, `Range: <base>..<head>`). The `git push` hook and `aaxis-oro task
   check` fail until an approved verdict covers HEAD; new code commits need a
   new review; a Stop hook blocks ending the turn once the ticket's code is committed and the tree is clean until the
   review ran or `changes-requested` findings are fixed and re-reviewed. A trivial change records
   `Verdict: skipped - <reason>` instead.
6. Root cause before fix, for every problem (bug, CI/test failure, review finding, data issue): state the root cause
   with evidence (file:line, log, reproduction) and its layer (code / test / data / environment / config / upstream)
   before proposing a fix, and change that layer. A change that only hides the symptom (skip, suppress, catch-all,
   retry, loosened assertion, mocked-away dependency, special-cased data) is a workaround: label it and get the user's
   approval; "out of scope" never justifies it: say so and let the user decide. A delegated diagnosis returns the
   layer and a root-cause fix. After three failed fix attempts for the same problem, stop and report what failed, what
   was tried and the current hypothesis. Never weaken,
   skip or delete a test to make a run pass; if the test is wrong, say why in `plan.md` and get approval. `plan.md`
   records it under `## Root cause` (`n/a - feature` when there is no defect).
7. When reporting work, list deploy actions only when `review.md` has Deploy notes, never the standard steps.
<!-- aaxis-oro:process-rules:end -->
