#!/usr/bin/env bash
# oro: ">=7.0.0"
# Bring derived state (vendor, caches, schema, translations, routes dump, assets) up to date after a branch switch
# or pull, for both stacks, running only the steps the changed inputs need. State: .oro-ai/local-env/refresh.json.
# Usage: refresh.sh [--all] [--project P] [--dry-run]    (--all or no record: every step)
# Console steps go through `aaxis-oro test <target> console` so each one is bound to its own stack (local: prod/dev
# kernel, local-test: test/behat_test); shared steps (composer, assets) touch vendor/ and public/ once. The routes dump runs per stack: Oro writes it through the
# public gaufrette filesystem, which is gridfs (that stack's Mongo) on gridfs projects.
# composer install runs with --no-scripts (Oro's handlers run pnpm install and asset steps that refresh covers, and can
# rewrite tracked files); it adds --no-dev only when vendor/ was installed without dev packages, and one
# --ignore-platform-req per entry of env.yml composer_ignore_platform_reqs. Tracked files modified by a run are reported as WARN. Never sudo, down -v, FLUSHALL, db.sh or reinstall.sh.
# Exit: 0 ok or nothing to do, 1 a step failed (refresh.json untouched), 3 guard abort, 64 usage.
source "$(dirname "$0")/lib/common.sh"
le_init refresh "$@"
ALL=0
for a in "${ARGS[@]:-}"; do case $a in --all) ALL=1 ;; "") ;; *) echo "usage: aaxis-oro dev refresh [--project DIR] [--dry-run] [--all]" >&2; exit 64 ;; esac; done
cd "$PROJECT" || exit 1
dirty() { git status --porcelain --untracked-files=no 2>/dev/null | sort; }
warn_new_dirty() { [ -n "${DIRTY0+x}" ] && comm -13 <(printf '%s\n' "$DIRTY0") <(dirty) | sed 's/^/refresh: WARN tracked file modified: /' | while IFS= read -r l; do say "$l"; done; return 0; }
PLAN=$(python3 "$LE_LIB/refresh.py" plan --project "$PROJECT" $([ $ALL = 1 ] && echo --all)) || fail "plan"
SINCE=$(sed -n 's/^#since //p' <<< "$PLAN"); STEPS=$(grep -v '^#' <<< "$PLAN" | cut -f1)
[ -n "$STEPS" ] || { say "refresh: up to date (since $SINCE)"; exit 0; }

tc() { "$LE_DIR/test.sh" --project "$PROJECT" --no-refresh-check "$@"; }
rmcache() { local e; for e in "$@"; do [ -d "var/cache/$e" ] && rm -rf -- "var/cache/$e"; done; return 0; }
step_composer() {
    local flags=(--no-interaction --no-scripts) r
    grep -q '"dev": false' vendor/composer/installed.json 2>/dev/null && flags+=(--no-dev)
    for r in $(python3 "$LE_LIB/env.py" get --project "$PROJECT" composer_ignore_platform_reqs 2>/dev/null | tr ',' ' '); do flags+=("--ignore-platform-req=$r"); done
    composer install "${flags[@]}"
}
step_cache_local() {
    local dev=0; [ -d var/cache/dev ] && dev=1
    rmcache prod dev; tc local console cache:warmup --env=prod || return
    [ $dev = 1 ] && { tc local console cache:warmup --env=dev || return; }; return 0
}
# The test kernel rebuilds its extend-entity cache from the test DB on first boot, and warmup fails before that DB exists.
step_cache_test() { rmcache test tes_ behat_test; tc local-test console cache:warmup --env=behat_test; }
step_baseline() { echo "baseline stale (composer.lock/migrations changed): run aaxis-oro env baseline before e2e (about 8 minutes)"; }
step_migrate() { tc local console oro:migration:load --force; }
# oro:migration:data:load prints each fixture it applies as "  > <FQCN>"; the loop below lists them.
step_data_load() { tc local console oro:migration:data:load; }
step_entity() { tc local console oro:entity-config:update && tc local console oro:entity-extend:update; }
step_translations() { tc local console oro:translation:load --rebuild-cache && tc local console oro:translation:dump; }
step_routing_local() { tc local console fos:js-routing:dump; }
step_routing_test() { tc local-test console fos:js-routing:dump --env=behat_test; }
step_assets() {
    local sl=(); [ -n "$(find public/bundles -maxdepth 1 -type l -print -quit 2>/dev/null)" ] && sl=(--symlink)
    tc local console oro:assets:install "${sl[@]}"
}

[ "$DRY" = 1 ] || DIRTY0=$(dirty)
say "refresh: $(wc -l <<< "$STEPS") steps since $SINCE"
for s in $STEPS; do
    fn=step_${s//-/_}; [ "$s" = baseline-stale ] && fn=step_baseline
    if [ "$DRY" = 1 ]; then say "refresh: would run $s ($(grep -P "^$s\t" <<< "$PLAN" | cut -f2))"; continue; fi
    t0=$EPOCHREALTIME
    out=$(mktemp)
    if "$fn" > "$out" 2>&1; then r=ok; else r=FAIL; fi
    cat "$out" >> "$LOG"
    say "$(awk -v a="$t0" -v b="$EPOCHREALTIME" -v s="$s" -v r="$r" 'BEGIN{printf "refresh: %-14s %-4s %5.1fs", s, r, b-a}')"
    if [ $r = ok ] && [ "$s" = data-load ]; then
        fx=$(sed -nE 's/^ *> *(loading |Loading )?([A-Za-z_][A-Za-z0-9_]*(\\[A-Za-z0-9_]+)+).*/\2/p' "$out" | sed 's/.*\\//' | paste -sd, -)
        say "refresh: data fixtures loaded: ${fx:-none}"
    fi
    rm -f "$out"
    [ $r = ok ] || { warn_new_dirty; say "refresh: stopped; log: $LOG"; exit 1; }
    case $s in routing-*|translations) [ -n "$(media_shadow_files)" ] && say "refresh: WARN stale public/media/js files shadow the gridfs dump; run: aaxis-oro env repair --only media" ;; esac
done
warn_new_dirty
[ "$DRY" = 1 ] || python3 "$LE_LIB/refresh.py" record --project "$PROJECT"
