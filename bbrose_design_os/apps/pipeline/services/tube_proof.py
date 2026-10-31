"""[His answer after test day finding 3, 2026-09-30 (transcribed at 23d4375), step 3 of its build — "The 3D proof. A
squeeze tube is added to the 3D engine, the drawing is rendered on it, and it is compared with the concept" — and his
look at 117 drawn from its map, 2026-10-02 (transcribed at 99ede0a): "And also the 3D".] THE SQUEEZE TUBE IN 3D: the
drawn product's own outline turned into a tube — round where it is round (the closure, and the body at its round end),
flattening toward its crimp as a squeeze tube's sleeve does, the sleeve's girth the same at every height (it is one
printed sheet rolled), the crimp ribbed — and the drawing wrapped on it as the front view shows it, rendered by the 3D
engine (Blender) under a gloss.

Pure geometry here (``tube_mesh``), the render in ``blender_scripts/tube_proof.py``. Millimetres throughout; y up."""
from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile

#: the 3D engine — the one the palette renders run on
BLENDER = os.path.expanduser("~/Applications/Blender-4.5.12-LTS.app/Contents/MacOS/Blender")
SCRIPT = os.path.join(os.path.dirname(__file__), "blender_scripts", "tube_proof.py")

TUBE_PROOF_PARAMS = {
    "ring_points": 96,          # points round each ring of the mesh
    "rows": 220,                # rings from the closure's foot to the crimp's top
    "crimp_mm": 9.0,            # the crimp's height, flat and ribbed, at the sleeve's top
    "crimp_depth_mm": 0.6,      # the crimp's thickness, front to back
    "rib_pitch_mm": 1.2,        # the crimp's ribs, one every this many mm across …
    "rib_depth_mm": 0.12,       # … standing this far proud
    "samples": 96,              # the render's samples (Cycles)
    "resolution": (1000, 1500),
}


def _ellipse_perimeter(a: float, b: float) -> float:
    """Ramanujan's second approximation."""
    if a + b <= 0.0:
        return 0.0
    h = ((a - b) / (a + b)) ** 2
    return math.pi * (a + b) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h)))


def _depth_for(a: float, girth: float, floor: float) -> float:
    """The half depth a sleeve of ``girth`` takes where its half width is ``a`` — its cross-section an ellipse of the
    same girth — never thinner than ``floor``."""
    if 2.0 * a >= girth / 2.0:
        return floor
    lo, hi = floor, a * 4.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if _ellipse_perimeter(a, mid) < girth:
            lo = mid
        else:
            hi = mid
    return max(floor, (lo + hi) / 2.0)


def tube_mesh(outline: list, *, round_diameter_mm: float, closure_share: float) -> dict:
    """The tube as a mesh from the drawn product's outline: ``outline`` — ``[(y, half width)]`` in mm, y from the
    product's foot (the closure's) up to its top (the crimp's) — ``round_diameter_mm`` his round diameter, and
    ``closure_share`` the share of the height the closure takes at the foot. ``{"vertices": [(x, y, z)],
    "uvs": [(u, v)], "faces": [((vi, ti), …)], "rings": [{"y", "a", "b", "part"}]}`` — x across, y up, z toward the
    viewer; each vertex's u, v the drawing's own place for it as the front shows it (x across the drawing's width, y up
    its height), so the drawing wraps exactly as the front view draws it."""
    p = TUBE_PROOF_PARAMS
    ys = [float(y) for y, _a in outline]
    y0, y1 = min(ys), max(ys)
    height = y1 - y0
    width = 2.0 * max(float(a) for _y, a in outline)
    girth = math.pi * round_diameter_mm
    closure_top = y0 + closure_share * height
    crimp_from = y1 - p["crimp_mm"]
    pts = sorted((float(y), float(a)) for y, a in outline)

    def half_width(y):
        for (ya, aa), (yb, ab) in zip(pts, pts[1:]):
            if ya <= y <= yb:
                return aa if yb == ya else aa + (ab - aa) * (y - ya) / (yb - ya)
        return pts[0][1] if y < pts[0][0] else pts[-1][1]
    n = int(p["ring_points"])
    vertices, uvs, rings = [], [], []
    for r in range(int(p["rows"]) + 1):
        y = y0 + height * r / float(p["rows"])
        a = half_width(y)
        if y <= closure_top:
            b, part = a, "closure"                           # the closure is round
        elif y >= crimp_from:
            b, part = p["crimp_depth_mm"] / 2.0, "crimp"
        else:
            b, part = _depth_for(a, girth, p["crimp_depth_mm"] / 2.0), "sleeve"
        rings.append({"y": round(y, 4), "a": round(a, 4), "b": round(b, 4), "part": part})
        for k in range(n):
            t = 2.0 * math.pi * k / n
            x, z = a * math.cos(t), b * math.sin(t)
            if part == "crimp":                                   # its ribs, standing out on both faces
                rib = p["rib_depth_mm"] * 0.5 * (1 + math.cos(2 * math.pi * x / p["rib_pitch_mm"]))
                z += rib if z >= 0.0 else -rib
            vertices.append((x, y, z))
            uvs.append((0.5 + x / width, (y - y0) / height))
    faces = []
    for r in range(int(p["rows"])):
        for k in range(n):
            a_, b_ = r * n + k, r * n + (k + 1) % n
            c_, d_ = (r + 1) * n + (k + 1) % n, (r + 1) * n + k
            faces.append(((a_, a_), (b_, b_), (c_, c_), (d_, d_)))
    for cap_ring, centre_y in ((0, y0), (int(p["rows"]), y1)):          # the two ends closed
        vertices.append((0.0, centre_y, 0.0))
        uvs.append((0.5, (centre_y - y0) / height))
        c = len(vertices) - 1
        for k in range(n):
            a_, b_ = cap_ring * n + k, cap_ring * n + (k + 1) % n
            faces.append(((c, c), (b_, b_), (a_, a_)) if cap_ring == 0 else ((c, c), (a_, a_), (b_, b_)))
    return {"vertices": vertices, "uvs": uvs, "faces": faces, "rings": rings}


def write_obj(mesh: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("# the squeeze tube's 3D proof\n")
        for x, y, z in mesh["vertices"]:
            f.write("v %.5f %.5f %.5f\n" % (x, y, z))
        for u, v in mesh["uvs"]:
            f.write("vt %.6f %.6f\n" % (u, v))
        for face in mesh["faces"]:
            f.write("f " + " ".join("%d/%d" % (vi + 1, ti + 1) for vi, ti in face) + "\n")


def render(mesh: dict, artwork_png: str, out_png: str, *, ground: str) -> dict:
    """The mesh rendered by the 3D engine, ``artwork_png`` (the drawing as the front shows it, the product's box
    exactly) wrapped on it, a gloss over it, on a ``ground`` (#RRGGBB) — written to ``out_png``. Raises where the engine
    does not finish."""
    with tempfile.TemporaryDirectory() as d:
        obj = os.path.join(d, "tube.obj")
        write_obj(mesh, obj)
        cfg = {"obj": obj, "artwork": artwork_png, "out": out_png, "ground": ground,
               "samples": TUBE_PROOF_PARAMS["samples"], "resolution": list(TUBE_PROOF_PARAMS["resolution"]),
               "height_mm": max(v[1] for v in mesh["vertices"]) - min(v[1] for v in mesh["vertices"])}
        cfg_path = os.path.join(d, "cfg.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        done = subprocess.run([BLENDER, "-b", "--factory-startup", "-noaudio", "-P", SCRIPT, "--", cfg_path],
                              capture_output=True, text=True, timeout=1800)
        if "TUBE_PROOF_OK" not in done.stdout:
            raise RuntimeError("the 3D engine did not finish: %s %s" % (done.stdout[-600:], done.stderr[-300:]))
    from PIL import Image
    views = []
    for view in ("front", "turned"):                     # the tube laid on its ground
        path = out_png.replace(".png", "_%s.png" % view)
        tube = Image.open(path).convert("RGBA")
        ground_im = Image.new("RGBA", tube.size, "#" + ground.lstrip("#"))
        Image.alpha_composite(ground_im, tube).convert("RGB").save(path)
        views.append(path)
    return {"out": out_png, "views": views, "cfg": {k: v for k, v in cfg.items() if k not in ("obj",)}}


def outline_from(doc) -> list:
    """The drawn product's outline (its ``body`` path) as ``[(y from its foot, half width)]`` in millimetres — each cubic
    sampled, each row's half width half the distance between the outline's two sides there."""
    body = next((n for n, _ in doc.walk() if n.name == "body"), None)
    if body is None:
        return []
    pts, last = [], None
    for sg in body.segments:
        if hasattr(sg, "x1") and last is not None:
            for k in range(1, 9):
                t = k / 8.0
                u = 1.0 - t
                pts.append((u ** 3 * last[0] + 3 * u * u * t * sg.x1 + 3 * u * t * t * sg.x2 + t ** 3 * sg.x,
                            u ** 3 * last[1] + 3 * u * u * t * sg.y1 + 3 * u * t * t * sg.y2 + t ** 3 * sg.y))
            last = (sg.x, sg.y)
        elif hasattr(sg, "x"):
            pts.append((sg.x, sg.y))
            last = (sg.x, sg.y)
    top, foot = min(y for _x, y in pts), max(y for _x, y in pts)
    out = []
    for i in range(201):
        y = top + (foot - top) * i / 200.0
        xs = [ax + (y - ay) * (bx - ax) / (by - ay) for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1])
              if (ay - y) * (by - y) <= 0 and ay != by]
        if len(xs) >= 2:
            out.append((foot - y, (max(xs) - min(xs)) / 2.0))
    return sorted(out)


def front_artwork(doc, out_png: str, *, dpi: int) -> str:
    """The drawing as the front shows it — the product's box exactly, its outline's ink stroke left out (on the tube the
    sleeve's own edge draws it) — through the real emitter, rasterised at ``dpi``."""
    import fitz

    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    copy = doc.model_copy(deep=True)

    def drop(group):
        group.children = [c for c in group.children if c.name != "silhouette-outline"]
        for c in group.children:
            if hasattr(c, "children"):
                drop(c)
    drop(copy.root)
    body = next(n for n, _ in copy.walk() if n.name == "body")
    xs = [sg.x for sg in body.segments if hasattr(sg, "x")]
    ys = [sg.y for sg in body.segments if hasattr(sg, "y")]
    with tempfile.TemporaryDirectory() as d:
        ai = emit_pdf_ai(copy, os.path.join(d, "front.ai"))
        page = fitz.open(ai)[0]
        mm = 72.0 / 25.4
        clip = fitz.Rect(min(xs) * mm, min(ys) * mm, max(xs) * mm, max(ys) * mm)
        page.get_pixmap(dpi=dpi, clip=clip).save(out_png)
    return out_png


__all__ = ["BLENDER", "SCRIPT", "TUBE_PROOF_PARAMS", "tube_mesh", "write_obj", "render", "outline_from",
           "front_artwork"]
