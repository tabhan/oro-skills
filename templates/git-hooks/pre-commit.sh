#!/usr/bin/env bash
# aaxis-oro:managed-pre-commit
# Managed by the aaxis-oro plugin: static/quality checks mirrored from this project's CI and tool configs.
# Do not edit; local edits are overwritten. Regenerate: aaxis-oro setup sync --project "$(git rev-parse --show-toplevel)"
# Status: aaxis-oro setup status. Settings: "precommit" in .oro-ai/config.json (path-prefix, atlas, skip, exclude).
# Env: AAXIS_ORO_PRECOMMIT_ALL=1 runs every step regardless of the staged file types (nothing staged also runs all).
# Sources: @@SOURCES@@
set -o pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

fail=0
STAGED="$(git diff --cached --name-only --diff-filter=ACMRD)"

# GATE (ERE, set per call) limits a step to commits that stage a matching file; unset, or nothing staged, runs it.
run_step() {
    local name="$1"
    shift
    if [[ -n "${GATE:-}" && -n "$STAGED" && -z "${AAXIS_ORO_PRECOMMIT_ALL:-}" ]] && ! grep -Eq -- "$GATE" <<<"$STAGED"; then
        echo "--- ${name} skipped (no staged file of its type)"
        return 0
    fi
    echo "==> ${name}"
    if ! "$@"; then
        echo "xxx ${name} FAILED" >&2
        fail=1
    fi
}

# CI lints the tracked tree only. Paths git ignores or excludes (.gitignore, .git/info/exclude), untracked paths and
# precommit.exclude entries are kept out of every whole-tree step: EXCL_CSV for phpcs/phpmd, EXCL_IGN for eslint/stylelint.
EXCLUDES=()
while IFS= read -r entry; do
    [[ -n "$entry" ]] && EXCLUDES+=("${entry%/}")
done < <({
    git ls-files --others --ignored --exclude-standard --directory
    git ls-files --others --exclude-standard --directory
    printf '%s\n' @@EXCLUDE@@
} | sort -u)
EXCL_CSV=""
EXCL_IGN=()
for entry in "${EXCLUDES[@]}"; do
    if [[ -d "$entry" ]]; then
        EXCL_CSV+="${EXCL_CSV:+,}*/${entry}/*"
        EXCL_IGN+=(--ignore-pattern "${entry}/**")
    else
        EXCL_CSV+="${EXCL_CSV:+,}*/${entry}"
        EXCL_IGN+=(--ignore-pattern "${entry}")
    fi
done

# CPU count for phpcs --parallel: nproc, else getconf, else 1 (macOS without coreutils, minimal images).
phpcs_jobs() {
    local n
    n="$(nproc 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null)"
    [[ "$n" =~ ^[0-9]+$ && "$n" -ge 1 ]] && echo "$n" || echo 1
}

# Directory arguments are replaced by the tracked, non-excluded YAML files under them (yamllint has no ignore flag).
run_yamllint() {
    local args=() files=() arg entry file skip dirs=0
    for arg in "$@"; do
        if [[ -d "$arg" ]]; then
            dirs=1
            while IFS= read -r -d '' file; do
                skip=""
                for entry in "${EXCLUDES[@]}"; do
                    case "$file" in "$entry"|"$entry"/*|$entry) skip=1 ;; esac
                done
                [[ -z "$skip" ]] && files+=("$file")
            done < <(git ls-files -z -- "$arg" | grep -zE '\.ya?ml$')
        else
            args+=("$arg")
        fi
    done
    if [[ "$dirs" -eq 1 && ${#files[@]} -eq 0 ]]; then
        return 0
    fi
    if command -v yamllint >/dev/null 2>&1; then
        yamllint "${args[@]}" "${files[@]}"
    elif command -v docker >/dev/null 2>&1; then
        # The image's entrypoint is yamllint itself; do not repeat the binary name.
        docker run --rm -v "$PWD":/data -w /data cytopia/yamllint:latest "${args[@]}" "${files[@]}"
    else
        echo "!!! yamllint unavailable (no yamllint, no docker); fix: aaxis-oro setup sync" >&2
        return 1
    fi
}

# Doctrine schema drift against the LOCAL database (prod kernel); never the test stack.
run_schema_drift() {
    case "${ORO_ENV:-${APP_ENV:-}}" in
        test|behat_test) echo "refusing: ORO_ENV/APP_ENV points at the test stack; the drift check measures the local database" >&2; return 1 ;;
    esac
    case "${ORO_DB_URL:-}${ORO_DB_DSN:-}" in
        *oro_test*) echo "refusing: the database DSN points at the test stack (oro_test*)" >&2; return 1 ;;
    esac
    local out err rc sql
    err="$(mktemp)"
    out="$(ORO_ENV=prod APP_ENV=prod php bin/console doctrine:schema:update --dump-sql --env=prod --no-debug 2>"$err")"
    rc=$?
    if [[ "$rc" -ne 0 ]]; then
        cat "$err" >&2
        rm -f "$err"
        echo "!!! schema drift check could not run (console exit $rc); this is not a pass. Fix the local stack, or opt out with \"skip\": [\"schema-drift\"] under \"precommit\" in .oro-ai/config.json" >&2
        return 1
    fi
    rm -f "$err"
    # Blank lines, SQL comments and the "[OK] Nothing to update" banner are not drift.
    sql="$(grep -Ev '^[[:space:]]*$|^[[:space:]]*--|Nothing to update|^[[:space:]]*\[(OK|NOTE)\]' <<<"$out")"
    if [[ -z "$sql" ]]; then
        return 0
    fi
    if [[ "$(grep -c 'ADD CONSTRAINT' <<<"$sql")" -ge 50 ]]; then
        echo "database looks incomplete (hundreds of ADD CONSTRAINT lines): an install or migration is probably still running against the local database. Wait for it to finish and commit again; do not use --no-verify." >&2
    else
        echo "Doctrine schema drift detected:" >&2
        echo "$sql" >&2
        echo "See solutions/references/entities/entity-extend-indexes.md (entity_extend.yml) for DROP INDEX on extend fields." >&2
    fi
    return 1
}
@@NODE@@
@@STEPS@@

if [[ "$fail" -ne 0 ]]; then
    echo "" >&2
    echo "pre-commit checks failed -- fix the issues above before committing." >&2
    exit 1
fi
exit 0
