"""AC verification report from a real run: Playwright results.json plus PHPUnit JUnit."""
import json
import os
import re
import xml.etree.ElementTree as ET

from . import model

TAG = re.compile(r"^@?" + model.TAG.pattern + r"$")


def playwright(path):
    """Return [(spec_id, ac_num, 'passed'|'failed'|'skipped', title)]."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = []

    def walk(suite):
        for sp in suite.get("specs", []):
            states = [t.get("status") for t in sp.get("tests", [])]
            state = "skipped" if states and all(s == "skipped" for s in states) else ("passed" if sp.get("ok") else "failed")
            for tag in sp.get("tags", []):
                m = TAG.match(tag)
                if m:
                    out.append((m.group(1), m.group(2), state, sp.get("title", ""), "e2e"))
        for child in suite.get("suites", []):
            walk(child)
    for s in data.get("suites", []):
        walk(s)
    return out


def groups_map(path):
    """phpunit --list-tests-xml output: {'Class::method': [groups]}."""
    m = {}
    for el in ET.parse(path).getroot().iter("testCaseMethod"):
        m[el.get("id", "").split("#")[0]] = [g.strip() for g in el.get("groups", "").split(",")]
    return m


def phpunit(junit, groups):
    out = []
    for tc in ET.parse(junit).getroot().iter("testcase"):
        cls, name = tc.get("class") or tc.get("classname", ""), re.split(r" with data set|#", tc.get("name", ""))[0]
        state = "failed" if tc.find("failure") is not None or tc.find("error") is not None else (
            "skipped" if tc.find("skipped") is not None else "passed")
        grp = groups.get("%s::%s" % (cls, name), [])
        grp += [g.get("value", "") for g in tc.iter("group")]
        for g in grp:
            m = TAG.match(g)
            if m:
                out.append((m.group(1), m.group(2), state, "%s::%s" % (cls, name), model.kind_of(tc.get("file") or cls)))
    return out


def evaluate(specs, results):
    rows, bad = [], 0
    for s in specs:
        for ac in s.acs:
            if ac.retired:
                continue
            mine = [r for r in results if (r[0], r[1]) == (s.id, ac.num) and r[4] in ("e2e", "functional")]
            ran = [r for r in mine if r[2] != "skipped"]
            status = "failed" if any(r[2] == "failed" for r in ran) else ("verified" if ran else "not run")
            bad += status != "verified"
            rows.append((ac.key, ac.title, status, "%d/%d" % (sum(r[2] == "passed" for r in ran), len(mine))))
    return rows, bad


def render(rows, sha, source):
    lines = ["# AC verification report", "", "Commit: `%s`  " % sha, "Run: `%s`" % source, "",
             "| AC | Title | Status | Passed carriers |", "|---|---|---|---|"]
    lines += ["| %s | %s | %s | %s |" % r for r in rows]
    return "\n".join(lines) + "\n"


def latest_run(results_root):
    runs = sorted(d for d in os.listdir(results_root) if os.path.isdir(os.path.join(results_root, d))) if os.path.isdir(results_root) else []
    return os.path.join(results_root, runs[-1]) if runs else None
