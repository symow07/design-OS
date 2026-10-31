"""DIP-0C5 — review contract, domains, dispositions, gates, consolidation."""
from __future__ import annotations

import json

import pytest

from tools.dip0c import config as C
from tools.dip0c import consolidate as CON
from tools.dip0c import dispositions as D
from tools.dip0c import gates as G
from tools.dip0c import review_contract as RC
from tools.dip0c import review_domains as RD
from tools.dip0c import rights_model as RM


def _item(domain=RD.FONT_FACE, subject="face-1", **kw):
    kw.setdefault("source_refs", ["materials/x.ttf"])
    kw.setdefault("machine_summary", {"health": "HEALTHY"})
    kw.setdefault("priority", "HIGH")
    kw.setdefault("reasons", ["no licence evidence"])
    return RC.review_item(domain=domain, subject_id=subject, **kw)


# === review-item identity ====================================================
def test_identity_is_domain_plus_subject_and_is_stable():
    a = RC.review_item_id(RD.FONT_FACE, "face-1")
    assert a == RC.review_item_id(RD.FONT_FACE, "face-1")          # deterministic
    assert a != RC.review_item_id(RD.FONT_FACE, "face-2")          # subject matters
    assert a != RC.review_item_id(RD.FONT_FAMILY, "face-1")        # domain matters


def test_the_same_subject_in_two_domains_is_two_review_items():
    """FONT_FACE asks a technical question; PROVENANCE_RIGHTS_GROUP asks a rights one.
    They are different decisions and must never be collapsed."""
    tech = RC.review_item_id(RD.FONT_FACE, "subject-x")
    rights = RC.review_item_id(RD.PROVENANCE_RIGHTS_GROUP, "subject-x")
    assert tech != rights


def test_queue_membership_never_creates_a_review_item():
    it = _item()
    mems = [RC.queue_membership(review_item_id_=it["review_item_id"], queue_id=q,
                                reason="r", priority="HIGH", blocking=True,
                                required_role="LEGAL_REVIEWER", batchable=True,
                                provenance="C4c")
            for q in ("Q1", "Q2", "Q3", "Q4")]
    for m in mems:
        assert m["creates_review_item"] is False
        assert m["carries_decision"] is False

    idx = RC.index([it], mems)
    assert idx["unique_review_items"] == 1              # ONE item...
    assert idx["total_queue_memberships"] == 4          # ...in FOUR queues
    assert idx["estimated_human_decisions"] == 1        # ...is ONE decision


def test_unique_items_are_not_double_counted_across_queues():
    """C4c's fourteen queues summed to 6,921 'decisions' for 4,883 files. Never again."""
    items = [_item(subject=f"face-{i}") for i in range(10)]
    mems = [RC.queue_membership(review_item_id_=it["review_item_id"], queue_id=f"Q{q}",
                                reason="r", priority="HIGH", blocking=False,
                                required_role="LEGAL_REVIEWER", batchable=True,
                                provenance="c")
            for it in items for q in range(4)]
    idx = RC.index(items, mems)
    assert idx["unique_review_items"] == 10
    assert idx["total_queue_memberships"] == 40
    assert idx["estimated_human_decisions"] == 10       # NOT 40
    assert idx["items_in_multiple_queues"] == 10
    assert "never the sum of queue memberships" in idx["queue_memberships_are_not_decisions"]


def test_the_same_domain_and_subject_resolves_to_one_item_however_often_it_is_added():
    dup = [_item(subject="face-1"), _item(subject="face-1"), _item(subject="face-1")]
    idx = RC.index(dup, [])
    assert idx["unique_review_items"] == 1


# === decisions attach to the ITEM, and are append-only =======================
def test_a_decision_attaches_to_the_item_not_to_a_membership():
    it = _item()
    RC.append_decision(it, decision=D.DEFER, reviewer="alice", at="2026-07-14T00:00Z")
    assert it["human"]["human_decision"] == D.DEFER
    assert len(it["decision_history"]) == 1


def test_a_correction_appends_a_new_event_against_the_same_identity():
    it = _item()
    before_id = it["review_item_id"]
    RC.append_decision(it, decision=D.DEFER, reviewer="alice", at="t1")
    RC.append_decision(it, decision=D.REJECT, reviewer="bob", at="t2",
                       reason="new evidence", corrects="the earlier DEFER")
    assert it["review_item_id"] == before_id            # same identity
    assert len(it["decision_history"]) == 2             # BOTH events survive
    assert it["decision_history"][0]["decision"] == D.DEFER
    assert it["decision_history"][1]["corrects_decision"]


def test_removing_a_membership_removes_neither_item_nor_history():
    it = _item()
    m = RC.queue_membership(review_item_id_=it["review_item_id"], queue_id="Q1",
                            reason="r", priority="HIGH", blocking=True,
                            required_role="LEGAL_REVIEWER", batchable=True,
                            provenance="c")
    RC.append_decision(it, decision=D.QUARANTINE, reviewer="a", at="t")
    idx = RC.index([it], [])                            # membership gone
    assert idx["unique_review_items"] == 1
    assert len(it["decision_history"]) == 1
    assert m["review_item_id"] == it["review_item_id"]


# === machine vs human vocabularies ===========================================
def test_the_two_vocabularies_are_disjoint():
    assert not (set(D.MACHINE_RECOMMENDATIONS) & set(D.HUMAN_DECISIONS))
    assert len(D.MACHINE_RECOMMENDATIONS) == 13
    assert len(D.HUMAN_DECISIONS) == 14


@pytest.mark.parametrize("decision", D.HUMAN_DECISIONS)
def test_a_machine_may_never_emit_a_human_decision(decision):
    with pytest.raises(C.HumanOnlyStateViolation):
        D.machine_disposition(decision)


@pytest.mark.parametrize("rec", D.MACHINE_RECOMMENDATIONS)
def test_a_machine_recommendation_is_not_a_human_decision(rec):
    assert D.machine_disposition(rec) == rec
    with pytest.raises(ValueError):
        D.human_decision(rec)                # it does NOT become a decision


def test_no_human_decision_grants_a_permission():
    for d in D.HUMAN_DECISIONS:
        assert D.decision_grants_permission(d) is False


def test_a_review_item_refuses_a_human_decision_as_its_recommendation():
    with pytest.raises(C.HumanOnlyStateViolation):
        _item(recommended_action=D.APPROVE_FONT)


def test_every_review_item_starts_with_every_permission_false():
    it = _item()
    assert set(it["permissions"]) == set(RM.PERMISSION_FLAGS)
    assert not any(it["permissions"].values())
    assert all(v is None for v in it["human"].values())
    assert it["machine_inference_immutable"] is True


# === domains =================================================================
def test_there_are_twelve_domains_each_declaring_its_contract():
    assert len(RD.DOMAINS) == 12
    for d in RD.DOMAINS:
        s = RD.spec(d)
        for k in ("allowed_human_actions", "required_roles", "batch_review_allowed",
                  "dual_control_required", "expiry_applies", "eventual_permissions"):
            assert k in s, (d, k)
        for a in s["allowed_human_actions"]:
            assert a in D.HUMAN_DECISIONS


def test_canonical_and_palette_require_dual_control():
    assert RD.spec(RD.CANONICAL_MASTER_CANDIDATE)["dual_control_required"] is True
    assert RD.spec(RD.COLOR_PALETTE)["dual_control_required"] is True


def test_rights_across_provenance_are_never_batched():
    """The C4b correction, at the contract layer."""
    assert RD.spec(RD.PROVENANCE_RIGHTS_GROUP)["batch_review_allowed"] is False
    assert "RIGHTS ATTACH TO PROVENANCE, NOT CONTENT" in \
        RD.spec(RD.PROVENANCE_RIGHTS_GROUP)["note"]


def test_font_technical_and_font_rights_are_different_domains():
    assert RD.FONT_FACE in RD.DOMAINS
    assert RD.PROVENANCE_RIGHTS_GROUP in RD.DOMAINS
    assert RD.spec(RD.FONT_FACE)["question"] != \
        RD.spec(RD.PROVENANCE_RIGHTS_GROUP)["question"]


# === gates ===================================================================
def test_retrieval_defaults_to_false():
    r = G.retrieval_gate(RD.REUSABLE_ASSET, {})
    assert r["allowed"] is False
    assert r["default"] is False
    assert len(r["unmet"]) == len(G.RETRIEVAL_CONDITIONS[RD.REUSABLE_ASSET])


def test_automatic_use_requires_retrieval_plus_more():
    """Satisfy EVERY retrieval condition — automatic use is still denied."""
    state = {c: True for c in G.RETRIEVAL_CONDITIONS[RD.REUSABLE_ASSET]}
    assert G.retrieval_gate(RD.REUSABLE_ASSET, state)["allowed"] is True

    a = G.automatic_use_gate(RD.REUSABLE_ASSET, state)
    assert a["allowed"] is False                       # retrieval is NOT enough
    assert "automatic_use_explicitly_granted" in a["unmet"]
    assert a["strictly_harder_than_retrieval"] is True


def test_the_two_permissions_never_collapse():
    assert G.gates_are_independent()["collapsed"] is False
    state = {c: True for c in G.RETRIEVAL_CONDITIONS[RD.FONT_FACE]}
    state.update({c: True for c in G.AUTOMATIC_USE_CONDITIONS})
    a = G.automatic_use_gate(RD.FONT_FACE, state)
    assert a["allowed"] is True                        # only with BOTH sets satisfied


def test_a_quarantined_asset_can_never_be_automatically_used():
    state = {c: True for c in G.RETRIEVAL_CONDITIONS[RD.REUSABLE_ASSET]}
    state.update({c: True for c in G.AUTOMATIC_USE_CONDITIONS})
    state["not_quarantined"] = False
    assert G.automatic_use_gate(RD.REUSABLE_ASSET, state)["allowed"] is False


def test_font_install_embed_and_production_are_separate_permissions():
    f = G.font_permissions_are_separate()
    assert f["implied_by_retrieval"] is False
    assert f["implied_by_automatic_use"] is False
    assert "installation" in f["separate"]


def test_evidence_domains_have_no_retrieval_path():
    r = G.retrieval_gate(RD.LICENSE_EVIDENCE, {})
    assert r["allowed"] is False
    assert "not a retrievable domain" in r["reason"]


# === historical memory =======================================================
def test_historical_memory_excludes_template_geometry():
    with pytest.raises(G.MemoryContractViolation):
        G.assert_memory_safe(["hierarchy", "reusable_dieline_paths"])
    with pytest.raises(G.MemoryContractViolation):
        G.assert_memory_safe(["exact_reusable_placement_coordinates"])
    with pytest.raises(G.MemoryContractViolation):
        G.assert_memory_safe(["template_instructions"])


def test_historical_memory_allows_only_descriptive_observations():
    r = G.memory_contract(["hierarchy", "spacing_tendencies", "color_relationships",
                           "design_era", "provenance"])
    assert r["valid"] is True
    assert r["posture"] == G.REFERENCE_MEMORY_ONLY
    assert r["excluded_present"] == []


def test_reference_memory_is_never_reproducible():
    assert "automatic_reproduction_of_old_designs" in G.MEMORY_EXCLUDED
    assert "complete_historical_layouts" in G.MEMORY_EXCLUDED
    assert "copied_artwork_paths" in G.MEMORY_EXCLUDED


# === coverage: the honesty test ==============================================
def test_the_coverage_table_does_not_claim_the_corpus_is_audited():
    cov = CON.coverage()
    by = {r["milestone"].split(" —")[0]: r for r in cov["rows"]}
    assert by["DIP-0A"]["status"] == CON.COMPLETE_FULL_CORPUS
    assert by["DIP-0C4"]["status"] == CON.COMPLETE_FULL_CORPUS
    assert by["DIP-0B"]["status"] == CON.PILOT_VALIDATED
    assert by["DIP-0C1/C2"]["status"] == CON.PILOT_VALIDATED
    assert by["DIP-0C3"]["status"] == CON.COMPLETE_FRAMEWORK
    # the uncomfortable numbers are stated, not smoothed
    assert by["DIP-0C1/C2"]["coverage_pct"] < 2.0
    assert by["DIP-0B"]["outstanding"] == 77
    assert by["DIP-0C1/C2"]["outstanding"] > 2200
    assert "NOT fully audited" in cov["headline"]


def test_outstanding_work_is_named_not_hidden():
    cov = CON.coverage()
    names = {w["workstream"] for w in cov["outstanding_workstreams"]}
    assert names == {"Historical Design Corpus Expansion",
                     "Reusable Asset Corpus Expansion"}
    for w in cov["outstanding_workstreams"]:
        assert w["status"] == CON.NOT_RUN_AT_CORPUS_SCALE
        assert w["outstanding_files"] > 0
        assert "not a hidden omission" in w["note"]


def test_old_milestone_artifacts_are_read_never_regenerated():
    a = CON.milestone_artifacts()
    assert a["regenerated_any_old_artifact"] is False
    assert a["reconciliation_count"] >= 11
    assert a["milestones_without_machine_reconciliation"]     # 0B, C1, C2 — stated


def test_activation_totals_are_all_zero():
    from tools.dip0c import compound as CP
    from tools.dip0c import ledger_store as LS
    act = CON.activation_totals(LS.validate(), CP.validate_committed())
    assert act["all_zero"] is True
    for k in ("real_approval_events", "real_permission_grants",
              "retrieval_enabled_assets", "automatic_use_enabled_assets",
              "fonts_installed", "files_moved_or_deleted",
              "synthetic_decisions_in_real_ledger"):
        assert act[k] == 0, k


# === the real run ============================================================
def test_the_review_index_counts_decisions_once():
    from tools.dip0c import run_c5
    rv = run_c5.build_review_index()
    i = rv["index"]
    assert i["estimated_human_decisions"] == i["unique_review_items"]
    assert i["total_queue_memberships"] >= i["unique_review_items"]
    # a FONT_FACE and its PROVENANCE_RIGHTS_GROUP are separate decisions
    assert i["by_domain"]["FONT_FACE"] == 4182
    # [the clean-up of 2026-10-04 — his fifth and sixth answers: the duplicate copies, the Cracked-by fonts and the
    # screen fonts left materials/ and the DIP-0A inventory lost exactly their 1,092 FONT rows (M1 1,028, M4 27, M5 37,
    # reconciled against the pre-move index); re-measured here: 2,099 -> 38 provenance-rights groups (built from the duplicate model, 1,047 -> 20 groups); no decision had been recorded against any of them. The faces, families and packages are read from
    # the C4a output on disk, made before the move, and still count the removed fonts — said in the clean-up's report.]
    assert i["by_domain"]["PROVENANCE_RIGHTS_GROUP"] == 38
    assert i["items_requiring_dual_control"] == 3        # 2 canonical + 1 palette


def test_no_review_item_carries_a_permission_or_a_decision():
    from tools.dip0c import run_c5
    rv = run_c5.build_review_index()
    for it in rv["items"][:300]:
        assert not any(it["permissions"].values())
        assert it["human"]["human_decision"] is None
        assert it["decision_history"] == []
        assert it["recommended_action"] in D.MACHINE_RECOMMENDATIONS


def test_c5_is_deterministic():
    from tools.dip0c import run_c5
    a = run_c5.build_review_index()["index"]
    b = run_c5.build_review_index()["index"]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
