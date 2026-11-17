#!/usr/bin/env bash
# oro: ">=6.1.0"
# Print the e2e worker count for this host: max(1, min(floor(cpus/4), floor((ram_gb-4)/3))).
# Usage: workers.sh [--write] [--project P]   (--write stores it in env.yml unless workers_source is user)
# Env overrides for tests: LE_CPUS, LE_RAM_GB. Exit: 0 ok, 64 usage.
source "$(dirname "$0")/lib/common.sh"
le_init workers "$@"
# nproc//proc/meminfo are Linux-only; macOS answers through sysctl.
cpus=${LE_CPUS:-$(nproc 2>/dev/null || sysctl -n hw.ncpu)}
if [ -z "${LE_RAM_GB:-}" ]; then
    if [ -r /proc/meminfo ]; then LE_RAM_GB=$(awk '/MemTotal/{print int($2/1048576)}' /proc/meminfo)
    else LE_RAM_GB=$(($(sysctl -n hw.memsize) / 1073741824)); fi
fi
ram=$LE_RAM_GB
by_cpu=$((cpus / 4)); by_ram=$(((ram - 4) / 3))
n=$((by_cpu < by_ram ? by_cpu : by_ram)); [ "$n" -ge 1 ] || n=1
if [[ " ${ARGS[*]:-} " == *" --write "* ]]; then
    if [ "$WORKERS_SOURCE" = user ]; then say "workers: kept $WORKERS (workers_source=user); computed $n"
    else python3 "$LE_LIB/envsh.py" set --project "$PROJECT" local_test.workers "$n" && say "workers: wrote $n" || fail "env.yml write"; fi
else
    echo "$n"
fi
