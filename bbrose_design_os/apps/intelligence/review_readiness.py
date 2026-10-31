"""Deterministic review readiness — DIP-1B-5B (`review_readiness/1.0`).

Readiness is **coordination metadata**. It says which candidates a human can usefully pick
up next and what blocks them. It is NOT approval, canonical/official status, ownership,
licence validity, or any operational permission — and it can never upgrade any of those.

Computed **on demand** (no migration, no persisted readiness table): the same input state
and calculation version always produce the same result, so persistence would only duplicate
what the inputs already determine.

It **reuses** the existing authority gates rather than re-deriving them:
`evidence_integrity.EvidenceIntegrityResolver` for integrity, `evidence_readiness` for the
brand rights/identity dimensions. The hard blocks below are structural, not inferred:

* **Rights are never inferred.** A curated acquisition is `UNREVIEWED` by lineage, full
  stop — matching SHA-256s, a nearby licence file, a sibling asset's conclusion, a machine
  label, or technical quality can never clear rights. (Exact bytes do not prove identical
  rights; rights attach to provenance and acquisition.)
* **The 21 brand-lineage candidates stay identity/evidence blocked**, and the palette stays
  blocked from primary-palette governance.
* An **unresolved evidence-integrity finding blocks only the candidates it affects.**
"""
from __future__ import annotations

import dataclasses

from .dataset_identifiers import DIP1B_CURATED_ASSET_EXPANSION_DATASET
from .evidence_integrity import (
    HASH_MISMATCH,
    REVIEW_REQUIRED as INTEGRITY_REVIEW_REQUIRED,
    STALE_GENERATED_OUTPUT,
    UNVERIFIED_SOURCE_VERSION,
    VERIFIED as INTEGRITY_VERIFIED,
    EvidenceIntegrityResolver,
)
from .models import (
    DesignAssetProfile, EvidenceReference, ObservedFact, ProvenanceRecord,
    ReviewCandidate,
)
from .review_campaign import (
    BRAND_LINEAGE_REVIEW_TYPE, PALETTE_LINEAGE_REVIEW_TYPE, WAVE_2B,
)

READINESS_SCHEMA = "review_readiness/1.0"
CALCULATION_VERSION = "bbrose.intelligence.review_readiness/1.0"

# --- bounded vocabularies --------------------------------------------------------
TECH_COMPLETE, TECH_PARTIAL, TECH_MISSING, TECH_CONFLICTING = (
    "COMPLETE", "PARTIAL", "MISSING", "CONFLICTING")
PROV_DOCUMENTED, PROV_PARTIAL, PROV_ABSENT, PROV_CONFLICTING = (
    "DOCUMENTED", "PARTIAL", "ABSENT", "CONFLICTING")
ID_VERIFIED, ID_PARTIALLY_VERIFIED, ID_UNVERIFIED, ID_CONFLICTING = (
    "VERIFIED", "PARTIALLY_VERIFIED", "UNVERIFIED", "CONFLICTING")
RIGHTS_UNREVIEWED, RIGHTS_EVIDENCE_PRESENT, RIGHTS_EVIDENCE_MISSING = (
    "UNREVIEWED", "EVIDENCE_PRESENT", "EVIDENCE_MISSING")
RIGHTS_CONFLICTING, RIGHTS_NOT_APPLICABLE = "CONFLICTING", "NOT_APPLICABLE"
INTEG_VERIFIED, INTEG_PARTIAL, INTEG_HASH_MISMATCH = "VERIFIED", "PARTIAL", "HASH_MISMATCH"
INTEG_STALE_SOURCE, INTEG_UNVERIFIED_SOURCE, INTEG_CONFLICTING = (
    "STALE_SOURCE", "UNVERIFIED_SOURCE", "CONFLICTING")
INTEG_REVIEW_REQUIRED = "REVIEW_REQUIRED"

READY_FOR_CLASSIFICATION = "READY_FOR_CLASSIFICATION"
READY_FOR_EVIDENCE_REVIEW = "READY_FOR_EVIDENCE_REVIEW"
NEEDS_INFORMATION = "NEEDS_INFORMATION"
BLOCKED_BY_INTEGRITY = "BLOCKED_BY_INTEGRITY"
BLOCKED_BY_IDENTITY = "BLOCKED_BY_IDENTITY"
BLOCKED_BY_RIGHTS = "BLOCKED_BY_RIGHTS"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

# the bounded set a browser filter may select from — callers validate against this rather
# than maintaining a second, drifting copy of the vocabulary
OVERALL_STATES = (
    READY_FOR_CLASSIFICATION, READY_FOR_EVIDENCE_REVIEW, NEEDS_INFORMATION,
    BLOCKED_BY_INTEGRITY, BLOCKED_BY_IDENTITY, BLOCKED_BY_RIGHTS, REVIEW_REQUIRED,
)

# --- blocker codes (ordering normalised so output is deterministic) --------------
B_INTEGRITY = "EVIDENCE_INTEGRITY_UNRESOLVED"
B_IDENTITY = "IDENTITY_UNCONFIRMED"
B_RIGHTS = "RIGHTS_UNREVIEWED"
B_TECHNICAL = "TECHNICAL_EVIDENCE_INCOMPLETE"
B_PROVENANCE = "PROVENANCE_INCOMPLETE"
_BLOCKER_ORDER = (B_INTEGRITY, B_IDENTITY, B_RIGHTS, B_TECHNICAL, B_PROVENANCE)
READINESS_BLOCKERS = _BLOCKER_ORDER      # bounded set for browser filter validation

# Each resolver status maps to exactly one readiness state. REVIEW_REQUIRED must NOT be
# reported as HASH_MISMATCH: the resolver is saying "a human must look", not "the hashes
# disagree". DECLARED_HASH_MISMATCH may appear as one reason code among several, but a
# reason code is not the finding — collapsing them would make readiness assert a specific
# evidence defect the authority gate never asserted. Reason codes are carried verbatim in
# `integrity_reason_codes` instead.
_INTEGRITY_MAP = {
    INTEGRITY_VERIFIED: INTEG_VERIFIED,
    HASH_MISMATCH: INTEG_HASH_MISMATCH,
    STALE_GENERATED_OUTPUT: INTEG_STALE_SOURCE,
    UNVERIFIED_SOURCE_VERSION: INTEG_UNVERIFIED_SOURCE,
    INTEGRITY_REVIEW_REQUIRED: INTEG_REVIEW_REQUIRED,
}


@dataclasses.dataclass(frozen=True)
class ReviewReadiness:
    schema_version: str
    calculation_version: str
    review_candidate_id: str
    corpus_item_id: str
    review_type: str
    wave: str
    technical_evidence: str
    provenance_evidence: str
    identity_evidence: str
    rights_evidence: str
    integrity: str
    overall: str
    blocker_codes: tuple[str, ...]
    recommended_reviewer_role: str
    recommended_next_action: str
    integrity_reason_codes: tuple[str, ...]
    # readiness NEVER implies any of these — stated, not assumed
    implies_approval: bool = False
    implies_rights_clearance: bool = False
    operational_permission_granted: bool = False

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def _is_curated_asset(item) -> bool:
    """Lineage test — a curated acquisition is rights-unreviewed by construction."""
    return DesignAssetProfile.objects.filter(
        corpus_item=item,
        dataset_identifier=DIP1B_CURATED_ASSET_EXPANSION_DATASET).exists()


def _technical_state(item) -> str:
    facts = ObservedFact.objects.filter(corpus_item=item).count()
    if facts == 0:
        return TECH_MISSING
    return TECH_COMPLETE if facts >= 2 else TECH_PARTIAL


def _provenance_state(item) -> str:
    if ProvenanceRecord.objects.filter(corpus_item=item).exists():
        return PROV_DOCUMENTED
    return PROV_ABSENT if not EvidenceReference.objects.filter(
        corpus_item=item).exists() else PROV_PARTIAL


def _identity_state(candidate, item, integrity) -> str:
    """Brand/palette lineage stays unconfirmed; technical evidence is not identity."""
    if candidate.review_type in (BRAND_LINEAGE_REVIEW_TYPE, PALETTE_LINEAGE_REVIEW_TYPE):
        # technical evidence may be present, but it is never brand identity
        if integrity.status != INTEGRITY_VERIFIED:
            return ID_PARTIALLY_VERIFIED
        return ID_PARTIALLY_VERIFIED if EvidenceReference.objects.filter(
            corpus_item=item).exists() else ID_UNVERIFIED
    return ID_VERIFIED if item.external_key else ID_UNVERIFIED


def _rights_state(candidate, item, wave) -> str:
    """Rights are NEVER inferred from hashes, folders, neighbours, or machine labels."""
    if candidate.review_type == ReviewCandidate.ReviewType.HISTORICAL_MEMORY:
        return RIGHTS_NOT_APPLICABLE          # reference memory, not a reuse claim
    if wave == WAVE_2B or _is_curated_asset(item):
        return RIGHTS_UNREVIEWED              # hard block, by lineage
    if candidate.review_type in (BRAND_LINEAGE_REVIEW_TYPE, PALETTE_LINEAGE_REVIEW_TYPE):
        return RIGHTS_UNREVIEWED
    return RIGHTS_EVIDENCE_MISSING


def _overall(tech, ident, rights, integ, candidate):
    blockers = []
    if integ != INTEG_VERIFIED:
        blockers.append(B_INTEGRITY)
    if ident in (ID_UNVERIFIED, ID_CONFLICTING, ID_PARTIALLY_VERIFIED) and \
            candidate.review_type in (BRAND_LINEAGE_REVIEW_TYPE,
                                      PALETTE_LINEAGE_REVIEW_TYPE):
        blockers.append(B_IDENTITY)
    if rights == RIGHTS_UNREVIEWED:
        blockers.append(B_RIGHTS)
    if tech in (TECH_MISSING, TECH_CONFLICTING):
        blockers.append(B_TECHNICAL)
    blockers = tuple(b for b in _BLOCKER_ORDER if b in blockers)   # normalised order

    # Blockers describe what a human may NOT conclude — they do not stop triage. Integrity
    # is the only one that changes the headline state, because unresolved evidence must not
    # look reviewable-to-conclusion.
    if B_INTEGRITY in blockers:
        overall = BLOCKED_BY_INTEGRITY
    elif tech == TECH_MISSING:
        overall = NEEDS_INFORMATION
    elif B_IDENTITY in blockers:
        overall = READY_FOR_CLASSIFICATION      # identity triage is exactly the work
    elif B_RIGHTS in blockers:
        overall = READY_FOR_CLASSIFICATION      # classify yes; clear rights no
    else:
        overall = READY_FOR_CLASSIFICATION
    return overall, blockers


def _next_action(overall, blockers, candidate):
    if B_INTEGRITY in blockers:
        return "TRIAGE_TECHNICAL_AND_IDENTITY_ONLY_EVIDENCE_INTEGRITY_UNRESOLVED"
    if overall == NEEDS_INFORMATION:
        return "REQUEST_MISSING_TECHNICAL_EVIDENCE"
    if B_RIGHTS in blockers:
        return "CLASSIFY_TECHNICALLY_THEN_QUEUE_FOR_RIGHTS_REVIEW"
    if B_IDENTITY in blockers:
        return "PERFORM_IDENTITY_TRIAGE"
    return "SUBMIT_SIGNED_CLASSIFICATION"


def assess_readiness(candidate, *, wave=None, integrity=None) -> ReviewReadiness:
    """Deterministic readiness for one ReviewCandidate. Read-only; writes nothing."""
    item = candidate.corpus_item
    integrity = integrity or EvidenceIntegrityResolver().evaluate(item)
    if wave is None:
        from .review_campaign import _dataset_identifier, assign_wave
        wave = assign_wave(candidate, _dataset_identifier(candidate))

    integ = _INTEGRITY_MAP.get(integrity.status, INTEG_UNVERIFIED_SOURCE)
    tech = _technical_state(item)
    prov = _provenance_state(item)
    ident = _identity_state(candidate, item, integrity)
    rights = _rights_state(candidate, item, wave)
    overall, blockers = _overall(tech, ident, rights, integ, candidate)

    return ReviewReadiness(
        schema_version=READINESS_SCHEMA, calculation_version=CALCULATION_VERSION,
        review_candidate_id=str(candidate.pk), corpus_item_id=str(item.pk),
        review_type=candidate.review_type, wave=wave,
        technical_evidence=tech, provenance_evidence=prov, identity_evidence=ident,
        rights_evidence=rights, integrity=integ, overall=overall,
        blocker_codes=blockers, recommended_reviewer_role="DESIGN_REVIEWER",
        recommended_next_action=_next_action(overall, blockers, candidate),
        integrity_reason_codes=tuple(integrity.reason_codes),
    )
