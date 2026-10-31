"""counter_tray_header 1.0 — the single-product counter display brought to production grade (owner, 2026-10-28).

Built on the product-grid branch's solved grid (counter_tray_header.solve_product_tray: the brief's rows × columns, the
openings from the product plus clearance), drawn again from the conventions measured on the house's own display dies
(apps/dielines/docs/research/counter_display_references.md):

- board presets, and at every fold its board-thickness compensation (one caliper, as the references' wall creases are
  inset: 0.5 mm on white card, 1.5 mm on E-flute);
- the header is the back panel's own board, doubled over (no hinge between them), its folded leaf one caliper shorter so
  it closes flat, held by a lock tab through a slot at the back panel's top;
- the corner glue flaps tapered at both ends (G3), their glue zones marked clear of the crease and the edges (G4);
- the insert (holder) locked: its plate's tabs pass through slots in the side walls with 0.3 mm play, its feet glued;
- each opening sized from the product plus clearance, with retention tongues reaching 0.6 mm into the product's face;
- no cut within 3 mm of a crease's end unless the crease ends on it; panels between parallel creases at least three
  calipers; grain marked; bleed only past printed faces.

The flat die is a counter_tray_header ``Die`` of ``Part`` s (the composer and the sheet exporters read it unchanged);
openings and lock slots are cut polygons in ``Part.slots``; glue zones ride in the record."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from statistics import median

from shapely import affinity
from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import linemerge, unary_union

VERSION = "1.0"
SCHEMA = "counter_tray_header/product-grid-2"
#: a record of the stand family's templates (stand_templates): its own solver, die and proofs
TEMPLATE_SCHEMA = "stand_template/1"


# --- the product grid the die is built on (from counter_tray_header 0.1, the consolidation of 2026-10-28) ---------

TEMPLATE_ID = "counter_tray_header"


#: a measure agrees with what it closes onto within this (mm)
TOL_MM = 0.01


#: the bleed every part's cut outline is offset by (mitre); the die's words stand clear of it
DIE_BLEED_MM = 3.0


def _r(value, nd=4):
    return round(float(value), nd) + 0.0          # + 0.0: never a negative zero in a record


@dataclass
class Part:
    name: str
    label: str
    faces: list = field(default_factory=list)      # (face name, Polygon, printed)
    creases: list = field(default_factory=list)    # (crease name, LineString)
    holes: list = field(default_factory=list)      # (hole name, (cx, cy), radius) — cut circles inside a face
    slits: list = field(default_factory=list)      # (slit name, LineString) — cut lines that bound no face
    tabs: list = field(default_factory=list)       # {"id", "base": LineString, "polygon", "meets"}
    slots: list = field(default_factory=list)      # {"id", "polygon", "length_mm", "width_mm"}
    joins: list = field(default_factory=list)      # (name, LineString) — in-plane joins: neither cut nor crease
    marks: list = field(default_factory=list)      # (text, (x, y), size, face, side) — words inside a face (WORDS
    #                                                layer); side "reverse": on the face's unprinted side, drawn flipped
    hole_shape: str = "circle"                    # holes store radius or half-side; legacy circle tuples stay valid
    half_cuts: list = field(default_factory=list)  # (name, LineString) — a part-through cut a fold runs on
    perfs: list = field(default_factory=list)      # (name, LineString) — a tear line
    corner_relief: object = None                   # where a tray's corner makes its creases and cuts meet

    def __post_init__(self):
        _validate_hole_shape(self.hole_shape)

    def hole_polygons(self):
        """The actual opening boundaries, used by fit, safe-area and cut exporters."""
        for name, (x, y), half in self.holes:
            yield name, (_rect(x - half, y - half, x + half, y + half)
                         if self.hole_shape == "square" else Point(x, y).buffer(half, 64))

    def hole_cut_length(self):
        return sum((8.0 if self.hole_shape == "square" else 2 * math.pi) * half
                   for _name, _centre, half in self.holes)

    def outline(self):
        return unary_union([f for _n, f, _p in self.faces])

    def cut_lines(self):
        rings = []
        for _n, f, _p in self.faces:
            rings.append(LineString(f.exterior.coords))
            rings.extend(LineString(i.coords) for i in f.interiors)
        lines = unary_union(rings)
        uncut = [c for _n, c in self.creases] + [j for _n, j in self.joins] + \
            [c for _n, c in self.half_cuts] + [c for _n, c in self.perfs]
        if uncut:
            lines = lines.difference(unary_union(uncut).buffer(1e-6, cap_style=2))
        merged = linemerge(lines) if lines.geom_type == "MultiLineString" else lines
        out = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
        out += [s for _n, s in self.slits]
        return [ln for ln in out if ln.length > 1e-6]

    def moved(self, dx, dy) -> "Part":
        mv = lambda geom: affinity.translate(geom, dx, dy)  # noqa: E731
        return Part(self.name, self.label,
                    [(n, mv(f), p) for n, f, p in self.faces], [(n, mv(c)) for n, c in self.creases],
                    [(n, (c[0] + dx, c[1] + dy), r) for n, c, r in self.holes], [(n, mv(s)) for n, s in self.slits],
                    [dict(tb, base=mv(tb["base"]), polygon=mv(tb["polygon"])) for tb in self.tabs],
                    [dict(sl, polygon=mv(sl["polygon"])) for sl in self.slots],
                    [(n, mv(j)) for n, j in self.joins],
                    [(m[0], (m[1][0] + dx, m[1][1] + dy)) + tuple(m[2:]) for m in self.marks], self.hole_shape,
                    [(n, mv(c)) for n, c in self.half_cuts], [(n, mv(c)) for n, c in self.perfs],
                    None if self.corner_relief is None else mv(self.corner_relief))


def _validate_hole_shape(value):
    if value not in ("circle", "square"):
        raise ValueError("A tray opening must be a circle or square")


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _seg(x0, y0, x1, y1):
    return LineString([(x0, y0), (x1, y1)])


@dataclass
class Die:
    parts: list
    sheet_w: float
    sheet_h: float
    labels: list          # (text, (x, y), size) — x, y the text's baseline start, mm
    bar: tuple            # (x, y, length) — the 50 mm calibration bar
    title: str


SHEET_MARGIN_MM = 25.0


PART_GAP_MM = 20.0


LABEL_MM = 6.0


def _halfspaces_box(x0, x1, y0, y1, z0, z1):
    return [((1, 0, 0), x1), ((-1, 0, 0), -x0), ((0, 1, 0), y1), ((0, -1, 0), -y0), ((0, 0, 1), z1), ((0, 0, -1), -z0)]


def _seg_hits_convex(e, p, planes, s_max=1.0 - 1e-7):
    lo, hi = 1e-9, s_max
    d = (p[0] - e[0], p[1] - e[1], p[2] - e[2])
    for (nx, ny, nz), off in planes:
        num = off - (nx * e[0] + ny * e[1] + nz * e[2])
        den = nx * d[0] + ny * d[1] + nz * d[2]
        if abs(den) < 1e-15:
            if num < 0:
                return False
            continue
        s = num / den
        if den > 0:
            hi = min(hi, s)
        else:
            lo = max(lo, s)
        if lo > hi:
            return False
    return hi - lo > 1e-9


def _seg_hits_cylinder(e, p, cx, cy, r, z0, z1, s_max=1.0 - 1e-7):
    dx, dy, dz = p[0] - e[0], p[1] - e[1], p[2] - e[2]
    fx, fy = e[0] - cx, e[1] - cy
    a = dx * dx + dy * dy
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r
    if a < 1e-15:
        return False
    disc = b * b - 4 * a * c
    if disc <= 0:
        return False
    sq = math.sqrt(disc)
    lo, hi = max((-b - sq) / (2 * a), 1e-9), min((-b + sq) / (2 * a), s_max)
    if abs(dz) < 1e-15:
        if not (z0 <= e[2] <= z1):
            return False
    else:
        sa, sb = (z0 - e[2]) / dz, (z1 - e[2]) / dz
        lo, hi = max(lo, min(sa, sb)), min(hi, max(sa, sb))
    return hi - lo > 1e-9


def _first_hit(e, p, occ, skip):
    for name, kind, data in occ:
        if name == skip:
            continue
        hit = _seg_hits_convex(e, p, data) if kind == "box" else _seg_hits_cylinder(e, p, *data)
        if hit:
            return name
    return None


PRODUCT_GRID_SCHEMA = "counter_tray_header/product-grid-1"


def solve_product_tray(*, product_width_mm, product_depth_mm, product_height_mm,
                       rows, columns, count, width_mm, depth_mm, height_mm,
                       header_height_mm, front_height_mm, board_mm=1.5,
                       hole_shape="square", clearance_mm=0.5, top_edge="square", row_seat_z_mm=None):
    """Single-product tray: an arbitrary counted grid, a holder, and a doubled header.

    This branch uses its own product inputs. It does not substitute a bottle for
    any historical palette, lipstick or balm. Dimensions are provisional until
    a folded sample is checked; visibility reports never alter the row seats.
    """
    _validate_hole_shape(hole_shape)
    if top_edge != "square":
        raise ValueError("This tray branch requires the declared square header edge")
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
           for value in (rows, columns, count)) or rows * columns != count or count > 100:
        raise ValueError("The observed tray count must equal rows times columns (at most 100)")
    values = dict(product_width_mm=product_width_mm, product_depth_mm=product_depth_mm,
                  product_height_mm=product_height_mm, width_mm=width_mm, depth_mm=depth_mm,
                  height_mm=height_mm, header_height_mm=header_height_mm,
                  front_height_mm=front_height_mm, board_mm=board_mm, clearance_mm=clearance_mm)
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 5000:
            raise ValueError("%s must be a finite positive millimetre measurement" % name)
    values = {name: float(value) for name, value in values.items()}
    t, W, D, H = (values[name] for name in ("board_mm", "width_mm", "depth_mm", "height_mm"))
    if row_seat_z_mm is not None:
        if (not isinstance(row_seat_z_mm, (list, tuple)) or len(row_seat_z_mm) != rows
                or any(isinstance(z, bool) or not isinstance(z, (int, float)) or not math.isfinite(z)
                       or z < t or z >= H or (z != t and z < 5 * t) for z in row_seat_z_mm)):
            raise ValueError("Each measured seat must be on the floor or leave room for a closed two-board support")
        values["row_seat_z_mm"] = list(map(float, row_seat_z_mm))
    front, header = values["front_height_mm"] - t, values["header_height_mm"]
    back = H - t - header
    fw, fd = W - 2 * t, D - 2 * t
    side = max(values["product_width_mm"], values["product_depth_mm"]) + values["clearance_mm"]
    if min(front, back, fw, fd) <= t or back < front:
        raise ValueError("The tray dimensions leave no usable floor, walls or header")
    fit = max(t, 1.0)
    pw, pd = fw - 2 * fit, fd - 2 * fit
    if min(pw, pd) <= 0:
        raise ValueError("The tray dimensions leave no usable holder plate")
    # The minimum web follows the existing engine's three-board rule. Centres
    # spread over the usable plate, retaining this edge margin on all four sides.
    edge = 3 * t
    def centres(span, number):
        if number == 1:
            return [span / 2]
        start = edge + side / 2
        return [start + index * (span - 2 * start) / (number - 1) for index in range(number)]
    xs, ys = centres(pw, columns), centres(pd, rows)
    row_platforms = []
    if row_seat_z_mm is not None:
        row_depth = pd / rows
        ys = [(row + .5) * row_depth for row in range(rows)]
        for row, seat in enumerate(row_seat_z_mm, 1):
            row_platforms.append({"row": row, "depth_mm": row_depth, "y0_mm": (row - 1) * row_depth,
                "seat_z_mm": float(seat), "seat_part": "seat row %d" % row if seat > t else None,
                "seat_wall_height_mm": float(seat) - 3 * t if seat > t else None,
                "collar_part": "holder row %d" % row, "collar_top_z_mm": float(seat) + 4 * t,
                "collar_leg_mm": 2 * t, "collar_foot_mm": 3 * t})
    leg = min(front, values["product_height_mm"] * 0.2)
    flap = min(12.0, front * 0.75, back * 0.75, fd / 4)
    foot = min(10.0, pd / 4)
    holes = [{"index": r * columns + c + 1, "row": r + 1, "column": c + 1,
              "centre_mm": [_r(x), _r(y)], "shape": hole_shape, "size_mm": _r(side),
              "product_centre_mm": [_r(t + fit + x), _r(t + fit + y)],
              "seat_z_mm": _r(row_seat_z_mm[r] if row_seat_z_mm is not None else t)}
             for r, y in enumerate(ys) for c, x in enumerate(xs)]
    result = {"schema": PRODUCT_GRID_SCHEMA,
            "template": {"id": TEMPLATE_ID, "version": VERSION, "branch": "single_product_grid",
                         "provisional": True, "production_ready": False},
            "inputs": values, "layout": {"rows": rows, "columns": columns, "count": count},
            "hole_shape": hole_shape, "top_edge": top_edge, "holes": holes,
            "geometry": {"floor_mm": [fw, fd], "front_panel_height_mm": front,
                         "back_panel_height_mm": back, "header_height_mm": header,
                         "holder_mm": [pw, pd], "holder_height_mm": leg, "holder_inset_mm": fit,
                         "corner_glue_flap_mm": flap, "holder_foot_flap_mm": foot,
                         "minimum_web_mm": edge, "opening_size_mm": side},
            "assembly": "Fold the tray walls and glue the corner flaps inside the sides. Fold the header double. "
                        "Fold the holder legs down and glue their feet to the tray floor. Products stand on the floor.",
            "provisional": True,
            "authority": {"layout": "picked-picture inspection", "product": "product brief measurements",
                          "dimensions": "brief and picked-picture panel proportions; provisional",
                          "clearance": "execution specification, total across the opening",
                          "top_edge": "owner-authorized square header edge"}}
    if row_platforms:
        result["geometry"]["row_platforms"] = row_platforms
        result["assembly"] = ("Fold and glue the tray. Fold each row seat into a closed box and glue its bottom to the tray floor. "
            "Fold each square-hole collar's end legs down and glue its feet onto that row's seat. "
            "Bottles rest on the solid seats, not through a hole onto the tray floor. Fold the header double.")
        result["authority"]["seats"] = "source bottle-height scale, paired cap tops and observed front-base clearance"
        result["authority"]["collar"] = ("provisional construction: four-board engagement, two-board end legs, "
                                            "three-board glue feet; no front wall across printed bottle labels")
    return result


def _product_row_parts(record, row):
    """A closed seat box carries weight; its low, end-supported collar locates bottles."""
    width = record["geometry"]["holder_mm"][0]
    depth = row["depth_mm"]
    parts = []
    if row["seat_part"]:
        wall = row["seat_wall_height_mm"]
        flap = min(3 * record["inputs"]["board_mm"], wall / 2, depth / 4)
        seat = Part(row["seat_part"], "ROW %d SEAT — closed box; glue bottom to tray floor" % row["row"])
        seat.faces = [("seat", _rect(0, 0, width, depth), False),
            ("front wall", _rect(0, -wall, width, 0), False),
            ("bottom", _rect(0, -wall - depth, width, -wall), False),
            ("back wall", _rect(0, depth, width, depth + wall), False),
            ("closure flap", _rect(0, depth + wall, width, depth + wall + flap), False),
            ("left wall", _rect(-wall, 0, 0, depth), False),
            ("right wall", _rect(width, 0, width + wall, depth), False)]
        seat.creases = [("seat / front", _seg(0, 0, width, 0)),
            ("front / bottom", _seg(0, -wall, width, -wall)),
            ("seat / back", _seg(0, depth, width, depth)),
            ("back / closure", _seg(0, depth + wall, width, depth + wall)),
            ("seat / left", _seg(0, 0, 0, depth)), ("seat / right", _seg(width, 0, width, depth))]
        for end, y0, y1 in (("front", -wall, 0), ("back", depth, depth + wall)):
            for side, x0, x1, hinge in (("left", -flap, 0, 0), ("right", width, width + flap, width)):
                seat.faces.append((end + " " + side + " glue flap", _rect(x0, y0, x1, y1), False))
                seat.creases.append((end + " " + side + " glue fold", _seg(hinge, y0, hinge, y1)))
        parts.append(seat)
    leg, foot = row["collar_leg_mm"], row["collar_foot_mm"]
    holder = Part(row["collar_part"], "ROW %d COLLAR — glue end feet to its solid seat" % row["row"],
                  hole_shape=record["hole_shape"])
    holder.faces = [("plate", _rect(0, 0, width, depth), False),
        ("left leg", _rect(-leg, 0, 0, depth), False),
        ("left foot", _rect(-leg-foot, 0, -leg, depth), False),
        ("right leg", _rect(width, 0, width + leg, depth), False),
        ("right foot", _rect(width + leg, 0, width + leg + foot, depth), False)]
    holder.creases = [("left foot / leg", _seg(-leg, 0, -leg, depth)),
        ("left leg / plate", _seg(0, 0, 0, depth)), ("plate / right leg", _seg(width, 0, width, depth)),
        ("right leg / foot", _seg(width + leg, 0, width + leg, depth))]
    holder.holes = [("opening %d" % hole["index"],
                     (hole["centre_mm"][0], hole["centre_mm"][1] - row["y0_mm"]), hole["size_mm"] / 2)
                    for hole in record["holes"] if hole["row"] == row["row"]]
    parts.append(holder)
    return parts


def _product_plate_hit(eye, point, data):
    """Intersect a ray with the actual perforated plate extruded through its board thickness."""
    material, z0, z1 = data
    dz = point[2] - eye[2]
    lo, hi = 1e-9, 1 - 1e-7
    if abs(dz) < 1e-15:
        if not z0 <= eye[2] <= z1:
            return False
    else:
        a, b = (z0 - eye[2]) / dz, (z1 - eye[2]) / dz
        lo, hi = max(lo, min(a, b)), min(hi, max(a, b))
    if hi - lo <= 1e-9:
        return False
    ends = [(eye[0] + (point[0] - eye[0]) * s, eye[1] + (point[1] - eye[1]) * s) for s in (lo, hi)]
    if math.dist(*ends) < 1e-9:
        return material.contains(Point(ends[0]))
    return material.intersection(LineString(ends)).length > 1e-9


def _product_first_hit(eye, point, occluders, skip):
    for name, kind, data in occluders:
        if name == skip:
            continue
        hit = _product_plate_hit(eye, point, data) if kind == "plate" else _first_hit(eye, point, [(name, kind, data)], skip)
        if hit:
            return name
    return None


def product_tray_platform_fronts(record):
    """Orthographic front faces of the actual, unprinted row support parts.

    Boxes are x/y-down millimetres from the stand's upper-left corner. Depth is
    the front-face y plane in the same physical coordinates as product centres;
    render deeper objects first, then these faces and the front tray panel.
    """
    v, g = record["inputs"], record["geometry"]
    if "row_platforms" not in g:
        return []
    H, t = v["height_mm"], v["board_mm"]
    x0 = t + g["holder_inset_mm"]
    x1 = x0 + g["holder_mm"][0]
    faces = []
    for row in g["row_platforms"]:
        seat, top = row["seat_z_mm"], row["collar_top_z_mm"]
        depth = t + g["holder_inset_mm"] + row["y0_mm"]
        def face(kind, part, left, bottom, right, upper):
            faces.append({"id": "row_%d_%s" % (row["row"], kind), "kind": kind,
                          "part": part, "row": row["row"], "depth_mm": depth,
                          "box_mm": [left, H - upper, right, H - bottom],
                          "material": "unprinted board", "printed": False})
        if row["seat_part"]:
            # The closed front silhouette includes its top and bottom board edges.
            face("support_front", row["seat_part"], x0, t, x1, seat)
        face("collar_front_edge", row["collar_part"], x0, top - t, x1, top)
        for side, left, right in (("left", x0, x0 + t), ("right", x1 - t, x1)):
            face("collar_%s_leg" % side, row["collar_part"], left, seat + t, right, top - t)
        foot = row["collar_foot_mm"]
        for side, left, right in (("left", x0, x0 + foot), ("right", x1 - foot, x1)):
            face("collar_%s_foot" % side, row["collar_part"], left, seat, right, seat + t)
    return faces


def product_tray_enclosure_elevations(record):
    """Expose the existing folded tray walls without inventing perspective.

    The back panel fills the space between the header and floor. A true front
    view shows only the board-thickness silhouettes of the sloping side walls;
    their full, measured slopes belong in the separate side elevation.
    Materials and print finishes are deliberately not assigned by geometry.
    """
    v, g = record["inputs"], record["geometry"]
    W, D, H, t = (v[key] for key in ("width_mm", "depth_mm", "height_mm", "board_mm"))
    header = g["header_height_mm"]
    front, back = (g[key] + t for key in ("front_panel_height_mm", "back_panel_height_mm"))
    faces = []
    for kind, name, depth, bounds, projection in (
            ("back_interior", "back panel", D - t, [t, header, W - t, H - t], "planar front face"),
            ("left_side_edge", "left side", 0., [0., header, t, H - t], "board-thickness orthographic silhouette"),
            ("right_side_edge", "right side", 0., [W - t, header, W, H - t], "board-thickness orthographic silhouette")):
        left, top, right, bottom = bounds
        faces.append({"id": "tray_" + kind, "kind": kind, "part": "tray", "face": name,
                      "depth_mm": depth, "box_mm": bounds, "projection": projection,
                      "polygon_mm": [[left, top], [right, top], [right, bottom], [left, bottom]]})
    side = {"width_mm": D, "height_mm": H,
            "coordinate_system": "Depth from front to back on x; height down from the stand top on y",
            "wall_polygon_mm": [[t, H - t], [t, H - front], [D - t, H - back], [D - t, H - t]],
            "front_wall_top_mm": H - front, "back_wall_top_mm": H - back,
            "board_mm": t, "source": "Existing tray side faces folded about the engine floor edges"}
    return {"front_faces": faces, "side_elevation": side,
            "projection_note": "True front elevation: side walls retain board thickness; their slope is shown only in the side elevation"}


#: the solver's sightline behaviour a stand record was solved under; a build whose stand predates it is solved again
#: ($0, round_files_gate.restand)
SIGHTLINE_REVISION = 'shape-check/2026-10-29'     # was 'inside-size/2026-10-29'; the shape check added
INSIDE_SIZE = ('Inside the owner\'s ruled size (2026-10-29): the stand\'s height and header kept; the rear rows raised '
               'and, where the header\'s safe area would be covered, the front row lowered, until every product\'s top '
               '25 mm band and the header\'s safe area are visible from the engine\'s eye')


def product_tray_raise_rear(record, *, keep_size=False):
    """Pass the unchanged 25 mm sightline test by raising the rear rows. Owner-selected (keep_size False): the height
    and header rise by the largest added rise. ``keep_size`` (the owner's ruling of 2026-10-29 on the stand's size):
    the height and header stay; the rear rows rise inside them, and when the rear products would then cover the
    header's safe area as the eye sees it, the front row is lowered — the highest front seat that lets both hold."""
    if record['inputs']['product_height_mm'] < 25:
        raise ValueError('A 25 mm visible top band needs a product at least 25 mm high')
    initial = product_tray_sightlines(record)
    original = [next(hole['seat_z_mm'] for hole in record['holes'] if hole['row'] == row)
                for row in range(1, record['layout']['rows'] + 1)]
    base_height, board = record['inputs']['height_mm'], record['inputs']['board_mm']
    def candidate(values):
        inputs = dict(record['inputs'], **record['layout'], hole_shape=record['hole_shape'],
                      top_edge=record['top_edge'], row_seat_z_mm=list(values),
                      height_mm=base_height if keep_size else base_height + max(a - b for a, b in zip(values, original)))
        return solve_product_tray(**inputs)

    def raise_rows(seats):
        """Rows 2… raised front to back, each by a bounded search, to the lowest 0.1 mm seat that passes."""
        seats = list(seats)
        current = candidate(seats) if seats != original else record
        for index in range(1, len(seats)):
            def passes(trial):
                return all(row['passed'] for row in product_tray_sightlines(trial)['products'] if row['row'] == index + 1)
            if passes(current):
                continue
            start = max(seats[index], 5 * board)
            low, high = start, start
            trial = list(seats)
            while True:
                trial[index] = high
                trial_record = candidate(trial)
                if passes(trial_record):
                    break
                low = high
                high += max(1., high - start)
                if high - original[index] > record['inputs']['product_height_mm']:
                    raise ValueError('The rear top band cannot be exposed within one product height of additional support')
            while high - low > .05:
                middle = (low + high) / 2
                trial[index] = middle
                if passes(candidate(trial)):
                    high = middle
                else:
                    low = middle
            seats[index] = math.ceil(high * 10) / 10
            current = candidate(seats)
            if not passes(current):
                raise ValueError('The rounded rear support does not pass the unchanged sightline check')
        return seats, current

    def holds(seats):
        """The rows raised from this front seat, or None where the seats cannot be built or the header is covered."""
        try:
            raised, current = raise_rows(seats)
        except ValueError:
            return None
        return (raised, current) if not keep_size or product_tray_sightlines(current)['header_clear'] else None

    found = holds(original)
    if found is None and keep_size:
        # the front row lowered in 0.5 mm steps to the first seat that lets both hold (down to the floor), then refined
        # back up to the highest such seat at 0.1 mm
        step, previous, seat = .5, original[0], original[0]
        while found is None and seat > board:
            previous, seat = seat, max(board, seat - step)
            found = holds([seat] + original[1:])
        if found is None:
            raise ValueError('Inside the ruled size no seats show every product\'s top band and the header\'s safe area')
        low, high = seat, previous
        while high - low > .1:
            middle = math.floor((low + high) / 2 * 10) / 10
            if middle <= low:
                break
            trial = holds([middle] + original[1:])
            if trial is None:
                high = middle
            else:
                low, found = middle, trial
    if found is None:
        raise ValueError('The existing 25 mm sightline check still has an occluded product')
    seats, current = found
    final = product_tray_sightlines(current)
    if not final['passed'] or (keep_size and not final['header_clear']):
        raise ValueError('The existing 25 mm sightline check still has an occluded product')
    current['authority']['rear_visibility'] = (INSIDE_SIZE if keep_size else
                                               'Explicit owner-selected rise until the existing 25 mm top-band check passes')
    return {'record': current, 'initial_sightlines': initial, 'final_sightlines': final,
            'original_seats_mm': original, 'final_seats_mm': seats,
            'added_rise_mm': [a - b for a, b in zip(seats, original)],
            'original_height_mm': base_height, 'final_height_mm': current['inputs']['height_mm'],
            'visible_band_mm': 25., 'seat_precision_mm': .1, 'keep_size': keep_size,
            'method': ('Raise rear rows front-to-back inside the ruled height; lower the front row only as far as the header\'s '
                       'safe area needs; bounded search using the unchanged engine eye and samples' if keep_size else
                       'Raise rear rows front-to-back; bounded search using the unchanged engine eye and samples; rebuild closed seats and raise the header by the largest added rise'),
            'allowed_difference': ('Row seats only: the height, header and footprint unchanged' if keep_size else
                                   'Rear platform rise and corresponding provisional back-wall height'),
            'physical_sample_required': True}


def product_tray_sightlines(record):
    """Report visibility at the engine's 500/350 mm eye; keep every pictured seat."""
    v, g = record["inputs"], record["geometry"]
    W, D, H, t = (v[key] for key in ("width_mm", "depth_mm", "height_mm", "board_mm"))
    pw, pd, ph = (v[key] for key in ("product_width_mm", "product_depth_mm", "product_height_mm"))
    eye = (W / 2, -500.0, 350.0)
    back = g["back_panel_height_mm"] + t
    front = g["front_panel_height_mm"] + t
    occ = [("front wall", "box", _halfspaces_box(0, W, 0, t, 0, front)),
           ("back wall and header", "box", _halfspaces_box(0, W, D - t, D, 0, H))]
    slope = (back - front) / D
    for name, x0, x1 in (("left wall", 0, t), ("right wall", W - t, W)):
        occ.append((name, "box", _halfspaces_box(x0, x1, 0, D, 0, back) + [((0, -slope, 1), front)]))
    for row in g.get("row_platforms", []):
        x0, y0 = t + g["holder_inset_mm"], t + g["holder_inset_mm"] + row["y0_mm"]
        x1, y1 = x0 + g["holder_mm"][0], y0 + row["depth_mm"]
        seat, top = row["seat_z_mm"], row["collar_top_z_mm"]
        if seat > t:
            occ.append(("row %d seat" % row["row"], "box", _halfspaces_box(x0, x1, y0, y1, t, seat)))
        holes = []
        for hole in record["holes"]:
            if hole["row"] != row["row"]:
                continue
            x, y = hole["product_centre_mm"]
            half = hole["size_mm"] / 2
            holes.append(_rect(x-half, y-half, x+half, y+half) if record["hole_shape"] == "square"
                         else Point(x, y).buffer(half, 64))
        material = _rect(x0, y0, x1, y1).difference(unary_union(holes))
        occ.append(("row %d collar" % row["row"], "plate", (material, top-t, top)))
        for side, a, b in (("left", x0, x0+t), ("right", x1-t, x1)):
            occ.append(("row %d %s collar leg" % (row["row"], side), "box",
                        _halfspaces_box(a, b, y0, y1, seat+t, top-t)))
        for side, a, b in (("left", x0, x0+row["collar_foot_mm"]), ("right", x1-row["collar_foot_mm"], x1)):
            occ.append(("row %d %s collar foot" % (row["row"], side), "box",
                        _halfspaces_box(a, b, y0, y1, seat, seat+t)))
    for hole in record["holes"]:
        x, y = hole["product_centre_mm"]
        seat = hole["seat_z_mm"]
        shape = ("cyl", (x, y, pw / 2, seat, seat + ph)) if record["hole_shape"] == "circle" else (
            "box", _halfspaces_box(x - pw / 2, x + pw / 2, y - pd / 2, y + pd / 2, seat, seat + ph))
        occ.append(("product %d" % hole["index"], *shape))
    rows = []
    band = min(25.0, ph)
    samples = max(1, math.ceil(band))
    for hole in record["holes"]:
        x, y = hole["product_centre_mm"]
        name = "product %d" % hole["index"]
        seat = hole["seat_z_mm"]
        results = [_product_first_hit(eye, (x, y - pd / 2, seat + ph - band + band * index / samples), occ, name)
                   for index in range(samples + 1)]
        visible = sum(hit is None for hit in results)
        rows.append({"index": hole["index"], "row": hole["row"], "column": hole["column"],
                     "seat_z_mm": hole["seat_z_mm"], "visible_fraction": visible / len(results),
                     "visible_samples": visible, "samples": len(results), "passed": visible == len(results),
                     "front_elevation_exposed_top_mm": max(0, min(ph, seat + ph - max(
                         [other["seat_z_mm"] + ph for other in record["holes"]
                          if other["column"] == hole["column"] and other["row"] < hole["row"]] or [seat]))),
                     "occluders": sorted({hit for hit in results if hit is not None})})
    header = product_tray_header_cover(record, eye)
    raised = (record.get("authority") or {}).get("rear_visibility")
    return {"schema": "counter_tray_header/product-grid-sightlines-1", "eye_mm": list(eye),
            "method": "3-D segments to each product's front centreline, sampled at most 1 mm apart in its top band",
            "visible_band_mm": band, "products": rows, "passed": all(row["passed"] for row in rows),
            "header": header, "header_clear": header["clear"],
            "design_gate": False, "seats_changed": bool(raised),
            "includes_measured_row_supports": bool(g.get("row_platforms")),
            "note": ("Measured report for the designer's eye. " + (raised + "." if raised else
                     "Covered bands do not change the picked row heights."))}


def product_tray_header_cover(record, eye):
    """How far up the header's printed face the products reach, seen from the engine's eye: each product's top front
    and back edges projected onto the back wall's face, measured above the header's lower edge. Within SAFE_MM the
    header's safe area (where its type and logo sit) is clear."""
    v = record["inputs"]
    wall, lower = v["depth_mm"] - v["board_mm"], v["height_mm"] - v["header_height_mm"]
    covered = 0.0
    for hole in record["holes"]:
        y, top = hole["product_centre_mm"][1], hole["seat_z_mm"] + v["product_height_mm"]
        for edge in (y - v["product_depth_mm"] / 2, y + v["product_depth_mm"] / 2):
            covered = max(covered, eye[2] + (wall - eye[1]) / (edge - eye[1]) * (top - eye[2]) - lower)
    return {"lower_edge_z_mm": lower, "covered_mm": round(covered, 4), "safe_mm": SAFE_MM,
            "clear": covered <= SAFE_MM + 1e-9,
            "method": "each product's top edges projected from the eye onto the back wall's face (y = depth - board)"}


def build_product_tray_die(record):
    """Draw the generic branch with the same Part/Die geometry and exporters."""
    g = record["geometry"]
    fw, fd = g["floor_mm"]
    front, back, header = (g[key] for key in ("front_panel_height_mm", "back_panel_height_mm", "header_height_mm"))
    flap = g["corner_glue_flap_mm"]
    tray = Part("tray", "TRAY — fold walls; glue corner flaps inside")
    tray.faces = [("floor", _rect(0, 0, fw, fd), False),
                  ("front panel", _rect(0, -front, fw, 0), True),
                  ("left side", Polygon([(0, 0), (0, fd), (-back, fd), (-front, 0)]), True),
                  ("right side", Polygon([(fw, 0), (fw + front, 0), (fw + back, fd), (fw, fd)]), True),
                  ("back panel", _rect(0, fd, fw, fd + back), True),
                  ("header front", _rect(0, fd + back, fw, fd + back + header), True),
                  ("header back", _rect(0, fd + back + header, fw, fd + back + 2 * header), False)]
    tray.creases = [("floor / front", _seg(0, 0, fw, 0)), ("floor / back", _seg(0, fd, fw, fd)),
                    ("floor / left", _seg(0, 0, 0, fd)), ("floor / right", _seg(fw, 0, fw, fd)),
                    ("back / header", _seg(0, fd + back, fw, fd + back)),
                    ("header fold", _seg(0, fd + back + header, fw, fd + back + header))]
    for end, y0, y1 in (("front", -front, 0), ("back", fd, fd + back)):
        for side_name, x0, x1, hinge in (("left", -flap, 0, 0), ("right", fw, fw + flap, fw)):
            tray.faces.append((end + " " + side_name + " glue flap", _rect(x0, y0, x1, y1), False))
            tray.creases.append((end + " " + side_name + " glue fold", _seg(hinge, y0, hinge, y1)))
    pw, pd = g["holder_mm"]
    leg, foot = g["holder_height_mm"], g["holder_foot_flap_mm"]
    holder = Part("holder", "HOLDER — fold legs down; glue feet to floor", hole_shape=record["hole_shape"])
    holder.faces = [("front foot", _rect(0, 0, pw, foot), False),
                    ("front leg", _rect(0, foot, pw, foot + leg), False),
                    ("plate", _rect(0, foot + leg, pw, foot + leg + pd), True),
                    ("back leg", _rect(0, foot + leg + pd, pw, foot + 2 * leg + pd), False),
                    ("back foot", _rect(0, foot + 2 * leg + pd, pw, 2 * foot + 2 * leg + pd), False)]
    holder.creases = [("holder fold %d" % i, _seg(0, y, pw, y)) for i, y in enumerate(
        (foot, foot + leg, foot + leg + pd, foot + 2 * leg + pd), 1)]
    holder.holes = [("opening %d" % hole["index"],
                     (hole["centre_mm"][0], foot + leg + hole["centre_mm"][1]), hole["size_mm"] / 2)
                    for hole in record["holes"]]
    raw_parts = [tray, holder]
    if g.get("row_platforms"):
        raw_parts = [tray] + [part for row in g["row_platforms"] for part in _product_row_parts(record, row)]
    placed, x = [], SHEET_MARGIN_MM
    row_y, row_bottom = SHEET_MARGIN_MM + LABEL_MM + 4, 0.0
    packing_width = tray.outline().bounds[2] - tray.outline().bounds[0]
    for part in raw_parts:
        minx, miny, maxx, maxy = part.outline().bounds
        if g.get("row_platforms") and x > SHEET_MARGIN_MM and x + maxx - minx > SHEET_MARGIN_MM + packing_width:
            x, row_y = SHEET_MARGIN_MM, row_bottom + PART_GAP_MM + LABEL_MM + 4
        moved = part.moved(x - minx, row_y - miny)
        placed.append(moved)
        row_bottom = max(row_bottom, moved.outline().bounds[3])
        x = moved.outline().bounds[2] + PART_GAP_MM
    bounds = unary_union([part.outline() for part in placed]).bounds
    width, height = math.ceil(bounds[2] + SHEET_MARGIN_MM), math.ceil(bounds[3] + SHEET_MARGIN_MM + 20)
    labels = [(part.label, (part.outline().bounds[0], part.outline().bounds[1] - DIE_BLEED_MM - 3), LABEL_MM)
              for part in placed]
    return Die(placed, width, height, labels, (SHEET_MARGIN_MM, height - 18.0, 50.0),
               "Single-product counter tray — provisional — flat die at 100 %")


# --- the production die (1.0) -----------------------------------------------------------------------------------------


#: board presets: caliper, the fold compensation (one caliper, measured on the references), the narrowest panel
#: between two parallel creases (three calipers, at least 3 mm), the grain the converter is asked to run
BOARDS = {
    "e_flute": {"name": "E-flute corrugated, 1.5 mm", "caliper_mm": 1.5, "fold_allowance_mm": 1.5,
                "grain": "flutes parallel to the back panel's height (column strength under the header)"},
    "sbs_1_5": {"name": "Solid bleached sulphate board, 1.5 mm", "caliper_mm": 1.5, "fold_allowance_mm": 1.5,
                "grain": "grain parallel to the back panel's height"},
    "white_card_0_5": {"name": "White card 350 g/m², 0.5 mm (the references' white-card displays)", "caliper_mm": 0.5,
                       "fold_allowance_mm": 0.5, "grain": "grain parallel to the back panel's height"},
}
#: what the product stands in: its opening shape by default
KINDS = {"bottle": "square", "jar": "circle", "stick": "circle", "palette": "oblong"}
RULES = {
    "glue_free_crease_mm": 2.0,        # glue stops this far from its hinge crease (G4)
    "glue_free_edge_mm": 1.5,          # and this far inside the flap's cut edges
    "lock_play_mm": 0.3,               # a lock slot is the board plus this
    "slot_end_play_mm": 0.3,           # and the tab's width plus this at each end
    "crease_end_clear_mm": 3.0,        # no cut within 3 mm of a crease end, unless the crease ends on it
    "min_panel_calipers": 3.0,         # narrowest panel between parallel creases
    "tab_radius_mm": 3.0,              # a tab's free corners rounded (K5)
    "header_tab_mm": 10.0,             # the header's lock tab, fold to tip
    "insert_tab_w_mm": 12.0,           # an insert tab's width
    "insert_tab_out_mm": 1.5,          # past the side wall's outside
    "retention_mm": 0.6,               # a tongue reaches this far into the product's face
    "tongue_w_mm": 6.0,
    "max_lean_deg": 3.0,               # the most any lock may let its part lean (Day 12's keys allowed 25.5°)
}
STANDARD_SHEETS = {  # mm, landscape; the converter confirms what it stocks
    "e_flute": [(1200, 800), (1400, 1000), (1600, 1200)],
    "sbs_1_5": [(1020, 720), (1100, 800), (1200, 900)],
    "white_card_0_5": [(1000, 700), (1020, 720), (1100, 800)],
}


def solve(*, product="bottle", board="e_flute", hole_shape=None, product_grid=None, **grid):
    """The production record: the product-grid branch's solved grid, the board preset, and the 1.0 construction."""
    grid = dict(product_grid or {}, **grid)
    if product not in KINDS:
        raise ValueError("The product must be one of %s" % ", ".join(KINDS))
    if board not in BOARDS:
        raise ValueError("The board must be one of %s" % ", ".join(BOARDS))
    shape = hole_shape or grid.pop("hole_shape", None) or KINDS[product]
    grid.pop("board_mm", None)
    preset = BOARDS[board]
    t = preset["caliper_mm"]
    base = solve_product_tray(**dict(grid, board_mm=t, hole_shape="circle" if shape == "circle" else "square"))
    g = base["geometry"]
    v = base["inputs"]
    # 1.0's own rules over the grid's: the insert's plate at 30 % of the product (6 mm and four calipers at least,
    # under the front lip and 60 % of the product where those allow), so its lock holds the lean under 3°; a collar's
    # legs three calipers wide, so their creases cannot crack (the grid's two calipers fail the trade rule)
    if g.get("row_platforms"):
        for row in g["row_platforms"]:
            row["collar_leg_mm"] = 3 * t
    else:
        low = max(6.0, 4 * t)
        high = max(low, min(g["front_panel_height_mm"], v["product_height_mm"] * 0.6))
        g["holder_height_mm"] = _r(min(max(v["product_height_mm"] * 0.3, low), high))
    fw, fd = g["floor_mm"]
    flap = g["corner_glue_flap_mm"]
    header = g["header_height_mm"]
    if header - t <= RULES["header_tab_mm"]:
        raise ValueError("The header is too short to double over and lock")
    pw_product, pd_product = v["product_width_mm"], v["product_depth_mm"]
    if shape == "oblong":
        opening = [pw_product + v["clearance_mm"], pd_product + v["clearance_mm"]]
    else:
        side = max(pw_product, pd_product) + v["clearance_mm"]
        opening = [side, side]
    insert_tabs = []
    if not g.get("row_platforms"):
        lo, hi = flap + RULES["crease_end_clear_mm"] + 0.5, fd - flap - RULES["crease_end_clear_mm"] - 0.5
        width = RULES["insert_tab_w_mm"]
        fit = g["holder_inset_mm"]
        if hi - lo >= 2 * width + 6:
            centres = [lo + width / 2 + 2, hi - width / 2 - 2]
        elif hi - lo >= width + 1:
            centres = [(lo + hi) / 2]
        else:
            centres = []
        insert_tabs = [{"y_mm": _r(y), "width_mm": width, "length_mm": _r(fit + t + RULES["insert_tab_out_mm"]),
                        "z_mm": _r(g["holder_height_mm"] - t / 2)} for y in centres]
    compensation = [
        {"fold": "floor / walls", "allowance_mm": t, "rule": "the walls stand outside the floor: outer = floor + 2 × caliper"},
        {"fold": "header fold (180°)", "allowance_mm": t, "rule": "the folded leaf is one caliper shorter so it closes flat"},
        {"fold": "header lock fold", "allowance_mm": RULES["lock_play_mm"], "rule": "slot = caliper + play"},
        {"fold": "glue folds", "allowance_mm": 0.0, "rule": "each flap lies on its wall's inside face; tapered G/3 at both ends"},
        {"fold": "holder legs", "allowance_mm": t, "rule": "each leg one caliper shorter: the plate's top at the leg height"},
        {"fold": "holder feet", "allowance_mm": 0.0, "rule": "the foot lies on the floor; its thickness is in the leg allowance"},
    ]
    record = dict(base)
    record.update({
        "schema": SCHEMA,
        "template": {"id": TEMPLATE_ID, "version": VERSION, "branch": "single_product_grid_production",
                     "provisional": False, "production_ready": True},
        "product": product, "board": dict(preset, preset=board), "hole_shape": shape,
        "production": {"opening_mm": [_r(opening[0]), _r(opening[1])], "insert_tabs": insert_tabs,
                       "header_folded_leaf_mm": _r(header - t), "compensation": compensation, "rules": dict(RULES),
                       "grain": preset["grain"], "dust_flaps": "none: an open tray has no tuck end to close against "
                       "dust, and none of the house's display dies carries one (the references)"},
        "provisional": False})
    record["assembly"] = (
        "Fold the walls up and glue each corner flap inside its side wall (glue zones marked). Fold the header over "
        "the back panel's top, shopper side, and push its lock tab through the slot at the back panel's top. "
        + ("Fold the holder's legs down, glue its feet to the floor, and spring its plate's tabs into the side walls' "
           "slots." if insert_tabs else
           "Fold and glue each row seat, then each collar onto its seat. ")
        + " Stand each product in its opening; the tongues hold it.")
    return record


def _tongues(centre, opening, product, shape):
    """The retention tongues of one opening: tabs left in the cut, reaching RULES['retention_mm'] into the product."""
    cx, cy = centre
    reach = RULES["retention_mm"]
    out = []
    if shape == "circle":
        radius, product_r = opening[0] / 2, max(product) / 2
        depth = radius - product_r + reach
        width = min(RULES["tongue_w_mm"], radius)
        for angle in (90, 210, 330):
            tongue = box(product_r - reach, -width / 2, radius + 1.0, width / 2)
            out.append(translate(rotate(tongue, angle, origin=(0, 0)), cx, cy))
        return out, depth
    half_w, half_d = opening[0] / 2, opening[1] / 2
    depth = half_w - product[0] / 2 + reach
    width = min(RULES["tongue_w_mm"], opening[1] / 3)
    for sign in (-1, 1):
        inner = cx + sign * (product[0] / 2 - reach)
        outer = cx + sign * (half_w + 1.0)
        out.append(box(min(inner, outer), cy - width / 2, max(inner, outer), cy + width / 2))
    return out, depth


def _opening(centre, record):
    shape = record["hole_shape"]
    opening = record["production"]["opening_mm"]
    product = [record["inputs"]["product_width_mm"], record["inputs"]["product_depth_mm"]]
    cx, cy = centre
    base = (Point(cx, cy).buffer(opening[0] / 2, 64) if shape == "circle"
            else box(cx - opening[0] / 2, cy - opening[1] / 2, cx + opening[0] / 2, cy + opening[1] / 2))
    tongues, depth = _tongues(centre, opening, product, shape)
    return base.difference(unary_union(tongues)), depth


def _tab(x0, y0, x1, y1, root):
    """A lock tab over the box (x0, y0)–(x1, y1), its root on side ``root`` ('top', 'bottom', 'left' or 'right') and
    its free corners rounded (K5)."""
    r = min(RULES["tab_radius_mm"], (x1 - x0) / 4, (y1 - y0) / 4)
    rounded = box(x0, y0, x1, y1).buffer(-r, join_style=1).buffer(r, join_style=1)
    strip = {"top": box(x0, y0, x1, y0 + r), "bottom": box(x0, y1 - r, x1, y1),
             "left": box(x0, y0, x0 + r, y1), "right": box(x1 - r, y0, x1, y1)}[root]
    return unary_union([rounded, strip])


def _taper(hinge_x, y0, y1, depth, side):
    """A glue flap hinged on x = hinge_x from y0 to y1, ``depth`` wide toward ``side`` (-1 left, 1 right), its ends
    tapered by a third of its depth (G3)."""
    x = hinge_x + side * depth
    cut = depth / 3
    return Polygon([(hinge_x, y0), (x, y0 + cut), (x, y1 - cut), (hinge_x, y1)])


# --- the shape check (the owner's goal of 2026-10-29: match the pick) -------------------------------------------------
#: the header outlines the shape check knows, each a function of the leaf's unit box (x right, y down, 0..1)
HEADER_SHAPES = ('square', 'rounded', 'quadrant', 'quadrant_left', 'arched')
#: an outline is read only from a picture polygon that overlaps its best shape at least this well
HEADER_IOU_MIN = 0.9
CURVE_SAMPLES = 64


def header_curve(shape, params, n=CURVE_SAMPLES):
    """The header's top boundary in the leaf's unit box: (x, depth) pairs from x = 0 to 1, depth below the top
    (0 = at the top edge). square: none; rounded: both top corners with radius r (of the height); quadrant: flat to
    `flat`, then a quarter-ellipse down to the lower right corner; quadrant_left: its mirror; arched: a half-ellipse."""
    xs = [i / n for i in range(n + 1)]
    if shape == 'square':
        return [(x, 0.0) for x in (0.0, 1.0)]
    if shape == 'quadrant':
        a = params['flat']
        return [(x, 0.0 if x <= a else 1 - math.sqrt(max(0.0, 1 - ((x - a) / (1 - a)) ** 2))) for x in xs]
    if shape == 'quadrant_left':
        return [(x, d) for x, d in [(1 - x, d) for x, d in header_curve('quadrant', params, n)][::-1]]
    if shape == 'arched':
        return [(x, 1 - math.sqrt(max(0.0, 1 - (2 * x - 1) ** 2))) for x in xs]
    r, aspect = params['r'], params.get('aspect', 1.0)       # r of the height; aspect = width / height
    rx = r / aspect
    out = []
    for x in xs:
        if x < rx:
            d = r - math.sqrt(max(0.0, r * r - ((rx - x) * aspect) ** 2))
        elif x > 1 - rx:
            d = r - math.sqrt(max(0.0, r * r - ((x - (1 - rx)) * aspect) ** 2))
        else:
            d = 0.0
        out.append((x, d))
    return out


def _unit_header(shape, params):
    curve = header_curve(shape, params)
    return Polygon([(0, 1)] + [(x, d) for x, d in curve] + [(1, 1)]).buffer(0)


def read_header_outline(inspection):
    """The picked picture's header outline, from its reading (panels.stand_header.print_polygon_px within its
    crop): the best of HEADER_SHAPES by overlap, its parameters searched on a grid; None when the reading gives none."""
    panel = ((inspection or {}).get('panels') or {}).get('stand_header') or {}
    if 'print_polygon_px' not in panel or 'crop_px' not in panel:
        return None
    x0, y0, x1, y1 = panel['crop_px']
    seen = Polygon([((x - x0) / (x1 - x0), (y - y0) / (y1 - y0)) for x, y in panel['print_polygon_px']]).buffer(0)
    if seen.is_empty or seen.area <= 0:
        return None
    aspect = (x1 - x0) / max(y1 - y0, 1e-9)
    candidates = [('square', {})] + [('rounded', {'r': r / 20, 'aspect': aspect}) for r in range(1, 11)] + \
        [(shape, {'flat': a / 20}) for shape in ('quadrant', 'quadrant_left') for a in range(0, 13)] + [('arched', {})]
    scored = []
    for shape, params in candidates:
        unit = _unit_header(shape, params)
        scored.append((seen.intersection(unit).area / seen.union(unit).area, shape, params))
    best = {}
    for iou, shape, params in scored:
        if shape not in best or iou > best[shape][0]:
            best[shape] = (iou, params)
    iou, shape, params = max((v[0], k, v[1]) for k, v in best.items())
    return {'shape': shape, 'params': params, 'iou': round(iou, 4),
            'scores': {k: round(v[0], 4) for k, v in sorted(best.items())}, 'source': 'panels.stand_header.print_polygon_px'}


def read_grounds(inspection, picture):
    """The ground colour of every printed panel the reading crops (the stand's board on its front strip, the header's
    ground), from the picked picture: the largest colour cluster of the crop that is not the photograph's light
    backdrop. The board's ground is the front strip's. {} without a picture."""
    import numpy as np
    from PIL import Image
    if picture is None:
        return {}
    import cv2
    with Image.open(picture) as image:
        rgb = np.asarray(image.convert('RGB'))
    out = {}
    for key, name in (('stand_base', 'board'), ('stand_header', 'header')):
        panel = ((inspection or {}).get('panels') or {}).get(key) or {}
        if 'crop_px' not in panel:
            continue
        x0, y0, x1, y1 = panel['crop_px']
        pixels = rgb[y0:y1, x0:x1].reshape(-1, 3).astype(np.float32)
        pixels = pixels[pixels.min(axis=1) < 225]                     # the light backdrop left out
        if len(pixels) < 50:
            continue
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
        _c, labels, centres = cv2.kmeans(pixels, 4, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
        counts = np.bincount(labels.ravel(), minlength=4)
        r, g, b = (int(round(v)) for v in centres[int(np.argmax(counts))])
        out[name] = {'hex': '#%02X%02X%02X' % (r, g, b), 'share': round(float(counts.max() / counts.sum()), 3),
                     'panel': key}
    return out


def header_polygons(fw, top, header, folded, outline):
    """The doubled header cut to the picture's outline: the header back rises from the back panel's top, the header
    front folds down over it at the header fold, so both are cut to the same curve, mirrored about the fold; the fold
    keeps only the straight part of the top edge (a fold cannot follow a curve). Returns (back, front, fold segment)."""
    fold = top + header
    curve = header_curve(outline['shape'], outline['params'])
    back = Polygon([(0, top)] + [(x * fw, fold - d * header) for x, d in curve] + [(fw, top)]).buffer(0)
    front = Polygon([(0, fold + folded)] + [(x * fw, fold + d * folded) for x, d in curve] + [(fw, fold + folded)]).buffer(0)
    straight = [x for x, d in curve if d <= 1e-9]
    # the fold: the longest run of the top edge left straight
    runs, run = [], []
    for x, d in curve:
        if d <= 1e-9:
            run.append(x)
        elif run:
            runs.append(run); run = []
    if run:
        runs.append(run)
    if not straight or not runs:
        raise ValueError('The header outline leaves no straight edge to fold the doubled header on')
    longest = max(runs, key=lambda r: r[-1] - r[0])
    if (longest[-1] - longest[0]) * fw < 10.0:
        raise ValueError('The header outline leaves less than 10 mm of straight edge to fold the doubled header on')
    return back, front, _seg(longest[0] * fw, fold, longest[-1] * fw, fold)


def build_die(record):
    """The production flat die: the tray, then the holder (or the row seats and collars), on one sheet."""
    if record.get("schema") == TEMPLATE_SCHEMA:
        from . import stand_templates
        return stand_templates.build_die(record)
    if record.get("schema") == PRODUCT_GRID_SCHEMA:          # an older stand (0.1's grid), drawn as it was
        return build_product_tray_die(record)
    if record.get("schema") != SCHEMA:
        raise ValueError("Not a counter display 1.0 record")
    g, v, p = record["geometry"], record["inputs"], record["production"]
    t = v["board_mm"]
    fw, fd = g["floor_mm"]
    front, back, header = (g[key] for key in ("front_panel_height_mm", "back_panel_height_mm", "header_height_mm"))
    folded = p["header_folded_leaf_mm"]
    flap = g["corner_glue_flap_mm"]
    tray = Part("tray", "TRAY — fold walls; glue corner flaps inside; double the header and lock it")
    top = fd + back                                 # the back panel's top: the header continues the same board
    tray.faces = [("floor", _rect(0, 0, fw, fd), False),
                  ("front panel", _rect(0, -front, fw, 0), True),
                  ("left side", Polygon([(0, 0), (0, fd), (-back, fd), (-front, 0)]), True),
                  ("right side", Polygon([(fw, 0), (fw + front, 0), (fw + back, fd), (fw, fd)]), True),
                  ("back panel", _rect(0, fd, fw, top), True),
                  ("header back", _rect(0, top, fw, top + header), True),
                  ("header front", _rect(0, top + header, fw, top + header + folded), True)]
    outline = g.get("header_outline")
    fold_seg = _seg(0, top + header, fw, top + header)
    if outline and outline["shape"] != "square":
        # the shape check (2026-10-29): the doubled header cut to the picked picture's outline
        header_back, header_front, fold_seg = header_polygons(fw, top, header, folded, outline)
        tray.faces[-2:] = [("header back", header_back, True), ("header front", header_front, True)]
    tab_w = max(20.0, fw * 0.5)
    tx0, tx1 = (fw - tab_w) / 2, (fw + tab_w) / 2
    tab_root = top + header + folded
    tray.faces.append(("header lock tab", _tab(tx0, tab_root, tx1, tab_root + RULES["header_tab_mm"], "top"), False))
    play, end = RULES["lock_play_mm"], RULES["slot_end_play_mm"]
    # folded down, the leaf's free edge lands one caliper above the back panel's top (the wrap takes the other): the
    # tab, one caliper thick, bends there and passes back through a slot spanning that band, plus play
    tray.slots.append({"id": "header lock slot", "polygon": _rect(tx0 - end, top - play / 2, tx1 + end,
                                                                      top + t + play / 2),
                       "length_mm": tab_w + 2 * end, "width_mm": t + play, "on": "the back panel's top",
                       "lands": [top, top + t]})
    tray.joins = [("back / header", _seg(0, top, fw, top))]
    tray.creases = [("floor / front", _seg(0, 0, fw, 0)), ("floor / back", _seg(0, fd, fw, fd)),
                    ("floor / left", _seg(0, 0, 0, fd)), ("floor / right", _seg(fw, 0, fw, fd)),
                    ("header fold", fold_seg),
                    ("header lock fold", _seg(tx0, tab_root, tx1, tab_root))]
    glue = []
    for end_name, y0, y1 in (("front", -front, 0), ("back", fd, top)):
        for side_name, hinge, side in (("left", 0, -1), ("right", fw, 1)):
            polygon = _taper(hinge, y0, y1, flap, side)
            tray.faces.append(("%s %s glue flap" % (end_name, side_name), polygon, False))
            crease = _seg(hinge, y0, hinge, y1)
            tray.creases.append(("%s %s glue fold" % (end_name, side_name), crease))
            glue.append(("%s %s glue flap" % (end_name, side_name),
                         polygon.buffer(-RULES["glue_free_edge_mm"], join_style=2).difference(
                             crease.buffer(RULES["glue_free_crease_mm"], cap_style=1))))
    for index, tab in enumerate(p["insert_tabs"], 1):
        z, y, w = tab["z_mm"], tab["y_mm"], tab["width_mm"]
        for side_name, sign, hinge in (("left", -1, 0), ("right", 1, fw)):
            x_mid = hinge + sign * z
            tray.slots.append({"id": "insert slot %s %d" % (side_name, index),
                               "polygon": _rect(x_mid - (t + play) / 2, y - w / 2 - end, x_mid + (t + play) / 2,
                                                   y + w / 2 + end),
                               "length_mm": w + 2 * end, "width_mm": t + play, "on": side_name + " side"})
    parts = [tray]
    if g.get("row_platforms"):
        for row in g["row_platforms"]:
            for part in _product_row_parts(dict(record, hole_shape="square" if record["hole_shape"] != "circle"
                                                   else "circle"), row):
                if part.holes:
                    part.slots = [{"id": name, "polygon": _opening(centre, record)[0], "kind": "opening"}
                                  for name, centre, _half in part.holes]
                    part.holes = []
                for name, polygon, _printed in part.faces:
                    if "glue flap" in name:
                        glue.append(("%s: %s" % (part.name, name),
                                     polygon.buffer(-RULES["glue_free_edge_mm"], join_style=2)))
                parts.append(part)
    else:
        parts.append(_holder(record, glue))
    placed, x = [], SHEET_MARGIN_MM
    row_y, row_bottom = SHEET_MARGIN_MM + LABEL_MM + 4, 0.0
    width = tray.outline().bounds[2] - tray.outline().bounds[0]
    moves = {}
    for part in parts:
        minx, miny, maxx, maxy = part.outline().bounds
        if x > SHEET_MARGIN_MM and x + maxx - minx > SHEET_MARGIN_MM + max(width, 400):
            x, row_y = SHEET_MARGIN_MM, row_bottom + PART_GAP_MM + LABEL_MM + 4
        moved = part.moved(x - minx, row_y - miny)
        moves[part.name] = (x - minx, row_y - miny)
        placed.append(moved)
        row_bottom = max(row_bottom, moved.outline().bounds[3])
        x = moved.outline().bounds[2] + PART_GAP_MM
    bounds = unary_union([part.outline() for part in placed]).bounds
    sheet_w, sheet_h = math.ceil(bounds[2] + SHEET_MARGIN_MM), math.ceil(bounds[3] + SHEET_MARGIN_MM + 20)
    labels = [(part.label, (part.outline().bounds[0], part.outline().bounds[1] - DIE_BLEED_MM - 3), LABEL_MM)
              for part in placed]
    die = Die(placed, sheet_w, sheet_h, labels, (SHEET_MARGIN_MM, sheet_h - 18.0, 50.0),
                 "Single-product counter display 1.0 — flat die at 100 %")
    owner_of = lambda name: name.split(":")[0] if ":" in name else ("holder" if name.startswith(("front foot", "back foot")) else "tray")  # noqa: E731
    die.glue = [(name, translate(polygon, *moves.get(owner_of(name), moves["tray"]))) for name, polygon in glue
                if not polygon.is_empty]
    return die


def _holder(record, glue):
    g, v, p = record["geometry"], record["inputs"], record["production"]
    t = v["board_mm"]
    pw, pd = g["holder_mm"]
    leg = g["holder_height_mm"] - t                  # one caliper shorter: the plate's top at the leg height
    foot = g["holder_foot_flap_mm"]
    fit = g["holder_inset_mm"]
    holder = Part("holder", "INSERT — fold legs down; glue feet to the floor; tabs into the side walls",
                     hole_shape="square" if record["hole_shape"] != "circle" else "circle")
    y_plate = foot + leg
    plate = _rect(0, y_plate, pw, y_plate + pd)
    tabs = []
    for tab in p["insert_tabs"]:
        y = y_plate + tab["y_mm"] - fit             # the tray's floor y, in the plate's own frame
        w, length = tab["width_mm"], tab["length_mm"]
        tabs.append(_tab(-length, y - w / 2, 0, y + w / 2, "right"))
        tabs.append(_tab(pw, y - w / 2, pw + length, y + w / 2, "left"))
    holder.faces = [("front foot", _rect(0, 0, pw, foot), False),
                    ("front leg", _rect(0, foot, pw, foot + leg), False),
                    ("plate", unary_union([plate] + tabs), True),
                    ("back leg", _rect(0, y_plate + pd, pw, y_plate + pd + leg), False),
                    ("back foot", _rect(0, y_plate + pd + leg, pw, y_plate + pd + leg + foot), False)]
    holder.creases = [("holder fold %d" % i, _seg(0, y, pw, y)) for i, y in enumerate(
        (foot, y_plate, y_plate + pd, y_plate + pd + leg), 1)]
    holder.slots = [{"id": "opening %d" % hole["index"], "kind": "opening",
                     "polygon": _opening((hole["centre_mm"][0], y_plate + hole["centre_mm"][1]), record)[0]}
                    for hole in record["holes"]]
    for name, y0, crease_y in (("front foot", 0, foot), ("back foot", y_plate + pd + leg, y_plate + pd + leg)):
        polygon = _rect(0, y0, pw, y0 + foot)
        glue.append((name, polygon.buffer(-RULES["glue_free_edge_mm"], join_style=2).difference(
            _seg(0, crease_y, pw, crease_y).buffer(RULES["glue_free_crease_mm"], cap_style=1))))
    return holder


def cut_polygons(part):
    """Every cut a part carries: its outline's rings, less its creases and joins, and its slots and openings."""
    lines = part.cut_lines()
    for slot in part.slots:
        lines.append(LineString(slot["polygon"].exterior.coords))
        lines.extend(LineString(ring.coords) for ring in slot["polygon"].interiors)
    return lines


def bleed_area(part):
    """Where ink may run: 3 mm past the part's printed faces (mitre), less its unprinted faces (all but the 1 mm by a
    crease, so a printed panel's colour reaches over its fold)."""
    printed = [face for _name, face, is_printed in part.faces if is_printed]
    if not printed:
        return Polygon()
    unprinted = unary_union([face for _name, face, is_printed in part.faces if not is_printed]).buffer(-1.0)
    return unary_union(printed).buffer(DIE_BLEED_MM, join_style=2).difference(unprinted)


def piece_of(die, name="tray"):
    """The part the design is painted and placed on. A template with its printed faces on more than one part (the slot-in
    header) gives them as one piece, each where it lies on the die's sheet."""
    wanted = [part for part in die.parts if any(printed for _n, _f, printed in part.faces)]
    if name != "tray" or len(wanted) <= 1 or not hasattr(die, "plan"):         # 1.0's insert plate is never painted
        return next(part for part in die.parts if part.name == name)
    piece = Part("tray", "the printed parts")
    for part in wanted:
        piece.faces += part.faces
        piece.creases += part.creases + part.half_cuts
        piece.joins += part.joins
        piece.slots += part.slots
        piece.perfs += part.perfs
    return piece


SAFE_MM = 3.0                         # each printed face's safe area: the face inset 3 mm (from the 0.1 sheets)


def safe_areas(part) -> list:
    """Each printed face's safe area: the face inset ``SAFE_MM``, less every hole of the part grown by ``SAFE_MM`` (the
    reviewer's MINOR 9: nothing safe runs over a hole), less every slit of the part (a cut that bounds no face: the
    lock tabs' relief slits run 2 mm into the side skins) and every slot lying in the face, each grown by ``SAFE_MM``
    (the sheet verifier's minor: the safe line stood 1.00 from the slits' ends). A slot cut out of its face (the back
    wall's lock-slot notches) is already in the face's own outline, so the inset clears it. Polygons, interiors kept."""
    from shapely.geometry import Point
    from shapely.ops import unary_union
    if part.hole_shape == "square":
        holes = unary_union([polygon.buffer(SAFE_MM, join_style=2)
                             for _name, polygon in part.hole_polygons()]) if part.holes else None
    else:
        holes = unary_union([Point(c).buffer(r + SAFE_MM, 16) for _n, c, r in part.holes]) if part.holes else None
    slits = [s for _n, s in part.slits]
    out = []
    for _n, face, printed in part.faces:
        if not printed:
            continue
        safe = face.buffer(-SAFE_MM, join_style=2)
        if holes is not None:
            safe = safe.difference(holes)
        cuts = [s.buffer(SAFE_MM, 16) for s in slits if s.distance(face) < SAFE_MM]
        cuts += [sl["polygon"].buffer(SAFE_MM, 16) for sl in part.slots if sl["polygon"].intersection(face).area > 1e-6]
        if cuts:
            safe = safe.difference(unary_union(cuts))
        out += [g for g in getattr(safe, "geoms", [safe]) if not g.is_empty and g.area > 1.0]
    return out


def layer_geometry(die):
    """The 1.0 die's layers (as the 0.1 sheets' layer_geometry drew them): cuts (slots and openings among them), creases,
    glue zones, and bleed only past printed faces (a 1 mm reach over a crease into an unprinted neighbour)."""
    out = {"cut": [], "holes": [], "crease": [], "perf": [], "half_cut": [], "glue": [], "safe": [], "bleed": [], "marks": []}
    for part in die.parts:
        out["cut"] += [list(line.coords) for line in cut_polygons(part)]
        out["crease"] += [list(crease.coords) for _name, crease in part.creases]
        out["perf"] += [list(line.coords) for _name, line in part.perfs]
        out["half_cut"] += [list(line.coords) for _name, line in part.half_cuts]
        bleed = bleed_area(part)
        for polygon in getattr(bleed, "geoms", [bleed]) if not bleed.is_empty else []:
            out["bleed"].append(list(polygon.exterior.coords))
            out["bleed"] += [list(ring.coords) for ring in polygon.interiors]
        for area in safe_areas(part):
            out["safe"].append(list(area.exterior.coords))
    for _name, polygon in getattr(die, "glue", []):
        for piece in getattr(polygon, "geoms", [polygon]):
            out["glue"].append(list(piece.exterior.coords))
    return out


# --- checks -----------------------------------------------------------------------------------------------------------

def _check(rows, key, measured, expected, ok, note=""):
    rows.append({"id": key, "measured": measured, "expected": expected, "ok": bool(ok), **({"note": note} if note else {})})


def trade_rules(record, die=None):
    """The die's own trade rules: every crease end on a cut or clear of every cut by 3 mm; no cut within 3 mm of a
    crease end; panels between parallel creases at least three calipers (and 3 mm); every lock slot the board plus play."""
    die = die or build_die(record)
    t = record["inputs"]["board_mm"]
    rows = []
    for part in die.parts:
        cuts = cut_polygons(part)
        ends_bad, near = [], []
        relief = getattr(part, "corner_relief", None)   # a tray's corner, where its walls' cuts and creases must meet
        for name, crease in part.creases:
            for end in (Point(crease.coords[0]), Point(crease.coords[-1])):
                if relief is not None and relief.contains(end):
                    continue
                # a cut the crease ends on is its own edge; every other cut keeps 3 mm from the end
                for line in cuts:
                    distance = line.distance(end)
                    if 0.01 < distance < RULES["crease_end_clear_mm"]:
                        near.append({"crease": name, "distance_mm": _r(distance)})
                if not part.outline().buffer(0.01).contains(end):
                    ends_bad.append(name)
        _check(rows, part.name + ": crease ends on a cut or 3 mm clear", near, [], not near)
        _check(rows, part.name + ": crease ends inside the part", ends_bad, [], not ends_bad)
        narrow = []
        creases = [(name, crease) for name, crease in part.creases]
        for i, (name_a, a) in enumerate(creases):
            for name_b, b in creases[i + 1:]:
                if _parallel(a, b) and _overlap(a, b) > 1.0:
                    gap = a.distance(b)
                    if 1e-6 < gap < max(RULES["min_panel_calipers"] * t, 3.0):
                        narrow.append({"creases": [name_a, name_b], "gap_mm": _r(gap)})
        _check(rows, part.name + ": no panel narrower than three calipers", narrow, [], not narrow)
        for slot in part.slots:
            if "width_mm" in slot:
                plies = slot.get("plies", 1)
                _check(rows, part.name + ": " + slot["id"] + " is the board plus play", slot["width_mm"],
                       plies * t + RULES["lock_play_mm"], abs(slot["width_mm"] - plies * t - RULES["lock_play_mm"]) <= 1e-6)
    return {"schema": "counter_display/trade-rules-1", "checks": rows, "passed": all(row["ok"] for row in rows)}


def _parallel(a, b):
    (ax0, ay0), (ax1, ay1) = a.coords[0], a.coords[-1]
    (bx0, by0), (bx1, by1) = b.coords[0], b.coords[-1]
    return abs((ax1 - ax0) * (by1 - by0) - (ay1 - ay0) * (bx1 - bx0)) < 1e-6 * max(a.length * b.length, 1)


def _overlap(a, b):
    """The length over which two parallel segments face each other."""
    (ax0, ay0), (ax1, ay1) = a.coords[0], a.coords[-1]
    ux, uy = (ax1 - ax0) / a.length, (ay1 - ay0) / a.length
    project = lambda x, y: (x - ax0) * ux + (y - ay0) * uy  # noqa: E731
    s = sorted([project(*b.coords[0]), project(*b.coords[-1])])
    return min(a.length, s[1]) - max(0.0, s[0])


def fold_check(record, die=None):
    """Fold the drawn die into the closed stand and check every flap lands: closed size, the header closing flat and
    its tab in its slot, each glue flap inside its wall, each insert tab in its wall slot and clear of the glue flaps,
    every opening's size, tongues and webs, the insert inside the walls."""
    die = die or build_die(record)
    g, v, p = record["geometry"], record["inputs"], record["production"]
    t = v["board_mm"]
    parts = {part.name: part for part in die.parts}
    tray = parts["tray"]
    face = lambda part, name: next(f for n, f, _ in part.faces if n == name)  # noqa: E731
    span = lambda geom, axis: geom.bounds[2 + axis] - geom.bounds[axis]  # noqa: E731
    rows = []
    floor = face(tray, "floor")
    for axis, key in ((0, "width_mm"), (1, "depth_mm")):
        _check(rows, "closed_" + key, _r(span(floor, axis) + 2 * t), v[key], abs(span(floor, axis) + 2 * t - v[key]) <= TOL_MM)
    height = t + span(face(tray, "back panel"), 1) + span(face(tray, "header back"), 1)
    _check(rows, "closed_height_mm", _r(height), v["height_mm"], abs(height - v["height_mm"]) <= TOL_MM)
    inner, outer = span(face(tray, "header front"), 1), span(face(tray, "header back"), 1)
    _check(rows, "header_closes_flat_mm", _r(outer - inner), t, abs(outer - inner - t) <= TOL_MM,
           "the folded leaf one caliper shorter than the leaf it covers")
    tab = face(tray, "header lock tab")
    slot = next(s for s in tray.slots if s["id"] == "header lock slot")["polygon"]
    _check(rows, "header_tab_fits_its_slot_mm", [_r(span(tab, 0)), _r(span(slot, 0))],
           "slot = tab + %.1f each end" % RULES["slot_end_play_mm"],
           abs(span(slot, 0) - span(tab, 0) - 2 * RULES["slot_end_play_mm"]) <= 1e-6 and
           slot.bounds[0] < tab.bounds[0] and slot.bounds[2] > tab.bounds[2])
    # folded 180° about the header fold, the leaf's free edge comes down to (fold − leaf) = the back's top + caliper;
    # the tab, one caliper thick, bends there: it occupies [top, top + caliper], which the slot must span
    fold_y = face(tray, "header back").bounds[3]
    lands = [fold_y - inner - t, fold_y - inner]
    slot_row = next(s for s in tray.slots if s["id"] == "header lock slot")
    _check(rows, "header_tab_lands_in_its_slot_mm", [_r(lands[0]), _r(lands[1])],
           [_r(slot.bounds[1]), _r(slot.bounds[3])],
           slot.bounds[1] <= lands[0] + 1e-6 and slot.bounds[3] >= lands[1] - 1e-6 and slot_row["width_mm"] >= t)
    for name, f, _printed in tray.faces:
        if "glue flap" not in name:
            continue
        wall = face(tray, "left side" if "left" in name else "right side")
        depth = span(f, 0)
        at_front = "front" in name
        wall_height = g["front_panel_height_mm"] if at_front else g["back_panel_height_mm"]
        _check(rows, name + " lands inside its wall", [_r(depth), _r(span(f, 1))],
               "≤ the wall's depth and its height there",
               depth <= span(floor, 1) / 4 + 1e-6 and span(f, 1) <= wall_height + 1e-6 and wall.area > 0)
    flap = g["corner_glue_flap_mm"]
    for tab_row in p["insert_tabs"]:
        y0, y1 = tab_row["y_mm"] - tab_row["width_mm"] / 2, tab_row["y_mm"] + tab_row["width_mm"] / 2
        _check(rows, "insert tab at y %.1f clear of the glue flaps" % tab_row["y_mm"], [_r(y0), _r(y1)],
               [_r(flap), _r(span(floor, 1) - flap)], y0 >= flap + 1 and y1 <= span(floor, 1) - flap - 1)
        _check(rows, "insert tab at y %.1f reaches through its wall" % tab_row["y_mm"], tab_row["length_mm"],
               g["holder_inset_mm"] + t, tab_row["length_mm"] >= g["holder_inset_mm"] + t + 1.0)
        slots = [s for s in tray.slots if s["id"].startswith("insert slot") and
                 abs((s["polygon"].bounds[1] + s["polygon"].bounds[3]) / 2 - (tray_origin(tray)[1] + tab_row["y_mm"])) < 1e-6]
        _check(rows, "insert tab at y %.1f has a slot in each wall" % tab_row["y_mm"], len(slots), 2, len(slots) == 2)
    holders = [part for name, part in parts.items() if name != "tray"]
    openings = [s for part in holders for s in part.slots if s.get("kind") == "opening"]
    _check(rows, "opening_count", len(openings), record["layout"]["count"], len(openings) == record["layout"]["count"])
    opening = p["opening_mm"]
    product = [v["product_width_mm"], v["product_depth_mm"]]
    nominal = [opening[0] - product[0], opening[1] - product[1]]
    _check(rows, "opening_clearance_mm", [_r(n) for n in nominal], v["clearance_mm"],
           all(abs(n - v["clearance_mm"]) <= TOL_MM for n in nominal) if record["hole_shape"] != "circle"
           else abs(opening[0] - max(product) - v["clearance_mm"]) <= TOL_MM)
    reach = RULES["retention_mm"]
    for part in holders:
        plate = face(part, "plate") if any(n == "plate" for n, _f, _p in part.faces) else None
        if plate is None:
            continue
        webs = [a["polygon"].distance(b["polygon"]) for i, a in enumerate(part.slots) for b in part.slots[i + 1:]
                if a.get("kind") == b.get("kind") == "opening"]
        _check(rows, part.name + ": opening web", _r(min(webs)) if webs else None, g["minimum_web_mm"] - 2 * reach,
               not webs or min(webs) >= g["minimum_web_mm"] - TOL_MM - 2.0)
        inside = all(plate.buffer(1e-6).contains(s["polygon"]) for s in part.slots if s.get("kind") == "opening")
        _check(rows, part.name + ": openings inside the plate", inside, True, inside)
    _check(rows, "retention tongues reach into the product", reach, "0.3–1.0 mm", 0.3 <= reach <= 1.0)
    if "holder" in parts:
        plate_w = record["geometry"]["holder_mm"][0]
        _check(rows, "insert inside the walls", _r(plate_w + 2 * g["holder_inset_mm"]), _r(span(floor, 0)),
               abs(plate_w + 2 * g["holder_inset_mm"] - span(floor, 0)) <= TOL_MM)
    return {"schema": "counter_display/fold-check-1", "template": "%s/%s" % (TEMPLATE_ID, VERSION),
            "checks": rows, "passed": all(row["ok"] for row in rows)}


def tray_origin(tray):
    floor = next(f for n, f, _ in tray.faces if n == "floor")
    return floor.bounds[0], floor.bounds[1]


def strength_check(record, die=None):
    """What the die itself proves about racking and lean (Day 12's finding: an open-ended channel can rack): the base
    a closed box (every wall creased to the floor, every corner glued), the header the back panel's own board (no
    hinge), and the lean each lock allows — atan(play / engagement) — at most RULES['max_lean_deg']. Loads and board
    stiffness are not modelled; the folded sample shows them."""
    die = die or build_die(record)
    g, v, p = record["geometry"], record["inputs"], record["production"]
    t = v["board_mm"]
    tray = next(part for part in die.parts if part.name == "tray")
    crease_names = {name for name, _ in tray.creases}
    rows = []
    walls = {"front", "back", "left", "right"}
    _check(rows, "every wall creased to the floor", sorted(w for w in walls if "floor / " + w in crease_names),
           sorted(walls), all("floor / " + w in crease_names for w in walls))
    corners = {"%s %s glue flap" % (e, s) for e in ("front", "back") for s in ("left", "right")}
    glued = {name for name, _f, _p in tray.faces if name in corners}
    _check(rows, "every corner glued (the base cannot rack as a mechanism)", sorted(glued), sorted(corners), glued == corners)
    hinge = "back / header" in crease_names
    _check(rows, "no hinge between the back panel and the header", "crease" if hinge else "same board", "same board",
           not hinge)
    lean = []
    slot_play = RULES["slot_end_play_mm"]
    if p["insert_tabs"]:
        leg = g["holder_height_mm"]
        angle = math.degrees(math.atan(slot_play / leg))
        lean.append({"lock": "insert: plate tabs in the side walls, feet glued", "play_mm": slot_play,
                     "engagement_mm": _r(leg), "lean_deg": round(angle, 2)})
    else:
        lean.append({"lock": "row seats: closed boxes glued to the floor", "play_mm": 0.0, "engagement_mm": None,
                     "lean_deg": 0.0})
    # the header is the back panel's own board: no hinge to lean about; its lock keeps the doubled leaves closed
    worst = max(row["lean_deg"] for row in lean)
    _check(rows, "the most any lock lets its part lean (deg)", worst, "≤ %.1f" % RULES["max_lean_deg"],
           worst <= RULES["max_lean_deg"], "Day 12's platform keys allowed 25.5° (a 1.5 mm key in a 2.0 mm slot)")
    return {"schema": "counter_display/strength-1", "checks": rows, "lean": lean, "passed": all(r["ok"] for r in rows),
            "not_modelled": ["the board's bending stiffness under the header", "the glue's strength",
                             "the retention tongues' grip force", "a loaded stand's sway under a shopper's push"]}


def sightline_check(record):
    """The engine's sightline check (500 mm in front, 350 mm up) on the stand's seats."""
    return product_tray_sightlines(record)


def qualify(record):
    die = build_die(record)
    reports = {"fold": fold_check(record, die), "strength": strength_check(record, die),
               "sightline": sightline_check(record), "trade_rules": trade_rules(record, die),
               "comparison": compare(record, die)}
    return {"schema": "counter_display/qualification-1", "template": "%s/%s" % (TEMPLATE_ID, VERSION),
            "reports": reports, "passed": all(report["passed"] for report in reports.values())}


# --- the engine's functions the round's stand adapter calls -----------------------------------------------------------

def sightlines(record):
    return sightline_check(record)




# --- the comparison against the house's measured display dies ----------------------------------------------------------

REFERENCES = "apps/dielines/docs/research/counter_display_references.json"


def compare(record, die=None):
    """Where this die differs from each measured reference, and why: one row per convention."""
    import json
    from pathlib import Path
    from django.conf import settings
    data = json.loads((Path(settings.BASE_DIR) / REFERENCES).read_text())
    die = die or build_die(record)
    g, v, p = record["geometry"], record["inputs"], record["production"]
    t = v["board_mm"]
    refs = data["references"]
    holder = [part for part in die.parts if part.name != "tray"]
    openings = [s["polygon"] for part in holder for s in part.slots if s.get("kind") == "opening"]
    web = min((a.distance(b) for i, a in enumerate(openings) for b in openings[i + 1:]), default=None)
    front = g["front_panel_height_mm"] + t
    lips = [r["front_lip_mm"] for r in refs if r.get("front_lip_mm")]
    rows = [
        {"convention": "construction", "ours": "glued-corner tray; the header the back panel's own board, doubled and locked",
         "references": data["common"]["construction"], "agrees": False,
         "why": "our header is a tall shopper-facing sign on the back panel: glued corners make the base a closed box that "
                "cannot rack under it; the references carry no header above their end walls (37.5–92 mm)"},
        {"convention": "front lip height (mm)", "ours": round(front, 1), "references": "%g–%g" % (min(lips), max(lips)),
         "agrees": min(lips) <= front <= max(lips),
         "why": "set by the brief and the picked picture's proportions" if not min(lips) <= front <= max(lips) else ""},
        {"convention": "side walls", "ours": "trapezoid, %.1f at the front rising to %.1f at the back" % (
            front, g["back_panel_height_mm"] + t), "references": "19 mm on the stand trays; trapezoid wings that tuck",
         "agrees": False, "why": "our side walls rise to the back panel's top to brace it under the header"},
        {"convention": "fold compensation", "ours": "%.1f mm (one caliper) at every fold" % t,
         "references": data["common"]["wall_crease_inset_mm"], "agrees": True, "why": ""},
        {"convention": "lock slots", "ours": "%s: %.1f × %.1f mm in each side wall at the insert's height" % (
            "insert" if p["insert_tabs"] else "none (row seats glued)", RULES["insert_tab_w_mm"] + 2 * RULES["slot_end_play_mm"],
            t + RULES["lock_play_mm"]), "references": "30–35 mm gaps in the floor/side crease, locking the end walls",
         "agrees": False, "why": "ours locks the product insert (Day 12's racking); a 13 mm slot over a 12 mm tab keeps its "
                                 "lean under 3°"},
        {"convention": "insert web (mm)", "ours": round(web, 1) if web is not None else None,
         "references": "hole + 8.5 to 9 mm pitch (an 8.5–9 mm web)",
         "agrees": web is not None and 8.5 <= web <= 9.0,
         "why": "the openings spread over the plate the brief's footprint gives; the web is at least three calipers"},
        {"convention": "insert plies", "ours": "one ply, %d retention tongues per opening reaching %.1f mm into the product" % (
            3 if record["hole_shape"] == "circle" else 2, RULES["retention_mm"]),
         "references": "two plies, the second 3 mm larger (LP-2015, BL-2050)", "agrees": False,
         "why": "the tongues hold each product in one board; the two-ply guide needs a second sheet"},
        {"convention": "glue flaps", "ours": "4 corner flaps, %.1f mm, ends tapered, glue zones marked" % g["corner_glue_flap_mm"],
         "references": "none on the display dies (52.5 mm on FL-2029's separate carton)", "agrees": False,
         "why": "see construction"},
        {"convention": "dust flaps", "ours": "none", "references": "none", "agrees": True, "why": ""},
        {"convention": "rounded corners (mm)", "ours": "lock tabs r %.1f" % RULES["tab_radius_mm"],
         "references": "tuck corners r 10, slot ends r 9", "agrees": False,
         "why": "our tabs are small locks (12–%.0f mm wide), not tucks" % max(20.0, g["floor_mm"][0] * .5)},
        {"convention": "bleed", "ours": "3 mm past printed faces only", "references": "a 2 pt halo around the whole die (inferred)",
         "agrees": False, "why": "trade rule B1; unprinted faces carry no ink"},
        {"convention": "die lines", "ours": "cut and crease on CutContour and Crease spot plates, crease dashed",
         "references": "cut black, crease red, both solid, no spot names", "agrees": False,
         "why": "trade rules E1/E2: the shop separates the knives by spot plate"},
    ]
    return {"schema": "counter_display/comparison-1", "references": [r["id"] for r in refs], "rows": rows,
            "passed": all("why" in row and (row["agrees"] or row["why"]) for row in rows)}


def template_definition():
    """The registry entry this die carries: counter_tray_header 1.0 (apps/dielines/registry.py COUNTER_DISPLAY)."""
    from apps.dielines import registry as R
    return R.resolve(TEMPLATE_ID, VERSION)


GRID_KEYS = ("product_width_mm", "product_depth_mm", "product_height_mm", "width_mm", "depth_mm", "height_mm",
             "header_height_mm", "front_height_mm", "clearance_mm")


def resolve_raised(record, raised):
    """The 1.0 record again from a grid record the product-grid branch adjusted (its rear rows raised for the
    sightline): its numbers, this record's product and board."""
    v = raised["inputs"]
    grid = {key: v[key] for key in GRID_KEYS}
    grid.update(record["layout"], top_edge="square")
    if v.get("row_seat_z_mm"):
        grid["row_seat_z_mm"] = v["row_seat_z_mm"]
    return solve(product=record["product"], board=record["board"]["preset"], hole_shape=record["hole_shape"], **grid)


# --- the stand from the brief (from round_files_stand, the consolidation of 2026-10-28) ---------------------------------

def _number(value, label, default=None):
    if value is None:
        if default is None:
            raise ValueError(label + ' is needed to build the product holder')
        value = default
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(label + ' must be a finite positive measurement')
    return float(value)


def stand_layout(brief, inspection):
    """The grid the holder is built for, the grid the picture shows, and their difference."""
    seen = (inspection or {}).get('stand', {})
    observed = {key: seen.get(key) for key in ('rows', 'columns', 'count')}
    stand = brief.get('stand') or {}
    layout = stand.get('layout') or {}
    count, rows, columns = stand.get('count'), layout.get('rows'), layout.get('columns')
    whole = lambda value: isinstance(value, int) and not isinstance(value, bool) and value > 0
    if whole(count) and whole(rows) and not whole(columns) and count % rows == 0:
        columns = count // rows
    if whole(count) and whole(columns) and not whole(rows) and count % columns == 0:
        rows = count // columns
    if inspection is None and whole(count) and not (whole(rows) and whole(columns)):
        rows = int(math.sqrt(count))                  # the die comes first: the squarest grid, wider than it is deep
        while count % rows:
            rows -= 1
        columns = count // rows
    if whole(rows) and whole(columns) and whole(count) and rows * columns == count <= 100:
        built, source = {'rows': rows, 'columns': columns, 'count': count}, 'brief'
        note = (None if built == observed else
                f"The picture shows {observed['count']} products ({observed['rows']} rows × {observed['columns']} across); "
                f"the stand is built for the brief’s {count} ({rows} rows × {columns} across).")
    elif inspection is None:
        raise ValueError('The die comes first: the brief must give rows × columns that make its count')
    else:
        built, source = dict(observed), 'picture'
        note = 'The brief gives no rows × columns that make its count, so the stand is built for the picture’s grid.'
    return dict(built, source=source, observed=observed, differs=built != observed, note=note)


def _panel_ratio(inspection, name):
    panel = (inspection or {}).get('panels', {}).get(name, {})
    box = panel.get('crop_px')
    if box is None:
        return None
    if (not isinstance(box, (list, tuple)) or len(box) != 4 or
            any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in box)):
        raise ValueError('The ' + name + ' source crop must be a pixel rectangle')
    left, top, right, bottom = box
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise ValueError('The ' + name + ' source crop has no positive area')
    image_size = inspection.get('image_size_px')
    if image_size and (right > image_size[0] or bottom > image_size[1]):
        raise ValueError('The ' + name + ' source crop is outside the picked picture')
    return (bottom - top) / (right - left)


def observed_row_placement(inspection, product_height, front_height, header_height):
    """Derive seats from full front bottles, cap-top differences and the base edge.

    These are provisional orthographic reconstruction measurements. A partially
    visible rear cap supplies its top only, never an invented full bottle box.
    """
    result = {'applied': False, 'provisional': True, 'method':
              'Front bottle height sets vertical scale; paired cap tops set row rises; base top sets front seat'}
    if inspection is None:
        return dict(result, reason='The die comes first: no picture, so the engine\'s own row rises')
    layout = inspection['stand']
    rows, columns = layout['rows'], layout['columns']
    bottles = layout.get('bottles')
    if not isinstance(bottles, list) or len(bottles) != rows * columns:
        return dict(result, reason='A located bottle observation is needed for every row and column')
    boxes = {}
    for bottle in bottles:
        if not isinstance(bottle, dict):
            return dict(result, reason='Every bottle observation must identify its grid cell and pixel rectangle')
        row, column, box = (bottle.get(key) for key in ('row', 'column', 'box_px'))
        if (isinstance(row, bool) or isinstance(column, bool) or not isinstance(row, int)
                or not isinstance(column, int) or not 0 <= row < rows or not 0 <= column < columns
                or (row, column) in boxes or not isinstance(box, (list, tuple)) or len(box) != 4
                or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in box)
                or box[0] < 0 or box[1] < 0 or box[2] <= box[0] or box[3] <= box[1]):
            return dict(result, reason='Bottle observations must cover unique grid cells with positive pixel rectangles')
        if inspection.get('image_size_px') and (box[2] > inspection['image_size_px'][0] or box[3] > inspection['image_size_px'][1]):
            return dict(result, reason='A bottle observation lies outside the picked picture')
        boxes[row, column] = list(box)
    base = inspection.get('panels', {}).get('stand_base', {}).get('crop_px')
    header = inspection.get('panels', {}).get('stand_header', {}).get('crop_px')
    if not base or not header:
        return dict(result, reason='Both the base top and header bottom must be located in the picture')
    front = [boxes[0, column] for column in range(columns)]
    if any(box[3] > base[1] for box in front):
        return dict(result, reason='The front bottle bottoms are occluded by the base; their full height is unresolved')
    scale = [product_height / (box[3] - box[1]) for box in front]
    gaps = [(base[1] - box[3]) * value for box, value in zip(front, scale)]
    front_seat = front_height + median(gaps)
    row_records = []
    for row in range(rows):
        rises = [(front[column][1] - boxes[row, column][1]) * scale[column] for column in range(columns)]
        if min(rises) < 0 < max(rises):
            return dict(result, reason='Cap-top observations disagree on whether this row is above or below the front row')
        rise = median(rises)
        row_records.append({'row': row, 'rise_mm': rise, 'seat_z_mm': front_seat + rise,
                            'column_rises_mm': rises, 'source_boxes_px': [boxes[row, column] for column in range(columns)]})
    header_gaps = [(box[1] - header[3]) * value for box, value in zip(front, scale)]
    measured_height = front_seat + product_height + header_height + median(header_gaps)
    return dict(result, applied=True, rows=row_records,
                row_seat_z_mm=[row['seat_z_mm'] for row in row_records],
                front_clearance_above_base_mm=median(gaps), column_mm_per_pixel=scale,
                header_gap_above_front_caps_mm=median(header_gaps), measured_height_mm=measured_height,
                source_base_crop_px=list(base), source_header_crop_px=list(header),
                limitation='Pixel heights preserve the observed front elevation; physical measurements and a folded sample remain required')


def stand_type(brief, inspection):
    """Which template solves this brief. The die comes first (no picture): the owner's type, or the one he chose, on the family's
    templates (part 2, 2026-10-31). A picture's reading (an older build) keeps the 1.0 it was read with."""
    chosen = (brief.get('stand') or {}).get('type')
    if chosen:
        return chosen
    return 'counter_tray_header' if inspection is None else None


def solve_template_stand(brief, chosen):
    """A stand on the family's templates, from the brief's product and envelope: the same result the chain reads from 1.0."""
    from . import stand_fold, stand_templates
    dimensions = brief.get('dimensions_mm', {})
    stand = brief.get('stand', {})
    target = stand.get('dimensions_mm', {})
    layout = stand_layout(brief, None)
    rows, columns, count = layout['rows'], layout['columns'], layout['count']
    pw = _number(dimensions.get('width', dimensions.get('diameter')), 'Product width')
    pd = _number(dimensions.get('depth'), 'Product depth', pw)
    ph = _number(dimensions.get('height'), 'Product height')
    board = _number(target.get('board_thickness'), 'Board thickness', 1.5)
    preset = 'e_flute' if abs(board - 1.5) < 1e-6 else 'white_card_0_5' if abs(board - 0.5) < 1e-6 else 'sbs_1_5'
    envelope = {'width_mm': target.get('width'), 'depth_mm': target.get('depth'), 'height_mm': target.get('height')}
    record = stand_templates.solve(chosen, product={'width_mm': pw, 'depth_mm': pd, 'height_mm': ph,
                                                    'cap_mm': float(dimensions.get('cap_height') or 0.0)},
                                   rows=rows, columns=columns, envelope=envelope, board=preset,
                                   provisional=stand.get('provisional', True) is not False,
                                   **dict(stand.get('options') or {}))
    shades = list(brief.get('shades') or [])
    if shades:
        record['column_shades'] = [dict(shades[index % len(shades)], column=index + 1) for index in range(columns)]
    die = stand_templates.build_die(record)
    report = stand_templates.qualify(record, die)
    v = record['inputs']
    W, D, H, t = v['width_mm'], v['depth_mm'], v['height_mm'], v['board_mm']
    geometry = layer_geometry(die)
    surfaces = {}
    tray = piece_of(die)
    for key, name in (('stand_header', 'header front'), ('stand_base', 'front panel')):
        polygon = next(face for face_name, face, _printed in tray.faces if face_name == name)
        left, top, right, bottom = polygon.bounds
        surfaces[key] = {'part': 'tray', 'face': name, 'box_mm': list(polygon.bounds), 'size_mm': [right - left, bottom - top],
                         'polygon_mm': [list(point) for point in polygon.exterior.coords], 'source_crop_px': None}
    header_h = v['header_height_mm']
    front_h = v['front_height_mm']
    sight = dict(report['sightlines'], products=report['sightlines']['eyes'][0]['products'],
                 header_clear=all(eye.get('header', {'ok': True})['ok'] for eye in report['sightlines']['eyes']),
                 eye_mm=[W / 2, -stand_fold.EYES[0][0], stand_fold.EYES[0][1]])
    elevation = {'width_mm': W, 'height_mm': H, 'header_box_mm': [0.0, 0.0, W, header_h], 'base_box_mm': [0.0, H - front_h, W, H],
                 'platform_fronts': [],
                 'product_slots': [{'index': hole['index'], 'row': hole['row'], 'column': hole['column'],
                                    'box_mm': [hole['product_centre_mm'][0] - pw / 2, H - hole['seat_z_mm'] - ph,
                                               hole['product_centre_mm'][0] + pw / 2, H - hole['seat_z_mm']],
                                    'seat_z_mm': hole['seat_z_mm'], 'depth_mm': hole['product_centre_mm'][1]} for hole in record['holes']]}
    return {'schema': 'round_files_stand/1', 'sightline_revision': SIGHTLINE_REVISION, 'type': chosen,
            'shape_check': {'schema': 'counter_tray_header/shape-check-1', 'header': {'picture': None, 'die_before': 'square', 'iou_min': HEADER_IOU_MIN,
                                                                                     'result': 'not read: the die comes first, with no picture'},
                            'walls': {'result': 'solved from the brief and the eyes'}, 'ground': {'picture': {}, 'result': 'not read: no picture'}},
            'record': record, 'count': count, 'rows': rows, 'columns': columns, 'layout': layout,
            'valid': report['fold']['passed'], 'fold_check': report['fold'], 'sightlines': sight, 'qualification': report,
            'sheet_mm': [die.sheet_w, die.sheet_h], 'surfaces': surfaces,
            'die': {'cut': geometry['cut'], 'fold': geometry['crease'], 'perf': geometry['perf'], 'half_cut': geometry['half_cut'], 'glue': geometry['glue']},
            'guides': {'safe': geometry['safe'], 'bleed': geometry['bleed']}, 'layers_geometry': geometry, 'front_elevation': elevation,
            'header_mm': surfaces['stand_header']['size_mm'], 'base_front_mm': surfaces['stand_base']['size_mm'],
            'dimensions_mm': {'width': W, 'depth': D, 'height': H, 'board_thickness': t}, 'provisional': True,
            'dimension_adjustments': [{'dimension': row['measure'].replace('_mm', ''), 'from_mm': row['from_mm'], 'to_mm': row['to_mm'],
                                       'reason': row['why']} for row in record.get('changes', [])],
            'observed_row_placement': {'applied': False, 'provisional': True, 'method': 'the rows rise by the rule, from both eyes',
                                       'reason': 'The die comes first: the rows are solved, never measured from a picture'},
            'measurement_sources': {'layout': 'the brief\u2019s rows \u00d7 columns', 'header_height': 'the rule, or the brief',
                                    'front_height': 'the rule, or the brief', 'missing_stand_dimensions': 'the eyes and the openings, by the least change'}}


def solve_stand(brief, inspection, *, include_enclosure=False, rear_visibility='inside', picture=None):
    """Return serializable geometry and reports without generating any artwork."""
    chosen = stand_type(brief, inspection)
    if chosen:
        return solve_template_stand(brief, chosen)
    dimensions = brief.get('dimensions_mm', {})
    stand = brief.get('stand', {})
    target = stand.get('dimensions_mm', {})
    layout = stand_layout(brief, inspection)
    rows, columns, count = (layout.get(key) for key in ('rows', 'columns', 'count'))
    if (any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in (rows, columns, count))
            or rows * columns != count or count > 100):
        raise ValueError('The picked picture must declare a count equal to its rows times columns')
    pw = _number(dimensions.get('width', dimensions.get('diameter')), 'Product width')
    pd = _number(dimensions.get('depth'), 'Product depth', pw)
    ph = _number(dimensions.get('height'), 'Product height')
    board = _number(target.get('board_thickness'), 'Board thickness', 1.5)
    clearance = 0.5  # total opening clearance, not 0.5 mm on each side
    opening = max(pw, pd) + clearance
    edge = 3 * board
    fit = max(board, 1.0)
    minimum_width = columns * opening + (columns + 1) * edge + 2 * fit + 2 * board
    minimum_depth = rows * opening + (rows + 1) * edge + 2 * fit + 2 * board
    width = _number(target.get('width'), 'Stand width', minimum_width)
    depth = _number(target.get('depth'), 'Stand depth', minimum_depth)
    adjustments = []
    provisional = stand.get('provisional', True) is not False
    for key, original, needed in (('width', width, minimum_width), ('depth', depth, minimum_depth)):
        if provisional and original < needed:
            adjustments.append({'dimension': key, 'from_mm': original, 'to_mm': needed,
                                'reason': 'Fit the observed count with product clearance and three-board webs'})
    if provisional:
        width, depth = max(width, minimum_width), max(depth, minimum_depth)
    floor_width = width - 2 * board
    header_ratio = _panel_ratio(inspection, 'stand_header')
    base_ratio = _panel_ratio(inspection, 'stand_base')
    header_height = floor_width * header_ratio if header_ratio is not None else ph * 0.6
    front_height = floor_width * base_ratio + board if base_ratio is not None else min(25.0, ph * 0.25)
    height = _number(target.get('height'), 'Stand height', ph + header_height + board)
    placement = observed_row_placement(inspection, ph, front_height, header_height)
    if placement['applied'] and len(placement['row_seat_z_mm']) != rows:
        placement = {'applied': False, 'provisional': True, 'method': placement['method'],
                     'reason': 'The picture’s rows differ from the built rows; seats use the engine’s own rises'}
    if placement['applied']:
        row_support_depth = rows * (opening + 2 * edge) + 2 * fit + 2 * board
        if provisional and depth < row_support_depth:
            adjustments.append({'dimension': 'depth', 'from_mm': depth, 'to_mm': row_support_depth,
                                'reason': 'Retain three-board edge webs around each separate measured row collar'})
            depth = row_support_depth
    if placement['applied'] and provisional and abs(height - placement['measured_height_mm']) > 1e-9:
        adjustments.append({'dimension': 'height', 'from_mm': height, 'to_mm': placement['measured_height_mm'],
                            'reason': 'Preserve the measured cap-top gap below the header after raising the pictured bottle seats'})
        height = placement['measured_height_mm']
    # Keep the constructed back >= front after the engine subtracts board and
    # header thickness. An exact decimal boundary can otherwise round below it.
    minimum_height = math.nextafter(front_height + header_height, math.inf)
    if provisional and height < minimum_height:
        adjustments.append({'dimension': 'height', 'from_mm': height, 'to_mm': minimum_height,
                            'reason': 'Retain the picked panel proportions with a back wall at least as tall as the front'})
        height = minimum_height
    if placement['applied']:
        placement['height_matches_observation'] = abs(height - placement['measured_height_mm']) <= TOL_MM
    profile = 'circle' if dimensions.get('diameter') and not dimensions.get('width') else 'square'
    # counter_tray_header 1.0 (owner, 2026-10-28): the production die, its board preset by the brief's thickness
    record = solve(product='bottle', board='e_flute' if abs(board - 1.5) < 1e-6 else 'white_card_0_5'
                              if abs(board - 0.5) < 1e-6 else 'sbs_1_5', product_grid={
        'product_width_mm': pw, 'product_depth_mm': pd, 'product_height_mm': ph,
        'rows': rows, 'columns': columns, 'count': count,
        'width_mm': width, 'depth_mm': depth, 'height_mm': height,
        'header_height_mm': header_height, 'front_height_mm': front_height,
        'hole_shape': profile, 'clearance_mm': clearance, 'top_edge': 'square',
        'row_seat_z_mm': placement['row_seat_z_mm'] if placement['applied'] else None})
    visibility_adjustment = None
    if rear_visibility == 'inside':
        # the default (the owner's goal of 2026-10-29: fix the stand's sightline failure; his ruling: keep its size):
        # rows whose seats were measured from the picture move inside the stand's own size until the eye sees every
        # product's top band and the header's safe area. Rows on the floor for want of evidence are not given rises
        # nobody measured: their report stays the designer's to read.
        first = product_tray_sightlines(record)
        if placement['applied'] and not (first['passed'] and first['header_clear']):
            try:
                visibility_adjustment = product_tray_raise_rear(record, keep_size=True)
            except ValueError as exc:
                visibility_adjustment = {'keep_size': True, 'failed': str(exc), 'initial_sightlines': first}
    elif rear_visibility:
        if not provisional:
            raise ValueError('Rear visibility adjustment needs provisional stand measurements')
        visibility_adjustment = product_tray_raise_rear(record)
    if visibility_adjustment is not None and 'record' in visibility_adjustment:
        raised = visibility_adjustment.pop('record')
        record = resolve_raised(record, raised)
        record.setdefault('authority', {})['rear_visibility'] = raised['authority']['rear_visibility']
        height = record['inputs']['height_mm']
        if placement['applied']:
            placement['height_matches_observation'] = abs(height - placement['measured_height_mm']) <= TOL_MM
    # the shape check (the owner's goal of 2026-10-29): the picked picture's header outline and its grounds against
    # the die — a mismatch fixed in the die before any painting, each check recorded
    outline, grounds = read_header_outline(inspection), read_grounds(inspection, picture)
    shape_check = {'schema': 'counter_tray_header/shape-check-1', 'header': {
        'picture': outline, 'die_before': 'square', 'iou_min': HEADER_IOU_MIN,
        'result': ('not read: the reading gives no header outline' if outline is None else
                   'matched: the picture\'s header is square' if outline['shape'] == 'square' else
                   'not fixed: the outline was read too loosely (overlap %.3f)' % outline['iou']
                   if outline['iou'] < HEADER_IOU_MIN else 'fixed: the header cut to the picture\'s %s outline' % outline['shape'])},
        'walls': {'result': 'not read: the reading outlines no wall; the walls stay the die\'s own (front %.1f mm, back '
                            '%.1f mm high)' % (record['geometry']['front_panel_height_mm'], record['geometry']['back_panel_height_mm'])},
        'ground': {'picture': grounds, 'die_before': 'the board\'s own white (no ground)',
                   'result': ('fixed: the board\'s base colour is the picture\'s ground %s' % grounds['board']['hex'])
                   if grounds.get('board') else 'not read: no picture or no front strip in the reading'}}
    if outline is not None and outline['shape'] != 'square' and outline['iou'] >= HEADER_IOU_MIN:
        record['geometry']['header_outline'] = {'shape': outline['shape'], 'params': outline['params'],
                                                'source': 'the picked picture (shape check)'}
    if grounds:
        record['production']['grounds'] = {name: row['hex'] for name, row in grounds.items()}
        record['production']['board_ground_hex'] = (grounds.get('board') or grounds.get('header'))['hex']
    die = build_die(record)
    fold = fold_check(record, die)
    sight = sightlines(record)
    geometry = layer_geometry(die)
    surfaces = {}
    tray = next(part for part in die.parts if part.name == 'tray')
    for key, name in (('stand_header', 'header front'), ('stand_base', 'front panel')):
        polygon = next(face for face_name, face, _printed in tray.faces if face_name == name)
        left, top, right, bottom = polygon.bounds
        surfaces[key] = {'part': 'tray', 'face': name, 'box_mm': list(polygon.bounds),
                         'size_mm': [right - left, bottom - top], 'polygon_mm': [list(point) for point in polygon.exterior.coords],
                         'source_crop_px': (inspection or {}).get('panels', {}).get(key, {}).get('crop_px')}
    elevation = {'width_mm': width, 'height_mm': height,
                 'header_box_mm': [board, 0.0, width - board, header_height],
                 'base_box_mm': [board, height - front_height, width - board, height - board],
                 'platform_fronts': product_tray_platform_fronts(record),
                 'product_slots': [{'index': hole['index'], 'row': hole['row'], 'column': hole['column'],
                     'box_mm': [hole['product_centre_mm'][0] - pw / 2, height - hole['seat_z_mm'] - ph,
                                hole['product_centre_mm'][0] + pw / 2, height - hole['seat_z_mm']],
                     'seat_z_mm': hole['seat_z_mm'],
                     'depth_mm': hole['product_centre_mm'][1]} for hole in record['holes']]}
    result = {'schema': 'round_files_stand/1', 'sightline_revision': SIGHTLINE_REVISION, 'shape_check': shape_check,
              'record': record,
              'count': count, 'rows': rows, 'columns': columns,
            'layout': layout,
            'valid': fold['passed'], 'fold_check': fold, 'sightlines': sight,
            'sheet_mm': [die.sheet_w, die.sheet_h], 'surfaces': surfaces,
            'die': {'cut': geometry['cut'] + [
                [[cx + radius * math.cos(2 * math.pi * i / 128), cy + radius * math.sin(2 * math.pi * i / 128)]
                 for i in range(129)] for cx, cy, radius in geometry['holes']], 'fold': geometry['crease']},
            'guides': {'safe': geometry['safe'], 'bleed': geometry['bleed']},
            'layers_geometry': geometry, 'front_elevation': elevation,
            'header_mm': surfaces['stand_header']['size_mm'], 'base_front_mm': surfaces['stand_base']['size_mm'],
            'dimensions_mm': {'width': width, 'depth': depth, 'height': height, 'board_thickness': board},
            'provisional': True, 'dimension_adjustments': adjustments, 'observed_row_placement': placement, 'measurement_sources': {
                'layout': ('the brief’s rows × columns; the picture’s grid is listed beside it' if layout['source'] == 'brief'
                           else 'picked-picture inspection; the brief gives no complete grid'),
                'header_height': 'source crop aspect at the tray width' if header_ratio is not None else 'provisional 60% of product height',
                'front_height': 'source crop aspect at the tray width plus board' if base_ratio is not None else 'provisional quarter product height, at most 25 mm',
                'missing_stand_dimensions': 'minimum holder fit with three-board webs, or product plus header height'}}
    if include_enclosure:
        enclosure = product_tray_enclosure_elevations(record)
        elevation['enclosure_faces'] = enclosure['front_faces']
        elevation['enclosure_projection'] = enclosure['projection_note']
        result['side_elevation'] = enclosure['side_elevation']
        result['enclosure_surfaces'] = []
        for name, polygon, printed in tray.faces:
            if name not in ('back panel', 'left side', 'right side', 'floor'):
                continue
            result['enclosure_surfaces'].append({'part': tray.name, 'face': name,
                'box_mm': list(polygon.bounds), 'polygon_mm': [list(point) for point in polygon.exterior.coords],
                'printed': printed, 'material': None,
                'note': 'Actual engine face; a source-supported material or finish must be assigned separately'})
    if visibility_adjustment is not None:
        result['rear_visibility_adjustment'] = visibility_adjustment
    return result
