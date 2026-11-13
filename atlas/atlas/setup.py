"""Per-project atlas setup: legacy hook cleanup, then an explicit index build."""
import json
import os
import subprocess
import sys

from . import build, legacy

GIT_HOOKS = ("post-checkout", "post-merge", "post-rewrite")
MARK = "# oro-atlas: refresh index"


def remove_git_hooks(project):
    """Earlier versions installed background-refresh git hooks; atlas never rebuilds on its own now. Foreign hooks stay."""
    p = subprocess.run(["git", "-C", project, "rev-parse", "--git-path", "hooks"], capture_output=True, text=True)
    notes = []
    for name in GIT_HOOKS if p.returncode == 0 else ():
        path = os.path.join(project, p.stdout.strip(), name)
        if os.path.isfile(path) and MARK in open(path, encoding="utf-8", errors="replace").read():
            os.remove(path)
            notes.append("git hook %s: removed (atlas no longer rebuilds automatically)" % name)
    return notes


def main(argv):
    args = [x for x in argv if not x.startswith("--")]
    project = os.path.abspath(args[0]) if args else ""
    cleanup_only = "--cleanup-only" in argv
    if not cleanup_only and not os.path.isfile(os.path.join(project, "bin", "console")):
        sys.stderr.write("usage: aaxis-oro atlas setup [--cleanup-only] [--no-build] <oro-project-root>\n")
        return 2
    if legacy.cleanup(project):
        print("removed legacy atlas hooks from %s (the aaxis-oro plugin provides them)" % legacy.settings_path(project))
    if cleanup_only:
        return 0
    for note in remove_git_hooks(project):
        print(note)
    return 0 if "--no-build" in argv else build.main(["--project", project])
