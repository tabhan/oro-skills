#!/usr/bin/env bash
# Installs (or updates) oro-skills into this machine's Claude Code skills directory.
# The repo checkout and the installed skills are kept separate: this script only
# ever creates symlinks under ~/.claude/skills pointing back at this checkout.
#
# Usage:
#   ./install.sh                 # clone/update this repo in place, then symlink all oro-* skills
#   ./install.sh --no-update     # skip git pull, just (re)symlink
#   ./install.sh --uninstall     # remove the symlinks this script created
#   REPO_URL=... TARGET_DIR=... ./install.sh   # first-time install from scratch (see below)
#
# First-time install on a machine that doesn't have the repo yet:
#   git clone git@github.com:tabhan/oro-skills.git /opt/projects/oro-skills
#   /opt/projects/oro-skills/install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

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
  git -C "$SCRIPT_DIR" pull --ff-only
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
