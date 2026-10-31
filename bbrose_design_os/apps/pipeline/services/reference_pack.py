"""RBV-1 — real bottle reference pack intake and capture validation.

``real_bottle_reference_pack/1.0`` intake: validates a declared pack
against the owner-approved standard, reports EXACTLY what is missing
(``REAL_BOTTLE_REFERENCE_INCOMPLETE`` — hidden geometry is never
fabricated), and records ``real_bottle_capture_protocol/1.0`` compliance
per photograph. Deterministic and local: PIL/EXIF facts are measured;
studio conditions that cannot be measured from pixels are DECLARED by the
owner and recorded as declarations, never silently assumed.
"""
from __future__ import annotations

from PIL import Image

SCHEMA = "real_bottle_reference_pack/1.0"
CAPTURE_SCHEMA = "real_bottle_capture_protocol/1.0"

COMPLETE = "REAL_BOTTLE_REFERENCE_COMPLETE"
INCOMPLETE = "REAL_BOTTLE_REFERENCE_INCOMPLETE"

# §6 pack items: (key, class, required)
PACK_ITEMS = (
    ("cad_or_technical_drawing", "GEOMETRY_AUTHORITY", True),
    ("overall_height_mm", "DIMENSION", True),
    ("body_width_mm", "DIMENSION", True),
    ("body_depth_mm", "DIMENSION", True),
    ("neck_diameter_mm", "DIMENSION", True),
    ("collar_dimensions_mm", "DIMENSION", True),
    ("bulb_dimensions_mm", "DIMENSION", True),
    ("front_photo", "CALIBRATED_PHOTO", True),
    ("side_photo", "CALIBRATED_PHOTO", True),
    ("top_photo", "PHOTO", True),
    ("three_quarter_photo", "PHOTO", True),
    ("closure_closeup", "PHOTO", True),
    ("neck_collar_closeup", "PHOTO", True),
    ("material_reference", "APPEARANCE", True),
    ("finish_reference", "APPEARANCE", True),
    ("colour_reference", "APPEARANCE", True),
    ("provenance", "PROVENANCE", True),
    ("owner_authorization", "PROVENANCE", True),
)

# §5 capture conditions — DECLARED by the capturer, recorded verbatim
CAPTURE_DECLARATIONS = (
    "camera_level_with_product_centre", "tripod_or_stable_support",
    "product_upright", "orientation_recorded", "neutral_background",
    "diffuse_lighting", "no_portrait_mode", "no_beauty_filter",
    "no_digital_background_removal", "no_wide_angle_lens",
    "long_distance_or_telephoto", "calibration_card_coplanar",
    "grey_or_white_balance_card", "uncropped_original_preserved",
)


def _photo_facts(path: str) -> dict:
    """Measurable local facts only — never a judgment of studio quality."""
    try:
        img = Image.open(path)
    except Exception:
        return {"readable": False}
    exif = img.getexif()
    return {"readable": True, "width_px": img.width,
            "height_px": img.height, "mode": img.mode,
            "exif_present": bool(len(exif)),
            "exif_preserved": bool(len(exif))}


def validate_reference_pack(manifest: dict) -> dict:
    """Intake validation for one declared pack.

    ``manifest`` maps item keys to entries: dimensions carry ``value``;
    photos carry ``path`` (local, already governance-cleared) plus a
    ``declarations`` dict of §5 capture conditions; provenance carries
    text. Missing keys are reported exactly; nothing is inferred.
    """
    items = {}
    missing = []
    uncertainty = []
    for key, klass, required in PACK_ITEMS:
        entry = manifest.get(key)
        if not entry:
            items[key] = {"class": klass, "present": False}
            if required:
                missing.append(key)
            continue
        record = {"class": klass, "present": True}
        if klass == "DIMENSION":
            record["value"] = entry.get("value")
            record["source"] = entry.get("source", "OWNER_DECLARED")
            if entry.get("value") in (None, ""):
                record["present"] = False
                missing.append(key)
        elif klass in ("CALIBRATED_PHOTO", "PHOTO"):
            facts = _photo_facts(entry["path"]) if entry.get("path") \
                else {"readable": False}
            record["measured"] = facts
            declared = {d: bool((entry.get("declarations") or {}).get(d))
                        for d in CAPTURE_DECLARATIONS}
            record["capture_declarations"] = declared
            unmet = [d for d, ok in declared.items() if not ok]
            if unmet:
                uncertainty.append(
                    {"item": key, "unmet_capture_conditions": unmet})
            if not facts.get("readable"):
                record["present"] = False
                missing.append(key)
            elif not facts.get("exif_present"):
                uncertainty.append({"item": key,
                                    "note": "EXIF absent — provenance of "
                                            "capture unverifiable"})
        else:
            record["value"] = entry.get("value") or entry.get("text")
            if not record["value"]:
                record["present"] = False
                missing.append(key)
        items[key] = record

    status = COMPLETE if not missing else INCOMPLETE
    return {
        "schema": SCHEMA,
        "capture_protocol": CAPTURE_SCHEMA,
        "status": status,
        "items": items,
        "missing_evidence": missing,
        "uncertainty": uncertainty,
        "fabrication_policy": "hidden or unavailable geometry is never "
                              "fabricated — missing items stay missing",
    }


def pilot_intake_state(manifest: dict | None = None) -> dict:
    """The current pilot pack state. With no owner submission the record
    lists every required item as missing — the exact §6 shopping list."""
    record = validate_reference_pack(manifest or {})
    record["pilot"] = "real BBROSE Bottle + Dropper (owner-selected)"
    record["synthetic_fixture_rule"] = ("a synthetic fixture can never be "
                                        "the pilot")
    return record
