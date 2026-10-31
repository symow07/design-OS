"""2A-9D commit 3 — reverse_tuck_end_carton/1.2 D-derived + mirror audit.

RTE 1.2 is the mirror of STE 1.2 (D-derived reach; tuck attachment swapped
top=front/bottom=back) and stays PROVISIONAL. The mirror audit is run
INDEPENDENTLY (not inherited from STE 1.2). Pins: D-derived reach; correct
mirrored attachment + tuck columns + slit panels; structural equivalence
to STE 1.2 at the same dims (flat, cut area); wide-short cases supported;
1.1 byte-stable and differs from 1.2; committed matrix reproduces; sweep
clean; no provider calls.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.qualification.dtuck_qual import geometry_content_hashes
from apps.dielines.qualification.reverse_tuck_qual import (
    geometry_content_hashes as h11_rte,
)
from apps.dielines.qualification.runner import (
    adapter_for,
    fixtures_for,
    qualify,
    seeded_property_sweep,
    sweep_seed_for,
)
from apps.dielines.tests import provider_tripwire as tripwire

DOCS = Path("docs/qualification/reverse_tuck_end_carton_1_2")
KEY = "reverse_tuck_end_carton@1.2"
MED = {"width_mm": 60.0, "depth_mm": 20.0, "height_mm": 130.0,
       "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
       "bleed_mm": 3.0, "safe_margin_mm": 4.0}
MED_HASH = "f91bf512a266499e4091bf2a75230f2e"


def _params(tpl, ver, over):
    from apps.dielines.validators.schema import DielineInputJSON
    u = dict(MED, **over)
    return DielineInputJSON(
        template=tpl, template_version=ver, unit="mm",
        dimensions={"width_mm": u["width_mm"], "depth_mm": u["depth_mm"],
                    "height_mm": u["height_mm"]},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": u["glue_tab_mm"],
                      "board_thickness_mm": u["board_thickness_mm"],
                      "thickness_compensation": True},
        metadata={"product_name": "p", "product_type": "c"})


class Rte12MirrorAuditTests(TestCase):
    def setUp(self):
        self.adapter = adapter_for(KEY)

    def test_tuck_is_depth_derived(self):
        c = calculate_dieline(_params("reverse_tuck_end_carton", "1.2", {}))
        assert abs(c.derived["tuck_flap_height_mm"] - (20 + 16)) < 0.05

    def test_mirrored_attachment_and_columns(self):
        r = qualify(MED, self.adapter)
        assert r.supported
        by = {c["name"]: c for c in r.folded_checks}
        assert by["reverse_attachment_preserved"]["ok"]
        assert by["top_tuck_over_front_column"]["ok"]
        assert by["bottom_tuck_over_back_column"]["ok"]
        assert by["slits_on_mirrored_panels"]["ok"]

    def test_structural_equivalence_to_ste_12(self):
        """Mirror only swaps the tuck column: flat + cut area equal STE 1.2
        at the same dims, but the tuck panels differ."""
        rte = calculate_dieline(_params("reverse_tuck_end_carton", "1.2", {}))
        ste = calculate_dieline(_params("straight_tuck_end_carton", "1.2", {}))
        assert rte.flat_width_mm == ste.flat_width_mm
        assert rte.flat_height_mm == ste.flat_height_mm
        assert abs(rte.cut_polygon.area - ste.cut_polygon.area) < 1e-6
        assert rte.derived["top_tuck_panel"] != ste.derived["top_tuck_panel"]

    def test_no_self_intersection_or_cut_fold_conflict(self):
        from apps.dielines.exporters.structural_comparison import (
            geometry_integrity,
        )
        integ = geometry_integrity(calculate_dieline(
            _params("reverse_tuck_end_carton", "1.2", {})))
        assert not integ["cut_fold_conflict"]
        assert not integ["self_intersecting"]
        assert not integ["open_contour"]

    def test_wide_short_supported(self):
        r = qualify(dict(MED, width_mm=90.0, depth_mm=25.0, height_mm=92.0),
                    self.adapter)
        assert r.supported, (r.violations, r.invariant_failures)

    def test_boundaries_stable(self):
        fx = fixtures_for(KEY)
        assert qualify(fx["inside_dust_pair_boundary"], self.adapter).supported
        assert not qualify(fx["outside_dust_pair_boundary"],
                           self.adapter).supported

    def test_committed_matrix_reproduces(self):
        committed = json.loads(
            (DOCS / "qualification_matrix.json").read_text())
        for row in committed["rows"]:
            r = qualify(row["input"], self.adapter)
            outcome = ("SUPPORTED" if r.supported else
                       ("REJECTED_BY_DOMAIN" if r.violations
                        else "INVARIANT_FAILURE"))
            assert outcome == row["outcome"], (row["case"], outcome)
            if r.supported:
                assert r.geometry_hash == row["geometry_hash"]
                assert r.content_hashes == row["content_hashes"]

    def test_representative_hash_frozen(self):
        assert qualify(MED, self.adapter).geometry_hash == MED_HASH

    def test_property_sweep_clean(self):
        s = seeded_property_sweep(self.adapter, seed=sweep_seed_for(KEY),
                                  n_in_domain=50, n_random=100)
        assert s["failures"] == [], s["failures"][:3]
        assert s["supported"] > 0 and s["rejected_by_domain"] > 0

    def test_rte_stays_provisional_and_1v1_default(self):
        from apps.dielines import registry
        assert registry.resolve("reverse_tuck_end_carton").version == "1.1"
        assert registry.resolve("reverse_tuck_end_carton", "1.2").provisional


class Rte11StabilityTests(TestCase):
    def test_1v1_byte_stable_and_differs_from_1v2(self):
        c11 = calculate_dieline(_params("reverse_tuck_end_carton", "1.1", {}))
        c12 = calculate_dieline(_params("reverse_tuck_end_carton", "1.2", {}))
        assert c11.derived["tuck_flap_height_mm"] == 60 * 1.227
        assert h11_rte(c11) != geometry_content_hashes(c12)


class Rte12HygieneTests(TestCase):
    def test_qualifying_every_rte_12_fixture_makes_no_provider_call(self):
        """WI-S — converted from a §Y2-registered source-string guard.

        Was: four words are absent from `dtuck_qual.py`. Now: every committed
        RTE 1.2 fixture is qualified with every provider boundary armed to
        raise, and the module has to have executed. This is the mirrored
        caller of the module `Ste12HygieneTests` exercises.
        """
        import apps.dielines.qualification.dtuck_qual as mod
        with tripwire.armed(mod) as watch:
            adapter = adapter_for(KEY)
            fixtures = fixtures_for(KEY)
            outcomes = {name: qualify(case, adapter).supported
                        for name, case in fixtures.items()}
        assert any(outcomes.values()) and not all(outcomes.values()), outcomes
        tripwire.assert_clean(watch, mod)
