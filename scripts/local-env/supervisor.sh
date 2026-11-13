#!/usr/bin/env bash
# oro: ">=7.0.0"
# Process control for the host stack (nginx, fpm, ws, mc, optional mc_test) under supervisord. Every action needs
# sudo, so by default this only prints the exact command (SUDO-NEEDED, exit 10) for the user to run or approve.
# Usage: supervisor.sh status|start|stop|restart <program...> | reload-nginx   [--run]
#   --run  execute the printed command with sudo; pass it only after the user approved that exact command.
# Never uses systemctl. Exit: 0 done, 10 sudo needed, 64 usage.
source "$(dirname "$0")/lib/common.sh"
le_init supervisor "$@"
LE_USAGE="supervisor.sh status|start|stop|restart <program...> | reload-nginx [--run]"
RUN=0; rest=()
for a in "${ARGS[@]:-}"; do [ "$a" = "--run" ] && RUN=1 || rest+=("$a"); done
case ${rest[0]:-} in
    status) cmd="sudo supervisorctl status ${rest[*]:1}" ;;
    start|stop|restart) [ ${#rest[@]} -ge 2 ] || usage_exit; cmd="sudo supervisorctl ${rest[0]} ${rest[*]:1}" ;;
    reload-nginx) cmd="sudo supervisorctl signal HUP nginx" ;;
    *) usage_exit ;;
esac
cmd=${cmd% }
if [ "$RUN" = 1 ] && [ "$DRY" = 0 ]; then say "+ $cmd"; $cmd 2>&1 | tee -a "$LOG"; exit "${PIPESTATUS[0]}"; fi
sudo_needed "$cmd"
finish 0
