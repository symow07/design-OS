"""M4B-B §8 — true technical sections of the palette assembly.

These are actual plane cuts computed from the meshes, not renders with a
clipping plane. A clipped render shows an open shell and reads as solid;
a real section closes the material boundary, so a thin wall, a missing
engagement or a collision is visible as geometry rather than as shading.

Every loop drawn here comes from ``palette_mesh_section``, which joins
segments combinatorially with no join tolerance and refuses an open or
ambiguous section rather than closing it silently.
"""
from __future__ import annotations

import hashlib

from PIL import Image, ImageDraw

from apps.pipeline.services import palette_mesh_section as MS
from apps.pipeline.services.palette_review_fonts import font

SCHEMA = "palette_technical_sections/1.0"

PAPER = (250, 249, 246)
INK = (28, 28, 32)
GREY = (110, 110, 118)
RED = (198, 48, 42)

#: A technical colour per component class, so a section reads as parts.
KEY = {
    "base": (108, 122, 140),
    "tray": (150, 166, 186),
    "lid": (128, 140, 158),
    "pan": (38, 96, 156),
    "powder": (120, 74, 52),
    "hinge": (150, 96, 176),
    "clasp": (214, 152, 38),
    "mirror": (96, 186, 200),
    "other": (170, 170, 178),
}


def _class_of(name):
    for key in ("mirror", "powder", "clasp", "hinge", "tray", "lid",
                "base"):
        if key in name:
            return key
    if name.startswith("metal_pan"):
        return "pan"
    return "other"


#: The eleven sections the directive names.
#: Which components a feature section frames.
FOCUS = {
    "hinge_axial": ("hinge_",), "hinge_cross": ("hinge_",),
    "clasp_engaged": ("clasp_",), "clasp_disengaged": ("clasp_",),
    "pocket_and_pan": ("metal_pan_", "powder_"),
    # ordered fallback: P1B has a structural rim, P1A does not. Trying
    # the more specific frame first keeps P1B's detail without dropping a
    # required section from P1A.
    "parting_seam": ("lid_structural_rim", "lid_outer_shell"),
    "mirror_stack": ("mirror",),
    "outer_wall": ("base_outer_shell",),
}

SECTIONS = (
    ("pan_row", "y", "PAN ROW",
     "through one row of pans — pocket, metal pan, powder, deck land"),
    ("pan_column", "x", "PAN COLUMN",
     "through one column of pans"),
    ("lid_base_stack", "y", "LID / BASE STACK",
     "the closed stack: base floor, tray, pan, powder, clearance, lid"),
    ("mirror_stack", "y", "MIRROR STACK",
     "lid roof, backing, adhesive, mirror, retaining border"),
    ("hinge_axial", "y", "HINGE — AXIAL",
     "along the hinge axis: alternating knuckles and the pin"),
    ("hinge_cross", "x", "HINGE — CROSS SECTION",
     "across the barrel: knuckle wall, pin, running clearance"),
    ("clasp_engaged", "x", "CLASP — ENGAGED",
     "hook lip behind the detent, closed"),
    ("clasp_disengaged", "x", "CLASP — DISENGAGED",
     "the same section with the lid open"),
    ("pocket_and_pan", "x", "POCKET AND METAL PAN",
     "drafted pocket wall, seating datum, pan wall and floor"),
    ("outer_wall", "x", "OUTER WALL",
     "case wall, draft and the tray beside it"),
    ("parting_seam", "x", "PARTING SEAM",
     "where the lid rim meets the base wall"),
)


class SectionError(RuntimeError):
    """Raised when a section cannot be computed exactly."""


def section_assembly(components, axis, at) -> dict:
    """Cut every component that meets the plane. Components that miss it
    are absent, not empty — an empty loop set would draw as nothing and
    read as 'no material there'."""
    out, skipped = {}, []
    for name, comp in sorted(components.items()):
        v = comp["vertices"]
        idx = {"x": 0, "y": 1, "z": 2}[axis]
        if not (v[:, idx].min() - 1e-9 <= at <= v[:, idx].max() + 1e-9):
            skipped.append(name)
            continue
        try:
            sec = MS.section_component(name, comp["vertices"],
                                       comp["faces"], axis, at)
            joined = MS.join_loops(sec)
        except MS.SectionError as exc:
            raise SectionError(f"{name} at {axis}={at}: {exc}") from exc
        if joined["loops"]:
            out[name] = joined
    return {"axis": axis, "at": at, "components": out,
            "not_on_plane": skipped}


HEAD_PX, FOOT_PX, PAD_PX = 190, 300, 160
MAX_H_PX = 1500


def draw_section(cut, out_path, title, subtitle, *, note="", w=2400,
                 h=None, focus=(), focus_margin_mm=3.0):
    """One section at uniform scale with a component key.

    The canvas follows the content: a palette section is wide and thin, so
    a fixed tall canvas would render it as a hairline in a field of white
    — technically a true section and useless to review.
    """
    pts = [p for j in cut["components"].values()
           for lp in j["loops"] for p in lp["points_2d"]]
    if not pts:
        raise SectionError(
            f"section {cut['axis']}={cut['at']} produced no material; the "
            "image would be blank and would read as 'nothing is there'")
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if focus:
        # A whole-case cut renders a hinge barrel as a few pixels. §4 and
        # §5 require the mechanism to be understandable, so a feature
        # section frames the feature and lets the rest run off the page.
        fpts = []
        for prefix in focus:                 # ordered: first match wins
            fpts = [p for n, j in cut["components"].items()
                    if n.startswith(prefix)
                    for lp in j["loops"] for p in lp["points_2d"]]
            if fpts:
                break
        if not fpts:
            raise SectionError(
                f"section is focused on {list(focus)} but none of those "
                f"components meet the plane {cut['axis']}={cut['at']}")
        m = focus_margin_mm
        xs = [min(q[0] for q in fpts) - m, max(q[0] for q in fpts) + m]
        ys = [min(q[1] for q in fpts) - m, max(q[1] for q in fpts) + m]
    span_x = max(1e-6, max(xs) - min(xs))
    span_y = max(1e-6, max(ys) - min(ys))
    # fit width, but never let a tall narrow detail run the canvas off the
    # page — the footer would end up drawn over the geometry
    s = min((w - 2 * PAD_PX) / span_x,
            (MAX_H_PX - HEAD_PX - FOOT_PX) / span_y)
    if h is None:
        h = int(HEAD_PX + span_y * s + FOOT_PX)
    img = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(img)
    ox = (w - span_x * s) / 2.0 - min(xs) * s
    oy = h - FOOT_PX + min(ys) * s

    order = sorted(cut["components"],
                   key=lambda n: (_class_of(n) in ("pan", "powder",
                                                   "mirror"),))
    used = []
    for name in order:
        cls = _class_of(name)
        used.append(cls)
        for lp in cut["components"][name]["loops"]:
            poly = [(ox + p[0] * s, oy - p[1] * s) for p in lp["points_2d"]]
            if len(poly) >= 3:
                d.polygon(poly, fill=KEY[cls], outline=INK)

    d.text((70, 70), title, font=font(46), fill=INK)
    d.text((70, 130), subtitle, font=font(27), fill=GREY)
    d.text((70, h - 240),
           f"true plane cut · {cut['axis']} = {cut['at']:.4f} mm · "
           f"{len(cut['components'])} component(s) on the plane · "
           f"uniform scale · {'FEATURE DETAIL' if focus else 'FULL SECTION'}",
           font=font(25), fill=GREY)
    if note:
        d.text((70, h - 200), note, font=font(26), fill=RED)
    for i, cls in enumerate(sorted(set(used))):
        x = 70 + (i % 5) * 300
        y = h - 150 + (i // 5) * 36
        d.rectangle([x, y, x + 26, y + 20], fill=KEY[cls], outline=INK)
        d.text((x + 36, y - 3), cls, font=font(24), fill=INK)
    d.text((70, h - 44),
           "PALT_P1_FINAL_DIMENSIONS: NOT_APPROVED · "
           "PALT_P1_MANUFACTURING_AUTHORITY: NOT_ESTABLISHED",
           font=font(21), fill=GREY)
    img.save(out_path)
    return out_path


def section_plan(components, dims, *, family) -> dict:
    """Where each named section is cut for this family."""
    tray = dims["tray"] if family == "P1B" else None
    if family == "P1B":
        p0 = tray["pockets"][0]
        row_y = p0["centre_mm"][1]
        col_x = p0["centre_mm"][0]
        wall_x = dims["case_width_mm"] / 2.0 - 1.0
    else:
        pitch = dims["pitch_mm"]
        row_y = -pitch
        col_x = -pitch
        wall_x = dims["envelope_mm"][0] / 2.0 - 1.0
    axis_x = 0.0
    knuckle_x = 0.0
    return {
        "pan_row": ("y", row_y), "pan_column": ("x", col_x),
        "lid_base_stack": ("y", row_y), "mirror_stack": ("y", 0.0),
        "hinge_axial": ("y", dims["hinge_axis_y_mm"]),
        "hinge_cross": ("x", knuckle_x),
        "clasp_engaged": ("x", axis_x), "clasp_disengaged": ("x", axis_x),
        "pocket_and_pan": ("x", col_x), "outer_wall": ("x", wall_x),
        "parting_seam": ("x", 0.0),
    }


def build_sections(components, dims, out_dir, *, family="P1B",
                   compose=None, mirror_present=False) -> dict:
    """Produce every named section for one family."""
    import os
    os.makedirs(out_dir, exist_ok=True)
    plan = section_plan(components, dims, family=family)
    made, skipped = {}, []
    closed = compose(components, dims, "CLOSED") if compose else components
    opened = compose(components, dims, "OPEN_90") if compose else components

    for key, axis, title, means in SECTIONS:
        if key == "mirror_stack" and not mirror_present:
            skipped.append({"section": key,
                            "why": "no mirror is established by the "
                                   "concept, so there is no stack to cut"})
            continue
        src = opened if key == "clasp_disengaged" else closed
        _ax, at = plan[key]
        try:
            cut = section_assembly(src, plan[key][0], at)
            path = os.path.join(out_dir, f"section_{key}.png")
            focus = FOCUS.get(key, ())
            draw_section(cut, path, f"{family} — {title}", means,
                         focus=focus,
                         focus_margin_mm=8.0 if key == "outer_wall"
                         else 3.0)
            made[key] = path
        except SectionError as exc:
            skipped.append({"section": key, "why": str(exc)[:200]})
    return {
        "record_type": SCHEMA, "family": family, "out_dir": out_dir,
        "required": [s[0] for s in SECTIONS],
        "produced": sorted(made), "produced_count": len(made),
        "skipped": skipped,
        "method": "TRUE_PLANE_CUT_NOT_CLIPPED_RENDER",
        "join_tolerance": None,
        "identity": hashlib.sha256(
            repr(sorted(made)).encode()).hexdigest()[:16],
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }
