"""Design Review Board — structured, renderer-agnostic approval data (RB1).

The Review Board is the platform's APPROVAL contract: the third layer beside
the Design Graph (artifact contract) and the TargetStrategy (pipeline
contract). It is neither a UI nor a document — it is STRUCTURED DATA. UI, and
later PDF / AI, are renderers over one ``ReviewBoardData``.

    Task -> build_review_board(task) -> ReviewBoardData -> { UI | PDF | AI }

Every Design Target inherits the same six sections and customizes only its
own SPECIFICATIONS section via ``TargetStrategy.review_sections``. This
module holds ZERO presentation — no HTML, no PDF/Illustrator layout, no CSS.
URLs and values are data; how they are laid out is each renderer's job.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class HeaderSection(BaseModel):
    brand: str = ""
    product: Optional[str] = None
    target: str = ""              # human label, e.g. "Packaging"
    version: str = ""             # e.g. "Task #42"
    created_at: str = ""
    updated_at: str = ""
    ai_version: str = ""          # model ids / engine version


class ConceptItem(BaseModel):
    id: int
    direction_name: str = ""
    rationale: str = ""
    image_url: Optional[str] = None
    qa_passed: Optional[bool] = None
    qa_score: Optional[float] = None
    is_approved: bool = False


class SelectedSection(BaseModel):
    approved_concept_id: Optional[int] = None
    preview_png_url: Optional[str] = None     # raster snapshot of the .ai
    editable_ai_url: Optional[str] = None      # the editable deliverable


class ReferenceItem(BaseModel):
    """One persisted TaskReference, presented from STORED metadata only.

    B4b-3A: every URL is the authorized per-task endpoint — never a raw
    FileField/MEDIA_URL — and nothing here is derived by re-inspecting the
    file. ``image_url`` is populated ONLY for raster types; documents (PDF/
    AI/EPS) carry ``doc_type`` and must render as neutral file cards, never
    through <img>.
    """
    id: int = 0
    category: str = ""             # the persisted key — 'color', never 'colour'
    category_label: str = ""       # owner-facing, e.g. 'Colour Reference'
    category_note: str = ""        # §4 non-authoritative guidance line
    filename: str = ""             # original_filename as stored
    media_type: str = ""           # detected at upload, stored
    file_size: int = 0
    file_size_display: str = ""    # human-readable, computed from stored int
    uploaded_at: str = ""          # ISO timestamp
    source: str = ""               # stored source classification display
    status: str = ""               # stored status field, verbatim
    previewable: bool = False      # raster only
    doc_type: str = ""             # 'PDF' | 'AI' | 'EPS' for neutral cards
    open_url: str = ""             # authorized inline view
    download_url: str = ""         # authorized attachment
    name: str = ""                 # legacy: category label (kept for renderers)
    image_url: Optional[str] = None  # legacy: authorized preview, raster only
    label: str = "Reference Only"  # always secondary + flagged


class SpecRow(BaseModel):
    label: str
    value: str


class ComparisonSection(BaseModel):
    """2B-3V-CORR-3 §12: side-by-side of the SELECTED concept render and the
    current native reconstruction, so a human judges fidelity visually —
    never from JSON reports alone. Additive; None on non-container tasks."""
    selected_concept_url: Optional[str] = None
    selected_caption: str = ""
    reconstruction_url: Optional[str] = None
    reconstruction_caption: str = ""


class ApprovalEvent(BaseModel):
    gate: str
    decision: str
    notes: str = ""
    decided_by: Optional[str] = None
    decided_at: str = ""


class ApprovalSection(BaseModel):
    status: str = ""
    reviewer: Optional[str] = None
    notes: str = ""
    history: list[ApprovalEvent] = Field(default_factory=list)


class ReviewBoardData(BaseModel):
    header: HeaderSection
    concepts: list[ConceptItem] = Field(default_factory=list)
    selected: SelectedSection = Field(default_factory=SelectedSection)
    comparison: Optional[ComparisonSection] = None
    references: list[ReferenceItem] = Field(default_factory=list)
    # B4b-3A §9/§11: whether this target ACCEPTS reference uploads. True →
    # an empty list renders the explicit empty state; False (Packaging,
    # preserved Complete Product) → an empty list renders nothing, exactly
    # as before this slice.
    references_expected: bool = False
    specifications: list[SpecRow] = Field(default_factory=list)
    approval: ApprovalSection = Field(default_factory=ApprovalSection)


# ---------------------------------------------------------------------------


def _abs(request, filefield) -> Optional[str]:
    if not filefield:
        return None
    url = filefield.url
    return request.build_absolute_uri(url) if request else url


def _iso(dt) -> str:
    return dt.isoformat() if dt else ""


def build_review_board(task, request=None) -> ReviewBoardData:
    """Assemble the six-section Review Board for ``task``. Pure data; safe on
    early-stage tasks (empty sections rather than errors)."""
    from django.conf import settings

    from apps.pipeline.targets import get_target

    brand = getattr(task, "brand", None)
    product = getattr(task, "product", None)
    header = HeaderSection(
        brand=getattr(brand, "name", "") or "",
        product=getattr(product, "name", None),
        target=task.get_design_target_display(),
        version=f"Design #{task.id}",                  # §BH55 Phase 3: a designer's word (it read "Task #")
        created_at=_iso(getattr(task, "created_at", None)),
        updated_at=_iso(getattr(task, "updated_at", None)),
        ai_version=f"{settings.IMAGE_MODEL} / {settings.CLAUDE_MODEL_FAST}",
    )

    # concepts — current (non-superseded) generated images + rationale
    from apps.pipeline.models import CreativeBrief
    brief = CreativeBrief.objects.filter(task=task).first()
    rationale_by_name = {}
    for d in ((brief.directions if brief else None) or []):
        if isinstance(d, dict) and d.get("name"):
            rationale_by_name[d["name"]] = d.get("rationale", "")
    concepts = []
    from apps.pipeline.services.gate1_review import image_is_selectable
    for img in task.images.filter(superseded=False):
        if not image_is_selectable(img, verify_pixels=True):
            continue
        qa = {}
        try:
            import json
            qa = json.loads(img.qa_notes) if img.qa_notes else {}
        except (ValueError, TypeError):
            qa = {}
        concepts.append(ConceptItem(
            id=img.id, direction_name=img.direction_name or "",
            rationale=rationale_by_name.get(img.direction_name, ""),
            image_url=_abs(request, img.image_file),
            qa_passed=img.qa_passed,
            qa_score=qa.get("score") if isinstance(qa, dict) else None,
            is_approved=img.is_approved,
        ))

    # selected — approved concept + the design deliverable. VQR-6: for
    # Product Container the reconstruction RESULT CONTRACT is the only
    # availability authority — the board links the authorized endpoints or
    # nothing, never a raw FileField URL from a merely-truthy record.
    output = task.current_output()
    selected = SelectedSection()
    if output and task.design_target == "product_container":
        from apps.pipeline.services.reconstruction_status import (
            build_container_reconstruction_result,
        )
        result = build_container_reconstruction_result(task)
        ai = result and result["artifacts"]["ai"]
        png = result and result["artifacts"]["png"]
        selected = SelectedSection(
            approved_concept_id=output.approved_image_id,
            preview_png_url=(png["preview_url"]
                             if png and png["available"] else None),
            editable_ai_url=(ai["download_url"]
                             if ai and ai["available"] else None),
        )
    elif output:
        selected = SelectedSection(
            approved_concept_id=output.approved_image_id,
            preview_png_url=_abs(request, output.design_preview),
            editable_ai_url=_abs(request, output.design_preview_ai),
        )

    # §12 comparison — selected concept vs current reconstruction (container)
    comparison = None
    if output and output.approved_image_id and getattr(
            output.approved_image, "image_file", None):
        if task.design_target == "product_container":
            # VQR-6: the reconstruction side comes from the result contract
            # (authorized endpoint) or is absent — never a raw media URL
            png = result and result["artifacts"]["png"]
            preview = (png["preview_url"]
                       if png and png["available"] else None)
            if preview and request:
                preview = request.build_absolute_uri(preview)
        else:
            preview = _abs(request, output.design_preview)
        if preview:
            comparison = ComparisonSection(
                selected_concept_url=_abs(request,
                                          output.approved_image.image_file),
                # §BH55 Phase 3: in a designer's words — they read "Selected concept #N · <its variation code>"
                # and "Current native reconstruction"
                selected_caption="The concept you chose",
                reconstruction_url=preview,
                reconstruction_caption=("The container drawn from it"
                                        if task.design_target == "product_container"
                                        else "The design made from it"),
            )

    # references — user uploads (Phase B4b), always "Reference Only".
    # B4b-3A: presented from STORED metadata alone (no file access, no MIME
    # re-detection) and linked ONLY through the authorized per-task endpoint —
    # ref.image.url / MEDIA_URL never enter the payload. One query; ordering
    # is (fixed category order, persisted ordering, uploaded_at, pk) so the
    # board is deterministic and never alphabetical-by-filename.
    from apps.pipeline.services.reference_manifest import (
        reference_rows_in_display_order,
    )
    from apps.pipeline.targets.ui import (
        PREVIEWABLE_EXTENSIONS, REFERENCE_CATEGORIES, REFERENCE_REVIEW_NOTES,
    )
    from apps.pipeline.targets.ui import INSPIRATION_CATEGORY
    cat_labels = {c["key"]: c["label"] for c in list(REFERENCE_CATEGORIES) + [INSPIRATION_CATEGORY]}
    previewable_types = {"image/png", "image/jpeg", "image/webp"}
    doc_types = {"application/pdf": "PDF",
                 "application/postscript": "EPS",
                 "application/vnd.adobe.illustrator": "AI"}

    def _size_display(n):
        if n < 1024:
            return f"{n} B"
        if n < 1024 * 1024:
            return f"{n / 1024:.1f} KB"
        return f"{n / (1024 * 1024):.1f} MB"

    def _authorized(ref, download=False):
        url = f"/api/tasks/{task.id}/references/{ref.id}/"
        if download:
            url += "?download=1"
        return request.build_absolute_uri(url) if request else url

    references = []
    # B4b-3B §25: the pipeline manifest and the Review Board share ONE
    # ordering helper, so the two surfaces cannot disagree
    for ref in reference_rows_in_display_order(task):
        previewable = ref.media_type in previewable_types
        ext = ("." + ref.original_filename.rsplit(".", 1)[-1].lower()
               if "." in ref.original_filename else "")
        doc_type = doc_types.get(ref.media_type, "")
        if ext == ".ai" and doc_type:
            # Illustrator writes both PDF-based and PostScript-based .ai
            # files; either way the owner uploaded an .ai and the card
            # should say so
            doc_type = "AI"
        references.append(ReferenceItem(
            id=ref.id,
            category=ref.kind,
            category_label=cat_labels.get(ref.kind, ref.kind),
            category_note=REFERENCE_REVIEW_NOTES.get(ref.kind, ""),
            filename=ref.original_filename,
            media_type=ref.media_type,
            file_size=ref.file_size,
            file_size_display=_size_display(ref.file_size),
            uploaded_at=_iso(ref.created_at),
            source=ref.get_source_display(),
            status=ref.status,
            previewable=previewable and ext in PREVIEWABLE_EXTENSIONS,
            doc_type=doc_type,
            open_url=_authorized(ref),
            download_url=_authorized(ref, download=True),
            name=cat_labels.get(ref.kind, ref.kind),
            image_url=(_authorized(ref)
                       if previewable and ext in PREVIEWABLE_EXTENSIONS
                       else None),
        ))
    references_expected = task.design_target == "product_container"

    # specifications — target-specific rows
    specs = [SpecRow(**r) for r in get_target(task.design_target).review_sections(task)]

    # approval — status + history from existing GateDecision rows
    history = [
        ApprovalEvent(
            gate=gd.gate, decision=gd.decision, notes=gd.notes or "",
            decided_by=(gd.decided_by.username if gd.decided_by else None),
            decided_at=_iso(gd.decided_at),
        )
        for gd in task.gate_decisions.all().order_by("decided_at")
    ]
    approval = ApprovalSection(
        status=task.status,
        reviewer=(task.assigned_to.username if getattr(task, "assigned_to", None) else None),
        notes=(task.gate_2_notes or task.gate_1_notes or ""),
        history=history,
    )

    return ReviewBoardData(
        header=header, concepts=concepts, selected=selected,
        comparison=comparison, references=references,
        references_expected=references_expected, specifications=specs,
        approval=approval)
