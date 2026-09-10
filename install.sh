#!/usr/bin/env bash
# Installs (or updates) oro-skills into this machine's Claude Code skills directory.
# The repo checkout and the installed skills are kept separate: this script only
# ever creates symlinks under ~/.claude/skills pointing back at this checkout.
#
# Usage:
#   ./install.sh                 # update this checkout (git pull), then symlink all oro-* skills
#   ./install.sh --no-update     # skip git pull, just (re)symlink
#   ./install.sh --uninstall     # remove the symlinks this script created
#
# First-time install with SSH access to the repo:
#   git clone git@github.com:tabhan/oro-skills.git /opt/projects/oro-skills
#   /opt/projects/oro-skills/install.sh
#
# First-time install with a read-only HTTPS token instead of an SSH key
# (get the token from the repo owner):
#   ORO_SKILLS_TOKEN=<token> ./bootstrap.sh /opt/projects/oro-skills
#   /opt/projects/oro-skills/install.sh
#
# Updating later (SSH checkout): just re-run install.sh, no token needed.
# Updating later (HTTPS/token checkout): the token isn't stored in .git/config,
# so pass it again on update: ORO_SKILLS_TOKEN=<token> ./install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
TOKEN="${ORO_SKILLS_TOKEN:-${GITHUB_TOKEN:-}}"

git_auth_args=()
if [ -n "$TOKEN" ]; then
  # -c is per-invocation only -- never written to .git/config, so the token
  # isn't persisted on disk. Must be passed again on every future update.
  git_auth_args=(-c "http.extraHeader=Authorization: Basic $(printf 'x-access-token:%s' "$TOKEN" | base64 | tr -d '\n')")
fi

UPDATE=1
UNINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --no-update) UPDATE=0 ;;
    --uninstall) UNINSTALL=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

if [ "$UNINSTALL" -eq 1 ]; then
  echo "Removing oro-skills symlinks from $SKILLS_DEST"
  for skill in "$SCRIPT_DIR"/oro-*/; do
    name="$(basename "$skill")"
    link="$SKILLS_DEST/$name"
    if [ -L "$link" ] && [ "$(readlink -f "$link")" = "$(readlink -f "$skill")" ]; then
      rm "$link"
      echo "  removed $link"
    fi
  done
  exit 0
fi

if [ "$UPDATE" -eq 1 ] && [ -d "$SCRIPT_DIR/.git" ]; then
  echo "Updating checkout at $SCRIPT_DIR"
  origin="$(git -C "$SCRIPT_DIR" remote get-url origin 2>/dev/null || true)"
  if [ -z "$TOKEN" ] && [[ "$origin" == https://* ]]; then
    echo "  (origin is HTTPS ($origin) and no ORO_SKILLS_TOKEN/GITHUB_TOKEN is set --" >&2
    echo "   this pull will fail unless git already has cached credentials for it)" >&2
  fi
  git -C "$SCRIPT_DIR" "${git_auth_args[@]}" pull --ff-only
fi

mkdir -p "$SKILLS_DEST"

echo "Symlinking skills into $SKILLS_DEST"
for skill in "$SCRIPT_DIR"/oro-*/; do
  name="$(basename "$skill")"
  [ -f "$skill/SKILL.md" ] || continue
  ln -sfn "$skill" "$SKILLS_DEST/$name"
  echo "  $name -> $skill"
done

echo "Done. Start a new Claude Code session to pick up the skills."
