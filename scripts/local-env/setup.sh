#!/usr/bin/env bash
# oro: ">=7.0.0"
# Set up all gitignored local config for this clone: migrate/create env.yml, ask for the values that are never
# defaulted (domains, certificates, project namespace), size e2e workers, render the managed files, set the Node and
# GridFS keys in parameters.yml, scaffold the POC scratch bundle, and print the sudo steps (SUDO-NEEDED).
# Usage: setup.sh [--set key=value]... [--non-interactive] [--project P] [--dry-run] [--verbose]
# Missing values are prompted on a terminal; otherwise listed as `ask:` lines (exit 64) so the caller can ask the user
# and rerun with --set. Never runs sudo. Idempotent: a second run changes nothing.
# Exit: 0 done, 1 failure, 10 sudo steps printed, 64 values missing.
source "$(dirname "$0")/lib/common.sh"
le_parse "$@"
python3 "$LE_LIB/env.py" migrate --project "$PROJECT" || exit $?
python3 "$LE_LIB/env.py" init --project "$PROJECT" || exit 1
le_init setup "$@"
SETS=() INTERACTIVE=0; [ -t 0 ] && INTERACTIVE=1
for ((i = 0; i < ${#ARGS[@]}; i++)); do
    case ${ARGS[$i]} in
        --set) SETS+=("${ARGS[$((i + 1))]:-}"); i=$((i + 1)) ;;
        --non-interactive) INTERACTIVE=0 ;;
        "") ;;
        *) LE_USAGE="setup.sh [--set key=value]... [--non-interactive]"; usage_exit ;;
    esac
done
run() { local out rc; out=$("$@" 2>&1); rc=$?; printf '%s\n' "$out" >> "$LOG"; [ -z "$out" ] || printf '%s\n' "$out"; [ "$rc" -eq 10 ] && SUDO_PENDING=1; return $((rc == 10 ? 0 : rc)); }
if [ "$DRY" = 1 ]; then run "$LE_DIR/render.sh" --dry-run --project "$PROJECT"; exit 0; fi

for kv in "${SETS[@]:-}"; do
    [ -z "$kv" ] || python3 "$LE_LIB/envsh.py" set --project "$PROJECT" "${kv%%=*}" "${kv#*=}" || fail "--set $kv"
done
mapfile -t missing < <(python3 "$LE_LIB/env.py" asks --project "$PROJECT" | grep .)
for key in "${missing[@]:-}"; do
    [ -n "$key" ] && [ "$INTERACTIVE" = 1 ] || continue
    read -r -p "$key: " val && [ -n "$val" ] && python3 "$LE_LIB/envsh.py" set --project "$PROJECT" "$key" "$val"
done
mapfile -t missing < <(python3 "$LE_LIB/env.py" asks --project "$PROJECT" | grep .)
if [ ${#missing[@]} -gt 0 ] && [ -n "${missing[0]}" ]; then
    for key in "${missing[@]}"; do say "ask: $key"; done
    say "setup: ${#missing[@]} value(s) needed; ask the user, then rerun with --set key=value"
    exit 64
fi

run "$LE_DIR/workers.sh" --write --project "$PROJECT" || fail "workers"
run "$LE_DIR/render.sh" --project "$PROJECT" || fail "render"
if [ -f "$PROJECT/config/parameters.yml" ]; then run "$LE_DIR/repair.sh" --only params --project "$PROJECT" || fail "params"
else say "params: config/parameters.yml absent (created by composer install); rerun setup afterwards"; fi
run "$LE_DIR/repair.sh" --only hosts --project "$PROJECT" || fail "hosts"
grep -q "wrote docker-compose.override.yml" "$LOG" && say "NEXT: docker compose up -d mongodb elasticsearch rabbitmq (applies port, memory and image changes)"
say "setup: done"
finish 0
