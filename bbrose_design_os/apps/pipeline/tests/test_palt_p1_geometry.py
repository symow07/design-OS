"""PALT-M4 — PALT-P1 parametric geometry tests.

Deterministic and non-rendering. Guards the structural promises: component
independence, shared identities across states, resolved (never eyeballed)
dimensions, fail-closed validation and no automatic shrinking.
"""
import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import palette_geometry as pg
from apps.pipeline.services import palette_geometry_validators as V
from apps.pipeline.services.palette_mechanism_geometry import (
    HINGE, LID_GROUP, OPEN_REVIEW_ANGLE_DEG, PALT_P1_MECHANISM,
    PREMIUM_ENVELOPE, STATES, assembly_manifest, build_components,
    compose_state, resolve_dimensions)
from apps.pipeline.services.palette_stackup_engine import ALLOWANCES


class ComponentTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, cls.dims = build_components()

    def test_components_are_generated_independently(self):
        # nine pans, nine pocket rings, tray, shells, mirror, mechanism
        assert len(self.comps) >= 25
        for i in range(1, 10):
            assert f"pan_{i}" in self.comps
            assert f"pocket_ring_{i}" in self.comps
        for name in ("base_outer_shell", "base_wall_ring", "inner_tray",
                     "lid_outer_shell", "lid_inner_structure",
                     "mirror_recess", "mirror", "hinge_pin",
                     "clasp_hook", "clasp_detent",
                     "hinge_wall_thickening", "clasp_wall_thickening"):
            assert name in self.comps, name

    def test_every_component_has_an_independent_identity(self):
        ids = [c["mesh_identity"] for c in self.comps.values()]
        # pans are identical solids at different positions, so identities
        # differ by position — none may be missing
        assert all(ids)
        assert len(set(ids)) >= len(ids) - 0   # positions differ

    def test_identities_are_deterministic(self):
        again, _ = build_components()
        assert {n: c["mesh_identity"] for n, c in self.comps.items()} == \
            {n: c["mesh_identity"] for n, c in again.items()}

    def test_exact_outer_envelope(self):
        assert self.dims["envelope_mm"] == list(PREMIUM_ENVELOPE)
        v = np.concatenate([c["vertices"] for c in self.comps.values()])
        w, d, h = PREMIUM_ENVELOPE
        assert abs(v[:, 0].min() + w / 2) < 0.05
        assert abs(v[:, 0].max() - w / 2) < 0.05
        assert abs(v[:, 1].min() + d / 2) < 0.05
        assert abs(v[:, 1].max() - d / 2) < 0.05
        assert v[:, 2].min() >= -1e-6 and v[:, 2].max() <= h + 1e-6

    def test_nine_pans_placed_on_the_resolved_pitch(self):
        pans = [self.comps[f"pan_{i}"] for i in range(1, 10)]
        centres = sorted({(round(float(p["vertices"][:, 0].mean()), 3),
                           round(float(p["vertices"][:, 1].mean()), 3))
                          for p in pans})
        assert len(centres) == 9
        xs = sorted({c[0] for c in centres})
        assert len(xs) == 3
        assert abs((xs[1] - xs[0]) - self.dims["pitch_mm"]) < 1e-6

    def test_pan_and_pocket_clearance_is_positive(self):
        clear = (self.dims["pocket_diameter_mm"]
                 - self.dims["pan_diameter_mm"]) / 2.0
        assert clear > 0

    def test_tray_floor_and_stackup_are_resolved_not_authored(self):
        d = self.dims
        assert d["tray_floor_mm"] > 0
        derived = (d["base_thickness_mm"] + d["tray_floor_mm"]
                   + d["pan_depth_mm"] + ALLOWANCES["pan_proud_recess_mm"])
        assert d["base_height_mm"] > derived - 1e-6
        assert abs(d["base_height_mm"] + d["lid_height_mm"]
                   + d["parting_gap_mm"] - d["envelope_mm"][2]) < 1e-6

    def test_mirror_recess_retains_the_mirror(self):
        mirror = self.comps["mirror"]["vertices"]
        recess = self.comps["mirror_recess"]["vertices"]
        assert mirror[:, 0].min() >= recess[:, 0].min() - 1e-6
        assert mirror[:, 0].max() <= recess[:, 0].max() + 1e-6
        assert mirror[:, 2].min() >= recess[:, 2].min() - 1e-6

    def test_hinge_axis_alignment_and_pin_engagement(self):
        barrels = [self.comps[f"hinge_barrel_{i}"] for i in range(1, 4)]
        ys = [float(b["vertices"][:, 1].mean()) for b in barrels]
        zs = [float(b["vertices"][:, 2].mean()) for b in barrels]
        assert max(ys) - min(ys) < 1e-6
        assert max(zs) - min(zs) < 1e-6
        pin = self.comps["hinge_pin"]["vertices"]
        assert abs(float(pin[:, 1].mean()) - ys[0]) < 1e-6
        assert HINGE["pin_radius_mm"] < HINGE["barrel_radius_mm"]
        span = max(float(b["vertices"][:, 0].max()) for b in barrels) - \
            min(float(b["vertices"][:, 0].min()) for b in barrels)
        assert (pin[:, 0].max() - pin[:, 0].min()) + 1e-6 >= span

    def test_barrel_fits_inside_the_thickened_hinge_wall(self):
        # the wall-integrated envelope was APPLIED, not the barrel shrunk
        assert self.dims["hinge_wall_mm"] > self.dims["case_wall_mm"]
        assert 2 * HINGE["barrel_radius_mm"] <= \
            self.dims["hinge_wall_mm"] + 1e-6

    def test_clasp_hook_and_detent_overlap_in_x(self):
        hook = self.comps["clasp_hook"]["vertices"]
        detent = self.comps["clasp_detent"]["vertices"]
        assert min(hook[:, 0].max(), detent[:, 0].max()) > \
            max(hook[:, 0].min(), detent[:, 0].min())


class StateTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, cls.dims = build_components()

    def test_all_states_compose(self):
        for state in STATES:
            out = compose_state(self.comps, self.dims, state)
            assert out, state

    def test_open_and_closed_share_component_identities(self):
        closed = compose_state(self.comps, self.dims, "CLOSED")
        for state in ("OPEN_90", "OPEN_REVIEW_ANGLE", "EXPLODED"):
            other = compose_state(self.comps, self.dims, state)
            for name, c in other.items():
                assert closed[name]["mesh_identity"] == c["mesh_identity"], \
                    (state, name)

    def test_closed_state_is_flush(self):
        closed = compose_state(self.comps, self.dims, "CLOSED")
        v = np.concatenate([c["vertices"] for c in closed.values()])
        assert abs(v[:, 2].max() - self.dims["envelope_mm"][2]) < 0.05

    def test_opening_direction_is_upward(self):
        closed = compose_state(self.comps, self.dims, "CLOSED")
        opened = compose_state(self.comps, self.dims, "OPEN_90")
        assert (opened["lid_outer_shell"]["vertices"][:, 2].max()
                > closed["lid_outer_shell"]["vertices"][:, 2].max() + 40)

    def test_open_angle_is_configurable_without_rebuilding(self):
        a = compose_state(self.comps, self.dims, "OPEN_REVIEW_ANGLE",
                          open_angle_deg=100.0)
        b = compose_state(self.comps, self.dims, "OPEN_REVIEW_ANGLE",
                          open_angle_deg=130.0)
        assert not np.allclose(a["lid_outer_shell"]["vertices"],
                               b["lid_outer_shell"]["vertices"])
        # identities are unchanged — the case was NOT rebuilt
        assert a["lid_outer_shell"]["mesh_identity"] == \
            b["lid_outer_shell"]["mesh_identity"]

    def test_exploded_state_separates_components(self):
        closed = compose_state(self.comps, self.dims, "CLOSED")
        exploded = compose_state(self.comps, self.dims, "EXPLODED")
        assert (exploded["lid_outer_shell"]["vertices"][:, 2].min()
                > closed["lid_outer_shell"]["vertices"][:, 2].min() + 20)

    def test_subset_states_contain_the_right_groups(self):
        lid = compose_state(self.comps, self.dims, "LID_ONLY")
        assert set(lid) <= set(LID_GROUP)
        base = compose_state(self.comps, self.dims, "BASE_ONLY")
        assert "lid_outer_shell" not in base
        tray = compose_state(self.comps, self.dims, "TRAY_ONLY")
        assert "inner_tray" in tray and "pan_1" in tray

    def test_unknown_state_is_refused(self):
        with self.assertRaises(ValueError):
            compose_state(self.comps, self.dims, "FLOATING")


class ValidatorTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, cls.dims = build_components()

    def test_premium_envelope_validates_cleanly(self):
        report = V.validate_assembly(self.comps, self.dims)
        assert report["valid"], report["findings"]

    def test_all_meshes_are_manifold(self):
        diag = V.geometry_diagnostics(self.comps)
        for name, entry in diag["per_component"].items():
            assert entry["non_manifold_edges"] == 0, (name, entry["codes"])

    def test_component_outside_envelope_is_rejected(self):
        comps = dict(self.comps)
        comps["stray"] = pg.transform(comps["pan_1"],
                                      translate=(0, 0, 120.0))
        report = V.validate_assembly(comps, self.dims)
        assert V.COMPONENT_OUTSIDE_ENVELOPE in {f["code"]
                                                for f in report["findings"]}

    def test_pan_collision_is_rejected(self):
        comps = dict(self.comps)
        comps["pan_2"] = pg.transform(
            comps["pan_2"],
            translate=(self.comps["pan_1"]["vertices"][:, 0].mean()
                       - self.comps["pan_2"]["vertices"][:, 0].mean(), 0, 0))
        report = V.validate_assembly(comps, self.dims)
        assert V.PAN_TO_PAN_COLLISION in {f["code"]
                                          for f in report["findings"]}

    def test_missing_detent_is_rejected(self):
        comps = {n: c for n, c in self.comps.items() if n != "clasp_detent"}
        report = V.validate_assembly(comps, self.dims)
        assert V.CLASP_HOOK_WITHOUT_DETENT in {f["code"]
                                               for f in report["findings"]}

    def test_missing_pin_is_rejected(self):
        comps = {n: c for n, c in self.comps.items() if n != "hinge_pin"}
        report = V.validate_assembly(comps, self.dims)
        assert V.INVALID_PIN_ENGAGEMENT in {f["code"]
                                            for f in report["findings"]}

    def test_misaligned_hinge_is_rejected(self):
        comps = dict(self.comps)
        comps["hinge_barrel_2"] = pg.transform(comps["hinge_barrel_2"],
                                               translate=(0, -2.0, 0))
        report = V.validate_assembly(comps, self.dims)
        assert V.MISALIGNED_HINGE_AXIS in {f["code"]
                                           for f in report["findings"]}

    def test_lid_to_powder_collision_is_rejected(self):
        comps = dict(self.comps)
        comps["mirror"] = pg.transform(comps["mirror"],
                                       translate=(0, 0, -4.0))
        report = V.validate_assembly(comps, self.dims)
        assert V.LID_TO_POWDER_COLLISION in {f["code"]
                                             for f in report["findings"]}

    def test_validators_never_repair(self):
        before = {n: c["mesh_identity"] for n, c in self.comps.items()}
        V.validate_assembly(self.comps, self.dims)
        after = {n: c["mesh_identity"] for n, c in self.comps.items()}
        assert before == after


class ManifestTests(SimpleTestCase):
    def test_manifest_records_authority_and_provenance(self):
        comps, dims = build_components()
        manifest = assembly_manifest(comps, dims)
        auth = manifest["authority"]
        assert auth["MANUFACTURING_GEOMETRY"] == "NOT_ESTABLISHED"
        assert auth["PALT_P1_FINAL_DIMENSIONS"] == "NOT_APPROVED"
        assert auth["PALT_P1_OWNER_APPROVAL"] == "PENDING_VISUAL_REVIEW"
        mech = manifest["mechanism"]
        assert mech["hinge_edge"] == "TOP_EDGE"
        assert mech["clasp_edge"] == "BOTTOM_EDGE"
        assert mech["opening_direction"] == "UPWARD"
        assert mech["front_artwork_orientation"] == "CLASP_AT_BOTTOM"
        assert mech["open_review_angle_deg"] == OPEN_REVIEW_ANGLE_DEG
        assert "NOT_MANUFACTURER_CONFIRMED" in mech["open_angle_provenance"]
        assert manifest["contract_spec"]["case"]["outer_width"]["provenance"]

    def test_mechanism_matches_the_owner_decision(self):
        assert PALT_P1_MECHANISM.hinge_strategy == \
            "WALL_INTEGRATED_PIN_HINGE"
        assert PALT_P1_MECHANISM.clasp_strategy == \
            "WALL_INTEGRATED_SNAP_CLASP"
        assert PALT_P1_MECHANISM.retention_strategy == "ADHESIVE_FIXED"

    def test_stress_fixture_envelope_is_smaller_and_separately_labelled(self):
        premium = resolve_dimensions()
        stress = resolve_dimensions((103.5, 101.3, 15.0), gap=2.0,
                                    margin=3.0)
        assert stress["envelope_mm"][0] < premium["envelope_mm"][0]
        assert stress["inter_pan_gap_mm"] < premium["inter_pan_gap_mm"]
        assert stress["outer_margin_mm"] < premium["outer_margin_mm"]
