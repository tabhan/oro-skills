#!/usr/bin/env bash
# oro: ">=7.0.0"
# Build the test baseline (PG template + Mongo private baseline) from a fresh oro:install, or no-op when the
# baseline_key (composer.lock + Migrations + data fixtures hash) is unchanged. Touches only oro_test* names.
# Usage: baseline.sh [--refresh] [--project P] [--dry-run] [--verbose]   (a rebuild takes ~8 minutes)
# Exit: 0 ok or up to date, 1 failure, 3 guard abort, 64 usage.
source "$(dirname "$0")/lib/common.sh"; source "$LE_LIB/stack.sh"
le_init baseline "$@"
REFRESH=0; [[ " ${ARGS[*]:-} " == *" --refresh "* ]] && REFRESH=1
key=$("$LE_LIB/baseline-key.sh" "$PROJECT") || fail "baseline key"
if [ "$REFRESH" = 0 ] && [ "$key" = "$BASELINE_KEY" ] && pg_exists "$TEST_BASE" && mongo_list | grep -qx "$MONGO_BASE"; then
    say "baseline: up to date (${key:0:12})"; exit 0
fi
[ -f "$PROJECT/.env-app.behat_test.local" ] || [ "$DRY" = 1 ] || fail ".env-app.behat_test.local missing; run setup first"
email=$(dotenv_get ORO_TEST_INSTALL_USER_EMAIL); org=$(dotenv_get ORO_TEST_INSTALL_ORGANIZATION_NAME)
[ -n "$email" ] || email=admin@example.com; [ -n "$org" ] || org=Oro
say "baseline: rebuilding (${BASELINE_KEY:0:12} -> ${key:0:12})"
le_guard oro_test "$TEST_DB"
pg_drop "$TEST_BASE" && pg_drop "$TEST_DB" || fail "pg drop"
mut "create $TEST_DB" pg -c "CREATE DATABASE \"$TEST_DB\"" || fail "create db"
mut "uuid-ossp in $TEST_DB" dx pgsql psql -U postgres -d "$TEST_DB" -qc 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"' || fail "extension"
es_drop_prefix "$ES_PREFIX"; redis_flush_session; mq_ensure_vhost; mq_purge
for m in "$MONGO_PUB" "$MONGO_PRIV" "$MONGO_BASE"; do mongo_drop "$m" || fail "mongo drop $m"; done
lap prepare
mut "oro:install --env=behat_test (slow)" console oro:install --env=behat_test --no-interaction --timeout=3000 \
    --language="$ADMIN_LANG" --formatting-code="$ADMIN_LANG" --organization-name="$org" \
    --user-name=admin --user-email="$email" --user-firstname="$ADMIN_FIRST" --user-lastname="$ADMIN_LAST" --user-password=admin \
    --application-url="https://$TEST_DOMAIN" --sample-data=n --skip-download-translations || fail "oro:install (log: $LOG)"
lap install
mut "close $TEST_DB sessions" pg -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$TEST_DB' AND pid<>pg_backend_pid()"
mut "pg template $TEST_BASE" pg -c "CREATE DATABASE \"$TEST_BASE\" TEMPLATE \"$TEST_DB\"" || fail "template clone"
mongo_copy "$MONGO_PRIV" "$MONGO_BASE" || fail "mongo baseline"
[ "$DRY" = 1 ] || python3 "$LE_LIB/envsh.py" set --project "$PROJECT" local_test.baseline_key "$key" || fail "env.yml write"
lap snapshot
total "baseline ok"
