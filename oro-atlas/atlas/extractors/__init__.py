"""Extractor registry. Each module exposes NAME and extract(ctx) -> iterable[dict].

Optional ORDER (int, default 100) sorts builds so shards others join on come first.
DEPENDS lists shards an extractor reads via ctx.shard(); declared here so extractor modules stay data-only.
"""
import importlib
import pkgutil

from ..common import AtlasError


DEPENDS = {
    "unsafe": ("services",),
}


def depends_of(mods, name):
    return tuple(getattr(mods[name], "DEPENDS", ())) + DEPENDS.get(name, ())


def with_dependents(mods, names):
    """Close names over reverse DEPENDS so a rebuilt shard never leaves a stale consumer behind."""
    result = set(names)
    grew = True
    while grew:
        extra = {n for n in mods if n not in result and set(depends_of(mods, n)) & result}
        result |= extra
        grew = bool(extra)
    return [n for n in mods if n in result] + [n for n in names if n not in mods]


def load_all():
    mods = {}
    for info in pkgutil.iter_modules(__path__):
        mod = importlib.import_module(__name__ + "." + info.name)
        name = getattr(mod, "NAME", None)
        if not name or not callable(getattr(mod, "extract", None)):
            raise AtlasError("extractor %s must define NAME and extract(ctx)" % info.name)
        if name in mods:
            raise AtlasError("duplicate extractor NAME '%s'" % name)
        mods[name] = mod
    return mods


def ordered(mods, only=None):
    names = with_dependents(mods, only) if only else list(mods)
    unknown = [n for n in names if n not in mods]
    if unknown:
        raise AtlasError("unknown category: %s (known: %s)" % (",".join(unknown), ",".join(sorted(mods))))
    return sorted(names, key=lambda n: (getattr(mods[n], "ORDER", 100), n))
