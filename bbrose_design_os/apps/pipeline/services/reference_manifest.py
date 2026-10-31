"""Pipeline reference manifest — B4b-3B.

One deterministic, versioned description of the references a task's owner
uploaded, built from persisted ``TaskReference`` rows ALONE, for the worker
pipeline to consume. Three hard rules:

1. **Metadata only.** Building the manifest never opens a file. Storage is
   consulted only for existence (a stat), so a missing object is representable
   (``availability: MISSING``) and the manifest stays usable for audit even
   when content is gone. Bytes are opened in exactly one place — the internal
   resolver — and only when a pipeline stage explicitly needs them.

2. **Opaque locators.** An entry identifies its content as
   ``{kind, task_id, reference_id}``. No storage key, filesystem path,
   FileField URL, MEDIA_URL, byte payload or credential ever enters the
   manifest; the browser's authorized HTTP endpoint is a human surface and
   deliberately does not appear here either.

3. **Reference only.** Every entry carries the category's usage semantics
   with the forbidden technical inferences spelled out. Nothing in the
   manifest upgrades an upload into dimensions, materials, print zones or
   production authority — Confirm Container Profile remains the authority.

The category catalog (keys, owner-facing labels, order) is shared with the
creation UI and Review Board via ``apps.pipeline.targets.ui``; the ordering
helper here is used by the Review Board too, so the two surfaces cannot
disagree.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass

MANIFEST_SCHEMA = "design_os.task_reference_manifest/1.0"

AVAILABLE = "AVAILABLE"
MISSING = "MISSING"

ELIGIBLE_RASTER = "ELIGIBLE_RASTER"
METADATA_ONLY = "METADATA_ONLY_FOR_CURRENT_IMAGE_STAGE"

#: stable stop/refusal code for content that should exist and does not
REFERENCE_CONTENT_UNAVAILABLE = "REFERENCE_CONTENT_UNAVAILABLE"

#: the only media types the current image stage can attach directly —
#: documents are represented as metadata, never converted or rasterized
PROVIDER_ELIGIBLE_MEDIA_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/webp"})

#: every media type the secure core can persist (resolver acceptance set)
ACCEPTED_MEDIA_TYPES = frozenset({
    "image/png", "image/jpeg", "image/webp",
    "application/pdf", "application/postscript",
    "application/vnd.adobe.illustrator",
})

#: §6 — category usage semantics. ``guidance`` is prose for the reasoning
#: agents; ``allowed`` / ``forbidden`` are stable machine-readable policy.
USAGE_SEMANTICS = {
    "container": {
        "guidance": "Use as shape, silhouette and proportion guidance only.",
        "allowed": ["visual_guidance", "silhouette_guidance",
                    "proportion_guidance"],
        "forbidden": ["dimension_inference", "capacity_inference",
                      "neck_finish_inference", "wall_thickness_inference",
                      "material_confirmation", "tolerance_inference",
                      "supplier_compatibility", "production_authority"],
    },
    "logo": {
        "guidance": ("Use as brand-mark reference. An uploaded raster logo "
                     "is not the final editable source and must not be "
                     "auto-traced."),
        "allowed": ["visual_guidance", "brand_mark_reference"],
        "forbidden": ["final_artwork_claim", "image_trace",
                      "editability_claim", "production_authority"],
    },
    "label": {
        "guidance": ("Use as typography, artwork hierarchy, decoration and "
                     "layout guidance."),
        "allowed": ["visual_guidance", "typography_guidance",
                    "layout_guidance"],
        "forbidden": ["production_artwork_claim",
                      "print_zone_confirmation",
                      "printable_geometry_claim", "production_authority"],
    },
    "inspiration": {
        "guidance": ("Use as mood, styling, material appearance or "
                     "visual-direction guidance."),
        "allowed": ["visual_guidance", "mood_guidance", "styling_guidance"],
        "forbidden": ["competitor_identity_copy",
                      "proprietary_artwork_copy", "production_authority"],
    },
    "color": {
        "guidance": "Use as colour-relationship and palette guidance.",
        "allowed": ["visual_guidance", "colour_relationship_guidance",
                    "palette_guidance"],
        "forbidden": ["pantone_inference", "cmyk_inference",
                      "coating_formula_inference",
                      "anodizing_specification_inference",
                      "colour_tolerance_inference", "production_authority"],
    },
}


#: the pictures read into words and never a provider input: his inspiration pictures (§BH69(2)), and [his final goal,
#: 2026-10-05, B1] his inside references — read for the carton's inside only, never sent to the concept pictures
WORDS_ONLY_KINDS = ("inspiration_picture", "inside_reference", "sticker_reference")


def _catalog():
    from apps.pipeline.targets.ui import INSIDE_CATEGORY, INSPIRATION_CATEGORY, REFERENCE_CATEGORIES, STICKER_CATEGORY
    return list(REFERENCE_CATEGORIES) + [INSPIRATION_CATEGORY, INSIDE_CATEGORY, STICKER_CATEGORY]


def category_order() -> list:
    return [c["key"] for c in _catalog()]


def category_labels() -> dict:
    return {c["key"]: c["label"] for c in _catalog()}


def reference_rows_in_display_order(task) -> list:
    """The ONE ordering every surface uses: fixed category order, then the
    persisted ordering, then upload timestamp, then pk. Never alphabetical —
    filenames are display strings, not identities."""
    order = {key: i for i, key in enumerate(category_order())}
    return sorted(task.references.all(),
                  key=lambda r: (order.get(r.kind, len(order)),
                                 r.ordering, r.created_at, r.id))


# ---------------------------------------------------------------------------
# manifest builder — metadata + a storage existence stat, never a byte read
# ---------------------------------------------------------------------------


def build_task_reference_manifest(task) -> dict:
    labels = category_labels()
    # §BH69(2): an inspiration picture is counted where a design carries one — a manifest without one is as it was
    counts = {key: 0 for key in category_order() if key not in WORDS_ONLY_KINDS}
    entries = []
    for ref in reference_rows_in_display_order(task):
        counts[ref.kind] = counts.get(ref.kind, 0) + 1
        # §BH69(2): an inspiration picture is read into words and is never a provider input, whatever its type
        raster = ref.media_type in PROVIDER_ELIGIBLE_MEDIA_TYPES and ref.kind not in WORDS_ONLY_KINDS
        try:
            exists = ref.image.storage.exists(ref.image.name)
        except (ValueError, NotImplementedError):
            exists = False
        semantics = USAGE_SEMANTICS.get(ref.kind, {})
        entries.append({
            "reference_id": ref.id,
            "task_id": task.id,
            "category": ref.kind,
            "category_label": labels.get(ref.kind, ref.kind),
            "original_filename": ref.original_filename,
            "media_type": ref.media_type,
            "file_size": ref.file_size,
            "ordering": ref.ordering,
            "uploaded_at": ref.created_at.isoformat() if ref.created_at
            else "",
            "source": ref.source,
            "status": ref.status,
            "preview_kind": "raster" if raster else "document",
            "availability": AVAILABLE if exists else MISSING,
            "attachment_eligibility": (ELIGIBLE_RASTER if raster
                                       else METADATA_ONLY),
            "content_locator": {"kind": "task_reference",
                                "task_id": task.id,
                                "reference_id": ref.id},
            "usage_policy": {
                "guidance": semantics.get("guidance", ""),
                "allowed": list(semantics.get("allowed", [])),
                "forbidden": list(semantics.get("forbidden", [])),
            },
        })
    return {
        "schema": MANIFEST_SCHEMA,
        "task_id": task.id,
        "design_target": task.design_target,
        "reference_count": len(entries),
        "counts_by_category": counts,
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# internal content resolver — the ONE place reference bytes are opened
# ---------------------------------------------------------------------------


class ReferenceResolutionError(Exception):
    """Refusal with a stable code; the message never contains a path."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass
class ResolvedReferenceContent:
    """Controlled content handle: identity, safe metadata and a byte stream.
    Deliberately no filesystem path, no URL, no model instance."""
    reference_id: int
    task_id: int
    category: str
    filename: str
    media_type: str
    file_size: int
    stream: io.BytesIO


def _locate_validated_path(*, task_id, reference_id):
    """All resolver checks; returns (ref, validated absolute path). Private —
    callers outside this module receive streams, never paths."""
    from django.core.files.storage import default_storage

    from apps.pipeline import references as refs
    from apps.pipeline.models import TaskReference

    ref = TaskReference.objects.filter(
        id=reference_id, task_id=task_id).first()
    if ref is None:
        # covers: missing task, missing reference, and a reference that
        # belongs to a DIFFERENT task — one non-leaking refusal for all three
        raise ReferenceResolutionError(
            REFERENCE_CONTENT_UNAVAILABLE,
            f"reference {reference_id} does not exist for task {task_id}")
    if ref.status != "REFERENCE_ONLY":
        raise ReferenceResolutionError(
            REFERENCE_CONTENT_UNAVAILABLE,
            f"reference {reference_id} has status {ref.status!r}")
    if ref.media_type not in ACCEPTED_MEDIA_TYPES:
        raise ReferenceResolutionError(
            REFERENCE_CONTENT_UNAVAILABLE,
            f"reference {reference_id} has unsupported stored media type "
            f"{ref.media_type!r}")
    if ref.file_size > refs.max_upload_bytes():
        raise ReferenceResolutionError(
            REFERENCE_CONTENT_UNAVAILABLE,
            f"reference {reference_id} exceeds the reference size limit")

    from django.core.exceptions import SuspiciousOperation

    name = ref.image.name or ""
    root = os.path.realpath(default_storage.path(refs.STORAGE_ROOT))
    try:
        full = os.path.realpath(default_storage.path(name))
    except (ValueError, NotImplementedError, SuspiciousOperation):
        # includes SuspiciousFileOperation — a stored name that tries to
        # leave the storage area resolves to a refusal, never an exception
        raise ReferenceResolutionError(
            REFERENCE_CONTENT_UNAVAILABLE,
            f"reference {reference_id} has no resolvable storage object")
    if not (full == root or full.startswith(root + os.sep)):
        raise ReferenceResolutionError(
            REFERENCE_CONTENT_UNAVAILABLE,
            f"reference {reference_id} escapes the reference storage area")
    if not os.path.exists(full):
        raise ReferenceResolutionError(
            REFERENCE_CONTENT_UNAVAILABLE,
            f"stored content for reference {reference_id} is missing")
    actual = os.path.getsize(full)
    if actual != ref.file_size:
        raise ReferenceResolutionError(
            REFERENCE_CONTENT_UNAVAILABLE,
            f"stored content for reference {reference_id} does not match "
            f"its recorded size ({actual} != {ref.file_size})")
    return ref, full


def verify_task_reference_content(*, task_id, reference_id) -> None:
    """Every resolver check WITHOUT reading bytes (stat only). Raises
    :class:`ReferenceResolutionError` on any violation."""
    _locate_validated_path(task_id=task_id, reference_id=reference_id)


def resolve_task_reference_content(*, task_id,
                                   reference_id) -> ResolvedReferenceContent:
    from apps.pipeline import references as refs

    ref, full = _locate_validated_path(task_id=task_id,
                                       reference_id=reference_id)
    with open(full, "rb") as fh:
        stream = io.BytesIO(fh.read())
    # a safe display name on the stream (several client libraries read it);
    # never the storage path
    stream.name = refs.sanitise_filename(ref.original_filename) or "reference"
    return ResolvedReferenceContent(
        reference_id=ref.id, task_id=ref.task_id, category=ref.kind,
        filename=ref.original_filename, media_type=ref.media_type,
        file_size=ref.file_size, stream=stream)


# ---------------------------------------------------------------------------
# image-stage attachment descriptors (§14)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RasterAttachment:
    """One provider-eligible raster reference, identified — not opened."""
    reference_id: int
    task_id: int
    category: str
    media_type: str
    original_filename: str
    ordering: int
    status: str


def raster_attachment_descriptors(manifest: dict) -> list:
    """Ordered, de-duplicated descriptors for every ELIGIBLE_RASTER entry.
    PDF/AI/EPS never appear here — they are metadata-only for the current
    image stage, by policy rather than by accident."""
    seen = set()
    out = []
    for entry in manifest.get("entries", []):
        if entry.get("attachment_eligibility") != ELIGIBLE_RASTER:
            continue
        rid = entry["reference_id"]
        if rid in seen:
            continue
        seen.add(rid)
        out.append(RasterAttachment(
            reference_id=rid, task_id=entry["task_id"],
            category=entry["category"], media_type=entry["media_type"],
            original_filename=entry["original_filename"],
            ordering=entry["ordering"], status=entry["status"]))
    return out


# ---------------------------------------------------------------------------
# reasoning-stage context (§12/§13) — text, no locators, no paths, no bytes
# ---------------------------------------------------------------------------

_CONSTRAINTS = (
    "Every uploaded file is REFERENCE ONLY - temporary visual guidance, "
    "never approved production specification. Preserve the owner's stated "
    "design intent; keep the category distinctions; never infer dimensions, "
    "capacity, neck finish, materials, tolerances, supplier compatibility, "
    "print zones, exact Pantone/CMYK values or production colour tolerances "
    "from any of them. The .ai document remains the source of truth for "
    "artwork; uploaded references are not final artwork and are never "
    "auto-traced."
)


def _entry_lines(manifest: dict) -> list:
    lines = []
    for e in manifest.get("entries", []):
        if e["category"] in WORDS_ONLY_KINDS:      # §BH69(2): its WORDS reach the planner, never its file or name; an
            continue                                # inside reference reaches the carton's inside alone (B1)
        lines.append(
            f"- [{e['category_label']}] \"{e['original_filename']}\" "
            f"({e['media_type']}, {e['status']}): "
            f"{e['usage_policy']['guidance']}")
    return lines


def _inspiration_block(manifest: dict) -> str:
    """§BH69(2): the owner's inspiration pictures as the WORDS read from them — never their files or their names."""
    entries = manifest["entries"] if "entries" in manifest else []
    ids = [e["reference_id"] for e in entries if e["category"] == "inspiration_picture"]
    if not ids:
        return ""
    from apps.pipeline.services import inspiration
    return inspiration.words_block(ids)


def _with_inspiration(context, manifest: dict):
    block = _inspiration_block(manifest)
    if not block:
        return context
    return block if not context else context + "\n\n" + block


def creative_director_reference_context(manifest: dict):
    """§12 — structured human-readable summary for direction planning.
    None when the task has no references."""
    lines = _entry_lines(manifest)
    if not manifest.get("reference_count") or not lines:
        return _with_inspiration(None, manifest)
    return _with_inspiration(
        "OWNER-UPLOADED REFERENCES (visual guidance only):\n"
        + "\n".join(lines)
        + "\n" + _CONSTRAINTS, manifest)


def prompt_engineer_reference_context(manifest: dict):
    """§13 — the same distinctions for prompt building. The resulting image
    prompt must keep container-shape, brand-logo, label-artwork, inspiration
    and colour guidance distinct, and must claim no technical authority."""
    lines = _entry_lines(manifest)
    if not manifest.get("reference_count") or not lines:
        return _with_inspiration(None, manifest)
    return _with_inspiration(
        "OWNER-UPLOADED REFERENCES for this task (visual guidance only - "
        "keep each category's role distinct in the prompt):\n"
        + "\n".join(lines)
        + "\n" + _CONSTRAINTS, manifest)
