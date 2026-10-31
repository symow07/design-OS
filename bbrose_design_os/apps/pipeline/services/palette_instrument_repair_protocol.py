"""M6 §29 — the DECLARATION for the axis-instrument repair.

Written and hashed BEFORE any repair is implemented, per the same law
as palette_powder_protocol.py (identity 087c7f64317910fb, which this
declaration does not touch).

The evidence this repair answers to is
docs/roadmap/palt_m6/axis_instrument_defect_findings.json, findings
F1-F7, all of one class: a property DECLARED of the measurement chain
that is not true of the artifact actually measured, with no check that
could notice. M6 has already withdrawn two verdicts to this class.

WHAT THIS REPAIR MAY TOUCH
  the instrument: frame provenance, the reader, the three texture
  axes, the controls, and the assertions that guard them.

WHAT IT MAY NOT TOUCH — and does not
  * PASS_LAW: 2 independent axes at >= 25% relative effect. Unmoved.
  * the sub-rig validity windows [0.35, 0.92], max_clipped_samples 0.
  * SENSITIVITY_BAR 0.25 and EFFECT_BAR 0.25.
  * any powder family definition, milling block, compaction block or
    shader graph. The families stay FROZEN for the whole repair, so
    that no result can be a consequence of having tuned the subject.
  * protocol identity 087c7f64317910fb.

A repair that improved a family verdict by changing a family would
prove nothing. The subject is frozen precisely so the only thing that
can change is what we can SEE.
"""
from __future__ import annotations

import hashlib
import json

SCHEMA = "axis_instrument_repair_protocol/1.0"
VERSION = 1

FINDINGS_ANSWERED = ("F1_FRAME_PROVENANCE_16BIT_IS_8BIT",
                     "F2_ALPHA_CHANNEL_CONTAMINATES_LUMINANCE",
                     "F3_SURFACE_AUTOCORRELATION_MM_IS_DEAD_BY_CONSTRUCTION",
                     "F4_EDGE_HIGHLIGHT_RESPONSE_NOISE_FLOOR_EXCEEDS_THE_PASS_BAR",
                     "F5_AXES_ARE_NOT_INDEPENDENT_AS_THE_LAW_REQUIRES",
                     "F6_NO_STIMULUS_REALIZATION_CONTROL_EXISTS",
                     "F7_SILENT_ZERO_FALLBACKS_ARE_INDISTINGUISHABLE")

#: Nothing in here is a bar. These are the frozen inputs the repair
#: inherits and is forbidden from adjusting.
FROZEN = {
    "pass_law": {"required_independent_axes": 2,
                 "relative_effect_bar": 0.25,
                 "supporting_axes_never_count": True},
    "validity_window": [0.35, 0.92],
    "max_clipped_samples": 0,
    "powder_families": "FROZEN_FOR_THE_DURATION_OF_THE_REPAIR",
    "protocol_identity": "087c7f64317910fb",
}

# --------------------------------------------------------------------------
# R1..R6 — the repairs, each with the assertion that makes its defect
# impossible to reintroduce silently, and the negative control that
# proves the assertion can fail.
# --------------------------------------------------------------------------

REPAIRS = {
    "R1_MEASURE_FROM_SCENE_LINEAR": {
        "answers": ["F1", "F2"],
        "change": "every texture axis reads the float EXR the renderer "
                  "already writes, in scene-linear, RGB only. The 8-bit "
                  "and mislabelled '16bit' PNGs are demoted to human "
                  "review artifacts and are never a measurement input.",
        "why_not_just_fix_the_png": "a 16-bit PNG would still be "
                                    "display-encoded and quantised, and "
                                    "the EXR is already written on every "
                                    "render. Measuring the float frame "
                                    "removes the whole class instead of "
                                    "moving it one bit deeper.",
        "assertion": "FRAME_PROVENANCE_ASSERTION — before any axis is "
                     "computed, the loaded frame must be floating point "
                     "with >= 3 channels, and the loader refuses a "
                     "uint8 array. Alpha is dropped explicitly, never "
                     "averaged.",
        "negative_control": "hand the loader the existing 8-bit RGBA "
                            "frame and require that it RAISES. A guard "
                            "that cannot reject the artifact that caused "
                            "the defect is not a guard.",
    },

    "R2_STIMULUS_REALIZATION_GATE": {
        "answers": ["F6"],
        "change": "every fixture pair, in every study, computes a "
                  "frame-level difference between its two members BEFORE "
                  "any axis is evaluated. If the members are bit-"
                  "identical, or differ by less than the declared "
                  "realization floor, the pair reports "
                  "STIMULUS_NOT_REALIZED and NO relative effect is "
                  "recorded for it.",
        "declared_floor": {"metric": "rms difference over the measured "
                                     "region, normalised by the region "
                                     "mean of the low member",
                           "value": 0.002,
                           "rationale": "0.2% of the region mean is "
                                        "roughly one part in 500 — below "
                                        "any structure the axes claim to "
                                        "resolve, and far above the zero "
                                        "produced by a deterministic "
                                        "re-render of identical input. It "
                                        "is a realization floor, NOT a "
                                        "pass bar, and it is never "
                                        "compared against 0.25."},
        "assertion": "no axis result may be written for a pair whose "
                     "stimulus did not realize. 'detects: false' becomes "
                     "unreachable for an unrealized stimulus, which is "
                     "the exact false conclusion drawn at 927ab8a.",
        "negative_control": "an identical-spec pair must report "
                            "STIMULUS_NOT_REALIZED, not 'no axis "
                            "detects'.",
    },

    "R3_WITHDRAW_SURFACE_AUTOCORRELATION_MM": {
        "answers": ["F3"],
        "change": "the axis is WITHDRAWN. It correlates a field that a "
                  "3x3 box high-pass has just whitened, so it reports "
                  "its own kernel support (0.14 mm = 2 px) on every "
                  "frame ever measured. It is not admitted, not "
                  "repaired in place, and not counted toward any pair.",
        "replacement_status": "NONE_DECLARED_YET. Grain SCALE remains an "
                              "unmeasured quantity. No pair currently "
                              "depends on it, so M6 is not blocked by "
                              "its absence, and inventing a replacement "
                              "inside a repair would be a new axis "
                              "smuggled past its own declaration.",
        "assertion": "SYNTHETIC_FIELD_CONTROL — any future scale axis "
                     "must first recover a KNOWN correlation length from "
                     "a synthetic field, within a declared tolerance, "
                     "before it may look at a render.",
        "negative_control": "the withdrawn axis fails that synthetic "
                            "control. Recording that failure is what "
                            "makes the withdrawal evidence rather than "
                            "opinion.",
    },

    "R4_PER_AXIS_NOISE_FLOOR_BECOMES_A_PRECONDITION": {
        "answers": ["F4"],
        "change": "each axis acquires a MEASURED seed-only noise floor "
                  "from a same-family, same-parameter, seed-varied "
                  "ensemble. An axis whose noise floor is >= the 25% pass "
                  "bar is INELIGIBLE to carry a pair, and an axis's "
                  "clearing result must exceed its own floor by the "
                  "declared separation margin.",
        "declared_margin": {"value": 2.0,
                            "meaning": "a clearing effect must be at "
                                       "least 2x the axis's measured "
                                       "seed-only floor",
                            "rationale": "EDGE_HIGHLIGHT_RESPONSE "
                                         "measured 0.27991 on seed alone "
                                         "and was counted as a clearing "
                                         "axis at 0.3604 — 1.29x its own "
                                         "noise. A factor of 2 is the "
                                         "smallest margin under which "
                                         "that result would not have "
                                         "been banked."},
        "explicitly_not": "this does NOT raise the pass bar. The bar "
                          "stays 0.25 for every axis. This adds an "
                          "eligibility precondition on the INSTRUMENT, "
                          "in the same spirit as enlarging the light "
                          "source rather than lowering a threshold.",
        "assertion": "the ensemble is computed and stored per axis; a "
                     "ruling that uses an axis without a recorded floor "
                     "raises.",
        "negative_control": "re-running the ruling with EDGE_HIGHLIGHT_"
                            "RESPONSE's measured floor must FLIP "
                            "MATTE_vs_SATIN from PASS to FAIL. If it "
                            "does not, this repair did nothing and the "
                            "finding was wrong.",
    },

    "R5_INDEPENDENCE_BECOMES_MEASURED": {
        "answers": ["F5"],
        "change": "axis independence stops being a prose claim. Over the "
                  "family census, every axis pair gets a measured "
                  "correlation. Two axes correlated above the declared "
                  "ceiling may not BOTH count toward the same pair's "
                  "2-axis requirement; the pair must find its second "
                  "clearing axis elsewhere.",
        "declared_ceiling": {"metric": "absolute Spearman rank "
                                       "correlation across the measured "
                                       "family census",
                             "value": 0.80,
                             "rationale": "declared before the "
                                          "correlations are computed. "
                                          "Four of the six lobe axes are "
                                          "the same scalar on different "
                                          "regions; whether that makes "
                                          "them redundant is an "
                                          "empirical question this "
                                          "measurement answers, not one "
                                          "the docstring may answer."},
        "explicitly_not": "the law still requires 2 axes at 25%. This "
                          "makes the word 'independent' in that law "
                          "checkable instead of asserted.",
        "assertion": "a ruling that counts two axes above the ceiling "
                     "raises rather than passing.",
        "negative_control": "an axis correlated with itself must be "
                            "rejected by the ceiling — proving the check "
                            "can fire.",
    },

    "R6_NO_SILENT_FALLBACK_VALUES": {
        "answers": ["F7"],
        "change": "every degenerate branch that currently returns 0.0 "
                  "raises instead. A region with a zero median, a "
                  "variance below the numerical floor, or a correlation "
                  "that never crosses its threshold within the search "
                  "window is a refusal to measure, not a measurement of "
                  "zero.",
        "assertion": "the axis functions have no return path that "
                     "produces a number the caller cannot distinguish "
                     "from a real reading.",
        "negative_control": "a black region must raise, and the test "
                            "asserts the raise.",
    },
}

# --------------------------------------------------------------------------
# the exit condition for the repair itself
# --------------------------------------------------------------------------

REPAIR_EXIT_CONDITIONS = (
    "every R1..R6 assertion exists and its negative control is recorded "
    "as having FAILED CORRECTLY — an assertion with no demonstrated "
    "failure mode does not count",
    "the axis sensitivity study is re-run on the repaired instrument "
    "with the families UNCHANGED, and its record carries the frozen "
    "family identities to prove they did not move",
    "the three diffuse pairs are re-ruled on the repaired instrument; "
    "whatever verdict results is recorded, PASS or FAIL",
    "MATTE_vs_SATIN's prior PASS is explicitly re-adjudicated and the "
    "prior record is superseded in place rather than deleted",
    "the GLITTER_PARTICLE_RIG census is re-measured from the EXR and "
    "its 87-event PASS is either confirmed or withdrawn",
    "texture_axes_validation.json is regenerated; the stale FAIL is "
    "superseded with its reason recorded",
    "the full canonical pytest suite passes, and the exit record is "
    "written externally with the git SHA pinned inside it — the suite "
    "does not verify itself",
    "owner_approved remains false; this repair may not approve itself",
)

NOT_ESTABLISHED_BY_THIS_REPAIR = (
    "any powder family verdict",
    "any owner acceptance",
    "manufacturing authority",
    "that the six lobe axes are sufficient — only whether they are "
    "eligible and independent",
)


def declaration() -> dict:
    return {
        "record_type": SCHEMA,
        "version": VERSION,
        "findings_answered": list(FINDINGS_ANSWERED),
        "frozen": FROZEN,
        "repairs": REPAIRS,
        "exit_conditions": list(REPAIR_EXIT_CONDITIONS),
        "not_established": list(NOT_ESTABLISHED_BY_THIS_REPAIR),
    }


def repair_identity() -> str:
    """Hash of the declaration. Any later edit to scope, bars, margins
    or controls moves this identity and is therefore visible."""
    payload = json.dumps(declaration(), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class RepairStatusError(RuntimeError):
    """The exit record is absent or does not evidence every condition."""


#: the external exit record this status function reads. The status is
#: DERIVED, never a literal: the module written to eliminate
#: "declared-but-unrealized" may not itself carry a hardcoded REALIZED
#: flag of either polarity — a literal False outlives the repair and a
#: literal True outlives the next regression equally silently.
EXIT_RECORD = ("docs/roadmap/palt_m6/instrument_repair_exit.json")


def repair_status(exit_record_path=None) -> dict:
    from pathlib import Path
    path = Path(__file__).resolve().parents[3] / (
        exit_record_path or EXIT_RECORD)
    realized = False
    exit_sha = None
    if path.exists():
        record = json.loads(path.read_text())
        conditions = record.get("exit_conditions") or {}
        missing = [c for c in REPAIR_EXIT_CONDITIONS
                   if c not in conditions]
        unevidenced = [
            c for c, row in conditions.items()
            if not (row.get("evidence")
                    and row.get("satisfied") is True)]
        if missing or unevidenced:
            raise RepairStatusError(
                f"exit record present but incomplete — missing "
                f"{len(missing)}, unevidenced {len(unevidenced)}: "
                f"{(missing + unevidenced)[:3]}")
        if record.get("repair_identity") != repair_identity():
            raise RepairStatusError(
                "exit record was written against a different repair "
                "declaration — the identity moved")
        realized = True
        exit_sha = record.get("git_sha")
    return {
        "DECLARED": True,
        "REALIZED": realized,
        "realized_evidence": str(path) if realized else None,
        "exit_record_sha": exit_sha,
        "repair_identity": repair_identity(),
        "protocol_identity_unchanged": FROZEN["protocol_identity"],
        "families_frozen": True,
        "bars_moved": [],
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }
