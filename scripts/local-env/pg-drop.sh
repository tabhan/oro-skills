#!/usr/bin/env bash
# oro: ">=7.0.0"
# Drop one test-stack PostgreSQL database (name must start with oro_test and not be the local data db).
# Usage: pg-drop.sh <name> [--project P] [--dry-run]
# Exit: 0 ok or already absent, 3 guard abort, 64 usage.
source "$(dirname "$0")/lib/common.sh"; source "$LE_LIB/stack.sh"
le_init pg-drop "$@"
LE_USAGE="pg-drop.sh <name>"
[ ${#ARGS[@]} -eq 1 ] || usage_exit
le_guard oro_test "${ARGS[0]}"
if pg_exists "${ARGS[0]}"; then pg_drop "${ARGS[0]}" && say "pg: dropped ${ARGS[0]}" || fail "pg drop ${ARGS[0]}"; else say "pg: nothing to drop (${ARGS[0]} absent)"; fi
