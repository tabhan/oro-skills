"""Extract `decorates` targets from YAML/XML/PHP text and check them against the atlas."""
import os
import re
import sys
from collections import Counter

import _common as c

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

from atlas.extractors.unsafe import ADVICE, FINAL_ADVICE  # noqa: E402

YAML_DECORATES = re.compile(r"(?:^|[\s{,])decorates\s*:\s*(['\"]?)@?([\w\\.\-]+)\1", re.M)
XML_DECORATES = re.compile(r"\bdecorates\s*=\s*(['\"])@?([\w\\.\-]+)\1")
AS_DECORATOR = re.compile(
    r"AsDecorator\(\s*(?:decorates\s*:\s*)?(?:(['\"])([\w\\.\-]+)\1|(\\?[\w\\]+)::class)"
)
USE_STMT = re.compile(r"^\s*use\s+\\?([\w\\]+)(?:\s+as\s+(\w+))?\s*;", re.M)
NAMESPACE = re.compile(r"^\s*namespace\s+([\w\\]+)\s*;", re.M)


def _norm(target):
    # YAML/PHP string escaping doubles backslashes; service ids never contain '\\\\'.
    return re.sub(r"\\+", r"\\", target).lstrip("\\") if "\\" in target else target


def php_imports(source):
    """Short name -> FQCN from a PHP file's `use` statements."""
    return {(alias or fqcn.rsplit("\\", 1)[-1]): fqcn for fqcn, alias in USE_STMT.findall(source)}


def resolve_class(name, source):
    """FQCN for a `X::class` reference, via the file's imports and namespace."""
    head, _, rest = name.partition("\\")
    imports = php_imports(source)
    ns = NAMESPACE.search(source)
    resolved = name.lstrip("\\")
    if not name.startswith("\\") and head in imports:
        resolved = imports[head] + ("\\" + rest if rest else "")
    elif not name.startswith("\\") and ns:
        resolved = ns.group(1) + "\\" + name
    return resolved


def targets(text, context=""):
    """Every decorates target in `text` (a Counter, so duplicates are kept); `context` supplies imports."""
    found = [_norm(t) for _, t in YAML_DECORATES.findall(text)]
    found += [_norm(t) for _, t in XML_DECORATES.findall(text)]
    found += [_norm(s) if s else resolve_class(k, context or text) for _, s, k in AS_DECORATOR.findall(text)]
    return Counter(found)


def new_targets(new, old, context=""):
    return sorted((targets(new, context) - targets(old, context)).keys())


def service_aliases(root, target):
    """Ids/classes equivalent to `target` per the services shard (aliases, class)."""
    names = {target}
    try:
        for rec in c.store.read_shard(c.atlas_dir(root), "services"):
            if target == rec.get("id") or target in (rec.get("aliases") or []):
                names |= {rec.get("id"), rec.get("class")} | set(rec.get("aliases") or [])
    except Exception:  # noqa: BLE001 - shard absent: fall back to the literal id
        pass
    return sorted(n for n in names if n)


def deny_reason(root, target):
    recs = [r for r in map(lambda n: c.unsafe_for(root, n), service_aliases(root, target)) if r and r.get("consumer_count")]
    reason = None
    if recs:
        rec = recs[0]
        who = ", ".join("%s (%s:%s)" % (x["class"].rsplit("\\", 1)[-1], x["file"], x["line"]) for x in rec["consumers"][:4])
        final = rec.get("kind") == "final class"
        fix = FINAL_ADVICE if final else (
            ADVICE + " (src/Aaxis/Bundle/AspectBundle/README.md; see 'atlas tag aaxis_aspect.interceptor')"
        )
        reason = (
            "Do not decorate '%s': its concrete %s is typehinted by %d consumer(s): %s. "
            "A decorator is not an instance of that class and breaks those constructors. Fix: %s."
            % (target, rec.get("kind") or "class", rec["consumer_count"], who, fix)
        )
    return reason
