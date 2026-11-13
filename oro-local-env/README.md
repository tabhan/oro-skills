# oro-local-env

Per-clone local environment facts and the scripts that act on them. Skill text (SKILL.md) arrives with the setup
work; this file documents the data contract.

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

Rules enforced by `validate`: the test db, baseline, ES prefix and RabbitMQ vhost must start with `oro_test`,
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
