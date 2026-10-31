"""PALT-M4 — PALT-P1 neutral geometry evidence package.

Renders the deterministic states in neutral clay and assembles the owner
review board. No powder realism, no cosmetic colour, no artwork, no beauty
render — geometry validation only.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw

from apps.pipeline.services import geometry_validation_render as gvr
from apps.pipeline.services import palette_geometry_validators as pgv
from apps.pipeline.services.palette_mechanism_geometry import (
    OPEN_REVIEW_ANGLE_DEG, PREMIUM_ENVELOPE, assembly_manifest,
    build_components, compose_state)
from apps.pipeline.services.palette_stackup_engine import footprint_stackup
from apps.pipeline.services.palette_mechanism_geometry import (
    PALT_P1_MECHANISM)
from apps.pipeline.services.palt_p1 import build_palt_p1

SCRIPT = os.path.join(os.path.dirname(gvr.SCRIPT), "palette_views.py")
RES = (1400, 1400)
SAMPLES = 40

STRESS_LABEL = ("ENGINEERING_STRESS_FIXTURE — NOT_PRODUCT_RECOMMENDATION — "
                "NOT_OWNER_APPROVED")


def _export(components, td):
    files = {}
    for name, c in components.items():
        path = os.path.join(td, f"{name}.obj")
        gvr.export_obj({"vertices": c["vertices"], "faces": c["faces"]}, path)
        files[name] = path
    return files


def _render(components, views, out_dir, *, centre, ortho_scale,
            detail_views=None, samples=SAMPLES, distance=600.0):
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        cfg = {
            "meshes": _export(components, td),
            "resolution": list(RES),
            "samples": samples,
            "centre": list(centre),
            "ortho_scale": ortho_scale,
            "camera_distance": distance,
            # pans stay FLAT-shaded: a pressed pan face is flat, and
            # smoothing its cap fan domes it into fake powder relief
            "smooth_prefixes": ["pocket_ring_", "hinge_barrel_",
                                "hinge_pin"],
            "detail_views": detail_views or {},
            "views": {k: os.path.join(out_dir, v) for k, v in views.items()},
        }
        cfg_path = os.path.join(td, "cfg.json")
        json.dump(cfg, open(cfg_path, "w"))
        result = subprocess.run(
            [gvr.BLENDER, "-b", "--factory-startup", "-noaudio", "-P",
             SCRIPT, "--", cfg_path],
            capture_output=True, text=True, timeout=3600)
        if "PALETTE_VIEWS_OK" not in result.stdout:
            raise RuntimeError(f"palette render failed: "
                               f"{result.stdout[-700:]} "
                               f"{result.stderr[-300:]}")


def pg_transform(component, pivot):
    """180 deg presentation flip about x through ``pivot`` (y, z)."""
    from apps.pipeline.services.palette_geometry import transform
    return transform(component, rotate_x_about=pivot, angle_deg=180.0)


def _stamp(path, lines, colour=(120, 46, 30), height=None):
    img = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(img)
    h = height or (12 + 22 * len(lines))
    draw.rectangle([0, 0, img.width, h], fill=(250, 246, 240))
    for i, line in enumerate(lines):
        draw.text((18, 8 + i * 22), line, fill=colour)
    img.save(path)


def generate_palt_p1_evidence(out_dir, *, samples=SAMPLES,
                              open_angle_deg=OPEN_REVIEW_ANGLE_DEG) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    comps, dims = build_components()
    validation = pgv.validate_assembly(comps, dims,
                                       open_angle_deg=open_angle_deg)
    if not validation["valid"]:
        raise RuntimeError(f"PALT-P1 geometry invalid: "
                           f"{validation['findings']}")
    diagnostics = pgv.geometry_diagnostics(comps)
    manifest = assembly_manifest(comps, dims)

    w, d, h = dims["envelope_mm"]
    centre = (0.0, 0.0, h / 2.0)
    scale = w * 1.25

    closed = compose_state(comps, dims, "CLOSED")
    _render(closed, {"front": "closed_front.png", "top": "closed_top.png",
                     "side": "closed_side.png",
                     "three_quarter": "closed_three_quarter.png"},
            out_dir, centre=centre, ortho_scale=scale, samples=samples)

    open_state = compose_state(comps, dims, "OPEN_REVIEW_ANGLE",
                               open_angle_deg=open_angle_deg)
    allv = np.concatenate([c["vertices"] for c in open_state.values()])
    o_centre = (0.0, float(allv[:, 1].mean()),
                float((allv[:, 2].min() + allv[:, 2].max()) / 2))
    o_scale = float(max(np.ptp(allv[:, 1]), np.ptp(allv[:, 2]),
                        np.ptp(allv[:, 0]))) * 1.2
    _render(open_state, {"front": "open_front.png",
                         "three_quarter": "open_three_quarter.png",
                         "side": "open_side.png"},
            out_dir, centre=o_centre, ortho_scale=o_scale, samples=samples,
            distance=900.0)

    tray = compose_state(comps, dims, "TRAY_ONLY")
    _render(tray, {"top": "pan_layout_top.png"}, out_dir,
            centre=(0, 0, dims["base_height_mm"] / 2), ortho_scale=scale,
            samples=samples)
    base = compose_state(comps, dims, "BASE_ONLY")
    _render(base, {"three_quarter": "base_only.png"}, out_dir,
            centre=(0, 0, dims["base_height_mm"] / 2), ortho_scale=scale,
            samples=samples)
    # lid shown MIRROR-SIDE UP: a 180 deg presentation flip about its own
    # centre so the required "lid and mirror" view actually shows the mirror
    lid = compose_state(comps, dims, "LID_ONLY")
    lv0 = np.concatenate([c["vertices"] for c in lid.values()])
    pivot = (float(lv0[:, 1].mean()), float(lv0[:, 2].mean()))
    lid = {n: pg_transform(c, pivot) for n, c in lid.items()}
    lv = np.concatenate([c["vertices"] for c in lid.values()])
    _render(lid, {"three_quarter": "lid_and_mirror.png"}, out_dir,
            centre=(0, 0, float(lv[:, 2].mean())), ortho_scale=scale,
            samples=samples)

    # mechanism close-ups (tight ortho crops)
    mech = compose_state(comps, dims, "MECHANISM_DETAIL")
    hy, hz = dims["hinge_axis_y_mm"], dims["hinge_axis_z_mm"]
    _render(mech, {"hinge_detail": "hinge_detail.png",
                   "clasp_detail": "clasp_detail.png"},
            out_dir, centre=(0, 0, h / 2), ortho_scale=scale,
            samples=samples,
            detail_views={
                "hinge_detail": {"loc": [40.0, hy - 60.0, hz + 26.0],
                                 "rot": [math.radians(66), 0.0,
                                         math.radians(30)],
                                 "scale": 44.0},
                "clasp_detail": {"loc": [30.0, -d / 2 - 55.0,
                                         dims["base_height_mm"] + 26.0],
                                 "rot": [math.radians(64), 0.0,
                                         math.radians(24)],
                                 "scale": 40.0}})

    exploded = compose_state(comps, dims, "EXPLODED")
    ev = np.concatenate([c["vertices"] for c in exploded.values()])
    _render(exploded, {"three_quarter": "exploded.png"}, out_dir,
            centre=(0, 0, float((ev[:, 2].min() + ev[:, 2].max()) / 2)),
            ortho_scale=float(np.ptp(ev[:, 2])) * 1.35, samples=samples,
            distance=900.0)

    # section view: half the assembly hidden (deterministic y-clip)
    section = {n: c for n, c in closed.items()
               if float(c["vertices"][:, 1].mean()) <= 0.5}
    _render(section, {"side": "section_through_height.png"}, out_dir,
            centre=centre, ortho_scale=scale, samples=samples)

    _stamp(os.path.join(out_dir, "hinge_detail.png"),
           ["HINGE DETAIL — wall-integrated pin hinge, TOP_EDGE",
            "MECHANISM_ASSUMPTIONS: DESIGN_DEFAULT estimates, "
            "NOT_MANUFACTURER_CONFIRMED"])
    _stamp(os.path.join(out_dir, "clasp_detail.png"),
           ["CLASP DETAIL — wall-integrated snap clasp, BOTTOM_EDGE",
            "MECHANISM_ASSUMPTIONS: DESIGN_DEFAULT estimates, "
            "NOT_MANUFACTURER_CONFIRMED"])
    _stamp(os.path.join(out_dir, "lid_and_mirror.png"),
           ["LID AND MIRROR — shown mirror-side up (180 deg presentation "
            "flip; geometry unchanged)"])
    _stamp(os.path.join(out_dir, "section_through_height.png"),
           ["SECTION THROUGH CASE HEIGHT (deterministic component clip, "
            "not a cut solid)"])

    dim_overlay(os.path.join(out_dir, "closed_front.png"),
                os.path.join(out_dir, "dimension_overlay.png"), dims)

    return {"components": comps, "dims": dims, "validation": validation,
            "diagnostics": diagnostics, "manifest": manifest}


def dim_overlay(src, dst, dims):
    img = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, d, h = dims["envelope_mm"]
    lines = [
        "PALT-P1 DIMENSION OVERLAY — resolved from the PALT-M2/M3 contracts",
        f"envelope {w} x {d} x {h} mm — "
        "PROVISIONALLY_APPROVED_FOR_GEOMETRY_DEVELOPMENT, "
        "FINAL DIMENSIONS NOT_APPROVED",
        f"pan 26.0 dia x {dims['pan_depth_mm']} deep · pocket "
        f"{dims['pocket_diameter_mm']} dia · pitch {dims['pitch_mm']} · "
        f"gap {dims['inter_pan_gap_mm']} · margin {dims['outer_margin_mm']}",
        f"case wall {dims['case_wall_mm']} · hinge wall "
        f"{dims['hinge_wall_mm']} · clasp wall {dims['clasp_wall_mm']} · "
        f"tray floor {dims['tray_floor_mm']} · parting "
        f"{dims['parting_gap_mm']}",
        f"height stack: lower bound "
        f"{dims['height_stackup']['GEOMETRIC_LOWER_BOUND_mm']} < "
        f"engineering {dims['height_stackup']['ENGINEERING_MINIMUM_mm']} < "
        f"premium {dims['height_stackup']['PREMIUM_DESIGN_TARGET_mm']} "
        f"(envelope {h})",
        "MANUFACTURING_AUTHORITY: NOT_ESTABLISHED",
    ]
    draw.rectangle([0, 0, img.width, 20 + 22 * len(lines)],
                   fill=(250, 246, 240))
    for i, line in enumerate(lines):
        draw.text((18, 12 + i * 22), line, fill=(60, 40, 35))
    img.save(dst)


def generate_stress_fixture(out_dir, *, samples=SAMPLES) -> dict:
    """The wall-integrated analytical minimum, rendered ONLY to show why
    the 116 x 116 envelope has better margins. Never a recommendation."""
    spec = build_palt_p1(inter_pan_gap=2.0, outer_margin=3.0)
    foot = footprint_stackup(spec, PALT_P1_MECHANISM, 3, 3)
    envelope = (round(foot.minimum_width_mm, 1),
                round(foot.minimum_depth_mm, 1), 15.0)
    comps, dims = build_components(envelope=envelope, gap=2.0, margin=3.0)
    validation = pgv.validate_assembly(comps, dims)
    closed = compose_state(comps, dims, "CLOSED")
    _render(closed, {"three_quarter": "stress_fixture_three_quarter.png",
                     "top": "stress_fixture_top.png"},
            out_dir, centre=(0, 0, envelope[2] / 2),
            ortho_scale=PREMIUM_ENVELOPE[0] * 1.25, samples=samples)
    for name in ("stress_fixture_three_quarter.png",
                 "stress_fixture_top.png"):
        _stamp(os.path.join(out_dir, name),
               [STRESS_LABEL,
                f"analytical minimum {envelope[0]} x {envelope[1]} x "
                f"{envelope[2]} mm at 2.0 gap / 3.0 margin",
                "shown only to demonstrate why 116 x 116 gives better "
                "margins, spacing and mechanism clearance"])
    return {"envelope_mm": list(envelope), "validation": validation,
            "dims": dims}
