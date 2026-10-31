"""Permission grants, scopes, expiry and the effective read model (DIP-0C3b3).

Two things are kept strictly apart:

    A. the historical GRANT EVENT  — immutable, forever
    B. the current EFFECTIVE VALUE — evaluated, never stored

An expired permission is **not** edited. The grant stays exactly as it was written;
the *evaluation* returns `False` with status `RE_REVIEW_REQUIRED`. Nothing that was
once true is rewritten to make the present tidy.

**Expiry fails closed.** The moment the review date passes, effective use stops —
whether or not anyone has generated the audit event. The audit event is for the
record; the *denial* does not wait for it.

**Reading never writes.** `effective_permissions()` is pure: it touches no file. The
expiry audit events are produced by a separate, explicit call, so a mere read can
never mutate the ledger behind your back.

**No permission is ever derived.** Not from ownership, not from a licence, not from
canonical status. Every `false -> true` requires an explicit, authorised, human
grant event naming that one permission.
"""
from __future__ import annotations

from datetime import datetime

from . import authz, config as C
from . import rights_model as RM

PARSER = f"{C.TOOL_NAME}.permissions/{C.TOOL_VERSION}"

FLAGS = RM.PERMISSION_FLAGS          # the 9 boolean permissions
LISTS = RM.PERMISSION_LISTS          # approved_products / approved_markets


class PermissionError_(RuntimeError):
    """Raised on an invalid permission operation."""


def _dt(v):
    if not v:
        return None
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


# --- action-specific prerequisites -------------------------------------------
# Permissions are NOT interchangeable. Redistributing an asset publicly is a
# different question from retrieving it internally, and they must not share a bar.
PREREQUISITES = {
    "retrieval_allowed": {
        "requires_ownership": (C.OWN_BBROSE_CONFIRMED, C.OWN_LICENSED_LIMITED,
                               C.OWN_JOINT_OR_CONTRACTED,
                               C.OWN_THIRD_PARTY_CONFIRMED),
        "requires_license": None,          # internal retrieval: licence not required
        "requires_purpose": True,
        "legal_only": False,
    },
    "automatic_use_allowed": {
        "requires_ownership": (C.OWN_BBROSE_CONFIRMED, C.OWN_LICENSED_LIMITED,
                               C.OWN_JOINT_OR_CONTRACTED),
        "requires_license": (C.LIC_APPROVED, C.LIC_INTERNAL_ONLY),
        "requires_purpose": True,
        "legal_only": False,
    },
    "production_use_allowed": {
        "requires_ownership": (C.OWN_BBROSE_CONFIRMED, C.OWN_LICENSED_LIMITED,
                               C.OWN_JOINT_OR_CONTRACTED),
        "requires_license": (C.LIC_APPROVED,),
        "requires_purpose": True,
        "legal_only": False,
    },
    "modification_allowed": {
        "requires_ownership": (C.OWN_BBROSE_CONFIRMED, C.OWN_LICENSED_LIMITED),
        "requires_license": (C.LIC_APPROVED, C.LIC_INTERNAL_ONLY),
        "requires_purpose": False,
        "legal_only": False,
    },
    "embedding_allowed": {
        "requires_ownership": (C.OWN_BBROSE_CONFIRMED, C.OWN_LICENSED_LIMITED),
        "requires_license": (C.LIC_APPROVED,),
        "requires_purpose": False,
        "legal_only": False,
    },
    # --- anything that exposes the asset OUTSIDE the company is legal's alone ---
    "redistribution_allowed": {
        "requires_ownership": (C.OWN_BBROSE_CONFIRMED,),
        "requires_license": (C.LIC_APPROVED,),
        "requires_purpose": True,
        "legal_only": True,
    },
    "public_export_allowed": {
        "requires_ownership": (C.OWN_BBROSE_CONFIRMED,),
        "requires_license": (C.LIC_APPROVED,),
        "requires_purpose": True,
        "legal_only": True,
    },
    "approved_for_bbrose": {
        "requires_ownership": (C.OWN_BBROSE_CONFIRMED, C.OWN_LICENSED_LIMITED,
                               C.OWN_JOINT_OR_CONTRACTED),
        "requires_license": None,
        "requires_purpose": False,
        "legal_only": False,
    },
    "approved_for_other_brands": {
        "requires_ownership": (C.OWN_BBROSE_CONFIRMED,),
        "requires_license": (C.LIC_APPROVED,),
        "requires_purpose": True,
        "legal_only": True,
    },
}


def check_grant(flag: str, *, actor_role: str, actor_id: str,
                ownership_state: str, license_state: str,
                evidence_records: list, reason: str, purpose: str = None,
                contradiction: dict = None,
                ownership_decision_ref: str = None,
                license_decision_ref: str = None) -> tuple[bool, list]:
    """Can this ONE permission be granted? No bundles, no inference."""
    problems: list[str] = []
    if flag not in FLAGS:
        return False, [f"{flag!r} is not a grantable permission flag"]
    p = PREREQUISITES[flag]

    # 1. AUTHORISED for THIS permission — legal permissions are legal's alone
    action = authz.permission_action(flag)
    try:
        authz.authorize(actor_role, action, actor_id=actor_id)
    except authz.NotAuthorized as e:
        problems.append(f"unauthorized: {e}")

    # 2. rights sufficient FOR THIS ACTION (not a generic "has rights" check)
    if ownership_state not in p["requires_ownership"]:
        problems.append(
            f"{flag}: ownership is {ownership_state!r}; this permission requires "
            f"one of {list(p['requires_ownership'])}")
    if p["requires_license"] and license_state not in p["requires_license"]:
        problems.append(
            f"{flag}: licence is {license_state!r}; this permission requires one "
            f"of {list(p['requires_license'])}")

    # 3. a purpose, where the permission is purpose-bound
    if p["requires_purpose"] and not (purpose or "").strip():
        problems.append(f"{flag}: an approved purpose must be recorded")

    # 4. reviewed + accepted evidence
    accepted = [e for e in (evidence_records or [])
                if e.get("review_status") == "REVIEWED_ACCEPTED"
                and e.get("reviewed_by")]
    if not accepted:
        problems.append(f"{flag}: no REVIEWED_ACCEPTED evidence supports this grant")

    # 5. the decisions this grant leans on must be referenced
    if not ownership_decision_ref:
        problems.append(f"{flag}: must reference the ownership decision it relies on")
    if p["requires_license"] and not license_decision_ref:
        problems.append(f"{flag}: must reference the licence decision it relies on")

    # 6. an explicit reason
    if not (reason or "").strip():
        problems.append(f"{flag}: a grant must record an explicit reason")

    # 7. contradictions acknowledged
    c = contradiction or {"contradiction_present": False,
                          "contradiction_acknowledged": False}
    if c["contradiction_present"] and not c["contradiction_acknowledged"]:
        problems.append(f"{flag}: an unacknowledged contradiction blocks this grant")

    return (not problems), problems


# --- the EFFECTIVE read model (PURE — it writes nothing) ----------------------
def effective_permissions(asset: str, events: list, *, now: str,
                          brand: str = None, product: str = None,
                          market: str = None, media: str = None) -> dict:
    """Evaluate the CURRENT effective permissions from the immutable grant history.

    Pure: reads events, writes nothing. `now` is injected so expiry is deterministic
    and testable.

    A permission is effective only if: a grant exists, it is not revoked, its
    validity has started, its review expiry has NOT passed, its scope matches, and
    no later quarantine supersedes it.
    """
    t = _dt(now)
    out = {f: {"value": False, "status": C.EFF_DENIED_NO_GRANT,
               "grant_event_id": None, "review_expiry": None,
               "reason": "no grant has ever been made"} for f in FLAGS}
    lists = {k: [] for k in LISTS}
    attribution_required = None

    mine = sorted([e for e in events if e.get("asset") == asset],
                  key=lambda e: (e["occurred_at"], e["event_id"]))

    quarantined = any(e["event_type"] == "ASSET_QUARANTINED" for e in mine)
    revoked_grants = {e["supersedes_event_id"] for e in mine
                      if e["event_type"] in ("PERMISSION_REVOKED",
                                             "PERMISSION_EXPIRED")
                      and e.get("supersedes_event_id")}

    for e in mine:
        if e["event_type"] != "PERMISSION_GRANTED":
            continue
        pm = e.get("permission") or {}
        flag = pm.get("flag")
        if flag not in FLAGS:
            continue

        rec = out[flag]
        rec["grant_event_id"] = e["event_id"]
        rec["review_expiry"] = pm.get("review_expiry")

        if quarantined:
            rec.update(value=False, status=C.EFF_DENIED_QUARANTINED,
                       reason="the asset is quarantined")
            continue
        if e["event_id"] in revoked_grants:
            rec.update(value=False, status=C.EFF_DENIED_REVOKED,
                       reason="this grant was revoked or expired by a later event")
            continue

        start = _dt(pm.get("validity_start"))
        if start and t < start:
            rec.update(value=False, status=C.EFF_DENIED_NOT_STARTED,
                       reason=f"validity begins {pm['validity_start']}")
            continue

        exp = _dt(pm.get("review_expiry"))
        if exp and t >= exp:
            # FAIL CLOSED. The grant is untouched; the EVALUATION denies. This does
            # not wait for an audit event to be generated.
            rec.update(value=False, status=C.EFF_RE_REVIEW_REQUIRED,
                       reason=f"review expiry {pm['review_expiry']} has passed; "
                              "effective use stops immediately and only a new "
                              "authorized human grant may restore it")
            continue

        if not _scope_matches(pm, brand, product, market, media):
            rec.update(value=False, status=C.EFF_DENIED_SCOPE,
                       reason=f"grant scope does not cover brand={brand!r} "
                              f"product={product!r} market={market!r} "
                              f"media={media!r}")
            continue

        rec.update(value=True, status=C.EFF_GRANTED,
                   reason="explicitly granted by an authorized human, in scope, "
                          "not expired, not revoked")
        for k in LISTS:
            lists[k] = sorted(set(lists[k]) | set(pm.get(k) or []))
        if pm.get("attribution_required") is not None:
            attribution_required = pm["attribution_required"]

    return {
        "asset": asset,
        "evaluated_at": now,
        "permissions": out,
        "approved_products": lists["approved_products"],
        "approved_markets": lists["approved_markets"],
        # an attribution requirement PERSISTS — a machine may never drop it
        "attribution_required": attribution_required,
        "quarantined": quarantined,
        "any_expired": any(r["status"] == C.EFF_RE_REVIEW_REQUIRED
                           for r in out.values()),
        "note": "DERIVED. The grant events are immutable and untouched; this is an "
                "evaluation. Reading never writes.",
        "parser": PARSER,
    }


def _scope_matches(pm: dict, brand, product, market, media=None) -> bool:
    """Scopes are INDEPENDENT: an empty list means 'unrestricted on that axis', and
    narrowing markets never narrows products.

    MEDIA (C3d) is checked through the TAXONOMY, not by string equality: a grant for
    `DIGITAL` covers `SCREEN` because the taxonomy says DIGITAL contains SCREEN — and
    it does NOT cover `PACKAGING_PRINT`, because PRINT and DIGITAL are declared
    disjoint. An unregistered media token FAILS CLOSED: we will not guess where an
    asset may be used.
    """
    if brand and pm.get("approved_brands") and brand not in pm["approved_brands"]:
        return False
    if product and pm.get("approved_products") \
            and product not in pm["approved_products"]:
        return False
    if market and pm.get("approved_markets") \
            and market not in pm["approved_markets"]:
        return False
    if media and pm.get("approved_media"):
        from . import taxonomy as TX
        covered = TX.covered_by_any("media", media, pm["approved_media"])
        if covered is not True:          # False -> not covered; None -> cannot tell
            return False
    return True


# --- expiry: detection is pure; the audit event is EXPLICIT -------------------
def detect_expired(asset: str, events: list, *, now: str) -> list[dict]:
    """PURE. Which grants have passed their review date? Writes nothing."""
    eff = effective_permissions(asset, events, now=now)
    return [{"flag": f, "grant_event_id": r["grant_event_id"],
             "review_expiry": r["review_expiry"],
             "effective_value": r["value"], "status": r["status"]}
            for f, r in eff["permissions"].items()
            if r["status"] == C.EFF_RE_REVIEW_REQUIRED]


def machine_may_revoke_only(previous: bool, requested: bool) -> bool:
    """Machine code may only ever turn a permission OFF."""
    if not previous and requested:
        raise RM.MachineMayNotIncrease(
            "machine may NOT turn a permission from false to true — granting is a "
            "human decision")
    return requested
