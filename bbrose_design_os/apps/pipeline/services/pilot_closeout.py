"""2C-2 live-pilot container-stage failure closeout (2026-07-27).

After three task-specific corrections the human's FINAL Gate-2 decision is
that the reconstruction engine cannot yet preserve selected concept #97
visually. That is a valid live-pilot FINDING: the orchestration, governance,
budgeting, gates and native infrastructure all passed; visual fidelity is
deferred to the FINAL VISUAL QUALITY AND CREATIVE PERFORMANCE PROGRAM. The
closeout is idempotent, preserves every output and decision immutably, and
leaves the task terminal-but-reviewable. Packaging is correctly prevented.
"""
from __future__ import annotations

FINAL_REJECTION_KEY = "container_reconstruction_rejected_2026_07_27_gate2_final"
RESULT_SCHEMA = "complete_product_live_pilot_stage_result/1.0"
RESULT_META_KEY = "complete_product_live_pilot_stage_result"
TERMINAL_STATUS = "container_stage_visually_rejected"
PROJECT_STATUS = "container_rejected"

FINAL_CODES = (
    "HUMAN_GATE2_VISUAL_REJECTION_FINAL",
    "SELECTED_CONTAINER_CONCEPT_NOT_PRESERVED",
    "CONTAINER_RECONSTRUCTION_ENGINE_VISUAL_FIDELITY_FAILED",
    "CONTAINER_CYLINDRICAL_FORM_NOT_PRESERVED",
    "CONTAINER_CLOSURE_VISUAL_FIDELITY_FAILED",
    "CONTAINER_GLASS_MATERIAL_REALIZATION_FAILED",
    "CONTAINER_PALETTE_FIDELITY_FAILED",
    "CONTAINER_PRODUCT_NAME_GROUPING_FAILED",
    "TASK_SPECIFIC_CORRECTION_LIMIT_REACHED",
)

FINAL_FINDINGS = (
    "the emitted bottle remains visually rectangular rather than cylindrical",
    "the broad flat shoulders do not preserve selected image #97",
    "the collar remains visually oversized and reads as a pink cap rather "
    "than polished rose-gold metal",
    "the pipette bulb remains broad, blunt and paddle-like rather than slim "
    "and tapered",
    "the neck-to-collar assembly remains schematic",
    "the glass material remains pale, flat and artificial",
    "the smoky dusty-rose palette is not preserved",
    "internal highlights read as vector panels rather than frosted-glass "
    "curvature",
    "Rose and Damascena remain visually separated rather than one unified "
    "product-name block",
    "the reconstruction remains a technical vector diagram rather than a "
    "faithful premium BBROSE container design",
)

STAGE_RESULT = {
    "orchestration": "PASS",
    "web_reference_governance": "PASS",
    "provider_budgeting_and_checkpointing": "PASS",
    "direction_selection_gate": "PASS",
    "gate1_concept_generation": "PASS",
    "profile_and_zone_confirmation": "PASS",
    "native_vector_infrastructure": "PASS",
    "automated_reconstruction_validation":
        "PASS TECHNICALLY / INVALIDATED VISUALLY",
    "human_selected_concept_fidelity": "FAIL",
    "human_gate2_acceptance": "REJECTED",
    "packaging_stage_creation": "CORRECTLY PREVENTED",
    "final_pilot_result": "CONTAINER_STAGE_FAILED_VISUAL_FIDELITY",
}


def close_container_stage(task, *, actor, now_iso) -> dict:
    """Perform (or idempotently return) the final closeout."""
    from apps.pipeline.models import AgentLog, GateDecision

    output = task.current_output()
    spec = output.spec_sheet or {}
    project = task.project
    if FINAL_REJECTION_KEY in spec:
        return spec[FINAL_REJECTION_KEY]      # idempotent — never duplicated

    record = {
        "schema_version": "container_gate2_rejection/1.0",
        "state": "REJECTED — FINAL for this pilot container stage",
        "decided_by": getattr(actor, "username", str(actor)),
        "decided_at": now_iso,
        "codes": list(FINAL_CODES),
        "final_visual_findings": list(FINAL_FINDINGS),
        "human_design_acceptance": "REJECTED",
        "revision_state": "DEFERRED_TO_FINAL_VISUAL_QUALITY_PROGRAM",
        "production_approval": "BLOCKED",
        "invalidation": "automated dimension and geometry passes do not "
                        "override this human decision",
        "rejected_output": {
            "design_preview_ai": output.design_preview_ai.name,
            "design_preview": output.design_preview.name},
    }
    spec[FINAL_REJECTION_KEY] = record
    output.spec_sheet = spec
    output.save(update_fields=["spec_sheet"])

    GateDecision.objects.create(
        task=task, gate="gate_2", decision="reject", decided_by=actor,
        notes="FINAL HUMAN GATE-2 VISUAL REJECTION — " + "; ".join(
            FINAL_CODES))
    AgentLog.objects.create(
        task=task, agent_name="ARIA", actor=actor, level="error",
        action=("Live pilot container stage CLOSED after the final human "
                "Gate-2 rejection — visual fidelity deferred to the Final "
                "Visual Quality Program; Packaging correctly prevented."),
        payload={"codes": list(FINAL_CODES)})

    task.status = TERMINAL_STATUS
    task.save(update_fields=["status", "updated_at"])

    if project is not None:
        meta = dict(project.metadata or {})
        meta[RESULT_META_KEY] = {
            "schema_version": RESULT_SCHEMA,
            "recorded_at": now_iso,
            "task_id": task.pk,
            "result": dict(STAGE_RESULT),
            "note": "a valid live-pilot finding, not a failed audit",
        }
        project.metadata = meta
        project.status = PROJECT_STATUS
        project.failed_stage = "container"
        project.save(update_fields=["status", "failed_stage", "metadata",
                                    "updated_at"])
    return record


__all__ = ["FINAL_CODES", "FINAL_FINDINGS", "FINAL_REJECTION_KEY",
           "RESULT_META_KEY", "RESULT_SCHEMA", "STAGE_RESULT",
           "TERMINAL_STATUS", "PROJECT_STATUS", "close_container_stage"]
