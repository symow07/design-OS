"""[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (7): "Geometric shapes are DRAWN, not traced: 124's arch is jagged
and broken into dashes. Arches, frames, ovals, borders and rules are rebuilt as clean geometric curves (symmetric where
the concept is), with an even stroke, matched to the concept's shape."] Line art found in a traced picture — the regions
of one ink that together make a thin, long line — and drawn as the line it is: an arch (an open curve, folded on its own
axis where it mirrors itself), an oval, a frame or a rule, its centre line fitted and smoothed, its stroke one even width
(the line's own, measured), in its ink. The regions it replaces are left out of the trace. $0: read from the redraw the
trace was made from; nothing paid."""
from __future__ import annotations

import math

#: the numbers it reads by (the executor's, new with his goal; kept on every record): ``close`` bridges a dashed line's
#: gaps (a share of the picture's width); a line is ``thin`` (its median half-width under this share of the shorter
#: side) and ``long`` (its box past this share of the shorter side); ``mirror``: an open line is symmetric where this
#: share of it lands on itself mirrored; ``rays``: the centre line read along so many rays; ``smooth``: rays averaged;
#: ``fit_px``: the fitted line stands within this many pixels (median) of the line it replaces, else it is not one;
#: ``replaced``: a traced region is the line's where this share of it lies on the line
GEOMETRY = {"version": "line_geometry/1.0", "close": 0.006, "thin": 0.012, "long": 0.25, "mirror": 0.6, "rays": 721,
            "smooth": 15, "fit_px": 1.5, "replaced": 0.7, "same_ink_de": 18.0, "points": 48, "fill": 0.08,
            "rule_box": 0.15, "inside": 0.9, "glow_de": 10.0}
ARCH, OVAL, RULE, CURVE = "arch", "oval", "rule", "curve"
#: [his goal for the pitch, B (10)] a gilded line is drawn this share of its measured run (which takes in the glow's
#: first gold pixels)
GOLD_WIDTH = 0.7


def _hex_lab(hx):
    import cv2
    import numpy as np
    px = np.uint8([[[int(hx[5:7], 16), int(hx[3:5], 16), int(hx[1:3], 16)]]])
    lab = cv2.cvtColor(px, cv2.COLOR_BGR2LAB).astype(float)[0, 0]
    return np.array([lab[0] * 100 / 255.0, lab[1] - 128, lab[2] - 128])


def _inks(regions):
    """The regions grouped by ink: every gold one together (a gilded line is drawn in its golds' lit and shaded tones,
    one line), the rest one group per ink within ``same_ink_de``."""
    import numpy as np

    from apps.pipeline.services.concept_design_map import is_gold_hex
    gold = [i for i, r in enumerate(regions) if is_gold_hex(r["fill"])]
    # [his goal for the pitch, 2026-10-15, B (10): "124's arch: a thin, bright gold line with its glow, as the concept
    # shows (it's now too thick and dull mustard)"] a gilded line keeps its two tones — its gold and its bright core —
    # never their average
    tones = sorted({regions[i]["fill"] for i in gold}, key=lambda hx: _hex_lab(hx)[0])
    groups = [{"lab": None, "idx": gold, "hex": _median_hex([regions[i]["fill"] for i in gold]),
               "tones": [tones[0], tones[-1]] if len(tones) >= 2 else None}] if gold else []
    for i, r in enumerate(regions):
        if i in gold:
            continue
        lab = _hex_lab(r["fill"])
        for g in groups:
            if g["lab"] is not None and np.linalg.norm(g["lab"] - lab) <= GEOMETRY["same_ink_de"]:
                g["idx"].append(i)
                break
        else:
            groups.append({"lab": lab, "idx": [i], "hex": r["fill"]})
    return groups


def _bright_gold(tones) -> str:
    """[His goal for the pitch, B (10): "a thin, bright gold line"] a gilded line's one colour: its gold and its bright
    core mixed half and half — never their shade's median (124's dull mustard), never a cream core alone."""
    a, b = tones[0], tones[-1]
    mix = [(int(a[i:i + 2], 16) + int(b[i:i + 2], 16)) // 2 for i in (1, 3, 5)]
    return "#%02X%02X%02X" % tuple(mix)


def _median_hex(hexes):
    import numpy as np
    arr = np.array([[int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)] for h in hexes])
    r, g, b = (int(v) for v in np.median(arr, axis=0))
    return "#%02X%02X%02X" % (r, g, b)


def _mask(regions, idx, w, h, points):
    import cv2
    import numpy as np
    m = np.zeros((h, w), np.uint8)
    for i in idx:
        for ring in regions[i]["rings"]:
            cv2.fillPoly(m, [np.int32([[x * w, y * h] for x, y in points(ring)])], 255)
    return m


def arch_of(band, w, h, box):
    """An open line folded on its own axis: its centre line from rays out of the foot of its axis, the two halves
    averaged, smoothed — ``(points left foot to apex to right foot, its axis, how well it mirrors)`` or None."""
    import numpy as np
    x0, y0, bw, bh = box
    ys, xs = np.nonzero(band)
    best = None
    for ax in np.arange(x0 + 0.35 * bw, x0 + 0.65 * bw, 0.5):
        mx = np.round(2 * ax - xs).astype(int)
        ok = (mx >= 0) & (mx < w)
        hit = float((band[ys[ok], mx[ok]] > 0).sum()) / max(int(ok.sum()), 1)      # none mirrored inside: no hit
        if best is None or hit > best[0]:
            best = (hit, ax)
    mirror, axis = best
    if mirror < GEOMETRY["mirror"]:
        return None
    cy = y0 + bh - 1.0
    half = {}
    for side in (-1, 1):
        for ang in np.linspace(0.0, math.pi / 2, GEOMETRY["rays"] // 2 + 1):
            dx, dy = side * math.cos(ang), -math.sin(ang)
            ts = np.arange(0.0, 1.3 * max(bw, bh), 0.5)
            px, py = np.round(axis + dx * ts).astype(int), np.round(cy + dy * ts).astype(int)
            ok = (px >= 0) & (px < w) & (py >= 0) & (py < h)
            on = band[py[ok], px[ok]] > 0
            if on.any():
                half.setdefault(round(ang, 5), []).append(float(ts[ok][on].mean()))
    angs = sorted(a for a, v in half.items() if len(v) == 2)
    if len(angs) < 20:
        return None
    r = np.array([sum(half[a]) / 2.0 for a in angs])
    k = GEOMETRY["smooth"]
    rs = np.convolve(np.pad(r, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
    a = np.array(angs)
    left = np.stack([axis - np.cos(a) * rs, cy - np.sin(a) * rs], 1)          # foot (angle 0) to apex (pi/2)
    raw = np.stack([axis - np.cos(a) * r, cy - np.sin(a) * r], 1)
    fit = float(np.median(np.hypot(*(left - raw).T)))
    right = np.stack([2 * axis - left[::-1, 0], left[::-1, 1]], 1)
    return np.concatenate([left, right[1:]]), axis, mirror, fit


def find(trace: dict, points, kinds=None) -> dict:
    """``{"lines": [{"kind", "points": [[x, y]] (shares of the picture), "width": a share of its width, "hex",
    "symmetric", "mirror", "fit_px"}], "replaced": [region index], "params"}`` — the line art of ``trace``'s regions
    drawn as the lines they are; ``points`` turns a traced ring into its points (``lid_art._ring_points``); ``kinds``,
    where given, the only kinds looked for (a picture from a photograph: its arches and ovals, never its edges)."""
    import cv2
    import numpy as np

    from apps.pipeline.services.concept_design_map import is_gold_hex
    w, h = trace["size_px"]
    regions = trace.get("regions") or []
    short = float(min(w, h))
    out, replaced = [], set()
    k = max(3, int(round(GEOMETRY["close"] * w)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    for group in _inks(regions):
        if len(group["idx"]) < 3:
            continue
        ink = _mask(regions, group["idx"], w, h, points)
        closed = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, kernel)
        n, lab, stats, _c = cv2.connectedComponentsWithStats(closed, 8)
        for c in range(1, n):
            x0, y0, bw, bh, area = (int(v) for v in stats[c])
            flat = min(bw, bh) < GEOMETRY["rule_box"] * max(bw, bh)
            if max(bw, bh) < GEOMETRY["long"] * short:
                continue                  # short
            band = (lab == c).astype(np.uint8)
            ring = not flat and _closed(band, bw, bh)
            if area > GEOMETRY["fill"] * bw * bh and not flat and not ring:
                continue                  # a mass — an open line covers little of its own box (a rule or a ring more)
            dist = cv2.distanceTransform(band, cv2.DIST_L2, 5)
            half = float(np.median(dist[dist > 0]))
            if half > GEOMETRY["thin"] * short:
                continue
            # its true half-width: the distance at its own middle (the transform's ridge) — the median of every pixel's
            # distance is a quarter of its width, not half
            ridge = (dist > 0) & (dist >= cv2.dilate(dist, np.ones((3, 3), np.uint8)) - 1e-6)
            mid = float(np.median(dist[ridge])) if ridge.any() else 2.0 * half
            if flat and kinds is not None and RULE not in kinds and CURVE not in kinds:
                continue                  # a picture whose straight edges are a photograph's, never drawn rules
            if flat:
                # a line that barely rises across its own length: a rule where it is straight (drawn end to end),
                # else left as traced — never folded into an arch
                ends = _rule_of(band, mid)
                if ends is not None:
                    line, axis, mirror, fit, kind = ends, float(ends[:, 0].mean()), 1.0, 0.0, RULE
                else:
                    bent = _curve_of(band, mid)        # a border that bends a little along its length: its own curve
                    if bent is None:
                        continue
                    line, axis, mirror, fit, kind = bent[0], float(bent[0][:, 0].mean()), 1.0, bent[1], CURVE
            elif ring:
                # a ring — a frame or an oval round something: drawn as the oval it is where it is one, else left
                # as traced; never folded into an arch
                ring = _oval_of(band)
                if ring is None:
                    continue
                line, axis, mirror, fit, kind = ring[0], ring[1], 1.0, ring[2], OVAL
            else:
                got = arch_of(band, w, h, (x0, y0, bw, bh))
                if got is None:
                    continue
                (line, axis, mirror, fit), kind = got, ARCH
                straight = _straight(line)
                if straight is not None:              # a rule: drawn straight, end to end, never as an arch
                    line, kind = straight, RULE
            if fit > GEOMETRY["fit_px"]:
                continue
            if kinds is not None and kind not in kinds:
                continue                  # not a kind this picture is read for
            # its even width: its closed ink measured straight across the line found, every pixel along it (the run of
            # ink through the line's own middle), the median — a break closed in a dashed line, a glint beside it, never
            # sets it
            width = _across(band, _along_points(line, kind == OVAL), 4.0 * mid) or 2.0 * mid
            reach = cv2.dilate(band, kernel)
            if kind == ARCH:
                # its legs followed down past where its band broke (behind the roses), both as far as the farther —
                # they mirror each other — and the pieces of them left out of the trace with the rest
                line = _with_legs(ink, line, width, k)
                legs = np.zeros_like(band)
                cv2.polylines(legs, [np.int32(np.round(line))], False, 1, max(1, int(round(width + 2 * k))))
                reach = np.maximum(reach, legs)
            taken = []
            for i in group["idx"]:
                one = _mask(regions, [i], w, h, points)
                if one.any() and float((reach[one > 0] > 0).mean()) >= GEOMETRY["replaced"]:
                    taken.append(i)
            replaced.update(taken)
            step = max(1, len(line) // GEOMETRY["points"])
            pts = line[::step].tolist() + ([line[-1].tolist()] if (len(line) - 1) % step else [])
            out.append({"kind": kind, "points": [[round(x / w, 5), round(y / h, 5)] for x, y in pts],
                        "width": round(width / w, 5),
                        # [his goal for the pitch, B (10)] a gilded line drawn thinner than its measured run (the
                        # glow's first gold pixels lie in it); the run itself still clears the trace's pieces along it
                        **({"drawn_width": round(GOLD_WIDTH * width / w, 5)} if group.get("tones") else {}),
                        "hex": _bright_gold(group["tones"]) if group.get("tones") else group["hex"],
                        "symmetric": True,
                        "axis": round(axis / w, 5), "mirror": round(mirror, 3), "fit_px": round(fit, 2),
                        "regions": len(taken)})
    # a line found running along a gold line, inside its width, is the gold line's own light (a gilded band's bright
    # core): its regions are the gold line's, never a line of its own
    gold = [l for l in out if is_gold_hex(l["hex"])]
    kept = []
    for line in out:
        if line in gold or not any(_along(line, g, w, h) for g in gold):
            kept.append(line)
    # a piece of any ink lying wholly inside a kept line's own corridor (its width and a pixel either side) is that
    # line's — a gilded line's cream core, its lit edge — never a piece of the picture left floating beside it
    if kept:
        corridor = np.zeros((h, w), np.uint8)
        for line in kept:
            pts = np.int32([[x * w, y * h] for x, y in line["points"]])
            cv2.polylines(corridor, [pts], line["kind"] == OVAL, 1, max(1, int(round(line["width"] * w + 2))))
        for i, region in enumerate(regions):
            if i in replaced:
                continue
            one = _mask(regions, [i], w, h, points)
            if one.any() and float((corridor[one > 0] > 0).mean()) >= GEOMETRY["inside"]:
                replaced.add(i)
    return {"lines": kept, "replaced": sorted(replaced), "params": dict(GEOMETRY)}



def glow_pieces(trace: dict, points, lines: list, bands: list) -> list:
    """[His goal of 2026-10-13, (8): "Glow is a real soft blur, never a stack of hard bands (124's arch glow reads as
    lines)."] The trace's pieces that are a found gold line's glow — each of one of its glow's own colours (within
    ``glow_de``) and lying wholly (``inside``) within the glow's reach of the line — their indices: the glow is drawn
    whole and smooth under the art (``glow_parts``), so the flat rings the trace cut it into are left out, never drawn
    over it. ``trace``: ``{"size_px", "regions"}``; ``bands``: the glow's (``{"to": a share of the width, "hex"}``)."""
    import cv2
    import numpy as np

    from apps.pipeline.services.concept_design_map import is_gold_hex
    w, h = trace["size_px"]
    regions = trace["regions"]
    gold = [line for line in lines if is_gold_hex(line["hex"])]
    if not gold or not bands:
        return []
    reach = np.zeros((h, w), np.uint8)
    for line in gold:
        pts = np.int32([[x * w, y * h] for x, y in line["points"]])
        cv2.polylines(reach, [pts], line["kind"] == OVAL, 1,
                      max(1, int(round((float(line["width"]) + 2.0 * float(bands[-1]["to"])) * w + 2))))
    inks = [_hex_lab(b["hex"]) for b in bands]
    out = []
    for i, region in enumerate(regions):
        if min(float(np.linalg.norm(_hex_lab(region["fill"]) - ink)) for ink in inks) > GEOMETRY["glow_de"]:
            continue
        one = _mask(regions, [i], w, h, points)
        if one.any() and float((reach[one > 0] > 0).mean()) >= GEOMETRY["inside"]:
            out.append(i)
    return out

def _with_legs(ink, line, width: float, gap: int):
    """An arch's line with its two legs followed on down: from each foot, row by row, the ink's own middle near where the
    leg was (a break of up to three closing gaps passed over) — the longer leg drawn on both sides, mirrored about the
    arch's own axis, since the legs mirror each other and a picture's flowers hide one more than the other."""
    import numpy as np
    pts = np.asarray(line, float)
    h, w = ink.shape
    r = int(max(2.0, width / 2.0 + 3.0))
    axis = float(pts[int(np.argmin(pts[:, 1])), 0])

    def follow(foot):
        x, y = float(foot[0]), int(round(foot[1]))
        path, miss = [], 0
        while y + 1 < h and miss <= 3 * gap:
            y += 1
            x0, x1 = max(0, int(round(x)) - r), min(w, int(round(x)) + r + 1)
            row = np.nonzero(ink[y, x0:x1])[0]
            if len(row):
                x = float(x0 + row.mean())
                path.append((x, float(y)))
                miss = 0
            else:
                miss += 1
        return path
    left, right = follow(pts[0]), follow(pts[-1])
    leg = left if len(left) >= len(right) else [(2.0 * axis - x, y) for x, y in right]
    if len(leg) < 2:
        return pts
    step = max(1, len(leg) // 8)
    leg = leg[step - 1::step] + ([leg[-1]] if (len(leg) % step) else [])
    mirrored = [(2.0 * axis - x, y) for x, y in leg]
    # the arch's own last few points at each foot give way to the leg, so its curve runs into the leg without a hook
    trim = max(1, len(pts) // 16)
    return np.vstack([np.array(leg[::-1]), pts[trim:-trim], np.array(mirrored)])


def _along_points(line, closed: bool) -> list:
    """Points every pixel along a found line (its own points joined), round to its start where it is closed."""
    import numpy as np
    pts = np.asarray(line, float)
    if closed:
        pts = np.vstack([pts, pts[:1]])
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(np.hypot(*(b - a))))
        out += [a + (b - a) * k / n for k in range(n)]
    return out


def _across(band, along: list, reach: float) -> float | None:
    """The median run of ``band`` straight across a line through ``along`` (its points, in order): at each point on the
    ink, along the line's normal there, the unbroken ink through the point, out to ``reach`` either side; None where
    none is."""
    import numpy as np
    pts = np.asarray(along, float)
    if len(pts) < 3:
        return None
    d = np.gradient(pts, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    steps = np.arange(0.5, reach, 0.5)
    runs = []
    for p, (dx, dy) in zip(pts, d):
        if not _on(band, p):
            continue
        n = np.array([-dy, dx])
        out_t = next((t for t in steps if not _on(band, p + n * t)), reach)
        in_t = next((t for t in steps if not _on(band, p - n * t)), reach)
        runs.append(out_t + in_t)
    return float(np.median(runs)) if runs else None


def _on(band, p) -> bool:
    h, w = band.shape
    xi, yi = int(round(float(p[0]))), int(round(float(p[1])))
    return 0 <= xi < w and 0 <= yi < h and bool(band[yi, xi])


def _rule_of(band, half: float):
    """A band's two ends where its ink lies along one straight line — every pixel of it within its own half-width and
    ``fit_px`` of that line (95th percentile) — else None."""
    import cv2
    import numpy as np
    ys, xs = np.nonzero(band)
    pts = np.stack([xs, ys], 1).astype(np.float32)
    vx, vy, cx, cy = (float(v) for v in cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01).reshape(-1))
    off = np.abs((pts[:, 0] - cx) * vy - (pts[:, 1] - cy) * vx)
    if float(np.percentile(off, 95)) > half + GEOMETRY["fit_px"]:
        return None
    t = (pts[:, 0] - cx) * vx + (pts[:, 1] - cy) * vy
    return np.array([[cx + float(t.min()) * vx, cy + float(t.min()) * vy], [cx + float(t.max()) * vx, cy + float(t.max()) * vy]])


def _curve_of(band, half: float):
    """``(points, the fit in pixels)`` — a thin line that runs one way along its length (a border, a rim seen in
    perspective) as the smooth curve through its middle: its ink read across its own long axis every two pixels, the
    middles smoothed, kept where every bin holds ink and its ink lies within its half-width and ``fit_px`` of the curve
    (95th percentile); else None."""
    import numpy as np
    ys, xs = np.nonzero(band)
    pts = np.stack([xs, ys], 1).astype(float)
    centre = pts.mean(axis=0)
    _u, _s, vt = np.linalg.svd(pts - centre, full_matrices=False)
    along, across = vt[0], vt[1]
    t = (pts - centre) @ along
    o = (pts - centre) @ across
    bins = np.arange(t.min(), t.max() + 2.0, 2.0)
    mids = []
    for a, b in zip(bins[:-1], bins[1:]):
        m = (t >= a) & (t < b)
        if m.any():
            mids.append(((a + b) / 2.0, float(o[m].mean())))
    if len(mids) < 0.9 * (len(bins) - 1) or len(mids) < 8:
        return None                                  # a gap along it, or a line that folds back: not one curve
    tt = np.array([m[0] for m in mids])
    oo = np.array([m[1] for m in mids])
    k = min(GEOMETRY["smooth"], (len(oo) // 2) * 2 - 1)
    sm = np.convolve(np.pad(oo, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
    off = np.abs(o - np.interp(t, tt, sm))
    if float(np.percentile(off, 95)) > half + GEOMETRY["fit_px"]:
        return None
    fit = float(np.median(np.abs(oo - sm)))
    line = centre + np.outer(tt, along) + np.outer(sm, across)
    step = max(1, len(line) // GEOMETRY["points"])
    return line[::step], fit


def _straight(line):
    """A line's two ends where every point of it stands within ``fit_px`` (or a pixel and a half) of the straight line
    through it — a rule; else None."""
    import cv2
    import numpy as np
    pts = np.asarray(line, np.float32)
    vx, vy, cx, cy = (float(v) for v in cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01).reshape(-1))
    off = np.abs((pts[:, 0] - cx) * vy - (pts[:, 1] - cy) * vx)
    if float(off.max()) > max(1.5, GEOMETRY["fit_px"]):
        return None
    t = (pts[:, 0] - cx) * vx + (pts[:, 1] - cy) * vy
    return np.array([[cx + float(t.min()) * vx, cy + float(t.min()) * vy], [cx + float(t.max()) * vx, cy + float(t.max()) * vy]])


def _closed(band, bw: int, bh: int) -> bool:
    """Whether a line's ink closes round a hole of its own (a ring), the hole a quarter of its box or more."""
    import cv2
    cnts, hier = cv2.findContours(band.astype("uint8"), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None:
        return False
    holes = [cv2.contourArea(c) for c, hh in zip(cnts, hier[0]) if hh[3] >= 0]
    return bool(holes) and max(holes) >= 0.25 * bw * bh


def oval_points(cx: float, cy: float, ax: float, ay: float, angle_deg: float, n: int) -> list:
    """``n`` points round an ellipse (centre, half axes, its turn) — a closed line's points, first not repeated."""
    t = math.radians(angle_deg)
    out = []
    for k in range(n):
        a = 2.0 * math.pi * k / n
        u, v = ax * math.cos(a), ay * math.sin(a)
        out.append((cx + u * math.cos(t) - v * math.sin(t), cy + u * math.sin(t) + v * math.cos(t)))
    return out


def _oval_of(band):
    """``(points, its centre's x, the fit in pixels)`` — a ring drawn as the ellipse it is: the ellipse through the
    middle of its ink (the mean of its outer and inner edges' fits), kept where both edges stand within ``fit_px`` x 2
    of their ellipses (median); None for a ring that is no oval (a rounded square, a frame)."""
    import cv2
    import numpy as np
    cnts, hier = cv2.findContours(band.astype("uint8"), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    outer = max((c for c, hh in zip(cnts, hier[0]) if hh[3] < 0), key=cv2.contourArea)
    inner = max((c for c, hh in zip(cnts, hier[0]) if hh[3] >= 0), key=cv2.contourArea)
    fits = []
    for edge in (outer, inner):
        if len(edge) < 5:
            return None
        (cx, cy), (ma, mb), ang = cv2.fitEllipse(edge)
        pts = edge.reshape(-1, 2).astype(float)
        t = math.radians(ang)
        u = (pts[:, 0] - cx) * math.cos(t) + (pts[:, 1] - cy) * math.sin(t)
        v = -(pts[:, 0] - cx) * math.sin(t) + (pts[:, 1] - cy) * math.cos(t)
        r = np.hypot(u / (ma / 2.0), v / (mb / 2.0))
        fits.append(((cx, cy, ma / 2.0, mb / 2.0, ang), float(np.median(np.abs(r - 1.0))) * (ma + mb) / 4.0))
    if max(f[1] for f in fits) > 2.0 * GEOMETRY["fit_px"]:
        return None
    (c1, c2) = (fits[0][0], fits[1][0])
    mid = [(a + b) / 2.0 for a, b in zip(c1, c2)]
    return (np.array(oval_points(mid[0], mid[1], mid[2], mid[3], mid[4], GEOMETRY["points"] * 2)), mid[0],
            max(f[1] for f in fits))


def _along(line, gold, w, h) -> bool:
    """Whether ``line`` runs along ``gold``: its points, median, within half the gold line's width of it."""
    import numpy as np
    a = np.array(line["points"]) * [w, h]
    b = np.array(gold["points"]) * [w, h]
    d = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(2)).min(1)
    return float(np.median(d)) <= max(2.0, 0.5 * gold["width"] * w + 2.0)


def segments(line: dict, x: float, y: float, w: float, h: float) -> list:
    """A found line as smooth cubic segments on the page (mm): a Catmull-Rom curve through its points, its ends and the
    arch's apex kept sharp."""
    from apps.ire.graph import CubicTo, MoveTo
    pts = [(x + px * w, y + py * h) for px, py in line["points"]]
    if line["kind"] == OVAL:                        # a closed line: round to its first point again
        pts = pts + pts[:1]
    apex = min(range(len(pts)), key=lambda i: pts[i][1]) if line["kind"] == ARCH else None
    segs = [MoveTo(x=pts[0][0], y=pts[0][1])]
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 and i != apex else pts[i]
        p3 = pts[i + 2] if i + 2 < len(pts) and i + 1 != apex else pts[i + 1]
        p1, p2 = pts[i], pts[i + 1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        segs.append(CubicTo(x1=c1[0], y1=c1[1], x2=c2[0], y2=c2[1], x=p2[0], y=p2[1]))
    return segs


#: the glow's mesh: ``steps`` patches round each end of a half, so a glow stands round a sharp apex with no notch
GLOW_MESH = {"version": "glow_mesh/1.0", "cap_steps": 8, "ring_steps": 48}


def glow_parts(line: dict, x: float, y: float, w: float, h: float, bands: list, sides=(-1.0, 1.0)) -> list:
    """[His goal of 2026-10-13, (8): "Glow is a real soft blur, never a stack of hard bands".] The glow round a found line
    as smooth meshes (``graph.MeshFill``'s patches, mm, and their corners' strengths) — ``[{"patches", "alphas", "box":
    [x0, y0, x1, y1], "blur"}]``, each part drawn inside its own box: from the stroke's edge out through each of the
    redraw's glow colours (``bands``: ``[{"to": a share of the picture's width, "hex"}]``, inner first; each colour at its
    band's middle), the last fading to nothing over one more band's width — whatever is drawn beneath it shows through,
    as under a real blur, never a colour read from elsewhere that steps where the glow ends. A folded line's halves are
    each their own part, round at both their ends and cut at the line's own axis — so the two meet there without a seam
    (they mirror each other), never one half's edge laid over the other's glow."""
    import numpy as np
    pts = np.array([(x + px * w, y + py * h) for px, py in line["points"]])
    half_w = 0.5 * float(line.get("drawn_width") or line["width"]) * w      # the glow begins where the drawn line ends
    # each band's own colour at its middle, the glow's first at the stroke's edge
    edges = [half_w] + [max(half_w + 0.05 * (k + 1), b["to"] * w) for k, b in enumerate(bands)]
    # … and a blur's own tail: the last colour fades to nothing over one more band's width, never cut at its reach
    radii = [half_w] + [(edges[k] + edges[k + 1]) / 2.0 for k in range(len(bands))] + [edges[-1] + (edges[-1] - edges[-2])]
    inks = [bands[0]["hex"]] + [b["hex"] for b in bands] + [bands[-1]["hex"]]
    strengths = [1.0] * (len(radii) - 1) + [0.0]
    apex = int(np.argmin(pts[:, 1])) if line["kind"] == ARCH else len(pts) - 1
    halves = ([pts[:apex + 1], pts[apex:]] if line["kind"] == ARCH
              else [np.vstack([pts, pts[:1]])] if line["kind"] == OVAL else [pts])
    axis = float(pts[apex, 0]) if line["kind"] == ARCH else None

    out = []
    for n, part in enumerate(halves):
        if len(part) < 2:
            continue
        patches, alphas = [], []
        d = np.gradient(part, axis=0)
        d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
        normal = np.stack([-d[:, 1], d[:, 0]], 1)
        ends = ((part[0], -d[0]), (part[-1], d[-1])) if line["kind"] != OVAL else ()
        steps = GLOW_MESH["cap_steps"]
        # ring by ring, the outermost first: on the inside of a bend the patches of neighbouring points overlap, and
        # each place shows the ring nearest the line — 124's arch, drawn point by point, showed a neighbour's first
        # ring over its second inside its apex: a flat colour, then a step
        for k in range(len(radii) - 2, -1, -1):
            for side in sides:
                for i in range(len(part) - 1):
                    a0, a1 = part[i] + side * normal[i] * radii[k], part[i + 1] + side * normal[i + 1] * radii[k]
                    b1, b0 = (part[i + 1] + side * normal[i + 1] * radii[k + 1],
                              part[i] + side * normal[i] * radii[k + 1])
                    patches.append([*a0, *a1, *b1, *b0, inks[k], inks[k], inks[k + 1], inks[k + 1]])
                    alphas.append([strengths[k], strengths[k], strengths[k + 1], strengths[k + 1]])
            # round ends: a fan of patches from the line's end round the half circle beyond it (a closed line has none)
            for end, tangent in ends:
                n0 = np.array([-tangent[1], tangent[0]])
                for j in range(steps):
                    t0, t1 = math.pi * j / steps, math.pi * (j + 1) / steps
                    u0 = n0 * math.cos(t0) + tangent * math.sin(t0)
                    u1 = n0 * math.cos(t1) + tangent * math.sin(t1)
                    a0, a1 = end + u0 * radii[k], end + u1 * radii[k]
                    b1, b0 = end + u1 * radii[k + 1], end + u0 * radii[k + 1]
                    patches.append([*a0, *a1, *b1, *b0, inks[k], inks[k], inks[k + 1], inks[k + 1]])
                    alphas.append([strengths[k], strengths[k], strengths[k + 1], strengths[k + 1]])
        if not patches:
            continue
        xs = [p[k] for p in patches for k in (0, 2, 4, 6)]
        ys = [p[k] for p in patches for k in (1, 3, 5, 7)]
        box = [min(xs), min(ys), max(xs), max(ys)]
        if axis is not None:                    # each half on its own side of the axis — the side it lies on
            box = ([box[0], box[1], axis, box[3]] if float(np.mean(part[:, 0])) < axis
                   else [axis, box[1], box[2], box[3]])
        # the layered file's own: each band a stroke along the line as wide as the band reaches, under Illustrator's
        # Gaussian blur as soft as the band is wide — the widest first
        rings = [{"width": round(2.0 * edges[k], 3), "hex": bands[k - 1]["hex"],
                  "blur": round(max(0.05, edges[k] - edges[k - 1]), 3)} for k in range(len(bands), 0, -1)]
        out.append({"patches": [[round(float(v), 3) if not isinstance(v, str) else v for v in p] for p in patches],
                    "alphas": alphas, "box": [round(v, 3) for v in box],
                    "blur": {"points": [[round(float(px), 3), round(float(py), 3)] for px, py in part],
                             "closed": line["kind"] == OVAL, "rings": rings}})
    return out


def glow_patches(line: dict, x: float, y: float, w: float, h: float, bands: list, sides=(-1.0, 1.0)) -> list:
    """Every part's patches of ``glow_parts``, together (a line that is not folded is one part)."""
    return [p for part in glow_parts(line, x, y, w, h, bands, sides) for p in part["patches"]]


def field_grid(rows: list, x: float, y: float, w: float, h: float, reach=None) -> dict:
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (9): "Gradients are smooth, never flat bands".] A colour
    field read on a grid — ``rows`` of hex, top to bottom, each left to right, the colour at each cell's middle — as the
    corners of a smooth mesh over the box at (``x``, ``y``), ``w`` x ``h`` mm: ``{"xs", "ys", "inks"}`` — the cell middles,
    its edge rows and columns carried out to the box's edges (``graph.MeshFill.grid``), or out to ``reach`` (``[x0, y0,
    x1, y1]`` mm, the shape the field fills) where the shape runs past the box: [(7): "matched to the concept's shape"]
    the field fills its shape to the shape's own edge — 125's lavender rim to rim — never a box inside it."""
    nr, nc = len(rows), len(rows[0])
    x0, y0, x1, y1 = (x, y, x + w, y + h) if reach is None else (min(x, float(reach[0])), min(y, float(reach[1])),
                                                                 max(x + w, float(reach[2])), max(y + h, float(reach[3])))
    xs = [x0] + [x + (j + 0.5) * w / nc for j in range(nc)] + [x1]
    ys = [y0] + [y + (i + 0.5) * h / nr for i in range(nr)] + [y1]
    inks = [[rows[min(max(i - 1, 0), nr - 1)][min(max(j - 1, 0), nc - 1)] for j in range(len(xs))]
            for i in range(len(ys))]
    return {"xs": [round(v, 3) for v in xs], "ys": [round(v, 3) for v in ys], "inks": inks}


def patches_of_grid(grid: dict) -> list:
    """A grid's mesh (``graph.MeshFill``'s patches, mm): a patch between each four neighbouring corners — blended by the
    reader, never a band."""
    xs, ys, inks = grid["xs"], grid["ys"], grid["inks"]
    out = []
    for i in range(len(ys) - 1):
        for j in range(len(xs) - 1):
            out.append([xs[j], ys[i], xs[j + 1], ys[i], xs[j + 1], ys[i + 1], xs[j], ys[i + 1],
                        inks[i][j], inks[i][j + 1], inks[i + 1][j + 1], inks[i + 1][j]])
    return out


def field_patches(rows: list, x: float, y: float, w: float, h: float) -> list:
    """``field_grid``'s mesh, its patches (``patches_of_grid``)."""
    return patches_of_grid(field_grid(rows, x, y, w, h))


def ring_blur(centre, half, angle_deg: float, grow: float, inner: str) -> dict:
    """``ring_patches``'s soft edge as the layered file carries it (``graph.MeshFill.blur``): one stroke of its own colour
    along the oval's edge, as wide as the ring, under Illustrator's own Gaussian blur as soft as it is wide."""
    reach = (grow - 1.0) * (float(half[0]) + float(half[1])) / 2.0
    pts = oval_points(float(centre[0]), float(centre[1]), float(half[0]), float(half[1]), float(angle_deg),
                      GLOW_MESH["ring_steps"])
    return {"points": [[round(px, 3), round(py, 3)] for px, py in pts], "closed": True,
            "rings": [{"width": round(2.0 * reach, 3), "hex": inner, "blur": round(reach, 3)}]}


def ring_patches(centre, half, angle_deg: float, grow: float, inner: str) -> tuple:
    """[His goal of 2026-10-13, (8).] A soft edge round an oval — its own colour (``inner``) at its edge, fading to
    nothing at ``grow`` times its size, over whatever is drawn beneath it — as one smooth mesh ring: ``(patches,
    alphas)`` (``graph.MeshFill``'s, mm), never rings stacked one over another."""
    cx, cy = float(centre[0]), float(centre[1])
    hx, hy = float(half[0]), float(half[1])
    t = math.radians(float(angle_deg))

    def pt(a, k):
        u, v = hx * k * math.cos(a), hy * k * math.sin(a)
        return cx + u * math.cos(t) - v * math.sin(t), cy + u * math.sin(t) + v * math.cos(t)
    steps = GLOW_MESH["ring_steps"]
    out = []
    for j in range(steps):
        a0, a1 = 2 * math.pi * j / steps, 2 * math.pi * (j + 1) / steps
        p0, p1, p2, p3 = pt(a0, 1.0), pt(a1, 1.0), pt(a1, grow), pt(a0, grow)
        out.append([round(v, 3) for v in (*p0, *p1, *p2, *p3)] + [inner, inner, inner, inner])
    return out, [[1.0, 1.0, 0.0, 0.0] for _ in out]
