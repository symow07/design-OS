"""Composite Design Targets (Phase C).

A COMPOSITE target does not add a workflow — it ORCHESTRATES an ordered
sequence of existing single-target runs under a DesignProject parent.
Complete Product = Product Container → Packaging.

C1: recipe + project/first-stage creation. C2: advance_project — the
stage-by-stage orchestrator that spawns the next stage on completion,
feeds the prior stage's approved design forward, and completes the project.
"""
from __future__ import annotations

import logging

from django.db import IntegrityError, transaction

from apps.pipeline.targets.base import DesignTarget

logger = logging.getLogger(__name__)

# Short consistency note appended to a downstream stage's brief so the concept
# prompt is reminded to match the fed-forward references (packaging parity is
# preserved — this is task text, not a prompt-profile change).
_MATCH_NOTE = ("\n\n[Match the approved container design shown in the attached "
               "references — same palette, motif and brand treatment.]")

# Ordered stages per composite target: (stage label, child task target).
COMPOSITE_RECIPES: dict[str, list[tuple[str, str]]] = {
    DesignTarget.COMPLETE_PRODUCT.value: [
        ("container", DesignTarget.PRODUCT_CONTAINER.value),
        ("packaging", DesignTarget.PACKAGING.value),
    ],
}


def is_composite(target: str | None) -> bool:
    return target in COMPOSITE_RECIPES


def recipe(target: str) -> list[tuple[str, str]]:
    return COMPOSITE_RECIPES[target]


def first_stage(target: str) -> tuple[str, str]:
    return recipe(target)[0]


def create_composite_project(*, brand, product, brief, created_by, target):
    """Create the DesignProject and its FIRST-stage child DesignTask (queued),
    returning (project, first_task). The caller enqueues the child's pipeline.
    No advancement here — that is C2."""
    from apps.pipeline.models import DesignProject, DesignTask

    stage_label, stage_target = first_stage(target)
    project = DesignProject.objects.create(
        brand=brand, product=product, brief=brief,
        design_target=target, status=stage_label, created_by=created_by,
    )
    task = DesignTask.objects.create(
        brand=brand, product=product, task_text=brief,
        design_target=stage_target, stage=stage_label, project=project,
        status="queued", created_by=created_by,
    )
    return project, task


# ---------------------------------------------------------------------------
# C2 orchestration
# ---------------------------------------------------------------------------


HANDOFF_SCHEMA_2C = "complete_product_stage_handoff/1.0"
PREFLIGHT_SCHEMA_2C = "complete_product_preflight/1.1"

#: §8 rich project states (computed projection; the DB status machine stays).
PROJECT_STATES = (
    "IN_PROGRESS", "AWAITING_CONTAINER_DECISION", "CONTAINER_REJECTED",
    "AWAITING_PACKAGING_DECISION", "PACKAGING_REJECTED",
    "DESIGN_COMPLETE_PRODUCTION_BLOCKED", "PRODUCTION_READY",
    "FAILED_REVIEWABLE")

COMPOSITE_STAGE_HUMAN_ACCEPTANCE_REQUIRED = \
    "COMPOSITE_STAGE_HUMAN_ACCEPTANCE_REQUIRED"


def stage_human_acceptance(task) -> dict:
    """§7: the LATEST human design decision for a stage task — never an
    automated report. Containers use the Human Design Acceptance category
    (2B-3D); packaging maps its explicit Gate-2 human decision."""
    output = task.current_output()
    spec = (output.spec_sheet if output else None) or {}
    if task.design_target == "product_container" or \
            spec.get("backend") == "container":
        from apps.ire.container_production_readiness import (
            ACCEPTANCE_KEY, human_design_acceptance)
        verdict = human_design_acceptance(spec)
        named = (spec.get(ACCEPTANCE_KEY) or {}).get("preview_sha256")
        if verdict.get("state") == "ACCEPTED" and named:
            # §BH55 Phase 1: an act written through his door names the
            # preview's bytes; re-verified on every read — a design that
            # changed after he accepted it advances nothing
            from apps.dashboard.owner_channel import preview_sha256
            now, _name = preview_sha256(output)
            if now != named:
                return {"state": "VOID",
                        "detail": "the preview is no longer the bytes "
                                  "his acceptance names",
                        "codes": [COMPOSITE_STAGE_HUMAN_ACCEPTANCE_REQUIRED]}
        return verdict
    from apps.pipeline.models import GateDecision
    last = (GateDecision.objects.filter(task=task, gate="gate_2")
            .order_by("-id").first())
    if last is None:
        return {"state": "NOT_REVIEWED",
                "codes": [COMPOSITE_STAGE_HUMAN_ACCEPTANCE_REQUIRED]}
    if last.decision == "approve":
        return {"state": "ACCEPTED", "decided_by":
                getattr(last.decided_by, "username", "") or "reviewer",
                "codes": []}
    return {"state": "REJECTED / REVISION_REQUIRED",
            "codes": [COMPOSITE_STAGE_HUMAN_ACCEPTANCE_REQUIRED]}


def _stage_ready_to_advance(task) -> tuple[bool, dict]:
    """A completed stage advances ONLY with human acceptance ACCEPTED (§7).
    Automated checks can never override the human stage decision."""
    acceptance = stage_human_acceptance(task)
    return acceptance.get("state") == "ACCEPTED", acceptance


def build_stage_handoff(project, source_task, dest_task) -> dict:
    """§5 bounded complete_product_stage_handoff/1.0 (no prompts, no paths
    beyond approved identities, no credentials, no unrelated task data)."""
    import hashlib as _hl
    import json as _json
    from django.utils import timezone as _tz

    from apps.pipeline.services import container_contract as cc
    output = source_task.current_output()
    spec = (output.spec_sheet if output else None) or {}
    prof = spec.get("container_profile/1.0") or {}
    fields = prof.get("fields") or {}

    def _fv(name):
        return (fields.get(name) or {}).get("value")

    acceptance = stage_human_acceptance(source_task)
    record = {
        "schema_version": HANDOFF_SCHEMA_2C,
        "project_id": project.id,
        "source_task_id": source_task.id,
        "destination_task_id": dest_task.id,
        "source_target": source_task.design_target,
        "destination_target": dest_task.design_target,
        "container_profile_hash": prof.get("profile_hash", ""),
        "zone_set_hash": (spec.get("container_decoration_zones/1.0") or {}
                          ).get("zone_set_hash", ""),
        "selected_variation_identity":
            (spec.get("container_selected_variation/1.0") or {}
             ).get("variation_id", ""),
        "approved_output_id": output.id if output else None,
        "container_dimensions_mm": {
            "width": _fv("body_width_mm"), "depth": _fv("body_depth_mm"),
            "height": _fv("body_height_mm")},
        # §BH70(1), item 17: a form with no cap carries no cap's sizes — said so, where they read as sizes owed
        "cap_dimensions_mm": (
            cc.NOT_APPLICABLE if "cap_width_mm" in cc.fields_not_applying(prof.get("archetype") or "")
            else {"width": _fv("cap_width_mm"), "depth": _fv("cap_depth_mm"), "height": _fv("cap_height_mm")}),
        "materials_colors": {
            "body_material": str(_fv("body_material") or "")[:120],
            "cap_color": str(_fv("cap_color") or "")[:120],
            "body_base_color": str(_fv("body_base_color") or "")[:120],
            "body_opacity": _fv("body_opacity")},
        "orientation": {
            "front": str(_fv("front_orientation") or "")[:120],
            "back": str(_fv("back_orientation") or "")[:120]},
        "artwork_preview_identity":
            (output.design_preview.name if output and output.design_preview
             else ""),
        "human_visual_acceptance_state": acceptance.get("state", ""),
        "readiness_state": "PENDING_EXTERNAL_EVIDENCE",
        "production_blockers":
            (spec.get("container_production_readiness/1.0") or {}
             ).get("blocking_codes", []),
        "handoff_at": _tz.now().isoformat(),
    }
    record["handoff_hash"] = _hl.sha256(_json.dumps(
        {k: v for k, v in record.items() if k != "handoff_at"},
        sort_keys=True, default=str).encode()).hexdigest()
    return record


# 2C-3 §11 — deterministic handoff validation (stable findings)
HANDOFF_REJECTED_SOURCE = "COMPOSITE_HANDOFF_REJECTED_SOURCE_OUTPUT"
HANDOFF_ACCEPTANCE_MISSING = "COMPOSITE_HANDOFF_HUMAN_ACCEPTANCE_MISSING"
HANDOFF_IDENTITY_MISMATCH = "COMPOSITE_HANDOFF_IDENTITY_MISMATCH"
HANDOFF_DUPLICATE = "COMPOSITE_HANDOFF_DUPLICATE"
HANDOFF_INCOMPLETE = "COMPOSITE_HANDOFF_INCOMPLETE"

#: bounded keys ONLY — anything beyond this whitelist is leakage
_HANDOFF_ALLOWED_KEYS = frozenset({
    "schema_version", "project_id", "source_task_id", "destination_task_id",
    "source_target", "destination_target", "container_profile_hash",
    "zone_set_hash", "selected_variation_identity", "approved_output_id",
    "container_dimensions_mm", "cap_dimensions_mm", "materials_colors",
    "orientation", "artwork_preview_identity",
    "human_visual_acceptance_state", "readiness_state",
    "production_blockers", "handoff_at", "handoff_hash"})

#: never-accepted fixtures: their outputs must never ride a handoff
_NEVER_ACCEPTED_FIXTURE_TASKS = (51, 52)


def validate_stage_handoff(record: dict, *, project, source_task,
                           dest_task) -> list[str]:
    """2C-3 §11: the handoff must carry ONLY approved bounded information,
    from an ACCEPTED source, with verifiable identity, exactly once."""
    import hashlib as _hl
    import json as _json

    problems: list[str] = []
    required = ("schema_version", "project_id", "source_task_id",
                "destination_task_id", "container_profile_hash",
                "approved_output_id", "human_visual_acceptance_state",
                "handoff_hash")
    if any(not record.get(k) and record.get(k) != 0 for k in required):
        problems.append(HANDOFF_INCOMPLETE)
    extra = set(record) - _HANDOFF_ALLOWED_KEYS
    if extra:
        problems.append(f"{HANDOFF_INCOMPLETE}: unbounded keys {sorted(extra)}")
    blob = _json.dumps(record, default=str).lower()
    if "prompt" in blob or "/users/" in blob or "http" in blob:
        problems.append(f"{HANDOFF_INCOMPLETE}: leakage (prompt/path/url)")

    acceptance = stage_human_acceptance(source_task)
    state = str(acceptance.get("state", ""))
    if state != "ACCEPTED" or \
            record.get("human_visual_acceptance_state") != "ACCEPTED":
        problems.append(HANDOFF_ACCEPTANCE_MISSING)
    if "REJECTED" in state:
        problems.append(HANDOFF_REJECTED_SOURCE)
    if source_task.pk in _NEVER_ACCEPTED_FIXTURE_TASKS:
        problems.append(f"{HANDOFF_REJECTED_SOURCE}: task "
                        f"#{source_task.pk} is a never-accepted fixture")

    output = source_task.current_output()
    spec = (output.spec_sheet if output else None) or {}
    if any(k.startswith("container_reconstruction_rejected")
           and record.get("artwork_preview_identity")
           and record["artwork_preview_identity"] ==
           ((spec.get(k) or {}).get("rejected_output") or {}
            ).get("design_preview") for k in spec):
        problems.append(HANDOFF_REJECTED_SOURCE)

    if (record.get("project_id") != project.pk
            or record.get("source_task_id") != source_task.pk
            or record.get("destination_task_id") != dest_task.pk
            or (output and record.get("approved_output_id") != output.pk)):
        problems.append(HANDOFF_IDENTITY_MISMATCH)
    expected = _hl.sha256(_json.dumps(
        {k: v for k, v in record.items()
         if k not in ("handoff_at", "handoff_hash")},
        sort_keys=True, default=str).encode()).hexdigest()
    if record.get("handoff_hash") != expected:
        problems.append(f"{HANDOFF_IDENTITY_MISMATCH}: hash")

    handoffs = (project.metadata or {}).get("handoffs") or {}
    dupes = [k for k, v in handoffs.items()
             if v.get("destination_task_id") == record.get(
                 "destination_task_id")]
    if len(dupes) > 1:
        problems.append(HANDOFF_DUPLICATE)
    return problems


def project_state(project, children=None) -> str:
    """§8 computed rich state — never one generic COMPLETED."""
    from apps.pipeline.models import DesignTask
    if children is None:
        children = {t.stage: t for t in
                    DesignTask.objects.filter(project=project)}
    stages = recipe(project.design_target)
    if project.status == "failed":
        return "FAILED_REVIEWABLE"
    for label, _t in stages:
        child = children.get(label)
        if child is None:
            return "IN_PROGRESS"
        acceptance = stage_human_acceptance(child)
        state = str(acceptance.get("state", ""))
        if "REJECTED" in state:
            return ("CONTAINER_REJECTED" if label == "container"
                    else "PACKAGING_REJECTED")
        if child.status != "completed" or state != "ACCEPTED":
            if child.status in ("awaiting_gate_2", "completed"):
                return ("AWAITING_CONTAINER_DECISION" if label == "container"
                        else "AWAITING_PACKAGING_DECISION")
            return "IN_PROGRESS"
    # every stage completed + human-accepted → design complete; production
    # readiness decides the final split.
    blockers: list = []
    for label, _t in stages:
        child = children.get(label)
        output = child.current_output() if child else None
        spec = (output.spec_sheet if output else None) or {}
        blockers.extend((spec.get("container_production_readiness/1.0") or {}
                         ).get("blocking_codes", []))
        # [the owner's answer of 2026-09-27: the design is finished when he approves it; the maker's printing
        # specification is production's — while a note stands the project says so, design complete]
        blockers.extend((spec.get("container_production_readiness/1.0") or {}
                         ).get("production_notes", []))
        # [§BH71 (0a): a check not measured yet is never a block — and never marked passed, so it keeps the
        # project at "design complete" too]
        blockers.extend((spec.get("container_production_readiness/1.0") or {}
                         ).get("acceptance_warnings", []))
        if spec.get("output_intent_missing"):
            blockers.append("MISSING_OUTPUT_INTENT")
    return "PRODUCTION_READY" if not blockers \
        else "DESIGN_COMPLETE_PRODUCTION_BLOCKED"


def complete_product_preflight() -> dict:
    """§12 complete_product_preflight/1.1 — no provider calls.

    /1.1 MAKES A FAILED CHECK SAY WHY IT FAILED.

    /1.0 reported ten booleans and turned every False into the SAME blocker
    string, `COMPOSITE_DEPENDENCY_NOT_READY: <check name>` — the name of the
    check, never the reason. Two of the ten reach outside the process, and
    both swallowed the exception into a bare False:

      * `migrations_applied` — a database that will not answer and a database
        with unapplied migrations produced an identical blocker. The remedies
        are opposite; `manage.py migrate` fixes one and is meaningless for
        the other.
      * `revision_match` — a broker with no worker listening and a genuine
        repo/worker revision mismatch produced an identical blocker, after a
        silent 15-second timeout.

    This is not a cosmetic record. views.py:129 gates composite creation on
    `result`, returns this whole dict in the 409 body, and on success PERSISTS
    it into project.metadata['creation']['preflight'] (views.py:155). A
    boolean with no extent is frozen into the permanent creation contract of
    every composite project ever made (§AY0(d): a quantity carries the state
    it was measured in).

    WHAT IS PRESERVED, so /1.0 readers do not break: `checks` stays a map of
    the same ten keys to booleans, and a check that cannot be measured stays
    False — fail-closed is correct here, an unknown must not authorise a live
    pilot. `check_detail` is added ALONGSIDE it, and the blocker keeps its
    `COMPOSITE_DEPENDENCY_NOT_READY:` prefix (pinned by
    test_2c1_composite_activation.py:230, which asserts startswith) and gains
    the reason after it.

    THE BUMP'S COST WAS MEASURED BEFORE IT WAS TAKEN, AND UNLIKE THE MANIFEST
    BUMP IN 4d59a68 IT IS NOT FREE. `complete_product_preflight/1.0` is
    asserted at test_2c1_composite_activation.py:222 — updated with this
    commit — and appears in docs/complete_product/pilot_authorization_packet
    .json:163, which is NOT edited: that packet records what actually ran,
    under /1.0, and a record of what was measured then is not mine to revise
    (§AZ0(a)). test_2c2a_pilot_selection.py:56 supplies the string as test
    INPUT to build_authorization_packet rather than asserting it, so it is
    untouched and still passes.
    """
    from django.conf import settings as _s
    checks: dict = {}
    detail: dict = {}

    def _record(name: str, ok: bool, why: str) -> None:
        checks[name] = ok
        detail[name] = why

    from apps.pipeline.targets import get_target
    _record("product_container_target", bool(get_target("product_container")),
            "target registered")
    _record("packaging_target", bool(get_target("packaging")),
            "target registered")

    # One measurement, not a private copy: apps/core/health.migration_state
    # names the unapplied migrations and distinguishes "could not read" from
    # "not applied". §AR2 — the third hand-rolled `migration_plan` call in
    # this repository is how the first two drift apart.
    from apps.core.health import migration_state
    _state = migration_state()
    _record("migrations_applied", _state == "ok", _state)

    try:
        from apps.pipeline.services.revision import current_revision
        from apps.pipeline.tasks import report_worker_revision
        repo = current_revision()
        worker = report_worker_revision.delay().get(timeout=15)
        if not repo:
            _record("revision_match", False,
                    "unknown: the repository revision could not be read")
        elif repo == worker:
            _record("revision_match", True, f"ok: repo and worker at {repo}")
        else:
            _record("revision_match", False,
                    f"mismatch: repo at {repo}, worker at {worker}")
    except Exception as exc:  # noqa: BLE001
        # A broker that never answers looks nothing like a stale worker, and
        # until /1.1 it produced the identical blocker.
        _record("revision_match", False,
                f"unknown: the worker revision could not be read ({exc})")
    _openai = bool(getattr(_s, "OPENAI_API_KEY", ""))
    _anthropic = bool(getattr(_s, "ANTHROPIC_API_KEY", ""))
    _missing = [n for n, present in (("OPENAI_API_KEY", _openai),
                                     ("ANTHROPIC_API_KEY", _anthropic))
                if not present]
    _record("provider_configuration", not _missing,
            "both provider keys present" if not _missing
            else f"absent or empty: {', '.join(_missing)}")

    _record("handoff_path",
            callable(_attach_handoff) and callable(build_stage_handoff),
            "handoff callables importable")
    from apps.ire.container_production_readiness import (
        human_design_acceptance)
    _record("human_acceptance_enforcement", callable(human_design_acceptance),
            "human_design_acceptance importable")
    from apps.pipeline import views as _views
    _record("gate2_enforcement", hasattr(_views, "Gate2ApproveView"),
            "Gate2ApproveView present")
    from apps.pipeline.models import TaskReference
    _record("task_reference_linking", TaskReference is not None,
            "TaskReference model present")
    from apps.pipeline.review_board import build_review_board
    _record("review_board", callable(build_review_board),
            "build_review_board importable")

    # The prefix is a pinned contract; the reason after it is the new part.
    blockers = [f"COMPOSITE_DEPENDENCY_NOT_READY: {name} — {detail[name]}"
                for name, ok in checks.items() if not ok]
    return {"schema_version": PREFLIGHT_SCHEMA_2C, "checks": checks,
            "check_detail": detail, "blockers": blockers,
            "result": "READY_FOR_LIVE_PILOT" if not blockers else "BLOCKED"}


def advance_project(project) -> None:
    """Advance a composite project one stage, driven by its children's states.

    Called from the completion hook when a project child reaches 'completed'.
    Recomputes status from children (the source of truth): spawns the next
    stage when the current one is done, or completes the project when all
    stages are. Idempotent + concurrency-safe (row lock + unique(project,
    stage) + get_or_create), so double completions/retries can't duplicate a
    stage.
    """
    from apps.pipeline.models import DesignProject, DesignTask

    stages = recipe(project.design_target)
    with transaction.atomic():
        project = DesignProject.objects.select_for_update().get(id=project.id)
        children = {t.stage: t for t in
                    DesignTask.objects.filter(project=project)}
        prev_task = None
        for label, target in stages:
            child = children.get(label)
            if child is None:
                # current stage not started — spawn it (from prev output) and stop
                _spawn_stage(project, label, target, prev_task)
                project.status = label
                project.failed_stage = ""
                project.save(update_fields=["status", "failed_stage", "updated_at"])
                return
            if child.status != "completed":
                # current stage still in flight (or failed) — hold here
                project.status = "failed" if child.status == "failed" else label
                project.failed_stage = label if child.status == "failed" else ""
                project.save(update_fields=["status", "failed_stage", "updated_at"])
                return
            ready, acceptance = _stage_ready_to_advance(child)
            if not ready:
                # §7: a completed stage without an explicit human ACCEPTED
                # decision holds the project — automated checks never advance
                # it, and task #51-style rejections can never feed Packaging.
                meta = dict(project.metadata or {})
                meta["hold"] = {
                    "stage": label,
                    "code": COMPOSITE_STAGE_HUMAN_ACCEPTANCE_REQUIRED,
                    "human_state": acceptance.get("state", "")}
                meta["project_state"] = project_state(project, children)
                project.metadata = meta
                project.status = label
                project.save(update_fields=["status", "metadata",
                                            "updated_at"])
                return
            prev_task = child
        # every stage completed
        project.status = "completed"
        project.failed_stage = ""
        project.save(update_fields=["status", "failed_stage", "updated_at"])


def mark_project_failed(project, stage: str) -> None:
    """Record a stage failure on the project (called from ARIA._fail)."""
    from apps.pipeline.models import DesignProject

    DesignProject.objects.filter(id=project.id).update(
        status="failed", failed_stage=stage or "")


def _spawn_stage(project, label, target, prev_task):
    """Create the next stage's child task (idempotent via unique(project,
    stage)), feed the prior stage's approved design forward, and enqueue it."""
    from apps.pipeline.models import DesignTask

    brief = project.brief + (_MATCH_NOTE if prev_task is not None else "")
    # [His goal after the pitch page, 2026-10-15, B (9)] a pitch run's next stage is a pitch run too, on its own clock
    from apps.pipeline.autopilot import inherited
    try:
        task, created = DesignTask.objects.get_or_create(
            project=project, stage=label,
            defaults=dict(
                brand=project.brand, product=project.product,
                task_text=brief, design_target=target,
                status="queued", created_by=project.created_by,
                options=inherited(project, prev_task),
            ),
        )
    except IntegrityError:
        return  # concurrent spawn won the race — nothing to do
    if not created:
        return  # stage already exists — idempotent no-op

    if prev_task is not None:
        _attach_handoff(task, prev_task)
        # §5/§9: ONE bounded handoff record per stage transition, persisted on
        # the project (created only with the stage → idempotent by creation).
        meta = dict(project.metadata or {})
        meta.setdefault("handoffs", {})[label] = build_stage_handoff(
            project, prev_task, task)
        meta.pop("hold", None)
        project.metadata = meta
        project.save(update_fields=["metadata", "updated_at"])

    from apps.pipeline.tasks import run_aria_pipeline
    run_aria_pipeline.delay(task.id)


#: [His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (1): "In a
#: Complete Product, the carton CONTINUES the approved container: same mood, motif, colours, type and logo treatment as
#: 122's approved tube (red line-art roses, oval window, blush pink). Its three options differ only by layout and
#: composition on the carton (e.g. full all-over pattern / oval window front / pattern band + clean panels), never by
#: mood or personality. The distinctness checks for mood, colour and motif don't apply to it."]
#: The words of the approved container's chosen direction a design continuing it keeps, each under what it is called.
CONTINUED_LOOK = (("Its idea", "concept_statement"), ("Its mood", "emotional_tone"), ("Its motif", "graphic_elements"),
                  ("Its colours", "color_system"), ("Its finish and logo treatment", "material_finish_direction"))


def continued_container(task):
    """[His test blocker on design 123, 2026-10-09, (1).] The approved container a Complete Product's carton continues —
    the source of its stage's hand-over record (``build_stage_handoff``, made when the container was approved) — or None
    for every other design."""
    from apps.pipeline.models import DesignTask
    project = task.project if getattr(task, "project_id", None) else None      # a design of no project continues none
    if project is None or project.design_target != DesignTarget.COMPLETE_PRODUCT.value:
        return None
    if task.design_target != DesignTarget.PACKAGING.value:
        return None
    record = ((project.metadata or {}).get("handoffs") or {}).get(task.stage)
    if not isinstance(record, dict) or record.get("destination_task_id") != task.pk:
        return None
    return DesignTask.objects.filter(pk=record.get("source_task_id"), project=project).first()


def continuation_words(task) -> str:
    """[His test blocker on design 123, (1): "same mood, motif, colours, type and logo treatment as 122's approved
    tube".] The approved container's look from its own record, for the planner and the concept prompts of the design
    continuing it: its chosen direction's words (``CONTINUED_LOOK``), the colours its drawing prints, each as measured on
    it, and the faces its drawing sets — what was approved, never the plan's guess at a face; "" for every other
    design."""
    from apps.pipeline.models import CreativeBrief
    source = continued_container(task)
    if source is None:
        return ""
    brief = CreativeBrief.objects.filter(task=source).first()
    chosen = None
    if brief is not None and brief.selected_direction_id:
        chosen = next((d for d in brief.directions or [] if d.get("direction_id") == brief.selected_direction_id), None)
    output = source.current_output()
    spec = (output.spec_sheet if output else None) or {}
    lines = ["This design is the carton of a Complete Product. Its container is approved%s, and the carton CONTINUES "
             "it." % ((' — "%s"' % chosen["name"]) if chosen and chosen.get("name") else "")]
    for label, field in CONTINUED_LOOK:
        text = " ".join(str((chosen or {}).get(field) or "").split())
        if text:
            lines.append("- %s: %s" % (label, text))
    roles = (spec.get("container_colour_check/1.0") or {}).get("roles") or {}
    drawn = ["%s %s" % (role, r["drawn"]) for role, r in roles.items() if isinstance(r, dict) and r.get("drawn")]
    if drawn:
        lines.append("- The colours its drawing prints, as measured on it: " + "; ".join(drawn))
    faces = [f for f in (spec.get("container_font_usage/1.0") or {}).get("faces") or [] if f.get("postscript")]
    if faces:
        lines.append("- Its type, as its drawing sets it: " + "; ".join(
            "%s (%s)" % (f["postscript"], ", ".join(f.get("roles") or []) or "type") for f in faces))
    elif chosen and chosen.get("typography"):
        lines.append("- Its type: " + " ".join(str(chosen["typography"]).split()))
    return "\n".join(lines)


#: [His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (3): "The
#: carton's inside follows the inside reference (the berry petal flowers), and its flaps/sides repeat 122's line art."]
#: The one rose a flap and a side carry: the largest piece of the container's line art that stands as one shape — its
#: outline holding nothing of another piece's — no longer than ROSE_ASPECT times its breadth either way, ROSE_MIN_MM to
#: ROSE_MAX_MM across: a rose near its own size on a flap, so its hairlines still print. Kept whole.
ROSE_ASPECT = 1.6
ROSE_MIN_MM = 8.0
ROSE_MAX_MM = 20.0


def _rose_of(outlines: dict, product_mm) -> dict | None:
    """[His test blocker on design 123, (3).] The largest whole, compact piece of the container's traced line art — an
    outline no other outline holds, with every outline it holds (its holes, the fine lines inside them) — as a motif's
    rings in millimetres (``inside_print.unit_motif``'s shape, read at aspect 1) and its size; None where none stands
    so. Read with the house mark's own reader of potrace's grammar, as the container's drawing reads it."""
    import xml.etree.ElementTree as ET

    import numpy as np
    from shapely.geometry import Point, Polygon

    from apps.ire import brand_mark
    fx0, fy0, kx, ky = (float(v) for v in outlines["frame"])
    pw, ph = float(product_mm[0]), float(product_mm[1])

    def mm(u, v):
        return [(fx0 + u * kx) * pw, (fy0 + v * ky) * ph]
    rings = []
    root = ET.fromstring(outlines["svg"].encode("utf-8"))
    for g in (el for el in root if el.tag.endswith("}g") or el.tag == "g"):
        xform = brand_mark._transform(g.get("transform"))
        for el in g:
            parsed, _curves, _lines = brand_mark._parse_d(el.get("d"), xform)
            for sub in parsed:
                ring, cur = [], None
                for op in sub:
                    if op[0] == "M":
                        cur = mm(op[1], op[2])
                        ring = [cur]
                    elif op[0] == "L":
                        nxt = mm(op[1], op[2])
                        ring.append(cur + nxt + nxt)
                        cur = nxt
                    elif op[0] == "C":
                        nxt = mm(op[5], op[6])
                        ring.append(mm(op[1], op[2]) + mm(op[3], op[4]) + nxt)
                        cur = nxt
                if len(ring) > 2:
                    rings.append(ring)
    if not rings:
        return None
    ons = [[(pt[-2], pt[-1]) for pt in r] for r in rings]
    boxes = np.array([[min(p[0] for p in o), min(p[1] for p in o), max(p[0] for p in o), max(p[1] for p in o)]
                      for o in ons])
    shapes = [Polygon(o).buffer(0) for o in ons]
    areas = np.array([sh.area for sh in shapes])
    starts = [Point(o[0]) for o in ons]

    def holders(i):
        return np.nonzero((boxes[:, 0] <= boxes[i, 0]) & (boxes[:, 1] <= boxes[i, 1]) & (boxes[:, 2] >= boxes[i, 2])
                          & (boxes[:, 3] >= boxes[i, 3]) & (areas > areas[i]))[0]
    best = None
    for i in range(len(rings)):
        w, h = boxes[i, 2] - boxes[i, 0], boxes[i, 3] - boxes[i, 1]
        if not ROSE_MIN_MM <= max(w, h) <= ROSE_MAX_MM or max(w, h) > ROSE_ASPECT * min(w, h):
            continue
        if any(shapes[j].contains(starts[i]) for j in holders(i)):
            continue                                   # an outline inside another: a part of that piece
        if best is None or w * h > best[0]:
            best = (w * h, i)
    if best is None:
        return None
    o = best[1]
    inside = np.nonzero((boxes[:, 0] >= boxes[o, 0]) & (boxes[:, 1] >= boxes[o, 1]) & (boxes[:, 2] <= boxes[o, 2])
                        & (boxes[:, 3] <= boxes[o, 3]))[0]
    members = [int(i) for i in inside if int(i) == o or shapes[o].contains(starts[int(i)])]
    return {"cubics": [[rings[i] for i in members]],
            "mm": [round(float(boxes[o, 2] - boxes[o, 0]), 2), round(float(boxes[o, 3] - boxes[o, 1]), 2)]}


def continued_line_art(task) -> dict | None:
    """[His test blocker on design 123, (3).] The approved container's line art as its drawing draws it — its largest
    line-art motif's flat redraw (made and paid for once, kept on its concept) traced as outlines, as the container's
    drawing traces it — with its box on the container, the container's size, its ink and its one whole rose
    (``_rose_of``): for the carton continuing it, at no cost; None for every other design, and where the container
    keeps none."""
    from apps.pipeline.services import flat_motif as fm
    from apps.pipeline.targets.container import _part_boxes
    source = continued_container(task)
    output = source.current_output() if source is not None else None
    image = output.approved_image if output is not None else None
    if image is None or not isinstance(image.reference_provenance, dict):
        return None
    boxes = _part_boxes(output.spec_sheet or {})
    best = None
    for part in sorted(image.reference_provenance.get(fm.SCHEMA) or {}):
        record = fm.kept_flat(image, part)
        if record is None or part not in boxes:
            continue
        box = boxes[part]
        area = (min(1.0, box[2]) - max(0.0, box[0])) * (min(1.0, box[3]) - max(0.0, box[1]))
        if best is None or area > best[0]:
            best = (area, part, record)
    if best is None:
        return None
    _area, part, record = best
    # the carton's continuation is the container's line art in its one ink (its rose, ``_rose_of``) — its outlines
    traced = fm.trace_flat(fm.flat_bytes(record), boxes[part], record["product_mm"], colour=False)
    if traced["state"] != fm.TRACED:
        return None
    return {"part": part, "outlines": traced["outlines"], "box": traced["box"],
            "product_mm": [float(v) for v in record["product_mm"]], "ink": traced["ink"],
            "ink_share": traced["ink_share"], "source_task_id": source.pk,
            "rose": _rose_of(traced["outlines"], record["product_mm"])}


def _attach_handoff(downstream_task, upstream_task) -> None:
    """Attach the upstream stage's approved design to the downstream task as
    TaskReferences (B4b grounding) so the next stage matches it visually:
    the rendered preview, the approved concept, and any carried-forward logo.
    Best-effort — a missing file is skipped, never fatal."""
    from django.core.files.base import ContentFile

    from apps.pipeline.models import TaskReference

    def copy(kind, filefield, name):
        if not filefield:
            return
        try:
            data = filefield.read()
        except (ValueError, OSError):
            return
        # B4b-3B: handoff rows carry the full persisted metadata, exactly
        # like user uploads — the manifest-driven grounding path only
        # attaches references whose stored type and size can be verified.
        from apps.pipeline import references as refs
        detected = refs.detect_media_type(data[:1024]) or ""
        ref = TaskReference(task=downstream_task, kind=kind,
                            original_filename=name, media_type=detected,
                            file_size=len(data))
        ref.image.save(name, ContentFile(data), save=True)

    output = upstream_task.current_output()
    if output is not None:
        copy("container", output.design_preview,
             f"handoff_{upstream_task.id}_preview.png")
        approved = output.approved_image
        if approved is not None:
            copy("inspiration", approved.image_file,
                 f"handoff_{upstream_task.id}_concept.png")
    # carry forward an uploaded logo from the upstream stage, if any
    logo = upstream_task.references.filter(kind="logo").first()
    if logo is not None:
        copy("logo", logo.image, f"handoff_{upstream_task.id}_logo.png")
    # §BH69(2): the owner's inspiration pictures go on with the product — the next stage is planned from the same
    # words; each keeps its fingerprint, so its reading is found and nothing is read again
    # [his final goal, 2026-10-05, B1] and his inside references, to the carton's stage that prints them
    for pic in upstream_task.references.filter(kind__in=("inspiration_picture", "inside_reference", "sticker_reference")
                                               ).order_by("kind", "ordering", "id"):
        try:
            data = pic.image.read()
        except (ValueError, OSError):
            continue
        ref = TaskReference(task=downstream_task, kind=pic.kind, original_filename=pic.original_filename,
                            media_type=pic.media_type, file_size=len(data), ordering=pic.ordering, sha256=pic.sha256)
        import os
        ext = os.path.splitext(pic.image.name)[1] or ".png"     # a generated name, never the supplied one
        ref.image.save(f"handoff_{upstream_task.id}_{pic.kind}_{pic.pk}{ext}", ContentFile(data), save=True)


# ---------------------------------------------------------------------------
# C3 coordinator read-model
# ---------------------------------------------------------------------------


def build_project_summary(project, request=None) -> dict:
    """Thin coordinator read-model for the Complete Product UX (C3).

    Shape = recipe ⋈ children: enumerate the canonical stages from the recipe
    and overlay each existing child by its stage label. N-stage generic (never
    hardcodes 2), so a new composite recipe (Gift Set, …) surfaces with zero UI
    change. Pure data — no presentation; the breadcrumb, cross-stage navigation
    and completed summary all render from this one object. Callers gate on
    project presence, so single-target tasks never reach here.
    """
    from apps.pipeline.models import DesignTask
    from apps.pipeline.targets.base import DesignTarget

    stages_recipe = recipe(project.design_target)
    children = {t.stage: t for t in DesignTask.objects.filter(project=project)}
    # the "current" stage is the one the project status names (container /
    # packaging); completed/failed name no in-flight stage.
    stage_labels = {label for label, _ in stages_recipe}
    current_label = project.status if project.status in stage_labels else None

    stages = []
    for label, target in stages_recipe:
        child = children.get(label)
        stage = {
            "label": label,
            "target": DesignTarget(target).label,   # display, even if unspawned
            "task_id": child.id if child is not None else None,
            "status": child.status if child is not None else "pending",
            "is_current": label == current_label,
            "hero_url": None,
            "deliverables": [],
        }
        if child is not None:
            output = child.current_output()
            if output is not None:
                stage["hero_url"], stage["deliverables"] = _stage_deliverables(
                    label, output, child.id, request)
            # §11: human acceptance + readiness/blockers per stage
            acceptance = stage_human_acceptance(child)
            stage["human_acceptance"] = acceptance.get("state", "")
            spec = (output.spec_sheet if output else None) or {}
            readiness = spec.get("container_production_readiness/1.0") or {}
            stage["production_ready"] = bool(readiness.get("ready"))
            stage["blockers"] = list(readiness.get("blocking_codes") or [])
            stage["production_notes"] = list(readiness.get("production_notes") or [])     # 2026-09-27
        stages.append(stage)

    meta = dict(project.metadata or {})
    state = project_state(project, children)
    combined_blockers = sorted({b for st in stages
                                for b in (st.get("blockers") or [])})
    next_action = {
        "IN_PROGRESS": "wait for the current stage / act on its gate",
        "AWAITING_CONTAINER_DECISION": "human Gate-2 decision on the container",
        "CONTAINER_REJECTED": "container revision required",
        "AWAITING_PACKAGING_DECISION": "human Gate-2 decision on the packaging",
        "PACKAGING_REJECTED": "packaging revision required",
        "DESIGN_COMPLETE_PRODUCTION_BLOCKED":
            "resolve external production blockers",
        "PRODUCTION_READY": "none — production-ready",
        "FAILED_REVIEWABLE": "review the failed stage and retry",
    }.get(state, "")
    return {
        "id": project.id,
        "target": DesignTarget(project.design_target).label,
        "status": project.status,
        "project_state": state,
        "failed_stage": project.failed_stage or "",
        "stages": stages,
        "handoffs": {k: {"handoff_hash": v.get("handoff_hash", ""),
                         "human_visual_acceptance_state":
                             v.get("human_visual_acceptance_state", "")}
                     for k, v in (meta.get("handoffs") or {}).items()},
        "hold": meta.get("hold"),
        "combined_blockers": combined_blockers,
        # 2C-3 §14: design completion and production authority are TWO flags
        "design_complete": state in ("PRODUCTION_READY",
                                     "DESIGN_COMPLETE_PRODUCTION_BLOCKED"),
        "production_ready": state == "PRODUCTION_READY",
        "next_required_action": next_action,
    }


def _stage_deliverables(label, output, task_id, request):
    """(hero_url, [ {label, url} … ]) for one stage's PackagingOutput. URLs
    reuse PackagingOutputSerializer (single source); labels follow the CHILD
    target — the structural file is a 'Container Structure .ai' for a container,
    a 'Dieline .ai' for packaging — never a generic 'dieline'."""
    from apps.pipeline.serializers import PackagingOutputSerializer

    data = PackagingOutputSerializer(output, context={"request": request}).data
    hero_url = data.get("design_preview_url")
    struct_label = ("Container Structure .ai" if label == "container"
                    else "Dieline .ai")
    candidates = [
        ("Editable Design .ai", data.get("design_preview_ai_url")),
        ("Production PDF (CMYK)", data.get("production_pdf_url")),
        (struct_label, data.get("dieline_ai_url")),
    ]
    deliverables = [{"label": lbl, "url": url} for lbl, url in candidates if url]
    if data.get("spec_sheet"):
        deliverables.append({"label": "Spec Sheet PDF",
                             "url": f"/api/tasks/{task_id}/download_spec/"})
    return hero_url, deliverables
