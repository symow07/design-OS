"""WI-Z / §AC2(b) — the abstract surface plan: ``(N, B)``, N unbound.

§AC2 ruled that **no zone is added in sprint 14** and that the back-panel work
is built against *"an ABSTRACT surface list of unbound length"*. §AC2(b) gives
the form: *"The ledger and the construction model take `(N, B)` — N surfaces,
budget B per surface — with N unbound. Surfaces are addressed positionally as
`surface[0] … surface[N-1]`. No zone name appears anywhere in the multi-layer
path."*

This module is that form. It is deliberately small and deliberately ignorant.

WHY THERE IS NO NAME IN HERE, AND WHY THAT IS THE POINT
--------------------------------------------------------
§AC2(a): *"I would have to name them, and naming them fixes the count… A guess
with a hash on it is indistinguishable from a decision."* A name is a decision
about how many there are and what each one is for. `surface[0]` is neither —
it is a position in a list whose length the caller supplied and this module
never checks against an expectation, because it has none.

§AC2(b) also gives the mechanism it is guarding against: *"an invented name in
a comment becomes an invented name in a variable becomes an invented name in an
emitter."* The defence is that the name never gets written down ONCE — and
that includes here. This paragraph originally recited the forbidden vocabulary
in order to promise it was absent, which is the first link of that chain
wearing the costume of the guard against it; the recital is gone and the
promise is kept by the two tests instead. `test_wiz_zone_contract.py` scans
this file for a zone id and `test_wiz_surface_plan.py` scans it for the
positional words a comment reaches for when it wants to say which surface is
which. If either appears, both go red.

WHAT "N UNBOUND" COSTS, AND WHY IT IS PAID
-------------------------------------------
`n` has NO DEFAULT. A caller that does not know how many surfaces it has
cannot get a plan by leaving the argument out, because §AB1(f) says the layer
count is not yet a number and *"nothing may be built assuming exactly two"*. A
default of 2 would be that assumption, written once, in the place everybody
imports from. `plan()` raises instead.

The same reasoning forbids a maximum. There is no `MAX_SURFACES` here: a
ceiling is a guess about the count in the opposite direction, and §AC2(d) says
the count is fixed **once**, by an owner ruling in §AD, after WI-2A's
re-enumeration produces a minimum. Until then this module accepts any N ≥ 1 and
reports what that N implies, which is all it can honestly do.

WHAT THIS MODULE IS NOT
------------------------
It is not an allocator. It says how much room `(N, B)` describes and where the
positions are; deciding WHICH section goes on WHICH surface is §AC3's splitting
rule and WI-2A's re-enumeration, and doing it here would smuggle a layout
policy into a data structure. `total_capacity` is a multiplication, and it is
stated as one so that nobody mistakes it for a promise that a document of that
many lines will fit — gaps, splitting and continuation markers all charge
against it, and §AC3(b) makes the marker cost a line.
"""
from __future__ import annotations

SCHEMA = "abstract_surface_plan/1.0"

RULE = ("N surfaces of budget B lines each, addressed positionally, with N "
        "unbound and no surface named")

#: Raised rather than defaulted. See the module docstring: a default N is
#: §AB1(f)'s forbidden assumption with an import path attached.
SURFACE_COUNT_REQUIRED = "ABSTRACT_SURFACE_PLAN_SURFACE_COUNT_REQUIRED"
SURFACE_COUNT_INVALID = "ABSTRACT_SURFACE_PLAN_SURFACE_COUNT_INVALID"
BUDGET_INVALID = "ABSTRACT_SURFACE_PLAN_BUDGET_INVALID"
INDEX_OUT_OF_RANGE = "ABSTRACT_SURFACE_PLAN_INDEX_OUT_OF_RANGE"


def address(index: int) -> str:
    """The positional address of one surface, ``surface[i]``.

    §AC2(b) spells the addressing out as ``surface[0] … surface[N-1]``, so the
    spelling lives in exactly one function rather than being formatted at each
    call site. This returns an ADDRESS, not a name: it is a rendering of an
    integer and carries no claim about what the surface is or where it is on
    the object.
    """
    i = int(index)
    if i < 0:
        raise ValueError(f"{INDEX_OUT_OF_RANGE}: {index}")
    return f"surface[{i}]"


def plan(n, budget) -> dict:
    """``abstract_surface_plan/1.0`` for N surfaces of B lines each.

    Both arguments are REQUIRED and neither has a default; see the module
    docstring for why `n` in particular must not have one.
    """
    if n is None:
        raise ValueError(SURFACE_COUNT_REQUIRED)
    count = int(n)
    if count < 1:
        raise ValueError(f"{SURFACE_COUNT_INVALID}: {n}")
    b = int(budget)
    if b < 0:
        raise ValueError(f"{BUDGET_INVALID}: {budget}")
    return {
        "schema_version": SCHEMA,
        "rule": RULE,
        "surfaces": count,
        "budget_lines_per_surface": b,
        "addresses": [address(i) for i in range(count)],
        # A multiplication, labelled as one. See the module docstring: this is
        # not a promise that a document of this many lines fits.
        "total_capacity_lines": count * b,
        "count_authority": None,          # §AB1(f) / §AC2(d). Never a number.
        "surface_names": None,            # §AC2(b). Never names.
    }


def capacity_for(plan_record: dict) -> int:
    """Total line capacity a plan describes. Reads the record, never re-derives
    it, so a plan built once cannot disagree with itself when read twice."""
    return int((plan_record or {}).get("total_capacity_lines") or 0)


def fits(plan_record: dict, line_cost: int) -> bool:
    """Whether ``line_cost`` lines fit in the plan's TOTAL capacity.

    THE HONEST LIMIT, stated because it would otherwise be assumed away: this
    is the unallocated question. It asks whether the lines fit in `N × B`, not
    whether any assignment of whole sections to surfaces exists — those differ
    exactly when a section is too tall for one surface but the total has room,
    which is the case §AC3 was ruled to handle. A True here is a necessary
    condition for a layout and never a sufficient one.
    """
    return int(line_cost) <= capacity_for(plan_record)


__all__ = ["BUDGET_INVALID", "INDEX_OUT_OF_RANGE", "RULE", "SCHEMA",
           "SURFACE_COUNT_INVALID", "SURFACE_COUNT_REQUIRED", "address",
           "capacity_for", "fits", "plan"]
