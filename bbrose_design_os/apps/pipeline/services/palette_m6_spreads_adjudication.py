"""M6-SPREADS ADJUDICATION — the establishment machinery's own act.

The driver (palette_m6_spreads_driver) renders and REFUSES to
adjudicate; this module is the second half of that separation. It reads
a committed raw ensemble record and adjudicates the establishment-table
rows the campaign declared that record to complete — under the leg
grammar AS WRITTEN, nothing improvised:

- the named quantity is 1k's clearing_dispersion (A289 recipe: the
  clearing recomputed at each member of the declared ensembles, and the
  MAX PAIRWISE ABSOLUTE DIFFERENCE of those clearings) computed by
  palette_clearing_dispersion — max_seed_only_effect is reported
  alongside where a row recorded it, NEVER the bar;
- adequacy precondition: the row's committed margin must exceed the
  DIRECTLY measured dispersion. Met -> the row establishes on the
  strict ruling's own terms (declared-ensemble spread, direct tier).
  Unmet -> ADEQUACY_PRECONDITION_UNMET_DIRECT, an honest FAIL — no
  crossing rescue (VOID: diffuse pairs FAIL if the standing 0.6571
  grows past 0.80; this act grows no census, so the constraint is
  cited, not re-derived);
- a row whose statistic the record DOES NOT CONTAIN is refused, not
  approximated: ABSENT_STATISTIC — the leg's named quantity remains
  unmeasured and the row stands untouched. (The known instance: the
  texture rig measures GRANULARITY_INDEX and GRAZING_BAND_CONTRAST;
  SHEEN_REGION_RESPONSE and HIGHLIGHT_FWHM are lobe axes of the
  characterization rig — a texture-rig raw record cannot adjudicate a
  SHEEN or FWHM leg, and saying so plainly is the adjudication.)

Member pairing: the campaign's declared ensembles pair member k of
family A with member k of family B (member 0 = the canonical pair
seeds), so the common key for clearings_per_seed is the MEMBER INDEX,
with the literal seeds recorded alongside. Member 0's clearing must
reproduce the row's committed reading — a raw record that cannot
reproduce the reading it claims to complete is refused.

Supersession is IN PLACE per the launcher's rule: the row's spread,
spread_source, status and note move; what they were is kept inside the
row under `superseded_2026_08_15`, and the full before/after with the
per-member clearings lives in the adjudication record committed next
to the raw record. cleared_against identities are minted by
palette_verdict_identity.mint over the measured payload.
"""
from __future__ import annotations

import json
from pathlib import Path

from apps.pipeline.services import palette_clearing_dispersion as CD
from apps.pipeline.services import palette_verdict_identity as VI

REPO = Path(__file__).resolve().parents[3]
SPREADS = REPO / "docs" / "roadmap" / "palt_m6" / "declared_spreads"
TABLE = (REPO / "docs" / "roadmap" / "palt_m6" / "establishment_closure"
         / "establishment_table.json")

ADJUDICATION_DATE = "2026-08-15"

#: statistic-name (row vocabulary) -> measured axis name
AXIS_OF = {
    "GRAN": "GRANULARITY_INDEX",
    "SHEEN": "SHEEN_REGION_RESPONSE",
    "FWHM": "HIGHLIGHT_FWHM",
}

#: what the campaign declaration says each raw record completes:
#: phase -> list of (table row verdict, statistic key, family_a, family_b)
#: family order matches the row's committed reading direction.
DECLARED_COMPLETIONS = {
    "sc": (
        ("S_V_C GRAN clearing", "GRAN", "POWDER_SATIN", "CREAM"),
        ("S_V_C FWHM clearing", "FWHM", "POWDER_SATIN", "CREAM"),
    ),
    "mvs_sheen": (
        ("M_V_S SHEEN clearing", "SHEEN", "POWDER_MATTE", "POWDER_SATIN"),
        # the same member-pairs measure the GRAN clearing directly; the
        # row is ESTABLISHED on TRANSFER and a direct measurement is the
        # strictly better tier — superseded on the same terms, no PASS
        # inherited, the arithmetic recomputed.
        ("M_V_S GRAN clearing", "GRAN", "POWDER_MATTE", "POWDER_SATIN"),
    ),
    "pvm_sheen": (
        ("P_V_M SHEEN clearing", "SHEEN", "PRESSED_POWDER", "POWDER_MATTE"),
        ("P_V_M GRAN clearing", "GRAN", "PRESSED_POWDER", "POWDER_MATTE"),
    ),
    # lobe phases (the SHEEN/FWHM legs' own instrument), declared in
    # sheen_fwhm_instrument_resolution.json: one raw record carrying all
    # four families' member swatches adjudicates all three lobe legs.
    "lobe": (
        ("M_V_S SHEEN clearing", "SHEEN", "POWDER_MATTE", "POWDER_SATIN"),
        ("P_V_M SHEEN clearing", "SHEEN", "PRESSED_POWDER", "POWDER_MATTE"),
        ("S_V_C FWHM clearing", "FWHM", "POWDER_SATIN", "CREAM"),
    ),
}

#: reading reproduction tolerance: the table stores 4-dp readings, so
#: member 0 must reproduce within one half-unit of the 4th place plus
#: float slack.
READING_TOLERANCE = 6e-5

#: The diffuse pairs' OWN leg grammar, exactly as the standing
#: consultation-point lines name it: MATTE_VS_SATIN and PRESSED_VS_MATTE
#: stand on GRAN + SHEEN legs AND the R5 census leg ("census leg
#: pending" / "same shape"); SATIN_VS_CREAM stands on its two legs with
#: no census leg named. SHIMMER_VS_METALLIC and GLITTER_RIG have their
#: own grammars (A4 discharge / event-ensemble adjudication) and are
#: restated by those acts, not here.
PAIR_GRAMMAR = {
    "MATTE_VS_SATIN": {
        "legs": ("M_V_S GRAN clearing", "M_V_S SHEEN clearing"),
        "census_leg": "R5 census GRAN|SHEEN",
    },
    "PRESSED_VS_MATTE": {
        "legs": ("P_V_M GRAN clearing", "P_V_M SHEEN clearing"),
        "census_leg": "R5 census GRAN|SHEEN",
    },
    "SATIN_VS_CREAM": {
        "legs": ("S_V_C GRAN clearing", "S_V_C FWHM clearing"),
        "census_leg": None,
    },
}

#: pair touched by each adjudicated/refused row
PAIR_OF_ROW = {
    "M_V_S GRAN clearing": "MATTE_VS_SATIN",
    "M_V_S SHEEN clearing": "MATTE_VS_SATIN",
    "P_V_M GRAN clearing": "PRESSED_VS_MATTE",
    "P_V_M SHEEN clearing": "PRESSED_VS_MATTE",
    "S_V_C GRAN clearing": "SATIN_VS_CREAM",
    "S_V_C FWHM clearing": "SATIN_VS_CREAM",
}


def _leg_established(row) -> bool:
    return str(row["status"]).startswith("ESTABLISHED")


def restate_pair(table, pair_key) -> str:
    """Rewrite one consultation-point line from CURRENT row statuses,
    under the pair's own named grammar — never inventing a leg and
    never dropping one."""
    grammar = PAIR_GRAMMAR[pair_key]
    legs = {v: _find_row(table, v) for v in grammar["legs"]}
    parts = [f"{v}: {row['status']}" for v, row in legs.items()]
    established = all(_leg_established(r) for r in legs.values())
    census_note = ""
    if grammar["census_leg"]:
        census = _find_row(table, grammar["census_leg"])
        census_ok = _leg_established(census)
        established = established and census_ok
        census_note = (f"; census leg ({grammar['census_leg']}) "
                       f"{census['status']}")
    head = "ESTABLISHED" if established else "NOT ESTABLISHED"
    line = (f"{head} — " + "; ".join(parts) + census_note
            + f" [restated {ADJUDICATION_DATE} by the spreads "
              "adjudication act from the rows in place]")
    table["pair_level_status_downstream_consultation_point"][pair_key] = line
    return line


class AdjudicationError(RuntimeError):
    """Refuses rather than producing a plausible verdict."""


def _member_values(raw, family, axis):
    """axis value per member index for one family, or None if the
    record does not carry the axis; literal seeds returned alongside."""
    phase = raw["phase"]
    fam_idx = raw["families"].index(family)
    seed_key = "seed_a" if fam_idx == 0 else "seed_b"
    values, seeds = {}, {}
    for row in raw["rows"]:
        key = f"{phase}_m{row['member']}_{family}"
        report = row["pair_report"].get(key)
        if report is None:
            raise AdjudicationError(
                f"raw record {phase} has no member report {key} — "
                "malformed record, refusing")
        if axis not in report:
            return None, None
        values[row["member"]] = float(report[axis])
        seeds[row["member"]] = row[seed_key]
    return values, seeds


def _lobe_member_values(raw, family, axis):
    """Per-member axis values from a lobe raw record (per-family
    member swatches, keyed members[family][k])."""
    fam = raw["members"].get(family)
    if fam is None:
        return None, None
    values, seeds = {}, {}
    for k, entry in enumerate(fam):
        if axis not in entry["axes"]:
            return None, None
        values[k] = float(entry["axes"][axis])
        seeds[k] = entry["seed"]
    return values, seeds


def _find_row(table, verdict):
    for row in table["table"]:
        if row["verdict"] == verdict:
            return row
    raise AdjudicationError(f"no establishment row {verdict!r}")


def adjudicate(phase, raw_path=None, table_path=TABLE, write=True) -> dict:
    """Adjudicate every row the campaign declared `phase` to complete."""
    if phase not in DECLARED_COMPLETIONS:
        raise AdjudicationError(f"phase {phase!r} has no declared "
                                "completions — nothing to adjudicate")
    raw_path = Path(raw_path or (SPREADS / f"raw_{phase}.json"))
    raw = json.loads(raw_path.read_text())
    table = json.loads(Path(table_path).read_text())
    lobe = raw["record_type"].startswith("m6_spreads_raw_lobe")

    acts, findings = [], []
    for verdict, stat_key, fam_a, fam_b in DECLARED_COMPLETIONS[phase]:
        axis = AXIS_OF[stat_key]
        getter = _lobe_member_values if lobe else _member_values
        vals_a, seeds_a = getter(raw, fam_a, axis)
        vals_b, seeds_b = getter(raw, fam_b, axis)
        if vals_a is None or vals_b is None:
            findings.append({
                "row": verdict,
                "finding": "ABSENT_STATISTIC",
                "statistic": axis,
                "detail": (f"the raw record measures neither family's "
                           f"{axis} — the leg's named quantity remains "
                           "unmeasured by this record and the row stands "
                           "untouched; refusal, not approximation"),
            })
            continue

        row = _find_row(table, verdict)
        disp = CD.clearing_dispersion(vals_a, vals_b)
        m0 = disp["per_seed_clearings"][0]
        reading = float(row["reading"])
        if abs(m0 - reading) > READING_TOLERANCE:
            raise AdjudicationError(
                f"{verdict}: member-0 clearing {m0:.6f} does not "
                f"reproduce the committed reading {reading} — the raw "
                "record cannot complete a row it cannot reproduce")

        margin = float(row["margin"])
        adequate = margin > disp["dispersion"]
        prior = {k: row.get(k) for k in
                 ("spread", "spread_source", "status", "note")}
        identity = VI.mint({
            "pair": verdict,
            "statistic": axis,
            "per_member_clearings": {str(k): round(v, 6) for k, v in
                                     disp["per_seed_clearings"].items()},
            "member_seeds": {str(k): [seeds_a[k], seeds_b[k]]
                             for k in seeds_a},
            "dispersion": round(disp["dispersion"], 6),
            "dispersion_recipe": disp["recipe_identity"],
            "source_record": raw_path.name,
        })

        row["spread"] = round(disp["dispersion"], 5)
        row["spread_source"] = (
            f"DIRECT: 6-member declared-ensemble pairs ({raw_path.name}), "
            f"clearing_dispersion recipe {disp['recipe_identity']}")
        if adequate:
            row["status"] = "ESTABLISHED"
            row["note"] = (
                f"established {ADJUDICATION_DATE} by direct "
                f"declared-ensemble measurement: margin {margin} > "
                f"clearing_dispersion {disp['dispersion']:.5f} "
                f"[cleared_against={identity}]")
        else:
            row["status"] = "ADEQUACY_PRECONDITION_UNMET_DIRECT"
            row["note"] = (
                f"honest FAIL {ADJUDICATION_DATE}: margin {margin} <= "
                f"clearing_dispersion {disp['dispersion']:.5f} measured "
                f"directly on the declared ensembles "
                f"[cleared_against={identity}]")
        row["superseded_" + ADJUDICATION_DATE.replace("-", "_")] = prior

        acts.append({
            "row": verdict, "statistic": axis,
            "families": [fam_a, fam_b],
            "member_seeds": {str(k): [seeds_a[k], seeds_b[k]]
                             for k in seeds_a},
            "per_member_clearings": disp["per_seed_clearings"],
            "pairwise": disp["pairwise"],
            "clearing_dispersion": disp["dispersion"],
            "recipe_identity": disp["recipe_identity"],
            "reading_reproduced_at_member_0": m0,
            "committed_reading": reading,
            "margin": margin,
            "adequacy_precondition_met": adequate,
            "prior_row_state": prior,
            "new_status": row["status"],
            "cleared_against": identity,
        })

    pairs_restated = {}
    for act in acts:
        pair_key = PAIR_OF_ROW.get(act["row"])
        if pair_key and pair_key not in pairs_restated:
            pairs_restated[pair_key] = restate_pair(table, pair_key)

    record = {
        "record_type": f"m6_spreads_adjudication_{phase}/1.0",
        "adjudicated": ADJUDICATION_DATE,
        "phase": phase,
        "raw_record": raw_path.name,
        "pair_level_lines_restated": pairs_restated,
        "law": ("1k clearing_dispersion under A289 "
                f"(recipe {CD.recipe_identity()}); adequacy = committed "
                "margin > directly measured dispersion; "
                "max_seed_only_effect never the bar; crossing rescue "
                "VOID (0.6571 past 0.80 fails the diffuse pairs) cited "
                "— this act grows no census"),
        "acts": acts,
        "findings": findings,
        "owner_approved": False,
    }
    if write:
        out = SPREADS / f"adjudication_{phase}.json"
        out.write_text(json.dumps(record, indent=1) + "\n")
        Path(table_path).write_text(json.dumps(table, indent=1) + "\n")
    return record


def adjudicate_glitter(raw_path=None, table_path=TABLE,
                       write=True) -> dict:
    """The glitter event ensemble's own adjudication: the census's
    replicate spread — the quantity every GLITTER row recorded as never
    measured — measured across the six declared trios, compared against
    the committed rows' margins in count units. The favorable partial
    replicate (144 vs 113) is cited as favorable-partial and inherits
    nothing; member 0 must reproduce the committed census exactly
    (discrete counts, same seeds, same law — determinism owes an exact
    integer)."""
    from apps.pipeline.services import palette_powder_rigs as GR

    raw_path = Path(raw_path or (SPREADS / "raw_glitter.json"))
    raw = json.loads(raw_path.read_text())
    table = json.loads(Path(table_path).read_text())

    counts = [int(r["census"]["GLITTER"]["event_count"])
              for r in raw["rows"]]
    controls = [int(r["census"]["MATTE_CONTROL"]["event_count"])
                for r in raw["rows"]]
    shimmer = [int(r["census"]["SHIMMER"]["event_count"])
               for r in raw["rows"]]
    areas = [float(r["census"]["GLITTER"]["median_event_area_px"])
             for r in raw["rows"]]

    event_row = _find_row(table, "GLITTER event PASS")
    control_row = _find_row(table, "glitter control cleanliness")
    if counts[0] != int(event_row["reading"]):
        raise AdjudicationError(
            f"member-0 GLITTER count {counts[0]} does not reproduce the "
            f"committed reading {event_row['reading']} — refusing")
    if controls[0] != int(control_row["reading"]):
        raise AdjudicationError(
            f"member-0 control count {controls[0]} does not reproduce "
            f"the committed reading {control_row['reading']} — refusing")

    def spread(vals):
        return max(abs(a - b) for i, a in enumerate(vals)
                   for b in vals[i + 1:])

    area_bar = GR.MIN_RESOLVABLE_PARTICLE_PX ** 2 * 0.5
    event_spread = spread(counts)
    control_spread = spread(controls)
    all_discrete = all(c >= GR.GLITTER_MIN_EVENTS for c in counts)
    all_ctl_quiet = all(c <= GR.CONTROL_MAX_EVENTS for c in controls)
    all_shimmer_continuous = all(c <= GR.CONTROL_MAX_EVENTS
                                 for c in shimmer)
    all_areas_resolve = all(a >= area_bar for a in areas)

    acts = []
    for row, sp, ok, detail in (
            (event_row, event_spread,
             all_discrete and float(event_row["margin"]) > event_spread,
             f"counts {counts}, every member >= "
             f"{GR.GLITTER_MIN_EVENTS}"),
            (control_row, control_spread,
             all_ctl_quiet and float(control_row["margin"])
             > control_spread,
             f"controls {controls}, every member <= "
             f"{GR.CONTROL_MAX_EVENTS}")):
        prior = {k: row.get(k) for k in
                 ("spread", "spread_source", "status", "note")}
        identity = VI.mint({
            "row": row["verdict"],
            "member_counts": counts if row is event_row else controls,
            "trio_seeds": [r["trio_seeds"] for r in raw["rows"]],
            "spread": sp,
            "source_record": raw_path.name,
        })
        row["spread"] = sp
        row["spread_source"] = ("DIRECT: 6-member declared event-"
                                f"ensemble trios ({raw_path.name})")
        if ok:
            row["status"] = "ESTABLISHED"
            row["note"] = (f"established {ADJUDICATION_DATE}: {detail}; "
                           f"margin {row['margin']} > replicate spread "
                           f"{sp} [cleared_against={identity}]")
        else:
            row["status"] = "ADEQUACY_PRECONDITION_UNMET_DIRECT"
            row["note"] = (f"honest FAIL {ADJUDICATION_DATE}: {detail}; "
                           f"margin {row['margin']} <= spread {sp} "
                           f"[cleared_against={identity}]")
        row["superseded_" + ADJUDICATION_DATE.replace("-", "_")] = prior
        acts.append({"row": row["verdict"], "spread": sp,
                     "new_status": row["status"],
                     "prior_row_state": prior,
                     "cleared_against": identity})

    established = (event_row["status"] == "ESTABLISHED"
                   and control_row["status"] == "ESTABLISHED"
                   and all_shimmer_continuous and all_areas_resolve)
    pair_identity = VI.mint({
        "pair": "SHIMMER_VS_GLITTER",
        "glitter_counts": counts, "controls": controls,
        "shimmer_counts": shimmer, "median_areas": areas,
        "source_record": raw_path.name,
    })
    if established:
        line = (
            f"ESTABLISHED — event ensemble measured at the declared six "
            f"trios: GLITTER counts {counts} (all >= "
            f"{GR.GLITTER_MIN_EVENTS}, replicate spread {event_spread} <"
            f" margin {event_row['margin']}); controls {controls} and "
            f"SHIMMER {shimmer} all quiet at every member; median event "
            f"areas {areas} all resolve (bar {area_bar}); both census "
            f"axes clear at every member — the favorable partial "
            f"replicate is cited as favorable-partial and inherited "
            f"nothing [cleared_against={pair_identity}; restated "
            f"{ADJUDICATION_DATE}]")
    else:
        line = (
            f"NOT ESTABLISHED — event row {event_row['status']}, "
            f"control row {control_row['status']}, shimmer continuous "
            f"{all_shimmer_continuous}, areas resolve "
            f"{all_areas_resolve} [restated {ADJUDICATION_DATE}]")
    table["pair_level_status_downstream_consultation_point"][
        "GLITTER_RIG"] = line

    record = {
        "record_type": "m6_spreads_adjudication_glitter/1.0",
        "adjudicated": ADJUDICATION_DATE,
        "raw_record": raw_path.name,
        "member_counts": {"GLITTER": counts, "MATTE_CONTROL": controls,
                          "SHIMMER": shimmer, "median_areas": areas},
        "acts": acts,
        "pair_level_lines_restated": {"GLITTER_RIG": line},
        "law": ("replicate spread = max pairwise |delta| across the "
                "declared members (A289's measure in the census's own "
                "count units); adequacy = committed margin > spread; "
                "census law thresholds unchanged; member 0 reproduced "
                "the committed census exactly"),
        "owner_approved": False,
    }
    if write:
        (SPREADS / "adjudication_glitter.json").write_text(
            json.dumps(record, indent=1) + "\n")
        Path(table_path).write_text(json.dumps(table, indent=1) + "\n")
    return record


#: flake-row grammar: (table row, axis, family_a, family_b, mode)
#: mode "reproduce" = member 0 must reproduce the committed reading
#: (both member-0 seeds are the canonical recorded pair seeds);
#: mode "rebase" = the historical reading's seed is unrecorded, so the
#: row re-bases on the declared member 0 — new terms, inheriting
#: nothing (glitter_flake_member_set_declaration.json).
FLAKE_ROWS = (
    ("S_V_M PATTERN clearing", "REFLECTED_PATTERN_CONTRAST",
     "SHIMMER", "POWDER_METALLIC", "reproduce"),
    ("S_V_M COHERENCE clearing", "REFLECTION_COHERENCE",
     "SHIMMER", "POWDER_METALLIC", "reproduce"),
    ("S_V_M ENV clearing", "ENVIRONMENT_CORRELATION",
     "SHIMMER", "POWDER_METALLIC", "reproduce"),
    ("MvG PATTERN clearing", "REFLECTED_PATTERN_CONTRAST",
     "POWDER_METALLIC", "GLITTER", "rebase"),
    ("MvG ENV clearing", "ENVIRONMENT_CORRELATION",
     "POWDER_METALLIC", "GLITTER", "rebase"),
)


def adjudicate_flake(raw_path=None, table_path=TABLE, write=True) -> dict:
    """Flake-rig rows adjudicated from the ensemble record: per-member
    clearings under each axis's OWN declared kind (relative or
    absolute, palette_flake_rig._axis_effect), dispersion under A289's
    max-pairwise-|delta| measure, adequacy = margin > dispersion.
    Pair lines are NOT restated here — the A4 independence discharge
    is the act that finishes the flake pairs, and it follows."""
    from apps.pipeline.services import palette_characterization_protocol \
        as PR
    from apps.pipeline.services import palette_flake_rig as FR

    raw_path = Path(raw_path or (SPREADS / "raw_flake.json"))
    raw = json.loads(raw_path.read_text())
    table = json.loads(Path(table_path).read_text())

    def member_axis(fam, axis):
        return {r["member"]: float(r["axes"][axis])
                for r in raw["members"][fam]}

    acts = []
    for verdict, axis, fam_a, fam_b, mode in FLAKE_ROWS:
        spec_row = PR.REFLECTIVE_AXES[axis]
        va, vb = member_axis(fam_a, axis), member_axis(fam_b, axis)
        per_member = {k: FR._axis_effect(spec_row, va[k], vb[k])
                      for k in sorted(va)}
        if len(per_member) < 2:
            raise AdjudicationError(f"{verdict}: fewer than two members")
        vals = [per_member[k] for k in sorted(per_member)]
        dispersion = max(abs(a - b) for i, a in enumerate(vals)
                         for b in vals[i + 1:])
        row = _find_row(table, verdict)
        prior = {k: row.get(k) for k in
                 ("reading", "margin", "spread", "spread_source",
                  "status", "note")}
        m0 = per_member[0]
        if mode == "reproduce":
            if abs(m0 - float(row["reading"])) > READING_TOLERANCE:
                raise AdjudicationError(
                    f"{verdict}: member-0 clearing {m0:.6f} does not "
                    f"reproduce the committed reading {row['reading']}")
            reading, margin = float(row["reading"]), float(row["margin"])
        else:
            reading = round(m0, 5)
            margin = round(reading - float(row["threshold"]), 5)
            row["reading"], row["margin"] = reading, margin
        clears_bar = reading >= float(row["threshold"])
        adequate = margin > dispersion
        identity = VI.mint({
            "row": verdict, "axis": axis, "kind": spec_row["kind"],
            "per_member_clearings": {str(k): round(v, 6)
                                     for k, v in per_member.items()},
            "member_seeds": {
                str(k): [raw["members"][fam_a][k]["seed"],
                         raw["members"][fam_b][k]["seed"]]
                for k in per_member},
            "dispersion": round(dispersion, 6),
            "source_record": raw_path.name,
        })
        row["spread"] = round(dispersion, 5)
        row["spread_source"] = (
            f"DIRECT: 6-member declared flake ensembles "
            f"({raw_path.name}), axis kind {spec_row['kind']}, A289 "
            "max-pairwise-|delta| dispersion")
        rebase_note = (" — re-based on declared member 0, new terms, "
                       "inheriting nothing" if mode == "rebase" else "")
        if clears_bar and adequate:
            row["status"] = "ESTABLISHED"
            row["note"] = (
                f"established {ADJUDICATION_DATE} by direct ensemble "
                f"measurement{rebase_note}: margin {margin} > "
                f"dispersion {dispersion:.5f} "
                f"[cleared_against={identity}]")
        else:
            if clears_bar:
                row["status"] = "ADEQUACY_PRECONDITION_UNMET_DIRECT"
                why = (f"margin {margin} <= dispersion "
                       f"{dispersion:.5f}")
            else:
                row["status"] = "NOT_ESTABLISHED_BELOW_BAR_DIRECT"
                why = (f"reading {reading} below the bar "
                       f"{row['threshold']}")
            row["note"] = (f"honest FAIL {ADJUDICATION_DATE}: {why}"
                           f"{rebase_note} [cleared_against={identity}]")
        row["superseded_" + ADJUDICATION_DATE.replace("-", "_")] = prior
        acts.append({
            "row": verdict, "axis": axis, "mode": mode,
            "per_member_clearings": per_member,
            "dispersion": dispersion, "reading": reading,
            "margin": margin, "clears_bar": clears_bar,
            "adequacy_precondition_met": adequate,
            "prior_row_state": prior, "new_status": row["status"],
            "cleared_against": identity,
        })

    record = {
        "record_type": "m6_spreads_adjudication_flake/1.0",
        "adjudicated": ADJUDICATION_DATE,
        "raw_record": raw_path.name,
        "acts": acts,
        "pair_lines": "NOT restated here — the A4 independence "
                      "discharge finishes the flake pairs in its own "
                      "act",
        "law": ("per-member clearing under each axis's declared kind "
                "(palette_flake_rig._axis_effect); dispersion = A289 "
                "max pairwise |delta|; adequacy = margin > dispersion; "
                "MvG rows re-based per "
                "glitter_flake_member_set_declaration.json"),
        "owner_approved": False,
    }
    if write:
        (SPREADS / "adjudication_flake.json").write_text(
            json.dumps(record, indent=1) + "\n")
        Path(table_path).write_text(json.dumps(table, indent=1) + "\n")
    return record


def _spearman(xs, ys):
    """Spearman rho via average ranks + Pearson on ranks — no SciPy."""
    def ranks(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        r = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while (j + 1 < len(order)
                   and vals[order[j + 1]] == vals[order[i]]):
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx <= 0 or vy <= 0:
        raise AdjudicationError(
            "degenerate rank variance — refusing a plausible rho")
    return cov / (vx * vy) ** 0.5


#: the flake pairs' counted axes, from the committed rig records
COUNTED_AXES = {
    "SHIMMER_VS_METALLIC": ("REFLECTED_PATTERN_CONTRAST",
                            "REFLECTION_COHERENCE",
                            "ENVIRONMENT_CORRELATION"),
    "METALLIC_VS_GLITTER": ("REFLECTED_PATTERN_CONTRAST",
                            "ENVIRONMENT_CORRELATION"),
}
INDEPENDENCE_CEILING = 0.80
#: table row per (pair, axis)
FLAKE_ROW_OF = {
    ("SHIMMER_VS_METALLIC", "REFLECTED_PATTERN_CONTRAST"):
        "S_V_M PATTERN clearing",
    ("SHIMMER_VS_METALLIC", "REFLECTION_COHERENCE"):
        "S_V_M COHERENCE clearing",
    ("SHIMMER_VS_METALLIC", "ENVIRONMENT_CORRELATION"):
        "S_V_M ENV clearing",
    ("METALLIC_VS_GLITTER", "REFLECTED_PATTERN_CONTRAST"):
        "MvG PATTERN clearing",
    ("METALLIC_VS_GLITTER", "ENVIRONMENT_CORRELATION"):
        "MvG ENV clearing",
}


def a4_discharge(raw_path=None, table_path=TABLE, write=True) -> dict:
    """A4 — independence discharged by the programme's sweep precedent
    on the completed ensembles: Spearman |rho| between each flake
    pair's counted axes, measured across the 18 declared flake ensemble
    member-measurements, against the unmoved 0.80 ceiling, with the
    fitted-population bound declared at use. Measured, not argued.
    Restates the two flake pair lines from the rows in place."""
    raw_path = Path(raw_path or (SPREADS / "raw_flake.json"))
    raw = json.loads(raw_path.read_text())
    table = json.loads(Path(table_path).read_text())

    population = []
    for fam in sorted(raw["members"]):
        for r in raw["members"][fam]:
            population.append((fam, r["seed"], r["axes"]))
    n = len(population)
    axes_needed = sorted({a for pair in COUNTED_AXES.values()
                          for a in pair})
    series = {a: [p[2][a] for p in population] for a in axes_needed}

    matrix = {}
    for i, a in enumerate(axes_needed):
        for b in axes_needed[i + 1:]:
            matrix[f"{a}|{b}"] = round(_spearman(series[a], series[b]),
                                       5)

    lines = {}
    rulings = {}
    for pair, counted in COUNTED_AXES.items():
        leg_status = {}
        for axis in counted:
            row = _find_row(table, FLAKE_ROW_OF[(pair, axis)])
            leg_status[axis] = row["status"]
        established = [a for a, s in leg_status.items()
                       if str(s).startswith("ESTABLISHED")]
        rhos = {}
        for i, a in enumerate(established):
            for b in established[i + 1:]:
                key = f"{a}|{b}" if f"{a}|{b}" in matrix else f"{b}|{a}"
                rhos[key] = matrix[key]
        independent = all(abs(v) <= INDEPENDENCE_CEILING
                          for v in rhos.values())
        ok = len(established) >= 2 and independent
        identity = VI.mint({
            "pair": pair, "counted": list(counted),
            "leg_status": leg_status, "rhos": rhos,
            "population": f"N={n} flake ensemble member-measurements",
            "ceiling": INDEPENDENCE_CEILING,
            "source_record": raw_path.name,
        })
        rulings[pair] = {
            "counted_axes": list(counted),
            "leg_status": leg_status,
            "established_counted": established,
            "abs_spearman_among_established": rhos,
            "independence_discharged": independent,
            "pair_established": ok,
            "cleared_against": identity,
        }
        legs_txt = "; ".join(f"{a}: {s}" for a, s in leg_status.items())
        if rhos:
            rho_txt = ", ".join(f"{k}={v}" for k, v in rhos.items())
        else:
            rho_txt = "none computable"
        if ok:
            line = (
                f"ESTABLISHED — {len(established)} counted axes "
                f"established ({', '.join(established)}) with "
                f"independence DISCHARGED by measurement: |rho| "
                f"{rho_txt} vs ceiling {INDEPENDENCE_CEILING} across "
                f"the declared N={n} flake-ensemble population "
                f"(POPULATION_BOUND: the three flake families' declared "
                f"members; binds nothing outside it); {legs_txt} "
                f"[cleared_against={identity}; restated "
                f"{ADJUDICATION_DATE} by the A4 discharge act]")
        else:
            est_txt = ", ".join(established) if established else "none"
            line = (
                f"NOT ESTABLISHED — established counted axes: "
                f"{est_txt}; independence "
                f"{'discharged' if independent else 'NOT discharged'} "
                f"({rho_txt}); {legs_txt} [restated "
                f"{ADJUDICATION_DATE} by the A4 discharge act]")
        key = ("SHIMMER_VS_METALLIC" if pair == "SHIMMER_VS_METALLIC"
               else "METALLIC_VS_GLITTER")
        table["pair_level_status_downstream_consultation_point"][key] \
            = line
        lines[key] = line

    record = {
        "record_type": "m6_a4_independence_discharge/1.0",
        "adjudicated": ADJUDICATION_DATE,
        "raw_record": raw_path.name,
        "population_bound": (
            f"N={n}: the three flake families' declared ensemble "
            "member-measurements (SHIMMER FLOOR_SEEDS, "
            "METALLIC_ENSEMBLE_SEEDS, GLITTER_FLAKE_ENSEMBLE_SEEDS) — "
            "fitted population declared at use, binds nothing outside "
            "it"),
        "ceiling": INDEPENDENCE_CEILING,
        "abs_spearman_matrix": matrix,
        "rulings": rulings,
        "pair_level_lines_restated": lines,
        "crossing_rescue": ("VOID constraint cited, not re-derived: "
                            "this act grows no diffuse census; the "
                            "0.6571 pre-commitment concerns "
                            "GRANULARITY x lobe on the diffuse pairs "
                            "and stands untriggered"),
        "owner_approved": False,
    }
    if write:
        (SPREADS / "a4_independence_discharge.json").write_text(
            json.dumps(record, indent=1) + "\n")
        Path(table_path).write_text(json.dumps(table, indent=1) + "\n")
    return record


if __name__ == "__main__":
    import os
    import sys

    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    if sys.argv[1] == "a4":
        rec = a4_discharge()
        for pair, r in rec["rulings"].items():
            print(f"{pair}: established_counted="
                  f"{r['established_counted']} rhos="
                  f"{r['abs_spearman_among_established']} -> "
                  f"{'ESTABLISHED' if r['pair_established'] else 'NOT'}")
        raise SystemExit(0)
    if sys.argv[1] == "flake":
        rec = adjudicate_flake()
        for act in rec["acts"]:
            print(f"{act['row']}: reading {act['reading']} disp "
                  f"{act['dispersion']:.5f} vs margin {act['margin']} "
                  f"-> {act['new_status']}")
        raise SystemExit(0)
    if sys.argv[1] == "glitter":
        rec = adjudicate_glitter()
        for act in rec["acts"]:
            print(f"{act['row']}: spread {act['spread']} -> "
                  f"{act['new_status']}")
        print(rec["pair_level_lines_restated"]["GLITTER_RIG"][:200])
        raise SystemExit(0)
    rec = adjudicate(sys.argv[1])
    for act in rec["acts"]:
        print(f"{act['row']}: dispersion "
              f"{act['clearing_dispersion']:.5f} vs margin "
              f"{act['margin']} -> {act['new_status']}")
    for f in rec["findings"]:
        print(f"{f['row']}: {f['finding']} ({f['statistic']})")
