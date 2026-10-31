"""Canonical technical-readiness vocabulary — migration guard.

`READY_AFTER_RIGHTS_REVIEW` named the RIGHTS axis from inside the TECHNICAL axis,
which the two-axis rule forbids. It is retired in favour of
`TECHNICALLY_USABLE_WITH_CAVEATS`.

This was a **terminology correction only**: no classification logic, threshold,
rights status, ownership status or eligibility changed. These tests pin exactly
that — the vocabulary is canonical and shared across every DIP stage, the retired
token can never be machine-emitted, legacy stored data normalizes forward with
provenance, and the C1 result counts are bit-for-bit what they were before.
"""
from __future__ import annotations

import json

from tools.dip0c import assetcandidate as AC
from tools.dip0c import config as C
from tools.dip0c import run_c1

RETIRED = "READY_AFTER_RIGHTS_REVIEW"
CANONICAL = "TECHNICALLY_USABLE_WITH_CAVEATS"

# The C1 pilot totals measured BEFORE the migration. A terminology change must not
# move a single record.
C1_BASELINE_READINESS = {
    CANONICAL: 14,                      # was READY_AFTER_RIGHTS_REVIEW: 14
    "NEEDS_VECTOR_RECONSTRUCTION": 1,
    "NEEDS_CLEANUP": 2,
    "REFERENCE_ONLY": 4,
}
C1_BASELINE_FILES = 24
C1_BASELINE_OVERRIDES = 2


# --- the retired value can never be machine-emitted --------------------------
def test_retired_constant_is_gone():
    assert not hasattr(C, "READY_AFTER_RIGHTS_REVIEW")


def test_retired_value_refused_by_guard():
    try:
        C.readiness_value(RETIRED)
    except C.ReadinessVocabularyViolation as e:
        assert CANONICAL in str(e)
    else:
        raise AssertionError("retired readiness value was not refused")


def test_unknown_value_refused_by_guard():
    try:
        C.readiness_value("TOTALLY_MADE_UP")
    except C.ReadinessVocabularyViolation:
        pass
    else:
        raise AssertionError("unknown readiness value was not refused")


def test_retired_value_not_in_canonical_vocabulary():
    assert RETIRED not in C.TECHNICAL_READINESS
    assert CANONICAL in C.TECHNICAL_READINESS
    assert C.READY_TECHNICALLY_USABLE_WITH_CAVEATS == CANONICAL


# --- legacy stored data normalizes forward, with provenance ------------------
def test_normalize_legacy_value():
    assert C.normalize_readiness(RETIRED) == (CANONICAL, True)


def test_normalize_leaves_canonical_untouched():
    for v in C.TECHNICAL_READINESS:
        assert C.normalize_readiness(v) == (v, False)


def test_normalize_block_records_the_migration_in_provenance():
    legacy = {"value": RETIRED, "evidence": ["clean editable vector geometry"],
              "confidence": 0.6}
    out = C.normalize_readiness_block(legacy)
    assert out["value"] == CANONICAL
    assert out["vocabulary_migrated_from"] == RETIRED
    assert any("normalized from retired vocabulary" in e for e in out["evidence"])
    # the original block is not mutated
    assert legacy["value"] == RETIRED


def test_normalize_block_is_a_noop_for_canonical_data():
    block = {"value": CANONICAL, "evidence": [], "confidence": 0.6}
    assert C.normalize_readiness_block(block) is block


# --- one vocabulary across C1 and C2 ----------------------------------------
def test_c1_and_c2_share_one_readiness_vocabulary():
    # C1 emits values from the canonical tuple...
    rec = _c1_record()
    assert rec["technical_readiness"]["value"] in C.TECHNICAL_READINESS
    # ...and C2's AssetCandidate axis A is the same vocabulary, merely UNSCORED
    # until C2b scores it (it must not invent a parallel vocabulary).
    a = AC.technical_readiness_unscored()
    assert a["value"] is None
    assert a["status"] == C.READY_UNSCORED
    assert C.READY_UNSCORED not in C.TECHNICAL_READINESS   # a status, not a verdict


# --- rights remain a separate axis ------------------------------------------
def test_readiness_never_grants_rights():
    rec = _c1_record()
    assert rec["technical_readiness"]["value"] == CANONICAL
    r = rec["rights"]
    assert r["ownership_status"] == "unverified"
    assert r["license_status"] == "unverified"
    assert not any(r[k] for k in ("commercial_use", "modification", "embedding",
                                  "redistribution"))
    g = rec["retrieval_gate"]
    assert not any(g[k] for k in ("retrieval", "automatic_use", "embedding",
                                  "production_use"))


def _c1_record():
    """A real C1 record for a clean vector asset (the value that was renamed)."""
    pilot = C.load_pilot()
    entry = next(e for e in pilot
                 if e["test_role"] == "clean_vector_high_complexity")
    return run_c1.audit_entry(entry, {})


# --- the migration changed no counts and no classifications -----------------
def test_migration_preserves_c1_counts_and_classifications():
    rc = run_c1.main()
    assert rc == 0
    recon = json.loads((C.OUT_REPORTS / "c1_reconciliation.json")
                       .read_text(encoding="utf-8"))
    assert recon["pilot_count"] == C1_BASELINE_FILES
    assert recon["technical_readiness_totals"] == C1_BASELINE_READINESS
    assert len(recon["classification_overrides"]) == C1_BASELINE_OVERRIDES
    assert recon["jpeg_shell_files"] == ["5955567.ai"]
    assert recon["parser_failures"] == []
    # and the retired token appears nowhere in the regenerated output
    assert recon["invariants"]["no_retired_readiness_vocabulary"] is True
    assert recon["invariants"]["readiness_vocabulary_canonical"] is True
