"""The stand die folded (owner's part 2, 2026-10-31): one model of a die in three dimensions, read from the die itself.

Every face of a die's parts is carried by a hinge tree (``Plan``): a root face posed in the stand, each other face turned
about its crease by its fold angle. The board is modelled by its mid-plane, ± half a caliper. Everything that proves a
stand reads this one model and never a second description of it: the closed size, how every panel meets its neighbour,
whether any two panels pass through each other, whether each lock's tab really lands in its slot, each product's seat and
clearance, the sightlines, and the line drawings (apps/dielines/exporters/stand_sheets.py).

Frames. On the die: x right, y down the sheet, the print side toward the reader, so local z points to the board's inner
side. In the stand: x as the shopper sees it, y away from the shopper, z up, the counter at z = 0."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import unary_union

TOL_MM = 0.01
#: every joint's bar (the owner's §4): gap or overlap 0.0–0.5 mm
JOINT_MAX_MM = 0.5
#: what a sightline ray is sampled at on a product's front face, in its width, and the steps down it (mm)
FACE_COLUMNS = (0.1, 0.5, 0.9)
FACE_STEP_MM = 1.0
HEADER_STEP_MM = 2.0
#: the owner's two eyes (§4): mm in front of the stand, mm above the counter
EYES = ((500.0, 350.0), (550.0, 500.0))
#: the owner's shade rule (part 3): the least of a carrier's colour window that must be seen
SHADE_WINDOW_SHARE = 0.5
#: what the no-bare-board check reads a face at
VIEW_STEP_MM = 4.0
#: a panel this many calipers off another, mid-plane to mid-plane, lies on it
LAP_CALIPERS = 1.5
#: the widest gap between two panels that reads as a dark line rather than a surface in view (the fit gap is 0.25 mm)
FIT_GAP_READ_MM = 0.3


def translation(x=0.0, y=0.0, z=0.0):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def pose(origin, x_axis, y_axis):
    """The transform taking a part's flat frame to the stand: the flat origin lands on ``origin``, flat x along ``x_axis``,
    flat y along ``y_axis`` (local z, the board's inner side, is their cross product)."""
    x, y = np.asarray(x_axis, float), np.asarray(y_axis, float)
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = x, y, np.cross(x, y), origin
    return m


def _rotation(point, axis, degrees):
    """A turn of ``degrees`` about the line through ``point`` along the unit vector ``axis`` (Rodrigues)."""
    a = math.radians(degrees)
    k = np.asarray(axis, float)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    R = np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K
    m = np.eye(4)
    m[:3, :3] = R
    p = np.asarray(point, float)
    m[:3, 3] = p - R @ p
    return m


@dataclass
class Hinge:
    """``child`` turns about ``crease`` (a crease, half-cut, perforation or join of the part) off ``parent``. A positive
    ``angle`` folds it toward the board's inner side, a negative one toward the print side; ``offset`` then lifts it that
    far off the parent's mid-plane along the parent's inner side (a 180° fold lands one caliper on)."""
    child: str
    parent: str
    crease: str
    angle: float
    offset: float = 0.0


@dataclass
class PartPlan:
    root: str
    pose: np.ndarray
    hinges: list = field(default_factory=list)


@dataclass
class Joint:
    """Where a panel meets a neighbour that is not hinged to it. ``edge``: a's nearest boundary against b's surface.
    ``lap``: a lies flat against b, surface to surface."""
    a: tuple      # (part, face)
    b: tuple
    kind: str = "edge"
    note: str = ""


@dataclass
class Lock:
    """A tab through a slot. ``tab``: (part, face); ``slot``: (part, slot id). ``kind``: ``flush`` stops level with the far
    surface; ``through`` passes it; ``barbed`` carries a head wider than its slot beyond the board."""
    id: str
    tab: tuple
    slot: tuple
    kind: str = "through"
    min_through_mm: float = 0.0


@dataclass
class Step:
    """One assembly step: its plain words, the hinges closed by it (child face names per part), the part it brings in,
    and the way that part approaches (mm, in the stand)."""
    words: str
    part: str = ""
    close: dict = field(default_factory=dict)
    approach: tuple = (0.0, 0.0, 0.0)
    products: bool = False
    angles: dict = field(default_factory=dict)      # a hinge's angle at this step and after, where it differs from the built stand's
    torn: bool = True                               # what tears away is gone by this step


@dataclass
class Plan:
    parts: dict                     # part name → PartPlan
    joints: list = field(default_factory=list)
    locks: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    products: list = field(default_factory=list)    # {"index", "row", "column", "frame": 4×4, "w", "d", "h", "seat", "plate"}


@dataclass
class Folded:
    part: str
    name: str
    printed: bool
    T: np.ndarray
    polygon: Polygon          # the face in its flat frame
    solid: object             # the face less its slots and openings: what a ray or a panel hits
    t: float

    @property
    def normal(self):
        return self.T[:3, 2]

    def world(self, xy):
        p = np.c_[np.asarray(xy, float), np.zeros(len(xy)), np.ones(len(xy))]
        return (self.T @ p.T).T[:, :3]

    def to_local(self, points):
        p = np.c_[np.asarray(points, float), np.ones(len(points))]
        return (np.linalg.inv(self.T) @ p.T).T[:, :3]

    def corners(self):
        return self.world(np.asarray(self.polygon.exterior.coords)[:-1])


def _edge_lines(part):
    return {name: line for name, line in
            list(part.creases) + list(part.joins) + list(getattr(part, "half_cuts", [])) + list(getattr(part, "perfs", []))}


def _hinge_matrix(line, child_polygon, angle, offset):
    """The turn of a child about its crease, in the parent's flat frame."""
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    u = np.array([x1 - x0, y1 - y0, 0.0])
    u /= np.linalg.norm(u)
    c = child_polygon.representative_point()
    w = np.array([c.x - x0, c.y - y0, 0.0])
    w -= u * (w @ u)
    if np.linalg.norm(w) < 1e-9:
        raise ValueError("A child face lies on its own crease")
    # k × w = |w| z: a positive angle carries the child toward local +z
    k = np.cross(w, (0.0, 0.0, 1.0))
    k /= np.linalg.norm(k)
    m = _rotation((x0, y0, 0.0), k, angle)
    lift = translation(z=offset)
    return lift @ m


def fold(die, plan, *, closed=None, approach=None, only=None, angles=None, keep_torn=False):
    """Every face of the die in the stand. ``closed``: per part, the share (0–1) each hinge's child is closed by, a hinge
    not named lying flat; None: all closed. ``approach``: per part, a shift of its whole. ``only``: the parts wanted.
    Returns {(part, face): Folded}."""
    moves = getattr(die, "moves", {})
    t = die.board_mm
    removed = set() if keep_torn else getattr(plan, "removed", set())
    angles = angles or {}
    out = {}
    for part in die.parts:
        if part.name not in plan.parts or (only is not None and part.name not in only):
            continue
        spec = plan.parts[part.name]
        dx, dy = moves.get(part.name, (0.0, 0.0))
        lines = _edge_lines(part)
        faces = {name: polygon for name, polygon, _printed in part.faces}
        printed = {name: is_printed for name, _polygon, is_printed in part.faces}
        shift = translation(*(approach or {}).get(part.name, (0.0, 0.0, 0.0)))
        T = {spec.root: shift @ spec.pose @ translation(-dx, -dy)}
        pending = list(spec.hinges)
        while pending:
            progressed = False
            for hinge in list(pending):
                if hinge.parent not in T:
                    continue
                share = 1.0 if closed is None else closed.get(part.name, {}).get(hinge.child, 0.0)
                angle = angles[hinge.child] if hinge.child in angles else hinge.angle * share
                T[hinge.child] = T[hinge.parent] @ _hinge_matrix(lines[hinge.crease], faces[hinge.child],
                                                                 angle, hinge.offset * share)
                pending.remove(hinge)
                progressed = True
            if not progressed:
                raise ValueError("A hinge of %s hangs from a face that is not joined: %s" % (part.name, pending[0].child))
        for name, polygon in faces.items():
            if name not in T:
                raise ValueError("The face %s of %s is on no hinge" % (name, part.name))
            if (part.name, name) in removed:                # torn away before the stand stands
                continue
            cuts = [slot["polygon"] for slot in part.slots if slot["polygon"].intersection(polygon).area > 1e-6]
            solid = polygon.difference(unary_union(cuts)) if cuts else polygon
            out[part.name, name] = Folded(part.name, name, printed[name], T[name], polygon, solid, t)
    return out


# --- the measures -----------------------------------------------------------------------------------------------------

def _rings(geometry):
    rings = []
    for piece in getattr(geometry, "geoms", [geometry]):
        if piece.is_empty:
            continue
        rings.append(np.asarray(piece.exterior.coords))
        rings.extend(np.asarray(ring.coords) for ring in piece.interiors)
    return rings


def closed_size(folded):
    """The closed stand's size, the board's thickness in it: {x, y, z: [min, max]}."""
    low, high = np.full(3, np.inf), np.full(3, -np.inf)
    for face in folded.values():
        c = face.corners()
        half = np.abs(face.normal) * face.t / 2
        low, high = np.minimum(low, (c - half).min(axis=0)), np.maximum(high, (c + half).max(axis=0))
    return {"x": [float(low[0]), float(high[0])], "y": [float(low[1]), float(high[1])], "z": [float(low[2]), float(high[2])]}


def slice_at(face, target, z=0.0):
    """Where ``face`` crosses the plane local z = ``z`` of ``target``: segments in target's flat frame ([] if it does not;
    None if it lies in that plane)."""
    points = []
    all_z = []
    for ring in _rings(face.solid):
        p = target.to_local(face.world(ring))
        all_z.append(p[:, 2])
        for a, b in zip(p, p[1:]):
            da, db = a[2] - z, b[2] - z
            if (da > 1e-9) != (db > 1e-9):
                s = da / (da - db)
                points.append(a[:2] + s * (b[:2] - a[:2]))
    if np.ptp(np.concatenate(all_z)) < 1e-9:
        return None
    if len(points) < 2:
        return []
    points = np.array(points)
    axis = points[np.argmax(np.linalg.norm(points - points[0], axis=1))] - points[0]
    order = np.argsort((points - points[0]) @ axis)
    points = points[order]
    return [LineString([points[i], points[i + 1]]) for i in range(0, len(points) - 1, 2)
            if np.linalg.norm(points[i + 1] - points[i]) > 1e-9]


def joint_gap(joint, folded):
    """The gap (positive) or overlap (negative) of one joint, surface to surface, in mm; None if the two do not face."""
    a, b = folded[joint.a], folded[joint.b]
    t = a.t
    p = b.to_local(a.corners())
    if joint.kind == "lap":
        if abs(abs(a.normal @ b.normal) - 1) > 1e-6:
            return None
        section = Polygon(p[:, :2]).buffer(0).intersection(b.polygon)
        if section.area <= 1e-6:
            return None
        return float(abs(p[:, 2].mean()) - t)
    near = np.abs(p[:, 2]).min()
    close = p[np.abs(p[:, 2]) <= near + 1e-6]
    if b.polygon.buffer(1.0).distance(MultiPoint(close[:, :2]).convex_hull) > 1e-6:
        return None
    return float(near - t / 2)


def joints_report(plan, folded, *, bar=JOINT_MAX_MM):
    rows = []
    for joint in plan.joints:
        gap = joint_gap(joint, folded)
        rows.append({"a": " / ".join(joint.a), "b": " / ".join(joint.b), "kind": joint.kind,
                     "gap_mm": None if gap is None else round(gap, 3), "note": joint.note,
                     "ok": gap is not None and abs(gap) <= bar + 1e-6})
    return {"bar_mm": bar, "joints": rows, "passed": bool(rows) and all(row["ok"] for row in rows)}


def _hinged_pairs(plan):
    pairs = set()
    for part, spec in plan.parts.items():
        for hinge in spec.hinges:
            pairs.add(frozenset(((part, hinge.child), (part, hinge.parent))))
    return pairs


def _strip(face, target, half):
    """Where ``face`` runs through the slab |local z of target| ≤ half: its solid's sections, in target's flat frame, each
    apart (near-collinear segments do not survive a union)."""
    lines = []
    for z in (-half, 0.0, half):
        lines.extend(slice_at(face, target, z) or [])
    return lines


def interference(plan, folded, *, tolerance=0.02):
    """Two panels may not pass through each other. Parallel and overlapping: their surfaces closer than a caliper. Crossing:
    a panel's mid-slice inside another's solid. Hinged neighbours are skipped; a tab in its slot does not count, since a
    slot is not solid. Returns the collisions."""
    hinged = _hinged_pairs(plan)
    names = list(folded)
    found = []
    for i, ka in enumerate(names):
        a = folded[ka]
        for kb in names[i + 1:]:
            if frozenset((ka, kb)) in hinged:
                continue
            b = folded[kb]
            t = a.t
            ca, cb = a.corners(), b.corners()
            if (ca.max(axis=0) < cb.min(axis=0) - t).any() or (cb.max(axis=0) < ca.min(axis=0) - t).any():
                continue
            if abs(abs(a.normal @ b.normal) - 1) < 1e-6:
                p = b.to_local(ca)
                distance = abs(float(p[:, 2].mean()))
                if distance < t - tolerance:
                    area = Polygon(p[:, :2]).buffer(0).intersection(b.solid).area
                    if area > 0.5:
                        found.append({"a": " / ".join(ka), "b": " / ".join(kb), "kind": "parallel", "distance_mm": round(distance, 3),
                                      "area_mm2": round(area, 2)})
                continue
            half = t / 2 - tolerance
            for one, two in ((a, b), (b, a)):
                solid = two.solid.buffer(-tolerance)
                length = max((line.intersection(solid).length for line in _strip(one, two, half)), default=0.0)
                if length > 0.05:
                    found.append({"a": " / ".join(ka), "b": " / ".join(kb), "kind": "crossing", "length_mm": round(float(length), 3)})
                    break
    return found


def locks_report(plan, folded, die):
    """Each lock read in three dimensions: the tab's section in its slot's plane must lie inside the slot with its thickness
    and play; it must reach through the board as the lock asks; a barbed one must carry a head wider than the slot past it."""
    parts = {part.name: part for part in die.parts}
    rows = []
    for lock in plan.locks:
        row = {"id": lock.id, "kind": lock.kind, "tab": " / ".join(lock.tab), "slot": " / ".join(lock.slot)}
        slot = next(item for item in parts[lock.slot[0]].slots if item["id"] == lock.slot[1])
        host_name = max((name for name, polygon, _p in parts[lock.slot[0]].faces),
                        key=lambda name: slot["polygon"].buffer(0.01).intersection(
                            next(polygon for n, polygon, _p in parts[lock.slot[0]].faces if n == name)).area)
        host = folded[lock.slot[0], host_name]
        tab = folded[lock.tab]
        t = tab.t
        sections = slice_at(tab, host, 0.0)
        p = host.to_local(tab.corners())
        high, low = p[:, 2].max(), p[:, 2].min()
        # the far side is the one its root is not on: the board its parent face hangs from stays on the near side
        hinge = next(h for h in plan.parts[lock.tab[0]].hinges if h.child == lock.tab[1])
        root_z = host.to_local(folded[lock.tab[0], hinge.parent].corners())[:, 2].mean()
        far = low if root_z > 0 else high
        through = abs(far) + t / 2 if high * low < 0 else 0.0
        row["through_mm"] = round(float(through), 3)
        if not sections:
            row.update(ok=False, why="the tab does not reach the slot's board")
            rows.append(row)
            continue
        section = max(sections, key=lambda s: s.length)
        body = section.buffer(t / 2, cap_style=2, join_style=2)
        fits = slot["polygon"].buffer(1e-6).contains(body)
        row["section_mm"] = round(section.length, 3)
        row["slot_mm"] = [round(slot.get("length_mm", 0.0), 3), round(slot.get("width_mm", 0.0), 3)]
        row["off_centre_mm"] = round(float(section.interpolate(0.5, normalized=True).distance(slot["polygon"].centroid)), 3)
        ok = bool(fits) and through >= lock.min_through_mm - TOL_MM
        why = "" if fits else "the tab's section falls outside its slot"
        if fits and not ok:
            why = "the tab reaches %.2f mm through; the lock asks %.2f" % (through, lock.min_through_mm)
        if lock.kind == "barbed":
            width = 0.0
            for share in (.3, .5, .7, .9):
                head = slice_at(tab, host, float(far) * share) or []
                width = max(width, max((s.length for s in head), default=0.0))
            row["head_mm"] = round(float(width), 3)
            if width <= slot.get("length_mm", 0.0):
                ok, why = False, "the head is no wider than its slot: nothing holds it"
        row.update(ok=bool(ok), **({"why": why} if why else {}))
        rows.append(row)
    return {"locks": rows, "count": len(rows), "passed": bool(rows) and all(row["ok"] for row in rows)}


def _box_corners(product):
    w, d, h = product["w"], product["d"], product["h"]
    local = np.array([[x, y, z, 1.0] for x in (-w / 2, w / 2) for y in (-d / 2, d / 2) for z in (0.0, h)])
    return (product["frame"] @ local.T).T[:, :3]


_BOX_EDGES = [(a, b) for a in range(8) for b in range(a + 1, 8) if bin(a ^ b).count("1") == 1]


def _box_section(product, face, z=0.0):
    """The product's section in a face's plane z, as a polygon in the face's flat frame (empty if it misses)."""
    p = face.to_local(_box_corners(product))
    points = []
    for a, b in _BOX_EDGES:
        da, db = p[a][2] - z, p[b][2] - z
        if (da > 1e-9) != (db > 1e-9):
            s = da / (da - db)
            points.append(p[a][:2] + s * (p[b][:2] - p[a][:2]))
    if len(points) < 3:
        return Polygon()
    return MultiPoint(points).convex_hull


def fit_report(plan, folded, *, clearance_mm, die=None):
    """Each product at its true size against what holds it: inside its opening with the clearance, on its seat, and in
    no panel. Clearance is the opening less the product across each way (the owner's: product + 1 mm)."""
    rows = []
    for product in plan.products:
        plate = folded[product["plate"]]
        section = _box_section(product, plate)
        opening = None
        for ring in plate.solid.interiors if hasattr(plate.solid, "interiors") else []:
            polygon = Polygon(ring)
            if polygon.contains(section.representative_point()):
                opening = polygon
        row = {"index": product["index"], "row": product["row"], "column": product["column"], "plate": " / ".join(product["plate"])}
        if opening is None:
            row.update(ok=False, why="no opening holds it")
            rows.append(row)
            continue
        x0, y0, x1, y1 = section.bounds
        ox0, oy0, ox1, oy1 = opening.bounds
        across = [ox1 - ox0 - (x1 - x0), oy1 - oy0 - (y1 - y0)]
        sides = min(x0 - ox0, ox1 - x1, y0 - oy0, oy1 - y1)
        seat = folded[product["seat"]]
        base = seat.to_local(_box_corners(product)[[i for i in range(8) if i % 2 == 0]])
        rest = float(np.abs(base[:, 2]).max() - seat.t / 2)
        hits = []
        for key, face in folded.items():
            for z in (-face.t / 2 + .02, 0.0, face.t / 2 - .02):
                cross = _box_section(product, face, z)
                if not cross.is_empty and cross.intersection(face.solid).area > 0.02:
                    hits.append(" / ".join(key))
                    break
        fits = min(across) >= product.get("clearance_mm", clearance_mm) - TOL_MM and sides > 0 and abs(rest) <= 0.05 and not hits
        row.update(clearance_mm=[round(v, 3) for v in across], least_side_mm=round(float(sides), 3),
                   above_seat_mm=round(rest, 3), hits=sorted(set(hits)), ok=bool(fits))
        rows.append(row)
    return {"clearance_mm": clearance_mm, "products": rows, "count": len(rows),
            "passed": bool(rows) and all(row["ok"] for row in rows)}


def art_report(folded, die):
    """No artwork under a flap and none in a glue zone. A printed face's print side must have nothing lying on it, and no
    glue zone may land on a printed face's print side or sit on one in the flat."""
    rows = []
    printed = [face for face in folded.values() if face.printed]
    for face in printed:
        for key, other in folded.items():
            if other is face or abs(abs(other.normal @ face.normal) - 1) > 1e-6:
                continue
            p = face.to_local(other.corners())
            z = float(p[:, 2].mean())
            if -2.5 * face.t < z < -1e-6:              # local z points inward: the print side is below
                area = Polygon(p[:, :2]).buffer(0).intersection(face.polygon).area
                if area > 1.0:
                    rows.append({"face": face.name, "under": " / ".join(key), "area_mm2": round(area, 1)})
    glue = list(getattr(die, "glue", []))
    for name, polygon in glue:
        for part in die.parts:
            for face_name, face, is_printed in part.faces:
                if is_printed and polygon.intersection(face).area > 0.5:
                    rows.append({"face": face_name, "glue": name})
    return {"printed_faces": [face.name for face in printed], "glue_zones": len(glue), "faults": rows, "passed": not rows}


# --- the sightlines ---------------------------------------------------------------------------------------------------

def _inside(xy, rings):
    """Even-odd over all rings at once: xy (n × 2) inside the polygon with holes."""
    inside = np.zeros(len(xy), bool)
    for ring in rings:
        a, b = ring[:-1], ring[1:]
        for (ax, ay), (bx, by) in zip(a, b):
            crosses = (ay > xy[:, 1]) != (by > xy[:, 1])
            if crosses.any():
                at = (bx - ax) * (xy[:, 1] - ay) / ((by - ay) or 1e-12) + ax
                inside ^= crosses & (xy[:, 0] < at)
    return inside


def _rays_blocked(eye, points, folded, products, skip, *, slab=False, whole=False, grow=0.0):
    """For each point, whether anything of the stand stands between the eye and it; and which. ``slab``: a panel stops a ray at either of its
    surfaces as well as its mid-plane, for a point on a surface a fit gap behind it. ``whole``: as if no panel had an opening. ``grow``: panels
    this much wider, so a fit gap between two of them reads as the dark line it is."""
    n = len(points)
    blocked = np.zeros(n, bool)
    names = {}
    d = points - eye
    for key, face in folded.items():
        inv = np.linalg.inv(face.T)
        e = inv[:3, :3] @ eye + inv[:3, 3]
        v = (inv[:3, :3] @ d.T).T
        shape = face.polygon if whole else face.solid
        rings = _rings(shape.buffer(grow, join_style=2) if grow else shape)
        for level in ((-face.t / 2, 0.0, face.t / 2) if slab else (0.0,)):
            with np.errstate(divide="ignore", invalid="ignore"):
                s = (level - e[2]) / v[:, 2]
            near = (s > 1e-6) & (s < 1 - 1e-6) & np.isfinite(s)
            if not near.any():
                continue
            xy = e[:2] + s[near, None] * v[near, :2]
            hit = _inside(xy, rings)
            if hit.any():
                idx = np.where(near)[0][hit]
                fresh = idx[~blocked[idx]]
                if len(fresh):
                    names[" / ".join(key)] = names.get(" / ".join(key), 0) + len(fresh)
                blocked[idx] = True
    for product in products:
        if product["index"] == skip:
            continue
        inv = np.linalg.inv(product["frame"])
        e = inv[:3, :3] @ eye + inv[:3, 3]
        v = (inv[:3, :3] @ d.T).T
        lo = np.array([-product["w"] / 2, -product["d"] / 2, 0.0])
        hi = np.array([product["w"] / 2, product["d"] / 2, product["h"]])
        with np.errstate(divide="ignore", invalid="ignore"):
            a, b = (lo - e) / v, (hi - e) / v
        low = np.nanmax(np.minimum(a, b), axis=1)
        high = np.nanmin(np.maximum(a, b), axis=1)
        hit = (high > low) & (high > 1e-6) & (low < 1 - 1e-6)
        if hit.any():
            fresh = hit & ~blocked
            if fresh.any():
                names["product %d" % product["index"]] = int(fresh.sum())
            blocked |= hit
    return blocked, names


def _eye_point(eye_row, width):
    return np.array([width / 2, -eye_row[0], eye_row[1]])


def sightlines_report(plan, folded, *, width, face_bar_mm, safe_mm=3.0, eyes=EYES):
    """From each eye: how much of every product's front face is seen, measured down from its top across its whole width;
    the share of it seen at all; and how much of the header's safe area is seen. A product passes when its top ``face_bar_mm``
    is seen whole; the header when its safe area is seen whole."""
    out = []
    for eye_row in eyes:
        eye = _eye_point(eye_row, width)
        rows = []
        for product in plan.products:
            w, d, h = product["w"], product["d"], product["h"]
            levels = np.arange(h, -1e-9, -FACE_STEP_MM)
            samples = np.array([[w * (u - .5), -d / 2 - 1e-3, z, 1.0] for z in levels for u in FACE_COLUMNS])
            world = (product["frame"] @ samples.T).T[:, :3]
            blocked, names = _rays_blocked(eye, world, folded, plan.products, product["index"])
            seen_level = ~blocked.reshape(len(levels), len(FACE_COLUMNS)).any(axis=1)
            run = 0
            for flag in seen_level:
                if not flag:
                    break
                run += 1
            band = 0.0 if run == 0 else min(h, (run - 1) * FACE_STEP_MM + FACE_STEP_MM * (run < len(levels)))
            rows.append({"index": product["index"], "row": product["row"], "column": product["column"],
                         "top_band_mm": round(float(band), 1), "seen_share": round(float(1 - blocked.mean()), 3),
                         "ok": band >= product.get("bar_mm", face_bar_mm) - 1e-6, "blocked_by": sorted(names)})
        report = {"eye_mm": {"in_front": eye_row[0], "above_counter": eye_row[1]}, "products": rows,
                  "products_passed": all(row["ok"] for row in rows)}
        # the header's shopper leaf, on whichever part carries it; a stand without one is not a stand that passes
        face = next((row for key, row in folded.items() if key[1] == "header front"), None)
        if face is None:
            report["header"] = {"seen_share": 0.0, "blocked_by": [], "ok": False, "samples": 0, "why": "the stand has no header"}
        else:
            safe = face.polygon.buffer(-safe_mm, join_style=2)
            x0, y0, x1, y1 = safe.bounds
            grid = np.array([[x, y] for x in np.arange(x0, x1 + 1e-9, HEADER_STEP_MM) for y in np.arange(y0, y1 + 1e-9, HEADER_STEP_MM)])
            grid = grid[_inside(grid, _rings(safe))]
            # a hair off the printed side, so the header's own board does not block its own face
            world = face.world(grid) - face.normal * 1e-3
            blocked, names = _rays_blocked(eye, world, folded, plan.products, None)
            report["header"] = {"seen_share": round(float(1 - blocked.mean()), 4), "blocked_by": sorted(names),
                                "ok": not blocked.any(), "samples": int(len(grid))}
        report["passed"] = report["products_passed"] and report["header"]["ok"]
        out.append(report)
    return {"schema": "stand_fold/sightlines-1", "method": "3-D rays from each eye to the folded die's faces and the products at "
            "their true sizes; the board by its mid-plane", "face_bar_mm": face_bar_mm, "eyes": out,
            "passed": all(row["passed"] for row in out)}


def _window_seen(eye, product, folded, products):
    """The share of a product's colour window, the front of its body below the cap, the eye sees; and how many points were read."""
    w, d, h = product["w"], product["d"], product["h"]
    levels = np.arange(h - (product.get("cap") or 0.0) - FACE_STEP_MM / 2, 0.0, -FACE_STEP_MM)       # the middle of each millimetre
    samples = np.array([[w * (u - .5), -d / 2 - 1e-3, z, 1.0] for z in levels for u in FACE_COLUMNS])
    if not len(samples):
        return 0.0, 0
    world = (product["frame"] @ samples.T).T[:, :3]
    blocked, _names = _rays_blocked(eye, world, folded, products, product["index"])
    return float(1 - blocked.mean()), len(samples)


def shade_report(plan, folded, *, width, names=None, share=SHADE_WINDOW_SHARE, eyes=EYES):
    """The owner's shade rule (part 3): every shade shows its colour to the shopper. A column is a shade; what carries it is its tester, else every
    product that says so, else every product in it. At least ``share`` of each carrier's colour window must be seen from every eye. A column with no
    carrier, or a window with no points read, fails: this check cannot pass by skipping."""
    names = {row["column"]: row for row in (names or [])}
    rows = []
    columns = sorted({product["column"] for product in plan.products})
    for column in columns:
        inside = [product for product in plan.products if product["column"] == column]
        carriers = [product for product in inside if product.get("tester") or product.get("carries_shade")] or inside
        if any("carries_shade" in product for product in inside) and not any(product.get("carries_shade") for product in inside):
            carriers = []
        seen = []
        for eye_row in eyes:
            eye = _eye_point(eye_row, width)
            for product in carriers:
                value, points = _window_seen(eye, product, folded, plan.products)
                seen.append({"eye": list(eye_row), "index": product["index"], "tester": bool(product.get("tester")), "share": round(value, 3), "points": points})
        worst = min((row["share"] for row in seen), default=0.0)
        ok = bool(seen) and all(row["points"] for row in seen) and worst >= share - 1e-6
        rows.append({"column": column, "shade": names.get(column, {}).get("name"), "hex": names.get(column, {}).get("hex"), "fourth_status": names.get(column, {}).get("fourth_status"), "carried_by": "tester" if any(row["tester"] for row in seen) else "product" if seen else "nothing",
                     "worst_share": round(worst, 3), "ok": ok, "readings": seen, **({} if ok else {"why": "no tester or product carries it" if not seen else "only %.0f %% of its colour window is seen" % (100 * worst)})})
    return {"schema": "stand_fold/shades-1", "rule": "at least %.0f %% of a carrier's colour window, from every eye" % (100 * share), "columns": rows, "worst_share": min((row["worst_share"] for row in rows), default=0.0),
            "passed": bool(rows) and all(row["ok"] for row in rows)}


def view_report(plan, folded, die, *, eyes=EYES, step=VIEW_STEP_MM):
    """No bare board in view (the owner's part 3). Every face is read from every eye with the stand stocked: a point of it the eye reaches is either its print
    side, which must carry art (a printed face or one of the die's ground faces), or its unprinted side, which is bare board. A caliper of each edge is left
    out: the model is the board's mid-plane, and its edges are a thickness apart. A stand of which nothing is read fails."""
    art = set(getattr(die, "ground_faces", None) or [])
    seen, bare, unprinted, through = {}, {}, {}, {}
    read = 0
    size = closed_size(folded)
    width = size["x"][0] + size["x"][1]
    for key, face in folded.items():
        inner = face.solid.buffer(-face.t, join_style=2)
        if inner.is_empty:
            continue
        x0, y0, x1, y1 = inner.bounds
        grid = np.array([[x, y] for x in np.arange(x0 + step / 2, x1, step) for y in np.arange(y0 + step / 2, y1, step)])
        if not len(grid):
            continue
        grid = grid[_inside(grid, _rings(inner))]
        if not len(grid):
            continue
        # a panel lying flat on this one covers it: the fit gap between them is a dark line, not a surface in view
        laps = {}
        for other_key, other in folded.items():
            if other_key == key or abs(abs(other.normal @ face.normal) - 1) > 1e-6:
                continue
            p = face.to_local(other.corners())
            z = float(p[:, 2].mean())
            if 0 < abs(z) <= LAP_CALIPERS * face.t:
                laps.setdefault(z > 0, []).append(Polygon(p[:, :2]).buffer(0).buffer(FIT_GAP_READ_MM, join_style=2))
        for eye_row in eyes:
            eye = _eye_point(eye_row, width)
            side = float((np.linalg.inv(face.T) @ np.array([*eye, 1.0]))[2])
            on_side = laps.get(side > 0)
            uncovered = grid if not on_side else grid[~np.array([any(lap.contains(Point(*xy)) for lap in on_side) for xy in grid])]
            if not len(uncovered):
                continue
            points = face.world(uncovered) + np.sign(side) * face.normal * (face.t / 2 + 1e-3)      # on the surface this eye faces
            blocked, _names = _rays_blocked(eye, points, folded, plan.products, None, slab=True, grow=FIT_GAP_READ_MM)
            read += len(points)
            if blocked.all():
                continue
            name = " / ".join(key)
            shut, _names = _rays_blocked(eye, points, folded, plan.products, None, slab=True, whole=True, grow=FIT_GAP_READ_MM)
            open_view = int((~blocked & ~shut).sum())
            hole_only = int((~blocked & shut).sum())
            if hole_only:                               # only down a product's clearance: a dark slit round it, not a surface in view
                through[name] = max(through.get(name, 0), hole_only)
            if not open_view:
                continue
            seen[name] = max(seen.get(name, 0), open_view)
            if side > 0:                                # local z points to the board's inner side: its unprinted side faces this eye
                bare[name] = max(bare.get(name, 0), open_view)
            elif not face.printed and key not in art:
                unprinted[name] = max(unprinted.get(name, 0), open_view)
    faults = [{"face": name, "kind": "its unprinted side is in view", "points": count} for name, count in sorted(bare.items())]
    faults += [{"face": name, "kind": "its print side is in view with no art", "points": count} for name, count in sorted(unprinted.items())]
    return {"schema": "stand_fold/view-1", "points_read": read, "step_mm": step, "faces_seen": sorted(seen), "seen_points": seen, "through_openings_only": through, "faults": faults,
            "passed": read > 0 and bool(seen) and not faults}


# --- the rest of a die's proof ------------------------------------------------------------------------------------------

def _direction(line):
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    return np.array([x1 - x0, y1 - y0]) / max(math.dist((x0, y0), (x1, y1)), 1e-9)


def grain_report(die, record):
    """The grain declared on the die and read against every fold: a fold across it folds cleanly and the panel keeps its column
    strength; a fold along it wanders, so it is listed for a wider crease and a sample. The main folds must all run across."""
    axis = record["production"]["grain_axis"]
    grain = np.array([0.0, 1.0]) if axis == "y" else np.array([1.0, 0.0])
    main = set(record["production"]["main_folds"])
    rows = []
    for part in die.parts:
        for name, line in list(part.creases) + list(part.half_cuts) + list(part.perfs):
            across = abs(_direction(line) @ grain) < 0.5
            rows.append({"part": part.name, "fold": name, "across_grain": bool(across), "main": name in main})
    missing = sorted(main - {row["fold"] for row in rows})
    bad = [row["fold"] for row in rows if row["main"] and not row["across_grain"]]
    return {"declared": record["production"]["grain"], "axis_on_the_die": axis, "folds": rows, "along_grain": [row["fold"] for row in rows if not row["across_grain"]],
            "main_folds_missing": missing, "main_folds_along_grain": bad, "passed": not missing and not bad}


def allowances_report(die, record):
    """Every fold of the die with its stated allowance: a fold no rule covers fails."""
    rows, unstated = [], []
    table = record["production"]["compensation"]
    for part in die.parts:
        for name, _line in list(part.creases) + list(part.half_cuts) + list(part.perfs):
            match = next((row for row in table if any(word in name for word in row.get("matches", []))), None)
            if match is None:
                unstated.append(part.name + " / " + name)
                continue
            rows.append({"part": part.name, "fold": name, "allowance_mm": match["allowance_mm"], "rule": match["rule"]})
    return {"folds": rows, "unstated": unstated, "passed": bool(rows) and not unstated}


def tip_report(plan, folded, *, mass_each_g, board_g_per_m2=None):
    """The one strength figure the rules can compute without a sample: how far the loaded stand tips before it falls, from its
    footprint and its centre of mass. ⟪PROVISIONAL⟫ until tested."""
    masses, moments = [], []
    area_density = (board_g_per_m2 or 500.0) / 1e6            # g per mm²
    for face in folded.values():
        c = face.polygon.centroid
        world = face.world([(c.x, c.y)])[0]
        m = face.polygon.area * area_density
        masses.append(m)
        moments.append(world * m)
    for product in plan.products:
        centre = (product["frame"] @ np.array([0.0, 0.0, product["h"] / 2, 1.0]))[:3]
        masses.append(mass_each_g)
        moments.append(centre * mass_each_g)
    total = sum(masses)
    com = sum(moments) / total
    size = closed_size(folded)
    x0, x1 = size["x"]
    y0, y1 = size["y"]
    margin = min(com[0] - x0, x1 - com[0], com[1] - y0, y1 - com[1])
    return {"mass_g": round(float(total), 1), "centre_of_mass_mm": [round(float(v), 1) for v in com],
            "tips_after_deg": round(math.degrees(math.atan2(margin, com[2])), 1), "provisional": True,
            "words": "⟪PROVISIONAL⟫ computed from the footprint and the centre of mass, the product's mass assumed; not a test"}


def slots_report(die, clear):
    """Every slot and opening kept clear of the creases that run beside it: a cut parallel to a crease and too close to it tears or will not
    fold. A crease that merely ends near a slot is the trade rules' matter."""
    rows = []
    for part in die.parts:
        folds = list(part.creases) + list(part.half_cuts)
        for slot in part.slots:
            for name, line in folds:
                d = _direction(line)
                x0, y0, x1, y1 = slot["polygon"].bounds
                along = np.array([x1 - x0, y1 - y0])
                # the slot's long side parallel to this crease, or an opening, whose every side is
                if slot.get("kind") != "opening" and abs(d @ (along / np.linalg.norm(along))) < 0.9:
                    continue
                gap = slot["polygon"].distance(line)
                if gap < clear - 0.01:
                    faces_it = line.buffer(clear + 1.0, cap_style=2).intersection(slot["polygon"]).area > 1e-6
                    if faces_it:
                        rows.append({"part": part.name, "slot": slot["id"], "crease": name, "gap_mm": round(float(gap), 3)})
    return {"clear_mm": clear, "too_close": rows, "passed": not rows}
