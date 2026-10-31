"""P1 owner visual review board — one high-resolution decision surface.

Combines the owner photographs (unstretched: uniform scaling and 90-degree
rotations only), the neutral geometry-validation renders, the corrected
material preview, reference-vs-render comparisons, the dimension
reconciliation table and the assumptions legend, with every panel labelled
by evidence class:

OWNER PHOTOGRAPH / NEUTRAL GEOMETRY VALIDATION / MATERIAL PREVIEW /
INFERRED GEOMETRY / OMITTED DETAILS

The photographs are perspective and uncalibrated - the board never claims
calibrated overlay accuracy.
"""
from __future__ import annotations

import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from apps.pipeline.services import concept_analysis as ca
from apps.pipeline.services import p1_pilot_geometry as p1

BOARD_W = 4400
MARGIN = 60
CLASS_COLOURS = {
    "OWNER PHOTOGRAPH": (24, 60, 130),
    "NEUTRAL GEOMETRY VALIDATION": (90, 90, 92),
    "MATERIAL PREVIEW": (196, 116, 15),
    "COMPARISON": (11, 110, 153),
}
_FONT = "/System/Library/Fonts/Helvetica.ttc"


def _font(size):
    try:
        return ImageFont.truetype(_FONT, size)
    except OSError:                               # pragma: no cover
        return ImageFont.load_default()


def _fit(img, max_w, max_h):
    """Uniform scale only - aspect ratio is never distorted."""
    s = min(max_w / img.width, max_h / img.height)
    return img.resize((max(1, int(img.width * s)),
                       max(1, int(img.height * s))), Image.LANCZOS), s


def _panel(board, draw, img, x, y, max_w, max_h, title, klass, note=None):
    img, scale = _fit(img, max_w, max_h)
    colour = CLASS_COLOURS[klass]
    board.paste(img, (x, y + 64))
    draw.rectangle([x - 3, y + 61, x + img.width + 3,
                    y + 64 + img.height + 3], outline=colour, width=5)
    draw.text((x, y), f"{klass}", font=_font(34), fill=colour)
    draw.text((x, y + img.height + 74), title, font=_font(30),
              fill=(45, 45, 48))
    if note:
        draw.text((x, y + img.height + 112), note, font=_font(24),
                  fill=(110, 90, 80))
    return img.width, img.height + 64 + 90


def _silhouette_image(render_path):
    mask, _, _, _ = ca.extract_mask(Image.open(render_path))
    arr = np.full(mask.shape, 255, dtype=np.uint8)
    arr[mask] = 30
    return Image.fromarray(arr).convert("RGB")


def build_v1_v2_comparison(v1_dir: str, v2_dir: str, out_png: str) -> None:
    """V1-vs-V2 front silhouettes + aligned overlay. Both come from the
    SAME pinned camera/scale, so overlaying RENDERS is legitimate — no
    photograph participates here."""
    s1, _, _, _ = ca.extract_mask(Image.open(os.path.join(v1_dir,
                                                          "front.png")))
    s2, _, _, _ = ca.extract_mask(Image.open(os.path.join(v2_dir,
                                                          "front.png")))
    h, w = s1.shape
    overlay = np.full((h, w, 3), 255, dtype=np.uint8)
    overlay[s1 & ~s2] = (200, 60, 60)        # V1 only
    overlay[s2 & ~s1] = (40, 90, 200)        # V2 only
    overlay[s1 & s2] = (70, 70, 75)          # agreement

    def _sil(mask):
        arr = np.full((h, w), 255, dtype=np.uint8)
        arr[mask] = 30
        return Image.fromarray(arr).convert("RGB")

    gap = 40
    canvas = Image.new("RGB", (w * 3 + gap * 2, h + 170), (247, 245, 242))
    canvas.paste(_sil(s1), (0, 150))
    canvas.paste(_sil(s2), (w + gap, 150))
    canvas.paste(Image.fromarray(overlay), (2 * (w + gap), 150))
    d = ImageDraw.Draw(canvas)
    d.text((20, 16), "P1 V1 vs V2 FRONT SILHOUETTES - same pinned camera, "
                     "aligned by construction (renders only, no "
                     "photograph)", font=_font(44), fill=(30, 30, 34))
    d.text((20, 76), "left: V1 (owner-rejected profiles)   middle: V2 "
                     "(revision)   right: overlay - red=V1 only, blue=V2 "
                     "only, dark=agreement", font=_font(36),
           fill=(90, 70, 60))
    canvas.save(out_png)


def build_photo_vs_v2(photo_crop: Image.Image, v2_dir: str,
                      out_png: str) -> None:
    """Owner-photo vs V2 qualitative comparison (uncalibrated)."""
    front = Image.open(os.path.join(v2_dir, "front.png")).convert("RGB")
    material = Image.open(os.path.join(
        v2_dir, "material_reference_preview.png")).convert("RGB")
    target_h = 1500
    panels = [_fit(img, 10_000, target_h)[0]
              for img in (photo_crop, material, front)]
    gap = 50
    total_w = sum(p.width for p in panels) + gap * 2
    canvas = Image.new("RGB", (total_w, target_h + 220), (247, 245, 242))
    x = 0
    labels = ["OWNER PHOTOGRAPH IMG_3120 (crop, lossless rotation)",
              "V2 MATERIAL PREVIEW (owner-confirmed materials)",
              "V2 NEUTRAL FRONT RENDER"]
    d = ImageDraw.Draw(canvas)
    for panel, label in zip(panels, labels):
        canvas.paste(panel, (x, 160))
        d.text((x + 8, 110), label, font=_font(32), fill=(45, 45, 48))
        x += panel.width + gap
    d.text((20, 16), "P1 OWNER PHOTO vs V2 - QUALITATIVE ONLY: the "
                     "photograph is perspective and uncalibrated; NO "
                     "accurate overlay is claimed", font=_font(44),
           fill=(140, 70, 70))
    canvas.save(out_png)


def build_owner_review_board(evidence_dir: str, intake_originals: str,
                             out_dir: str | None = None,
                             revision_banner: str | None = None) -> dict:
    out_dir = out_dir or evidence_dir
    E = lambda name: os.path.join(evidence_dir, name)  # noqa: E731
    P = lambda name: os.path.join(                     # noqa: E731
        intake_originals, "measurments",
        "P1 — Dropper serum bottle", name)

    # owner photographs: whole-region crops + a LOSSLESS 90-degree rotation
    # for upright display (rotation is not distortion; originals untouched)
    photo_front = Image.open(P("IMG_3120.jpg")).convert("RGB") \
        .crop((450, 950, 2400, 3024)) \
        .transpose(Image.Transpose.ROTATE_270)
    photo_parts = Image.open(P("IMG_3123.jpg")).convert("RGB") \
        .crop((500, 1000, 3950, 2200))

    front = Image.open(E("front.png")).convert("RGB")
    side = Image.open(E("side.png")).convert("RGB")
    top = Image.open(E("top.png")).convert("RGB")
    tq = Image.open(E("three_quarter_diagnostic.png")).convert("RGB")
    closure = Image.open(E("closure_detail.png")).convert("RGB")
    neck = Image.open(E("neck_detail.png")).convert("RGB")
    material = Image.open(E("material_reference_preview.png")).convert("RGB")
    silhouette = _silhouette_image(E("front.png"))

    board = Image.new("RGB", (BOARD_W, 8600), (247, 245, 242))
    draw = ImageDraw.Draw(board)

    # header
    draw.text((MARGIN, 40), "P1 DROPPER SERUM BOTTLE - OWNER VISUAL REVIEW "
                            "BOARD", font=_font(64), fill=(30, 30, 34))
    for i, line in enumerate([
        "PROVISIONAL_BEST_EFFORT_GEOMETRY_PILOT | geometry authority: "
        "PROVISIONAL_OWNER_MEASURED_PLUS_INFERRED | manufacturing "
        "authority: NOT_ESTABLISHED",
        "owner approval: PENDING_VISUAL_REVIEW | GATE_2: BLOCKED | "
        "photographs are perspective + uncalibrated - NO calibrated "
        "overlay accuracy is claimed",
        "photographs are never stretched: uniform scaling and whole-image "
        "crops only | THREAD_GEOMETRY_NOT_MODELLED | "
        "NOT_MANUFACTURING_AUTHORITATIVE",
    ]):
        draw.text((MARGIN, 130 + i * 40), line, font=_font(28),
                  fill=(90, 70, 60))
    if revision_banner:
        draw.text((MARGIN, 250), revision_banner, font=_font(30),
                  fill=(140, 70, 70))

    y0 = 320
    # row 1: owner photographs + material preview
    _panel(board, draw, photo_front, MARGIN, y0, 1000, 1450,
           "IMG_3120 - assembled product (crop of untouched original)",
           "OWNER PHOTOGRAPH")
    _panel(board, draw, material, 1180, y0, 1000, 1450,
           "corrected material preview (owner-corrected facts 2026-08-04)",
           "MATERIAL PREVIEW",
           note="bottle GLASS/MATTE/TRANSLUCENT ORANGE | collar+bulb "
                "PLASTIC/GLOSSY/ORANGE (bulb OPAQUE)")
    _panel(board, draw, tq, 2300, y0, 1000, 1450,
           "three-quarter neutral render", "NEUTRAL GEOMETRY VALIDATION")
    _panel(board, draw, photo_parts, 3420, y0, 920, 700,
           "IMG_3123 - dropper assembly (crop)", "OWNER PHOTOGRAPH",
           note="pipette is hidden interior - excluded from renders (S5)")
    # dimension table under IMG_3123
    ty = y0 + 900
    draw.text((3420, ty), "DIMENSION RECONCILIATION", font=_font(34),
              fill=(30, 30, 34))
    rows = [
        ("field", "owner", "model/render"),
        ("assembled height", "114.3", "114.28 (-0.02%)"),
        ("body diameter", "37.4", "37.42 (+0.05%)"),
        ("bottle height", "91.6", "91.6 exact"),
        ("collar dia x h", "21.4 x 16.5", "exact, z 78.6-95.1"),
        ("bulb dia x h", "10.57 x 19.2", "exact, top 114.3"),
        ("neck dia", "15.6", "15.6 (thread 17.4 omitted)"),
        ("wall end / shldr", "66 / 69", "A1 / A2 r=14.93"),
        ("neck base", "-", "73.49 = 91.6-18.11"),
        ("pipette (math)", "88.74 x 6.9", "tip 9.16, top 97.9"),
    ]
    for i, (a, b, c) in enumerate(rows):
        f = _font(26 if i else 28)
        yy = ty + 50 + i * 40
        draw.text((3420, yy), a, font=f, fill=(45, 45, 48))
        draw.text((3860, yy), b, font=f, fill=(24, 60, 130))
        draw.text((4060, yy), c, font=f, fill=(11, 110, 153))

    # row 2: neutral orthos
    y1 = y0 + 1720
    x = MARGIN
    for img, title in ((front, "front orthographic"),
                       (side, "side orthographic"),
                       (top, "top orthographic"),
                       (closure, "closure detail"),
                       (neck, "neck detail (thread statement inside)")):
        w, _h = _panel(board, draw, img, x, y1, 800, 1150, title,
                       "NEUTRAL GEOMETRY VALIDATION")
        x += w + 60

    # row 3: comparisons
    y2 = y1 + 1420
    _panel(board, draw, photo_front, MARGIN, y2, 900, 1300,
           "front reference (photo crop)", "COMPARISON",
           note="perspective, uncalibrated - visual juxtaposition only")
    _panel(board, draw, front, 1060, y2, 900, 1300,
           "front render (same scale policy: fit-to-panel only)",
           "COMPARISON")
    _panel(board, draw, silhouette, 2060, y2, 900, 1300,
           "render silhouette (front)", "COMPARISON",
           note="silhouette from the RENDER only - photo silhouette not "
                "extracted (cluttered uncalibrated background)")
    # legend: inferred + omitted
    lx = 3060
    draw.text((lx, y2), "INFERRED GEOMETRY", font=_font(36),
              fill=(196, 116, 15))
    inferred = [
        "shoulder: V2 C2 smootherstep + fullness bias (VISUAL_ESTIMATE,",
        "  MEDIUM; V1 cosine model owner-rejected)",
        "bulb: V2 rounded capsule, TRUE hemispherical dome (VISUAL_",
        "  ESTIMATE, MEDIUM; V1 conical cap owner-rejected)",
        "neck finish: GL18/DIN 168 class (ONLINE_ANALOGOUS_REFERENCE,",
        "  MEDIUM, NOT_EXACT_MATCH); pitch 3.0 from the DIN table",
        "base bottom radius 2.5 + weighted settle; collar edge round 0.8;",
        "  bottom glass 3.0 (GENERIC_RENDERING_DEFAULT, LOW)",
    ]
    for i, line in enumerate(inferred):
        draw.text((lx, y2 + 60 + i * 42), line, font=_font(28),
                  fill=(120, 90, 40))
    draw.text((lx, y2 + 360), "OMITTED DETAILS", font=_font(36),
              fill=(179, 69, 79))
    omitted = [
        "GL18-class thread geometry (S1) - statement stamped on views",
        "collar knurling/ribs (S2); base embossing 50ml/46/dots (S3)",
        "label artwork (S4, deferred); pipette in renders (S5, interior)",
    ]
    for i, line in enumerate(omitted):
        draw.text((lx, y2 + 420 + i * 42), line, font=_font(28),
                  fill=(140, 70, 70))
    draw.text((lx, y2 + 600), "ASSUMPTIONS AWAITING OWNER ANSWERS",
              font=_font(36), fill=(24, 60, 130))
    for i, line in enumerate([
            "A1: 66 = straight-wall end?   A2: 69 = point on shoulder",
            "curve (model r=14.93)?   A3: 18.11 neck landmark?",
            "A4: 105 = bulb top to pipette tip?"]):
        draw.text((lx, y2 + 660 + i * 42), line, font=_font(28),
                  fill=(50, 70, 110))

    # optional revision-comparison row (present in V2+ evidence dirs)
    fy = y2 + 1560
    comp_a = os.path.join(evidence_dir, "v1_v2_silhouette_comparison.png")
    comp_b = os.path.join(evidence_dir, "owner_photo_vs_v2.png")
    if os.path.exists(comp_a) or os.path.exists(comp_b):
        y3 = fy
        x = MARGIN
        if os.path.exists(comp_a):
            w, _h = _panel(board, draw,
                           Image.open(comp_a).convert("RGB"), x, y3,
                           2450, 1200, "V1 vs V2 silhouettes (renders, "
                           "aligned by construction)", "COMPARISON")
            x += w + 80
        if os.path.exists(comp_b):
            _panel(board, draw, Image.open(comp_b).convert("RGB"), x, y3,
                   4400 - x - MARGIN, 1200,
                   "owner photo vs V2 (qualitative, uncalibrated)",
                   "COMPARISON")
        fy = y3 + 1420

    # footer
    draw.text((MARGIN, fy), "evidence: docs/visual_quality/rbv/p1_pilot/"
                            "2026-08-04 | contract p1_provisional_geometry/"
                            "1.0 | meshes e7b0236deb66715e / "
                            "7175cb33d5cd7375 / 491a134981dd9506",
              font=_font(26), fill=(90, 90, 92))
    draw.text((MARGIN, fy + 40), "visual review + pipeline validation only "
                                 "- NEVER supplier/manufacturing geometry",
              font=_font(26), fill=(140, 70, 70))

    board = board.crop((0, 0, BOARD_W, fy + 110))
    png_path = os.path.join(out_dir, "owner_review_board.png")
    pdf_path = os.path.join(out_dir, "owner_review_board.pdf")
    board.save(png_path)
    board.save(pdf_path, "PDF", resolution=200.0)

    manifest = {
        "record_type": "p1_owner_review_board_manifest/1.0",
        "created_at": "2026-08-04",
        "board": {"png": "owner_review_board.png",
                  "pdf": "owner_review_board.pdf",
                  "pixel_dimensions": list(board.size)},
        "evidence_classes": ["OWNER PHOTOGRAPH",
                             "NEUTRAL GEOMETRY VALIDATION",
                             "MATERIAL PREVIEW", "COMPARISON",
                             "INFERRED GEOMETRY (legend)",
                             "OMITTED DETAILS (legend)"],
        "photo_treatment": "whole-region crops + uniform LANCZOS scaling; "
                           "IMG_3120 crop rotated 90 degrees clockwise "
                           "(lossless) for upright display - never "
                           "stretched, never distorted; originals "
                           "untouched",
        "calibration_statement": "photographs are perspective and "
                                 "uncalibrated - the board claims NO "
                                 "calibrated overlay accuracy",
        "materials": p1.MATERIALS,
        "accuracy_status": p1.build_p1_contract()["accuracy_status"],
        "sources": {
            "owner_photographs": ["IMG_3120.jpg (crop 450,950-2400,3024)",
                                  "IMG_3123.jpg (crop 500,1000-3950,2200)"],
            "renders": ["front.png", "side.png", "top.png",
                        "three_quarter_diagnostic.png",
                        "closure_detail.png", "neck_detail.png",
                        "material_reference_preview.png"],
        },
    }
    json.dump(manifest, open(os.path.join(
        out_dir, "owner_review_board_manifest.json"), "w"), indent=1)
    return manifest
