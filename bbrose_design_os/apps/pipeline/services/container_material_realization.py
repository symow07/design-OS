"""Material-influence realization for the native container (Phase 2B-3A,
§5).

Reuses the Phase-2A task-scoped approval + influence plan wholesale
(``concept_references``): §3 approved references + §4 ``material_influence_plan
/1.0`` already exist and are provider-free and locator-guarded. This adds §5 —
``material_influence_realization/1.0`` — which maps each approved reference's
CLAIMED influence to an emitted MANIFESTATION in the reconstructed document.

Honest status discipline (per the "don't gate on unverifiable signals" rule):
* ``REALIZED``        tied to a concrete emitted swatch / group / text run
* ``NOT_REALIZED``    only when a SPECIFIC claim the doc demonstrably lacks
                      (a name was expected but no live text was emitted)
* ``REVIEW_REQUIRED`` principle-level influences (motif/composition) — present
                      or not, absence is not a hard failure
* ``NOT_APPLICABLE``  finish/texture (deferred to 2B-3B) and when there are no
                      approved references

Only a real ``NOT_REALIZED`` yields ``MATERIAL_INFLUENCE_NOT_REALIZED``. The
report references items by id only — never a file locator (a path in a
persisted spec_sheet would be a leak). This is a PRODUCTION-READINESS concern,
so its code never enters the reconstruction ``blockers``.
"""
from __future__ import annotations

import json

SCHEMA = "material_influence_realization/1.0"
MATERIAL_INFLUENCE_NOT_REALIZED = "MATERIAL_INFLUENCE_NOT_REALIZED"

REALIZED = "REALIZED"
PARTIALLY_REALIZED = "PARTIALLY_REALIZED"
NOT_REALIZED = "NOT_REALIZED"
NOT_APPLICABLE = "NOT_APPLICABLE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

_LOCATOR_MARKERS = ("materials/", "media/", "/users/", ".png", ".jpg",
                    ".jpeg", ".webp", ".ai", ".pdf", ".eps")


def _assert_no_locator(report: dict) -> None:
    blob = json.dumps(report).lower()
    for marker in _LOCATOR_MARKERS:
        if marker in blob:
            raise AssertionError(
                f"realization report contains a file locator {marker!r} — "
                "reports reference items by id, never assets")


def _emitted(doc) -> dict:
    """What the reconstructed document actually contains, by kind."""
    has_swatch = has_text = has_motif = False
    for node, _ in doc.walk():
        name = str(getattr(node, "name", ""))
        if node.type in ("rect", "path") and name.startswith("swatch-"):
            has_swatch = True
        elif node.type == "text":
            has_text = True
        elif node.type == "group" and name.startswith("motif-"):
            has_motif = True
    return {"swatch": has_swatch, "text": has_text, "motif": has_motif}


def not_applicable_realization(task) -> dict:
    """The common container path: no approved references → nothing claimed."""
    report = {"schema_version": SCHEMA, "task_id": getattr(task, "pk", None),
              "state": "NO_APPROVED_REFERENCES", "references": [],
              "codes": []}
    _assert_no_locator(report)
    return report


def build_realization(task, doc, influence_plan: dict) -> dict:
    """§5 realization report: per approved reference, the emitted manifestation
    of each claimed influence. ``influence_plan`` is the persisted
    material_influence_plan/1.0 (locator-free)."""
    emitted = _emitted(doc)
    refs_out = []
    any_not_realized = False
    for ref in (influence_plan or {}).get("references", []):
        influences = {}

        # palette — concrete: realized when named swatches are emitted
        influences["palette"] = {
            "status": REALIZED if emitted["swatch"] else REVIEW_REQUIRED,
            "emitted": "named-swatches" if emitted["swatch"] else ""}

        # typography — concrete: a name was expected, so live text must exist
        if emitted["text"]:
            influences["typography"] = {"status": REALIZED,
                                        "emitted": "live-text"}
        else:
            influences["typography"] = {"status": NOT_REALIZED, "emitted": ""}
            any_not_realized = True

        # motif — principle-level: present or not, absence is not a hard fail
        influences["motif"] = {
            "status": REALIZED if emitted["motif"] else REVIEW_REQUIRED,
            "emitted": "motif-group" if emitted["motif"] else ""}

        # composition — principle-level, structural
        influences["composition"] = {"status": REVIEW_REQUIRED, "emitted": ""}

        # texture / finishing — separation masks are deferred to 2B-3B
        influences["texture"] = {"status": NOT_APPLICABLE, "emitted": ""}
        influences["finishing"] = {"status": NOT_APPLICABLE, "emitted": ""}

        refs_out.append({
            "reference_id": ref.get("reference_id"),
            "library_item_id": ref.get("library_item_id"),
            "permission": ref.get("permission"),
            "influences": influences})

    report = {
        "schema_version": SCHEMA,
        "task_id": getattr(task, "pk", None),
        "state": "MEASURED" if refs_out else "NO_APPROVED_REFERENCES",
        "influence_plan_hash": (influence_plan or {}).get("plan_hash", ""),
        "references": refs_out,
        "codes": [MATERIAL_INFLUENCE_NOT_REALIZED] if any_not_realized else [],
    }
    _assert_no_locator(report)
    return report


__all__ = [
    "SCHEMA", "MATERIAL_INFLUENCE_NOT_REALIZED", "REALIZED",
    "PARTIALLY_REALIZED", "NOT_REALIZED", "NOT_APPLICABLE", "REVIEW_REQUIRED",
    "build_realization", "not_applicable_realization",
]
