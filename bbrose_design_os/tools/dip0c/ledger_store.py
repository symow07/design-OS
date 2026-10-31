"""Ledger storage, append-only enforcement, and the derived read model (C3b2).

The event files are the SOURCE OF TRUTH. `index.json` is generated — and doubles as
a **deletion tripwire**: it remembers which files existed and what they hashed to,
so a file removed or edited outside the tool is detected rather than silently
forgotten.

`append()` may add new records and regenerate the index. It **never** rewrites the
content of a prior record.
"""
from __future__ import annotations

import json
from pathlib import Path

from tools.dip0.provenance import now_iso

from . import authz, config as C, ledger as L
from . import rights_model as RM

PARSER = f"{C.TOOL_NAME}.ledger_store/{C.TOOL_VERSION}"

KINDS = {
    "events": (L.EVENTS_DIR, "event_id"),
    "evidence": (L.EVIDENCE_DIR, "evidence_id"),
    "assertions": (L.ASSERTIONS_DIR, "assertion_id"),
}


def ensure_dirs() -> None:
    for d, _ in KINDS.values():
        C.assert_output_safe(d)
        C.assert_not_frozen_milestone(d)
        d.mkdir(parents=True, exist_ok=True)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load(kind: str) -> list[dict]:
    d, _ = KINDS[kind]
    if not d.exists():
        return []
    return [_read(p) for p in sorted(d.glob("*.json"))]


def append(kind: str, record: dict) -> Path:
    """Write a NEW immutable record. Refuses to touch an existing file."""
    d, idkey = KINDS[kind]
    ensure_dirs()
    rid = record[idkey]
    path = d / f"{rid}.json"
    if path.exists():
        existing = _read(path)
        if L.content_hash(existing) == L.content_hash(record):
            return path                     # identical: idempotent, not a rewrite
        raise L.LedgerError(
            f"{rid} already exists with different content. A ledger record is "
            "IMMUTABLE — record a superseding event instead of editing it.")
    C.assert_output_safe(path)
    C.assert_not_frozen_milestone(path)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


def build_index() -> dict:
    """GENERATED from the immutable files. Never the source of truth."""
    idx = {
        "schema_version": L.SCHEMA_VERSION,
        "generated_at": now_iso(),
        "note": "GENERATED from the immutable record files. The FILES are the "
                "source of truth; this index is a convenience and a deletion "
                "tripwire. Do not treat it as authoritative.",
        "counts": {},
        "records": {},
    }
    for kind, (_, idkey) in KINDS.items():
        recs = load(kind)
        idx["counts"][kind] = len(recs)
        idx["records"][kind] = sorted(
            ({"id": r[idkey], "asset": r.get("asset"),
              "content_hash": r["content_hash"],
              "type": r.get("event_type") or r.get("evidence_type")
              or r.get("asserted_state")}
             for r in recs),
            key=lambda x: x["id"])
    return idx


def write_index() -> Path:
    ensure_dirs()
    idx = build_index()
    C.assert_output_safe(L.INDEX_PATH)
    C.assert_not_frozen_milestone(L.INDEX_PATH)
    L.INDEX_PATH.write_text(json.dumps(idx, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    return L.INDEX_PATH


# --- the validator -----------------------------------------------------------
def validate() -> dict:
    """Detect every way the ledger could have been tampered with or broken."""
    findings: dict[str, list] = {
        "modified_records": [],       # content no longer matches its own hash
        "deleted_records": [],        # the index remembers it; the file is gone
        "duplicate_ids": [],
        "broken_supersedes": [],
        "missing_evidence_refs": [],
        "missing_assertion_refs": [],
        "invalid_actor_roles": [],
        "unauthorized_actions": [],
        "illegal_state_transitions": [],
        "invalid_timestamps": [],
        "hash_mismatches": [],
        "index_divergence": [],
        "unknown_event_types": [],
        # C3b4 — the state the whole milestone exists to make impossible. Checking it
        # only at write time would leave a hand-edited or badly-merged ledger holding
        # two active masters with nothing to notice.
        "overlapping_active_masters": [],
        "invalid_compound_events": [],
    }

    events = load("events")
    evidence = load("evidence")
    assertions = load("assertions")
    ev_ids = {e["evidence_id"] for e in evidence}
    asr_ids = {a["assertion_id"] for a in assertions}
    evt_ids = [e["event_id"] for e in events]

    # (a) content hashes — an edit to any record's substance is detectable
    for kind, (_, idkey) in KINDS.items():
        for r in load(kind):
            if L.content_hash(r) != r.get("content_hash"):
                findings["hash_mismatches"].append(
                    {"kind": kind, "id": r[idkey],
                     "reason": "content no longer matches its content_hash — the "
                               "record was edited in place"})
                findings["modified_records"].append(r[idkey])

    # (b) duplicate ids
    for kind, (_, idkey) in KINDS.items():
        seen = {}
        for r in load(kind):
            seen.setdefault(r[idkey], 0)
            seen[r[idkey]] += 1
        findings["duplicate_ids"] += [
            {"kind": kind, "id": k} for k, n in seen.items() if n > 1]

    # (c) the index as a DELETION tripwire
    if L.INDEX_PATH.exists():
        old = json.loads(L.INDEX_PATH.read_text(encoding="utf-8"))
        for kind in KINDS:
            known = {r["id"]: r["content_hash"]
                     for r in old.get("records", {}).get(kind, [])}
            _, idkey = KINDS[kind]
            present = {r[idkey]: r["content_hash"] for r in load(kind)}
            for rid, h in known.items():
                if rid not in present:
                    findings["deleted_records"].append({"kind": kind, "id": rid})
                elif present[rid] != h:
                    findings["index_divergence"].append(
                        {"kind": kind, "id": rid,
                         "reason": "content hash changed since the index was "
                                   "written — the record was modified"})

    # (d) references, roles, authorisation, transitions, timestamps
    for e in events:
        if e["event_type"] not in L.EVENT_TYPES:
            findings["unknown_event_types"].append(e["event_id"])
            continue
        if e["actor_role"] not in authz.ROLES:
            findings["invalid_actor_roles"].append(
                {"event_id": e["event_id"], "role": e["actor_role"]})
        else:
            try:
                authz.authorize(e["actor_role"], L.EVENT_ACTION[e["event_type"]],
                                actor_id=e["actor_id"])
            except authz.NotAuthorized as err:
                findings["unauthorized_actions"].append(
                    {"event_id": e["event_id"], "reason": str(err)})

        if e["supersedes_event_id"] and e["supersedes_event_id"] not in evt_ids:
            findings["broken_supersedes"].append(
                {"event_id": e["event_id"],
                 "missing": e["supersedes_event_id"]})
        for ref in e["evidence_refs"]:
            if ref not in ev_ids:
                findings["missing_evidence_refs"].append(
                    {"event_id": e["event_id"], "missing": ref})
        for ref in e["assertion_refs"]:
            if ref not in asr_ids:
                findings["missing_assertion_refs"].append(
                    {"event_id": e["event_id"], "missing": ref})

        for field in ("occurred_at", "recorded_at"):
            v = e.get(field)
            if v and not _is_iso(v):
                findings["invalid_timestamps"].append(
                    {"event_id": e["event_id"], "field": field, "value": v})

        if e["event_type"] in L.DECISION_EVENTS and e["previous_state"] \
                and e["requested_state"]:
            axis = (RM.AXIS_LICENSE
                    if e["requested_state"] in C.LICENSE_STATES
                    else RM.AXIS_OWNERSHIP)
            try:
                RM.validate_transition(axis, e["previous_state"],
                                       e["requested_state"], RM.ACTOR_HUMAN)
            except (RM.IllegalTransition, RM.MachineMayNotIncrease,
                    C.HumanOnlyStateViolation) as err:
                findings["illegal_state_transitions"].append(
                    {"event_id": e["event_id"], "reason": str(err)})

    # --- C3b4: the committed ledger must never hold two active overlapping masters
    # Imported here: canonical_read imports permissions, which imports this module.
    from . import canonical_read as CR
    from . import compound as CP

    all_events = events + CP.expand()
    for c in CR.conflicts(all_events):
        findings["overlapping_active_masters"].append(
            {"assets": c["assets"], "events": c["events"],
             "relation": c["relation"], "reason": c["reason"]})
    cp_report = CP.validate_committed()
    findings["invalid_compound_events"] = list(cp_report["problems"])

    clean = all(not v for v in findings.values())
    return {"valid": clean, "findings": findings,
            "counts": {"events": len(events), "evidence": len(evidence),
                       "assertions": len(assertions),
                       "compound_events": cp_report["compound_events"]}}


def _is_iso(v: str) -> bool:
    from datetime import datetime
    try:
        datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


# --- the READ MODEL (derived — it is NOT the ledger) -------------------------
def read_model(asset: str, machine_record: dict) -> dict:
    """Compute the effective state for one asset.

    Derived from: immutable machine inference + business assertions + ACCEPTED
    evidence + append-only human decisions + later revocations. The result is a
    projection; the ledger remains the source of truth, and nothing here is
    written back.
    """
    events = [e for e in load("events") if e["asset"] == asset]
    events.sort(key=lambda e: (e["occurred_at"], e["event_id"]))
    evidence = [e for e in load("evidence") if e["asset"] == asset]
    assertions = [a for a in load("assertions") if a["asset"] == asset]

    superseded = {e["supersedes_event_id"] for e in events
                  if e["supersedes_event_id"]}
    live = [e for e in events if e["event_id"] not in superseded]

    state = {RM.AXIS_OWNERSHIP: machine_record["machine_inference"]
             [RM.AXIS_OWNERSHIP]["machine_state"],
             RM.AXIS_LICENSE: machine_record["machine_inference"]
             [RM.AXIS_LICENSE]["machine_state"]}
    confirmed_by = {RM.AXIS_OWNERSHIP: None, RM.AXIS_LICENSE: None}

    for e in live:
        if e["event_type"] in L.DECISION_EVENTS and e["requested_state"]:
            axis = (RM.AXIS_LICENSE if e["requested_state"] in C.LICENSE_STATES
                    else RM.AXIS_OWNERSHIP)
            state[axis] = e["requested_state"]
            confirmed_by[axis] = {"actor_id": e["actor_id"],
                                  "role": e["actor_role"],
                                  "at": e["occurred_at"],
                                  "event_id": e["event_id"],
                                  "review_expiry": e["review_expiry"]}
        elif e["event_type"] == L.OWNERSHIP_REVOKED:
            state[RM.AXIS_OWNERSHIP] = C.OWN_QUARANTINED
            confirmed_by[RM.AXIS_OWNERSHIP] = None
        elif e["event_type"] == L.LICENSE_REVOKED:
            state[RM.AXIS_LICENSE] = C.LIC_EXPIRED_OR_REVIEW
            confirmed_by[RM.AXIS_LICENSE] = None

    # an assertion is shown, never applied
    live_assertions = [a for a in assertions if not a["withdrawn_at"]]
    withdrawn = [a for a in assertions if a["withdrawn_at"]]

    return {
        "asset": asset,
        "effective_ownership": state[RM.AXIS_OWNERSHIP],
        "effective_license": state[RM.AXIS_LICENSE],
        "confirmed_by": confirmed_by,
        "business_assertions": [
            {"assertion_id": a["assertion_id"],
             "asserted_state": a["asserted_state"],
             "asserted_by": a["asserted_by"],
             "is_confirmation": False, "grants_permissions": False}
            for a in live_assertions],
        "withdrawn_assertions": [a["assertion_id"] for a in withdrawn],
        "accepted_evidence": [e["evidence_id"] for e in evidence
                              if e["review_status"] == L.EV_ACCEPTED],
        "rejected_evidence": [e["evidence_id"] for e in evidence
                              if e["review_status"] == L.EV_REJECTED],
        "pending_evidence": [e["evidence_id"] for e in evidence
                             if e["review_status"] == L.EV_SUBMITTED],
        "event_count": len(events),
        "superseded_event_count": len(superseded),
        # C3b2 grants nothing: permissions arrive in C3b3
        "permissions": RM.permissions(),
        "note": "a DERIVED read model. The immutable event files are the source of "
                "truth. Permissions remain false — granting is DIP-0C3b3.",
    }
