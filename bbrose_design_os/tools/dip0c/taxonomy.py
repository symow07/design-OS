"""The scope taxonomy: what a scope token MEANS (DIP-0C3b4).

Each axis — markets, products, lockups, variant_roles — has its **own** taxonomy and
its **own** comparison rules. There is no generic token relation, because the axes do
not behave alike: `EU` contains `FR`, but `PRIMARY` containing `PRIMARY_HORIZONTAL`
is a claim about brand policy, not geography, and one rule cannot honestly serve both.

Two rules do the safety work:

**DISJOINT is never inferred from the absence of an edge.** Two registered tokens are
disjoint only where the taxonomy *says* they are — mutually-exclusive children,
mutually-exclusive roots on a closed-world axis, or an explicit `disjoint_peers`
entry. A PARENT or GENERAL token with no recorded relationship is `UNKNOWN`, never
disjoint: a category might contain the thing it is being compared to.

**An unregistered token is UNKNOWN and fails closed.** Nothing is inferred from
spelling. `LIPGLOSS` resolves to `LIP_GLOSS` only because an alias says so, never
because the strings look alike.
"""
from __future__ import annotations

import json
from functools import lru_cache

from . import config as C

PARSER = f"{C.TOOL_NAME}.taxonomy/{C.TOOL_VERSION}"
TAXONOMY_PATH = C.DOCS_ROOT / "scope_taxonomy.json"

# --- the quad-state, on a single axis ----------------------------------------
IDENTICAL = "SCOPE_IDENTICAL"
OVERLAPPING = "SCOPE_OVERLAPPING"
DISJOINT = "SCOPE_DISJOINT"
UNKNOWN = "SCOPE_UNKNOWN_OVERLAP"
RELATIONS = (IDENTICAL, OVERLAPPING, DISJOINT, UNKNOWN)

# token types
T_PARENT = "PARENT"
T_LEAF = "LEAF"
T_GENERAL = "GENERAL"
T_SPECIAL = "SPECIAL"

# `media` (v1.1.0) is INDEPENDENT of products: products say what is being designed,
# media says where it may be used. A palette approved for DIGITAL is not approved for
# the press, and folding one into the other would collapse two questions into one.
AXES = ("markets", "products", "lockups", "variant_roles", "media")

# A token type that may CONTAIN other things. Absence of an edge to one of these
# never proves disjointness — the category might swallow the other token whole.
CONTAINER_TYPES = (T_PARENT, T_GENERAL, T_SPECIAL)


class TaxonomyError(RuntimeError):
    """The taxonomy file is missing, malformed, or self-contradictory."""


@lru_cache(maxsize=1)
def load(path: str = None) -> dict:
    p = C.Path(path) if path else TAXONOMY_PATH
    if not p.exists():
        raise TaxonomyError(f"scope taxonomy not found at {p}")
    doc = json.loads(p.read_text())
    _validate(doc)
    return doc


def version() -> str:
    return load()["taxonomy_version"]


def _validate(doc: dict) -> None:
    for axis in AXES:
        if axis not in doc.get("axes", {}):
            raise TaxonomyError(f"taxonomy is missing the {axis!r} axis")
        ax = doc["axes"][axis]
        toks = ax["tokens"]
        for name, t in toks.items():
            if t["type"] not in (T_PARENT, T_LEAF, T_GENERAL, T_SPECIAL):
                raise TaxonomyError(f"{axis}.{name}: unknown token type {t['type']!r}")
            for child in t.get("children", []):
                if child not in toks:
                    raise TaxonomyError(
                        f"{axis}.{name} declares child {child!r}, which is not a "
                        "registered token")
        # an alias must not collide with a real token, or resolution is ambiguous
        for name, t in toks.items():
            for a in t.get("aliases", []):
                if a in toks:
                    raise TaxonomyError(
                        f"{axis}: alias {a!r} of {name!r} is also a canonical token")


# --- resolution ---------------------------------------------------------------
def resolve(axis: str, token: str) -> dict:
    """Normalise ONE submitted token. The original is preserved for provenance —
    normalisation must never erase what the human actually wrote."""
    ax = load()["axes"][axis]
    toks, submitted = ax["tokens"], token
    t = (token or "").strip().upper()

    if not t:
        return {"submitted": submitted, "token": None, "known": False,
                "reason": "empty token"}

    dep = ax.get("deprecated_tokens", {})
    if t in dep:
        repl = dep[t].get("replaced_by")
        if not repl or repl not in toks:
            return {"submitted": submitted, "token": None, "known": False,
                    "reason": f"{t!r} is deprecated with no valid replacement"}
        return {"submitted": submitted, "token": repl, "known": True,
                "deprecated": True, "replaced_by": repl,
                "reason": f"{t!r} is deprecated; normalised to {repl!r}"}

    if t in toks:
        return {"submitted": submitted, "token": t, "known": True,
                "type": toks[t]["type"]}

    for name, spec in toks.items():                 # alias — declared, never guessed
        if t in [a.upper() for a in spec.get("aliases", [])]:
            return {"submitted": submitted, "token": name, "known": True,
                    "type": spec["type"], "alias_of": name,
                    "reason": f"{t!r} is a declared alias of {name!r}"}

    return {"submitted": submitted, "token": None, "known": False,
            "reason": f"{t!r} is not registered in the {axis!r} taxonomy — the "
                      "machine will not guess what it means"}


def _ancestors(axis: str, token: str) -> list[str]:
    toks = load()["axes"][axis]["tokens"]
    parents = {c: name for name, t in toks.items() for c in t.get("children", [])}
    out, cur = [], token
    while cur in parents:
        cur = parents[cur]
        if cur in out:                              # a cycle: refuse to loop forever
            raise TaxonomyError(f"{axis}: cycle in the token hierarchy at {cur!r}")
        out.append(cur)
    return out


def _root(axis: str, token: str) -> str:
    anc = _ancestors(axis, token)
    return anc[-1] if anc else token


def _parent(axis: str, token: str) -> str | None:
    anc = _ancestors(axis, token)
    return anc[0] if anc else None


def covers(axis: str, outer: str, inner: str) -> bool | None:
    """Does `outer` CONTAIN `inner`? (EU covers FR; FR does not cover EU.)

    Containment is directional, and set arithmetic cannot see it: narrowing EU to FR
    removes nothing from a set point of view, yet France is plainly inside the EU.
    Returns None when the taxonomy cannot say — the caller must fail closed.
    """
    ro, ri = resolve(axis, outer), resolve(axis, inner)
    if not ro["known"] or not ri["known"]:
        return None
    if ro["token"] == ri["token"]:
        return True
    toks = load()["axes"][axis]["tokens"]
    if toks[ro["token"]]["type"] == T_SPECIAL:
        return True                      # a SPECIAL token (e.g. ALL) contains everything
    return ro["token"] in _ancestors(axis, ri["token"])


def covered_by_any(axis: str, token: str, outers: list) -> bool | None:
    """Is `token` inside ANY of `outers`? None if the taxonomy cannot say."""
    unknown = False
    for o in outers:
        c = covers(axis, o, token)
        if c:
            return True
        if c is None:
            unknown = True
    return None if unknown else False


def relate_tokens(axis: str, a: str, b: str) -> tuple[str, str]:
    """The relation between two submitted tokens on ONE axis. Returns
    (relation, why)."""
    if axis not in AXES:
        raise TaxonomyError(f"{axis!r} is not a scope axis")
    ax = load()["axes"][axis]
    ra, rb = resolve(axis, a), resolve(axis, b)

    if not ra["known"] or not rb["known"]:
        bad = ra if not ra["known"] else rb
        return UNKNOWN, f"unresolved token: {bad['reason']}"

    ta, tb = ra["token"], rb["token"]
    toks = ax["tokens"]
    if ta == tb:
        return IDENTICAL, f"the same token ({ta})"

    # 0. a SPECIAL token (e.g. media ALL) contains everything on its axis. It must be
    #    settled BEFORE the closed-world root rule, which would otherwise see it as a
    #    distinct root and wrongly call it disjoint.
    for x, y in ((ta, tb), (tb, ta)):
        if toks[x]["type"] == T_SPECIAL:
            return OVERLAPPING, f"{x} is a SPECIAL token covering every {axis}"

    # 1. an EXPLICIT overlap edge always wins
    for pair in ax.get("explicit_overlaps", []):
        if {ta, tb} == set(pair):
            return OVERLAPPING, f"the taxonomy declares {ta} and {tb} to overlap"

    # 2. ancestor / descendant -> the category contains the thing
    if ta in _ancestors(axis, tb):
        return OVERLAPPING, f"{ta} is an ancestor of {tb}"
    if tb in _ancestors(axis, ta):
        return OVERLAPPING, f"{tb} is an ancestor of {ta}"

    # 3. an EXPLICIT disjoint peering — INHERITED down the hierarchy.
    #    If PRINT and DIGITAL are declared mutually exclusive, then PACKAGING_PRINT
    #    (a child of PRINT) is disjoint from DIGITAL too. That is not an inference
    #    from naming or structure; it follows necessarily from a declaration a human
    #    made. Nothing is guessed — the edge is inherited, not invented.
    anc_a = {ta} | set(_ancestors(axis, ta))
    anc_b = {tb} | set(_ancestors(axis, tb))
    for pair in ax.get("disjoint_peers", []):
        x, y = pair
        if (x in anc_a and y in anc_b) or (y in anc_a and x in anc_b):
            via = "" if {ta, tb} == {x, y} else f" (inherited via {x}/{y})"
            return DISJOINT, (f"the taxonomy declares {x} and {y} mutually "
                              f"exclusive{via}")

    # --- everything below requires the axis to be CLOSED-WORLD ---
    if not ax.get("closed_world"):
        return UNKNOWN, (f"the {axis} axis is open-world: absent an explicit edge, "
                         f"whether {ta} and {tb} intersect is unknown")

    # 4. siblings whose parent declares its children mutually exclusive
    pa, pb = _parent(axis, ta), _parent(axis, tb)
    if pa and pa == pb and toks[pa].get("mutually_exclusive_children"):
        return DISJOINT, (f"{ta} and {tb} are mutually exclusive children of {pa}")

    # 5. distinct roots on an axis that declares its roots mutually exclusive
    root_a, root_b = _root(axis, ta), _root(axis, tb)
    if root_a != root_b and ax.get("mutually_exclusive_roots"):
        # ...but NEVER for a container token: a category may still swallow the other
        if toks[ta]["type"] in CONTAINER_TYPES and not _ancestors(axis, ta) \
                and toks[ta]["type"] == T_GENERAL:
            return UNKNOWN, (f"{ta} is a GENERAL token that cuts across the {axis} "
                             f"tree; whether it covers {tb} is not declared")
        if toks[tb]["type"] == T_GENERAL:
            return UNKNOWN, (f"{tb} is a GENERAL token that cuts across the {axis} "
                             f"tree; whether it covers {ta} is not declared")
        return DISJOINT, (f"{ta} and {tb} sit in different mutually exclusive roots "
                          f"({root_a} vs {root_b}) of a closed-world axis")

    # 6. registered, closed-world, and STILL no declared relationship. Do not guess.
    return UNKNOWN, (f"{ta} and {tb} are both registered, but the taxonomy declares "
                     "no relationship between them and neither disjointness nor "
                     "overlap follows from its structure")
