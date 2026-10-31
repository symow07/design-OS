"""The twelve review domains (DIP-0C5).

Each domain declares what a human may do in it, who may do it, whether it takes two
people, whether it expires, and which permissions could *eventually* be granted — never
which are granted, because none are.

**Domains are not merged.** The same subject reviewed in two different domains is two
different decisions: a `FONT_FACE` review asks *"is this typographically what we think it
is?"*; a `PROVENANCE_RIGHTS_GROUP` review asks *"do we know where this copy came from?"*.
Collapsing them would let a technical confirmation imply a rights one — the C4b defect,
one layer up.
"""
from __future__ import annotations

from . import authz
from . import config as C
from . import dispositions as D

PARSER = f"{C.TOOL_NAME}.review_domains/{C.TOOL_VERSION}"
SCHEMA_VERSION = "review_domain/1.0"

HISTORICAL_DESIGN_UNIT = "HISTORICAL_DESIGN_UNIT"
REUSABLE_ASSET = "REUSABLE_ASSET"
BRAND_ASSET = "BRAND_ASSET"
CANONICAL_MASTER_CANDIDATE = "CANONICAL_MASTER_CANDIDATE"
COLOR_PALETTE = "COLOR_PALETTE"
FONT_FACE = "FONT_FACE"
FONT_FAMILY = "FONT_FAMILY"
FONT_SOURCE_PACKAGE = "FONT_SOURCE_PACKAGE"
LICENSE_EVIDENCE = "LICENSE_EVIDENCE"
OWNERSHIP_EVIDENCE = "OWNERSHIP_EVIDENCE"
QUARANTINE_BATCH = "QUARANTINE_BATCH"
PROVENANCE_RIGHTS_GROUP = "PROVENANCE_RIGHTS_GROUP"

DOMAINS = (
    HISTORICAL_DESIGN_UNIT, REUSABLE_ASSET, BRAND_ASSET,
    CANONICAL_MASTER_CANDIDATE, COLOR_PALETTE, FONT_FACE, FONT_FAMILY,
    FONT_SOURCE_PACKAGE, LICENSE_EVIDENCE, OWNERSHIP_EVIDENCE, QUARANTINE_BATCH,
    PROVENANCE_RIGHTS_GROUP,
)

# Permission flags a domain could EVENTUALLY reach. Not one is granted.
_RETRIEVE = ("retrieval_allowed",)
_ASSET_PERMS = ("retrieval_allowed", "automatic_use_allowed",
                "production_use_allowed", "modification_allowed",
                "embedding_allowed")

SPEC = {
    HISTORICAL_DESIGN_UNIT: {
        "question": "may this design inform REFERENCE MEMORY?",
        "allowed_human_actions": (D.APPROVE_REFERENCE_MEMORY, D.REJECT, D.DEFER,
                                  D.REQUEST_EVIDENCE),
        "required_roles": (authz.DESIGN_REVIEWER, authz.BRAND_ADMIN),
        "batch_review_allowed": True,
        "dual_control_required": False,
        "expiry_applies": False,
        "eventual_permissions": _RETRIEVE,
        "note": "REFERENCE MEMORY ONLY. A historical design is never a template and "
                "never becomes reusable geometry.",
    },
    REUSABLE_ASSET: {
        "question": "is this an isolated, technically ready, rights-clear asset?",
        "allowed_human_actions": (D.APPROVE_REUSABLE_ASSET, D.REJECT, D.DEFER,
                                  D.REQUEST_CLEANUP, D.REQUEST_EVIDENCE,
                                  D.QUARANTINE),
        "required_roles": (authz.DESIGN_REVIEWER, authz.BRAND_ADMIN,
                           authz.LEGAL_REVIEWER),
        "batch_review_allowed": True,
        "dual_control_required": False,
        "expiry_applies": True,
        "eventual_permissions": _ASSET_PERMS,
        "note": "technical readiness and rights are separate axes and never collapse",
    },
    BRAND_ASSET: {
        "question": "is this BBROSE's brand material at all?",
        "allowed_human_actions": (D.APPROVE_BRAND_ASSET, D.REJECT, D.DEFER,
                                  D.REQUEST_EVIDENCE, D.QUARANTINE),
        "required_roles": (authz.BRAND_ADMIN, authz.LEGAL_REVIEWER),
        "batch_review_allowed": False,
        "dual_control_required": False,
        "expiry_applies": True,
        "eventual_permissions": _ASSET_PERMS,
        "note": "folder location has never implied ownership",
    },
    CANONICAL_MASTER_CANDIDATE: {
        "question": "WHICH FILE IS the brand?",
        "allowed_human_actions": (D.APPROVE_CANONICAL_MASTER, D.REJECT, D.DEFER,
                                  D.SUPERSEDE, D.DEPRECATE, D.QUARANTINE),
        "required_roles": (authz.BRAND_ADMIN, authz.DESIGN_REVIEWER,
                           authz.LEGAL_REVIEWER),
        "batch_review_allowed": False,
        "dual_control_required": True,          # C3b3
        "expiry_applies": True,
        "eventual_permissions": _ASSET_PERMS,
        "note": "DUAL CONTROL: two attestations, two distinct people. Canonical status "
                "grants NO operational permission.",
    },
    COLOR_PALETTE: {
        "question": "are these the brand's colours?",
        "allowed_human_actions": (D.APPROVE_PALETTE, D.REJECT, D.DEFER,
                                  D.REQUEST_EVIDENCE, D.SUPERSEDE, D.DEPRECATE,
                                  D.QUARANTINE),
        "required_roles": (authz.BRAND_ADMIN, authz.DESIGN_REVIEWER,
                           authz.LEGAL_REVIEWER),
        "batch_review_allowed": False,
        "dual_control_required": True,          # C3d
        "expiry_applies": True,
        "eventual_permissions": _ASSET_PERMS,
        "note": "DUAL CONTROL. Approving a palette grants NO permission.",
    },
    FONT_FACE: {
        "question": "is this face technically what we think it is?",
        "allowed_human_actions": (D.APPROVE_FONT, D.REJECT, D.DEFER,
                                  D.REQUEST_EVIDENCE, D.QUARANTINE),
        "required_roles": (authz.DESIGN_REVIEWER, authz.LEGAL_REVIEWER),
        "batch_review_allowed": True,
        "dual_control_required": False,         # no TYPOGRAPHY_SYSTEM domain exists
        "expiry_applies": True,
        "eventual_permissions": _ASSET_PERMS,
        "note": "a TECHNICAL question. It says nothing about rights — that is "
                "PROVENANCE_RIGHTS_GROUP.",
    },
    FONT_FAMILY: {
        "question": "do these faces belong together?",
        "allowed_human_actions": (D.APPROVE_FONT, D.REJECT, D.DEFER),
        "required_roles": (authz.DESIGN_REVIEWER, authz.BRAND_ADMIN),
        "batch_review_allowed": True,
        "dual_control_required": False,
        "expiry_applies": False,
        "eventual_permissions": (),
        "note": "a family name is a HYPOTHESIS, not identity proof",
    },
    FONT_SOURCE_PACKAGE: {
        "question": "what were we given, and with what paperwork?",
        "allowed_human_actions": (D.APPROVE_LIMITED_USE, D.REJECT, D.DEFER,
                                  D.REQUEST_EVIDENCE, D.QUARANTINE),
        "required_roles": (authz.LEGAL_REVIEWER, authz.BRAND_ADMIN),
        "batch_review_allowed": True,
        "dual_control_required": False,
        "expiry_applies": True,
        "eventual_permissions": _ASSET_PERMS,
        "note": "one package's licence NEVER clears another",
    },
    LICENSE_EVIDENCE: {
        "question": "what does this document actually say, and what does it cover?",
        "allowed_human_actions": (D.REQUEST_EVIDENCE, D.REJECT, D.DEFER),
        "required_roles": (authz.LEGAL_REVIEWER,),
        "batch_review_allowed": True,
        "dual_control_required": False,
        "expiry_applies": True,
        "eventual_permissions": (),
        "note": "EVIDENCE IS NOT APPROVAL. An OFL grants nothing until a human reads "
                "it and decides.",
    },
    OWNERSHIP_EVIDENCE: {
        "question": "does this document establish who owns it?",
        "allowed_human_actions": (D.REQUEST_EVIDENCE, D.REJECT, D.DEFER),
        "required_roles": (authz.LEGAL_REVIEWER,),
        "batch_review_allowed": True,
        "dual_control_required": False,
        "expiry_applies": True,
        "eventual_permissions": (),
        "note": "a business assertion is a BELIEF; evidence is a FACT ON FILE; neither "
                "is a confirmation",
    },
    QUARANTINE_BATCH: {
        "question": "should this batch stay disabled?",
        "allowed_human_actions": (D.QUARANTINE, D.REJECT, D.DEFER,
                                  D.REQUEST_EVIDENCE, D.APPROVE_LIMITED_USE),
        "required_roles": (authz.LEGAL_REVIEWER, authz.BRAND_ADMIN),
        "batch_review_allowed": True,
        "dual_control_required": False,
        "expiry_applies": False,
        "eventual_permissions": (),
        "note": "quarantine is PROPOSED, never applied by machine. Nothing is deleted.",
    },
    PROVENANCE_RIGHTS_GROUP: {
        "question": "do we know where THIS copy came from?",
        "allowed_human_actions": (D.APPROVE_LIMITED_USE, D.REJECT, D.DEFER,
                                  D.REQUEST_EVIDENCE, D.QUARANTINE),
        "required_roles": (authz.LEGAL_REVIEWER,),
        "batch_review_allowed": False,          # rights never batch across provenance
        "dual_control_required": False,
        "expiry_applies": True,
        "eventual_permissions": _ASSET_PERMS,
        "note": "RIGHTS ATTACH TO PROVENANCE, NOT CONTENT. Identical bytes from two "
                "sources are TWO rights decisions.",
    },
}

assert set(SPEC) == set(DOMAINS)
# Every allowed action in every domain must be a HUMAN decision — never a machine one.
for _d, _s in SPEC.items():
    for _a in _s["allowed_human_actions"]:
        assert _a in D.HUMAN_DECISIONS, (_d, _a)
# Rights across provenance are never batched. This is the C4b correction, at the
# contract layer.
assert not SPEC[PROVENANCE_RIGHTS_GROUP]["batch_review_allowed"]
assert SPEC[CANONICAL_MASTER_CANDIDATE]["dual_control_required"]
assert SPEC[COLOR_PALETTE]["dual_control_required"]


def spec(domain: str) -> dict:
    if domain not in SPEC:
        raise ValueError(f"{domain!r} is not a review domain")
    return SPEC[domain]
