"""§W4 — the stroke weights this repo draws rules at, and what stands behind
each one (``container_line_weight/1.0``).

§W4 ruled that ``ai8_color.DIVIDER_WIDTH_PT`` and the container front rule are
DIFFERENT OBJECTS and that **both numbers stand**. Nothing here changes a
number. What §W4(b) asked for is the container front rule's own recorded
weight rationale, because "different objects" rules on identity and is not a
blessing of 0.25 mm as a considered value.

Recording that rationale honestly turned up two things §W4 could not have
known, both verified against the emitted documents rather than read off the
source:

1. **The ruled weight is now drawn — THIS ITEM HAS BEEN FALSIFIED TWICE AND
   BOTH REVERSALS ARE KEPT.** It read *"the ruled 0.25 mm is never drawn"*,
   because ``compose_container.py``'s front rule sits on the 2C-2E
   ``direct_print`` branch, which fires only when ``compose_container_graph``
   is given ``hierarchy_lines``. The claim attached to that was *"NOTHING in
   the repo passes that argument"*, which ``2d8e4e5`` corrected to the narrower
   and true one: no PRODUCTION caller passed it. **§BB7(c) then ruled both
   production call sites wired, and the narrow claim is false too.** The branch
   is what production composes, and the rule is drawn at (0.30, 1.0) from both
   sites — measured on the emitted document, not inferred from the wiring.
2. **The front rule that IS drawn is a different element**: the
   selected-concept dropper sheet's. That is the sheet the container target
   actually emits whenever it has geometry.

   THAT ITEM READ "a different element AT A DIFFERENT WEIGHT ... at 0.20 mm and
   0.8 opacity" UNTIL §BB7(e), AND HALF OF IT IS NOW FALSE. C16(b) ruled 0.30 mm
   and opacity 1.0 for this element too, so the two rules no longer differ by
   width at all — they differ by whether they are drawn. The owner ruled that
   distinction explicitly: *"the real difference between the two rules is that
   one is drawn and one is not, not their widths."* The weights live in
   ``ELEMENTS`` below and are not restated here, so this paragraph cannot go
   stale the same way twice.

So there are THREE elements here, not two. Each names its context below, per
§W4(a). §W4(c) — a later proof that MEASURES a container's front rule
supersedes all of this — is the route by which any of it changes.

WHAT A RATIONALE CAN AND CANNOT BE HERE. No manufacturer has measured any of
these strokes. The only authority in the repo is
``container_production_method._METHOD_DEFAULTS[...]["min_line_mm"]``, which is
labelled INFERRED_NONAUTHORITATIVE in its own file — typical type defaults,
never manufacturer authority. So each rationale records WHERE THE NUMBER SITS
against that table and stops there. ``position_against_table`` computes that
placement instead of restating it, so a change to the table surfaces as a
changed rationale rather than as a comment that quietly went stale.

Pure: no Django, no ORM, no network.
"""
from __future__ import annotations

SCHEMA = "container_line_weight/1.0"

#: §W4 is a ruling about which elements exist, not a measurement of any of
#: them. Nothing below is manufacturer authority.
STATUS = "OWNER_RULED_PENDING_MEASUREMENT"

MM_PER_PT = 25.4 / 72.0

CLEARS = "CLEARS"
EXACTLY_ON = "EXACTLY ON"
BELOW = "BELOW"

#: The elements, each naming its context (§W4(a)). ``emitted`` records whether
#: production actually draws it — the distinction §W4(b) turned up.
ELEMENTS = {
    "gate_a_divider": {
        "site": "apps/pipeline/services/ai8_color.py DIVIDER_WIDTH_PT",
        "width_pt": 0.362384,
        "width_mm": 0.362384 * MM_PER_PT,
        "context": "the colour-sheet divider on the ACCEPTED PROOF, read out "
                   "of that proof's content stream and verified at Gate A",
        "authority": "ACCEPTED_PROOF — measured, in the context it was "
                     "measured in. Not transferable to another surface.",
        "emitted": True,
    },
    "container_front_rule": {
        "site": "apps/ire/compose_container.py rule-front-single",
        "width_mm": 0.30,
        "width_pt": 0.30 / MM_PER_PT,
        "context": "the single fine rule above the product name on the 2C-2E "
                   "DIRECT-PRINT front, where type prints straight onto the "
                   "material with no label and no decoration field",
        "authority": "OWNER_RULED — §AU2. A ruled design value, not a "
                     "measurement. No manufacturer and no proof has measured "
                     "this stroke. Superseded on arrival of any §W4(c) proof "
                     "that measures a printed container front rule.",
        "superseded_value_mm": 0.25,
        "superseded_because": "0.25 mm was never chosen; it was present. "
                              "§AU2 ruled 0.30 as the smallest weight the "
                              "owner is willing to put on owner-facing output "
                              "while it has no measurement behind it — a "
                              "judgement about print RISK, not a measurement "
                              "of print behaviour.",
        # §AU2, verbatim: "`emitted` flips to True ONLY when the branch is
        # genuinely reached — not as part of the same edit, and not on the
        # strength of this ruling." That condition is now MET, and by the only
        # thing that could meet it: §BB7(c) ruled both production call sites
        # wired, they pass `hierarchy_lines`, and the rule is drawn. The flip
        # rides with the wiring that earns it, which is the case §AU2 reserved
        # it for — not alongside a width change, which is what it forbade.
        "emitted": True,
        "emitted_because": "§BB7(c) — apps/pipeline/targets/container/"
                           "__init__.py and apps/pipeline/services/"
                           "native_handoff.py both supply hierarchy_lines "
                           "from front_hierarchy.ruled_front_hierarchy, so "
                           "direct_print is on from every path and "
                           "rule-front-single is drawn at (0.30, 1.0) — "
                           "measured on the emitted document at both sites",
        "superseded_unreached_because": "the direct-print branch requires "
                             "compose_container_graph(hierarchy_lines=...), "
                             "and no PRODUCTION caller passes it — test "
                             "callers do, and that is what makes the branch "
                             "measured rather than shipped; inside the "
                             "branch the rule additionally requires a "
                             "SUPPORTED motif language. TRUE UNTIL §BB7(c) "
                             "wired both sites; kept beside the flip so the "
                             "change is legible rather than silent, which is "
                             "this record's own convention for a superseded "
                             "value.",
        # §AU order 3 — MEASURED 2026-08-21, not assumed. AU2 named a third
        # gate the A10 manifest row had missed and required that "the executor
        # must confirm which concepts satisfy it before claiming the divider is
        # drawable — per AD0(a), that is a measurement to take, not a condition
        # to assume is met." Measured: the gate is not the obstacle. Every
        # classified family clears it; what does not clear it is the ABSENCE
        # of a motif signal, which is a different thing from a family failing.
        "third_gate_measured": {
            # §BH65(c)4 re-measured it: two families joined the composing classifier (ENGRAVED_LINEWORK, HALO_RINGS),
            # both with a language, both clearing gate three — 13 of 13 on 2026-08-21 became 15 of 15
            # [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start
            # testing"): "The lid is missing the concept's rule, ring and radial lines." Re-measured: RADIAL_LINES
            # joined the composing classifier with its own language, and clears gate three — 15 of 15 on 2026-09-23
            # became 16 of 16]
            "measured_on": "2026-09-25",
            "families_clearing": 16,
            "families_total": 16,
            "blocked_families": [],
            "blocked_cases": ["no structured record (capability NONE)",
                              "empty motif signature (capability NONE)",
                              "unclassified prose (REVIEW_REQUIRED)"],
            "measured_by": "apps/ire/tests/test_au3_divider_gates.py",
        },
    },
    "dropper_front_rule": {
        "site": "apps/ire/compose_dropper.py rule-front-single",
        "width_mm": 0.30,
        "width_pt": 0.30 / MM_PER_PT,
        "opacity": 1.0,
        "context": "the selected-concept dropper sheet's single fine rule — "
                   "the front rule the container target ACTUALLY emits, on "
                   "both the dimensional and the flat view",
        "authority": "OWNER_RULED — §BB7(e) C16(b): 0.30 mm everywhere, "
                     "opacity 1.0 solid. Supersedes the recorded absence of "
                     "authority: §W4 did not name this element, because that "
                     "ruling was written against the unreached one.",
        "superseded_value_mm": 0.2,
        "superseded_opacity": 0.8,
        "emitted": True,
    },
}

RULE = (
    "OWNER_BLOCKER_CLEARANCE.md §W4 — the Gate-A divider and the container "
    "front rule are different objects and both numbers stand. Neither is "
    "changed here. §W4(b) is answered by recording what bears on each weight "
    "and what does not: the only table in the repo is INFERRED_NONAUTHORITATIVE "
    "type defaults, so a weight that clears it is not thereby approved. §W4(c) "
    "— a proof that measures a container's front rule supersedes this record."
)


def position_against_table(width_mm: float) -> dict:
    """method_type → whether ``width_mm`` clears that method's line floor.

    Computed from the capability table rather than transcribed, so a change
    to the table shows up as a changed rationale instead of leaving a comment
    asserting something that stopped being true.
    """
    from apps.ire.container_production_method import _METHOD_DEFAULTS

    out = {}
    for method_type, defaults in _METHOD_DEFAULTS.items():
        floor = float(defaults["min_line_mm"])
        out[method_type] = {
            "floor_mm": floor,
            "standing": (CLEARS if width_mm > floor + 1e-9 else
                         BELOW if width_mm < floor - 1e-9 else EXACTLY_ON),
        }
    return dict(sorted(out.items()))


def weight_record(element_id: str) -> dict:
    """One element's context and its standing against the capability table."""
    element = dict(ELEMENTS[element_id])
    standing = position_against_table(element["width_mm"])
    return {
        "schema_version": SCHEMA,
        "status": STATUS,
        "rule": RULE,
        "element_id": element_id,
        **element,
        "table_authority": "INFERRED_NONAUTHORITATIVE type defaults "
                           "(container_production_method/1.0) — a weight that "
                           "clears these is not thereby approved for print",
        "standing_by_method": standing,
        "clears": sorted(m for m, s in standing.items()
                         if s["standing"] == CLEARS),
        "below": sorted(m for m, s in standing.items()
                        if s["standing"] == BELOW),
        "exactly_on": sorted(m for m, s in standing.items()
                             if s["standing"] == EXACTLY_ON),
    }


__all__ = ["BELOW", "CLEARS", "ELEMENTS", "EXACTLY_ON", "MM_PER_PT", "RULE",
           "SCHEMA", "STATUS", "position_against_table", "weight_record"]
