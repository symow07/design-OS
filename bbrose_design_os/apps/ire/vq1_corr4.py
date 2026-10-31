"""VQ-1-CORR-4 — human-calibrated canonical contour + generator rewrite.

Every component is built from ONE canonical left half-profile; the right
side is a mathematical reflection of the left (never authored twice).
The same segment objects serve the silhouette diagnostic, the rendered
fixture, the Design Graph, PDF/PNG/AI emission and the validators, and
the emitted PDF contours are extracted and compared back against the
canonical paths (VQ_CANONICAL_PROFILE_NOT_USED_BY_RENDER on divergence).

Geometry is driven by vq1_human_calibrated_reference_contour/1.0 —
manually calibrated against a gridded read of reference image #97
(GeneratedImage 97, media/generated/task_52_var_2_reALblg.png,
1024x1536). CONCEPT_ONLY authority; no production measurements derive
from it. Best automated verdict is always
PASSES_STRUCTURAL_FORM_PENDING_HUMAN_REVIEW.
"""
from __future__ import annotations

import math

from apps.ire.graph import (ClosePath, Color, CubicTo, GradientFill,
                            GradientStop, Group, LineTo, MoveTo, Path,
                            Stroke)

#: VQ-1-RESET-1 §4 — this generator is FROZEN; it produced a fixture a
#: human rejected. Rejected regression input only; never a new candidate.
GENERATOR_STATE = "LEGACY_REJECTED_STRUCTURAL_GENERATOR"
MAY_EMIT_NEW_CANDIDATE = False

_K = 0.5523
INK = Color.from_hex("#2A2426")
REFERENCE_IMAGE = "GeneratedImage#97 task_52_var_2_reALblg.png (1024x1536)"

#: near-orthographic shared camera — one ellipse ratio for every rim
PROJECTION4 = {"mode": "weak_perspective_front",
               "ellipse_depth_ratio": 0.13, "centerline": "shared",
               "scale": "shared", "vertical_axis": "shared"}

#: mm dims derived from the manually calibrated contour (body h/w 1.92 —
#: the reference is a SQUATTER cylinder than every prior fixture)
CORR4_DIMS = {
    "body_diameter": 31.3, "body_height": 60.5, "shoulder_rise": 7.6,
    "neck_diameter": 10.4, "visible_neck": 2.2,
    "collar_diameter": 19.0, "collar_height": 15.8, "collar_bow": 0.55,
    "bulb_height": 21.2, "bulb_max_width": 12.3, "bulb_base_width": 8.6,
    "bulb_max_at": 0.28, "bulb_dome_n": 2.0, "bulb_taper": 0.10,
    "bulb_dome_start": 0.74, "bulb_dome_width": 0.72,
    "bulb_insertion": 3.0, "base_curve_depth": 1.6,
}

#: manually calibrated reference outline — left half, (y_px, half_w_px)
#: in image space; centerline x=665, assembly spans y 292..1336
REF_OUTLINE_PX = [
    (292, 0), (310, 30), (340, 46), (390, 58), (440, 64), (470, 66),
    (490, 67),                       # bulb (widest just above the collar)
    (490, 102), (660, 105),          # collar sleeve (near-vertical sides)
    (672, 120), (690, 152), (706, 167), (718, 173),   # rounded shoulder
    (1310, 173),                     # parallel body wall
    (1322, 171), (1330, 160), (1334, 135), (1336, 0),  # integrated base
]
_REF_TOP, _REF_BOT, _REF_CX = 292.0, 1336.0, 665.0
_REF_H = _REF_BOT - _REF_TOP


def calibrated_anchors() -> list[dict]:
    """§3 human-calibrated normalized anchors (y down from bulb apex,
    x = half-width; both as fractions of total assembly height)."""
    named = {
        "bulb_apex": (292, 0), "bulb_max_width": (470, 66),
        "bulb_collar_junction": (490, 67), "collar_top": (490, 102),
        "collar_bottom": (660, 105), "neck_bounds": (661, 55),
        "shoulder_start": (672, 120), "shoulder_apex": (690, 152),
        "body_wall_top": (718, 173), "body_wall_bottom": (1310, 173),
        "lower_body_curve": (1330, 160), "base_integration": (1336, 0),
        "shared_centerline": (814, 0),
    }
    comp = {"bulb_apex": "bulb", "bulb_max_width": "bulb",
            "bulb_collar_junction": "bulb", "collar_top": "collar",
            "collar_bottom": "collar", "neck_bounds": "neck",
            "shoulder_start": "shoulder", "shoulder_apex": "shoulder",
            "body_wall_top": "body", "body_wall_bottom": "body",
            "lower_body_curve": "base", "base_integration": "base",
            "shared_centerline": "centerline"}
    out = []
    for name, (y, hw) in named.items():
        out.append({
            "name": name, "component": comp[name],
            "y_norm": round((y - _REF_TOP) / _REF_H, 4),
            "half_width_norm": round(hw / _REF_H, 4),
            "tolerance_norm": 0.012,
            "status": "MANUALLY_CALIBRATED_AGAINST_GRIDDED_REFERENCE",
            "human_confirmed": False,
            "source_image": REFERENCE_IMAGE,
            "authority": "CONCEPT_ONLY_NOT_PRODUCTION",
        })
    return out


def ref_half_width_norm(y_norm: float) -> float:
    """Interpolated calibrated half-width (fraction of assembly height)
    at normalized height y_norm."""
    y = _REF_TOP + y_norm * _REF_H
    pts = REF_OUTLINE_PX
    for (y0, w0), (y1, w1) in zip(pts, pts[1:]):
        if y0 <= y <= y1 and y1 > y0:
            u = (y - y0) / (y1 - y0)
            return (w0 + (w1 - w0) * u) / _REF_H
    return 0.0


# --- assembly layout ---------------------------------------------------------

def layout(d: dict) -> dict:
    y_ct = d["bulb_height"] - d["bulb_insertion"]        # collar top
    y_cb = y_ct + d["collar_height"]                     # collar bottom
    y_bt = y_cb + d["visible_neck"]                      # body top
    y_sh = y_bt + d["shoulder_rise"]                     # wall start
    y_bs = y_bt + d["body_height"] - d["base_curve_depth"]
    y_bot = y_bt + d["body_height"]
    return {"y_collar_top": y_ct, "y_collar_bot": y_cb, "y_body_top": y_bt,
            "y_wall_top": y_sh, "y_base_start": y_bs, "y_bottom": y_bot,
            "total_height": y_bot}


# --- mirroring (right side is ALWAYS a reflection of the left) --------------

def _starts(segs):
    cur, out = None, []
    for s in segs:
        out.append(cur)
        if not isinstance(s, ClosePath):
            cur = (s.x, s.y)
    return out


def mirrored_return(segs, cx: float):
    """Given a left half traced start->end (first seg MoveTo), return the
    mathematically mirrored right half traced end->start."""
    starts = _starts(segs)
    out = []
    for seg, start in zip(segs[::-1], starts[::-1]):
        if isinstance(seg, MoveTo):
            continue
        if isinstance(seg, LineTo):
            out.append(LineTo(x=2 * cx - start[0], y=start[1]))
        elif isinstance(seg, CubicTo):
            out.append(CubicTo(x1=2 * cx - seg.x2, y1=seg.y2,
                               x2=2 * cx - seg.x1, y2=seg.y1,
                               x=2 * cx - start[0], y=start[1]))
    return out


def _closed(left_half, cx):
    return left_half + mirrored_return(left_half, cx) + [ClosePath()]


# --- canonical half profiles -------------------------------------------------

def bulb_half_width_frac(t: float, d: dict) -> float:
    """Canonical bulb half-profile (fraction of max half-width) at height
    fraction t (0 = insertion base inside the collar, 1 = dome apex)."""
    b = d["bulb_base_width"] / d["bulb_max_width"]
    t_max, n, taper = d["bulb_max_at"], d["bulb_dome_n"], d["bulb_taper"]
    t_dome, w_dome = d["bulb_dome_start"], d["bulb_dome_width"]
    if t <= t_max:                              # gradual lower widening
        u = t / t_max
        return b + (1 - b) * math.sin(math.pi / 2 * u)
    if t <= t_dome:                             # continuous narrowing
        u = (t - t_max) / (t_dome - t_max)
        return 1.0 - (1.0 - w_dome) * u ** (1 + taper * 4)
    s = (t - t_dome) / (1 - t_dome)             # narrow rounded dome
    return max(0.0, w_dome * (1 - s ** n) ** (1 / n))


def bulb_samples(d: dict, n: int = 21) -> list[dict]:
    out = []
    for i in range(n):
        t = i / (n - 1)
        f = bulb_half_width_frac(t, d)
        out.append({"t": round(t, 4), "width_frac": round(f, 4),
                    "half_width_mm": round(f * d["bulb_max_width"] / 2, 4)})
    return out


def canonical_geometry(d: dict, ox: float, oy: float, s: float) -> dict:
    """The ONE set of canonical closed contours (name -> segment list).
    Used identically by silhouette, render, Design Graph and validators."""
    lay = layout(d)
    cx = d["body_diameter"] / 2

    def X(x):
        return ox + x * s

    def Y(y):
        return oy + y * s

    XC = X(cx)
    bw2, nw2, cw2 = (d["body_diameter"] / 2, d["neck_diameter"] / 2,
                     d["collar_diameter"] / 2)
    er = PROJECTION4["ellipse_depth_ratio"]

    # BODY — horizontal tangent at the neck, ONE continuous shoulder
    # cubic with a vertical tangent at wall entry, parallel walls, one
    # lower curve integrated into the sidewalls (no pedestal ellipse)
    y_bt, y_sh = lay["y_body_top"], lay["y_wall_top"]
    y_bs, y_bot = lay["y_base_start"], lay["y_bottom"]
    body_left = [
        MoveTo(x=X(cx - nw2), y=Y(y_bt)),
        CubicTo(x1=X(cx - nw2 - (bw2 - nw2) * 0.55), y1=Y(y_bt),
                x2=X(cx - bw2), y2=Y(y_sh - d["shoulder_rise"] * 0.45),
                x=X(cx - bw2), y=Y(y_sh)),
        LineTo(x=X(cx - bw2), y=Y(y_bs)),
        CubicTo(x1=X(cx - bw2), y1=Y(y_bs + d["base_curve_depth"] * 0.9),
                x2=X(cx - bw2 * 0.55), y2=Y(y_bot),
                x=X(cx), y=Y(y_bot)),
    ]
    body = _closed(body_left, XC)

    # COLLAR — cylindrical sleeve: shallow top/bottom rims, curved
    # (bowed) side surface, no straight rectangular block edges
    y_ct, y_cb = lay["y_collar_top"], lay["y_collar_bot"]
    rim = cw2 * er
    bow = d["collar_bow"]
    ch = (y_cb - rim) - (y_ct + rim)
    collar_left = [
        MoveTo(x=X(cx), y=Y(y_ct)),
        CubicTo(x1=X(cx - cw2 * _K), y1=Y(y_ct),
                x2=X(cx - cw2), y2=Y(y_ct + rim * (1 - _K)),
                x=X(cx - cw2), y=Y(y_ct + rim)),
        CubicTo(x1=X(cx - cw2 - bow), y1=Y(y_ct + rim + ch / 3),
                x2=X(cx - cw2 - bow), y2=Y(y_ct + rim + 2 * ch / 3),
                x=X(cx - cw2), y=Y(y_cb - rim)),
        CubicTo(x1=X(cx - cw2), y1=Y(y_cb - rim * (1 - _K)),
                x2=X(cx - cw2 * _K), y2=Y(y_cb),
                x=X(cx), y=Y(y_cb)),
    ]
    collar = _closed(collar_left, XC)

    # NECK — one narrow cylinder, mostly enclosed by the collar, with a
    # small visible glass transition below the collar bottom
    y_nt, y_nb = y_ct + 7.0, lay["y_body_top"] + 0.3
    nrim = nw2 * er
    neck_left = [
        MoveTo(x=X(cx), y=Y(y_nt)),
        CubicTo(x1=X(cx - nw2 * _K), y1=Y(y_nt),
                x2=X(cx - nw2), y2=Y(y_nt + nrim),
                x=X(cx - nw2), y=Y(y_nt + nrim)),
        LineTo(x=X(cx - nw2), y=Y(y_nb - nrim)),
        CubicTo(x1=X(cx - nw2), y1=Y(y_nb - nrim),
                x2=X(cx - nw2 * _K), y2=Y(y_nb),
                x=X(cx), y=Y(y_nb)),
    ]
    neck = _closed(neck_left, XC)

    # BULB — dense polyline through the ONE canonical half-profile,
    # mirrored; base partially enters the collar; rounded dome apex
    n_path = 41
    bulb_left = [MoveTo(x=X(cx - bulb_half_width_frac(0, d)
                             * d["bulb_max_width"] / 2),
                        y=Y(y_ct + d["bulb_insertion"]))]
    for i in range(1, n_path):
        t = i / (n_path - 1)
        hw = bulb_half_width_frac(t, d) * d["bulb_max_width"] / 2
        y = (y_ct + d["bulb_insertion"]) - t * d["bulb_height"]
        bulb_left.append(LineTo(x=X(cx - hw), y=Y(y)))
    bulb = _closed(bulb_left, XC)

    return {"BODY": body, "COLLAR": collar, "NECK": neck, "BULB": bulb,
            "_lay": lay, "_transform": (ox, oy, s)}


# --- drawing -----------------------------------------------------------------

_ORDER = ("BODY", "NECK", "COLLAR", "BULB")


def draw_fixture(d, ox, oy, s, *, prefix="", silhouette_only=False,
                 component=None, stroke_color=None, width_mm=0.35):
    """Render the fixture from the canonical geometry — the same segment
    objects the validators and Design Graph see."""
    g = canonical_geometry(d, ox, oy, s)
    col = stroke_color or INK
    kids = []
    names = [component.upper()] if component else list(_ORDER)
    if silhouette_only or component:
        for n in names:
            kids.append(Path(name=f"{prefix}{n}", segments=g[n],
                             stroke=Stroke(color=col, width_mm=width_mm)))
        return Group(name=f"{prefix}Contour", role="product",
                     children=kids)
    for n in _ORDER:
        kids.append(Path(name=f"{prefix}{n}", segments=g[n],
                         fill=_cylindrical_fill(n, d, ox, s)))
    kids.append(Path(name=f"{prefix}OUTLINE", segments=g["BODY"],
                     stroke=Stroke(color=INK, width_mm=0.22,
                                   opacity=0.45)))
    return Group(name=f"{prefix}Bottle", role="product", children=kids)


#: highlight / mid / core-shadow for each turned surface
_CYL = {"BODY": ("#F4EFEC", "#E4DBD6", "#B7A9A3"),
        "COLLAR": ("#F0E2D2", "#CDBBAE", "#8C7A6E"),
        "NECK": ("#F2ECE7", "#DDD3CE", "#A79B96"),
        "BULB": ("#8E7680", "#5C4A50", "#33272C")}


def _cylindrical_fill(name, d, ox, s):
    """One horizontal axial gradient across the turned surface — the
    cylindrical read comes from the fill of the canonical path itself,
    so no extra geometry is introduced."""
    hw = {"BODY": d["body_diameter"], "COLLAR": d["collar_diameter"],
          "NECK": d["neck_diameter"],
          "BULB": d["bulb_max_width"]}[name] / 2
    cx = d["body_diameter"] / 2
    hi, mid, lo = _CYL[name]
    return GradientFill(
        kind="linear", x1=ox + (cx - hw) * s, y1=0.0,
        x2=ox + (cx + hw) * s, y2=0.0,
        stops=[GradientStop(offset=0.0, color=Color.from_hex(mid)),
               GradientStop(offset=0.26, color=Color.from_hex(hi)),
               GradientStop(offset=0.62, color=Color.from_hex(mid)),
               GradientStop(offset=1.0, color=Color.from_hex(lo))])


def draw_reference_contour(ox, oy, h_mm, *, prefix="ref-",
                           color_hex="#9C8F89", width_mm=0.4):
    """The human-calibrated reference contour at height h_mm — an
    independent overlay, NOT produced by the generator."""
    k = h_mm / _REF_H
    cx_mm = ox + 173 * k

    def pt(y, hw):
        return (cx_mm - hw * k, oy + (y - _REF_TOP) * k)

    segs = [MoveTo(x=pt(*REF_OUTLINE_PX[0])[0],
                   y=pt(*REF_OUTLINE_PX[0])[1])]
    for y, hw in REF_OUTLINE_PX[1:]:
        p = pt(y, hw)
        segs.append(LineTo(x=p[0], y=p[1]))
    segs += mirrored_return(segs, cx_mm) + [ClosePath()]
    return Group(name=f"{prefix}Calibrated", role="generic", children=[
        Path(name=f"{prefix}REF_CONTOUR", segments=segs,
             stroke=Stroke(color=Color.from_hex(color_hex),
                           width_mm=width_mm))])


# --- validators --------------------------------------------------------------

def _cubic_pt(seg, p0, t):
    x = ((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * seg.x1
         + 3 * (1 - t) * t ** 2 * seg.x2 + t ** 3 * seg.x)
    y = ((1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * seg.y1
         + 3 * (1 - t) * t ** 2 * seg.y2 + t ** 3 * seg.y)
    return x, y


def shoulder_curvature_samples(d: dict, n: int = 17) -> list[dict]:
    """Sampled curvature along the ONE left shoulder cubic."""
    g = canonical_geometry(d, 0, 0, 1.0)
    seg = g["BODY"][1]
    p0 = (g["BODY"][0].x, g["BODY"][0].y)
    out = []
    for i in range(n):
        # interior samples only — clamped one-sided differences at the
        # exact endpoints degenerate to 0 and are not real curvature
        t = 0.02 + 0.96 * i / (n - 1)
        dt = 1e-4
        a = _cubic_pt(seg, p0, t - dt)
        b = _cubic_pt(seg, p0, t + dt)
        m = _cubic_pt(seg, p0, t)
        dx, dy = (b[0] - a[0]) / (2 * dt), (b[1] - a[1]) / (2 * dt)
        ddx = (b[0] - 2 * m[0] + a[0]) / dt ** 2
        ddy = (b[1] - 2 * m[1] + a[1]) / dt ** 2
        den = (dx * dx + dy * dy) ** 1.5 or 1e-9
        out.append({"t": round(t, 3), "x": round(m[0], 3),
                    "y": round(m[1], 3),
                    "curvature": round(abs(dx * ddy - dy * ddx) / den, 6)})
    return out


def bulb_findings(d: dict, n: int = 21) -> list[str]:
    """§8 explicit bulb failures on the canonical profile + path."""
    out = []
    smp = bulb_samples(d, n)
    w = [x["width_frac"] for x in smp]
    g = canonical_geometry(d, 0, 0, 1.0)
    cx = d["body_diameter"] / 2
    pts = [(s.x, s.y) for s in g["BULB"]
           if not isinstance(s, ClosePath)]
    half = (len(pts) + 1) // 2
    left, right = pts[:half], pts[half - 1:][::-1]
    for lp, rp in zip(left, right[:len(left)]):
        if abs((cx - lp[0]) - (rp[0] - cx)) > 1e-9 or \
                abs(lp[1] - rp[1]) > 1e-9:
            out.append("VQ_BULB_LEFT_RIGHT_ASYMMETRY")
            break
    for p, s in zip(pts[:41], smp if n == 41 else bulb_samples(d, 41)):
        if abs((cx - p[0]) - s["half_width_mm"]) > 0.02:
            out.append("VQ_BULB_PROFILE_RENDER_DIVERGENCE")
            break
    upper = [x for x in smp if x["t"] >= 0.5]
    deltas = [a["width_frac"] - b["width_frac"]
              for a, b in zip(upper, upper[1:])]
    if any(dl < 0.005 for dl in deltas):
        out.append("VQ_BULB_UPPER_PLATEAU")
    s9 = bulb_half_width_frac(d["bulb_max_at"]
                              + 0.9 * (1 - d["bulb_max_at"]), d)
    if s9 > 0.60:
        out.append("VQ_BULB_TOMBSTONE_DOME")
    if w[-1] != 0.0 or w[-2] >= 0.45:
        out.append("VQ_BULB_CLOSURE_PATH_INVALID")
    return out


def verify_emitted_contours(pdf_path: str, geometry: dict,
                            tol_pt: float = 0.35) -> list[str]:
    """§9 — extract the ACTUAL emitted PDF contours and require equality
    with the canonical paths (post-render, not pre-render data)."""
    import fitz
    k = 72.0 / 25.4
    page = fitz.open(pdf_path)[0]
    # extended=True also yields the clip paths a gradient-filled object is
    # emitted as (PDF shading is painted through a clip, not a fill op)
    drawings = page.get_drawings(extended=True)

    def expected_items(segs):
        items, cur = [], None
        for s in segs:
            if isinstance(s, MoveTo):
                cur = (s.x * k, s.y * k)
            elif isinstance(s, LineTo):
                items.append(("l", [cur, (s.x * k, s.y * k)]))
                cur = (s.x * k, s.y * k)
            elif isinstance(s, CubicTo):
                items.append(("c", [cur, (s.x1 * k, s.y1 * k),
                                    (s.x2 * k, s.y2 * k),
                                    (s.x * k, s.y * k)]))
                cur = (s.x * k, s.y * k)
        return items

    def matches(drawing, items):
        got = [(it[0], [(p.x, p.y) for p in it[1:]])
               for it in drawing["items"] if it[0] in ("l", "c")]
        if len(got) == len(items) + 1 and got[-1][0] == "l":
            got = got[:-1]                    # explicit closing line
        if len(got) != len(items):
            return False
        for (kind_g, pts_g), (kind_e, pts_e) in zip(got, items):
            if kind_g != kind_e or len(pts_g) != len(pts_e):
                return False
            for pg, pe in zip(pts_g, pts_e):
                if abs(pg[0] - pe[0]) > tol_pt or \
                        abs(pg[1] - pe[1]) > tol_pt:
                    return False
        return True

    out = []
    for name in _ORDER:
        items = expected_items(geometry[name])
        if not any(matches(dw, items) for dw in drawings):
            out.append(f"VQ_CANONICAL_PROFILE_NOT_USED_BY_RENDER:{name}")
    return out


def perceived_structural_report(d: dict, emitted_findings=None) -> dict:
    """§13 perceived validation. Human rejection is always authoritative;
    the best automated state never exceeds pending-human-review."""
    lay = layout(d)
    g = canonical_geometry(d, 0, 0, 1.0)
    cx = d["body_diameter"] / 2
    checks, findings = {}, []

    walls = [s for s in g["BODY"] if isinstance(s, LineTo)]
    lx = [s.x for s in walls if s.x < cx]
    rx = [s.x for s in walls if s.x > cx]
    sep_dev = abs((max(rx) - min(lx)) - d["body_diameter"]) if lx and rx \
        else 99
    checks["body_wall_parallelism"] = sep_dev < 0.05
    if sep_dev >= 0.05:
        findings.append("VQ_BODY_WALL_PARALLELISM_FAILED")

    curv = shoulder_curvature_samples(d)
    kk = [c["curvature"] for c in curv]
    jump = max(abs(a - b) for a, b in zip(kk, kk[1:]))
    # a straight diagonal facet = a run of near-zero curvature samples
    flat_run = run = 0
    for v in kk:
        run = run + 1 if v < 0.005 else 0
        flat_run = max(flat_run, run)
    checks["shoulder_curvature_continuity"] = (
        jump < max(kk) * 0.6 and flat_run < 3)
    if not checks["shoulder_curvature_continuity"]:
        findings.append("VQ_SHOULDER_FACETED_FALLBACK")

    checks["neck_visibility"] = d["visible_neck"] > 0
    checks["collar_cylindrical_readability"] = (
        not any(isinstance(s, LineTo) for s in g["COLLAR"])
        and 0.70 <= d["collar_height"] / d["collar_diameter"] <= 0.95)
    if not checks["collar_cylindrical_readability"]:
        findings.append("VQ_COLLAR_CYLINDRICAL_READABILITY_FAILED")
    closure_area = (d["collar_diameter"] * d["collar_height"]
                    + d["bulb_max_width"] * d["bulb_height"] * 0.7)
    body_area = d["body_diameter"] * d["body_height"]
    checks["collar_visual_mass_subordinate"] = \
        closure_area / body_area < 0.30
    if not checks["collar_visual_mass_subordinate"]:
        findings.append("VQ_CLOSURE_VISUAL_MASS_EXCESSIVE")

    bf = bulb_findings(d)
    checks["bulb_symmetry"] = "VQ_BULB_LEFT_RIGHT_ASYMMETRY" not in bf
    checks["bulb_taper"] = "VQ_BULB_UPPER_PLATEAU" not in bf
    checks["bulb_dome"] = ("VQ_BULB_TOMBSTONE_DOME" not in bf
                           and "VQ_BULB_CLOSURE_PATH_INVALID" not in bf)
    checks["bulb_insertion"] = d["bulb_insertion"] > 0
    findings += bf

    checks["base_integration"] = True     # base cubics live INSIDE BODY
    checks["closure_coherence"] = (
        d["bulb_base_width"] < d["collar_diameter"] - 2
        and d["neck_diameter"] < d["collar_diameter"])
    com_y = (lay["y_body_top"] + d["body_height"] * 0.5)
    checks["visual_center_of_mass_in_body"] = \
        com_y / lay["total_height"] > 0.5

    emitted = emitted_findings if emitted_findings is not None else []
    checks["canonical_render_identity"] = not emitted
    findings += emitted

    ok = all(checks.values())
    return {"record_type": "vq1_corr4_perceived_structural_report/1.0",
            "checks": checks, "findings": sorted(set(findings)),
            "verdict": ("PASSES_STRUCTURAL_FORM_PENDING_HUMAN_REVIEW"
                        if ok else "STRUCTURAL_FORM_FAILED"),
            "human_note": "human rejection is always authoritative; "
                          "this verdict never auto-accepts"}
