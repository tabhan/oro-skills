# env

Per-clone local environment facts and the scripts that act on them. `SKILL.md` is the decision guide; this file
documents the data contract. All commands run as `aaxis-oro env <command>`.

## env.yml

Location: `<project>/.oro-ai/local-env/env.yml` (untracked; `.oro-ai/` is the local data root).
Legacy location `<project>/.claude/oro-local-env/env.yml` is migrated, not read.
Machine-readable schema: `schema/env.schema.json`. Every script loads the file through
`scripts/local-env/lib/env.py`.

| Key | Meaning |
|---|---|
| `project` | compose project name prefix (required) |
| `app_root` | application root in the container/host convention, default `/oroapp` |
| `project_namespace` | PHP namespace of the project bundles; used by the "Aaxis bundles never depend on project code" check |
| `qa_server` | `url`, `db_dump`, `attachments` (var/data archive only; public/media is cache, never synced) |
| `local` | `domain`, `tls_cert`, `tls_key`, `db` (default `oro`) |
| `local_test` | test stack: `domain`, `tls_cert`, `tls_key`, `db` (`oro_test`), `db_baseline`, `es_prefix`, `mq_vhost`, `redis_dbs`, `mongo_public`, `mongo_private`, `mongo_private_baseline`, `baseline_key`, `workers`, `workers_source` (`auto`/`user`), `admin` |
| `services.mongo` | `port` (27017), `cache_gb` (0.5), `mem_limit` (2g) |

Rules enforced by `validate`: the test db and RabbitMQ vhost must start with `oro_test`, the baseline db and ES prefix with `oro_test_`,
Mongo test names with `oro_test_` (the destructive scripts rely on this guard), and `local_test.db` differs from `local.db`.
Domains, certificates and `project_namespace` are never defaulted; `validate` prints them as `ask:` lines and setup asks.

## Commands

```bash
python3 scripts/local-env/lib/env.py validate <file>          # 0 valid, 1 invalid
python3 scripts/local-env/lib/env.py migrate [--project P]    # legacy -> new location, converting to the schema
python3 scripts/local-env/lib/env.py get [--project P] local_test.es_prefix
python3 -m unittest discover -s tests/local_env
```

`migrate` is idempotent; it exits 2 and changes nothing when both files exist and differ.

## Scripts

All live in `scripts/local-env/`, read `<project>/.oro-ai/local-env/env.yml` and accept `--project P`, `--dry-run`,
`--verbose` (`--json` where noted). Output is one line per phase; detail goes to
`<project>/.oro-ai/local-env/logs/<script>-<ts>.log` (last 10 kept per script).

Exit codes: 0 ok, 1 failure, 2 drift (`check.sh`), 3 guard abort, 10 sudo needed (the command is printed as
`SUDO-NEEDED: <cmd>`; scripts never run sudo), 64 usage.

| Script | Purpose |
|---|---|
| `env check [--json]` (`check.sh`) | read-only drift report: Node (`.nvmrc` vs `parameters.yml` vs shell), PHP vs `composer.json`, Mongo port and cache flag, nginx/fpm, `/etc/hosts`, test DBs, vhost, baseline key |
| `repair.sh [--only params\|vhost\|hosts\|templates]` | fixes what check reports: `parameters.yml` keys, test vhost, sudo steps for `/etc/hosts`; dotenv files it edits are backed up to `var/backups/oro-local-env/` |
| `baseline.sh [--refresh]` | `oro:install --env=behat_test` into `db`, then PG template + Mongo private baseline; no-op while `baseline_key` matches |
| `reset.sh [--skip-reindex]` | PG clone from template, Mongo restore, ES indices by name, test session Redis db, `behat_test.log`, MQ queues, reindex |
| `es-drop-prefix.sh`, `pg-drop.sh`, `mongo-drop.sh`, `mq-vhost-drop.sh` | single-resource drops behind the guard |
| `import-attachments.sh`, `restore-local.sh --yes` | qa attachments into GridFS through `FileManager`; qa dump into the local data db |
| `workers.sh [--write]` | `max(1, min(floor(cpus/4), floor((ram_gb-4)/3)))`, RAM from MemTotal |
| `aaxis-oro test <local\|local-test> <phpunit\|e2e\|console\|verify>` | explicit-target runner, no default (`scripts/local-env/test.sh`) |
| `supervisor.sh`, `switch.sh` | print the sudo command for process control / host switch (`aaxis-oro env switch`); the team `oro-project` script delegates to it (`oro-project --install` links it into `/usr/local/bin`) |

`config/parameters.yml` is generated and fully managed by these scripts: `oro_asset.nodejs_path/npm_path/pnpm_path`
come from nvm's resolution of `node_pin` (env.yml, optional) or else `.nvmrc`, and `gaufrette_adapter.public/private`
are the GridFS adapters. `check.sh` reports any difference and `repair.sh --only params` rewrites the file in place
without a backup (do not hand-edit it). The test stack dotenv files must not define Redis cache DSNs
(`ORO_REDIS_CACHE/DOCTRINE/LAYOUT_DSN`): app caches stay on disk and Redis only holds sessions.

Guard (every destructive path): the names come from `env.yml`, must start with `oro_test` (Mongo `oro_test_`), are
listed before deleting and deleted one by name (ES refuses wildcard deletes); any name outside the prefix aborts
with exit 3 before anything is touched, and an empty list is a no-op. The Redis flush only targets the test session
db (never 0). `session_redis_db` defaults to 7 (the last entry of `redis_dbs` when 7 is absent).

`aaxis-oro test` first refuses `--env`/`-e` values and `ORO_ENV`/`APP_ENV` outside the target's kernel envs (`local-test`:
`test`, `behat_test`; `local`: anything but those), then boots each env's real kernel (`lib/live-target.php`, ~0.5 s
per env) and compares the resolved values with env.yml: live `select current_database()`, search prefixes, GridFS
db names, and for `behat_test` also the MQ vhost and session db. Mismatch exits 3 and runs nothing; success is one
line with the elapsed time. `phpunit` always sets `ORO_ENV=test`; `e2e` runs
`aaxis:test:e2e --env=behat_test`; both print a summary of at most ~15 lines and the log path.

Tests: `python3 -m unittest discover -s tests/local_env` (guards run against stubbed docker/curl/php in
`tests/local_env/stubs/`).
