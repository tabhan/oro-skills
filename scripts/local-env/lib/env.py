#!/usr/bin/env python3
"""Load, validate, migrate and write the per-clone local-env facts (<project>/.oro-ai/local-env/env.yml).

  env.py validate <file>            exit 0 valid, 1 invalid (messages on stderr); missing asks are warnings only
  env.py migrate [--project P]      move <P>/.claude/oro-local-env/env.yml to the new location, converting to the schema
  env.py get [--project P] <a.b>    print one value (lists as comma-separated)
  env.py path [--project P]         print the env.yml path

Exit 2 when migrate finds both files and they differ; 64 on usage errors. Stdlib only (miniyaml from atlas).
Domains and certificates are never defaulted: validate lists them as asks for setup.
"""
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.realpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "atlas"))

from atlas import miniyaml  # noqa: E402

SCHEMA_PATH = os.path.join(ROOT, "env", "schema", "env.schema.json")
NEW_REL = os.path.join(".oro-ai", "local-env", "env.yml")
OLD_REL = os.path.join(".claude", "oro-local-env", "env.yml")
HEADER = "# Per-clone local environment facts for the aaxis-oro env scripts. Never committed (.oro-ai/ is untracked).\n"

# Non-environment-specific defaults only: no domains, certs or namespaces.
DEFAULTS = {
    "app_root": "/oroapp",
    "local": {"db": "oro"},
    "local_test": {
        "db": "oro_test", "db_baseline": "oro_test_baseline", "es_prefix": "oro_test_", "mq_vhost": "oro_test",
        "redis_dbs": [4, 5, 6, 7], "mongo_public": "oro_test_public", "mongo_private": "oro_test_private",
        "mongo_private_baseline": "oro_test_private_baseline", "workers_source": "auto",
        "admin": {"first": "John", "last": "Doe", "language": "en_US"},
    },
    "services": {"mongo": {"port": 27017, "cache_gb": 0.5, "mem_limit": "2g"}},
}
ASKS = ("local.domain", "local.tls_cert", "local.tls_key", "local_test.domain", "local_test.tls_cert",
        "local_test.tls_key", "project_namespace")


def new_path(project):
    return os.path.join(os.path.abspath(project), NEW_REL)


def old_path(project):
    return os.path.join(os.path.abspath(project), OLD_REL)


def plain(node):
    """miniyaml containers -> plain dict/list so equality and json work."""
    if isinstance(node, dict):
        return {k: plain(v) for k, v in node.items()}
    if isinstance(node, list):
        return [plain(v) for v in node]
    # miniyaml has no float scalars; the schema holds no decimal-looking strings.
    return float(node) if isinstance(node, str) and re.fullmatch(r"-?\d+\.\d+", node) else node


def load(path):
    data = plain(miniyaml.parse_file(path))
    return data if isinstance(data, dict) else {}


def with_defaults(data, defaults=DEFAULTS):
    out = dict(data)
    for key, value in defaults.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = with_defaults(out[key], value)
        elif isinstance(value, dict):
            out.setdefault(key, with_defaults({}, value))
        else:
            out.setdefault(key, value)
    return out


def _json_type(value):
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return {str: "string", list: "array", dict: "object", type(None): "null"}.get(type(value), "unknown")


def check_schema(value, schema, where="env"):
    """Subset of JSON Schema used by env.schema.json: type, enum, pattern, required, properties, items."""
    errors = []
    kinds = schema.get("type")
    kinds = [kinds] if isinstance(kinds, str) else kinds
    actual = _json_type(value)
    if kinds and actual not in kinds and not (actual == "integer" and "number" in kinds):
        return ["%s: expected %s, got %s" % (where, "/".join(kinds), actual)]
    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: %r not in %s" % (where, value, schema["enum"]))
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        errors.append("%s: %r does not match %s" % (where, value, schema["pattern"]))
    if isinstance(value, dict):
        errors += ["%s: missing required key %r" % (where, k) for k in schema.get("required", []) if k not in value]
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                errors += check_schema(value[key], sub, "%s.%s" % (where, key))
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errors += check_schema(item, schema["items"], "%s[%d]" % (where, i))
    return errors


def guard_errors(data):
    """Test-stack names must carry the test prefix: the reset/drop scripts rely on it to never touch real data."""
    t = data.get("local_test")
    if not isinstance(t, dict):
        return []
    rules = (("db", "oro_test"), ("db_baseline", "oro_test_"), ("es_prefix", "oro_test_"), ("mq_vhost", "oro_test"),
             ("mongo_public", "oro_test_"), ("mongo_private", "oro_test_"), ("mongo_private_baseline", "oro_test_"))
    errors = ["local_test.%s: prefix must start with %s (got %r)" % (k, p, t[k])
              for k, p in rules if isinstance(t.get(k), str) and not t[k].startswith(p)]
    if isinstance(data.get("local"), dict) and data["local"].get("db") and data["local"]["db"] == t.get("db"):
        errors.append("local_test.db must differ from local.db")
    return errors


def lookup(data, dotted):
    node = data
    for part in dotted.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return node


def missing_asks(data):
    return [a for a in ASKS if not lookup(data, a)]


def validate(data):
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        schema = json.load(fh)
    return check_schema(data, schema) + guard_errors(data)


def _scalar(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


def dump(data, indent=0):
    pad = "    " * indent
    lines = []
    for key, value in data.items():
        if isinstance(value, dict) and value:
            lines.append("%s%s:" % (pad, key))
            lines.append(dump(value, indent + 1))
        elif isinstance(value, list):
            if any(isinstance(v, (dict, list)) for v in value):
                raise ValueError("%s: lists of mappings or lists are not supported in env.yml" % key)
            lines.append("%s%s: [%s]" % (pad, key, ", ".join(_scalar(v) for v in value)))
        else:
            lines.append("%s%s: %s" % (pad, key, _scalar(value) if not isinstance(value, dict) else "{}"))
    return "\n".join(lines)


def save(path, data):
    text = HEADER + dump(data) + "\n"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def migrate(project, out=sys.stdout):
    """0 done or nothing to do, 2 refused. The legacy file is only removed after the converted data validated and
    was written; a copy stays beside the new file as env.yml.legacy.bak."""
    old, new = old_path(project), new_path(project)
    if not os.path.exists(old):
        out.write("env.yml: nothing to migrate (%s)\n" % ("already at " + new if os.path.exists(new) else "no legacy file"))
        return 0
    converted = with_defaults(load(old))
    errors = validate(converted)
    if errors:
        sys.stderr.write("".join("error: %s\n" % e for e in errors) + "env.yml: legacy file kept at %s; fix it and rerun\n" % old)
        return 2
    if os.path.exists(new) and load(new) != converted:
        sys.stderr.write("env.yml: both %s and %s exist and differ; merge by hand and delete the old one\n" % (old, new))
        return 2
    try:
        if not os.path.exists(new):
            save(new, converted)
    except ValueError as exc:
        sys.stderr.write("env.yml: cannot convert (%s); legacy file kept at %s\n" % (exc, old))
        return 2
    shutil.copy2(old, new + ".legacy.bak")
    os.remove(old)
    try:
        os.rmdir(os.path.dirname(old))
    except OSError:
        pass
    out.write("env.yml: moved %s -> %s (backup %s.legacy.bak)\n" % (old, new, new))
    return 0


def main(argv):
    if not argv or argv[0] not in ("validate", "migrate", "get", "path"):
        sys.stderr.write(__doc__)
        return 64
    cmd, rest = argv[0], argv[1:]
    project = os.getcwd()
    if "--project" in rest:
        i = rest.index("--project")
        project = rest[i + 1] if i + 1 < len(rest) else project
        rest = rest[:i] + rest[i + 2:]
    if cmd == "migrate":
        return migrate(project)
    if cmd == "path":
        print(new_path(project))
        return 0
    if cmd == "get":
        if len(rest) != 1 or not os.path.exists(new_path(project)):
            sys.stderr.write("env.py get: needs one dotted key and an existing %s\n" % new_path(project))
            return 64
        value = lookup(with_defaults(load(new_path(project))), rest[0])
        print(",".join(str(v) for v in value) if isinstance(value, list) else "" if value is None else value)
        return 0
    if len(rest) != 1 or not os.path.exists(rest[0]):
        sys.stderr.write("env.py validate: give an existing file\n")
        return 64
    data = load(rest[0])
    errors = validate(data)
    for e in errors:
        sys.stderr.write("error: %s\n" % e)
    for a in missing_asks(data):
        sys.stderr.write("ask: %s is not set; setup must ask for it\n" % a)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
