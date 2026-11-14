# oro: ">=7.0.0"
# Test-stack primitives shared by reset.sh, baseline.sh and the drop scripts. Requires common.sh + le_init.

pg_exists() { le_ident "$1"; [ "$(pg -c "select 1 from pg_database where datname='$1'")" = 1 ]; }

pg_clone() { # template target
    le_guard oro_test "$1"; le_guard oro_test "$2"
    mut "pg clone $1 -> $2" pg -c "DROP DATABASE IF EXISTS \"$2\" WITH (FORCE)" -c "CREATE DATABASE \"$2\" TEMPLATE \"$1\""
}

pg_drop() {
    le_guard oro_test "$1"
    [ "$1" != "$LOCAL_DB" ] || guard_abort "refusing '$1': it is the local data db"
    mut "pg drop $1" pg -c "DROP DATABASE IF EXISTS \"$1\" WITH (FORCE)"
}

mongo_list() { dx mongodb mongosh --quiet --eval 'db.adminCommand({listDatabases:1,nameOnly:true}).databases.forEach(d=>print(d.name))'; }

mongo_copy() { # src dst: dump|restore with namespace remap
    le_guard oro_test_ "$1"; le_guard oro_test_ "$2"
    mut "mongo copy $1 -> $2" dx mongodb sh -c "mongodump --quiet --archive --db $1 | mongorestore --quiet --archive --nsFrom '$1.*' --nsTo '$2.*' --drop"
}

mongo_drop() {
    le_guard oro_test_ "$1"
    mut "mongo drop $1" dx mongodb mongosh --quiet --eval "db.getSiblingDB('$1').dropDatabase()"
}

# Deletes every index named under the prefix, one DELETE per name (ES refuses wildcard deletes). Sets ES_DROPPED.
es_drop_prefix() {
    local prefix=$1 names n
    le_ident "$prefix"
    case $prefix in "$ES_PREFIX"*) ;; *) guard_abort "refusing prefix '$prefix': outside configured es_prefix '$ES_PREFIX'" ;; esac
    names=$(es "/_cat/indices/${prefix}*?h=index") || fail "elasticsearch unreachable"
    ES_DROPPED=0
    [ -n "$names" ] || return 0
    for n in $names; do case $n in "$ES_PREFIX"*) ;; *) guard_abort "refusing index '$n': outside es_prefix '$ES_PREFIX'" ;; esac; done
    for n in $names; do
        if [ "$DRY" = 1 ]; then say "would: es delete $n"; else logv "es delete $n"; es "/$n" -XDELETE >> "$LOG" 2>&1; fi
        ES_DROPPED=$((ES_DROPPED + 1))
    done
}

vhost_exists() { dx rabbitmq rabbitmqctl list_vhosts -q 2>/dev/null | grep -qx "$1"; }

# User the test stack connects to RabbitMQ as, or empty. Read from the test stack dotenv ORO_MQ_DSN, never the dev
# one; a ${VAR} placeholder resolves from the same file, then from the dev dotenv (the value render.sh bakes in).
mq_test_user() {
    local f dsn user name val
    for f in .env-app.test.local .env-app.behat_test.local; do
        [ -f "$PROJECT/$f" ] || continue
        dsn=$(grep -E '^ORO_MQ_DSN=' "$PROJECT/$f" | tail -1 | cut -d= -f2- | tr -d "'\"")
        [ -n "$dsn" ] || continue
        user=$(sed -nE 's#^amqps?://([^:@/]+).*#\1#p' <<< "$dsn")
        if [[ $user =~ ^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$ ]]; then
            name=${BASH_REMATCH[1]}; val=$(grep -E "^$name=" "$PROJECT/$f" | tail -1 | cut -d= -f2- | tr -d "'\"")
            [ -n "$val" ] || val=$(mq_dev_dotenv "$name")
            user=$val
        fi
        [ -n "$user" ] && [[ $user != *'$'* ]] && { echo "$user"; return 0; }
    done
    user=$(mq_dev_dotenv RABBITMQ_DEFAULT_USER); [[ $user != *'$'* ]] && echo "$user"
    return 0
}
mq_dev_dotenv() { local f; for f in .env-app.local .env-app; do [ -f "$PROJECT/$f" ] && grep -E "^$1=" "$PROJECT/$f" | tail -1 | cut -d= -f2- | tr -d "'\"" | grep . && return 0; done; return 0; }

mq_user_exists() { dx rabbitmq rabbitmqctl list_users -q 2>/dev/null | cut -f1 | grep -qx "$1"; }

# True when the user holds configure/write/read ".*" on the vhost.
mq_user_has_access() { dx rabbitmq rabbitmqctl list_permissions -p "$1" -q 2>/dev/null | awk -F'\t' -v u="$2" '$1==u && $2==".*" && $3==".*" && $4==".*" {f=1} END{exit !f}'; }

# Runs a RabbitMQ mutation; on failure reports the step with rabbitmqctl's own output. Exits 1.
mq_step() {
    local step=$1 out; shift
    if [ "$DRY" = 1 ]; then say "would: $step"; return 0; fi
    logv "+ $step"
    out=$("$@" 2>&1) || { say "FAIL $step: $(tr '\n' ' ' <<< "$out")"; exit 1; }
}

# Idempotent: creates the test vhost when missing and always (re)grants the test stack user on it, so a vhost left
# without permissions by an interrupted run heals. No-op when env.yml configures no local_test vhost.
mq_ensure_vhost() {
    [ -n "${MQ_VHOST:-}" ] || return 0
    le_guard oro_test "$MQ_VHOST"
    local user created=0; user=$(mq_test_user)
    [ -n "$user" ] || fail "vhost user: no RabbitMQ user resolvable from ORO_MQ_DSN in .env-app.test.local (or RABBITMQ_DEFAULT_USER); run render.sh"
    mq_user_exists "$user" || fail "vhost user: RabbitMQ user '$user' does not exist (rabbitmqctl add_user, or fix ORO_MQ_DSN in .env-app.test.local)"
    vhost_exists "$MQ_VHOST" || { mq_step "vhost create $MQ_VHOST" dx rabbitmq rabbitmqctl add_vhost "$MQ_VHOST"; created=1; }
    mq_step "vhost permissions $user on $MQ_VHOST" dx rabbitmq rabbitmqctl set_permissions -p "$MQ_VHOST" "$user" '.*' '.*' '.*'
    if [ "$created" = 1 ]; then say "vhost: created $MQ_VHOST for $user"; else say "vhost: $MQ_VHOST present, $user permissions ensured"; fi
}

mq_purge() {
    le_guard oro_test "$MQ_VHOST"
    local q rc=0
    for q in $(dx rabbitmq rabbitmqctl list_queues -p "$MQ_VHOST" name -q 2>/dev/null | grep -vx name); do
        mut "mq purge $MQ_VHOST/$q" dx rabbitmq rabbitmqctl purge_queue -p "$MQ_VHOST" "$q" || rc=1
    done
    return $rc
}

# Flushes only the test session db; db 0 holds the local stack's sessions.
redis_flush_session() {
    [[ $SESSION_DB =~ ^[0-9]+$ ]] && [ "$SESSION_DB" -ge 1 ] || guard_abort "refusing redis db '$SESSION_DB': test session db must be >= 1"
    mut "redis flushdb $SESSION_DB" dx redis redis-cli -n "$SESSION_DB" FLUSHDB
}

truncate_test_log() { [ -f "$PROJECT/var/logs/behat_test.log" ] && { [ "$DRY" = 1 ] || : > "$PROJECT/var/logs/behat_test.log"; }; return 0; }
