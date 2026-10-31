"""Emitted-geometry measurement for composed artwork (2A-6E-CORR-8 §2/§9).

The first fidelity gate validated declarations — element presence, motif
labels, declared zones — and a composition whose BAKED/POWDER was a fraction
of the selected scale passed with zero failures
(FIDELITY_VALIDATED_DECLARATIONS_NOT_GEOMETRY). This module measures the
ACTUAL emitted vector geometry, relative to the front panel, and is the
single source of truth for both the audit report and the geometry gate.

All numbers are fractions of the front panel (width/height/area) unless
suffixed _mm.

Text extents are MEASURED, not estimated: advance widths come from the
registered face (CORR-10) and cap heights from that same face's OS/2
sCapHeight (VQR-3). This header described the superseded 0.52 em/char
estimate for two arcs after the widths stopped using it, while
``_text_bbox_mm`` one screen below claimed real metrics for a height that was
still the 0.72 constant — each docstring wrong in the opposite direction.
Both now say what the code does.

``text_metrics`` will still hand a LAYOUT caller a constant when no face can
be asked. This module is a measurement surface feeding a gate, so where an
extent cannot be measured that must surface as unmeasured rather than as a
plausible number.
"""
from __future__ import annotations

_PT_TO_MM = 1.0 / 2.835

#: shape-aware ink-area factor per emitted particle kind (a bounding box
#: overcounts an ellipse ~27%, a star ~65%, a hairline tick ~80%) — the
#: honest approximation of printed decorative coverage.
_PARTICLE_AREA_FACTOR = {"circle": 0.785, "ellipse": 0.785, "star": 0.35,
                         "tick": 0.22, "cross": 0.18}


def _text_bbox_mm(run, font_name=None, cap_em=0.72):
    """(x, y_top, w, h) of a live text run in document mm — widths from the
    ACTUAL registered face's advances, heights from its real cap height.

    Rotation contract (matches the pdf_ai emitter): rotation −90 with a
    left anchor runs DOWNWARD from (x, y), glyph height extending to the
    right of the anchor."""
    from apps.ire.text_metrics import text_width_mm

    size_mm = run.size_pt * _PT_TO_MM
    cap_height = size_mm * cap_em
    # §BH65(c)8: the box is the box the run PRINTS — in its case, with its letter-spacing after every glyph but the
    # last. A run with neither measures exactly as before.
    text = run.text or " "
    if getattr(run, "text_case", None) == "upper":
        text = text.upper()
    length = text_width_mm(text, size_mm, font_name)
    tracking = getattr(run, "tracking_em", None) or 0.0
    if tracking:
        length += tracking * size_mm * max(len(text) - 1, 0)
    rotation = abs(float(getattr(run, "rotation_deg", 0.0) or 0.0)) % 180.0
    if 45.0 <= rotation <= 135.0:
        return (run.x, run.y, cap_height, length)
    x = run.x
    if run.align == "center":
        x -= length / 2.0
    elif run.align == "right":
        x -= length
    return (x, run.y - cap_height, length, cap_height)


def _stroke_pad_mm(path) -> float:
    """Half the stroke width in mm — how far the ink reaches beyond the
    geometry on each side. ``0.0`` for an unstroked path, so a fill-only
    path's box is byte-identical to what it was before stroke was consulted.

    A stroke is centred on its own path in PDF, which is what
    ``pdf_ai._set_stroke`` asks for: ``setLineWidth(stroke.width_mm * mm)``
    and nothing else. Half on each side, therefore.
    """
    stroke = getattr(path, "stroke", None)
    width = None if stroke is None else getattr(stroke, "width_mm", None)
    if not width or float(width) <= 0.0:
        return 0.0
    return float(width) / 2.0


def _seg_points(segments):
    """``[(points, closed)]`` — the subpaths of a segment list, each a list of
    ``(x, y, is_curve_point)`` in draw order.

    A segment list is not one shape. ``GLASS_INNER_WALL`` is ``M L M L``: two
    disjoint open lines, four butt caps between them, and treating it as a
    single four-point run would join two strokes the emitter never joined.
    """
    subpaths, current, origin = [], [], None

    def resume():
        # a ClosePath returns the pen to the subpath origin; a segment after
        # it with no MoveTo of its own starts from there
        if not current and origin is not None:
            current.append(origin)

    for seg in segments:
        op = getattr(seg, "op", None)
        if op == "M":
            if current:
                subpaths.append((current, False))
            origin = (float(seg.x), float(seg.y), False)
            current = [origin]
        elif op == "L":
            resume()
            current.append((float(seg.x), float(seg.y), False))
        elif op == "C":
            resume()
            current.extend((float(px), float(py), True) for px, py in (
                (seg.x1, seg.y1), (seg.x2, seg.y2), (seg.x, seg.y)))
        elif op == "Z":
            if current:
                subpaths.append((current, True))
            current = []
    if current:
        subpaths.append((current, False))
    return subpaths


def _path_bbox(path) -> tuple[float, float, float, float] | None:
    """``(x, y, w, h)`` of the INK the emitter lays down for ``path``, in
    document mm — stroke width included, because a stroke is ink.

    §Y4's finding, fixed under §Z4. A horizontal rule is two points with the
    same y: its GEOMETRY has zero height and its ink does not. Reading the
    coordinates alone reported a hairline as a line of no thickness, so every
    reader of this box — the non-blocking overlap evidence list, the artboard
    containment check — was blind to it. This is the measurement corrected,
    not a tolerance widened: an unstroked path's box does not move by one
    float, and the answer for a stroked one is what the producer inks.

    WHERE the pad goes is read off the producer, not assumed.
    ``pdf_ai`` never calls ``setLineCap`` or ``setLineJoin``, so ReportLab's
    canvas defaults stand: cap 0 (BUTT) and join 0 (miter). A butt cap stops
    dead at the endpoint, so an open segment's ink extends half a width
    PERPENDICULAR to its direction and not one micron along it. Padding all
    four sides uniformly would be simpler and would invent 0.04 mm of length
    at each end of every 0.08 mm rule on this sheet — a small number, and
    still ink that is not there. At a join the ink does reach half a width in
    both axes (a miter on a right angle reaches exactly that), and so does a
    curve (its extremum in one axis has a tangent perpendicular to it), so
    those points take the full pad.
    """
    pad = _stroke_pad_mm(path)
    # (x0, y0, x1, y1) CORNERS while accumulating — deliberately not the
    # (x, y, w, h) this returns, so a half-converted edit cannot type-check
    boxes = []

    def add(x0, y0, x1, y1):
        boxes.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))

    for points, closed in _seg_points(path.segments):
        if not points:
            continue
        for x, y, is_curve in points:
            # every point is at least itself; a curve point and the vertices
            # of a closed subpath (all of which are joins) take the full pad
            grow = pad if (is_curve or closed) else 0.0
            add(x - grow, y - grow, x + grow, y + grow)
        pairs = list(zip(points, points[1:]))
        if closed and len(points) > 1:
            pairs.append((points[-1], points[0]))
        for (ax, ay, a_curve), (bx, by, b_curve) in pairs:
            if a_curve or b_curve:
                add(ax - pad, ay - pad, bx + pad, by + pad)
                continue
            dx, dy = bx - ax, by - ay
            length = (dx * dx + dy * dy) ** 0.5
            if length <= 0.0:
                add(ax - pad, ay - pad, bx + pad, by + pad)
                continue
            px, py = pad * abs(dy) / length, pad * abs(dx) / length
            add(ax - px, ay - py, bx + px, by + py)
        if not closed and len(points) > 2:
            # interior vertices of an OPEN subpath are joins, not caps
            for x, y, _ in points[1:-1]:
                add(x - pad, y - pad, x + pad, y + pad)

    if not boxes:
        return None
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    return (x0, y0, x1 - x0, y1 - y0)


def _union(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return (x0, y0, x1 - x0, y1 - y0)


def measure_front_geometry(doc, front_bounds_mm: tuple, gx0: float = 0.0,
                           gy0: float = 0.0) -> dict:
    """The emitted-geometry report for the front panel.

    ``front_bounds_mm``: (x, y, w, h) of the front panel in DOCUMENT space
    (the caller applies the same gx/gy translation the composer used).
    """
    fx, fy, fw, fh = front_bounds_mm

    def rel_box(box):
        if box is None:
            return None
        return {"x": round((box[0] - fx) / fw, 3),
                "y": round((box[1] - fy) / fh, 3),
                "w": round(box[2] / fw, 3), "h": round(box[3] / fh, 3)}

    def on_front(box) -> bool:
        if box is None:
            return False
        cx = box[0] + box[2] / 2.0
        cy = box[1] + box[3] / 2.0
        return fx - 1 <= cx <= fx + fw + 1 and fy - 1 <= cy <= fy + fh + 1

    from apps.ire.text_metrics import (cap_height_em, metrics_provenance,
                                       resolve_metric_faces,
                                       resolve_role_metrics)

    faces = resolve_metric_faces(doc.metadata)
    bold_font, bold_path = faces.get("bold") or (None, None)
    cap_em = cap_height_em(bold_path)
    # per role, so a run is measured with the face it will be DRAWN with
    role_metrics = resolve_role_metrics(faces)

    text_boxes: dict = {}
    logo_box = None
    frame_boxes = []
    particles_front = []
    particles_all = []
    surface_counts: dict = {}
    ink_area_front = 0.0

    from apps.ire.brand_mark import is_mark as _is_mark

    def _walk(node, current_surface):
        name = str(getattr(node, "name", ""))
        if node.type == "group" and name.startswith(
                "powder_constellation-"):
            current_surface = name.split("-", 1)[1]
        if node.type == "text":
            face, face_cap, _ = role_metrics.get(
                node.font) or role_metrics.get("regular") or (None, cap_em,
                                                              False)
            text_boxes[name] = _text_bbox_mm(node, face, face_cap)
        elif (node.type == "image" or _is_mark(node)) and name.startswith("logo"):
            # [the owner's second answer of 2026-09-25: the mark drawn from its approved vector master states its
            # box as the raster did]
            nonlocal logo_box
            logo_box = (node.x, node.y, node.w, node.h)
        elif node.type == "path" and name.startswith("logo-frame"):
            frame_boxes.append(_path_bbox(node))
        elif node.type == "path" and name.startswith("particle-"):
            box = _path_bbox(node)
            particles_all.append(box)
            surface_counts[current_surface or "unknown"] = \
                surface_counts.get(current_surface or "unknown", 0) + 1
            if on_front(box) and box:
                particles_front.append(box)
                kind = name.rsplit("-", 1)[-1]
                factor = _PARTICLE_AREA_FACTOR.get(kind, 0.6)
                nonlocal ink_area_front
                ink_area_front += factor * box[2] * box[3]
        for child in getattr(node, "children", []) or []:
            _walk(child, current_surface)
    _walk(doc.root, None)

    name_boxes = [box for key, box in text_boxes.items()
                  if key.startswith("product-name")]
    name_union = _union(name_boxes)
    constellation_union = _union(particles_front)
    centroid = None
    if particles_front:
        centroid = {
            "x": round(sum(b[0] + b[2] / 2.0 for b in particles_front)
                       / len(particles_front) / fw
                       - fx / fw, 3),
            "y": round(sum(b[1] + b[3] / 2.0 for b in particles_front)
                       / len(particles_front) / fh
                       - fy / fh, 3),
        }
    # density quadrants (fraction of front particles per quadrant)
    quadrants = {"upper_left": 0, "upper_right": 0,
                 "lower_left": 0, "lower_right": 0}
    for box in particles_front:
        cx = (box[0] + box[2] / 2.0 - fx) / fw
        cy = (box[1] + box[3] / 2.0 - fy) / fh
        key = (("lower" if cy >= 0.5 else "upper") + "_"
               + ("right" if cx >= 0.5 else "left"))
        quadrants[key] += 1
    total_front = max(1, len(particles_front))
    particle_area = sum(b[2] * b[3] for b in particles_front)
    adjoining = surface_counts.get("side_right", 0)
    other_surfaces = {k: v for k, v in surface_counts.items()
                      if k not in ("front", "side_right")}

    logo_frame_union = _union([logo_box] + frame_boxes)
    return {
        "front_panel_mm": {"w": round(fw, 1), "h": round(fh, 1)},
        "logo": rel_box(logo_box),
        "logo_frame_group": rel_box(logo_frame_union),
        "name_lines": {key: rel_box(box) for key, box in text_boxes.items()
                       if key.startswith("product-name")},
        "product_name_group": rel_box(name_union),
        "tagline": rel_box(text_boxes.get("tagline")),
        "vertical_copy": rel_box(text_boxes.get("vertical-copy")),
        "constellation": {
            "front_count": len(particles_front),
            "total_count": len(particles_all),
            # the ADJOINING side only — flaps/opposite side counted apart
            "side_continuation_count": adjoining,
            "other_surface_counts": other_surfaces,
            "bounding": rel_box(constellation_union),
            "centroid": centroid,
            "quadrant_share": {key: round(value / total_front, 2)
                               for key, value in quadrants.items()},
            "bbox_area_fraction": round(particle_area / (fw * fh), 4),
            # shape-aware printed coverage — the contract's 15-20% band
            "coverage_fraction": round(ink_area_front / (fw * fh), 4),
        },
        "metric_font": bold_font,
        # ONE face name used to stand for every run's measurement. It named
        # the bold face while non-bold runs were measured with no face at
        # all, so a reader could not tell which extents were real. Each role
        # now reports the face that measured it and whether its cap height
        # was READ or substituted.
        "text_metrics_provenance": metrics_provenance(role_metrics),
    }


__all__ = ["measure_front_geometry"]
