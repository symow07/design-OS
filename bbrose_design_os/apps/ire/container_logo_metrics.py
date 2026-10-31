"""VQR-3 — rendered logo metrics (``container_logo_metrics/1.0``).

``visual_quality_gate._logo_axis`` has read this contract since VQR-2A and
nothing has ever produced it, so the logo axis has been permanently
UNMEASURED — which is blocking. This module measures the logo AS EMITTED:
the node a composer actually placed, against the asset file it actually
pointed at.

THREE MEASURED FACTS, no inference:

* ``rendered_extent_pt`` — the placed x-extent. "Extent" with no axis
  qualifier already means the x-extent in this codebase
  (``geometry_validation_render.rendered_extent_mm``); that convention is
  reused rather than a second one invented. Document space is mm
  (``graph.Document.page_w``) and is converted here once.
* ``clipped`` — the placement leaves its own clip path, or leaves the page.
* ``materially_distorted`` — the placed aspect differs from the asset's
  INTRINSIC aspect. A raster drawn at a non-uniform scale IS distorted;
  ``ASPECT_TOLERANCE`` exists only to absorb float rounding in mm-space
  geometry. It is not a design allowance and is not copied from any gate
  threshold's provenance.

A composer may place the logo more than once (the dropper sheet emits a hero
and a flat view). Every placement is recorded and the three gate-read
scalars take the WORST case — smallest extent, any clipped, any distorted —
because averaging across placements would hide a defective one.

WHEN THE ASSET CANNOT BE READ THERE IS NO RECORD. Distortion is unknowable
without the intrinsic aspect, and a record whose ``materially_distorted`` is
absent reads at the gate as False — a claim that the artwork is undistorted,
made from no measurement. An absent record leaves the axis UNMEASURED, which
is the true state.

A placement with no width or height has no aspect at all. That is a MEASURED
defect rather than an unmeasurable one, so it is recorded as
``degenerate_box`` and distorts the record, instead of dividing into a
plausible-looking 0.0.

Known limitation, stated rather than hidden: a curved clip path is bounded
by its control hull, which over-estimates the clip area, so clipping by a
curve can be under-reported. Every clip emitted today is a rectangle.

Pure: no Django, no ORM, no network.

[THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace, switch
the mark to it so gold foil can print." A mark drawn from its approved vector master is measured too — it is an
AssetRef, its box placed as the raster's is, and its INTRINSIC aspect is the master's ink bounds'
(``apps/ire/brand_mark.py``), so a box stretched off the master's proportion is distorted exactly as a stretched raster
is. Its asset row names the master file and its sha256, and ``intrinsic_px`` is None: a vector has no pixels.]
"""
from __future__ import annotations

import hashlib
import os

SCHEMA = "container_logo_metrics/1.0"

MM_TO_PT = 72.0 / 25.4

#: Relative aspect deviation absorbed as float rounding, NOT as a design
#: allowance: placements are computed in mm and rounded at three decimals,
#: so 1% sits far above that noise and far below any deliberate stretch.
ASPECT_TOLERANCE = 0.01

_EPS_MM = 1e-6


def _intrinsic(path: str):
    """``(width_px, height_px, height/width)`` for a readable raster asset,
    or None when the file cannot be measured."""
    try:
        from PIL import Image as _PILImage
        with _PILImage.open(path) as im:
            width, height = im.size
    except Exception:  # noqa: BLE001 — any decode failure is unmeasurable
        return None
    if not width or not height:
        return None
    return int(width), int(height), height / width


def _sha256(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return ""


def _clip_bbox(clip):
    xs = [s.x for s in clip if hasattr(s, "x")]
    ys = [s.y for s in clip if hasattr(s, "y")]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _clip_findings(node, doc) -> list:
    x0, y0 = node.x, node.y
    x1, y1 = node.x + node.w, node.y + node.h
    findings = []
    # [the owner's second answer of 2026-09-25: a mark drawn from its approved vector master is an AssetRef, which
    # carries no clip of its own]
    clip = getattr(node, "clip", None)
    box = _clip_bbox(clip) if clip else None
    if box and (x0 < box[0] - _EPS_MM or y0 < box[1] - _EPS_MM
                or x1 > box[2] + _EPS_MM or y1 > box[3] + _EPS_MM):
        findings.append("clip_path")
    if x0 < -_EPS_MM or y0 < -_EPS_MM \
            or x1 > doc.page_w + _EPS_MM or y1 > doc.page_h + _EPS_MM:
        findings.append("page_bounds")
    return findings


def logo_image_nodes(doc) -> list:
    """The emitted logo rasters, classified exactly as the v1.1 census and
    Design Graph 2.0 classify them — reference wins over logo — so the three
    records cannot disagree about which node is the logo."""
    found = []
    for node, parent in doc.walk():
        if node.type != "image":
            continue
        low = str(getattr(node, "name", "") or "").lower()
        if "reference" in low or (
                parent is not None
                and getattr(parent, "name", "") == "Reference"):
            continue
        if "logo" in low:
            found.append(node)
    return found


def measure_logo_metrics(doc, *, confirmed_assets=()) -> dict | None:
    """``container_logo_metrics/1.0`` for an emitted Document, or None when
    no logo was emitted or its asset cannot be measured.

    ``confirmed_assets`` are the files an owner has actually authorised. With
    none supplied the record says the confirmation is unknown; it never says
    False from an empty list.
    """
    # [the owner's second answer of 2026-09-25: the placed marks — rasters, and marks drawn from the approved vector
    # master — through the ONE helper every reader shares; for a document with no such mark, logo_image_nodes]
    from apps.ire import brand_mark
    nodes = brand_mark.logo_nodes(doc)
    if not nodes:
        return None

    confirmed = {os.path.realpath(p) for p in confirmed_assets if p}
    placements, assets = [], {}
    for node in nodes:
        src = brand_mark.source_of(node)
        if brand_mark.is_mark(node):
            master = brand_mark.resolve(node.asset_id)
            if master is None:
                return None
            intrinsic, sha = (None, None, master.aspect), master.sha256
        else:
            intrinsic, sha = _intrinsic(src), None
        if intrinsic is None:
            return None
        width_px, height_px, intrinsic_aspect = intrinsic
        if src not in assets:
            assets[src] = {
                "path": src,
                "sha256": _sha256(src) if sha is None else sha,
                "intrinsic_px": [width_px, height_px] if sha is None else None,
                "intrinsic_aspect": round(intrinsic_aspect, 6),
                "owner_confirmed": (os.path.realpath(src) in confirmed
                                    if confirmed else None),
            }
        # A box with no width or height has no aspect. That is a MEASURED
        # defect, not an unmeasurable one, so it is named here rather than
        # falling out of a division guard as a plausible-looking 0.0.
        degenerate = node.w <= 0 or node.h <= 0
        rendered_aspect = None if degenerate else node.h / node.w
        deviation = (None if degenerate else
                     abs(rendered_aspect - intrinsic_aspect)
                     / intrinsic_aspect)
        clip_findings = _clip_findings(node, doc)
        placements.append({
            "node_name": str(getattr(node, "name", "") or ""),
            "src": src,
            "placed_mm": [round(node.x, 3), round(node.y, 3),
                          round(node.w, 3), round(node.h, 3)],
            "rendered_extent_pt": round(max(node.w, 0.0) * MM_TO_PT, 3),
            "rendered_height_pt": round(max(node.h, 0.0) * MM_TO_PT, 3),
            "rendered_aspect": (None if rendered_aspect is None
                                else round(rendered_aspect, 6)),
            "intrinsic_aspect": round(intrinsic_aspect, 6),
            "aspect_deviation": (None if deviation is None
                                 else round(deviation, 6)),
            "degenerate_box": degenerate,
            "materially_distorted": (True if degenerate
                                     else deviation > ASPECT_TOLERANCE),
            "clipped": bool(clip_findings),
            "clip_findings": clip_findings,
        })

    return {
        "schema_version": SCHEMA,
        "rendered_extent_pt": min(p["rendered_extent_pt"] for p in placements),
        "clipped": any(p["clipped"] for p in placements),
        "materially_distorted": any(p["materially_distorted"]
                                    for p in placements),
        "placement_count": len(placements),
        "placements": placements,
        "aspect_tolerance": ASPECT_TOLERANCE,
        "assets": [assets[k] for k in sorted(assets)],
        "measured_by": "apps.ire.container_logo_metrics.measure_logo_metrics",
    }
