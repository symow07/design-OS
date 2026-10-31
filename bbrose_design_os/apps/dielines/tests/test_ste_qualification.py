"""2A-9C slice 1 — STE 1.1 qualification.

Pins: the honest domain (defect regions excluded, boundaries stable both
sides); the measured reference and the historical 90×25×92 die are
REJECTED with named constraints; the 1.1 GENERATOR still reproduces
historical geometry (qualification never mutates 1.1); the committed
matrix values reproduce; the endpoint fails closed for STE; the sweep is
clean; no provider calls.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.dielines.qualification.domain import evaluate_domain
from apps.dielines.qualification.legacy_tuck import STE_DOMAIN
from apps.dielines.qualification.runner import (
    adapter_for,
    fixtures_for,
    qualify,
    seeded_property_sweep,
    sweep_seed_for,
)
from apps.dielines.tests import provider_tripwire as tripwire

DOCS = Path("docs/qualification/straight_tuck_end_carton_1_1")


class SteDomainTests(TestCase):
    def setUp(self):
        self.adapter = adapter_for("straight_tuck_end_carton")

    def test_measured_reference_is_outside_its_own_formulas_domain(self):
        fixtures = fixtures_for("straight_tuck_end_carton")
        result = qualify(fixtures["measured_reference_28x28x120"],
                         self.adapter)
        assert not result.supported
        assert any("DUST_PAIR_CLEARANCE" in v for v in result.violations)

    def test_historical_task50_ste_die_is_rejected(self):
        fixtures = fixtures_for("straight_tuck_end_carton")
        result = qualify(fixtures["historical_task50_ste_90x25x92"],
                         self.adapter)
        assert not result.supported
        assert any("TUCK_LIP_VS_HEIGHT" in v for v in result.violations)

    def test_dust_clamp_and_slit_reduction_are_domain_edges(self):
        names = {c.name for c in STE_DOMAIN}
        assert "DUST_CLAMP_BOUNDARY" in names
        assert "SLIT_WEB_UNREDUCED" in names
        # inside the domain the emitted die is unclamped and unreduced
        fixtures = fixtures_for("straight_tuck_end_carton")
        result = qualify(fixtures["nearly_square"], self.adapter)
        assert result.supported
        by_name = {c["name"]: c for c in result.folded_checks}
        assert by_name["dust_unclamped"]["ok"]
        assert by_name["slit_unreduced"]["ok"]

    def test_boundaries_stable_both_sides(self):
        fixtures = fixtures_for("straight_tuck_end_carton")
        for inside, outside, constraint in (
                ("inside_dust_pair_boundary", "outside_dust_pair_boundary",
                 "DUST_PAIR_CLEARANCE"),
                ("inside_lip_boundary", "outside_lip_boundary",
                 "TUCK_LIP_VS_HEIGHT")):
            ok = qualify(fixtures[inside], self.adapter)
            assert ok.supported, (inside, ok.violations,
                                  ok.invariant_failures)
            bad_violations = evaluate_domain(fixtures[outside], STE_DOMAIN)
            assert any(constraint in v for v in bad_violations), (
                outside, bad_violations)

    def test_generator_still_reproduces_historical_geometry(self):
        """Qualification NEVER mutates 1.1: an out-of-domain historical
        die still generates through calculate_dieline (fail-closed lives
        in the qualification layer, endpoint and UI — new-die paths)."""
        from apps.dielines.geometry.engine import calculate_dieline
        fixtures = fixtures_for("straight_tuck_end_carton")
        coords = calculate_dieline(self.adapter.build_params(
            fixtures["historical_task50_ste_90x25x92"]))
        assert coords.derived["structure_type"] == \
            "straight_tuck_end_carton"
        assert coords.derived["template_version"] == "1.1"
        assert coords.dimensions.manufacture == (90.0, 25.0, 92.0)

    def test_committed_matrix_values_reproduce(self):
        committed = json.loads(
            (DOCS / "qualification_matrix.json").read_text())
        for row in committed["rows"]:
            result = qualify(row["input"], self.adapter)
            outcome = ("SUPPORTED" if result.supported else
                       ("REJECTED_BY_DOMAIN" if result.violations
                        else "INVARIANT_FAILURE"))
            assert outcome == row["outcome"], (row["case"], outcome)
            if result.supported:
                assert result.geometry_hash == row["geometry_hash"]
                assert result.content_hashes == row["content_hashes"]

    def test_property_sweep_is_clean(self):
        summary = seeded_property_sweep(
            self.adapter, seed=sweep_seed_for("straight_tuck_end_carton"),
            n_in_domain=50, n_random=100)
        assert summary["failures"] == [], summary["failures"][:3]
        assert summary["supported"] > 0
        assert summary["rejected_by_domain"] > 0

    def test_thickness_compensation_varies(self):
        fixtures = fixtures_for("straight_tuck_end_carton")
        base = dict(fixtures["medium_shallow"])
        thin = qualify(dict(base, board_thickness_mm=0.3), self.adapter)
        thick = qualify(dict(base, board_thickness_mm=0.8), self.adapter)
        assert thin.supported and thick.supported
        assert thin.content_hashes != thick.content_hashes
        assert thin.geometry_hash != thick.geometry_hash


class SteEndpointTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("ste9c", "s@c.com", "pw")
        group, _ = Group.objects.get_or_create(name="Reviewer")
        user.groups.add(group)
        self.client.force_login(user)

    def test_endpoint_fails_closed_for_new_ste_dies(self):
        res = self.client.post(
            "/api/dielines/qualify_dimensions/",
            {"template": "straight_tuck_end_carton",
             "width_mm": 90.0, "depth_mm": 25.0, "height_mm": 92.0,
             "board_thickness_mm": 0.35, "glue_tab_mm": 12.0},
            content_type="application/json")
        data = res.json()
        assert data["qualification_available"] is True
        assert data["supported"] is False
        assert any("TUCK_LIP_VS_HEIGHT" in v for v in data["violations"])
        assert "TECHNICALLY_QUALIFIED_DOMAIN" in \
            data["authority"]["technical"]
        assert "NOT production readiness" in data["authority"]["technical"]

    def test_endpoint_supports_in_band_ste(self):
        res = self.client.post(
            "/api/dielines/qualify_dimensions/",
            {"template": "straight_tuck_end_carton",
             "width_mm": 60.0, "depth_mm": 20.0, "height_mm": 130.0,
             "board_thickness_mm": 0.5, "glue_tab_mm": 12.0},
            content_type="application/json")
        data = res.json()
        assert data["supported"] is True
        assert data["collision"]["all_ok"] is True


class SteHygieneTests(TestCase):
    def test_qualifying_every_ste_fixture_makes_no_provider_call(self):
        """WI-S — converted from a §Y2-registered source-string guard.

        The version this replaces read `legacy_tuck.py` and asserted four
        words were absent from it, which is a claim about a file rather than
        about the code. This one qualifies every committed STE fixture with
        every provider boundary in the repo armed to raise, and requires the
        run to have executed lines in the module.
        """
        import apps.dielines.qualification.legacy_tuck as mod
        with tripwire.armed(mod) as watch:
            adapter = adapter_for("straight_tuck_end_carton")
            fixtures = fixtures_for("straight_tuck_end_carton")
            outcomes = {name: qualify(case, adapter).supported
                        for name, case in fixtures.items()}
        # the exercise has to have gone down both sides of the domain, or a
        # whole half of the module is unvisited and the tripwire says nothing
        # about it
        assert any(outcomes.values()) and not all(outcomes.values()), outcomes
        tripwire.assert_clean(watch, mod)
