---
name: oro-frontend-knowledge-base
description: >
  Personal notes on OroCommerce frontend gotchas specific to the Buckman project.
  Generic OroCommerce frontend knowledge (JS module system, PageComponent/AppModule
  lifecycle, Webpack asset pipeline, SCSS/BEM architecture, Twig layout blocks,
  AMD→ESM migration, coding standards) is now covered by the official
  oroinc/ai-dev-platform plugin — see plugins/orocommerce-development/skills/develop/references/frontend.md
  and plugins/orocommerce-maintenance/skills/audit-frontend/. Use that plugin first.
  This skill is reserved for real incidents hit while developing Buckman that the
  official docs don't cover.
---

# OroCommerce Frontend Knowledge Base Skill (Buckman-specific)

This knowledge base previously contained a full copy of generic OroCommerce frontend
documentation (JS architecture, PageComponents, AppModules, CSS architecture, Twig
templates, configuration reference, best practices, migration guide). That content
duplicated the official `oroinc/ai-dev-platform` plugin's frontend reference docs and
has been removed (2026-09-10) in favor of pointing to the plugin.

For generic OroCommerce frontend questions, consult:
- `plugins/orocommerce-development/skills/develop/references/frontend.md`
- `plugins/orocommerce-development/skills/develop/references/nuxt-storefront.md`
- `plugins/orocommerce-maintenance/skills/audit-frontend/SKILL.md` and `references/ci-lint-stage.md`
- `plugins/orocommerce-review/agents/frontend-reviewer.md`

## Available Documents (Task → Document Mapping)

None currently. No Buckman-specific frontend incident (e.g. an SRI/asset-versioning
bug, a translation-scope bug, a module-name conflict, a build-config quirk) has been
documented here yet. When a real, concrete incident is hit during Buckman development
that the official plugin docs don't cover, add a new `references/*.md` file describing
the specific incident (symptom, root cause, fix) and list it in the table below —
do not re-add generic explanations of Oro's frontend architecture.

| Task Type | Document File | Key Content |
|----------|--------------|------|
