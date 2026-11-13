"""Implementations behind `aaxis-oro version` (version, diff, applies) and `aaxis-oro dev lint`."""
import argparse
import json
import os
import sys

from . import ConstraintError, detect, parse_version
from . import diff as D
from . import lint
from . import resolve as R

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", ".."))
VERSION_DOC = """Print the Oro version of a project (from composer.lock). Exit 0 known, 4 unknown, 64 usage.

`aaxis-oro version diff --from 7.0.5 --to 8.0.0` lists guidance units that activate/deactivate between two versions;
`aaxis-oro version applies ...` tells which guidance applies to the project."""

APPLIES_DOC = """Which version-scoped guidance applies to this project's Oro version.

  applies [--project P] [-v] [--json] <path-or-topic>...   exit 0 all apply, 1 some out of range, 4 version unknown
  applies [--project P] --list-active <dir>                files that apply (+ inactive line spans to skip)
  applies [--project P] --list-inactive <dir>              units that do not apply
  applies [--project P] --check <id> [--registry FILE]     hook check gate: run|warn|skip
Exit 64 on usage errors, 4 when the version is unknown (policy: docs/VERSIONING.md)."""

LINT_DOC = """Lint version-scoped guidance: parsable ranges, balanced markers, topic ids, adjoining ranges per topic.

  dev lint [--root DIR] [PATH...]    exit 0 clean, 1 violations, 64 usage"""


def diff_main(argv):
    ap = argparse.ArgumentParser(prog="aaxis-oro version diff", description="List guidance units that activate or deactivate between two Oro versions.")
    ap.add_argument("--from", dest="v_from", required=True)
    ap.add_argument("--to", dest="v_to", required=True)
    ap.add_argument("--root", default=ROOT, help="tree to scan (default: the plugin)")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
        rows = D.diff(os.path.abspath(a.root), parse_version(a.v_from), parse_version(a.v_to))
    except SystemExit as exc:
        return 64 if exc.code else 0
    except ConstraintError as exc:
        sys.stderr.write("aaxis-oro version diff: %s\n" % exc)
        return 64
    print(json.dumps(rows, indent=2) if a.json else D.format_table(rows))
    return 0


def version_main(argv):
    if argv[:1] == ["diff"]:
        return diff_main(argv[1:])
    if argv[:1] == ["applies"]:
        return applies_main(argv[1:])
    ap = argparse.ArgumentParser(prog="aaxis-oro version", description=VERSION_DOC)
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-cache", action="store_true", help="ignore and do not write .oro-ai/version.json")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    r = detect(os.path.abspath(args.project), use_cache=not args.no_cache, write_cache=not args.no_cache)
    if args.json:
        print(json.dumps(r.as_dict(), indent=2))
    elif r.known:
        print(r.version)
    else:
        sys.stderr.write("aaxis-oro version: unknown (%s)\n" % r.reason)
    for w in r.warnings:
        sys.stderr.write("aaxis-oro version: warning: %s\n" % w)
    return 0 if r.known else 4



UNKNOWN_LINE = "Oro version unknown; only version-neutral rules are active, version-specific rules are inactive (advisory)"


def applies_main(argv):
    ap = argparse.ArgumentParser(prog="aaxis-oro version applies", description=APPLIES_DOC, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*")
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--root", default=ROOT, help="where topics are searched (default: the plugin)")
    ap.add_argument("--list-active", metavar="DIR")
    ap.add_argument("--list-inactive", metavar="DIR")
    ap.add_argument("--check", metavar="ID")
    ap.add_argument("--registry", default=os.path.join(ROOT, "atlas", "hooks", "checks.yml"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    modes = [bool(a.targets), bool(a.list_active), bool(a.list_inactive), bool(a.check)]
    if sum(modes) != 1:
        sys.stderr.write("aaxis-oro version applies: give exactly one of <path-or-topic>..., --list-active, --list-inactive, --check\n")
        return 64
    det = detect(os.path.abspath(a.project))
    version = det.version
    unknown = version is None
    if unknown:
        sys.stderr.write("aaxis-oro version applies: %s (%s)\n" % (UNKNOWN_LINE, det.reason))
    warnings = []
    try:
        if a.check:
            d = R.check_decision(R.load_registry(a.registry), a.check, version)
            verdict = "skip" if not d["run"] else ("warn" if d["severity"] == "warn" else "run")
            print(json.dumps(dict(d, verdict=verdict)) if a.json else "%s  %s" % (verdict, d["reason"]))
            return 4 if unknown else (0 if d["run"] else 1)
        if a.list_active or a.list_inactive:
            target = a.list_active or a.list_inactive
            if not os.path.exists(target):
                sys.stderr.write("aaxis-oro version applies: no such path %s\n" % target)
                return 64
            if a.list_active:
                files = R.active_files(target, version, warnings)
                if a.json:
                    print(json.dumps({"version": str(version) if version else None, "files": {k: v for k, v in files.items()}}))
                for path, skips in ([] if a.json else files.items()):
                    print(path + ("  [skip lines: %s]" % ", ".join("%d-%d" % s for s in skips) if skips else ""))
            else:
                rows = [(u, s) for u, s in R.resolve(target, version, warnings=warnings) if s == R.INACTIVE]
                print(json.dumps([u.as_dict(s) for u, s in rows]) if a.json else "\n".join("%s  oro %s" % (u.ref(), u.effective_range) for u, s in rows))
            for w in warnings:
                sys.stderr.write("aaxis-oro version applies: warning: %s\n" % w)
            return 4 if unknown else 0
        collected = []
        for t in a.targets:
            if os.path.exists(t):
                collected += R.resolve(t, version, warnings=warnings)
            else:
                found = R.find_topic(t, a.root, version)
                if not found:
                    sys.stderr.write("aaxis-oro version applies: %r is neither an existing path nor a known topic\n" % t)
                    return 64
                collected += found
    except ConstraintError as exc:
        sys.stderr.write("aaxis-oro version applies: bad oro range: %s\n" % exc)
        return 64
    for w in warnings:
        sys.stderr.write("aaxis-oro version applies: warning: %s\n" % w)
    out_of_range = [(u, s) for u, s in collected if s == R.INACTIVE]
    if a.json:
        print(json.dumps([u.as_dict(s) for u, s in collected]))
    else:
        for u, s in collected:
            if a.verbose or s != R.ACTIVE:
                print("%-8s %s  oro %s" % (s, u.ref(), u.effective_range))
    if unknown:
        return 4
    return 1 if out_of_range else 0



def lint_main(argv):
    ap = argparse.ArgumentParser(prog="aaxis-oro dev lint", description=LINT_DOC, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--root", default=ROOT)
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    root = os.path.abspath(a.root)
    missing = [p for p in a.paths if not os.path.exists(p)]
    if missing:
        sys.stderr.write("aaxis-oro dev lint: no such path %s\n" % ", ".join(missing))
        return 64
    problems, warns = lint.lint_all(root, [os.path.abspath(p) for p in a.paths] or None)
    for w in warns:
        sys.stderr.write("warning: %s\n" % w)
    for p in problems:
        print(p)
    if problems:
        sys.stderr.write("aaxis-oro dev lint: %d violation(s)\n" % len(problems))
    return 1 if problems else 0

