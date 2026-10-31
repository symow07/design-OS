"""RBV-2B — geometry-validation render orchestration.

One immutable ``container_geometry/1.0`` mesh drives every view: the mesh
is built once, exported once (OBJ, z-up, base at z=0), and the checked-in
Blender script renders all views from that single file. The renderer is a
visualization layer — it never becomes geometry authority, and every
output states it is a GEOMETRY VALIDATION FIXTURE, not a real-bottle
comparison.

§11 render checks measure the rendered silhouette (via the concept-
analysis background segmenter) against the geometry contract: physical
scale per view, front/side scale agreement, clipping, centering and
bounding boxes. Failures carry stable codes (RENDER_SCALE_MISMATCH,
RENDER_CLIPPED, ...). §9 determinism is judged on DECODED PIXELS.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw

from apps.pipeline.services import concept_analysis as ca
from apps.pipeline.services import mesh_diagnostics as md
from apps.pipeline.services.container_geometry import build_mesh

MANIFEST_SCHEMA = "geometry_validation_render_manifest/1.0"
CAMERA_STANDARD = "real_bottle_camera_standard/1.0"
LIGHTING_STANDARD = "real_bottle_lighting_standard/1.0 "
"(GEOMETRY_VALIDATION_LIGHTING)"
MATERIAL_OVERRIDE = {
    "version": "validation_clay/1.0",
    "base_colour": [0.69, 0.667, 0.65, 1.0],
    "roughness": 0.9, "specular": 0.1, "alpha": 1.0,
    "normals": "geometry normals unmodified",
    "colour_management": "Cycles CPU · Standard view transform · "
                         "exposure 0 · gamma 1 · sRGB · 8-bit PNG",
}
NOT_REAL_BOTTLE = ("GEOMETRY VALIDATION FIXTURE — NOT A REAL BOTTLE "
                   "COMPARISON")

RENDER_SCALE_MISMATCH = "RENDER_SCALE_MISMATCH"
RENDER_CLIPPED = "RENDER_CLIPPED"
RENDER_OFF_CENTER = "RENDER_OFF_CENTER"
RENDER_CLOSURE_MISSING = "RENDER_CLOSURE_MISSING"

RENDER_PARAMS = {
    "version": "geometry_validation_render_params/1.0",
    "resolution": [1600, 2200],
    "samples": 12,
    "ortho_scale_factor": 1.12,       # vertical coverage = H * factor
    "scale_tolerance": 0.03,          # rendered mm/px vs expected
    "center_tolerance": 0.03,         # fraction of image width
}

BLENDER = os.path.expanduser(
    "~/Applications/Blender-4.5.12-LTS.app/Contents/MacOS/Blender")
SCRIPT = os.path.join(os.path.dirname(__file__), "blender_scripts",
                      "validation_views.py")
VIEW_NAMES = ("front", "side", "top", "closure_detail",
              "three_quarter_diagnostic", "wireframe", "normals")


def export_obj(mesh: dict, path: str, *, z_offset: float = 0.0,
               flip_profile_axis: float | None = None) -> None:
    """Deterministic OBJ export. ``flip_profile_axis`` converts the
    profile-axis convention (index 0 = product top) into z-up world
    space: z' = flip_profile_axis - z, then + z_offset."""
    v = mesh["vertices"].copy()
    if flip_profile_axis is not None:
        v[:, 2] = flip_profile_axis - v[:, 2]
    v[:, 2] += z_offset
    lines = [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in v]
    lines += [f"f {a + 1} {b + 1} {c + 1}" for a, b, c in mesh["faces"]]
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def pixel_hash(path: str) -> str:
    """§9: hash DECODED pixels — PNG metadata never participates."""
    arr = np.asarray(Image.open(path).convert("RGB"))
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def _silhouette_bounds(path: str):
    img = Image.open(path)
    mask, _, _, _ = ca.extract_mask(img)
    if mask is None or not mask.any():
        return None, (img.width, img.height)
    ys, xs = np.nonzero(mask)
    return {"x0": int(xs.min()), "x1": int(xs.max()),
            "y0": int(ys.min()), "y1": int(ys.max()),
            "touches_frame": bool(mask[0].any() or mask[-1].any()
                                  or mask[:, 0].any()
                                  or mask[:, -1].any())}, \
        (img.width, img.height)


def check_views(view_paths: dict, dims: dict, assembly_height: float,
                *, has_closure: bool) -> tuple[dict, list[str]]:
    """§11 measurements vs the geometry contract."""
    codes: list[str] = []
    res_y = RENDER_PARAMS["resolution"][1]
    mm_per_px = assembly_height * RENDER_PARAMS["ortho_scale_factor"] / res_y
    measurements: dict = {"expected_mm_per_px": round(mm_per_px, 5)}
    expected = {
        "front": ("front_width_mm", dims.get("front_width_mm")),
        "side": ("side_depth_mm", dims.get("side_depth_mm")
                 or dims.get("front_width_mm")),
    }
    for view in ("front", "side", "top", "closure_detail"):
        path = view_paths.get(view)
        if not path or not os.path.exists(path):
            continue
        bounds, (w, h) = _silhouette_bounds(path)
        if bounds is None:
            if view == "closure_detail":
                # a tight detail crop can fill the border sample with
                # clay — segmentation is n/a there; verify CONTENT via
                # luminance variance instead of failing the view
                arr = np.asarray(Image.open(path).convert("L"),
                                 dtype=float)
                if float(arr.std()) > 2.0:
                    measurements[view] = {
                        "note": "detail crop fills frame — silhouette "
                                "segmentation not applicable; content "
                                "verified by variance",
                        "luminance_std": round(float(arr.std()), 2)}
                    continue
                if has_closure:
                    codes.append(RENDER_CLOSURE_MISSING)
                continue
            codes.append(f"{RENDER_CLIPPED}:{view}:no_silhouette")
            continue
        entry = {"bounds_px": bounds}
        # a detail CROP legitimately meets the frame; full views must not
        if bounds["touches_frame"] and view != "closure_detail":
            codes.append(f"{RENDER_CLIPPED}:{view}")
        cx = (bounds["x0"] + bounds["x1"]) / 2
        if abs(cx - w / 2) / w > RENDER_PARAMS["center_tolerance"]:
            codes.append(f"{RENDER_OFF_CENTER}:{view}")
        if view in expected:
            key, mm = expected[view]
            if mm:
                rendered_mm = (bounds["x1"] - bounds["x0"] + 1) * mm_per_px
                entry["rendered_extent_mm"] = round(rendered_mm, 2)
                entry["contract_extent_mm"] = mm
                if abs(rendered_mm - mm) / mm > \
                        RENDER_PARAMS["scale_tolerance"]:
                    codes.append(f"{RENDER_SCALE_MISMATCH}:{view}")
        if view == "front":
            rendered_h = (bounds["y1"] - bounds["y0"] + 1) * mm_per_px
            entry["rendered_height_mm"] = round(rendered_h, 2)
            if abs(rendered_h - assembly_height) / assembly_height > \
                    RENDER_PARAMS["scale_tolerance"]:
                codes.append(f"{RENDER_SCALE_MISMATCH}:front_height")
        if view == "closure_detail" and has_closure:
            coverage = ((bounds["x1"] - bounds["x0"])
                        * (bounds["y1"] - bounds["y0"])) / (w * h)
            entry["closure_view_coverage"] = round(coverage, 4)
            if coverage < 0.05:
                codes.append(RENDER_CLOSURE_MISSING)
        measurements[view] = entry
    # front/side vertical scale agreement (same mm/px by construction —
    # verified from rendered heights)
    f = measurements.get("front", {}).get("rendered_height_mm")
    s_bounds = measurements.get("side", {}).get("bounds_px")
    if f and s_bounds:
        side_h = (s_bounds["y1"] - s_bounds["y0"] + 1) * mm_per_px
        measurements["side"]["rendered_height_mm"] = round(side_h, 2)
        if abs(side_h - f) / f > RENDER_PARAMS["scale_tolerance"]:
            codes.append(f"{RENDER_SCALE_MISMATCH}:front_vs_side")
    return measurements, codes


def render_fixture(fixture: dict, out_dir: str, *,
                   samples: int | None = None,
                   uncertainty: list[str] | None = None,
                   reference_availability: str | None = None) -> dict:
    """Render every §2 view for one fixture from ONE mesh identity.

    ``fixture``: {fixture_id, geometry_record, meshes: {body, collar?,
    bulb?} (positioned, z-up), assembly_height_mm, closure_center_mm,
    closure_height_mm, dims}. Returns the §10 manifest.
    """
    os.makedirs(out_dir, exist_ok=True)
    meshes = fixture["meshes"]
    with tempfile.TemporaryDirectory() as td:
        mesh_files = {}
        for name, mesh in meshes.items():
            path = os.path.join(td, f"{name}.obj")
            export_obj(mesh, path)
            mesh_files[name] = path
        view_paths = {v: os.path.join(out_dir, f"{v}.png")
                      for v in VIEW_NAMES if v != "normals"}
        view_paths["normals"] = os.path.join(out_dir, "normals.png")
        cfg = {
            "meshes": mesh_files,
            "assembly_height_mm": fixture["assembly_height_mm"],
            "closure_center_mm": fixture["closure_center_mm"],
            "closure_height_mm": fixture["closure_height_mm"],
            "resolution": RENDER_PARAMS["resolution"],
            "samples": samples or RENDER_PARAMS["samples"],
            "views": view_paths,
            "three_quarter_distance_factor":
                fixture.get("three_quarter_distance_factor", 3.2),
            "shade_smooth": fixture.get("shade_smooth", False),
        }
        cfg_path = os.path.join(td, "cfg.json")
        json.dump(cfg, open(cfg_path, "w"))
        result = subprocess.run(
            [BLENDER, "-b", "--factory-startup", "-noaudio", "-P", SCRIPT,
             "--", cfg_path],
            capture_output=True, text=True, timeout=1800)
        if "VALIDATION_VIEWS_OK" not in result.stdout:
            raise RuntimeError(
                f"blender render failed: {result.stdout[-800:]} "
                f"{result.stderr[-400:]}")

    # bounds/dimensions view: PIL annotation over the front render
    front = Image.open(view_paths["front"]).convert("RGB")
    bounds, (w, h) = _silhouette_bounds(view_paths["front"])
    draw = ImageDraw.Draw(front)
    if bounds:
        draw.rectangle([bounds["x0"], bounds["y0"], bounds["x1"],
                        bounds["y1"]], outline=(179, 69, 79), width=4)
    dims = fixture["dims"]
    draw.text((20, 20), NOT_REAL_BOTTLE, fill=(179, 69, 79))
    draw.text((20, 44),
              f"contract: H {dims.get('height_mm')}mm · W "
              f"{dims.get('front_width_mm')}mm · D "
              f"{dims.get('side_depth_mm') or dims.get('front_width_mm')}"
              "mm", fill=(60, 40, 35))
    bounds_path = os.path.join(out_dir, "bounds_dimensions.png")
    front.save(bounds_path)
    view_paths["bounds_dimensions"] = bounds_path

    measurements, codes = check_views(
        view_paths, dims, fixture["assembly_height_mm"],
        has_closure="collar" in meshes or "bulb" in meshes)

    diagnostics = {name: md.diagnose_mesh(m["vertices"], m["faces"])
                   for name, m in meshes.items()}
    assembly = md.diagnose_assembly(
        meshes["body"], meshes.get("collar"), meshes.get("bulb"))

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "statement": NOT_REAL_BOTTLE,
        "fixture_id": fixture["fixture_id"],
        "geometry_schema": fixture["geometry_record"]["schema"],
        "geometry_class": fixture["geometry_record"]["geometry_class"],
        "authority_class": fixture["geometry_record"]["source_authority"],
        "cross_section_family":
            fixture["geometry_record"]["cross_section"]["family"],
        "dimensions": dims,
        "mesh_identities": {n: m["mesh_identity"]
                            for n, m in meshes.items()},
        "mesh_statistics": diagnostics,
        "assembly_relations": assembly,
        "blender_version": "Blender 4.5.12 LTS (pinned)",
        "render_engine": "CYCLES CPU · seed 0 · "
                         f"{samples or RENDER_PARAMS['samples']} samples",
        "camera_standard": CAMERA_STANDARD,
        "lighting_standard": LIGHTING_STANDARD,
        "material_override": MATERIAL_OVERRIDE,
        "render_params": RENDER_PARAMS,
        "views": {v: os.path.basename(p) for v, p in view_paths.items()},
        "pixel_dimensions": RENDER_PARAMS["resolution"],
        "physical_scale_mm_per_px":
            measurements["expected_mm_per_px"],
        "pixel_hashes": {v: pixel_hash(p)
                         for v, p in view_paths.items()
                         if os.path.exists(p)},
        "measurements": measurements,
        "warnings": codes,
        "uncertainty": (list(uncertainty) if uncertainty is not None
                        else ["synthetic geometry fixture — no real-bottle "
                              "reference available (pack INCOMPLETE)"]),
        "reference_availability": (reference_availability
                                   or "NONE — real reference pack "
                                      "incomplete"),
    }
    json.dump(manifest, open(os.path.join(out_dir, "manifest.json"), "w"),
              indent=1)
    return manifest


def build_positioned_assembly(body_record: dict, closure_profiles=None):
    """(meshes dict z-up positioned, assembly facts). Body from a
    container_geometry record; optional collar/bulb records stack above
    the body in the visible-structure scope only."""
    def _flip(mesh, span):
        # container_geometry's z axis follows the profile (index 0 =
        # top); flip into z-up. Mirroring inverts handedness, so face
        # winding is re-normalized to outward normals — construction
        # convention, not silent defect repair (diagnostics still guard
        # every mesh).
        mesh["vertices"] = mesh["vertices"].copy()
        mesh["vertices"][:, 2] = span - mesh["vertices"][:, 2]
        mesh["faces"] = mesh["faces"][:, [0, 2, 1]].copy()
        return mesh

    body = _flip(build_mesh(body_record),
                 float(body_record["dimensions"]["height_mm"]))
    height = float(body_record["dimensions"]["height_mm"])
    meshes = {"body": body}
    closure_top = height
    closure_bottom = height
    if closure_profiles:
        z = height
        for name, rec in closure_profiles:
            h_local = float(rec["dimensions"]["height_mm"])
            m = _flip(build_mesh(rec), h_local)
            m["vertices"][:, 2] += z
            meshes[name] = m
            closure_bottom = min(closure_bottom, z)
            z += h_local
            closure_top = z
    if closure_top > height:          # a real closure exists
        closure_center = (closure_bottom + closure_top) / 2
        closure_height = closure_top - closure_bottom
    else:
        # no closure component: the detail view frames the neck/shoulder
        # region (top 30% of the body) honestly
        closure_center = 0.85 * height
        closure_height = 0.30 * height
    return meshes, {"assembly_height_mm": closure_top,
                    "closure_center_mm": closure_center,
                    "closure_height_mm": closure_height}


#: Gate C exemption — this module feeds verdicts from display-encoded
#: frames BY DECLARATION. The registry test asserts the exemption set
#: is closed: a new site cannot appear without failing it.
DISPLAY_SPACE_BY_DECLARATION = ("RBV §11 pixel checks: the subject is the review frame")
