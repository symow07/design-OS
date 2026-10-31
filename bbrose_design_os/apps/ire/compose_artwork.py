"""Compose a Design Graph for an ARTWORK target (§BH55 Phase 2, 2026-09-19).

An artwork target is a flat printed or digital piece built around ONE key visual: the concept picture a person
approved at Gate 1, placed to cover its region (its proportion kept, the overflow clipped, never stretched), the
product's own name set in type, and the brand logo on a ground the owner permitted it to sit on. Native vector grounds
and type; the key visual and the logo are the flagged raster exceptions, as on every composer here.

THE OWNER'S RULES THIS COMPOSER READS, NOT RESTATES:
  * the logo — §AU3 (``container_brand_usage``): clear space 1.0 x its own measured cap height on all four sides, 12 mm
    minimum reproduced width in print, 60 px on screen; §BB1: the mark in its positive form sits only on pure white or
    one of the two owner-named light grounds, by LOOKUP (``GROUND_HEX_RULED``), never a tint that "looks light". Every
    ground under the mark here IS ``#F6EDEB``, the first ruled ground; nothing tinted from the picture ever sits under it.
  * type — the faces come from the role layer (``font_roles``) through the document's own surface tag, so the theme
    reaches this surface; every run is MEASURED in the face the document draws it with (``resolve_metric_faces``,
    the map the emitter uses) against the box it was set in. A run that does not fit is NAMED — never set below its
    floor, never clipped (§BH50(f)(3): "Text that does not fit is a design problem to solve, not a number to shrink").
  * the line pitch of running copy is the back panel's own (``back_panel.LEADING_EM``) — one model, two readers.

WHAT IS CHOSEN HERE, AND SAID AS CHOSEN (a new target's own typographic scale, not an instrument): the key visual's
share of the page, the headline's size range and the body size as fractions of the format's short side. Each is a
module constant with its reason.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Optional

from apps.ire.graph import Color, Document, Group, Rect, SolidFill, TextRun
from apps.ire.nodes import image_node, ink_for, intrinsic_aspect, rect_clip

SCHEMA = "artwork_record/1.0"
SURFACE_FORMAT = "apps/ire/compose_artwork.py::artwork_document"
SURFACE_SHEET = "apps/ire/compose_artwork.py::presentation_document"

MM_PER_PT = 25.4 / 72.0
#: a digital format is sized in CSS pixels; the vector file carries it at 96 px to the inch
MM_PER_PX = 25.4 / 96.0

#: §BB1's first owner-named light ground (``container_brand_usage.GROUND_HEX_RULED``) — the ONLY ground the logo sits on
GROUND_HEX = "#F6EDEB"

#: CHOSEN: the key visual's share of the trim along the format's long axis — the picture leads, the type sits below
#: (portrait) or beside (landscape) it on the light ground the logo is permitted on
KEY_VISUAL_SHARE = 0.66
#: CHOSEN: the headline's size range and the running copy's size, as fractions of the format's short side in mm
#: (A4: 63 → 25.2 pt, copy 12.2 pt; A5: 44.4 → 17.8 pt, copy 8.6 pt) — a scale, so every format carries one voice
HEADLINE_MAX_PT_PER_MM = 0.30
HEADLINE_MIN_PT_PER_MM = 0.12
COPY_PT_PER_MM = 0.066
#: CHOSEN: the running copy is never set below this, whatever the format
COPY_FLOOR_PT = 7.0
#: the owner's floor for small copy, §BH50(f)(3) ("the 5.0 pt floor governs"), read as the floor for ANY run here: on a
#: format so small its own scale would set the name below it (a display tray's lip), the name is set no smaller
HEADLINE_FLOOR_PT = 5.0
#: CHOSEN: the headline is sized to this share of the type box's width, so it never runs margin to margin; running
#: copy wraps at the narrower share, a reading measure (about 60-75 characters at the copy size)
HEADLINE_MEASURE_SHARE = 0.88
COPY_MEASURE_SHARE = 0.74
#: CHOSEN: on the "info" layout the key visual closes the page — this share of the trim, at the foot, into the bleed
INFO_VISUAL_SHARE = 0.36
#: CHOSEN: the picture sits BESIDE the type only on a format at least this much wider than tall. MEASURED on the
#: booth's near-square walls (3000 × 2400) and counter (1000 × 900): a side-by-side type box a third of the width
#: set the name over its box at its own floor (ARTWORK_COPY_EXCEEDS_BOX) — a design problem, solved by the layout and
#: not by a smaller number; stacked, the name holds. Every format shipped before keeps its layout.
SIDE_BY_SIDE_ASPECT = 1.5
#: CHOSEN: the subline sits at this share of the headline, never below the running copy's size
SUBLINE_SHARE = 0.34
#: CHOSEN: the logo's placed height as a share of the short side, never below the §AU3 minimum width
LOGO_H_PER_MM = 0.05

#: [his answer of 2026-10-05, W9: "let the copy box grow to fit; no hold for under 2 mm"] the type box grows into the
#: picture's region by what its words still need at their floors; CHOSEN: the picture keeps at least this share of its
#: own height — past it the box stops growing and what is left over is measured
TYPE_BOX_PICTURE_KEEPS = 0.5
#: his: an overrun under this many millimetres is never a hold — it is measured and recorded, and the design goes on
COPY_OVERRUN_TOLERANCE_MM = 2.0

HEADLINE_ROLE, COPY_ROLE = "heading", "body"

# the codes that hold a design at Gate 2 — each a MEASURED fact, never a guess
EXCEEDS_BOX = "ARTWORK_COPY_EXCEEDS_BOX"
COPY_UNMEASURED = "ARTWORK_COPY_UNMEASURED"
COPY_NOT_DRAWN = "ARTWORK_COPY_NOT_DRAWN"
KEY_VISUAL_MISSING = "ARTWORK_KEY_VISUAL_MISSING"
LOGO_NOT_PLACED = "ARTWORK_LOGO_NOT_PLACED"
LOGO_BELOW_MINIMUM = "ARTWORK_LOGO_BELOW_MINIMUM_SIZE"
HEADLINE_MISSING = "ARTWORK_HEADLINE_MISSING"
HEADLINE_IS_THE_BRIEF = "ARTWORK_HEADLINE_IS_THE_BRIEF_LINE"


@dataclass(frozen=True)
class ArtworkFormat:
    """One deliverable. ``layout``: "cover" (the key visual with the name beside or below it) or "info" (the product's
    own words on the light ground). A digital format carries its pixel size in ``px``."""
    key: str
    label: str
    width_mm: float
    height_mm: float
    bleed_mm: float = 0.0
    safe_mm: float = 5.0
    layout: str = "cover"
    px: Optional[tuple[int, int]] = None
    #: (top, right, bottom, left) the TYPE keeps clear of the page's edges — a platform's chrome sits over a story's
    #: top and foot; None: the uniform safe margin all round. The picture still runs to the edges.
    safe_insets_mm: Optional[tuple[float, float, float, float]] = None

    def insets(self) -> tuple[float, float, float, float]:
        return self.safe_insets_mm or (self.safe_mm, self.safe_mm, self.safe_mm, self.safe_mm)

    @property
    def page_w(self) -> float:
        return self.width_mm + 2 * self.bleed_mm

    @property
    def page_h(self) -> float:
        return self.height_mm + 2 * self.bleed_mm


def px_format(key, label, w_px, h_px, *, safe_px=48, layout="cover", safe_insets_px=None) -> ArtworkFormat:
    """A digital format from its pixel size (96 px to the inch in the vector file)."""
    insets = tuple(round(v * MM_PER_PX, 4) for v in safe_insets_px) if safe_insets_px else None
    return ArtworkFormat(key=key, label=label, width_mm=round(w_px * MM_PER_PX, 4), height_mm=round(h_px * MM_PER_PX, 4),
                         bleed_mm=0.0, safe_mm=round(safe_px * MM_PER_PX, 4), layout=layout, px=(w_px, h_px),
                         safe_insets_mm=insets)


@dataclass
class ArtworkCopy:
    """The words a piece carries, each with where it came from. Nothing is written for a product that has no words
    on record: ``body`` holds only the product record's own copy."""
    headline: str = ""
    headline_source: str = ""
    subline: str = ""
    body: tuple = ()
    body_source: str = ""
    codes: list = field(default_factory=list)


def _sha(path) -> Optional[str]:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _faces(metadata: dict) -> dict:
    """The role → face map the emitter draws this document with, each face registered for measuring."""
    from apps.ire.text_metrics import register_font, resolve_metric_faces
    faces = resolve_metric_faces(metadata) or {}
    for label, path in faces.values():
        register_font(label, path)
    return faces


def _face(role: str, faces: dict) -> Optional[str]:
    from apps.ire.font_roles import base_role
    entry = faces.get(base_role(role)) or faces.get(role)
    return entry[0] if entry else None


def _width_mm(text: str, size_pt: float, face: Optional[str]) -> Optional[float]:
    from apps.ire.text_metrics import text_width_mm_measured
    if not face:
        return None
    return text_width_mm_measured(text, size_pt * MM_PER_PT, face)


def _split(text: str, parts: int) -> list[str]:
    """Break on whitespace into ``parts`` balanced lines (by characters) — a name is never broken inside a word."""
    words = text.split()
    if parts <= 1 or len(words) < 2:
        return [text]
    parts = min(parts, len(words))
    target = len(text) / parts
    lines, cur = [], []
    for w in words:
        cur.append(w)
        if len(lines) < parts - 1 and len(" ".join(cur)) >= target:
            lines.append(" ".join(cur))
            cur = []
    if cur:
        lines.append(" ".join(cur))
    return lines


def _wrap(text: str, size_pt: float, face: Optional[str], width_mm: float) -> list[str]:
    """Greedy word wrap by MEASURED width (a word longer than the line stands alone, and is measured as such)."""
    lines, cur = [], ""
    for w in text.split():
        trial = f"{cur} {w}".strip()
        wmm = _width_mm(trial, size_pt, face)
        if cur and wmm is not None and wmm > width_mm:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


#: the size a line is measured at to find the size that fits it — a set width is linear in its size, so the fitting
#: size is this one scaled by a ratio of two widths in millimetres, and every quantity keeps its own unit
_REF_PT = 10.0


def _fit_headline(name: str, face: Optional[str], avail_mm: float, max_pt: float, min_pt: float):
    """(lines, size_pt): the largest size, up to ``max_pt``, at which the name fits the width on one line, else on two
    or three balanced lines; below ``min_pt`` it is never set — it is drawn at the floor and measured as over."""
    for parts in (1, 2, 3):
        lines = _split(name, parts)
        widest_mm = max((_width_mm(ln, _REF_PT, face) or 0.0) for ln in lines)
        if not widest_mm:
            return lines, max_pt
        size_pt = min(max_pt, _REF_PT * (avail_mm / widest_mm))
        if size_pt >= min_pt:
            return lines, round(size_pt, 2)
        if len(lines) < parts:
            break
    return _split(name, 3), round(min_pt, 2)


@dataclass
class _Frame:
    """Where a format is being drawn: an origin and a scale (the presentation sheet draws each format smaller)."""
    ox: float = 0.0
    oy: float = 0.0
    s: float = 1.0

    def x(self, v):
        return self.ox + v * self.s

    def y(self, v):
        return self.oy + v * self.s

    def d(self, v):
        return v * self.s


def _descent_mm(face: Optional[str], size_pt: float) -> float:
    """The face's own descender depth at this size (the font file's value), else a quarter em."""
    try:
        from reportlab.pdfbase import pdfmetrics
        d = abs(pdfmetrics.getFont(face).face.descent) / 1000.0 if face else None
    except Exception:  # noqa: BLE001 — an unregistered face has no descent to read
        d = None
    return (d if d else 0.25) * size_pt * MM_PER_PT


def _place_picture(fmt, key_visual, region, f, nodes, rec) -> None:
    """The key visual covers ``region`` — its proportion kept, centred, the overflow clipped — and its pixels per inch
    as placed are MEASURED into ``rec``."""
    aspect = intrinsic_aspect(key_visual)
    if aspect is None:
        rec["state"] = "MISSING"
        return
    rx, ry, rw, rh = region
    if aspect > rh / rw:                                       # taller than the region: its width fills it
        pw, ph = rw, rw * aspect
    else:
        pw, ph = rh / aspect, rh
    px_, py_ = rx + (rw - pw) / 2.0, ry + (rh - ph) / 2.0
    nodes.append(image_node(f"{fmt.key}-key-visual", key_visual, f.x(px_), f.y(py_), f.d(pw), f.d(ph),
                            clip=rect_clip(f.x(rx), f.y(ry), f.d(rw), f.d(rh))))
    from PIL import Image as _PIL
    with _PIL.open(key_visual) as im:
        w_px, h_px = im.size
    k = w_px / pw                                              # source pixels per placed millimetre
    rec.update(state="PLACED", source_px=[w_px, h_px], placed_mm=[round(pw, 3), round(ph, 3)],
               region_mm=[round(v, 3) for v in region],
               crop_px=[round((rx - px_) * k), round((ry - py_) * k), round(rw * k), round(rh * k)],
               effective_ppi=round(k * 25.4, 1),
               note="pixels per inch as placed — measured; no print-resolution floor is on record here")


def compose_format(fmt: ArtworkFormat, copy: ArtworkCopy, *, key_visual: Optional[str], logo: Optional[str],
                   faces: dict, frame: Optional[_Frame] = None, logo_master=None) -> tuple[Group, dict]:
    """One format, laid out and MEASURED. Returns its group (in the frame's coordinates) and its record row. The row's
    measurements are taken at true size whatever the frame's scale — the sheet shows the same layout smaller.

    Two passes: the stack (logo, name, descriptor, the product's own words) is built and measured first — every run's
    width in its face, the stack's height to the last line's descender — then set in the middle of its type box. A
    stack taller than its box, or a run wider than it, is NAMED, never clipped.

    [THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    switch the mark to it so gold foil can print." ``logo_master`` — the approved vector master a caller found on
    file (apps/ire/brand_mark.py) — gives the mark its aspect (its ink bounds), its cap band (its own outlines,
    rasterised) and its node; None, every call before it, reads the raster ``logo`` exactly as before.]"""
    from apps.ire import back_panel
    from apps.ire.container_brand_usage import (MINIMUM_WIDTH_MM_PRINT, MINIMUM_WIDTH_PX_SCREEN, clear_space_mm,
                                                measure_cap_ratio)
    f = frame or _Frame()
    b, W, H = fmt.bleed_mm, fmt.page_w, fmt.page_h
    tx, ty, tw, th = b, b, fmt.width_mm, fmt.height_mm             # the trim box
    short = min(tw, th)
    ground = Color.from_hex(GROUND_HEX)
    ink = ink_for(ground)
    head_face, copy_face = _face(HEADLINE_ROLE, faces), _face(COPY_ROLE, faces)
    max_pt, min_pt = short * HEADLINE_MAX_PT_PER_MM, max(HEADLINE_FLOOR_PT, short * HEADLINE_MIN_PT_PER_MM)
    max_pt = max(max_pt, min_pt)
    copy_pt = max(COPY_FLOOR_PT, round(short * COPY_PT_PER_MM, 2))
    pitch_mm = copy_pt * MM_PER_PT * back_panel.LEADING_EM
    row = {"key": fmt.key, "label": fmt.label, "trim_mm": [tw, th], "bleed_mm": b, "safe_mm": fmt.safe_mm,
           "layout": fmt.layout, "px": list(fmt.px) if fmt.px else None,
           "ground": {"hex": GROUND_HEX, "ruled_as": "brand_light_ground", "rule": "§BB1 GROUND_HEX_RULED (lookup)"},
           "ink_hex": "#%02X%02X%02X" % tuple(round(c * 255) for c in (ink.r, ink.g, ink.b)),
           "runs": [], "codes": []}
    nodes = [Rect(name=f"{fmt.key}-ground", x=f.x(0), y=f.y(0), w=f.d(W), h=f.d(H),
                  fill=SolidFill(color=ground))]

    # ---- the key visual's region, and the type box it leaves: kept ``gap`` from the picture and the format's own
    # insets from the page's edges (by default both are the uniform safe margin)
    kv = {"source": key_visual, "sha256": _sha(key_visual) if key_visual else None}
    gap = fmt.safe_mm
    in_t, in_r, in_b, in_l = fmt.insets()
    if fmt.layout == "cover" and tw < SIDE_BY_SIDE_ASPECT * th:  # upright or near-square: the picture above
        region = (0.0, 0.0, W, b + th * KEY_VISUAL_SHARE)
        band = (tx + in_l, region[3] + gap, tw - in_l - in_r, ty + th - in_b - (region[3] + gap))
    elif fmt.layout == "cover":                                # wide: the picture left, the type right
        region = (0.0, 0.0, b + tw * KEY_VISUAL_SHARE, H)
        band = (region[2] + gap, ty + in_t, tx + tw - in_r - (region[2] + gap), th - in_t - in_b)
    elif fmt.layout == "type":                                 # type: no picture, the stack on the ruled ground
        region = None
        band = (tx + in_l, ty + in_t, tw - in_l - in_r, th - in_t - in_b)
    else:                                                      # info: the words above, the picture closing the page
        top = b + th * (1.0 - INFO_VISUAL_SHARE)
        region = (0.0, top, W, H - top)
        band = (tx + in_l, ty + in_t, tw - in_l - in_r, top - gap - (ty + in_t))
    pic_at = len(nodes)                                        # where the picture is drawn: behind every word
    if region is None:
        kv = {"state": "NOT_IN_THIS_LAYOUT"}
    else:
        _place_picture(fmt, key_visual, region, f, nodes, kv)
    pic_n = len(nodes) - pic_at
    if kv.get("state") == "MISSING":
        row["codes"].append(KEY_VISUAL_MISSING)
    row["key_visual"] = kv
    bx, by, bw, bh = band
    row["type_box_mm"] = [round(v, 3) for v in band]
    cx = bx + bw / 2.0

    # ---- pass 1: the stack, measured
    stack, y = [], 0.0                                         # (kind, y from the stack's top, payload)
    if logo_master is not None:
        from apps.ire import brand_mark
        logo_rec = {"source": logo_master.path, "sha256": logo_master.sha256, "vector_master": True}
        ratio = logo_master.aspect
    else:
        logo_rec = {"source": logo, "sha256": _sha(logo) if logo else None}
        ratio = intrinsic_aspect(logo)
    if ratio is None:
        logo_rec["state"] = "NOT_PLACED"
        row["codes"].append(LOGO_NOT_PLACED)
    else:
        lh = short * LOGO_H_PER_MM
        min_w = (MINIMUM_WIDTH_PX_SCREEN * MM_PER_PX) if fmt.px else MINIMUM_WIDTH_MM_PRINT
        if lh / ratio < min_w:
            lh = min_w * ratio
        lw = lh / ratio
        cap = (brand_mark.cap_band(logo_master) if logo_master is not None
               else measure_cap_ratio(logo) if logo else None)
        cap_ratio = (cap or {}).get("cap_ratio") or 1.0
        clear = clear_space_mm(lh, cap_ratio)
        stack.append(("logo", y + clear, (lw, lh)))
        y += clear + lh + clear
        logo_rec.update(state="PLACED", placed_mm=[round(lw, 3), round(lh, 3)], clear_space_mm=round(clear, 3),
                        cap_ratio=cap_ratio if cap else None,
                        cap_ratio_source="measured" if cap else "UNMEASURED — 1.0 used, the stricter bound (§AL4)",
                        minimum_width_mm=round(min_w, 3), ground=GROUND_HEX)
        if lw + 1e-9 < min_w:
            row["codes"].append(LOGO_BELOW_MINIMUM)
    row["logo"] = logo_rec
    top_y = y                                                  # the stack's height above the name: the logo, its space
    logo_entries = list(stack)

    def words_below(cap_pt):
        """The name at the largest size up to ``cap_pt`` that fits the box's WIDTH, and the words under it: the
        entries, where the stack ends, and the face and size of its lowest line (for its descender)."""
        entries, y2, last2, size2 = [], top_y, (None, 0.0), None
        if copy.headline:
            lines, size2 = _fit_headline(copy.headline, head_face, bw * HEADLINE_MEASURE_SHARE, min(cap_pt, max_pt),
                                         min_pt)
            for i, ln in enumerate(lines):
                y2 += size2 * MM_PER_PT * (1.0 if i == 0 else back_panel.LEADING_EM)
                entries.append(("run", y2, (f"{fmt.key}-headline-{i + 1}", ln, size2, HEADLINE_ROLE)))
            last2 = (head_face, size2)
        if copy.subline:
            sub_pt = max(copy_pt, round((size2 or max_pt) * SUBLINE_SHARE, 2))
            y2 += sub_pt * MM_PER_PT * (1.0 + back_panel.LEADING_EM)
            entries.append(("run", y2, (f"{fmt.key}-subline", copy.subline, sub_pt, COPY_ROLE)))
            last2 = (copy_face, sub_pt)
        if fmt.layout == "info" and copy.body:
            y2 += pitch_mm
            for p, para in enumerate(copy.body):
                for i, ln in enumerate(_wrap(para, copy_pt, copy_face, bw * COPY_MEASURE_SHARE)):
                    y2 += pitch_mm
                    entries.append(("run", y2, (f"{fmt.key}-copy-{p + 1}-{i + 1}", ln, copy_pt, COPY_ROLE)))
                y2 += pitch_mm * 0.5
            last2 = (copy_face, copy_pt)
        height_mm = y2 + _descent_mm(*last2) if last2[0] or last2[1] else y2
        return entries, height_mm, size2

    entries, stack_h, size = words_below(max_pt)
    if copy.headline and stack_h > bh and size is not None and size > min_pt:
        # the name is held to the box's HEIGHT as well as its width: the largest size in its OWN range at which the whole
        # stack fits (a size chosen within the range, never below its floor); if even the floor does not fit, the
        # stack is set at the floor and measured as over — named, never clipped
        lo, hi = min_pt, size
        for _ in range(14):
            mid = (lo + hi) / 2.0
            if words_below(mid)[1] <= bh:
                lo = mid
            else:
                hi = mid
        entries, stack_h, size = words_below(lo)
        row["headline_held_to"] = "the type box's height"
    # [his answer W9] the words still taller than their box at their floors: the box grows into the picture by what
    # they need — a picture above it gives up its foot, a picture below it its top — the picture keeping at least
    # TYPE_BOX_PICTURE_KEEPS of its height and placed again in what it keeps; a layout with no picture beside the box
    # does not grow it (the page's insets stay), and what is left over is measured below
    need = stack_h - bh
    if need > 1e-6 and region is not None and kv.get("state") == "PLACED":
        rx_, ry_, rw_, rh_ = region
        give = min(need, rh_ * (1.0 - TYPE_BOX_PICTURE_KEEPS))
        if ry_ + rh_ <= by + 1e-6:                             # the picture above the box
            region = (rx_, ry_, rw_, rh_ - give)
            band = (bx, by - give, bw, bh + give)
        elif ry_ >= by + bh - 1e-6:                            # the picture below the box
            region = (rx_, ry_ + give, rw_, rh_ - give)
            band = (bx, by, bw, bh + give)
        else:
            give = 0.0
        if give > 0.0:
            moved = []
            _place_picture(fmt, key_visual, region, f, moved, kv)
            nodes[pic_at:pic_at + pic_n] = moved
            bx, by, bw, bh = band
            row["type_box_mm"] = [round(v, 3) for v in band]
            row["type_box_grown"] = {"by_mm": round(give, 3), "rule": "his answer W9: the copy box grows to fit",
                                     "picture_region_mm": [round(v, 3) for v in region]}
    if not copy.headline:
        row["codes"].append(HEADLINE_MISSING)
    else:
        row["headline_pt"] = size
        row["headline_range_pt"] = [round(min_pt, 2), round(max_pt, 2)]
    if fmt.layout == "info" and not copy.body:
        row["copy_note"] = "no copy on the product record — nothing is written for it"
    row["copy_pt"] = copy_pt
    stack = logo_entries + entries

    # ---- pass 2: set in the middle of the type box, each run measured where it is set
    y0 = by + max(0.0, (bh - stack_h) / 2.0)
    for kind, dy, payload in stack:
        if kind == "logo":
            lw, lh = payload
            if logo_master is not None:           # [the owner's second answer of 2026-09-25: drawn from the master]
                nodes.append(brand_mark.mark_node(f"{fmt.key}-logo", logo_master, f.x(cx - lw / 2.0), f.y(y0 + dy),
                                                  f.d(lw), f.d(lh)))
                continue
            nodes.append(image_node(f"{fmt.key}-logo", logo, f.x(cx - lw / 2.0), f.y(y0 + dy), f.d(lw), f.d(lh)))
            continue
        name, text, size_pt, role = payload
        face = _face(role, faces)
        width = _width_mm(text, size_pt, face)
        state = ("NOT_DRAWN" if face is None else "UNMEASURED" if width is None
                 else "HELD" if width <= bw + 1e-6
                 else "OVER_UNDER_TOLERANCE" if width - bw < COPY_OVERRUN_TOLERANCE_MM else "EXCEEDS_BOX")
        row["runs"].append({"name": name, "text": text, "role": role, "face": face, "size_pt": size_pt,
                            "box_width_mm": round(bw, 3), "width_mm": None if width is None else round(width, 3),
                            "state": state})
        nodes.append(TextRun(name=name, text=text, x=f.x(cx), y=f.y(y0 + dy), font=role, size_pt=f.d(size_pt),
                             color=ink, align="center"))
    # [his answer W9] an overrun under COPY_OVERRUN_TOLERANCE_MM is measured, never a hold
    row["vertical"] = {"box_height_mm": round(bh, 3), "stack_height_mm": round(stack_h, 3),
                       "state": ("HELD" if stack_h <= bh + 1e-6
                                 else "OVER_UNDER_TOLERANCE" if stack_h - bh < COPY_OVERRUN_TOLERANCE_MM
                                 else "EXCEEDS_BOX"),
                       "over_mm": round(max(0.0, stack_h - bh), 3)}
    if row["vertical"]["state"] == "EXCEEDS_BOX":
        row["codes"].append(EXCEEDS_BOX)
    for r in row["runs"]:
        code = {"EXCEEDS_BOX": EXCEEDS_BOX, "UNMEASURED": COPY_UNMEASURED, "NOT_DRAWN": COPY_NOT_DRAWN}.get(r["state"])
        if code and code not in row["codes"]:
            row["codes"].append(code)
    group = Group(name=f"format-{fmt.key}", role="artwork", children=[n for n in nodes if n is not None])
    return group, row


def artwork_document(fmt: ArtworkFormat, copy: ArtworkCopy, *, key_visual, logo, title="",
                     logo_master=None) -> tuple[Document, dict]:
    """One format at true size, bleed included — the production page. [``logo_master``: the owner's second answer
    of 2026-09-25 — the approved vector master, when a caller found one on file.]"""
    meta = {"typography_surface": SURFACE_FORMAT, "artwork_format": fmt.key}
    group, row = compose_format(fmt, copy, key_visual=key_visual, logo=logo, faces=_faces(meta),
                                logo_master=logo_master)
    doc = Document(page_w=fmt.page_w, page_h=fmt.page_h, title=title or fmt.label, metadata=meta,
                   root=Group(name="artwork", role="artwork", children=[group]))
    return doc, row


#: CHOSEN: the presentation sheet's margin, the gap between formats, and the height the tallest format is drawn at
SHEET_MARGIN_MM, SHEET_GAP_MM, SHEET_ROW_H_MM = 12.0, 10.0, 180.0


def presentation_document(formats, copy: ArtworkCopy, *, key_visual, logo, title="", extras=(),
                          logo_master=None) -> Document:
    """Every format side by side at ONE common scale (their true relative sizes), each labelled with its size — the
    picture the design's gate shows. The same layout code as the production pages; the measurements are theirs.
    ``extras`` are panels drawn beside the formats at the same scale (the structure the pieces fold into): each a dict
    with its ``key``, ``label``, ``w_mm``, ``h_mm`` and a ``draw(frame)`` that returns its group.
    [``logo_master``: the owner's second answer of 2026-09-25 — the approved vector master, when a caller found one.]"""
    meta = {"typography_surface": SURFACE_SHEET}
    faces = _faces(meta)
    tallest_mm = max([f.page_h for f in formats] + [e["h_mm"] for e in extras])
    s = SHEET_ROW_H_MM / tallest_mm              # a ratio: the sheet's row over the tallest piece, both in millimetres
    label_h = 9.0
    x = SHEET_MARGIN_MM
    top = SHEET_MARGIN_MM + 10.0
    groups = []
    ink = ink_for(Color.from_hex("#FFFFFF"))
    for fmt in formats:
        g, _row = compose_format(fmt, copy, key_visual=key_visual, logo=logo, faces=faces, frame=_Frame(x, top, s),
                                 logo_master=logo_master)
        size = (f"{fmt.px[0]} × {fmt.px[1]} px" if fmt.px else
                f"{fmt.width_mm:g} × {fmt.height_mm:g} mm" + (f" + {fmt.bleed_mm:g} mm bleed" if fmt.bleed_mm else ""))
        lab = TextRun(name=f"label-{fmt.key}", text=f"{fmt.label} · {size}", x=x, y=top + fmt.page_h * s + label_h * 0.7,
                      font=COPY_ROLE, size_pt=7.5, color=ink, align="left")
        groups.append(Group(name=f"sheet-{fmt.key}", role="generic", children=[g, lab]))
        x += fmt.page_w * s + SHEET_GAP_MM
    for e in extras:
        g = e["draw"](_Frame(x, top, s))
        lab = TextRun(name=f"label-{e['key']}", text=f"{e['label']} · {e['w_mm']:g} × {e['h_mm']:g} mm", x=x,
                      y=top + e["h_mm"] * s + label_h * 0.7, font=COPY_ROLE, size_pt=7.5, color=ink, align="left")
        groups.append(Group(name=f"sheet-{e['key']}", role="generic", children=[g, lab]))
        x += e["w_mm"] * s + SHEET_GAP_MM
    page_w = x - SHEET_GAP_MM + SHEET_MARGIN_MM
    page_h = top + SHEET_ROW_H_MM + label_h + SHEET_MARGIN_MM
    heading = TextRun(name="sheet-title", text=title or copy.headline or "Artwork", x=SHEET_MARGIN_MM,
                      y=SHEET_MARGIN_MM + 4.0, font=HEADLINE_ROLE, size_pt=11.0, color=ink, align="left")
    bg = Rect(name="sheet-ground", x=0, y=0, w=page_w, h=page_h, fill=SolidFill(color=Color.from_hex("#FFFFFF")))
    return Document(page_w=page_w, page_h=page_h, title=title or "Artwork", metadata=meta,
                    root=Group(name="presentation", role="artwork", children=[bg, heading, *groups]))


# --- the STRUCTURE a display's pieces fold into: a provisional drawing, never a die (apps/ire/fit_grid.py) ---------
SURFACE_STRUCTURE = "apps/ire/compose_artwork.py::structure_document"
#: CHOSEN: the drawing's margin, the space between the tray's blank and the header card, the header card's two tabs
#: (width, depth), the line weights of a cut and a fold, and the size its labels are set at
STRUCTURE_MARGIN_MM, STRUCTURE_GAP_MM = 15.0, 20.0
HEADER_TAB_MM = (20.0, 12.0)
CUT_MM, FOLD_MM, FOLD_DASH_MM = 0.35, 0.25, (3.0, 2.0)
STRUCTURE_LABEL_PT = 7.0


def structure_size(fit: dict) -> tuple[float, float]:
    """The drawing's page: the tray's blank and the header card side by side, a title above, the labels below."""
    from apps.ire import fit_grid
    x0, y0, x1, y1 = fit_grid.blank_outline(fit)["bbox"]
    hw, hh = fit["header"]["w_mm"], fit["header"]["h_mm"]
    w = STRUCTURE_MARGIN_MM * 2 + (x1 - x0) + STRUCTURE_GAP_MM + hw
    h = STRUCTURE_MARGIN_MM * 2 + 12.0 + max(y1 - y0, hh + HEADER_TAB_MM[1]) + 14.0
    return round(w, 2), round(h, 2)


STRUCTURE_INK_HEX = "#59283A"


def _strokes(f: _Frame):
    """A cut (solid) and a fold (dashed), in the ruled ink, at the frame's scale."""
    from apps.ire.graph import Stroke
    ink = Color.from_hex(STRUCTURE_INK_HEX)
    return (Stroke(color=ink, width_mm=f.d(CUT_MM)),
            Stroke(color=ink, width_mm=f.d(FOLD_MM), dash=(f.d(FOLD_DASH_MM[0]), f.d(FOLD_DASH_MM[1]))))


def _poly(f: _Frame, name, points, stroke, *, ox=0.0, oy=0.0, close=True):
    """A drawn outline: ``points`` in a piece's own millimetres, placed at (ox, oy) on the page, through the frame."""
    from apps.ire.graph import ClosePath, LineTo, MoveTo, Path
    pts = [(f.x(ox + p[0]), f.y(oy + p[1])) for p in points]
    segs = [MoveTo(x=pts[0][0], y=pts[0][1])] + [LineTo(x=x, y=y) for x, y in pts[1:]] + ([ClosePath()] if close else [])
    return Path(name=name, segments=segs, stroke=stroke)


def _label(f: _Frame, name, text, x, y):
    return TextRun(name=name, text=text, x=f.x(x), y=f.y(y), font=COPY_ROLE, size_pt=f.d(STRUCTURE_LABEL_PT),
                   color=Color.from_hex(STRUCTURE_INK_HEX), align="left")


def compose_structure(fit: dict, frame: Optional[_Frame] = None) -> Group:
    """The tray's flat blank — its cut outline solid, its folds dashed — and the header card with its two tabs, each
    dimension labelled, under the one line that says what this drawing is: PROVISIONAL, a converter's die governs."""
    from apps.ire import fit_grid
    f = frame or _Frame()
    w, h = structure_size(fit)
    ol = fit_grid.blank_outline(fit)
    ox, oy = STRUCTURE_MARGIN_MM, STRUCTURE_MARGIN_MM + 12.0          # the blank's top-left on the page
    cut, fold = _strokes(f)

    def poly(name, points, stroke, close=True, dx=0.0, dy=0.0):
        return _poly(f, name, points, stroke, ox=ox + dx, oy=oy + dy, close=close)

    def label(name, text, x, y):
        return _label(f, name, text, x, y)

    t, hd = fit["tray"], fit["header"]
    a = fit["arrangement"]
    nodes = [Rect(name="structure-ground", x=f.x(0), y=f.y(0), w=f.d(w), h=f.d(h),
                  fill=SolidFill(color=Color.from_hex("#FFFFFF"))),
             label("structure-state", fit["structure_state"], STRUCTURE_MARGIN_MM, STRUCTURE_MARGIN_MM + 3.0),
             poly("tray-blank-cut", ol["cut"], cut)]
    nodes += [poly(f"tray-blank-fold-{i + 1}", [p, q], fold, close=False) for i, (p, q) in enumerate(ol["folds"])]
    bx, by, bw, bd = ol["base"]
    nodes += [label("dim-base", f"base {bw:g} × {bd:g} mm (inner)", ox + bx + 2.0, oy + by + bd / 2.0),
              label("dim-back", f"back wall {t['back_h_mm']:g} mm", ox + bx + 2.0, oy + by - t["back_h_mm"] / 2.0),
              label("dim-lip", f"lip {t['lip_h_mm']:g} mm", ox + bx + 2.0, oy + by + bd + t["lip_h_mm"] / 2.0 + 2.0)]
    # the header card: its face, and two tabs that lock into the back wall
    x0, y0, x1, y1 = ol["bbox"]
    hx = STRUCTURE_MARGIN_MM + (x1 - x0) + STRUCTURE_GAP_MM
    hy = oy
    tw_, td_ = HEADER_TAB_MM
    hw, hh = hd["w_mm"], hd["h_mm"]
    card = [(0, 0), (hw, 0), (hw, hh), (hw * 0.75 + tw_ / 2, hh), (hw * 0.75 + tw_ / 2, hh + td_),
            (hw * 0.75 - tw_ / 2, hh + td_), (hw * 0.75 - tw_ / 2, hh), (hw * 0.25 + tw_ / 2, hh),
            (hw * 0.25 + tw_ / 2, hh + td_), (hw * 0.25 - tw_ / 2, hh + td_), (hw * 0.25 - tw_ / 2, hh), (0, hh)]
    nodes.append(poly("header-card-cut", card, cut, dx=hx - ox, dy=hy - oy))
    nodes.append(label("dim-header", f"header card {hw:g} × {hh:g} mm · two tabs into the back wall",
                       hx, hy + hh + td_ + 6.0))
    nodes.append(label("fit-line", f"{a['columns']} × {a['rows']} = {fit['units']} units ({a['empty_places']} empty) · "
                                   f"{fit['clearance_mm']:g} mm around each · board {fit['board_mm']:g} mm (chosen)",
                       STRUCTURE_MARGIN_MM, h - STRUCTURE_MARGIN_MM + 4.0))
    return Group(name="structure", role="structure", children=nodes)


def structure_document(fit: dict) -> Document:
    """The drawing at true size — a page in the print file."""
    w, h = structure_size(fit)
    return Document(page_w=w, page_h=h, title="Structure (provisional)",
                    metadata={"typography_surface": SURFACE_STRUCTURE},
                    root=Group(name="structure-page", role="structure", children=[compose_structure(fit)]))


def file_sha256(path) -> Optional[str]:
    return _sha(path) if path and os.path.exists(path) else None
