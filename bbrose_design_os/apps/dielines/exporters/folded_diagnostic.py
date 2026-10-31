"""Real folded-closure diagnostic (Phase 2A-9-CORR-2 §4).

Simulates the closure mechanics of a tuck carton by transforming the
ACTUAL flap outlines (the same polygons/Bézier paths the die cuts) through
the fold rotations — not a decorated rectangular box:

    stage 1  fully open (flat flaps, glued tube)
    stage 2  top closure half-folded (dust flaps in, tuck at 45°)
    stage 3  top closed; bottom closure half-folded
    stage 4  fully closed (both hooks inserted)

Each frame labels panel identities, the opposing attachment (top tuck on
MAIN A, bottom tuck on MAIN B), dust flaps, slit positions, the glue seam
and the insertion order (1 dust → 2 dust → 3 tuck). The folded collision
numbers come from the geometry module's collision_report, which measures
the actual flap outlines, and are printed on the sheet.
"""
from __future__ import annotations

import math

_ISO_CO = math.cos(math.radians(30))
_ISO_SI = math.sin(math.radians(30))


def _project(p, scale, ox, oy):
    x, y, z = p
    px = (x - y) * _ISO_CO
    py = z + (x + y) * _ISO_SI
    return (ox + px * scale, oy - py * scale)


class _Frame:
    """One body panel's 3D frame: origin at the hinge start, ``d`` along
    the panel, ``n`` pointing into the box."""

    def __init__(self, origin, d, n):
        self.origin, self.d, self.n = origin, d, n

    def body_point(self, u, z):
        ox, oy, oz = self.origin
        return (ox + u * self.d[0], oy + u * self.d[1], oz + z)

    def flap_point(self, u, v, z_edge, sign, theta, fold_v=None, phi=0.0):
        """Flap point at (u, v beyond the hinge). ``sign`` +1 = top flap,
        -1 = bottom. ``theta`` fold angle (0 = flat extension, 90 = over
        the opening); beyond ``fold_v`` the hook rotates by ``phi`` more."""
        base_u = self.body_point(u, z_edge)
        th = math.radians(theta)

        def offset(dist, ang):
            up = math.cos(ang) * sign
            inw = math.sin(ang)
            return (dist * inw * self.n[0], dist * inw * self.n[1],
                    dist * up)

        if fold_v is None or v <= fold_v:
            o = offset(v, th)
            return (base_u[0] + o[0], base_u[1] + o[1], base_u[2] + o[2])
        o1 = offset(fold_v, th)
        o2 = offset(v - fold_v, th + math.radians(phi))
        return (base_u[0] + o1[0] + o2[0], base_u[1] + o1[1] + o2[1],
                base_u[2] + o1[2] + o2[2])


def _flap_uv(polygon, hinge_x0, hinge_y, top):
    """Flat outline -> (u, v>=0) relative to its hinge (flat is y-down)."""
    pts = []
    for px, py in polygon.exterior.coords:
        v = (hinge_y - py) if top else (py - hinge_y)
        pts.append((px - hinge_x0, max(v, 0.0)))
    return pts


def export_folded_diagnostic(coords, out_path: str,
                             collision: dict | None = None,
                             closure=None) -> str | None:
    """Render the 4-stage folded diagnostic PNG; returns the path.

    ``closure`` (2A-9C slice 0): an optional
    apps.dielines.qualification.closure.ClosureModel naming the tuck and
    dust panels — entry-slit ear closures, stadium friction closures and
    straight/reverse orientations all articulate through the same
    transforms. Default (None) keeps the opposing-tuck behavior.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    d = coords.derived
    panels = {p.name: p for p in coords.panels}
    if closure is None:
        top_name, bottom_name = "main_a", "main_b"
        dust_names = ("side_a", "side_b", "side_a", "side_b")
    else:
        top_name, bottom_name = (closure.top_tuck_panel,
                                 closure.bottom_tuck_panel)
        dust_names = tuple(closure.dust_panels)
    body_names = [p.name for p in coords.panels if p.name != "glue_tab"]
    main_a, side_a = panels[body_names[0]], panels[body_names[1]]
    main_b, side_b = panels[body_names[2]], panels[body_names[3]]
    H = coords.dimensions.inner[2]
    t = coords.board_thickness_mm
    closure_v = coords.dimensions.manufacture[1] - 2 * t   # P - 2t

    # tube frames (turtle: +x, +y, -x, -y; inward = left-rotate(heading))
    frames = {}
    pos, heading = (0.0, 0.0, 0.0), (1.0, 0.0)
    for panel in (main_a, side_a, main_b, side_b):
        inward = (-heading[1], heading[0])
        frames[panel.name] = _Frame(pos, (heading[0], heading[1], 0.0),
                                    (inward[0], inward[1], 0.0))
        pos = (pos[0] + panel.width * heading[0],
               pos[1] + panel.width * heading[1], 0.0)
        heading = (-heading[1], heading[0])

    # flap outlines in (u, v) form — hinge panels come from the closure
    top_panel, bottom_panel = panels[top_name], panels[bottom_name]
    tuck_top = _flap_uv(coords.tuck_flap_polygons[0], top_panel.x,
                        top_panel.y, top=True)
    tuck_bot = _flap_uv(coords.tuck_flap_polygons[1], bottom_panel.x,
                        bottom_panel.y + bottom_panel.height, top=False)
    dust = {}
    for index, key in enumerate(("d0_top", "d1_top", "d2_bot", "d3_bot")):
        dust_panel = panels[dust_names[index]]
        is_top = key.endswith("top")
        dust[key] = _flap_uv(
            coords.dust_flap_polygons[index], dust_panel.x,
            dust_panel.y if is_top else dust_panel.y + dust_panel.height,
            is_top)
    slit_l = float(d.get("entry_slit_mm") or 0.0)

    stages = [
        ("1 — FULLY OPEN", dict(td=0, tt=0, th=0, bd=0, bt=0, bh=0)),
        ("2 — TOP HALF-FOLDED (dust in first)",
         dict(td=90, tt=45, th=45, bd=0, bt=0, bh=0)),
        ("3 — TOP CLOSED, BOTTOM HALF-FOLDED",
         dict(td=90, tt=90, th=90, bd=90, bt=45, bh=45)),
        ("4 — FULLY CLOSED (hooks inserted, ears in slits)",
         dict(td=90, tt=90, th=90, bd=90, bt=90, bh=90)),
    ]

    frame_w, frame_h = 760, 720
    img = Image.new("RGB", (frame_w * 2, frame_h * 2 + 120), "white")
    draw = ImageDraw.Draw(img)
    scale = 3.4

    for idx, (title, a) in enumerate(stages):
        ox = (idx % 2) * frame_w + 300
        oy = (idx // 2) * frame_h + 470

        def poly3d(points3d, color, width=2, fill=None):
            pts = [_project(p, scale, ox, oy) for p in points3d]
            if fill:
                draw.polygon(pts, fill=fill, outline=color)
            else:
                draw.line(pts + [pts[0]], fill=color, width=width)

        def label3d(p, text, color="black"):
            x, y = _project(p, scale, ox, oy)
            draw.text((x - 4 * len(text), y - 6), text, fill=color)

        # body panels (fills ordered far -> near for painter overlap)
        order = [main_b.name, side_b.name, side_a.name, main_a.name]
        fills = {main_a.name: "#F2E8DC", side_a.name: "#E4D5C3",
                 main_b.name: "#EADFCE", side_b.name: "#DCCBB5"}
        for name in order:
            panel = panels[name]
            fr = frames[name]
            ring = [fr.body_point(0, 0), fr.body_point(panel.width, 0),
                    fr.body_point(panel.width, H), fr.body_point(0, H)]
            poly3d(ring, "#555555", fill=fills[name])
        panel_labels = {main_a.name: "MAIN A", side_a.name: "SIDE A",
                        main_b.name: "MAIN B", side_b.name: "SIDE B"}
        for name in order:
            panel = panels[name]
            fr = frames[name]
            label3d(fr.body_point(panel.width / 2, H / 2),
                    panel_labels[name])

        # glue seam: first body panel's left edge meets the free edge
        fr_a = frames[main_a.name]
        poly3d([fr_a.body_point(0, 0), fr_a.body_point(0, H)],
               "#B03030", width=4)
        label3d(fr_a.body_point(0, H * 0.15), "GLUE SEAM", "#B03030")

        # dust flaps (drawn before the tuck that covers them)
        for index, (key, sign, angle_key) in enumerate((
                ("d0_top", +1, "td"), ("d1_top", +1, "td"),
                ("d2_bot", -1, "bd"), ("d3_bot", -1, "bd"))):
            fr = frames[dust_names[index]]
            z_edge = H if sign > 0 else 0.0
            pts = [fr.flap_point(u, v, z_edge, sign, a[angle_key])
                   for u, v in dust[key]]
            poly3d(pts, "#3060C0", width=2)
        label3d(frames[dust_names[0]].flap_point(side_a.width / 2, 12, H, 1,
                                                 a["td"]),
                "DUST (1st/2nd)", "#3060C0")

        # major tucks per the declared closure attachment
        for uv, fr_name, sign, tkey, hkey, label in (
                (tuck_top, top_name, +1, "tt", "th",
                 f"TOP TUCK ← {top_name.upper()}"),
                (tuck_bot, bottom_name, -1, "bt", "bh",
                 f"BOTTOM TUCK ← {bottom_name.upper()}")):
            fr = frames[fr_name]
            z_edge = H if sign > 0 else 0.0
            pts = [fr.flap_point(u, v, z_edge, sign, a[tkey],
                                 fold_v=closure_v, phi=a[hkey])
                   for u, v in uv]
            poly3d(pts, "#207040", width=3)
            mid_u = (max(u for u, _ in uv) + min(u for u, _ in uv)) / 2
            label3d(fr.flap_point(mid_u, closure_v / 2, z_edge, sign,
                                  a[tkey], fold_v=closure_v, phi=a[hkey]),
                    label + " (3rd)", "#207040")
            # lock markers: slit/ear positions (entry-slit closures) or
            # the friction-slit ends (stadium closures)
            marker_u = ((slit_l / 2, max(u for u, _ in uv) - slit_l / 2)
                        if slit_l > 0 else
                        (max(u for u, _ in uv) * 0.35,
                         max(u for u, _ in uv) * 0.65))
            for u_slit in marker_u:
                p = fr.flap_point(u_slit, closure_v, z_edge, sign,
                                  a[tkey], fold_v=closure_v, phi=a[hkey])
                x, y = _project(p, scale, ox, oy)
                draw.ellipse([x - 3, y - 3, x + 3, y + 3],
                             outline="#C08000", width=2)
        label3d(frames[top_name].flap_point(10, closure_v, H, 1, a["tt"],
                                            fold_v=closure_v, phi=a["th"]),
                "slit/ear" if slit_l > 0 else "friction lock", "#C08000")

        draw.text((ox - 280, oy - 450), title, fill="black")

    orientation = (closure.orientation if closure is not None
                   else "OPPOSING_TUCK")
    lock_note = ("the 2t ears snap into the entry slits (amber markers)"
                 if slit_l > 0 else
                 "the shoulders lock behind the friction slits "
                 "(amber markers)")
    draw.text((20, frame_h * 2 + 10),
              "FOLDED-CLOSURE DIAGNOSTIC — actual flap outlines transformed "
              f"through the fold rotations. {orientation} attachment: top "
              f"tuck on {top_name.upper()}, bottom tuck on "
              f"{bottom_name.upper()}. Insertion order per end: dust flap, "
              f"dust flap, then the tuck; {lock_note}.",
              fill="black")
    if collision:
        failed = [c["name"] for c in collision.get("checks", [])
                  if not c["ok"]]
        draw.text((20, frame_h * 2 + 40),
                  ("folded collision checks: ALL PASS ("
                   f"{len(collision.get('checks', []))} checks on actual "
                   "flap geometry)") if not failed
                  else "FOLDED COLLISION FAILURES: " + ", ".join(failed),
                  fill="#207040" if not failed else "#B03030")
    draw.text((20, frame_h * 2 + 70),
              "PROVISIONAL STRUCTURE — PHYSICAL SAMPLE REQUIRED — NOT "
              "APPROVED FOR MASS PRODUCTION", fill="#B03030")

    img.save(out_path)
    return out_path


__all__ = ["export_folded_diagnostic"]
