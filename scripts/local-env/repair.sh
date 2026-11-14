#!/usr/bin/env bash
# oro: ">=7.0.0"
# Repair drift found by check.sh. Items: params (config/parameters.yml is generated, so it is rewritten in place
# without backup: Node paths from env.yml node_pin or .nvmrc via nvm, GridFS adapters; also strips Redis cache
# DSNs from the test stack dotenv files, which are backed up to var/backups/oro-local-env/), vhost (create the
# test RabbitMQ vhost if missing, and always grant the test stack MQ user on it), hosts (prints the sudo command),
# templates (re-render once render.sh exists).
# Usage: repair.sh [--only params|node|vhost|hosts|templates|media] [--project P] [--dry-run] [--verbose]   (node = params)
# Exit: 0 repaired, 1 failure, 10 sudo steps printed, 64 usage.
source "$(dirname "$0")/lib/common.sh"; source "$LE_LIB/stack.sh"
le_init repair "$@"
ONLY=""
for i in "${!ARGS[@]}"; do [ "${ARGS[$i]}" = "--only" ] && ONLY=${ARGS[$((i + 1))]:-}; done
[ "$ONLY" = node ] && ONLY=params
case $ONLY in ""|params|vhost|hosts|templates|media) ;; *) LE_USAGE="repair.sh [--only params|vhost|hosts|templates|media]"; usage_exit ;; esac
want_item() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
backup() { local dst=$PROJECT/var/backups/oro-local-env; mut "backup $1" bash -c 'mkdir -p "$1" && cp -p "$2" "$1/$(basename "$2").$(date +%Y%m%d-%H%M%S)"' _ "$dst" "$1"; }

if want_item params; then
    want=$(nvm_version)
    if [ -z "$want" ] || [ "$want" = "N/A" ]; then
        pin=${NODE_PIN:-$(tr -d ' \n' < "$PROJECT/.nvmrc" 2>/dev/null)}
        mut "nvm install $pin" bash -c 'export NVM_DIR=${NVM_DIR:-$HOME/.nvm}; . "$NVM_DIR/nvm.sh" && nvm install "$1"' _ "$pin" || fail "nvm install"
        want=$(nvm_version)
    fi
    if [ "$DRY" = 1 ] && { [ -z "$want" ] || [ "$want" = "N/A" ]; }; then say "params: would install the pinned Node version then rewrite parameters.yml"
    else
        [ -n "$want" ] && [ "$want" != "N/A" ] || fail "params: node version did not resolve"
        bindir=${NVM_DIR:-$HOME/.nvm}/versions/node/$want/bin
        mut "set node paths -> $bindir" python3 "$LE_LIB/nodephp.py" set-node "$PROJECT/config/parameters.yml" "$bindir" || fail "parameters.yml rewrite"
        for k in public private; do
            mut "gaufrette_adapter.$k" python3 "$LE_LIB/nodephp.py" set-param "$PROJECT/config/parameters.yml" "gaufrette_adapter.$k" "'gridfs:%env(ORO_MONGODB_DSN_${k^^})%'" || fail "parameters.yml rewrite"
        done
        [ "$DRY" = 1 ] || say "params: parameters.yml node paths -> $want, GridFS adapters set"
    fi
    for f in .env-app.test.local .env-app.behat_test.local; do
        if grep -qE '^ORO_REDIS_(CACHE|DOCTRINE|LAYOUT)_DSN=' "$PROJECT/$f" 2>/dev/null; then
            backup "$PROJECT/$f"
            mut "strip redis cache dsns from $f" sed -i -E '/^ORO_REDIS_(CACHE|DOCTRINE|LAYOUT)_DSN=/d' "$PROJECT/$f" || fail "strip $f"
            [ "$DRY" = 1 ] || say "params: removed Redis cache DSNs from $f"
        fi
    done
fi
if want_item media; then
    # Moved, never deleted: the files were written by an older dump and may be the only copy of what nginx served.
    dst=$PROJECT/.oro-ai/local-env/moved-aside/$(date +%Y%m%d-%H%M%S); n=0
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        rel=${f#"$PROJECT"/}
        mut "move aside $rel" bash -c 'mkdir -p "$(dirname "$2/$3")" && mv "$1" "$2/$3"' _ "$f" "$dst" "$rel" || fail "move $rel"
        n=$((n + 1))
    done < <(media_shadow_files; sitemap_shadow_files)
    [ "$n" -gt 0 ] && say "media: moved $n shadowing file(s) to ${dst#"$PROJECT"/}"
fi
want_item vhost && mq_ensure_vhost
if want_item hosts; then
    for d in "$LOCAL_DOMAIN" "$TEST_DOMAIN"; do
        [ -n "$d" ] && ! grep -Eq "(^|[[:space:]])$d([[:space:]]|\$)" /etc/hosts && sudo_needed "echo '127.0.0.1 $d' | sudo tee -a /etc/hosts"
    done
fi
if want_item templates && [ -x "$LE_DIR/render.sh" ]; then
    mut "re-render managed files" "$LE_DIR/render.sh" --project "$PROJECT" || fail "render"
    say "templates: re-rendered"
fi
say "repair: done"
finish 0
