"""§BH71 PART 1, THE OWNER'S GOAL OF 2026-09-28 — THE DRAWN SHAPE COMES FROM THE CONCEPT, NOT A TEMPLATE: "Take the drawn
outline and proportions from the chosen concept picture itself (read and traced to a clean vector). Templates are only
a fallback, and the design says when the fallback was used."

``container_outline_trace/1.0`` — the chosen concept picture's product outline, read from its own pixels and fitted to
a clean vector:

* a form drawn in PLAN (a compact): the lid's rim — the largest ellipse the picture's edges support. A well-supported
  ellipse is the lid seen at a tilt: its kind is ROUND when the concept's own reading names the lid round or the
  ellipse is itself a circle, OVAL when the reading names it oval (a shape no form draws yet); else the largest
  four-cornered outline, rectified, is a ROUNDED_RECT or a SQUARE by its aspect; else the outline is FREE_FORM — a
  shape the system does not know, said so and never forced into another;
* a form drawn in ELEVATION: the product's own axis, its half-width at every height about that axis, and the band where
  its closure narrows or steps — the outline mirrored about the axis and fitted, and the proportions read off it.

Pure: Pillow, numpy and OpenCV on the picture's bytes; no ORM, no provider, nothing written. Deterministic: the same
bytes and the same TRACE_PARAMS give the same record, which carries the bytes' sha256 so it is read once.

What it decides, and what it never does:
* the drawn OUTLINE's kind and proportions — a PROPOSAL a person confirms, like every proposal ("PROPOSED_FROM_THE
  PICTURE — never a confirmation", the dropper fitter's words of itself, container_profile_fit.py — removed with
  REFIT in the clean-up of 2026-10-04, its words in git history);
* never a size: one confirmed dimension scales it (the width), and the other is derived and proposed;
* never a material, a finish or a colour — §BH67(b)3 stands: nothing the picture shows becomes a finish unless the
  words specify it;
* the numbers that accept an ellipse as the rim — its perimeter supported at 0.85 or more by the picture's own edges,
  its median distance from them 1 % of its long axis or less — are the executor's, NEW with this module and recorded
  in every trace (TRACE_PARAMS); they decide only whether the trace or the template draws, and no ruled number moves.
"""
from __future__ import annotations

import hashlib
import math

SCHEMA = "container_outline_trace/1.0"

TRACE_PARAMS = {
    "version": "concept_outline_params/1.4",   # [his test day finding 3] 1.1: the row's own ground, parts on one
                                               # axis; 1.2: the product's colour down its axis; 1.3: [his answer of
                                               # 2026-10-05, W7] a squat product read as it stands, never laid down;
                                               # 1.4: [his review of 127, 130, 131 and 132, 2026-10-15, D (11)] the
                                               # shadow a product casts on a light ground left out (``CAST_SHADOW``)
    "scale_px": 768,                 # the long side the picture is read at
    "min_picture_px": 32,            # a picture whose short side is shorter than this is not read
    "blur_px": 5,                    # the L channel's Gaussian before the edges
    "canny": (20, 60),               # hysteresis thresholds on L
    "min_contour_px": 60,            # an edge run shorter than this fits no rim
    "min_axis_share": 0.15,          # the rim's long semi-axis, as a share of the frame's short side
    "support_px": 1.5,               # a rim sample within this distance of an edge counts as supported
    "rim_support_min": 0.85,         # the executor's, new: the rim's perimeter supported at least this much
    "rim_residual_max": 0.01,        # the executor's, new: median distance ≤ this share of the long semi-axis
    "circle_aspect_min": 0.97,       # an ellipse this near a circle IS one, whatever the words say
    "centre_window": 0.70,           # the rim's centre inside the middle share of the frame (a background disc is not)
    "quad_epsilons": (0.02, 0.03, 0.05),  # approxPolyDP's tolerances tried, as shares of the outline's perimeter
    "quad_hull_share": 0.90,         # the four corners must keep this share of the outline's own area
    # [his test blocker on design 124, 2026-10-11, (2): "Fix for every palette and compact"] the executor's, new: a lid
    # whose corners are too round for the tolerances above (the wiring check's compact, rounded 12 % of its short side)
    # cut at the coarser ``quad_round_epsilons`` into four sides, a line fitted to the middle ``quad_side_middle`` of
    # each, the lines met; the four corners never more than ``quad_round_area`` of the outline's own area
    "quad_round_epsilons": (0.06, 0.08, 0.10, 0.12),
    "quad_side_middle": 0.5,
    "quad_round_area": 1.12,
    "square_aspect": 0.97,           # a rectified quadrilateral this near 1:1 is a square
    "rim_samples": 360,              # points on a candidate rim where the edges' support is read
    "profile_rows": 96,              # ELEVATION: the half-width is sampled at this many heights
    "closure_narrow_ratio": 0.72,    # ELEVATION: the closure band narrows to this share of the body (concept_analysis)
    "step_share": 0.03,              # ELEVATION: a half-width jump of this share of the body width is a cap step
    "mask_bg_distance": 30.0,        # ELEVATION: Lab distance from the frame's border colour that is product
    "seed_fill_max": 0.85,           # ELEVATION: a cut keeping more of its seed box than this separated nothing
    "solidity_min": 0.80,            # ELEVATION: a standing product's outline is at least this convex
    "side_disagree_row": 0.25,       # ELEVATION: a height whose two sides differ by this share of the widest disagrees
    "side_disagree_max_share": 0.30, # ELEVATION: two sides disagreeing over more of the height are two products
                                     # (measured: 53 0 %, 51's body 2 %, 52's carton-and-dropper 35 %)
    "reflection_rise": 0.05,         # ELEVATION: a core widening again by this share below a waist is a reflection
    "side_colour_de": 12.0,          # ELEVATION: a height whose two halves' chroma (a*, b*) differ this much: two colours
    "side_colour_max_share": 0.40,   # ELEVATION: two colours over more of the height are two products
    "cuts_agree_ratio": 0.06,        # ELEVATION: two cuts whose proportions differ by more do not confirm each other
    "cuts_agree_closure": 0.04,      # ELEVATION: nor two whose closure lines differ by more of the height
    "closure_min_share": 0.04,       # ELEVATION: a closure line nearer the top than this is a corner, not a closure
    "closure_off_axis": 0.50,        # ELEVATION: a narrower top whose middle is off the axis by more than this share
                                     # of its own half-width is not the product's closure
    "detail_blur_share": 0.04,       # ELEVATION: the picture's edges blurred this share of its long side — its detail
    "min_seed_px": 8,                # ELEVATION: a seed narrower or shorter than this is not cut
    "cut_seed": 20260928,            # ELEVATION: the random state every cut starts from
    "detail_pad_share": 0.25,        # ELEVATION: the detail's box widened this share of its height, above and below
    "narrow_end_up": 0.75,           # ELEVATION: an end narrower than this share of the other is its closure's
    "closure_colour_rows": 6,        # ELEVATION: rows each side of a height whose colours are compared
    "closure_colour_reach": 0.60,    # ELEVATION: a closure as wide as its body ends in this upper share of the height
    "closure_colour_de": 12.0,       # ELEVATION: Lab distance across a height that is the closure meeting the body
    # [his test day finding 3, 2026-09-30, design 117: a tube on a studio sweep, its ground shading down the frame]
    "row_ground_share": 0.02,        # ELEVATION: each row's ground is read at its two ends, this share of the width each
    "part_min_share": 0.05,          # ELEVATION: a part this share of the largest or more, its middle across the
                                     # largest's width, is the same product's (a cap of another colour, its foot)
}

#: [His review of 127, 130, 131 and 132, 2026-10-15, D (11); the lead's look at 134's flacon: its cap traced a third too
#: narrow and stepped, its body a third too wide] the shadow a product casts on a LIGHT ground (its median L* at least
#: ``ground_l``) is never the product: what the cut kept in the ground's own colour (a*, b* each within ``chroma``),
#: darker than it by at most ``darker_l`` L*, is left out — only where what is left is one product (at least ``keeps``
#: of the cut) and what was left out lies to one side of it (``one_side`` of it) as a cast shadow does; a light product's
#: own pale parts, on both its sides, are kept. 134's shadow ran 0.4 of its body's width beside it and moved its axis
#: 67 px: every half-width was read about the wrong middle. The executor's, new.
CAST_SHADOW = {"version": 1, "ground_l": 62.0, "chroma": 4.0, "darker_l": 25.0, "keeps": 0.5, "one_side": 0.8}

TRACED_FROM_CONCEPT = "TRACED_FROM_CONCEPT"
TEMPLATE_FALLBACK = "TEMPLATE_FALLBACK"

ROUND, OVAL, SQUARE, ROUNDED_RECT, FREE_FORM, PROFILE = "round", "oval", "square", "rounded_rect", "free_form", "profile"

#: why the template draws instead, by name
TRACE_NO_CONCEPT_IMAGE = "TRACE_NO_CONCEPT_IMAGE"
TRACE_IMAGE_UNREADABLE = "TRACE_IMAGE_UNREADABLE"
TRACE_NO_RIM = "TRACE_NO_RIM"                       # no ellipse and no four-cornered outline the edges support
TRACE_MASK_UNRESOLVED = "TRACE_MASK_UNRESOLVED"     # ELEVATION: the product could not be told from the ground
TRACE_PRODUCT_CROPPED = "TRACE_PRODUCT_CROPPED"     # ELEVATION: the product runs off the frame
TRACE_NOT_TRACED_FORM = "TRACE_NOT_TRACED_FORM"     # a form this module does not read (the dropper keeps M3)
TRACE_IMAGE_CHANGED = "TRACE_IMAGE_CHANGED"         # the record names other bytes than the picture now
TRACE_NO_CLOSURE = "TRACE_NO_CLOSURE"               # ELEVATION: no line where the closure meets the body


# --- reading the picture ---------------------------------------------------------------------------------------------


def _read(image_bytes: bytes):
    """(the picture as BGR at TRACE_PARAMS["scale_px"], the scale from the original's pixels) or (None, 0.0)."""
    import cv2
    import numpy as np
    if not image_bytes:
        return None, 0.0
    img = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None, 0.0
    h, w = img.shape[:2]
    if min(h, w) < TRACE_PARAMS["min_picture_px"]:           # too small to hold an outline
        return None, 0.0
    s = float(TRACE_PARAMS["scale_px"]) / max(h, w)
    if s < 1.0:
        img = cv2.resize(img, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_AREA)
    else:
        s = 1.0
    return img, s


def _edges(img):
    """(the edge map, its distance transform) on the picture's lightness."""
    import cv2
    L = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[:, :, 0]
    b = int(TRACE_PARAMS["blur_px"])
    L = cv2.GaussianBlur(L, (b, b), 0)
    lo, hi = TRACE_PARAMS["canny"]
    edges = cv2.Canny(L, lo, hi)
    return edges, cv2.distanceTransform(255 - edges, cv2.DIST_L2, 3)


def _sha256(image_bytes) -> str | None:
    """The picture's bytes' sha256 — None when there are no bytes."""
    if not image_bytes:
        return None
    return hashlib.sha256(image_bytes).hexdigest()


def _ellipse_samples(cx, cy, w_axis, h_axis, angle_deg):
    """TRACE_PARAMS["rim_samples"] points on the ellipse cv2 describes by (centre, (width, height), angle), in the
    picture's pixels."""
    import numpy as np
    t = np.linspace(0.0, 2.0 * math.pi, int(TRACE_PARAMS["rim_samples"]), endpoint=False)
    a, b = w_axis / 2.0, h_axis / 2.0
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    x, y = a * np.cos(t), b * np.sin(t)
    return np.stack([cx + x * c - y * s, cy + x * s + y * c], axis=1)


def _rims(img, dist, edges):
    """Every ellipse the picture's edge runs fit, scored by how much of its perimeter the edges support, largest first."""
    import cv2
    import numpy as np
    h, w = dist.shape
    out = []
    cnts, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    for c in cnts:
        if len(c) < TRACE_PARAMS["min_contour_px"]:
            continue
        (cx, cy), (wa, ha), ang = cv2.fitEllipseDirect(c)      # five points or more: it never raises
        a, b = max(wa, ha) / 2.0, min(wa, ha) / 2.0
        if not (a >= TRACE_PARAMS["min_axis_share"] * min(h, w) and a <= 0.9 * max(h, w) and b >= 5.0):
            continue
        pts = _ellipse_samples(cx, cy, wa, ha, ang)
        inside = (pts[:, 0] >= 0) & (pts[:, 0] < w) & (pts[:, 1] >= 0) & (pts[:, 1] < h)
        if inside.mean() < 0.98:                 # a rim that leaves the frame is not the product's (a mirror, a vase)
            continue
        xs, ys = pts[inside, 0].astype(int), pts[inside, 1].astype(int)
        d = dist[ys, xs]
        out.append({"cx": float(cx), "cy": float(cy), "w_axis": float(wa), "h_axis": float(ha), "angle": float(ang),
                    "a": float(a), "b": float(b),
                    "support": float((d <= TRACE_PARAMS["support_px"]).mean()),
                    "residual": float(np.median(d)) / a})
    out.sort(key=lambda e: -e["a"])
    return out


def _rounded_quad(c):
    """[His test blocker on design 124, 2026-10-11, (2): "Fix for every palette and compact"] the four corners of an
    outline whose corners are rounded — too round for ``approxPolyDP`` to close four corners at ``quad_epsilons`` — where
    its straight sides meet: the outline cut into four sides at the four corners a coarser tolerance keeps
    (``quad_round_epsilons``), a line fitted to the straight middle of each side (``quad_side_middle`` of its length),
    each side's line met with the next's. None where it does not make four sides."""
    import cv2
    import numpy as np
    hull = cv2.convexHull(c)
    cand = None
    for eps in TRACE_PARAMS["quad_round_epsilons"]:
        got = cv2.approxPolyDP(hull, eps * cv2.arcLength(hull, True), True)
        if len(got) == 4:
            cand = got
            break
    if cand is None:
        return None
    v = cand.reshape(4, 2).astype(np.float64)
    pts = c.reshape(-1, 2).astype(np.float64)
    lo, hi = (1.0 - TRACE_PARAMS["quad_side_middle"]) / 2.0, (1.0 + TRACE_PARAMS["quad_side_middle"]) / 2.0
    lines = []
    for i in range(4):
        a, b = v[i], v[(i + 1) % 4]
        length = float(np.linalg.norm(b - a))
        if length < 10:
            return None
        u = (b - a) / length
        normal = np.array([-u[1], u[0]])
        along = (pts - a) @ u / length
        off = np.abs((pts - a) @ normal)
        middle = pts[(along > lo) & (along < hi) & (off < 0.1 * length)]
        if len(middle) < 5:
            return None
        vx, vy, x0, y0 = cv2.fitLine(middle.astype(np.float32), cv2.DIST_L2, 0, 0.01, 0.01).ravel()
        lines.append((np.array([x0, y0], np.float64), np.array([vx, vy], np.float64)))
    corners = []
    for i in range(4):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        m = np.array([d1, -d2]).T
        if abs(np.linalg.det(m)) < 1e-6:
            return None
        t = np.linalg.solve(m, p2 - p1)[0]
        corners.append(p1 + t * d1)
    quad = np.float32(corners).reshape(-1, 1, 2)
    hull_area, quad_area = cv2.contourArea(hull), cv2.contourArea(quad)
    if not hull_area <= quad_area <= TRACE_PARAMS["quad_round_area"] * hull_area:
        return None
    return quad.astype(np.int32)


def _quadrilateral(edges, dist):
    """The largest four-cornered outline the edges close — (corners in the picture's pixels, its rectified aspect, its
    corner share) — or None."""
    import cv2
    import numpy as np
    h, w = dist.shape
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    best = None
    for c in sorted(cnts, key=cv2.contourArea, reverse=True)[:5]:
        area = cv2.contourArea(c)
        if area < (TRACE_PARAMS["min_axis_share"] * min(h, w)) ** 2 * 4:
            break
        hull = cv2.convexHull(c)
        poly = None
        for eps in TRACE_PARAMS["quad_epsilons"]:              # the finest tolerance that closes four corners
            cand = cv2.approxPolyDP(hull, eps * cv2.arcLength(hull, True), True)
            if len(cand) == 4 and cv2.contourArea(cand) >= TRACE_PARAMS["quad_hull_share"] * cv2.contourArea(hull):
                poly = cand
                break
        rounded = poly is None
        if rounded:
            poly = _rounded_quad(c)                            # its corners rounded: where its straight sides meet
        if poly is None:
            continue
        pts = poly.reshape(4, 2).astype(np.float32)
        # order: top-left, top-right, bottom-right, bottom-left
        s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
        tl, br, tr, bl = pts[np.argmin(s)], pts[np.argmax(s)], pts[np.argmin(d)], pts[np.argmax(d)]
        top, bottom = np.linalg.norm(tr - tl), np.linalg.norm(br - bl)
        left, right = np.linalg.norm(bl - tl), np.linalg.norm(br - tr)
        wq, hq = (top + bottom) / 2.0, (left + right) / 2.0
        if min(wq, hq) < 10:
            continue
        # the corner radius: how far the hull's own outline stands in from the polygon's corners
        corner = float(np.mean([cv2.pointPolygonTest(hull, tuple(map(float, p)), True) for p in (tl, tr, br, bl)]))
        # [124's Gate 1, 2026-10-10: his palette stopped on "Object of type float32 is not JSON serializable"] every
        # measure a plain number, as the record that keeps it can hold — the sides are numpy's float32, and round()
        # keeps them so
        best = {"corners_px": [[round(float(v), 2) for v in p] for p in (tl, tr, br, bl)],
                "aspect": round(float(min(wq, hq) / max(wq, hq)), 4), "wide": bool(wq >= hq),
                "corner_share": round(float(abs(corner) / min(wq, hq)), 4), "rounded": rounded}
        break
    return best


def trace_plan(image_bytes: bytes, *, reading_shape: str | None = None, surface_box=None) -> dict:
    """The outline of a form drawn in PLAN — a compact's lid — from its concept picture. ``reading_shape`` is what the
    concept's own reading names the lid ("round", "oval", "square", …, or None); ``surface_box`` the reading's box of
    the product as fractions of the frame, a prior for where the rim lies (None: the middle of the frame)."""
    rec = {"schema_version": SCHEMA, "params": dict(TRACE_PARAMS), "view": "PLAN",
           "source_sha256": _sha256(image_bytes), "reading_shape": reading_shape}
    if not image_bytes:
        return {**rec, "state": TEMPLATE_FALLBACK, "reason": TRACE_NO_CONCEPT_IMAGE}
    img, s = _read(image_bytes)
    if img is None:
        return {**rec, "state": TEMPLATE_FALLBACK, "reason": TRACE_IMAGE_UNREADABLE}
    h, w = img.shape[:2]
    edges, dist = _edges(img)
    if surface_box:
        x0, y0, x1, y1 = surface_box
        win = (x0 * w, y0 * h, x1 * w, y1 * h)
    else:
        m = (1.0 - TRACE_PARAMS["centre_window"]) / 2.0
        win = (m * w, m * h, (1.0 - m) * w, (1.0 - m) * h)
    rims = [e for e in _rims(img, dist, edges) if win[0] <= e["cx"] <= win[2] and win[1] <= e["cy"] <= win[3]]
    held = [e for e in rims if e["support"] >= TRACE_PARAMS["rim_support_min"]
            and e["residual"] <= TRACE_PARAMS["rim_residual_max"]]
    rec["candidates"] = len(rims)
    if held:
        e = held[0]
        aspect = e["b"] / e["a"]
        named = ""                                  # the reading named no shape
        if reading_shape:
            named = reading_shape.lower()
        if aspect >= TRACE_PARAMS["circle_aspect_min"] or named in ("round", "circle", "circular", "disc"):
            kind, assumption = ROUND, (
                "the ellipse is itself a circle" if aspect >= TRACE_PARAMS["circle_aspect_min"] else
                "a circle seen tilted — the rim alone cannot tell a tilted circle from an oval seen square-on; the "
                "concept's reading names it %s" % named)
        elif named in ("oval", "ellipse", "elliptical"):
            kind, assumption = OVAL, "the concept's reading names the lid oval — an oval lid, seen at the picture's angle"
        else:
            kind, assumption = ROUND, ("a circle seen tilted — the concept's reading names no shape, and a compact's lid "
                                       "seen at an angle draws exactly this ellipse")
        long_axis_angle = e["angle"] if e["w_axis"] >= e["h_axis"] else e["angle"] + 90.0
        return {**rec, "state": TRACED_FROM_CONCEPT, "kind": kind, "assumption": assumption,
                "rim": {"centre_px": [round(e["cx"] / s, 2), round(e["cy"] / s, 2)],
                        "semi_axes_px": [round(e["a"] / s, 2), round(e["b"] / s, 2)],
                        "long_axis_angle_deg": round(long_axis_angle % 180.0, 2),
                        "cv_ellipse": [round(e["cx"] / s, 3), round(e["cy"] / s, 3), round(e["w_axis"] / s, 3),
                                       round(e["h_axis"] / s, 3), round(e["angle"], 3)],
                        "support": round(e["support"], 4), "residual": round(e["residual"], 5)},
                "tilt_deg": round(math.degrees(math.acos(min(1.0, aspect))), 2),
                "aspect": 1.0 if kind == ROUND else round(aspect, 4),
                "map": "weak-perspective affine: the rim's ellipse to a circle (exact for an orthographic view)"}
    quad = _quadrilateral(edges, dist)
    if quad:
        kind = SQUARE if quad["aspect"] >= TRACE_PARAMS["square_aspect"] else ROUNDED_RECT
        return {**rec, "state": TRACED_FROM_CONCEPT, "kind": kind, "quad": quad, "aspect": quad["aspect"],
                "corner_share": quad["corner_share"],
                "assumption": "a four-cornered outline, its aspect read from its sides (not rectified for perspective)"}
    near = rims[0] if rims else None
    return {**rec, "state": TEMPLATE_FALLBACK, "reason": TRACE_NO_RIM,
            "detail": ("no rim the edges support: the largest ellipse is %.0f %% supported, %.2f %% off" % (
                100 * near["support"], 100 * near["residual"]) if near else
                "no ellipse and no four-cornered outline among the picture's edges")}


#: [His test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2): "ONE ENGINE:
#: palettes and compacts run the same map-first path as the tube and carton".] A compact's map reads its lid as a carton's
#: map reads its front panel: square to the eye. The lid its plan trace finds (``trace_plan``) is cut from the concept and
#: stood square — four corners taken to a rectangle of the sides' own lengths (a perspective map), a round rim's ellipse
#: taken to the circle of its long axis (an affine map) — at the picture's own resolution: the LID PICTURE the map reads,
#: the flat redraw is made from and the drawing is scored against. Pure: the same bytes give the same picture.
LID_PICTURE_SCHEMA = "container_lid_picture/1.0"
LID_STRAIGHTENED = "STRAIGHTENED"
LID_NOT_STRAIGHTENED = "NOT_STRAIGHTENED"
#: a round lid's picture outside its rim — never the lid, said by its own colour
LID_OUTSIDE = (255, 255, 255)


def lid_picture(image_bytes: bytes, trace: dict | None = None) -> dict:
    """The concept's lid stood square: ``{"schema_version", "state", "shape": "rect" | "round", "size_px": [w, h],
    "from_px" (the four corners, or the rim's centre, axes and turn, in the concept's own pixels), "source_sha256",
    "lid_sha256", "png": its bytes}`` — or NOT_STRAIGHTENED with the trace's own reason where no lid traced, never a
    picture guessed. ``trace`` the plan trace already made of these bytes (``trace_plan``), else made here."""
    import cv2
    import numpy as np
    plan = trace if trace is not None else trace_plan(image_bytes)
    rec = {"schema_version": LID_PICTURE_SCHEMA, "source_sha256": _sha256(image_bytes)}
    if plan.get("state") != TRACED_FROM_CONCEPT:
        return {**rec, "state": LID_NOT_STRAIGHTENED,
                "reason": "its lid was not traced — %s" % (plan.get("detail") or plan.get("reason"))}
    img = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if plan.get("quad"):
        _small, s = _read(image_bytes)
        tl, tr, br, bl = (np.float32(p) / s for p in plan["quad"]["corners_px"])
        w = int(round((np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2.0))
        h = int(round((np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2.0))
        corners = np.float32([tl, tr, br, bl])
        warp = cv2.getPerspectiveTransform(corners, np.float32([[0, 0], [w, 0], [w, h], [0, h]]))
        lid = cv2.warpPerspective(img, warp, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        shape, origin = "rect", {"corners": [[round(float(v), 2) for v in p] for p in corners]}
    else:
        cx, cy, w_axis, h_axis, _angle = plan["rim"]["cv_ellipse"]
        a, b = max(w_axis, h_axis) / 2.0, min(w_axis, h_axis) / 2.0
        turn = math.radians(plan["rim"]["long_axis_angle_deg"])
        rot = np.array([[math.cos(turn), math.sin(turn)], [-math.sin(turn), math.cos(turn)]])
        stretch = rot.T @ np.diag([1.0, a / b]) @ rot             # the short axis drawn out to the long one's length
        r = int(round(a))
        shift = np.array([r, r]) - stretch @ np.array([cx, cy])
        lid = cv2.warpAffine(img, np.hstack([stretch, shift.reshape(2, 1)]), (2 * r, 2 * r), flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REPLICATE)
        outside = np.ones(lid.shape[:2], np.uint8)
        cv2.circle(outside, (r, r), r, 0, -1)
        lid[outside.astype(bool)] = LID_OUTSIDE
        w = h = 2 * r
        shape, origin = "round", {"centre": [round(float(cx), 2), round(float(cy), 2)],
                                  "axes": [round(float(a), 2), round(float(b), 2)],
                                  "long_axis_angle_deg": plan["rim"]["long_axis_angle_deg"]}
    ok, png = cv2.imencode(".png", lid)
    if not ok:
        return {**rec, "state": LID_NOT_STRAIGHTENED, "reason": "its straightened lid could not be written"}
    data = png.tobytes()
    return {**rec, "state": LID_STRAIGHTENED, "shape": shape, "size_px": [int(w), int(h)], "from_px": origin,
            "lid_sha256": _sha256(data), "png": data}


#: [His goal after the pitch page, 2026-10-15, A (3): "131 drawn landscape when the concept is portrait with a cream
#: border"] a lid's RIM, read on its picture stood square (``lid_picture``): along each side, the lines from its edge in
#: — each the median colour (CIE76, L* a* b*) of the middle ``span`` of the side — the rim a run of lines begun within
#: ``skip_px`` of the edge (its shadow or anti-aliasing), at least ``least_px`` deep, ended by the first line ``step_de``
#: or more from the line before it; every line of the run within ``line_de`` of the run's own median, its lines on
#: average at least ``line_even`` within ``line_de`` of their own medians. A run reaching ``reach_share`` of the side's
#: length is the art running to the edge, never a rim. A rim is the concept's only where all four sides read one, their
#: colours within ``sides_de`` of one another. The executor's, new.
LID_BORDER = {"version": "lid_border/1.0", "skip_px": 2, "reach_share": 0.08, "span": (0.2, 0.8), "line_de": 10.0,
              "line_even": 0.6, "step_de": 12.0, "sides_de": 15.0, "least_px": 2}


def _lab_lines(img):
    """(L*, a*, b*) of a BGR picture as one float array, L* 0..100."""
    import cv2
    import numpy as np
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    return np.stack([lab[..., 0] * 100.0 / 255.0, lab[..., 1] - 128.0, lab[..., 2] - 128.0], -1)


def _rim_run(lines: list):
    """``(the rim's depth in lines, its median colour)`` read along one side's ``lines`` (edge first), or None."""
    import numpy as np
    meds = [np.median(line, 0) for line in lines]
    even = [float(np.mean(np.linalg.norm(line - med, axis=1) < LID_BORDER["line_de"])) for line, med in zip(lines, meds)]
    for start in range(min(int(LID_BORDER["skip_px"]) + 1, len(lines))):
        d = start + 1
        while d < len(lines) and float(np.linalg.norm(meds[d] - meds[d - 1])) < LID_BORDER["step_de"]:
            d += 1
        if d >= len(lines):
            return None                                 # the art runs to the edge: no rim
        if d - start < int(LID_BORDER["least_px"]):
            continue
        run = np.array(meds[start:d])
        middle = np.median(run, 0)
        if float(np.max(np.linalg.norm(run - middle, axis=1))) < LID_BORDER["line_de"] \
                and float(np.mean(even[start:d])) >= LID_BORDER["line_even"]:
            return d, middle
    return None


def lid_border(png: bytes) -> dict | None:
    """[His goal after the pitch page, 2026-10-15, A (3)] The rim a concept shows round its lid's art (``LID_BORDER``),
    read on the lid stood square — ``{"top", "right", "bottom", "left"}`` each a share of the lid's own height or width,
    ``"hex"`` its colour, ``"version"`` — or None where the lid's art runs to its edge on any side, or its sides read
    rims of different colours. Pure: the same bytes give the same rim."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR) if png else None
    if img is None:
        return None
    lab = _lab_lines(img)
    h, w = lab.shape[:2]
    lo, hi = LID_BORDER["span"]
    xs, ys = slice(int(lo * w), max(int(hi * w), int(lo * w) + 1)), slice(int(lo * h), max(int(hi * h), int(lo * h) + 1))
    reach_y, reach_x = max(1, int(LID_BORDER["reach_share"] * h)), max(1, int(LID_BORDER["reach_share"] * w))
    sides = {"top": ([lab[d, xs] for d in range(reach_y)], h), "bottom": ([lab[h - 1 - d, xs] for d in range(reach_y)], h),
             "left": ([lab[ys, d] for d in range(reach_x)], w), "right": ([lab[ys, w - 1 - d] for d in range(reach_x)], w)}
    read = {}
    for side, (lines, length) in sides.items():
        run = _rim_run(lines)
        if run is None:
            return None
        read[side] = (run[0] / float(length), run[1])
    colours = np.array([ref for _share, ref in read.values()])
    middle = np.median(colours, 0)
    if float(np.max(np.linalg.norm(colours - middle, axis=1))) >= LID_BORDER["sides_de"]:
        return None
    px = np.uint8([[[np.clip(middle[0] * 2.55, 0, 255), np.clip(middle[1] + 128, 0, 255),
                     np.clip(middle[2] + 128, 0, 255)]]])
    b, g, r = cv2.cvtColor(px, cv2.COLOR_LAB2BGR)[0, 0]
    return {**{side: round(share, 5) for side, (share, _ref) in read.items()}, "hex": "#%02X%02X%02X" % (r, g, b),
            "version": LID_BORDER["version"]}


def _kernel(img):
    """The morphology kernel a picture's masks are closed and opened with — 1 % of its long side, odd."""
    import cv2
    h, w = img.shape[:2]
    k = max(3, int(0.01 * max(h, w)) | 1)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))


def _seed_boxes(img) -> list:
    """Where a standing product may be, in the order tried — ``[(how, (x, y, w, h))]``: the box of what differs from the
    frame's own border colour; the box of the picture's detail — its edges, blurred — because a product on a ground of
    its own colour still has edges and a plain ground has none (measured on task 51: a pink bottle on a pink wall, whose
    border-colour box held 0.4 % of the frame); the middle of the frame; and — [his test day finding 3, 2026-09-30,
    design 117: a tube standing on its hot-pink cap on a ground shading from peach to pink, whose border colour's box
    held only its hot-pink upper body, the cap a second part below and the soft-pink lower body near the ground; only
    the middle read the whole tube, no second cut agreed, and the template drew] — the box of every part on the
    largest part's axis that differs from its own row's ground, read at the row's two ends, because a studio sweep
    shades down the frame and one border colour takes the shading for a product."""
    import cv2
    import numpy as np
    h, w = img.shape[:2]
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    out = []
    border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    rough = (np.linalg.norm(lab - np.median(border, axis=0), axis=2) >= TRACE_PARAMS["mask_bg_distance"]).astype(np.uint8)
    rough = cv2.morphologyEx(rough, cv2.MORPH_OPEN, _kernel(img))
    n, _labels, stats, _c = cv2.connectedComponentsWithStats(rough, 8)
    if n > 1:
        i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        if stats[i, cv2.CC_STAT_AREA] >= 0.05 * h * w:
            out.append(("the box of what differs from the frame's border colour", tuple(int(v) for v in stats[i, :4])))
    lum = lab[:, :, 0]
    grad = np.hypot(cv2.Sobel(lum, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(lum, cv2.CV_32F, 0, 1, ksize=3))
    k = int(TRACE_PARAMS["detail_blur_share"] * max(h, w)) | 1
    blurred = cv2.GaussianBlur(grad, (k, k), 0)
    if float(blurred.max()) > 0.0:
        _t, detail = cv2.threshold((255.0 * blurred / float(blurred.max())).astype(np.uint8), 0, 255,
                                   cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        n, _labels, stats, _c = cv2.connectedComponentsWithStats(detail, 8)
        if n > 1:
            i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            x, y, bw, bh = (int(v) for v in stats[i, :4])
            # widened along the product's height: a closure of one smooth colour has little detail of its own (task
            # 51's cap block sat outside the detail's box, and the cut left it on the wall)
            pad = int(TRACE_PARAMS["detail_pad_share"] * bh)
            y0, y1 = max(0, y - pad), min(h, y + bh + pad)
            out.append(("the box of the picture's detail — its edges, blurred", (x, y0, bw, y1 - y0)))
    out.append(("the middle of the frame", (int(0.15 * w), int(0.05 * h), int(0.70 * w), int(0.90 * h))))
    k = max(2, int(TRACE_PARAMS["row_ground_share"] * w))
    ground = np.median(np.concatenate([lab[:, :k], lab[:, -k:]], axis=1), axis=1)[:, None, :]
    rough = (np.linalg.norm(lab - ground, axis=2) >= TRACE_PARAMS["mask_bg_distance"]).astype(np.uint8)
    rough = cv2.morphologyEx(rough, cv2.MORPH_OPEN, _kernel(img))
    n, _labels, stats, centres = cv2.connectedComponentsWithStats(rough, 8)
    if n > 1:
        order = sorted(range(1, n), key=lambda i: -int(stats[i, cv2.CC_STAT_AREA]))
        big = order[0]
        if stats[big, cv2.CC_STAT_AREA] >= 0.05 * h * w:
            x0, bw = int(stats[big, cv2.CC_STAT_LEFT]), int(stats[big, cv2.CC_STAT_WIDTH])
            parts = [i for i in order if x0 <= float(centres[i][0]) <= x0 + bw
                     and stats[i, cv2.CC_STAT_AREA] >= TRACE_PARAMS["part_min_share"] * stats[big, cv2.CC_STAT_AREA]]
            xs = [int(stats[i, 0]) for i in parts] + [int(stats[i, 0] + stats[i, 2]) for i in parts]
            ys = [int(stats[i, 1]) for i in parts] + [int(stats[i, 1] + stats[i, 3]) for i in parts]
            out.append(("the box of what differs from its own row's ground, every part on one axis",
                        (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))))
    return out


def _cut(img, box: tuple) -> tuple:
    """(the product's mask, why not) — GrabCut in ``box`` widened by 6 %, its result closed, opened, reduced to its
    largest part and its holes filled; ``(None, why)`` when the cut is not one standing product: too little or too
    much of the frame, its whole seed kept (nothing was separated), or an outline not solid enough to stand."""
    import cv2
    import numpy as np
    h, w = img.shape[:2]
    x, y, bw, bh = box
    gx, gy = int(0.06 * bw), int(0.06 * bh)
    rect = (max(1, x - gx), max(1, y - gy), min(w - 2, bw + 2 * gx), min(h - 2, bh + 2 * gy))
    rect = (rect[0], rect[1], min(rect[2], w - 1 - rect[0]), min(rect[3], h - 1 - rect[1]))
    if min(rect[2], rect[3]) < TRACE_PARAMS["min_seed_px"]:
        return None, "the seed is %d x %d px — too small to cut" % (rect[2], rect[3])
    gc = np.zeros((h, w), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    # GrabCut starts its colour models from OpenCV's one global random state, so a cut depended on what was cut before
    # it in the same process (measured: task 52 read in a different order was confirmed once and refused once); the
    # state is set before every cut, and the same bytes give the same record
    cv2.setRNGSeed(int(TRACE_PARAMS["cut_seed"]))
    cv2.grabCut(img, gc, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    mask = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
    kern = _kernel(img)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kern)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kern)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        return None, "the cut kept nothing"
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    mask = (labels == i).astype(np.uint8)
    flood = np.pad(mask, 1, constant_values=0) * 255
    ff = np.zeros((h + 4, w + 4), np.uint8)
    cv2.floodFill(flood, ff, (0, 0), 128)
    mask = (flood[1:-1, 1:-1] != 128).astype(np.uint8)          # holes filled
    mask = _without_cast_shadow(img, mask)
    share = float(mask.mean())
    if not 0.02 <= share <= 0.9:
        return None, "the product would be %.1f %% of the frame" % (100 * share)
    fill = float(mask.sum()) / max(1.0, float(rect[2] * rect[3]))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    solidity = float(mask.sum()) / max(1.0, cv2.contourArea(cv2.convexHull(max(cnts, key=cv2.contourArea))))
    if fill > TRACE_PARAMS["seed_fill_max"]:
        return None, "the cut kept %.0f %% of its seed — the product was not told from its ground" % (100 * fill)
    if solidity < TRACE_PARAMS["solidity_min"]:
        return None, "the outline is %.0f %% solid — not one standing product" % (100 * solidity)
    return mask, None


def _largest_filled(mask):
    """The mask's largest part, its holes filled."""
    import cv2
    import numpy as np
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        return mask
    part = (labels == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    h, w = part.shape
    flood = np.pad(part, 1, constant_values=0) * 255
    ff = np.zeros((h + 4, w + 4), np.uint8)
    cv2.floodFill(flood, ff, (0, 0), 128)
    return (flood[1:-1, 1:-1] != 128).astype(np.uint8)


def _without_cast_shadow(img, mask):
    """The cut ``mask`` without the shadow its product casts on a light ground (``CAST_SHADOW``) — the mask as cut where
    the ground is not light, nothing is in its colour, or what would be left out is not one shadow to one side."""
    import cv2
    import numpy as np
    p = CAST_SHADOW
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] *= 100.0 / 255.0
    ground = np.median(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]), axis=0)
    if float(ground[0]) < p["ground_l"]:
        return mask
    shade = (mask > 0) & (np.abs(lab[..., 1] - ground[1]) <= p["chroma"]) & (np.abs(lab[..., 2] - ground[2]) <= p["chroma"]) \
        & (lab[..., 0] < ground[0]) & (lab[..., 0] >= ground[0] - p["darker_l"])
    if not shade.any():
        return mask
    kept = cv2.morphologyEx((mask > 0).astype(np.uint8) * (~shade).astype(np.uint8), cv2.MORPH_OPEN, _kernel(img))
    kept = _largest_filled(kept)
    if float(kept.sum()) < p["keeps"] * float(mask.sum()):
        return mask
    cols = np.where(kept.any(axis=0))[0]
    _ys, xs = np.nonzero((mask > 0) & (kept == 0))
    if not len(xs) or not len(cols):
        return mask
    right = float(np.mean(xs > (cols.min() + cols.max()) / 2.0))
    if max(right, 1.0 - right) < p["one_side"]:
        return mask
    return kept


def _upright(mask, as_pictured: bool = False):
    """The turn that stands the mask upright — (its 2x3 matrix, the side of the square it is drawn in, the angle in
    degrees); (None, 0, 0.0) when the product already stands within a degree of it.

    [His answer of 2026-10-05, W7: "build it. Squat jars (creams, balms) are core products."] ``as_pictured``: the turn
    is the small one that squares the outline to the picture's frame — never more than 45° — as every product is
    pictured standing, straight-on (the concept's own pose: "standing upright, closed", "not leaning, tilted or
    turned"): up in the picture is up. Without it the outline's LONG side is stood vertical, as before — which turns a
    jar pictured wider than tall a full 90° and reads its lid and body as its two halves ("two colours"); the trace
    reads as pictured only where no two cuts agree the first way (``trace_elevation``, ``standing_pixels``)."""
    import cv2
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    (cx, cy), (rw, rh), ang = cv2.minAreaRect(max(cnts, key=cv2.contourArea))
    turn = ang if rh >= rw else ang - 90.0              # the angle that makes the rectangle's LONG side vertical
    while turn > 90.0:
        turn -= 180.0
    while turn <= -90.0:
        turn += 180.0
    if as_pictured:
        turn = ((turn + 45.0) % 90.0) - 45.0            # [W7] squared to the frame's nearest axis: a squat jar stands
    if abs(turn) < 1.0:
        return None, 0, 0.0
    h, w = mask.shape
    side = int(math.ceil(math.hypot(h, w)))
    m = cv2.getRotationMatrix2D((cx, cy), turn, 1.0)
    m[0, 2] += side / 2.0 - cx
    m[1, 2] += side / 2.0 - cy
    return m, side, float(turn)


def _rows(mask) -> tuple:
    """(top, bottom, the sampled rows, each row's leftmost and rightmost product pixel, which rows hold any) of an
    upright mask — TRACE_PARAMS["profile_rows"] heights from its top to its foot."""
    import numpy as np
    ys, _xs = np.nonzero(mask)
    top, bottom = int(ys.min()), int(ys.max())
    rows = np.linspace(top, bottom, int(TRACE_PARAMS["profile_rows"])).astype(int)
    lr = []
    for y in rows:
        xr = np.nonzero(mask[y])[0]
        lr.append((float(xr.min()), float(xr.max())) if xr.size else (float("nan"), float("nan")))
    lr = np.array(lr)
    return top, bottom, rows, lr, ~np.isnan(lr[:, 0])


def _core(mask) -> tuple:
    """The mask's SYMMETRIC CORE, read at TRACE_PARAMS["profile_rows"] heights — ``(top, bottom, rows, the raw edges,
    which rows hold any, the axis, the core half-widths)``: each height's half-width is the NEARER of its two edges
    from the axis, so what clings to one side of a product — its shadow on the wall, a prop's edge beside it — is left
    out and what it holds on both sides is kept. The axis is the median centre of the middle eight tenths of its
    height: a tip or a reflection at either end does not move it."""
    import numpy as np
    top, bottom, rows, lr, ok = _rows(mask)
    centres = (lr[:, 0] + lr[:, 1]) / 2.0
    middle = ok.copy()
    middle[: len(rows) // 10] = False
    middle[len(rows) - len(rows) // 10:] = False
    axis = float(np.median(centres[middle]))
    core = np.where(ok, np.clip(np.minimum(axis - lr[:, 0], lr[:, 1] - axis), 0.0, None), 0.0)
    return top, bottom, rows, lr, ok, axis, core


def _read_standing(img, mask, *, meets_foot: bool, pixels: bool = False, as_pictured: bool = False) -> dict:
    """The standing product the mask outlines, read about its own axis (``_core``): stood upright, its foot cut where
    it meets its reflection — in the lowest quarter, a waist its core widens from again — and stood NARROW END UP (a
    product stands closure up in its drawing, and a tube stands on its cap in its picture as often as on its end).
    ``meets_foot``: the mask reached the frame's foot, which only a reflection cut away may do. Returns its turn, its
    core half-width at every height as a share of its widest, its proportion, where its closure meets its body and how
    that was seen — or ``{"refused": why}``: a product whose two sides disagree over most of its height (two products,
    one standing against the other) is not read as one, and one that runs off the frame's foot is not read at all."""
    import cv2
    import numpy as np
    m, side, turned = _upright(mask, as_pictured)
    if m is not None:
        mask = cv2.warpAffine(mask, m, (side, side), flags=cv2.INTER_NEAREST)
        img = cv2.warpAffine(img, m, (side, side), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
    top, bottom, rows, lr, ok, axis, core = _core(mask)
    widest = float(np.percentile(core[ok], 98))
    waist = None
    for i in range(max(1, int(0.75 * len(rows))), len(rows) - 1):
        if core[i] <= core[i - 1] and core[i] <= core[i + 1] \
                and float(core[i + 1:].max()) > core[i] + TRACE_PARAMS["reflection_rise"] * widest:
            waist = i
            break
    if waist is not None:
        mask = mask.copy()
        mask[int(rows[waist]) + 1:, :] = 0              # below the waist: the product's reflection on the floor
        top, bottom, rows, lr, ok, axis, core = _core(mask)
    elif meets_foot:
        return {"refused": "the product runs off the frame at its foot"}
    end = max(1, len(rows) // 7)
    flipped = float(np.mean(core[len(rows) - end:])) < TRACE_PARAMS["narrow_end_up"] * float(np.mean(core[:end]))
    if flipped:
        mask, img = mask[::-1, ::-1].copy(), img[::-1, ::-1].copy()
        turned = turned + 180.0
        top, bottom, rows, lr, ok, axis, core = _core(mask)
    widest = float(np.percentile(core[ok], 98))
    sides = np.abs((axis - lr[:, 0]) - (lr[:, 1] - axis)) / max(1.0, widest)
    disagree = float(np.mean(sides[ok] > TRACE_PARAMS["side_disagree_row"]))
    if disagree > TRACE_PARAMS["side_disagree_max_share"]:
        return {"refused": "its two sides disagree over %.0f %% of its height — not read as one standing product"
                           % (100 * disagree)}
    # and a product's two halves are one material: a second product merged into the first (a carton behind a bottle,
    # task 52) makes a symmetric outline whose halves are two colours — read in their chroma (a*, b*), because light
    # falling from one side makes one half of any product lighter than the other (task 51's glass: 96 % of its
    # height differed in full Lab)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    halves = []
    for i, y in enumerate(rows):
        reach = int(core[i])
        if reach < 3:
            continue
        a = int(round(axis))
        left, right = lab[y, a - reach:a], lab[y, a:a + reach]
        halves.append(float(np.linalg.norm(np.median(left[:, 1:], axis=0) - np.median(right[:, 1:], axis=0))))
    two_colours = 0.0                                   # no height wide enough to hold two halves: none differ
    if halves:
        two_colours = float(np.mean(np.array(halves) > TRACE_PARAMS["side_colour_de"]))
    if two_colours > TRACE_PARAMS["side_colour_max_share"]:
        return {"refused": "its two halves are two colours over %.0f %% of its height — not read as one standing "
                           "product" % (100 * two_colours)}
    body_half = float(np.percentile(core[ok], 75))
    height_px = float(bottom - top)
    # the closure: the top rows narrower than the body (a neck, a pump, a dropper) over more than a corner's rounding;
    # else, for a closure as wide as its body (a cap block, a lid), the height in the upper part where its colour
    # changes most; else none read
    narrow = core < TRACE_PARAMS["closure_narrow_ratio"] * body_half
    band = 0
    while band < len(core) and (narrow[band] or not ok[band]):
        band += 1
    closure_share, closure_by = None, None
    if 0 < band < len(rows):
        # a closure stands on its body's axis: a narrower top whose middle lies off it is another product's top (task
        # 52: the carton behind the dropper rose above it, and read as the dropper's closure)
        centres = (lr[:band, 0] + lr[:band, 1]) / 2.0
        off = float(np.nanmedian(np.abs(centres - axis)))
        if off > TRACE_PARAMS["closure_off_axis"] * max(1.0, float(np.median(core[:band]))):
            return {"refused": "its narrower top stands %.0f px off its axis — not a closure on its own body; not "
                               "read as one standing product" % off}
    if 0 < band < len(rows) and float(rows[band] - top) / height_px >= TRACE_PARAMS["closure_min_share"]:
        closure_share, closure_by = round(float(rows[band] - top) / height_px, 4), "the outline narrows above its body"
    else:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        colour = []
        for y in rows:
            inside = np.abs(np.arange(mask.shape[1]) - axis) <= max(1.0, 0.6 * float(core[np.argmin(np.abs(rows - y))]))
            colour.append(np.median(lab[y][inside & (mask[y] > 0)], axis=0) if (inside & (mask[y] > 0)).any()
                          else [np.nan] * 3)
        colour = np.array(colour)
        k = int(TRACE_PARAMS["closure_colour_rows"])
        best, at = 0.0, None
        for i in range(k, int(TRACE_PARAMS["closure_colour_reach"] * len(rows))):
            step = float(np.linalg.norm(np.nanmean(colour[i - k:i], axis=0) - np.nanmean(colour[i:i + k], axis=0)))
            if step > best:
                best, at = step, i
        if at is not None and best >= TRACE_PARAMS["closure_colour_de"] \
                and float(rows[at] - top) / height_px >= TRACE_PARAMS["closure_min_share"]:
            closure_share = round(float(rows[at] - top) / height_px, 4)
            closure_by = "its colour changes by ΔE %.0f there" % best
    # [his test day finding 3, 2026-09-30, design 117: his concept's body is two colours, hot pink over soft pink, and
    # nothing read where one meets the other] the product's colour down its axis — at every sampled height, the median
    # of the middle of its width, the band a closure's colour is read in — as a hex; None where no pixel is there
    axis_colours = []
    for i, y in enumerate(rows):
        reach = max(1, int(0.6 * float(core[i])))
        lo, hi = max(0, int(round(axis)) - reach), int(round(axis)) + reach + 1
        seen = img[y, lo:hi][mask[y, lo:hi] > 0]
        axis_colours.append("#%02X%02X%02X" % tuple(int(v) for v in np.median(seen, axis=0)[::-1]) if len(seen)
                            else None)
    steps = [i for i in range(1, len(core)) if ok[i] and ok[i - 1]
             and abs(core[i] - core[i - 1]) > TRACE_PARAMS["step_share"] * 2 * body_half]
    profile = [[round(float((rows[i] - top) / height_px), 4), round(min(1.0, float(core[i] / widest)), 4)]
               for i in range(len(rows))]
    read = {"turned_deg": round(turned, 2), "stood_narrow_end_up": bool(flipped),
            "foot_cut_at_its_reflection": waist is not None, "sides_disagree": round(disagree, 4),
            "height_to_width": round(height_px / (2.0 * widest), 4),
            "closure_share": closure_share, "closure_by": closure_by,
            "steps_at": [profile[i][0] for i in steps][:6], "profile": profile, "axis_colours": axis_colours}
    if as_pictured:
        read["stood_as_pictured"] = True                # [W7] read as the picture stands it, never laid on its side
    if pixels:
        # [his answer after test day finding 3, 2026-09-30: the design read from the picture] the pixels this read was
        # made on, stood upright as the PICTURE stands the product — turned about its axis, never end over end
        read["_pixels"] = ((img[::-1, ::-1].copy(), mask[::-1, ::-1].copy()) if flipped else (img, mask))
    return read


def trace_elevation(image_bytes: bytes) -> dict:
    """The outline of a form drawn in ELEVATION — a bottle, a jar, a tube, a lipstick, a mascara or a pencil standing —
    from its concept picture: the product cut from its ground from each seed of ``_seed_boxes``, stood upright, its
    half-width read at every height about its own axis as a share of its widest, and the line where its closure meets
    its body. TWO CUTS MUST AGREE — their proportion within TRACE_PARAMS["cuts_agree_ratio"] and their closure line
    within ["cuts_agree_closure"] — because one cut can be wrong and look right: measured on his task 51, the picture's
    detail cut the pink body and left its cap on the pink wall (3.07 : 1, its "closure" 7 % down), and on task 52 the
    border colour's cut took the carton behind the dropper as the dropper's own (1.79 : 1). A read no second cut
    confirms falls back to the template, every cut's numbers said."""
    rec = {"schema_version": SCHEMA, "params": dict(TRACE_PARAMS, cast_shadow=dict(CAST_SHADOW)), "view": "ELEVATION",
           "source_sha256": _sha256(image_bytes)}
    if not image_bytes:
        return {**rec, "state": TEMPLATE_FALLBACK, "reason": TRACE_NO_CONCEPT_IMAGE}
    img, _s = _read(image_bytes)
    if img is None:
        return {**rec, "state": TEMPLATE_FALLBACK, "reason": TRACE_IMAGE_UNREADABLE}
    import numpy as np
    tried, cropped, reads, masks = [], 0, [], []
    for how, box in _seed_boxes(img):
        mask, why = _cut(img, box)
        if mask is None:
            tried.append("%s: %s" % (how, why))
            continue
        edge = np.concatenate([mask[0], mask[:, 0], mask[:, -1]])
        if edge.mean() > 0.01:                          # more than a touch of the frame: the product runs off it
            cropped += 1
            tried.append("%s: the product runs off the frame" % how)
            continue
        masks.append((how, mask))
    # [his answer of 2026-10-05, W7: "build it. Squat jars (creams, balms) are core products."] read the way it always
    # was; only where no two cuts agree, read again as the picture stands the product (a squat jar, never laid down)
    first = None
    for as_pictured in (False, True):
        reads = []
        for how, mask in masks:
            # the frame's foot only a reflection may reach — cut at the product's own foot, or refused there
            read = _read_standing(img, mask, meets_foot=bool(mask[-1].mean() > 0.01), as_pictured=as_pictured)
            if "refused" in read:
                if not as_pictured:
                    tried.append("%s: %s" % (how, read["refused"]))
                continue
            reads.append((how, read))
        agreed = _first_agreeing(reads)
        if agreed is not None:
            break
        if first is None:
            first = reads
    else:
        reads = first
    for i, (how, read) in enumerate(reads):
        agree = [other for other, second in reads[i + 1:] if _cuts_agree(read, second)]
        if agree:
            return {**rec, "state": TRACED_FROM_CONCEPT, "kind": PROFILE, "mask_method": "GRABCUT, seeded with " + how,
                    "confirmed_by": ["GRABCUT, seeded with " + other for other in agree], "seeds_not_taken": tried,
                    **read, "assumption": "heights foreshorten with the camera's pitch, so the ratios are the picture's "
                                          "(container_profile_fit's own caveat)"}
    said = tried + ["%s: read %.2f : 1, its closure %s, and no second cut agrees" % (
        how, read["height_to_width"], "at %.0f %%" % (100 * read["closure_share"]) if read["closure_share"] is not None
        else "not seen") for how, read in reads]
    reason = TRACE_MASK_UNRESOLVED
    if tried and cropped == len(tried) and not reads:
        reason = TRACE_PRODUCT_CROPPED
    return {**rec, "state": TEMPLATE_FALLBACK, "reason": reason, "detail": "; ".join(said)}


def standing_pixels(image_bytes: bytes):
    """[His answer after test day finding 3, 2026-09-30 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 23d4375): the chosen
    design is read from its picture, "the same strategy we used with" the shape.] The product's own pixels as the
    elevation trace confirms it — ``(picture, mask, read)``: the picture read at TRACE_PARAMS["scale_px"], the product
    stood upright about its own axis as the picture stands it (turned, never end over end), its foot cut at its
    reflection, and the mask of the first cut a second cut agrees with, as ``trace_elevation`` takes it; None where no
    two cuts agree — the trace's own refusal."""
    if not image_bytes:
        return None
    img, _s = _read(image_bytes)
    if img is None:
        return None
    import numpy as np
    masks = []
    for _how, box in _seed_boxes(img):
        mask, _why = _cut(img, box)
        if mask is None:
            continue
        edge = np.concatenate([mask[0], mask[:, 0], mask[:, -1]])
        if edge.mean() > 0.01:
            continue
        masks.append(mask)
    # [his answer of 2026-10-05, W7] as trace_elevation reads it: the way it always was, then as the picture stands it
    for as_pictured in (False, True):
        reads = []
        for mask in masks:
            read = _read_standing(img, mask, meets_foot=bool(mask[-1].mean() > 0.01), pixels=True,
                                  as_pictured=as_pictured)
            if "refused" not in read:
                reads.append(read)
        for i, read in enumerate(reads):
            if any(_cuts_agree(read, second) for second in reads[i + 1:]):
                picture, mask = read.pop("_pixels")
                return picture, mask, read
    return None


def _first_agreeing(reads: list):
    """The first ``(how, read)`` a later read of ``reads`` agrees with (``_cuts_agree``), or None."""
    for i, (how, read) in enumerate(reads):
        if any(_cuts_agree(read, second) for _o, second in reads[i + 1:]):
            return how, read
    return None


def _cuts_agree(a: dict, b: dict) -> bool:
    """Two reads of one product agree: their proportions within TRACE_PARAMS["cuts_agree_ratio"] of each other, and
    their closure lines within ["cuts_agree_closure"] of the height (or neither seen)."""
    ratio = a["height_to_width"] / b["height_to_width"]
    if abs(ratio - 1.0) > TRACE_PARAMS["cuts_agree_ratio"]:
        return False
    if a["closure_share"] is None or b["closure_share"] is None:
        return a["closure_share"] is None and b["closure_share"] is None
    return abs(a["closure_share"] - b["closure_share"]) <= TRACE_PARAMS["cuts_agree_closure"]


# --- the trace as the drawing's geometry --------------------------------------------------------------------------------

#: a compact's variants by the traced kind — the form's own vocabulary (archetypes.VOCABULARY["compact"])
PLAN_VARIANT = {ROUND: "round", SQUARE: "square", ROUNDED_RECT: "rounded_rect"}


def plan_height_ratio(trace: dict) -> float:
    """A lid's length over its width in plan, as its concept shows it — ``trace_plan``'s own aspect, turned as the
    picture turns it. A round or a square lid is as long as it is wide; a rounded rectangle its sides' short over long,
    turned by which is wider; [His goal after the pitch page, 2026-10-15, A (3): "SHAPES AND PROPORTIONS come from the
    concept"] an oval its rim's short axis over its long, turned by where its long axis lies (it was proposed a circle)."""
    if trace.get("kind") in (ROUND, SQUARE):               # a square is one by its own reading (``square_aspect``)
        return 1.0
    aspect = float(trace["aspect"])
    wide = True
    if trace.get("quad"):
        wide = bool(trace["quad"]["wide"])
    elif trace.get("rim"):
        angle = float(trace["rim"]["long_axis_angle_deg"]) % 180.0
        wide = angle <= 45.0 or angle >= 135.0           # the long axis nearer the frame's across than its down
    if not wide:
        return 1.0 / aspect
    return aspect


def proposal(trace: dict | None, archetype: str, *, width_mm: float | None = None,
             traced_variants: dict | None = None) -> dict:
    """What the trace proposes for the shape step: ``{"variant", "height_mm"}`` for a form drawn in plan (the height
    DERIVED from the confirmed or proposed width by the picture's aspect), ``{"height_mm"}`` for one drawn in elevation;
    ``{}`` when the trace draws nothing — or when its kind is one no variant of the form draws (an oval compact, a
    free-form lid): that shape is said, never forced into a variant (``unknown_shape``). [§BH71 PART 3:
    ``traced_variants`` — the form's own declared names for what a trace of its lid is (``archetypes``); the
    compact's own when not given.]"""
    if not trace or trace.get("state") != TRACED_FROM_CONCEPT:
        return {}
    if trace.get("view") == "PLAN":
        names = PLAN_VARIANT
        if traced_variants is not None:
            names = traced_variants
        variant = names.get(trace.get("kind"))
        if variant is None:
            return {}
        out = {"variant": variant}
        if width_mm:
            out["height_mm"] = round(width_mm * plan_height_ratio(trace), 1)
        return out
    if width_mm and trace.get("height_to_width"):
        # [his goal after the pitch page, B (10): the lotion tube, 139, proposed 35 x 63.4 and drawn 55 x 63.4 — squat,
        # its concept tall] the height the picture's proportion gives the width the form is DRAWN at (a tube's flat
        # end), as ``concept_proportion_size`` gives it
        from apps.pipeline.targets.container.silhouettes import drawn_width_mm
        from apps.pipeline.targets.ui import form_ranges
        height = drawn_width_mm(archetype, float(width_mm)) * float(trace["height_to_width"])
        # … never past the sizes the form may measure — the shape step's own limits (``form_ranges``), which the page's
        # slider and the server's check read alike
        low, high = form_ranges(archetype)["height_mm"]
        return {"height_mm": round(min(float(high), max(float(low), height)), 1)}
    return {}


def unknown_shape(trace: dict | None, known: dict | None = None) -> dict | None:
    """A traced shape no variant of the form draws — ``{"kind", "words"}`` — or None. PART 3 of his goal: "When a concept
    shows a shape the system doesn't know, it says so and offers to learn it. It never squeezes a product into the
    wrong shape.\""""
    if not trace or trace.get("state") != TRACED_FROM_CONCEPT or trace.get("view") != "PLAN":
        return None
    names = PLAN_VARIANT                     # [§BH71 PART 3: the form's own names, its learned lids among them]
    if known is not None:
        names = known
    if trace.get("kind") in names:
        return None
    words = {OVAL: "an oval lid", FREE_FORM: "a lid of its own outline"}.get(trace.get("kind"), str(trace.get("kind")))
    return {"kind": trace.get("kind"), "words": words}


def outline_for(trace: dict | None, *, archetype: str, variant: str | None, image_sha256: str | None,
                traced_variants: dict | None = None) -> tuple:
    """(the outline the drawing takes — for ``ContainerProfile.outline`` — or None, and the source record
    ``container_outline_source/1.0``: TRACED_FROM_CONCEPT with the trace's own numbers, or TEMPLATE_FALLBACK with the
    reason by name and which template drew)."""
    template = _template_words(archetype, variant)
    if trace is None:
        return None, {"source": TEMPLATE_FALLBACK, "reason": TRACE_NO_CONCEPT_IMAGE, "template": template}
    if image_sha256 is not None and trace.get("source_sha256") != image_sha256:
        return None, {"source": TEMPLATE_FALLBACK, "reason": TRACE_IMAGE_CHANGED, "template": template,
                      "detail": "the trace names other bytes than the approved concept picture"}
    if trace.get("state") != TRACED_FROM_CONCEPT:
        return None, {"source": TEMPLATE_FALLBACK, "reason": trace.get("reason"), "template": template,
                      **({"detail": trace["detail"]} if trace.get("detail") else {})}
    if trace.get("view") == "PLAN":
        names = PLAN_VARIANT                        # [§BH71 PART 3: the form's own names, when it declares them]
        if traced_variants is not None:
            names = traced_variants
        want = names.get(trace.get("kind"))
        if want is None:
            return None, {"source": TEMPLATE_FALLBACK, "reason": "TRACE_SHAPE_UNKNOWN", "template": template,
                          "detail": "the concept's lid is %s — a shape no variant of the %s draws yet"
                                    % (unknown_shape(trace)["words"], archetype)}
        if variant != want:
            return None, {"source": TEMPLATE_FALLBACK, "reason": "TRACE_NOT_ACCEPTED_AT_CONFIRMATION",
                          "template": template,
                          "detail": "the concept's lid is %s; the shape confirmed is %s — the confirmation governs, and "
                                    "the traced lid is drawn once the shape is confirmed as the picture shows it"
                                    % (_shape_word(want), _shape_word(variant))}
        outline = {"kind": trace["kind"], "corner_share": trace.get("corner_share"),
                   "source_sha256": trace.get("source_sha256")}
        rim = trace.get("rim") or {}
        return outline, {"source": TRACED_FROM_CONCEPT, "kind": trace["kind"], "template": None,
                         "support": rim.get("support"), "residual": rim.get("residual"),
                         "tilt_deg": trace.get("tilt_deg"), "assumption": trace.get("assumption"),
                         "source_sha256": trace.get("source_sha256")}
    if trace.get("closure_share") is None:
        return None, {"source": TEMPLATE_FALLBACK, "reason": TRACE_NO_CLOSURE, "template": template,
                      "detail": "the picture shows no line where the closure meets the body — its outline does "
                                "not narrow there and its colour does not change"}
    # [his test day finding 3, 2026-09-30: the trace stands every picture narrow end up, and says when it turned one —
    # design 117's tube stood on its cap; the drawing never heard it, and drew the tube on its crimp]
    stands = trace.get("stood_narrow_end_up") is True
    outline = {"kind": PROFILE, "profile": trace.get("profile"), "closure_share": trace.get("closure_share"),
               "height_to_width": trace.get("height_to_width"), "source_sha256": trace.get("source_sha256"),
               "stands_on_closure": stands,
               # [his review of 127, 130, 131 and 132, 2026-10-15, C (3)] its foot cut at its reflection: the round its
               # last rows turn along is drawn continued (``silhouettes.END_ROUND``)
               "foot_cut_at_its_reflection": trace.get("foot_cut_at_its_reflection") is True}
    return outline, {"source": TRACED_FROM_CONCEPT, "kind": PROFILE, "template": None, "stands_on_closure": stands,
                     "height_to_width": trace.get("height_to_width"), "closure_share": trace.get("closure_share"),
                     "closure_by": trace.get("closure_by"),
                     "sides_disagree": trace.get("sides_disagree"), "mask_method": trace.get("mask_method"),
                     "assumption": trace.get("assumption"), "source_sha256": trace.get("source_sha256")}


def not_traced(archetype: str, variant: str | None, *, detail: str) -> dict:
    """The source record of a drawing no trace reaches — TEMPLATE_FALLBACK, TRACE_NOT_TRACED_FORM, which template
    drew and why in words — so the design says the fallback was used on every form, not only where a trace ran."""
    return {"source": TEMPLATE_FALLBACK, "reason": TRACE_NOT_TRACED_FORM,
            "template": _template_words(archetype, variant), "detail": detail}


def words(source: dict | None) -> str:
    """The drawn outline's source in words — the review board's row."""
    if not source:
        return "not recorded"
    if source.get("source") == TRACED_FROM_CONCEPT and source.get("kind") == PROFILE:
        said = ("traced from the concept — its outline read about its own axis, %.2f times as tall as it is wide"
                % float(source["height_to_width"]))
        if source.get("stands_on_closure") is True:
            said += ", standing on its closure as the concept stands it"
        return said
    if source.get("source") == TRACED_FROM_CONCEPT:
        said = "traced from the concept — a %s lid" % _shape_word(source.get("kind"))
        if source.get("support") is not None:          # a rim's fit; a four-cornered outline has none
            said += ", the rim %.0f %% supported, %.2f %% off, seen %.0f° tilted" % (
                100 * float(source["support"]), 100 * float(source["residual"]), float(source["tilt_deg"]))
        return said
    said = "%s — the fallback: %s" % (source["template"], _reason_words(source.get("reason")))
    if source.get("detail"):
        said += " (%s)" % source["detail"]
    return said


def _template_words(archetype: str, variant: str | None) -> str:
    """Which template draws, in words — "the compact template, rounded rectangle"."""
    said = "the %s template" % archetype
    if variant:
        said += ", %s" % _shape_word(variant)
    return said


def _shape_word(kind) -> str:
    """A shape in words; "none" when none is named."""
    if kind is None:
        return "none"
    if kind in _SHAPE_WORDS:
        return _SHAPE_WORDS[kind]
    return str(kind)


def _reason_words(reason) -> str:
    """Why the template drew, in words."""
    if reason in _REASON_WORDS:
        return _REASON_WORDS[reason]
    return str(reason).lower().replace("_", " ")


#: a lid's shape in words
_SHAPE_WORDS = {ROUND: "round", SQUARE: "square", ROUNDED_RECT: "rounded rectangle", OVAL: "oval",
                FREE_FORM: "free-form"}

_REASON_WORDS = {
    TRACE_NO_CONCEPT_IMAGE: "there is no approved concept picture to trace",
    TRACE_IMAGE_UNREADABLE: "the concept picture could not be read",
    TRACE_NO_RIM: "the picture's edges support no outline of the lid",
    TRACE_MASK_UNRESOLVED: "the product could not be told from its ground",
    TRACE_PRODUCT_CROPPED: "the product runs off the picture's edge",
    TRACE_NOT_TRACED_FORM: "this form keeps its own drawing",
    TRACE_IMAGE_CHANGED: "the trace was read from another picture",
    TRACE_NO_CLOSURE: "the picture shows no line where the closure meets the body",
    "TRACE_SHAPE_UNKNOWN": "the concept shows a shape this form does not draw yet",
    "TRACE_NOT_ACCEPTED_AT_CONFIRMATION": "the shape confirmed is not the shape the concept shows",
}


# --- §BH71 PART 1, THE HERO ELEMENT: "The concept's hero element (e.g. 91's rose-gold flower emblem), its finish and its
# --- material carry into the drawing." ----------------------------------------------------------------------------------

HERO_SCHEMA = "container_hero_trace/1.0"

HERO_PARAMS = {
    "version": "concept_hero_params/1.0",
    "lid_radius_px": 800.0,          # the lid is rectified to a circle of this radius before anything inside it is read
    "window_support_min": 0.85,      # the window's own ellipse, supported by the rectified picture's edges this much
    "window_max_share": 0.80,        # a window is smaller than the lid it sits in (its area, as a share of the lid's)
    "window_inner": 0.86,            # units are read inside this share of the window's axes (its frame left out)
    "ground_band": (0.88, 0.94),     # the window's ground is read in this band of its axes, inside its frame
    "ground_distance": 14.0,         # Lab distance from the window's own ground that is a unit
    "unit_min_share": 0.004,         # a unit covers at least this share of the window
    "metal_l_spread": 18.0,          # a unit whose lightness spreads this much is lit like metal, not a flat ink
    "highlight_l": 15.0,             # lighter than the ground by this much, touching a metal unit: its highlight
}

HERO_FROM_CONCEPT = "HERO_FROM_CONCEPT"
HERO_NOT_READ = "HERO_NOT_READ"


def _to_circle(trace: dict, radius: float):
    """The affine that takes the traced rim's ellipse to an upright circle of ``radius`` — (the 2x3 matrix, the side
    of the square it is drawn in): rotate into the ellipse's own axes, scale each to the radius, rotate back."""
    import numpy as np
    cx, cy, wa, ha, ang = trace["rim"]["cv_ellipse"]
    t = math.radians(ang)
    c, s = math.cos(t), math.sin(t)
    into = np.array([[c, s], [-s, c]])
    back = np.array([[c, -s], [s, c]])
    a = back @ np.diag([radius / (wa / 2.0), radius / (ha / 2.0)]) @ into
    side = int(2 * radius) + 40
    off = np.array([side / 2.0, side / 2.0]) - a @ np.array([cx, cy])
    return np.hstack([a, off[:, None]]).astype(np.float32), side


def trace_hero(image_bytes: bytes, trace: dict | None) -> dict:
    """The concept's hero element inside its window, read from the picture (ROUTE A — measured, never traced): the
    lid rectified to a circle with the rim's own ellipse; the window's ellipse inside it, its centre and axes as shares
    of the lid; and each unit the window holds — a teardrop's pointed end, its axis, its length and its width as shares
    of the window's width, its measured colour and whether it is lit like metal. The drawing draws each unit with the
    design language's own primitive at that pose (``design_language._petal_path``), and snaps its colour to a colour a
    record names — no pixel is placed and no colour is invented. ``HERO_NOT_READ`` with the reason when there is no
    round lid to rectify, no window in it, or nothing in the window."""
    import cv2
    import numpy as np
    rec = {"schema_version": HERO_SCHEMA, "params": dict(HERO_PARAMS), "source_sha256": None}
    if trace is not None:
        rec["source_sha256"] = trace.get("source_sha256")
    if not image_bytes or not trace or trace.get("state") != TRACED_FROM_CONCEPT or trace.get("kind") != ROUND:
        return {**rec, "state": HERO_NOT_READ, "reason": "no round lid traced to rectify"}
    img = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return {**rec, "state": HERO_NOT_READ, "reason": TRACE_IMAGE_UNREADABLE}
    R = float(HERO_PARAMS["lid_radius_px"])
    M, side = _to_circle(trace, R)
    flat = cv2.warpAffine(img, M, (side, side), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
    lid_c = side / 2.0
    # the window: the largest ellipse the rectified picture supports, inside the lid and smaller than it
    small = cv2.resize(flat, (side // 2, side // 2), interpolation=cv2.INTER_AREA)
    edges, dist = _edges(small)
    wins = []
    for e in _rims(small, dist, edges):
        cx, cy, a = 2 * e["cx"], 2 * e["cy"], 2 * e["a"]
        if (e["support"] >= HERO_PARAMS["window_support_min"] and math.hypot(cx - lid_c, cy - lid_c) + a < 0.95 * R
                and (e["a"] * e["b"] * 4) / (R * R) < HERO_PARAMS["window_max_share"]):
            wins.append(e)
    if not wins:
        return {**rec, "state": HERO_NOT_READ, "reason": "no window inside the lid the picture's edges support"}
    w = wins[0]
    wcx, wcy, wwa, wha, wang = 2 * w["cx"], 2 * w["cy"], 2 * w["w_axis"], 2 * w["h_axis"], w["angle"]
    upright = abs(((wang + 45.0) % 180.0) - 45.0) < 45.0          # its first axis within 45° of horizontal
    ww, wh = (wwa, wha) if upright else (wha, wwa)                # the window's box, in the rectified pixels
    x0, y0 = wcx - ww / 2.0, wcy - wh / 2.0
    inside = np.zeros(flat.shape[:2], np.uint8)
    k = HERO_PARAMS["window_inner"]
    cv2.ellipse(inside, ((wcx, wcy), (wwa * k, wha * k), wang), 255, -1)
    lab = cv2.cvtColor(flat, cv2.COLOR_BGR2LAB).astype(np.float32)
    # the window's own ground, read in the band just inside its frame, where no unit reaches — a median over the whole
    # window would be the units' colour wherever they cover most of it
    band = np.zeros(flat.shape[:2], np.uint8)
    cv2.ellipse(band, ((wcx, wcy), (wwa * HERO_PARAMS["ground_band"][1], wha * HERO_PARAMS["ground_band"][1]), wang), 255, -1)
    cv2.ellipse(band, ((wcx, wcy), (wwa * HERO_PARAMS["ground_band"][0], wha * HERO_PARAMS["ground_band"][0]), wang), 0, -1)
    ground = np.median(lab[band > 0], axis=0)
    fg = ((np.linalg.norm(lab - ground, axis=2) > HERO_PARAMS["ground_distance"]) & (inside > 0)).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    n, labels, stats, cents = cv2.connectedComponentsWithStats(fg, 8)
    area_in = float((inside > 0).sum())
    comps = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < HERO_PARAMS["unit_min_share"] * area_in:
            continue
        m = (labels == i).astype(np.uint8)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        comps.append((i, max(cnts, key=cv2.contourArea), cents[i], m))
    # a highlight — lighter than the window's ground and touching a unit lit like metal — is that unit's light, never a
    # unit of its own
    def lit(m):
        return float(np.std(lab[m > 0][:, 0])) > HERO_PARAMS["metal_l_spread"]
    reach = max(9, int(0.03 * ww) | 1)
    grow = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (reach, reach))
    metal = [(cv2.dilate(m, grow), cv2.convexHull(c)) for _i, c, _cc, m in comps if lit(m)]

    def highlight(c, cc, m):
        if float(np.median(lab[m > 0][:, 0])) <= float(ground[0]) + HERO_PARAMS["highlight_l"]:
            return False
        return any(bool((mm & m).any()) or cv2.pointPolygonTest(hull, (float(cc[0]), float(cc[1])), False) > 0
                   for mm, hull in metal)
    kept = [(i, c, cc, m) for i, c, cc, m in comps if not highlight(c, cc, m)]
    units = []
    for n_, (i, cnt, cc, m) in enumerate(sorted(kept, key=lambda u: (u[2][1], u[2][0]))):
        pts = cnt.reshape(-1, 2).astype(np.float64)
        tip = pts[int(np.argmax(np.hypot(pts[:, 0] - cc[0], pts[:, 1] - cc[1])))]
        far = pts[int(np.argmax(np.hypot(pts[:, 0] - tip[0], pts[:, 1] - tip[1])))]
        length = float(np.hypot(*(far - tip)))
        theta = math.atan2(far[1] - tip[1], far[0] - tip[0])
        perp = (pts[:, 0] - tip[0]) * -math.sin(theta) + (pts[:, 1] - tip[1]) * math.cos(theta)
        px = lab[m > 0]
        med = np.median(px, axis=0)
        bgr = cv2.cvtColor(np.uint8([[med]]), cv2.COLOR_LAB2BGR)[0][0]
        units.append({
            "name": "petal-%d" % n_,
            "anchor": [round(float((tip[0] - x0) / ww), 4), round(float((tip[1] - y0) / wh), 4)],
            "theta_deg": round(math.degrees(theta), 2),
            "length": round(length / ww, 4), "width": round(float(perp.max() - perp.min()) / ww, 4),
            "hex": "#%02X%02X%02X" % (int(bgr[2]), int(bgr[1]), int(bgr[0])),
            "lab": [round(float(v), 1) for v in med],
            "metal": bool(float(np.std(px[:, 0])) > HERO_PARAMS["metal_l_spread"]),
        })
    if not units:
        return {**rec, "state": HERO_NOT_READ, "reason": "the window holds nothing that differs from its own ground"}
    ground_bgr = cv2.cvtColor(np.uint8([[ground]]), cv2.COLOR_LAB2BGR)[0][0]
    return {**rec, "state": HERO_FROM_CONCEPT, "route": "A — measured primitives, no pixel traced",
            "window": {"shape": "oval", "centre": [round((wcx - lid_c) / R, 4), round((wcy - lid_c) / R, 4)],
                       "width": round(ww / (2 * R), 4), "height": round(wh / (2 * R), 4),
                       "support": round(w["support"], 4),
                       "ground_hex": "#%02X%02X%02X" % (int(ground_bgr[2]), int(ground_bgr[1]), int(ground_bgr[0]))},
            "units": units, "count": len(units), "metal_units": [u["name"] for u in units if u["metal"]]}


def hero_window_box(hero: dict) -> tuple:
    """The hero's window as (x0, y0, x1, y1) fractions of the lid's own box — its centre an offset from the lid's centre
    in shares of the lid's radius, its size in shares of the lid's diameter (``trace_hero``'s own units)."""
    w = hero["window"]
    cx, cy = 0.5 + w["centre"][0] / 2.0, 0.5 + w["centre"][1] / 2.0
    return (round(cx - w["width"] / 2.0, 4), round(cy - w["height"] / 2.0, 4),
            round(cx + w["width"] / 2.0, 4), round(cy + w["height"] / 2.0, 4))
