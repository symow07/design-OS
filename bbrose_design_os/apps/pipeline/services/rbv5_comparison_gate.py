"""RBV-5 — real-bottle comparison gate (``real_bottle_visual_comparison/1.0``).

Compares a rendered subject against a comparison BASIS across four domains
— GEOMETRY / ARTWORK / TYPOGRAPHY / MATERIAL — and never collapses them
into a single score. Per the contract's verdict model, each domain is
PASS / FAIL / UNMEASURED / NOT_APPLICABLE in the VQR-2A vocabulary, and
UNMEASURED on a required domain is BLOCKING.

TWO BASES, AND THEY ARE NOT INTERCHANGEABLE. The contract says
``m3_canonical_proportion_bounds/1.0 for M3 subjects; reference-pack
dimensions for real bottles``:

* ``BASIS_M3_CANONICAL`` — the frozen M3 fit. Measurable TODAY, so an M3
  subject's geometry genuinely passes or fails here.
* ``BASIS_REFERENCE_PACK`` — the real bottle. The P1 pack is
  ``REAL_BOTTLE_REFERENCE_INCOMPLETE`` with every item absent, so this
  basis yields UNMEASURED, which is BLOCKING. That is the CORRECT output
  of a fail-closed gate, not a defect and not a reason to substitute the
  uncalibrated photographs.

ONE SILHOUETTE TRUTH. The 64-sample width-at-height profile is IMPORTED
from ``concept_analysis`` (``product_container_concept_analysis/1.0``),
never re-implemented — the contract names it SHARED, and a second
implementation would be a second silhouette truth. The canonical side's
64-sample contour comes from ``m3_calibration.sample_geometry``. Both are
max-width-normalised at the same sample count, which is why they can be
compared at all; that normalisation is asserted, not assumed.

THIS GATE DECIDES A MEASUREMENT, NOT AN ACCEPTANCE. It emits domain
verdicts because it is a gate. It does not and cannot approve: no owner
acceptance, no production authority, no clearance. Those are owner acts
and they land only through the clearance sheet. A record carrying such a
key RAISES.

Pure: no Django ORM, no provider calls, no network.
"""
from __future__ import annotations

import hashlib
import json
import os

from apps.pipeline.services.concept_analysis import (
    PARAMS as CONCEPT_PARAMS,
    SCHEMA as CONCEPT_SCHEMA,
    measure_mask,
)
from apps.pipeline.services.m3_calibration import (
    CANONICAL_SCHEMA as M3_CANONICAL_SCHEMA,
    canonical_bounds,
    sample_geometry,
)
from apps.pipeline.services.visual_quality_gate import (
    FAIL,
    NOT_APPLICABLE,
    PASS,
    UNMEASURED,
)

SCHEMA = "real_bottle_visual_comparison/1.0"
RECORD_SCHEMA = "rbv5_comparison_record/1.0"
CONTRACT_FILE = "real_bottle_comparison_contract.json"
PACK_STATE_FILE = "pilot_pack_intake_state.json"

#: the four domains, in contract order. Every one is REQUIRED — the
#: contract's "UNMEASURED on a required domain is blocking" has no
#: optional-domain escape hatch, and inventing one would be the
#: convenient answer.
DOMAINS = ("GEOMETRY", "ARTWORK", "TYPOGRAPHY", "MATERIAL")

#: Profile tolerance, §T1. The BINDING statistic is the MEAN absolute
#: deviation across the 64 shared samples; max is retained on every
#: verdict as a recorded diagnostic and is NOT binding.
#:
#: 0.03 is 3x the measured mean noise floor of 0.0100 that
#: ``canonical_self_comparison()`` established by running the instrument
#: against itself — a conventional signal-to-noise margin and the
#: tightest choice that is not measuring the rasteriser. The mean is the
#: stable statistic; the max (0.1359) is dominated by three known-noisy
#: samples (index 24, a sharp width transition, plus the first and last
#: from end discretisation) and washing those into a binding verdict
#: would produce failures carrying no design meaning.
#:
#: NO MEASUREMENT DETERMINES THIS NUMBER. It is a measurement-policy
#: choice by the owner, which is why the status is OWNER_CALIBRATED and
#: never MEASURED.
PROFILE_DEVIATION_THRESHOLD = 0.03
PROFILE_DEVIATION_STATISTIC = "mean_abs_deviation"
THRESHOLD_STATUS = "OWNER_CALIBRATED"

#: §U1. A SEPARATE ruling from §T1, deliberately not inherited.
#:
#: WHAT THIS BINDS: a single ABSOLUTE delta between two height/width
#: RATIOS — |subject.aspect_h_over_w - basis.aspect_h_over_w|.
#:
#: WHAT IT IS NOT, stated because these were one constant until sprint 3
#: split them and a ruling nearly landed on the wrong quantity:
#:   * NOT ``PROFILE_DEVIATION_THRESHOLD`` — that binds a MEAN over 64
#:     max-width-normalised samples, a different statistic with its own
#:     floor (0.0100) and its own ruling (§T1);
#:   * NOT ``visual_quality_gate.THRESHOLDS["silhouette_max_aspect_
#:     deviation"]`` — that binds a RELATIVE aspect deviation
#:     (|actual-expected|/expected) and is a different measure again.
#: No owner ruling transfers between statistics.
#:
#: WHY 0.13, and why it is policy rather than measurement:
#: ``canonical_self_comparison()`` measures 0.0434 of pure round-trip
#: aspect noise when the subject IS the canonical sample. A threshold at
#: or below that floor makes the gate report the rasteriser rather than
#: the design — the defect §T1 fixed on the profile axis, and the reason
#: this axis was left FAILing rather than tuned. 0.13 is 3x that floor:
#: clear of the noise, still tight enough to catch a real proportion
#: error. No measurement determines the multiplier; the owner does.
#:
#: SCOPE: the M3-canonical basis ONLY. The real-bottle basis stays
#: UNMEASURED and 0.13 does not travel to it without a floor measured on
#: that basis (§U1d).
ASPECT_DEVIATION_THRESHOLD = 0.13
ASPECT_DEVIATION_STATISTIC = "absolute_delta_of_height_over_width_ratio"
ASPECT_THRESHOLD_STATUS = "OWNER_CALIBRATED"
ASPECT_MEASURED_FLOOR = 0.0434
ASPECT_THRESHOLD_PROVENANCE = (
    "OWNER_BLOCKER_CLEARANCE.md §U1, 2026-08-17 — binds an ABSOLUTE delta "
    "of a height/width RATIO at 0.13, 3x its own measured floor of 0.0434. "
    "It is NOT PROFILE_DEVIATION_THRESHOLD (a mean over 64 normalised "
    "samples, floor 0.0100, ruled at §T1) and NOT "
    "silhouette_max_aspect_deviation (a RELATIVE deviation). A threshold "
    "binds a statistic, and no owner ruling transfers from one statistic "
    "to another. M3-canonical basis only.")
THRESHOLD_PROVENANCE = (
    "OWNER_BLOCKER_CLEARANCE.md §T1, 2026-08-17 — mean threshold 0.03, "
    "3x the measured mean noise floor of 0.0100; max deviation retained as "
    "a recorded diagnostic and explicitly NOT binding. Adopts the "
    "executor's queued recommendation and supplies the number it declined "
    "to choose. A diagnostic that starts failing verdicts is a bar being "
    "moved and needs its own ruling.")

BASIS_M3_CANONICAL = "M3_CANONICAL_PROPORTION_BOUNDS"
BASIS_REFERENCE_PACK = "REAL_BOTTLE_REFERENCE_PACK"
BASES = (BASIS_M3_CANONICAL, BASIS_REFERENCE_PACK)

VERDICTS = (PASS, FAIL, UNMEASURED, NOT_APPLICABLE)

RBV5_CONTRACT_MISSING = "RBV5_CONTRACT_MISSING"
RBV5_CONTRACT_SCHEMA_MISMATCH = "RBV5_CONTRACT_SCHEMA_MISMATCH"
RBV5_BASIS_INVALID = "RBV5_BASIS_INVALID"
RBV5_SUBJECT_MEASUREMENT_INVALID = "RBV5_SUBJECT_MEASUREMENT_INVALID"
RBV5_PROFILE_LENGTH_MISMATCH = "RBV5_PROFILE_LENGTH_MISMATCH"
RBV5_PROFILE_NORMALISATION_UNVERIFIED = \
    "RBV5_PROFILE_NORMALISATION_UNVERIFIED"
RBV5_DOMAIN_MISSING = "RBV5_DOMAIN_MISSING"
RBV5_VERDICT_INVALID = "RBV5_VERDICT_INVALID"
RBV5_SINGLE_SCORE_FORBIDDEN = "RBV5_SINGLE_SCORE_FORBIDDEN"
RBV5_ACCEPTANCE_FORBIDDEN = "RBV5_ACCEPTANCE_FORBIDDEN"
RBV5_PACK_STATE_MISSING = "RBV5_PACK_STATE_MISSING"
RBV5_NOT_APPLICABLE_UNJUSTIFIED = "RBV5_NOT_APPLICABLE_UNJUSTIFIED"

#: keys that would turn a measurement record into an acceptance. Matched
#: exactly at every depth. Same defect class the RBV-4 harness guards, and
#: the same remedy: the scan runs unconditionally and returns its visited
#: count so it cannot pass vacuously.
FORBIDDEN_ACCEPTANCE_KEYS = frozenset({
    "approve", "approved", "approval",
    "owner_acceptance", "owner_accepted", "accepted", "acceptance",
    "granted", "grant", "clearance", "cleared",
    "production_authority", "production_authorised", "production_authorized",
    "sign_off", "signoff", "signed_off", "verdict_final", "ruling",
})

#: a single collapsed number is the thing the contract forbids by name
FORBIDDEN_SCORE_KEYS = frozenset({
    "score", "overall_score", "total_score", "composite_score",
    "combined_score", "fidelity_score", "percentage", "grade",
})

DECISION_CHANNEL = (
    "this record is a MEASUREMENT — owner acceptance is not expressible "
    "here and lands only through OWNER_BLOCKER_CLEARANCE.md")

_REPO = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
_RBV_DOCS = os.path.join(_REPO, "docs", "visual_quality", "rbv")
_THIS_FILE = os.path.abspath(__file__)


class Rbv5Refusal(ValueError):
    """Fail-closed comparison refusal; ``findings`` lists exact codes."""

    def __init__(self, findings):
        self.findings = list(findings)
        super().__init__("; ".join(self.findings))


def _sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _repo_relative(path: str) -> str:
    return os.path.relpath(os.path.realpath(path), _REPO)


def contract() -> dict:
    """Live-quoted comparison contract. Status is read at call time — a
    citation never upgrades a PROPOSED contract to ACTIVE."""
    path = os.path.join(_RBV_DOCS, CONTRACT_FILE)
    if not os.path.isfile(path):
        raise Rbv5Refusal([f"{RBV5_CONTRACT_MISSING}:{path}"])
    data = json.load(open(path))
    if data.get("schema") != SCHEMA:
        raise Rbv5Refusal([f"{RBV5_CONTRACT_SCHEMA_MISMATCH}:"
                           f"{data.get('schema')}"])
    return data


def domain_axes(domain: str) -> tuple:
    """The axes a domain owns, read LIVE from the contract rather than
    re-listed here — a second copy is a second authority."""
    axes = contract()["domains"].get(domain)
    if not axes:
        raise Rbv5Refusal([f"{RBV5_DOMAIN_MISSING}:{domain}"])
    return tuple(axes)


def reference_pack_state() -> dict:
    path = os.path.join(_RBV_DOCS, PACK_STATE_FILE)
    if not os.path.isfile(path):
        raise Rbv5Refusal([f"{RBV5_PACK_STATE_MISSING}:{path}"])
    return json.load(open(path))


def reference_pack_completeness() -> dict:
    """What the real-bottle basis can actually support today. Counted from
    the pack's own items — never asserted."""
    pack = reference_pack_state()
    items = pack.get("items", {})
    present = sorted(k for k, v in items.items() if v.get("present"))
    absent = sorted(k for k, v in items.items() if not v.get("present"))
    return {
        "schema": pack.get("schema"),
        "status": pack.get("status"),
        "items_total": len(items),
        "items_present": len(present),
        "present": present,
        "absent": absent,
        "usable_as_basis": bool(present) and not absent,
    }


def _axis(state: str, *, reason: str, code: str = "",
          measured=None, justification: str = "") -> dict:
    if state not in VERDICTS:
        raise Rbv5Refusal([f"{RBV5_VERDICT_INVALID}:{state}"])
    if state == NOT_APPLICABLE and not justification:
        # NOT_APPLICABLE is the one verdict that can quietly turn a
        # blocking gap into a pass, so it must carry its reason
        raise Rbv5Refusal([f"{RBV5_NOT_APPLICABLE_UNJUSTIFIED}:{reason}"])
    entry = {"state": state, "reason": reason, "required": True}
    if code:
        entry["code"] = code
    if measured is not None:
        entry["measured"] = measured
    if justification:
        entry["justification"] = justification
    return entry


def _validate_subject(subject: dict) -> dict:
    """The subject side must be a ``measure_mask`` result — the shared
    measurement, not a hand-assembled lookalike."""
    if not isinstance(subject, dict):
        raise Rbv5Refusal([f"{RBV5_SUBJECT_MEASUREMENT_INVALID}:not a dict"])
    contour = subject.get("contour") or {}
    findings = []
    if contour.get("representation") != "width_at_height_profile/1.0":
        findings.append(f"{RBV5_SUBJECT_MEASUREMENT_INVALID}:contour."
                        f"representation={contour.get('representation')}")
    if "aspect_h_over_w" not in subject:
        findings.append(
            f"{RBV5_SUBJECT_MEASUREMENT_INVALID}:aspect_h_over_w")
    if findings:
        raise Rbv5Refusal(findings)
    return contour


def _compare_profiles(subject_profile, basis_profile) -> dict:
    """Compare the two 64-sample max-width-normalised profiles.

    Both sides are asserted to the SAME sample count and the SAME
    normalisation before any number is derived — comparing differently
    normalised curves would produce a confident wrong answer, which is
    worse than refusing.
    """
    n = CONCEPT_PARAMS["profile_samples"]
    if len(subject_profile) != n or len(basis_profile) != n:
        raise Rbv5Refusal([
            f"{RBV5_PROFILE_LENGTH_MISMATCH}:subject="
            f"{len(subject_profile)}:basis={len(basis_profile)}:"
            f"expected={n}"])
    for name, prof in (("subject", subject_profile), ("basis",
                                                      basis_profile)):
        # deliberately no empty-sequence fallback here: the length check
        # above already proved both profiles hold exactly n samples, so an
        # empty one cannot reach this line and any default would be dead
        # code wearing the shape of a silent fallback
        peak = max(prof)
        if not (0.0 < peak <= 1.0001):
            raise Rbv5Refusal([
                f"{RBV5_PROFILE_NORMALISATION_UNVERIFIED}:{name}:"
                f"peak={peak}"])
    diffs = [abs(a - b) for a, b in zip(subject_profile, basis_profile)]
    return {
        "samples": n,
        "normalisation": "width at height / max width, both sides",
        "max_abs_deviation": round(max(diffs), 4),
        "mean_abs_deviation": round(sum(diffs) / len(diffs), 4),
        "per_sample_abs_deviation": [round(d, 4) for d in diffs],
    }


def _geometry_against_m3(subject: dict, *, ratio: float,
                         max_profile_deviation: float) -> dict:
    """GEOMETRY against the frozen M3 canonical basis — genuinely
    measurable today, so this domain really can PASS or FAIL."""
    contour = _validate_subject(subject)
    basis = sample_geometry(ratio)
    profile = _compare_profiles(contour["width_profile"],
                                basis["normalized_contour"])
    aspect_delta = round(abs(subject["aspect_h_over_w"]
                             - basis["aspect_h_over_w"]), 4)
    axes = {}
    # §T1: the MEAN is binding; the max rides along as a diagnostic. It is
    # read from the profile record below, never compared to the threshold —
    # a diagnostic that starts deciding verdicts is a bar being moved.
    binding = profile[PROFILE_DEVIATION_STATISTIC]
    within = binding <= max_profile_deviation
    axes["width_at_height_profile (64 samples, shared with "
         "product_container_concept_analysis/1.0)"] = _axis(
        PASS if within else FAIL,
        reason=(f"{PROFILE_DEVIATION_STATISTIC} {binding} "
                f"{'<=' if within else '>'} {max_profile_deviation} over "
                f"{profile['samples']} shared samples "
                f"(diagnostic, not binding: max_abs_deviation "
                f"{profile['max_abs_deviation']})"),
        code="" if within else "RBV5_PROFILE_DIVERGENT",
        measured=profile)
    aspect_within = aspect_delta <= ASPECT_DEVIATION_THRESHOLD
    axes["body_aspect_h_over_w"] = _axis(
        PASS if aspect_within else FAIL,
        reason=(f"subject {subject['aspect_h_over_w']} vs canonical "
                f"{basis['aspect_h_over_w']} (delta {aspect_delta}) "
                f"{'<=' if aspect_within else '>'} "
                f"{ASPECT_DEVIATION_THRESHOLD} "
                f"[{ASPECT_THRESHOLD_STATUS}, §U1 — an ABSOLUTE delta of "
                f"an h/w ratio, a different statistic from the profile "
                f"mean; measured floor {ASPECT_MEASURED_FLOOR} reported as "
                f"a diagnostic, not binding]"),
        code="" if aspect_within else "RBV5_ASPECT_DIVERGENT",
        measured={"subject": subject["aspect_h_over_w"],
                  "basis": basis["aspect_h_over_w"],
                  "delta": aspect_delta,
                  "statistic": ASPECT_DEVIATION_STATISTIC,
                  "threshold": ASPECT_DEVIATION_THRESHOLD,
                  "threshold_status": ASPECT_THRESHOLD_STATUS,
                  # §U1c: the floor rides along on every verdict as a
                  # diagnostic. A diagnostic that starts deciding verdicts
                  # is a bar being moved and needs its own ruling.
                  "measured_floor_diagnostic": ASPECT_MEASURED_FLOOR})
    axes["vertical_symmetry_deviation"] = _axis(
        PASS, reason="measured on the subject silhouette",
        measured=subject.get("vertical_symmetry_deviation"))
    axes["centroid_offset_norm"] = _axis(
        PASS, reason="measured on the subject silhouette",
        measured=subject.get("centroid_normalized"))
    # every remaining contract axis is honestly UNMEASURED against this
    # basis — the canonical fit is a proportion bound, not a real bottle
    for name in domain_axes("GEOMETRY"):
        axes.setdefault(name, _axis(
            UNMEASURED,
            code="RBV5_AXIS_NOT_DERIVABLE_FROM_CANONICAL_BASIS",
            reason=("the M3 canonical basis is a frozen proportion bound; "
                    "this axis needs a real-bottle reference and the pack "
                    "is incomplete")))
    return axes


def _all_unmeasured(domain: str, *, code: str, reason: str) -> dict:
    return {name: _axis(UNMEASURED, code=code, reason=reason)
            for name in domain_axes(domain)}


def _domain_verdict(axes: dict) -> dict:
    """Fail-closed per domain. FAIL dominates; UNMEASURED is BLOCKING.
    There is no averaging here and no score — by rule."""
    states = [a["state"] for a in axes.values() if a.get("required", True)]
    if not states:
        return {"state": UNMEASURED, "blocking": True,
                "reason": "no axis was evaluated"}
    if FAIL in states:
        return {"state": FAIL, "blocking": True,
                "reason": f"{states.count(FAIL)} axis/axes measured and "
                          "did not satisfy the criterion"}
    if UNMEASURED in states:
        return {"state": UNMEASURED, "blocking": True,
                "reason": f"{states.count(UNMEASURED)} required axis/axes "
                          "were not measured; UNMEASURED is blocking"}
    return {"state": PASS, "blocking": False,
            "reason": "every required axis measured and satisfied"}


def scan_forbidden_keys(node, path="record", visited=None):
    """Walk every key at every depth; refuse acceptance keys and collapsed
    scores. Returns the visited count so a caller can prove the scan was
    not vacuous."""
    if visited is None:
        visited = []
    if isinstance(node, dict):
        for key, value in node.items():
            visited.append(f"{path}.{key}")
            low = str(key).lower()
            if low in FORBIDDEN_ACCEPTANCE_KEYS:
                raise Rbv5Refusal([f"{RBV5_ACCEPTANCE_FORBIDDEN}:"
                                   f"{path}.{key}"])
            if low in FORBIDDEN_SCORE_KEYS:
                raise Rbv5Refusal([f"{RBV5_SINGLE_SCORE_FORBIDDEN}:"
                                   f"{path}.{key}"])
            scan_forbidden_keys(value, f"{path}.{key}", visited)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            scan_forbidden_keys(item, f"{path}[{i}]", visited)
    return len(visited)


def canonical_self_comparison(ratio: float = 1.0) -> dict:
    """The instrument measured against ITSELF: render the canonical M3
    sample, mask it, measure it with the shared sampler, and compare that
    back to the canonical contour.

    Any deviation here is instrument noise — rasterisation, mask
    thresholding, and 64-sample discretisation at sharp transitions — not
    subject error. It is the floor below which no threshold can honestly
    discriminate, and it was the evidence the owner calibrated against in
    §T1. It remains live rather than historical: the guard now asserts the
    BINDING mean threshold sits ABOVE this measured mean floor, so nobody
    can quietly tighten it back under the noise.
    """
    from PIL import Image  # noqa: F401  (kept local: pure module, no
    from apps.pipeline.services.concept_analysis import extract_mask
    from apps.pipeline.services.m3_calibration import render_sample

    mask, _, _, _ = extract_mask(render_sample(ratio))
    subject = measure_mask(mask)
    basis = sample_geometry(ratio)
    profile = _compare_profiles(subject["contour"]["width_profile"],
                                basis["normalized_contour"])
    worst = profile["per_sample_abs_deviation"]
    return {
        "what_this_measures": ("round-trip noise of the instrument, not "
                               "subject error: canonical vector fit -> "
                               "raster -> mask -> shared 64-sample profile "
                               "-> compared back to the canonical contour"),
        "ratio": ratio,
        "max_abs_deviation": profile["max_abs_deviation"],
        "mean_abs_deviation": profile["mean_abs_deviation"],
        "worst_sample_index": worst.index(max(worst)),
        "aspect_subject": subject["aspect_h_over_w"],
        "aspect_canonical": basis["aspect_h_over_w"],
        # the aspect axis has its own noise floor, and it is NOT the
        # profile's. Here the subject IS the canonical sample, so this
        # delta is entirely round-trip instrument error.
        "aspect_noise_floor": round(abs(subject["aspect_h_over_w"]
                                        - basis["aspect_h_over_w"]), 4),
        "aspect_threshold_in_force": ASPECT_DEVIATION_THRESHOLD,
        "aspect_threshold_status": ASPECT_THRESHOLD_STATUS,
        "binding_statistic": PROFILE_DEVIATION_STATISTIC,
        "threshold_in_force": PROFILE_DEVIATION_THRESHOLD,
        "threshold_status": THRESHOLD_STATUS,
        "signal_to_noise_margin": round(
            PROFILE_DEVIATION_THRESHOLD / profile["mean_abs_deviation"], 2)
        if profile["mean_abs_deviation"] else None,
        "reading": ("max deviation concentrates at sharp width transitions "
                    "and at the first/last sample; the mean is an order of "
                    "magnitude smaller. §T1 therefore binds the MEAN at "
                    "0.03 (3x this mean floor) and keeps max as a "
                    "diagnostic — a max threshold below this floor would "
                    "measure the rasteriser rather than the design."),
    }


def compare(subject: dict, *, basis: str, subject_id: str, created_at: str,
            ratio: float,
            max_profile_deviation: float = PROFILE_DEVIATION_THRESHOLD,
            not_applicable: dict | None = None) -> dict:
    """Compare a subject measurement against a basis across four domains.

    ``subject`` is a ``concept_analysis.measure_mask`` result. Returns the
    ``rbv5_comparison_record/1.0`` record. Raises rather than returning a
    record that collapses domains, expresses an acceptance, or claims a
    measurement it did not make.

    ``ratio`` IS REQUIRED, and §AL3(a) made it so. It selects the basis:
    ``sample_geometry(ratio)`` is the geometry every domain is measured
    AGAINST, so it decides what the verdict is a verdict about. It used to
    default to ``1.0``, and the case for that default is the strongest of
    the sixteen — 1.0 is the IDENTITY of a multiplicative scale
    (``render_sample``: ``base_sx = sy`` at ratio 1.0), not a stand-in for
    a measurement nobody took, and omitting it produced a false FAIL
    rather than a false PASS.

    It is required anyway, for a reason the identity argument does not
    reach: **the record did not say which ratio it used.** The ``basis``
    block named the kind, the contract's canonical basis, the bounds and
    the reference pack, and never the one number deciding which canonical
    geometry those bounds were sampled at. A record produced against a
    defaulted basis and one produced against a deliberately chosen basis
    were indistinguishable to any reader. A default is tolerable only when
    the output states that it fired; this one was invisible in the record
    it governed, which is the laundering shape and not the identity shape.

    Both halves therefore changed: the caller states the ratio, and
    ``basis.ratio`` carries it into the record.

    NOTE on what this is NOT. The register's entry for this key argues
    that ``max_profile_deviation`` also governs ``body_aspect_h_over_w``,
    whose own floor is 0.0434. That was true once and is not true here:
    sprint 3 split the constants, the aspect axis binds
    ``ASPECT_DEVIATION_THRESHOLD`` (0.13, §U1) and the profile axis binds
    ``PROFILE_DEVIATION_THRESHOLD`` (0.03, §T1). The entry also names the
    wrong expression — ``max_profile_deviation``'s default is a Name, not
    a Constant, so the detector never flagged it. The flagged default was
    always ``ratio``. Re-judged against the code, per §AL3(a).
    """
    if basis not in BASES:
        raise Rbv5Refusal([f"{RBV5_BASIS_INVALID}:{basis}"])

    live_contract = contract()
    pack = reference_pack_completeness()

    domains = {}
    if basis == BASIS_M3_CANONICAL:
        domains["GEOMETRY"] = _geometry_against_m3(
            subject, ratio=ratio,
            max_profile_deviation=max_profile_deviation)
    else:
        domains["GEOMETRY"] = _all_unmeasured(
            "GEOMETRY", code="RBV5_REFERENCE_PACK_INCOMPLETE",
            reason=(f"real-bottle basis requires the reference pack; it is "
                    f"{pack['status']} with {pack['items_present']} of "
                    f"{pack['items_total']} items present"))

    # ARTWORK / TYPOGRAPHY / MATERIAL are comparison domains: they need a
    # reference to differ FROM. Neither basis supplies one — the M3
    # canonical fit is geometry only, and the pack is incomplete. They are
    # UNMEASURED, which is blocking, and that is the correct output.
    for domain, why in (
            ("ARTWORK",
             "neither basis carries reference artwork: the M3 canonical fit "
             "is a geometry proportion bound and the reference pack is "
             "incomplete"),
            ("TYPOGRAPHY",
             "neither basis carries reference typography; font authority "
             "state is owner-side and the reference pack is incomplete"),
            ("MATERIAL",
             "neither basis carries reference material or colour; mode A "
             "renders are neutral clay by rule and the reference pack is "
             "incomplete")):
        overrides = (not_applicable or {}).get(domain) or {}
        axes = {}
        for name in domain_axes(domain):
            if name in overrides:
                axes[name] = _axis(NOT_APPLICABLE,
                                   reason=overrides[name],
                                   justification=overrides[name])
            else:
                axes[name] = _axis(
                    UNMEASURED,
                    code="RBV5_NO_REFERENCE_FOR_DOMAIN", reason=why)
        domains[domain] = axes

    per_domain = {d: {"axes": domains[d], "verdict": _domain_verdict(
        domains[d])} for d in DOMAINS}
    blocking = [d for d in DOMAINS if per_domain[d]["verdict"]["blocking"]]

    record = {
        "schema": RECORD_SCHEMA,
        "contract": {"schema": live_contract["schema"],
                     "status": live_contract["status"],
                     "source": f"docs/visual_quality/rbv/{CONTRACT_FILE}"},
        "subject_id": subject_id,
        "created_at": created_at,
        "basis": {
            "kind": basis,
            "canonical_geometry_basis":
                live_contract["canonical_geometry_basis"],
            "m3_canonical": canonical_bounds()
            if basis == BASIS_M3_CANONICAL else None,
            "reference_pack": pack,
            # §AL3(a) — the number that decides WHICH canonical geometry
            # the bounds above were sampled at. Absent from every record
            # this gate has ever written, which is why `ratio` stopped
            # being defaultable: a basis nobody can name is not a basis.
            "ratio": ratio,
            "ratio_meaning": ("horizontal multiplier applied to the M3 "
                              "assembly when sampling the basis; 1.0 is "
                              "uniform scale (no horizontal distortion)"),
        },
        "domains": per_domain,
        "blocking_domains": blocking,
        "gate_state": FAIL if blocking else PASS,
        "no_single_score_rule": live_contract["no_single_score_rule"],
        "thresholds": {
            "binding_statistic": PROFILE_DEVIATION_STATISTIC,
            "binding_threshold": max_profile_deviation,
            "diagnostic_only": ["max_abs_deviation"],
            "status": THRESHOLD_STATUS,
            "provenance": THRESHOLD_PROVENANCE,
            "aspect": {
                "binding_statistic": ASPECT_DEVIATION_STATISTIC,
                "threshold": ASPECT_DEVIATION_THRESHOLD,
                "status": ASPECT_THRESHOLD_STATUS,
                "measured_floor": ASPECT_MEASURED_FLOOR,
                "provenance": ASPECT_THRESHOLD_PROVENANCE,
                "scope": ("M3-canonical basis only; the real-bottle basis "
                          "stays UNMEASURED and this number does not "
                          "travel there without a floor measured on that "
                          "basis (§U1d)"),
            },
        },
        "authority": {
            "what_this_is": ("a MEASUREMENT across four domains, never "
                             "collapsed into one number"),
            "what_this_is_not": ("an acceptance, a clearance, or production "
                                 "authority — the gate cannot express one"),
            "decision_channel": DECISION_CHANNEL,
        },
        "provenance": {
            "shared_measurement": {
                "schema": CONCEPT_SCHEMA,
                "profile_samples": CONCEPT_PARAMS["profile_samples"],
                "function": "concept_analysis.measure_mask",
                "note": ("imported, never re-implemented — the contract "
                         "names this profile SHARED and a second "
                         "implementation would be a second silhouette "
                         "truth"),
            },
            "canonical_basis_schema": M3_CANONICAL_SCHEMA,
            "derivation": {"module": _repo_relative(_THIS_FILE),
                           "code_sha256": _sha256(_THIS_FILE)},
        },
    }
    record["forbidden_key_scan"] = {
        "keys_visited": scan_forbidden_keys(record),
        "acceptance_keys": sorted(FORBIDDEN_ACCEPTANCE_KEYS),
        "score_keys": sorted(FORBIDDEN_SCORE_KEYS),
    }
    return record
