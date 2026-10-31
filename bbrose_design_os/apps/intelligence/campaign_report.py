"""Deterministic campaign reporting + coverage gaps — DIP-1B-5B.

Two rules shape this module:

* **Corpus counts and campaign counts are never blended.** The campaign is a deliberately
  bounded subset (38 of 100 assets, 10 of 34 fonts); mixing the two would misrepresent both.
* **There is no combined "approved percentage."** Progress is reported along separate,
  non-substitutable axes — imported, in campaign, technically reviewed, human classified,
  evidence assessed, governance selected, operationally permitted. Collapsing them into one
  number would imply that technical progress is approval progress. It is not.

Read-only: the report writes nothing and grants nothing.
"""
from __future__ import annotations

from collections import Counter

from apps.accounts.models import DecisionEvent

from .dataset_identifiers import (
    DIP0C2_ASSET_CANDIDATE_DATASET, DIP1B_CURATED_ASSET_EXPANSION_DATASET,
)
from .models import (
    BrandCandidateProfile, CorpusItem, DesignAssetProfile, FontFaceProfile,
    GovernanceDecisionProjection, HistoricalDesignProfile, HumanAssertionProjection,
    OperationalPermissionProjection, ReviewCandidate,
)
from .review_campaign import WAVES, build_campaign_scope
from .review_readiness import assess_readiness

REPORT_SCHEMA = "dip1b_curated_review_report/1.0"

# --- coverage gaps ---------------------------------------------------------------
GAP_SCHEMA = "dip1b_corpus_coverage_gap/1.0"
HAIR_CARE_GAP_ID = "dip1b_coverage_gap:HAIR_CARE/1.0"


def hair_care_coverage_gap() -> dict:
    """A deterministic, visible record of the hair-care memory gap.

    Deliberately NON-BLOCKING: it must not stall unrelated review waves, and it must not
    tempt anyone into importing a weak or unverified design merely to make a number move.
    Closing it is an acquisition decision, not a review action.

    Coverage is reported as a literal 0 rather than counted. `HistoricalDesignProfile`
    carries only `product_family_machine_label` — a machine guess — and `audit_status`
    tops out at `MACHINE_AUDITED`. No field records human product-family verification, so
    verified coverage is 0 *by construction*. Counting the machine label here would launder
    a guess into a verification claim, which this slice forbids.
    """
    return {
        "schema_version": GAP_SCHEMA,
        "gap_id": HAIR_CARE_GAP_ID,
        "missing_product_family": "HAIR_CARE",
        # human-only: no machine label can raise this number
        "human_verified_coverage": 0,
        "coverage_verification_note": (
            "Verification of product family is human-only. Machine labels are not "
            "coverage; no human product-family verification exists in this schema."),
        "desired_evidence_type": "DEEPLY_AUDITED_HISTORICAL_PRODUCTION_DESIGN",
        "minimum_source_requirements": [
            "ORIGINAL_PRODUCTION_ARTWORK_NOT_A_MOCKUP",
            "RESOLVED_SOURCE_PROVENANCE",
            "VERIFIED_SOURCE_INTEGRITY",
            "SUFFICIENT_TECHNICAL_EVIDENCE_FOR_LAYOUT_AND_TYPOGRAPHY_REVIEW",
        ],
        "severity": "MEDIUM",
        "recommended_acquisition_action": (
            "ACQUIRE_AND_AUDIT_A_GENUINE_HAIR_CARE_PRODUCTION_DESIGN"),
        "blocking": False,
        "blocks_other_waves": False,
        "notes": ("Do not import a weak or unverified design to fill this gap; an "
                  "unverified reference would corrupt the memory it is meant to serve."),
    }


def coverage_gaps() -> list[dict]:
    return [hair_care_coverage_gap()]


# --- corpus vs campaign ----------------------------------------------------------
def corpus_counts() -> dict:
    """Everything IMPORTED — independent of what is under active review."""
    curated = DesignAssetProfile.objects.filter(
        dataset_identifier=DIP1B_CURATED_ASSET_EXPANSION_DATASET).count()
    return {
        "historical_designs": HistoricalDesignProfile.objects.count(),
        "design_assets": DesignAssetProfile.objects.count(),
        "design_assets_c2": DesignAssetProfile.objects.filter(
            dataset_identifier=DIP0C2_ASSET_CANDIDATE_DATASET).count(),
        "design_assets_curated": curated,
        # the corpus-wide hard block: every curated acquisition, in campaign or not
        "curated_assets_rights_unreviewed": curated,
        "fonts": FontFaceProfile.objects.count(),
        "brand_lineage_candidates": BrandCandidateProfile.objects.filter(
            corpus_item__external_key__startswith="brand:").count(),
        "palette_lineage_candidates": BrandCandidateProfile.objects.filter(
            corpus_item__external_key__startswith="palette:").count(),
    }


def _campaign_counts(entries) -> dict:
    by_wave = Counter(e["wave"] for e in entries)
    w4 = [e for e in entries if e["review_type"] in
          ("BRAND_IDENTITY", "PALETTE_OBSERVATION")]
    return {
        "total_review_candidates": len(entries),
        "by_wave": {w: by_wave.get(w, 0) for w in WAVES},
        # distinct key names from corpus_counts() on purpose: these are the in-campaign
        # subset, and a shared key would invite reading one population as the other
        "brand_lineage_in_campaign": sum(
            1 for e in w4 if e["review_type"] == "BRAND_IDENTITY"),
        "palette_lineage_in_campaign": sum(
            1 for e in w4 if e["review_type"] == "PALETTE_OBSERVATION"),
        "curated_assets_in_campaign": sum(
            1 for e in entries
            if e["dataset_identifier"] == DIP1B_CURATED_ASSET_EXPANSION_DATASET),
        "c2_assets_in_campaign": sum(
            1 for e in entries
            if e["dataset_identifier"] == DIP0C2_ASSET_CANDIDATE_DATASET),
    }


def _authority_counts() -> dict:
    """The numbers that must stay zero until real humans decide."""
    return {
        "signed_decision_events": DecisionEvent.objects.count(),
        "human_assertion_projections": HumanAssertionProjection.objects.count(),
        "governance_selections": GovernanceDecisionProjection.objects.count(),
        # must count ONLY the allowed state — an unfiltered count would over-report a
        # number whose whole purpose is to stay zero until a human decides
        "allowed_operational_permissions": OperationalPermissionProjection.objects.filter(
            effective_state=OperationalPermissionProjection.State.ALLOWED).count(),
    }


def build_campaign_report(*, scope=None) -> dict:
    """Deterministic report. Corpus and campaign are reported SEPARATELY, and there is no
    single blended approval figure by design."""
    scope = scope if scope is not None else build_campaign_scope()
    entries = scope["entries"]

    candidates = {str(c.pk): c for c in ReviewCandidate.objects.select_related(
        "corpus_item")}
    readiness_rows = []
    for e in entries:
        c = candidates.get(e["review_candidate_id"])
        if c is None:
            continue
        readiness_rows.append(assess_readiness(c, wave=e["wave"]))

    blockers = Counter()
    for r in readiness_rows:
        blockers.update(r.blocker_codes)

    completed = sum(1 for c in candidates.values()
                    if c.workflow_status == ReviewCandidate.Status.COMPLETED)

    return {
        "schema_version": REPORT_SCHEMA,
        "campaign_id": scope["campaign_id"],
        # NB: never merged — two different populations
        "corpus": corpus_counts(),
        "campaign": _campaign_counts(entries),
        "readiness_states": dict(sorted(Counter(
            r.overall for r in readiness_rows).items())),
        "blocker_counts": dict(sorted(blockers.items())),
        "technical_evidence_counts": dict(sorted(Counter(
            r.technical_evidence for r in readiness_rows).items())),
        "provenance_evidence_counts": dict(sorted(Counter(
            r.provenance_evidence for r in readiness_rows).items())),
        "identity_evidence_counts": dict(sorted(Counter(
            r.identity_evidence for r in readiness_rows).items())),
        "rights_evidence_counts": dict(sorted(Counter(
            r.rights_evidence for r in readiness_rows).items())),
        "integrity_counts": dict(sorted(Counter(
            r.integrity for r in readiness_rows).items())),
        # separate, non-substitutable progress axes — deliberately NOT one percentage
        "progress_axes": {
            # count the corpus itself, not a sum of profile tables: summing
            # historical+assets+fonts silently omits every brand and palette item
            "imported_corpus_items": CorpusItem.objects.count(),
            "in_active_campaign": len(entries),
            "review_tasks_completed": completed,
            "human_classified": HumanAssertionProjection.objects.count(),
            "evidence_assessed": 0,
            "governance_selected": GovernanceDecisionProjection.objects.count(),
            "operationally_permitted": 0,
        },
        "authority_counts": _authority_counts(),
        "coverage_gaps": coverage_gaps(),
        "combined_approval_percentage": None,   # intentionally absent: see module docstring
    }
