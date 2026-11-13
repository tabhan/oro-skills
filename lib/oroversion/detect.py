"""Detect the Oro version of a project from composer.lock, with a hash-keyed cache in .oro-ai/version.json."""
import hashlib
import json
import os
import re

from .constraint import ConstraintError, Version, parse_version

PACKAGES = ("oro/platform", "oro/commerce", "oro/commerce-enterprise", "oro/crm")
CACHE_REL = os.path.join(".oro-ai", "version.json")


class DetectResult:
    def __init__(self, version=None, source_pkg=None, lock_sha256=None, warnings=None, reason=None, cached=False):
        self.version = version
        self.source_pkg = source_pkg
        self.lock_sha256 = lock_sha256
        self.warnings = warnings or []
        self.reason = reason
        self.cached = cached

    @property
    def known(self):
        return self.version is not None

    def as_dict(self):
        return {"version": str(self.version) if self.version else None, "source_pkg": self.source_pkg,
                "lock_sha256": self.lock_sha256, "warnings": self.warnings, "reason": self.reason, "cached": self.cached}


_BRANCH_DEV = re.compile(r"^v?(\d+)\.(\d+)\.[xX*]-dev$|^v?(\d+)\.[xX*]-dev$")


def normalise(raw):
    """Return (Version|None, warning|None). dev branches have no knowable patch level."""
    text = str(raw).strip()
    warning = None
    version = None
    m = _BRANCH_DEV.match(text)
    if text.startswith("dev-") or text in ("", "master"):
        warning = "dev branch %r has no version" % text
    elif m:
        major, minor = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), 0)
        version = Version(int(major), int(minor), 0)
        warning = "%s is a dev branch: patch level unknown, assuming %s" % (text, version)
    else:
        try:
            version = parse_version(text)
        except ConstraintError:
            warning = "unparsable version %r" % text
    return version, warning


def _read_lock(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def _from_lock(data, sha):
    pkgs = {p.get("name"): p.get("version") for p in data.get("packages", []) + data.get("packages-dev", [])}
    found = [(name, pkgs[name]) for name in PACKAGES if name in pkgs]
    if not found:
        return DetectResult(lock_sha256=sha, reason="no oro package (%s) in composer.lock" % ", ".join(PACKAGES))
    warnings, parsed = [], []
    for name, raw in found:
        version, warning = normalise(raw)
        if warning:
            warnings.append("%s: %s" % (name, warning))
        if version:
            parsed.append((name, version))
    if not parsed:
        return DetectResult(lock_sha256=sha, warnings=warnings, reason="oro packages have no release version (dev branch)")
    minors = {(v.major, v.minor) for _, v in parsed}
    if len(minors) > 1:
        warnings.append("oro packages disagree on major.minor: " + ", ".join("%s=%s" % (n, v) for n, v in parsed))
    name, version = parsed[0]
    return DetectResult(version, name, sha, warnings)


def detect(project, use_cache=True, write_cache=True):
    """Detect the version for `project`; re-detects when the lock hash differs from the cache."""
    lock = os.path.join(project, "composer.lock")
    if not os.path.isfile(lock):
        return DetectResult(reason="no composer.lock in %s" % project)
    try:
        data, sha = _read_lock(lock)
    except (OSError, ValueError) as exc:
        return DetectResult(reason="composer.lock unreadable: %s" % exc)
    cache = os.path.join(project, CACHE_REL)
    if use_cache and os.path.isfile(cache):
        try:
            with open(cache, encoding="utf-8") as fh:
                c = json.load(fh)
            if c.get("lock_sha256") == sha and c.get("version"):
                return DetectResult(parse_version(c["version"]), c.get("source_pkg"), sha, c.get("warnings", []), cached=True)
        except (OSError, ValueError, ConstraintError):
            pass
    result = _from_lock(data, sha)
    if write_cache and result.known:
        try:
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache, "w", encoding="utf-8") as fh:
                json.dump({"version": str(result.version), "source_pkg": result.source_pkg, "lock_sha256": sha,
                           "warnings": result.warnings}, fh, indent=2)
                fh.write("\n")
        except OSError:
            result.warnings.append("could not write %s" % cache)
    return result
