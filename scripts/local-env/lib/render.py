#!/usr/bin/env python3
# oro: ">=7.0.0"
"""Render the gitignored local config from env/templates and env.yml.

  render.py check|diff|write --project P

check  list drift only (one line each), exit 2 when any; diff  unified diffs; write  apply, backing up replaced files
to var/backups/oro-local-env/ and printing SUDO-NEEDED lines for files outside the project (nginx, supervisor).
Exit: 0 clean/applied, 1 error (invalid env.yml, unset value: the message names the key), 2 drift.
Templates: {{dotted.key}} values, {{#if flag}}..{{/if}} blocks on their own lines. Merge templates (.env-app.local)
enforce KEY=value lines in place, drop !KEY lines and keep everything else.
"""
import difflib
import getpass
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.realpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import env  # noqa: E402

TEMPLATES = os.path.join(ROOT, "env", "templates")
STAGE = os.path.join(".oro-ai", "local-env", "rendered")
BACKUPS = os.path.join("var", "backups", "oro-local-env")
OBSOLETE = (".env-app.e2e.local", "config/config_e2e.yml")
POC = os.path.join("src", "Aaxis", "Bundle", "AppBundle")


class RenderError(Exception):
    pass


def nginx_dir():
    return os.environ.get("LE_NGINX_DIR", "/etc/nginx/conf.d")


def supervisor_dir():
    return os.environ.get("LE_SUPERVISOR_DIR", "/etc/supervisor/conf.d")


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def dotenv(project):
    values = {}
    for name in (".env-app", ".env-app.local"):
        for line in (read(os.path.join(project, name)) or "").splitlines():
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
            if m:
                values[m.group(1)] = re.sub(r"\$\{(\w+)\}", lambda x: values.get(x.group(1), ""), m.group(2).strip("'\""))
    return values


def compose_rabbit_image(project):
    m = re.search(r"image:\s*(\S*rabbitmq:[^\s'\"]*?)(-management)?(-alpine)?\s*$", read(os.path.join(project, "docker-compose.yml")) or "", re.M)
    if not m:
        raise RenderError("docker-compose.yml: no rabbitmq image found")
    return "%s-management%s" % (m.group(1), m.group(3) or "")


def workers_auto():
    """Same formula as workers.sh, so a render before `workers --write` already shows the final value."""
    cpus = int(os.environ.get("LE_CPUS") or os.cpu_count() or 1)
    ram = int(os.environ.get("LE_RAM_GB") or int(re.search(r"MemTotal:\s+(\d+)", read("/proc/meminfo") or "MemTotal: 0").group(1)) // 1048576)
    return max(1, min(cpus // 4, (ram - 4) // 3))


def context(project, data, target):
    de = dotenv(project)
    current = dotenv_of(project, ".env-app.test.local")
    t = data["local_test"]
    session = t.get("session_redis_db") or (7 if 7 in t["redis_dbs"] else t["redis_dbs"][-1])
    pg_version = re.search(r"serverVersion=([\d.]+)", de.get("ORO_DB_URL", ""))
    search = de.get("ORO_SEARCH_URL", "")
    flat = {
        "target": target, "workers": t.get("workers") or workers_auto(), "user": getpass.getuser(), "project_dir": project, "session_db": str(session),
        "pg_user": de.get("POSTGRES_USER", "postgres"), "pg_password": de.get("POSTGRES_PASSWORD", "postgres"),
        "pg_server_version": pg_version.group(1) if pg_version else "17",
        "rabbit_user": de.get("RABBITMQ_DEFAULT_USER", "guest"), "rabbit_pass": de.get("RABBITMQ_DEFAULT_PASS", "guest"),
        "redis_url": de.get("ORO_REDIS_URL", "redis://127.0.0.1:6379"),
        "search_url": search if search.startswith("elastic-search://") else "elastic-search://127.0.0.1:9200",
        "admin_email": t["admin"].get("email") or current.get("ORO_TEST_INSTALL_USER_EMAIL") or "admin@example.com",
        "admin_org": current.get("ORO_TEST_INSTALL_ORGANIZATION_NAME") or "Oro",
        "rabbitmq_image": compose_rabbit_image(project),
    }
    return flat


def dotenv_of(project, name):
    out = {}
    for line in (read(os.path.join(project, name)) or "").splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def expand(template, data, flat, flags):
    lines, stack = [], [True]
    for line in template.splitlines():
        m = re.fullmatch(r"\s*\{\{#if (\w+)\}\}\s*", line)
        if m:
            stack.append(stack[-1] and bool(flags.get(m.group(1)) or env.lookup(data, m.group(1))))
            continue
        if re.fullmatch(r"\s*\{\{/if\}\}\s*", line):
            stack.pop()
            continue
        if stack[-1]:
            lines.append(line)

    def value(m):
        key = m.group(1)
        v = flat[key] if key in flat else env.lookup(data, key)
        if v is None or v == "":
            raise RenderError("%s is not set in env.yml; setup must ask for it" % key)
        return str(v)

    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", value, "\n".join(lines)) + "\n"


def merge_dotenv(existing, wanted):
    lines = (existing or "").splitlines()
    for spec in wanted.splitlines():
        if not spec.strip() or spec.startswith("#"):
            continue
        if spec.startswith("!"):
            key = spec[1:]
            lines = [x for x in lines if not re.match(r"^%s=" % re.escape(key), x)]
            continue
        key = spec.split("=", 1)[0]
        hits = [i for i, x in enumerate(lines) if re.match(r"^%s=" % re.escape(key), x)]
        if hits:
            lines[hits[0]] = spec
            lines = [x for i, x in enumerate(lines) if i == hits[0] or i not in hits]
        else:
            lines.append(spec)
    return "\n".join(lines) + "\n"


def items(project, data):
    """(id, kind, dest, content, extra) for every managed file; dest is absolute."""
    flat = lambda target: context(project, data, target)  # noqa: E731
    p = lambda rel: os.path.join(project, rel)  # noqa: E731
    tmpl = lambda name: read(os.path.join(TEMPLATES, name))  # noqa: E731
    out = [("compose", "file", p("docker-compose.override.yml"),
            expand(tmpl("docker-compose.override.yml.tmpl"), data, flat("local"), {}), None)]
    merged = merge_dotenv(read(p(".env-app.local")), expand(tmpl("env-app.local.tmpl"), data, flat("local"), {}))
    out.append(("env-local", "file", p(".env-app.local"), merged, None))
    for target in ("behat_test", "test"):
        out.append(("env-" + target, "file", p(".env-app.%s.local" % target),
                    expand(tmpl("env-app.test-stack.local.tmpl"), data, flat(target), {target: True}), None))
    domain = data["local_test"].get("domain")
    nginx = expand(tmpl("nginx-test.conf.tmpl"), data, flat("local"), {})
    out.append(("nginx", "sudo", p(os.path.join(STAGE, "nginx-test.conf")), nginx,
                (os.path.join(nginx_dir(), "%s.conf" % domain), "sudo nginx -t && sudo supervisorctl signal HUP nginx")))
    if data["local_test"].get("supervisor_consumer"):
        out.append(("supervisor", "sudo", p(os.path.join(STAGE, "supervisor-mc_test.conf")),
                    expand(tmpl("supervisor-mc_test.conf.tmpl"), data, flat("local"), {}),
                    (os.path.join(supervisor_dir(), "mc_test.conf"), "sudo supervisorctl reread && sudo supervisorctl update")))
    return out


def poc_missing(project):
    """Paths the POC scratch bundle scaffold would create; existing files (a bundle already in use) are never touched."""
    base = os.path.join(project, POC)
    wanted = {"AaxisAppBundle.php": "AaxisAppBundle.php", os.path.join("Resources", "config", "oro", "bundles.yml"):
              os.path.join("Resources", "config", "oro", "bundles.yml"), ".gitignore": "gitignore"}
    if os.path.isdir(base):
        wanted = {k: v for k, v in wanted.items() if k == ".gitignore"}
    return [(os.path.join(base, rel), os.path.join(TEMPLATES, "poc-bundle", src)) for rel, src in wanted.items()
            if not os.path.exists(os.path.join(base, rel))]


def installed(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read(), True
    except FileNotFoundError:
        return None, True
    except PermissionError:
        return None, False


def plan(project, data):
    """List of dicts: id, dest, status (ok|missing|differs|obsolete|poc), content, old, sudo."""
    rel = lambda path: os.path.relpath(path, project)  # noqa: E731
    out = []
    for iid, kind, dest, content, extra in items(project, data):
        old = read(dest)
        status = "ok" if old == content else "missing" if old is None else "differs"
        out.append({"id": iid, "dest": dest, "name": rel(dest), "status": status, "content": content, "old": old, "sudo": None})
        if kind == "sudo":
            inst, readable = installed(extra[0])
            if readable and inst != content:
                out.append({"id": iid + "-installed", "dest": extra[0], "name": extra[0], "status": "missing" if inst is None else "differs",
                            "content": content, "old": inst, "sudo": "sudo cp %s %s && %s" % (dest, extra[0], extra[1])})
    for rel_path in OBSOLETE:
        if os.path.exists(os.path.join(project, rel_path)):
            out.append({"id": "obsolete", "dest": os.path.join(project, rel_path), "name": rel_path, "status": "obsolete", "content": None, "old": read(os.path.join(project, rel_path)), "sudo": None})
    for dest, src in poc_missing(project):
        out.append({"id": "poc", "dest": dest, "name": rel(dest), "status": "poc", "content": read(src), "old": None, "sudo": None})
    return out


def backup(project, path):
    dst = os.path.join(project, BACKUPS)
    os.makedirs(dst, exist_ok=True)
    shutil.copy2(path, os.path.join(dst, "%s.%s" % (os.path.basename(path), time.strftime("%Y%m%d-%H%M%S"))))


def ensure_ignored(project, paths):
    """Never edit .gitignore: untracked local files go to .git/info/exclude when git does not already ignore them."""
    exclude = os.path.join(project, ".git", "info", "exclude")
    if not os.path.isdir(os.path.join(project, ".git")):
        return
    have = read(exclude) or ""
    add = []
    for rel_path in paths:
        if subprocess.run(["git", "-C", project, "check-ignore", "-q", rel_path]).returncode != 0:
            add.append("/" + rel_path)
    if add:
        os.makedirs(os.path.dirname(exclude), exist_ok=True)
        with open(exclude, "a", encoding="utf-8") as fh:
            fh.write(("" if have.endswith("\n") or not have else "\n") + "\n".join(add) + "\n")


def write(project, steps):
    done, sudo = [], []
    for s in steps:
        if s["status"] == "ok":
            continue
        if s["sudo"]:
            sudo.append(s["sudo"])
            continue
        if s["status"] == "obsolete":
            backup(project, s["dest"])
            os.remove(s["dest"])
            done.append("removed %s" % s["name"])
            continue
        if s["old"] is not None and s["dest"].startswith(project) and not s["dest"].startswith(os.path.join(project, STAGE)):
            backup(project, s["dest"])
        os.makedirs(os.path.dirname(s["dest"]), exist_ok=True)
        tmp = s["dest"] + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(s["content"])
        os.replace(tmp, s["dest"])
        done.append("wrote %s" % s["name"])
    ensure_ignored(project, [os.path.relpath(s["dest"], project) for s in steps if s["id"] in ("compose", "env-local", "env-behat_test", "env-test", "nginx", "supervisor") and s["dest"].startswith(project)])
    return done, sudo


def main(argv):
    if len(argv) != 3 or argv[0] not in ("check", "diff", "write") or argv[1] != "--project":
        sys.stderr.write(__doc__)
        return 64
    mode, project = argv[0], os.path.abspath(argv[2])
    path = env.new_path(project)
    if not os.path.exists(path):
        sys.stderr.write("env.yml missing at %s; run setup\n" % path)
        return 1
    data = env.with_defaults(env.load(path))
    errors = env.validate(data)
    if errors:
        sys.stderr.write("".join("error: %s\n" % e for e in errors))
        return 1
    try:
        steps = plan(project, data)
    except RenderError as exc:
        sys.stderr.write("render: %s\n" % exc)
        return 1
    drift = [s for s in steps if s["status"] != "ok"]
    if mode == "check":
        for s in drift:
            print("%s: %s%s" % (s["name"], {"differs": "differs from render", "missing": "missing", "obsolete": "obsolete, remove", "poc": "POC scratch bundle missing"}[s["status"]],
                                " (sudo)" if s["sudo"] else ""))
        return 2 if drift else 0
    if mode == "diff":
        for s in drift:
            if s["content"] is None:
                print("--- %s\n+++ /dev/null (obsolete: removed)" % s["name"])
                continue
            sys.stdout.writelines(difflib.unified_diff((s["old"] or "").splitlines(True), s["content"].splitlines(True), "a/" + s["name"], "b/" + s["name"]))
        return 0
    done, sudo = write(project, steps)
    for line in done:
        print(line)
    for cmd in sudo:
        print("SUDO-NEEDED: %s" % cmd)
    print("render: %d written, %d unchanged" % (len(done), len(steps) - len(drift)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
