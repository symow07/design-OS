"""§BB7 — the ruled front tiers, built once for every composer that draws a
front (``ruled_front_hierarchy/1.0``).

§BB7(c) ruled **WIRE BOTH** call sites in the owner's own typed words —
*"Wire both call sites — container/__init__.py:1081 and
services/native_handoff.py:249. One front from every path. My ruling."* §BB7(b)
re-authorised the wiring that §BB6 reverted, conditional on C9, and §BB7(a)
answers C9. So the front is drawn, and it is drawn from one place.

WHY THIS MODULE EXISTS RATHER THAN A LIST AT EACH CALL SITE. Three production
composers need the same tiers and reach them differently — §BB7(g)(a) warns in
terms that *"any executor who assumes one patch fits all three is wrong before
he starts."* The CONTENT is one thing and the PLUMBING is three; this file is
the content, and each composer keeps its own plumbing.

WHY THE DESCRIPTOR IS A LITERAL HERE AND NOT READ OUT OF THE REGISTER. Sourcing
it from ``tools.brand_strings.RULED_STRINGS`` at runtime would put the owner's
string into the emitter with NO edit to the register — which is precisely the
visibility ``RULED_STRINGS`` exists to create. Its own refusal text says so:
*"Add the site to RULED_STRINGS if the use is intended — which is a visible
edit to a register, and is the point."* So the literal is written here, this
file is registered as one of C9's sites, and the duplication is safe in the one
way that matters: ``RULED_STRING_ALTERED`` refuses any copy whose characters
drift from the owner's.

  SUPERSEDED FOR THIS FILE BY §BH65(b)1 (2026-09-22), and kept because the
  reasoning was right for the question it answered. There is no longer a
  literal here: the descriptor is each product's own, passed in by the caller,
  and ``RULED_STRINGS`` no longer lists this file as a site of ``FACIAL SERUM``.
  What the paragraph protected — that the owner's string never enters the
  emitter unseen — is now protected by the string not entering it at all
  unless a product's record says it.

WHY THERE IS NO NET-CONTENT TIER, THOUGH THE PINNED FIXTURE HAS ONE.
``test_wit_unit_analysis.py`` carries a three-line hierarchy ending ``30 ml``.
That third line is a MEASUREMENT FIXTURE and is not emittable copy:
``brand_strings.NOT_OURS`` rules ``net_content`` out by name as *"§AE2(b)
REGULATED, not brand — NET CONTENT is inside reserved_copy.RESERVED_HEADINGS
and is manifest row B5, already BLOCKING. AU1 rejected 'descriptor plus volume'
for exactly this reason."* Emitting it would be a blocking regulated string with
no ruled value behind it, and would do the thing AU1 refused. The front carries
TWO tiers until B5 is ruled.

WHY THE PRODUCT NAME IS NOT RESHAPED. §BB7(a) ruled the DESCRIPTOR's characters
and said nothing about the name's. ``NOT_OURS`` records the name as *"supplied
FROM THE PRODUCT RECORD rather than invented"*, so it is passed through exactly
as the record holds it. The fixture's uppercase ``ROSE NECTAR`` is the fixture's,
not a ruling: a record holding ``Rose Nectar`` prints ``Rose Nectar``.

§BH65(b)1, OWNER RULED 2026-09-22 — THE DESCRIPTOR IS DERIVED FROM THE PRODUCT.
His words: "DESCRIPTOR = "FACIAL SERUM" is hard-coded on every container front
and appears nowhere in the run's record. That is the line I saw on a face
palette in task 84 and mistook for a vocabulary problem. Derive it from the
product; where no record says what the product is, print nothing rather than a
wrong word."

WHAT THE CONSTANT HAD DONE. §BB7(a) ruled `FACIAL SERUM` as C9, "the one front
descriptor line", on the day the only container this system drew was a serum.
§BB7(c) then wired it as a module constant into BOTH production call sites, so
it printed on EVERY container front. Measured across the product table: it
printed on a LIP GLOSS (task 51 — the very front §BB7(c) measured when it was
wired), a NIGHT REPAIR OIL (52), four acceptance fixtures whose record names no
product (53-56), the serum demo it describes (57), the Rose Glow PALETTE (84-88)
and the FOCUS pressed-powder COMPACT (89). Right on one of eleven runs.

THE REGISTER HAD RESERVED THIS EXACT QUESTION. `tools/brand_strings.py` pinned the
ruled string to this file and wrote beside it: "Whether the front hierarchy
gains a per-product source in place of this ruled literal is OWNER-RESERVED",
and two tests quote the owner's earlier instruction verbatim — a per-product
source "is a measured proposal to bring back, not a decision to make". §BH65(b)1
is that decision, made by him. It is applied, not interpreted around.

THE SOURCE IS `Product.product_type`, the one field whose job is to say what the
product IS, and it is passed through EXACTLY as the record holds it — the
`NOT_OURS` precedent for the product name ("supplied FROM THE PRODUCT RECORD
rather than invented ... a record holding `Rose Nectar` prints `Rose Nectar`").
Nothing is uppercased, trimmed of words or rephrased: a descriptor reshaped by
the machine would be the §AE2(c) taste fabrication C9 exists to prevent.

"PRINT NOTHING RATHER THAN A WRONG WORD" IS TWO CASES, both measured on the table:
an EMPTY `product_type` (the four acceptance fixtures) says nothing; and a
`product_type` that is only a PACKAGING word says what the product is packed IN,
not what it IS — three rows read `carton`, one of them the night repair OIL.
The packaging words are not a list written here: they are the container forms
the one declaration names (`archetypes.ARCHETYPES`) plus the secondary pack the
selected-concept contract calls `OUTER_CARTON`.

NO DEFAULT, BY CONSTRUCTION. `ruled_front_hierarchy` takes the descriptor as a
REQUIRED keyword. A default of `FACIAL SERUM` would be the defect; a default of
None would let a caller forget the product silently. A caller must say which
descriptor it means, and None means the record said nothing.

Pure: no Django, no ORM, no network — the product is read by attribute only.
"""
from __future__ import annotations

from apps.pipeline.targets.container.archetypes import ARCHETYPES as _CONTAINER_FORMS

SCHEMA = "ruled_front_hierarchy/1.0"

#: §BH65(b)1 — where begin_output records the descriptor it derived, beside
#: `product_name`, so reconstruction is a function of the spec and both call
#: sites print the same word. A spec written before this key existed has none,
#: and is derived from its task's product at reconstruction instead.
SPEC_KEY = "product_descriptor"

#: §BH65(b)1 — a `product_type` that is ONLY one of these names the pack, not
#: the product, and prints nothing. The container forms come from the one
#: declaration; `carton` is the secondary pack (`OUTER_CARTON` in
#: `selected_concept_contract`) and is the word three product rows carry.
PACKAGING_WORDS = frozenset(_CONTAINER_FORMS) | frozenset({"carton"})


def descriptor_from_record(product_type):
    """What the product IS, as its own record holds it — or None.

    None for an empty record and for a record that names only a PACKAGING word:
    "print nothing rather than a wrong word" (§BH65(b)1). Otherwise the value is
    returned exactly as held, stripped of surrounding whitespace only."""
    value = str(product_type or "").strip()
    if not value or value.casefold() in PACKAGING_WORDS:
        return None
    return value


def net_content_for(product) -> str | None:
    """§BH67(c)2, OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md:23350, LIVE): "The dropper's "NIGHT REPAIR OIL"
    and "30 ml / 1.01 fl. oz." are the same defect as FACIAL SERUM. Derive both from the product record; where the
    record is silent, print nothing." The product's net content is ``Product.net_weight`` AS HELD — its own help text
    reads "e.g. '5 g X 12 PCS' or '30 ml e 1 fl. oz.'" — printed in the record's own spelling; None when the record
    is silent."""
    return (getattr(product, "net_weight", "") or "").strip() or None


def descriptor_for(spec, product=None):
    """The descriptor a reconstruction prints: the one begin_output recorded in
    the spec, or — for a spec written before §BH65(b)1 — derived now from the
    task's own product. Never a constant."""
    spec = spec or {}
    if SPEC_KEY in spec:
        return spec[SPEC_KEY]
    return descriptor_from_record(getattr(product, "product_type", None))

#: The descriptor's weight relative to the name. It does NOT set the point size.
#: ``compose_container._native_decoration`` takes the size from the tier's KIND —
#: ``_hero_tier_pt("descriptor")`` returns ``HERO_DESCRIPTOR_PT``, ruled 5.0 pt by
#: §BD(a) — and then applies ``max(1.0, rel)``, which for any value below 1.0 is
#: exactly 1.0 and multiplies nothing. So what this constant actually selects is
#: the tier's GAP (``rel < 1.0`` takes the tight step) and its regular rather than
#: bold face (bold needs ``rel >= 0.9``).
#:
#: THIS COMMENT PREVIOUSLY NAMED ``HERO_SUPPORT_PT`` AS THE FLOOR, and §BD(a) is
#: what falsified it: the descriptor left the shared support constant and took a
#: constant of its own. Nothing about ``0.8`` moved — the number is unchanged and
#: still means what it meant. It is the SENTENCE that was wrong, which is why the
#: fix is here and not in the value.
DESCRIPTOR_REL = 0.8


def ruled_front_hierarchy(product_name: str, *, descriptor) -> list[dict]:
    """The ordered live-text tiers for a direct-print front.

    §BH65(b)1: the descriptor is THIS PRODUCT's, passed by the caller, and its
    tier is dropped when the record said nothing — "print nothing rather than a
    wrong word". The name tier still stands, so ``direct_print`` is on from
    every path exactly as §BB7(c) wired it: every product row carries a name,
    and `begin_output` falls back to the task text for `product_name` when one
    does not, so the hierarchy is empty only if both are absent at once.

    THIS DOCSTRING USED TO SAY "Never empty: the descriptor is ruled and stands
    whether or not the record carries a name". That was true of the constant and
    is the sentence §BH65(b)1 retires.
    """
    tiers = []
    if product_name:
        tiers.append({"text": product_name, "kind": "product_name",
                      "rel": 1.0})
    if descriptor:
        tiers.append({"text": descriptor, "kind": "descriptor",
                      "rel": DESCRIPTOR_REL})
    return tiers


__all__ = ["DESCRIPTOR_REL", "PACKAGING_WORDS", "SCHEMA", "SPEC_KEY",
           "descriptor_for", "descriptor_from_record", "ruled_front_hierarchy"]
