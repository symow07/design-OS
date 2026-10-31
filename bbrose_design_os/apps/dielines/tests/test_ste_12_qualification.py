"""2A-9D commit 2 — straight_tuck_end_carton/1.2 D-derived qualification.

Pins: 1.2 uses the D-derived tuck (reach = D + 16, no W-derived closure
depth); the lip-vs-height and dust-clamp defects are gone; wide-short
cartons 1.1 rejected are now supported; the W >= 1.262 D dust edge is
unchanged; 1.1 stays byte-stable and default; committed matrix reproduces;
sweep clean; no provider calls.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.qualification.dtuck_qual import geometry_content_hashes
from apps.dielines.qualification.legacy_tuck import (
    geometry_content_hashes as h11,
)
from apps.dielines.qualification.runner import (
    adapter_for,
    fixtures_for,
    qualify,
    seeded_property_sweep,
    sweep_seed_for,
)
from apps.dielines.tests import provider_tripwire as tripwire

DOCS = Path("docs/qualification/straight_tuck_end_carton_1_2")
KEY = "straight_tuck_end_carton@1.2"
MED = {"width_mm": 60.0, "depth_mm": 20.0, "height_mm": 130.0,
       "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
       "bleed_mm": 3.0, "safe_margin_mm": 4.0}
MED_HASH = "08d1b09fa1b10649066ac0e8d2ca6c8c"


def _params(ver, over):
    from apps.dielines.validators.schema import DielineInputJSON
    u = dict(MED, **over)
    return DielineInputJSON(
        template="straight_tuck_end_carton", template_version=ver,
        unit="mm",
        dimensions={"width_mm": u["width_mm"], "depth_mm": u["depth_mm"],
                    "height_mm": u["height_mm"]},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": u["glue_tab_mm"],
                      "board_thickness_mm": u["board_thickness_mm"],
                      "thickness_compensation": True},
        metadata={"product_name": "p", "product_type": "c"})


class Ste12ClosureTests(TestCase):
    def setUp(self):
        self.adapter = adapter_for(KEY)

    def test_tuck_is_depth_derived_not_width(self):
        for W, D, H in [(60, 20, 130), (90, 25, 92), (40, 30, 100)]:
            c = calculate_dieline(_params("1.2", {"width_mm": float(W),
                                  "depth_mm": float(D), "height_mm": float(H)}))
            assert abs(c.derived["tuck_flap_height_mm"] - (D + 16)) < 0.05, \
                (W, D, H)
            # NOT the W-ratio value
            assert abs(c.derived["tuck_flap_height_mm"] - W * 1.227) > 0.5

    def test_no_w_derived_closure_depth(self):
        # doubling W (D,H fixed) must NOT change the tuck reach
        a = calculate_dieline(_params("1.2", {"width_mm": 40.0}))
        b = calculate_dieline(_params("1.2", {"width_mm": 80.0}))
        assert a.derived["tuck_flap_height_mm"] == \
            b.derived["tuck_flap_height_mm"]
        # but doubling D must change it
        cc = calculate_dieline(_params("1.2", {"depth_mm": 40.0}))
        assert cc.derived["tuck_flap_height_mm"] != \
            a.derived["tuck_flap_height_mm"]

    def test_wide_short_cases_1v1_rejected_are_supported(self):
        for over in ({"width_mm": 90.0, "depth_mm": 25.0, "height_mm": 92.0},
                     {"width_mm": 200.0, "depth_mm": 40.0,
                      "height_mm": 250.0}):
            r = qualify(dict(MED, **over), self.adapter)
            assert r.supported, (over, r.violations, r.invariant_failures)
            by = {c["name"]: c for c in r.folded_checks}
            assert by["lip_is_fixed_under_half_height"]["ok"]
            assert by["dust_unclamped"]["ok"]

    def test_dust_clearance_edge_unchanged_from_1v1(self):
        # square 28x28x120 fails dust clearance in BOTH 1.1 and 1.2
        r = qualify(dict(MED, width_mm=28.0, depth_mm=28.0,
                         height_mm=120.0), self.adapter)
        assert not r.supported
        assert any("DUST_PAIR_CLEARANCE" in v for v in r.violations)

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


class Ste11StabilityTests(TestCase):
    def test_1v1_byte_stable_and_differs_from_1v2(self):
        c11 = calculate_dieline(_params("1.1", {}))
        c12 = calculate_dieline(_params("1.2", {}))
        # 1.1 unchanged (matches slice-1 committed medium_shallow-class value)
        assert c11.derived["tuck_flap_height_mm"] == 60 * 1.227
        # 1.2 is genuinely different geometry (not backward-compatible)
        assert h11(c11) != geometry_content_hashes(c12)

    def test_1v1_remains_default(self):
        from apps.dielines import registry
        assert registry.resolve("straight_tuck_end_carton").version == "1.1"


class Ste12EndpointTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("s12", "s@12.com", "pw")
        g, _ = Group.objects.get_or_create(name="Reviewer")
        user.groups.add(g)
        self.client.force_login(user)

    def test_endpoint_uses_current_1v1_not_1v2(self):
        # the endpoint qualifies the CURRENT version (1.1); the wide-short
        # case must still be rejected there (no default switch)
        res = self.client.post(
            "/api/dielines/qualify_dimensions/",
            {"template": "straight_tuck_end_carton",
             "width_mm": 90.0, "depth_mm": 25.0, "height_mm": 92.0,
             "board_thickness_mm": 0.5, "glue_tab_mm": 12.0},
            content_type="application/json").json()
        assert res["supported"] is False
        assert any("TUCK_LIP_VS_HEIGHT" in v for v in res["violations"])


class Ste12HygieneTests(TestCase):
    def test_qualifying_every_ste_12_fixture_makes_no_provider_call(self):
        """WI-S — converted from a §Y2-registered source-string guard.

        Was: four words are absent from `dtuck_qual.py`. Now: every committed
        STE 1.2 fixture is qualified with every provider boundary armed to
        raise, and the module has to have executed. `dtuck_qual` is shared
        with RTE 1.2, so its sibling test exercises the other caller — the
        two together are what make the D-derived module's coverage real.
        """
        import apps.dielines.qualification.dtuck_qual as mod
        with tripwire.armed(mod) as watch:
            adapter = adapter_for(KEY)
            fixtures = fixtures_for(KEY)
            outcomes = {name: qualify(case, adapter).supported
                        for name, case in fixtures.items()}
        assert any(outcomes.values()) and not all(outcomes.values()), outcomes
        tripwire.assert_clean(watch, mod)
