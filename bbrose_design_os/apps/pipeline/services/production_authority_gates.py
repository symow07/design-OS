"""The production-authority gate record says what is — §BH46(b) and (d).

Gates B to E are intake. Each gate's `requires` list stands — the nineteen items
are still what production needs — but the SOURCE of every item is the
owner-supplied spec pack, never a supplier the system wrote to. The system
reads a spec, validates it and refuses it; it never goes and gets one.

This module writes ``production_authority_gate.json`` on every run from what is:

* Gate A — carried verbatim from ``production_authority_gate_a.json``, the
  owner-ruled Illustrator pass of 2026-07-31 and its history;
* Gates B to E — computed from the intake state (``spec_pack_intake``): an item
  is SATISFIED only by intaken, provenanced evidence, and a gate passes when
  every one of its items is satisfied. Nothing here flips a gate by any other
  means;
* the outreach block — a summary derived from the dispatch record, which
  §BH46(a) superseded and kept as history;
* the deferral — read from the deferral record.

``gates_passed`` is computed from satisfied items; ``next_required_owner_action``
is "place the spec pack" with the missing items listed. ``supplier_requests_sent``
is a field that describes a path the system no longer has: it is 0 forever.
"""
import json
import os
from datetime import datetime, timezone

from django.conf import settings

from . import spec_pack_intake as SPI

DOCS_REL = "docs/production_authority"
PA = os.path.join(settings.BASE_DIR, "docs", "production_authority")
GATE_A = os.path.join(PA, "production_authority_gate_a.json")
DISPATCH = os.path.join(PA, "supplier_evidence_request_dispatch.json")
DEFERRAL = os.path.join(PA, "supplier_outreach_deferral.json")
OUT = os.path.join(PA, "production_authority_gate.json")

GATE_ORDER = ("B_supplier_geometry", "C_flat_artwork",
              "D_colour_separation", "E_material_specification")

#: The codes as they were written on 2026-07-31. They name that day's cause;
#: the cause now is the `cause` field beside them. Kept, not renamed (§AZ0(u)).
BLOCKED_CODES = {
    "B_supplier_geometry": "BLOCKED_PENDING_SUPPLIER_GEOMETRY",
    "C_flat_artwork": "BLOCKED_PENDING_PRINT_ZONE_AND_WRAP_EVIDENCE",
    "D_colour_separation": "BLOCKED_PENDING_DECORATION_PROCESS_AND_COLOUR_EVIDENCE",
    "E_material_specification": "BLOCKED_PENDING_SUPPLIER_MATERIAL_EVIDENCE",
}

SOURCE = "OWNER_SUPPLIED_SPEC_PACK"
CAUSE_NOT_HANDED_OVER = "spec pack not yet handed over"
PACKAGING_MAY_BEGIN_WHEN = ("the required geometry and artwork gates pass "
                            "(Gate B and Gate C at minimum)")
EVIDENCE_AUTHORITY_ORDER = [
    "owner-supplied supplier technical drawing",
    "owner-supplied supplier signed or written compatibility confirmation",
    "physical sample measurement",
    "owner-supplied supplier material specification",
    "owner-supplied supplier print-zone specification",
    "accepted concept geometry and artwork",
]
ON_CONFLICT = [
    "preserve the concept",
    "record the difference",
    "create a production adaptation proposal",
    "stop for owner approval",
    "never silently modify accepted artwork",
]


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _gate_from_items(gate, items, deferred):
    """One gate of B to E, computed from its items and nothing else."""
    rows = [i for i in items if i["gate"] == gate]
    satisfied = [i for i in rows if i["state"] == SPI.SATISFIED]
    missing = [i["item"] for i in rows if i["state"] == SPI.MISSING]
    refused = [i["item"] for i in rows if i["state"] == SPI.REFUSED]
    # a gate passes when no item is missing and none is refused — every item
    # satisfied by intaken evidence, and by nothing else
    passed = bool(rows) and not missing and not refused
    if passed:
        cause = "every item intaken"
        blocked_by = None
    elif not satisfied and not refused:
        cause = CAUSE_NOT_HANDED_OVER
        blocked_by = ("no owner-supplied evidence intaken for this item: "
                      + ", ".join(missing))
    else:
        cause = (f"spec pack incomplete: {len(satisfied)} of {len(rows)} items "
                 "intaken")
        blocked_by = ("no owner-supplied evidence intaken for this item: "
                      + ", ".join(missing + refused))
    dates = sorted({d["handed_over_on"] for i in satisfied
                    for d in i["satisfied_by"] if d["handed_over_on"]})
    return {
        "requires": [i["item"] for i in rows],
        "source": SOURCE,
        "evidence_present": bool(satisfied),
        "state": "PASSED" if passed else "BLOCKED",
        "blocked_by": blocked_by,
        "blocked_code": None if passed else BLOCKED_CODES[gate],
        "blocked_code_note": ("the code names the cause as it was written on "
                              "2026-07-31; the cause now is `cause` (§BH46(e))"),
        "cause": cause,
        "items_total": len(rows),
        "items_satisfied": len(satisfied),
        "items_refused": len(refused),
        "items_missing": len(missing),
        "items": [{"item": i["item"], "state": i["state"],
                   "satisfied_by": i["satisfied_by"]} for i in rows],
        "items_satisfied_on": dates[-1] if dates else None,
        "deferred_non_blocking_for_platform_development": deferred,
    }


def build(intake=None, write=True):
    """Derive the gate record from Gate A's own record, the intake state, the
    superseded dispatch record and the deferral record, as they are on this
    run. `intake` may be given (a spec_pack_intake state) so a caller can ask
    what the record would say; by default the location as it stands is read."""
    gate_a = _load(GATE_A)
    intake = intake if intake is not None else SPI.validate(write=False)[0]
    dispatch = _load(DISPATCH) if os.path.isfile(DISPATCH) else None
    deferral = _load(DEFERRAL) if os.path.isfile(DEFERRAL) else None
    deferred = bool(deferral) and deferral["PRODUCTION_AUTHORITY_GATES_B_TO_E"] \
        == "DEFERRED_NON_BLOCKING_FOR_PLATFORM_DEVELOPMENT"
    generated_on = datetime.now(timezone.utc).date().isoformat()

    gates = {"A_illustrator_execution": gate_a["gate"]}
    for g in GATE_ORDER:
        gates[g] = _gate_from_items(g, intake["items"], deferred)
    passed = [k for k, v in gates.items() if v["state"] == "PASSED"]
    missing = [f"{i['gate']}: {i['item']}" for i in intake["items"]
               if i["state"] != SPI.SATISFIED]
    if missing:
        action = (f"place the spec pack: {len(missing)} of {len(intake['items'])} "
                  "items missing — " + "; ".join(missing))
    else:
        action = "none for the gates: every item is intaken with provenance"
    outreach = None
    if dispatch:
        outreach = {
            "superseded_by": dispatch["superseded_by"] if "superseded_by" in dispatch
            else None,
            "status": "SUPERSEDED-BY §BH46 — the system never contacts suppliers; "
                      "kept as history, unsent",
            "requests_total": dispatch["requests_total"],
            "requests_sent": 0,
            "dispatch_complete": False,
            "log": f"{DOCS_REL}/supplier_evidence_request_dispatch.json",
        }
    rec = {
        "record_type": "production_authority_gate/2.0",
        "generated_on": generated_on,
        "first_created": gate_a["created_at"],
        "derived_from": [
            f"{DOCS_REL}/production_authority_gate_a.json",
            f"{SPI.DOCS_REL}/spec_pack_manifest.json and spec_pack/",
            f"{DOCS_REL}/supplier_evidence_request_dispatch.json",
            f"{DOCS_REL}/supplier_outreach_deferral.json",
        ],
        "derivation": "Gate A is carried verbatim from its own record; gates B to "
                      "E are computed from the intake state on this run — an item "
                      "is SATISFIED only by intaken, provenanced evidence and a "
                      "gate passes only when every one of its items is; nothing "
                      "here flips a gate by any other means",
        "gates": gates,
        "all_gates_blocked": not passed,
        "gates_passed": len(passed),
        "packaging_may_begin_when": PACKAGING_MAY_BEGIN_WHEN,
        "packaging_may_begin_now": (gates["B_supplier_geometry"]["state"] == "PASSED"
                                    and gates["C_flat_artwork"]["state"] == "PASSED"),
        "evidence_authority_order": EVIDENCE_AUTHORITY_ORDER,
        "concept_never_overrides_qualified_production_evidence": True,
        "on_conflict": ON_CONFLICT,
        "gate_a_correction": gate_a["gate_a_correction"],
        "supplier_requests_sent": 0,
        "supplier_requests_sent_note": "a field that describes a path the system no "
                                       "longer has (§BH46): it stays 0 forever, and "
                                       "its tests are the proof that no outreach "
                                       "path exists",
        "gates_remaining_blocked": len([g for g in gates if gates[g]["state"] != "PASSED"]),
        "gate_a_passing_does_not_imply": gate_a["gate_a_passing_does_not_imply"],
        "next_required_owner_action": action,
        "spec_pack_intake": {
            "location": SPI.DOCS_REL,
            "documents_placed": intake["documents_placed"],
            "items_satisfied": intake["items_satisfied"],
            "items_refused": intake["items_refused"],
            "items_missing": intake["items_missing"],
            "state_record": f"{SPI.DOCS_REL}/intake_state.json",
            "dry_run": f"{SPI.DOCS_REL}/dry_run.md",
        },
        "supplier_request_dispatch": outreach,
        "supplier_outreach": "SUPERSEDED-BY §BH46 — the system never contacts suppliers",
        "gates_b_to_e_deferral": (deferral["PRODUCTION_AUTHORITY_GATES_B_TO_E"]
                                  if deferral else None),
        "gates_b_to_e_wait_on": "the owner-supplied spec pack, intaken item by item "
                                "(§BH46)",
        "deferral_is_not_a_pass": True,
    }
    if write:
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
    return rec
