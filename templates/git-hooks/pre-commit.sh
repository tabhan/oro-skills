#!/usr/bin/env bash
# aaxis-oro:managed-pre-commit
# Managed by the aaxis-oro plugin: static/quality checks mirrored from this project's CI and tool configs.
# Do not edit; local edits are overwritten. Regenerate: aaxis-oro setup sync --project "$(git rev-parse --show-toplevel)"
# Status: aaxis-oro setup status. Settings: "precommit" in .oro-ai/config.json (path-prefix, atlas, skip).
# Sources: @@SOURCES@@
set -o pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

fail=0
run_step() {
    local name="$1"
    shift
    echo "==> ${name}"
    if ! "$@"; then
        echo "xxx ${name} FAILED" >&2
        fail=1
    fi
}

run_yamllint() {
    if command -v yamllint >/dev/null 2>&1; then
        yamllint "$@"
    elif command -v docker >/dev/null 2>&1; then
        # The image's entrypoint is yamllint itself; do not repeat the binary name.
        docker run --rm -v "$PWD":/data -w /data cytopia/yamllint:latest "$@"
    else
        echo "!!! yamllint unavailable (no yamllint, no docker); fix: aaxis-oro setup sync" >&2
        return 1
    fi
}
@@NODE@@
@@STEPS@@

if [[ "$fail" -ne 0 ]]; then
    echo "" >&2
    echo "pre-commit checks failed -- fix the issues above before committing." >&2
    exit 1
fi
exit 0
