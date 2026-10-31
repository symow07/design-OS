"""PALT-M4C-4 §2 — the production confirmation flow.

A route existing is not proof. This module is the flow itself: a palette
task reaches ``awaiting_design_intent_confirmation`` carrying a drafted
reading of the selected design; a human confirms or corrects it; the
result is persisted as a VERSIONED, append-only record with a
``design_intent`` GateDecision beside it; and only then is the confirmed
intent allowed to drive the mapper, the contract and the geometry.

The ordering matters and is enforced. ``map_confirmed_intent`` refuses a
draft, so an unconfirmed reading cannot reach geometry by accident — that
refusal is the whole point of the state.

A revision never edits an earlier row. It supersedes it, so the draft,
each correction and the reasoning behind them stay separately auditable.
"""
from __future__ import annotations

from dataclasses import asdict

from django.db import transaction

from apps.pipeline.models import (
    GateDecision, PaletteIntentConfirmation)
from apps.pipeline.services import palette_design_intent as di
from apps.pipeline.services import palette_intent_confirmation as pic
from apps.pipeline.services import palette_intent_mapping as pim

SCHEMA = "palette_confirmation_flow/1.0"

AWAITING = "awaiting_design_intent_confirmation"
CONFIRMED = "design_intent_confirmed"
GATE = "design_intent"


class ConfirmationFlowError(RuntimeError):
    """Raised when the flow is driven out of order."""


class UnconfirmedIntentError(ConfirmationFlowError):
    """Raised when a draft reading is used as design authority."""


def open_confirmation(task, intent) -> dict:
    """Put a task into the confirmation state carrying a drafted reading."""
    panel = pic.panel(intent)
    task.status = AWAITING
    task.save(update_fields=["status"])
    return panel


def _serialize_intent(intent) -> dict:
    return {
        "concept_reference": intent.concept_reference,
        "identity": intent.identity(),
        "state": intent.state,
        "unresolved_regions": list(intent.unresolved_regions),
        "fields": [asdict(f) for f in intent.fields],
    }


@transaction.atomic
def save_confirmation(task, intent, record, *, user=None,
                      notes="", scope=None) -> PaletteIntentConfirmation:
    """Persist a confirmation as a new version with a governed record."""
    if task.status != AWAITING:
        raise ConfirmationFlowError(
            f"task {task.pk} is {task.status!r}, not {AWAITING!r}; a "
            "confirmation may only be recorded from the state that asks "
            "for one")
    confirmed = pic.apply_confirmations(intent, record)
    previous = (PaletteIntentConfirmation.objects
                .select_for_update()
                .filter(task=task, superseded_by__isnull=True)
                .order_by("-version").first())
    version = (previous.version + 1) if previous else 1
    decision = GateDecision.objects.create(
        task=task, gate=GATE, decision="approve",
        decided_by=user,
        notes=(notes or "design-intent confirmation") +
        f" | draft {intent.identity()} -> confirmed {confirmed.identity()}")
    row = PaletteIntentConfirmation.objects.create(
        task=task, version=version,
        concept_reference=intent.concept_reference,
        draft_identity=intent.identity(),
        confirmation_identity=record.identity(),
        confirmed_intent_identity=confirmed.identity(),
        panel=pic.panel(intent), actions=record.to_dict()["actions"],
        confirmed_intent=_serialize_intent(confirmed),
        scope=scope or PaletteIntentConfirmation.SCOPE_VISIBLE_COMPOSITION,
        gate_decision=decision, confirmed_by=user)
    if previous:
        previous.superseded_by = row
        previous.save(update_fields=["superseded_by"])
    # NOT gate_1_approved. Confirming what the engine understood approves
    # a READING; promoting the task to a real gate would let anything keyed
    # off that gate advance on a reading.
    task.status = CONFIRMED
    task.save(update_fields=["status"])
    return row


def current_confirmation(task):
    return (PaletteIntentConfirmation.objects
            .filter(task=task, superseded_by__isnull=True)
            .order_by("-version").first())


def revision_history(task):
    """Every version, oldest first — nothing is overwritten."""
    return list(PaletteIntentConfirmation.objects
                .filter(task=task).order_by("version"))


def rehydrate(row) -> di.PaletteDesignIntent:
    """Rebuild the confirmed intent from its stored record."""
    intent = di.PaletteDesignIntent(
        concept_reference=row.confirmed_intent["concept_reference"])
    intent.unresolved_regions = list(
        row.confirmed_intent.get("unresolved_regions", []))
    for f in row.confirmed_intent["fields"]:
        intent.add(**f)
    return intent


def map_confirmed_intent(row_or_intent, defaults=None) -> dict:
    """Map a CONFIRMED intent onto the engineering contract.

    Refuses a draft. This is the gate between an AI reading and geometry,
    and it is the reason the confirmation state exists at all.
    """
    intent = (rehydrate(row_or_intent)
              if isinstance(row_or_intent, PaletteIntentConfirmation)
              else row_or_intent)
    unconfirmed = [f.name for f in intent.fields
                   if f.confirmation_state == di.PENDING
                   and f.constraint_level == di.HARD]
    if unconfirmed:
        raise UnconfirmedIntentError(
            "these HARD visible constraints are still an AI draft and "
            f"cannot drive geometry: {sorted(unconfirmed)}. Only "
            "HUMAN_CONFIRMED_DESIGN_INTENT is design authority.")
    if defaults is None:
        from apps.pipeline.services import palette_rect_tray_geometry as rt
        d = rt.RECT_TRAY_DEFAULTS
        defaults = {
            "pan.shape": "CIRCLE",
            "pan.count": d["cells_x"] * d["cells_y"],
            "grid.rows": d["cells_y"], "grid.columns": d["cells_x"],
            "tray.width_mm": d["tray_width_mm"],
            "tray.depth_mm": d["tray_depth_mm"],
        }
    return pim.map_intent(intent, defaults)


def flow_state(task) -> dict:
    """Everything the Review Board needs to link to this confirmation."""
    current = current_confirmation(task)
    history = revision_history(task)
    return {
        "record_type": SCHEMA,
        "task_id": task.pk,
        "task_status": task.status,
        "awaiting_confirmation": task.status == AWAITING,
        "grants_gate_approval": False,
        "current_version": current.version if current else None,
        "confirmed_intent_identity":
            current.confirmed_intent_identity if current else None,
        "scope": current.scope if current else None,
        "gate_decision_id": current.gate_decision_id if current else None,
        "gate": GATE,
        "revision_count": len(history),
        "revisions": [
            {"version": r.version, "created_at": r.created_at.isoformat(),
             "draft_identity": r.draft_identity,
             "confirmed_intent_identity": r.confirmed_intent_identity,
             "superseded": not r.is_current,
             "confirmed_by": getattr(r.confirmed_by, "username", None)}
            for r in history],
        "review_board_url": f"/dashboard/palette/intent-confirmation/"
                            f"{task.pk}/",
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }
