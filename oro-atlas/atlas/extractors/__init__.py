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


# Inputs each shard ingests directly; anything else cannot make it stale (composer.lock always can).
# "src": filename suffixes read under src/ and config/; "cache": built from the compiled prod container dump.
_YML = (".yml", ".yaml")
INPUTS = {
    "services": {"src": (), "cache": True},
    "mq": {"src": (".php",), "cache": True},
    "tags": {"src": (".php",) + _YML, "cache": True},
    "events": {"src": (".php",), "cache": True},
    "grids": {"src": ("datagrids.yml",), "cache": True},
    "layouts": {"src": _YML + (".twig", ".php"), "cache": True},
    "unsafe": {"src": (".php",) + _YML, "cache": False},
    "entities": {"src": (".php", "entity_extend.yml", "entity_config.yml"), "cache": False},
    "config": {"src": ("system_configuration.yml",), "cache": False},
    "js": {"src": (".js", "jsmodules.yml"), "cache": False},
    "workflows": {"src": ("workflows.yml", "workflows.en.yml"), "cache": False},
    "operations": {"src": ("actions.yml",), "cache": False},
}
# An extractor missing from the table is assumed to read everything.
DEFAULT_INPUT = {"src": (".php", ".yml", ".yaml", ".xml"), "cache": True}


def inputs_of(name):
    return INPUTS.get(name, DEFAULT_INPUT)


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
