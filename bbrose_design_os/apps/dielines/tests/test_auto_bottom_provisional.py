"""Auto-bottom provisional classification (Phase 2A-6A).

`tuck_top_auto_bottom_carton/1.1` has correct cut/fold boundaries but its
closure MECHANICS are still an approximation, so it is production-ineligible
until a measured crash-lock reference die exists. It stays available for
technical inspection; it never reaches production.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.dielines import registry
from apps.dielines.exporters.structural_comparison import geometry_integrity
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.schema import DielineInputJSON
from apps.pipeline.services.template_selection import select_template

AUTO = "tuck_top_auto_bottom_carton"
STE = "straight_tuck_end_carton"
RTE = "reverse_tuck_end_carton"
SKYNTE = "skynte_foundation_tuck_carton"

PRODUCTION_ELIGIBLE = {
    f"{STE}/1.1", f"{RTE}/1.1", f"{SKYNTE}/1.0",
}


def _params(template_id, version=None):
    return DielineInputJSON(
        template=template_id, unit="mm", template_version=version,
        dimensions={"width_mm": 42.0, "depth_mm": 32.0, "height_mm": 140.0},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": 10.0, "board_thickness_mm": 0.30,
                      "thickness_compensation": True},
        metadata={"product_name": "p", "product_type": "t"},
    )


class TestClassification:
    def test_auto_bottom_11_is_provisional_and_ineligible(self):
        defn = registry.resolve(AUTO, "1.1")
        assert defn.structure_status == registry.STRUCTURE_PROVISIONAL
        assert defn.production_ready is False
        assert defn.ineligibility_code == registry.MEASURED_REFERENCE_REQUIRED

    def test_limitations_are_recorded_for_review(self):
        defn = registry.resolve(AUTO, "1.1")
        joined = " ".join(defn.structural_limitations).lower()
        for phrase in ("crash-lock", "adhesive", "diagonal", "merge"):
            assert phrase in joined, f"limitation not recorded: {phrase}"

    def test_it_is_not_described_as_a_finished_production_die(self):
        notes = " ".join(registry.resolve(AUTO, "1.1").notes)
        assert "NOT a finished auto-bottom production die" in notes
        assert "measured crash-lock reference die" in notes

    def test_implementation_and_history_are_preserved(self):
        # still buildable for inspection, and 1.0 still reproducible
        assert calculate_dieline(_params(AUTO, "1.1")) is not None
        assert calculate_dieline(_params(AUTO, "1.0")) is not None
        assert registry.versions_of(AUTO) == ["1.0", "1.1"]

    def test_cut_fold_validation_is_not_weakened(self):
        coords = calculate_dieline(_params(AUTO, "1.1"))
        integrity = geometry_integrity(coords)
        assert integrity["cut_fold_conflict"] is False
        assert integrity["cut_fold_conflict_segments"] == []


class TestProductionChooser:
    def test_chooser_offers_exactly_the_approved_set(self):
        offered = {d.key for d in registry.production_templates()}
        assert offered == PRODUCTION_ELIGIBLE

    def test_auto_bottom_is_excluded_at_both_versions(self):
        offered = {d.key for d in registry.production_templates()}
        assert f"{AUTO}/1.1" not in offered
        assert f"{AUTO}/1.0" not in offered

    def test_generic_1_0_versions_excluded(self):
        offered = {d.key for d in registry.production_templates()}
        assert f"{STE}/1.0" not in offered
        assert f"{RTE}/1.0" not in offered

    def test_other_templates_remain_selectable(self):
        for template_id, version in ((STE, "1.1"), (RTE, "1.1"), (SKYNTE, "1.0")):
            assert registry.is_production_eligible(template_id, version)
            assert registry.is_production_eligible(template_id)  # current

    def test_unknown_and_excluded_versions_fail_closed(self):
        assert registry.is_production_eligible(AUTO) is False
        assert registry.is_production_eligible("no_such_template") is False
        assert registry.is_production_eligible(STE, "9.9") is False


class TestExplicitSelection:
    @staticmethod
    def _task():
        return SimpleNamespace(product=None)

    def test_explicit_auto_bottom_selection_is_refused(self):
        sel = select_template(self._task(), user_template=AUTO,
                              dimensions={"width_mm": 42.0, "depth_mm": 32.0,
                                          "height_mm": 140.0})
        assert sel.resolved is False
        assert sel.code == registry.MEASURED_REFERENCE_REQUIRED
        assert sel.structure_status == registry.STRUCTURE_PROVISIONAL
        # the reasons name the actual limitations, not a generic refusal
        assert any("crash-lock" in r for r in sel.reasons)

    def test_refusal_offers_only_production_templates(self):
        sel = select_template(self._task(), user_template=AUTO)
        keys = {c["key"] for c in sel.candidates}
        assert keys == PRODUCTION_ELIGIBLE

    def test_superseded_generic_selection_returns_its_own_code(self):
        """A defective version and a provisional structure are different
        problems and must not share one code."""
        # 2A-9E: STE requires explicit version confirmation now; with the
        # legacy version pinned it resolves to 1.1 (its own code path, not a
        # shared defective/provisional code).
        sel = select_template(self._task(), user_template=STE,
                              user_version="1.1")
        assert sel.resolved is True
        assert sel.version == "1.1"

    def test_eligible_templates_still_resolve(self):
        # 2A-9E: STE/RTE need an explicit version (recommended-corrected
        # policy); Skynte has no correction and resolves bare.
        for template_id, ver in ((STE, "1.1"), (RTE, "1.1"), (SKYNTE, None)):
            sel = select_template(self._task(), user_template=template_id,
                                  user_version=ver,
                                  dimensions={"width_mm": 42.0,
                                              "depth_mm": 32.0,
                                              "height_mm": 140.0})
            assert sel.resolved is True, template_id


class TestGate2Refusal:
    """Gate 2 must return MEASURED_REFERENCE_REQUIRED, not a generic code."""

    def _report(self, template_id, version, tmp_path, media_root):
        from .test_production_validator import (
            _checklist,
            _inventory,
            _output,
        )
        spec = {"template": template_id, "required_template": template_id,
                "template_version": version}
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory(), spec=spec)
        out.dieline_job.structure_selection = {
            "template_id": template_id, "template_version": version,
            "parameters": {}, "confirmed_at": "2026-07-20T10:00:00Z",
            "geometry_hash": registry.geometry_hash(template_id, version, {}),
        }
        from apps.dielines.validators.production import evaluate_production
        return evaluate_production(out, expected_template=template_id)

    def test_auto_bottom_blocked_with_measured_reference_required(
            self, tmp_path, media_root):
        report = self._report(AUTO, "1.1", tmp_path, media_root)
        assert registry.MEASURED_REFERENCE_REQUIRED in report.codes()
        failure = next(f for f in report.failures
                       if f["code"] == registry.MEASURED_REFERENCE_REQUIRED)
        assert failure["structure_status"] == registry.STRUCTURE_PROVISIONAL
        assert "measured production die" in failure["detail"]

    def test_generic_1_0_blocked_with_the_version_code(
            self, tmp_path, media_root):
        report = self._report(STE, "1.0", tmp_path, media_root)
        assert "NON_PRODUCTION_TEMPLATE_VERSION" in report.codes()
        assert registry.MEASURED_REFERENCE_REQUIRED not in report.codes()

    def test_eligible_versions_raise_neither_code(self, tmp_path, media_root):
        for template_id, version in ((STE, "1.1"), (RTE, "1.1")):
            codes = self._report(template_id, version, tmp_path,
                                 media_root).codes()
            assert "NON_PRODUCTION_TEMPLATE_VERSION" not in codes
            assert registry.MEASURED_REFERENCE_REQUIRED not in codes


@pytest.fixture()
def media_root(tmp_path):
    from django.test import override_settings
    root = tmp_path / "media"
    root.mkdir()
    with override_settings(MEDIA_ROOT=str(root)):
        yield str(root)
