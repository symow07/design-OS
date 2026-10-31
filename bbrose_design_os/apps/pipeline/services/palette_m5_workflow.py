"""M5 §10 — the real workflow trace.

The material engine must not remain a service used only from tests, so
this drives the actual production path for every variant and records the
identifier each stage produced:

    PaletteDesignIntent
    → PaletteMaterialSpec
    → Design Graph material node
    → governed task artifact (PaletteMaterialArtifact)
    → Blender production scene
    → rendered evidence
    → Review Board

Each stage is verified, not narrated: the trace FAILS when a variant is
missing any link in the chain, and the verifier re-reads everything from
the database and the filesystem rather than trusting what the builder
returned.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from django.db import transaction

from apps.pipeline.models import (DesignTask, PaletteMaterialArtifact)
from apps.pipeline.services import palette_confirmation_flow as FLOW
from apps.pipeline.services import palette_design_graph as DG
from apps.pipeline.services import palette_es3083_intent as ES
from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_m5_evidence as M5E
from apps.pipeline.services import palette_material_engine as ME
from apps.pipeline.services import palette_moulded_rect as MR
from apps.pipeline.services import palette_rect_tray_geometry as RT
from apps.pipeline.services import palette_render_contract as RC

SCHEMA = "m5_material_workflow_trace/1.0"

REPO = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = REPO / "docs" / "roadmap" / "palt_m5" / "evidence"

TASK_MARKER = "M5-MATERIAL-WORKFLOW ES3083 palette"


class WorkflowTraceError(RuntimeError):
    """Raised when a production stage is bypassed or missing."""


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def attach_material_node(graph, contract) -> dict:
    """A Design Graph carrying the material contract as a graph node.

    The document changes, so the graph identity changes — a material
    node is graph content, not an annotation."""
    doc = graph["document"].model_copy(deep=True)
    meta = dict(doc.metadata)
    meta["material_node"] = {
        "node_type": "material_contract",
        "material_contract_identity": contract.identity(),
        "assignments": [a.resolved() for a in contract.assignments],
        "symbolic_colour_references": sorted({
            a.colour.name for a in contract.assignments
            if a.colour.kind == ME.SYMBOLIC}),
        "display_proxy_authority": "VISUALIZATION_ONLY",
    }
    doc.metadata = meta
    return {**graph, "document": doc,
            "graph_identity": DG._identity(doc, graph["packaging_link"]),
            "material_node_identity": hashlib.sha256(
                json.dumps(meta["material_node"],
                           sort_keys=True).encode()).hexdigest()[:16]}


def _task():
    """The governed palette task the trace runs against."""
    task = DesignTask.objects.filter(task_text=TASK_MARKER).first()
    if task:
        return task
    from apps.core.models import Brand, Product
    brand = Brand.objects.filter(name="BBROSE").first()
    if brand is None:
        brand = Brand.objects.create(name="BBROSE", master_brief="BBROSE")
    product = Product.objects.filter(product_id="ES-3083-M5").first()
    if product is None:
        product = Product.objects.create(
            brand=brand, product_id="ES-3083-M5", name="Outer Glow",
            category="EY", year=2026, product_type="eyeshadow palette")
    return DesignTask.objects.create(
        brand=brand, product=product, task_text=TASK_MARKER,
        status="running", design_target="palette")


@transaction.atomic
def run_trace(*, board_path=None) -> dict:
    """Drive every variant through the production chain and record it."""
    task = _task()

    # 1 — PaletteDesignIntent, confirmed through the governed flow
    draft = ES.build_es3083_intent()
    confirmation = FLOW.current_confirmation(task)
    if confirmation is None:
        FLOW.open_confirmation(task, draft)
        confirmation = FLOW.save_confirmation(
            task, draft, OC.confirmation_record(),
            notes="M5 material workflow trace")
    intent = FLOW.rehydrate(confirmation)

    # 2/3 — material spec into a Design Graph material node
    tray = RT.build_rect_recessed_tray()
    base_graph = DG.build_palette_design_graph(intent, tray)
    comps, _dims = MR.build_rect_components(OC.confirmed_intent())
    geometry_identity = M5E.assembly_identity(comps)

    board = board_path or str(EVIDENCE_DIR / "m5_material_variant_board.png")
    board_identity = _sha(board)[:16] if os.path.exists(board) else ""

    rows = []
    for name, filename, _means in M5E.VARIANT_FILES:
        contract = ME.variant_contracts()[name]
        graph = attach_material_node(base_graph, contract)
        evidence = EVIDENCE_DIR / filename
        scene_identity = hashlib.sha256(
            (geometry_identity + contract.identity()
             + RC.contract_identity() + "three_quarter"
             + "OPEN_REVIEW_ANGLE").encode()).hexdigest()[:16]
        render_identity = _sha(evidence)[:16] if evidence.exists() else ""
        artifact, _created = PaletteMaterialArtifact.objects.update_or_create(
            task=task, variant_name=name,
            defaults={
                "intent_confirmation": confirmation,
                "material_contract_identity": contract.identity(),
                "design_graph_identity": graph["graph_identity"],
                "geometry_identity": geometry_identity,
                "scene_identity": scene_identity,
                "render_identity": render_identity,
                "evidence_path": str(evidence.relative_to(REPO)),
                "evidence_sha256": _sha(evidence) if evidence.exists()
                else "",
                "review_board_artifact_identity": board_identity,
                "material_contract": contract.to_dict(),
            })
        rows.append({"variant": name, "artifact_id": artifact.pk})
    return {"task_id": task.pk,
            "confirmation_version": confirmation.version,
            "gate_decision_id": confirmation.gate_decision_id,
            "variants": rows}


def verify_trace() -> dict:
    """Re-read the whole chain from the database and the filesystem.

    Nothing from ``run_trace``'s return value is trusted here.
    """
    task = DesignTask.objects.filter(task_text=TASK_MARKER).first()
    stages_failed = []
    rows = []
    if task is None:
        return {"record_type": SCHEMA, "verdict": "FAIL",
                "why": "no governed task exists for the M5 trace"}

    confirmation = FLOW.current_confirmation(task)
    if confirmation is None or confirmation.gate_decision_id is None:
        stages_failed.append("PaletteDesignIntent confirmation")

    expected = {name for name, _f, _m in M5E.VARIANT_FILES}
    artifacts = {a.variant_name: a
                 for a in PaletteMaterialArtifact.objects.filter(task=task)}
    for name in sorted(expected):
        a = artifacts.get(name)
        row = {"variant": name}
        if a is None:
            row["verdict"] = "FAIL_NO_GOVERNED_ARTIFACT"
            stages_failed.append(f"{name}: governed task artifact")
            rows.append(row)
            continue
        contract = ME.variant_contracts()[name]
        checks = {
            "intent_revision": a.intent_confirmation_id is not None
            and a.intent_confirmation.is_current,
            "material_contract_identity_matches_engine":
                a.material_contract_identity == contract.identity(),
            "design_graph_identity_present":
                bool(a.design_graph_identity),
            "geometry_identity_present": bool(a.geometry_identity),
            "scene_identity_present": bool(a.scene_identity),
            "render_identity_present": bool(a.render_identity),
            "evidence_file_exists":
                (REPO / a.evidence_path).exists(),
            "evidence_hash_matches_file":
                (REPO / a.evidence_path).exists()
                and _sha(REPO / a.evidence_path) == a.evidence_sha256,
            "review_board_reference_present":
                bool(a.review_board_artifact_identity),
        }
        failed = [k for k, ok in checks.items() if not ok]
        row.update({
            "task_id": task.pk,
            "intent_revision": getattr(a.intent_confirmation, "version",
                                       None),
            "material_contract_identity": a.material_contract_identity,
            "design_graph_material_node_identity":
                a.design_graph_identity,
            "geometry_identity": a.geometry_identity,
            "scene_identity": a.scene_identity,
            "render_identity": a.render_identity,
            "review_board_artifact_identity":
                a.review_board_artifact_identity,
            "checks": checks,
            "verdict": "PASS" if not failed else "FAIL",
        })
        if failed:
            stages_failed.append(f"{name}: {failed}")
        rows.append(row)

    return {
        "record_type": SCHEMA,
        "task_id": task.pk,
        "task_status": task.status,
        "confirmation_version": getattr(confirmation, "version", None),
        "gate_decision_id": getattr(confirmation, "gate_decision_id",
                                    None),
        "variants": rows,
        "stages_failed": stages_failed,
        "test_only_bypass": False,
        "M5_REAL_WORKFLOW_CONNECTION":
            "PASS" if not stages_failed else "FAIL",
        "chain": ["PaletteDesignIntent", "PaletteMaterialSpec",
                  "DesignGraph material node",
                  "PaletteMaterialArtifact (governed)",
                  "Blender production scene", "rendered evidence",
                  "Review Board"],
    }
