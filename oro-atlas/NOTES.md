# Project notes

Project knowledge that is not code (env facts, gotchas, decisions, recipes) lives in
`<project>/.oro-ai/notes/<slug>.md`, untracked and personal. Atlas indexes it in the `notes` shard.
Never put secrets (passwords, tokens, cookies) in a note: the build skips notes that look like they hold one.

```
---
title: one line
kind: gotcha|decision|recipe
surface: always|anchored
anchors: [class:Foo\Bar, service:oro_product.x, entity:Oro\..\Product, workflow:name, bundle:BuckmanProductBundle, path:src/Buckman/**/Export*.php]
updated: 2026-11-13        # optional, defaults to the file's mtime
oro: ">=8.0"               # optional composer range; absent = applies to every version
---
body
```

- `always`: no code anchor (env, servers, ops habits); meant for session start, newest first, capped at 40.
- `anchored`: surfaces next to atlas results for a matching class/service/entity/workflow/bundle/path.
  Path globs: `**` crosses directories, `*` does not. Needs at least one anchor.
- Build resolves each anchor against the index (path: file tree, bundle: `<Name>.php` under src/ then vendor/).
  When every anchor of an anchored note is dead the note is demoted to `always` and flagged `possibly stale`.
- A note with a missing/invalid frontmatter field, unknown kind/anchor type, bad `oro:` range or a secret-like
  string is skipped with a build warning; `atlas notes --lint` lists them.
- A note whose `oro:` range excludes the project's Oro version is inactive: not injected, not attached to queries,
  listed by `atlas notes` only with `--all`.

## Commands

`atlas notes [term...] [--always|--anchored|--lint] [--all] [--limit N] [--json]`: one line per note
(`slug  [kind/surface] title  (flags)  path`), exit 1 when nothing matches. Term words match slug, title, kind,
anchors and body. The shard refreshes itself when a note file changed.
Every `atlas <sub> <term>` hit is followed by `    note: <slug> - <title>` for matching anchored notes
(each note once per output, max 5; `--json` adds `notes` to the hit).

## Python API (for hooks)

Import `atlas.notesindex` (add `<plugin>/oro-atlas` to `sys.path`). All functions take plain dicts.

| Function | Returns |
|----------|---------|
| `load(out_dir)` | shard records (`id`=slug, `title`, `kind`, `surface` effective, `declared`, `anchors` [`type`,`value`,`live`,`dir`], `possibly_stale`, `oro`, `updated`, `file`); `[]` when not built. `out_dir = atlas.common.atlas_dir(root)` |
| `always_notes(notes, version, cap=ALWAYS_CAP)` | `(notes to inject newest first, count held back by the cap)` |
| `anchored_for_path(notes, relpath, version)` | active anchored notes whose path glob or bundle dir covers a project-relative file |
| `anchored_for_hit(notes, record, version)` | same for one atlas query record (id/keys/class/file) |
| `search(notes, term, version, include_inactive)` | matching notes, exact slug first |
| `is_active(note, version)` | False when the `oro:` range excludes `version` (None = unknown: version-neutral only) |
| `fingerprint(root)` | stamp of the note files (drives staleness) |

`version` is `index.json`'s `oro_version`. Hooks must stay quiet when the shard is missing (`load` returns `[]`)
and cap what they print (titles and paths only; the body is read from the file on demand).
