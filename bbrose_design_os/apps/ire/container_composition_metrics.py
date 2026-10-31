"""VQR-3 — emitted composition metrics (``container_composition_metrics/1.0``).

``visual_quality_gate._composition_axis`` has read this contract since VQR-2A
and nothing has ever produced it, so the composition axis has been
permanently UNMEASURED — which is blocking. The gate reads three fields, and
only two of them can be measured today:

* ``elements_outside_artboard`` — MEASURED. The page IS the artboard, and
  leaving it is already a defect elsewhere in this codebase
  (``container_logo_metrics._clip_findings`` reports ``page_bounds``); that
  definition is reused rather than a second one invented.
* ``front_hierarchy_nonempty`` — MEASURED. Whether any artwork type tier
  reached the FRONT at all, which is the emptiness the gate calls a defect.
  Which surface a run sits on is read from the emitter's own ``Surface-*``
  group ancestry, never from the run's name: a back panel's INCI block is
  artwork type by every name-based test, and counting it would report a
  non-empty front hierarchy for a container whose front carries no type.
* ``blocking_overlaps`` — MEASURED SINCE §W3, by ``container_overlap``. It
  was absent because two elements overlapping is not a defect: the front
  composition draws a rule and sets type over it on purpose, and supplying
  ``0`` would have flipped the whole axis to PASS on a number nobody
  measured. §W3 ruled the line — type over type blocks, type over artwork
  does not — for BOTH axes at once, so the rule lives in one module and this
  one imports it rather than restating it. The count still goes absent, and
  the axis still stays UNMEASURED, where the rule cannot be applied to a run
  (§W3(d)).

The owner ruled on what blocks and the third field arrived without anything
else here moving, which is what the deliberate incompleteness was for.

TEXT EXTENTS CARRY THEIR OWN PROVENANCE (VQR-3 / WI-F). An artboard verdict
computed from a guessed extent is a guessed verdict, so every element records
how its extent was obtained and the record republishes the per-role font
provenance it measured with.

GROUP BOUNDS ARE NOT MEASURED and no group is treated as an element. A group
has no box of its own; giving it the union of its subtree would invent a
bound the emitter never drew.

Pure: no Django, no ORM, no network.
"""
from __future__ import annotations

SCHEMA = "container_composition_metrics/1.0"

#: float noise in mm-space geometry, not a placement allowance. Flush with
#: the trim is a placement; this only absorbs rounding.
_EPS_MM = 1e-6

#: nodes that carry their own box directly.
_BOXED_TYPES = ("rect", "image", "barcode", "asset_ref", "sticker_bridge")

#: nothing is permanently unmeasured here any more. §W3 supplied the overlap
#: ruling; what remains is per-document and is built by ``container_overlap``.


def _bbox(node, role_metrics):
    """``(x, y, w, h, extent_source)`` in document mm, or None for a node
    that has no box of its own (a group, or a path with no coordinates).

    ``_text_bbox_mm`` and ``_path_bbox`` are imported from the geometry
    report rather than reimplemented: the rotation and alignment contract for
    a text box is subtle, and two copies of it would drift into disagreeing
    about where the same run sits.
    """
    from apps.ire.geometry_report import _path_bbox, _text_bbox_mm

    kind = getattr(node, "type", "")
    if kind == "text":
        face, cap_em, measured = role_metrics.get(node.font) \
            or role_metrics.get("regular") or (None, 0.72, False)
        box = _text_bbox_mm(node, face, cap_em)
        source = "measured_text" if (face and measured) else "estimated_text"
        return (*box, source)
    if kind == "path":
        box = _path_bbox(node)
        return None if box is None else (*box, "geometry")
    if kind in _BOXED_TYPES:
        return (node.x, node.y, node.w, node.h, "geometry")
    return None


def _outside_artboard(box, page_w: float, page_h: float) -> bool:
    x, y, w, h = box[0], box[1], box[2], box[3]
    return (x < -_EPS_MM or y < -_EPS_MM
            or x + w > page_w + _EPS_MM or y + h > page_h + _EPS_MM)


def _emitted_surface(node, parents) -> tuple[str | None, bool]:
    """``(surface, true_scale)`` — the surface the EMITTER placed ``node`` on
    and whether it drew that surface at full size, or ``(None, False)`` when
    it placed the node outside every surface group.

    The nearest surface-group ancestor, never the node's own name: a reader
    that re-derived the surface from a node name would be guessing at what
    the emitter already states in its structure.

    Two prefixes, and telling them apart is §W1's whole subject. ``Surface-*``
    is the schematic strip's DIAGRAM of a surface, at map scale;
    ``TrueScaleSurface-*`` is the surface itself at its confirmed zone
    dimensions. A reader that could not distinguish them would either hold a
    thumbnail to a print floor — the sprint-7 1.5 pt finding — or exempt a
    real printed panel from the measurement §W1(b) requires of it. Callers get
    both facts and must decide; the surface alone is not enough to decide on.
    """
    from apps.ire.compose_container import (SURFACE_GROUP_PREFIX,
                                            TRUE_SCALE_SURFACE_PREFIX)

    cur = parents.get(id(node))
    while cur is not None:
        name = str(getattr(cur, "name", "") or "")
        if name.startswith(TRUE_SCALE_SURFACE_PREFIX):
            return name[len(TRUE_SCALE_SURFACE_PREFIX):], True
        if name.startswith(SURFACE_GROUP_PREFIX):
            return name[len(SURFACE_GROUP_PREFIX):], False
        cur = parents.get(id(cur))
    return None, False


def front_hierarchy_runs(doc) -> list:
    """The live text runs that are FRONT artwork type. Two exclusions, and
    neither is invented here:

    * SHEET FURNITURE — a spec label, a swatch caption, an SKU — by the same
      prefix set ``validate_typography_hierarchy`` excludes, so the two
      readers cannot disagree about what counts as type;
    * TYPE ON ANOTHER SURFACE. ``_surface_panels`` wraps every confirmed
      decoration surface EXCEPT the hero in a ``Surface-{name}`` group, so
      such an ancestor is the emitter saying this run is not on the front.
      Back-panel copy is artwork type and still not front hierarchy — without
      this a container whose front carried no type at all would report a
      non-empty front hierarchy off the back panel's INCI block.

    The second exclusion is on the SURFACE, not on the scale. §W1's full-scale
    back panel is more obviously not front type than the strip's diagram of it
    was, so drawing it at true size must not readmit it here.
    """
    from apps.ire.compose_container import HERO_SURFACE
    from apps.ire.container_motif_fidelity import NON_ARTWORK_TEXT_PREFIXES

    parents = {id(node): parent for node, parent in doc.walk()}
    return [node for node, _ in doc.walk()
            if getattr(node, "type", "") == "text"
            and not str(getattr(node, "name", "") or "").startswith(
                NON_ARTWORK_TEXT_PREFIXES)
            and _emitted_surface(node, parents)[0] in (None, HERO_SURFACE)]


def measure_composition_metrics(doc) -> dict | None:
    """``container_composition_metrics/1.0`` for an emitted Document, or None
    when the document has no drawable element to measure.

    None rather than a record of zeros: mirrors ``container_logo_metrics``,
    where an unreadable asset yields NO record. A record asserting nothing is
    outside an artboard nothing was drawn on is a measurement of nothing.
    """
    from apps.ire.container_overlap import (blocking_overlap_count,
                                            measure_text_overlaps,
                                            unmeasurable_reason)
    from apps.ire.text_metrics import (metrics_provenance,
                                       resolve_metric_faces,
                                       resolve_role_metrics)

    faces = resolve_metric_faces(doc.metadata)
    role_metrics = resolve_role_metrics(faces)

    elements, outside = 0, []
    for node, _ in doc.walk():
        box = _bbox(node, role_metrics)
        if box is None:
            continue
        elements += 1
        if _outside_artboard(box, doc.page_w, doc.page_h):
            outside.append({
                "node_name": str(getattr(node, "name", "") or ""),
                "node_type": node.type,
                "box_mm": [round(v, 3) for v in box[:4]],
                "extent_source": box[4],
            })
    if not elements:
        return None

    hierarchy = front_hierarchy_runs(doc)
    overlaps = measure_text_overlaps(doc)
    blocking = blocking_overlap_count(overlaps)
    unmeasured, reasons = [], {}
    if blocking is None:
        unmeasured.append("blocking_overlaps")
        reasons["blocking_overlaps"] = unmeasurable_reason(overlaps)
    return {
        "schema_version": SCHEMA,
        "elements_outside_artboard": len(outside),
        "front_hierarchy_nonempty": bool(hierarchy),
        **({"blocking_overlaps": blocking} if blocking is not None else {}),
        "overlap_rule": overlaps["rule"],
        "blocking_overlap_pairs": overlaps["blocking"],
        "overlaps_over_artwork_not_blocking": overlaps[
            "non_blocking_over_artwork"],
        "overlap_runs_examined": overlaps["runs_examined"],
        "overlap_unmeasurable_runs": overlaps["unmeasurable_runs"],
        "unmeasured": unmeasured,
        "unmeasured_reasons": reasons,
        "artboard_mm": [round(doc.page_w, 3), round(doc.page_h, 3)],
        "element_count": elements,
        "outside_elements": outside,
        "front_hierarchy": [str(getattr(r, "name", "") or "")
                            for r in hierarchy],
        "text_metrics_provenance": metrics_provenance(role_metrics),
        "measured_by": "apps.ire.container_composition_metrics"
                       ".measure_composition_metrics",
    }


__all__ = ["SCHEMA", "front_hierarchy_runs", "measure_composition_metrics"]
