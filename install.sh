#!/usr/bin/env bash
# Transition shim. aaxis-oro is a Claude Code plugin (skills, agents and hooks come from
# the plugin). This script: removes the legacy ~/.claude/skills/oro-* and agent symlinks and the old atlas CLI
# links, keeps `aaxis-oro` on PATH, then registers the self-hosted marketplace and installs the plugin. Marketplace source: ORO_SKILLS_MARKETPLACE (default git@github.com:tabhan/oro-skills.git).
#
# Usage:
#   ./install.sh                 # update this checkout (git pull), remove legacy symlinks, install the plugin, link CLIs
#   ./install.sh --no-update     # skip git pull
#   ./install.sh --project DIR   # project whose .claude/settings.local.json is cleaned of legacy atlas hooks (default: cwd)
#   ./install.sh --uninstall     # remove the CLI symlink this script created
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

# Symlinks in $1 named $2 that point into this checkout (even when the target no longer exists) are legacy.
remove_legacy_links() {
  local dir="$1" pattern="$2" link target
  for link in "$dir"/$pattern; do
    [ -L "$link" ] || continue
    target="$(readlink -f "$link")"
    case "$target" in "$SCRIPT_DIR"/*) rm "$link"; echo "  removed $link" ;; esac
  done
}

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

# Lint pre-commit for contributors; CI stays the authoritative gate. Skipped when not a git checkout.
if [ -d "$SCRIPT_DIR/.git" ] && [ "$(git -C "$SCRIPT_DIR" config --get core.hooksPath || true)" != ".githooks" ]; then
  git -C "$SCRIPT_DIR" config core.hooksPath .githooks
fi

if [ "$UNINSTALL" -eq 1 ]; then
  echo "Removing aaxis-oro links"
  remove_legacy_links "$SKILLS_DEST" 'oro-*'
  remove_legacy_links "$AGENTS_DEST" 'oro-*.md'
  remove_legacy_links "${ORO_ATLAS_BIN_DIR:-$HOME/.local/bin}" '*'
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
remove_legacy_links "$SKILLS_DEST" 'oro-*'
remove_legacy_links "$AGENTS_DEST" 'oro-*.md'

if [ "$INSTALL_PLUGIN" -eq 1 ]; then
  if command -v claude >/dev/null 2>&1; then
    echo "Registering aaxis-oro marketplace ($MARKETPLACE) and installing the plugin"
    claude plugin marketplace add "$MARKETPLACE" || echo "  (marketplace add failed or already present)" >&2
    claude plugin install aaxis-oro@aaxis-oro || FAILED+=("claude plugin install aaxis-oro@aaxis-oro")
  else
    echo "  (claude CLI not found: run 'claude plugin marketplace add $MARKETPLACE' and 'claude plugin install aaxis-oro@aaxis-oro' later)" >&2
  fi
fi

# One CLI: link it so agents and shells can call `aaxis-oro` without an absolute path.
CLI_BIN_DIR="${ORO_ATLAS_BIN_DIR:-$HOME/.local/bin}"
mkdir -p "$CLI_BIN_DIR"
remove_legacy_links "$CLI_BIN_DIR" 'atlas*'
remove_legacy_links "$CLI_BIN_DIR" 'oro-*'
ln -sfn "$SCRIPT_DIR/bin/aaxis-oro" "$CLI_BIN_DIR/aaxis-oro"
echo "  $CLI_BIN_DIR/aaxis-oro -> $SCRIPT_DIR/bin/aaxis-oro"
case ":$PATH:" in
  *":$CLI_BIN_DIR:"*) ;;
  *) echo "  (add $CLI_BIN_DIR to PATH, or call $SCRIPT_DIR/bin/aaxis-oro directly)" >&2 ;;
esac

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
if [ -f "$PROJECT_DIR/.claude/settings.local.json" ] && grep -q "oro-atlas" "$PROJECT_DIR/.claude/settings.local.json"; then
  echo "Cleaning legacy atlas hooks from $PROJECT_DIR/.claude/settings.local.json"
  python3 "$SCRIPT_DIR/bin/aaxis-oro" atlas setup --cleanup-only "$PROJECT_DIR" \
    || FAILED+=("python3 $SCRIPT_DIR/bin/aaxis-oro atlas setup --cleanup-only $PROJECT_DIR")
fi

if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "Done with failures; re-run these by hand:" >&2
  printf '  %s\n' "${FAILED[@]}" >&2
  exit 1
fi
echo "Done. Start a new Claude Code session to pick up the plugins."
