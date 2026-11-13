---
name: env
description: >-
  Use for ANY local Oro environment task: check or repair the local or local-test stack, reset the test
  DB/ES/Mongo/MQ, rebuild the e2e baseline, restore the qa dump, import qa attachments, size e2e workers, switch the
  host between projects, "e2e env broken", "port changed", "mongo OOM", "how many workers". Always go through
  `aaxis-oro env ...` and `aaxis-oro test <target> ...`; never run docker compose down -v, FLUSHALL, db.sh or
  reinstall.sh, and never sudo without asking.
---

# env

Per-clone facts live in `<project>/.oro-ai/local-env/env.yml` (contract: `README.md`, schema: `schema/`). Scripts are
quiet (one line per phase), log detail to `.oro-ai/local-env/logs/`, take `--project P`, `--dry-run`, `--verbose`.
Every gitignored local config file is rendered from `env/templates/` + env.yml: never hand-edit a rendered file, change
env.yml (or the template, in oro-skills) and rerun. `check` detects drift by rendering and comparing.

| Situation | Command |
|---|---|
| New clone, or first run of this plugin on a project | `aaxis-oro env setup` (asks for what it cannot default, see below) |
| Something feels off (ports, Node, PHP, vhost, baseline, config drift) | `aaxis-oro env check` (exit 2 = drift, lists items) |
| What would setup/repair change? | `aaxis-oro env render --diff` (or `--check`); read-only |
| check reported drift | `aaxis-oro env repair [--only params\|vhost\|hosts\|templates]` |
| Test stack dirty before an e2e/PHPUnit run | `aaxis-oro env reset [--skip-reindex]` |
| Baseline missing or `baseline_key` changed (composer.lock, migrations, fixtures) | `aaxis-oro env baseline [--refresh]` (about 8 minutes, no-op when current) |
| Need qa attachments / qa dump locally | `aaxis-oro env import-attachments`, `aaxis-oro env restore --yes` |
| Worker count for e2e | `aaxis-oro env workers [--write]` (setup writes it; `workers_source: user` pins it) |
| Run a test or console command | `aaxis-oro test <local\|local-test> <phpunit\|e2e\|console\|verify>` (explicit target, verified first) |
| Move the host to another project | `aaxis-oro env switch <project>` (user-run, sudo) |

## Setup

- Domains, TLS certificate paths and the project namespace are never defaulted or hard-coded. When setup exits 64 with
  `ask:` lines, ask the user for each value, then rerun `aaxis-oro env setup --set key=value ...`.
- It renders `docker-compose.override.yml` (fixed Mongo port, capped cache and memory, no dummy profile),
  `.env-app.local` (merge: Node pin and profile lines removed, Mongo port set), `.env-app.behat_test.local` and
  `.env-app.test.local` (one template), the nginx test block and, only with `local_test.supervisor_consumer: true`, the
  `mc_test` program (autostart off). Nginx and supervisor files are staged under `.oro-ai/local-env/rendered/`.
- Node comes from `.nvmrc` through nvm into `parameters.yml` (managed, no backup); PHP comes from `composer.json`.
- It also scaffolds the git-ignored POC bundle `src/Aaxis/Bundle/AppBundle` (own `.gitignore` `*`) for spikes; code there
  is never committed or depended on. Existing files in it are left alone.
- Container changes are not applied by setup: it prints `NEXT: docker compose up -d ...`; run that, never `down -v`.

## Hard rules

- sudo protocol: exit 10 means the script printed `SUDO-NEEDED: <cmd>`. Show the exact command to the user and wait for
  them to run it or approve it, even in bypass mode; never run it yourself. Nginx reload is `sudo supervisorctl signal HUP
  nginx`, never systemctl.
- Exit 3 is a guard abort (a name outside `oro_test*`, or a target that does not resolve to its configured stack).
  Do not work around it; read the printed line.
- Test and dev stacks are separate (DB, search prefix, MQ vhost, session db). Tests never run against `local`.
- Redis holds sessions only (local db 0, test db 7); app caches stay on disk. No Redis cache DSNs in test dotenv files.
- The test web kernel is `behat_test` (nginx `fastcgi_param ORO_ENV behat_test`); children (fixtures, actions, PHPUnit)
  use `test`. Run the MQ consumer only during a run: `c oro:message-queue:consume --env=behat_test` in the background,
  or `sc start mc_test`. No websocket server for the test stack.
- Reuse the team aliases (`sc`, `rs`, `cstart`, `cstop`, `d`, `c`, `/oroapp`, `oro-project`); never rename them.
- Gotchas: pipeline PHPUnit has no ext-intl (`\Locale::*` throws; run with `php -n`); pre-commit schema-drift checks
  hit a nonexistent `oro` DB during an install: export `ORO_DB_URL` first.
- CI single-DB mode must keep working; see `references/ci-parity.md`.
