"""PALT-M4C §6 — the PALT-P2 single-pan pressed-powder compact family.

``PALT_P2`` is a different structural case from ES3083, not a second
eyeshadow palette: one large pan, no lattice, a lid that usually carries a
mirror and a puff. This module holds the SHARED family contract and the
per-variant intent, so two variants that look different cannot collapse
into one generic compact.

**A finding that governs this whole slice.** The recovered asset is a
single file named ``ref_FB3093__FB3090粉饼.png``. The filename pairs the
two codes, but the sheet itself is titled FB3093 and its display box
carries ``ITEM NO. FB3093``. Nothing on it documents FB3090, and no
separate FB3090 asset exists in this repository. PALT-P2A is therefore
drafted from a real reading; **PALT-P2B is UNSOURCED** and its fields are
recorded as having no source rather than being invented to fill the
comparison the directive asks for.

The non-collapse requirement is still met, and honestly: the mechanism is
proved against controlled variants of the family contract, and labelled as
a mechanism proof rather than as a reading of FB3090.
"""
from __future__ import annotations

import hashlib

from apps.pipeline.services import palette_design_intent as di
from apps.pipeline.services import palette_firing_trace as FT

SCHEMA = "palette_compact_family/1.0"

FAMILY = "SINGLE_PAN_PRESSED_POWDER_COMPACT_FAMILY"
P2A, P2B = "PALT_P2A", "PALT_P2B"

SOURCE = ("ConceptReference:2 FB3093__FB3090粉饼 "
          "(media/references/ref_FB3093__FB3090粉饼.png)")

#: Every axis the directive asks the comparison to cover.
COMPARISON_AXES = (
    "outer_silhouette", "compact_proportions", "pan_geometry",
    "lid_geometry", "window_or_mirror", "hinge", "clasp",
    "opening_direction", "powder_type", "artwork", "colour_zones",
    "material_zones", "visible_manufacturing_strategy",
)

#: What every member of the family shares, independent of artwork.
FAMILY_CONTRACT = {
    "record_type": "compact_family_contract/1.0",
    "family": FAMILY,
    "pan_count": 1,
    "pan_lattice": "NONE_SINGLE_CAVITY",
    "closure": "HINGED_FLIP_TOP",
    "opening_direction": "UPWARD",
    "lid_carries": ["mirror_or_puff_compartment"],
    "powder_form": "PRESSED_POWDER",
    "structural_difference_from_ES3083": (
        "the 4x3 lattice degenerates to a single cavity, so the deck land, "
        "the inter-pocket spacing rule and the grid alignment constraints "
        "have no members. This is a genuinely different structural case, "
        "not a variation on the palette."),
    "authority": "PROVISIONAL_FAMILY_READING_NOT_OWNER_CONFIRMED",
}

UNSOURCED = "NO_SOURCE_IN_THIS_REPOSITORY"


def _f(name, value, level, region, confidence, method, ref=SOURCE, **kw):
    base = dict(geometry_relevance=False, material_relevance=False,
                artwork_relevance=False, note="")
    base.update(kw)
    return dict(name=name, value=value, source_reference=ref,
                source_region=region, confidence=confidence,
                extraction_method=method, confirmation_state=di.PENDING,
                constraint_level=level, **base)


def build_p2a_intent() -> di.PaletteDesignIntent:
    """FB3093 — read from the sheet, which was opened and inspected."""
    it = di.PaletteDesignIntent(concept_reference=f"{P2A} FB3093 — {SOURCE}")
    add = it.add
    add(**_f("pan_count", 1, di.HARD, "compact render, single cavity", 0.85,
             "IMAGE_COUNTED", geometry_relevance=True))
    add(**_f("pan_shapes", "ROUND_IN_SQUARE_CASE", di.SOFT,
             "open compact render", 0.6, "IMAGE_INFERRED",
             geometry_relevance=True,
             note="the case reads square with rounded corners; the pan "
                  "itself is not resolvable at this size"))
    add(**_f("silhouette", "SQUARE_ROUNDED", di.SOFT,
             "closed and open compact renders", 0.7, "IMAGE_INFERRED",
             geometry_relevance=True))
    add(**_f("opening_direction", "UPWARD", di.HARD,
             "compact shown open, lid hinged at the back", 0.85,
             "IMAGE_INFERRED", geometry_relevance=True))
    add(**_f("hinge_location", "REAR_EDGE", di.SOFT,
             "open compact render", 0.65, "IMAGE_INFERRED",
             geometry_relevance=True))
    add(**_f("clasp_location", "FRONT_EDGE", di.SOFT,
             "closed compact render", 0.5, "IMAGE_INFERRED",
             geometry_relevance=True,
             note="a front catch is implied by the flip-top form but is "
                  "not clearly visible"))
    add(**_f("mirror_presence", "UNRESOLVED", di.SOFT,
             "open compact interior", 0.35, "IMAGE_INFERRED",
             geometry_relevance=True,
             note="the lid interior is not legible at this size; a mirror "
                  "and a puff compartment are both plausible"))
    add(**_f("powder_finish_intent", "PRESSED_POWDER", di.HARD,
             "'FACE POWDER' / 'POLVOS' on the display box", 0.9,
             "IMAGE_COUNTED", material_relevance=True))
    add(**_f("apparent_material", "MOULDED_PLASTIC_MATTE", di.SOFT,
             "compact body", 0.6, "IMAGE_INFERRED",
             material_relevance=True))
    add(**_f("colour_zones", ["705", "7506", "7530", "705 / 30%"],
             di.HARD, "named colour chips printed on the sheet", 0.9,
             "OWNER_STATED", material_relevance=True,
             note="house colour codes, NOT Pantone tokens; not converted"))
    add(**_f("shade_names", "SIX_SHADE_SWATCH_ROW_PLUS_LABEL_STRIP_SHEET",
             di.HARD, "swatch row and label strip grid", 0.85,
             "IMAGE_COUNTED", artwork_relevance=True))
    add(**_f("typography_zones",
             ["BBROSE", "FACE POWDER", "Super Stay", "UP TO 24 H.",
              "POLVOS"], di.HARD, "display box front", 0.9,
             "IMAGE_COUNTED", artwork_relevance=True))
    add(**_f("logo_position", "BOX_TOP_AND_COMPACT_LID", di.SOFT,
             "BBROSE mark", 0.7, "IMAGE_INFERRED", artwork_relevance=True))
    add(**_f("regulatory_zones", "BACK_PANEL_WITH_INGREDIENTS_AND_BARCODE",
             di.HARD, "display box back panel", 0.9, "IMAGE_COUNTED",
             artwork_relevance=True))
    add(**_f("ornament", "STAR_BADGE_COOL_FLASH", di.DECORATIVE,
             "box header badges", 0.8, "IMAGE_INFERRED",
             artwork_relevance=True,
             note="ornament only — must not become moulded relief"))
    add(**_f("pattern", "REPEATING_SUPER_STAY_SIDE_PANEL", di.DECORATIVE,
             "display box side panels", 0.8, "IMAGE_INFERRED",
             artwork_relevance=True))
    it.unresolved_regions = [
        "pan diameter and compact dimensions in millimetres — not readable",
        "mirror versus puff compartment in the lid",
        "clasp geometry",
        "the physical sample photographed on the sheet is labelled "
        "S-8171 B, which is not FB3093 — the relationship is unrecorded",
    ]
    it.view = {
        "estimated_camera_view": "flat production sheet with small renders",
        "visible_faces": ["display box front and back", "compact closed",
                          "compact open"],
        "hidden_faces": ["compact underside", "lid interior detail"],
    }
    return it


def build_p2b_intent() -> di.PaletteDesignIntent:
    """FB3090 — declared, NOT read. There is no FB3090 source here."""
    it = di.PaletteDesignIntent(
        concept_reference=f"{P2B} FB3090 — {UNSOURCED}")
    it.unresolved_regions = [
        f"{axis}: {UNSOURCED}" for axis in COMPARISON_AXES]
    it.view = {"estimated_camera_view": UNSOURCED,
               "visible_faces": [], "hidden_faces": []}
    return it


def compare() -> dict:
    """The comparative package the directive asks for, with the gap
    stated rather than filled."""
    a, b = build_p2a_intent(), build_p2b_intent()
    rows = []
    for axis in COMPARISON_AXES:
        fa = a.get(axis) or a.get({"compact_proportions": "silhouette",
                                   "outer_silhouette": "silhouette",
                                   "pan_geometry": "pan_shapes",
                                   "lid_geometry": "hinge_location",
                                   "window_or_mirror": "mirror_presence",
                                   "hinge": "hinge_location",
                                   "clasp": "clasp_location",
                                   "powder_type": "powder_finish_intent",
                                   "artwork": "typography_zones",
                                   "material_zones": "apparent_material",
                                   "visible_manufacturing_strategy":
                                       "apparent_material",
                                   }.get(axis, axis))
        rows.append({
            "axis": axis,
            "PALT_P2A_FB3093": {
                "value": fa.value if fa else None,
                "confidence": round(float(fa.confidence), 3) if fa else FT.traced_zero("palette_compact_family.py:compare", "guard"),
                "constraint_level": fa.constraint_level if fa else None,
                "state": "READ_FROM_SOURCE" if fa else "NOT_READ"},
            "PALT_P2B_FB3090": {"value": None, "confidence": 0.0,
                                "state": UNSOURCED},
            "comparable": False,
        })
    return {
        "record_type": SCHEMA,
        "PALT_P2": FAMILY,
        "PALT_P2A": "FB3093",
        "PALT_P2B": "FB3090",
        "PALT_P2_FINAL_PRIMARY_CONCEPT": "PENDING_COMPARATIVE_REVIEW",
        "family_contract": dict(FAMILY_CONTRACT),
        "axes": rows,
        "blocking_finding": {
            "finding": "FB3090 HAS NO SOURCE IN THIS REPOSITORY",
            "detail": "the recovered file is named "
                      "ref_FB3093__FB3090粉饼.png, but the sheet is titled "
                      "FB3093 and its display box carries ITEM NO. FB3093. "
                      "Nothing on it documents FB3090, and no separate "
                      "FB3090 asset exists.",
            "consequence": "a comparative review cannot be conducted, and "
                           "an arbitrary selection is exactly what the "
                           "directive forbids",
            "what_would_unblock_it": "the FB3090 production sheet or "
                                     "native .ai source",
        },
        "comparable_axis_count": 0,
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
        "package_identity": hashlib.sha256(
            (a.identity() + b.identity()).encode()).hexdigest()[:16],
    }


def variant_contract(intent) -> dict:
    """Collapse an intent onto the family contract to a comparable
    contract. Two variants whose visible designs differ MUST produce
    different contracts here."""
    out = dict(FAMILY_CONTRACT)
    out.pop("record_type", None)
    for axis in COMPARISON_AXES:
        f = intent.get(axis)
        if f is not None and f.confirmation_state != di.REMOVED:
            out[axis] = f.value
    for name in ("silhouette", "pan_shapes", "hinge_location",
                 "clasp_location", "mirror_presence", "colour_zones",
                 "typography_zones", "apparent_material", "ornament"):
        f = intent.get(name)
        if f is not None and f.confirmation_state != di.REMOVED:
            out[name] = f.value
    return out


def non_collapse_proof(variants) -> dict:
    """Prove the engine keeps differing designs distinct.

    This is a MECHANISM proof. It is not a reading of FB3090, because no
    FB3090 source exists; presenting it as one would be the fabrication
    the directive forbids.
    """
    contracts = {name: variant_contract(it) for name, it in variants.items()}
    names = list(contracts)
    pairs = []
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            diff = sorted(k for k in set(contracts[x]) | set(contracts[y])
                          if contracts[x].get(k) != contracts[y].get(k))
            pairs.append({"a": x, "b": y, "differing_fields": diff,
                          "collapsed": not diff})
    return {
        "record_type": "compact_non_collapse_proof/1.0",
        "evidence_kind": "MECHANISM_PROOF_NOT_A_READING_OF_FB3090",
        "variants": names,
        "pairs": pairs,
        "any_collapsed": any(p["collapsed"] for p in pairs),
        "verdict": "FAIL" if any(p["collapsed"] for p in pairs) else "PASS",
        "proves": "TWO_DIFFERING_VISIBLE_DESIGNS_PRODUCE_TWO_CONTRACTS",
        "does_not_prove": [
            "anything about FB3090, which has no source here",
            "that either compact is manufacturable",
        ],
    }
