"""M4B-B §9/§10 — neutral review evidence for both palette families.

Both families render through ONE script with one lighting rig and one
camera set, so any difference between the two images comes from the
design and not from the setup. P1A declares Boolean CSG for its pockets;
P1B declares none because it is built Boolean-free. That is the only
configuration difference between them.

Medium-grey technical clay with contact shading. No white-on-white.

The two views that were blocked at the previous checkpoint —
``closed_top`` and ``closed_three_quarter`` — need a lid. Both families
now have one, so §9's ten-view comparison completes here.
"""
from __future__ import annotations

import hashlib
import math
import os

from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_moulded_geometry as MG
from apps.pipeline.services import palette_moulded_rect as MR
from apps.pipeline.services import palt_p1_m4b_evidence as EV

SCHEMA = "palette_m4b_b_evidence/1.0"

P1A, P1B = "P1A", "P1B"

#: §10 — the neutral review set. ``state`` names the articulation and
#: ``camera`` the built-in or detail camera.
REVIEW_VIEWS = (
    ("closed_top", "CLOSED", "top", "the closed palette from above"),
    ("closed_front", "CLOSED", "front", "the closed front elevation"),
    ("closed_side", "CLOSED", "side", "the closed side elevation"),
    ("closed_three_quarter", "CLOSED", "three_quarter",
     "the closed palette, three-quarter"),
    ("open_top", "OPEN_REVIEW_ANGLE", "top", "opened, from above"),
    ("open_front", "OPEN_REVIEW_ANGLE", "front", "opened front elevation"),
    ("open_side", "OPEN_REVIEW_ANGLE", "side",
     "opened side elevation — the lid angle reads here"),
    ("open_three_quarter", "OPEN_REVIEW_ANGLE", "three_quarter",
     "opened, three-quarter"),
    ("pan_layout", "TRAY_ONLY", "top_tray",
     "the pan field alone — lid, hinge and clasp removed"),
    ("recessed_pocket_detail", "TRAY_ONLY", "pocket_detail",
     "one pocket, its draft and the seated pan"),
    ("hinge_exterior", "CLOSED", "hinge_ext", "the hinge from outside"),
    ("hinge_interior", "OPEN_90", "hinge_int",
     "the knuckles from inside the case"),
    ("hinge_exploded", "EXPLODED", "hinge_ext", "the hinge separated"),
    ("clasp_exterior", "CLOSED", "clasp_ext", "the clasp from outside"),
    ("clasp_interior", "OPEN_90", "clasp_int",
     "the hook and detent from inside"),
    ("clasp_exploded", "EXPLODED", "clasp_ext", "the clasp separated"),
    ("lid_interior", "OPEN_REVIEW_ANGLE", "lid_int",
     "the inside of the lid"),
    ("mirror_stack_view", "OPEN_REVIEW_ANGLE", "mirror_stack_cam",
     "the mirror in its recess"),
    ("exploded_palette", "EXPLODED", "three_quarter",
     "every component separated"),
)

#: §8 supplies these three as true cuts rather than renders.
SECTION_VIEWS = ("hinge_section", "clasp_section", "true_stack_section")

#: Drawn, not rendered.
OVERLAY_VIEWS = ("dimension_overlay",)

REQUIRED = tuple(v[0] for v in REVIEW_VIEWS) + SECTION_VIEWS + OVERLAY_VIEWS


#: Components a state removes rather than moves.
HIDE = {
    "TRAY_ONLY": ("lid_", "hinge_", "clasp_", "mirror"),
}


def _families():
    ca, da = MG.build_moulded_components()
    cb, db = MR.build_rect_components(OC.confirmed_intent())
    return {
        P1A: {"components": ca, "dims": da, "compose": MG.compose_moulded_state,
              "envelope": da["envelope_mm"],
              "deck": da["deck_z_mm"],
              "hinge": (da["hinge_axis_y_mm"], da["hinge_axis_z_mm"]),
              "mirror": True, "boolean_free": False},
        P1B: {"components": cb, "dims": db, "compose": MR.compose_rect_state,
              "envelope": [db["case_width_mm"], db["case_depth_mm"],
                           db["case_height_mm"]],
              "deck": db["base_height_mm"],
              "hinge": (db["hinge_axis_y_mm"], db["hinge_axis_z_mm"]),
              "mirror": db["mirror_state"] != MR.UNRESOLVED,
              "boolean_free": True},
    }


def _detail_cameras(fam):
    """Explicit cameras for the mechanism details."""
    w, d, h = fam["envelope"]
    hy, hz = fam["hinge"]
    D = 260.0
    az, el = math.radians(38), math.radians(26)

    def three_q(centre, dist, scale):
        return {"loc": [centre[0] + dist * math.cos(el) * math.sin(az),
                        centre[1] - dist * math.cos(el) * math.cos(az),
                        centre[2] + dist * math.sin(el)],
                "rot": [math.pi / 2 - el, 0.0, az], "scale": scale}

    return {
        "top_tray": {"loc": [0.0, 0.0, h + 220.0], "rot": [0.0, 0.0, 0.0],
                     "scale": max(w, d) * 0.95},
        "pocket_detail": three_q((-w * 0.22, -d * 0.18, fam["deck"]),
                                 D, 40.0),
        "hinge_ext": three_q((0.0, hy - 6.0, hz), D, 62.0),
        "hinge_int": three_q((0.0, hy + 6.0, hz + 6.0), D, 62.0),
        "clasp_ext": three_q((0.0, d / 2.0 + 6.0, fam["deck"]), D, 62.0),
        "clasp_int": three_q((0.0, d / 2.0 - 8.0, fam["deck"]), D, 62.0),
        "lid_int": {"loc": [0.0, -d * 0.9, h * 2.4], "rot":
                    [math.radians(34), 0.0, 0.0], "scale": max(w, d) * 1.05},
        # A DISTINCT camera, not a second use of lid_int: the render dict
        # is keyed by camera, so two views sharing one camera silently
        # write a single file while the record claims both.
        "mirror_stack_cam": {"loc": [0.0, -d * 0.72, h * 2.1],
                             "rot": [math.radians(30), 0.0, 0.0],
                             "scale": max(w, d) * 0.78},
    }


#: The VIEWS placed side by side in the §9 comparison. Only these share a
#: frame across both families. Keying this by state instead put a 14 mm
#: closed elevation inside a 192 mm open-assembly frame, which renders as
#: a sliver — technically correct and useless to review.
COMPARED_VIEWS = ("closed_top", "closed_three_quarter", "open_top",
                  "open_three_quarter", "pan_layout",
                  "recessed_pocket_detail")


#: §4 — what each built-in camera actually sees. Framing an elevation by
#: the 3D max extent puts a 68.8 x 14 mm side view inside a 113.6 mm
#: frame; the projected extent is what the image contains.
CAMERA_AXES = {"front": (0, 2), "side": (1, 2), "top": (0, 1)}


def projected_scale(lo, hi, camera, *, margin=None):
    """Ortho scale from the extent the camera actually sees."""
    from apps.pipeline.services import palette_render_contract as RC
    m = RC.FRAME_MARGIN if margin is None else margin
    span = hi - lo
    axes = CAMERA_AXES.get(camera)
    if axes is None:                       # three-quarter and details
        return float(max(span)) * m
    if margin is None and camera in ("front", "side"):
        m = RC.ELEVATION_FRAME_MARGIN
    return float(max(span[axes[0]], span[axes[1]])) * m


def shared_frames() -> dict:
    """One centre and ortho scale per compared VIEW, spanning BOTH
    families, so a side-by-side pair is genuinely to the same scale."""
    import numpy as np
    fams = _families()
    states = {v[1] for v in REVIEW_VIEWS if v[0] in COMPARED_VIEWS}
    out = {}
    for state in states:
        los, his = [], []
        for fam in fams.values():
            if state in HIDE:
                comps = {n: c for n, c in fam["components"].items()
                         if not any(n.startswith(h) for h in HIDE[state])}
            else:
                comps = fam["compose"](fam["components"], fam["dims"],
                                       state)
            pts = np.concatenate([c["vertices"] for c in comps.values()])
            los.append(pts.min(axis=0))
            his.append(pts.max(axis=0))
        lo = np.min(np.array(los), axis=0)
        hi = np.max(np.array(his), axis=0)
        out[state] = {"centre": tuple(((lo + hi) / 2.0).tolist()),
                      "bounds_lo": lo.tolist(), "bounds_hi": hi.tolist(),
                      "ortho_scale": float(max(hi - lo)) * 1.18}
    return out


def render_family(name, out_dir, *, samples=40, only=None,
                  frames=None) -> dict:
    """Render the §10 set for one family."""
    fam = _families()[name]
    os.makedirs(out_dir, exist_ok=True)
    w, d, h = fam["envelope"]
    cams = _detail_cameras(fam)
    made, skipped = {}, []

    by_state: dict = {}
    for key, state, camera, means in REVIEW_VIEWS:
        if only and key not in only:
            continue
        if key == "mirror_stack_view" and not fam["mirror"]:
            skipped.append({"view": key, "why":
                            "the concept establishes no mirror, so there "
                            "is no stack to show"})
            continue
        by_state.setdefault(state, []).append((key, camera, means))

    batches = []
    for state, entries in sorted(by_state.items()):
        cmp_e = [e for e in entries if e[0] in COMPARED_VIEWS]
        oth_e = [e for e in entries if e[0] not in COMPARED_VIEWS]
        if cmp_e:
            batches.append((state, cmp_e))
        if oth_e:
            batches.append((state, oth_e))

    for state, entries in batches:
        if state in HIDE:
            # "the pan field alone" means alone. Leaving the opened lid in
            # frame puts a thin edge-on shell across the image and reads as
            # a render artefact rather than as the pan field.
            comps = {n: c for n, c in fam["components"].items()
                     if not any(n.startswith(h) for h in HIDE[state])}
        else:
            comps = fam["compose"](fam["components"], fam["dims"], state)
        # Frame the COMPOSED state, not the closed envelope. An opened lid
        # reaches far above and behind the case, so a fixed frame crops the
        # pan field out of exactly the view meant to show it.
        # a frame applies to a compared VIEW; other views in the same
        # state keep a frame fitted to what they actually show
        shared = ((frames or {}).get(state)
                  if all(k in COMPARED_VIEWS for k, _c, _m in entries)
                  else None)
        if shared:
            centre = tuple(shared["centre"])
            scale = float(shared["ortho_scale"])
        else:
            import numpy as np
            pts = np.concatenate([c["vertices"] for c in comps.values()])
            lo, hi = pts.min(axis=0), pts.max(axis=0)
            centre = tuple(((lo + hi) / 2.0).tolist())
            scale = None                 # per-camera, set below
        views = {}
        details = {}
        per_camera_scale = {}
        for key, camera, _means in entries:
            if camera in views:
                raise RuntimeError(
                    f"{name}/{state}: {camera!r} is claimed by two views; "
                    "the render dict is keyed by camera, so one file would "
                    "be written while the record claimed both")
            views[camera] = f"{key}.png"
            if camera in cams:
                details[camera] = cams[camera]
            elif scale is None:
                per_camera_scale[camera] = projected_scale(lo, hi, camera)
        if scale is not None:
            EV.render(comps, views, out_dir, centre=centre,
                      ortho_scale=scale, detail_views=details,
                      samples=samples, distance=max(520.0, scale * 4.0))
        else:
            # each built-in camera gets the scale of what it sees; detail
            # cameras carry their own scale already
            groups = {}
            for cam_name, fname in views.items():
                sc = per_camera_scale.get(
                    cam_name, projected_scale(lo, hi, cam_name))
                groups.setdefault(round(sc, 6), {})[cam_name] = fname
            for sc, grp in groups.items():
                EV.render(comps, grp, out_dir, centre=centre,
                          ortho_scale=sc,
                          detail_views={k: v for k, v in details.items()
                                        if k in grp},
                          samples=samples,
                          distance=max(520.0, sc * 4.0))
        for key, _camera, _means in entries:
            path = os.path.join(out_dir, f"{key}.png")
            if not os.path.exists(path):
                raise RuntimeError(
                    f"{name}: {key}.png was recorded but not written")
            made[key] = path

    # §10's drawn view — never rendered, so it is produced here rather
    # than being reported missing from every family.
    if not only or "dimension_overlay" in (only or ()):
        made["dimension_overlay"] = dimension_overlay(
            name, os.path.join(out_dir, "dimension_overlay.png"))

    return {"family": name, "out_dir": out_dir, "produced": sorted(made),
            "produced_count": len(made), "skipped": skipped,
            "boolean_free": fam["boolean_free"],
            "lighting": "MEDIUM_GREY_TECHNICAL_CLAY_STUDIO",
            "shared_frames": {k: v for k, v in (frames or {}).items()},
            "frame_policy":
                "the six side-by-side views share one frame across both "
                "families; detail views are framed per family because they "
                "are never placed adjacent",
            "renderer": "palette_csg_views.py (one script, both families)"}


def evidence_manifest(records, section_records) -> dict:
    produced = {r["family"]: set(r["produced"]) for r in records}
    for fam, rec in section_records.items():
        produced.setdefault(fam, set())
        for key, mapped in (("hinge_cross", "hinge_section"),
                            ("clasp_engaged", "clasp_section"),
                            ("lid_base_stack", "true_stack_section")):
            if key in rec.get("produced", []):
                produced[fam].add(mapped)
    return {
        "record_type": SCHEMA,
        "required_views": list(REQUIRED),
        "required_count": len(REQUIRED),
        "families": {
            fam: {"produced": sorted(v), "produced_count": len(v),
                  "missing": sorted(set(REQUIRED) - v)}
            for fam, v in produced.items()},
        "identical_setup": True,
        "why_identical": "both families render through palette_csg_views.py "
                         "with one lighting rig and one camera set, so a "
                         "difference between the images comes from the "
                         "design and not from the setup",
        "white_on_white": False,
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
        "identity": hashlib.sha256(
            repr(sorted((f, sorted(v)) for f, v in produced.items()))
            .encode()).hexdigest()[:16],
    }


def dimension_overlay(family, out_path) -> str:
    """§10 — the drawn dimension view.

    Every figure is labelled with its authority. The whole envelope is a
    PROVISIONAL_DESIGN_DEFAULT and none of it is approved, so a dimension
    drawing that looked like a manufacturing drawing would misrepresent
    what it is.
    """
    from PIL import Image, ImageDraw

    from apps.pipeline.services.palette_review_fonts import font

    fam = _families()[family]
    dims = fam["dims"]
    w, d, h = fam["envelope"]
    PAPER, INK, GREY = (250, 249, 246), (28, 28, 32), (110, 110, 118)
    RED, BLUE = (198, 48, 42), (38, 96, 156)
    W, H = 2200, 1500
    img = Image.new("RGB", (W, H), PAPER)
    dr = ImageDraw.Draw(img)
    s = min((W - 620) / w, (H - 700) / d)
    ox, oy = 300, 420

    dr.rectangle([ox, oy, ox + w * s, oy + d * s], outline=INK, width=5)
    if family == P1B:
        tray = dims["tray"]
        wall = MR.CONSTRUCTION["case_wall_mm"]
        for p in tray["pockets"]:
            cx, cy = p["centre_mm"]
            pw, ph = p["opening_width_mm"], p["opening_height_mm"]
            x = ox + (w / 2 + cx - pw / 2) * s
            y = oy + (d / 2 - cy - ph / 2) * s
            dr.rounded_rectangle(
                [x, y, x + pw * s, y + ph * s],
                radius=max(2, int(p["sharp_corner_radius_at_deck_mm"] * s)),
                outline=BLUE, width=3)
        rows = [("case width", w), ("case depth", d), ("case height", h),
                ("pitch x", tray["grid"]["pitch_x_mm"]),
                ("pitch y", tray["grid"]["pitch_y_mm"]),
                ("pan opening w", tray["pockets"][0]["opening_width_mm"]),
                ("pan opening h", tray["pockets"][0]["opening_height_mm"]),
                ("case wall", wall)]
    else:
        pitch = dims["pitch_mm"]
        r = dims["spec"].layout.pans[0].width.value / 2.0
        for row in range(3):
            for col in range(3):
                cx, cy = (col - 1) * pitch, (row - 1) * pitch
                x = ox + (w / 2 + cx) * s
                y = oy + (d / 2 - cy) * s
                dr.ellipse([x - r * s, y - r * s, x + r * s, y + r * s],
                           outline=BLUE, width=3)
        rows = [("case width", w), ("case depth", d), ("case height", h),
                ("pitch", pitch), ("pan diameter", 2 * r),
                ("case wall", dims["case_wall_mm"])]

    dr.line([(ox, oy - 60), (ox + w * s, oy - 60)], fill=RED, width=4)
    dr.text((ox + w * s / 2 - 70, oy - 104), f"{w:.3f} mm",
            font=font(30), fill=RED)
    dr.line([(ox - 60, oy), (ox - 60, oy + d * s)], fill=RED, width=4)
    dr.text((ox - 270, oy + d * s / 2 - 18), f"{d:.3f} mm",
            font=font(30), fill=RED)

    dr.text((80, 70), f"{family} — DIMENSION OVERLAY", font=font(46),
            fill=INK)
    dr.text((80, 130),
            "every figure is PROVISIONAL — this is not a manufacturing "
            "drawing", font=font(27), fill=RED)
    y = oy + d * s + 90
    for i, (label, value) in enumerate(rows):
        visible = family == P1B and label in ("case width", "case depth")
        tag = "FROM CONFIRMED INTENT" if visible else "PROVISIONAL DEFAULT"
        dr.text((80 + (i % 2) * 1000, y + (i // 2) * 44),
                f"{label}: {value:.4f} mm    [{tag}]",
                font=font(27), fill=INK)
    dr.text((80, H - 110),
            "PALT_P1_FINAL_DIMENSIONS: NOT_APPROVED · "
            "PALT_P1_MANUFACTURING_AUTHORITY: NOT_ESTABLISHED · "
            "PALT_P1_OWNER_APPROVAL: NOT_GRANTED", font=font(24), fill=GREY)
    dr.text((80, H - 70),
            "authority for the case footprint: the confirmed ES3083 pan "
            "field. All other figures are generic hidden construction."
            if family == P1B else
            "authority: GENERIC_RENDERING_DEFAULT throughout",
            font=font(24), fill=GREY)
    img.save(out_path)
    return out_path
