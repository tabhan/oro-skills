#!/usr/bin/env bash
# oro: ">=7.0.0"
# Drop one test-stack Mongo database (name must start with oro_test_).
# Usage: mongo-drop.sh <name> [--project P] [--dry-run]
# Exit: 0 ok or already absent, 3 guard abort, 64 usage.
source "$(dirname "$0")/lib/common.sh"; source "$LE_LIB/stack.sh"
le_init mongo-drop "$@"
LE_USAGE="mongo-drop.sh <name>"
[ ${#ARGS[@]} -eq 1 ] || usage_exit
le_guard oro_test_ "${ARGS[0]}"
if mongo_list | grep -qx "${ARGS[0]}"; then mongo_drop "${ARGS[0]}" && say "mongo: dropped ${ARGS[0]}" || fail "mongo drop ${ARGS[0]}"; else say "mongo: nothing to drop (${ARGS[0]} absent)"; fi
