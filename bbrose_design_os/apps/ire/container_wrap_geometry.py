"""True seam-aware wrap production geometry (Phase 2B-3C, §7-§10).

A production-geometry DATA record (radius / circumference / seam / arc-mapping /
anchors / exclusions), NOT a re-emission of the concept sheet — §7 is explicit
that the concept-sheet panel is not the production wrap file. Builds on
``container_projection.project_zone`` and adds the seam, anchors, exclusions,
text-safe regions and a deterministic projection hash, plus §10 alignment
measurement. Manufacturer-grade distortion compensation is never claimed
without verified tolerances → CONTAINER_PROJECTION_DISTORTION_REVIEW_REQUIRED.
"""
from __future__ import annotations

import hashlib
import json

from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import container_projection as cp
# bound by name, not reached through `cc.`, so this module's reads can be
# isolated from the contract's own (§AA WI-R: a read site proven to refuse
# only because something upstream refused first has not been proven at all)
from apps.pipeline.services.container_contract import zone_surface

SCHEMA = "container_wrap_geometry/1.0"

# --- §10 alignment codes -----------------------------------------------------
WRAP_ALIGNMENT_FAILED = "CONTAINER_WRAP_ALIGNMENT_FAILED"
WRAP_SEAM_CONFLICT = "CONTAINER_WRAP_SEAM_CONFLICT"
TEXT_CROSSES_SEAM = "CONTAINER_TEXT_CROSSES_SEAM"
WRAP_REGISTRATION_FAILED = "CONTAINER_WRAP_REGISTRATION_FAILED"
PROJECTION_DISTORTION_REVIEW_REQUIRED = "CONTAINER_PROJECTION_DISTORTION_REVIEW_REQUIRED"
SURFACE_PROJECTION_REVIEW_REQUIRED = cc.SURFACE_PROJECTION_REVIEW_REQUIRED

# §BH50(f)(6), OWNER RULED 2026-09-13: WRAP ALIGNMENT does not apply to a
# surface with no wrap — scoped to wrapped surfaces, placed and not retired. A
# wrapped surface is one whose width the contract develops by π
# (container_contract.surface_geometry: BODY_WRAP, CAP_WRAP) — the only
# surfaces with a seam. A projected face (BODY_FRONT and the others) carries
# its bare width and no seam, so the seam check has nothing to place itself on
# there; before this ruling it fired on task 52's BODY_FRONT off the
# composer's hand-set placement record (nx 0.15 / nw 0.70 against 4/22).
WRAPPED_SURFACES = ("BODY_WRAP", "CAP_WRAP")
#: a confirmed zone whose TYPE or TECHNIQUE names a wrap is wrapped whatever
#: surface it sits on (the confirm endpoint does not check the one against the
#: other) — this guard only ever makes the rule apply, never the reverse
_WRAP_ZONE_TYPES = ("WRAP_LABEL_ZONE", "SHRINK_SLEEVE_ZONE")
_WRAP_TECHNIQUES = ("wrap_label", "shrink_sleeve")
#: the zones that carry a PROJECTION record (radius, arc, distortion, review):
#: every curved or flat body face as well as the wraps. CAP_WRAP joined at
#: §BH50(f)(6): a confirmed cap wrap is a wrapped surface, and calling it
#: wrapped without building its record would issue APPLICABLE over nothing
#: evaluated. No proposer emits one, so no recorded wrap_set_hash moves.
_PROJECTED_SURFACES = ("BODY_WRAP", "CAP_WRAP", "BODY_FRONT", "BODY_BACK",
                       "BODY_LEFT", "BODY_RIGHT")
_SEAM_SAFE_MM = 4.0

# --- §BH50(f)(6) seam-check applicability: EVALUATION states, local to this
# record (the contract's NOT_APPLICABLE of the same spelling is a §2
# verification state of a profile field, a different field of a different
# record; importing it here would merge the two) --------------------------
APPLICABLE = "APPLICABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"
UNMEASURED = "UNMEASURED"


def _canonical(p) -> str:
    return json.dumps(p, sort_keys=True, separators=(",", ":"), default=str)


def _hash(p) -> str:
    return hashlib.sha256(_canonical(p).encode()).hexdigest()[:32]


def _wrap_record(zone: dict, surface: dict) -> dict:
    """Production geometry for one wrap-capable zone."""
    proj = cp.project_zone(zone, surface)
    curve = proj.get("curvature_type")
    w = float(zone.get("width") or 0.0)
    h = float(zone.get("height") or 0.0)
    rec = {
        "zone_id": zone.get("zone_id"),
        # the record's own `surface` key, read through the contract's accessor
        # (§AA WI-R): the two spellings live one line apart here and this is
        # the file that made it look like they were the same field.
        "surface": zone_surface(zone),
        # §BH50(f)(6): whether this zone's surface carries a seam at all. Not a
        # projection_hash input, so every recorded hash keeps its value.
        "wrapped": is_wrapped_zone(zone) is True,
        "curvature_type": curve,
        "method": proj.get("method"),
        "usable_width_mm": round(w, 2),
        "usable_height_mm": round(h, 2),
        "seam_position": "trailing_edge",
        "seam_safe_mm": _SEAM_SAFE_MM,
        "front_anchor": "arc_0deg",
        "back_anchor": "arc_180deg",
        "wrap_direction": "left_to_right",
        "registration_tolerance_mm": zone.get("registration_tolerance_mm"),
        "distortion": proj.get("distortion"),
        "review_required": proj.get("review_required", False),
        "text_safe_x_fraction": [round(_SEAM_SAFE_MM / w, 4) if w else 0.0,
                                 round(1 - (_SEAM_SAFE_MM / w if w else 0.0), 4)],
    }
    if curve in (cc.CYLINDRICAL, cc.TAPERED_CYLINDRICAL):
        pj = proj.get("projected") or {}
        circ = round(float(surface.get("w") or 0.0), 2)
        zx = float(zone.get("x") or 0.0)
        rec["radius_mm"] = pj.get("wrap_radius_mm")
        rec["circumference_mm"] = circ
        rec["arc_deg"] = pj.get("wrap_arc_deg")
        # §7 flat x → angular arc mapping (start / centre / end)
        rec["arc_mapping"] = {
            "artwork_start_deg": _arc_position(zx, circ),
            "artwork_centre_deg": _arc_position(zx + w / 2.0, circ),
            "artwork_end_deg": _arc_position(zx + w, circ),
            "seam_deg": 0.0}
        if curve == cc.TAPERED_CYLINDRICAL:
            rec["top_width_mm"] = pj.get("top_width_mm")
            rec["bottom_width_mm"] = pj.get("bottom_width_mm")
            rec["field_shape"] = pj.get("field_shape")
            rec["top_exclusion_mm"] = round(h * 0.08, 2)
            rec["bottom_exclusion_mm"] = round(h * 0.08, 2)
            rec["distortion_review"] = PROJECTION_DISTORTION_REVIEW_REQUIRED
    elif curve == cc.ROUNDED_RECT:
        pj = proj.get("projected") or {}
        rec["flat_centre_inset_mm"] = pj.get("flat_centre_inset_mm")
        rec["corner_transition"] = "bounded"
    elif curve == cc.OVAL:
        rec["projection_note"] = (proj.get("note") or "front/back panel only")
    if proj.get("review_required"):
        rec["review_code"] = proj.get("code", SURFACE_PROJECTION_REVIEW_REQUIRED)
    rec["projection_hash"] = _hash({k: rec.get(k) for k in (
        "zone_id", "surface", "curvature_type", "method", "usable_width_mm",
        "usable_height_mm", "seam_position", "seam_safe_mm", "radius_mm",
        "circumference_mm", "arc_deg")})
    return rec


def build_wrap_geometry(zones: list[dict], profile_record: dict) -> dict:
    """container_wrap_geometry/1.0 for every wrap-capable confirmed zone."""
    geom = cc.surface_geometry(profile_record)
    records, review = [], False
    for z in zones or []:
        if zone_surface(z) not in _PROJECTED_SURFACES:
            continue
        surface = geom.get(zone_surface(z), {})
        rec = _wrap_record(z, surface)
        records.append(rec)
        review = review or rec.get("review_required", False)
    out = {"schema_version": SCHEMA, "wraps": records,
           "review_required": review,
           # §BH50(f)(6): the zones the seam check evaluates — none on a
           # product whose every zone is a projected face
           "wrapped_zone_ids": [r["zone_id"] for r in records if r["wrapped"]]}
    out["wrap_set_hash"] = _hash(sorted(r["projection_hash"] for r in records))
    return out


def is_wrapped_zone(zone: dict):
    """§BH50(f)(6): True for a zone on a wrapped surface, or a zone whose
    confirmed type or technique names a wrap on any surface; False for a
    projected face; None when the surface is unresolved — absent, or outside
    the contract's vocabulary. Read through this module's own binding of
    ``zone_surface`` (WI-R), so the alias spelling still raises here."""
    surface = zone_surface(zone)
    if surface not in cc.SURFACES:
        return None
    if surface in WRAPPED_SURFACES:
        return True
    if zone.get("zone_type") in _WRAP_ZONE_TYPES or any(
            t in _WRAP_TECHNIQUES for t in (zone.get("permitted_techniques") or [])):
        return True
    return False


def _not_applicable(reason: str, **fields) -> dict:
    """The one verdict that could turn a blocking gap into a pass quietly, so
    it is built here and nowhere else, and it refuses to exist without a
    reason (the rbv5 idiom: NA must carry its justification)."""
    if not reason:
        raise ValueError("NOT_APPLICABLE without a reason is not a verdict")
    return {"state": NOT_APPLICABLE, "reason": reason, **fields}


def seam_applicability(zones) -> dict:
    """Where the seam check places itself — read from the ZONE RECORD (the
    surface each zone sits on, and what it is confirmed as), never from the
    page. Applicability is never decided by absence: an empty or missing zone
    set, or a zone whose surface does not resolve, is UNMEASURED with the
    zone named, not NOT_APPLICABLE."""
    per_zone: list[dict] = []
    if not zones:
        return {"state": UNMEASURED,
                "reason": "no zone record: the seam check has no surface to "
                          "place itself on",
                "wrapped_zone_ids": [], "per_zone": per_zone}
    unresolved: list[str] = []
    for z in zones:
        surface = zone_surface(z)          # the alias spelling raises (WI-R)
        wrapped = is_wrapped_zone(z)
        per_zone.append({"zone_id": z.get("zone_id"), "surface": surface,
                         "wrapped": wrapped,
                         "confirmation": z.get("user_confirmation_state")})
        if wrapped is None:
            unresolved.append(f"{z.get('zone_id')} on {surface!r}")
    if unresolved:
        return {"state": UNMEASURED,
                "reason": "a zone's surface is unresolved: "
                          + ", ".join(unresolved)
                          + " — applicability is never decided by absence",
                "wrapped_zone_ids": [], "per_zone": per_zone}
    wrapped_ids = [p["zone_id"] for p in per_zone if p["wrapped"]]
    if wrapped_ids:
        named = ", ".join(f"{p['zone_id']} on {p['surface']}"
                          for p in per_zone if p["wrapped"])
        return {"state": APPLICABLE,
                "reason": f"wrapped surface on record: {named}",
                "wrapped_zone_ids": wrapped_ids, "per_zone": per_zone}
    faces = "; ".join(
        f"{p['zone_id']} on {p['surface']} ({p['confirmation'] or 'unconfirmed'})"
        for p in per_zone)
    return _not_applicable(
        f"no wrapped surface in the zone set — {faces}; the seam rule places "
        f"itself on {' and '.join(WRAPPED_SURFACES)}, the surfaces the "
        f"contract develops by π",
        wrapped_zone_ids=[], per_zone=per_zone)


def validate_wrap_alignment(wrap_geometry: dict, doc, zones: list[dict]) -> dict:
    """§10 alignment measurement over the emitted placements vs the wrap
    geometry: text/marks in the seam-safe band, unresolved distortion, etc.
    Production-readiness codes (never reconstruction blockers).

    §BH50(f)(6): the SEAM family (TEXT_CROSSES_SEAM, WRAP_SEAM_CONFLICT, and
    the reserved WRAP_ALIGNMENT_FAILED / WRAP_REGISTRATION_FAILED when they
    gain producers) is evaluated on WRAPPED zones only, decided by
    ``seam_applicability`` from the zone record. On a zone set with no wrapped
    surface the record reads ``seam_check`` NOT_APPLICABLE with its reason —
    never PASS (``aligned`` is None), never silence. A wrapped record with no
    seam band on it is UNMEASURED, never the old ``[0.0, 1.0]`` default. The
    projection and distortion reviews keep firing on every curved zone: a
    tapered face distorts whether or not it wraps, and that rule describes
    the product. Before this ruling ``zones`` was received and never read, and
    an empty zone set returned ``aligned`` True over nothing."""
    seam = seam_applicability(zones)
    codes: list[str] = []
    wraps = {w["zone_id"]: w for w in wrap_geometry.get("wraps") or []}
    wrapped_ids = set(seam.get("wrapped_zone_ids") or [])
    unread: list[str] = []
    for zid in sorted(wrapped_ids):
        w = wraps.get(zid)
        if not w or not w.get("usable_width_mm") or not w.get("text_safe_x_fraction"):
            unread.append(f"{zid}: no seam band on record")
    readable = {zid for zid in wrapped_ids
                if not any(u.startswith(f"{zid}:") for u in unread)}
    placements = (doc.metadata or {}).get("placements") or []
    for pl in placements:
        zid = pl.get("zone_id")
        w = wraps.get(zid)
        if not w or zid not in readable:
            continue
        lo, hi = w["text_safe_x_fraction"]
        nx = float(pl.get("nx", 0))
        nw = float(pl.get("nw", 0))
        kind = pl.get("kind")
        # a text/motif/divider mark that runs into the seam-safe band
        # conflicts (§10). "divider" is here because §BB4 relabelled the front
        # rule off "motif"; dropping it from this tuple would have retired a
        # geometric check on an object that did not move.
        if kind in ("product_name", "motif", "divider") and (
                nx < lo - 1e-6 or nx + nw > hi + 1e-6):
            code = (TEXT_CROSSES_SEAM if kind == "product_name"
                    else WRAP_SEAM_CONFLICT)
            codes.append(code)
    # unresolved tapered/oval/custom distortion → review, on every curved zone
    for w in wrap_geometry.get("wraps") or []:
        if w.get("review_required"):
            codes.append(w.get("review_code", SURFACE_PROJECTION_REVIEW_REQUIRED))
        elif w.get("distortion_review"):
            codes.append(PROJECTION_DISTORTION_REVIEW_REQUIRED)
    # de-dup, stable
    seen, ordered = set(), []
    for c in codes:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    if seam["state"] == APPLICABLE and unread:
        seam = {**seam, "state": UNMEASURED,
                "reason": "; ".join(unread) + " — a wrapped record without a "
                          "seam band is not read as aligned"}
    aligned = None
    if seam["state"] == APPLICABLE:
        aligned = not any(
            c in ordered for c in (WRAP_ALIGNMENT_FAILED, WRAP_SEAM_CONFLICT,
                                   TEXT_CROSSES_SEAM, WRAP_REGISTRATION_FAILED))
    return {"codes": ordered, "aligned": aligned, "seam_check": seam}


def _arc_position(x_mm: float, circumference_mm: float) -> float:
    """Flat x → angular position (deg) on the cylinder (§7 mapping)."""
    if not circumference_mm:
        return 0.0
    return round((x_mm / circumference_mm) * 360.0 % 360.0, 2)


__all__ = [
    "SCHEMA", "build_wrap_geometry", "validate_wrap_alignment",
    "WRAP_ALIGNMENT_FAILED", "WRAP_SEAM_CONFLICT", "TEXT_CROSSES_SEAM",
    "WRAP_REGISTRATION_FAILED", "PROJECTION_DISTORTION_REVIEW_REQUIRED",
    "SURFACE_PROJECTION_REVIEW_REQUIRED",
    # §BH50(f)(6)
    "WRAPPED_SURFACES", "is_wrapped_zone", "seam_applicability",
    "APPLICABLE", "NOT_APPLICABLE", "UNMEASURED",
]
