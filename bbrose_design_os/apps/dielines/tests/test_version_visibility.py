"""2A-9E commit 3 — version is visible and classified everywhere.

Pins: structure_presentation carries the version + its new-selection class;
the Review Board specification shows the version; the chooser JS renders
recommended vs legacy and never hides the recommended corrected version.
"""
from __future__ import annotations

from pathlib import Path

from django.test import TestCase

from apps.dielines.models import DielineJob
from apps.pipeline.services import structure_selection as ss
from apps.pipeline.services.template_selection import TemplateSelection


def _job_with(template_id, version):
    job = DielineJob.objects.create(
        template_type=template_id, scenario="B", input_json={},
        extraction_result={})
    sel = TemplateSelection(resolved=True, template_id=template_id,
                            version=version, source="EXPLICIT_USER_CONFIRMATION")
    rec = ss.build_structure_record(sel, {
        "width_mm": 60.0, "depth_mm": 20.0, "height_mm": 130.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0, "glue_tab_mm": 12.0,
        "board_thickness_mm": 0.5})
    ss.save_structure_record(job, rec)
    return job


class StructurePresentationVersionTests(TestCase):
    def test_1v2_is_shown_as_recommended(self):
        job = _job_with("straight_tuck_end_carton", "1.2")
        pres = ss.structure_presentation(job)
        assert pres["template_version"] == "1.2"
        assert pres["new_selection_class"] == "RECOMMENDED_CORRECTED_VERSION"
        assert pres["recommended_version"] == "1.2"

    def test_1v1_is_shown_as_legacy(self):
        job = _job_with("straight_tuck_end_carton", "1.1")
        pres = ss.structure_presentation(job)
        assert pres["template_version"] == "1.1"
        assert pres["new_selection_class"] == "LEGACY_REPRODUCTION_ONLY"
        assert pres["recommended_version"] == "1.2"

    def test_version_never_omitted(self):
        for tid, ver in [("straight_tuck_end_carton", "1.2"),
                         ("skynte_foundation_tuck_carton", "1.0")]:
            pres = ss.structure_presentation(_job_with(tid, ver))
            assert pres["template_version"] == ver
            assert pres["new_selection_class"]


class ChooserJsTests(TestCase):
    def test_chooser_renders_recommended_and_legacy_by_class(self):
        js = Path("static/js/gates.js").read_text()
        assert "RECOMMENDED_CORRECTED_VERSION" in js
        assert "LEGACY_REPRODUCTION_ONLY" in js
        # the recommended card is not gated behind production_ready anymore
        assert "physical_validation_required" in js
        # [the owner's goal of 2026-09-25, (d): the legacy versions stay folded behind their own line, in words — it read
        # "Advanced: legacy versions (superseded for new selection)"]
        assert "Earlier versions — kept for the designs made with them" in js
        assert '<details class="tech struct-legacy">' in js

    def test_selector_carries_version(self):
        js = Path("static/js/gates.js").read_text()
        assert "data-version" in js
        assert "selectedStructureTemplate" in js
