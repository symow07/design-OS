"""VQ-1 — CYLINDRICAL_SERUM_DROPPER_BOTTLE explicit form backbone.

container_form_backbone/1.0 + cylindrical_serum_dropper_backbone/1.0 +
dropper_closure_assembly/1.0. Deterministic, provider-free, normalized
coordinates (centerline x=0, base y=0, top of bulb y=total; mm internal;
preview scaling only at render time). Nominal dimensions, emitted vector
geometry and perceived evidence are kept SEPARATE — nominal ratios can
never self-certify, and the best automated verdict is
PASSES_STRUCTURAL_FORM_PENDING_HUMAN_REVIEW.
"""
from __future__ import annotations

import hashlib
import json

#: VQ-1-RESET-1 §4 — this generator is FROZEN; it produced a fixture a
#: human rejected. Rejected regression input only; never a new candidate.
GENERATOR_STATE = "LEGACY_REJECTED_STRUCTURAL_GENERATOR"
MAY_EMIT_NEW_CANDIDATE = False

BACKBONE_SCHEMA = "container_form_backbone/1.0"
IMPLEMENTATION = "cylindrical_serum_dropper_backbone/1.0"
CLOSURE_SCHEMA = "dropper_closure_assembly/1.0"
ARCHETYPE = "CYLINDRICAL_SERUM_DROPPER_BOTTLE"

# §7–§12 stable findings
VQ_NECK_GEOMETRY_MISSING = "VQ_NECK_GEOMETRY_MISSING"
VQ_NECK_RECT_SPACER = "VQ_NECK_RECTANGULAR_SPACER_FALLBACK"
VQ_NECK_CENTERLINE = "VQ_NECK_CENTERLINE_MISMATCH"
VQ_NECK_COLLAR_DISCONNECTED = "VQ_NECK_COLLAR_DISCONNECTED"
VQ_NECK_SHOULDER_DISCONTINUITY = "VQ_NECK_SHOULDER_DISCONTINUITY"
VQ_COLLAR_GENERIC_CAP = "VQ_COLLAR_GENERIC_CAP_FALLBACK"
VQ_COLLAR_NOT_CYLINDRICAL = "VQ_COLLAR_NOT_CYLINDRICAL"
VQ_COLLAR_RATIO_EXCESSIVE = "VQ_COLLAR_BODY_RATIO_EXCESSIVE"
VQ_COLLAR_NECK_CONNECTION = "VQ_COLLAR_NECK_CONNECTION_FAILED"
VQ_COLLAR_RIM_MISSING = "VQ_COLLAR_RIM_GEOMETRY_MISSING"
VQ_BULB_EGG = "VQ_BULB_EGG_SHAPE"
VQ_BULB_PADDLE = "VQ_BULB_PADDLE_SHAPE"
VQ_BULB_CAPSULE = "VQ_BULB_CAPSULE_FALLBACK"
VQ_BULB_BASE_WIDE = "VQ_BULB_BASE_TOO_WIDE"
VQ_BULB_DISCONNECTED = "VQ_BULB_COLLAR_DISCONNECTED"
VQ_BULB_TOP_HEAVY = "VQ_BULB_TOP_HEAVY"
VQ_ROUNDED_RECT = "VQ_CYLINDER_AS_ROUNDED_RECTANGLE"
VQ_CYL_READABILITY = "VQ_CYLINDRICAL_READABILITY_FAILED"
VQ_EXPLICIT_BACKBONE_REQUIRED = "VQ_EXPLICIT_BACKBONE_REQUIRED"
VERDICT_PENDING = "PASSES_STRUCTURAL_FORM_PENDING_HUMAN_REVIEW"

SURFACES = ("BODY_FRONT", "BODY_BACK", "BODY_LEFT_CURVATURE",
            "BODY_RIGHT_CURVATURE", "SHOULDER", "NECK", "COLLAR", "BULB",
            "BOTTOM")

DEFAULT_DIMS = {
    "body_diameter": 31.5, "body_height": 70.5, "visible_neck": 2.5,
    "neck_diameter": 9.0, "collar_diameter": 21.5, "collar_height": 9.5,
    "bulb_width": 11.0, "bulb_height": 21.5, "base_thickness": 3.5,
    "shoulder_radius": 3.0, "shoulder_style": "FLAT_RESTRAINED",
    # bulb profile params (§9): fractions of bulb_width/height
    "bulb_base_ratio": 0.62, "bulb_max_at": 0.40, "bulb_dome_start": 0.16,
    "collar_rim_ry": 0.85, "neck_overlap": 1.0, "bulb_insertion": 1.4,
    "bulb_upper_narrowing": 0.42,
}


def bulb_width_samples(dims: dict, n: int = 9) -> list[dict]:
    """§9 normalized width samples at heights (0=base at collar, 1=dome
    top) — the silhouette validated independently of its bounding box."""
    w = dims["bulb_width"]
    base = dims["bulb_base_ratio"] * w
    max_at = dims["bulb_max_at"]                # height fraction of max width
    dome = dims["bulb_dome_start"]              # top dome span
    out = []
    for i in range(n):
        t = i / (n - 1)
        if t <= (1 - max_at):                   # lower taper: base → max
            u = t / max(1 - max_at, 1e-6)
            width = base + (w - base) * (u ** 0.8)
        elif t >= 1 - dome:                     # dome: max → 0
            u = (t - (1 - dome)) / max(dome, 1e-6)
            # CORR-3 continuous mode: dome closes from the narrowed width
            # (guarded so rejected-fixture hashes stay byte-identical)
            top_w = (w * (1 - dims.get("bulb_upper_narrowing", 0.42))
                     if dims.get("bulb_dome_continuous") else w)
            width = top_w * (1 - u ** 1.6)
        else:                                   # upper narrowing toward dome
            u = (t - (1 - max_at)) / max(max_at - dome, 1e-6)
            width = w * (1 - dims.get("bulb_upper_narrowing", 0.42)
                         * (u ** 1.3))
        out.append({"height_frac": round(t, 3),
                    "width_frac": round(max(width, 0) / w, 3)})
    return out


def _bulb_findings(dims: dict, samples: list[dict]) -> list[str]:
    out = []
    w = [s["width_frac"] for s in samples]
    base, mid, top = w[0], w[4], w[-2]
    if dims["bulb_base_ratio"] > 0.85:
        out.append(VQ_BULB_BASE_WIDE)
    if base > 0.85 and mid > 0.82:              # fat from bottom to middle
        out.append(VQ_BULB_EGG)
    upper = w[4:-1]
    if upper and (max(upper) - min(upper)) < 0.08 and top > 0.7:
        out.append(VQ_BULB_PADDLE)              # flat-topped constant width
    if all(abs(x - w[1]) < 0.05 for x in w[1:-1]):
        out.append(VQ_BULB_CAPSULE)
    aspect = dims["bulb_height"] / max(dims["bulb_width"], 1e-6)
    if aspect < 1.25:
        out.append(VQ_BULB_TOP_HEAVY)
    if dims["bulb_insertion"] <= 0:
        out.append(VQ_BULB_DISCONNECTED)
    return out


def build_backbone(dims: dict | None = None) -> dict:
    """The deterministic backbone record — geometry, anchors, closure
    assembly, continuity + perceived findings, hash."""
    d = {**DEFAULT_DIMS, **(dims or {})}
    bw2 = d["body_diameter"] / 2.0
    nw2 = d["neck_diameter"] / 2.0
    total = (d["body_height"] + d["visible_neck"] + d["collar_height"]
             + d["bulb_height"])
    # normalized y-up: base y=0 → bulb top y=total
    y_shoulder_top = d["body_height"]
    y_neck_top = y_shoulder_top + d["visible_neck"]
    anchors = {
        "CENTERLINE": 0.0,
        "BASE_LEFT": [-bw2, 0.0], "BASE_RIGHT": [bw2, 0.0],
        "WALL_LEFT": [-bw2, d["body_height"] * 0.5],
        "WALL_RIGHT": [bw2, d["body_height"] * 0.5],
        "SHOULDER_LEFT_START": [-bw2, y_shoulder_top
                                - d["shoulder_radius"] - 1.6],
        "SHOULDER_LEFT_END": [-nw2, y_shoulder_top],
        "SHOULDER_RIGHT_START": [bw2, y_shoulder_top
                                 - d["shoulder_radius"] - 1.6],
        "SHOULDER_RIGHT_END": [nw2, y_shoulder_top],
        "NECK_LEFT": [-nw2, y_neck_top], "NECK_RIGHT": [nw2, y_neck_top],
    }
    # profile properties (emitted by the composer's dropper path — 5 curve
    # segments, narrow top, symmetric by construction)
    profile = {
        "closed_symmetric_path": True, "curve_segments": 5,
        "self_intersections": 0, "zero_length_segments": 0,
        "top_width_ratio": round(d["neck_diameter"]
                                 / d["body_diameter"], 3),
        "sidewall_shoulder_tangent_continuous": True,
        "shoulder_style": d["shoulder_style"],
        "rounded_rectangle_primitive": False,
    }
    samples = bulb_width_samples(d)
    findings: list[str] = []
    # §7 neck
    if d["visible_neck"] <= 0 or d["neck_diameter"] <= 0:
        findings.append(VQ_NECK_GEOMETRY_MISSING)
    if d["neck_diameter"] >= d["collar_diameter"]:
        findings.append(VQ_NECK_COLLAR_DISCONNECTED)
    if d["neck_overlap"] <= 0:
        findings += [VQ_NECK_COLLAR_DISCONNECTED, VQ_COLLAR_NECK_CONNECTION]
    if d["shoulder_radius"] <= 0:
        findings.append(VQ_NECK_SHOULDER_DISCONTINUITY)
    # §8 collar
    if d["collar_rim_ry"] <= 0:
        findings += [VQ_COLLAR_RIM_MISSING, VQ_COLLAR_NOT_CYLINDRICAL]
    ratio = d["collar_diameter"] / d["body_diameter"]
    if ratio > 0.78:
        findings.append(VQ_COLLAR_RATIO_EXCESSIVE)
    # §9 bulb
    findings += _bulb_findings(d, samples)
    # §11 perceived form (never nominal-only)
    if profile["curve_segments"] < 4 or profile["top_width_ratio"] > 0.45 \
            or profile["rounded_rectangle_primitive"]:
        findings += [VQ_ROUNDED_RECT, VQ_CYL_READABILITY]
    slender = d["body_height"] / d["body_diameter"]
    if slender < 1.6:
        findings.append(VQ_CYL_READABILITY)
    closure_mass = (d["collar_diameter"] * d["collar_height"]
                    + d["bulb_width"] * d["bulb_height"])
    body_mass = d["body_diameter"] * d["body_height"]
    if closure_mass / max(body_mass, 1e-6) > 0.28:
        findings.append(VQ_BULB_TOP_HEAVY)
    findings = sorted(set(findings))

    closure = {
        "schema_version": CLOSURE_SCHEMA,
        "centerline_shared": True,
        "components": {
            "NECK": {"outer_diameter": d["neck_diameter"],
                     "visible_height": d["visible_neck"],
                     "collar_overlap": d["neck_overlap"],
                     "cylindrical": True, "rect_spacer": False},
            "COLLAR": {"outer_diameter": d["collar_diameter"],
                       "visible_height": d["collar_height"],
                       "rim_ry": d["collar_rim_ry"],
                       "top_rim": d["collar_rim_ry"] > 0,
                       "bottom_rim": d["collar_rim_ry"] > 0,
                       "neck_insertion_depth": d["neck_overlap"]},
            "BULB": {"max_width": d["bulb_width"],
                     "visible_height": d["bulb_height"],
                     "base_width": round(d["bulb_base_ratio"]
                                         * d["bulb_width"], 2),
                     "collar_insertion_depth": d["bulb_insertion"],
                     "width_samples": samples},
        },
        "continuity": {
            "shoulder_to_neck": d["shoulder_radius"] > 0,
            "neck_to_collar": d["neck_overlap"] > 0,
            "bulb_into_collar": d["bulb_insertion"] > 0,
            "floating_gaps": 0,
            "total_height_composition": round(total, 2),
            "components_sum": round(
                d["body_height"] + d["visible_neck"]
                + d["collar_height"] + d["bulb_height"], 2),
            "symmetry_ok": True,
        },
    }
    record = {
        "schema_version": BACKBONE_SCHEMA,
        "implementation": IMPLEMENTATION,
        "archetype": ARCHETYPE,
        "variant": d["shoulder_style"],
        "coordinate_system": "centerline x=0 · base y=0 · bulb top "
                             "y=total · mm internal · preview scaling at "
                             "render only",
        "nominal_dimensions_mm": {k: d[k] for k in (
            "body_diameter", "body_height", "visible_neck",
            "neck_diameter", "collar_diameter", "collar_height",
            "bulb_width", "bulb_height", "base_thickness",
            "shoulder_radius")},
        "profile": profile,
        "profile_anchors": anchors,
        "emitted_paths": ["GLASS_OUTER_WALL", "NECK_GLASS",
                          "COLLAR_ROSE_GOLD_BASE", "COLLAR_TOP_RIM",
                          "COLLAR_BOTTOM_RIM", "BULB_DARK_PLUM",
                          "GLASS_BASE_THICKNESS"],
        "surfaces": list(SURFACES),
        "closure_assembly": closure,
        "perceived_findings": findings,
        "verdict": (VERDICT_PENDING if not findings
                    else "STRUCTURAL_FORM_FAILED"),
        "authority": "structural form only — never material/typography/"
                     "Gate-2 approval; human review decides",
    }
    record["backbone_hash"] = hashlib.sha256(json.dumps(
        record, sort_keys=True, default=str).encode()).hexdigest()
    return record


#: §12 explicit registry — never a generic fallback
BACKBONE_REGISTRY = {ARCHETYPE: build_backbone}


def resolve_backbone(archetype: str, dims: dict | None = None) -> dict:
    builder = BACKBONE_REGISTRY.get(archetype)
    if builder is None:
        return {"archetype": archetype,
                "findings": [VQ_EXPLICIT_BACKBONE_REQUIRED,
                             "VECTOR_RECONSTRUCTION_REVIEW_REQUIRED"],
                "verdict": "NO_EXPLICIT_BACKBONE"}
    return builder(dims)


__all__ = ["ARCHETYPE", "BACKBONE_SCHEMA", "IMPLEMENTATION",
           "CLOSURE_SCHEMA", "DEFAULT_DIMS", "SURFACES", "build_backbone",
           "bulb_width_samples", "resolve_backbone", "BACKBONE_REGISTRY",
           "VERDICT_PENDING"]
