"""Project root resolution shared by every aaxis-oro entry point that defaults to "the current project"."""
import os
import subprocess


def resolve(start=None):
    """Nearest ancestor holding .oro-ai/config.json, else the git toplevel, else `start` itself (default: cwd).

    A subdirectory of the project must resolve to the project, never to itself: callers create .oro-ai state under it.
    """
    here = os.path.abspath(start or os.getcwd())
    cur = here
    while True:
        if os.path.isfile(os.path.join(cur, ".oro-ai", "config.json")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    p = subprocess.run(["git", "-C", here, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    top = p.stdout.strip() if p.returncode == 0 else ""
    return os.path.abspath(top) if top else here


if __name__ == "__main__":
    print(resolve())
