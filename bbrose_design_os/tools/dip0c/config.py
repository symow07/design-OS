"""DIP-0C configuration: reuse posture, capability tiers, EPS states, models.

Reuses the DIP-0A read-only invariants. The governing rule of this milestone:
**no machine process declares anything reusable, owned, or licensed.** Every
value here is a candidate/recommendation; final approval is human-only, and the
technical axis is kept strictly separate from the rights axis.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from tools.dip0.config import (  # noqa: F401 — re-exported read-only invariants
    REPO_ROOT,
    SOURCE_ROOT,
    assert_output_safe,
    relpath,
    physical_path,
)

TOOL_NAME = "dip0c"
TOOL_VERSION = "0.1.0"

OUTPUT_ROOT = REPO_ROOT / "var" / "design_intelligence" / "audits" / "dip0c"
OUT_TECHNICAL = OUTPUT_ROOT / "technical"
OUT_PREVIEWS = OUTPUT_ROOT / "previews"
OUT_REPORTS = OUTPUT_ROOT / "reports"
OUT_TEMP = OUTPUT_ROOT / "temporary"
OUT_EPS_PDF = OUT_TEMP / "eps_pdf"            # Ghostscript derivatives only (C1B)

# DOCS_ROOT is the FROZEN, committed milestone tree. It is a READ input to later tests
# (pilot manifests, prior reconciliations, the taxonomy) — normal tests read it and NEVER
# overwrite it.
DOCS_ROOT = REPO_ROOT / "docs" / "design_intelligence" / "dip0c"

# MILESTONE_OUTPUT_ROOT is where milestone artifacts are WRITTEN. It defaults to the frozen
# tree, but ordinary tests point DIP0C_MILESTONE_OUTPUT at a temp dir so a normal run never
# rewrites frozen history. Regenerating the committed artifacts is explicit and opt-in
# (DIP0C_ALLOW_MILESTONE_WRITE=1) — see `assert_not_frozen_milestone`.
MILESTONE_OUTPUT_ROOT = Path(os.environ.get("DIP0C_MILESTONE_OUTPUT") or DOCS_ROOT)
ALLOW_MILESTONE_WRITE = os.environ.get("DIP0C_ALLOW_MILESTONE_WRITE") == "1"

# C3a's JSON products are mutable generator output, even though a later frozen manifest
# identifies one exact historical version by hash.  Tests must never overwrite the local
# path that may currently hold that historical version (or useful mismatch evidence).
# Keep the normal CLI default unchanged; the test session supplies a throwaway root.
C3A_OUTPUT_ROOT = Path(os.environ.get("DIP0C_C3A_OUTPUT_ROOT") or OUTPUT_ROOT)


class FrozenMilestoneWrite(RuntimeError):
    """A normal run tried to overwrite the frozen, committed milestone tree. FAIL CLOSED."""


def assert_not_frozen_milestone(path) -> None:
    """Refuse to write into the committed `docs/design_intelligence/dip0c/` tree unless
    regeneration is explicitly opted in. This keeps frozen milestone history immutable
    under ordinary test runs — the manual `git checkout` revert is no longer load-bearing."""
    p = Path(path).resolve()
    frozen = DOCS_ROOT.resolve()
    if (p == frozen or frozen in p.parents) and not ALLOW_MILESTONE_WRITE:
        raise FrozenMilestoneWrite(
            f"refusing to write frozen DIP-0C milestone artifact {relpath(p)}: normal "
            "runs must target a temp dir (DIP0C_MILESTONE_OUTPUT); explicit regeneration "
            "sets DIP0C_ALLOW_MILESTONE_WRITE=1.")


PILOT_MANIFEST = DOCS_ROOT / "pilot_manifest.json"

# --- capability tiers -------------------------------------------------------
# dip0b tiers, plus DIP-0C's tool-derived and EPS-specific tiers.
TIER_DIRECT = "DIRECT"
TIER_HEURISTIC = "HEURISTIC"
TIER_REQUIRES_ILLUSTRATOR = "REQUIRES_ILLUSTRATOR"
TIER_REQUIRES_HUMAN = "REQUIRES_HUMAN"
TIER_DIRECT_FROM_EPS_HEADER = "DIRECT_FROM_EPS_HEADER"
TIER_DERIVED_VIA_GHOSTSCRIPT = "DERIVED_VIA_GHOSTSCRIPT"
TIER_REQUIRES_TOOL = "REQUIRES_TOOL"
TIER_CONVERSION_FAILED = "CONVERSION_FAILED"
TIERS = (TIER_DIRECT, TIER_HEURISTIC, TIER_REQUIRES_ILLUSTRATOR,
         TIER_REQUIRES_HUMAN, TIER_DIRECT_FROM_EPS_HEADER,
         TIER_DERIVED_VIA_GHOSTSCRIPT, TIER_REQUIRES_TOOL, TIER_CONVERSION_FAILED)

# --- EPS capability states (explicit) --------------------------------------
EPS_HEADER_AUDITED = "HEADER_AUDITED"
EPS_GHOSTSCRIPT_NOT_INSTALLED = "GHOSTSCRIPT_NOT_INSTALLED"
EPS_GHOSTSCRIPT_PILOT_PENDING = "GHOSTSCRIPT_PILOT_PENDING"
EPS_GHOSTSCRIPT_PILOT_PASSED = "GHOSTSCRIPT_PILOT_PASSED"
EPS_GHOSTSCRIPT_PILOT_FAILED = "GHOSTSCRIPT_PILOT_FAILED"
EPS_CONVERSION_FAILED = "CONVERSION_FAILED"
EPS_HEADER_ONLY_PARTIAL = "HEADER_ONLY_PARTIAL"
EPS_REQUIRES_HUMAN = "REQUIRES_HUMAN"
EPS_STATES = (EPS_HEADER_AUDITED, EPS_GHOSTSCRIPT_NOT_INSTALLED,
              EPS_GHOSTSCRIPT_PILOT_PENDING, EPS_GHOSTSCRIPT_PILOT_PASSED,
              EPS_GHOSTSCRIPT_PILOT_FAILED, EPS_CONVERSION_FAILED,
              EPS_HEADER_ONLY_PARTIAL, EPS_REQUIRES_HUMAN)
GHOSTSCRIPT_ADAPTER_BLOCKED = "BLOCKED_TOOL_UNAVAILABLE"

# --- reuse posture (controlled vocabulary) ---------------------------------
# APPROVED_REUSABLE is HUMAN-ONLY and must never be emitted by machine code.
POSTURE_APPROVED_REUSABLE = "APPROVED_REUSABLE"       # human only
POSTURE_REUSABLE_AFTER_REVIEW = "REUSABLE_AFTER_REVIEW"
POSTURE_REFERENCE_ONLY = "REFERENCE_ONLY"
POSTURE_BRAND_MASTER_CANDIDATE = "BRAND_MASTER_CANDIDATE"
POSTURE_THIRD_PARTY_RESTRICTED = "THIRD_PARTY_RESTRICTED"
POSTURE_LICENSE_UNVERIFIED = "LICENSE_UNVERIFIED"
POSTURE_OWNERSHIP_UNCONFIRMED = "OWNERSHIP_UNCONFIRMED"
POSTURE_QUARANTINED = "QUARANTINED"
POSTURE_OUT_OF_SCOPE = "OUT_OF_SCOPE"

REUSE_POSTURES = (
    POSTURE_APPROVED_REUSABLE, POSTURE_REUSABLE_AFTER_REVIEW,
    POSTURE_REFERENCE_ONLY, POSTURE_BRAND_MASTER_CANDIDATE,
    POSTURE_THIRD_PARTY_RESTRICTED, POSTURE_LICENSE_UNVERIFIED,
    POSTURE_OWNERSHIP_UNCONFIRMED, POSTURE_QUARANTINED, POSTURE_OUT_OF_SCOPE,
)
# The eight a machine may emit — APPROVED_REUSABLE is deliberately excluded.
MACHINE_ALLOWED_POSTURES = tuple(p for p in REUSE_POSTURES
                                 if p != POSTURE_APPROVED_REUSABLE)


class ReusePostureViolation(RuntimeError):
    """Raised if machine code ever tries to emit APPROVED_REUSABLE."""


def machine_posture(value: str) -> str:
    """Guard: machine code routes every posture through here."""
    if value == POSTURE_APPROVED_REUSABLE:
        raise ReusePostureViolation(
            "APPROVED_REUSABLE is a human-only decision; machine code must not "
            "emit it")
    if value not in MACHINE_ALLOWED_POSTURES:
        raise ReusePostureViolation(f"unknown reuse posture: {value!r}")
    return value


# --- technical readiness (axis A ONLY — never rights) ----------------------
# THE canonical technical-readiness vocabulary for every DIP stage (C1, C2, …).
# It describes the ARTEFACT only. No value here refers to rights, ownership,
# licensing, reuse posture, retrieval or automatic use — those live on axis B/C
# and are never folded into this axis.
READY_TECHNICALLY_READY = "TECHNICALLY_READY"
READY_TECHNICALLY_USABLE_WITH_CAVEATS = "TECHNICALLY_USABLE_WITH_CAVEATS"
READY_NEEDS_CLEANUP = "NEEDS_CLEANUP"
READY_NEEDS_VECTOR_RECONSTRUCTION = "NEEDS_VECTOR_RECONSTRUCTION"
READY_REFERENCE_ONLY = "REFERENCE_ONLY"
READY_QUARANTINE = "QUARANTINE"
READY_REJECT_CANDIDATE = "REJECT_CANDIDATE"
# added in C2b — the same tuple is extended, never forked into a parallel one
READY_REQUIRES_TOOL = "REQUIRES_TOOL"
READY_HEADER_ONLY_PARTIAL = "HEADER_ONLY_PARTIAL"
TECHNICAL_READINESS = (
    READY_TECHNICALLY_READY, READY_TECHNICALLY_USABLE_WITH_CAVEATS,
    READY_NEEDS_CLEANUP, READY_NEEDS_VECTOR_RECONSTRUCTION, READY_REFERENCE_ONLY,
    READY_QUARANTINE, READY_REJECT_CANDIDATE, READY_REQUIRES_TOOL,
    READY_HEADER_ONLY_PARTIAL,
)

# Retired vocabulary -> canonical replacement. `READY_AFTER_RIGHTS_REVIEW` named
# the RIGHTS axis from inside the TECHNICAL axis, which the two-axis rule forbids.
# Terminology correction only: no logic, threshold or outcome changed — the same
# artefacts receive the same verdict under the new name.
RETIRED_READINESS = {
    "READY_AFTER_RIGHTS_REVIEW": READY_TECHNICALLY_USABLE_WITH_CAVEATS,
}


class ReadinessVocabularyViolation(RuntimeError):
    """Raised if machine code emits a retired or unknown readiness value."""


def readiness_value(value: str) -> str:
    """Guard: machine code routes every technical-readiness value through here.
    Retired vocabulary is refused outright — it is never emitted, only migrated."""
    if value in RETIRED_READINESS:
        raise ReadinessVocabularyViolation(
            f"{value!r} is retired; emit "
            f"{RETIRED_READINESS[value]!r} instead (see "
            f"docs/design_intelligence/dip0c/readiness_vocabulary_migration.md)")
    if value not in TECHNICAL_READINESS:
        raise ReadinessVocabularyViolation(f"unknown readiness value: {value!r}")
    return value


def normalize_readiness(value: str) -> tuple[str, bool]:
    """Read path for legacy STORED data: map retired vocabulary forward.
    Returns (canonical_value, was_normalized)."""
    if value in RETIRED_READINESS:
        return RETIRED_READINESS[value], True
    return value, False


def normalize_readiness_block(block: dict) -> dict:
    """Normalize a stored readiness envelope, recording the migration in its own
    provenance so the correction is never silent."""
    if not isinstance(block, dict) or "value" not in block:
        return block
    new, changed = normalize_readiness(block["value"])
    if not changed:
        return block
    out = dict(block)
    old = block["value"]
    out["value"] = new
    out["evidence"] = list(block.get("evidence", [])) + [
        f"normalized from retired vocabulary {old!r} -> {new!r} "
        "(terminology correction; no logic or outcome change)"]
    out["vocabulary_migrated_from"] = old
    return out


def rights_block() -> dict:
    """Rights axis (B). All permissions default false/unverified; DIP-0C never
    sets any of these true — only a human decision can, in a later step."""
    return {
        "ownership_status": "unverified",
        "license_status": "unverified",
        "commercial_use": False,
        "modification": False,
        "embedding": False,
        "redistribution": False,
        "attribution_required": None,
        "approved_brands": [],
        "approved_markets": [],
        "review_expiry": None,
        "reviewer": None,
        "evidence": [],
        "confidence": 0.0,
    }


def retrieval_gate() -> dict:
    """Retrieval/auto-use stay false regardless of technical readiness.

    DIP-0C reports readiness + risk; it never activates the library.
    """
    return {
        "retrieval": False,
        "automatic_use": False,
        "embedding": False,
        "production_use": False,
        "note": ("stays false until human approval; a clean technical audit "
                 "never flips these on"),
    }


# --- DIP-0C2 segmentation vocabulary (added in C2a) ------------------------
C2_PILOT_MANIFEST = DOCS_ROOT / "c2_pilot_manifest.json"
OUT_CANDIDATES = OUTPUT_ROOT / "candidates"       # per-candidate JSON (git-ignored)

# how a candidate was derived from its source
SEG_METHOD_VECTOR = "VECTOR_GEOMETRY"
SEG_METHOD_VECTOR_WHOLE_NATURAL = "VECTOR_WHOLE_FILE_NATURAL"
SEG_METHOD_VECTOR_WHOLE_FALLBACK = "VECTOR_WHOLE_FILE_FALLBACK"
SEG_METHOD_SVG = "SVG_ELEMENT_TREE"
SEG_METHOD_RASTER = "RASTER_CONNECTED_REGION"
SEG_METHOD_EPS_PREVIEW = "EPS_PREVIEW_DERIVED"
SEG_METHOD_NONE = "NONE"
SEG_METHODS = (SEG_METHOD_VECTOR, SEG_METHOD_VECTOR_WHOLE_NATURAL,
               SEG_METHOD_VECTOR_WHOLE_FALLBACK, SEG_METHOD_SVG,
               SEG_METHOD_RASTER, SEG_METHOD_EPS_PREVIEW, SEG_METHOD_NONE)

# file-level segmentation outcome
SEG_STATUS_SEGMENTED = "SEGMENTED"                 # vector: split into >1
SEG_STATUS_WHOLE_FILE = "WHOLE_FILE_SINGLE_ASSET"  # vector: one asset
SEG_STATUS_AUTO_CONFIDENT = "AUTO_CONFIDENT"       # raster: clean regions
SEG_STATUS_AUTO_LOW_CONF = "AUTO_LOW_CONFIDENCE"   # raster: weak separation
SEG_STATUS_MANUAL = "MANUAL_REVIEW_REQUIRED"       # raster: no reliable split
SEG_STATUS_PREVIEW_DERIVED = "PREVIEW_DERIVED"     # EPS: from a usable preview
SEG_STATUS_UNAVAILABLE = "UNAVAILABLE"             # no reliable segmentation
SEGMENTATION_STATUS = (SEG_STATUS_SEGMENTED, SEG_STATUS_WHOLE_FILE,
                       SEG_STATUS_AUTO_CONFIDENT, SEG_STATUS_AUTO_LOW_CONF,
                       SEG_STATUS_MANUAL, SEG_STATUS_PREVIEW_DERIVED,
                       SEG_STATUS_UNAVAILABLE)

# asset-type vocabulary — HEURISTIC, human-reviewable; C2a leaves it UNKNOWN
# (type inference is a C2b/C2c concern, deliberately not implemented here).
ASSET_TYPE_UNKNOWN = "UNKNOWN_ASSET_TYPE"
ASSET_TYPES = (
    "ICON", "MOTIF", "FLOWER", "LEAF", "FRAME", "RIBBON", "BADGE", "ORNAMENT",
    "PATTERN_TILE", "BACKGROUND", "TEXTURE", "GRADIENT_ASSET", "ILLUSTRATION",
    "LOGO", "BRAND_MARK", "COLOR_SWATCH_SET", "COLLECTION_SHEET", "MOCKUP",
    "REFERENCE_COMPOSITION", ASSET_TYPE_UNKNOWN,
)

# axis A is present but deliberately UNSCORED in C2a (scoring is C2b)
READY_UNSCORED = "UNSCORED_IN_C2A"
# axis C posture is present but pending in C2a (recommendation is C2b+)
POSTURE_PENDING = "PENDING_REVIEW"


def ensure_output_dirs() -> None:
    for d in (OUT_TECHNICAL, OUT_PREVIEWS, OUT_REPORTS, OUT_TEMP, OUT_EPS_PDF,
              OUT_CANDIDATES):
        assert_output_safe(d)
        d.mkdir(parents=True, exist_ok=True)


def load_pilot(manifest: Path | None = None) -> list[dict]:
    manifest = Path(manifest or PILOT_MANIFEST)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return data["entries"]


def load_c2_pilot(manifest: Path | None = None) -> list[dict]:
    manifest = Path(manifest or C2_PILOT_MANIFEST)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return data["entries"]


# --- DIP-0C2b vocabulary ----------------------------------------------------
# Readiness evidence codes (axis A only). Each carries a tier + detail + whether
# it BLOCKS. Technical and rights evidence are never merged into one score.
EV_PATH_CLEANLINESS = "PATH_CLEANLINESS"
EV_VECTOR_RASTER_BALANCE = "VECTOR_RASTER_BALANCE"
EV_COMPLEXITY = "COMPLEXITY"
EV_ISOLATION = "ISOLATION"
EV_TRANSPARENT_BACKGROUND = "TRANSPARENT_BACKGROUND"
EV_EDITABLE_COLORS = "EDITABLE_COLORS"
EV_RASTER_RESOLUTION = "RASTER_RESOLUTION"
EV_CORRUPTION = "CORRUPTION"
EV_UNSUPPORTED_FEATURES = "UNSUPPORTED_FEATURES"
EV_EMBEDDED_RASTER_DEPENDENCE = "EMBEDDED_RASTER_DEPENDENCE"
EV_COLLECTION_SHEET_AMBIGUITY = "COLLECTION_SHEET_AMBIGUITY"
EV_UNSAFE_SVG = "UNSAFE_SVG"
EV_EPS_TOOL_LIMITATION = "EPS_TOOL_LIMITATION"
EV_WATERMARK_SUSPICION = "WATERMARK_SUSPICION"
READINESS_EVIDENCE_CODES = (
    EV_PATH_CLEANLINESS, EV_VECTOR_RASTER_BALANCE, EV_COMPLEXITY, EV_ISOLATION,
    EV_TRANSPARENT_BACKGROUND, EV_EDITABLE_COLORS, EV_RASTER_RESOLUTION,
    EV_CORRUPTION, EV_UNSUPPORTED_FEATURES, EV_EMBEDDED_RASTER_DEPENDENCE,
    EV_COLLECTION_SHEET_AMBIGUITY, EV_UNSAFE_SVG, EV_EPS_TOOL_LIMITATION,
    EV_WATERMARK_SUSPICION,
)

# Effective-resolution bands, measured on the CANDIDATE CROP (not the parent file
# and NOT from DPI metadata). Nothing is called PRINT_READY from pixels alone:
# print suitability needs an intended physical size and the resulting PPI, which
# we do not have for rasters.
RES_HIGH_RES_CANDIDATE = "HIGH_RES_CANDIDATE"      # >= 2000 px long edge
RES_SCREEN_READY = "SCREEN_READY"                  # >= 1000 px
RES_LOW_RES_REFERENCE = "LOW_RES_REFERENCE"        # >= 400 px
RES_TOO_LOW = "TOO_LOW"                            # < 400 px
RESOLUTION_BANDS = (RES_HIGH_RES_CANDIDATE, RES_SCREEN_READY,
                    RES_LOW_RES_REFERENCE, RES_TOO_LOW)
RES_THRESHOLDS = {RES_HIGH_RES_CANDIDATE: 2000, RES_SCREEN_READY: 1000,
                  RES_LOW_RES_REFERENCE: 400}
PRINT_SUITABILITY_UNDETERMINED = "UNDETERMINED_REQUIRES_PHYSICAL_SIZE"

# Pattern / repeat verdicts
PAT_SEAMLESS_LIKELY = "SEAMLESS_LIKELY"
PAT_NON_SEAMLESS_LIKELY = "NON_SEAMLESS_LIKELY"
PAT_REPEAT_TYPE_UNCERTAIN = "REPEAT_TYPE_UNCERTAIN"
PAT_REQUIRES_TOOL = "REQUIRES_TOOL"
PAT_REQUIRES_HUMAN = "REQUIRES_HUMAN"
PATTERN_VERDICTS = (PAT_SEAMLESS_LIKELY, PAT_NON_SEAMLESS_LIKELY,
                    PAT_REPEAT_TYPE_UNCERTAIN, PAT_REQUIRES_TOOL,
                    PAT_REQUIRES_HUMAN)
# A machine may say SEAMLESS_LIKELY, but never above this confidence, and it never
# implies reusability, retrieval or automatic use.
SEAMLESS_CONFIDENCE_CAP = 0.75

# --- DIP-0C2c vocabulary ----------------------------------------------------
OUT_C2C = OUTPUT_ROOT / "c2c"

# SOURCE-level relationships (between FILES)
SRC_EXACT_FILE_DUPLICATE = "EXACT_FILE_DUPLICATE"
SRC_SAME_DOWNLOAD_PACKAGE = "SAME_DOWNLOAD_PACKAGE"
SRC_FILENAME_FAMILY = "FILENAME_FAMILY"
SRC_ALTERNATE_FORMAT_SOURCE = "ALTERNATE_FORMAT_SOURCE"
SRC_VERSION_SOURCE = "VERSION_SOURCE"
SOURCE_RELATIONSHIPS = (SRC_EXACT_FILE_DUPLICATE, SRC_SAME_DOWNLOAD_PACKAGE,
                        SRC_FILENAME_FAMILY, SRC_ALTERNATE_FORMAT_SOURCE,
                        SRC_VERSION_SOURCE)

# CANDIDATE-level relationships (between ASSET CANDIDATES). A candidate edge is
# NEVER created from a source edge alone — source facts are evidence, not identity.
CAND_EXACT_VISUAL_DUPLICATE = "EXACT_VISUAL_DUPLICATE"
CAND_LIKELY_NEAR_DUPLICATE = "LIKELY_NEAR_DUPLICATE"
CAND_POSSIBLE_COLORWAY = "POSSIBLE_COLORWAY"
CAND_POSSIBLE_CROP_VARIANT = "POSSIBLE_CROP_VARIANT"
CAND_POSSIBLE_FORMAT_VARIANT = "POSSIBLE_FORMAT_VARIANT"
CAND_POSSIBLE_SCALE_VARIANT = "POSSIBLE_SCALE_VARIANT"
CAND_COLLECTION_MEMBER = "COLLECTION_MEMBER"
CAND_UNKNOWN_RELATIONSHIP = "UNKNOWN_RELATIONSHIP"
CANDIDATE_RELATIONSHIPS = (
    CAND_EXACT_VISUAL_DUPLICATE, CAND_LIKELY_NEAR_DUPLICATE,
    CAND_POSSIBLE_COLORWAY, CAND_POSSIBLE_CROP_VARIANT,
    CAND_POSSIBLE_FORMAT_VARIANT, CAND_POSSIBLE_SCALE_VARIANT,
    CAND_COLLECTION_MEMBER, CAND_UNKNOWN_RELATIONSHIP,
)
REL_REVIEW_REQUIRED = "REVIEW_REQUIRED"

# Perceptual-hash thresholds (64-bit). BOTH dHash and pHash must agree for a
# strong near-duplicate; disagreement drops the pair to REVIEW_REQUIRED.
HAMMING_STRONG = 6            # <= 6 : strong similarity candidate
HAMMING_REVIEW = 12           # 7-12 : review required;  > 12 : unrelated

# Information-content guards. These OVERRIDE hash distance: a blank, uniform or
# mostly-transparent image can never produce a confident near-duplicate.
INFO_MIN_STD = 8.0            # grayscale std below this = near-uniform
INFO_MIN_ALPHA_COVERAGE = 0.05
# Entropy catches only DEGENERATE images. It must stay low: flat vector artwork
# legitimately has few distinct grey levels (a 3-colour logo is ~1.2 bits) while
# carrying plenty of shape information, so a high entropy floor would wrongly
# condemn exactly the assets this library is made of. Variance is the real guard.
INFO_MIN_ENTROPY = 0.5        # bits
WEAK_EVIDENCE_CONFIDENCE_CAP = 0.30

# Transform variants that are hashed. A match holding ONLY under a transform is
# reported as explicit evidence, never as a silent near-duplicate.
XF_IDENTITY = "IDENTITY"
XF_MIRRORED = "MIRRORED"
XF_ROT90 = "ROT90"
XF_ROT180 = "ROT180"
XF_ROT270 = "ROT270"
TRANSFORMS = (XF_IDENTITY, XF_MIRRORED, XF_ROT90, XF_ROT180, XF_ROT270)

# Colorway / variant evidence thresholds
PALETTE_DIFFERENT_MIN = 0.25   # palette distance above this = materially different
PALETTE_SIMILAR_MAX = 0.10
SILHOUETTE_SIMILAR_MAX = 8     # shape-hash Hamming
ASPECT_SIMILAR_TOL = 0.08
SCALE_VARIANT_MIN_RATIO = 1.25  # dimensions differ by >= this = scale variant

# Family graph
STRONG_EDGE_CONFIDENCE = 0.60   # only these build connected components
WEAK_BRIDGE_CONFIDENCE = 0.75   # a sole-connector below this is a WEAK BRIDGE
POSTURE_CANONICAL_CANDIDATE = "CANONICAL_CANDIDATE"   # nominated, never selected

# --- DIP-0C2d vocabulary ----------------------------------------------------
OUT_C2D = OUTPUT_ROOT / "c2d"

# GROUP TYPES. A collection group is NOT a duplicate family: a sheet may hold many
# independent assets that are reviewed together but are in no way substitutes for
# one another. Never collapse these labels into the word "family".
GROUP_COLLECTION = "COLLECTION_GROUP"
GROUP_VISUAL_FAMILY = "VISUAL_FAMILY"                 # visual equivalence ONLY
GROUP_SOURCE_PACKAGE = "SOURCE_PACKAGE_FAMILY"
GROUP_EXACT_DUPLICATE = "EXACT_DUPLICATE_GROUP"
GROUP_CROSS_FORMAT = "CROSS_FORMAT_SOURCE_FAMILY"
GROUP_TYPES = (GROUP_COLLECTION, GROUP_VISUAL_FAMILY, GROUP_SOURCE_PACKAGE,
               GROUP_EXACT_DUPLICATE, GROUP_CROSS_FORMAT)

# The absence of a hash is NOT evidence of visual difference.
VISUAL_COMPARISON_UNAVAILABLE = "VISUAL_COMPARISON_UNAVAILABLE"

# Why an UNKNOWN_RELATIONSHIP edge is unresolved. UNKNOWN is a REVIEW QUEUE, never
# positive family evidence: a comparison was generated, the evidence was
# insufficient, and a human may clarify it.
UR_VISUAL_EVIDENCE_INSUFFICIENT = "VISUAL_EVIDENCE_INSUFFICIENT"
UR_SEGMENTATION_GRANULARITY_MISMATCH = "SEGMENTATION_GRANULARITY_MISMATCH"
UR_SOURCE_FAMILY_EVIDENCE_ONLY = "SOURCE_FAMILY_EVIDENCE_ONLY"
UR_CANDIDATE_VS_WHOLE_SHEET_MISMATCH = "CANDIDATE_VS_WHOLE_SHEET_MISMATCH"
UR_EPS_VISUAL_CAPABILITY_UNAVAILABLE = "EPS_VISUAL_CAPABILITY_UNAVAILABLE"
UR_LOW_INFORMATION_IMAGE = "LOW_INFORMATION_IMAGE"
UR_THRESHOLD_REVIEW_BAND = "THRESHOLD_REVIEW_BAND"
UR_CONFLICTING_HASH_EVIDENCE = "CONFLICTING_HASH_EVIDENCE"
UNKNOWN_REASONS = (
    UR_VISUAL_EVIDENCE_INSUFFICIENT, UR_SEGMENTATION_GRANULARITY_MISMATCH,
    UR_SOURCE_FAMILY_EVIDENCE_ONLY, UR_CANDIDATE_VS_WHOLE_SHEET_MISMATCH,
    UR_EPS_VISUAL_CAPABILITY_UNAVAILABLE, UR_LOW_INFORMATION_IMAGE,
    UR_THRESHOLD_REVIEW_BAND, UR_CONFLICTING_HASH_EVIDENCE,
)

# Batchable review queues
QUEUE_EXACT_DUPLICATES = "A_EXACT_DUPLICATES"
QUEUE_COLLECTION_GROUPS = "B_COLLECTION_GROUPS"
QUEUE_CROSS_FORMAT = "C_CROSS_FORMAT_SOURCE_FAMILIES"
QUEUE_UNKNOWN = "D_UNKNOWN_RELATIONSHIPS"
QUEUE_CANONICAL = "E_CANONICAL_CANDIDATE_NOMINATIONS"
QUEUE_EPS_UNAVAILABLE = "F_EPS_COMPARISON_UNAVAILABLE"
QUEUE_LOW_INFORMATION = "G_LOW_INFORMATION_VISUAL_EVIDENCE"
QUEUE_WEAK_BRIDGES = "H_WEAK_BRIDGES"
QUEUE_RIGHTS_BLOCKED = "I_RIGHTS_OWNERSHIP_BLOCKED"
REVIEW_QUEUES = (QUEUE_EXACT_DUPLICATES, QUEUE_COLLECTION_GROUPS,
                 QUEUE_CROSS_FORMAT, QUEUE_UNKNOWN, QUEUE_CANONICAL,
                 QUEUE_EPS_UNAVAILABLE, QUEUE_LOW_INFORMATION,
                 QUEUE_WEAK_BRIDGES, QUEUE_RIGHTS_BLOCKED)

PRIORITY_HIGH = "HIGH"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_LOW = "LOW"
PRIORITY_OPTIONAL = "OPTIONAL"
REVIEW_PRIORITIES = (PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW,
                     PRIORITY_OPTIONAL)

# Blocking safety limit (see c2d_known_limitations.md). Skipping is RECORDED, never
# silent, and is a documented scalability limitation — not a claim of completeness.
MAX_BUCKET_MEMBERS = 400


def human_review_block() -> dict:
    """Every field blank. A human decision NEVER overwrites machine inference —
    the two live in separate blocks and are reconciled by a person, not by code."""
    return {
        "reviewer": None,
        "reviewed_at": None,
        "relationship_confirmation": None,
        "family_confirmation": None,
        "collection_confirmation": None,
        "canonical_selection": None,
        "duplicate_disposition": None,
        "colorway_crop_format_confirmation": None,
        "reuse_approval": None,
        "exclusion_decision": None,
        "correction_reason": None,
        "notes": "",
    }


# --- DIP-0C3 vocabulary -----------------------------------------------------
OUT_C3A = C3A_OUTPUT_ROOT / "c3a"
OUT_C3A_REPORTS = C3A_OUTPUT_ROOT / "reports"
C3_PILOT_MANIFEST = DOCS_ROOT / "c3_pilot_manifest.json"

# --- OWNERSHIP (axis: who owns it) ------------------------------------------
# Neither a filename nor a folder can prove ownership: three of the five vector
# logos in the BBROSE office folder are third-party. Machine code routes every
# value through machine_ownership().
#
# Machine-permitted states are all UNCERTAIN. Every CONFIRMED or GRANTED state is
# human-only: confirming who owns a thing is a decision, not an inference.
OWN_UNKNOWN = "OWNERSHIP_UNKNOWN"
OWN_BBROSE_UNCONFIRMED = "BBROSE_OWNED_UNCONFIRMED"
OWN_THIRD_PARTY_UNCONFIRMED = "THIRD_PARTY_UNCONFIRMED"
OWN_DISPUTED = "OWNERSHIP_DISPUTED"
OWN_QUARANTINED = "QUARANTINED_PENDING_REVIEW"
# human only:
OWN_BBROSE_CONFIRMED = "BBROSE_OWNED_CONFIRMED"
OWN_THIRD_PARTY_CONFIRMED = "THIRD_PARTY_CONFIRMED"
OWN_LICENSED_LIMITED = "LICENSED_FOR_LIMITED_USE"
OWN_JOINT_OR_CONTRACTED = "JOINT_OR_CONTRACTED_USE"
# a BUSINESS ASSERTION — recorded, never a confirmation, grants nothing
OWN_BUSINESS_ASSERTED_BBROSE = "BUSINESS_ASSERTED_BBROSE"

MACHINE_ALLOWED_OWNERSHIP = (OWN_UNKNOWN, OWN_BBROSE_UNCONFIRMED,
                             OWN_THIRD_PARTY_UNCONFIRMED, OWN_DISPUTED,
                             OWN_QUARANTINED)
HUMAN_ONLY_OWNERSHIP = (OWN_BBROSE_CONFIRMED, OWN_THIRD_PARTY_CONFIRMED,
                        OWN_LICENSED_LIMITED, OWN_JOINT_OR_CONTRACTED)
OWNERSHIP_STATES = (MACHINE_ALLOWED_OWNERSHIP + HUMAN_ONLY_OWNERSHIP
                    + (OWN_BUSINESS_ASSERTED_BBROSE,))

# --- LICENCE (a SEPARATE axis from ownership) -------------------------------
# Ownership confirmation NEVER grants a licence; licence approval NEVER proves
# ownership. Every restrictive/approving state is a human decision.
LIC_UNVERIFIED = "LICENSE_UNVERIFIED"
LIC_NO_EVIDENCE = "NO_LICENSE_EVIDENCE"
LIC_COMMERCIAL_UNKNOWN = "COMMERCIAL_USE_UNKNOWN"
LIC_QUARANTINED = "QUARANTINED"
LIC_EXPIRED_OR_REVIEW = "EXPIRED_OR_REVIEW_REQUIRED"
# human only:
LIC_APPROVED = "LICENSE_APPROVED"
LIC_INTERNAL_ONLY = "INTERNAL_USE_ONLY"
LIC_ATTRIBUTION_REQUIRED = "ATTRIBUTION_REQUIRED"
LIC_MODIFICATION_RESTRICTED = "MODIFICATION_RESTRICTED"
LIC_EMBEDDING_RESTRICTED = "EMBEDDING_RESTRICTED"
LIC_REDISTRIBUTION_RESTRICTED = "REDISTRIBUTION_RESTRICTED"

MACHINE_ALLOWED_LICENSE = (LIC_UNVERIFIED, LIC_NO_EVIDENCE,
                           LIC_COMMERCIAL_UNKNOWN, LIC_QUARANTINED,
                           LIC_EXPIRED_OR_REVIEW)
HUMAN_ONLY_LICENSE = (LIC_APPROVED, LIC_INTERNAL_ONLY, LIC_ATTRIBUTION_REQUIRED,
                      LIC_MODIFICATION_RESTRICTED, LIC_EMBEDDING_RESTRICTED,
                      LIC_REDISTRIBUTION_RESTRICTED)
LICENSE_STATES = MACHINE_ALLOWED_LICENSE + HUMAN_ONLY_LICENSE

# --- CANONICAL BRAND MASTER -------------------------------------------------
# Canonical status answers "WHICH FILE IS AUTHORITATIVE?".
# Permissions answer   "WHAT MAY THE SYSTEM DO WITH IT?".
# These are never the same question — a file may be the canonical master while
# every operational permission remains false.
CANONICAL_BRAND_MASTER = "CANONICAL_BRAND_MASTER"        # human only
ALTERNATE_LOCKUP = "ALTERNATE_LOCKUP"                    # human only
MONOCHROME_VARIANT = "MONOCHROME_VARIANT"                # human only
COLOR_VARIANT = "COLOR_VARIANT"                          # human only
PRODUCT_SPECIFIC_VARIANT = "PRODUCT_SPECIFIC_VARIANT"    # human only
DEPRECATED_VERSION = "DEPRECATED_VERSION"                # human only
REJECTED_CANDIDATE = "REJECTED_CANDIDATE"                # human only
HUMAN_ONLY_CANONICAL = (CANONICAL_BRAND_MASTER, ALTERNATE_LOCKUP,
                        MONOCHROME_VARIANT, COLOR_VARIANT,
                        PRODUCT_SPECIFIC_VARIANT, DEPRECATED_VERSION,
                        REJECTED_CANDIDATE)

# the ONLY things a machine may say about canonical status
BRAND_MASTER_CANDIDATE = "BRAND_MASTER_CANDIDATE"
POSSIBLE_VARIANT = "POSSIBLE_VARIANT"
POSSIBLE_CONFLICT = "POSSIBLE_CONFLICT"
CANONICAL_REQUIRES_HUMAN = "REQUIRES_HUMAN"
MACHINE_ALLOWED_CANONICAL = (BRAND_MASTER_CANDIDATE, POSSIBLE_VARIANT,
                             POSSIBLE_CONFLICT, CANONICAL_REQUIRES_HUMAN)
CANONICAL_STATES = HUMAN_ONLY_CANONICAL + MACHINE_ALLOWED_CANONICAL

# --- permission scopes / effective status ------------------------------------
# A grant EVENT is historical and immutable. The EFFECTIVE value is evaluated.
EFF_GRANTED = "GRANTED"
EFF_DENIED_NO_GRANT = "DENIED_NO_GRANT"
EFF_DENIED_NOT_STARTED = "DENIED_NOT_YET_VALID"
EFF_DENIED_REVOKED = "DENIED_REVOKED"
EFF_DENIED_QUARANTINED = "DENIED_QUARANTINED"
EFF_DENIED_SCOPE = "DENIED_SCOPE_MISMATCH"
EFF_RE_REVIEW_REQUIRED = "RE_REVIEW_REQUIRED"           # expired -> fail closed
EFFECTIVE_STATUSES = (EFF_GRANTED, EFF_DENIED_NO_GRANT, EFF_DENIED_NOT_STARTED,
                      EFF_DENIED_REVOKED, EFF_DENIED_QUARANTINED,
                      EFF_DENIED_SCOPE, EFF_RE_REVIEW_REQUIRED)

# --- brand relationship hypotheses ------------------------------------------
BR_SAME_BRAND_VARIANT = "SAME_BRAND_VARIANT"
BR_POSSIBLE_OUTDATED_VERSION = "POSSIBLE_OUTDATED_VERSION"
BR_POSSIBLE_COLOR_VARIANT = "POSSIBLE_COLOR_VARIANT"
BR_POSSIBLE_LOCKUP_VARIANT = "POSSIBLE_LOCKUP_VARIANT"
BR_POSSIBLE_PRODUCT_VARIANT = "POSSIBLE_PRODUCT_VARIANT"
BR_POSSIBLE_THIRD_PARTY_ASSET = "POSSIBLE_THIRD_PARTY_ASSET"
BR_UNKNOWN = "UNKNOWN_BRAND_RELATIONSHIP"
BRAND_RELATIONSHIPS = (BR_SAME_BRAND_VARIANT, BR_POSSIBLE_OUTDATED_VERSION,
                       BR_POSSIBLE_COLOR_VARIANT, BR_POSSIBLE_LOCKUP_VARIANT,
                       BR_POSSIBLE_PRODUCT_VARIANT, BR_POSSIBLE_THIRD_PARTY_ASSET,
                       BR_UNKNOWN)

# C3 classification overrides
OVERRIDE_DESIGN_COMPOSITION = "DESIGN_COMPOSITION"

THIRD_PARTY_BRANDS = ("ATC", "JOJIA")


class HumanOnlyStateViolation(RuntimeError):
    """Raised if machine code tries to emit a human-only ownership/licence/master
    state. These decisions are never automatable."""


def machine_ownership(value: str) -> str:
    """Guard. A filename or folder may SUPPORT evidence; it can never prove
    ownership, so EVERY confirmed state is unreachable from machine code. A
    business assertion is likewise not something a machine may infer."""
    if value in HUMAN_ONLY_OWNERSHIP:
        raise HumanOnlyStateViolation(
            f"{value!r} is HUMAN-ONLY: confirming ownership is a decision, not an "
            f"inference. A machine may only ever say one of "
            f"{list(MACHINE_ALLOWED_OWNERSHIP)}")
    if value == OWN_BUSINESS_ASSERTED_BBROSE:
        raise HumanOnlyStateViolation(
            f"{value!r} records what a HUMAN asserted; a machine cannot invent a "
            "business assertion")
    if value not in MACHINE_ALLOWED_OWNERSHIP:
        raise HumanOnlyStateViolation(f"unknown ownership state: {value!r}")
    return value


def machine_license(value: str) -> str:
    """Guard. Evidence is never approval, and a restriction is a human reading of
    a licence, not a machine inference."""
    if value in HUMAN_ONLY_LICENSE:
        raise HumanOnlyStateViolation(
            f"{value!r} is HUMAN-ONLY: evidence is never approval. A machine may "
            f"only ever say one of {list(MACHINE_ALLOWED_LICENSE)}")
    if value not in MACHINE_ALLOWED_LICENSE:
        raise HumanOnlyStateViolation(f"unknown licence state: {value!r}")
    return value


def machine_brand_master(value: str) -> str:
    """Guard. A machine may NOMINATE or flag; it may never declare the canonical
    master, an approved variant, a lockup, a deprecation or a rejection. Deciding
    which file is authoritative is a human judgement about the brand."""
    if value in HUMAN_ONLY_CANONICAL:
        raise HumanOnlyStateViolation(
            f"{value!r} is HUMAN-ONLY: deciding which file is authoritative (or "
            f"how it relates to the master) is a human judgement. A machine may "
            f"only say one of {list(MACHINE_ALLOWED_CANONICAL)}")
    if value not in MACHINE_ALLOWED_CANONICAL and value is not None:
        raise HumanOnlyStateViolation(f"unknown canonical state: {value!r}")
    return value


def permission_matrix() -> dict:
    """Every permission independent, every one denied. A technically strong asset
    stays UNUSABLE until a human confirms these."""
    return {
        "retrieval_allowed": False,
        "automatic_use_allowed": False,
        "production_use_allowed": False,
        "modification_allowed": False,
        "embedding_allowed": False,
        "redistribution_allowed": False,
        "public_export_allowed": False,
        "approved_for_bbrose": False,
        "approved_for_other_brands": False,
        "approved_markets": [],
        "approved_products": [],
        "attribution_required": None,
        "review_expiry": None,
    }


# Raster role guess (HEURISTIC, human-reviewable)
ROLE_BACKGROUND = "BACKGROUND"
ROLE_TEXTURE = "TEXTURE"
ROLE_PHOTO = "PHOTO"
ROLE_ILLUSTRATION = "ILLUSTRATION"
ROLE_UNKNOWN = "UNKNOWN_ROLE"
RASTER_ROLES = (ROLE_BACKGROUND, ROLE_TEXTURE, ROLE_PHOTO, ROLE_ILLUSTRATION,
                ROLE_UNKNOWN)
