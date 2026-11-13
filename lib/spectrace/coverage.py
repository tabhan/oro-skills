"""Static AC coverage: every active AC has at least one tagged e2e/functional carrier."""
from . import model

COUNTS = ("e2e", "functional")


def check(specs, tags):
    problems, rows = [], []
    known = {}
    for s in specs:
        seen = set()
        for ac in s.acs:
            if ac.num in seen:
                problems.append("%s: AC-%s defined twice (ids are never reused)" % (s.id, ac.num))
            seen.add(ac.num)
            known[(s.id, ac.num)] = ac
            if not ac.retired and not ac.has_gwt:
                problems.append("%s: AC-%s lacks Given/When/Then" % (s.id, ac.num))
    for (sid, num), ac in sorted(known.items(), key=lambda kv: (kv[0][0], int(kv[0][1]))):
        if ac.retired:
            continue
        carriers = tags.get((sid, num), [])
        good = [c for c in carriers if c[0] in COUNTS and (ac.layer in (None, c[0]))]
        status = "covered"
        if not good:
            only_unit = carriers and all(c[0] == "unit" for c in carriers)
            wrong = [c for c in carriers if c[0] in COUNTS]
            status = "unit-only" if only_unit else ("wrong-layer" if wrong else "uncovered")
            problems.append("%s:AC-%s %s%s" % (sid, num, status, " (Layer: %s)" % ac.layer if status == "wrong-layer" else ""))
        rows.append((ac.key, status, ", ".join(sorted({c[1] for c in good}))))
    for (sid, num), carriers in sorted(tags.items()):
        ac = known.get((sid, num))
        if ac is None:
            problems.append("orphan tag spec:%s:AC-%s in %s (unknown AC)" % (sid, num, carriers[0][1]))
        elif ac is not None and ac.retired:
            problems.append("tag spec:%s:AC-%s in %s cites a retired AC" % (sid, num, carriers[0][1]))
    return problems, rows
