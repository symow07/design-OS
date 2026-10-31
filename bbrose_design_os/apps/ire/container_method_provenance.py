"""§AA3 — which STAGE supplied a container's print method (`container_method_provenance/1.0`).

`propose_zones` produced a guess, the guess became a floor, the floor became a
number in a census, and nothing in that chain ever said "assumed". This module
is the sentence that was missing.

THE DEFECT, MEASURED RATHER THAN ASSERTED
-----------------------------------------
`back_panel.size_for_surface` returns a `size_source` record. Run it twice —
once against the record the live pipeline builds, once against the hand-written
one in `tests/test_back_panel.py` — and the `source` field comes back
IDENTICAL:

    live    : "container_production_method/1.0 capability table for BODY_BACK"
    fixture : "container_production_method/1.0 capability table for BODY_BACK"

The floors differ (5.0 vs 6.0) and the method types differ (SCREEN_PRINT vs
HOT_STAMP), but the provenance string does not, because there is no provenance
string — there is a description of WHICH TABLE was read, which is a different
question from WHO PUT THE ROW IN IT. The live 5.0 traces to
`container_contract.make_zone`'s signature, where `permitted_techniques` has
the DEFAULT VALUE `("screen_printing",)`; `propose_zones` calls it without the
argument for both body faces. No stage of the pipeline ever formed an opinion
about how the back of this bottle is decorated. The fixture 6.0 traces to four
keys typed into a test file.

§AA3(a) names this "the same class of defect as `constraints_source` before
§Y1", and that analogy fixes the SHAPE of the fix: §Y1(d) turned a constant
into a real provenance field and added `constraints_by_field` beside it for a
consumer that must not parse prose. This module is that, one level up — the
method itself rather than the constraints hanging off it.

WHY THE INFORMATION IS NOT MISSING, AND WHERE IT GOES
----------------------------------------------------
`build_production_methods` already records `authority_state` and
`verification_source` on every method it builds. `container_text_floor.
surface_floors` then copies four keys out of each method — `method_id`,
`method_type`, `floor_pt`, `floor_origin` — and DROPS the rest. The authority
is discarded at exactly the boundary where the floor is decided, so everything
downstream of that copy is structurally unable to tell a proposal from a
confirmation. The fix is to stop dropping it, not to invent it.

THE FOUR STAGES
---------------
`OWNER_CONFIRMED` is the only one that is a confirmation. The other three are
kept apart from each other because §AA3(a) requires it: "a method that came
from `propose_zones` is a *proposal*; a method that came from a fixture is a
*fixture*; a method an owner confirmed is neither."

`UNATTRIBUTED` is deliberately NOT called `FIXTURE`. What is detectable is the
ABSENCE of the builder's signature — a record with no `authority_state` did not
come out of `build_production_methods` — and that is a weaker claim than "a
test wrote this". The two coincide in this repo today, and that is a fact with
evidence rather than a definition: `build_production_methods` is the only
producer of a `container_production_method/1.0` record in non-test code
(`apps/ire/container_production_method.py:226`), reached from the single call
site `apps/pipeline/targets/container/__init__.py:1014`. If a second producer
ever appears, `UNATTRIBUTED` stays true about its records and `FIXTURE` would
have quietly become a lie.

TWO CONSTRAINTS THAT LIVE OUTPUT NEVER REACHES (§AA's WI-K precedent)
--------------------------------------------------------------------
Stated here because §AA made it a standing rule that a fix whose effect on
production output is zero says so next to itself, not in a footnote.

1. `USER_REQUESTED` is unreachable today. `build_production_methods` selects it
   when a zone's `source` is `EXPLICIT_USER_FACT`, and no production code path
   ever sets that on a zone: `make_zone` defaults `source=SRC_INFERRED` and
   nothing overrides it. So the branch exists, is tested, and has never run on
   a real container.
2. `OWNER_CONFIRMED` is unreachable today. The builder hard-codes
   `confirmed_by: ""` and `authority_state` is never
   `VERIFIED_MANUFACTURER_CAPABILITY`, by construction and on purpose — the
   module docstring calls that "the intended, honest state". So EVERY method on
   EVERY live container is `MACHINE_PROPOSED`, and this module's answer for
   live output is known in advance. It is still worth recording, because the
   record is what stops the next reader from having to rediscover it.

ITS EFFECT ON EMITTED OUTPUT IS ZERO, AND THAT IS MEASURED
----------------------------------------------------------
§AA made it a standing rule that a fix whose effect on production output is
nil says so beside itself — and §Z1 punished attribution by inspection, so the
claim is measured rather than reasoned from the diff. The dropper sheet was
emitted twice against the LIVE methods record, once from a detached worktree
at HEAD and once from this tree, and compared byte for byte: 47,728 bytes both
times, 64 text runs both times, text-geometry hash `6246ca5b1132d697` both
times. The only differing bytes are ReportLab's `/CreationDate`, `/ModDate`
and random `/ID`. Nothing about the artwork changed. What changed is what the
record is able to SAY about the artwork, which is the whole of §AA3.

WHAT THIS DOES NOT DO
---------------------
It does not make `propose_zones` smarter — §AA3(e) forbids it by name, because
improving the proposal makes the misreading harder to notice. `make_zone`'s
default is untouched. It does not reopen supplier outreach, permanently
withdrawn by §C2 and not resurrected by implication (§AA3(d)). It does not
decide whether an owner's stated design intent CONFIRMS a method as distinct
from verifying a press can hold it — that is an owner's ruling, it is recorded
as an open question rather than settled here, and `USER_REQUESTED` is reported
as its own stage precisely so that ruling has something to attach to.

Pure: no Django, no ORM, no network.
"""
from __future__ import annotations

SCHEMA = "container_method_provenance/1.0"

# --- the stages (§AA3(a)) ----------------------------------------------------

#: a human confirmed this method. The only stage that is a confirmation.
STAGE_OWNER_CONFIRMED = "OWNER_CONFIRMED"

#: the owner asked for this technique as DESIGN INTENT (zone source
#: EXPLICIT_USER_FACT → USER_REQUESTED_UNVERIFIED). Not a machine proposal and
#: not a fixture, so §AA3(a)'s three-way does not hold it — it gets its own
#: name rather than being rounded to the nearest one. Whether it confirms the
#: METHOD is an owner question this module does not answer.
STAGE_USER_REQUESTED = "USER_REQUESTED_DESIGN_INTENT"

#: `build_production_methods` derived it from a PROPOSED zone's
#: `permitted_techniques`. A proposal. Every live container is here.
STAGE_MACHINE_PROPOSED = "MACHINE_PROPOSED"

#: the record carries no `authority_state`, so it did not come from
#: `build_production_methods` and no stage of the pipeline claims it. See the
#: module docstring for why this is not called FIXTURE.
STAGE_UNATTRIBUTED = "UNATTRIBUTED"

#: the method record says its technique is not supported at all.
STAGE_UNSUPPORTED = "UNSUPPORTED"

#: §AA3(a) — exactly one stage is a confirmation. A frozenset of one is not
#: over-engineering: it is the place an owner ruling about STAGE_USER_REQUESTED
#: would land, and a bare `== STAGE_OWNER_CONFIRMED` scattered over three
#: modules would not have one.
CONFIRMED_STAGES = frozenset({STAGE_OWNER_CONFIRMED})

#: §AA3(a). Reported per surface; never silently absent.
METHOD_UNCONFIRMED = "CONTAINER_PRINT_METHOD_UNCONFIRMED"

_STAGE_MEANING = {
    STAGE_OWNER_CONFIRMED: "a human confirmed this method",
    STAGE_USER_REQUESTED: "the owner asked for this technique as design "
                          "intent; no manufacturer capability was verified",
    STAGE_MACHINE_PROPOSED: "propose_zones proposed the technique this method "
                            "was derived from — a PROPOSAL, never authority",
    STAGE_UNATTRIBUTED: "no stage claims this method: the record carries no "
                        "authority_state, so it did not come from "
                        "build_production_methods",
    STAGE_UNSUPPORTED: "the record states its technique is unsupported",
}

RULE = (
    "OWNER_BLOCKER_CLEARANCE.md §AA3 — a container's print method records "
    "WHICH STAGE supplied it. A method that came from propose_zones is a "
    "PROPOSAL, a method that came from a hand-written record is UNATTRIBUTED, "
    "and a method an owner confirmed is neither. Only OWNER_CONFIRMED is a "
    "confirmation; every other stage leaves the surface's floor a disclosed "
    "assumption and the typography axis blocking on it (§AA3(b), (c))."
)

#: §AA3(c) — what the number on an unconfirmed surface actually is.
ASSUMPTION = (
    "the floor on this surface is an ASSUMPTION, not a fact. It is the "
    "capability table's row for a method type that no stage of this pipeline "
    "confirmed for this container, so it describes what that KIND of press "
    "holds and not what this container is printed with. It may keep shipping "
    "(§AA3(c)); it may not present itself as confirmed while it does."
)

#: §AA3(b)/(c) — what a verdict on one of these surfaces is worth. Carefully
#: NOT a claim that the axis blocks BECAUSE of this: it does not, `below_floor`
#: says why in full, and a constant asserting a block that does not happen
#: would be the same defect as a fallback presenting as a measurement.
UNCONFIRMED_NOTE = (
    "OWNER_BLOCKER_CLEARANCE.md §AA3 — the floor on these surfaces came from "
    "a print method no stage confirmed, so a run that clears it has been "
    "shown to clear a GUESS and not to be legible. The typography axis's "
    "verdict does not rest on this: what blocks it is a run found below its "
    "floor, or a surface whose product copy is drawn only as a depiction "
    "(§BH50(f)(1)); when neither stands, the verdict becomes a universal "
    "claim of legibility resting on a technique that entered as a default "
    "argument value. Whether that verdict should instead be UNMEASURED is an "
    "owner ruling — taking it here would repeal §W2's PASS branch, including "
    "the 2.0 pt bottom inkjet code §W2 names as a FALSE FAIL. Surfaces "
    "affected: ")


def method_stage(method) -> str:
    """Which stage supplied this single method record.

    Reads only what the record carries. A method that has been through
    `build_production_methods` always has `authority_state`; one that has not
    is `UNATTRIBUTED`, and the distinction is the whole point of the function.
    """
    from apps.ire.container_production_method import (
        INFERRED_NONAUTHORITATIVE, UNSUPPORTED, USER_REQUESTED_UNVERIFIED,
        VERIFIED_MANUFACTURER_CAPABILITY)

    if not isinstance(method, dict):
        return STAGE_UNATTRIBUTED
    authority = method.get("authority_state")
    if authority is None:
        # No builder signature. Not "a fixture" — an absence of attribution.
        return STAGE_UNATTRIBUTED
    if authority == VERIFIED_MANUFACTURER_CAPABILITY:
        return STAGE_OWNER_CONFIRMED
    # A non-empty `confirmed_by` is a human putting their name to it. The
    # builder writes "" and nothing in the repo overwrites it today, so this
    # branch is the hook a future confirmation flow lands on rather than a
    # state that occurs. It is checked BEFORE the unverified states so that a
    # confirmation cannot be masked by the authority field it travels with.
    if str(method.get("confirmed_by") or "").strip():
        return STAGE_OWNER_CONFIRMED
    if authority == USER_REQUESTED_UNVERIFIED:
        return STAGE_USER_REQUESTED
    if authority == UNSUPPORTED:
        return STAGE_UNSUPPORTED
    if authority == INFERRED_NONAUTHORITATIVE:
        return STAGE_MACHINE_PROPOSED
    # An authority_state this module does not know. Not confirmed, and not
    # quietly folded into MACHINE_PROPOSED: a stage nobody recognises is
    # unattributed, which is the honest answer and the blocking one.
    return STAGE_UNATTRIBUTED


def stage_meaning(stage: str) -> str:
    return _STAGE_MEANING.get(stage, "unrecognised stage")


def is_confirmed(stage: str) -> bool:
    return stage in CONFIRMED_STAGES


def surface_provenance(methods_record) -> dict:
    """surface → who supplied the print method(s) recorded for it.

    ``{"stages": [...], "confirmed": bool, "methods": [...]}``. A surface is
    confirmed only when EVERY method recorded for it is confirmed: one
    unconfirmed method is enough to make the surface's floor an assumption,
    because the floor is resolved across all of them.

    Surfaces with NO recorded method do not appear. That is not an oversight —
    §W2(b) already rules that case, the record already says the word FALLBACK,
    and a second disclosure saying the fallback is unconfirmed would add a
    word without adding a fact. The defect §AA3 names is a RECORDED method
    presenting as a confirmed one.
    """
    by_surface: dict[str, list[dict]] = {}
    for method in (methods_record or {}).get("methods") or []:
        if not isinstance(method, dict):
            continue
        stage = method_stage(method)
        for surface in method.get("target_surfaces") or []:
            if surface is None:
                continue
            by_surface.setdefault(str(surface), []).append({
                "method_id": method.get("method_id"),
                "method_type": method.get("method_type"),
                "stage": stage,
                "confirmed": is_confirmed(stage),
                "authority_state": method.get("authority_state"),
                "verification_source": method.get("verification_source"),
                "confirmed_by": method.get("confirmed_by") or "",
                "stage_meaning": stage_meaning(stage),
            })

    resolved = {}
    for surface, methods in sorted(by_surface.items()):
        methods = sorted(methods, key=lambda m: str(m["method_id"]))
        resolved[surface] = {
            "stages": sorted({m["stage"] for m in methods}),
            "confirmed": all(m["confirmed"] for m in methods),
            "methods": methods,
        }
    return resolved


def unconfirmed_surfaces(provenance) -> list[str]:
    """The surfaces whose recorded method nobody confirmed, sorted."""
    return sorted(s for s, r in (provenance or {}).items()
                  if not r["confirmed"])


def unconfirmed_reason(provenance) -> str:
    """§AA3(b)'s sentence, with the surfaces and stages named in it."""
    parts = []
    for surface in unconfirmed_surfaces(provenance):
        entry = provenance[surface]
        types = "/".join(str(m["method_type"]) for m in entry["methods"])
        stages = "/".join(entry["stages"])
        parts.append(f"{surface} ({types} — {stages})")
    return UNCONFIRMED_NOTE + ", ".join(parts)


def measure_method_provenance(methods_record) -> dict:
    """``container_method_provenance/1.0`` for a methods record."""
    provenance = surface_provenance(methods_record)
    unconfirmed = unconfirmed_surfaces(provenance)
    return {
        "schema_version": SCHEMA,
        "rule": RULE,
        "by_surface": provenance,
        "unconfirmed_surfaces": unconfirmed,
        "any_unconfirmed": bool(unconfirmed),
        "all_confirmed": bool(provenance) and not unconfirmed,
        "codes": [METHOD_UNCONFIRMED] if unconfirmed else [],
        "assumption": ASSUMPTION if unconfirmed else None,
        "reason": unconfirmed_reason(provenance) if unconfirmed else None,
        "surfaces_examined": sorted(provenance),
        "measured_by": "apps.ire.container_method_provenance."
                       "measure_method_provenance",
    }


__all__ = ["ASSUMPTION", "CONFIRMED_STAGES", "METHOD_UNCONFIRMED", "RULE",
           "SCHEMA", "STAGE_MACHINE_PROPOSED", "STAGE_OWNER_CONFIRMED",
           "STAGE_UNATTRIBUTED", "STAGE_UNSUPPORTED", "STAGE_USER_REQUESTED",
           "UNCONFIRMED_NOTE", "is_confirmed", "measure_method_provenance",
           "method_stage", "stage_meaning", "surface_provenance",
           "unconfirmed_reason", "unconfirmed_surfaces"]
