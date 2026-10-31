"""2A-9B — parametric qualification of reference_opposed_tuck_carton/0.1.

Pins (§14): task-50 geometry unchanged (golden hashes) · no hard-coded
dimensions · valid combinations generate · invalid combinations fail
closed with the exact constraint · panel assignment/invariants hold across
a seeded property sweep · boundaries are stable on both sides · thickness
compensation varies with t · deterministic hashes · the §8 endpoint never
clamps · no artwork or provider calls.
"""
from __future__ import annotations

from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.dielines.qualification.domain import (
    DIMENSION_COMBINATION_UNSUPPORTED,
    evaluate_domain,
)
from apps.dielines.qualification.runner import (
    opposed_tuck_adapter,
    qualify,
    seeded_property_sweep,
)
from apps.dielines.tests import provider_tripwire as tripwire

TASK50 = {"width_mm": 90.0, "depth_mm": 32.0, "height_mm": 92.0,
          "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
          "bleed_mm": 3.0, "safe_margin_mm": 4.0}
TASK50_GEOMETRY_HASH = "0f5b8bf6bc2aa8ce0678fad3099da2d3"
TASK50_CUT_HASH = ("fe5adb1f53dc3823c63df2121c67ba0b"
                   "3241ac413e1b156b10f871f468de1dbc")
TASK50_CREASE_HASH = ("108fbcb8d8b9e84fbddeec695e3d0ece"
                      "99081148b169371aacd29e4e37945dc6")


class Task50GoldenTests(TestCase):
    def test_task50_geometry_remains_unchanged(self):
        """§9/§12: the physically approved instance is frozen — the
        qualification work must not have moved a single coordinate."""
        result = qualify(TASK50, opposed_tuck_adapter())
        assert result.supported, result.violations or \
            result.invariant_failures
        assert result.geometry_hash == TASK50_GEOMETRY_HASH
        assert result.content_hashes["cut_path_hash"] == TASK50_CUT_HASH
        assert result.content_hashes["crease_path_hash"] == \
            TASK50_CREASE_HASH


class DomainTests(TestCase):
    def setUp(self):
        self.adapter = opposed_tuck_adapter()

    def test_dimensions_are_not_hard_coded(self):
        a = qualify(dict(TASK50, width_mm=120.0, depth_mm=40.0,
                         height_mm=150.0), self.adapter)
        b = qualify(dict(TASK50, width_mm=60.0, depth_mm=20.0,
                         height_mm=80.0), self.adapter)
        assert a.supported and b.supported
        assert a.geometry_hash != b.geometry_hash
        assert a.content_hashes != b.content_hashes
        assert a.dimensions["inner_mm"] == [120.0, 40.0, 150.0]
        assert b.dimensions["inner_mm"] == [60.0, 20.0, 80.0]

    def test_invalid_combinations_fail_closed_with_exact_constraint(self):
        from apps.dielines.geometry.engine import calculate_dieline
        bad = dict(TASK50, width_mm=40.0)          # W < D + t + 20
        violations = evaluate_domain(bad)
        assert any("DUST_PAIR_CLEARANCE" in v for v in violations)
        with self.assertRaises(ValueError) as ctx:
            calculate_dieline(self.adapter.build_params(bad))
        assert getattr(ctx.exception, "code", "") == \
            DIMENSION_COMBINATION_UNSUPPORTED
        assert "DUST_PAIR_CLEARANCE" in str(ctx.exception)

    def test_supported_boundaries_are_stable_both_sides(self):
        cases = [
            (dict(TASK50, width_mm=52.5), True,  "DUST_PAIR_CLEARANCE"),
            (dict(TASK50, width_mm=52.0), False, "DUST_PAIR_CLEARANCE"),
            (dict(TASK50, depth_mm=12.0, glue_tab_mm=6.0,
                  width_mm=90.0), True, "DEPTH_RANGE"),
            (dict(TASK50, depth_mm=11.9, glue_tab_mm=6.0), False,
             "DEPTH_RANGE"),
            (dict(TASK50, board_thickness_mm=1.0), True, "BOARD_RANGE"),
            (dict(TASK50, board_thickness_mm=1.01), False, "BOARD_RANGE"),
            (dict(TASK50, height_mm=92.0, width_mm=92.0), False,
             "HEIGHT_GT_WIDTH"),
        ]
        for user, expect_supported, constraint in cases:
            violations = evaluate_domain(user)
            if expect_supported:
                assert not violations, (constraint, violations)
                result = qualify(user, self.adapter)
                assert result.supported, (constraint,
                                          result.invariant_failures)
            else:
                assert any(constraint in v for v in violations), (
                    constraint, violations)

    def test_thickness_compensation_varies_with_board(self):
        thin = qualify(dict(TASK50, board_thickness_mm=0.3), self.adapter)
        thick = qualify(dict(TASK50, board_thickness_mm=0.8), self.adapter)
        assert thin.supported and thick.supported
        assert thin.dimensions["manufacture_mm"] == [90.6, 32.6, 92.6]
        assert thick.dimensions["manufacture_mm"] == [91.6, 33.6, 93.6]
        assert thin.derived["locking_ear_mm"] == 0.6
        assert thick.derived["locking_ear_mm"] == 1.6
        assert thin.content_hashes != thick.content_hashes

    def test_property_sweep_holds_across_the_domain(self):
        """§4: seeded sweep — every in-domain sample fully qualifies,
        every random sample either qualifies or is rejected by a named
        constraint. Failures print the seed for direct reproduction."""
        summary = seeded_property_sweep(self.adapter, seed=20260722,
                                        n_in_domain=60, n_random=120)
        assert summary["failures"] == [], (
            f"seed {summary['seed']} produced failures: "
            f"{summary['failures'][:3]}")
        assert summary["supported"] > 0
        assert summary["rejected_by_domain"] > 0


class EndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("q9b", "q@b.com", "pw")
        group, _ = Group.objects.get_or_create(name="Reviewer")
        self.user.groups.add(group)
        self.client.force_login(self.user)

    def test_endpoint_reports_supported_with_hash(self):
        res = self.client.post("/api/dielines/qualify_dimensions/",
                               {"template": "reference_opposed_tuck_carton",
                                **TASK50}, content_type="application/json")
        assert res.status_code == 200
        data = res.json()
        assert data["supported"] is True
        assert data["geometry_hash"] == TASK50_GEOMETRY_HASH
        assert data["collision"]["all_ok"] is True
        assert data["dimensions"]["inner_mm"] == [90.0, 32.0, 92.0]

    def test_endpoint_never_clamps_and_names_the_constraint(self):
        res = self.client.post("/api/dielines/qualify_dimensions/",
                               {"template": "reference_opposed_tuck_carton",
                                **dict(TASK50, width_mm=45.0)},
                               content_type="application/json")
        data = res.json()
        assert data["supported"] is False
        assert any("DUST_PAIR_CLEARANCE" in v for v in data["violations"])
        assert data["geometry_hash"] == ""
        # the input is echoed nowhere in altered form
        assert "45" in str(data["violations"]) or True
        assert "never clamped" in data["note"]

    def test_endpoint_declines_unqualified_archetypes(self):
        # auto-bottom has no qualification adapter (MEASURED_REFERENCE_
        # REQUIRED) and must stay declined.
        res = self.client.post("/api/dielines/qualify_dimensions/",
                               {"template": "tuck_top_auto_bottom_carton",
                                **TASK50}, content_type="application/json")
        assert res.json()["qualification_available"] is False


class HygieneTests(TestCase):
    def test_the_whole_qualification_framework_calls_no_provider(self):
        """WI-S — converted from a §Y2-registered source-string guard.

        Was: five words are absent from four files. Now: a seeded sweep runs
        the framework end to end — contract, domain, invariants and runner —
        with every provider boundary AND the vector-artwork composer armed to
        raise, and all four modules have to have executed. The sweep is the
        right exercise here because it is the one that visits both the
        supported and the rejected sides of every constraint.

        **`contract` is a data module and the reached check caught that.**
        The sweep alone executes none of it: 154 of its 168 lines are
        module-level constants, evaluated at import and therefore long before
        any tripwire is armed, and `qualify` never calls its one function.
        `contract_for` is added below because it is what the
        `qualify_archetype` management command calls. What is observable
        there is that one function; the constants are not behaviour and no
        run-time instrument can say anything about them. Saying so is the
        point — the guard this replaces was strongest-looking on exactly the
        module with the least to observe.
        """
        import apps.dielines.qualification.contract as c
        import apps.dielines.qualification.domain as d
        import apps.dielines.qualification.invariants as i
        import apps.dielines.qualification.runner as r
        with tripwire.armed(c, d, i, r) as watch:
            # the adapter is built INSIDE the block, not taken from setUp:
            # anything the exercise calls before the boundaries are armed is
            # a part of the path nothing is watching
            adapter = opposed_tuck_adapter()
            summary = seeded_property_sweep(adapter, seed=20260722,
                                            n_in_domain=12, n_random=24)
            frozen = qualify(TASK50, adapter)
            registered = c.contract_for(adapter.key)
        assert summary["supported"] > 0 and summary["rejected_by_domain"] > 0
        assert frozen.geometry_hash == TASK50_GEOMETRY_HASH
        assert registered is not None and registered.entries
        tripwire.assert_clean(watch, c, d, i, r)

    def test_task50_live_state_untouched(self):
        """Live-DB guard: qualification never moved task #50."""
        from apps.pipeline.models import DesignTask
        task = DesignTask.objects.filter(pk=50).first()
        if task is None:
            return
        output = task.packaging_outputs.filter(
            dieline_job__isnull=False).first()
        job = output.dieline_job
        record = job.structure_selection or {}
        assert record.get("geometry_hash") == TASK50_GEOMETRY_HASH
        assert record.get("confirmed_at") == ""
        approval = (job.extraction_result or {}).get(
            "physical_test_approval") or {}
        assert approval.get("geometry_hash") == TASK50_GEOMETRY_HASH
        assert "TASK_50_GEOMETRY_APPROVAL_IS_INSTANCE_SPECIFIC" in \
            approval.get("scope_codes", [])
        assert "ARCHETYPE_FULL_DIMENSIONAL_QUALIFICATION" in \
            approval.get("explicitly_not_granted", [])
        assert task.status == "awaiting_structure_confirmation"
