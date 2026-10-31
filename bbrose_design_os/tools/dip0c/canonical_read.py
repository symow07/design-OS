"""The scope-indexed canonical read model (DIP-0C3b4). PURE — it writes nothing.

The C3b2 read model answers "what is the state of THIS asset?". That question cannot
detect two active masters, because two-active-masters is a property of a **set** of
assets sharing a scope, not of any one of them. So this module projects across all
canonical events at once and indexes by scope.

**Conflicts fail closed, and they fail LOCALLY.** Two masters colliding over France
do not invalidate a master approved only for the United States. A conflict blocks the
assets involved for the *affected* scope — the conflicting scope, the uncertain query
scope, and any child scope proven to be affected — and leaves provably disjoint
scopes alone. Being maximally destructive is not the same as being safe; it just
teaches people to ignore the system.

**Nothing here picks a winner.** Not the newest timestamp, not the filename, not the
technical readiness. Two actives over one scope is `CANONICAL_CONFLICT` and it stays
that way until a human resolves it.
"""
from __future__ import annotations

from . import canonical_scope as S
from . import config as C
from . import ledger as L
from . import ledger_store as LS
from . import permissions as P
from . import taxonomy as TX

# the palette state that ACTIVATES authority in the BRAND_PALETTE domain
PAL_APPROVED = "APPROVED_BRAND_PALETTE"

PARSER = f"{C.TOOL_NAME}.canonical_read/{C.TOOL_VERSION}"

# --- lifecycle states the read model exposes (C3b4 §6) ------------------------
ACTIVE = "ACTIVE"
DEPRECATED = "DEPRECATED"          # historically authoritative; not for new work
SUPERSEDED = "SUPERSEDED"          # replaced by a NAMED successor
REJECTED = "REJECTED"              # never was a master
QUARANTINED = "QUARANTINED"        # unusable until concerns are resolved
LIFECYCLE = (ACTIVE, DEPRECATED, SUPERSEDED, REJECTED, QUARANTINED)

CANONICAL_CONFLICT = "CANONICAL_CONFLICT"
TAXONOMY_REVIEW_REQUIRED = "TAXONOMY_REVIEW_REQUIRED"


def _canonical_events(events: list) -> list:
    """Live canonical events in CAUSAL order.

    Sorting by timestamp alone is unsound: a resolution is written as one atomic
    compound, so the deprecation of the incumbent and the activation of its successor
    carry the SAME `occurred_at`. Break that tie on `event_id` and the deprecation can
    sort ahead of the activation it supersedes — the incumbent would never leave
    ACTIVE, and two masters would appear to hold one scope.

    So: an event that supersedes another is always ordered after it. Within that
    constraint, order is (occurred_at, event_id) — fully deterministic, which the
    queue tests depend on.
    """
    # SCOPE_REDUCED changes what a master IS canonical for, so the projection must
    # see it. It is not in L.CANONICAL_EVENTS (it is a corrective event), and leaving
    # it out silently ignored every narrowing.
    kinds = (set(L.CANONICAL_EVENTS)
             | {L.ASSET_QUARANTINED, L.SCOPE_REDUCED,
                L.PALETTE_QUARANTINED, L.PALETTE_APPROVAL_REVOKED})
    ev = [e for e in events if e.get("event_type") in kinds]
    pending = sorted(ev, key=lambda e: (e["occurred_at"], e["event_id"]))
    known = {e["event_id"] for e in pending}
    emitted: set[str] = set()
    out: list[dict] = []

    while pending:
        ready = [e for e in pending
                 if not e.get("supersedes_event_id")
                 or e["supersedes_event_id"] not in known
                 or e["supersedes_event_id"] in emitted]
        if not ready:
            out.extend(pending)          # a cycle: emit deterministically, don't hang
            break
        nxt = ready[0]                   # `pending` is already sorted, so this is the
        pending.remove(nxt)              # earliest ready event — deterministic
        emitted.add(nxt["event_id"])
        out.append(nxt)
    return out


def masters(events: list) -> list[dict]:
    """Every asset that has ever been activated as a canonical master, with its
    current lifecycle state. Derived; never written back."""
    out: dict[str, dict] = {}
    ev = _canonical_events(events)

    for e in ev:
        et, asset = e["event_type"], e["asset"]
        can = e.get("canonical") or {}
        state = can.get("canonical_state")

        activating = (
            (et in (L.CANONICAL_MASTER_APPROVED, L.CANONICAL_MASTER_REPLACED)
             and state == C.CANONICAL_BRAND_MASTER)
            or (et in (L.BRAND_PALETTE_APPROVED, L.PALETTE_SUPERSEDED)
                and state == PAL_APPROVED))
        if activating:
            out[asset] = {
                "asset": asset,
                "authority_domain": can.get("authority_domain",
                                            L.DOMAIN_BRAND_MASTER),
                "palette": can.get("palette"),
                "lifecycle": ACTIVE,
                "activation_event_id": e["event_id"],
                "activated_at": e["occurred_at"],
                "scope": can.get("scope"),
                "taxonomy_version": (can.get("scope") or {}).get("taxonomy_version"),
                "attestations": can.get("attestations") or [],
                "supersedes": e.get("supersedes_event_id"),
                "superseded_by": None,
                "history": [e["event_id"]],
            }
            # a replacement names its incumbent, and that link is explicit
            if et in (L.CANONICAL_MASTER_REPLACED, L.PALETTE_SUPERSEDED) \
                    and e.get("supersedes_event_id"):
                for other in out.values():
                    if other["activation_event_id"] == e["supersedes_event_id"]:
                        other["lifecycle"] = SUPERSEDED
                        other["superseded_by"] = {"asset": asset,
                                                  "event_id": e["event_id"]}
            continue

        if asset not in out:
            continue
        rec = out[asset]
        rec["history"].append(e["event_id"])
        if et in (L.CANONICAL_MASTER_DEPRECATED, L.PALETTE_DEPRECATED):
            # A supersession retires the incumbent AND names its successor, in one
            # atomic compound — so both constituents supersede the same activation
            # and their relative order is arbitrary. SUPERSEDED is the more specific
            # fact (it carries the link), and a plain deprecation must not clobber it.
            if state == C.REJECTED_CANDIDATE:
                rec["lifecycle"] = REJECTED
            elif rec.get("superseded_by"):
                rec["lifecycle"] = SUPERSEDED
            else:
                rec["lifecycle"] = DEPRECATED
            rec["deprecated_at"] = e["occurred_at"]
            rec["deprecation_reason"] = e.get("decision_reason")
        elif et in (L.ASSET_QUARANTINED, L.PALETTE_QUARANTINED):
            rec["lifecycle"] = QUARANTINED
            rec["quarantine_reason"] = e.get("decision_reason")
        elif et == L.SCOPE_REDUCED and can.get("scope"):
            rec["scope"] = can["scope"]          # a narrowing only ever reduces
            rec["scope_reduced_at"] = e["occurred_at"]
        elif et in (L.VARIANT_RECLASSIFIED, L.PALETTE_VARIANT_APPROVED):
            # reclassified out of the authoritative role: it is no longer THE master
            # (or THE palette). It remains a recorded, approved variant.
            rec["lifecycle"] = DEPRECATED
            rec["reclassified_as"] = state
        elif et == L.PALETTE_APPROVAL_REVOKED:
            # a rejected candidate never was the brand's palette
            rec["lifecycle"] = (REJECTED if state == "REJECTED_PALETTE"
                                else DEPRECATED)
            rec["revoked_at"] = e["occurred_at"]
            rec["revocation_reason"] = e.get("decision_reason")

    return sorted(out.values(), key=lambda r: (r["asset"], r["activation_event_id"]))


def conflicts(events: list) -> list[dict]:
    """Every pair of ACTIVE masters whose scopes collide. Fails closed: an UNCERTAIN
    overlap is a conflict, because 'we cannot tell' is not 'they do not collide'."""
    active = [m for m in masters(events) if m["lifecycle"] == ACTIVE]
    out = []
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            if not a["scope"] or not b["scope"]:
                continue
            # DIFFERENT AUTHORITY DOMAINS DO NOT CONFLICT. A brand palette and a logo
            # master may both be authoritative for the same brand, product, market and
            # period without contradicting each other: one says which COLOURS are the
            # brand's, the other says which FILE is. Uniqueness is a property WITHIN a
            # domain. Collapsing them into one bucket would manufacture a conflict out
            # of two decisions that answer different questions.
            if a["authority_domain"] != b["authority_domain"]:
                continue
            rel = S.relate(a["scope"], b["scope"])
            if rel["relation"] == S.DISJOINT:
                continue                              # provably cannot collide
            out.append({
                "state": CANONICAL_CONFLICT,
                "authority_domain": a["authority_domain"],
                "assets": sorted([a["asset"], b["asset"]]),
                "events": sorted([a["activation_event_id"],
                                  b["activation_event_id"]]),
                "relation": rel["relation"],
                "proven": rel["proven"],
                "uncertain": not rel["proven"],
                "reason": rel["reason"],
                "per_axis": rel["per_axis"],
                "affected_scope": _affected_scope(a["scope"], b["scope"], rel),
                "resolution_is_human_only": True,
                "permitted_resolutions": list(RESOLUTION_HINTS),
            })
    return sorted(out, key=lambda c: (c["assets"], c["events"]))


RESOLUTION_HINTS = (
    "DEPRECATE_INCUMBENT", "SUPERSEDE_INCUMBENT", "NARROW_INCUMBENT_SCOPE",
    "NARROW_NEW_SCOPE", "RECLASSIFY_AS_VARIANT", "REJECT_NEW_CANDIDATE",
    "QUARANTINE_BOTH_PENDING_REVIEW",
)


def _affected_scope(a: dict, b: dict, rel: dict) -> dict:
    """WHICH scope the conflict blocks. Not 'everything' — the intersection, plus any
    axis we are merely uncertain about."""
    affected, uncertain_axes = {}, []
    for axis in ("lockup", "products", "markets", "variant_role"):
        r = rel["per_axis"][axis]
        if r == S.UNKNOWN:
            uncertain_axes.append(axis)
            affected[axis] = {"mode": "UNCERTAIN",
                              "left": a[axis], "right": b[axis]}
        elif a[axis]["mode"] == S.MODE_ALL:
            affected[axis] = b[axis]
        elif b[axis]["mode"] == S.MODE_ALL:
            affected[axis] = a[axis]
        else:
            affected[axis] = {"mode": S.MODE_LIST,
                              "tokens": sorted(set(a[axis]["tokens"])
                                               | set(b[axis]["tokens"]))}
    return {"brand": a["brand"], **affected,
            "uncertain_axes": uncertain_axes,
            "note": "the conflict blocks THIS scope. A master approved for a provably "
                    "disjoint scope is unaffected."}


def canonical_for(events: list, query_scope: dict,
                  authority_domain: str = L.DOMAIN_BRAND_MASTER) -> dict:
    """THE query: which asset is authoritative for this scope, IN THIS DOMAIN?

    Fails closed and fails LOCALLY. If a conflict touches the queried scope, the
    answer is CANONICAL_CONFLICT and no asset is returned — but a conflict elsewhere,
    or in another authority domain, does not contaminate this answer.
    """
    active = [m for m in masters(events) if m["lifecycle"] == ACTIVE
              and m["authority_domain"] == authority_domain]
    matches, uncertain = [], []
    for m in active:
        if not m["scope"]:
            continue
        rel = S.relate(m["scope"], query_scope)
        if rel["relation"] == S.DISJOINT:
            continue
        (matches if rel["proven"] else uncertain).append({"master": m, "rel": rel})

    # does any KNOWN conflict touch the scope being asked about?
    touching = []
    for c in conflicts(events):
        if c["authority_domain"] != authority_domain:
            continue
        for asset in c["assets"]:
            m = next((x for x in active if x["asset"] == asset), None)
            if m and m["scope"] and S.relate(m["scope"],
                                             query_scope)["relation"] != S.DISJOINT:
                touching.append(c)
                break

    if touching or len(matches) + len(uncertain) > 1:
        return {
            "state": CANONICAL_CONFLICT,
            "asset": None,
            "usable": False,
            "query_scope": query_scope,
            "conflicting_assets": sorted({a for c in touching for a in c["assets"]}
                                         or {m["master"]["asset"]
                                             for m in matches + uncertain}),
            "conflicts": touching,
            "uncertain": bool(uncertain) or any(c["uncertain"] for c in touching),
            "reason": "more than one active canonical master could apply to this "
                      "scope, or an unresolved conflict touches it. No winner is "
                      "chosen — not by timestamp, not by filename, not by quality.",
            "parser": PARSER,
        }

    if not matches and not uncertain:
        return {"state": "NO_CANONICAL_MASTER", "asset": None, "usable": False,
                "query_scope": query_scope,
                "reason": "no active canonical master covers this scope",
                "parser": PARSER}

    m = matches[0]
    return {
        "state": ACTIVE,
        "authority_domain": authority_domain,
        "asset": m["master"]["asset"],
        "usable": True,
        "activation_event_id": m["master"]["activation_event_id"],
        "scope": m["master"]["scope"],
        "relation_to_query": m["rel"]["relation"],
        "taxonomy_version": m["master"]["taxonomy_version"],
        "query_scope": query_scope,
        "grants_permissions": False,
        "note": "being the canonical master says WHICH file is authoritative. It "
                "grants NO operational permission — those are separate and default "
                "to false.",
        "parser": PARSER,
    }


def taxonomy_drift(events: list) -> list[dict]:
    """Would today's taxonomy read an old approval differently? Never silently
    reinterpret a decision a human made under different definitions."""
    current = TX.version()
    out = []
    for m in masters(events):
        pinned = m.get("taxonomy_version")
        if pinned and pinned != current:
            out.append({
                "asset": m["asset"],
                "event_id": m["activation_event_id"],
                "state": TAXONOMY_REVIEW_REQUIRED,
                "pinned_taxonomy_version": pinned,
                "current_taxonomy_version": current,
                "reason": "this decision was made under an earlier taxonomy. Its "
                          "original interpretation is preserved; a human must "
                          "confirm the current taxonomy does not change what it "
                          "means before operational behaviour relies on it.",
            })
    return sorted(out, key=lambda r: (r["asset"], r["event_id"]))


def project(events: list, *, now: str, query_scopes: list = None) -> dict:
    """The whole derived view. PURE: reads events, writes nothing."""
    ms = masters(events)
    cs = conflicts(events)
    assets = sorted({e["asset"] for e in events})
    perms = {a: P.effective_permissions(a, events, now=now) for a in assets}

    # A master caught in a conflict is NOT reported as active. `canonical_for()`
    # already refuses to name a winner, but a caller reading `project()["active"]`
    # would otherwise see two overlapping actives listed side by side — which is
    # precisely the thing this milestone promises the read model cannot expose.
    # They move to `conflicted`: still ACTIVE in the ledger, unusable as canonical.
    in_conflict = {a for c in cs for a in c["assets"]}
    return {
        "evaluated_at": now,
        "taxonomy_version": TX.version(),
        "authority_domains": {
            d: {"active": [m["asset"] for m in ms
                           if m["lifecycle"] == ACTIVE
                           and m["authority_domain"] == d
                           and m["asset"] not in in_conflict],
                "conflicted": [m["asset"] for m in ms
                               if m["lifecycle"] == ACTIVE
                               and m["authority_domain"] == d
                               and m["asset"] in in_conflict]}
            for d in L.AUTHORITY_DOMAINS},
        "active": [m for m in ms
                   if m["lifecycle"] == ACTIVE and m["asset"] not in in_conflict],
        "conflicted": [m for m in ms
                       if m["lifecycle"] == ACTIVE and m["asset"] in in_conflict],
        "deprecated": [m for m in ms if m["lifecycle"] == DEPRECATED],
        "superseded": [m for m in ms if m["lifecycle"] == SUPERSEDED],
        "rejected": [m for m in ms if m["lifecycle"] == REJECTED],
        "quarantined": [m for m in ms if m["lifecycle"] == QUARANTINED],
        "supersession_chains": _chains(ms),
        "conflicts": cs,
        "conflict_free": not cs,
        "taxonomy_review_required": taxonomy_drift(events),
        "expired_permissions": {a: P.detect_expired(a, events, now=now)
                                for a in assets
                                if P.detect_expired(a, events, now=now)},
        "effective_permissions": perms,
        "queries": [{"scope": q, "result": canonical_for(events, q)}
                    for q in (query_scopes or [])],
        "note": "DERIVED. The ledger is the source of truth; nothing here is written "
                "back. Conflicts fail closed and fail LOCALLY.",
        "parser": PARSER,
    }


def _chains(ms: list) -> list[dict]:
    """old -> new supersession chains, explicitly linked."""
    chains = []
    for m in ms:
        if m.get("superseded_by"):
            chains.append({"from_asset": m["asset"],
                           "from_event": m["activation_event_id"],
                           "to_asset": m["superseded_by"]["asset"],
                           "to_event": m["superseded_by"]["event_id"],
                           "lifecycle": m["lifecycle"]})
    return sorted(chains, key=lambda c: (c["from_asset"], c["to_asset"]))


def project_from_ledger(*, now: str, query_scopes: list = None) -> dict:
    """Convenience: project the committed ledger. Still pure."""
    return project(LS.load("events"), now=now, query_scopes=query_scopes)
