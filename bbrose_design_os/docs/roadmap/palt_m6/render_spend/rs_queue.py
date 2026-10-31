"""M6-RECALIBRATION-EXECUTE queue — the committed runner (never a
scratchpad artifact; the A91 lesson). Executes the amended spend
declaration (combined_render_spend_declaration/1.2, 64 min / 80 max)
EXACTLY: composition is the declaration's, only the order is the
runner's.

First act per A98/2o: begin_traced_queue — the deliberate control
firing stamped into the ledger before frame one; every save routes
through assert_process_controlled. Resumable at unit boundaries; a
resumed process emits its own control. Cap 80 enforced. Ends by
writing the 2l/2r reconciliation evidence consumed by the analysis.
Solved energies are committed AS THEMSELVES with their iteration
lists per 2q, each iteration under its own label so no intermediate
state is overwritten.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()

from apps.pipeline.services import palette_queue_control as QC

RS = "docs/roadmap/palt_m6/render_spend"
TXDIR = os.path.join(RS, "frames_tx")
LOBEDIR = os.path.join(RS, "frames_lobe")
GLDIR = os.path.join(RS, "frames_gl")
LEDGER = os.path.join(RS, "queue_ledger.json")
RESULTS = os.path.join(RS, "queue_results.json")
MASK_SRC = "docs/roadmap/palt_m6/texture_axes/_region_mask.json"
CAP = 80

for d in (TXDIR, LOBEDIR, GLDIR):
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, "_region_mask.json")
    if not os.path.exists(dst):
        shutil.copyfile(MASK_SRC, dst)  # zero mask renders, declared

led = json.load(open(LEDGER)) if os.path.exists(LEDGER) else {
    "frames_rendered": 0, "done": [], "units": {}}
res = json.load(open(RESULTS)) if os.path.exists(RESULTS) else {
    "record_type": "recalibration_execute_results/1.0",
    "protocol_identity": "ef4c4dd7baf072ee",
    "recal": {}, "ct_texture": {}, "energy_ctl": {}, "lobe": {},
    "p5": {}, "p6": {}, "floor_frames": {}, "refusals": []}

# FIRST ACT — A98: prove the trace live in THIS process, stamp the
# ledger, before any import can fire a wired site in anger. A159: the
# governing declaration's identity travels in the stamp.
import hashlib

_DECL_ID = hashlib.sha256(
    open(os.path.join(RS, "spend_declaration.json"), "rb").read()
).hexdigest()[:16]
QC.begin_traced_queue("rs_queue", os.path.join(RS, "firing_trace.jsonl"),
                      led, _DECL_ID)
json.dump(led, open(LEDGER, "w"), indent=1)

from apps.pipeline.services import palette_characterization_rig as CR
from apps.pipeline.services import palette_energy_recovery as ER
from apps.pipeline.services import palette_powder_engine as PE
from apps.pipeline.services import palette_powder_protocol as PP
from apps.pipeline.services import palette_powder_rigs as PR
from apps.pipeline.services import palette_powder_texture_axes as TX

SHADE = PE.PowderShade("prov_char_neutral", (0.62, 0.55, 0.48),
                       PE.PROVISIONAL_VISUALIZATION_SHADE)
CSHADE = PE.PowderShade("prov_census_neutral", (0.62, 0.55, 0.48),
                        PE.PROVISIONAL_VISUALIZATION_SHADE)
WARM = PE.PowderShade("prov_dark_warm_sienna", (0.38, 0.22, 0.14),
                      PE.PROVISIONAL_VISUALIZATION_SHADE)
RECAL = (("SHIMMER", PP.SHIMMER), ("POWDER_METALLIC", PP.POWDER_METALLIC),
         ("BAKED", PP.BAKED), ("MARBLED", PP.MARBLED))
DOWN, UP, RETRY = 0.39773, 1.04545, 1.02273
#: A114 named three axes; the committed instrument admits TWO — the
#: autocorrelation axis was WITHDRAWN by the marbling repair (R3,
#: measure_texture_axes docstring). The premise divergence is recorded
#: and adjudication over the corrected set is DEFERRED to the owner;
#: this run renders and ledgers control frames without stamping.
AXES_ADMITTED = ("GRANULARITY_INDEX", "GRAZING_BAND_CONTRAST")
CTL_BAR = 0.125


def flush():
    json.dump(led, open(LEDGER, "w"), indent=1)
    json.dump(res, open(RESULTS, "w"), indent=1)


def save(tag, n, unit):
    QC.assert_process_controlled(led)
    led["frames_rendered"] += n
    led["done"].append(tag)
    if unit not in led["units"]:
        led["units"][unit] = 0
    led["units"][unit] += n
    if led["frames_rendered"] > CAP:
        flush()
        raise RuntimeError(f"CAP {CAP} EXCEEDED at {tag} — owner "
                           "ruling required BEFORE further frames")
    flush()
    print(f"[rs {led['frames_rendered']}/{CAP}] {tag}", flush=True)


def done(tag):
    return tag in led["done"]


def planar(d):
    pl = d["regions"]["PLANAR"]
    return float(pl["scene_linear_peak"]), int(pl["clipped_sample_count"])


TIDX = CR.region_indices(TXDIR)


def tx_axes(d, spec):
    # A558/3aa — the spec is now REQUIRED here: a measurement that
    # cannot name the family and seed it read raises rather than
    # returning a number. UNEXERCISED in the node that made this
    # change; render authority was not revived to run it.
    frame = TX.load_scene_linear(d["exr"], family=spec.family,
                                 seed=spec.seed, measurement=d)
    TX.region_alignment_assertion(frame, TIDX, d)
    return TX.measure_texture_axes(frame, TIDX)


# ---- unit 1: recalibration, per family, seed 700, 2q ----------------
for fam_name, fam_key in RECAL:
    tag = f"recal_{fam_name}"
    if done(tag):
        continue
    spec = PE.PowderMaterialSpec(fam_key, SHADE, seed=700)
    ref = PR.glitter_rig_overrides()["specular_source"]["energy"]
    d = TX._render_at(spec, TXDIR, f"rsprobe_{fam_name}", ref, samples=32)
    probe_peak, _pc = planar(d)
    d = TX._render_at(spec, TXDIR, f"rsbase_{fam_name}", 0.0, samples=32)
    base_peak, _bc = planar(d)
    if base_peak >= TX.SUBJECT_WINDOW[1]:
        raise TX.TextureAxisError(f"{fam_name}: base alone exceeds window")
    energy, peak, iterations = ref, probe_peak, []
    for i in range(4):
        spec_contrib = max(peak - base_peak, 1e-6)
        energy = energy * (TX.CAL_TARGET - base_peak) / spec_contrib
        d = TX._render_at(spec, TXDIR, f"rscal_{fam_name}_i{i + 1}",
                          energy, samples=32)
        peak, clip = planar(d)
        iterations.append({"energy": energy, "peak": peak,
                           "clipped": clip})
        if clip == 0 and TX.SUBJECT_WINDOW[0] <= peak <= TX.SUBJECT_WINDOW[1]:
            break
    else:
        raise TX.TextureAxisError(f"{fam_name}: did not converge: "
                                  f"{iterations}")
    res["recal"][fam_name] = {
        "energy_committed_as_itself_2q": energy,
        "iterations": iterations, "probe_peak": probe_peak,
        "base_peak": base_peak, "ref": ref, "seed": 700}
    save(tag, 2 + len(iterations), f"recal_{fam_name}")

RECAL_E = {fam: res["recal"][fam]["energy_committed_as_itself_2q"]
           for fam, _k in RECAL}
FAMS_CT = [("POWDER_MATTE", PP.POWDER_MATTE,
            ER.read_cached_energy("POWDER_MATTE")["energy"])] + \
          [(n, k, RECAL_E[n]) for n, k in RECAL]

# ---- unit 2: census-replicate texture rows --------------------------
for fam_name, fam_key, energy in FAMS_CT:
    if fam_name not in res["ct_texture"]:
        res["ct_texture"][fam_name] = {}
    for seed in (700, 701):
        tag = f"ctx_{fam_name}_{seed}"
        if done(tag):
            continue
        spec = PE.PowderMaterialSpec(fam_key, SHADE, seed=seed)
        d = TX._render_at(spec, TXDIR, f"ctx_{fam_name}_{seed}", energy,
                          samples=64)
        peak, clip = planar(d)
        row = {"energy": energy, "peak": peak, "clipped": clip,
               "material_identity": spec.material_identity()}
        if clip != 0 or peak < TX.SUBJECT_WINDOW[0]:
            row["REFUSED"] = ("clipped" if clip else "below window — a "
                              "measurement of darkness is not a "
                              "measurement")
            res["refusals"].append(f"ctx_{fam_name}_{seed}: "
                                   f"{row['REFUSED']}")
        else:
            row["axes"] = tx_axes(d, spec)
        res["ct_texture"][fam_name][str(seed)] = row
        save(tag, 1, f"ct_texture_{fam_name}")

# ---- unit 3: energy negative controls (A104/A115/A115b) -------------
# A114 adjudication is DEFERRED: the ruling names an axis the committed
# instrument withdrew (R3), so stamping over a corrected axis set waits
# for the owner. This unit renders and ledgers the declared control
# frames, applies only the pre-committed REFUSAL branches (down outside
# window; A115b second clip), and records achieved peaks as data.
def _reuse(label):
    meas = os.path.join(TXDIR, f"swatch_{label}.json")
    if not os.path.exists(meas):
        return None
    d = json.load(open(meas))
    d["exr"] = os.path.join(TXDIR, f"swatch_{label}.exr")
    return d


for fam_name, fam_key in RECAL:
    tag = f"ectl_{fam_name}"
    if done(tag):
        continue
    energy = RECAL_E[fam_name]
    spec = PE.PowderMaterialSpec(fam_key, SHADE, seed=700)
    entry = {"reference": "ctx seed-700 frame (shared, not re-rendered)",
             "offsets": {"down": DOWN, "up": UP}, "up_frames": [],
             "ADJUDICATION_DEFERRED_TO_OWNER": (
                 "A114 names SURFACE_AUTOCORRELATION_MM; the committed "
                 "instrument admits two axes (R3 withdrawal) — stamps "
                 "wait for the owner's ruling over the corrected set; "
                 "computable from these frames at zero render cost")}
    frames = 0
    d = _reuse(f"ectl_{fam_name}_down")
    if d is None:
        d = TX._render_at(spec, TXDIR, f"ectl_{fam_name}_down",
                          energy * DOWN, samples=64)
    frames += 1
    dpeak, dclip = planar(d)
    entry["down"] = {"peak": dpeak, "clipped": dclip}
    down_ok = dclip == 0 and dpeak >= TX.SUBJECT_WINDOW[0]
    if not down_ok:
        entry["down"]["REFUSED"] = "outside window — not a reading"
    d = _reuse(f"ectl_{fam_name}_up")
    if d is None:
        d = TX._render_at(spec, TXDIR, f"ectl_{fam_name}_up",
                          energy * UP, samples=64)
    frames += 1
    upeak, uclip = planar(d)
    entry["up_frames"].append({"peak": upeak, "clipped": uclip,
                               "factor": UP})
    if uclip != 0:
        d = _reuse(f"ectl_{fam_name}_up_retry")
        if d is None:
            d = TX._render_at(spec, TXDIR, f"ectl_{fam_name}_up_retry",
                              energy * RETRY, samples=64)
        frames += 1
        upeak, uclip = planar(d)
        entry["up_frames"].append({"peak": upeak, "clipped": uclip,
                                   "factor": RETRY})
    if uclip != 0:
        entry["FAMILY_STOPPED"] = ("second clip — stops the family and "
                                   "reports (A115b.4)")
        res["refusals"].append(f"ectl_{fam_name}: second clip")
    elif not down_ok:
        entry["FAMILY_TO_OWNER"] = ("down-frame refused — control did "
                                    "not clear; rows return (A104)")
        res["refusals"].append(f"ectl_{fam_name}: down refused")
    else:
        entry["achieved_peaks_pending_adjudication"] = [dpeak, upeak]
    res["energy_ctl"][fam_name] = entry
    save(tag, frames, f"energy_ctl_{fam_name}")

# ---- unit 4: lobe completion ---------------------------------------
for fam_name, fam_key in (("POWDER_SATIN", PP.POWDER_SATIN),
                          ("PRESSED_POWDER", PP.PRESSED_POWDER),
                          ("CREAM", PP.CREAM)):
    for seed in (700, 701):
        tag = f"lobe_{fam_name}_{seed}"
        if done(tag):
            continue
        spec = PE.PowderMaterialSpec(fam_key, SHADE, seed=seed)
        d = CR.characterize_powder(spec, LOBEDIR,
                                   label=f"lobe_{fam_name}_{seed}",
                                   samples=64)
        res["lobe"][f"{fam_name}_{seed}"] = {
            "axes": {k: v for k, v in CR.axes_from(d).items()
                     if not k.startswith("_")},
            "material_identity": spec.material_identity()}
        save(tag, 1, "ct_lobe_completion")

# ---- unit 5: P5 matte zero-particle controls ------------------------
GIDX = CR.region_indices(GLDIR)
greport = json.load(open(
    "docs/roadmap/palt_m6/glitter_particle_rig_report.json"))
genergy = greport["energy_calibration"]["calibrated_energy"]
gover = json.loads(json.dumps(PR.glitter_rig_overrides()))
gover["specular_source"]["energy"] = genergy
for seed in (67, 68):
    tag = f"p5ctl_{seed}"
    if done(tag):
        continue
    spec = PE.PowderMaterialSpec(PP.POWDER_MATTE, CSHADE, seed=seed)
    d = CR.characterize_powder(spec, GLDIR, label=f"p5ctl_{seed}",
                               overrides=gover, samples=64)
    c = PR.particle_census(d["exr"], GIDX)
    res["p5"][str(seed)] = {"event_count": c["event_count"],
                            "control_max": 5,
                            "clears": c["event_count"] <= 5}
    save(tag, 1, "p5_matte_zero_particle_controls")

# ---- unit 6: P6 C3-class positives ---------------------------------
P6_DIFFUSE = (("m_v_s", PP.POWDER_MATTE, PP.POWDER_SATIN,
               "SHEEN_REGION_RESPONSE"),
              ("p_v_m", PP.PRESSED_POWDER, PP.POWDER_MATTE,
               "SHEEN_REGION_RESPONSE"),
              ("s_v_c", PP.POWDER_SATIN, PP.CREAM, "HIGHLIGHT_FWHM"))
for pair, ka, kb, axis in P6_DIFFUSE:
    tag = f"p6_{pair}"
    if done(tag):
        continue
    vals = {}
    for k in (ka, kb):
        spec = PE.PowderMaterialSpec(k, WARM, seed=500)
        d = CR.characterize_powder(spec, LOBEDIR,
                                   label=f"p6_{pair}_{k}", samples=64)
        vals[k] = CR.axes_from(d)[axis]
    eff = TX._effect(vals[ka], vals[kb])
    res["p6"][pair] = {
        "counted_axis": axis, "a": vals[ka], "b": vals[kb],
        "relative_effect": eff, "bar": 0.25,
        "verdict": ("SENSITIVE_AT_WARM" if eff >= 0.25 else
                    "INSTRUMENT_NOT_VALIDATED_AT_CONDITION")}
    save(tag, 2, "p6_positive_controls")
tag = "p6_glitter"
if not done(tag):
    ev = {}
    for k, name in ((PP.GLITTER, "GLITTER"), (PP.POWDER_MATTE, "MATTE")):
        spec = PE.PowderMaterialSpec(k, WARM, seed=500)
        d = CR.characterize_powder(spec, GLDIR, label=f"p6_gl_{name}",
                                   overrides=gover, samples=64)
        ev[name] = PR.particle_census(d["exr"], GIDX)["event_count"]
    res["p6"]["glitter"] = {
        "glitter_events": ev["GLITTER"], "matte_events": ev["MATTE"],
        "verdict": ("SENSITIVE_AT_WARM"
                    if ev["GLITTER"] >= 25 and ev["MATTE"] <= 5 else
                    "INSTRUMENT_NOT_VALIDATED_AT_CONDITION")}
    save(tag, 2, "p6_positive_controls")

# ---- unit 7: floor-statistic replicate FRAMES ONLY ------------------
for fam_name, fam_key in (("POWDER_MATTE", PP.POWDER_MATTE),
                          ("POWDER_SATIN", PP.POWDER_SATIN),
                          ("CREAM", PP.CREAM)):
    for seed in (810, 811, 812, 813, 814, 815):
        tag = f"fr_{fam_name}_{seed}"
        if done(tag):
            continue
        spec = PE.PowderMaterialSpec(fam_key, SHADE, seed=seed)
        d = CR.characterize_powder(spec, LOBEDIR,
                                   label=f"fr_{fam_name}_{seed}",
                                   samples=64)
        res["floor_frames"][f"{fam_name}_{seed}"] = {
            "exr": d["exr"],
            "material_identity": spec.material_identity(),
            "note": "FRAMES ONLY — analysis is the next node's"}
        save(tag, 1, f"floor_replicate_{fam_name}")

# ---- unit 8: A122 down-frame re-derivation (M6-CONTROL-COMPLETION) --
# Executes ONLY the numbers the amended declaration states; inert
# until the a122 section exists. One retry per A115b/A122; a second
# refusal stops the family and reports.
DEC = json.load(open(os.path.join(RS, "spend_declaration.json")))
if "a122_down_rederivation" in DEC:
    A122 = DEC["a122_down_rederivation"]["lines"]
    for fam_name, fam_key in (("SHIMMER", PP.SHIMMER),
                              ("POWDER_METALLIC", PP.POWDER_METALLIC),
                              ("BAKED", PP.BAKED)):
        tag = f"down_redo_{fam_name}"
        if done(tag):
            continue
        line = A122[f"down_redo_{fam_name}"]
        energy = RECAL_E[fam_name]
        spec = PE.PowderMaterialSpec(fam_key, SHADE, seed=700)
        frames = 0
        d = TX._render_at(spec, TXDIR, f"dredo_{fam_name}",
                          energy * line["factor"], samples=64)
        frames += 1
        peak, clip = planar(d)
        attempts = [{"peak": peak, "clipped": clip,
                     "factor": line["factor"]}]
        ok = clip == 0 and peak >= TX.SUBJECT_WINDOW[0]
        if not ok:
            d = TX._render_at(spec, TXDIR, f"dredo_{fam_name}_retry",
                              energy * line["retry_factor"], samples=64)
            frames += 1
            peak, clip = planar(d)
            attempts.append({"peak": peak, "clipped": clip,
                             "factor": line["retry_factor"]})
            ok = clip == 0 and peak >= TX.SUBJECT_WINDOW[0]
        entry = res["energy_ctl"][fam_name]
        entry["down_redo_attempts"] = attempts
        if not ok:
            entry["FAMILY_STOPPED"] = ("second down refusal — stops "
                                       "the family and reports (A122)")
            res["refusals"].append(f"down_redo_{fam_name}: second "
                                   "refusal")
        else:
            down_ax = tx_axes(d, spec)
            up = _reuse(f"ectl_{fam_name}_up")
            up_frame = TX.load_scene_linear(up["exr"], family=spec.family,
                                            seed=spec.seed, measurement=up)
            TX.region_alignment_assertion(up_frame, TIDX, up)
            up_ax = TX.measure_texture_axes(up_frame, TIDX)
            up_peak = float(up["regions"]["PLANAR"]["scene_linear_peak"])
            ref = res["ct_texture"][fam_name]["700"]["axes"]
            entry["axes"] = {}
            gran_fail = False
            for axis in AXES_ADMITTED:
                ea = TX._effect(ref[axis], down_ax[axis])
                eb = TX._effect(ref[axis], up_ax[axis])
                clears = max(ea, eb) <= CTL_BAR
                entry["axes"][axis] = {
                    "shift_down": ea, "shift_up": eb, "bar": CTL_BAR,
                    "stamp": ("ENERGY_INVARIANT_AT_CONDITION" if clears
                              else "NOT_ENERGY_INVARIANT_AT_CONDITION"),
                    "reference_value": ref[axis],
                    "cleared_range": ([peak, up_peak] if clears
                                      else None)}
                if axis == "GRANULARITY_INDEX" and not clears:
                    gran_fail = True
            entry["SURFACE_AUTOCORRELATION_MM"] = (
                "DOES_NOT_EXIST — withdrawn per R3 (declared+"
                "adjudicated); read_stamped_axis raises on absence")
            entry["validated_range_achieved_peaks"] = [peak, up_peak]
            if "FAMILY_TO_OWNER" in entry:
                entry["FAMILY_TO_OWNER_SUPERSEDED"] = entry.pop(
                    "FAMILY_TO_OWNER") + " — superseded by the A122 "
                "re-derivation; row retained here per 2k"
            if gran_fail:
                entry["FAMILY_EXCLUDED"] = (
                    "GRANULARITY_INDEX not energy-invariant at "
                    "condition — rows return (A114 gate)")
            for seed in ("700", "701"):
                row = res["ct_texture"][fam_name][seed]
                inside = peak <= row["peak"] <= up_peak
                row["validated_range_check"] = (
                    "INSIDE" if inside else "OUTSIDE — to owner")
        save(tag, frames, f"down_redo_{fam_name}")

flush()
print("QUEUE COMPLETE at", led["frames_rendered"], "frames", flush=True)
