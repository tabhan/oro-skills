---
name: spec
description: >
  Use when writing or changing a feature spec under /spec, planning a ticket (align ticket AC with spec AC),
  tagging e2e/Functional tests to an AC, or producing AC coverage/verification reports
  (`aaxis-oro spec coverage|report`).
---

# spec

One long-lived spec per feature in the official `/spec/` directory is the single source of truth; ticket dirs are
per-change records. Mechanics (format, tag syntax, CLI flags) live in `references/format.md`; read it when writing a
spec or a tag, not otherwise.

## Decide

| Situation | Do |
| --- | --- |
| New feature with no spec | Create `spec/spec-<purpose>-<feature>.md` the way `orocommerce-discovery:create-spec` does, plus `id` and `status` front matter and `### AC-<n>` blocks (format.md). Approval = normal PR review. |
| Changed obligation | Never edit an AC's meaning or reuse its number: add a new AC, move the old one under `## Retired`. |
| Plan step of a ticket | List every ticket AC next to the spec AC that covers it, or "spec diff needed". Any gap stops the flow until a human resolves it. No reconciliation file. Never edit the ticket without human approval. |
| Writing tests for an AC | Tag the e2e scenario `@spec:<ID>:AC-<n>` or the Functional test `#[Group('spec:<ID>:AC-<n>')]`. Only e2e and Functional count; a Unit test never covers an AC, even if tagged. |
| Existing tests of a feature that now gets a spec | Retro-tag them then. Features without a spec are not retro-tagged. |
| "Is every AC tested?" | `aaxis-oro spec coverage` (static, exit 1 on gaps, unit-only carriers, retired or unknown tags). |
| "Does it actually work?" | Run the suite, then `aaxis-oro spec report` (latest `var/e2e-results/<ts>/results.json`, plus `--junit`); an AC is verified only if a carrier ran and all passed. Quote the report, not memory. |
| Code comments | No ticket, phase or AC ids in code comments. |

Official `REQ-/SEC-/CON-` ids keep their meaning in sections 3 and 4; an AC may cite them with `Covers: REQ-001`.
Plan-time id sweeps (`spec.id-pattern` in `.oro-ai/config.json`) are unaffected: AC ids are scoped by the spec `id`.
