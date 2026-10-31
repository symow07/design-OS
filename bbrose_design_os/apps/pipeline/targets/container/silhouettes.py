"""Parametric container silhouette backbone (Phase B, 2026-07-08).

The PRODUCT_CONTAINER target's structural backbone — the container's answer
to packaging's deterministic dieline. Given a confirmed ``ContainerProfile``,
``build_backbone`` returns a ``ContainerBackbone``: the frame the IRE
container composer fills with color zones, label artwork, logo and text.

Geometry is in millimetres, y-DOWN, in the container's own local box
(0..width_mm × 0..height_mm); the composer offsets it onto the concept
sheet. Outlines are graph ``Segment`` lists so the composer wraps them in
``Path`` nodes with no conversion. Structural, not manufacturing-accurate —
the confirm gate + "design intent, not pixels" cover the rest.

First slice: three FORM archetypes — bottle (tall neck), jar (wide squat),
tube (straight body). ``variant`` and ``cap_style`` apply coarse factor
tweaks in this slice; richer variant shapes and the remaining types
(compact, palette, lipstick, mascara/lip-gloss) follow the same pattern.

§BH55(a), 2026-09-20: COMPACT is built, by that same pattern — the first of
the four remaining types, and the form the owner's Phase 1 brief asks for (a
hinged palette, four baked pans, a mirror in the lid). It is the one
archetype whose drawn face is its PLAN rather than its elevation: the lid is
the artwork surface, and an elevation of a compact is a slab. So for a
compact ``width_mm`` × ``height_mm`` are the lid footprint seen from above
and the closed thickness is ``depth_mm``, carried in ``case_geometry``.
Lipstick, mascara and lip-gloss still follow the elevation pattern.

§BH70(1), 2026-09-27: LIPSTICK, MASCARA and PENCIL are built, in that
elevation pattern — each closed and standing, its cap over its body, one
outline (`_capped_body`) with each form's own shares. Until now a lipstick
and a mascara were drawn as the TUBE (a squeeze tube with a crimped end) and
a pencil could not be drawn at all.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Optional

from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo, Segment
from apps.pipeline.targets.container import archetypes as _declared

_K = 0.5522847498307936   # circle→cubic control-point factor

Rect = tuple[float, float, float, float]     # (x, y, w, h), mm, y-down


@dataclass
class ContainerProfile:
    """The confirm-gate payload — what the human reviews before IRE runs."""
    #: §BH61(a): NO DEFAULT. A profile with no archetype is a refusal, not a bottle.
    archetype: str                            # bottle | jar | tube | compact
    #: §BH61(d) / §BH65(e) — THE LAST OF THE BOTTLE-SHAPED DEFAULTS. These read "cylindrical", 110 x 40, a
    #: 0.42 neck and a screw cap, so a compact built without them RECORDED itself as a cylindrical form with a
    #: neck and a screw cap. A field nobody set is now None: THIS DATACLASS IS ALSO THE RECORD (`asdict` is
    #: stored as `container_profile`), and None there means "not known" — the begin_output dropper path sets
    #: the body dimensions to None on purpose so a carton's size never becomes the container's (§4).
    #: Drawing still needs numbers, so `build_backbone` draws from a COPY filled with THIS form's own declared
    #: `nominal`; a bottle's are the same 110 / 40 / 0.42 it always had, so no bottle draws differently.
    variant: Optional[str] = None             # the form's own variants — archetypes.VOCABULARY
    height_mm: Optional[float] = None
    width_mm: Optional[float] = None
    neck_ratio: Optional[float] = None        # neck width / body width — a bottle's word only
    cap_style: Optional[str] = None           # the form's own closures — archetypes.VOCABULARY
    label_zone: Optional[Rect] = None         # override; else derived
    decoration_zone: Optional[Rect] = None    # override; else derived
    # 2C-2E dropper closure geometry (mm, HUMAN_CONFIRMED_CONCEPT_ONLY):
    # {"collar_h": 14, "bulb_h": 22, "collar_w": 28, "base_thickness": 3.5,
    #  "shoulder_radius": 3}. None for every non-dropper profile.
    closure_geometry: Optional[dict] = None
    # §BH55(a) compact case geometry (mm, HUMAN_CONFIRMED_CONCEPT_ONLY), the
    # dropper's `closure_geometry` pattern for a form the elevation cannot
    # describe: {"thickness_mm": 18, "pan_count": 4, "pan_rows": 1,
    # "pan_diameter_mm": 24, "mirror": True, "hinge_mm": 6, "clasp_mm": 18}.
    # None for every non-compact profile; defaults applied by `_compact`.
    case_geometry: Optional[dict] = None
    # §BH71 PART 1, the owner's goal of 2026-09-28: "Take the drawn outline and proportions from the chosen concept
    # picture itself … Templates are only a fallback." The outline traced from the approved concept
    # (`services.concept_outline.outline_for`) — {"kind": "round" | "square" | "rounded_rect" | …,
    # "corner_share", "source_sha256"} — attached only when the shape confirmed is the shape the concept shows.
    # [And for a form drawn in elevation, {"kind": "profile", "profile": [[height share, half-width share], ...],
    # "closure_share", "height_to_width", "source_sha256"} — its outline read about its own axis.]
    # None: the form's template draws, and the drawing's record says why.
    outline: Optional[dict] = None


@dataclass
class ContainerBackbone:
    """The structural frame the container composer consumes.

    ``silhouette`` fills with the BODY colour then strokes as the outline;
    ``cap_region`` overpaints with the CAP colour; ``label_zone`` clips the
    label artwork; anchors position logo/product name. Body colour = the
    silhouette fill, so no separate body_region path is needed.
    """
    archetype: str
    width_mm: float
    height_mm: float
    silhouette: list[Segment]
    cap_region: list[Segment]
    label_zone: Rect
    decoration_zone: Optional[Rect] = None
    anchors: dict[str, tuple[float, float]] = field(default_factory=dict)
    # 2C-2E dropper closure: the collar band and the bulb dome as SEPARATE
    # editable regions (COLLAR_ROSE_GOLD / BULB_DARK_PLUM). None for every
    # non-dropper cap style — the composer then draws the legacy cap_region.
    # [His review of 127, 130, 131 and 132, 2026-10-15, D (11)] … save a traced closure its concept's map reads as a cap
    # on a collar: its collar, below its cap's own region (``_traced_elevation``)
    collar_region: Optional[list] = None
    bulb_region: Optional[list] = None
    base_band_mm: float = 0.0            # visible glass base thickness (mm)
    # §BH55(a) compact: the parts of the OPEN case, in the same local box as
    # `silhouette`, as separate editable regions — the four pans the brief
    # names and the mirror in the lid. The generic composer draws neither and
    # ignores them, exactly as it ignores collar/bulb on a non-dropper; the
    # palette sheet composer draws them. None for every non-compact form.
    pan_regions: Optional[list] = None
    mirror_region: Optional[list] = None
    hinge_axis_mm: float = 0.0           # distance of the hinge from the back edge
    pan_diameter_mm: float = 0.0         # the pan actually drawn
    #: §BH55(a) — WHERE that diameter came from, because the two answers mean different things to a reader:
    #: HOUSE_PAN_CONTRACT     the owner's preserved 26.0 mm pan (palette_pan_profile.PAN_CONTRACT), which fits
    #: DERIVED_CASE_TOO_SMALL the case cannot hold the house pan, so a smaller one is drawn AND SAID
    #: NAMED_BY_A_PERSON      a diameter given in case_geometry, which always wins
    pan_diameter_source: str = ""
    #: [His goal after the pitch page, 2026-10-15, A (3): "131 drawn landscape when the concept is portrait with a cream
    #: border"] a lid traced from its concept whose concept shows a rim round its art: the rim as its own region — the
    #: lid's outline less its inset face, drawn even-odd in the rim's own colour over the lid's art. None for every lid
    #: whose concept shows none, and for every other form.
    border_region: Optional[list] = None


# --- geometry helpers --------------------------------------------------------


def _rrect(x: float, y: float, w: float, h: float, r: float) -> list[Segment]:
    """Closed rounded-rectangle outline (mm, y-down)."""
    r = max(0.0, min(r, w / 2.0, h / 2.0))
    if r == 0:
        return [MoveTo(x=x, y=y), LineTo(x=x + w, y=y), LineTo(x=x + w, y=y + h),
                LineTo(x=x, y=y + h), ClosePath()]
    k = r * _K
    return [
        MoveTo(x=x + r, y=y),
        LineTo(x=x + w - r, y=y),
        CubicTo(x1=x + w - r + k, y1=y, x2=x + w, y2=y + r - k, x=x + w, y=y + r),
        LineTo(x=x + w, y=y + h - r),
        CubicTo(x1=x + w, y1=y + h - r + k, x2=x + w - r + k, y2=y + h, x=x + w - r, y=y + h),
        LineTo(x=x + r, y=y + h),
        CubicTo(x1=x + r - k, y1=y + h, x2=x, y2=y + h - r + k, x=x, y=y + h - r),
        LineTo(x=x, y=y + r),
        CubicTo(x1=x, y1=y + r - k, x2=x + r - k, y2=y, x=x + r, y=y),
        ClosePath(),
    ]


def _rrect_with_button(y: float, w: float, h: float, r: float, bw: float, br: float) -> list[Segment]:
    """§BH71 PART 3: ONE closed outline — a rounded rectangle ``w`` wide from ``y`` down ``h`` (its corner ``r``)
    with a button ``bw`` wide centred on its top edge, rising from ``y`` to 0 (its corner ``br``): an airless jar's
    pump button on its lid, drawn as the one outline it is seen as — never a second path laid over the first."""
    r = max(0.0, min(r, (w - bw) / 2.0, h / 2.0))
    br = max(0.0, min(br, bw / 2.0, y / 2.0))
    k, kb = r * _K, br * _K
    b0, b1 = (w - bw) / 2.0, (w + bw) / 2.0
    return [
        MoveTo(x=b0, y=y), LineTo(x=b0, y=br),
        CubicTo(x1=b0, y1=br - kb, x2=b0 + br - kb, y2=0.0, x=b0 + br, y=0.0),
        LineTo(x=b1 - br, y=0.0),
        CubicTo(x1=b1 - br + kb, y1=0.0, x2=b1, y2=br - kb, x=b1, y=br),
        LineTo(x=b1, y=y), LineTo(x=w - r, y=y),
        CubicTo(x1=w - r + k, y1=y, x2=w, y2=y + r - k, x=w, y=y + r),
        LineTo(x=w, y=y + h - r),
        CubicTo(x1=w, y1=y + h - r + k, x2=w - r + k, y2=y + h, x=w - r, y=y + h),
        LineTo(x=r, y=y + h),
        CubicTo(x1=r - k, y1=y + h, x2=0.0, y2=y + h - r + k, x=0.0, y=y + h - r),
        LineTo(x=0.0, y=y + r),
        CubicTo(x1=0.0, y1=y + r - k, x2=r - k, y2=y, x=r, y=y),
        ClosePath(),
    ]


def _circle(cx: float, cy: float, r: float) -> list[Segment]:
    """Closed circle as four cubics (mm, y-down) — §BH55(a), for a compact's pans."""
    k = r * _K
    return [
        MoveTo(x=cx, y=cy - r),
        CubicTo(x1=cx + k, y1=cy - r, x2=cx + r, y2=cy - k, x=cx + r, y=cy),
        CubicTo(x1=cx + r, y1=cy + k, x2=cx + k, y2=cy + r, x=cx, y=cy + r),
        CubicTo(x1=cx - k, y1=cy + r, x2=cx - r, y2=cy + k, x=cx - r, y=cy),
        CubicTo(x1=cx - r, y1=cy - k, x2=cx - k, y2=cy - r, x=cx, y=cy - r),
        ClosePath(),
    ]


def _ellipse(cx: float, cy: float, a: float, b: float) -> list[Segment]:
    """Closed ellipse as four cubics (mm, y-down), semi-axes ``a`` across and ``b`` along — §BH71 PART 3, a learned
    oval lid; the circle's own construction with its two radii apart."""
    ka, kb = a * _K, b * _K
    return [
        MoveTo(x=cx, y=cy - b),
        CubicTo(x1=cx + ka, y1=cy - b, x2=cx + a, y2=cy - kb, x=cx + a, y=cy),
        CubicTo(x1=cx + a, y1=cy + kb, x2=cx + ka, y2=cy + b, x=cx, y=cy + b),
        CubicTo(x1=cx - ka, y1=cy + b, x2=cx - a, y2=cy + kb, x=cx - a, y=cy),
        CubicTo(x1=cx - a, y1=cy - kb, x2=cx - ka, y2=cy - b, x=cx, y=cy - b),
        ClosePath(),
    ]


def _cap_factors(cap_style: str) -> tuple[float, float]:
    """(cap_width_factor, cap_height_factor) relative to body width / height."""
    return {
        "screw": (0.34, 0.12),
        "pump":  (0.26, 0.20),   # taller, narrower
        "flip":  (0.40, 0.09),   # wider, shorter
        "lid":   (1.02, 0.32),   # jar lid — wide, deep
        "crimp": (0.50, 0.05),   # tube crimp — wide, thin
        # §BH71 PART 3 — the catalogue's closures, each its own proportion
        "brush_cap": (0.46, 0.42),     # a nail polish's tall brush cap
        "crimp_spray": (0.72, 0.26),   # a perfume's collar and overcap
        "airless_pump": (0.98, 0.24),  # an overcap as wide as the airless body
        "mist": (0.80, 0.22),          # a fine-mist actuator under its overcap
        "roller_ball": (0.55, 0.30),   # a roll-on's tall cap over its ball
        "nozzle": (0.30, 0.16),        # a lip tube's applicator nozzle
    }.get(cap_style, (0.34, 0.12))


# --- per-archetype builders --------------------------------------------------


def _slim_bottle(p: ContainerProfile) -> ContainerBackbone:
    """2B-3V-CORR-4: a slim RECTANGULAR gloss bottle — flat readable front,
    straight side walls, softly rounded corners, and a low flat rectangular
    cap block sitting directly on the body (no neck/shoulder taper). This is
    the wand-applicator lip-gloss silhouette, never a rounded squeeze tube."""
    W, H = p.width_mm, p.height_mm
    cap_h = 0.18 * H
    rb = min(W, H) * 0.10                 # soft corner radius
    rc = rb * 0.7                          # cap corners slightly tighter

    def _rounded_rect(x0, y0, w, h, r):
        return [
            MoveTo(x=x0 + r, y=y0),
            LineTo(x=x0 + w - r, y=y0),
            CubicTo(x1=x0 + w - r + r * _K, y1=y0, x2=x0 + w, y2=y0 + r - r * _K,
                    x=x0 + w, y=y0 + r),
            LineTo(x=x0 + w, y=y0 + h - r),
            CubicTo(x1=x0 + w, y1=y0 + h - r + r * _K,
                    x2=x0 + w - r + r * _K, y2=y0 + h, x=x0 + w - r, y=y0 + h),
            LineTo(x=x0 + r, y=y0 + h),
            CubicTo(x1=x0 + r - r * _K, y1=y0 + h, x2=x0, y2=y0 + h - r + r * _K,
                    x=x0, y=y0 + h - r),
            LineTo(x=x0, y=y0 + r),
            CubicTo(x1=x0, y1=y0 + r - r * _K, x2=x0 + r - r * _K, y2=y0,
                    x=x0 + r, y=y0),
            ClosePath(),
        ]

    sil = _rounded_rect(0, 0, W, H, rb)                     # one clean block
    cap_region = _rounded_rect(W * 0.02, 0, W * 0.96, cap_h, rc)
    body_top = cap_h + 0.02 * H
    body_h = H - body_top
    lw, lh = W * 0.72, body_h * 0.55
    lx, ly = (W - lw) / 2.0, body_top + body_h * 0.16
    label = p.label_zone or (lx, ly, lw, lh)
    deco = p.decoration_zone or (lx, ly + lh + body_h * 0.05, lw, body_h * 0.16)
    return ContainerBackbone(
        "bottle", W, H, sil, cap_region, label, deco,
        anchors={"logo": (W / 2.0, ly + lh * 0.14),
                 "product_name": (W / 2.0, ly + lh * 0.48)})


def _dropper_bottle(p: ContainerProfile) -> ContainerBackbone:
    """2C-2E serum dropper bottle: tall cylindrical body with a flat,
    restrained shoulder and a visible thick glass base, topped by a polished
    collar band and a smooth bulb dome — collar and bulb are SEPARATE
    regions so the composer keeps them independently editable. All geometry
    is HUMAN_CONFIRMED_CONCEPT_ONLY; ``height_mm`` is the TOTAL height
    including the closure."""
    W, H = p.width_mm, p.height_mm
    cx = W / 2.0
    g = p.closure_geometry or {}
    collar_h = float(g.get("collar_h", 0.13 * H))
    bulb_h = float(g.get("bulb_h", 0.21 * H))
    collar_w = min(float(g.get("collar_w", 0.85 * W)), W * 0.98)
    base_t = float(g.get("base_thickness", 0.05 * H))
    shoulder_r = float(g.get("shoulder_radius", min(3.0, W * 0.1)))
    bulb_w = collar_w * 0.55
    y_bulb, y_collar = bulb_h, bulb_h + collar_h    # body starts at y_collar

    # bulb: smooth dome (flat where it meets the collar)
    bulb_region = [
        MoveTo(x=cx - bulb_w / 2, y=y_bulb),
        CubicTo(x1=cx - bulb_w / 2, y1=y_bulb - bulb_h * 0.95,
                x2=cx + bulb_w / 2, y2=y_bulb - bulb_h * 0.95,
                x=cx + bulb_w / 2, y=y_bulb),
        ClosePath(),
    ]
    # collar: clean cylindrical band
    collar_region = [
        MoveTo(x=cx - collar_w / 2, y=y_bulb),
        LineTo(x=cx + collar_w / 2, y=y_bulb),
        LineTo(x=cx + collar_w / 2, y=y_collar),
        LineTo(x=cx - collar_w / 2, y=y_collar),
        ClosePath(),
    ]
    # body: straight walls, flat shoulder with a small transition radius,
    # softly rounded base corners (the thick base band is a composer object)
    r, rb = shoulder_r, min(W, H) * 0.04
    body = [
        MoveTo(x=r, y=y_collar),
        LineTo(x=W - r, y=y_collar),
        CubicTo(x1=W - r + r * _K, y1=y_collar, x2=W, y2=y_collar + r - r * _K,
                x=W, y=y_collar + r),
        LineTo(x=W, y=H - rb),
        CubicTo(x1=W, y1=H - rb + rb * _K, x2=W - rb + rb * _K, y2=H,
                x=W - rb, y=H),
        LineTo(x=rb, y=H),
        CubicTo(x1=rb - rb * _K, y1=H, x2=0, y2=H - rb + rb * _K, x=0, y=H - rb),
        LineTo(x=0, y=y_collar + r),
        CubicTo(x1=0, y1=y_collar + r - r * _K, x2=r - r * _K, y2=y_collar,
                x=r, y=y_collar),
        ClosePath(),
    ]
    body_h = H - y_collar
    lw, lh = W * 0.67, body_h * 0.59
    label = p.label_zone or (cx - lw / 2, y_collar + body_h * 0.15, lw, lh)
    lx, ly, lw, lh = label
    return ContainerBackbone(
        "bottle", W, H, body, collar_region, label, p.decoration_zone,
        anchors={"logo": (cx, ly + lh * 0.12),
                 "product_name": (cx, ly + lh * 0.44)},
        collar_region=collar_region, bulb_region=bulb_region,
        base_band_mm=base_t)


def _bottle(p: ContainerProfile) -> ContainerBackbone:
    if (p.variant or "").lower() == "slim":
        return _slim_bottle(p)
    if (p.cap_style or "").lower() == "dropper":
        return _dropper_bottle(p)
    W, H = p.width_mm, p.height_mm
    cx = W / 2.0
    cw_f, ch_f = _cap_factors(p.cap_style if p.cap_style in _BOTTLE_CAPS else "screw")
    cap_w, cap_h = cw_f * W, ch_f * H
    neck_w = max(0.2, min(0.7, p.neck_ratio)) * W
    neck_h = 0.06 * H
    shoulder_h = 0.12 * H
    if p.variant == "airless":
        # §BH71 PART 3: an airless bottle is a straight cylinder under an overcap as wide as it — no neck, no shoulder
        neck_w, neck_h, shoulder_h = min(cap_w, W * 0.98), 0.01 * H, 0.01 * H
    elif p.variant == "flacon":
        neck_h, shoulder_h = 0.03 * H, 0.05 * H         # a flacon's square glass shoulders and short neck
    elif p.variant == "roller":
        neck_h, shoulder_h = 0.02 * H, 0.08 * H         # a roll-on's rounded shoulder up to its ball
    y1, y2, y3 = cap_h, cap_h + neck_h, cap_h + neck_h + shoulder_h
    rb = min(W, H) * 0.06
    # tapered narrows the body toward the shoulder; square uses straight
    # diagonal shoulders; cylindrical curves them.
    body_r = W if p.variant != "tapered" else W * 0.92
    bx = (W - body_r) / 2.0

    sil: list[Segment] = [
        MoveTo(x=cx - cap_w / 2, y=0),
        LineTo(x=cx + cap_w / 2, y=0),
        LineTo(x=cx + cap_w / 2, y=y1),
        LineTo(x=cx + neck_w / 2, y=y1),
        LineTo(x=cx + neck_w / 2, y=y2),
    ]
    if p.variant in ("square", "flacon"):
        sil.append(LineTo(x=bx + body_r, y=y3))
    else:
        sil.append(CubicTo(
            x1=cx + neck_w / 2 + (body_r / 2 - neck_w / 2) * 0.4, y1=y2,
            x2=bx + body_r, y2=y3 - shoulder_h * 0.4, x=bx + body_r, y=y3))
    sil += [
        LineTo(x=bx + body_r, y=H - rb),
        CubicTo(x1=bx + body_r, y1=H - rb + rb * _K, x2=bx + body_r - rb + rb * _K, y2=H, x=bx + body_r - rb, y=H),
        LineTo(x=bx + rb, y=H),
        CubicTo(x1=bx + rb - rb * _K, y1=H, x2=bx, y2=H - rb + rb * _K, x=bx, y=H - rb),
        LineTo(x=bx, y=y3),
    ]
    if p.variant in ("square", "flacon"):
        sil.append(LineTo(x=cx - neck_w / 2, y=y2))
    else:
        sil.append(CubicTo(
            x1=bx, y1=y3 - shoulder_h * 0.4,
            x2=cx - neck_w / 2 - (body_r / 2 - neck_w / 2) * 0.4, y2=y2,
            x=cx - neck_w / 2, y=y2))
    sil += [
        LineTo(x=cx - neck_w / 2, y=y1),
        LineTo(x=cx - cap_w / 2, y=y1),
        ClosePath(),
    ]
    cap_region = [
        MoveTo(x=cx - cap_w / 2, y=0), LineTo(x=cx + cap_w / 2, y=0),
        LineTo(x=cx + cap_w / 2, y=y1), LineTo(x=cx + neck_w / 2, y=y1),
        LineTo(x=cx + neck_w / 2, y=y2), LineTo(x=cx - neck_w / 2, y=y2),
        LineTo(x=cx - neck_w / 2, y=y1), LineTo(x=cx - cap_w / 2, y=y1), ClosePath(),
    ]
    body_h = H - y3
    lw, lh = body_r * 0.72, body_h * 0.5
    lx, ly = cx - lw / 2, y3 + body_h * 0.26
    label = p.label_zone or (lx, ly, lw, lh)
    deco = p.decoration_zone
    if deco is None and body_h * 0.14 > 4:
        deco = (lx, ly + lh + body_h * 0.04, lw, body_h * 0.12)
    return ContainerBackbone(
        "bottle", W, H, sil, cap_region, label, deco,
        anchors={"logo": (cx, ly + lh * 0.16), "product_name": (cx, ly + lh * 0.52)})


def _jar(p: ContainerProfile) -> ContainerBackbone:
    W, H = p.width_mm, p.height_mm
    cx = W / 2.0
    _, ch_f = _cap_factors("lid")
    lid_h = ch_f * H
    body_r = min(W, H) * 0.14
    if p.variant == "sifter":
        lid_h = 0.40 * H                          # §BH71 PART 3: a loose powder's deep screw lid over its sifter
    top = 0.0
    if p.variant == "airless":
        top = 0.10 * H                            # §BH71 PART 3: an airless jar's pump button, on its lid
    sil = _rrect(0, top, W, H - top, body_r)     # squat rounded body
    cap_region = _rrect(0, top, W, lid_h, min(body_r, lid_h / 2))
    if top:                                       # one outline: the button on the lid, never a path over a path
        sil = _rrect_with_button(top, W, H - top, body_r, W * 0.32, W * 0.05)
        cap_region = _rrect_with_button(top, W, lid_h, min(body_r, lid_h / 2), W * 0.32, W * 0.05)
    body_top = top + lid_h
    body_h = H - body_top
    lw, lh = W * 0.74, body_h * 0.56
    lx, ly = cx - lw / 2, body_top + body_h * 0.22
    label = p.label_zone or (lx, ly, lw, lh)
    return ContainerBackbone(
        "jar", W, H, sil, cap_region, label, p.decoration_zone,
        anchors={"logo": (cx, ly + lh * 0.16), "product_name": (cx, ly + lh * 0.55)})


#: [his test day finding 3, 2026-09-30, design 117: "it gave me a bottle of shampoo". The tube template drew a straight
#: body, a rounded shoulder and a screw cap's narrow cap on top, whatever its closure. A squeeze tube is round at its
#: cap end and flattened at its crimp, where it is widest: a round tube's crimp is π/2 of its diameter across, so its
#: round end is 2/π of the drawing's width — 0.64; measured on his concept, the flip-top is 0.62 of the crimp's width]
TUBE_ROUND_END = 2.0 / math.pi
#: a flip-top as wide as the round end it closes, all but its edge; a screw cap about half of it
TUBE_CAP_OF_ROUND_END = {"flip": 0.96, "screw": 0.55}
#: the cap's height, the shoulder where the round end meets it, and the flat crimp band, as shares of the height
TUBE_CAP_H, TUBE_SHOULDER_H, TUBE_CRIMP_H = 0.12, 0.03, 0.04


def _squeeze_tube(p: ContainerProfile) -> ContainerBackbone:
    """A squeeze tube standing closure up, as the drawing stands every product: its cap on its round end, a short
    shoulder, its body widening in straight sides to the crimp, and the crimp a flat band as wide as the drawing."""
    W, H = p.width_mm, p.height_mm
    cx = W / 2.0
    round_w = TUBE_ROUND_END * W
    cap_w = TUBE_CAP_OF_ROUND_END.get(p.cap_style, TUBE_CAP_OF_ROUND_END["screw"]) * round_w
    cap_h = TUBE_CAP_H * H
    y2 = cap_h + TUBE_SHOULDER_H * H
    y3 = H - TUBE_CRIMP_H * H
    sil = [
        MoveTo(x=cx - cap_w / 2, y=0),
        LineTo(x=cx + cap_w / 2, y=0),
        LineTo(x=cx + cap_w / 2, y=cap_h),
        LineTo(x=cx + round_w / 2, y=y2),
        LineTo(x=W, y=y3),
        LineTo(x=W, y=H),
        LineTo(x=0, y=H),
        LineTo(x=0, y=y3),
        LineTo(x=cx - round_w / 2, y=y2),
        LineTo(x=cx - cap_w / 2, y=cap_h),
        ClosePath(),
    ]
    cap_region = _rrect(cx - cap_w / 2, 0, cap_w, cap_h, cap_w * 0.10)
    body_h = y3 - y2
    ly, lh = y2 + body_h * 0.22, body_h * 0.55
    reach = round_w + (W - round_w) * (ly - y2) / body_h      # the body's width where the label starts, its narrowest
    lw = reach * 0.78
    label = p.label_zone or (cx - lw / 2, ly, lw, lh)
    lx, ly, lw, lh = label
    return ContainerBackbone(
        "tube", W, H, sil, cap_region, label, p.decoration_zone,
        anchors={"logo": (cx, ly + lh * 0.16), "product_name": (cx, ly + lh * 0.52)})


def _tube(p: ContainerProfile) -> ContainerBackbone:
    if p.cap_style in TUBE_CAP_OF_ROUND_END and p.variant != "slim":
        return _squeeze_tube(p)                   # [his test day finding 3] a lip tube's slim nozzle form below
    W, H = p.width_mm, p.height_mm
    cx = W / 2.0
    cw_f, ch_f = _cap_factors("nozzle" if p.cap_style == "nozzle" else "screw")   # [§BH71 PART 3: a lip tube's]
    cap_w, cap_h = cw_f * W, ch_f * H
    shoulder_h = 0.10 * H
    y1 = cap_h
    y2 = cap_h + shoulder_h
    crimp = 0.03 * H
    # straight body, small cap at top over a rounded shoulder, flat crimped base
    sil = [
        MoveTo(x=cx - cap_w / 2, y=0),
        LineTo(x=cx + cap_w / 2, y=0),
        LineTo(x=cx + cap_w / 2, y=y1),
        CubicTo(x1=cx + cap_w / 2 + (W / 2 - cap_w / 2) * 0.5, y1=y1,
                x2=W, y2=y2 - shoulder_h * 0.4, x=W, y=y2),
        LineTo(x=W, y=H - crimp),
        LineTo(x=W, y=H),
        LineTo(x=0, y=H),
        LineTo(x=0, y=H - crimp),
        LineTo(x=0, y=y2),
        CubicTo(x1=0, y1=y2 - shoulder_h * 0.4,
                x2=cx - cap_w / 2 - (W / 2 - cap_w / 2) * 0.5, y2=y1,
                x=cx - cap_w / 2, y=y1),
        ClosePath(),
    ]
    cap_region = _rrect(cx - cap_w / 2, 0, cap_w, cap_h, cap_w * 0.12)
    body_h = H - y2
    lw, lh = W * 0.78, body_h * 0.55
    lx, ly = cx - lw / 2, y2 + body_h * 0.22
    label = p.label_zone or (lx, ly, lw, lh)
    return ContainerBackbone(
        "tube", W, H, sil, cap_region, label, p.decoration_zone,
        anchors={"logo": (cx, ly + lh * 0.16), "product_name": (cx, ly + lh * 0.52)})


#: §BH55(a) — a compact's defaults, in the brief's own terms. Every one is a proposal a person confirms or
#: changes at the gate, exactly as the bottle's are; none is a manufacturing dimension.
COMPACT_DEFAULTS = {"thickness_mm": 18.0, "pan_count": 4,
                    "pan_rows": 0,               # 0 = choose the layout that draws the LARGEST pan
                    "pan_diameter_mm": 0.0,      # 0 = the HOUSE pan if the case holds it, else derived — see below
                    "mirror": True, "hinge_mm": 6.0, "clasp_mm": 18.0}


def house_pan_diameter_mm() -> float:
    """The pan this house makes, read from the record that owns it — §BH55(a).

    `palette_pan_profile.PAN_CONTRACT["pan_outside_diameter_mm"]` is 26.0 mm and its provenance reads "owner M4B-A
    preserved value". A compact that derived its own pan diameter would be a second answer to a question the owner
    has already answered, disagreeing with his by millimetres, which is the defect §BH55 Phase 4 spent a commit on
    in the colour dict. Read, never written: 26.0 is his and clause 3 keeps it.

    Imported inside the function because this module is pure geometry with no service dependencies, and because a
    machine without the PALT services must still draw a compact — it then falls back to the case, and says so.
    """
    try:
        from apps.pipeline.services.palette_pan_profile import PAN_CONTRACT
        return float(PAN_CONTRACT["pan_outside_diameter_mm"][0])
    except Exception:
        return 0.0


#: §BH71 PART 3: the compact's variants whose lid is a circle — the round one, and the cushion
ROUND_LIDS = ("round", "cushion")
#: §BH71 PART 3: the variant a learned oval lid is offered as (``services.learned_shapes``) — an ellipse in the plan's
#: own width and length, its face the whole ellipse; the key names the geometry, so drawing it needs no lookup
OVAL_LID = "learned_oval"
#: §BH71 PART 3: the closures a bottle draws with a cap of their own proportion — every declared one but the
#: dropper, which draws its own assembly
_BOTTLE_CAPS = ("screw", "pump", "flip", "brush_cap", "crimp_spray", "airless_pump", "mist", "roller_ball")


def compact_lid_face(width_mm: float, height_mm: float, case_geometry: Optional[dict] = None,
                     variant: Optional[str] = None) -> dict:
    """The LID FACE of a compact in plan — ``{"x_mm", "y_mm", "width_mm", "height_mm"}``: the whole plan less the hinge
    band at the back. Its keys carry their unit, so the WI-T analysis reads every length taken from it as millimetres.

    ONE definition, read twice: `_compact` draws it as the lid's `cap_region`, and since §BH67(c)3 the zone proposal
    makes it the compact's print zone — OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "THE COMPACT'S
    PRINT ZONE IS THE WHOLE LID, inside bleed and the mark's clear space." A second copy of the hinge arithmetic in
    the contract would be a second answer to where the lid is.

    [§BH71 PART 1: a ROUND lid is the whole circle — its hinge a knuckle at the back edge, which a round lid's plan
    does not cut a band from — and the face says its shape beside its box, "shape" and "corner_mm", so a reader
    keeps print inside the lid's own outline rather than its box. The rectangle's face is unchanged.]"""
    g = dict(COMPACT_DEFAULTS, **(case_geometry or {}))
    if (variant or "").lower() in ROUND_LIDS:
        d_mm = min(float(width_mm), float(height_mm))
        return {"x_mm": (float(width_mm) - d_mm) / 2.0, "y_mm": (float(height_mm) - d_mm) / 2.0,
                "width_mm": d_mm, "height_mm": d_mm, "shape": "round", "corner_mm": d_mm / 2.0}
    if (variant or "").lower() == OVAL_LID:        # [§BH71 PART 3: a learned oval lid is the whole ellipse]
        return {"x_mm": 0.0, "y_mm": 0.0, "width_mm": float(width_mm), "height_mm": float(height_mm), "shape": "oval",
                "corner_mm": min(float(width_mm), float(height_mm)) / 2.0}
    hinge_mm = max(2.0, float(g["hinge_mm"]))
    return {"x_mm": 0.0, "y_mm": hinge_mm, "width_mm": float(width_mm), "height_mm": float(height_mm) - hinge_mm}


def _compact(p: ContainerProfile) -> ContainerBackbone:
    """A hinged compact, DRAWN IN PLAN — §BH55(a).

    `width_mm` × `height_mm` are the lid footprint seen from above (the artwork surface); the closed thickness is
    `case_geometry["thickness_mm"]`. The hinge is the back edge (y = 0) and the clasp is centred on the front edge
    (y = H), which is how a compact is held and opened, so a reader can tell the two ends apart at a glance.

    `cap_region` is the LID FACE. On a bottle that region is the closure and the label sits below it; on a compact
    the lid IS the face the artwork is printed on, so the label zone is inset inside it rather than beside it.

    The pans and the mirror are the OPEN case, returned as their own regions: the generic container composer draws
    neither, and the palette sheet composer draws both. The ROW COUNT is measured from the case — whichever layout
    leaves the most room — but the DIAMETER is the house's own pan, `PAN_CONTRACT`'s owner-preserved 26.0 mm, drawn
    whenever the case holds it. A case too small for the house pan gets the fitted diameter and says so on the
    backbone (`pan_diameter_source`), because a silently shrunken "baked pan" is how a 19.3 mm one reaches a design.
    """
    g = dict(COMPACT_DEFAULTS, **(p.case_geometry or {}))
    W, H = p.width_mm, p.height_mm
    cx = W / 2.0
    # §BH71 PART 1, the owner's goal of 2026-09-28, measured: "the compact template ignores 'Round' and always draws a
    # rounded rectangle." The variant is read now: ROUND draws the lid as a circle across the plan's narrower side,
    # its face the whole circle; SQUARE and ROUNDED_RECT draw the plan's rectangle, their corner the traced concept's
    # own share where the drawing carries one (`p.outline`), else the template's 8 %.
    variant = (p.variant or "").lower()
    if variant in ROUND_LIDS:                  # [§BH71 PART 3: a cushion compact is round, its lid a circle]
        variant = "round"
    corner_default = 0.08
    if variant == "paperboard":                # [§BH71 PART 3: a paperboard palette's book corners]
        corner_default = 0.02
    # [His goal after the pitch page, 2026-10-15, A (3)] a traced corner of 0.0 is the concept's square corner, never
    # "no corner read": only a corner the outline does not carry takes the template's
    corner_share = (p.outline or {}).get("corner_share")
    if corner_share is None:
        corner_share = corner_default
    r_case = min(W, H) * min(0.5, max(0.0, float(corner_share)))
    face = compact_lid_face(W, H, p.case_geometry, variant=variant)
    hinge = face["y_mm"]
    border_region = None
    if variant == "round":
        r_lid = face["width_mm"] / 2.0
        sil = _circle(cx, H / 2.0, r_lid)
        cap_region = _circle(cx, H / 2.0, r_lid)
    elif variant == OVAL_LID:                  # [§BH71 PART 3: a learned oval — the ellipse in the plan]
        sil = _ellipse(cx, H / 2.0, W / 2.0, H / 2.0)
        cap_region = _ellipse(cx, H / 2.0, W / 2.0, H / 2.0)
    else:
        # the lid face is the whole plan less the hinge band at the back — `compact_lid_face`, the one definition
        sil = _rrect(0, 0, W, H, r_case)
        cap_region = _rrect(face["x_mm"], hinge, face["width_mm"], face["height_mm"], r_case)
        if (p.outline or {}).get("kind") in TRACED_PLAN_KINDS:
            # [His goal after the pitch page, 2026-10-15, A (3): "SHAPES AND PROPORTIONS come from the concept ... 131
            # drawn landscape when the concept is portrait with a cream border"] a lid traced from its concept is the
            # lid its concept shows, whole: no hinge band in the body's colour across its back (131's grey strip) —
            # the hinge is behind the lid, never on its face; and the rim the concept shows round its art drawn as a
            # rim, at its measured widths, in its own colour (``concept_outline.lid_border``)
            cap_region = _rrect(0, 0, W, H, r_case)
            border_region = lid_border_region(W, H, r_case, (p.outline or {}).get("border"))

    # the pans: `pan_rows` rows inside the base's own inset, sized by the gutters
    n = max(1, int(g["pan_count"]))
    inset_x = W * 0.09
    inset_y = hinge + (H - hinge) * 0.16
    field_w = W - 2 * inset_x
    field_h = (H - inset_y) - (H * 0.14)        # leave the clasp end clear
    if variant == "round":                     # §BH71: the round case's field is the circle's inscribed square
        side_mm = face["width_mm"] * 0.62
        inset_x, inset_y = cx - side_mm / 2.0, H / 2.0 - side_mm / 2.0
        field_w = field_h = side_mm
    elif variant == OVAL_LID:                  # [§BH71 PART 3: an oval case's field, the same shares of its axes]
        field_w, field_h = W * 0.62, H * 0.62
        inset_x, inset_y = cx - field_w / 2.0, H / 2.0 - field_h / 2.0
    gutter = min(field_w, field_h) * 0.07

    def _fit(rows):
        per = -(-n // rows)                     # ceiling division
        return min((field_w - gutter * (per - 1)) / per,
                   (field_h - gutter * (rows - 1)) / rows), per

    # §BH55(a): the row count is MEASURED, not chosen — whichever layout draws the largest pan wins, because a
    # baked pan is a real object (26–36 mm across on a face palette) and a layout that shrinks it to fit is the
    # wrong layout. On the brief's own 110 × 95 case a single row draws 19.3 mm and two rows draw 28.6 mm, so two
    # rows win; on a wide shallow case a single row wins by the same arithmetic. A row count named in
    # `case_geometry` is a person's choice and is obeyed.
    rows = max(1, min(int(g["pan_rows"]), n)) if int(g["pan_rows"]) else         max(range(1, n + 1), key=lambda r: _fit(r)[0])
    d_fit, per_row = _fit(rows)
    # §BH55(a): the HOUSE's pan first. A diameter named in case_geometry is a person's and always wins; otherwise
    # the owner's preserved 26.0 mm is drawn WHEN THE CASE HOLDS IT, and only a case too small for it falls back to
    # the fitted diameter — which is then SAID on the backbone rather than passing as a chosen size.
    named = float(g["pan_diameter_mm"])
    house = house_pan_diameter_mm()
    if named:
        d, source = named, "NAMED_BY_A_PERSON"
    elif house and house <= d_fit:
        d, source = house, "HOUSE_PAN_CONTRACT"
    else:
        d, source = d_fit, "DERIVED_CASE_TOO_SMALL"
    d = max(6.0, d)
    pans, i = [], 0
    for row in range(rows):
        in_row = min(per_row, n - i)
        row_w = in_row * d + gutter * (in_row - 1)
        y = inset_y + d / 2 + row * (d + gutter)
        for col in range(in_row):
            pans.append(_circle(cx - row_w / 2 + d / 2 + col * (d + gutter), y, d / 2))
            i += 1

    # the mirror: the lid's own inset panel, drawn on the open sheet opposite the pans
    mirror = None
    if g.get("mirror") and variant == "round":   # §BH71: a round lid's mirror is round, inside its rim
        mirror = _circle(cx, H / 2.0, face["width_mm"] * 0.40)
    elif g.get("mirror"):
        mw, mh = W - 2 * inset_x, (H - hinge) * 0.62
        mirror = _rrect(cx - mw / 2, hinge + (H - hinge) * 0.14, mw, mh, min(r_case, mh / 2))

    # the artwork zone on the lid face, and the anchors inside it
    lw, lh = W * 0.76, (H - hinge) * 0.52
    lx, ly = cx - lw / 2, hinge + (H - hinge) * 0.24
    if variant == "round":                     # §BH71: inside the circle — its inscribed rectangle's share
        lw, lh = face["width_mm"] * 0.64, face["height_mm"] * 0.50
        lx, ly = cx - lw / 2, H / 2.0 - lh / 2.0
    label = p.label_zone or (lx, ly, lw, lh)
    return ContainerBackbone(
        "compact", W, H, sil, cap_region, label, p.decoration_zone,
        anchors={"logo": (cx, ly + lh * 0.18), "product_name": (cx, ly + lh * 0.60),
                 "clasp": (cx, H - max(1.0, float(g["clasp_mm"])) / 2)},
        pan_regions=pans, mirror_region=mirror, hinge_axis_mm=hinge,
        pan_diameter_mm=d, pan_diameter_source=source, border_region=border_region)


#: [His goal after the pitch page, 2026-10-15, A (3)] the plan kinds a lid traced from its concept is drawn whole as
#: (``concept_outline.PLAN_VARIANT``'s rectangles; a round or an oval lid is already its whole outline)
TRACED_PLAN_KINDS = ("square", "rounded_rect")
#: the sides of a lid's rim, as ``concept_outline.lid_border`` measures them — each a share of the lid's own height
#: (top, bottom) or width (left, right)
BORDER_SIDES = ("top", "right", "bottom", "left")


def lid_border_region(W: float, H: float, r: float, border: Optional[dict]) -> Optional[list]:
    """[His goal after the pitch page, 2026-10-15, A (3): "131 ... with a cream border"] The rim a concept shows round its
    lid's art, as one region: the lid's outline (``_rrect`` 0, 0, ``W``, ``H``, corner ``r``) with its inset face cut
    out — the face inset by the rim's measured share on each side, its corner the lid's less the narrowest rim — to be
    drawn even-odd. None where no rim was measured (``border`` None) or one side's measure is missing."""
    if not border or any(border.get(k) is None for k in BORDER_SIDES):
        return None
    top, right, bottom, left = (max(0.0, float(border[k])) for k in BORDER_SIDES)
    x0, y0 = left * W, top * H
    w, h = W - (left + right) * W, H - (top + bottom) * H
    if w <= 0 or h <= 0:
        return None
    inner_r = max(0.0, r - min(x0, y0, right * W, bottom * H))
    return _rrect(0, 0, W, H, r) + _rrect(x0, y0, w, h, inner_r)


def _capped_body(p: ContainerProfile, *, cap_share: float, cap_width: float, top_radius: float,
                 base_radius: float, label_cover: tuple[float, float]) -> tuple:
    """§BH70(1) — the one outline a lipstick, a mascara and a pencil share, CLOSED and standing: a cap over a body of
    the same axis, the cap `cap_width` of the body's width, the pair drawn as ONE silhouette with the step between
    them where the cap is narrower. Each form passes its own shares; nothing here is a bottle's (no neck, no
    shoulder), and the label zone sits on the BODY below the cap, inset by `label_cover` (width, height shares)."""
    W, H = p.width_mm, p.height_mm
    cx = W / 2.0
    cap_h = cap_share * H
    cw = cap_width * W
    rt = min(top_radius, cw / 2.0, cap_h / 2.0)             # the cap's top corners
    rb = min(base_radius, W / 2.0, (H - cap_h) / 2.0)       # the body's base corners
    x0, x1 = cx - cw / 2.0, cx + cw / 2.0
    k_t, k_b = rt * _K, rb * _K
    sil = [
        MoveTo(x=x0 + rt, y=0),
        LineTo(x=x1 - rt, y=0),
        CubicTo(x1=x1 - rt + k_t, y1=0, x2=x1, y2=rt - k_t, x=x1, y=rt),
        LineTo(x=x1, y=cap_h),
        LineTo(x=W, y=cap_h),                                # the step to the body, flat when the widths agree
        LineTo(x=W, y=H - rb),
        CubicTo(x1=W, y1=H - rb + k_b, x2=W - rb + k_b, y2=H, x=W - rb, y=H),
        LineTo(x=rb, y=H),
        CubicTo(x1=rb - k_b, y1=H, x2=0, y2=H - rb + k_b, x=0, y=H - rb),
        LineTo(x=0, y=cap_h),
        LineTo(x=x0, y=cap_h),
        LineTo(x=x0, y=rt),
        CubicTo(x1=x0, y1=rt - k_t, x2=x0 + rt - k_t, y2=0, x=x0 + rt, y=0),
        ClosePath(),
    ]
    cap_region = _rrect(x0, 0, cw, cap_h, rt)
    body_h = H - cap_h
    lw, lh = W * label_cover[0], body_h * label_cover[1]
    lx, ly = cx - lw / 2.0, cap_h + (body_h - lh) / 2.0
    label = p.label_zone or (lx, ly, lw, lh)
    return sil, cap_region, label


def _lipstick(p: ContainerProfile) -> ContainerBackbone:
    """§BH70(1): a lipstick CLOSED — the pull-off cap over the upper half, the case below it carrying the print. A
    square case has near-square corners and a round one a softened top; the cap is the case's own width."""
    W, H = p.width_mm, p.height_mm
    square = (p.variant or "").lower() == "square"
    sil, cap_region, label = _capped_body(
        p, cap_share=0.52, cap_width=1.0, top_radius=W * (0.06 if square else 0.22),
        base_radius=W * (0.04 if square else 0.08), label_cover=(0.74, 0.62))
    lx, ly, lw, lh = label
    return ContainerBackbone(
        "lipstick", W, H, sil, cap_region, label, p.decoration_zone,
        anchors={"logo": (W / 2.0, ly + lh * 0.18), "product_name": (W / 2.0, ly + lh * 0.58)})


def _mascara(p: ContainerProfile) -> ContainerBackbone:
    """§BH70(1): a mascara CLOSED — the long cap that is its wand's grip over the upper part, a touch narrower than
    the vial below it, which carries the print. Nothing is a tube's: no crimp, no screw cap on a shoulder."""
    W, H = p.width_mm, p.height_mm
    square = (p.variant or "").lower() == "square"
    sil, cap_region, label = _capped_body(
        p, cap_share=0.56, cap_width=0.9, top_radius=W * (0.08 if square else 0.3),
        base_radius=W * (0.06 if square else 0.2), label_cover=(0.76, 0.66))
    lx, ly, lw, lh = label
    return ContainerBackbone(
        "mascara", W, H, sil, cap_region, label, p.decoration_zone,
        anchors={"logo": (W / 2.0, ly + lh * 0.16), "product_name": (W / 2.0, ly + lh * 0.55)})


def _pencil(p: ContainerProfile) -> ContainerBackbone:
    """§BH70(1): a cosmetic pencil — the cap over its sharpened (or twist-up) point at the top, the long barrel below
    carrying the print, its butt end square. The barrel's print runs the length of it, which is how a pencil is
    printed; the zone here is that length."""
    W, H = p.width_mm, p.height_mm
    share, width, top = 0.26, 1.0, W * 0.45
    if (p.cap_style or "").lower() == "click":
        share, width, top = 0.06, 0.55, W * 0.2          # §BH71 PART 3: a click pen — its button, no cap
    elif (p.variant or "").lower() == "pen":
        share, width, top = 0.32, 1.0, W * 0.3           # §BH71 PART 3: a liner pen — its cap a third of it
    sil, cap_region, label = _capped_body(
        p, cap_share=share, cap_width=width, top_radius=top, base_radius=W * 0.05, label_cover=(0.8, 0.78))
    lx, ly, lw, lh = label
    return ContainerBackbone(
        "pencil", W, H, sil, cap_region, label, p.decoration_zone,
        anchors={"logo": (W / 2.0, ly + lh * 0.12), "product_name": (W / 2.0, ly + lh * 0.5)})


def _simplify(points: list, eps: float) -> list:
    """Douglas-Peucker: the fewest of ``points`` that keep the polyline within ``eps`` mm of every one of them."""
    if len(points) < 3:
        return list(points)
    (x0, y0), (x1, y1) = points[0], points[-1]
    dx, dy = x1 - x0, y1 - y0
    span = math.hypot(dx, dy)
    far, at = 0.0, 0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        d = abs(dy * (px - x0) - dx * (py - y0)) / span if span > 0 else math.hypot(px - x0, py - y0)
        if d > far:
            far, at = d, i
    if far <= eps:
        return [points[0], points[-1]]
    return _simplify(points[:at + 1], eps)[:-1] + _simplify(points[at:], eps)


def _curve_through(points: list, width: float, height: float) -> list[Segment]:
    """Cubic segments through ``points`` after the first (Catmull-Rom at tension 0.5, as Bézier handles): a clean vector
    that passes through every kept point, a turn sharper than ``_CORNER_DEG`` kept as a corner, every handle held inside
    the ``width`` x ``height`` box the product is drawn in, so no curve bulges past its own widest.

    [§BH71 PART 1, the owner's goal of 2026-09-28, "traced to a clean vector": the box did not hold it. A handle was
    (next - prev) / 6 on both sides of a point, so a long side beside a short shoulder threw the shoulder's curve
    past its own points — a horn 6.45 mm tall at each shoulder of task 53's traced bottle, 7.4 mm under an aerosol's
    overcap. Each handle now lies along the same tangent, a third of ITS OWN segment long (the uniform spacing's
    (next - prev) / 6 exactly, where the two segments are equal), and every control point is held inside the span
    of the two points its segment joins: a cubic lies inside the hull of its four points, so no curve leaves the
    two points it joins. The box holds too, since every point is inside it.]"""
    n = len(points)

    def tangent(i):
        if i == 0 or i == n - 1:
            return None
        (ax, ay), (bx, by), (cx, cy) = points[i - 1], points[i], points[i + 1]
        turn = abs((math.atan2(cy - by, cx - bx) - math.atan2(by - ay, bx - ax) + math.pi) % (2.0 * math.pi) - math.pi)
        if turn > math.radians(_CORNER_DEG):
            return None
        length = math.hypot(cx - ax, cy - ay)
        return ((cx - ax) / length, (cy - ay) / length) if length else None
    segs = []
    for i in range(n - 1):
        (x0, y0), (x1, y1) = points[i], points[i + 1]

        def within(x, y, x0=x0, y0=y0, x1=x1, y1=y1):
            return min(max(x0, x1), max(min(x0, x1), x)), min(max(y0, y1), max(min(y0, y1), y))
        third = math.hypot(x1 - x0, y1 - y0) / 3.0
        t0, t1 = tangent(i), tangent(i + 1)
        (h0x, h0y) = (t0[0] * third, t0[1] * third) if t0 else (0.0, 0.0)
        (h1x, h1y) = (t1[0] * third, t1[1] * third) if t1 else (0.0, 0.0)
        (c1x, c1y), (c2x, c2y) = within(x0 + h0x, y0 + h0y), within(x1 - h1x, y1 - h1y)
        segs.append(CubicTo(x1=c1x, y1=c1y, x2=c2x, y2=c2y, x=x1, y=y1))
    return segs


#: a turn in a traced outline sharper than this stays a corner — a cap's step, a shoulder's edge
_CORNER_DEG = 35.0
#: the tolerance a traced outline is simplified to, as a share of the product's height
_TRACE_TOLERANCE_SHARE = 0.004


#: [His goal after the pitch page, 2026-10-15, A (3): "SHAPES AND PROPORTIONS come from the concept: caps, droppers, lids,
#: collars ... (not crude templates: 128's grey-block dropper, 130's shield lid)"] how a traced closure is read as the
#: parts it is. A closure is a LID where its side holds at least ``LID_WIDE_SHARE`` of the body's widest (the share
#: ``concept_outline.TRACE_PARAMS["closure_narrow_ratio"]`` reads a closure as narrower than its body by); its side is
#: the median half-width of the middle ``LID_SIDE_ROWS`` of its rows. A row more than ``CLOSURE_FLARE_STEP`` (a share of
#: the widest) wider than the row above it, at the closure's foot, is the body's shoulder flaring out under the closure
#: — never the closure (130's white shoulder read into its gold lid, the "shield"); the closure ends where its side
#: stops widening, never higher than ``CLOSURE_FLARE_MAX`` of its own height up. The rows at a lid's top narrower than
#: ``LID_SIDE_HOLD`` of its side, within ``LID_TOP_FACE_MAX`` of the closure's height, are its top face seen from above
#: (the photo's ellipse), drawn as the flat top an elevation shows — its corners the turn the outline makes there.
LID_WIDE_SHARE = 0.72
LID_SIDE_ROWS = (0.25, 0.75)
CLOSURE_FLARE_STEP = 0.004
CLOSURE_FLARE_MAX = 0.5
LID_SIDE_HOLD = 0.98
LID_TOP_FACE_MAX = 0.5
#: [His goal after the pitch page, A (3)] a dropper's closure parts: its collar the closure's lowest rows, each at least
#: ``COLLAR_KEEP_SHARE`` of the collar's own width (the widest of the closure's lowest ``COLLAR_BASE_SHARE`` of rows);
#: the rows above the first narrower one its bulb (128's chrome bulb on its wider chrome collar) — each part at least
#: ``CLOSURE_PART_MIN_ROWS`` traced rows, or not split
COLLAR_KEEP_SHARE = 0.85
COLLAR_BASE_SHARE = 0.25
CLOSURE_PART_MIN_ROWS = 2


def _flare_foot(prof: list, rows: list, c: float) -> Optional[float]:
    """Where a closure's own side stops widening at its foot, as a share of the height — the rows below it, each wider
    than the one above by more than ``CLOSURE_FLARE_STEP``, the body's shoulder flaring out under it; None where its
    foot does not flare, or would end higher than ``CLOSURE_FLARE_MAX`` of its own height up."""
    i = rows[-1]
    while i > 0 and prof[i][1] > prof[i - 1][1] + CLOSURE_FLARE_STEP:
        i -= 1
    if i < rows[-1] and prof[i][0] >= (1.0 - CLOSURE_FLARE_MAX) * c:
        return round((prof[i][0] + prof[i + 1][0]) / 2.0, 4)
    return None


def _side_of(rows: list) -> float:
    """The median half-width of the middle ``LID_SIDE_ROWS`` of ``rows`` — a closure's own side."""
    lo, hi = int(len(rows) * LID_SIDE_ROWS[0]), max(int(len(rows) * LID_SIDE_ROWS[1]), int(len(rows) * LID_SIDE_ROWS[0]) + 1)
    mid = sorted(s for _t, s in rows[lo:hi])
    return mid[len(mid) // 2]


def closure_shaped(profile: list, closure_share: float, cap_style: Optional[str] = None,
                   archetype: Optional[str] = None) -> tuple:
    """[His goal after the pitch page, 2026-10-15, A (3)] ``(the profile, the closure's share, what was read)`` — the
    traced profile ``[(t, s)]`` (shares of the height and of the widest, top down) and its closure line, a LID (a closure
    as wide as its body, the constants above) read as the part it is: its foot where its own side stops widening, never
    the body's shoulder under it; its top face, seen from above, its flat top where its form names it a lid (a jar's).
    A narrower closure — a cap on its neck, a
    dropper's bulb on its collar — is read as traced. ``what`` names each change, ``[]`` where none was made."""
    prof = [(float(t), float(s)) for t, s in profile]
    c = float(closure_share)
    said = []
    rows = [i for i, (t, _s) in enumerate(prof) if t < c]
    if len(rows) < 2 * CLOSURE_PART_MIN_ROWS:
        return prof, c, said
    if (cap_style or "").lower() == "dropper":
        # [His review of 127, 130, 131 and 132, 2026-10-15, D (11)] a dropper's collar sits on the glass neck: the rows at
        # its foot, wider each than the one above, are the bottle's shoulder rising under it — never the collar (128's
        # line fell 0.035 into its shoulder, so its collar was read 0.66 wide and no bulb could be split from it)
        foot = _flare_foot(prof, rows, c)
        if foot is not None:
            said.append("the collar's foot read where its side stops widening (%.3f of the height, was %.3f): the rows "
                        "below are the bottle's shoulder" % (foot, c))
            c = foot
        return prof, c, said
    widest = max(s for _t, s in prof)
    if _side_of([prof[i] for i in rows]) < LID_WIDE_SHARE * widest:
        return prof, c, said                            # a cap on a neck: its neck and shoulder are read as they were
    foot = _flare_foot(prof, rows, c)
    if foot is not None:
        c = foot
        said.append("the lid's foot read where its side stops widening (%.3f of the height, was %.3f): the rows "
                    "below, wider each than the one above, are the body's shoulder" % (c, float(closure_share)))
    closure = [(t, s) for t, s in prof if t < c]
    side = _side_of(closure)
    # its top squared only on a LID — the closure its form names a lid, or a lid cap style: a lipstick's, a mascara's
    # or a stick's cap as wide as its case may truly be domed, and the profile alone cannot tell a dome from a lid's top
    # face seen from above
    lid = (cap_style or "").lower() == "lid" or (_declared.is_known(archetype)
                                                 and _declared.closure_part_of(archetype) == "lid")
    if lid and side >= LID_WIDE_SHARE * widest:
        top = 0
        while top < len(closure) and closure[top][1] < LID_SIDE_HOLD * side:
            top += 1
        if 0 < top < len(closure) and closure[top][0] <= LID_TOP_FACE_MAX * c:
            prof = [(t, max(s, side)) if k <= top else (t, s) for k, (t, s) in enumerate(prof)]
            said.append("the lid's top face, seen from above in the photo, drawn as the flat top an elevation shows "
                        "(its first %.3f of the height)" % closure[top][0])
    return prof, c, said


def closure_split(profile: list, closure_share: float) -> Optional[float]:
    """[His goal after the pitch page, 2026-10-15, A (3): "128's grey-block dropper"] Where a dropper's bulb meets its
    collar, as a share of the height — or None: the collar the closure's lowest rows as wide as its own base
    (``COLLAR_KEEP_SHARE``), the bulb every row above the first narrower one. A bulb narrower than its collar (128's)
    and a round bulb on a narrow neck read alike: the neck is the first narrower row."""
    rows = [(float(t), float(s)) for t, s in profile if float(t) < float(closure_share)]
    if len(rows) < 2 * CLOSURE_PART_MIN_ROWS:
        return None
    base = rows[-max(1, int(len(rows) * COLLAR_BASE_SHARE)):]
    collar_w = max(s for _t, s in base)
    def first_narrower(least):
        i = len(rows) - 1
        while i >= 0 and rows[i][1] >= least:
            i -= 1
        return i
    i = first_narrower(COLLAR_KEEP_SHARE * collar_w)
    if i < CLOSURE_PART_MIN_ROWS - 1 or len(rows) - 1 - i < CLOSURE_PART_MIN_ROWS:
        return None
    # the step between them read halfway: a row wider than halfway from the bulb's own width to the collar's is the
    # collar's shoulder, never a skirt on the bulb
    bulb = sorted(s for _t, s in rows[:i + 1])
    i = first_narrower((collar_w + bulb[len(bulb) // 2]) / 2.0)
    if i < CLOSURE_PART_MIN_ROWS - 1:
        return None
    return rows[i][0]


def _simplify_keeping(points: list, eps: float, keep: frozenset) -> list:
    """``_simplify``, every point whose height (``y``) is in ``keep`` kept — an end's arc is drawn through all its points,
    never cut to a chamfer by the tolerance."""
    marks = [0] + [i for i in range(1, len(points) - 1) if points[i][1] in keep] + [len(points) - 1]
    out = []
    for a, b in zip(marks, marks[1:]):
        out += _simplify(points[a:b + 1], eps)[:-1]
    return out + [points[-1]]


def _part_outline(rows: list, cx: float, W: float, H: float, eps: float, keep: frozenset = frozenset()) -> list[Segment]:
    """One closed part of a traced outline from its rows ``[(t, s)]``, top down: its right side down, across, its left
    side up — drawn as the silhouette is (``_simplify``, ``_curve_through``); the rows at the heights in ``keep`` (shares
    of the height, an end's arc: ``rounded_ends``) each kept."""
    held = frozenset(t * H for t in keep)
    right = _simplify_keeping([(cx + s * W / 2.0, t * H) for t, s in rows], eps, held)
    left = _simplify_keeping([(cx - s * W / 2.0, t * H) for t, s in reversed(rows)], eps, held)
    return [MoveTo(x=right[0][0], y=right[0][1])] + _curve_through(right, W, H) + [LineTo(x=left[0][0], y=left[0][1])] \
        + _curve_through(left, W, H) + [ClosePath()]


#: [His review of 127, 130, 131 and 132, 2026-10-15, C (3): "parts meet as the concept shows ... the product outline
#: matches the concept (130's jar is a shield shape, not a round squat jar)"; D (11)] how each END of a traced outline —
#: the top of its closure, the foot of its body — is drawn. The photo's end is read from the end inward: its rows widen
#: until they grow by no more than ``grow`` (a share of the widest) over ``still`` of the height; the end's own side is
#: the first row at ``hold`` of the widest of them. An end whose last row narrows to under ``point`` of that side is the
#: rounding the photo shows there — a dome (a bulb, a lipstick's cap) or the ellipse a base or a top face makes seen a
#: little from above (130's foot, 128's) — drawn as the quarter ellipse its own depth makes, its width across that depth
#: in the concept's own proportion at most: a dome stays a dome, a base seen from above is drawn as the flat foot an
#: elevation shows, its corners rounded at the depth the photo shows them; never the V of the photo's ellipse (130's
#: shield) nor the chamfer and the steps 96 rows make of it (128's bulb, its castle top; its foot, bevelled). An end
#: still wide at its last row is the rounding of a flat end: drawn as the quarter ellipse through its own extent — and
#: one the trace cut at its reflection (127's capsule foot) as the round its last rows were turning along, continued.
#: ``samples`` points on each quarter, every one kept. The executor's, new.
END_ROUND = {"version": 1, "grow": 0.02, "still": 0.03, "hold": 0.99, "point": 0.5, "samples": 8}


def _end_arc(rows: list, htw: float, cut: bool) -> Optional[tuple]:
    """``(rows kept, arc rows)`` for the end ``rows[0]`` is at (``rows`` from that end inward, ``(t, s)``), or None where
    the end is not rounded (its first row already its side)."""
    p = END_ROUND
    best, best_at, k = rows[0][1], 0, 0
    for k in range(1, len(rows)):
        if rows[k][1] > best + p["grow"]:
            best, best_at = rows[k][1], k
        elif abs(rows[k][0] - rows[best_at][0]) >= p["still"]:
            break
    side_ref = max(s for _t, s in rows[:k + 1])
    e = next(j for j in range(k + 1) if rows[j][1] >= p["hold"] * side_ref)
    if e == 0 or side_ref <= 0:
        return None
    if e == 1:
        # [his last goal before the pitch, Step 2, 138: "a straight block" — its square black cap drawn with a flared,
        # rounded top] an end that reaches its side in one row is square: its one narrower row the photo's thin top
        # ellipse (or a mask's last row, a crimp's V), drawn flat at its side's width with square corners, never a round
        return rows[1:], [(rows[0][0], rows[1][1])]
    (t_end, s_end), (t_e, s_e) = rows[0], rows[e]
    sign = 1.0 if t_e > t_end else -1.0
    depth = abs(t_e - t_end)                            # shares of the height
    half = s_e / 2.0                                    # the end's half-width, in widths of the widest
    if s_end < p["point"] * s_e:
        rx = min(1.0, depth * htw / half) if half > 0 else 1.0   # a dome keeps its round; a base seen from above, flat
        ry = depth
    else:
        lack = (s_e - s_end) / 2.0
        if cut and lack > 0:
            r = min(half, (depth * htw) ** 2 / (2.0 * lack) + lack / 2.0)    # the circle its last rows turn along
            rx, ry = r / half, r / htw
        else:
            rx, ry = (s_e - s_end) / s_e, depth
    t_c = t_end + sign * ry
    n = int(p["samples"])
    arc = [(t_c - sign * ry * math.sin(math.pi / 2.0 * j / n), s_e * (1.0 - rx) + s_e * rx * math.cos(math.pi / 2.0 * j / n))
           for j in range(n + 1)]
    kept = [(t, s) for t, s in rows if sign * (t - t_c) > 0]
    return kept, arc


def rounded_ends(profile: list, htw: float, cut_foot: bool = False) -> tuple:
    """``(the profile, the heights of its ends' arcs)`` — a traced profile ``[(t, s)]`` (top down) with its top and its
    foot each drawn as ``END_ROUND`` reads it; ``htw`` the outline's height over its width (the concept's proportion),
    ``cut_foot`` the trace's own word that its foot was cut at its reflection. An end its rows do not round is kept."""
    prof = [(float(t), float(s)) for t, s in profile]
    if len(prof) < 4 or not htw:
        return prof, frozenset()
    keep = set()
    top = _end_arc(prof, float(htw), False)
    if top is not None:
        kept, arc = top
        prof = arc[::-1] + kept                         # the arc from its end down, then the rows below it
        keep |= {t for t, _s in arc}
    foot = _end_arc(list(reversed(prof)), float(htw), cut_foot)
    if foot is not None:
        kept, arc = foot
        prof = list(reversed(kept)) + arc               # the rows above it, then the arc down to its end
        keep |= {t for t, _s in arc}
    return prof, frozenset(keep)


def _traced_elevation(p: ContainerProfile, template: ContainerBackbone) -> ContainerBackbone:
    """§BH71 PART 1, the owner's goal of 2026-09-28: "Take the drawn outline and proportions from the chosen concept
    picture itself (read and traced to a clean vector). Templates are only a fallback." A form drawn in ELEVATION, its
    outline the concept's own (``p.outline``, ``concept_outline.trace_elevation``): the half-width read at every height
    about the product's axis, mirrored, scaled so its widest is the confirmed width and its height the confirmed
    height, simplified and drawn as smooth cubics through the kept points, its corners kept; the closure the part above
    the line the picture shows it meeting the body; the label in the body below it, inside its narrowest reach. The
    template drew ``template`` and is kept for what the trace does not say (the decoration zone a person set).

    [His goal after the pitch page, 2026-10-15, A (3)] the closure read as the part it is (``closure_shaped``): a lid's
    straight sides and flat top, never a shield; a dropper's bulb and collar each its own region (``closure_split``)."""
    W, H = p.width_mm, p.height_mm
    cx = W / 2.0
    prof = [(float(t), min(1.0, max(0.0, float(s)))) for t, s in p.outline["profile"]]
    prof, c, _said = closure_shaped(prof, float(p.outline["closure_share"]), p.cap_style, p.archetype)
    # [His review of 127, 130, 131 and 132, 2026-10-15, C (3), D (11)] its top and its foot as the concept shows them
    # (``END_ROUND``): a dome round, a base flat with its corners rounded — never the photo's ellipse, never steps
    prof, ends = rounded_ends(prof, p.outline.get("height_to_width"), p.outline.get("foot_cut_at_its_reflection") is True)
    eps = _TRACE_TOLERANCE_SHARE * H
    sil = _part_outline(prof, cx, W, H, eps, ends)

    def reach_at(t):
        """The traced half-width at ``t`` (a share of the height), read between the two rows about it."""
        for (t0, s0), (t1, s1) in zip(prof, prof[1:]):
            if t0 <= t <= t1:
                return s0 + (s1 - s0) * ((t - t0) / (t1 - t0) if t1 > t0 else 0.0)
        return prof[-1][1]
    cap_rows = [(t, s) for t, s in prof if t < c] + [(c, reach_at(c))]
    cap_region = _part_outline(cap_rows, cx, W, H, eps, ends)
    body_top = c * H
    body_h = H - body_top
    lh = body_h * 0.5
    ly = body_top + body_h * 0.26
    narrowest = min(s for t, s in prof if ly / H <= t <= (ly + lh) / H)
    lw = narrowest * W * 0.78                           # inside the body's narrowest reach, 11 % in from each edge
    label = p.label_zone or (cx - lw / 2.0, ly, lw, lh)
    lx, ly, lw, lh = label
    bulb_region = collar_region = None
    if (p.cap_style or "").lower() == "dropper" and len(cap_rows) >= 4:
        # [his goal for the pitch, B (9)] a dropper's bulb drawn as its own part over the collar — [his goal after the
        # pitch page, A (3)] split where the collar's own width ends (``closure_split``), the collar its own region;
        # else above its narrowest waist (where a bulb's round meets its collar), as before
        waist_t = closure_split(prof, c)
        if waist_t is None:
            # [His review of 127, 130, 131 and 132, 2026-10-15, D (11)] else where its width steps most — the bulb's foot
            # on its collar — never the first narrow row under its tip (128's two-row "bulb", its castle top)
            inner = [k for k in range(len(cap_rows) - 1) if 0.15 * c < cap_rows[k][0] < 0.9 * c]
            if inner:
                waist_t = cap_rows[max(inner, key=lambda k: abs(cap_rows[k + 1][1] - cap_rows[k][1]))][0]
        if waist_t is not None:
            b_rows = [(t, s) for t, s in cap_rows if t <= waist_t]
            k_rows = [(waist_t, reach_at(waist_t))] + [(t, s) for t, s in cap_rows if t > waist_t]
            if len(b_rows) >= 2:
                bulb_region = _part_outline(b_rows, cx, W, H, eps, ends)
            if len(k_rows) >= 2:
                collar_region = _part_outline(k_rows, cx, W, H, eps, ends)
            if bulb_region is not None and collar_region is not None:
                # the closure's own region its collar, as every dropper backbone draws it (``_dropper_bottle``, M3's):
                # the bulb its own part over it, so a gold collar's foil never runs under a bulb of another material
                cap_region = collar_region
    elif p.outline.get("collar_split") is not None and 0.0 < float(p.outline["collar_split"]) < c:
        # [His review of 127, 130, 131 and 132, 2026-10-15, D (11): "gold collar"; the lead's look at 134's flacon: its
        # gold collar under its plum cap drawn in plum] a closure its concept shows as two parts — a cap on its collar,
        # each read on the concept's map as its own part (``closure_parts_split``) — drawn as both: the cap its region
        # down to where the collar begins, the collar its own region below it, each in its own colour and finish
        split = float(p.outline["collar_split"])
        upper = [(t, s) for t, s in cap_rows if t < split] + [(split, reach_at(split))]
        lower = [(split, reach_at(split))] + [(t, s) for t, s in cap_rows if t > split]
        if len(upper) >= 2 and len(lower) >= 2:
            cap_region = _part_outline(upper, cx, W, H, eps, ends)
            collar_region = _part_outline(lower, cx, W, H, eps, ends)
    return ContainerBackbone(
        template.archetype, W, H, sil, cap_region, label, p.decoration_zone,
        anchors={"logo": (cx, ly + lh * 0.16), "product_name": (cx, ly + lh * 0.52)}, bulb_region=bulb_region,
        collar_region=collar_region)


#: [his test day finding 3, 2026-09-30, design 117: his concept stands its squeeze tube on its flip-top, and the drawing
#: stood it on its crimp] the forms drawn standing on their closure when their concept's trace shows them so — a squeeze
#: tube stands on its cap; every other form's narrow end in a picture is its neck, and it is drawn closure up
STOOD_ON_CLOSURE_FORMS = ("tube",)
#: [his answer after test day finding 3, 2026-09-30, (4): "round" — his 50 mm is the tube's round diameter] the forms
#: whose confirmed width is their ROUND width and whose drawing is as wide as their flat end, π/2 of it: a squeeze tube,
#: round at its cap and pressed flat at its crimp (his concept's own proportion: 180 over 78.5 is 2.29, the picture 2.31)
ROUND_WIDTH_FORMS = ("tube",)


def drawn_width_mm(archetype: str, width_mm: float) -> float:
    """The width a form is DRAWN at from its confirmed width: a round-width form's flat end, π/2 of it; every other
    form's width as confirmed."""
    return width_mm * math.pi / 2.0 if archetype in ROUND_WIDTH_FORMS else width_mm


def _stood_on_closure(bb: ContainerBackbone, p: ContainerProfile) -> ContainerBackbone:
    """The backbone turned end over end, as its concept stands it: its outline and its closure mirrored top to bottom;
    its label mirrored with them unless the profile set it (a person's, or the confirmed front's — the drawing's own
    numbers, measured on this turned outline); its anchors laid again top down in the label, the logo above the name,
    as every builder lays them — never mirrored, which would set the name above the logo."""
    H = bb.height_mm

    def flip(segs):
        if segs is None:
            return None
        return [s.model_copy(update={k: H - getattr(s, k) for k in ("y", "y1", "y2") if hasattr(s, k)}) for s in segs]
    lx, ly, lw, lh = bb.label_zone
    if p.label_zone is None:
        ly = H - ly - lh
    cx = bb.width_mm / 2.0
    return replace(bb, silhouette=flip(bb.silhouette), cap_region=flip(bb.cap_region),
                   collar_region=flip(bb.collar_region), bulb_region=flip(bb.bulb_region), label_zone=(lx, ly, lw, lh),
                   anchors={"logo": (cx, ly + lh * 0.16), "product_name": (cx, ly + lh * 0.52)})


def _mirrored(right: list, W: float, H: float) -> list[Segment]:
    """§BH71 PART 3: a closed outline symmetric about the vertical axis, from its right half — ``right`` the points from
    the top of the axis down to its foot — drawn as a traced outline is (``_curve_through``): smooth through every point,
    a turn sharper than ``_CORNER_DEG`` kept a corner, every handle inside the box."""
    cx = W / 2.0
    left = [(2.0 * cx - x, y) for x, y in reversed(right)]
    return [MoveTo(x=right[0][0], y=right[0][1])] + _curve_through(right, W, H) + _curve_through(left, W, H) \
        + [ClosePath()]


def _band(right: list, top: float, foot: float, W: float, H: float) -> list[Segment]:
    """The part of a mirrored outline between heights ``top`` and ``foot`` (mm), closed across at both — a closure's
    region, read off the same points the silhouette is drawn through."""
    def reach(y):
        for (x0, y0), (x1, y1) in zip(right, right[1:]):
            if y0 <= y <= y1 and y1 > y0:
                return x0 + (x1 - x0) * (y - y0) / (y1 - y0)
        return right[-1][0]
    inner = [(x, y) for x, y in right if top < y < foot]
    part = [(reach(top), top)] + inner + [(reach(foot), foot)]
    cx = W / 2.0
    left = [(2.0 * cx - x, y) for x, y in reversed(part)]
    return [MoveTo(x=part[0][0], y=part[0][1])] + _curve_through(part, W, H) + [LineTo(x=left[0][0], y=left[0][1])] \
        + _curve_through(left, W, H) + [ClosePath()]


def _tin(p: ContainerProfile) -> ContainerBackbone:
    """§BH71 PART 3, the owner's goal of 2026-09-28: "Add each as a shape the system can draw." A TIN, drawn in plan —
    its lid seen from above as it is held: ROUND a circle across the plan's narrower side, SLIDE the plan's rectangle
    with softly rounded corners. No hinge, no clasp, no pans — those are the compact's: a tin's lid lifts, twists or
    slides. The lid is its face, whole."""
    W, H = p.width_mm, p.height_mm
    cx, cy = W / 2.0, H / 2.0
    if (p.variant or "").lower() == "round":
        d = min(W, H)
        sil, cap_region = _circle(cx, cy, d / 2.0), _circle(cx, cy, d / 2.0)
        lw, lh = d * 0.64, d * 0.50
    elif (p.variant or "").lower() == OVAL_LID:     # [§BH71 PART 3: a learned oval tin — the ellipse in the plan]
        sil, cap_region = _ellipse(cx, cy, W / 2.0, H / 2.0), _ellipse(cx, cy, W / 2.0, H / 2.0)
        lw, lh = W * 0.64, H * 0.50
    else:
        corner_share = (p.outline or {}).get("corner_share")                    # the traced lid's own corner
        if corner_share is None:                    # [His goal after the pitch page, A (3)] a traced 0.0 is square
            corner_share = 0.06
        r = min(W, H) * min(0.5, max(0.0, float(corner_share)))
        sil, cap_region = _rrect(0, 0, W, H, r), _rrect(0, 0, W, H, r)
        lw, lh = W * 0.76, H * 0.56
    label = p.label_zone or (cx - lw / 2.0, cy - lh / 2.0, lw, lh)
    lx, ly, lw, lh = label
    return ContainerBackbone("tin", W, H, sil, cap_region, label, p.decoration_zone,
                             anchors={"logo": (cx, ly + lh * 0.18), "product_name": (cx, ly + lh * 0.55)})


def _sachet(p: ContainerProfile) -> ContainerBackbone:
    """§BH71 PART 3: a SACHET, drawn flat as it lies — the pouch, its heat seal across the top with the tear notch cut
    into its edge (its "closure": where it is torn open) and across the foot, and down one side (three-side) or both
    (four-side); the print inside the seals."""
    W, H = p.width_mm, p.height_mm
    seal = max(3.0, min(W, H) * 0.06)
    notch, ny = seal * 0.6, seal * 0.5
    sil = [MoveTo(x=0, y=0), LineTo(x=W, y=0), LineTo(x=W, y=ny - notch / 2.0), LineTo(x=W - notch, y=ny),
           LineTo(x=W, y=ny + notch / 2.0), LineTo(x=W, y=H), LineTo(x=0, y=H), ClosePath()]
    cap_region = [MoveTo(x=0, y=0), LineTo(x=W, y=0), LineTo(x=W, y=ny - notch / 2.0), LineTo(x=W - notch, y=ny),
                  LineTo(x=W, y=ny + notch / 2.0), LineTo(x=W, y=seal), LineTo(x=0, y=seal), ClosePath()]
    left = seal
    right = seal if (p.variant or "").lower() == "four_side" else 0.0
    inner_w, inner_h = W - left - right, H - 2.0 * seal
    lw, lh = inner_w * 0.80, inner_h * 0.62
    lx, ly = left + (inner_w - lw) / 2.0, seal + inner_h * 0.16
    label = p.label_zone or (lx, ly, lw, lh)
    lx, ly, lw, lh = label
    return ContainerBackbone("sachet", W, H, sil, cap_region, label, p.decoration_zone,
                             anchors={"logo": (lx + lw / 2.0, ly + lh * 0.14),
                                      "product_name": (lx + lw / 2.0, ly + lh * 0.45)})


def _oval_stick(p: ContainerProfile) -> ContainerBackbone:
    """§BH71 PART 3: an OVAL STICK closed and standing — a deodorant's or a body stick's: its snap-on cap over the top
    fifth, as wide as the case; the case below it carrying the print. Not a lipstick: a lipstick's cap takes half its
    height and it stops at 40 mm across."""
    W, H = p.width_mm, p.height_mm
    oval = (p.variant or "").lower() != "round"
    sil, cap_region, label = _capped_body(
        p, cap_share=0.22, cap_width=1.0, top_radius=W * (0.22 if oval else 0.30),
        base_radius=W * (0.10 if oval else 0.16), label_cover=(0.72, 0.58))
    lx, ly, lw, lh = label
    return ContainerBackbone("oval_stick", W, H, sil, cap_region, label, p.decoration_zone,
                             anchors={"logo": (W / 2.0, ly + lh * 0.16), "product_name": (W / 2.0, ly + lh * 0.52)})


def _aerosol(p: ContainerProfile) -> ContainerBackbone:
    """§BH71 PART 3: an AEROSOL CAN standing — its body printed all round; STRAIGHT, its shoulder rolled just under an
    overcap as wide as the can; NECKED, its shoulder domed into a neck under a narrower cap; its foot a rim. Not a
    bottle: a can has no neck to label and no screw cap."""
    W, H = p.width_mm, p.height_mm
    cx = W / 2.0
    necked = (p.variant or "").lower() == "necked"
    cap_w = W * (0.62 if necked else 0.98)
    cap_h = H * (0.16 if necked else 0.20)
    c = cap_w / 2.0
    if necked:
        right = [(cx, 0.0), (cx + c * 0.82, 0.0), (cx + c, cap_h * 0.12), (cx + c, cap_h),
                 (cx + c * 0.92, cap_h + H * 0.01), (cx + W * 0.40, cap_h + H * 0.05), (W, cap_h + H * 0.11),
                 (W, H * 0.97), (cx + W * 0.46, H), (cx, H)]
        body_top = cap_h + H * 0.11
    else:
        right = [(cx, 0.0), (cx + c * 0.86, 0.0), (cx + c, cap_h * 0.10), (cx + c, cap_h),
                 (cx + W * 0.47, cap_h + H * 0.005), (W, cap_h + H * 0.03), (W, H * 0.97), (cx + W * 0.46, H), (cx, H)]
        body_top = cap_h + H * 0.03
    sil = _mirrored(right, W, H)
    cap_region = _band(right, 0.0, cap_h, W, H)
    body_h = H - body_top
    lw, lh = W * 0.80, body_h * 0.56
    label = p.label_zone or (cx - lw / 2.0, body_top + body_h * 0.20, lw, lh)
    lx, ly, lw, lh = label
    return ContainerBackbone("aerosol", W, H, sil, cap_region, label, p.decoration_zone,
                             anchors={"logo": (cx, ly + lh * 0.16), "product_name": (cx, ly + lh * 0.52)})


#: §BH71 PART 3: an ampoule's right half, by variant — (x as a share of the width from the axis, y as a share of the
#: height) — and the height its tip ends at: a GLASS ampoule's bulb above a snap-off neck, a PLASTIC one's flat
#: twist-off tab above its neck, a sample VIAL's stopper over a straight vial
_AMPOULE_HALVES = {
    "glass": ([(0.0, 0.0), (0.18, 0.01), (0.28, 0.06), (0.30, 0.14), (0.24, 0.24), (0.20, 0.30), (0.22, 0.34),
               (0.46, 0.40), (0.50, 0.46), (0.50, 0.92), (0.40, 0.99), (0.0, 1.0)], 0.30),
    "plastic": ([(0.0, 0.0), (0.35, 0.0), (0.35, 0.18), (0.14, 0.20), (0.14, 0.24), (0.44, 0.28), (0.50, 0.33),
                 (0.50, 0.93), (0.40, 0.99), (0.0, 1.0)], 0.20),
    "vial": ([(0.0, 0.0), (0.46, 0.0), (0.50, 0.02), (0.50, 0.22), (0.44, 0.23), (0.44, 0.94), (0.36, 0.99),
              (0.0, 1.0)], 0.225),
}


def _ampoule(p: ContainerProfile) -> ContainerBackbone:
    """§BH71 PART 3: an AMPOULE or a sample VIAL standing — a slim single dose with its tip, tab or stopper on top
    (``_AMPOULE_HALVES``). Not a bottle: no cap on a shoulder, and some ten millimetres across."""
    W, H = p.width_mm, p.height_mm
    cx = W / 2.0
    half, tip = _AMPOULE_HALVES.get((p.variant or "").lower(), _AMPOULE_HALVES["glass"])
    right = [(cx + u * W, v * H) for u, v in half]
    sil = _mirrored(right, W, H)
    cap_region = _band(right, 0.0, tip * H, W, H)
    body_top = tip * H + H * 0.10
    body_h = H - body_top
    lw, lh = W * 0.78, body_h * 0.62
    label = p.label_zone or (cx - lw / 2.0, body_top + body_h * 0.12, lw, lh)
    lx, ly, lw, lh = label
    return ContainerBackbone("ampoule", W, H, sil, cap_region, label, p.decoration_zone,
                             anchors={"logo": (cx, ly + lh * 0.14), "product_name": (cx, ly + lh * 0.50)})


#: §BH61(c): the BUILDERS are this module's; the KEYS are the one declaration's, and a mismatch is a
#: refusal at import rather than a form that silently cannot be drawn.
_ARCHETYPES = {"bottle": _bottle, "jar": _jar, "tube": _tube, "compact": _compact,
               "lipstick": _lipstick, "mascara": _mascara, "pencil": _pencil,
               "tin": _tin, "sachet": _sachet, "oval_stick": _oval_stick, "aerosol": _aerosol,
               "ampoule": _ampoule}
if set(_ARCHETYPES) != set(_declared.ARCHETYPES):
    raise RuntimeError(
        "CONTAINER_ARCHETYPE_REGISTRY_DIVERGED: silhouettes draws %s; the declaration names %s "
        "(apps/pipeline/targets/container/archetypes.py)"
        % (sorted(_ARCHETYPES), sorted(_declared.ARCHETYPES)))

SUPPORTED_ARCHETYPES = tuple(_ARCHETYPES)


def _drawable(profile: ContainerProfile) -> ContainerProfile:
    """§BH65(e): a COPY to draw from, each missing dimension filled with THIS form's own declared `nominal`.
    The profile itself is never changed — its None is the record saying "not known"."""
    nominal = _declared.nominal_of(profile.archetype)
    fill = {}
    if profile.height_mm is None:
        fill["height_mm"] = float(nominal["height_mm"])
    if profile.width_mm is None:
        fill["width_mm"] = float(nominal["width_mm"])
    if profile.neck_ratio is None and "neck_ratio" in _declared.proportions_of(profile.archetype):
        fill["neck_ratio"] = float(nominal["neck_ratio"])
    return replace(profile, **fill) if fill else profile


def build_backbone(profile: ContainerProfile) -> ContainerBackbone:
    """Dispatch to the archetype's OWN builder — and REFUSE, by name, an archetype the declaration does not know.

    §BH65(e): this was a `.get()` on the builder table whose DEFAULT WAS THE BOTTLE BUILDER, under the docstring
    "Unknown archetype → bottle", and a test pinned it. It is the §BH61(a) defect in its last hiding place: a
    `.get()` default that is a FUNCTION, which §BH64(c)'s guard — written to catch a `.get()` whose default is an
    archetype LITERAL — could not see. (Spelled out here without the code itself, because the guard that now
    catches the shape reads docstring lines as source, and would catch its own history.) Removing the bottle-shaped dimension defaults exposed it: an unknown form now has
    no bottle size to borrow, and the bottle builder it fell back to could no longer draw it."""
    builder = _ARCHETYPES.get(profile.archetype)
    if builder is None:
        raise _declared.ArchetypeUnresolved(["build_backbone(profile.archetype)"], value=profile.archetype)
    drawable = _drawable(profile)
    if profile.archetype in ROUND_WIDTH_FORMS:
        # [his answer after test day finding 3, (4)] drawn as wide as its flat end; its round end its confirmed width
        drawable = replace(drawable, width_mm=drawn_width_mm(profile.archetype, drawable.width_mm))
    drawn = builder(drawable)
    # §BH71 PART 1: a form drawn in elevation whose profile carries the concept's traced outline is drawn from it;
    # its template drew ``drawn`` and stays the fallback
    if profile.outline is not None and profile.outline.get("kind") == "profile":
        traced = _traced_elevation(drawable, drawn)
        # [his test day finding 3: a squeeze tube its concept stands on its cap is drawn standing on its cap]
        if profile.archetype in STOOD_ON_CLOSURE_FORMS and profile.outline.get("stands_on_closure") is True:
            return _stood_on_closure(traced, drawable)
        return traced
    return drawn
