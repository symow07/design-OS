"""Canonical reviewer authorization policy — the ONE definition (DIP-1A-2 decoupling).

**This is the single source of truth for roles, actions, and who may do what.** It lives
inside the deployable application package and depends on nothing but the standard library:
no Django, no database, no filesystem, no `materials/`, no audit tooling. That is a hard
requirement — this module is imported at Django startup, during migrations, in CI, and by
the standalone DIP audit tools, and every one of those contexts must be able to import it
without dragging in anything else.

History: the policy originated in `tools/dip0c/authz.py` (DIP-0C3b2). When the Django
accounts app began storing role *assignments* against it (DIP-1A-2), importing the audit
tool at production startup became an accidental coupling — the production app would not
boot unless the `tools/` package shipped with it. The policy therefore moved **here**, and
`tools/dip0c/authz.py` is now a thin re-export. There is exactly one policy; the audit tool
sees precisely what production sees.

The policy is deliberately narrow: **no role may do everything.** A `SYSTEM_ADMIN` can
revoke and quarantine but may **not** confirm ownership, approve a licence, grant a
permission, or select a canonical master — administrative power is not legal authority. A
`DESIGN_REVIEWER` may review evidence about geometry but may not decide who owns the
artwork. `git` authorship is provenance, not authorization.
"""
from __future__ import annotations

POLICY_ID = "bbrose.reviewer.authz"
POLICY_VERSION_1_0 = "authz/1.0"
POLICY_VERSION_1_1 = "authz/1.1"
POLICY_VERSION_1_2 = "authz/1.2"
# DIP-1C-5B: the three human semantic-metadata actions are new, so the active policy
# advances to 1.3. 1.0/1.1/1.2 are preserved unchanged as immutable historical
# interpretation for events whose signed snapshot pins them.
POLICY_VERSION_1_3 = "authz/1.3"
POLICY_VERSION = "authz/1.4"

# The explicit public contract. `tools/dip0c/authz.py` re-exports exactly this set, and a
# test asserts the two modules agree name-for-name — so the audit tool can never drift
# from production policy. Keep this in sync when adding a role or action.
__all__ = [
    "POLICY_ID",
    "POLICY_VERSION", "POLICY_VERSION_1_0", "POLICY_VERSION_1_1", "POLICY_VERSION_1_2",
    "POLICY_VERSIONS",
    "RECORD_HUMAN_SEMANTIC_METADATA", "CORRECT_HUMAN_SEMANTIC_METADATA",
    "RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT",
    # roles
    "BUSINESS_OWNER", "BRAND_ADMIN", "LEGAL_REVIEWER", "DESIGN_REVIEWER",
    "SYSTEM_ADMIN", "OBSERVER", "ROLES",
    # actions
    "SUBMIT_ASSERTION", "WITHDRAW_ASSERTION", "SUBMIT_EVIDENCE", "REVIEW_EVIDENCE",
    "CONFIRM_OWNERSHIP", "CONFIRM_THIRD_PARTY", "APPROVE_LICENSE", "APPROVE_LIMITED_USE",
    "REVOKE_DECISION", "REQUIRE_RE_REVIEW", "APPROVE_CANONICAL_MASTER",
    "ATTEST_CANONICAL_TECHNICAL", "ATTEST_CANONICAL_LEGAL", "CLASSIFY_VARIANT",
    "DEPRECATE_CANONICAL", "CONFIRM_BRAND_IDENTITY", "CONFIRM_DESIGN_QUALITY",
    "APPROVE_BUSINESS_SCOPE", "GRANT_PERMISSION", "GRANT_LEGAL_PERMISSION",
    "REVOKE_PERMISSION", "EXECUTE_EXPIRY", "QUARANTINE_ASSET", "ATTEST_PALETTE_COLOR",
    "ATTEST_PALETTE_RIGHTS", "APPROVE_BRAND_PALETTE", "CONFIRM_PALETTE_ASSOCIATION",
    "DEPRECATE_PALETTE",
    "GRANT_REVIEWER_ROLE", "REVOKE_REVIEWER_ROLE", "ENABLE_REVIEWER_PROFILE",
    "DISABLE_REVIEWER_PROFILE",
    "VIEW_INTELLIGENCE_REVIEW_QUEUE", "CLAIM_INTELLIGENCE_REVIEW",
    "RECORD_INTELLIGENCE_CLASSIFICATION", "CORRECT_INTELLIGENCE_CLASSIFICATION",
    "RECORD_INTELLIGENCE_EVIDENCE_ASSESSMENT",
    "REQUEST_INTELLIGENCE_CLARIFICATION",
    "FINALIZE_CANONICAL_BRAND_ASSET", "REVOKE_CANONICAL_BRAND_ASSET",
    "FINALIZE_PRIMARY_BRAND_PALETTE", "REVOKE_PRIMARY_BRAND_PALETTE",
    "ACTIONS",
    # mappings + invariants
    "LEGAL_PERMISSIONS", "POLICY", "POLICY_V1_0", "POLICY_V1_1",
    "POLICIES_BY_VERSION",
    "SYSTEM_ADMIN_FORBIDDEN",
    # API
    "NotAuthorized", "may", "authorize", "permission_action",
    # deterministic role selection
    "ROLE_SELECTION_RULE", "ROLE_TIEBREAK", "role_breadth", "authorizing_roles",
    "select_role_used", "policy_for_version", "authorizing_roles_for_version",
    "select_role_used_for_version",
]

# --- roles ------------------------------------------------------------------
BUSINESS_OWNER = "BUSINESS_OWNER"
BRAND_ADMIN = "BRAND_ADMIN"
LEGAL_REVIEWER = "LEGAL_REVIEWER"
DESIGN_REVIEWER = "DESIGN_REVIEWER"
SYSTEM_ADMIN = "SYSTEM_ADMIN"
OBSERVER = "OBSERVER"
#: TEMPORARY WEB-REFERENCE REVIEW (owner-authorized, 2026-07-25): endpoint-side
#: web-source review only. DELIBERATELY absent from every action's role tuple
#: below — an assignment of this role authorizes NO decision-chain action
#: (metadata, fork resolution, gates, roles all stay denied by policy).
WEB_REFERENCE_REVIEWER = "WEB_REFERENCE_REVIEWER"
ROLES = (BUSINESS_OWNER, BRAND_ADMIN, LEGAL_REVIEWER, DESIGN_REVIEWER,
         SYSTEM_ADMIN, OBSERVER, WEB_REFERENCE_REVIEWER)

# --- actions ----------------------------------------------------------------
SUBMIT_ASSERTION = "submit_assertion"
WITHDRAW_ASSERTION = "withdraw_assertion"
SUBMIT_EVIDENCE = "submit_evidence"
REVIEW_EVIDENCE = "review_evidence"
CONFIRM_OWNERSHIP = "confirm_ownership"
CONFIRM_THIRD_PARTY = "confirm_third_party"
APPROVE_LICENSE = "approve_license"
APPROVE_LIMITED_USE = "approve_limited_use"
REVOKE_DECISION = "revoke_decision"
REQUIRE_RE_REVIEW = "require_re_review"
# --- C3b3 ---
APPROVE_CANONICAL_MASTER = "approve_canonical_master"
# --- dual control: a canonical master needs TWO attestations from TWO people ---
ATTEST_CANONICAL_TECHNICAL = "attest_canonical_technical"
ATTEST_CANONICAL_LEGAL = "attest_canonical_legal"
CLASSIFY_VARIANT = "classify_variant"            # lockup / colour / product variant
DEPRECATE_CANONICAL = "deprecate_canonical"
CONFIRM_BRAND_IDENTITY = "confirm_brand_identity"
CONFIRM_DESIGN_QUALITY = "confirm_design_quality"   # geometry, proportions, colour
APPROVE_BUSINESS_SCOPE = "approve_business_scope"   # BBROSE product/market scope
GRANT_PERMISSION = "grant_permission"
GRANT_LEGAL_PERMISSION = "grant_legal_permission"   # redistribution, public export
REVOKE_PERMISSION = "revoke_permission"
EXECUTE_EXPIRY = "execute_expiry"
QUARANTINE_ASSET = "quarantine_asset"
# --- C3d: palette authority. Approving a brand palette is as consequential as
# approving a canonical master, so it takes the same shape: two attestations, two
# people, and a BRAND_ADMIN-only activation.
ATTEST_PALETTE_COLOR = "attest_palette_color"      # colour + brand half
ATTEST_PALETTE_RIGHTS = "attest_palette_rights"    # rights + use half (legal only)
APPROVE_BRAND_PALETTE = "approve_brand_palette"    # final activation
CONFIRM_PALETTE_ASSOCIATION = "confirm_palette_association"
DEPRECATE_PALETTE = "deprecate_palette"
# --- DIP-1A-5A: reviewer-role administration. Appointing a reviewer confers
# authority, so it is a protected, signed decision like the others. Granting/enabling
# is appointing authority (never SYSTEM_ADMIN); revoking/disabling only REDUCES, so
# SYSTEM_ADMIN may do those.
GRANT_REVIEWER_ROLE = "grant_reviewer_role"
REVOKE_REVIEWER_ROLE = "revoke_reviewer_role"
ENABLE_REVIEWER_PROFILE = "enable_reviewer_profile"
DISABLE_REVIEWER_PROFILE = "disable_reviewer_profile"
VIEW_INTELLIGENCE_REVIEW_QUEUE = "view_intelligence_review_queue"
CLAIM_INTELLIGENCE_REVIEW = "claim_intelligence_review"
RECORD_INTELLIGENCE_CLASSIFICATION = "record_intelligence_classification"
CORRECT_INTELLIGENCE_CLASSIFICATION = "correct_intelligence_classification"
# DIP-1C-5B: bounded human descriptive metadata for search. These DESCRIBE an item; none
# grants operational authority. Distinct actions so they never masquerade as classification.
RECORD_HUMAN_SEMANTIC_METADATA = "record_human_semantic_metadata"
CORRECT_HUMAN_SEMANTIC_METADATA = "correct_human_semantic_metadata"
# DIP-1C-5C-CORR-4: resolve MULTIPLE active metadata events into one effective bundle.
# Distinct from a correction because it invalidates a SET of prior events rather than one
# parent, so it must be separately authorized and separately auditable.
RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT = "resolve_human_semantic_metadata_conflict"
# A `request_semantic_metadata_clarification` action was considered and DELIBERATELY NOT
# added: DIP-1C-5B builds no clarification workflow, and an authorized, signable action with
# no service, view or projector handler is not a placeholder — it is a latent failure, since
# the projector fails closed on any intelligence event it cannot project. Reviewers raise
# metadata questions through the existing evidence-clarification path until a real workflow
# is specified.
RECORD_INTELLIGENCE_EVIDENCE_ASSESSMENT = (
    "record_intelligence_evidence_assessment")
REQUEST_INTELLIGENCE_CLARIFICATION = "request_intelligence_clarification"
# --- DIP-1B-4B: bounded, dual-control governance selections. Finalization identifies
# the candidate selected for one strict scope and grants no operational permission.
# Revocation only reduces governance state and remains an emergency-brake action.
FINALIZE_CANONICAL_BRAND_ASSET = "finalize_canonical_brand_asset"
REVOKE_CANONICAL_BRAND_ASSET = "revoke_canonical_brand_asset"
FINALIZE_PRIMARY_BRAND_PALETTE = "finalize_primary_brand_palette"
REVOKE_PRIMARY_BRAND_PALETTE = "revoke_primary_brand_palette"
ACTIONS = (SUBMIT_ASSERTION, WITHDRAW_ASSERTION, SUBMIT_EVIDENCE, REVIEW_EVIDENCE,
           CONFIRM_OWNERSHIP, CONFIRM_THIRD_PARTY, APPROVE_LICENSE,
           APPROVE_LIMITED_USE, REVOKE_DECISION, REQUIRE_RE_REVIEW,
           GRANT_REVIEWER_ROLE, REVOKE_REVIEWER_ROLE, ENABLE_REVIEWER_PROFILE,
           DISABLE_REVIEWER_PROFILE,
           APPROVE_CANONICAL_MASTER, ATTEST_CANONICAL_TECHNICAL,
           ATTEST_CANONICAL_LEGAL, CLASSIFY_VARIANT, DEPRECATE_CANONICAL,
           CONFIRM_BRAND_IDENTITY, CONFIRM_DESIGN_QUALITY, APPROVE_BUSINESS_SCOPE,
           GRANT_PERMISSION, GRANT_LEGAL_PERMISSION, REVOKE_PERMISSION,
           EXECUTE_EXPIRY, QUARANTINE_ASSET,
           ATTEST_PALETTE_COLOR, ATTEST_PALETTE_RIGHTS, APPROVE_BRAND_PALETTE,
           CONFIRM_PALETTE_ASSOCIATION, DEPRECATE_PALETTE,
           VIEW_INTELLIGENCE_REVIEW_QUEUE, CLAIM_INTELLIGENCE_REVIEW,
           RECORD_INTELLIGENCE_CLASSIFICATION, CORRECT_INTELLIGENCE_CLASSIFICATION,
           RECORD_INTELLIGENCE_EVIDENCE_ASSESSMENT,
           REQUEST_INTELLIGENCE_CLARIFICATION,
           FINALIZE_CANONICAL_BRAND_ASSET, REVOKE_CANONICAL_BRAND_ASSET,
           FINALIZE_PRIMARY_BRAND_PALETTE, REVOKE_PRIMARY_BRAND_PALETTE,
           RECORD_HUMAN_SEMANTIC_METADATA, CORRECT_HUMAN_SEMANTIC_METADATA,
           RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT)

# Legal permissions — the ones that expose the asset OUTSIDE the company.
LEGAL_PERMISSIONS = ("redistribution_allowed", "public_export_allowed",
                     "approved_for_other_brands")

# --- the policy -------------------------------------------------------------
# Read it as: "which roles may perform this action?"
POLICY_V1_0: dict[str, tuple[str, ...]] = {
    SUBMIT_ASSERTION:    (BUSINESS_OWNER, BRAND_ADMIN),
    WITHDRAW_ASSERTION:  (BUSINESS_OWNER, BRAND_ADMIN),
    SUBMIT_EVIDENCE:     (BUSINESS_OWNER, BRAND_ADMIN, LEGAL_REVIEWER,
                          DESIGN_REVIEWER),
    REVIEW_EVIDENCE:     (LEGAL_REVIEWER, BRAND_ADMIN, DESIGN_REVIEWER),
    # ownership is a LEGAL determination — a designer or an admin cannot decide it
    CONFIRM_OWNERSHIP:   (LEGAL_REVIEWER, BRAND_ADMIN),
    CONFIRM_THIRD_PARTY: (LEGAL_REVIEWER, BRAND_ADMIN),
    # licensing is legal counsel's call ALONE
    APPROVE_LICENSE:     (LEGAL_REVIEWER,),
    APPROVE_LIMITED_USE: (LEGAL_REVIEWER,),
    # anyone with standing may pull the emergency brake — revocation only REDUCES
    REVOKE_DECISION:     (LEGAL_REVIEWER, BRAND_ADMIN, SYSTEM_ADMIN),
    REQUIRE_RE_REVIEW:   (LEGAL_REVIEWER, BRAND_ADMIN, SYSTEM_ADMIN,
                          DESIGN_REVIEWER),

    # --- C3b3 ---
    # Deciding WHICH FILE IS AUTHORITATIVE is a brand judgement, not an admin one —
    # and it is under DUAL CONTROL. Final activation is BRAND_ADMIN's, but it is
    # only reachable once BOTH attestations below exist, from two DIFFERENT people.
    APPROVE_CANONICAL_MASTER:   (BRAND_ADMIN,),
    ATTEST_CANONICAL_TECHNICAL: (DESIGN_REVIEWER, BRAND_ADMIN),
    # the rights half of a canonical approval is legal counsel's, and no one else's
    ATTEST_CANONICAL_LEGAL:     (LEGAL_REVIEWER,),
    CLASSIFY_VARIANT:         (BRAND_ADMIN, DESIGN_REVIEWER),
    DEPRECATE_CANONICAL:      (BRAND_ADMIN, BUSINESS_OWNER),
    CONFIRM_BRAND_IDENTITY:   (BRAND_ADMIN, BUSINESS_OWNER),
    # geometry, proportions, colour — the designer's expertise
    CONFIRM_DESIGN_QUALITY:   (DESIGN_REVIEWER, BRAND_ADMIN),
    APPROVE_BUSINESS_SCOPE:   (BUSINESS_OWNER, BRAND_ADMIN),
    # granting operational use
    GRANT_PERMISSION:         (LEGAL_REVIEWER, BRAND_ADMIN),
    # ...but anything that exposes the asset OUTSIDE the company is legal's alone
    GRANT_LEGAL_PERMISSION:   (LEGAL_REVIEWER,),
    REVOKE_PERMISSION:        (LEGAL_REVIEWER, BRAND_ADMIN, SYSTEM_ADMIN),
    EXECUTE_EXPIRY:           (SYSTEM_ADMIN, LEGAL_REVIEWER, BRAND_ADMIN),
    QUARANTINE_ASSET:         (SYSTEM_ADMIN, LEGAL_REVIEWER, BRAND_ADMIN),

    # --- C3d: palette authority ---
    # the colour/brand half — a designer's or a brand admin's judgement
    ATTEST_PALETTE_COLOR:        (BRAND_ADMIN, DESIGN_REVIEWER),
    # ...the rights half is legal counsel's ALONE
    ATTEST_PALETTE_RIGHTS:       (LEGAL_REVIEWER,),
    # final activation, once BOTH attestations exist, from two DIFFERENT people
    APPROVE_BRAND_PALETTE:       (BRAND_ADMIN,),
    CONFIRM_PALETTE_ASSOCIATION: (BRAND_ADMIN, BUSINESS_OWNER),
    DEPRECATE_PALETTE:           (BRAND_ADMIN, BUSINESS_OWNER),

    # --- DIP-1A-5A: reviewer-role administration ---
    # appointing a reviewer confers authority — a business/brand decision, never admin
    GRANT_REVIEWER_ROLE:      (BUSINESS_OWNER, BRAND_ADMIN),
    ENABLE_REVIEWER_PROFILE:  (BUSINESS_OWNER, BRAND_ADMIN),
    # revoking/disabling only REDUCES authority, so SYSTEM_ADMIN may pull the brake
    REVOKE_REVIEWER_ROLE:     (BUSINESS_OWNER, BRAND_ADMIN, SYSTEM_ADMIN),
    DISABLE_REVIEWER_PROFILE: (BUSINESS_OWNER, BRAND_ADMIN, SYSTEM_ADMIN),
}

# DIP-1B-3 adds a bounded human-intelligence workflow. These actions record review work
# and signed assertions; none grants operational authority. The prior mapping remains
# immutable historical interpretation for events whose signed snapshot pins authz/1.0.
POLICY_V1_1: dict[str, tuple[str, ...]] = {
    **POLICY_V1_0,
    VIEW_INTELLIGENCE_REVIEW_QUEUE: (
        BUSINESS_OWNER, BRAND_ADMIN, LEGAL_REVIEWER, DESIGN_REVIEWER),
    CLAIM_INTELLIGENCE_REVIEW: (
        BUSINESS_OWNER, BRAND_ADMIN, LEGAL_REVIEWER, DESIGN_REVIEWER),
    RECORD_INTELLIGENCE_CLASSIFICATION: (
        BUSINESS_OWNER, BRAND_ADMIN, DESIGN_REVIEWER),
    CORRECT_INTELLIGENCE_CLASSIFICATION: (
        BUSINESS_OWNER, BRAND_ADMIN, DESIGN_REVIEWER),
    RECORD_INTELLIGENCE_EVIDENCE_ASSESSMENT: (
        BRAND_ADMIN, LEGAL_REVIEWER, DESIGN_REVIEWER),
    REQUEST_INTELLIGENCE_CLARIFICATION: (
        BUSINESS_OWNER, BRAND_ADMIN, LEGAL_REVIEWER, DESIGN_REVIEWER),
}

# DIP-1B-4B adds only the four explicit governance transition actions. Finalization is a
# BRAND_ADMIN decision reached only after the service verifies complementary attestations.
# Revocation reduces state, so the established emergency-brake roles may perform it.
# Neither action grants an operational permission.
POLICY_V1_2: dict[str, tuple[str, ...]] = {
    **POLICY_V1_1,
    FINALIZE_CANONICAL_BRAND_ASSET: (BRAND_ADMIN,),
    REVOKE_CANONICAL_BRAND_ASSET: (BUSINESS_OWNER, BRAND_ADMIN, SYSTEM_ADMIN),
    FINALIZE_PRIMARY_BRAND_PALETTE: (BRAND_ADMIN,),
    REVOKE_PRIMARY_BRAND_PALETTE: (BUSINESS_OWNER, BRAND_ADMIN, SYSTEM_ADMIN),
}

# DIP-1C-5B adds the three human semantic-metadata actions. These record bounded, signed
# DESCRIPTIVE metadata to improve search; none grants operational authority. Descriptive
# review is a designer/brand judgement; legal counsel is not required to describe an item.
POLICY_V1_3: dict[str, tuple[str, ...]] = {
    **POLICY_V1_2,
    RECORD_HUMAN_SEMANTIC_METADATA: (BUSINESS_OWNER, BRAND_ADMIN, DESIGN_REVIEWER),
    CORRECT_HUMAN_SEMANTIC_METADATA: (BUSINESS_OWNER, BRAND_ADMIN, DESIGN_REVIEWER),
}
# 1.4 adds conflict resolution. Same substantive reviewer roles as correction — resolving
# duplicates is descriptive judgement, not authority — and SYSTEM_ADMIN stays forbidden.
POLICY: dict[str, tuple[str, ...]] = {
    **POLICY_V1_3,
    RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT: (
        BUSINESS_OWNER, BRAND_ADMIN, DESIGN_REVIEWER),
}
POLICIES_BY_VERSION = {
    POLICY_VERSION_1_0: POLICY_V1_0,
    POLICY_VERSION_1_1: POLICY_V1_1,
    POLICY_VERSION_1_2: POLICY_V1_2,
    POLICY_VERSION_1_3: POLICY_V1_3,
    POLICY_VERSION: POLICY,
}
POLICY_VERSIONS = tuple(POLICIES_BY_VERSION)

# SYSTEM_ADMIN may only ever REDUCE. It can quarantine, revoke, expire and demand
# re-review — and it may NEVER confirm ownership, approve a licence, grant any
# permission, or select the canonical master. Administrative power is not authority.
SYSTEM_ADMIN_FORBIDDEN = (CONFIRM_OWNERSHIP, CONFIRM_THIRD_PARTY, APPROVE_LICENSE,
                          APPROVE_LIMITED_USE, APPROVE_CANONICAL_MASTER,
                          ATTEST_CANONICAL_TECHNICAL, ATTEST_CANONICAL_LEGAL,
                          CLASSIFY_VARIANT, GRANT_PERMISSION,
                          GRANT_LEGAL_PERMISSION, CONFIRM_BRAND_IDENTITY,
                          APPROVE_BUSINESS_SCOPE,
                          ATTEST_PALETTE_COLOR, ATTEST_PALETTE_RIGHTS,
                          APPROVE_BRAND_PALETTE, CONFIRM_PALETTE_ASSOCIATION,
                          # appointing a reviewer / enabling participation confers
                          # authority — admin power is not authority
                          GRANT_REVIEWER_ROLE, ENABLE_REVIEWER_PROFILE,
                          VIEW_INTELLIGENCE_REVIEW_QUEUE, CLAIM_INTELLIGENCE_REVIEW,
                          RECORD_INTELLIGENCE_CLASSIFICATION,
                          CORRECT_INTELLIGENCE_CLASSIFICATION,
                          RECORD_INTELLIGENCE_EVIDENCE_ASSESSMENT,
                          REQUEST_INTELLIGENCE_CLARIFICATION,
                          FINALIZE_CANONICAL_BRAND_ASSET,
                          FINALIZE_PRIMARY_BRAND_PALETTE,
                          # descriptive metadata is substantive review, not admin power
                          RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT,
                          RECORD_HUMAN_SEMANTIC_METADATA,
                          CORRECT_HUMAN_SEMANTIC_METADATA)

# --- invariants, enforced at import (not by convention) ---------------------
# An OBSERVER appears in no policy entry: read-only by construction.
assert not any(OBSERVER in roles for roles in POLICY.values())
# SYSTEM_ADMIN may only ever reduce.
assert not any(SYSTEM_ADMIN in POLICY[a] for a in SYSTEM_ADMIN_FORBIDDEN), (
    "SYSTEM_ADMIN must never confirm, approve, grant or select a canonical master")
# Every POLICY key and value is a known action / known role — no typo can create a
# silent orphan mapping that authorises nothing or names a non-role.
assert set(POLICY).issubset(set(ACTIONS)), "POLICY names an unknown action"
assert all(r in ROLES for roles in POLICY.values() for r in roles), (
    "POLICY names an unknown role")


class NotAuthorized(RuntimeError):
    """Raised when an actor's role does not permit the requested action."""


def may(role: str, action: str) -> bool:
    if role not in ROLES:
        return False
    return role in POLICY.get(action, ())


def authorize(role: str, action: str, *, actor_id: str = "?") -> str:
    """The ONE place a (role, action) pair is decided. Raises, or returns the action."""
    if role not in ROLES:
        raise NotAuthorized(f"unknown role {role!r} for actor {actor_id!r}")
    if action not in ACTIONS:
        raise NotAuthorized(f"unknown action {action!r}")
    if not may(role, action):
        raise NotAuthorized(
            f"role {role!r} may NOT {action!r}. Permitted roles: "
            f"{list(POLICY[action])}. (Git authorship is provenance, not "
            "authorisation.)")
    return action


def permission_action(flag: str) -> str:
    """Which action does granting THIS permission require? Anything that exposes
    the asset outside the company is LEGAL_REVIEWER's alone."""
    return GRANT_LEGAL_PERMISSION if flag in LEGAL_PERMISSIONS else GRANT_PERMISSION


# --- deterministic role selection (used by the 1A-3 authorization service) ---------
# When an actor holds several roles that all authorise an action, exactly ONE is
# recorded as `role_used`. The rule is fixed and policy-defined — never database row
# order, set iteration, alphabetical accident, or anything from the request body.
#
# The rule is LEAST PRIVILEGE, computed from the policy itself: pick the authorising
# role that can perform the FEWEST actions overall (the narrowest authority), so a
# legal determination is attributed to LEGAL_REVIEWER rather than to a BRAND_ADMIN who
# merely also qualifies, and a revocation is attributed to the reduce-only SYSTEM_ADMIN.
# Ties break by a fixed order (ROLES) so the result is total and reproducible.
ROLE_SELECTION_RULE = "least_privilege_by_action_breadth/1.0"
ROLE_TIEBREAK = ROLES


def role_breadth(role: str) -> int:
    """How many distinct actions this role may perform. Smaller = less privileged."""
    return sum(1 for a in ACTIONS if role in POLICY.get(a, ()))


def policy_for_version(version: str):
    """Return the exact frozen mapping for a signed policy version, or ``None``."""
    return POLICIES_BY_VERSION.get(version)


def _role_breadth_for_policy(role: str, policy) -> int:
    return sum(1 for roles in policy.values() if role in roles)


def authorizing_roles(action: str, roles) -> tuple[str, ...]:
    """The subset of `roles` that may perform `action`, in canonical ROLES order."""
    permitted = POLICY.get(action, ())
    held = set(roles)
    return tuple(r for r in ROLES if r in held and r in permitted)


def select_role_used(action: str, active_roles) -> str | None:
    """Deterministically choose the single `role_used`, or None if none authorise.

    Least-privileged authorising role wins (narrowest authority by action breadth),
    ties broken by ROLE_TIEBREAK. The caller never chooses; policy does.
    """
    candidates = authorizing_roles(action, active_roles)
    if not candidates:
        return None
    return min(candidates, key=lambda r: (role_breadth(r), ROLE_TIEBREAK.index(r)))


def authorizing_roles_for_version(version: str, action: str, roles) -> tuple[str, ...]:
    policy = policy_for_version(version)
    if policy is None:
        return ()
    permitted = policy.get(action, ())
    held = set(roles)
    return tuple(r for r in ROLES if r in held and r in permitted)


def select_role_used_for_version(version: str, action: str, active_roles) -> str | None:
    policy = policy_for_version(version)
    if policy is None:
        return None
    candidates = authorizing_roles_for_version(version, action, active_roles)
    if not candidates:
        return None
    return min(candidates, key=lambda r: (
        _role_breadth_for_policy(r, policy), ROLE_TIEBREAK.index(r)))
