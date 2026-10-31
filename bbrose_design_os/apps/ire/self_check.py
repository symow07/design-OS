"""[His final goal, 2026-10-05 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32e9aaf), C7: "THE SYSTEM CHECKS ITS OWN
WORK. Inspect the drawn output for defects: bumps, notches or spurs on outlines (e.g. 119's silhouette, bottom right);
stray specks; overlaps; text touching or crossing; cut text; wrong glyphs ("the ℮ must be the real estimated sign, not
'e'"); elements in the safe margin. Fix them itself, or show what and where. Never hand me a defect silently."]

Two passes round every drawing — a carton's, a container's, each artwork format's — both before he sees it:

- ``repair(doc)`` — on the Design Graph, before it is measured or drawn. A traced outline's defects: the pieces opening
  and closing it at 0.35 mm take off (a bump, a spur) or fill in (a dent, a notch), standing 0.05 mm off it; on a shape
  that is its own mirror (a bottle, a vial) only where its mirror image has nothing of the kind within 2 mm (the neck's
  threads repeat on both sides and are the shape, never a defect). Each stretch of them is redrawn as ONE smooth curve
  through it, along the outline's own tangents either side, on the part's solid, rim and shadow together — 119's right
  edge, which wobbled over 5 mm. A speck (an island under 0.3 mm²) is removed. An "e" after a quantity is set as ℮.
  Lettering, marks, codes, bands and the carton's ground are never touched.
- ``inspect(pdf, regions)`` — on the drawn file: text crossing text, a line across a traced shape's edge or on it in an
  ink that does not read, a line cut by a fold, a line in the safe margin, an "e" where ℮ belongs, a character its face
  has no glyph for — each shown with its panel and its millimetres; nothing here is changed by the eye of the check.

A pass that cannot run is itself shown: a check that did not happen is never read as a clean one. The record
(``SCHEMA``) keeps both — what was fixed and what is shown — and the design's page lists every one beside Approve."""
from __future__ import annotations

import re

SCHEMA = "self_check/1.0"
OPEN_MM = 0.35            # a feature thinner than twice this vanishes as the outline is opened (spur) or closed (notch)
MIN_LENGTH_MM = 0.5       # on a shape that is not its own mirror, a defect is longer than this
MIN_DEPTH_MM = 0.05       # and every defect stands this far off the outline (its widest inscribed circle)
MIN_AREA_MM2 = 0.005
SPECK_MM2 = 0.3           # an island of a traced shape smaller than this is a speck
SYMMETRIC_IOU = 0.85      # a shape this close to its mirror image is symmetric
PAIR_MM = 2.0             # a piece whose mirror lands this close to a piece of its kind is the shape's own (threads)
CLUSTER_MM = 6.0          # one side's defects this close together are one stretch of wobble
BAND_MM = 1.0             # and the smooth curve redrawn through a stretch reaches this far past it
OVERLAP_MM = 0.25
CROSS_LOW, CROSS_HIGH = 0.12, 0.88   # a line this much on a traced solid and the rest off it crosses its edge
WRONG_E = re.compile(r"\d\s*(?:ml|mL|ML|g|G|oz|fl\.?\s*oz)\.?\s+[eE](?=\s|$|/)")
ESTIMATED = "℮"


# ---------------------------------------------------------------------------------------------- geometry of a path

def _sample(segs, steps: int = 16) -> list:
    """A path's rings as point lists, its cubics sampled."""
    rings, cur, last = [], None, None
    for s in segs:
        if s.op == "M":
            cur = [(s.x, s.y)]
            rings.append(cur)
            last = (s.x, s.y)
        elif s.op == "L":
            cur.append((s.x, s.y))
            last = (s.x, s.y)
        elif s.op == "C":
            x0, y0 = last
            for i in range(1, steps + 1):
                t = i / steps
                u = 1 - t
                cur.append((u ** 3 * x0 + 3 * u * u * t * s.x1 + 3 * u * t * t * s.x2 + t ** 3 * s.x,
                            u ** 3 * y0 + 3 * u * u * t * s.y1 + 3 * u * t * t * s.y2 + t ** 3 * s.y))
            last = (s.x, s.y)
    return [r for r in rings if len(r) >= 3]


def _polygon(segs):
    """The path's filled area (nonzero), its rings united, holes taken out where a ring sits inside another."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = []
    for ring in _sample(segs):
        p = Polygon(ring).buffer(0)
        if not p.is_empty:
            polys.append(p)
    if not polys:
        return None
    polys.sort(key=lambda p: -p.area)
    shape = polys[0]
    for p in polys[1:]:
        shape = shape.difference(p) if shape.contains(p) else unary_union([shape, p])
    return shape


def _mirror(geom, axis_x: float):
    from shapely.affinity import scale
    return scale(geom, xfact=-1.0, yfact=1.0, origin=(axis_x, 0.0))


def _pieces(geom):
    return [g for g in getattr(geom, "geoms", [geom]) if not g.is_empty and g.area > 0]


def _length(piece) -> float:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)       # a degenerate sliver's envelope divides by zero
        rect = piece.minimum_rotated_rectangle
    xs, ys = rect.exterior.coords.xy
    return max(((xs[i] - xs[i + 1]) ** 2 + (ys[i] - ys[i + 1]) ** 2) ** 0.5 for i in range(4))


def _depth(piece) -> float:
    """How far a piece stands off the outline: the diameter of the widest circle inside it."""
    import shapely
    return 2.0 * shapely.maximum_inscribed_circle(piece, 0.005).length


def symmetry(shape) -> tuple:
    """``(symmetric, axis)``: whether the shape is its own mirror about the vertical through its centroid (a bottle, a
    vial), and that axis."""
    axis = shape.centroid.x                     # a spike off one edge barely moves it; it moves the bounds' middle
    twin = _mirror(shape, axis)
    return shape.intersection(twin).area / max(shape.union(twin).area, 1e-9) >= SYMMETRIC_IOU, axis


def outline_defects(shape) -> list:
    """``[{"kind": "spur"|"notch", "piece": geom, "at": (x, y), "length_mm", "depth_mm"}]`` — the pieces opening and
    closing the shape at OPEN_MM take off (a spur, a bump) or fill in (a notch, a dent), standing MIN_DEPTH_MM off the
    outline. On a shape that is its own mirror, a piece is a defect when its mirror image lands nowhere near a piece of
    its kind (the neck's threads repeat on both sides and are the shape); on any other shape, when it is longer than
    MIN_LENGTH_MM (a corner's tip is not)."""
    if shape is None or shape.is_empty:
        return []
    opened = shape.buffer(-OPEN_MM, join_style=1).buffer(OPEN_MM, join_style=1)
    closed = shape.buffer(OPEN_MM, join_style=1).buffer(-OPEN_MM, join_style=1)
    found = {"spur": [p for p in _pieces(shape.difference(opened)) if p.area > MIN_AREA_MM2],
             "notch": [p for p in _pieces(closed.difference(shape)) if p.area > MIN_AREA_MM2]}
    symmetric, axis = symmetry(shape)
    out = []
    for kind, pieces in found.items():
        for p in pieces:
            depth = _depth(p)
            if depth < MIN_DEPTH_MM:
                continue
            if symmetric:
                m = _mirror(p, axis).centroid
                if any(m.distance(q.centroid) <= PAIR_MM for q in pieces):
                    continue                                    # its mirror has one too: the shape's own feature
            elif _length(p) <= MIN_LENGTH_MM:
                continue
            c = p.representative_point()
            out.append({"kind": kind, "piece": p, "at": (round(c.x, 2), round(c.y, 2)),
                        "length_mm": round(_length(p), 2), "depth_mm": round(depth, 2)})
    return out


def stretches(defects: list, axis: float) -> list:
    """One side's defects gathered into stretches of wobble: ``[{"side": "left"|"right", "y0", "y1", "defects"}]``."""
    out = []
    for side in ("left", "right"):
        mine = sorted((d for d in defects if (d["piece"].centroid.x > axis) == (side == "right")),
                      key=lambda d: d["piece"].bounds[1])
        for d in mine:
            _x0, y0, _x1, y1 = d["piece"].bounds
            if out and out[-1]["side"] == side and y0 - out[-1]["y1"] <= CLUSTER_MM:
                out[-1]["y1"] = max(out[-1]["y1"], y1)
                out[-1]["defects"].append(d)
            else:
                out.append({"side": side, "y0": y0, "y1": y1, "defects": [d]})
    return out


def _bezier(p0, s, t: float) -> tuple:
    if s.op == "L":
        return (p0[0] + (s.x - p0[0]) * t, p0[1] + (s.y - p0[1]) * t)
    u = 1.0 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * s.x1 + 3 * u * t * t * s.x2 + t ** 3 * s.x,
            u ** 3 * p0[1] + 3 * u * u * t * s.y1 + 3 * u * t * t * s.y2 + t ** 3 * s.y)


def _unit(dx: float, dy: float) -> tuple:
    n = (dx * dx + dy * dy) ** 0.5
    return (dx / n, dy / n) if n > 1e-9 else (0.0, 0.0)


def _tangent_out(p0, s) -> tuple:
    """The direction a drawn segment leaves its end in."""
    if s.op == "C":
        for hx, hy in ((s.x2, s.y2), (s.x1, s.y1), p0):
            if abs(s.x - hx) + abs(s.y - hy) > 1e-9:
                return _unit(s.x - hx, s.y - hy)
    return _unit(s.x - p0[0], s.y - p0[1])


def _tangent_in(p0, s) -> tuple:
    """The direction a drawn segment leaves its start in."""
    if s.op == "C":
        for hx, hy in ((s.x1, s.y1), (s.x2, s.y2), (s.x, s.y)):
            if abs(hx - p0[0]) + abs(hy - p0[1]) > 1e-9:
                return _unit(hx - p0[0], hy - p0[1])
    return _unit(s.x - p0[0], s.y - p0[1])


def smooth_through(segs: list, inside) -> tuple:
    """``(segments, replaced)`` — in each closed ring of a path, every run of drawn segments that passes through the
    region ``inside((x, y))`` names is replaced with ONE cubic from the last point before the run to the first after it,
    its handles along the outline's own tangents there: the outline is redrawn smooth through the region and joins the
    rest of it without a seam; every other segment, and every ring the region misses, is kept as it was."""
    from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo
    out, replaced, i = [], 0, 0
    while i < len(segs):
        if segs[i].op != "M":
            out.append(segs[i])
            i += 1
            continue
        j = i + 1
        while j < len(segs) and segs[j].op in ("C", "L"):
            j += 1
        closed = j < len(segs) and segs[j].op == "Z"
        start, draws = (segs[i].x, segs[i].y), list(segs[i + 1:j])
        i = j + (1 if closed else 0)
        if not closed or len(draws) < 3:
            out += [MoveTo(x=start[0], y=start[1])] + draws + ([ClosePath()] if closed else [])
            continue
        if abs(draws[-1].x - start[0]) + abs(draws[-1].y - start[1]) > 1e-6:
            draws.append(LineTo(x=start[0], y=start[1]))          # the closing line, drawn, so the ring can turn
        m = len(draws)
        begins = [start] + [(d.x, d.y) for d in draws[:-1]]
        touched = [any(inside(_bezier(begins[k], draws[k], t / 8.0)) for t in range(9)) for k in range(m)]
        if all(touched) or not any(touched):
            out += [MoveTo(x=start[0], y=start[1])] + draws + [ClosePath()]
            continue
        r = next(k for k in range(m) if not touched[k])           # the ring turned to begin after an untouched segment
        order = list(range(r + 1, m)) + list(range(0, r + 1))
        draws = [draws[k] for k in order]
        begins = [begins[k] for k in order]
        touched = [touched[k] for k in order]
        new, k = [], 0
        while k < m:
            if not touched[k]:
                new.append(draws[k])
                k += 1
                continue
            l = k
            while l + 1 < m and touched[l + 1]:
                l += 1
            a, b = begins[k], (draws[l].x, draws[l].y)
            tin = _tangent_out(begins[k - 1], draws[k - 1])
            tout = _tangent_in(b, draws[(l + 1) % m])
            third = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 / 3.0
            new.append(CubicTo(x1=a[0] + tin[0] * third, y1=a[1] + tin[1] * third,
                               x2=b[0] - tout[0] * third, y2=b[1] - tout[1] * third, x=b[0], y=b[1]))
            replaced += l - k + 1
            k = l + 1
        first = begins[0]
        out += [MoveTo(x=first[0], y=first[1])] + new + [ClosePath()]
    return out, replaced


def _drop_specks(segs: list) -> tuple:
    """``(segments, [speck])`` — the rings of a path that stand alone (inside no other ring) and enclose less than
    SPECK_MM2, dropped."""
    from shapely.geometry import Polygon
    rings, cur = [], None
    for s in segs:
        if s.op == "M":
            cur = [s]
            rings.append(cur)
        elif cur is not None:
            cur.append(s)
    polys = []
    for ring in rings:
        pts = _sample(ring)
        polys.append(Polygon(pts[0]).buffer(0) if pts else None)
    keep, specks = [], []
    for n, (ring, p) in enumerate(zip(rings, polys)):
        alone = p is not None and not any(q is not None and m != n and q.area > p.area and q.contains(p)
                                          for m, q in enumerate(polys))
        if alone and p.area < SPECK_MM2 and len(rings) > 1:
            specks.append(p)
            continue
        keep += ring
    return keep, specks


def _panel_of(x: float, y: float, regions: list):
    for r in regions:
        if r["x"] <= x <= r["x"] + r["w"] and r["y"] <= y <= r["y"] + r["h"]:
            return r
    return None


# ------------------------------------------------------------------------------------------ pass 1: on the graph

#: the traced parts the repair reads, by name: a part's solid shape, the pale rim round it and the rim's shadow — never
#: the carton's ground (its die line carries the thumb notch), a band's drips, lettering, a mark or a code
SHAPE_NAMES = ("shape-map-", "shape-rim-")


def repair(doc, regions: list | None = None) -> list:
    """The traced shapes of ``doc`` repaired in place, before it is drawn: ``[finding]``, each with what and where (the
    region it stands in, by name, and its millimetres). A speck (an island under SPECK_MM2) is removed. A part's outline
    defects (``outline_defects``) — on a shape that is its own mirror, a stretch of one edge whose mirror is clean — are
    redrawn as one smooth curve through the stretch, on the part's solid, rim and shadow together; a defect the curve
    does not mend is shown, not fixed."""
    from shapely.geometry import box

    from apps.ire.graph import Group, Path
    findings = []

    def where(x, y):
        r = _panel_of(x, y, regions or [])
        return {"panel": r["name"] if r else None, "x_mm": round(x - (r["x"] if r else 0.0), 1),
                "y_mm": round(y - (r["y"] if r else 0.0), 1)}

    parts = {}

    def visit(group):
        for i, node in enumerate(group.children):
            if isinstance(node, Group):
                visit(node)
            elif isinstance(node, Path) and node.fill is not None and str(node.name or "").startswith(SHAPE_NAMES):
                parts.setdefault((id(group), str(node.name).rsplit("-", 1)[-1]), []).append((group, i))

    visit(doc.root)
    if doc.inside is not None:
        visit(doc.inside)

    # [his final goal, C7: "the ℮ must be the real estimated sign, not 'e'"] an "e" after a quantity, set as the sign
    def signs(group):
        from apps.ire.graph import StickerBridge, TextRun
        for i, node in enumerate(group.children):
            if isinstance(node, Group):
                signs(node)
            elif isinstance(node, TextRun) and WRONG_E.search(node.text or ""):
                group.children[i] = node.model_copy(update={"text": normalise_estimated(node.text)})
                findings.append({"kind": "wrong glyph", "fixed": True, **where(node.x, node.y),
                                 "what": "%r printed an 'e' where the estimated sign belongs — set as ℮"
                                 % node.text[:40]})
            elif isinstance(node, StickerBridge):
                # the label is drawn from its own words: a quantity's "e" there set as the sign before it is drawn
                wrong = {k: v for k, v in (node.info or {}).items() if isinstance(v, str) and WRONG_E.search(v)}
                if wrong:
                    info = dict(node.info, **{k: normalise_estimated(v) for k, v in wrong.items()})
                    group.children[i] = node.model_copy(update={"info": info})
                    for k, v in wrong.items():
                        findings.append({"kind": "wrong glyph", "fixed": True, **where(node.x, node.y),
                                         "what": "the label's %s %r printed an 'e' where the estimated sign belongs "
                                                 "— set as ℮" % (k.replace("_", " "), v[:40])})

    signs(doc.root)
    if doc.inside is not None:
        signs(doc.inside)
    for members in parts.values():
        shapes = []
        for group, i in members:
            node = group.children[i]
            segs, specks = _drop_specks(list(node.segments))
            for p in specks:
                c = p.representative_point()
                findings.append({"kind": "speck", "fixed": True, "what": "a speck of %s (%.2f mm²) removed"
                                 % (node.name, p.area), **where(c.x, c.y)})
            if specks:
                group.children[i] = node = node.model_copy(update={"segments": segs})
            shapes.append((group, i, node, _polygon(node.segments)))
        primary = next((s for s in shapes if str(s[2].name).startswith("shape-map-")), shapes[0])
        if primary[3] is None:
            continue
        symmetric, axis = symmetry(primary[3])
        defects = [d for s in shapes if s[3] is not None for d in outline_defects(s[3])]
        if not defects:
            continue
        x0, _y0, x1, _y1 = primary[3].bounds
        if symmetric:
            regions_of = []
            for st in stretches(defects, axis):
                lo, hi = (axis, x1 + 2.0) if st["side"] == "right" else (x0 - 2.0, axis)
                regions_of.append((box(lo, st["y0"] - BAND_MM, hi, st["y1"] + BAND_MM), st))
        else:
            regions_of = [(d["piece"].buffer(BAND_MM), {"side": None, "y0": d["piece"].bounds[1],
                                                        "y1": d["piece"].bounds[3], "defects": [d]}) for d in defects]
        for zone, st in regions_of:
            def inside(pt, zone=zone):
                return zone.contains(_point(pt))
            for group, i, _node, _shape in shapes:
                node = group.children[i]
                segs, replaced = smooth_through(list(node.segments), inside)
                if replaced:
                    group.children[i] = node.model_copy(update={"segments": segs})
        left = [d for group, i, _n, _s in shapes
                for d in outline_defects(_polygon(group.children[i].segments))
                if any(zone.intersects(d["piece"]) for zone, _st in regions_of)]
        for zone, st in regions_of:
            ds = st["defects"]
            kinds = sorted({"bump" if d["kind"] == "spur" else "dent" for d in ds})
            deep = max(d["depth_mm"] for d in ds)
            still = [d for d in left if zone.intersects(d["piece"])]
            c = ds[0]["piece"].representative_point()
            edge = ("the %s edge of the traced shape \"%s\"" % (st["side"], primary[2].name)) if st["side"] else \
                ("the outline of the traced shape \"%s\"" % primary[2].name)
            span = max(st["y1"] - st["y0"], max(d["length_mm"] for d in ds))
            findings.append({"kind": "outline", "fixed": not still, **where(c.x, c.y), "what": (
                "%s wobbled over %.1f mm (%d %s, up to %.2f mm) — %s" % (
                    edge, span, len(ds), " and ".join(k + "s" for k in kinds), deep,
                    "redrawn as one smooth curve through it" if not still else
                    "the smooth curve did not mend it: %d remain" % len(still)))})
    return findings


def _point(pt):
    from shapely.geometry import Point
    return Point(pt)


def normalise_estimated(words: str) -> str:
    """[His final goal, C7: "the ℮ must be the real estimated sign, not 'e'"] an "e" after a quantity, where the
    estimated sign belongs ("8 ml e 0.27 fl oz"), made the sign itself."""
    return re.sub(r"(\d\s*(?:ml|mL|ML|g|G|oz|fl\.?\s*oz)\.?)\s+[eE](?=\s|$|/)", "\\1 " + ESTIMATED, str(words or ""))


# --------------------------------------------------------------------------------------- pass 2: on the drawn file

GUIDE_RGB = 0x00A0E3          # the guides' own ink (counter_display_files.GUIDE_HEX): their words are not his design's
CORE_UP, CORE_DOWN = 0.70, 0.15            # a Latin line's letters stand this many sizes above and below its baseline
CORE_UP_AR, CORE_DOWN_AR = 0.75, 0.30      # an Arabic line's
LEGIBLE_RATIO = 2.0           # type on a solid with less contrast than this does not read


def _arabic(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" or "\ufb50" <= ch <= "\ufeff" for ch in text)


def _luminance(rgb: tuple) -> float:
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: tuple, b: tuple) -> float:
    """The contrast ratio of two colours (0–1 RGB), lighter over darker."""
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _core(span: dict, direction: tuple, k: float) -> tuple:
    """A drawn line's letters' box in millimetres: along the line, its extent; across it, from a little under its
    baseline to its capitals' height (not the face's ascender and descender, which overlap at any leading)."""
    up = (direction[1], -direction[0])
    size = span["size"]
    hi, lo = (CORE_UP_AR, CORE_DOWN_AR) if _arabic(span["text"]) else (CORE_UP, CORE_DOWN)
    ox, oy = span["origin"]
    x0, y0, x1, y1 = span["bbox"]
    if abs(direction[0]) >= abs(direction[1]):
        ys = sorted((oy + up[1] * hi * size, oy - up[1] * lo * size))
        return (x0 * k, ys[0] * k, x1 * k, ys[1] * k)
    xs = sorted((ox + up[0] * hi * size, ox - up[0] * lo * size))
    return (xs[0] * k, y0 * k, xs[1] * k, y1 * k)


def inspect(pdf_path: str, regions: list, *, folds: list | None = None, page_offset=(0.0, 0.0), safe_mm: float = 0.0,
            pages=(0,), shapes: list | None = None, inkless: tuple = ("glue_tab",),
            inside_axis: float | None = None) -> list:
    """The drawn file read for what the eye would catch: ``[finding]`` with panel and millimetres. ``regions`` —
    ``[{"name", "x", "y", "w", "h"}]`` in the document's millimetres (a carton's panels, a container's zones);
    ``folds`` — ``[(x1, y1, x2, y2)]`` a carton's fold lines; ``page_offset`` — the page's top left in the same
    millimetres; ``safe_mm`` — the margin key elements stand inside; ``shapes`` — ``[(name, polygon, hex)]`` the traced
    solids drawn on the outside: a line of type set across one's edge (part on it, part off), or on it in an ink that
    does not read against it, is shown; ``inkless`` — the regions no design is printed on (the glue tab), whose marks
    are guides; ``inside_axis`` — where the second page is the sheet's inside, the vertical line it is mirrored about
    (its panels and folds read there mirrored). A guide's words (in the guides' own blue) are never his design's."""
    import fitz
    from shapely.geometry import box as _box
    k = 25.4 / 72.0
    ox, oy = page_offset
    findings = []
    doc = fitz.open(pdf_path)
    for pno in pages:
        if pno >= doc.page_count:
            continue
        page = doc[pno]
        board = "the inside" if pno == 1 else "the outside"
        page_regions, page_folds = regions, folds
        if pno == 1 and inside_axis is not None:
            page_regions = [dict(r, x=2 * inside_axis - r["x"] - r["w"]) for r in regions]
            page_folds = [(2 * inside_axis - f[0], f[1], 2 * inside_axis - f[2], f[3]) for f in folds or []]
        spans = []
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                for sp in ln["spans"]:
                    t = sp["text"].strip()
                    if not t or sp["color"] == GUIDE_RGB:
                        continue
                    x0, y0, x1, y1 = _core(sp, ln["dir"], k)
                    horizontal = abs(ln["dir"][0]) >= abs(ln["dir"][1])
                    rgb = ((sp["color"] >> 16) & 255, (sp["color"] >> 8) & 255, sp["color"] & 255)
                    spans.append({"text": t, "box": (x0 + ox, y0 + oy, x1 + ox, y1 + oy), "font": sp["font"],
                                  "base": sp["origin"][1] * k + oy if horizontal else sp["origin"][0] * k + ox,
                                  "h": horizontal, "size": sp["size"], "rgb": tuple(v / 255.0 for v in rgb)})

        def where(box):
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            r = _panel_of(cx, cy, page_regions)
            return r, {"panel": r["name"] if r else None, "board": board,
                       "x_mm": round(cx - (r["x"] if r else 0.0), 1), "y_mm": round(cy - (r["y"] if r else 0.0), 1)}
        on = [(s, *where(s["box"])) for s in spans]
        # guides and labels outside every panel, and the marks on a face no ink is printed on: not his design
        on = [(s, r, w) for s, r, w in on if r is not None and r["name"] not in inkless]
        for i, (a, ra, wa) in enumerate(on):
            for b, rb, _wb in on[i + 1:]:
                if ra is not rb:
                    continue
                ix = min(a["box"][2], b["box"][2]) - max(a["box"][0], b["box"][0])
                iy = min(a["box"][3], b["box"][3]) - max(a["box"][1], b["box"][1])
                if a["h"] == b["h"] and a["h"] and abs(a["base"] - b["base"]) < 0.05:
                    iy = ix if ix > OVERLAP_MM else 0.0     # one line's runs meet; they never overprint
                elif a["h"] == b["h"] and not a["h"] and abs(a["base"] - b["base"]) < 0.05:
                    iy = min(a["box"][3], b["box"][3]) - max(a["box"][1], b["box"][1])
                    ix = iy if iy > OVERLAP_MM else 0.0
                if ix > OVERLAP_MM and iy > OVERLAP_MM:
                    findings.append({"kind": "text crossing", "fixed": False,
                                     "what": "%r and %r touch" % (a["text"][:30], b["text"][:30]), **wa})
            x0, y0, x1, y1 = a["box"]
            for f in page_folds or []:
                vertical = abs(f[0] - f[2]) < 1e-6 and x0 + 0.3 < f[0] < x1 - 0.3 and y0 < max(f[1], f[3]) \
                    and y1 > min(f[1], f[3])
                horizontal = abs(f[1] - f[3]) < 1e-6 and y0 + 0.3 < f[1] < y1 - 0.3 and x0 < max(f[0], f[2]) \
                    and x1 > min(f[0], f[2])
                if vertical or horizontal:
                    findings.append({"kind": "cut text", "fixed": False,
                                     "what": "%r runs across a fold" % a["text"][:30], **wa})
                    break
            if pno == 0:
                line = _box(x0, y0, x1, y1)
                for shape_name, poly, ink in shapes or []:
                    share = line.intersection(poly).area / max(line.area, 1e-9)
                    if CROSS_LOW < share < CROSS_HIGH:
                        findings.append({"kind": "text crossing", "fixed": False, **wa,
                                         "what": "%r is set across the edge of the traced shape \"%s\" (%d%% of it "
                                                 "on the shape)" % (a["text"][:30], shape_name, round(100 * share))})
                    elif share >= CROSS_HIGH and ink:
                        h = ink.lstrip("#")
                        fill = tuple(int(h[n:n + 2], 16) / 255.0 for n in (0, 2, 4))
                        ratio = contrast(a["rgb"], fill)
                        if ratio < LEGIBLE_RATIO:
                            findings.append({"kind": "overlap", "fixed": False, **wa,
                                             "what": "%r is set on the traced shape \"%s\" in an ink that does not "
                                                     "read against it (contrast %.1f:1)" % (a["text"][:30], shape_name,
                                                                                            ratio)})
            margin = ra.get("safe_mm", safe_mm)                 # a region's own margin (a container's back panel)
            if margin and (x0 < ra["x"] + margin - 0.1 or x1 > ra["x"] + ra["w"] - margin + 0.1
                           or y0 < ra["y"] + margin - 0.1 or y1 > ra["y"] + ra["h"] - margin + 0.1):
                over = max(ra["x"] + margin - x0, x1 - (ra["x"] + ra["w"] - margin),
                           ra["y"] + margin - y0, y1 - (ra["y"] + ra["h"] - margin))
                findings.append({"kind": "in the safe margin", "fixed": False,
                                 "what": "%r stands %.1f mm inside the %g mm safe margin" % (a["text"][:30], over,
                                                                                           margin), **wa})
        line_text = {}
        for s, r, w in on:
            line_text.setdefault((r["name"], round(s["base"], 1)), []).append((s["text"], w))
        for (_panel, _base), items in line_text.items():
            joined = " ".join(t for t, _w in items)
            if WRONG_E.search(joined):
                findings.append({"kind": "wrong glyph", "fixed": False, **items[0][1],
                                 "what": "%r prints an 'e' where the estimated sign ℮ belongs" % joined[:40]})
        # a character its face has no glyph for is drawn as the face's empty box (glyph 0, or the replacement
        # character the file maps it to): never his letter
        for tr in page.get_texttrace():
            if not any((c[1] == 0 and c[0] > 32) or c[0] == 0xFFFD for c in tr["chars"]):
                continue
            words = "".join(chr(c[0]) for c in tr["chars"]).strip()
            bx = tr["bbox"]
            box = (bx[0] * k + ox, bx[1] * k + oy, bx[2] * k + ox, bx[3] * k + oy)
            r, w = where(box)
            if r is None or r["name"] in inkless:
                continue
            findings.append({"kind": "wrong glyph", "fixed": False, **w,
                             "what": "%r is set in %s, which has no glyph for one of its characters — it prints as an "
                                     "empty box" % (words[:30], tr["font"])})
    return findings


def carton_frame(coords) -> tuple:
    """``(regions, folds, inside_axis)`` of a carton, in its drawn page's millimetres (the page's margin round the
    bleed): each panel and flap by name, each fold line, and the line its inside is mirrored about."""
    from apps.ire.compose import _PAGE_MARGIN_MM
    vx = coords.bleed_polygon.bounds[0] - _PAGE_MARGIN_MM
    vy = coords.bleed_polygon.bounds[1] - _PAGE_MARGIN_MM
    regions = [{"name": p.name, "x": p.x - vx, "y": p.y - vy, "w": p.width, "h": p.height} for p in coords.panels]
    folds = [(f[0] - vx, f[1] - vy, f[2] - vx, f[3] - vy) for f in coords.fold_lines]
    bx0, _by0, bx1, _by1 = coords.bleed_polygon.bounds
    return regions, folds, (bx0 + bx1) / 2.0 - vx


def sheet_frame(doc, back_panel: dict | None = None) -> list:
    """A container's sheet as its regions: [his final goal, C7: "elements in the safe margin"; A: "The safe margin rule
    applies to containers too"] its back panel at print size where it is drawn (``back_panel`` — the back panel's own
    record: its origin, its size and its margin), read with that margin; then the sheet itself."""
    regions = []
    record = back_panel if back_panel is not None else (doc.metadata or {}).get("container_back_panel/1.0")
    if record and record.get("origin_mm") and record.get("panel_mm"):
        (x, y), (w, h) = record["origin_mm"], record["panel_mm"]
        regions.append({"name": "back panel", "x": float(x), "y": float(y), "w": float(w), "h": float(h),
                        "safe_mm": float(record.get("margin_mm") or 0.0)})
    return regions + [{"name": "sheet", "x": 0.0, "y": 0.0, "w": doc.page_w, "h": doc.page_h}]


def traced_solids(doc) -> list:
    """``[(name, polygon, ink hex)]`` the traced solids drawn on the outside (a part's solid shape, not its rim)."""
    from apps.ire.graph import Path
    out = []
    for node, _parent in doc.walk():
        if isinstance(node, Path) and node.fill is not None and str(node.name or "").startswith("shape-map-"):
            poly = _polygon(node.segments)
            color = getattr(node.fill, "color", None)
            if poly is not None:
                out.append((node.name, poly, color.to_hex() if color is not None else None))
    return out


def repair_said(doc, regions: list) -> tuple:
    """``(fixed, shown)`` — ``repair``, and where it cannot run, that it did not, shown. [His goal after the pitch page,
    2026-10-15, A (5): "logos and small text are always readable against what's behind them."] Then every mark and line
    of type on the product read against what is painted beneath it, its ink moved the least it must to read
    (``legibility.repair``) — each move said beside Approve; never a stop."""
    try:
        fixed, shown = repair(doc, regions), []
    except Exception as exc:  # noqa: BLE001 — the drawing goes on; that it was not repaired is shown
        fixed, shown = [], [{"kind": "check", "fixed": False,
                             "what": "the outline and sign repair could not run: %s" % exc}]
    try:
        from apps.ire import legibility
        fixed += legibility.repair(doc)
    except Exception as exc:  # noqa: BLE001 — the drawing goes on; that its contrast was not read is shown
        shown.append({"kind": "check", "fixed": False, "what": "the contrast repair could not run: %s" % exc})
    return fixed, shown


def inspect_said(path: str | None, doc, regions: list, *, folds: list | None = None, safe_mm: float = 0.0,
                 inside_axis: float | None = None) -> list:
    """``inspect`` of the file ``doc`` was drawn to; a file not drawn, or one that cannot be read, shown as such — a
    check that did not happen is never read as a clean one."""
    import os
    if not path or not os.path.exists(path):
        return [{"kind": "check", "fixed": False, "what": "no drawn file was there to read"}]
    try:
        found = inspect(path, regions, folds=folds, safe_mm=safe_mm, shapes=traced_solids(doc),
                        pages=(0, 1) if doc.inside is not None else (0,), inside_axis=inside_axis)
    except Exception as exc:  # noqa: BLE001 — that the drawn file was not read is shown
        return [{"kind": "check", "fixed": False, "what": "the drawn file could not be read: %s" % exc}]
    # [his goal after the pitch page, 2026-10-15, A (5)] every mark and line of type on the product that still reads
    # under its ratio against what is painted beneath it — a window, a lid's art, a mesh ground, the cap, the body, the
    # carton's ground, not only a traced solid — shown beside Approve, never a stop
    try:
        from apps.ire import legibility
        found += legibility.remaining(doc)
    except Exception as exc:  # noqa: BLE001 — that its contrast was not read is shown
        found.append({"kind": "check", "fixed": False, "what": "the contrast check could not run: %s" % exc})
    return found


def run(doc, draw, regions: list, *, folds: list | None = None, safe_mm: float = 0.0,
        inside_axis: float | None = None) -> tuple:
    """[His final goal, C7.] The two passes round one drawing: ``doc`` repaired, ``draw(doc)`` writing its file (its
    path returned), the file inspected. ``(the drawn path, the record)``."""
    fixed, shown = repair_said(doc, regions)
    path = draw(doc)
    shown += inspect_said(path, doc, regions, folds=folds, safe_mm=safe_mm, inside_axis=inside_axis)
    return path, record(fixed, shown)


def said(f: dict) -> str:
    """A finding in his words: what, and where — the panel, and its millimetres from the panel's left and top."""
    where = ""
    if f.get("panel") and "x_mm" in f:
        where = " — on the %s%s, %g mm from its left and %g mm from its top" % (
            str(f["panel"]).replace("_", " "), " (inside)" if f.get("board") == "the inside" else "",
            f["x_mm"], f["y_mm"])
    return "%s%s" % (f["what"], where)


def record(fixed: list, shown: list) -> dict:
    """What the check did and what it shows: ``{"schema", "fixed", "shown", "clean", "said"}`` — ``said`` his lines,
    each fixed one first ("Fixed: ...") and each shown one after ("Look at: ...")."""
    unresolved = [f for f in fixed if f.get('fixed', True) is False]
    shown = list(shown) + [f for f in unresolved if f not in shown]
    fixed = [f for f in fixed if f.get('fixed', True)]
    return {"schema": SCHEMA, "fixed": fixed, "shown": shown, "clean": not shown,
            "said": ["Fixed: " + said(f) for f in fixed] + ["Look at: " + said(f) for f in shown]}


# ------------------------------------------------------------------------------------------- checks it went on past

#: [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design. A failing check fixes the
#: drawing itself and re-checks; if it still fails, the design continues and the problem is shown beside Approve in
#: plain words."] the checks a design went on past while it was drawn, kept on its output as each is met —
#: ``[{"code", "what", "options"}]`` — and listed beside Approve with the drawing's own check (``with_shown``)
CHECKS_SHOWN_KEY = "checks_shown/1.0"


def keep_shown(spec: dict, code: str, what: str, options=()) -> None:
    """One check the design went on past, kept on ``spec`` once: its code, what it found in words, and what he can do."""
    rows = list(spec.get(CHECKS_SHOWN_KEY) or [])
    row = {"code": str(code).split(":", 1)[0].strip(), "what": what}
    if options:
        row["options"] = list(options)
    if row not in rows:
        rows.append(row)
    spec[CHECKS_SHOWN_KEY] = rows


def with_shown(check: dict | None, spec: dict) -> dict:
    """The drawing's own check (``record``) with every check the design went on past added to what it shows — each in
    its words, with what he can do; the drawing's own check as it was where it went past none."""
    check = check or record([], [])
    shown = list(check.get("shown") or [])
    seen = {f.get("what") for f in shown}
    for row in spec.get(CHECKS_SHOWN_KEY) or []:
        what = row["what"] + (" — you can " + ", or ".join(row["options"]) if row.get("options") else "")
        if what not in seen:
            seen.add(what)
            shown.append({"kind": "a check it went on past", "fixed": False, "what": what, "code": row["code"]})
    return record(list(check.get("fixed") or []), shown)
