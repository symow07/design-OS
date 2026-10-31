"""VQ-1-CORR-5 — closure-first structural reset.

CORR-4 was rejected because the *canonical geometry itself* did not
preserve reference #97 (the renderer was faithful to a wrong shape). So
CORR-5 stops generating complete bottles first: three isolated
subfixtures (bulb profile, collar+neck, shoulder+body) must each satisfy
deterministic constraints before ``assembly_gate`` will release the full
assembly. A failed closure can no longer hide inside a composition.

Geometry comes from vq1_human_calibrated_reference_contour/1.1, which was
re-read off three LARGE gridded crops of reference #97 (closure,
shoulder+neck, body+base) rather than the whole product at thumbnail
scale. That re-read is what corrected v1.0's two structural errors: the
collar is 52% of body width (v1.0 measured 61% by including the highlight
bloom) and the shoulder rise is only 50 px (v1.0 used a rise ~65% too
large, which the human saw as an oversized dome).

CONCEPT_ONLY authority; no production measurement derives from it. The
best automated state is always PASSES_STRUCTURAL_FORM_PENDING_HUMAN_REVIEW
— automated path equality never overrides a human visual rejection.
"""
from __future__ import annotations

import math

from apps.ire.corr_mirror import closed_from_left, mirrored_return  # noqa
from apps.ire.graph import (ClosePath, Color, CubicTo, GradientFill,
                            GradientStop, Group, LineTo, MoveTo, Path,
                            Stroke)

#: VQ-1-RESET-1 §4 — this generator is FROZEN; it produced a fixture a
#: human rejected. Rejected regression input only; never a new candidate.
GENERATOR_STATE = "LEGACY_REJECTED_STRUCTURAL_GENERATOR"
MAY_EMIT_NEW_CANDIDATE = False

INK = Color.from_hex("#2A2426")
REFERENCE_IMAGE = "GeneratedImage#97 task_52_var_2_reALblg.png (1024x1536)"
CONTOUR_VERSION = "vq1_human_calibrated_reference_contour/1.1"

#: measured off the large crops — px in source-image space
REF_CENTERLINE_PX = 666.5
REF_TOP_PX, REF_BOTTOM_PX = 292.0, 1348.0
REF_BODY_WIDTH_PX = 343.0
PX_PER_MM = REF_BODY_WIDTH_PX / 31.3

#: §4 explicit structural landmarks, each visible on a large gridded crop
REF_LANDMARKS = {
    # name: (y_px, half_width_px, crop)
    "bulb_top": (292, 0, "closure"),
    "bulb_dome_upper": (330, 36, "closure"),
    "bulb_dome_lower": (372, 47, "closure"),
    "bulb_maximum_width": (415, 48, "closure"),
    "bulb_upper_taper": (452, 45, "closure"),
    "bulb_lower_width": (470, 40, "closure"),
    "bulb_insertion_stem": (488, 22, "closure"),
    "collar_top": (492, 89, "closure"),
    "collar_bottom": (655, 89, "closure"),
    "neck_visible": (662, 52, "shoulder_neck"),
    "shoulder_start": (680, 107, "shoulder_neck"),
    "shoulder_apex": (705, 148, "shoulder_neck"),
    "body_wall_top": (730, 171, "shoulder_neck"),
    "body_wall_bottom": (1310, 171, "body_base"),
    "base_curve": (1338, 150, "body_base"),
    "base_bottom": (1348, 0, "body_base"),
}

#: §4 crops the landmarks were read from (committed alongside the record)
REF_CROPS = {
    "closure": {"box_px": [540, 270, 800, 700], "zoom": 3,
                "grid_step_px": 20},
    "shoulder_neck": {"box_px": [470, 610, 870, 790], "zoom": 3,
                      "grid_step_px": 20},
    "body_base": {"box_px": [470, 700, 870, 1370], "zoom": 2,
                  "grid_step_px": 40},
}

#: mm — every ratio below is inside the §5/§7/§10 reference targets
CORR5_DIMS = {
    "body_diameter": 31.3,          # 343 px
    "body_height": 61.0,            # shoulder start -> base bottom
    "shoulder_rise": 4.6,           # 50 px — calibrated, deliberately small
    "base_curve_depth": 3.5,
    "neck_diameter": 9.0,           # 28.8% of body, 57% of collar
    "visible_neck": 1.6,            # small glass transition only
    "collar_diameter": 15.9,        # 50.8% of body   (target 45-55%)
    "collar_height": 12.1,          # 76% of width    (target 65-85%)
    "collar_rim": 0.55,
    "collar_bow": 0.22,
    "bulb_max_width": 8.8,          # 28.1% of body   (target 25-32%)
    "bulb_stem_width": 3.9,         # 12.5% of body   (target 10-15%)
    "bulb_body_height": 15.0,
    "bulb_stem_visible": 3.2,
    "bulb_insertion": 2.6,          # stem depth inside the collar
    "bulb_max_at": 0.44,
    "bulb_dome_start": 0.76,
    "bulb_dome_width": 0.47,
    "bulb_narrowing_exp": 1.5,
    "bulb_dome_n": 2.0,
}

#: near-orthographic — measured 5 px of rim bow over an 89 px half-width
PROJECTION5 = {"mode": "weak_perspective_front", "ellipse_depth_ratio": 0.06,
               "centerline": "shared", "scale": "shared",
               "vertical_axis": "shared"}

BULB_FAILURES = ("VQ_BULB_TOMBSTONE_DOME", "VQ_BULB_POLYGONAL_CROWN",
                 "VQ_BULB_FLAT_BASE", "VQ_BULB_INSERTION_STEM_MISSING",
                 "VQ_BULB_UPPER_MIDDLE_TOO_WIDE",
                 "VQ_BULB_REFERENCE_PROFILE_FAILED")
SHOULDER_FAILURES = ("VQ_SHOULDER_DOME_OVERSIZED",
                     "VQ_SHOULDER_RISE_EXCESSIVE",
                     "VQ_SHOULDER_REFERENCE_PROFILE_FAILED")


def calibrated_landmarks() -> list[dict]:
    """§4 — normalized landmarks with left/right pairs derived by exact
    reflection about the shared centerline."""
    span = REF_BOTTOM_PX - REF_TOP_PX
    out = []
    for name, (y, hw, crop) in REF_LANDMARKS.items():
        out.append({
            "name": name, "crop": crop,
            "y_px": y, "half_width_px": hw,
            "left_px": REF_CENTERLINE_PX - hw,
            "right_px": REF_CENTERLINE_PX + hw,
            "y_norm": round((y - REF_TOP_PX) / span, 4),
            "half_width_norm": round(hw / span, 4),
            "width_frac_of_body": round(2 * hw / REF_BODY_WIDTH_PX, 4),
            "tolerance_norm": 0.010,
            "status": "MANUALLY_CALIBRATED_ON_LARGE_GRIDDED_CROP",
            "human_confirmed": False,
            "source_image": REFERENCE_IMAGE,
            "authority": "CONCEPT_ONLY_NOT_PRODUCTION",
        })
    out.append({"name": "shared_centerline", "crop": "all",
                "x_px": REF_CENTERLINE_PX, "y_px": None,
                "status": "MANUALLY_CALIBRATED_ON_LARGE_GRIDDED_CROP",
                "human_confirmed": False, "tolerance_norm": 0.004,
                "source_image": REFERENCE_IMAGE,
                "authority": "CONCEPT_ONLY_NOT_PRODUCTION"})
    return out


# --- bulb: ONE canonical half-profile ---------------------------------------

def bulb_total_height(d: dict) -> float:
    return (d["bulb_insertion"] + d["bulb_stem_visible"]
            + d["bulb_body_height"])


def bulb_half_width(t: float, d: dict) -> float:
    """Half-width in mm at height fraction t (0 = stem bottom inside the
    collar, 1 = dome apex). Narrow stem -> rapid smooth widening ->
    maximum in the lower-middle -> slimmer upper-middle -> narrow dome."""
    max_hw = d["bulb_max_width"] / 2
    stem_hw = d["bulb_stem_width"] / 2
    H = bulb_total_height(d)
    t_stem = (d["bulb_insertion"] + d["bulb_stem_visible"]) / H
    t_max, t_dome = d["bulb_max_at"], d["bulb_dome_start"]
    w_dome = d["bulb_dome_width"]
    if t <= t_stem:
        # cylindrical stem, softly rounded at the very bottom so the base
        # is never a flat horizontal edge
        r = min(0.06, t_stem * 0.25)
        if t < r:
            return stem_hw * math.sin(math.pi / 2 * (t / r)) ** 0.55
        return stem_hw
    if t <= t_max:                       # rapid but smooth widening
        u = (t - t_stem) / (t_max - t_stem)
        smooth = u * u * (3 - 2 * u)
        return stem_hw + (max_hw - stem_hw) * smooth
    if t <= t_dome:                      # visibly slimmer upper-middle
        u = (t - t_max) / (t_dome - t_max)
        return max_hw * (1 - (1 - w_dome) * u ** d["bulb_narrowing_exp"])
    u = (t - t_dome) / (1 - t_dome)      # narrow, smoothly rounded dome
    n = d["bulb_dome_n"]
    return max(0.0, max_hw * w_dome * (1 - u ** n) ** (1 / n))


def bulb_samples(d: dict, n: int = 31) -> list[dict]:
    H = bulb_total_height(d)
    out = []
    for i in range(n):
        t = i / (n - 1)
        hw = bulb_half_width(t, d)
        out.append({"t": round(t, 4), "half_width_mm": round(hw, 4),
                    "width_frac": round(hw / (d["bulb_max_width"] / 2), 4),
                    "width_frac_of_body": round(
                        2 * hw / d["body_diameter"], 4),
                    "y_mm_from_stem_base": round(t * H, 4)})
    return out


# --- canonical geometry ------------------------------------------------------

def layout(d: dict) -> dict:
    y_ct = d["bulb_insertion"] + d["bulb_stem_visible"] + \
        d["bulb_body_height"] - d["bulb_insertion"]      # collar top
    y_cb = y_ct + d["collar_height"]
    y_bt = y_cb + d["visible_neck"]                      # shoulder start
    y_wall = y_bt + d["shoulder_rise"]
    y_bottom = y_bt + d["body_height"]
    return {"y_bulb_apex": 0.0, "y_collar_top": y_ct, "y_collar_bot": y_cb,
            "y_body_top": y_bt, "y_wall_top": y_wall,
            "y_base_start": y_bottom - d["base_curve_depth"],
            "y_bottom": y_bottom, "total_height": y_bottom}


def canonical_geometry(d: dict, ox: float, oy: float, s: float,
                       components=None) -> dict:
    lay = layout(d)
    cx = d["body_diameter"] / 2
    er = PROJECTION5["ellipse_depth_ratio"]
    K = 0.5523

    def X(x):
        return ox + x * s

    def Y(y):
        return oy + y * s

    XC = X(cx)
    out = {}

    # BODY — shallow calibrated shoulder, parallel walls, integrated base
    bw2, nw2 = cx, d["neck_diameter"] / 2
    y_bt, y_w = lay["y_body_top"], lay["y_wall_top"]
    y_bs, y_bot = lay["y_base_start"], lay["y_bottom"]
    body_left = [
        MoveTo(x=X(cx - nw2), y=Y(y_bt)),
        CubicTo(x1=X(cx - nw2 - (bw2 - nw2) * 0.62), y1=Y(y_bt),
                x2=X(cx - bw2), y2=Y(y_w - d["shoulder_rise"] * 0.38),
                x=X(cx - bw2), y=Y(y_w)),
        LineTo(x=X(cx - bw2), y=Y(y_bs)),
        CubicTo(x1=X(cx - bw2), y1=Y(y_bs + d["base_curve_depth"] * 0.86),
                x2=X(cx - bw2 * 0.52), y2=Y(y_bot),
                x=X(cx), y=Y(y_bot)),
    ]
    out["BODY"] = closed_from_left(body_left, XC)

    # COLLAR — narrow vertical sleeve: shallow rims, gently bowed sides
    y_ct, y_cb = lay["y_collar_top"], lay["y_collar_bot"]
    cw2 = d["collar_diameter"] / 2
    rim = cw2 * er
    bow = d["collar_bow"]
    inner = (y_cb - rim) - (y_ct + rim)
    collar_left = [
        MoveTo(x=X(cx), y=Y(y_ct)),
        CubicTo(x1=X(cx - cw2 * K), y1=Y(y_ct),
                x2=X(cx - cw2), y2=Y(y_ct + rim * (1 - K)),
                x=X(cx - cw2), y=Y(y_ct + rim)),
        CubicTo(x1=X(cx - cw2 - bow), y1=Y(y_ct + rim + inner / 3),
                x2=X(cx - cw2 - bow), y2=Y(y_ct + rim + 2 * inner / 3),
                x=X(cx - cw2), y=Y(y_cb - rim)),
        CubicTo(x1=X(cx - cw2), y1=Y(y_cb - rim * (1 - K)),
                x2=X(cx - cw2 * K), y2=Y(y_cb),
                x=X(cx), y=Y(y_cb)),
    ]
    out["COLLAR"] = closed_from_left(collar_left, XC)

    # NECK — one glass cylinder, overlapped by the collar for most of its
    # length, with only a small visible transition below the collar
    y_nt = y_ct + d["collar_height"] * 0.45          # starts inside collar
    y_nb = lay["y_body_top"] + 0.25
    nrim = nw2 * er
    neck_left = [
        MoveTo(x=X(cx), y=Y(y_nt)),
        CubicTo(x1=X(cx - nw2 * K), y1=Y(y_nt),
                x2=X(cx - nw2), y2=Y(y_nt + nrim * (1 - K)),
                x=X(cx - nw2), y=Y(y_nt + nrim)),
        LineTo(x=X(cx - nw2), y=Y(y_nb - nrim)),
        CubicTo(x1=X(cx - nw2), y1=Y(y_nb - nrim * (1 - K)),
                x2=X(cx - nw2 * K), y2=Y(y_nb),
                x=X(cx), y=Y(y_nb)),
    ]
    out["NECK"] = closed_from_left(neck_left, XC)

    # BULB — dense polyline through the ONE canonical half-profile
    n_path = 61
    H = bulb_total_height(d)
    y_stem_base = lay["y_collar_top"] + d["bulb_insertion"]
    bulb_left = [MoveTo(x=X(cx - bulb_half_width(0.0, d)), y=Y(y_stem_base))]
    for i in range(1, n_path):
        t = i / (n_path - 1)
        bulb_left.append(LineTo(x=X(cx - bulb_half_width(t, d)),
                                y=Y(y_stem_base - t * H)))
    out["BULB"] = closed_from_left(bulb_left, XC)

    if components:
        return {k: v for k, v in out.items()
                if k in {c.upper() for c in components}}
    return out


# --- drawing -----------------------------------------------------------------

_CYL = {"BODY": ("#F4EFEC", "#E3DAD5", "#B5A79F"),
        "COLLAR": ("#F2E5D4", "#D2C0B0", "#8E7A6B"),
        "NECK": ("#F2ECE7", "#DCD2CC", "#A79B96"),
        "BULB": ("#8B7078", "#5A484F", "#31262B")}
_ORDER = ("BODY", "NECK", "COLLAR", "BULB")


def _fill(name, d, ox, s):
    hw = {"BODY": d["body_diameter"], "COLLAR": d["collar_diameter"],
          "NECK": d["neck_diameter"], "BULB": d["bulb_max_width"]}[name] / 2
    cx = d["body_diameter"] / 2
    hi, mid, lo = _CYL[name]
    return GradientFill(
        kind="linear", x1=ox + (cx - hw) * s, y1=0.0,
        x2=ox + (cx + hw) * s, y2=0.0,
        stops=[GradientStop(offset=0.0, color=Color.from_hex(mid)),
               GradientStop(offset=0.27, color=Color.from_hex(hi)),
               GradientStop(offset=0.63, color=Color.from_hex(mid)),
               GradientStop(offset=1.0, color=Color.from_hex(lo))])


def draw(d, ox, oy, s, *, prefix="", outline_only=False, components=None,
         stroke_color=None, width_mm=0.4, neutral=False):
    """Render straight from the canonical geometry. ``neutral`` uses flat
    diagnostic fills (§9 forbids cosmetic materials on the closure page)."""
    g = canonical_geometry(d, ox, oy, s, components)
    names = [n for n in _ORDER if n in g]
    kids = []
    if outline_only:
        for n in names:
            kids.append(Path(name=f"{prefix}{n}", segments=g[n],
                             stroke=Stroke(color=stroke_color or INK,
                                           width_mm=width_mm)))
        return Group(name=f"{prefix}Contour", role="product", children=kids)
    flat = {"BODY": "#E7E0DB", "NECK": "#D6CCC6", "COLLAR": "#C4B4A6",
            "BULB": "#5A484F"}
    for n in names:
        f = (SolidFillLike(flat[n]) if neutral else _fill(n, d, ox, s))
        kids.append(Path(name=f"{prefix}{n}", segments=g[n], fill=f))
    if "BODY" in g:
        kids.append(Path(name=f"{prefix}OUTLINE", segments=g["BODY"],
                         stroke=Stroke(color=INK, width_mm=0.2,
                                       opacity=0.45)))
    return Group(name=f"{prefix}Bottle", role="product", children=kids)


def SolidFillLike(hexcode):
    from apps.ire.graph import SolidFill
    return SolidFill(color=Color.from_hex(hexcode))


def draw_reference_contour(ox, oy, h_mm, *, prefix="ref5-",
                           color_hex="#B0453A", width_mm=0.5,
                           landmarks=None, cx_mm=None):
    """The calibrated reference outline itself — independent of the
    generator, so an overlay is a real comparison."""
    span = REF_BOTTOM_PX - REF_TOP_PX
    k = h_mm / span
    # position by the SHARED CENTERLINE when given — overlays must line
    # up on the axis, not on a bounding-box edge
    cx = cx_mm if cx_mm is not None else ox + REF_BODY_WIDTH_PX / 2 * k
    pts = [(y, hw) for (y, hw, _c) in
           (landmarks or list(REF_LANDMARKS.values()))]
    segs = [MoveTo(x=cx - pts[0][1] * k, y=oy + (pts[0][0] - REF_TOP_PX) * k)]
    for y, hw in pts[1:]:
        segs.append(LineTo(x=cx - hw * k, y=oy + (y - REF_TOP_PX) * k))
    segs += mirrored_return(segs, cx) + [ClosePath()]
    return Group(name=f"{prefix}Calibrated", role="generic", children=[
        Path(name=f"{prefix}REF", segments=segs,
             stroke=Stroke(color=Color.from_hex(color_hex),
                           width_mm=width_mm))])


# --- §3 subfixtures: each must pass before the assembly is released ---------

def bulb_subfixture(d: dict) -> dict:
    """A. BULB_PROFILE_FIXTURE — deterministic constraints from §5."""
    smp = bulb_samples(d, 31)
    w = [x["half_width_mm"] for x in smp]
    body = d["body_diameter"]
    H = bulb_total_height(d)
    t_stem = (d["bulb_insertion"] + d["bulb_stem_visible"]) / H
    findings, checks = [], {}

    checks["max_width_25_32pc_of_body"] = \
        0.25 <= d["bulb_max_width"] / body <= 0.32
    checks["stem_width_10_15pc_of_body"] = \
        0.10 <= d["bulb_stem_width"] / body <= 0.15
    checks["stem_substantially_narrower"] = \
        d["bulb_stem_width"] <= 0.60 * d["bulb_max_width"]
    if not (checks["max_width_25_32pc_of_body"]
            and checks["stem_width_10_15pc_of_body"]
            and checks["stem_substantially_narrower"]):
        findings.append("VQ_BULB_REFERENCE_PROFILE_FAILED")

    # an insertion stem exists: a near-constant narrow run below t_stem
    # the constant run, past the small rounding at the very bottom tip
    stem_run = [x for x in smp if 0.08 <= x["t"] <= t_stem]
    checks["insertion_stem_exists"] = (
        len(stem_run) >= 4
        and max(s["half_width_mm"] for s in stem_run)
        - min(s["half_width_mm"] for s in stem_run) < 0.02
        and abs(stem_run[0]["half_width_mm"]
                - d["bulb_stem_width"] / 2) < 1e-6
        and d["bulb_insertion"] > 0)
    if not checks["insertion_stem_exists"]:
        findings.append("VQ_BULB_INSERTION_STEM_MISSING")

    # no flat base: the bottom sample must not equal the stem width
    checks["no_flat_base_segment"] = w[0] < w[1] - 1e-6
    if not checks["no_flat_base_segment"]:
        findings.append("VQ_BULB_FLAT_BASE")

    peak = w.index(max(w))
    checks["maximum_in_lower_middle"] = 0.35 <= peak / 30 <= 0.60
    upper_third = [x["half_width_mm"] for x in smp if x["t"] >= 2 / 3]
    lower_middle = max(w)
    checks["upper_middle_clearly_slimmer"] = \
        max(upper_third) <= 0.80 * lower_middle
    if not checks["upper_middle_clearly_slimmer"]:
        findings.append("VQ_BULB_UPPER_MIDDLE_TOO_WIDE")

    above = w[peak:]
    checks["continuous_narrowing_above_max"] = \
        all(b < a for a, b in zip(above, above[1:]))
    checks["dome_closes_to_zero"] = w[-1] == 0.0
    checks["dome_narrow_not_tombstone"] = w[-2] <= 0.42 * max(w)
    if not (checks["dome_closes_to_zero"]
            and checks["dome_narrow_not_tombstone"]):
        findings.append("VQ_BULB_TOMBSTONE_DOME")

    # crown continuity: second differences over the dome stay small and
    # every step is a genuine change (a polygon shows equal linear steps)
    dome = [x["half_width_mm"] for x in smp if x["t"] >= d["bulb_dome_start"]]
    d1 = [a - b for a, b in zip(dome, dome[1:])]
    d2 = [abs(a - b) for a, b in zip(d1, d1[1:])]
    checks["crown_continuously_curved"] = (
        len(dome) >= 5 and all(x > 0 for x in d1)
        and max(d2) > 1e-4 and max(d2) < max(d1))
    if not checks["crown_continuously_curved"]:
        findings.append("VQ_BULB_POLYGONAL_CROWN")

    checks["at_least_31_samples"] = len(smp) >= 31
    ok = all(checks.values())
    return {"record_type": "vq1_corr5_bulb_subfixture/1.0",
            "component": "BULB", "checks": checks,
            "findings": sorted(set(findings)),
            "samples_31": smp,
            "max_width_mm": d["bulb_max_width"],
            "max_width_frac_of_body": round(d["bulb_max_width"] / body, 4),
            "stem_width_mm": d["bulb_stem_width"],
            "stem_width_frac_of_body": round(d["bulb_stem_width"] / body, 4),
            "stem_visible_mm": d["bulb_stem_visible"],
            "insertion_mm": d["bulb_insertion"],
            "status": "PASSES_STRUCTURAL_FORM_PENDING_HUMAN_REVIEW" if ok
                      else "SUBFIXTURE_FAILED",
            "human_review": "PENDING"}


def collar_neck_subfixture(d: dict) -> dict:
    """B. COLLAR_AND_NECK_FIXTURE — §7 sleeve + §8 neck interface."""
    g = canonical_geometry(d, 0, 0, 1.0)
    lay = layout(d)
    body = d["body_diameter"]
    findings, checks = [], {}

    ratio = d["collar_diameter"] / body
    sleeve = d["collar_height"] / d["collar_diameter"]
    checks["collar_45_55pc_of_body"] = 0.45 <= ratio <= 0.55
    checks["sleeve_height_65_85pc_of_width"] = 0.65 <= sleeve <= 0.85
    if not (checks["collar_45_55pc_of_body"]
            and checks["sleeve_height_65_85pc_of_width"]):
        findings.append("VQ_COLLAR_GENERIC_BLOCK_FALLBACK")

    # a block has straight sides; a sleeve is all curves with a bow
    checks["no_straight_sleeve_sidewall"] = \
        not any(isinstance(s, LineTo) for s in g["COLLAR"])
    side = g["COLLAR"][2]
    checks["sidewall_is_bowed"] = \
        (d["body_diameter"] / 2 - side.x1) > d["collar_diameter"] / 2
    if not (checks["no_straight_sleeve_sidewall"]
            and checks["sidewall_is_bowed"]):
        findings.append("VQ_COLLAR_GENERIC_BLOCK_FALLBACK")

    rim = d["collar_diameter"] / 2 * PROJECTION5["ellipse_depth_ratio"]
    checks["minimal_top_face"] = rim / d["collar_height"] < 0.10
    checks["not_jar_lid"] = sleeve > 0.5 and ratio < 0.62
    if not checks["not_jar_lid"]:
        findings.append("VQ_COLLAR_JAR_LID_SILHOUETTE")

    opening = d["bulb_stem_width"] + 0.3
    checks["top_opening_concealed_by_stem"] = \
        d["bulb_stem_width"] >= 0.85 * opening
    checks["neck_substantially_narrower_than_collar"] = \
        d["neck_diameter"] <= 0.65 * d["collar_diameter"]
    overlap = lay["y_collar_bot"] - (lay["y_collar_top"]
                                     + d["collar_height"] * 0.45)
    neck_len = overlap + d["visible_neck"] + 0.25
    checks["neck_mostly_hidden_in_collar"] = overlap / neck_len >= 0.60
    checks["small_visible_glass_transition"] = \
        0 < d["visible_neck"] <= 0.25 * d["collar_height"]
    checks["collar_physically_overlaps_neck"] = overlap > 0
    if not (checks["neck_mostly_hidden_in_collar"]
            and checks["collar_physically_overlaps_neck"]):
        findings.append("VQ_CLOSURE_ASSEMBLY_INCOHERENT")

    # not a rectangular plug: the neck has curved rims AND straight sides
    checks["neck_is_cylindrical"] = (
        any(isinstance(s, CubicTo) for s in g["NECK"])
        and any(isinstance(s, LineTo) for s in g["NECK"]))
    if not checks["neck_is_cylindrical"]:
        findings.append("VQ_NECK_RECTANGULAR_SPACER_FALLBACK")

    closure_mass = (d["collar_diameter"] * d["collar_height"]
                    + d["bulb_max_width"] * d["bulb_body_height"] * 0.7)
    checks["closure_mass_subordinate"] = \
        closure_mass / (body * d["body_height"]) < 0.22
    if not checks["closure_mass_subordinate"]:
        findings.append("VQ_COLLAR_VISUAL_MASS_EXCESSIVE")

    ok = all(checks.values())
    return {"record_type": "vq1_corr5_collar_neck_subfixture/1.0",
            "component": "COLLAR+NECK", "checks": checks,
            "findings": sorted(set(findings)),
            "collar_body_ratio": round(ratio, 4),
            "sleeve_height_width_ratio": round(sleeve, 4),
            "neck_collar_ratio": round(d["neck_diameter"]
                                       / d["collar_diameter"], 4),
            "neck_overlap_mm": round(overlap, 3),
            "neck_hidden_fraction": round(overlap / neck_len, 4),
            "visible_neck_mm": d["visible_neck"],
            "status": "PASSES_STRUCTURAL_FORM_PENDING_HUMAN_REVIEW" if ok
                      else "SUBFIXTURE_FAILED",
            "human_review": "PENDING"}


def shoulder_body_subfixture(d: dict) -> dict:
    """C. SHOULDER_AND_BODY_FIXTURE — §10 shallow shoulder, §11 cylinder."""
    from apps.ire.corr_mirror import cubic_curvature_samples
    g = canonical_geometry(d, 0, 0, 1.0)
    cx = d["body_diameter"] / 2
    findings, checks = [], {}

    # §10 the calibrated rise: 50 px of a 343 px body width
    ref_rise = ((REF_LANDMARKS["body_wall_top"][0]
                 - REF_LANDMARKS["shoulder_start"][0]) / PX_PER_MM)
    rise_frac = d["shoulder_rise"] / d["body_diameter"]
    checks["shoulder_rise_matches_reference"] = \
        abs(d["shoulder_rise"] - ref_rise) <= 0.6
    checks["shoulder_rise_shallow"] = rise_frac <= 0.18
    if not checks["shoulder_rise_shallow"]:
        findings.append("VQ_SHOULDER_RISE_EXCESSIVE")
    if not checks["shoulder_rise_matches_reference"]:
        findings.append("VQ_SHOULDER_REFERENCE_PROFILE_FAILED")

    # a dome would rise as much as it spreads; a shallow shoulder does not
    spread = cx - d["neck_diameter"] / 2
    checks["not_a_dome"] = d["shoulder_rise"] <= 0.55 * spread
    checks["shoulder_is_uppermost_portion_only"] = \
        d["shoulder_rise"] / d["body_height"] <= 0.12
    if not (checks["not_a_dome"]
            and checks["shoulder_is_uppermost_portion_only"]):
        findings.append("VQ_SHOULDER_DOME_OVERSIZED")

    sh = g["BODY"][1]
    checks["shoulder_is_one_cubic"] = isinstance(sh, CubicTo)
    checks["horizontal_tangent_at_neck"] = abs(sh.y1 - g["BODY"][0].y) < 1e-9
    checks["vertical_tangent_at_wall"] = abs(sh.x2 - sh.x) < 1e-9
    k = [c["curvature"] for c in cubic_curvature_samples(
        g["BODY"][0], sh, 21)]
    checks["no_straight_facet"] = min(k) > 0.001
    if not checks["no_straight_facet"]:
        findings.append("VQ_SHOULDER_FACETED_FALLBACK")

    walls = [s for s in g["BODY"] if isinstance(s, LineTo)]
    lx = [s.x for s in walls if s.x < cx]
    rx = [s.x for s in walls if s.x > cx]
    checks["walls_parallel"] = bool(lx and rx) and \
        abs((max(rx) - min(lx)) - d["body_diameter"]) < 1e-9
    checks["no_taper"] = bool(lx) and (max(lx) - min(lx)) < 1e-9
    if not (checks["walls_parallel"] and checks["no_taper"]):
        findings.append("VQ_BODY_WALL_PARALLELISM_FAILED")

    checks["base_integrated_no_pedestal"] = "BASE" not in g
    checks["base_curve_shallow"] = \
        0 < d["base_curve_depth"] <= 0.15 * d["body_diameter"]
    body_ratio = d["body_height"] / d["body_diameter"]
    ref_ratio = ((REF_LANDMARKS["base_bottom"][0]
                  - REF_LANDMARKS["shoulder_start"][0])
                 / REF_BODY_WIDTH_PX)
    checks["body_proportion_matches_reference"] = \
        abs(body_ratio - ref_ratio) <= 0.08

    ok = all(checks.values())
    return {"record_type": "vq1_corr5_shoulder_body_subfixture/1.0",
            "component": "SHOULDER+BODY", "checks": checks,
            "findings": sorted(set(findings)),
            "shoulder_rise_mm": d["shoulder_rise"],
            "reference_shoulder_rise_mm": round(ref_rise, 3),
            "shoulder_rise_frac_of_body_width": round(rise_frac, 4),
            "body_height_width_ratio": round(body_ratio, 4),
            "reference_body_height_width_ratio": round(ref_ratio, 4),
            "shoulder_curvature_samples": cubic_curvature_samples(
                g["BODY"][0], sh, 21),
            "status": "PASSES_STRUCTURAL_FORM_PENDING_HUMAN_REVIEW" if ok
                      else "SUBFIXTURE_FAILED",
            "human_review": "PENDING"}


def assembly_gate(d: dict, emitted_findings=None) -> dict:
    """§12 — the complete bottle is released only when all three
    subfixtures pass AND emitted contours equal canonical contours."""
    subs = {"A_bulb": bulb_subfixture(d),
            "B_collar_neck": collar_neck_subfixture(d),
            "C_shoulder_body": shoulder_body_subfixture(d)}
    emitted = list(emitted_findings or [])
    passed = {k: v["status"].startswith("PASSES") for k, v in subs.items()}
    identity_ok = not emitted
    released = all(passed.values()) and identity_ok
    findings = sorted({f for v in subs.values() for f in v["findings"]}
                      | set(emitted))
    return {"record_type": "vq1_corr5_assembly_gate/1.0",
            "subfixtures": {k: v["status"] for k, v in subs.items()},
            "subfixture_records": subs,
            "canonical_render_identity": "EQUAL" if identity_ok
                                         else emitted,
            "complete_assembly_released": released,
            "findings": findings,
            "status": ("PASSES_STRUCTURAL_FORM_PENDING_HUMAN_REVIEW"
                       if released else "COMPLETE_ASSEMBLY_BLOCKED"),
            "human_note": "automated path equality never overrides a human "
                          "visual rejection; this never auto-accepts"}


def verify_emitted_contours(pdf_path, geometry, tol_pt=0.35):
    from apps.ire.vq1_corr4 import verify_emitted_contours as _v
    return _v(pdf_path, geometry, tol_pt)
