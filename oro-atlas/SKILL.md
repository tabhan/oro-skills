---
name: oro-atlas
description: >-
  Run FIRST (before grep or reading vendor/) for any Oro question of the form "which event / DI tag /
  service / datagrid / workflow / operation / MQ topic / system config / layout block / mediator event /
  entity exists or should I hook into": `atlas <subcommand> <term>` answers from a generated index of
  vendor/ and src/ with file:line. Use BEFORE writing an event listener, decorator, service override,
  DI tag, datagrid extension, workflow/operation, MQ processor, system config field, layout block or
  jsmodules entry, to reuse the OOTB hook. Also use at design/investigation time, before reading
  vendor/ to learn how Oro wires something. Run `atlas unsafe <Class>` before any `decorates:`.
---

# oro-atlas

Generated index of Oro extension points. Answers "which hook already exists?" with `file:line`
instead of grepping 14k services by hand. Details: [README.md](README.md).

## Routing: task -> command

| Task | Command |
|------|---------|
| Hook into something happening (listener) | `atlas event <name-fragment>` |
| Register a service in a collection (provider, extension, voter) | `atlas tag <tag-fragment>` |
| Find an existing service / its class and id | `atlas service <fragment>` |
| Override or wrap a core service | `atlas unsafe <Class>` first, then `atlas service` |
| Extend a datagrid (columns, filters, listener) | `atlas grid <grid-name>` |
| Add/alter a workflow or its transitions | `atlas workflow <name>` |
| Add a button/action (operation, action group) | `atlas operation <name>` |
| Async work (topic, processor) | `atlas mq <fragment>` |
| New system config field / read an existing one | `atlas config <fragment>` |
| Layout block type, data provider, layout update | `atlas layout <fragment>` |
| jsmodules entry, mediator event, JS component | `atlas js <fragment>` |
| Entity table, class, extend/config | `atlas entity <fragment>` |
| Unsure which category | `atlas search <fragment>` |
| Is the index fresh? | `atlas status` |

## Rules

- `atlas unsafe <Class>` lists classes typehinted concretely by other constructors. If the target
  is listed, `decorates:` breaks the container: use `aaxis_aspect.interceptor` (see oro-conventions §2).
- Reuse an OOTB hook when one exists; only add a new event/tag/extension point if the atlas has none.
- A `STALE` line (`atlas status` exits 2) means the index is out of date: run
  `atlas-build --incremental` (needs the project's `php bin/console` working) before trusting results.
- Investigation counts: run atlas before reading vendor/, not only before editing. Subagents get this
  reminder from the SubagentStart hook.
- If `.claude/atlas/` is missing, run `atlas-setup <root>` once (registers hooks, then builds; plain
  rebuild: `atlas-build --project <root>`). Output is git-ignored.
- If `atlas` is not on PATH, use `$ORO_SKILLS_DIR/oro-atlas/bin/atlas` (default checkout:
  `/opt/projects/oro-skills/oro-atlas/bin/atlas`) with `--project <root>`.
- Add `--json` to any query or `status` for machine-readable output.
- Treat hits as pointers: open the `file:line` before relying on a signature.
