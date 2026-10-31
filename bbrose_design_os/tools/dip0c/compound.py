"""Compound events: resolving a conflict without ever passing through a broken state.

A replacement is *two* facts — the incumbent stops being the master, and the successor
starts. Appending those as two files means that between the two writes the ledger
contains **two active masters for one scope**, which is precisely the state this
milestone exists to make impossible. A crash there leaves it permanently.

So a resolution is **one immutable file** carrying its constituent events embedded.
The constituents are never written as separate ledger files, and the file is installed
with `os.replace()` — an atomic rename on POSIX. Either the whole resolution is
visible or none of it is. There is no torn state to detect, because there is no
interval in which one can exist.

The write order matters and is not decorative:

    build in memory -> project the POST-state -> validate (<=1 active per scope)
    -> write temp on the SAME filesystem -> fsync the file -> os.replace -> fsync dir

If anything fails before `os.replace`, **nothing becomes visible**. The derived index
is regenerated separately, afterwards; it is a convenience and a tripwire, never the
source of truth.

Git gives us versioned history and content hashes, not cryptographic immutability —
see `c3b4_known_limitations.md`. Commit signing and DB transactions are DIP-1.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from tools.dip0.report import json_default

from . import canonical_read as CR
from . import config as C
from . import ledger as L
from . import taxonomy as TX

PARSER = f"{C.TOOL_NAME}.compound/{C.TOOL_VERSION}"
SCHEMA_VERSION = "compound/1.0"
COMPOUND_DIR = L.LEDGER_ROOT / "compound"


class CompoundError(RuntimeError):
    """A compound operation was refused. Nothing was written."""


def state_hash(events: list) -> str:
    """A fingerprint of the projected canonical state — used to prove the ledger did
    not move under us between validation and write."""
    ms = CR.masters(events)
    payload = [{"asset": m["asset"], "lifecycle": m["lifecycle"],
                "event": m["activation_event_id"], "scope": m.get("scope")}
               for m in ms]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=json_default).encode()
    ).hexdigest()


def build(action: str, *, asset: str, actor_id: str, actor_role: str,
          occurred_at: str, reason: str, constituents: list,
          incumbent_event_id: str = None, replacement_event_id: str = None,
          resulting_scopes: dict = None, evidence_refs: list = None,
          attestations: list = None, pre_state_hash: str = None,
          post_state_hash: str = None) -> dict:
    """Assemble the compound record. Pure — writes nothing."""
    rec = {
        "schema_version": SCHEMA_VERSION,
        "compound_event_id": None,
        "resolution_action": action,
        "asset": asset,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "occurred_at": occurred_at,
        "decision_reason": reason,
        "incumbent_event_id": incumbent_event_id,
        "replacement_event_id": replacement_event_id,
        "resulting_scopes": resulting_scopes or {},
        "evidence_refs": sorted(evidence_refs or []),
        "attestations": list(attestations or []),
        "taxonomy_version": TX.version(),
        "expected_pre_state_hash": pre_state_hash,
        "expected_post_state_hash": post_state_hash,
        "constituent_ids": [e["event_id"] for e in constituents],
        "constituent_hashes": {e["event_id"]: e["content_hash"]
                               for e in constituents},
        "constituents": list(constituents),      # EMBEDDED — no separate files
        "created_at": None,
        "compound_content_hash": None,
        "note": "ATOMIC. The constituent events live inside this file and are never "
                "written separately; a resolution is visible in full or not at all.",
        "parser": PARSER,
    }
    rec["compound_event_id"] = L.make_id(
        "cmp", {k: v for k, v in rec.items()
                if k not in ("compound_event_id", "created_at",
                             "compound_content_hash")})
    return rec


def content_hash(rec: dict) -> str:
    body = {k: v for k, v in rec.items()
            if k not in ("compound_content_hash", "created_at")}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, default=json_default).encode()).hexdigest()


def validate(rec: dict, *, existing_events: list) -> list[str]:
    """Everything that must hold BEFORE anything is written."""
    problems: list[str] = []

    if rec["schema_version"] != SCHEMA_VERSION:
        problems.append(f"unknown compound schema {rec['schema_version']!r}")
    if not rec.get("constituents"):
        problems.append("a compound event must embed at least one constituent event")
    if not (rec.get("decision_reason") or "").strip():
        problems.append("a conflict resolution must record an explicit reason")

    ids = [e["event_id"] for e in rec["constituents"]]
    if len(set(ids)) != len(ids):
        problems.append(f"duplicate constituent event ids: {ids}")
    existing_ids = {e["event_id"] for e in existing_events}
    for i in ids:
        if i in existing_ids:
            problems.append(f"constituent {i} already exists in the ledger")

    # embedded constituents must not have been tampered with
    for e in rec["constituents"]:
        want = rec["constituent_hashes"].get(e["event_id"])
        got = L.content_hash(e)
        if want != got:
            problems.append(
                f"constituent {e['event_id']} hash mismatch: the embedded record "
                f"does not match its recorded hash ({want} != {got})")

    if rec["taxonomy_version"] != TX.version():
        problems.append(
            f"taxonomy version mismatch: this resolution was built against "
            f"{rec['taxonomy_version']}, the current taxonomy is {TX.version()}. "
            "Re-validate before writing — a taxonomy change may reinterpret scope.")

    # the incumbent must actually exist and actually be active
    if rec["incumbent_event_id"]:
        inc = [m for m in CR.masters(existing_events)
               if m["activation_event_id"] == rec["incumbent_event_id"]]
        if not inc:
            problems.append(
                f"incumbent {rec['incumbent_event_id']} is not an activation event "
                "in the ledger")
        elif inc[0]["lifecycle"] != CR.ACTIVE:
            problems.append(
                f"incumbent {rec['incumbent_event_id']} is not ACTIVE (it is "
                f"{inc[0]['lifecycle']}) — there is nothing to resolve")

    # dual control survives the conflict path: activating a master ALWAYS needs both
    activating = [e for e in rec["constituents"]
                  if e["event_type"] in L.DUAL_CONTROL_EVENTS]
    if activating:
        atts = rec.get("attestations") or []
        cats = {a.get("category") for a in atts}
        actors = {a.get("actor_id") for a in atts}
        if len(cats) < 2:
            problems.append(
                "this resolution ACTIVATES a canonical master, so it requires BOTH "
                "the technical/brand and the rights/ownership attestation — dual "
                "control is not bypassable through the conflict path")
        if len(actors) < 2:
            problems.append(
                "this resolution ACTIVATES a canonical master: its attestations must "
                f"come from two DIFFERENT people, not {actors}")

    # the pre-state must be what we validated against
    if rec.get("expected_pre_state_hash"):
        actual = state_hash(existing_events)
        if actual != rec["expected_pre_state_hash"]:
            problems.append(
                "pre-state mismatch: the ledger changed between validation and "
                "write. Nothing was appended; rebuild the resolution.")

    # --- THE check: project the post-state and refuse overlapping actives ---
    post = existing_events + rec["constituents"]
    for c in CR.conflicts(post):
        problems.append(
            f"post-state would hold two active canonical masters for an overlapping "
            f"scope: {c['assets']} ({c['relation']}; {c['reason']}). Refused.")

    if rec.get("expected_post_state_hash"):
        if state_hash(post) != rec["expected_post_state_hash"]:
            problems.append("post-state hash mismatch: the resolution does not "
                            "produce the state it claims")
    return problems


def commit(rec: dict, *, existing_events: list, dry_run: bool = False) -> Path:
    """Validate, then install ATOMICALLY. If validation fails, NOTHING is written."""
    problems = validate(rec, existing_events=existing_events)
    if problems:
        raise CompoundError(
            "compound operation REFUSED — nothing was appended:\n  - "
            + "\n  - ".join(problems))
    if dry_run:
        return None

    C.assert_output_safe(COMPOUND_DIR)
    COMPOUND_DIR.mkdir(parents=True, exist_ok=True)
    target = COMPOUND_DIR / f"{rec['compound_event_id']}.json"
    if target.exists():
        raise CompoundError(
            f"{target.name} already exists. The ledger is APPEND-ONLY: a compound "
            "event is never overwritten.")

    rec = dict(rec)
    rec["created_at"] = L.now_iso()
    rec["compound_content_hash"] = content_hash(rec)
    blob = json.dumps(rec, indent=2, sort_keys=False, default=json_default) + "\n"

    # temp file on the SAME filesystem, so os.replace is a true atomic rename
    fd, tmp = tempfile.mkstemp(dir=str(COMPOUND_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(blob)
            fh.flush()
            os.fsync(fh.fileno())            # the bytes are on disk...
        os.replace(tmp, target)              # ...and now they are visible, atomically
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    _fsync_dir(COMPOUND_DIR)                 # ...and the directory entry is durable
    return target


def _fsync_dir(d: Path) -> None:
    """Durability of the rename itself. Best-effort: not every platform allows it."""
    try:
        fd = os.open(str(d), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except (OSError, AttributeError):
        pass


def load_all() -> list[dict]:
    if not COMPOUND_DIR.exists():
        return []
    return [json.loads(p.read_text())
            for p in sorted(COMPOUND_DIR.glob("cmp-*.json"))]


def expand(compounds: list = None) -> list[dict]:
    """The constituent events, unpacked for projection. The compound FILE stays the
    source of truth; this is a view of it."""
    out = []
    for c in (compounds if compounds is not None else load_all()):
        out.extend(c.get("constituents", []))
    return out


def validate_committed() -> dict:
    """Validator for compound files already on disk (used by ledger_store)."""
    problems, seen = [], set()
    for c in load_all():
        cid = c.get("compound_event_id")
        if not cid:
            problems.append("a compound file has no compound_event_id")
            continue
        if cid in seen:
            problems.append(f"duplicate compound id {cid}")
        seen.add(cid)
        if c.get("compound_content_hash") != content_hash(c):
            problems.append(f"{cid}: compound content hash mismatch — the file was "
                            "modified after it was written")
        for e in c.get("constituents", []):
            want = c.get("constituent_hashes", {}).get(e.get("event_id"))
            if want and want != L.content_hash(e):
                problems.append(f"{cid}: constituent {e['event_id']} was modified")

    events = expand()
    for conf in CR.conflicts(events):
        problems.append(
            f"the committed ledger holds two ACTIVE canonical masters for an "
            f"overlapping scope: {conf['assets']} — {conf['reason']}")
    return {"valid": not problems, "problems": problems,
            "compound_events": len(seen), "parser": PARSER}
