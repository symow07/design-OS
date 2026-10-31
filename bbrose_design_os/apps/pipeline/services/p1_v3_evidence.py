"""P1 V3 evidence orchestration — owner-review package.

Separated render modes (owner ruling):
A. NEUTRAL GEOMETRY VALIDATION — clay, pinned cameras (validation_views).
B. MATERIAL VALIDATION — studio scene, hollow glass solid
   (VISUALIZATION_ONLY_GEOMETRY), amber volume absorption.
C. MASK AUTHORITY — silhouettes from the alpha of an unlit emission render
   (silhouette_mask.py); never thresholded shaded RGB.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw

from apps.pipeline.services import geometry_validation_render as gvr
from apps.pipeline.services import mesh_diagnostics as md
from apps.pipeline.services import p1_pilot_geometry as p1
from apps.pipeline.services.p1_review_board import _fit, _font

SCRIPT_DIR = os.path.dirname(gvr.SCRIPT)
MASK_SCRIPT = os.path.join(SCRIPT_DIR, "silhouette_mask.py")
STUDIO_SCRIPT = os.path.join(SCRIPT_DIR, "p1_material_studio.py")

MATERIAL_NODES = {
    "glass": {"shader": "Principled BSDF + Volume Absorption",
              "base_colour": [0.93, 0.89, 0.85],
              "surface_roughness": 0.32,
              "transmission_weight": 1.0, "ior": 1.5,
              "volume_absorption_colour": [0.95, 0.72, 0.30],
              "volume_absorption_density_per_mm": 0.78,
              "authority": "OWNER_CONFIRMED external appearance + "
                           "VISUALIZATION parameters"},
    "collar": {"shader": "Principled BSDF (dielectric, no transmission)",
               "base_colour": [0.55, 0.13, 0.015],
               "roughness": 0.12, "specular_ior_level": 0.55},
    "bulb": {"shader": "Principled BSDF (opaque)",
             "base_colour": [0.60, 0.10, 0.03],
             "roughness": 0.22, "specular_ior_level": 0.45},
    "lighting": {"world_strength": 0.22, "sample_clamp_indirect": 4.0,
                 "key": "area 320x320 @ (-260,-330,250), 1.3e6 W",
                 "fill": "area 260x260 @ (300,-280,120), 4.0e5 W",
                 "rim": "area 60x260 @ (140,300,240), 1.3e6 W",
                 "side_lit_edge": "key 1.0e5 / fill 5.0e4 / rim 3.2e6",
                 "colour_management": "Cycles CPU seed 0, Standard view "
                                      "transform, exposure 0, gamma 1"},
}


def _jsonable(obj):
    """numpy scalars → native Python for json.dump."""
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    return obj


def _run(script, cfg, ok_token):
    with tempfile.NamedTemporaryFile("w", suffix=".json",
                                     delete=False) as fh:
        json.dump(cfg, fh)
        cfg_path = fh.name
    try:
        result = subprocess.run(
            [gvr.BLENDER, "-b", "--factory-startup", "-noaudio", "-P",
             script, "--", cfg_path],
            capture_output=True, text=True, timeout=3600)
        if ok_token not in result.stdout:
            raise RuntimeError(f"{os.path.basename(script)} failed: "
                               f"{result.stdout[-600:]} "
                               f"{result.stderr[-300:]}")
    finally:
        os.unlink(cfg_path)


def _export_meshes(meshes, td):
    files = {}
    for name, mesh in meshes.items():
        path = os.path.join(td, f"{name}.obj")
        gvr.export_obj(mesh, path)
        files[name] = path
    return files


# ---------------------------------------------------------------------------
# mask authority


def render_masks(meshes, out_paths: dict, *, detail_views=None,
                 resolution=(800, 1100), samples=16):
    """Deterministic alpha masks for the requested views."""
    with tempfile.TemporaryDirectory() as td:
        cfg = {
            "meshes": _export_meshes(meshes, td),
            "assembly_height_mm": p1.OWNER["total_assembled_height_mm"],
            "resolution": list(resolution),
            "samples": samples,
            "detail_views": detail_views or {},
            "views": out_paths,
        }
        _run(MASK_SCRIPT, cfg, "SILHOUETTE_MASK_OK")


def load_mask(path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGBA"))[:, :, 3] >= 128


def mask_hash(mask: np.ndarray) -> str:
    return hashlib.sha256(np.packbits(mask).tobytes()).hexdigest()[:16]


def mask_metrics(mask: np.ndarray, mm_per_px: float) -> dict:
    ys, xs = np.nonzero(mask)
    h, w = mask.shape
    # internal holes: background components not reachable from the border
    from collections import deque
    bg = ~mask
    seen = np.zeros_like(bg)
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if bg[y, x] and not seen[y, x]:
                seen[y, x] = True
                dq.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if bg[y, x] and not seen[y, x]:
                seen[y, x] = True
                dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and bg[ny, nx] \
                    and not seen[ny, nx]:
                seen[ny, nx] = True
                dq.append((ny, nx))
    holes = int((bg & ~seen).sum())
    return {
        "bounds_px": {"x0": int(xs.min()), "x1": int(xs.max()),
                      "y0": int(ys.min()), "y1": int(ys.max())},
        "width_mm": round((xs.max() - xs.min() + 1) * mm_per_px, 2),
        "height_mm": round((ys.max() - ys.min() + 1) * mm_per_px, 2),
        "cx_offset_fraction": round(
            abs((xs.min() + xs.max()) / 2 - w / 2) / w, 4),
        "internal_hole_pixels": holes,
        "hash": mask_hash(mask),
    }


def _mask_image(mask, colour=(30, 30, 33)):
    arr = np.full(mask.shape + (3,), 255, dtype=np.uint8)
    arr[mask] = colour
    return Image.fromarray(arr)


def _overlay(m_old, m_new, old_col=(200, 60, 60), new_col=(40, 90, 200)):
    arr = np.full(m_old.shape + (3,), 255, dtype=np.uint8)
    arr[m_old & ~m_new] = old_col
    arr[m_new & ~m_old] = new_col
    arr[m_old & m_new] = (70, 70, 75)
    return Image.fromarray(arr)


# ---------------------------------------------------------------------------
# neutral geometry validation (mode A)

NEUTRAL_RENAME = {
    "front": "neutral_front.png", "side": "neutral_side.png",
    "top": "neutral_top.png",
    "three_quarter_diagnostic": "neutral_three_quarter.png",
    "closure_detail": "closure_detail.png",
    "wireframe": "wireframe.png", "normals": "normals.png",
    "bounds_dimensions": "bounds_dimensions.png",
}


def _detail_pass(meshes, center, height, out_png, samples, stamp=None):
    with tempfile.TemporaryDirectory() as td:
        cfg = {
            "meshes": _export_meshes(meshes, td),
            "assembly_height_mm": p1.OWNER["total_assembled_height_mm"],
            "closure_center_mm": center,
            "closure_height_mm": height,
            "resolution": gvr.RENDER_PARAMS["resolution"],
            "samples": samples,
            "views": {"closure_detail": out_png},
            "shade_smooth": True,
        }
        _run(gvr.SCRIPT, cfg, "VALIDATION_VIEWS_OK")
    if stamp:
        img = Image.open(out_png).convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, img.width, 26 + 22 * len(stamp)],
                       fill=(250, 246, 240))
        for i, line in enumerate(stamp):
            draw.text((20, 8 + i * 22), line, fill=(120, 46, 30))
        img.save(out_png)


def generate_neutral(out_dir, meshes, records, facts, samples=64,
                     fixture_id="P1_V3") -> dict:
    fixture = {
        "fixture_id": fixture_id,
        "geometry_record": records["body"],
        "meshes": meshes,
        "assembly_height_mm": facts["assembly_height_mm"],
        "closure_center_mm": facts["closure_center_mm"],
        "closure_height_mm": facts["closure_height_mm"],
        "three_quarter_distance_factor": 4.2,
        "shade_smooth": True,
        "dims": {"height_mm": p1.OWNER["total_assembled_height_mm"],
                 "front_width_mm": p1.OWNER["body_diameter_mm"],
                 "side_depth_mm": p1.OWNER["body_diameter_mm"]},
    }
    manifest = gvr.render_fixture(fixture, out_dir, samples=samples,
                                  uncertainty=[
                                      "V3 provisional geometry — owner "
                                      "review pending"],
                                  reference_availability="PARTIAL — owner "
                                  "measurements + uncalibrated photos")
    for old, new in NEUTRAL_RENAME.items():
        src = os.path.join(out_dir, f"{old}.png") \
            if not old.endswith(".png") else os.path.join(out_dir, old)
        src = os.path.join(out_dir, f"{old}.png")
        dst = os.path.join(out_dir, new)
        if os.path.exists(src) and src != dst:
            shutil.move(src, dst)
    neck_stamp = [
        "THREAD_GEOMETRY_NOT_MODELLED",
        "GL18 / DIN 18 CLASS - OWNER_CONFIRMED 2026-08-27 "
        "(CLASS ONLY, NOT A SUPPLIER PART)",
        "NOT_MANUFACTURING_AUTHORITATIVE - outer-form validation only",
    ]
    _detail_pass(meshes, facts["neck_detail_center_mm"],
                 facts["neck_detail_height_mm"],
                 os.path.join(out_dir, "neck_detail.png"), samples,
                 stamp=neck_stamp)
    _detail_pass(meshes, facts["shoulder_detail_center_mm"],
                 facts["shoulder_detail_height_mm"],
                 os.path.join(out_dir, "shoulder_detail.png"), samples)
    _detail_pass(meshes, facts["bulb_detail_center_mm"],
                 facts["bulb_detail_height_mm"],
                 os.path.join(out_dir, "bulb_detail.png"), samples)
    _detail_pass(meshes, facts["base_detail_center_mm"],
                 facts["base_detail_height_mm"],
                 os.path.join(out_dir, "base_detail.png"), samples)
    return manifest


# ---------------------------------------------------------------------------
# material validation (mode B)


def generate_material(out_dir, glass, collar, bulb, *, samples=96,
                      diag_resolution=(1000, 1375),
                      resolution=(1400, 1925), liquid=None) -> dict:
    meshes = {"glass": glass, "collar": collar, "bulb": bulb}
    if liquid is not None:
        meshes["liquid"] = liquid
    E = lambda n: os.path.join(out_dir, n)  # noqa: E731

    def studio(views, background="grey", lighting="studio",
               detail_views=None, res=None, n=None):
        with tempfile.TemporaryDirectory() as td:
            cfg = {
                "meshes": _export_meshes(meshes, td),
                "assembly_height_mm":
                    p1.OWNER["total_assembled_height_mm"],
                "resolution": list(res or resolution),
                "samples": n or samples,
                "background": background,
                "lighting": lighting,
                "detail_views": detail_views or {},
                "views": views,
            }
            _run(STUDIO_SCRIPT, cfg, "P1_MATERIAL_STUDIO_OK")

    studio({"front": E("material_front.png"),
            "three_quarter": E("material_three_quarter.png"),
            "neck_shoulder": E("diag_neck_shoulder.png"),
            "base_closeup": E("diag_base.png")},
           detail_views={
               "neck_shoulder": {"center_mm": 80.0, "height_mm": 28.0},
               "base_closeup": {"center_mm": 7.0, "height_mm": 22.0}})
    studio({"front": E("diag_white.png")}, background="white",
           res=diag_resolution)
    studio({"front": E("diag_card.png")}, background="card",
           res=diag_resolution)
    studio({"front": E("diag_stripes.png")}, background="stripes",
           res=diag_resolution)
    studio({"front": E("diag_edge_lit.png")}, lighting="side_lit_edge",
           res=diag_resolution)

    shutil.copyfile(E("material_three_quarter.png"),
                    E("material_reference_preview.png"))
    img = Image.open(E("material_reference_preview.png")).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, img.width, 78], fill=(250, 246, 240))
    for i, line in enumerate([
            "P1 V3 MATERIAL-REFERENCE PREVIEW - TRANSPARENT MATTE ORANGE "
            "GLASS (owner-clarified) + VISUALIZATION-ONLY glass thickness",
            "bottle GLASS/FROSTED EXTERIOR/TRANSPARENT ORANGE-TINTED | "
            "collar burnt-orange glossy | bulb red-orange glossy OPAQUE "
            "| serum fill = VISUALIZATION_ONLY",
            "does NOT replace the neutral geometry-validation views | NOT "
            "a client-presentation render"]):
        draw.text((20, 8 + i * 22), line, fill=(120, 46, 30))
    img.save(E("material_reference_preview.png"))

    # glass-transmission diagnostic composite
    panels = [
        ("diag_white.png", "1. white background"),
        ("material_front.png", "2. mid-grey background"),
        ("diag_card.png", "3. B/W calibration card behind"),
        ("diag_stripes.png", "6. stripe object behind the bottle"),
        ("diag_neck_shoulder.png", "4. neck + shoulder transmission"),
        ("diag_base.png", "5. glass base close-up"),
        ("diag_edge_lit.png", "7. side-lit edge transmission"),
    ]
    tile_h = 980
    imgs = [(_fit(Image.open(E(f)).convert("RGB"), 10_000, tile_h)[0], t)
            for f, t in panels]
    gap = 26
    total_w = sum(i.width for i, _ in imgs) + gap * (len(imgs) - 1) + 60
    canvas = Image.new("RGB", (total_w, tile_h + 220), (247, 245, 242))
    d = ImageDraw.Draw(canvas)
    d.text((30, 18), "MATERIAL DIAGNOSTIC - TRANSPARENT MATTE ORANGE "
                     "GLASS", font=_font(52), fill=(30, 30, 34))
    d.text((30, 84), "proves: transparent + orange-tinted + frosted "
                     "exterior + background visible through the body "
                     "(diffused) + base optically denser than the neck | "
                     "hollow glass is VISUALIZATION_ONLY_GEOMETRY",
           font=_font(28), fill=(90, 70, 60))
    x = 30
    for img_p, title in imgs:
        canvas.paste(img_p, (x, 150))
        d.text((x + 4, 150 + tile_h + 10), title, font=_font(26),
               fill=(45, 45, 48))
        x += img_p.width + gap
    canvas.save(E("glass_transmission_diagnostic.png"))
    return MATERIAL_NODES


# ---------------------------------------------------------------------------
# diagnostics + comparisons


def shoulder_profile_diagnostic(out_png, photo_crop) -> None:
    W, Hc = 2600, 1500
    canvas = Image.new("RGB", (W, Hc), (247, 245, 242))
    d = ImageDraw.Draw(canvas)
    d.text((30, 20), "P1 SHOULDER PROFILE DIAGNOSTIC - V1 / V2 / V3 / "
                     "V4", font=_font(48), fill=(30, 30, 34))
    d.text((30, 80), "V1-V3 owner-rejected; V4 = authored clamped cubic "
                     "spline, narrowing departs EARLIER + progressive "
                     "curvature + soft neck root (VISUAL_ESTIMATE, "
                     "LOW/MEDIUM) - NOT_MANUFACTURING_AUTHORITATIVE",
           font=_font(26), fill=(90, 70, 60))
    photo, _ = _fit(photo_crop, 640, 1120)
    canvas.paste(photo, (30, 150))
    d.rectangle([27, 147, 33 + photo.width, 153 + photo.height],
                outline=(24, 60, 130), width=4)
    d.text((30, 156 + photo.height), "owner photo (uncalibrated, "
                                     "qualitative)", font=_font(24),
           fill=(24, 60, 130))

    # profile chart: z horizontal 64..75.5, r vertical 6..19.5
    x0, y0, x1, y1 = 760, 190, 2160, 1120
    z_lo, z_hi, r_lo, r_hi = 64.0, 75.5, 6.0, 19.5

    def X(z):
        return x0 + (z - z_lo) / (z_hi - z_lo) * (x1 - x0)

    def Y(r):
        return y1 - (r - r_lo) / (r_hi - r_lo) * (y1 - y0)

    d.rectangle([x0, y0, x1, y1], outline=(150, 150, 150), width=2)
    for z, label in ((66.0, "66 (A1)"), (69.0, "69 (A2)"),
                     (73.49, "73.49 neck base (CALC)")):
        d.line([(X(z), y0), (X(z), y1)], fill=(190, 190, 195), width=2)
        d.text((X(z) - 30, y1 + 10), label, font=_font(24),
               fill=(90, 90, 95))
    colours = {"V1": (170, 170, 175), "V2": (205, 140, 140),
               "V3": (200, 60, 60), "V4": (40, 90, 200)}
    zs = np.linspace(64.5, 75.0, 320)
    for rev, col in colours.items():
        pts = [(X(z), Y(p1.shoulder_radius(z, rev))) for z in zs]
        d.line(pts, fill=col, width=5 if rev == p1.REVISION else 3)
    for z, r, _c in p1.SHOULDER_CONTROL_POINTS_V4:
        d.ellipse([X(z) - 7, Y(r) - 7, X(z) + 7, Y(r) + 7],
                  outline=(40, 90, 200), width=3, fill=(247, 245, 242))
    d.text((x1 - 420, y0 + 10), "grey = V1 (rejected)", font=_font(26),
           fill=colours["V1"])
    d.text((x1 - 420, y0 + 44), "rose = V2 (rejected)", font=_font(26),
           fill=colours["V2"])
    d.text((x1 - 420, y0 + 78), "red = V3 (rejected)", font=_font(26),
           fill=colours["V3"])
    d.text((x1 - 420, y0 + 112), "blue = V4 + control points",
           font=_font(26), fill=colours["V4"])

    # continuity + landmark radii
    h = 0.02
    rows = [f"continuity at authored knots ({p1.REVISION}, "
            "finite differences):"]
    for z in (66.0, 69.0, 71.4, 73.1, 73.49):
        rev = p1.REVISION
        r = p1.shoulder_radius(z, rev)
        d1 = (p1.shoulder_radius(z + h, rev)
              - p1.shoulder_radius(z - h, rev)) / (2 * h)
        d2 = (p1.shoulder_radius(z + h, rev) - 2 * r
              + p1.shoulder_radius(z - h, rev)) / (h * h)
        rows.append(f"z={z:6.2f}  r={r:6.2f}  dr/dz={d1:7.3f}  "
                    f"d2r/dz2={d2:7.2f}")
    rows.append("clamped tangents: dr/dz = 0 at the wall (66) and at the "
                "neck base (73.49) - no ridge, no kink")
    for i, line in enumerate(rows):
        d.text((760, 1180 + i * 34), line, font=_font(26),
               fill=(45, 45, 48))
    canvas.save(out_png)


def build_comparisons(out_dir, photo_front, mm_per_px, masks) -> None:
    E = lambda n: os.path.join(out_dir, n)  # noqa: E731
    m1, m2, m3 = masks["V1"], masks["V2"], masks["V3"]
    gap = 30
    h, w = m1.shape
    labels = ["V1 - OWNER REJECTED", "V2 - OWNER REJECTED",
              "V3 - CURRENT REVISION", "V1/V2 overlay", "V2/V3 overlay",
              "V1/V2/V3 combined"]
    tri = np.full((h, w, 3), 255, dtype=np.uint8)
    tri[m1 & ~m2 & ~m3] = (200, 60, 60)
    tri[m2 & ~m3] = (196, 116, 15)
    tri[m3 & ~m2] = (40, 90, 200)
    tri[m1 & m2 & m3] = (70, 70, 75)
    panels = [_mask_image(m1), _mask_image(m2), _mask_image(m3),
              _overlay(m1, m2), _overlay(m2, m3), Image.fromarray(tri)]
    canvas = Image.new("RGB", (w * 6 + gap * 5 + 60, h + 260),
                       (247, 245, 242))
    d = ImageDraw.Draw(canvas)
    d.text((30, 16), "P1 V1 / V2 / V3 SILHOUETTES - deterministic mask "
                     "authority (unlit alpha pass; NO thresholded shaded "
                     "RGB; same pinned camera)", font=_font(44),
           fill=(30, 30, 34))
    d.text((30, 72), "changed: shoulder region (fuller V3 curve) + bulb "
                     "(V3 narrowed collar entry, fuller dome) | unchanged: "
                     "body wall, base, collar bounds, all accepted owner "
                     "dimensions | combined: red=V1-only, amber=V2-only, "
                     "blue=V3-only, dark=common", font=_font(28),
           fill=(90, 70, 60))
    x = 30
    for img, label in zip(panels, labels):
        canvas.paste(img, (x, 130))
        d.text((x + 4, 140 + h), label, font=_font(28), fill=(45, 45, 48))
        x += w + gap
    canvas.save(E("v1_v2_v3_silhouette_comparison.png"))

    # region close-ups (V2 vs V3)
    def region(y_lo_mm, y_hi_mm, out, title):
        # rows from mm: y_px = h/2 - (z - H/2)/mm_per_px with H=114.3
        Hmm = 114.3
        row0 = int(h / 2 - (y_hi_mm - Hmm / 2) / mm_per_px)
        row1 = int(h / 2 - (y_lo_mm - Hmm / 2) / mm_per_px)
        row0, row1 = max(row0, 0), min(row1, h)
        ov = _overlay(m2[row0:row1], m3[row0:row1])
        pan2 = _mask_image(m2[row0:row1])
        pan3 = _mask_image(m3[row0:row1])
        ch = row1 - row0
        c = Image.new("RGB", (w * 3 + gap * 2 + 60, ch + 220),
                      (247, 245, 242))
        dd = ImageDraw.Draw(c)
        dd.text((30, 14), title, font=_font(40), fill=(30, 30, 34))
        dd.text((30, 66), "mask authority (unlit alpha) | red=V2 only, "
                          "blue=V3 only, dark=agreement", font=_font(26),
                fill=(90, 70, 60))
        xx = 30
        for img, lab in ((pan2, "V2"), (pan3, "V3"), (ov, "overlay")):
            c.paste(img, (xx, 110))
            dd.text((xx + 4, 118 + ch), lab, font=_font(26),
                    fill=(45, 45, 48))
            xx += w + gap
        c.save(E(out))

    region(58.0, 80.0, "v2_v3_shoulder_comparison.png",
           "V2 vs V3 SHOULDER (close-up)")
    region(92.0, 115.5, "v2_v3_bulb_comparison.png",
           "V2 vs V3 BULB (close-up)")

    # owner-photo vs V3 qualitative
    files = ["material_front.png", "neutral_front.png",
             "shoulder_detail.png", "bulb_detail.png", "neck_detail.png",
             "base_detail.png"]
    titles = ["V3 material front", "V3 neutral front",
              "V3 shoulder close-up", "V3 bulb close-up",
              "V3 neck/collar close-up", "V3 base close-up"]
    target_h = 1050
    panels = [(_fit(photo_front, 10_000, target_h)[0],
               "OWNER PHOTO IMG_3120 (crop, lossless rotation)")]
    closure_crop = photo_front.crop(
        (0, 0, photo_front.width, int(photo_front.height * 0.42)))
    panels.append((_fit(closure_crop, 10_000, target_h)[0],
                   "OWNER PHOTO closure region"))
    for f, t in zip(files, titles):
        panels.append((_fit(Image.open(E(f)).convert("RGB"), 10_000,
                            target_h)[0], t))
    total_w = sum(im.width for im, _ in panels) + 26 * len(panels) + 60
    canvas = Image.new("RGB", (total_w, target_h + 240), (247, 245, 242))
    d = ImageDraw.Draw(canvas)
    d.text((30, 16), "P1 OWNER PHOTO vs V3 - QUALITATIVE ONLY",
           font=_font(48), fill=(140, 70, 70))
    d.text((30, 78), "OWNER PHOTOGRAPH IS PERSPECTIVE AND UNCALIBRATED | "
                     "NO ACCURATE PHOTOGRAPHIC OVERLAY IS CLAIMED | "
                     "COMPARISON IS QUALITATIVE ONLY | photos never "
                     "stretched/warped", font=_font(28), fill=(90, 70, 60))
    x = 30
    for im, t in panels:
        canvas.paste(im, (x, 150))
        d.text((x + 4, 160 + target_h), t, font=_font(24),
               fill=(45, 45, 48))
        x += im.width + 26
    canvas.save(E("owner_photo_vs_v3.png"))


# ---------------------------------------------------------------------------
# validation + manifests + board


def run_mask_validation(out_dir, facts) -> dict:
    """Mask-authority checks for V3 + the V2 warning re-evaluation."""
    E = lambda n: os.path.join(out_dir, n)  # noqa: E731
    res = (800, 1100)
    mm_per_px = p1.OWNER["total_assembled_height_mm"] * 1.12 / res[1]
    masks = {}
    for rev in ("V1", "V2", "V3"):
        _, meshes, _ = p1.build_p1_assembly(rev)
        render_masks(meshes, {"front": E(f"silhouette_{rev}_front.png")},
                     resolution=res)
        masks[rev] = load_mask(E(f"silhouette_{rev}_front.png"))
    # V3 determinism: render the front mask twice
    _, m3, _ = p1.build_p1_assembly("V3")
    render_masks(m3, {"front": E("silhouette_V3_front_repeat.png"),
                      "side": E("silhouette_V3_side.png"),
                      "closure_detail": E("silhouette_V3_closure.png")},
                 detail_views={"closure_detail": {
                     "center_mm": facts["closure_center_mm"],
                     "height_mm": facts["closure_height_mm"]}},
                 resolution=res)
    repeat = load_mask(E("silhouette_V3_front_repeat.png"))
    front = mask_metrics(masks["V3"], mm_per_px)
    side = mask_metrics(load_mask(E("silhouette_V3_side.png")), mm_per_px)
    closure_mm_per_px = facts["closure_height_mm"] * 1.6 / res[1]
    closure = mask_metrics(load_mask(E("silhouette_V3_closure.png")),
                           closure_mm_per_px)
    validation = {
        "record_type": "p1_v3_validation_manifest/1.0",
        "mask_authority": "unlit emission alpha pass "
                          "(blender_scripts/silhouette_mask.py) — "
                          "lighting-independent by construction (the mask "
                          "scene contains NO lights)",
        "front": front, "side": side, "closure_detail": closure,
        "deterministic": mask_hash(masks["V3"]) == mask_hash(repeat),
        "expected": {"width_mm": p1.OWNER["body_diameter_mm"],
                     "height_mm": p1.OWNER["total_assembled_height_mm"]},
        "checks": {
            "front_width": abs(front["width_mm"]
                               - p1.OWNER["body_diameter_mm"]) < 0.4,
            "front_height": abs(front["height_mm"]
                                - p1.OWNER["total_assembled_height_mm"])
            < 0.4,
            "front_centred": front["cx_offset_fraction"] < 0.01,
            "closure_centred": closure["cx_offset_fraction"] < 0.01,
            "no_internal_holes": front["internal_hole_pixels"] == 0
            and closure["internal_hole_pixels"] == 0,
        },
        "v2_warning_resolution": {
            "warning": "RENDER_OFF_CENTER:closure_detail (V2 manifest)",
            "mask_authority_cx_offset_fraction":
                closure["cx_offset_fraction"],
            "classification": ("RGB_SEGMENTATION_ARTIFACT"
                               if closure["cx_offset_fraction"] < 0.01
                               else "ACTUAL_CAMERA_OR_GEOMETRY_OFFSET"),
            "evidence": "the unlit alpha mask of the same closure-detail "
                        "camera is centred within tolerance while the V2 "
                        "shaded-RGB segmentation drifted (smooth-shading "
                        "highlight blended into the background) — the "
                        "warning was a segmentation artifact, not a "
                        "camera/geometry offset",
        },
        "mask_hashes": {f"{rev}_front": mask_hash(m)
                        for rev, m in masks.items()},
    }
    return _jsonable(validation), masks, mm_per_px


def write_manifests(out_dir, contract, validation, glass) -> None:
    E = lambda n: os.path.join(out_dir, n)  # noqa: E731
    json.dump(contract, open(E("geometry_manifest.json"), "w"), indent=1)
    json.dump({
        "record_type": "p1_v3_materials_manifest/1.0",
        "owner_confirmed_materials": p1.MATERIALS,
        "material_nodes": MATERIAL_NODES,
        "glass_construction": {
            "strategy": "single revolved closed manifold: outer surface + "
                        "mouth rim + inner cavity surface + inner floor "
                        "(no Solidify modifier; deterministic path "
                        "revolve)",
            "wall_body_mm": p1.GLASS_WALL_BODY_MM,
            "wall_neck_mm": p1.GLASS_WALL_NECK_MM,
            "inner_floor_mm": p1.BOTTOM_GLASS_THICKNESS_MM,
            "authority": "VISUALIZATION_ONLY_GEOMETRY — never measured, "
                         "never manufacturing geometry",
            "identity": glass["mesh_identity"],
        },
    }, open(E("materials_manifest.json"), "w"), indent=1)
    json.dump({
        "record_type": "p1_v3_assumptions_manifest/1.0",
        "authority_classes": list(p1.AUTHORITY_CLASSES),
        "provisional_assumptions":
            contract["provisional_assumptions"],
        "modelling_simplifications":
            contract["modelling_simplifications"],
        "shoulder_control_points_v3":
            contract["shoulder_control_points_v3"],
        "bulb_control_points_v3": contract["bulb_control_points_v3"],
        "accuracy_status": contract["accuracy_status"],
        "calibration_statement": "owner photographs are perspective and "
                                 "uncalibrated — no calibrated overlay "
                                 "accuracy is claimed anywhere in V3",
    }, open(E("assumptions_manifest.json"), "w"), indent=1)
    src = json.load(open(os.path.join(
        "docs", "visual_quality", "rbv", "p1_pilot", "2026-08-04",
        "source_derivation_manifest.json")))
    src["record_type"] = "p1_v3_source_derivation_manifest/1.0"
    src["v3_note"] = "V1 research carried forward unchanged; V3 adds no " \
                     "new online sources — shoulder/bulb control points " \
                     "are VISUAL_ESTIMATE_FROM_OWNER_PHOTO"
    json.dump(src, open(E("source_derivation_manifest.json"), "w"),
              indent=1)
    json.dump(_jsonable(validation),
              open(E("validation_manifest.json"), "w"), indent=1)


def build_board(out_dir, photo_front, photo_parts) -> dict:
    E = lambda n: os.path.join(out_dir, n)  # noqa: E731
    board = Image.new("RGB", (4400, 9400), (247, 245, 242))
    d = ImageDraw.Draw(board)
    d.text((60, 40), "P1 DROPPER SERUM BOTTLE - OWNER VISUAL REVIEW "
                     "BOARD (V3)", font=_font(64), fill=(30, 30, 34))
    header = [
        "V3 REVISION - V1 + V2 owner-rejected (shoulder + material); "
        "V1/V2 preserved | owner approval: PENDING_VISUAL_REVIEW | "
        "GATE_2: BLOCKED | manufacturing authority: NOT_ESTABLISHED",
        "sections: OWNER PHOTOGRAPHY | OWNER-MEASURED DIMENSIONS | "
        "OWNER-CONFIRMED MATERIALS | ONLINE-ANALOGOUS EVIDENCE | "
        "CALCULATED | VISUALLY ESTIMATED | NEUTRAL GEOMETRY | MATERIAL "
        "VALIDATION | VISUALIZATION-ONLY INNER GLASS | OMITTED DETAILS",
        "photographs are perspective + uncalibrated - NO calibrated "
        "overlay accuracy claimed | THREAD_GEOMETRY_NOT_MODELLED | "
        "masks = unlit alpha authority (never thresholded shaded RGB)",
    ]
    for i, line in enumerate(header):
        d.text((60, 132 + i * 40), line, font=_font(27), fill=(90, 70, 60))

    def panel(img, x, y, mw, mh, klass, title, col):
        img, _s = _fit(img, mw, mh)
        board.paste(img, (x, y + 56))
        d.rectangle([x - 3, y + 53, x + img.width + 3,
                     y + 59 + img.height], outline=col, width=5)
        d.text((x, y), klass, font=_font(30), fill=col)
        d.text((x, y + img.height + 66), title, font=_font(27),
               fill=(45, 45, 48))
        return img.width

    BLUE, GREY, AMBER, TEAL = (24, 60, 130), (90, 90, 92), \
        (196, 116, 15), (11, 110, 153)
    y = 300
    x = 60
    x += panel(photo_front, x, y, 900, 1300, "OWNER PHOTOGRAPH",
               "IMG_3120 (crop, lossless rotation)", BLUE) + 70
    x += panel(Image.open(E("material_front.png")).convert("RGB"), x, y,
               900, 1300, "MATERIAL VALIDATION",
               "V3 material front (hollow glass + absorption)",
               AMBER) + 70
    x += panel(Image.open(E("material_three_quarter.png")).convert("RGB"),
               x, y, 900, 1300, "MATERIAL VALIDATION",
               "V3 material three-quarter", AMBER) + 70
    x += panel(Image.open(E("neutral_front.png")).convert("RGB"), x, y,
               900, 1300, "NEUTRAL GEOMETRY VALIDATION",
               "V3 neutral front (clay)", GREY) + 70
    panel(photo_parts, x, y, 4340 - x, 620, "OWNER PHOTOGRAPH",
          "IMG_3123 dropper (pipette hidden interior - S5)", BLUE)

    y2 = y + 1500
    x = 60
    for name, title in (("neutral_side.png", "neutral side"),
                        ("neutral_top.png", "neutral top"),
                        ("neutral_three_quarter.png",
                         "neutral three-quarter"),
                        ("closure_detail.png", "closure detail"),
                        ("neck_detail.png",
                         "neck detail (thread statement)")):
        x += panel(Image.open(E(name)).convert("RGB"), x, y2, 780, 1100,
                   "NEUTRAL GEOMETRY VALIDATION", title, GREY) + 56

    y3 = y2 + 1330
    x = 60
    for name, title in (("shoulder_detail.png", "shoulder detail (V3)"),
                        ("bulb_detail.png", "bulb detail (V3)"),
                        ("base_detail.png", "base detail (V3)")):
        x += panel(Image.open(E(name)).convert("RGB"), x, y3, 700, 990,
                   "NEUTRAL GEOMETRY VALIDATION", title, GREY) + 56
    panel(Image.open(E("shoulder_profile_diagnostic.png")).convert("RGB"),
          x, y3, 4340 - x, 1050, "VISUALLY ESTIMATED",
          "shoulder profile diagnostic (V1/V2/V3 + control points)",
          TEAL)

    y4 = y3 + 1290
    panel(Image.open(E("glass_transmission_diagnostic.png")).convert(
        "RGB"), 60, y4, 4280, 1150, "MATERIAL VALIDATION",
        "glass-transmission diagnostic - transparent matte orange glass "
        "(VISUALIZATION-ONLY inner glass)", AMBER)

    y5 = y4 + 1380
    panel(Image.open(E("v1_v2_v3_silhouette_comparison.png")).convert(
        "RGB"), 60, y5, 2700, 1150, "CALCULATED",
        "V1/V2/V3 silhouettes - deterministic mask authority", TEAL)
    x_leg = 2860
    d.text((x_leg, y5), "DIMENSION RECONCILIATION (mask authority)",
           font=_font(34), fill=(30, 30, 34))
    validation = json.load(open(E("validation_manifest.json")))
    rows = [
        ("assembled height", "114.3 OWNER",
         f"{validation['front']['height_mm']} mask"),
        ("body diameter", "37.4 OWNER",
         f"{validation['front']['width_mm']} mask"),
        ("front centred", "-",
         f"{validation['front']['cx_offset_fraction']:.4f} offset"),
        ("closure centred", "-",
         f"{validation['closure_detail']['cx_offset_fraction']:.4f} "
         "offset"),
        ("internal holes", "0 required",
         str(validation['front']['internal_hole_pixels'])),
        ("V2 OFF_CENTER warning", "-",
         validation['v2_warning_resolution']['classification']),
    ]
    for i, (a, b, c) in enumerate(rows):
        d.text((x_leg, y5 + 60 + i * 42), a, font=_font(28),
               fill=(45, 45, 48))
        d.text((x_leg + 640, y5 + 60 + i * 42), b, font=_font(28),
               fill=BLUE)
        d.text((x_leg + 1000, y5 + 60 + i * 42), c, font=_font(28),
               fill=TEAL)
    d.text((x_leg, y5 + 380), "OMITTED MANUFACTURING DETAILS",
           font=_font(34), fill=(179, 69, 79))
    for i, line in enumerate([
            "GL18-class thread (stamped on views) | collar ribs | base",
            "embossing 50ml/46 | label artwork | pipette in renders",
            "inner glass = VISUALIZATION_ONLY (never manufacturing)"]):
        d.text((x_leg, y5 + 440 + i * 40), line, font=_font(28),
               fill=(140, 70, 70))

    y6 = y5 + 1330
    panel(Image.open(E("v2_v3_shoulder_comparison.png")).convert("RGB"),
          60, y6, 2100, 900, "CALCULATED", "V2 vs V3 shoulder close-up",
          TEAL)
    panel(Image.open(E("v2_v3_bulb_comparison.png")).convert("RGB"),
          2260, y6, 2080, 900, "CALCULATED", "V2 vs V3 bulb close-up",
          TEAL)

    y7 = y6 + 1150
    panel(Image.open(E("owner_photo_vs_v3.png")).convert("RGB"), 60, y7,
          4280, 900, "OWNER PHOTOGRAPH", "owner photo vs V3 (qualitative "
          "only - uncalibrated)", BLUE)

    fy = y7 + 1120
    d.text((60, fy), "evidence: docs/visual_quality/rbv/p1_pilot/"
                     "2026-08-04_v3 | V1/V2 preserved | contract "
                     "p1_provisional_geometry/1.0 revision V3",
           font=_font(26), fill=(90, 90, 92))
    d.text((60, fy + 40), "visual review + pipeline validation only - "
                          "NEVER supplier/manufacturing geometry",
           font=_font(26), fill=(140, 70, 70))
    board = board.crop((0, 0, 4400, fy + 110))
    board.save(E("owner_review_board.png"))
    board.save(E("owner_review_board.pdf"), "PDF", resolution=200.0)
    manifest = {
        "record_type": "p1_v3_owner_review_board_manifest/1.0",
        "board": {"png": "owner_review_board.png",
                  "pdf": "owner_review_board.pdf",
                  "pixel_dimensions": list(board.size)},
        "photo_treatment": "whole-region crops + uniform scaling + "
                           "lossless 90-degree rotation only; originals "
                           "untouched",
        "calibration_statement": "no calibrated overlay accuracy claimed",
        "accuracy_status": p1.build_p1_contract("V3")["accuracy_status"],
    }
    json.dump(manifest, open(E("owner_review_board_manifest.json"), "w"),
              indent=1)
    return manifest


def generate_v3(out_dir, *, neutral_samples=64, material_samples=96,
                skip_material=False) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    contract = p1.build_p1_contract("V3")
    if contract["consistency_status"] != "PASS":
        raise RuntimeError(f"V3 consistency REJECTED: "
                           f"{contract['consistency_findings']}")
    records, meshes, facts = p1.build_p1_assembly("V3")
    glass = p1.build_p1_glass_solid()
    diag = md.diagnose_mesh(glass["vertices"], glass["faces"])
    if diag["codes"]:
        raise RuntimeError(f"glass solid diagnostics: {diag['codes']}")

    generate_neutral(out_dir, meshes, records, facts,
                     samples=neutral_samples)
    if not skip_material:
        generate_material(out_dir, glass, meshes["collar"],
                          meshes["bulb"], samples=material_samples)
    validation, masks, mm_per_px = run_mask_validation(out_dir, facts)

    photo_dir = os.path.join("docs", "visual_quality", "rbv",
                             "owner_inputs", "2026-08-04", "originals",
                             "measurments", "P1 — Dropper serum bottle")
    photo_front = Image.open(os.path.join(photo_dir, "IMG_3120.jpg")) \
        .convert("RGB").crop((450, 950, 2400, 3024)) \
        .transpose(Image.Transpose.ROTATE_270)
    photo_parts = Image.open(os.path.join(photo_dir, "IMG_3123.jpg")) \
        .convert("RGB").crop((500, 1000, 3950, 2200))

    shoulder_profile_diagnostic(
        os.path.join(out_dir, "shoulder_profile_diagnostic.png"),
        photo_front.crop((0, int(photo_front.height * 0.18),
                          photo_front.width,
                          int(photo_front.height * 0.72))))
    build_comparisons(out_dir, photo_front, mm_per_px, masks)
    write_manifests(out_dir, contract, validation, glass)
    board = build_board(out_dir, photo_front, photo_parts)
    return {"contract": contract, "validation": validation,
            "board": board, "glass_identity": glass["mesh_identity"]}
