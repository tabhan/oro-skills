---
name: atlas
description: >-
  Run FIRST (before grep or reading vendor/) for any Oro question of the form "which event / DI tag /
  service / datagrid / workflow / operation / MQ topic / system config / layout block / mediator event /
  entity exists or should I hook into": `aaxis-oro atlas <subcommand> <term>` answers from a generated index of
  vendor/ and src/ with file:line. Use BEFORE writing an event listener, decorator, service override,
  DI tag, datagrid extension, workflow/operation, MQ processor, system config field, layout block or
  jsmodules entry, to reuse the OOTB hook. Also use at design/investigation time, before reading
  vendor/ to learn how Oro wires something. Run `aaxis-oro atlas unsafe <Class>` before any `decorates:`.
---

# atlas

Generated index of Oro extension points. Answers "which hook already exists?" with `file:line`
instead of grepping 14k services by hand. Details: [README.md](README.md).

## Routing: task -> command

| Task | Command |
|------|---------|
| Hook into something happening (listener) | `aaxis-oro atlas event <name-fragment>` |
| Register a service in a collection (provider, extension, voter) | `aaxis-oro atlas tag <tag-fragment>` |
| Find an existing service / its class and id | `aaxis-oro atlas service <fragment>` |
| Override or wrap a core service | `aaxis-oro atlas unsafe <Class>` first, then `aaxis-oro atlas service` |
| Extend a datagrid (columns, filters, listener) | `aaxis-oro atlas grid <grid-name>` |
| Add/alter a workflow or its transitions | `aaxis-oro atlas workflow <name>` |
| Add a button/action (operation, action group) | `aaxis-oro atlas operation <name>` |
| Async work (topic, processor) | `aaxis-oro atlas mq <fragment>` |
| New system config field / read an existing one | `aaxis-oro atlas config <fragment>` |
| Layout block type, data provider, layout update | `aaxis-oro atlas layout <fragment>` |
| jsmodules entry, mediator event, JS component | `aaxis-oro atlas js <fragment>` |
| Entity table, class, extend/config | `aaxis-oro atlas entity <fragment>` |
| Unsure which category | `aaxis-oro atlas search <fragment>` |
| Project notes (gotchas, decisions, env facts) | `aaxis-oro atlas notes <term>` (format: [NOTES.md](NOTES.md)) |
| Is the index fresh? | `aaxis-oro atlas status` |

## Rules

- `aaxis-oro atlas unsafe <Class>` lists classes typehinted concretely by other constructors. If the target
  is listed, `decorates:` breaks the container: use `aaxis_aspect.interceptor` (see the solutions skill, override-core-service.md).
- Reuse an OOTB hook when one exists; only add a new event/tag/extension point if the atlas has none.
- A `STALE` line (`aaxis-oro atlas status` exits 2) means the index is out of date. Atlas never rebuilds by itself: run
  `aaxis-oro atlas build --incremental` (needs the project's `php bin/console` working) or ask the user to, before trusting results.
- Investigation counts: run atlas before reading vendor/, not only before editing. Subagents get this
  reminder from the SubagentStart hook.
- If `.oro-ai/atlas/` is missing, run `aaxis-oro atlas setup <root>` once (builds; plain
  rebuild: `aaxis-oro atlas build --project <root>`). Output is git-ignored.
- If `aaxis-oro` is not on PATH, use `${CLAUDE_PLUGIN_ROOT}/bin/aaxis-oro` (or `$ORO_SKILLS_DIR/bin/aaxis-oro`); pass `--project <root>` after `atlas`.
- Add `--json` to any query or `status` for machine-readable output.
- Treat hits as pointers: open the `file:line` before relying on a signature.
