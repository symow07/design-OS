"""Container influence plan/1.1 + precise per-reference realization + similarity
risk (Phase 2B-3C, §15-§17).

Additive over the 2B-3A `material_influence_realization/1.0` (which stays as-is):
this adds the container-specific influence dimensions and — crucially — makes
each approved reference claim ONLY the dimensions its own metadata supports, so
a palette reference does not silently claim cap orientation, and two references
receive DIFFERENT realization records unless they genuinely claim the same
dimensions. Provider-free, locator-free (reference by id, never a file path).
"""
from __future__ import annotations

import re

INFLUENCE_SCHEMA = "material_influence_plan/1.1"
REALIZATION_SCHEMA = "material_influence_realization/1.1"
SIMILARITY_REVIEW = "CONTAINER_REFERENCE_SIMILARITY_REVIEW_REQUIRED"
NOT_REALIZED_CODE = "MATERIAL_INFLUENCE_NOT_REALIZED"

REALIZED = "REALIZED"
PARTIALLY_REALIZED = "PARTIALLY_REALIZED"
NOT_REALIZED = "NOT_REALIZED"
NOT_APPLICABLE = "NOT_APPLICABLE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

#: the container influence dimensions (§15) + the vocabulary that lets a
#: reference legitimately CLAIM each one.
_DIM_KEYWORDS = {
    "palette": {"gold", "pink", "blush", "ivory", "cream", "pastel", "peach",
                "mint", "rose", "color", "colour", "palette", "tonal"},
    "typography": {"type", "typographic", "serif", "sans", "condensed",
                   "editorial", "lettering", "wordmark"},
    "motif": {"floral", "line", "linework", "wave", "halo", "dot", "dots",
              "particle", "pattern", "ornament", "abstract", "botanical",
              "petal", "motif"},
    "logo_scale": {"logo", "mark", "monogram", "emblem", "crest"},
    "front_back_balance": {"front", "back", "panel", "layout", "composition"},
    "cap_body_coordination": {"cap", "lid", "closure", "top", "coordinated"},
    "label_density": {"dense", "minimal", "busy", "sparse", "clean", "density"},
    "wrap_continuation": {"wrap", "continuous", "allover", "seamless",
                          "around"},
    "finishing": {"foil", "emboss", "deboss", "gloss", "matte", "spot",
                  "varnish", "metallic"},
}
#: load-bearing dimensions whose absence (when claimed) is a real NOT_REALIZED
_LOAD_BEARING = frozenset({"palette", "typography", "motif", "logo_scale"})
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_LOCATOR_MARKERS = ("materials/", "media/", "/users/", ".png", ".jpg", ".jpeg",
                    ".webp", ".ai", ".pdf", ".eps")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(str(text or "").lower()))


def _assert_no_locator(payload) -> None:
    import json
    blob = json.dumps(payload).lower()
    for marker in _LOCATOR_MARKERS:
        if marker in blob:
            raise AssertionError(
                f"influence record contains a file locator {marker!r}")


def _claimed_dimensions(row) -> list[str]:
    vocab = _tokens(getattr(row, "title", "").replace("-", " ")) \
        | _tokens(getattr(row, "description", ""))
    dims = [d for d, kws in _DIM_KEYWORDS.items() if vocab & kws]
    return dims or ["palette"]      # a reference at least informs palette tone


def build_container_influence_plan(task, approved) -> dict:
    """material_influence_plan/1.1 — each reference claims only the dimensions
    its metadata supports (§15)."""
    from pathlib import Path
    references = []
    for row in approved:
        references.append({
            "reference_id": row.pk,
            "library_item_id": Path(row.library_item_id).name[:120],
            "permission": row.permission_status,
            "claimed_dimensions": _claimed_dimensions(row),
        })
    plan = {"schema_version": INFLUENCE_SCHEMA, "task_id": getattr(task, "pk", None),
            "container_dimensions": sorted(_DIM_KEYWORDS),
            "references": references,
            "prohibited_from_copying": [
                "copy the same layout", "trace the artwork",
                "reproduce a unique illustration",
                "recreate the same logo placement"],
            "production_use_granted": False}
    _assert_no_locator(plan)
    return plan


def _emitted(doc) -> dict:
    has = {"swatch": False, "text": False, "motif": False, "cap": False,
           "back": False, "wrap": False}
    for node, _ in doc.walk():
        name = str(getattr(node, "name", ""))
        if node.type in ("rect", "path") and name.startswith("swatch-"):
            has["swatch"] = True
        elif node.type == "text":
            has["text"] = True
        elif node.type == "group" and name.startswith("motif-"):
            has["motif"] = True
            if "WRAP" in name:
                has["wrap"] = True
        elif node.type == "group" and name.startswith("Surface-CAP"):
            has["cap"] = True
        elif node.type == "group" and name == "Surface-BODY_BACK":
            has["back"] = True
    return has


def _dimension_status(dim: str, emitted: dict, logo_used: bool) -> tuple[str, str]:
    """(status, emitted_evidence) for one claimed dimension."""
    if dim == "palette":
        return (REALIZED, "named-swatches") if emitted["swatch"] else (NOT_REALIZED, "")
    if dim == "typography":
        return (REALIZED, "live-text") if emitted["text"] else (NOT_REALIZED, "")
    if dim == "motif":
        return (REALIZED, "motif-group") if emitted["motif"] else (REVIEW_REQUIRED, "")
    if dim == "logo_scale":
        return (REALIZED, "logo") if logo_used else (REVIEW_REQUIRED, "")
    if dim == "cap_body_coordination":
        return (REALIZED, "cap-surface") if emitted["cap"] else (NOT_APPLICABLE, "")
    if dim == "front_back_balance":
        return (REALIZED, "back-surface") if emitted["back"] else (REVIEW_REQUIRED, "")
    if dim == "wrap_continuation":
        return (REALIZED, "wrap-motif") if emitted["wrap"] else (REVIEW_REQUIRED, "")
    if dim == "label_density":
        return (REVIEW_REQUIRED, "")          # measured elsewhere (§14)
    if dim == "finishing":
        return (NOT_APPLICABLE, "")           # finish masks deferred (2B-3B/2B-4)
    return (REVIEW_REQUIRED, "")


def build_container_realization(task, doc, plan: dict) -> dict:
    """material_influence_realization/1.1 — per reference, per CLAIMED
    dimension, the emitted manifestation + status (§16). Distinct references
    get distinct records because they claim distinct dimensions."""
    emitted = _emitted(doc)
    logo_used = bool((doc.metadata or {}).get("logo_zone_used"))
    refs_out, codes = [], []
    for ref in (plan or {}).get("references", []):
        dims = {}
        realized_count = 0
        for dim in ref.get("claimed_dimensions", []):
            status, evidence = _dimension_status(dim, emitted, logo_used)
            dims[dim] = {"status": status, "emitted": evidence}
            if status == REALIZED:
                realized_count += 1
            if status == NOT_REALIZED and dim in _LOAD_BEARING:
                codes.append(NOT_REALIZED_CODE)
        refs_out.append({
            "reference_id": ref.get("reference_id"),
            "library_item_id": ref.get("library_item_id"),
            "permission": ref.get("permission"),
            "claimed_dimensions": ref.get("claimed_dimensions"),
            "dimensions": dims,
            "realized_count": realized_count})
    report = {"schema_version": REALIZATION_SCHEMA,
              "task_id": getattr(task, "pk", None),
              "state": "MEASURED" if refs_out else "NO_APPROVED_REFERENCES",
              "references": refs_out, "codes": _dedup(codes)}
    _assert_no_locator(report)
    return report


def similarity_risk(realization: dict, *, threshold: int = 4) -> dict:
    """§17: a single reference realizing many dimensions risks leaning too
    close to one reference (layout/motif/logo/composition). Principle-based,
    not pixel similarity; never auto-removes the design."""
    flagged = [r["reference_id"] for r in realization.get("references", [])
               if r.get("realized_count", 0) >= threshold]
    return {"flagged_reference_ids": flagged,
            "codes": [SIMILARITY_REVIEW] if flagged else [],
            "method": "realized-dimension-count (principle-based)"}


def not_applicable_realization(task) -> dict:
    return {"schema_version": REALIZATION_SCHEMA,
            "task_id": getattr(task, "pk", None),
            "state": "NO_APPROVED_REFERENCES", "references": [], "codes": []}


def _dedup(seq):
    seen, out = set(), []
    for c in seq:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


__all__ = [
    "INFLUENCE_SCHEMA", "REALIZATION_SCHEMA", "SIMILARITY_REVIEW",
    "NOT_REALIZED_CODE", "REALIZED", "PARTIALLY_REALIZED", "NOT_REALIZED",
    "NOT_APPLICABLE", "REVIEW_REQUIRED", "build_container_influence_plan",
    "build_container_realization", "similarity_risk",
    "not_applicable_realization",
]
