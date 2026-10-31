"""Provider pre-spend validation (Phase 2B-3V Gate-1 correction §3).

Immediately before ANY image-provider call, the caller validates the exact
files it is about to open against the task's authorised set. If the actual
files differ from the approved set — or any authorisation invariant is broken —
the validator returns ``ok=False`` and the caller makes ZERO provider calls.

The complete validation result is persisted (AgentLog) whether it passes or
fails, so an audit can always answer "what was checked before the money was
spent?". No provider call happens in this module.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field

from apps.pipeline.services.reference_manifest import (
    REFERENCE_CONTENT_UNAVAILABLE,
)
from apps.pipeline.services.visual_reference_resolver import (
    APPROVED_REFERENCE_FILE_MISSING,
    APPROVED_VISUAL_REFERENCES_REQUIRED,
    REFERENCE_APPROVAL_SET_CHANGED,
    REFERENCE_INFLUENCE_PLAN_MISMATCH,
    UNAPPROVED_VISUAL_REFERENCE_USED,
)

# Additional stable pre-spend codes.
PRODUCTION_USE_NOT_PERMITTED = "PRODUCTION_USE_NOT_PERMITTED"
DUPLICATE_ACTIVE_GENERATION = "DUPLICATE_ACTIVE_GENERATION"
VARIATION_DIVERSITY_GATE_FAILED = "VARIATION_DIVERSITY_GATE_FAILED"

# CORR-2 §4 per-variation exact-set codes.
VARIATION_REFERENCE_ASSIGNMENT_MISMATCH = "VARIATION_REFERENCE_ASSIGNMENT_MISMATCH"
VARIATION_REFERENCE_NOT_APPROVED = "VARIATION_REFERENCE_NOT_APPROVED"
VARIATION_REFERENCE_FILE_MISSING = "VARIATION_REFERENCE_FILE_MISSING"
VARIATION_REFERENCE_PLAN_MISMATCH = "VARIATION_REFERENCE_PLAN_MISMATCH"
VARIATION_REFERENCE_SET_EXPANDED = "VARIATION_REFERENCE_SET_EXPANDED"
VARIATION_REFERENCE_SET_REDUCED = "VARIATION_REFERENCE_SET_REDUCED"


def validate_variation_prespend(task, bundle, *, variation_id, assigned_ids,
                                opened_ids, passed_ids,
                                expected_plan_hash=None) -> PreSpendResult:
    """CORR-2 §4: enforce, immediately before ONE variation's image call, the
    exact-set invariant

        passed_reference_set == opened_reference_set == assigned_reference_set
        and assigned_reference_set ⊆ approved_reference_set

    plus plan-membership, approval and file presence of every assigned id. Any
    violation → ``ok=False`` and the caller makes ZERO image calls."""
    codes: list = []
    assigned = set(assigned_ids)
    opened = set(opened_ids)
    passed = set(passed_ids)
    approved = set(bundle.approved_reference_ids) | set(bundle.missing_reference_ids)
    present = set(bundle.approved_reference_ids)
    plan_ids = set(bundle.plan_reference_ids)

    not_approved = assigned - approved
    if not_approved:
        codes.append(f"{VARIATION_REFERENCE_NOT_APPROVED}: {sorted(not_approved)}")
    not_in_plan = assigned - plan_ids
    if not_in_plan:
        codes.append(f"{VARIATION_REFERENCE_PLAN_MISMATCH}: {sorted(not_in_plan)}")
    if expected_plan_hash and expected_plan_hash != bundle.influence_plan_hash:
        codes.append(f"{VARIATION_REFERENCE_PLAN_MISMATCH}: influence-plan hash "
                     "changed")
    missing = assigned & set(bundle.missing_reference_ids)
    if missing:
        codes.append(f"{VARIATION_REFERENCE_FILE_MISSING}: {sorted(missing)}")
    # B4b-3B §16: an owner-supplied upload whose content failed internal
    # resolution blocks every render — silence would ship a set the owner
    # believes is grounded by a file that never arrived.
    if bundle.upload_content_errors:
        codes.append(f"{REFERENCE_CONTENT_UNAVAILABLE}: " + ", ".join(
            f"reference {e['reference_id']} ({e['category']} "
            f"'{e['original_filename']}')"
            for e in bundle.upload_content_errors))
    # exact-set: no extra file, no dropped file (beyond an already-flagged
    # not-approved / missing reason).
    if opened - assigned or passed - assigned:
        codes.append(f"{VARIATION_REFERENCE_SET_EXPANDED}: opened "
                     f"{sorted(opened)} exceeds assigned {sorted(assigned)}")
    expected_open = assigned & present - missing - not_approved
    if expected_open - opened:
        codes.append(f"{VARIATION_REFERENCE_SET_REDUCED}: assigned "
                     f"{sorted(expected_open)} but opened {sorted(opened)}")
    if passed != opened:
        codes.append(f"{VARIATION_REFERENCE_ASSIGNMENT_MISMATCH}: passed "
                     f"{sorted(passed)} != opened {sorted(opened)}")

    detail = {
        "task_id": getattr(task, "pk", None),
        "variation_id": variation_id,
        "approved_reference_ids": sorted(present),
        "assigned_reference_ids": sorted(assigned),
        "opened_reference_ids": sorted(opened),
        "passed_reference_ids": sorted(passed),
        "influence_plan_hash": bundle.influence_plan_hash,
        "expected_plan_hash": expected_plan_hash or "",
        "production_use_allowed": False,
    }
    return PreSpendResult(ok=not codes, codes=codes, detail=detail)


@dataclass
class PreSpendResult:
    ok: bool
    codes: list = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _authorised_paths(bundle, has_logo) -> set:
    paths = {r.path for r in bundle.concept_references} | set(bundle.upload_paths)
    if has_logo and bundle.logo_path:
        paths.add(bundle.logo_path)
    return paths


def validate_image_prespend(
    task,
    bundle,
    *,
    opened_files,
    has_logo,
    expected_variations=None,
    expected_plan_hash=None,
    diversity_ok=None,
    require_visual=False,
    operation_active=False,
) -> PreSpendResult:
    """Validate everything checkable before spending, then return a result.

    ``opened_files``    the exact ordered paths the caller will hand the
                        provider (logo + references).
    ``expected_plan_hash``  when regenerating from a Gate-1 job, the hash the
                        job was validated against — must match the live plan.
    ``diversity_ok``    the §5 variation-diversity verdict (None when N/A).
    ``require_visual``  the workflow cannot proceed without approved visuals
                        (container Gate-1); packaging leaves it False.
    """
    from apps.pipeline.services.concept_references import approved_references

    codes: list = []
    opened = [str(p) for p in (opened_files or [])]
    authorised = _authorised_paths(bundle, has_logo)

    # 1. every opened file must trace to an authorised, task-scoped source.
    unauthorised = [p for p in opened if p not in authorised]
    if unauthorised:
        codes.append(UNAPPROVED_VISUAL_REFERENCE_USED)
    missing_on_disk = [p for p in opened if not os.path.exists(p)]

    # 2. the approval set must not have changed since the bundle was built.
    live_ids = sorted(r.pk for r in approved_references(task))
    if live_ids != sorted(bundle.approved_reference_ids):
        codes.append(REFERENCE_APPROVAL_SET_CHANGED)

    # 3. an approved reference whose file could not be resolved blocks the spend.
    if bundle.missing_reference_ids:
        codes.append(APPROVED_REFERENCE_FILE_MISSING)

    # 3b. B4b-3B §16: an uploaded TaskReference whose content failed internal
    # resolution blocks the spend the same way — never silently omitted.
    if bundle.upload_content_errors:
        codes.append(REFERENCE_CONTENT_UNAVAILABLE)

    # 4. influence-plan hash must match the expectation (regeneration path).
    if expected_plan_hash and expected_plan_hash != bundle.influence_plan_hash:
        codes.append(REFERENCE_INFLUENCE_PLAN_MISMATCH)

    # 5. concept-reference approval NEVER grants production use.
    if any(r.production_use_allowed for r in approved_references(task)):
        codes.append(PRODUCTION_USE_NOT_PERMITTED)

    # 6. the workflow required visual grounding but none is authorised.
    if require_visual and not bundle.reference_file_paths():
        codes.append(APPROVED_VISUAL_REFERENCES_REQUIRED)

    # 7. the §5 variation-diversity gate must have passed.
    if diversity_ok is False:
        codes.append(VARIATION_DIVERSITY_GATE_FAILED)

    # 8. no other active generation for the same stage.
    if operation_active:
        codes.append(DUPLICATE_ACTIVE_GENERATION)

    detail = {
        "task_id": getattr(task, "pk", None),
        "selected_direction_id": _selected_direction_id(task),
        "expected_variations": list(expected_variations or []),
        "approved_reference_ids": list(bundle.approved_reference_ids),
        "live_approved_reference_ids": live_ids,
        "opened_files": [os.path.basename(p) for p in opened],
        "unauthorised_files": [os.path.basename(p) for p in unauthorised],
        "files_missing_on_disk": [os.path.basename(p) for p in missing_on_disk],
        "influence_plan_hash": bundle.influence_plan_hash,
        "expected_plan_hash": expected_plan_hash or "",
        "permission_state": "USER_APPROVED_FOR_CONCEPT_REFERENCE"
                            if bundle.approved_reference_ids else "NONE",
        "production_use_allowed": False,
        "diversity_ok": diversity_ok,
        "has_logo": bool(has_logo),
        "require_visual": bool(require_visual),
    }
    return PreSpendResult(ok=not codes, codes=codes, detail=detail)


def _selected_direction_id(task):
    brief = getattr(task, "brief", None)
    return getattr(brief, "selected_direction_id", "") if brief else ""


def persist_prespend(task, result, log_fn=None, agent_name="ImageProducer"):
    """Durably record the pre-spend result (pass or fail) as an AgentLog row."""
    from apps.pipeline.models import AgentLog

    verdict = "PASSED" if result.ok else "FAILED"
    action = (f"Provider pre-spend validation {verdict}"
              + (f" — {', '.join(result.codes)}" if result.codes else ""))
    AgentLog.objects.create(
        task=task, agent_name=agent_name, action=action,
        payload={"prespend": result.as_dict()},
        level="info" if result.ok else "error")
    if log_fn:
        log_fn(action, data={"prespend": result.as_dict()},
               level="info" if result.ok else "error")
    return result


__all__ = [
    "validate_image_prespend", "validate_variation_prespend",
    "persist_prespend", "PreSpendResult",
    "PRODUCTION_USE_NOT_PERMITTED", "DUPLICATE_ACTIVE_GENERATION",
    "VARIATION_DIVERSITY_GATE_FAILED",
    "VARIATION_REFERENCE_ASSIGNMENT_MISMATCH", "VARIATION_REFERENCE_NOT_APPROVED",
    "VARIATION_REFERENCE_FILE_MISSING", "VARIATION_REFERENCE_PLAN_MISMATCH",
    "VARIATION_REFERENCE_SET_EXPANDED", "VARIATION_REFERENCE_SET_REDUCED",
]
