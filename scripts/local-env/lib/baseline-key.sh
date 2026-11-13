#!/usr/bin/env bash
# oro: ">=7.0.0"
# Prints sha256(composer.lock + every Migrations/DataFixtures dir under src/ and vendor/, path+content). Usage: baseline-key.sh <project>
cd "${1:?project}" || exit 64
{ sha256sum composer.lock | cut -d' ' -f1
  find src vendor -type d \( -name Migrations -o -name DataFixtures \) -not -path '*/Tests/*' -not -path '*/node_modules/*' 2>/dev/null | sort | while read -r d; do
    find "$d" -type f | sort | xargs sha256sum
  done
} | sha256sum | cut -d' ' -f1
