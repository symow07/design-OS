"""Owner-authorized pipeline concept-selection ceremony
(pipeline_container_concept_selection/1.0, 2C-2D-CORR-2 §3).

Signs ONE chain-grade DecisionEvent that RECORDS the existing human Gate-1
concept selection — the GateDecision row and the hashed metadata record stay
the authoritative originals, untouched. The event authorizes nothing: the
action is not in ``authz.ACTIONS`` (no role can ever perform it), and the
payload signs an explicit non-authorization list covering profile
confirmation, zone confirmation, reconstruction, human design acceptance,
Gate 2, Packaging creation and production authority.

Idempotent: a re-run for the same task with the same decision identity
returns the existing event; a conflicting identity fails closed.
"""
from __future__ import annotations

import dataclasses

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts import bootstrap_registry as reg
from apps.accounts.bootstrap_environment import classify_environment
from apps.accounts.decision_chain import (
    _BOOTSTRAP_APPEND_TOKEN,
    append_pipeline_concept_selection_event,
)
from apps.accounts.models import (
    RESULT_ALLOWED,
    AuthorizationAudit,
    DecisionChainHead,
    DecisionEvent,
)
from apps.pipeline.services import selected_concept_contract as scc

CEREMONY_ENDPOINT = "cli:pipeline_container_concept_selection"
EVENT_META_KEY = "gate1_concept_selection_event"


class ConceptSelectionCeremonyError(RuntimeError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclasses.dataclass(frozen=True)
class CeremonyResult:
    status: str                    # PERFORMED | ALREADY_RECORDED
    event_id: str
    sequence_number: int


def record_concept_selection_event(*, task, actor) -> CeremonyResult:
    """Sign the SELECT_CONTAINER_CONCEPT record for ``task`` from its live
    records. Every referenced fact is read from the database — nothing is
    fabricated, nothing is rewritten."""
    from apps.pipeline.models import GateDecision, GeneratedImage

    if not actor.is_superuser or not actor.is_active:
        raise ConceptSelectionCeremonyError("ACTOR_NOT_SUPERUSER_OR_INACTIVE")
    project = task.project
    if project is None:
        raise ConceptSelectionCeremonyError(
            "TASK_HAS_NO_PROJECT", "the selection record is project-scoped")
    meta = project.metadata or {}
    record = meta.get(scc.SELECTION_META_KEY)
    contract = meta.get(scc.META_KEY)
    if not isinstance(record, dict) or not isinstance(contract, dict):
        raise ConceptSelectionCeremonyError(
            "SELECTION_RECORDS_MISSING",
            "gate1_concept_selection and the visual contract must exist first")
    if record.get("visual_contract_hash") != contract.get("contract_hash"):
        raise ConceptSelectionCeremonyError(
            "SELECTION_RECORDS_INCONSISTENT",
            "the metadata decision record does not pin this contract")
    gd = GateDecision.objects.filter(
        task=task, gate="gate_1", decision="approve").order_by(
        "-decided_at").first()
    if gd is None:
        raise ConceptSelectionCeremonyError(
            "GATE_DECISION_MISSING", "no gate_1 approval exists to record")
    selected_id = (record.get("selected") or {}).get("image_id")
    selected = GeneratedImage.objects.filter(pk=selected_id).first()
    if selected is None or not selected.is_approved:
        raise ConceptSelectionCeremonyError(
            "SELECTED_IMAGE_STATE_INVALID",
            "the recorded selected image must exist and be approved")

    try:
        direction_id = task.brief.selected_direction_id or ""
    except Exception:  # noqa: BLE001 — a task without a brief still records
        direction_id = ""

    with transaction.atomic():
        head = DecisionChainHead.objects.select_for_update().get(pk=1)
        now = timezone.now()
        classification, environment_evidence = classify_environment()
        payload = {
            "bootstrap_schema": reg.CONCEPT_SELECT_SCHEMA,
            "single_operator": True,
            "dual_control": False,
            "actor_user_id": actor.pk,
            "decision_code": reg.CONCEPT_SELECT_DECISION_CODE,
            "project_id": project.pk,
            "task_id": task.pk,
            "design_target": task.design_target,
            "selected_direction_id": direction_id,
            "selected_direction_name": selected.direction_name or "",
            "selected_image_id": selected.pk,
            "selected_variation_identity":
                (selected.reference_provenance or {}).get(
                    "variation_identity", ""),
            "unselected": record.get("unselected") or [],
            "gate_decision_id": gd.pk,
            "gate_decision_decided_at": gd.decided_at.isoformat(),
            "metadata_decision_record_hash": record.get("record_hash"),
            "visual_contract_schema": contract.get("schema_version"),
            "visual_contract_hash": contract.get("contract_hash"),
            "human_decided_at": record.get("decided_at"),
            "recorded_at": now.isoformat(),
            "signing_epoch": settings.DECISION_EVENT_ACTIVE_KEY_ID,
            "statements": list(reg.CONCEPT_SELECT_REQUIRED_STATEMENTS),
            "non_authorizations":
                list(reg.CONCEPT_SELECT_NON_AUTHORIZATIONS),
            "authorization_basis": reg.CONCEPT_SELECT_AUTHORIZATION_BASIS,
            "account_control_basis": reg.CONCEPT_SELECT_ACCOUNT_CONTROL_BASIS,
            "environment_classification": classification,
            "environment_evidence": environment_evidence,
            "observed_user_is_active": bool(actor.is_active),
            "observed_user_is_superuser": bool(actor.is_superuser),
        }
        already = DecisionEvent.objects.filter(
            action=reg.PIPELINE_CONTAINER_CONCEPT_SELECT,
            subject_type="DesignTask", subject_id=str(task.pk),
            superseded_by__isnull=True).exists()
        event = append_pipeline_concept_selection_event(
            capability=_BOOTSTRAP_APPEND_TOKEN, user=actor, payload=payload,
            head=head, now=now)
        status = "ALREADY_RECORDED" if already else "PERFORMED"

        # explicit lineage, additive — the original hashed record is untouched
        meta = dict(project.metadata or {})
        meta[EVENT_META_KEY] = {
            "event_id": event.event_id,
            "sequence_number": event.sequence_number,
            "action": event.action,
            "signing_epoch": event.signing_key_id,
            "recorded_at": (event.payload or {}).get("recorded_at"),
            "lineage": (f"GateDecision #{gd.pk} → DecisionEvent "
                        f"#{event.sequence_number} ({event.event_id})"),
        }
        project.metadata = meta
        project.save(update_fields=["metadata", "updated_at"])

        if status == "PERFORMED":
            AuthorizationAudit.objects.create(
                user=actor, action=reg.PIPELINE_CONTAINER_CONCEPT_SELECT,
                subject_type="DesignTask", subject_id=str(task.pk),
                result=RESULT_ALLOWED, reason_code="AUTHORIZED",
                active_roles=[], authorizing_roles=[],
                role_used=reg.BOOTSTRAP_OPERATOR,
                selection_rule=reg.CONCEPT_SELECT_AUTHORIZATION_BASIS,
                endpoint=CEREMONY_ENDPOINT, request_method="",
                metadata={
                    "severity": "CRITICAL",
                    "ceremony": reg.CONCEPT_SELECT_SCHEMA,
                    "decision_event_id": event.event_id,
                    "gate_decision_id": gd.pk,
                    "selected_image_id": selected.pk,
                })
        return CeremonyResult(status, event.event_id, event.sequence_number)


__all__ = ["CeremonyResult", "ConceptSelectionCeremonyError",
           "EVENT_META_KEY", "record_concept_selection_event"]
