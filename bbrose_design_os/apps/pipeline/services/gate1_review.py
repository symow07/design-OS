"""Gate-1 set review state: rejection labels, per-image selectability and the
computed set-level rejection banner (Phase 2B-3V Gate-1 correction §7).

A rejected Gate-1 set is PRESERVED, never deleted — the images, their prompts,
QA results, provider-cost rows and files stay for audit. What changes is that
the affected images become UNSELECTABLE (the human can no longer approve one at
Gate 1) and the task surfaces a set-level rejection banner without being
globally failed.

No provider call, no deletion, no task creation happens here.
"""
from __future__ import annotations

#: Stable set-level rejection codes (Phase 2B-3V Gate-1).
UNAPPROVED_REFERENCE_GROUNDING = "UNAPPROVED_REFERENCE_GROUNDING"
VARIATION_CONTRACT_NOT_PRESERVED = "VARIATION_CONTRACT_NOT_PRESERVED"

#: Refusal code when a human tries to approve a rejected/unselectable image.
GATE1_IMAGE_REJECTED_UNSELECTABLE = "GATE1_IMAGE_REJECTED_UNSELECTABLE"

#: The audit prefix carried by every rejected image's ``user_rejection_label``.
REJECTED_PREFIX = "REJECTED"

#: The human-facing banner text shown for a rejected set.
SET_REJECTED_MESSAGE = (
    "Gate-1 set rejected before human selection because unapproved visual "
    "references were used and the required variation contract was not "
    "preserved."
)


def provenance_rejected(image) -> bool:
    return str(getattr(image, 'user_rejection_label', '') or '').strip().upper().startswith(REJECTED_PREFIX)


def image_is_selectable(image, *, verify_pixels=True) -> bool:
    from .concept_quality import image_verdict
    if provenance_rejected(image) or getattr(image, 'superseded', False):
        return False
    return image_verdict(image, verify_pixels=verify_pixels)['passed']


def mark_set_rejected(task, codes, message=SET_REJECTED_MESSAGE):
    """Label every ACTIVE (non-superseded) Gate-1 image of ``task`` REJECTED
    with the given set-level codes. Idempotent; preserves the files/records.

    Returns the list of affected image ids. Makes no provider call, deletes
    nothing, and does not touch task.status (the task stays reviewable at
    awaiting_gate_1, never globally failed).
    """
    from apps.pipeline.models import GeneratedImage

    code_str = "; ".join(codes)
    label = f"{REJECTED_PREFIX} — GATE1_SET_REJECTED ({code_str})"[:200]
    affected = []
    for img in GeneratedImage.objects.filter(task=task, superseded=False):
        img.user_rejection_label = label
        prov = dict(img.reference_provenance or {})
        prov["gate1_set_rejection"] = {"codes": list(codes), "message": message}
        img.reference_provenance = prov
        img.save(update_fields=["user_rejection_label", "reference_provenance"])
        affected.append(img.id)
    return affected


def gate1_set_status(task) -> dict | None:
    """Computed set-level rejection banner for the API, or None when the set is
    not (fully) rejected. Additive — no model field, so a later authorized
    regeneration whose fresh images carry no label clears it automatically."""
    from apps.pipeline.models import GeneratedImage

    active = list(GeneratedImage.objects.filter(task=task, superseded=False))
    if not active or any(not provenance_rejected(i) for i in active):
        return None
    codes, message = [], SET_REJECTED_MESSAGE
    for i in active:
        rej = (i.reference_provenance or {}).get("gate1_set_rejection")
        if isinstance(rej, dict):
            codes = rej.get("codes") or codes
            message = rej.get("message") or message
            break
    return {
        "status": "GATE1_SET_REJECTED",
        "codes": codes,
        "message": message,
        "rejected_image_ids": [i.id for i in active],
        "selectable": False,
    }
