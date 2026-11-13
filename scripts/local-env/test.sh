#!/usr/bin/env bash
# oro: ">=7.0.0"
# Run phpunit, e2e or a console command against an EXPLICIT target after verifying what that target really
# resolves to (db, search prefix, MQ vhost, Mongo dbs, session db) against env.yml. No default target.
# Usage: aaxis-oro test [--project P] <local|local-test> <phpunit|e2e|console|verify> [args...]
#   local-test  phpunit (ORO_ENV=test), e2e (aaxis:test:e2e on behat_test), console (default --env=behat_test)
#   local       console only (default --env=prod); tests never run against the local data stack
#   verify      only print the verification line
# Exit: command's own code; 3 target mismatch or refused combination; 64 usage.
source "$(dirname "$0")/lib/common.sh"
src_project=$PWD
if [ "${1:-}" = "--project" ]; then [ -d "${2:-}" ] || { echo "usage: --project needs a directory" >&2; exit 64; }; src_project=$(cd "$2" && pwd); shift 2; fi
TARGET=${1:-}; ACTION=${2:-}
case $TARGET in local|local-test) ;; *) echo "usage: aaxis-oro test [--project P] <local|local-test> <phpunit|e2e|console|verify> [args...]" >&2; exit 64 ;; esac
case $ACTION in phpunit|e2e|console|verify) ;; *) echo "usage: aaxis-oro test <local|local-test> <phpunit|e2e|console|verify> [args...]" >&2; exit 64 ;; esac
shift 2
le_init test --project "$src_project"

dsn_path() { sed -E 's#^[A-Za-z0-9+-]+://[^/]*/?([^?]*).*#\1#'; }
dsn_prefix() { sed -n 's/.*[?&]prefix=\([^&]*\).*/\1/p'; }
MISMATCH=()
expect_eq() { [ "$3" = "$4" ] || MISMATCH+=("$1 $2 is '$3', expected '$4'"); }
expect_pre() { case $3 in "$4"*) ;; *) MISMATCH+=("$1 $2 is '$3', expected prefix '$4'") ;; esac; }

# Env flags and ORO_ENV/APP_ENV must stay inside the target's own kernel envs.
env_allowed() { if [ "$TARGET" = local-test ]; then [[ $1 == test || $1 == behat_test ]]; else [[ $1 != test && $1 != behat_test ]]; fi; }
check_env_overrides() {
    local prev="" v a
    for a in "$@"; do
        v=""
        case $a in --env=*) v=${a#--env=} ;; -e=*) v=${a#-e=} ;; -e?*) v=${a#-e} ;; esac
        [ -z "$v" ] && case $prev in --env|-e) v=$a ;; esac
        [ -n "$v" ] && ! env_allowed "$v" && MISMATCH+=("env flag '$v' is outside the $TARGET kernel envs")
        prev=$a
    done
    for v in "${ORO_ENV:-}" "${APP_ENV:-}"; do
        [ -n "$v" ] && ! env_allowed "$v" && MISMATCH+=("environment ORO_ENV/APP_ENV='$v' is outside the $TARGET kernel envs")
    done
}
check_env_overrides "$@"
if [ ${#MISMATCH[@]} -gt 0 ]; then
    say "guard: $TARGET refuses env overrides; nothing was run"; printf '  %s\n' "${MISMATCH[@]:0:5}"; exit 3
fi

# Boots the env's real kernel and compares what it resolves to with env.yml. web=1 adds MQ and sessions.
LIVE=""
live_get() { sed -n "s/^$1=//p" <<< "$LIVE" | head -1; }
verify_env() { # env expected_db web
    local e=$1 want_db=$2 web=$3 v
    LIVE=$(cd "$PROJECT" && ORO_ENV=$e ORO_DEBUG=0 php "$LE_LIB/live-target.php" "$PROJECT" "$e" 2>>"$LOG")
    [ -n "$LIVE" ] || { MISMATCH+=("$e kernel did not boot (see $LOG)"); return; }
    expect_eq "$e" "live current_database()" "$(live_get current_database)" "$want_db"
    expect_eq "$e" database_dsn "$(live_get database_dsn | dsn_path)" "$want_db"
    if [ "$TARGET" = local-test ]; then
        for v in search_engine_dsn website_search_engine_dsn; do expect_pre "$e" "$v" "$(live_get $v | dsn_prefix)" "$ES_PREFIX"; done
        expect_eq "$e" gaufrette.public "$(live_get gaufrette_adapter.public | sed "s/^gridfs://" | dsn_path)" "$MONGO_PUB"
        expect_eq "$e" gaufrette.private "$(live_get gaufrette_adapter.private | sed "s/^gridfs://" | dsn_path)" "$MONGO_PRIV"
        if [ "$web" = 1 ]; then
            expect_eq "$e" message_queue_transport_dsn "$(live_get message_queue_transport_dsn | dsn_path)" "$MQ_VHOST"
            expect_eq "$e" session_handler_dsn "$(live_get session_handler_dsn | dsn_path)" "$SESSION_DB"
        fi
    else
        case $(live_get gaufrette_adapter.private | sed "s/^gridfs://" | dsn_path) in oro_test*) MISMATCH+=("$e gaufrette private points at a test db") ;; esac
        case $(live_get search_engine_dsn | dsn_prefix) in "$ES_PREFIX"*) MISMATCH+=("$e search prefix is a test prefix") ;; esac
    fi
}

T0=$EPOCHREALTIME
if [ "$TARGET" = local-test ]; then
    verify_env test "$TEST_DB" 0; verify_env behat_test "$TEST_DB" 1
    desc="db=$TEST_DB es=$ES_PREFIX* mq=$MQ_VHOST mongo=$MONGO_PUB,$MONGO_PRIV session=$SESSION_DB"
else
    verify_env prod "$LOCAL_DB" 1
    desc="db=$LOCAL_DB"
fi
if [ ${#MISMATCH[@]} -gt 0 ]; then
    say "guard: $TARGET does not resolve to its configured stack; nothing was run"
    printf '  %s\n' "${MISMATCH[@]:0:5}"; printf '  %s\n' "${MISMATCH[@]}" >> "$LOG"
    exit 3
fi
say "test: $TARGET verified ($desc) in $(awk -v a="$T0" -v b="$EPOCHREALTIME" 'BEGIN{printf "%.1fs", b-a}')"
[ "$ACTION" = verify ] && exit 0

cd "$PROJECT" || exit 1
if [ "$TARGET" = local ]; then
    [ "$ACTION" = console ] || { say "guard: tests never run against the local data stack; use local-test"; exit 3; }
    has_env=0; for a in "$@"; do case $a in --env|--env=*) has_env=1 ;; esac; done
    [ $has_env = 1 ] && exec php bin/console "$@" || exec php bin/console "$@" --env=prod
fi
truncate_test_log
case $ACTION in
    console)
        has_env=0; for a in "$@"; do case $a in --env|--env=*) has_env=1 ;; esac; done
        [ $has_env = 1 ] && exec php bin/console "$@" || exec php bin/console "$@" --env=behat_test ;;
    phpunit)
        bin=bin/phpunit; [ -x "$bin" ] || bin=vendor/bin/phpunit
        ORO_ENV=test php "$bin" "$@" >> "$LOG" 2>&1; rc=$?
        grep -E '^(OK \(|Tests:|FAILURES!|ERRORS!|WARNINGS!|No tests executed)' "$LOG" | tail -4 ;;
    e2e)
        php bin/console aaxis:test:e2e --env=behat_test "$@" >> "$LOG" 2>&1; rc=$?
        grep -E '^\s*[0-9]+ (passed|failed|flaky|skipped|did not run)|scenarios? (passed|failed)' "$LOG" | tail -6
        res=$(ls -dt var/e2e-results/*/ 2>/dev/null | head -1); [ -n "$res" ] && echo "results: ${res%/}" ;;
esac
echo "exit=$rc log=$LOG"
exit "$rc"
