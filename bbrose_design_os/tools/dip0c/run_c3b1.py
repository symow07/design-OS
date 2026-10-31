"""DIP-0C3b1 runner — validate the rights model and emit the transition matrix.

This slice ships a MODEL, so the "run" is a validation: it enumerates every
(from, to) pair on both axes for both actors, records which are legal and which are
refused and why, and proves the central invariant holds by construction rather than
by inspection.

No materials are read. Integrity is still snapshotted, because a slice that touches
nothing must be able to *prove* it touched nothing.

    python -m tools.dip0c.run_c3b1
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter

from tools.dip0.integrity import compare, snapshot
from tools.dip0.report import json_default

from . import config as C
from . import rights_model as RM

PARSER = f"{C.TOOL_NAME}.run_c3b1/{C.TOOL_VERSION}"

HUMAN_ONLY_TOKENS = (C.OWN_BBROSE_CONFIRMED, C.OWN_THIRD_PARTY_CONFIRMED,
                     C.OWN_LICENSED_LIMITED, C.OWN_JOINT_OR_CONTRACTED,
                     C.LIC_APPROVED, C.CANONICAL_BRAND_MASTER,
                     C.POSTURE_APPROVED_REUSABLE)


def build_matrix() -> dict:
    """Every (from, to) pair on every axis for every actor, with the verdict."""
    matrix = {}
    for axis in (RM.AXIS_OWNERSHIP, RM.AXIS_LICENSE):
        matrix[axis] = {}
        for actor in (RM.ACTOR_MACHINE, RM.ACTOR_HUMAN):
            legal, refused = [], []
            for frm in RM.STATES[axis]:
                for to in RM.STATES[axis]:
                    if frm == to:
                        continue
                    try:
                        RM.validate_transition(axis, frm, to, actor)
                        legal.append({"from": frm, "to": to})
                    except (RM.IllegalTransition, RM.MachineMayNotIncrease,
                            C.HumanOnlyStateViolation) as e:
                        refused.append({"from": frm, "to": to,
                                        "refused_because": type(e).__name__,
                                        "reason": str(e)})
            matrix[axis][actor] = {
                "legal_count": len(legal),
                "refused_count": len(refused),
                "legal": legal,
                "refused": refused,
            }
    return matrix


def verify_guards() -> dict:
    """Prove the human-only states and the no-increase rule are unreachable."""
    results = {}

    def _refuses(fn, *a):
        try:
            fn(*a)
        except (C.HumanOnlyStateViolation, RM.MachineMayNotIncrease,
                RM.IllegalTransition):
            return True
        return False

    results["machine_cannot_emit_human_only_ownership"] = all(
        _refuses(C.machine_ownership, s) for s in C.HUMAN_ONLY_OWNERSHIP)
    results["machine_cannot_emit_human_only_license"] = all(
        _refuses(C.machine_license, s) for s in C.HUMAN_ONLY_LICENSE)
    results["machine_cannot_invent_a_business_assertion"] = _refuses(
        C.machine_ownership, C.OWN_BUSINESS_ASSERTED_BBROSE)
    results["machine_cannot_select_canonical_master"] = _refuses(
        C.machine_brand_master, C.CANONICAL_BRAND_MASTER)

    # the invariant: no machine transition may increase rank on either axis
    increases = []
    for axis in (RM.AXIS_OWNERSHIP, RM.AXIS_LICENSE):
        for frm, to in RM.legal_transitions(axis, RM.ACTOR_MACHINE):
            if RM.RANK[axis][to] > RM.RANK[axis][frm]:
                increases.append((axis, frm, to))
    results["machine_never_increases_certainty"] = not increases
    results["certainty_increases_found"] = increases

    # the invariant: no machine permission grant
    perms = RM.permissions()
    grant_refused = []
    for flag in RM.PERMISSION_FLAGS:
        proposed = dict(perms)
        proposed[flag] = True
        grant_refused.append(_refuses(RM.machine_permission_update, perms,
                                      proposed))
    results["machine_cannot_grant_any_permission"] = all(grant_refused)
    results["permission_flags_checked"] = len(RM.PERMISSION_FLAGS)

    # machine MAY revoke
    rec = RM.rights_record("x")
    rec["permissions"]["retrieval_allowed"] = True          # (a human granted it)
    RM.machine_revoke(rec, "retrieval_allowed", reason="expired")
    results["machine_may_revoke"] = rec["permissions"]["retrieval_allowed"] is False
    return results


def verify_layers() -> dict:
    """The four layers must have DISJOINT key sets — no layer can write another."""
    rec = RM.rights_record("x")
    keys = {
        "business_assertion": set(rec["business_assertion"]),
        "machine_inference": set(rec["machine_inference"][RM.AXIS_OWNERSHIP]),
        "human_confirmation": set(rec["human_confirmation"][RM.AXIS_OWNERSHIP]),
        "permissions": set(rec["permissions"]),
    }
    overlaps = {}
    names = list(keys)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = keys[a] & keys[b]
            if shared:
                overlaps[f"{a}|{b}"] = sorted(shared)
    return {
        "layer_key_counts": {k: len(v) for k, v in keys.items()},
        "layers_are_disjoint": not overlaps,
        "overlapping_keys": overlaps,
        "defaults": {
            "ownership": rec["machine_inference"]["ownership"]["machine_state"],
            "license": rec["machine_inference"]["license"]["machine_state"],
            "confirmed_ownership": rec["human_confirmation"]["ownership"][
                "confirmed_state"],
            "all_permissions_denied": all(
                rec["permissions"][f] is False for f in RM.PERMISSION_FLAGS),
            "approved_products": rec["permissions"]["approved_products"],
            "approved_markets": rec["permissions"]["approved_markets"],
            "canonical_brand_master": rec["canonical_brand_master"],
        },
    }


def verify_assertion_grants_nothing() -> dict:
    """A business assertion records a BELIEF and changes nothing else."""
    rec = RM.rights_record("logo6.ai")
    before = json.dumps(
        {"m": rec["machine_inference"], "h": rec["human_confirmation"],
         "p": rec["permissions"]}, default=json_default, sort_keys=True)
    rec["business_assertion"] = RM.business_assertion(
        C.OWN_BUSINESS_ASSERTED_BBROSE, asserted_by="business_owner",
        asserted_at="2026-07-11T00:00:00+00:00",
        notes="the business believes this is the BBROSE logo")
    after = json.dumps(
        {"m": rec["machine_inference"], "h": rec["human_confirmation"],
         "p": rec["permissions"]}, default=json_default, sort_keys=True)

    ok, why = RM.can_confirm(rec, RM.AXIS_OWNERSHIP, C.OWN_BBROSE_CONFIRMED,
                             reviewed_evidence=[])
    return {
        "assertion_changed_nothing_else": before == after,
        "assertion_is_not_a_confirmation":
            rec["business_assertion"]["is_confirmation"] is False,
        "assertion_grants_no_permission": all(
            rec["permissions"][f] is False for f in RM.PERMISSION_FLAGS),
        "effective_ownership_is_still_unknown":
            RM.effective_state(rec, RM.AXIS_OWNERSHIP) == C.OWN_UNKNOWN,
        "assertion_alone_cannot_confirm": ok is False,
        "why_not": why,
    }


def _no_output_under_source() -> dict:
    src, out = C.SOURCE_ROOT.resolve(), C.OUTPUT_ROOT.resolve()
    inside = out == src or src in out.parents
    return {"output_root": str(out), "source_root": str(src), "ok": not inside}


def main(argv=None) -> int:
    t0 = time.monotonic()
    C.ensure_output_dirs()
    before = snapshot()
    matrix = build_matrix()
    guards = verify_guards()
    layers = verify_layers()
    assertion = verify_assertion_grants_nothing()
    after = snapshot()

    integrity = {"materials": compare(before, after),
                 "no_output_under_source": _no_output_under_source()}

    counts = {axis: {actor: {"legal": matrix[axis][actor]["legal_count"],
                             "refused": matrix[axis][actor]["refused_count"]}
                     for actor in matrix[axis]} for axis in matrix}
    refused_reasons = Counter(
        r["refused_because"] for axis in matrix
        for r in matrix[axis][RM.ACTOR_MACHINE]["refused"])

    recon = {
        "slice": "DIP-0C3b1",
        "c3a_commit": "2c00dda6e0595f85d78c189941cb5682bd0b9f57",
        "model_version": RM.MODEL_VERSION,
        "ownership_states": {
            "machine_permitted": list(C.MACHINE_ALLOWED_OWNERSHIP),
            "human_only": list(C.HUMAN_ONLY_OWNERSHIP),
            "business_assertion": C.OWN_BUSINESS_ASSERTED_BBROSE,
            "total": len(C.OWNERSHIP_STATES),
        },
        "license_states": {
            "machine_permitted": list(C.MACHINE_ALLOWED_LICENSE),
            "human_only": list(C.HUMAN_ONLY_LICENSE),
            "total": len(C.LICENSE_STATES),
        },
        "transition_counts": counts,
        "machine_refusal_reasons": dict(refused_reasons),
        "permission_flags": list(RM.PERMISSION_FLAGS),
        "machine_guards": guards,
        "four_layers": layers,
        "business_assertion_behaviour": assertion,
        "integrity": integrity,
        "runtime_seconds": round(time.monotonic() - t0, 2),
    }

    # committed lightweight records
    mpath = C.MILESTONE_OUTPUT_ROOT / "c3b1_transition_matrix.json"
    C.assert_output_safe(mpath)
    mpath.write_text(json.dumps(matrix, default=json_default, indent=2),
                     encoding="utf-8")
    rpath = C.MILESTONE_OUTPUT_ROOT / "c3b1_reconciliation.json"
    C.assert_output_safe(rpath)
    rpath.write_text(json.dumps(recon, default=json_default, indent=2),
                     encoding="utf-8")

    ok = (integrity["materials"]["unchanged"]
          and integrity["no_output_under_source"]["ok"]
          and all(v for k, v in guards.items() if isinstance(v, bool))
          and layers["layers_are_disjoint"]
          and all(v for v in assertion.values() if isinstance(v, bool)))
    _print(recon)
    if not ok:
        print("\nFAILED: a model invariant does not hold", file=sys.stderr)
        return 1
    return 0


def _print(r: dict) -> None:
    print(f"DIP-0C3b1 — rights model {r['model_version']}")
    print(f"  ownership:  {len(r['ownership_states']['machine_permitted'])} "
          f"machine-permitted, {len(r['ownership_states']['human_only'])} "
          f"HUMAN-ONLY, + 1 business assertion")
    print(f"  license:    {len(r['license_states']['machine_permitted'])} "
          f"machine-permitted, {len(r['license_states']['human_only'])} HUMAN-ONLY")
    for axis, by_actor in r["transition_counts"].items():
        print(f"  {axis:9} transitions: "
              f"machine legal={by_actor['machine']['legal']} "
              f"refused={by_actor['machine']['refused']} | "
              f"human legal={by_actor['human']['legal']}")
    print(f"  refusals:   {r['machine_refusal_reasons']}")
    print(f"  permissions:{len(r['permission_flags'])} flags, all default false")
    print("  guards:")
    for k, v in r["machine_guards"].items():
        if isinstance(v, bool):
            print(f"     {k}: {v}")
    print(f"  layers disjoint: {r['four_layers']['layers_are_disjoint']}")
    print(f"  assertion grants nothing: "
          f"{r['business_assertion_behaviour']['assertion_grants_no_permission']}, "
          f"cannot confirm: "
          f"{r['business_assertion_behaviour']['assertion_alone_cannot_confirm']}")
    print(f"  integrity:  materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:    {r['runtime_seconds']}s")


if __name__ == "__main__":
    raise SystemExit(main())
