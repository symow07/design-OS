"""Structural comparison page + difference checklist (DIP-2A-5-DIE-2).

The correction contract for task #47 requires a STRUCTURAL review artifact
generated BEFORE any graphics are applied: a human compares this page (and
its machine-readable checklist) against the customer's manufacturing
reference, and only after the structure passes does artwork placement run.

Output (both returned):
    {job_id}_structural_comparison.pdf   — 3 pages:
        1. structure-only preview (cut / crease / entry slits, panel labels,
           flap inventory callouts, no artwork)
        2. dimensional reconciliation: the three supplied dimension sets vs
           the engine model, every assumption spelled out, collision checks
        3. template parameter table + differences vs the replaced dieline +
           required-feature checklist
    {job_id}_structural_checklist.json   — the same content machine-readable
    (consumed by the Gate-2 production-readiness validator).
"""
from __future__ import annotations

import json
import os
from datetime import date

from reportlab.lib.colors import CMYKColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ..analysis.reconciliation import ReconciliationResult
from .counter_display_files import (
    INK,
    _polyline,
    _poly_path,
    _primitive_path,
    _resolve_fonts,
    _stadium_points,
)

_CUT = CMYKColor(1, 1, 0, 0)      # informational preview, process ink
_CREASE = CMYKColor(0, 1, 1, 0)
_GRAY = CMYKColor(0, 0, 0, 0.5)

#: Shared length between a crease and the cut boundary that counts as a
#: cut/fold conflict (endpoint contact is ~0.1 mm; a real panel edge is tens).
_CUT_FOLD_CONFLICT_MIN_MM = 2.0

_PAGE_W = 297.0                    # A4 landscape, mm
_PAGE_H = 210.0
_MARGIN = 14.0

# Required structural features are derived from the TEMPLATE REGISTRY, not
# hardcoded: each template DECLARES its own panel sequence and flap/notch
# capabilities, so the checklist asks "does the drawn die deliver what this
# template promised?" rather than "does it look like the Skynte die?".
# (Phase 2A-6A: a fixed side-seam list reported false MISSING_CLOSURE_GEOMETRY
# for every generic template.)

#: capability declared in the registry -> how the geometry evidences it.
_CAPABILITY_EVIDENCE = {
    "top_tuck_flap": lambda d: (d.get("top_tuck_height_mm")
                                or d.get("tuck_flap_height_mm", 0)) > 0,
    "bottom_tuck_flap": lambda d: (d.get("bottom_tuck_height_mm", 0) > 0
                                   or d.get("bottom_tuck_panel") is not None),
    "top_dust_flaps": lambda d: d.get("dust_flap_height_mm", 0) > 0,
    "bottom_dust_flaps": lambda d: d.get("dust_flap_height_mm", 0) > 0,
    "crash_lock_base": lambda d: (d.get("auto_bottom_height_mm") or 0) > 0,
    "cubic_shoulder_curves": lambda d: d.get("tuck_curve_h_mm", 0) > 0,
    "friction_slits": lambda d: d.get("slit_width_mm", 0) > 0,
    "tapered_glue_flap": lambda d: d.get("glue_tab_corner_cut_mm", 0) > 0,
    "tuck_base_entry_slits": lambda d: d.get("entry_slit_mm", 0) > 0,
    "per_hinge_creases": lambda d: True,   # verified by geometry_integrity
    "shoulder_lock_notches_2t": lambda d: d.get("lock_notch_mm", 0) > 0,
    "dust_base_notch": lambda d: d.get("dust_flap_base_notch_mm", 0) > 0,
}

_HUMAN_LABEL = {
    "top_tuck_flap": "top tuck flap",
    "bottom_tuck_flap": "bottom tuck closure (mirrored tuck, not a rectangle)",
    "top_dust_flaps": "top dust flaps",
    "bottom_dust_flaps": "bottom dust flaps",
    "crash_lock_base": "crash-lock auto bottom",
    "cubic_shoulder_curves": "rounded tuck-flap corners (cubic shoulders)",
    "friction_slits": "friction slits with tear-safe stadium ends",
    "tapered_glue_flap": "glue-flap taper on the free edge",
    "tuck_base_entry_slits": "tuck-base entry / locking slits",
    "per_hinge_creases": "creases drawn per hinge only — none over a cut edge",
    "shoulder_lock_notches_2t": "shoulder lock notches sized from board "
                                "thickness (2t)",
    "dust_base_notch": "angled dust flaps with base notch + top chamfer",
}


def required_features(coords) -> list[dict]:
    """What THIS template promised, and whether the die delivers it."""
    from apps.dielines import registry

    d = coords.derived or {}
    template_id = str(d.get("structure_type") or "")
    version = d.get("template_version")
    try:
        defn = registry.resolve(template_id, version)
    except (registry.UnknownTemplate, registry.TemplateVersionMismatch):
        return [{"feature": f"template {template_id!r} is not registered",
                 "present": False}]

    features = [{
        "feature": "panel sequence " + " | ".join(defn.panel_order()),
        "present": [p.name for p in coords.panels] == defn.panel_order(),
    }]
    for capability in sorted(defn.flap_capabilities | defn.notch_capabilities):
        check = _CAPABILITY_EVIDENCE.get(capability)
        if check is None:
            continue
        features.append({
            "feature": _HUMAN_LABEL.get(capability, capability),
            "present": bool(check(d)),
        })
    if defn.board_compensation_model != registry.BOARD_MODEL_NONE:
        features.append({
            "feature": "board-thickness compensation on panel widths",
            "present": d.get("thickness_compensation") is True,
        })
    integrity = geometry_integrity(coords)
    features.append({
        "feature": "no crease scored over a cut edge",
        "present": not integrity["cut_fold_conflict"],
    })
    features.append({
        "feature": "closed, non-self-intersecting cut contour",
        "present": not (integrity["self_intersecting"]
                        or integrity["open_contour"]),
    })
    return features


def build_checklist(
    coords, reconciliation: ReconciliationResult,
    previous_spec: dict | None = None,
) -> dict:
    """Machine-readable structural checklist (also feeds the PDF)."""
    d = coords.derived
    features = required_features(coords)
    differences = []
    prev = previous_spec or {}
    if prev:
        differences = [
            {"aspect": "template",
             "previous": prev.get("template", ""),
             "corrected": d.get("structure_type", "")},
            {"aspect": "panel sequence",
             "previous": "glue | main | side | main | side (STE engine order)",
             "corrected": "glue | side | main | side | main (supplied reference)"},
            {"aspect": "board thickness",
             "previous": f"{prev.get('board_thickness_mm', '')} mm",
             "corrected": f"{coords.board_thickness_mm:g} mm (inferred from "
                          "supplied inner dimensions)"},
            {"aspect": "tuck height model",
             "previous": "W × 1.227 (square-reference factor)",
             "corrected": "D + lip per end (DECISION-019)"},
            {"aspect": "tuck-base entry slits",
             "previous": "absent",
             "corrected": f"{d.get('entry_slit_mm', 0):g} mm per fold end"},
            {"aspect": "horizontal creases",
             "previous": "full-width, crossing cut edges",
             "corrected": "per hinge segment only"},
        ]
    return {
        "generated": date.today().isoformat(),
        "template": d.get("structure_type"),
        "template_version": d.get("template_version"),
        "archetype": d.get("archetype"),
        "panel_order": [p.name for p in coords.panels],
        "geometry_integrity": geometry_integrity(coords),
        "flat_mm": [coords.flat_width_mm, coords.flat_height_mm],
        "structure_passed_before_graphics": (
            reconciliation.reconciled and all(f["present"] for f in features)
        ),
        "required_features": features,
        "differences_vs_previous": differences,
        "parameters": d.get("parameters", {}),
        "reconciliation": reconciliation.to_dict(),
        "flap_inventory": _flap_inventory(coords),
    }


#: How far a boundary edge may sit off a crease and still count as lying on
#: it (float noise, not a real offset).
_COLLINEAR_TOLERANCE_MM = 0.01


def _collinear_overlap_mm(segment, boundary) -> float:
    """Exact length of ``segment`` that lies ON ``boundary``.

    Walks the boundary's edges, keeps the ones collinear with the segment
    (within `_COLLINEAR_TOLERANCE_MM`), projects them onto the segment's own
    axis and measures the union of the overlapping intervals. Endpoint
    contact contributes zero length, as it should.
    """
    x1, y1, x2, y2 = segment
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 0:
        return 0.0
    ux, uy = dx / length, dy / length          # unit direction
    nx, ny = -uy, ux                           # unit normal

    intervals: list[tuple[float, float]] = []
    coords_ring = list(boundary.coords)
    for (ax, ay), (bx, by) in zip(coords_ring, coords_ring[1:]):
        # both endpoints must sit on the segment's infinite line
        if abs((ax - x1) * nx + (ay - y1) * ny) > _COLLINEAR_TOLERANCE_MM:
            continue
        if abs((bx - x1) * nx + (by - y1) * ny) > _COLLINEAR_TOLERANCE_MM:
            continue
        ta = (ax - x1) * ux + (ay - y1) * uy    # projections onto the segment
        tb = (bx - x1) * ux + (by - y1) * uy
        lo, hi = (ta, tb) if ta <= tb else (tb, ta)
        lo, hi = max(lo, 0.0), min(hi, length)
        if hi - lo > 1e-9:
            intervals.append((lo, hi))

    if not intervals:
        return 0.0
    intervals.sort()
    total, cur_lo, cur_hi = 0.0, *intervals[0]
    for lo, hi in intervals[1:]:
        if lo > cur_hi + 1e-9:
            total += cur_hi - cur_lo
            cur_lo, cur_hi = lo, hi
        else:
            cur_hi = max(cur_hi, hi)
    return total + (cur_hi - cur_lo)


def geometry_integrity(coords) -> dict:
    """Contour-level integrity facts the Gate-2 structural checks read.

    * self_intersecting / open_contour — shapely validity + ring closure on
      the cut polygon (an open or crossing knife path is uncuttable).
    * cut_fold_conflict — a crease drawn along an edge that is actually cut.
      Creases are compared against the cut boundary: a crease segment lying
      ON the outer boundary would score a fold where the knife already goes
      (the defect DECISION-020 removed from the side-seam archetype).
    """
    poly = coords.cut_polygon
    ring = list(poly.exterior.coords)
    open_contour = ring[0] != ring[-1]
    boundary = poly.exterior

    # Measured EXACTLY, edge by edge: a buffered intersection inflates every
    # contact by the buffer radius, which both over-reports a real conflict
    # and invents fractions of a millimetre on creases that merely touch the
    # boundary at their endpoints. Collinear overlap is a 1-D interval
    # problem, so compute it as one.
    conflicts = []
    for x1, y1, x2, y2 in coords.fold_lines:
        shared = _collinear_overlap_mm((x1, y1, x2, y2), boundary)
        if shared >= _CUT_FOLD_CONFLICT_MIN_MM:
            conflicts.append({
                "segment": [x1, y1, x2, y2],
                "shared_mm": round(shared, 4),
            })

    return {
        "self_intersecting": not poly.is_valid,
        "open_contour": bool(open_contour),
        "cut_fold_conflict": bool(conflicts),
        "cut_fold_conflict_segments": conflicts,
        "component_count": len(coords.components),
    }


def _flap_inventory(coords) -> list[dict]:
    d = coords.derived
    inv = []
    for cid, poly in coords.components:
        b = poly.bounds
        inv.append({
            "component": cid,
            "width_mm": round(b[2] - b[0], 2),
            "height_mm": round(b[3] - b[1], 2),
        })
    for sid, cx, cy, sw, sh in coords.stadium_cutouts:
        inv.append({"component": sid, "width_mm": round(sw, 2),
                    "height_mm": round(sh, 2), "kind": "slit"})
    for i, (sx1, _sy1, sx2, _sy2) in enumerate(coords.slit_lines):
        inv.append({"component": f"entry-slit-{i}",
                    "width_mm": round(abs(sx2 - sx1), 2),
                    "height_mm": 0.0, "kind": "entry-cut"})
    if d.get("lock_notch_mm"):
        inv.append({"component": "shoulder-lock-notches (x4)",
                    "width_mm": d["lock_notch_mm"],
                    "height_mm": d["lock_notch_mm"], "kind": "notch"})
    return inv


def export_structural_comparison(
    coords, reconciliation: ReconciliationResult, job_id: str,
    output_dir: str, previous_spec: dict | None = None,
) -> tuple[str, str]:
    """Write the comparison PDF + checklist JSON; returns (pdf_path, json_path)."""
    os.makedirs(output_dir, exist_ok=True)
    checklist = build_checklist(coords, reconciliation, previous_spec)

    json_path = os.path.join(output_dir, f"{job_id}_structural_checklist.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(checklist, fh, indent=2)

    pdf_path = os.path.join(output_dir, f"{job_id}_structural_comparison.pdf")
    font_r, font_b = _resolve_fonts()
    c = canvas.Canvas(pdf_path, pagesize=(_PAGE_W * mm, _PAGE_H * mm))
    c.setTitle(f"Structural comparison — {checklist['template']}"
               f"/{checklist['template_version']}")

    _page_preview(c, coords, checklist, font_r, font_b)
    c.showPage()
    _page_reconciliation(c, checklist, font_r, font_b)
    c.showPage()
    _page_checklist(c, checklist, font_r, font_b)
    c.save()
    return pdf_path, json_path


# --- page 1: structure-only preview ----------------------------------------


def _page_preview(c, coords, checklist, font_r, font_b):
    c.setFillColor(INK)
    c.setFont(font_b, 13)
    c.drawString(_MARGIN * mm, (_PAGE_H - _MARGIN) * mm,
                 "STRUCTURAL COMPARISON — STRUCTURE ONLY, NO ARTWORK")
    c.setFont(font_r, 8.5)
    c.drawString(
        _MARGIN * mm, (_PAGE_H - _MARGIN - 5.5) * mm,
        f"{checklist['template']}/{checklist['template_version']}  ·  "
        f"flat {coords.flat_width_mm:g} × {coords.flat_height_mm:g} mm  ·  "
        "compare against the customer's manufacturing reference BEFORE "
        "applying graphics",
    )

    # Fit the flat into the drawing area.
    area_x, area_y = _MARGIN, _MARGIN + 6.0
    area_w, area_h = _PAGE_W - 2 * _MARGIN, _PAGE_H - 2 * _MARGIN - 18.0
    s = min(area_w / coords.flat_width_mm, area_h / coords.flat_height_mm)
    ox = area_x + (area_w - coords.flat_width_mm * s) / 2.0
    oy = area_y + (area_h - coords.flat_height_mm * s) / 2.0

    def TX(x):
        return (ox + x * s) * mm

    def TY(y):
        return (oy + (coords.flat_height_mm - y) * s) * mm

    c.setStrokeColor(_CREASE)
    c.setLineWidth(0.5)
    c.setDash([2.2 * mm, 1.2 * mm])
    for x1, y1, x2, y2 in coords.fold_lines:
        c.line(TX(x1), TY(y1), TX(x2), TY(y2))

    c.setStrokeColor(_CUT)
    c.setLineWidth(0.7)
    c.setDash()
    for cid, poly in coords.components:
        prims = coords.component_paths.get(cid)
        if prims:
            _primitive_path(c, prims, TX, TY)
        else:
            _poly_path(c, poly, TX, TY)
    for _sid, cx, cy, sw, sh in coords.stadium_cutouts:
        _polyline(c, _stadium_points(cx, cy, sw, sh), TX, TY, close=True)
    for sx1, sy1, sx2, sy2 in coords.slit_lines:
        c.line(TX(sx1), TY(sy1), TX(sx2), TY(sy2))

    # Panel labels with real widths.
    c.setFillColor(_GRAY)
    c.setFont(font_b, 8)
    for p in coords.panels:
        cx = TX(p.x + p.width / 2.0)
        cy = TY(p.y + p.height / 2.0)
        c.drawCentredString(cx, cy, p.name.replace("_", " "))
        c.setFont(font_r, 7)
        c.drawCentredString(cx, cy - 3.4 * mm, f"{p.width:g} mm")
        c.setFont(font_b, 8)

    # Flap callouts. Built from whatever the ENGINE published: the side-seam
    # archetype reports a tuck lip and entry slits, the generic engines do
    # not, so every key is optional (Phase 2A-6A: indexing side-seam-only keys
    # crashed the whole standard path for generic templates).
    d = coords.derived
    c.setFont(font_r, 7)
    parts = []
    tuck_h = d.get("top_tuck_height_mm", d.get("tuck_flap_height_mm"))
    if tuck_h:
        lip = d.get("top_tuck_lip_mm")
        parts.append(
            f"top tuck {tuck_h:g} mm"
            + (f" (D {coords.dimensions.manufacture[1]:g} + lip {lip:g})"
               if lip else "")
        )
    for label, key, fmt in (
        ("dust", "dust_flap_height_mm", "g"),
        ("entry slits", "entry_slit_mm", "g"),
        ("lock notches", "lock_notch_mm", "g"),
        ("slit", "slit_width_mm", ".1f"),
    ):
        value = d.get(key)
        if value:
            parts.append(f"{label} {value:{fmt}} mm")
    c.setFillColor(INK)
    c.drawString(_MARGIN * mm, (area_y - 4.5) * mm, "   ·   ".join(parts))


# --- page 2: reconciliation --------------------------------------------------


def _page_reconciliation(c, checklist, font_r, font_b):
    rec = checklist["reconciliation"]
    y = _PAGE_H - _MARGIN
    c.setFillColor(INK)
    c.setFont(font_b, 13)
    c.drawString(_MARGIN * mm, y * mm, "DIMENSIONAL VALIDATION")
    y -= 7

    c.setFont(font_r, 8.5)
    mfg = rec["manufacture_mm"]
    c.drawString(_MARGIN * mm, y * mm,
                 f"manufacturing (drawn truth): {mfg[0]:g} × {mfg[1]:g} × "
                 f"{mfg[2]:g} mm   ·   board t = {rec['board_thickness_mm']:g} mm"
                 f" (inferred {rec['board_thickness_inferred_mm']} mm)   ·   "
                 f"reconciled: {'YES' if rec['reconciled'] else 'NO'}")
    y -= 8

    c.setFont(font_b, 8.5)
    for col, x in (("set", 0), ("axis", 22), ("supplied", 44), ("model", 68),
                   ("delta", 90), ("status", 108)):
        c.drawString((_MARGIN + x) * mm, y * mm, col)
    y -= 4.5
    c.setFont(font_r, 8.5)
    for a in rec["axis_checks"]:
        for val, x in ((a["dimension_set"], 0), (a["axis"], 22),
                       (f"{a['supplied_mm']:g}", 44), (f"{a['model_mm']:g}", 68),
                       (f"{a['delta_mm']:+g}", 90), (a["status"], 108)):
            c.drawString((_MARGIN + x) * mm, y * mm, str(val))
        y -= 4.5
    y -= 3

    c.setFont(font_b, 9)
    c.drawString(_MARGIN * mm, y * mm,
                 "ASSUMPTIONS (reported, never silently applied):")
    y -= 5
    c.setFont(font_r, 8)
    for a in rec["assumptions"]:
        for i, line in enumerate(_wrap(a, 150)):
            c.drawString((_MARGIN + 4) * mm, y * mm,
                         ("• " if i == 0 else "  ") + line)
            y -= 4
    y -= 2
    if rec["discrepancies"]:
        c.setFont(font_b, 9)
        c.drawString(_MARGIN * mm, y * mm, "DISCREPANCIES — HUMAN DECISION REQUIRED:")
        y -= 5
        c.setFont(font_r, 8)
        for disc in rec["discrepancies"]:
            for line in _wrap(disc, 150):
                c.drawString((_MARGIN + 4) * mm, y * mm, line)
                y -= 4

    y -= 3
    c.setFont(font_b, 9)
    c.drawString(_MARGIN * mm, y * mm, "CLOSURE COLLISION CHECKS:")
    y -= 5
    c.setFont(font_r, 8)
    for cc in rec["collision_checks"]:
        mark = "PASS" if cc["ok"] else "FAIL"
        c.drawString((_MARGIN + 4) * mm, y * mm,
                     f"[{mark}] {cc['name']}: {cc['value_mm']:g} mm "
                     f"(limit {cc['limit_mm']:g}) — {cc['detail']}"[:170])
        y -= 4


# --- page 3: parameters, differences, features -------------------------------


def _page_checklist(c, checklist, font_r, font_b):
    y = _PAGE_H - _MARGIN
    c.setFillColor(INK)
    c.setFont(font_b, 13)
    c.drawString(_MARGIN * mm, y * mm,
                 "TEMPLATE PARAMETERS · DIFFERENCES · REQUIRED FEATURES")
    y -= 8

    c.setFont(font_b, 9)
    c.drawString(_MARGIN * mm, y * mm, "PARAMETERS "
                 f"({checklist['template']}/{checklist['template_version']}):")
    y -= 5
    c.setFont(font_r, 8)
    for k, v in checklist["parameters"].items():
        c.drawString((_MARGIN + 4) * mm, y * mm, f"{k} = {v}")
        y -= 4
    y -= 3

    if checklist["differences_vs_previous"]:
        c.setFont(font_b, 9)
        c.drawString(_MARGIN * mm, y * mm, "DIFFERENCES VS REPLACED DIELINE:")
        y -= 5
        c.setFont(font_r, 8)
        for diff in checklist["differences_vs_previous"]:
            c.drawString((_MARGIN + 4) * mm, y * mm,
                         f"{diff['aspect']}: {diff['previous']}  →  "
                         f"{diff['corrected']}"[:175])
            y -= 4
        y -= 3

    c.setFont(font_b, 9)
    c.drawString(_MARGIN * mm, y * mm, "REQUIRED REFERENCE FEATURES:")
    y -= 5
    c.setFont(font_r, 8)
    for f in checklist["required_features"]:
        mark = "PRESENT" if f["present"] else "MISSING"
        c.drawString((_MARGIN + 4) * mm, y * mm, f"[{mark}] {f['feature']}")
        y -= 4
    y -= 4

    passed = checklist["structure_passed_before_graphics"]
    c.setFont(font_b, 10)
    c.drawString(
        _MARGIN * mm, y * mm,
        "STRUCTURE GATE: "
        + ("PASSED — graphics placement may proceed" if passed
           else "NOT PASSED — do not place graphics"),
    )


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


__all__ = ["build_checklist", "export_structural_comparison"]
