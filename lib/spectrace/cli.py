import argparse
import os
import subprocess
import sys

from . import coverage, model, report

HELP = """usage: aaxis-oro spec <coverage|report> [options]

  coverage [--root DIR] [--spec-dir D] [--tests D] [--ids A,B] [-v]
      static: every active AC has >=1 tagged e2e/functional test; unit-only, wrong-layer and orphan tags fail
  report   [--root DIR] [--e2e results.json] [--junit phpunit.xml ...] [--groups-xml list-tests.xml]
           [--sha SHA] [--ids A,B] [--out report.md]
      verification from a real run (default: latest <root>/var/e2e-results/<ts>/results.json); AC verified only
      if >=1 carrier ran and all passed
Exit: 0 ok, 1 gaps or failures, 64 usage.
"""


def paths(a):
    root = os.path.abspath(a.root)
    return root, a.spec_dir or os.path.join(root, "spec"), getattr(a, "tests", None) or os.path.join(root, "src")


def parser(prog):
    p = argparse.ArgumentParser(prog=prog, add_help=False)
    p.add_argument("--root", default=".")
    p.add_argument("--spec-dir")
    p.add_argument("--ids")
    return p


def run_coverage(argv):
    p = parser("coverage")
    p.add_argument("--tests")
    p.add_argument("-v", action="store_true")
    a = p.parse_args(argv)
    _, spec_dir, tests = paths(a)
    ids = set(a.ids.split(",")) if a.ids else None
    specs = model.load_specs(spec_dir, ids)
    tags = {k: v for k, v in model.scan_tags(tests).items() if not ids or k[0] in ids}
    problems, rows = coverage.check(specs, tags)
    if a.v:
        print("\n".join("%-28s %-11s %s" % r for r in rows))
    print("\n".join(problems))
    print("spec coverage: %d AC, %d problem(s)" % (len(rows), len(problems)))
    return 1 if problems else 0


def sha_of(root):
    r = subprocess.run(["git", "-C", root, "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def run_report(argv):
    p = parser("report")
    p.add_argument("--e2e")
    p.add_argument("--junit", action="append", default=[])
    p.add_argument("--groups-xml")
    p.add_argument("--sha")
    p.add_argument("--out")
    a = p.parse_args(argv)
    root, spec_dir, _ = paths(a)
    e2e = a.e2e
    if not e2e and not a.junit:
        run = report.latest_run(os.path.join(root, "var", "e2e-results"))
        e2e = os.path.join(run, "results.json") if run else None
    if not e2e and not a.junit:
        sys.stderr.write("spec report: no results found (pass --e2e / --junit)\n")
        return 64
    results = report.playwright(e2e) if e2e else []
    groups = report.groups_map(a.groups_xml) if a.groups_xml else {}
    for j in a.junit:
        results += report.phpunit(j, groups)
    specs = model.load_specs(spec_dir, set(a.ids.split(",")) if a.ids else None)
    rows, bad = report.evaluate(specs, results)
    md = report.render(rows, a.sha or sha_of(root), " ".join([e2e or ""] + a.junit).strip())
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(md)
        print("\n".join("%s %s" % (r[0], r[2]) for r in rows if r[2] != "verified"))
        print("spec report: %d/%d verified -> %s" % (len(rows) - bad, len(rows), a.out))
    else:
        sys.stdout.write(md)
    return 1 if bad else 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        sys.stdout.write(HELP)
        return 0
    cmds = {"coverage": run_coverage, "report": run_report}
    if argv[0] not in cmds:
        sys.stderr.write(HELP)
        return 64
    try:
        return cmds[argv[0]](argv[1:])
    except SystemExit:
        return 64
    except (OSError, ValueError, KeyError) as e:
        sys.stderr.write("spec %s: %s\n" % (argv[0], e))
        return 64
