"""A150/2x — the two-identity citing path for verdict estimates.

A single hash answers ONE bit — did anything move — and the remedies
for the components differ completely, so a verdict estimate carries
two identities evaluated separately:

  VALUE identity      moves iff the measured quantity moves
  PROVENANCE identity moves iff the measuring instrument moves

The citing path reports WHICH moved and never a single verdict. The
state that was invisible before this existed is the third one: a
quantity remeasured under a changed instrument that reproduces the
same number is not freshness — it is two different measurements
agreeing, which is a finding requiring adjudication.

Recipes are co-located per 2w in the functions below; every payload
field is recoverable from committed records or from git.
"""
import hashlib
import json

FRESH = "FRESH"
STALE_VALUE_MOVED = "STALE[value_moved]"
AGREEMENT_ACROSS_INSTRUMENT_CHANGE = "AGREEMENT_ACROSS_INSTRUMENT_CHANGE"
STALE_BOTH_MOVED = "STALE[value_moved+provenance_moved]"


class VerdictIdentityError(RuntimeError):
    """The record does not carry both identities. Raised, never
    warned: a one-identity record cannot answer a two-bit question."""


def mint(payload):
    """RECIPE: sha256(json.dumps(payload, sort_keys=True))[:16]."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def provenance_payload(measuring_code_commit, rig_source_sha,
                       protocol_identity_at_measurement):
    """RECIPE for the provenance identity: mint() over exactly these
    three fields. Every one is checkable — the commit from git, the
    rig source hash by sha256 of that commit's committed rig module,
    the protocol identity from the measuring record (or the explicit
    string NOT_STATED_IN_RECORD where the record omitted it, which is
    itself the honest value and moves if it is ever supplied)."""
    return {"measuring_code_commit": measuring_code_commit,
            "rig_source_sha": rig_source_sha,
            "protocol_identity_at_measurement":
                protocol_identity_at_measurement}


def evaluate(record, value_now, provenance_now):
    """Report WHICH identities moved. Never a single verdict."""
    if "value_identity" not in record:
        raise VerdictIdentityError(
            "record carries no value identity — refusing to read")
    if "provenance_identity" not in record:
        raise VerdictIdentityError(
            "record carries no provenance identity — a one-identity "
            "record cannot distinguish a remeasurement from an "
            "instrument change (2x); refusing to read")
    value_moved = record["value_identity"] != value_now
    prov_moved = record["provenance_identity"] != provenance_now
    if value_moved and prov_moved:
        state = STALE_BOTH_MOVED
    elif value_moved:
        state = STALE_VALUE_MOVED
    elif prov_moved:
        state = AGREEMENT_ACROSS_INSTRUMENT_CHANGE
    else:
        state = FRESH
    return {
        "state": state,
        "value_moved": value_moved,
        "provenance_moved": prov_moved,
        "citable_as_fresh": state == FRESH,
        "requires_adjudication":
            state == AGREEMENT_ACROSS_INSTRUMENT_CHANGE,
        "note": ("a quantity reproduced under a changed instrument is "
                 "two measurements agreeing, not one measurement "
                 "standing; agreement is a finding, not identity"
                 if state == AGREEMENT_ACROSS_INSTRUMENT_CHANGE
                 else ""),
    }
