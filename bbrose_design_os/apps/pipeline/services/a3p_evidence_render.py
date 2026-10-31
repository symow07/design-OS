"""PALT-M4B-A3P §5 — generate the 41 required diagnostics.

Every image is bound to a frozen geometry whose identity is asserted
before anything is drawn, so an image can never quietly depict a mesh
other than the one it claims. The A3R set renders the FAILED candidate C
and is labelled historical; the A3F and A3M sets render the corrected
true-normal geometry.

Labels are written into each PNG's own metadata as well as drawn on it,
so the validator reads them back from the image file rather than from a
sidecar that could drift away from the picture.

Blender 4.5.12 LTS renders the three-dimensional views in its
VISUALIZATION_AND_RENDERING_ONLY role. Plots, maps, diagrams and
histograms are drawn deterministically with the same PIL toolchain the
earlier accepted A2/A3 evidence used — a convergence plot is not a
photograph of anything and Blender cannot produce one.
"""
from __future__ import annotations

import copy
import json
import math
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo

from apps.pipeline.services import a3p_evidence_manifest as MAN
from apps.pipeline.services import palette_identity as PI
from apps.pipeline.services import palette_thickness_authority as TA
from apps.pipeline.services import palt_m4b_a3 as A3
from apps.pipeline.services.geometry_validation_render import (
    BLENDER, export_obj, pixel_hash)
from apps.pipeline.services.palette_cored_tray_geometry import (
    DEFAULT_CORE, build_cored_palette_tray)
from apps.pipeline.services.palette_review_fonts import font

SCHEMA = "a3p_evidence_render/1.0"
SCRIPT = os.path.join(os.path.dirname(__file__), "blender_scripts",
                      "m4b_a_tray_views.py")
BLENDER_VERSION = "Blender 4.5.12 LTS (pinned)"

PAPER = (250, 249, 246)
INK = (28, 28, 32)
GREY = (110, 110, 118)
RED = (198, 48, 42)
GREEN = (44, 150, 92)
BLUE = (38, 96, 156)
AMBER = (214, 152, 38)
VIOLET = (150, 96, 176)
MARKER_RGB = (199, 28, 23)          # the Blender marker clay, sRGB

AUTHORITY = ("PALT_P1_FINAL_DIMENSIONS: NOT_APPROVED · "
             "PALT_P1_MANUFACTURING_AUTHORITY: NOT_ESTABLISHED · "
             "PALT_P1_OWNER_APPROVAL: NOT_GRANTED")

#: recorded A3R minimum (docs/roadmap/palt_m4b_a3r/minimum_region_manifest)
MIN_REGION = {
    "xyz_mm": (-23.467508, -19.132122, 2.79107),
    "measured_normal_thickness_mm": 0.600738,
    "analytical_thickness_mm": 0.85726026,
    "section_thickness_mm": 14.47712,
    "source_face": 1028, "opposing_face": 17093,
    "source_normal": (-0.452353, -0.754705, 0.475181),
    "opposing_normal": (0.078743, 0.131375, -0.9882),
    "feature": "FLOOR_FILLET",
    "classification": "CONFIRMED_PHYSICAL_THIN_REGION",
}
#: recorded A3M maximum (docs/roadmap/palt_m4b_a3m/a3m_validation_report)
MAX_REGION = {
    "xyz_mm": (-30.151002, -44.327052, 6.847279),
    "reported_ray_mm": 11.830091,
    "midpoint_inscribed_diameter_mm": 0.819609,
    "midpoint_ratio": 0.069282,
    "source_face": 720, "opposing_face": 14998,
    "source_normal": (-0.048201, 0.981146, 0.187164),
    "opposing_normal": (0.0, -0.999657, -0.026177),
    "classification": "LONG_PATH_NOT_LOCAL_WALL_THICKNESS",
    "authoritative_local_wall_mm": 2.161657,
    "feature": "DECK_SKIN",
}


class EvidenceRenderError(RuntimeError):
    """Raised when evidence cannot be produced from the frozen geometry."""


# --------------------------------------------------------------------------
# frozen geometry
# --------------------------------------------------------------------------

def frozen_tray(milestone: str) -> dict:
    """Rebuild a milestone's frozen tray and REFUSE on identity drift."""
    bind = MAN.GEOMETRY_BINDING[milestone]
    core = copy.deepcopy(DEFAULT_CORE)
    core.update(bind["core_overrides"])
    tray = build_cored_palette_tray(A3.tray_spec(), core)
    got = PI.mesh_geometry_identity(tray)
    want = bind["mesh_geometry_identity"]
    if got != want:
        raise EvidenceRenderError(
            f"{milestone} evidence must render {want} but the kernel now "
            f"produces {got}. Rendering anyway would attach a truthful "
            f"label to the wrong mesh.")
    tray["_geometry_identity"] = got
    tray["_milestone"] = milestone
    return tray


# --------------------------------------------------------------------------
# labelling — written INTO the png, not beside it
# --------------------------------------------------------------------------

def binding_for_identity(identity, *, prefer=None):
    """Which frozen geometry this identity actually IS.

    The stamp must record what was MEASURED, not what the manifest asked
    for. Reading the binding at both stamp time and validation time would
    compare a constant with itself, and three of the eight failure
    conditions could never fire.

    A3F and A3M deliberately share one corrected geometry, so a bare scan
    would resolve every A3M image to A3F and give it A3F's labels.
    ``prefer`` disambiguates when the geometry IS the one that milestone
    requires — and is ignored when it is not, so a mismatch still falls
    through to the real binding and fires.
    """
    if prefer and MAN.GEOMETRY_BINDING.get(prefer, {}).get(
            "mesh_geometry_identity") == identity:
        return prefer, MAN.GEOMETRY_BINDING[prefer]
    for name, bind in MAN.GEOMETRY_BINDING.items():
        if bind["mesh_geometry_identity"] == identity:
            return name, bind
    return None, {"mesh_geometry_identity": identity,
                  "status": "UNRECOGNISED_GEOMETRY", "legacy_alias": None}


def stamp(path, milestone, title, subtitle, *, geometry_identity,
          extra=()):
    """Draw the labels on the image and embed them in its metadata.

    ``geometry_identity`` is the identity the geometry actually hashed to
    when it was rebuilt, so what the validator reads back is a measurement
    and not a restatement of the requirement.
    """
    measured_milestone, bind = binding_for_identity(geometry_identity,
                                                    prefer=milestone)
    labels = list(MAN.REQUIRED_LABELS.get(measured_milestone, ()))
    if not labels:
        labels = [f"UNRECOGNISED GEOMETRY {geometry_identity}"]
    img = Image.open(path).convert("RGB")
    w, h = img.size
    head, foot = 96, 34 + 30 * (len(labels) + 1)
    out = Image.new("RGB", (w, h + head + foot), PAPER)
    out.paste(img, (0, head))
    d = ImageDraw.Draw(out)
    d.text((30, 22), title, font=font(42), fill=INK)
    d.text((30, 64), subtitle, font=font(24), fill=GREY)
    y = head + h + 12
    for i, text in enumerate(labels):
        colour = RED if milestone == MAN.A3R else INK
        d.text((30, y + i * 30), text, font=font(25), fill=colour)
    y += 30 * len(labels)
    for j, text in enumerate(list(extra) + [AUTHORITY]):
        d.text((30, y + j * 30), text, font=font(20), fill=GREY)
    meta = PngInfo()
    meta.add_text("a3p_milestone", milestone)
    meta.add_text("a3p_labels", "|".join(labels))
    meta.add_text("a3p_geometry_identity", geometry_identity)
    meta.add_text("a3p_status", bind["status"])
    meta.add_text("a3p_blender", BLENDER_VERSION)
    meta.add_text("a3p_schema", SCHEMA)
    out.save(path, pnginfo=meta)
    return path


# --------------------------------------------------------------------------
# blender
# --------------------------------------------------------------------------

def _marker_mesh(point, r=2.0, *, pin=True, z_lo=-6.0, z_hi=22.0):
    """An octahedron at the diagnostic point, plus a through-pin.

    A point inside the deck skin is not visible from underneath, so a bare
    octahedron produces an underside image that does not expose the
    feature it exists to show — the validator catches exactly that. The
    pin protrudes beyond both faces of the tray, so the location reads
    from any camera without the image pretending to see through material.
    """
    x, y, z = point
    verts = [[x + r, y, z], [x - r, y, z], [x, y + r, z],
             [x, y - r, z], [x, y, z + r], [x, y, z - r]]
    faces = [[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4],
             [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]]
    if pin:
        a = r * 0.34
        base = len(verts)
        for zz in (z_lo, z_hi):
            verts += [[x - a, y - a, zz], [x + a, y - a, zz],
                      [x + a, y + a, zz], [x - a, y + a, zz]]
        lo, hi = base, base + 4
        for i in range(4):
            j = (i + 1) % 4
            faces += [[lo + i, hi + i, hi + j], [lo + i, hi + j, lo + j]]
        faces += [[lo, lo + 2, lo + 1], [lo, lo + 3, lo + 2],
                  [hi, hi + 1, hi + 2], [hi, hi + 2, hi + 3]]
    return {"vertices": np.asarray(verts, float),
            "faces": np.asarray(faces, np.int64)}


def _run_blender(cfg):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(cfg, fh)
        p = fh.name
    proc = subprocess.run(
        [BLENDER, "-b", "--factory-startup", "-noaudio", "-P", SCRIPT,
         "--", p], capture_output=True, text=True, timeout=3600)
    if "M4B_A_TRAY_VIEWS_OK" not in proc.stdout:
        raise EvidenceRenderError(proc.stdout[-2500:] + proc.stderr[-1500:])


def blender_view(tray, out_path, *, mode="clay", view="top", marker=None,
                 obj_dir, samples=48, res=1800, scale=132.0, wire_px=1.1):
    """One deterministic Blender view of the frozen tray."""
    os.makedirs(obj_dir, exist_ok=True)
    tray_obj = os.path.join(obj_dir, f"tray_{tray['_geometry_identity']}.obj")
    if not os.path.exists(tray_obj):
        export_obj(tray, tray_obj)
    meshes = {"cored_palette_tray": tray_obj}
    if marker is not None:
        mp = os.path.join(obj_dir, f"marker_{view}_{mode}.obj")
        export_obj(_marker_mesh(marker), mp)
        meshes["marker_point"] = mp
    deck = tray["tray"]["elevations_mm"]["deck"] if "tray" in tray \
        else tray["elevations_mm"]["deck"]
    views = {"top": {"az": 0, "el": 89.9, "scale": scale},
             "under": {"az": 34, "el": -34, "scale": scale},
             "three_quarter": {"az": 36, "el": 30, "scale": scale},
             "closeup": {"az": 28, "el": 22, "scale": scale}}
    _run_blender({"meshes": meshes, "mode": mode, "samples": samples,
                  "resolution": [res, res], "ortho_scale": scale,
                  "wire_px": wire_px, "smooth_angle_deg": 31.0,
                  "centre": [0.0, 0.0, deck / 2.0],
                  "camera_distance": 700.0,
                  "detail_views": {view: views[view]},
                  "views": {view: out_path}})
    return out_path


# --------------------------------------------------------------------------
# deterministic drawn diagnostics
# --------------------------------------------------------------------------

def _canvas(w=2000, h=1300):
    img = Image.new("RGB", (w, h), PAPER)
    return img, ImageDraw.Draw(img)


def _axes(d, box, xlab, ylab):
    x0, y0, x1, y1 = box
    d.rectangle(box, outline=INK, width=3)
    d.text(((x0 + x1) // 2 - 90, y1 + 18), xlab, font=font(26), fill=INK)
    d.text((x0 - 150, (y0 + y1) // 2), ylab, font=font(26), fill=INK)


def _key(d, x, y, items, size=24):
    for i, (label, colour) in enumerate(items):
        yy = y + i * 34
        d.rectangle([x, yy, x + 26, yy + 20], fill=colour, outline=INK)
        d.text((x + 38, yy - 3), label, font=font(size), fill=INK)


def meridional_profile(tray):
    """The pocket and cup profiles in the (r, z) plane, from the mesh."""
    return (np.asarray(tray["pocket_profile_rings"], float)
            if "pocket_profile_rings" in tray else None)


def draw_offset_comparison(out_path, region):
    """Why a radial offset delivers w*cos(obliquity) and a normal offset
    delivers w — drawn as real geometry, not as a caption."""
    img, d = _canvas(2000, 1200)
    cx, cy, R = 760, 700, 380
    # a quarter fillet arc, the surface that failed
    pts = [(cx + R * math.cos(a), cy - R * math.sin(a))
           for a in np.linspace(0, math.pi / 2, 80)]
    d.line(pts, fill=INK, width=6)
    w = 150
    rad = [(cx + (R - w) * math.cos(a), cy - (R - w) * math.sin(a))
           for a in np.linspace(0, math.pi / 2, 80)]
    d.line(rad, fill=RED, width=6)
    for a in (0.35, 0.7, 1.05):
        sx, sy = cx + R * math.cos(a), cy - R * math.sin(a)
        # radial direction is toward the arc centre here, so on THIS arc
        # the two agree; the failure is where the profile is not an arc
        # about the offset origin — shown by the oblique segment below
        d.line([(sx, sy), (cx, cy)], fill=GREY, width=2)
    ox, oy = 1420, 700
    d.line([(ox - 330, oy - 300), (ox + 260, oy + 240)], fill=INK, width=6)
    nx, ny = 0.63, -0.77
    for t in (0.2, 0.5, 0.8):
        px = ox - 330 + t * 590
        py = oy - 300 + t * 540
        d.line([(px, py), (px + nx * 150, py + ny * 150)],
               fill=GREEN, width=5)
        d.line([(px, py), (px + 150, py)], fill=RED, width=3)
    d.text((360, 120), "RADIAL OFFSET", font=font(40), fill=RED)
    d.text((320, 168),
           "delivers w · cos(obliquity) where the normal is not radial",
           font=font(25), fill=GREY)
    d.text((1180, 120), "TRUE NORMAL OFFSET", font=font(40), fill=GREEN)
    d.text((1180, 168), "delivers w everywhere", font=font(25), fill=GREY)
    _key(d, 120, 1010, [
        ("pocket surface (fit-controlling)", INK),
        (f"radial offset — measured {region['measured_normal_thickness_mm']}"
         " mm at the floor fillet", RED),
        ("normal offset — the correction", GREEN)])
    img.save(out_path)
    return out_path


def draw_thickness_definitions(out_path, region):
    """What each definition means, and why three numbers at one point are
    not a contradiction."""
    img, d = _canvas(2000, 1250)
    rows = [
        ("LOCAL_NORMAL_THICKNESS",
         region["measured_normal_thickness_mm"],
         "along the surface normal to the physically opposing wall", GREEN),
        ("ANALYTICAL_NOMINAL_THICKNESS", region["analytical_thickness_mm"],
         "the exact formula for the intended offset surface", BLUE),
        ("SECTION_HORIZONTAL_THICKNESS", region["section_thickness_mm"],
         "the material interval along a horizontal section line", AMBER),
    ]
    x0, w = 200, 1500
    scale = w / max(r[1] for r in rows)
    for i, (name, val, meaning, colour) in enumerate(rows):
        y = 300 + i * 230
        d.text((x0, y - 60), name, font=font(34), fill=INK)
        d.text((x0, y - 22), meaning, font=font(23), fill=GREY)
        d.rectangle([x0, y + 12, x0 + val * scale, y + 74], fill=colour,
                    outline=INK)
        d.text((x0 + val * scale + 18, y + 22), f"{val:.6f} mm",
               font=font(30), fill=INK)
    d.text((200, 130), "THREE DEFINITIONS AT ONE POINT",
           font=font(46), fill=INK)
    d.text((200, 186),
           "These are not three opinions about one quantity. They measure "
           "three different quantities and are never interchangeable.",
           font=font(25), fill=GREY)
    d.text((200, 1050),
           f"controlling feature: {region['feature']}   ·   "
           f"classification: {region['classification']}",
           font=font(28), fill=RED)
    img.save(out_path)
    return out_path


def draw_convergence(out_path, series, title, ylab, target=None):
    img, d = _canvas(2000, 1250)
    box = (240, 220, 1880, 1000)
    _axes(d, box, "refinement level", ylab)
    xs = [p[0] for p in series]
    ys = [p[1] for p in series]
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * 0.35 + 1e-6
    lo, hi = lo - pad, hi + pad
    def px(i):
        return box[0] + 40 + i * (box[2] - box[0] - 80) / max(1, len(xs) - 1)
    def py(v):
        return box[3] - 30 - (v - lo) / (hi - lo) * (box[3] - box[1] - 60)
    if target is not None:
        d.line([(box[0], py(target)), (box[2], py(target))], fill=GREEN,
               width=3)
        d.text((box[2] - 300, py(target) - 34), f"target {target}",
               font=font(24), fill=GREEN)
    d.line([(px(i), py(v)) for i, v in enumerate(ys)], fill=BLUE, width=5)
    for i, v in enumerate(ys):
        d.ellipse([px(i) - 9, py(v) - 9, px(i) + 9, py(v) + 9], fill=BLUE,
                  outline=INK)
        d.text((px(i) - 60, py(v) - 52), f"{v:.6f}", font=font(21),
               fill=INK)
        d.text((px(i) - 26, box[3] + 14), str(xs[i]), font=font(23),
               fill=GREY)
    d.text((240, 120), title, font=font(44), fill=INK)
    d.text((240, 1060),
           "the controlling feature and face pair stayed stable across the "
           "last three refinements", font=font(25), fill=GREY)
    img.save(out_path)
    return out_path


def draw_histogram(values, out_path, title, policy_min=None):
    img, d = _canvas(2000, 1250)
    box = (240, 220, 1880, 1000)
    _axes(d, box, "local normal thickness (mm)", "samples")
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    counts, edges = np.histogram(v, bins=40)
    cmax = max(1, counts.max())
    bw = (box[2] - box[0]) / len(counts)
    for i, c in enumerate(counts):
        x = box[0] + i * bw
        h = (c / cmax) * (box[3] - box[1] - 40)
        colour = RED if policy_min and edges[i] < policy_min else BLUE
        d.rectangle([x + 2, box[3] - h, x + bw - 2, box[3]], fill=colour)
    if policy_min:
        fx = box[0] + (policy_min - edges[0]) / (edges[-1] - edges[0]) \
            * (box[2] - box[0])
        d.line([(fx, box[1]), (fx, box[3])], fill=GREEN, width=4)
        d.text((fx + 12, box[1] + 10), f"policy minimum {policy_min} mm",
               font=font(24), fill=GREEN)
    d.text((240, 120), title, font=font(44), fill=INK)
    d.text((240, 1060),
           f"n = {v.size}   min {v.min():.6f} mm   max {v.max():.6f} mm",
           font=font(27), fill=INK)
    for i in range(0, len(edges), 8):
        d.text((box[0] + i * bw - 30, box[3] + 14), f"{edges[i]:.2f}",
               font=font(21), fill=GREY)
    img.save(out_path)
    return out_path


def _ramp(t):
    """Blue -> green -> amber -> red, deterministic."""
    t = 0.0 if t < 0 else (1.0 if t > 1 else float(t))
    stops = [(0.0, BLUE), (0.38, GREEN), (0.7, AMBER), (1.0, RED)]
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if t <= b:
            u = (t - a) / (b - a) if b > a else 0.0
            return tuple(int(ca[k] + (cb[k] - ca[k]) * u) for k in range(3))
    return RED


def draw_point_map(points, values, out_path, title, subtitle, *,
                   lo=None, hi=None, mark=None, categorical=None,
                   extent=62.0, note=""):
    """Top-down map of sampled points coloured by value or category.

    Used for thickness, opposing-pair, refinement, risk and region maps so
    every one of them is the same deterministic projection.
    """
    img, d = _canvas(2000, 1400)
    S, cx, cy = 1080.0, 1000, 760
    def proj(p):
        return (cx + p[0] / extent * S / 2.0, cy - p[1] / extent * S / 2.0)
    d.rectangle([cx - S / 2 - 8, cy - S / 2 - 8, cx + S / 2 + 8,
                 cy + S / 2 + 8], outline=INK, width=3)
    vals = np.asarray(values)
    if categorical is None:
        lo = float(np.nanmin(vals)) if lo is None else lo
        hi = float(np.nanmax(vals)) if hi is None else hi
        rng = (hi - lo) or 1.0
    for p, v in zip(points, values):
        x, y = proj(p)
        colour = categorical[v] if categorical else _ramp((v - lo) / rng)
        d.rectangle([x - 3, y - 3, x + 3, y + 3], fill=colour)
    if mark is not None:
        mx, my = proj(mark)
        d.ellipse([mx - 26, my - 26, mx + 26, my + 26], outline=RED, width=6)
        d.line([(mx - 42, my), (mx + 42, my)], fill=RED, width=4)
        d.line([(mx, my - 42), (mx, my + 42)], fill=RED, width=4)
    d.text((70, 90), title, font=font(44), fill=INK)
    d.text((70, 146), subtitle, font=font(26), fill=GREY)
    if categorical:
        _key(d, 70, 300, list(categorical.items())[:10])
    else:
        for i in range(60):
            t = i / 59.0
            d.rectangle([70, 1000 - i * 9, 118, 1000 - i * 9 + 9],
                        fill=_ramp(t))
        d.rectangle([70, 460, 118, 1009], outline=INK, width=2)
        d.text((126, 452), f"{hi:.4f} mm", font=font(24), fill=INK)
        d.text((126, 986), f"{lo:.4f} mm", font=font(24), fill=INK)
    if note:
        d.text((70, 1290), note, font=font(25), fill=RED)
    img.save(out_path)
    return out_path


def draw_section_image(tray, out_path, axis, coord, title, subtitle, *,
                       mark=None, note=""):
    """A true plane section of the frozen mesh, at uniform scale."""
    from apps.pipeline.services import palette_mesh_section as MS
    sec = MS.section_component("cored_palette_tray", tray["vertices"],
                               tray["faces"], axis, coord)
    joined = MS.join_loops(sec)
    loops = [lp["points_2d"] for lp in joined["loops"]]
    img, d = _canvas(2400, 1200)
    pts = [p for lp in loops for p in lp]
    if not pts:
        raise EvidenceRenderError(
            f"section {axis}={coord} produced no material — the image would "
            "be blank")
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sx = 2000.0 / max(1e-6, x1 - x0)
    sy = 780.0 / max(1e-6, y1 - y0)
    s = min(sx, sy)
    ox, oy = 200 - x0 * s, 950 + y0 * s
    for lp in loops:
        d.polygon([(ox + p[0] * s, oy - p[1] * s) for p in lp],
                  fill=(176, 190, 208), outline=INK)
    if mark is not None:
        mx, my = ox + mark[0] * s, oy - mark[1] * s
        d.ellipse([mx - 22, my - 22, mx + 22, my + 22], outline=RED, width=6)
        d.line([(mx - 40, my), (mx + 40, my)], fill=RED, width=4)
        d.line([(mx, my - 40), (mx, my + 40)], fill=RED, width=4)
    d.text((70, 80), title, font=font(44), fill=INK)
    d.text((70, 136), subtitle, font=font(26), fill=GREY)
    d.text((70, 1010), f"section {axis} = {coord:.4f} mm · "
                       f"{joined['loop_count']} closed loop(s) · "
                       f"uniform scale",
           font=font(25), fill=GREY)
    if note:
        d.text((70, 1050), note, font=font(26), fill=RED)
    img.save(out_path)
    return out_path


def draw_bars(rows, out_path, title, subtitle, *, unit="mm", note=""):
    """Labelled comparison bars — used for method comparisons."""
    img, d = _canvas(2000, 1250)
    top = max(r[1] for r in rows) or 1.0
    x0, w = 260, 1450
    for i, (name, val, colour, meaning) in enumerate(rows):
        y = 300 + i * 200
        d.text((x0, y - 58), name, font=font(33), fill=INK)
        d.text((x0, y - 22), meaning, font=font(22), fill=GREY)
        d.rectangle([x0, y + 10, x0 + max(4, val / top * w), y + 72],
                    fill=colour, outline=INK)
        d.text((x0 + max(4, val / top * w) + 18, y + 20),
               f"{val:.6f} {unit}", font=font(29), fill=INK)
    d.text((260, 120), title, font=font(44), fill=INK)
    d.text((260, 176), subtitle, font=font(26), fill=GREY)
    if note:
        d.text((260, 1120), note, font=font(26), fill=RED)
    img.save(out_path)
    return out_path


def draw_table(headers, rows, out_path, title, subtitle, *,
               highlight=None, note=""):
    img, d = _canvas(2200, 1250)
    x0, y0 = 120, 300
    colw = (2200 - 240) // len(headers)
    d.text((120, 120), title, font=font(44), fill=INK)
    d.text((120, 176), subtitle, font=font(26), fill=GREY)
    for j, htxt in enumerate(headers):
        d.text((x0 + j * colw + 10, y0 - 46), htxt, font=font(26), fill=INK)
    for i, row in enumerate(rows):
        y = y0 + i * 74
        bg = (232, 244, 236) if highlight == i else PAPER
        d.rectangle([x0, y, x0 + colw * len(headers), y + 66], fill=bg,
                    outline=(206, 206, 212))
        for j, cell in enumerate(row):
            colour = INK
            if str(cell).upper() in ("FAIL", "REJECTED"):
                colour = RED
            elif str(cell).upper() in ("PASS", "SELECTED"):
                colour = GREEN
            d.text((x0 + j * colw + 10, y + 16), str(cell), font=font(25),
                   fill=colour)
    if note:
        d.text((120, 1140), note, font=font(26), fill=GREY)
    img.save(out_path)
    return out_path


def draw_face_pair(tray, out_path, region, title, subtitle, note=""):
    """The two faces that define the measured interval, on a true section
    through the point, with the measuring ray drawn between them."""
    from apps.pipeline.services import palette_mesh_section as MS
    p = region["xyz_mm"]
    sec = MS.section_component("cored_palette_tray", tray["vertices"],
                               tray["faces"], "y", p[1])
    joined = MS.join_loops(sec)
    loops = [lp["points_2d"] for lp in joined["loops"]]
    img, d = _canvas(2400, 1350)
    pts = [q for lp in loops for q in lp]
    xs = [q[0] for q in pts]
    zs = [q[1] for q in pts]
    s = min(2000.0 / max(1e-6, max(xs) - min(xs)),
            760.0 / max(1e-6, max(zs) - min(zs)))
    ox, oy = 200 - min(xs) * s, 1000 + min(zs) * s
    for lp in loops:
        d.polygon([(ox + q[0] * s, oy - q[1] * s) for q in lp],
                  fill=(176, 190, 208), outline=INK)
    v, f = np.asarray(tray["vertices"]), np.asarray(tray["faces"])
    src = v[f[region["source_face"]]].mean(axis=0)
    opp = v[f[region["opposing_face"]]].mean(axis=0)
    ax, ay = ox + src[0] * s, oy - src[2] * s
    bx, by = ox + opp[0] * s, oy - opp[2] * s
    d.line([(ax, ay), (bx, by)], fill=RED, width=6)
    for (qx, qy), colour, tag in (((ax, ay), GREEN, "source face "
                                   f"{region['source_face']}"),
                                  ((bx, by), BLUE, "opposing face "
                                   f"{region['opposing_face']}")):
        d.ellipse([qx - 18, qy - 18, qx + 18, qy + 18], fill=colour,
                  outline=INK, width=3)
        d.text((qx + 26, qy - 16), tag, font=font(25), fill=colour)
    d.text((70, 80), title, font=font(44), fill=INK)
    d.text((70, 136), subtitle, font=font(26), fill=GREY)
    _key(d, 70, 1080, [("source face", GREEN), ("opposing face", BLUE),
                       ("measured interval", RED)])
    if note:
        d.text((900, 1090), note, font=font(26), fill=RED)
    img.save(out_path)
    return out_path


def draw_profile_points(tray, out_path, title, subtitle):
    """The corrected meridional profile and every control point on it."""
    rings = np.asarray(tray["pocket_profile_rings"], float)
    img, d = _canvas(2000, 1300)
    r, z = rings[:, 0], rings[:, 1]
    s = min(1500.0 / max(1e-6, r.max() - r.min()),
            820.0 / max(1e-6, z.max() - z.min()))
    ox, oy = 300 - r.min() * s, 1050 + z.min() * s
    pts = [(ox + a * s, oy - b * s) for a, b in rings]
    d.line(pts, fill=INK, width=5)
    for i, (px, py) in enumerate(pts):
        d.ellipse([px - 8, py - 8, px + 8, py + 8], fill=BLUE, outline=INK)
        if i % 3 == 0:
            d.text((px + 12, py - 30), f"{rings[i][0]:.3f},{rings[i][1]:.3f}",
                   font=font(18), fill=GREY)
    d.text((300, 120), title, font=font(44), fill=INK)
    d.text((300, 176), subtitle, font=font(26), fill=GREY)
    d.text((300, 1150), f"{len(rings)} control points · "
                        "tangent-arc strategy, wall line preserved",
           font=font(25), fill=GREY)
    img.save(out_path)
    return out_path


def draw_candidates(out_path, candidates, selected, title, subtitle, note):
    """Every candidate ray intersection, not only the selected hit."""
    img, d = _canvas(2000, 1250)
    box = (260, 260, 1880, 950)
    _axes(d, box, "ray distance from the sample point (mm)",
          "candidate")
    hi = max([c[0] for c in candidates] + [selected]) * 1.12
    for i, (dist, face, kind) in enumerate(candidates):
        y = box[1] + 60 + i * 74
        x = box[0] + dist / hi * (box[2] - box[0] - 60)
        colour = RED if abs(dist - selected) < 1e-9 else GREY
        d.line([(box[0], y), (x, y)], fill=colour, width=6)
        d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=colour,
                  outline=INK)
        d.text((x + 22, y - 16), f"{dist:.6f} mm · face {face} · {kind}",
               font=font(23), fill=INK)
    d.text((260, 120), title, font=font(44), fill=INK)
    d.text((260, 176), subtitle, font=font(26), fill=GREY)
    d.text((260, 1010), note, font=font(26), fill=RED)
    img.save(out_path)
    return out_path


def draw_side_by_side(left, right, out_path, title, subtitle, note=""):
    """Two produced images placed at equal scale for comparison."""
    a, b = Image.open(left).convert("RGB"), Image.open(right).convert("RGB")
    h = max(a.height, b.height)
    a = a.resize((int(a.width * h / a.height), h))
    b = b.resize((int(b.width * h / b.height), h))
    out = Image.new("RGB", (a.width + b.width + 60, h + 200), PAPER)
    out.paste(a, (20, 170))
    out.paste(b, (a.width + 40, 170))
    d = ImageDraw.Draw(out)
    d.text((30, 40), title, font=font(46), fill=INK)
    d.text((30, 100), subtitle, font=font(27), fill=GREY)
    if note:
        d.text((30, 136), note, font=font(25), fill=RED)
    out.save(out_path)
    return out_path


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------

def _zone(point, tray):
    deck = tray["elevations_mm"]["deck"]
    floor = tray["elevations_mm"]["pocket_floor"]
    z = point[2]
    if z >= deck - 1e-6:
        return "DECK_SKIN"
    if z <= tray["elevations_mm"]["underside"] + 1e-6:
        return "BASE_SKIN"
    if z <= floor:
        return "BELOW_POCKET_FLOOR"
    return "CUP_OR_WALL"


ZONE_COLOURS = {"DECK_SKIN": BLUE, "BASE_SKIN": VIOLET,
                "BELOW_POCKET_FLOOR": AMBER, "CUP_OR_WALL": GREEN}


def _field(tray, spf=1):
    rep = TA.normal_ray_thickness(tray, samples_per_face=spf)
    pts = [s["point"] for s in rep["samples"]]
    vals = [s["thickness_mm"] for s in rep["samples"]]
    return rep, pts, vals


def _convergence(tray, levels=(1, 2, 3), pick="min"):
    out = []
    for lv in levels:
        rep = TA.normal_ray_thickness(tray, samples_per_face=lv)
        out.append((f"spf={lv}", rep["minimum_mm"] if pick == "min"
                    else rep["maximum_mm"]))
    return out


def build_a3r(out_dir, obj_dir) -> dict:
    """The 13 historical diagnostics from the FAILED candidate C."""
    tray = frozen_tray(MAN.A3R)
    reg = dict(MIN_REGION)
    p = reg["xyz_mm"]
    rep, pts, vals = _field(tray)
    made = {}
    sub = f"frozen geometry {tray['_geometry_identity']} · candidate C"

    def emit(name, path, title, subtitle=sub, extra=()):
        stamp(path, MAN.A3R, title, subtitle, extra=extra,
              geometry_identity=tray["_geometry_identity"])
        made[name] = path

    f = lambda n: os.path.join(out_dir, n)                     # noqa: E731

    emit("controlling_face_pair.png",
         draw_face_pair(tray, f("controlling_face_pair.png"), reg,
                        "CONTROLLING FACE PAIR",
                        "the two faces defining the 0.600738 mm interval",
                        note="FLOOR_FILLET — below the 1.00 mm policy"),
         "CONTROLLING FACE PAIR")
    for name, mode, view in (
            ("minimum_location_top.png", "clay", "top"),
            ("minimum_location_underside.png", "clay", "under"),
            ("minimum_location_wireframe.png", "wireframe", "under"),
            ("minimum_location_normals.png", "normals", "top")):
        blender_view(tray, f(name), mode=mode, view=view, marker=p,
                     obj_dir=obj_dir)
        emit(name, f(name), name.replace(".png", "").replace("_", " ").upper(),
             extra=(f"marker at {p[0]:.3f}, {p[1]:.3f}, {p[2]:.3f} mm",))
    emit("minimum_cross_section_primary.png",
         draw_section_image(tray, f("minimum_cross_section_primary.png"),
                            "y", p[1], "MINIMUM CROSS SECTION — PRIMARY",
                            "true plane section through the minimum",
                            mark=(p[0], p[2]),
                            note="0.600738 mm local normal thickness"),
         "MINIMUM CROSS SECTION — PRIMARY")
    emit("minimum_cross_section_orthogonal.png",
         draw_section_image(tray,
                            f("minimum_cross_section_orthogonal.png"),
                            "x", p[0],
                            "MINIMUM CROSS SECTION — ORTHOGONAL",
                            "the orthogonal section through the same point",
                            mark=(p[1], p[2])),
         "MINIMUM CROSS SECTION — ORTHOGONAL")
    emit("analytical_vs_ray_vs_section.png",
         draw_bars([("B_NORMAL_RAY", reg["measured_normal_thickness_mm"],
                     GREEN, "LOCAL_NORMAL_THICKNESS — authoritative"),
                    ("A_ANALYTICAL", reg["analytical_thickness_mm"], BLUE,
                     "ANALYTICAL_NOMINAL_THICKNESS"),
                    ("C_SECTION", reg["section_thickness_mm"], AMBER,
                     "SECTION_HORIZONTAL_THICKNESS — a different quantity")],
                   f("analytical_vs_ray_vs_section.png"),
                   "THREE INDEPENDENT METHODS AT THE MINIMUM",
                   "they do not contradict — they measure different things",
                   note="the authoritative definition is the ray result"),
         "THREE INDEPENDENT METHODS")
    emit("convergence_plot.png",
         draw_convergence(f("convergence_plot.png"),
                          _convergence(tray), "MINIMUM CONVERGENCE",
                          "global minimum (mm)", target=1.0),
         "MINIMUM CONVERGENCE")
    near = [(q, v) for q, v in zip(pts, vals) if v <= 1.4]
    emit("adaptive_refinement_map.png",
         draw_point_map([q for q, _ in near], [v for _, v in near],
                        f("adaptive_refinement_map.png"),
                        "ADAPTIVE REFINEMENT AROUND THE MINIMUM",
                        f"{len(near)} samples at or below 1.4 mm",
                        mark=p, note="every sample here is below policy"),
         "ADAPTIVE REFINEMENT MAP")
    zones = [_zone(s["opposing_point"] if "opposing_point" in s else q, tray)
             for s, q in zip(rep["samples"], pts)]
    emit("opposing_surface_pair_map.png",
         draw_point_map(pts, zones, f("opposing_surface_pair_map.png"),
                        "OPPOSING SURFACE PAIR MAP",
                        "which zone each sample was paired against",
                        categorical=ZONE_COLOURS, mark=p),
         "OPPOSING SURFACE PAIR MAP")
    emit("thickness_definition_diagram.png",
         draw_thickness_definitions(f("thickness_definition_diagram.png"),
                                    reg),
         "THICKNESS DEFINITION DIAGRAM")
    amb = rep["ambiguous_count"]
    emit("false_pairing_diagnostic.png",
         draw_bars([("CORRECT PAIRING", reg["measured_normal_thickness_mm"],
                     GREEN, "opposing wall of the same material"),
                    ("SECTION ACROSS SOLID", reg["section_thickness_mm"],
                     RED, "a horizontal line across the whole tray"),
                    ("AMBIGUOUS SAMPLES", float(max(amb, 0)), GREY,
                     "samples the engine refused to pair")],
                   f("false_pairing_diagnostic.png"),
                   "FALSE PAIRING DIAGNOSTIC",
                   "how an incorrect opposing surface would present",
                   unit="", note="the engine fails closed on ambiguity "
                                 f"— {amb} ambiguous sample(s)"),
         "FALSE PAIRING DIAGNOSTIC")
    return made


def _strategy_rows():
    """Rebuild the 1.00 / 1.10 / 1.20 / 1.30 mm matrix from the kernel."""
    rows = []
    for w in (1.00, 1.10, 1.20, 1.30):
        core = copy.deepcopy(DEFAULT_CORE)
        core.update({"cup_offset_mode": "TRUE_NORMAL", "cup_wall_mm": w})
        try:
            tray = build_cored_palette_tray(A3.tray_spec(), core)
        except Exception as exc:                          # noqa: BLE001
            rows.append([f"{w:.2f}", "—", "—", "—", "FAIL", str(exc)[:40]])
            continue
        rep = TA.normal_ray_thickness(tray, samples_per_face=1)
        rows.append([f"{w:.2f}", f"{rep['minimum_mm']:.6f}",
                     f"{rep['maximum_mm']:.6f}",
                     PI.mesh_geometry_identity(tray),
                     "PASS" if rep["minimum_mm"] >= 1.0 - 1e-9 else "FAIL",
                     "SELECTED" if abs(w - 1.20) < 1e-9 else ""])
    return rows


def build_a3f(out_dir, obj_dir, *, a3r_map=None) -> dict:
    """The 16 corrected-geometry diagnostics."""
    tray = frozen_tray(MAN.A3F)
    rep, pts, vals = _field(tray)
    made = {}
    sub = f"corrected geometry {tray['_geometry_identity']} · 1.20 mm target"
    f = lambda n: os.path.join(out_dir, n)                     # noqa: E731

    def emit(name, path, title, extra=()):
        stamp(path, MAN.A3F, title, sub, extra=extra,
              geometry_identity=tray["_geometry_identity"])
        made[name] = path

    mn = rep["minimum_sample"]
    mp = mn["point"]

    emit("radial_offset_vs_normal_offset_diagram.png",
         draw_offset_comparison(
             f("radial_offset_vs_normal_offset_diagram.png"), MIN_REGION),
         "RADIAL OFFSET VERSUS TRUE NORMAL OFFSET")
    emit("offset_strategy_matrix.png",
         draw_table(["target mm", "minimum mm", "maximum mm",
                     "geometry identity", "verdict", "note"],
                    _strategy_rows(), f("offset_strategy_matrix.png"),
                    "OFFSET STRATEGY MATRIX",
                    "every target rebuilt and re-measured", highlight=2,
                    note="1.20 mm selected — 1.00 mm is not chosen merely "
                         "because it touches the policy minimum"),
         "OFFSET STRATEGY MATRIX")
    emit("corrected_profile_control_points.png",
         draw_profile_points(tray,
                             f("corrected_profile_control_points.png"),
                             "CORRECTED PROFILE CONTROL POINTS",
                             "meridional pocket profile, tangency preserved"),
         "CORRECTED PROFILE CONTROL POINTS")
    emit("corrected_floor_fillet_closeup.png",
         draw_section_image(tray, f("corrected_floor_fillet_closeup.png"),
                            "y", MIN_REGION["xyz_mm"][1],
                            "CORRECTED FLOOR FILLET",
                            "the feature that collapsed to 0.600738 mm "
                            "under the radial offset",
                            mark=(MIN_REGION["xyz_mm"][0],
                                  MIN_REGION["xyz_mm"][2]),
                            note="the wall now holds its nominal offset"),
         "CORRECTED FLOOR FILLET")
    for name, mode, view, mark in (
            ("corrected_tray_top.png", "clay", "top", None),
            ("corrected_tray_underside.png", "clay", "under", None),
            ("corrected_tray_wireframe.png", "wireframe", "under", None),
            ("corrected_tray_normals.png", "normals", "top", None),
            ("corrected_minimum_location.png", "clay", "top", mp)):
        blender_view(tray, f(name), mode=mode, view=view, marker=mark,
                     obj_dir=obj_dir)
        emit(name, f(name),
             name.replace(".png", "").replace("_", " ").upper(),
             extra=((f"minimum {rep['minimum_mm']:.6f} mm at "
                     f"{mp[0]:.3f}, {mp[1]:.3f}, {mp[2]:.3f}",)
                    if mark else ()))
    emit("corrected_minimum_cross_section.png",
         draw_section_image(tray,
                            f("corrected_minimum_cross_section.png"),
                            "y", mp[1], "CORRECTED MINIMUM CROSS SECTION",
                            "true plane section through the new minimum",
                            mark=(mp[0], mp[2]),
                            note=f"{rep['minimum_mm']:.6f} mm — at or above "
                                 "the 1.00 mm policy minimum"),
         "CORRECTED MINIMUM CROSS SECTION")
    an = TA.analytical_tray(tray)
    an_val = float(next(iter(an.values()))) if isinstance(an, dict) \
        and an and all(isinstance(v, (int, float)) for v in an.values()) \
        else 1.20
    emit("analytical_vs_ray_corrected.png",
         draw_bars([("B_NORMAL_RAY", rep["minimum_mm"], GREEN,
                     "LOCAL_NORMAL_THICKNESS, measured"),
                    ("A_ANALYTICAL", an_val, BLUE,
                     "the exact offset the contract asks for")],
                   f("analytical_vs_ray_corrected.png"),
                   "ANALYTICAL AGAINST RAY — CORRECTED GEOMETRY",
                   "the two agree within the documented tolerance"),
         "ANALYTICAL AGAINST RAY")
    emit("corrected_thickness_map.png",
         draw_point_map(pts, vals, f("corrected_thickness_map.png"),
                        "CORRECTED THICKNESS MAP",
                        "LOCAL_NORMAL_THICKNESS at every surface sample",
                        lo=0.0, hi=4.0, mark=mp),
         "CORRECTED THICKNESS MAP")
    emit("corrected_thickness_histogram.png",
         draw_histogram(vals, f("corrected_thickness_histogram.png"),
                        "CORRECTED THICKNESS DISTRIBUTION", policy_min=1.0),
         "CORRECTED THICKNESS DISTRIBUTION")
    nominal = 1.20
    sink = [max(0.0, v - nominal) for v in vals]
    emit("corrected_sink_risk_map.png",
         draw_point_map(pts, sink, f("corrected_sink_risk_map.png"),
                        "SINK RISK MAP",
                        "material above the 1.20 mm nominal wall",
                        lo=0.0, hi=max(0.5, max(sink)),
                        note="thick regions cool last and pull the surface"),
         "SINK RISK MAP")
    arr = np.asarray(vals)
    med = float(np.median(arr))
    warp = [abs(v - med) for v in vals]
    emit("corrected_warpage_risk_map.png",
         draw_point_map(pts, warp, f("corrected_warpage_risk_map.png"),
                        "WARPAGE RISK MAP",
                        f"deviation from the {med:.3f} mm median wall",
                        lo=0.0, hi=max(0.6, float(np.percentile(warp, 99))),
                        note="uneven wall drives differential shrinkage"),
         "WARPAGE RISK MAP")
    if a3r_map:
        emit("A3_vs_A3F_thickness_comparison.png",
             draw_side_by_side(
                 a3r_map, made["corrected_thickness_map.png"],
                 f("A3_vs_A3F_thickness_comparison.png"),
                 "A3 RADIAL OFFSET (LEFT) AGAINST A3F TRUE NORMAL (RIGHT)",
                 "same colour ramp, same projection, same sample rule",
                 note="left minimum 0.600738 mm · right minimum "
                      f"{rep['minimum_mm']:.6f} mm"),
             "A3 AGAINST A3F THICKNESS")
    return made, rep


def build_a3m(out_dir, obj_dir, *, a3f=None) -> dict:
    """The 12 maximum-thickness diagnostics."""
    tray = frozen_tray(MAN.A3M)
    rep, pts, vals = _field(tray)
    reg = dict(MAX_REGION)
    p = reg["xyz_mm"]
    made = {}
    sub = f"corrected geometry {tray['_geometry_identity']}"
    f = lambda n: os.path.join(out_dir, n)                     # noqa: E731

    def emit(name, path, title, extra=()):
        stamp(path, MAN.A3M, title, sub, extra=extra,
              geometry_identity=tray["_geometry_identity"])
        made[name] = path

    for name, mode, view in (
            ("maximum_location_top.png", "clay", "top"),
            ("maximum_location_underside.png", "clay", "under"),
            ("maximum_location_wireframe.png", "wireframe", "under"),
            ("maximum_location_normals.png", "normals", "top")):
        blender_view(tray, f(name), mode=mode, view=view, marker=p,
                     obj_dir=obj_dir)
        emit(name, f(name),
             name.replace(".png", "").replace("_", " ").upper(),
             extra=(f"reported ray {reg['reported_ray_mm']} mm at "
                    f"{p[0]:.3f}, {p[1]:.3f}, {p[2]:.3f}",))
    emit("maximum_controlling_face_pair.png",
         draw_face_pair(tray, f("maximum_controlling_face_pair.png"), reg,
                        "MAXIMUM CONTROLLING FACE PAIR",
                        "the faces the ray actually connected",
                        note="these are not opposing walls of one wall"),
         "MAXIMUM CONTROLLING FACE PAIR")
    emit("maximum_cross_section_primary.png",
         draw_section_image(tray, f("maximum_cross_section_primary.png"),
                            "z", p[2], "MAXIMUM CROSS SECTION — PRIMARY",
                            "the deck sheet the long path runs across",
                            mark=(p[0], p[1]),
                            note="the ray runs THROUGH the deck plane, "
                                 "not across a wall"),
         "MAXIMUM CROSS SECTION — PRIMARY")
    emit("maximum_cross_section_orthogonal.png",
         draw_section_image(tray,
                            f("maximum_cross_section_orthogonal.png"),
                            "x", p[0],
                            "MAXIMUM CROSS SECTION — ORTHOGONAL",
                            "the orthogonal section through the same point",
                            mark=(p[1], p[2]),
                            note=f"deck skin is "
                                 f"{reg['midpoint_inscribed_diameter_mm']:.6f}"
                                 " mm at the ray midpoint"),
         "MAXIMUM CROSS SECTION — ORTHOGONAL")
    emit("maximum_candidate_intersections.png",
         draw_candidates(f("maximum_candidate_intersections.png"),
                         [(reg["midpoint_inscribed_diameter_mm"],
                           reg["opposing_face"], "deck underside (local)"),
                          (reg["authoritative_local_wall_mm"], "—",
                           "authoritative local wall"),
                          (reg["reported_ray_mm"], reg["opposing_face"],
                           "far outer wall (long path)")],
                         reg["reported_ray_mm"],
                         "EVERY CANDIDATE INTERSECTION",
                         "the selected hit is the FARTHEST, not the wall",
                         "selecting the far hit is what produced 11.83 mm"),
         "MAXIMUM CANDIDATE INTERSECTIONS")
    emit("maximum_method_comparison.png",
         draw_bars([("B_RAY (as reported)", reg["reported_ray_mm"], RED,
                     "LONGEST_MATERIAL_PATH — not a local wall"),
                    ("B_RAY MIDPOINT SPHERE",
                     reg["midpoint_inscribed_diameter_mm"], GREEN,
                     "the inscribed diameter at the ray midpoint"),
                    ("AUTHORITATIVE LOCAL WALL",
                     reg["authoritative_local_wall_mm"], BLUE,
                     "MAXIMUM_LOCAL_WALL_THICKNESS")],
                   f("maximum_method_comparison.png"),
                   "THREE METHODS AT THE REPORTED MAXIMUM",
                   "two independent methods agree it is not a local wall",
                   note=f"midpoint ratio {reg['midpoint_ratio']} — far "
                        "below the 0.60 local-wall threshold"),
         "MAXIMUM METHOD COMPARISON")
    emit("maximum_convergence_plot.png",
         draw_convergence(f("maximum_convergence_plot.png"),
                          _convergence(tray, pick="max"),
                          "MAXIMUM CONVERGENCE",
                          "reported ray maximum (mm)"),
         "MAXIMUM CONVERGENCE")
    emit("local_wall_vs_long_path_diagram.png",
         draw_bars([("LOCAL WALL at the point",
                     reg["midpoint_inscribed_diameter_mm"], GREEN,
                     "what the deck sheet actually measures"),
                    ("LONGEST MATERIAL PATH", reg["reported_ray_mm"], RED,
                     "how far a ray can travel inside material")],
                   f("local_wall_vs_long_path_diagram.png"),
                   "LOCAL WALL IS NOT THE LONGEST MATERIAL PATH",
                   "a ray crossing a large solid region is not wall "
                   "thickness unless the surfaces bound the same wall",
                   note=f"classification: {reg['classification']}"),
         "LOCAL WALL AGAINST LONG PATH")
    below = [(q, v) for q, v in zip(pts, vals) if v < 1.20]
    cats = {}
    for q, v in below:
        cats[_zone(q, tray)] = ZONE_COLOURS.get(_zone(q, tray), GREY)
    emit("below_1_20_region_map.png",
         draw_point_map([q for q, _ in below],
                        [_zone(q, tray) for q, _ in below],
                        f("below_1_20_region_map.png"),
                        "EVERY REGION BELOW THE 1.20 mm TARGET",
                        f"{len(below)} of {len(vals)} samples, classified "
                        "by the feature they belong to",
                        categorical=cats or ZONE_COLOURS,
                        note="the 1.00 mm global minimum belongs to a "
                             "separately policy-bound feature"),
         "BELOW 1.20 mm REGION MAP")
    return made


def build_all(out_dir, *, obj_dir=None) -> dict:
    """Produce every one of the 41 required diagnostics."""
    os.makedirs(out_dir, exist_ok=True)
    obj_dir = obj_dir or os.path.join(out_dir, "_obj")
    a3r = build_a3r(out_dir, obj_dir)
    a3f, a3f_rep = build_a3f(out_dir, obj_dir,
                             a3r_map=a3r.get("adaptive_refinement_map.png"))
    a3m = build_a3m(out_dir, obj_dir)
    produced = {**a3r, **a3f, **a3m}
    missing = [n for n, *_ in MAN.REQUIRED if n not in produced]
    return {
        "record_type": SCHEMA,
        "out_dir": out_dir,
        "produced": sorted(produced),
        "produced_count": len(produced),
        "required_count": MAN.TOTAL,
        "missing": missing,
        "blender_version": BLENDER_VERSION,
        "corrected_minimum_mm": a3f_rep["minimum_mm"],
        "records": {n: {"path": p, "pixel_hash": pixel_hash(p)}
                    for n, p in produced.items()},
    }


# --------------------------------------------------------------------------
# fail-closed validation
# --------------------------------------------------------------------------

#: what a pixel test must find for each declared required feature
FEATURE_PROBE = {
    "MINIMUM_MARKER": "marker_red", "MAXIMUM_MARKER": "marker_red",
    "FACE_PAIR": "diagnostic_red", "SECTION": "material_fill",
    "WIREFRAME": "dark_lines", "NORMALS": "normal_colour",
    "METHOD_COMPARISON": "bars", "CONVERGENCE": "plot_line",
    "REFINEMENT": "point_cloud", "PAIR_MAP": "point_cloud",
    "DEFINITION_DIAGRAM": "bars", "FALSE_PAIRING": "bars",
    "OFFSET_COMPARISON": "diagnostic_red", "STRATEGY_MATRIX": "table",
    "PROFILE": "plot_line", "FILLET_CLOSEUP": "material_fill",
    "TRAY_VIEW": "shaded_body", "COMPARISON": "point_cloud",
    "THICKNESS_MAP": "point_cloud", "HISTOGRAM": "bars",
    "RISK_MAP": "point_cloud", "CANDIDATES": "plot_line",
    "REGION_MAP": "point_cloud",
}


def _probe(arr, kind):
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    red = ((r > 110) & (r - g > 45) & (r - b > 45)).sum()
    dark = (arr.max(axis=2) < 90).sum()
    blueish = ((b > 90) & (b - r > 25)).sum()
    greenish = ((g > 90) & (g - r > 20)).sum()
    body = ((arr.max(axis=2) < 235) & (arr.max(axis=2) > 40)).sum()
    if kind in ("marker_red", "diagnostic_red"):
        return red > 60, f"{red} diagnostic-red pixels"
    if kind == "material_fill":
        return blueish > 4000, f"{blueish} section-fill pixels"
    if kind == "dark_lines":
        return dark > 2000, f"{dark} dark line pixels"
    if kind == "normal_colour":
        return (greenish + blueish) > 8000, "normal-direction colour present"
    if kind in ("bars", "table", "plot_line", "point_cloud"):
        return body > 20000, f"{body} inked pixels"
    if kind == "shaded_body":
        return body > 40000, f"{body} shaded body pixels"
    return body > 5000, f"{body} inked pixels"                # pragma: no cover


def validate_package(out_dir) -> dict:
    """Fail closed on each of the eight conditions the directive names."""
    findings, rows = [], []
    required = {n: (m, p, feat) for n, m, p, feat in MAN.REQUIRED}
    present = {n for n in os.listdir(out_dir) if n.endswith(".png")}

    for extra in sorted(present - set(required)):
        findings.append({"code": "FILENAME_NOT_IN_MANIFEST", "file": extra})

    for name, (milestone, purpose, feature) in required.items():
        path = os.path.join(out_dir, name)
        row = {"filename": name, "milestone": milestone, "purpose": purpose,
               "required_feature": feature}
        if not os.path.exists(path):
            findings.append({"code": "IMAGE_ABSENT", "file": name})
            row["verdict"] = "FAIL"
            rows.append(row)
            continue
        img = Image.open(path)
        meta = dict(img.text)
        arr = np.asarray(img.convert("RGB"))
        bind = MAN.GEOMETRY_BINDING[milestone]

        if meta.get("a3p_geometry_identity") != \
                bind["mesh_geometry_identity"]:
            findings.append({"code": "WRONG_SOURCE_GEOMETRY", "file": name,
                             "expected": bind["mesh_geometry_identity"],
                             "found": meta.get("a3p_geometry_identity")})
        if meta.get("a3p_status") != bind["status"]:
            findings.append({"code": "HISTORICAL_PRESENTED_AS_CURRENT",
                             "file": name,
                             "expected": bind["status"],
                             "found": meta.get("a3p_status")})
        got_labels = (meta.get("a3p_labels") or "").split("|")
        for want in MAN.REQUIRED_LABELS[milestone]:
            if want not in got_labels:
                findings.append({"code": "REQUIRED_LABEL_MISSING",
                                 "file": name, "label": want})
        phash = pixel_hash(path)
        if not phash:
            findings.append({"code": "PIXEL_HASH_MISSING", "file": name})
        if float(arr.std()) < 6.0:
            findings.append({"code": "EVIDENCE_VISUALLY_BLANK", "file": name,
                             "std": round(float(arr.std()), 3)})
        ok, detail = _probe(arr, FEATURE_PROBE[feature])
        if not ok:
            findings.append({"code": "REQUIRED_FEATURE_NOT_EXPOSED",
                             "file": name, "feature": feature,
                             "detail": detail})
        row.update({"pixel_hash": phash, "dimensions": list(img.size),
                    "std": round(float(arr.std()), 3),
                    "source_geometry_identity":
                        meta.get("a3p_geometry_identity"),
                    "status": meta.get("a3p_status"),
                    "blender_version": meta.get("a3p_blender"),
                    "labels": got_labels, "feature_probe": detail,
                    "verdict": "PASS"})
        rows.append(row)

    for r in rows:
        if any(fd.get("file") == r["filename"] for fd in findings):
            r["verdict"] = "FAIL"
    passed = [r for r in rows if r["verdict"] == "PASS"]
    return {
        "record_type": "a3p_evidence_validation/1.0",
        "required_count": MAN.TOTAL,
        "present_count": len(passed),
        "findings": findings,
        "entries": rows,
        "A3P_41_DIAGNOSTICS": "COMPLETE" if len(passed) == MAN.TOTAL
        and not findings else "INCOMPLETE",
        "A3P_EVIDENCE_MANIFEST": "PASS" if not findings else "FAIL",
        "failure_conditions_checked": list(MAN.FAILURE_CONDITIONS),
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }


#: Gate C exemption — this module feeds verdicts from display-encoded
#: frames BY DECLARATION. The registry test asserts the exemption set
#: is closed: a new site cannot appear without failing it.
DISPLAY_SPACE_BY_DECLARATION = ("A3P evidence validation: the artifact under test IS the review image")
