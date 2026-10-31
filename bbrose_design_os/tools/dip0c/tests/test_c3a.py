"""DIP-0C3a tests — brand/logo audit, overrides, and the human-only guards.

The guards are the point of this slice: a machine cannot confirm BBROSE ownership,
cannot approve a licence, cannot select a canonical master, and cannot turn a
filename or a folder into brand identity. C3a audits technique and relationships
only — ownership, licence and permission are C3b, and every permission stays false.
"""
from __future__ import annotations

import json

import pytest

from tools.dip0c import brand, brand_rel, config as C
from tools.dip0c import run_c3a


def test_c3a_test_outputs_are_session_scoped():
    assert C.C3A_OUTPUT_ROOT != C.OUTPUT_ROOT
    assert C.OUT_C3A.parent == C.C3A_OUTPUT_ROOT
    assert C.OUT_C3A_REPORTS.parent == C.C3A_OUTPUT_ROOT


@pytest.fixture(scope="module")
def out():
    assert run_c3a.main() == 0
    recon = json.loads((C.OUT_C3A_REPORTS / "c3a_reconciliation.json")
                       .read_text(encoding="utf-8"))
    records = json.loads((C.OUT_C3A / "brand_candidates.json")
                         .read_text(encoding="utf-8"))
    edges = json.loads((C.OUT_C3A / "brand_relationships.json")
                       .read_text(encoding="utf-8"))
    return recon, {r["filename"]: r for r in records}, edges


# --- human-only states are unreachable by machine ---------------------------
def test_machine_cannot_confirm_bbrose_ownership():
    with pytest.raises(C.HumanOnlyStateViolation):
        C.machine_ownership(C.OWN_BBROSE_CONFIRMED)
    # the machine may only ever say UNCONFIRMED
    assert C.machine_ownership(C.OWN_BBROSE_UNCONFIRMED) == \
        C.OWN_BBROSE_UNCONFIRMED


def test_machine_cannot_approve_a_license():
    with pytest.raises(C.HumanOnlyStateViolation):
        C.machine_license(C.LIC_APPROVED)
    assert C.machine_license(C.LIC_NO_EVIDENCE) == C.LIC_NO_EVIDENCE


def test_machine_cannot_select_the_canonical_master():
    with pytest.raises(C.HumanOnlyStateViolation):
        C.machine_brand_master(C.CANONICAL_BRAND_MASTER)
    # it may only NOMINATE
    assert C.machine_brand_master(C.BRAND_MASTER_CANDIDATE) == \
        C.BRAND_MASTER_CANDIDATE


def test_human_only_states_never_appear_in_output(out):
    recon, _, _ = out
    assert recon["machine_guards"]["human_only_states_absent_from_output"] is True
    assert recon["machine_guards"]["leaked_states"] == []


def test_all_permissions_remain_false(out):
    recon, records, _ = out
    assert recon["machine_guards"]["all_permissions_false"] is True
    for r in records.values():
        p = r["permissions"]
        for k in ("retrieval_allowed", "automatic_use_allowed",
                  "production_use_allowed", "modification_allowed",
                  "embedding_allowed", "redistribution_allowed",
                  "public_export_allowed", "approved_for_bbrose",
                  "approved_for_other_brands"):
            assert p[k] is False
        assert p["approved_markets"] == [] and p["approved_products"] == []


def test_technical_readiness_does_not_activate_use(out):
    """LOGO6.ai is technically sound and still entirely unusable.

    (Its FILE-level C1 readiness is TECHNICALLY_USABLE_WITH_CAVEATS while its
    CANDIDATE-level C2b readiness is TECHNICALLY_READY — two different levels, both
    correct. Either way it activates nothing.)
    """
    _, records, _ = out
    r = records["LOGO6.ai"]
    assert r["technical_readiness"]["value"] in (
        C.READY_TECHNICALLY_READY, C.READY_TECHNICALLY_USABLE_WITH_CAVEATS)
    assert r["queue_i_membership"]["in_queue_i"] is True
    assert r["permissions"]["retrieval_allowed"] is False
    assert r["permissions"]["automatic_use_allowed"] is False
    assert r["permissions"]["production_use_allowed"] is False
    assert r["ownership"]["status"] == "NOT_ASSESSED_IN_C3A"
    assert r["license"]["status"] == "NOT_ASSESSED_IN_C3A"


def test_c3a_assesses_no_ownership_or_license(out):
    recon, _, _ = out
    assert recon["machine_guards"]["ownership_not_assessed_in_c3a"] is True
    assert recon["machine_guards"]["license_not_assessed_in_c3a"] is True


# --- classification overrides ------------------------------------------------
def test_bbrose_compositions_get_overrides_without_rewriting_dip0a(out):
    recon, records, _ = out
    assert {o["file"] for o in recon["classification_overrides"]} == \
        {"BBROSE.pdf", "BBROSE-1.pdf"}
    for name in ("BBROSE.pdf", "BBROSE-1.pdf"):
        ov = records[name]["classification_override"]
        # DIP-0A is preserved, not rewritten
        assert ov["inventory_category_original"] == "BRAND_MASTER"
        assert records[name]["dip0a_classification"] == "BRAND_MASTER"
        assert ov["audit_category_override"] == C.OVERRIDE_DESIGN_COMPOSITION
        assert ov["reuse_posture"] == C.POSTURE_REFERENCE_ONLY
        assert ov["human_confirmed_category"] is None
        assert ov["cannot_be_canonical_master"] is True
    assert recon["machine_guards"]["dip0a_classification_preserved"] is True


def test_override_evidence_is_preserved(out):
    _, records, _ = out
    ev = " ".join(records["BBROSE.pdf"]["classification_override"]
                  ["override_evidence"])
    assert "raster coverage" in ev
    assert "embedded images" in ev
    assert "live-text spans" in ev
    assert "NOT isolated logo geometry" in ev


def test_compositions_cannot_be_nominated_as_canonical_masters(out):
    recon, records, _ = out
    noms = set(recon["brand_master_candidate_nominations"])
    assert "BBROSE.pdf" not in noms and "BBROSE-1.pdf" not in noms
    for name in ("BBROSE.pdf", "BBROSE-1.pdf"):
        assert records[name]["brand_master_candidate"] is None
        assert records[name]["canonical_brand_master"] is None
    assert recon["machine_guards"]["no_composition_or_third_party_nominated"] is True


# --- brand-name detection ----------------------------------------------------
def test_live_text_gives_direct_brand_evidence(out):
    _, records, _ = out
    b = records["JOJIA LOGO.ai"]["brand_name"]
    assert b["value"] == "JOJIA"
    assert b["tier"] == C.TIER_DIRECT
    assert b["live_text_spans"], "span provenance must be recorded"
    assert any("DIRECTLY from live text" in e for e in b["evidence"])


def test_outlined_wordmark_returns_requires_human(out):
    _, records, _ = out
    b = records["logo.pdf"]["brand_name"]
    assert b["value"] is None
    assert b["tier"] == C.TIER_REQUIRES_HUMAN
    assert b["confidence"] == 0.0
    assert any("OUTLINED" in e for e in b["evidence"])
    assert any("no OCR" in e for e in b["evidence"])


def test_a_headline_is_not_asserted_as_a_brand_name(out):
    """LOGO6.ai's live text reads 'global logistics services'. The machine must NOT
    assert that as a brand name — and must hand the text to the reviewer."""
    _, records, _ = out
    b = records["LOGO6.ai"]["brand_name"]
    assert b["value"] is None
    assert b["tier"] == C.TIER_REQUIRES_HUMAN
    assert any("NONE matches a known brand token" in e for e in b["evidence"])
    texts = " ".join(s["text"] for s in b["live_text_spans"]).lower()
    assert "logistic" in texts, "the extracted text must be offered as evidence"


def test_filename_and_folder_never_establish_brand_identity(out):
    _, records, _ = out
    for r in records.values():
        nf = r["name_and_folder_evidence"]
        assert nf["is_decisive"] is False
        assert "SUPPORTING evidence only" in nf["note"]
    # ATC LOGO.ai is named ATC and sits in the BBROSE folder; neither decides it
    atc = records["ATC LOGO.ai"]
    assert atc["name_and_folder_evidence"]["folder_is_bbrose_office"] is True
    assert atc["brand_name"]["value"] is None          # outlined -> not read
    assert atc["detected_third_party_brand"]["value"] == "ATC"
    assert "supporting evidence only" in \
        " ".join(atc["detected_third_party_brand"]["evidence"]).lower()


# --- third-party stays excluded ---------------------------------------------
def test_third_party_material_is_never_nominated(out):
    recon, records, _ = out
    noms = set(recon["brand_master_candidate_nominations"])
    for name in ("ATC LOGO.ai", "JOJIA LOGO.ai", "LOGO ATC.ai"):
        assert name not in noms
        assert records[name]["brand_master_candidate"] is None
        assert records[name]["permissions"]["approved_for_bbrose"] is False
        assert records[name]["permissions"]["production_use_allowed"] is False


def test_third_party_inside_the_bbrose_folder_is_detected(out):
    recon, _, _ = out
    tp = {t["file"]: t for t in recon["third_party_candidates"]}
    assert {"ATC LOGO.ai", "JOJIA LOGO.ai", "LOGO ATC.ai"} <= set(tp)
    # all of them sit in the BBROSE office folder — which grants nothing
    for name in ("ATC LOGO.ai", "JOJIA LOGO.ai", "LOGO ATC.ai"):
        assert tp[name]["in_bbrose_office_folder"] is True


# --- relationships -----------------------------------------------------------
def test_shared_folder_never_proves_a_brand_relationship(out):
    _, _, edges = out
    for e in edges:
        assert e["shared_folder_is_decisive"] is False
        assert e["human_confirmed_relationship"] is None
        for h in e["hypotheses"]:
            assert h["relationship"] in C.BRAND_RELATIONSHIPS
            assert h["human_confirmed"] is None
            assert "positive_evidence" in h and "contradictory_evidence" in h
    folder_only = [e for e in edges
                   if e["primary"] == C.BR_UNKNOWN
                   and any("share a folder" in p
                           for h in e["hypotheses"]
                           for p in h["positive_evidence"])]
    for e in folder_only:
        h = next(h for h in e["hypotheses"] if h["relationship"] == C.BR_UNKNOWN)
        assert any("NEVER proves" in c for c in h["contradictory_evidence"])
        assert h["confidence"] <= 0.15


def test_brand_relationships_only_between_brand_assets(out):
    _, _, edges = out
    files = {e["a"] for e in edges} | {e["b"] for e in edges}
    # a baby-pattern / background / sticker sheet is rights-blocked, not brand art
    assert not any("baby-pattern" in f or "rounded-shapes" in f for f in files)


# --- determinism + integrity -------------------------------------------------
def test_run_is_deterministic(out):
    recon, _, _ = out
    assert run_c3a.main() == 0
    r2 = json.loads((C.OUT_C3A_REPORTS / "c3a_reconciliation.json")
                    .read_text(encoding="utf-8"))
    for k in ("classification_overrides", "brand_names_from_live_text",
              "brand_master_candidate_nominations", "third_party_candidates",
              "relationship_edges", "relationship_hypotheses"):
        assert recon[k] == r2[k], f"{k} is not deterministic"


def test_source_integrity(out):
    recon, _, _ = out
    assert recon["integrity"]["materials"]["unchanged"] is True
    assert recon["integrity"]["no_output_under_source"]["ok"] is True


def test_human_fields_blank(out):
    recon, records, _ = out
    assert recon["machine_guards"]["human_fields_blank"] is True
    for r in records.values():
        assert r["human"]["category"] is None
        assert r["human"]["reviewed_by"] is None


# --- unit: guards on the builders -------------------------------------------
def test_hypothesis_rejects_unknown_relationship():
    with pytest.raises(ValueError):
        brand_rel.hypothesis("MADE_UP", positive=[], contradictory=[],
                             confidence=0.5, tier=C.TIER_HEURISTIC)


def test_known_brand_token_matching():
    assert brand._known_brand_in("Welcome to BBROSE cosmetics") == "BBROSE"
    assert brand._known_brand_in("Jojiia") == "JOJIA"
    assert brand._known_brand_in("ATC group") == "ATC"
    assert brand._known_brand_in("global logistics services") is None
