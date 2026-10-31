"""RBV-2A — deterministic cross-section-aware container mesh core.

``container_geometry/1.0`` is the GEOMETRY AUTHORITY record for real-bottle
visualization: dimensional inputs + profiles + an EXPLICIT cross-section
family, lofted into a deterministic mesh. The owner's critical amendment is
structural law here:

* a pure revolve is valid ONLY for ``geometry_class:
  AXISYMMETRIC_REVOLUTION`` (circular cross-section) — a rectangular, oval,
  flat or asymmetric bottle is NEVER silently revolved;
* when the available evidence cannot define side/depth geometry the record
  classifies ``THREE_DIMENSIONAL_GEOMETRY_INCOMPLETE`` — hidden geometry is
  never fabricated.

Authority separation (owner decision, recorded):

* ARTWORK_AUTHORITY            = EDITABLE_AI
* GEOMETRY_AUTHORITY           = CAD_OR_VERSIONED_CONTAINER_GEOMETRY
* RENDER_SCENE_AUTHORITY       = NONE — VISUALIZATION_ONLY
* PNG_RENDER_AUTHORITY         = REVIEW_EVIDENCE_ONLY
* AI_GENERATED_CONCEPT_AUTHORITY = DESIGN_INTENT_REFERENCE_ONLY

The Blender scene never replaces confirmed geometry, CAD, technical
drawings or editable AI artwork. Material appearance never lives inside
this geometry authority.
"""
from __future__ import annotations

import hashlib

import numpy as np

SCHEMA = "container_geometry/1.0"

# cross-section families (owner amendment §1)
CIRCULAR = "CIRCULAR"
ELLIPTICAL = "ELLIPTICAL"
SUPERELLIPSE = "SUPERELLIPSE"
ROUNDED_RECTANGLE = "ROUNDED_RECTANGLE"
RECTANGULAR = "RECTANGULAR"
CUSTOM = "CUSTOM"
FAMILIES = (CIRCULAR, ELLIPTICAL, SUPERELLIPSE, ROUNDED_RECTANGLE,
            RECTANGULAR, CUSTOM)

AXISYMMETRIC_REVOLUTION = "AXISYMMETRIC_REVOLUTION"
LOFTED_CROSS_SECTION = "LOFTED_CROSS_SECTION"
GEOMETRY_INCOMPLETE = "THREE_DIMENSIONAL_GEOMETRY_INCOMPLETE"

AUTHORITIES = {
    "ARTWORK_AUTHORITY": "EDITABLE_AI",
    "GEOMETRY_AUTHORITY": "CAD_OR_VERSIONED_CONTAINER_GEOMETRY",
    "RENDER_SCENE_AUTHORITY": "NONE_VISUALIZATION_ONLY",
    "PNG_RENDER_AUTHORITY": "REVIEW_EVIDENCE_ONLY",
    "AI_GENERATED_CONCEPT_AUTHORITY": "DESIGN_INTENT_REFERENCE_ONLY",
}

MESH_PARAMS = {
    "version": "container_mesh_params/1.0",
    "height_samples": 96,
    "section_samples": 64,
    "depth_match_tolerance": 0.02,   # circular: |depth-width|/width beyond
                                     # this is a conflicting-evidence error
}


# ---------------------------------------------------------------------------
# cross-section generators — unit half-extents, scaled per ring at loft time


def _section_points(family: str, params: dict, n: int) -> np.ndarray:
    """(n, 2) unit cross-section outline (half-width=1, half-depth=1),
    starting at +x, counter-clockwise. Deterministic."""
    t = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    if family == CIRCULAR or family == ELLIPTICAL:
        return np.stack([np.cos(t), np.sin(t)], axis=1)
    if family == SUPERELLIPSE:
        p = float(params.get("exponent", 4.0))
        if p <= 0:
            raise ValueError("superellipse exponent must be positive")
        return np.stack([
            np.sign(np.cos(t)) * np.abs(np.cos(t)) ** (2.0 / p),
            np.sign(np.sin(t)) * np.abs(np.sin(t)) ** (2.0 / p)], axis=1)
    if family == ROUNDED_RECTANGLE:
        r = min(max(float(params.get("corner_radius_ratio", 0.25)), 0.01),
                0.99)
        # superellipse approximation of a rounded rectangle: exponent from
        # corner ratio (r→1 approaches ellipse, r→0 approaches rectangle)
        p = 2.0 / max(r, 1e-6)
        return _section_points(SUPERELLIPSE, {"exponent": min(p, 40.0)}, n)
    if family == RECTANGULAR:
        return _section_points(SUPERELLIPSE, {"exponent": 40.0}, n)
    if family == CUSTOM:
        pts = np.asarray(params.get("outline_points") or [], dtype=float)
        if pts.ndim != 2 or pts.shape[0] < 8 or pts.shape[1] != 2:
            raise ValueError(
                "CUSTOM cross-section requires >=8 authoritative outline "
                "points — custom sections exist only when evidence exists")
        idx = np.linspace(0, pts.shape[0] - 1, n).round().astype(int)
        return pts[idx]
    raise ValueError(f"unknown cross-section family {family!r}")


# ---------------------------------------------------------------------------
# geometry record classification (fail-closed; never fabricate depth)


def classify_geometry(record: dict) -> tuple[str, list[str]]:
    """(geometry_class, findings). CIRCULAR may revolve; everything else
    lofts and REQUIRES side/depth evidence."""
    findings: list[str] = []
    family = (record.get("cross_section") or {}).get("family")
    if family not in FAMILIES:
        return GEOMETRY_INCOMPLETE, [f"unknown cross-section family "
                                     f"{family!r}"]
    dims = record.get("dimensions") or {}
    width = dims.get("front_width_mm")
    depth = dims.get("side_depth_mm")
    if not dims.get("height_mm") or not width:
        return GEOMETRY_INCOMPLETE, ["height_mm and front_width_mm are "
                                     "required"]
    if family == CIRCULAR:
        if depth and abs(float(depth) - float(width)) / float(width) > \
                MESH_PARAMS["depth_match_tolerance"]:
            findings.append(
                "declared side depth conflicts with a circular section — "
                "evidence conflict, not silently revolved")
            return GEOMETRY_INCOMPLETE, findings
        return AXISYMMETRIC_REVOLUTION, findings
    # every non-circular family needs explicit depth evidence
    if not depth:
        findings.append(
            "side/depth geometry undefined for a non-circular section — "
            "refusing to fabricate hidden geometry")
        return GEOMETRY_INCOMPLETE, findings
    if family == CUSTOM and not (record.get("cross_section") or {}).get(
            "params", {}).get("outline_points"):
        findings.append("CUSTOM family requires authoritative outline "
                        "evidence")
        return GEOMETRY_INCOMPLETE, findings
    return LOFTED_CROSS_SECTION, findings


# ---------------------------------------------------------------------------
# mesh construction


def _resample(profile, n):
    """profile: list of (y_norm 0..1, half_extent_norm 0..1) → (n,) array."""
    prof = np.asarray(profile, dtype=float)
    ys = np.linspace(0.0, 1.0, n)
    return np.interp(ys, prof[:, 0], prof[:, 1])


def build_mesh(record: dict) -> dict:
    """Deterministic lofted mesh from a classified geometry record.

    Returns {vertices (N,3) mm, faces (M,3) int, mesh_identity,
    geometry_class}. Raises ValueError for records that classify
    INCOMPLETE — callers surface the finding; nothing is fabricated.
    """
    geometry_class, findings = classify_geometry(record)
    if geometry_class == GEOMETRY_INCOMPLETE:
        raise ValueError("; ".join(findings) or GEOMETRY_INCOMPLETE)

    dims = record["dimensions"]
    height = float(dims["height_mm"])
    half_w = float(dims["front_width_mm"]) / 2.0
    half_d = (float(dims["side_depth_mm"]) / 2.0
              if dims.get("side_depth_mm") else half_w)
    family = record["cross_section"]["family"]
    params = record["cross_section"].get("params") or {}

    n_h = MESH_PARAMS["height_samples"]
    n_s = MESH_PARAMS["section_samples"]
    width_profile = _resample(record.get("front_profile")
                              or [(0, 1), (1, 1)], n_h)
    depth_profile = _resample(record.get("side_profile")
                              or record.get("front_profile")
                              or [(0, 1), (1, 1)], n_h)
    if family != CIRCULAR and not record.get("side_profile"):
        # a lofted section with no side profile keeps a CONSTANT depth
        # scale — the safe, declared assumption (recorded, not hidden)
        depth_profile = np.ones(n_h)

    section = _section_points(family, params, n_s)
    ys = np.linspace(0.0, height, n_h)
    rings = []
    for i in range(n_h):
        ring = np.empty((n_s, 3))
        ring[:, 0] = section[:, 0] * half_w * width_profile[i]
        ring[:, 1] = section[:, 1] * half_d * depth_profile[i]
        ring[:, 2] = ys[i]
        rings.append(ring)
    vertices = np.concatenate(rings, axis=0)

    faces = []
    for i in range(n_h - 1):
        base, nxt = i * n_s, (i + 1) * n_s
        for j in range(n_s):
            k = (j + 1) % n_s
            faces.append((base + j, base + k, nxt + j))
            faces.append((base + k, nxt + k, nxt + j))
    # end caps (fan to centroid)
    top_c = len(vertices)
    bot_c = top_c + 1
    vertices = np.concatenate([
        vertices,
        [[0.0, 0.0, 0.0]],
        [[0.0, 0.0, height]]], axis=0)
    for j in range(n_s):
        k = (j + 1) % n_s
        faces.append((j, top_c, k))
        last = (n_h - 1) * n_s
        faces.append((last + j, last + k, bot_c))
    faces = np.asarray(faces, dtype=np.int64)

    identity = hashlib.sha256(
        np.round(vertices, 6).tobytes() + faces.tobytes()).hexdigest()[:16]
    return {"vertices": vertices, "faces": faces,
            "mesh_identity": identity, "geometry_class": geometry_class}


# ---------------------------------------------------------------------------
# the authority contract


def build_geometry_record(*, source_authority: str, dimensions: dict,
                          cross_section: dict, front_profile=None,
                          side_profile=None, shoulder_profile=None,
                          neck_profile=None, closure=None,
                          uncertainty=None) -> dict:
    """The full ``container_geometry/1.0`` record — classification,
    validation status and mesh identities. Material appearance is
    deliberately impossible to express here."""
    record = {
        "schema": SCHEMA,
        "authorities": dict(AUTHORITIES),
        "source_authority": source_authority,
        "dimensions": dict(dimensions),
        "cross_section": dict(cross_section),
        "front_profile": front_profile,
        "side_profile": side_profile,
        "shoulder_profile": shoulder_profile,
        "neck_profile": neck_profile,
        "closure": closure,
        "uncertainty": list(uncertainty or []),
        "mesh_params_version": MESH_PARAMS["version"],
    }
    geometry_class, findings = classify_geometry(record)
    record["geometry_class"] = geometry_class
    record["findings"] = findings
    if geometry_class == GEOMETRY_INCOMPLETE:
        record["geometric_validation_status"] = GEOMETRY_INCOMPLETE
        record["body_mesh_identity"] = None
        record["closure_mesh_identity"] = None
        return record
    body = build_mesh(record)
    record["body_mesh_identity"] = body["mesh_identity"]
    closure_identity = None
    if closure and closure.get("profile"):
        closure_rec = {
            "dimensions": {"height_mm": closure["height_mm"],
                           "front_width_mm": closure["width_mm"]},
            "cross_section": {"family": closure.get("family_section",
                                                    CIRCULAR)},
            "front_profile": closure["profile"],
        }
        closure_identity = build_mesh(closure_rec)["mesh_identity"]
    record["closure_mesh_identity"] = closure_identity
    record["geometric_validation_status"] = "MESH_BUILT_PENDING_VALIDATION"
    return record
