#!/usr/bin/env bash
# oro: ">=7.0.0"
# Read-only drift check of the local and local-test environment against env.yml, .nvmrc and composer.json.
# Prints drifted items only (--verbose: every item), then one summary line.
# Usage: check.sh [--json] [--verbose] [--project P]
# Exit: 0 clean, 1 env.yml invalid, 2 drift (items listed), 3 guard-invalid env.yml.
source "$(dirname "$0")/lib/common.sh"
le_init check "$@"
RES=$(mktemp); trap 'rm -f "$RES"' EXIT
item() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$RES"; }   # status item detail
ok() { item ok "$1" "${2:-}"; }
bad() { item drift "$1" "$2"; }

# node
if [ -f "$PROJECT/.nvmrc" ] || [ -n "$NODE_PIN" ]; then
    want=$(nvm_version); [ -n "$want" ] || want="N/A"
    if [ "$want" = "N/A" ]; then bad node ".nvmrc $(cat "$PROJECT/.nvmrc") not installed in nvm"
    else
        shellv=$(node -v 2>/dev/null)
        mapfile -t paths < <(python3 "$LE_LIB/nodephp.py" node-paths "$PROJECT/config/parameters.yml" 2>/dev/null)
        wrong=""
        for p in "${paths[@]:-}"; do case $p in *"/$want/bin/"*) ;; *) wrong=1 ;; esac; done
        if [ -n "$wrong" ] || [ ${#paths[@]} -ne 3 ] || [ -z "${paths[0]}" ] || [ -z "${paths[1]}" ] || [ -z "${paths[2]}" ]; then bad node "parameters.yml oro_asset node/npm/pnpm paths are not all under $want (repair.sh --only node)"
        elif [ "$shellv" != "$want" ]; then bad node "shell node is ${shellv:-missing}, .nvmrc resolves to $want"
        else ok node "$want"; fi
    fi
else bad node ".nvmrc missing"; fi

# parameters.yml is generated: GridFS adapters per topology, and no Redis app-cache DSNs in the test stack's dotenv
for k in public private; do
    got=$(python3 "$LE_LIB/nodephp.py" get-param "$PROJECT/config/parameters.yml" "gaufrette_adapter.$k" 2>/dev/null)
    if [ "$got" = "gridfs:%env(ORO_MONGODB_DSN_${k^^})%" ]; then ok "gaufrette-$k"; else bad "gaufrette-$k" "parameters.yml gaufrette_adapter.$k is '${got:-unset}', expected the GridFS adapter (repair.sh --only params)"; fi
done
redis=$(grep -lE '^ORO_REDIS_(CACHE|DOCTRINE|LAYOUT)_DSN=' "$PROJECT"/.env-app.test.local "$PROJECT"/.env-app.behat_test.local 2>/dev/null | xargs -r -n1 basename | tr '\n' ' ')
if [ -n "$redis" ]; then bad redis-cache "Redis cache DSNs set in ${redis% }; caches stay on disk (repair.sh --only params)"; else ok redis-cache; fi

# php
req=$(python3 "$LE_LIB/nodephp.py" php-require "$PROJECT" 2>/dev/null); phpv=$(php -r 'echo PHP_VERSION;' 2>/dev/null)
if [ -z "$req" ] || [ -z "$phpv" ]; then bad php "cannot read composer require.php or php version"
elif ! python3 "$LE_LIB/nodephp.py" php-ok "$req" "$phpv"; then bad php "php $phpv does not satisfy composer require.php $req"
else
    pin=$(grep -E '^PHP_VERSION=' "$PROJECT/.env-app.local" 2>/dev/null | cut -d= -f2)
    if [ -n "$pin" ] && ! python3 "$LE_LIB/nodephp.py" php-ok "$req" "$pin.0"; then bad php ".env-app.local PHP_VERSION=$pin does not satisfy $req"; else ok php "$phpv"; fi
fi

# services
if docker inspect "$(cname mongodb)" >/dev/null 2>&1; then
    if docker port "$(cname mongodb)" 27017/tcp 2>/dev/null | grep -q ":$MONGO_PORT\$"; then ok mongo-port "$MONGO_PORT"; else bad mongo-port "mongodb is not published on fixed host port $MONGO_PORT"; fi
    if docker inspect -f '{{join .Config.Cmd " "}}' "$(cname mongodb)" 2>/dev/null | grep -Eq -- "--wiredTigerCacheSizeGB[ =]$MONGO_CACHE"; then ok mongo-cache "$MONGO_CACHE"; else bad mongo-cache "mongod lacks --wiredTigerCacheSizeGB $MONGO_CACHE"; fi
else bad mongo-port "mongodb container $(cname mongodb) not running"; fi
if pgrep -x nginx >/dev/null && pgrep -f php-fpm >/dev/null; then ok web "nginx+fpm running"; else bad web "nginx or php-fpm not running"; fi
for d in "$LOCAL_DOMAIN" "$TEST_DOMAIN"; do
    [ -n "$d" ] || { bad hosts "domain not set in env.yml (setup asks)"; continue; }
    if grep -Eq "(^|[[:space:]])$d([[:space:]]|\$)" /etc/hosts; then ok hosts "$d"; else bad hosts "$d missing from /etc/hosts (sudo)"; fi
done

# test stack data
for db in "$TEST_DB" "$TEST_BASE"; do
    if pg_out=$(pg -c "select 1 from pg_database where datname='$db'" 2>/dev/null) && [ "$pg_out" = 1 ]; then ok "pg-$db"; else bad "pg-$db" "database $db missing"; fi
done
if dx rabbitmq rabbitmqctl list_vhosts -q 2>/dev/null | grep -qx "$MQ_VHOST"; then ok mq-vhost "$MQ_VHOST"; else bad mq-vhost "vhost $MQ_VHOST missing"; fi
if dx mongodb mongosh --quiet --eval 'db.adminCommand({listDatabases:1,nameOnly:true}).databases.forEach(d=>print(d.name))' 2>/dev/null | grep -qx "$MONGO_BASE"; then ok mongo-baseline "$MONGO_BASE"; else bad mongo-baseline "mongo db $MONGO_BASE missing"; fi
[ "$(dx redis redis-cli -n "$SESSION_DB" ping 2>/dev/null)" = PONG ] && ok redis "db $SESSION_DB" || bad redis "redis db $SESSION_DB unreachable"
key=$("$LE_LIB/baseline-key.sh" "$PROJECT" 2>/dev/null)
if [ -z "$BASELINE_KEY" ]; then bad baseline-key "no baseline built yet (baseline.sh)"
elif [ "$key" != "$BASELINE_KEY" ]; then bad baseline-key "stale: composer.lock/migrations/fixtures changed (baseline.sh)"
else ok baseline-key "${key:0:12}"; fi

# managed files (templates arrive with the setup work)
if [ -x "$LE_DIR/render.sh" ]; then
    while IFS= read -r line; do bad template "$line"; done < <("$LE_DIR/render.sh" --check --project "$PROJECT" 2>&1 | grep -v '^$')
fi

drift=$(grep -c '^drift' "$RES"); total=$(wc -l < "$RES")
if [ "$JSON" = 1 ]; then
    python3 - "$RES" <<'P'
import json, sys
rows = [dict(zip(("status", "item", "detail"), l.rstrip("\n").split("\t"))) for l in open(sys.argv[1])]
print(json.dumps({"drift": sum(r["status"] == "drift" for r in rows), "items": rows}))
P
else
    awk -F'\t' -v v="$VERBOSE" '$1=="drift"{printf "DRIFT %s: %s\n",$2,$3} $1=="ok"&&v==1{printf "ok    %s %s\n",$2,$3}' "$RES"
    echo "check: $((total - drift)) ok, $drift drift"
fi
cp "$RES" "$LOG"
[ "$drift" = 0 ] || exit 2
