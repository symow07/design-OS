"""The Design Graph — the central contract of the whole IRE pipeline.

Every stage speaks THIS schema and nothing else: VUE emits it, the Brand
Asset Resolver rewrites AssetRef nodes in it, the IRE compositor builds it,
the validators check it, and every Illustrator emitter (pdf_ai, jsx)
consumes it. No component invents its own structure — swap any stage and the
pipeline still composes as long as it speaks the graph.

Nodes preserve the medium of each authored element: live type, vector logos,
geometry and placed illustration pixels. Hybrid masters validate image asset
identity and effective PPI before emission; a bitmap is never a substitute for
required live copy, an approved vector mark or measured geometry.

Coordinate system: millimetres, y-DOWN, origin top-left — the same flat
system the dieline geometry engine uses (apps/dielines/geometry). Emitters
convert to each backend's axis convention. Colours are 0..1 floats; a hex
helper is provided. Round-trips losslessly to/from JSON via pydantic.
"""
from __future__ import annotations

import contextlib
import contextvars
import math
from typing import Annotated, Literal, Optional, Union

from annotated_types import Ge, Le
from pydantic import BaseModel, Field, model_serializer, model_validator

from apps.ire.text_script import is_rtl

# ---------------------------------------------------------------------------
# Bounds: a value past one of the drawing's own bounds is brought to it, and said
# ---------------------------------------------------------------------------

#: [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design. A failing check fixes the
#: drawing itself and re-checks; if it still fails, the design continues and the problem is shown beside Approve in
#: plain words."] 125 stopped on a bound of this schema: a line asked 0.6 em of letter-spacing against the 0.5 a run
#: takes. While a drawing is made (``bounds_kept``), a value past one of a model's CLOSED bounds (``ge``/``le``) is
#: brought to that bound and recorded, so the stage says it beside Approve; outside a drawing the schema refuses as
#: before — a repair is made only where it is said. An open bound (a size above zero) is never "brought" anywhere: a
#: size of nothing is a fault of the engine, and stops, in words.
_BROUGHT: contextvars.ContextVar = contextvars.ContextVar("graph_values_brought_to_bound", default=None)
_BOUNDS: dict = {}

#: what each bounded value is, in words — every closed bound of this schema has its words (the wiring check holds it)
BOUND_WORDS = {
    "r": "a colour's red", "g": "a colour's green", "b": "a colour's blue",
    "offset": "a gradient stop's place along it", "opacity": "an opacity",
    "tracking_em": "a line's letter-spacing", "blur_mm": "a shadow's blur",
    "start_opacity": "a fade's starting opacity", "end_opacity": "a fade's ending opacity",
}
#: the unit a bounded value is said in
BOUND_UNITS = {"tracking_em": " em", "blur_mm": " mm"}
#: a value past its bound by no more than this is arithmetic's rounding (1.0000000002 for 1): brought, never said
BOUND_NOISE = 1e-6


def closed_bounds(cls) -> list:
    """``[(field, lowest, highest)]`` — the closed bounds a model's own fields declare (``None`` where unbounded)."""
    found = _BOUNDS.get(cls)
    if found is None:
        found = []
        for name, info in cls.model_fields.items():
            lo = next((float(m.ge) for m in info.metadata if isinstance(m, Ge)), None)
            hi = next((float(m.le) for m in info.metadata if isinstance(m, Le)), None)
            if lo is not None or hi is not None:
                found.append((name, lo, hi))
        _BOUNDS[cls] = found
    return found


@contextlib.contextmanager
def bounds_kept():
    """While a drawing is made: every value brought to its bound, ``[{"model", "field", "asked", "set", "of"}]``."""
    token = _BROUGHT.set([])
    try:
        yield _BROUGHT.get()
    finally:
        _BROUGHT.reset(token)


def bound_words(row: dict) -> str:
    """One value brought to its bound, in words: what it is, what it asked, the bound, what it is drawn at."""
    unit = BOUND_UNITS.get(row["field"], "")
    what = BOUND_WORDS.get(row["field"], row["field"].replace("_", " "))
    of = (" (%s)" % row["of"]) if row.get("of") else ""
    return "%s%s asked %g%s, past the %g%s the drawing takes — drawn at %g%s" % (
        what, of, row["asked"], unit, row["set"], unit, row["set"], unit)


class _Bounded(BaseModel):
    """A model whose closed bounds a drawing keeps (``bounds_kept``) instead of stopping on."""

    @model_validator(mode="before")
    @classmethod
    def _to_its_bounds(cls, data):
        brought = _BROUGHT.get()
        if brought is None or not isinstance(data, dict):
            return data
        changed = None
        for name, lo, hi in closed_bounds(cls):
            value = data.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or math.isnan(value):
                continue
            to = lo if (lo is not None and value < lo) else hi if (hi is not None and value > hi) else None
            if to is None:
                continue
            if changed is None:
                changed = dict(data)
            changed[name] = to
            if abs(float(value) - to) > BOUND_NOISE:     # arithmetic's own rounding is brought, never said
                of = data.get("text") or data.get("name") or ""
                brought.append({"model": cls.__name__, "field": name, "asked": float(value), "set": to,
                                "of": str(of)[:60]})
        return changed if changed is not None else data

# ---------------------------------------------------------------------------
# Paint: colours, fills, strokes
# ---------------------------------------------------------------------------


class Color(_Bounded):
    """An RGB colour in 0..1, with an optional CMYK override for print.

    RGB is always present (screen preview + reportlab RGB path); CMYK, when
    set, is what a production emitter should prefer so brand spot colours
    survive to plate.
    """
    r: float = Field(ge=0.0, le=1.0)
    g: float = Field(ge=0.0, le=1.0)
    b: float = Field(ge=0.0, le=1.0)
    cmyk: Optional[tuple[float, float, float, float]] = None

    @classmethod
    def from_hex(cls, value: str, cmyk: tuple[float, float, float, float] | None = None) -> "Color":
        h = value.lstrip("#")
        if len(h) != 6:
            raise ValueError(f"expected #RRGGBB, got {value!r}")
        return cls(r=int(h[0:2], 16) / 255.0,
                   g=int(h[2:4], 16) / 255.0,
                   b=int(h[4:6], 16) / 255.0, cmyk=cmyk)

    def to_hex(self) -> str:
        return f"#{round(self.r * 255):02X}{round(self.g * 255):02X}{round(self.b * 255):02X}"


class GradientStop(_Bounded):
    offset: float = Field(ge=0.0, le=1.0)
    color: Color
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class GradientFill(BaseModel):
    """Editable axial/radial gradient (emits as a PDF shading / native AI
    gradient, never a baked raster)."""
    type: Literal["gradient"] = "gradient"
    kind: Literal["linear", "radial"] = "linear"
    stops: list[GradientStop] = Field(min_length=2)
    # linear: (x1,y1)->(x2,y2); radial: (cx,cy) with radius r. mm, doc space.
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    cx: float = 0.0
    cy: float = 0.0
    r: float = 0.0


class SolidFill(_Bounded):
    type: Literal["solid"] = "solid"
    color: Color
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class PatternFill(_Bounded):
    """§BH65(c)4 — a vector PATTERN inside the element's shape: engraved lines, a cross-hatch, a stipple or halftone of
    dots, a texture grain, or concentric rings. Emitted as native vector geometry cut to the shape — never a raster,
    and never a PDF pattern resource the colour counter could not read."""
    type: Literal["pattern"] = "pattern"
    kind: Literal["lines", "crosshatch", "dots", "grain", "rings"]
    color: Color
    #: the distance between two lines, two dots' centres, two rings — or, for a grain, the mean distance between marks
    spacing_mm: float = Field(gt=0.0)
    #: a line's or a ring's weight; a dot's diameter; a grain mark's length is spacing x 0.5
    weight_mm: float = Field(default=0.15, gt=0.0)
    angle_deg: float = 0.0
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    #: a grain is seeded, so the same element draws the same marks every time
    seed: int = 1


class MeshFill(BaseModel):
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (8) and (9): "Glow is a real soft blur, never a stack of
    hard bands", "Gradients are smooth, never flat bands".] A smooth colour field over a shape: a mesh of patches, each
    four corners (mm, page space, round the patch) and a colour at each corner, the colour between them blended
    smoothly — emitted as the PDF's own smooth shading (a Coons patch mesh) and as Illustrator's gradient mesh, never a
    stack of bands and never a picture. ``patches``: ``[[x0, y0, x1, y1, x2, y2, x3, y3, hex0, hex1, hex2, hex3]]``."""
    type: Literal["mesh"] = "mesh"
    patches: list[list] = Field(min_length=1)
    #: how the layered file carries it, where Illustrator draws it as the drawing does — a field read on a grid
    #: (``{"xs", "ys", "inks"}``: the corners' places, mm, and their colours, row by row) as thin strips each one smooth
    #: gradient across; a glow round a line (``{"points", "closed", "rings": [{"width", "hex", "blur"}]}``, mm, the
    #: outermost ring first) as strokes under Illustrator's own Gaussian blur. Neither: its patches, said
    grid: Optional[dict] = None
    blur: Optional[dict] = None
    #: [his goal of 2026-10-13, (8)] each patch's four corners' own strength (0 to 1, in the patches' order): a glow
    #: fades to nothing at its reach, so what is drawn beneath it — a sky, a ground, roses — shows through as it does
    #: under a real blur, never a colour read from elsewhere. None: every corner its full colour
    alphas: Optional[list[list[float]]] = None

    @model_validator(mode="after")
    def _alphas_match(self):
        if self.alphas is not None and (len(self.alphas) != len(self.patches)
                                        or any(len(a) != 4 or not all(0.0 <= float(v) <= 1.0 for v in a)
                                               for a in self.alphas)):
            raise ValueError("a mesh's alphas are four strengths (0 to 1) for each of its patches")
        return self


Fill = Annotated[Union[SolidFill, GradientFill, PatternFill, MeshFill], Field(discriminator="type")]


class Stroke(_Bounded):
    color: Color
    width_mm: float = Field(gt=0.0)
    dash: Optional[tuple[float, float]] = None   # (on, off) mm
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Geometry primitives for vector paths
# ---------------------------------------------------------------------------


class MoveTo(BaseModel):
    op: Literal["M"] = "M"
    x: float
    y: float


class LineTo(BaseModel):
    op: Literal["L"] = "L"
    x: float
    y: float


class CubicTo(BaseModel):
    op: Literal["C"] = "C"
    x1: float
    y1: float
    x2: float
    y2: float
    x: float
    y: float


class ClosePath(BaseModel):
    op: Literal["Z"] = "Z"


Segment = Annotated[Union[MoveTo, LineTo, CubicTo, ClosePath], Field(discriminator="op")]


# ---------------------------------------------------------------------------
# Nodes (discriminated on ``type``). All nodes may carry a name so groups and
# objects arrive in Illustrator with meaningful labels.
# ---------------------------------------------------------------------------


#: §BH65(c)2 — the finishes the press applies after the ink. An INK finish (foil, metallic ink) IS the colour the
#: element prints in; a CLEAR finish (spot UV, gloss varnish, soft-touch laminate, emboss, deboss) sits on the
#: element's own ink. Either way the finish prints from its own PLATE — the emitter writes each plate on its own page
#: after the artwork, a 100 % black mask in register, labelled with ``plate`` (apps/ire/container_finishes.py).
FinishKind = Literal["foil", "metallic_ink", "spot_uv", "gloss_varnish", "soft_touch", "emboss", "deboss"]


class Finish(BaseModel):
    kind: FinishKind
    #: the plate's name as a printer reads it: FOIL_ROSE_GOLD, SPOT_UV, SOFT_TOUCH
    plate: str = Field(min_length=1)
    #: what an INK finish looks like on page 1 — the metal's depiction; a clear finish has none of its own
    appearance: Optional[Color] = None


#: fields a node carries only when set. A document that uses none of them dumps BYTE-IDENTICALLY to one written
#: before they existed, so no design-graph hash and no serialised graph identity moves for a document that does not
#: use the new vocabulary (§BH65(c): the composer learns words; the documents that never say them do not change).
_OMIT_WHEN_UNSET = ("finishes", "blend_mode", "opacity_mask", "shadow", "tracking_em", "text_case", "turn",
                    # [the owner's second answer of 2026-09-25: a Path's fill rule, set only on the house mark drawn
                    # from its approved vector master (apps/ire/brand_mark.py) — no other path dumps it]
                    "fill_rule",
                    # [D-D9-5, Day 9: "the name is lettering"] the words a group's drawing stands for, set only on a
                    # logotype drawn as outlines (apps/ire/lettering.py) — no other group dumps it
                    "actual_text")

#: §BH65(c)5 — the PDF blend modes a node may print in (PDF 1.4 §7.2.4), by the planner's own spelling
BlendMode = Literal["multiply", "screen", "overlay", "soft-light", "hard-light", "darken", "lighten", "color-dodge",
                    "color-burn", "difference", "exclusion"]


class Shadow(_Bounded):
    """§BH65(c)7 — a SOFT SHADOW under the element: its silhouette offset by (offset_x_mm, offset_y_mm), its edge
    softened over ``blur_mm``. APPROXIMATED in vector — PDF has no blur — and the contract says so."""
    offset_x_mm: float = 0.6
    offset_y_mm: float = 0.8
    blur_mm: float = Field(default=1.2, ge=0.0)
    color: Color
    opacity: float = Field(default=0.35, ge=0.0, le=1.0)


class _NodeBase(_Bounded):
    name: str = ""
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    #: §BH65(c)2 — see Finish. A LIST, because one element takes more than one finish: a foil name that is also
    #: embossed is two plates (measured on the first render, where a single field let the emboss overwrite the
    #: foil). At most one INK finish counts — the first; the clear ones stack on it. On a Group they reach every
    #: leaf below it, except a clear finish on a CLIPPED Group, which floods the clip's region instead.
    finishes: list[Finish] = Field(default_factory=list)
    #: §BH65(c)5 — the node (a Group: everything below it) prints in this blend mode over what is under it
    blend_mode: Optional[BlendMode] = None
    #: §BH65(c)7 — a soft shadow under the node (a Group: under each of its shapes)
    shadow: Optional[Shadow] = None

    @model_serializer(mode="wrap")
    def _omit_unset_vocabulary(self, handler):
        data = handler(self)
        if isinstance(data, dict):
            for key in _OMIT_WHEN_UNSET:
                if key in data and not data[key]:
                    del data[key]
        return data


class Path(_NodeBase):
    """A native vector path: an explicit segment list (Bézier-capable)."""
    type: Literal["path"] = "path"
    segments: list[Segment] = Field(min_length=1)
    fill: Optional[Fill] = None
    stroke: Optional[Stroke] = None
    #: THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803, the block headed "Before I start
    #: testing"): "When I approve the logo trace, switch the mark to it so gold foil can print." The rule the fill
    #: paints by. None — every path before this field — is the emitter's own default, which reportlab makes EVEN-ODD
    #: (canvas.py:407, ``_fillMode = FILL_EVEN_ODD``). "nonzero" is the winding rule an SVG master declares and the
    #: house mark drawn from its approved vector master prints by, page 1 and plate alike: under even-odd an outline
    #: nested in another that runs the SAME way cuts a hole the master does not have. Omitted from every dump when
    #: unset (``_OMIT_WHEN_UNSET``), so no existing design-graph hash moves.
    fill_rule: Optional[Literal["nonzero", "evenodd"]] = None


class Rect(_NodeBase):
    """Convenience primitive; emitters draw a real rectangle (rounded when
    ``radius_mm`` > 0), not four line segments."""
    type: Literal["rect"] = "rect"
    x: float
    y: float
    w: float
    h: float
    radius_mm: float = 0.0
    fill: Optional[Fill] = None
    stroke: Optional[Stroke] = None


#: §BH50(f)(1), OWNER RULED 2026-09-13 — what a text run IS, stated by the
#: composer that emitted it, so the §W2 floor reads the copy printed on the
#: product by the SURFACE it prints on and never by where the run sits on the
#: page or what it is named.
PRINTED_ON_PRODUCT = "PRINTED_ON_PRODUCT"          # size_pt is the size it prints at
DEPICTION_OF_PRODUCT_COPY = "DEPICTION_OF_PRODUCT_COPY"   # a schematic of product copy at diagram size
SHEET_ANNOTATION = "SHEET_ANNOTATION"              # the review sheet's own furniture

#: §BH65(c)8 — the widest letter-spacing a run takes, in em of its own size. [His goal of 2026-10-13
#: (OWNER_BLOCKER_CLEARANCE.md), (1): 125 "stopped while drawing … on one of its own checks".] ONE bound: the composer
#: spaces a line no wider than this (``compose_container.MAP_TYPE_MAX_TRACK_EM``) — it spaced 125's capitals to 0.6
#: against this 0.5, a bound written twice, disagreeing, and the run was refused
TRACKING_EM_MAX = 0.5


class PrintScope(BaseModel):
    """§BH50(f)(1): the composer's declaration of what a run is. A product
    kind names the surface it is on (and the zone when the composer knows
    it); an annotation sits on no product surface. ABSENT on a run means
    UNDECLARED — never "out of scope": a reader judges an undeclared run by
    the inference it used before and says so, so a forgotten declaration
    fails closed."""
    kind: Literal["PRINTED_ON_PRODUCT", "DEPICTION_OF_PRODUCT_COPY",
                  "SHEET_ANNOTATION"]
    surface: Optional[str] = None
    zone_id: Optional[str] = None

    @model_validator(mode="after")
    def _surface_rule(self):
        if self.kind == SHEET_ANNOTATION and self.surface:
            raise ValueError("a sheet annotation sits on no product surface")
        if self.kind != SHEET_ANNOTATION and not self.surface:
            raise ValueError(f"{self.kind} needs the surface it is on")
        return self


class TextRun(_NodeBase):
    """Editable live text. ``outline=True`` asks the emitter to convert to
    vector outlines (font-compat fallback) — never rasterize."""
    type: Literal["text"] = "text"
    text: str
    x: float
    y: float
    font: str = "regular"          # logical role; emitter maps to a real face
    size_pt: float = Field(gt=0.0)
    color: Color
    align: Literal["left", "center", "right"] = "left"
    # §BH32(d)(i): right-to-left is DETECTED from the text when a producer
    # leaves it unset — the first strong-directional character decides (bidi
    # P2/P3, apps/ire/text_script.is_rtl). §BH31 measured that no producer
    # ever set this flag, so Arabic runs reached the emitter as Latin runs.
    # An explicit True/False from a producer is kept as its declaration.
    rtl: Optional[bool] = None
    outline: bool = False
    # 2A-6E-CORR-7: rotation around the anchor point, degrees CCW —
    # vertical consumer copy (e.g. POLVO HORNEADO on the right edge) stays
    # LIVE text instead of being outlined or dropped.
    rotation_deg: float = 0.0
    # §BH50(f)(1): the composer's declaration of what this run is (see
    # PrintScope). EXCLUDED from every dump: it is read in-process by the two
    # §W2 instruments and is not part of the document's serialised identity,
    # so a declared document dumps byte-identically to an undeclared one and
    # no design-graph hash moves. None means undeclared, never out of scope.
    print_scope: Optional[PrintScope] = Field(default=None, exclude=True)
    #: §BH65(c)8 — letter-spacing, in em of the run's own size, added after every glyph but the last
    tracking_em: Optional[float] = Field(default=None, ge=0.0, le=TRACKING_EM_MAX)
    #: §BH65(c)8 — "upper": the run PRINTS in capitals; ``text`` keeps the record's own words
    text_case: Optional[Literal["upper"]] = None

    @model_validator(mode="after")
    def _detect_rtl(self):
        if self.rtl is None:
            self.rtl = is_rtl(self.text)
        return self


class Image(_NodeBase):
    """Raster escape hatch (Phase-1 interim motif/logo). Validators flag any
    Image that lands in a structural layer; the asset library replaces these
    with vector AssetRefs in Phase 2. ``clip`` is an optional clip path in
    doc-space segments."""
    type: Literal["image"] = "image"
    src: str                       # absolute path to the raster
    x: float
    y: float
    w: float
    h: float
    clip: Optional[list[Segment]] = None


class Barcode(_NodeBase):
    """Semantic machine-readable node — emitters render it as native VECTOR
    (EAN-13 bars / QR modules), never an image."""
    type: Literal["barcode"] = "barcode"
    symbology: Literal["ean13", "qr"]
    value: str
    x: float
    y: float
    w: float
    h: float


class AssetRef(_NodeBase):
    """A reference to a Brand Asset Library entry (Phase 2). Resolved in place
    to a Group of vector Paths before emission. ``query`` lets the compositor
    ask for an asset it hasn't resolved yet (a library miss triggers the
    offline, human-approved minting flow)."""
    type: Literal["asset_ref"] = "asset_ref"
    #: [the owner's second answer of 2026-09-25: ``brand-mark:<sha256>`` names the house mark's approved vector
    #: master — ``apps/ire/brand_mark.expand`` draws it, at emit and at handoff, as ONE Path of the master's outlines
    #: at nonzero winding (not a Group: one path, so a counter is cut by the rule); the box is what instruments read]
    asset_id: Optional[str] = None
    query: str = ""                # semantic request when asset_id is unknown
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    recolor: Optional[Color] = None


class StickerBridge(_NodeBase):
    """TEMPORARY bridge (Phase 1) to the existing, pixel-correct trilingual
    sticker renderer (apps/dielines/exporters/info_panel.draw_info_panel).

    The sticker's auto-fit trilingual layout is not yet ported to native graph
    nodes; until it is, this node lets the info face ship through the graph
    pipeline with zero visual regression by delegating its region to the
    proven renderer at emit time. To be replaced by a real node subtree in a
    dedicated later slice — the ONE deliberate contract exception, isolated
    here so it is easy to find and remove."""
    type: Literal["sticker_bridge"] = "sticker_bridge"
    x: float
    y: float
    w: float
    h: float
    info: dict = Field(default_factory=dict)
    # [his review of 119, 2026-10-05, point 3: "The back panel must match the other panels."] the panel's own ground
    # the copy stands on: given, the sticker lays no paper and draws no frame of its own
    ground: Optional[str] = None
    # [his review of 119, 2026-10-05, point 2: "THE BACK PANEL IS LAID OUT, NOT CRAMMED"] the carton's plan for this
    # panel (its region in the panel's millimetres, the blocks it carries, its title and foot, its one size) and the
    # ink its copy is set in; empty, the sticker as before
    layout: dict = Field(default_factory=dict)
    ink: Optional[str] = None


class OpacityMask(_Bounded):
    """§BH65(c)6 — a FADE: the group's opacity runs from ``start_opacity`` to ``end_opacity`` along a line
    ((x1, y1) -> (x2, y2)) or out from a centre ((cx, cy), radius ``r``), mm, doc space. Emitted as a true PDF
    luminosity soft mask — never a raster, never flattened to one alpha."""
    kind: Literal["linear", "radial"] = "linear"
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    cx: float = 0.0
    cy: float = 0.0
    r: float = 0.0
    start_opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    end_opacity: float = Field(default=0.0, ge=0.0, le=1.0)


class Group(_NodeBase):
    """A named group → a named Illustrator group/layer. Nesting models the
    document hierarchy (Artwork > Product > Label > Logo ...)."""
    type: Literal["group"] = "group"
    children: list["Node"] = Field(default_factory=list)
    # Semantic role so downstream stages can reason without name-matching
    # (e.g. validators: "structural" groups must contain no Image nodes).
    role: Literal[
        "artwork", "background", "panel", "product", "label", "logo",
        "typography", "decoration", "effects", "structure", "info", "generic",
    ] = "generic"
    clip: Optional[list[Segment]] = None
    #: §BH65(c)6 — everything below fades through this soft mask
    opacity_mask: Optional[OpacityMask] = None
    #: [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (2): "A palette or compact lies flat: its box's front is
    #: the lid's face (landscape). Use each container's real orientation for every form."] a group whose children are
    #: laid out upright in their own frame and turned onto the page — ``(a, b, c, d, e, f)`` in mm, y down:
    #: x' = a·x + c·y + e, y' = b·x + d·y + f; a quarter turn (a, b, c, d each 0 or ±1) and a move. Its clip and its
    #: children are in its own frame. None — every group before it — is drawn as laid out.
    turn: Optional[tuple[float, float, float, float, float, float]] = None
    #: [D-D9-5, Day 9: "Enchanted Rose" becomes a logotype built by our engine from a licensed face's own outlines] the
    #: words this group's drawing stands for, in logical order. A logotype is outlines, never live text, so its copy
    #: would not extract; the emitter wraps a group that names its words in a marked-content span whose ActualText is
    #: these words (pdf_ai._draw_group). None — every group before it — writes no span and is omitted from every dump
    #: (``_OMIT_WHEN_UNSET``), so no design-graph hash moves.
    actual_text: Optional[str] = None

    @model_validator(mode="after")
    def _a_quarter_turn(self):
        if self.turn is not None:
            a, b, c, d = self.turn[:4]
            if any(v not in (-1.0, 0.0, 1.0) for v in (a, b, c, d)) or abs(a * d - b * c) != 1.0:
                raise ValueError("a group's turn is a quarter turn and a move: %r" % (self.turn,))
        return self


def quarter_turn(width_mm: float, height_mm: float, at_x: float, at_y: float) -> tuple:
    """[His goal of 2026-10-13, (2).] The turn that stands a frame laid out ``width_mm`` wide and ``height_mm`` tall, its
    top-left at (``at_x``, ``at_y``), on a panel ``height_mm`` wide and ``width_mm`` tall at the same top-left: the
    frame's top edge along the panel's left, its right edge along the panel's top — a landscape front drawn upright,
    on a die whose front stands. (u, v) in the frame → (at_x + (v − at_y), at_y + width_mm − (u − at_x))."""
    return (0.0, -1.0, 1.0, 0.0, at_x - at_y, at_y + width_mm + at_x)


def turned_point(turn, x: float, y: float) -> tuple:
    """A point of a turned group's own frame on the page."""
    a, b, c, d, e, f = turn
    return a * x + c * y + e, b * x + d * y + f


Node = Annotated[
    Union[Group, Path, Rect, TextRun, Image, Barcode, AssetRef, StickerBridge],
    Field(discriminator="type"),
]


class Document(BaseModel):
    """The whole design. ``page_w/h`` in mm; ``root`` is the top group whose
    subtree is the entire artwork + dieline linework."""
    schema_version: int = 1
    page_w: float = Field(gt=0.0)
    page_h: float = Field(gt=0.0)
    title: str = ""
    metadata: dict = Field(default_factory=dict)
    root: Group
    #: [his final goal, 2026-10-05, B1: "Two artboards, OUTSIDE and INSIDE."] the sheet's inside, drawn on its own
    #: artboard after ``root``'s (the outside); None — every document before it — draws the one artboard it always did,
    #: and is omitted from every dump, so no design-graph hash moves
    inside: Optional[Group] = None

    @model_validator(mode="after")
    def _root_is_group(self) -> "Document":
        if self.root.type != "group":
            raise ValueError("Document.root must be a Group")
        return self

    @model_serializer(mode="wrap")
    def _omit_unset_inside(self, handler):
        data = handler(self)
        if isinstance(data, dict) and data.get("inside") is None:
            data.pop("inside", None)
        return data

    # --- traversal helpers shared by resolver / validators / emitters -------

    def walk(self):
        """Depth-first (node, parent_group) over the whole tree."""
        def _walk(node, parent):
            yield node, parent
            if isinstance(node, Group):
                for child in node.children:
                    yield from _walk(child, node)
        yield from _walk(self.root, None)

    def find_role(self, role: str) -> list[Group]:
        return [n for n, _ in self.walk()
                if isinstance(n, Group) and n.role == role]


# Recursive forward refs (Group.children -> Node -> Group ...).
Group.model_rebuild()
Document.model_rebuild()
