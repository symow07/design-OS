"""Compose a Design Graph for a PRODUCT_CONTAINER concept sheet (Phase B2).

Turns a ``ContainerBackbone`` (the parametric silhouette frame) + the
approved concept's extracted assets into a native-vector concept sheet, in
the ONE shared Design Graph — no subclass, reusing the pdf_ai emitter.

Standard: native-vector container STRUCTURE with explicitly flagged raster
exceptions. Native vector: silhouette, cap/body colour zones, product name,
SKU, colour swatches, anchors. Flagged raster exceptions (isolated,
labelled, technical debt for the Brand Asset Library phase): (1) the
uploaded reference photo — only inside the ``Reference`` group; (2) the
interim label/decorative graphic and the logo bitmap. Nothing else is raster.

[The owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803):
"When I approve the logo trace, switch the mark to it so gold foil can
print." Handed an approved vector master (``logo_master``), the logo is not a
bitmap: it is drawn from the master (``apps/ire/brand_mark.py``).]
"""
from __future__ import annotations

import math
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
    MeshFill,
    MoveTo,
    Path,
    Rect,
    SolidFill,
    Stroke,
    TextRun,
    TRACKING_EM_MAX,
)
# [his goal of 2026-10-13, (7)-(9)] lines drawn as lines, fields and glows as smooth meshes — shared with the lid's art
from apps.pipeline.services import line_geometry as _LG
from apps.ire.nodes import (centered_text, image_node, ink_for,
                            intrinsic_aspect, rect_clip)
from apps.ire import brand_mark as _brand_mark
from apps.ire import sparkle_glyph as _sparkle
# §AY2/AZ5: the composer PREDICTS the brand gate rather than keeping its own
# copy of the cap ratio and the clear-space factor. One model, two readers.
from apps.ire.container_brand_usage import (clear_space_mm, measure_cap_ratio,
                                            text_ink_top)
from apps.ire.container_text_floor import FALLBACK_FLOOR_PT
from apps.pipeline.services.container_contract import zone_surface
from apps.pipeline.targets.container import archetypes as _declared
from apps.pipeline.targets.container.silhouettes import ContainerBackbone
from apps.pipeline.targets.container.silhouettes import _rrect as _rounded_rect

# VQR-1: the concept sheet is PRODUCT-DERIVED, never a fixed page standard.
# The rejected reconstruction shipped on a hardcoded A4 artboard unrelated
# to the 95 mm product; the artboard now derives from the confirmed profile
# with proportional chrome. The factors must stay BELOW the VQR-2A
# artboard_max_product_factor (3.0) so the artboard-fitness axis measures
# a product-derived canvas. Legacy constants kept only as the layout's
# proportional reference frame.
_PAGE_W, _PAGE_H = 210.0, 297.0          # legacy reference frame (unused)
_PAGE_FACTOR_W = 2.45                    # page width  = 2.45 × width_mm
_PAGE_FACTOR_H = 1.62                    # page height = 1.62 × height_mm

# --- §Z1(b): type sizes CHOSEN as type ---------------------------------------
# Every one of these replaced a `max(literal, <a millimetre length> * f)`. The
# instrument that found them is `apps/ire/unit_analysis.py`; a `size_pt` grep
# could not, because these reach `centered_text` as its FIFTH POSITIONAL
# argument and the string "size_pt" appears nowhere at the call site.
#
# The values are MEASURED, not invented: they are what the composer already
# emitted at every product size the repo builds. The sweep is in the test —
# 20×60 through 50×140 mm all emitted the literal, so on the live native path
# this moves nothing below a 59.369 × 163.265 mm bottle (the crossover, found
# by bisection on the old expression over the real geometry). Above it the
# millimetre term used to win and the name grew with the bottle; it now holds
# still, which is §Z1(b) being obeyed rather than a regression. The other two
# paths DO change and by how much is stated in the test, not rounded away
# here: the direct-print hierarchy from 40×110 up, and the non-native
# fallback at every size. Neither is production-reachable.
FRONT_NAME_PT = 8.0        # native front, the live production path
HERO_NAME_PT = 9.0         # direct-print hierarchy, product-name tier
HERO_SUPPORT_PT = 3.2      # direct-print hierarchy, every OTHER support tier
FALLBACK_NAME_PT = 3.75    # the non-native fallback sheet's container label

#: §BH68(b), OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "LID NAME SIZE — BOTH RULINGS STAND, RECONCILED.
#: §Z1(b) says a type size is chosen as type; §BH67(b)4 says size it from the surface. So: the size is a step on the
#: typographic scale, and the step chosen is the largest one the lid's own zone holds for the concept's layout. No
#: computed sizes, and no bottle size on a lid." THE CLASSICAL SCALE of type sizes, in points: 6 to 12 by the point,
#: then 14, 16, 18, 21, 24, 36, 48, 60 and 72. A lid's name is one of these, chosen by trying them from the largest down
#: (`_concept_face`); nothing sizes it arithmetically, and HERO_NAME_PT — the bottle front's tier — is not read there.
TYPE_SCALE_PT = (6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 14.0, 16.0, 18.0, 21.0, 24.0, 36.0, 48.0, 60.0, 72.0)


def scale_step_at_most(value_pt: float) -> float:
    """The largest step of TYPE_SCALE_PT not above ``value_pt``; the smallest step where every step is above it."""
    return max((step for step in TYPE_SCALE_PT if step <= value_pt), default=TYPE_SCALE_PT[0])

#: §BD(a) — OWNER-RULED at 5.0 pt. The VALUE is the owner's; the NAME is the
#: executor's, which is the split he stated when he ruled it.
#:
#: 5.0 pt is the SCREEN/PAD-PRINT FLOOR out of
#: ``container_production_method._METHOD_DEFAULTS``, bound as governing by
#: §W2(a) — whose status is OWNER_CALIBRATED. It is NOT §W2(b)'s flat 5.0 pt
#: fallback. The two rules hold the same number and are different rules, and
#: §W2(b)'s own text says a capability table outranks a fallback; recording
#: which one this is here is the whole reason the distinction survives.
#:
#: WHY THIS IS A NEW CONSTANT AND NOT A HIGHER ``HERO_SUPPORT_PT``. The queued
#: item asked whether the support tier should rise. The owner declined that
#: shape in his own words: *"the name must lead — 9.0 over 5.0 keeps that lead;
#: raising every support tier was a bigger change than the defect."* So the
#: descriptor moves and NOTHING ELSE DOES.
#:
#: WHAT THAT KNOWINGLY LEAVES BEHIND, STATED HERE RATHER THAN DISCOVERED LATER:
#: ``net_content`` stays at ``HERO_SUPPORT_PT`` 3.2, which is BELOW this floor.
#: That is ruled, not overlooked — §BD(e) records it — and it clears only
#: ``BOTTOM_INKJET_CODE``'s 2.0. An instrument that reds on it has found a real
#: thing; the answer is to bring it back to the owner, not to raise this.
HERO_DESCRIPTOR_PT = 5.0   # direct-print hierarchy, descriptor tier (§BD(a))

#: Millimetres of glyph advance PER POINT of type size. This was `_CHAR_W =
#: 0.185`, described as an em fraction and compared against a millimetre
#: width — a point quantity tested against a millimetre one. It is not an em
#: fraction: 0.185 mm/pt IS 0.524 em, which is a real bold advance, whereas
#: 0.185 em is narrower than any face has. **Two errors were cancelling**, and
#: the wrapping looked right because they did. Naming the true dimension makes
#: the arithmetic exact and changes no number.
_CHAR_ADVANCE_MM_PER_PT = 0.185
#: §BH65(c)8 — capitals against mixed case: MEASURED 2026-09-23 on five house names through text_metrics — Poppins-Light
#: (the name's face) 1.039-1.094, Poppins-Regular 1.052-1.103, Montserrat-Bold 1.156-1.204. The estimate takes the
#: largest, so it never passes a capitalised name the clip would then eat.
_CAPS_ADVANCE_FACTOR = 1.2
#: a point is exactly 25.4/72 mm; tracking is em of the run's size, so tracking_em x size_pt x this is millimetres —
#: the `_MM_PER_PT` suffix is the declaration §Z1(a) makes the unit analyser read
_TRACKING_MM_PER_PT = 25.4 / 72.0

#: Millimetres of layout advance PER POINT of type size — §Z1(b) running
#: backwards, the shape WI-P fixed in `compose_dropper`. Each was a bare
#: coefficient turning a point size into a millimetre coordinate. The values
#: are unchanged, so no artwork moves; divide by 25.4/72 to read them as em:
#: 1.15 → 3.26 em, 1.9 → 5.39 em, 1.55 → 4.39 em, 1.0 → 2.83 em. §AB3 rules no
#: leading this sprint, so these are recorded at their incumbent values and
#: WI-V has the em numbers it needs without anything having been decided here.
_NAME_STEP_MM_PER_PT = 1.15
_HERO_STEP_MM_PER_PT = 1.9
_HERO_STEP_TIGHT_MM_PER_PT = 1.55
_BASELINE_DROP_MM_PER_PT = 1.0
#: §BH66(b): a point in millimetres, and how far below its baseline a run's ink reaches, in ems — the ruled front's
#: own model (`_ink_extent`), which places the rule between the name's ink and the supporting line's
_INK_MM_PER_PT = 25.4 / 72.0
_INK_BELOW_EM = 0.25


def _sheet_layout(backbone) -> dict:
    """Product-derived sheet geometry: hero at TRUE 1:1 product scale,
    reference column, surface strip and spec block all proportional to the
    confirmed dimensions — the page can never be an unrelated fixed
    standard, and content fits by construction."""
    W, H = backbone.width_mm, backbone.height_mm
    page_w, page_h = W * _PAGE_FACTOR_W, H * _PAGE_FACTOR_H
    header = 0.12 * H
    con_box = (0.2 * W + 0.9 * W + 0.15 * W, header, W, H)
    ref_box = (0.2 * W, header, 0.9 * W, H)
    strip_box = (0.2 * W, header + H + 0.06 * H, 1.25 * W, 0.18 * H)
    spec_y = header + H + 0.06 * H + 0.18 * H + 0.04 * H
    # chrome scale: text/offsets proportional to the product height, with
    # the old 190 mm hero box as the reference frame
    k = max(0.35, H / 190.0)
    return {"page_w": page_w, "page_h": page_h, "con_box": con_box,
            "ref_box": ref_box, "strip_box": strip_box, "spec_y": spec_y,
            "title_y": header * 0.62, "k": k}
_INK = Color.from_hex("#3F2620")
_OUTLINE_W = 0.4        # mm
_DEFAULT_BODY = "#EAD7D2"
_DEFAULT_CAP = "#C9A24B"
#: [His goal after the pitch page, 2026-10-15, A (2): "METALS: gold and chrome are drawn as metallic (highlights and
#: shadows as the concept shows), never flat tan or grey"] a metal part's light drawn as its concept shows it: its lit
#: colour (a* b*) at the concept's own lightness at each place across it, never darker than ``METAL_L_RANGE[0]`` nor
#: lighter than ``METAL_L_RANGE[1]`` (L*)
METAL_L_RANGE = (4.0, 98.0)


def _metal_stops(hex_: str, lightness: list) -> list:
    """The stops a metal part is drawn with: at each ``[offset, L*]`` of its measured light
    (``flat_motif.light_run``), its own lit colour ``hex_`` taken to that lightness — so a turned colour (the designer's
    eye, a lever) re-tints the same light."""
    import cv2
    import numpy as np
    h = hex_.lstrip("#")
    lab = cv2.cvtColor(np.uint8([[[int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)]]]), cv2.COLOR_BGR2LAB)[0, 0]
    stops = []
    for offset, light in lightness:
        level = min(METAL_L_RANGE[1], max(METAL_L_RANGE[0], float(light)))
        px = np.uint8([[[round(level * 2.55), int(lab[1]), int(lab[2])]]])
        b, g, r = cv2.cvtColor(px, cv2.COLOR_LAB2BGR)[0, 0]
        stops.append(GradientStop(offset=min(1.0, max(0.0, float(offset))),
                                  color=Color.from_hex("#%02X%02X%02X" % (int(r), int(g), int(b)))))
    return stops


def _closure_fill(hex_: str, look: Optional[dict], segments: list):
    """[His goal after the pitch page, 2026-10-15, A (2)] A closure part's fill: its measured light run across its own
    width (a linear gradient, left edge to right, through ``_metal_stops``) where it is metal (``look``), else its colour
    flat. One named path either way, so its levers and the layered file read it as before."""
    if not look or len(look.get("lightness") or []) < 2:
        return SolidFill(color=Color.from_hex(hex_))
    xs = [float(getattr(sg, "x")) for sg in segments if hasattr(sg, "x")]
    ys = [float(getattr(sg, "y")) for sg in segments if hasattr(sg, "y")]
    mid = (min(ys) + max(ys)) / 2.0
    return GradientFill(kind="linear", stops=_metal_stops(hex_, look["lightness"]), x1=min(xs), y1=mid, x2=max(xs),
                        y2=mid)

# layout regions (mm)
_REF_BOX = (12.0, 40.0, 84.0, 150.0)      # left: reference photo
_CON_BOX = (110.0, 40.0, 88.0, 190.0)     # right: editable container (hero)


def _scaled(segments, s, ox, oy):
    """Scale by s and offset by (ox, oy) — backbone-local → sheet coords."""
    out = []
    for seg in segments:
        if seg.op == "M":
            out.append(MoveTo(x=ox + seg.x * s, y=oy + seg.y * s))
        elif seg.op == "L":
            out.append(LineTo(x=ox + seg.x * s, y=oy + seg.y * s))
        elif seg.op == "C":
            out.append(CubicTo(
                x1=ox + seg.x1 * s, y1=oy + seg.y1 * s,
                x2=ox + seg.x2 * s, y2=oy + seg.y2 * s,
                x=ox + seg.x * s, y=oy + seg.y * s))
        else:
            out.append(seg)               # ClosePath
    return out


def _fit(bw: float, bh: float, box) -> tuple[float, float, float]:
    """(scale, ox, oy) to center a bw×bh backbone in a layout box."""
    bx, by, cw, ch = box
    s = min(cw / bw, ch / bh) if bw and bh else 1.0
    ox = bx + (cw - bw * s) / 2.0
    oy = by + (ch - bh * s) / 2.0
    return s, ox, oy


def _tint(color: Color, toward_white: float) -> Color:
    """A lighter tint of ``color`` — a native decoration field, no raster.
    Channels are 0..1 floats (see graph.Color)."""
    f = max(0.0, min(1.0, toward_white))
    mix = lambda c: c + (1.0 - c) * f  # noqa: E731
    return Color(r=mix(color.r), g=mix(color.g), b=mix(color.b))


#: §BH67 HARD STOP, OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md:23350, LIVE): "a finish or colour applied that
#: nothing specified". Every colour this composer PRINTS comes from the caller's ``colors``: ``ink``, the type's colour
#: (``colour_sources.type_ink``), and ``motif``, the motif's colours (``colour_sources.motif_colours``) — each chosen
#: from a record and named in the run's ``container_colour_sources/1.0``. A caller that hands in neither — a test
#: fixture, a path not yet taught — gets the two stand-ins below, which NO record names, and the container target's
#: ``printed_colour_audit`` refuses a run that prints one. `#5A2C3A` is the dropper palette's TYPE_WINE ("authority
#: UNVERIFIED", kept for task 52 by §BH50(f)(9)), carried onto every container without authority; measured on task
#: 91's lid, its name and Arabic line printed in it while the concept says "in Deep Rose". A glow with no colour of
#: its own was a white disc; it is now drawn in the face's own colour, and white is kept only as the stand-in.
_UNSOURCED_INK = "#5A2C3A"
_UNSOURCED_LIGHT = "#FFFFFF"
#: the tints of the body colour this composer prints, by what it prints them for — the ONLY colours it derives,
#: declared here so the audit reads them from their owner
BODY_TINTS = {"native decoration field": 0.55, "surface panel field": 0.6, "back surface panel field": 0.8}


def _name_font(concept_front: Optional[dict]) -> str:
    """§BH67(c)5: the product name's font role — ``font_roles.CONCEPT_NAME`` when the concept names a face from the
    granted set for it (``concept_typeface.read``, carried on the plan as ``typeface``), else the display alias the
    name has always printed in. The layer resolves the lead through the seam; this only marks the runs."""
    from apps.ire.concept_typeface import LEADS
    from apps.ire.font_roles import CONCEPT_NAME
    name = ((concept_front or {}).get("typeface") or {}).get("name") or {}
    return CONCEPT_NAME if name.get("verdict") == LEADS and name.get("stem") else "bold"


def _ink(colors: Optional[dict]) -> Color:
    return Color.from_hex((colors or {}).get("ink") or _UNSOURCED_INK)


def _motif_swatches(colors: Optional[dict]):
    """The motif's palette built ONLY from the caller's sourced motif colours — cycled over the design language's
    six roles, its ink role the type ink — or None, when the caller sourced none (the language's own defaults,
    which the audit refuses)."""
    from apps.ire.design_language import Swatch, SwatchSet
    hexes = [h for h in ((colors or {}).get("motif") or []) if h]
    if not hexes:
        return None

    def pick(i):
        return Swatch("MOTIF_%d" % (i % len(hexes) + 1), hexes[i % len(hexes)], None)
    return SwatchSet(ground_top=pick(0), ground_bottom=pick(1), line_light=pick(0), line_deep=pick(1),
                     accent=pick(2), ink=Swatch("TYPE_INK", _ink(colors).to_hex(), None))


def declared_tints(colors: Optional[dict]) -> dict[str, str]:
    """``{hex: what it is}`` — every tint of the body colour this composer can print for ``colors``."""
    body = Color.from_hex((colors or {}).get("body", _DEFAULT_BODY))
    return {_tint(body, f).to_hex(): "a %d%% tint toward white of the body colour, the %s" % (round(f * 100), what)
            for what, f in BODY_TINTS.items()}


def _body_height(backbone: ContainerBackbone) -> float:
    """Height of the body silhouette (total height minus the closure above
    it) — the dropper's silhouette is the body path, so its top edge is the
    shoulder line."""
    ys = [float(getattr(seg, "y", None))
          for seg in backbone.silhouette
          if getattr(seg, "y", None) is not None]
    top = min(ys) if ys else 0.0
    return backbone.height_mm - top


def _front_zone(zones: list[dict]) -> Optional[dict]:
    """The primary front decoration zone from the confirmed zone set."""
    order = ("FRONT_PRINT_ZONE", "WRAP_LABEL_ZONE", "BODY_FRONT")
    for want in order:
        for z in zones or []:
            if z.get("zone_type") == want or zone_surface(z) == want:
                return z
    return (zones or [None])[0]


def _front_view_zone(zone: Optional[dict], backbone: ContainerBackbone) -> Optional[dict]:
    """[The clean-up's wiring check, 2026-10-05, its finding W11] The front zone as the front view draws it. A body wrap
    label's ``x`` and ``width`` are measured round the unrolled wrap — a jar's proposed label is 0.85 of its
    circumference, centred on its front (``container_contract.propose_zones``) — and every reader here takes a zone's
    ``x`` across the drawn body: read as it stood, the label's centre stood 34 mm past a 60 mm jar, and a mark moved
    clear of the picture's parts was drawn off the sheet (Gate 2: logo clipped, an element outside the artboard). The
    front view shows the half of the wrap facing it: a point at angle φ from the front's centre lands at
    ``D/2 · (1 + sin φ)`` across the body (D its width, the wrap's circumference πD), so the label's front extent is its
    two ends' projections, each held to the visible half. Its height is the body's, unchanged; every other zone, and a
    wrap label wholly on the back, is returned as it is."""
    import math
    if zone is None or zone_surface(zone) != "BODY_WRAP":
        return zone
    d = float(backbone.width_mm)
    a, b = float(zone["x"]), float(zone["x"]) + float(zone["width"])
    phi = [(u - math.pi * d / 2.0) / (d / 2.0) for u in (a, b)]      # each end's angle from the front's centre
    if phi[0] >= math.pi / 2.0 or phi[1] <= -math.pi / 2.0:
        return zone
    x0, x1 = (d / 2.0 * (1.0 + math.sin(max(-math.pi / 2.0, min(math.pi / 2.0, p)))) for p in phi)
    return dict(zone, x=round(x0, 4), width=round(x1 - x0, 4))


# [his answer of 2026-10-05, W10: "a jar's back copy goes on the back of its wrap label; with no wrap, on the base
# label. Never nowhere."] where a design's back copy prints — read off the zones' own surfaces here, where the
# accessor is bound; the panel itself (``back_panel``) stays pure
from apps.ire import back_panel as _bp  # noqa: E402


def _wrap_back_ends(wrap: dict, body_width_mm: float) -> list:
    """The parts of a wrap label behind the body. Round the unrolled wrap (its circumference π × the body's width) the
    front faces the viewer about the middle, as the front view reads it (``compose_container._front_view_zone``), so
    the front is the middle half and the back the two quarters at the ends; a label centred on the front reaches the
    back as its two ends, either side of the seam's gap. Each end kept is a zone of the label's own height and margin,
    the end a reader turning the jar meets first (the far end) first; an end under _bp.WRAP_END_MIN_MM is not used."""
    import math
    c = math.pi * float(body_width_mm)
    a, b = float(wrap["x"]), float(wrap["x"]) + float(wrap["width"])
    ends = []
    for side, x0, x1 in (("its far end", max(a, 0.75 * c), b), ("its near end", a, min(b, 0.25 * c))):
        if x1 - x0 >= _bp.WRAP_END_MIN_MM:
            ends.append(dict(wrap, x=round(x0, 3), width=round(x1 - x0, 3),
                             part="%s — %s" % (_bp.WHERE_WRAP_BACK, side)))
    return ends


def information_zones(zones, body_width_mm: float | None = None) -> tuple:
    """``(where, [zone, …])`` — where this design's back copy prints, in his order (W10): its back print zone; else
    the back of its wrap label (its two ends behind the body, ``_wrap_back_ends``); else its base label (a confirmed
    zone on the base that is not the batch code's window); else ``(None, [])`` — and the caller refuses by name."""
    back = _bp.back_zone(zones)
    if back is not None:
        return _bp.WHERE_BACK_ZONE, [back]
    wrap = next((z for z in zones or [] if zone_surface(z) == "BODY_WRAP"), None)
    if wrap is not None and body_width_mm:
        ends = _wrap_back_ends(wrap, float(body_width_mm))
        if ends:
            return _bp.WHERE_WRAP_BACK, ends
    base = next((z for z in zones or [] if zone_surface(z) in _bp._BASE_SURFACES
                 and z.get("zone_type") != "BOTTOM_CODE_ZONE"), None)
    if base is not None:
        return _bp.WHERE_BASE_LABEL, [base]
    return None, []


def compose_information_panels(sections, zones, body_width_mm, x: float, y: float, **kw) -> tuple:
    """``([Group, …], record)`` — the back copy at the size it prints, on the surface his order gives it
    (``information_zones``). One zone: one panel, as before. A wrap's two ends: the copy flows from the first end to
    the second at section boundaries — the first end takes the whole sections it holds, the second the rest — the
    sections numbered on, nothing dropped, the whole label shrunk evenly where it does not stand (his correction of
    2026-10-07); the record joins the two (one fit, one set of lines). No zone at
    all: no panel, and the record carries _bp.NO_SURFACE — refused by name, never drawn nowhere."""
    where, places = information_zones(zones, body_width_mm)
    # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] the label's QR, on the first panel its copy starts on
    qr_url = kw.pop("qr_url", None)
    if not places:
        _g, rec = _bp.compose_back_panel(sections, None, x, y, **kw)
        return [], {**rec, "where": None, "codes": list(rec["codes"]) + [_bp.NO_SURFACE],
                    "reason": rec["reason"] + " [His answer W10: \"Never nowhere.\"] This design has no back print "
                              "zone, no wrap label reaching the back and no base label: its back copy has no surface, "
                              "and the design is refused by name until it has one."}
    sections = list(sections or [])

    def flow(label_pt=None):
        groups, recs, start, cx = [], [], 0, x
        for i, zone in enumerate(places):
            part = sections[start:]
            if i and not part:
                break                                  # the copy is whole on the ends before: no empty panel is drawn
            surface = zone_surface(zone)
            g, rec = _bp.compose_back_panel(part, zone, cx, y, first_section=start, surface=surface,
                                            label_pt=label_pt, fill_area=True,
                                            **({"qr_url": qr_url} if qr_url and not i else {}), **kw)
            if i < len(places) - 1 and rec.get("emitted"):
                whole = 0
                for s in rec["sections"]:
                    if s["lines_emitted"] < s["lines_required"]:
                        break
                    whole += 1
                whole = max(whole, 1) if part else 0
                if whole < len(part):
                    g, rec = _bp.compose_back_panel(part[:whole], zone, cx, y, first_section=start, surface=surface,
                                                    label_pt=label_pt,
                                                    **({"qr_url": qr_url} if qr_url and not i else {}), **kw)
                start += whole
            else:
                start = len(sections)
            if g is not None:
                groups.append(g)
            recs.append({**rec, "part": zone.get("part", where)})
            cx += float(zone["width"]) + _bp.PANEL_GAP_MM
            if not rec.get("emitted"):
                break
        return groups, recs

    if len(places) == 1:
        groups, recs = flow()                          # one panel: it shrinks whole on its own (``compose_back_panel``)
    else:
        # [His correction of 2026-10-07: "Shrink the whole label evenly until everything fits, keeping its layout,
        # spacing and order."] a wrap's two ends carry one label: it flows from the first end to the second at its size,
        # and where it does not stand on both, the whole label — both ends — steps down a quarter point and flows again,
        # to the floor (``label_floor_of``). One end shrunk alone would have taken the whole label onto the first end at
        # a size the second never shares
        pt, source = _bp.size_for_surface(kw.get("methods_record"), kw.get("size_pt"), zone_surface(places[0]))
        lowest = _bp.label_floor_of(source)
        while True:
            groups, recs = flow(pt)
            if (all(r.get("fits") for r in recs) and sum(len(r.get("sections") or []) for r in recs) == len(sections)) \
                    or pt - 0.25 < lowest - 1e-9:
                break
            pt = round(pt - 0.25, 2)
    if len(recs) == 1:
        return groups, {**recs[0], "where": where}
    worst = max(recs, key=lambda r: r.get("overflow_mm") or 0.0)
    joined = {**recs[0], "where": where,
              "panels": [{k: r.get(k) for k in ("part", "zone_id", "surface", "panel_mm", "origin_mm", "fits",
                                                  "overflow_mm")} for r in recs],
              "emitted": all(r.get("emitted") for r in recs),
              "fit_measured": all(r.get("fit_measured") for r in recs),
              "fits": None if any(r.get("fits") is None for r in recs) else all(r["fits"] for r in recs),
              "copy_preserved": all(r.get("copy_preserved") for r in recs),
              "lines": [e for r in recs for e in r.get("lines") or []],
              "sections": [s for r in recs for s in r.get("sections") or []],
              "codes": [c for c in dict.fromkeys(c for r in recs for c in r.get("codes") or [])],
              "panel_mm": [round(sum(r["panel_mm"][0] for r in recs) + _bp.PANEL_GAP_MM * (len(recs) - 1), 3),
                           max(r["panel_mm"][1] for r in recs)]}
    for key in ("lines_required", "lines_emitted", "characters_supplied", "characters_emitted",
                "characters_not_emitted"):
        joined[key] = sum(r.get(key) or 0 for r in recs)
    for key in ("height_required_mm", "height_available_mm", "overflow_mm", "column_mm"):
        joined[key] = worst.get(key)
    return groups, joined


def _render_motif(language, bounds, role, *, seed=1, density=1.4, name="", swatches=None):
    """Native motif nodes (via the closed design-language engine) inside
    ``bounds`` on the sheet. Deterministic (fixed seed); zero rasters. §BH67: ``swatches`` is the motif's SOURCED
    palette (``_motif_swatches``); without one the language's own defaults print, and the audit refuses them."""
    from apps.ire.design_language import LanguageParameters

    params = (LanguageParameters(density=density, seed=seed) if swatches is None
              else LanguageParameters(density=density, seed=seed, swatches=swatches))
    ident = lambda v: v  # noqa: E731 — bounds are already sheet-space mm
    nodes = language.build(bounds, params, role, ident, ident)
    return Group(name=name or f"motif-{role}", role="decoration",
                 children=nodes) if nodes else None


def _logo_box(backbone: ContainerBackbone, logo_path, lw: float, s: float,
              px, py, logo_master=None):
    """The logo's placed box ``(x, y, w, h)`` in document mm, or None when no
    logo node is emitted.

    ONE definition with TWO readers: the image node further down, and the front
    keep-out that has to know where the mark's bottom edge is BEFORE any text
    is placed. The alternative is the same arithmetic written twice, which is
    how a keep-out and the mark it keeps out of come to disagree about where
    the mark is (§AR2). Returns None on exactly the two conditions that
    suppress the node — no ``logo`` anchor, or an asset whose aspect cannot be
    read — so "no box" and "no logo drawn" cannot come apart.

    [THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    switch the mark to it so gold foil can print." Handed an approved vector master (``logo_master``), the height is
    the MASTER's — its ink bounds' aspect, never its padded viewBox — and the box is the one the raster would get
    otherwise; with none, the asset is read exactly as before.]
    """
    if "logo" not in backbone.anchors:
        return None
    ratio = logo_master.aspect if logo_master is not None else intrinsic_aspect(logo_path)
    if ratio is None:
        return None
    ax, ay = backbone.anchors["logo"]
    span = lw * s * 0.6
    h = span * ratio
    return (px(ax) - span / 2.0, py(ay) - h / 2.0, span, h)


def _fields_keepout_y(keepout_y, box, split_mm, py):
    """[His test day finding 3, 2026-09-30] The front's keep-out when the concept's words set the name in the lower
    field: the split, plus the clear space the mark keeps below itself (the keep-out less the mark's bottom edge),
    when that is lower than the mark's own keep-out; else the mark's keep-out, unchanged."""
    if split_mm is None or keepout_y is None or box is None:
        return keepout_y
    return max(keepout_y, py(split_mm) + (keepout_y - (box[1] + box[3])))


def _front_keepout_y(box, logo_path, logo_master=None):
    """Lowest y at which front ink may begin: the mark's bottom edge plus the
    ruled ``1.0 x cap height`` clear space (§AU3/C2). None when there is no
    mark to keep clear of.

    DERIVED FROM THE BAR, NOT TUNED TO IT (AZ5(d)). A coefficient nudged until
    the assertion went green would pass today and collide the moment the asset,
    the cap ratio or the zone changed — a constant that happens to satisfy a
    measurement is not the same object as the measurement. So the band is
    measured from the asset on every call and multiplied by the owner's ruled
    factor, both of which live in ``container_brand_usage``.

    When the cap band is UNMEASURED the ratio falls back to ``1.0``, treating
    the whole mark as cap band. That is stricter than any real measurement
    because a cap ratio cannot exceed 1.0, so the fallback can never weaken the
    guard (§AL4). On the live asset the branch is NOT taken — ``logo.png``
    measures at ``cap_ratio 0.856667`` — so it is proved by a test that FORCES
    it rather than by this sentence (§AA, and AZ0(k) is what happens when a
    sentence like this is trusted instead).
    """
    if box is None:
        return None
    _x, y, _w, h = box
    # [the owner's second answer of 2026-09-25: an approved vector master's band is measured on the master itself,
    # rasterised (brand_mark.cap_band) — by the same instrument, against its ink height]
    band = _brand_mark.cap_band(logo_master) if logo_master is not None else measure_cap_ratio(logo_path)
    return y + h + clear_space_mm(h, band["cap_ratio"] if band else 1.0)


def _hero_tier_pt(kind: str) -> float:
    """The ruled point size for one direct-print hierarchy tier.

    §BD(a) gave the descriptor its own constant, and the moment there were
    THREE sizes instead of two this had to become a function: the size formula
    had TWO copies in the branch below — one in the keep-out block sizing tier
    0, one in the tier loop — and a three-way conditional written out twice is
    two instruments that can disagree about the same tier. They never did
    disagree while both said "name or support"; the ruling is what makes the
    duplication expensive. Unified here rather than duplicated wider.

    Any kind that is neither the name nor the descriptor is support, at
    ``HERO_SUPPORT_PT``, which §BD(a) expressly did not move.
    """
    if kind == "product_name":
        return HERO_NAME_PT
    if kind == "descriptor":
        return HERO_DESCRIPTOR_PT
    return HERO_SUPPORT_PT


def name_width_estimate_mm(text: str, size_pt: float, *, tracking_em: float = 0.0, upper: bool = False) -> float:
    """The width ``wrap_name`` reads a run as — extracted, not copied, so §BH68(b)'s step test reads every line exactly
    as the wrap does (§BH65(c)8: capitals and tracking included)."""
    est = len(text) * size_pt * _CHAR_ADVANCE_MM_PER_PT * (_CAPS_ADVANCE_FACTOR if upper else 1.0)
    return est + tracking_em * size_pt * _TRACKING_MM_PER_PT * max(len(text) - 1, 0)


#: §BH70(1) — A NAME WIDER THAN ITS FRONT IS REFUSED, NEVER CLIPPED. Both fronts wrap the name inside the front zone
#: and clip their group to it, so a line the wrap cannot break — a single word wider than the zone — was drawn with both
#: its ends cut off: his §BD(b), "A clipped brand name never ships", broken without a word. MEASURED at a9daa5d by this
#: module's own estimate: a 20 mm bottle named "Rosewaterglow" (19.2 mm at 8 pt on a 14.4 mm front) and a 7 mm pencil
#: named "Rose Glow" (5.9 mm on 5.6). The shape step now stops such a design in words before anything is drawn
#: (`targets.container.name_fits_front`); this is the composer's own last word on it, for any name that reaches it
#: another way — at a size or in a style the shape step could not know.
NAME_WIDER_THAN_FRONT = "CONTAINER_NAME_WIDER_THAN_ITS_FRONT"


class NameWiderThanFront(ValueError):
    """A line of the product's name is wider than the front it is printed across, so drawing it would cut it off."""

    def __init__(self, line, line_mm, front_mm, size_pt):
        self.line, self.line_mm, self.front_mm, self.size_pt = line, line_mm, front_mm, size_pt
        super().__init__(
            f"{NAME_WIDER_THAN_FRONT}: the name's line \u201c{line}\u201d needs {line_mm:.1f} mm at {size_pt:g} pt and "
            f"the front is {front_mm:.1f} mm across — drawn, it would be cut off, and a cut-off name never ships "
            "(§BD(b)). Nothing was drawn.")


def refuse_a_clipped_name(lines, size_pt: float, front_mm: float, *, tracking_em: float = 0.0,
                          upper: bool = False) -> None:
    """Raise `NameWiderThanFront` for the first line the front would clip, by the width the wrap itself reads."""
    for line in lines:
        line_mm = name_width_estimate_mm(line, size_pt, tracking_em=tracking_em, upper=upper)
        if line_mm > front_mm:
            raise NameWiderThanFront(line, line_mm, front_mm, size_pt)


#: §BH70(1) — THE SHEET'S OWN WORDS FIT THE PAGE THEY ARE ON. The concept sheet is product-derived — 2.45 x the
#: product's width (VQR-1), under the frozen 3.0 artboard rule — while its title, its reference label, its SKU line
#: and its swatches take their size from the product's HEIGHT (`k`). On a slim tall product the two disagree: MEASURED
#: before this, a pencil 8 mm across drew a 19.6 mm sheet that cut off its own title's first and last letters, both
#: ends of its reference label and its cap swatch, and a mascara's lost its cap swatch — the same arithmetic breaks a
#: 20 x 200 mm tube, a form that was already here. Each of the sheet's words now keeps the size the sheet has always
#: given it wherever it fits, so every sheet that fitted is drawn exactly as before; a word that would run off the page
#: is set smaller by the explicit conversion the front name's fit already uses (mm over mm/pt, §Z1(b) clause (A)), and
#: a swatch that would leave the page takes the next row. None of these is print artwork: the typography record
#: excludes all four by name (`container_motif_fidelity.NON_ARTWORK_TEXT_PREFIXES`), so no print floor reads them.
CHROME_ROOM = 0.92                 # the share of the page's width the sheet's own words may take


def chrome_size_pt(text: str, size_pt: float, room_mm: float) -> float:
    """``size_pt`` where ``text`` fits ``room_mm`` at that size; else the size at which it does (§BH70(1)). Read at the
    capitals' advance, the widest — as the name's wrap is (§BH65(c)8) — so it never passes a word the page then cuts."""
    est_mm = name_width_estimate_mm(text, size_pt, upper=True)
    if est_mm <= room_mm:
        return size_pt
    return size_pt * room_mm / est_mm


def wrap_name(text: str, size_pt: float, max_w_mm: float, *, tracking_em: float = 0.0,
              upper: bool = False) -> list[str]:
    """Break a name that would overrun ``max_w_mm`` into balanced lines.

    §BD(b) — OWNER-RULED: *"The direct-print front wraps long names to two
    lines, as the Decoration branch did ... A clipped brand name never ships."*

    EXTRACTED RATHER THAN COPIED, AND THAT IS THE POINT. This is the Decoration
    branch's own algorithm, lifted verbatim so that the two fronts cannot drift.
    Writing it a second time would have manufactured exactly the defect class
    §BB7 has been about — two instruments measuring one document and
    disagreeing — inside the commit that answers it. "As the Decoration branch
    did" is honoured most exactly by it being the same code.

    THE RULING SAYS "TWO LINES" AND THIS FUNCTION CAN RETURN THREE, WHICH IS
    DISCLOSED RATHER THAN RESOLVED BY THE EXECUTOR. The owner named the
    Decoration branch as the model in the same sentence, and that branch caps
    at three. For the name the owner gave as acceptance evidence the two
    clauses agree: "Rose Nectar Lip Gloss" wraps to exactly TWO. They could
    disagree for a longer name, and if that ever matters it is the owner's to
    settle; nothing here decides it.

    NO NEW LEADING IS INTRODUCED HERE and none may be: §AB3 rules no leading
    this sprint. The caller supplies the step from the constants that already
    exist.
    """
    # §BH65(c)8: a tracked run and a run in capitals are wider than its letters' plain advance — capitals by up to
    # 1.2x (measured, see _CAPS_ADVANCE_FACTOR); the tracking adds its em after every glyph. Without both the
    # estimate would pass a name the front group's clip then eats at both ends — §BD(b)'s defect, again.
    est = name_width_estimate_mm(text, size_pt, tracking_em=tracking_em, upper=upper)
    if est <= max_w_mm:
        return [text]
    words = text.split()
    want = min(3, max(2, round(est / max_w_mm + 0.4)))
    per = -(-len(words) // want)
    return [" ".join(words[i:i + per]) for i in range(0, len(words), per)][:3]


def fitting_name_lines(text: str, size_pt: float, max_w_mm: float, *, tracking_em: float = 0.0,
                       upper: bool = False) -> list[str]:
    """The container front's name lines: `wrap_name`'s balanced split wherever every line fits, else the words filled
    line by line as far as each fits, still at most three lines (§BH70(1), §BD(b)).

    The balanced split can leave a line wider than the front — "Focus Pressed / Powder" did, at 9 pt on a 28.8 mm
    front, and the front's clip cut the first line at both ends. A name that cannot be set either way is returned as
    the balanced split, and the front refuses it by name (`refuse_a_clipped_name`) rather than drawing it cut. Read only
    by the two container fronts, which clip: `wrap_name` itself is unchanged, so the lid's steps (§BH68(b)) and the
    dropper's own break search, which read it too, draw exactly as they did."""
    from apps.ire.text_script import drop_break_separators
    lines = drop_break_separators(wrap_name(text, size_pt, max_w_mm, tracking_em=tracking_em, upper=upper))

    def fits(line):
        return name_width_estimate_mm(line, size_pt, tracking_em=tracking_em, upper=upper) <= max_w_mm
    if all(fits(line) for line in lines):
        return lines
    filled, current = [], ""
    for word in text.split():
        trial = (current + " " + word).strip()
        if current and not fits(trial):
            filled.append(current)
            current = word
        else:
            current = trial
    filled.append(current)
    filled = drop_break_separators(filled)          # [his final goal, C8] a line that breaks drops its separator
    if len(filled) <= 3 and all(fits(line) for line in filled):
        return filled
    return lines


def _native_decoration(backbone: ContainerBackbone, front_zone, name_lines,
                       body_c: Color, s: float, px, py, language=None,
                       hierarchy=None, direct_print=False, keepout_y=None, name_style=None, ink=None,
                       swatches=None, name_font="bold"):
    """Native artwork placed INTO the confirmed front zone (§5/§6-front): a
    soft tinted field, an optional native MOTIF (via the design-language
    engine), a keyline, and the product name as LIVE text. Zero rasters.
    Returns (Group, placements) in zone-normalised (0..1) coordinates.

    2C-2E ``direct_print``: the typography prints straight on the material —
    NO decoration field, NO keyline, no boxed background (a rectangular
    label fallback is a fidelity failure on this path). ``hierarchy`` is an
    ordered list of {"text", "rel", "kind"} live-text tiers replacing the
    uniform name lines."""
    lx, ly, lw, lh = backbone.label_zone
    zx, zy, zw, zh = px(lx), py(ly), lw * s, lh * s
    zid = (front_zone or {}).get("zone_id")
    if direct_print and hierarchy:
        ink = ink or Color.from_hex(_UNSOURCED_INK)          # §BH67: the sourced type ink
        children: list = []
        placements = []
        # a SUPPORTED motif renders in its RESTRAINED direct-print form: the
        # concept's sole graphic element beyond type is a single fine
        # horizontal rule above the product name — never a striped field
        # painted across a typography-first front.
        # §AU2: 0.30 mm below is the OWNER-RULED container front rule,
        # superseding the 0.25 mm that §W4 recorded. 0.25 was never chosen; it
        # was present, and on a direct-printed front a 0.25 mm hairline sits at
        # the edge of where dot gain stops being theoretical. The rationale is
        # ire/container_line_weight.py — which also holds the colour-sheet
        # divider this is NOT, and now records the SUPERSEDED value beside the
        # ruled one so the change is legible rather than silent.
        # EMITTED since §BB7(c): both production call sites supply
        # hierarchy_lines, so this branch is what production draws and the
        # number has reached a proof. This comment read "Still unemitted: no
        # caller supplies hierarchy_lines" until the wiring landed, which was
        # the same overstatement `2d8e4e5` corrected in container_line_weight
        # — true of PRODUCTION callers only, never of callers — and the wiring
        # falsified even the narrow reading.
        # §AY2 step 1 / AZ5(c): the whole front stack drops below the mark's
        # clear space, and the RULE drops with it.
        #
        # ONE SHIFT, SIZED BY THE HIGHEST PIECE OF INK — AND THE FIRST DRAFT
        # GOT THAT WRONG. It sized the shift from the first TEXT tier alone
        # and moved the rule by the same amount, on the reasoning that
        # "shifting the cursor without shifting the rule would fix the worse
        # one and leave the other, so shift is computed once, above both."
        # Moving both is necessary and is NOT sufficient: the two need
        # DIFFERENT shifts and the rule needs the larger one. Measured on the
        # live front zone (zy 66.2200, zh 38.5000, keep-out 77.2674):
        #
        #     tier-0 ink top  76.8030   needs  0.4643
        #     rule  ink top   75.4600   needs  1.8074
        #
        # so a 0.4643 shift left `rule-front-single` 1.3430 mm short and the
        # gate still failed. Which element is highest is not a fact about this
        # layout to be recalled — it depends on `zh` (the rule governs while
        # `zh < 48.09`) and on `size0` (a support-tier hero would flip it), so
        # the code takes the MINIMUM over the ink this branch is about to
        # place and never assumes which one won.
        # §BH66(b), OWNER RULED 2026-09-23 (OWNER_BLOCKER_CLEARANCE.md:23254, LIVE): "THE RULE SITS BELOW THE NAME.
        # §W4 and §AU1 are three days apart and mine; the later governs, and §AU1 is the later. The code has been
        # drawing it above for a month." It was: `rule_y = zy + zh * 0.24` against a name whose baseline sits one
        # millimetre per point below `zy + zh * 0.10` put the rule ABOVE the name on every zone shorter than 48.1 mm
        # and THROUGH its letters up to 64.3 mm — measured 0.12 mm over task 89's capitals, 0.02 mm over task 84's
        # two l's, 1.29 mm over task 52's "Rose". The rule is now placed AFTER the tiers, between the name's ink and
        # the supporting line's (below), and the paragraph above is the record of what the keep-out used to size.
        y_cursor = zy + zh * 0.10
        shift = 0.0
        # `and hierarchy` stood here and could not be false: this entire block
        # is inside `if direct_print and hierarchy:`. A fresh-agent audit found
        # it (AZ0(t)). Removed rather than left as harmless, because a dead
        # condition reads as a REAL second precondition — and "the shift needs
        # hierarchy" is precisely the false sentence that shipped in
        # `02ff1c9`'s message about the OTHER branch, which has no such guard.
        if keepout_y is not None:
            t0 = hierarchy[0]
            # `_pt` SUFFIX, AND IT IS LOAD-BEARING RATHER THAN DECORATIVE.
            # §Z1(a) makes the suffix a declaration and `unit_analysis`
            # enforces it, so the name is what tells the analyser this holds
            # POINTS. It had to be added when the size selection moved into
            # `_hero_tier_pt`: the analyser reads a `_PT`-suffixed CONSTANT as
            # a declaration but not a `_pt`-suffixed FUNCTION, so the call's
            # return read as unknown and the arithmetic below it went with it.
            # Repaired at the producer by naming the value, per the WI-V
            # precedent — never by admitting the finding to the register.
            size0_pt = _hero_tier_pt(
                t0.get("kind", "")) * max(1.0, float(t0.get("rel", 1.0)))
            # y_cursor is a CURSOR here, so its baseline is one drop below it;
            # the ink top is then one cap height above THAT. Shifting the
            # cursor by an ink-top delta would over-shift by size x 0.74812 —
            # 3.3516 mm on this tier, against 1.6863 mm of spare — and fail
            # containment at the zone floor (AZ5(d)).
            #
            # Only tier 0 appears here, and that is a DERIVATION rather than a
            # convenience: tier i+1's ink top is `y_i + step_i*size_i +
            # 0.74812*size_{i+1}` against tier i's `y_i + 0.74812*size_i`, and
            # every step factor (1.9, 1.55) exceeds 0.74812, so the step term
            # alone puts every later tier strictly lower for ANY sizes.
            #
            # §BD(a) AND §BD(b) BOTH TESTED AGAINST THAT DERIVATION RATHER THAN
            # ASSUMED SAFE BY IT, because it is the sentence that licenses
            # sizing the shift off ONE line of ONE tier.
            #   - §BD(a) raises the descriptor 3.2 → 5.0. The derivation is
            #     size-INDEPENDENT — it says "for ANY sizes" and the algebra
            #     carries `size_{i+1}` symbolically — so it survives untouched.
            #   - §BD(b) puts more than one LINE in a tier, which the
            #     derivation did not contemplate at all. Within a tier the
            #     lines share one size and advance by a constant step, so
            #     line j's ink top is `y_i + j*step + 0.74812*size_i`: strictly
            #     increasing in j, and the FIRST line is the tier's highest
            #     ink. So tier 0 line 0 is still the highest text in the stack
            #     and `tops` still names it. That is why the wrap does not move
            #     `rule_y`, and it is a measured invariance, not an oversight.
            # The rule's ink top is `rule_y` itself: `_ink_box` reads a Path's
            # SEGMENTS and does not widen the box by the stroke, so predicting
            # a half-stroke here would predict a gate that does not exist.
            # §BH66(b): the rule is below the name, so tier 0's ink is the stack's highest and the ONLY term — the
            # shift carries no reason that no longer exists. On the 38.5 mm live zone above that is 0.4643 mm, not
            # the 1.8074 mm the rule used to force: the stack sits 1.343 mm higher, still clear of the mark.
            shift = max(0.0, keepout_y - text_ink_top(
                y_cursor + size0_pt * _BASELINE_DROP_MM_PER_PT, size0_pt))
            y_cursor += shift
        name_ink_bottom = support_ink_top = name_gap = None
        for i, tier in enumerate(hierarchy):
            rel = float(tier.get("rel", 1.0))
            kind = tier.get("kind", f"line-{i}")
            # `rel` is the tier's weight relative to its neighbours and is
            # dimensionless, so it may scale a chosen size. What it may not do
            # is scale the ZONE HEIGHT into a point size, which is what
            # `max(9.0, zh * 0.125 * rel)` did. The floor is kept as the floor
            # it always was: below rel 1.0 the literal won at every zone.
            # `size_pt`, not `size`: see the note at `size0_pt` above. The
            # suffix is the declaration that keeps `gap` a MILLIMETRE, and
            # without it `gap / zh` below reads as a reciprocal length and the
            # unit analyser reports a MIXED that is not there.
            size_pt = _hero_tier_pt(kind) * max(1.0, rel)
            gap = size_pt * (_HERO_STEP_MM_PER_PT if rel >= 1.0
                             else _HERO_STEP_TIGHT_MM_PER_PT)
            # §BD(b) — the name wraps rather than clipping. Measured defect it
            # answers: the emitted front carried `ose Nectar Lip Glos`, eaten
            # at BOTH ends by the group's clip, on the same emission where the
            # ruled descriptor arrived intact.
            #
            # ONLY THE NAME TIER WRAPS, AND THAT IS THE RULING'S SCOPE, NOT A
            # SHORTCUT. The owner ruled about the brand name. A descriptor is
            # ruled copy whose characters §BB7(a) fixed, and breaking it across
            # lines is a typographic decision on regulated-adjacent copy that
            # nobody has made.
            style = (name_style or {}) if kind == "product_name" else {}   # §BH65(c)8
            lines = (fitting_name_lines(tier["text"], size_pt, zw * 0.94,
                                        tracking_em=style.get("tracking_em") or 0.0,
                                        upper=style.get("text_case") == "upper")
                     if kind == "product_name" else [tier["text"]])
            if kind == "product_name":
                # §BH70(1): a line this front's clip would cut is refused, never drawn cut (§BD(b))
                refuse_a_clipped_name(lines, size_pt, zw, tracking_em=style.get("tracking_em") or 0.0,
                                      upper=style.get("text_case") == "upper")
            # WITHIN a tier the lines advance by the NAME step, and no new
            # constant is coined for it: §AB3 rules no leading this sprint, and
            # `_NAME_STEP_MM_PER_PT` is already the repo's name-line leading —
            # the very number the Decoration branch steps wrapped name lines
            # by. BETWEEN tiers the tier `gap` still governs, applied once
            # after the last line, so a one-line name lays out exactly as it
            # did before this ruling.
            line_step = size_pt * _NAME_STEP_MM_PER_PT
            if kind == "product_name":
                name_gap = gap
            for j, line in enumerate(lines):
                baseline = y_cursor + size_pt * _BASELINE_DROP_MM_PER_PT
                if kind == "product_name":
                    name_ink_bottom = baseline + size_pt * _INK_MM_PER_PT * _INK_BELOW_EM
                elif name_ink_bottom is not None and support_ink_top is None:
                    support_ink_top = text_ink_top(baseline, size_pt)
                children.append(centered_text(
                    # the hero keeps the canonical product-name node prefix the
                    # fidelity validators key on. A wrapped name takes the
                    # `-0`/`-1` suffix the dropper sheet already uses for the
                    # same job; both spellings satisfy the `startswith`
                    # validators, and an UNWRAPPED name keeps the bare name so
                    # that no existing instrument moves for a name that never
                    # wrapped.
                    (("product-name-hero" if len(lines) == 1
                      else f"product-name-hero-{j}") if kind == "product_name"
                     else f"front-{kind}"), line,
                    zx + zw / 2.0,
                    y_cursor + size_pt * _BASELINE_DROP_MM_PER_PT,
                    size_pt, ink,
                    # §BH67(c)5: the name tier in the concept's own granted face when it names one
                    font=(name_font if kind == "product_name" else "bold") if rel >= 0.9 else "regular"))
                if style:
                    # §BH65(c)8: the concept's own tracking and small-caps words, on the name tier only
                    children[-1].tracking_em = style.get("tracking_em")
                    children[-1].text_case = style.get("text_case")
                # recorded conservatively inside the zone's safe margin (the
                # containment validator enforces 3 mm on a 22×40 zone → stay
                # within [0.15, 0.85] horizontally and clamp vertically)
                nh = round(min(gap / zh, 0.22), 3)
                ny = round(min(max((y_cursor - zy) / zh, 0.12), 0.86 - nh), 3)
                placements.append({
                    "zone_id": zid,
                    "kind": ("product_name" if kind == "product_name"
                             else "support_text"),
                    "nx": 0.15, "ny": ny, "nw": 0.70, "nh": nh,
                    "surface_family": "body"})
                y_cursor += line_step if j + 1 < len(lines) else gap
        if language is not None and name_ink_bottom is not None:
            # §BH66(b): §AU1's own order — "the product name; below it a single fine horizontal rule; below that
            # exactly one supporting line of type". The rule sits midway between the name's ink and the supporting
            # line's; with no supporting line it sits where one would begin, half the name's tier step below it. The
            # tiers do not move for it: the tier step already leaves the room (11.05 mm at the ruled 9 pt over 5 pt).
            rule_y = ((name_ink_bottom + support_ink_top) / 2.0 if support_ink_top is not None
                      else name_ink_bottom + name_gap / 2.0)
            rule_w = zw * 0.5
            children.insert(0, Group(name="motif-front", role="decoration",
                                     children=[Path(
                name="rule-front-single",
                segments=[MoveTo(x=zx + (zw - rule_w) / 2, y=rule_y),
                          LineTo(x=zx + (zw + rule_w) / 2, y=rule_y)],
                stroke=Stroke(color=ink, width_mm=0.30))]))
            # §BB4 — the owner ruled this node IS the DIVIDER element of
            # pc.vqr3_artwork_composition, not a motif. The enclosing group is
            # still named motif-front and that name is not a classification.
            # §BH66(b): the divider's box is recorded WHERE THE RULE IS DRAWN, a 0.04-high box centred on it; the
            # `0.22 + shift / zh` it replaced described a rule above the name that no longer exists.
            placements.insert(0, {"zone_id": zid, "kind": "divider",
                                  "nx": 0.25, "ny": round((rule_y - zy) / zh - 0.02, 3),
                                  "nw": 0.50, "nh": 0.04,
                                  "surface_family": "body"})
        group = Group(name=FRONT_DIRECT_PRINT_GROUP, role="decoration",
                      children=children, clip=rect_clip(zx, zy, zw, zh))
        return group, placements
    children = [
        Rect(name="decoration-field", x=zx, y=zy, w=zw, h=zh, radius_mm=1.5,
             fill=SolidFill(color=_tint(body_c, 0.55))),
    ]
    placements = [{"zone_id": zid, "kind": "field", "nx": 0.0, "ny": 0.0,
                   "nw": 1.0, "nh": 1.0, "surface_family": "body"}]
    # the hero motif — rendered into the field, inside a small inset
    if language is not None:
        inset = min(zw, zh) * 0.08
        motif = _render_motif(language, (zx + inset, zy + inset,
                                         zw - 2 * inset, zh - 2 * inset),
                              "front", seed=1, density=1.6, name="motif-front", swatches=swatches)
        if motif is not None:
            children.append(motif)
            # clipped to the field; recorded conservatively within the zone's
            # safe margin + coverage cap (independent of zone size)
            placements.append({"zone_id": zid, "kind": "motif", "nx": 0.15,
                               "ny": 0.15, "nw": 0.70, "nh": 0.70,
                               "surface_family": "body"})
    children.append(
        Rect(name="decoration-keyline", x=zx, y=zy, w=zw, h=zh, radius_mm=1.5,
             stroke=Stroke(color=_INK, width_mm=0.25)))
    lines = [ln for ln in (name_lines or []) if ln][:3]
    if lines:
        cx, top = zx + zw / 2.0, zy + zh * 0.30
        # VQR-1: the sheet draws at TRUE product scale. The product name
        # never drops below the 8 pt legibility floor (the fidelity gate's
        # PRODUCT_NAME_TOO_SMALL rule) — a long single-line name WRAPS into
        # up to three balanced lines instead of shrinking or clipping.
        size = FRONT_NAME_PT
        if len(lines) == 1:
            # §BD(b): the body of this is now `wrap_name`, shared with the
            # direct-print front. Behaviour here is unchanged — the extraction
            # is byte-for-byte the same arithmetic — and the reason it moved is
            # that the OTHER branch had to have it too.
            lines = fitting_name_lines(lines[0], size, zw * 0.94)
        longest = max(len(ln) for ln in lines)
        if longest * size * _CHAR_ADVANCE_MM_PER_PT > zw * 0.94:
            # a fit-to-width, which is a point size derived from a millimetre
            # width THROUGH the advance — mm / (mm/pt) = pt. §Z1(b) forbids a
            # size scaled off a length by a bare coefficient, not one obtained
            # by an explicit conversion; that distinction is the whole of
            # clause (A). Clamped by the chosen size, so at every zone the
            # repo builds it returns FRONT_NAME_PT and this branch is inert.
            size = max(FRONT_NAME_PT,
                       (zw * 0.94) / (longest * _CHAR_ADVANCE_MM_PER_PT))
        # §BH70(1): a line this front's clip would cut is refused, never drawn cut (§BD(b))
        refuse_a_clipped_name(lines, size, zw)
        # §AY2 step 1 / AZ5(c): drop the stack clear of the mark. Computed
        # HERE, after the fit-to-width, because `size` is not final until then
        # and the clear-space delta is a function of it.
        #
        # `top` is a BASELINE in this branch — line 0's text is placed at
        # `top` directly, not at `top + size * _BASELINE_DROP_MM_PER_PT` — so
        # text_ink_top applies to it as-is. The direct-print branch above needs
        # the drop term because ITS `y_cursor` is a cursor. Two branches, two
        # meanings for a similar-looking variable; conflating them is a 5.99 mm
        # error at 8 pt, and it points the way that looks like clearance.
        shift = 0.0
        if keepout_y is not None:
            shift = max(0.0, keepout_y - text_ink_top(top, size))
            top += shift
        step = max(size * _NAME_STEP_MM_PER_PT, zh * 0.16)
        for i, line in enumerate(lines):
            children.append(centered_text(
                f"product-name-{i}", line, cx, top + i * step, size,
                ink_for(body_c), font="bold"))
        nh = min(0.55, 0.16 * len(lines) + 0.08)
        # 0.20 + shift/zh, NOT (top - zy)/zh — that form is 0.30 unshifted
        # against the 0.20 standing here, a 0.10 move of the recorded box on
        # every native compose. Same reasoning as the motif above.
        placements.append({"zone_id": zid, "kind": "product_name",
                           "nx": 0.15, "ny": round(0.20 + shift / zh, 3),
                           "nw": 0.70, "nh": nh, "surface_family": "body"})
    group = Group(name="Decoration", role="decoration", children=children,
                  clip=rect_clip(zx, zy, zw, zh))
    return group, placements


# --- multi-surface emission (§5-§8) -----------------------------------------

_CAP_SURFACES = ("CAP_FRONT", "CAP_BACK", "CAP_TOP", "CAP_WRAP")
_WRAP_SURFACES = ("BODY_WRAP", "CAP_WRAP")
#: code / exclusion surfaces — carry a code area, NEVER decoration/motif
_CODE_SURFACES = ("CRIMP_ZONE", "NECK", "SHOULDER", "BOTTOM")
_SURFACE_STRIP = (12.0, 200.0, 92.0, 46.0)     # left-lower sheet region (mm)

#: every decoration surface BEYOND the hero is wrapped in a
#: ``Surface-{name}`` group, so the prefix is the emitter's own statement of
#: which surface a node sits on. Named here, not at each reader: a reader that
#: re-derived "the front" from node names would disagree with the emitter the
#: moment the emitter changed, and back-panel copy would be counted as front
#: type. PUBLIC — read by ``container_composition_metrics``.
SURFACE_GROUP_PREFIX = "Surface-"
HERO_SURFACE = "BODY_FRONT"
#: [his goal of 2026-10-10, item 2] the open tray's printed insert, the surface its shade names print on
TRAY_INSERT_SURFACE = "TRAY_INSERT"

#: §W1(a) — the same statement for a surface drawn at FULL SCALE. A
#: ``Surface-*`` group is the strip's DIAGRAM of a surface, at map scale; a
#: ``TrueScaleSurface-*`` group is the surface itself, at its confirmed zone
#: dimensions in document mm. Two prefixes rather than one flag because the
#: difference decides whether a reader may hold a run to a PRINT floor: the
#: strip must not be measured harder (§W1(c), the sprint-7 1.5 pt finding) and
#: the full-scale panel is measured like any other surface (§W1(b)). Neither
#: prefix is a substring of the other, so a reader cannot half-match.
TRUE_SCALE_SURFACE_PREFIX = "TrueScaleSurface-"

#: §BD(c) — the direct-print front's group name, PUBLIC and named here for the
#: same reason ``SURFACE_GROUP_PREFIX`` is: a reader that spells it out itself
#: disagrees with the emitter the moment the emitter changes.
#:
#: THE DEFECT THAT MADE THIS A CONSTANT, measured rather than reasoned about.
#: ``container_production_method._in_artwork`` decides which text runs are
#: measured for the minimum-size floor by testing the name chain against
#: ``("Decoration", "motif-", "Surface-", TRUE_SCALE_SURFACE_PREFIX)``. Before
#: §BB7(c) the front name was emitted into a group literally named
#: ``Decoration`` and WAS measured, at 8.0 pt. The wiring moved it into
#: ``FRONT_DIRECT_PRINT``, which matches none of those four, and the front
#: silently stopped being measured at all — an instrument that was firing went
#: dark, which is the opposite direction from the one §BD(c) anticipated and
#: is why the repair could not wait for its own tranche.
#:
#: The BACK equivalent never had this problem and the asymmetry is the tell:
#: ``BACK_DIRECT_PRINT`` sits inside ``Surface-BODY_BACK``, so it matched on
#: its PARENT's name and its own name was never load-bearing. The front hangs
#: directly off ``Container``, so nothing above it matched either.
FRONT_DIRECT_PRINT_GROUP = "FRONT_DIRECT_PRINT"


def _surface_panels(zones, colors, language, product_name, body_c,
                    back_sections=None, strip_box=None, k=1.0, hero_surface=HERO_SURFACE, batch_code_place=None,
                    info_surface=None):
    """A native artwork panel for every confirmed decoration surface BEYOND
    the front hero (§5/§8): back = readable info role, cap = independent
    name/mark, wrap = reduced motif continuation + seam marker, sides =
    reduced continuation. Returns (Group|None, placements, inventory,
    front_back_relationship)."""
    seen: dict[str, dict] = {}
    for z in zones or []:
        surf = zone_surface(z)
        # §BH66(a): a FACE is its own hero — a compact's lid is drawn once, in plan, and never again as a strip panel
        if surf and surf not in seen and surf != hero_surface:
            seen[surf] = z
    inventory = {hero_surface: "hero"}
    # §BH70(1), item 7 of the list the owner was sent: THE INFORMATION PANEL IS THE SURFACE THE BACK PRINT ZONE IS ON. It
    # was the surface NAMED BODY_BACK, which only a bottle, a tube and the slim forms have — so a compact's base, where
    # its back print zone and its ingredients go, was drawn as a motif continuation. A bottle's back stays its panel.
    info_surfaces = {zone_surface(z) for z in zones or [] if z.get("zone_type") == "BACK_PRINT_ZONE"} | {"BODY_BACK"}
    # [his answer of 2026-10-05, W10] the surface the back copy prints on when there is no back print zone — a jar's
    # wrap label, its back (``back_panel.information_zones``) — is its information panel too
    if info_surface:
        info_surfaces.add(info_surface)
    fb = {"schema_version": "container_front_back_relationship/1.0",
          "front_role": "hero_brand_name_motif", "back_role": None,
          "roles_distinct": True}
    # [His review of 127, 130, 131 and 132, 2026-10-15, C (8): "No empty grey blocks in the files (131's base bottom)"]
    # a surface is drawn as a panel only where it holds what prints on it — the brief's back copy, its code zone's
    # window, a cap's mark, a motif's continuation; a panel that would hold only a placeholder ("INFO · INCI · CODE",
    # "BATCH —") on a tint of the body is not drawn — its surface stays in the inventory, its role said
    def _holds(surf, z):
        if surf in _CODE_SURFACES:
            return bool(batch_code_place) and z.get("zone_type") == "BOTTOM_CODE_ZONE"
        if surf in info_surfaces:
            return bool(back_sections)
        return surf in _CAP_SURFACES or language is not None
    held_back: list = []
    for surf, z in sorted(seen.items()):
        if not _holds(surf, z):
            inventory[surf] = ("code_area" if surf in _CODE_SURFACES else "readable_info" if surf in info_surfaces
                               else "motif_continuation")
            if surf in info_surfaces and surf not in _CODE_SURFACES:
                fb["back_role"] = "readable_info_inci_legal"
            # its surface's group kept, empty — every confirmed surface still has its group (§5) — and nothing drawn
            held_back.append(Group(name=f"{SURFACE_GROUP_PREFIX}{surf}", role="decoration", children=[]))
    seen = {surf: z for surf, z in seen.items() if _holds(surf, z)}
    if not seen:
        return (Group(name="Surfaces", role="decoration", children=held_back) if held_back else None), [], \
            inventory, fb

    sx, sy, sw, sh = strip_box or _SURFACE_STRIP
    k = max(0.5, k)
    cols = min(len(seen), 3)
    rows = (len(seen) + cols - 1) // cols
    pw, ph = sw / cols, sh / max(rows, 1)
    panels: list = []
    placements: list = []
    for i, (surf, z) in enumerate(sorted(seen.items())):
        r, c = divmod(i, cols)
        x, y = sx + c * pw, sy + r * ph
        is_code = surf in _CODE_SURFACES
        fam = "cap" if surf in _CAP_SURFACES else "body"
        inventory[surf] = ("code_area" if is_code
                           else "readable_info" if surf in info_surfaces
                           else "cap_mark" if fam == "cap"
                           else "motif_continuation")
        kids: list = [
            Rect(name=f"panel-{surf}-field", x=x + 1 * k, y=y + 3 * k,
                 w=pw - 2 * k, h=ph - 5 * k, radius_mm=1.0 * k,
                 fill=SolidFill(color=_tint(body_c, 0.6 if surf not in info_surfaces
                                            else 0.8))),
            centered_text(f"panel-{surf}-label", surf.replace("_", " "),
                          x + pw / 2, y + 2 * k, 3.0 * k, _INK, font="bold"),
        ]
        if is_code and batch_code_place and z.get("zone_type") == "BOTTOM_CODE_ZONE":
            # [his rules for cloning a design from a picture, 2026-10-02, rule 5: "replace the placeholders ('INFO · INCI ·
            # CODE', 'BATCH') with the brief's back copy: ... batch code place"] the confirmed code zone drawn as the
            # window it is — kept clear of ink for the filling line's code, in its own proportions — under his words
            zw_, zh_ = float(z.get("width") or 1.0), float(z.get("height") or 1.0)
            ww = min(pw * 0.7, (ph * 0.36) * zw_ / zh_)
            wh = ww * zh_ / zw_
            kids.append(Group(name=f"BOTTOM_TECHNICAL_CODE-{surf}", role="generic", children=[
                Rect(name=f"panel-{surf}-code-window", x=x + (pw - ww) / 2, y=y + ph * 0.30, w=ww, h=wh,
                     stroke=Stroke(color=_ink(colors), width_mm=0.15, dash=(0.6, 0.4))),
                centered_text(f"panel-{surf}-code-place", str(batch_code_place).rstrip("."),
                              x + pw / 2, y + ph * 0.30 + wh + 3.0 * k, 2.4 * k, _ink(colors)),
                centered_text(f"panel-{surf}-code-size", "%g × %g mm" % (round(zw_, 1), round(zh_, 1)),
                              x + pw / 2, y + ph * 0.30 + wh + 6.0 * k, 2.2 * k, _ink(colors))]))
        elif is_code:
            # exclusion surface: a bounded technical code area only, never
            # decoration (2C-2E §6: batch / manufacturing date / expiry)
            code_group = Group(name=f"BOTTOM_TECHNICAL_CODE-{surf}",
                               role="generic", children=[
                centered_text(f"panel-{surf}-code-batch", "BATCH —",
                              x + pw / 2, y + ph * 0.40, 2.4 * k, _ink(colors)),
                centered_text(f"panel-{surf}-code-dates", "MFG — · EXP —",
                              x + pw / 2, y + ph * 0.62, 2.2 * k, _ink(colors))])
            kids.append(code_group)
        elif surf in info_surfaces and back_sections:
            # 2C-2E §12: live-text sections — real product-record copy where
            # verified, a bounded CONTENT_VERIFICATION_REQUIRED marker where
            # not. Never meaningless pseudo-text.
            back_kids: list = []
            back_ink = _ink(colors)       # §BH67: printed copy takes the sourced type ink, never the sheet's own
            ty = y + 5.5 * k
            for si, sec in enumerate(back_sections):
                if ty + 3.0 * k > y + ph - 2:
                    # [his final goal, 2026-10-05, A] the strip depicts what its box holds: a section past its foot is
                    # not drawn to be clipped away (three languages run past it; the true-scale panel carries them all)
                    break
                back_kids.append(TextRun(
                    name=f"back-section-{si}-heading",
                    text=str(sec.get("heading", ""))[:40], x=x + 2 * k, y=ty,
                    size_pt=2.4 * k, color=back_ink, font="bold", align="left"))
                ty += 3.0 * k
                back_kids.append(TextRun(
                    name=f"back-section-{si}-copy",
                    text=str(sec.get("text", ""))[:70], x=x + 2 * k, y=ty,
                    size_pt=2.0 * k, color=back_ink, align="left"))
                ty += 3.6 * k
            kids.append(Group(name="BACK_DIRECT_PRINT", role="decoration",
                              children=back_kids,
                              clip=rect_clip(x + 1, y + 3, pw - 2, ph - 5)))
            fb["back_role"] = "readable_info_inci_legal"
        elif surf in info_surfaces:
            # readability-first: quiet ground + an info placeholder, no motif
            kids.append(centered_text(f"panel-{surf}-info", "INFO · INCI · CODE",
                                      x + pw / 2, y + ph / 2, 2.6, _INK))
            fb["back_role"] = "readable_info_inci_legal"
        elif fam == "cap":
            kids.append(centered_text(
                f"panel-{surf}-mark",
                (product_name.split()[0] if product_name else "MARK").upper(),
                x + pw / 2, y + ph / 2, 3.2, _ink(colors), font="bold"))
        elif language is not None:
            # reduced motif continuation
            motif = _render_motif(language, (x + 2, y + 5, pw - 4, ph - 8),
                                  "side_right", seed=2 + i, density=0.8,
                                  name=f"motif-{surf}", swatches=_motif_swatches(colors))
            if motif is not None:
                kids.append(motif)
                placements.append({"zone_id": z.get("zone_id"), "kind": "motif",
                                   "nx": 0.15, "ny": 0.15, "nw": 0.70, "nh": 0.70,
                                   "surface_family": fam})
        if surf in _WRAP_SURFACES:
            # seam marker at the panel edge (registration reference)
            kids.append(Path(name=f"seam-{surf}", segments=[
                MoveTo(x=x + 1, y=y + 3), LineTo(x=x + 1, y=y + ph - 2)],
                stroke=Stroke(color=_INK, width_mm=0.2)))
        panels.append(Group(name=f"{SURFACE_GROUP_PREFIX}{surf}",
                            role="decoration", children=kids))
    return (Group(name="Surfaces", role="decoration", children=panels + held_back),
            placements, inventory, fb)


# --- §BH65(c)3: THE CONCEPT'S OWN ELEMENTS, WHERE §AU1 LETS THEM PRINT ---------------------------------------------

#: the least height, in mm, a region must offer before a window or a motif band is drawn in it — declared before any
#: case was measured, and never moved to let one through: below it the element is recorded NOT_PLACED, not squeezed
CONCEPT_FRONT_MIN_MM = 8.0
#: the §AU2 container front rule weight, reused for every rule the concept adds (a window's frame, a ring)
_CONCEPT_RULE_MM = 0.30
_CONCEPT_GAP_MM = 3.0
_AU1 = ("§AU1 (C8, OWNER RULED, OWNER_BLOCKER_CLEARANCE.md:5652): 'The decoration element sits above or behind, as it "
        "already does. Nothing else prints on the front.'")


def _ink_extent(group: Group) -> tuple[float, float]:
    """(top, bottom) of the ruled front stack's ink: each run from its cap top to a quarter of its size below the
    baseline, and the divider's own line."""
    tops, bottoms = [], []
    for n in group.children:
        if isinstance(n, TextRun):
            tops.append(n.y - n.size_pt * 0.3528 * 0.75)
            bottoms.append(n.y + n.size_pt * 0.3528 * 0.25)
        elif isinstance(n, Group):
            for leaf in n.children:
                ys = [s.y for s in (getattr(leaf, "segments", ()) or ()) if hasattr(s, "y")]
                tops.extend(ys)
                bottoms.extend(ys)
    return (min(tops) if tops else 0.0), (max(bottoms) if bottoms else 0.0)


def _alternate_outlines(group: Group) -> None:
    """"alternating filled and outline forms": every other FILLED leaf becomes outline-only in its own colour."""
    i = 0
    stack = [group]
    while stack:
        node = stack.pop(0)
        for child in getattr(node, "children", ()):
            if isinstance(child, Group):
                stack.append(child)
            elif isinstance(child, Path) and isinstance(child.fill, SolidFill):
                if i % 2:
                    child.stroke = Stroke(color=child.fill.color, width_mm=0.25)
                    child.fill = None
                i += 1


def draw_ring(x: float, y: float, w: float, h: float, ink: Color, radius_mm: Optional[float] = None) -> Path:
    """A rule tracing a region's edge at the §AU2 front-rule weight. On the container front §AU1 decides whether it
    prints (it does not today: its lower stroke prints below the supporting line); drawn here so a ruling that lets it
    print changes where it is called, not what it is. [the owner's second answer of 2026-09-25: ``radius_mm`` — a
    face's ring traced on the lid's own outline (``_ring_on_the_lid``); none handed in, the corner it always drew]"""
    corner = radius_mm if radius_mm is not None else min(w, h) * 0.08
    return Path(name="frame-ring", segments=_rounded_rect(x, y, w, h, corner),
                stroke=Stroke(color=ink, width_mm=_CONCEPT_RULE_MM))


def _fade_and_glow(plan: dict, motif: Group, box: tuple, kids: list, ink: Optional[Color] = None) -> None:
    """§BH65(c)6: the concept's own fade — the motif fades out from its centre, or down, or up — and its glow, a
    disc under a radial soft mask, drawn BEHIND the motif. §BH67: the shadow prints in the sourced type ink and the
    glow in the face's own colour (``plan["ground_hex"]``) — no concept on record names a colour for either."""
    from apps.ire.graph import OpacityMask
    bx, by, bw, bh = box
    fade = plan.get("fade")
    if fade == "out":
        motif.opacity_mask = OpacityMask(kind="radial", cx=bx + bw / 2.0, cy=by + bh / 2.0,
                                         r=max(bw, bh) * 0.6, start_opacity=1.0, end_opacity=0.12)
    elif fade in ("down", "up"):
        top, bottom = (by, by + bh) if fade == "down" else (by + bh, by)
        motif.opacity_mask = OpacityMask(kind="linear", x1=bx, y1=top, x2=bx, y2=bottom,
                                         start_opacity=1.0, end_opacity=0.12)
    if plan.get("shadow"):
        # §BH65(c)7: the concept's own shadow words — under the concept's motif, in its own ink at a third alpha
        from apps.ire.graph import Shadow
        motif.shadow = Shadow(color=ink or Color.from_hex(_UNSOURCED_INK), opacity=0.3)
    if plan.get("glow"):
        from apps.ire.graph import OpacityMask as _OM
        disc = _rounded_rect(bx + bw * 0.2, by + bh * 0.1, bw * 0.6, bh * 0.8, min(bw, bh) * 0.4)
        kids.insert(kids.index(motif), Group(
            name="concept-glow", role="decoration",
            opacity_mask=_OM(kind="radial", cx=bx + bw / 2.0, cy=by + bh / 2.0, r=max(bw, bh) * 0.45,
                             start_opacity=0.85, end_opacity=0.0),
            children=[Path(name="glow", segments=disc, fill=SolidFill(
                color=Color.from_hex(plan.get("ground_hex") or _UNSOURCED_LIGHT)))]))


def _ellipse_path(x: float, y: float, w: float, h: float) -> list:
    """A closed ellipse filling (x, y, w, h): four cubics at the circle's own control distance."""
    k = 0.5522847498307936
    cx, cy, rx, ry = x + w / 2.0, y + h / 2.0, w / 2.0, h / 2.0
    return [MoveTo(x=cx + rx, y=cy),
            CubicTo(x1=cx + rx, y1=cy + ry * k, x2=cx + rx * k, y2=cy + ry, x=cx, y=cy + ry),
            CubicTo(x1=cx - rx * k, y1=cy + ry, x2=cx - rx, y2=cy + ry * k, x=cx - rx, y=cy),
            CubicTo(x1=cx - rx, y1=cy - ry * k, x2=cx - rx * k, y2=cy - ry, x=cx, y=cy - ry),
            CubicTo(x1=cx + rx * k, y1=cy - ry, x2=cx + rx, y2=cy - ry * k, x=cx + rx, y=cy),
            ClosePath()]


def _hero_units(hero: dict, box: tuple, swatches) -> Group:
    """§BH71 PART 1, ROUTE A: the hero's units drawn into the window ``box`` (x, y, w, h mm) — each with
    ``design_language._petal_path`` at its measured pose (its pointed end, its axis, its length and width as shares of
    the window's width), named ``petal-<i>`` so the motif-fidelity check and the finish reader count them, and filled
    with the colour a record names nearest the one measured (ΔE76 in Lab over the sourced motif palette): no colour
    is invented, and one no record names never prints (§BH67's hard stop). Without a sourced palette the measured
    colour is not used at all — the unsourced stand-in prints, and the printed-colour audit refuses it by name."""
    import math

    from apps.ire.design_language import _petal_path
    x, y, w, hh = box
    named = [sw.hex for sw in swatches.all()] if swatches is not None else []
    ident = lambda v: v  # noqa: E731 — the pose is already sheet-space mm
    kids = []
    for u in hero["units"]:
        ax, ay = x + u["anchor"][0] * w, y + u["anchor"][1] * hh
        path = _petal_path(u["name"], ax, ay, math.radians(u["theta_deg"]), u["length"] * w, u["width"] * w,
                           ident, ident)
        path.fill = SolidFill(color=Color.from_hex(_nearest_named(u["hex"], named)))
        kids.append(path)
    return Group(name="motif-window", role="decoration", children=kids)


def _nearest_named(hex_: str, named: list) -> str:
    """The named colour nearest ``hex_`` by ΔE76 in Lab, or the unsourced stand-in when no colour is named."""
    if not named:
        return _UNSOURCED_LIGHT
    from apps.ire.container_brand_usage import _delta_e_hex
    return min(named, key=lambda h: _delta_e_hex(hex_, h) if _delta_e_hex(hex_, h) is not None else 1e9)


def draw_concept_elements(plan: dict, region: tuple, language, ink: Color, *,
                          fit_width: bool = True, swatches=None) -> tuple[list, list, list]:
    """The concept's window (its interior filled as its colour field says, the motif cut to it, the frame on top), or
    its motif FIELD / EDGE, drawn into ``region`` = (x, y, w, h). Returns (nodes, placements as absolute boxes, the
    names drawn). Where it may print is not decided here. ``fit_width=False`` draws the window to the region exactly:
    a face's layout has already sized it (§BH66(a), ``concept_face``)."""
    from apps.ire.graph import GradientFill, GradientStop
    x, y, w, h = region
    kids, boxes, drawn = [], [], []
    layout = plan.get("layout")
    if layout == "window":
        ww = min(w * 0.62, h * 3.2) if fit_width else w
        wx = x + (w - ww) / 2.0
        # §BH67(d)2: the window in the shape the concept draws — an oval fills its box; a round one is a circle in it
        shape = plan.get("window_shape")
        if shape == "round":
            d = min(ww, h)
            seg = _ellipse_path(wx + (ww - d) / 2.0, y + (h - d) / 2.0, d, d)
        elif shape == "oval":
            seg = _ellipse_path(wx, y, ww, h)
        else:
            seg = _rounded_rect(wx, y, ww, h, h * 0.30)
        fill = plan.get("window_fill") or {}
        if fill.get("kind") == "radial":
            interior = GradientFill(kind="radial", cx=wx + ww / 2.0, cy=y + h / 2.0, r=max(ww, h) * 0.62, stops=[
                GradientStop(offset=0.0, color=Color.from_hex(fill["centre"])),
                GradientStop(offset=1.0, color=Color.from_hex(fill["edge"]))])
        else:
            interior = SolidFill(color=Color.from_hex(fill.get("hex") or plan.get("ground_hex") or _UNSOURCED_LIGHT))
        kids.append(Path(name="window-interior", segments=seg, fill=interior))
        drawn.append("window-interior")
        hero = plan.get("hero") or {}
        if hero.get("units"):
            # §BH71 PART 1: the concept's own hero, MEASURED on its picture (route A) — each unit drawn with the
            # language's own primitive at the pose the picture shows, its colour the nearest a record names
            motif = _hero_units(hero, (wx, y, ww, h), swatches)
            motif.clip = seg
            motif.blend_mode = plan.get("blend")
            kids.append(motif)
            boxes.append(("motif", wx, y, ww, h))
            drawn.append("motif-window")
        elif language is not None:
            inset = min(ww, h) * 0.12
            motif = _render_motif(language, (wx + inset, y + inset, ww - 2 * inset, h - 2 * inset), "front",
                                  seed=1, density=1.0, name="motif-window", swatches=swatches)
            if motif is not None:
                motif.clip = seg
                motif.blend_mode = plan.get("blend")        # §BH65(c)5: the concept's own blend words, or none
                if plan.get("outlines"):
                    _alternate_outlines(motif)
                kids.append(motif)
                _fade_and_glow(plan, motif, (wx + inset, y + inset, ww - 2 * inset, h - 2 * inset), kids, ink)
                boxes.append(("motif", wx + inset, y + inset, ww - 2 * inset, h - 2 * inset))
                drawn.append("motif-window")
        kids.append(Path(name="window-frame", segments=seg, stroke=Stroke(color=ink, width_mm=_CONCEPT_RULE_MM)))
        boxes.append(("window", wx, y, ww, h))
        drawn.append("window-frame")
    elif layout in ("field", "edge") and language is not None:
        bw = w if layout == "field" else w * 0.7
        bh = h if layout == "field" else h * 0.7
        by = y if layout == "field" else y + h - bh
        motif = _render_motif(language, (x, by, bw, bh), "front", seed=1, density=1.0, name=f"motif-{layout}",
                              swatches=swatches)
        if motif is not None:
            motif.clip = rect_clip(x, by, bw, bh)
            motif.blend_mode = plan.get("blend")            # §BH65(c)5
            if plan.get("outlines"):
                _alternate_outlines(motif)
            kids.append(motif)
            _fade_and_glow(plan, motif, (x, by, bw, bh), kids, ink)
            boxes.append(("motif", x, by, bw, bh))
            drawn.append(motif.name)
    return kids, boxes, drawn


def _concept_front(plan: dict, zone: dict, stack: Group, logo_box, logo_path, s: float, px, py,
                   language, *, ink: Optional[Color] = None,
                   swatches=None, logo_master=None) -> tuple[Optional[Group], Optional[Group], list, dict]:
    """§AU1's placement of the concept's own elements on the container front. Returns (a group drawn ABOVE the type
    or None, a group drawn BEHIND it or None, placements, the record). ABOVE: between the confirmed zone's safe
    margin and the mark's 1.0x cap-height clear space (§AY2 — it holds on every side of the mark). BEHIND: only when
    the concept's own words put the motif there, and only below the mark's clear space (§BA: a motif field UNDER
    the mark is a ground, and C12 keeps that red). BELOW the supporting line: never — §AU1. Whatever cannot print is
    recorded with the millimetres and the ruling, and nothing ruled is moved to make room."""
    record = {"drawn": [], "not_placed": []}
    try:
        zx0, zy0 = px(float(zone["x"])), py(float(zone["y"]))
        zw, zh = float(zone["width"]) * s, float(zone["height"]) * s
    except (KeyError, TypeError, ValueError):
        record["not_placed"].append({"element": "all", "reason": "the confirmed zone carries no geometry"})
        return None, None, [], record
    margin = float(zone.get("safe_margin_mm") or 0.0) * s
    zid = zone.get("zone_id")
    ink = ink or Color.from_hex(_UNSOURCED_INK)          # §BH67: the sourced type ink
    type_top, type_bottom = _ink_extent(stack)
    if logo_box is not None:
        lx, ly, lw, lh = logo_box
        # [the owner's second answer of 2026-09-25: the approved vector master's own band, when one is handed in]
        band = _brand_mark.cap_band(logo_master) if logo_master is not None else measure_cap_ratio(logo_path)
        clear = clear_space_mm(lh, band["cap_ratio"] if band else 1.0)
        above_bottom = ly - clear
        behind_top = ly + lh + clear
    else:
        above_bottom = type_top - _CONCEPT_GAP_MM
        behind_top = zy0 + margin
    placements = []

    def place(kind, x, y, w, h):
        placements.append({"zone_id": zid, "kind": kind, "nx": round((x - zx0) / zw, 4),
                           "ny": round((y - zy0) / zh, 4), "nw": round(w / zw, 4), "nh": round(h / zh, 4)})

    if plan.get("ring"):
        record["not_placed"].append({"element": "frame-ring", "reasons": [
            _AU1, "a ring around the zone prints its lower stroke below the supporting line"]})
    above_group = behind_group = None
    layout = plan.get("layout")
    # every region is measured for INK, not for path: a stroked frame paints half its weight OUTSIDE its path, so the
    # region keeps that half-width clear of the safe margin and of the mark's clear space on every edge — otherwise
    # a window sized to the boundary would put 0.15 mm of its frame inside both
    half = _CONCEPT_RULE_MM / 2.0
    if layout:
        above = (zx0 + margin + half, zy0 + margin + half, zw - 2 * (margin + half),
                 (above_bottom - half) - (zy0 + margin + half))
        if above[3] >= CONCEPT_FRONT_MIN_MM:
            kids, boxes, drawn = draw_concept_elements(plan, above, language, ink, swatches=swatches)
            if kids:
                above_group = Group(name="FRONT_CONCEPT", role="decoration",
                                    clip=rect_clip(zx0, zy0, zw, zh), children=kids)
                record["drawn"] += drawn
                record["placed"] = "above the mark's clear space"
                for kind, bx, by, bw, bh in boxes:
                    place(kind, bx, by, bw, bh)
        else:
            reasons = ["above the mark: %.3f mm of ink room between the confirmed zone's safe margin and the mark's "
                       "1.0x cap-height clear space (§AY2), each kept clear of a 0.30 mm rule's half-width — under "
                       "the %.1f mm floor" % (above[3], CONCEPT_FRONT_MIN_MM),
                       "below the supporting line: " + _AU1]
            sx = [sg.x for sg in (stack.clip or ()) if hasattr(sg, "x")]
            sy = [sg.y for sg in (stack.clip or ()) if hasattr(sg, "y")]
            behind_box = ((min(sx) + half, behind_top + half, max(sx) - min(sx) - 2 * half,
                           max(sy) - behind_top - 2 * half) if sx and sy else None)
            if (plan.get("behind") and layout in ("field", "edge") and behind_box
                    and behind_box[3] >= CONCEPT_FRONT_MIN_MM):
                kids, boxes, drawn = draw_concept_elements(plan, behind_box, language, ink, swatches=swatches)
                if kids:
                    behind_group = Group(name="FRONT_CONCEPT_BEHIND", role="decoration",
                                         clip=rect_clip(*behind_box), children=kids)
                    record["drawn"] += drawn
                    record["placed"] = "behind the type, below the mark's clear space"
                    for kind, bx, by, bw, bh in boxes:
                        place(kind, bx, by, bw, bh)
            else:
                reasons.append("behind the type: " + (
                    "a window behind the type would be a panel behind the names" if layout == "window" else
                    "the concept's own words do not put the motif behind the type" if not plan.get("behind") else
                    "the region below the mark's clear space is under the %.1f mm floor" % CONCEPT_FRONT_MIN_MM))
                record["not_placed"].append({"element": layout, "above_mm": round(above[3], 3),
                                             "reasons": reasons})
    return above_group, behind_group, placements, record


def _leaf_box(node) -> Optional[tuple]:
    """(x, y, w, h) of a drawn leaf from its own geometry — every point of a path, a curve's control points included,
    so it can only over-state; a rect's own box; None for anything else."""
    segs = getattr(node, "segments", None)
    if segs:
        xs = [float(getattr(p, a)) for p in segs for a in ("x", "x1", "x2") if hasattr(p, a)]
        ys = [float(getattr(p, a)) for p in segs for a in ("y", "y1", "y2") if hasattr(p, a)]
        if xs and ys:
            return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    if all(hasattr(node, a) for a in ("x", "y", "w", "h")) and getattr(node, "type", "") != "text":
        return (float(node.x), float(node.y), float(node.w), float(node.h))
    return None


def _refuse_behind_mark(group: Group, clear_box) -> list:
    """§BH66(a)'s second limit — "no motif field as a ground behind the mark": every motif leaf whose box meets the
    mark's clear space is taken out of the group, and its name is returned so the record can say what was refused."""
    from apps.ire.concept_face import refuse_behind_mark
    refused: list = []

    def walk(g):
        keep = []
        for child in g.children:
            if isinstance(child, Group):
                walk(child)
                if child.children:
                    keep.append(child)
                continue
            box = _leaf_box(child)
            if box is not None and refuse_behind_mark([(child.name, box)], clear_box):
                refused.append(child.name)
                continue
            keep.append(child)
        g.children = keep

    if clear_box is not None:
        walk(group)
    return refused


#: [the owner's second answer of 2026-09-25] the steps a ray is tried back along its own length when it meets the mark's
#: clear space — 1/400 of it, a quarter of a millimetre on a 100 mm ray; the executor's resolution, not a design value
_TRIM_STEPS = 400


def _trim_rays_at_mark(group: Group, clear_box) -> dict:
    """[the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
    "The lid is missing the concept's rule, ring and radial lines."] §BH66(a)'s second limit — "no motif field as a
    ground behind the mark" — for RAYS. ``_refuse_behind_mark`` takes out a whole leaf whose box meets the mark's clear
    space; a ray from a centre under the mark always does — its box spans the centre's x, inside the clear space's — so
    every upward ray would go whole, and the rays would stop in a hole. Instead each ray (``radial-ray-i``) that meets
    the clear space is SHORTENED back along its own line to the longest length at which neither its box nor its node's
    (``radial-node-i``, moved with it) meets it — the same meeting test, read the same way, on the boxes the
    instruments read; nothing is clipped and nothing is drawn into the clear space. A ray left shorter than its own node
    is no ray, and is removed with it. Returns ``{"trimmed": [...], "removed": [...]}`` by name."""
    from apps.ire.concept_face import refuse_behind_mark
    import re as _re
    out: dict = {"trimmed": [], "removed": []}
    if clear_box is None:
        return out
    leaves = {}
    stack = [group]
    while stack:
        parent = stack.pop()
        for child in parent.children:
            if isinstance(child, Group):
                stack.append(child)
            else:
                leaves[child.name] = (child, parent)
    for name, (ray, parent) in sorted(leaves.items()):
        m = _re.fullmatch(r"radial-ray-(\d+)", name) if name is not None else None
        if m is None:
            continue
        node_entry = leaves.get("radial-node-" + m.group(1))
        node = node_entry[0] if node_entry is not None else None
        x0, y0 = ray.segments[0].x, ray.segments[0].y
        x1, y1 = ray.segments[-1].x, ray.segments[-1].y
        nb = _leaf_box(node) if node is not None else None
        r = nb[2] / 2.0 if nb is not None else 0.0

        def meets(t):
            xt, yt = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
            boxes = [(min(x0, xt), min(y0, yt), abs(xt - x0), abs(yt - y0))]
            if node is not None:
                boxes.append((xt - r, yt - r, 2.0 * r, 2.0 * r))
            return bool(refuse_behind_mark([(name, b) for b in boxes], clear_box))
        if not meets(1.0):
            continue
        t = next((k / _TRIM_STEPS for k in range(_TRIM_STEPS - 1, 0, -1) if not meets(k / _TRIM_STEPS)), 0.0)
        length = t * ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        if t <= 0.0 or length < 2.0 * r:
            parent.children = [c for c in parent.children if c is not ray]
            if node is not None:
                node_entry[1].children = [c for c in node_entry[1].children if c is not node]
            out["removed"].append(name)
            continue
        xt, yt = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        ray.segments = [MoveTo(x=x0, y=y0), CubicTo(x1=x0 + (xt - x0) / 3.0, y1=y0 + (yt - y0) / 3.0,
                                                     x2=x0 + 2.0 * (xt - x0) / 3.0, y2=y0 + 2.0 * (yt - y0) / 3.0,
                                                     x=xt, y=yt)]
        if node is not None:
            dx, dy = xt - x1, yt - y1
            node.segments = [sg.model_copy(update={a: getattr(sg, a) + (dx if a.startswith("x") else dy)
                                                   for a in ("x", "y", "x1", "y1", "x2", "y2") if hasattr(sg, a)})
                             for sg in node.segments]
        out["trimmed"].append(name)
    return out


def _outside_the_oval_lid(set_: dict, ellipse: tuple, *, style: dict, ar_text: Optional[str]) -> list:
    """§BH71 PART 3: each laid-out element's reach past a LEARNED OVAL lid's safe ellipse ``(cx, cy, a, b)`` — the
    lid's own ellipse less its zone's safe margin — as ``[(element, mm)]``, measured along the ray from the centre;
    the elements read as `_outside_the_round_lid` reads them, the circle's own measure left exactly as it was."""
    import math
    cx, cy, a, b = ellipse

    def past(points) -> float:
        worst = -1.0
        for px, py in points:
            dx, dy = px - cx, py - cy
            rho = math.hypot(dx / a, dy / b)
            if rho > 0.0:
                worst = max(worst, math.hypot(dx, dy) * (1.0 - 1.0 / rho))
        return worst
    return _lid_reach(set_, past, style=style, ar_text=ar_text)


def _outside_the_round_lid(set_: dict, circle: tuple, *, style: dict, ar_text: Optional[str]) -> list:
    """§BH71 PART 1: each laid-out element's reach past a ROUND lid's safe circle ``(cx, cy, r)`` — the lid's own
    circle less its zone's safe margin — as ``[(element, mm)]``, the elements that keep inside left out: every line of
    the name and the Arabic line by its own ink box (its width as the wrap reads it), the mark by its own ink box —
    its clear space is kept from every other element by the layout, inside the mark's region (§AY2, §BH68(b)2), and
    the lid's edge is not an element — the window by the oval its box holds, the rule by its two ends. The zone is a
    rectangle and cannot say this: a line inside the zone's box can still leave the circle at its corners."""
    import math

    cx, cy, r = circle

    def past(points) -> float:
        return max(math.hypot(px - cx, py - cy) for px, py in points) - r
    return _lid_reach(set_, past, style=style, ar_text=ar_text)


def _lid_reach(set_: dict, past, *, style: dict, ar_text: Optional[str]) -> list:
    """§BH71: each laid-out element's reach past a lid's safe outline, by ``past`` (points -> mm past it) — every
    line of the name and the Arabic line by its own ink box, the mark by its ink box, the window by the oval its box
    holds, the rule by its two ends — the elements that keep inside left out. [§BH71 PART 3: the round lid's walk,
    moved here unchanged so an oval lid reads the same elements the same way]"""
    import math

    from apps.ire import concept_face as CF
    placed = set_["lay"].get("placed") or {}
    tracking, upper = style.get("tracking_em") or 0.0, style.get("text_case") == "upper"

    def corners(x, y, w, h):
        return ((x, y), (x + w, y), (x, y + h), (x + w, y + h))

    def run(p, text, size_pt, top, h):
        w = name_width_estimate_mm(text, size_pt, tracking_em=tracking, upper=upper)
        x = p["x"] - w / 2.0
        if p["align"] == CF.LEFT:
            x = p["x"]
        elif p["align"] == CF.RIGHT:
            x = p["x"] - w
        return past(corners(x, top, w, h))

    out = []
    if CF.NAME in placed and set_["lines"]:
        p, size_pt = placed[CF.NAME], set_["size_pt"]
        line_h = (CF.INK_ABOVE_EM + CF.INK_BELOW_EM) * size_pt * CF.MM_PER_PT
        out += [(CF.NAME, run(p, line, size_pt, p["ink_top"] + j * size_pt * _NAME_STEP_MM_PER_PT, line_h))
                for j, line in enumerate(set_["lines"])]
    if CF.NAME_AR in placed and ar_text:
        p = placed[CF.NAME_AR]
        out.append((CF.NAME_AR, run(p, ar_text, set_["ar_size_pt"], p["ink_top"], p["ink_bottom"] - p["ink_top"])))
    if CF.SHADE in placed and set_.get("shade"):
        # [his answer of 2026-09-29, (4)] the shade line by its whole ink box: both languages and the em between them
        p, w = placed[CF.SHADE], _shade_width(set_["shade"])
        left = _shade_runs(set_["shade"], p["x"], p["align"])[0][2]
        out.append((CF.SHADE, past(corners(left, p["ink_top"], w, p["ink_bottom"] - p["ink_top"]))))
    if CF.MARK in placed:
        out.append((CF.MARK, past(corners(*placed[CF.MARK]["box"]))))
    if "window" in placed:
        x, y, w, h = placed["window"]
        out.append(("window", past([(x + w / 2.0 * (1.0 + math.cos(t)), y + h / 2.0 * (1.0 + math.sin(t)))
                                    for t in (2.0 * math.pi * i / 72 for i in range(72))])))
    if "rule" in placed:
        x, y, w, h = placed["rule"]
        out.append(("rule", past(((x, y + h / 2.0), (x + w, y + h / 2.0)))))
    return [(element, round(beyond, 3)) for element, beyond in out if beyond > 1e-3]


#: [his answer of 2026-09-29 to the §BH71 report, (4): "the lid drawing draws the shade name my brief asks for"] the
#: shade line's two runs — its English and its Arabic, each its own run, so neither is set inside the other's direction
SHADE_RUN, SHADE_RUN_AR = "product-shade", "product-shade-ar"
#: a shade line the concept's picture gives no line of its own to take its size from is set at this share of the
#: name's size — a step of the scale, never above half the name (the executor's numbers, new)
SHADE_SHARE_OF_NAME = 0.25
SHADE_MOST_OF_NAME = 0.5


def _shade_set(shade: Optional[dict], box: Optional[tuple], name_pt: float) -> Optional[dict]:
    """The record's one shade as a lid sets it — its English and its Arabic as the record holds them, never the
    concept's words; the step of the scale the line is set at: the height of the concept's own shade line where its
    picture shows one (``box``, drawing mm), else ``SHADE_SHARE_OF_NAME`` of the name — never above
    ``SHADE_MOST_OF_NAME`` of the name, never under the scale's smallest step; one em of that size between the two
    languages. None where the record holds no shade."""
    from apps.ire import concept_face as CF
    if not shade or not (shade.get("en") or shade.get("ar")):
        return None
    if box is not None:
        want, place = box[3] / ((CF.INK_ABOVE_EM + CF.INK_BELOW_EM) * CF.MM_PER_PT), "the concept's own shade line"
    else:
        want, place = name_pt * SHADE_SHARE_OF_NAME, "the face's foot"
    size = max(TYPE_SCALE_PT[0], min(scale_step_at_most(want), scale_step_at_most(name_pt * SHADE_MOST_OF_NAME)))
    return {"en": shade.get("en") or "", "ar": shade.get("ar") or "", "size_pt": size, "place": place,
            "gap_mm": round(size * CF.MM_PER_PT, 3)}


def _shade_runs(shade_set: dict, x: float, align: str) -> list:
    """The shade line's runs as ``[(run name, text, left x, width)]`` — its English and its Arabic side by side, one
    em of its size between them, the pair placed at ``x`` as the line's own alignment says; each run's width the
    wrap's own estimate, the one every other line of the lid is measured by."""
    from apps.ire import concept_face as CF
    parts = [(n, t) for n, t in ((SHADE_RUN, shade_set["en"]), (SHADE_RUN_AR, shade_set["ar"])) if t]
    widths = [name_width_estimate_mm(t, shade_set["size_pt"]) for _n, t in parts]
    total = sum(widths) + shade_set["gap_mm"] * (len(parts) - 1)
    left = x - total / 2.0
    if align == CF.LEFT:
        left = x
    elif align == CF.RIGHT:
        left = x - total
    runs = []
    for (name, text), w in zip(parts, widths):
        runs.append((name, text, left, w))
        left += w + shade_set["gap_mm"]
    return runs


def _shade_width(shade_set: dict) -> float:
    """The shade line's whole width: its runs and the em between them."""
    runs = _shade_runs(shade_set, 0.0, "left")
    return runs[-1][2] + runs[-1][3] - runs[0][2]


def _lid_step_refusals(set_: dict, *, style: dict, ar_text: Optional[str]) -> list:
    """§BH68(b): what keeps the lid's zone from holding the concept's layout with the name at ``set_["size_pt"]`` —
    each as ``{kind, key, amount, reason}`` (never ``text``: a dict carrying ``kind`` and
    ``text`` is a brand-copy tier to tools/brand_strings.py); [] when nothing does. Every line of the name and the Arabic line inside the
    text width, as the wrap reads them; nothing the concept places left unplaced; nothing colliding once the face follows
    the concept's layout; every element inside its region (§BH68(b)2); no element the concept sizes squeezed to make
    room — the window keeps the concept's height
    where the vision step read it, and its designed width (``concept_face.WINDOW_WIDTH_SHARE`` of the text region) where
    it did not. Elements may MOVE, the least distance, recorded, as the follow pass always moves them; the line count is
    the wrap's own (``wrap_name`` discloses its two-or-three question rather than deciding it, and so does this)."""
    from apps.ire import concept_face as CF
    size_pt, text_w, lay, follow = set_["size_pt"], set_["text_w"], set_["lay"], set_["follow"]
    out = []
    tracking, upper = style.get("tracking_em") or 0.0, style.get("text_case") == "upper"
    over = [(name_width_estimate_mm(line, size_pt, tracking_em=tracking, upper=upper) - text_w, line)
            for line in set_["lines"]]
    worst = max(over, default=(0.0, ""))
    if worst[0] > 1e-6:
        out.append({"kind": "width", "key": "name", "amount": worst[0],
                    "reason": "the name's line %r runs %.2f mm past the %.2f mm text width" % (worst[1], worst[0],
                                                                                            text_w)})
    if ar_text:
        past = name_width_estimate_mm(ar_text, set_["ar_size_pt"]) - text_w
        if past > 1e-6:
            out.append({"kind": "width", "key": "name_ar", "amount": past,
                        "reason": "the Arabic line runs %.2f mm past the %.2f mm text width" % (past, text_w)})
    if set_.get("shade"):
        past = _shade_width(set_["shade"]) - text_w          # [his answer of 2026-09-29, (4)] the shade line too
        if past > 1e-6:
            out.append({"kind": "width", "key": "shade", "amount": past,
                        "reason": "the shade line runs %.2f mm past the %.2f mm text width" % (past, text_w)})
    for gone in lay.get("not_placed") or []:
        out.append({"kind": "unplaced", "key": gone["element"], "amount": 0.0,
                    "reason": "the %s cannot be placed — %s" % (gone["element"], gone["reason"])})
    for hit in lay.get("collisions") or []:
        out.append({"kind": "collision", "key": tuple(sorted(hit["elements"])), "amount": hit["overlap_mm"],
                    "reason": "%s collide by %.3f mm — %s" % (" and ".join(hit["elements"]), hit["overlap_mm"],
                                                            hit["reason"])})
    for move in follow.get("moves") or []:
        if move["element"] == "window" and "concept_height_mm" in move:
            out.append({"kind": "squeeze", "key": "window", "amount": move["concept_height_mm"] - move["height_mm"],
                        "reason": "the window is squeezed from the concept's %.3f mm to %.3f mm"
                                % (move["concept_height_mm"], move["height_mm"])})
    # §BH68(b)2: EVERY ELEMENT INSIDE ITS REGION — the mark's clear space inside the mark's region, the type's ink and the
    # window and motif inside the text region. The follow pass, left no room, places an element OUTSIDE its region
    # without any overlap, so no collision records it: measured on task 110 (§BH68(f)), 72 pt pushed the mark 19.8 mm
    # above the lid face and the Arabic line past its foot, and nothing refused the step.
    # [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
    # "The lid is missing the concept's rule, ring and radial lines." The MOTIF is not type. The one-em GAP a ring keeps
    # is the type's (``concept_face``: "one em of the name's size between stacked elements, and between the type and the
    # ring"), so the motif region is held to the ring's INSIDE — the mark's region — the ring framing the whole face.
    # Measured on task 110 with its rim rule drawn: held one em inside the ring, the name fell from 48 to 12 pt ("the
    # motif_region leaves its region by 12.11 mm"); held to the ring's inside, 36 pt is the largest step the lid holds.
    # The GAP itself is not touched. With no ring the two regions are one region, and nothing here moves.]
    regions = lay.get("regions") or {}
    for element, place_ in (lay.get("placed") or {}).items():
        region = regions.get("mark" if element in (CF.MARK, "motif_region") else "text")
        if not region:
            continue
        rx, ry, rw, rh = region
        if element == CF.MARK:
            x, y, w, h = place_["clear_box"]
        elif isinstance(place_, dict):
            x, y, w, h = rx, place_["ink_top"], 0.0, place_["ink_bottom"] - place_["ink_top"]  # its width: the check above
        else:
            x, y, w, h = place_
        beyond = max(ry - y, (y + h) - (ry + rh), rx - x, (x + w) - (rx + rw), 0.0)
        if beyond > 1e-3:
            out.append({"kind": "outside", "key": element, "amount": beyond,
                        "reason": "the %s leaves its region by %.2f mm" % (element, beyond)})
    followed = {f["element"] for f in follow.get("followed") or []}
    window = (lay.get("placed") or {}).get("window")
    if window and "window" not in followed:
        designed = lay["regions"]["text"][2] * CF.WINDOW_WIDTH_SHARE
        if window[2] < designed - 1e-3:
            out.append({"kind": "narrow", "key": "window", "amount": designed - window[2],
                        "reason": "the window narrows from its designed %.3f mm to %.3f mm" % (designed, window[2])})
    # §BH71 PART 1: ON A ROUND LID, EVERY ELEMENT INSIDE ITS CIRCLE (`_outside_the_round_lid`) — a step that leaves one
    # outside is refused as a step that leaves one outside its region is
    if set_.get("round_lid") is not None:
        for element, beyond in _outside_the_round_lid(set_, set_["round_lid"], style=style, ar_text=ar_text):
            out.append({"kind": "round", "key": element, "amount": beyond,
                        "reason": "the %s leaves the round lid by %.2f mm" % (element, beyond)})
    if set_.get("oval_lid") is not None:          # [§BH71 PART 3: on a learned oval lid, inside its ellipse]
        for element, beyond in _outside_the_oval_lid(set_, set_["oval_lid"], style=style, ar_text=ar_text):
            out.append({"kind": "oval", "key": element, "amount": beyond,
                        "reason": "the %s leaves the oval lid by %.2f mm" % (element, beyond)})
    return out


def _lid_name_step(set_at, *, style: dict, ar_text: Optional[str]) -> tuple:
    """§BH68(b): the largest step of TYPE_SCALE_PT the lid holds for the concept's layout, tried from the top — the
    chosen set and its record, with each larger step and why it did not hold. A step holds when it makes nothing worse
    than the smallest step does: what the concept's layout breaks on this lid at EVERY size is not the name's doing,
    and is recorded as such (``at_every_step``) rather than refusing every step. Only the steps at or above the
    name's own floor are tried: the fidelity instrument refuses a name below it (``container_fidelity._MIN_NAME_PT``,
    8.0 pt), so 6 and 7 pt are never the lid's name."""
    from apps.ire.container_fidelity import _MIN_NAME_PT
    steps = [step for step in TYPE_SCALE_PT if step >= _MIN_NAME_PT]
    smallest = set_at(steps[0])
    always = _lid_step_refusals(smallest, style=style, ar_text=ar_text)

    def worse(r):
        return not any(a["kind"] == r["kind"] and a["key"] == r["key"] and r["amount"] <= a["amount"] + 1e-6
                       for a in always)
    refused = []
    for step in sorted(steps, reverse=True):
        set_ = smallest if step == steps[0] else set_at(step)
        why = [r["reason"] for r in _lid_step_refusals(set_, style=style, ar_text=ar_text) if worse(r)]
        if not why:
            return set_, {"governed_by": "§BH68(b)", "scale_pt": list(TYPE_SCALE_PT), "floor_pt": _MIN_NAME_PT,
                          "step_pt": step,
                          "ar_step_pt": set_["ar_size_pt"], "larger_steps_refused": refused,
                          "at_every_step": [a["reason"] for a in always],
                          "why": "the largest step of the typographic scale the lid's own zone holds for the "
                                 "concept's layout"}
        refused.append({"step_pt": step, "why": why})
    raise AssertionError("unreachable: the smallest step makes nothing worse than itself")


#: [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
#: "The lid is missing the concept's rule, ring and radial lines."] the concept's rule on a face — named so the finish
#: reader's own suffix (``container_finishes.DIVIDER``) lands its foil on it, and so no instrument that reads a node
#: beginning ``rule-`` (the ruled field's geometry, the concept sheet's hero rule) counts it as theirs
FACE_RULE = "face-rule-front-single"


def _line_ink(colors: Optional[dict], key: str) -> Color:
    """[the owner's second answer of 2026-09-25] The colour a face's own line prints in — ``colors[key]``, sourced by the
    caller (``colour_sources.line_colour``: the concept's words, else the brand's fine-detail swatch) — else the
    unsourced stand-in the printed-colour audit refuses by name. Never the type ink by accident."""
    hx = colors.get(key) if colors is not None else None
    return Color.from_hex(hx if hx is not None else _UNSOURCED_INK)


def _ring_on_the_lid(ring: tuple, surface: Optional[tuple], surface_radius: Optional[float],
                     vision: Optional[dict]) -> tuple:
    """[the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
    "The lid is missing the concept's rule, ring and radial lines."] The ring's corner, and the record of its shape.
    §BH67(c)3, OWNER RULED 2026-09-24: "the ring runs round the lid as the concept draws it". The ring is traced on
    the LID'S OWN OUTLINE: its corner is the outline's corner less the ring's inset from it, its path where
    ``concept_face.layout`` puts it — one stroke inside the safe line. A concept that draws its ring in another shape
    than the lid's (task 110: the vision read's ring is "round"; this lid is a rounded rectangle) is drawn on the lid's
    outline and SAYS SO — SUBSTITUTED, by name: the least move from the concept's shape that keeps the ring round the
    lid, the only shape that does (§BH67(d)2: "the element is moved the least distance that satisfies it, recorded by
    name"). And the safe margin holds where the concept draws its ring nearer the edge: both
    distances are recorded. Returns (the corner in mm — None for the corner ``draw_ring`` always drew — and the record)."""
    read = vision is not None and vision.get("state") == "READ"
    elements = vision.get("elements") if read else None
    seen = next((e for e in elements if e.get("kind") == "ring"), None) if elements is not None else None
    concept_shape = seen.get("shape") if seen is not None else None
    if surface is None or surface_radius is None:
        return None, {"state": "NO_OUTLINE", "concept_shape": concept_shape,
                      "reason": "the lid's outline carries no corner to trace; the ring keeps the corner it always drew"}
    rx, ry, rw, rh = ring
    sx, sy, sw, sh = surface
    inset = min(rx - sx, ry - sy, (sx + sw) - (rx + rw), (sy + sh) - (ry + rh))
    lid_shape = "round" if abs(sw - sh) < 1e-6 and 2.0 * surface_radius >= sw - 1e-6 else "rounded_rect"
    record = {"state": ("SUBSTITUTED" if concept_shape is not None and concept_shape != lid_shape else
                        "THE_LID_OUTLINE"),
              "concept_shape": concept_shape, "drawn_shape": lid_shape,
              "corner_mm": round(max(0.0, surface_radius - inset), 3), "lid_corner_mm": round(surface_radius, 3),
              "path_inset_mm": round(inset, 3), "ink_inset_mm": round(inset - _CONCEPT_RULE_MM / 2.0, 3)}
    if seen is not None and concept_shape is not None:
        x0, y0, x1, y1 = seen["box"]
        record["concept_inset_mm"] = round(min(x0 * sw, y0 * sh, (1.0 - x1) * sw, (1.0 - y1) * sh), 3)
    record["reason"] = (
        "the concept's ring is %s and this lid is a %s %.1f x %.1f mm: the ring is traced on the lid's own outline, "
        "corner %.2f mm (the lid's %.2f less its %.2f mm inset) — the least move from the concept's shape that keeps "
        "it round the lid (§BH67(c)3; the least move, recorded by name, §BH67(d)2)" % (concept_shape, lid_shape.replace("_", " "), sw, sh, record["corner_mm"],
                                           surface_radius, inset)
        if record["state"] == "SUBSTITUTED" else
        "the ring is traced on the lid's own outline, corner %.2f mm (the lid's %.2f less its %.2f mm inset)"
        % (record["corner_mm"], surface_radius, inset))
    if "concept_inset_mm" in record:
        record["reason"] += ("; its ink %.2f mm inside the lid's edge, where the concept draws it %.2f mm in — the "
                             "safe margin holds" % (record["ink_inset_mm"], record["concept_inset_mm"]))
    return record["corner_mm"], record


def _concept_face(plan: dict, zone: dict, s: float, px, py, language, logo_path, product_name: str,
                  composer_mark_w: float, descriptor: Optional[str], *, ink: Optional[Color] = None,
                  swatches=None, surface: Optional[tuple] = None, rule_ink: Optional[Color] = None,
                  ring_ink: Optional[Color] = None, surface_radius: Optional[float] = None,
                  logo_master=None, surface_shape: Optional[str] = None) -> tuple:
    """§BH66(a) — THE FACE AS THE CONCEPT ARRANGES IT. OWNER RULED 2026-09-23 (``OWNER_BLOCKER_CLEARANCE.md:23254``,
    LIVE): on a surface that is its product's face "the concept's own arrangement governs, inside two limits that
    stand: the mark's clear space on every side (§AY2), and no motif field as a ground behind the mark (§BA / C12).
    Draw the window, the ring, the Arabic line and their finishes where the concept puts them, and refuse by name only
    what those two limits actually forbid."

    ``plan["face"]`` is ``concept_face.read``'s reading of the concept's own words, made by the caller with the
    product's Arabic name. This lays it into the confirmed zone less its safe margin (``concept_face.layout``) and
    draws exactly that: the window or motif region and the ring BEHIND the type, the name and the Arabic line in the
    direct-print group the instruments already measure, and the mark's box for the caller to place the lockup in.
    Returns (the concept group or None, the type group, the mark's box or None, placements, the record)."""
    from apps.ire import concept_face as CF
    face = plan["face"]
    record = {"schema_version": CF.SCHEMA, "governed_by": CF.GOVERNED_BY, "surface": face.get("surface"),
              "reading": {k: face.get(k) for k in ("state", "layout", "region", "elements", "order",
                                                    "approximated")},
              "name_ar_source": face.get("name_ar_source"), "drawn": [], "refused": [], "not_in_arrangement": []}
    try:
        zx0, zy0 = px(float(zone["x"])), py(float(zone["y"]))
        zw, zh = float(zone["width"]) * s, float(zone["height"]) * s
    except (KeyError, TypeError, ValueError):
        record["not_placed"] = [{"element": "all", "reason": "the confirmed zone carries no geometry"}]
        return None, None, None, [], record
    margin = float(zone.get("safe_margin_mm") or 0.0) * s
    zid = zone.get("zone_id")
    ink = ink or Color.from_hex(_UNSOURCED_INK)          # §BH67: the sourced type ink
    style = plan.get("name_style") or {}
    # §BH67(b)2: the name the concept sets as its display wordmark — the record's own leading phrase, word for word
    # (``display_name.read``) — where the concept quotes one; the record's whole name otherwise. The rest of the
    # record's name stays on the record and off the face, said by name.
    display = face.get("display_name") or {}
    if (display.get("name") or {}).get("source") == "CONCEPT_DISPLAY_NAME":
        product_name = display["name"]["text"]
    record["display_name"] = {k: display.get(k) for k in ("name", "name_ar", "off_the_face", "refused")} or None
    if (plan.get("hero") or {}).get("units"):
        # §BH71 PART 1: the concept's own hero, measured on its picture (route A) — its units, and which of them the
        # picture shows lit like metal, on the face's record for the finishes to read
        record["hero"] = {"units": [u["name"] for u in plan["hero"]["units"]],
                          "metal_units": list(plan["hero"]["metal_units"])}
    box = (zx0 + margin, zy0 + margin, zw - 2 * margin, zh - 2 * margin)
    # §BH71 PART 1: a ROUND lid (`silhouettes._compact` draws its outline a circle) keeps its print inside the circle,
    # not only inside its zone's box — the lid's own circle, read off the outline the backbone draws, less the zone's
    # safe margin; None on every other lid
    round_lid = None
    if surface is not None and surface_radius is not None and abs(surface[2] - surface[3]) < 1e-6 \
            and 2.0 * surface_radius >= surface[2] - 1e-6:
        round_lid = (surface[0] + surface[2] / 2.0, surface[1] + surface[3] / 2.0, surface_radius - margin)
    # §BH71 PART 3: a LEARNED OVAL lid (`silhouettes._ellipse`) keeps its print inside its ellipse, less the margin
    oval_lid = None
    if surface is not None and surface_shape == "oval":
        oval_lid = (surface[0] + surface[2] / 2.0, surface[1] + surface[3] / 2.0, surface[2] / 2.0 - margin,
                    surface[3] / 2.0 - margin)
    ring_mm = _CONCEPT_RULE_MM if plan.get("ring") else None
    # [the owner's second answer of 2026-09-25: "The lid is missing the concept's rule, ring and radial lines."] the
    # concept's own rule (``concept_front.lines``), at the §AU2 front-rule weight every rule the concept adds takes
    rule_mm = _CONCEPT_RULE_MM if plan.get("rule") else None
    ar_text = face.get("name_ar") or None
    if (display.get("name_ar") or {}).get("source") == "CONCEPT_DISPLAY_NAME":
        ar_text = display["name_ar"]["text"]           # §BH67(b)2: the Arabic wordmark, the record's own leading words
    ar_scale = float(((face.get("elements") or {}).get(CF.NAME_AR) or {}).get("scale") or 1.0)
    # [his answer of 2026-09-29 to the §BH71 report, (4)] the record's one shade — its words the record's; its place
    # and its size the concept's own shade line where the picture shows one
    shade = face.get("shade") if CF.SHADE in (face.get("elements") or {}) else None
    shade_box = CF.shade_line_box(face.get("vision_layout"), surface or (zx0, zy0, zw, zh)) if shade else None
    if logo_master is not None:
        # [the owner's second answer of 2026-09-25: the mark's aspect and band are the approved vector master's —
        # its ink bounds and its own outlines rasterised — when one is handed in]
        aspect, band = logo_master.aspect, _brand_mark.cap_band(logo_master)
    else:
        aspect = intrinsic_aspect(logo_path) if logo_path else None
        band = measure_cap_ratio(logo_path) if aspect else None
    # §BH67(d)2: the window's shape from the concept's PICTURE where its words give none — the vision read's own
    vision = face.get("vision_layout") or {}
    if not plan.get("window_shape") and vision.get("state") == "READ":
        seen = next((e.get("shape") for e in vision.get("elements") or [] if e.get("kind") == "window"), None)
        if seen in ("oval", "round"):
            plan = dict(plan, window_shape=seen, why=dict(plan.get("why") or {},
                                                          window_shape=["the vision read of the concept: %s" % seen]))

    def set_at(size_pt):
        """The face laid out with the name at ``size_pt``, the Arabic line at its own step, and followed to the
        concept's layout (§BH67(d)2: the vision step's read moves each element it read to where the concept puts it on
        the real surface; every rule wins by the least move, recorded by name; an element it could not read keeps its
        fixed slot, and says so)."""
        text_w = box[2] - (2 * (_CONCEPT_RULE_MM + size_pt * CF.MM_PER_PT * CF.GAP_EM) if ring_mm else 0.0)
        lines = (wrap_name(product_name, size_pt, text_w, tracking_em=style.get("tracking_em") or 0.0,
                           upper=style.get("text_case") == "upper") if product_name else [])
        ar_size_pt = scale_step_at_most(size_pt * ar_scale)       # the Arabic line is a step too, never above the name
        shade_set = _shade_set(shade, shade_box, size_pt)
        lay = CF.layout(face, box=box, ring_mm=ring_mm, name_lines=lines, name_size_pt=size_pt,
                        name_step_mm=size_pt * _NAME_STEP_MM_PER_PT, ar_text=ar_text, ar_size_pt=ar_size_pt,
                        mark_aspect=aspect, mark_cap_ratio=(band["cap_ratio"] if band else 1.0),
                        composer_mark_w=composer_mark_w,
                        shade_size_pt=(shade_set["size_pt"] if shade_set else None),
                        shade_has_arabic=bool(shade_set and shade_set["ar"]))
        follow = CF.follow_concept_layout(
            lay, face.get("vision_layout"), zone=(surface or (zx0, zy0, zw, zh)), mark_aspect=aspect,
            mark_cap_ratio=(band["cap_ratio"] if band else 1.0), measured=face.get("measured"))   # §BH71
        if rule_mm is not None:
            # [the owner's second answer of 2026-09-25] the rule between the name and the Arabic line, placed once the
            # stack is followed — inside the step's own layout, so every check a step answers to reads it too
            CF.place_rule(lay, rule_mm=rule_mm,
                          concept=CF.concept_box(face.get("vision_layout"), "rule", surface or (zx0, zy0, zw, zh)))
        return {"size_pt": size_pt, "text_w": text_w, "lines": lines, "ar_size_pt": ar_size_pt, "lay": lay,
                "follow": follow, "round_lid": round_lid, "oval_lid": oval_lid, "shade": shade_set}

    # §BH68(b): THE LARGEST STEP OF THE SCALE THE LID'S OWN ZONE HOLDS FOR THE CONCEPT'S LAYOUT, tried from the top
    set_, record["name_size"] = _lid_name_step(set_at, style=style, ar_text=ar_text)
    size_pt, lines, ar_size_pt, lay = set_["size_pt"], set_["lines"], set_["ar_size_pt"], set_["lay"]
    record["concept_layout"] = set_["follow"]
    record.update({k: lay[k] for k in ("box", "ring", "regions", "gap_mm", "placed", "not_placed", "collisions",
                                       "rules")})
    if round_lid is not None:
        # §BH71 PART 1: the round lid's safe circle, and what leaves it at the step chosen — only what leaves it at every
        # step, where the concept's own arrangement puts it; the containment report reads it by name
        record["round_lid"] = {"circle_mm": [round(v, 3) for v in round_lid], "outside": [
            {"element": e, "beyond_mm": b} for e, b in _outside_the_round_lid(set_, round_lid, style=style,
                                                                             ar_text=ar_text)]}
    if oval_lid is not None:
        # §BH71 PART 3: the oval lid's safe ellipse, and what leaves it at the step chosen
        record["oval_lid"] = {"ellipse_mm": [round(v, 3) for v in oval_lid], "outside": [
            {"element": e, "beyond_mm": b} for e, b in _outside_the_oval_lid(set_, oval_lid, style=style,
                                                                            ar_text=ar_text)]}
    placements: list = []

    def place(kind, x, y, w, h):
        # recorded INSIDE the drawn box, never beyond it: the start rounds up and the end rounds down at the record's
        # four decimals, so an element laid exactly on the safe-margin line is never recorded across it
        import math
        nx0, ny0 = math.ceil((x - zx0) / zw * 1e4) / 1e4, math.ceil((y - zy0) / zh * 1e4) / 1e4
        nx1, ny1 = math.floor((x + w - zx0) / zw * 1e4) / 1e4, math.floor((y + h - zy0) / zh * 1e4) / 1e4
        placements.append({"zone_id": zid, "kind": kind, "nx": nx0, "ny": ny0, "nw": round(nx1 - nx0, 4),
                           "nh": round(ny1 - ny0, 4)})

    placed = lay["placed"]
    mark_box = tuple(placed[CF.MARK]["box"]) if CF.MARK in placed else None
    clear_box = tuple(placed[CF.MARK]["clear_box"]) if CF.MARK in placed else None
    concept_kids: list = []
    if "window" in placed:
        kids, boxes, drawn = draw_concept_elements(plan, tuple(placed["window"]), language, ink, fit_width=False,
                                                   swatches=swatches)
        concept_kids += kids
        record["drawn"] += drawn
        for kind, bx, by, bw, bh in boxes:
            place(kind, bx, by, bw, bh)
    elif "motif_region" in placed and language is not None:
        kids, boxes, drawn = draw_concept_elements(dict(plan, layout="field"), tuple(placed["motif_region"]),
                                                   language, ink, swatches=swatches)
        for kid in kids:
            if isinstance(kid, Group):
                # [the owner's second answer of 2026-09-25] a radial motif's rays are shortened at the mark's clear
                # space before the whole-leaf refusal reads the group, so none is refused whole and none enters it
                trim = _trim_rays_at_mark(kid, clear_box)
                if trim["trimmed"] or trim["removed"]:
                    record.setdefault("trimmed", []).append({
                        "limit": "no motif field as a ground behind the mark (§BH66(a); §BA / C12)",
                        "count": len(trim["trimmed"]), "elements": trim["trimmed"][:24],
                        "removed": trim["removed"][:24], "removed_count": len(trim["removed"]),
                        "how": "shortened back along its own line until neither its box nor its node's meets the "
                               "mark's clear space, its node moved with it — never drawn into it, never refused whole; "
                               "a ray left shorter than its node is removed with it"})
                refused = _refuse_behind_mark(kid, clear_box)
                if refused:
                    record["refused"].append({
                        "limit": "no motif field as a ground behind the mark (§BH66(a); §BA / C12)",
                        "count": len(refused), "elements": refused[:24],
                        "how": "refused WHOLE: the brand-usage instrument reads each element's own box, never a "
                               "clip, so an element that meets the mark's clear space anywhere is taken out"})
        if ((face.get("region") or {}).get("kind") or "").startswith("corner_"):
            # led from the corner its words name: the name the contract's edge-led reader knows
            for kid in kids:
                if isinstance(kid, Group) and kid.name == "motif-field":
                    kid.name = "motif-edge"
            drawn = ["motif-edge" if d == "motif-field" else d for d in drawn]
        concept_kids += kids
        record["drawn"] += drawn
        # a motif across the WHOLE face is its ground field — the concept's own "ambient field" — and is recorded as
        # the composer records its own full-zone decoration field; a band or a corner stays a motif placement
        full = ((face.get("region") or {}).get("kind") == "full")
        for kind, bx, by, bw, bh in boxes:
            place("field" if full and kind == "motif" else kind, bx, by, bw, bh)
    if ring_mm:
        # [the owner's second answer of 2026-09-25: "The lid is missing the concept's rule, ring and radial lines."] the
        # ring in its own colour — ``ring_ink``, the concept's words for it, else the brand's fine-detail swatch; the type
        # ink it borrowed until now only by accident — traced on the lid's own outline, its shape recorded by name
        corner, record["ring_shape"] = _ring_on_the_lid(tuple(lay["ring"]), surface, surface_radius,
                                                        face.get("vision_layout"))
        concept_kids.append(draw_ring(*lay["ring"], ring_ink if ring_ink is not None else Color.from_hex(_UNSOURCED_INK),
                                      radius_mm=corner))
        record["drawn"].append("frame-ring")
        # a ring's artwork is its stroke: recorded as the four strips its ink occupies, as the §BB4 divider is recorded
        # as the strip it prints — never as the box it encloses, which would claim 85% of a lid for a 0.30 mm line
        rx, ry, rw, rh = lay["ring"]
        half = ring_mm / 2.0
        for sx, sy, sw, sh in ((rx - half, ry - half, rw + ring_mm, ring_mm),
                               (rx - half, ry + rh - half, rw + ring_mm, ring_mm),
                               (rx - half, ry - half, ring_mm, rh + ring_mm),
                               (rx + rw - half, ry - half, ring_mm, rh + ring_mm)):
            place("frame", sx, sy, sw, sh)
    if "rule" in placed:
        # [the owner's second answer of 2026-09-25: "The lid is missing the concept's rule, ring and radial lines."]
        # the concept's rule, one straight stroke at the §AU2 weight in the colour its own words give it
        # (``rule_ink``); recorded as the strip its ink prints — the §BB4 divider's kind — never a box it does not fill
        rx, ry, rw, rh = placed["rule"]
        concept_kids.append(Path(name=FACE_RULE, segments=[MoveTo(x=rx, y=ry + rh / 2.0),
                                                           LineTo(x=rx + rw, y=ry + rh / 2.0)],
                                 stroke=Stroke(color=rule_ink if rule_ink is not None
                                               else Color.from_hex(_UNSOURCED_INK), width_mm=rule_mm)))
        record["drawn"].append(FACE_RULE)
        place("divider", rx, ry, rw, rh)
    text_reg = lay["regions"]["text"]
    type_kids: list = []
    if CF.NAME in placed and lines:
        p = placed[CF.NAME]
        align = {"left": "left", "right": "right"}.get(p["align"], "center")
        for j, line in enumerate(lines):
            run = TextRun(name=("product-name-hero" if len(lines) == 1 else f"product-name-hero-{j}"), text=line,
                          x=p["x"], y=p["baseline"] + j * size_pt * _NAME_STEP_MM_PER_PT, size_pt=size_pt,
                          color=ink, font=_name_font(plan), align=align)          # §BH67(c)5
            if style:
                run.tracking_em = style.get("tracking_em")
                run.text_case = style.get("text_case")
            type_kids.append(run)
        record["drawn"].append("product-name-hero")
        place("product_name", text_reg[0], p["ink_top"], text_reg[2], p["ink_bottom"] - p["ink_top"])
    if CF.NAME_AR in placed and ar_text:
        p = placed[CF.NAME_AR]
        type_kids.append(TextRun(name="product-name-ar", text=ar_text, x=p["x"], y=p["baseline"], size_pt=ar_size_pt,
                                 color=ink, font="regular",
                                 align={"left": "left", "right": "right"}.get(p["align"], "center")))
        record["drawn"].append("product-name-ar")
        place("product_name", text_reg[0], p["ink_top"], text_reg[2], p["ink_bottom"] - p["ink_top"])
    if CF.SHADE in placed and set_.get("shade"):
        # [his answer of 2026-09-29 to the §BH71 report, (4): "the lid drawing draws the shade name my brief asks
        # for"] the record's shade, English and Arabic side by side, where the concept sets its own shade line or at
        # the face's foot — the words always the record's, never the ones the concept's picture shows
        p, shade_set = placed[CF.SHADE], set_["shade"]
        for run_name, text, left, _w in _shade_runs(shade_set, p["x"], p["align"]):
            type_kids.append(TextRun(name=run_name, text=text, x=left, y=p["baseline"], size_pt=shade_set["size_pt"],
                                     color=ink, font="regular", align="left"))
        record["drawn"].append(SHADE_RUN)
        place("product_name", text_reg[0], p["ink_top"], text_reg[2], p["ink_bottom"] - p["ink_top"])
        record["shade"] = {"en": shade_set["en"], "ar": shade_set["ar"], "size_pt": shade_set["size_pt"],
                           "place": shade_set["place"], "source": (shade or {}).get("source"),
                           "ar_unconfirmed": bool((shade or {}).get("ar_unconfirmed"))}
    if descriptor:
        record["not_in_arrangement"].append({
            "element": "descriptor", "text": descriptor,
            "reason": "the concept's own arrangement names no supporting line; the descriptor stays on the record "
                      "and off the face"})
    def lid_clip():
        # §BH71 PART 1: on a round lid nothing prints past the lid's own edge — cut to its circle, not to the square its
        # zone is (measured on task 110 redrawn round: a gloss's highlight cut to the square lit the lid's corners)
        if round_lid is not None or oval_lid is not None:   # [§BH71 PART 3: and an oval lid, cut to its ellipse]
            return _ellipse_path(*surface)
        return rect_clip(zx0, zy0, zw, zh)
    concept_group = (Group(name="FRONT_CONCEPT", role="decoration", clip=lid_clip(),
                           children=concept_kids) if concept_kids else None)
    type_group = Group(name=FRONT_DIRECT_PRINT_GROUP, role="decoration", clip=lid_clip(),
                       children=type_kids)
    return concept_group, type_group, mark_box, placements, record


#: [his answer after test day finding 3; the executor's proposal recorded with it: the small copy "placed at the
#: picture's place and size but typed from the brief"] the executor's working figures for type set where the picture
#: prints it, recorded beside every typed line, no ruled number: a line's ink — its tallest letter's top to its lowest
#: letter's foot — is MAP_TYPE_INK_EM of its size, its baseline MAP_TYPE_BELOW_EM of its size above that foot, and the
#: lines of one name MAP_TYPE_LEADING_EM apart
MAP_TYPE_INK_EM = 0.95
#: [his goal of 2026-10-12, (7): ""EYESHADOW PALETTE" as small spaced capitals, as the concept shows (not grey title
#: case)"] a line the picture prints in capitals — its words the brief's, their letters the ones it shows — is set in
#: capitals: its traced height the capitals' own (MAP_TYPE_CAP_EM of an em), spaced out to the width the picture gives
#: it, never wider than MAP_TYPE_MAX_TRACK_EM between letters — [his goal of 2026-10-13, (1)] the text model's own bound
#: (``graph.TRACKING_EM_MAX``), never a second number: 0.6 here against its 0.5 stopped 125
MAP_TYPE_CAP_EM = 0.70
MAP_TYPE_MAX_TRACK_EM = TRACKING_EM_MAX


def _caps_as_seen(t: dict) -> bool:
    """A line the picture prints in capitals whose words are the letters it shows, in any case."""
    seen = [ch for ch in str(t.get("seen") or "") if ch.isalpha()]
    words = [ch for ch in str(t.get("words") or "") if ch.isalpha()]
    return bool(seen) and all(ch.isascii() and ch.isupper() for ch in seen) and \
        [ch.upper() for ch in words] == seen
MAP_TYPE_BELOW_EM = 0.22
MAP_TYPE_LEADING_EM = 1.1
#: [his go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): the map path for a wand vial, whose picture
#: prints its small copy at 4.1 pt on a 16 mm vial] the smallest a line set where its picture prints it is set at: §W2's
#: floor where no print method is recorded (``container_text_floor.FALLBACK_FLOOR_PT``, the floor the acceptance reads)
MAP_TYPE_FLOOR_PT = FALLBACK_FLOOR_PT


def _script_runs(text: str) -> list:
    """``[(text, right_to_left)]``: a line's runs by script, in its reading order — its Arabic words one run, every
    other word the run it follows; a word with no letter (a separator) the run it follows, whatever its script [his
    second look at 117, 2026-10-02: an Arabic line's "•" kept inside its one right-to-left run]."""
    from apps.ire.text_script import is_rtl
    runs: list = []
    for word in text.split():
        rtl = bool(is_rtl(word))
        if runs and not any(ch.isalpha() for ch in word):
            runs[-1] = (runs[-1][0] + " " + word, runs[-1][1])
            continue
        if runs and runs[-1][1] == rtl:
            runs[-1] = (runs[-1][0] + " " + word, rtl)
        else:
            runs.append((word, rtl))
    return runs


#: [his look at 117 drawn from its map, 2026-10-02] each layer of a script's lettering, by the name it is drawn under —
#: the gold ring, lit and in its bronze shade, IS the name's traced contour, so the name checks and the foil read it
LETTERING_NAMES = {"outer": "script-lettering-outer", "ring": "product-name-traced",
                   "ring-shade": "product-name-traced-shade", "inline": "script-lettering-inline",
                   "body": "script-lettering-body"}
#: [his rules for cloning a design from a picture, 2026-10-02, rule 4] the layers of a script's lettering that are its gold
LETTERING_GOLD = ("ring", "ring-shade")


def _lettering_paths(layered: dict | None, at) -> dict | None:
    """[His look at 117 drawn from its map, 2026-10-02.] A script line's lettering layers (``trace_lettering``) as
    filled paths, back to front, each under its name in LETTERING_NAMES and in its measured ink; with the bounds of the
    outermost as fractions. None where no layer is on record."""
    if not layered or not layered.get("layers"):
        return None
    # [his rules for cloning a design from a picture, 2026-10-02, rule 4: "only the gold OUTLINES are foil"] the gold
    # ring, lit and in its shade, each the ring it is — cut, even-odd, at the outline of the first layer drawn over the
    # gold (the pale inline, or the letter's body where there is none), so a plate cut from it is the letters' gold
    # outline and never the letters solid; page 1 shows what it showed, the next layer in covering each cut
    layers = layered["layers"]
    golds = [j for j, layer in enumerate(layers) if layer["name"] in LETTERING_GOLD]
    within = (_traced_segments({"svg": layers[golds[-1] + 1]["svg"], "frame": layered["frame"]}, at)[0]
              if golds and golds[-1] + 1 < len(layers) and "svg" in layers[golds[-1] + 1] else [])
    paths, bounds = [], None
    for layer in layers:
        if "cubics" in layer:
            # [his rules, 2026-10-02, rule 1] a layer of lettering SET in a face: its cubics, its holes its own
            segs, b = _cubic_segments(layer["cubics"], at)
            if segs:
                paths.append(Path(name=LETTERING_NAMES[layer["name"]], segments=segs,
                                  fill=SolidFill(color=Color.from_hex(layer["ink"])), fill_rule="evenodd"))
                bounds = bounds if bounds is not None else b
            continue
        segs, b = _traced_segments({"svg": layer["svg"], "frame": layered["frame"]}, at)
        if not segs:
            continue
        ring = layer["name"] in LETTERING_GOLD and bool(within)
        paths.append(Path(name=LETTERING_NAMES[layer["name"]], segments=segs + (within if ring else []),
                          fill=SolidFill(color=Color.from_hex(layer["ink"])),
                          fill_rule="evenodd" if ring else "nonzero"))
        bounds = bounds if bounds is not None else b
    if not paths or not any(p.name == LETTERING_NAMES["ring"] for p in paths):
        return None
    return {"paths": paths, "bounds": bounds}


def _cubic_segments(polys, at):
    """[His rules, 2026-10-02, rule 1.] Each ring of each polygon (``[[x0, y0], [c1x, c1y, c2x, c2y, x, y], …]`` in the
    product's fractions) as the cubics it is, placed through ``at``; and their bounds as fractions."""
    segs, xs, ys = [], [], []
    for poly in polys:
        for ring in poly:
            xs.append(ring[0][0])
            ys.append(ring[0][1])
            x, y = at(ring[0])
            segs.append(MoveTo(x=x, y=y))
            for c in ring[1:]:
                xs.extend(c[0::2])
                ys.extend(c[1::2])
                (ax, ay), (bx, by), (x, y) = at(c[0:2]), at(c[2:4]), at(c[4:6])
                segs.append(CubicTo(x1=ax, y1=ay, x2=bx, y2=by, x=x, y=y))
            segs.append(ClosePath())
    return segs, ([min(xs), min(ys), max(xs), max(ys)] if xs else None)


def continued_outlines(art: dict, part_box, w: float, h: float) -> dict:
    """[His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (3).] The
    approved container's line art (``art``: its flat redraw's outlines, their box on the container and the container's
    size — ``targets.composite.continued_line_art``) laid over ``part_box`` — fractions of a product ``w`` × ``h`` mm —
    at the container's own scale, enlarged only as far as it must be to cover the box, centred on it: the outlines with
    their frame moved onto this product, for ``_traced_segments`` (cropped to the box by the caller). Its roses are the
    tube's roses, at the tube's size or larger, never shrunk."""
    fx0, fy0, fx1, fy1 = (float(v) for v in art["box"])
    pw_c, ph_c = float(art["product_mm"][0]), float(art["product_mm"][1])
    field_w, field_h = (fx1 - fx0) * pw_c, (fy1 - fy0) * ph_c
    px0, py0, px1, py1 = (float(v) for v in part_box)
    k = max(1.0, (px1 - px0) * w / field_w, (py1 - py0) * h / field_h)
    ox, oy, kx, ky = (float(v) for v in art["outlines"]["frame"])
    cx = (px0 + px1) / 2.0 + (ox - (fx0 + fx1) / 2.0) * pw_c * k / w
    cy = (py0 + py1) / 2.0 + (oy - (fy0 + fy1) / 2.0) * ph_c * k / h
    return {"svg": art["outlines"]["svg"], "frame": [cx, cy, kx * pw_c * k / w, ky * ph_c * k / h]}


def _reaching(segs: list, x0: float, y0: float, x1: float, y1: float) -> list:
    """[His test blocker on design 123, (3).] The subpaths of ``segs`` whose box reaches the box (x0, y0)–(x1, y1) — the
    rest lie wholly outside the crop and are left out of the file."""
    out, sub = [], []

    def flush():
        pts = [(g.x, g.y) for g in sub if hasattr(g, "x")] + [(g.x1, g.y1) for g in sub if hasattr(g, "x1")]
        if pts and min(p[0] for p in pts) <= x1 and max(p[0] for p in pts) >= x0 and min(
                p[1] for p in pts) <= y1 and max(p[1] for p in pts) >= y0:
            out.extend(sub)
    for g in segs:
        if isinstance(g, MoveTo) and sub:
            flush()
            sub = []
        sub.append(g)
    if sub:
        flush()
    return out


#: [His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4):
#: "the big rose in Blossom Arch / Stem Journey is 122's rose, whole and scaled ($0)".]
#: The container's rose in a continued carton's big bloom: as large as its place this many times over, centred on it;
#: the field kept clear behind it by this share of its place each side, and drawn at this opacity round it — the
#: concept's field around its one bloom is faint (Stem Journey's)
BLOOM_GROW = 1.6
BLOOM_CLEAR = 0.1
BLOOM_FIELD_OPACITY = 0.5
def clear_rings(rects: list) -> list:
    """[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (4): "never
    over the pattern so the small copy gets lost".] The places a field is kept clear of (``x0, y0, x1, y1`` each), merged
    where they meet — two laid over each other cut nothing where they overlap (a clip fills by its winding, and two
    holes over one spot wind it back in: measured on Garden Wrap at 57 x 123 mm, its "Hand Cream", spaced down into its
    Arabic's place, stood on the field) — each a ring of points wound against a box's (to cut from a clip)."""
    from shapely.geometry import box
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
    if not rects:
        return []
    merged = unary_union([box(*r) for r in rects])
    return [[list(p) for p in orient(poly, sign=-1.0).exterior.coords[:-1]]
            for poly in getattr(merged, "geoms", [merged]) if not poly.is_empty]


#: [His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010).] a line of
#: copy no taller than this share of the product's height is small copy: a continued field is kept clear of it — the
#: tube's roses, laid where the concept's own sat, fell under Garden Wrap's "Hand Cream", its Arabic and its size, in their
#: own light pink; never cleared round the name, which the concept sets over its roses
#: [His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 6: "FRONT TEXT: "Rose Blossom" in the granted face closest to the concept's soft rounded sans (Quicksand or Montserrat), ONE colour, never two pinks or the heavy house bold; "Hand Cream" in the same family, lighter; Arabic in a matching sans (Tajawal or Cairo), not Naskh. No hard rectangle cut out of the roses behind it; soft breathing room as the concept shows, and the soft oval cartouche behind the BBROSE logo."]
#: the soft room round a front's type: each line's place grown ROOM_PAD of its height, merged where they meet, then laid
#: ROOM_STEPS times over the field in the ground's colour, each ROOM_STRENGTH strong and ROOM_SOFT of the lines' height
#: wider than the last — so the field fades into a clearing round the type and never ends at an edge
ROOM_PAD = 0.3
ROOM_SOFT = 0.22
ROOM_STEPS = 7
ROOM_STRENGTH = 0.3
#: … and the soft oval the mark stands in: its edge fading over these rings, each this much wider, this strong
CARTOUCHE_RINGS = 4
CARTOUCHE_SOFT = 0.12
CARTOUCHE_STRENGTH = 0.28


def soft_rooms(types: list, ground_hex, sw: float, sh: float, ox: float, oy: float) -> list:
    """[His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 6: "FRONT TEXT: "Rose Blossom" in the granted face closest to the concept's soft rounded sans (Quicksand or Montserrat), ONE colour, never two pinks or the heavy house bold; "Hand Cream" in the same family, lighter; Arabic in a matching sans (Tajawal or Cairo), not Naskh. No hard rectangle cut out of the roses behind it; soft breathing room as the concept shows, and the soft oval cartouche behind the BBROSE logo."]
    The soft rooms of a front's ground over its field, under its type: each typed line's place (``types``' boxes, the
    product's fractions; ``sw``, ``sh`` its drawn size, ``ox``, ``oy`` its top left) grown ROOM_PAD of its height and
    merged where they meet, then laid ROOM_STEPS times, each ring ROOM_SOFT of the lines' mean height wider than the
    last, in the ground's colour at ROOM_STRENGTH — rounded, never a rectangle's edge; [] with no ground or no type."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    if not ground_hex:
        return []
    places, tall = [], []
    for t in types:
        tb = [float(v) for v in t.get("box") or []]
        if len(tb) != 4 or not t.get("words"):
            continue
        x0, y0, x1, y1 = ox + tb[0] * sw, oy + tb[1] * sh, ox + tb[2] * sw, oy + tb[3] * sh
        pad = ROOM_PAD * (y1 - y0)
        places.append(box(x0 - pad, y0 - pad, x1 + pad, y1 + pad))
        tall.append(y1 - y0)
    if not places:
        return []
    core = unary_union(places)
    step = ROOM_SOFT * sum(tall) / len(tall)
    out = []
    for k in range(ROOM_STEPS - 1, -1, -1):
        shape = core.buffer(step * k, join_style=1, resolution=8)
        segs = []
        for poly in getattr(shape, "geoms", [shape]):
            pts = list(poly.exterior.coords)
            segs += [MoveTo(x=pts[0][0], y=pts[0][1])] + [LineTo(x=x, y=y) for x, y in pts[1:]] + [ClosePath()]
        out.append(Path(name="soft-room-%d" % k, segments=segs, fill_rule="nonzero",
                        fill=SolidFill(color=Color.from_hex(ground_hex), opacity=ROOM_STRENGTH)))
    return out


SMALL_COPY_SHARE = 0.035
#: … the room kept round it, a share of its own height
SMALL_COPY_PAD = 0.35


def _traced_segments(outlines: dict, at):
    """[His answer after test day finding 3, (3).] The outlines potrace traced of a script line (``trace_script``),
    read with the house mark's own reader of potrace's grammar (``brand_mark._transform``, ``_parse_d``), each point
    taken through its frame to the product's fractions and through ``at`` onto the sheet; and their bounds as fractions."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(outlines["svg"].encode("utf-8"))
    fx0, fy0, kx, ky = (float(v) for v in outlines["frame"])
    subs = []
    for g in (el for el in root if el.tag.endswith("}g") or el.tag == "g"):
        xform = _brand_mark._transform(g.get("transform"))
        for path_el in g:
            parsed, _curves, _lines = _brand_mark._parse_d(path_el.get("d"), xform)
            subs.extend(parsed)
    xs, ys, segs = [], [], []

    def P(u, v):
        fx, fy = fx0 + u * kx, fy0 + v * ky
        xs.append(fx)
        ys.append(fy)
        return at((fx, fy))
    for sub in subs:
        for op in sub:
            if op[0] == "M":
                x, y = P(op[1], op[2])
                segs.append(MoveTo(x=x, y=y))
            elif op[0] == "L":
                x, y = P(op[1], op[2])
                segs.append(LineTo(x=x, y=y))
            elif op[0] == "C":
                ax, ay = P(op[1], op[2])
                bx, by = P(op[3], op[4])
                x, y = P(op[5], op[6])
                segs.append(CubicTo(x1=ax, y1=ay, x2=bx, y2=by, x=x, y=y))
            else:
                segs.append(ClosePath())
    return segs, ([min(xs), min(ys), max(xs), max(ys)] if xs else None)


#: [§BH50(g)] the share of the safe area's width a front line is set within — the estimate of a face's width runs a little
#: under the face itself (147's name, sized to its picture, measured 2.1 mm over)
MAP_TYPE_SAFE_FILL = 0.92


def _name_parts(typed: list, product_name: str) -> set:
    """[His go of 2026-10-08.] The lines a name the picture sets over several lines is set on — 122's 148, "ROSE" over
    "BLOSSOM", the start of "Rose Blossom Hand Cream": read top to bottom, the lines no phrase on record names (their
    words the picture's own) whose words, together and in order, spell the start of the product's name; two lines at
    least, else none (119's "LIP GLOSS" is in its name, never its start)."""
    from apps.pipeline.services.concept_design_map import PICTURE_ENGLISH

    def words(text):
        return [w for w in str(text).casefold().split() if any(ch.isalnum() for ch in w)]
    name = words(product_name)
    taken, spelled = [], []
    for t in sorted((t for t in typed if t.get("source") == PICTURE_ENGLISH and t.get("box")),
                    key=lambda t: (float(t["box"][1]), float(t["box"][0]))):
        mine = words(t.get("words"))
        if mine and name[len(spelled):len(spelled) + len(mine)] == mine:
            taken.append(t["part"])
            spelled += mine
    return set(taken) if len(taken) >= 2 else set()


def _name_start(typed: list, product_name: str) -> set:
    """[His test blocker on design 122 at reconstruction, 2026-10-08: "the concept sets "Rose Blossom" small inside its
    oval window. The picture's layout wins (my rule): draw the name at the size the concept shows".] The one line a
    concept sets the start of its name on, alone — 122's 149, "Rose Blossom" of "Rose Blossom Hand Cream", its "Hand
    Cream" on the line below: read top to bottom, the first line, from any source, whose words are the first words of
    the product's name, two at least or the whole name; none where a line carries the whole name. Until this a line was
    the name only when it was the whole name, so 149's was drawn as plain copy and the drawing stopped with no name."""
    def words(text):
        return [w for w in str(text).casefold().split() if any(ch.isalnum() for ch in w)]
    name = words(product_name)
    if not name or any(words(t.get("words")) == name for t in typed):
        return set()
    for t in sorted((t for t in typed if t.get("box")), key=lambda t: (float(t["box"][1]), float(t["box"][0]))):
        mine = words(t.get("words"))
        if mine and (len(mine) >= 2 or len(mine) == len(name)) and name[:len(mine)] == mine:
            return {t["part"]}
    return set()


def _map_lettered(t: dict, k: int, is_name: bool, at) -> dict | None:
    """[The owner's finding on design 119, 2026-10-03.] A display or turned line (one ``concept_design_map.set_display``
    measured, with its outlines traced) whose words the picture shows in full: its letters SET in the closest face where
    one came close and they were set in the line's own words, else its traced outlines — ``{"path", "bounds" (product
    fractions), "lettering": how, in words}``; None for any other line."""
    setting = t.get("lettering_set")
    if (setting is None or not t.get("outlines") or "svg" not in t["outlines"] or t.get("match") is None
            or float(t["match"]) < 1.0):
        return None
    name = "product-name-traced" if is_name else "front-lettering-%d" % k
    ink = SolidFill(color=Color.from_hex(t["ink"]))
    keys = ("state", "face", "iou", "outline", "bar", "why", "faces_measured", "lines", "read_turned", "set_by",
            "display_faces_measured")
    how = {key: setting[key] for key in keys if key in setting}
    if setting.get("state") == "SET" and setting.get("words") == t["words"] and setting.get("layers"):
        segs, bounds = _cubic_segments(setting["layers"][0]["cubics"], at)
        if segs and bounds:
            return {"path": Path(name=name, segments=segs, fill=ink, fill_rule="evenodd"), "bounds": bounds,
                    "lettering": how}
    segs, bounds = _traced_segments(t["outlines"], at)
    if not segs or not bounds:
        return None
    return {"path": Path(name=name, segments=segs, fill=ink, fill_rule="nonzero"), "bounds": bounds,
            "lettering": dict(how, drawn="traced")}


#: [His goal after the pitch page, 2026-10-15 (OWNER_BLOCKER_CLEARANCE.md), A (6): "TEXT FITS its frame (130's Arabic ran
#: outside the oval)."] a line inside a window or frame is held inside it: no wider than the frame's inside at the line's
#: own rows, less this share of it each side
MAP_TYPE_FRAME_PAD = 0.06
#: a right-to-left run measured in the granted Arabic face, and given this much more room — the face it prints in may run
#: wider than the face it is measured in
MAP_TYPE_RTL_ROOM = 1.12


def _frame_room(t: dict, shapes: dict, w: float, h: float) -> Optional[tuple[float, float]]:
    """[His goal after the pitch page, A (6)] ``(left, right)`` in mm of the room a line has inside the window or frame
    that holds it — the smallest whose box holds the line's centre and more than its box — at the line's own rows: an
    ellipse's chord at the row farthest from its centre, a box's inside; less ``MAP_TYPE_FRAME_PAD`` each side. None
    where no window or frame holds it."""
    fx0, fy0, fx1, fy1 = (float(v) for v in t["box"])
    cx, cy = (fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0
    best = None
    for holder in list(shapes.get("windows") or []) + list(shapes.get("frames") or []):
        bx0, by0, bx1, by1 = (float(v) for v in holder["box"])
        area = (bx1 - bx0) * (by1 - by0)
        if not (bx0 <= cx <= bx1 and by0 <= cy <= by1) or area <= (fx1 - fx0) * (fy1 - fy0):
            continue
        if best is None or area < best[0]:
            best = (area, holder)
    if best is None:
        return None
    holder = best[1]
    bx0, by0, bx1, by1 = (float(v) for v in holder["box"])
    left, right = bx0 * w, bx1 * w
    if holder.get("shape") == "ellipse" and holder.get("centre") and holder.get("half"):
        ex, ey = float(holder["centre"][0]) * w, float(holder["centre"][1]) * h
        a, b = float(holder["half"][0]) * w, float(holder["half"][1]) * h
        dy = max(abs(fy0 * h - ey), abs(fy1 * h - ey))
        half = a * math.sqrt(max(0.0, 1.0 - (dy / b) ** 2)) if b > 0 else 0.0
        left, right = ex - half, ex + half
    pad = MAP_TYPE_FRAME_PAD * (right - left)
    return (left + pad, right - pad) if right - left > 2.0 * pad else None


#: [his last goal before the pitch, 2026-10-16, Step 2: "text inside the panel and readable (139's "with colloidal oat"
#: runs off the edge ...)"] a line no frame holds stays inside the product's own outline at its rows, this far in each side
MAP_TYPE_OUTLINE_PAD_MM = 1.5


def _outline_room(backbone, fy0: float, fy1: float) -> Optional[tuple[float, float]]:
    """``(left, right)`` in mm of the room inside the drawn product's own outline (``backbone.silhouette``) at the rows
    ``fy0``–``fy1`` (shares of its height) — the narrowest of them, its curves sampled — less MAP_TYPE_OUTLINE_PAD_MM a
    side; None where the outline cannot be read there."""
    pts, last = [], None
    for seg in getattr(backbone, "silhouette", None) or []:
        x, y = getattr(seg, "x", None), getattr(seg, "y", None)
        if x is None or y is None:
            continue
        if last is not None and getattr(seg, "x1", None) is not None:
            (ax, ay), (bx, by), (cx, cy) = last, (seg.x1, seg.y1), (seg.x2, seg.y2)
            for k in range(1, 8):
                u = k / 8.0
                pts.append(((1 - u) ** 3 * ax + 3 * (1 - u) ** 2 * u * bx + 3 * (1 - u) * u * u * cx + u ** 3 * x,
                            (1 - u) ** 3 * ay + 3 * (1 - u) ** 2 * u * by + 3 * (1 - u) * u * u * cy + u ** 3 * y))
        pts.append((float(x), float(y)))
        last = (float(x), float(y))
    if len(pts) < 3:
        return None
    h = float(backbone.height_mm)
    left, right = None, None
    for f in (fy0, (fy0 + fy1) / 2.0, fy1):
        yy = f * h
        xs = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            if (y0 <= yy < y1) or (y1 <= yy < y0):
                xs.append(x0 + (yy - y0) * (x1 - x0) / (y1 - y0))
        if len(xs) < 2:
            continue
        lo, hi = min(xs), max(xs)
        left = lo if left is None else max(left, lo)
        right = hi if right is None else min(right, hi)
    if left is None or right - left <= 2.0 * MAP_TYPE_OUTLINE_PAD_MM:
        return None
    return left + MAP_TYPE_OUTLINE_PAD_MM, right - MAP_TYPE_OUTLINE_PAD_MM


def _arabic_width_mm(text: str, size_pt: float) -> Optional[float]:
    """[His goal after the pitch page, A (6)] a right-to-left run's width as shaped, in the granted Arabic face — the
    Latin estimate reads Arabic letters as Latin ones (130's line ran outside its oval)."""
    from apps.dielines.exporters.text_intl import shape_ar
    from apps.ire.font_roles import theme_faces
    from apps.ire.text_metrics import drawn_width_mm
    face = theme_faces()["faces"].get("arabic-body")
    if not face:
        return None
    return drawn_width_mm(shape_ar(text, keep_harakat=True), size_pt * _INK_MM_PER_PT, face[0])


def _upper_of(t: dict, face: Optional[dict]) -> bool:
    """[His goal after the pitch page, A (1)] whether a line prints in capitals: its read's case, where it set a face."""
    return bool(face and face["upper"])


def _tracking_of(face: Optional[dict]) -> float:
    """[His goal after the pitch page, A (1)] the letter-spacing a line's read gives it, in ems."""
    return min(float(face["tracking_em"]), MAP_TYPE_MAX_TRACK_EM) if face else 0.0


def _map_type_group(map_front: dict, zone: dict, backbone, s: float, ox: float, oy: float, *, name_font: str,
                    product_name: str, faces: dict | None = None):
    """[His answer after test day finding 3, 2026-09-30.] The front's type, set where its concept picture prints it:
    each line the map traced (``map_front["shapes"]["types"]``) that a source on record gives words (``words``,
    ``source``) — in its measured ink, at the largest size at which it fits both its traced width and its traced
    height; the record's product name in the concept's own face (``name_font``), wrapped to the lines that height holds;
    a line of two scripts set as one run per script, the first from the line's left edge and the last to its right, as
    the picture lays them. A line no source gives words is left out, by name. Returns ``(the group, its placements in
    his front — each as pictured — and the record: what was set, at what size, from where, its drawn box, and what was
    left out)``, or None where no line has words (the ruled block then sets the front).
    [His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 6: "FRONT TEXT: "Rose Blossom" in the granted face closest to the concept's soft rounded sans (Quicksand or Montserrat), ONE colour, never two pinks or the heavy house bold; "Hand Cream" in the same family, lighter; Arabic in a matching sans (Tajawal or Cairo), not Naskh. No hard rectangle cut out of the roses behind it; soft breathing room as the concept shows, and the soft oval cartouche behind the BBROSE logo."]
    ``faces`` (a carton front's own roles, ``front_faces``): its name set in its "name" role, every other line's Latin
    in its "copy" role and its Arabic in its "arabic" role — and the name in ONE ink, the one its picture's lines are
    read in where they agree, else its largest line's."""
    types = (map_front.get("shapes") or {}).get("types") or []
    # [his last goal before the pitch, Step 2, 138: "fonts ... as the concept shows" — its "eau de parfum" set "Eau de
    # Parfum", his brief's capitals] his brief's words in the case the concept letters them: a line its read sets in small
    # letters is set in small letters (never the product's name, set as the record holds it)
    typed = [dict(t, words=t["words"].lower()) if ((t.get("style") or {}).get("case") == "lower"
                                                    and t["words"] != product_name) else t
             for t in types if t.get("words")]
    if not typed:
        return None
    w, h = backbone.width_mm, backbone.height_mm
    zx, zy, zw, zh = (float(zone[k]) for k in ("x", "y", "width", "height"))
    kids, places, boxes, lines_record = [], [], {}, []
    gold_names: list = []
    over_codes: list = []                      # [his go of 2026-10-02] lines typed wider than the front
    name_traced = None
    left_out = [{"part": t["part"], "why": t.get("left_out")} for t in types if not t.get("words")]

    def est(text, size_pt):
        return name_width_estimate_mm(text, size_pt)
    # [his goal after the pitch page, A (1)] each Latin line in the granted face closest to its concept's lettering, its
    # widths measured in that face; [A (6)] every line held inside the frame that holds it
    from apps.ire import lettering_faces as _LF
    shapes = map_front.get("shapes") or {}
    chosen = {id(t): _LF.choose(t) for t in typed}

    def measure_mm(t, text, size_pt, *, rtl=False, upper=False, tracking=0.0):
        if rtl:
            got = _arabic_width_mm(text, size_pt)
            if got is not None:
                return got * MAP_TYPE_RTL_ROOM
        face = chosen[id(t)]
        if face is not None and not rtl:
            got = _LF.width_mm(face, text.upper() if upper else text, size_pt, tracking)
            if got is not None:
                return got
        return name_width_estimate_mm(text, size_pt, upper=upper, tracking_em=tracking)

    def line_width_mm(t, line, size_pt, *, upper=False, tracking=0.0):
        runs = _script_runs(line)
        space = measure_mm(t, " ", size_pt, upper=upper, tracking=tracking)
        return sum(measure_mm(t, text, size_pt, rtl=rtl, upper=upper, tracking=tracking) for text, rtl in runs) + \
            space * (len(runs) - 1)
    # [§BH50(g)(1)-(2), OWNER RULED: "THE ... SAFE AREA GOVERNS THE FRONT"; "THE PRODUCT NAME IS FRONT COPY — the floor
    # and the safe area apply to it like any other run"] a line is set no wider than the zone's safe area — smaller than
    # the picture sets it where the picture runs past it (122's concept 147: its name 2.1 mm past), centred where the
    # picture centres it
    name_parts = _name_parts(typed, product_name) or _name_start(typed, product_name)
    margin_mm = float(zone.get("safe_margin_mm") or 0.0)
    safe_width_mm = zw - 2.0 * margin_mm if zw > 2.0 * margin_mm else zw
    # [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010): Garden Wrap's "Rose" set at 21.9 pt over its "Blossom" at
    # 10.5 pt — each line sized from its own trace, the picture setting them alike] a name the picture sets over several
    # lines is set at one size: the largest at which every line fits its own width, no taller than its tallest line
    named = [t for t in typed if t["words"] == product_name or t["part"] in name_parts]
    one_size = None
    if len(named) >= 2 and not any(t.get("lettering_set") or t.get("rotation") in (90, -90) for t in named):
        tallest = max((float(t["box"][3]) - float(t["box"][1])) * h for t in named)
        one_size = min([tallest / MAP_TYPE_INK_EM / _INK_MM_PER_PT]
                       + [min((float(t["box"][2]) - float(t["box"][0])) * w, safe_width_mm * MAP_TYPE_SAFE_FILL)
                          / max(line_width_mm(t, t["words"], 1.0, upper=_upper_of(t, chosen[id(t)]),
                                           tracking=_tracking_of(chosen[id(t)])), 1e-6) for t in named])
    # [his goal of 2026-10-10, item 6: "ONE colour, never two pinks"] the name's one ink
    name_ink = None
    if faces and named:
        read = {str(t["ink_read"]).upper() for t in named if t.get("ink_read")}
        name_ink = (read.pop() if len(read) == 1 and len([t for t in named if t.get("ink_read")]) == len(named)
                    else max(named, key=lambda t: float(t["box"][3]) - float(t["box"][1]))["ink"])
    for k, t in enumerate(typed):
        fx0, fy0, fx1, fy1 = (float(v) for v in t["box"])
        bw, bh = (fx1 - fx0) * w, (fy1 - fy0) * h               # mm: the picture's line
        bw = min(bw, safe_width_mm * MAP_TYPE_SAFE_FILL)
        room = _frame_room(t, map_front.get("holders") or shapes, w, h)
        if room is None:
            room = _outline_room(backbone, fy0, fy1)
        if room is not None and (room[1] - room[0] < bw or fx0 * w < room[0] or fx0 * w + bw > room[1]):
            # [his goal after the pitch page, A (6)] no wider than its frame at its own rows, centred where the picture
            # centres it, kept inside the frame
            bw = room[1] - room[0]
            centre = min(max((fx0 + fx1) / 2.0 * w, room[0] + bw / 2.0), room[1] - bw / 2.0)
            fx0 = (centre - bw / 2.0) / w
        face = chosen[id(t)]
        upper, face_track = _upper_of(t, face), _tracking_of(face)
        cap_em = _LF.cap_em(face) if face is not None else MAP_TYPE_CAP_EM
        ink = Color.from_hex(t["ink"])
        # [his go of 2026-10-08] a name the picture sets over several lines (122's 148: "ROSE" / "BLOSSOM") is the name on
        # each of them — a line no phrase on record names whose words run in the product's name
        is_name = t["words"] == product_name or t["part"] in name_parts
        if is_name and name_ink is not None:
            ink = Color.from_hex(name_ink)
        caps, track = (not is_name) and _caps_as_seen(t), 0.0     # [his goal of 2026-10-12, (7)]
        if is_name and one_size is not None:
            size_pt, lines = one_size, [t["words"]]
        elif is_name:
            best = None
            for n in (1, 2, 3):
                lines_em = MAP_TYPE_INK_EM + (n - 1) * MAP_TYPE_LEADING_EM
                size_pt = bh / lines_em / _INK_MM_PER_PT
                for _ in range(60):
                    lines = fitting_name_lines(t["words"], size_pt, bw)
                    if len(lines) <= n and all(line_width_mm(t, line, size_pt, upper=upper, tracking=face_track) <= bw
                                               for line in lines):
                        break
                    size_pt *= 0.97
                if best is None or size_pt > best[0]:
                    best = (size_pt, lines)
            size_pt, lines = best
        elif caps:
            # [his goal of 2026-10-12, (7)] the capitals at their own height, spaced to the picture's width — [his goal
            # after the pitch page, A (1)] the height of its own face's capitals, measured in its own face
            size_pt = bh / cap_em / _INK_MM_PER_PT
            natural = line_width_mm(t, t["words"], size_pt, upper=True)
            if natural > bw:
                size_pt *= bw / natural
            elif len(t["words"]) > 1:
                track = min(MAP_TYPE_MAX_TRACK_EM, (bw - natural) / (size_pt * _TRACKING_MM_PER_PT
                                                                      * (len(t["words"]) - 1)))
            lines = [t["words"]]
        else:
            # its width at one point, measured as it is set: its face, its case, its spacing
            width_mm_per_pt = line_width_mm(t, t["words"], 1.0, upper=upper, tracking=face_track)
            size_pt = min(bh / MAP_TYPE_INK_EM / _INK_MM_PER_PT, bw / width_mm_per_pt)
            lines = [t["words"]]
            track = face_track
        # [his go of 2026-10-02: the map path for a wand vial] never under the print floor: a line the picture prints
        # smaller is set at the floor, centred where the picture centres it, and its record says so
        pictured_pt = size_pt
        size_pt = max(size_pt, MAP_TYPE_FLOOR_PT)
        if is_name and size_pt > pictured_pt:
            lines = fitting_name_lines(t["words"], size_pt, max(bw, zw))
        # [the owner's finding on design 119, 2026-10-03: "front as the concept shows it"] a line the picture letters in a
        # display face, or stands on end, drawn as the picture letters it — set in the closest face, in its own words,
        # where one came close (``concept_design_map.set_display``), else the picture's traced lettering, with why —
        # never typed across where the picture stands it on end
        # [his goal after the pitch page, A (1)] a line its read sets in a granted face — any but a script — is that face's
        # live type, never the picture's traced letters (128's "TIDE GLASS", traced pale from the glass's glow)
        set_live = face is not None and face["family"] != "script" and t.get("rotation") not in (90, -90)
        lettered = None if set_live else _map_lettered(t, k, is_name, lambda p: (ox + float(p[0]) * w * s,
                                                                                  oy + float(p[1]) * h * s))
        if lettered is not None:
            kids.append(lettered["path"])
            from apps.pipeline.services.concept_design_map import is_gold_hex as _is_gold
            if _is_gold(lettered["path"].fill.color.to_hex()):
                # [his goal of 2026-10-12, (4)] a line set as the picture letters it, in its gold — 124's script name
                gold_names.append(lettered["path"].name)
            bounds = lettered["bounds"]
            boxes[t["part"]] = [round(v, 5) for v in bounds]
            tx0, ty0, tx1, ty1 = bounds[0] * w, bounds[1] * h, bounds[2] * w, bounds[3] * h
            cx0, cx1, cy0, cy1 = max(tx0, zx), min(tx1, zx + zw), max(ty0, zy), min(ty1, zy + zh)
            places.append({"zone_id": zone.get("zone_id"), "kind": "product_name" if is_name else "descriptor",
                           "surface_family": "body", "as_pictured": True, "nx": round((cx0 - zx) / zw, 4),
                           "ny": round((cy0 - zy) / zh, 4), "nw": round((cx1 - cx0) / zw, 4),
                           "nh": round((cy1 - cy0) / zh, 4)})
            # its size, as pictured: the height of its letters across the line — its width, stood on end
            across = (tx1 - tx0) if t.get("rotation") in (90, -90) else (ty1 - ty0)
            lines_record.append({"part": t["part"], "words": t["words"], "source": t["source"], "lines": [t["words"]],
                                 "size_pt": round(across / MAP_TYPE_INK_EM / _INK_MM_PER_PT, 2), "traced": True,
                                 **({"rotation": t["rotation"]} if t.get("rotation") in (90, -90) else {}),
                                 "lettering": lettered["lettering"]})
            if is_name and (name_traced is None or lines_record[-1]["size_pt"] > name_traced["size_pt"]):
                # [his go of 2026-10-08] the name set as the picture letters it, at its largest line's size
                name_traced = {"words": t["words"], "size_pt": lines_record[-1]["size_pt"],
                               "read_as": "the height of the name's letters as the picture sets them"}
            continue
        # [his answer after test day finding 3, (3): "the script lettering also traced from the picture"] the name drawn
        # as the picture's own traced lettering — only where every word the picture shows is the record's name
        if is_name and not set_live and t.get("outlines") and t.get("match") is not None and float(t["match"]) >= 1.0:
            segs, bounds = _traced_segments(t["outlines"], lambda p: (ox + float(p[0]) * w * s, oy + float(p[1]) * h * s))
            # [his look at 117 drawn from its map, 2026-10-02: the script's edges "not constant", its highlighting "not
            # looking good"] the lettering as the picture layers it, each layer an even offset of one smooth letter
            # [his rules for cloning a design from a picture, 2026-10-02, rule 1: "LETTERING IS SET, NOT TRACED ...
            # exact words"] the letters set in the closest face where one came close AND they were set in the record's
            # own words; else the picture's traced lettering, with why
            lettering = t.get("lettering_layers")
            setting = lettering["set"] if lettering and "set" in lettering else None
            if setting and setting["state"] == "SET" and setting["words"] == t["words"] and setting.get("layers"):
                lettering = {"layers": setting["layers"]}
            layered = _lettering_paths(lettering, lambda p: (ox + float(p[0]) * w * s, oy + float(p[1]) * h * s))
            if layered:
                kids.extend(layered["paths"])
                bounds = layered["bounds"]
                # [his answer 2 of 2026-10-02: gold in the picture is foil] the lettering's gold ring, lit and in its shade
                # — and [his goal of 2026-10-12, (4)] any layer of it drawn in the picture's gold
                from apps.pipeline.services.concept_design_map import is_gold_hex as _is_gold
                gold_names.extend(p.name for p in layered["paths"]
                                  if p.name in (LETTERING_NAMES["ring"], LETTERING_NAMES["ring-shade"])
                                  or (isinstance(p.fill, SolidFill) and _is_gold(p.fill.color.to_hex())))
            elif segs and bounds:
                kids.append(Path(name="product-name-traced", segments=segs, fill=SolidFill(color=ink),
                                 fill_rule="nonzero"))
                from apps.pipeline.services.concept_design_map import is_gold_hex as _is_gold
                if _is_gold(ink.to_hex()):
                    gold_names.append("product-name-traced")   # [his goal of 2026-10-12, (4)] 124's gold script name
            if (layered or segs) and bounds:
                boxes[t["part"]] = [round(v, 5) for v in bounds]
                tx0, ty0, tx1, ty1 = bounds[0] * w, bounds[1] * h, bounds[2] * w, bounds[3] * h
                cx0, cx1, cy0, cy1 = max(tx0, zx), min(tx1, zx + zw), max(ty0, zy), min(ty1, zy + zh)
                places.append({"zone_id": zone.get("zone_id"), "kind": "product_name", "surface_family": "body",
                               "as_pictured": True, "nx": round((cx0 - zx) / zw, 4), "ny": round((cy0 - zy) / zh, 4),
                               "nw": round((cx1 - cx0) / zw, 4), "nh": round((cy1 - cy0) / zh, 4)})
                lines_record.append({"part": t["part"], "words": t["words"], "source": t["source"], "lines": lines,
                                     "size_pt": round(size_pt, 2), "traced": True,
                                     # [his rules, rule 1] set in a face, or traced and why
                                     **({"lettering": {key: setting[key] for key in ("state", "face", "iou", "outline",
                                                                                     "bar", "why", "faces_measured",
                                                                                     "lines")
                                                       if key in setting}} if setting else {})})
                name_traced = {"words": t["words"], "size_pt": round(size_pt, 2),
                               "read_as": "the size a typed name filling its place takes"}
                continue
        if t.get("rotation") in (90, -90):
            # [his fixes to 142 (Cherry Kiss), 2026-10-17, (1): "A vertical script name is set vertically in a matching
            # script face, whole and inside the panel (it came out horizontal sans, cut off)."] a line the picture stands
            # on end and no tracer lettered is set on end in its own face, as one line: its letters as tall as its box
            # is wide, its length no longer than its box's height nor the front's safe height, centred where the picture
            # centres it — reading up at 90, down at -90
            tx0, ty0, tx1, ty1 = (float(v) for v in t["box"])
            across = (tx1 - tx0) * w
            face = _LF.by_proportion(t, face, (ty1 - ty0) * h / across if across > 0 else 0.0, MAP_TYPE_INK_EM)
            chosen[id(t)] = face
            upper, face_track = _upper_of(t, face), _tracking_of(face)
            along = min((ty1 - ty0) * h, (zh - 2.0 * margin_mm if zh > 2.0 * margin_mm else zh) * MAP_TYPE_SAFE_FILL)
            length_per_pt = max(line_width_mm(t, t["words"], 1.0, upper=upper, tracking=face_track), 1e-6)
            pictured_pt = min(across / MAP_TYPE_INK_EM / _INK_MM_PER_PT, along / length_per_pt)
            size_pt = max(pictured_pt, MAP_TYPE_FLOOR_PT)
            em = size_pt * _INK_MM_PER_PT
            length_mm = line_width_mm(t, t["words"], size_pt, upper=upper, tracking=face_track)
            rise = (MAP_TYPE_INK_EM - MAP_TYPE_BELOW_EM) * em          # mm: baseline to the letters' top
            spare = (across - MAP_TYPE_INK_EM * em) / 2.0
            if t["rotation"] == 90:
                base_x = tx0 * w + spare + rise                         # the letters' tops to its left
                x0, x1 = base_x - rise, base_x + MAP_TYPE_BELOW_EM * em
            else:
                base_x = tx1 * w - spare - rise                         # the letters' tops to its right
                x0, x1 = base_x - MAP_TYPE_BELOW_EM * em, base_x + rise
            mid = (ty0 + ty1) / 2.0 * h
            if is_name:
                run_font = face["font"] if face else (faces["name"] if faces else name_font)
                run_name = "product-name-hero-0"
            else:
                run_font = face["font"] if face else (faces["copy"] if faces else "regular")
                run_name = "front-descriptor-%d-0" % k
            kids.append(TextRun(name=run_name, text=t["words"], x=ox + base_x * s, y=oy + mid * s, size_pt=size_pt,
                                color=ink, font=run_font, align="center", rotation_deg=float(t["rotation"]),
                                **({"text_case": "upper"} if upper else {}),
                                **({"tracking_em": round(face_track, 4)} if face_track else {})))
            y0, y1 = mid - length_mm / 2.0, mid + length_mm / 2.0
            boxes[t["part"]] = [round(x0 / w, 5), round(y0 / h, 5), round(x1 / w, 5), round(y1 / h, 5)]
            cx0, cx1, cy0, cy1 = max(x0, zx), min(x1, zx + zw), max(y0, zy), min(y1, zy + zh)
            places.append({"zone_id": zone.get("zone_id"), "kind": "product_name" if is_name else "descriptor",
                           "surface_family": "body", "as_pictured": True, "nx": round((cx0 - zx) / zw, 4),
                           "ny": round((cy0 - zy) / zh, 4), "nw": round((cx1 - cx0) / zw, 4),
                           "nh": round((cy1 - cy0) / zh, 4)})
            lines_record.append({"part": t["part"], "words": t["words"], "source": t["source"], "lines": [t["words"]],
                                 "size_pt": round(size_pt, 2), "rotation": t["rotation"], "set_on_end": True,
                                 **({"face": {k_: face[k_] for k_ in ("stem", "weight", "family", "why")}}
                                    if face else {}),
                                 **({"at_the_floor": {"pictured_pt": round(pictured_pt, 2),
                                                      "floor_pt": MAP_TYPE_FLOOR_PT}} if size_pt > pictured_pt else {})})
            continue
        em = size_pt * _INK_MM_PER_PT                            # mm: one em of this line
        ink_h = (MAP_TYPE_INK_EM + (len(lines) - 1) * MAP_TYPE_LEADING_EM) * em
        top = fy0 * h + (bh - ink_h) / 2.0
        baselines = [top + (MAP_TYPE_INK_EM - MAP_TYPE_BELOW_EM) * em + j * MAP_TYPE_LEADING_EM * em
                     for j in range(len(lines))]
        if caps:
            # [his goal of 2026-10-12, (7)] capitals stand on their baseline to their own height, no descender
            ink_h = cap_em * em
            top = fy0 * h + (bh - ink_h) / 2.0
            baselines = [top + ink_h]
        widest = 0.0
        for j, line in enumerate(lines):
            if is_name:
                # [his goal after the pitch page, A (1)] the name in the face closest to its concept's lettering, in its
                # case and spacing; else the concept's own named face, or the front's
                kids.append(TextRun(name="product-name-hero-%d" % j, text=line, x=ox + (fx0 * w + bw / 2.0) * s,
                                    y=oy + baselines[j] * s, size_pt=size_pt, color=ink,
                                    font=face["font"] if face else (faces["name"] if faces else name_font),
                                    align="center",
                                    **({"text_case": "upper"} if upper else {}),
                                    **({"tracking_em": round(face_track, 4)} if face_track else {})))
                widest = max(widest, line_width_mm(t, line, size_pt, upper=upper, tracking=face_track))
                continue
            # its runs side by side, a space apart, the line centred where the picture centres it — each anchored at its
            # left edge, so an estimate wider than the run leaves its room at the line's end, never between its runs
            runs = _script_runs(line)
            # [his goal of 2026-10-12, (7)] a line measured as it is set — capitals, spaced, where it is set so; [his goal
            # after the pitch page, A (1), (6)] in its own face, its Arabic in the Arabic face
            cased = caps or upper

            def run_width_mm(text, pt, rtl=False, _t=t, _track=track, _cased=cased):
                return measure_mm(_t, text, pt, rtl=rtl, upper=_cased, tracking=_track)
            space = run_width_mm(" ", size_pt)
            # [his second look at 117, 2026-10-02] a line the map names as a name (117's "Arabic product name") set bold,
            # as the picture sets it; every other line regular
            line_font = "bold" if "name" in str(t["part"]).lower() else "regular"
            if t.get("weight") == "bold":
                # [his review of 119, 2026-10-05, point 4: "Set it in the concept's weight (bold, berry)."] a line the
                # picture sets bold, measured (`trace_type`), set bold
                line_font = "bold"
            if faces:
                # [his goal of 2026-10-10, item 6: ""Hand Cream" in the same family, lighter"] the front's copy role
                line_font = faces["copy"]
            if face is not None:
                line_font = face["font"]      # [his goal after the pitch page, A (1)] its concept's lettering
            widths = [run_width_mm(text, size_pt, rtl) for text, rtl in runs]
            widest = sum(widths) + space * (len(runs) - 1)
            cursor = fx0 * w + (bw - widest) / 2.0
            for r, ((text, rtl), rw) in enumerate(zip(runs, widths)):
                x, align = cursor, "left"
                if len(runs) == 1:
                    # [his second look at 117, 2026-10-02] a line of one run centred where the picture centres it — an
                    # estimate off by any amount moves its two ends alike (117's Arabic name printed 2 mm left of it)
                    x, align = fx0 * w + bw / 2.0, "center"
                if len(runs) == 2 and r == 0:
                    # [his look at 117 drawn from its map, 2026-10-02] a bilingual line's two runs anchored toward their
                    # join, one space apart: an estimate off by any amount moves the line's outer ends, never the gap
                    # between its runs (117's "Body Lotion •" and its Arabic printed about 2.5 mm apart)
                    x, align = cursor + rw, "right"
                run_font = faces["arabic"] if faces and rtl else line_font
                if rtl and face is not None and not faces:
                    run_font = "regular"           # an Arabic run keeps the Arabic face its role resolves
                kids.append(TextRun(name="front-descriptor-%d-%d" % (k, r), text=text, x=ox + x * s,
                                    y=oy + baselines[j] * s, size_pt=size_pt, color=ink,
                                    font=run_font, align=align, rtl=rtl,
                                    **({"text_case": "upper", "tracking_em": round(track, 4)} if cased and not rtl
                                       else {"tracking_em": round(track, 4)} if track and not rtl else {})))
                cursor += rw + space
        x0, x1 = fx0 * w + (bw - widest) / 2.0, fx0 * w + (bw + widest) / 2.0
        y0, y1 = top, top + ink_h
        if widest > zw:
            # [his go of 2026-10-02] a line wider than the front he confirmed — the floor can make one so — measured
            # where it is typed, its code holding acceptance as every overrun's does, never cut by the front unsaid
            from apps.ire.compose_dropper import FRONT_COPY_EXCEEDS_ZONE
            over_codes.append("%s: %s +%.2f mm" % (FRONT_COPY_EXCEEDS_ZONE, t["part"], widest - zw))
        boxes[t["part"]] = [round(x0 / w, 5), round(y0 / h, 5), round(x1 / w, 5), round(y1 / h, 5)]
        cx0, cx1, cy0, cy1 = max(x0, zx), min(x1, zx + zw), max(y0, zy), min(y1, zy + zh)
        places.append({"zone_id": zone.get("zone_id"), "kind": "product_name" if is_name else "descriptor",
                       "surface_family": "body", "as_pictured": True, "nx": round((cx0 - zx) / zw, 4),
                       "ny": round((cy0 - zy) / zh, 4), "nw": round((cx1 - cx0) / zw, 4), "nh": round((cy1 - cy0) / zh, 4)})
        lines_record.append({"part": t["part"], "words": t["words"], "source": t["source"], "lines": lines,
                             "size_pt": round(size_pt, 2),
                             **({"face": {k_: face[k_] for k_ in ("stem", "weight", "family", "why")}} if face else {}),
                             **({"in_frame_mm": [round(room[0], 2), round(room[1], 2)]} if room is not None else {}),
                             **({"at_the_floor": {"pictured_pt": round(pictured_pt, 2), "floor_pt": MAP_TYPE_FLOOR_PT}}
                                if size_pt > pictured_pt else {})})
    record = {"typed": lines_record, "left_out": left_out, "boxes": boxes, "codes": over_codes,
              **({"name_traced": name_traced} if name_traced else {}), "gold_nodes": gold_names,
              "type_figures": {"ink_em": MAP_TYPE_INK_EM, "below_em": MAP_TYPE_BELOW_EM,
                               "leading_em": MAP_TYPE_LEADING_EM}}
    return (Group(name=FRONT_DIRECT_PRINT_GROUP, role="decoration", children=kids,
                  clip=rect_clip(ox + zx * s, oy + zy * s, zw * s, zh * s)), places, record)


#: [his answer after test day finding 3] the motif a front drawn from its concept's map draws: its band's gold edge
#: [and its scattered stars]
MAP_MOTIF_PREFIXES = ("drip-map-", "sparkle-map-", "lineart-map-", "lineart-gold-map-")
#: [his test blocker on design 124, 2026-10-11, (3)] a lid's art, traced in colour: its illustration's paths, and the group
#: that draws the whole of it (``lid_art.art_group``)
LID_ART_PREFIX, LID_ART_GROUP = "lid-art-", "LID ART"
#: [his answers of 2026-10-02 (a18911a), answer 2: "Gold in the picture is foil"] the map front's parts its tracers find by
#: the picture's gold, by the names they are drawn under (a band's own fill and pale line are "band-map-", never gold)
MAP_GOLD_PREFIXES = ("drip-map-", "sparkle-map-", "rule-map-", "lineart-gold-map-", "frame-gold-map-",
                     "window-rim-gold-map-")   # [his goal of 2026-10-13, (7)] a window's gold rim, drawn as a line
#: [his look at 117 drawn from its map, 2026-10-02] the map front's parts inside the product's drawn outline
MAP_WITHIN_OUTLINE = "map-front-within-the-outline"
#: [his rules for cloning a design from a picture, 2026-10-02, rule 3: "EDGE TO EDGE MEANS BLEED"] the parts the picture
#: runs edge to edge, cut by the product's drawn outline only — past it they are its bleed; and the rest, his front
MAP_EDGE_TO_EDGE = "map-front-edge-to-edge"
MAP_WITHIN_HIS_FRONT = "map-front-within-his-front"
#: [his look at 117 drawn from its map, 2026-10-02: the edges "not looking 3D"] each layer of a band's relief, by the
#: name it is drawn under — the gold's under the drip's, so the foil the concept names on the drips reads them
MAP_RELIEF_NAMES = {"edge-shade": "drip-map-%d-shade", "edge-body": "drip-map-%d-body", "edge-lit": "drip-map-%d-lit",
                    "edge-body-inner": "drip-map-%d-body-inner", "edge-inner": "drip-map-%d-inner",
                    "inline": "band-map-%d-inline", "fill": "band-map-%d"}
#: … and a sparkle's: its rim in its shade at its own size, its body in its ink, its heart lit — shares of its size
MAP_SPARKLE_RELIEF = (("-rim", 1.0, "ink_shade"), ("", 0.75, "ink"), ("-lit", 0.4, "ink_lit"))
#: [his rules for cloning a design from a picture, 2026-10-02, rule 4: "THE FOIL PLATE FOLLOWS THE DRAWING ... only the
#: gold OUTLINES are foil"] the layers of a band's relief that are its gold. Each is drawn as the ring it is — cut, even-
#: odd, where the gold ends inside it: at the outline of the first layer drawn over the gold (the pale line, or the fill
#: where there is none) — so a plate cut from them is the gold outline, never the band it rings; page 1 shows what it
#: showed, the next layer in covering each cut
MAP_RELIEF_GOLD = ("edge-shade", "edge-body", "edge-lit", "edge-body-inner", "edge-inner")


#: a mark drawn no wider than this share over the picture's own mark's width
MARK_WIDE_SLACK = 1.08


def _map_mark_box(map_front: dict, zone: dict, backbone, s: float, ox: float, oy: float, master):
    """[His answer after test day finding 3, 2026-09-30: the house mark "from its approved master only, never traced, at
    the place the picture gives it".] The approved master's box ``(x, y, w, h)`` on the sheet at the concept's mark: its
    height the picture's ink's, its left edge the ink's, its width the master's own proportion of that height — never
    stretched — held inside his confirmed front; with what it leaves over beside the picture's ink, in millimetres.
    None where the map traced no mark."""
    marks = (map_front.get("shapes") or {}).get("marks") or []
    if not marks:
        return None
    w_mm, h_mm = backbone.width_mm, backbone.height_mm
    fx0, fy0, fx1, fy1 = marks[0]["box"]
    hh = (fy1 - fy0) * h_mm                                   # mm: the picture's ink height
    ww = hh / float(master.aspect)                            # mm: the master's own width at that height
    fit = "the picture's ink height; the master's own width at it"
    # [his last goal before the pitch, 2026-10-16, Step 2: "text inside the panel" — 126's BBROSE drawn 38 mm wide
    # across a 40 mm bottle, past its label and its outline] never wider than the picture's own mark (MARK_WIDE_SLACK
    # over it) nor than his front: where its own width at the picture's height would be, it is set smaller, unstretched,
    # centred on the picture's mark
    most = min((fx1 - fx0) * w_mm * MARK_WIDE_SLACK, float(zone["width"]))
    y0, left = fy0 * h_mm, fx0 * w_mm
    if ww > most > 0:
        scale = most / ww
        y0 += (hh - hh * scale) / 2.0
        ww, hh = most, hh * scale
        left = (fx0 + fx1) / 2.0 * w_mm - ww / 2.0
        fit = "the picture's own mark's width — the master's own proportion at it, set smaller to hold it"
    x0 = max(left, float(zone["x"]))
    x0 = min(x0, float(zone["x"]) + float(zone["width"]) - ww)
    return {"box": (ox + x0 * s, oy + y0 * s, ww * s, hh * s), "part": marks[0]["part"],
            "ink": marks[0].get("ink"),
            "fit": fit,
            "drawn_box": [round(x0 / w_mm, 5), fy0, round((x0 + ww) / w_mm, 5), fy1],
            "beside_the_picture_mm": {"left": round(x0 - fx0 * w_mm, 2), "right": round(x0 + ww - fx1 * w_mm, 2)}}


def _past_the_outline(node, outline, sides) -> float | None:
    """[His rules for cloning a design from a picture, 2026-10-02, rule 3.] How far ``node`` (a path or a rect, sheet
    millimetres) runs past ``outline`` (its segments) on each side it reaches — ``sides``: {side: (top, foot)}, the
    sheet rows it reaches that side on, or None for every row both share — at its narrowest, read at nine rows a side;
    None where they share none."""
    from shapely.geometry import LineString, Polygon

    def ring(segs):
        pts, last = [], None
        for sg in segs:
            if sg.op in ("M", "L"):
                last = (sg.x, sg.y)
                pts.append(last)
            elif sg.op == "C" and last is not None:
                for k in range(1, 9):
                    u, v = k / 8.0, 1.0 - k / 8.0
                    pts.append((v ** 3 * last[0] + 3 * v * v * u * sg.x1 + 3 * v * u * u * sg.x2 + u ** 3 * sg.x,
                                v ** 3 * last[1] + 3 * v * v * u * sg.y1 + 3 * v * u * u * sg.y2 + u ** 3 * sg.y))
                last = (sg.x, sg.y)
        return Polygon(pts).buffer(0) if len(pts) >= 3 else None
    shape = (ring(node.segments) if hasattr(node, "segments")
             else Polygon([(node.x, node.y), (node.x + node.w, node.y), (node.x + node.w, node.y + node.h),
                           (node.x, node.y + node.h)]))
    body = ring(outline)
    if shape is None or body is None or shape.is_empty or body.is_empty:
        return None
    least = None
    for side, rows in sides.items():
        y0, y1 = max(shape.bounds[1], body.bounds[1]), min(shape.bounds[3], body.bounds[3])
        if rows is not None:
            y0, y1 = max(y0, rows[0]), min(y1, rows[1])
        if y1 <= y0:
            continue
        for k in range(1, 10):
            y = y0 + (y1 - y0) * k / 10.0
            line = LineString([(body.bounds[0] - 1e3, y), (body.bounds[2] + 1e3, y)])
            a, b = shape.intersection(line), body.intersection(line)
            if a.is_empty or b.is_empty:
                continue
            past = (b.bounds[0] - a.bounds[0]) if side == "left" else (a.bounds[2] - b.bounds[2])
            least = past if least is None else min(least, past)
    return least


def _mark_clear_of(box, boxes: dict, zone: dict, backbone, s: float, ox: float, oy: float) -> tuple:
    """[His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): the map path for a wand vial.] The
    house mark's ruled ``box`` (document mm) as it is where it clears every part a front drawn from its picture drew
    (``boxes``: fractions of the product); else moved, its size kept, into the free height those parts leave on the
    body's front — from the closure's edge (``backbone.cap_region``) to the body's far end — the run above them where it
    holds the mark with a quarter of its height clear on each side, else the tallest run, centred across the front
    ``zone``. ``(the box, where it went in words)``; ``(box, None)`` where it clears them already or no run holds it."""
    x, y, bw, bh = box
    w, h = backbone.width_mm, backbone.height_mm
    drawn = [(ox + b[0] * w * s, oy + b[1] * h * s, ox + b[2] * w * s, oy + b[3] * h * s) for b in boxes.values()]
    if not drawn or not any(x < x1 and x + bw > x0 and y < y1 and y + bh > y0 for x0, y0, x1, y1 in drawn):
        return box, None
    cap_ys = [float(sg.y) for sg in (backbone.cap_region or []) if hasattr(sg, "y")]
    body = (0.0, h)
    if cap_ys:
        body = (max(cap_ys), h) if min(cap_ys) < h / 2.0 else (0.0, min(cap_ys))   # the body: away from its closure
    top, foot = oy + body[0] * s, oy + body[1] * s
    spans: list = []
    for _x0, y0, _x1, y1 in sorted(drawn, key=lambda d: d[1]):
        if spans and y0 <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], y1)
        else:
            spans.append([y0, y1])
    edges = [top] + [v for span in spans for v in span] + [foot]
    runs = [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2) if edges[i + 1] - edges[i] >= 1.5 * bh]
    if not runs:
        return box, None
    above = runs[0] if runs[0][1] <= spans[0][0] + 1e-6 else None
    a, b = above if above is not None else max(runs, key=lambda r: r[1] - r[0])
    cx = ox + (float(zone["x"]) + float(zone["width"]) / 2.0) * s
    return ((cx - bw / 2.0, (a + b) / 2.0 - bh / 2.0, bw, bh),
            "above the picture's parts" if above is not None else "in the front's tallest free height")


def _outline_segments(shape: dict, at, sw: float, sh: float) -> list:
    """[His go of 2026-10-08, item 1.] A traced frame's or window's closed outline: an ellipse as four cubic arcs about its
    centre, turned by its angle; a four-sided one through its corners. ``at``: a point in the product's fractions to the
    page; ``sw``, ``sh``: the product's drawn width and height."""
    import math
    if shape["shape"] == "ellipse":
        (cx, cy), (hx, hy) = at(shape["centre"]), (float(shape["half"][0]) * sw, float(shape["half"][1]) * sh)
        t = math.radians(float(shape["angle"]))
        k = 0.5522847498

        def pt(u, v):
            return cx + u * math.cos(t) - v * math.sin(t), cy + u * math.sin(t) + v * math.cos(t)
        quads = [((hx, 0), (hx, k * hy), (k * hx, hy), (0, hy)), ((0, hy), (-k * hx, hy), (-hx, k * hy), (-hx, 0)),
                 ((-hx, 0), (-hx, -k * hy), (-k * hx, -hy), (0, -hy)), ((0, -hy), (k * hx, -hy), (hx, -k * hy), (hx, 0))]
        x, y = pt(hx, 0)
        segs = [MoveTo(x=x, y=y)]
        for _p0, c1, c2, p1 in quads:
            (ax, ay), (bx, by), (ex, ey) = pt(*c1), pt(*c2), pt(*p1)
            segs.append(CubicTo(x1=ax, y1=ay, x2=bx, y2=by, x=ex, y=ey))
        return segs + [ClosePath()]
    pts = [at(c) for c in shape["corners"]]
    return [MoveTo(x=pts[0][0], y=pts[0][1])] + [LineTo(x=x, y=y) for x, y in pts[1:]] + [ClosePath()]


#: [His goal after the pitch page, 2026-10-15, A (4).] a traced solid's further inks are drawn under this name — never
#: ``shape-map-``: the outline repair (``self_check.SHAPE_NAMES``) redraws a part's solid and rims together, and a layer
#: that is not concentric with them is no ring of theirs
SHAPE_INK_NAME = "shape-ink-%d-%d"
#: … and a solid lies in a window where its box lies inside the window's box, give or take this share of the product
IN_WINDOW_SLACK = 0.01


def in_a_window(box, windows: list) -> bool:
    """[His goal after the pitch page, 2026-10-15, A (4).] Whether the part's ``box`` (the product's fractions) lies inside
    one of the traced ``windows`` — 132's flower in its cartouche: drawn over the window, as the picture prints it."""
    return any(float(wb[0]) - IN_WINDOW_SLACK <= float(box[0]) and float(wb[1]) - IN_WINDOW_SLACK <= float(box[1])
               and float(box[2]) <= float(wb[2]) + IN_WINDOW_SLACK and float(box[3]) <= float(wb[3]) + IN_WINDOW_SLACK
               for wb in (wd["box"] for wd in windows if wd.get("box")))


#: [His review of 127, 130, 131 and 132, 2026-10-15, C (3)] a face's art starts at its closure's drawn foot where the
#: closure stands at the product's top and ends above ``FACE_TOP_MOST`` of its height (``face_art.face_top``'s own limit)
FACE_TOP_MOST = 0.6


#: [his last goal before the pitch, Step 2] the parting line where a cap meets its body: its width, and its shade of the
#: cap's own colour (each channel this share of it)
JOIN_WIDTH_MM = 0.25
JOIN_SHADE = 0.6


def closure_foot_share(backbone) -> Optional[float]:
    """Where the drawn closure ends — its cap, and its collar where it has one — as a share of the product's height,
    where it stands at the top; None for a closure drawn elsewhere (a tube stood on its cap) or none."""
    ys = [float(getattr(sg, "y")) for region in (backbone.cap_region, backbone.collar_region) if region
          for sg in region if hasattr(sg, "y")]
    if not ys or not backbone.height_mm or min(ys) >= 0.5 * float(backbone.height_mm):
        return None
    foot = max(ys) / float(backbone.height_mm)
    return foot if 0.0 < foot < FACE_TOP_MOST else None


def closure_head_share(backbone) -> Optional[float]:
    """Where a closure drawn at the product's foot (a tube stood on its cap) begins, as a share of its height; None for
    a closure at the top, or none."""
    ys = [float(getattr(sg, "y")) for region in (backbone.cap_region, backbone.collar_region) if region
          for sg in region if hasattr(sg, "y")]
    if not ys or not backbone.height_mm or min(ys) < 0.5 * float(backbone.height_mm):
        return None
    head = min(ys) / float(backbone.height_mm)
    return head if 1.0 - FACE_TOP_MOST < head < 1.0 else None


def _map_front_group(map_front: dict, zone: dict, backbone, s: float, ox: float, oy: float):
    """[His answer after test day finding 3, 2026-09-30: each part "the same way, draw it"; the layout "exactly the
    picture".] The parts the concept's map traced (``map_front["shapes"]``, fractions of the product's box), drawn at the
    picture's places on the product as drawn: each band filled in its colour with its gold edge stroked as traced, each
    rule in its measured ink. Returns ``(the group, its placements in the front zone — each AS PICTURED, so the zone's
    safe margin is a production note on it (his answer on the safe margin) — and the record: what was drawn, the motif's
    node names, each part's drawn box)``."""
    shapes = map_front["shapes"]
    w, h = backbone.width_mm, backbone.height_mm

    def at(p):
        return ox + float(p[0]) * w * s, oy + float(p[1]) * h * s

    def path(points, close):
        segs = [MoveTo(x=at(points[0])[0], y=at(points[0])[1])]
        segs += [LineTo(x=at(p)[0], y=at(p)[1]) for p in points[1:]]
        return segs + ([ClosePath()] if close else [])

    def curve(points, close):
        # [his look at 117 drawn from its map, 2026-10-02: "everything should be smooth"] a traced line drawn as one
        # smooth curve through its points — each step a cubic Bézier whose handles follow its neighbours (Catmull-Rom)
        # — never a chain of straight steps
        pts = [at(p) for p in points]
        n = len(pts)
        if n < 3:
            return path(points, close)
        segs = [MoveTo(x=pts[0][0], y=pts[0][1])]
        for i in range(n if close else n - 1):
            p0 = pts[(i - 1) % n] if (close or i > 0) else pts[i]
            p1, p2 = pts[i], pts[(i + 1) % n]
            p3 = pts[(i + 2) % n] if (close or i + 2 < n) else p2
            segs.append(CubicTo(x1=p1[0] + (p2[0] - p0[0]) / 6.0, y1=p1[1] + (p2[1] - p0[1]) / 6.0,
                                x2=p2[0] - (p3[0] - p1[0]) / 6.0, y2=p2[1] - (p3[1] - p1[1]) / 6.0, x=p2[0], y=p2[1]))
        return segs + ([ClosePath()] if close else [])

    def cubics(polys):
        # [his rules, 2026-10-02, rule 2] each ring of each polygon as the cubics it was refit as, every point placed
        segs = []
        for poly in polys:
            for ring in poly:
                x, y = at(ring[0])
                segs.append(MoveTo(x=x, y=y))
                for c in ring[1:]:
                    (ax, ay), (bx, by), (x, y) = at(c[0:2]), at(c[2:4]), at(c[4:6])
                    segs.append(CubicTo(x1=ax, y1=ay, x2=bx, y2=by, x=x, y=y))
                segs.append(ClosePath())
        return segs

    children, places, boxes, drawn, clipped = [], [], {}, [], {}
    face = map_front.get("face_art")
    if face:
        # [his goal for the pitch, 2026-10-15, A (4), B (7)] the product's printed face as its flat redraw traced in
        # colour, over the whole product clipped to its outline — the map's fields, bands, motifs, frames and rules are
        # in it; its type and its mark are set over it, live
        from apps.pipeline.targets.container.lid_art import art_group
        top = float(face.get("top") or 0.0)
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (3): "parts meet as the concept shows (127 has a gap
        # between the cap and the body)"] the face meets the closure as drawn: it begins at the drawn closure's own foot,
        # never at the map's reading of it a little above (127's art over its cap's foot) or below it (130's navy band —
        # the body's colour showing between its lid and its face)
        _foot = closure_foot_share(backbone)
        if _foot is not None:
            top = _foot
        # [his goal after the pitch page, B (10)] and where a closure stands at its foot (139's tube on its cap), the
        # face ends where the drawn closure begins
        end = float(face["foot"]) if face.get("foot") is not None else 1.0
        _head = closure_head_share(backbone)
        if _head is not None and end < 1.0:
            end = _head
        children.append(art_group(face, ox, oy + top * h * s, w * s, (end - top) * h * s,
                                  _scaled(backbone.silhouette, s, ox, oy), prefix="face", name="FACE ART",
                                  ground=not face.get("flat")))
        # [his last goal before the pitch, Step 2; his D (11) for 126: "the two gold frame lines"] the map's own rules
        # and frames drawn over the face's art too: a hairline its flat redraw may lose
        shapes = {k: v for k, v in shapes.items() if k in ("types", "marks", "params", "rules", "frames")}
        drawn.append("face art")
    zx, zy = float(zone["x"]), float(zone["y"])
    zw, zh = float(zone["width"]), float(zone["height"])

    def place(kind, name, pts, ink_mm2=None):
        # [his yes of 2026-09-30, transcribed at 5d23649: "The design is drawn from the map only inside the area he
        # confirms."] a part the picture prints past his confirmed front is drawn to its edge and no further — what is
        # cut, on each side, said in millimetres; its drawn box and its placement are what is drawn
        x0, x1 = min(float(p[0]) for p in pts) * w, max(float(p[0]) for p in pts) * w
        y0, y1 = min(float(p[1]) for p in pts) * h, max(float(p[1]) for p in pts) * h
        cut = {side: round(v, 2) for side, v in (("left", zx - x0), ("right", x1 - zx - zw), ("top", zy - y0),
                                                 ("foot", y1 - zy - zh)) if v > 0.005}
        if cut:
            clipped[name] = cut
        x0, x1, y0, y1 = max(x0, zx), min(x1, zx + zw), max(y0, zy), min(y1, zy + zh)
        boxes[name] = [round(x0 / w, 5), round(y0 / h, 5), round(x1 / w, 5), round(y1 / h, 5)]
        places.append({"zone_id": zone.get("zone_id"), "kind": kind, "surface_family": "body", "as_pictured": True,
                       "nx": round((x0 - zx) / zw, 4), "ny": round((y0 - zy) / zh, 4),
                       "nw": round((x1 - x0) / zw, 4), "nh": round((y1 - y0) / zh, 4),
                       # [his go of 2026-10-08, item 1] line art and a frame cover what their strokes ink
                       **({"ink_share": round(min(1.0, ink_mm2 / (zw * zh)), 4)} if ink_mm2 is not None else {})})
    edge_kids, edge_parts = [], []
    # [His goal after the pitch page, 2026-10-15, A (4): "every element in the concept is drawn (132's centre flower …
    # was missing)"] a solid the picture prints INSIDE a window (132's flower in its cartouche) is drawn over the window
    # and its frame, never under them: 132's flower was traced and drawn, then painted out by its cartouche's fill
    over_windows = []
    standing = []

    def _stands_alone(box) -> bool:
        # a part over less than ROUND_FIELD_SHARE of the front stands in one place; one over more is the field itself
        from apps.ire.compose import ROUND_FIELD_SHARE
        x0, y0 = max(0.0, float(box[0])), max(0.0, float(box[1]))
        x1, y1 = min(1.0, float(box[2])), min(1.0, float(box[3]))
        return (x1 - x0) * (y1 - y0) < ROUND_FIELD_SHARE
    for i, solid in enumerate(shapes.get("shapes") or []):
        # [the owner's finding on design 119, 2026-10-03: "Every panel is vector, drawn from the concept's map"] a solid
        # shape the picture prints in one colour, as the fewest cubics it was refit as, its holes its own — under every
        # other part, as the picture prints them over it
        start = len(children)
        if solid.get("undrawn"):
            # [His review of 127, 130, 131 and 132, 2026-10-15, C (2): "never printed broken"] a motif its photo's trace
            # breaks, with no clean redraw to draw it from, is left out — said beside Approve (``flat_motif_codes``)
            continue
        flat = solid.get("flat") or {}
        if flat.get("state") == "TRACED":
            # [His review of 127, 130, 131 and 132, 2026-10-15, C (2): "redrawn flat and traced again"] drawn from its flat
            # redraw, in its own colours where it was traced so, else its clean outlines in its ink — in its part's box
            bx0, by0, bx1, by1 = (float(v) for v in flat["box"])
            (ax, ay), (ax1, ay1) = at((bx0, by0)), at((bx1, by1))
            if flat.get("art"):
                from apps.pipeline.targets.container.lid_art import art_group
                children.append(art_group(flat["art"], ax, ay, ax1 - ax, ay1 - ay, None, prefix="shape-map-%d" % i,
                                          name="shape-map-%d %s" % (i, solid["part"]), ground=False))
            else:
                segs, _bounds = _traced_segments(flat["outlines"], at)
                children.append(Path(name="shape-map-%d" % i, segments=segs, fill_rule="nonzero",
                                     fill=SolidFill(color=Color.from_hex(flat["ink"]))))
            if in_a_window(solid["box"], shapes.get("windows") or []):
                over_windows.extend(children[start:])
                del children[start:]
            elif _stands_alone([bx0, by0, bx1, by1]):
                # [his goal after the pitch page, B (10): the designer's eye on 140, "concept a full-colour smiling honey
                # dipper; drawing a faint ghosted outline"] a motif redrawn flat that stands in one place on the front
                # stands OVER the pattern run all round it and over the soft room round the type — never under them:
                # 140's dipper was drawn first, then its oat field twice and seven rooms of the ground over it
                standing.extend(children[start:])
                del children[start:]
            place("motif", solid["part"], [[bx0, by0], [bx1, by1]])
            drawn.append(solid["part"])
            continue
        if solid.get("rim") and solid["rim"].get("cubics"):
            # [his review of 119, 2026-10-05, point 5: "The silhouette keeps the concept's details"] the pale rim the
            # picture draws round it, and the edge's shadow outside the rim, under it — its neck's threads read against
            # them, and they close the wand's gap
            outer = solid["rim"].get("outer")
            if outer and outer.get("cubics"):
                children.append(Path(name="shape-rim-outer-%d" % i, segments=cubics(outer["cubics"]),
                                     fill=SolidFill(color=Color.from_hex(outer["ink"])), fill_rule="evenodd"))
            children.append(Path(name="shape-rim-%d" % i, segments=cubics(solid["rim"]["cubics"]),
                                 fill=SolidFill(color=Color.from_hex(solid["rim"]["ink"])), fill_rule="evenodd"))
        children.append(Path(name="shape-map-%d" % i, segments=cubics(solid["cubics"]),
                             fill=SolidFill(color=Color.from_hex(solid["ink"])), fill_rule="evenodd"))
        for j, layer in enumerate(solid.get("layers") or []):
            # [his goal after the pitch page, 2026-10-15, A (4)] each further ink the picture prints the shape in (132's
            # flower: its gold disc, then its blue outline and leaves), over its first
            children.append(Path(name=SHAPE_INK_NAME % (i, j), segments=cubics(layer["cubics"]),
                                 fill=SolidFill(color=Color.from_hex(layer["ink"])), fill_rule="evenodd"))
        if in_a_window(solid["box"], shapes.get("windows") or []):
            over_windows.extend(children[start:])
            del children[start:]
        place("motif", solid["part"], [solid["box"][0:2], solid["box"][2:4]])
        drawn.append(solid["part"])
    for i, band in enumerate(shapes.get("bands") or []):
        start = len(children)
        edges = band["edges"] if "edges" in band else {}
        arches = band.get("arches") or {}
        if arches.get("stops") and arches.get("rows"):
            # [his look at 117 drawn from its map, 2026-10-02] the arches between its drips in the picture's own colour
            # down them, behind the band: from the band's top to its drips' foot, the full width it is drawn across
            from apps.ire.graph import GradientFill, GradientStop
            bx = [float(p[0]) for p in band["outline"]]
            # [his rules, rule 3] run, with the band, past a side it reaches
            ax0, ay0 = at((min(bx) - (band["bleed_reach"] if "left" in edges else 0), arches["rows"][0]))
            ax1, ay1 = at((max(bx) + (band["bleed_reach"] if "right" in edges else 0), arches["rows"][1]))
            children.append(Rect(name="band-map-%d-arches" % i, x=ax0, y=ay0, w=ax1 - ax0, h=ay1 - ay0, fill=GradientFill(
                kind="linear", x1=ax0, y1=ay0, x2=ax0, y2=ay1,
                stops=[GradientStop(offset=float(o), color=Color.from_hex(hx)) for o, hx in arches["stops"]])))
        relief = (band.get("relief") or {}).get("layers") or []
        if relief:
            # [his look at 117 drawn from its map, 2026-10-02: the edges "not looking 3D"] the band and its gold edge as
            # the picture lights them, back to front, each an even offset of the band
            # [his rules, 2026-10-02, rule 4] … its gold each the ring it is: cut where the gold ends inside
            golds = [j for j, layer in enumerate(relief) if layer["name"] in MAP_RELIEF_GOLD]
            within = relief[golds[-1] + 1]["outline"] if golds and golds[-1] + 1 < len(relief) else None
            for layer in relief:
                if layer.get("cubics"):
                    # [his rules, 2026-10-02, rule 2: "SHAPES ARE REDRAWN AS CLEAN CURVES"] the layer as the fewest
                    # cubics the map refit it as, its holes its own (even-odd) — the gold its ring, open where it is
                    children.append(Path(name=MAP_RELIEF_NAMES[layer["name"]] % i, segments=cubics(layer["cubics"]),
                                         fill=SolidFill(color=Color.from_hex(layer["ink"])), fill_rule="evenodd"))
                    continue
                ring = layer["name"] in MAP_RELIEF_GOLD and within is not None
                children.append(Path(name=MAP_RELIEF_NAMES[layer["name"]] % i,
                                     segments=curve(layer["outline"], True) + (curve(within, True) if ring else []),
                                     fill=SolidFill(color=Color.from_hex(layer["ink"])),
                                     fill_rule="evenodd" if ring else None))
        else:
            children.append(Path(name="band-map-%d" % i, segments=curve(band["outline"], True),
                                 fill=SolidFill(color=Color.from_hex(band["fill"]))))
        place("band", band["part"], band["outline"])
        drawn.append(band["part"])
        if relief and band.get("edge_width"):
            edge_pts = [p for line in band.get("edge") or [] for p in line]
            if edge_pts:
                place("motif", map_front["edge_part"] if map_front.get("edge_part") else band["part"] + " — its edge",
                      edge_pts)
        elif band.get("edge_ink") and band.get("edge_width"):
            for j, line in enumerate(band.get("edge") or []):
                children.append(Path(name="drip-map-%d-%d" % (i, j), segments=curve(line, False),
                                     stroke=Stroke(color=Color.from_hex(band["edge_ink"]),
                                                   width_mm=float(band["edge_width"]) * w * s)))
            edge_pts = [p for line in band.get("edge") or [] for p in line]
            if edge_pts:
                # under the map's own name for the motif it draws, so the score finds where it was drawn
                place("motif", map_front["edge_part"] if map_front.get("edge_part") else band["part"] + " — its edge",
                      edge_pts)
        if edges:
            # [his rules, rule 3] the band runs edge to edge: cut by the outline only, never by his front; not cut, so
            # nothing is recorded cut from it
            edge_kids.extend(children[start:])
            del children[start:]
            clipped.pop(band["part"], None)
            clipped.pop(map_front["edge_part"] if map_front.get("edge_part") else band["part"] + " — its edge", None)
            edge_parts.append({"part": band["part"], "sides": sorted(edges), "node": "band-map-%d" % i,
                               "rows": {side: (at((0, a))[1], at((0, b))[1]) for side, (a, b) in edges.items()}})
    for i, scatter in enumerate(shapes.get("scatters") or []):
        # [his answer after test day finding 3] each star its own traced outline, in its core's ink
        for j, star in enumerate(scatter.get("stars") or []):
            # [his look at 117 drawn from its map, 2026-10-02: the sparkles "match the reference exactly", never
            # "inconsistent"] each the one sparkle shape at its own centre and reach, in the pinch its motif shares
            if star.get("centre") and scatter.get("glyph"):
                (scx, scy), (shw, shh) = at(star["centre"]), star["half"]
                pinch, tip = float(scatter["glyph"]["pinch"]), float(scatter["glyph"]["tip"])
                if scatter.get("ink_lit") and scatter.get("ink_shade"):
                    # [his look: "3D"] its darker rim, its body, its lit heart — the one sparkle at three sizes
                    for suffix, share, key in MAP_SPARKLE_RELIEF:
                        children.append(Path(name="sparkle-map-%d-%d%s" % (i, j, suffix),
                                             segments=_sparkle.segments(scx, scy, shw * w * s * share, shh * h * s * share,
                                                                        pinch, tip),
                                             fill=SolidFill(color=Color.from_hex(scatter[key]))))
                    continue
                segs = _sparkle.segments(scx, scy, shw * w * s, shh * h * s, pinch, tip)
            else:
                segs = path(star["outline"], True)
            children.append(Path(name="sparkle-map-%d-%d" % (i, j), segments=segs,
                                 fill=SolidFill(color=Color.from_hex(star["ink"]))))
        pts = [p for star in scatter.get("stars") or [] for p in star["outline"]]
        if pts:
            place("motif", scatter["part"], pts)
            drawn.append(scatter["part"])
    # [his go of 2026-10-08, items 1 and 2: "Trace line art and frames in ANY colour ... Keep each motif in the picture's
    # own colour"; "smooth curves, even stroke widths ... each motif its own named layer"] each motif of line art its own
    # named group, every stroke one smooth curve at the motif's one width in its own ink; then each cleared window over
    # the strokes, filled with the surface it shows; then each frame round it, at its one width
    for i, lines in enumerate(shapes.get("lines") or []):
        prefix = "lineart-gold-map-%d" if lines.get("gold") else "lineart-map-%d"
        if lines.get("drawn_with") and (lines.get("flat") or {}).get("box"):
            # [his goal after the pitch page, B (10)] a part another part's field already draws whole
            # (``container.one_field_once``) is drawn there, once — never printed over it again
            fb = [float(v) for v in lines["flat"]["box"]]
            place("motif", lines["part"], [fb[0:2], fb[2:4]])
            drawn.append(lines["part"])
            continue
        continued = lines.get("continued")
        if continued is not None:
            # [his test blocker on design 123, 2026-10-09, (3)] a carton continuing its approved container: the
            # container's own line art in this part — its flat redraw's outlines at the container's scale, cropped to
            # the part's box, in its ink — never a stroke traced from the carton's own photo
            pb = [float(v) for v in continued["part_box"]]
            segs, _bounds = _traced_segments(continued_outlines(continued, pb, w, h), at)
            (cx0, cy0), (cx1, cy1) = at((pb[0], pb[1])), at((pb[2], pb[3]))
            segs = _reaching(segs, min(cx0, cx1), min(cy0, cy1), max(cx0, cx1), max(cy0, cy1))
            # [his second test blocker on design 123] kept clear of the small copy set over it: each line's box, padded,
            # cut out of its clip (wound against the part's box, so the clip's winding leaves it out)
            places = []
            for t in shapes.get("types") or []:
                tb = [float(v) for v in t.get("box") or []]
                if len(tb) == 4 and t.get("words") and tb[3] - tb[1] <= SMALL_COPY_SHARE:
                    pad = SMALL_COPY_PAD * (tb[3] - tb[1])
                    places.append((tb[0] - pad, tb[1] - pad, tb[2] + pad, tb[3] + pad))
            bloom = continued.get("bloom")
            rose = continued.get("rose")
            if bloom and rose:
                # [his second test blocker on design 123, (4)] the field kept clear behind the bloom
                cw, ch = (bloom[2] - bloom[0]) * BLOOM_CLEAR, (bloom[3] - bloom[1]) * BLOOM_CLEAR
                places.append((bloom[0] - cw, bloom[1] - ch, bloom[2] + cw, bloom[3] + ch))
            if map_front.get("soft_room"):
                # [his goal of 2026-10-10, item 6: "No hard rectangle cut out of the roses behind it"] the field is
                # never cut round its type on a soft front: its rooms are laid over it (``soft_rooms``), the bloom's
                # clearing kept
                places = places[len(places) - 1:] if bloom and rose else []
            # [his test findings on design 123, (4)] merged where they meet, so none cuts another back in
            clear = [seg for ring in clear_rings(places) for seg in path(ring, True)]
            children.append(Group(name=(prefix % i) + " " + str(lines["part"]), role="decoration",
                                  clip=path([[pb[0], pb[1]], [pb[2], pb[1]], [pb[2], pb[3]], [pb[0], pb[3]]], True)
                                  + clear,
                                  children=[Path(name=(prefix % i) + "-continued", segments=segs,
                                                 fill=SolidFill(color=Color.from_hex(continued["ink"]),
                                                                opacity=BLOOM_FIELD_OPACITY if bloom and rose else 1.0),
                                                 fill_rule="nonzero")]))
            if bloom and rose:
                # [his second test blocker on design 123, (4): "the big rose ... is 122's rose, whole and scaled"] the
                # container's own rose, whole, as large as its place holds BLOOM_GROW times over, centred on it
                from apps.ire.inside_print import _motif_segments, unit_motif
                unit = unit_motif(rose["cubics"], 1.0)
                bw_mm, bh_mm = (bloom[2] - bloom[0]) * w, (bloom[3] - bloom[1]) * h
                size_mm = min(bw_mm, bh_mm) * BLOOM_GROW
                (cx, cy) = at(((bloom[0] + bloom[2]) / 2.0, (bloom[1] + bloom[3]) / 2.0))
                children.append(Path(name=(prefix % i) + "-bloom", fill=SolidFill(color=Color.from_hex(continued["ink"])),
                                     fill_rule="nonzero", segments=_motif_segments(
                                         unit, cx - size_mm * s / 2.0, cy - size_mm * s / 2.0, size_mm * s)))
            place("motif", lines["part"], [[pb[0], pb[1]], [pb[2], pb[3]]],
                  ink_mm2=float(continued["ink_share"]) * (pb[2] - pb[0]) * w * (pb[3] - pb[1]) * h)
            drawn.append(lines["part"])
            continue
        flat = lines.get("flat")
        if flat is not None and flat.get("state") == "TRACED" and flat.get("art"):
            # [his goal for the pitch, 2026-10-15, A (4); B (7): "a traced motif keeps its colours"] an illustrated
            # motif drawn in its own colours, traced from its flat redraw as a lid's art is, in the part's box
            from apps.pipeline.targets.container.lid_art import art_group
            bx0, by0, bx1, by1 = (float(v) for v in flat["box"])
            (ax, ay), (ax1, ay1) = at((bx0, by0)), at((bx1, by1))
            children.append(art_group(flat["art"], ax, ay, ax1 - ax, ay1 - ay, None, prefix=(prefix % i),
                                      name=(prefix % i) + " " + str(lines["part"]), ground=False))
            if in_a_window([bx0, by0, bx1, by1], shapes.get("windows") or []):
                # [His review of 127, 130, 131 and 132, 2026-10-15, C: the designer's eye on 132] a motif printed ON a
                # window (132's lily in its cartouche) drawn over it, as a solid one is — never painted out by its fill
                over_windows.append(children.pop())
            elif _stands_alone([bx0, by0, bx1, by1]):
                standing.append(children.pop())       # [his goal after the pitch page, B (10)] over the field and rooms
            place("motif", lines["part"], [[bx0, by0], [bx1, by1]],
                  ink_mm2=float(flat.get("ink_share") or 0.0) * (bx1 - bx0) * w * (by1 - by0) * h)
            drawn.append(lines["part"])
            continue
        if flat is not None and flat.get("state") == "TRACED":
            # [his test finding on design 122's drawing, 2026-10-08, A: "Trace it as OUTLINES (not centre-lines),
            # keeping thick-and-thin strokes and the fine detail ... Wrap the clean motif onto the form at the concept's
            # layout."] the motif as its flat redraw's traced outlines, filled in its ink, in the part's box where the
            # concept lays it — its own named group, as every motif's
            segs, _bounds = _traced_segments(flat["outlines"], at)
            children.append(Group(name=(prefix % i) + " " + str(lines["part"]), role="decoration", children=[
                Path(name=(prefix % i) + "-outlines", segments=segs, fill=SolidFill(color=Color.from_hex(flat["ink"])),
                     fill_rule="nonzero")]))
            bx0, by0, bx1, by1 = (float(v) for v in flat["box"])
            if in_a_window([bx0, by0, bx1, by1], shapes.get("windows") or []):
                over_windows.append(children.pop())       # [his review of 132, C] over the window it is printed on
            elif _stands_alone([bx0, by0, bx1, by1]):
                standing.append(children.pop())       # [his goal after the pitch page, B (10)] over the field and rooms
            place("motif", lines["part"], [[bx0, by0], [bx1, by1]],
                  ink_mm2=float(flat["ink_share"]) * (bx1 - bx0) * w * (by1 - by0) * h)
            drawn.append(lines["part"])
            continue
        if lines.get("undrawn"):
            # [his finding, A1: "Never trace motifs from the concept photo."] a motif with no flat redraw to trace, or
            # one not whole, is left undrawn — said by the drawing's stop (``flat_motif_codes``)
            continue
        stroke = Stroke(color=Color.from_hex(lines["ink"]), width_mm=float(lines["width"]) * w * s)
        children.append(Group(name=(prefix % i) + " " + str(lines["part"]), role="decoration", children=[
            Path(name=(prefix % i) + "-%d" % j, segments=curve(st["points"], bool(st["closed"])), stroke=stroke)
            for j, st in enumerate(lines.get("strokes") or []) if len(st["points"]) >= 2]))
        place("motif", lines["part"], [p for st in lines.get("strokes") or [] for p in st["points"]],
              ink_mm2=float(lines["width"]) * w * sum(
                  math.hypot((b[0] - a[0]) * w, (b[1] - a[1]) * h)
                  for st in lines.get("strokes") or [] for a, b in zip(st["points"], st["points"][1:])))
        drawn.append(lines["part"])
    if map_front.get("soft_room") and not face:
        # [His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 6: "FRONT TEXT: "Rose Blossom" in the granted face closest to the concept's soft rounded sans (Quicksand or Montserrat), ONE colour, never two pinks or the heavy house bold; "Hand Cream" in the same family, lighter; Arabic in a matching sans (Tajawal or Cairo), not Naskh. No hard rectangle cut out of the roses behind it; soft breathing room as the concept shows, and the soft oval cartouche behind the BBROSE logo."]
        # soft breathing room round the front's type, over every field drawn above
        # [His review of 127, 130, 131 and 132, 2026-10-15, C] never round a line a window holds: the window is its
        # room — 132's haze ran out past its cartouche's gold frame over the tiles
        children.extend(soft_rooms([t for t in shapes.get("types") or []
                                    if not (t.get("box") and in_a_window(t["box"], shapes.get("windows") or []))],
                                   map_front.get("ground") or map_front.get("room_ground"), w * s, h * s, ox, oy))
    # [his goal after the pitch page, B (10)] each motif redrawn flat standing in one place, over the field and its rooms
    children.extend(standing)
    marks = [m["box"] for m in shapes.get("marks") or [] if m.get("box")]
    for i, window in enumerate(shapes.get("windows") or []):
        held = any(float(window["box"][0]) <= float(b[0]) and float(window["box"][1]) <= float(b[1])
                   and float(b[2]) <= float(window["box"][2]) and float(b[3]) <= float(window["box"][3]) for b in marks)
        if map_front.get("soft_room") and held and window.get("shape") == "ellipse":
            # [his goal of 2026-10-10, item 6: "the soft oval cartouche behind the BBROSE logo"] the window the mark
            # stands in, a soft oval: its own fill, its edge fading out — [his goal of 2026-10-13, (8): "Glow is a real
            # soft blur, never a stack of hard bands"] one smooth mesh ring from its own colour to the ground, never
            # CARTOUCHE_RINGS rings stacked
            ground = map_front.get("ground") or map_front.get("room_ground")
            if ground:
                centre = at(window["centre"])
                half = (float(window["half"][0]) * w * s, float(window["half"][1]) * h * s)
                ring, strengths = _LG.ring_patches(centre, half, float(window["angle"]), 1.0 + CARTOUCHE_SOFT,
                                                   window["fill"])
                xs = [p[k] for p in ring for k in (0, 2, 4, 6)]
                ys = [p[k] for p in ring for k in (1, 3, 5, 7)]
                children.append(Path(name="window-map-%d-soft" % i, fill=MeshFill(
                    patches=ring, alphas=strengths,
                    blur=_LG.ring_blur(centre, half, float(window["angle"]), 1.0 + CARTOUCHE_SOFT,
                                       window["fill"])), segments=[
                    MoveTo(x=min(xs), y=min(ys)), LineTo(x=max(xs), y=min(ys)), LineTo(x=max(xs), y=max(ys)),
                    LineTo(x=min(xs), y=max(ys)), ClosePath()]))
        if window.get("shape") == "arch":
            # [his goal of 2026-10-13, (7)-(9)] under its own arch: its glow outside its rim a smooth mesh, its field a
            # smooth mesh, its rim one even line in its ink over both
            line = {"kind": "arch", "points": window["points"], "width": window["rim"]["width"]}
            x00, y00 = at((0.0, 0.0))
            if window.get("glow"):
                gl = window["glow"]
                # fading to nothing over what is drawn beneath it — never to a colour read beside it in the concept
                parts = _LG.glow_parts(line, x00, y00, w * s, h * s, gl["bands"], sides=(-1.0,))
                for n, part in enumerate(parts):
                    gx0, gy0, gx1, gy1 = part["box"]
                    children.append(Path(name="window-glow-map-%d-%d" % (i, n),
                                         fill=MeshFill(patches=part["patches"], alphas=part["alphas"],
                                                       blur=part["blur"]),
                                         segments=[MoveTo(x=gx0, y=gy0), LineTo(x=gx1, y=gy0), LineTo(x=gx1, y=gy1),
                                                   LineTo(x=gx0, y=gy1), ClosePath()]))
            outline = _LG.segments(line, x00, y00, w * s, h * s) + [ClosePath()]
        else:
            outline = _outline_segments(window, at, w * s, h * s)
        fb = (window.get("field") or {}).get("box")
        # [his goal of 2026-10-13, (7): "matched to the concept's shape"] the field out to its outline's own edges, the
        # outline cutting it — the concept's lavender rim to rim, never a box inside the arch
        oxs = [v for g in outline for v in (getattr(g, "x", None), getattr(g, "x1", None), getattr(g, "x2", None))
               if v is not None]
        oys = [v for g in outline for v in (getattr(g, "y", None), getattr(g, "y1", None), getattr(g, "y2", None))
               if v is not None]
        grid = (_LG.field_grid(window["field"]["rows"], at(fb[:2])[0], at(fb[:2])[1], (fb[2] - fb[0]) * w * s,
                               (fb[3] - fb[1]) * h * s, reach=[min(oxs), min(oys), max(oxs), max(oys)])
                if window.get("field") else None)
        fill = (MeshFill(patches=_LG.patches_of_grid(grid), grid=grid) if grid is not None
                else SolidFill(color=Color.from_hex(window["fill"])))
        children.append(Path(name="window-map-%d" % i, segments=outline, fill=fill))
        if window.get("shape") == "arch":
            rim = window["rim"]
            children.append(Path(name=("window-rim-gold-map-%d" if rim.get("gold") else "window-rim-map-%d") % i,
                                 segments=_LG.segments(line, x00, y00, w * s, h * s),
                                 stroke=Stroke(color=Color.from_hex(rim["ink"]), width_mm=float(rim["width"]) * w * s)))
        place("motif", window["part"], [window["box"][0:2], window["box"][2:4]])
        drawn.append(window["part"])
    for i, frame in enumerate(shapes.get("frames") or []):
        children.append(Path(name=("frame-gold-map-%d" if frame.get("gold") else "frame-map-%d") % i,
                             segments=_outline_segments(frame, at, w * s, h * s),
                             stroke=Stroke(color=Color.from_hex(frame["ink"]), width_mm=float(frame["width"]) * w * s)))
        fb = frame["box"]
        place("rule", frame["part"], [fb[0:2], fb[2:4]],
              ink_mm2=float(frame["width"]) * w * 2.0 * ((fb[2] - fb[0]) * w + (fb[3] - fb[1]) * h))
        drawn.append(frame["part"])
    children.extend(over_windows)          # [his goal after the pitch page, 2026-10-15, A (4)] over its window
    for i, rule in enumerate(shapes.get("rules") or []):
        start = len(children)
        # [his rules, rule 3] a rule the picture runs edge to edge drawn past the sides it reaches (its drawn box)
        x0, y0, x1, y1 = rule["drawn_box"] if "drawn_box" in rule else rule["box"]
        lit = bool(rule.get("ink_lit") and rule.get("ink_shade"))
        children.append(Rect(name="rule-map-%d" % i, x=at((x0, y0))[0], y=at((x0, y0))[1], w=(x1 - x0) * w * s,
                             h=(y1 - y0) * h * s,
                             fill=SolidFill(color=Color.from_hex(rule["ink_shade"] if lit else rule["ink"]))))
        if lit:
            # [his look: "3D"] its lit middle, the middle half of its height
            children.append(Rect(name="rule-map-%d-lit" % i, x=at((x0, y0))[0], y=at((x0, y0))[1] + (y1 - y0) * h * s / 4.0,
                                 w=(x1 - x0) * w * s, h=(y1 - y0) * h * s / 2.0,
                                 fill=SolidFill(color=Color.from_hex(rule["ink_lit"]))))
        x0, y0, x1, y1 = rule["box"]
        place("rule", rule["part"], [(x0, y0), (x1, y1)])
        drawn.append(rule["part"])
        if rule.get("edges"):
            edge_kids.extend(children[start:])
            del children[start:]
            clipped.pop(rule["part"], None)
            edge_parts.append({"part": rule["part"], "sides": list(rule["edges"]), "node": "rule-map-%d" % i,
                               "rows": {side: None for side in rule["edges"]}})
    # [his answers of 2026-10-02 (a18911a), answer 2: "Gold in the picture is foil ... That is the rule for every design"]
    # the nodes drawn from the picture's gold — every part the tracers found by its gold: the band's raised edge (its
    # gold layers) or its stroked edge, the stars, the rule
    gold_nodes = [getattr(k, "name", "") for k in children + edge_kids
                  if str(getattr(k, "name", "")).startswith(MAP_GOLD_PREFIXES)]
    # [the clean-up's wiring check, 2026-10-04, its finding W1] the motif this front draws is said only where the map
    # names one — a band's traced edge (its drips) or the scattered shapes; a picture that prints neither expects none,
    # and the motif check then reads the concept's own motif words (container_motif_fidelity), never an absent motif
    motif = (bool(shapes.get("scatters")) or bool(shapes.get("lines"))
             or any(b.get("edge") for b in shapes.get("bands") or []))
    record = {"drawn": drawn, "motif_prefixes": list(MAP_MOTIF_PREFIXES) if motif else [], "boxes": boxes,
              "gold_nodes": gold_nodes,
              "clipped_to_his_front_mm": clipped, "drips": [b.get("drips") for b in shapes.get("bands") or []],
              "stars": [sc.get("count") for sc in shapes.get("scatters") or []],
              "source_sha256": shapes.get("source_sha256"), "params": (shapes.get("params") or {}).get("version")}
    # [his look at 117 drawn from its map, 2026-10-02: the band, the rule and the outer drips printed past the tube's
    # outline] cut to the product's own drawn outline as well as to his confirmed front: nothing prints past its edge
    record["clipped_to"] = "his confirmed front and the product's drawn outline"
    within = Group(name=MAP_WITHIN_OUTLINE, role="decoration", children=children,
                   clip=_scaled(backbone.silhouette, s, ox, oy))
    if edge_kids:
        # [his rules, 2026-10-02, rule 3: "EDGE TO EDGE MEANS BLEED ... never a gap (117's left gap)"] the parts the
        # picture runs edge to edge, cut by the drawn outline only, and how far past it each runs on its rows — the
        # bleed the drawing gives it, measured against the house's own (DEFAULT_BLEED_MM); his front still bounds the rest
        from apps.dielines.constants import DEFAULT_BLEED_MM
        sil = _scaled(backbone.silhouette, s, ox, oy)
        by_name = {getattr(k, "name", ""): k for k in edge_kids}
        for part in edge_parts:
            node = by_name.get(part["node"])
            past = _past_the_outline(node, sil, part.pop("rows")) if node is not None else None
            part["past_the_outline_mm"] = None if past is None else round(past / s, 2)
            part["bleed_mm"] = DEFAULT_BLEED_MM
            part["into_the_bleed"] = past is not None and past / s >= DEFAULT_BLEED_MM
        record["edge_to_edge"] = edge_parts
        record["clipped_to"] = ("his confirmed front and the product's drawn outline; the parts the picture runs edge "
                                "to edge, the drawn outline only")
        return (Group(name="motif-map-front", role="decoration", children=[
            Group(name=MAP_EDGE_TO_EDGE, role="decoration", children=edge_kids, clip=sil),
            Group(name=MAP_WITHIN_HIS_FRONT, role="decoration", children=[within],
                  clip=rect_clip(ox + zx * s, oy + zy * s, zw * s, zh * s))]), places, record)
    # [found on 117 redrawn, 2026-10-02: named "MAP_FRONT", the design graph's census — which counts the front's artwork
    # as the groups named "motif-" — read the drawn drips, rule and stars as a zone-only placeholder and the quality
    # check failed it] the front's motif, named as every front's motif is
    return (Group(name="motif-map-front", role="decoration", children=[within],
                  clip=rect_clip(ox + zx * s, oy + zy * s, zw * s, zh * s)), places, record)


#: the names a front's lettering is drawn under when it is traced or set as outlines rather than typed — read as type
#: by the census (``_front_type_census``), never as decoration
LETTERING_NODE_PREFIXES = ("product-name-traced", "front-lettering-", "script-lettering-")


def _front_type_census(doc: Document) -> dict:
    """[His answer of 2026-10-05, W6: "type-only is a real design style; refuse only real placeholder text."] The
    front's own type, counted where the emitter drew it — the container view outside every surface group (never the
    strip's diagram, a true-scale back panel or the sheet's furniture) — as live runs with words and as lettering drawn
    in outline; and every run read for the tokens that are never product copy (``container_typography_metrics``'s
    list, the placeholder check's own). The quality check reads it to tell a type-only front from a zone-only fill."""
    from apps.ire.container_composition_metrics import _emitted_surface
    from apps.ire.container_typography_metrics import _PLACEHOLDER_MARKERS, _marker_in, container_view_text_runs
    view, _strip = container_view_text_runs(doc)
    runs = [n for n, surface in view if surface is None and str(getattr(n, "text", "")).strip()]
    parents = {id(node): parent for node, parent in doc.walk()}
    lettering = [n for n, _ in doc.walk() if str(getattr(n, "name", "")).startswith(LETTERING_NODE_PREFIXES)
                 and _emitted_surface(n, parents)[0] is None]
    placeholders = [{"node_name": str(n.name), "text": str(n.text), "marker": _marker_in(str(n.text), _PLACEHOLDER_MARKERS)}
                    for n in runs if _marker_in(str(n.text), _PLACEHOLDER_MARKERS) is not None]
    return {"front_type": {"runs": len(runs), "lettering": len(lettering), "placeholder_runs": placeholders}}


def container_design_graph_record(doc: Document, *, zones_consumed: list[str],
                                  mode: str) -> dict:
    """container_design_graph/1.0 census over the emitted native Document
    (§4). The decorative-raster count must be 0 — the reference photo and the
    controlled logo fallback are the only permitted Image nodes and are
    counted separately, never as decoration.

    [The owner's second answer of 2026-09-25: a mark drawn from its approved vector master is neither — it is counted
    as ``logo_vector_marks``, a key the census carries only when such a mark is drawn, so a census without one is
    what it always was.]"""
    live_text = sum(1 for n, _ in doc.walk() if n.type == "text")
    vector_paths = sum(1 for n, _ in doc.walk() if n.type in ("path", "rect"))
    images = [(n, p) for n, p in doc.walk() if n.type == "image"]
    reference_rasters, logo_rasters, decorative_rasters = 0, 0, 0
    for node, parent in images:
        nm = str(getattr(node, "name", "")).lower()
        if "reference" in nm or (parent and parent.name == "Reference"):
            reference_rasters += 1
        elif "logo" in nm:
            logo_rasters += 1
        else:
            decorative_rasters += 1
    vector_marks = sum(1 for n, _ in doc.walk() if _brand_mark.is_mark(n))
    # per-surface artwork group inventory (2B-2A §9: additive → /1.1)
    surface_groups = sorted({
        str(n.name).split(SURFACE_GROUP_PREFIX, 1)[1]
        for n, _ in doc.walk()
        if n.type == "group" and str(getattr(n, "name", "")).startswith(
            SURFACE_GROUP_PREFIX)})
    motif_groups = sorted({
        str(n.name) for n, _ in doc.walk()
        if n.type == "group" and str(getattr(n, "name", "")).startswith("motif-")})
    return {
        **_front_type_census(doc),
        "schema_version": "container_design_graph/1.1",
        "mode": mode,
        "archetype": doc.metadata.get("archetype", ""),
        "zones_consumed": list(zones_consumed),
        "primitives": {"live_text": live_text, "vector_paths": vector_paths,
                       "reference_rasters": reference_rasters,
                       "logo_rasters": logo_rasters,
                       **({"logo_vector_marks": vector_marks} if vector_marks else {})},
        "decorative_raster_count": decorative_rasters,
        "logo_zone_used": doc.metadata.get("logo_zone_used", ""),
        "surface_groups": surface_groups,
        "surface_inventory": doc.metadata.get("surface_inventory", {}),
        "motif_groups": motif_groups,
        "motif_family": doc.metadata.get("motif_family"),
        "front_back_relationship": doc.metadata.get("front_back_relationship", {}),
    }


#: [His goal after the pitch page, 2026-10-15, A (2)] the closure parts' names, by the key their look is under
CLOSURE_PART_NAMES = {"cap": "cap", "bulb": "closure-bulb", "collar": "closure-collar"}


def _with_gold_closure(record: dict, looks: Optional[dict]) -> dict:
    """[His goal after the pitch page, 2026-10-15, A (2): "gold goes on the foil plate"] the map front's record with each
    closure part drawn in the picture's gold among its gold nodes — on the foil plate as every gold part the map traced
    (``container_finishes.apply``'s ``gold_as_drawn``); the plate is the part's shape, its gradient only its look."""
    gold = [CLOSURE_PART_NAMES[k] for k, look in (looks or {}).items() if look.get("metal") == "gold"
            and k in CLOSURE_PART_NAMES]
    if not gold:
        return record
    return dict(record, gold_nodes=list(record.get("gold_nodes") or []) + [n for n in gold
                                                                          if n not in (record.get("gold_nodes") or [])])


def compose_container_graph(
    backbone: ContainerBackbone, *,
    reference_path: Optional[str] = None,
    label_path: Optional[str] = None,
    logo_path: Optional[str] = None,
    colors: Optional[dict] = None,
    product_name: str = "",
    sku: str = "",
    zones: Optional[list] = None,
    name_lines: Optional[list] = None,
    native: bool = False,
    motif_spec: Optional[dict] = None,
    transparency: Optional[dict] = None,
    material_stack: Optional[dict] = None,
    hierarchy_lines: Optional[list] = None,
    back_sections: Optional[list] = None,
    concept_front: Optional[dict] = None,
    # [his test day finding 3, 2026-09-30] where the concept's upper colour field meets its lower, as a share of the
    # height; the lower field (``colors["body_lower"]``) drawn from there to the foot, inside the body's outline
    body_split: Optional[float] = None,
    # [his test day finding 3, 2026-09-30] the concept's words place the mark in the upper field and the name in the
    # lower: the mark centred in the part of the front above ``body_split``, the name stack begun below it
    front_fields: bool = False,
    # [his test day finding 3, 2026-09-30] the label IS the front he confirmed (`container_front_label/1.0`), so the
    # mark stands below the room the concept's own elements need above it
    label_is_front: bool = False,
    # THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    # switch the mark to it so gold foil can print." The approved vector master (apps/ire/brand_mark.py), handed in
    # by a caller that found one on file; None — every call before this parameter — draws the raster as before.
    logo_master=None,
    # [his answer after test day finding 3, 2026-09-30, transcribed at 23d4375: "...and the same way, draw it"; the layout
    # "exactly the picture. Not the rule"] ``{"shapes": container_design_shapes/1.0}``: the parts the concept's map
    # traced, drawn at the picture's places in place of the motif the concept's words asked for (``_map_front_group``)
    map_front=None,
    # [his rules for cloning a design from a picture, 2026-10-02, rule 5: "THE BACK IS DRAWN"; §W1(a): "a full-scale back
    # panel at true dimensions with untruncated copy"] ``{"methods_record": …}`` — the back copy (``back_sections``) is
    # drawn as well at the size it prints, from the confirmed BACK_PRINT_ZONE (`back_panel.compose_back_panel`), below
    # the sheet's spec, the sheet grown to hold it; None — every call before this parameter — draws the strip only
    back_panel: Optional[dict] = None,
    # … and the phrase the brief's back copy names its batch code's place in: the confirmed code zone drawn as its window
    batch_code_place: Optional[str] = None,
    # [His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 2: "A palette design must include the whole palette: the lid AND the open tray with its 18 pans in 3 rows of 6, each shade name from my brief printed under its pan."]
    # ``{"tray": palette_tray.read_tray(...), "ground_hex", "ink_hex", "edge_hexes"}`` — the open tray's printed insert
    # drawn at the size it prints, below everything else on the sheet, the sheet grown to hold it; None draws none
    open_tray: Optional[dict] = None,
    # [His goal after the pitch page, 2026-10-15, A (2)] ``{"cap": look, "bulb": look}`` — a metal closure part's light
    # as its concept shows it (the container target's ``closure_looks_of``); None — every call before it — draws each flat
    closure_looks: Optional[dict] = None,
    # [His review of 127, 130, 131 and 132, 2026-10-15, D (11)] ``[{"at", "hex", "width_share"}]`` — the seams its concept
    # shows across its closure (the container target's ``closure_seams_of``); None — every call before it — draws none
    closure_seams: Optional[list] = None,
) -> Document:
    colors = colors or {}
    body_c = Color.from_hex(colors.get("body", _DEFAULT_BODY))
    cap_c = Color.from_hex(colors.get("cap", _DEFAULT_CAP))
    # 2B-2: native mode consumes confirmed zones and emits native artwork —
    # the raster label is never placed (decorative raster count 0).
    native = native or bool(zones)
    # 2B-2A: the SUPPORTED motif renders through the closed design-language
    # engine; NONE/REVIEW_REQUIRED render no motif (fail-closed handled upstream).
    motif_language = None
    if native and motif_spec:
        from apps.ire.container_motif import language_for_spec
        motif_language = language_for_spec(motif_spec)

    layout = _sheet_layout(backbone)
    _k = layout["k"]
    s, ox, oy = _fit(backbone.width_mm, backbone.height_mm,
                     layout["con_box"])

    def px(x):  # backbone-local x → sheet
        return ox + x * s

    def py(y):
        return oy + y * s

    children: list = []

    # §BH70(1): the room the sheet's own words have — CHROME_ROOM of the page, centred on it
    _room_mm = layout["page_w"] * CHROME_ROOM
    _room_x0_mm = (layout["page_w"] - _room_mm) / 2

    # --- title -------------------------------------------------------------
    if product_name:
        _title = product_name.upper()
        children.append(centered_text(
            "sheet-title", _title, layout["page_w"] / 2,
            layout["title_y"], chrome_size_pt(_title, max(7.0, 20 * _k), _room_mm), _INK, font="bold"))

    # --- Reference group (flagged raster exception, clearly labelled) ------
    _ref_box = layout["ref_box"]
    _ref_label = "REFERENCE — not final artwork"
    _ref_label_pt = chrome_size_pt(_ref_label, max(3.0, 6 * _k), _room_mm)
    # §BH70(1): centred on its box as always, but kept on the page — on a slim sheet the box is narrower than the label
    _ref_half_mm = name_width_estimate_mm(_ref_label, _ref_label_pt, upper=True) / 2
    _ref_cx = min(max(_ref_box[0] + _ref_box[2] / 2, _room_x0_mm + _ref_half_mm),
                  _room_x0_mm + _room_mm - _ref_half_mm)
    ref_children: list = [centered_text(
        "reference-label", _ref_label, _ref_cx, _ref_box[1] - 4 * _k,
        _ref_label_pt, _INK, font="bold")]
    rx, ry, rw, rh = _ref_box
    ref_img = image_node("reference-photo", reference_path, rx, ry, rw, rh,
                         clip=rect_clip(rx, ry, rw, rh))
    if ref_img is not None:
        ref_children.append(ref_img)
    else:
        ref_children.append(Rect(name="reference-placeholder", x=rx, y=ry,
                                 w=rw, h=rh, stroke=Stroke(color=_INK, width_mm=0.3)))
    children.append(Group(name="Reference", role="generic", children=ref_children))

    # --- Container group (native vector structure) -------------------------
    sil = _scaled(backbone.silhouette, s, ox, oy)
    if material_stack and backbone.collar_region is not None:
        # 2C-2E §10: the frosted dropper bottle as INDEPENDENT editable
        # material objects — never one opaque fill. GLASS_HIGHLIGHT is a
        # NONPRINTING visualization object (metadata below keeps it out of
        # print separations by contract).
        frost = float(material_stack.get("frost_intensity", 0.7))
        trans = float(material_stack.get("translucency", 0.35))
        body_hex = material_stack.get("body_color", "#D8BEB8")
        fill_hex = material_stack.get("product_color", "#C9A6A0")
        collar_c = Color.from_hex(material_stack.get("collar_color",
                                                     "#B76E79"))
        bulb_c = Color.from_hex(material_stack.get("bulb_color", "#3A2A2C"))
        base_h = max(float(backbone.base_band_mm), 1.0) * s
        body_top = oy + (backbone.height_mm
                         - _body_height(backbone)) * s
        body_bottom = oy + backbone.height_mm * s
        inset = backbone.width_mm * s * 0.07
        con_children = [
            Path(name="GLASS_OUTER_WALL", segments=sil,
                 fill=SolidFill(color=Color.from_hex(body_hex),
                                opacity=round(min(trans, 0.35), 3))),
            Path(name="FROST_TREATMENT", segments=sil,
                 fill=SolidFill(color=Color.from_hex("#FFFFFF"),
                                opacity=round(0.12 + frost * 0.22, 3))),
            Rect(name="PRODUCT_FILL_APPEARANCE",
                 x=ox + inset, y=body_top + 2.0,
                 w=backbone.width_mm * s - 2 * inset,
                 h=max(body_bottom - body_top - base_h - 2.0, 1.0),
                 fill=SolidFill(color=Color.from_hex(fill_hex),
                                opacity=0.45)),
            Rect(name="GLASS_BASE_THICKNESS",
                 x=ox + inset * 0.5, y=body_bottom - base_h,
                 w=backbone.width_mm * s - inset,
                 h=base_h,
                 fill=SolidFill(color=Color.from_hex(body_hex),
                                opacity=0.30)),
            Rect(name="GLASS_HIGHLIGHT",
                 x=ox + backbone.width_mm * s * 0.16, y=body_top + 2.0,
                 w=backbone.width_mm * s * 0.08,
                 h=max(body_bottom - body_top - base_h - 2.0, 1.0),
                 fill=SolidFill(color=Color.from_hex("#FFFFFF"),
                                opacity=0.25)),
            Path(name="COLLAR_ROSE_GOLD",
                 segments=_scaled(backbone.collar_region, s, ox, oy),
                 fill=SolidFill(color=collar_c)),
            Path(name="BULB_DARK_PLUM",
                 segments=_scaled(backbone.bulb_region, s, ox, oy),
                 fill=SolidFill(color=bulb_c)),
        ]
    elif transparency:
        # 2B-3V-CORR-3 §6 / CORR-4: a TRANSPARENT container never collapses
        # into one opaque body fill — the wall and the visible internal
        # product colour are SEPARATE editable objects with named swatch
        # roles, and the fill sits INSIDE the body (below the cap) with a
        # glass highlight so the wall visibly reads as clear.
        product_c = Color.from_hex(
            (transparency.get("product_color") or "#F2C4CE"))
        cap_bottom = max((float(getattr(seg, "y", 0) or 0)
                          for seg in backbone.cap_region), default=0.0)
        fill_top = oy + (cap_bottom + backbone.height_mm * 0.015) * s
        fill_h = oy + backbone.height_mm * s * 0.985 - fill_top
        # [his test day finding 3, 2026-09-30: a tube drawn standing on its cap (`silhouettes._stood_on_closure`) —
        # its body is ABOVE the cap, and the fill measured below it was a 1 mm sliver]
        cap_top = min((float(getattr(seg, "y", 0) or 0) for seg in backbone.cap_region
                       if hasattr(seg, "y")), default=0.0)
        if cap_top > backbone.height_mm / 2.0:
            fill_top = oy + backbone.height_mm * 0.015 * s
            fill_h = oy + (cap_top - backbone.height_mm * 0.015) * s - fill_top
        inset = backbone.width_mm * s * 0.06
        con_children = [
            Path(name="body-transparent-wall", segments=sil,
                 fill=SolidFill(color=Color.from_hex("#FDF7F2"),
                                opacity=0.10)),
            Rect(name="product-peach-rose-fill",
                 x=ox + inset, y=fill_top,
                 w=backbone.width_mm * s - 2 * inset, h=max(fill_h, 1.0),
                 fill=SolidFill(color=product_c, opacity=0.45)),
            Rect(name="glass-highlight",
                 x=ox + backbone.width_mm * s * 0.16, y=fill_top,
                 w=backbone.width_mm * s * 0.09, h=max(fill_h, 1.0),
                 fill=SolidFill(color=Color.from_hex("#FFFFFF"),
                                opacity=0.28)),
            Path(name="cap", segments=_scaled(backbone.cap_region, s, ox, oy),
                 fill=_closure_fill(cap_c.to_hex(), (closure_looks or {}).get("cap"),
                                    _scaled(backbone.cap_region, s, ox, oy))),
        ]
    else:
        con_children = [Path(name="body", segments=sil, fill=SolidFill(color=body_c))]
        if body_split is not None and colors.get("body_lower"):
            # [his test day finding 3, 2026-09-30: the concept's two colour fields] the lower field, from the split to
            # the foot, inside the body's own outline — the cap drawn over it
            con_children.append(Group(name="body-fields", role="structure", clip=sil, children=[Rect(
                name="body-lower-field", x=ox, y=oy + body_split * backbone.height_mm * s,
                w=backbone.width_mm * s, h=(1.0 - body_split) * backbone.height_mm * s,
                fill=SolidFill(color=Color.from_hex(colors["body_lower"])))]))
        con_children.append(Path(name="cap", segments=_scaled(backbone.cap_region, s, ox, oy),
                                 fill=_closure_fill(cap_c.to_hex(), (closure_looks or {}).get("cap"),
                                                    _scaled(backbone.cap_region, s, ox, oy))))
    # VQR-1: a dropper backbone carries a REAL bulb region — the accepted
    # assembly renders as an independent editable object; the rejected
    # "rectangular gold block" cap can no longer stand in for a dropper
    if backbone.bulb_region is not None and not any(
            getattr(c, "name", "") in ("closure-bulb", "BULB_DARK_PLUM")
            for c in con_children):
        # [His goal after the pitch page, 2026-10-15, A (3): "128's grey-block dropper"] its colour read on its own part of
        # the concept (``colors["bulb"]``), its light drawn as the concept shows it where it is metal — never a stock
        # plum; where no part of the picture was read for it, the closure's own colour
        _bulb_hex = colors.get("bulb") or cap_c.to_hex()
        con_children.append(Path(
            name="closure-bulb",
            segments=_scaled(backbone.bulb_region, s, ox, oy),
            fill=_closure_fill(_bulb_hex, (closure_looks or {}).get("bulb"),
                               _scaled(backbone.bulb_region, s, ox, oy))))
    if closure_seams and backbone.cap_region:
        # [His review of 127, 130, 131 and 132, 2026-10-15, D (11); the lead's look at 135: its flip-top "a flat yellow
        # rectangle"] each seam its concept shows across its closure, a line where the photo shows it, in the colour it
        # shows, inside the closure's own outline
        _seam_clip = _scaled(backbone.cap_region, s, ox, oy)
        con_children.append(Group(name="closure-seams", role="structure", clip=_seam_clip, children=[
            Path(name="closure-seam-%d" % i, segments=[
                MoveTo(x=ox, y=oy + float(seam["at"]) * backbone.height_mm * s),
                LineTo(x=ox + backbone.width_mm * s, y=oy + float(seam["at"]) * backbone.height_mm * s)],
                 stroke=Stroke(color=Color.from_hex(seam["hex"]),
                               width_mm=max(0.15, float(seam["width_share"]) * backbone.height_mm * s)))
            for i, seam in enumerate(closure_seams)]))
    _join = closure_foot_share(backbone) if backbone.cap_region else None
    if _join is not None and not material_stack:
        # [his last goal before the pitch, 2026-10-16, Step 2: "the hero is never lost: caps and closures" — 127's brown
        # cap on its brown drip band read as one shape, the cap gone] where the cap meets the body, the parting line its
        # concept shows: a fine line across the body at the drawn cap's foot, in a deeper shade of the cap's own colour
        _y = oy + _join * backbone.height_mm * s
        _deep = Color(r=cap_c.r * JOIN_SHADE, g=cap_c.g * JOIN_SHADE, b=cap_c.b * JOIN_SHADE)
        con_children.append(Group(name="closure-join", role="structure", clip=_scaled(backbone.silhouette, s, ox, oy),
                                  children=[Path(name="closure-join-line", segments=[
                                      MoveTo(x=ox, y=_y), LineTo(x=ox + backbone.width_mm * s, y=_y)],
                                      stroke=Stroke(color=_deep, width_mm=JOIN_WIDTH_MM))]))
    if backbone.collar_region is not None and backbone.bulb_region is None and not material_stack:
        # [His review of 127, 130, 131 and 132, 2026-10-15, D (11): "gold collar"; the lead's look at 134's flacon] a
        # cap's collar its concept shows as its own part, drawn as it: its colour read on its own part of the concept
        # (``colors["collar"]``), its light as the concept shows it where it is metal — under the cap, over the body
        _collar_hex = colors.get("collar") or cap_c.to_hex()
        con_children.append(Path(
            name="closure-collar",
            segments=_scaled(backbone.collar_region, s, ox, oy),
            fill=_closure_fill(_collar_hex, (closure_looks or {}).get("collar"),
                               _scaled(backbone.collar_region, s, ox, oy))))
    if backbone.border_region is not None:
        # [His goal after the pitch page, 2026-10-15, A (3): "131 ... with a cream border"] the rim its concept shows round
        # the lid's face, in the rim's own colour, over the lid
        con_children.append(Path(name="lid-border", segments=_scaled(backbone.border_region, s, ox, oy),
                                 fill=SolidFill(color=Color.from_hex(colors.get("border") or colors.get("body")
                                                                     or _DEFAULT_BODY)),
                                 fill_rule="evenodd"))
    lx, ly, lw, lh = backbone.label_zone
    placements: list = []
    map_front_record = None
    map_mark = None
    # [the clean-up's wiring check, its finding W11] a wrap label as the front view draws it (``_front_view_zone``)
    front_zone = _front_view_zone(_front_zone(zones), backbone) if native else None
    if front_zone is not None and (map_front or {}).get("face_art"):
        # [his goal for the pitch, 2026-10-15, A (4), B (9)] a face drawn from its concept prints where its concept prints
        # — the whole face, from below an unprinted closure down: its art, its type and its mark at the picture's places
        # the whole product: the art begins below the closure; the type and the mark stand where the picture prints
        # them — a mark on its lid stays on its lid
        front_zone = dict(front_zone, x=0.0, y=0.0, width=backbone.width_mm, height=backbone.height_mm)
    concept_front_record = None
    # [his final goal, 2026-10-05, A: "The safe margin rule applies to containers too (117 included): text, logos and
    # key elements stay inside it; backgrounds and patterns still run into the bleed."] the picture's parts fitted inside
    # the front zone's own safe margin before any is placed — the mark first among them; a band or rule the picture runs
    # edge to edge still runs out (his answer of 2026-10-01, "the picture wins", is replaced for these)
    map_safe = None
    # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2): "ONE ENGINE"] a face drawn from its concept's map and
    # its art: the map read from the lid stood square, so its fractions are of the lid's own face (the backbone's
    # cap_region), never the product's box beside it — every part of the map laid on that face (``_mbb``, ``_mox``,
    # ``_moy``, the zone moved with it), the box its art covers
    _cf_face = (concept_front or {}).get("face") if native and front_zone else None
    lid_map = bool(native and _cf_face and _cf_face.get("state") == "MAP" and map_front and map_front.get("lid_art"))
    _mbb, _mox, _moy, _mzone, _lid_box = backbone, ox, oy, front_zone, None
    if lid_map:
        from dataclasses import replace as _replace_bb
        _lid_pts = [(float(getattr(sg, "x")), float(getattr(sg, "y"))) for sg in (backbone.cap_region or [])
                    if hasattr(sg, "x") and hasattr(sg, "y")]
        _lid_box = (min(x for x, _y in _lid_pts), min(y for _x, y in _lid_pts),
                    max(x for x, _y in _lid_pts) - min(x for x, _y in _lid_pts),
                    max(y for _x, y in _lid_pts) - min(y for _x, y in _lid_pts))
        _mbb = _replace_bb(backbone, width_mm=_lid_box[2], height_mm=_lid_box[3])
        _mox, _moy = ox + _lid_box[0] * s, oy + _lid_box[1] * s
        _mzone = dict(front_zone, x=float(front_zone["x"]) - _lid_box[0], y=float(front_zone["y"]) - _lid_box[1])
    if map_front and front_zone:
        from apps.ire.compose import inside_safe
        _m = float(_mzone.get("safe_margin_mm") or 0.0)
        _zx, _zy, _zw, _zh = (float(_mzone[k]) for k in ("x", "y", "width", "height"))
        map_front, map_safe = inside_safe(map_front, _mbb.width_mm, _mbb.height_mm, _m, product_name,
                                          rect=(_zx + _m, _zy + _m, _zx + _zw - _m, _zy + _zh - _m))
    # computed BEFORE the decoration, because the front keep-out has to know
    # where the mark's bottom edge is before any text is placed. Same box is
    # read again below to emit the node, so the keep-out and the mark cannot
    # disagree about where the mark is.
    # [the owner's second answer of 2026-09-25: the master reaches the helpers as a keyword ONLY when one is handed
    # in, so every call made without one is the call made before — a test's double of a helper sees the same shape]
    _mk = _brand_mark.master_kwargs(logo_master)
    split_mm = (body_split * backbone.height_mm if front_fields and body_split is not None
                and colors.get("body_lower") and "logo" in backbone.anchors else None)
    if split_mm is not None and not ly < split_mm < ly + lh:
        split_mm = None
    # [his test day finding 3, 2026-09-30, design 117: laid into the front he confirmed, the mark stood 0.16 of it down
    # and left the concept's own elements — which print ABOVE the mark (`_concept_elements`) — 7.1 mm where they need
    # CONCEPT_FRONT_MIN_MM (1.8 mm once centred above the split); nothing printed, the motif the concept asks for was
    # missing and the redraw was refused.] Where the label IS his front and the concept's plan puts elements above the
    # mark, the highest the mark's top may stand is below their full room: the front's safe margin, a rule's width,
    # the floor, and the mark's own clear space. The mark's size, its clear space and the floor are not moved.
    room_top = None
    if (label_is_front and front_zone is not None and (concept_front or {}).get("layout")
            and ((concept_front or {}).get("face") or {}).get("state") != "READ"):
        try:
            room_top = (float(front_zone["y"]) + float(front_zone.get("safe_margin_mm") or 0.0)
                        + _CONCEPT_RULE_MM + CONCEPT_FRONT_MIN_MM)
        except (KeyError, TypeError, ValueError):
            room_top = None
    _probe = (_logo_box(backbone, logo_path, lw, s, px, py, **_mk)
              if split_mm is not None or room_top is not None else None)
    _probe_keepout = _front_keepout_y(_probe, logo_path, **_mk) if _probe is not None else None
    if _probe is None or _probe_keepout is None:
        split_mm = None
    else:
        from dataclasses import replace as _replace
        ax, ay = backbone.anchors["logo"]
        mh = _probe[3] / s                                             # the mark's height, mm
        clear = (_probe_keepout - (_probe[1] + _probe[3])) / s          # its own clear space, mm
        top = ly if room_top is None else max(ly, room_top + clear)     # the highest its top may stand
        cy = None
        if split_mm is not None:
            # "upper zone reserved for logo, lower zone for name and descriptor stack": the mark centred between the
            # highest its top may stand and the split — when it fits there
            if split_mm - top >= mh:
                cy = (top + split_mm) / 2.0
            else:
                split_mm = None
        elif ay - mh / 2.0 < top:
            cy = top + _CONCEPT_RULE_MM + mh / 2.0                       # only as far down as their room needs
        if cy is not None:
            backbone = _replace(backbone, anchors=dict(backbone.anchors, logo=(ax, cy)))
    _logo = _logo_box(backbone, logo_path, lw, s, px, py, **_mk)
    # [his answer after test day finding 3] the mark where the picture prints it, drawn from its approved master
    map_mark = (_map_mark_box(map_front, _mzone, _mbb, s, _mox, _moy, logo_master)
                if map_front and front_zone and _logo is not None and logo_master is not None else None)
    if map_mark is not None:
        _logo = map_mark["box"]
    # §BH66(a): a FACE — a form whose declared primary surface is its face — is arranged as the concept's own words put
    # it, when the caller hands in the reading of them and a confirmed zone is there to lay it into; everything else
    # keeps the ruled front
    _face = (concept_front or {}).get("face") if native and front_zone else None
    face_active = bool(_face and _face.get("state") == "READ")
    hero_surface = (_face.get("surface") or HERO_SURFACE) if (face_active or lid_map) else HERO_SURFACE
    if lid_map:
        # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2) and (3): "Never replaced by a template"] its art
        # first — the illustration redrawn flat and traced in colour, its sky as gradients — laid on the lid's own face
        # and clipped to its outline; then the parts its map traced, its lines of type set as every map sets them (the
        # granted face closest to each) and its mark from its master, each where the picture prints it — still its own
        # hero, drawn once
        from apps.pipeline.targets.container import lid_art as _lid_art
        con_children.append(_lid_art.art_group(map_front["lid_art"], _mox, _moy, _lid_box[2] * s, _lid_box[3] * s,
                                               clip=_scaled(backbone.cap_region, s, ox, oy)))
        # [His goal after the pitch page, 2026-10-15, A (3): "131 ... with a cream border"] the rim its concept shows
        # round the art drawn over the art's edge — moved above the art laid on the lid
        _rims = [c for c in con_children if getattr(c, "name", "") == "lid-border"]
        con_children = [c for c in con_children if getattr(c, "name", "") != "lid-border"] + _rims
        map_group, placements, map_front_record = _map_front_group(map_front, _mzone, _mbb, s, _mox, _moy)
        # [his goal of 2026-10-12, (4): "gold in the picture is foil (my rule): 124's gold arch and gold "Enchanted
        # Rose" go on the foil plate with the logo."] the art's regions traced in the picture's gold — 124's arch
        from apps.pipeline.services.concept_design_map import is_gold_hex as _is_gold
        map_front_record["gold_nodes"] += [LID_ART_PREFIX + str(j) for j, region in enumerate(
            map_front["lid_art"]["regions"]) if _is_gold(region["fill"])]
        # [his goal of 2026-10-13, (7)] each gold line drawn as a line — 124's arch — on the foil plate as its regions were
        map_front_record["gold_nodes"] += ["lid-line-%d" % j for j, line in enumerate(
            map_front["lid_art"].get("lines") or []) if _is_gold(line["hex"])]
        map_front_record["zone_on_sheet"] = {"top_mm": round(oy + float(front_zone["y"]) * s, 4), "scale": s}
        if map_safe is not None:
            map_front_record["safe_margin"] = map_safe
        con_children.append(map_group)
        map_typed = _map_type_group(map_front, _mzone, _mbb, s, _mox, _moy, name_font=_name_font(concept_front),
                                    product_name=product_name)
        if map_typed is not None:
            map_front_record["boxes"].update(map_typed[2]["boxes"])
            map_front_record.update({k: v for k, v in map_typed[2].items() if k not in ("boxes", "gold_nodes")})
            map_front_record["gold_nodes"] += map_typed[2]["gold_nodes"]
            map_front_record["drawn"] += [line["part"] for line in map_typed[2]["typed"]]
            con_children.append(map_typed[0])
            placements = placements + map_typed[1]
        if map_mark is not None:
            map_front_record["boxes"][map_mark["part"]] = map_mark["drawn_box"]
            map_front_record["mark"] = {k: map_mark[k] for k in ("fit", "beside_the_picture_mm", "ink")}
            map_front_record["drawn"].append(map_mark["part"])
            map_front_record["gold_nodes"].append("logo")
        elif _logo is not None:
            # no master of the mark on hand: the house mark laid where the picture prints its mark, at the picture's ink
            # height in the mark's own proportion — never left at the form's ruled place, over the lid's name
            from types import SimpleNamespace as _Proportion
            _at = _map_mark_box(map_front, _mzone, _mbb, s, _mox, _moy,
                                _Proportion(aspect=float(_logo[3]) / float(_logo[2])))
            if _at is not None:
                _logo = _at["box"]
                map_front_record["boxes"][_at["part"]] = _at["drawn_box"]
                map_front_record["mark"] = {"placed": "where the picture prints its mark", "fit": _at["fit"],
                                            "why": "no master of the mark on hand"}
        # the picture's motif is its illustration, drawn by its art — what the motif check measures, never the family
        # the concept's words requested (his answer after test day finding 3: drawn as the picture draws it)
        if map_front["lid_art"]["regions"]:
            map_front_record["motif_prefixes"] = list(map_front_record["motif_prefixes"]) + [LID_ART_PREFIX]
        map_front_record["lid_art"] = {"regions": len(map_front["lid_art"]["regions"]),
                                       # [his goal of 2026-10-13, (7)-(9)] the sky and the glow as smooth meshes, the
                                       # lines found drawn as lines
                                       "sky": "mesh", "glow": "mesh" if map_front["lid_art"].get("lines") else "bands",
                                       "lines": len(map_front["lid_art"].get("lines") or []),
                                       "sky_bands": len(map_front["lid_art"]["sky"]["rows"]),
                                       "measured": map_front["lid_art"]["measured"],
                                       "drawn_on_mm": [round(v, 3) for v in _lid_box],
                                       # [his goal of 2026-10-13, (7)-(9)] where on the sheet: x, y, width, height (mm)
                                       "on_page_mm": [round(_mox, 3), round(_moy, 3), round(_lid_box[2] * s, 3),
                                                      round(_lid_box[3] * s, 3)]}
    elif native and face_active:
        _descriptor = next((t.get("text") for t in (hierarchy_lines or []) if t.get("kind") == "descriptor"), None)
        # §BH67(d)2: the SURFACE the concept's fractions are of — the lid face the backbone draws (its cap_region),
        # which is the confirmed zone for a run proposed since §BH67(c)3 and wider than an older record's inset zone
        _face_pts = [(float(getattr(sg, "x")), float(getattr(sg, "y"))) for sg in (backbone.cap_region or [])
                     if hasattr(sg, "x") and hasattr(sg, "y")]
        _surface = ((px(min(x for x, _y in _face_pts)), py(min(y for _x, y in _face_pts)),
                     (max(x for x, _y in _face_pts) - min(x for x, _y in _face_pts)) * s,
                     (max(y for _x, y in _face_pts) - min(y for _x, y in _face_pts)) * s) if _face_pts else None)
        # [the owner's second answer of 2026-09-25: the ring traced on the lid's own outline] the outline's corner, read
        # off the outline itself: its top edge's straight run begins one corner radius in from its left edge
        # (``silhouettes._rrect``, which draws every lid face)
        _top = min(y for _x, y in _face_pts) if _face_pts else None
        _surface_radius = ((min(x for x, y in _face_pts if abs(y - _top) < 1e-9) - min(x for x, _y in _face_pts)) * s
                           if _face_pts else None)
        # [§BH71 PART 3: a lid face drawn with no straight run and longer than it is wide is an ellipse — a learned
        # oval lid (`silhouettes._ellipse`); a circle is square and keeps the round lid's reading exactly]
        _surface_shape = None
        if _surface is not None and abs(_surface[2] - _surface[3]) > 1e-6 and not any(
                type(sg).__name__ == "LineTo" for sg in (backbone.cap_region or [])):
            _surface_shape = "oval"
        concept_group, type_group, face_logo, placements, face_record = _concept_face(
            concept_front, front_zone, s, px, py, motif_language, logo_path, product_name,
            (_logo[2] if _logo else 0.0), _descriptor, ink=_ink(colors), swatches=_motif_swatches(colors),
            surface=_surface, rule_ink=_line_ink(colors, "rule"), ring_ink=_line_ink(colors, "ring"),
            surface_radius=_surface_radius, surface_shape=_surface_shape, **_mk)
        if concept_group is not None:
            con_children.append(concept_group)
        if type_group is not None:
            con_children.append(type_group)
        if face_logo is not None:
            _logo = face_logo
        concept_front_record = dict(concept_front, face=face_record)
    elif native:
        # 2B-2/2B-2A: native decoration + hero motif into the confirmed zone —
        # NO raster label. 2C-2E: a hierarchy contract switches the zone to
        # direct print (no field, no keyline, no boxed background).
        lines = name_lines or ([product_name] if product_name else [])
        # [his answer after test day finding 3] the parts the concept's map traced, at the picture's places
        map_group = None
        map_typed = None
        if map_front and front_zone:
            map_group, _map_places, map_front_record = _map_front_group(map_front, front_zone, backbone, s, ox, oy)
            # [his answers after 122 was redrawn, 2026-10-08, (2): "Fix the front-copy fit check so it measures against
            # MY confirmed print area"] where his confirmed front stands on the sheet, for the fit to read each line in it
            map_front_record["zone_on_sheet"] = {"top_mm": round(oy + float(front_zone["y"]) * s, 4), "scale": s}
            if map_safe is not None:
                map_front_record["safe_margin"] = map_safe          # [his final goal, A] what was fitted, and how
            map_typed = _map_type_group(map_front, front_zone, backbone, s, ox, oy, name_font=_name_font(concept_front),
                                        product_name=product_name)
            if map_typed is not None:
                map_front_record["boxes"].update(map_typed[2]["boxes"])
                map_front_record.update({k: v for k, v in map_typed[2].items() if k not in ("boxes", "gold_nodes")})
                map_front_record["gold_nodes"] += map_typed[2]["gold_nodes"]
                map_front_record["drawn"] += [line["part"] for line in map_typed[2]["typed"]]
            if map_mark is not None:
                # the mark drawn from its master at the picture's place: its box for the score, its fit said
                map_front_record["boxes"][map_mark["part"]] = map_mark["drawn_box"]
                map_front_record["mark"] = {k: map_mark[k] for k in ("fit", "beside_the_picture_mm", "ink")}
                map_front_record["drawn"].append(map_mark["part"])
                map_front_record["gold_nodes"].append("logo")        # the mark, where the picture prints its gold
            elif _logo is not None and map_typed is not None:
                # [his go of 2026-10-02: the map path for a wand vial, whose picture prints no mark] the house mark at its
                # ruled size, clear of every part the picture's front draws — moved into the free height they leave
                # where it would lie over them — and said
                _logo, _where = _mark_clear_of(_logo, map_front_record["boxes"], front_zone, backbone, s, ox, oy)
                if _where is not None:
                    map_front_record["mark"] = {"placed": _where,
                                                "why": "the picture prints no mark; the house mark kept clear of its parts"}
        if map_typed is not None:
            # [his answer after test day finding 3] the front's type where its picture prints it, not the ruled block
            deco_group, placements = map_typed[0], map_typed[1]
        else:
            deco_group, placements = _native_decoration(
                backbone, front_zone, lines, body_c, s, px, py,
                language=motif_language, hierarchy=hierarchy_lines,
                direct_print=bool(hierarchy_lines),
                keepout_y=_fields_keepout_y(_front_keepout_y(_logo, logo_path, **_mk), _logo, split_mm, py),
                name_style=(concept_front or {}).get("name_style"), ink=_ink(colors),
                swatches=_motif_swatches(colors), name_font=_name_font(concept_front))
        # §BH65(c)3: the concept's own elements, where §AU1 lets decoration print — only when the caller hands in the
        # plan the concept's words make, and only on the direct-print front; the ruled stack is never moved
        above_group = behind_group = None
        if map_group is not None:
            placements = placements + _map_places
            con_children.append(map_group)
        # [his answer after test day finding 3: the picture's motif, never the one its words asked for, where it is drawn]
        if concept_front and hierarchy_lines and front_zone and map_group is None:
            above_group, behind_group, concept_places, concept_record = _concept_front(
                concept_front, front_zone, deco_group, _logo, logo_path, s, px, py, motif_language,
                ink=_ink(colors), swatches=_motif_swatches(colors), **_mk)
            placements = placements + concept_places
            concept_front_record = dict(concept_front, **concept_record)
        if behind_group is not None:
            con_children.append(behind_group)
        con_children.append(deco_group)
        if above_group is not None:
            con_children.append(above_group)
    else:
        # legacy: label artwork is a flagged raster exception, clipped to zone
        label_img = image_node(
            "label-artwork", label_path, px(lx), py(ly), lw * s, lh * s,
            clip=rect_clip(px(lx), py(ly), lw * s, lh * s))
        if label_img is not None:
            con_children.append(label_img)
    # logo — the ONE permitted controlled raster fallback (reported separately,
    # never counted as decoration) until a vector master exists
    logo_zone_used = ""
    if _logo is not None and logo_master is not None:
        # THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo
        # trace, switch the mark to it so gold foil can print." The mark drawn from the approved vector master: an
        # AssetRef in the same box, which the emitter expands into the master's outlines and a foil plate is cut from
        _mark = _brand_mark.mark_node("logo", logo_master, *_logo)
        if map_mark is not None and map_mark["ink"]:
            # [his look at 117 drawn from its map, 2026-10-02: "The foil gold, it's the picture, not the brand"] the
            # mark the picture prints is drawn in the picture's own gold as it is drawn — nothing repaints it after
            _mark.recolor = Color.from_hex(map_mark["ink"])
        con_children.append(_mark)
        logo_zone_used = _brand_mark.ZONE_USED
    elif _logo is not None:
        # the height is the ASSET'S, not this composer's. It used to be
        # span*0.36 for every logo ever placed, which stretched the real mark
        # by 73%; the old y offset span*0.18 was half that height, so the
        # anchor has always meant "centred", and it still does. That geometry
        # now lives in _logo_box, which the front keep-out reads too.
        logo_img = image_node("logo", logo_path, *_logo)
        if logo_img is not None:
            con_children.append(logo_img)
            logo_zone_used = "front-controlled-fallback"
    # product name — native live text at its anchor (legacy single line;
    # native mode already stacked the name inside the decoration group)
    if not native and product_name and "product_name" in backbone.anchors:
        ax, ay = backbone.anchors["product_name"]
        con_children.append(centered_text(
            "container-name", product_name, px(ax), py(ay),
            FALLBACK_NAME_PT, ink_for(body_c), font="bold"))
    # outline stroked LAST so the container reads crisp over the fills
    con_children.append(Path(name="silhouette-outline", segments=sil,
                             stroke=Stroke(color=_INK, width_mm=_OUTLINE_W)))
    children.append(Group(name="Container", role="product", children=con_children))

    # --- multi-surface emission (2B-2A §5-§8): native artwork for every
    #     confirmed decoration surface beyond the front hero ------------------
    surface_inventory: dict = {hero_surface: "hero"}
    front_back = {"schema_version": "container_front_back_relationship/1.0",
                  "front_role": "hero_brand_name_motif", "back_role": None,
                  "roles_distinct": True}
    if native:
        _info_where, _info_zones = information_zones(zones, backbone.width_mm)
        surfaces_group, surf_placements, surface_inventory, front_back = \
            _surface_panels(zones, colors, motif_language, product_name,
                            body_c, back_sections=back_sections,
                            strip_box=layout["strip_box"], k=_k, hero_surface=hero_surface,
                            batch_code_place=batch_code_place,
                            info_surface=zone_surface(_info_zones[0]) if _info_zones and back_sections else None)
        if surfaces_group is not None:
            children.append(surfaces_group)
            placements = placements + surf_placements

    # --- Spec group (native vector: SKU, name, colour swatches) ------------
    spec_children: list = []
    sy = layout["spec_y"]
    _spec_x = layout["ref_box"][0]
    if sku:
        _sku = f"SKU: {sku}"
        spec_children.append(TextRun(
            name="sku", text=_sku, x=_spec_x, y=sy,
            size_pt=chrome_size_pt(_sku, max(4.0, 8 * _k), _room_x0_mm + _room_mm - _spec_x),
            color=_INK, font="bold", align="left"))
    # cap/body colour swatches with labels; a transparent container (§6)
    # carries the full named-role swatch registry instead of two flat fills
    if transparency and backbone.archetype != "bottle":
        # §BH70(1), item 11 of the list the owner was sent: a transparent form that is not a bottle is named for what its
        # sheet paints — the wall, the product seen through it, its cap or lid. The registry below was ruled for the
        # transparent serum bottle (2B-3V-CORR-3 §6) and named a peach-rose fill, dewdrops and the serum's print colours
        # on every transparent form, whatever it held; a bottle keeps it as ruled.
        swatches = [
            ("CONTAINER_TRANSPARENT_BODY", Color.from_hex("#FDF7F2")),
            ("PRODUCT_SEEN_THROUGH", Color.from_hex(transparency.get("product_color") or "#F2C4CE")),
            (_declared.closure_part_of(backbone.archetype).upper(), cap_c),
        ]
    elif transparency:
        product_c = Color.from_hex(
            (transparency.get("product_color") or "#F2C4CE"))
        swatches = [
            ("CONTAINER_TRANSPARENT_BODY", Color.from_hex("#FDF7F2")),
            ("PRODUCT_PEACH_ROSE_FILL", product_c),
            ("CAP_BLUSH", cap_c),
            ("LOGO_PRINT", Color.from_hex("#B76E79")),
            ("PRODUCT_NAME_PRINT", Color.from_hex("#8B3A52")),
            ("DEWDROP_CLEAR", Color.from_hex("#FFFFFF")),
            ("DEWDROP_PEACH", Color.from_hex("#F7DDE3")),
            ("DEWDROP_HIGHLIGHT", Color.from_hex("#FFFFFF")),
            ("SPOT_UV_DEWDROPS", Color.from_hex("#E8E8E8")),
        ]
    else:
        # §BH70(1), item 21 of the list the owner was sent: the closure colour named for the part it paints — a jar's or
        # a compact's LID, where every form's drawn file said CAP; a bottle's stays CAP
        swatches = [("BODY", body_c), (_declared.closure_part_of(backbone.archetype).upper(), cap_c)]
        if lid_map:
            # [His review of 127, 130, 131 and 132, 2026-10-15, C (8): "No empty grey blocks in the files"] a lid drawn
            # as its art prints no flat colour of its own: no swatch of one (131's grey "LID" block)
            swatches = swatches[:1]
        if backbone.collar_region is not None and backbone.bulb_region is None and colors.get("collar"):
            swatches.append(("COLLAR", Color.from_hex(colors["collar"])))   # [his review, D (11)] its collar drawn
        if body_split is not None and colors.get("body_lower"):
            swatches.insert(1, ("BODY_LOWER", Color.from_hex(colors["body_lower"])))   # [his test day finding 3]
    # §BH70(1): the swatches keep their size and their four to a row wherever the first one and its caption fit the
    # page beside each other, which is every sheet there was; on a narrower page the swatch block is drawn at the scale
    # at which they do, and a swatch whose caption would still leave the page opens the next row
    _row_end_mm = _room_x0_mm + _room_mm
    _ks = _k
    if swatches:
        _cap0 = f"{swatches[0][0]} {swatches[0][1].to_hex()}"[:40]
        if _spec_x + 19 * _k + name_width_estimate_mm(_cap0, max(2.5, 4.5 * _k), upper=True) > _row_end_mm:
            _ks = (_row_end_mm - _spec_x) / (19 + name_width_estimate_mm(_cap0, 4.5, upper=True))
            if 4.5 * _ks < 2.5:
                _ks = (_row_end_mm - _spec_x - name_width_estimate_mm(_cap0, 2.5, upper=True)) / 19
            _ks = max(_ks, 0.1)
    _col = _row = 0
    for i, (lab, col) in enumerate(swatches):
        _caption = f"{lab} {col.to_hex()}"[:40]
        if _col == 4 or (_col and _spec_x + _col * 46 * _ks + 19 * _ks
                         + name_width_estimate_mm(_caption, max(2.5, 4.5 * _ks), upper=True) > _row_end_mm):
            _col, _row = 0, _row + 1
        swx = _spec_x + _col * 46 * _ks
        swy = sy + 6 * _ks + _row * 14 * _ks
        _col += 1
        spec_children.append(Rect(name=f"swatch-{lab.lower()}", x=swx, y=swy,
                                  w=16 * _ks, h=10 * _ks,
                                  fill=SolidFill(color=col),
                                  stroke=Stroke(color=_INK, width_mm=0.25)))
        spec_children.append(TextRun(
            name=f"swatch-label-{lab.lower()}",
            text=_caption,
            x=swx + 19 * _ks, y=swy + 7 * _ks, size_pt=max(2.5, 4.5 * _ks),
            color=_INK, align="left"))
    children.append(Group(name="Spec", role="info", children=spec_children))

    # [his rules for cloning a design from a picture, 2026-10-02, rule 5: "THE BACK IS DRAWN"; §W1(a)] the back copy at
    # the size it prints, below the spec, from the confirmed back zone; the sheet grown to hold it — never scaled to fit
    page_h = layout["page_h"]
    back_metadata: dict = {}
    if back_panel is not None and back_sections:
        from apps.ire import back_panel as _back_panel
        _spec_foot = max([float(n.y) + float(getattr(n, "h", 0.0) or 0.0) for n in spec_children] + [float(sy)])
        _bx, _by = layout["strip_box"][0], _spec_foot + 12.0 * _k
        # [his answer of 2026-10-05, W10: "Never nowhere"] on the surface his order gives it — the back print zone; a
        # jar's wrap label's back (its two ends, the copy flowing from one to the other); the base label — and with
        # none, no panel and a record that refuses by name
        true_scale, fit = compose_information_panels(
            back_sections, zones, backbone.width_mm, _bx, _by, ink=_ink(colors),
            methods_record=back_panel.get("methods_record"), heading_role="heading", copy_role="body",
            packaging=_declared.is_face(backbone.archetype),   # [his goal of 2026-10-12, (14)] a palette, a compact
            # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] the label's QR, where the shape step measured it
            **({"qr_url": back_panel["qr_url"]} if back_panel.get("qr_url") else {}),
            # [his goal of 2026-10-06, item 8] measured as this document is drawn — the theme's faces, never the legacy
            doc_metadata={"typography_surface": "apps/ire/compose_container.py::compose_container_graph"})
        back_metadata[_back_panel.SCHEMA] = fit
        if true_scale:
            _label = ("BACK PANEL AT PRINT SIZE (%g × %g mm)" % tuple(fit["panel_mm"])
                      if fit.get("where") == _back_panel.WHERE_BACK_ZONE
                      else "%s AT PRINT SIZE (%s × %g mm)" % (
                          str(fit.get("where")).upper(),
                          " + ".join("%g" % p["panel_mm"][0] for p in fit.get("panels") or [fit]),
                          fit["panel_mm"][1]))
            children.append(TextRun(
                name="sheet-back-panel-true-scale-label", text=_label,
                x=_bx, y=_by - 2.5 * _k, size_pt=max(2.5, 4.5 * _k), color=_INK, font="bold", align="left"))
            children.extend(true_scale)
            page_h = max(page_h, _by + float(fit["panel_mm"][1]) + 8.0 * _k)
        # §BH50(f)(2): which nodes draw which section, the strip's and the panel's, so the placeholder record joins its
        # findings to the sections by this map and never by a run's name
        back_metadata["back_copy_drawings"] = {
            str(si): {"heading": str(sec.get("heading", "")), "strip": [f"back-section-{si}-copy"],
                      "true_scale": [f"back-panel-{e['section']}-{e['role']}-{e['order']}"
                                     for e in fit.get("lines") or []
                                     if e.get("fits") and e.get("section") == si and e.get("role") == "copy"]}
            for si, sec in enumerate(back_sections)}

    # [his goal of 2026-10-10, item 2] the open tray, every pan and its shade's name, at the size it prints
    tray_record = None
    if open_tray is not None:
        from apps.dielines.exporters.counter_display_files import _resolve_fonts
        from apps.ire import palette_tray as _palette_tray
        _tx, _ty = layout["strip_box"][0], page_h + 10.0 * _k
        tray_group, tray_record = _palette_tray.compose_open_tray(
            open_tray["tray"], backbone.width_mm, backbone.height_mm, _tx, _ty, ground_hex=open_tray["ground_hex"],
            ink_hex=open_tray["ink_hex"], edge_hexes=open_tray["edge_hexes"], face=_resolve_fonts()[0],
            pans=open_tray.get("pans"),              # [his test blocker on design 124, (5)] each pan its shade
            # [his goal of 2026-10-12, (11)–(13)] the tray's own inks, as its picture prints them
            rim_hex=open_tray.get("rim_hex"), glow_hex=open_tray.get("glow_hex"),
            name_hex=open_tray.get("name_hex"), lid_inside=open_tray.get("lid_inside"))
        _label = "OPEN TRAY AT PRINT SIZE (%g × %g mm) — %d PANS, %d ROWS OF %d" % (
            tray_record["insert_mm"][0], tray_record["insert_mm"][1], tray_record["rows"] * tray_record["cols"],
            tray_record["rows"], tray_record["cols"])
        children.append(TextRun(name="sheet-open-tray-label", text=_label, x=_tx, y=_ty - 2.5 * _k,
                                size_pt=chrome_size_pt(_label, max(2.5, 4.5 * _k), _room_mm), color=_INK,
                                font="bold", align="left"))
        children.append(tray_group)
        _before = page_h
        page_h = _ty + tray_record.get("drawn_h_mm", tray_record["insert_mm"][1]) + 8.0 * _k
        # the sheet's height the tray took, at the size it prints — product, never presentation canvas (Gate 2's
        # artboard axis reads it from the drawing's record)
        tray_record["sheet_grown_mm"] = round(page_h - _before, 3)

    root = Group(name="Artwork", role="artwork", children=children)
    # VQR-1: the emitted PRODUCT bounds (mm, sheet space) — the quality
    # gate's silhouette axis measures these against the confirmed profile
    _structure = [sil, _scaled(backbone.cap_region, s, ox, oy)]
    if backbone.bulb_region is not None:
        _structure.append(_scaled(backbone.bulb_region, s, ox, oy))
    _xs, _ys = [], []
    for _segs in _structure:
        for _seg in _segs:
            for _ax, _ay in (("x", "y"), ("x1", "y1"), ("x2", "y2")):
                _vx = getattr(_seg, _ax, None)
                _vy = getattr(_seg, _ay, None)
                if _vx is not None and _vy is not None:
                    _xs.append(float(_vx))
                    _ys.append(float(_vy))
    _bounds = ([round(max(_xs) - min(_xs), 3),
                round(max(_ys) - min(_ys), 3)] if _xs else None)
    doc = Document(page_w=layout["page_w"], page_h=page_h,
                    title=product_name or "Container concept",
                    metadata={"typography_surface": "apps/ire/compose_container.py::compose_container_graph",  # §BH32(h)
                              "target": "product_container",
                              "archetype": backbone.archetype,
                              "mode": "native" if native else "legacy",
                              "logo_zone_used": logo_zone_used,
                              "front_zone_id": (front_zone or {}).get("zone_id"),
                              "placements": placements,
                              "surface_inventory": surface_inventory,
                              "front_back_relationship": front_back,
                              "motif_family": (motif_spec or {}).get("rendered_via"),
                              # 2C-2E §10: photographic-styling visualization
                              # objects — material communication on the sheet,
                              # NEVER print separations
                              "nonprinting_objects": (
                                  ["GLASS_HIGHLIGHT"] if material_stack
                                  else []),
                              "material_stack_used": bool(
                                  material_stack
                                  and backbone.collar_region is not None),
                              # VQR-1: product-derived artboard evidence
                              "artboard_mm": [round(layout["page_w"], 3),
                                              round(page_h, 3)],
                              "artboard_policy":
                                  "PRODUCT_DERIVED_FROM_CONFIRMED_PROFILE",
                              "product_bounds_mm": _bounds,
                              **({"concept_front": concept_front_record} if concept_front_record else {}),
                              # [his answer after test day finding 3] the parts drawn from the concept's map, and where
                              **({"map_front": _with_gold_closure(map_front_record, closure_looks)}
                                 if map_front_record else {}),
                              # [his goal after the pitch page, A (2)] each metal closure part: its metal and its light
                              **({"closure_looks": closure_looks} if closure_looks else {}),
                              # [his goal of 2026-10-10, item 2] the open tray drawn: its grid, its pans, its names
                              **({"open_tray": tray_record} if tray_record else {}),
                              # §BH67(c)5: the concept's own face for the name, for the layer to verify and draw
                              **({"concept_typeface": {
                                  "stem": ((concept_front or {}).get("typeface") or {}).get("name", {}).get("stem"),
                                  "words": ((concept_front or {}).get("typeface") or {}).get("name", {}).get("words"),
                                  "governed_by": "§BH67(c)5"}}
                                 if _name_font(concept_front) != "bold" else {}),
                              }, root=root)
    # §BH50(f)(1): this composer states what every run it emitted IS — the
    # front's printed copy on BODY_FRONT (the direct-print group, the legacy
    # Decoration group, the legacy container name), every strip panel's
    # depiction of its surface's copy, and the sheet's own furniture. A run
    # this pass does not know stays undeclared and is judged by inference
    # and disclosed. Metadata on the nodes only: no drawn byte moves.
    from apps.ire.print_scope import declare as _declare_print_scopes
    _front_zid = (front_zone or {}).get("zone_id")
    _zone_ids = {}
    for _z in (zones or []):
        _zone_ids.setdefault(zone_surface(_z), _z.get("zone_id"))
    _surfs = sorted({s for s in _zone_ids if s})
    doc.metadata.update(back_metadata)      # [his rules of 2026-10-02, rule 5] the back panel's fit and its drawings
    doc.metadata["print_scope_census"] = _declare_print_scopes(
        doc,
        printed_groups={FRONT_DIRECT_PRINT_GROUP: (hero_surface, _front_zid),
                        "Decoration": (hero_surface, _front_zid),
                        "Container": (hero_surface, _front_zid),
                        # [his rules of 2026-10-02, rule 5] the back at the size it prints, where it is drawn
                        f"{TRUE_SCALE_SURFACE_PREFIX}BODY_BACK": ("BODY_BACK", _zone_ids.get("BODY_BACK")),
                        # [his goal of 2026-10-10, item 2] the shade names print on the tray's insert, a surface no
                        # print method is recorded for: judged at the disclosed fallback floor
                        "SHADE NAMES": (TRAY_INSERT_SURFACE, None)},
        depiction_groups={f"{SURFACE_GROUP_PREFIX}{s}": (s, _zone_ids.get(s))
                          for s in _surfs},
        annotation_names=("sheet-title", "reference-label", "sku", "sheet-back-panel-true-scale-label",
                          "sheet-open-tray-label")
                         + tuple(f"panel-{s}-label" for s in _surfs)
                         + tuple(f"panel-{s}-info" for s in _surfs),
        annotation_prefixes=("swatch-label-",))
    return doc
