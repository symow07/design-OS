"""Curved-surface projection + decoration-zone containment (Phase 2B-2,
slice 3).

Deterministic geometry over the FROZEN 2B-1 contract (container_contract is
not modified). Two concerns:

* ``project_zone`` — map a confirmed flat decoration zone onto its surface's
  curvature (§7): FLAT 1:1; CYLINDRICAL flat-width→arc-length + seam;
  TAPERED_CYLINDRICAL trapezoid + reported distortion; OVAL bounded front/back
  only (full wrap fails); ROUNDED_RECT flat centre + bounded corners;
  CUSTOM_PROFILE / UNKNOWN fail closed with
  CONTAINER_SURFACE_PROJECTION_REVIEW_REQUIRED. Manufacturer-grade distortion
  compensation is never claimed without verified specs — distortion is
  reported, not silently corrected.

* ``validate_zone_containment`` — every emitted artwork placement must belong
  to a confirmed zone, sit within it (minus safe margin), respect the max
  coverage, and stay off excluded surfaces / the wrap seam / the cap-body
  divide (§6). Precise, stable codes; nothing is silently resized to pass.
"""
from __future__ import annotations

import math

from apps.pipeline.services import container_contract as cc
# bound by name, not reached through `cc.`, so this module's reads can be
# isolated from the contract's own (§AA WI-R)
from apps.pipeline.services.container_contract import zone_surface
# [his answer on the print area's safe margin, 2026-10-01, transcribed at f23b9e8] the note's head, kept where the verdict
# reads its production notes
from apps.ire.container_production_readiness import ZONE_SAFE_MARGIN_AS_PICTURED

# --- §6 containment codes ----------------------------------------------------
DECORATION_OUTSIDE_ZONE = "CONTAINER_DECORATION_OUTSIDE_ZONE"
ZONE_SAFE_MARGIN_VIOLATION = "CONTAINER_ZONE_SAFE_MARGIN_VIOLATION"
ARTWORK_SURFACE_MISMATCH = "CONTAINER_ARTWORK_SURFACE_MISMATCH"
WRAP_SEAM_CONFLICT = "CONTAINER_WRAP_SEAM_CONFLICT"
CAP_BODY_ZONE_CONFLICT = "CONTAINER_CAP_BODY_ZONE_CONFLICT"
DECORATION_COVERAGE_EXCEEDED = "CONTAINER_DECORATION_COVERAGE_EXCEEDED"

#: §7 projection review (reuse the 2B-1 refusal code)
SURFACE_PROJECTION_REVIEW_REQUIRED = cc.SURFACE_PROJECTION_REVIEW_REQUIRED

#: surfaces that must never carry decoration (exclusion zones)
_EXCLUDED_SURFACES = ("NECK", "SHOULDER", "CRIMP_ZONE")
_CAP_SURFACES = ("CAP_FRONT", "CAP_BACK", "CAP_TOP", "CAP_WRAP")


def _surface_family(surface: str | None) -> str:
    return "cap" if surface in _CAP_SURFACES else "body"


# --- §7 projection -----------------------------------------------------------

def project_zone(zone: dict, surface: dict) -> dict:
    """Project one flat zone onto its surface. Returns a bounded record:
    ``method``, ``flat`` (mm), ``projected`` (mm + wrap/taper metadata),
    ``distortion`` (reported, never silently compensated), and
    ``review_required`` (+ ``code``) when the curvature is not safely
    modellable."""
    curve = zone.get("curvature_type") or surface.get("curvature")
    w = float(zone.get("width") or 0.0)
    h = float(zone.get("height") or 0.0)
    flat = {"width_mm": round(w, 3), "height_mm": round(h, 3)}
    base = {"curvature_type": curve, "flat": flat}

    if curve == cc.FLAT:
        return {**base, "method": "direct_1_1",
                "projected": dict(flat), "distortion": 0.0,
                "review_required": False}

    if curve in (cc.CYLINDRICAL, cc.TAPERED_CYLINDRICAL):
        surf_w = float(surface.get("w") or 0.0)          # circumference (mm)
        radius = (zone.get("curvature_radius_mm")
                  or (surf_w / (2 * math.pi) if surf_w else 0.0))
        # sweep angle the flat width subtends on the cylinder
        arc_deg = round((w / (radius * 2 * math.pi)) * 360.0, 2) \
            if radius else 0.0
        projected = {"width_mm": round(w, 3), "height_mm": round(h, 3),
                     "wrap_radius_mm": round(radius, 3),
                     "wrap_arc_deg": arc_deg,
                     "note": "flat width is the printed arc length; seam "
                             "preserved at the zone edge"}
        # perceived horizontal foreshortening at the arc edges (reported)
        distortion = round(1.0 - math.cos(math.radians(min(arc_deg, 180) / 2)),
                           4) if arc_deg else 0.0
        if curve == cc.TAPERED_CYLINDRICAL:
            # bounded top/bottom circumference difference → trapezoid field
            taper = float(zone.get("taper_ratio") or 0.12)
            taper = max(0.0, min(0.4, taper))
            projected["top_width_mm"] = round(w * (1 - taper), 3)
            projected["bottom_width_mm"] = round(w, 3)
            projected["field_shape"] = "trapezoid"
            distortion = round(max(distortion, taper), 4)
        return {**base, "method": "cylindrical_arc", "projected": projected,
                "distortion": distortion, "review_required": False}

    if curve == cc.OVAL:
        # bounded FRONT/BACK panels only — a full oval wrap is not safely
        # modellable here; only a zone that stays on the flatter front/back
        # face is allowed
        surface_ok = zone_surface(zone) in ("BODY_FRONT", "BODY_BACK")
        if not surface_ok:
            return {**base, "method": "oval", "projected": None,
                    "distortion": None, "review_required": True,
                    "code": SURFACE_PROJECTION_REVIEW_REQUIRED,
                    "note": "oval full-wrap projection is not modelled; "
                            "confirm a front/back zone"}
        return {**base, "method": "oval_front_back",
                "projected": {"width_mm": round(w, 3),
                              "height_mm": round(h, 3),
                              "note": "front/back panel only; edges curve away"},
                "distortion": 0.08, "review_required": False}

    if curve == cc.ROUNDED_RECT:
        # flat central region maps 1:1; the corner band is reported bounded
        corner = round(min(w, h) * 0.12, 3)
        return {**base, "method": "rounded_rect",
                "projected": {"width_mm": round(w, 3), "height_mm": round(h, 3),
                              "flat_centre_inset_mm": corner,
                              "note": "central region is flat; keep artwork "
                                      "inside the corner inset"},
                "distortion": 0.03, "review_required": False}

    # CUSTOM_PROFILE / UNKNOWN / anything else → fail closed
    return {**base, "method": "unsupported", "projected": None,
            "distortion": None, "review_required": True,
            "code": SURFACE_PROJECTION_REVIEW_REQUIRED,
            "note": f"curvature {curve!r} is not safely modellable"}


def project_zones(zones: list[dict], profile_record: dict) -> dict:
    """Per-zone projection report + an overall review flag."""
    geom = cc.surface_geometry(profile_record)
    per_zone, review = [], False
    for z in zones or []:
        surface = geom.get(zone_surface(z), {})
        rec = project_zone(z, surface)
        rec["zone_id"] = z.get("zone_id")
        per_zone.append(rec)
        review = review or rec.get("review_required", False)
    return {"zones": per_zone, "review_required": review,
            "code": SURFACE_PROJECTION_REVIEW_REQUIRED if review else None}


# --- §6 containment ----------------------------------------------------------

def validate_zone_containment(placements: list[dict],
                              zones: list[dict],
                              profile_record: dict) -> list[str]:
    """Every emitted artwork placement must belong to a confirmed zone and sit
    within it. ``placements``: [{zone_id, kind, nx, ny, nw, nh}] in
    zone-normalised (0..1) coordinates. Returns stable §6 codes; [] when
    every placement is contained. Nothing is resized here — a violation is
    reported, never silently fixed."""
    problems: list[str] = []
    by_id = {z.get("zone_id"): z for z in (zones or [])}
    surfaces = set(cc.surfaces_for(profile_record.get("archetype", ""),
                                   profile_record.get("variant", "")))
    for pl in placements or []:
        zid = pl.get("zone_id")
        zone = by_id.get(zid)
        kind = pl.get("kind", "artwork")
        if zone is None:
            problems.append(f"{DECORATION_OUTSIDE_ZONE}: {kind} references "
                            f"unknown zone {zid!r}")
            continue
        surface = zone_surface(zone)
        if surface not in surfaces:
            problems.append(f"{ARTWORK_SURFACE_MISMATCH}: {kind} on {surface!r}")
        if surface in _EXCLUDED_SURFACES:
            problems.append(f"{ARTWORK_SURFACE_MISMATCH}: {kind} on the "
                            f"decoration-excluded surface {surface}")
        # cap/body: a placement's declared family must match its zone's surface
        want_family = pl.get("surface_family")
        if want_family and want_family != _surface_family(surface):
            problems.append(
                f"{CAP_BODY_ZONE_CONFLICT}: {kind} is {want_family} artwork "
                f"but zone {zid} is on a {_surface_family(surface)} surface")
        nx, ny = float(pl.get("nx", 0)), float(pl.get("ny", 0))
        nw, nh = float(pl.get("nw", 0)), float(pl.get("nh", 0))
        # bounds within the zone (0..1)
        if nx < -1e-6 or ny < -1e-6 or nx + nw > 1 + 1e-6 or ny + nh > 1 + 1e-6:
            problems.append(
                f"{DECORATION_OUTSIDE_ZONE}: {kind} ({nx:.2f},{ny:.2f},"
                f"{nw:.2f},{nh:.2f}) exceeds zone {zid}")
        # safe margin (mm) as a fraction of the zone
        zw = float(zone.get("width") or 0.0)
        zh = float(zone.get("height") or 0.0)
        margin = float(zone.get("safe_margin_mm") or 0.0)
        if zw and zh and kind != "field":
            mfx, mfy = margin / zw, margin / zh
            if (nx < mfx - 1e-6 or ny < mfy - 1e-6
                    or nx + nw > 1 - mfx + 1e-6 or ny + nh > 1 - mfy + 1e-6):
                if pl.get("as_pictured") is True:
                    # [his answer on the print area's safe margin, 2026-10-01: "The picture (Recommended)"] placed by a
                    # front drawn from its concept's measured layout where the picture prints it — a production note
                    problems.append(f"{ZONE_SAFE_MARGIN_AS_PICTURED}: {kind} sits inside the {margin}mm safe "
                                    f"margin of zone {zid}, where the concept picture prints it")
                else:
                    problems.append(f"{ZONE_SAFE_MARGIN_VIOLATION}: {kind} breaks "
                                    f"the {margin}mm safe margin of zone {zid}")
        # coverage
        cov_cap = zone.get("max_artwork_coverage")
        # [his go of 2026-10-08, item 1] line art and a frame print only their strokes: their coverage is the share of the
        # zone their ink covers (``ink_share``), never their box's
        covers = float(pl["ink_share"]) if pl.get("ink_share") is not None else nw * nh
        if cov_cap is not None and kind != "field" and covers > cov_cap + 1e-6:
            problems.append(
                f"{DECORATION_COVERAGE_EXCEEDED}: {kind} covers "
                f"{covers:.0%} of zone {zid} (cap {cov_cap:.0%})")
        # wrap seam: a placement that runs off a wrap edge conflicts with the seam
        if "WRAP" in (surface or "") and (nx < -1e-6 or nx + nw > 1 + 1e-6):
            problems.append(f"{WRAP_SEAM_CONFLICT}: {kind} crosses the wrap "
                            f"seam of zone {zid}")
    return problems


__all__ = [
    "project_zone", "project_zones", "validate_zone_containment",
    "DECORATION_OUTSIDE_ZONE", "ZONE_SAFE_MARGIN_VIOLATION", "ZONE_SAFE_MARGIN_AS_PICTURED",
    "ARTWORK_SURFACE_MISMATCH", "WRAP_SEAM_CONFLICT", "CAP_BODY_ZONE_CONFLICT",
    "DECORATION_COVERAGE_EXCEEDED", "SURFACE_PROJECTION_REVIEW_REQUIRED",
]
