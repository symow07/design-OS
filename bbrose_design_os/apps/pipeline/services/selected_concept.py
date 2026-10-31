"""The selected Gate-1 concept as a structured reconstruction record
(2A-6E-CORR-7 §fidelity).

Task #50's production artwork dropped the selected Powder Constellation
concept: the vector composer derived its design language from the persisted
DIRECTION (whose "fine hairline rule" vocabulary matched the generic
ruled-field pattern) and never consumed the SELECTED VARIATION — even though
the approved image's provenance carries the variation identity and the
regeneration run persisted the variation's full structured record
(signatures, zones, coverage, prompt).

This service closes that loop: it loads the variation record the user
actually approved, verifies it against the approved image's own prompt, and
turns it into a bounded reconstruction spec the composer and the fidelity
validator both consume. When the identity exists but the record cannot be
recovered or verified, reconstruction FAILS CLOSED
(VECTOR_RECONSTRUCTION_REVIEW_REQUIRED) — the direction is never silently
substituted for the concept the user chose.
"""
from __future__ import annotations

import re

#: Uppercase multi-word phrases (consumer copy) inside a variation prompt.
_COPY_PHRASE_RE = re.compile(r"\b([A-ZÁÉÍÓÚÑÜ]{2,}(?:\s+[A-ZÁÉÍÓÚÑÜ]{2,})+)\b")
_VERTICAL_WINDOW = 160


def load_selected_variation(task, approved_image) -> dict | None:
    """The structured variation record behind an approved Gate-1 image.

    Returns None for legacy images (no structured variation identity).
    Returns {"verified": False, ...} when the identity exists but the
    record cannot be recovered or its prompt does not match the approved
    image — callers must fail closed on that.
    """
    provenance = approved_image.reference_provenance or {}
    identity = provenance.get("variation_identity") or ""
    if not identity or identity.startswith("variation_"):
        return None      # legacy render — no structured variation record

    revised = provenance.get('repair_variation_contract')
    if revised is not None:
        import hashlib
        parent_id = provenance.get('repair_parent_image_id')
        parent = task.images.filter(pk=parent_id, pk__lt=approved_image.pk).first() if parent_id else None
        if (not isinstance(revised, dict) or parent is None or
                revised.get('variation_id') != identity or
                revised.get('prompt') != approved_image.prompt_used or
                revised.get('parent_prompt_sha256') != hashlib.sha256(parent.prompt_used.encode()).hexdigest()):
            return {'variation_id': identity, 'verified': False, 'reason': 'The revised concept does not match its saved parent and prompt.'}
        inherited = load_selected_variation(task, parent)
        if not inherited or not inherited.get('verified') or inherited.get('variation_id') != identity:
            return {'variation_id': identity, 'verified': False, 'reason': 'The revised concept has no verified parent variation.'}
        return {**revised, 'verified': True}

    payload = _find_prompts_payload(task, identity)
    variation = None
    if payload:
        for candidate in payload.get("variations", []):
            if candidate.get("variation_id") == identity:
                variation = candidate
                break
    if variation is None:
        return {"variation_id": identity, "verified": False,
                "reason": "no persisted prompt payload carries this "
                          "variation identity"}
    if str(variation.get("prompt", "")).strip() != \
            str(approved_image.prompt_used or "").strip():
        return {"variation_id": identity, "verified": False,
                "reason": "the recovered variation prompt does not match "
                          "the approved image's prompt"}
    return {**variation, "verified": True}


#: Observability log actions that preserve a structured variations payload.
#: "generation result" = the reference-grounded REGENERATION flow (2A-6E);
#: "variation contract result" = the INITIAL structured contract render
#: (2B-3V container_gate1_variations/1.0) — task #51's Gate-1 set came from
#: the latter, and missing it here fail-closed a fully-confirmed container
#: with SELECTED_CONTAINER_VARIATION_IDENTITY_REQUIRED.
_PAYLOAD_LOG_ACTIONS = ("Gate-1 prompts: generation result",
                        "Gate-1 variation contract result")


def _find_prompts_payload(task, identity) -> dict | None:
    """The structured variations payload that produced the approved set: the
    Gate-1 checkpoint first (2C-2C-CORR-1 preserves the plan VERBATIM and
    hash-verified — the observability logs truncate long raw responses at
    20k chars and a checkpoint-reuse run logs only the reuse marker), then a
    regeneration job's persisted copy, then the observability logs."""
    from apps.pipeline.models import AgentLog, Gate1RegenerationJob
    from apps.pipeline.services import gate1_checkpoint as ckpt

    cp = ckpt.load_checkpoint(task)
    if cp:
        payload = (cp.get("prompt_plan") or {}).get("payload") or {}
        if any(v.get("variation_id") == identity
               for v in payload.get("variations") or []):
            return payload

    for job in Gate1RegenerationJob.objects.filter(
            task=task, status=Gate1RegenerationJob.STATUS_COMPLETED
    ).order_by("-id"):
        payload = job.prompts_payload or {}
        if payload.get("variations"):
            return payload
    from apps.pipeline.services.claude_service import loads_tolerant
    for log in AgentLog.objects.filter(
            task=task, action__in=_PAYLOAD_LOG_ACTIONS,
            payload__ok=True).order_by("-id"):
        for raw in reversed(log.payload.get("raw_responses") or []):
            try:
                payload = loads_tolerant(raw)
            except ValueError:
                continue
            if isinstance(payload, dict) and payload.get("variations"):
                # [his test findings on design 121, 2026-10-07, item 1] the answer as the concept step read it — its
                # ids by their slots (gate1_prompts.agree_ids): the log keeps the model's own words, "A_d1_REBEL_BLOOM",
                # where the concept was drawn and approved as "A_REBEL_BLOOM"; read apart, a design outside a project
                # (no checkpoint) would stop after Gate 1 with its approved concept not found
                from apps.pipeline.services.container_gate1 import CONTAINER_VARIATION_SLOTS
                from apps.pipeline.services.gate1_prompts import agree_ids
                agree_ids(payload, identity_slots=CONTAINER_VARIATION_SLOTS)
                return payload
    return None


def extract_copy_lines(variation: dict, product_name: str) -> dict:
    """Deterministic consumer-copy extraction from the variation's own
    prompt — verbatim phrases only, nothing invented.

    Returns {"secondary": [phrases...], "vertical": phrase|None}: uppercase
    multi-word phrases that are not the product name itself; a phrase whose
    surrounding prompt text says it runs vertically is flagged."""
    prompt = str(variation.get("prompt") or "")
    name_normalized = " ".join(str(product_name or "").upper().split())
    name_words = set(name_normalized.split())
    seen, secondary = set(), []
    vertical = None
    for match in _COPY_PHRASE_RE.finditer(prompt):
        phrase = " ".join(match.group(1).split())
        if phrase in seen:
            continue
        seen.add(phrase)
        if phrase == name_normalized or set(phrase.split()) <= name_words:
            continue
        secondary.append(phrase)
        window = prompt[max(0, match.start() - _VERTICAL_WINDOW):
                        match.end() + _VERTICAL_WINDOW].lower()
        if vertical is None and ("vertical" in window or "rotated" in window):
            vertical = phrase
    return {"secondary": secondary[:4], "vertical": vertical}


def reconstruction_spec(variation: dict, *, product_name: str,
                        direction: dict | None = None) -> dict:
    """The bounded spec the composer and the fidelity validator share."""
    copy_lines = extract_copy_lines(variation, product_name)
    name_words = [w for w in str(product_name or "").upper().split() if w]
    return {
        "variation_id": variation.get("variation_id", ""),
        "title": variation.get("title", ""),
        "composition_signature": variation.get("composition_signature", ""),
        "color_field_signature": variation.get("color_field_signature", ""),
        "motif_signature": variation.get("motif_signature", ""),
        "logo_zone": variation.get("logo_zone", ""),
        "product_name_zone": variation.get("product_name_zone", ""),
        "decorative_coverage_pct": variation.get("decorative_coverage_pct"),
        "name_lines": name_words[:3],
        "secondary_copy": copy_lines["secondary"],
        "vertical_copy": copy_lines["vertical"],
        "direction_id": (direction or {}).get("direction_id", ""),
        "verified": bool(variation.get("verified")),
    }


__all__ = ["load_selected_variation", "reconstruction_spec",
           "extract_copy_lines"]
