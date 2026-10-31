"""Deterministic human-review queues (DIP-0C3b4).

Ten queues, A–J. Determinism is a tested property, not an aspiration: every queue
sorts on stable keys and never on dict or set iteration order, so building the same
ledger twice yields byte-identical output. A queue that reshuffles itself between runs
cannot be reviewed in batches, and cannot be diffed.

**Canonical decisions and conflicts are never batch-approved.** Queues A, B and C
carry `batch_review_allowed = False`. Deciding which file *is* the brand is not a
thing you do fifty at a time.
"""
from __future__ import annotations

from . import canonical_read as CR
from . import config as C
from . import permissions as P

PARSER = f"{C.TOOL_NAME}.review_c3b4/{C.TOOL_VERSION}"

CRITICAL, HIGH, MEDIUM, LOW = "CRITICAL", "HIGH", "MEDIUM", "LOW"

QUEUES = {
    "A": "canonical candidates awaiting dual-control review",
    "B": "active canonical conflicts",
    "C": "replacement requests",
    "D": "scope-overlap uncertainty",
    "E": "deprecated or superseded masters",
    "F": "technically strong but ownership/licence-blocked",
    "G": "contradictory business assertion vs file evidence",
    "H": "missing or expired review evidence",
    "I": "permission grants requiring re-review",
    "J": "third-party brand materials",
}
# Canonical authority is never decided in bulk.
NO_BATCH = ("A", "B", "C")


def _q(key, items, *, priority, reason, roles, action, evidence="") -> dict:
    return {
        "queue": key,
        "title": QUEUES[key],
        "count": len(items),
        "priority": priority,
        "shared_reason": reason,
        "required_reviewer_roles": list(roles),
        "items": items,                       # already deterministically sorted
        "evidence_status": evidence,
        "recommended_next_action": action,
        "batch_review_allowed": key not in NO_BATCH,
    }


def build(events: list, *, now: str, nominations: list = None,
          third_party: list = None, contradictions: list = None,
          technically_strong: list = None) -> dict:
    """Every queue, from the ledger plus the machine's own (non-binding) findings."""
    ms = CR.masters(events)
    conflicts = CR.conflicts(events)
    by_asset = {m["asset"]: m for m in ms}

    # --- A. nominated, but nobody has reviewed it -----------------------------
    a_items = sorted(
        [{"asset": n["asset"], "machine_state": n.get("state"),
          "reason": "machine NOMINATION only — a nomination confers nothing until "
                    "two humans attest to it",
          "blocking": "no canonical approval exists"}
         for n in (nominations or []) if n["asset"] not in by_asset],
        key=lambda r: r["asset"])

    # --- B. two active masters over one scope --------------------------------
    b_items = [{"assets": c["assets"], "events": c["events"],
                "relation": c["relation"], "proven": c["proven"],
                "reason": c["reason"],
                "affected_scope": c["affected_scope"],
                "permitted_resolutions": c["permitted_resolutions"]}
               for c in conflicts if c["proven"]]

    # --- C. replacements in flight -------------------------------------------
    c_items = sorted(
        [{"asset": m["asset"], "event": m["activation_event_id"],
          "supersedes": m["supersedes"],
          "reason": "a replacement activation — dual control applies in full"}
         for m in ms if m["lifecycle"] == CR.ACTIVE and m.get("supersedes")],
        key=lambda r: (r["asset"], r["event"]))

    # --- D. we genuinely cannot tell whether the scopes intersect ------------
    d_items = [{"assets": c["assets"], "events": c["events"],
                "reason": c["reason"],
                "uncertain_axes": c["affected_scope"].get("uncertain_axes", []),
                "resolution": "register the unknown token in scope_taxonomy.json, or "
                              "narrow one scope so the two are provably disjoint"}
               for c in conflicts if not c["proven"]]
    d_items += [{"assets": [t["asset"]], "events": [t["event_id"]],
                 "reason": t["reason"], "uncertain_axes": ["taxonomy_version"],
                 "resolution": "confirm the current taxonomy does not change what "
                               "this decision meant when it was made"}
                for t in CR.taxonomy_drift(events)]

    # --- E. retired masters ---------------------------------------------------
    e_items = sorted(
        [{"asset": m["asset"], "lifecycle": m["lifecycle"],
          "superseded_by": (m.get("superseded_by") or {}).get("asset"),
          "reason": "DEPRECATED remains historically authoritative for its former "
                    "period but must not be chosen for new work; SUPERSEDED names "
                    "its successor explicitly"}
         for m in ms if m["lifecycle"] in (CR.DEPRECATED, CR.SUPERSEDED,
                                           CR.REJECTED, CR.QUARANTINED)],
        key=lambda r: (r["lifecycle"], r["asset"]))

    # --- F/G/J. machine findings, carried through unchanged -------------------
    f_items = sorted(technically_strong or [], key=lambda r: r.get("asset", ""))
    g_items = sorted(contradictions or [], key=lambda r: r.get("asset", ""))
    j_items = sorted(third_party or [], key=lambda r: r.get("asset", ""))

    # --- H/I. evidence and permission expiry ---------------------------------
    assets = sorted({e["asset"] for e in events})
    h_items, i_items = [], []
    for asset in assets:
        expired = P.detect_expired(asset, events, now=now)
        for x in expired:
            i_items.append({
                "asset": asset, "flag": x["flag"],
                "grant_event": x["grant_event_id"],
                "review_expiry": x["review_expiry"],
                "effective_value": x["effective_value"],
                "reason": "the review date passed: the permission is ALREADY denied. "
                          "Only a new authorised human grant restores it."})
        m = by_asset.get(asset)
        if m and m["lifecycle"] == CR.ACTIVE and expired:
            h_items.append({
                "asset": asset, "event": m["activation_event_id"],
                "reason": "an ACTIVE canonical master whose rights evidence has "
                          "expired — canonical authority outliving its evidence"})
    i_items.sort(key=lambda r: (r["asset"], r["flag"]))
    h_items.sort(key=lambda r: (r["asset"], r["event"]))

    out = {
        "A": _q("A", a_items, priority=HIGH,
                reason="nominated by machine; awaiting two human attestations",
                roles=["BRAND_ADMIN", "DESIGN_REVIEWER", "LEGAL_REVIEWER"],
                action="run the 15-item checklist under dual control",
                evidence="not yet reviewed"),
        "B": _q("B", b_items, priority=CRITICAL,
                reason="two ACTIVE canonical masters cover one scope. Both are "
                       "unusable as canonical for the affected scope until a human "
                       "resolves it — no winner is chosen by machine.",
                roles=["BRAND_ADMIN", "LEGAL_REVIEWER"],
                action="choose ONE of the seven resolution actions",
                evidence="varies"),
        "C": _q("C", c_items, priority=HIGH,
                reason="a replacement activation — full dual control applies",
                roles=["BRAND_ADMIN", "LEGAL_REVIEWER"],
                action="confirm both attestations and the resulting scopes",
                evidence="attestations required"),
        "D": _q("D", d_items, priority=MEDIUM,
                reason="the taxonomy cannot say whether these scopes intersect. This "
                       "FAILS CLOSED: uncertainty is treated as a conflict.",
                roles=["BRAND_ADMIN", "BUSINESS_OWNER"],
                action="register the token, or narrow a scope to make them disjoint",
                evidence="taxonomy incomplete"),
        "E": _q("E", e_items, priority=LOW,
                reason="retired masters — kept for the historical record",
                roles=["BRAND_ADMIN"],
                action="confirm the retirement is correctly recorded",
                evidence="historical"),
        "F": _q("F", f_items, priority=HIGH,
                reason="technically strong, but rights are unconfirmed. Technical "
                       "readiness and rights are separate axes and never collapse.",
                roles=["LEGAL_REVIEWER"],
                action="confirm ownership and licence, or quarantine",
                evidence="ownership/licence unverified"),
        "G": _q("G", g_items, priority=HIGH,
                reason="the business asserts one thing and the file says another",
                roles=["LEGAL_REVIEWER", "BRAND_ADMIN"],
                action="acknowledge the contradiction WITH a reason, or reject",
                evidence="contradictory"),
        "H": _q("H", h_items, priority=CRITICAL,
                reason="an ACTIVE canonical master whose evidence has expired",
                roles=["LEGAL_REVIEWER"],
                action="re-review the evidence or revoke the canonical status",
                evidence="expired"),
        "I": _q("I", i_items, priority=CRITICAL,
                reason="a permission passed its review date. It is ALREADY denied — "
                       "this queue restores service, it does not stop a leak.",
                roles=["LEGAL_REVIEWER", "BRAND_ADMIN"],
                action="re-review and issue a NEW grant, or leave it denied",
                evidence="expired"),
        "J": _q("J", j_items, priority=HIGH,
                reason="third-party brand material sitting inside BBROSE folders. "
                       "Folder location has never implied ownership.",
                roles=["LEGAL_REVIEWER"],
                action="confirm third-party status; keep every permission false",
                evidence="third-party"),
    }
    return {
        "evaluated_at": now,
        "queues": out,
        "totals": {k: v["count"] for k, v in out.items()},
        "total_items": sum(v["count"] for v in out.values()),
        "critical": sorted(k for k, v in out.items()
                           if v["priority"] == CRITICAL and v["count"]),
        "never_batch_approved": list(NO_BATCH),
        "parser": PARSER,
    }
