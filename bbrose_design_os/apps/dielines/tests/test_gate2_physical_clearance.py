"""2A-9E commit 4 — Gate-2 exact-hash FIT_PASS clearance (narrowly scoped).

The physical blocker (PHYSICAL_SAMPLE_VALIDATION_REQUIRED) on a STE/RTE 1.2
structure clears ONLY when the EXACT geometry hash has a recorded FIT_PASS,
and clearing it must NOT open Gate 2 (independent blockers still apply).
Discriminating tests per the advisor:
  1. exact-hash FIT_PASS clears only the physical structural blocker;
  2. with that FIT_PASS, Gate 2 still fails on independent blockers;
  3. a FIT_PASS for a different hash does not clear;
plus a live check: task #50 and STE/RTE 1.2 with no FIT_PASS still block.
"""
from __future__ import annotations

import json
import os
import shutil
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.dielines import registry
from apps.dielines.analysis.reconciliation import reconcile_dimensions
from apps.dielines.exporters.structural_comparison import build_checklist
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.models import DielineJob
from apps.dielines.services.physical_validation import (
    record_physical_validation,
)
from apps.dielines.validators.production import _check_structural
from apps.dielines.validators.production import ProductionReport
from apps.dielines.validators.schema import DielineInputJSON

PARAMS = {"width_mm": 60.0, "depth_mm": 20.0, "height_mm": 130.0,
          "bleed_mm": 3.0, "safe_margin_mm": 4.0, "glue_tab_mm": 12.0,
          "board_thickness_mm": 0.5}


def _coords():
    return calculate_dieline(DielineInputJSON(
        template="straight_tuck_end_carton", template_version="1.2",
        unit="mm",
        dimensions={"width_mm": 60.0, "depth_mm": 20.0, "height_mm": 130.0},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": 12.0, "board_thickness_mm": 0.5,
                      "thickness_compensation": True},
        metadata={"product_name": "P", "product_type": "carton"}))


def _hash():
    return registry.geometry_hash("straight_tuck_end_carton", "1.2", PARAMS)


def _setup(media_root, *, fit_pass_hash=None):
    coords = _coords()
    job = DielineJob.objects.create(
        template_type="straight_tuck_end_carton", scenario="B",
        input_json={}, extraction_result={})
    ghash = _hash()
    record = {"template_id": "straight_tuck_end_carton",
              "template_version": "1.2", "parameters": PARAMS,
              "confirmed_at": "2026-07-23T10:00:00Z", "confirmed_by": "r",
              "geometry_hash": ghash,
              "panel_order": [p.name for p in coords.panels]}
    job.structure_selection = record
    job.save(update_fields=["structure_selection"])
    if fit_pass_hash:
        user = User.objects.create_user("g2", "g@2.com", "pw")
        record_physical_validation(
            job, user, template_key="straight_tuck_end_carton/1.2",
            geometry_hash=fit_pass_hash, outcome="FIT_PASS",
            sample_printed_at_100pct=True)
    # checklist file (so the other structural checks have data)
    d = os.path.join(media_root, "dielines", str(job.id))
    os.makedirs(d, exist_ok=True)
    checklist = build_checklist(
        coords, reconcile_dimensions(coords, coords.dimensions.inner,
                                     coords.dimensions.outer))
    json.dump(checklist, open(
        os.path.join(d, f"{job.id}_structural_checklist.json"), "w"))
    output = SimpleNamespace(
        spec_sheet={"template": "straight_tuck_end_carton",
                    "template_version": "1.2",
                    "panel_order": [p.name for p in coords.panels]},
        dieline_job=job)
    return output


class Gate2PhysicalClearanceTests(TestCase):
    def test_exact_hash_fit_pass_clears_only_the_physical_blocker(self):
        import tempfile
        mr = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mr, True)
        with override_settings(MEDIA_ROOT=mr):
            out = _setup(mr, fit_pass_hash=_hash())
            r = ProductionReport()
            _check_structural(r, out, out.spec_sheet,
                              "straight_tuck_end_carton", True)
            assert "PHYSICAL_SAMPLE_VALIDATION_REQUIRED" not in r.codes()
            assert any("has recorded FIT_PASS" in w for w in r.warnings), r.warnings   # §BH70(3): said, as information

    def test_bh70_no_fit_pass_is_said_and_never_blocks(self):
        """[§BH70(3), his words: "A physical sample is never required to finish a design (a colleague test-fits; that is
        not the system's job)." This test read `test_no_fit_pass_blocks` and asserted the code among the failures.]
        With no FIT_PASS the untested geometry is a warning, never a failure."""
        import tempfile
        mr = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mr, True)
        with override_settings(MEDIA_ROOT=mr):
            out = _setup(mr, fit_pass_hash=None)
            r = ProductionReport()
            _check_structural(r, out, out.spec_sheet,
                              "straight_tuck_end_carton", True)
            assert "PHYSICAL_SAMPLE_VALIDATION_REQUIRED" not in r.codes()
            assert [w for w in r.warnings if w.startswith("PHYSICAL_SAMPLE_VALIDATION_REQUIRED:")
                    and registry.PHYSICAL_SAMPLE_INFORMATION in w], r.warnings

    def test_bh70_a_fit_pass_for_another_geometry_is_not_read_as_this_ones(self):
        """[§BH70(3): this test read `test_different_hash_fit_pass_does_not_clear`.] A FIT_PASS recorded for another
        geometry is still not said as this one's — the warning says the sample is untested — and nothing blocks."""
        import tempfile
        mr = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mr, True)
        with override_settings(MEDIA_ROOT=mr):
            out = _setup(mr, fit_pass_hash="deadbeef" * 8)
            r = ProductionReport()
            _check_structural(r, out, out.spec_sheet,
                              "straight_tuck_end_carton", True)
            assert "PHYSICAL_SAMPLE_VALIDATION_REQUIRED" not in r.codes()
            assert any(registry.PHYSICAL_SAMPLE_INFORMATION in w for w in r.warnings), r.warnings

    def test_clearing_physical_does_not_open_gate2_output_intent(self):
        """With the exact-hash FIT_PASS, the physical structural blocker is
        gone, but the full Gate-2 evaluation still fails on the independent
        output-intent (ICC) blocker — clearing physical != Gate 2 opens."""
        import tempfile
        from apps.dielines.validators.production import evaluate_production
        mr = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mr, True)
        with override_settings(MEDIA_ROOT=mr):
            out = _setup(mr, fit_pass_hash=_hash())
            # spec has no output_intent / ICC -> MISSING_OUTPUT_INTENT stands
            out.spec_sheet["output_intent_missing"] = True
            out.design_preview_ai = SimpleNamespace(name="")
            out.production_pdf = SimpleNamespace(name="")
            report = evaluate_production(
                out, expected_template="straight_tuck_end_carton",
                require_structure_confirmation=True)
            codes = report.codes()
            assert "PHYSICAL_SAMPLE_VALIDATION_REQUIRED" not in codes
            assert report.ready is False  # other blockers keep Gate 2 shut


class LiveNothingClearedTests(TestCase):
    def test_task50_and_1v2_still_block_with_no_fit_pass(self):
        """Live guard: no real FIT_PASS exists, so nothing is cleared."""
        from apps.dielines.services.physical_validation import (
            promotion_blockers,
        )
        from apps.pipeline.models import DesignTask
        task = DesignTask.objects.filter(pk=50).first()
        if task is not None:
            out = task.packaging_outputs.filter(
                dieline_job__isnull=False).first()
            job = out.dieline_job
            rec = job.structure_selection or {}
            assert promotion_blockers(
                job, template_key="reference_opposed_tuck_carton/0.1",
                geometry_hash=rec.get("geometry_hash", "")), \
                "task #50 must still block (no FIT_PASS)"
