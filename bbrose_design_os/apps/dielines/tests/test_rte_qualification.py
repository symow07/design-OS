"""2A-9C slice 3 — reverse_tuck_end_carton/1.1 qualification + mirror audit.

Pins: the mirror is correct (top tuck on FRONT, bottom on BACK; tuck
columns; slits on mirrored panels; structural equivalence to STE at the
same dims — same flat, same cut area, same integrity); explicit
mirror-defect classes cannot pass; the honest domain matches STE's band
(derived independently); boundaries stable both sides; RTE stays
provisional; committed matrix reproduces; sweep clean; 1.1 unchanged; no
provider calls.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.qualification.domain import evaluate_domain
from apps.dielines.qualification.reverse_tuck_qual import RTE_DOMAIN
from apps.dielines.qualification.runner import (
    adapter_for,
    fixtures_for,
    qualify,
    seeded_property_sweep,
    sweep_seed_for,
)
from apps.dielines.tests import provider_tripwire as tripwire

DOCS = Path("docs/qualification/reverse_tuck_end_carton_1_1")
REP = {"width_mm": 60.0, "depth_mm": 20.0, "height_mm": 130.0,
       "board_thickness_mm": 0.5, "glue_tab_mm": 10.0,
       "bleed_mm": 3.0, "safe_margin_mm": 4.0}
REP_HASH = "6559e7758ef2a9751dace261f8ba0807"


class RteMirrorAuditTests(TestCase):
    def setUp(self):
        self.adapter = adapter_for("reverse_tuck_end_carton")

    def test_tuck_attachment_is_mirrored(self):
        result = qualify(REP, self.adapter)
        assert result.supported
        d = result._coords.derived
        assert d["top_tuck_panel"] == "front"
        assert d["bottom_tuck_panel"] == "back"

    def test_tucks_sit_over_the_correct_mirrored_columns(self):
        """A mirrored x-sign error would land a tuck on the wrong panel."""
        result = qualify(REP, self.adapter)
        by_name = {c["name"]: c for c in result.folded_checks}
        assert by_name["top_tuck_over_front_column"]["ok"]
        assert by_name["bottom_tuck_over_back_column"]["ok"]
        assert by_name["slits_on_mirrored_panels"]["ok"]
        assert by_name["reverse_attachment_preserved"]["ok"]

    def test_structural_equivalence_to_ste_at_same_dims(self):
        """The mirror only swaps the tuck column: flat, cut area and
        integrity must equal STE at the same dimensions."""
        rte = calculate_dieline(self.adapter.build_params(REP))
        ste_adapter = adapter_for("straight_tuck_end_carton")
        ste = calculate_dieline(ste_adapter.build_params(REP))
        assert rte.flat_width_mm == ste.flat_width_mm
        assert rte.flat_height_mm == ste.flat_height_mm
        assert abs(rte.cut_polygon.area - ste.cut_polygon.area) < 1e-6
        assert len(rte.components) == len(ste.components)
        assert len(rte.stadium_cutouts) == len(ste.stadium_cutouts)
        # but the tuck columns are swapped
        assert rte.derived["top_tuck_panel"] != ste.derived["top_tuck_panel"]

    def test_no_cut_fold_conflict_or_self_intersection(self):
        from apps.dielines.exporters.structural_comparison import (
            geometry_integrity,
        )
        integ = geometry_integrity(calculate_dieline(
            self.adapter.build_params(REP)))
        assert not integ["cut_fold_conflict"]
        assert not integ["self_intersecting"]
        assert not integ["open_contour"]


class RteDomainTests(TestCase):
    def setUp(self):
        self.adapter = adapter_for("reverse_tuck_end_carton")

    def test_shares_ste_narrow_band(self):
        # wide-short (lip>H/2) and square-ish (W<1.262D) are excluded
        assert any("TUCK_LIP_VS_HEIGHT" in v for v in evaluate_domain(
            dict(REP, width_mm=90.0, depth_mm=25.0, height_mm=92.0),
            RTE_DOMAIN))
        assert any("DUST_PAIR_CLEARANCE" in v for v in evaluate_domain(
            dict(REP, width_mm=40.0, depth_mm=40.0, height_mm=130.0),
            RTE_DOMAIN))

    def test_boundaries_stable_both_sides(self):
        fixtures = fixtures_for("reverse_tuck_end_carton")
        for inside, outside, constraint in (
                ("inside_dust_pair_boundary", "outside_dust_pair_boundary",
                 "DUST_PAIR_CLEARANCE"),
                ("inside_lip_boundary", "outside_lip_boundary",
                 "TUCK_LIP_VS_HEIGHT")):
            assert qualify(fixtures[inside], self.adapter).supported
            assert any(constraint in v for v in evaluate_domain(
                fixtures[outside], RTE_DOMAIN))

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

    def test_representative_hash_frozen(self):
        result = qualify(REP, self.adapter)
        assert result.geometry_hash == REP_HASH

    def test_property_sweep_is_clean(self):
        summary = seeded_property_sweep(
            self.adapter, seed=sweep_seed_for("reverse_tuck_end_carton"),
            n_in_domain=50, n_random=100)
        assert summary["failures"] == [], summary["failures"][:3]
        assert summary["supported"] > 0
        assert summary["rejected_by_domain"] > 0

    def test_rte_stays_provisional(self):
        from apps.dielines import registry
        defn = registry.resolve("reverse_tuck_end_carton", "1.1")
        assert defn.provisional is True
        # RTE 1.1 slice-3 qualification added no version; 2A-9D later adds
        # the non-current 1.2 D-derived correction. 1.1 stays current.
        assert registry.resolve("reverse_tuck_end_carton").version == "1.1"
        versions = {v for (tid, v) in registry._REGISTRY
                    if tid == "reverse_tuck_end_carton"}
        assert {"1.0", "1.1"} <= versions


class RteEndpointTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("rte9c", "r@c.com", "pw")
        group, _ = Group.objects.get_or_create(name="Reviewer")
        user.groups.add(group)
        self.client.force_login(user)

    def test_endpoint_supports_in_band_and_rejects_out_of_band(self):
        ok = self.client.post(
            "/api/dielines/qualify_dimensions/",
            {"template": "reverse_tuck_end_carton", **REP},
            content_type="application/json").json()
        assert ok["supported"] is True
        assert ok["geometry_hash"] == REP_HASH
        bad = self.client.post(
            "/api/dielines/qualify_dimensions/",
            {"template": "reverse_tuck_end_carton",
             "width_mm": 90.0, "depth_mm": 25.0, "height_mm": 92.0,
             "board_thickness_mm": 0.35, "glue_tab_mm": 12.0},
            content_type="application/json").json()
        assert bad["supported"] is False
        assert any("TUCK_LIP_VS_HEIGHT" in v for v in bad["violations"])


class RteHygieneTests(TestCase):
    def test_qualifying_every_rte_fixture_makes_no_provider_call(self):
        """WI-S — converted from a §Y2-registered source-string guard.

        Was: four words are absent from `reverse_tuck_qual.py`. Now: every
        committed RTE fixture is qualified with every provider boundary armed
        to raise, and the module has to have executed.
        """
        import apps.dielines.qualification.reverse_tuck_qual as mod
        with tripwire.armed(mod) as watch:
            adapter = adapter_for("reverse_tuck_end_carton")
            fixtures = fixtures_for("reverse_tuck_end_carton")
            outcomes = {name: qualify(case, adapter).supported
                        for name, case in fixtures.items()}
        assert any(outcomes.values()) and not all(outcomes.values()), outcomes
        tripwire.assert_clean(watch, mod)
