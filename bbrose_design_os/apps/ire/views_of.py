"""[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (6): "SEE THE DESIGN ON THE PAGE: show each drawing (outside,
inside, lid, tray, back label, plates) large, with click-to-enlarge, zoom and pan".] Where each drawing stands on the
drawing's own pages — measured on the design graph as it is composed, kept on the design's record (``SCHEMA``), read by
the page's viewer (apps/pipeline/drawing_views.py). Every kind of design: a carton's panels and its label, a container's
product, open tray, lid inside, back label and its concept, an artwork's pieces; the inside and each finish plate are
pages of their own."""
from __future__ import annotations

SCHEMA = "drawing_views/1.0"

#: the named parts of a drawing shown on their own, in the words the page gives them (a name's start for the surfaces)
NAMED = {
    "Container": "The design",
    "OPEN TRAY": "The open tray",
    "LID INSIDE": "The inside of the lid",
    "Reference": "The concept it is drawn from",
    "panel-front": "The front",
    "panel-back": "The back",
    "panel-side_left": "The left side",
    "panel-side_right": "The right side",
    "label": "The back label",
}
#: a name that starts so is a surface of its own — its words its surface's
STARTS = (("TrueScaleSurface-", "The %s, at its true size"), ("Surface-", "The %s"),
          ("sheet-", "The %s piece"))
#: the least a part's box may be, in millimetres, to be shown on its own
LEAST_MM = 8.0


def _points(node):
    """Every point of a leaf's own geometry, in its own frame (mm)."""
    t = getattr(node, "type", "")
    if t == "path":
        pts = []
        for s in node.segments:
            for k in ("x", "x1", "x2"):
                v = getattr(s, k, None)
                if v is not None:
                    pts.append((v, getattr(s, "y" if k == "x" else ("y1" if k == "x1" else "y2"))))
        return pts
    if t == "text":
        from apps.ire.back_panel import MM_PER_PT
        size = float(node.size_pt) * MM_PER_PT
        width = max(size, 0.55 * size * len(node.text or ""))
        x0 = node.x - (width / 2.0 if getattr(node, "align", "left") == "center" else
                       width if getattr(node, "align", "left") == "right" else 0.0)
        return [(x0, node.y - size), (x0 + width, node.y + 0.25 * size)]
    if all(hasattr(node, k) for k in ("x", "y", "w", "h")):
        return [(node.x, node.y), (node.x + node.w, node.y + node.h)]
    return []


def bounds(node, turns=()):
    """``(x0, y0, x1, y1)`` in page millimetres of everything ``node`` draws — a turned group's turned — or None."""
    from apps.ire.graph import turned_point
    t = getattr(node, "type", "")
    if t == "group":
        inner = turns + ((node.turn,) if getattr(node, "turn", None) is not None else ())
        boxes = [b for b in (bounds(c, inner) for c in node.children) if b is not None]
        if not boxes:
            return None
        return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    pts = _points(node)
    if not pts:
        return None
    for turn in reversed(turns):
        pts = [turned_point(turn, x, y) for x, y in pts]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def views(doc) -> dict:
    """``{"schema", "sections": [{"key", "words", "page": 1, "box_mm"}]}`` — each named part of the drawing's first page
    that stands on its own (``NAMED``, ``STARTS``), measured where it is drawn (a turned group's turned); its inside is
    the second page."""
    out, seen = [], set()

    def visit(node, turns):
        name = getattr(node, "name", "") or ""
        words = NAMED.get(name)
        if words is None:
            for start, said in STARTS:
                if name.startswith(start):
                    words = said % name[len(start):].replace("_", " ").lower()
                    break
        if words is not None and words not in seen:
            box = bounds(node, turns)
            if box is not None and box[2] - box[0] >= LEAST_MM and box[3] - box[1] >= LEAST_MM:
                seen.add(words)
                out.append({"key": name, "words": words, "page": 1, "box_mm": [round(v, 2) for v in box]})
        if getattr(node, "type", "") == "group":
            inner = turns + ((node.turn,) if getattr(node, "turn", None) is not None else ())
            for child in node.children:
                visit(child, inner)

    visit(doc.root, ())
    return {"schema": SCHEMA, "sections": out}
