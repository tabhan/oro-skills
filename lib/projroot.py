"""Oro application root detection shared by every aaxis-oro entry point that defaults to "the current project".

The root is recognised by the fixed layout of an Oro application, never by where `.oro-ai/` happens to exist, so a
stray `.oro-ai/` in a subdirectory can neither be taken as the root nor be created there.
"""
import os
import sys

USAGE_EXIT = 64


class NotOroProject(Exception):
    """No Oro application root where one is required (cwd outside a project, or an invalid --project)."""


def is_root(path):
    """True when `path` has the Oro application layout: `bin/console` next to `composer.lock`.

    Both are fixed by the Oro application skeleton and exist in a fresh checkout before `composer install`, in git
    worktrees, and nowhere below the root (src/, vendor/oro/*, public/ carry neither).
    """
    return os.path.isfile(os.path.join(path, "bin", "console")) and os.path.isfile(os.path.join(path, "composer.lock"))


def find(start=None):
    """Nearest ancestor of `start` (default: cwd; a file counts as its directory) that is an Oro root, else None."""
    cur = os.path.abspath(start or os.getcwd())
    if not os.path.isdir(cur):
        cur = os.path.dirname(cur)
    found = None
    while found is None:
        if is_root(cur):
            found = cur
        elif os.path.dirname(cur) == cur:
            break
        else:
            cur = os.path.dirname(cur)
    return found


def require(explicit=None, start=None):
    """The Oro root: `explicit` (must itself be a root) or the nearest root above `start`/cwd; raises NotOroProject."""
    if explicit:
        root = os.path.abspath(explicit)
        if not is_root(root):
            raise NotOroProject("--project %s is not an Oro application root (need bin/console and composer.lock)" % explicit)
    else:
        root = find(start)
        if root is None:
            raise NotOroProject("no Oro project found from %s (need bin/console and composer.lock); "
                                "cd into one or pass --project" % os.path.abspath(start or os.getcwd()))
    return root


def main(argv):
    """`projroot.py [--project P]`: print the root, or the error on stderr with exit 64."""
    explicit = argv[1] if len(argv) >= 2 and argv[0] == "--project" else None
    code = 0
    try:
        print(require(explicit))
    except NotOroProject as exc:
        sys.stderr.write("aaxis-oro: %s\n" % exc)
        code = USAGE_EXIT
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
