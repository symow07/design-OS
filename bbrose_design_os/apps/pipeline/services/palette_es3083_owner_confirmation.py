"""PALT-M4C §1 — the owner's confirmation of the ES3083 design intent.

The owner confirmed VISIBLE COMPOSITION only. That distinction is the
whole point of this record: a confirmation that quietly widened into
dimensional or manufacturing authority would be the failure this
programme has guarded against at every gate.

So the record carries both halves. ``CONFIRMED_VISIBLE_COMPOSITION``
lists what the owner actually ruled on. ``EXPLICITLY_NOT_AUTHORIZED``
lists, verbatim from the directive, what this confirmation is not
authority for — and ``check_authority()`` refuses when a caller tries to
draw one of those conclusions from it.

Pantone 621 C and 627 C stay NAMED. No licensed conversion exists here,
and the directive says not to convert them numerically.
"""
from __future__ import annotations

from apps.pipeline.services import palette_design_intent as di
from apps.pipeline.services import palette_es3083_intent as es
from apps.pipeline.services import palette_intent_confirmation as pic

SCHEMA = "palette_es3083_owner_confirmation/1.0"

OWNER = "OWNER"
CONCEPT = "ES3083吸塑_展盒刀线"

#: What the owner ruled on, exactly as the directive states it.
CONFIRMED_VISIBLE_COMPOSITION = {
    "PAN_SHAPE": {"value": "RECTANGULAR",
                  "level": di.HARD, "field": "pan_shapes"},
    "PAN_LAYOUT": {"value": "4 x 3", "level": di.HARD, "field": None},
    "PAN_COUNT": {"value": 12, "level": di.HARD, "field": "pan_count"},
    "ROWS": {"value": 3, "level": di.HARD, "field": "rows"},
    "COLUMNS": {"value": 4, "level": di.HARD, "field": "columns"},
    "BRAND": {"value": "BBROSE", "level": di.HARD, "field": None},
    "PRODUCT_TYPE": {"value": "EYE SHADOW", "level": di.HARD,
                     "field": None},
    "PRODUCT_NAME": {"value": "OUTER GLOW", "level": di.HARD,
                     "field": None},
    "COLOUR_REFERENCES": {"value": ["PANTONE 621 C", "PANTONE 627 C"],
                          "level": di.HARD, "field": "colour_zones"},
    "ARTWORK_ELEMENTS": {
        "value": ["BBROSE", "EYE SHADOW", "OUTER GLOW",
                  "shade-label strips", "visible typography hierarchy",
                  "product colour zones", "palette artwork zones"],
        "level": di.HARD, "field": "typography_zones"},
}

#: Verbatim from the directive. A confirmation of visible composition is
#: not evidence for any of these.
EXPLICITLY_NOT_AUTHORIZED = (
    "exact pan dimensions",
    "exact case dimensions",
    "tolerances",
    "wall thickness",
    "hinge construction",
    "clasp construction",
    "hidden geometry",
    "thermoforming details",
    "manufacturing feasibility",
)

PANTONE_POLICY = {
    "state": "NAMED_REFERENCE_NOT_NUMERICALLY_CONVERTED",
    "tokens": ["PANTONE 621 C", "PANTONE 627 C"],
    "why": "the directive forbids numeric conversion unless licensed "
           "authoritative colour data is available; none is present here",
    "governs": "THE_NAMED_TOKEN",
}


class UnauthorizedInference(PermissionError):
    """Raised when the visible-composition confirmation is used as
    authority for something the owner did not confirm."""


def check_authority(claim: str) -> None:
    """Refuse a claim this confirmation cannot support."""
    low = claim.lower()
    for banned in EXPLICITLY_NOT_AUTHORIZED:
        if banned in low:
            raise UnauthorizedInference(
                f"the ES3083 owner confirmation covers VISIBLE COMPOSITION "
                f"only and is not authority for {banned!r}. Those remain "
                "provisional or unresolved.")


def confirmation_record() -> pic.ConfirmationRecord:
    """The owner's actions against the drafted intent."""
    draft = es.build_es3083_intent()
    rec = pic.ConfirmationRecord(concept_reference=draft.concept_reference,
                                 draft_identity=draft.identity())
    # The draft read pan_count / rows / columns as SOFT at 0.55 because the
    # render was too small to count with certainty. The owner has now
    # counted them, so they become HARD by owner statement — not by the
    # engine gaining confidence it never had.
    for name, value in (("pan_count", 12), ("rows", 3), ("columns", 4)):
        rec.apply(pic.ConfirmationAction(route="BASELINE_REPLAY", 
            field_name=name, action=pic.CORRECT, actor=OWNER,
            new_value=value, note="owner-counted from the selected design"))
        rec.apply(pic.ConfirmationAction(route="BASELINE_REPLAY", 
            field_name=name, action=pic.RECLASSIFY, actor=OWNER,
            new_level=di.HARD,
            note="owner-visible constraint, not an engine inference"))
    rec.apply(pic.ConfirmationAction(route="BASELINE_REPLAY", 
        field_name="pan_shapes", action=pic.CONFIRM, actor=OWNER,
        note="RECTANGULAR confirmed as a HARD visible constraint"))
    rec.apply(pic.ConfirmationAction(route="BASELINE_REPLAY", 
        field_name="colour_zones", action=pic.CONFIRM, actor=OWNER,
        note="Pantone 621 C / 627 C confirmed as NAMED references; not "
             "converted numerically"))
    rec.apply(pic.ConfirmationAction(route="BASELINE_REPLAY", 
        field_name="typography_zones", action=pic.CONFIRM, actor=OWNER,
        note="BBROSE / EYE SHADOW / OUTER GLOW confirmed"))
    rec.apply(pic.ConfirmationAction(route="BASELINE_REPLAY", 
        field_name="shade_names", action=pic.CONFIRM, actor=OWNER,
        note="shade-label strips confirmed as present"))
    # Visible composition only: the owner did NOT rule on the mechanism.
    for name in ("hinge_location", "mirror_presence"):
        rec.apply(pic.ConfirmationAction(route="BASELINE_REPLAY", 
            field_name=name, action=pic.MARK_UNRESOLVED, actor=OWNER,
            note="hinge and clasp construction are explicitly outside this "
                 "confirmation"))
    return rec


def confirmed_intent():
    """The intent carrying the owner's decisions, draft left intact."""
    draft = es.build_es3083_intent()
    return pic.apply_confirmations(draft, confirmation_record())


def owner_confirmation() -> dict:
    """The durable record."""
    draft = es.build_es3083_intent()
    rec = confirmation_record()
    confirmed = pic.apply_confirmations(draft, rec)
    return {
        "record_type": SCHEMA,
        "concept": CONCEPT,
        "selected_concept": "ES3083吸塑_展盒刀线 BBROSE OUTER GLOW "
                            "EYESHADOW PALETTE",
        "pilot_roles": {
            "PALT_P1A": "ENGINEERING_REGRESSION_FIXTURE — 3 x 3 round pans, "
                        "preserve unchanged",
            "PALT_P1B": "OWNER_DESIGN_INTENT_PILOT — ES3083 OUTER GLOW"},
        "confirmed_visible_composition": {
            k: {"value": v["value"], "constraint_level": v["level"]}
            for k, v in CONFIRMED_VISIBLE_COMPOSITION.items()},
        "scope": "VISIBLE_COMPOSITION_ONLY",
        "explicitly_not_authorized": list(EXPLICITLY_NOT_AUTHORIZED),
        "pantone_policy": dict(PANTONE_POLICY),
        "draft_identity": draft.identity(),
        "confirmation_identity": rec.identity(),
        "confirmed_intent_identity": confirmed.identity(),
        "actions": rec.to_dict()["actions"],
        "confirmed_field_count": sum(
            1 for f in confirmed.fields if f.is_design_authority),
        "still_unresolved": list(confirmed.unresolved_regions),
        "PALT_P1_FINAL_DIMENSIONS": "NOT_APPROVED",
        "PALT_P1_MANUFACTURING_AUTHORITY": "NOT_ESTABLISHED",
        "PALT_P1_OWNER_APPROVAL": "NOT_GRANTED",
        "GATE_2": "BLOCKED",
    }
