#!/usr/bin/env bash
# Transition shim. oro-skills is a Claude Code plugin (skills, agents and hooks come from
# the plugin). This script: removes the legacy ~/.claude/skills/oro-* and agent symlinks,
# keeps the atlas CLIs on PATH, then registers the self-hosted marketplace and installs the
# plugin. Marketplace source: ORO_SKILLS_MARKETPLACE (default git@github.com:tabhan/oro-skills.git).
#
# Usage:
#   ./install.sh                 # update this checkout (git pull), remove legacy symlinks, install the plugin, link CLIs
#   ./install.sh --no-update     # skip git pull
#   ./install.sh --project DIR   # project whose .claude/settings.local.json is cleaned of legacy atlas hooks (default: cwd)
#   ./install.sh --uninstall     # remove the CLI symlinks this script created
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
#
# This repo intentionally dropped its generic Oro/OroCommerce reference content
# in favor of the official oroinc/ai-dev-platform plugin suite (see README) --
# so by default this script also registers that marketplace and installs the
# official plugins covering the knowledge this repo used to duplicate.
#   ./install.sh --no-plugin             # skip marketplace add + plugin install (symlink cleanup + bins only)
#   ./install.sh --no-official-plugins   # skip that
#   ORO_SKILLS_OFFICIAL_PLUGINS="orocommerce-development orocommerce-review" ./install.sh
#     (override the default plugin list; orocommerce-orchestrator is NOT installed
#     by default since it duplicates the ai-sdlc-c1 flow some projects already use)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
AGENTS_DEST="${CLAUDE_AGENTS_DIR:-$HOME/.claude/agents}"
TOKEN="${ORO_SKILLS_TOKEN:-${GITHUB_TOKEN:-}}"
OFFICIAL_PLUGINS="${ORO_SKILLS_OFFICIAL_PLUGINS:-orocommerce-development orocommerce-review orocommerce-testing orocommerce-maintenance}"

git_auth_args=()
if [ -n "$TOKEN" ]; then
  # -c is per-invocation only -- never written to .git/config, so the token
  # isn't persisted on disk. Must be passed again on every future update.
  git_auth_args=(-c "http.extraHeader=Authorization: Basic $(printf 'x-access-token:%s' "$TOKEN" | base64 | tr -d '\n')")
fi

MARKETPLACE="${ORO_SKILLS_MARKETPLACE:-git@github.com:tabhan/oro-skills.git}"
INSTALL_PLUGIN=1
PROJECT_DIR="$PWD"
FAILED=()
UPDATE=1
UNINSTALL=0
INSTALL_OFFICIAL=1
while [ $# -gt 0 ]; do
  arg="$1"; shift
  case "$arg" in
    --project) PROJECT_DIR="$(cd "${1:?--project needs a directory}" && pwd)"; shift ;;
    --no-update) UPDATE=0 ;;
    --uninstall) UNINSTALL=1 ;;
    --no-official-plugins) INSTALL_OFFICIAL=0 ;;
    --no-plugin) INSTALL_PLUGIN=0 ;;
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
  for agent in "$SCRIPT_DIR"/oro-*/agents/*.md; do
    [ -f "$agent" ] || continue
    link="$AGENTS_DEST/$(basename "$agent")"
    if [ -L "$link" ] && [ "$(readlink -f "$link")" = "$(readlink -f "$agent")" ]; then
      rm "$link"
      echo "  removed $link"
    fi
  done
  for b in atlas atlas-build atlas-setup atlas-precommit; do
    link="${ORO_ATLAS_BIN_DIR:-$HOME/.local/bin}/$b"
    if [ -L "$link" ] && [ "$(readlink -f "$link")" = "$(readlink -f "$SCRIPT_DIR/oro-atlas/bin/$b")" ]; then
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

# Legacy symlinks would duplicate every skill and agent next to the plugin's copy.
echo "Removing legacy symlinks from $SKILLS_DEST and $AGENTS_DEST"
for skill in "$SCRIPT_DIR"/oro-*/; do
  link="$SKILLS_DEST/$(basename "$skill")"
  if [ -L "$link" ] && [ "$(readlink -f "$link")" = "$(readlink -f "$skill")" ]; then
    rm "$link"
    echo "  removed $link"
  fi
done
for agent in "$SCRIPT_DIR"/oro-*/agents/*.md; do
  [ -f "$agent" ] || continue
  link="$AGENTS_DEST/$(basename "$agent")"
  if [ -L "$link" ] && [ "$(readlink -f "$link")" = "$(readlink -f "$agent")" ]; then
    rm "$link"
    echo "  removed $link"
  fi
done

if [ "$INSTALL_PLUGIN" -eq 1 ]; then
  if command -v claude >/dev/null 2>&1; then
    echo "Registering oro-skills marketplace ($MARKETPLACE) and installing the plugin"
    claude plugin marketplace add "$MARKETPLACE" || echo "  (marketplace add failed or already present)" >&2
    claude plugin install oro-skills@oro-skills || FAILED+=("claude plugin install oro-skills@oro-skills")
  else
    echo "  (claude CLI not found: run 'claude plugin marketplace add $MARKETPLACE' and 'claude plugin install oro-skills@oro-skills' later)" >&2
  fi
fi

# oro-atlas ships a CLI; link it so agents can call `atlas` without an absolute path.
ATLAS_BIN_DIR="${ORO_ATLAS_BIN_DIR:-$HOME/.local/bin}"
if [ -x "$SCRIPT_DIR/oro-atlas/bin/atlas" ]; then
  mkdir -p "$ATLAS_BIN_DIR"
  for b in atlas atlas-build atlas-setup atlas-precommit; do
    [ -x "$SCRIPT_DIR/oro-atlas/bin/$b" ] || continue
    ln -sfn "$SCRIPT_DIR/oro-atlas/bin/$b" "$ATLAS_BIN_DIR/$b"
    echo "  $ATLAS_BIN_DIR/$b -> $SCRIPT_DIR/oro-atlas/bin/$b"
  done
  case ":$PATH:" in
    *":$ATLAS_BIN_DIR:"*) ;;
    *) echo "  (add $ATLAS_BIN_DIR to PATH, or call $SCRIPT_DIR/oro-atlas/bin/atlas directly)" >&2 ;;
  esac
fi

if [ "$INSTALL_OFFICIAL" -eq 1 ]; then
  if command -v claude >/dev/null 2>&1; then
    echo "Registering oroinc/ai-dev-platform marketplace"
    claude plugin marketplace add oroinc/ai-dev-platform || FAILED+=("claude plugin marketplace add oroinc/ai-dev-platform")
    for plugin in $OFFICIAL_PLUGINS; do
      echo "Installing $plugin@ai-dev-platform"
      claude plugin install "${plugin}@ai-dev-platform" -y || FAILED+=("claude plugin install ${plugin}@ai-dev-platform -y")
    done
  else
    echo "  (claude CLI not found on PATH -- skipping official oroinc/ai-dev-platform plugin install." >&2
    echo "   Install it yourself later: /plugin marketplace add oroinc/ai-dev-platform, then /plugin install <name>@ai-dev-platform)" >&2
  fi
fi

# Pre-plugin atlas hooks in the project's settings.local.json would fire a second time next to the plugin's.
if [ -f "$SCRIPT_DIR/oro-atlas/bin/atlas-setup" ] && [ -f "$PROJECT_DIR/.claude/settings.local.json" ] \
   && grep -q "oro-atlas" "$PROJECT_DIR/.claude/settings.local.json"; then
  echo "Cleaning legacy atlas hooks from $PROJECT_DIR/.claude/settings.local.json"
  python3 "$SCRIPT_DIR/oro-atlas/bin/atlas-setup" --cleanup-only "$PROJECT_DIR" \
    || FAILED+=("python3 $SCRIPT_DIR/oro-atlas/bin/atlas-setup --cleanup-only $PROJECT_DIR")
fi

if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "Done with failures; re-run these by hand:" >&2
  printf '  %s\n' "${FAILED[@]}" >&2
  exit 1
fi
echo "Done. Start a new Claude Code session to pick up the plugins."
