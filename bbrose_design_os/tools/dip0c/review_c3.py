"""The C3 review queues (DIP-0C3d).

**A queue is identified by its `queue_id`, never by its letter.** The letter is a
display label: it is what a human sees at the top of a column, and it may be renumbered
tomorrow without a single line of code changing. C3b4 already shipped queues lettered
A–J with *different meanings*, and if letters were identity that collision would quietly
corrupt every downstream reader. Code, tests, reports and future database rows key on
`queue_id`.

Determinism is a tested property: every queue sorts on stable keys, never on dict or set
iteration order, so the same ledger builds the same queues byte-for-byte.

**No canonical or palette approval is ever batch-approved.** Deciding which file *is* the
brand — or which colours *are* the brand — is not a thing you do fifty at a time.
"""
from __future__ import annotations

from . import canonical_read as CR
from . import config as C
from . import ledger as L
from . import permissions as P
from . import rights_model as RM

PARSER = f"{C.TOOL_NAME}.review_c3/{C.TOOL_VERSION}"
QUEUE_SCHEMA_VERSION = "review_queue/1.0"

CRITICAL, HIGH, MEDIUM, LOW = "CRITICAL", "HIGH", "MEDIUM", "LOW"

# --- the registry. queue_id is IDENTITY; display_label is presentation. ---------
QUEUES = (
    ("POSSIBLE_BRAND_MASTER", "A", "Possible BBROSE logo masters", HIGH, True),
    ("COMPOSITION_MISLABELLED_AS_MASTER", "B",
     "Brand compositions incorrectly labelled as masters", MEDIUM, True),
    ("OUTLINED_WORDMARK_IDENTIFICATION", "C",
     "Outlined wordmarks needing human identification", MEDIUM, True),
    ("THIRD_PARTY_LOGO_IN_BBROSE_FOLDER", "D",
     "Third-party logos inside BBROSE folders", HIGH, True),
    ("TECHNICALLY_STRONG_OWNERSHIP_BLOCKED", "E",
     "Technically strong but ownership-blocked assets", HIGH, True),
    ("MISSING_BRAND_LICENSE_EVIDENCE", "F",
     "Missing brand-asset licence evidence", HIGH, True),
    ("CANONICAL_MASTER_NOMINATION", "G", "Canonical-master nominations", HIGH, False),
    ("CANONICAL_CONFLICT", "H", "Canonical conflicts and replacements", CRITICAL,
     False),
    ("PALETTE_ASSOCIATION_REVIEW", "I", "Palette association review", MEDIUM, True),
    ("PALETTE_OWNERSHIP_LICENSE_REVIEW", "J", "Palette ownership / licence review",
     HIGH, True),
    ("PALETTE_APPROVAL_DUAL_CONTROL", "K",
     "Palette approval and dual-control review", HIGH, False),
    ("EXPIRED_OR_REVOKED_APPROVAL", "L",
     "Expired or revoked brand/palette approvals", CRITICAL, True),
    ("ASSERTION_CONTRADICTS_EVIDENCE", "M",
     "Contradictory business assertion and file evidence", HIGH, True),
    ("RIGHTS_BLOCKED_PERMISSION", "N",
     "Rights-blocked operational permissions", HIGH, True),
)
QUEUE_IDS = tuple(q[0] for q in QUEUES)
LABELS = {q[0]: q[1] for q in QUEUES}
TITLES = {q[0]: q[2] for q in QUEUES}
PRIORITIES = {q[0]: q[3] for q in QUEUES}
BATCHABLE = {q[0]: q[4] for q in QUEUES}

# Queue IDs are globally unique — enforced at import, not by convention.
assert len(set(QUEUE_IDS)) == len(QUEUE_IDS), "duplicate queue_id"
assert len({q[1] for q in QUEUES}) == len(QUEUES), "duplicate display_label"
# Authority is never granted in bulk.
assert not BATCHABLE["CANONICAL_CONFLICT"]
assert not BATCHABLE["PALETTE_APPROVAL_DUAL_CONTROL"]
assert not BATCHABLE["CANONICAL_MASTER_NOMINATION"]

ROLES = {
    "POSSIBLE_BRAND_MASTER": ["BRAND_ADMIN", "DESIGN_REVIEWER"],
    "COMPOSITION_MISLABELLED_AS_MASTER": ["BRAND_ADMIN", "DESIGN_REVIEWER"],
    "OUTLINED_WORDMARK_IDENTIFICATION": ["BRAND_ADMIN", "DESIGN_REVIEWER"],
    "THIRD_PARTY_LOGO_IN_BBROSE_FOLDER": ["LEGAL_REVIEWER"],
    "TECHNICALLY_STRONG_OWNERSHIP_BLOCKED": ["LEGAL_REVIEWER"],
    "MISSING_BRAND_LICENSE_EVIDENCE": ["LEGAL_REVIEWER"],
    "CANONICAL_MASTER_NOMINATION": ["BRAND_ADMIN", "DESIGN_REVIEWER",
                                    "LEGAL_REVIEWER"],
    "CANONICAL_CONFLICT": ["BRAND_ADMIN", "LEGAL_REVIEWER"],
    "PALETTE_ASSOCIATION_REVIEW": ["BRAND_ADMIN", "BUSINESS_OWNER"],
    "PALETTE_OWNERSHIP_LICENSE_REVIEW": ["LEGAL_REVIEWER"],
    "PALETTE_APPROVAL_DUAL_CONTROL": ["BRAND_ADMIN", "DESIGN_REVIEWER",
                                      "LEGAL_REVIEWER"],
    "EXPIRED_OR_REVOKED_APPROVAL": ["LEGAL_REVIEWER", "BRAND_ADMIN"],
    "ASSERTION_CONTRADICTS_EVIDENCE": ["LEGAL_REVIEWER", "BRAND_ADMIN"],
    "RIGHTS_BLOCKED_PERMISSION": ["LEGAL_REVIEWER"],
}


def _q(queue_id: str, items: list, *, reason: str, action: str,
       evidence: str = "") -> dict:
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "queue_id": queue_id,                 # IDENTITY
        "display_label": LABELS[queue_id],    # presentation only
        "title": TITLES[queue_id],
        "count": len(items),
        "priority": PRIORITIES[queue_id],
        "shared_reason": reason,
        "required_reviewer_roles": list(ROLES[queue_id]),
        "items": items,
        "evidence_status": evidence,
        "recommended_next_action": action,
        "batch_review_allowed": BATCHABLE[queue_id],
    }


def build(events: list, *, now: str, brand_findings: dict = None) -> dict:
    """Every C3 queue, from the ledger plus the machine's non-binding findings."""
    f = brand_findings or {}
    ms = CR.masters(events)
    confl = CR.conflicts(events)
    by_asset = {m["asset"]: m for m in ms}

    def _sorted(rows, *keys):
        return sorted(rows, key=lambda r: tuple(str(r.get(k, "")) for k in keys))

    # --- brand/logo findings, carried through unchanged ------------------------
    q: dict[str, dict] = {}
    q["POSSIBLE_BRAND_MASTER"] = _q(
        "POSSIBLE_BRAND_MASTER",
        _sorted(f.get("possible_masters", []), "asset"),
        reason="machine NOMINATION only — a nomination confers nothing",
        action="run the 15-item canonical checklist under dual control",
        evidence="not reviewed")
    q["COMPOSITION_MISLABELLED_AS_MASTER"] = _q(
        "COMPOSITION_MISLABELLED_AS_MASTER",
        _sorted(f.get("mislabelled_compositions", []), "asset"),
        reason="a composition is not a master merely because it contains the logo",
        action="reclassify as DESIGN_COMPOSITION / REFERENCE_ONLY",
        evidence="machine inference")
    q["OUTLINED_WORDMARK_IDENTIFICATION"] = _q(
        "OUTLINED_WORDMARK_IDENTIFICATION",
        _sorted(f.get("outlined_wordmarks", []), "asset"),
        reason="the text is outlined: no machine can read what it says",
        action="a human must identify the wordmark",
        evidence="REQUIRES_HUMAN")
    q["THIRD_PARTY_LOGO_IN_BBROSE_FOLDER"] = _q(
        "THIRD_PARTY_LOGO_IN_BBROSE_FOLDER",
        _sorted(f.get("third_party_logos", []), "asset"),
        reason="folder location has never implied ownership",
        action="confirm third-party status; keep every permission false",
        evidence="third-party")
    q["TECHNICALLY_STRONG_OWNERSHIP_BLOCKED"] = _q(
        "TECHNICALLY_STRONG_OWNERSHIP_BLOCKED",
        _sorted(f.get("technically_strong", []), "asset"),
        reason="technical readiness and rights are separate axes and never collapse",
        action="confirm ownership and licence, or quarantine",
        evidence="ownership unverified")
    q["MISSING_BRAND_LICENSE_EVIDENCE"] = _q(
        "MISSING_BRAND_LICENSE_EVIDENCE",
        _sorted(f.get("missing_license_evidence", []), "asset"),
        reason="no licence evidence is on file for this brand asset",
        action="obtain and review licence evidence",
        evidence="missing")

    # --- canonical (BRAND_MASTER domain) --------------------------------------
    nominated = [n for n in f.get("canonical_nominations", [])
                 if n.get("asset") not in by_asset]
    q["CANONICAL_MASTER_NOMINATION"] = _q(
        "CANONICAL_MASTER_NOMINATION", _sorted(nominated, "asset"),
        reason="nominated by machine; awaiting TWO human attestations",
        action="dual-control canonical approval",
        evidence="not reviewed")

    master_conf = [c for c in confl
                   if c["authority_domain"] == L.DOMAIN_BRAND_MASTER]
    palette_conf = [c for c in confl
                    if c["authority_domain"] == L.DOMAIN_BRAND_PALETTE]
    q["CANONICAL_CONFLICT"] = _q(
        "CANONICAL_CONFLICT",
        sorted(master_conf + palette_conf,
               key=lambda c: (c["authority_domain"], c["assets"])),
        reason="two ACTIVE authorities cover one scope IN THE SAME DOMAIN. A brand "
               "palette and a logo master never conflict with each other — they answer "
               "different questions.",
        action="choose ONE of the seven resolution actions",
        evidence="varies")

    # --- palettes (BRAND_PALETTE domain) --------------------------------------
    q["PALETTE_ASSOCIATION_REVIEW"] = _q(
        "PALETTE_ASSOCIATION_REVIEW",
        _sorted(f.get("palettes_unassociated", []), "asset"),
        reason="is this palette BBROSE's at all? The filename does not say so.",
        action="confirm or deny brand association",
        evidence="REQUIRES_HUMAN")
    q["PALETTE_OWNERSHIP_LICENSE_REVIEW"] = _q(
        "PALETTE_OWNERSHIP_LICENSE_REVIEW",
        _sorted(f.get("palettes_rights_unresolved", []), "asset"),
        reason="ownership unconfirmed and licence unverified; third-party naming may "
               "be present",
        action="confirm ownership and record a licence decision",
        evidence="unverified")
    q["PALETTE_APPROVAL_DUAL_CONTROL"] = _q(
        "PALETTE_APPROVAL_DUAL_CONTROL",
        _sorted(f.get("palettes_awaiting_approval", []), "asset"),
        reason="a brand palette needs TWO attestations from TWO people, and grants no "
               "permission even then",
        action="colour/brand attestation + rights/use attestation, then activation",
        evidence="attestations required")

    # --- rights, expiry, contradictions ---------------------------------------
    assets = sorted({e["asset"] for e in events})
    expired: list[dict] = []
    for asset in assets:
        for x in P.detect_expired(asset, events, now=now):
            expired.append({
                "asset": asset, "flag": x["flag"],
                "grant_event": x["grant_event_id"],
                "review_expiry": x["review_expiry"],
                "reason": "the review date passed: the permission is ALREADY denied"})
    revoked = [{"asset": e["asset"], "event": e["event_id"],
                "event_type": e["event_type"],
                "reason": e.get("decision_reason")}
               for e in events
               if e.get("event_type") in (L.PALETTE_APPROVAL_REVOKED,
                                          L.PALETTE_RE_REVIEW_REQUIRED,
                                          L.RE_REVIEW_REQUIRED)]
    q["EXPIRED_OR_REVOKED_APPROVAL"] = _q(
        "EXPIRED_OR_REVOKED_APPROVAL",
        _sorted(expired + revoked, "asset", "flag", "event"),
        reason="an approval or permission has expired or been revoked. Expiry fails "
               "closed: it is ALREADY denied — this queue restores service, it does "
               "not stop a leak.",
        action="re-review and issue a NEW grant, or leave it denied",
        evidence="expired")
    q["ASSERTION_CONTRADICTS_EVIDENCE"] = _q(
        "ASSERTION_CONTRADICTS_EVIDENCE",
        _sorted(f.get("contradictions", []), "asset"),
        reason="the business asserts one thing and the file says another",
        action="acknowledge the contradiction WITH a reason, or reject",
        evidence="contradictory")

    # every permission flag, DERIVED from the canonical PermissionSet — never a
    # hardcoded count, so adding a flag cannot silently leave this report stale
    blocked = [{"asset": a, "blocked_flags": sorted(P.FLAGS),
                "reason": "no authorised human has granted any permission"}
               for a in assets
               if not any(r["value"] for r in
                          P.effective_permissions(a, events,
                                                  now=now)["permissions"].values())]
    q["RIGHTS_BLOCKED_PERMISSION"] = _q(
        "RIGHTS_BLOCKED_PERMISSION", _sorted(blocked, "asset"),
        reason="every operational permission is false until granted by name",
        action="grant individually, or leave denied",
        evidence="unverified")

    ordered = {qid: q[qid] for qid in QUEUE_IDS}       # deterministic order
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "evaluated_at": now,
        "permission_flags": sorted(RM.PERMISSION_FLAGS),   # derived, not hardcoded
        "permission_flag_count": len(RM.PERMISSION_FLAGS),
        "queues": ordered,
        "totals": {qid: ordered[qid]["count"] for qid in QUEUE_IDS},
        "total_items": sum(v["count"] for v in ordered.values()),
        "critical": [qid for qid in QUEUE_IDS
                     if ordered[qid]["priority"] == CRITICAL
                     and ordered[qid]["count"]],
        "never_batch_approved": [qid for qid in QUEUE_IDS if not BATCHABLE[qid]],
        "note": "queue_id is IDENTITY; display_label is presentation and may change "
                "without changing what a queue means.",
        "parser": PARSER,
    }
