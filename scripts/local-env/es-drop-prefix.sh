#!/usr/bin/env bash
# oro: ">=7.0.0"
# Delete the Elasticsearch indices under a test prefix, by name.
# Usage: es-drop-prefix.sh <prefix> [--project P] [--dry-run] [--verbose]
# Exit: 0 ok or nothing to delete, 3 prefix/index outside local_test.es_prefix, 1 ES unreachable, 64 usage.
source "$(dirname "$0")/lib/common.sh"; source "$LE_LIB/stack.sh"
le_init es-drop-prefix "$@"
LE_USAGE="es-drop-prefix.sh <prefix>"
[ ${#ARGS[@]} -eq 1 ] || usage_exit
es_drop_prefix "${ARGS[0]}"
if [ "$ES_DROPPED" = 0 ]; then say "es: nothing to delete under ${ARGS[0]}"; else say "es: deleted $ES_DROPPED indices under ${ARGS[0]}"; fi
