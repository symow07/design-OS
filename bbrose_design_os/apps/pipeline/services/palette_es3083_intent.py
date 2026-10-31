"""PALT-M4C M4C-3 — design intent drafted from the recovered ES3083 asset.

``ES3083吸塑_展盒刀线`` is a real BBROSE "Outer Glow" eyeshadow palette
production sheet, recovered in §4 from ConceptReference 6 (task 50, which
was filed under the PACKAGING target). Every field below was read from
that sheet, which was opened and inspected.

Nothing here is owner-confirmed. The whole record is a
``PROVISIONAL_INTENT_VARIANT`` and every field is
``PENDING_OWNER_CONFIRMATION`` until the owner rules — including which of
the two recovered palette designs is the selected concept.

§H discipline is applied: the mint field is a MATERIAL/COLOUR zone read
from the flat artwork, not a shadow; the bubble scatter is ornament, not
moulded relief; the display box is packaging, not the palette body.
"""
from __future__ import annotations

from apps.pipeline.services import palette_design_intent as di

CONCEPT_REFERENCE = (
    "ConceptReference:6 ES3083吸塑_展盒刀线 — BBROSE 'Outer Glow' eyeshadow "
    "palette (media/references/ref_ES3083吸塑_展盒刀线.png)")

SOURCE_TASK = 50
SOURCE_TARGET_AT_RECOVERY = "packaging"


def _f(name, value, level, region, confidence, method, *, geom=False,
       mat=False, art=False, note=""):
    return dict(name=name, value=value, source_reference=CONCEPT_REFERENCE,
                source_region=region, confidence=confidence,
                extraction_method=method,
                confirmation_state=di.PENDING, constraint_level=level,
                geometry_relevance=geom, material_relevance=mat,
                artwork_relevance=art, note=note)


def build_es3083_intent() -> di.PaletteDesignIntent:
    """Provisional intent drafted from the recovered production sheet."""
    intent = di.PaletteDesignIntent(concept_reference=CONCEPT_REFERENCE)

    # --- internal layout (the headline contradiction with PALT-P1) -----
    intent.add(**_f("pan_shapes", "RECTANGULAR", di.HARD,
                    "rendered open case + thermoformed tray photograph",
                    0.9, "IMAGE_COUNTED", geom=True,
                    note="PALT-P1 assumed CIRCULAR pans; the real BBROSE "
                         "palette uses rectangular pans"))
    intent.add(**_f("pan_count", 12, di.SOFT,
                    "rendered open case, pan grid", 0.55, "IMAGE_COUNTED",
                    geom=True,
                    note="approximately 4x3 read from a small render; "
                         "SOFT rather than HARD because the render is not "
                         "large enough to count with certainty"))
    intent.add(**_f("rows", 3, di.SOFT, "rendered open case", 0.55,
                    "IMAGE_COUNTED", geom=True))
    intent.add(**_f("columns", 4, di.SOFT, "rendered open case", 0.55,
                    "IMAGE_COUNTED", geom=True))
    intent.add(**_f("spacing_rhythm", "tight even spacing", di.SOFT,
                    "pan grid", 0.6, "IMAGE_MEASURED", geom=True))
    intent.add(**_f("margins", "tight margins", di.SOFT,
                    "case border around the pan field", 0.55,
                    "IMAGE_MEASURED", geom=True))
    intent.add(**_f("alignment", "ORTHOGONAL_GRID", di.SOFT, "pan field",
                    0.7, "IMAGE_INFERRED", geom=True))

    # --- outer form ---------------------------------------------------
    intent.add(**_f("silhouette", "SQUARE_ROUNDED", di.SOFT,
                    "rendered closed case", 0.6, "IMAGE_INFERRED",
                    geom=True))
    intent.add(**_f("perceived_thickness", "slim", di.SOFT,
                    "rendered case side", 0.5, "IMAGE_INFERRED", geom=True))
    intent.add(**_f("corner_radius_impression", "softly rounded corners",
                    di.SOFT, "outer silhouette", 0.55, "IMAGE_INFERRED",
                    geom=True))

    # --- mechanical ---------------------------------------------------
    intent.add(**_f("opening_direction", "UPWARD", di.HARD,
                    "rendered case shown open", 0.85, "IMAGE_INFERRED",
                    geom=True))
    intent.add(**_f("hinge_location", "TOP_EDGE", di.SOFT,
                    "rendered open case, lid pivot", 0.6, "IMAGE_INFERRED",
                    geom=True,
                    note="the lid pivots along one long edge; which edge "
                         "is the product TOP needs owner confirmation"))
    intent.add(**_f("mirror_presence", False, di.SOFT,
                    "rendered open case interior", 0.4, "IMAGE_INFERRED",
                    geom=True,
                    note="no mirror is visible in the render, but the lid "
                         "interior is not clearly shown — low confidence"))

    # --- material / colour --------------------------------------------
    intent.add(**_f("apparent_material", "MOULDED_PLASTIC_MATTE", di.SOFT,
                    "case body", 0.6, "IMAGE_INFERRED", mat=True))
    intent.add(**_f("colour_zones", ["PANTONE 621 C", "PANTONE 627 C"],
                    di.HARD, "explicit Pantone chips on the sheet", 0.95,
                    "OWNER_STATED", mat=True,
                    note="printed on the production sheet as named "
                         "Pantone chips — the strongest fact on it"))
    intent.add(**_f("powder_finish_intent", "PRESSED_POWDER", di.SOFT,
                    "product category", 0.7, "IMAGE_INFERRED", mat=True))

    # --- artwork ------------------------------------------------------
    intent.add(**_f("logo_position", "LID_CENTRE", di.SOFT,
                    "BBROSE mark on the case face", 0.65, "IMAGE_INFERRED",
                    art=True))
    intent.add(**_f("typography_zones",
                    ["EYE SHADOW", "OUTER GLOW", "BBROSE",
                     "SOMBRA DE OJOS"], di.HARD,
                    "display box and case face", 0.9, "IMAGE_COUNTED",
                    art=True))
    intent.add(**_f("shade_names", "SHADE_LABEL_STRIP_SHEET_PRESENT",
                    di.HARD, "label strip grid on the sheet", 0.85,
                    "IMAGE_COUNTED", art=True))
    intent.add(**_f("regulatory_zones", "BACK_PANEL_WITH_BARCODE",
                    di.HARD, "display box regulatory panel", 0.9,
                    "IMAGE_COUNTED", art=True))
    intent.add(**_f("ornament", "BUBBLE_DOT_SCATTER", di.DECORATIVE,
                    "case and box artwork", 0.8, "IMAGE_INFERRED",
                    art=True,
                    note="ornament only — must not become moulded relief"))
    intent.add(**_f("pattern", "SMILEY_LETTERFORM_O", di.DECORATIVE,
                    "EYE SHAD(O)W wordmark", 0.85, "IMAGE_INFERRED",
                    art=True))

    # --- style --------------------------------------------------------
    intent.add(**_f("playful", "smiley motif, bubble scatter",
                    di.DECORATIVE, "overall", 0.75, "IMAGE_INFERRED",
                    art=True))
    intent.add(**_f("youthful", "mint palette, rounded letterforms",
                    di.DECORATIVE, "overall", 0.7, "IMAGE_INFERRED",
                    art=True))

    intent.decomposition = di.decompose({
        "PRODUCT_GEOMETRY": {"read": "case silhouette, lid relationship"},
        "PAN_LAYOUT": {"read": "rectangular pan grid, approx 4x3"},
        "MECHANICAL_COMPONENTS": {"read": "hinged lid, opening upward"},
        "MATERIAL_ZONES": {"read": "matte moulded plastic case"},
        "COLOUR_ZONES": {"read": "Pantone 621 C / 627 C"},
        "ARTWORK": {"read": "wordmarks, bubble scatter, shade labels"},
        "TYPOGRAPHY": {"read": "EYE SHADOW / OUTER GLOW / BBROSE"},
        "LIGHTING": {"ignored": "render lighting is not product geometry"},
        "BACKGROUND": {"ignored": "black sheet background is not artwork"},
        "PRESENTATION_EFFECTS": {"ignored": "sheet layout is not product"},
        "SHADOWS": {"ignored": "render shadow is not moulded relief"},
        "REFLECTIONS": {"ignored": "tray photo highlights are not cut-outs"},
    })
    intent.view = {
        "estimated_camera_view": "flat production sheet — orthographic "
                                 "artwork plus one three-quarter render "
                                 "and one photograph",
        "visible_faces": ["case face", "open interior", "display box flat"],
        "hidden_faces": ["case underside", "lid interior", "hinge detail"],
        "occlusion": "the open render occludes the lid interior",
        "perspective_uncertainty": "pan count read from a small render",
    }
    intent.unresolved_regions = [
        "exact pan count and grid (4x3 assumed, SOFT)",
        "mirror presence in the lid interior",
        "which edge is the product TOP",
        "pan pitch and pan size in millimetres — NOT readable from the "
        "sheet; no dimension is claimed",
    ]
    return intent
