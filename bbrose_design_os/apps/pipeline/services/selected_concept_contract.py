"""Human Gate-1 selected-concept authority for composite Product Container
tasks (2C-2D, 2026-07-27).

Three bounded, project-scoped records — none is production authority:

1. ``gate1_concept_selection`` — the HUMAN selection decision
   (``SELECT_CONTAINER_CONCEPT``): selected/unselected image identities, the
   human rationale verbatim, actor, timestamp and a canonical-JSON sha256
   identity. The immutable ``GateDecision`` row remains the platform's audit
   entry; this record carries the decision CONTENT. (The signed DecisionEvent
   chain has no pipeline concept-selection action in authz/1.4 — adding one
   is a policy-version decision, deliberately not taken here.)

2. ``selected_concept_visual_contract`` —
   ``container_selected_concept_visual_contract/1.0``: the authoritative
   visual relationships for the next stages (bottle form / body material /
   closure / front decoration / carton relationship), the PROHIBITED
   photographic interpretations, the persisted visual-quality warnings, and
   BOUNDED pixel measurements of the selected render. The selected render is
   the visual source of INTENT — no pixel-derived value is ever a production
   dimension, and every measurement carries confidence / source / tolerance /
   verification state.

3. Dropper decoration-zone augmentation — the mandated four-zone proposal
   (BODY front/back print, OPTIONAL collar band, technical bottom code).
   Applied ONLY on the contract-gated composite path; legacy bottle
   proposals are byte-identical without the contract.
"""
from __future__ import annotations

import hashlib
import json

CONTRACT_SCHEMA = "container_selected_concept_visual_contract/1.0"
META_KEY = "selected_concept_visual_contract"
SELECTION_META_KEY = "gate1_concept_selection"
DECISION_CODE = "SELECT_CONTAINER_CONCEPT"

# 2C-2D-CORR-2 §4: the product record's 40×40×110 describes the OUTER CARTON,
# never the bottle. These codes classify the contamination; the dims survive
# only under the bounded secondary-packaging record.
DIM_PROPOSAL_SCHEMA = "container_concept_dimension_proposal/1.0"
EXTENSIONS_SCHEMA = "container_profile_extensions/1.0"
SECONDARY_PACKAGING_KEY = "known_secondary_packaging_dimensions"
REFERENT_FINDING_KEY = "dimension_referent_finding"
CARTON_CONTAMINATION_CODES = (
    "CONTAINER_PROFILE_CARTON_DIMENSION_CONTAMINATION",
    "CONTAINER_DIMENSION_REFERENT_MISMATCH",
    "CARTON_DIMENSIONS_NOT_CONTAINER_DIMENSIONS",
)

# §9 additions — the /1.0 contract (hash-pinned by the signed selection
# record) is never mutated; these ride in a separate addendum record.
WARNINGS_ADDENDUM_KEY = "selected_concept_warnings_addendum"
WARNINGS_ADDENDUM = (
    "carton dimensions must never populate bottle geometry",
    "all bottle dimensions remain concept-only",
    "optional collar artwork is excluded pending manufacturer data",
)

# §8D: the collar zone is EXCLUDED from the confirmable set, not proposed.
COLLAR_ZONE_EXCLUSION = {
    "zone": "OPTIONAL_COLLAR_ZONE",
    "decision": "EXCLUDE_FROM_CONFIRMABLE_ZONE_SET",
    "reasons": [
        "no confirmed collar dimensions",
        "no required artwork",
        "metallic collar material already provides the intended accent",
        "optional future decoration may be reviewed only after "
        "manufacturer data",
    ],
}

# Measurement provenance vocabulary — every result is CONCEPT-ONLY.
SRC_PIXEL = "PIXEL_ANALYSIS_PIL_HSV"
SRC_AGENT_VISUAL = "AGENT_VISUAL_INSPECTION"
CONCEPT_ONLY = "CONCEPT_ONLY_UNVERIFIED"
UNAVAILABLE = "MEASUREMENT_UNAVAILABLE"

# §3: none of these may ever become printed artwork or re-enter prompts as a
# positive directive. They may appear in the contract ONLY inside the
# prohibited_interpretations subtree (mirrors the checkpoint's prompt
# prohibition discipline).
FORBIDDEN_MOTIF_TERMS = (
    "petal", "dewdrop", "droplet", "condensation", "liquid veil",
    "rose illustration", "botanical pattern", "floral pattern",
    "particle field",
)
MOTIF_OUTSIDE_PROHIBITION = "CONTRACT_FORBIDDEN_MOTIF_OUTSIDE_PROHIBITION"


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)


def _sha(payload) -> str:
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


# ---------------------------------------------------------------------------
# §4 — bounded visual analysis of the selected render
# ---------------------------------------------------------------------------

def _entry(name, value, *, units, confidence, tolerance, source,
           verification=CONCEPT_ONLY, note=""):
    e = {"measurement": name, "value": value, "units": units,
         "confidence": confidence, "tolerance": tolerance,
         "source": source, "verification_state": verification}
    if note:
        e["note"] = note
    return e


def measure_selected_concept(image_path) -> list[dict]:
    """Bounded pixel analysis of the selected concept render.

    Frame-fraction geometry + palette only — never mm, never production
    dimensions. Region masks are HSV heuristics; where a mask comes back
    empty the entry is recorded MEASUREMENT_UNAVAILABLE rather than guessed.
    """
    import colorsys

    from PIL import Image

    out: list[dict] = []
    im = Image.open(image_path).convert("RGB")
    W, H = im.size
    out.append(_entry("frame_size", [W, H], units="px", confidence=1.0,
                      tolerance=0, source=SRC_PIXEL,
                      note="exact raster dimensions of the concept render"))
    sw = 256
    sm = im.resize((sw, max(1, round(sw * H / W))))
    w, h = sm.size
    px = sm.load()

    def hsv(x, y):
        r, g, b = px[x, y]
        return colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

    def is_bg(x, y):
        _, s, v = hsv(x, y)
        return s < 0.10 and v > 0.82

    def bbox(mask):
        if not mask:
            return None
        xs = [x for x, _ in mask]
        ys = [y for _, y in mask]
        return (round(min(xs) / w, 3), round(min(ys) / h, 3),
                round((max(xs) + 1) / w, 3), round((max(ys) + 1) / h, 3))

    # -- negative space ------------------------------------------------------
    bg_n = sum(1 for y in range(h) for x in range(w) if is_bg(x, y))
    out.append(_entry("negative_space_fraction", round(bg_n / (w * h), 3),
                      units="fraction_of_frame", confidence=0.9,
                      tolerance=0.05, source=SRC_PIXEL))
    thirds = []
    for i in range(3):
        n = sum(1 for y in range(h)
                for x in range(i * w // 3, (i + 1) * w // 3) if is_bg(x, y))
        thirds.append(round(n / (w * h / 3), 3))
    out.append(_entry("negative_space_by_horizontal_third", thirds,
                      units="fraction_of_third", confidence=0.9,
                      tolerance=0.05, source=SRC_PIXEL,
                      note="left / centre / right vertical bands"))

    # -- dominant palette ----------------------------------------------------
    import collections
    q = sm.quantize(colors=6, method=Image.MEDIANCUT).convert("RGB")
    qx = q.load()
    counts = collections.Counter(qx[x, y] for y in range(h) for x in range(w))
    palette = [{"hex": f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}",
                "share": round(n / (w * h), 3)}
               for c, n in counts.most_common(6)]
    out.append(_entry("dominant_palette_6", palette, units="hex+share",
                      confidence=0.85, tolerance=0.03, source=SRC_PIXEL,
                      note="median-cut quantization; photographic lighting "
                           "included — not a print palette"))

    # -- regions (HSV heuristics, spatially constrained) ----------------------
    bulb = [(x, y) for y in range(int(h * 0.35)) for x in range(w)
            if hsv(x, y)[2] < 0.35]
    bb = bbox(bulb)
    if bb is None:
        out.append(_entry("bulb_bbox", None, units="frame_fraction",
                          confidence=0.0, tolerance=None, source=SRC_PIXEL,
                          verification=UNAVAILABLE))
        return out
    out.append(_entry("bulb_bbox", list(bb), units="frame_fraction",
                      confidence=0.75, tolerance=0.03, source=SRC_PIXEL,
                      note="dark-plum dropper bulb (darkest upper cluster)"))
    bx0, by0, bx1, by1 = bb
    bxc = (bx0 + bx1) / 2

    collar = [(x, y) for y in range(int(by1 * h) - 2, int(h * 0.55))
              for x in range(w)
              if abs(x / w - bxc) < (bx1 - bx0) / 2 + 0.06
              and 0.02 <= hsv(x, y)[0] <= 0.15 and hsv(x, y)[1] > 0.30]
    cb = bbox(collar)
    if cb:
        out.append(_entry("collar_bbox", list(cb), units="frame_fraction",
                          confidence=0.6, tolerance=0.05, source=SRC_PIXEL,
                          note="rose-gold metallic band under the bulb; mask "
                               "can leak into warm shoulder reflections"))
    body_top = (cb[3] if cb else by1)
    body = [(x, y) for y in range(int(body_top * h), h) for x in range(w)
            if abs(x / w - bxc) < 0.20 and not is_bg(x, y)]
    bob = bbox(body)
    if bob:
        out.append(_entry("bottle_body_bbox", list(bob),
                          units="frame_fraction", confidence=0.7,
                          tolerance=0.04, source=SRC_PIXEL))

    # carton: object columns clearly left of the bottle strip, by density
    def col_density(x):
        return sum(1 for y in range(h) if not is_bg(x, y)
                   and hsv(x, y)[2] > 0.4) / h
    carton_cols = [x for x in range(int((bxc - 0.22) * w))
                   if col_density(x) > 0.25]
    carton = [(x, y) for x in carton_cols for y in range(h)
              if not is_bg(x, y) and hsv(x, y)[2] > 0.4]
    cab = bbox(carton)
    if cab:
        out.append(_entry("carton_bbox", list(cab), units="frame_fraction",
                          confidence=0.65, tolerance=0.05, source=SRC_PIXEL,
                          note="column-density mask; floor shadow excluded "
                               "by value threshold"))

    # typography zone on the bottle front (dark copy inside the body strip)
    if bob:
        type_px = [(x, y) for y in range(int(body_top * h), int(bob[3] * h))
                   for x in range(w)
                   if abs(x / w - bxc) < 0.17 and hsv(x, y)[2] < 0.55]
        tb = bbox(type_px)
        if tb:
            out.append(_entry("front_typography_zone_bbox", list(tb),
                              units="frame_fraction", confidence=0.65,
                              tolerance=0.04, source=SRC_PIXEL,
                              note="wine-plum copy block on the frosted "
                                   "body; includes logo + name + support "
                                   "line"))

    # -- derived ratios (frame-fraction arithmetic, concept-only) ------------
    if bob and cb:
        bulb_h = by1 - by0
        collar_h = cb[3] - cb[1]
        body_h = bob[3] - bob[1]
        body_w = bob[2] - bob[0]
        total_h = bob[3] - by0
        ratios = (
            ("body_to_closure_ratio",
             round(body_h / max(bulb_h + collar_h, 1e-6), 2), 0.6, 0.15,
             "body height vs bulb+collar height"),
            ("body_aspect_ratio_h_over_w",
             round((body_h * H) / max(body_w * W, 1e-6), 2), 0.7, 0.1,
             "frame-scaled: height and width fractions span different "
             "pixel axes"),
            ("collar_height_rel_body",
             round(collar_h / max(body_h, 1e-6), 2), 0.55, 0.1,
             "collar mask may over-read"),
            ("bulb_height_rel_collar",
             round(bulb_h / max(collar_h, 1e-6), 2), 0.55, 0.15, ""),
            ("bottle_total_height_fraction_of_frame",
             round(total_h, 3), 0.7, 0.05, ""),
        )
        for name, val, conf, tol, note in ratios:
            out.append(_entry(name, val, units="ratio", confidence=conf,
                              tolerance=tol, source=SRC_PIXEL, note=note))
        if cab:
            out.append(_entry("carton_to_bottle_height_scale",
                              round((cab[3] - cab[1]) / max(total_h, 1e-6),
                                    2),
                              units="ratio", confidence=0.6, tolerance=0.1,
                              source=SRC_PIXEL))

    # -- agent visual reads the masks cannot resolve -------------------------
    out.append(_entry("visible_glass_base_thickness_rel_body", 0.05,
                      units="ratio", confidence=0.5, tolerance=0.02,
                      source=SRC_AGENT_VISUAL,
                      note="clear-glass base strip read from the render"))
    out.append(_entry("shoulder_relationship", "flat_to_restrained",
                      units="categorical", confidence=0.8, tolerance=None,
                      source=SRC_AGENT_VISUAL))
    out.append(_entry("logo_zone_position",
                      "small BBROSE mark upper area of the front typography "
                      "block, above the product name",
                      units="categorical", confidence=0.7, tolerance=None,
                      source=SRC_AGENT_VISUAL))
    return out


# ---------------------------------------------------------------------------
# §2/§3/§7 — the authoritative visual contract
# ---------------------------------------------------------------------------

def build_visual_contract(selected_image, *, measurements,
                          human_rationale: dict) -> dict:
    """The authoritative selected-concept relationships (§2), the prohibited
    photographic interpretations (§3) and the persisted visual-quality
    warnings (§7), derived from — and pinned to — the selected image."""
    prov = (getattr(selected_image, "reference_provenance", None) or {})
    contract = {
        "schema_version": CONTRACT_SCHEMA,
        "authority": {
            "status": "AUTHORITATIVE_VISUAL_INTENT_CONCEPT_ONLY",
            "visual_source_of_intent": f"GeneratedImage #{selected_image.id}",
            "production_dimensions":
                "NEVER inferred from the image — pixel measurements are "
                "concept-only relationships",
        },
        "provenance": {
            "source_image_id": selected_image.id,
            "variation_identity": prov.get("variation_identity", ""),
            "direction_name": selected_image.direction_name or "",
            "task_id": selected_image.task_id,
            "qa_passed": selected_image.qa_passed,
            "human_rationale": human_rationale,
        },
        "bottle_form": {
            "requirements": [
                "premium rigid serum dropper bottle",
                "approximately 30 ml, concept-only",
                "cylindrical body",
                "tall and visually elegant proportion",
                "flat or very restrained shoulder",
                "short controlled neck",
                "stable thick glass base",
                "realistic wall thickness",
            ],
            "prohibitions": [
                "no exaggerated shoulder",
                "no squat or bulky bottle",
                "no perfume-style fantasy shape",
            ],
        },
        "body_material": {
            "requirements": [
                "frosted translucent glass",
                "dusty rose / smoky blush material character",
                "subtle internal depth",
                "controlled warm undertone",
                "visible glass base",
                "premium soft-frosted finish",
            ],
            "prohibitions": [
                "do not flatten the body into one opaque pink fill",
            ],
            "keep_separate_later": [
                "glass wall", "product-fill appearance", "frost treatment",
                "highlight/reflection", "printed decoration",
            ],
            "note": "photographic reflections are not printed artwork",
        },
        "closure": {
            "requirements": [
                "smooth dark-plum pipette bulb",
                "polished rose-gold metallic collar",
                "clean cylindrical collar",
                "refined bulb-to-collar proportion",
                "realistic dropper construction",
            ],
            "prohibitions": [
                "strongly ribbed pharmacy caps",
                "oversized metallic collars",
                "gold-only yellow metal",
                "black generic closure",
                "supplier-specific copied geometry",
            ],
        },
        "front_decoration": {
            "rule": "decoration appears directly printed on the frosted "
                    "glass",
            "prohibitions": [
                "a rectangular adhesive label",
                "a large opaque panel",
                "a boxed background behind the typography",
                "a generic centered label fallback",
            ],
            "hierarchy": ["BBROSE", "Rose Damascena", "Night Repair Oil",
                          "supporting volume or technical copy"],
            "dominant_text": "the product name is the dominant "
                             "consumer-facing text",
            "typography_qualities": ["elegant", "restrained", "readable",
                                     "premium", "spacious",
                                     "appropriate for skincare"],
            "render_defects_not_authoritative":
                "the selected image has weak small-copy contrast and "
                "imperfect line spacing — preserve the hierarchy and mood, "
                "not the rendering defects",
            "improve_later": ["BBROSE logo visibility",
                              "product-name legibility", "line spacing",
                              "alignment", "contrast", "exact text accuracy"],
            "reconstruction_rule": "keep all text live during reconstruction",
        },
        "carton_relationship": {
            "requirements": [
                "tall straight-tuck-end carton",
                "muted dusty mauve / blush / smoky-rose color world",
                "soft-touch or matte appearance",
                "restrained rose-gold detail",
                "bottle and carton clearly belong to one family",
                "bottle remains the hero",
                "carton remains secondary",
            ],
            "suggested_hierarchy": [
                "small BBROSE mark near the top",
                "Rose Damascena in the middle or lower-middle",
                "small Night Repair Oil support line",
                "one restrained metallic rule or micro-detail",
            ],
            "prohibitions": [
                "do not copy the exact pseudo-text or spacing errors from "
                "the generated image",
                "do not add large floral artwork",
            ],
        },
        "prohibited_interpretations": {
            "classification": "PHOTOGRAPHIC_STYLING_NOT_PRINTED_ARTWORK",
            "never_printed_artwork": [
                "shadows", "floor reflections", "highlights",
                "backdrop colors", "photographic gradients", "water",
                "condensation", "droplets", "petals", "flowers", "props",
            ],
            "do_not_introduce": [
                "literal rose illustration", "botanical pattern",
                "decorative particle field", "dewdrop motif",
                "generic label card", "competitor layout",
                "supplier branding", "task #51 visual logic",
                "liquid veil styling",
            ],
        },
        "visual_quality_warnings": [
            "BBROSE logo currently too small / low contrast",
            "bottle supporting copy is difficult to read",
            "product-name line break requires refinement",
            "generated pseudo-text is not production copy",
            "bottle may need a slightly taller/slimmer proportion",
            "carton typography needs exact hierarchy reconstruction",
            "carton must not dominate the bottle",
            "photographic material gradients must not become printed "
            "gradients",
        ],
        "warnings_note": "warnings are persisted for later correction and "
                         "do not invalidate the selection",
        "measurements": measurements,
        # §5 — the editable fields the human will confirm at the next gate.
        # Fields with a container_profile/1.0 name confirm through the
        # existing contract; the rest are concept-only extras the
        # confirmation mandate must place (schema decision, not taken here).
        "profile_confirmation_fields": [
            {"field": "body height", "schema_1_0": "body_height_mm"},
            {"field": "body diameter", "schema_1_0": "body_width_mm"},
            {"field": "base thickness", "schema_1_0": None},
            {"field": "shoulder radius", "schema_1_0": "shoulder_height_mm"},
            {"field": "neck diameter", "schema_1_0": "neck_width_mm"},
            {"field": "collar diameter", "schema_1_0": "cap_width_mm"},
            {"field": "collar height", "schema_1_0": "cap_height_mm"},
            {"field": "bulb height", "schema_1_0": None},
            {"field": "total height", "schema_1_0": None},
            {"field": "capacity", "schema_1_0": None},
            {"field": "transparency", "schema_1_0": "body_transparency"},
            {"field": "frost intensity", "schema_1_0": None},
        ],
        "zone_notes": {
            "OPTIONAL_COLLAR_ZONE":
                "optional finish or small accent only; no required artwork; "
                "must remain unconfirmed unless collar dimensions exist",
            "BOTTOM_CODE_ZONE": "technical batch/date code only",
            "placement_rule":
                "front hero artwork never on the bottom or back",
        },
    }
    contract["contract_hash"] = _sha(contract)
    return contract


def validate_motif_freedom(contract: dict) -> list[str]:
    """§3/§10: forbidden motif terms may appear ONLY inside the
    prohibited_interpretations subtree. Anywhere else is a violation."""
    problems: list[str] = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, path + (str(k),))
        elif isinstance(node, (list, tuple)):
            for i, v in enumerate(node):
                walk(v, path + (str(i),))
        elif isinstance(node, str):
            low = node.lower()
            for term in FORBIDDEN_MOTIF_TERMS:
                if term in low and "prohibited_interpretations" not in path \
                        and "prohibitions" not in path:
                    problems.append(
                        f"{MOTIF_OUTSIDE_PROHIBITION}: {term!r} at "
                        f"{'/'.join(path)}")
    walk(contract, ())
    return problems


def persist_visual_contract(project, contract: dict) -> None:
    meta = dict(project.metadata or {})
    meta[META_KEY] = contract
    project.metadata = meta
    project.save(update_fields=["metadata", "updated_at"])


def stored_contract_for(task, approved_image):
    """The project's visual contract, ONLY when it is pinned to exactly this
    approved image — anything else returns None and the legacy path runs."""
    project = getattr(task, "project", None)
    if project is None:
        return None
    contract = (project.metadata or {}).get(META_KEY)
    if not isinstance(contract, dict):
        return None
    if (contract.get("provenance") or {}).get("source_image_id") \
            != getattr(approved_image, "id", None):
        return None
    return contract


# ---------------------------------------------------------------------------
# §1 — the human selection decision record
# ---------------------------------------------------------------------------

def record_selection_decision(project, *, selected_image, unselected_images,
                              rationale: dict, actor, contract_hash: str,
                              now_iso: str) -> dict:
    """Persist the SELECT_CONTAINER_CONCEPT decision content on the project.
    The GateDecision row (created by the approval endpoint) is the immutable
    audit entry; this record carries identities, rationale and a sha256 over
    its own canonical JSON."""
    def ident(img):
        prov = (getattr(img, "reference_provenance", None) or {})
        return {"image_id": img.id,
                "variation_identity": prov.get("variation_identity", "")}

    record = {
        "decision": DECISION_CODE,
        "selected": ident(selected_image),
        "unselected": [ident(i) for i in unselected_images],
        "unselected_disposition":
            "valid unselected alternatives, preserved in the project "
            "history — never superseded, never deleted",
        "human_rationale": rationale,
        "decided_by": getattr(actor, "username", str(actor)),
        "decided_at": now_iso,
        "visual_contract_hash": contract_hash,
    }
    record["record_hash"] = _sha(record)
    meta = dict(project.metadata or {})
    meta[SELECTION_META_KEY] = record
    project.metadata = meta
    project.save(update_fields=["metadata", "updated_at"])
    return record


# ---------------------------------------------------------------------------
# §4 — carton-dimension hygiene (2C-2D-CORR-2)
# ---------------------------------------------------------------------------

def secondary_packaging_record(product) -> dict:
    """The product record's outer-carton dimensions, preserved under an
    explicit referent — never as container geometry. The product record
    itself is not touched."""
    def _f(name):
        v = getattr(product, name, None) if product else None
        return float(v) if v is not None else None
    return {
        "width_mm": _f("width_mm"),
        "depth_mm": _f("depth_mm"),
        "height_mm": _f("height_mm"),
        "referent": "OUTER_CARTON",
        "source": "PRODUCT_RECORD",
        "verification": "AS_RECORDED_NOT_MANUFACTURER_VERIFIED",
    }


def dimension_referent_finding() -> dict:
    return {
        "codes": list(CARTON_CONTAMINATION_CODES),
        "statement": ("the product record's 40×40×110 mm describes the "
                      "OUTER CARTON of BBR-SK-201; it must never populate "
                      "bottle width, diameter, height, total height, cap "
                      "dimensions or any container geometry validator"),
        "disposition": ("carton dimensions preserved ONLY under "
                        f"'{SECONDARY_PACKAGING_KEY}'; container profile "
                        "dimension fields left MISSING pending human "
                        "confirmation"),
    }


# ---------------------------------------------------------------------------
# §5 — editable concept-only dimension proposal
# ---------------------------------------------------------------------------

_SRC_50 = "WEB_SOURCE_50_ANALOG_FACT"
_SRC_OWNER = "OWNER_CONCEPT_DECISION"
_SRC_IMG = "IMAGE_97_RATIO"


def _dim(field, value, unit, *, source, derivation, confidence, tolerance,
         note=""):
    e = {"field": field, "value": value, "unit": unit, "source": source,
         "derivation_method": derivation, "confidence": confidence,
         "tolerance": tolerance,
         "verification_state": CONCEPT_ONLY,
         "manufacturer_confirmation_required": True,
         "editable_before_confirmation": True}
    if note:
        e["note"] = note
    return e


def build_concept_dimension_proposal(contract: dict) -> dict:
    """Bounded ranges from the approved analog (source 50), the selected
    render's ratios and the owner's 30 ml concept decision — never exact
    pixel-derived values, never presented as BBR-SK-201 production facts."""
    ratios = {m["measurement"]: m for m in
              (contract.get("measurements") or [])
              if isinstance(m, dict)}

    def _r(name, default=None):
        v = (ratios.get(name) or {}).get("value")
        return v if isinstance(v, (int, float)) else default

    body_frac = None
    bb = (ratios.get("bottle_body_bbox") or {}).get("value")
    bulb = (ratios.get("bulb_bbox") or {}).get("value")
    if isinstance(bb, list) and isinstance(bulb, list):
        body_frac = (bb[3] - bb[1]) / max((bb[3] - bulb[1]), 1e-6)
    body_share = body_frac if body_frac else 0.65
    analog_total = 104.0                       # source 50, ~104 mm overall
    body_est = analog_total * body_share
    aspect = _r("body_aspect_ratio_h_over_w", 1.9)
    collar_rel = _r("collar_height_rel_body", 0.22)
    bulb_rel = _r("bulb_height_rel_collar", 1.5)

    def rng(mid, spread):
        return [round(mid - spread, 1), round(mid + spread, 1)]

    proposals = [
        _dim("nominal_capacity", 30, "ml", source=_SRC_OWNER,
             derivation="owner concept decision (2C-2B mandate)",
             confidence=1.0, tolerance="concept-only",
             note="APPROXIMATELY_30_ML_CONCEPT_ONLY — not a fill "
                  "specification"),
        _dim("total_height", rng(analog_total, 5), "mm", source=_SRC_50,
             derivation="analog feasibility: source-50 30 ml dropper "
                        "bottle overall height ≈104 mm",
             confidence=0.4, tolerance="±5 mm",
             note="whether the analog's height includes the dropper "
                  "closure is UNSPECIFIED in the source — recorded as "
                  "overall height INCLUDING closure; the referent must be "
                  "fixed at manufacturer confirmation"),
        _dim("body_height", rng(body_est, body_est * 0.08), "mm",
             source=f"{_SRC_50}+{_SRC_IMG}",
             derivation="analog total ≈104 mm × image body-share "
                        f"≈{round(body_share, 2)} (body bbox vs bulb-to-base "
                        "extent)",
             confidence=0.4, tolerance="±8%",
             note="body only, EXCLUDING the dropper closure"),
        _dim("body_diameter", rng((body_est / aspect + 31.8) / 2, 3), "mm",
             source=f"{_SRC_50}+{_SRC_IMG}",
             derivation="midpoint of source-50 analog diameter ≈31.8 mm and "
                        "image aspect-derived estimate "
                        f"(body height ÷ {round(aspect, 2)})",
             confidence=0.4, tolerance="±3 mm"),
        _dim("neck_diameter", rng(10, 1), "mm", source=_SRC_50,
             derivation="source-50 analog mouth ≈10 mm",
             confidence=0.4, tolerance="±1 mm"),
        _dim("collar_height", rng(body_est * collar_rel,
                                  body_est * collar_rel * 0.2), "mm",
             source=_SRC_IMG,
             derivation="image collar-to-body ratio "
                        f"≈{round(collar_rel, 2)} × body-height estimate",
             confidence=0.35, tolerance="±20%",
             note="the collar mask can over-read into shoulder reflections"),
        _dim("bulb_height", rng(body_est * collar_rel * bulb_rel,
                                body_est * collar_rel * bulb_rel * 0.2),
             "mm", source=_SRC_IMG,
             derivation="image bulb-to-collar ratio "
                        f"≈{round(bulb_rel, 2)} × collar-height estimate",
             confidence=0.35, tolerance="±20%"),
        _dim("base_thickness", [3.0, 4.5], "mm", source=_SRC_IMG,
             derivation="agent visual read of the clear-glass base strip "
                        "(~5% of body height)",
             confidence=0.3, tolerance="range only"),
        _dim("collar_diameter", None, "mm", source="NONE",
             derivation="no analog or image basis — requires manufacturer "
                        "data",
             confidence=0.0, tolerance=None),
    ]
    return {
        "schema_version": DIM_PROPOSAL_SCHEMA,
        "authority": "CONCEPT_ONLY_UNVERIFIED — every value is an editable "
                     "proposal; nothing here is a production dimension",
        "analog_disclaimer": ("source-50 values are analog feasibility "
                              "facts for a comparable 30 ml dropper bottle "
                              "— they are NOT BBR-SK-201 production facts"),
        "proposals": proposals,
    }


# ---------------------------------------------------------------------------
# §6/§7 — additive profile extension record (zero migration: spec JSON)
# ---------------------------------------------------------------------------

def build_profile_extensions(dim_proposal: dict) -> dict:
    """container_profile_extensions/1.0 — the dropper fields the base
    container_profile/1.0 cannot own. Values are the §5 proposal ranges (or
    qualitative concept tokens); everything stays editable and UNCONFIRMED."""
    by_field = {p["field"]: p for p in (dim_proposal or {}).get(
        "proposals", [])}

    def _ext(name, *, qualitative=None):
        p = by_field.get(name)
        return {
            "value": qualitative if qualitative is not None
            else (p or {}).get("value"),
            "unit": (p or {}).get("unit"),
            "source": (p or {}).get("source",
                                    "SELECTED_CONCEPT_VISUAL_CONTRACT"
                                    if qualitative else "NONE"),
            "verification": CONCEPT_ONLY,
            "editable": True,
        }
    return {
        "schema_version": EXTENSIONS_SCHEMA,
        "proposal_authority": "CONCEPT_ONLY",
        "confirmation_state": "UNCONFIRMED",
        "fields": {
            "subtype": _ext("subtype", qualitative="SERUM_DROPPER_BOTTLE"),
            "body_height": _ext("body_height"),
            "body_diameter": _ext("body_diameter"),
            "total_height": _ext("total_height"),
            "base_thickness": _ext("base_thickness"),
            "neck_diameter": _ext("neck_diameter"),
            "collar_diameter": _ext("collar_diameter"),
            "collar_height": _ext("collar_height"),
            "bulb_height": _ext("bulb_height"),
            "nominal_capacity": _ext("nominal_capacity"),
            "frost_intensity": _ext("frost_intensity",
                                    qualitative="SOFT_FROSTED"),
            "glass_translucency": _ext("glass_translucency",
                                       qualitative="TRANSLUCENT"),
        },
    }


def persist_warnings_addendum(project) -> dict:
    """§9: additive warnings — the hash-pinned /1.0 contract is untouched."""
    contract = (project.metadata or {}).get(META_KEY) or {}
    record = {
        "schema_version": "selected_concept_warnings_addendum/1.0",
        "base_contract_hash": contract.get("contract_hash", ""),
        "added": list(WARNINGS_ADDENDUM),
        "reason": "2C-2D-CORR-2 §9",
    }
    meta = dict(project.metadata or {})
    meta[WARNINGS_ADDENDUM_KEY] = record
    project.metadata = meta
    project.save(update_fields=["metadata", "updated_at"])
    return record


def all_warnings(project) -> list[str]:
    """Base contract warnings + addendum, in presentation order."""
    meta = project.metadata or {}
    base = ((meta.get(META_KEY) or {}).get("visual_quality_warnings")
            or [])
    added = ((meta.get(WARNINGS_ADDENDUM_KEY) or {}).get("added") or [])
    return list(base) + list(added)


# ---------------------------------------------------------------------------
# §5/§6 — contract-gated profile seeding + dropper zone augmentation
# ---------------------------------------------------------------------------

def seed_profile_from_visual_contract(record: dict, contract: dict) -> dict:
    """Concept-only field proposals from the visual contract — always
    INFERRED_NONAUTHORITATIVE, never prefilled as confirmed facts. The
    contract derives from the HUMAN-selected concept, so it supersedes other
    INFERRED/MISSING seeds (e.g. the heuristic 'screw' cap default) — but a
    USER-confirmed or VERIFIED value is never touched."""
    import copy

    from apps.pipeline.services import container_contract as cc

    out = copy.deepcopy(record)
    fields = out.setdefault("fields", {})
    # §5 archetype: the human-selected concept (serum dropper bottle) is
    # stronger evidence than the keyword heuristic — the live pilot brief's
    # "apothecary" once inferred a jar. Top-level keys drive surfaces_for();
    # still a PROPOSAL, confirmed only by the human at the next gate.
    out["archetype"] = "bottle"
    out["variant"] = "cylindrical"
    # §7 qualitative tokens — no exact physical value is confirmed here
    proposals = {
        "archetype": "bottle",
        "variant": "cylindrical",
        "cap_type": "PIPETTE_DROPPER — polished rose-gold collar, smooth "
                    "dark-plum bulb (concept-only)",
        "cap_color": "POLISHED_ROSE_GOLD collar / SMOOTH_DARK_PLUM bulb "
                     "(concept-only)",
        "body_material": "FROSTED_TRANSLUCENT_GLASS (concept-only)",
        "body_base_color": "DUSTY_ROSE / SMOKY_BLUSH (concept-only)",
        "shoulder_type": "FLAT_OR_RESTRAINED (concept-only)",
        "body_transparency": "TRANSLUCENT — soft-frosted (concept-only)",
    }
    overridable = {cc.INFERRED, cc.MISSING}
    for name, text in proposals.items():
        verification = (fields.get(name) or {}).get("verification",
                                                    cc.MISSING)
        if verification in overridable:
            fields[name] = {"value": text, "source": cc.SRC_INFERRED,
                            "verification": cc.INFERRED}
    out["profile_hash"] = cc.profile_hash(out)
    return out


# ---------------------------------------------------------------------------
# 2C-2E §1/§2/§8 — human profile + dimension confirmation (concept authority)
# ---------------------------------------------------------------------------

HUMAN_CONFIRMED = "HUMAN_CONFIRMED_CONCEPT_ONLY"
NOT_MFG_VERIFIED = "NOT_MANUFACTURER_VERIFIED"
DECISIONS_SCHEMA = "container_confirmation_decisions/1.0"

#: 2C-2E §2 — the owner's confirmed concept dimensions, with referents.
CONFIRMED_CONCEPT_DIMENSIONS = {
    "nominal_capacity": {"value": 30, "unit": "ml"},
    "total_height": {"value": 104, "unit": "mm",
                     "referent": "INCLUDES_DROPPER_CLOSURE"},
    "body_height": {"value": 68, "unit": "mm",
                    "referent": "BOTTOM_BASE_TO_TOP_OF_SHOULDER"},
    "body_diameter": {"value": 33, "unit": "mm"},
    "base_thickness": {"value": 3.5, "unit": "mm"},
    "shoulder_radius": {"value": 3, "unit": "mm"},
    "neck_diameter": {"value": 10, "unit": "mm",
                      "referent": "SITS_PARTLY_WITHIN_COLLAR_ASSEMBLY_"
                                  "NEVER_ADDED_TO_TOTAL_HEIGHT_TWICE"},
    "collar_diameter": {"value": 28, "unit": "mm"},
    "collar_height": {"value": 14, "unit": "mm", "referent": "VISIBLE"},
    "bulb_height": {"value": 22, "unit": "mm", "referent": "VISIBLE"},
    "frost_intensity": {"value": 70, "unit": "/100"},
    "glass_translucency": {"value": 35, "unit": "/100",
                           "referent": "VISUAL_TRANSLUCENCY"},
    "subtype": {"value": "SERUM_DROPPER_BOTTLE", "unit": None},
}


def confirm_extension_dimensions(output, *, values=None, actor, now_iso
                                 ) -> dict:
    """§2: record the human's concept-dimension confirmations on the
    container_profile_extensions/1.0 record. Every value stays editable,
    NOT_MANUFACTURER_VERIFIED, and manufacturer-confirmation-required —
    concept authority is never production authority."""
    values = values or CONFIRMED_CONCEPT_DIMENSIONS
    spec = output.spec_sheet or {}
    ext = spec.get(EXTENSIONS_SCHEMA) or {
        "schema_version": EXTENSIONS_SCHEMA, "fields": {}}
    fields = ext.setdefault("fields", {})
    for name, v in values.items():
        entry = dict(fields.get(name) or {})
        entry.update({
            "value": v["value"], "unit": v.get("unit"),
            "confirmation_authority": HUMAN_CONFIRMED,
            "production_verification": NOT_MFG_VERIFIED,
            "editable": True,
            "manufacturer_confirmation_required": True,
            "source": "HUMAN_CONFIRMATION_2C_2E",
        })
        if v.get("referent"):
            entry["referent"] = v["referent"]
        fields[name] = entry
    ext["confirmation_state"] = HUMAN_CONFIRMED
    ext["proposal_authority"] = "CONCEPT_ONLY"
    ext["confirmed_by"] = getattr(actor, "username", str(actor))
    ext["confirmed_at"] = now_iso
    ext["referent_notes"] = {
        "total_height": "INCLUDES_DROPPER_CLOSURE",
        "body_height": "BOTTOM_BASE_TO_TOP_OF_SHOULDER",
        "neck": "sits partly within the collar assembly — never added to "
                "the total height a second time",
        "tolerances": "no tolerance here is a verified manufacturing "
                      "tolerance",
    }
    spec[EXTENSIONS_SCHEMA] = ext
    output.spec_sheet = spec
    output.save(update_fields=["spec_sheet"])
    return ext


def record_confirmation_decisions(output, project, *, actor, now_iso,
                                  profile_hash, zone_set_hash,
                                  combined_hash) -> dict:
    """§8: the six explicit human confirmation decisions, each referencing
    the full selection lineage. These decisions authorize reconstruction to
    the Gate-2 review and NOTHING beyond it."""
    contract = (project.metadata or {}).get(META_KEY) or {}
    event = (project.metadata or {}).get("gate1_concept_selection_event") \
        or {}
    refs = {
        "project_id": project.pk,
        "task_id": output.task_id,
        "selected_image_id": (contract.get("provenance") or {}).get(
            "source_image_id"),
        "selected_variation_identity": (contract.get("provenance") or {}
                                        ).get("variation_identity"),
        "visual_contract_hash": contract.get("contract_hash"),
        "concept_selection_event": {
            "event_id": event.get("event_id"),
            "sequence_number": event.get("sequence_number")},
        "confirmed_profile_hash": profile_hash,
        "confirmed_zone_set_hash": zone_set_hash,
        "combined_confirmation_hash": combined_hash,
    }
    decisions = [
        {"decision": "CONTAINER_PROFILE_CONFIRMED",
         "subject": "container_profile/1.0"},
        {"decision": "CONCEPT_DIMENSIONS_CONFIRMED",
         "subject": EXTENSIONS_SCHEMA},
        {"decision": "BODY_FRONT_PRINT_ZONE_CONFIRMED",
         "subject": "z_front"},
        {"decision": "BODY_BACK_PRINT_ZONE_CONFIRMED",
         "subject": "z_back"},
        {"decision": "BOTTOM_CODE_ZONE_CONFIRMED",
         "subject": "z_bottom_code"},
        # §AH (sprint 15, WI-3C). The jar emitted geometry to `z_wrap` while
        # the contract confirmed nothing there — production code placing
        # artwork on an unconfirmed surface, pinned since WI-Z and now ruled.
        # BODY_WRAP is the DEVELOPED CYLINDER: 125.66 mm at a 40 mm body,
        # where BODY_FRONT is 40.00 mm. A factor of π is not a spelling
        # difference, and a wrap label (one artwork, one seam, no reverse) is
        # not a front/back pair (two artworks, two keylines). Confirmed
        # EXACTLY as emitted — no coverage re-tuned, technique tuple left at
        # one member — so no zone_hash, zone_set_hash or
        # combined_confirmation_hash moves. See §AH4.
        {"decision": "BODY_WRAP_LABEL_ZONE_CONFIRMED",
         "subject": "z_wrap"},
        {"decision": "OPTIONAL_COLLAR_ZONE_EXCLUSION_CONFIRMED",
         "subject": "OPTIONAL_COLLAR_ZONE",
         "state": "EXCLUDED_FROM_CONFIRMABLE_ZONE_SET"},
    ]
    record = {
        "schema_version": DECISIONS_SCHEMA,
        "authority": HUMAN_CONFIRMED,
        "decided_by": getattr(actor, "username", str(actor)),
        "decided_at": now_iso,
        "references": refs,
        "decisions": decisions,
        "non_authorizations": [
            "human_design_acceptance", "gate_2", "packaging_creation",
            "production_authority"],
    }
    record["record_hash"] = _sha(record)
    spec = output.spec_sheet or {}
    spec[DECISIONS_SCHEMA] = record
    output.spec_sheet = spec
    output.save(update_fields=["spec_sheet"])
    return record


#: 2C-2E-CORR-2 §3 — the owner's revised closure values (68 + 3 + 11.5 +
#: 21.5 = 104). Visual concept values, never tooling dimensions.
CORR2_CLOSURE_REVISIONS = {
    "visible_neck_height": {"value": 3, "unit": "mm",
                            "referent": "VISIBLE_BETWEEN_SHOULDER_AND_"
                                        "COLLAR"},
    "collar_diameter": {"value": 24, "unit": "mm"},
    "collar_height": {"value": 11.5, "unit": "mm", "referent": "VISIBLE"},
    "bulb_width": {"value": 13, "unit": "mm",
                   "referent": "MAXIMUM_VISIBLE"},
    "bulb_height": {"value": 21.5, "unit": "mm", "referent": "VISIBLE"},
}


#: 2C-2E-CORR-3 §3 — the FINAL concept-only proportion amendment
#: (70.5 + 2.5 + 9.5 + 21.5 = 104). Visual concept values only.
CORR3_PROPORTION_REVISIONS = {
    "body_diameter": {"value": 31.5, "unit": "mm"},
    "body_height": {"value": 70.5, "unit": "mm",
                    "referent": "BOTTOM_BASE_TO_TOP_OF_SHOULDER"},
    "neck_diameter": {"value": 9, "unit": "mm"},
    "visible_neck_height": {"value": 2.5, "unit": "mm"},
    "collar_diameter": {"value": 21.5, "unit": "mm"},
    "collar_height": {"value": 9.5, "unit": "mm", "referent": "VISIBLE"},
    "bulb_width": {"value": 11, "unit": "mm",
                   "referent": "MAXIMUM_VISIBLE"},
    "bulb_height": {"value": 21.5, "unit": "mm", "referent": "VISIBLE"},
}


def amend_closure_dimensions(output, *, revisions: dict, actor, now_iso,
                             reason: str) -> dict:
    """2C-2E-CORR-2 §3: an ADDITIVE human concept-dimension amendment.

    The prior confirmation history is never rewritten: every amended field
    records its previous value inside the amendment entry, the entry itself
    is appended to ``amendments``, and the authority stays
    HUMAN_CONFIRMED_CONCEPT_ONLY / NOT_MANUFACTURER_VERIFIED — these are
    visual concept values, never tooling dimensions or production
    tolerances."""
    spec = output.spec_sheet or {}
    ext = spec.get(EXTENSIONS_SCHEMA) or {
        "schema_version": EXTENSIONS_SCHEMA, "fields": {}}
    fields = ext.setdefault("fields", {})
    previous = {}
    for name, v in revisions.items():
        prior = dict(fields.get(name) or {})
        previous[name] = prior.get("value")
        entry = prior
        entry.update({
            "value": v["value"], "unit": v.get("unit", "mm"),
            "confirmation_authority": HUMAN_CONFIRMED,
            "production_verification": NOT_MFG_VERIFIED,
            "editable": True,
            "manufacturer_confirmation_required": True,
            "source": "HUMAN_VISUAL_AMENDMENT_2C_2E_CORR_2",
        })
        if v.get("referent"):
            entry["referent"] = v["referent"]
        fields[name] = entry
    amendment = {
        "amendment": "HUMAN_CONCEPT_DIMENSION_AMENDMENT",
        "reason": reason,
        "decided_by": getattr(actor, "username", str(actor)),
        "decided_at": now_iso,
        "authority": HUMAN_CONFIRMED,
        "revised": {k: v["value"] for k, v in revisions.items()},
        "previous_values": previous,
    }
    amendment["amendment_hash"] = _sha(amendment)
    ext.setdefault("amendments", []).append(amendment)
    ext["confirmation_state"] = HUMAN_CONFIRMED
    ext["extensions_hash"] = _sha(
        {k: (fields.get(k) or {}).get("value") for k in sorted(fields)})
    spec[EXTENSIONS_SCHEMA] = ext
    output.spec_sheet = spec
    output.save(update_fields=["spec_sheet"])
    return amendment


def confirmed_dropper_geometry(spec: dict) -> dict | None:
    """The reconstruction geometry from a HUMAN_CONFIRMED extensions record,
    or None when this is not the 2C-2E dropper path."""
    ext = (spec or {}).get(EXTENSIONS_SCHEMA) or {}
    if ext.get("confirmation_state") != HUMAN_CONFIRMED:
        return None
    f = ext.get("fields") or {}

    def _v(name):
        return (f.get(name) or {}).get("value")
    required = ("total_height", "body_height", "body_diameter",
                "collar_height", "bulb_height")
    if any(_v(n) is None for n in required):
        return None
    return {
        "total_height_mm": float(_v("total_height")),
        "body_height_mm": float(_v("body_height")),
        "body_diameter_mm": float(_v("body_diameter")),
        "collar_height_mm": float(_v("collar_height")),
        "bulb_height_mm": float(_v("bulb_height")),
        "collar_diameter_mm": float(_v("collar_diameter") or 0) or None,
        "neck_diameter_mm": float(_v("neck_diameter") or 0) or None,
        "visible_neck_mm": float(_v("visible_neck_height") or 0) or None,
        "bulb_width_mm": float(_v("bulb_width") or 0) or None,
        "base_thickness_mm": float(_v("base_thickness") or 0) or None,
        "shoulder_radius_mm": float(_v("shoulder_radius") or 0) or None,
        "frost_intensity": (float(_v("frost_intensity") or 70)) / 100.0,
        "translucency": (float(_v("glass_translucency") or 35)) / 100.0,
    }


def augment_dropper_zones(profile_record: dict, zones: list[dict]
                          ) -> list[dict]:
    """§8: the dropper zone proposal — front/back direct print + the
    technical bottom code zone. The OPTIONAL collar zone is EXCLUDED from
    the confirmable set (2C-2D-CORR-2 §8D, ``COLLAR_ZONE_EXCLUSION``): no
    confirmed collar dimensions exist, no artwork is required there, and
    the metallic collar material already provides the intended accent."""
    from apps.pipeline.services import container_contract as cc

    out = [z for z in zones if z.get("zone_type") != "NECK_BAND_ZONE"]
    have = {z.get("zone_type") for z in out}
    if "BOTTOM_CODE_ZONE" not in have:
        out.append(cc.bottom_code_zone(profile_record))      # §BH71 (0b): the one rule, shared with every form
    return out
