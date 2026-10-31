"""Container production separations + swatch/spot contract (Phase 2B-3B,
§6-§8/§11-§14).

A CONTRACT/manifest over the emitted document + the derived production methods:
which named separations exist, their swatch/spot identity, visibility default,
target zones, and the deterministic technical geometry (white underbase, label
cut/bleed/safe, shrink-sleeve seam). It does NOT paint finish masks as visible
process artwork — separations are recorded as data with a visibility default
(§7); nothing opaque is drawn over the design. Spot values stay technical
placeholders until a manufacturer confirms them.

White underbase (§11) is keyed off the confirmed profile transparency, never
assumed: unknown/inferred transparency → REVIEW_REQUIRED, generated only when
transparency is confirmed. All hashing is deterministic (§14).
"""
from __future__ import annotations

import hashlib
import json

from apps.pipeline.services.container_contract import zone_surface

SCHEMA = "container_production_separations/1.0"

# process vs spot classification
PROCESS = "PROCESS"
SPOT = "SPOT"
TECHNICAL = "TECHNICAL"       # cut/bleed/safe/seam/notes — nonprinting guides

_CAP_SURFACES = ("CAP_FRONT", "CAP_BACK", "CAP_TOP", "CAP_WRAP")

#: method_type → (separation name, spot swatch name) for its ink/finish layers.
_METHOD_SEPARATIONS = {
    "SCREEN_PRINT": [("SCREEN_INK_1", "SCREEN_INK_1", SPOT),
                     ("SCREEN_INK_2", "SCREEN_INK_2", SPOT)],
    "PAD_PRINT": [("PAD_PRINT_INK_1", "PAD_PRINT_INK_1", SPOT)],
    "CAP_PRINT": [("PAD_PRINT_INK_1", "PAD_PRINT_INK_1", SPOT)],
    "HOT_STAMP": [("HOT_STAMP", "HOT_STAMP_FOIL", SPOT)],
    "CAP_HOT_STAMP": [("CAP_HOT_STAMP", "CAP_FOIL", SPOT)],
    "EMBOSS": [("EMBOSS", "EMBOSS", SPOT)],
    "DEBOSS": [("DEBOSS", "DEBOSS", SPOT)],
    "ADHESIVE_LABEL": [],
    "WRAP_LABEL": [],
    "SHRINK_SLEEVE": [],
    "BOTTOM_INKJET_CODE": [("BOTTOM_CODE", "BOTTOM_CODE", SPOT)],
    "DIGITAL_PRINT": [],
}


def _canonical(p) -> str:
    return json.dumps(p, sort_keys=True, separators=(",", ":"), default=str)


def _hash(p) -> str:
    return hashlib.sha256(_canonical(p).encode()).hexdigest()[:32]


def _sep(sep_id, name, method_id, zones, surfaces, *, swatch, classification,
         visible, overprint="REVIEW_REQUIRED", printable=True,
         geometry=None, notes="") -> dict:
    rec = {
        "separation_id": sep_id, "name": name, "method_id": method_id,
        "target_zone_ids": list(zones), "target_surfaces": list(surfaces),
        "swatch": swatch, "classification": classification,
        "overprint": overprint, "printable": printable,
        "visibility_default": "visible" if visible else "hidden",
        "geometry": geometry or {}, "notes": notes,
    }
    rec["separation_hash"] = _hash({k: rec[k] for k in (
        "name", "method_id", "target_zone_ids", "target_surfaces", "swatch",
        "classification", "overprint", "visibility_default")})
    return rec


def _label_geometry(zone: dict) -> dict:
    """LABEL_CUT/BLEED/SAFE rects around a confirmed label zone (§12), in mm.
    NOT a confirmed production cutline — a technical proposal pending review."""
    w = float(zone.get("width") or 0.0)
    h = float(zone.get("height") or 0.0)
    bleed, safe, radius = 3.0, 3.0, 2.0
    return {"cut": {"w": round(w, 2), "h": round(h, 2), "corner_radius_mm": radius},
            "bleed": {"w": round(w + 2 * bleed, 2), "h": round(h + 2 * bleed, 2),
                      "bleed_mm": bleed},
            "safe": {"w": round(max(0.0, w - 2 * safe), 2),
                     "h": round(max(0.0, h - 2 * safe), 2), "safe_mm": safe},
            "confirmed_cutline": False}


def _sleeve_geometry(zone: dict) -> dict:
    """Shrink-sleeve seam + exclusion bands (§13). Distortion is flagged for
    manufacturer review — never a production-ready compensation claim."""
    w = float(zone.get("width") or 0.0)
    h = float(zone.get("height") or 0.0)
    band = round(h * 0.08, 2)
    return {"projected_width_mm": round(w, 2), "projected_height_mm": round(h, 2),
            "seam_position": "trailing_edge", "seam_safe_mm": 4.0,
            "top_exclusion_mm": band, "bottom_exclusion_mm": band,
            "distortion_review": "CONTAINER_PROJECTION_DISTORTION_REVIEW_REQUIRED"}


def _transparency_state(profile_record: dict) -> str:
    fields = profile_record.get("fields") or {}
    t = fields.get("body_transparency") or {}
    val = str(t.get("value") or "").lower()
    verified = t.get("verification") == "VERIFIED"
    if verified and val in ("transparent", "translucent", "clear"):
        return "CONFIRMED_TRANSPARENT"
    if verified and val in ("opaque",):
        return "CONFIRMED_OPAQUE"
    return "UNKNOWN"


def build_separations(methods_record: dict, doc, zones: list[dict],
                      profile_record: dict) -> dict:
    """container_production_separations/1.0 for the emitted document."""
    by_id = {z.get("zone_id"): z for z in (zones or [])}
    separations = []
    swatches: dict[str, dict] = {}

    def _register_swatch(name, classification, overprint="REVIEW_REQUIRED"):
        if name in swatches:
            return
        swatches[name] = {
            "name": name, "classification": classification,
            "value": "TECHNICAL_PLACEHOLDER" if classification == SPOT else "CMYK",
            "overprint": overprint,
            "manufacturer_review": classification == SPOT}

    # PROCESS_ARTWORK — the visible printed design (name + motif + field)
    printed_surfaces = sorted({m for rec in (methods_record.get("methods") or [])
                               for m in (rec.get("target_surfaces") or [])})
    separations.append(_sep(
        "sep_process", "PROCESS_ARTWORK", "", [z.get("zone_id") for z in zones],
        printed_surfaces, swatch="PROCESS_CMYK", classification=PROCESS,
        visible=True, overprint="knockout"))
    _register_swatch("PROCESS_CMYK", PROCESS, overprint="knockout")

    # per-method ink / finish separations (hidden spot layers, §7)
    for rec in (methods_record.get("methods") or []):
        mtype = rec.get("method_type")
        zids = rec.get("target_zone_ids") or []
        surfs = rec.get("target_surfaces") or []
        for name, swatch, cls in _METHOD_SEPARATIONS.get(mtype, []):
            sid = f"sep_{name.lower()}_{rec.get('method_id')}"
            separations.append(_sep(sid, name, rec.get("method_id"), zids,
                                    surfs, swatch=swatch, classification=cls,
                                    visible=False))
            _register_swatch(swatch, cls)
        # label technical geometry (§12)
        if mtype in ("ADHESIVE_LABEL", "WRAP_LABEL"):
            zone = by_id.get(zids[0]) if zids else None
            geo = _label_geometry(zone) if zone else {}
            for tech in ("LABEL_CUT", "LABEL_BLEED", "LABEL_SAFE"):
                separations.append(_sep(
                    f"sep_{tech.lower()}_{rec.get('method_id')}", tech,
                    rec.get("method_id"), zids, surfs, swatch=tech,
                    classification=TECHNICAL, visible=False, printable=False,
                    geometry=geo, notes="technical proposal, not a confirmed cutline"))
                _register_swatch(tech, TECHNICAL, overprint="none")
        # shrink-sleeve technical geometry (§13)
        if mtype == "SHRINK_SLEEVE":
            zone = by_id.get(zids[0]) if zids else None
            geo = _sleeve_geometry(zone) if zone else {}
            for tech in ("SHRINK_SLEEVE_SEAM", "SHRINK_SLEEVE_SAFE"):
                separations.append(_sep(
                    f"sep_{tech.lower()}_{rec.get('method_id')}", tech,
                    rec.get("method_id"), zids, surfs, swatch=tech,
                    classification=TECHNICAL, visible=False, printable=False,
                    geometry=geo))
                _register_swatch(tech, TECHNICAL, overprint="none")

    # white underbase (§11) — keyed off CONFIRMED transparency, never assumed
    transparency = _transparency_state(profile_record)
    needs_ub = any((rec.get("white_underbase_requirement") == "conditional")
                   for rec in (methods_record.get("methods") or []))
    underbase = {"state": "NOT_APPLICABLE"}
    if needs_ub:
        if transparency == "CONFIRMED_TRANSPARENT":
            body_zones = [z.get("zone_id") for z in zones
                          if zone_surface(z) not in _CAP_SURFACES]
            separations.append(_sep(
                "sep_white_underbase", "WHITE_UNDERBASE", "", body_zones,
                printed_surfaces, swatch="WHITE_UNDERBASE", classification=SPOT,
                visible=False, overprint="knockout",
                notes="follows printed artwork bounds; choke pending manufacturer"))
            _register_swatch("WHITE_UNDERBASE", SPOT)
            underbase = {"state": "GENERATED", "separation": "WHITE_UNDERBASE",
                         "choke_spread_mm": "REVIEW_REQUIRED"}
        else:
            underbase = {"state": "REVIEW_REQUIRED",
                         "reason": "container transparency is not confirmed",
                         "code": "CONTAINER_WHITE_UNDERBASE_REQUIRED"}

    record = {
        "schema_version": SCHEMA,
        "separations": separations,
        "swatches": list(swatches.values()),
        "duplicate_swatch_names": [],       # by construction (dict-keyed)
        "white_underbase": underbase,
        "transparency_state": transparency,
    }
    record["separation_set_hash"] = _hash(sorted(
        s["separation_hash"] for s in separations))
    return record


def combined_production_hash(methods_record: dict,
                             separations_record: dict) -> str:
    """§14 combined method + separation confirmation identity — a change to any
    method or separation invalidates it (timestamps excluded)."""
    return _hash({"methods": methods_record.get("method_set_hash"),
                  "separations": separations_record.get("separation_set_hash")})


__all__ = [
    "SCHEMA", "PROCESS", "SPOT", "TECHNICAL", "build_separations",
    "combined_production_hash",
]
