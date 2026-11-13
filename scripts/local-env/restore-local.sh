#!/usr/bin/env bash
# oro: ">=7.0.0"
# Replace the LOCAL data db (local.db, never oro_test*) with the qa dump, clear the prod cache, then import
# attachments. Destructive for local data, so it needs --yes.
# Usage: restore-local.sh --yes [--dump <file-or-url>] [--attachments <file-or-url>] [--skip-attachments] [--project P] [--dry-run]
# Exit: 0 ok, 1 failure, 3 guard abort, 64 usage or --yes missing. Download options via LE_CURL_OPTS.
source "$(dirname "$0")/lib/common.sh"
le_init restore-local "$@"
YES=0; DUMP=$QA_DUMP; ATT=$QA_ATT; SKIPATT=0
for i in "${!ARGS[@]}"; do
    case ${ARGS[$i]} in
        --yes) YES=1 ;; --skip-attachments) SKIPATT=1 ;;
        --dump) DUMP=${ARGS[$((i + 1))]:-} ;; --attachments) ATT=${ARGS[$((i + 1))]:-} ;;
    esac
done
le_ident "$LOCAL_DB"
case $LOCAL_DB in oro_test*) guard_abort "refusing to restore into '$LOCAL_DB': it is a test name" ;; esac
[ -n "$DUMP" ] || fail "no dump: set qa_server.db_dump or pass --dump"
if [ "$YES" = 0 ] && [ "$DRY" = 0 ]; then echo "restore-local: would replace DB '$LOCAL_DB' with $DUMP; rerun with --yes" >&2; exit 64; fi
fetch() { # src -> local file path in $2
    case $1 in http*) curl -fsSL ${LE_CURL_OPTS:-} -o "$2" "$1" ;; *) cp "$1" "$2" ;; esac
}
work=$PROJECT/var/oro-local-env-restore
mut "prepare $work" mkdir -p "$work"
[ "$DRY" = 1 ] || trap 'rm -rf -- "$work"' EXIT
mut "fetch $DUMP" fetch "$DUMP" "$work/oro.sql.tgz" || fail "download dump"
mut "extract dump" tar -xzf "$work/oro.sql.tgz" -C "$work" || fail "extract dump"
sql=$work/oro.sql
[ "$DRY" = 1 ] || [ -f "$sql" ] || fail "oro.sql not found in the dump"
lap fetch
mut "recreate $LOCAL_DB" pg -c "DROP DATABASE IF EXISTS \"$LOCAL_DB\" WITH (FORCE)" -c "CREATE DATABASE \"$LOCAL_DB\"" || fail "recreate $LOCAL_DB"
mut "copy dump into container" docker cp "$sql" "$(cname pgsql):/tmp/oro.sql" || fail "docker cp"
mut "load dump" dx pgsql psql -U postgres -d "$LOCAL_DB" -q -f /tmp/oro.sql || fail "load dump"
mut "remove dump from container" dx pgsql rm -f /tmp/oro.sql
lap db-restore
mut "cache:clear prod" console cache:clear --env=prod || fail "cache:clear"
lap cache-clear
if [ "$SKIPATT" = 0 ] && [ -n "$ATT" ]; then
    att=$ATT
    case $att in http*) att=$work/attachments.tgz; mut "fetch $ATT" fetch "$ATT" "$att" || fail "download attachments" ;; esac
    if [ "$DRY" = 1 ]; then say "would: import-attachments.sh $att --env prod"
    else "$LE_DIR/import-attachments.sh" "$att" --env prod --project "$PROJECT" || exit 1; fi
    lap attachments
fi
total "restore ok"
