"""Project discovery, build context and PHP class location helpers."""
import hashlib
import json
import os
import re
import subprocess

OUT_SUBDIR = os.path.join("var", "atlas")


class AtlasError(Exception):
    """Expected, user-facing failure (bad project, php failure, missing shard)."""


class MissingShard(AtlasError):
    pass


def find_project_root(start=None):
    """Walk up from `start` until a dir holding composer.lock and bin/console."""
    cur = os.path.abspath(start or os.getcwd())
    found = None
    while found is None:
        if os.path.isfile(os.path.join(cur, "composer.lock")) and os.path.isfile(
            os.path.join(cur, "bin", "console")
        ):
            found = cur
        else:
            parent = os.path.dirname(cur)
            if parent == cur:
                raise AtlasError(
                    "no Oro project found (need composer.lock + bin/console); use --project"
                )
            cur = parent
    return found


def read_text(path):
    """File text, or "" when missing/unreadable so one bad file never aborts a shard."""
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            text = fh.read()
    except (OSError, TypeError, ValueError):
        text = ""
    return text


def strip_comment(text):
    """Drop a trailing YAML `# comment`; a quote only opens at a token start, so `don't` stays text."""
    quote, i, end = None, 0, len(text)
    while i < end:
        ch = text[i]
        if quote and ch == "\\" and quote == '"':
            i += 1  # skip the escaped character
        elif quote and text.startswith("''", i) and quote == "'":
            i += 1  # '' is an escaped quote inside a single-quoted scalar
        elif quote:
            quote = None if ch == quote else quote
        elif ch in "\"'" and (i == 0 or text[i - 1] in " \t[{,:-"):
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            end = i
        i += 1
    return text[:end]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_php_json(root, args, timeout=900):
    """Run `php bin/console ...` and parse its stdout as JSON."""
    cmd = ["php", "bin/console"] + args
    proc = subprocess.run(
        cmd, cwd=root, capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise AtlasError("%s failed (%d): %s" % (" ".join(cmd), proc.returncode, proc.stderr[-500:]))
    try:
        return json.loads(proc.stdout)
    except ValueError as exc:
        raise AtlasError("%s did not return JSON: %s" % (" ".join(cmd), exc))


_PSR4_RE = re.compile(r"'((?:[^'\\]|\\\\)+)'\s*=>\s*array\((.*?)\),", re.S)
_PATH_RE = re.compile(r"\$(vendorDir|baseDir)\s*\.\s*'([^']*)'")
_CLASSMAP_RE = re.compile(r"'((?:[^'\\]|\\\\)+)'\s*=>\s*\$(vendorDir|baseDir)\s*\.\s*'([^']*)'")


class ClassLocator:
    """Resolves FQCN -> (relative file, declaration line) from composer autoload maps."""

    def __init__(self, root):
        self.root = root
        self.psr4 = []
        self.classmap = {}
        self._cache = {}
        self._load()

    def _base(self, which):
        return os.path.join(self.root, "vendor") if which == "vendorDir" else self.root

    def _load(self):
        comp = os.path.join(self.root, "vendor", "composer")
        p = os.path.join(comp, "autoload_psr4.php")
        if os.path.isfile(p):
            text = open(p, encoding="utf-8", errors="replace").read()
            for m in _PSR4_RE.finditer(text):
                prefix = m.group(1).replace("\\\\", "\\")
                dirs = [self._base(w) + d for w, d in _PATH_RE.findall(m.group(2))]
                self.psr4.append((prefix, dirs))
            # longest prefix first so nested namespaces win
            self.psr4.sort(key=lambda x: -len(x[0]))
        p = os.path.join(comp, "autoload_classmap.php")
        if os.path.isfile(p):
            for m in _CLASSMAP_RE.finditer(open(p, encoding="utf-8", errors="replace").read()):
                self.classmap[m.group(1).replace("\\\\", "\\")] = self._base(m.group(2)) + m.group(3)

    def file_of(self, fqcn):
        fqcn = fqcn.lstrip("\\")
        path = self.classmap.get(fqcn)
        if path is None:
            for prefix, dirs in self.psr4:
                if fqcn.startswith(prefix):
                    rest = fqcn[len(prefix):].replace("\\", "/") + ".php"
                    path = next((d + "/" + rest for d in dirs if os.path.isfile(d + "/" + rest)), None)
                    if path:
                        break
        return path

    def locate(self, fqcn):
        """Return (relpath, line) or (None, None); line is the class declaration."""
        if fqcn not in self._cache:
            self._cache[fqcn] = self._locate(fqcn)
        return self._cache[fqcn]

    def _locate(self, fqcn):
        path = self.file_of(fqcn)
        result = (None, None)
        if path and os.path.isfile(path):
            short = re.escape(fqcn.rsplit("\\", 1)[-1])
            decl = re.compile(r"^\s*(?:(?:final|abstract|readonly)\s+)*(?:class|interface|trait|enum)\s+" + short + r"\b")
            line = 1
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for n, text in enumerate(fh, 1):
                    if decl.match(text):
                        line = n
                        break
            result = (os.path.relpath(os.path.realpath(path), os.path.realpath(self.root)), line)
        return result


class Context:
    """Passed to every extractor: project paths, cached runtime dumps, shard access."""

    def __init__(self, root, refresh_raw=False):
        self.root = root
        self.out_dir = os.path.join(root, OUT_SUBDIR)
        self.raw_dir = os.path.join(self.out_dir, "raw")
        self.refresh_raw = refresh_raw
        self._locator = None
        self._raw = {}

    @property
    def locator(self):
        if self._locator is None:
            self._locator = ClassLocator(self.root)
        return self._locator

    def container(self):
        from . import raw
        if "container" not in self._raw:
            self._raw["container"] = raw.container(self)
        return self._raw["container"]

    def events(self):
        from . import raw
        if "events" not in self._raw:
            self._raw["events"] = raw.events(self)
        return self._raw["events"]

    def shard(self, name):
        """Records of an already-built shard (build order guarantees dependencies)."""
        from . import store
        return list(store.read_shard(self.out_dir, name))

    def rel(self, path):
        return os.path.relpath(os.path.realpath(path), os.path.realpath(self.root))
