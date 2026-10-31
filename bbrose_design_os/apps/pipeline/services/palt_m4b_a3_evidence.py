"""PALT-M4B-A3 §10 — coring, thickness and section evidence.

Sections are drawn from the same deterministic section engine that feeds
the thickness field, at true proportion with uniform magnification.
Technical colours are the A2 key, extended with core cavity and rib.
"""
from __future__ import annotations

import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw

from apps.pipeline.services import palt_m4b_a3 as A3
from apps.pipeline.services.geometry_validation_render import (
    BLENDER, export_obj, pixel_hash)
from apps.pipeline.services.palette_review_fonts import font

SCRIPT = os.path.join(os.path.dirname(__file__), "blender_scripts",
                      "m4b_a_tray_views.py")

PAPER = (250, 249, 246)
INK = (28, 28, 32)
GREY = (110, 110, 118)
KEY = {
    "tray": (108, 122, 140), "core_cavity": (246, 232, 206),
    "pocket_cavity": (232, 236, 241), "metal_pan": (38, 96, 156),
    "powder": (120, 74, 52), "ok": (44, 150, 92),
    "warn": (214, 152, 38), "bad": (198, 48, 42), "rib": (150, 96, 176),
}
NOT_AUTH = ("PALT_P1_FINAL_DIMENSIONS: NOT_APPROVED · "
            "PALT_P1_MANUFACTURING_AUTHORITY: NOT_ESTABLISHED · "
            "PALT_M4B_B: BLOCKED · PALT_M5: BLOCKED")


def _legend(d, x, y, items, size=23):
    for i, (label, colour) in enumerate(items):
        yy = y + i * 30
        d.rectangle([x, yy, x + 24, yy + 18], fill=colour, outline=INK)
        d.text((x + 34, yy - 2), label, font=font(size), fill=INK)


def _wrap(text, width):
    words, line, out = str(text).split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out


def draw_section(section, title, subtitle, out_path, *, w=2400, h=1100):
    """One true section, all components, uniform scale."""
    img = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(img)
    d.text((60, 36), title, font=font(42), fill=INK)
    d.text((60, 90), subtitle, font=font(24), fill=GREY)
    loops = []
    for name, comp in section.get("components", {}).items():
        for lp in comp["loops"]:
            if name.startswith("powder_"):
                col, z = KEY["powder"], 3
            elif name.startswith("metal_pan_"):
                col, z = KEY["metal_pan"], 2
            else:
                col, z = KEY["tray"], 1
            loops.append((z, col, np.asarray(lp["points_2d"], float)))
    if not loops:
        d.text((60, 200), "section produced no loops", font=font(30),
               fill=KEY["bad"])
        img.save(out_path)
        return out_path
    allp = np.concatenate([p for _, _, p in loops])
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    box = (60, 170, w - 60, h - 150)
    scale = min((box[2] - box[0]) / max(hi[0] - lo[0], 1e-6),
                (box[3] - box[1]) / max(hi[1] - lo[1], 1e-6))
    ox = box[0] + ((box[2] - box[0]) - (hi[0] - lo[0]) * scale) / 2.0
    oy = box[3] - ((box[3] - box[1]) - (hi[1] - lo[1]) * scale) / 2.0

    def P(p):
        return (ox + (p[0] - lo[0]) * scale, oy - (p[1] - lo[1]) * scale)

    loops.sort(key=lambda t: t[0])
    for _z, col, pts in loops:
        d.polygon([P(p) for p in pts], fill=col, outline=INK)
    d.text((60, h - 108), f"uniform scale {scale:.1f} px/mm — true "
                          f"proportion, no axis stretched", font=font(23),
           fill=GREY)
    _legend(d, w - 460, 190, [("tray material", KEY["tray"]),
                              ("metal pan", KEY["metal_pan"]),
                              ("powder", KEY["powder"])])
    d.text((60, h - 44), NOT_AUTH, font=font(21), fill=KEY["bad"])
    img.save(out_path)
    return out_path


def draw_thickness_map(row, out_path, policy):
    """Per-plane thickness envelope for one strategy."""
    w, h = 2200, 1200
    img = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(img)
    d.text((60, 36), f"PALT-M4B-A3 — {row['strategy']}", font=font(40),
           fill=INK)
    if not row.get("constructible"):
        d.text((60, 100), "NOT CONSTRUCTIBLE", font=font(40), fill=KEY["bad"])
        for i, line in enumerate(_wrap(row["reason"], 92)):
            d.text((60, 170 + i * 34), line, font=font(25), fill=INK)
        d.text((60, h - 44), NOT_AUTH, font=font(21), fill=KEY["bad"])
        img.save(out_path)
        return out_path
    field = row["thickness_field"]
    limit = policy["MAXIMUM_THICKNESS_RATIO"]["mm"]
    d.text((60, 90), f"ratio {row['thickness_ratio']}:1 against a {limit}:1 "
                     f"policy · min {row['minimum_thickness_mm']} mm · max "
                     f"{row['maximum_thickness_mm']} mm · "
                     f"{row['verdict']}", font=font(25),
           fill=KEY["ok"] if row["valid"] else KEY["bad"])
    rows = field["per_plane"]
    x0, x1, y0, y1 = 120, w - 120, 180, h - 260
    mx = max(r["max_mm"] for r in rows) * 1.1
    bw = (x1 - x0) / max(len(rows), 1)
    thr = policy["target_nominal_wall_mm"] * \
        policy["sink_threshold_ratio_vs_nominal"]
    for i, r in enumerate(rows):
        x = x0 + i * bw
        yb = y1 - (r["min_mm"] / mx) * (y1 - y0)
        yt = y1 - (r["max_mm"] / mx) * (y1 - y0)
        col = KEY["bad"] if r["max_mm"] > thr else KEY["ok"]
        d.rectangle([x + 1, yt, x + bw - 1, yb], fill=col)
    ythr = y1 - (thr / mx) * (y1 - y0)
    d.line([(x0, ythr), (x1, ythr)], fill=INK, width=3)
    d.text((x0, ythr - 30), f"sink threshold {thr:.2f} mm", font=font(23),
           fill=INK)
    d.line([(x0, y1), (x1, y1)], fill=INK, width=2)
    d.text((x0, y1 + 12), f"{len(rows)} section planes (x then y)",
           font=font(23), fill=GREY)
    _legend(d, x0, h - 200, [("plane max at or below threshold", KEY["ok"]),
                             ("plane max above threshold", KEY["bad"])])
    d.text((60, h - 44), NOT_AUTH, font=font(21), fill=KEY["bad"])
    img.save(out_path)
    return out_path


def draw_histogram(field, out_path, policy, title):
    w, h = 2000, 1100
    img = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(img)
    d.text((60, 36), title, font=font(40), fill=INK)
    d.text((60, 90), f"{field['sample_count']} medial-ridge samples over "
                     f"{field['plane_count']} planes · "
                     f"{field['sampling']['method']}", font=font(23),
           fill=GREY)
    counts = field["histogram"]["counts"]
    edges = field["histogram"]["edges_mm"]
    x0, x1, y0, y1 = 120, w - 120, 180, h - 240
    mx = max(counts) or 1
    bw = (x1 - x0) / len(counts)
    nominal = policy["target_nominal_wall_mm"]
    for i, c in enumerate(counts):
        x = x0 + i * bw
        yb = y1 - (c / mx) * (y1 - y0)
        mid = (edges[i] + edges[i + 1]) / 2
        col = KEY["ok"] if mid <= nominal * 2 else KEY["bad"]
        d.rectangle([x + 2, yb, x + bw - 2, y1], fill=col)
    d.line([(x0, y1), (x1, y1)], fill=INK, width=2)
    for i in range(0, len(edges), 4):
        x = x0 + i * bw
        d.text((x - 14, y1 + 10), f"{edges[i]:.1f}", font=font(21),
               fill=GREY)
    d.text((x0, y1 + 48), "local wall thickness (mm)", font=font(24),
           fill=INK)
    stats = [("min", field["minimum_thickness_mm"]),
             ("p5", field["percentiles_mm"]["p5"]),
             ("median", field["median_thickness_mm"]),
             ("p95", field["percentiles_mm"]["p95"]),
             ("max", field["maximum_thickness_mm"]),
             ("ratio", field["thickness_ratio"])]
    for i, (k, v) in enumerate(stats):
        d.text((x1 - 420, 200 + i * 36), k, font=font(25), fill=GREY)
        d.text((x1 - 200, 200 + i * 36), f"{v}", font=font(25), fill=INK)
    d.text((60, h - 44), NOT_AUTH, font=font(21), fill=KEY["bad"])
    img.save(out_path)
    return out_path


def draw_comparison(baseline, selected, out_path, policy):
    w, h = 2000, 950
    img = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(img)
    d.text((60, 36), "PALT-M4B-A3 — A2 SOLID vs A3 CORED", font=font(42),
           fill=INK)
    d.text((60, 92), "same pocket geometry; the only difference is the "
                     "underside", font=font(24), fill=GREY)
    limit = policy["MAXIMUM_THICKNESS_RATIO"]["mm"]
    rows = [
        ("minimum wall (mm)", baseline["minimum_thickness_mm"],
         selected["minimum_thickness_mm"], True),
        ("maximum section (mm)", baseline["maximum_thickness_mm"],
         selected["maximum_thickness_mm"], False),
        ("thickness ratio", baseline["thickness_ratio"],
         selected["thickness_ratio"], False),
        (f"within {limit}:1 policy",
         baseline["thickness_ratio"] <= limit,
         selected["thickness_ratio"] <= limit, None),
    ]
    d.text((760, 190), "A2 SOLID UNDERSIDE", font=font(28), fill=GREY)
    d.text((1400, 190), "A3 CORED", font=font(28), fill=KEY["ok"])
    for i, (k, a, b, higher_better) in enumerate(rows):
        y = 250 + i * 62
        d.text((60, y), k, font=font(27), fill=INK)
        d.text((760, y), str(a), font=font(27),
               fill=KEY["bad"] if a is False else GREY)
        col = KEY["ok"]
        if b is False:
            col = KEY["bad"]
        d.text((1400, y), str(b), font=font(27), fill=col)
    d.text((60, h - 100), "the coring removes the 5.65 mm solid outer floor; "
                          "the pocket geometry and the pan fit are untouched",
           font=font(24), fill=GREY)
    d.text((60, h - 44), NOT_AUTH, font=font(21), fill=KEY["bad"])
    img.save(out_path)
    return out_path


def render_core_views(assembly, out_dir):
    """Blender diagnostics of the selected core — visualisation only."""
    import json
    obj_dir = os.path.join(out_dir, "_obj")
    os.makedirs(obj_dir, exist_ok=True)
    meshes = {}
    for name, comp in assembly["components"].items():
        path = os.path.join(obj_dir, f"{name}.obj")
        export_obj(comp, path)
        meshes[name] = path
    tray_only = {"cored_palette_tray": meshes["cored_palette_tray"]}
    deck = assembly["tray"]["elevations_mm"]["deck"]
    base = {"centre": [0.0, 0.0, deck / 2.0], "camera_distance": 700.0,
            "smooth_angle_deg": 31.0}
    outs = {}

    def run(cfg):
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as fh:
            json.dump(cfg, fh)
            p = fh.name
        proc = subprocess.run(
            [BLENDER, "-b", "--factory-startup", "-noaudio", "-P", SCRIPT,
             "--", p], capture_output=True, text=True, timeout=3600)
        if "M4B_A_TRAY_VIEWS_OK" not in proc.stdout:
            raise RuntimeError(proc.stdout[-2500:] + proc.stderr[-1500:])

    a = os.path.join(out_dir, "selected_core_neutral_three_quarter.png")
    run(dict(base, meshes=meshes, mode="clay", samples=64,
             resolution=[2000, 2000], ortho_scale=132.0,
             views={"three_quarter": a}))
    outs["selected_core_neutral_three_quarter"] = a
    b = os.path.join(out_dir, "selected_core_underside.png")
    run(dict(base, meshes=tray_only, mode="clay", samples=64,
             resolution=[2000, 2000], ortho_scale=132.0,
             detail_views={"under": {"az": 34, "el": -34, "scale": 132.0}},
             views={"under": b}))
    outs["selected_core_underside"] = b
    c = os.path.join(out_dir, "selected_core_wireframe.png")
    run(dict(base, meshes=tray_only, mode="wireframe", samples=24,
             wire_px=1.0, resolution=[2400, 2400], ortho_scale=132.0,
             detail_views={"under": {"az": 34, "el": -34, "scale": 132.0}},
             views={"under": c}))
    outs["selected_core_wireframe"] = c
    d_ = os.path.join(out_dir, "selected_core_topology.png")
    run(dict(base, meshes=tray_only, mode="normals", samples=8,
             resolution=[2000, 2000], ortho_scale=132.0,
             detail_views={"under": {"az": 34, "el": -34, "scale": 132.0}},
             views={"under": d_}))
    outs["selected_core_topology"] = d_
    return outs


def build_evidence(out_dir, *, render=True, sampling=None) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    matrix = A3.strategy_matrix(sampling=sampling)
    selection = A3.select_core(matrix)
    assembly = A3.build_selected(selection)
    clearance = A3.clearance_recheck(assembly)
    secs = A3.sections(assembly)
    chosen = next(r for r in matrix["strategies"]
                  if r["strategy"] == selection["selected"])
    policy = matrix["policy"]
    paths = []

    for row in matrix["strategies"]:
        tag = row["strategy"].split("_")[0]
        paths.append(draw_thickness_map(
            row, os.path.join(out_dir, f"strategy_{tag}_thickness_map.png"),
            policy))
    paths.append(draw_histogram(
        chosen["thickness_field"],
        os.path.join(out_dir, "thickness_histogram.png"), policy,
        "PALT-M4B-A3 — THICKNESS DISTRIBUTION, SELECTED CORE"))
    paths.append(draw_comparison(
        matrix["uncored_baseline"], chosen,
        os.path.join(out_dir, "A2_vs_A3_thickness_comparison.png"), policy))

    titles = {
        "centre_row_section": "centre pan row",
        "centre_column_section": "centre pan column",
        "between_two_pans_section": "between two adjacent pans",
        "narrow_ligament_section": "through the narrowest deck ligament",
        "minimum_pocket_wall_section": "through the minimum pocket wall",
        "maximum_thickness_section": "through the thickest region",
        "core_construction_section": "through the selected core",
        "outer_wall_transition_section": "outer wall transition",
    }
    for name, sec in secs.items():
        axis, at = A3.SECTION_PLANES[name]
        paths.append(draw_section(
            sec, f"PALT-M4B-A3 — {titles[name].upper()}",
            f"deterministic Python mesh-plane section, {axis} = {at} mm — "
            "no Blender Boolean participates",
            os.path.join(out_dir, f"{name}.png")))

    renders = render_core_views(assembly, out_dir) if render else {}
    paths += list(renders.values())

    return {"matrix": matrix, "selection": selection, "assembly": assembly,
            "clearance": clearance, "sections": secs, "chosen": chosen,
            "paths": [os.path.basename(p) for p in paths],
            "pixel_hashes": {os.path.basename(p): pixel_hash(p)
                             for p in paths},
            "out_dir": out_dir}
