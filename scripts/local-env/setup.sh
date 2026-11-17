#!/usr/bin/env bash
# oro: ">=6.1.0"
# Set up all gitignored local config for this clone: migrate/create env.yml, ask for the values that are never
# defaulted (domains, certificates, project namespace), size e2e workers, render the managed files, set the Node and
# GridFS keys in parameters.yml, scaffold the POC scratch bundle, and print the sudo steps (SUDO-NEEDED).
# Usage: setup.sh [--set key=value]... [--non-interactive] [--test-only] [--project P] [--dry-run] [--verbose]
# --test-only (persisted as test_only: true in env.yml): manage only the test stack — .env-app.behat_test.local,
# .env-app.test.local and nginx-test. .env-app.local, the compose override and parameters.yml are never touched,
# and only the local_test.* values are asked for. For projects that already have their own dev environment.
# Missing values are prompted on a terminal; otherwise listed as `ask:` lines (exit 64) so the caller can ask the user
# and rerun with --set. Never runs sudo. Idempotent: a second run changes nothing.
# Exit: 0 done, 1 failure, 10 sudo steps printed, 64 values missing.
source "$(dirname "$0")/lib/common.sh"
le_parse "$@"
python3 "$LE_LIB/env.py" migrate --project "$PROJECT" || exit $?
python3 "$LE_LIB/env.py" init --project "$PROJECT" || exit 1
le_init setup "$@"
SETS=() INTERACTIVE=0 TEST_ONLY_FLAG=0; [ -t 0 ] && INTERACTIVE=1
for ((i = 0; i < ${#ARGS[@]}; i++)); do
    case ${ARGS[$i]} in
        --set) SETS+=("${ARGS[$((i + 1))]:-}"); i=$((i + 1)) ;;
        --non-interactive) INTERACTIVE=0 ;;
        --test-only) TEST_ONLY_FLAG=1 ;;
        "") ;;
        *) LE_USAGE="setup.sh [--set key=value]... [--non-interactive] [--test-only]"; usage_exit ;;
    esac
done
if [ "$TEST_ONLY_FLAG" = 1 ] && [ "$TEST_ONLY" != 1 ]; then
    python3 "$LE_LIB/envsh.py" set --project "$PROJECT" test_only true || fail "env.yml write"
    TEST_ONLY=1
fi
ASK_ARGS=(); [ "$TEST_ONLY" = 1 ] && ASK_ARGS=(--test-only)
run() { local out rc; out=$("$@" 2>&1); rc=$?; printf '%s\n' "$out" >> "$LOG"; [ -z "$out" ] || printf '%s\n' "$out"; [ "$rc" -eq 10 ] && SUDO_PENDING=1; return $((rc == 10 ? 0 : rc)); }
if [ "$DRY" = 1 ]; then run "$LE_DIR/render.sh" --dry-run --project "$PROJECT"; exit 0; fi

for kv in "${SETS[@]:-}"; do
    [ -z "$kv" ] || python3 "$LE_LIB/envsh.py" set --project "$PROJECT" "${kv%%=*}" "${kv#*=}" || fail "--set $kv"
done
missing=(); while IFS= read -r m; do missing+=("$m"); done < <(python3 "$LE_LIB/env.py" asks --project "$PROJECT" ${ASK_ARGS[@]+"${ASK_ARGS[@]}"} | grep .)
for key in "${missing[@]:-}"; do
    [ -n "$key" ] && [ "$INTERACTIVE" = 1 ] || continue
    read -r -p "$key: " val && [ -n "$val" ] && python3 "$LE_LIB/envsh.py" set --project "$PROJECT" "$key" "$val"
done
missing=(); while IFS= read -r m; do missing+=("$m"); done < <(python3 "$LE_LIB/env.py" asks --project "$PROJECT" ${ASK_ARGS[@]+"${ASK_ARGS[@]}"} | grep .)
if [ ${#missing[@]} -gt 0 ] && [ -n "${missing[0]}" ]; then
    for key in "${missing[@]}"; do say "ask: $key"; done
    say "setup: ${#missing[@]} value(s) needed; ask the user, then rerun with --set key=value"
    exit 64
fi

run "$LE_DIR/workers.sh" --write --project "$PROJECT" || fail "workers"
run "$LE_DIR/render.sh" --project "$PROJECT" || fail "render"
if [ "$TEST_ONLY" = 1 ]; then say "params: skipped (test-only: parameters.yml is not managed)"
elif [ -f "$PROJECT/config/parameters.yml" ]; then run "$LE_DIR/repair.sh" --only params --project "$PROJECT" || fail "params"
else say "params: config/parameters.yml absent (created by composer install); rerun setup afterwards"; fi
run "$LE_DIR/repair.sh" --only hosts --project "$PROJECT" || fail "hosts"
grep -q "wrote docker-compose.override.yml" "$LOG" && say "NEXT: docker compose up -d mongodb elasticsearch rabbitmq (applies port, memory and image changes)"
say "setup: done"
finish 0
