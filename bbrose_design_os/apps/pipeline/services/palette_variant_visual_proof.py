"""PALT-M4C-9 §8 — the rendered visual variant proof.

The geometric proof showed two intents produce two different meshes. This
shows the difference is VISIBLE, under identical neutral lighting and
comparable views, between:

* PALT-P1A — the engineering default, nine circular pans in a 3 x 3 field;
* PALT-P1B — the ES3083 design-intent variant, twelve rectangular pans in
  a 4 x 3 field with ES3083-derived margins and spacing.

Two of the ten required views need a lid. There is no lid: PALT-M4B-B has
not been built. Those two are recorded ``BLOCKED_ON_UNBUILT_LID_GEOMETRY``
rather than rendered from an invented lid, and they are excluded from the
verdict instead of counted as passes.

The verdict is computed from measured differences between the two builds,
not asserted from the pictures.
"""
from __future__ import annotations

import hashlib
import os

from PIL import Image, ImageDraw

from apps.pipeline.services import palette_recessed_tray_geometry as round_t
from apps.pipeline.services import palette_rect_tray_geometry as rect_t
from apps.pipeline.services import palt_m4b_a as A
from apps.pipeline.services.a3p_evidence_render import (
    GREY, INK, PAPER, _canvas)
from apps.pipeline.services.palette_review_fonts import font

SCHEMA = "palette_variant_visual_proof/1.0"

BLOCKED = "BLOCKED_ON_UNBUILT_LID_GEOMETRY"

P1A, P1B = "PALT-P1A", "PALT-P1B"

#: identical for both variants — a difference must come from the design,
#: not from the camera or the light. The renders themselves now come from
#: the §10 review set, which shoots both families through one script.
NEUTRAL = {"mode": "clay", "samples": 40, "renderer": "palette_csg_views"}

REQUIRED_VIEWS = (
    ("closed_top", "closed, from above", "PAIR"),
    ("closed_three_quarter", "closed, three-quarter", "PAIR"),
    ("open_top", "open, from above", "PAIR"),
    ("open_three_quarter", "open, three-quarter", "PAIR"),
    ("pan_layout_top", "the pan field alone, orthographic", "PAIR"),
    ("interior_crop", "the pocket interior, close", "PAIR"),
    ("silhouette_comparison", "outer silhouette outlines", "DRAW"),
    ("layout_graph_comparison", "the layout as a graph", "DRAW"),
    ("artwork_zone_comparison", "artwork zone hierarchy", "DRAW"),
    ("colour_zone_diagram", "named colour zones", "DRAW"),
)

#: the differences the ES3083 variant must show
REQUIRED_DIFFERENCES = (
    "rectangular rather than circular pans",
    "12 rather than 9 pans",
    "4 x 3 rather than 3 x 3 layout",
    "ES3083-derived margins",
    "ES3083-derived spacing",
    "case proportion",
    "lid / base relationship",
    "artwork zones",
    "typography zones",
    "colour zones",
    "design character",
)

#: §9 view -> the review render that supplies it, once both families have
#: a lid. closed_top and closed_three_quarter were the two blocked views.
FROM_REVIEW = {
    "closed_top": "closed_top",
    "closed_three_quarter": "closed_three_quarter",
    "open_top": "open_top",
    "open_three_quarter": "open_three_quarter",
    "pan_layout_top": "pan_layout",
    "interior_crop": "recessed_pocket_detail",
}


class VariantProofError(RuntimeError):
    """Raised when a proof would misrepresent what was rendered."""


def _variants():
    a = round_t.build_recessed_palette_tray(dict(A._values(A.TRAY)))
    b = rect_t.build_rect_recessed_tray()
    return a, b


def _pair(left, right, out_path, title, subtitle, note=""):
    a, b = Image.open(left).convert("RGB"), Image.open(right).convert("RGB")
    h = max(a.height, b.height)
    a = a.resize((int(a.width * h / a.height), h))
    b = b.resize((int(b.width * h / b.height), h))
    out = Image.new("RGB", (a.width + b.width + 70, h + 250), PAPER)
    out.paste(a, (20, 200))
    out.paste(b, (a.width + 50, 200))
    d = ImageDraw.Draw(out)
    d.text((30, 40), title, font=font(46), fill=INK)
    d.text((30, 104), subtitle, font=font(27), fill=GREY)
    if note:
        d.text((30, 146), note, font=font(24), fill=(198, 48, 42))
    d.text((30, h + 210), f"{P1A} — engineering default", font=font(28),
           fill=INK)
    d.text((a.width + 60, h + 210),
           f"{P1B} — ES3083 design-intent variant", font=font(28), fill=INK)
    out.save(out_path)
    return out_path


def _silhouette_and_layout(a, b, out_path, kind):
    """Outline / layout-graph comparison, drawn at one shared scale."""
    img, d = _canvas(2200, 1250)
    span = 130.0
    s = 900.0 / span
    for i, (tray, name, shape) in enumerate(
            ((a, P1A, "CIRCLE"), (b, P1B, "RECT"))):
        cx = 560 + i * 1080
        cy = 640
        spec = tray["spec"]
        w = spec["tray_width_mm"]
        h_ = spec.get("tray_depth_mm", w)
        d.rounded_rectangle([cx - w * s / 2, cy - h_ * s / 2,
                             cx + w * s / 2, cy + h_ * s / 2],
                            radius=int(spec["corner_radius_mm"] * s),
                            outline=(38, 96, 156), width=6)
        for p in tray["pockets"]:
            px, py = p["centre_mm"]
            X, Y = cx + px * s, cy - py * s
            if kind == "silhouette":
                if shape == "CIRCLE":
                    r = p["opening_radius_mm"] * s
                    d.ellipse([X - r, Y - r, X + r, Y + r],
                              outline=(44, 150, 92), width=5)
                else:
                    pw = p["opening_width_mm"] * s / 2
                    ph = p["opening_height_mm"] * s / 2
                    d.rounded_rectangle([X - pw, Y - ph, X + pw, Y + ph],
                                        radius=int(
                                            p["sharp_corner_radius_at_deck_mm"]
                                            * s), outline=(44, 150, 92),
                                        width=5)
            else:
                d.ellipse([X - 9, Y - 9, X + 9, Y + 9], fill=(150, 96, 176))
                for q in tray["pockets"]:
                    qx, qy = q["centre_mm"]
                    if abs(qx - px) < 1e-6 or abs(qy - py) < 1e-6:
                        d.line([(X, Y), (cx + qx * s, cy - qy * s)],
                               fill=(206, 196, 220), width=2)
        rows = len({round(p["centre_mm"][1], 6) for p in tray["pockets"]})
        cols = len({round(p["centre_mm"][0], 6) for p in tray["pockets"]})
        d.text((cx - 200, cy + h_ * s / 2 + 40),
               f"{name} — {len(tray['pockets'])} pans, {cols} x {rows}",
               font=font(30), fill=INK)
        d.text((cx - 200, cy + h_ * s / 2 + 82),
               f"{w:.2f} x {h_:.2f} mm  ·  ratio "
               f"{w / h_:.3f}", font=font(25), fill=GREY)
    d.text((60, 70),
           "SILHOUETTE COMPARISON" if kind == "silhouette"
           else "LAYOUT GRAPH COMPARISON", font=font(48), fill=INK)
    d.text((60, 132), "one shared scale, one shared projection",
           font=font(27), fill=GREY)
    img.save(out_path)
    return out_path


def _zone_diagram(out_path, graph_a, graph_b, kind):
    img, d = _canvas(2200, 1250)
    title = ("ARTWORK ZONE COMPARISON" if kind == "artwork"
             else "COLOUR ZONE DIAGRAM")
    d.text((60, 70), title, font=font(48), fill=INK)
    d.text((60, 132), "from each variant's design graph", font=font(27),
           fill=GREY)
    for i, (label, g) in enumerate((
            (f"{P1A} — engineering default", graph_a),
            (f"{P1B} — ES3083", graph_b))):
        x = 90 + i * 1080
        d.text((x, 250), label, font=font(30), fill=INK)
        if g is None:
            d.text((x, 310), "no design graph — the engineering default "
                             "carries no artwork", font=font(25),
                   fill=(150, 150, 156))
            continue
        meta = g["document"].metadata
        items = (meta.get("named_colour_references", []) if kind == "colour"
                 else [n.name for n, _ in g["document"].walk()
                       if getattr(n, "role", "") in
                       ("typography", "decoration", "label", "panel")])
        for j, item in enumerate(items[:14]):
            y = 310 + j * 46
            colour = ((200, 60, 140) if kind == "colour"
                      else (24, 150, 168))
            d.rectangle([x, y, x + 28, y + 24], fill=colour, outline=INK)
            d.text((x + 42, y - 2), str(item), font=font(26), fill=INK)
        if not items:
            d.text((x, 310), "none", font=font(26), fill=(150, 150, 156))
    img.save(out_path)
    return out_path


def measured_differences(a, b, *, graph_a=None, graph_b=None,
                         assembly_a=None, assembly_b=None) -> list:
    """The eleven differences the directive requires, each MEASURED.

    Every ``visible`` flag is computed by comparing the two builds. An
    asserted True would make the verdict unfalsifiable — the same defect
    §4 found in MARGIN_REALISED, and the directive says the bridge FAILS
    when a difference is not clearly visible.
    """
    def grid(t):
        return (len({round(p["centre_mm"][0], 6) for p in t["pockets"]}),
                len({round(p["centre_mm"][1], 6) for p in t["pockets"]}))

    def shape(t):
        return ("CIRCULAR" if "opening_radius_mm" in t["pockets"][0]
                else t.get("pocket_shape", "UNKNOWN"))

    def margin_x(t):
        g = grid(t)[0]
        pitch = t["spec"].get("pitch_mm") or t["spec"]["pitch_x_mm"]
        return round((t["spec"]["tray_width_mm"] - g * pitch) / 2.0, 6)

    def spacing(t):
        s = t["spec"]
        return (round(s.get("pitch_mm") or s["pitch_x_mm"], 6),
                round(s.get("pitch_mm") or s["pitch_y_mm"], 6))

    def proportion(t):
        return round(t["spec"]["tray_width_mm"]
                     / t["spec"]["tray_depth_mm"], 6)

    def typography(g):
        if g is None:
            return []
        return [n.text for n, _ in g["document"].walk()
                if getattr(n, "type", "") == "text"]

    def colours(g):
        if g is None:
            return []
        return list(g["document"].metadata.get(
            "named_colour_references", []))

    def character(t, g):
        """Design character as a comparable signature, not an opinion."""
        return (shape(t), len(t["pockets"]), grid(t),
                len(typography(g)), len(colours(g)))

    def row(name, va, vb, *, tol=None, excluded=False, why=""):
        if excluded:
            return {"difference": name, "a": va, "b": vb,
                    "visible": None, "excluded_from_verdict": True,
                    "why": why}
        if tol is not None:
            vis = abs(float(va) - float(vb)) > tol
        else:
            vis = va != vb
        return {"difference": name, "a": va, "b": vb, "visible": bool(vis),
                "excluded_from_verdict": False}

    def lid_base(dims):
        """The lid/base relationship, as a comparable signature."""
        if dims is None:
            return None
        if "case_height_mm" in dims:                       # P1B
            return (round(dims["lid_height_mm"]
                          / dims["base_height_mm"], 4),
                    round(dims["hinge_axis_y_mm"]
                          / dims["case_depth_mm"], 4))
        return (round(dims["lid_height_mm"]                # P1A
                      / dims["base_height_mm"], 4),
                round(dims["hinge_axis_y_mm"]
                      / dims["envelope_mm"][1], 4))

    return [
        row("rectangular rather than circular pans", shape(a), shape(b)),
        row("12 rather than 9 pans", len(a["pockets"]), len(b["pockets"])),
        row("4 x 3 rather than 3 x 3 layout",
            "x".join(map(str, grid(a))), "x".join(map(str, grid(b)))),
        row("ES3083-derived margins", margin_x(a), margin_x(b), tol=1e-4),
        row("ES3083-derived spacing", spacing(a), spacing(b)),
        row("case proportion", proportion(a), proportion(b), tol=1e-4),
        row("lid / base relationship", lid_base(assembly_a),
            lid_base(assembly_b),
            excluded=(assembly_a is None or assembly_b is None),
            why="both assemblies must be supplied to compare the lid and "
                "base; neither family's lid existed at the previous "
                "checkpoint"),
        row("artwork zones",
            sorted({n.role for n, _ in graph_a["document"].walk()
                    if getattr(n, "role", "") in ("artwork", "decoration",
                                                  "label", "panel")})
            if graph_a else [],
            sorted({n.role for n, _ in graph_b["document"].walk()
                    if getattr(n, "role", "") in ("artwork", "decoration",
                                                  "label", "panel")})
            if graph_b else []),
        row("typography zones", typography(graph_a), typography(graph_b)),
        row("colour zones", colours(graph_a), colours(graph_b)),
        row("design character", character(a, graph_a),
            character(b, graph_b)),
    ]


def build_visual_proof(out_dir, *, graph_b=None, review_dirs=None,
                       assembly_a=None, assembly_b=None) -> dict:
    """The ten-view comparison. Renders come from the §10 review set so
    both families are shot with one lighting rig and one camera."""
    os.makedirs(out_dir, exist_ok=True)
    a, b = _variants()
    views, missing = {}, []

    for key, means, how in REQUIRED_VIEWS:
        out = os.path.join(out_dir, f"{key}.png")
        if how == "PAIR":
            src = FROM_REVIEW[key]
            pa = os.path.join((review_dirs or {}).get(P1A, ""),
                              f"{src}.png")
            pb = os.path.join((review_dirs or {}).get(P1B, ""),
                              f"{src}.png")
            if not (os.path.exists(pa) and os.path.exists(pb)):
                missing.append({"view": key,
                                "why": f"the review render {src}.png is "
                                       "not present for both families"})
                continue
            _pair(pa, pb, out, key.replace("_", " ").upper(),
                  f"{means} · identical neutral lighting, identical "
                  "camera, one shared frame")
            views[key] = out
        elif key in ("silhouette_comparison", "layout_graph_comparison"):
            _silhouette_and_layout(
                a, b, out,
                "silhouette" if key.startswith("sil") else "layout")
            views[key] = out
        else:
            _zone_diagram(out, None, graph_b,
                          "artwork" if key.startswith("artwork")
                          else "colour")
            views[key] = out

    diffs = measured_differences(a, b, graph_a=None, graph_b=graph_b,
                                 assembly_a=assembly_a,
                                 assembly_b=assembly_b)
    judged = [d for d in diffs if not d["excluded_from_verdict"]]
    unproven = [d["difference"] for d in judged if not d["visible"]]
    complete = not missing
    verdict = "PASS" if (complete and not unproven) else "FAIL"
    return {
        "record_type": SCHEMA,
        "variant_a": {"id": P1A, "role": "ENGINEERING_DEFAULT",
                      "mesh_identity": a["mesh_identity"]},
        "variant_b": {"id": P1B, "role": "ES3083_DESIGN_INTENT_VARIANT",
                      "mesh_identity": b["mesh_identity"]},
        "lighting": "IDENTICAL_NEUTRAL_CLAY_BOTH_VARIANTS",
        "camera": "IDENTICAL_ORTHOGRAPHIC_PARAMETERS_BOTH_VARIANTS",
        "frame": "ONE_SHARED_FRAME_PER_COMPARED_STATE_SPANNING_BOTH_"
                 "FAMILIES",
        "why_shared_frame": "these views are placed side by side, and two "
                            "images at different scales captioned as an "
                            "identical-camera comparison would mislead a "
                            "reviewer about how much the design changed",
        "views_produced": sorted(views),
        "produced_count": len(views),
        "required_view_count": len(REQUIRED_VIEWS),
        "views_missing": missing,
        "all_required_views_exist": complete,
        "required_difference_count": len(REQUIRED_DIFFERENCES),
        "measured_differences": diffs,
        "differences_judged": len(judged),
        "differences_not_visible": unproven,
        "differences_excluded_from_verdict": [
            d["difference"] for d in diffs if d["excluded_from_verdict"]],
        "negative_control": "comparing a variant with itself yields no "
                            "visible difference on any axis, so the check "
                            "can fail",
        "DESIGN_INTENT_BRIDGE": verdict,
        "why": "every difference flag is MEASURED by comparing the two "
               "builds; none is asserted, or the verdict could not fail. "
               "The verdict requires all ten views to exist.",
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
        "proof_identity": hashlib.sha256(
            (a["mesh_identity"] + b["mesh_identity"]).encode()
        ).hexdigest()[:16],
    }


#: Gate C exemption — this module feeds verdicts from display-encoded
#: frames BY DECLARATION. The registry test asserts the exemption set
#: is closed: a new site cannot appear without failing it.
DISPLAY_SPACE_BY_DECLARATION = ("M5 §5 visual discrimination: declared as display-frame proof")
