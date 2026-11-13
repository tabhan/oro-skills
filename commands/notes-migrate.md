---
description: Migrate this project's Claude auto-memory into .oro-ai/notes (classify, confirm, apply)
allowed-tools: Bash, Read
---

Migrate the project auto-memory to atlas notes. Mechanics: `atlas/NOTES.md` (format) and `aaxis-oro memory --help`.

1. Run `aaxis-oro memory inventory`. It prints `nothing to migrate` when done: say so and stop.
2. Classify every row (read a file only when the line is not enough):
   - `global`: cross-project personal preference or habit (applies in any project). Kept in place, marked `scope: global`.
   - `always`: project fact with no code anchor (env, servers, ops habit): note with `surface: always`.
   - `anchored`: tied to a class/service/entity/workflow/bundle/path: note with `surface: anchored` and `anchors`.
   - `stale`: obsolete, or already covered by an aaxis-oro skill or rule: delete (check `aaxis-oro atlas notes`/skills before claiming covered).
   Prefer `anchored` over `always` whenever a real anchor exists; the always tier is capped at 40.
3. Present ONE table: file | class | slug/anchors (notes) | reason. Wait for the user's confirmation or edits. No writes before it.
4. Build the plan JSON in the scratchpad: `{"items":[{"file","action":"note|delete|global","slug","title","kind":"gotcha|decision|recipe","surface","anchors":[],"body","suggest"}]}`.
   - Body: the fact in a few lines, English, no secrets (passwords, tokens, cookies, session ids): redact them; apply skips any note that looks like it holds one.
   - `suggest`: only when the item generalizes beyond this project; it is reported, never applied to oro-skills.
5. Run `aaxis-oro memory apply --plan <file>`. It writes the notes, backs up and deletes migrated memories, drops their MEMORY.md index lines, marks globals and rebuilds the notes shard. Report its output (at most 15 lines) and any `suggest:` lines.

Idempotent: re-running reports `nothing to migrate`. Never edit or delete files in the memory dir by hand.
