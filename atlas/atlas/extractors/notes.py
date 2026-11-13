"""Project notes (.oro-ai/notes/*.md): validates frontmatter, resolves anchors against the other shards."""
import sys

from .. import notesindex

NAME = "notes"
ORDER = 200
DEPENDS = ("services", "entities", "workflows")


def _ids(ctx, shard):
    return {notesindex.normalize(v) for r in ctx.shard(shard) for v in [r.get("id", "")] + list(r.get("keys", []))}


def extract(ctx):
    notes, skipped = notesindex.read_notes(ctx.root)
    for slug, reason in skipped:
        sys.stderr.write("atlas: note %s skipped: %s\n" % (slug, reason))
    resolver = notesindex.Resolver(ctx.root, {s: _ids(ctx, s) for s in ("services", "entities", "workflows")},
                                   ctx.locator.locate)
    records = [notesindex.resolve_note(n, resolver) for n in notes]
    always = sum(1 for r in records if r["surface"] == "always")
    if always > notesindex.ALWAYS_CAP:
        sys.stderr.write("atlas: %d always-tier notes exceed the cap of %d; only the newest %d are injected at session start\n"
                         % (always, notesindex.ALWAYS_CAP, notesindex.ALWAYS_CAP))
    return records
