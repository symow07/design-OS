"""WI-X / §AB1 — the label's CONSTRUCTION, recorded at its true provenance.

§AB1 ruled that the label becomes MULTI-LAYER — a peel-reveal or booklet label
on the same bottle — and that the owner-sourced reduction of the mandatory set
runs anyway. Both, not one as a fallback for the other.

This module records that decision. It does NOT draw it. There is no dieline
here, no peel geometry, no second artwork carrier and no zone: §AB1's WI-X is
"a provenance and structure item, not a dieline", and a module that quietly
grew a layout would be answering a question the owner reserved.

WHAT THE FORM IS FOR. WI-N (§AA3) found a machine's default argument and a
hand-written fixture returning the same provenance string, so a PROPOSAL read
as a CONFIRMATION. The fix was to record WHICH STAGE supplied a fact rather
than which table was read. §AB1(b) asks for that form here, and the reason is
the same in reverse: the multi-layer target is an owner DECISION, which is
real authority over what we are trying to build and NO authority at all over
whether a converter can build it. Those are two facts and this module keeps
them in two fields.

TWO CONDITIONS BLOCK, AND ONLY ONE OF THEM IS THE ONE §AB1 NAMED.

  1. MANUFACTURABILITY IS UNCONFIRMED — §AB1(b), and stated by the ruling
     itself. §C2 withdrew supplier outreach permanently, so nobody can confirm
     that our converter runs a multi-layer label at this size. `SUPPLIER_
     CONFIRMED` is therefore a state no action authorized in this repository
     can reach. That is written down as a property of the record and NOT as a
     request: §C2 is permanent, this module does not reopen it, and a comment
     proposing outreach as the remedy would be reopening it in prose.

     SCOPED TO THE CONSTRUCTION §AB1 RULED ON. The block is the multi-layer
     target's. Single-layer is what this repository already prints, and
     blocking it would extend a ruling past its subject — see
     `measure_label_construction`, where the consequence that forced the
     scoping is written out.

  2. THE CONFIRMED ZONE SET DOES NOT CONTAIN THE SURFACE THE TARGET IMPLIES —
     found here, not given by the ruling, and reported under AB0(b) because it
     is a measurement that a ruling would have to bet against. ES3083's
     confirmed set has THREE members and one documented exclusion; a
     peel-reveal or booklet label carries printable faces none of them names,
     and §X2(a) makes adding one a CONTRACT change — new zone confirmation,
     new `zone_set_hash`, re-derived `combined_confirmation_hash` — "not a
     layout decision a composer or an executor may reach for".

     THE THREE ARE NOT SPELLED OUT HERE, and that is §AC2(b): *"No zone name
     appears anywhere in the multi-layer path."* They were, until WI-Z. The
     names now live in the contract that confirms them and in the guard that
     pins this module to it (`test_wiz_zone_contract.py`), which asserts this
     file contains none. Nothing is lost by not typing them: every record this
     module emits carries `confirmed_zones_examined`, which lists the zones it
     was actually handed rather than the ones somebody typed a sprint ago.

     §AB1(a) is not in tension with this. It says the multi-layer label adds no
     separate physical OBJECT, and that is about the pack: no carton, no
     leaflet, no second pick in assembly. It is silent on the zone contract,
     which is a different mechanism with its own hashes. So the target is
     authorized and the surface it needs is not yet contracted, and this module
     reports that rather than resolving it in either direction. Performing the
     contract change here would be exactly the reach §X2(a) forbids; declaring
     the target unreachable because of it would be inventing a veto §AB1 did
     not give.

WHAT IS NOT RULED, AND IS ENFORCED RATHER THAN NOTED. §AB1(f) — "the layer
count is NOT yet a number. Two is the working assumption and it is not ruled.
Do not build anything that assumes exactly two." `require_layer_count` RAISES.
A constant a consumer could multiply by would be a number, and a docstring
asking politely that nobody multiply by it is how working assumptions become
dimensions. The variant is unruled the same way: §AB1 names peel-reveal AND
booklet and picks neither, so `RULED_VARIANT` is None and both appear in
`VARIANTS_NAMED_NOT_RULED`.

§X2 IS NOT LIFTED. §AB1(a) narrows what the ban was ABOUT; it does not repeal
it. The carton, the leaflet-in-a-box, the outer wrap and the larger container
all remain banned, and `is_banned_separate_object` exists so that a future
consumer cannot reintroduce one under the multi-layer heading by calling it a
layer.

Pure: no Django, no ORM, no network, no geometry.
"""
from __future__ import annotations

SCHEMA = "container_label_construction/1.0"

# --- what is being built (§AB1) ----------------------------------------------

#: One printed face on one carrier. Everything in this repository today, and
#: the state every measurement in it was taken against.
SINGLE_LAYER = "SINGLE_LAYER"

#: §AB1's ruled target. One label, applied once, to one bottle, carrying more
#: than one printable face.
MULTI_LAYER = "MULTI_LAYER"

#: §AB1 names both and rules neither. Recorded as named-not-ruled rather than
#: omitted, because "the owner mentioned it" and "the owner chose it" are
#: different facts and the second one is the one that is missing.
VARIANTS_NAMED_NOT_RULED = ("PEEL_REVEAL", "BOOKLET")

#: No variant is ruled. See `VARIANTS_NAMED_NOT_RULED`.
RULED_VARIANT = None

# --- who supplied it (the WI-N shape) ----------------------------------------

#: an owner ruling chose this target. Authority over WHAT WE ARE BUILDING.
#: NOT a manufacturability claim — §AB1(b) says so in the ruling itself.
STAGE_OWNER_DIRECTED = "OWNER_DIRECTED"

#: a converter confirmed it can make this at this size. The ONLY stage that
#: moves manufacturability to CONFIRMED, and a state no action authorized in
#: this repository can reach (§C2 permanent). Present so the block has
#: something to be waiting for; absent from any live record.
STAGE_SUPPLIER_CONFIRMED = "SUPPLIER_CONFIRMED"

#: the pipeline derived it. A proposal, never authority.
STAGE_MACHINE_PROPOSED = "MACHINE_PROPOSED"

#: nothing claims it. Not "default" and not "fixture" — the absence of a
#: signature is a weaker and more durable claim than a guess at whose it was.
STAGE_UNATTRIBUTED = "UNATTRIBUTED"

#: §AB1(b). Exactly one stage confirms MANUFACTURABILITY, and it is not the
#: one that chose the target. A frozenset of one is where an owner ruling
#: about some other stage would land.
MANUFACTURABILITY_CONFIRMING_STAGES = frozenset({STAGE_SUPPLIER_CONFIRMED})

CONFIRMED = "CONFIRMED"
UNCONFIRMED = "UNCONFIRMED"

_STAGE_MEANING = {
    STAGE_OWNER_DIRECTED: "an owner ruling chose this construction; no "
                          "manufacturer capability was verified",
    STAGE_SUPPLIER_CONFIRMED: "a converter confirmed it can make this at this "
                              "size",
    STAGE_MACHINE_PROPOSED: "the pipeline derived it — a PROPOSAL, never "
                            "authority",
    STAGE_UNATTRIBUTED: "no stage claims this construction: the record carries "
                        "no provenance_stage",
}

# --- codes -------------------------------------------------------------------

#: §AB1(b). The axis blocks on this.
MANUFACTURABILITY_UNCONFIRMED = "LABEL_CONSTRUCTION_MANUFACTURABILITY_UNCONFIRMED"

#: §AB1(f). Raised, not returned — see `require_layer_count`.
LAYER_COUNT_NOT_RULED = "LABEL_LAYER_COUNT_NOT_RULED"

#: Found by WI-X rather than given by §AB1. See the module docstring, 2.
ZONE_SET_LACKS_SURFACE = "LABEL_CONSTRUCTION_ZONE_SET_LACKS_SURFACE"

#: §X2/§AB1(a). Fires when something banned is offered as a "layer".
BANNED_SEPARATE_OBJECT = "LABEL_CONSTRUCTION_BANNED_SEPARATE_OBJECT"

RULE = (
    "OWNER_BLOCKER_CLEARANCE.md §AB1 — the label becomes MULTI-LAYER on the "
    "same bottle, chosen by the owner and manufacturable by nobody's "
    "confirmation. The construction records WHICH STAGE supplied it: a target "
    "an owner directed is authority over what is being built and no evidence "
    "at all that it can be built, and only SUPPLIER_CONFIRMED is the second "
    "thing. Every other stage leaves manufacturability UNCONFIRMED and the "
    "axis blocking (§AB1(b))."
)

#: §AB1(b) — what the target actually is while it is unconfirmed.
ASSUMPTION = (
    "the manufacturability of this construction is an ASSUMPTION, not a fact. "
    "An owner directed the target; no converter has said it can be made at "
    "this size, and §C2 withdrew supplier outreach permanently, so no action "
    "authorized in this repository can produce that confirmation. §AB1(b) "
    "rules this an honest state and not a reason to avoid the decision: a "
    "target chosen and not yet verifiable is recorded as chosen and not yet "
    "verified. It may keep being the target while it is unconfirmed; it may "
    "not present itself as confirmed while it does."
)

#: The second block. Deliberately NOT phrased as a veto — see the docstring.
ZONE_NOTE = (
    "the confirmed zone set does not contain a printable surface for this "
    "construction: a multi-layer label carries faces none of the confirmed "
    "zones names, and the zones actually examined are listed beside this note "
    "in `confirmed_zones_examined` rather than named here (§AC2(b)). "
    "§X2(a) makes adding a zone a CONTRACT change — new zone confirmation, "
    "new zone_set_hash, re-derived combined_confirmation_hash — and not a "
    "decision a composer or an executor may reach for. §AB1 authorized the "
    "TARGET; it did not perform that contract change and neither does this "
    "module. This is reported as a second condition on the same axis rather "
    "than as a refusal of the target, because inventing a veto the owner did "
    "not give is the same defect as inventing a confirmation he did not give."
)

#: §X2, restated by §AB1(a): the ban is narrowed in scope, not repealed. A
#: multi-layer label is one carrier; each of these is a second OBJECT.
BANNED_SEPARATE_OBJECTS = ("CARTON", "LEAFLET_IN_BOX", "OUTER_WRAP",
                           "LARGER_CONTAINER")


class LabelLayerCountNotRuled(Exception):
    """§AB1(f). Raised by `require_layer_count`; carries the code."""

    code = LAYER_COUNT_NOT_RULED


def require_layer_count():
    """Always raises. §AB1(f) — "do not build anything that assumes exactly
    two", enforced rather than requested.

    There is deliberately no constant here holding the working assumption as
    an integer. Two IS the working assumption and §AB1 says so in as many
    words, but a module-level `2` is a number a consumer can multiply a
    surface area by, and the distance from that to a dimension nobody ruled is
    one commit. The assumption lives in the ruling, where it is a sentence.
    """
    raise LabelLayerCountNotRuled(
        f"{LAYER_COUNT_NOT_RULED}: §AB1(f) — the layer count is not yet a "
        "number. Two is the owner's working assumption and is NOT ruled; the "
        "count follows from WI-W's ledger, which reports what each surface "
        "budget buys. Ask for a budget, not for a count."
    )


def is_banned_separate_object(kind) -> bool:
    """§X2 / §AB1(a). True when `kind` is a second physical object rather than
    a layer of one label. §AB1(a) narrowed what the ban was ABOUT; it did not
    lift it, and this is the thing that stops a carton re-entering under the
    multi-layer heading by being called a layer."""
    return str(kind or "").strip().upper().replace(" ", "_") \
        in BANNED_SEPARATE_OBJECTS


def construction_stage(record) -> str:
    """Which stage supplied this construction record. Reads only what the
    record carries; an unsigned record is UNATTRIBUTED, and that distinction
    is the whole point of the function."""
    if not isinstance(record, dict):
        return STAGE_UNATTRIBUTED
    stage = record.get("provenance_stage")
    if stage in _STAGE_MEANING:
        return str(stage)
    return STAGE_UNATTRIBUTED


def stage_meaning(stage: str) -> str:
    return _STAGE_MEANING.get(stage, _STAGE_MEANING[STAGE_UNATTRIBUTED])


def manufacturability(stage: str) -> str:
    """§AB1(b). CONFIRMED only from a stage that confirms manufacturability —
    which is not the stage that chose the target."""
    return CONFIRMED if stage in MANUFACTURABILITY_CONFIRMING_STAGES \
        else UNCONFIRMED


def zone_set_covers(construction, confirmed_zones, *,
                    contracted_count=None) -> bool:
    """Whether the confirmed zone set already contains a surface for this
    construction. True for SINGLE_LAYER on any non-empty set; for MULTI_LAYER
    it needs a surface beyond the contracted baseline, so it is False until a
    contract change lands. See the module docstring, 2.

    §AC2(b) — NO ZONE NAME APPEARS IN THIS FUNCTION ANY MORE, and the change is
    not cosmetic. It read the confirmed set MINUS a three-element literal set
    of the contract's names, typed here; the names themselves are in the
    contract module and in the guard, and are deliberately not repeated in this
    sentence, because §AC2(b)'s stated mechanism is *"an invented name in a
    comment becomes an invented name in a variable becomes an invented name in
    an emitter"* and a docstring quoting them to explain their removal is still
    step one of that chain. §AC2(a) gives the reason the rule exists: naming
    the surfaces fixes the count, and this module has no authority over the
    count.

    So the baseline arrives as a COUNT the caller supplies. `contracted_count`
    absent means the caller did not state a baseline, and the multi-layer
    answer is then **False** — fail-closed, because "I was not told" and "there
    is room" are different states and only one of them is safe to guess.

    WHAT CHANGED BEHAVIOURALLY, stated because a predicate swapped quietly is
    how a gate stops gating. Old: "is there a name outside the three?" New:
    "are there more surfaces than the baseline has?" They agree whenever the
    confirmed set CONTAINS the baseline, which is the only case the contract
    permits, and they diverge if somebody ever confirms three DIFFERENT zones —
    old True, new False. That divergence cannot arrive silently: WI-X's
    `test_the_three_zones_are_the_ones_the_contract_confirms` pins the
    confirmed set to the contract source and goes red first. The count-based
    form is safe BECAUSE the name-pinning guard exists; the two are a pair and
    neither should be deleted without the other.
    """
    zones = {str(z) for z in (confirmed_zones or [])}
    if not zones:
        return False
    if construction != MULTI_LAYER:
        return True
    if contracted_count is None:
        return False
    return len(zones) > int(contracted_count)


def measure_label_construction(record, *, confirmed_zones=(),
                               contracted_count=None) -> dict:
    """``container_label_construction/1.0`` for a construction record.

    Shaped like `measure_method_provenance`: the codes, the assumption and the
    reason are all absent when there is nothing to disclose, so a reader never
    has to distinguish "no finding" from "the field was not populated".
    """
    stage = construction_stage(record)
    construction = str((record or {}).get("construction") or SINGLE_LAYER) \
        if isinstance(record, dict) else SINGLE_LAYER
    made = manufacturability(stage)
    covered = zone_set_covers(construction, confirmed_zones,
                              contracted_count=contracted_count)

    # §AB1(b) is scoped to the construction it ruled ON. The field above stays
    # literally true for every stage — no converter has confirmed anything,
    # because §C2 means no converter has been asked — but the BLOCK belongs to
    # the multi-layer target, which is what §AB1 put in question. Single-layer
    # is what this repository already builds; blocking it would extend a ruling
    # past its subject, which is the same class of error as ignoring one.
    #
    # This is not a preference. Wire the axis below into the fidelity report
    # without this line and every container in the repository blocks, all of
    # them correctly single-layer — a gate that fails everything it measures
    # has stopped measuring. That consequence is what scoped it.
    in_question = construction != SINGLE_LAYER

    codes = []
    if in_question and made != CONFIRMED:
        codes.append(MANUFACTURABILITY_UNCONFIRMED)
    if not covered:
        codes.append(ZONE_SET_LACKS_SURFACE)

    return {
        "schema_version": SCHEMA,
        "rule": RULE,
        "construction": construction,
        "variant": RULED_VARIANT,
        "variants_named_not_ruled": list(VARIANTS_NAMED_NOT_RULED),
        "layer_count": None,                     # §AB1(f). Never a number.
        "provenance_stage": stage,
        "stage_meaning": stage_meaning(stage),
        "manufacturability": made,
        "zone_set_covers_construction": covered,
        "confirmed_zones_examined": sorted(str(z) for z in
                                           (confirmed_zones or [])),
        "codes": codes,
        "assumption": ASSUMPTION if MANUFACTURABILITY_UNCONFIRMED in codes
                      else None,
        "zone_note": None if covered else ZONE_NOTE,
        "blocking": bool(codes),
        "measured_by": "apps.ire.container_label_construction."
                       "measure_label_construction",
    }


def label_construction_axis(report) -> dict:
    """The blocking axis (§AB1(b)), in the vocabulary `container_fidelity`
    already uses rather than a second one invented alongside it.

    UNMEASURED, not MEASURED_FAIL. Nothing here has been shown to be WRONG —
    a converter may well run this label tomorrow. What is true is that the
    claim has never been measured, and `required: True` is what makes an
    unmeasured required axis block instead of passing quietly. §AB1(b) says
    the axis STAYS blocking until a real supplier confirms it, and
    `UNMEASURED` + `required` is the existing machinery for exactly that.
    """
    from apps.ire.container_fidelity import MEASURED_PASS, UNMEASURED

    blocking = bool((report or {}).get("blocking"))
    return {
        "axis": "label_construction",
        "state": UNMEASURED if blocking else MEASURED_PASS,
        "required": True,
        "codes": list((report or {}).get("codes") or []),
        "detail": (report or {}).get("assumption") or "",
        "zone_note": (report or {}).get("zone_note"),
    }


__all__ = ["ASSUMPTION", "BANNED_SEPARATE_OBJECT", "BANNED_SEPARATE_OBJECTS",
           "CONFIRMED", "LAYER_COUNT_NOT_RULED", "LabelLayerCountNotRuled",
           "MANUFACTURABILITY_CONFIRMING_STAGES",
           "MANUFACTURABILITY_UNCONFIRMED", "MULTI_LAYER", "RULE",
           "RULED_VARIANT", "SCHEMA", "SINGLE_LAYER", "STAGE_MACHINE_PROPOSED",
           "STAGE_OWNER_DIRECTED", "STAGE_SUPPLIER_CONFIRMED",
           "STAGE_UNATTRIBUTED", "UNCONFIRMED", "VARIANTS_NAMED_NOT_RULED",
           "ZONE_NOTE", "ZONE_SET_LACKS_SURFACE", "construction_stage",
           "is_banned_separate_object", "label_construction_axis",
           "manufacturability", "measure_label_construction",
           "require_layer_count", "stage_meaning", "zone_set_covers"]
