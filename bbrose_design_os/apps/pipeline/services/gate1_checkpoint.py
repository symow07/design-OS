"""container_gate1_prompt_plan/1.0 — the checkpointed Gate-1 prompt plan
(2C-2C-CORR-1).

A validated Prompt Engineer plan is expensive, human-contracted and
deterministic in meaning; an EXTERNAL image-provider failure (a billing
refusal) must not force it to be rebuilt — that wastes provider calls and
invites drift. This module promotes a passed plan into an explicit retryable
checkpoint bound to hashes of everything that gave it authority:

* the task, project and selected direction;
* the human-mandated variation spec (identities + directives + attempt cap);
* the approved reference identities AND their quarantined bytes;
* the influence plan;
* the prohibited-use contract text;
* the image-provider routing contract.

On retry, an unchanged context reuses the plan — Prompt Engineer is skipped
and no PE ApiCallRecord is created. ANY drift invalidates the checkpoint
with GATE1_PROMPT_PLAN_CHECKPOINT_INVALIDATED and requires new human
authorization; the plan is never silently rebuilt.

Image production progresses per variation (PENDING → GENERATING → GENERATED
→ QA states / PROVIDER_BILLING_BLOCKED) so a failed A never resets B or C,
never duplicates images and never consumes another PE call. A retry after a
billing block additionally requires the explicit owner acknowledgement
OPENAI_IMAGE_BILLING_CONFIRMED_BY_OWNER before any image spend.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.utils import timezone

CHECKPOINT_SCHEMA = "container_gate1_prompt_plan/1.0"
CHECKPOINT_KEY = "gate1_prompt_plan"
PREREQ_KEY = "gate1_generation_prerequisites"

STATE_VALIDATED = "VALIDATED_READY_FOR_IMAGE_PRODUCTION"
STATE_BILLING_BLOCKED = "GATE1_IMAGE_PRODUCTION_BLOCKED_PROVIDER_BILLING"
STATE_CONSUMED = "CONSUMED_IMAGES_GENERATED"

GATE1_PROMPT_PLAN_CHECKPOINT_INVALIDATED = \
    "GATE1_PROMPT_PLAN_CHECKPOINT_INVALIDATED"
PROVIDER_CALL_BUDGET_EXCEEDED = "PROVIDER_CALL_BUDGET_EXCEEDED"
BILLING_ACK = "OPENAI_IMAGE_BILLING_CONFIRMED_BY_OWNER"
BILLING_ACK_REQUIRED = "OPENAI_IMAGE_BILLING_CONFIRMED_BY_OWNER_REQUIRED"

#: §4 per-variation states
V_PENDING = "PENDING"
V_GENERATING = "GENERATING"
V_GENERATED = "GENERATED"
V_QA_PENDING = "QA_PENDING"
V_QA_PASSED = "QA_PASSED"
V_QA_FAILED = "QA_FAILED"
V_BILLING_BLOCKED = "PROVIDER_BILLING_BLOCKED"
V_FAILED_REVIEWABLE = "FAILED_REVIEWABLE"

#: task hold status while generation prerequisites are incomplete (§9)
HOLD_STATUS = "awaiting_gate1_generation_configuration"


def _sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _reference_root(image_root: str) -> Path:
    """Where a reference's bytes are, by the root its row names — §BH55 Phase 4.

    It read `Path("media")`, relative to the process's working directory: right only when the process runs from the
    Django root, and silently unreadable everywhere else, which turns the drift check below into two FILE_UNREADABLE
    strings comparing equal. The roots are the ones the rest of the system resolves: MEDIA_ROOT for a media file, and
    the materials root the Materials page and the Image seam read for a governed one.
    """
    from django.conf import settings
    if image_root == "media":
        return Path(settings.MEDIA_ROOT)
    if image_root == "materials":
        from apps.dashboard.materials_library import repo_root
        return repo_root()
    return Path(image_root)


def _reference_fingerprints(task) -> list[dict]:
    from apps.pipeline.services.concept_references import approved_references
    out = []
    for ref in approved_references(task):
        file_sha = ""
        try:
            root = _reference_root(ref.image_root)
            file_sha = hashlib.sha256(
                (root / ref.image_path).read_bytes()).hexdigest()
        except OSError:
            file_sha = "FILE_UNREADABLE"
        out.append({"reference_id": ref.pk,
                    "library_item_id": ref.library_item_id,
                    "file_sha256": file_sha,
                    "scope_sha256": _sha(ref.description or "")})
    return out


def context_hashes(task) -> dict:
    """Every input that gives a validated plan its authority (§3)."""
    from django.conf import settings

    from apps.pipeline.models import CreativeBrief
    project = getattr(task, "project", None)
    spec = (((project.metadata or {}).get("gate1_variation_spec") or {})
            if project else {})
    brief = CreativeBrief.objects.filter(task=task).first()
    plan_obj = getattr(task, "concept_influence_plan", None)
    refs = _reference_fingerprints(task)
    return {
        "task_id": task.id,
        "project_id": getattr(project, "id", None),
        "direction_id": (brief.selected_direction_id if brief else ""),
        "variation_spec_hash": _sha(spec),
        "variation_identities": list(spec.get("variation_identities") or []),
        "reference_ids": [r["reference_id"] for r in refs],
        "reference_hashes": refs,
        "influence_plan_hash": (getattr(plan_obj, "plan_hash", "") or ""),
        "prohibited_use_contract_hash": _sha(
            [r["scope_sha256"] for r in refs]
            + [spec.get("richness_directives", "")]),
        "provider_routing_contract": {
            "image_model": settings.IMAGE_MODEL,
            "per_variation_reference_routing": True,
        },
    }


def load_checkpoint(task) -> dict | None:
    project = getattr(task, "project", None)
    if project is None:
        return None
    cp = (project.metadata or {}).get(CHECKPOINT_KEY)
    if cp and cp.get("task_id") == task.id:
        return cp
    return None


def has_checkpoint(task) -> bool:
    return load_checkpoint(task) is not None


def _save(task, cp) -> None:
    project = task.project
    meta = dict(project.metadata or {})
    meta[CHECKPOINT_KEY] = cp
    project.metadata = meta
    project.save(update_fields=["metadata"])


def create_checkpoint(task, *, payload, prompts, pe_call_id,
                      provider_model="", validation_codes=()) -> dict:
    """Promote a PASSED Prompt Engineer result into the retryable
    checkpoint (§2). Never rewrites the plan; stores it verbatim."""
    ctx = context_hashes(task)
    cp = {
        "schema_version": CHECKPOINT_SCHEMA,
        **ctx,
        "prompt_engineer_call_id": pe_call_id,
        "provider_model": provider_model,
        "prompt_plan": {"payload": payload, "prompts": prompts},
        "prompt_plan_hash": _sha(prompts),
        "validation_result": {"ok": True,
                              "codes": list(validation_codes)},
        "state": STATE_VALIDATED,
        "retry_eligibility": "RETRYABLE_ON_UNCHANGED_CONTEXT",
        "billing_acknowledged": False,
        # §BH67(c)4: keyed by the plan's own ids — a slot-named plan's context holds no identities
        "variations": {vid: {"state": V_PENDING}
                       for vid in (ctx["variation_identities"]
                                   or [p.get("variation_id") for p in prompts or [] if p.get("variation_id")])},
        "created_at": timezone.now().isoformat(),
    }
    _save(task, cp)
    return cp


def verify_checkpoint(task) -> tuple[bool, list[str]]:
    """§3 — the reuse contract. True only when EVERY bound input is
    unchanged; otherwise the stable invalidation code plus the exact
    mismatches."""
    cp = load_checkpoint(task)
    if cp is None:
        return False, ["no checkpoint"]
    current = context_hashes(task)
    mismatches = []
    for key in ("task_id", "project_id", "direction_id",
                "variation_spec_hash", "variation_identities",
                "reference_ids", "influence_plan_hash",
                "prohibited_use_contract_hash",
                "provider_routing_contract"):
        if cp.get(key) != current.get(key):
            mismatches.append(f"{key} changed")
    stored_files = {r["reference_id"]: r["file_sha256"]
                    for r in cp.get("reference_hashes", [])}
    current_files = {r["reference_id"]: r["file_sha256"]
                     for r in current["reference_hashes"]}
    if stored_files != current_files:
        mismatches.append("reference file hashes changed")
    if mismatches:
        return False, [GATE1_PROMPT_PLAN_CHECKPOINT_INVALIDATED, *mismatches]
    return True, []


def plan_variation_ids(cp) -> list:
    """§BH67(c)4: the variation ids the checkpointed PLAN carries, in order — the identities a person named for the
    project when there are any, else the ids the slot-named variations gave themselves."""
    named = list(cp.get("variation_identities") or [])
    if named:
        return named
    return [p.get("variation_id") for p in ((cp.get("prompt_plan") or {}).get("prompts") or [])
            if p.get("variation_id")]


def checkpoint_plan_result(task, *, aria=None):
    """Reconstruct the PASSED plan as a RegenPromptsResult WITHOUT any
    provider call — revalidated through the same pure validator that
    accepted it (defence in depth, still zero calls)."""
    from apps.pipeline.services import container_gate1 as cg1
    from apps.pipeline.services.gate1_prompts import (
        RegenPromptsResult,
        alike_only,
        validate_regeneration_payload,
    )
    cp = load_checkpoint(task)
    payload = cp["prompt_plan"]["payload"]
    codes = validate_regeneration_payload(
        payload, cp["variation_identities"], cp["reference_ids"],
        cp["influence_plan_hash"],
        schema_version=cg1.CONTAINER_GATE1_SCHEMA,
        # the field set the plan was MADE under: a plan generated without approved references carries no
        # reference_ids (CORR-2 §7), and demanding them refused every such plan on reuse — tasks 84, 88, 89, 91
        required_fields=(cg1.CONTAINER_REQUIRED_FIELDS if cp["reference_ids"]
                         else cg1.CONTAINER_REQUIRED_FIELDS_NO_REFS),
        diversity_fields=cg1.CONTAINER_DIVERSITY_FIELDS,
        min_pairwise=cg1.CONTAINER_MIN_PAIRWISE_DIFFERENCES,
        schema_code=cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED,
        empty_code=cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED,
        not_distinct_code=cg1.CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT,
        identity_code=cg1.CONTAINER_VARIATION_IDENTITY_MISSING,
        require_per_variation_reference_ids=bool(cp["reference_ids"]),
        # §BH67(c)4: a plan made without named identities is revalidated by the slot rule it was made under
        identity_slots=(None if cp["variation_identities"] else cg1.CONTAINER_VARIATION_SLOTS))
    # [his test blocker on design 123, 2026-10-09, (2)] a plan drawn though too alike is reused as it was drawn
    alike = tuple(codes) if alike_only(codes, cg1.CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT) else ()
    if codes and not alike:
        return RegenPromptsResult(
            ok=False, payload=payload, prompts=[],
            codes=(GATE1_PROMPT_PLAN_CHECKPOINT_INVALIDATED, *codes),
            attempts=0, raw_responses=("<checkpoint revalidation failed>",),
            provider_model=cp.get("provider_model", ""))
    return RegenPromptsResult(
        ok=True, payload=payload, prompts=cp["prompt_plan"]["prompts"],
        codes=(), attempts=0,
        raw_responses=(f"<reused checkpoint {cp['prompt_plan_hash'][:16]} "
                       f"from ApiCallRecord "
                       f"{cp['prompt_engineer_call_id']} — no provider "
                       "call>",),
        provider_model=cp.get("provider_model", ""), alike=alike)


def set_variation_state(task, variation_id, state) -> None:
    cp = load_checkpoint(task)
    if cp is None:
        return
    cp.setdefault("variations", {}).setdefault(variation_id, {})[
        "state"] = state
    cp["variations"][variation_id]["updated_at"] = timezone.now().isoformat()
    _save(task, cp)


def mark_billing_blocked(task, variation_id=None) -> None:
    """§5 — classify without invalidating: the plan, the other variations
    and the regeneration allowance are untouched."""
    cp = load_checkpoint(task)
    if cp is None:
        return
    cp["state"] = STATE_BILLING_BLOCKED
    cp["billing_classification"] = [
        "OPENAI_IMAGE_PROVIDER_BILLING_LIMIT_REACHED",
        "EXTERNAL_PROVIDER_BILLING_BLOCKER",
        "IMAGE_PRODUCTION_RETRY_REQUIRED"]
    cp["billing_acknowledged"] = False
    if variation_id:
        cp.setdefault("variations", {}).setdefault(variation_id, {})[
            "state"] = V_BILLING_BLOCKED
    _save(task, cp)


def acknowledge_billing(task, *, actor) -> dict:
    """§6 — records ONLY the owner's report; proves nothing about provider
    availability. Never touches keys or balances."""
    cp = load_checkpoint(task)
    cp["billing_acknowledged"] = True
    cp["billing_acknowledgement"] = {
        "statement": BILLING_ACK,
        "recorded_at": timezone.now().isoformat(),
        "actor": getattr(actor, "username", str(actor)),
        "meaning": ["owner reports the correct OpenAI project is funded",
                    "owner reports the API key belongs to that project",
                    "owner reports the usage limit has been reviewed",
                    "owner reports the worker was restarted with the "
                    "intended key"],
    }
    if cp["state"] == STATE_BILLING_BLOCKED:
        cp["state"] = STATE_VALIDATED
    _save(task, cp)
    return cp


def existing_variation_image(task, variation_id):
    """The already-generated, non-superseded image for a variation — retry
    must never duplicate it (§4)."""
    from apps.pipeline.models import GeneratedImage
    return GeneratedImage.objects.filter(
        task=task, superseded=False,
        reference_provenance__variation_identity=variation_id).first()


def budget_guard(task, planned_calls: int) -> list[str]:
    """§8 — refuse BEFORE spend when the path would exceed the slice cap."""
    cp = load_checkpoint(task)
    if cp is None or "slice_budget" not in cp:
        return []
    from apps.pipeline.models import ApiCallRecord
    b = cp["slice_budget"]
    used = ApiCallRecord.objects.count() - b["ledger_at_slice_start"]
    if used + planned_calls > b["slice_cap"]:
        return [PROVIDER_CALL_BUDGET_EXCEEDED,
                f"used {used} + planned {planned_calls} > cap "
                f"{b['slice_cap']}"]
    return []


# --- §9 generation prerequisites (the race-condition gate) ----------------------

def generation_prerequisites(task) -> tuple[bool, list[str]]:
    """A composite-project container task may enqueue Gate-1 generation ONLY
    when every prerequisite exists. Non-composite tasks (task #51, every
    legacy task) are always ready — their behavior is unchanged."""
    project = getattr(task, "project", None)
    if project is None:
        return True, []
    from apps.pipeline.models import CreativeBrief
    from apps.pipeline.services.concept_references import approved_references
    meta = project.metadata or {}
    # §BH55 PHASE 1 (OWNER STANDING ORDER, 2026-09-19): "Where the run stops, fix what actually stopped it." These
    # prerequisites are the 2C web-grounded PILOT's governance — its mandated variation spec, its provider budget,
    # its prohibited-use contract — hand-built for project 7, and nothing in the product can supply them. MEASURED on
    # a no-spend dry run of a NEW Complete Product project through the dashboard's own requests: every such project
    # stopped right after its direction was chosen, in `awaiting_gate1_generation_configuration`, a status the
    # dashboard renders as a blank panel — missing "active variation spec", "provider budget", "prohibited-use
    # contract". A project that DECLARES the pilot keeps every prerequisite, exactly as before; any other project
    # generates as a single task does — the container target's own variation constants (which it already falls
    # back to without a spec), its spend held by the per-task cap that every recorded provider call checks.
    if "web_grounded_pilot" not in meta:
        return True, []
    missing = []
    brief = CreativeBrief.objects.filter(task=task).first()
    if not (brief and brief.selected_direction_id):
        missing.append("selected direction")
    if not meta.get("gate1_variation_spec"):
        missing.append("active variation spec")
    pilot = meta.get("web_grounded_pilot") or {}
    ctx = pilot.get("provider_context_contract") or {}
    if ctx.get("raw_image_inputs", {}).get("source_ids"):
        refs = approved_references(task)
        if not refs:
            missing.append("approved reference context")
        if getattr(task, "concept_influence_plan", None) is None:
            missing.append("influence plan")
    if not pilot.get("budget"):
        missing.append("provider budget")
    if not ctx:
        missing.append("prohibited-use contract")
    return (not missing), missing


def record_prerequisites(task, ready: bool, missing) -> None:
    project = getattr(task, "project", None)
    if project is None:
        return
    meta = dict(project.metadata or {})
    meta[PREREQ_KEY] = {
        "state": ("GATE1_GENERATION_PREREQUISITES_READY" if ready
                  else "AWAITING_GATE1_GENERATION_CONFIGURATION"),
        "missing": list(missing),
        "task_id": task.id,
        "checked_at": timezone.now().isoformat(),
    }
    project.metadata = meta
    project.save(update_fields=["metadata"])


__all__ = [
    "CHECKPOINT_SCHEMA", "CHECKPOINT_KEY", "STATE_VALIDATED",
    "STATE_BILLING_BLOCKED", "STATE_CONSUMED",
    "GATE1_PROMPT_PLAN_CHECKPOINT_INVALIDATED",
    "PROVIDER_CALL_BUDGET_EXCEEDED", "BILLING_ACK", "BILLING_ACK_REQUIRED",
    "HOLD_STATUS",
    "context_hashes", "load_checkpoint", "has_checkpoint",
    "create_checkpoint", "verify_checkpoint", "checkpoint_plan_result",
    "set_variation_state", "mark_billing_blocked", "acknowledge_billing",
    "existing_variation_image", "budget_guard",
    "generation_prerequisites", "record_prerequisites",
]
