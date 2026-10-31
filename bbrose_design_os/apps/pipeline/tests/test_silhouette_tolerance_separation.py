"""§U preamble — a threshold binds a STATISTIC, and no owner ruling
transfers from one statistic to another.

Sprint 3 found §T1 one commit from being silently applied to a quantity
the owner never calibrated: `PROFILE_DEVIATION_THRESHOLD` and
`ASPECT_DEVIATION_THRESHOLD` were both 0.03, so a ruling made about a mean
over 64 normalised samples would have landed on an absolute ratio delta as
well. That was caught by a person noticing. This converts the catch into a
test.

THE RULE ENCODED HERE: two silhouette tolerances sharing a value are a
SUSPECTED CONFLATION and must be proven distinct — the justification is
recorded below, keyed by the pair, and a new collision fails until someone
writes one. Equality is not forbidden; unexamined equality is.
"""
import pytest

from apps.pipeline.services import rbv5_comparison_gate as r5
from apps.pipeline.services import visual_quality_gate as vqg
from apps.pipeline.services import vqr2b_reconstruction_measurement as v2


def _constants():
    """The four live silhouette tolerances, each with the statistic it
    binds and its measured floor. Adding a fifth without listing it here
    is caught by test_no_silhouette_tolerance_is_unlisted."""
    return {
        "rbv5.PROFILE_DEVIATION_THRESHOLD": {
            "value": r5.PROFILE_DEVIATION_THRESHOLD,
            "statistic": r5.PROFILE_DEVIATION_STATISTIC,
            "status": r5.THRESHOLD_STATUS,
            "floor": 0.0100,
            "quantity": "mean abs deviation over 64 max-width-normalised "
                        "samples, subject vs M3 canonical basis",
        },
        "rbv5.ASPECT_DEVIATION_THRESHOLD": {
            "value": r5.ASPECT_DEVIATION_THRESHOLD,
            "statistic": r5.ASPECT_DEVIATION_STATISTIC,
            "status": r5.ASPECT_THRESHOLD_STATUS,
            "floor": r5.ASPECT_MEASURED_FLOOR,
            "quantity": "single ABSOLUTE delta between two height/width "
                        "ratios",
        },
        "vqr2b.PROFILE_DEVIATION_THRESHOLD": {
            "value": v2.PROFILE_DEVIATION_THRESHOLD,
            "statistic": v2.PROFILE_DEVIATION_STATISTIC,
            "status": v2.THRESHOLD_STATUS,
            "floor": v2.MEASURED_FLOOR,
            "quantity": "mean abs deviation over 64 max-width-normalised "
                        "samples, RECONSTRUCTION vs SELECTED CONCEPT",
        },
        "visual_quality_gate.silhouette_max_aspect_deviation": {
            "value": vqg.THRESHOLDS["silhouette_max_aspect_deviation"],
            "statistic": "relative_aspect_deviation",
            "status": "UNMEASURED_FLOOR",
            "floor": None,
            "quantity": "RELATIVE aspect deviation "
                        "|actual-expected|/expected, structural "
                        "conformance against the confirmed profile",
        },
    }


#: Pairs that legitimately share a value, each with the reason they are
#: nonetheless distinct. A collision NOT listed here fails the suite.
JUSTIFIED_COLLISIONS = {
    frozenset({"rbv5.PROFILE_DEVIATION_THRESHOLD",
               "vqr2b.PROFILE_DEVIATION_THRESHOLD"}): (
        "Both are 0.03 and both bind a mean over the same shared 64-sample "
        "profile, but they are separate rulings over separate questions "
        "with different evidence. RBV-5 (§T1) compares a subject to the M3 "
        "canonical basis and its 0.03 is 3x a measured instrument floor of "
        "0.0100. R2b (§U2) compares a reconstruction to its selected "
        "concept, its measured floor is EXACTLY 0.0, and its 0.03 clears "
        "no noise at all — it is a pure design tolerance. Same number, "
        "different meaning, different owner ruling; neither may be changed "
        "by a ruling about the other."),
}


class TestSilhouetteTolerancesAreDistinct:
    def test_every_constant_names_the_statistic_it_binds(self):
        """§U preamble: a threshold constant carries the name of the
        statistic it binds. PROFILE_DEVIATION_STATISTIC set the pattern;
        it is extended, not left as a one-off."""
        for name, spec in _constants().items():
            assert spec["statistic"], name
            assert isinstance(spec["statistic"], str), name

    def test_the_two_calibrated_statistics_are_not_the_same_statistic(self):
        """The specific conflation that nearly happened."""
        assert r5.PROFILE_DEVIATION_STATISTIC != r5.ASPECT_DEVIATION_STATISTIC

    def test_shared_values_are_proven_distinct_not_assumed(self):
        """THE STRUCTURAL CATCH. Any two tolerances at the same value are
        a suspected conflation until a justification is recorded for that
        exact pair."""
        consts = _constants()
        names = sorted(consts)
        unjustified = []
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if consts[a]["value"] != consts[b]["value"]:
                    continue
                if frozenset({a, b}) not in JUSTIFIED_COLLISIONS:
                    unjustified.append((a, b, consts[a]["value"]))
        assert unjustified == [], (
            "silhouette tolerances share a value with no recorded "
            "justification — treat as a SUSPECTED CONFLATION and prove "
            "them distinct before ruling on either (§U preamble): "
            f"{unjustified}")

    def test_the_collision_detector_actually_fires(self, monkeypatch):
        """NEGATIVE CONTROL. A guard that has never been seen refusing is
        not known to work — and this one currently passes only because
        every live collision happens to be justified. Remove the
        justification and it must fail."""
        monkeypatch.setattr(
            "apps.pipeline.tests.test_silhouette_tolerance_separation."
            "JUSTIFIED_COLLISIONS", {})
        consts = _constants()
        names = sorted(consts)
        unjustified = [
            (a, b) for i, a in enumerate(names) for b in names[i + 1:]
            if consts[a]["value"] == consts[b]["value"]
            and frozenset({a, b}) not in JUSTIFIED_COLLISIONS
        ]
        assert unjustified, (
            "with justifications removed the detector found no collision "
            "— it would not catch a real conflation either")
        assert (("rbv5.PROFILE_DEVIATION_THRESHOLD",
                 "vqr2b.PROFILE_DEVIATION_THRESHOLD") in unjustified)

    def test_each_justification_is_substantive(self):
        for pair, reason in JUSTIFIED_COLLISIONS.items():
            assert len(reason) >= 120, sorted(pair)
            # a justification must say what makes them different, not that
            # they happen to be equal
            assert "different" in reason.lower(), sorted(pair)

    def test_a_justification_cannot_outlive_the_collision(self):
        """If two constants stop sharing a value, the justification for
        that pair is stale and must be removed — otherwise a future
        collision could be silently pre-approved."""
        consts = _constants()
        stale = [sorted(pair) for pair in JUSTIFIED_COLLISIONS
                 if len({consts[n]["value"] for n in pair}) != 1]
        assert stale == [], (
            "a recorded collision justification no longer describes a "
            f"collision — remove it so it cannot pre-approve a future "
            f"one: {stale}")

    def test_no_silhouette_tolerance_is_unlisted(self):
        """A fifth tolerance added without listing it here would escape
        the collision check entirely."""
        for module, attrs in ((r5, ("PROFILE_DEVIATION_THRESHOLD",
                                    "ASPECT_DEVIATION_THRESHOLD")),
                              (v2, ("PROFILE_DEVIATION_THRESHOLD",))):
            found = {a for a in dir(module)
                     if a.endswith("_DEVIATION_THRESHOLD")}
            assert found == set(attrs), (
                f"{module.__name__} exposes tolerance constants not listed "
                f"in this test: {sorted(found - set(attrs))}")

    def test_an_owner_calibrated_status_names_its_ruling(self):
        """A constant may not claim OWNER_CALIBRATED without provenance
        pointing at the ruling that calibrated it."""
        for prov, section in ((r5.THRESHOLD_PROVENANCE, "§T1"),
                              (r5.ASPECT_THRESHOLD_PROVENANCE, "§U1"),
                              (v2.THRESHOLD_PROVENANCE, "§U2")):
            assert section in prov
            assert "OWNER_BLOCKER_CLEARANCE.md" in prov

    @pytest.mark.parametrize("name,spec", sorted(_constants().items()))
    def test_a_calibrated_threshold_sits_above_its_measured_floor(
            self, name, spec):
        """Where a floor was measured, the binding number must clear it.
        The one exception is a floor of exactly 0.0, where there is no
        noise to clear and the tolerance is a pure design statement."""
        floor = spec["floor"]
        if floor is None:
            pytest.skip(f"{name} has no measured floor")
        if floor == 0.0:
            assert spec["value"] > 0.0
            return
        assert spec["value"] > floor, name
