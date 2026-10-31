"""§W3 — the ONE overlap rule, read by BOTH axes (``container_overlap/1.0``).

``blocking_overlaps`` on the composition axis and ``materially_overlapping``
on the typography axis were the same question asked twice, and both were
refused for the same reason: no committed record said which overlaps block.
OWNER_BLOCKER_CLEARANCE.md §W3 now says. It is ONE rule, so it lives in one
module and both axes import it — two copies would drift into disagreeing
about the same pair of runs, which is the failure this repo already avoids by
sharing ``_outside_artboard`` and ``_clip_bbox`` rather than restating them.

THE RULE IS THREE CLAUSES AND NOTHING ELSE:

* (a) TWO TEXT RUNS WHOSE GEOMETRY INTERSECTS BLOCK, at any opacity. Two
  names on top of each other is never intentional. Every node here carries
  ``opacity`` (``graph._NodeBase``), so the clause has something to bite on:
  it is recorded as evidence on each pair and is NEVER read as an exemption.
  A name hidden under another name at 5% is still two names.
* (b) TYPE OVER A RULE, MOTIF, MEDALLION OR COLOUR FIELD DOES NOT BLOCK. That
  is the composition working as drawn, and the A2 rosette and the FB3093 lids
  depend on it. Those overlaps are still COUNTED and reported, because a
  ``0`` from a reader that discriminated and a ``0`` from a reader that found
  nothing at all are different facts, and a record that cannot tell them
  apart cannot show the rule was applied.
* (c) CROSSING THE ARTBOARD EDGE blocks SEPARATELY and is already measured as
  ``elements_outside_artboard``. Nothing here folds it in — an element half
  off the page must not be re-reported as an overlap and counted twice.

§W3(d): a case that does not fit those three clauses cleanly is UNMEASURED
and blocking, and it goes back to the owner rather than being absorbed. One
such case is live — an obliquely rotated run, below.

SCOPE IS THE CONTAINER VIEW, and ``container_view_text_runs`` is reused
rather than a third scope invented. Overlap is a geometry-at-scale property,
like ``min_text_pt`` and unlike a placeholder: the surface strip draws the
other surfaces as a schematic, at diagram scale AND at diagram positions, so
two strip captions touching says nothing about what the container looks like.
§W1(c) — do not measure the strip harder — forbids answering it there. Runs
the emitter placed on two different surfaces cannot overlap in any case; they
are on different faces of the object.

Pure: no Django, no ORM, no network.
"""
from __future__ import annotations

SCHEMA = "container_overlap/1.0"

#: float noise in mm-space geometry, not a clearance allowance — matches the
#: logo, composition and typography producers. Boxes that merely ABUT are not
#: an intersection: two stacked lines of type whose extents meet exactly are
#: adjacent lines, which is how type is set.
_EPS_MM = 1e-6

#: DOMAIN: text-run rotation, in this module only, and it is a float-noise
#: allowance rather than a claim that a degree of rotation is negligible.
#: ``geometry_report._text_bbox_mm`` returns a box that IS the run's extent
#: only when the run is axis-aligned; off-axis it returns the unrotated box,
#: which is neither a subset nor a superset of the rotated glyphs. A run
#: authored at an angle sets a deliberate value, not 0.4 degrees.
_AXIS_TOLERANCE_DEG = 1.0

RULE = (
    "OWNER_BLOCKER_CLEARANCE.md §W3 — two text runs whose geometry "
    "intersects BLOCK, at any opacity; type set over a rule, motif, medallion "
    "or colour field does NOT block; crossing the artboard edge blocks "
    "separately as elements_outside_artboard. A case not fitting those three "
    "clauses cleanly is UNMEASURED and blocking (§W3(d)) and returns to the "
    "owner. The legibility-based variant — blocking only where an overlap "
    "materially impairs reading — was considered and is NOT available, "
    "because no instrument in this repo can measure 'impairs'."
)

_OBLIQUE_REASON = (
    "a container-view text run is set at an angle, and this repo cannot state "
    "its extent: geometry_report._text_bbox_mm returns the UNROTATED box for "
    "any rotation outside the axis-aligned cases, so neither an intersection "
    "nor the absence of one can be read off it. §W3(a) asks whether the "
    "geometry intersects; the geometry is not available for this run, so no "
    "count is supplied and the axis stays UNMEASURED (§W3(d)) rather than "
    "blocking on a box the emitter never drew. Runs affected: "
)


def _name(node) -> str:
    return str(getattr(node, "name", "") or "")


def _axis_aligned(node) -> bool:
    rotation = abs(float(getattr(node, "rotation_deg", 0.0) or 0.0)) % 90.0
    return min(rotation, 90.0 - rotation) <= _AXIS_TOLERANCE_DEG


def _intersection(a, b) -> tuple[float, float] | None:
    over_x = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    over_y = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    if over_x > _EPS_MM and over_y > _EPS_MM:
        return (over_x, over_y)
    return None


def _pair(node_a, box_a, node_b, box_b, overlap) -> dict:
    """Both members of an intersecting pair, with the evidence a reader needs
    to check the verdict: the boxes, how each extent was obtained (WI-F — a
    verdict from a guessed extent is a guessed verdict), and the opacities
    §W3(a) ruled irrelevant."""
    return {
        "nodes": [_name(node_a), _name(node_b)],
        "node_types": [getattr(node_a, "type", ""), getattr(node_b, "type", "")],
        "overlap_mm": [round(overlap[0], 3), round(overlap[1], 3)],
        "boxes_mm": [[round(v, 3) for v in box_a[:4]],
                     [round(v, 3) for v in box_b[:4]]],
        "extent_sources": [box_a[4], box_b[4]],
        "opacity": [float(getattr(node_a, "opacity", 1.0)),
                    float(getattr(node_b, "opacity", 1.0))],
    }


def measure_text_overlaps(doc) -> dict:
    """§W3 applied to an emitted Document's container view.

    Reports the blocking pairs, the runs the rule could not be applied to, and
    the type-over-artwork overlaps clause (b) ruled non-blocking. It does NOT
    decide the gate fields — ``blocking_overlap_count`` does, so that both
    axes derive their answer from the same function and cannot disagree.
    """
    from apps.ire.container_composition_metrics import _bbox, _emitted_surface
    from apps.ire.container_typography_metrics import container_view_text_runs
    from apps.ire.text_metrics import resolve_metric_faces, resolve_role_metrics

    role_metrics = resolve_role_metrics(resolve_metric_faces(doc.metadata))
    parents = {id(node): parent for node, parent in doc.walk()}
    runs = [node for node, _ in container_view_text_runs(doc)[0]]

    measurable, oblique = [], []
    for node in runs:
        if _axis_aligned(node):
            measurable.append((node, _bbox(node, role_metrics)))
        else:
            oblique.append({
                "node_name": _name(node),
                "rotation_deg": float(getattr(node, "rotation_deg", 0.0) or 0.0),
            })

    blocking = []
    for index, (node_a, box_a) in enumerate(measurable):
        for node_b, box_b in measurable[index + 1:]:
            hit = _intersection(box_a, box_b)
            if hit is not None:
                blocking.append(_pair(node_a, box_a, node_b, box_b, hit))

    artwork = []
    for node, _ in doc.walk():
        if getattr(node, "type", "") == "text":
            continue
        surface, true_scale = _emitted_surface(node, parents)
        # the strip's diagram furniture is not artwork the container's type
        # sits over; §W1's full-scale panel IS, and its keyline is exactly the
        # rule §W3(b) ruled type may be set over.
        if surface is not None and not true_scale:
            continue
        box = _bbox(node, role_metrics)
        if box is None:
            continue
        for run, run_box in measurable:
            hit = _intersection(run_box, box)
            if hit is not None:
                artwork.append(_pair(run, run_box, node, box, hit))

    return {
        "schema_version": SCHEMA,
        "blocking": blocking,
        "unmeasurable_runs": oblique,
        "non_blocking_over_artwork": artwork,
        "runs_examined": len(runs),
        "rule": RULE,
        "artboard_crossings_measured_separately": "elements_outside_artboard",
        "measured_by": "apps.ire.container_overlap.measure_text_overlaps",
    }


def blocking_overlap_count(record) -> int | None:
    """The number of blocking overlaps, or None when the rule could not be
    applied to every run and nothing it COULD be applied to blocked.

    A pair that blocks is reported even beside a run the rule could not reach:
    a positive finding is about the pair that was found, while a zero is a
    universal claim over every pair on the surface.
    """
    if record["blocking"]:
        return len(record["blocking"])
    return None if record["unmeasurable_runs"] else 0


def unmeasurable_reason(record) -> str:
    return _OBLIQUE_REASON + ", ".join(
        f"{r['node_name']} ({r['rotation_deg']}°)"
        for r in record["unmeasurable_runs"])


__all__ = ["SCHEMA", "RULE", "blocking_overlap_count", "measure_text_overlaps",
           "unmeasurable_reason"]
