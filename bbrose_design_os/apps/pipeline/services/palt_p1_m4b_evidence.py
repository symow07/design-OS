"""PALT-M4B — CSG-resolved neutral evidence for the corrected PALT-P1."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw

from apps.pipeline.services import geometry_validation_render as gvr
from apps.pipeline.services.palette_review_fonts import font

SCRIPT = os.path.join(os.path.dirname(gvr.SCRIPT), "palette_csg_views.py")
RES = (1500, 1500)
SAMPLES = 44
# cutters are NEVER smoothed: a smoothed cutter makes the cut pocket
# wall read as a soft dimple instead of a crisp moulded recess
SMOOTH = ["metal_pan_", "powder_", "hinge_knuckle_", "hinge_pin"]


def _export(components, td):
    files = {}
    for name, c in components.items():
        path = os.path.join(td, f"{name}.obj")
        gvr.export_obj({"vertices": c["vertices"], "faces": c["faces"]}, path)
        files[name] = path
    return files


def render(components, views, out_dir, *, centre, ortho_scale,
           detail_views=None, section=None, samples=SAMPLES,
           distance=600.0, technical=False, materials=None,
           light_policy=None, exr_views=None, png16_views=None):
    os.makedirs(out_dir, exist_ok=True)
    csg = {n: c["csg"] for n, c in components.items() if "csg" in c}
    with tempfile.TemporaryDirectory() as td:
        from apps.pipeline.services import palette_render_contract as RC
        cfg = {
            **(light_policy or RC.blender_config()),
            "meshes": _export(components, td),
            "csg": csg,
            "section": section,
            "resolution": list(RES), "samples": samples,
            "centre": list(centre), "ortho_scale": ortho_scale,
            "camera_distance": distance,
            "smooth_prefixes": SMOOTH,
            "technical_tones": technical,
            "materials": materials or {},
            "detail_views": detail_views or {},
            "views": {k: os.path.join(out_dir, v) for k, v in views.items()},
            "exr_views": {k: os.path.join(out_dir, v)
                          for k, v in (exr_views or {}).items()},
            "png16_views": {k: os.path.join(out_dir, v)
                            for k, v in (png16_views or {}).items()},
        }
        p = os.path.join(td, "cfg.json")
        json.dump(cfg, open(p, "w"))
        r = subprocess.run(
            [gvr.BLENDER, "-b", "--factory-startup", "-noaudio", "-P",
             SCRIPT, "--", p], capture_output=True, text=True, timeout=5400)
        if "PALETTE_CSG_VIEWS_OK" not in r.stdout:
            raise RuntimeError(f"CSG render failed: {r.stdout[-900:]} "
                               f"{r.stderr[-300:]}")
        return [ln for ln in r.stdout.splitlines()
                if ("WARNING" in ln and "CSG" in ln)
                or "SECTION_WARNING" in ln
                or ln.startswith("SCENE_LINEAR_STATS")]


def stamp(path, lines, colour=(150, 40, 25)):
    img = Image.open(path).convert("RGB")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width, 16 + 26 * len(lines)], fill=(250, 247, 242))
    for i, line in enumerate(lines):
        d.text((18, 10 + i * 26), line, font=font(21), fill=colour)
    img.save(path)
