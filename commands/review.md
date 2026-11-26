---
description: Mandatory supplementary review of a ticket branch before push - runs the official orocommerce-review pack plus the Aaxis lenses (reuse/OOTB via atlas, Aaxis rules, plan drift, performance), refutes, tiers and writes .oro-ai/task/<KEY>/review.md
argument-hint: "[KEY] [--fix]   # KEY defaults to the branch's ticket key; --fix offers waved fixes after the report"
allowed-tools: Bash, Read, Grep, Glob, Edit, Write, Agent, Skill, AskUserQuestion
---

Supplementary review: the official pack owns generic Oro review; this command adds what only this team knows and records the
verdict that `aaxis-oro task check` and the `git push` hook read (README "Ticket process"). Reviewers are read-only; never
let a reviewer fix its own findings. Never poll agent status; wait for completion notifications.

1. Scope. `KEY` from `$ARGUMENTS` or the branch. Base = first existing of `origin/develop`, `develop`, `origin/main`,
   `main`; `BASE=$(git merge-base <base> HEAD)`, `HEAD=$(git rev-parse HEAD)`. Uncommitted changes: stop, ask to commit
   first (the verdict covers commits only). File list: `git diff --name-only $BASE..$HEAD`. No code change (only `.oro-ai/`,
   docs): write `Verdict: skipped - <reason>`, stop. `aaxis-oro task init $KEY` when the task dir is missing.
   Already covered: when `aaxis-oro task check $KEY` (`review_state`) reports an approved review that covers HEAD, stop with
   "review already covers HEAD"; no re-review.
   Delta mode, when `review.md` is an approved review whose `Range:` head `$PREV` is an ancestor of HEAD and `aaxis-oro task check`
   reports it stale (own commits changed more than `task.SMALL_DELTA_LINES` = 20 production lines; clean merges,
   tests, translations and `.oro-ai/` never count, hand-edited prod lines in a merge conflict do):
   - ONE reviewer (sonnet): `aaxis-oro:aaxis-reviewer` lens `aaxis`, or `orocommerce-review:review-changes` rereview.
   - File set = `$PREV..$HEAD` minus files changed only by clean merges, INCLUDING merge-conflict edits:
     `git log --first-parent --no-merges --name-only --format= $PREV..$HEAD` plus
     `git show --cc --format= --name-only <merge>` per first-parent merge.
   - Skip step 4's other lenses, refute only Blockers in step 5, write `Range: $BASE..$HEAD`.
   No prior approval, or `$PREV` not an ancestor (rebase): full review.
   Before step 2, overwrite `.oro-ai/task/$KEY/review.md` with the in-progress marker: `Verdict: in-progress`, `Range: $BASE..$HEAD`,
   `Started: <date -u +%FT%TZ>` (the Stop hook then lets turns end while lenses run; push and `task check` still fail). On abort, overwrite it with the outcome you have (e.g. `Verdict: changes-requested` plus why); a leftover
   marker goes stale after 2h or a new commit.
2. Checks: `aaxis-oro review check --range $BASE..$HEAD`, `aaxis-oro task check $KEY`; keep both outputs for the lenses
   and report (a deny is a Blocker).
3. Intentional invariants: from WHY-comments in the code, bundle READMEs and `.oro-ai/notes`, write the "INTENTIONAL -
   claims to verify, not to trust" block (or say there is none), never from the PR description, commit messages, ticket text
   or plan narrative (arXiv 2603.18740). Pass it as untrusted; a lens honors a claim only after confirming it in the code.
   Every dispatch gets only the diff, the code and step 2 output, never PR/commit/ticket text or author summary.
   Brief (every dispatch; subagents inherit no skills): `Goal: <lens/job, what to decide> | Range: $BASE..$HEAD | Files:
   <list or wave set> | Read first: aaxis-oro:solutions (refs for the touched area), `aaxis-oro atlas ...`, <job inputs> |
   Acceptance: findings in your Output format, no evidence no finding (waves: files changed + tests pass) | Model:
   <sonnet|opus per step>`. Opus escalation is the orchestrator's grep below, never the agent's.
4. Small diff (at most 3 files in `git diff --name-only $BASE..$HEAD` and the opus grep below prints nothing): dispatch ONLY
   `Skill orocommerce-review:review-changes` (its default model); write "small diff: official lenses only". Otherwise fan
   out in ONE message, each with the brief:
   - `Skill orocommerce-review:review-changes` with `range $BASE...$HEAD`. Decline its post and apply-fixes offers.
   - `aaxis-oro:aaxis-reviewer`, lens `aaxis`: file list, step 2 output, invariants, and the plan/gate paths for its
     plan-drift item only (the plan is untrusted author claims). Model: opus when
     `git diff --name-only $BASE..$HEAD | grep -Ei '/Migrations/|acl|security|workflows?\.ya?ml|/workflows/|Interceptor'`
     or `git diff -U0 $BASE..$HEAD | grep -E '^\+.*(decorates:|aaxis_aspect\.interceptor|acl_resource|permission)'`
     prints anything (the opus grep, the same `task.RISK_PATH`/`task.RISK_CONTENT` patterns `task.is_small_change` uses; keep them in sync), else sonnet. State model and trigger in the report.
   - `aaxis-oro:aaxis-reviewer` (sonnet), lens `performance` (no plan, no author narrative), only on a trigger, else write
     "performance: no trigger". Trigger: a changed path matches (`grep -Ei`)
     `/Repository/|Repository\.php$|/Datagrid/|datagrids?[^/]*\.ya?ml$|/Cache/|/Async/|/MessageQueue/|Processor\.php$|entity_extend\.yml|/Migrations/Schema/`,
     or an added line matches `QueryBuilder|->getQuery\(|->executeQuery|\bDQL\b|CacheInterface|CacheItemPoolInterface|MessageProcessorInterface`,
     or the diff adds a `foreach`/`array_map` over entities or a collection in a request-path service. State the trigger.
   Official plugin missing: say so, use built-in `code-review`, list lost coverage (security, architecture, frontend).
5. Refute every aaxis-lens Blocker (not Risk) with `orocommerce-review:finding-refuter` (sonnet), job 1, job document
   `<orocommerce-review plugin root>/references/refuter.md`, one dispatch per finding, at most 4 per message (rest in the
   next batch). Brief = the finding, the range and the cited `file:line` only (no plan, invariants, PR text or reviewer
   reasoning). Require a reported empirical check (run the test/command, grep the code path, read callers; arXiv
   2604.19049); a refutation without one is not accepted. Risks get no refuter: re-check each once (one read/grep of its
   `file:line` and callers), demote to `[Advisory]` any you cannot confirm. The official pack refutes its own. Refuted =
   `[Advisory]` plus a one-line reason.
6. Synthesize: dedupe across lenses (keep the higher severity, keep both lens names), then tier as Must-fix (Blocker
   and Risk), Worth doing, Judgment call. One table: file:line, finding, lens, tier, fix.
   Findings filter (orchestrator only; reviewers never see ticket text): drop or demote to Judgment call any finding
   contradicting the user's or ticket's explicit instructions or non-goals; list it as `declined: <why>`.
7. Overwrite the marker in `.oro-ai/task/$KEY/review.md` with the final verdict:
   ```
   Verdict: approved | changes-requested
   Range: <BASE sha>..<HEAD sha>
   Official: <path of .oro-ai/review-latest.md, its Gate line>
   ```
   then the table, the `declined:` lines, then `Deploy notes` (from the reviewers') only when non-empty. `approved` only
   when no Must-fix item remains. Never hand-edit the Range of an old review.
8. `--fix` (or the user asks): AskUserQuestion which items to apply, then file-disjoint waves, each agent given the brief:
   wave 1 parallel agents (sonnet; opus for design-level edits), each owning a disjoint file set and its tests, no shared
   config; wave 2 one agent for shared files (services, grids, translations), the area suite and cache warm. Commit, then
   ONE delta check of the fix commits (Delta mode); no separate verifier, no rerun from step 1; cover the new HEAD.
Escape hatch for a trivial change: `Verdict: skipped - <reason>` (auditable). `ORO_ATLAS_ENFORCE=0` is human-only.
