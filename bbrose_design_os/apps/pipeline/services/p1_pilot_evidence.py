"""P1 pilot evidence package generator (owner-review deliverables).

Produces the neutral geometry-validation package (front/side/top ortho,
closure detail, neck detail, three-quarter, wireframe, normals, bounds,
measurement overlay) plus the separate material-reference preview, the
versioned contract and the assumptions/source manifests — everything the
owner instruction requires for PROVISIONAL_BEST_EFFORT_GEOMETRY_PILOT
review. Render authority stays REVIEW_EVIDENCE_ONLY.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw

from apps.pipeline.services import geometry_validation_render as gvr
from apps.pipeline.services import p1_pilot_geometry as p1

P1_UNCERTAINTY = [
    "PROVISIONAL geometry: owner hand measurements + inferred values "
    "(assumptions A1-A4 OWNER-RESOLVED 2026-08-27; simplifications S1-S7 "
    "in the contract still stand)",
    "calibrated photography exists but is CORROBORATING ONLY — every "
    "pixel-derived number is DERIVED_INDICATIVE with an error bar, never "
    "OWNER_MEASURED; the caliper record is the dimensional authority",
    "NOT manufacturing geometry — never send to a supplier",
]
P1_REFERENCE_AVAILABILITY = (
    "PARTIAL — owner caliper measurements + 23 uncalibrated owner "
    "photographs + the 2026-08-27 capture set (5 ruler-in-plane frames "
    "bound to the P1_V4 view keys); no CAD, no technical drawing")

AUTHORITY_COLOURS = {
    "OWNER_MEASURED": (24, 60, 130),
    "CALCULATED_FROM_OWNER_DATA": (11, 110, 153),
    "VISUAL_ESTIMATE_FROM_PHOTO": (196, 116, 15),
    "GENERIC_RENDERING_DEFAULT": (179, 69, 79),
}


def _measurement_overlay(front_png: str, out_png: str, facts: dict) -> None:
    """Dimension + assumption overlay on the front orthographic render."""
    img = Image.open(front_png).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    o = p1.OWNER
    d = {k: v["value"] for k, v in p1.derived_values().items()}
    H = facts["assembly_height_mm"]
    px_per_mm = h / (H * gvr.RENDER_PARAMS["ortho_scale_factor"])

    def y_of(z_mm):
        return h / 2 - (z_mm - H / 2) * px_per_mm

    landmarks = [
        (0.0, "z=0 base (dia 37.35 OWNER)", "OWNER_MEASURED"),
        (o["straight_wall_end_mm"], "66.0 straight-wall end (A1)",
         "OWNER_MEASURED"),
        (o["shoulder_landmark_69_mm"],
         f"69.0 owner landmark — model r={d['shoulder_r_at_69_mm']} (A2)",
         "VISUAL_ESTIMATE_FROM_PHOTO"),
        (d["neck_base_z_mm"], "73.49 neck base = 91.6-18.11 (CALC)",
         "CALCULATED_FROM_OWNER_DATA"),
        (d["collar_bottom_z_mm"], "78.60 collar bottom = 95.1-16.5 (CALC)",
         "CALCULATED_FROM_OWNER_DATA"),
        (o["bottle_height_mm"], "91.6 glass mouth (OWNER)", "OWNER_MEASURED"),
        (d["collar_top_z_mm"], "95.10 collar top = 114.3-19.2 (CALC)",
         "CALCULATED_FROM_OWNER_DATA"),
        (o["total_assembled_height_mm"], "114.3 assembled top (OWNER)",
         "OWNER_MEASURED"),
    ]
    for z, label, authority in landmarks:
        y = y_of(z)
        colour = AUTHORITY_COLOURS[authority]
        draw.line([(w * 0.18, y), (w * 0.82, y)], fill=colour, width=2)
        draw.text((w * 0.185, y - 26), label, fill=colour)

    # body width arrow at z=30
    y = y_of(30.0)
    half_px = (o["body_diameter_mm"] / 2) * px_per_mm
    draw.line([(w / 2 - half_px, y), (w / 2 + half_px, y)],
              fill=AUTHORITY_COLOURS["OWNER_MEASURED"], width=4)
    draw.text((w / 2 + half_px + 8, y - 10), "dia 37.4 OWNER",
              fill=AUTHORITY_COLOURS["OWNER_MEASURED"])

    header = [
        "P1 PROVISIONAL GEOMETRY - MEASUREMENT + ASSUMPTION OVERLAY",
        "authority colours: blue=OWNER_MEASURED  teal=CALCULATED  "
        "amber=VISUAL_ESTIMATE  red=GENERIC_DEFAULT",
        "PROVISIONAL_OWNER_MEASURED_PLUS_INFERRED - NOT manufacturing "
        "geometry",
    ]
    for i, line in enumerate(header):
        draw.text((20, 16 + i * 22), line, fill=(60, 40, 35))
    img.save(out_png)


def _neck_detail(meshes: dict, facts: dict, out_png: str,
                 samples: int) -> None:
    """Second targeted pass of the SAME pinned script: the closure-detail
    camera aimed at the shoulder/neck/collar junction."""
    with tempfile.TemporaryDirectory() as td:
        mesh_files = {}
        for name, mesh in meshes.items():
            path = os.path.join(td, f"{name}.obj")
            gvr.export_obj(mesh, path)
            mesh_files[name] = path
        cfg = {
            "meshes": mesh_files,
            "assembly_height_mm": facts["assembly_height_mm"],
            "closure_center_mm": facts["neck_detail_center_mm"],
            "closure_height_mm": facts["neck_detail_height_mm"],
            "resolution": gvr.RENDER_PARAMS["resolution"],
            "samples": samples,
            "views": {"closure_detail": out_png},
            "shade_smooth": True,
        }
        cfg_path = os.path.join(td, "cfg.json")
        json.dump(cfg, open(cfg_path, "w"))
        result = subprocess.run(
            [gvr.BLENDER, "-b", "--factory-startup", "-noaudio", "-P",
             gvr.SCRIPT, "--", cfg_path],
            capture_output=True, text=True, timeout=1800)
        if "VALIDATION_VIEWS_OK" not in result.stdout:
            raise RuntimeError(f"neck detail render failed: "
                               f"{result.stdout[-500:]}")
    # owner ruling: every neck-detail view must visibly carry the thread
    # omission statement
    img = Image.open(out_png).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, img.width, 56], fill=(250, 246, 240))
    draw.text((20, 8), "THREAD_GEOMETRY_NOT_MODELLED (GL18/DIN 168 class "
                       "OWNER_CONFIRMED 2026-08-27; class only, not a "
                       "supplier part)", fill=(120, 46, 30))
    draw.text((20, 30), "NOT_MANUFACTURING_AUTHORITATIVE - outer-form "
                        "validation only", fill=(120, 46, 30))
    img.save(out_png)


def _material_preview(meshes: dict, facts: dict, out_png: str,
                      samples: int) -> None:
    script = os.path.join(os.path.dirname(gvr.SCRIPT),
                          "p1_material_preview.py")
    with tempfile.TemporaryDirectory() as td:
        mesh_files = {}
        for name, mesh in meshes.items():
            path = os.path.join(td, f"{name}.obj")
            gvr.export_obj(mesh, path)
            mesh_files[name] = path
        cfg = {"meshes": mesh_files,
               "assembly_height_mm": facts["assembly_height_mm"],
               "resolution": gvr.RENDER_PARAMS["resolution"],
               "samples": samples, "output": out_png}
        cfg_path = os.path.join(td, "cfg.json")
        json.dump(cfg, open(cfg_path, "w"))
        result = subprocess.run(
            [gvr.BLENDER, "-b", "--factory-startup", "-noaudio", "-P",
             script, "--", cfg_path],
            capture_output=True, text=True, timeout=1800)
        if "P1_MATERIAL_PREVIEW_OK" not in result.stdout:
            raise RuntimeError(f"material preview failed: "
                               f"{result.stdout[-500:]}")
    # banner: this preview never replaces the neutral validation views
    img = Image.open(out_png).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, img.width, 78], fill=(250, 246, 240))
    for i, line in enumerate([
            "P1 MATERIAL-REFERENCE PREVIEW - "
            "OWNER_CONFIRMED_MATERIAL_EVIDENCE mapping (corrected "
            "2026-08-04)",
            "bottle GLASS/MATTE/TRANSLUCENT ORANGE | collar PLASTIC/GLOSSY/"
            "ORANGE | bulb PLASTIC/GLOSSY/ORANGE OPAQUE",
            "does NOT replace the neutral geometry-validation views | NOT "
            "a client-presentation render"]):
        draw.text((20, 8 + i * 22), line, fill=(120, 46, 30))
    img.save(out_png)


def generate_p1_evidence(out_dir: str, *, samples: int | None = None,
                         preview_samples: int | None = None) -> dict:
    """Build contract + full render evidence package for owner review."""
    os.makedirs(out_dir, exist_ok=True)
    contract = p1.build_p1_contract()
    if contract["consistency_status"] != "PASS":
        raise RuntimeError("P1 consistency REJECTED: "
                           f"{contract['consistency_findings']}")
    records, meshes, facts = p1.build_p1_assembly()

    fixture = {
        "fixture_id": "P1_provisional_pilot",
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
    manifest = gvr.render_fixture(
        fixture, out_dir, samples=samples,
        uncertainty=P1_UNCERTAINTY,
        reference_availability=P1_REFERENCE_AVAILABILITY)

    n = samples or gvr.RENDER_PARAMS["samples"]
    _neck_detail(meshes, facts, os.path.join(out_dir, "neck_detail.png"), n)
    _material_preview(meshes, facts,
                      os.path.join(out_dir, "material_reference_preview.png"),
                      preview_samples or max(n, 48))
    _measurement_overlay(os.path.join(out_dir, "front.png"),
                         os.path.join(out_dir, "measurement_overlay.png"),
                         facts)

    json.dump(contract, open(os.path.join(out_dir,
                                          "p1_geometry_contract.json"), "w"),
              indent=1)
    manifest["views"]["neck_detail"] = "neck_detail.png"
    manifest["views"]["measurement_overlay"] = "measurement_overlay.png"
    manifest["views"]["material_reference_preview"] = \
        "material_reference_preview.png"
    manifest["pixel_hashes"]["neck_detail"] = gvr.pixel_hash(
        os.path.join(out_dir, "neck_detail.png"))
    json.dump(manifest, open(os.path.join(out_dir, "manifest.json"), "w"),
              indent=1)
    return {"contract": contract, "manifest": manifest}
