#!/usr/bin/env bash
# oro: ">=7.0.0"
# Bring derived state (vendor, caches, schema, translations, routes dump, assets) up to date after a branch switch
# or pull, for both stacks, running only the steps the changed inputs need. State: .oro-ai/local-env/refresh.json.
# Usage: refresh.sh [--all] [--project P] [--dry-run]    (--all or no record: every step)
# Console steps go through `aaxis-oro test <target> console` so each one is bound to its own stack (local: prod/dev
# kernel, local-test: test/behat_test); shared steps (composer, routes dump, assets) touch public/ and vendor/ once.
# composer install keeps scripts enabled (they install assets and clear caches) and adds --no-dev only when vendor/
# was installed without dev packages. Never sudo, down -v, FLUSHALL, db.sh or reinstall.sh.
# Exit: 0 ok or nothing to do, 1 a step failed (refresh.json untouched), 3 guard abort, 64 usage.
source "$(dirname "$0")/lib/common.sh"
le_init refresh "$@"
ALL=0
for a in "${ARGS[@]:-}"; do case $a in --all) ALL=1 ;; "") ;; *) echo "usage: aaxis-oro dev refresh [--project DIR] [--dry-run] [--all]" >&2; exit 64 ;; esac; done
cd "$PROJECT" || exit 1
PLAN=$(python3 "$LE_LIB/refresh.py" plan --project "$PROJECT" $([ $ALL = 1 ] && echo --all)) || fail "plan"
SINCE=$(sed -n 's/^#since //p' <<< "$PLAN"); STEPS=$(grep -v '^#' <<< "$PLAN" | cut -f1)
[ -n "$STEPS" ] || { say "refresh: up to date (since $SINCE)"; exit 0; }

tc() { "$LE_DIR/test.sh" --project "$PROJECT" --no-refresh-check "$@"; }
rmcache() { local e; for e in "$@"; do [ -d "var/cache/$e" ] && rm -rf -- "var/cache/$e"; done; return 0; }
step_composer() {
    local flags=(--no-interaction)
    grep -q '"dev": false' vendor/composer/installed.json 2>/dev/null && flags+=(--no-dev)
    composer install "${flags[@]}"
}
step_cache_local() {
    local dev=0; [ -d var/cache/dev ] && dev=1
    rmcache prod dev; tc local console cache:warmup --env=prod || return
    [ $dev = 1 ] && { tc local console cache:warmup --env=dev || return; }; return 0
}
step_cache_test() { rmcache test tes_ behat_test; tc local-test console cache:warmup --env=test && tc local-test console cache:warmup --env=behat_test; }
step_baseline() { echo "baseline stale (composer.lock/migrations changed): run aaxis-oro env baseline before e2e (about 8 minutes)"; }
step_migrate() { tc local console oro:migration:load --force; }
step_entity() { tc local console oro:entity-config:update && tc local console oro:entity-extend:update; }
step_translations() { tc local console oro:translation:load --rebuild-cache && tc local console oro:translation:dump; }
step_routing() { tc local console fos:js-routing:dump; }
step_assets() {
    local sl=(); [ -n "$(find public/bundles -maxdepth 1 -type l -print -quit 2>/dev/null)" ] && sl=(--symlink)
    tc local console oro:assets:install "${sl[@]}"
}

say "refresh: $(wc -l <<< "$STEPS") steps since $SINCE"
for s in $STEPS; do
    fn=step_${s//-/_}; [ "$s" = baseline-stale ] && fn=step_baseline
    if [ "$DRY" = 1 ]; then say "refresh: would run $s ($(grep -P "^$s\t" <<< "$PLAN" | cut -f2))"; continue; fi
    t0=$EPOCHREALTIME
    if "$fn" >> "$LOG" 2>&1; then r=ok; else r=FAIL; fi
    say "$(awk -v a="$t0" -v b="$EPOCHREALTIME" -v s="$s" -v r="$r" 'BEGIN{printf "refresh: %-14s %-4s %5.1fs", s, r, b-a}')"
    [ $r = ok ] || { say "refresh: stopped; log: $LOG"; exit 1; }
done
[ "$DRY" = 1 ] || python3 "$LE_LIB/refresh.py" record --project "$PROJECT"
