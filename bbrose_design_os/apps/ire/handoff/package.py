"""Handoff package builder + structural validator (Phase 2A-8 §2/§12).

``build_handoff_package`` writes the deterministic package next to the
job's other exports: design_handoff.jsx, design_graph.json,
handoff_manifest.json, plus references to the existing preview/dieline
deliverables. ``validate_handoff`` compares Design Graph ↔ serialized graph
↔ expected layer tree ↔ (optionally) a real Illustrator inspection summary,
with the stable §12 failure codes. The PDF-compatible preview emitter is
untouched: the package is an ADDITIONAL, explicitly requested output.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from apps.ire.handoff.graph_schema import (
    HANDOFF_SCHEMA,
    NON_PRINTING_LAYERS,
    canonical_hash,
    expected_layer_tree,
    serialize_handoff_graph,
)
from apps.ire.handoff.jsx_emitter import EMITTER_VERSION, emit_design_handoff_jsx

MANIFEST_SCHEMA = "illustrator_handoff_manifest/1.0"

#: §12 stable codes.
HANDOFF_LAYER_TREE_MISMATCH = "HANDOFF_LAYER_TREE_MISMATCH"
HANDOFF_OBJECT_COUNT_MISMATCH = "HANDOFF_OBJECT_COUNT_MISMATCH"
HANDOFF_SWATCH_MISSING = "HANDOFF_SWATCH_MISSING"
HANDOFF_SPOT_COLOR_MISSING = "HANDOFF_SPOT_COLOR_MISSING"
HANDOFF_ORPHAN_SPOT_SWATCH = "HANDOFF_ORPHAN_SPOT_SWATCH"
HANDOFF_TEXT_OUTLINED = "HANDOFF_TEXT_OUTLINED"
HANDOFF_FONT_MISSING = "HANDOFF_FONT_MISSING"
HANDOFF_PANEL_ASSIGNMENT_MISMATCH = "HANDOFF_PANEL_ASSIGNMENT_MISMATCH"
HANDOFF_FINISH_LAYER_MISMATCH = "HANDOFF_FINISH_LAYER_MISMATCH"
HANDOFF_REFERENCE_LAYER_PRINTABLE = "HANDOFF_REFERENCE_LAYER_PRINTABLE"
HANDOFF_UNEXPECTED_RASTER = "HANDOFF_UNEXPECTED_RASTER"
ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED = \
    "ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED"


def build_handoff_package(doc, out_dir: str, *, task_id: int,
                          geometry_hash: str = "",
                          production_blockers: tuple = (),
                          logo_asset: str | None = None) -> dict:
    """Write the package; return {paths, hashes, manifest}.

    ``logo_asset``: the controlled BRAND_LOGO_RASTER_FALLBACK file — the one
    permitted linked asset (§2/§8); copied into ./assets so the script's
    bounded lookup resolves it. Nothing else ships.
    """
    import shutil
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    linked_assets: list[str] = []
    if logo_asset and Path(logo_asset).exists():
        assets = out / "assets"
        assets.mkdir(exist_ok=True)
        target = assets / Path(logo_asset).name
        shutil.copyfile(logo_asset, target)
        linked_assets.append(Path(logo_asset).name)
    graph = serialize_handoff_graph(doc, task_id=task_id)
    graph_hash = canonical_hash(graph)
    jsx = emit_design_handoff_jsx(graph)
    jsx_hash = hashlib.sha256(jsx.encode()).hexdigest()

    graph_path = out / "design_graph.json"
    graph_path.write_text(json.dumps(graph, indent=1, ensure_ascii=True))
    jsx_path = out / "design_handoff.jsx"
    jsx_path.write_text(jsx)

    layer_tree = expected_layer_tree(graph)
    tree_hash = hashlib.sha256(json.dumps(
        layer_tree, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "handoff_graph_schema": HANDOFF_SCHEMA,
        "emitter_version": EMITTER_VERSION,
        "task_id": task_id,
        "design_graph_hash": graph_hash,
        "geometry_hash": geometry_hash,
        "jsx_hash": jsx_hash,
        "layer_tree_hash": tree_hash,
        "fonts": graph["fonts"],
        "font_policy": ("fonts are REFERENCES to expected installed faces; "
                        "no font binaries ship in this package"),
        "process_swatches": [s["name"] for s in graph["process_swatches"]],
        "spot_swatches": [s["name"] for s in graph["spot_swatches"]],
        "expected_object_census": graph["object_census"],
        "expected_layer_tree": layer_tree,
        "linked_assets": sorted(linked_assets),
        "production_blockers": list(production_blockers),
        "execution_verification":
            ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED,
        "notes": graph["finish_note"],
    }
    manifest_path = out / "handoff_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=1,
                                        ensure_ascii=True))
    return {"graph": graph, "manifest": manifest,
            "paths": {"jsx": str(jsx_path), "graph": str(graph_path),
                      "manifest": str(manifest_path)},
            "hashes": {"graph": graph_hash, "jsx": jsx_hash,
                       "layer_tree": tree_hash}}


def _painted_swatch_names(graph: dict) -> set[str]:
    """Every swatch name a PRINTABLE object actually paints with.

    FOUR routes, because the serializer uses four: a stroke colour, a fill
    (solid or gradient stop), a **top-level** ``swatch`` on live text runs,
    and the ``finish`` tag.

    The text route was MISSED by the first version of this helper and found
    by audit. Text is the one object type whose colour is not nested under
    ``fill``/``stroke`` — ``_emit``'s TextRun branch in graph_schema sets
    ``swatch=`` directly on the record — so a spot ink used only for type
    read as unused, and the check would have reported a plate that prints.
    A false orphan is worse than the gap it closes: it teaches the reader to
    ignore the code.

    ``finish`` usually holds a finish spot name, but graph_schema assigns the
    raw group name with a ``14_TECHNICAL_NOTES`` fallback, so it is not
    guaranteed to be one. Harmless — callers intersect against the spot set.

    Non-printable objects are excluded on purpose: a reference halo that
    happens to name a plate does not make that plate print anything.

    Returns process names too; callers intersect against the spot set.
    """
    used: set[str] = set()
    for obj in graph.get("objects") or []:
        if not obj.get("printable"):
            continue
        stroke = obj.get("stroke") or {}
        if stroke.get("swatch"):
            used.add(stroke["swatch"])
        fill = obj.get("fill") or {}
        if fill.get("swatch"):
            used.add(fill["swatch"])
        for stop in fill.get("stops") or []:
            if stop.get("swatch"):
                used.add(stop["swatch"])
        if obj.get("swatch"):            # live text runs carry it flat
            used.add(obj["swatch"])
        if obj.get("finish"):
            used.add(obj["finish"])
    return used


def validate_handoff(doc, graph: dict, *,
                     illustrator_summary: dict | None = None) -> list[str]:
    """§12 structural validation. Empty list = consistent."""
    failures: list[str] = []
    regenerated = serialize_handoff_graph(
        doc, task_id=graph.get("task_id"))
    if canonical_hash(regenerated) != canonical_hash(graph):
        failures.append(HANDOFF_LAYER_TREE_MISMATCH
                        + ": serialized graph no longer matches the Design "
                          "Graph")
    # census: text runs, rasters, per-layer object counts
    doc_census = {"path": 0, "rect": 0, "text": 0, "image": 0}
    from apps.ire import brand_mark as _brand_mark
    for node, _parent in doc.walk():
        if node.type in doc_census:
            doc_census[node.type] += 1
        elif _brand_mark.is_mark(node):
            # [the owner's second answer of 2026-09-25: a mark drawn from its approved vector master is serialised
            # as the one path it draws]
            doc_census["path"] += 1
    graph_census = dict(graph.get("object_census") or {})
    # the serializer adds one derived bleed guide path (§3)
    if doc_census["path"] + 1 != graph_census.get("path", 0):
        failures.append(
            HANDOFF_OBJECT_COUNT_MISMATCH
            + f": document paths {doc_census['path']} (+1 derived guide) vs "
              f"graph {graph_census.get('path', 0)}")
    for name in ("WARM_IVORY_BASE",):
        if name not in {s["name"] for s in graph["process_swatches"]}:
            failures.append(HANDOFF_SWATCH_MISSING + f": {name}")
    required_spots = {"CUT", "CREASE", "SPOT_UV", "EMBOSS", "DEBOSS",
                      "ROSE_GOLD_FOIL"}
    have_spots = {s["name"] for s in graph["spot_swatches"]}
    for name in sorted(required_spots - have_spots):
        failures.append(HANDOFF_SPOT_COLOR_MISSING + f": {name}")
    # H020 (docs/design_intelligence/watch/ENGINE_HOOKS_BACKLOG.md, 6-source
    # convergence). The loop above is only the MISSING half of the contract.
    # The other half: the jsx emitter creates EVERY entry in spot_swatches
    # (jsx_emitter.py:100), so a spot swatch nothing paints with ships as an
    # EMPTY SEPARATION PLATE — the supplier mounts and bills a plate that
    # prints nothing.
    #
    # This is deliberately NOT container_adapter.py's `spot_set - used`.
    # There, both sides come from persisted records and vary with the data.
    # Here `required_spots` above is a local literal and SPOT_SWATCHES is a
    # module constant; they hold the SAME six names, and `have_spots` is
    # rebuilt verbatim from SPOT_SWATCHES on every serialize. So any
    # name-level difference is identically empty for every document, forever.
    # Usage is the only direction that can vary — so usage is what is checked.
    orphan_spots = have_spots - _painted_swatch_names(graph)
    if orphan_spots:
        failures.append(HANDOFF_ORPHAN_SPOT_SWATCH + ": "
                        + ",".join(sorted(orphan_spots)))
    for obj in graph["objects"]:
        if obj["type"] == "text" and not obj.get("live", False):
            failures.append(HANDOFF_TEXT_OUTLINED + f": {obj['name']}")
        if obj["type"] == "image" and obj["layer"] != "06_BRAND":
            failures.append(HANDOFF_UNEXPECTED_RASTER
                            + f": {obj['name']} on {obj['layer']}")
        if obj["layer"] in NON_PRINTING_LAYERS and obj.get("printable"):
            failures.append(HANDOFF_REFERENCE_LAYER_PRINTABLE
                            + f": {obj['name']}")
        if obj["layer"].startswith(("10_", "11_", "12_", "13_")) \
                and not obj.get("finish"):
            failures.append(HANDOFF_FINISH_LAYER_MISMATCH
                            + f": {obj['name']} carries no finish tag")
        if obj["layer"] == "05_PANEL_ARTWORK" and not obj.get("panel"):
            failures.append(HANDOFF_PANEL_ASSIGNMENT_MISMATCH
                            + f": {obj['name']}")

    if illustrator_summary is None:
        failures.append(ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED)
    else:
        if illustrator_summary.get("status") == "ILLUSTRATOR_FONT_MISSING":
            failures.append(
                HANDOFF_FONT_MISSING + ": "
                + ", ".join(illustrator_summary.get("missingFonts", [])))
        expected_layers = len(graph["root_layers"])
        if illustrator_summary.get("layers") != expected_layers:
            failures.append(
                HANDOFF_LAYER_TREE_MISMATCH
                + f": Illustrator created "
                  f"{illustrator_summary.get('layers')} root layers, "
                  f"expected {expected_layers}")
        expected_text = graph["object_census"].get("text", 0) \
            + sum(1 for o in graph["objects"]
                  if o["type"] == "sticker_bridge")
        if illustrator_summary.get("textFrames") != expected_text:
            failures.append(
                HANDOFF_OBJECT_COUNT_MISMATCH
                + f": Illustrator text frames "
                  f"{illustrator_summary.get('textFrames')} vs expected "
                  f"{expected_text}")
        for error in illustrator_summary.get("errors", []):
            failures.append(HANDOFF_OBJECT_COUNT_MISMATCH
                            + f": runtime error {error}")
    return failures


__all__ = ["build_handoff_package", "validate_handoff", "MANIFEST_SCHEMA",
           "HANDOFF_ORPHAN_SPOT_SWATCH",
           "ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED"]
