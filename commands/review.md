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
   (only `.oro-ai/`, docs): write `Verdict: skipped - <reason>` and stop.
2. Deterministic checks: `aaxis-oro review check --range $BASE..$HEAD` and `aaxis-oro task check $KEY`; keep both
   outputs for the lenses and the report (a deny is a Blocker).
3. Intentional invariants: from WHY-comments, the ticket, `plan.md`, bundle READMEs and `.oro-ai/notes`, write the
   "INTENTIONAL - do NOT flag" block (or say there is none). Pass it verbatim to every lens.
4. Fan out in ONE message:
   - `Skill orocommerce-review:review-changes` with `range $BASE...$HEAD`. Decline its post and apply-fixes offers.
   - `aaxis-oro:aaxis-reviewer` (opus), lens `aaxis`, with plan/gate paths, file list, step 2 output, invariants.
   - `aaxis-oro:aaxis-reviewer` (sonnet), lens `performance`, only when the diff touches repositories, entity
     mappings, `entity_extend.yml`, migrations, DQL/QueryBuilder/SQL, grid datasources, caches or MQ processors;
     otherwise note "performance: no trigger".
   If the official plugin is missing, say so, fall back to the built-in `code-review` skill and list the lost
   coverage (security, architecture, frontend) in the report.
5. Refute every Blocker/Risk from the aaxis lenses with `orocommerce-review:finding-refuter` (sonnet), job 1, job
   document `<orocommerce-review plugin root>/references/refuter.md`, one dispatch per finding, in parallel. The
   official pack refutes its own. A refuted finding becomes `[Advisory]` with the reason on one line.
6. Synthesize: dedupe across lenses (keep the higher severity, keep both lens names), then tier as Must-fix (Blocker
   and Risk), Worth doing, Judgment call. One table: file:line, finding, lens, tier, fix.
7. Write `.oro-ai/task/$KEY/review.md` (create the dir with `aaxis-oro task init $KEY`):
   ```
   Verdict: approved | changes-requested
   Range: <BASE sha>..<HEAD sha>
   Official: <path of .oro-ai/review-latest.md, its Gate line>
   ```
   then the table. `approved` only when no Must-fix item remains. Never hand-edit the Range of an old review: new
   commits need a new review (re-review mode of the official skill is fine for the delta).
8. `--fix` (or the user asks): AskUserQuestion which items to apply, then file-disjoint waves - wave 1 parallel agents
   (sonnet; opus for design-level edits) each owning a disjoint file set and its tests, no shared config; wave 2 one
   agent for shared files (services, grids, translations) plus the area suite and cache warm. Commit, then verify with
   a separate sonnet agent and rerun this command from step 1: the verdict must cover the new HEAD.

Escape hatch for a trivial change: `Verdict: skipped - <reason>` (auditable). `ORO_ATLAS_ENFORCE=0` is human-only.
