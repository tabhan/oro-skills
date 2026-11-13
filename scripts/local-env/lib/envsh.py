#!/usr/bin/env python3
# oro: ">=7.0.0"
"""Shell bridge to env.yml for the local-env scripts.

  envsh.py shell --project P            print KEY='value' assignments (validated; exit 1 invalid, 3 guard violation)
  envsh.py set --project P <a.b> <val>  write one value (ints/null/true/false are typed)
"""
import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import env  # noqa: E402

MAP = (
    ("PROJ", "project"), ("APP_ROOT", "app_root"), ("PROJECT_NS", "project_namespace"),
    ("QA_DUMP", "qa_server.db_dump"), ("QA_ATT", "qa_server.attachments"),
    ("LOCAL_DB", "local.db"), ("LOCAL_DOMAIN", "local.domain"),
    ("TEST_DB", "local_test.db"), ("TEST_BASE", "local_test.db_baseline"), ("TEST_DOMAIN", "local_test.domain"),
    ("ES_PREFIX", "local_test.es_prefix"), ("MQ_VHOST", "local_test.mq_vhost"),
    ("MONGO_PUB", "local_test.mongo_public"), ("MONGO_PRIV", "local_test.mongo_private"),
    ("MONGO_BASE", "local_test.mongo_private_baseline"), ("BASELINE_KEY", "local_test.baseline_key"),
    ("WORKERS", "local_test.workers"), ("WORKERS_SOURCE", "local_test.workers_source"),
    ("ADMIN_LANG", "local_test.admin.language"), ("ADMIN_FIRST", "local_test.admin.first"),
    ("ADMIN_LAST", "local_test.admin.last"),
    ("NODE_PIN", "node_pin"), ("MONGO_PORT", "services.mongo.port"), ("MONGO_CACHE", "services.mongo.cache_gb"), ("MONGO_MEM", "services.mongo.mem_limit"),
)


def typed(text):
    if text in ("null", "~"):
        return None
    if text in ("true", "false"):
        return text == "true"
    try:
        return int(text)
    except ValueError:
        return text


def main(argv):
    if len(argv) < 3 or argv[0] not in ("shell", "set") or argv[1] != "--project":
        sys.stderr.write(__doc__)
        return 64
    project, rest = argv[2], argv[3:]
    path = env.new_path(project)
    if not os.path.exists(path):
        sys.stderr.write("env.yml missing at %s; run the setup first\n" % path)
        return 1
    data = env.with_defaults(env.load(path))
    if argv[0] == "set":
        if len(rest) != 2:
            sys.stderr.write(__doc__)
            return 64
        node = data
        parts = rest[0].split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = typed(rest[1])
        errors = env.validate(data)
        if errors:
            sys.stderr.write("".join("error: %s\n" % e for e in errors))
            return 1
        env.save(path, data)
        return 0
    errors = env.validate(data)
    guard = env.guard_errors(data)
    if errors:
        sys.stderr.write("".join("error: %s\n" % e for e in errors))
        return 3 if guard else 1
    for name, key in MAP:
        value = env.lookup(data, key)
        print("%s=%s" % (name, shlex.quote("" if value is None else str(value))))
    session = (data["local_test"].get("session_redis_db"))
    if session is None:
        dbs = data["local_test"].get("redis_dbs") or [7]
        session = 7 if 7 in dbs else dbs[-1]
    print("SESSION_DB=%s" % int(session))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
