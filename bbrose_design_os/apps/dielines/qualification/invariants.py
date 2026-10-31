"""Parametric invariants (2A-9B §3) — checked for EVERY valid combination.

Archetype-aware but generically structured: an adapter names the expected
panel sequence and tuck panels; everything else measures the emitted
DielineCoordinates directly (contours, slits, creases, folded collisions,
reconciliation, determinism).
"""
from __future__ import annotations


def check_invariants(coords, *, expected_inner, adapter) -> list[str]:
    """All violated §3 invariants; empty list = the die holds."""
    problems: list[str] = []
    d = coords.derived or {}

    def bad(msg):
        problems.append(msg)

    # panel sequence + attachment
    order = [p.name for p in coords.panels]
    if order != adapter.panel_sequence:
        bad(f"panel sequence {order} != {adapter.panel_sequence}")
    if d.get("top_tuck_panel") != adapter.top_tuck_panel:
        bad(f"top tuck on {d.get('top_tuck_panel')} != "
            f"{adapter.top_tuck_panel}")
    if d.get("bottom_tuck_panel") != adapter.bottom_tuck_panel:
        bad(f"bottom tuck on {d.get('bottom_tuck_panel')} != "
            f"{adapter.bottom_tuck_panel}")

    # inner dimensions preserved
    if tuple(round(v, 4) for v in coords.dimensions.inner) != \
            tuple(round(v, 4) for v in expected_inner):
        bad(f"inner {coords.dimensions.inner} != requested "
            f"{tuple(expected_inner)}")

    # dust flaps attached to the side panels
    panels = {p.name: p for p in coords.panels}
    for polygon, side in zip(coords.dust_flap_polygons,
                             adapter.closure.dust_panels):
        minx, _, maxx, _ = polygon.bounds
        panel = panels[side]
        if not (panel.x - 0.01 <= minx and maxx <= panel.right + 0.01):
            bad(f"dust flap escapes {side}")

    # contour / cut-fold integrity
    from apps.dielines.exporters.structural_comparison import (
        geometry_integrity,
    )
    integrity = geometry_integrity(coords)
    if integrity["open_contour"]:
        bad("cut contour is open")
    if integrity["self_intersecting"]:
        bad("cut contour self-intersects")
    if integrity["cut_fold_conflict"]:
        bad("a crease overlaps a cut edge")

    # closure-specific slit/notch/lock checks — driven by the DECLARED
    # closure model, never by an entry-slit assumption. No family runs
    # with zero lock checks.
    from apps.dielines.qualification.closure import (
        SLIT_ENTRY_L_CUT,
        SLIT_STADIUM_FRICTION,
        SLIT_TUCK_BASE_ENTRY,
    )
    closure = adapter.closure
    if closure.slit_type == SLIT_ENTRY_L_CUT:
        # entry slits stay cut interruptions; creases stop around them;
        # ears align with the slits (unchanged opposing-tuck rigor)
        if len(coords.slit_lines) != closure.expected_slit_line_count:
            bad(f"{len(coords.slit_lines)} slit cuts != "
                f"{closure.expected_slit_line_count}")
        slit_l = float(d.get("entry_slit_mm", 0.0))
        fold_spans = [(min(x1, x2), max(x1, x2), y1)
                      for (x1, y1, x2, y2) in coords.fold_lines
                      if abs(y1 - y2) < 1e-6]
        slit_x = sorted({round(s[0], 3) for s in coords.slit_lines}
                        | {round(s[2], 3) for s in coords.slit_lines})
        for main in (closure.top_tuck_panel, closure.bottom_tuck_panel):
            panel = panels[main]
            expected_lo = panel.x + slit_l
            matches = [s for s in fold_spans
                       if abs(s[0] - expected_lo) < 0.51]
            if not matches:
                bad(f"no fold crease starts {slit_l:g} mm inside {main} "
                    "(crease not shortened around the slits)")
            for edge in (panel.x, panel.right):
                if not any(abs(sx - edge) < 0.51
                           or abs(sx - edge - slit_l) < 0.51
                           or abs(sx - edge + slit_l) < 0.51
                           for sx in slit_x):
                    bad(f"no entry slit aligned with the {main} ear at "
                        f"x = {edge:g}")
    elif closure.slit_type == SLIT_STADIUM_FRICTION:
        # friction closures: stadium slits present per active tuck; 2t
        # lock notches recorded when compensation is on
        if len(coords.stadium_cutouts) != closure.expected_stadium_count:
            bad(f"{len(coords.stadium_cutouts)} stadium friction slits != "
                f"{closure.expected_stadium_count}")
        if d.get("thickness_compensation") and \
                not float(d.get("lock_notch_mm") or 0) > 0:
            bad("compensated die is missing the 2t shoulder lock notches")
    elif closure.slit_type == SLIT_TUCK_BASE_ENTRY:
        # DECISION-020 side-seam entry slits are line cuts at fold ends;
        # the closure ALSO carries stadium friction slits + 2t lock
        # notches — all three are checked (strengthening, not weakening).
        if not coords.slit_lines:
            bad("tuck-base entry slits are missing")
        if closure.expected_stadium_count and \
                len(coords.stadium_cutouts) != closure.expected_stadium_count:
            bad(f"{len(coords.stadium_cutouts)} stadium friction slits != "
                f"{closure.expected_stadium_count}")
        if d.get("thickness_compensation") and \
                not float(d.get("lock_notch_mm") or 0) > 0:
            bad("compensated die is missing the 2t shoulder lock notches")

    # no duplicate cut or crease segments (all closures)
    def _norm(seg):
        a, b = (round(seg[0], 4), round(seg[1], 4)), \
               (round(seg[2], 4), round(seg[3], 4))
        return (a, b) if a <= b else (b, a)
    for name, segs in (("crease", coords.fold_lines),
                       ("slit-cut", coords.slit_lines)):
        normed = [_norm(s) for s in segs]
        if len(normed) != len(set(normed)):
            bad(f"duplicate {name} segments emitted")

    # glue flap tapered and clear
    if d.get("glue_tab_corner_cut_mm", 0) <= 0:
        bad("glue flap is not tapered")
    glue_minx = coords.glue_tab_polygon.bounds[0]
    if glue_minx < -1e-6:
        bad("glue flap escapes the flat origin")

    # folded checks on the actual flap geometry (dust envelope, tuck
    # collision, ear engagement, bleed, component overlap ...)
    folded = adapter.collision_report(coords)
    for check in folded["checks"]:
        if not check["ok"]:
            bad(f"folded check failed: {check['name']} — {check['detail']}")

    # top and bottom tuck flaps must not collide in the closed state:
    # they close over DIFFERENT openings (top/bottom); verify their flat
    # zones do not overlap the same opening
    top_tuck, bottom_tuck = coords.tuck_flap_polygons
    if top_tuck.intersection(bottom_tuck).area > 1e-9:
        bad("top and bottom tuck flaps overlap in the flat")

    # bleed and safe
    if not coords.bleed_polygon.contains(coords.cut_polygon):
        bad("bleed does not enclose the full cut contour")
    if not coords.cut_polygon.contains(coords.safe_polygon):
        bad("safe area escapes the cut contour")

    # inner/manufacturing/outer reconcile
    from apps.dielines.analysis.reconciliation import reconcile_dimensions
    reconciliation = reconcile_dimensions(
        coords, supplied_inner=coords.dimensions.inner,
        supplied_outer=coords.dimensions.outer)
    if reconciliation.discrepancies:
        bad("dimension reconciliation: "
            + " | ".join(reconciliation.discrepancies))
    for check in reconciliation.collision_checks:
        if not check.ok:
            bad(f"reconciliation check failed: {check.name}")

    # determinism
    if adapter.content_hashes(coords) != \
            adapter.content_hashes(adapter.calculate(expected_inner,
                                                     coords)):
        bad("geometry is not deterministic")
    return problems


__all__ = ["check_invariants"]
