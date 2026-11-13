# oro: ">=7.0.0"
# Shared helpers for the local-env scripts (sourced, not executed).
# Exit codes: 0 ok, 1 failure, 2 drift (check), 3 guard abort, 10 sudo needed, 64 usage.
LE_LIB=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LE_DIR=$(dirname "$LE_LIB")
LE_ROOT=$(cd "$LE_DIR/../.." && pwd)
SUDO_PENDING=0

le_parse() {
    PROJECT=$PWD DRY=0 VERBOSE=0 JSON=0 ARGS=()
    while [ $# -gt 0 ]; do
        case $1 in
            --project) [ $# -ge 2 ] && [ -d "$2" ] || { echo "usage: --project needs an existing directory" >&2; exit 64; }
                PROJECT=$(cd "$2" && pwd); shift ;;
            --dry-run) DRY=1 ;;
            --verbose) VERBOSE=1 ;;
            --json) JSON=1 ;;
            -h|--help) sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
            *) ARGS+=("$1") ;;
        esac
        shift
    done
}

say() { printf '%s\n' "$*"; printf '%s\n' "$*" >> "$LOG"; }
logv() { printf '%s\n' "$*" >> "$LOG"; [ "$VERBOSE" = 1 ] && printf '%s\n' "$*"; return 0; }
fail() { say "FAIL $*"; exit 1; }
usage_exit() { echo "usage: $LE_USAGE" >&2; exit 64; }
guard_abort() { say "guard: $*; nothing changed"; exit 3; }

# Loads env.yml into shell variables (PROJ, TEST_DB, ES_PREFIX, ...); exits 1/3 when invalid.
le_init() {
    LE_NAME=$1; shift
    le_parse "$@"
    LOGDIR=$PROJECT/.oro-ai/local-env/logs
    mkdir -p "$LOGDIR"
    LOG=$LOGDIR/$LE_NAME-$(date +%Y%m%d-%H%M%S).log
    : > "$LOG"
    # shellcheck disable=SC2012
    ls -1t "$LOGDIR/$LE_NAME"-*.log 2>/dev/null | tail -n +11 | xargs -r rm -f --
    python3 "$LE_ROOT/bin/oro-applies" --project "$PROJECT" "$0" >/dev/null 2>&1
    if [ $? -eq 1 ]; then echo "$LE_NAME: skipped, does not apply to this Oro version"; exit 0; fi
    local out rc
    out=$(python3 "$LE_LIB/envsh.py" shell --project "$PROJECT" 2>"$LOG.err"); rc=$?
    if [ $rc -ne 0 ]; then head -3 "$LOG.err" >&2; cat "$LOG.err" >> "$LOG"; rm -f "$LOG.err"; exit $rc; fi
    rm -f "$LOG.err"
    eval "$out"
    LE_T0=$EPOCHREALTIME; LE_T=$LE_T0
}

lap() { local n=$EPOCHREALTIME; say "$(awk -v a="$LE_T" -v b="$n" -v l="$1" 'BEGIN{printf "%-18s %5.1fs", l, b-a}')"; LE_T=$n; }
total() { say "$(awk -v a="$LE_T0" -v b="$EPOCHREALTIME" -v l="$1" 'BEGIN{printf "%s %.1fs", l, b-a}')"; }

# Run a mutating command: output to the log; in --dry-run only print what would happen.
mut() {
    local desc=$1; shift
    if [ "$DRY" = 1 ]; then say "would: $desc"; return 0; fi
    logv "+ $desc"
    "$@" >> "$LOG" 2>&1
}

# Command that prints a SUDO-NEEDED line instead of running sudo.
sudo_needed() { say "SUDO-NEEDED: $*"; SUDO_PENDING=1; }
finish() { [ "$SUDO_PENDING" = 1 ] && exit 10; exit "${1:-0}"; }

le_ident() { [[ $1 =~ ^[A-Za-z0-9_]+$ ]] || guard_abort "refusing '$1': not a plain identifier"; }
# le_guard <prefix> <name>: abort (exit 3) when the name is not under the test prefix.
le_guard() { le_ident "$2"; case $2 in "$1"*) ;; *) guard_abort "refusing '$2': outside test prefix '$1'" ;; esac; }

cname() { echo "${LE_CONTAINER_PREFIX:-$PROJ}-$1-1"; }
dx() { local svc=$1; shift; docker exec "$(cname "$svc")" "$@"; }
pg() { dx pgsql psql -U postgres -qAt "$@"; }
es() { curl -s "${ES_URL:-http://127.0.0.1:9200}$1" "${@:2}"; }
console() { (cd "$PROJECT" && php bin/console "$@"); }

# Value of KEY from the first existing dotenv file (highest priority first); empty if unset.
dotenv_get() {
    local key=$1 f
    for f in .env-app.test.local .env-app.behat_test.local .env-app.local; do
        [ -f "$PROJECT/$f" ] && grep -E "^$key=" "$PROJECT/$f" | tail -1 | cut -d= -f2- && return 0
    done
    return 0
}

nvm_version() { # resolves env.yml node_pin, else .nvmrc, through nvm; prints vX.Y.Z or N/A
    local want=${NODE_PIN:-}; [ -n "$want" ] || want=$(tr -d ' \n' < "$PROJECT/.nvmrc" 2>/dev/null) || return
    # shellcheck disable=SC1091
    (export NVM_DIR=${NVM_DIR:-$HOME/.nvm}; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" >/dev/null 2>&1 && nvm version "$want" 2>/dev/null)
}

