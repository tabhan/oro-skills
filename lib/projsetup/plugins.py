"""Enable the Oro plugins per project in .claude/settings.local.json (they are disabled globally)."""
import json
import os
import subprocess

PLUGIN_KEYS = (
    "aaxis-oro@aaxis-oro",
    "orocommerce-development@ai-dev-platform",
    "orocommerce-foundation@ai-dev-platform",
    "orocommerce-discovery@ai-dev-platform",
    "orocommerce-testing@ai-dev-platform",
    "orocommerce-review@ai-dev-platform",
    "orocommerce-maintenance@ai-dev-platform",
)
REL = os.path.join(".claude", "settings.local.json")


def _git(root, *args):
    try:
        return subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True)
    except OSError:
        return None


def ensure_excluded(root, dry):
    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    if inside is None or inside.returncode != 0:
        return None
    if _git(root, "check-ignore", "-q", REL).returncode == 0:
        return None
    if dry:
        return "%s: would add to .git/info/exclude" % REL
    path = _git(root, "rev-parse", "--path-format=absolute", "--git-path", "info/exclude").stdout.strip()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, encoding="utf-8") as fh:
            cur = fh.read()
    except OSError:
        cur = ""
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(("" if not cur or cur.endswith("\n") else "\n") + ".claude/settings.local.json\n")
    return "%s: added to .git/info/exclude" % REL


def sync(root, dry):
    """Merge PLUGIN_KEYS=true into enabledPlugins. Returns output lines."""
    path = os.path.join(root, REL)
    data, lines = {}, []
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return ["warning: %s is not valid JSON; plugins not enabled, left untouched" % REL]
        if not isinstance(data, dict) or not isinstance(data.get("enabledPlugins", {}), dict):
            return ["warning: %s has an unexpected shape; plugins not enabled, left untouched" % REL]
    enabled = data.setdefault("enabledPlugins", {})
    added = []
    for key in PLUGIN_KEYS:
        if enabled.get(key) is False:
            lines.append("warning: %s is false in %s (opted out); left as is" % (key, REL))
        elif enabled.get(key) is not True:
            enabled[key] = True
            added.append(key)
    if added:
        if not dry:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(data, indent=2) + "\n")
        lines.insert(0, "%s: enabled %d plugins" % (REL, len(added)))
    else:
        lines.insert(0, "%s: plugins unchanged" % REL)
    ex = ensure_excluded(root, dry)
    return lines + ([ex] if ex else [])
