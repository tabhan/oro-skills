#!/usr/bin/env bash
# oro: ">=7.0.0"
# Import qa attachments (var/data archive or an extracted dir) into the app's attachments filesystem via Oro's
# FileManager (GridFS when configured). Skips files already stored. Never touches public/media (it is a cache).
# Usage: import-attachments.sh <archive.tgz|dir> [--env prod] [--project P] [--dry-run]
# Exit: 0 ok, 1 any file failed, 64 usage.
source "$(dirname "$0")/lib/common.sh"
le_init import-attachments "$@"
LE_USAGE="import-attachments.sh <archive.tgz|dir> [--env prod]"
src=${ARGS[0]:-}; env=prod
for i in "${!ARGS[@]}"; do [ "${ARGS[$i]}" = "--env" ] && env=${ARGS[$((i + 1))]:-prod}; done
[ -n "$src" ] && [ -e "$src" ] || usage_exit
case $env in test|behat_test) fail "refusing --env $env: attachments go to a real data stack" ;; esac
tmp=""
if [ -f "$src" ]; then
    [ "$DRY" = 1 ] && { say "would: extract $src and import attachments (env $env)"; exit 0; }
    tmp=$(mktemp -d "${TMPDIR:-/tmp}/oro-attachments.XXXXXX") || fail "mktemp"
    trap '[ -n "$tmp" ] && [ -d "$tmp" ] && rm -rf -- "$tmp"' EXIT
    tar -xzf "$src" -C "$tmp" >> "$LOG" 2>&1 || fail "extract $src"
    dir=$(find "$tmp" -type d -name attachments -print -quit)
    [ -n "$dir" ] || fail "no attachments/ directory in $src"
    root=$(dirname "$dir")
else
    root=$src
fi
[ "$DRY" = 1 ] && { say "would: import $root/attachments (env $env)"; exit 0; }
out=$(ORO_ENV=$env ORO_DEBUG=0 php "$LE_DIR/import-attachments.php" "$PROJECT" "$root" 2>>"$LOG"); rc=$?
say "attachments: $out"
[ $rc -eq 0 ] || fail "some attachments failed (log: $LOG)"
