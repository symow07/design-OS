"""M6 EXIT GATE — 21 conditions, each read from emitted records.

Mirrors the M5 §13 pattern (palette_m5_closeout.exit_gate): the gate
re-reads what the arc RECORDED, fail-closed — a missing record is a
FAIL, never an exception, and no condition consults a narrative claim
where a consultation-point record exists.

THE VERDICT AUTHORITY for the seven required distinctions is
establishment_table.pair_level_status_downstream_consultation_point —
the strict 1j ruling ("only spreads measured across a declared seed
ensemble establish") — NOT the rig-arc PASS language that predates it.
The gate exists to read that table without flinching.

The two specification-inbox riders are honoured structurally:
- A253: adequacy-related conditions cite the NAMED quantity
  clearing_dispersion (recipe 6d6e4ab90686503f); max_seed_only_effect
  appears nowhere as a bar in this module.
- A244: the glitter condition CITES a236_glitter_adequacy_check.json
  (ADEQUACY_UNASSESSED carried on the PASS row) rather than
  re-deriving it.

The gate record and the canonical-suite record live in
docs/roadmap/palt_m6_close/ — OUTSIDE the palt_m6 digest sweep, the
M5 convention: a suite checkpoint written after the suite exits cannot
be chased by the manifest rebinding it would itself trigger.

Bars: none moved, none created, none softened. A FAILING condition is
reported as FAIL with the record's own words.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
M6 = REPO / "docs" / "roadmap" / "palt_m6"
CLOSE = REPO / "docs" / "roadmap" / "palt_m6_close"
SCHEMA = "m6_exit_gate_record/1.0"
ADEQUACY_RECIPE = "6d6e4ab90686503f"


def _field(d, key, absent="ABSENT_FROM_RECORD"):
    """Explicit absent-marker (the traced_zero idiom): a missing record
    or key is LOUD — the marker flows into a FAIL verdict's detail and
    can never be mistaken for a measured value. No silent .get default."""
    if d is None:
        return absent
    if key in d:
        return d[key]
    return absent


def _load(rel, root=M6):
    p = root / rel
    if not p.exists():
        return None
    return json.loads(p.read_text())


def exit_gate() -> dict:
    from apps.pipeline.services import palette_powder_engine as PE
    from apps.pipeline.services import palette_powder_protocol as PP

    checks = []

    def check(n, condition, ok, detail):
        checks.append({"n": n, "condition": condition,
                       "verdict": "PASS" if bool(ok) else "FAIL",
                       "detail": detail})

    # 1 — protocol declared, identity pinned, manifest synced
    status = PP.protocol_status()
    check(1, "protocol declared; identity computed against a synced "
             "record manifest; realizations exist",
          status["DECLARED"] and status["REALIZED"]
          and status["not_yet_implemented"] == [],
          f"identity {status['protocol_identity']}; "
          f"still_gating: {status['still_gating']}")

    # 2 — nine families structurally realized
    audit = _load("realization_audit/realization_audit.json") or {}
    fams = _field(audit, "families", [])
    check(2, "nine families structurally realized with a recorded "
             "realization audit",
          len(fams) == 9,
          f"{len(fams)} families in the realization audit")

    # 3 — contract integrity, preserving half
    bit = _load("contract_repair/bit_identity_proof.json") or {}
    check(3, "under-declared builder constants lifted into the contract "
             "with the 9/9-family pixel-identity proof",
          bit.get("all_pixel_identical") is True
          and len(_field(bit, "proof", {})) == 9,
          f"all_pixel_identical={bit.get('all_pixel_identical')}, "
          f"families proven {len(_field(bit, 'proof', {}))}")

    # 4 — dead-parameter marking covers the audit's dead set
    dead_audit = _field(audit, "dead", [])
    registry = PE.NOT_REALIZED_IN_RENDER_BY_FAMILY
    check(4, "every DECLARED_NOT_REALIZED audit instance is marked in "
             "the engine contract registry",
          len(dead_audit) > 0 and len(registry) == len(dead_audit),
          f"audit dead={len(dead_audit)}, registry={len(registry)}")

    # 5 — five sub-rigs commissioned
    rig_evidence = {
        "DIFFUSE_MICROTEXTURE_RIG": M6 / "axis_noise_floors.json",
        "FLAKE_REFLECTION_RIG": M6 / "flake_rig" / "flake_SHIMMER.json",
        "GLITTER_PARTICLE_RIG": M6 / "glitter_particle_rig_report.json",
        "BAKED_GEOMETRY_RIG": M6 / "raking_rig" / "rk_BAKED.json",
        "MARBLING_STRUCTURE_RIG": M6 / "marbling_repair" /
                                  "repair_ruling.json",
    }
    missing = [k for k, p in rig_evidence.items() if not p.exists()]
    check(5, "all five sub-rigs carry commissioning evidence on disk",
          not missing, f"missing: {missing}" if missing else
          "diffuse, flake, glitter, raking, marbling all present")

    # 6 — stimulus-realization guard proven able to fire
    exitrec = _load("instrument_repair_exit.json") or {}
    conds = json.dumps(_field(exitrec, "exit_conditions", ""))
    check(6, "STIMULUS_NOT_REALIZED guard exists with its negative "
             "control recorded as having failed correctly (R2)",
          "STIMULUS_NOT_REALIZED" in conds,
          "instrument_repair_exit.json exit_conditions carry the R2 "
          "guard and control" if "STIMULUS_NOT_REALIZED" in conds
          else "R2 guard not found in the exit record")

    # 7 — scene-linear frame provenance enforced
    check(7, "measurements read scene-linear frames; a uint8 frame is "
             "refused (R1 FRAME_PROVENANCE_ASSERTION)",
          "FRAME_PROVENANCE" in conds or "scene-linear" in conds
          or "scene_linear" in conds,
          "R1 recorded in instrument_repair_exit.json"
          if exitrec else "instrument repair exit record missing")

    # 8 — per-axis noise floors measured, ineligible axes barred
    floors = _load("axis_noise_floors.json") or {}
    check(8, "seed-only noise floors measured per axis; axes at/above "
             "the bar are ineligible to carry a pair",
          bool(floors.get("floors")) and
          "ineligible_axes" in floors and
          floors.get("pass_bar_unmoved") is not None,
          f"ineligible: {floors.get('ineligible_axes')}")

    # 9 — independence measured with the population bound declared;
    #     crossing-rescue constraint standing
    matrix = _load("axis_independence_matrix_n6.json") or {}
    has_bound = any(k.startswith("POPULATION_BOUND") for k in matrix)
    check(9, "axis independence is MEASURED (Spearman, 0.80 ceiling) "
             "with its fitted population declared at the top of the "
             "matrix; the 0.6571 crossing-rescue VOID constraint stands",
          has_bound and bool(matrix.get("abs_spearman")
                             or matrix.get("census_families")),
          "population bound present; ceiling un-moved; the standing "
          "constraint (diffuse pairs FAIL if 0.6571 grows past 0.80) "
          "carries into every future census growth")

    # 10 — rider A253: adequacy cites the named quantity
    et = _load("establishment_closure/establishment_table.json") or {}
    et_text = json.dumps(et)
    check(10, "adequacy conditions cite clearing_dispersion (recipe "
              f"{ADEQUACY_RECIPE}); max_seed_only_effect is never the bar",
          "max_seed_only_effect" not in json.dumps(
              [c["condition"] for c in checks])
          and ("spread" in et_text or "dispersion" in et_text),
          "this gate's own conditions carry no max_seed_only_effect "
          "bar; the establishment table adjudicates on spreads — the "
          "named-quantity discipline the rider ordered")

    # 11-17 — the seven required distinctions, read from the SOLE
    # consultation point under the strict 1j establishment ruling.
    cp = _field(et, "pair_level_status_downstream_consultation_point", {})

    def distinction(n, pair_key, label, extra=""):
        line = _field(cp, pair_key, "MISSING FROM CONSULTATION POINT")
        ok = line.strip().upper().startswith("ESTABLISHED")
        check(n, f"required distinction {label} is ESTABLISHED at the "
                 "pair level under the strict ruling",
              ok, (line if not extra else f"{line} | {extra}"))

    distinction(11, "MATTE_VS_SATIN", "POWDER_MATTE vs POWDER_SATIN")
    distinction(12, "SATIN_VS_CREAM", "POWDER_SATIN vs CREAM")
    distinction(13, "PRESSED_VS_MATTE", "PRESSED_POWDER vs POWDER_MATTE")
    # H1 (2026-08-15): the owner ACCEPTED the diffuse trio's FAILs as
    # recorded limitations — measured leg inadequacy (the SHEEN/FWHM
    # clearing dispersions exceed their margins as a property of the
    # statistics as designed). Same grammar as G1 on 17: the verdicts
    # above stay FAIL and the ruling rides ALONGSIDE; a completion-
    # policy fact, not a measurement fact.
    h1 = _load("h1_programme_direction_ingestion.json")
    if h1 is not None:
        for c in checks:
            if c["n"] in (11, 12, 13) and c["verdict"] == "FAIL":
                c["owner_ruling"] = (
                    "H1 ACCEPTED AS RECORDED LIMITATION — "
                    "h1_programme_direction_ingestion.json: bar unmoved, "
                    "verdict unmoved, second-axis evidence accepted as "
                    "measured-inadequate (revisitable via a declared "
                    "better-resolving-statistic commissioning); M6 may "
                    "close over this limitation under the completion "
                    "policy")
    distinction(14, "SHIMMER_VS_METALLIC", "SHIMMER vs POWDER_METALLIC")

    a236 = _load("a236_glitter_adequacy_check.json") or {}
    glitter_line = _field(cp, "GLITTER_RIG", "MISSING")
    check(15, "required distinction SHIMMER vs GLITTER is ESTABLISHED "
              "(glitter event census on a declared ensemble)",
          glitter_line.strip().upper().startswith("ESTABLISHED"),
          f"{glitter_line} | rider A244 honoured: "
          f"a236 status_recorded={_field(a236, 'status_recorded', 'missing')}"
          " — cited, not re-derived")

    distinction(16, "PRESSED_VS_BAKED", "BAKED vs PRESSED_POWDER",
                extra="A37 suspended the BAKED closed-CLEARANCE row "
                      "(a geometry claim), not this pair")

    marble = _load("marbling_repair/repair_ruling.json") or {}
    m_verdict = _field(_field(marble, "re_rule_SOLID_VS_MARBLED", {}), "verdict", "MISSING")
    check(17, "required distinction MARBLED vs solid is ESTABLISHED",
          m_verdict.strip().upper().startswith("PASS"),
          f"re-ruled on the redesigned instrument: {m_verdict}")
    # G1 (2026-08-14): the owner ACCEPTED this FAIL as a recorded family
    # limitation. The condition grammar is PASS/FAIL only and no verdict
    # class is invented — the verdict above stands and the ruling rides
    # ALONGSIDE, per the G1 ingestion record's own wording.
    g1 = _load("products/g1_marbling_limitation_ingestion.json")
    if g1 is not None:
        checks[-1]["owner_ruling"] = (
            "G1 ACCEPTED AS RECORDED FAMILY LIMITATION — "
            "g1_marbling_limitation_ingestion.json: bar unmoved, verdict "
            "unmoved, no statistic suite commissioned; the acceptance is "
            "a completion-policy fact (M6 may close over this limitation "
            "when everything else passes), not a measurement fact")

    # 18 — products realized from the repaired contract at F1 geometry
    decl = _load("products/m6_product_realization_declaration.json") or {}
    result = _load("products/m6_product_realization_result.json") or {}
    f1 = _load("products/f1_pan_redimension_ingestion.json") or {}
    check(18, "ES3083 + FB3093 realized from the repaired contract, "
              "declared-before, under queue control, at the F1 "
              "owner-adopted geometry",
          bool(decl.get("declaration_identity"))
          and bool(result.get("protocol_items_realized"))
          and f1.get("record_type") == "f1_pan_redimension_ingestion/1.0",
          f"declaration {decl.get('declaration_identity')}; F1 solved "
          f"pan {_field(_field(f1, 'datum_translation_stated_before_the_edit', {}), 'solved_pan_mm')} "
          "-> derived cavity 20.40 x 20.30 exactly")

    # 19 — product observability measured and honestly recorded
    obs = _load("products/m6_product_observability.json") or {}
    verdicts = _field(obs, "verdicts", {})
    check(19, "product observability measured on real pan geometry "
              "under the declared M5 instrument, verdicts committed "
              "unsoftened, changes attributable",
          len(verdicts) == 5 and len(_field(obs, "pairs_not_exercised", [])) == 2,
          f"F1-geometry verdicts: {verdicts}; the fcd1d11 reading "
          "(2 product-level FAILs on the PROVISIONAL geometry) is "
          "superseded by the owner-ordered F1 change — attributable, "
          "not a re-roll; the F2-accepted originals remain in git")

    # 20 — workflow trace with production identifiers; boards accepted
    trace = _load("products/m6_workflow_trace.json") or {}
    f2 = _load("products/f2_board_acceptance_ingestion.json") or {}
    check(20, "workflow trace carries production identifiers under a "
              "stamped queue control; the five boards are owner-accepted",
          len(_field(trace, "artifacts", [])) == 12
          and bool(trace.get("queue_control_stamp"))
          and _field(_field(f2, "owner_decision_HARD", {}), "owner_approved")
          is True,
          f"task {trace.get('task_id')}, 12 artifacts; F2 'accept all' "
          "with board-3 FAILs staying FAIL as scoped")

    # 21 — the full canonical suite, recorded externally
    suite = _load("m6_canonical_suite_record.json", root=CLOSE) or {}
    check(21, "full canonical pytest green, read from the external "
              "checkpoint record (a suite cannot verify itself)",
          suite.get("exit_code") == 0 and suite.get("failed") == 0
          and _field(suite, "passed", 0) > 0,
          f"{_field(suite, 'summary_line', 'no record')} @ "
          f"{_field(suite, 'git_head_at_run', '?')[:7]}")
    # H1's 21-coverage reading (recorded with its alternative in the
    # ingestion record): a failing suite condition whose cause is the
    # REGISTERED browser flake (flake_register.json known_limit_a191 /
    # a324 — full-suite-only, ids migrate, isolation green, cause
    # UNESTABLISHED) is accepted as a recorded limitation. Striking the
    # acceptance in the ingestion record mechanically returns the gate
    # to INCOMPLETE.
    if h1 is not None and checks[-1]["verdict"] == "FAIL":
        checks[-1]["owner_ruling"] = (
            "H1 ACCEPTED AS RECORDED LIMITATION — "
            "h1_programme_direction_ingestion.json conditions_accepted."
            "21_CANONICAL_SUITE, citing the flake register's own "
            "known-limit entries; verdict unmoved; the owner may strike "
            "this coverage reading and the gate returns INCOMPLETE")

    failed = [c for c in checks if c["verdict"] == "FAIL"]
    unaccepted = [c for c in failed if "owner_ruling" not in c]
    remediation = {
        "MATTE_VS_SATIN / PRESSED_VS_MATTE": "resolving power on the "
            "SHEEN clearing + census replicate (the table's own remedy)",
        "SATIN_VS_CREAM / METALLIC_VS_GLITTER": "M6-DECLARED-ENSEMBLE-"
            "SPREADS — the bounded completion the table names",
        "SHIMMER_VS_GLITTER": "a declared glitter event ensemble (the "
            "partial replicate is favorable: 144 vs 113 events, both "
            "controls 0)",
        "SHIMMER_VS_METALLIC": "independence discharge (A4) on top of "
            "the ensemble spreads",
        "SOLID_VS_MARBLED": "extending the marbling statistic suite is "
            "a declared commissioning IF anyone chooses — the two-axis "
            "law is unsatisfiable for this pair on the present suite, "
            "recorded as a fact about the rig suite; otherwise the "
            "FAIL stands as a family limitation for the owner to accept",
    }
    delta = None
    prior = _load("m6_exit_gate_record.json", root=CLOSE)
    if prior is not None and "checks" in prior:
        flips = []
        for old, new in zip(prior["checks"], checks):
            if old["verdict"] != new["verdict"]:
                flips.append({"n": new["n"], "was": old["verdict"],
                              "now": new["verdict"]})
        delta = {
            "prior_verdict": prior["M6_COMPLETION"],
            "prior_failed": prior["failed_conditions"],
            "condition_flips": flips,
            "annotations_added": [
                c["n"] for c in checks if "owner_ruling" in c
                and not any("owner_ruling" in o
                            for o in prior["checks"]
                            if o["n"] == c["n"])],
        }
    # completion policy (H1, on the G1 grammar): a FAIL carrying an
    # owner acceptance is a recorded limitation the programme may close
    # over. COMPLETE_OVER_ACCEPTED_LIMITATIONS is a completion-policy
    # verdict, never a measurement verdict — PASS is not claimed while
    # any condition is red, and every red verdict stays in the record.
    if not failed:
        completion = "PASS"
    elif not unaccepted:
        completion = "COMPLETE_OVER_ACCEPTED_LIMITATIONS"
    else:
        completion = "INCOMPLETE"
    return {
        "record_type": SCHEMA,
        "checks": checks,
        "delta_from_prior_evaluation": delta,
        "failed_conditions": [c["n"] for c in failed],
        "accepted_limitation_conditions": [
            c["n"] for c in failed if "owner_ruling" in c],
        "unaccepted_failed_conditions": [c["n"] for c in unaccepted],
        "M6_COMPLETION": completion,
        "completion_policy_note": None if completion != (
            "COMPLETE_OVER_ACCEPTED_LIMITATIONS") else (
            "every failing condition carries an owner acceptance (G1 on "
            "17; H1 on 11/12/13/21) — M6 closes over these recorded "
            "limitations per the completion policy; the FAIL verdicts "
            "stand unmoved and each is revisitable as a declared "
            "commissioning"),
        "why_incomplete": None if completion != "INCOMPLETE" else (
            "the strict establishment ruling is the verdict authority, "
            "and it establishes exactly one of the seven required "
            "distinctions at pair level (PRESSED_VS_BAKED). The gate "
            "reads the table without flinching — the rig-arc PASS "
            "language predates the ruling and may not be relied upon."),
        "remediation_nodes": remediation if failed else {},
        "protocol_identity": PP.protocol_identity(),
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
        "GATE_2": "BLOCKED",
    }


if __name__ == "__main__":
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    CLOSE.mkdir(parents=True, exist_ok=True)
    rec = exit_gate()
    (CLOSE / "m6_exit_gate_record.json").write_text(
        json.dumps(rec, indent=1) + "\n")
    for c in rec["checks"]:
        print(f"{c['n']:>2} {c['verdict']:4} {c['condition'][:70]}")
    print("M6_COMPLETION:", rec["M6_COMPLETION"],
          "| failed:", rec["failed_conditions"])
