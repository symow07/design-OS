"""Compose a Design Graph from the dieline + approved artwork (Phase 1).

This is the bridge from the old "draw straight onto a canvas" components
exporter to the graph-first pipeline: it builds a Document whose structural
content (panel grounds, product typography, cut/fold linework) is NATIVE
editable vector, whose logo rides as a flagged Image node when it is drawn
from its raster (until the Phase-2 asset library replaces it), and
whose info face is a StickerBridge (delegated to the proven trilingual
renderer until it is ported to nodes).

Coordinate system: the dieline engine works in mm, y-down, with the flat
laid out in absolute coords. We shift by the page margin so the graph origin
is the page corner (page_w/h = bleed bounds + margin), matching what the
pdf_ai emitter expects (x*mm, y flipped by page height).
"""
from __future__ import annotations

import re

from apps.dielines.exporters.artwork_layers import component_polygon
from apps.dielines.exporters.info_panel import has_info_content
from apps.ire.graph import (
    ClosePath,
    Color,
    CubicTo,
    Document,
    Group,
    Image,
    LineTo,
    MoveTo,
    Path,
    Rect,
    Segment,
    SolidFill,
    StickerBridge,
    Stroke,
    TextRun, quarter_turn,)

_TINT = "#EFE9E4"
_PAGE_MARGIN_MM = 10.0
_ARTWORK_PANELS = ("front", "back")

#: §BH55 Phase 2 (2026-09-19): THE CARTON FRONT'S TYPE IS CHOSEN AS TYPE — the §Z1(b) guard: a point size must not
#: move when the product's millimetres do (`tests/test_wiq_type_scale_independence.py`, where this composer's name and
#: the line under it were registered as moving). CHOSEN, and said as chosen: the product family's own sizes on the
#: live dropper's front — the name at 9.0 pt (`compose_dropper.py`, `name_min=9.0`) and the line under it at 6.0 pt,
#: the ratio the owner's review looked at, 6.0 under 9.0 (OWNER_REVIEW_QUEUE.md:1995-2028) — both above the 5.0 pt
#: floor for product copy (§W2, LIVE; §BH50(f)(1), LIVE). Before this the name was 7.5 % of its panel's width in
#: points and its line 4.5 %, never measured, and cut at 40 characters: on a gift set's 111 mm carton the name ran
#: across the front panel's folds.
FRONT_NAME_PT = 9.0
FRONT_LINE_PT = 6.0
#: CHOSEN, and said as chosen: the most lines the name's block and the line under it are set in before they are
#: recorded over — the name's block stands above where its one line stood, the line under it below
FRONT_NAME_MOST_LINES = 3
FRONT_LINE_MOST_LINES = 2
#: the measurement of the front's type, on the Document and on the design's record
FRONT_TYPE_KEY = "front_type/1.0"
#: §BH50(f)(3), LIVE: "FRONT COPY: the 5.0 pt floor governs and a copy overrun BLOCKS Gate 2 — text that does not fit
#: is a design problem to solve, not a number to shrink"; a run the instrument could not measure is not passed
FRONT_COPY_EXCEEDS_PANEL = "CARTON_FRONT_COPY_EXCEEDS_PANEL"
#: [his final goal, 2026-10-05 (transcribed at 32e9aaf), C5: "THE INFO IS ONE DESIGNED BLOCK ... Only if it still
#: doesn't fit, STOP and offer: a wider carton, the info printed on the inside, or fewer languages. Never scatter it;
#: never go below the floor."] the carton's label, laid out and measured where it is composed — its levels, its face,
#: its languages — and the code that holds Gate 2 where it cannot stand on the back's sticker at its floors, with the
#: offers measured to hold it. Nothing moves to a side: his review's point 2 ("move a block ... to a side panel") is
#: replaced by his final goal.
BACK_COPY_KEY = "back_copy/1.0"
#: [his final goal, 2026-10-05, B1] what the carton's inside prints, kept on the document and the design's record
INSIDE_KEY = "inside_print/1.0"
LABEL_DOES_NOT_FIT = "CARTON_LABEL_DOES_NOT_FIT"
#: [his final goal, B3: "Sticker (default): the ground runs across the back; the info sits ON TOP as a rounded-rectangle
#: label with a margin."] the sticker stands on the back's safe margin, the label's copy this far inside it
STICKER_PAD_MM = 1.5
STICKER_RADIUS_MM = 2.0
STICKER_PAPER = "#FFFFFF"
#: [his final goal, C5] the fewer languages offered, most first — English always kept: he enters English
FEWER_LANGUAGES = (("en", "es"), ("en", "ar"), ("en",))
#: [his second goal of 2026-10-06, item 2: TRADE_RULES.md B1, G4] the ground's bleed over the glue crease onto the glue
#: flap — the rest of the flap is glued and free of ink
GLUE_BLEED_MM = 3.0
#: [His correction of 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a6b2092): "when the label doesn't fit, the
#: text gets SMALLER. Never move information anywhere else (not inside, not behind the QR, not to another panel) and
#: never drop it. Never widen the carton for text; the "widen" step is removed."] The label shrinks evenly to its 3 pt
#: floor (``label_layout.steps``); where it still does not stand, the design stops by name and says so, with the one
#: offer his choice may take — fewer languages. The carton is never widened for it (his second goal's widening, and its
#: offer "a wider carton", are gone), and nothing is printed inside (gone since that goal).
#: [his review of 119, 2026-10-05, point 1: "LANGUAGES: labels stay trilingual (English, Spanish, Arabic). That is how
#: my company works: I enter English, the system translates."] a piece of his English the label carries without its
#: Spanish or its Arabic — a translation missing, or no Arabic face to set it — holds Gate 2 by name, where the sticker
#: drew the label in fewer languages without a word. The Arabic carries no ingredients, as the house's labels never have
#: (INCI names are international; ``info_panel.build_sticker_blocks``).
LABEL_NOT_TRILINGUAL = "CARTON_LABEL_NOT_TRILINGUAL"
TRILINGUAL_FIELDS = ("description", "ingredients", "how_to_use", "warnings")
FRONT_COPY_UNMEASURED = "CARTON_FRONT_COPY_UNMEASURED"

# stroke widths in mm (points/2.8346): cut 0.8pt, fold 0.5pt, halo 1.6pt
_W_CUT = 0.282
_W_FOLD = 0.176
_W_HALO = 0.564
# CMYK overrides so the emitted .ai carries no RGB operators for the
# technical linework (Gate-2 "no RGB artwork"); RGB stays for screen use.
_CUT = Color.from_hex("#0000FF", cmyk=(1.0, 1.0, 0.0, 0.0))
_FOLD = Color.from_hex("#FF0000", cmyk=(0.0, 1.0, 1.0, 0.0))
_WHITE = Color.from_hex("#FFFFFF", cmyk=(0.0, 0.0, 0.0, 0.0))
_INK_LIGHT = Color.from_hex("#FCF8F5", cmyk=(0.0, 0.02, 0.03, 0.01))


def _concept_motif(map_front):
    """The concept's own motif: the largest shape its front's map traced — what the inside repeats and the flaps carry
    — or None. [His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (3):
    "its flaps/sides repeat 122's line art".] A carton continuing its approved container: the container's own rose
    (``targets.composite.continued_line_art``), whole, in millimetres — never a shape traced from the carton's photo."""
    continued = (map_front or {}).get("continued")
    if continued is not None:
        return continued["rose"]["cubics"] if continued.get("rose") else None   # else the mark: never the photo's shape
    # [His review of 127, 130, 131 and 132, 2026-10-15, C (2): "NO BROKEN MOTIFS: a motif that can't be traced cleanly
    # (132's side and flap flower, which looks like a fidget spinner) is redrawn flat and traced again; never printed
    # broken."] never a shape left out as broken; one redrawn flat, its redraw's clean outlines in one ink; never ONE
    # ink of a shape the picture prints in several — 132's flower's gold alone, its white petals cut out of it, was the
    # spinner — but its inks together, the shape's whole outline
    held = (map_front or {}).get("shapes") or {}
    shapes = [sh for sh in held.get("shapes") or []
              if not sh.get("undrawn") and (sh.get("flat") is None or sh.get("flat_mono") is not None)]
    # … and a motif of line art standing in one place on the front (never the pattern run all round it), redrawn
    # flat: its clean outlines (132's lily, read as a motif in its cartouche)
    wraps = [id(line) for line in wrapping_pattern(map_front)]
    shapes += [dict(line, box=line["flat"]["box"]) for line in held.get("lines") or []
               if line.get("flat_mono") is not None and not line.get("undrawn") and id(line) not in wraps]
    if not shapes:
        return None
    sh = max(shapes, key=lambda sh: (sh["box"][2] - sh["box"][0]) * (sh["box"][3] - sh["box"][1]))
    if sh.get("flat_mono") is not None:
        return outline_cubics(sh["flat_mono"]["outlines"])
    return sh["cubics"] + [poly for layer in sh.get("layers") or [] for poly in layer["cubics"]]


def outline_cubics(outlines: dict) -> list:
    """potrace's outlines of a flat redraw (``flat_motif.trace_flat``: ``{"svg", "frame"}``) as a traced shape's cubics —
    each ring its own polygon, ``[[start], [c1x, c1y, c2x, c2y, x, y], …]`` in the product's fractions, a line a cubic
    along itself — as ``inside_print.unit_motif`` reads them."""
    from apps.ire.compose_container import _traced_segments
    segs, _bounds = _traced_segments(outlines, lambda p: (float(p[0]), float(p[1])))
    polys, ring, at = [], None, None
    for g in segs:
        if isinstance(g, MoveTo):
            if ring and len(ring) > 2:
                polys.append([ring])
            at = (float(g.x), float(g.y))
            ring = [[at[0], at[1]]]
        elif isinstance(g, CubicTo) and ring is not None:
            ring.append([float(g.x1), float(g.y1), float(g.x2), float(g.y2), float(g.x), float(g.y)])
            at = (float(g.x), float(g.y))
        elif isinstance(g, LineTo) and ring is not None:
            ring.append([at[0], at[1], float(g.x), float(g.y), float(g.x), float(g.y)])
            at = (float(g.x), float(g.y))
    if ring and len(ring) > 2:
        polys.append([ring])
    return polys


def wrapping_pattern(map_front) -> list:
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (1): "THE PATTERN WRAPS THE WHOLE PACK: when the concept shows
    a pattern running all round (132's majolica), it covers every panel of the carton (sides, back behind the sticker,
    flaps), never only the front."] The front's line-art parts that run all round, from the front's own data: each
    drawn as a field — from its flat redraw (traced in its colours or as outlines) or from a continued container's art —
    over ROUND_FIELD_SHARE of the front or more. A pattern that covers most of the front edge to edge is printed all
    over the pack, as its concept's own layout picture draws 132's (every panel, every flap); a motif standing in one
    place on the front (under that share) is not a pattern, and stays there."""
    out = []
    for line in ((map_front or {}).get("shapes") or {}).get("lines") or []:
        if line.get("undrawn") or line.get("drawn_with"):
            continue                # [his goal after the pitch page, B (10)] a field drawn once, by the part it is
        flat, continued = line.get("flat") or {}, line.get("continued") or {}
        if flat.get("state") == "TRACED" and flat.get("box"):
            box = flat["box"]
        elif continued.get("part_box"):
            box = continued["part_box"]
        else:
            continue
        x0, y0 = max(0.0, float(box[0])), max(0.0, float(box[1]))
        x1, y1 = min(1.0, float(box[2])), min(1.0, float(box[3]))
        if (x1 - x0) * (y1 - y0) >= ROUND_FIELD_SHARE:
            out.append(line)
    return out


def _motif_aspect(map_front, map_panel) -> float:
    """The aspect ``_concept_motif``'s shape is read at: a traced shape's, in the front's fractions, the front's height
    over its width; a continued container's rose, drawn in millimetres, 1."""
    if ((map_front or {}).get("continued") or {}).get("rose"):
        return 1.0
    return (map_panel.height / map_panel.width) if map_panel is not None else 1.0


def _motif_ink(map_front):
    """[His test blocker on design 123, (3)] a continued container's rose in the container's own ink; None — the
    design's own tone — for every other design."""
    continued = (map_front or {}).get("continued") or {}
    return continued.get("ink") if continued.get("rose") else None


def compose_components_graph(
    coords, *,
    tint: str = _TINT, logo_path: str | None = None,
    product_name: str = "", subtitle: str = "", panel_info: dict | None = None,
    page_margin_mm: float = _PAGE_MARGIN_MM,
    safe_margin_mm: float = 4.0,
    logo_master=None,
    map_front: dict | None = None,
    inside: dict | None = None,
    turn_faces: bool = False,
) -> Document:
    """Build the Design Graph for the design-on-dieline composition.

    [THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    switch the mark to it so gold foil can print." ``logo_master`` — the approved vector master (apps/ire/brand_mark.py)
    a caller found on file — draws each panel's mark from it; None, every call before it, draws the raster.]

    [His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its own
    for every new design, for a wand vial and a carton".] ``map_front`` — the carton's own concept picture's map, its
    shapes traced and its type lines given their words (``targets.packaging.carton_map_front``) — draws the FRONT panel
    as the picture draws it (``_map_front_panel``) in place of its ruled mark and ruled type; every other panel as
    before. None, every call before it, draws every panel as before.

    [His final goal, 2026-10-05 (transcribed at 32e9aaf), B1: "INSIDE AND TOP PRINTING."] ``inside`` — what the inside
    prints (``apps.ire.inside_print.plan``) — draws the sheet's inside on the document's second artboard and designs
    the flaps; None, every call before it, draws the one artboard as before.

    [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (2): "A palette or compact lies flat: its box's front is the
    lid's face (landscape)."] ``turn_faces`` — the box lies flat: its die stands as ever (the tucks on its narrow ends),
    and its front and back are laid out as they are seen, wide and short, upright, then turned onto the die
    (``graph.quarter_turn``); a part of the front is not continued round a box that lies flat (said on the record).
    False, every call before it, draws every face as the die stands."""
    info = panel_info or {}
    has_info = has_info_content(info)

    min_x, min_y, max_x, max_y = coords.bleed_polygon.bounds
    vx = min_x - page_margin_mm
    vy = min_y - page_margin_mm
    vw = (max_x - min_x) + 2 * page_margin_mm
    vh = (max_y - min_y) + 2 * page_margin_mm + 8.0   # caption band, as before

    def gx(x: float) -> float:
        return x - vx

    def gy(y: float) -> float:
        return y - vy

    tint_c = Color.from_hex(tint)
    if map_front and map_front.get("ground"):
        # [his review of 119, 2026-10-05, point 3: "One ground all round the carton ... The back panel must match the
        # other panels."] the concept's own ground on every panel, flap and the glue tab
        tint_c = Color.from_hex(map_front["ground"])

    display = [p for p in coords.panels if p.name in _ARTWORK_PANELS]
    info_panel = next((p for p in display if p.name == "back"), None) if has_info else None
    art_panels = [p for p in display if p is not info_panel]
    # [his go of 2026-10-02] the front drawn from its concept's map; the other art panels ruled, as before
    map_panel = next((p for p in art_panels if p.name == "front"), None) if map_front else None
    ruled_panels = [p for p in art_panels if p is not map_panel]

    # --- Background: silhouette + per-panel grounds -------------------------
    # [his final goal, B2: "The glue area marked"] the glue tab's face is glued: no ink on it — [his second goal of
    # 2026-10-06, item 2: the trade's rules B1, G4] past the bleed the ground runs over the glue crease, so no white
    # shows at the box's edge if the die shifts; the rest of the flap, where the glue goes, stays free of ink
    _ground = coords.cut_polygon
    if getattr(coords, "glue_tab_polygon", None) is not None:
        from shapely.geometry import box as _box
        _tab = coords.glue_tab_polygon
        _tx0, _ty0, _tx1, _ty1 = _tab.bounds
        _no_ink = _tab.difference(_box(_tx1 - GLUE_BLEED_MM, _ty0 - 1.0, _tx1 + 1.0, _ty1 + 1.0))
        _left = coords.cut_polygon.difference(_no_ink.buffer(0.01)) if not _no_ink.is_empty else coords.cut_polygon
        _ground = max(getattr(_left, "geoms", [_left]), key=lambda g: g.area)
    bg_children: list = [
        Path(name="silhouette", fill=SolidFill(color=tint_c),
             segments=_poly_segments(_ground.exterior.coords, gx, gy)),
    ]
    for p in display:
        # [his go of 2026-10-02; his review of 119, 2026-10-05, point 3] every panel on the one ground — the back too,
        # where a paper of its own (#FCF8F5) was laid under the sticker
        bg_children.append(Rect(
            name=f"panel-{p.name}", x=gx(p.x), y=gy(p.y), w=p.width, h=p.height,
            fill=SolidFill(color=tint_c)))
    background = Group(name="Background", role="background", children=bg_children)
    # [his final goal, 2026-10-05, B1: "The flaps carry design (logo or pattern)."]
    flaps = []
    if inside is not None:
        # [his goal of 2026-10-06, item 10] the flaps carry the concept's own motif, else the mark — never a pattern
        # the design never had
        from apps.ire.inside_print import flap_nodes
        flaps = flap_nodes(coords, gx, gy, inside, ground_hex=tint_c.to_hex(), logo_master=logo_master,
                           motif_cubics=_concept_motif(map_front), motif_aspect=_motif_aspect(map_front, map_panel),
                           safe_mm=safe_margin_mm, motif_ink=_motif_ink(map_front),
                           motif_cap_mm=max(((map_front or {}).get("continued") or {}).get("rose", {}).get("mm") or [0])
                           or None)
    # [His review of 127, 130, 131 and 132, 2026-10-15, C (1): "it covers every panel of the carton (sides, back behind
    # the sticker, flaps)"] where the front's pattern runs all round, the flaps carry the pattern itself
    # (``pattern_flaps``, below) — the lid keeps its mark over it; no motif stamped on the pattern
    wraps = bool(wrapping_pattern(map_front)) and map_panel is not None and not turn_faces
    if wraps:
        flaps = [n for n in flaps if str(getattr(n, "name", "")) == "lid-mark"]

    # --- Product artwork: none is placed -----------------------------------
    # [The clean-up of 2026-10-04 (E2), approved by the owner: the motif placed on every panel and flap is removed —
    # no caller had passed one since the owner's finding on design 119.] The group stands, empty, so every reader that
    # finds the document's groups by role finds it as before.
    panels_group = Group(name="Product", role="product", children=[])

    # --- Logo (flagged raster) ----------------------------------------------
    # [his goal of 2026-10-13, (2)] a box lying flat: its plain front and back laid out as they are seen (their mark and
    # their name), then turned onto the die with them
    seen_ruled = [_seen_flat(p) if (turn_faces and p.name in _FLAT_SEEN) else p for p in ruled_panels]
    logo_nodes = _logo_nodes(seen_ruled, logo_path, gx, gy, logo_master=logo_master)
    map_children: list = []
    if map_panel is not None:
        notch = (getattr(coords, "derived", None) or {}).get("thumb_notch") or {}
        notch_mm = float(notch["r"]) + 1.0 if notch.get("panel") == "front" else None
        # [his goal of 2026-10-10, item 6] its soft rooms in the carton's own ground where its map reads none
        # [his goal of 2026-10-13, (2)] a box lying flat: the front laid out as it is seen, the notch at its right
        face = _seen_flat(map_panel) if turn_faces else map_panel
        map_children, map_logo, map_record = _map_front_panel(
            dict(map_front, room_ground=tint_c.to_hex()), face, gx, gy, logo_path, logo_master, product_name,
            safe_mm=safe_margin_mm,
            top_mm=None if turn_faces else notch_mm, right_mm=notch_mm if turn_faces else None)
        if turn_faces:
            turn = quarter_turn(face.width, face.height, gx(map_panel.x), gy(map_panel.y))
            map_children = [Group(name="front, laid out as the box lies", role="decoration", children=map_children,
                                  turn=turn)]
            map_logo = [Group(name="logo-front, as the box lies", role="logo", children=map_logo, turn=turn)] \
                if map_logo else []
            map_record["turned"] = {"why": "the box lies flat: its front is laid out as it is seen and turned onto the "
                                           "die", "seen_mm": [round(face.width, 2), round(face.height, 2)]}
        logo_nodes += map_logo
    # [his test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (1): "Every
    # panel is drawn from it."] the back and the sides its layout picture gives, each from its own map; one it does not
    # give continues the front (his (2)), said
    layout = ((map_front or {}).get("panels") or {}) if map_panel is not None else {}
    by_name = {p.name: p for p in coords.panels}
    drawn_panels, panel_records, typed_sides = [], [], set()
    for name, pm in sorted(layout.items()):
        p = by_name.get(name)
        if p is None:
            continue
        if "continues" in pm:
            panel_records.append({"panel": name, "drawn_from": "continues the front: %s" % pm["continues"]})
            continue
        seen = _seen_flat(p) if turn_faces else p
        kids, logos, rec = _map_front_panel(pm, seen, gx, gy, None, logo_master, product_name, safe_mm=safe_margin_mm,
                                            panel_name=name, ruled_mark=False)
        if turn_faces:                      # [his goal of 2026-10-13, (2)] as the box lies, turned onto the die
            turn = quarter_turn(seen.width, seen.height, gx(p.x), gy(p.y))
            kids = [Group(name="%s, laid out as the box lies" % name, role="decoration", children=kids, turn=turn)]
            logos = [Group(name="logo-%s, as the box lies" % name, role="logo", children=logos, turn=turn)] \
                if logos else []
        # clipped to the panel between the body's own folds: what it runs to its foot never reaches a flap
        top, foot = max(p.y, coords.body_top_y), min(p.y + p.height, coords.body_bottom_y)
        x0, y0, y1 = gx(p.x), gy(top) + 0.05, gy(foot) - 0.05
        drawn_panels.append(Group(name="Map %s" % name, role="decoration", children=kids, clip=[
            MoveTo(x=x0, y=y0), LineTo(x=x0 + p.width, y=y0), LineTo(x=x0 + p.width, y=y1), LineTo(x=x0, y=y1),
            ClosePath()]))
        logo_nodes += logos
        panel_records.append(rec["front_type"])
        if rec["front_type"]["typed"]:
            typed_sides.add(name)
    logo_group = Group(name="Logo", role="logo", children=_turned_by_panel(
        logo_nodes, seen_ruled, gx, gy, lambda n: n.name[len("logo-"):] if n.name.startswith("logo-") else None, "logo")
        if turn_faces else logo_nodes)
    # [the owner's finding on design 119, 2026-10-03: "sides, back and flaps continue the concept's own ground, colours
    # and graphics"] a part the front's picture runs edge to edge continues round the carton at its own rows
    # [his goal of 2026-10-13, (2)] never round a box lying flat: its front's rows run along the die, not across it
    continued = _continued_nodes(map_front, coords.panels, gx, gy) if map_panel is not None and not turn_faces else []
    if wraps:
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (1)] the front's pattern on every flap and tuck, under
        # the lid's mark
        patterned = pattern_flaps(map_children, coords, gx, gy)
        flaps = patterned + flaps
        map_record["round_the_pack"] = {
            "parts": [line["part"] for line in wrapping_pattern(map_front)], "flaps": len(patterned),
            "flaps_named": [n.name[len("flap-"):-len("-pattern")] for n in patterned],
            "why": "the front's pattern covers %g of it or more, edge to edge: it is printed all round the pack — sides, "
                   "back under the sticker, flaps and tucks — never the glue tab" % ROUND_FIELD_SHARE}

    # --- Typography (native live text), SET AS TYPE and MEASURED (§BH55 Phase 2) ------------------------
    # in the faces the emitter draws this document with; the logo's foot, per panel, back in dieline millimetres
    from apps.ire.compose_artwork import _faces
    type_children, front_type = _type_nodes(
        seen_ruled, product_name, subtitle, tint_c, gx, gy, faces=_faces({"has_info": has_info}),
        safe_mm=safe_margin_mm, logo_bottoms={n.name[len("logo-"):]: n.y + vy + n.h for n in logo_nodes
                                              if getattr(n, "type", "") != "group"})
    if turn_faces:                          # [his goal of 2026-10-13, (2)] the plain front's name, turned with its mark
        type_children = _turned_by_panel(type_children, seen_ruled, gx, gy, lambda n: (
            n.print_scope.surface[len("carton-"):] if getattr(n, "print_scope", None) is not None
            and str(n.print_scope.surface).startswith("carton-") else None), "typography")
    # [his final goal, 2026-10-05, C5] the label laid out as one block on the back's sticker — or stopped with offers
    label_plan = None
    if info_panel is not None:
        # [his goal of 2026-10-13, (2)] a box lying flat: its label laid out on the back as it is seen
        label_plan = plan_back_copy(info, [_seen_flat(p) if (turn_faces and p.name == "back") else p
                                           for p in coords.panels], safe_margin_mm, coords=coords)
    scallops, scallop_record = [], None
    if map_panel is not None:
        # [the owner's finding on design 119, 2026-10-03] his brief's side copy on both sides, in the front's own ink —
        # [his final goal, C5: "Side panels do ONE job: name, size and brand graphics."] and nothing of the label
        side_nodes, side_record = _side_design_nodes(map_front, map_record, [] if turn_faces else map_children,
                                                     [p for p in coords.panels if p.name not in typed_sides], gx, gy,
                                                     safe_margin_mm, faces=_faces({"has_info": has_info}),
                                                     logo_master=logo_master, product_name=product_name,
                                                     logo_path=logo_path, layout=layout,
                                                     motif_aspect=map_panel.height / map_panel.width)
        type_children += side_nodes
        # [his test findings on design 123, (2)] the front's field and its scalloped band round every panel of its row,
        # kept clear of the type each side sets
        if not turn_faces:              # [his goal of 2026-10-13, (2)] never round a box lying flat — said on its record
            continued += _continued_round(map_children, coords.panels, gx, gy,
                                          body=(coords.body_top_y, coords.body_bottom_y),
                                          holes=_side_type_holes(side_nodes), layout=layout)
            # [His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 5: "SCALLOP BAND: messy and inconsistent. Draw ONE continuous scallop: every arc the same size, clean at panel edges, aligned across every fold and round the whole carton."]
            scallops, map_children, scallop_record = scallop_round(map_children, coords.panels, gx, gy,
                                                                   body=(coords.body_top_y, coords.body_bottom_y))
        else:
            map_record["not_round_a_flat_box"] = "the front's parts are not continued round a box that lies flat"
        front_type["panels"] += side_record["panels"] + panel_records
        front_type["codes"] += [c for r in panel_records for c in r.get("codes") or []]
        front_type["codes"] += side_record["codes"]
        # [his go of 2026-10-02] the front's type set where its picture sets it, measured inside its panel
        front_type["panels"].insert(0, map_record["front_type"])
        if map_record.get("round_the_pack"):
            # [His review of 127, 130, 131 and 132, 2026-10-15, C (1)] on the drawing's record: the pattern printed all
            # round the pack, and on which flaps
            front_type["round_the_pack"] = map_record["round_the_pack"]
        front_type["codes"] = map_record["front_type"]["codes"] + front_type["codes"]
    type_group = Group(name="Typography", role="typography", children=type_children)

    # --- Info face: the sticker, and the label on it -----------------------
    info_children: list = []
    if info_panel is not None:
        # [his final goal, 2026-10-05, C5 and B3] the label, one block, on its sticker over the back's ground — the
        # default rounded one, his custom one, or none where he chose it printed on the panel — in the front's ink that
        # stands out most from what it stands on (the ground's colour on a dark sticker)
        from apps.ire import back_info
        layout = label_plan["layouts"]["back"]
        style = layout["style"]
        back = next(p for p in coords.panels if p.name == "back")
        die_back = back
        if turn_faces:                       # [his goal of 2026-10-13, (2)] the label as the box lies, turned onto the die
            back = _seen_flat(back)
        paper = STICKER_PAPER
        if style.get("mode") == "printed":
            paper = tint_c.to_hex()
        ink = contrast_ink(map_front, Color.from_hex(paper)).to_hex() if map_panel is not None else None
        if layout["sticker_mm"] is not None:
            sx, sy, sw, sh = layout["sticker_mm"]
            if style.get("mode") == "custom":
                deep = contrast_ink(map_front, Color.from_hex(STICKER_PAPER)).to_hex() if map_panel is not None \
                    else "#59283A"
                paper, ink = back_info.colours(style, tint_c.to_hex(), deep)
                info_children.append(Path(
                    name="sticker", segments=back_info.outline(style, gx(back.x + sx), gy(back.y + sy), sw, sh),
                    fill=SolidFill(color=Color.from_hex(paper)),
                    stroke=Stroke(color=Color.from_hex(ink), width_mm=back_info.BORDER_MM)
                    if style.get("border") in ("thin", "double") else None))
                if style.get("border") == "double":
                    inset = 4 * back_info.BORDER_MM
                    info_children.append(Path(
                        name="sticker-inner-border", stroke=Stroke(color=Color.from_hex(ink), width_mm=back_info.BORDER_MM),
                        segments=back_info.outline(style, gx(back.x + sx) + inset, gy(back.y + sy) + inset,
                                                   sw - 2 * inset, sh - 2 * inset)))
            else:
                info_children.append(Rect(name="sticker", x=gx(back.x + sx), y=gy(back.y + sy), w=sw, h=sh,
                                          radius_mm=STICKER_RADIUS_MM, fill=SolidFill(color=Color.from_hex(paper))))
        info_children.append(StickerBridge(name="label", x=gx(back.x), y=gy(back.y), w=back.width, h=back.height,
                                           info=info, ground=paper, layout=layout, ink=ink))
        if turn_faces:
            info_children = [Group(name="the label, laid out as the box lies", role="info", children=info_children,
                                   turn=quarter_turn(back.width, back.height, gx(die_back.x), gy(die_back.y)))]
    info_group = Group(name="Info", role="info", children=info_children)

    # --- [his final goal, 2026-10-05, B2] the die on its own layers, and the guides ----------------------------------
    cut_nodes, crease_nodes = _structure_layers(coords, gx, gy)
    die = [Group(name="CUT", role="structure", children=cut_nodes),
           Group(name="CREASE", role="structure", children=crease_nodes),
           *_guide_layers(coords, gx, gy, safe_margin_mm)]

    root = Group(name="Artwork", role="artwork", children=[
        background, *([Group(name="Flaps", role="decoration", children=flaps)] if flaps else []), panels_group,
        *([Group(name="Continued round the carton", role="decoration", children=continued)] if continued else []),
        *([Group(name="Map front", role="decoration", children=map_children)] if map_children else []),
        *drawn_panels,
        # [his goal of 2026-10-10, item 5] the one scallop round the whole row, over every panel's own drawing
        *([Group(name="Scallop round the carton", role="decoration", children=scallops)] if scallops else []),
        logo_group, type_group, info_group, *die,
    ])
    # [his rule 1 for 119 and every design, 2026-10-05: "the Arabic ملمّع as my brief writes it"] the carton keeps its
    # Arabic marks — the shadda of his brief's ملمّع was shaped away by the exempt drawer this document is drawn on
    from apps.ire.emitters.pdf_ai import ARABIC_MARKS_KEY
    inside_root = None
    if inside is not None:
        # [his final goal, B1: "Two artboards, OUTSIDE and INSIDE."] the inside, its pattern following his reference and
        # his words, else the concept's own traced shape — never the label (his second goal of 2026-10-06, item 1)
        from apps.ire.inside_print import inside_group
        motif = _concept_motif(map_front)
        inside_root = inside_group(coords, gx, gy, inside, motif_cubics=motif,
                                   motif_aspect=_motif_aspect(map_front, map_panel),
                                   structure=cut_nodes + crease_nodes)
    return Document(page_w=vw, page_h=vh, title="BBROSE design",
                    metadata={"has_info": has_info, FRONT_TYPE_KEY: front_type, ARABIC_MARKS_KEY: True, LAYERS_KEY: True,
                              **({BACK_COPY_KEY: label_plan["record"]} if label_plan else {}),
                              **({INSIDE_KEY: dict(inside)} if inside is not None else {}),
                              **({"map_front": map_record} if map_panel is not None else {}),
                              **({SCALLOP_SCHEMA: scallop_record} if scallop_record else {}),
                              # [his goal of 2026-10-10, item 6] the front's own faces, for the files to set it in
                              **({"front_faces": map_front["front_faces"]}
                                 if map_panel is not None and map_front.get("front_faces") else {})}, root=root,
                    inside=inside_root)


#: [the owner's finding on design 119, 2026-10-03] the panels a front's edge-to-edge part continues across, from each of
#: its sides: the panel beside it, and round the back to the glue tab
CONTINUED_FROM = {"left": ("side_left", "back"), "right": ("side_right",)}   # [his final goal, B2] never the glue tab


def _continued_nodes(map_front: dict, panels, gx, gy) -> list:
    """[The owner's finding on design 119, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7): "Every panel
    is vector, drawn from the concept's map: front as the concept shows it; sides, back and flaps continue the concept's
    own ground, colours and graphics".] Each band and rule the front's picture runs edge to edge
    (``concept_design_map.trace_band`` / ``trace_rule``: ``edges``) continued flat, in its own colour, across the panels
    beside that edge (CONTINUED_FROM) at the rows where it meets it — the band's fill, the rule's ink."""
    shapes = map_front.get("shapes") or {}
    by_name = {p.name: p for p in panels}
    nodes = []
    # [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010)] and a solid shape it runs edge to edge (a scalloped band)
    # continued as a band is, in its own colour
    # [his test findings on design 123, (2): "the scallop band runs all the way round"] a solid shape run edge to edge
    # continues round as its own shape (``_continued_round``) — flat rows only for a band the picture prints flat
    across = shapes.get("bands") or []
    for i, band in enumerate(across):
        edges = band["edges"] if isinstance(band.get("edges"), dict) else {}
        for side, rows in sorted(edges.items()):
            for name in CONTINUED_FROM.get(side, ()):
                p = by_name.get(name)
                if p is None or not band.get("fill"):
                    continue
                a, b = float(rows[0]), float(rows[1])
                nodes.append(Rect(name="continued-band-%d-%s" % (i, name), x=gx(p.x), y=gy(p.y + a * p.height),
                                  w=p.width, h=(b - a) * p.height, fill=SolidFill(color=Color.from_hex(band["fill"]))))
    for i, rule in enumerate(shapes.get("rules") or []):
        _x0, y0, _x1, y1 = rule["drawn_box"] if "drawn_box" in rule else rule["box"]
        ink = rule["ink_shade"] if rule.get("ink_shade") else rule.get("ink")
        for side in rule.get("edges") or []:
            for name in CONTINUED_FROM.get(side, ()):
                p = by_name.get(name)
                if p is None or not ink:
                    continue
                nodes.append(Rect(name="continued-rule-%d-%s" % (i, name), x=gx(p.x), y=gy(p.y + y0 * p.height),
                                  w=p.width, h=(y1 - y0) * p.height, fill=SolidFill(color=Color.from_hex(ink))))
    return nodes


#: [His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (2): "Where a
#: panel still has nothing from a picture, it CONTINUES the front: Garden Wrap's rose field runs across every panel
#: unbroken; the scallop band runs all the way round ... the back keeps the same ground and pattern (faint), with the
#: info sticker on top."] the panels round the carton the front continues on — its row, never the glue tab (his final
#: goal, B2) — a part of line art over this share of the front its field, run round; and the field's strength on the
#: back, under the sticker
ROUND_PANELS = ("back", "side_left", "side_right")
ROUND_FIELD_SHARE = 0.5
BACK_FIELD_OPACITY = 0.35
#: [His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 5: "SCALLOP BAND: messy and inconsistent. Draw ONE continuous scallop: every arc the same size, clean at panel edges, aligned across every fold and round the whole carton."]
#: the panels of the body's row the one scallop runs round, left to right as the die lays them; a band whose arcs cannot
#: be read keeps its picture's height and takes arcs this share of it wide, this share of it high
SCALLOP_ROW = ("back", "side_left", "front", "side_right")
SCALLOP_FALLBACK_PITCH = 1.6
SCALLOP_FALLBACK_RISE = 0.35
#: how finely a band's traced edge is read: its curves walked in this many steps, its edge binned this many mm across
SCALLOP_CURVE_STEPS = 12
SCALLOP_BIN_MM = 0.25
SCALLOP_STEP_MM = 0.2
#: … and an arc's top read where its edge stands within this share of the band's depth from its highest point
SCALLOP_TOP_SHARE = 0.6
#: … across the front's width less this share at each edge
SCALLOP_EDGE_SHARE = 0.08
#: a scallop's arcs are bubbles: never flatter than this share of their width high (Garden Wrap's concept draws them
#: 0.37; its traced outline, the two rows of arcs overlapping, reads them 0.12)
SCALLOP_MIN_RISE = 0.35
#: a quarter ellipse's handle
SCALLOP_K = 0.5523


def _shift_x(value, dx: float):
    """[His goal of 2026-10-10, item 9: "FRONT PATTERN is mirrored left-right (a damask): keep the concept's organic garden, never mirrored."] A node's dump moved ``dx`` millimetres across the page — every point's x, a box's left —
    never turned over."""
    if isinstance(value, dict):
        out = {k: _shift_x(v, dx) for k, v in value.items()}
        for key in ("x", "x1", "x2"):
            if isinstance(value.get(key), (int, float)):
                out[key] = float(value[key]) + dx
        return out
    if isinstance(value, list):
        return [_shift_x(v, dx) for v in value]
    return value


def _mirror_x(value, fold: float):
    """A node's dump mirrored across the vertical line x = ``fold`` (page millimetres): every point's x, a box's left."""
    if isinstance(value, dict):
        out = {k: _mirror_x(v, fold) for k, v in value.items()}
        for key in ("x", "x1", "x2"):
            if isinstance(value.get(key), (int, float)):
                out[key] = 2.0 * fold - float(value[key])
        if value.get("type") == "rect" and isinstance(value.get("w"), (int, float)):
            out["x"] = 2.0 * fold - float(value["x"]) - float(value["w"])
        return out
    if isinstance(value, list):
        return [_mirror_x(v, fold) for v in value]
    return value


def _round_parts(map_children: list, front, gx, gy) -> tuple:
    """The front's parts that continue round the carton, each as drawn on the front: ``(its field — each path of a line
    art part over ROUND_FIELD_SHARE of the front, never the bloom laid on it —, each solid shape it runs edge to edge
    — the scalloped band —)``."""
    fx0, fx1 = gx(front.x), gx(front.x + front.width)
    area = front.width * front.height
    field, bands = [], []

    def bounds(segs):
        xs = [float(g.x) for g in segs if hasattr(g, "x")]
        ys = [float(g.y) for g in segs if hasattr(g, "y")]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else None

    def drawn_segments(node):
        if isinstance(node, Path):
            return list(node.segments)
        return [g for c in getattr(node, "children", None) or [] for g in drawn_segments(c)]

    def walk(nodes):
        for n in nodes or []:
            name = str(getattr(n, "name", ""))
            if isinstance(n, Group) and name.startswith(("lineart-map-", "lineart-gold-map-")):
                box = bounds(n.clip) if n.clip else bounds(drawn_segments(n))
                if box and (box[2] - box[0]) * (box[3] - box[1]) >= ROUND_FIELD_SHARE * area:
                    field.extend(c for c in n.children if isinstance(c, Path) and not c.name.endswith("-bloom"))
                    # [His review of 127, 130, 131 and 132, 2026-10-15, C (1)] a pattern traced in its own colours
                    # (``lid_art.art_group``: its lines and its illustration, each a group of its own) runs round too —
                    # 132's majolica was drawn so, and found no path here: its sides, back and flaps were left grey
                    field.extend(c for c in n.children if isinstance(c, Group))
                continue
            if isinstance(n, Path) and name.startswith("shape-map-"):
                box = bounds(n.segments)
                if box and box[0] < fx0 and box[2] > fx1:
                    bands.append(n)
                continue
            walk(getattr(n, "children", None))
    walk(map_children)
    return field, bands


#: [His test findings on design 123, 2026-10-09, (2) and (4): "never over the pattern so the small copy gets lost"] a
#: side's line of type stood on end kept clear of the field run round it by this share of its letters' height each side
#: (the front's small copy is kept clear so, ``compose_container.SMALL_COPY_PAD``)
ROUND_TYPE_PAD = 0.35


def _side_type_holes(side_nodes: list) -> dict:
    """``{panel: [(x0, y0, x1, y1) page mm]}`` — where each line of type a side sets stands, stood on end and reading up
    from its foot (``_side_design_nodes``): its letters' height across, its length up from its foot, padded by
    ROUND_TYPE_PAD of their height."""
    from apps.ire.back_panel import MM_PER_PT
    from apps.ire.compose_container import name_width_estimate_mm
    holes = {}
    for n in side_nodes:
        name = str(getattr(n, "name", ""))
        m = re.match(r"side-(?:name|copy)-(side_left|side_right)", name)
        if m is None or not isinstance(n, TextRun):
            continue
        tall = float(n.size_pt) * MM_PER_PT
        long_ = name_width_estimate_mm(n.text, float(n.size_pt))
        pad = ROUND_TYPE_PAD * tall
        holes.setdefault(m.group(1), []).append((n.x - 0.8 * tall - pad, n.y - long_ - pad, n.x + 0.3 * tall + pad,
                                                 n.y + pad))
    return holes


def _continued_round(map_children: list, panels, gx, gy, body: tuple | None = None,
                     holes: dict | None = None, layout: dict | None = None) -> list:
    """[His test findings on design 123, (2).] The front continued round the carton on each panel of its row
    (ROUND_PANELS): its field, clipped to the panel between the body's own folds (``body``: its top and its foot — a
    side's panel runs past the fold onto its dust flap); the field faint on the back (BACK_FIELD_OPACITY), where the
    sticker is laid over it.
    [His goal of 2026-10-10, item 9: "FRONT PATTERN is mirrored left-right (a damask): keep the concept's organic garden, never mirrored."]
    The field is MOVED onto each panel, never mirrored across its fold: the left side shows the garden's right part, the
    right side its left part, the back the whole of it — the concept's organic garden, as it grows, on every panel.
    [His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 5: "SCALLOP BAND: messy and inconsistent. Draw ONE continuous scallop: every arc the same size, clean at panel edges, aligned across every fold and round the whole carton."]
    Its scalloped band is no longer copied round: the one scallop is drawn round the whole row (``scallop_round``)."""
    by_name = {p.name: p for p in panels}
    front = by_name.get("front")
    if front is None:
        return []
    field, _bands = _round_parts(map_children, front, gx, gy)
    if not field:
        return []
    # [his goal of 2026-10-10, item 9] each panel's shift from the front: the left side ends where the garden ends,
    # the right side and the back begin where it begins — moved, never turned over
    shifts = {}
    for name in ROUND_PANELS:
        p = by_name.get(name)
        if p is None:
            continue
        if name == "side_left":
            shifts[name] = (p.x + p.width) - (front.x + front.width)
        else:
            shifts[name] = p.x - front.x
    field = [_compact(part) for part in field]
    nodes = []
    span = _field_span(field)
    for name in ROUND_PANELS:
        p = by_name.get(name)
        if p is None or name not in shifts:
            continue
        # [his test findings on design 123, (1)] a panel drawn from the layout picture: the front's field only where its
        # picture prints line art, as strong as it prints it, and the front's band where its picture prints it
        own = (layout or {}).get(name)
        drawn = isinstance(own, dict) and "continues" not in own
        parts = (field if own.get("line_art") else []) if drawn else field
        kids = []
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (1)] the field repeated at the front's own width until it
        # covers the panel — a panel wider than the front never left bare at its edge
        for k, shift in enumerate(_tiles(shifts[name], front.width, span, gx(p.x), gx(p.x + p.width),
                                         -1 if name == "side_left" else 1)):
            for i, part in enumerate(parts):
                copy = _moved(part, shift, 0.0, "round-%s-%d" % (name, i) + ("-%d" % k if k else ""))
                if name == "back" and not drawn:
                    copy = _faint(copy, BACK_FIELD_OPACITY)
                kids.append(copy)
        top, foot = (max(p.y, body[0]), min(p.y + p.height, body[1])) if body else (p.y, p.y + p.height)
        x0, y0, y1 = gx(p.x), gy(top) + 0.05, gy(foot) - 0.05
        clip = [MoveTo(x=x0, y=y0), LineTo(x=x0 + p.width, y=y0), LineTo(x=x0 + p.width, y=y1), LineTo(x=x0, y=y1),
                ClosePath()]
        # [his test findings on design 123, (2) and (4)] the side's type kept clear of the field: each line's place cut
        # out of the clip, wound against the panel's (as the front's small copy is)
        from apps.ire.compose_container import clear_rings
        for ring in clear_rings((holes or {}).get(name) or []):           # merged where they meet
            clip += [MoveTo(x=ring[0][0], y=ring[0][1])] + [LineTo(x=x, y=y) for x, y in ring[1:]] + [ClosePath()]
        nodes.append(Group(name="round-%s" % name, role="decoration", children=kids, clip=clip))
    return nodes


def _field_span(field: list) -> tuple | None:
    """``(x0, x1)`` page mm the front's field draws across, or None."""
    xs = []

    def walk(node):
        if isinstance(node, Path):
            xs.extend(float(v) for g in node.segments for v in (getattr(g, "x", None), getattr(g, "x1", None),
                                                                getattr(g, "x2", None)) if v is not None)
        for c in getattr(node, "children", None) or []:
            walk(c)
    for part in field:
        walk(part)
    return (min(xs), max(xs)) if xs else None


#: [His review of 127, 130, 131 and 132, 2026-10-15, C (1)] a further copy of the field is laid only where it reaches
#: this far (mm) onto the panel — never for the sliver a stroke runs past the front's edge
TILE_REACH_MM = 0.5


def _tiles(shift: float, period: float, span, x0: float, x1: float, way: int) -> list:
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (1)] the shifts that lay the front's field (drawn across
    ``span``) over x0..x1 page mm: ``shift`` first, then on at ``period`` (the front's width) the panel's ``way`` from
    it while a copy still reaches the panel — and back the other way to cover what the first leaves."""
    if span is None or period <= 0:
        return [shift]
    out = [shift]
    for direction in (way, -way):
        k = 1
        while k < 12:
            s = shift + direction * k * period
            if span[1] + s <= x0 + TILE_REACH_MM or span[0] + s >= x1 - TILE_REACH_MM:
                break
            out.append(s)
            k += 1
    return out


def _moved(node, dx: float, dy: float, name: str):
    """A drawn node — a path, or a group of them (a pattern traced in its colours) — moved ``dx``, ``dy`` mm, renamed: a
    group in a group of its own that moves it (``Group.turn``, no turn and a move), its thousands of shapes never copied
    point by point."""
    if isinstance(node, Group):
        return Group(name=name, role="decoration", turn=(1.0, 0.0, 0.0, 1.0, float(dx), float(dy)), children=[node])
    dump = _shift_x(node.model_dump(), dx)
    if dy:
        dump = _shift_y(dump, dy)
    dump["name"] = name
    return type(node).model_validate(dump)


def _compact(node):
    """A pattern traced in its colours, its shapes of one colour each one compound path (even-odd: its regions never
    overlap — the tracer cuts each out of the next — so a region inside another's hole still fills) in each of its
    groups: one path a colour, where 132's majolica drew 6,274 — the same drawing, a file Illustrator opens."""
    if not isinstance(node, Group):
        return node
    kids, by_ink = [], {}
    for c in node.children:
        if isinstance(c, Path) and isinstance(c.fill, SolidFill) and c.stroke is None and c.fill_rule == "evenodd":
            key = (c.fill.color.to_hex(), round(float(c.fill.opacity), 4), round(float(c.opacity), 4))
            if key in by_ink:
                by_ink[key].segments.extend(c.segments)
                continue
            merged = c.model_copy(update={"segments": list(c.segments), "name": "%s-%s" % (node.name, key[0])})
            by_ink[key] = merged
            kids.append(merged)
            continue
        kids.append(_compact(c))
    return node.model_copy(update={"children": kids})


def _shift_y(value, dy: float):
    """A node's dump moved ``dy`` millimetres down the page — every point's y, a box's top."""
    if isinstance(value, dict):
        out = {k: _shift_y(v, dy) for k, v in value.items()}
        for key in ("y", "y1", "y2"):
            if isinstance(value.get(key), (int, float)):
                out[key] = float(value[key]) + dy
        return out
    if isinstance(value, list):
        return [_shift_y(v, dy) for v in value]
    return value


def _faint(node, strength: float):
    """A drawn node with every fill and stroke under it at ``strength`` of its own opacity (the back's faint field)."""
    def walk(value):
        if isinstance(value, dict):
            out = {k: walk(v) for k, v in value.items()}
            for key in ("fill", "stroke"):
                if isinstance(value.get(key), dict) and isinstance(value[key].get("opacity"), (int, float)):
                    out[key] = dict(out[key], opacity=round(float(value[key]["opacity"]) * strength, 4))
            return out
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value
    return type(node).model_validate(walk(node.model_dump()))


def pattern_flaps(map_children: list, coords, gx, gy) -> list:
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (1): "it covers every panel of the carton (sides, back behind
    the sticker, flaps), never only the front. No grey panels."] The front's field (``_round_parts``) on every flap and
    tuck: each the copy its body panel carries (``_continued_round``'s shift across), repeated up or down by the body's
    height until it covers the flap — the pattern carried on past the fold as one tiled print — clipped to the flap's
    own outline; never the glue tab (his final goal, B2: no ink where the glue goes)."""
    panels = {p.name: p for p in coords.panels}
    front = panels.get("front")
    body_top, body_foot = getattr(coords, "body_top_y", None), getattr(coords, "body_bottom_y", None)
    if front is None or body_top is None or body_foot is None:
        return []
    field, _bands = _round_parts(map_children, front, gx, gy)
    if not field:
        return []
    field = [_compact(part) for part in field]
    period_x, period_y = front.width, float(body_foot) - float(body_top)
    xs = _field_span(field)
    ys = []

    def walk(node):
        if isinstance(node, Path):
            ys.extend(float(g.y) for g in node.segments if hasattr(g, "y"))
        for c in getattr(node, "children", None) or []:
            walk(c)
    for part in field:
        walk(part)
    if xs is None or not ys or period_y <= 0:
        return []
    fy0, fy1 = min(ys), max(ys)
    nodes = []
    for name, poly in getattr(coords, "components", []) or []:
        if name in ("main-body", "glue-tab"):
            continue
        x0, y0, x1, y1 = poly.bounds
        mid = (x0 + x1) / 2.0
        under = next((p for p in coords.panels if p.x <= mid <= p.x + p.width and p.name in ROUND_PANELS + ("front",)),
                     None)
        if under is None:
            continue
        across = 0.0
        if under.name == "side_left":
            across = (under.x + under.width) - (front.x + front.width)
        elif under.name != "front":
            across = under.x - front.x
        up = 1 if (y0 + y1) / 2.0 > float(body_foot) else -1
        kids = []
        for i, dx in enumerate(_tiles(across, period_x, xs, gx(x0), gx(x1), 1)):
            for j in range(1, 6):
                dy = up * j * period_y
                lo, hi = gy(y0) + TILE_REACH_MM, gy(y1) - TILE_REACH_MM
                before, past = (fy0 + dy >= hi, fy1 + dy <= lo) if up < 0 else (fy1 + dy <= lo, fy0 + dy >= hi)
                if past:
                    break
                if before:
                    continue
                for k, part in enumerate(field):
                    kids.append(_moved(part, dx, dy, "flap-%s-pattern-%d-%d-%d" % (name, i, j, k)))
        if kids:
            clip = [MoveTo(x=gx(px), y=gy(py)) if n == 0 else LineTo(x=gx(px), y=gy(py))
                    for n, (px, py) in enumerate(list(poly.exterior.coords)[:-1])] + [ClosePath()]
            nodes.append(Group(name="flap-%s-pattern" % name, role="decoration", clip=clip, children=kids))
    return nodes


def _flattened(segments) -> list:
    """A path's outline as points, page mm: each line and each curve walked in steps no longer than SCALLOP_STEP_MM
    (a curve in SCALLOP_CURVE_STEPS at the least), so every bin its edge is read in holds a point."""
    import math
    pts, at = [], None
    for g in segments:
        if isinstance(g, MoveTo):
            at = (float(g.x), float(g.y))
            pts.append(at)
        elif isinstance(g, LineTo) and at is not None:
            x0, y0 = at
            steps = max(1, int(math.ceil(math.hypot(g.x - x0, g.y - y0) / SCALLOP_STEP_MM)))
            pts += [(x0 + (g.x - x0) * k / steps, y0 + (g.y - y0) * k / steps) for k in range(1, steps + 1)]
            at = (float(g.x), float(g.y))
        elif isinstance(g, CubicTo) and at is not None:
            x0, y0 = at
            reach = math.hypot(g.x1 - x0, g.y1 - y0) + math.hypot(g.x2 - g.x1, g.y2 - g.y1) + math.hypot(
                g.x - g.x2, g.y - g.y2)
            steps = max(SCALLOP_CURVE_STEPS, int(math.ceil(reach / SCALLOP_STEP_MM)))
            for k in range(1, steps + 1):
                t = k / float(steps)
                u = 1.0 - t
                pts.append((u ** 3 * x0 + 3 * u * u * t * g.x1 + 3 * u * t * t * g.x2 + t ** 3 * g.x,
                            u ** 3 * y0 + 3 * u * u * t * g.y1 + 3 * u * t * t * g.y2 + t ** 3 * g.y))
            at = (float(g.x), float(g.y))
    return pts


def scallop_reading(band, x0: float, x1: float, mid_y: float) -> dict:
    """[His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 5: "SCALLOP BAND: messy and inconsistent. Draw ONE continuous scallop: every arc the same size, clean at panel edges, aligned across every fold and round the whole carton."]
    What a band the picture traced says of its scallops, read across the front (``x0``…``x1``, page mm): ``{"foot":
    whether it runs along the foot (its middle below the front's, ``mid_y``), "crest": its arcs' tops, "base": where they meet, "pitch": an arc's width, "arcs":
    how many its edge shows, "fill"}`` — its edge read from its outline, bin by bin; a band whose arcs cannot be read
    keeps its height, its arcs SCALLOP_FALLBACK_PITCH of it wide and SCALLOP_FALLBACK_RISE of it high."""
    pts = _flattened(band.segments)
    ys = [y for _x, y in pts]
    top, bottom = min(ys), max(ys)
    foot = (top + bottom) / 2.0 > mid_y
    # read across the front's middle only: a photographed box curls its band up at its edges
    inset = SCALLOP_EDGE_SHARE * (x1 - x0)
    x0, x1 = x0 + inset, x1 - inset
    n = max(4, int((x1 - x0) / SCALLOP_BIN_MM))
    edge = [None] * n
    for x, y in pts:
        if x0 <= x < x1:
            i = min(n - 1, int((x - x0) / (x1 - x0) * n))
            v = y if foot else -y
            edge[i] = v if edge[i] is None else min(edge[i], v)
    known = [v for v in edge if v is not None]
    reading = {"foot": foot, "fill": band.fill.color.to_hex() if band.fill is not None else None, "read": False}
    if len(known) >= n // 2:
        filled, last = [], known[0]
        for v in edge:
            last = v if v is not None else last
            filled.append(last)
        smooth = [sum(filled[max(0, i - 2):i + 3]) / len(filled[max(0, i - 2):i + 3]) for i in range(n)]
        # its depth read between its edge's lower and upper tenths — a traced end curling up at the box's edge never
        # sets it; an arc's top is where its edge stands within SCALLOP_TOP_SHARE of that depth from the top
        ranked = sorted(smooth)
        lo, hi = ranked[int(0.1 * (n - 1))], ranked[int(0.9 * (n - 1))]
        cut = lo + SCALLOP_TOP_SHARE * (hi - lo)
        crests, i = [], 0
        while i < n:
            if smooth[i] <= cut:
                j = i
                while j < n and smooth[j] <= cut:
                    j += 1
                k = min(range(i, j), key=lambda q: smooth[q])
                crests.append(x0 + (k + 0.5) * (x1 - x0) / n)
                i = j
            else:
                i += 1
        if len(crests) >= 3 and hi - lo > 0.2:
            gaps = sorted(b - a for a, b in zip(crests, crests[1:]))
            reading.update(read=True, pitch=gaps[len(gaps) // 2], arcs=len(crests),
                           crest=lo if foot else -lo, base=hi if foot else -hi)
    if not reading["read"]:
        tall = bottom - top
        crest = top if foot else bottom
        base = crest + tall * SCALLOP_FALLBACK_RISE * (1.0 if foot else -1.0)
        reading.update(pitch=tall * SCALLOP_FALLBACK_PITCH, arcs=0, crest=crest, base=base)
    return reading


def scallop_round(map_children: list, panels, gx, gy, body: tuple) -> tuple:
    """[His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 5: "SCALLOP BAND: messy and inconsistent. Draw ONE continuous scallop: every arc the same size, clean at panel edges, aligned across every fold and round the whole carton."]
    ``(the nodes, the front's nodes without the band it replaces, the record)`` — each scalloped band the front's
    picture runs edge to edge drawn again as ONE scallop round the body's whole row (SCALLOP_ROW, back to right side):
    every arc the same width and the same height — the picture's own, the width fitted so a whole number of arcs runs
    round the carton exactly, so the scallop meets itself where the carton is glued — its two free edges each at the
    foot of an arc, clean; one path, in the band's own colour, from its arcs to the body's fold (``body``: its top and
    its foot), never onto a flap. The band the picture traced is taken off the front: the one scallop runs across it."""
    by_name = {p.name: p for p in panels}
    row = [by_name[n] for n in SCALLOP_ROW if n in by_name]
    front = by_name.get("front")
    if front is None or len(row) < 2:
        return [], map_children, None
    _field, bands = _round_parts(map_children, front, gx, gy)
    if not bands:
        return [], map_children, None
    drop = {id(b) for b in bands}

    def without(nodes):
        out = []
        for n in nodes:
            if id(n) in drop:
                continue
            if isinstance(n, Group):
                n = n.model_copy(update={"children": without(n.children)})
            out.append(n)
        return out
    rx0, rx1 = gx(row[0].x), gx(row[-1].x + row[-1].width)
    length = rx1 - rx0
    # each panel between the body's folds — the front to its own fold, where its tuck folds (it runs past the body's
    # line by the board's thickness), never onto a flap
    def reach(p):
        top = max(p.y, body[0]) + (0.0 if p.name == "front" else 0.05)
        foot = (p.y + p.height) if p.name == "front" else min(p.y + p.height, body[1]) - 0.05
        return gy(top), gy(foot)
    top, foot = min(reach(p)[0] for p in row), max(reach(p)[1] for p in row)
    nodes, records = [], []
    for b, band in enumerate(bands):
        read = scallop_reading(band, gx(front.x), gx(front.x + front.width), gy(front.y + front.height / 2.0))
        arcs = max(1, int(round(length / read["pitch"])))
        pitch = length / arcs
        rise = max(abs(read["base"] - read["crest"]), SCALLOP_MIN_RISE * pitch)
        base = read["base"]
        edge_y = foot if read["foot"] else top
        up = -1.0 if read["foot"] else 1.0               # an arc rises toward the band's free side
        k = SCALLOP_K
        segs = [MoveTo(x=rx0, y=edge_y), LineTo(x=rx0, y=base)]
        for a in range(arcs):
            xa = rx0 + a * pitch
            xc = xa + pitch / 2.0
            peak = base + up * rise
            segs += [CubicTo(x1=xa, y1=base + up * rise * k, x2=xc - k * pitch / 2.0, y2=peak, x=xc, y=peak),
                     CubicTo(x1=xc + k * pitch / 2.0, y1=peak, x2=xa + pitch, y2=base + up * rise * k,
                             x=xa + pitch, y=base)]
        segs += [LineTo(x=rx1, y=edge_y), ClosePath()]
        # the one path, drawn on each panel of the row inside that panel alone — continuous across every fold, and
        # never a clip reaching past its panel onto a flap
        kids = []
        for p in row:
            py0, py1 = reach(p)
            px0, px1 = gx(p.x), gx(p.x + p.width)
            kids.append(Group(name="scallop-%d-%s" % (b, p.name), role="decoration", clip=[
                MoveTo(x=px0, y=py0), LineTo(x=px1, y=py0), LineTo(x=px1, y=py1), LineTo(x=px0, y=py1), ClosePath()],
                children=[Path(name="scallop-band-%d" % b if p.name == "front" else "scallop-band-%d-%s" % (b, p.name),
                               segments=segs, fill=band.fill)]))
        nodes.append(Group(name="scallop-round-%d" % b, role="decoration", children=kids))
        records.append({"arcs": arcs, "pitch_mm": round(pitch, 3), "rise_mm": round(rise, 3),
                        "row_mm": round(length, 3), "read_from_the_picture": read["read"],
                        "arcs_the_picture_shows": read["arcs"], "along": "foot" if read["foot"] else "head",
                        "fill": read["fill"], "meets_itself": "where the carton is glued, at the foot of an arc"})
    return nodes, without(map_children), {"schema": SCALLOP_SCHEMA, "bands": records}


#: kept on the drawing's record
SCALLOP_SCHEMA = "carton_scallop_round/1.0"


#: [the owner's finding on design 119, 2026-10-03] the panels his brief's side copy is set on
SIDE_PANELS = ("side_left", "side_right")


def _side_copy_setting(map_front: dict, map_record: dict) -> dict | None:
    """His brief's side copy as each side sets it: the phrases, the ink, the size and line pitch, and each phrase's
    length stood on end (mm) — None where the brief gives none."""
    from apps.ire.compose_container import MAP_TYPE_FLOOR_PT, _script_runs, name_width_estimate_mm
    phrases = [p for p in map_front.get("side_copy") or [] if p]
    if not phrases:
        return None
    ground = Color.from_hex(map_front["ground"]) if map_front.get("ground") else Color.from_hex(_TINT)
    ink = contrast_ink(map_front, ground)
    sizes = [float(t["size_pt"]) for t in map_record.get("typed") or [] if t.get("size_pt") and not t.get("traced")]
    size_pt = max(min(sizes) if sizes else FRONT_LINE_PT, MAP_TYPE_FLOOR_PT)
    from apps.ire.back_panel import LEADING_EM, MM_PER_PT
    lengths = []
    for phrase in phrases:
        runs = _script_runs(phrase)
        space = name_width_estimate_mm(" ", size_pt)
        lengths.append(sum(name_width_estimate_mm(text, size_pt) for text, _rtl in runs) + space * (len(runs) - 1))
    return {"phrases": phrases, "ink": ink, "size_pt": size_pt, "pitch": size_pt * MM_PER_PT * LEADING_EM,
            "lengths": lengths}


def contrast_ink(map_front: dict, ground) -> Color:
    """The front's ink that stands out most from ``ground`` — the side copy's and the back copy's ink."""
    shapes = map_front.get("shapes") or {}
    inks = [t["ink"] for t in shapes.get("types") or [] if t.get("ink")] + [
        sh["ink"] for sh in shapes.get("shapes") or [] if sh.get("ink")]

    def lum(c):
        return 0.299 * c.r + 0.587 * c.g + 0.114 * c.b
    ink = max((Color.from_hex(i) for i in inks), key=lambda c: abs(lum(c) - lum(ground)), default=None)
    if ink is None:
        ink = Color.from_hex("#59283A") if lum(ground) >= 0.5 else Color.from_hex("#F7F0E6")
    return ink


def _side_copy_nodes(map_front: dict, map_record: dict, panels, gx, gy, safe_mm: float) -> tuple:
    """[The owner's finding on design 119, 2026-10-03 (transcribed at 32898c7): "sides ... continue the concept's own
    ground, colours and graphics"; his brief: "Carton side: ..."] His brief's side copy (``map_front["side_copy"]``) on
    each side panel: each phrase one line, stood on end and reading from the foot up as a tall carton's side reads,
    the lines side by side across the panel, centred; in the ink of the front's that stands out most from the ground,
    at the size of the front's smallest typed line (never under the print floor), each script its own run. Returns
    ``(the runs, {"panels": [what was set on each side, measured], "codes": [a line longer than its side]})``."""
    from apps.ire.compose_container import _script_runs, name_width_estimate_mm
    setting = _side_copy_setting(map_front, map_record)
    if setting is None:
        return [], {"panels": [], "codes": []}
    phrases, ink, size_pt, pitch = setting["phrases"], setting["ink"], setting["size_pt"], setting["pitch"]
    from apps.ire.back_panel import MM_PER_PT
    nodes, records, codes = [], [], []
    for p in (q for q in panels if q.name in SIDE_PANELS):
        avail = p.height - 2 * safe_mm
        cx, cy = p.x + p.width / 2.0, p.y + p.height / 2.0
        first = cx - (len(phrases) - 1) * pitch / 2.0
        lines = []
        for j, phrase in enumerate(phrases):
            runs = _script_runs(phrase)
            space = name_width_estimate_mm(" ", size_pt)
            widths = [name_width_estimate_mm(text, size_pt) for text, _rtl in runs]
            total = sum(widths) + space * (len(runs) - 1)
            # stood on end, reading up: a run's start is its foot; the line centred on the panel's height
            base_x = first + j * pitch + size_pt * MM_PER_PT * 0.35
            cursor = cy + total / 2.0
            for r, ((text, rtl), rw) in enumerate(zip(runs, widths)):
                nodes.append(TextRun(name="side-copy-%s-%d-%d" % (p.name, j, r), text=text, x=gx(base_x), y=gy(cursor),
                                     size_pt=size_pt, color=ink, font="regular", align="left", rtl=rtl,
                                     rotation_deg=90.0))
                cursor -= rw + space
            lines.append({"text": phrase, "length_mm": round(total, 2)})
            if total > avail:
                codes.append(f"{FRONT_COPY_EXCEEDS_PANEL}:{p.name}:side-copy-{j}")
        records.append({"panel": p.name, "drawn_from": "the brief's side copy", "size_pt": round(size_pt, 2),
                        "avail_mm": round(avail, 2), "lines": lines})
    return nodes, {"panels": records, "codes": codes}


#: [His goal of 2026-10-06, item 11 (transcribed at a9ac953): "Side panels are designed: the product name at a real size
#: plus a brand graphic from the concept, not one tiny vertical line on plain ground."] A side, inside its safe margin,
#: from its top: the concept's own motif (the shape its front's map traced — else the house mark) over this share of its
#: height; a gap; the product name stood on end, reading from the foot up, in the face and the letters the front sets it
#: in, as large as it stands in the rest of the height and this share of the width; his brief's side copy (the size, the
#: product's kind) beside it at its own size — in the front's ink that stands out most from the ground.
SIDE_GRAPHIC_SHARE = 0.2
SIDE_NAME_WIDTH_SHARE = 0.6
SIDE_GAP_MM = 3.0
SIDE_NAME_MAX_PT = 60.0
#: [His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (2): "sides use
#: the front's type style, smaller and lighter (never a giant bold name)".] the side's name in the front's own face, a
#: weight lighter, at most this share of the size the front sets it at; the weight a side takes for the front's
SIDE_NAME_SHARE_OF_FRONT = 0.5
LIGHTER = {"black": "bold", "bold": "regular", "front-name": "front-copy"}   # [his goal of 2026-10-10, item 6]
#: … and never under the real size his goal of 2026-10-06, item 11 ("the product name at a real size") set it at
SIDE_NAME_MIN_PT = 12.0


def _side_design_nodes(map_front: dict, map_record: dict, map_children: list, panels, gx, gy, safe_mm: float, *,
                       faces: dict, logo_master=None, motif_aspect: float = 1.0, product_name: str = "",
                       logo_path: str | None = None, layout: dict | None = None) -> tuple:
    """[His goal of 2026-10-06, item 11.] Each side panel designed (``SIDE_GRAPHIC_SHARE`` …): ``(the nodes, {"panels":
    [what each side holds, measured], "codes": [a line longer than its side]})``. The name is the front's own: its
    traced letters where the front draws them traced, else its run in the front's face; measured in the face it is drawn
    in, never estimated. Before (2026-10-03): his side copy alone, at the front's smallest size — one 5 pt line."""
    from apps.ire.back_panel import MM_PER_PT
    from apps.ire.compose_artwork import _face, _width_mm
    from apps.ire.compose_container import _script_runs, name_width_estimate_mm
    from apps.ire.inside_print import _motif_segments, drawn_at, unit_motif
    setting = _side_copy_setting(map_front, map_record)
    ground = Color.from_hex(map_front["ground"]) if map_front.get("ground") else Color.from_hex(_TINT)
    ink = setting["ink"] if setting else contrast_ink(map_front, ground)
    drawn = []

    def walk(nodes):
        for n in nodes or []:
            drawn.append(n)
            walk(getattr(n, "children", None))
    walk(map_children)
    hero = [n for n in drawn if str(getattr(n, "name", "")).startswith("product-name-hero-")]
    name_lines = [n for n in drawn if getattr(n, "name", "") == "product-name-traced"]
    traced = name_lines[0] if name_lines else None
    lettered = ""
    if traced is not None:
        # [his test blocker on design 122 at reconstruction, 2026-10-08] a front line setting the start of the name is
        # the name, traced as the name: the sides carry its words as the front letters them (119: "Rose Glaze")
        lettered = " ".join(str(((map_record or {}).get("name_traced") or {}).get("words") or "").split())
    if len(name_lines) > 1:
        # [his goal after the pitch page, B (10): 140's side printed "Oat &" alone, the first of its name's three lines,
        # run out of its panel] a name the front sets over several lines is carried WHOLE, its lines as the front stacks
        # them, as one block — fitted inside the side's frame below, never one of its lines alone
        traced = traced.model_copy(update={"segments": [g for n in name_lines for g in n.segments]})
        lettered = " ".join(str(product_name or "").split()) or lettered
    if not hero and traced is None:
        # the front's own lettering of the name where the map read it as a line of its words, not as the record's name
        # (119: "Rose Glaze" lettered, "Rose Glaze Lip Gloss" on record) — its traced letters, never a stand-in face
        types = ((map_front or {}).get("shapes") or {}).get("types") or []
        wanted = " ".join(str(product_name or "").split()).lower()
        for n in drawn:
            m = re.match(r"front-lettering-(\d+)$", str(getattr(n, "name", "")))
            words = " ".join(str(types[int(m.group(1))].get("words") or "").split()) if m and int(m.group(1)) < len(
                types) else ""
            if words and words.lower() in wanted:
                traced, lettered = n, words
                break
    # the front's own name — its hero lines as the front sets them; else the product's name, in the front's bold
    name = " ".join(n.text for n in hero) if hero else " ".join(str(product_name or "").split())
    font = hero[0].font if hero else "bold"
    # [his test findings on design 123, (2)] in the front's own face, a weight lighter, smaller than the front sets it
    font = LIGHTER.get(font, font)
    front_pt = max([float(n.size_pt) for n in hero]
                   or [float(t["size_pt"]) for t in (map_record or {}).get("typed") or [] if t.get("size_pt")]
                   or [SIDE_NAME_MAX_PT / SIDE_NAME_SHARE_OF_FRONT])
    name_max_pt = min(SIDE_NAME_MAX_PT, max(SIDE_NAME_MIN_PT, front_pt * SIDE_NAME_SHARE_OF_FRONT))
    # [his test findings on design 123, (2)] where the front's field runs round the carton, it is the side's graphic
    round_field = bool(_round_parts(map_children, next((q for q in panels if q.name == "front"), None), gx,
                                    gy)[0]) if any(q.name == "front" for q in panels) else False
    face = _face(font, faces)
    cubics = _concept_motif(map_front)
    motif = unit_motif(cubics, motif_aspect) if cubics else None
    nodes, records, codes = [], [], []
    for p in (q for q in panels if q.name in SIDE_PANELS):
        x0, y0 = p.x + safe_mm, p.y + safe_mm
        w, h = p.width - 2 * safe_mm, p.height - 2 * safe_mm
        if w <= 0 or h <= 0:
            continue
        record = {"panel": p.name, "drawn_from": "the product name, a brand graphic from the concept and the brief's "
                                                 "side copy", "avail_mm": round(h, 2)}
        # [his test findings on design 123, (1)] the field is the side's graphic only where it is drawn on it: a side its
        # layout picture draws with no line art keeps its own graphic
        own = (layout or {}).get(p.name)
        field_here = round_field and not (isinstance(own, dict) and "continues" not in own and not own.get("line_art"))
        # the brand graphic, upright at the side's top
        gh = 0.0 if field_here else h * SIDE_GRAPHIC_SHARE
        side = min(gh, w * 0.8)
        if field_here:
            record["graphic"] = "the front's field, run round the carton"
        elif motif:
            # [his test blocker on design 123, 2026-10-09, (3)] a continuing carton's side: the container's own rose,
            # in its ink
            rose_ink = _motif_ink(map_front)
            nodes.append(Path(name="side-graphic-%s" % p.name, fill=SolidFill(
                color=Color.from_hex(rose_ink) if rose_ink else ink), fill_rule="nonzero",
                segments=_motif_segments(drawn_at(motif, side), gx(x0 + (w - side) / 2.0), gy(y0 + (gh - side) / 2.0),
                                         side)))          # [his goal after the pitch page, B (10)] for its size
            record["graphic"] = "the approved container's rose" if rose_ink else "the concept's own motif"
        elif logo_master is not None:
            from apps.ire.inside_print import _mark_on
            mark = _mark_on(logo_master, "side-graphic-%s" % p.name, x0, x0 + w, y0, y0 + gh, gx, gy, 0.8)
            nodes.append(mark.model_copy(update={"fill": SolidFill(color=ink)}))
            record["graphic"] = "the house mark"
        elif logo_path:
            # the house mark as its one controlled raster, where no vector master is on file — as the panels' logo
            from apps.ire.nodes import image_node, intrinsic_aspect
            ratio = intrinsic_aspect(logo_path) or 0.3
            lw = min(w * 0.8, gh / ratio)
            raster = image_node("side-graphic-%s" % p.name, logo_path, gx(x0 + (w - lw) / 2.0),
                                gy(y0 + (gh - lw * ratio) / 2.0), lw, lw * ratio)
            if raster is not None:
                nodes.append(raster)
                record["graphic"] = "the house mark (its raster)"
        # the side copy's column, beside the name
        lines = setting["phrases"] if setting else []
        size_pt = setting["size_pt"] if setting else 0.0
        pitch = setting["pitch"] if setting else 0.0
        copy_w = pitch * len(lines)
        run_h = h - gh - SIDE_GAP_MM                              # the name's length stood on end, and the copy's
        name_w = max(0.0, min(w * SIDE_NAME_WIDTH_SHARE, w - copy_w - SIDE_GAP_MM))
        foot = y0 + h                                              # every line stood on end reads up from here
        col = x0 + (w - (name_w + (SIDE_GAP_MM + copy_w if lines else 0.0))) / 2.0
        if traced is not None:
            segs, (bx0, by0, bx1, by1) = traced.segments, _seg_bounds(traced.segments)
            tw, th = bx1 - bx0, by1 - by0                          # page units are millimetres
            # lettering the front already stands on end (119's) keeps its own turn, reading from the foot up as the
            # side's does; lettering set across is turned 90° anticlockwise to stand so — measured on 119 redrawn: the
            # front's standing "Rose Glaze" turned again lay across the side at a tenth of its size
            standing = th > tw
            along, across = (th, tw) if standing else (tw, th)
            k = min(run_h / along, name_w / across) if along and across else 0.0
            if k > 0:
                cx, cy = gx(col + name_w / 2.0), gy(foot - run_h / 2.0)
                turned = []
                for sgm in segs:
                    d = sgm.model_dump()
                    for kx, ky in (("x", "y"), ("x1", "y1"), ("x2", "y2")):
                        if kx in d:
                            dx, dy = (d[kx] - (bx0 + bx1) / 2.0) * k, (d[ky] - (by0 + by1) / 2.0) * k
                            d[kx], d[ky] = (cx + dx, cy + dy) if standing else (cx + dy, cy - dx)
                    turned.append(type(sgm)(**d))
                nodes.append(Path(name="side-name-%s" % p.name, segments=turned, fill=SolidFill(color=ink),
                                  fill_rule=getattr(traced, "fill_rule", "nonzero")))
                record.update(name=lettered or name or "the front's traced name", name_mm=round(along * k, 2),
                              name_traced=True)
        elif name:
            size = name_max_pt
            while size > 6.0:
                long_ = _width_mm(name, size, face) or name_width_estimate_mm(name, size)
                if long_ <= run_h and size * MM_PER_PT * 0.75 <= name_w:
                    break
                size -= 0.5
            long_ = _width_mm(name, size, face) or name_width_estimate_mm(name, size)
            base_x = col + name_w / 2.0 + size * MM_PER_PT * 0.36   # the cap's middle on the column's middle
            nodes.append(TextRun(name="side-name-%s" % p.name, text=name, x=gx(base_x),
                                 y=gy(foot - (run_h - long_) / 2.0), size_pt=size, color=ink, font=font, align="left",
                                 rotation_deg=90.0))
            record.update(name=name, name_size_pt=round(size, 2), name_mm=round(long_, 2))
            if long_ > run_h + 0.01:
                codes.append(f"{FRONT_COPY_EXCEEDS_PANEL}:{p.name}:side-name")
        # his side copy, beside the name
        set_lines = []
        for j, phrase in enumerate(lines):
            runs = _script_runs(phrase)
            space = name_width_estimate_mm(" ", size_pt)
            widths = [name_width_estimate_mm(text, size_pt) for text, _rtl in runs]
            total = sum(widths) + space * (len(runs) - 1)
            base_x = col + name_w + SIDE_GAP_MM + j * pitch + size_pt * MM_PER_PT * 0.35
            cursor = foot - (run_h - total) / 2.0
            for r, ((text, rtl), rw) in enumerate(zip(runs, widths)):
                nodes.append(TextRun(name="side-copy-%s-%d-%d" % (p.name, j, r), text=text, x=gx(base_x),
                                     y=gy(cursor), size_pt=size_pt, color=ink, font="regular", align="left", rtl=rtl,
                                     rotation_deg=90.0))
                cursor -= rw + space
            set_lines.append({"text": phrase, "length_mm": round(total, 2)})
            if total > run_h:
                codes.append(f"{FRONT_COPY_EXCEEDS_PANEL}:{p.name}:side-copy-{j}")
        record.update(size_pt=round(size_pt, 2), lines=set_lines)
        records.append(record)
    return nodes, {"panels": records, "codes": codes}


def _seg_bounds(segs) -> tuple:
    xs, ys = [], []
    for sgm in segs:
        d = sgm.model_dump()
        for kx, ky in (("x", "y"), ("x1", "y1"), ("x2", "y2")):
            if d.get(kx) is not None:
                xs.append(d[kx])
                ys.append(d[ky])
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 0.0, 0.0)


def _label_fonts() -> dict:
    """The faces the carton's copy is drawn in — the sticker's own, as the emitter registers them."""
    from apps.dielines.exporters.info_panel import _resolve_arabic_font_for_label
    from apps.dielines.exporters.counter_display_files import _resolve_fonts
    f_reg, f_bold = _resolve_fonts()
    return {"regular": f_reg, "bold": f_bold, "arabic": _resolve_arabic_font_for_label()}


def _sticker_region(width_mm: float, height_mm: float, safe_mm: float, style: dict | None = None) -> tuple:
    """The back's sticker (on its safe margin) and the label's region inside it, each [x, y, w, h] in the panel's
    millimetres. [His final goal, B3] ``style`` (``back_info.plan``): "printed" — no sticker, the region the safe
    margin's own; a custom sticker's shape holds its copy in the largest rectangle it can (``back_info.text_rect``)."""
    sticker = [safe_mm, safe_mm, width_mm - 2 * safe_mm, height_mm - 2 * safe_mm]
    if style and style.get("mode") == "printed":
        return None, list(sticker)
    if style and style.get("mode") == "custom":
        from apps.ire import back_info
        tx, ty, tw, th = back_info.text_rect(style, sticker[2], sticker[3])
        return sticker, [safe_mm + tx, safe_mm + ty, tw, th]
    pad = STICKER_PAD_MM
    return sticker, [safe_mm + pad, safe_mm + pad, sticker[2] - 2 * pad, sticker[3] - 2 * pad]


def _plan_at(info: dict, width_mm: float, region: list, fonts: dict, languages) -> dict:
    from apps.dielines.exporters import label_layout as LL
    from reportlab.lib.units import mm as pt_per_mm
    return LL.plan_label(info, region[2] * pt_per_mm, region[3] * pt_per_mm, fonts, panel_w=width_mm * pt_per_mm,
                         languages=languages)


def _back_plan(info: dict, panels, safe_mm: float) -> dict:
    """The label on the back's sticker as ``plan_back_copy`` lays it — its fonts, its languages, its sticker and region,
    its plan — at the back's own width."""
    from apps.dielines.exporters import label_layout as LL
    fonts = _label_fonts()
    back = next(p for p in panels if p.name == "back")
    chosen = [lang for lang in info.get("label_languages") or [] if lang in LL.LANGUAGES]
    wanted = tuple(chosen) if chosen else LL.LANGUAGES
    languages = tuple(lang for lang in wanted if lang != "ar" or fonts["arabic"])
    # [his final goal, B3] the back's info as he chose it at the size step: a sticker, printed, or his custom sticker
    style = info.get("back_info") if isinstance(info.get("back_info"), dict) else {"mode": "sticker"}
    sticker, region = _sticker_region(back.width, back.height, safe_mm, style)
    plan = _plan_at(info, back.width, region, fonts, languages) if region[2] > 0 and region[3] > 0 else {"fits": False}
    return {"fonts": fonts, "back": back, "chosen": chosen, "wanted": wanted, "languages": languages, "style": style,
            "sticker": sticker, "region": region, "plan": plan}


def label_form(info: dict, back_mm, safe_mm: float) -> dict:
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (7): "Every back label carries the full set ... Never leave it
    nearly empty."] The form the pieces the system WROTE for the carton's label are set in (``label_copy.FORMS``): the
    richest at which the whole label stands as one block on the back's sticker (``plan_label`` at its floor, as
    ``_back_plan`` lays it, the back ``back_mm`` wide and tall), measured before the carton is drawn — so a written
    piece is shortened, or set in English only, before his label is ever stopped for want of room — and where even the
    shortest does not stand, the written pieces left off one at a time (``label_copy.DROP_ORDER``), his never.
    ``{"form", "dropped"}``."""
    from apps.dielines.exporters import label_layout as LL
    from apps.pipeline.services import label_copy as lc
    fonts = _label_fonts()
    chosen = [lang for lang in info.get("label_languages") or [] if lang in LL.LANGUAGES]
    languages = tuple(lang for lang in (tuple(chosen) if chosen else LL.LANGUAGES) if lang != "ar" or fonts["arabic"])
    style = info.get("back_info") if isinstance(info.get("back_info"), dict) else {"mode": "sticker"}
    _sticker, region = _sticker_region(float(back_mm[0]), float(back_mm[1]), safe_mm, style)
    if region[2] <= 0 or region[3] <= 0:
        return {"form": lc.FULL_EN, "dropped": []}
    # the written pieces' translations, where the label's translation was made: else they are set in English only —
    # the system's own copy is never a piece missing its languages
    tr = info.get("translations") if isinstance(info.get("translations"), dict) else {}
    translated = all(str((tr.get(lang) or {}).get(f) or "").strip() for f in info.get(lc.PANEL_WRITTEN_KEY) or ()
                     for lang in ("es", "ar") if lang in languages and not (lang == "ar" and f == "ingredients"))
    for form in (lc.FORMS if translated else lc.ENGLISH_ONLY):
        if _plan_at(dict(info, **{lc.PANEL_FORM_KEY: form}), float(back_mm[0]), region, fonts, languages)["fits"]:
            return {"form": form, "dropped": []}
    written = set(info.get(lc.PANEL_WRITTEN_KEY) or ()) | ({"made_in"} if info.get(lc.PANEL_MADE_IN_KEY) else set())
    order = [p for p in lc.DROP_ORDER if p in written]
    for k in range(1, len(order) + 1):
        trial = dict(info, **{lc.PANEL_FORM_KEY: lc.TINY_EN, lc.PANEL_DROPPED_KEY: order[:k]})
        if _plan_at(trial, float(back_mm[0]), region, fonts, languages)["fits"]:
            return {"form": lc.TINY_EN, "dropped": order[:k]}
    return {"form": lc.TINY_EN, "dropped": order}


def plan_back_copy(info: dict, panels, safe_mm: float, coords=None) -> dict:
    """[His final goal, 2026-10-05 (transcribed at 32e9aaf), C5: "THE INFO IS ONE DESIGNED BLOCK. All label info ...
    lives together on the back sticker ... If it doesn't fit, shrink step by step keeping per-level consistency".] The
    carton's label laid out as one block (``label_layout``) on the back's sticker — the sticker on the back's safe
    margin, the copy STICKER_PAD_MM inside it — in the languages he chose (``info["label_languages"]``: his choice of the
    fewer-languages offer), else all three. [His correction of 2026-10-07] It shrinks evenly to 3 pt and is never moved,
    dropped or printed inside, and the carton is never widened for it: a label that does not stand at 3 pt holds Gate 2
    by name (LABEL_DOES_NOT_FIT) and says so, with the fewer-languages offer measured (``label_offers``) for his choice,
    the sticker carrying the title, the brand's line and the foot while it waits. ``{"layouts": {"back": layout},
    "record": ...}``."""
    from apps.dielines.exporters import label_layout as LL
    got = _back_plan(info, panels, safe_mm)
    fonts, back, chosen, wanted = got["fonts"], got["back"], got["chosen"], got["wanted"]
    languages, style, sticker, region, plan = (got["languages"], got["style"], got["sticker"], got["region"],
                                               got["plan"])
    codes, offers, shown = [], {}, languages
    if not plan["fits"]:
        codes.append(LABEL_DOES_NOT_FIT)
        offers = label_offers(info, panels, safe_mm, languages, fonts, coords=coords)
        shown = ()
    if shown != languages:
        plan = _plan_at(info, back.width, region, fonts, shown)
    layout = {"region_mm": region, "sticker_mm": sticker, "languages": list(shown), "levels": plan["levels"],
              "title": True, "band": True, "style": style}
    # [his review of 119, 2026-10-05, point 1] every piece of his English in each language the label carries
    translations = info.get("translations") or {}
    from apps.pipeline.services import label_copy as _lc
    for field in TRILINGUAL_FIELDS:
        if not str(info.get(field) or "").strip():
            continue
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] a written piece set in English only so the whole
        # label stands is set so by measure, never a piece missing its languages
        if field in (info.get(_lc.PANEL_WRITTEN_KEY) or ()) and (
                _lc.english_only(info.get(_lc.PANEL_FORM_KEY)) or field in (info.get(_lc.PANEL_DROPPED_KEY) or ())):
            continue
        for lang in ("es", "ar"):
            if lang not in wanted or (lang == "ar" and field == "ingredients"):
                continue
            of = info.get(_lc.TRANSLATED_ENGLISH_KEY)
            if lang == "ar" and not fonts["arabic"]:
                codes.append("%s:%s:%s:no Arabic face" % (LABEL_NOT_TRILINGUAL, lang, field))
            elif not str((translations.get(lang) or {}).get(field) or "").strip():
                codes.append("%s:%s:%s" % (LABEL_NOT_TRILINGUAL, lang, field))
            elif isinstance(of, dict) and of.get(field) != " ".join(str(info.get(field) or "").split()):
                # [his review, C (7)] a translation of other English than the label prints is no translation of it
                codes.append("%s:%s:%s" % (LABEL_NOT_TRILINGUAL, lang, field))
    lv = plan["levels"]
    if LABEL_DOES_NOT_FIT in codes:
        said = ("The label does not fit on the back's sticker even shrunk evenly to %g pt; nothing was moved, dropped or "
                "widened. It waits on you: change its copy or the carton's size, or choose fewer languages"
                % LL.FLOOR_PT)
    else:
        said = ("the label stands as one block on the back's sticker, shrunk evenly: the title %g pt, the body and the "
                "ingredients and warnings %g pt" % (lv["title"], lv["body"]))
    record = {"levels_pt": {k: lv[k] for k in ("title", "body", "fine")}, "face": lv["face"],
              "floors_pt": {"body": LL.FLOOR_PT, "fine": LL.FINE_FLOOR_PT}, "safe_mm": safe_mm,
              "sticker_mm": [round(v, 2) for v in sticker] if sticker else None, "languages": list(languages),
              "back_info": dict(style),
              "languages_chosen": bool(chosen), "codes": codes, "offers": offers,
              "panels": {"back": LL.record_of(plan)}, "said": [said]}
    return {"layouts": {"back": layout}, "record": record}


def label_offers(info: dict, panels, safe_mm: float, languages, fonts: dict, coords=None) -> dict:
    """[His final goal, 2026-10-05, C5: "STOP and offer: ... or fewer languages."] The offer measured, through the same
    layout, to hold the label: ``{"fewer_languages": [each set of fewer languages that stands on this carton]}`` — left
    out where none holds, and never chosen for him. [His correction of 2026-10-07: "Never widen the carton for text"; his
    acceptance of "fewer languages only by my choice"] a wider carton is no longer offered, nor the info inside."""
    back = next(p for p in panels if p.name == "back")
    width_mm, height_mm = back.width, back.height

    style = info.get("back_info") if isinstance(info.get("back_info"), dict) else None

    def fits(width, langs):
        _sticker, region = _sticker_region(width, height_mm, safe_mm, style)
        return region[2] > 0 and region[3] > 0 and _plan_at(info, width, region, fonts, langs)["fits"]
    offers = {}
    fewer = [list(s) for s in FEWER_LANGUAGES if set(s) < set(languages) and fits(width_mm, s)]
    if fewer:
        offers["fewer_languages"] = fewer
    return offers


#: [his review of 119, 2026-10-05, point 4: "Nothing inside the safe margin: 119's foot line touches the fold."] a part of
#: the front drawn from its picture still inside the safe margin once fitted holds Gate 2 by name; a line of the picture's
#: whose parts cannot stand side by side inside it at the print floor is set one under another; a bold line is set this
#: much wider than its estimate
FRONT_INSIDE_SAFE_MARGIN = "CARTON_FRONT_INSIDE_SAFE_MARGIN"
STACK_GAP_EM = 0.3
BOLD_WIDTH = 1.06


def _bleeds(part: dict) -> bool:
    """A band or rule the picture runs edge to edge — it runs into the bleed, and never into the safe margin's rule.
    [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010)] and a solid shape it runs edge to edge (``concept_design_map.edge_to_edge``):
    123's Garden Wrap's scalloped band, fitted inside the margin as a key element, stood 9 mm above the carton's foot."""
    return bool(part.get("edges"))


def _to_the_fold(part: dict) -> dict:
    """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010).] A shape
    a carton's front runs to its foot (``concept_design_map.edge_to_edge``) stopped at the foot: there the front folds
    onto its bottom tuck, where nothing of the front is printed — its sides run on past their folds, the side panels
    continuing it at the same rows."""
    def walk(v):
        if isinstance(v, list) and v and all(isinstance(n, (int, float)) for n in v) and len(v) % 2 == 0:
            return [min(float(n), 1.0) if i % 2 else n for i, n in enumerate(v)]
        if isinstance(v, list):
            return [walk(e) for e in v]
        return v
    return dict(part, cubics=walk(part.get("cubics") or []), box=walk(part.get("box") or []))


def _frac_walk(obj, k: float, bx: float, by: float, ky: float | None = None):
    """``obj``'s product fractions moved by x' = k·x + bx, y' = ky·y + by (``ky`` is ``k`` where none is given): every
    box, drawn box, cubic, outline, edge, a window's arch and traced outline's frame in it."""
    ky = k if ky is None else ky

    def pairs(v):
        if isinstance(v, list) and v and all(isinstance(n, (int, float)) for n in v) and len(v) % 2 == 0:
            return [(k * float(n) + bx) if i % 2 == 0 else (ky * float(n) + by) for i, n in enumerate(v)]
        if isinstance(v, list):
            return [pairs(e) for e in v]
        return v
    if isinstance(obj, dict):
        out = {}
        for key, v in obj.items():
            # [his goal of 2026-10-13, (7)] a window's arch (its rim's line, ``points``) moves with its box — it stood
            # where the concept drew it while its box and field moved, its field a box inside it on 125's front
            if key in ("box", "drawn_box", "cubics", "outline", "edge", "corners", "centre", "points"):
                out[key] = pairs(v)
            elif key == "frame" and isinstance(v, list) and len(v) == 4:
                out[key] = [k * v[0] + bx, ky * v[1] + by, k * v[2], ky * v[3]]
            elif key == "half" and isinstance(v, list) and len(v) == 2:
                out[key] = [k * float(v[0]), ky * float(v[1])]      # a window's or frame's ellipse, sized with it
            elif key == "axis" and isinstance(v, (int, float)):
                out[key] = k * float(v) + bx                          # an arch's axis, where its apex stands
            elif key == "width" and ("shape" in obj or "axis" in obj) and isinstance(v, (int, float)):
                out[key] = k * float(v)                               # a frame's stroke or an arch's, scaled with it
            elif key == "to" and "hex" in obj and isinstance(v, (int, float)):
                out[key] = k * float(v)                               # a glow's reach, a share of the width
            else:
                out[key] = _frac_walk(v, k, bx, by, ky)
        return out
    if isinstance(obj, list):
        return [_frac_walk(e, k, bx, by, ky) for e in obj]
    return obj


#: [His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (4): "Scale the layout as a whole when the real size differs from the concept's (57 x 37 x 123 mm)."]
#: a front whose panel's shape differs from its concept's face by under this share is laid out as the picture lays it
UNIFORM_TOLERANCE = 0.02


def uniform_layout(map_front: dict, W: float, H: float) -> tuple:
    """[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (4): "Scale the layout as a whole when the real size differs from the concept's (57 x 37 x 123 mm)."]
    The front's key elements — its type, its mark, the window and frame round it, each solid shape the picture does not
    run edge to edge, the bloom of its line art — laid out as the concept lays them, as one block at the concept's own
    proportions (``face_aspect``, its face's width over its height), as large as the panel holds and centred on it;
    what the picture runs edge to edge — a band, a rule, a shape into the bleed, the field of line art, a scatter —
    still spans the panel. Garden Wrap's face is 0.30 as wide as it is tall, his 57 x 123 mm front 0.46: read straight
    onto the panel, every element stood 1.55 times as wide as the concept draws it, and its name grew into "Hand Cream".
    ``(the map front, the record — None where the shapes agree)``."""
    aspect = map_front.get("face_aspect")
    if not aspect or not W or not H:
        return map_front, None
    panel = W / H
    if abs(panel / float(aspect) - 1.0) < UNIFORM_TOLERANCE:
        return map_front, None
    kx, ky = (float(aspect) / panel, 1.0) if panel > float(aspect) else (1.0, panel / float(aspect))
    bx, by = (1.0 - kx) / 2.0, (1.0 - ky) / 2.0
    shapes = map_front.get("shapes") or {}
    laid = dict(shapes)
    for key in ("types", "marks", "windows", "frames", "shapes"):
        if shapes.get(key):
            laid[key] = [p if key == "shapes" and _bleeds(p) else _frac_walk(p, kx, bx, by, ky) for p in shapes[key]]
    lines = []
    for line in shapes.get("lines") or []:
        bloom = (line.get("continued") or {}).get("bloom")
        if bloom:
            b = [float(v) for v in bloom]
            line = dict(line, continued=dict(line["continued"], bloom=[kx * b[0] + bx, ky * b[1] + by,
                                                                       kx * b[2] + bx, ky * b[3] + by]))
        lines.append(line)
    if shapes.get("lines"):
        laid["lines"] = lines
    record = {"face_aspect": round(float(aspect), 4), "panel_aspect": round(panel, 4),
              "scale": [round(kx, 4), round(ky, 4)],
              "block_mm": [round(kx * W, 2), round(ky * H, 2)]}
    return dict(map_front, shapes=laid), record


def _typed_size(t: dict, W: float, H: float) -> float:
    """The size a typed line is set at (pt) — the largest that fits its box, never under the print floor — as
    ``compose_container._map_type_group`` sets it."""
    from apps.ire.compose_container import MAP_TYPE_FLOOR_PT, MAP_TYPE_INK_EM, _INK_MM_PER_PT, name_width_estimate_mm
    x0, y0, x1, y1 = (float(v) for v in t["box"])
    per_pt = max(name_width_estimate_mm(t["words"], 1.0), 1e-6)
    return max(min((y1 - y0) * H / MAP_TYPE_INK_EM / _INK_MM_PER_PT, (x1 - x0) * W / per_pt), MAP_TYPE_FLOOR_PT)


def _drawn_bounds(t: dict):
    """[His final goal, 2026-10-05, A: "text, logos and key elements stay inside it".] What a lettered line draws, in the
    product's fractions — its set letters, its traced outlines and its layered lettering, whichever it carries, their
    union (the drawing takes one of them): 117's script name draws its gold layers past the box its ink was read in."""
    from apps.ire.compose_container import _cubic_segments, _lettering_paths, _traced_segments

    def ident(p):
        return float(p[0]), float(p[1])
    found = []
    setting = t.get("lettering_set")
    if setting and setting.get("state") == "SET" and setting.get("layers"):
        found.append(_cubic_segments(setting["layers"][0]["cubics"], ident)[1])
    lettering = t.get("lettering_layers")
    if lettering:
        inner = lettering.get("set")
        if inner and inner.get("state") == "SET" and inner.get("layers"):
            found.append(_cubic_segments(inner["layers"][0]["cubics"], ident)[1])
        drawn = _lettering_paths(lettering, ident)
        if drawn:
            found.append(drawn["bounds"])
    if t.get("outlines") and "svg" in t["outlines"]:
        found.append(_traced_segments(t["outlines"], ident)[1])
    found = [b for b in found if b]
    if not found:
        return None
    return [min(b[0] for b in found), min(b[1] for b in found), max(b[2] for b in found), max(b[3] for b in found)]


def _typed_extent(t: dict, W: float, H: float, product_name: str) -> list:
    """Where a typed line prints on the panel (mm): its box, or — a line the print floor sets larger than its box — its
    width and height at that size, centred where the picture centres it."""
    from apps.ire.compose_container import MAP_TYPE_LEADING_EM, _INK_MM_PER_PT, name_width_estimate_mm
    x0, y0, x1, y1 = (float(v) for v in t["box"])
    bw, bh = (x1 - x0) * W, (y1 - y0) * H
    if t.get("words") == product_name or t.get("lettering_set") or t.get("rotation") in (90, -90):
        drawn = _drawn_bounds(t)
        if drawn is not None:
            x0, y0, x1, y1 = min(x0, drawn[0]), min(y0, drawn[1]), max(x1, drawn[2]), max(y1, drawn[3])
        return [x0 * W, y0 * H, x1 * W, y1 * H]
    size = _typed_size(t, W, H)
    wide = name_width_estimate_mm(t["words"], size)
    if t.get("weight") == "bold":
        wide *= BOLD_WIDTH
    cx, cy = (x0 + x1) / 2.0 * W, (y0 + y1) / 2.0 * H
    half, tall = max(bw, wide) / 2.0, max(bh, size * _INK_MM_PER_PT * MAP_TYPE_LEADING_EM) / 2.0
    return [cx - half, cy - tall, cx + half, cy + tall]


def _lap(a, b) -> float:
    """The area two boxes (``x0, y0, x1, y1``) share."""
    w, h = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def _key_boxes(shapes: dict, W: float, H: float, product_name: str, group: list) -> list:
    """``[(part, box mm)]`` — every key part of the front but ``group``'s lines: a solid shape, a mark, another line."""
    out = []
    for key in ("shapes", "marks"):
        for part in shapes.get(key) or []:
            if part.get("box"):
                b = [float(v) for v in part["box"]]
                out.append((part.get("part") or key, (b[0] * W, b[1] * H, b[2] * W, b[3] * H)))
    for t in shapes.get("types") or []:
        if t.get("words") and t.get("part") not in group:
            out.append((t.get("part"), tuple(_typed_extent(t, W, H, product_name))))
    return out


def inside_safe(map_front: dict, W: float, H: float, safe_mm: float, product_name: str, rect=None) -> tuple:
    """[His review of 119, 2026-10-05, point 4: "Nothing inside the safe margin: 119's foot line touches the fold."] The
    front's parts as its picture places them, fitted inside the panel's safe margin: a row of typed lines too wide to
    stand side by side inside it at its size set one under another, centred where the row is; then every part but a band
    or rule the picture runs edge to edge (into the bleed) scaled by one factor and moved as one, the least that brings
    them inside — the picture's composition kept, smaller. ``(the map front fitted, the record)``.
    [His final goal, 2026-10-05, A: "The safe margin rule applies to containers too (117 included)".] ``rect`` — the safe
    rectangle in the product's millimetres (``x0, y0, x1, y1``): a container's front zone inset by its own margin; a
    carton's panel inset by ``safe_mm`` when none is given."""
    rx0, ry0, rx1, ry1 = (safe_mm, safe_mm, W - safe_mm, H - safe_mm) if rect is None else (float(v) for v in rect)
    shapes = map_front.get("shapes") or {}
    typed = [t for t in shapes.get("types") or [] if t.get("words")]
    stacked = []
    rows = []
    for t in sorted(typed, key=lambda t: float(t["box"][1])):
        if t.get("words") == product_name or t.get("lettering_set") or t.get("rotation") in (90, -90):
            continue
        for row in rows:
            r = row[0]["box"]
            lap = min(float(t["box"][3]), float(r[3])) - max(float(t["box"][1]), float(r[1]))
            if lap > 0.5 * min(float(t["box"][3]) - float(t["box"][1]), float(r[3]) - float(r[1])):
                row.append(t)
                break
        else:
            rows.append([t])
    moved = {}
    room = rx1 - rx0
    for row in rows:
        if len(row) < 2:
            continue
        row.sort(key=lambda t: float(t["box"][0]))
        widths = [_typed_extent(t, W, H, product_name) for t in row]
        need = sum(e[2] - e[0] for e in widths)
        if need <= room:
            continue
        centre = (min(e[0] for e in widths) + max(e[2] for e in widths)) / 2.0 / W
        y = min(e[1] for e in widths) / H
        # [his final goal, 2026-10-05, C8: "A LINE THAT BREAKS DROPS ITS SEPARATOR."] the row broken into lines: the
        # "·" between "LIP GLOSS" and the Arabic goes with the break
        from apps.ire.text_script import drop_break_separators
        words = drop_break_separators([t["words"] for t in row])
        for t, e, said in zip(row, widths, words):
            # each line in a box as tall as the size it is set at, one under another, a gap between
            x0, x1 = (float(v) for v in (t["box"][0], t["box"][2]))
            half, tall = (x1 - x0) / 2.0, (e[3] - e[1]) / H
            moved[t["part"]] = ([centre - half, y, centre + half, y + tall], said)
            y += tall * (1.0 + STACK_GAP_EM)
        stacked.append([t["part"] for t in row])
    if moved:
        types = [dict(t, box=moved[t["part"]][0], words=moved[t["part"]][1]) if t.get("part") in moved else t
                 for t in shapes.get("types") or []]
        shapes = dict(shapes, types=types)
    # a typed line the print floor sets wider or taller than the picture's box for it, poking past the margin while it
    # fits inside it: moved just inside — never the whole front shrunk for one line's letters; a row set one line under
    # another moves as one, its lines never onto each other
    nudged = []
    not_nudged = []   # [his final goal, C7] a line left where the picture sets it: a nudge would put it on another part
    room_h = ry1 - ry0
    typed_free = [t for t in shapes.get("types") or [] if t.get("words") and t.get("words") != product_name
                  and not t.get("lettering_set") and t.get("rotation") not in (90, -90)]
    in_stack = {part for group in stacked for part in group}
    groups = [list(g) for g in stacked] + [[t["part"]] for t in typed_free if t["part"] not in in_stack]
    by_part = {t["part"]: t for t in shapes.get("types") or []}
    shift = {}
    for group in groups:
        es = [_typed_extent(by_part[part], W, H, product_name) for part in group if part in by_part]
        if not es:
            continue
        x0, y0 = min(e[0] for e in es), min(e[1] for e in es)
        x1, y1 = max(e[2] for e in es), max(e[3] for e in es)
        dx = dy = 0.0
        if x1 - x0 <= room:
            if x0 < rx0:
                dx = rx0 - x0
            elif x1 > rx1:
                dx = rx1 - x1
        if y1 - y0 <= room_h:
            if y0 < ry0:
                dy = ry0 - y0
            elif y1 > ry1:
                dy = ry1 - y1
        if dx or dy:
            # [his final goal, 2026-10-05, C7: "overlaps; text touching or crossing"] never onto another part: 119's
            # "LIP GLOSS", under its bottle, was nudged up onto the bottle's foot, dark on dark — a line a nudge would
            # put on another part stays where the picture sets it, and the front is fitted as one
            onto = [name for name, box in _key_boxes(shapes, W, H, product_name, group)
                    if _lap((x0 + dx, y0 + dy, x1 + dx, y1 + dy), box) > _lap((x0, y0, x1, y1), box) + 1e-6]
            if onto:
                not_nudged.append({"parts": group, "onto": onto})
                continue
            for part in group:
                shift[part] = (dx, dy)
            nudged.append({"parts": group, "moved_mm": [round(dx, 2), round(dy, 2)]})
    if shift:
        def moved_box(t):
            dx, dy = shift[t["part"]]
            b = [float(v) for v in t["box"]]
            return dict(t, box=[b[0] + dx / W, b[1] + dy / H, b[2] + dx / W, b[3] + dy / H])
        shapes = dict(shapes, types=[moved_box(t) if t.get("part") in shift else t for t in shapes.get("types") or []])
    # [his final goal, 2026-10-05, A: "text, logos and key elements stay inside it; backgrounds and patterns still run
    # into the bleed"] only the key elements are fitted — the type, the mark, a solid shape; every band, rule and
    # scattered motif stays where the picture prints it
    # [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010): Garden Wrap's BBROSE mark set below its oval] and the
    # window or frame a mark is set in moves with it — the shapes, the type and the mark are fitted, and the oval round
    # the mark was left where the picture prints it
    keys = ("shapes", "types", "marks", "windows", "frames")
    record = {"safe_mm": safe_mm, "stacked": stacked, "nudged": nudged, "scale": 1.0, "moved_mm": [0.0, 0.0]}
    if not_nudged:
        record["not_nudged"] = not_nudged
    for _round in range(3):
        extents = []
        for key in keys:
            for part in shapes.get(key) or []:
                if key in ("bands", "rules", "shapes") and _bleeds(part):
                    continue
                if key == "types":
                    if part.get("words"):
                        extents.append(_typed_extent(part, W, H, product_name))
                    continue
                if part.get("box"):
                    b = [float(v) for v in part["box"]]
                    extents.append([b[0] * W, b[1] * H, b[2] * W, b[3] * H])
        if not extents:
            break
        ux0, uy0 = min(e[0] for e in extents), min(e[1] for e in extents)
        ux1, uy1 = max(e[2] for e in extents), max(e[3] for e in extents)
        if ux0 >= rx0 - 1e-6 and uy0 >= ry0 - 1e-6 and ux1 <= rx1 + 1e-6 and uy1 <= ry1 + 1e-6:
            break
        k = min(1.0, (rx1 - rx0) / max(ux1 - ux0, 1e-6), (ry1 - ry0) / max(uy1 - uy0, 1e-6))
        cx = min(max((ux0 + ux1) / 2.0, rx0 + k * (ux1 - ux0) / 2.0), rx1 - k * (ux1 - ux0) / 2.0)
        cy = min(max((uy0 + uy1) / 2.0, ry0 + k * (uy1 - uy0) / 2.0), ry1 - k * (uy1 - uy0) / 2.0)
        bx, by = (cx - k * (ux0 + ux1) / 2.0) / W, (cy - k * (uy0 + uy1) / 2.0) / H
        fitted = dict(shapes)
        for key in keys:
            if shapes.get(key):
                fitted[key] = [p if key in ("bands", "rules", "shapes") and _bleeds(p) else _frac_walk(p, k, bx, by)
                               for p in shapes[key]]
        shapes = fitted
        record["scale"] = round(record["scale"] * k, 4)
        record["moved_mm"] = [round(cx - (ux0 + ux1) / 2.0, 2), round(cy - (uy0 + uy1) / 2.0, 2)]
    outside = []
    for t in shapes.get("types") or []:
        if t.get("words"):
            e = _typed_extent(t, W, H, product_name)
            if e[0] < rx0 - 0.01 or e[2] > rx1 + 0.01 or e[1] < ry0 - 0.01 or e[3] > ry1 + 0.01:
                outside.append(t["part"])
    record["codes"] = ["%s:front:%s" % (FRONT_INSIDE_SAFE_MARGIN, part) for part in outside]
    return dict(map_front, shapes=shapes), record


#: [his go of 2026-10-02] the type a front drawn from its picture sets over its panel
CARTON_MAP_FRONT = "carton front drawn from its concept's map"


#: [his goal of 2026-10-13, (2)] the panels a box lying flat shows wide — its front and its back
_FLAT_SEEN = ("front", "back")


def _turned_by_panel(nodes: list, seen: list, gx, gy, panel_of, role: str) -> list:
    """[His goal of 2026-10-13, (2).] ``nodes`` with each laid out on a panel seen lying flat (``_seen_flat``) gathered
    into one group turned onto that panel of the die (``graph.quarter_turn``), in their order; the rest as they are."""
    turned = {p.name: p for p in seen if p.name in _FLAT_SEEN}
    groups, out = {}, []
    for n in nodes:
        name = panel_of(n) if getattr(n, "type", "") != "group" else None
        p = turned.get(name)
        if p is None:
            out.append(n)
            continue
        if name not in groups:
            groups[name] = Group(name="%s, laid out as the box lies" % name, role=role, children=[],
                                 turn=quarter_turn(p.width, p.height, gx(p.x), gy(p.y)))
            out.append(groups[name])
        groups[name].children.append(n)
    return out


def _seen_flat(p):
    """[His goal of 2026-10-13, (2).] A die's panel as it is seen on a box lying flat: as wide as the die stands it tall,
    as tall as it stands it wide, laid out upright at the panel's own place (the caller turns it onto the die)."""
    from types import SimpleNamespace
    return SimpleNamespace(name=p.name, x=p.x, y=p.y, width=p.height, height=p.width)


def _map_front_panel(map_front: dict, p, gx, gy, logo_path, logo_master, product_name, safe_mm: float = 0.0,
                     top_mm: float | None = None, *, panel_name: str = "front", ruled_mark: bool = True,
                     right_mm: float | None = None) -> tuple:
    """[His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a).] The carton's front panel ``p`` as
    its concept picture draws it — the container's own map front (``compose_container``: each band, rule and scattered
    motif the map traced, its type lines set where the picture sets them, the mark where the picture prints it, else
    the house mark at the panel's ruled place kept clear of them) on the panel's millimetres, the panel its outline and
    its print area. Returns ``(the drawn nodes, the mark's node(s), the record: what was drawn, its type measured against
    the panel — a line wider than the panel holds Gate 2, as the ruled front's does)``.
    [His test findings on design 123, 2026-10-09 (transcribed at cbdf721), (1): "Every panel is drawn from it."] any
    panel drawn so from its own map (``panel_name``) — its mark only where its picture prints one (``ruled_mark``
    False: never the house mark at a ruled place)."""
    from types import SimpleNamespace

    from apps.ire.compose_container import _map_front_group, _map_mark_box, _map_type_group, _mark_clear_of
    W, H = p.width, p.height
    # [his test findings on design 123, 2026-10-09, (4)] the concept's layout scaled as a whole (``uniform_layout``)
    map_front, uniform = uniform_layout(map_front, W, H)
    # [his review of 119, 2026-10-05, point 4] nothing inside the safe margin: the picture's parts fitted inside it
    safe = None
    if safe_mm:
        # [his final goal, 2026-10-05, B2] where the thumb notch is cut into the front's top edge, its key elements
        # stand clear of it too (``top_mm``: the notch's depth and a millimetre more, where that is past the margin)
        top = max(safe_mm, top_mm or 0.0)
        right = max(safe_mm, right_mm or 0.0)      # [his goal of 2026-10-13, (2)] a box lying flat: the notch at its right
        map_front, safe = inside_safe(map_front, W, H, safe_mm, product_name,
                                      rect=(safe_mm, top, W - right, H - safe_mm))
    # [His review of 127, 130, 131 and 132, 2026-10-15, C: the designer's eye on 132, "the Arabic line sits on the
    # label's bottom edge"] the lines a window or its frame holds kept inside it, top to foot
    map_front, frame_held = hold_in_frames(map_front)
    # [his second test blocker on design 123] a shape run to the foot stops at the fold onto the bottom tuck
    held = map_front.get("shapes") or {}
    if any(_bleeds(sh) for sh in held.get("shapes") or []):
        map_front = dict(map_front, shapes=dict(held, shapes=[_to_the_fold(sh) if _bleeds(sh) else sh
                                                               for sh in held.get("shapes") or []]))
    outline = [MoveTo(x=0.0, y=0.0), LineTo(x=W, y=0.0), LineTo(x=W, y=H), LineTo(x=0.0, y=H), ClosePath()]
    panel = SimpleNamespace(width_mm=W, height_mm=H, silhouette=outline, cap_region=[])
    zone = {"zone_id": "carton-front", "x": 0.0, "y": 0.0, "width": W, "height": H}
    ox, oy = gx(p.x), gy(p.y)
    group, _places, record = _map_front_group(map_front, zone, panel, 1.0, ox, oy)
    kids = [group] if group is not None else []
    # [His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 6: "FRONT TEXT: "Rose Blossom" in the granted face closest to the concept's soft rounded sans (Quicksand or Montserrat), ONE colour, never two pinks or the heavy house bold; "Hand Cream" in the same family, lighter; Arabic in a matching sans (Tajawal or Cairo), not Naskh. No hard rectangle cut out of the roses behind it; soft breathing room as the concept shows, and the soft oval cartouche behind the BBROSE logo."]
    # the front's own faces, where its concept letters its name in a sans (``front_faces``)
    from apps.ire.front_faces import ARABIC_ROLE, COPY_ROLE, KEY as FACES_KEY, NAME_ROLE
    faces = ({"name": NAME_ROLE, "copy": COPY_ROLE, "arabic": ARABIC_ROLE}
             if map_front.get(FACES_KEY) else None)
    typed = _map_type_group(map_front, zone, panel, 1.0, ox, oy, name_font="bold", product_name=product_name,
                            faces=faces)
    if typed is not None:
        kids.append(typed[0])
        record["boxes"].update(typed[2]["boxes"])
        record.update({k: v for k, v in typed[2].items() if k not in ("boxes", "gold_nodes")})
        record["gold_nodes"] += typed[2]["gold_nodes"]
        record["drawn"] += [line["part"] for line in typed[2]["typed"]]
    mark = _map_mark_box(map_front, zone, panel, 1.0, ox, oy, logo_master) if logo_master is not None else None
    logos = []
    if mark is not None:
        box = mark["box"]
        record["boxes"][mark["part"]] = mark["drawn_box"]
        record["mark"] = {k: mark[k] for k in ("fit", "beside_the_picture_mm", "ink")}
        record["drawn"].append(mark["part"])
    elif not ruled_mark:
        box = None
    else:
        ruled = _logo_nodes([p], logo_path, gx, gy, logo_master=logo_master)
        box = (ruled[0].x, ruled[0].y, ruled[0].w, ruled[0].h) if ruled else None
        if box is not None:
            box, where = _mark_clear_of(box, record["boxes"], zone, panel, 1.0, ox, oy)
            if where is not None:
                record["mark"] = {"placed": where, "why": "the picture prints no mark; the house mark kept clear of its parts"}
    if box is not None and logo_master is not None:
        from apps.ire import brand_mark
        node = brand_mark.mark_node("logo-%s" % panel_name, logo_master, *box)
        if mark is not None and mark["ink"]:
            node.recolor = Color.from_hex(mark["ink"])
        logos.append(node)
    elif box is not None and logo_path:
        logos.append(Image(name="logo-%s" % panel_name, src=logo_path, x=box[0], y=box[1], w=box[2], h=box[3]))
    over = [line["part"] for line in record.get("typed") or []
            if any(v < -0.001 or v > 1.001 for v in record["boxes"].get(line["part"], [0.0, 0.0, 1.0, 1.0]))]
    record["front_type"] = {"panel": panel_name,
                            "drawn_from": CARTON_MAP_FRONT if panel_name == "front" else map_front.get("drawn_from"),
                            "typed": [{k: line[k] for k in ("part", "words", "size_pt") if k in line}
                                      for line in record.get("typed") or []],
                            "codes": [f"{FRONT_COPY_EXCEEDS_PANEL}:{panel_name}:{part}" for part in over]}
    if safe is not None:
        record["safe_margin"] = safe
        record["front_type"]["codes"] += safe["codes"]
    if uniform is not None:
        record["uniform"] = uniform
    if frame_held:
        record["held_in_frame"] = frame_held
    return kids, logos, record


#: [His review of 127, 130, 131 and 132, 2026-10-15, C: the designer's eye on 132, "the Arabic line sits on the label's
#: bottom edge over the tile pattern".] the lines a window or frame holds stand inside it by this share of its height at
#: its top and its foot — the share it keeps them clear of its sides by (``compose_container.MAP_TYPE_FRAME_PAD``)
FRAME_HOLD_PAD = 0.06


def hold_in_frames(map_front: dict) -> tuple:
    """[His review of 127, 130, 131 and 132, 2026-10-15, C.] The type lines a window or frame holds — each whose centre
    it holds, and smaller than it — kept inside it top to foot by FRAME_HOLD_PAD of its height: where they run past,
    their rows drawn closer together as one block (their sizes with them), its top kept where the picture sets it unless
    that too runs past, never moved sideways. 132's read set its Arabic at 0.726-0.760 of the front, its cartouche's
    frame at 0.764: on the frame's line. ``(the map front, [what was held, each said])``."""
    shapes = map_front.get("shapes") or {}
    holders = [h for h in list(shapes.get("windows") or []) + list(shapes.get("frames") or []) if h.get("box")]
    types = list(shapes.get("types") or [])
    said = []
    for holder in sorted(holders, key=lambda h: (h["box"][2] - h["box"][0]) * (h["box"][3] - h["box"][1])):
        bx0, by0, bx1, by1 = (float(v) for v in holder["box"])
        held = [i for i, t in enumerate(types) if t.get("words") and t.get("box")
                and bx0 <= (t["box"][0] + t["box"][2]) / 2.0 <= bx1 and by0 <= (t["box"][1] + t["box"][3]) / 2.0 <= by1
                and (t["box"][2] - t["box"][0]) * (t["box"][3] - t["box"][1]) < (bx1 - bx0) * (by1 - by0)]
        if not held:
            continue
        top, foot = min(float(types[i]["box"][1]) for i in held), max(float(types[i]["box"][3]) for i in held)
        pad = FRAME_HOLD_PAD * (by1 - by0)
        lo, hi = by0 + pad, by1 - pad
        if top >= lo - 1e-9 and foot <= hi + 1e-9 or foot <= top:
            continue
        # the block's top kept where the picture sets it (what stands above it — 132's lily — never run into), its rows
        # drawn closer to its foot; moved down only where its top too runs past
        new_top = max(top, lo)
        k = min(1.0, (hi - new_top) / (foot - top))
        for i in held:
            types[i] = _frac_walk(types[i], 1.0, 0.0, new_top - k * top, k)
        said.append({"holder": holder.get("part"), "lines": [types[i].get("part") for i in held],
                     "rows": [round(top, 4), round(foot, 4)], "to": [round(new_top, 4), round(new_top + k * (foot - top), 4)],
                     "why": "kept inside the frame that holds them, %g of its height clear of its top and foot"
                            % FRAME_HOLD_PAD})
    if not said:
        return map_front, []
    return dict(map_front, shapes=dict(shapes, types=types)), said


# --- node builders -----------------------------------------------------------


def _poly_segments(coords_seq, gx, gy) -> list[Segment]:
    pts = list(coords_seq)
    segs: list[Segment] = [MoveTo(x=gx(pts[0][0]), y=gy(pts[0][1]))]
    for x, y in pts[1:]:
        segs.append(LineTo(x=gx(x), y=gy(y)))
    return segs


def _rect_clip(p, gx, gy) -> list[Segment]:
    return [MoveTo(x=gx(p.x), y=gy(p.y)),
            LineTo(x=gx(p.x + p.width), y=gy(p.y)),
            LineTo(x=gx(p.x + p.width), y=gy(p.y + p.height)),
            LineTo(x=gx(p.x), y=gy(p.y + p.height))]


def _component_clip_segments(coords, comp_id, gx, gy) -> list[Segment] | None:
    """The flap/tab outline as graph segments (Bézier tuck shoulders kept)."""
    from apps.dielines.geometry.primitives import CubicSeg
    prims = coords.component_paths.get(comp_id)
    if prims:
        x0, y0 = prims[0].p0
        segs: list[Segment] = [MoveTo(x=gx(x0), y=gy(y0))]
        for seg in prims:
            if isinstance(seg, CubicSeg):
                segs.append(CubicTo(
                    x1=gx(seg.c1[0]), y1=gy(seg.c1[1]),
                    x2=gx(seg.c2[0]), y2=gy(seg.c2[1]),
                    x=gx(seg.p1[0]), y=gy(seg.p1[1])))
            else:
                segs.append(LineTo(x=gx(seg.p1[0]), y=gy(seg.p1[1])))
        return segs
    poly = component_polygon(coords, comp_id)
    if poly is None:
        return None
    ext = list(poly.exterior.coords)
    return [MoveTo(x=gx(ext[0][0]), y=gy(ext[0][1]))] + [
        LineTo(x=gx(x), y=gy(y)) for x, y in ext[1:]]


def _logo_nodes(art_panels, logo_path, gx, gy, logo_master=None) -> list:
    import os
    if logo_master is not None:
        # [the owner's second answer of 2026-09-25: the approved vector master's ink bounds give the height, and each
        # panel's mark is drawn from it — the same box the raster gets]
        from apps.ire import brand_mark
        ratio = logo_master.aspect
    else:
        if not (logo_path and os.path.exists(logo_path)):
            return []
        from PIL import Image as PILImage
        with PILImage.open(logo_path) as im:
            lw, lh = im.size
        ratio = lh / lw if lw else 0.3
    nodes = []
    for p in art_panels:
        span = p.width * 0.62
        h = span * ratio
        lx = p.x + (p.width - span) / 2.0
        ly = p.y + p.height * 0.16          # upper band (y-down from top)
        if logo_master is not None:
            nodes.append(brand_mark.mark_node(f"logo-{p.name}", logo_master, gx(lx), gy(ly), span, h))
            continue
        nodes.append(Image(name=f"logo-{p.name}", src=logo_path,
                           x=gx(lx), y=gy(ly), w=span, h=h))
    return nodes


def _type_nodes(art_panels, product_name, subtitle, tint_c, gx, gy, *, faces=None, safe_mm=4.0,
                logo_bottoms=None) -> tuple[list, dict]:
    """The front's name and the line under it, SET AS TYPE and MEASURED (§BH55 Phase 2): each in the face the emitter
    draws it with, against its panel's width inside the safe margin. A name wider than that is set in two or three
    balanced lines at the SAME size — never smaller, never cut — its block standing where the one line stood, and
    clear of the logo above it; what still does not fit is recorded over, with the code that holds Gate 2."""
    from apps.ire.back_panel import LEADING_EM, MM_PER_PT
    from apps.ire.compose_artwork import _face, _split, _width_mm, _wrap
    from apps.ire.compose_dropper import NAME_LEADING_EM
    from apps.ire.graph import PRINTED_ON_PRODUCT, PrintScope
    from apps.ire.text_metrics import cap_height_em
    # ink chosen by tint luminance so type stays readable on dark grounds
    lum = 0.299 * tint_c.r + 0.587 * tint_c.g + 0.114 * tint_c.b
    ink = (Color.from_hex("#F7F0E6") if lum < 0.5 else Color.from_hex("#59283A"))
    faces = faces or {}
    bold, regular = _face("bold", faces), _face("regular", faces)
    name_pitch_mm = FRONT_NAME_PT * MM_PER_PT * NAME_LEADING_EM
    line_pitch_mm = FRONT_LINE_PT * MM_PER_PT * LEADING_EM
    name_cap_mm = FRONT_NAME_PT * MM_PER_PT * cap_height_em(dict(faces.values()).get(bold) if bold else None)
    nodes, panels, codes = [], [], []

    def fitted(text, size_pt, face, avail_mm):
        """The fewest lines at this size, by MEASURED word wrap (a word wider than the line stands alone and is measured
        as such) — balanced when the balanced lines measure inside the width too."""
        lines = _wrap(text, size_pt, face, avail_mm)
        balanced = _split(text, len(lines))
        if len(balanced) == len(lines) and all(
                (w := _width_mm(ln, size_pt, face)) is not None and w <= avail_mm for ln in balanced):
            lines = balanced
        return lines, [_width_mm(ln, size_pt, face) for ln in lines]

    for p in art_panels:
        cx = p.x + p.width / 2.0
        avail_mm = p.width - 2 * safe_mm
        scope = PrintScope(kind=PRINTED_ON_PRODUCT, surface=f"carton-{p.name}")
        rec = {"panel": p.name, "avail_mm": round(avail_mm, 2)}
        if product_name:
            lines, widths = fitted(product_name, FRONT_NAME_PT, bold, avail_mm)
            base_mm = p.y + p.height * 0.52                     # the last line stands where the one line stood
            first_mm = base_mm - (len(lines) - 1) * name_pitch_mm
            for i, line in enumerate(lines):
                nodes.append(TextRun(
                    name="product-name" if i == 0 else f"product-name-{i}", text=line,
                    x=gx(cx), y=gy(first_mm + i * name_pitch_mm), align="center",
                    font="bold", size_pt=FRONT_NAME_PT, color=ink, print_scope=scope))
            top_mm = first_mm - name_cap_mm
            logo_mm = (logo_bottoms or {}).get(p.name)
            rec["name"] = {"lines": lines, "widths_mm": [None if w is None else round(w, 2) for w in widths],
                           "size_pt": FRONT_NAME_PT, "top_mm": round(top_mm - p.y, 2),
                           "logo_bottom_mm": None if logo_mm is None else round(logo_mm - p.y, 2)}
            if any(w is None for w in widths):
                codes.append(f"{FRONT_COPY_UNMEASURED}:{p.name}:name")
            elif (any(w > avail_mm for w in widths) or len(lines) > FRONT_NAME_MOST_LINES
                  or (logo_mm is not None and top_mm < logo_mm)):
                codes.append(f"{FRONT_COPY_EXCEEDS_PANEL}:{p.name}:name")
        if subtitle:
            lines, widths = fitted(subtitle, FRONT_LINE_PT, regular, avail_mm)
            for i, line in enumerate(lines):
                nodes.append(TextRun(
                    name="subtitle" if i == 0 else f"subtitle-{i}", text=line,
                    x=gx(cx), y=gy(p.y + p.height * 0.60 + i * line_pitch_mm), align="center",
                    font="regular", size_pt=FRONT_LINE_PT, color=ink, print_scope=scope))
            rec["line"] = {"lines": lines, "widths_mm": [None if w is None else round(w, 2) for w in widths],
                           "size_pt": FRONT_LINE_PT}
            if any(w is None for w in widths):
                codes.append(f"{FRONT_COPY_UNMEASURED}:{p.name}:line")
            elif any(w > avail_mm for w in widths) or len(lines) > FRONT_LINE_MOST_LINES:
                codes.append(f"{FRONT_COPY_EXCEEDS_PANEL}:{p.name}:line")
        panels.append(rec)
    return nodes, {"schema": FRONT_TYPE_KEY, "safe_mm": safe_mm, "panels": panels, "codes": codes}


#: [his final goal, 2026-10-05, B2: "Each on its own named layer: CUT, CREASE, GLUE, BLEED, SAFE, ARTWORK."] a document
#: drawn on named layers: its root's groups named for them, everything else its ARTWORK
LAYERS_KEY = "layers/1.0"


def _structure_layers(coords, gx, gy) -> tuple:
    """[His final goal, B2: "Cut lines solid; crease lines dashed on EVERY fold, including flap hinges and the tuck
    fold."] ``(CUT nodes, CREASE nodes)``: the die's one outline with its holes (the friction slits) and its open cuts
    (the tuck folds' lock slits), solid; every fold — the panels', the flap hinges', the tuck folds' — dashed. No halo:
    a white stroke under a line knocks the artwork out where it prints."""
    cut_segs = _poly_segments(coords.cut_polygon.exterior.coords, gx, gy) + [ClosePath()]
    for ring in coords.cut_polygon.interiors:
        cut_segs += _poly_segments(ring.coords, gx, gy) + [ClosePath()]
    cut = [Path(name="cut", segments=cut_segs, stroke=Stroke(color=_CUT, width_mm=_W_CUT))]
    for i, (x1, y1, x2, y2) in enumerate(coords.slit_lines):
        cut.append(Path(name=f"slit-{i}", segments=[MoveTo(x=gx(x1), y=gy(y1)), LineTo(x=gx(x2), y=gy(y2))],
                        stroke=Stroke(color=_CUT, width_mm=_W_CUT)))
    crease = [Path(name=f"fold-{i}", segments=[MoveTo(x=gx(x1), y=gy(y1)), LineTo(x=gx(x2), y=gy(y2))],
                   stroke=Stroke(color=_FOLD, width_mm=_W_FOLD, dash=(1.06, 0.71)))
              for i, (x1, y1, x2, y2) in enumerate(coords.fold_lines)]
    return cut, crease


def _guide_layers(coords, gx, gy, safe_mm: float) -> list:
    """[His final goal, B2: "The glue area marked; bleed and safe-area lines; dimensions labelled."] The GLUE, BLEED,
    SAFE and DIMENSIONS groups — guides drawn on screen in one guide colour, never printed (``counter_display_files``)."""
    from apps.dielines.exporters.counter_display_files import GUIDE_HEX
    guide = Color.from_hex(GUIDE_HEX)
    thin = Stroke(color=guide, width_mm=0.1)
    dashed = Stroke(color=guide, width_mm=0.1, dash=(1.0, 0.8))
    groups = []
    tab = getattr(coords, "glue_tab_polygon", None)
    if tab is not None:
        x0, y0, x1, y1 = tab.bounds
        hatch = []
        step = 2.5
        t = -(y1 - y0)
        while t < (x1 - x0):
            a = (max(x0, x0 + t), y0 + max(0.0, -t))
            b = (min(x1, x0 + t + (y1 - y0)), y0 + min(y1 - y0, (x1 - x0) - t))
            hatch += [MoveTo(x=gx(a[0]), y=gy(a[1])), LineTo(x=gx(b[0]), y=gy(b[1]))]
            t += step
        groups.append(Group(name="GLUE", role="generic", children=[
            Path(name="glue-area", segments=_poly_segments(tab.exterior.coords, gx, gy) + [ClosePath()], stroke=thin),
            Path(name="glue-hatch", segments=hatch, stroke=thin),
            TextRun(name="glue-label", text="GLUE — NO INK", x=gx((x0 + x1) / 2.0) + 1.0, y=gy((y0 + y1) / 2.0),
                    size_pt=5.0, color=guide, align="center", rotation_deg=90.0)]))
    groups.append(Group(name="BLEED", role="generic", children=[
        Path(name="bleed-line", segments=_poly_segments(coords.bleed_polygon.exterior.coords, gx, gy) + [ClosePath()],
             stroke=dashed)]))
    safe = []
    for p in coords.panels:
        if p.name not in _ARTWORK_PANELS:
            continue
        safe.append(Path(name=f"safe-{p.name}", stroke=dashed, segments=[
            MoveTo(x=gx(p.x + safe_mm), y=gy(p.y + safe_mm)), LineTo(x=gx(p.x + p.width - safe_mm), y=gy(p.y + safe_mm)),
            LineTo(x=gx(p.x + p.width - safe_mm), y=gy(p.y + p.height - safe_mm)),
            LineTo(x=gx(p.x + safe_mm), y=gy(p.y + p.height - safe_mm)), ClosePath()]))
    groups.append(Group(name="SAFE", role="generic", children=safe))
    bx0, by0, bx1, by1 = coords.bleed_polygon.bounds
    cx0, cy0, cx1, cy1 = coords.cut_polygon.bounds
    w, d, h = coords.dimensions.manufacture
    yb = by1 + 4.0
    xl = bx0 - 4.0
    dims = [Path(name="dim-flat-width", stroke=thin, segments=[
                MoveTo(x=gx(cx0), y=gy(yb)), LineTo(x=gx(cx1), y=gy(yb)),
                MoveTo(x=gx(cx0), y=gy(yb - 1.2)), LineTo(x=gx(cx0), y=gy(yb + 1.2)),
                MoveTo(x=gx(cx1), y=gy(yb - 1.2)), LineTo(x=gx(cx1), y=gy(yb + 1.2))]),
            TextRun(name="dim-flat-width-label", text="%g mm" % round(cx1 - cx0, 1), x=gx((cx0 + cx1) / 2.0),
                    y=gy(yb - 0.8), size_pt=5.0, color=guide, align="center"),
            Path(name="dim-flat-height", stroke=thin, segments=[
                MoveTo(x=gx(xl), y=gy(cy0)), LineTo(x=gx(xl), y=gy(cy1)),
                MoveTo(x=gx(xl - 1.2), y=gy(cy0)), LineTo(x=gx(xl + 1.2), y=gy(cy0)),
                MoveTo(x=gx(xl - 1.2), y=gy(cy1)), LineTo(x=gx(xl + 1.2), y=gy(cy1))]),
            TextRun(name="dim-flat-height-label", text="%g mm" % round(cy1 - cy0, 1), x=gx(xl - 0.8),
                    y=gy((cy0 + cy1) / 2.0), size_pt=5.0, color=guide, align="center", rotation_deg=90.0),
            *[TextRun(name="dim-carton" if i == 0 else "dim-carton-%d" % i, text=line, x=gx(cx0), y=gy(yb + 4.5 + 2.3 * i),
                      size_pt=5.0, color=guide, align="left")
              for i, line in enumerate(_carton_words(coords, w, d, h, cx1 - cx0, cy1 - cy0, cx0 - bx0, safe_mm))],
            # [his second goal of 2026-10-06, item 2: TRADE_RULES.md R1, E3] the grain and the side shown, for the converter
            TextRun(name="dim-grain", text="Grain parallel to the height (converter to confirm) · print side shown",
                    x=gx(cx0), y=gy(yb + 4.5 + 2.3 * len(_carton_words(coords, w, d, h, cx1 - cx0, cy1 - cy0,
                                                                      cx0 - bx0, safe_mm))),
                    size_pt=5.0, color=guide, align="left")]
    for p in coords.panels:
        # each panel's width on the dimension line, under its panel — never a guide's word on the artwork
        dims.append(TextRun(name=f"dim-{p.name}", text="%g" % round(p.width, 2), x=gx(p.x + p.width / 2.0),
                            y=gy(yb + 2.6), size_pt=4.0, color=guide, align="center"))
    groups.append(Group(name="DIMENSIONS", role="generic", children=dims))
    return groups


def _carton_words(coords, w, d, h, flat_w, flat_h, bleed, safe_mm) -> list:
    """The die's own words, line by line. [His second goal of 2026-10-06, item 2] a die drawn to the trade's rules (1.4)
    says its style and ECMA code, its inside and its crease-to-crease sizes, and its board — what a converter reads
    first — on lines of its own, each short enough to stay on the artboard; an older die says its sizes as before."""
    derived = getattr(coords, "derived", None) or {}
    tail = "flat %g × %g mm · bleed %g mm · safe %g mm" % (round(flat_w, 1), round(flat_h, 1), round(bleed, 1), safe_mm)
    if derived.get("dimension_semantics") != "inside":
        return ["W %g × D %g × H %g mm · %s" % (w, d, h, tail)]
    iw, idp, ih = coords.dimensions.inner
    return ["%s · inside W %g × D %g × H %g mm" % (derived.get("style_words", "").split(":")[0], iw, idp, ih),
            "creases %g × %g × %g mm · board %g mm · %s" % (w, d, h, coords.board_thickness_mm, tail)]


def _structure_nodes(coords, gx, gy) -> list:
    cut = _poly_segments(coords.cut_polygon.exterior.coords, gx, gy)
    nodes = [
        # white halo first (keeps lines readable over full-surface artwork)
        Path(name="cut-halo", segments=cut,
             stroke=Stroke(color=_WHITE, width_mm=_W_HALO)),
    ]
    for i, (x1, y1, x2, y2) in enumerate(coords.fold_lines):
        nodes.append(Path(name=f"fold-halo-{i}",
                          segments=[MoveTo(x=gx(x1), y=gy(y1)),
                                    LineTo(x=gx(x2), y=gy(y2))],
                          stroke=Stroke(color=_WHITE, width_mm=_W_HALO)))
    nodes.append(Path(name="cut", segments=cut,
                      stroke=Stroke(color=_CUT, width_mm=_W_CUT)))
    for i, (x1, y1, x2, y2) in enumerate(coords.fold_lines):
        nodes.append(Path(name=f"fold-{i}",
                          segments=[MoveTo(x=gx(x1), y=gy(y1)),
                                    LineTo(x=gx(x2), y=gy(y2))],
                          stroke=Stroke(color=_FOLD, width_mm=_W_FOLD,
                                        dash=(1.06, 0.71))))
    return nodes
