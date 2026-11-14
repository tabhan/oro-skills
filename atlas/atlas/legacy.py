"""Legacy atlas hook entries in Claude Code settings files (the plugin's hooks/hooks.json replaced them)."""
import json
import os
import shutil

# Every filename the pre-plugin install could have registered; oro-atlas/hooks/ keeps a shim for each.
SCRIPTS = ("pretooluse_edit.py", "pretooluse_bash.py", "posttooluse_edit.py", "posttooluse_bash.py", "userpromptsubmit.py",
           "subagentstart.py", "stop.py", "sessionstart_atlas.py", "sessionstart_legacy.py", "sessionstart_migrate.py",
           "sessionstart_version.py")


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


def settings_files(project, home=None):
    home = home or os.path.expanduser("~")
    paths = [os.path.join(d, ".claude", n) for d in (project, home) for n in ("settings.local.json", "settings.json")]
    return list(dict.fromkeys(os.path.abspath(p) for p in paths))


def load_file(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def load(project):
    return load_file(settings_path(project))


def project_has_legacy(project):
    data = load(project)
    return bool(data) and has_legacy(data)


def clean_file(path):
    """Rewrite one settings file without legacy atlas hooks; True when it changed. Missing/invalid files are skipped."""
    data = load_file(path)
    if not isinstance(data, dict) or not has_legacy(data):
        return False
    target = os.path.realpath(path)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(remove_legacy(data), fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    shutil.copymode(target, tmp)
    os.replace(tmp, target)
    return True


def cleanup(project):
    return clean_file(settings_path(project))


def cleanup_all(project, home=None):
    """Clean project and user-level settings files; returns the paths that changed. One bad file never stops the rest."""
    changed = []
    for path in settings_files(project, home):
        try:
            if clean_file(path):
                changed.append(path)
        except (OSError, AttributeError, TypeError):
            pass
    return changed
