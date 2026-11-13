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

| Situation | Command |
|---|---|
| Something feels off (ports, Node, PHP, vhost, baseline) | `aaxis-oro env check` (exit 2 = drift, lists items) |
| check reported drift | `aaxis-oro env repair [--only params\|vhost\|hosts\|templates]` |
| Test stack dirty before an e2e/PHPUnit run | `aaxis-oro env reset [--skip-reindex]` |
| Baseline missing or `baseline_key` changed (composer.lock, migrations, fixtures) | `aaxis-oro env baseline [--refresh]` (about 8 minutes, no-op when current) |
| Need qa attachments / qa dump locally | `aaxis-oro env import-attachments`, `aaxis-oro env restore --yes` |
| Worker count for e2e | `aaxis-oro env workers [--write]` |
| Run a test or console command | `aaxis-oro test <local\|local-test> <phpunit\|e2e\|console\|verify>` (explicit target, verified first) |
| Move the host to another project | `aaxis-oro env switch <project>` (user-run, sudo) |

## Hard rules

- Exit 10 means a sudo step: the script printed `SUDO-NEEDED: <cmd>`. Show it to the user; never run it yourself.
- Exit 3 is a guard abort (a name outside `oro_test*`, or a target that does not resolve to its configured stack).
  Do not work around it; read the printed line.
- Test and dev stacks are separate (DB, search prefix, MQ vhost, session db). Tests never run against `local`.
- `config/parameters.yml` Node and GridFS keys are managed by `repair`; do not hand-edit them.
- CI single-DB mode must keep working; see `references/ci-parity.md`.
