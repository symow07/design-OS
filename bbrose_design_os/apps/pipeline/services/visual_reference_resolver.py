"""One canonical visual-reference resolver for EVERY image-generation path
(Phase 2B-3V Gate-1 correction §2).

Task #51's Gate-1 set was rejected because the image provider was fed four
house references (YB-1039/1036/1026/BB-202509-1234) that the product-profile
reference-anatomy path auto-selected — none of which had task-scoped concept
approval — while the four the user DID approve never reached the provider.

The correction: exactly one resolver decides which image FILES may be passed to
the provider, and it permits a file only when it is task-scoped and
human-authorized. Two authorised sources exist:

  1. USER_APPROVED_FOR_CONCEPT_REFERENCE ``ConceptReference`` rows — carried by
     the task's material-influence plan; and
  2. ``TaskReference`` uploads the human attached to THIS task (Phase B4b:
     logo / container / label / inspiration / colour).

The product-profile / reference-anatomy / material-library HOUSE INDEX
(``reference_index.select_references`` over ``DesignReference``) NEVER
contributes an image file. It may still feed bounded *textual* context (product
form, reference anatomy) to the text agents where authorised — but "house
reference" status is not automatic visual-use permission.

No other code path may append visual references independently: every image path
resolves its provider inputs here. No provider call happens in this module.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from django.conf import settings

# Stable resolver / pre-spend refusal codes (§2/§3).
APPROVED_VISUAL_REFERENCES_REQUIRED = "APPROVED_VISUAL_REFERENCES_REQUIRED"
APPROVED_REFERENCE_FILE_MISSING = "APPROVED_REFERENCE_FILE_MISSING"
REFERENCE_APPROVAL_SET_CHANGED = "REFERENCE_APPROVAL_SET_CHANGED"
REFERENCE_INFLUENCE_PLAN_MISMATCH = "REFERENCE_INFLUENCE_PLAN_MISMATCH"
UNAPPROVED_VISUAL_REFERENCE_USED = "UNAPPROVED_VISUAL_REFERENCE_USED"

#: cap on design-reference files passed to images.edit (logo rides on top).
MAX_PROVIDER_REFERENCE_FILES = 4


@dataclass(frozen=True)
class ResolvedReference:
    """One approved concept reference and the influence the plan permits it."""
    reference_id: int
    path: str
    permitted_analysis: tuple = ()
    prohibited_from_copying: tuple = ()
    influence: dict = field(default_factory=dict)


@dataclass
class VisualReferenceBundle:
    """The authorised visual grounding for one task's image generation."""
    task_id: int
    concept_references: list = field(default_factory=list)      # ResolvedReference
    upload_paths: list = field(default_factory=list)            # str
    logo_path: str | None = None
    logo_is_uploaded: bool = False
    influence_plan_hash: str = ""
    permitted_analysis: tuple = ()
    prohibited_from_copying: tuple = ()
    #: files that exist and were rejected root-bounding — recorded, never sent.
    missing_reference_ids: list = field(default_factory=list)
    #: reference ids named in the current influence plan (§4 plan-membership).
    plan_reference_ids: list = field(default_factory=list)
    #: B4b-3B §16: uploaded references (TaskReference) whose content failed
    #: internal resolution — {code, reference_id, category,
    #: original_filename}. NEVER silently dropped: pre-spend validation
    #: refuses the render while any entry is present.
    upload_content_errors: list = field(default_factory=list)

    @property
    def approved_reference_ids(self) -> list:
        return [r.reference_id for r in self.concept_references]

    def references_for(self, assigned_ids) -> tuple:
        """(files, opened_ids) for exactly the assigned ids that are approved
        AND file-present — CORR-2 §2. Never expands to the full approved set,
        never substitutes a missing file, never adds an unassigned reference:
        ids that are not approved / not present are simply omitted here and
        FLAGGED by the pre-spend validator (which fails the spend)."""
        by_id = {r.reference_id: r for r in self.concept_references}
        files, opened_ids = [], []
        for rid in assigned_ids:
            r = by_id.get(rid)
            if r is not None:
                files.append(r.path)
                opened_ids.append(rid)
        return files, opened_ids

    def provider_files_for(self, assigned_ids) -> tuple:
        """(ordered file list for this variation's images.edit call, has_logo, opened_ids).

        §BH57(a)3: the logo leads, and A LONE LOGO IS ENOUGH. It used to require at least one assigned reference,
        so a run with no approved references attached nothing while its prompt still said the wordmark was
        attached — the model drew the wordmark itself, badly. The owner's ruling: "Attach it … a lie to the model
        is worse than a limit."
        """
        files, opened_ids = self.references_for(assigned_ids)
        if self.logo_path:
            return [self.logo_path] + files, True, opened_ids
        return files, False, opened_ids

    @property
    def has_logo(self) -> bool:
        return bool(self.logo_path)

    def reference_file_paths(self) -> list:
        """Design-reference files only (concept refs + uploads), capped. The
        logo is NOT counted here — it rides on top in :meth:`provider_files`."""
        combined = ([r.path for r in self.concept_references] + self.upload_paths)
        return combined[:MAX_PROVIDER_REFERENCE_FILES]

    def provider_files(self) -> tuple:
        """(ordered file list actually passed to images.edit, has_logo).

        The logo leads the list when present. §BH57(a)3 REMOVED the "at least one design reference" condition:
        the old contract was "no references → plain generate", which meant a lone logo never reached the model
        even though the prompt said it had. MEASURED on task 84: zero references, `official_logo_included: false`,
        and a prompt instructing the model that "the official BBROSE logo" was attached. The owner ruled it
        attached. A run with neither logo nor references still takes the plain generate path, unchanged.
        """
        refs = self.reference_file_paths()
        if self.logo_path:
            return [self.logo_path] + refs, True
        if not refs:
            return [], False
        return refs, False


def _influence_plan(task):
    """(plan_dict, plan_hash) for the task, or ({}, "") when none exists."""
    plan_obj = getattr(task, "concept_influence_plan", None)
    if plan_obj is None:
        return {}, ""
    return (plan_obj.plan or {}), (plan_obj.plan_hash or "")


def _plan_reference_index(plan: dict) -> dict:
    index = {}
    for ref in (plan.get("references") or []):
        try:
            index[int(ref.get("reference_id"))] = ref
        except (TypeError, ValueError):
            continue
    return index


def _upload_paths(task) -> tuple:
    """(logo_path|None, [grounding paths], [content errors]) from the task's
    human uploads. Empty when the task has no TaskReferences (packaging
    parity).

    B4b-3B: driven by the reference manifest, not by iterating rows —
    * only ELIGIBLE_RASTER entries (PNG/JPEG/WEBP) can become provider
      files; PDF/AI/EPS are metadata-only for the current image stage and
      are never converted or handed to <images.edit>;
    * every eligible entry is verified through the internal resolver at
      resolution time (task scope, status, root bounding, size match);
    * a verification failure is NOT a silent skip — it is recorded as a
      content error carrying the stable code, and pre-spend validation
      refuses the spend (§16: the owner supplied it, so its absence stops
      the render before any provider call).
    """
    from apps.pipeline.services.reference_manifest import (
        ReferenceResolutionError, build_task_reference_manifest,
        raster_attachment_descriptors, verify_task_reference_content)

    logo, grounding, errors = None, [], []
    try:
        manifest = build_task_reference_manifest(task)
    except Exception:  # noqa: BLE001 — no reverse relation on bare tasks
        return None, [], []
    by_id = {r.id: r for r in task.references.all()}
    for att in raster_attachment_descriptors(manifest):
        try:
            verify_task_reference_content(task_id=task.pk,
                                          reference_id=att.reference_id)
        except ReferenceResolutionError as err:
            errors.append({"code": err.code,
                           "reference_id": att.reference_id,
                           "category": att.category,
                           "original_filename": att.original_filename})
            continue
        path = by_id[att.reference_id].image.path
        if att.category == "logo" and logo is None:
            logo = path
        else:
            grounding.append(path)
    return logo, grounding[:MAX_PROVIDER_REFERENCE_FILES], errors


def resolve_visual_references(task) -> VisualReferenceBundle:
    """The single authority for a task's provider image inputs (§2).

    Returns only task-scoped, human-authorised files: approved concept
    references (whose file exists within its declared root) followed by the
    task's uploads. Never the house index. An approved reference whose file is
    missing is recorded in ``missing_reference_ids`` and excluded — a render
    must never claim a visual it did not receive.
    """
    from apps.pipeline.services.concept_references import (
        PERMITTED_ANALYSIS, PROHIBITED_FROM_COPYING, approved_references,
        reference_file_path)

    plan, plan_hash = _influence_plan(task)
    plan_index = _plan_reference_index(plan)

    resolved, missing = [], []
    for row in approved_references(task):
        try:
            path = reference_file_path(row)          # root-bounded (may raise)
        except AssertionError:
            missing.append(row.pk)
            continue
        if not path.exists():
            missing.append(row.pk)
            continue
        ref_plan = plan_index.get(row.pk, {})
        resolved.append(ResolvedReference(
            reference_id=row.pk,
            path=str(path),
            permitted_analysis=tuple(ref_plan.get("permitted_analysis")
                                     or PERMITTED_ANALYSIS),
            prohibited_from_copying=tuple(ref_plan.get("prohibited_from_copying")
                                          or PROHIBITED_FROM_COPYING),
            influence={k: v for k, v in ref_plan.items()
                       if k.endswith("_influence")},
        ))

    upload_logo, upload_grounding, upload_errors = _upload_paths(task)
    logo = upload_logo or settings.BRAND_LOGO_PATH
    has_logo = bool(logo) and os.path.exists(str(logo))

    return VisualReferenceBundle(
        task_id=task.pk,
        concept_references=resolved,
        upload_paths=list(upload_grounding),
        logo_path=str(logo) if has_logo else None,
        logo_is_uploaded=bool(upload_logo),
        influence_plan_hash=plan_hash,
        permitted_analysis=tuple(PERMITTED_ANALYSIS),
        prohibited_from_copying=tuple(PROHIBITED_FROM_COPYING),
        missing_reference_ids=missing,
        plan_reference_ids=list(plan_index.keys()),
        upload_content_errors=upload_errors,
    )


__all__ = [
    "resolve_visual_references", "VisualReferenceBundle", "ResolvedReference",
    "MAX_PROVIDER_REFERENCE_FILES",
    "APPROVED_VISUAL_REFERENCES_REQUIRED", "APPROVED_REFERENCE_FILE_MISSING",
    "REFERENCE_APPROVAL_SET_CHANGED", "REFERENCE_INFLUENCE_PLAN_MISMATCH",
    "UNAPPROVED_VISUAL_REFERENCE_USED",
]
