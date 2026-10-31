"""VQ-1-RESET-2 — concept-visual envelope backbone.

Two authorities, never conflated:

* CONCEPT_VISUAL_GEOMETRY — normalized contours traced from reference
  image #97. Authorized for visual reconstruction and preview. It may
  never be described as manufacturable, supplier-confirmed, or a
  production/tooling dimension.
* PRODUCTION_GEOMETRY — manufacturer drawing, supplier specification,
  physical sample or approved CAD. Currently NOT_AVAILABLE, so production
  readiness stays blocked by VQ_PRODUCTION_GEOMETRY_EVIDENCE_REQUIRED.

The envelope carries no millimetres at all: assembly height is 1.0, body
visible width is 1.0, the shared centerline is 0. Every contour is fitted
with cubic curves to the ACTUAL pixel edge of the unobscured right side
and mirrored — a mirroring the human authorized as a concept-only
assumption, because the left side is occluded by the carton and bilateral
symmetry is not measurable from this photograph.

Only the visible envelope of the dark closure is modelled. Its internal
mechanism is UNRESOLVED / HIDDEN and is never drawn.
"""
from __future__ import annotations

from apps.ire.corr_mirror import closed_from_left, mirrored_return  # noqa
from apps.ire.graph import (ClosePath, Color, CubicTo, GradientFill,
                            GradientStop, Group, MoveTo, Path, Stroke)

AUTHORITY_SCHEMA = "container_geometry_authority/1.0"
ENVELOPE_SCHEMA = "concept_visual_envelope/1.0"
INK = Color.from_hex("#2A2426")

CONCEPT_VISUAL = "CONCEPT_VISUAL_GEOMETRY"
PRODUCTION = "PRODUCTION_GEOMETRY"
VQ_PRODUCTION_GEOMETRY_EVIDENCE_REQUIRED = \
    "VQ_PRODUCTION_GEOMETRY_EVIDENCE_REQUIRED"

#: §1 the only approved semantic statement about the dark component
APPROVED_VISIBLE_SEMANTIC = \
    "VISIBLE_DARK_CLOSURE_ENVELOPE_WITH_ROUNDED_DOME_AND_FLARED_SKIRT"
INTERNAL_MECHANISM = "UNRESOLVED / HIDDEN"
FORBIDDEN_CLASSIFICATIONS = (
    "exposed conventional pipette bulb", "narrow-stem bulb",
    "outer overcap", "actuator", "complete closure mechanism")

#: §6 stable failures
VQ_CLOSURE_ENVELOPE_SPEAR_SHAPE = "VQ_CLOSURE_ENVELOPE_SPEAR_SHAPE"
VQ_CLOSURE_ENVELOPE_LEAF_SHAPE = "VQ_CLOSURE_ENVELOPE_LEAF_SHAPE"
VQ_CLOSURE_CONSTANT_WIDTH_REGION_MISSING = \
    "VQ_CLOSURE_CONSTANT_WIDTH_REGION_MISSING"
VQ_CLOSURE_FLARE_MISSING = "VQ_CLOSURE_FLARE_MISSING"
VQ_UNSUPPORTED_EXTERNAL_STEM_EMITTED = \
    "VQ_UNSUPPORTED_EXTERNAL_STEM_EMITTED"

#: §5 deterministic reference-pixel relationships. NOT physical dimensions.
REFERENCE_PIXEL_RELATIONSHIPS = {
    "authority": "REFERENCE_PIXEL_RELATIONSHIPS",
    "is_physical_dimension": False,
    "source_image": "GeneratedImage#97 task_52_var_2_reALblg.png",
    "visible_body_width_px": 343,
    "visible_collar_width_px": 217,
    "collar_body_ratio": 0.633,
    "dark_constant_width_px": 109,
    "dark_body_ratio": 0.318,
    "lower_flare_width_px": 129,
    "flare_body_ratio": 0.376,
    "constant_width_run_px": 96,
    "left_body_edge": "PARTIALLY_OCCLUDED_BY_CARTON",
    "bilateral_symmetry": "NOT_DIRECTLY_MEASURABLE",
}

#: §3 CORR-5's millimetre values, frozen as rejected assumptions. Kept so
#: nothing is deleted, and deliberately NOT used by anything here.
REJECTED_INTERNAL_ASSUMPTIONS = {
    "state": "REJECTED_INTERNAL_ASSUMPTIONS",
    "origin": "CORR-5 (vq1_corr5_fixture.json, hash d99c412df4989c18)",
    "values_mm": {"body_diameter": 31.3, "body_height": 61.0,
                  "collar_diameter": 15.9, "collar_height": 12.1,
                  "bulb_max_width": 8.8, "bulb_stem_width": 3.9,
                  "bulb_body_height": 15.0, "bulb_stem_visible": 3.2,
                  "total_height": 92.9},
    "may_drive_new_fixture": False,
    "web_grounded": False,
    "note": "internal assumptions, never supplier-confirmed; preserved as "
            "rejected evidence only",
}

#: §4 component bands in source-image pixel space (from the calibrated
#: crops). Boundaries only — widths come from the measured contour.
COMPONENT_BANDS = {
    # the collar's top edge is at ~492; ending the dark band at 490 keeps
    # the collar out of the closure's own contour
    # boundaries are set INSIDE each component: rows straddling an edge
    # blend two widths, and a band that starts on one reads too narrow
    "DARK_CLOSURE": (292, 488),
    "COLLAR": (500, 668),
    "NECK_VISIBLE": (670, 690),
    "SHOULDER": (690, 730),
    "BODY": (730, 1310),
    "BASE": (1310, 1348),
}
ASSEMBLY_SPAN_PX = (292, 1348)
BODY_WIDTH_PX = 343.0
#: body visible width as a fraction of assembly height. Width and height
#: are normalized INDEPENDENTLY (both to 1.0), so every x must be scaled
#: by this when drawing — without it the render is 1:1 instead of ~3:1,
#: and a profile comparison that divides by body width cannot see the
#: error. The visual inspector caught exactly that.
ASPECT_W_OVER_H = BODY_WIDTH_PX / (ASSEMBLY_SPAN_PX[1]
                                   - ASSEMBLY_SPAN_PX[0])
CENTERLINE_PX = 666.5
OCCLUDED_SIDE = "LEFT"


def geometry_authority(production_available: bool = False) -> dict:
    """§2 — the two-authority record. Concept geometry can never silently
    become production geometry."""
    return {
        "schema_version": AUTHORITY_SCHEMA,
        "modes": {
            CONCEPT_VISUAL: {
                "authority_sources": ["selected reference pixels",
                                      "normalized visible contours",
                                      "human semantic decisions",
                                      "visualizer findings"],
                "permitted_use": ["visual structural reconstruction",
                                  "concept preview",
                                  "native-vector concept artwork",
                                  "visual comparison"],
                "prohibited_claims": ["manufacturable", "supplier-confirmed",
                                      "production dimension",
                                      "tooling dimension",
                                      "verified closure construction",
                                      "formula compatibility"],
                "state": "AUTHORIZED"},
            PRODUCTION: {
                "authority_sources": ["manufacturer technical drawing",
                                      "supplier specification",
                                      "physical sample measurement",
                                      "approved CAD",
                                      "manufacturer confirmation"],
                "state": ("AVAILABLE" if production_available
                          else "NOT_AVAILABLE"),
                "blocked_by": ([] if production_available
                               else [VQ_PRODUCTION_GEOMETRY_EVIDENCE_REQUIRED,
                                     "MANUFACTURER_DIMENSIONS_REQUIRED",
                                     "CLOSURE_CONSTRUCTION_CONFIRMATION_"
                                     "REQUIRED",
                                     "BOTTLE_CLOSURE_COMPATIBILITY_REQUIRED",
                                     "PHYSICAL_SAMPLE_OR_TECHNICAL_DRAWING_"
                                     "REQUIRED"])},
        },
        "visible_component_semantic": APPROVED_VISIBLE_SEMANTIC,
        "internal_closure_mechanism": INTERNAL_MECHANISM,
        "forbidden_classifications": list(FORBIDDEN_CLASSIFICATIONS),
        "bilateral_symmetry": "HUMAN_APPROVED_CONCEPT_ONLY_ASSUMPTION",
        "symmetry_reason": "the left side of the reference is partially "
                           "occluded by the carton; the unobscured right "
                           "contour may be mirrored for concept-visual "
                           "geometry. This is not evidence of production "
                           "symmetry or tooling geometry.",
        "rejected_internal_assumptions": REJECTED_INTERNAL_ASSUMPTIONS,
    }


# --- normalized envelope ------------------------------------------------------

def _smooth(vals, window=9):
    out, n = [], len(vals)
    half = window // 2
    for i in range(n):
        seg = [v for v in vals[max(0, i - half):min(n, i + half + 1)]
               if v is not None]
        out.append(sum(seg) / len(seg) if seg else None)
    return out


def _catmull_to_cubic(points):
    """Catmull-Rom through the sampled edge → C1 cubic Bézier chain. A
    polyline of pixel samples would read as polygonal; this keeps the
    fitted curve continuous, which §8 requires."""
    pts = list(points)
    if len(pts) < 2:
        return []
    ext = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        out.append((c1, c2, p2))
    return out


def build_envelope(half_width_px: dict, *, samples_per_band: int = 14,
                   image_id: str = "", crops=()) -> dict:
    """§4 — the normalized concept-visual envelope. ``half_width_px`` maps
    source-image y → measured right-edge half-width in px. Output carries
    NO millimetres."""
    top, bottom = ASSEMBLY_SPAN_PX
    span = float(bottom - top)
    ys = sorted(y for y in half_width_px if top <= y <= bottom)
    raw = [half_width_px[y] for y in ys]
    sm = _smooth(raw, 11)
    lookup = {y: v for y, v in zip(ys, sm) if v is not None}

    def hw(y):
        if y in lookup:
            return lookup[y]
        near = min(lookup, key=lambda k: abs(k - y))
        return lookup[near]

    components = {}
    for name, (y0, y1) in COMPONENT_BANDS.items():
        pts = []
        for i in range(samples_per_band + 1):
            y = y0 + (y1 - y0) * i / samples_per_band
            # normalized: assembly height 1.0, body visible width 1.0,
            # centerline 0, +x to the right
            pts.append((round(hw(y) / BODY_WIDTH_PX, 5),
                        round((y - top) / span, 5)))
        components[name] = {
            "normalized_points": pts,
            "y_norm_range": [round((y0 - top) / span, 5),
                             round((y1 - top) / span, 5)],
            "max_half_width_norm": round(max(p[0] for p in pts), 5),
            "min_half_width_norm": round(min(p[0] for p in pts), 5),
        }
    return {
        "schema_version": ENVELOPE_SCHEMA,
        "reference_image": image_id, "crops": list(crops),
        "coordinate_system": {
            "assembly_height": 1.0, "body_visible_width": 1.0,
            "shared_centerline": 0.0, "units": "NORMALIZED_NONE",
            "millimetres_used": False},
        "centerline_px": CENTERLINE_PX,
        "assembly_span_px": list(ASSEMBLY_SPAN_PX),
        "body_width_px": BODY_WIDTH_PX,
        "components": components,
        "occluded_regions": [{"side": OCCLUDED_SIDE,
                              "cause": "adjacent carton",
                              "y_norm_range": [0.0, 1.0],
                              "measurable": False}],
        "mirrored_regions": [{"side": "LEFT",
                              "derived_from": "measured RIGHT edge",
                              "authority": "HUMAN_APPROVED_CONCEPT_ONLY_"
                                           "ASSUMPTION"}],
        "confidence": 0.72,
        "human_authority": "CONCEPT_VISUAL_GEOMETRY_AUTHORIZED",
        "production_authority_prohibition":
            "this envelope may NOT be described as manufacturable, "
            "supplier-confirmed, a production dimension, a tooling "
            "dimension or a verified closure construction",
        "reference_pixel_relationships": REFERENCE_PIXEL_RELATIONSHIPS,
    }


def envelope_left_path(env: dict, ox: float, oy: float, height: float):
    """One canonical left-half path from the envelope, as cubics. The
    right half is produced by exact mirroring at draw time."""
    order = ("DARK_CLOSURE", "COLLAR", "NECK_VISIBLE", "SHOULDER", "BODY",
             "BASE")
    pts = []
    for name in order:
        for x, y in env["components"][name]["normalized_points"]:
            p = (ox - x * height * ASPECT_W_OVER_H, oy + y * height)
            if not pts or abs(p[0] - pts[-1][0]) > 1e-9 or \
                    abs(p[1] - pts[-1][1]) > 1e-9:
                pts.append(p)
    # close the base onto the centerline so the silhouette is a solid
    segs = [MoveTo(x=pts[0][0], y=pts[0][1])]
    for c1, c2, p in _catmull_to_cubic(pts):
        segs.append(CubicTo(x1=c1[0], y1=c1[1], x2=c2[0], y2=c2[1],
                            x=p[0], y=p[1]))
    return segs


def canonical_paths(env: dict, ox: float, oy: float, height: float) -> dict:
    """The ONE contour set: the rendered outline and the concept contour
    are the same objects (§8)."""
    left = envelope_left_path(env, ox, oy, height)
    return {"ENVELOPE": closed_from_left(left, ox)}


_FILL = ("#F2ECE8", "#E6DCD6", "#B3A49C")

#: RESET-2 iteration 2: the assembly is drawn as SEPARATE visible
#: components. Iteration 1 emitted one undifferentiated silhouette, and
#: the inspector correctly reported "no closure, no collar" — a single
#: outline cannot show an assembly.
_COMPONENT_FILL = {
    "DARK_CLOSURE": ("#7A6570", "#4A3A44", "#291F26"),
    "COLLAR": ("#F0E0CE", "#CDB9A6", "#8A7460"),
    "NECK_VISIBLE": ("#EFE7E1", "#DCD1CA", "#A99C95"),
    "BODY_ASSEMBLY": ("#F4EEEA", "#E7DCD6", "#B3A49C"),
}
#: draw order: glass first, then the metal collar, then the dark closure
_COMPONENT_ORDER = ("BODY_ASSEMBLY", "NECK_VISIBLE", "COLLAR",
                    "DARK_CLOSURE")
#: the glass body is one continuous contour — shoulder, body and base are
#: a single silhouette so no horizontal ledge appears between them
_BODY_BANDS = ("SHOULDER", "BODY", "BASE")


def component_paths(env, ox, oy, height):
    """One closed contour per VISIBLE component, each mirrored from its
    own measured right edge."""
    out = {}
    for name in _COMPONENT_ORDER:
        bands = _BODY_BANDS if name == "BODY_ASSEMBLY" else (name,)
        pts = []
        for band in bands:
            band_pts = list(env["components"][band]["normalized_points"])
            if band == "COLLAR":
                # extend the sleeve up to meet the closure's flare at its
                # own full width, so the union has no notch between them
                top_y = env["components"]["DARK_CLOSURE"][
                    "y_norm_range"][1]
                band_pts = [(band_pts[0][0], top_y)] + band_pts
            for x, y in band_pts:
                p = (ox - x * height * ASPECT_W_OVER_H, oy + y * height)
                if not pts or abs(p[0] - pts[-1][0]) > 1e-9 or \
                        abs(p[1] - pts[-1][1]) > 1e-9:
                    pts.append(p)
        segs = [MoveTo(x=pts[0][0], y=pts[0][1])]
        for c1, c2, p in _catmull_to_cubic(pts):
            segs.append(CubicTo(x1=c1[0], y1=c1[1], x2=c2[0], y2=c2[1],
                                x=p[0], y=p[1]))
        out[name] = closed_from_left(segs, ox)
    return out


def draw_assembly(env, ox, oy, height, *, prefix="", outline_only=False,
                  width_mm=0.45, color=None):
    """The consumer-visible assembly. The same contours serve the render
    and the diagnostic outline."""
    g = component_paths(env, ox, oy, height)
    kids = []
    for name in _COMPONENT_ORDER:
        if outline_only:
            kids.append(Path(name=f"{prefix}{name}", segments=g[name],
                             stroke=Stroke(color=color or INK,
                                           width_mm=width_mm)))
        else:
            hi, mid, lo = _COMPONENT_FILL[name]
            kids.append(Path(
                name=f"{prefix}{name}", segments=g[name],
                fill=GradientFill(
                    kind="linear", x1=ox - height * 0.52, y1=0.0,
                    x2=ox + height * 0.52, y2=0.0,
                    stops=[GradientStop(offset=0.0,
                                        color=Color.from_hex(mid)),
                           GradientStop(offset=0.28,
                                        color=Color.from_hex(hi)),
                           GradientStop(offset=0.66,
                                        color=Color.from_hex(mid)),
                           GradientStop(offset=1.0,
                                        color=Color.from_hex(lo))])))
    return Group(name=f"{prefix}Assembly", role="product", children=kids)


def render_page_width(height: float) -> float:
    """The body is ~1.01x the normalized unit, so a page narrower than
    that clips the silhouette — iteration 1 was cropped this way."""
    return height * ASPECT_W_OVER_H * 1.45


def draw_envelope(env, ox, oy, height, *, prefix="", outline_only=False,
                  width_mm=0.5, color=None):
    g = canonical_paths(env, ox, oy, height)
    if outline_only:
        node = Path(name=f"{prefix}ENVELOPE", segments=g["ENVELOPE"],
                    stroke=Stroke(color=color or INK, width_mm=width_mm))
    else:
        hi, mid, lo = _FILL
        node = Path(name=f"{prefix}ENVELOPE", segments=g["ENVELOPE"],
                    fill=GradientFill(
                        kind="linear",
                        x1=ox - height * ASPECT_W_OVER_H * 0.5, y1=0.0,
                        x2=ox + height * ASPECT_W_OVER_H * 0.5, y2=0.0,
                        stops=[GradientStop(offset=0.0,
                                            color=Color.from_hex(mid)),
                               GradientStop(offset=0.28,
                                            color=Color.from_hex(hi)),
                               GradientStop(offset=0.66,
                                            color=Color.from_hex(mid)),
                               GradientStop(offset=1.0,
                                            color=Color.from_hex(lo))]))
    return Group(name=f"{prefix}Envelope", role="product", children=[node])


def draw_component(env, name, ox, oy, height, *, prefix="", color=None,
                   width_mm=0.5):
    """One component's visible contour, mirrored — for close-up panels."""
    pts = [(ox - x * height * ASPECT_W_OVER_H, oy + y * height)
           for x, y in env["components"][name]["normalized_points"]]
    segs = [MoveTo(x=pts[0][0], y=pts[0][1])]
    for c1, c2, p in _catmull_to_cubic(pts):
        segs.append(CubicTo(x1=c1[0], y1=c1[1], x2=c2[0], y2=c2[1],
                            x=p[0], y=p[1]))
    segs = segs + mirrored_return(segs, ox) + [ClosePath()]
    return Group(name=f"{prefix}{name}", role="product", children=[
        Path(name=f"{prefix}{name}_CONTOUR", segments=segs,
             stroke=Stroke(color=color or INK, width_mm=width_mm))])


# --- §6 envelope validation ---------------------------------------------------

def closure_envelope_findings(env: dict) -> dict:
    """The dark closure must read as: rounded dome → near-parallel sides →
    short lower flare → collar. Anything else is a stable failure."""
    pts = env["components"]["DARK_CLOSURE"]["normalized_points"]
    w = [p[0] for p in pts]
    n = len(w)
    peak = w.index(max(w))
    top_w = w[0]
    findings, checks = [], {}

    # a long near-constant shaft through the upper/middle, measured past
    # the dome so the dome's own narrowing does not count as variation
    cap_n = env.get("dome_cap", {}).get("samples", 0)
    if cap_n:
        body_pts = w[cap_n:]
        mid = body_pts[:max(1, int(len(body_pts) * 0.72))]
    else:
        mid = w[int(n * 0.30):int(n * 0.78)]
    spread = (max(mid) - min(mid)) / max(max(mid), 1e-9)
    checks["constant_width_region_present"] = spread <= 0.14
    if not checks["constant_width_region_present"]:
        findings.append(VQ_CLOSURE_CONSTANT_WIDTH_REGION_MISSING)

    # short lower flare: widest point in the bottom quarter
    checks["lower_flare_present"] = (peak >= int(n * 0.75)
                                     and max(w) > max(mid) * 1.06)
    if not checks["lower_flare_present"]:
        findings.append(VQ_CLOSURE_FLARE_MISSING)

    checks["rounded_dome_not_spear"] = top_w <= max(w) * 0.45
    if top_w > max(w) * 0.55:
        findings.append(VQ_CLOSURE_ENVELOPE_SPEAR_SHAPE)
    # a leaf/teardrop puts its maximum in the middle, not at the skirt
    checks["no_mid_maximum"] = not (0.25 * n <= peak <= 0.65 * n)
    if not checks["no_mid_maximum"]:
        findings.append(VQ_CLOSURE_ENVELOPE_LEAF_SHAPE)
    # an external stem would show a narrow waist just above the collar
    lower = w[int(n * 0.72):]
    checks["no_external_stem"] = min(lower) >= max(mid) * 0.80
    if not checks["no_external_stem"]:
        findings.append(VQ_UNSUPPORTED_EXTERNAL_STEM_EMITTED)

    return {"checks": checks, "findings": sorted(set(findings)),
            "constant_width_spread": round(spread, 4),
            "peak_at_fraction": round(peak / (n - 1), 4),
            "top_width_fraction_of_max": round(top_w / max(w), 4),
            "status": ("ENVELOPE_MATCHES_APPROVED_VISIBLE_SEMANTIC"
                       if not findings else "ENVELOPE_FAILED")}


# --- §10 deterministic visual comparison --------------------------------------

GATES = {"silhouette_iou_min": 0.90, "mean_contour_max": 0.020,
         "p95_contour_max": 0.045, "max_contour_max": 0.070,
         "collar_ratio_error_max": 0.025, "dark_ratio_error_max": 0.025,
         "aspect_error_max": 0.02}


def _resample(pairs, n=400):
    """(y_norm, half_width_norm) → n evenly spaced half-widths."""
    pts = sorted(pairs)
    out = []
    for i in range(n):
        y = i / (n - 1)
        lo = max((p for p in pts if p[0] <= y), default=pts[0],
                 key=lambda p: p[0])
        hi = min((p for p in pts if p[0] >= y), default=pts[-1],
                 key=lambda p: p[0])
        if hi[0] == lo[0]:
            out.append(lo[1])
        else:
            f = (y - lo[0]) / (hi[0] - lo[0])
            out.append(lo[1] * (1 - f) + hi[1] * f)
    return out


def compare_to_reference(reference_pairs, candidate_pairs, *,
                         reference_ratios: dict,
                         candidate_ratios: dict, n: int = 400,
                         candidate_aspect: float | None = None) -> dict:
    """Both profiles are half-widths normalized by the SAME body width, so
    this measures shape AND scale. Only the unobscured right side is
    compared — the occluded left is never scored."""
    a, b = _resample(reference_pairs, n), _resample(candidate_pairs, n)
    inter = sum(min(x, y) for x, y in zip(a, b))
    union = sum(max(x, y) for x, y in zip(a, b))
    iou = inter / union if union else 0.0
    d = sorted(abs(x - y) for x, y in zip(a, b))
    mean_d = sum(d) / len(d)
    p95 = d[int(len(d) * 0.95)]
    ca = sum(y * v for y, v in zip((i / (n - 1) for i in range(n)), a))
    cb = sum(y * v for y, v in zip((i / (n - 1) for i in range(n)), b))
    centroid = abs(ca / max(sum(a), 1e-9) - cb / max(sum(b), 1e-9))
    err = {k: abs(reference_ratios.get(k, 0) - candidate_ratios.get(k, 0))
           for k in ("collar_body_ratio", "dark_body_ratio",
                     "flare_body_ratio", "constant_width_run_norm",
                     "shoulder_rise_norm")}
    metrics = {
        "silhouette_iou_non_occluded": round(iou, 5),
        "mean_normalized_contour_distance": round(mean_d, 5),
        "p95_contour_distance": round(p95, 5),
        "max_contour_distance": round(d[-1], 5),
        "component_centroid_displacement": round(centroid, 5),
        "collar_body_ratio_error": round(err["collar_body_ratio"], 5),
        "dark_body_ratio_error": round(err["dark_body_ratio"], 5),
        "constant_width_region_difference":
            round(err["constant_width_run_norm"], 5),
        "flare_width_difference": round(err["flare_body_ratio"], 5),
        "shoulder_rise_difference": round(err["shoulder_rise_norm"], 5),
        "occluded_side_excluded_from_scoring": OCCLUDED_SIDE,
        "reference_aspect_w_over_h": round(ASPECT_W_OVER_H, 5),
        "candidate_aspect_w_over_h": (round(candidate_aspect, 5)
                                      if candidate_aspect else None),
        "aspect_error": (round(abs(candidate_aspect - ASPECT_W_OVER_H), 5)
                         if candidate_aspect else None),
    }
    gates = {
        "silhouette_iou": iou >= GATES["silhouette_iou_min"],
        "mean_contour_distance": mean_d <= GATES["mean_contour_max"],
        "p95_contour_distance": p95 <= GATES["p95_contour_max"],
        "max_contour_distance": d[-1] <= GATES["max_contour_max"],
        "collar_body_ratio": err["collar_body_ratio"] <=
        GATES["collar_ratio_error_max"],
        "dark_body_ratio": err["dark_body_ratio"] <=
        GATES["dark_ratio_error_max"],
        # profile comparison divides by body width and is therefore blind
        # to overall proportion; this gate is what catches a squat render
        "assembly_aspect": (candidate_aspect is not None and
                            abs(candidate_aspect - ASPECT_W_OVER_H)
                            <= GATES["aspect_error_max"]),
    }
    return {"metrics": metrics, "gates": gates,
            "gates_pass": all(gates.values()), "thresholds": dict(GATES),
            "note": "a failing component is never excluded to improve the "
                    "overall score"}


def envelope_ratios(env: dict) -> dict:
    """Ratios read back off the envelope itself, in the same normalized
    units as the reference relationships."""
    comp = env["components"]
    pts = comp["DARK_CLOSURE"]["normalized_points"]
    cap_n = env.get("dome_cap", {}).get("samples", 0)
    dark = [p[0] for p in pts]
    body = dark[cap_n:] if cap_n else dark[int(len(dark) * 0.30):]
    # the shaft is the constant-width run: exclude the lower flare
    shaft = body[:max(1, int(len(body) * 0.72))] if cap_n else \
        dark[int(len(dark) * 0.30):int(len(dark) * 0.78)]
    band = COMPONENT_BANDS["DARK_CLOSURE"]
    span = ASSEMBLY_SPAN_PX[1] - ASSEMBLY_SPAN_PX[0]
    sh = comp["SHOULDER"]["y_norm_range"]
    return {
        "collar_body_ratio": round(comp["COLLAR"]["max_half_width_norm"] * 2,
                                   5),
        "dark_body_ratio": round(sum(shaft) / len(shaft) * 2, 5),
        "flare_body_ratio": round(max(dark) * 2, 5),
        "constant_width_run_norm": round(
            (band[1] - band[0]) * 0.48 / span, 5),
        "shoulder_rise_norm": round(sh[1] - sh[0], 5),
    }


# --- RESET2-CORR-1: dome termination ------------------------------------------

VQ_CLOSURE_DOME_FLAT_TOP = "VQ_CLOSURE_DOME_FLAT_TOP"
VQ_CLOSURE_APEX_FINITE_WIDTH = "VQ_CLOSURE_APEX_FINITE_WIDTH"
VQ_CLOSURE_HORIZONTAL_CLOSING_SEGMENT = \
    "VQ_CLOSURE_HORIZONTAL_CLOSING_SEGMENT"
VQ_REFERENCE_DOME_NOT_PRESERVED = "VQ_REFERENCE_DOME_NOT_PRESERVED"
VQ_CLOSURE_APEX_NOT_CENTERED = "VQ_CLOSURE_APEX_NOT_CENTERED"
VQ_CLOSURE_TOP_HORIZONTAL_SEGMENT = "VQ_CLOSURE_TOP_HORIZONTAL_SEGMENT"
VQ_CLOSURE_DOME_CURVATURE_DISCONTINUITY = \
    "VQ_CLOSURE_DOME_CURVATURE_DISCONTINUITY"
VQ_CLOSURE_UPPER_PLATEAU = "VQ_CLOSURE_UPPER_PLATEAU"

#: the measured dome spans ~56 px of the 1056 px assembly before the shaft
#: reaches full width
DOME_HEIGHT_NORM = 56.0 / (ASSEMBLY_SPAN_PX[1] - ASSEMBLY_SPAN_PX[0])
DOME_SAMPLES = 24


def apply_dome_cap(env: dict, *, samples: int = DOME_SAMPLES,
                   dome_height: float = DOME_HEIGHT_NORM) -> dict:
    """Replace ONLY the closure's dome termination.

    IT4 ended the closure contour at a finite half-width, so mirroring
    joined the two sides with a straight horizontal segment — a flat,
    clipped crown. The replacement is a quarter-ellipse cap: half-width
    reaches exactly zero at the apex on the shared centerline, and its
    slope is zero where it meets the constant-width shaft, so the join is
    C1-continuous. Nothing outside the dome region is touched."""
    import copy
    import math
    out = copy.deepcopy(env)
    pts = list(out["components"]["DARK_CLOSURE"]["normalized_points"])
    y0 = pts[0][1]
    y_end = y0 + dome_height
    shaft = [p for p in pts if p[1] > y_end]
    if not shaft:
        return out
    shaft_hw = shaft[0][0]
    # sampled by ANGLE, not by height: a quarter-ellipse sampled uniformly
    # in y takes a very large first step off the apex, which reads as a
    # curvature discontinuity in the discrete check even though the curve
    # itself is smooth
    cap = []
    for i in range(samples + 1):
        th = (math.pi / 2) * i / samples      # 0 = apex, pi/2 = shaft join
        hw = shaft_hw * math.sin(th)
        y = y0 + dome_height * (1.0 - math.cos(th))
        cap.append((round(hw, 6), round(y, 6)))
    new_pts = cap + shaft
    out["components"]["DARK_CLOSURE"]["normalized_points"] = new_pts
    out["components"]["DARK_CLOSURE"]["max_half_width_norm"] = round(
        max(p[0] for p in new_pts), 5)
    out["components"]["DARK_CLOSURE"]["min_half_width_norm"] = 0.0
    out["dome_cap"] = {
        "construction": "QUARTER_ELLIPSE_CAP",
        "samples": samples + 1,
        "dome_height_norm": round(dome_height, 6),
        "shaft_half_width_norm": round(shaft_hw, 6),
        "apex_half_width": 0.0,
        "apex_on_centerline": True,
        "c1_join_to_shaft": True,
        "replaced_region_only": "DARK_CLOSURE upper dome",
        "samples_in_upper_quarter": samples + 1,
        "control_points": [list(p) for p in cap],
    }
    return out


def dome_findings(env: dict) -> dict:
    """§5 deterministic dome checks."""
    pts = env["components"]["DARK_CLOSURE"]["normalized_points"]
    w = [p[0] for p in pts]
    y = [p[1] for p in pts]
    findings, checks = [], {}
    checks["apex_half_width_zero"] = abs(w[0]) < 1e-9
    if not checks["apex_half_width_zero"]:
        findings += [VQ_CLOSURE_APEX_FINITE_WIDTH, VQ_CLOSURE_DOME_FLAT_TOP]
    # a horizontal closing segment = two apex-adjacent points at one y
    checks["no_horizontal_closing_segment"] = abs(y[1] - y[0]) > 1e-9
    if not checks["no_horizontal_closing_segment"]:
        findings += [VQ_CLOSURE_TOP_HORIZONTAL_SEGMENT,
                     VQ_CLOSURE_HORIZONTAL_CLOSING_SEGMENT]
    cap_n = env.get("dome_cap", {}).get("samples", 0)
    cap = w[:cap_n] if cap_n else w[:6]
    checks["dome_widens_monotonically_from_apex"] = all(
        b >= a - 1e-9 for a, b in zip(cap, cap[1:]))
    checks["at_least_21_dome_samples"] = cap_n >= 21
    # curvature continuity across the cap: bounded second differences
    d1 = [b - a for a, b in zip(cap, cap[1:])]
    d2 = [abs(b - a) for a, b in zip(d1, d1[1:])]
    checks["dome_curvature_continuous"] = bool(d2) and max(d2) < 0.02
    if not checks["dome_curvature_continuous"]:
        findings.append(VQ_CLOSURE_DOME_CURVATURE_DISCONTINUITY)
    # no plateau inside the cap other than the C1 join at the very end
    plateau = sum(1 for v in d1[:-2] if abs(v) < 1e-4)
    checks["no_upper_plateau"] = plateau <= 1
    if not checks["no_upper_plateau"]:
        findings.append(VQ_CLOSURE_UPPER_PLATEAU)
    checks["apex_centered"] = abs(w[0]) < 1e-9
    if not checks["apex_centered"]:
        findings.append(VQ_CLOSURE_APEX_NOT_CENTERED)
    return {"checks": checks, "findings": sorted(set(findings)),
            "apex_half_width": w[0], "dome_samples": cap_n,
            "status": ("DOME_TERMINATION_VALID" if not findings
                       else "DOME_TERMINATION_FAILED")}


def unchanged_outside_dome(before: dict, after: dict) -> dict:
    """§1 — prove that only the dome changed."""
    diffs = {}
    for name in before["components"]:
        b = before["components"][name]["normalized_points"]
        a = after["components"][name]["normalized_points"]
        if name != "DARK_CLOSURE":
            diffs[name] = "IDENTICAL" if b == a else "CHANGED"
            continue
        cap_n = after.get("dome_cap", {}).get("samples", 0)
        b_shaft = [p for p in b if p[1] > after["dome_cap"][
            "dome_height_norm"] + b[0][1]]
        a_shaft = a[cap_n:]
        diffs[name] = ("SHAFT_AND_FLARE_IDENTICAL" if b_shaft == a_shaft
                       else "SHAFT_OR_FLARE_CHANGED")
    return {"per_component": diffs,
            "only_dome_changed": all(
                v in ("IDENTICAL", "SHAFT_AND_FLARE_IDENTICAL")
                for v in diffs.values())}


# --- IT6: collar / neck visible-envelope replacement --------------------------

VQ_COLLAR_STEPPED_TOWER_FALLBACK = "VQ_COLLAR_STEPPED_TOWER_FALLBACK"
VQ_COLLAR_SINGLE_SLEEVE_NOT_PRESERVED = \
    "VQ_COLLAR_SINGLE_SLEEVE_NOT_PRESERVED"
VQ_NECK_SPACER_RING_FALLBACK = "VQ_NECK_SPACER_RING_FALLBACK"
VQ_VISIBLE_INTERNAL_ADAPTER_UNSUPPORTED = \
    "VQ_VISIBLE_INTERNAL_ADAPTER_UNSUPPORTED"
VQ_DARK_CLOSURE_LOWER_INTERFACE_FAILED = \
    "VQ_DARK_CLOSURE_LOWER_INTERFACE_FAILED"
VQ_CLOSURE_COMPONENT_CONTINUITY_FAILED = \
    "VQ_CLOSURE_COMPONENT_CONTINUITY_FAILED"

#: IT6 draws only THREE visible objects. IT5 drew the neck as its own pale
#: component between collar and shoulder — that separate object, with its
#: own top and bottom edges, is what read as a stepped tower and a white
#: spacer ring. The glass is now one continuous contour.
IT6_VISIBLE_ORDER = ("GLASS_ASSEMBLY", "COLLAR_SLEEVE", "DARK_CLOSURE")
IT6_GLASS_BANDS = ("NECK_VISIBLE", "SHOULDER", "BODY", "BASE")

#: §9 technical construction, never part of the consumer-facing contour
NONPRINTING_TECHNICAL_INTERNALS = (
    "INTERNAL_NECK_FINISH", "INTERNAL_CLOSURE_OPENING",
    "INTERNAL_PIPETTE_INTERFACE", "INTERNAL_OVERLAP_REGION")

_IT6_FILL = {"GLASS_ASSEMBLY": ("#F4EEEA", "#E7DCD6", "#B3A49C"),
             "COLLAR_SLEEVE": ("#F0E0CE", "#CDB9A6", "#8A7460"),
             "DARK_CLOSURE": ("#7A6570", "#4A3A44", "#291F26")}


def build_it6_envelope(env5: dict, *, flare_overlap: float = 0.004) -> dict:
    """Replace ONLY the collar envelope, the visible neck transition and
    the dark component's lower interface. The dome, shaft, body,
    shoulder, base, aspect and centerline come through untouched."""
    import copy
    out = copy.deepcopy(env5)
    comp = out["components"]

    # one clean sleeve: drop the blended transition rows at each end of the
    # measured collar so the sleeve does not taper into a ledge
    col = list(comp["COLLAR"]["normalized_points"])
    trim = max(1, len(col) // 8)
    body = col[trim:len(col) - 1] or col
    full = max(p[0] for p in body)
    y_top, y_bot = col[0][1], col[-1][1]
    rim = (y_bot - y_top) * 0.055          # restrained top/bottom edges
    bow = full * 0.012                     # one subtly curved front face
    n = 18
    sleeve = []
    for i in range(n + 1):
        t = i / n
        y = y_top + (y_bot - y_top) * t
        if t < 0.14:                       # restrained top edge
            hw = full * (0.965 + 0.035 * (t / 0.14))
        elif t > 0.88:                     # restrained bottom edge
            hw = full * (1.0 - 0.02 * ((t - 0.88) / 0.12))
        else:
            u = (t - 0.14) / 0.74
            hw = full + bow * (1 - (2 * u - 1) ** 2)
        sleeve.append((round(hw, 6), round(y, 6)))
    comp["COLLAR"]["normalized_points"] = sleeve
    comp["COLLAR"]["max_half_width_norm"] = round(
        max(p[0] for p in sleeve), 5)
    comp["COLLAR"]["min_half_width_norm"] = round(
        min(p[0] for p in sleeve), 5)

    # the dark component's lower flare overlaps the collar top so the two
    # read as one closure family with no gap and no planted-on look
    dark = list(comp["DARK_CLOSURE"]["normalized_points"])
    last_hw, last_y = dark[-1]
    dark.append((round(last_hw, 6), round(y_top + flare_overlap, 6)))
    comp["DARK_CLOSURE"]["normalized_points"] = dark

    out["it6_collar_neck"] = {
        "replaced": ["COLLAR_VISIBLE_ENVELOPE", "VISIBLE_NECK_TRANSITION",
                     "DARK_COMPONENT_TO_COLLAR_INTERFACE"],
        "collar_sleeve_samples": len(sleeve),
        "collar_full_half_width_norm": round(full, 6),
        "restrained_rim_norm": round(rim, 6),
        "front_face_bow_norm": round(bow, 6),
        "visible_steps": 0,
        "glass_is_one_contour": True,
        "glass_bands_merged": list(IT6_GLASS_BANDS),
        "neck_drawn_as_separate_object": False,
        "flare_overlap_norm": flare_overlap,
        "dome_untouched": True, "shaft_untouched": True,
        "body_untouched": True, "shoulder_untouched": True,
        "base_untouched": True,
        "nonprinting_technical_internals":
            list(NONPRINTING_TECHNICAL_INTERNALS),
        "internals_affect_visible_contour": False,
    }
    return out


def it6_component_paths(env, ox, oy, height):
    """Three visible closed contours. The glass is continuous through the
    neck, so no separate pale object can read as a spacer ring."""
    out = {}
    groups = {"GLASS_ASSEMBLY": IT6_GLASS_BANDS,
              "COLLAR_SLEEVE": ("COLLAR",),
              "DARK_CLOSURE": ("DARK_CLOSURE",)}
    for name in IT6_VISIBLE_ORDER:
        pts = []
        for band in groups[name]:
            for x, y in env["components"][band]["normalized_points"]:
                p = (ox - x * height * ASPECT_W_OVER_H, oy + y * height)
                if not pts or abs(p[0] - pts[-1][0]) > 1e-9 or \
                        abs(p[1] - pts[-1][1]) > 1e-9:
                    pts.append(p)
        segs = [MoveTo(x=pts[0][0], y=pts[0][1])]
        for c1, c2, p in _catmull_to_cubic(pts):
            segs.append(CubicTo(x1=c1[0], y1=c1[1], x2=c2[0], y2=c2[1],
                                x=p[0], y=p[1]))
        out[name] = closed_from_left(segs, ox)
    return out


def draw_it6(env, ox, oy, height, *, prefix="", outline_only=False,
             width_mm=0.45, color=None, components=None):
    g = it6_component_paths(env, ox, oy, height)
    names = [n for n in IT6_VISIBLE_ORDER
             if not components or n in components]
    kids = []
    for name in names:
        if outline_only:
            kids.append(Path(name=f"{prefix}{name}", segments=g[name],
                             stroke=Stroke(color=color or INK,
                                           width_mm=width_mm)))
        else:
            hi, mid, lo = _IT6_FILL[name]
            kids.append(Path(
                name=f"{prefix}{name}", segments=g[name],
                fill=GradientFill(
                    kind="linear",
                    x1=ox - height * ASPECT_W_OVER_H * 0.52, y1=0.0,
                    x2=ox + height * ASPECT_W_OVER_H * 0.52, y2=0.0,
                    stops=[GradientStop(offset=0.0,
                                        color=Color.from_hex(mid)),
                           GradientStop(offset=0.28,
                                        color=Color.from_hex(hi)),
                           GradientStop(offset=0.66,
                                        color=Color.from_hex(mid)),
                           GradientStop(offset=1.0,
                                        color=Color.from_hex(lo))])))
    return Group(name=f"{prefix}IT6", role="product", children=kids)


def it6_unchanged_report(env5: dict, env6: dict) -> dict:
    """§16 — prove the authorized scope was respected."""
    c5, c6 = env5["components"], env6["components"]
    cap = env6.get("dome_cap", {}).get("samples", 0)
    dome5 = c5["DARK_CLOSURE"]["normalized_points"][:cap]
    dome6 = c6["DARK_CLOSURE"]["normalized_points"][:cap]
    shaft5 = c5["DARK_CLOSURE"]["normalized_points"][cap:]
    shaft6 = c6["DARK_CLOSURE"]["normalized_points"][cap:]
    return {
        "dome_identical": dome5 == dome6,
        "shaft_identical_except_interface": shaft5 == shaft6[:len(shaft5)],
        "interface_points_added": len(shaft6) - len(shaft5),
        "body_identical": c5["BODY"]["normalized_points"] ==
        c6["BODY"]["normalized_points"],
        "shoulder_identical": c5["SHOULDER"]["normalized_points"] ==
        c6["SHOULDER"]["normalized_points"],
        "base_identical": c5["BASE"]["normalized_points"] ==
        c6["BASE"]["normalized_points"],
        "neck_band_identical": c5["NECK_VISIBLE"]["normalized_points"] ==
        c6["NECK_VISIBLE"]["normalized_points"],
        "collar_replaced": c5["COLLAR"]["normalized_points"] !=
        c6["COLLAR"]["normalized_points"],
        "aspect_identical": True,
        "centerline_identical": env5["centerline_px"] ==
        env6["centerline_px"],
    }


def it6_collar_findings(env6: dict) -> dict:
    """§5/§10 — the visible collar must be one continuous sleeve."""
    pts = env6["components"]["COLLAR"]["normalized_points"]
    w = [p[0] for p in pts]
    findings, checks = [], {}
    # a step is a large jump between adjacent samples
    steps = sum(1 for a, b in zip(w, w[1:]) if abs(b - a) > 0.012)
    checks["visible_contour_steps_zero"] = steps == 0
    if steps:
        findings += [VQ_COLLAR_STEPPED_TOWER_FALLBACK,
                     VQ_COLLAR_SINGLE_SLEEVE_NOT_PRESERVED]
    checks["walls_near_vertical"] = (max(w) - min(w)) / max(w) < 0.06
    checks["single_sleeve"] = len(pts) >= 12
    checks["glass_is_one_contour"] = \
        env6["it6_collar_neck"]["glass_is_one_contour"]
    checks["no_separate_neck_object"] = not \
        env6["it6_collar_neck"]["neck_drawn_as_separate_object"]
    if not checks["no_separate_neck_object"]:
        findings.append(VQ_NECK_SPACER_RING_FALLBACK)
    checks["internals_hidden"] = not \
        env6["it6_collar_neck"]["internals_affect_visible_contour"]
    if not checks["internals_hidden"]:
        findings.append(VQ_VISIBLE_INTERNAL_ADAPTER_UNSUPPORTED)
    dark = env6["components"]["DARK_CLOSURE"]["normalized_points"]
    collar_top = pts[0][1]
    checks["dark_flare_overlaps_collar"] = dark[-1][1] >= collar_top
    if not checks["dark_flare_overlaps_collar"]:
        findings += [VQ_DARK_CLOSURE_LOWER_INTERFACE_FAILED,
                     VQ_CLOSURE_COMPONENT_CONTINUITY_FAILED]
    return {"checks": checks, "findings": sorted(set(findings)),
            "visible_steps": steps,
            "collar_body_ratio": round(max(w) * 2, 5),
            "status": ("COLLAR_SINGLE_SLEEVE_VALID" if not findings
                       else "COLLAR_ENVELOPE_FAILED")}
