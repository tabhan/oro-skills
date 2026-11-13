#!/usr/bin/env python3
# oro: ">=7.0.0"
"""Node and PHP resolution helpers for check/repair.

  nodephp.py php-require <project>             print composer.json require.php
  nodephp.py php-ok <constraint> <version>     exit 0 when the version satisfies the composer constraint
  nodephp.py node-paths <parameters.yml>       print the oro_asset.{nodejs,npm,pnpm}_path values, one per line
  nodephp.py set-node <parameters.yml> <bin>   point the three paths at <bin>/{node,npm,pnpm} (adds missing keys)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "lib"))

from oroversion import constraint  # noqa: E402

KEYS = (("nodejs_path", "node"), ("npm_path", "npm"), ("pnpm_path", "pnpm"))


def main(argv):
    cmd, rest = (argv[0], argv[1:]) if argv else ("", [])
    if cmd == "php-require" and len(rest) == 1:
        with open(os.path.join(rest[0], "composer.json"), encoding="utf-8") as fh:
            print(json.load(fh).get("require", {}).get("php", ""))
        return 0
    if cmd == "php-ok" and len(rest) == 2:
        return 0 if constraint.parse_constraint(rest[0]).matches(rest[1]) else 1
    if cmd == "node-paths" and len(rest) == 1:
        text = open(rest[0], encoding="utf-8").read()
        for key, _ in KEYS:
            m = re.search(r"^\s*oro_asset\.%s:\s*(\S+)" % key, text, re.M)
            print(m.group(1) if m else "")
        return 0
    if cmd == "set-node" and len(rest) == 2:
        path, bindir = rest
        text = open(path, encoding="utf-8").read()
        for key, binary in KEYS:
            line = "oro_asset.%s: %s/%s" % (key, bindir.rstrip("/"), binary)
            if re.search(r"^\s*oro_asset\.%s:" % key, text, re.M):
                text = re.sub(r"^(\s*)oro_asset\.%s:.*$" % key, lambda m: m.group(1) + line, text, flags=re.M)
            else:
                text = re.sub(r"^(parameters:\s*\n)", lambda m: m.group(1) + "    " + line + "\n", text, count=1, flags=re.M)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
        return 0
    sys.stderr.write(__doc__)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
