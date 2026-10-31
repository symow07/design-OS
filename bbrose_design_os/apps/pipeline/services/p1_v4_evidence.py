"""P1 V4 evidence orchestration — owner STRICT-standard review package.

V3 was owner-REJECTED (visual quality + product realism UNACCEPTABLE,
match to the real bottle POOR). V4 is judged against the owner
photographs, never against V3. Shared machinery (mask authority, neutral
clay mode, material studio, shoulder diagnostic) is reused from
``p1_v3_evidence``; everything version-specific lives here so V1–V3 stay
byte-reproducible.
"""
from __future__ import annotations

import json
import os

import numpy as np
from PIL import Image, ImageDraw

from apps.pipeline.services import mesh_diagnostics as md
from apps.pipeline.services import p1_pilot_geometry as p1
from apps.pipeline.services import p1_v3_evidence as ev3
from apps.pipeline.services.p1_review_board import _fit, _font

REV_COLOURS = {"V1": (170, 170, 175), "V2": (205, 140, 140),
               "V3": (200, 60, 60), "V4": (40, 90, 200)}


def run_mask_validation(out_dir, facts) -> tuple:
    """Mask-authority metrics for every revision + V4 determinism."""
    E = lambda n: os.path.join(out_dir, n)  # noqa: E731
    res = (800, 1100)
    mm_per_px = p1.OWNER["total_assembled_height_mm"] * 1.12 / res[1]
    masks = {}
    for rev in ("V1", "V2", "V3", "V4"):
        _, meshes, _ = p1.build_p1_assembly(rev)
        ev3.render_masks(meshes, {"front": E(f"silhouette_{rev}_front.png")},
                         resolution=res)
        masks[rev] = ev3.load_mask(E(f"silhouette_{rev}_front.png"))
    _, m4, _ = p1.build_p1_assembly("V4")
    ev3.render_masks(m4, {"front": E("silhouette_V4_front_repeat.png"),
                          "side": E("silhouette_V4_side.png"),
                          "closure_detail": E("silhouette_V4_closure.png")},
                     detail_views={"closure_detail": {
                         "center_mm": facts["closure_center_mm"],
                         "height_mm": facts["closure_height_mm"]}},
                     resolution=res)
    repeat = ev3.load_mask(E("silhouette_V4_front_repeat.png"))
    front = ev3.mask_metrics(masks["V4"], mm_per_px)
    side = ev3.mask_metrics(ev3.load_mask(E("silhouette_V4_side.png")),
                            mm_per_px)
    closure = ev3.mask_metrics(
        ev3.load_mask(E("silhouette_V4_closure.png")),
        facts["closure_height_mm"] * 1.6 / res[1])
    validation = {
        "record_type": "p1_v4_validation_manifest/1.0",
        "revision": "V4",
        "mask_authority": "unlit emission alpha pass "
                          "(blender_scripts/silhouette_mask.py) — the mask "
                          "scene contains NO lights, so masks are "
                          "lighting-independent by construction",
        "front": front, "side": side, "closure_detail": closure,
        "deterministic": ev3.mask_hash(masks["V4"]) == ev3.mask_hash(repeat),
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
        "mask_hashes": {f"{rev}_front": ev3.mask_hash(m)
                        for rev, m in masks.items()},
    }
    return ev3._jsonable(validation), masks, mm_per_px


def build_comparisons(out_dir, photo_front, mm_per_px, masks) -> None:
    E = lambda n: os.path.join(out_dir, n)  # noqa: E731
    m1, m2, m3, m4 = (masks["V1"], masks["V2"], masks["V3"], masks["V4"])
    gap = 30
    h, w = m4.shape
    combined = np.full((h, w, 3), 255, dtype=np.uint8)
    combined[m3 & ~m4] = REV_COLOURS["V3"]
    combined[m4 & ~m3] = REV_COLOURS["V4"]
    combined[m1 & ~m2 & ~m3 & ~m4] = REV_COLOURS["V1"]
    combined[m3 & m4] = (70, 70, 75)
    panels = [ev3._mask_image(m1), ev3._mask_image(m2),
              ev3._mask_image(m3), ev3._mask_image(m4),
              ev3._overlay(m3, m4), Image.fromarray(combined)]
    labels = ["V1 - OWNER REJECTED", "V2 - OWNER REJECTED",
              "V3 - OWNER REJECTED", "V4 - CURRENT REVISION",
              "V3/V4 overlay", "V1/V3/V4 combined"]
    canvas = Image.new("RGB", (w * 6 + gap * 5 + 60, h + 260),
                       (247, 245, 242))
    d = ImageDraw.Draw(canvas)
    d.text((30, 16), "P1 V1 / V2 / V3 / V4 SILHOUETTES - deterministic "
                     "mask authority (unlit alpha pass; NO thresholded "
                     "shaded RGB; same pinned camera)", font=_font(44),
           fill=(30, 30, 34))
    d.text((30, 72), "V4 changes: shoulder narrows EARLIER with "
                     "progressive curvature and a soft neck root (no "
                     "swelling, no pinch) + bulb with near-vertical sides "
                     "| unchanged: body wall, base, collar bounds, every "
                     "accepted owner dimension | overlay: red=V3 only, "
                     "blue=V4 only, dark=agreement", font=_font(28),
           fill=(90, 70, 60))
    x = 30
    for img, label in zip(panels, labels):
        canvas.paste(img, (x, 130))
        d.text((x + 4, 140 + h), label, font=_font(28), fill=(45, 45, 48))
        x += w + gap
    canvas.save(E("v1_v2_v3_v4_silhouette_comparison.png"))

    def region(y_lo_mm, y_hi_mm, out, title):
        Hmm = p1.OWNER["total_assembled_height_mm"]
        row0 = max(int(h / 2 - (y_hi_mm - Hmm / 2) / mm_per_px), 0)
        row1 = min(int(h / 2 - (y_lo_mm - Hmm / 2) / mm_per_px), h)
        ch = row1 - row0
        pan3 = ev3._mask_image(m3[row0:row1])
        pan4 = ev3._mask_image(m4[row0:row1])
        ov = ev3._overlay(m3[row0:row1], m4[row0:row1])
        c = Image.new("RGB", (w * 3 + gap * 2 + 60, ch + 220),
                      (247, 245, 242))
        dd = ImageDraw.Draw(c)
        dd.text((30, 14), title, font=_font(40), fill=(30, 30, 34))
        dd.text((30, 66), "mask authority (unlit alpha) | red=V3 only, "
                          "blue=V4 only, dark=agreement", font=_font(26),
                fill=(90, 70, 60))
        xx = 30
        for img, lab in ((pan3, "V3 (rejected)"), (pan4, "V4"),
                         (ov, "overlay")):
            c.paste(img, (xx, 110))
            dd.text((xx + 4, 118 + ch), lab, font=_font(26),
                    fill=(45, 45, 48))
            xx += w + gap
        c.save(E(out))

    region(58.0, 80.0, "v3_v4_shoulder_comparison.png",
           "V3 vs V4 SHOULDER (close-up)")
    region(92.0, 115.5, "v3_v4_bulb_comparison.png",
           "V3 vs V4 BULB (close-up)")

    files = ["material_front.png", "neutral_front.png",
             "shoulder_detail.png", "bulb_detail.png", "neck_detail.png",
             "base_detail.png"]
    titles = ["V4 material front", "V4 neutral front",
              "V4 shoulder close-up", "V4 bulb close-up",
              "V4 neck/collar close-up", "V4 base close-up"]
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
    d.text((30, 16), "P1 OWNER PHOTO vs V4 - QUALITATIVE ONLY",
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
    canvas.save(E("owner_photo_vs_v4.png"))


def write_manifests(out_dir, contract, validation, glass) -> None:
    E = lambda n: os.path.join(out_dir, n)  # noqa: E731
    json.dump(contract, open(E("geometry_manifest.json"), "w"), indent=1)
    json.dump({
        "record_type": "p1_v4_materials_manifest/1.0",
        "owner_confirmed_materials": p1.MATERIALS,
        "material_nodes": ev3.MATERIAL_NODES,
        "v4_recalibration": {
            "glass_surface_roughness": 0.36,
            "glass_transmission_weight": 1.0,
            "glass_ior": 1.5,
            "volume_absorption_colour": [0.99, 0.86, 0.70],
            "volume_absorption_density_per_mm": 0.05,
            "transmission_bounces": 16,
            "max_bounces": 20,
            "reason": "V3 read as dark brown opaque smoked glass. Root "
                      "cause found in V4: the bottle was modelled EMPTY, "
                      "so all colour had to come from the glass itself — "
                      "which physically saturates to brown/red over the "
                      "long base path. V4 keeps the glass only lightly "
                      "tinted + frosted and adds the serum fill, giving "
                      "an even warm-orange body, a lighter empty neck and "
                      "NO dark-red base band",
            "collar": {"base_colour": [0.72, 0.165, 0.012],
                       "roughness": 0.10,
                       "fine_vertical_ribbing": "procedural wave bump, "
                       "strength 0.18 (photo-supported, subtle)"},
            "bulb": {"base_colour": [0.70, 0.115, 0.03],
                     "roughness": 0.20},
            "backdrop": "grey 0.60 + dedicated backdrop wash light "
                        "(9.0e5 W) so transmitted background is luminous",
            "serum_fill": {
                "authority": "VISUALIZATION_ONLY_GEOMETRY",
                "why": "the real bottle is FILLED (IMG_3120) — the even "
                       "warm body colour and the lighter empty neck come "
                       "from the contents; an empty amber shell can only "
                       "saturate to the rejected red base band",
                "shader": "Principled transmission 1.0, IOR 1.36, "
                          "roughness 0.03 + Volume Absorption "
                          "[1.0,0.66,0.02] @ 0.11/mm (solved from Beer-Lambert: transmitted = exp(-d*(1-colour)*path) targeted at R~1.0 G~0.5 B~0.1 over the ~30 mm body path)",
                "fill_line_authority": "VISUAL_ESTIMATE (0.86 of cavity)"},
        },
        "glass_construction": {
            "strategy": "single revolved closed manifold: outer surface + "
                        "mouth rim + inner cavity surface + inner floor",
            "wall_body_mm": p1.GLASS_WALL_BODY_MM,
            "wall_neck_mm": p1.GLASS_WALL_NECK_MM,
            "inner_floor_mm": p1.BOTTOM_GLASS_THICKNESS_MM,
            "authority": "VISUALIZATION_ONLY_GEOMETRY — never measured, "
                         "never manufacturing geometry",
            "identity": glass["mesh_identity"],
        },
    }, open(E("materials_manifest.json"), "w"), indent=1)
    json.dump({
        "record_type": "p1_v4_assumptions_manifest/1.0",
        "authority_classes": list(p1.AUTHORITY_CLASSES),
        "provisional_assumptions": contract["provisional_assumptions"],
        "modelling_simplifications": contract["modelling_simplifications"],
        "shoulder_control_points_v4": contract["shoulder_control_points_v4"],
        "bulb_control_points_v4": contract["bulb_control_points_v4"],
        "collar_ribbing_v4": contract["collar_ribbing_v4"],
        "accuracy_status": contract["accuracy_status"],
        "calibration_statement": "owner photographs are perspective and "
                                 "uncalibrated — no calibrated overlay "
                                 "accuracy is claimed anywhere in V4",
    }, open(E("assumptions_manifest.json"), "w"), indent=1)
    src = json.load(open(os.path.join(
        "docs", "visual_quality", "rbv", "p1_pilot", "2026-08-04",
        "source_derivation_manifest.json")))
    src["record_type"] = "p1_v4_source_derivation_manifest/1.0"
    src["v4_note"] = "V1 research carried forward unchanged; V4 adds no " \
                     "new online sources — shoulder/bulb control points " \
                     "and collar ribbing are VISUAL_ESTIMATE_FROM_OWNER_" \
                     "PHOTO"
    json.dump(src, open(E("source_derivation_manifest.json"), "w"),
              indent=1)
    json.dump(validation, open(E("validation_manifest.json"), "w"),
              indent=1)


def build_board(out_dir, photo_front, photo_parts) -> dict:
    E = lambda n: os.path.join(out_dir, n)  # noqa: E731
    board = Image.new("RGB", (4400, 9600), (247, 245, 242))
    d = ImageDraw.Draw(board)
    d.text((60, 40), "P1 DROPPER SERUM BOTTLE - OWNER VISUAL REVIEW "
                     "BOARD (V4)", font=_font(64), fill=(30, 30, 34))
    for i, line in enumerate([
        "V4 REVISION - V1, V2 and V3 all owner-REJECTED and preserved "
        "unchanged | owner approval: PENDING_VISUAL_REVIEW | GATE_2: "
        "BLOCKED | manufacturing authority: NOT_ESTABLISHED",
        "sections: OWNER PHOTOGRAPHY | OWNER-MEASURED DIMENSIONS | "
        "OWNER-CONFIRMED MATERIALS | ONLINE-ANALOGOUS EVIDENCE | "
        "CALCULATED | VISUALLY ESTIMATED | NEUTRAL GEOMETRY | MATERIAL "
        "VALIDATION | VISUALIZATION-ONLY INNER GLASS | OMITTED DETAILS",
        "photographs are perspective + uncalibrated - NO calibrated "
        "overlay accuracy claimed | THREAD_GEOMETRY_NOT_MODELLED | masks "
        "= unlit alpha authority | judged against the real photographs, "
        "never against V3",
    ]):
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
               "V4 material front (transparent frosted orange glass)",
               AMBER) + 70
    x += panel(Image.open(E("material_three_quarter.png")).convert("RGB"),
               x, y, 900, 1300, "MATERIAL VALIDATION",
               "V4 material three-quarter", AMBER) + 70
    x += panel(Image.open(E("neutral_front.png")).convert("RGB"), x, y,
               900, 1300, "NEUTRAL GEOMETRY VALIDATION",
               "V4 neutral front (clay)", GREY) + 70
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
    for name, title in (("shoulder_detail.png", "shoulder detail (V4)"),
                        ("bulb_detail.png", "bulb detail (V4)"),
                        ("base_detail.png", "base detail (V4)")):
        x += panel(Image.open(E(name)).convert("RGB"), x, y3, 700, 990,
                   "NEUTRAL GEOMETRY VALIDATION", title, GREY) + 56
    panel(Image.open(E("shoulder_profile_diagnostic.png")).convert("RGB"),
          x, y3, 4340 - x, 1050, "VISUALLY ESTIMATED",
          "shoulder profile diagnostic (V1-V4 + V4 control points)", TEAL)

    y4 = y3 + 1290
    panel(Image.open(E("glass_transmission_diagnostic.png")).convert(
        "RGB"), 60, y4, 4280, 1150, "MATERIAL VALIDATION",
        "glass-transmission diagnostic - transparent frosted orange glass "
        "(VISUALIZATION-ONLY inner glass)", AMBER)

    y5 = y4 + 1380
    panel(Image.open(E("v1_v2_v3_v4_silhouette_comparison.png")).convert(
        "RGB"), 60, y5, 2700, 1150, "CALCULATED",
        "V1/V2/V3/V4 silhouettes - deterministic mask authority", TEAL)
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
        ("mask determinism", "required", str(validation['deterministic'])),
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
            "GL18-class thread (stamped on views) | base embossing",
            "50ml/46 | label artwork | pipette in renders",
            "inner glass = VISUALIZATION_ONLY (never manufacturing)"]):
        d.text((x_leg, y5 + 440 + i * 40), line, font=_font(28),
               fill=(140, 70, 70))

    y6 = y5 + 1330
    panel(Image.open(E("v3_v4_shoulder_comparison.png")).convert("RGB"),
          60, y6, 2100, 900, "CALCULATED", "V3 vs V4 shoulder close-up",
          TEAL)
    panel(Image.open(E("v3_v4_bulb_comparison.png")).convert("RGB"),
          2260, y6, 2080, 900, "CALCULATED", "V3 vs V4 bulb close-up",
          TEAL)

    y7 = y6 + 1150
    panel(Image.open(E("owner_photo_vs_v4.png")).convert("RGB"), 60, y7,
          4280, 900, "OWNER PHOTOGRAPH",
          "owner photo vs V4 (qualitative only - uncalibrated)", BLUE)

    fy = y7 + 1120
    d.text((60, fy), "evidence: docs/visual_quality/rbv/p1_pilot/"
                     "2026-08-04_v4 | V1-V3 preserved | contract "
                     "p1_provisional_geometry/1.0 revision V4",
           font=_font(26), fill=(90, 90, 92))
    d.text((60, fy + 40), "visual review + pipeline validation only - "
                          "NEVER supplier/manufacturing geometry",
           font=_font(26), fill=(140, 70, 70))
    board = board.crop((0, 0, 4400, fy + 110))
    board.save(E("owner_review_board.png"))
    board.save(E("owner_review_board.pdf"), "PDF", resolution=200.0)
    manifest = {
        "record_type": "p1_v4_owner_review_board_manifest/1.0",
        "board": {"png": "owner_review_board.png",
                  "pdf": "owner_review_board.pdf",
                  "pixel_dimensions": list(board.size)},
        "photo_treatment": "whole-region crops + uniform scaling + "
                           "lossless 90-degree rotation only; originals "
                           "untouched",
        "calibration_statement": "no calibrated overlay accuracy claimed",
        "accuracy_status": p1.build_p1_contract("V4")["accuracy_status"],
    }
    json.dump(manifest, open(E("owner_review_board_manifest.json"), "w"),
              indent=1)
    return manifest


def generate_v4(out_dir, *, neutral_samples=64, material_samples=112,
                skip_neutral=False, skip_material=False) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    contract = p1.build_p1_contract("V4")
    if contract["consistency_status"] != "PASS":
        raise RuntimeError(f"V4 consistency REJECTED: "
                           f"{contract['consistency_findings']}")
    records, meshes, facts = p1.build_p1_assembly("V4")
    glass = p1.build_p1_glass_solid("V4")
    liquid = p1.build_p1_liquid_solid("V4")
    for name, solid in (("glass", glass), ("liquid", liquid)):
        diag = md.diagnose_mesh(solid["vertices"], solid["faces"])
        if diag["codes"]:
            raise RuntimeError(f"{name} solid diagnostics: {diag['codes']}")

    if not skip_neutral:
        ev3.generate_neutral(out_dir, meshes, records, facts,
                             samples=neutral_samples, fixture_id="P1_V4")
    if not skip_material:
        ev3.generate_material(out_dir, glass, meshes["collar"],
                              meshes["bulb"], samples=material_samples,
                              liquid=liquid)
    validation, masks, mm_per_px = run_mask_validation(out_dir, facts)

    photo_dir = os.path.join("docs", "visual_quality", "rbv",
                             "owner_inputs", "2026-08-04", "originals",
                             "measurments", "P1 — Dropper serum bottle")
    photo_front = Image.open(os.path.join(photo_dir, "IMG_3120.jpg")) \
        .convert("RGB").crop((450, 950, 2400, 3024)) \
        .transpose(Image.Transpose.ROTATE_270)
    photo_parts = Image.open(os.path.join(photo_dir, "IMG_3123.jpg")) \
        .convert("RGB").crop((500, 1000, 3950, 2200))

    ev3.shoulder_profile_diagnostic(
        os.path.join(out_dir, "shoulder_profile_diagnostic.png"),
        photo_front.crop((0, int(photo_front.height * 0.18),
                          photo_front.width,
                          int(photo_front.height * 0.72))))
    build_comparisons(out_dir, photo_front, mm_per_px, masks)
    write_manifests(out_dir, contract, validation, glass)
    board = build_board(out_dir, photo_front, photo_parts)
    return {"contract": contract, "validation": validation,
            "board": board, "glass_identity": glass["mesh_identity"],
            "liquid_identity": liquid["mesh_identity"]}
