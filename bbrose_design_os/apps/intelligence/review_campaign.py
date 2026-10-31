"""Frozen curated review campaign scope — DIP-1B-5B.

`dip1b_curated_review_scope/1.0` freezes the EXISTING 90 canonical ReviewCandidates into
five bounded review waves. It is **coordination metadata**: it creates nothing, decides
nothing, and confers no approval, governance status, or operational permission.

Two rules the rest of this slice depends on:

* **Waves are assigned by dataset LINEAGE + review type — never by machine
  `candidate_kind`.** A machine label may not redefine dataset identity, campaign group,
  provenance lineage, or governance subject type. The brand-lineage candidate that a
  machine classified `PALETTE` therefore stays a brand-lineage Wave 4 subject.
* **The hashed scope content carries no volatile values** (no generation timestamp), so a
  rebuild from unchanged repository/database state yields the same scope hash. Applying the
  campaign repeatedly is idempotent by construction.

The campaign is deliberately a BOUNDED SUBSET of the curated corpus: 38 of 100 design
assets and 10 of 34 fonts are in scope. Corpus counts and campaign counts are reported
separately and never blended (see `campaign_report`).
"""
from __future__ import annotations

import hashlib
import json

from .dataset_identifiers import (
    DIP0C2_ASSET_CANDIDATE_DATASET,
    DIP1B_CURATED_ASSET_EXPANSION_DATASET,
)
from .models import CorpusItem, DesignAssetProfile, ReviewCandidate

CAMPAIGN_ID = "dip1b_curated_review_scope/1.0"
CAMPAIGN_SCHEMA = CAMPAIGN_ID

WAVE_1 = "WAVE_1_HISTORICAL_DESIGN_MEMORY"
WAVE_2A = "WAVE_2A_ORIGINAL_C2_DESIGN_ASSETS"
WAVE_2B = "WAVE_2B_CURATED_DESIGN_ASSETS"
WAVE_3 = "WAVE_3_FONT_CANDIDATES"
WAVE_4 = "WAVE_4_BRAND_AND_PALETTE_TRIAGE"
WAVES = (WAVE_1, WAVE_2A, WAVE_2B, WAVE_3, WAVE_4)

# The verified partition of the existing 90 tasks (handoff-review confirmed).
EXPECTED_WAVE_COUNTS = {WAVE_1: 20, WAVE_2A: 14, WAVE_2B: 24, WAVE_3: 10, WAVE_4: 22}
EXPECTED_TOTAL = 90

# Review types, by lineage, that make up Wave 4.
BRAND_LINEAGE_REVIEW_TYPE = ReviewCandidate.ReviewType.BRAND_IDENTITY
PALETTE_LINEAGE_REVIEW_TYPE = ReviewCandidate.ReviewType.PALETTE_OBSERVATION


class CampaignScopeError(ValueError):
    """The campaign scope cannot be frozen. FAIL CLOSED — nothing is created."""


# --- per-wave bounded metadata ---------------------------------------------------
# Required human OUTPUTS only; the system never answers them (see review_packet).
_WAVE_META = {
    WAVE_1: {
        "selection_reason": "CURATED_HISTORICAL_REFERENCE_MEMORY",
        "reviewer_discipline": "DESIGN_REVIEWER",
        "risk_codes": ("REFERENCE_MEMORY_ONLY", "POSSIBLE_OBSOLETE_BRAND"),
        "required_outputs": (
            "product_family", "design_role", "layout_pattern", "typography_hierarchy",
            "color_relationships", "reference_memory_suitability", "copying_risk",
            "obsolete_brand_risk"),
    },
    WAVE_2A: {
        "selection_reason": "DIP0C2_SEMANTIC_ASSET_CANDIDATE",
        "reviewer_discipline": "DESIGN_REVIEWER",
        "risk_codes": ("RIGHTS_REVIEW_REQUIRED",),
        "required_outputs": (
            "asset_category", "extraction_quality", "vector_raster_suitability",
            "collection_relationship", "provenance_completeness",
            "rights_review_requirement", "reference_only_or_technically_reusable"),
    },
    WAVE_2B: {
        "selection_reason": "CURATED_MVP_ASSET_EXPANSION",
        "reviewer_discipline": "DESIGN_REVIEWER",
        # curated acquisitions are rights-unreviewed BY CONSTRUCTION — never inferred clear
        "risk_codes": ("RIGHTS_UNREVIEWED_CURATED_ACQUISITION", "RIGHTS_REVIEW_REQUIRED"),
        "required_outputs": (
            "asset_category", "extraction_quality", "vector_raster_suitability",
            "collection_relationship", "provenance_completeness",
            "rights_review_requirement", "reference_only_or_technically_reusable"),
    },
    WAVE_3: {
        "selection_reason": "CURATED_FONT_REVIEW_SUBSET",
        "reviewer_discipline": "DESIGN_REVIEWER",
        "risk_codes": ("LICENCE_EVIDENCE_UNVERIFIED", "POSSIBLE_SYSTEM_OR_TRIAL_FONT"),
        "required_outputs": (
            "family_identity", "style_category", "script_coverage",
            "weight_width_suitability", "bbrose_suitability", "licence_evidence_state",
            "system_demo_trial_suspicion"),
    },
    WAVE_4: {
        "selection_reason": "BRAND_AND_PALETTE_IDENTITY_TRIAGE",
        "reviewer_discipline": "DESIGN_REVIEWER",
        "risk_codes": ("IDENTITY_UNCONFIRMED", "EVIDENCE_INTEGRITY_REVIEW_REQUIRED"),
        "required_outputs": (
            "visible_brand_identity", "bbrose_third_party_or_unknown",
            "master_composition_lockup_or_unrelated", "vector_master_suitability",
            "missing_evidence"),
    },
}
# Wave 4 splits its required outputs by lineage; the palette subject asks palette
# questions, the brand subjects ask brand questions.
_PALETTE_META = {
    "selection_reason": "PALETTE_OBSERVATION_TRIAGE",
    "reviewer_discipline": "DESIGN_REVIEWER",
    "risk_codes": ("PARTIAL_PARSE", "NOT_AUTHORITATIVE_PALETTE_EVIDENCE"),
    "required_outputs": (
        "observed_colors", "parse_completeness", "authoritative_bbrose_evidence",
        "candidate_only_suitability", "blockers_before_governance_review"),
}


def canonical_bytes(value) -> bytes:
    """Deterministic bytes, matching the intelligence-app convention."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def _dataset_identifier(candidate) -> str:
    """The asset's dataset LINEAGE. Empty for non-asset subjects."""
    if candidate.review_type != ReviewCandidate.ReviewType.DESIGN_ASSET:
        return ""
    profile = DesignAssetProfile.objects.filter(
        corpus_item=candidate.corpus_item).first()
    if profile is None:
        raise CampaignScopeError(
            f"design-asset candidate {candidate.pk} has no DesignAssetProfile; its "
            "dataset lineage cannot be established.")
    return profile.dataset_identifier


def assign_wave(candidate, dataset_identifier: str) -> str:
    """Wave from LINEAGE + review type. Machine `candidate_kind` is never consulted."""
    rt = candidate.review_type
    if rt == ReviewCandidate.ReviewType.HISTORICAL_MEMORY:
        return WAVE_1
    if rt == ReviewCandidate.ReviewType.DESIGN_ASSET:
        if dataset_identifier == DIP0C2_ASSET_CANDIDATE_DATASET:
            return WAVE_2A
        if dataset_identifier == DIP1B_CURATED_ASSET_EXPANSION_DATASET:
            return WAVE_2B
        raise CampaignScopeError(
            f"design-asset candidate {candidate.pk} has unsupported dataset "
            f"{dataset_identifier!r}")
    if rt == ReviewCandidate.ReviewType.FONT_TECHNICAL:
        return WAVE_3
    if rt in (BRAND_LINEAGE_REVIEW_TYPE, PALETTE_LINEAGE_REVIEW_TYPE):
        return WAVE_4
    raise CampaignScopeError(f"unsupported review type {rt!r}")


def _meta_for(candidate, wave):
    if wave == WAVE_4 and candidate.review_type == PALETTE_LINEAGE_REVIEW_TYPE:
        return _PALETTE_META
    return _WAVE_META[wave]


def _entry(candidate) -> dict:
    item = candidate.corpus_item
    dataset = _dataset_identifier(candidate)
    wave = assign_wave(candidate, dataset)
    meta = _meta_for(candidate, wave)
    return {
        "review_candidate_id": str(candidate.pk),
        "corpus_item_id": str(item.pk),
        "external_key": item.external_key,
        "item_kind": item.item_kind,
        "review_type": candidate.review_type,
        "dataset_identifier": dataset,
        "wave": wave,
        "selection_reason": meta["selection_reason"],
        "business_priority": candidate.priority,
        "known_risk_codes": list(meta["risk_codes"]),
        "recommended_reviewer_discipline": meta["reviewer_discipline"],
        "required_human_outputs": list(meta["required_outputs"]),
    }


def _validate(candidates) -> None:
    """Fail closed on anything that would corrupt the campaign's identity contract.

    NB: the *size* of the campaign is NOT asserted here — `verify_campaign_partition`
    checks the frozen 90-item contract against real data. Keeping the two apart means the
    builder stays a pure function of whatever candidates exist (and so is unit-testable on
    a fixture), while the frozen contract is still enforced where it matters.
    """
    seen_items = {}
    for c in candidates:
        item = c.corpus_item
        # deprecated / redirected / retired subjects may never be a campaign subject
        if item.lifecycle_state != CorpusItem.Lifecycle.ACTIVE:
            raise CampaignScopeError(
                f"candidate {c.pk} points at non-ACTIVE CorpusItem {item.pk} "
                f"({item.lifecycle_state}) — deprecated identities cannot be reviewed.")
        if item.pk in seen_items:
            raise CampaignScopeError(
                f"duplicate active review subject for CorpusItem {item.pk}")
        seen_items[item.pk] = c.pk


def build_campaign_scope() -> dict:
    """The deterministic, hash-stable scope document. Creates nothing; reads only."""
    candidates = list(
        ReviewCandidate.objects.select_related("corpus_item").order_by("pk"))
    _validate(candidates)
    entries = sorted((_entry(c) for c in candidates),
                     key=lambda e: (e["wave"], e["external_key"],
                                    e["review_candidate_id"]))
    counts = {w: sum(1 for e in entries if e["wave"] == w) for w in WAVES}
    document = {
        "schema_version": CAMPAIGN_SCHEMA,
        "campaign_id": CAMPAIGN_ID,
        "wave_counts": counts,
        "total_candidates": len(entries),
        "entries": entries,
        # NB: deliberately no generated_at — the hashed content must be volatile-free so
        # repeated builds are idempotent.
    }
    return document


def verify_campaign_partition(document=None, expected=None) -> dict:
    """Enforce the FROZEN campaign contract (90 tasks; 20/14/24/10/22) against real data.

    Separate from `build_campaign_scope` on purpose: the builder is a pure function of the
    candidates present, this is the contract check. Raises `CampaignScopeError` on any
    deviation — the campaign is a bounded subset and must not silently drift.
    """
    document = document if document is not None else build_campaign_scope()
    expected = expected if expected is not None else EXPECTED_WAVE_COUNTS
    counts = document["wave_counts"]
    if counts != expected:
        raise CampaignScopeError(
            f"wave partition {counts} != frozen partition {expected}")
    if document["total_candidates"] != sum(expected.values()):
        raise CampaignScopeError(
            f"campaign total {document['total_candidates']} != {sum(expected.values())}")
    return document


def campaign_scope_hash(document=None) -> str:
    document = document if document is not None else build_campaign_scope()
    return hashlib.sha256(canonical_bytes(document)).hexdigest()


def campaign_entries_by_candidate() -> dict:
    return {e["review_candidate_id"]: e for e in build_campaign_scope()["entries"]}


def campaign_entry_for(candidate) -> dict | None:
    return campaign_entries_by_candidate().get(str(candidate.pk))
