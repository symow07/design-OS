"""Structure selection persistence + the confirmation gate (Phase 2A-6, §4–5).

Owns the durable structural decision on `DielineJob.structure_selection` and
the human confirmation that must precede artwork composition.

Restart semantics (the rule the whole phase leans on): once a structure is
persisted, a retry NEVER re-selects. `load_structure_record` returns exactly
what was stored, and `assert_unchanged` refuses to proceed if the geometry
hash for the persisted parameters no longer matches — a silent die change is
a hard stop, not a warning.

Confirmation is idempotent for the same geometry hash and invalidated by any
change of template, version or parameters (a different die needs a fresh
human decision). No DecisionEvent and no permission are created here: this
is a technical structure confirmation, not design authority.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.dielines import registry

# Errors surfaced to the API layer.
STRUCTURE_NOT_SELECTED = "STRUCTURE_NOT_SELECTED"
STRUCTURE_NOT_CONFIRMED = "STRUCTURE_NOT_CONFIRMED"
STRUCTURE_CHANGED = "STRUCTURE_CHANGED_SINCE_CONFIRMATION"
STRUCTURE_ALREADY_CONFIRMED = "STRUCTURE_ALREADY_CONFIRMED"


class StructureError(ValueError):
    """Structural state prevents the requested step. Carries a stable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def build_structure_record(
    selection, parameters: dict, *, assumptions=None,
    dimension_reconciliation: dict | None = None,
    generic_accepted: bool = False,
) -> dict:
    """The durable record for a resolved :class:`TemplateSelection`."""
    if not selection.resolved:
        raise StructureError(
            STRUCTURE_NOT_SELECTED,
            "cannot persist an unresolved template selection; the structure "
            "confirmation gate must run first",
        )
    defn = registry.resolve(selection.template_id, selection.version)
    return {
        "template_id": defn.template_id,
        "template_version": defn.version,
        "parameters": dict(parameters),
        "source": selection.source,
        "confidence": selection.confidence,
        "reasons": list(selection.reasons),
        "assumptions": list(assumptions or ()),
        "geometry_hash": registry.geometry_hash(
            defn.template_id, defn.version, parameters),
        "generic_accepted": bool(generic_accepted),
        "dimension_reconciliation": dimension_reconciliation or {},
        "confirmed_by": "",
        "confirmed_at": "",
        "panel_sequence": defn.panel_order(),
        "closure_type": defn.closure_type,
        "glue_seam_position": defn.glue_seam_position,
    }


def save_structure_record(job, record: dict) -> dict:
    """Persist the record on the job (single field write)."""
    job.structure_selection = record
    job.template_type = record["template_id"]
    job.save(update_fields=["structure_selection", "template_type"])
    return record


def load_structure_record(job) -> dict:
    """The persisted structure, or {} for a legacy job.

    A restart reads this and uses it verbatim — it never re-runs selection.
    """
    return dict(job.structure_selection or {})


def is_confirmed(job) -> bool:
    rec = load_structure_record(job)
    return bool(rec.get("confirmed_at")) and _hash_matches(rec)


def _hash_matches(record: dict) -> bool:
    if not record:
        return False
    expected = registry.geometry_hash(
        record.get("template_id", ""), record.get("template_version", ""),
        record.get("parameters") or {},
    )
    return expected == record.get("geometry_hash")


def assert_unchanged(job) -> dict:
    """Return the persisted record, refusing if it no longer describes the
    geometry its hash was taken over."""
    rec = load_structure_record(job)
    if not rec:
        raise StructureError(STRUCTURE_NOT_SELECTED,
                             "no structure has been selected for this job")
    if not _hash_matches(rec):
        raise StructureError(
            STRUCTURE_CHANGED,
            "the persisted structure no longer matches its geometry hash — "
            "the template, version or parameters changed after confirmation; "
            "re-confirm the structure before generating artwork",
        )
    return rec


def assert_confirmed(job) -> dict:
    """Gate used by artwork composition. Never generates artwork on an
    unconfirmed or drifted structure."""
    rec = assert_unchanged(job)
    if not rec.get("confirmed_at"):
        raise StructureError(
            STRUCTURE_NOT_CONFIRMED,
            "the structure has not been confirmed — artwork composition is "
            "blocked until a reviewer confirms the die",
        )
    return rec


@transaction.atomic
def confirm_structure(job, user, *, geometry_hash: str | None = None) -> dict:
    """Record the human structure confirmation. Idempotent per hash.

    ``geometry_hash``, when supplied by the caller, must match the persisted
    structure — a reviewer cannot confirm a die they were not shown.

    The caller's ``job`` instance is refreshed in place, so a caller that
    keeps using it never reads a stale pre-confirmation record.
    """
    locked = type(job).objects.select_for_update().get(pk=job.pk)
    rec = assert_unchanged(locked)
    # 2A-9 §8: a structure this job has permanently invalidated (e.g. the
    # task-50 90×25×92 die rejected against the customer reference) can
    # never be re-confirmed, whatever selection path produced it again.
    banned = (locked.extraction_result or {}).get("banned_geometry_hashes", [])
    if rec.get("geometry_hash") in banned:
        raise StructureError(
            "STRUCTURE_PERMANENTLY_INVALIDATED",
            "this exact geometry was permanently invalidated for this job "
            "(rejected against the supplied structural reference) — it "
            "cannot be confirmed again",
        )
    if geometry_hash and geometry_hash != rec["geometry_hash"]:
        raise StructureError(
            STRUCTURE_CHANGED,
            "the structure changed since it was presented — reload the "
            "structure confirmation page and review the current die",
        )
    # 2A-9 §6/§7: the CUSTOMER-GRADE archetypes (task #50's opposed die, the
    # ecma_ste archetype) follow an APPROVE-FOR-PHYSICAL-TEST-then-confirm
    # flow — their confirmation gate itself refuses until an exact-hash
    # FIT_PASS. 2A-9E: STE/RTE 1.2 (confirmation_requires_physical_fit_pass
    # = False) instead proceed through confirmation + artwork with the
    # physical blocker at Gate 2 only. The flag draws that line.
    # [§BH70(3) (§BH70 LIVE), his words: "A physical sample is never required to finish a design (a colleague
    # test-fits; that is not the system's job)." The confirmation of a CUSTOMER-GRADE archetype refused here until an
    # exact-hash FIT_PASS — and with it the artwork — as the paragraph above says; that refusal is retired. The
    # template is still resolved here, an unknown one refused by name, and its untested geometry is said on the
    # projection (`physical_validation_blockers`), never a hold.]
    registry.resolve(rec["template_id"], rec.get("template_version"))
    if not rec.get("confirmed_at"):
        rec["confirmed_by"] = getattr(user, "username", "") or ""
        rec["confirmed_at"] = timezone.now().isoformat()
        save_structure_record(locked, rec)
    job.structure_selection = rec
    return rec


def invalidate_confirmation(job, reason: str) -> dict:
    """Drop a confirmation because the structure is being changed. The next
    generation must be confirmed again."""
    rec = load_structure_record(job)
    if not rec:
        return rec
    rec["confirmed_by"] = ""
    rec["confirmed_at"] = ""
    rec.setdefault("reasons", []).append(f"confirmation invalidated: {reason}")
    return save_structure_record(job, rec)


def structure_presentation(job, coords=None) -> dict:
    """Everything the confirmation page must show (section 5).

    Pure data — the renderer decides presentation. Includes the panel map,
    flap/notch inventory, compensation assumptions and the collision result,
    so the reviewer confirms the actual die, not a description of it.
    """
    rec = load_structure_record(job)
    if not rec:
        return {}
    defn = registry.resolve(rec["template_id"], rec.get("template_version"))
    out = {
        "template_id": defn.template_id,
        "template_version": defn.version,
        "template_label": defn.label,
        # 2A-9E §3: the version's new-selection standing, shown on the
        # structure-review screen (never omit the version).
        "new_selection_class": (
            registry.NEW_SELECTION_RECOMMENDED
            if defn.version == registry.recommended_corrected_version(
                defn.template_id)
            else (registry.NEW_SELECTION_LEGACY
                  if registry.recommended_corrected_version(defn.template_id)
                  else "PRODUCTION_CURRENT")),
        "recommended_version": registry.recommended_corrected_version(
            defn.template_id) or defn.version,
        "panel_sequence": defn.panel_order(),
        "panel_sequence_label": defn.panel_sequence_label(),
        "dimension_semantics": defn.dimension_semantics,
        "closure_type": defn.closure_type,
        "glue_seam_position": defn.glue_seam_position,
        "board_compensation_model": defn.board_compensation_model,
        "flap_capabilities": sorted(defn.flap_capabilities),
        "notch_capabilities": sorted(defn.notch_capabilities),
        "provisional": defn.provisional,
        # Production eligibility must be visible AT the gate, not discovered
        # at Gate 2 (Phase 2A-6A UI review).
        "production_ready": defn.production_ready,
        "structure_status": defn.structure_status,
        "ineligibility_code": defn.ineligibility_code,
        "structural_limitations": list(defn.structural_limitations),
        "template_notes": list(defn.notes),
        "parameters": rec.get("parameters", {}),
        "selection_source": rec.get("source"),
        "selection_confidence": rec.get("confidence"),
        "selection_reasons": rec.get("reasons", []),
        "assumptions": rec.get("assumptions", []),
        "geometry_hash": rec.get("geometry_hash"),
        "confirmed_at": rec.get("confirmed_at", ""),
        "confirmed_by": rec.get("confirmed_by", ""),
        "dimension_reconciliation": rec.get("dimension_reconciliation", {}),
    }
    if coords is not None:
        from apps.dielines.exporters.structural_comparison import (
            geometry_integrity,
        )
        d = coords.derived or {}
        integrity = geometry_integrity(coords)
        out["geometry_integrity"] = integrity
        out["cut_fold_conflict_mm"] = round(
            sum(s["shared_mm"] for s in integrity["cut_fold_conflict_segments"]), 2)
        out["flat_mm"] = [coords.flat_width_mm, coords.flat_height_mm]
        out["panels"] = [
            {"name": p.name, "width_mm": round(p.width, 2),
             "height_mm": round(p.height, 2)} for p in coords.panels
        ]
        out["components"] = [cid for cid, _ in coords.components]
        out["slits"] = [s[0] for s in coords.stadium_cutouts]
        out["entry_cut_segments"] = len(coords.slit_lines)
        out["geometry_notes"] = list(d.get("notes") or [])
        # 2A-9-CORR-2 §6: the major-flap attachment must be explicit on the
        # review screen — panel assignment is the review contract, never
        # inferred from the template name.
        panel_label = {"main_a": "MAIN PANEL A", "main_b": "MAIN PANEL B",
                       "back": "MAIN PANEL A (first main)",
                       "front": "MAIN PANEL B (second main)"}
        if d.get("top_tuck_panel"):
            out["tuck_attachment"] = {
                "top": panel_label.get(d["top_tuck_panel"],
                                       str(d["top_tuck_panel"])),
                "bottom": panel_label.get(d.get("bottom_tuck_panel"),
                                          str(d.get("bottom_tuck_panel"))),
                "opposing": d.get("top_tuck_panel")
                            != d.get("bottom_tuck_panel"),
            }
        if d.get("closure_orientation"):
            out["closure_label"] = (
                "OPPOSING TUCK / REFERENCE-MATCHED PROVISIONAL"
                if d["closure_orientation"] == "OPPOSING_TUCK"
                else d["closure_orientation"])
        if d.get("attachment_map"):
            out["attachment_map"] = d["attachment_map"]

    # ---- 2A-9: confirmability, physical-validation blocker, artifacts ----
    # The projection must make the REJECTED die unrenderable as active and
    # the provisional die non-confirmable, so the UI cannot re-arm either.
    extraction = job.extraction_result or {}
    banned = extraction.get("banned_geometry_hashes", [])
    out["banned"] = out["geometry_hash"] in banned
    out["physical_validation_required"] = (
        defn.ineligibility_code
        == registry.PHYSICAL_SAMPLE_VALIDATION_REQUIRED)
    out["confirmable"] = not out["banned"]
    if out["physical_validation_required"]:
        from apps.dielines.services.physical_validation import (
            promotion_blockers,
        )
        # §BH70(3): what the sample must show is said, as information — it no longer makes the structure
        # unconfirmable, and the next step is its confirmation (it was APPROVE_FOR_PHYSICAL_TEST, then
        # RECORD_PHYSICAL_RESULT)
        out["physical_validation_blockers"] = promotion_blockers(
            job, template_key=defn.key,
            geometry_hash=out["geometry_hash"] or "")
        approval = extraction.get("physical_test_approval") or {}
        if approval.get("geometry_hash") == out["geometry_hash"]:
            out["physical_test_approval"] = approval
        out["next_action"] = "CONFIRM" if out["confirmable"] else "NONE"
        out["provisional_labels"] = [
            "PROVISIONAL STRUCTURE", "PHYSICAL SAMPLE REQUIRED",
            "NOT APPROVED FOR MASS PRODUCTION"]
    manifest = extraction.get("provisional_preview") or {}
    if manifest.get("geometry_hash") == out["geometry_hash"]:
        out["provisional_artifacts"] = _artifact_urls(manifest)
        out["content_hashes"] = manifest.get("content_hashes")
        summary = _artifact_json(manifest, "collision_report")
        if summary:
            out["collision_summary"] = summary.get("archetype_checks")
        comp = _artifact_json(manifest, "compensation_report")
        if comp:
            out["compensation_assumptions"] = (
                (comp.get("compensations") or [])
                + (comp.get("assumptions") or []))
            out["dimension_model"] = comp.get("dimension_model")
    return out


def _artifact_urls(manifest: dict) -> dict:
    """Map provisional-preview artifact paths to MEDIA_URL links."""
    import os

    from django.conf import settings

    urls = {}
    root = str(settings.MEDIA_ROOT)
    for key, path in (manifest.get("artifacts") or {}).items():
        p = str(path)
        if os.path.isabs(p) and p.startswith(root) and os.path.exists(p):
            rel = os.path.relpath(p, root)
            urls[key] = f"{settings.MEDIA_URL}{rel}"
    return urls


def _artifact_json(manifest: dict, key: str) -> dict | None:
    import json
    import os

    path = (manifest.get("artifacts") or {}).get(key)
    if not path or not os.path.exists(str(path)):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


__all__ = [
    "StructureError",
    "STRUCTURE_NOT_SELECTED",
    "STRUCTURE_NOT_CONFIRMED",
    "STRUCTURE_CHANGED",
    "build_structure_record",
    "save_structure_record",
    "load_structure_record",
    "confirm_structure",
    "invalidate_confirmation",
    "assert_unchanged",
    "assert_confirmed",
    "is_confirmed",
    "structure_presentation",
]
