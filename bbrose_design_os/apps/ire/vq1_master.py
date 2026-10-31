"""VQ-1-MASTER — reference-contour-driven structural fit.

Every prior VQ-1 candidate was built from a parameter model and then
compared to the reference. That is backwards, and it is why each
iteration fixed one symptom while preserving a wrong global form. Here
the reference edge IS the model: contours are extracted from image #97 in
SOURCE pixel space, cubic Bézier segments are fitted to those samples
with a measured residual, and the render is compared back to the source
crop. The reference comparison — not the internal parameter model — is
the fidelity authority (§16).

Only four visible objects are permitted (§9). Hidden mechanism is never
rendered. Concept-visual authority only: nothing here is manufacturable,
tooling-ready or supplier-confirmed.
"""
from __future__ import annotations

from apps.ire.corr_mirror import closed_from_left
from apps.ire.graph import (Color, CubicTo, GradientFill, GradientStop,
                            Group, MoveTo, Path, Stroke)

MASTER_SCHEMA = "vq1_master_structural_fit/1.0"
INK = Color.from_hex("#2A2426")

#: §9 the ONLY visible structural objects
VISIBLE_OBJECTS = ("VISIBLE_DARK_CLOSURE_ENVELOPE", "SINGLE_METAL_COLLAR_SLEEVE",
                   "MINIMAL_GLASS_NECK_TRANSITION",
                   "BOTTLE_SHOULDER_AND_BODY")
FORBIDDEN_VISIBLE = ("spacer ring", "washer", "gasket", "adapter block",
                     "internal plug", "rectangular opening", "thread stack",
                     "extra collar tier", "lower collar ledge",
                     "upper collar ledge", "white horizontal band")
NONPRINTING_TECHNICAL_INTERNALS = (
    "INTERNAL_NECK_FINISH", "INTERNAL_CLOSURE_OPENING",
    "INTERNAL_PIPETTE_INTERFACE", "INTERNAL_OVERLAP_REGION")

#: §4 approved consumer-visible semantics
APPROVED_SEMANTIC = ("VISIBLE_DARK_CLOSURE_ENVELOPE_WITH_ROUNDED_DOME,"
                     "LONG_NEAR_CONSTANT_WIDTH_SHAFT,"
                     "AND_SHORT_FLARED_SKIRT")
INTERNAL_MECHANISM = "UNRESOLVED / HIDDEN"

#: measurement frame — SOURCE image pixel space
CENTERLINE_PX = 666.5
ASSEMBLY_SPAN_PX = (292, 1348)
BODY_WIDTH_PX = 343.0
ASPECT_W_OVER_H = BODY_WIDTH_PX / (ASSEMBLY_SPAN_PX[1] - ASSEMBLY_SPAN_PX[0])

#: component bands set INSIDE each part so no boundary row blends two widths
#: bands OVERLAP at every interface. M1 left a 12 px gap between the dark
#: closure and the collar, and the emitted silhouette dipped through it —
#: the junction scored worst for exactly that reason. Overlapping means the
#: union of the drawn objects covers every row continuously.
#: M4 shared contact manifold: the components MEET at one exact row and
#: never overlap. The reference handoff is not a step — it is a 13-row ramp
#: (69.5 -> 108.5 px) that is the collar rim. Overlapping bands flattened
#: that ramp and quantized the transition; the collar contour now owns it.
CONTACT_ROW_PX = 495
BANDS = {
    "DARK_CLOSURE": (292, CONTACT_ROW_PX),
    "COLLAR": (CONTACT_ROW_PX, 676),
    "GLASS": (664, 1348),          # neck + shoulder + body + base, continuous
}

#: MODEL-2 three-surface junction. M3 flattened the collar rim by
#: overlapping two bands; M4 collapsed it to one contact row and
#: overshot. The rim is neither component's edge — it is a surface of the
#: collar assembly, so it gets its own locally fitted patch between two
#: exact seams. Visible MECHANICAL objects stay four; visible SURFACES
#: may be more.
SEAM_A_PX = 495          # dark flare terminal <-> rim
SEAM_B_PX = 508          # rim <-> collar cylindrical wall
RIM_BANDS = {
    "DARK_CLOSURE": (292, SEAM_A_PX),
    "COLLAR_TOP_RIM": (SEAM_A_PX, SEAM_B_PX),
    "COLLAR": (SEAM_B_PX, 676),
    "GLASS": (664, 1348),
}
RIM_DRAW_ORDER = ("GLASS", "COLLAR", "COLLAR_TOP_RIM", "DARK_CLOSURE")
#: the rim is a SURFACE of the collar assembly, never a mechanical object
COLLAR_ASSEMBLY_SURFACES = ("COLLAR_TOP_RIM_TRANSITION_SURFACE",
                            "COLLAR_CYLINDRICAL_WALL_SURFACE",
                            "COLLAR_BOTTOM_RIM_SURFACE")
RIM_SURFACE_OWNER = "SINGLE_METAL_COLLAR_ASSEMBLY"
VISIBLE_MECHANICAL_OBJECT_COUNT = 4


def build_rim_fit(half_width_px: dict, *, tol: float = 0.35) -> dict:
    """Three-surface fit. The rim patch is fitted to its own 13 source
    rows at a tighter tolerance than the long components, because a local
    ramp needs a local fit — that is the whole point of the model."""
    fits = {}
    for name, band in RIM_BANDS.items():
        step = 1 if name == "COLLAR_TOP_RIM" else 3
        s = extract_component_samples(half_width_px, band, step=step)
        fits[name] = {**fit_cubics(s, tol=tol), "band_px": list(band),
                      "samples_px": [[round(a, 3), b] for a, b in s]}
    return {"schema_version": "vq1_master_rim_model/2.0",
            "measurement_space": "SOURCE_IMAGE_PIXELS",
            "seam_a_px": SEAM_A_PX, "seam_b_px": SEAM_B_PX,
            "fits": fits,
            "collar_assembly_surfaces": list(COLLAR_ASSEMBLY_SURFACES),
            "rim_surface_owner": RIM_SURFACE_OWNER,
            "rim_is_fifth_mechanical_object": False,
            "visible_mechanical_object_count":
                VISIBLE_MECHANICAL_OBJECT_COUNT,
            "fidelity_authority": "REFERENCE_COMPARISON_NOT_PARAMETER_MODEL",
            "authority": "CONCEPT_VISUAL_GEOMETRY_ONLY",
            "is_physical_dimension": False, "manufacturable": False}


def draw_rim_model(fit_record, ox, oy, height, *, prefix="",
                   outline_only=False, width_mm=0.45, color=None,
                   only=None):
    fill = dict(_FILL)
    fill["COLLAR_TOP_RIM"] = _FILL["COLLAR"]   # one collar material read
    kids = []
    for name in RIM_DRAW_ORDER:
        if only and name not in only:
            continue
        f = fit_record["fits"].get(name)
        if not f:
            continue
        segs = component_path(f, ox, oy, height)
        if not segs:
            continue
        if outline_only:
            kids.append(Path(name=f"{prefix}{name}", segments=segs,
                             stroke=Stroke(color=color or INK,
                                           width_mm=width_mm)))
        else:
            hi, mid, lo = fill[name]
            kids.append(Path(
                name=f"{prefix}{name}", segments=segs,
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
    return Group(name=f"{prefix}RimModel", role="product", children=kids)

#: §10-§14 deterministic gates
GATES = {
    "apex_centred_px": 1.0, "shaft_variation": 0.02,
    "flare_mirror_px": 1.0, "contact_slope_deg": 0.5,
    "dark_body_ratio_err": 0.015, "flare_body_ratio_err": 0.015,
    "shaft_run_err": 0.03, "collar_body_ratio_err": 0.015,
    "collar_hw_err": 0.020, "collar_width_variation": 0.015,
    "collar_steps": 0, "collar_iou": 0.97, "collar_mean": 0.010,
    "collar_p95": 0.025, "collar_max": 0.045, "junction_max": 0.045,
    "neck_height_err_px": 2.0, "shoulder_iou": 0.95,
    "shoulder_rise_err": 0.015, "centerline_align_px": 1.0,
    "visible_object_count": 4,
}


# --- §16 contour fitting -------------------------------------------------------

#: v1 fitter defects, found in VQ-1-MASTER-CLOSE-1 and corrected for FUTURE
#: work only in ``apps/ire/contour_fit.py``. v1 stays byte-stable so every
#: historical artifact and hash reproduces exactly.
LEGACY_FIT_SCHEMA = "vq_contour_fit/1.0"
LEGACY_FIT_DEFECTS = ("VQ_FIT_CUBICS_COARSENING_BYPASSES_TOLERANCE",
                      "VQ_FITTER_SEGMENT_CAP_FAILS_TO_PRESERVE_ERROR_BOUND")
LEGACY_FIT_STATE = "LEGACY_REPRODUCTION_ONLY_DEFECT_DISCLOSED"
CORRECTED_FITTER = "apps.ire.contour_fit.fit_contour"


def fit_cubics(samples, *, tol: float = 0.6, max_seg: int = 48) -> dict:
    """Fit a chain of cubic Béziers to (x, y) reference edge samples and
    MEASURE the residual. Segments are split until every sample is within
    ``tol`` source pixels, so the fit is driven by the reference, not by a
    chosen segment count.

    LEGACY — DEFECT DISCLOSED, DO NOT USE FOR NEW RECONSTRUCTIONS.
    When the adaptive split exceeds ``max_seg`` the coarsening branch below
    replaces the tolerance-guaranteed result with uniform chunks and does NOT
    re-enforce ``tol``; the returned ``residual_max`` is then unbounded rather
    than tolerance-capped. This is left exactly as-is on purpose so frozen
    candidates (notably M3) reproduce byte-identically. New work must use
    ``apps.ire.contour_fit.fit_contour``, which enforces the tolerance or
    fails closed with ``VQ_VECTOR_FIT_TOLERANCE_NOT_ACHIEVED``.
    """
    pts = [tuple(p) for p in samples]
    if len(pts) < 3:
        return {"segments": [], "residual_max": 0.0, "residual_mean": 0.0,
                "segment_count": 0, "sample_count": len(pts)}

    def bez(p0, c1, c2, p3, t):
        u = 1 - t
        return (u ** 3 * p0[0] + 3 * u * u * t * c1[0]
                + 3 * u * t * t * c2[0] + t ** 3 * p3[0],
                u ** 3 * p0[1] + 3 * u * u * t * c1[1]
                + 3 * u * t * t * c2[1] + t ** 3 * p3[1])

    def fit_one(seg):
        p0, p3 = seg[0], seg[-1]
        n = len(seg)
        # Catmull-Rom style tangents scaled to the chord
        c1 = (p0[0] + (seg[min(1, n - 1)][0] - p0[0]) * 1.2,
              p0[1] + (seg[min(1, n - 1)][1] - p0[1]) * 1.2)
        c2 = (p3[0] + (seg[max(n - 2, 0)][0] - p3[0]) * 1.2,
              p3[1] + (seg[max(n - 2, 0)][1] - p3[1]) * 1.2)
        res = 0.0
        for i, s in enumerate(seg):
            t = i / (n - 1)
            b = bez(p0, c1, c2, p3, t)
            res = max(res, ((b[0] - s[0]) ** 2 + (b[1] - s[1]) ** 2) ** 0.5)
        return (c1, c2, p3), res

    def split(seg, depth=0):
        (c1, c2, p3), res = fit_one(seg)
        if (res <= tol or len(seg) <= 4 or depth > 8):
            return [((c1, c2, p3), res)]
        mid = len(seg) // 2
        return split(seg[:mid + 1], depth + 1) + split(seg[mid:], depth + 1)

    out = split(pts)
    if len(out) > max_seg:                       # coarsen rather than explode
        step = max(1, len(pts) // max_seg)
        chunks = [pts[i:i + step + 1] for i in range(0, len(pts) - 1, step)]
        out = [fit_one(c) for c in chunks if len(c) >= 2]
    segs = [o[0] for o in out]
    residuals = [o[1] for o in out]
    return {"segments": segs, "start": pts[0],
            "residual_max": round(max(residuals), 4),
            "residual_mean": round(sum(residuals) / len(residuals), 4),
            "segment_count": len(segs), "sample_count": len(pts)}


def extract_component_samples(half_width_px: dict, band: tuple, *,
                              step: int = 3) -> list:
    """Reference edge samples for one band, in SOURCE pixel space:
    (half_width_px, y_px). Measurement never happens on an upscaled copy."""
    y0, y1 = band
    out = []
    for y in range(y0, y1 + 1, step):
        if y in half_width_px:
            out.append((half_width_px[y], float(y)))
    return out


def build_fit(half_width_px: dict, *, tol: float = 0.6) -> dict:
    """Fit all three visible contour groups to the reference edge."""
    fits = {}
    for name, band in BANDS.items():
        s = extract_component_samples(half_width_px, band)
        fits[name] = {**fit_cubics(s, tol=tol), "band_px": list(band),
                      "samples_px": [[round(a, 3), b] for a, b in s]}
    return {"schema_version": MASTER_SCHEMA,
            "measurement_space": "SOURCE_IMAGE_PIXELS",
            "centerline_px": CENTERLINE_PX,
            "assembly_span_px": list(ASSEMBLY_SPAN_PX),
            "body_width_px": BODY_WIDTH_PX,
            "fits": fits,
            "fidelity_authority": "REFERENCE_COMPARISON_NOT_PARAMETER_MODEL",
            "authority": "CONCEPT_VISUAL_PIXEL_EVIDENCE",
            "is_physical_dimension": False,
            "visible_objects": list(VISIBLE_OBJECTS),
            "approved_semantic": APPROVED_SEMANTIC,
            "internal_mechanism": INTERNAL_MECHANISM,
            "nonprinting_internals": list(NONPRINTING_TECHNICAL_INTERNALS)}


# --- rendering from the fitted contour ----------------------------------------

def _to_page(x_px, y_px, ox, oy, height):
    """SOURCE pixel space -> page mm, preserving the measured aspect."""
    span = ASSEMBLY_SPAN_PX[1] - ASSEMBLY_SPAN_PX[0]
    k = height / span
    return (ox - x_px * k, oy + (y_px - ASSEMBLY_SPAN_PX[0]) * k)


def component_path(fit: dict, ox, oy, height):
    f = fit
    if not f["segments"]:
        return []
    p0 = _to_page(f["start"][0], f["start"][1], ox, oy, height)
    segs = [MoveTo(x=p0[0], y=p0[1])]
    for (c1, c2, p3) in f["segments"]:
        a = _to_page(c1[0], c1[1], ox, oy, height)
        b = _to_page(c2[0], c2[1], ox, oy, height)
        c = _to_page(p3[0], p3[1], ox, oy, height)
        segs.append(CubicTo(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                            x=c[0], y=c[1]))
    return closed_from_left(segs, ox)


_FILL = {"GLASS": ("#F4EEEA", "#E7DCD6", "#B3A49C"),
         "COLLAR": ("#F0E0CE", "#CDB9A6", "#8A7460"),
         "DARK_CLOSURE": ("#7A6570", "#4A3A44", "#291F26")}
DRAW_ORDER = ("GLASS", "COLLAR", "DARK_CLOSURE")


def draw_master(fit_record, ox, oy, height, *, prefix="",
                outline_only=False, width_mm=0.45, color=None,
                only=None):
    kids = []
    for name in DRAW_ORDER:
        if only and name not in only:
            continue
        segs = component_path(fit_record["fits"][name], ox, oy, height)
        if not segs:
            continue
        if outline_only:
            kids.append(Path(name=f"{prefix}{name}", segments=segs,
                             stroke=Stroke(color=color or INK,
                                           width_mm=width_mm)))
        else:
            hi, mid, lo = _FILL[name]
            kids.append(Path(
                name=f"{prefix}{name}", segments=segs,
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
    return Group(name=f"{prefix}Master", role="product", children=kids)


def render_page_width(height: float) -> float:
    return height * ASPECT_W_OVER_H * 1.5
