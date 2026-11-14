---
description: Mandatory supplementary review of a ticket branch before push - runs the official orocommerce-review pack plus the Aaxis lenses (reuse/OOTB via atlas, Aaxis rules, plan drift, performance), refutes, tiers and writes .oro-ai/task/<KEY>/review.md
argument-hint: "[KEY] [--fix]   # KEY defaults to the branch's ticket key; --fix offers waved fixes after the report"
allowed-tools: Bash, Read, Grep, Glob, Edit, Write, Agent, Skill, AskUserQuestion
---

Supplementary review: the official pack owns generic Oro review, this command adds what only this team knows and
records a verdict that `aaxis-oro task check` and the `git push` hook read (README "Ticket process"). Reviewers are
read-only; never let a reviewer fix its own findings.

1. Scope. `KEY` from `$ARGUMENTS` or the branch. Base = first existing of `origin/develop`, `develop`, `origin/main`,
   `main`; `BASE=$(git merge-base <base> HEAD)`, `HEAD=$(git rev-parse HEAD)`. Uncommitted changes: stop and ask to
   commit first (the verdict covers commits only). File list: `git diff --name-only $BASE..$HEAD`. No code change
   (only `.oro-ai/`, docs): write `Verdict: skipped - <reason>` and stop. Create the task dir with
   `aaxis-oro task init $KEY` when missing.
   Before step 2, write the in-progress marker to `.oro-ai/task/$KEY/review.md` (overwriting any earlier review;
   this run's verdict replaces it): `Verdict: in-progress`, `Range: $BASE..$HEAD`, `Started: <date -u +%FT%TZ>`.
   The Stop hook then lets turns end while lenses run in the background; push and `task check` still fail. If the
   run aborts, overwrite the marker with the outcome you have (e.g. `Verdict: changes-requested` plus why); a
   leftover marker goes stale after 2h or on a new commit and the Stop hook blocks again.
2. Deterministic checks: `aaxis-oro review check --range $BASE..$HEAD` and `aaxis-oro task check $KEY`; keep both
   outputs for the lenses and the report (a deny is a Blocker).
3. Intentional invariants: from WHY-comments in the code, bundle READMEs and `.oro-ai/notes`, write the
   "INTENTIONAL - claims to verify, not to trust" block (or say there is none). Never source it from the PR
   description, commit messages, ticket text or the plan narrative: author framing makes reviewers miss defects
   (arXiv 2603.18740). Pass it labelled as untrusted; a lens honors a claim only after confirming it in the code.
   Isolation rule for every dispatch below: lenses and refuters judge from the diff (`$BASE..$HEAD`), the code and
   the deterministic step 2 output. Do not pass the PR description, commit messages, ticket text or the author's
   summary of the change.
4. Fan out in ONE message:
   - `Skill orocommerce-review:review-changes` with `range $BASE...$HEAD`. Decline its post and apply-fixes offers.
   - `aaxis-oro:aaxis-reviewer`, lens `aaxis`, with file list, step 2 output, invariants, and the plan/gate paths for its plan-drift item only (the plan is a set of
     untrusted author claims to compare the diff against, never evidence the code is right). Model:
     sonnet by default; opus when the diff is high-risk (migrations, ACL/security, workflow transitions, aspect
     interceptors, `decorates:`). Decide mechanically: opus when
     `git diff --name-only $BASE..$HEAD | grep -Ei '/Migrations/|acl|security|workflows?\.ya?ml|/workflows/|Interceptor'`
     or `git diff -U0 $BASE..$HEAD | grep -E '^\+.*(decorates:|aaxis_aspect\.interceptor|acl_resource|permission)'`
     prints anything. State the model chosen and the trigger in the report.
   - `aaxis-oro:aaxis-reviewer` (sonnet), lens `performance` (no plan, no author narrative), only when the diff touches repositories, entity
     mappings, `entity_extend.yml`, migrations, DQL/QueryBuilder/SQL, grid datasources, caches or MQ processors;
     otherwise note "performance: no trigger".
   If the official plugin is missing, say so, fall back to the built-in `code-review` skill and list the lost
   coverage (security, architecture, frontend) in the report.
5. Refute every Blocker/Risk from the aaxis lenses with `orocommerce-review:finding-refuter` (sonnet), job 1, job
   document `<orocommerce-review plugin root>/references/refuter.md`, one dispatch per finding, in parallel. The
   brief is the finding, the range and the cited `file:line` only: no plan, invariants block, PR text or reviewer
   reasoning beyond the finding. Tell the refuter to prefer an empirical check (run the test or command, grep the
   code path, read the callers) over agreeing or disagreeing with the reviewer, and to report the check it ran
   (arXiv 2604.19049); a refutation without a check is not accepted. The official pack refutes its own. A refuted
   finding becomes `[Advisory]` with the reason on one line.
6. Synthesize: dedupe across lenses (keep the higher severity, keep both lens names), then tier as Must-fix (Blocker
   and Risk), Worth doing, Judgment call. One table: file:line, finding, lens, tier, fix.
7. Overwrite the marker in `.oro-ai/task/$KEY/review.md` with the final verdict:
   ```
   Verdict: approved | changes-requested
   Range: <BASE sha>..<HEAD sha>
   Official: <path of .oro-ai/review-latest.md, its Gate line>
   ```
   then the table, then a `Deploy notes` section (from the reviewers' Deploy notes) only when non-empty. `approved` only when no Must-fix item remains. Never hand-edit the Range of an old review: new
   commits need a new review (re-review mode of the official skill is fine for the delta).
8. `--fix` (or the user asks): AskUserQuestion which items to apply, then file-disjoint waves - wave 1 parallel agents
   (sonnet; opus for design-level edits) each owning a disjoint file set and its tests, no shared config; wave 2 one
   agent for shared files (services, grids, translations) plus the area suite and cache warm. Commit, then verify with
   a separate sonnet agent and rerun this command from step 1: the verdict must cover the new HEAD.

Escape hatch for a trivial change: `Verdict: skipped - <reason>` (auditable). `ORO_ATLAS_ENFORCE=0` is human-only.
