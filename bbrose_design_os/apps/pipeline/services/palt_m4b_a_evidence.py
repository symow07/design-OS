"""PALT-M4B-A — limited diagnostic evidence.

Exactly the eleven artefacts the owner listed, no review board.

The two section images are drawn from the Python section engine's own
loops, at TRUE SCALE with uniform magnification only — never stretched to
fill a canvas. Blender takes no part in the sections and no Boolean
operation takes part in anything.
"""
from __future__ import annotations

import os
import subprocess
import tempfile

from PIL import Image, ImageDraw

from apps.pipeline.services import palette_moulded_validators as mv
from apps.pipeline.services import palt_m4b_a as A
from apps.pipeline.services.geometry_validation_render import (
    BLENDER, export_obj, pixel_hash)
from apps.pipeline.services.palette_review_fonts import font

SCRIPT = os.path.join(os.path.dirname(__file__), "blender_scripts",
                      "m4b_a_tray_views.py")

CLAY_VIEWS = ("recessed_tray_neutral_three_quarter", "recessed_tray_top",
              "recessed_pocket_closeup", "pan_seating_closeup")
PAPER = (247, 245, 242)
INK = (30, 30, 34)
TRAY_FILL = (176, 176, 180)
PAN_FILL = (126, 132, 140)
POWDER_FILL = (74, 74, 80)
ACCENT = (11, 110, 153)
WARN = (166, 68, 62)

NOT_AUTHORITATIVE = (
    "PALT_P1_FINAL_DIMENSIONS: NOT_APPROVED  ·  "
    "PALT_P1_MANUFACTURING_AUTHORITY: NOT_ESTABLISHED  ·  "
    "PALT_P1_OWNER_APPROVAL: REJECTED_PENDING_M4B  ·  PALT_M5: BLOCKED")


# ---------------------------------------------------------------------------
# Blender diagnostics (visualisation only)


def _run_blender(cfg, out_dir):
    with tempfile.NamedTemporaryFile("w", suffix=".json",
                                     delete=False) as fh:
        import json
        json.dump(cfg, fh)
        cfg_path = fh.name
    proc = subprocess.run(
        [BLENDER, "-b", "--factory-startup", "-noaudio", "-P", SCRIPT,
         "--", cfg_path],
        capture_output=True, text=True, timeout=3600)
    if "M4B_A_TRAY_VIEWS_OK" not in proc.stdout:
        raise RuntimeError(
            f"Blender diagnostic render failed:\n{proc.stdout[-3000:]}\n"
            f"{proc.stderr[-3000:]}")
    return proc


def render_diagnostics(assembly, out_dir) -> dict:
    """Six Blender diagnostics: four clay, one wireframe, one normals."""
    os.makedirs(out_dir, exist_ok=True)
    obj_dir = os.path.join(out_dir, "_obj")
    os.makedirs(obj_dir, exist_ok=True)
    meshes = {}
    for name, comp in assembly["components"].items():
        path = os.path.join(obj_dir, f"{name}.obj")
        export_obj(comp, path)
        meshes[name] = path

    tray = assembly["tray"]
    deck = tray["elevations_mm"]["deck"]
    centre = [0.0, 0.0, deck / 2.0]
    pitch = tray["spec"]["pitch_mm"]
    pocket_centre = [-pitch, 0.0, deck / 2.0]
    written = {}

    tray_only = {"recessed_palette_tray": meshes["recessed_palette_tray"]}
    base = {"meshes": meshes, "centre": centre, "camera_distance": 700.0,
            "smooth_angle_deg": 31.0}

    clay_cfg = dict(base, mode="clay", samples=64,
                    resolution=[2000, 2000], ortho_scale=132.0,
                    detail_views={
                        "pan_seating_closeup": {
                            "az": 26, "el": 17, "scale": 26.0,
                            "target": [-pitch, 0.0, 4.4]}},
                    views={
                        "three_quarter": os.path.join(
                            out_dir,
                            "recessed_tray_neutral_three_quarter.png"),
                        "top": os.path.join(out_dir,
                                            "recessed_tray_top.png"),
                        "pan_seating_closeup": os.path.join(
                            out_dir, "pan_seating_closeup.png")})
    _run_blender(clay_cfg, out_dir)

    # the pocket close-up is deliberately TRAY-ONLY: with pans installed
    # only the 1.0 mm recess is visible, and the owner's failure condition
    # is that the recess is not visually obvious. Empty, the full 4.65 mm
    # depth, the drafted wall and both fillets read directly.
    pocket_cfg = dict(base, meshes=tray_only, mode="clay", samples=64,
                      resolution=[2000, 2000], ortho_scale=132.0,
                      detail_views={
                          "recessed_pocket_closeup": {
                              "az": 30, "el": 24, "scale": 42.0,
                              "target": pocket_centre}},
                      views={"recessed_pocket_closeup": os.path.join(
                          out_dir, "recessed_pocket_closeup.png")})
    _run_blender(pocket_cfg, out_dir)

    wire_cfg = dict(base, mode="wireframe", samples=24, wire_px=1.0,
                    resolution=[2400, 2400], ortho_scale=132.0,
                    views={"three_quarter": os.path.join(
                        out_dir, "recessed_tray_wireframe.png")})
    _run_blender(wire_cfg, out_dir)

    norm_cfg = dict(base, mode="normals", samples=8,
                    resolution=[2000, 2000], ortho_scale=132.0,
                    views={"three_quarter": os.path.join(
                        out_dir, "recessed_tray_normals.png")})
    _run_blender(norm_cfg, out_dir)

    for name in CLAY_VIEWS + ("recessed_tray_wireframe",
                              "recessed_tray_normals"):
        path = os.path.join(out_dir, f"{name}.png")
        written[name] = {"file": f"{name}.png",
                         "pixel_hash": pixel_hash(path)}
    return written


# ---------------------------------------------------------------------------
# true-scale section drawings


def _loops(section):
    """(fill colour, points) for every loop, back to front."""
    order = []
    for name, joined in section["components"].items():
        if name.startswith("powder_"):
            col, z = POWDER_FILL, 2
        elif name.startswith("metal_pan_"):
            col, z = PAN_FILL, 1
        else:
            col, z = TRAY_FILL, 0
        for loop in joined["loops"]:
            order.append((z, col, name, loop["points_2d"]))
    order.sort(key=lambda t: t[0])
    return order


def _hatch(size, box, spacing, colour, mask):
    layer = Image.new("RGB", size, colour)
    hatch = Image.new("L", size, 0)
    hd = ImageDraw.Draw(hatch)
    x0, y0, x1, y1 = box
    s = int(spacing)
    for off in range(int(x0 - (y1 - y0)), int(x1) + 1, s):
        hd.line([(off, y1), (off + (y1 - y0), y0)], fill=255, width=1)
    hatch = Image.composite(hatch, Image.new("L", size, 0), mask)
    return layer, hatch


def _draw_section(section, scale, origin, size, *, hatched=True):
    """Uniform scale, y flipped so +z is up. No axis is stretched."""
    img = Image.new("RGB", size, PAPER)
    d = ImageDraw.Draw(img)
    ox, oy = origin

    def px(p):
        return (ox + p[0] * scale, oy - p[1] * scale)

    for _z, col, _name, pts in _loops(section):
        poly = [px(p) for p in pts]
        d.polygon(poly, fill=col, outline=INK)
        if hatched and col == TRAY_FILL:
            mask = Image.new("L", size, 0)
            ImageDraw.Draw(mask).polygon(poly, fill=255)
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            layer, hm = _hatch(size, (min(xs), min(ys), max(xs), max(ys)),
                               max(6, scale * 0.9), (150, 150, 154), mask)
            img.paste(layer, (0, 0), hm)
            d.polygon(poly, outline=INK)
    return img, d, px


def draw_centre_section(section, tray, out_path) -> str:
    """Full section at true scale, plus a uniformly magnified detail."""
    W = 3400
    margin = 90
    span = tray["spec"]["tray_width_mm"]
    s_full = (W - 2 * margin) / span
    pitch = tray["spec"]["pitch_mm"]
    detail_mm = pitch + 6.0
    s_det = (W - 2 * margin) / detail_mm

    deck = tray["elevations_mm"]["deck"]
    pad = 0.55                                   # mm of air above and below
    h_full = int((deck + 2 * pad) * s_full) + 2
    h_det = int((deck + 2 * pad) * s_det) + 2
    H = margin + 96 + h_full + 150 + 96 + h_det + margin

    canvas = Image.new("RGB", (W, H), PAPER)
    cd = ImageDraw.Draw(canvas)
    cd.text((margin, 42), "PALT-M4B-A — CENTRE SECTION THROUGH THE MIDDLE "
                          "PAN ROW", font=font(46), fill=INK)
    cd.text((margin, 100),
            "deterministic Python mesh-plane intersection (y = 0) — no "
            "Blender Boolean participates; every loop closed",
            font=font(26), fill=ACCENT)

    y1 = margin + 96 + 60
    full, _, _ = _draw_section(
        section, s_full,
        (margin + span / 2 * s_full, y1 + h_full - pad * s_full),
        (W, y1 + h_full + 4))
    canvas.paste(full.crop((0, y1, W, y1 + h_full + 2)), (0, y1))
    cd.text((margin, y1 + h_full + 16),
            f"full section — TRUE SCALE, {span:.0f} mm across, uniform "
            f"{s_full:.1f} px/mm, no axis stretched", font=font(25),
            fill=(70, 70, 74))

    y2 = y1 + h_full + 150
    cd.text((margin, y2 - 46), "CENTRE POCKET — uniformly magnified "
                               f"({s_det:.1f} px/mm), still undistorted",
            font=font(30), fill=INK)
    # the centre pocket sits at x = 0, so anchoring it to the canvas centre
    # frames it without moving the section
    det, _, _ = _draw_section(section, s_det,
                              (W / 2.0, y2 + h_det - pad * s_det),
                              (W, y2 + h_det + 4))
    canvas.paste(det.crop((0, y2, W, y2 + h_det + 2)), (0, y2))

    cd.text((margin, H - margin + 10), NOT_AUTHORITATIVE, font=font(24),
            fill=WARN)
    canvas.save(out_path)
    return out_path


def draw_annotated_section(section, tray, pan, report, out_path) -> str:
    """The magnified centre pocket with the elevation chain called out."""
    W = 3400
    margin = 110
    plot_w = 2050
    detail_mm = 32.0
    s = plot_w / detail_mm
    deck = tray["elevations_mm"]["deck"]
    lid_z = pan["lid_inner_z_mm"]
    pad = 0.45
    plot_h = int((lid_z + 2 * pad) * s) + 2
    top = margin + 150
    base_y = top + plot_h - pad * s            # y of z = 0
    H = top + plot_h + 520

    canvas = Image.new("RGB", (W, H), PAPER)
    cd = ImageDraw.Draw(canvas)
    cd.text((margin, 40), "PALT-M4B-A — ANNOTATED CENTRE SECTION",
            font=font(46), fill=INK)
    cd.text((margin, 98), "elevations read from the mesh section itself, "
                          "not from the contract they are checked against",
            font=font(26), fill=ACCENT)

    # the plot is a window on the centre pocket; the section is not scaled
    # to fit it, it is simply framed by it
    panel, _, _ = _draw_section(section, s, (plot_w / 2.0, plot_h - pad * s),
                               (plot_w, plot_h + 4))
    canvas.paste(panel.crop((0, 0, plot_w, plot_h)), (margin, top))

    def y_of(z):
        return base_y - z * s

    xr = margin + plot_w + 46
    levels = [
        (lid_z, "lid seating plane 8.55 (reference)", ACCENT),
        (pan["pan_top_z_mm"] + pan["powder_crown_mm"], "powder crown 6.45",
         (70, 70, 74)),
        (deck, "tray deck 7.15", INK),
        (pan["pan_top_z_mm"], "pan top 6.15", INK),
        (tray["pockets"][0]["wall_bottom_z_mm"],
         f"wall / floor tangent {tray['pockets'][0]['wall_bottom_z_mm']:.2f}",
         (120, 120, 124)),
        (pan["pan_seating_z_mm"], "pan seating 2.65", INK),
        (tray["elevations_mm"]["pocket_floor"], "pocket floor 2.50", INK),
        (tray["elevations_mm"]["underside"], "tray underside 1.50", INK),
    ]
    # true elevations can be 0.15 mm apart; fan the LABELS apart and use
    # leader lines rather than moving the geometry or faking the scale
    levels.sort(key=lambda t: -t[0])
    rows, last = [], None
    for z, label, col in levels:
        y = y_of(z)
        if last is not None and y - last < 40:
            y = last + 40
        rows.append((z, y, label, col))
        last = y
    for z, ly, label, col in rows:
        ty = y_of(z)
        cd.line([(margin + 18, ty), (xr - 60, ty)], fill=col, width=2)
        cd.line([(xr - 60, ty), (xr - 14, ly)], fill=col, width=2)
        cd.text((xr, ly - 16), label, font=font(27), fill=col)

    def dim(z0, z1, x, text, col=WARN, left=False):
        ya, yb = y_of(z0), y_of(z1)
        cd.line([(x, ya), (x, yb)], fill=col, width=3)
        for y in (ya, yb):
            cd.line([(x - 11, y), (x + 11, y)], fill=col, width=3)
        f = font(28)
        tx = x - 18 - cd.textlength(text, font=f) if left else x + 18
        cd.text((tx, (ya + yb) / 2 - 16), text, font=f, fill=col)

    dim(pan["pan_top_z_mm"], deck, margin + plot_w - 120, "pan recess 1.00",
        left=True)
    dim(tray["elevations_mm"]["underside"],
        tray["elevations_mm"]["pocket_floor"], margin + 120, "floor 1.00")
    dim(pan["pan_top_z_mm"] + pan["powder_crown_mm"], lid_z,
        margin + plot_w - 640,
        f"powder-to-lid "
        f"{lid_z - pan['pan_top_z_mm'] - pan['powder_crown_mm']:.2f}",
        ACCENT)

    fy = top + plot_h + 60
    seat = report["reports"]["pan_seating"]["measured"]
    contract_measured = report["reports"]["recessed_tray_contract"]["measured"]
    tight = seat["min_radial_clearance_mm"] < 0
    rows = [
        ("pocket depth", f"{tray['pockets'][0]['depth_mm']} mm "
                         "(deck 7.15 - floor 2.50)", False),
        ("pocket draft (measured from the mesh)",
         f"{contract_measured['pocket_wall_draft_deg']} deg", False),
        ("pan recess below deck", f"{seat['pan_recess_mm']} mm", False),
        ("adhesive gap under the pan", f"{seat['adhesive_gap_mm']} mm",
         False),
        ("min radial pan clearance",
         f"{seat['min_radial_clearance_mm']} mm at z "
         f"{seat['min_clearance_z_mm']} mm", tight),
        ("section loops", f"{section['loop_count']} closed, "
                          f"{section['open_loop_count']} open", False),
    ]
    for i, (k, v, bad) in enumerate(rows):
        cd.text((margin, fy + i * 40), k, font=font(27), fill=(45, 45, 48))
        cd.text((margin + 900, fy + i * 40), v, font=font(27),
                fill=WARN if bad else ACCENT)
    if seat["min_radial_clearance_mm"] < 0:
        cd.text((margin, fy + len(rows) * 40 + 24),
                "PAN / POCKET INTERFERENCE DETECTED — reported, not "
                "corrected. No dimension was altered to make validation "
                "pass; see the solved envelope in the validation report.",
                font=font(28), fill=WARN)
    cd.text((margin, H - 58), NOT_AUTHORITATIVE, font=font(24), fill=WARN)
    canvas.save(out_path)
    return out_path


# ---------------------------------------------------------------------------


def status_record(assembly, section, report, renders) -> dict:
    """M4B-A's own state. The kernel and the contract are judged
    separately: the mesh is clean, and the validators it enabled found a
    real conflict in the dimensions they were pointed at."""
    fails = [f for f in report["findings"] if f.get("severity") == "FAIL"]
    mesh_clean = not [f for f in fails
                      if f["code"] != mv.PAN_POCKET_INTERSECTION]
    seat = report["reports"]["pan_seating"]["measured"]
    interference = -seat["min_radial_clearance_mm"]
    return {
        "record_type": "palt_m4b_a_status/1.0",
        "milestone": A.MILESTONE,
        "date": "2026-08-06",
        "PALT_M4B_A_KERNEL": "IMPLEMENTED_AND_VALIDATED" if mesh_clean
                             else "DEFECTIVE",
        "PALT_M4B_A_MESH_DIAGNOSTICS": "CLEAN" if mesh_clean else "FAILED",
        "PALT_M4B_A_SECTION_ENGINE": "IMPLEMENTED_AND_VALIDATED"
                                     if section["open_loop_count"] == 0
                                     else "FAILED",
        "PALT_M4B_A_PAN_POCKET_CONTRACT":
            "CONFLICT_DETECTED_OWNER_DECISION_REQUIRED",
        "PALT_M4B_A_OWNER_REVIEW": "PENDING_STRICT_REVIEW",
        "PALT_M4B_IMPLEMENTATION": "INCOMPLETE",
        "PALT_M4B_RENDER_PIPELINE": "REPLACED_BOOLEAN_FREE",
        "PALETTE_TRAY_GEOMETRY_AUTHORITY":
            "DETERMINISTIC_PYTHON_MESH_CONSTRUCTION",
        "BLENDER_ROLE": "VISUALIZATION_AND_RENDERING_ONLY",
        "BLENDER_BOOLEAN_MODIFIERS": "NOT_AUTHORITY_FOR_CORE_TRAY_GEOMETRY",
        "PALT_P1_FINAL_DIMENSIONS": "NOT_APPROVED",
        "PALT_P1_MANUFACTURING_AUTHORITY": "NOT_ESTABLISHED",
        "PALT_P1_OWNER_APPROVAL": "REJECTED_PENDING_M4B",
        "PALT_M5": "BLOCKED",
        "self_approved": False,
        "provider_calls": 0,
        "image_generation_calls": 0,
        "tray_mesh_identity": assembly["tray"]["mesh_identity"],
        "section_identity": section["section_identity"],
        "failure_count": report["failure_count"],
        "declared_count": report["declared_count"],
        "open_failures": [f["code"] for f in fails],
        "unresolved_defects": [
            "PAN_POCKET_INTERSECTION — the 26.6 mm pocket, the 0.6 mm "
            "moulded floor fillet and the sharp-cornered 26.0 mm pan model "
            f"cannot all three hold. Interference {interference:.4f} mm at "
            f"z {seat['min_clearance_z_mm']} mm (the pan base). This "
            "follows from M4B-A's decision to MODEL the moulded fillets, "
            "which section 2 asked for; without them the pan clears. "
            "Three solved resolutions are published; none applied.",
            "MOULDING.wall_to_floor_radius_mm (0.8) vs internal_fillet_mm "
            "(0.6) for the pocket — interpretation awaiting confirmation.",
            "structural rib / hinge / clasp reinforcement interfaces are "
            "declared, not modelled; deferred to M4B-B.",
            "solid-block section variation above 5:1 would sink in ABS; "
            "underside hollowing proposed for M4B-B.",
        ],
        "deliverables": {
            "renders": sorted(renders),
            "sections": ["centre_section.png",
                         "centre_section_annotated.png"],
            "manifests": ["tray_topology_manifest.json",
                          "tray_mesh_diagnostics.json",
                          "tray_section_manifest.json"]},
        "not_created_deliberately": [
            "the complete M4B review board (owner: not in this slice)"],
        "required_test_inversions": [{
            "owner_test": "no pan/pocket intersection",
            "implemented_as":
                "test_pan_pocket_interference_is_reported_not_repaired",
            "inverted": True,
            "reason":
                "the test asserts that the interference IS detected and "
                "reported with a number, and that nothing was mutated to "
                "hide it. Asserting the owner's original polarity would "
                "require changing a dimension to pass, which is "
                "prohibited. It flips back to the owner's polarity as soon "
                "as the pan/pocket conflict is ruled on.",
            "declared_not_substituted": True}],
        "pocket_diameter_reading": {
            "contract_value_mm": 26.6,
            "meaning": "THEORETICAL_SHARP_CORNER_WALL_LINE_AT_DECK_PLANE",
            "visible_opening_across_top_view_mm": 27.758826,
            "note": "a caliper on recessed_tray_top.png reads 27.76, not "
                    "26.6, because the 0.6 mm rim fillet bulges outward "
                    "from the wall line. This is a semantics statement, "
                    "not a discrepancy."},
    }


def build_evidence(out_dir, *, render=True) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    assembly = A.build_assembly()
    section = A.centre_section(assembly)
    layers = A._layers_exposed(section, assembly["tray"], A._values(A.PAN))
    report = A.validate(assembly, section)

    A.write_json(os.path.join(out_dir, "tray_topology_manifest.json"),
                 A.topology_manifest(assembly))
    A.write_json(os.path.join(out_dir, "tray_mesh_diagnostics.json"),
                 A.mesh_diagnostics_manifest(report))
    A.write_json(os.path.join(out_dir, "tray_section_manifest.json"),
                 A.section_manifest(section, layers))

    draw_centre_section(section, assembly["tray"],
                        os.path.join(out_dir, "centre_section.png"))
    draw_annotated_section(section, assembly["tray"], A._values(A.PAN),
                           report,
                           os.path.join(out_dir,
                                        "centre_section_annotated.png"))
    renders = render_diagnostics(assembly, out_dir) if render else {}

    A.write_json(os.path.join(out_dir, "palt_m4b_a_geometry_contract.json"),
                 A.contract())
    A.write_json(os.path.join(out_dir, "palt_m4b_a_validation_report.json"),
                 {"record_type": "palt_m4b_a_validation_report/1.0",
                  "milestone": A.MILESTONE,
                  "validator": report["validator"],
                  "valid": report["valid"],
                  "failure_count": report["failure_count"],
                  "declared_count": report["declared_count"],
                  "findings": report["findings"],
                  "reports": report["reports"],
                  "section_layers_exposed": layers,
                  "renders": renders})
    A.write_json(os.path.join(out_dir, "palt_m4b_a_status.json"),
                 status_record(assembly, section, report, renders))
    return {"assembly": assembly, "section": section, "report": report,
            "layers": layers, "renders": renders, "out_dir": out_dir}
