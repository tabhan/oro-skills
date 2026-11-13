#!/usr/bin/env bash
# oro: ">=7.0.0"
# Render the gitignored local config (docker-compose.override.yml, .env-app.local merge, .env-app.behat_test.local,
# .env-app.test.local, nginx server block and optional supervisor program staged under .oro-ai/local-env/rendered/)
# from env/templates and env.yml. Replaced files are backed up to var/backups/oro-local-env/.
# Usage: render.sh [--check|--diff|--dry-run] [--project P] [--verbose]
# --check lists drift only (used by check.sh); --diff/--dry-run change nothing.
# Exit: 0 clean or applied, 1 error (unset value named), 2 drift (--check), 10 sudo steps printed, 64 usage.
source "$(dirname "$0")/lib/common.sh"
le_init render "$@"
mode=write
for a in "${ARGS[@]:-}"; do
    case $a in
        --check) mode=check ;;
        --diff) mode=diff ;;
        "") ;;
        *) LE_USAGE="render.sh [--check|--diff|--dry-run]"; usage_exit ;;
    esac
done
[ "$DRY" = 1 ] && [ "$mode" = write ] && mode=check
if [ "$mode" != write ]; then
    out=$(python3 "$LE_LIB/render.py" "$mode" --project "$PROJECT" 2>&1); rc=$?
    printf '%s\n' "$out" >> "$LOG"
    [ -z "$out" ] || { [ "$DRY" = 1 ] && printf '%s\n' "$out" | sed 's/^/would: /' || printf '%s\n' "$out"; }
    [ "$mode" = diff ] && exit "$rc"
    [ "$rc" -ne 1 ] || exit 1
    exit "$rc"
fi
out=$(python3 "$LE_LIB/render.py" write --project "$PROJECT" 2>&1) || { printf '%s\n' "$out" | head -5; printf '%s\n' "$out" >> "$LOG"; exit 1; }
printf '%s\n' "$out" >> "$LOG"
while IFS= read -r line; do
    case $line in
        SUDO-NEEDED:*) sudo_needed "${line#SUDO-NEEDED: }" ;;
        *) say "$line" ;;
    esac
done <<< "$out"
finish 0
