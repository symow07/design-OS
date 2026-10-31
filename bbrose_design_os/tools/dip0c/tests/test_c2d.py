"""DIP-0C2d tests — review manifest, queues, interpretation rules.

The interpretation rules are the point of this slice, so they are the tests:
a collection group is NOT a duplicate family; UNKNOWN_RELATIONSHIP is a review
queue, never positive evidence; an EPS without a hash is UNAVAILABLE, not
unrelated; cross-format members keep different readiness; canonical is nominated,
never selected; nothing propagates; every human field is blank; and machine
inference is immutable once a human writes a decision.
"""
from __future__ import annotations

import copy
import json

import pytest

from tools.dip0c import config as C
from tools.dip0c import review_c2d as RV
from tools.dip0c import run_c2d


@pytest.fixture(scope="module")
def out():
    assert run_c2d.main() == 0
    recon = json.loads((C.OUT_REPORTS / "c2d_reconciliation.json")
                       .read_text(encoding="utf-8"))
    rows = json.loads((C.OUT_C2D / "review_manifest.json")
                      .read_text(encoding="utf-8"))
    queues = json.loads((C.OUT_C2D / "review_queues.json")
                        .read_text(encoding="utf-8"))
    groups = json.loads((C.OUT_C2D / "groups.json").read_text(encoding="utf-8"))
    return recon, rows, queues, groups


# --- 1. collection groups are NOT duplicate families ------------------------
def test_collection_groups_are_not_duplicate_families(out):
    recon, _, _, groups = out
    coll = [g for g in groups if g["group_type"] == C.GROUP_COLLECTION]
    assert coll, "the pilot has collection groups"
    for g in coll:
        assert g["group_type"] != C.GROUP_EXACT_DUPLICATE
        assert g["group_type"] != C.GROUP_VISUAL_FAMILY
        assert "NOT A DUPLICATE FAMILY" in g["note"].upper()
        assert "NOT substitutes" in g["note"]
    assert recon["invariants"][
        "collection_groups_not_labelled_duplicate_families"] is True


def test_group_types_stay_distinct(out):
    recon, _, _, groups = out
    for g in groups:
        assert g["group_type"] in C.GROUP_TYPES
    # the pilot has no visual equivalence, so there must be NO visual family
    assert recon["visual_families"] == 0
    assert recon["collection_groups"] == 6
    assert recon["exact_duplicate_groups"] == 1


# --- 2. UNKNOWN is a review queue, never positive evidence -------------------
def test_unknown_never_becomes_positive_family_evidence(out):
    recon, _, _, groups = out
    assert recon["invariants"]["unknown_never_becomes_a_visual_family"] is True
    # no group is founded on UNKNOWN edges
    for g in groups:
        if g["group_type"] == C.GROUP_VISUAL_FAMILY:
            assert "UNKNOWN" not in " ".join(g["evidence"]).upper()


def test_unknown_edges_are_grouped_by_shared_reason(out):
    recon, _, queues, _ = out
    by_reason = recon["unknown_relationship_totals"]["by_reason"]
    assert sum(by_reason.values()) == recon["unknown_relationship_totals"]["edges"]
    for reason in by_reason:
        assert reason in C.UNKNOWN_REASONS
    # a queue exists per reason, so nobody inspects N unrelated edges one by one
    uq = [q for q in queues if q["queue"].startswith(C.QUEUE_UNKNOWN)]
    assert len(uq) == len(by_reason)
    for q in uq:
        assert "NOT" in q["shared_review_reason"]
        assert q["one_decision_may_apply_to_group"] is True


# --- 3. EPS is UNAVAILABLE, not unrelated -----------------------------------
def test_eps_is_unavailable_not_unrelated(out):
    recon, rows, queues, _ = out
    eps = [r for r in rows if r["machine"]["dhash"] is None]
    assert len(eps) == recon["eps_visual_comparison_unavailable"] == 6
    for r in eps:
        lim = " ".join(r["machine"]["capability_limitations"])
        assert C.VISUAL_COMPARISON_UNAVAILABLE in lim
        assert "NOT evidence of visual difference" in lim
        # it must NOT be described as unrelated
        assert "unrelated" not in lim.lower()
    q = next(q for q in queues if q["queue"] == C.QUEUE_EPS_UNAVAILABLE)
    assert "Do NOT read these as visually unrelated" in \
        q["recommended_reviewer_action"]


# --- 4. cross-format members keep DIFFERENT readiness ------------------------
def test_cross_format_family_preserves_different_readiness(out):
    _, rows, _, groups = out
    xf = [g for g in groups if g["group_type"] == C.GROUP_CROSS_FORMAT]
    assert xf
    fam = next(g for g in xf
               if any("5955" in m for m in g["members"]))
    readiness = set()
    for r in rows:
        if r["machine"]["cross_format_source_family"] == fam["group_id"]:
            readiness.add(r["machine"]["technical_readiness"])
    # the .ai, .jpg and .eps members must NOT have collapsed to one value
    assert len(readiness) > 1, f"readiness propagated across formats: {readiness}"
    assert "readiness is NOT shared" in " ".join(fam["evidence"])


# --- 5. canonical: nominated, never selected --------------------------------
def test_canonical_nomination_never_becomes_selection(out):
    recon, rows, queues, _ = out
    assert recon["invariants"]["no_automatic_canonical_selection"] is True
    nominated = [r for r in rows
                 if r["machine"]["canonical_candidate_nomination"]]
    assert nominated
    for r in nominated:
        assert r["machine"]["canonical_candidate_nomination"] == \
            C.POSTURE_CANONICAL_CANDIDATE
        assert r["human"]["canonical_selection"] is None


# --- 6. nothing propagates ---------------------------------------------------
def test_rights_and_permissions_never_propagate_through_groups(out):
    recon, rows, _, _ = out
    assert recon["invariants"]["no_rights_or_permissions_propagated"] is True
    for r in rows:
        m = r["machine"]
        assert m["retrieval_eligibility"] is False
        assert m["automatic_use_eligibility"] is False
        assert m["rights_status"]["ownership"] == "unconfirmed"
        assert m["rights_status"]["license"] == "unverified"
        assert m["reuse_posture"] == C.POSTURE_PENDING


# --- 7. every human field is blank ------------------------------------------
def test_every_human_field_is_blank(out):
    recon, rows, _, _ = out
    assert recon["invariants"]["all_human_fields_blank"] is True
    for r in rows:
        for k, v in r["human"].items():
            assert v in (None, ""), f"human field {k} was machine-written"


def test_no_batch_decision_is_applied_automatically(out):
    recon, _, queues, _ = out
    assert recon["invariants"]["no_batch_decision_applied"] is True
    for q in queues:
        assert q["batch_decision_applied"] is False


# --- 8. machine inference is immutable after human review --------------------
def test_machine_inference_immutable_after_human_review(out):
    _, rows, _, _ = out
    row = copy.deepcopy(rows[0])
    before = copy.deepcopy(row["machine"])
    # a reviewer disagrees with the machine and records it
    row["human"]["reviewer"] = "symow"
    row["human"]["relationship_confirmation"] = "REJECTED"
    row["human"]["canonical_selection"] = "some-other-id"
    row["human"]["correction_reason"] = "machine was wrong"
    # the machine block must be untouched — the two never share a key
    assert row["machine"] == before
    assert not (set(row["machine"]) & set(row["human"]))


# --- 9. queues are deterministic --------------------------------------------
def test_queues_are_deterministic(out):
    recon, _, queues, _ = out
    assert run_c2d.main() == 0
    q2 = json.loads((C.OUT_C2D / "review_queues.json").read_text(encoding="utf-8"))
    assert [q["queue"] for q in queues] == [q["queue"] for q in q2]
    assert [q["items"] for q in queues] == [q["items"] for q in q2]
    r2 = json.loads((C.OUT_REPORTS / "c2d_reconciliation.json")
                    .read_text(encoding="utf-8"))
    assert recon["priority_totals"] == r2["priority_totals"]
    assert recon["groups_by_type"] == r2["groups_by_type"]


def test_all_nine_queues_exist_with_priorities_and_reasons(out):
    _, _, queues, _ = out
    ids = {q["queue"].split("/")[0] for q in queues}
    assert ids == set(C.REVIEW_QUEUES)
    for q in queues:
        assert q["priority"] in C.REVIEW_PRIORITIES
        assert q["shared_review_reason"]
        assert q["recommended_reviewer_action"]


# --- 10. skipped large buckets appear in the limitations ---------------------
def test_skipped_bucket_limitation_is_recorded(out):
    recon, _, _, _ = out
    lim = recon["blocking_coverage_limitation"]
    assert lim["max_bucket_members"] == C.MAX_BUCKET_MEMBERS
    assert "skipped_buckets" in lim
    assert lim["skipped_bucket_count"] == len(lim["skipped_buckets"])
    assert lim["reason_for_the_limit"]
    assert lim["coverage_note"]     # states completeness honestly either way


# --- 11. totals reconcile with C2c ------------------------------------------
def test_totals_reconcile_with_c2c(out):
    recon, rows, _, _ = out
    rec = recon["reconciles_with_c2c"]
    assert rec["candidates"] is True
    assert rec["c2c_candidates"] == rec["c2d_manifest_rows"] == len(rows) == 48
    assert rec["c2d_candidate_groups"] == rec["c2c_components"]
    assert recon["invariants"]["components_match_c2c"] is True


# --- 12. every priority carries reasons + integrity --------------------------
def test_every_priority_has_reasons(out):
    _, rows, _, _ = out
    for r in rows:
        assert r["machine"]["review_priority"] in C.REVIEW_PRIORITIES
        assert r["machine"]["review_reasons"], "a priority with no reason"


def test_source_integrity(out):
    recon, _, _, _ = out
    assert recon["integrity"]["materials"]["unchanged"] is True
    assert recon["integrity"]["no_output_under_source"]["ok"] is True


# --- unit: the UNKNOWN reason classifier ------------------------------------
def _c(cid, sha="S", folder="p", member=False, path="p/x.png"):
    return {"candidate_id": cid, "source_sha256": sha, "source_folder": folder,
            "source_path": path,
            "collection": {"is_member": True} if member else None}


def test_unknown_reason_eps_is_capability_not_difference():
    e = {"perceptual_comparison": "UNAVAILABLE_REQUIRES_TOOL"}
    assert RV.unknown_reason(e, _c("a"), _c("b")) == \
        C.UR_EPS_VISUAL_CAPABILITY_UNAVAILABLE


def test_unknown_reason_conflicting_hashes():
    e = {"dhash_distance": 2, "phash_distance": 30, "weak_visual_evidence": False}
    assert RV.unknown_reason(e, _c("a"), _c("b")) == \
        C.UR_CONFLICTING_HASH_EVIDENCE


def test_unknown_reason_low_information():
    e = {"dhash_distance": 0, "phash_distance": 0, "weak_visual_evidence": True}
    assert RV.unknown_reason(e, _c("a"), _c("b")) == C.UR_LOW_INFORMATION_IMAGE


def test_unknown_reason_candidate_vs_whole_sheet():
    e = {"dhash_distance": 20, "phash_distance": 22, "weak_visual_evidence": False}
    a = _c("a", member=True, path="p/sheet.jpg")
    b = _c("b", member=False, path="p/whole.ai")
    assert RV.unknown_reason(e, a, b) == C.UR_CANDIDATE_VS_WHOLE_SHEET_MISMATCH
