"""Legacy atlas hook entries in <project>/.claude/settings.local.json (the plugin's hooks/hooks.json replaced them)."""
import json
import os

SCRIPTS = ("pretooluse_edit.py", "posttooluse_bash.py", "posttooluse_edit.py", "userpromptsubmit.py", "subagentstart.py")


def is_legacy(command):
    return "oro-atlas" in command and any(s in command for s in SCRIPTS)


def has_legacy(settings):
    return any(is_legacy(h.get("command", "")) for groups in settings.get("hooks", {}).values()
               for g in groups for h in g.get("hooks", []))


def remove_legacy(settings):
    """Drop only the entries is_legacy() matches; everything else in the file is left untouched."""
    hooks = settings.get("hooks", {})
    for event in list(hooks):
        kept = []
        for group in hooks[event]:
            group["hooks"] = [h for h in group.get("hooks", []) if not is_legacy(h.get("command", ""))]
            if group["hooks"]:
                kept.append(group)
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if "hooks" in settings and not settings["hooks"]:
        del settings["hooks"]
    return settings


def settings_path(project):
    return os.path.join(project, ".claude", "settings.local.json")


def load(project):
    try:
        with open(settings_path(project), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def project_has_legacy(project):
    data = load(project)
    return bool(data) and has_legacy(data)


def cleanup(project):
    """Rewrite settings.local.json without legacy atlas hooks; True when the file changed."""
    data = load(project)
    if not data or not has_legacy(data):
        return False
    path = settings_path(project)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(remove_legacy(data), fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return True
