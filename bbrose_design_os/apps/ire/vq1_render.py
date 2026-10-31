"""VQ-1-CORR-2 — reference-faithful diagnostic renderer.

One shared weak-perspective projection contract for the whole bottle
(single ellipse depth ratio, one centerline, one scale); soft rounded
serum shoulder; true cylindrical read (curved side shading in neutral
greys); one glass neck mostly enclosed by a tall delicate collar sleeve
with shallow rims and a concealed opening; tapered pipette bulb inserted
into the collar; integrated curved base. Neutral light background —
structural judgment only, no material realism.
"""
from __future__ import annotations

from apps.ire.graph import (ClosePath, Color, CubicTo, Document, Group,
                            LineTo, MoveTo, Path, Rect, SolidFill, Stroke,
                            TextRun)
from apps.ire.nodes import centered_text, image_node, rect_clip

#: VQ-1-RESET-1 §4 — this generator is FROZEN; it produced a fixture a
#: human rejected. Rejected regression input only; never a new candidate.
GENERATOR_STATE = "LEGACY_REJECTED_STRUCTURAL_GENERATOR"
MAY_EMIT_NEW_CANDIDATE = False

_K = 0.5523
INK = Color.from_hex("#2A2426")
#: §6 shared projection contract — every ellipse uses THIS depth ratio
PROJECTION = {"mode": "weak_perspective_front", "ellipse_depth_ratio": 0.055,
              "centerline": "shared", "scale": "shared",
              "vertical_axis": "shared"}

CORR2_DIMS = {
    "body_diameter": 31.5, "body_height": 70.5, "visible_neck": 1.2,
    "neck_diameter": 9.0, "collar_diameter": 19.5, "collar_height": 12.0,
    "bulb_width": 10.5, "bulb_height": 21.0, "base_thickness": 3.5,
    "shoulder_style": "SOFT_ROUNDED_SERUM_SHOULDER", "shoulder_rise": 9.0,
    "bulb_base_ratio": 0.45, "bulb_max_at": 0.62, "bulb_insertion": 2.2,
}

#: CORR-3 — reference-contour-driven targets (collar/body 0.53, sleeve
#: h/w 0.83, bulb base 0.33/max 0.56 of collar width, minimal ellipses)
CORR3_DIMS = {
    "body_diameter": 31.5, "body_height": 70.5, "visible_neck": 0.8,
    "neck_diameter": 8.5, "collar_diameter": 16.7, "collar_height": 13.9,
    "bulb_width": 9.4, "bulb_height": 21.0, "base_thickness": 2.0,
    "shoulder_style": "SOFT_ROUNDED_SERUM_SHOULDER", "shoulder_rise": 8.0,
    "bulb_base_ratio": 0.585, "bulb_max_at": 0.58, "bulb_insertion": 2.6,
}


def draw_bottle(d, ox, oy, s, *, prefix="", silhouette_only=False):
    """The corrected fixture at (ox, oy), scale s. y-down sheet space;
    local y0 = bulb top."""
    W, cx = d["body_diameter"], d["body_diameter"] / 2.0
    er = PROJECTION["ellipse_depth_ratio"]
    bulb_h, col_h, neck_v = d["bulb_height"], d["collar_height"], \
        d["visible_neck"]
    rise = d["shoulder_rise"]
    y_col = bulb_h
    y_neck = y_col + col_h
    y_body = y_neck + neck_v          # top of shoulder rise
    H = y_body + d["body_height"]
    y_base = H - d["base_thickness"]
    bw2, nw2, cw2 = W / 2, d["neck_diameter"] / 2, d["collar_diameter"] / 2
    bwh = d["bulb_width"] / 2

    def X(x):
        return ox + x * s

    def Y(y):
        return oy + y * s

    def N(n):
        return f"{prefix}{n}"

    def ell(name, cy, rx, ry, fill, op=1.0):
        return Path(name=name, segments=[
            MoveTo(x=X(cx - rx), y=Y(cy)),
            CubicTo(x1=X(cx - rx), y1=Y(cy - ry * _K), x2=X(cx - rx * _K),
                    y2=Y(cy - ry), x=X(cx), y=Y(cy - ry)),
            CubicTo(x1=X(cx + rx * _K), y1=Y(cy - ry), x2=X(cx + rx),
                    y2=Y(cy - ry * _K), x=X(cx + rx), y=Y(cy)),
            CubicTo(x1=X(cx + rx), y1=Y(cy + ry * _K), x2=X(cx + rx * _K),
                    y2=Y(cy + ry), x=X(cx), y=Y(cy + ry)),
            CubicTo(x1=X(cx - rx * _K), y1=Y(cy + ry), x2=X(cx - rx),
                    y2=Y(cy + ry * _K), x=X(cx - rx), y=Y(cy)),
            ClosePath()], fill=SolidFill(color=fill, opacity=op))

    # body silhouette: soft rounded shoulder rising gently into the neck,
    # straight walls, integrated elliptical base (no pedestal)
    base_ry = bw2 * er * 2
    body = [
        MoveTo(x=X(cx - nw2), y=Y(y_body)),
        LineTo(x=X(cx + nw2), y=Y(y_body)),
        # soft rounded shoulder (right): one continuous outward curve
        CubicTo(x1=X(cx + nw2 + (bw2 - nw2) * 0.15), y1=Y(y_body + rise * 0.30),
                x2=X(cx + bw2), y2=Y(y_body + rise * 0.55),
                x=X(cx + bw2), y=Y(y_body + rise)),
        LineTo(x=X(cx + bw2), y=Y(y_base)),
        # integrated base: elliptical bottom continuing from the sidewall
        CubicTo(x1=X(cx + bw2), y1=Y(H + base_ry * 0.4),
                x2=X(cx + bw2 * 0.45), y2=Y(H + base_ry),
                x=X(cx), y=Y(H + base_ry)),
        CubicTo(x1=X(cx - bw2 * 0.45), y1=Y(H + base_ry),
                x2=X(cx - bw2), y2=Y(H + base_ry * 0.4),
                x=X(cx - bw2), y=Y(y_base)),
        LineTo(x=X(cx - bw2), y=Y(y_body + rise)),
        CubicTo(x1=X(cx - bw2), y1=Y(y_body + rise * 0.55),
                x2=X(cx - nw2 - (bw2 - nw2) * 0.15),
                y2=Y(y_body + rise * 0.30),
                x=X(cx - nw2), y=Y(y_body)),
        ClosePath(),
    ]
    kids = []
    if silhouette_only:
        kids.append(Path(name=N("SILHOUETTE"), segments=body,
                         stroke=Stroke(color=INK, width_mm=0.35)))
    else:
        kids += [
            Path(name=N("BODY"), segments=body,
                 fill=SolidFill(color=Color.from_hex("#E9E2DE"))),
            # cylindrical read: curved side shading, neutral grey
            Path(name=N("SIDE_SHADE_L"), segments=[
                MoveTo(x=X(cx - bw2), y=Y(y_body + rise + 1)),
                LineTo(x=X(cx - bw2), y=Y(y_base - 1)),
                CubicTo(x1=X(cx - bw2 + 3.2), y1=Y(y_base - 6),
                        x2=X(cx - bw2 + 3.2), y2=Y(y_body + rise + 7),
                        x=X(cx - bw2), y=Y(y_body + rise + 1)),
                ClosePath()],
                fill=SolidFill(color=Color.from_hex("#B9AEA9"),
                               opacity=0.5)),
            Path(name=N("SIDE_SHADE_R"), segments=[
                MoveTo(x=X(cx + bw2), y=Y(y_body + rise + 1)),
                LineTo(x=X(cx + bw2), y=Y(y_base - 1)),
                CubicTo(x1=X(cx + bw2 - 3.2), y1=Y(y_base - 6),
                        x2=X(cx + bw2 - 3.2), y2=Y(y_body + rise + 7),
                        x=X(cx + bw2), y=Y(y_body + rise + 1)),
                ClosePath()],
                fill=SolidFill(color=Color.from_hex("#A79B96"),
                               opacity=0.55)),
        ]
        # one cylindrical glass neck (mostly enclosed by the collar)
        kids.append(Rect(name=N("NECK_GLASS"), x=X(cx - nw2 + 0.3),
                         y=Y(y_neck - 0.6), w=(d["neck_diameter"] - 0.6) * s,
                         h=(neck_v + 1.6) * s,
                         fill=SolidFill(color=Color.from_hex("#DDD3CE"))))
        # collar: tall delicate sleeve, vertical walls, shallow rims
        rim_ry = cw2 * er
        kids += [
            Path(name=N("COLLAR_SLEEVE"), segments=[
                MoveTo(x=X(cx - cw2), y=Y(y_col + rim_ry)),
                CubicTo(x1=X(cx - cw2), y1=Y(y_col + rim_ry - rim_ry * _K),
                        x2=X(cx - cw2 * _K), y2=Y(y_col),
                        x=X(cx), y=Y(y_col)),
                CubicTo(x1=X(cx + cw2 * _K), y1=Y(y_col),
                        x2=X(cx + cw2), y2=Y(y_col + rim_ry - rim_ry * _K),
                        x=X(cx + cw2), y=Y(y_col + rim_ry)),
                LineTo(x=X(cx + cw2), y=Y(y_neck - rim_ry * 0.4)),
                CubicTo(x1=X(cx + cw2 * 0.5), y1=Y(y_neck + rim_ry * 0.6),
                        x2=X(cx - cw2 * 0.5), y2=Y(y_neck + rim_ry * 0.6),
                        x=X(cx - cw2), y=Y(y_neck - rim_ry * 0.4)),
                ClosePath()],
                fill=SolidFill(color=Color.from_hex("#C8B8B2"))),
            # shallow top rim; the opening is concealed by the bulb base
            ell(N("COLLAR_TOP_RIM"), y_col + rim_ry, cw2 - 0.25, rim_ry,
                Color.from_hex("#B5A29B"), 0.9),
            Path(name=N("COLLAR_SIDE_SHADE"), segments=[
                MoveTo(x=X(cx + cw2 - 1.8), y=Y(y_col + rim_ry + 0.5)),
                LineTo(x=X(cx + cw2), y=Y(y_col + rim_ry + 0.7)),
                LineTo(x=X(cx + cw2), y=Y(y_neck - 0.8)),
                LineTo(x=X(cx + cw2 - 1.8), y=Y(y_neck - 0.6)),
                ClosePath()],
                fill=SolidFill(color=Color.from_hex("#9B8880"),
                               opacity=0.6)),
        ]
        # bulb: tapered pipette, inserted into the collar (base concealed)
        base_hw = bwh * d["bulb_base_ratio"]
        ins = d["bulb_insertion"]
        max_y = bulb_h * (1 - d["bulb_max_at"])
        bulb = [
            MoveTo(x=X(cx - base_hw), y=Y(y_col + ins)),
            CubicTo(x1=X(cx - bwh * 0.9), y1=Y(bulb_h * 0.86),
                    x2=X(cx - bwh), y2=Y(max_y + bulb_h * 0.16),
                    x=X(cx - bwh), y=Y(max_y)),
            CubicTo(x1=X(cx - bwh), y1=Y(max_y * 0.45),
                    x2=X(cx - bwh * 0.48), y2=Y(0.9),
                    x=X(cx), y=Y(0.6)),
            CubicTo(x1=X(cx + bwh * 0.48), y1=Y(0.9),
                    x2=X(cx + bwh), y2=Y(max_y * 0.45),
                    x=X(cx + bwh), y=Y(max_y)),
            CubicTo(x1=X(cx + bwh), y1=Y(max_y + bulb_h * 0.16),
                    x2=X(cx + bwh * 0.9), y2=Y(bulb_h * 0.86),
                    x=X(cx + base_hw), y=Y(y_col + ins)),
            ClosePath()]
        kids.append(Path(name=N("BULB"), segments=bulb,
                         fill=SolidFill(color=Color.from_hex("#6B5A57"))))
        kids.append(Path(name=N("OUTLINE"), segments=body,
                         stroke=Stroke(color=INK, width_mm=0.22,
                                       opacity=0.45)))
    return Group(name=f"{prefix}Bottle", role="product", children=kids)


def compose_corr2_sheet(reference_path, rejected_png, out_prefix):
    kids = [centered_text("sheet-title", "VQ-1-CORR-2 — REFERENCE-FAITHFUL "
                          "STRUCTURAL DIAGNOSTIC", 105, 12, 9, INK,
                          font="bold"),
            centered_text("sheet-sub", "neutral light background · shared "
                          "weak-perspective projection (ellipse depth "
                          "0.10) · structure only", 105, 17, 4, INK)]

    def lab(t, x, y):
        kids.append(TextRun(name=f"panel-label-{t[:18]}", text=t, x=x, y=y,
                            size_pt=2.8, color=INK, font="bold",
                            align="left"))
    lab("1 · REFERENCE #97", 12, 26)
    img = image_node("reference-97", reference_path, 12, 28, 52, 76,
                     clip=rect_clip(12, 28, 52, 76))
    if img:
        kids.append(img)
    lab("2 · REJECTED VQ-1", 70, 26)
    img2 = image_node("reference-rejected-vq1", rejected_png, 70, 28, 52,
                      76, clip=rect_clip(70, 28, 52, 76))
    if img2:
        kids.append(img2)
    lab("3 · CORR-2 FIXTURE", 130, 26)
    kids.append(draw_bottle(CORR2_DIMS, 138, 30, 0.68))
    lab("4 · SILHOUETTE ONLY", 12, 112)
    kids.append(draw_bottle(CORR2_DIMS, 22, 116, 0.62, prefix="sil-",
                            silhouette_only=True))
    lab("5 · CLOSURE ×2.4 (insertion + shallow rims)", 70, 112)
    kids.append(Group(name="closure-clip", role="generic", children=[
        draw_bottle(CORR2_DIMS, 84, 116, 2.4, prefix="cu-")],
        clip=rect_clip(70, 114, 66, 74)))
    lab("6 · BULB WIDTH PROFILE (11 samples)", 145, 112)
    from apps.ire.vq1_backbone import bulb_width_samples
    y = 117
    for smp in bulb_width_samples({**CORR2_DIMS,
                                   "bulb_dome_start": 0.18,
                                   "bulb_upper_narrowing": 0.42}, n=11):
        kids.append(TextRun(name=f"ws-{smp['height_frac']}",
                            text=f"h={smp['height_frac']:.2f} "
                                 f"w={smp['width_frac']:.2f}",
                            x=145, y=y, size_pt=2.3, color=INK,
                            align="left"))
        y += 3.0
    lab("7 · SHARED CAMERA: one centerline · one ellipse ratio 0.10 · one "
        "scale", 12, 196)
    lab("8 · PERCEIVED CHECKS: shoulder soft-rounded · collar/body 0.62 · "
        "sleeve h/w 0.62 · opening concealed · base integrated", 12, 201)
    lab("9 · NEGATIVES preserved (B–H) · previous fixture 19f9b98d "
        "preserved REJECTED", 12, 206)
    doc = Document(page_w=210, page_h=297, title="VQ-1-CORR-2",
                   metadata={"target": "vq1_corr2"},
                   root=Group(name="Artwork", role="artwork",
                              children=kids))
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.rasterize import pdf_to_png
    ai = emit_pdf_ai(doc, out_prefix + ".ai")
    pdf_to_png(ai, out_prefix + ".png")
    import shutil
    shutil.copyfile(ai, out_prefix + ".pdf")
    return doc
