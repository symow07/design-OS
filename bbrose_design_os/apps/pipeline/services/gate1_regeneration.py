"""Reference-grounded Gate-1 regeneration (Phase 2A-6E §6–§8).

Task #50's first Gate-1 set was rejected by the user as three cosmetic
variations of one near-empty layout. This service regenerates the Gate-1
set for the SAME selected direction — the Creative Director is never rerun
and the direction selection never changes — grounded in the user-approved
concept references and their influence plan, with the visual-richness
directives below and a deterministic variation-diversity gate that runs
BEFORE any image spend.

Refusal codes (checked synchronously, before anything is queued):
    REGEN_NOT_AT_GATE1            task is not at awaiting_gate_1
    REGEN_NO_APPROVED_REFERENCES  fewer than 2 approved concept references
    REGEN_NO_INFLUENCE_PLAN       no material_influence_plan/1.0 persisted
"""
from __future__ import annotations

from django.db import transaction

REGEN_NOT_AT_GATE1 = "REGEN_NOT_AT_GATE1"
REGEN_NO_APPROVED_REFERENCES = "REGEN_NO_APPROVED_REFERENCES"
REGEN_NO_INFLUENCE_PLAN = "REGEN_NO_INFLUENCE_PLAN"

#: §6 + §7: the visual-richness reinterpretation and the three mandated
#: variation identities, threaded to the Prompt Engineer as revision
#: feedback. The selected direction's axis stays; emptiness does not.
GATE1_RICHNESS_DIRECTIVES = """
REINTERPRET the selected direction as refined editorial packaging with
CONTROLLED ARTISTIC RICHNESS. Typography remains the primary system, but the
design must no longer be empty or generic: use roughly 15-20% of the front
panel for controlled decorative artwork (layered editorial color fields,
refined micro-patterns, powder-particle constellations, abstract radiance
lines, fine contour structures, tonal framing, subtle geometric
interruptions, asymmetric side bands, embossed vector details, restrained
gold-stamping, deliberate secondary typography, panel-continuation
elements). NEVER: one isolated curved line as the entire artistic system,
nearly blank pale backgrounds, photography, raster texture, full-face
decorative fields, dominant black/navy/dark-brown, or floral imagery beyond
what the approved references support.

The three variations must be MATERIALLY different — different product-name
placement, logo placement, color-field structure, decorative motif,
Spanish-copy placement, panel rhythm and finishing emphasis — never three
cosmetic variations of one layout:

VARIATION A — EDITORIAL PANEL: oversized condensed typography; an asymmetric
vertical secondary color panel with a controlled micro-pattern inside or
beside it; BBROSE placed with stronger brand authority; blush, ivory and
rose-gold; ~15% decorative coverage.

VARIATION B — LAYERED TYPE FIELD: layered BAKED POWDER typography with
controlled depth over one tonal background block; fine radiance lines or a
contour system; the Spanish copy integrated intentionally (never tiny footer
text); light sky blue or pale peach as a secondary field; ~15-20% coverage;
a different hierarchy from Variation A.

VARIATION C — POWDER CONSTELLATION: editorial product-name hierarchy; a
sparse but visually meaningful powder-particle constellation concentrated in
one corner or edge, subtly continuing toward one side panel; warm ivory,
light peach and soft mint or blush; restrained spot-UV and embossing; ~15-20%
coverage; no single arc as the complete motif.
"""


class GateRegenerationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def ensure_reference_refresh_enabled():
    """The legacy paid route remains closed until its prompts are target-aware."""
    raise GateRegenerationError(
        "REFERENCE_REFRESH_PAUSED",
        "Reference refresh is paused while it is updated to respect the product, "
        "colours and artwork in your brief. Your existing concepts and approved "
        "references are kept. No new generation has started.")


def check_regeneration_ready(task):
    """The synchronous refusal gate. Returns (approved_rows, plan) or raises
    with a stable code."""
    from apps.pipeline.services.concept_references import (
        APPROVE_MIN, approved_references)

    if task.status != "awaiting_gate_1":
        raise GateRegenerationError(
            REGEN_NOT_AT_GATE1,
            f"reference-grounded regeneration requires awaiting_gate_1; "
            f"task is {task.status!r}")
    approved = approved_references(task)
    if len(approved) < APPROVE_MIN:
        raise GateRegenerationError(
            REGEN_NO_APPROVED_REFERENCES,
            f"{len(approved)} approved concept reference(s); at least "
            f"{APPROVE_MIN} are required — approve references first")
    plan = getattr(task, "concept_influence_plan", None)
    if plan is None:
        raise GateRegenerationError(
            REGEN_NO_INFLUENCE_PLAN,
            "no influence plan persisted — approve references first")
    return approved, plan


#: [his final goal, 2026-10-05, B4] the same richness when the three variations are the three planned directions —
#: one for each, in order — before he has picked one
GATE1_DIRECTIONS_RICHNESS_DIRECTIVES = GATE1_RICHNESS_DIRECTIVES.replace(
    "REINTERPRET the selected direction as",
    "REINTERPRET each of the three planned directions — ONE variation for each, in order — as")
assert GATE1_DIRECTIONS_RICHNESS_DIRECTIVES != GATE1_RICHNESS_DIRECTIVES

#: The three mandated variation identities (§7) — bound to every job so the
#: worker and the audit trail agree on what was requested.
VARIATION_IDENTITIES = ["A_EDITORIAL_PANEL", "B_LAYERED_TYPE_FIELD",
                        "C_POWDER_CONSTELLATION"]


@transaction.atomic
def request_gate1_regeneration(task, user) -> dict:
    """Create (or return) THE ONE active regeneration job for this task and
    enqueue the worker exactly once (2A-6E-CORR-2 §4). Repeated clicks are
    idempotent: an active job is returned as-is, never duplicated. Nothing
    is generated inside this transaction."""
    from apps.pipeline.models import AgentLog, DesignTask, Gate1RegenerationJob

    ensure_reference_refresh_enabled()
    task = DesignTask.objects.select_for_update().get(pk=task.pk)
    active = (Gate1RegenerationJob.objects
              .filter(task=task,
                      status__in=Gate1RegenerationJob.ACTIVE_STATUSES)
              .first())
    if active is not None:
        return {"accepted": True, "job_id": active.pk,
                "status": active.status,
                "celery_task_id": active.celery_task_id,
                "reference_ids": active.approved_reference_ids,
                "influence_plan_hash": active.influence_plan_hash,
                "already_active": True}

    approved, plan = check_regeneration_ready(task)
    from apps.pipeline.models import CreativeBrief
    brief = CreativeBrief.objects.filter(task=task).first()
    if brief is None or not brief.directions:
        raise GateRegenerationError(
            REGEN_NOT_AT_GATE1, "no direction plan to regenerate for")
    # [his final goal, 2026-10-05, B4: "Three truly different concepts drawn straight away ... He picks a picture."]
    # before he picks a picture no direction is chosen: the job ("" — every planned direction) draws the three again,
    # one for each, grounded in his references
    direction_id = brief.selected_direction_id

    job = Gate1RegenerationJob.objects.create(
        task=task, direction_id=direction_id,
        approved_reference_ids=[r.pk for r in approved],
        influence_plan_hash=plan.plan_hash,
        variation_identities=list(VARIATION_IDENTITIES),
        created_by=user)
    AgentLog.objects.create(
        task=task, agent_name="ARIA", actor=user,
        action=(f"Reference-grounded Gate-1 regeneration job {job.pk} "
                f"created by {user.username} with {len(approved)} approved "
                f"concept reference(s)"),
        payload={"job_id": job.pk,
                 "approved_reference_ids": job.approved_reference_ids,
                 "influence_plan_hash": job.influence_plan_hash,
                 "variation_identities": job.variation_identities},
    )
    task.status = "queued"
    task.save(update_fields=["status"])

    def _enqueue():
        from apps.pipeline.tasks import regenerate_gate1_references
        result = regenerate_gate1_references.delay(job.pk)
        Gate1RegenerationJob.objects.filter(pk=job.pk).update(
            celery_task_id=str(result.id))

    transaction.on_commit(_enqueue)
    return {"accepted": True, "job_id": job.pk, "status": job.status,
            "celery_task_id": "", "reference_ids": job.approved_reference_ids,
            "influence_plan_hash": job.influence_plan_hash,
            "already_active": False}


def recover_task_to_gate1(task, job, user) -> dict:
    """§7 operational recovery (2A-6E-CORR-5): restore a task that a
    regeneration-JOB failure wrongly moved to 'failed'. Verifies the
    failure generated nothing and changed nothing before touching status;
    makes zero provider calls; records the recovery against the failed job.
    """
    from apps.pipeline.models import (AgentLog, ConceptReference,
                                      CreativeBrief, GeneratedImage)

    def _refuse(reason):
        raise GateRegenerationError("RECOVERY_PRECONDITION_FAILED", reason)

    if task.status != "failed":
        _refuse(f"task is {task.status!r}, not 'failed'")
    if job.task_id != task.pk or job.status != "failed":
        _refuse("the referenced regeneration job is not this task's failed "
                "job")
    new_images = GeneratedImage.objects.filter(
        task=task, created_at__gte=job.created_at).count()
    if new_images:
        _refuse(f"{new_images} image(s) were created after the job started "
                "— not a generation-free failure")
    brief = CreativeBrief.objects.filter(task=task).first()
    if not brief or brief.selected_direction_id != job.direction_id:
        _refuse("the selected direction no longer matches the job")
    approved = sorted(ConceptReference.objects.filter(
        task=task,
        permission_status=ConceptReference.PERMISSION_APPROVED)
        .values_list("pk", flat=True))
    if approved != sorted(job.approved_reference_ids):
        _refuse("the approved reference set no longer matches the job")
    plan = getattr(task, "concept_influence_plan", None)
    if plan is None or plan.plan_hash != job.influence_plan_hash:
        _refuse("the influence plan no longer matches the job")

    task.status = "awaiting_gate_1"
    task.error_message = ""
    task.save(update_fields=["status", "error_message"])
    AgentLog.objects.create(
        task=task, agent_name="ARIA", actor=user,
        action=(f"Operational recovery: task restored to awaiting_gate_1 "
                f"after regeneration job {job.pk} failed job-scoped "
                f"(GATE1_REGENERATION_FAILED). No image was generated, no "
                f"provider was called, approvals and influence plan are "
                f"unchanged."),
        payload={"code": "GATE1_REGENERATION_FAILED", "job_id": job.pk,
                 "job_error": job.error[:500],
                 "approved_reference_ids": job.approved_reference_ids,
                 "influence_plan_hash": job.influence_plan_hash},
        level="warning",
    )
    return {"recovered": True, "job_id": job.pk,
            "status": task.status}


# §9's `mark_images_rejected` and its REJECTED_LABEL — the old API's "mark rejected" door's service — left
# with that door in the clean-up of 2026-10-04 (E7); the labels it wrote stay on their images, and the
# activity feed still reads its old log lines (apps/pipeline/feed_words.py).
__all__ = ["request_gate1_regeneration", "check_regeneration_ready",
           "recover_task_to_gate1", "VARIATION_IDENTITIES",
           "GateRegenerationError",
           "GATE1_RICHNESS_DIRECTIVES",
           "REGEN_NOT_AT_GATE1", "REGEN_NO_APPROVED_REFERENCES",
           "REGEN_NO_INFLUENCE_PLAN"]
