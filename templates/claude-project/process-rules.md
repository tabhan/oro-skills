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
<!-- aaxis-oro:process-rules:end -->
