"""2A-9C slice 2 — Skynte side-seam 1.0 qualification.

Pins: the task-#47 golden reference (42×32×140) generates unchanged with
its frozen geometry + content hashes; the honest domain (width cap +
dust-clearance edge, boundaries stable both sides); D-derived closure (no
lip-vs-height defect); no version bump needed; the endpoint fails closed
for out-of-domain Skynte; the sweep is clean; no provider calls.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.dielines.qualification.domain import evaluate_domain
from apps.dielines.qualification.runner import (
    adapter_for,
    fixtures_for,
    qualify,
    seeded_property_sweep,
    sweep_seed_for,
)
from apps.dielines.qualification.side_seam_qual import SKYNTE_DOMAIN, _WIDTH_CAP
from apps.dielines.tests import provider_tripwire as tripwire

DOCS = Path("docs/qualification/skynte_foundation_tuck_carton_1_0")
TASK47 = {"width_mm": 42.0, "depth_mm": 32.0, "height_mm": 140.0,
          "board_thickness_mm": 0.30, "glue_tab_mm": 10.0,
          "bleed_mm": 3.0, "safe_margin_mm": 4.0}
TASK47_HASH = "2be58c7bdb0afcc5728d700789c3e1e7"
TASK47_CUT = "10578abcbbffb631"     # prefix pin (full checked below)


class Task47GoldenTests(TestCase):
    def test_task47_reference_is_supported_and_frozen(self):
        result = qualify(TASK47, adapter_for("skynte_foundation_tuck_carton"))
        assert result.supported, (result.violations,
                                  result.invariant_failures)
        assert result.geometry_hash == TASK47_HASH
        assert result.content_hashes["cut_path_hash"].startswith(TASK47_CUT)

    def test_generator_reproduces_task47_geometry_unchanged(self):
        from apps.dielines.geometry.engine import calculate_dieline
        adapter = adapter_for("skynte_foundation_tuck_carton")
        coords = calculate_dieline(adapter.build_params(TASK47))
        assert [p.name for p in coords.panels] == [
            "glue_tab", "side_left", "front", "side_right", "back"]
        assert coords.dimensions.manufacture == (42.0, 32.0, 140.0)
        assert coords.derived["top_tuck_panel"] == "back"
        assert coords.derived["bottom_tuck_panel"] == "front"


class SkynteDomainTests(TestCase):
    def setUp(self):
        self.adapter = adapter_for("skynte_foundation_tuck_carton")

    def test_closure_is_depth_derived_no_lip_defect(self):
        result = qualify(TASK47, self.adapter)
        by_name = {c["name"]: c for c in result.folded_checks}
        assert by_name["tuck_is_depth_derived"]["ok"]
        assert by_name["lip_vs_height"]["ok"]

    def test_width_cap_is_a_hard_generator_limit(self):
        assert 73.0 < _WIDTH_CAP < 73.5
        inside = dict(TASK47, width_mm=73.3, depth_mm=40.0, height_mm=200.0)
        outside = dict(TASK47, width_mm=73.5, depth_mm=40.0, height_mm=200.0)
        assert not evaluate_domain(inside, SKYNTE_DOMAIN)
        assert any("SHOULDER_FITS_LIP" in v
                   for v in evaluate_domain(outside, SKYNTE_DOMAIN))
        # the generator itself fails closed past the cap
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.geometry.engine import GeometryError
        with self.assertRaises((GeometryError, ValueError)):
            calculate_dieline(self.adapter.build_params(
                dict(TASK47, width_mm=90.0, depth_mm=40.0, height_mm=200.0)))

    def test_dust_clearance_boundary_stable_both_sides(self):
        fixtures = fixtures_for("skynte_foundation_tuck_carton")
        assert qualify(fixtures["inside_dust_pair_boundary"],
                       self.adapter).supported
        assert any("DUST_PAIR_CLEARANCE" in v for v in evaluate_domain(
            fixtures["outside_dust_pair_boundary"], SKYNTE_DOMAIN))

    def test_committed_matrix_reproduces(self):
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
            self.adapter,
            seed=sweep_seed_for("skynte_foundation_tuck_carton"),
            n_in_domain=50, n_random=100)
        assert summary["failures"] == [], summary["failures"][:3]
        assert summary["supported"] > 0
        assert summary["rejected_by_domain"] > 0

    def test_no_version_bump_qualification_is_readonly(self):
        # slice 2 registers no new template version
        from apps.dielines import registry
        versions = {v for (tid, v) in registry._REGISTRY
                    if tid == "skynte_foundation_tuck_carton"}
        assert versions == {"1.0"}


class SkynteEndpointTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("sk9c", "s@k.com", "pw")
        group, _ = Group.objects.get_or_create(name="Reviewer")
        user.groups.add(group)
        self.client.force_login(user)

    def test_endpoint_supports_reference(self):
        res = self.client.post(
            "/api/dielines/qualify_dimensions/",
            {"template": "skynte_foundation_tuck_carton", **TASK47},
            content_type="application/json")
        data = res.json()
        assert data["supported"] is True
        assert data["geometry_hash"] == TASK47_HASH

    def test_endpoint_fails_closed_past_width_cap(self):
        res = self.client.post(
            "/api/dielines/qualify_dimensions/",
            {"template": "skynte_foundation_tuck_carton",
             "width_mm": 90.0, "depth_mm": 40.0, "height_mm": 200.0,
             "board_thickness_mm": 0.5, "glue_tab_mm": 12.0},
            content_type="application/json")
        data = res.json()
        assert data["supported"] is False
        assert any("SHOULDER_FITS_LIP" in v for v in data["violations"])


class SkynteHygieneTests(TestCase):
    def test_qualifying_every_skynte_fixture_makes_no_provider_call(self):
        """WI-S — converted from a §Y2-registered source-string guard.

        Was: four words are absent from `side_seam_qual.py`. Now: every
        committed Skynte fixture is qualified with every provider boundary
        armed to raise, and the module has to have executed.
        """
        import apps.dielines.qualification.side_seam_qual as mod
        with tripwire.armed(mod) as watch:
            adapter = adapter_for("skynte_foundation_tuck_carton")
            fixtures = fixtures_for("skynte_foundation_tuck_carton")
            outcomes = {name: qualify(case, adapter).supported
                        for name, case in fixtures.items()}
        assert any(outcomes.values()) and not all(outcomes.values()), outcomes
        tripwire.assert_clean(watch, mod)
