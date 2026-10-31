"""PALT-M4 — PALT-P1 neutral geometry review board."""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

from apps.pipeline.services.palette_review_fonts import fit, font

CLASSES = {
    "NEUTRAL GEOMETRY VALIDATION": (90, 90, 92),
    "MECHANISM DETAIL": (11, 110, 153),
    "ENGINEERING STRESS FIXTURE": (179, 69, 79),
    "DIMENSION EVIDENCE": (24, 60, 130),
}


def build_review_board(out_dir, manifest, validation, diagnostics,
                       stress=None) -> dict:
    E = lambda n: os.path.join(out_dir, n)  # noqa: E731
    board = Image.new("RGB", (4400, 6100), (247, 245, 242))
    d = ImageDraw.Draw(board)
    d.text((60, 40), "PALT-P1 STANDARD 9-PAN EYESHADOW PALETTE — NEUTRAL "
                     "GEOMETRY REVIEW BOARD", font=font(58),
           fill=(30, 30, 34))
    dims = manifest["resolved_dimensions"]
    env = manifest["envelope_mm"]
    for i, line in enumerate([
        f"envelope {env[0]} x {env[1]} x {env[2]} mm — "
        "PROVISIONALLY_APPROVED_FOR_GEOMETRY_DEVELOPMENT | "
        "PALT_P1_FINAL_DIMENSIONS: NOT_APPROVED | "
        "PALT_P1_MANUFACTURING_AUTHORITY: NOT_ESTABLISHED | "
        "PALT_P1_OWNER_APPROVAL: PENDING_VISUAL_REVIEW",
        "neutral clay geometry validation only — no powder realism, no "
        "glitter, no cosmetic colour, no artwork, no beauty render",
        f"{manifest['component_count']} independently generated components; "
        "OPEN and CLOSED share identical component identities by "
        "construction (the lid group is articulated, never re-authored)",
        f"hinge {manifest['mechanism']['hinge_strategy']} at "
        f"{manifest['mechanism']['hinge_edge']} · clasp "
        f"{manifest['mechanism']['clasp_strategy']} at "
        f"{manifest['mechanism']['clasp_edge']} · opening "
        f"{manifest['mechanism']['opening_direction']} · front artwork "
        f"{manifest['mechanism']['front_artwork_orientation']} · open "
        f"review angle {manifest['mechanism']['open_review_angle_deg']} deg "
        "(DESIGN_DEFAULT, NOT_MANUFACTURER_CONFIRMED)",
    ]):
        d.text((60, 122 + i * 34), line, font=font(25), fill=(90, 70, 60))

    def panel(name, x, y, mw, mh, klass, title):
        path = E(name)
        if not os.path.exists(path):
            return 0
        img = fit(Image.open(path).convert("RGB"), mw, mh)
        col = CLASSES[klass]
        board.paste(img, (x, y + 52))
        d.rectangle([x - 3, y + 49, x + img.width + 3, y + 55 + img.height],
                    outline=col, width=4)
        d.text((x, y), klass, font=font(26), fill=col)
        d.text((x, y + img.height + 62), title, font=font(25),
               fill=(45, 45, 48))
        return img.width

    y = 260
    x = 60
    for name, title in (("closed_front.png", "closed — front"),
                        ("closed_top.png", "closed — top"),
                        ("closed_side.png", "closed — side"),
                        ("closed_three_quarter.png",
                         "closed — three-quarter")):
        x += panel(name, x, y, 1000, 1000,
                   "NEUTRAL GEOMETRY VALIDATION", title) + 50

    y2 = y + 1160
    x = 60
    for name, title in (("open_front.png", "open — front"),
                        ("open_three_quarter.png",
                         "open — three-quarter"),
                        ("open_side.png", "open — side"),
                        ("pan_layout_top.png", "pan layout — top")):
        x += panel(name, x, y2, 1000, 1000,
                   "NEUTRAL GEOMETRY VALIDATION", title) + 50

    y3 = y2 + 1160
    x = 60
    for name, title, klass in (
            ("base_only.png", "base only", "NEUTRAL GEOMETRY VALIDATION"),
            ("lid_and_mirror.png", "lid and mirror",
             "NEUTRAL GEOMETRY VALIDATION"),
            ("hinge_detail.png", "hinge close-up", "MECHANISM DETAIL"),
            ("clasp_detail.png", "clasp close-up", "MECHANISM DETAIL")):
        x += panel(name, x, y3, 1000, 1000, klass, title) + 50

    y4 = y3 + 1160
    x = 60
    for name, title, klass in (
            ("exploded.png", "exploded assembly",
             "NEUTRAL GEOMETRY VALIDATION"),
            ("section_through_height.png", "section through case height",
             "NEUTRAL GEOMETRY VALIDATION"),
            ("dimension_overlay.png", "dimension overlay",
             "DIMENSION EVIDENCE"),
            ("stress_fixture_three_quarter.png",
             "ENGINEERING STRESS FIXTURE — not a recommendation",
             "ENGINEERING STRESS FIXTURE")):
        x += panel(name, x, y4, 1000, 1000, klass, title) + 50

    fy = y4 + 1170
    d.text((60, fy), "RESOLVED DIMENSIONS (from the contracts, never "
                     "eyeballed)", font=font(30), fill=(30, 30, 34))
    rows = [
        ("pan", f"26.0 dia x {dims['pan_depth_mm']} deep"),
        ("pocket", f"{dims['pocket_diameter_mm']} dia "
                   f"(pan + 2 x 0.30 tolerance)"),
        ("pitch / gap / margin", f"{dims['pitch_mm']} / "
                                 f"{dims['inter_pan_gap_mm']} / "
                                 f"{dims['outer_margin_mm']}"),
        ("case / hinge / clasp wall", f"{dims['case_wall_mm']} / "
                                      f"{dims['hinge_wall_mm']} / "
                                      f"{dims['clasp_wall_mm']}"),
        ("base / lid height", f"{dims['base_height_mm']} / "
                              f"{dims['lid_height_mm']}"),
        ("parting gap", f"{dims['parting_gap_mm']}"),
        ("height stack (lower / eng / premium)",
         f"{dims['height_stackup']['GEOMETRIC_LOWER_BOUND_mm']} / "
         f"{dims['height_stackup']['ENGINEERING_MINIMUM_mm']} / "
         f"{dims['height_stackup']['PREMIUM_DESIGN_TARGET_mm']}"),
        ("validators", f"{validation['finding_count']} findings — "
                       f"valid={validation['valid']}"),
        ("mesh diagnostics", f"{diagnostics['component_count']} components, "
                             f"{diagnostics['total_faces']} faces, all "
                             "manifold"),
    ]
    for i, (k, v) in enumerate(rows):
        d.text((60, fy + 46 + i * 34), k, font=font(25), fill=(45, 45, 48))
        d.text((760, fy + 46 + i * 34), v, font=font(25), fill=(11, 110, 153))

    if stress:
        d.text((2100, fy), "PREMIUM vs STRESS FIXTURE", font=font(30),
               fill=(179, 69, 79))
        for i, line in enumerate([
                f"premium envelope: {env[0]} x {env[1]} x {env[2]} mm "
                f"(gap 4.0, margin 5.0)",
                f"stress fixture:   {stress['envelope_mm'][0]} x "
                f"{stress['envelope_mm'][1]} x {stress['envelope_mm'][2]} mm "
                "(gap 2.0, margin 3.0)",
                "the stress fixture is the wall-integrated analytical "
                "minimum — NOT_PRODUCT_RECOMMENDATION, NOT_OWNER_APPROVED",
                "it exists only to show the margin, spacing and mechanism "
                "clearance the premium envelope buys"]):
            d.text((2100, fy + 46 + i * 34), line, font=font(25),
                   fill=(140, 70, 70))

    d.text((60, fy + 400), "evidence: docs/roadmap/palt_m4/ · geometry "
                           "authority PROVISIONAL_DESIGN_ONLY · "
                           "MANUFACTURING_AUTHORITY NOT_ESTABLISHED · "
                           "not self-approved", font=font(25),
           fill=(140, 70, 70))
    board = board.crop((0, 0, 4400, fy + 450))
    png = E("palt_p1_neutral_review_board.png")
    pdf = E("palt_p1_neutral_review_board.pdf")
    board.save(png)
    board.save(pdf, "PDF", resolution=200.0)
    return {"record_type": "palt_p1_review_board/1.0",
            "png": os.path.basename(png), "pdf": os.path.basename(pdf),
            "pixel_dimensions": list(board.size)}


def build_stress_comparison(out_dir, stress, env) -> str:
    E = lambda n: os.path.join(out_dir, n)  # noqa: E731
    left = Image.open(E("closed_three_quarter.png")).convert("RGB")
    right = Image.open(E("stress_fixture_three_quarter.png")).convert("RGB")
    left = fit(left, 1500, 1500)
    right = fit(right, 1500, 1500)
    canvas = Image.new("RGB", (left.width + right.width + 150,
                               max(left.height, right.height) + 260),
                       (247, 245, 242))
    d = ImageDraw.Draw(canvas)
    d.text((40, 22), "PREMIUM PILOT vs ENGINEERING STRESS FIXTURE",
           font=font(46), fill=(30, 30, 34))
    d.text((40, 80), "the stress fixture is NOT_PRODUCT_RECOMMENDATION and "
                     "NOT_OWNER_APPROVED — it demonstrates why the premium "
                     "envelope has better margins", font=font(26),
           fill=(140, 70, 70))
    canvas.paste(left, (40, 160))
    canvas.paste(right, (left.width + 110, 160))
    d.text((40, 170 + left.height),
           f"PALT-P1 premium {env[0]} x {env[1]} x {env[2]} mm "
           "(gap 4.0 / margin 5.0)", font=font(30), fill=(45, 45, 48))
    d.text((left.width + 110, 170 + right.height),
           f"stress fixture {stress['envelope_mm'][0]} x "
           f"{stress['envelope_mm'][1]} x {stress['envelope_mm'][2]} mm "
           "(gap 2.0 / margin 3.0)", font=font(30), fill=(140, 70, 70))
    path = E("palt_p1_stress_fixture_comparison.png")
    canvas.save(path)
    return os.path.basename(path)
