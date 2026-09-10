#!/usr/bin/env bash
# One-time clone for people who have a read-only HTTPS token instead of SSH
# access to this repo. Not needed if you can `git clone git@github.com:...`.
#
# Usage:
#   ORO_SKILLS_TOKEN=<token> ./bootstrap.sh [target-dir]
#
# The token is only used for this clone -- it is passed via a one-off `git -c`
# header, so it is never written into the resulting checkout's .git/config.
# You'll need to pass it again on future updates: see install.sh's header.

set -euo pipefail

REPO_URL="${ORO_SKILLS_REPO_URL:-https://github.com/tabhan/oro-skills.git}"
TARGET_DIR="${1:-oro-skills}"
TOKEN="${ORO_SKILLS_TOKEN:-${GITHUB_TOKEN:-}}"

if [ -z "$TOKEN" ]; then
  echo "Set ORO_SKILLS_TOKEN (or GITHUB_TOKEN) to a read-only token for this repo first." >&2
  exit 1
fi

git -c "http.extraHeader=Authorization: Basic $(printf 'x-access-token:%s' "$TOKEN" | base64 | tr -d '\n')" \
  clone "$REPO_URL" "$TARGET_DIR"

echo "Cloned into $TARGET_DIR. Now run: $TARGET_DIR/install.sh"
