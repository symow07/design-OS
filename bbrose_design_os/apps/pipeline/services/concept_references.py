"""Concept-reference candidates, approval and influence plan (Phase 2A-6E).

Task #50's Gate-1 audit proved the material intelligence never reached the
image provider in a usable visual form: the render path performed no material
retrieval at all, DIP context was two text notes at planning time, and the
only visuals the provider saw were house production-reference rasters whose
identity was not even persisted. This service closes the loop with an
explicit, human-gated flow:

    build_candidates(task)            bounded deterministic retrieval →
                                      CANDIDATE rows, thumbnails, statuses
    user selects 2–4 in the UI        never automatic
    approve_concept_references(...)   USER_APPROVED_FOR_CONCEPT_REFERENCE +
                                      material_influence_plan/1.0

Boundaries carried by code:
  * no provider call anywhere in this module;
  * machine code never sets APPROVED — approval requires a user;
  * concept-reference permission never implies production use
    (ConceptReference.production_use_allowed is structurally False);
  * the influence plan describes design principles and carries NO file
    locator — a path-like value in the plan raises instead of shipping
    (the design_context leak discipline);
  * `materials/` stays read-only: candidates are read and streamed, never
    copied, converted or modified.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

INFLUENCE_SCHEMA = "material_influence_plan/1.0"
CANDIDATE_LIMIT = 10
HISTORICAL_LIMIT = 6
MATERIAL_LIMIT = 4
APPROVE_MIN, APPROVE_MAX = 2, 4

#: Stable refusal codes.
REFERENCE_APPROVAL_COUNT_OUT_OF_RANGE = "REFERENCE_APPROVAL_COUNT_OUT_OF_RANGE"
REFERENCE_NOT_A_CANDIDATE = "REFERENCE_NOT_A_CANDIDATE"
REFERENCE_WRONG_TASK = "REFERENCE_WRONG_TASK"

#: What the user's approval permits the pipeline to analyze.
PERMITTED_ANALYSIS = ("palette", "composition", "motif", "typography",
                      "texture", "finishing")
#: Copy prohibitions attached to EVERY approved reference (§5).
PROHIBITED_FROM_COPYING = (
    "copy the same layout",
    "reproduce the same pattern",
    "trace the artwork",
    "recreate the same logo placement",
    "reproduce unique illustrations",
    "imitate a competitor package closely",
)

#: Decorative DIP inventory categories whose displayable rasters may be
#: offered as concept candidates.
_MATERIAL_CATEGORIES = ("PATTERN", "BACKGROUND", "MOTIF",
                        "RASTER_DESIGN_ASSET", "REUSABLE_VECTOR_ASSET", "ICON")
_DISPLAYABLE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
#: Vocabulary that makes a decorative material relevant to a cosmetics
#: packaging brief even when the filename shares no literal token with it.
_COSMETIC_RELEVANCE_TOKENS = frozenset(
    "gold golden floral flower rose pink blush pastel luxury elegant pattern "
    "texture abstract line lines wave marble silk satin powder beauty "
    "cosmetic cosmetics glitter shimmer gradient soft cream ivory peach mint "
    "editorial minimal ornament linework halo radial dot dots particle".split())

_TOKEN_RE = re.compile(r"[a-z0-9]+")
#: Locator fragments that must never appear in an influence plan.
_LOCATOR_MARKERS = ("materials/", "media/", "/users/", ".png", ".jpg",
                    ".jpeg", ".webp", ".ai", ".pdf", ".eps")


class ConceptReferenceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _dip_inventory_path() -> Path:
    default = Path(settings.BASE_DIR).parent / "var" / "design_intelligence" \
        / "audits" / "dip0" / "inventory" / "inventory.jsonl"
    return Path(getattr(settings, "DIP_INVENTORY_PATH", default))


def materials_root() -> Path:
    """The read-only root that inventory relative_paths resolve against."""
    return Path(getattr(settings, "MATERIALS_ROOT",
                        Path(settings.BASE_DIR).parent))


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(str(text or "").lower()))


#: [His goal of 2026-10-06, item 13 (transcribed at a9ac953): "On the concept-pick page, the "draw again with references"
#: grid ... shows only references that match the brief, not unrelated stock."] Words that say nothing of a brief: English's
#: own small words, and the words every brief and every file of this house shares. MEASURED on designs 117, 119 and 120:
#: stock backgrounds were offered as matching the brief on "and", "for", "with", "design" and "style", and house files on
#: "bbrose", "carton" and "back" — every one of the 16 offered to 120.
STOP_WORDS = frozenset(
    "and the for with without from into onto over under its our your their this that these those are was were has have "
    "had will can all any each every only also very just than then there here what which who how why when where across "
    "about above below after before between through per via not but one two three own new more most look feel make made "
    "use like set sets give gives shown show shows inside outside top bottom left right front back side sides "
    "design designs designed style styles background backgrounds product products packaging package brand bbrose carton "
    "cartons box boxes art image images picture pictures copy text type logo name test imaginary".split())


def _task_tokens(task) -> set[str]:
    """The brief's own words a reference may match — never a word every brief or file shares (``STOP_WORDS``)."""
    parts = [getattr(task, "task_text", "") or ""]
    product = getattr(task, "product", None)
    if product is not None:
        parts += [product.name or "", product.product_type or ""]
    return {t for t in _tokens(" ".join(parts)) if len(t) > 2 and t not in STOP_WORDS and not t.isdigit()}


# --- candidate retrieval ---------------------------------------------------------


def _historical_candidates(task, profile=None):
    """Scored DesignReference rows — the house production-file index."""
    from apps.core.models import DesignReference

    refs = list(DesignReference.objects.filter(active=True))
    if not refs:
        return []
    tokens = _task_tokens(task)
    product = getattr(task, "product", None)
    category = (getattr(product, "category", "") if product else "") or \
        ((profile or {}).get("category") or "")
    media = Path(settings.MEDIA_ROOT)

    rows = []
    for ref in refs:
        if not (media / ref.image_path).exists():
            continue
        score = 0.0
        reasons = []
        if category and ref.category == category:
            score += 3
            reasons.append(f"same product category ({category})")
        type_overlap = tokens & _tokens(ref.product_type)
        if type_overlap:
            score += 2 * len(type_overlap)
            reasons.append("matching product type "
                           + "/".join(sorted(type_overlap)[:3]))
        hay = set(ref.tags or []) | _tokens(ref.summary)
        tag_overlap = tokens & hay
        if tag_overlap:
            score += len(tag_overlap)
            reasons.append("shared design vocabulary "
                           + "/".join(sorted(tag_overlap)[:4]))
        # [his goal of 2026-10-06, item 13] offered only for the brief: its product, or two of its own words
        if not type_overlap and len(tag_overlap) < 2:
            continue
        rows.append({
            "source_type": "HISTORICAL_DESIGN_REFERENCE",
            "library_item_id": f"design_reference:{ref.pk}",
            "title": ref.name[:200],
            "description": (ref.summary or "")[:500],
            "relevance_reason": "; ".join(reasons)[:300],
            "retrieval_score": score,
            # House production lineage, but ownership is a human verdict —
            # the machine records lineage, never a right.
            "ownership_status": "HOUSE_PRODUCTION_LINEAGE_UNCONFIRMED",
            "rights_status": "RIGHTS_UNREVIEWED",
            "is_vector": False,   # the indexed file is a raster of the source
            "image_root": "media",
            "image_path": ref.image_path,
        })
    rows.sort(key=lambda r: (-r["retrieval_score"], r["library_item_id"]))
    return rows[:HISTORICAL_LIMIT]


def _material_candidates(task):
    """Day 7 §3: candidates ranked on what the library index says each file shows (materials_retrieval) — captions, tags,
    style, kind, measured colours, suitable surfaces — never on a file name; the top three to five and one contrast, each
    pinned by content hash with a role; the house index joins with a house boost."""
    from apps.pipeline.services import materials_retrieval
    try:
        return materials_retrieval.candidates(task)
    except OSError:
        return []


#: §BH60(b) — the project-metadata key naming design references this run may NOT see, by id. Generic: the
#: key holds whatever a run's own record names, and this module carries no target of its own. It exists for
#: a REPRODUCTION test, where the run is asked to redraw a design the house has already made and must not be
#: handed that design: "it does not get the original artwork, in any form, at any stage."
WITHHELD_REFERENCE_IDS_KEY = "withheld_design_reference_ids"


def withheld_reference_ids(task) -> set:
    """The design-reference ids this task's project withholds, or an empty set.

    A project that withholds nothing is the ordinary case, so an absent key and a task with no project both
    read as "withholds nothing". Only whole numbers count; anything else in the list is not an id and is not
    treated as one.
    """
    project = task.project if task.project_id else None
    if project is None:
        return set()
    named = project.metadata.get(WITHHELD_REFERENCE_IDS_KEY) if project.metadata else None
    if not isinstance(named, (list, tuple, set)):
        return set()
    return {int(v) for v in named
            if isinstance(v, int) or (isinstance(v, str) and v.strip().isdigit())}


def withheld_source_files(task) -> set:
    """The file names of the artwork this task's project withholds — one design can sit in more than one library.

    FOUND ON THE §BH65(d) RE-RUN (2026-09-23): FB-2060 is DesignReference 15 AND the AI-design-library file
    `materials/historical AI production designs/FB-2060 白卡.ai`, a candidate under its own `ai:` id on task 89's run
    and task 90's. A withheld design reference names its own source file (`DesignReference.source_file`), and a
    candidate whose file IS that file is the same artwork and is withheld with it — measured on the record, never
    matched by title, and never left to where it happens to fall in a list the planner reads the first ten of.
    """
    ids = withheld_reference_ids(task)
    if not ids:
        return set()
    from apps.core.models import DesignReference
    return {Path(name).name for name in DesignReference.objects.filter(id__in=ids).values_list(
        "source_file", flat=True) if name}


def build_candidates(task, profile=None, limit: int = CANDIDATE_LIMIT):
    """Bounded, deterministic candidate retrieval. Persists CANDIDATE rows
    idempotently (existing approvals/declines are never overwritten) and
    NEVER approves anything. No provider call.

    §BH60(b): a design reference whose id the project WITHHOLDS is dropped before anything is persisted or
    described — it reaches neither the record nor the planner.
    """
    from apps.pipeline.models import ConceptReference

    from apps.pipeline.services.ai_style_profile import (
        ai_design_candidates)
    proposed = (_historical_candidates(task, profile=profile)
                + _material_candidates(task)
                + ai_design_candidates(task))[:limit + 8]
    withheld = withheld_reference_ids(task)
    if withheld:
        # §BH60(b): the ids this project withholds never become rows and never reach the planner — and neither does
        # the same artwork under another library's id (`withheld_source_files`)
        barred = {"design_reference:%d" % i for i in withheld}
        files = withheld_source_files(task)
        proposed = [d for d in proposed if d.get("library_item_id") not in barred
                    and not (d.get("image_path") and Path(d["image_path"]).name in files)]
    rows = []
    for data in proposed:
        row, created = ConceptReference.objects.get_or_create(
            task=task, library_item_id=data["library_item_id"],
            defaults=data)
        if not created:
            # refresh retrieval metadata; permission state is untouchable here
            for field in ("retrieval_score", "relevance_reason"):
                setattr(row, field, data[field])
            row.save(update_fields=["retrieval_score", "relevance_reason"])
        rows.append(row)
    return rows


# --- approval + influence plan ----------------------------------------------------


def _influence_line(kind: str, vocabulary: set[str], fallback: str) -> str:
    words = sorted(vocabulary)[:4]
    if words:
        return (f"borrow the reference's {kind} language around "
                + ", ".join(words) + " — as a principle, never a copy")
    return fallback


def build_influence_plan(task, approved) -> dict:
    """material_influence_plan/1.0 — design principles derived from the
    approved references' own metadata. Deterministic; locator-free."""
    references = []
    from apps.pipeline.services.materials_retrieval import pins
    for row in approved:
        vocab = _tokens(row.title.replace("-", " ")) | _tokens(row.description)
        references.append({
            "reference_id": row.pk,
            "library_item_id": Path(row.library_item_id).name[:120],
            "source_type": row.source_type,
            "permission": row.permission_status,
            "permitted_analysis": list(PERMITTED_ANALYSIS),
            "palette_influence": _influence_line(
                "palette", vocab & {"gold", "pink", "blush", "ivory", "cream",
                                    "pastel", "peach", "mint", "rose"},
                "analyze the reference's palette balance and tonal layering; "
                "never sample it verbatim"),
            "typography_influence": _influence_line(
                "typographic", vocab & {"editorial", "serif", "sans",
                                        "condensed", "minimal", "type"},
                "study the reference's typographic scale and hierarchy "
                "conventions"),
            "composition_influence": (
                "apply a comparable degree of visual density and hierarchy "
                "discipline; compose a NEW layout"),
            "motif_influence": _influence_line(
                "motif", vocab & {"floral", "line", "linework", "wave",
                                  "halo", "dot", "dots", "particle",
                                  "pattern", "ornament", "abstract"},
                "generalize the reference's motif treatment into a new, "
                "original system"),
            "texture_influence": _influence_line(
                "texture", vocab & {"marble", "silk", "satin", "glitter",
                                    "shimmer", "texture", "gradient"},
                "note how the reference layers texture without crowding "
                "the face"),
            "finishing_influence": (
                "translate the reference's finish discipline (foil, emboss, "
                "spot UV) into restrained, production-plausible treatments"),
            "prohibited_from_copying": list(PROHIBITED_FROM_COPYING),
            "similarity_risk_note": (
                "the generated design must remain clearly distinguishable "
                "from this reference; shared principles, never a shared "
                "composition"),
        })
    plan = {
        "schema_version": INFLUENCE_SCHEMA,
        "task_id": task.pk,
        "references": references,
        # Day 7 §3: the library pins (content hash + role) — a changed pin changes this plan and its hash
        "library_pins": pins(approved),
        "principles": [
            "use the references' balance of color fields to create depth",
            "borrow concepts (layered micro-linework, tonal framing, "
            "asymmetric hierarchy) — never compositions",
            "match a comparable degree of visual density",
            "keep every influence production-plausible and native-vector "
            "reconstructable",
        ],
        "production_use_granted": False,
    }
    _assert_no_locator(plan)
    return plan


def _assert_no_locator(plan: dict) -> None:
    """Fail closed on leakage: the plan describes principles; a file locator
    in it would let a downstream consumer fetch the asset."""
    blob = json.dumps(plan).lower()
    for marker in _LOCATOR_MARKERS:
        if marker in blob:
            raise AssertionError(
                f"influence plan contains a file locator marker {marker!r} — "
                "plans carry principles, never assets")


def plan_hash(plan: dict) -> str:
    return hashlib.sha256(
        json.dumps(plan, sort_keys=True).encode()).hexdigest()


@transaction.atomic
def approve_concept_references(task, user, ids) -> dict:
    """The HUMAN approval action: mark 2–4 of this task's candidates
    USER_APPROVED_FOR_CONCEPT_REFERENCE and build the influence plan.
    Anything else refuses with a stable code. Grants concept reference only —
    never production use."""
    from apps.pipeline.models import ConceptInfluencePlan, ConceptReference

    ids = [int(v) for v in (ids or [])]
    if not (APPROVE_MIN <= len(set(ids)) <= APPROVE_MAX):
        raise ConceptReferenceError(
            REFERENCE_APPROVAL_COUNT_OUT_OF_RANGE,
            f"select between {APPROVE_MIN} and {APPROVE_MAX} references "
            f"(got {len(set(ids))})")
    rows = list(ConceptReference.objects.select_for_update()
                .filter(pk__in=ids))
    if len(rows) != len(set(ids)):
        raise ConceptReferenceError(
            REFERENCE_NOT_A_CANDIDATE,
            "one or more selected references do not exist")
    for row in rows:
        if row.task_id != task.pk:
            raise ConceptReferenceError(
                REFERENCE_WRONG_TASK,
                f"reference {row.pk} belongs to another task")

    now = timezone.now()
    for row in rows:
        row.permission_status = ConceptReference.PERMISSION_APPROVED
        row.approved_by = user
        row.approved_at = now
        row.save(update_fields=["permission_status", "approved_by",
                                "approved_at"])
    # everything not chosen this round returns to CANDIDATE (a previous
    # approval the user did not re-select is no longer approved)
    (ConceptReference.objects.filter(task=task)
     .exclude(pk__in=[r.pk for r in rows])
     .filter(permission_status=ConceptReference.PERMISSION_APPROVED)
     .update(permission_status=ConceptReference.PERMISSION_CANDIDATE,
             approved_by=None, approved_at=None))

    plan = build_influence_plan(task, rows)
    digest = plan_hash(plan)
    ConceptInfluencePlan.objects.update_or_create(
        task=task, defaults={"schema_version": INFLUENCE_SCHEMA,
                             "plan": plan, "plan_hash": digest,
                             "created_by": user})
    return {"approved_ids": sorted(r.pk for r in rows),
            "plan_hash": digest, "schema_version": INFLUENCE_SCHEMA}


def approved_references(task):
    from apps.pipeline.models import ConceptReference
    return list(ConceptReference.objects.filter(
        task=task,
        permission_status=ConceptReference.PERMISSION_APPROVED))


def reference_file_path(row) -> Path:
    """Absolute path of a reference's displayable file, bounded to its
    declared root (read-only use)."""
    from apps.pipeline.services import materials_retrieval as mr
    if row.image_root == "previews":          # Day 7: a library file pictured through its preview, named by content hash
        root = mr.previews_root()
    elif row.image_root == "house":           # Day 7: a house artwork through its Day 5 page preview
        root = mr.house_index_path().parent
    else:
        root = (Path(settings.MEDIA_ROOT) if row.image_root == "media"
                else materials_root())
    path = (root / row.image_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise AssertionError("concept-reference path escapes its root") from exc
    if row.image_root == 'materials':
        # Day 6 migration: a pre-migration path resolves through the manifest to the file's new place.
        # Mapping only: library ids are `materials:<sha>`, `ai:<name>` or `design_reference:<pk>`, so an
        # id is not a byte pin here; placement law (materials_placement) pins bytes where they are used.
        from apps.ire.materials_paths import resolve_material_file
        path = resolve_material_file(row.image_path, repo_root=root)
    return path


__all__ = [
    "build_candidates", "approve_concept_references", "approved_references",
    "build_influence_plan", "plan_hash", "reference_file_path",
    "materials_root", "ConceptReferenceError", "INFLUENCE_SCHEMA",
    "APPROVE_MIN", "APPROVE_MAX", "PROHIBITED_FROM_COPYING",
    "REFERENCE_APPROVAL_COUNT_OUT_OF_RANGE", "REFERENCE_NOT_A_CANDIDATE",
    "REFERENCE_WRONG_TASK",
]
