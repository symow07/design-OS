"""Bounded vector design-language library (Phase 2A-6, §7).

Generalizes the deterministic Liquid Veil composer into a small, closed set
of reconstructable primitives. A "design language" is a named recipe that
turns a parameter set into native graph nodes — editable gradients, Bézier
paths, filled ribbons — for one surface.

Deliberately CLOSED. If a Gate-1 visual cannot be responsibly rebuilt from
the primitives here, :func:`resolve_language` raises
:class:`VectorReconstructionReviewRequired` and the pipeline stops. There is
no image-tracing path and no raster fallback: silently printing pixels is
the failure this phase exists to remove.

Supported primitives (§7): base fills · gradients · ribbons · flowing lines ·
contour streams · geometric fields · line patterns · simple abstract motifs ·
panel masks · finish masks · live typography.

Every generator exposes its parameters on :class:`LanguageParameters`, so a
designer can recolor (swatches), retune (density, scale, stroke width,
opacity), reweight per panel (emphasis) and reassign finishes without
regenerating anything upstream.
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field, replace

from apps.ire.graph import (
    ClosePath,
    Color,
    CubicTo,
    GradientFill,
    GradientStop,
    LineTo,
    MoveTo,
    Path,
    Segment,
    SolidFill,
    Stroke,
)


class VectorReconstructionReviewRequired(ValueError):
    """The requested visual cannot be built from the supported primitives.

    Raised instead of degrading to a printable raster. Carries the code the
    API and the validators surface.
    """
    code = "VECTOR_RECONSTRUCTION_REVIEW_REQUIRED"

    def __init__(self, message: str, *, requested: str = "",
                 supported: tuple[str, ...] = ()):
        super().__init__(message)
        self.requested = requested
        self.supported = tuple(supported)


# --- paint vocabulary ---------------------------------------------------------


@dataclass(frozen=True)
class Swatch:
    """A named, CMYK-bearing colour. Renaming/recolouring one swatch
    recolours every object that references it."""
    name: str
    hex: str
    cmyk: tuple[float, float, float, float]

    def color(self) -> Color:
        return Color.from_hex(self.hex, cmyk=self.cmyk)


@dataclass(frozen=True)
class SwatchSet:
    ground_top: Swatch
    ground_bottom: Swatch
    line_light: Swatch
    line_deep: Swatch
    accent: Swatch
    ink: Swatch

    def all(self) -> tuple[Swatch, ...]:
        return (self.ground_top, self.ground_bottom, self.line_light,
                self.line_deep, self.accent, self.ink)

    def to_dict(self) -> dict:
        # §BH67: a SOURCED swatch (the concept's own colour) carries no CMYK override — RGB, like the sourced ink
        return {s.name: {"hex": s.hex, "cmyk": list(s.cmyk) if s.cmyk is not None else None} for s in self.all()}


DEFAULT_SWATCHES = SwatchSet(
    ground_top=Swatch("GROUND_TOP", "#E8C9B3", (0.06, 0.22, 0.30, 0.02)),
    ground_bottom=Swatch("GROUND_BOTTOM", "#F0DECB", (0.04, 0.12, 0.20, 0.00)),
    line_light=Swatch("LINE_LIGHT", "#F7EFE4", (0.02, 0.05, 0.10, 0.00)),
    line_deep=Swatch("LINE_DEEP", "#D9B49A", (0.10, 0.32, 0.42, 0.05)),
    accent=Swatch("ACCENT_FOIL", "#B76E79", (0.12, 0.62, 0.42, 0.12)),
    ink=Swatch("INK", "#59283A", (0.35, 0.85, 0.45, 0.45)),
)

#: 2A-6E-CORR-7: the Powder Constellation palette — every name is an
#: editable CMYK swatch a designer recolors globally.
POWDER_CONSTELLATION_SWATCHES = SwatchSet(
    ground_top=Swatch("WARM_IVORY_BASE", "#FAF3EC",
                      (0.02, 0.05, 0.08, 0.00)),
    ground_bottom=Swatch("BLUSH_PINK", "#F2C4CE", (0.02, 0.30, 0.10, 0.00)),
    line_light=Swatch("SOFT_PEACH_PARTICLES", "#F0C9A8",
                      (0.04, 0.24, 0.36, 0.00)),
    line_deep=Swatch("DUSTY_PINK_TYPE", "#C98B96",
                     (0.14, 0.52, 0.28, 0.04)),
    accent=Swatch("ROSE_GOLD_PLACEHOLDER", "#B76E79",
                  (0.12, 0.62, 0.42, 0.12)),
    ink=Swatch("WARM_GREY_SUPPORTING_TEXT", "#8A7F78",
               (0.40, 0.40, 0.42, 0.20)),
)
WHITE_TYPE_HIGHLIGHT = Swatch("WHITE_TYPE_HIGHLIGHT", "#FDFBF7",
                              (0.00, 0.01, 0.03, 0.00))
SOFT_MINT_WASH = Swatch("SOFT_MINT_WASH", "#E8F5F0", (0.09, 0.00, 0.06, 0.00))


# --- panel roles ---------------------------------------------------------------

ROLE_FRONT = "front"
ROLE_BACK = "back"
ROLE_SIDE_LEFT = "side_left"
ROLE_SIDE_RIGHT = "side_right"
ROLE_TOP_FLAP = "top_flap"
ROLE_BOTTOM_FLAP = "bottom_flap"
ROLE_DUST_FLAP = "dust_flap"
ROLE_GLUE_FLAP = "glue_flap"

#: How strongly each surface carries the design (§8). The front is the
#: strongest expression; the back prioritizes regulatory readability; sides
#: coordinate without mechanically repeating the front; flaps are reduced.
DEFAULT_EMPHASIS: dict[str, float] = {
    ROLE_FRONT: 1.0,
    ROLE_BACK: 0.0,          # quiet ground only — legal copy must stay legible
    ROLE_SIDE_LEFT: 0.55,
    ROLE_SIDE_RIGHT: 0.55,
    ROLE_TOP_FLAP: 0.35,
    ROLE_BOTTOM_FLAP: 0.35,
    ROLE_DUST_FLAP: 0.25,
    ROLE_GLUE_FLAP: 0.15,    # glued face — artwork here is wasted ink
}


def panel_role(name: str) -> str:
    """Map an engine panel/component id onto a design panel role."""
    n = (name or "").lower()
    if n in (ROLE_FRONT, ROLE_BACK, ROLE_SIDE_LEFT, ROLE_SIDE_RIGHT):
        return n
    if n in ("glue_tab", "glue-tab", ROLE_GLUE_FLAP):
        return ROLE_GLUE_FLAP
    if "dust" in n:
        return ROLE_DUST_FLAP
    if n.startswith("top-"):
        return ROLE_TOP_FLAP
    if n.startswith("bottom-"):
        return ROLE_BOTTOM_FLAP
    return ROLE_SIDE_LEFT


# --- parameters -----------------------------------------------------------------


@dataclass(frozen=True)
class LanguageParameters:
    """Everything a designer can retune without touching code."""
    swatches: SwatchSet = DEFAULT_SWATCHES
    density: float = 1.0             # elements per 10 mm of surface width
    scale: float = 1.0               # motif scale multiplier
    stroke_min_mm: float = 0.18
    stroke_max_mm: float = 0.32
    opacity: float = 0.9
    ribbon_opacity: float = 0.35
    control_jitter: float = 1.0      # 0 = perfectly regular, 1 = organic
    emphasis: dict = field(default_factory=lambda: dict(DEFAULT_EMPHASIS))
    finish: str = "none"             # "none" | "spot_uv" | "emboss" | "foil"
    continuation: str = "wrap"       # "wrap" (continue across panels) | "reset"
    seed: int = 0

    def for_surface(self, role: str) -> "LanguageParameters":
        """This parameter set weighted for one panel role."""
        weight = float(self.emphasis.get(role, 0.5))
        return replace(self, density=self.density * weight, opacity=self.opacity)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["swatches"] = self.swatches.to_dict()
        return d


# --- generators -------------------------------------------------------------------
#
# Each takes (bounds, params, rng, gx, gy) and returns graph nodes. Bounds are
# (x, y, w, h) in dieline mm; gx/gy translate into document space.


def _stroke(params, rng, deep=False):
    sw = params.swatches
    return Stroke(
        color=(sw.line_deep if deep else sw.line_light).color(),
        width_mm=rng.uniform(params.stroke_min_mm, params.stroke_max_mm),
        opacity=params.opacity,
    )


def _points_to_cubics(pts, gx, gy) -> list[Segment]:
    segs: list[Segment] = []
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        segs.append(CubicTo(
            x1=gx(xa), y1=gy(ya + (yb - ya) / 3.0),
            x2=gx(xb), y2=gy(ya + 2.0 * (yb - ya) / 3.0),
            x=gx(xb), y=gy(yb)))
    return segs


def _meander(x0, y0, h, amp, rng, steps=None):
    steps = steps or max(3, int(h / 24.0))
    return [(x0 + rng.uniform(-amp, amp), y0 + h * i / steps)
            for i in range(steps + 1)]


def gen_gradient_field(bounds, params, rng, gx, gy) -> list:
    """Primitive: base fill / gradient. One editable axial gradient."""
    bx, by, bw, bh = bounds
    return [Path(
        name="gradient-field",
        segments=[MoveTo(x=gx(bx), y=gy(by)), LineTo(x=gx(bx + bw), y=gy(by)),
                  LineTo(x=gx(bx + bw), y=gy(by + bh)),
                  LineTo(x=gx(bx), y=gy(by + bh)), ClosePath()],
        fill=GradientFill(
            kind="linear",
            stops=[GradientStop(offset=0.0,
                                color=params.swatches.ground_top.color()),
                   GradientStop(offset=1.0,
                                color=params.swatches.ground_bottom.color())],
            x1=gx(bx + bw / 2), y1=gy(by),
            x2=gx(bx + bw / 2), y2=gy(by + bh)),
    )]


def gen_flowing_lines(bounds, params, rng, gx, gy) -> list:
    """Primitive: flowing lines — meandering vertical Bézier streams."""
    bx, by, bw, bh = bounds
    n = max(0, int(bw / 10.0 * params.density * 4))
    nodes = []
    for i in range(n):
        x_base = bx + bw * (i + 0.5) / max(n, 1)
        x_base += rng.uniform(-1.5, 1.5) * params.control_jitter
        amp = rng.uniform(0.06, 0.16) * bw / 4.0 * params.scale
        pts = _meander(x_base, by, bh, amp * params.control_jitter, rng)
        nodes.append(Path(
            name=f"flow-line-{i}",
            segments=[MoveTo(x=gx(pts[0][0]), y=gy(pts[0][1]))]
                     + _points_to_cubics(pts, gx, gy),
            stroke=_stroke(params, rng, deep=rng.random() < 0.3)))
    return nodes


def gen_ribbons(bounds, params, rng, gx, gy) -> list:
    """Primitive: ribbons — closed translucent veil bands."""
    bx, by, bw, bh = bounds
    n = max(0, int(bw / 10.0 * params.density))
    nodes = []
    for i in range(n):
        x_base = bx + bw * rng.uniform(0.15, 0.85)
        amp = rng.uniform(0.10, 0.20) * bw / 4.0 * params.scale
        width = rng.uniform(1.6, 3.2) * params.scale
        down = _meander(x_base, by, bh, amp * params.control_jitter, rng)
        up = [(x + width, y) for x, y in reversed(down)]
        segs: list[Segment] = [MoveTo(x=gx(down[0][0]), y=gy(down[0][1]))]
        segs += _points_to_cubics(down, gx, gy)
        segs.append(LineTo(x=gx(up[0][0]), y=gy(up[0][1])))
        segs += _points_to_cubics(up, gx, gy)
        segs.append(ClosePath())
        nodes.append(Path(name=f"ribbon-{i}", segments=segs,
                          fill=SolidFill(color=params.swatches.line_light.color()),
                          opacity=params.ribbon_opacity))
    return nodes


def gen_contour_streams(bounds, params, rng, gx, gy) -> list:
    """Primitive: contour streams — nested horizontal topographic curves."""
    bx, by, bw, bh = bounds
    n = max(0, int(bh / 10.0 * params.density * 1.2))
    nodes = []
    for i in range(n):
        y_base = by + bh * (i + 0.5) / max(n, 1)
        amp = rng.uniform(0.5, 2.0) * params.scale * params.control_jitter
        steps = max(3, int(bw / 12.0))
        pts = [(bx + bw * j / steps,
                y_base + math.sin(j * 0.9 + i) * amp) for j in range(steps + 1)]
        nodes.append(Path(
            name=f"contour-{i}",
            segments=[MoveTo(x=gx(pts[0][0]), y=gy(pts[0][1]))]
                     + _points_to_cubics(pts, gx, gy),
            stroke=_stroke(params, rng, deep=(i % 4 == 0))))
    return nodes


def gen_geometric_field(bounds, params, rng, gx, gy) -> list:
    """Primitive: geometric field — stacked strata bands."""
    bx, by, bw, bh = bounds
    n = max(1, int(3 * params.density))
    nodes = []
    for i in range(n):
        top = by + bh * i / n
        height = bh / n
        deep = i % 2 == 0
        nodes.append(Path(
            name=f"strata-{i}",
            segments=[MoveTo(x=gx(bx), y=gy(top)),
                      LineTo(x=gx(bx + bw), y=gy(top)),
                      LineTo(x=gx(bx + bw), y=gy(top + height)),
                      LineTo(x=gx(bx), y=gy(top + height)), ClosePath()],
            fill=SolidFill(
                color=(params.swatches.line_deep if deep
                       else params.swatches.line_light).color()),
            opacity=0.18 + 0.10 * (i % 3)))
    return nodes


def gen_line_pattern(bounds, params, rng, gx, gy) -> list:
    """Primitive: line pattern — regular ruled/diagonal field."""
    bx, by, bw, bh = bounds
    step = max(1.5, 4.0 / max(params.density, 0.05)) * params.scale
    nodes, i = [], 0
    x = bx - bh
    while x < bx + bw:
        nodes.append(Path(
            name=f"rule-{i}",
            segments=[MoveTo(x=gx(x), y=gy(by)),
                      LineTo(x=gx(x + bh), y=gy(by + bh))],
            stroke=_stroke(params, rng, deep=(i % 5 == 0))))
        x += step
        i += 1
    return nodes


def _pattern_rect(name, bounds, gx, gy, fill):
    bx, by, bw, bh = bounds
    return Path(name=name, segments=[MoveTo(x=gx(bx), y=gy(by)), LineTo(x=gx(bx + bw), y=gy(by)),
                                     LineTo(x=gx(bx + bw), y=gy(by + bh)), LineTo(x=gx(bx), y=gy(by + bh)),
                                     ClosePath()], fill=fill)


def gen_engraved_field(bounds, params, rng, gx, gy) -> list:
    """§BH65(c)4 primitive: an ENGRAVED field — fine parallel hatching on a diagonal, crossed at a wider spacing
    and lower weight, the way an engraved plate builds tone. Native vector lines inside the region."""
    from apps.ire.graph import PatternFill
    spacing = max(0.55, 1.1 / max(params.density, 0.05)) * params.scale
    deep, light = params.swatches.line_deep.color(), params.swatches.line_light.color()
    return [_pattern_rect("engraved-field", bounds, gx, gy, PatternFill(
                kind="lines", color=deep, spacing_mm=spacing, weight_mm=0.12, angle_deg=32.0,
                opacity=params.opacity)),
            _pattern_rect("engraved-field-cross", bounds, gx, gy, PatternFill(
                kind="lines", color=light, spacing_mm=spacing * 1.7, weight_mm=0.08, angle_deg=-32.0,
                opacity=params.opacity * 0.6))]


def gen_pattern_repeat(bounds, params, rng, gx, gy) -> list:
    """§BH65(c)4 primitive: a PATTERN REPEAT — an offset grid of dots, the halftone a printed repeat is built from."""
    from apps.ire.graph import PatternFill
    spacing = max(1.2, 2.4 / max(params.density, 0.05)) * params.scale
    return [_pattern_rect("pattern-repeat", bounds, gx, gy, PatternFill(
        kind="dots", color=params.swatches.line_deep.color(), spacing_mm=spacing, weight_mm=spacing * 0.28,
        opacity=params.opacity))]


def gen_halo_rings(bounds, params, rng, gx, gy) -> list:
    """§BH65(c)4 primitive: HALO rings — concentric fine rings from the region's centre."""
    from apps.ire.graph import PatternFill
    spacing = max(0.8, 1.6 / max(params.density, 0.05)) * params.scale
    return [_pattern_rect("halo-rings", bounds, gx, gy, PatternFill(
        kind="rings", color=params.swatches.line_deep.color(), spacing_mm=spacing, weight_mm=0.14,
        opacity=params.opacity))]


#: §BH67(b)1 — a petal bloom's own parameters, read from the concept's words by ``container_motif.petal_parameters``;
#: these are the values a concept that says nothing more gets, each the executor's and each recorded on the spec
PETAL_DEFAULTS = {"count": 7, "arrangement": "radial", "outline": "none", "width_ratio": 0.42, "opacity": None}


def _petal_path(name: str, ax: float, ay: float, theta: float, length: float, width: float, gx, gy):
    """One closed Bézier petal: POINTED at its anchor, widest two-thirds out, ROUND at its tip — the teardrop the
    concepts draw ("slender Bézier teardrop petals"), turned to ``theta`` radians about its anchor."""
    h = width / 2.0
    c, s = math.cos(theta), math.sin(theta)

    def at(u, v):
        return gx(ax + u * c - v * s), gy(ay + u * s + v * c)
    L = length
    pts = [((0.25 * L, 0.55 * h), (0.55 * L, h), (0.72 * L, h)), ((0.90 * L, h), (L, 0.55 * h), (L, 0.0)),
           ((L, -0.55 * h), (0.90 * L, -h), (0.72 * L, -h)), ((0.55 * L, -h), (0.25 * L, -0.55 * h), (0.0, 0.0))]
    x0, y0 = at(0.0, 0.0)
    segs = [MoveTo(x=x0, y=y0)]
    for (u1, v1), (u2, v2), (u3, v3) in pts:
        (x1, y1), (x2, y2), (x3, y3) = at(u1, v1), at(u2, v2), at(u3, v3)
        segs.append(CubicTo(x1=x1, y1=y1, x2=x2, y2=y2, x=x3, y=y3))
    segs.append(ClosePath())
    return Path(name=name, segments=segs)


def gen_petal_bloom(bounds, params, rng, gx, gy, petals: dict | None = None) -> list:
    """§BH67(b)1 — SOFT PETALS DRAWN AS PETALS. The count, the arrangement and the outline pattern are the concept's
    own words (``petals``): a FAN rising from the foot of the region, a RADIAL bloom round its centre, or a SCATTER;
    every petal filled from the motif's palette in turn — its SOURCED colours since the §BH67 hard stop — and, where
    the words say "alternating filled … and … outline", every second petal an outline. Deterministic; zero rasters.
    Until §BH67(b)1 a petal concept was drawn by ``gen_abstract_motif`` (scattered vertical ellipses, a count from
    the box width) or, through the classifier's substring vote, as dewdrops."""
    p = dict(PETAL_DEFAULTS, **(petals or {}))
    bx, by, bw, bh = bounds
    n = max(1, int(p["count"]))
    palette = [params.swatches.line_light.color(), params.swatches.line_deep.color(), params.swatches.accent.color()]
    alpha = p["opacity"] if p["opacity"] is not None else params.opacity
    nodes = []
    for i in range(n):
        if p["arrangement"] == "fan":
            # rising from the foot of the region, spread across 160 degrees, the centre petals longest
            ax, ay = bx + bw / 2.0, by + bh * 0.94
            frac = 0.5 if n == 1 else i / (n - 1)
            theta = math.radians(-90.0 + (frac - 0.5) * 160.0)
            length = min(bw * 0.50, bh * 0.86) * (0.80 + 0.20 * math.cos(theta + math.pi / 2.0))
        elif p["arrangement"] == "scatter":
            ax, ay = bx + bw * rng.uniform(0.2, 0.8), by + bh * rng.uniform(0.25, 0.85)
            theta = math.radians(rng.uniform(0.0, 360.0))
            length = min(bw, bh) * rng.uniform(0.22, 0.32)
        else:
            # a radial bloom: each petal's point at a small inner ring, its round tip outward
            cx, cy = bx + bw / 2.0, by + bh / 2.0
            theta = math.radians(-90.0 + 360.0 * i / n)
            inner = min(bw, bh) * 0.05
            ax, ay = cx + inner * math.cos(theta), cy + inner * math.sin(theta)
            length = min(bw, bh) * 0.42
        path = _petal_path(f"petal-{i}", ax, ay, theta, length, length * float(p["width_ratio"]), gx, gy)
        colour = palette[i % len(palette)]
        if p["outline"] == "all" or (p["outline"] == "alternate" and i % 2 == 1):
            path.stroke = Stroke(color=colour, width_mm=0.25)
        else:
            path.fill = SolidFill(color=colour, opacity=round(float(alpha), 3))
        nodes.append(path)
    return nodes


#: [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
#: "The lid is missing the concept's rule, ring and radial lines."] a RADIAL LINES motif's own parameters, read from the
#: concept's words by ``container_motif.radial_parameters``; these are what a concept that says nothing more gets, each
#: the executor's and each recorded on the spec. ``rays``: a ray every 5 degrees — near the approved concept of task 110,
#: whose picture draws about eighteen to a quarter turn
RADIAL_DEFAULTS = {"rays": 72, "nodes": False, "taper": False, "opacity": None}
#: "a small filled circular node": 0.85 mm across — measured off task 110's approved concept (about 6 px of a lid face
#: 779 px across its 110 mm)
RADIAL_NODE_DIAMETER_MM = 0.85
#: "density tapering toward the rim": each ray reaches between this share of the way to its region's edge and all of it,
#: so fewer rays — and fewer nodes — reach the rim; the executor's reading of words that give no number
RADIAL_TAPER_SHORTEST = 0.55


def _node_segments(cx: float, cy: float, r: float, gx, gy) -> list:
    """A closed circle of radius ``r`` at (cx, cy): four cubics at the circle's own control distance."""
    k = 0.5522847498307936
    return [MoveTo(x=gx(cx + r), y=gy(cy)),
            CubicTo(x1=gx(cx + r), y1=gy(cy + r * k), x2=gx(cx + r * k), y2=gy(cy + r), x=gx(cx), y=gy(cy + r)),
            CubicTo(x1=gx(cx - r * k), y1=gy(cy + r), x2=gx(cx - r), y2=gy(cy + r * k), x=gx(cx - r), y=gy(cy)),
            CubicTo(x1=gx(cx - r), y1=gy(cy - r * k), x2=gx(cx - r * k), y2=gy(cy - r), x=gx(cx), y=gy(cy - r)),
            CubicTo(x1=gx(cx + r * k), y1=gy(cy - r), x2=gx(cx + r), y2=gy(cy - r * k), x=gx(cx + r), y=gy(cy)),
            ClosePath()]


def gen_radial_lines(bounds, params, rng, gx, gy, radial: dict | None = None) -> list:
    """[the owner's second answer of 2026-09-25: "The lid is missing the concept's rule, ring and radial lines."] RADIAL
    LINES DRAWN AS RAYS — task 110's own words: "fine Bézier stroked lines emanating from a single centre point behind
    the type, each ending in a small filled circular node, all in Blush #F2C4CE at reduced opacity, density tapering
    toward the rim". Each ray a straight cubic Bézier from the region's centre outward at the language's finest stroke
    (``stroke_min_mm``); where the words say so each ends in a filled node (``RADIAL_NODE_DIAMETER_MM``), and the rays'
    reach tapers so fewer reach the rim. ONE colour, the motif's own: ``line_light``, the first of the sourced motif
    palette — the colour the motif sentence names. Never ``line_deep``, which that palette fills from the colour-field
    sentence (on task 110 the type's Deep Rose). Its opacity is the words' own number, or their reading where they give
    none (``container_motif.radial_parameters``). The rays begin where they stop touching — n rays w wide are w apart at
    r = n·w/2π — so the centre stays a point, not a blot. Named ``radial-ray-i`` / ``radial-node-i`` so a composer can
    shorten a ray and move its node together. Deterministic; zero rasters. Until this a radial concept was drawn as a
    powder scatter: its words scored one hit each for three families and the tie went to the first listed."""
    p = dict(RADIAL_DEFAULTS, **(radial if radial is not None else {}))
    bx, by, bw, bh = bounds
    n = int(round(float(p["rays"]) * params.density))
    if n < 3:
        return []            # a near-quiet surface carries no rays
    cx, cy = bx + bw / 2.0, by + bh / 2.0
    colour = params.swatches.line_light.color()
    alpha = round(float(p["opacity"] if p["opacity"] is not None else params.opacity), 3)
    stroke_mm = params.stroke_min_mm
    node_r_mm = RADIAL_NODE_DIAMETER_MM / 2.0 if p["nodes"] else 0.0
    inner_mm = n * stroke_mm / (2.0 * math.pi)
    out = []
    for i in range(n):
        theta = 2.0 * math.pi * i / n - math.pi / 2.0
        c, s = math.cos(theta), math.sin(theta)
        across = (bx + bw - cx) / c if c > 1e-12 else ((bx - cx) / c if c < -1e-12 else math.inf)
        down = (by + bh - cy) / s if s > 1e-12 else ((by - cy) / s if s < -1e-12 else math.inf)
        reach_mm = min(across, down) - node_r_mm
        if p["taper"]:
            reach_mm *= RADIAL_TAPER_SHORTEST + (1.0 - RADIAL_TAPER_SHORTEST) * rng.random()
        if reach_mm <= inner_mm:
            continue
        x0, y0, x1, y1 = cx + inner_mm * c, cy + inner_mm * s, cx + reach_mm * c, cy + reach_mm * s
        out.append(Path(name=f"radial-ray-{i}", segments=[
            MoveTo(x=gx(x0), y=gy(y0)),
            CubicTo(x1=gx(x0 + (x1 - x0) / 3.0), y1=gy(y0 + (y1 - y0) / 3.0),
                    x2=gx(x0 + 2.0 * (x1 - x0) / 3.0), y2=gy(y0 + 2.0 * (y1 - y0) / 3.0), x=gx(x1), y=gy(y1))],
            stroke=Stroke(color=colour, width_mm=stroke_mm, opacity=alpha)))
        if p["nodes"]:
            out.append(Path(name=f"radial-node-{i}", segments=_node_segments(x1, y1, node_r_mm, gx, gy),
                            fill=SolidFill(color=colour, opacity=alpha)))
    return out


def gen_abstract_motif(bounds, params, rng, gx, gy) -> list:
    """Primitive: simple abstract motif — a repeated elliptical petal mark."""
    bx, by, bw, bh = bounds
    n = max(1, int(bw / 10.0 * params.density))
    nodes = []
    k = 0.5522847498307936
    for i in range(n):
        cx = bx + bw * rng.uniform(0.15, 0.85)
        cy = by + bh * rng.uniform(0.1, 0.9)
        r = rng.uniform(1.5, 4.0) * params.scale
        ry = r * rng.uniform(1.4, 2.2)
        nodes.append(Path(
            name=f"motif-{i}",
            segments=[
                MoveTo(x=gx(cx), y=gy(cy - ry)),
                CubicTo(x1=gx(cx + r * k), y1=gy(cy - ry),
                        x2=gx(cx + r), y2=gy(cy - ry * k),
                        x=gx(cx + r), y=gy(cy)),
                CubicTo(x1=gx(cx + r), y1=gy(cy + ry * k),
                        x2=gx(cx + r * k), y2=gy(cy + ry),
                        x=gx(cx), y=gy(cy + ry)),
                CubicTo(x1=gx(cx - r * k), y1=gy(cy + ry),
                        x2=gx(cx - r), y2=gy(cy + ry * k),
                        x=gx(cx - r), y=gy(cy)),
                CubicTo(x1=gx(cx - r), y1=gy(cy - ry * k),
                        x2=gx(cx - r * k), y2=gy(cy - ry),
                        x=gx(cx), y=gy(cy - ry)),
                ClosePath()],
            fill=SolidFill(color=params.swatches.line_light.color()),
            opacity=0.30))
    return nodes


# --- languages -----------------------------------------------------------------


def gen_powder_constellation(bounds, params, rng, gx, gy) -> list:
    """Primitive: powder constellation (2A-6E-CORR-7).

    A bounded, fully editable particle field: small circles, slim ellipses,
    short curved strokes, four-point radiance stars and sparse cross ticks,
    with varied sizes and opacity, massing toward the LOWER-RIGHT corner and
    dispersing diagonally toward mid-panel — the Powder Constellation
    concept's motif as native vector objects. Emitted in named sub-groups
    ("constellation-core", "constellation-drift") so a designer can delete,
    recolor, thin or re-finish whole regions; every particle is its own
    named node. Density derives from params.density and the surface
    emphasis, so side-panel continuation is a REDUCED field, never a
    mechanical repeat (the per-surface seed differs by construction)."""
    from apps.ire.graph import Group

    bx, by, bw, bh = bounds
    # §4 (2A-6E-CORR-8): the front carries ~90-150 particles at meaningful
    # scale; sides get a REDUCED continuation via their emphasis weighting.
    total = min(220, int(bw * 1.3 * params.density))
    if total < 3:
        return []          # a near-quiet surface carries no constellation
    core_count = max(2, int(total * 0.7))
    peach = params.swatches.line_light.color()
    rose = params.swatches.accent.color()
    k = 0.5522847498307936

    def _particle(index, cluster):
        if cluster == "core":
            u = max(rng.uniform(0, 1), rng.uniform(0, 1))     # →1 bias
            v = max(rng.uniform(0, 1), rng.uniform(0, 1))
            cx = bx + bw * (0.40 + 0.58 * u)
            cy = by + bh * (0.40 + 0.58 * v)
        else:
            t = rng.uniform(0, 1)
            cx = bx + bw * (0.15 + 0.65 * t) + bw * rng.uniform(-0.08, 0.08)
            cy = by + bh * (0.15 + 0.65 * t) + bh * rng.uniform(-0.10, 0.10)
        cx = min(max(cx, bx + 1.0), bx + bw - 1.0)
        cy = min(max(cy, by + 1.0), by + bh - 1.0)
        size = rng.uniform(0.72, 2.95) * params.scale
        color = rose if rng.random() < 0.45 else peach
        alpha = rng.uniform(0.35, 1.0) * params.opacity
        kind = rng.random()
        kind_label = ("circle" if kind < 0.35 else
                      "ellipse" if kind < 0.55 else
                      "tick" if kind < 0.75 else
                      "star" if kind < 0.9 else "cross")
        name = f"particle-{cluster}-{index}-{kind_label}"
        if kind < 0.55:      # circle / slim ellipse
            rx = size
            ry = size * (1.0 if kind < 0.35 else rng.uniform(1.6, 2.6))
            return Path(name=name, segments=[
                MoveTo(x=gx(cx), y=gy(cy - ry)),
                CubicTo(x1=gx(cx + rx * k), y1=gy(cy - ry),
                        x2=gx(cx + rx), y2=gy(cy - ry * k),
                        x=gx(cx + rx), y=gy(cy)),
                CubicTo(x1=gx(cx + rx), y1=gy(cy + ry * k),
                        x2=gx(cx + rx * k), y2=gy(cy + ry),
                        x=gx(cx), y=gy(cy + ry)),
                CubicTo(x1=gx(cx - rx * k), y1=gy(cy + ry),
                        x2=gx(cx - rx), y2=gy(cy + ry * k),
                        x=gx(cx - rx), y=gy(cy)),
                CubicTo(x1=gx(cx - rx), y1=gy(cy - ry * k),
                        x2=gx(cx - rx * k), y2=gy(cy - ry),
                        x=gx(cx), y=gy(cy - ry)),
                ClosePath()],
                fill=SolidFill(color=color, opacity=alpha))
        if kind < 0.75:      # short curved stroke (brush tick)
            length = size * rng.uniform(2.0, 3.5)
            angle = rng.uniform(-0.9, -0.3)
            dx, dy = length * math.cos(angle), length * math.sin(angle)
            return Path(name=name, segments=[
                MoveTo(x=gx(cx), y=gy(cy)),
                CubicTo(x1=gx(cx + dx * 0.3), y1=gy(cy + dy * 0.6),
                        x2=gx(cx + dx * 0.7), y2=gy(cy + dy * 0.4),
                        x=gx(cx + dx), y=gy(cy + dy))],
                stroke=Stroke(color=color, width_mm=max(0.12, size * 0.22),
                              opacity=alpha))
        if kind < 0.9:       # four-point radiance star
            # [his look at 117 drawn from its map, 2026-10-02: small designs like the sparkles "always inconsistent.
            # And not looking good"] the one sparkle every drawing draws, the house's, its arms' reach as before (1.6 x
            # the size) — curved arms, where the straight-sided star's were straight
            from apps.ire import sparkle_glyph
            r_out = size * 1.6
            return Path(name=name, segments=sparkle_glyph.segments(gx(cx), gy(cy), r_out, r_out,
                                                                    sparkle_glyph.HOUSE_PINCH, sparkle_glyph.HOUSE_TIP),
                        fill=SolidFill(color=color, opacity=alpha))
        # sparse cross tick
        arm = size * 1.2
        return Path(name=name, segments=[
            MoveTo(x=gx(cx - arm), y=gy(cy)), LineTo(x=gx(cx + arm), y=gy(cy)),
            MoveTo(x=gx(cx), y=gy(cy - arm)), LineTo(x=gx(cx), y=gy(cy + arm))],
            stroke=Stroke(color=color, width_mm=max(0.12, size * 0.18),
                          opacity=alpha))

    return [
        Group(name="constellation-core", role="decoration", children=[
            _particle(i, "core") for i in range(core_count)]),
        Group(name="constellation-drift", role="decoration", children=[
            _particle(i, "drift") for i in range(max(2, total - core_count))]),
    ]


@dataclass(frozen=True)
class DesignLanguage:
    """A named recipe: ordered primitive generators + default parameters."""
    name: str
    label: str
    generators: tuple = ()
    ground: str = "gradient"          # "gradient" | "solid"
    keywords: tuple[str, ...] = ()
    defaults: LanguageParameters = LanguageParameters()

    def build(self, bounds, params: LanguageParameters, role: str, gx, gy) -> list:
        weighted = params.for_surface(role)
        rng = random.Random(_surface_seed(params.seed, role, self.name))
        nodes: list = []
        for gen in self.generators:
            nodes.extend(gen(bounds, weighted, rng, gx, gy))
        return nodes


def _surface_seed(base: int, surface: str, language: str) -> int:
    return (int(base) * 1000003
            + sum(ord(c) for c in surface) * 131
            + sum(ord(c) for c in language))


LIQUID_VEIL = DesignLanguage(
    name="liquid_veil", label="Liquid Veil (flowing engraved pour)",
    generators=(gen_flowing_lines, gen_ribbons),
    keywords=("liquid", "veil", "pour", "flow", "fluid", "silk", "drape",
              "engraved", "texture", "gradient"),
)
CONTOUR_TERRAIN = DesignLanguage(
    name="contour_terrain", label="Contour Terrain (topographic streams)",
    generators=(gen_contour_streams,),
    keywords=("contour", "topographic", "terrain", "wave", "ripple", "layer"),
)
STRATA_FIELD = DesignLanguage(
    name="strata_field", label="Strata Field (material bands)",
    generators=(gen_geometric_field,),
    keywords=("strata", "band", "block", "geometric", "material", "stack",
              "architectural", "minimal"),
)
RULED_FIELD = DesignLanguage(
    name="ruled_field", label="Ruled Field (line pattern)",
    generators=(gen_line_pattern,),
    keywords=("line", "stripe", "rule", "pinstripe", "grid", "pattern",
              "linear", "graphic"),
)
PETAL_SCATTER = DesignLanguage(
    name="petal_scatter", label="Petal Scatter (abstract botanical motif)",
    generators=(gen_abstract_motif,),
    keywords=("petal", "floral", "botanical", "motif", "bloom", "leaf",
              "organic", "scatter"),
)
QUIET_GROUND = DesignLanguage(
    name="quiet_ground", label="Quiet Ground (gradient only)",
    generators=(),
    keywords=("minimal", "plain", "clean", "quiet", "typographic", "empty"),
)
POWDER_CONSTELLATION = DesignLanguage(
    name="powder_constellation",
    label="Powder Constellation (dispersing particle field)",
    generators=(gen_powder_constellation,),
    keywords=("powder", "particle", "particles", "constellation", "dot",
              "dots", "scatter", "scattered", "sparkle", "star", "stars",
              "speck", "dust", "dispersing", "drift"),
    defaults=LanguageParameters(
        swatches=POWDER_CONSTELLATION_SWATCHES, density=1.0,
        # §4 panel mapping: side continuation is 10-20% of the front count;
        # flaps stay near-quiet; the glue flap carries nothing.
        emphasis={ROLE_FRONT: 1.0, ROLE_BACK: 0.0, ROLE_SIDE_LEFT: 0.12,
                  ROLE_SIDE_RIGHT: 0.45, ROLE_TOP_FLAP: 0.0,
                  ROLE_BOTTOM_FLAP: 0.0, ROLE_DUST_FLAP: 0.0,
                  ROLE_GLUE_FLAP: 0.0}),
)

def gen_dewdrop_constellation(bounds, params, rng, gx, gy) -> list:
    """Primitive: dewdrop constellation (2B-3V-CORR-3 §3).

    A bounded, fully editable field of translucent DROPLETS — closed Bézier
    teardrops, near-circular dew beads and elongated drops, each with its own
    small highlight ellipse, plus sparse sparkle crosses — never generic
    circles-only and never diagonal rules. Movement is VERTICAL sparse→dense:
    a thin origin near the lower edge rising into a denser upper cluster
    (the selected Dewdrop Constellation reading). Emitted in named semantic
    sub-groups ("dewdrop-core", "dewdrop-drift", "dewdrop-highlights") so a
    designer can delete, recolor, thin or re-finish whole regions; every
    droplet is its own named node. Density derives from params.density and
    the surface emphasis, so back/side continuation is a REDUCED field."""
    from apps.ire.graph import Group

    bx, by, bw, bh = bounds
    total = min(180, int(bw * 1.1 * params.density))
    if total < 3:
        return []
    core_count = max(2, int(total * 0.6))       # dense upper cluster
    clear = params.swatches.line_light.color()   # DEWDROP_CLEAR
    peach = params.swatches.line_deep.color()    # DEWDROP_PEACH
    k = 0.5522847498307936
    highlights: list = []

    def _ellipse(name, cx, cy, rx, ry, color, alpha):
        return Path(name=name, segments=[
            MoveTo(x=gx(cx), y=gy(cy - ry)),
            CubicTo(x1=gx(cx + rx * k), y1=gy(cy - ry),
                    x2=gx(cx + rx), y2=gy(cy - ry * k),
                    x=gx(cx + rx), y=gy(cy)),
            CubicTo(x1=gx(cx + rx), y1=gy(cy + ry * k),
                    x2=gx(cx + rx * k), y2=gy(cy + ry),
                    x=gx(cx), y=gy(cy + ry)),
            CubicTo(x1=gx(cx - rx * k), y1=gy(cy + ry),
                    x2=gx(cx - rx), y2=gy(cy + ry * k),
                    x=gx(cx - rx), y=gy(cy)),
            CubicTo(x1=gx(cx - rx), y1=gy(cy - ry * k),
                    x2=gx(cx - rx * k), y2=gy(cy - ry),
                    x=gx(cx), y=gy(cy - ry)),
            ClosePath()],
            fill=SolidFill(color=color, opacity=alpha))

    def _teardrop(name, cx, cy, r, color, alpha):
        """Closed Bézier teardrop: pointed tip above a round bowl."""
        tip_y = cy - r * 2.1
        return Path(name=name, segments=[
            MoveTo(x=gx(cx), y=gy(tip_y)),
            CubicTo(x1=gx(cx + r * 0.55), y1=gy(cy - r * 1.1),
                    x2=gx(cx + r), y2=gy(cy - r * 0.45),
                    x=gx(cx + r), y=gy(cy)),
            CubicTo(x1=gx(cx + r), y1=gy(cy + r * k),
                    x2=gx(cx + r * k), y2=gy(cy + r),
                    x=gx(cx), y=gy(cy + r)),
            CubicTo(x1=gx(cx - r * k), y1=gy(cy + r),
                    x2=gx(cx - r), y2=gy(cy + r * k),
                    x=gx(cx - r), y=gy(cy)),
            CubicTo(x1=gx(cx - r), y1=gy(cy - r * 0.45),
                    x2=gx(cx - r * 0.55), y2=gy(cy - r * 1.1),
                    x=gx(cx), y=gy(tip_y)),
            ClosePath()],
            fill=SolidFill(color=color, opacity=alpha))

    def _droplet(index, cluster):
        # vertical sparse→dense: drift sits low & sparse, core rises dense
        if cluster == "core":
            u = max(rng.uniform(0, 1), rng.uniform(0, 1))
            cy = by + bh * (0.06 + 0.42 * (1 - u))       # upper region
            cx = bx + bw * (0.30 + 0.62 * max(rng.uniform(0, 1),
                                              rng.uniform(0, 1)))
        else:
            t = rng.uniform(0, 1)
            cy = by + bh * (0.45 + 0.50 * t)             # lower, sparser
            cx = bx + bw * (0.08 + 0.55 * t) + bw * rng.uniform(-0.06, 0.06)
        cx = min(max(cx, bx + 1.2), bx + bw - 1.2)
        cy = min(max(cy, by + 1.6), by + bh - 1.2)
        # three size classes (small bead / medium drop / large drop)
        size_class = rng.random()
        size = (rng.uniform(0.5, 0.9) if size_class < 0.45 else
                rng.uniform(0.9, 1.6) if size_class < 0.85 else
                rng.uniform(1.6, 2.6)) * params.scale
        color = peach if rng.random() < 0.6 else clear
        alpha = rng.uniform(0.45, 0.95) * params.opacity
        kind = rng.random()
        if kind < 0.40:                          # near-circular dew bead
            node = _ellipse(f"dewdrop-{cluster}-{index}-bead", cx, cy,
                            size, size * rng.uniform(0.92, 1.05), color, alpha)
        elif kind < 0.78:                        # teardrop
            node = _teardrop(f"dewdrop-{cluster}-{index}-teardrop",
                             cx, cy, size, color, alpha)
        elif kind < 0.94:                        # elongated drop
            node = _ellipse(f"dewdrop-{cluster}-{index}-elongated", cx, cy,
                            size * rng.uniform(0.55, 0.7),
                            size * rng.uniform(1.5, 2.1), color, alpha)
        else:                                    # sparse sparkle cross
            arm = size * 1.1
            return Path(name=f"dewdrop-{cluster}-{index}-sparkle", segments=[
                MoveTo(x=gx(cx - arm), y=gy(cy)),
                LineTo(x=gx(cx + arm), y=gy(cy)),
                MoveTo(x=gx(cx), y=gy(cy - arm)),
                LineTo(x=gx(cx), y=gy(cy + arm))],
                stroke=Stroke(color=clear, width_mm=max(0.12, size * 0.16),
                              opacity=alpha))
        # per-droplet highlight (upper-left inner shine) for the larger beads
        if size >= 0.9 * params.scale:
            highlights.append(_ellipse(
                f"dewdrop-highlight-{cluster}-{index}",
                cx - size * 0.32, cy - size * 0.38,
                size * 0.22, size * 0.14,
                params.swatches.accent.color(),        # DEWDROP_HIGHLIGHT
                min(1.0, alpha + 0.25)))
        return node

    core = [_droplet(i, "core") for i in range(core_count)]
    drift = [_droplet(i, "drift") for i in range(max(2, total - core_count))]
    return [
        Group(name="dewdrop-core", role="decoration", children=core),
        Group(name="dewdrop-drift", role="decoration", children=drift),
        Group(name="dewdrop-highlights", role="decoration",
              children=highlights),
    ]


DEWDROP_CONSTELLATION_SWATCHES = SwatchSet(
    ground_top=Swatch("CONTAINER_TRANSPARENT_BODY", "#FDF7F2",
                      (0.00, 0.03, 0.04, 0.00)),
    ground_bottom=Swatch("PRODUCT_PEACH_ROSE_FILL", "#F2C4CE",
                         (0.02, 0.30, 0.10, 0.00)),
    line_light=Swatch("DEWDROP_CLEAR", "#FFFFFF", (0.0, 0.0, 0.0, 0.0)),
    line_deep=Swatch("DEWDROP_PEACH", "#F7DDE3", (0.02, 0.16, 0.06, 0.00)),
    accent=Swatch("DEWDROP_HIGHLIGHT", "#FFFFFF", (0.0, 0.0, 0.0, 0.0)),
    ink=Swatch("PRODUCT_NAME_PRINT", "#8B3A52", (0.20, 0.80, 0.40, 0.15)),
)

DEWDROP_CONSTELLATION = DesignLanguage(
    name="dewdrop_constellation",
    label="Dewdrop Constellation (translucent droplet field)",
    generators=(gen_dewdrop_constellation,),
    keywords=("dewdrop", "dewdrops", "droplet", "droplets", "dew",
              "teardrop", "teardrops", "drop", "drops", "constellation"),
    defaults=LanguageParameters(
        swatches=DEWDROP_CONSTELLATION_SWATCHES, density=1.0,
        emphasis={ROLE_FRONT: 1.0, ROLE_BACK: 0.10, ROLE_SIDE_LEFT: 0.12,
                  ROLE_SIDE_RIGHT: 0.25, ROLE_TOP_FLAP: 0.0,
                  ROLE_BOTTOM_FLAP: 0.0, ROLE_DUST_FLAP: 0.0,
                  ROLE_GLUE_FLAP: 0.0}),
)

#: §BH65(c)4 — the three families the planner reasons in and nothing could draw (composer_vocabulary.PLANNER_FAMILY_ROUTE)
ENGRAVED_FIELD = DesignLanguage(
    name="engraved_field", label="Engraved Field (fine hatching)",
    generators=(gen_engraved_field,),
    keywords=("engraved", "engraving", "etched", "hatch", "hatching", "guilloche", "linework"),
)
PATTERN_REPEAT = DesignLanguage(
    name="pattern_repeat", label="Pattern Repeat (offset dot grid)",
    generators=(gen_pattern_repeat,),
    keywords=("repeat", "tile", "tiled", "lattice", "halftone", "stipple"),
)
HALO_RINGS = DesignLanguage(
    name="halo_rings", label="Halo Rings (concentric)",
    generators=(gen_halo_rings,),
    keywords=("halo", "concentric", "radial ring", "orbit"),
)
#: §BH67(b)1 — the petal family drawn as itself. No lexical keywords: it is reached ONLY through the family map, so
#: adding it moves no vote of the lexical fallback. ``container_motif.language_for_spec`` binds the concept's own
#: count, arrangement and outline pattern to its generator.
PETAL_BLOOM = DesignLanguage(
    name="petal_bloom", label="Petal Bloom (teardrop petals as the concept arranges them)",
    generators=(gen_petal_bloom,),
    keywords=(),
)
#: [the owner's second answer of 2026-09-25: "The lid is missing the concept's rule, ring and radial lines."] the radial
#: family drawn as itself. No lexical keywords, as the petal bloom has none: reached ONLY through the family map, so
#: adding it moves no vote of the lexical fallback. ``container_motif.language_for_spec`` binds the concept's own node,
#: taper and opacity words to its generator.
RADIAL_LINES = DesignLanguage(
    name="radial_lines", label="Radial Lines (fine rays from one centre, each ending in a node where the words say so)",
    generators=(gen_radial_lines,),
    keywords=(),
)

_LANGUAGES: dict[str, DesignLanguage] = {
    lang.name: lang for lang in (
        LIQUID_VEIL, CONTOUR_TERRAIN, STRATA_FIELD, RULED_FIELD,
        PETAL_SCATTER, QUIET_GROUND, POWDER_CONSTELLATION,
        DEWDROP_CONSTELLATION, ENGRAVED_FIELD, PATTERN_REPEAT, HALO_RINGS, PETAL_BLOOM,
        # [the owner's second answer of 2026-09-25]
        RADIAL_LINES,
    )
}

#: Minimum keyword evidence before a direction is considered reconstructable.
#: Below this the visual is not responsibly rebuildable from these primitives.
MIN_KEYWORD_MATCHES = 2


def supported_languages() -> list[DesignLanguage]:
    return [_LANGUAGES[k] for k in sorted(_LANGUAGES)]


def get_language(name: str) -> DesignLanguage:
    lang = _LANGUAGES.get((name or "").strip())
    if lang is None:
        raise VectorReconstructionReviewRequired(
            f"design language {name!r} is not supported",
            requested=name, supported=tuple(sorted(_LANGUAGES)))
    return lang


def resolve_language(direction: dict | None, *, explicit: str | None = None,
                     variation: dict | None = None) -> DesignLanguage:
    """Choose the design language for the SELECTED visual — or stop.

    2A-6E-CORR-7: when the user approved a structured VARIATION, its own
    signatures and prompt are the authoritative vocabulary — task #50's
    direction text ("fine hairline rule") matched the generic ruled-field
    pattern while the approved Powder Constellation variation was never
    consulted, and the production artwork silently became diagonal stripes.
    The direction is only the LEGACY source (pre-variation tasks).

    Matching is lexical (no model call, no semantic search). A visual whose
    language does not reach ``MIN_KEYWORD_MATCHES`` against any supported
    primitive set raises VECTOR_RECONSTRUCTION_REVIEW_REQUIRED — it is NEVER
    rasterized and never substituted with a generic supported pattern.
    """
    if explicit:
        return get_language(explicit)
    if variation:
        text = " ".join(
            str(variation.get(k) or "") for k in (
                "title", "motif_signature", "composition_signature",
                "color_field_signature", "prompt",
            )
        ).lower()
        if not text.strip():
            raise VectorReconstructionReviewRequired(
                "the selected variation carries no visual description to "
                "reconstruct from",
                requested=str(variation.get("variation_id") or ""),
                supported=tuple(sorted(_LANGUAGES)))
        return _best_language(text,
                              requested=str(variation.get("variation_id")
                                            or ""))
    direction = direction or {}
    text = " ".join(
        str(direction.get(k) or "") for k in (
            "name", "design_axis", "concept_statement", "graphic_elements",
            "imagery_approach", "material_finish_direction", "layout_structure",
            "color_system", "prompt_seed",
        )
    ).lower()
    if not text.strip():
        raise VectorReconstructionReviewRequired(
            "the selected direction carries no visual description to "
            "reconstruct from",
            supported=tuple(sorted(_LANGUAGES)))
    return _best_language(text, requested=str(direction.get("name") or ""))


def _best_language(text: str, *, requested: str) -> DesignLanguage:
    scored = sorted(
        ((sum(1 for kw in lang.keywords if kw in text), lang)
         for lang in _LANGUAGES.values()),
        key=lambda pair: (-pair[0], pair[1].name),
    )
    best_score, best = scored[0]
    if best_score < MIN_KEYWORD_MATCHES:
        raise VectorReconstructionReviewRequired(
            "this visual language cannot be responsibly rebuilt "
            "from the supported vector primitives "
            f"(best match {best.name!r} scored {best_score}, floor is "
            f"{MIN_KEYWORD_MATCHES}) — a designer must extend the library or "
            "choose another direction; the concept render must NOT be printed",
            requested=requested,
            supported=tuple(sorted(_LANGUAGES)))
    return best


__all__ = [
    "DesignLanguage",
    "LanguageParameters",
    "Swatch",
    "SwatchSet",
    "DEFAULT_SWATCHES",
    "POWDER_CONSTELLATION_SWATCHES",
    "WHITE_TYPE_HIGHLIGHT",
    "SOFT_MINT_WASH",
    "gen_powder_constellation",
    "gen_radial_lines", "RADIAL_DEFAULTS", "RADIAL_NODE_DIAMETER_MM", "RADIAL_TAPER_SHORTEST",
    "DEFAULT_EMPHASIS",
    "VectorReconstructionReviewRequired",
    "resolve_language",
    "get_language",
    "supported_languages",
    "panel_role",
    "MIN_KEYWORD_MATCHES",
    "ROLE_FRONT", "ROLE_BACK", "ROLE_SIDE_LEFT", "ROLE_SIDE_RIGHT",
    "ROLE_TOP_FLAP", "ROLE_BOTTOM_FLAP", "ROLE_DUST_FLAP", "ROLE_GLUE_FLAP",
]
