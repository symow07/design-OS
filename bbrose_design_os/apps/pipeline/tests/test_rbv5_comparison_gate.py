"""RBV-5 — real-bottle comparison gate: the no-collapse rule, the
fail-closed verdict model, the SHARED silhouette measurement, and the
honest UNMEASURED real-bottle side.

The P1 reference pack is empty, so a real-bottle comparison here is
UNMEASURED and therefore blocking. That is the CORRECT output of a
fail-closed gate and these tests pin it as such — not as a defect to be
worked around.
"""
import json
from pathlib import Path

import pytest

from apps.pipeline.services import concept_analysis as ca
from apps.pipeline.services import m3_calibration as m3
from apps.pipeline.services import rbv5_comparison_gate as g
from apps.pipeline.services.visual_quality_gate import (
    FAIL, NOT_APPLICABLE, PASS, UNMEASURED)

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def subject():
    """A real subject measurement: the canonical M3 sample rendered and
    measured through the SHARED sampler."""
    mask, _, _, _ = ca.extract_mask(m3.render_sample(1.0))
    return ca.measure_mask(mask)


def _record(subject, **kw):
    kw.setdefault("basis", g.BASIS_M3_CANONICAL)
    kw.setdefault("subject_id", "M3_CANONICAL_SELF")
    kw.setdefault("created_at", "2026-08-17")
    # NOT a default standing in for something unknown: the `subject`
    # fixture above is literally `render_sample(1.0)`, so 1.0 is the ratio
    # this subject WAS rendered at, and the basis has to be sampled to
    # match it. `compare` stopped defaulting `ratio` (§AL3(a)) precisely
    # so the number is stated by whoever knows it — here, the fixture.
    kw.setdefault("ratio", 1.0)
    return g.compare(subject, **kw)


def _deep_keys(node, out=None):
    out = [] if out is None else out
    if isinstance(node, dict):
        for k, v in node.items():
            out.append(str(k).lower())
            _deep_keys(v, out)
    elif isinstance(node, list):
        for i in node:
            _deep_keys(i, out)
    return out


class TestContractBinding:
    def test_contract_is_quoted_live_and_still_proposed(self, subject):
        rec = _record(subject)
        assert rec["contract"]["schema"] == g.SCHEMA
        assert "PROPOSED" in rec["contract"]["status"]
        assert rec["contract"]["status"] == g.contract()["status"]

    def test_axes_come_from_the_contract_not_a_copy(self):
        live = g.contract()["domains"]
        for domain in g.DOMAINS:
            assert g.domain_axes(domain) == tuple(live[domain])
        # non-vacuity: an empty domain would make coverage trivial
        assert all(len(g.domain_axes(d)) > 0 for d in g.DOMAINS)

    def test_all_four_domains_are_required(self, subject):
        rec = _record(subject)
        assert tuple(rec["domains"]) == g.DOMAINS
        for domain in g.DOMAINS:
            for axis in rec["domains"][domain]["axes"].values():
                assert axis["required"] is True


class TestDomainsAreNeverCollapsed:
    """The contract's no_single_score_rule, enforced rather than quoted."""

    def test_no_score_key_exists_anywhere(self, subject):
        rec = _record(subject)
        assert not (set(_deep_keys(rec)) & g.FORBIDDEN_SCORE_KEYS)
        assert rec["no_single_score_rule"] == \
            g.contract()["no_single_score_rule"]

    def test_a_planted_score_is_refused(self):
        with pytest.raises(g.Rbv5Refusal) as e:
            g.scan_forbidden_keys({"domains": {"GEOMETRY": {
                "fidelity_score": 0.91}}})
        assert e.value.findings == [
            f"{g.RBV5_SINGLE_SCORE_FORBIDDEN}:"
            "record.domains.GEOMETRY.fidelity_score"]

    def test_scan_is_not_vacuous(self):
        # exact count on a known structure: a scan that visited nothing
        # would return 0 and satisfy a loose assertion
        assert g.scan_forbidden_keys(
            {"a": 1, "b": {"c": 2}, "d": [{"e": 3}]}) == 5

    def test_each_domain_keeps_its_own_verdict(self, subject):
        rec = _record(subject)
        states = {d: rec["domains"][d]["verdict"]["state"]
                  for d in g.DOMAINS}
        # GEOMETRY carries a MIX: its measurable axes now return real
        # verdicts under §T1/§U1, while the axes that need a real-bottle
        # reference stay UNMEASURED — so the domain is UNMEASURED and
        # blocking. The point of this test is that the record shows the
        # per-axis difference rather than an averaged summary.
        geometry_axes = {a["state"]
                         for a in rec["domains"]["GEOMETRY"]["axes"].values()}
        assert PASS in geometry_axes, "the calibrated axes must show PASS"
        assert UNMEASURED in geometry_axes
        assert states["GEOMETRY"] == UNMEASURED
        assert states["ARTWORK"] == UNMEASURED


class TestFailClosed:
    def test_a_blocking_failure_survives_aggregation(self):
        axes = {"a": {"state": PASS, "required": True, "reason": "ok"},
                "b": {"state": FAIL, "required": True, "reason": "bad"},
                "c": {"state": PASS, "required": True, "reason": "ok"}}
        v = g._domain_verdict(axes)
        assert v["state"] == FAIL and v["blocking"] is True

    def test_unmeasured_is_blocking_not_neutral(self):
        axes = {"a": {"state": PASS, "required": True, "reason": "ok"},
                "b": {"state": UNMEASURED, "required": True,
                      "reason": "no reference"}}
        v = g._domain_verdict(axes)
        assert v["state"] == UNMEASURED and v["blocking"] is True

    def test_fail_dominates_unmeasured(self):
        axes = {"a": {"state": UNMEASURED, "required": True, "reason": "-"},
                "b": {"state": FAIL, "required": True, "reason": "-"}}
        assert g._domain_verdict(axes)["state"] == FAIL

    def test_empty_domain_is_unmeasured_not_pass(self):
        v = g._domain_verdict({})
        assert v["state"] == UNMEASURED and v["blocking"] is True

    def test_gate_state_fails_while_any_domain_blocks(self, subject):
        rec = _record(subject)
        assert rec["blocking_domains"]
        assert rec["gate_state"] == FAIL

    def test_not_applicable_must_carry_a_justification(self):
        with pytest.raises(g.Rbv5Refusal) as e:
            g._axis(NOT_APPLICABLE, reason="looks irrelevant")
        assert e.value.findings[0].startswith(
            g.RBV5_NOT_APPLICABLE_UNJUSTIFIED)

    def test_justified_not_applicable_is_allowed_and_recorded(self, subject):
        rec = _record(subject, not_applicable={
            "ARTWORK": {"logo_bounds_norm": "subject is a geometry "
                                            "validation fixture with no "
                                            "artwork by design"}})
        entry = rec["domains"]["ARTWORK"]["axes"]["logo_bounds_norm"]
        assert entry["state"] == NOT_APPLICABLE
        assert entry["justification"]
        # and it still cannot rescue the domain, because the other axes
        # remain UNMEASURED
        assert rec["domains"]["ARTWORK"]["verdict"]["blocking"] is True


class TestTheSilhouetteTruthIsShared:
    def test_the_profile_function_is_imported_not_reimplemented(self):
        assert g.measure_mask is ca.measure_mask
        assert g.CONCEPT_PARAMS is ca.PARAMS

    def test_sample_count_comes_from_the_shared_params(self, subject):
        assert subject["contour"]["samples"] == ca.PARAMS["profile_samples"]
        assert ca.PARAMS["profile_samples"] == 64

    def test_source_module_defines_no_second_profile(self):
        src = (REPO / "apps" / "pipeline" / "services" /
               "rbv5_comparison_gate.py").read_text()
        # the gate may compare profiles; it may not build one
        assert "def measure_mask" not in src
        assert "width_at_height_profile/1.0" in src  # it validates the tag

    def test_mismatched_sample_counts_refuse(self):
        with pytest.raises(g.Rbv5Refusal) as e:
            g._compare_profiles([0.5] * 32, [0.5] * 64)
        assert e.value.findings[0].startswith(g.RBV5_PROFILE_LENGTH_MISMATCH)

    def test_unnormalised_profile_refuses_rather_than_comparing(self):
        """Comparing differently normalised curves yields a confident
        wrong answer, which is worse than refusing."""
        with pytest.raises(g.Rbv5Refusal) as e:
            g._compare_profiles([12.0] * 64, [0.5] * 64)
        assert e.value.findings[0].startswith(
            g.RBV5_PROFILE_NORMALISATION_UNVERIFIED)

    def test_a_subject_that_is_not_a_shared_measurement_refuses(self):
        with pytest.raises(g.Rbv5Refusal) as e:
            g.compare({"aspect_h_over_w": 3.0,
                       "contour": {"representation": "hand_rolled/9.9"}},
                      basis=g.BASIS_M3_CANONICAL, subject_id="X",
                      created_at="2026-08-17", ratio=1.0)
        assert any("representation" in f for f in e.value.findings)


class TestTheRealBottleSideIsHonestlyUnmeasured:
    def test_the_pack_is_counted_not_asserted(self):
        pack = g.reference_pack_completeness()
        assert pack["items_total"] > 0
        assert pack["items_present"] == 0
        assert pack["usable_as_basis"] is False
        assert pack["status"] == "REAL_BOTTLE_REFERENCE_INCOMPLETE"

    def test_real_bottle_basis_yields_blocking_unmeasured_geometry(
            self, subject):
        rec = _record(subject, basis=g.BASIS_REFERENCE_PACK)
        geom = rec["domains"]["GEOMETRY"]
        assert geom["verdict"]["state"] == UNMEASURED
        assert geom["verdict"]["blocking"] is True
        for axis in geom["axes"].values():
            assert axis["code"] == "RBV5_REFERENCE_PACK_INCOMPLETE"
        # the pack's own numbers are carried, so the reason is checkable
        assert rec["basis"]["reference_pack"]["items_present"] == 0

    def test_the_uncalibrated_photos_are_never_substituted(self, subject):
        rec = _record(subject, basis=g.BASIS_REFERENCE_PACK)
        flat = json.dumps(rec).lower()
        assert "uncalibrated" not in flat or "photo" not in flat.split(
            "uncalibrated")[1][:80]
        assert rec["basis"]["reference_pack"]["present"] == []

    def test_invalid_basis_refuses(self, subject):
        with pytest.raises(g.Rbv5Refusal) as e:
            _record(subject, basis="VIBES")
        assert e.value.findings == [f"{g.RBV5_BASIS_INVALID}:VIBES"]


class TestTheGateCannotAccept:
    def test_no_acceptance_key_anywhere(self, subject):
        rec = _record(subject)
        assert not (set(_deep_keys(rec)) & g.FORBIDDEN_ACCEPTANCE_KEYS)

    def test_a_planted_acceptance_is_refused(self):
        with pytest.raises(g.Rbv5Refusal) as e:
            g.scan_forbidden_keys({"domains": {"owner_acceptance": True}})
        assert e.value.findings[0].startswith(g.RBV5_ACCEPTANCE_FORBIDDEN)

    def test_the_record_says_what_it_is_not(self, subject):
        rec = _record(subject)
        assert "acceptance" in rec["authority"]["what_this_is_not"]
        assert rec["authority"]["decision_channel"] == g.DECISION_CHANNEL


class TestThresholdIsOwnerCalibratedAndSitsAboveTheNoise:
    """§T1. The number is a measurement-policy choice by the owner, not a
    result — so it is recorded OWNER_CALIBRATED, never MEASURED."""

    def test_threshold_is_owner_calibrated_with_its_provenance(self,
                                                               subject):
        rec = _record(subject)["thresholds"]
        assert rec["status"] == "OWNER_CALIBRATED"
        assert rec["status"] != "MEASURED"
        assert "§T1" in rec["provenance"]
        assert rec["binding_statistic"] == "mean_abs_deviation"
        assert rec["binding_threshold"] == g.PROFILE_DEVIATION_THRESHOLD == \
            0.03

    def test_the_binding_threshold_sits_ABOVE_the_measured_mean_floor(self):
        """THE INVERTED GUARD (§T1e). It used to assert the floor exceeded
        the threshold — evidence that the provisional number was too tight.
        Now it asserts the opposite and permanently: the binding mean
        threshold must stay ABOVE the measured mean noise floor, so nobody
        can quietly tighten it back under the noise."""
        cal = g.canonical_self_comparison()
        floor = cal["mean_abs_deviation"]
        assert g.PROFILE_DEVIATION_THRESHOLD > floor, (
            f"binding mean threshold {g.PROFILE_DEVIATION_THRESHOLD} is at "
            f"or below the measured mean noise floor {floor} — the gate "
            "would be measuring the rasteriser, not the design")
        # §T1c: 3x the floor is the calibrated margin; hold it as a floor
        # on the margin itself so a later tightening cannot creep
        assert cal["signal_to_noise_margin"] >= 3.0

    def test_max_is_retained_as_a_diagnostic_and_is_not_binding(self,
                                                                subject):
        """§T1e: keep max reported on every verdict. A diagnostic that
        starts failing verdicts is a bar being moved."""
        rec = _record(subject)
        axis = [a for n, a in rec["domains"]["GEOMETRY"]["axes"].items()
                if "width_at_height_profile" in n][0]
        measured = axis["measured"]
        assert "max_abs_deviation" in measured
        assert "diagnostic, not binding" in axis["reason"]
        assert rec["thresholds"]["diagnostic_only"] == ["max_abs_deviation"]
        # the decisive property: max EXCEEDS the threshold, and the axis
        # still passes on the binding mean. If this ever flips to FAIL on
        # max, the diagnostic has become a bar.
        assert measured["max_abs_deviation"] > g.PROFILE_DEVIATION_THRESHOLD
        assert measured["mean_abs_deviation"] <= \
            g.PROFILE_DEVIATION_THRESHOLD
        assert axis["state"] == PASS

    def test_self_comparison_still_measures_instrument_noise(self):
        cal = g.canonical_self_comparison()
        assert cal["mean_abs_deviation"] < cal["max_abs_deviation"]
        assert cal["threshold_status"] == "OWNER_CALIBRATED"
        assert cal["binding_statistic"] == "mean_abs_deviation"

    def test_the_aspect_threshold_is_owner_calibrated_by_its_own_ruling(
            self):
        """§U1. A SEPARATE ruling from §T1 — deliberately the same 3x
        multiplier, deliberately not inherited, because a threshold binds
        a STATISTIC and no ruling transfers between statistics."""
        assert g.ASPECT_THRESHOLD_STATUS == "OWNER_CALIBRATED"
        assert g.ASPECT_DEVIATION_THRESHOLD == 0.13
        prov = g.ASPECT_THRESHOLD_PROVENANCE
        assert "§U1" in prov
        # §U1a: the file itself must say what this binds and what it is not
        assert "ABSOLUTE delta" in prov and "RATIO" in prov
        assert "NOT PROFILE_DEVIATION_THRESHOLD" in prov
        assert "NOT silhouette_max_aspect_deviation" in prov
        assert g.ASPECT_DEVIATION_STATISTIC != g.PROFILE_DEVIATION_STATISTIC

    def test_the_aspect_threshold_sits_ABOVE_its_measured_floor(self):
        """THE INVERTED GUARD (§U1b), same shape §T1 used. It previously
        asserted the floor EXCEEDED the threshold — evidence the number
        was too tight. It now asserts the opposite, permanently, so the
        aspect threshold cannot be quietly re-tightened under the noise."""
        cal = g.canonical_self_comparison()
        floor = cal["aspect_noise_floor"]
        assert g.ASPECT_DEVIATION_THRESHOLD > floor, (
            f"aspect threshold {g.ASPECT_DEVIATION_THRESHOLD} is at or "
            f"below its measured floor {floor} — the gate would be "
            "reporting the rasteriser, not the design")
        # §U1 describes 0.13 as "three times" the floor. Exactly 3x would
        # be 0.1302; the owner ruled the round number, so the real
        # multiplier is 2.9954. Asserting >= 3.0 would fail the owner's own
        # ruling, so the guard binds what §U1b actually requires — ABOVE
        # the floor — and the rounding is recorded rather than smoothed.
        assert g.ASPECT_DEVIATION_THRESHOLD / floor > 2.99
        # the recorded floor must track the measured one
        assert abs(g.ASPECT_MEASURED_FLOOR - floor) < 1e-6

    def test_the_measured_floor_rides_along_as_a_diagnostic(self, subject):
        """§U1c. A diagnostic that starts deciding verdicts is a bar being
        moved — so it is reported on every verdict and never compared."""
        rec = _record(subject)
        axis = rec["domains"]["GEOMETRY"]["axes"]["body_aspect_h_over_w"]
        assert axis["measured"]["measured_floor_diagnostic"] == \
            g.ASPECT_MEASURED_FLOOR
        assert axis["measured"]["statistic"] == g.ASPECT_DEVIATION_STATISTIC

    def test_the_calibration_does_not_travel_to_the_real_bottle_basis(
            self, subject):
        """§U1d. The real-bottle basis has no measured aspect floor, so it
        stays UNMEASURED — a calibrated M3 number does not license a
        verdict there."""
        rec = _record(subject, basis=g.BASIS_REFERENCE_PACK)
        geom = rec["domains"]["GEOMETRY"]
        assert geom["verdict"]["state"] == UNMEASURED
        assert geom["axes"]["body_aspect_h_over_w"]["state"] == UNMEASURED


class TestProvenanceAndPurity:
    def test_record_names_the_shared_measurement_and_its_derivation(
            self, subject):
        prov = _record(subject)["provenance"]
        assert prov["shared_measurement"]["schema"] == ca.SCHEMA
        assert prov["shared_measurement"]["profile_samples"] == 64
        assert prov["canonical_basis_schema"] == m3.CANONICAL_SCHEMA
        assert len(prov["derivation"]["code_sha256"]) == 64

    def test_same_inputs_same_record(self, subject):
        assert _record(subject) == _record(subject)

    def test_no_provider_or_orm_imports(self):
        src = (REPO / "apps" / "pipeline" / "services" /
               "rbv5_comparison_gate.py").read_text()
        for banned in ("import requests", "import anthropic",
                       "from django.db", "urllib.request",
                       "from apps.pipeline.models"):
            assert banned not in src, banned


class TestTrackerClaimHonesty:
    def test_node_does_not_claim_measured_real_bottle_comparison(self):
        from apps.pipeline.management.commands.roadmap_status import (
            load_tracker)
        node = {n["id"]: n for n in load_tracker()["nodes"]}[
            "quality.rbv5_comparison_gate"]
        if not g.reference_pack_completeness()["usable_as_basis"]:
            assert "UNMEASURED" in node["scope"], (
                "the real-bottle side is UNMEASURED in the engine — the "
                "node must say so rather than imply a comparison ran")
        assert (node["visual_quality_percent"] or 0) == 0
