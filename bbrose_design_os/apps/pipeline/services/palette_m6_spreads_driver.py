"""M6-SPREADS-EXECUTION driver — renders the declared ensembles, records
raw per-member clearings, and REFUSES to adjudicate.

Seed authority, in order: member_set_resolution.json (families resolved
from records at 93f0202) + the M6-ENSEMBLE-CONVENTION-DECLARATION
constants pinned in the instruments at 4aac8bc. Nothing here re-derives
either; a family whose member set is not determined by those two
sources is reported BLOCKED, never guessed (the glitter FLAKE ensemble
is the known instance — the event ensemble is pinned, a flake member
set for GLITTER is not).

WHAT THIS DRIVER DELIBERATELY DOES NOT DO: establishment-row
supersession and leg verdicts. The strict ruling's leg grammar
(adequacy preconditions, what establishes a clearing) belongs to the
establishment machinery and is executed in its own step reading these
raw measurements — measurement and adjudication stay separate acts, so
a context boundary between them costs nothing and improvises no law.

Queue law honoured: the first act names the campaign declaration's
identity, computed from the COMMITTED bytes (git show HEAD:path), so
the declaration cannot drift after declaration. Spend ceiling 80 per
the declaration; the driver counts pair-runs against it and refuses
past the ceiling.

Phases, in declared order (run one per invocation, commit between):
  sc         — SATIN_VS_CREAM, 6 member-pairs (texture rig)
  mvs_sheen  — MATTE_VS_SATIN SHEEN leg, 6 member-pairs
  pvm_sheen  — PRESSED_VS_MATTE SHEEN leg, 6 member-pairs
  mg         — METALLIC_VS_GLITTER (BLOCKED unless GLITTER flake
               members resolve from flake records — reported, not
               guessed)
  glitter    — the declared event ensemble (6 trio members)
  a4         — independence discharge on the completed ensembles
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs" / "roadmap" / "palt_m6" / "declared_spreads"
FRAMES = REPO.parent / "var" / "m6" / "spreads_frames"  # scratch, NOT_A_RECORD (A403); the one var/ since 2026-10-04
DECLARATION_RELPATH = ("bbrose_design_os/docs/roadmap/palt_m6/"
                       "declared_spreads/spreads_campaign_declaration.json")
CEILING = 80


class SpreadsDriverError(RuntimeError):
    pass


def declaration_identity() -> str:
    """Identity of the COMMITTED declaration bytes — drift-proof."""
    blob = subprocess.run(
        ["git", "show", f"HEAD:{DECLARATION_RELPATH}"],
        capture_output=True, cwd=REPO)
    if blob.returncode != 0:
        raise SpreadsDriverError(
            "cannot read the committed declaration from git — the queue "
            "may not start against an uncommitted work order")
    return hashlib.sha256(blob.stdout).hexdigest()[:16]


def _texture_members(family):
    from apps.pipeline.services import palette_powder_texture_axes as TA
    if family == "POWDER_MATTE":
        rec = json.loads(
            (REPO / "docs/roadmap/palt_m6/axis_noise_floors.json")
            .read_text())
        ens = rec["ensemble"]
        if ens["family"] != "POWDER_MATTE":
            raise SpreadsDriverError("noise-floor ensemble is not MATTE's")
        return tuple(ens["seeds"])
    if family in TA.ENSEMBLE_SEEDS_BY_FAMILY:
        return tuple(TA.ENSEMBLE_SEEDS_BY_FAMILY[family])
    raise SpreadsDriverError(
        f"no member set for {family} in the two seed authorities — "
        "BLOCKED, not guessed")


def _spent() -> int:
    ledger_path = OUT / "spreads_queue_ledger.json"
    if not ledger_path.exists():
        return 0
    ledger = json.loads(ledger_path.read_text())
    if "pair_runs_spent" in ledger:
        return int(ledger["pair_runs_spent"])
    return 0


def _record_spend(n, ledger):
    ledger["pair_runs_spent"] = _spent() + n
    (OUT / "spreads_queue_ledger.json").write_text(
        json.dumps(ledger, indent=1))


def _begin_queue(phase):
    from apps.pipeline.services import palette_queue_control as QC
    ledger_path = OUT / "spreads_queue_ledger.json"
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text())
    else:
        ledger = {}
    if (OUT / f"raw_{phase}.json").exists():
        raise SpreadsDriverError(
            f"phase {phase} already has its raw record — completed; "
            "re-execution is forbidden, resume at the next phase")
    trace = OUT / f"spreads_firing_trace_{phase}.jsonl"
    if trace.exists():
        # crashed attempt: control landed but the phase never wrote its
        # record. Rotate the dead trace aside (never delete) so the new
        # queue's control is the file's FIRST act — the fcd1d11 lesson.
        n = 1
        while (OUT / f"spreads_firing_trace_{phase}_superseded_{n}"
               ".jsonl").exists():
            n += 1
        trace.rename(OUT / f"spreads_firing_trace_{phase}_superseded_{n}"
                     ".jsonl")
    stamp = QC.begin_traced_queue(
        f"m6_spreads_{phase}", str(trace), ledger, declaration_identity())
    return ledger, stamp


def run_texture_pair_phase(phase, fam_a, fam_b) -> dict:
    """One leg-ensemble: 6 calibrated member-pairs, raw clearings only."""
    from apps.pipeline.services import palette_powder_engine as PE
    from apps.pipeline.services import palette_powder_texture_axes as TA

    members_a = _texture_members(fam_a)
    members_b = _texture_members(fam_b)
    if _spent() + 6 > CEILING:
        raise SpreadsDriverError(
            f"phase {phase} would exceed the declared ceiling {CEILING} "
            f"(spent {_spent()}) — refusing; spend is declared, not elastic")

    ledger, stamp = _begin_queue(phase)
    FRAMES.mkdir(parents=True, exist_ok=True)
    shade = PE.PowderShade("prov_char_neutral", (0.62, 0.55, 0.48),
                           "PROVISIONAL_VISUALIZATION_SHADE")
    rows = []
    for i, (sa, sb) in enumerate(zip(members_a, members_b)):
        out_dir = FRAMES / phase / f"member_{i}"
        out_dir.mkdir(parents=True, exist_ok=True)
        pair = TA.characterize_texture_pair(
            PE.PowderMaterialSpec(fam_a, shade, seed=sa),
            PE.PowderMaterialSpec(fam_b, shade, seed=sb),
            str(out_dir),
            label_a=f"{phase}_m{i}_{fam_a}", label_b=f"{phase}_m{i}_{fam_b}")
        rows.append({"member": i, "seed_a": sa, "seed_b": sb,
                     "pair_report": pair})
        print(f"{phase} member {i} landed (seeds {sa}/{sb})", flush=True)
    _record_spend(6, ledger)

    rec = {
        "record_type": f"m6_spreads_raw_measurements_{phase}/1.0",
        "phase": phase, "families": [fam_a, fam_b],
        "members_a": list(members_a), "members_b": list(members_b),
        "queue_control_stamp": stamp,
        "declaration_identity": declaration_identity(),
        "rows": rows,
        "adjudication": "DEFERRED BY DESIGN — raw measurements only; the "
                        "establishment machinery adjudicates in its own "
                        "act reading this record",
        "owner_approved": False,
    }
    (OUT / f"raw_{phase}.json").write_text(json.dumps(
        rec, indent=1, default=str) + "\n")
    return rec


LOBE_FAMILIES = ("POWDER_MATTE", "POWDER_SATIN", "CREAM",
                 "PRESSED_POWDER")


def run_lobe_ensemble_phase() -> dict:
    """The SHEEN/FWHM legs' own instrument: per-member swatches on the
    characterization (lobe) rig, raw axes only — measure, never
    adjudicate. Declared in sheen_fwhm_instrument_resolution.json
    BEFORE this ran; 24 member-measurements counted (harder than the
    texture phases' per-pair unit — the ceiling cannot be snuck past).
    """
    from apps.pipeline.services import palette_characterization_rig as CR
    from apps.pipeline.services import palette_powder_engine as PE

    members = {fam: _texture_members(fam) for fam in LOBE_FAMILIES}
    n = sum(len(v) for v in members.values())
    if _spent() + n > CEILING:
        raise SpreadsDriverError(
            f"lobe phase would exceed the declared ceiling {CEILING} "
            f"(spent {_spent()}, +{n}) — refusing; spend is declared, "
            "not elastic")

    ledger, stamp = _begin_queue("lobe")
    shade = PE.PowderShade("prov_char_neutral", (0.62, 0.55, 0.48),
                           "PROVISIONAL_VISUALIZATION_SHADE")
    out = {}
    for fam, seeds in members.items():
        out_dir = FRAMES / "lobe" / fam
        out_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for k, seed in enumerate(seeds):
            spec = PE.PowderMaterialSpec(fam, shade, seed=seed)
            d = CR.characterize_powder(
                spec, str(out_dir), label=f"lobe_{fam}_m{k}_s{seed}")
            clipped = int(d["frame"]["clipped_sample_count"])
            if clipped:
                raise SpreadsDriverError(
                    f"lobe member {fam} m{k} (seed {seed}) clipped "
                    f"{clipped} samples — the rig window failed; "
                    "refusing to record a clipped measurement")
            axes = CR.normalized(CR.axes_from(d))
            rows.append({
                "member": k, "seed": seed,
                # discriminate()'s own input: normalized axes
                # (normalization touches HIGHLIGHT_PEAK only)
                "axes": {a: axes[a] for a in axes
                         if not a.startswith("_")},
                "material_identity": spec.material_identity(),
                "render_identity": d.get("render_identity"),
                "exr": d["exr"],
                "scene_linear_peak": d["frame"]["scene_linear_peak"],
                "clipped_sample_count": clipped,
            })
            print(f"lobe {fam} member {k} landed (seed {seed})",
                  flush=True)
        out[fam] = rows
    _record_spend(n, ledger)

    rec = {
        "record_type": "m6_spreads_raw_lobe/1.0",
        "phase": "lobe",
        "instrument": "DIFFUSE_LOBE_RIG (palette_characterization_rig."
                      "characterize_powder; axes_from + normalized — "
                      "discriminate()'s own input)",
        "resolution_record": "sheen_fwhm_instrument_resolution.json",
        "members": out,
        "member_seeds": {fam: list(s) for fam, s in members.items()},
        "queue_control_stamp": stamp,
        "declaration_identity": declaration_identity(),
        "adjudication": "DEFERRED BY DESIGN — raw measurements only; the "
                        "establishment machinery adjudicates in its own "
                        "act reading this record",
        "owner_approved": False,
    }
    (OUT / "raw_lobe.json").write_text(json.dumps(
        rec, indent=1, default=str) + "\n")
    return rec


def run_glitter_event_phase() -> dict:
    """The declared glitter EVENT ensemble: the census trio re-measured
    at the six member indices pinned in GLITTER_EVENT_ENSEMBLE (member =
    one trio, per the pinned convention's own wording). Measure-only —
    event counts recorded raw, adjudication deferred to the machinery.

    Calibration is the rig's OWN law executed verbatim at the member-0
    trio seeds (measured-brightest candidate, base-off peak, the
    E_{n+1} = E_n * (target - base) / peak fixed-point, clip guard) —
    reimplemented here rather than imported so the committed instrument
    module's bytes (hashed into standing provenance identities) are not
    touched. The census law itself IS imported: particle_census,
    unchanged.
    """
    from apps.pipeline.services import palette_characterization_rig as CR
    from apps.pipeline.services import palette_powder_engine as PE
    from apps.pipeline.services import palette_powder_protocol as PP
    from apps.pipeline.services import palette_powder_rigs as GR

    trios = [tuple(t) for t in GR.GLITTER_EVENT_ENSEMBLE]
    if _spent() + len(trios) > CEILING:
        raise SpreadsDriverError(
            f"glitter phase would exceed the ceiling {CEILING} "
            f"(spent {_spent()}, +{len(trios)}) — refusing")

    ledger, stamp = _begin_queue("glitter")
    out_dir = FRAMES / "glitter_event"
    out_dir.mkdir(parents=True, exist_ok=True)
    shade = PE.PowderShade("prov_census_neutral", (0.62, 0.55, 0.48),
                           PE.PROVISIONAL_VISUALIZATION_SHADE)

    g0, m0, s0 = trios[0]
    glitter_spec = PE.PowderMaterialSpec(PP.GLITTER, shade, seed=g0)
    particle_px = (glitter_spec.params["particles"]["particle_size_mm"]
                   * GR.PX_PER_MM)
    if particle_px < GR.MIN_RESOLVABLE_PARTICLE_PX:
        raise SpreadsDriverError(
            f"declared particle {particle_px:.1f}px does not resolve — "
            "fix the rig, not the powder")

    idx = CR.region_indices(str(out_dir))
    overrides = GR.glitter_rig_overrides()

    renders = 0
    candidates = {}
    for fam, seed in ((PP.SHIMMER, s0), (PP.GLITTER, g0)):
        d = CR.characterize_powder(
            PE.PowderMaterialSpec(fam, shade, seed=seed), str(out_dir),
            label=f"energy_ref_{fam}", overrides=overrides, samples=64)
        candidates[fam] = float(
            d["regions"]["PLANAR"]["scene_linear_peak"])
        renders += 1
    bright_fam = max(candidates, key=candidates.get)
    bright_seed = s0 if bright_fam == PP.SHIMMER else g0
    bright_spec = PE.PowderMaterialSpec(bright_fam, shade,
                                        seed=bright_seed)
    peak = candidates[bright_fam]
    base_over = json.loads(json.dumps(overrides))
    base_over["specular_source"]["energy"] = 0.0
    base = CR.characterize_powder(bright_spec, str(out_dir),
                                  label="energy_base",
                                  overrides=base_over, samples=64)
    renders += 1
    base_peak = float(base["regions"]["PLANAR"]["scene_linear_peak"])
    if base_peak >= 0.92:
        raise SpreadsDriverError(
            f"base lighting alone peaks at {base_peak} — no compact "
            "energy can bring the rig into the window")
    ref_energy = overrides["specular_source"]["energy"]
    energy = ref_energy
    iterations = []
    for _ in range(4):
        energy = energy * (0.92 - base_peak) / max(peak, 0.92)
        it = CR.characterize_powder(
            bright_spec, str(out_dir), label="energy_iteration",
            overrides={**json.loads(json.dumps(overrides)),
                       "specular_source":
                       {**overrides["specular_source"],
                        "energy": energy}},
            samples=64)
        renders += 1
        pl = it["regions"]["PLANAR"]
        peak = float(pl["scene_linear_peak"])
        iterations.append({"energy": energy, "peak": peak,
                           "clipped": pl["clipped_sample_count"]})
        if pl["clipped_sample_count"] == 0 and peak <= 0.92:
            break
    else:
        raise SpreadsDriverError(
            f"calibration did not converge in 4 iterations: {iterations}")
    overrides = json.loads(json.dumps(overrides))
    overrides["specular_source"]["energy"] = energy
    calibration = {"reference_energy": ref_energy,
                   "calibration_fixture": f"{bright_fam} (measured "
                                          f"brightest of {candidates})",
                   "base_peak_specular_off": base_peak,
                   "target_linear": 0.92,
                   "iterations": iterations,
                   "calibrated_energy": energy,
                   "law": "E_{n+1} = E_n * (target - base_peak) / "
                          "peak_n — the rig's own law, verbatim"}

    rows = []
    for k, (gs, ms, ss) in enumerate(trios):
        census = {}
        for label, family, seed in (
                ("GLITTER", PP.GLITTER, gs),
                ("MATTE_CONTROL", PP.POWDER_MATTE, ms),
                ("SHIMMER", PP.SHIMMER, ss)):
            spec = PE.PowderMaterialSpec(family, shade, seed=seed)
            d = CR.characterize_powder(
                spec, str(out_dir), label=f"census_{label}_m{k}",
                overrides=overrides, samples=64)
            renders += 1
            pl = d["regions"]["PLANAR"]
            if pl["clipped_sample_count"]:
                raise SpreadsDriverError(
                    f"{label} m{k} clipped after calibration — the "
                    "calibration itself failed; refusing")
            c = GR.particle_census(
                d["exr"], idx,
                event_map_path=str(out_dir / f"event_map_{label}_m{k}"
                                   ".png"),
                annotate_source=d["png"])
            census[label] = {
                "seed": seed,
                "event_count": c["event_count"],
                "median_event_area_px": c["median_event_area_px"],
                "scene_linear_peak": pl["scene_linear_peak"],
                "material_identity": spec.material_identity(),
            }
        rows.append({"member": k, "trio_seeds": [gs, ms, ss],
                     "census": census})
        print(f"glitter trio member {k} landed (seeds {gs}/{ms}/{ss}): "
              f"G={census['GLITTER']['event_count']} "
              f"C={census['MATTE_CONTROL']['event_count']} "
              f"S={census['SHIMMER']['event_count']}", flush=True)
    _record_spend(len(trios), ledger)

    rec = {
        "record_type": "m6_spreads_raw_glitter/1.0",
        "phase": "glitter",
        "instrument": "GLITTER_PARTICLE_RIG (palette_powder_rigs."
                      "particle_census, law untouched); calibration = "
                      "the rig's own fixed-point law at member-0 seeds",
        "ensemble": [list(t) for t in trios],
        "ensemble_authority": "palette_powder_rigs.GLITTER_EVENT_"
                              "ENSEMBLE pinned at 4aac8bc",
        "predeclared": {
            "GLITTER_MIN_EVENTS": GR.GLITTER_MIN_EVENTS,
            "CONTROL_MAX_EVENTS": GR.CONTROL_MAX_EVENTS,
            "EVENT_LUMINANCE_FACTOR": GR.EVENT_LUMINANCE_FACTOR,
            "EVENT_MIN_AREA_PX": GR.EVENT_MIN_AREA_PX,
            "EVENT_MAX_AREA_PX": GR.EVENT_MAX_AREA_PX,
        },
        "energy_calibration": calibration,
        "renders_this_phase": renders,
        "rows": rows,
        "queue_control_stamp": stamp,
        "declaration_identity": declaration_identity(),
        "adjudication": "DEFERRED BY DESIGN — raw event counts only; "
                        "the establishment machinery adjudicates in its "
                        "own act reading this record; the favorable "
                        "partial replicate (144 vs 113) is NOT evidence "
                        "and inherits nothing",
        "owner_approved": False,
    }
    (OUT / "raw_glitter.json").write_text(json.dumps(
        rec, indent=1, default=str) + "\n")
    return rec


def run_flake_ensemble_phase() -> dict:
    """The flake-rig ensembles: SHIMMER (FLOOR_SEEDS, record-resolved),
    POWDER_METALLIC (4aac8bc) and GLITTER (glitter_flake_member_set_
    declaration.json) — 18 member-measurements serving the S_V_M
    PATTERN completion and both MvG legs. Measure-only: reflective axes
    recorded raw per member against the same-series mirror reference;
    the rig's own validity gates (mirror contrast, subject peak, zero
    clipping) enforced per render; adjudication deferred.
    """
    from apps.pipeline.services import (
        palette_characterization_protocol as PR,
        palette_flake_rig as FR,
    )

    members = {
        "SHIMMER": tuple(FR.FLOOR_SEEDS),
        "POWDER_METALLIC": tuple(FR.METALLIC_ENSEMBLE_SEEDS),
        "GLITTER": tuple(FR.GLITTER_FLAKE_ENSEMBLE_SEEDS),
    }
    n = sum(len(v) for v in members.values())
    if _spent() + n > CEILING:
        raise SpreadsDriverError(
            f"flake phase would exceed the ceiling {CEILING} "
            f"(spent {_spent()}, +{n}) — refusing")

    ledger, stamp = _begin_queue("flake")
    out_dir = FRAMES / "flake_ensembles"
    out_dir.mkdir(parents=True, exist_ok=True)

    mirror = PR.measure_under(PR.REFLECTIVE_MATERIAL_RIG,
                              PR.MIRROR_REFERENCE_SPEC, str(out_dir),
                              "flake_mirror_reference", samples=48)
    v = PR.REFLECTIVE_MATERIAL_RIG["validity"]
    mirror_contrast = PR.grid_pattern_contrast(
        PR._region_grid(mirror, "PLANAR"))
    if mirror_contrast < v["mirror_reference_min_pattern_contrast"] or \
            PR._clipped_subject(mirror) > 0:
        raise SpreadsDriverError(
            f"mirror commissioning failed: contrast {mirror_contrast}")

    out = {}
    for fam, seeds in members.items():
        rows = []
        for k, seed in enumerate(seeds):
            d = FR._measure(fam, seed, str(out_dir),
                            f"flake_{fam}_m{k}_s{seed}", samples=48)
            # loud membership filter, never a silent-zero default —
            # max() raises on an empty sequence, which is the refusal
            peaks = [float(reg["scene_linear_peak"])
                     for reg in d["regions"].values()
                     if "scene_linear_peak" in reg]
            peak = max(peaks)
            if peak < v["min_subject_peak_scene_linear"]:
                raise SpreadsDriverError(
                    f"{fam} m{k} peak {peak:.4f} below the declared "
                    "window — refusing")
            if PR._clipped_subject(d) > 0:
                raise SpreadsDriverError(f"{fam} m{k} clipped — refused")
            axes = PR.reflective_axes(d, mirror)
            rows.append({
                "member": k, "seed": seed,
                "axes": {a: float(axes[a]) for a in axes
                         if not str(a).startswith("_")},
                "subject_peak": round(peak, 6),
            })
            print(f"flake {fam} member {k} landed (seed {seed})",
                  flush=True)
        out[fam] = rows
    _record_spend(n, ledger)

    rec = {
        "record_type": "m6_spreads_raw_flake/1.0",
        "phase": "flake",
        "instrument": "FLAKE_REFLECTION_RIG (palette_flake_rig._measure "
                      "+ palette_characterization_protocol."
                      "reflective_axes against the same-series mirror "
                      "reference; axis kinds per REFLECTIVE_AXES)",
        "mirror_pattern_contrast": round(mirror_contrast, 6),
        "members": out,
        "member_seeds": {fam: list(s) for fam, s in members.items()},
        "seed_authorities": {
            "SHIMMER": "FLOOR_SEEDS — record-resolved at 93f0202",
            "POWDER_METALLIC": "METALLIC_ENSEMBLE_SEEDS @ 4aac8bc",
            "GLITTER": "GLITTER_FLAKE_ENSEMBLE_SEEDS @ "
                       "glitter_flake_member_set_declaration.json",
        },
        "off_declaration_use": "GLITTER on this rig cites the SOUND USE "
                               "ruling (metallic_vs_glitter_reflective"
                               ".json); its validity conditions "
                               "(subject peak, zero clipping) are "
                               "re-measured per member above",
        "queue_control_stamp": stamp,
        "declaration_identity": declaration_identity(),
        "adjudication": "DEFERRED BY DESIGN — raw axes only; the "
                        "establishment machinery adjudicates in its own "
                        "act reading this record",
        "owner_approved": False,
    }
    (OUT / "raw_flake.json").write_text(json.dumps(
        rec, indent=1, default=str) + "\n")
    return rec


PHASES = {
    "sc": ("POWDER_SATIN", "CREAM"),
    "mvs_sheen": ("POWDER_MATTE", "POWDER_SATIN"),
    "pvm_sheen": ("PRESSED_POWDER", "POWDER_MATTE"),
}


if __name__ == "__main__":
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    OUT.mkdir(parents=True, exist_ok=True)
    phase = sys.argv[1]
    if phase == "identity":
        print(declaration_identity())
    elif phase in PHASES:
        a, b = PHASES[phase]
        r = run_texture_pair_phase(phase, a, b)
        print(f"{phase} COMPLETE — 6 members, raw record written")
    elif phase == "lobe":
        r = run_lobe_ensemble_phase()
        print("lobe COMPLETE — 4 families x 6 members, raw record "
              "written")
    elif phase == "glitter":
        r = run_glitter_event_phase()
        print("glitter COMPLETE — 6 trio members, raw record written")
    elif phase == "flake":
        r = run_flake_ensemble_phase()
        print("flake COMPLETE — 3 families x 6 members, raw record "
              "written")
    elif phase == "mg":
        raise SpreadsDriverError(
            "METALLIC_VS_GLITTER rides in the 'flake' phase since "
            "2026-08-15: GLITTER_FLAKE_ENSEMBLE_SEEDS was declared in "
            "glitter_flake_member_set_declaration.json (the historical "
            "blocker — no member set in any record — is resolved by "
            "declaration, not by guessing); run phase 'flake'")
    else:
        raise SpreadsDriverError(f"unknown phase {phase!r}")
