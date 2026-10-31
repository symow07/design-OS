"""Motif fidelity for the native container reconstruction (Phase 2B-2A,
slice 2).

Measures the ACTUAL emitted motif geometry against ``container_motif_spec/1.0``
— never the declaration. The gate is deliberately the geometry, not the label:
the expected motif-node type (from the chosen ``DesignLanguage``) must actually
be present in the emitted Document. A SUPPORTED motif that rendered nothing, or
rendered the wrong family, fails; a first-pass concept with no motif is not
measured. Noisy INFERRED-local targets (centroid/density/coverage) are surfaced
as UNMEASURED, never gated against a pixel estimate (the packaging lesson:
measure geometry, but do not fail on noise).

Three-state per axis: MEASURED_PASS / MEASURED_FAIL / UNMEASURED.
"""
from __future__ import annotations

from apps.ire.container_motif import CAP_NONE, CAP_REVIEW_REQUIRED
from apps.ire.container_fidelity import (MEASURED_FAIL, MEASURED_PASS,
                                         UNMEASURED, UNMEASURED_BLOCKING)

# --- §4 stable codes ---------------------------------------------------------
MOTIF_FAMILY_MISMATCH = "CONTAINER_MOTIF_FAMILY_MISMATCH"
MOTIF_MISSING = "CONTAINER_MOTIF_MISSING"
MOTIF_DENSITY_FAILED = "CONTAINER_MOTIF_DENSITY_FAILED"
MOTIF_POSITION_FAILED = "CONTAINER_MOTIF_POSITION_FAILED"
MOTIF_COVERAGE_FAILED = "CONTAINER_MOTIF_COVERAGE_FAILED"
MOTIF_CONTINUATION_FAILED = "CONTAINER_MOTIF_CONTINUATION_FAILED"
MOTIF_COLOR_RELATIONSHIP_FAILED = "CONTAINER_MOTIF_COLOR_RELATIONSHIP_FAILED"

#: which emitted path-name prefixes each DesignLanguage produces — the honest
#: signature of a rendered family in the geometry (not its label).
_LANGUAGE_NODE_PREFIX = {
    "powder_constellation": ("particle-",),
    "dewdrop_constellation": ("dewdrop-",),
    "ruled_field": ("rule-",),
    "contour_terrain": ("contour-",),
    "liquid_veil": ("flow-line-", "ribbon-"),
    "petal_scatter": ("motif-",),
    "strata_field": ("strata-",),
    "quiet_ground": ("gradient-field",),
    # §BH65(c)4: the three new languages' node names — a LOOKUP ROW each, so the family check can find their
    # geometry; without them a concept routed to one would read MISMATCH over geometry it drew. No bar, axis or code.
    "engraved_field": ("engraved-",),
    "pattern_repeat": ("pattern-",),
    "halo_rings": ("halo-",),
    # §BH67(b)1: the petal bloom's node names — a lookup row, like §BH65(c)4's. No bar, axis or code.
    "petal_bloom": ("petal-",),
    # [the owner's second answer of 2026-09-25: "The lid is missing the concept's rule, ring and radial lines."] the
    # radial language's rays and nodes — a lookup row, like the petals'. No bar, axis or code. No node was named
    # "radial-" before it (searched), so the prefix claims no other family's geometry.
    "radial_lines": ("radial-",),
}
_ALL_MOTIF_PREFIXES = tuple(sorted(
    {p for prefixes in _LANGUAGE_NODE_PREFIX.values() for p in prefixes}))

#: live text that is SHEET FURNITURE, not front artwork type — a spec label,
#: a swatch caption, an SKU. Named once because two readers disagreeing about
#: what counts as artwork type is how a document with no product name comes
#: to report a non-empty hierarchy.
NON_ARTWORK_TEXT_PREFIXES = ("sheet-", "swatch-", "sku", "reference-",
                             "spec-")

# 2B-3V-CORR-3 §8/§11 stable codes
MOTIF_SCALE_DISTRIBUTION_FAILED = "CONTAINER_MOTIF_SCALE_DISTRIBUTION_FAILED"
SELECTED_CONCEPT_FIDELITY_FAILED = "SELECTED_CONTAINER_CONCEPT_FIDELITY_FAILED"
TYPOGRAPHY_HIERARCHY_FAILED = "CONTAINER_TYPOGRAPHY_HIERARCHY_FAILED"
PRODUCT_NAME_TOO_SMALL = "CONTAINER_PRODUCT_NAME_TOO_SMALL"


def _axis(state, *, code="", detail=""):
    return {"state": state, "code": code, "detail": detail}


def _path_bbox(path):
    """RECORDED, NOT FIXED (WI-L / §Z4). A second copy of what
    ``geometry_report._path_bbox`` used to be, and it still ignores stroke
    width: a hairline measures zero height here.

    §Z4 named the geometry-report helper and ``elements_outside_artboard``.
    It did not name this one, and the two now disagree — on the powder
    constellation's 104 particles, on the 17 stroked `tick` marks. Fixing it
    would move ``dewdrop_census``'s size_min/size_max, which a
    ``size_max < size_min * 1.8`` threshold turns into
    MOTIF_SCALE_DISTRIBUTION_FAILED, and ``container_quant_fidelity``'s ink
    coverage ratio: gate axes the ruling did not cover, and §Y4's stated
    reason for deferring this fix in the first place. It goes to the owner
    sheet with the numbers rather than into this commit.
    """
    xs, ys = [], []
    for seg in path.segments:
        for attr in ("x", "x1", "x2"):
            v = getattr(seg, attr, None)
            if v is not None:
                xs.append(float(v))
        for attr in ("y", "y1", "y2"):
            v = getattr(seg, attr, None)
            if v is not None:
                ys.append(float(v))
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def _motif_paths(doc, prefixes):
    return [n for n, _ in doc.walk()
            if n.type == "path"
            and str(getattr(n, "name", "")).startswith(prefixes)]


def measure_motif(doc, prefixes=_ALL_MOTIF_PREFIXES) -> dict:
    """Count + bounding + centroid (document mm) of the emitted motif nodes."""
    paths = _motif_paths(doc, tuple(prefixes))
    boxes = [b for b in (_path_bbox(p) for p in paths) if b]
    count = len(paths)
    if not boxes:
        return {"count": count, "centroid": None, "bounding": None}
    cx = sum(b[0] + b[2] / 2.0 for b in boxes) / len(boxes)
    cy = sum(b[1] + b[3] / 2.0 for b in boxes) / len(boxes)
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return {"count": count, "centroid": {"x": round(cx, 2), "y": round(cy, 2)},
            "bounding": (round(x0, 2), round(y0, 2),
                         round(x1 - x0, 2), round(y1 - y0, 2))}


def validate_motif_fidelity(doc, motif_spec: dict) -> dict:
    """Three-state motif-fidelity report over the emitted ``doc`` vs the spec.

    * capability NONE           → no motif expected; overall UNMEASURED
    * capability REVIEW_REQUIRED → gated elsewhere (fail-closed motif); here
                                   UNMEASURED so it is not double-counted
    * capability SUPPORTED       → the expected motif node type MUST be present
                                   (else MOTIF_MISSING / MOTIF_FAMILY_MISMATCH);
                                   noisy INFERRED targets stay UNMEASURED
    """
    axes: dict[str, dict] = {}
    # [his answer after test day finding 3, 2026-09-30, transcribed at 23d4375: the design drawn from its picture, "the
    # same way"] a front drawn from its concept's map draws the PICTURE's motif — on 117 its drips, where the concept's
    # words asked for a powder constellation — so the motif expected is the one it says it drew, and the family the
    # words requested is said beside it, set aside
    from_map = (getattr(doc, "metadata", None) or {}).get("map_front") or {}
    if from_map.get("motif_prefixes"):
        drawn = measure_motif(doc, tuple(from_map["motif_prefixes"]))
        axes["motif_family"] = (_axis(MEASURED_PASS) if drawn["count"] else _axis(
            MEASURED_FAIL, code=MOTIF_MISSING, detail="the concept's map names a motif and none of its geometry "
                                                      "was emitted"))
        for axis in ("motif_density", "motif_position", "motif_coverage", "motif_continuation"):
            axes[axis] = _axis(UNMEASURED)
        report = _summarise(axes, drawn)
        report["from_the_picture"] = {"drawn": list(from_map.get("drawn") or []),
                                      "words_requested": motif_spec.get("requested_family"),
                                      "set_aside_by": "his answer after test day finding 3 (transcribed at 23d4375)"}
        if report["failures"]:
            report["failures"].append(SELECTED_CONCEPT_FIDELITY_FAILED)
        return report
    cap = motif_spec.get("reconstruction_capability")
    if cap in (CAP_NONE, CAP_REVIEW_REQUIRED, None):
        axes["motif_family"] = _axis(UNMEASURED)
        return _summarise(axes, measure_motif(doc))

    # 2B-3V-CORR-3 §11: the expectation comes from the REQUESTED FAMILY's
    # honest generator mapping, never from whatever happened to render — a
    # ruled field emitted for a dewdrop family fails here on geometry, and
    # approximate-family metadata alone can never produce MEASURED_PASS.
    from apps.ire.container_motif import _FAMILY_TO_LANGUAGE
    rendered_via = motif_spec.get("rendered_via") or ""
    family = motif_spec.get("requested_family") or ""
    family_language = _FAMILY_TO_LANGUAGE.get(family, rendered_via)
    expected = _LANGUAGE_NODE_PREFIX.get(family_language, ())
    any_motif = measure_motif(doc)
    expected_measure = measure_motif(doc, expected) if expected else {"count": 0}

    if any_motif["count"] == 0:
        axes["motif_family"] = _axis(MEASURED_FAIL, code=MOTIF_MISSING,
                                     detail="a supported motif was authored but "
                                            "no motif geometry was emitted")
    elif expected_measure["count"] == 0:
        axes["motif_family"] = _axis(
            MEASURED_FAIL, code=MOTIF_FAMILY_MISMATCH,
            detail=f"the requested family {family!r} expects "
                   f"{family_language!r} geometry ({expected}); the emitted "
                   "motif nodes carry a different family's geometry")
    else:
        axes["motif_family"] = _axis(MEASURED_PASS)

    # §8: droplet families additionally validate droplet-specific geometry —
    # kind mix, scale spread, vertical sparse→dense movement, regional density.
    if family_language == "dewdrop_constellation":
        axes.update(_dewdrop_axes(doc))
    else:
        for axis in ("motif_density", "motif_position"):
            axes[axis] = _axis(UNMEASURED)
    # noisy INFERRED-local targets stay unmeasured (never gated on pixels)
    for axis in ("motif_coverage", "motif_continuation"):
        axes.setdefault(axis, _axis(UNMEASURED))
    report = _summarise(axes, expected_measure if expected else any_motif)
    if report["failures"]:
        report["failures"].append(SELECTED_CONCEPT_FIDELITY_FAILED)
    return report


def dewdrop_census(doc) -> dict:
    """§8: census of the ACTUAL emitted dewdrop geometry, by node name."""
    paths = _motif_paths(doc, ("dewdrop-",))
    kinds = {"teardrop": 0, "bead": 0, "elongated": 0, "sparkle": 0,
             "highlight": 0}
    sizes: list[float] = []
    core_y: list[float] = []
    drift_y: list[float] = []
    for p in paths:
        name = str(getattr(p, "name", ""))
        for kind in kinds:
            if name.endswith(kind) or f"-{kind}" in name \
                    or name.startswith(f"dewdrop-{kind}"):
                kinds[kind] += 1
                break
        box = _path_bbox(p)
        if box:
            sizes.append(max(box[2], box[3]))
            if "-core-" in name:
                core_y.append(box[1] + box[3] / 2.0)
            elif "-drift-" in name:
                drift_y.append(box[1] + box[3] / 2.0)
    droplet_count = kinds["teardrop"] + kinds["bead"] + kinds["elongated"]
    return {"paths": len(paths), "kinds": kinds,
            "droplet_count": droplet_count,
            "size_min": round(min(sizes), 2) if sizes else None,
            "size_max": round(max(sizes), 2) if sizes else None,
            "core_mean_y": round(sum(core_y) / len(core_y), 2) if core_y else None,
            "drift_mean_y": round(sum(drift_y) / len(drift_y), 2) if drift_y else None,
            "core_count": len(core_y), "drift_count": len(drift_y)}


def _dewdrop_axes(doc) -> dict:
    """§8 droplet-specific measured axes (geometry, not labels)."""
    c = dewdrop_census(doc)
    axes: dict[str, dict] = {}
    kind_variety = sum(1 for k in ("teardrop", "bead", "elongated")
                       if c["kinds"][k] > 0)
    if c["droplet_count"] < 8 or kind_variety < 2:
        axes["motif_density"] = _axis(
            MEASURED_FAIL, code=MOTIF_DENSITY_FAILED,
            detail=f"{c['droplet_count']} droplet(s) across {kind_variety} "
                   "kind(s) — a dewdrop constellation needs a varied field")
    else:
        axes["motif_density"] = _axis(MEASURED_PASS)
    # scale spread: three size classes need a real min→max spread
    if c["size_min"] is None or c["size_max"] < c["size_min"] * 1.8:
        axes["motif_scale"] = _axis(
            MEASURED_FAIL, code=MOTIF_SCALE_DISTRIBUTION_FAILED,
            detail=f"droplet sizes {c['size_min']}–{c['size_max']}mm do not "
                   "form distinct size classes")
    else:
        axes["motif_scale"] = _axis(MEASURED_PASS)
    # vertical sparse→dense movement: dense core sits ABOVE the sparse drift
    if c["core_mean_y"] is None or c["drift_mean_y"] is None \
            or not (c["core_mean_y"] < c["drift_mean_y"]
                    and c["core_count"] > c["drift_count"]):
        axes["motif_position"] = _axis(
            MEASURED_FAIL, code=MOTIF_POSITION_FAILED,
            detail="the dense cluster does not sit above the sparse drift — "
                   "no vertical sparse→dense movement")
    else:
        axes["motif_position"] = _axis(MEASURED_PASS)
    return axes


def validate_typography_hierarchy(doc, product_name: str) -> dict:
    """§7: the emitted TYPE must carry the hierarchy — the product name
    visibly dominant over supporting copy — not merely exist."""
    runs = [n for n, _ in doc.walk() if n.type == "text"]
    name_token = (product_name or "").split()[0].lower() if product_name else ""
    # a run is the product name when its TEXT carries the name token; once
    # the name is genuinely present, sibling runs carrying the canonical
    # product-name node marker EXTEND the set — a multi-line name
    # ("Rose" / "Damascena") must never count its own second line as
    # competing supporting copy (2C-2E-CORR-1). The marker alone never
    # substitutes for the text: an absent name still fails.
    #
    # THE MARKER IS PANEL-QUALIFIED, AND 2C-2E-CORR-1 ONLY HALF-FIXED IT.
    # Node names are built as ``prefix + base``, and the concept sheet draws
    # the front TWICE: once unprefixed (panel 5) and once as a true-scale
    # specimen with ``prefix="flat-"`` (panel 8). CORR-1 matched the marker
    # with ``startswith("product-name")``, which sees ``product-name-hero-1``
    # and misses ``flat-product-name-hero-1`` — so the specimen's SECOND name
    # line fell through to `other` and became "competing supporting copy",
    # the precise thing the paragraph above says must never happen. Its
    # sibling ``flat-product-name-hero-0`` escaped only by accident, because
    # its TEXT is "Rose" and the token test caught it: the two lines of one
    # block were landing on opposite sides of the classifier.
    #
    # It was invisible while panel 8 was set 2.5 pt smaller than panel 5. The
    # gate passed because the misclassified line happened to be shorter than
    # the name, not because it was classified correctly. §AB2(d) ruled one
    # spelling at 9.0 pt, the two sizes became equal, and `name_size <=
    # max(support)` fired with the name compared against ITSELF. The ruling
    # did not create this defect; it removed the coincidence that hid it.
    #
    # A panel prefix always ends in "-", so the marker is exact at the start
    # of the node name or immediately after a prefix. This does NOT weaken
    # the gate — a genuinely undersized name still fails, and that is
    # asserted directly rather than assumed.
    def _carries_name_marker(run) -> bool:
        node = str(getattr(run, "name", ""))
        return node.startswith("product-name") or "-product-name" in node

    token_runs = [r for r in runs
                  if name_token and name_token in str(r.text or "").lower()]
    name_runs = ([r for r in runs
                  if r in token_runs or _carries_name_marker(r)]
                 if token_runs else [])
    other = [r for r in runs if r not in name_runs
             and not str(getattr(r, "name", "")).startswith(
                 NON_ARTWORK_TEXT_PREFIXES)]
    axes: dict[str, dict] = {}
    # [his answer after test day finding 3, (3): "the script lettering also traced from the picture"] a name drawn as
    # the picture's traced lettering, its words the record's name, is the name at the size a typed name filling its
    # place takes — read before the sheet's own title can stand in for it
    # [his test blocker on design 124, 2026-10-11] … or the start of the record's name, the line the composer takes as
    # the name (124's "Enchanted Rose" of "Enchanted Rose Palette" was drawn as its name and this check, asking for the
    # whole name, measured the sheet's title instead and refused the drawing)
    from apps.ire.container_fidelity import spells_the_name, traced_name
    traced = traced_name(doc)
    if traced is not None and spells_the_name(traced.get("words"), product_name):
        support = [float(r.size_pt or 0) for r in runs if not str(getattr(r, "name", "")).startswith(
            NON_ARTWORK_TEXT_PREFIXES) and not _carries_name_marker(r)]
        axes["product_name"] = (_axis(MEASURED_PASS) if not support or traced["size_pt"] > max(support) else _axis(
            MEASURED_FAIL, code=PRODUCT_NAME_TOO_SMALL,
            detail=f"the traced name {traced['size_pt']}pt does not dominate supporting copy ({max(support)}pt)"))
        report = _summarise(axes, {"text_runs": len(runs), "traced_name": True})
        if report["failures"]:
            report["failures"].append(SELECTED_CONCEPT_FIDELITY_FAILED)
        return report
    if not name_runs:
        axes["product_name"] = _axis(
            MEASURED_FAIL, code=TYPOGRAPHY_HIERARCHY_FAILED,
            detail=f"no live text run carries the product name "
                   f"{product_name!r}")
    else:
        name_size = max(float(r.size_pt or 0) for r in name_runs)
        support = [float(r.size_pt or 0) for r in other]
        if support and name_size <= max(support):
            axes["product_name"] = _axis(
                MEASURED_FAIL, code=PRODUCT_NAME_TOO_SMALL,
                detail=f"product name {name_size}pt does not dominate "
                       f"supporting copy ({max(support)}pt)")
        else:
            axes["product_name"] = _axis(MEASURED_PASS)
    report = _summarise(axes, {"text_runs": len(runs)})
    if report["failures"]:
        report["failures"].append(SELECTED_CONCEPT_FIDELITY_FAILED)
    return report


def _summarise(axes: dict, measure: dict) -> dict:
    failures = [a["code"] for a in axes.values()
                if a["state"] == MEASURED_FAIL and a["code"]]
    counts = {
        "measured_pass": sum(1 for a in axes.values() if a["state"] == MEASURED_PASS),
        "measured_fail": sum(1 for a in axes.values() if a["state"] == MEASURED_FAIL),
        "unmeasured": sum(1 for a in axes.values() if a["state"] == UNMEASURED),
    }
    # §BH50(f)(5): a pass never outvotes an unmeasured axis — the motif
    # summary read MEASURED_PASS over four UNMEASURED axes on task 52 and the
    # board printed it. A measured pass beside an unmeasured axis reads
    # UNMEASURED_BLOCKING (the VQR-2A rule the base report already keeps);
    # every axis unmeasured stays UNMEASURED; the unmeasured axes block
    # acceptance through readiness and never the reconstruction, which reads
    # only ``failures``.
    overall = (MEASURED_FAIL if counts["measured_fail"]
               else UNMEASURED_BLOCKING
               if counts["measured_pass"] and counts["unmeasured"]
               else (MEASURED_PASS if counts["measured_pass"] else UNMEASURED))
    return {"axes": axes, "counts": counts, "overall": overall,
            "failures": failures, "measure": measure}


__all__ = [
    "measure_motif", "validate_motif_fidelity", "dewdrop_census",
    "validate_typography_hierarchy",
    "MOTIF_FAMILY_MISMATCH", "MOTIF_MISSING", "MOTIF_DENSITY_FAILED",
    "MOTIF_POSITION_FAILED", "MOTIF_COVERAGE_FAILED",
    "MOTIF_CONTINUATION_FAILED", "MOTIF_COLOR_RELATIONSHIP_FAILED",
    "MOTIF_SCALE_DISTRIBUTION_FAILED", "SELECTED_CONCEPT_FIDELITY_FAILED",
    "TYPOGRAPHY_HIERARCHY_FAILED", "PRODUCT_NAME_TOO_SMALL",
]
