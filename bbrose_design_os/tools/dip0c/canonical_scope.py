"""Canonical scope: the quad-state comparison every canonical decision uses (C3b4).

This is the **single** comparison implementation. Canonical approval, conflict
detection, replacement validation, the scope-indexed read model, narrowing/widening
validation and the review queues all call `relate()`. The C3b3 boolean overlap helper
is retired, and a test asserts nothing still reaches for it — two divergent notions of
"overlap" inside one system is exactly how a second master slips through.

Three things carry the safety:

**An axis is a MODE, not a bare list.** `ALL` (omission, per the schema) is different
from `NONE`, which is different from `INCOMPLETE` (we don't know). Incomplete data
never silently becomes `ALL` — it becomes `SCOPE_UNKNOWN_OVERLAP`.

**Periods are half-open** `[valid_from, valid_until)`, so touching intervals are
disjoint: a master ending exactly when its successor begins does not overlap it.

**DISJOINT on any one axis proves the scopes cannot collide** — and that is the only
thing that can beat an `UNKNOWN` elsewhere. Uncertainty anywhere else fails closed.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import config as C
from . import taxonomy as TX
from .taxonomy import DISJOINT, IDENTICAL, OVERLAPPING, UNKNOWN

PARSER = f"{C.TOOL_NAME}.canonical_scope/{C.TOOL_VERSION}"

# --- axis modes ---------------------------------------------------------------
MODE_ALL = "ALL"                 # every token on this axis (the schema's meaning
                                 # of an omitted or empty list)
MODE_LIST = "LIST"               # exactly these tokens
MODE_NONE = "NONE"               # explicitly nothing on this axis
MODE_INCOMPLETE = "INCOMPLETE"    # we do not know -> fails closed
MODE_INVALID = "INVALID"          # malformed input -> fails closed
MODES = (MODE_ALL, MODE_LIST, MODE_NONE, MODE_INCOMPLETE, MODE_INVALID)

LIST_AXES = {"products": "products", "markets": "markets",
             "media": "media"}
TOKEN_AXES = {"lockup": "lockups", "variant_role": "variant_roles"}

# Every axis a scope compares on, in a fixed order (determinism).
AXIS_ORDER = ("lockup", "products", "markets", "media", "variant_role")

MIN_TIME = datetime(1, 1, 1, tzinfo=timezone.utc)
MAX_TIME = datetime(9999, 12, 31, tzinfo=timezone.utc)


class ScopeError(RuntimeError):
    """A scope could not be built."""


def _dt(v):
    """Normalise to UTC. Anything malformed is a signal, not an exception."""
    if v in (None, ""):
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return MODE_INVALID
    if d.tzinfo is None:
        return MODE_INVALID          # a naive timestamp is not a UTC instant
    return d.astimezone(timezone.utc)


def axis_value(submitted, *, incomplete: bool = False) -> dict:
    """One axis of a scope, with its meaning RECORDED rather than implied."""
    if incomplete:
        return {"mode": MODE_INCOMPLETE, "tokens": [], "submitted": submitted}
    if submitted is None or (isinstance(submitted, (list, tuple))
                             and len(submitted) == 0):
        # the schema explicitly defines omission as ALL (C3b4 §3)
        return {"mode": MODE_ALL, "tokens": [], "submitted": submitted}
    if isinstance(submitted, str):
        submitted = [submitted]
    if not isinstance(submitted, (list, tuple)):
        return {"mode": MODE_INVALID, "tokens": [], "submitted": submitted}
    return {"mode": MODE_LIST, "tokens": sorted(str(t) for t in submitted),
            "submitted": list(submitted)}


def scope(brand: str, *, lockup="PRIMARY", products=None, markets=None,
          media=None, variant_role="MASTER", valid_from: str = None,
          valid_until: str = None, incomplete_axes=()) -> dict:
    """Build a canonical scope. Omission means ALL; *incompleteness* means UNKNOWN,
    and the two are never conflated.

    MEDIA (taxonomy v1.1.0) is INDEPENDENT of products. Products answer *what is being
    designed*; media answers *where it may be used*. A palette approved for DIGITAL is
    not approved for the press, and folding media into the product tree would collapse
    two questions into one.
    """
    if not brand:
        raise ScopeError("a scope must name its brand")
    return {
        "schema_version": "canonical_scope/1.1",
        "brand": brand,
        "lockup": axis_value(lockup, incomplete="lockup" in incomplete_axes),
        "products": axis_value(products, incomplete="products" in incomplete_axes),
        "markets": axis_value(markets, incomplete="markets" in incomplete_axes),
        "media": axis_value(media, incomplete="media" in incomplete_axes),
        "variant_role": axis_value(variant_role,
                                   incomplete="variant_role" in incomplete_axes),
        "period": period(valid_from, valid_until),
        "taxonomy_version": TX.version(),
    }


# --- backward compatibility: v1.0.0 scopes predate the media axis ---------------
COMPAT_MEDIA_NORMALIZED = "MEDIA_ADDED_BY_COMPATIBILITY_NORMALIZATION"


def normalize_for_compare(s: dict) -> dict:
    """A scope pinned to a taxonomy that had no `media` axis gets media = ALL, and
    SAYS SO. The original submitted scope is preserved untouched: a compatibility
    default is a fact about our migration, not a fact the human ever asserted.
    """
    if "media" in s:
        return s
    out = dict(s)
    out["media"] = axis_value(None)                       # omission means ALL
    out["media"]["compatibility"] = COMPAT_MEDIA_NORMALIZED
    out["media"]["submitted"] = None
    out["compatibility_normalized"] = [COMPAT_MEDIA_NORMALIZED]
    out["original_scope_taxonomy_version"] = s.get("taxonomy_version")
    return out


def period(valid_from: str = None, valid_until: str = None) -> dict:
    """Half-open [valid_from, valid_until). Touching intervals are DISJOINT."""
    f, u = _dt(valid_from), _dt(valid_until)
    invalid = MODE_INVALID in (f, u)
    if not invalid and f and u and f >= u:
        invalid = True                          # contradictory: ends before it starts
    return {
        "submitted_from": valid_from, "submitted_until": valid_until,
        "valid_from": None if f in (None, MODE_INVALID) else f.isoformat(),
        "valid_until": None if u in (None, MODE_INVALID) else u.isoformat(),
        "open_start": f is None and not invalid,
        "open_end": u is None and not invalid,
        "interval": "half-open [valid_from, valid_until)",
        "invalid": invalid,
    }


# --- comparison ---------------------------------------------------------------
def _relate_periods(a: dict, b: dict) -> tuple[str, str]:
    if a.get("invalid") or b.get("invalid"):
        return UNKNOWN, ("a validity period is malformed or contradictory — the "
                         "machine will not guess when it applies")
    af = _dt(a["valid_from"]) or MIN_TIME
    au = _dt(a["valid_until"]) or MAX_TIME
    bf = _dt(b["valid_from"]) or MIN_TIME
    bu = _dt(b["valid_until"]) or MAX_TIME
    if au <= bf or bu <= af:
        # half-open: one ending exactly when the other begins is DISJOINT
        return DISJOINT, "the validity periods do not intersect (half-open)"
    if af == bf and au == bu:
        return IDENTICAL, "the validity periods are the same"
    return OVERLAPPING, "the validity periods intersect"


def _relate_axis(axis_name: str, a: dict, b: dict) -> tuple[str, str]:
    """One axis: mode against mode, then token sets under the axis taxonomy."""
    ta = TOKEN_AXES.get(axis_name) or LIST_AXES.get(axis_name)

    for v, side in ((a, "left"), (b, "right")):
        if v["mode"] in (MODE_INCOMPLETE, MODE_INVALID):
            return UNKNOWN, (f"the {side} {axis_name} scope is {v['mode']} — missing "
                             "or malformed data never silently becomes ALL")

    if a["mode"] == MODE_NONE or b["mode"] == MODE_NONE:
        return DISJOINT, f"one side covers no {axis_name} at all"
    if a["mode"] == MODE_ALL and b["mode"] == MODE_ALL:
        return IDENTICAL, f"both cover ALL {axis_name}"
    if a["mode"] == MODE_ALL or b["mode"] == MODE_ALL:
        return OVERLAPPING, (f"one side covers ALL {axis_name}, which necessarily "
                             "includes the other")

    # both LIST. Resolve aliases BEFORE comparing: EU and EUROPE are the same market,
    # and comparing the raw strings would call them merely overlapping. Set equality
    # is settled before the pairwise sweep, or an identical scope would trip the
    # "proven intersection" branch and report OVERLAPPING — the read model needs to
    # tell those two apart.
    na = [TX.resolve(ta, t) for t in a["tokens"]]
    nb = [TX.resolve(ta, t) for t in b["tokens"]]
    unresolved = [x for x in na + nb if not x["known"]]
    if unresolved:
        return UNKNOWN, "; ".join(x["reason"] for x in unresolved[:3])
    if sorted(x["token"] for x in na) == sorted(x["token"] for x in nb):
        return IDENTICAL, f"the same {axis_name} (after alias resolution)"

    best, whys = DISJOINT, []
    for x in a["tokens"]:
        for y in b["tokens"]:
            rel, why = TX.relate_tokens(ta, x, y)
            if rel in (OVERLAPPING, IDENTICAL):
                # a PROVEN intersection settles it: they collide, full stop
                return OVERLAPPING, f"{x} vs {y}: {why}"
            if rel == UNKNOWN:
                best, _ = UNKNOWN, whys.append(f"{x} vs {y}: {why}")
    if best == UNKNOWN:
        return UNKNOWN, "; ".join(whys[:3])
    return DISJOINT, f"no {axis_name} token intersects"


def relate(a: dict, b: dict) -> dict:
    """THE scope comparison. Every canonical workflow routes through this.

    DISJOINT on any single axis proves the two scopes cannot both apply, and that
    beats uncertainty elsewhere. Otherwise any UNKNOWN fails closed.
    """
    a, b = normalize_for_compare(a), normalize_for_compare(b)
    per_axis: dict[str, dict] = {}

    if a["brand"] != b["brand"]:
        per_axis["brand"] = {"relation": DISJOINT,
                             "why": f"different brands ({a['brand']} vs {b['brand']})"}
    else:
        per_axis["brand"] = {"relation": IDENTICAL, "why": "the same brand"}

    for name in AXIS_ORDER:
        rel, why = _relate_axis(name, a[name], b[name])
        per_axis[name] = {"relation": rel, "why": why}

    rel, why = _relate_periods(a["period"], b["period"])
    per_axis["period"] = {"relation": rel, "why": why}

    rels = [v["relation"] for v in per_axis.values()]
    if DISJOINT in rels:
        overall = DISJOINT
        reason = next(f"{k}: {v['why']}" for k, v in per_axis.items()
                      if v["relation"] == DISJOINT)
        proven = True
    elif UNKNOWN in rels:
        overall = UNKNOWN
        reason = next(f"{k}: {v['why']}" for k, v in per_axis.items()
                      if v["relation"] == UNKNOWN)
        proven = False
    elif all(r == IDENTICAL for r in rels):
        overall, reason, proven = IDENTICAL, "every axis is identical", True
    else:
        overall = OVERLAPPING
        reason = next(f"{k}: {v['why']}" for k, v in per_axis.items()
                      if v["relation"] == OVERLAPPING)
        proven = True

    return {
        "relation": overall,
        "reason": reason,
        "proven": proven,           # False == the overlap is UNCERTAIN, not absent
        "per_axis": {k: v["relation"] for k, v in per_axis.items()},
        "per_axis_why": {k: v["why"] for k, v in per_axis.items()},
        "taxonomy_version": TX.version(),
        "parser": PARSER,
    }


def collides(a: dict, b: dict) -> bool:
    """Fail closed: IDENTICAL, OVERLAPPING and UNKNOWN all block. Only a PROVEN
    DISJOINT lets two canonical masters coexist."""
    return relate(a, b)["relation"] != DISJOINT


# --- narrowing vs widening ----------------------------------------------------
def narrowing_delta(previous: dict, requested: dict) -> dict:
    """What a scope change actually does. Widening is NOT narrowing with a minus
    sign — it is a new approval, and it must go through full dual control."""
    previous = normalize_for_compare(previous)
    requested = normalize_for_compare(requested)
    removed: dict[str, list] = {}
    added: dict[str, list] = {}
    problems: list[str] = []

    if previous["brand"] != requested["brand"]:
        problems.append("a scope change may not change the brand — that is a new "
                        "canonical approval, not a narrowing")

    for name in AXIS_ORDER:
        p, r = previous[name], requested[name]
        for v, side in ((p, "previous"), (r, "requested")):
            if v["mode"] in (MODE_INCOMPLETE, MODE_INVALID):
                problems.append(f"the {side} {name} scope is {v['mode']}: a narrowing "
                                "must be computed from complete scopes")
        if p["mode"] == MODE_ALL and r["mode"] == MODE_ALL:
            continue
        if p["mode"] == MODE_ALL and r["mode"] == MODE_LIST:
            removed[name] = ["<ALL> -> " + ", ".join(r["tokens"])]
            continue
        if p["mode"] == MODE_LIST and r["mode"] == MODE_ALL:
            added[name] = ["<ALL>"]              # ALL is strictly wider than any list
            continue
        if p["mode"] == MODE_LIST and r["mode"] == MODE_LIST:
            # Containment, NOT set difference. Narrowing EU to FR removes nothing
            # from a set point of view — yet France is plainly inside the EU, and
            # calling that a widening would force a full reapproval for a genuine
            # reduction. Only the taxonomy can answer this.
            ax = LIST_AXES.get(name) or TOKEN_AXES[name]
            esc, gone, unknown = [], [], []
            for t in r["tokens"]:
                inside = TX.covered_by_any(ax, t, p["tokens"])
                if inside is None:
                    unknown.append(t)
                elif not inside:
                    esc.append(t)               # escapes the previous scope -> WIDER
            for t in p["tokens"]:
                still = TX.covered_by_any(ax, t, r["tokens"])
                if still is None:
                    unknown.append(t)
                elif not still:
                    gone.append(t)              # no longer covered -> NARROWER
            if unknown:
                problems.append(
                    f"the {name} scope change cannot be classified: "
                    f"{sorted(set(unknown))} are not resolvable against the "
                    "taxonomy. A scope change that cannot be proven to REDUCE is "
                    "refused — it might be widening in disguise.")
            if esc:
                added[name] = sorted(esc)
            if gone:
                removed[name] = sorted(gone)

    # a period may only shrink
    pp, rp = previous["period"], requested["period"]
    if pp.get("invalid") or rp.get("invalid"):
        problems.append("a validity period is malformed: a narrowing must be "
                        "computed from valid periods")
    else:
        pf = _dt(pp["valid_from"]) or MIN_TIME
        pu = _dt(pp["valid_until"]) or MAX_TIME
        rf = _dt(rp["valid_from"]) or MIN_TIME
        ru = _dt(rp["valid_until"]) or MAX_TIME
        if rf < pf or ru > pu:
            added["period"] = [f"[{rp['valid_from']}, {rp['valid_until']})"]

    widening = bool(added)
    if widening:
        problems.append(
            f"this WIDENS the scope on {sorted(added)} — widening is a NEW canonical "
            "approval and must pass the complete dual-control process. It may not be "
            "recorded as a scope reduction.")
    return {
        "removed": removed, "added": added,
        "is_narrowing": (not widening) and bool(removed) and not problems,
        "is_widening": widening,
        "no_change": not removed and not added and not problems,
        "problems": problems,
    }
