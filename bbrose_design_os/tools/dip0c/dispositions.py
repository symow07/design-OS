"""Machine recommendations and human decisions — two disjoint vocabularies (DIP-0C5).

A machine may **recommend**. Only a human may **decide**. The two vocabularies share no
value, so a recommendation cannot become a decision by copying a string from one field
to another — the guard raises, and a test proves the sets do not intersect.

This is the whole of DIP-0 compressed into one module: eleven slices of "the machine may
only reduce certainty or permission, never increase it", expressed as two lists that must
never touch.
"""
from __future__ import annotations

from . import config as C

PARSER = f"{C.TOOL_NAME}.dispositions/{C.TOOL_VERSION}"
SCHEMA_VERSION = "disposition/1.0"

# --- what a MACHINE may recommend ------------------------------------------------
RECOMMEND_INCLUDE_AS_REFERENCE_MEMORY = "RECOMMEND_INCLUDE_AS_REFERENCE_MEMORY"
RECOMMEND_EXCLUDE_FROM_MEMORY = "RECOMMEND_EXCLUDE_FROM_MEMORY"
REUSABLE_AFTER_REVIEW = "REUSABLE_AFTER_REVIEW"
TECHNICALLY_READY = "TECHNICALLY_READY"
NEEDS_CLEANUP = "NEEDS_CLEANUP"
NEEDS_VECTOR_RECONSTRUCTION = "NEEDS_VECTOR_RECONSTRUCTION"
REFERENCE_ONLY = "REFERENCE_ONLY"
RIGHTS_REVIEW_REQUIRED = "RIGHTS_REVIEW_REQUIRED"
PROVENANCE_MISSING = "PROVENANCE_MISSING"
QUARANTINE_CANDIDATE = "QUARANTINE_CANDIDATE"
OUT_OF_SCOPE = "OUT_OF_SCOPE"
REQUIRES_TOOL = "REQUIRES_TOOL"
REQUIRES_HUMAN = "REQUIRES_HUMAN"

MACHINE_RECOMMENDATIONS = (
    RECOMMEND_INCLUDE_AS_REFERENCE_MEMORY, RECOMMEND_EXCLUDE_FROM_MEMORY,
    REUSABLE_AFTER_REVIEW, TECHNICALLY_READY, NEEDS_CLEANUP,
    NEEDS_VECTOR_RECONSTRUCTION, REFERENCE_ONLY, RIGHTS_REVIEW_REQUIRED,
    PROVENANCE_MISSING, QUARANTINE_CANDIDATE, OUT_OF_SCOPE, REQUIRES_TOOL,
    REQUIRES_HUMAN,
)

# --- what only a HUMAN may decide -------------------------------------------------
APPROVE_REFERENCE_MEMORY = "APPROVE_REFERENCE_MEMORY"
APPROVE_REUSABLE_ASSET = "APPROVE_REUSABLE_ASSET"
APPROVE_BRAND_ASSET = "APPROVE_BRAND_ASSET"
APPROVE_CANONICAL_MASTER = "APPROVE_CANONICAL_MASTER"
APPROVE_PALETTE = "APPROVE_PALETTE"
APPROVE_FONT = "APPROVE_FONT"
APPROVE_LIMITED_USE = "APPROVE_LIMITED_USE"
REJECT = "REJECT"
QUARANTINE = "QUARANTINE"
DEFER = "DEFER"
REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
REQUEST_CLEANUP = "REQUEST_CLEANUP"
SUPERSEDE = "SUPERSEDE"
DEPRECATE = "DEPRECATE"

HUMAN_DECISIONS = (
    APPROVE_REFERENCE_MEMORY, APPROVE_REUSABLE_ASSET, APPROVE_BRAND_ASSET,
    APPROVE_CANONICAL_MASTER, APPROVE_PALETTE, APPROVE_FONT, APPROVE_LIMITED_USE,
    REJECT, QUARANTINE, DEFER, REQUEST_EVIDENCE, REQUEST_CLEANUP, SUPERSEDE,
    DEPRECATE,
)

# The two vocabularies MUST NOT INTERSECT. Enforced at import, not by convention:
# a shared value would be a doorway from "the machine thinks" to "a human decided".
assert not (set(MACHINE_RECOMMENDATIONS) & set(HUMAN_DECISIONS)), (
    "a machine recommendation and a human decision must never share a value")

# Which decisions actually GRANT something. None of them grants a permission — a
# permission is granted separately, by flag, and never by an approval.
GRANTS_NO_PERMISSION = tuple(HUMAN_DECISIONS)


def machine_disposition(value: str | None) -> str | None:
    """Guard. Machine code may recommend; it may never decide."""
    if value is None:
        return None
    if value in HUMAN_DECISIONS:
        raise C.HumanOnlyStateViolation(
            f"{value!r} is a HUMAN DECISION. Machine code may only recommend. "
            f"Permitted machine recommendations: {list(MACHINE_RECOMMENDATIONS)}")
    if value not in MACHINE_RECOMMENDATIONS:
        raise ValueError(f"{value!r} is not a known machine recommendation")
    return value


def human_decision(value: str) -> str:
    """A human decision. Recorded; never inferred."""
    if value not in HUMAN_DECISIONS:
        raise ValueError(
            f"{value!r} is not a human decision. If it is a machine recommendation, "
            "it does NOT become a decision by being written into a decision field.")
    return value


def decision_grants_permission(_decision: str) -> bool:
    """**No.** Not one of them.

    Approving a canonical master grants nothing. Approving a palette grants nothing.
    Approving a font grants nothing. A permission is granted separately, by name, by an
    authorised human — the discipline established in C3b3 and never once relaxed.
    """
    return False
