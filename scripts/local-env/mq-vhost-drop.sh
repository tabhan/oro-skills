#!/usr/bin/env bash
# oro: ">=7.0.0"
# Delete one test-stack RabbitMQ vhost (name must start with oro_test and equal local_test.mq_vhost).
# Usage: mq-vhost-drop.sh <name> [--project P] [--dry-run]
# Exit: 0 ok or already absent, 3 guard abort, 64 usage.
source "$(dirname "$0")/lib/common.sh"; source "$LE_LIB/stack.sh"
le_init mq-vhost-drop "$@"
LE_USAGE="mq-vhost-drop.sh <name>"
[ ${#ARGS[@]} -eq 1 ] || usage_exit
le_guard oro_test "${ARGS[0]}"
[ "${ARGS[0]}" = "$MQ_VHOST" ] || guard_abort "refusing '${ARGS[0]}': not the configured vhost '$MQ_VHOST'"
if vhost_exists "${ARGS[0]}"; then mut "delete vhost ${ARGS[0]}" dx rabbitmq rabbitmqctl delete_vhost "${ARGS[0]}" && say "mq: deleted vhost ${ARGS[0]}" || fail "vhost delete"; else say "mq: nothing to delete (${ARGS[0]} absent)"; fi
