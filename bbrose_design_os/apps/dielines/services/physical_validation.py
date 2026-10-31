"""Physical sample validation record (Phase 2A-9 §7).

A provisional archetype (OPEN_SOURCE_FORMULA_ADAPTED_PROVISIONAL) is only
geometry until a human folds a printed 100%-scale sample and records what
the board actually did. This service persists that record with a BOUNDED
outcome vocabulary and measured corrections in millimetres.

Rules enforced here and pinned by tests:
  * only outcomes from :data:`ALLOWED_OUTCOMES` may be recorded;
  * a visual/screenshot review can never be recorded as FIT_PASS —
    the record requires ``sample_printed_at_100pct=True``;
  * only FIT_PASS may advance the template from provisional 0.1 to a
    confirmed internal version (:func:`promotion_blockers`); recording it
    here does NOT publish a new version — that is a separate, human,
    code-reviewed step.
"""
from __future__ import annotations

from django.utils import timezone

FIT_PASS = "FIT_PASS"

ALLOWED_OUTCOMES = frozenset({
    FIT_PASS,
    "FIT_TOO_TIGHT",
    "FIT_TOO_LOOSE",
    "DEPTH_INCORRECT",
    "HEIGHT_INCORRECT",
    "DUST_FLAP_COLLISION",
    "MAJOR_TUCK_ENTRY_FAILURE",
    "LOCKING_SLIT_FAILURE",
    "GLUE_FLAP_INTERFERENCE",
    "BOARD_COMPENSATION_FAILURE",
    "PANEL_NOT_SQUARE",
    "OTHER_MEASURED_CORRECTION_REQUIRED",
    # 2A-9E §5 additional accepted names (superset — existing names kept)
    "TUCK_ENTRY_FAILURE",
    "SLIT_OR_NOTCH_FAILURE",
})

_RECORDS_KEY = "physical_validation_records"


class PhysicalValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def record_physical_validation(
    job, user, *, template_key: str, geometry_hash: str, outcome: str,
    sample_printed_at_100pct: bool,
    board_thickness_mm: float | None = None,
    measured_corrections_mm: dict | None = None,
    notes: str = "",
) -> dict:
    """Persist one bounded physical-test result on the job."""
    if outcome not in ALLOWED_OUTCOMES:
        raise PhysicalValidationError(
            "PHYSICAL_OUTCOME_UNKNOWN",
            f"outcome {outcome!r} is not in the bounded vocabulary "
            f"{sorted(ALLOWED_OUTCOMES)}")
    # 2A-9-CORR-2 §7: a permanently invalidated geometry (e.g. a rejected
    # closure topology) can never receive a physical result — its test
    # sheet must not even be printed, let alone recorded as FIT_PASS.
    banned = (job.extraction_result or {}).get("banned_geometry_hashes", [])
    if geometry_hash in banned:
        raise PhysicalValidationError(
            "PHYSICAL_RESULT_FOR_INVALIDATED_GEOMETRY",
            "this geometry hash was permanently invalidated for this job "
            "(rejected structure) — no physical result may be recorded "
            "against it")
    if outcome == FIT_PASS and not sample_printed_at_100pct:
        raise PhysicalValidationError(
            "PHYSICAL_SAMPLE_REQUIRED",
            "FIT_PASS requires a sample printed at exact 100% scale — a "
            "visual or screenshot review is never a physical fit result")
    corrections = {}
    for name, value in (measured_corrections_mm or {}).items():
        try:
            corrections[str(name)] = round(float(value), 3)
        except (TypeError, ValueError) as exc:
            raise PhysicalValidationError(
                "PHYSICAL_CORRECTION_NOT_NUMERIC",
                f"measured correction {name!r} must be millimetres, got "
                f"{value!r}") from exc
    record = {
        "template_key": template_key,
        "geometry_hash": geometry_hash,
        "outcome": outcome,
        "sample_printed_at_100pct": bool(sample_printed_at_100pct),
        "board_thickness_mm": board_thickness_mm,
        "measured_corrections_mm": corrections,
        "notes": notes[:1000],
        "recorded_by": getattr(user, "username", str(user)),
        "recorded_at": timezone.now().isoformat(),
    }
    payload = dict(job.extraction_result or {})
    payload.setdefault(_RECORDS_KEY, []).append(record)
    job.extraction_result = payload
    job.save(update_fields=["extraction_result"])
    return record


def validation_records(job, template_key: str | None = None) -> list[dict]:
    records = list(
        (getattr(job, "extraction_result", None) or {}).get(_RECORDS_KEY, []))
    if template_key:
        records = [r for r in records if r.get("template_key") == template_key]
    return records


def promotion_blockers(job, *, template_key: str, geometry_hash: str) -> list[str]:
    """Why the provisional template may NOT be promoted yet. Empty only when
    a physical FIT_PASS exists for exactly this geometry."""
    records = validation_records(job, template_key)
    if not records:
        return ["PHYSICAL_SAMPLE_VALIDATION_REQUIRED: no physical test has "
                "been recorded for this template"]
    latest = records[-1]
    blockers: list[str] = []
    if latest.get("outcome") != FIT_PASS:
        blockers.append(
            f"PHYSICAL_FIT_NOT_PASSED: latest recorded outcome is "
            f"{latest.get('outcome')!r}")
    if latest.get("geometry_hash") != geometry_hash:
        blockers.append(
            "PHYSICAL_RESULT_FOR_DIFFERENT_GEOMETRY: the recorded test was "
            "for another geometry hash — reprint and retest")
    if not latest.get("sample_printed_at_100pct"):
        blockers.append("PHYSICAL_SAMPLE_REQUIRED: the recorded test was not "
                        "printed at 100% scale")
    return blockers


def dimensional_family_blockers(job, *, template_key: str,
                                family_hashes: list[str],
                                minimum_passes: int = 3) -> list[str]:
    """2A-9E §5: why a DIMENSIONAL FAMILY is not yet physically validated.

    A family requires multiple representative exact-hash FIT_PASSes — one
    instance pass never promotes the family. Empty list means every listed
    representative hash has a recorded FIT_PASS AND at least
    ``minimum_passes`` distinct hashes passed. This function only REPORTS;
    it never grants authority.
    """
    records = validation_records(job, template_key)
    passed = {r["geometry_hash"] for r in records
              if r.get("outcome") == FIT_PASS
              and r.get("sample_printed_at_100pct")}
    blockers: list[str] = []
    missing = [h for h in family_hashes if h not in passed]
    if missing:
        blockers.append(
            f"PHYSICAL_FAMILY_INCOMPLETE: {len(missing)} of "
            f"{len(family_hashes)} representative hashes lack a FIT_PASS")
    if len(passed & set(family_hashes)) < minimum_passes:
        blockers.append(
            f"PHYSICAL_FAMILY_INSUFFICIENT: fewer than {minimum_passes} "
            "representative passes recorded")
    return blockers


__all__ = [
    "ALLOWED_OUTCOMES", "FIT_PASS", "PhysicalValidationError",
    "record_physical_validation", "validation_records", "promotion_blockers",
    "dimensional_family_blockers",
]
