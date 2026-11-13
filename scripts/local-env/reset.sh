#!/usr/bin/env bash
# oro: ">=7.0.0"
# Reset the local test stack to its baseline: PG clone from template, Mongo restore, ES indices, test session
# Redis db, behat_test log, MQ queues, search reindex. Touches only oro_test* names; never the local data stack.
# Usage: reset.sh [--skip-reindex] [--project P] [--dry-run] [--verbose]
# Exit: 0 ok, 1 phase failed or baseline missing, 3 guard abort, 64 usage.
source "$(dirname "$0")/lib/common.sh"; source "$LE_LIB/stack.sh"
le_init reset "$@"
SKIP=0; [[ " ${ARGS[*]:-} " == *" --skip-reindex "* ]] && SKIP=1
phase() { local n=$1; shift; "$@" || fail "$n (log: $LOG)"; lap "$n"; }

pg_exists "$TEST_BASE" || fail "baseline $TEST_BASE missing; run baseline.sh"
phase pg-clone pg_clone "$TEST_BASE" "$TEST_DB"
phase mongo-restore mongo_copy "$MONGO_BASE" "$MONGO_PRIV"
phase es-drop es_drop_prefix "$ES_PREFIX"
phase redis-session redis_flush_session
truncate_test_log
phase mq-purge mq_purge
if [ "$SKIP" = 0 ]; then
    phase reindex-backoffice mut "reindex backoffice" console oro:search:reindex --env=behat_test
    phase reindex-website mut "reindex website" console oro:website-search:reindex --env=behat_test
fi
total "reset ok"
