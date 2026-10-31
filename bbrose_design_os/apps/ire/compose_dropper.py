"""2C-2E-CORR-2 — the refined serum-dropper concept sheet.

Second human Gate-2 review: CORR-1's closure was top-heavy (Ø28 collar over a
Ø33 body), the collar read as a flat band, the bulb as a capsule, the liquid
line made the bottle look open, and the glass shading read as stripes. This
revision draws the HUMAN-AMENDED closure (collar Ø24 × 11.5, bulb 13 × 21.5,
3 mm visible neck) as one believable physical assembly, a six-role editable
rose-gold material, a continuous cylindrical glass recipe with no fill-level
ellipse, and a unified stacked product-name block — all native editable
vectors; every sheen/shade is NONPRINTING visualization.

Authority: HUMAN_CONFIRMED_CONCEPT_ONLY / NOT_MANUFACTURER_VERIFIED —
visual concept values, never tooling dimensions.
"""
from __future__ import annotations

from typing import Optional

from apps.ire.graph import (
    ClosePath,
    Color,
    CubicTo,
    Document,
    GradientFill,
    GradientStop,
    Group,
    LineTo,
    MoveTo,
    Path,
    Rect,
    SolidFill,
    Stroke,
    TextRun,
)
from apps.ire import back_panel
from apps.ire import brand_mark as _brand_mark
from apps.ire import colour_roles
from apps.ire.nodes import (centered_text, image_node, intrinsic_aspect,
                            rect_clip)
# §BB7(g)(a) — SHARED, NOT COPIED. §BD(b) ruled that a direct-print front wraps
# long names, and `wrap_name` is the algorithm that ruling names. Writing the
# dropper a second line-breaker would manufacture the defect class §BB7 is
# about — two composers drawing one front and disagreeing — inside the commit
# that plumbs them together. The import direction is measured and not assumed:
# in a virgin interpreter `import apps.ire.compose_container` leaves
# `apps.ire.compose_dropper` absent from `sys.modules`, because this package's
# two references to this module (`targets/container/__init__.py:1060`,
# `:896`) are both function-local. So there is no cycle.
from apps.ire.compose_container import wrap_name
from apps.ire.container_brand_usage import text_ink_top

_PAGE_W, _PAGE_H = 210.0, 297.0
_INK = Color.from_hex("#2A2426")
_K = 0.5523

#: §5/§7 unified material system — separate editable roles with the
#: process/spot authority state carried onto the sheet swatches.
MATERIALS = {
    "BODY_BASE": ("#D8BEB8", "frosted dusty-rose glass — PROCESS, "
                             "authority UNVERIFIED"),
    "PRODUCT_FILL": ("#C9A6A0", "internal product tint — PROCESS, "
                                "authority UNVERIFIED"),
    "GLASS_BASE": ("#EFE8E3", "clear glass base — PROCESS, "
                              "authority UNVERIFIED"),
    "ROSE_GOLD_BASE": ("#BC7480", "blush-copper base — METALLIC SPOT, "
                                  "authority UNVERIFIED"),
    "ROSE_GOLD_LIGHT": ("#EBD0BC", "warm champagne highlight — "
                                   "NONPRINTING viz"),
    "ROSE_GOLD_SPECULAR": ("#FDEFE4", "narrow specular — NONPRINTING viz"),
    "ROSE_GOLD_SHADOW": ("#6E3A46", "deep warm-metal shadow — "
                                    "NONPRINTING viz"),
    "BULB_DARK_PLUM": ("#3F2A33", "smooth dark plum — PROCESS, "
                                  "authority UNVERIFIED"),
    "TYPE_WINE": ("#5A2C3A", "typography — PROCESS, authority UNVERIFIED"),
}

NONPRINTING = (
    "GLASS_INNER_WALL", "LEFT_EDGE_CURVATURE", "RIGHT_EDGE_CURVATURE",
    "CENTRAL_GLASS_LIGHT", "GLASS_SPECULAR", "SHOULDER_REFRACTION",
    "SHOULDER_ELLIPSE", "BASE_REFRACTION", "COLLAR_ROSE_GOLD_LIGHT",
    "COLLAR_ROSE_GOLD_SPECULAR", "COLLAR_ROSE_GOLD_SHADOW",
    "COLLAR_TOP_RIM", "COLLAR_BOTTOM_RIM", "BULB_HIGHLIGHT",
)


def _hex(name):
    """A product material's colour as drawn: through the palette layer (§BH50(d), below)."""
    return palette_row(name)["color"]


#: §BH50(d), OWNER RULED 2026-09-13 — THE PRODUCT'S COLOUR ROLES, declared by the composer and resolved through the
#: palette layer (apps/ire/colour_roles.py) to brand_gov. A material of the product takes the §BH39 role whose
#: MEASURED cluster its colour falls in, at the record's own clustering tolerance (ΔE76 ≤ 8, the record's
#: `measured_by`), the nearest when two hold it; the ΔE76 to that cluster and how far the drawn colour moves are
#: measured beside each (image_checks' CIE76, the instrument the brand record was measured with). Every other
#: material falls in no cluster — the nearest is 13.46 away (PRODUCT_FILL to accent_nude) — and keeps its literal
#: with no role: assigning one is the owner's line, and a mechanical nearest-swatch mapping would recolour the
#: chosen product by up to ΔE76 39. The ink falls in accent_dark's cluster, which carries no brand swatch, so it
#: resolves to its own literal (SURFACE_FALLBACK); the PRODUCTION route §BH39(b) allows it is unreachable from any
#: emit (materials_retrieval.query raises). Warm Gold's cluster holds no product colour (the nearest, ROSE_GOLD_LIGHT,
#: is 19.7 from it), so Warm Gold is drawn nowhere on the product.
PRODUCT_COLOUR_ROLES = {
    "BODY_BASE": "accent_nude",           # 6.66 to #DDC8B7 -> Warm Nude #E8C9B3; the glass moves 9.54
    "GLASS_BASE": "ground_cream",         # 1.23 to #F2E8E2 -> Warm Cream #FAF3EC; moves 3.92
    "ROSE_GOLD_LIGHT": "accent_nude",     # 4.32 to #DDC8B7 -> Warm Nude #E8C9B3; moves 3.01
    "ROSE_GOLD_SPECULAR": "ground_cream",  # 3.95 to #F2E8E2 (accent_nude's #F9EBD5 at 5.88) -> Warm Cream; moves 3.44
    "INK": "accent_dark",                 # 6.73 to #231916 -> no brand swatch: its own literal
}
PALETTE_CLUSTER_TOLERANCE_DE76 = 8.0
PALETTE_SCHEMA = "container_palette/1.0"
_PALETTE_SURFACE = {colour_roles.SURFACE_KEY: "apps/ire/compose_dropper.py::compose_dropper_sheet"}


def _literal(name):
    return _INK if name == "INK" else Color.from_hex(MATERIALS[name][0])


def palette_row(name) -> dict:
    """One product colour through the palette layer: its role or none, the colour drawn, and the source."""
    lit = _literal(name)
    role = PRODUCT_COLOUR_ROLES.get(name)
    if role is None:
        return {"name": name, "literal": lit.to_hex(), "role": None, "hex": lit.to_hex(), "color": lit,
                "source": colour_roles.SOURCE_SURFACE_FALLBACK, "tier": None,
                "evidence": "no role: the colour falls in no §BH39 measured cluster within ΔE76 8", "verdicts": []}
    return dict(colour_roles.resolve_role(_PALETTE_SURFACE, role, lit), name=name, literal=lit.to_hex())


def product_palette() -> dict:
    """container_palette/1.0 — every product material and the ink, as the layer resolved them for this sheet."""
    return {"schema_version": PALETTE_SCHEMA,
            "rule": "a material takes the §BH39 role whose measured cluster its colour falls in, at the record's own "
                    "clustering tolerance, the nearest when two hold it; every other material keeps its literal",
            "tolerance_delta_e76": PALETTE_CLUSTER_TOLERANCE_DE76, "record": "docs/brand_gov/colour_roles_1_0.json",
            "rows": [{k: v for k, v in palette_row(n).items() if k != "color"} for n in (*MATERIALS, "INK")]}


# ---------------------------------------------------------------------------
# the bottle — local mm: x 0..33, y 0..104 (y down; bulb top at 0)
# height composition: 21.5 bulb + 11.5 collar + 3 visible neck + 68 body
# ---------------------------------------------------------------------------

def _bottle_group(g: dict, ox: float, oy: float, s: float, *,
                  name="Bottle", clip=None,
                  front_children: Optional[list] = None,
                  name_prefix: str = "") -> Group:
    W = g["body_diameter_mm"]                       # 33
    H = g["total_height_mm"]                        # 104
    collar_w = g["collar_diameter_mm"] or 24.0      # 24
    collar_h = g["collar_height_mm"]                # 11.5
    bulb_h = g["bulb_height_mm"]                    # 21.5
    bulb_w = g.get("bulb_width_mm") or collar_w * 0.54   # 13
    neck_w = g["neck_diameter_mm"] or 10.0          # 10
    neck_vis = g.get("visible_neck_mm") or 3.0      # 3
    base_t = g["base_thickness_mm"] or 3.5
    sh_r = g["shoulder_radius_mm"] or 3.0
    frost = g.get("frost_intensity", 0.7)
    trans = g.get("translucency", 0.35)

    cx = W / 2.0
    y_collar = bulb_h                               # 21.5
    y_neck = bulb_h + collar_h                      # 33
    y_body = y_neck + neck_vis                      # 36
    flare_end = y_body + sh_r + 1.4
    y_base = H - base_t                             # 100.5

    def X(x):
        return ox + x * s

    def Y(y):
        return oy + y * s

    def N(n):
        return f"{name_prefix}{n}"

    def ellipse(name_, cx_, cy_, rx, ry, fill=None, op=1.0, stroke=None):
        k = _K
        return Path(name=name_, segments=[
            MoveTo(x=X(cx_ - rx), y=Y(cy_)),
            CubicTo(x1=X(cx_ - rx), y1=Y(cy_ - ry * k), x2=X(cx_ - rx * k),
                    y2=Y(cy_ - ry), x=X(cx_), y=Y(cy_ - ry)),
            CubicTo(x1=X(cx_ + rx * k), y1=Y(cy_ - ry), x2=X(cx_ + rx),
                    y2=Y(cy_ - ry * k), x=X(cx_ + rx), y=Y(cy_)),
            CubicTo(x1=X(cx_ + rx), y1=Y(cy_ + ry * k), x2=X(cx_ + rx * k),
                    y2=Y(cy_ + ry), x=X(cx_), y=Y(cy_ + ry)),
            CubicTo(x1=X(cx_ - rx * k), y1=Y(cy_ + ry), x2=X(cx_ - rx),
                    y2=Y(cy_ + ry * k), x=X(cx_ - rx), y=Y(cy_)),
            ClosePath()],
            fill=(SolidFill(color=fill, opacity=op) if fill else None),
            stroke=stroke)

    def curved_band(name_, x_out, x_in, y0, y1, color, op):
        """A narrow band whose inner edge bows with the cylinder — never a
        broad rectangular bar."""
        return Path(name=name_, segments=[
            MoveTo(x=X(x_out), y=Y(y0)),
            LineTo(x=X(x_out), y=Y(y1)),
            CubicTo(x1=X(x_out), y1=Y(y1),
                    x2=X(x_in), y2=Y(y1 - (y1 - y0) * 0.05),
                    x=X(x_in), y=Y(y1 - (y1 - y0) * 0.08)),
            LineTo(x=X(x_in), y=Y(y0 + (y1 - y0) * 0.08)),
            CubicTo(x1=X(x_in), y1=Y(y0 + (y1 - y0) * 0.05),
                    x2=X((x_out + x_in) / 2), y2=Y(y0 + 0.6),
                    x=X(x_out), y=Y(y0)),
            ClosePath()],
            fill=SolidFill(color=color, opacity=op))

    # --- body silhouette (§10): neck top → restrained flat shoulder →
    #     straight cylinder → softly elliptical base --------------------------
    nw2, bw2, rb = neck_w / 2.0, W / 2.0, 1.9
    body = [
        MoveTo(x=X(cx - nw2), y=Y(y_body)),
        LineTo(x=X(cx + nw2), y=Y(y_body)),
        LineTo(x=X(cx + nw2), y=Y(y_body + 0.9)),
        CubicTo(x1=X(cx + nw2), y1=Y(flare_end - 0.4),
                x2=X(cx + bw2 - sh_r * 0.4), y2=Y(flare_end - sh_r),
                x=X(cx + bw2), y=Y(flare_end)),
        LineTo(x=X(cx + bw2), y=Y(H - rb)),
        CubicTo(x1=X(cx + bw2), y1=Y(H - rb + rb * _K),
                x2=X(cx + bw2 - rb + rb * _K), y2=Y(H),
                x=X(cx + bw2 - rb), y=Y(H)),
        CubicTo(x1=X(cx + bw2 * 0.5), y1=Y(H + 1.3),
                x2=X(cx - bw2 * 0.5), y2=Y(H + 1.3),
                x=X(cx - bw2 + rb), y=Y(H)),
        CubicTo(x1=X(cx - bw2 + rb - rb * _K), y1=Y(H),
                x2=X(cx - bw2), y2=Y(H - rb + rb * _K),
                x=X(cx - bw2), y=Y(H - rb)),
        LineTo(x=X(cx - bw2), y=Y(flare_end)),
        CubicTo(x1=X(cx - bw2 + sh_r * 0.4), y1=Y(flare_end - sh_r),
                x2=X(cx - nw2), y2=Y(flare_end - 0.4),
                x=X(cx - nw2), y=Y(y_body + 0.9)),
        ClosePath(),
    ]

    # --- §9 continuous cylindrical glass recipe ------------------------------
    kids: list = [
        Path(name=N("GLASS_OUTER_WALL"), segments=body,
             fill=SolidFill(color=_hex("BODY_BASE"),
                            opacity=round(min(trans + 0.15, 0.55), 3))),
        # §8: the internal product reads as a subtle vertical tonal tint —
        # NO horizontal liquid line, no open-vessel ellipse
        Path(name=N("PRODUCT_FILL_APPEARANCE"), segments=[
            MoveTo(x=X(cx - bw2 + 2.0), y=Y(flare_end + 1.5)),
            LineTo(x=X(cx + bw2 - 2.0), y=Y(flare_end + 1.5)),
            LineTo(x=X(cx + bw2 - 2.0), y=Y(y_base - 0.5)),
            LineTo(x=X(cx - bw2 + 2.0), y=Y(y_base - 0.5)),
            ClosePath()],
            fill=GradientFill(
                kind="linear", x1=X(cx), y1=Y(flare_end + 1.5),
                x2=X(cx), y2=Y(y_base),
                stops=[GradientStop(offset=0.0, color=_hex("PRODUCT_FILL"),
                                    opacity=0.24),
                       GradientStop(offset=0.45, color=_hex("PRODUCT_FILL"),
                                    opacity=0.48),
                       GradientStop(offset=1.0, color=_hex("PRODUCT_FILL"),
                                    opacity=0.58)])),
        curved_band(N("LEFT_EDGE_CURVATURE"), 0.0, 2.4, flare_end + 0.8,
                    y_base - 0.8, Color.from_hex("#B79B95"), 0.26),
        curved_band(N("RIGHT_EDGE_CURVATURE"), W, W - 2.4, flare_end + 0.8,
                    y_base - 0.8, Color.from_hex("#A98D88"), 0.34),
        # broad soft central light — the cylinder's facing tone
        curved_band(N("CENTRAL_GLASS_LIGHT"), cx - 3.6, cx + 3.6,
                    flare_end + 2.0, y_base - 2.0,
                    Color.from_hex("#FFFFFF"), 0.06),
        Path(name=N("FROST_TREATMENT"), segments=body,
             fill=SolidFill(color=Color.from_hex("#FFFFFF"),
                            opacity=round(0.06 + frost * 0.12, 3))),
        # narrow specular following the curvature
        curved_band(N("GLASS_SPECULAR"), cx - 8.4, cx - 7.5,
                    flare_end + 2.5, y_base - 3.0,
                    Color.from_hex("#FFFFFF"), 0.26),
        # inner wall depth — the glass thickness read
        Path(name=N("GLASS_INNER_WALL"), segments=[
            MoveTo(x=X(cx - bw2 + 1.1), y=Y(flare_end + 1.0)),
            LineTo(x=X(cx - bw2 + 1.1), y=Y(y_base - 0.6)),
            MoveTo(x=X(cx + bw2 - 1.1), y=Y(flare_end + 1.0)),
            LineTo(x=X(cx + bw2 - 1.1), y=Y(y_base - 0.6))],
            stroke=Stroke(color=Color.from_hex("#FFFFFF"), width_mm=0.32,
                          opacity=0.32)),
        ellipse(N("SHOULDER_REFRACTION"), cx, flare_end + 0.5, bw2 - 1.6,
                0.9, fill=Color.from_hex("#F4E9E4"), op=0.28),
        ellipse(N("SHOULDER_ELLIPSE"), cx, flare_end, bw2 - 0.6, 1.1,
                fill=Color.from_hex("#F4E9E4"), op=0.32),
        Path(name=N("GLASS_BASE_THICKNESS"), segments=[
            MoveTo(x=X(cx - bw2 + 0.8), y=Y(y_base)),
            CubicTo(x1=X(cx - bw2 * 0.4), y1=Y(y_base + 1.1),
                    x2=X(cx + bw2 * 0.4), y2=Y(y_base + 1.1),
                    x=X(cx + bw2 - 0.8), y=Y(y_base)),
            LineTo(x=X(cx + bw2 - 0.8), y=Y(H - 0.5)),
            CubicTo(x1=X(cx + bw2 * 0.4), y1=Y(H + 0.6),
                    x2=X(cx - bw2 * 0.4), y2=Y(H + 0.6),
                    x=X(cx - bw2 + 0.8), y=Y(H - 0.5)),
            ClosePath()],
            fill=SolidFill(color=_hex("GLASS_BASE"), opacity=0.40)),
        ellipse(N("BASE_REFRACTION"), cx, y_base + base_t * 0.45,
                bw2 * 0.55, base_t * 0.28,
                fill=Color.from_hex("#FFFFFF"), op=0.22),
    ]

    # --- §7 visible neck + connection ---------------------------------------
    kids += [
        Rect(name=N("NECK_GLASS"), x=X(cx - nw2 + 0.3), y=Y(y_neck),
             w=(neck_w - 0.6) * s, h=(neck_vis + 1.0) * s,
             fill=SolidFill(color=_hex("BODY_BASE"), opacity=0.55)),
        Path(name=N("NECK_CONNECTION_HINT"), segments=[
            MoveTo(x=X(cx - nw2 + 0.8), y=Y(y_neck + neck_vis * 0.55)),
            LineTo(x=X(cx + nw2 - 0.8), y=Y(y_neck + neck_vis * 0.55))],
            stroke=Stroke(color=_INK, width_mm=0.12, opacity=0.35)),
    ]

    # --- §4/§5 collar: refined cylindrical metal, six editable roles --------
    cw2 = collar_w / 2.0
    rim_ry = 0.85
    collar_body = [
        MoveTo(x=X(cx - cw2), y=Y(y_collar + rim_ry)),
        CubicTo(x1=X(cx - cw2 * 0.5), y1=Y(y_collar - 0.2),
                x2=X(cx + cw2 * 0.5), y2=Y(y_collar - 0.2),
                x=X(cx + cw2), y=Y(y_collar + rim_ry)),
        # curved cylindrical side with a slight inset at the neck connection
        CubicTo(x1=X(cx + cw2), y1=Y(y_neck - 2.0),
                x2=X(cx + cw2 - 0.5), y2=Y(y_neck - 0.8),
                x=X(cx + cw2 - 0.75), y=Y(y_neck + 0.3)),
        CubicTo(x1=X(cx + cw2 * 0.5), y1=Y(y_neck + 1.1),
                x2=X(cx - cw2 * 0.5), y2=Y(y_neck + 1.1),
                x=X(cx - cw2 + 0.75), y=Y(y_neck + 0.3)),
        CubicTo(x1=X(cx - cw2 + 0.5), y1=Y(y_neck - 0.8),
                x2=X(cx - cw2), y2=Y(y_neck - 2.0),
                x=X(cx - cw2), y=Y(y_collar + rim_ry)),
        ClosePath(),
    ]
    collar_grad = GradientFill(
        kind="linear", x1=X(cx - cw2), y1=Y(y_collar),
        x2=X(cx + cw2), y2=Y(y_collar),
        stops=[GradientStop(offset=0.0, color=_hex("ROSE_GOLD_SHADOW")),
               GradientStop(offset=0.22, color=_hex("ROSE_GOLD_BASE")),
               GradientStop(offset=0.40, color=_hex("ROSE_GOLD_LIGHT")),
               GradientStop(offset=0.52, color=_hex("ROSE_GOLD_SPECULAR")),
               GradientStop(offset=0.62, color=_hex("ROSE_GOLD_LIGHT")),
               GradientStop(offset=0.85, color=_hex("ROSE_GOLD_BASE")),
               GradientStop(offset=1.0, color=_hex("ROSE_GOLD_SHADOW"))])
    kids += [
        Path(name=N("COLLAR_ROSE_GOLD_BASE"), segments=collar_body,
             fill=collar_grad),
        curved_band(N("COLLAR_ROSE_GOLD_LIGHT"), cx - cw2 * 0.46,
                    cx - cw2 * 0.10, y_collar + 1.1, y_neck - 0.5,
                    _hex("ROSE_GOLD_LIGHT"), 0.45),
        curved_band(N("COLLAR_ROSE_GOLD_SPECULAR"), cx - cw2 * 0.26,
                    cx - cw2 * 0.16, y_collar + 0.9, y_neck - 0.4,
                    _hex("ROSE_GOLD_SPECULAR"), 0.75),
        curved_band(N("COLLAR_ROSE_GOLD_SHADOW"), cx + cw2 * 0.94,
                    cx + cw2 * 0.58, y_collar + 1.0, y_neck - 0.5,
                    _hex("ROSE_GOLD_SHADOW"), 0.42),
        ellipse(N("COLLAR_TOP_RIM"), cx, y_collar + rim_ry, cw2 - 0.3,
                rim_ry, fill=_hex("ROSE_GOLD_LIGHT"), op=0.9),
        ellipse(N("COLLAR_BOTTOM_RIM"), cx, y_neck - 0.1, cw2 - 0.6,
                0.55, fill=_hex("ROSE_GOLD_SHADOW"), op=0.5),
    ]

    # --- §6 bulb: narrow base, gentle lower taper, smooth elongated dome ----
    bwh = bulb_w / 2.0                   # 6.5
    base_hw = bwh * 0.62                 # narrow base entering the collar
    bulb = [
        MoveTo(x=X(cx - base_hw), y=Y(y_collar + 1.4)),
        CubicTo(x1=X(cx - bwh * 0.96), y1=Y(bulb_h * 0.78),
                x2=X(cx - bwh), y2=Y(bulb_h * 0.52),
                x=X(cx - bwh), y=Y(bulb_h * 0.40)),
        CubicTo(x1=X(cx - bwh), y1=Y(bulb_h * 0.16),
                x2=X(cx - bwh * 0.52), y2=Y(0.7),
                x=X(cx), y=Y(0.7)),
        CubicTo(x1=X(cx + bwh * 0.52), y1=Y(0.7),
                x2=X(cx + bwh), y2=Y(bulb_h * 0.16),
                x=X(cx + bwh), y=Y(bulb_h * 0.40)),
        CubicTo(x1=X(cx + bwh), y1=Y(bulb_h * 0.52),
                x2=X(cx + bwh * 0.96), y2=Y(bulb_h * 0.78),
                x=X(cx + base_hw), y=Y(y_collar + 1.4)),
        ClosePath(),
    ]
    kids += [
        Path(name=N("BULB_DARK_PLUM"), segments=bulb,
             fill=SolidFill(color=_hex("BULB_DARK_PLUM"))),
        curved_band(N("BULB_HIGHLIGHT"), cx - bwh * 0.52, cx - bwh * 0.18,
                    bulb_h * 0.18, bulb_h * 0.66,
                    Color.from_hex("#FFFFFF"), 0.14),
        Path(name=N("silhouette-outline"), segments=body,
             stroke=Stroke(color=_INK, width_mm=0.22, opacity=0.5)),
    ]
    if front_children:
        kids += front_children
    return Group(name=name, role="product", children=kids, clip=clip)



def _extent(segments) -> tuple[float, float, float, float]:
    """(xmin, xmax, ymin, ymax) over every point a segment names — end points and controls."""
    xs, ys = [], []
    for sg in segments:
        for ax, ay in (("x", "y"), ("x1", "y1"), ("x2", "y2")):
            if hasattr(sg, ax) and hasattr(sg, ay):
                xs.append(float(getattr(sg, ax)))
                ys.append(float(getattr(sg, ay)))
    return min(xs), max(xs), min(ys), max(ys)


def _bottle_group_m3(backbone, g: dict, ox: float, oy: float, s: float, *,
                     name="Bottle", clip=None,
                     front_children: Optional[list] = None,
                     name_prefix: str = "") -> Group:
    """§BH48(b)(ii) — M3 DRAWS. The accepted fit's three outlines (glass, collar, dark
    closure), already in the profile's local mm box, are the drawing source; the parametric
    material stack is re-hung on their measured extents under the SAME node names the
    fidelity reader requires (REQUIRED_MATERIAL_OBJECTS), so every downstream reader sees the
    same objects. Nothing here reads a typed number for a shape; ``g`` supplies only the
    material impressions (frost, translucency) and the base band a silhouette does not hold.
    """
    frost = g["frost_intensity"]                     # the derived geometry carries every key
    trans = g["translucency"]
    base_t = g["base_thickness_mm"]

    def X(x):
        return ox + x * s

    def Y(y):
        return oy + y * s

    def N(n):
        return f"{name_prefix}{n}"

    def T(segs):
        """The outline mapped into the sheet — the accepted curves survive exactly."""
        out = []
        for sg in segs:
            if isinstance(sg, MoveTo):
                out.append(MoveTo(x=X(sg.x), y=Y(sg.y)))
            elif isinstance(sg, LineTo):
                out.append(LineTo(x=X(sg.x), y=Y(sg.y)))
            elif isinstance(sg, CubicTo):
                out.append(CubicTo(x1=X(sg.x1), y1=Y(sg.y1), x2=X(sg.x2), y2=Y(sg.y2), x=X(sg.x), y=Y(sg.y)))
            else:
                out.append(ClosePath())
        return out

    # the parametric composer's own helpers, twinned here so `_bottle_group` stays byte-identical
    def ellipse(name_, cx_, cy_, rx, ry, fill=None, op=1.0, stroke=None):
        k = _K
        return Path(name=name_, segments=[
            MoveTo(x=X(cx_ - rx), y=Y(cy_)),
            CubicTo(x1=X(cx_ - rx), y1=Y(cy_ - ry * k), x2=X(cx_ - rx * k), y2=Y(cy_ - ry), x=X(cx_), y=Y(cy_ - ry)),
            CubicTo(x1=X(cx_ + rx * k), y1=Y(cy_ - ry), x2=X(cx_ + rx), y2=Y(cy_ - ry * k), x=X(cx_ + rx), y=Y(cy_)),
            CubicTo(x1=X(cx_ + rx), y1=Y(cy_ + ry * k), x2=X(cx_ + rx * k), y2=Y(cy_ + ry), x=X(cx_), y=Y(cy_ + ry)),
            CubicTo(x1=X(cx_ - rx * k), y1=Y(cy_ + ry), x2=X(cx_ - rx), y2=Y(cy_ + ry * k), x=X(cx_ - rx), y=Y(cy_)),
            ClosePath()],
            fill=(SolidFill(color=fill, opacity=op) if fill else None), stroke=stroke)

    def curved_band(name_, x_out, x_in, y0, y1, color, op):
        return Path(name=name_, segments=[
            MoveTo(x=X(x_out), y=Y(y0)), LineTo(x=X(x_out), y=Y(y1)),
            CubicTo(x1=X(x_out), y1=Y(y1), x2=X(x_in), y2=Y(y1 - (y1 - y0) * 0.06), x=X(x_in), y=Y(y1 - (y1 - y0) * 0.08)),
            LineTo(x=X(x_in), y=Y(y0 + (y1 - y0) * 0.08)),
            CubicTo(x1=X(x_in), y1=Y(y0 + (y1 - y0) * 0.06), x2=X(x_out), y2=Y(y0), x=X(x_out), y=Y(y0)),
            ClosePath()], fill=SolidFill(color=color, opacity=op))

    glass, collar, bulb = backbone.silhouette, backbone.collar_region, backbone.bulb_region
    gx0, gx1, gy0, gy1 = _extent(glass)
    cx0, cx1, cy0, cy1 = _extent(collar)
    bx0, bx1, by0, by1 = _extent(bulb)
    cx = (gx0 + gx1) / 2.0
    bw2 = (gx1 - gx0) / 2.0
    cw2 = (cx1 - cx0) / 2.0
    bwh = (bx1 - bx0) / 2.0
    y_base = gy1 - base_t
    # the shoulder: where the glass first reaches (nearly) its full width — read from the outline
    shoulder_y = gy0
    for sg in glass:
        if hasattr(sg, "x") and hasattr(sg, "y") and abs(float(sg.x) - gx1) < 0.3:
            shoulder_y = float(sg.y)
            break
    flare_end = shoulder_y
    # the glass the fit starts inside the collar — its top half-width, read from the outline's
    # points within 0.3 mm of its top: the NECK_GLASS object the fidelity reader measures
    # (§BH50(f)(8) line 7, 2026-09-17: rule 3 now reads the visible waist below the collar; this half-width still
    #  sizes the drawn NECK_GLASS, whose top edge alone closure_assembly_connection reads — no fidelity rule reads the
    #  width any more. Annotated, never rewritten, §AZ0(u).)
    top_pts = [float(sg.x) for sg in glass if hasattr(sg, "x") and hasattr(sg, "y") and float(sg.y) <= gy0 + 0.3]
    if len(top_pts) < 2:
        raise ValueError("M3_FIT_OUTLINE_TOP_UNRESOLVED: the glass outline has no two points within 0.3 mm of its top")
    g_top_hw = (max(top_pts) - min(top_pts)) / 2.0
    body = T(glass)
    kids: list = [
        Rect(name=N("NECK_GLASS"), x=X(cx - g_top_hw + 0.3), y=Y(gy0),
             w=(2.0 * g_top_hw - 0.6) * s, h=max(cy1 - gy0, 0.5) * s,
             fill=SolidFill(color=_hex("BODY_BASE"), opacity=0.55)),
        Path(name=N("GLASS_OUTER_WALL"), segments=body,
             fill=SolidFill(color=_hex("BODY_BASE"), opacity=round(min(trans + 0.15, 0.55), 3))),
        # the same tonal tint as the parametric group: the reader takes the strongest stop as the
        # fill's opacity (container_concept_fidelity._opacity), so the opacities sit on the stops
        Path(name=N("PRODUCT_FILL_APPEARANCE"), segments=body,
             fill=GradientFill(kind="linear", x1=X(cx), y1=Y(flare_end + 1.5), x2=X(cx), y2=Y(y_base),
                               stops=[GradientStop(offset=0.0, color=_hex("PRODUCT_FILL"), opacity=0.24),
                                      GradientStop(offset=0.45, color=_hex("PRODUCT_FILL"), opacity=0.48),
                                      GradientStop(offset=1.0, color=_hex("PRODUCT_FILL"), opacity=0.58)])),
        curved_band(N("LEFT_EDGE_CURVATURE"), gx0, gx0 + 2.4, flare_end + 0.8, y_base - 0.8, Color.from_hex("#B79B95"), 0.26),
        curved_band(N("RIGHT_EDGE_CURVATURE"), gx1, gx1 - 2.4, flare_end + 0.8, y_base - 0.8, Color.from_hex("#A98D88"), 0.34),
        curved_band(N("CENTRAL_GLASS_LIGHT"), cx - 3.6, cx + 3.6, flare_end + 2.0, y_base - 2.0, Color.from_hex("#FFFFFF"), 0.06),
        Path(name=N("FROST_TREATMENT"), segments=body,
             fill=SolidFill(color=Color.from_hex("#FFFFFF"), opacity=round(0.06 + frost * 0.12, 3))),
        curved_band(N("GLASS_SPECULAR"), cx - 8.4, cx - 7.5, flare_end + 2.5, y_base - 3.0, Color.from_hex("#FFFFFF"), 0.26),
        Path(name=N("GLASS_INNER_WALL"), segments=[
            MoveTo(x=X(gx0 + 1.1), y=Y(flare_end + 1.0)), LineTo(x=X(gx0 + 1.1), y=Y(y_base - 0.6)),
            MoveTo(x=X(gx1 - 1.1), y=Y(flare_end + 1.0)), LineTo(x=X(gx1 - 1.1), y=Y(y_base - 0.6))],
             stroke=Stroke(color=Color.from_hex("#FFFFFF"), width_mm=0.32, opacity=0.35)),
        ellipse(N("SHOULDER_REFRACTION"), cx, flare_end + 0.5, bw2 - 1.6, 0.9, fill=Color.from_hex("#F4E9E4"), op=0.28),
        ellipse(N("SHOULDER_ELLIPSE"), cx, flare_end, bw2 - 0.6, 1.1, fill=Color.from_hex("#F4E9E4"), op=0.32),
        Path(name=N("GLASS_BASE_THICKNESS"), segments=[
            MoveTo(x=X(gx0 + 0.8), y=Y(y_base)),
            CubicTo(x1=X(cx - bw2 * 0.4), y1=Y(y_base + 1.1), x2=X(cx + bw2 * 0.4), y2=Y(y_base + 1.1), x=X(gx1 - 0.8), y=Y(y_base)),
            LineTo(x=X(gx1 - 0.8), y=Y(gy1)), LineTo(x=X(gx0 + 0.8), y=Y(gy1)), ClosePath()],
             fill=SolidFill(color=_hex("GLASS_BASE"), opacity=0.40)),
        ellipse(N("BASE_REFRACTION"), cx, y_base + base_t * 0.45, bw2 - 2.2, base_t * 0.35, fill=Color.from_hex("#FFFFFF"), op=0.22),
        Path(name=N("NECK_CONNECTION_HINT"), segments=[
            MoveTo(x=X(cx - cw2 * 0.6), y=Y(cy1 - 0.2)), LineTo(x=X(cx + cw2 * 0.6), y=Y(cy1 - 0.2))],
             stroke=Stroke(color=_hex("ROSE_GOLD_SHADOW"), width_mm=0.25, opacity=0.35)),
    ]
    collar_grad = GradientFill(
        kind="linear", x1=X(cx0), y1=Y(cy0), x2=X(cx1), y2=Y(cy0),
        stops=[GradientStop(offset=0.0, color=_hex("ROSE_GOLD_SHADOW")),
               GradientStop(offset=0.22, color=_hex("ROSE_GOLD_BASE")),
               GradientStop(offset=0.40, color=_hex("ROSE_GOLD_LIGHT")),
               GradientStop(offset=0.52, color=_hex("ROSE_GOLD_SPECULAR")),
               GradientStop(offset=0.62, color=_hex("ROSE_GOLD_LIGHT")),
               GradientStop(offset=0.85, color=_hex("ROSE_GOLD_BASE")),
               GradientStop(offset=1.0, color=_hex("ROSE_GOLD_SHADOW"))])
    kids += [
        Path(name=N("COLLAR_ROSE_GOLD_BASE"), segments=T(collar), fill=collar_grad),
        curved_band(N("COLLAR_ROSE_GOLD_LIGHT"), cx - cw2 * 0.46, cx - cw2 * 0.10, cy0 + 1.1, cy1 - 0.5, _hex("ROSE_GOLD_LIGHT"), 0.45),
        curved_band(N("COLLAR_ROSE_GOLD_SPECULAR"), cx - cw2 * 0.26, cx - cw2 * 0.16, cy0 + 0.9, cy1 - 0.4, _hex("ROSE_GOLD_SPECULAR"), 0.75),
        curved_band(N("COLLAR_ROSE_GOLD_SHADOW"), cx + cw2 * 0.94, cx + cw2 * 0.58, cy0 + 1.0, cy1 - 0.5, _hex("ROSE_GOLD_SHADOW"), 0.42),
        ellipse(N("COLLAR_TOP_RIM"), cx, cy0 + 0.85, cw2 - 0.3, 0.85, fill=_hex("ROSE_GOLD_LIGHT"), op=0.9),
        ellipse(N("COLLAR_BOTTOM_RIM"), cx, cy1 - 0.1, cw2 - 0.6, 0.55, fill=_hex("ROSE_GOLD_SHADOW"), op=0.5),
        Path(name=N("BULB_DARK_PLUM"), segments=T(bulb), fill=SolidFill(color=_hex("BULB_DARK_PLUM"))),
        curved_band(N("BULB_HIGHLIGHT"), cx - bwh * 0.52, cx - bwh * 0.18, by0 + (by1 - by0) * 0.18, by0 + (by1 - by0) * 0.66, Color.from_hex("#FFFFFF"), 0.14),
        Path(name=N("silhouette-outline"), segments=body, stroke=Stroke(color=_INK, width_mm=0.22, opacity=0.5)),
    ]
    if front_children:
        kids += front_children
    return Group(name=name, role="product", children=kids, clip=clip)


# ---------------------------------------------------------------------------
# §11/§12 front typography — one unified stacked name block, live text
# ---------------------------------------------------------------------------

#: §Z1/§Z2 — the front's type sizes, in POINTS, chosen as type.
#:
#: These were fractions of ``zh`` (the zone's height in millimetres, times the
#: panel's drawing scale) stored in a field the emitter passes straight to
#: ``setFont`` unconverted. `BRAND_PT` is the size that arithmetic was reaching
#: for: 5% of 42.3 mm is 2.115 mm, which is 5.995 pt — so the intent was ~6 pt
#: all along and the emitted artefact carried 2.5803 pt.
#:
#: `SUPPORT_PT` and `NET_CONTENT_PT` keep the values they already had, where
#: the literal floor of a ``max(literal, zh * f)`` dominated at every scale in
#: use. They are NOT raised to the print floor here: that is a proportion
#: decision about the front, and §Z2(d) keeps a design pass out of a unit fix.
#: They stay below the capability-table floor and the axis keeps saying so.
#:
#: §BH50(b), OWNER RULED 2026-09-13 — THE FLOOR STANDS AND THE DESIGN MOVES. The design question the
#: paragraph above held open is answered: 5.0 pt is a legibility rule, not a July rule, so both runs are
#: set AT the §W2 floor BODY_FRONT carries (5.0 pt; its method is machine-proposed, §AA3), in the role
#: map's faces, and 3.4 / 3.0 stay here as history. Nothing shrinks and no floor moves. The leads below
#: re-lay the stack so it keeps, at the new size, the two clearances it was built to keep, and
#: `front_copy_fit` records whether the confirmed front zone holds each run at the size it is set.
BRAND_PT = 6.0
SUPPORT_PT = 5.0        # §BH50(b); 3.4 until 2026-09-13
NET_CONTENT_PT = 5.0    # §BH50(b); 3.0 until 2026-09-13

#: §Z1(b) RUNNING BACKWARDS — the name block's leading, in EM.
#:
#: The line below this comment used to read ``leading = name_size * 1.06``,
#: where ``leading`` is added to a millimetre coordinate and ``name_size`` is a
#: point size. §Z1(b) forbids deriving a point size from a millimetre length;
#: this is the same law in the other direction, and it is the more expensive
#: direction, because nothing about the result looks wrong. ``1.06`` reads as
#: an em ratio — tight leading, which is exactly what the code comment beside
#: it claims. Applied to points and added to millimetres, it is a ratio of
#: mm-per-pt, and the leading it actually sets is::
#:
#:     1.06 / (25.4 / 72) = 3.0047244094488192 em
#:
#: Three times the type size, in a block whose own comment says "two serif
#: lines with tight leading, one visual element". At ``name_min=9.0`` that is
#: a 9.54 mm gap between two 9 pt lines.
#:
#: `NAME_LEADING_INCUMBENT_EM` is the ratio the artwork HAD, not the ratio the
#: expression looked like it was asking for. Setting 1.06 em would close the
#: hero gap from 9.54 mm to 3.3655 mm and the flat panel's from 6.89 mm to
#: 2.4306 mm — a visible re-proportioning of the front, which §AA2(d) forbade
#: in that sprint, and of the name block specifically, which §AA2(c) reserved
#: to the owner as a design ruling. So the unit path was corrected and the
#: proportion was left exactly where it was.
#:
#: The effect of THAT fix on production output was zero. That was the point of
#: the number chosen, and `apps/ire/tests/test_wip_leading_units.py` measures
#: it rather than asserting it. What the fix bought is that the 3.005 is
#: written down: it was previously a units bug wearing a design decision's
#: clothes, and it became a design decision the owner could price and rule on.
#: §AC1 is that ruling, and it is below.
#:
#: §AC1(f) — THIS NUMBER KEEPS A NAME EVEN THOUGH IT IS NO LONGER THE SETTING.
#: "Deleting the number would delete the evidence that the accident happened."
#: It is referenced by `tools/wiv_leading_comparison.py`, by WI-P's price-of-
#: the-ruling test, and by WI-Y's side-by-side, all of which need the exact
#: float rather than a rounded 3.0047.
NAME_LEADING_INCUMBENT_EM = 3.0047244094488192

#: §AC1 — THE LEADING, RULED. THE METRIC FLOOR BINDS AND THE SETTING IS 2.0 em.
#:
#: §AB3 reserved this and WI-V rendered 1.06 / 2.0 / 3.0047 at true scale.
#: §AC1's ruling, in its own words: *"the metric floor is the constraint. At
#: 1.06 em the line boxes overlap by 0.959 mm. That is a FAIL. The leading
#: rises until the metric floor clears, and the number it must clear is
#: 1.362 em."*
#:
#: WHY THE METRIC FLOOR AND NOT THE INK FLOOR (§AC1(a)). At 1.06 em the drawn
#: letters still clear by 1.073 mm, and WI-V reported that honestly. It is not
#: a permission. It is a property of the two strings `Rose` and `Damascena`,
#: neither of which has a descender, and §AB2(f) has already ruled that the
#: next SKU will have a different name. The ink clearance therefore dies on the
#: first product name containing a `g`, `j`, `p`, `q` or `y`, with nothing in
#: the pipeline to notice. §AC0(a): when two floors disagree, the one that
#: survives a change of content binds.
#:
#: WHY 2.0 AND NOT 1.362 (§AC1(b)/(c)). Clearing zero is not a design; the
#: floor says only which values are legal. 2.0 em clears it by 0.638 em, which
#: is enough headroom to absorb a descender without re-ruling, and keeps two
#: lines legible as one unit. The owner named this a bet that can be lost:
#: it loses if the 2.0 em render at true scale reads as two unrelated lines
#: rather than one lockup, and `NAME_LEADING_INCUMBENT_EM` is then the
#: fallback and needs no new ruling to take.
#:
#: WHAT MOVES. The hero gap goes 9.540 -> 6.350 mm and panel 8's 6.890 ->
#: 4.586 mm. This is the first change to the front's proportion in this arc
#: that is NOT zero-effect, and it is authorised. The support stack is
#: unaffected in its clearance — WI-U anchored it to the name block's last
#: baseline precisely so the leading could move without dragging the block
#: below it, and `apps/ire/tests/test_wiy_leading_metric_floor.py` measures
#: that rather than assuming it.
#:
#: THE IDENTIFIER, AND A READING I AM DECLARING BECAUSE I MAY HAVE IT WRONG.
#: §AC7 says "Keep `NAME_LEADING_EM = 3.0047244094488192` named (AC1(f))".
#: Read literally that is the identifier keeping the old value; read against
#: AC1(f)'s own stated reason — *"as the recorded incumbent... deleting the
#: number would delete the evidence"* — it is the NUMBER keeping A name. I
#: have taken the second reading, so `NAME_LEADING_EM` is what the composer
#: reads and is 2.0, and the incumbent is preserved above under a name that
#: says what it is. The first reading would leave a constant called
#: "the name leading, in em" holding a value that is not the name leading,
#: in the one file whose sprint was about a comment that lied about this
#: exact quantity. If the owner meant the first reading it is a one-line
#: swap and this paragraph is the notice.
NAME_LEADING_EM = 2.0

#: §AB2(a) — WHY THE SUPPORT LINE FOLLOWS THE NAME INSTEAD OF THE ZONE.
#:
#: These two replaced ``zy + zh * 0.545`` and ``zy + zh * 0.61``. The defect
#: they fix is a PLACEMENT bug and not a size verdict: the owner ruled 9.0 pt
#: correct and ruled the −1.389 mm overlap the thing to repair, by moving the
#: support line and not by shrinking the name.
#:
#: The mechanism, because a fraction is not obviously wrong until you see what
#: it is a fraction OF. ``leading`` is PHYSICAL — 9.54 mm at 9.0 pt, and the
#: same 9.54 mm however large the panel is drawn. The support line's ``0.545``
#: was a fraction of the DRAWN zone, so it moved with the panel scale while the
#: block above it did not. The two were independent, and at the only scale that
#: prints they collided. That is also why the sheet concealed it: at s=1.22 the
#: fraction had grown 22% and the block had not, so panel 5 cleared by
#: +0.891 mm while 1:1 overlapped by −1.389.
#:
#: Anchoring both to the name block's last baseline makes the whole support
#: stack one physical object, like the name block above it, so it cannot be
#: pulled apart by a scale again — and, deliberately, so it cannot be pulled
#: apart by a LEADING either. WI-V renders 1.06 / 2.0 / 3.0047 em next, and
#: against a fixed fraction two of those three would have collided by different
#: amounts; the owner would have been comparing collisions rather than leading.
#: No leading is chosen here — §AB3 reserves that — but the comparison is now
#: about the thing it claims to be about.
#:
#: THE VALUES ARE MEASURED, NOT PICKED. 1.175 em reproduces the clearance of
#: the 6.5 pt render — the only front layout in this repository that has ever
#: been rendered, seen, and called clean ("the layout is clean and every run
#: clears"). Read off that artefact it is +1.5194 mm; 1.175 em delivers
#: +1.5188 mm at 9.0 pt, the 0.0006 being what a 3-decimal em constant costs.
#: 0.866 em reproduces the old support→net baseline distance of 2.7495 mm: the
#: exact ratio is 0.8659842519685039 and 0.866 is its 3-decimal rounding, which
#: lands the net-content baseline 5.0e-5 mm — fifty nanometres — below where it
#: sat. So the one relationship in this block that was never broken is carried
#: across unchanged rather than re-tuned. §AB2(b) authorises
#: the proportion to change; it does not ask for anything else to be rebalanced,
#: and nothing else was.
#:
#: Both are em of the NAME size, so the support stack tracks the type it is
#: supporting. Dimensionally pt × (mm/pt) × em = mm, which is §Z1(b)'s clause
#: (A) satisfied by an explicit conversion rather than by a bare coefficient —
#: `apps/ire/unit_analysis.py` reads this file at 0 findings.
#:
#: §BH50(b) — RE-LAID AT 5.0 PT, THE SAME TWO MEASUREMENTS KEPT. Raising the two runs to 5.0 pt grows
#: their ascent and descent, so at 1.175 / 0.866 em the clearance below the name fell from 1.518 mm to
#: 0.915 mm and the support-to-net gap from 1.267 mm to 0.347 mm, measured off the emitted PDF with the
#: instrument `apps/ire/tests/test_wiu_front_collision.py` uses. The re-lay keeps both, re-measured the
#: same way: 1.365 em holds 1.518 mm below the name and 1.156 em holds 1.268 mm between the two runs, at
#: every panel scale. The stack grows downward into the empty band, whose question §AB2(c) still
#: reserves; 1.175 and 0.866 held the same clearances at 3.4 and 3.0 pt and stay here as history.
SUPPORT_LEAD_EM = 1.365   # §BH50(b); 1.175 until 2026-09-13
NET_LEAD_EM = 1.156       # §BH50(b); 0.866 until 2026-09-13

#: §AC1(e) — THE FRONT'S NAME LINES, AND WHY THIS PARAMETER EXISTS AT ALL.
#:
#: These two strings were literals inside `_front_typography`. §AC1(e) makes
#: lifting them out **the named exception to "no chained fixes"**, for one
#: reason and not for tidiness: §AC1(d)'s negative control requires the same
#: guard run on a synthetic descender-bearing name, and *you cannot render a
#: descender-bearing name into a string that is not a variable.* The parameter
#: IS the instrument. It is named as an exception in §AC1(e) so it cannot be
#: cited later as a precedent for cleaning up code near a fix.
#:
#: THE DEFAULT REPRODUCES TODAY'S ARTWORK EXACTLY and every caller takes it, so
#: production output does not move by one bit on this account. What DOES move
#: is the leading, above, and keeping the two separable is the whole point:
#: the owner is about to judge a render, and a render that changed two things
#: is a render that answers neither question.
#:
#: WHAT IS **NOT** DONE HERE, RECORDED RATHER THAN FIXED. `compose_dropper_sheet`
#: takes a `product_name: str` and does not pass it here — the sheet's declared
#: name and the front's drawn name are independent, and have been. Wiring them
#: together is NOT within §AC1(e), because this block is exactly two lines and
#: a free-form name is one string: `test_wiu_front_collision.py` already
#: composes the sheet with "Rose Damascena Night Repair Oil" and the front
#: still draws "Rose"/"Damascena". Connecting them requires ruling **how a
#: product name breaks across the lines of the lockup**, which is a design
#: ruling nobody has made and which §AC does not contain. The disconnect is
#: therefore a finding with its size measured, not a repair taken on the way
#: past. `name_lines` accepts any length so the ruling, when it comes, has
#: somewhere to land.
#:
#: §BH68(d), OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE) — THE RULING CAME: "THE DROPPER'S "Rose" /
#: "Damascena" is FACIAL SERUM again. Derive it from the product record; print nothing where the record is silent."
#: `FRONT_NAME_LINES = ("Rose", "Damascena")` is GONE, as FRONT_DESCRIPTOR went at §BH67(c)2. The front's name is the
#: sheet's `product_name` — the product record's name, which both production callers already pass (the container
#: target, `spec["product_name"]`; the exploration render, the same or the owner's own knob) — and where the ruled
#: hierarchy supplies a name tier, that tier, as §BB7(g)(a) wired. HOW IT BREAKS ACROSS THE LOCKUP is read as the
#: composer's own `wrap_name` at the name's point size, the function every supplied line already passes through here
#: (§BB7(g)(a), §BD(b)): "Rose Damascena" still breaks into "Rose" / "Damascena", bit for bit. A record with no name
#: prints no name. [2026-09-25, THE OWNER'S ANSWER TO THE §BH68 REPORT: where a line the wrap sets does not fit the
#: front's safe area, the name breaks into the fewest lines, up to four, that do — `front_name_lines` below.]

#: §BB7(g)(a) — the dropper front's DESCRIPTOR tier, named for exactly the
#: reason §AC1(e) named the two name literals: a string that only exists inside
#: a function body cannot be supplied, cannot be defaulted against, and cannot
#: be asserted about from outside. `descriptor` below now defaults to this, and
#: the default reproduces today's artwork to the character.
#:
#: THIS IS A DIFFERENT PRODUCT'S COPY FROM THE ONE `front_hierarchy.DESCRIPTOR`
#: HOLDS, AND THAT IS THE WHOLE REASON THE PLUMBING STOPS SHORT OF A SOURCE.
#: §BB7(a) ruled `FACIAL SERUM` for the container front. This string is
#: `N I G H T   R E P A I R   O I L` — letter-spaced, and describing an OIL.
#: The owner's instruction on §3 is in terms: *"the dropper fixture carries a
#: DIFFERENT product's copy … Do not overwrite one product's copy with
#: another's."* So `compose_dropper_sheet` learns to ACCEPT a hierarchy and no
#: production caller passes one; `targets/container/__init__.py` is untouched
#: by this commit. `test_bb7g_no_container_descriptor_on_the_dropper` below
#: makes that refusal executable rather than a promise in a comment.
#:
#: NOT REGISTERED IN `reserved_copy.py` AND NOT REGISTERED HERE EITHER. The
#: string is product copy that no register lists, which is a finding carried to
#: `OWNER_REVIEW_QUEUE.md` and deliberately not repaired on the way past (§AC):
#: registering copy is a claim about what the copy IS, and that is the question
#: the owner reserved.
#:
#: §BH67(c)2 RULED THE SOURCE, 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md:23350,
#: LIVE): "The dropper's "NIGHT REPAIR OIL" and "30 ml / 1.01 fl. oz." are the
#: same defect as FACIAL SERUM. Derive both from the product record; where the
#: record is silent, print nothing." The constant `FRONT_DESCRIPTOR`
#: ("N I G H T   R E P A I R   O I L") and the net-content literal are GONE: the
#: descriptor is the caller's `descriptor` — `front_hierarchy.descriptor_for`,
#: §BH65(b)1's derivation from `Product.product_type` — and the net content its
#: `net_content`, `front_hierarchy.net_content_for`, `Product.net_weight` as
#: held. Absent, the line is not drawn.

#: §BC(h) — C10. The mark's width as a share of the front zone's width.
#:
#: 0.55 x 22.0 mm = 12.10 mm [task 52 since §BH54(f), 2026-09-18: 0.55 x 27.6 = 15.18 mm], which clears
#: ``container_brand_usage.MINIMUM_WIDTH_MM_PRINT`` (12.0). The incumbent 0.40
#: gave 8.80 mm and missed that floor by 3.2 mm — **on the branch production
#: actually reaches**, since ``targets/container/__init__.py:1050`` reads
#: ``if geometry is not None:`` and routes to ``compose_dropper_sheet``
#: whenever a confirmed dropper geometry exists, which for this product it
#: does. The failing mark was therefore not on a branch nobody renders.
#:
#: THE OWNER CHOSE 0.55 AND NOT THE 0.546 THE SITTING BRIEF ANTICIPATED, for
#: the 0.10 mm of headroom above the floor. The margin he was buying is real
#: and narrow: 0.545 gives 11.99 mm and STILL FAILS. ``test_c10_mark_width.py``
#: renders at that value and proves it fails, so the headroom is a measured
#: property of the artwork rather than a claim in a comment.
#:
#: NAMED RATHER THAN INLINE FOR ONE REASON: the guard is required to assert on
#: the EMITTED node's width and not on this factor, and the only way to prove a
#: width guard discriminates is to vary what feeds it and watch the emitted
#: geometry cross the floor. An inline literal cannot be varied, so the
#: negative control could not exist and the assertion could not be shown to be
#: non-vacuous.
#:
#: WHAT THIS DOES NOT DO. It does not wire ``evaluate_brand_usage`` to this
#: composer — §BC(h) names that a follow-up candidate and says in terms that it
#: MUST NOT be silently done alongside. Nor does it touch ``place()`` below,
#: whose ``nx``/``nw`` are fixed at 0.15/0.70 and so describe a 15.4 mm band
#: that no longer matches the drawn mark at any share. That mismatch predates
#: this ruling, is a placement record attesting a width the drawing does not
#: have, and is recorded here as a finding rather than repaired on the way
#: past (§AC).
MARK_ZONE_SHARE = 0.55


#: §BH50(b) — THE PANEL HOLDS THE SMALL COPY, OR THE COMPOSER SAYS SO BY NAME.
#: /1.1 since §BH50(g)(1) (re-typed §BH53(a)): `state` is judged against the safe area, not the zone — a /1.0 record's
#: HELD meant "inside the zone" and is read as such by the board, never re-labelled
FRONT_COPY_FIT_SCHEMA = "container_front_copy_fit/1.1"
FRONT_COPY_EXCEEDS_ZONE = "CONTAINER_FRONT_COPY_EXCEEDS_ZONE"
#: §BH50(g)(1), OWNER RULED — typed 2026-09-17, re-typed in OWNER RULING §BH53(a) (OWNER_BLOCKER_CLEARANCE.md
#: :21604-21607): "THE 16.0 mm SAFE AREA GOVERNS THE FRONT. Copy 5.5 mm inside it will be trimmed on a real run.
#: Gate 2 refuses the current front until it is re-laid, and that refusal is correct. Record the 22.0 mm zone
#: beside it as the outer bound." A run wider than the zone's confirmed safe area (width − 2 × safe_margin_mm) is
#: this code, with its millimetres, at acceptance; the zone's own code above keeps its meaning (decided without
#: the margin) and a run past both carries both, each true. Until §BH53 the verdict was against the zone and the
#: safe area read "MEASURED, NOT RULED" — kept in the record's note as history.
FRONT_COPY_EXCEEDS_SAFE_AREA = "CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA"
#: where the governing width came from — what §BH50(g)(3) asks of every width: his typed word, applied to the
#: margin the zone's own confirmed record carries
FRONT_COPY_LIMIT_SOURCE = ("OWNER_TYPED — §BH50(g)(1), re-typed in OWNER RULING §BH53(a) (OWNER_BLOCKER_CLEARANCE.md "
                           ":21604-21607, 2026-09-17): the safe area is the zone's width less twice its own confirmed "
                           "safe_margin_mm, read from the zone record and never defaulted; the zone's width is the "
                           "OUTER BOUND, recorded beside it")
#: §BH50(f)(3)/(5): a run the fit could not measure, a face the emitter would not draw, a zone with no
#: usable safe margin, or the axis this document has no instrument for — never read as held
FRONT_COPY_FIT_UNMEASURED = "CONTAINER_FRONT_COPY_FIT_UNMEASURED"
#: THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block of that date headed "Before I start
#: testing" — it carries no section number): "Make Gate 2 measure the front's height." A run whose INK leaves the zone's
#: safe band — above its top or below its foot, the zone's own safe margin in from each edge — measured at PRINT SIZE,
#: is this code with its millimetres; it joins readiness['front_copy'] and blocks acceptance, never the reconstruction,
#: like every other front-copy code. Where the band or a face cannot be measured the vertical axis stays UNMEASURED.
FRONT_COPY_EXCEEDS_SAFE_BAND = "CONTAINER_FRONT_COPY_EXCEEDS_SAFE_BAND"
_SMALL_COPY_RUNS = ("front-support", "front-net-content")
#: the hero name runs, measured beside the small copy VERDICT-FREE: whether the name is "front copy" under
#: §BH50(f)(3) is his line (its floors are 8.0 / 9.0 pt and §BD(b)'s clip rule, not the 5.0 pt floor)
#: [§BH50(g)(2), OWNER RULED — typed 2026-09-17, re-typed in §BH53(a) (OWNER_BLOCKER_CLEARANCE.md :21608-21609):
#: "THE PRODUCT NAME IS FRONT COPY — the floor and the safe area apply to it like any other run." From this commit
#: the name runs are JUDGED by the same walk — the safe-area verdict, the outer bound, the codes — and their own
#: floors (8.0 pt, §AB2's 9.0, §BD(b)'s clip rule) stand beside §W2's 5.0 pt, which already reaches them by surface;
#: nothing is softened. The sentence above is history.]
_NAME_RUN_PREFIX = "product-name-hero"
#: [THE OWNER'S SECOND ANSWER OF 2026-09-25: "Make Gate 2 measure the front's height." The cost below was paid: the
#: block is composed at s = 1 in memory (`print_size_runs`) and measured (`_vertical_fit`). This text is what the record
#: still carries where the block cannot be measured — no print-size block handed in, or no usable safe margin.]
FRONT_COPY_VERTICAL_COST = (
    "UNMEASURED — the sheet draws the front at 1.22x (hero) and at min(34 / zone width, 70 / zone height) (flat: "
    "1.5455x on a 22.0 mm zone; 1.2319x on task 52's 27.6 mm zone since §BH54(f)), never at print size; "
    "measuring the vertical fit means composing the front block at s = 1 in memory (the composer is pure) "
    "and holding its ink against the zone's height and safe margin; until then the axis blocks acceptance "
    "(§BH50(f)(5)) and never the reconstruction")


def _safe_area_mm(zone) -> tuple:
    """(safe_area_mm, safe_margin_mm) from the zone record — the zone's own confirmed margin, read and never
    defaulted (container_projection's `or 0.0` is the pattern not to copy). None when the record carries no
    usable margin: the safe-area leg is then UNMEASURED, and only that leg."""
    width = float(zone["width"])
    margin = zone.get("safe_margin_mm")
    try:
        margin = float(margin)
    except (TypeError, ValueError):
        return None, None
    if margin < 0 or 2 * margin >= width:
        return None, margin
    return round(width - 2 * margin, 4), margin


def _face_for(node, faces):
    """The face the NON-EXEMPT emitter draws this run with (pdf_ai._draw_text: the base role, then the
    run's own role name), or None when it would draw nothing — a refused role's runs are skipped, never set
    in a fallback face. §BH50(f)(3): the measurer used to substitute 'regular' for a role it lacked and
    raise KeyError when the map was empty, which parked the task (aria.py) — a reconstruction, and any
    exploration through this composer, blocked by its own measuring instrument."""
    return _face_for_role(node.font or "regular", faces)


def _face_for_role(role: str, faces):
    """`_face_for`'s rule for a run known by its role alone — the name's face before the name is drawn."""
    entry = _face_entry_for_role(role, faces)
    return entry[0] if entry else None


def _face_entry_for_role(role: str, faces):
    """``(face name, file path)`` the emitter draws a run of ``role`` with — `_face_for`'s rule — or None."""
    from apps.ire.font_roles import base_role
    return faces.get(base_role(role)) or faces.get(role)


#: THE OWNER'S ANSWER TO THE §BH68 REPORT, 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block of that date — his message
#: carries no section number): "BBR-SK-201's name on the dropper breaks into four lines, the only break that fits."
#: Built as a rule and not for one SKU — §BH68(d): "a hard-coded product word is one defect class, not one defect". The
#: ruled wrap stands wherever its lines fit the front's safe area; where one does not, measured as `front_copy_fit`
#: measures the drawn run, the name breaks at its own words into the FEWEST lines, up to this many, whose every line
#: fits — among them the break whose widest line is narrowest, the most room. On task 52's front (a 21.6 mm safe area)
#: two four-line breaks fit, "Rose / Damascena / Night / Repair Oil" (widest 19.59 mm) and "Rose / Damascena / Night
#: Repair / Oil" (21.03 mm); the first is drawn, and he was told before it was built that one line from him reverses
#: it. Where no break of four lines fits, the wrap's lines stand and Gate 2 refuses them by name, as before.
FRONT_NAME_MAX_LINES = 4
#: the role the front's name is drawn in (`_front_typography`), and so the face its break is measured in
_NAME_ROLE = "heading"


def front_name_lines(name: str, size_pt: float, zone) -> list[str]:
    """The front's name broken across the lockup — see FRONT_NAME_MAX_LINES.

    The ruled wrap's lines (`wrap_name`, §BD(b)) are measured first, in the face the emitter draws the name with at
    ``size_pt``, against the zone's own safe area (`_safe_area_mm`); where every one fits they stand, bit for bit.
    Where one does not, every break of the name's words into one to FRONT_NAME_MAX_LINES lines is measured, and the
    fewest lines that all fit are taken, the narrowest widest line first. Where the safe area or the face cannot be
    measured, or no break fits, the wrap's lines stand, and `front_copy_fit` names the verdict as it always has."""
    from itertools import combinations

    from apps.ire.text_metrics import resolve_metric_faces, text_width_mm_measured
    wrapped = wrap_name(name, size_pt, float(zone["width"]) * 0.94)
    safe_area_mm, _margin = _safe_area_mm(zone)
    # the sheet's own surface tag — the one its document declares — so the face is the one the emitter draws
    face = _face_for_role(_NAME_ROLE, resolve_metric_faces(_PALETTE_SURFACE))
    if safe_area_mm is None or face is None:
        return wrapped
    size_mm = size_pt * back_panel.MM_PER_PT

    def widest(lines):
        widths = [text_width_mm_measured(line, size_mm, face) for line in lines]
        return None if None in widths else max(widths)

    held = widest(wrapped)
    if held is None or held <= safe_area_mm:
        return wrapped
    words = name.split()
    for count in range(1, min(FRONT_NAME_MAX_LINES, len(words)) + 1):
        fits = []
        for cuts in combinations(range(1, len(words)), count - 1):
            bounds = (0, *cuts, len(words))
            lines = [" ".join(words[a:b]) for a, b in zip(bounds, bounds[1:])]
            width = widest(lines)
            if width is not None and width <= safe_area_mm:
                fits.append((width, lines))
        if fits:
            return min(fits, key=lambda fit: fit[0])[1]
    return wrapped


#: what the record's "vertical" says where the axis was measured (the owner's second answer of 2026-09-25)
FRONT_COPY_VERTICAL_MEASURE = (
    "MEASURED at print size — the front block composed at s = 1 in memory, each run's ink from its own glyph outlines "
    "in the face the emitter draws it with, against the zone's safe band (its safe margin in from the top edge and "
    "from the foot); a run past either edge is CONTAINER_FRONT_COPY_EXCEEDS_SAFE_BAND with its millimetres, at "
    "acceptance, never the reconstruction")


def print_size_runs(g, zone, logo_path, *, name_lines, descriptor, net_content, logo_master=None) -> list[dict]:
    """The front block composed at PRINT SIZE — s = 1 — in memory: the composition FRONT_COPY_VERTICAL_COST named.
    Every text run, its baseline measured from the zone's top edge. The composer is pure: the block is measured and
    dropped, and the sheet draws nothing twice (the owner's second answer of 2026-09-25).

    [The same answer's bug 3: ``logo_master`` — the approved vector master the sheet was handed — goes in too, so the
    block measured is the block drawn: whether a mark resolves decides whether the ``front-brand`` run is set.]"""
    kids, _placements, _logo, (_zx, zy, _zw, _zh) = _front_typography(
        g, zone, 0.0, 0.0, 1.0, logo_path, name_lines=name_lines, descriptor=descriptor, net_content=net_content,
        **_brand_mark.master_kwargs(logo_master))
    runs, stack = [], list(kids)
    while stack:
        node = stack.pop()
        if isinstance(node, Group):
            stack.extend(node.children)
        elif isinstance(node, TextRun):
            runs.append({"name": str(node.name), "text": node.text, "size_pt": float(node.size_pt),
                         "font": node.font, "baseline_mm": node.y - zy})
    return sorted(runs, key=lambda r: r["baseline_mm"])


def _vertical_fit(print_runs, zone, faces, copy_runs=_SMALL_COPY_RUNS) -> tuple[list, list, bool]:
    """``(rows, codes, measured)``: every judged run of the print-size block — the name lines and the small copy, as the
    horizontal walk judges them — its INK read from its own glyph outlines in the face the emitter draws it with
    (`text_metrics.ink_extent_em`, never a cap-height model), against the zone's safe band: the zone's own safe margin
    in from its top edge and from its foot. A run past either edge is FRONT_COPY_EXCEEDS_SAFE_BAND with its
    millimetres; a placeholder's fit is a geometric fact and never copy verified (§BH50(f)(2)); where the band, the
    block or a face gives nothing to measure, the axis is UNMEASURED and says why (§BH50(f)(5): never HELD)."""
    from apps.ire.text_metrics import ink_extent_em
    if print_runs is None:
        return [], [f"{FRONT_COPY_FIT_UNMEASURED}: vertical (no print-size block was handed to the instrument)"], False
    height = float(zone["height"])
    try:
        margin = float(zone.get("safe_margin_mm"))
    except (TypeError, ValueError):
        margin = None
    if margin is None or margin < 0 or 2 * margin >= height:
        return [], [f"{FRONT_COPY_FIT_UNMEASURED}: vertical (the zone record carries no usable safe margin)"], False
    top_edge, foot_edge = margin, height - margin
    rows, codes, measured = [], [], True
    for run in print_runs:
        name = run["name"]
        if name not in copy_runs and not name.startswith(_NAME_RUN_PREFIX):
            continue
        row = {"name": name, "text": run["text"], "size_pt": run["size_pt"],
               "baseline_mm": round(run["baseline_mm"], 4), "safe_top_mm": top_edge, "safe_foot_mm": foot_edge,
               "zone_height_mm": height}
        entry = _face_entry_for_role(run["font"] or "regular", faces)      # `_face_for`'s own default role
        extent = None
        if entry is not None:
            extent = ink_extent_em(run["text"], entry[1])
        if extent is None:
            row["state"] = "UNMEASURED"
            codes.append(f"{FRONT_COPY_FIT_UNMEASURED}: vertical ({name}: no glyph outlines to measure)")
            measured = False
            rows.append(row)
            continue
        size_mm = run["size_pt"] * back_panel.MM_PER_PT
        ink_top = run["baseline_mm"] - extent[0] * size_mm
        ink_bottom = run["baseline_mm"] - extent[1] * size_mm
        over = max(top_edge - ink_top, ink_bottom - foot_edge, 0.0)
        row.update(face=entry[0], ink_top_mm=round(ink_top, 4), ink_bottom_mm=round(ink_bottom, 4),
                   spare_top_mm=round(ink_top - top_edge, 4), spare_foot_mm=round(foot_edge - ink_bottom, 4))
        if isinstance(run["text"], str) and "CONTENT_VERIFICATION_REQUIRED" in run["text"]:
            row["state"] = "PLACEHOLDER"
        elif over > 1e-9:
            row["state"] = "EXCEEDS_SAFE_BAND"
            row["over_mm"] = round(over, 4)
            codes.append(f"{FRONT_COPY_EXCEEDS_SAFE_BAND}: {name} +{round(over, 4)} mm")
        else:
            row["state"] = "HELD"
        rows.append(row)
    return rows, codes, measured


def front_copy_fit(doc, zone, print_runs=None, *, copy_runs=_SMALL_COPY_RUNS, vertical_unmeasured=None) -> dict:
    """§BH50(b): each small-copy run measured at the size it is set, in the face the document draws it
    with (`text_metrics.resolve_metric_faces`, the same role → face map the emitter uses), against the
    confirmed front zone's own width — the reading of "the panel can hold them" his (b) is transcribed
    under (OWNER_BLOCKER_CLEARANCE.md, §BH50's reading). A run wider than the zone is named, never shrunk.

    §BH50(f)(3), OWNER RULED 2026-09-13: "the 5.0 pt floor governs, and a copy overrun BLOCKS Gate 2.
    Text that does not fit is a design problem to solve, not a number to shrink." The record blocks
    ACCEPTANCE now — its `codes` join readiness['front_copy'], read at Gate-2 approval, never the
    reconstruction — and it is TOTAL: every run reads HELD, EXCEEDS_ZONE, PLACEHOLDER (§BH50(f)(2): a
    placeholder's fit is a geometric fact, never copy verified), NOT_DRAWN (the emitter would skip the
    run) or UNMEASURED, and an absent, unmeasurable or undrawn run is a code, never a pass. The verdict
    stays against the TAKEN limit, the zone's width, until his line on which limit governs; the zone's own
    confirmed safe area (width − 2 × safe_margin_mm) is measured beside every run, verdict-free, and
    labelled MEASURED, NOT RULED. The axis measured is HORIZONTAL (arc length at the set size); the
    vertical axis is UNMEASURED with its cost, and blocks. The hero name is measured beside the small copy
    verdict-free (whether it is "front copy" is his line).

    §BH50(g)(1), OWNER RULED — typed 2026-09-17, re-typed in §BH53(a) (OWNER_BLOCKER_CLEARANCE.md :21604-21607):
    "THE 16.0 mm SAFE AREA GOVERNS THE FRONT. Copy 5.5 mm inside it will be trimmed on a real run. Gate 2
    refuses the current front until it is re-laid, and that refusal is correct. Record the 22.0 mm zone
    beside it as the outer bound." So the sentence above — the verdict "stays against the TAKEN limit, the
    zone's width, until his line" — is HISTORY from this commit: each run's `state` is judged against the
    zone's confirmed SAFE AREA (width − 2 × safe_margin_mm; 16.0 mm on task 52 [21.6 mm since §BH54(f) revised the
    zone to 27.6 mm on 2026-09-18 — the support line then HELD by 0.0964 mm]); a run over it is
    CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA with its millimetres; the zone is recorded beside it on every row
    as the OUTER BOUND (`outer_bound_state`, `zone_width_mm`, `spare_mm`), its own code keeping its meaning;
    and a zone record with no usable safe margin leaves the governing leg UNMEASURED — a code per run, never
    HELD (§BH50(f)(5)). Still at ACCEPTANCE only, never the reconstruction. On task 52 the support line
    (21.5036 mm) is refused by 5.5036 mm — his "5.5 mm" — and no size clears it (3.7203 pt against the 5.0 pt
    floor): a re-lay, or a zone change, which is his. The name runs stay verdict-free in this commit;
    §BH50(g)(2) is its own.

    §BH50(g)(2), OWNER RULED — typed 2026-09-17, re-typed in §BH53(a) (:21608-21609): "THE PRODUCT NAME IS FRONT
    COPY — the floor and the safe area apply to it like any other run." From its own commit the name runs
    (product-name-hero-*, the flat twins skipped) are judged by the same walk: the safe-area verdict, the outer
    bound, the codes. On task 52 "Damascena" (19.5897 mm at 9.0 pt in Montserrat-Bold) is refused on the safe
    area by 3.5897 mm, 2.4103 mm inside the outer bound; "Rose" is inside. Stated plainly: no ruled move clears
    it — 7.3508 pt would be needed against the name's own 8.0 pt floor (§AB2 fixes 9.0), it is one word and
    `wrap_name` breaks on whitespace only (§BD(b)) — so a face, tracking or name decision, or a zone change,
    which are his. `front-brand` (BBROSE at 6.0 pt, drawn only when no logo resolves) is not the product name
    and stays measured by nothing, listed for him.

    §BH70(1), item 5 of the list the owner was sent: the same instrument reads THE GENERIC PATH'S FRONT
    (`targets.container.generic_front_copy_fit`). ``copy_runs`` names the runs judged beside the name — the dropper's
    small copy by default, the ruled front's descriptor there — and ``vertical_unmeasured``, when given, is why this
    document's height has no instrument: the vertical axis is then UNMEASURED in those words, in its code and in its
    record, never HELD. Called as before, the record is byte for byte what it was."""
    from apps.ire.text_metrics import resolve_metric_faces, text_width_mm_measured
    faces = resolve_metric_faces(doc.metadata) or {}
    zone_width_mm = float(zone["width"])
    safe_area_mm, safe_margin_mm = _safe_area_mm(zone)
    runs, overruns, codes, name_runs = [], [], [], []

    def _measure(node, name):
        row = {"name": name, "text": node.text, "size_pt": node.size_pt, "role": node.font,
               "zone_width_mm": zone_width_mm, "safe_area_mm": safe_area_mm,
               "safe_margin_mm": safe_margin_mm}
        if abs(float(getattr(node, "rotation_deg", 0.0) or 0.0)) == 90.0:
            # [his fixes to 142 (Cherry Kiss), 2026-10-17, (1)] a run set on end runs down the zone: its length is held
            # against the zone's height and its safe height, said so
            height_mm = float(zone["height"])
            row.update(zone_width_mm=height_mm, axis="along the zone's height, the run set on end",
                       safe_area_mm=(round(height_mm - 2.0 * safe_margin_mm, 4) if safe_area_mm is not None
                                     else None))
        zone_width_mm_ = row["zone_width_mm"]
        safe_area_mm_ = row["safe_area_mm"]
        placeholder = "CONTENT_VERIFICATION_REQUIRED" in str(node.text or "")
        if not faces:
            row.update(face=None, state="UNMEASURED",
                       reason="the role→face map could not be resolved for this document")
            return row
        face = _face_for(node, faces)
        row["face"] = face
        if face is None:
            row.update(state="NOT_DRAWN",
                       reason=f"no face resolved for role {node.font!r}: the non-exempt emitter skips "
                              "this run, so there is no drawn width to hold")
            return row
        width_mm = text_width_mm_measured(node.text, node.size_pt * back_panel.MM_PER_PT, face)
        if width_mm is None:
            row.update(state="UNMEASURED", reason=f"the face {face!r} could not measure this text")
            return row
        row["width_mm"] = round(width_mm, 4)
        row["spare_mm"] = round(zone_width_mm_ - width_mm, 4)
        # §BH50(g)(1): the zone's width is the OUTER BOUND, recorded beside the safe area on every row
        row["outer_bound_state"] = "HELD" if width_mm <= zone_width_mm_ else "EXCEEDS_ZONE"
        if safe_area_mm_ is None:
            row["spare_to_safe_area_mm"] = None
            row["safe_area_state"] = "UNMEASURED"
        else:
            row["spare_to_safe_area_mm"] = round(safe_area_mm_ - width_mm, 4)
            row["safe_area_state"] = "INSIDE" if width_mm <= safe_area_mm_ else "OVER"
        if placeholder:
            row["state"] = "PLACEHOLDER"
        elif safe_area_mm_ is None:
            # §BH50(g)(1) with §BH50(f)(5): the governing limit is unmeasurable on this zone record — never HELD
            row["state"] = "UNMEASURED"
            row["reason"] = ("the zone record carries no usable safe_margin_mm, so the governing safe area is "
                             "unmeasured; the outer bound is measured beside it")
        else:
            # §BH50(g)(1): the verdict is against the SAFE AREA; the zone is the outer bound
            row["state"] = "HELD" if width_mm <= safe_area_mm_ else "EXCEEDS_SAFE_AREA"
        return row

    def _judge(row, name):
        """§BH50(g)(1): the safe-area verdict first (it governs), then the outer bound (its code keeps its
        meaning), then an unmeasured leg — each a code at acceptance, never silence. A placeholder run defers
        to §BH50(f)(2): its fit is a geometric fact, never copy verified, and never an overrun code here."""
        if row["state"] == "PLACEHOLDER":
            return
        if row["state"] == "EXCEEDS_SAFE_AREA":
            over = round(row["width_mm"] - row["safe_area_mm"], 4)
            overruns.append({"code": FRONT_COPY_EXCEEDS_SAFE_AREA, "run": name, "over_mm": over,
                             "limit_mm": row["safe_area_mm"]})
            codes.append(f"{FRONT_COPY_EXCEEDS_SAFE_AREA}: {name} +{over} mm")
        if row.get("outer_bound_state") == "EXCEEDS_ZONE":
            over = round(row["width_mm"] - row["zone_width_mm"], 4)
            overruns.append({"code": FRONT_COPY_EXCEEDS_ZONE, "run": name, "over_mm": over,
                             "limit_mm": row["zone_width_mm"]})
            codes.append(f"{FRONT_COPY_EXCEEDS_ZONE}: {name} +{over} mm")
        if row["state"] in ("UNMEASURED", "NOT_DRAWN"):
            detail = ("safe area unmeasured on this zone record" if "width_mm" in row else row["state"])
            codes.append(f"{FRONT_COPY_FIT_UNMEASURED}: {name} ({detail})")

    for node, _ in doc.walk():
        name = str(getattr(node, "name", ""))
        if getattr(node, "type", "") != "text":
            continue
        if name in copy_runs:
            row = _measure(node, name)
            runs.append(row)
            _judge(row, name)
        elif name.startswith(_NAME_RUN_PREFIX) and not name.startswith("flat-"):
            # §BH50(g)(2): the product name is front copy — judged like any other run
            row = _measure(node, name)
            name_runs.append(row)
            _judge(row, name)
    # THE OWNER'S SECOND ANSWER OF 2026-09-25: "Make Gate 2 measure the front's height." — the print-size block's ink
    # against the zone's safe band; UNMEASURED, with its reason, where the block or the band gives nothing to measure
    if vertical_unmeasured is None:
        vertical_runs, vertical_codes, vertical_measured = _vertical_fit(print_runs, zone, faces, copy_runs)
        vertical_words = FRONT_COPY_VERTICAL_COST
    else:
        # §BH70(1), item 5: a document whose height has no instrument says why, in its own words — never HELD
        vertical_runs, vertical_measured = [], False
        vertical_codes = [f"{FRONT_COPY_FIT_UNMEASURED}: vertical ({vertical_unmeasured})"]
        vertical_words = f"UNMEASURED — {vertical_unmeasured}"
    codes.extend(vertical_codes)
    if vertical_measured:
        vertical_words = FRONT_COPY_VERTICAL_MEASURE
    return {"schema_version": FRONT_COPY_FIT_SCHEMA,
            "limit": "the confirmed front zone's SAFE AREA — width − 2 × safe_margin_mm (§BH50(g)(1), re-typed "
                     "§BH53(a): \"THE 16.0 mm SAFE AREA GOVERNS THE FRONT\"); an overrun blocks Gate 2 through "
                     "readiness['front_copy'], at acceptance; the zone's width is recorded beside it as the "
                     "OUTER BOUND (until §BH53 the limit was the zone, §BH50(b) taken, and the safe area was "
                     "measured, not ruled)",
            "limit_source": FRONT_COPY_LIMIT_SOURCE,
            "outer_bound": "the confirmed zone's width (22.0 mm on task 52 until §BH54(f) revised it to 27.6 mm on "
                           "2026-09-18), recorded beside the safe area on "
                           "every row — zone_width_mm, spare_mm, outer_bound_state (§BH50(g)(1): \"Record the "
                           "22.0 mm zone beside it as the outer bound\"); a run past it also exceeds the safe "
                           "area and carries both codes",
            "axis": "horizontal — arc length at the set size, in the face the emitter draws with",
            "vertical": vertical_words,
            "vertical_runs": vertical_runs,
            "safe_area_mm": safe_area_mm, "safe_margin_mm": safe_margin_mm,
            "safe_area_note": "GOVERNS (§BH50(g)(1), typed 2026-09-17, re-typed §BH53(a)) — the verdict on every "
                              "run is against the safe area; before §BH53 this note read \"MEASURED, NOT RULED "
                              "(§BH50(f)(3): the limit is his line; §X2 reads the same bottle's back zone as its "
                              "own printable column)\", kept here as history; §X2's back column (19.0 mm) is "
                              "not reached by (g)(1), which names THE FRONT",
            "runs": runs, "overruns": overruns,
            "name_runs": name_runs,
            "name_note": "§BH50(g)(2) (typed 2026-09-17, re-typed §BH53(a)): THE PRODUCT NAME IS FRONT COPY — the floor "
                         "and the safe area apply to it like any other run; the name runs are judged above and their "
                         "codes sit in `codes`; their own floors (8.0 pt, §AB2's 9.0, §BD(b)'s clip rule) stand beside "
                         "§W2's 5.0 pt, never softened. Before §BH53 this note read \"measured verdict-free: whether "
                         "the product name is front copy under §BH50(f)(3) is his line (its own floors are 8.0 pt and "
                         "9.0 pt; §BD(b))\", kept here as history",
            "codes": codes,
            "blocks": "ACCEPTANCE (Gate-2 approval, through readiness['front_copy']); never the reconstruction"}


def _front_typography(g, zone, ox, oy, s, logo_path, prefix="",
                      name_min=9.0, name_lines=None, descriptor=None, net_content=None, logo_master=None):
    """The front artwork's live type, positioned in mm and sized in points.

    ``ox``/``oy``/``zone``/``g`` and ``s`` are all MILLIMETRE quantities (``s``
    is the panel's drawing scale, which multiplies them). They decide where
    everything sits and how large the drawing is. **They decide no type size.**
    ``name_min`` is in points and is the only argument that may.

    §Z1(a): the emitter converts ``_mm`` and does not convert ``_pt``, so a
    ``size_pt`` derived from a millimetre length is emitted as that number of
    points — and would change if the same physical zone were drawn at a
    different panel scale. `apps/ire/tests/test_wij_type_size_units.py` varies
    every millimetre input above and requires every emitted size to hold still.
    """
    closure_h = (g["collar_height_mm"] + g["bulb_height_mm"]
                 + (g.get("visible_neck_mm") or 3.0))
    zx = ox + float(zone["x"]) * s
    zy = oy + (closure_h + float(zone["y"])) * s
    zw, zh = float(zone["width"]) * s, float(zone["height"]) * s
    cx = zx + zw / 2.0
    ink = _hex("TYPE_WINE")
    children: list = []
    placements: list = []
    zid = zone.get("zone_id")

    def P(n):
        return f"{prefix}{n}"

    def place(kind, ny, nh):
        placements.append({"zone_id": zid, "kind": kind, "nx": 0.15,
                           "ny": round(ny, 3), "nw": 0.70,
                           "nh": round(nh, 3), "surface_family": "body"})

    logo_used = ""
    logo_w = zw * MARK_ZONE_SHARE
    # the height is the ASSET'S. It used to be logo_w*0.30 whatever the file
    # actually was; the placement is anchored at its top, so reading the true
    # aspect changes the height and nothing else.
    if logo_master is not None:
        # THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo
        # trace, switch the mark to it so gold foil can print." Handed the approved vector master, the mark is drawn
        # from it — the same box, its height from the master's ink bounds — as an AssetRef the emitter expands
        logo_ratio = logo_master.aspect
        logo = _brand_mark.mark_node(P("logo"), logo_master, cx - logo_w / 2,
                                     zy + zh * 0.075, logo_w, logo_w * logo_ratio)
    else:
        logo_ratio = intrinsic_aspect(logo_path)
        logo = None if logo_ratio is None else image_node(
            P("logo"), logo_path, cx - logo_w / 2,
            zy + zh * 0.075, logo_w, logo_w * logo_ratio)
    if logo is not None:
        children.append(logo)
        logo_used = "front-controlled-fallback" if logo_master is None else _brand_mark.ZONE_USED
        place("logo", 0.08, 0.10)
    else:
        children.append(centered_text(P("front-brand"), "BBROSE", cx,
                                      zy + zh * 0.13, BRAND_PT, ink,
                                      font="bold"))
        place("support_text", 0.08, 0.09)

    # ONE subtle fine rule — drawn BELOW the name, after the name block (§BH66(b)). It stood here, between the
    # mark and the name at 0.225 of the zone, until §BH66(b) ruled "THE RULE SITS BELOW THE NAME": a dropper is a
    # bottle, and §AU1 governs its front. The weight stays §BB7(e)'s: C16(b) YES — 0.30 mm, opacity 1.0 solid.

    # §11: the stacked product-name block — two serif lines, dominant over
    # everything else on the panel.
    #
    # §AB3(c). This comment used to end "with tight leading, one visual
    # element". IT WAS FALSE, and it had been false since the units bug that
    # produced the number: the leading was NAME_LEADING_INCUMBENT_EM = 3.0047
    # em, which at the ruled 9.0 pt is a 9.540 mm gap between two 9 pt lines —
    # three times the type size. Measured off the emitted PDF, the two line
    # boxes clear each other by 5.216 mm and the drawn letters by 7.247 mm,
    # against a face whose own line boxes do not meet until 1.362 em.
    # Whatever else 9.540 mm is, it is not tight, and a sentence in the
    # repository saying it is does not get to wait for a design decision.
    #
    # Two numbers because there are two quantities, and WI-V's first pass
    # conflated them: a PDF span box runs ascent to descent whether or not a
    # glyph reaches either end, so the line box is a fact about the FACE and
    # the ink is a fact about THESE WORDS — `Rose` has no descender. It is
    # written down at the number rather than only in the tool because at the
    # TIGHT end of §AB3(a)'s comparison the two disagree about whether
    # anything is wrong at all, and §AC1(a) resolved that disagreement in the
    # line box's favour permanently. Which is meant is now settled and it is
    # the FACE: `apps/ire/tests/test_wiy_leading_metric_floor.py` measures the
    # floor from the face and proves, with a descender-bearing control, that
    # its verdict does not move when the words do.
    #
    # "Tight leading, one visual element" is the §11 CONCEPT SPEC's language,
    # and the spec has not changed. The discrepancy was real and was made
    # visible instead of being described away.
    #
    # §AC1 HAS NOW RULED, and the block below is set at 2.0 em. The spec's
    # phrase is still not literally met — 2.0 em is not "tight" by the metric
    # floor's standard of 1.362 — and that is deliberate: §AC1(a) ruled that
    # the tight end FAILS, because at 1.06 em the line boxes overlap by
    # 0.959 mm and only the absence of a descender in `Rose` keeps the ink
    # apart. So the artwork moves toward the phrase and stops where the face
    # allows, with 0.638 em of headroom for the descender the next SKU brings.
    # §AC1(c) records 2.0 as a bet the owner named so it can be lost, against
    # the true-scale render WI-Y puts in the queue; if it loses,
    # NAME_LEADING_INCUMBENT_EM is the fallback and needs no new ruling.
    name_size = name_min
    # `leading` is a MILLIMETRE offset and `name_size` is a POINT size, so the
    # conversion is explicit and the ratio is named in em. See NAME_LEADING_EM:
    # §AC1 ruled the em value and it is 2.0, above the 1.362 em metric floor.
    leading = name_size * back_panel.MM_PER_PT * NAME_LEADING_EM
    block_top = zy + zh * 0.30
    # §AC1(e). The strings arrive as an argument now; `FRONT_NAME_LINES` is the
    # default and reproduces the two literals that used to be written here. The
    # loop indexes from `block_top` so line 0 lands where it always did and the
    # two-line case is bit-identical: `0 * leading` and `1 * leading` are exact.
    #
    # §BB7(g)(a): and each supplied line is WRAPPED rather than clipped, through
    # `wrap_name` — the very function §BD(b) ruled for the other direct-print
    # front. The measured defect §BD(b) answered was `ose Nectar Lip Glos`, a
    # name eaten at both ends by its group's clip; this group clips too
    # (`rect_clip(*zrect)` at both call sites), so an unwrapped long name fails
    # here in exactly that way.
    #
    # THE WIDTH IS THE UNSCALED ZONE WIDTH, AND THE `* s` IS OMITTED ON PURPOSE.
    # `zw` above is `zone["width"] * s` — a DRAWING length, different at panel 5
    # (s=1.22) and panel 8 (s=1.5455). `name_size` is a POINT size and §Z1(a)
    # holds it still across scales. Wrapping a point-sized string against a
    # scaled width would therefore break the SAME name into different lines on
    # the two panels of one sheet, which is precisely the panel-5/panel-8
    # divergence §AB2(d) ruled out. `zone["width"]` is 22.0 at both call sites [27.6 on task 52
    # since §BH54(f); the argument is that both call sites pass the SAME width, which stands] —
    # panel 8 passes `dict(front_zone, x=0, y=0)`, which preserves width — so
    # the break is identical by construction. `0.94` is the share
    # `compose_container.py:482` uses, kept identical for the same anti-drift
    # reason as the function itself.
    #
    # BIT-IDENTICAL FOR THE DEFAULT, MEASURED AND NOT ASSUMED:
    # `wrap_name("Rose", 9.0, 20.68)` -> `["Rose"]` and
    # `wrap_name("Damascena", 9.0, 20.68)` -> `["Damascena"]`, since "Damascena"
    # estimates 14.985 mm against a 20.68 mm limit. Twelve characters fit at
    # 9.0 pt and thirteen do not.
    # §BH68(d): no module default — the lines are the product record's (the sheet hands them in), or none
    # [2026-09-25, the owner's answer to the §BH68 report: the wrap's lines where they fit the safe area, else the fewest
    # lines up to four that do — `front_name_lines`, measured as `front_copy_fit` measures the drawn run]
    lines = [w for raw in (name_lines or ())
             for w in front_name_lines(raw, name_size, zone)]
    # §BH49(c): the product's text is set BY ROLE through the layer — the name is the heading
    # (Montserrat[wght] at its pinned 700 instance, §BH33(2)), the support line the body, the net
    # content the caption; the aliases (`serif-bold`, `bold`, `regular`) stay for the sheet's own
    # furniture. Task 52's record carries no Arabic string, so no arabic-* run is composed here
    # and none is invented; an Arabic string, when a record carries one, takes ARABIC_ROLE_FOR.
    for i, line in enumerate(lines):
        children.append(centered_text(P(f"product-name-hero-{i}"), line, cx,
                                      block_top + i * leading, name_size, ink,
                                      font="heading"))
    # §BH68(d): the name's placement is recorded where a name is drawn — a silent record places none, as §BH67(c)2
    # records no support line it did not draw
    if lines:
        place("product_name", 0.29, 0.24)

    # §AB2(a): both baselines hang off the name block's LAST line, so the
    # support stack keeps its clearance whatever the leading and whatever the
    # panel scale. See SUPPORT_LEAD_EM for the measurement they reproduce.
    # `(len(lines) - 1) * leading` is the last line's offset, which for the
    # two-line default is `leading` exactly — the anchor did not move, it
    # learned to count.
    em_mm = name_size * back_panel.MM_PER_PT
    last_baseline = block_top + (len(lines) - 1) * leading
    support_y = last_baseline + em_mm * SUPPORT_LEAD_EM
    net_y = support_y + em_mm * NET_LEAD_EM
    # the weight's standing against the capability table is in ire/container_line_weight.py.
    # §BH66(b), OWNER RULED 2026-09-23: "THE RULE SITS BELOW THE NAME" — §AU1's order, name, the rule below it, the
    # supporting line below that. It sits midway between the name's ink (a quarter em below its last baseline, the
    # ruled front's own model) and the supporting line's cap top; the tiers keep §BH50(b)'s leading, which leaves
    # 2.28 mm between the two inks at the ruled 9 pt over 5 pt, about a millimetre of air each side of 0.30 mm.
    rule_y = ((last_baseline + em_mm * 0.25) + text_ink_top(support_y, SUPPORT_PT)) / 2.0
    rule_w = zw * 0.38
    children.append(Group(name=P("motif-front"), role="decoration",
                          children=[Path(
        name=P("rule-front-single"),
        segments=[MoveTo(x=cx - rule_w / 2, y=rule_y),
                  LineTo(x=cx + rule_w / 2, y=rule_y)],
        stroke=Stroke(color=ink, width_mm=0.30, opacity=1.0))]))
    place("motif", (rule_y - zy) / zh - 0.015, 0.03)
    # §BB7(g)(a). The literal became `FRONT_DESCRIPTOR` and the argument
    # defaults to it, so the emitted characters are unchanged. ONLY THE NAME
    # WRAPS AND THIS TIER DOES NOT — `compose_container.py:477-481` states the
    # scope: the owner ruled about the brand name, and breaking ruled,
    # regulated-adjacent copy across lines is a typographic decision nobody has
    # made. The letter-spacing in this particular string would make such a break
    # arbitrary twice over.
    # §BH67(c)2: the descriptor is the product record's, and a silent record prints no line — the rule keeps its
    # §AU1 place below the name either way, measured against where the supporting line sits
    if descriptor:
        children.append(centered_text(P("front-support"), descriptor, cx,
                                      support_y, SUPPORT_PT, ink, font="body"))
        # The placement record is DERIVED now rather than transcribed. It used to
        # carry 0.515/0.585, hand-matched to the 0.545/0.61 above; a hand-matched
        # constant beside a computed one is a lie waiting for the computed one to
        # move, which is the same class of defect as the collision itself.
        # §BH50(b): the record's top is the run's own box top, one em of its own size above its baseline —
        # derived, where the 0.03 it replaces was matched by hand to the 3.4 pt run and drifts 0.6 mm at 5.0 pt
        place("support_text", (support_y - SUPPORT_PT * back_panel.MM_PER_PT - zy) / zh, 0.07)
    # §BH67(c)2: the net content is `Product.net_weight` as held, in the record's own spelling — never a literal
    if net_content:
        children.append(centered_text(P("front-net-content"), net_content, cx,
                                      net_y, NET_CONTENT_PT, ink, font="caption"))
        place("support_text", (net_y - NET_CONTENT_PT * back_panel.MM_PER_PT - zy) / zh, 0.06)
    return children, placements, logo_used, (zx, zy, zw, zh)


# ---------------------------------------------------------------------------
# panels
# ---------------------------------------------------------------------------

def _panel_frame(label, x, y, w, h):
    return [Rect(name=f"panel-frame-{label[:24]}", x=x, y=y, w=w, h=h,
                 radius_mm=1.0,
                 fill=SolidFill(color=Color.from_hex("#F7F1EC")),
                 stroke=Stroke(color=_INK, width_mm=0.15, opacity=0.5)),
            TextRun(name=f"panel-label-{label[:24]}", text=label, x=x,
                    y=y - 1.6, size_pt=2.7, color=_INK, font="bold",
                    align="left")]


def _review_raster(label, path, x, y, w, h):
    """A prior output shown for comparison — a REVIEW REFERENCE raster,
    never printable artwork (the census counts it as reference)."""
    kids = _panel_frame(label, x, y, w, h)
    img = image_node(f"reference-{label[:20]}", path, x + 1, y + 1,
                     w - 2, h - 2, clip=rect_clip(x + 1, y + 1, w - 2,
                                                  h - 2))
    if img is not None:
        kids.append(img)
    return kids


def _back_panel(back_sections, x, y, w, h, zone=None):
    # §BH54(g): the caption said "(22×36)" as a literal — true of task 52 by coincidence, false of every other back
    # zone, and false of task 52 once its back zone was revised to 22 × 39.6. The DRAWN caption prints the confirmed
    # zone's size; the node's name is the panel's identity and no longer carries a size (names are cut at 24
    # characters, which a size like "(22×42.3)" would overrun).
    kids = _panel_frame("9a · BACK PRINT", x, y, w, h)
    if zone:
        kids[1].text = f"9a · BACK PRINT ({float(zone['width']):g}×{float(zone['height']):g})"
    ink = _hex("TYPE_WINE")
    ty = y + 5.0
    body_kids: list = []
    for si, sec in enumerate(back_sections or []):
        body_kids.append(TextRun(
            name=f"back-section-{si}-heading",
            text=str(sec.get("heading", ""))[:36], x=x + 3, y=ty,
            size_pt=2.5, color=ink, font="heading", align="left"))   # §BH49(c)
        ty += 3.1
        body_kids.append(TextRun(
            name=f"back-section-{si}-copy",
            text=str(sec.get("text", ""))[:60], x=x + 3, y=ty,
            size_pt=2.1, color=_INK, font="body", align="left"))   # §BH49(c)
        ty += 2.5
        body_kids.append(Path(
            name=f"back-section-{si}-rule",
            segments=[MoveTo(x=x + 3, y=ty), LineTo(x=x + w - 3, y=ty)],
            stroke=Stroke(color=_INK, width_mm=0.08, opacity=0.35)))
        ty += 2.1
    kids.append(Group(name="BACK_DIRECT_PRINT", role="decoration",
                      children=body_kids,
                      clip=rect_clip(x + 1, y + 1, w - 2, h - 2)))
    return Group(name="Surface-BODY_BACK", role="decoration", children=kids)


def _bottom_panel(g, zone, x, y, w):
    W = g["body_diameter_mm"]
    s = (w - 8) / (W + 6)
    cxx = x + w / 2.0
    r = W / 2.0 * s
    cyy = y + r + 6
    k = _K
    kids = _panel_frame("9b · BOTTOM CODE (14×5)", x, y, w, 2 * r + 11)
    kids.append(Path(name="bottom-base-circle", segments=[
        MoveTo(x=cxx - r, y=cyy),
        CubicTo(x1=cxx - r, y1=cyy - r * k, x2=cxx - r * k, y2=cyy - r,
                x=cxx, y=cyy - r),
        CubicTo(x1=cxx + r * k, y1=cyy - r, x2=cxx + r, y2=cyy - r * k,
                x=cxx + r, y=cyy),
        CubicTo(x1=cxx + r, y1=cyy + r * k, x2=cxx + r * k, y2=cyy + r,
                x=cxx, y=cyy + r),
        CubicTo(x1=cxx - r * k, y1=cyy + r, x2=cxx - r, y2=cyy + r * k,
                x=cxx - r, y=cyy),
        ClosePath()],
        stroke=Stroke(color=_INK, width_mm=0.2, opacity=0.6)))
    zw, zh = float(zone["width"]) * s, float(zone["height"]) * s
    kids.append(Rect(name="bottom-code-window", x=cxx - zw / 2,
                     y=cyy - zh / 2, w=zw, h=zh,
                     stroke=Stroke(color=_INK, width_mm=0.2)))
    kids.append(Group(name="BOTTOM_TECHNICAL_CODE", role="generic",
                      children=[centered_text(
                          "bottom-code-batch", "BATCH — MFG — EXP —", cxx,
                          cyy + 0.7, 1.8, _INK)]))
    return Group(name="Surface-BOTTOM", role="generic", children=kids)


# ---------------------------------------------------------------------------
# §13 — the comparison concept sheet
# ---------------------------------------------------------------------------

def front_copy_from_hierarchy(hierarchy_lines):
    """Destructure ruled hierarchy tiers into this lockup's two copy slots.

    Returns ``(name_lines, descriptor)``, either of which may be ``None``
    meaning *"this slot keeps its module default"*. [§BH68(d), 2026-09-24: the
    NAME slot has no module default either now. A ``None`` there is filled by
    the sheet's own ``product_name`` — the product record's — or, where the
    record is silent, prints no name.] ``None`` in, ``(None,
    None)`` out — so a caller that passes nothing gets today's artwork to the
    bit, and the whole of §3 is inert until a source is ruled.
    [§BH67(c)2, 2026-09-24: the DESCRIPTOR slot has no module default now. A
    ``None`` there is filled by the sheet's own ``descriptor`` — the product
    record's — or, where the record is silent, prints nothing.]

    WHY A FUNCTION AND NOT FOUR LINES INSIDE THE SHEET. It is the only way the
    §AB2(d) property can be a PROPERTY rather than a habit. Panel 5 and panel 8
    are two calls to `_front_typography` twenty lines apart; the first time they
    disagreed it was because one of them restated a value the other took by
    default. One derivation, one pair of locals, both calls fed from it — and
    `test_bb7g_both_panels_take_one_hierarchy` asserts the emitted runs match,
    which is the only form of the claim that a future edit cannot quietly break.

    THE NET-CONTENT TIER IS NOT READ, AND `front_hierarchy.py:26-34` is why: the
    ruled hierarchy has no such tier, because §AE2(b) classes net content
    REGULATED (manifest row B5, BLOCKING). This composer draws `30 ml / 1.01
    fl. oz.` from its own literal and keeps doing so. A hierarchy that somehow
    carried a `net_content` tier would be IGNORED here rather than emitted,
    which is the fail-closed direction: the front cannot acquire a regulated
    quantity from an unruled source by accident.

    Unknown kinds are ignored for the same reason, and the FIRST tier of a kind
    wins, so a malformed hierarchy cannot silently overwrite copy twice.
    """
    if not hierarchy_lines:
        return None, None
    name_lines = None
    descriptor = None
    for tier in hierarchy_lines:
        kind = (tier or {}).get("kind")
        text = ((tier or {}).get("text") or "").strip()
        if not text:
            continue
        if kind == "product_name" and name_lines is None:
            # NOT split here. `_front_typography` wraps, because only it knows
            # the point size the break has to be measured at.
            name_lines = [text]
        elif kind == "descriptor" and descriptor is None:
            descriptor = text
    return name_lines, descriptor


def _draw_bottle(g: dict, ox: float, oy: float, s: float, *, name="Bottle", clip=None,
                 front_children: Optional[list] = None, name_prefix: str = "",
                 drawing_source: Optional[str] = None, backbone=None) -> Group:
    """§BH48(b)(ii): one dispatcher for the sheet's four bottle drawings — the parametric group
    (byte for byte as before) or the accepted fit's outlines when the source says so.
    §BH49(a): no source named means the product's — M3_FIT, which needs the backbone the sheet
    derived; a caller that wants the typed numbers names PARAMETRIC."""
    if drawing_source is None:
        drawing_source = "M3_FIT"
    if drawing_source == "M3_FIT":
        if backbone is None:
            raise ValueError("M3_FIT_BACKBONE_REQUIRED: the M3 drawing needs the backbone derived from the fit")
        return _bottle_group_m3(backbone, g, ox, oy, s, name=name, clip=clip,
                                front_children=front_children, name_prefix=name_prefix)
    return _bottle_group(g, ox, oy, s, name=name, clip=clip,
                         front_children=front_children, name_prefix=name_prefix)


def compose_dropper_sheet(
    geometry: dict, *,
    zones: list,
    reference_path: Optional[str],
    logo_path: Optional[str],
    product_name: str,
    sku: str,
    back_sections: Optional[list],
    revision_status: str,
    prior_outputs: Optional[list] = None,    # [(label, png_path), ...]
    # §Z3(a) — the SAME container_production_method/1.0 record the typography
    # axis reads. Absent, it is §W2(b)'s unrecorded case and the back panel
    # takes the disclosed 5.0 pt fallback exactly as before; present, the back
    # panel's copy is set at BODY_BACK's own capability-table floor. Passing
    # one object to composer and axis is what stops the two disagreeing — the
    # disagreement, not the number, was the defect §Z3 names.
    methods_record: Optional[dict] = None,
    # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] the address the back's QR carries, where the shape step
    # measured the back holding it; None draws the panel as it was
    back_qr_url: Optional[str] = None,
    # §BH48(b)(ii) — the drawing source. PARAMETRIC draws `_bottle_group` from the numbers as
    # before, byte for byte; M3_FIT draws the accepted fit's own outlines (`backbone`, the
    # ContainerBackbone `build_m3_dropper_backbone` builds from the profile derived from it).
    # §BH49(a) — the composers draw from the accepted M3 concept BY CONSTRUCTION: no source
    # named resolves to M3_FIT, and a backbone not supplied is derived here from the geometry
    # on the ruling's one anchor (m3_backbone.ANCHOR_MM); the typed numbers draw only
    # for a caller that names PARAMETRIC. Anything else is refused by name.
    drawing_source: Optional[str] = None,
    backbone=None,
    # §BB7(g)(a) — the THIRD production composer learns the same word the other
    # two call sites already speak. §BB7(g)(a) warned that *"any executor who
    # assumes one patch fits all three is wrong before he starts"*, and the
    # measurement behind that warning was that this function took no
    # `hierarchy_lines` parameter at all. It does now, and the plumbing is
    # genuinely different: the other two hand the tiers straight to
    # `_native_decoration`, which sizes each tier from its KIND. This composer
    # has a fixed three-block lockup — name, descriptor, net content — with its
    # own sizes and its own leading, so the tiers are DESTRUCTURED into the
    # arguments that lockup already has rather than drawn from.
    #
    # NO PRODUCTION CALLER PASSES THIS, AND THAT IS THE OWNER'S RESERVATION, NOT
    # AN OVERSIGHT. `targets/container/__init__.py:1074` is untouched by this
    # commit. The parameter exists so that the day the source question is ruled,
    # the ruling lands at ONE call site instead of being discovered here.
    hierarchy_lines: Optional[list] = None,
    # §BH67(c)2: the product record's descriptor and net content — `front_hierarchy.descriptor_for` and
    # `net_content_for`. None is the record's silence, and a silent record prints nothing (no module default).
    descriptor: Optional[str] = None,
    net_content: Optional[str] = None,
    # THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    # switch the mark to it so gold foil can print." The approved vector master (apps/ire/brand_mark.py), handed in
    # by a caller that found one on file; None — every call before this parameter — draws the raster as before.
    logo_master=None,
) -> Document:
    front_zone = next((z for z in zones or []
                       if z.get("zone_type") == "FRONT_PRINT_ZONE"), None)
    bottom_zone = next((z for z in zones or []
                        if z.get("zone_type") == "BOTTOM_CODE_ZONE"),
                       {"width": 14, "height": 5})
    # §BH49(a): resolve the drawing source — the product's, by construction
    if drawing_source is None:
        drawing_source = "M3_FIT"
    if drawing_source == "M3_FIT" and backbone is None:
        from apps.pipeline.targets.container import m3_backbone as _m3b
        # §BH70(1): the form is passed, never defaulted — this sheet is the DROPPER's own and serves that one form, as
        # its callers already refuse any other before it is reached (`exploration_render.frozen_inputs`)
        _profile_m3, geometry, _derivation = _m3b.m3_profile_geometry(_m3b.ANCHOR_MM, geometry, "bottle")
        backbone = _m3b.build_m3_dropper_backbone(_profile_m3)
    elif drawing_source not in ("M3_FIT", "PARAMETRIC"):
        raise ValueError(f"CONTAINER_DRAWING_SOURCE_UNKNOWN: {drawing_source!r} — the sheet draws M3_FIT or PARAMETRIC")
    g = geometry
    back_zone = back_panel.back_zone(zones)

    children: list = [
        centered_text("sheet-title",
                      "PRODUCT CONTAINER — SELECTED CONCEPT RECONSTRUCTION",
                      _PAGE_W / 2, 12, 10, _INK, font="bold"),
        centered_text("sheet-status-12", f"12 · {revision_status}",
                      _PAGE_W / 2, 17.5, 5.5, Color.from_hex("#8E4F5C")),
    ]

    # row 1 — 2/3/4 · prior outputs (review references, immutable)
    row_y, row_h, pw = 25.0, 62.0, 28.0
    for i, (label, path) in enumerate(list(prior_outputs or [])[:3]):
        children.extend(_review_raster(f"{2 + i} · {label}", path,
                                       12 + i * 31, row_y, pw, row_h))
    # 1 · concept #97 — tall, at a scale comparable to the CORR-3 hero
    children.extend(_review_raster("1 · SELECTED CONCEPT #97",
                                   reference_path, 106, 28.0, 44.0, 130.0))

    # right column — 4 · CORR-2 hero, large enough for judgment
    hero_s = 1.22
    hero_ox, hero_oy = 158.0, 28.0
    children.append(TextRun(name="panel-label-hero",
                            text="5 · CORR-3 RECONSTRUCTION", x=hero_ox - 8,
                            y=hero_oy - 3.0, size_pt=2.7, color=_INK,
                            font="bold", align="left"))
    front_group = None
    placements, logo_used = [], ""
    # [the owner's second answer of 2026-09-25: the master reaches the helpers as a keyword ONLY when one is handed
    # in, so every call made without one is the call made before — a test's double of a helper sees the same shape]
    _mk = _brand_mark.master_kwargs(logo_master)
    # §BB7(g)(a). Derived ONCE, above both panels, and passed to both. See
    # `front_copy_from_hierarchy` for why this is one call and not two.
    front_lines, front_descriptor = front_copy_from_hierarchy(hierarchy_lines)
    if front_lines is None:
        # §BH68(d): with no ruled hierarchy, the front's name is the sheet's own `product_name` — the product record's —
        # and a silent record prints no name; never the module default that left with this ruling
        front_lines = [product_name.strip()] if isinstance(product_name, str) and product_name.strip() else []
    if front_descriptor is None:
        front_descriptor = descriptor          # §BH67(c)2: the record's, or none
    if front_zone is not None:
        fk, placements, logo_used, zrect = _front_typography(
            g, front_zone, hero_ox, hero_oy, hero_s, logo_path,
            name_lines=front_lines, descriptor=front_descriptor, net_content=net_content, **_mk)
        front_group = Group(name="FRONT_DIRECT_PRINT", role="decoration",
                            children=fk, clip=rect_clip(*zrect))
    children.append(_draw_bottle(
        g, hero_ox, hero_oy, hero_s, name="Bottle",
        front_children=[front_group] if front_group else None,
        drawing_source=drawing_source, backbone=backbone))

    # row 2 — 6 · silhouette · 7 · closure ×2 · 8 · front typography
    r2y = 100.0
    children.extend(_panel_frame("6 · SILHOUETTE", 12, r2y, 34, 78))
    children.append(_draw_bottle(
        g, 12 + (34 - g["body_diameter_mm"] * 0.68) / 2, r2y + 3, 0.68,
        name="Bottle-Small", name_prefix="cu0-",
        clip=rect_clip(13, r2y + 1, 32, 76),
        drawing_source=drawing_source, backbone=backbone))
    children.extend(_panel_frame("7 · CLOSURE ×2", 52, r2y, 46, 78))
    children.append(_draw_bottle(
        g, 52 + (46 - g["body_diameter_mm"] * 1.85) / 2, r2y + 4, 1.85,
        name="Bottle-CloseUp-Closure", name_prefix="cu2-",
        clip=rect_clip(53, r2y + 1, 44, 76),
        drawing_source=drawing_source, backbone=backbone))
    children.extend(_panel_frame("8 · FRONT TYPOGRAPHY", 12, 188.0, 40, 78))
    if front_zone is not None:
        flat_s = min(34 / float(front_zone["width"]),
                     70 / float(front_zone["height"]))
        closure_h = (g["collar_height_mm"] + g["bulb_height_mm"]
                     + (g.get("visible_neck_mm") or 3.0))
        # §AB2(d) — the panel-5 / panel-8 disagreement, RESOLVED at 9.0.
        # This call used to pass `name_min=6.5` while panel 5 above took the
        # 9.0 default, so the sheet showed the front under two different type
        # programmes and called both the front. §AA2 recorded that as a
        # finding; §AB2 rendered it and ruled it. One spelling, and it is
        # panel 8 that conforms. The argument is not re-passed as 9.0: the
        # default IS the ruling, and restating it here would let the two drift
        # apart again exactly as they did the first time.
        #
        # §BB7(g)(a) PASSES TWO ARGUMENTS HERE AND THAT IS NOT A BREACH OF THE
        # PARAGRAPH ABOVE — it is the same principle in the only form available.
        # `name_min` is a RULING, so its one spelling is the signature default
        # and no call site may restate it. `front_lines`/`front_descriptor` are
        # a CALLER'S INPUT, which a signature default cannot carry; the single
        # spelling is therefore the pair of locals computed once above, and both
        # panels read the same two names. What §AB2(d) forbids is two sources
        # for one value. There is one source, and it is fifty lines up.
        fk2, _, _, _ = _front_typography(
            g, dict(front_zone, x=0, y=0),
            12 + (40 - float(front_zone["width"]) * flat_s) / 2,
            192.0 - closure_h * flat_s, flat_s, logo_path,
            prefix="flat-", name_lines=front_lines,
            descriptor=front_descriptor, net_content=net_content, **_mk)
        children.append(Group(name="FrontArtworkFlat", role="decoration",
                              children=fk2,
                              clip=rect_clip(13, 189.0, 38, 74)))

    # row 3 — 9 · glass-material close-up · back+bottom · 10 · dims
    r3y = 188.0
    children.extend(_panel_frame("9 · GLASS MATERIAL", 56, r3y, 24, 66))
    children.append(_draw_bottle(
        g, 56 + (24 - g["body_diameter_mm"] * 0.74) / 2, r3y + 2 - 40 * 0.74,
        0.74, name="Bottle-Glass", name_prefix="cu3-",
        clip=rect_clip(57, r3y + 1, 22, 64),
        drawing_source=drawing_source, backbone=backbone))
    children.append(_back_panel(back_sections, 84.0, r3y + 4, 38, 58, zone=back_zone))
    children.append(_bottom_panel(g, bottom_zone, 126.0, r3y + 4, 30))

    # 13 · §W1(a) — the back panel AT PRINT SIZE, beside the strip's diagram of
    # it. The origin is the sheet's free region as measured on the emitted
    # document, not an eyeballed gap: 9b ends at y≈221.5 and the swatch column
    # starts at x=160. The panel is drawn 1:1 from the confirmed zone, so a
    # zone too tall for the region crosses the artboard and the composition
    # axis says so — scaling it to fit is the one thing §W1 forbids.
    true_scale_panel, back_panel_record = back_panel.compose_back_panel(
        back_sections, back_zone, 126.0, 232.0, ink=_hex("INK"),   # §BH50(d): the product's ink, through the layer
        methods_record=methods_record,
        heading_role="heading", copy_role="body",   # §BH49(c): the product's regulatory text, by role
        # [his goal of 2026-10-06, item 8] measured as this sheet is drawn — the theme's faces, never the legacy ones
        doc_metadata={"typography_surface": "apps/ire/compose_dropper.py::compose_dropper_sheet"},
        **({"qr_url": back_qr_url} if back_qr_url else {}))
    # §BH50(f)(2): the composer states which nodes draw which section of the back copy — the strip's
    # `back-section-{i}-copy` and the true-scale panel's `back-panel-{i}-copy-*` — so the placeholder record
    # joins its findings to the record's slots by THIS map and never by matching a run's name to a heading.
    # Metadata only: no drawn byte moves.
    back_copy_drawings = {}
    for si, sec in enumerate(back_sections or []):
        back_copy_drawings[str(si)] = {
            "heading": str(sec.get("heading", "")),
            "strip": [f"back-section-{si}-copy"],
            "true_scale": [f"back-panel-{e['section']}-{e['role']}-{e['order']}"
                           for e in (back_panel_record.get("lines") or [])
                           if e.get("fits") and e.get("section") == si and e.get("role") == "copy"]}
    if true_scale_panel is not None:
        children.append(TextRun(
            name="sheet-back-panel-true-scale-label",
            text=f"13 · BACK PANEL AT PRINT SIZE "
                 f"({back_panel_record['panel_mm'][0]:g} × "
                 f"{back_panel_record['panel_mm'][1]:g} mm)",
            x=126.0, y=229.5, size_pt=2.7, color=_INK, font="bold",
            align="left"))
        children.append(true_scale_panel)
    dims = (f"10 · REVISED CLOSURE (HUMAN_CONFIRMED_CONCEPT_ONLY): body "
            f"Ø{g['body_diameter_mm']:g}×{g['body_height_mm']:g} + neck "
            f"{g.get('visible_neck_mm') or 3:g} + collar "
            f"Ø{g['collar_diameter_mm']:g}×{g['collar_height_mm']:g} + bulb "
            f"{g.get('bulb_width_mm') or 13:g}×{g['bulb_height_mm']:g} = "
            f"{g['total_height_mm']:g} total — NOT_MANUFACTURER_VERIFIED")
    children.append(TextRun(name="confirmed-dims", text=dims[:150], x=12,
                            y=r3y + 74, size_pt=2.3, color=_INK,
                            align="left"))

    # 11 · swatches (material system + authority)
    sx, sy = 160.0, r3y + 2
    children.append(TextRun(name="panel-label-swatches",
                            text="11 · MATERIAL SYSTEM (authority "
                                 "UNVERIFIED)", x=sx, y=sy, size_pt=2.7,
                            color=_INK, font="bold", align="left"))
    # §BH50(d): each swatch draws, and its label prints, the colour the product is drawn with — so the sheet
    # never prints a hex it no longer draws
    for i, label in enumerate(MATERIALS):
        row = palette_row(label)
        swy = sy + 3.2 + i * 6.0
        children.append(Rect(name=f"swatch-{label.lower()}", x=sx, y=swy,
                             w=6, h=4,
                             fill=SolidFill(color=row["color"]),
                             stroke=Stroke(color=_INK, width_mm=0.12)))
        children.append(TextRun(name=f"swatch-label-{label.lower()}",
                                text=f"{label} {row['hex']}", x=sx + 7.5,
                                y=swy + 3.0, size_pt=1.9, color=_INK,
                                align="left"))
    if sku:
        children.append(TextRun(name="sku", text=f"SKU: {sku}", x=12,
                                y=283.0, size_pt=5, color=_INK, font="bold",
                                align="left"))

    root = Group(name="Artwork", role="artwork", children=children)
    doc = Document(page_w=_PAGE_W, page_h=_PAGE_H,
                   title=product_name or "Container concept",
                   metadata={
                       "typography_surface": "apps/ire/compose_dropper.py::compose_dropper_sheet",  # §BH32(h)
                       "target": "product_container",
                       "archetype": "bottle",
                       "mode": "native",
                       "logo_zone_used": logo_used,
                       "front_zone_id": (front_zone or {}).get("zone_id"),
                       "placements": placements,
                       # §BH50(f)(2): the section map, and the front's net content — since §BH67(c)2 the
                       # product record's `net_weight` as held, never this composer's literal; none when silent
                       "back_copy_drawings": back_copy_drawings,
                       "copy_literals": [
                           {"slot": "net_content", "node": P("front-net-content"),
                            "text": net_content,
                            "source": "Product.net_weight — the product record, as held (§BH67(c)2)"}
                           for P in (lambda n: n, lambda n: "flat-" + n)] if net_content else [],
                       "surface_inventory": {"BODY_FRONT": "hero",
                                             "BODY_BACK": "readable_info",
                                             "BOTTOM": "code_area"},
                       "front_back_relationship": {
                           "schema_version":
                               "container_front_back_relationship/1.0",
                           "front_role": "hero_brand_name_motif",
                           "back_role": "readable_info_inci_legal",
                           "roles_distinct": True},
                       "motif_family": "ruled_field",
                       "nonprinting_objects": list(NONPRINTING),
                       "material_stack_used": True,
                       back_panel.SCHEMA: back_panel_record,
                   }, root=root)
    # §BH50(b): the panel holds the small copy, or the composer says so by name — measured on this
    # document, in the faces it draws with, against the confirmed front zone
    if front_zone is not None:
        doc.metadata[FRONT_COPY_FIT_SCHEMA] = front_copy_fit(
            doc, front_zone, print_runs=print_size_runs(g, front_zone, logo_path, name_lines=front_lines,
                                                        descriptor=front_descriptor, net_content=net_content,
                                                        **_mk))
    # §BH50(d): the product's palette through the layer, recorded; the emitter's role map is declared for the
    # brand-resolved hexes only, so a literal the sheet's furniture shares (the ink) is never declared and the
    # document-wide map cannot recolour the furniture
    palette = product_palette()
    doc.metadata[PALETTE_SCHEMA] = palette
    colour_roles.declare_roles(doc, {r["hex"]: r["role"] for r in palette["rows"]
                                     if r["source"] == colour_roles.SOURCE_BRAND_GOV})

    live_text = sum(1 for n, _ in doc.walk() if n.type == "text")
    paths = sum(1 for n, _ in doc.walk() if n.type in ("path", "rect"))
    rasters = sum(1 for n, _ in doc.walk() if n.type == "image")
    # [the owner's second answer of 2026-09-25: a mark drawn from the approved vector master is no raster, and the
    # line says so — only when one is drawn, so every other sheet's census line is the line it always was]
    marks = sum(1 for n, _ in doc.walk() if _brand_mark.is_mark(n))
    root.children.append(TextRun(
        name="census-line",
        text=(f"11 · CENSUS: {live_text + 1} live text · {paths} vector "
              f"paths · {rasters} rasters (reference/review + controlled "
              "logo fallback) · 0 decorative") if not marks else
             (f"11 · CENSUS: {live_text + 1} live text · {paths} vector "
              f"paths · {rasters} rasters (reference/review) · {marks} "
              "marks from the approved vector master · 0 decorative"),
        x=12, y=287.5, size_pt=2.3, color=_INK, align="left"))
    # §BH50(f)(1): this composer states what every run it emitted IS — the
    # product's printed copy by the surface it prints on (the hero front and
    # its flat twin on BODY_FRONT, the true-scale panel on BODY_BACK), the
    # strip's and the bottom diagram's depictions, and the sheet's own
    # furniture — so the §W2 floor reads the copy printed on the product and
    # nothing else. A run this pass does not know stays undeclared and is
    # judged by inference and disclosed; the product-path test proves the
    # census empty. Metadata on the nodes only: no drawn byte moves.
    from apps.ire.compose_container import TRUE_SCALE_SURFACE_PREFIX as _TSP
    from apps.ire.print_scope import declare as _declare_print_scopes
    _front_zid = (front_zone or {}).get("zone_id")
    _back_zid = (back_zone or {}).get("zone_id")
    doc.metadata["print_scope_census"] = _declare_print_scopes(
        doc,
        printed_groups={"FRONT_DIRECT_PRINT": ("BODY_FRONT", _front_zid),
                        "FrontArtworkFlat": ("BODY_FRONT", _front_zid),
                        f"{_TSP}{back_panel.SURFACE}": ("BODY_BACK", _back_zid)},
        depiction_groups={"Surface-BODY_BACK": ("BODY_BACK", _back_zid),
                          "Surface-BOTTOM": ("BOTTOM",
                                             (bottom_zone or {}).get("zone_id"))},
        annotation_names=("sheet-title", "sheet-status-12", "panel-label-hero",
                          "sheet-back-panel-true-scale-label", "confirmed-dims",
                          "sku", "census-line"),
        annotation_prefixes=("panel-label-", "swatch-label-"))
    return doc


__all__ = ["MATERIALS", "NONPRINTING", "compose_dropper_sheet"]
