"""Phase 2A-9 — customer-grade STE archetype (§11 mandated facts).

Pins: 90×32×92/0.5 preserved · 25 mm cannot return · exact panel sequence ·
slit-locks stay cut · creases stop at cut interruptions · deterministic
curved shoulders · no dust collision · full-contour bleed · zero cut/fold
overlap · deterministic output · provisional cannot pass Gate 2 · physical
FIT_PASS required · supplier die overrides the archetype · screenshot never
embedded · task-50 artwork not remapped · no provider calls.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase

from apps.dielines import registry
from apps.dielines.geometry.ecma_ste import (
    ECMA_A20_20_01_01_STE_CARTON_V0_1,
    EcmaSteGeometryError,
    calculate_ecma_ste,
    collision_report,
    geometry_content_hashes,
)
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.models import DielineJob
from apps.dielines.services.physical_validation import (
    ALLOWED_OUTCOMES,
    PhysicalValidationError,
    promotion_blockers,
    record_physical_validation,
)
from apps.dielines.tests import provider_tripwire as tripwire
from apps.dielines.validators.schema import DielineInputJSON

TASK50_INNER = (90.0, 32.0, 92.0)
BOARD = 0.5


def _params(width=90.0, depth=32.0, height=92.0, board=BOARD):
    return DielineInputJSON(
        template="ecma_a20_20_01_01_ste_carton", template_version="0.1",
        unit="mm",
        dimensions={"width_mm": width, "depth_mm": depth,
                    "height_mm": height},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": 12.0, "board_thickness_mm": board,
                      "thickness_compensation": True},
        metadata={"product_name": "T", "product_type": "carton"},
    )


class ArchetypeGeometryTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.coords = calculate_dieline(_params())

    def test_preserves_inner_90_32_92_at_board_05(self):
        assert self.coords.dimensions.inner == TASK50_INNER
        assert self.coords.board_thickness_mm == BOARD
        # body span between the main creases IS the inner height
        assert abs((self.coords.body_bottom_y - self.coords.body_top_y)
                   - 92.0) < 1e-6
        # closure face depth equals the inner depth exactly
        d = self.coords.derived
        P = self.coords.dimensions.manufacture[1]
        assert abs((P - 2 * BOARD) - 32.0) < 1e-6
        assert d["structure_status"] == \
            "OPEN_SOURCE_FORMULA_ADAPTED_PROVISIONAL"

    def test_panel_sequence_is_exact(self):
        assert [p.name for p in self.coords.panels] == [
            "glue_tab", "back", "side_left", "front", "side_right"]
        defn = registry.resolve("ecma_a20_20_01_01_ste_carton", "0.1")
        assert defn.panel_order() == [p.name for p in self.coords.panels]

    def test_slit_locks_remain_cut(self):
        # 8 entry-slit cut segments: 2 per fold end, both ends, both tucks
        assert len(self.coords.slit_lines) == 8
        # the vertical legs cross the fold by slit_depth - 2t
        verticals = [s for s in self.coords.slit_lines
                     if abs(s[0] - s[2]) < 1e-9]
        assert len(verticals) == 4
        for (_, y1, _, y2) in verticals:
            assert abs(abs(y2 - y1) - 2.5) < 1e-6

    def test_creases_stop_at_cut_interruptions(self):
        # tuck-fold creases span exactly (back width) - 2*slit_len
        d = self.coords.derived
        back = next(p for p in self.coords.panels if p.name == "back")
        spans = sorted(abs(x2 - x1)
                       for (x1, _, x2, _) in self.coords.fold_lines)
        expected = back.width + BOARD - 2 * d["entry_slit_mm"]
        assert any(abs(s - expected) < 1e-6 for s in spans), (
            f"no crease spans {expected} (spans: {spans})")
        # and no crease is scored over a cut edge (geometry integrity)
        from apps.dielines.exporters.structural_comparison import (
            geometry_integrity,
        )
        integ = geometry_integrity(self.coords)
        assert integ["cut_fold_conflict"] is False
        assert integ["self_intersecting"] is False
        assert integ["open_contour"] is False

    def test_curved_shoulders_are_deterministic_cubics(self):
        from apps.dielines.geometry.primitives import CubicSeg
        prims = self.coords.component_paths["top-back-tuck"]
        cubics = [p for p in prims if isinstance(p, CubicSeg)]
        assert len(cubics) == 2
        again = calculate_dieline(_params())
        prims2 = again.component_paths["top-back-tuck"]
        assert [(p.p0, getattr(p, "c1", None), p.p1) for p in prims] == \
               [(p.p0, getattr(p, "c1", None), p.p1) for p in prims2]

    def test_dust_flaps_do_not_collide(self):
        report = collision_report(self.coords)
        by_name = {c["name"]: c for c in report["checks"]}
        assert by_name["dust_flaps_opposing_clearance"]["ok"]
        assert by_name["component_area_overlap"]["ok"]
        assert report["all_ok"], report

    def test_bleed_follows_the_full_contour(self):
        cut, bleed = self.coords.cut_polygon, self.coords.bleed_polygon
        assert bleed.geom_type == "Polygon" and bleed.is_valid
        assert bleed.contains(cut)
        cb, bb = cut.bounds, bleed.bounds
        grow = min(cb[0] - bb[0], cb[1] - bb[1], bb[2] - cb[2], bb[3] - cb[3])
        assert grow >= 3.0 - 1e-6

    def test_output_is_deterministic(self):
        h1 = geometry_content_hashes(self.coords)
        h2 = geometry_content_hashes(calculate_dieline(_params()))
        assert h1 == h2
        from apps.dielines.exporters.counter_display_files import write_carton_svg
        import tempfile as tf
        with tf.TemporaryDirectory() as d1, tf.TemporaryDirectory() as d2:
            s1 = write_carton_svg(self.coords, "det", output_dir=d1)
            s2 = write_carton_svg(calculate_dieline(_params()), "det",
                            output_dir=d2)
            assert s1 == s2

    def test_board_thickness_zero_is_refused(self):
        """Every compensation derives from t — uncompensated geometry is
        not a mode this archetype has."""
        with self.assertRaises(EcmaSteGeometryError):
            calculate_ecma_ste(_params(board=0.0),
                               ECMA_A20_20_01_01_STE_CARTON_V0_1)

    def test_provenance_is_persisted(self):
        prov = self.coords.derived["formula_provenance"]
        assert prov["source_license"] == "MIT"
        assert "DDR68/Rhino_Packaging_Toolkit" in prov["source_repository"]
        assert prov["commit_reviewed"].startswith("e062327c")
        assert prov["bbrose_changes"]


class WrongDepthTests(TestCase):
    def test_25mm_depth_is_a_different_geometry_hash_and_bannable(self):
        """The 90×25×92 die produces a distinct hash; once banned on a job,
        confirmation refuses it forever."""
        from apps.pipeline.services import structure_selection as ss
        from apps.pipeline.services.template_selection import (
            TemplateSelection,
        )
        job = DielineJob.objects.create(
            template_type="ecma_a20_20_01_01_ste_carton", scenario="B",
            input_json={}, extraction_result={})
        selection = TemplateSelection(
            resolved=True, template_id="ecma_a20_20_01_01_ste_carton",
            version="0.1", source="OPEN_SOURCE_FORMULA_ADAPTED_PROVISIONAL")
        bad = ss.build_structure_record(
            selection, {"width_mm": 90.0, "depth_mm": 25.0,
                        "height_mm": 92.0, "board_thickness_mm": 0.5})
        good = ss.build_structure_record(
            selection, {"width_mm": 90.0, "depth_mm": 32.0,
                        "height_mm": 92.0, "board_thickness_mm": 0.5})
        assert bad["geometry_hash"] != good["geometry_hash"]
        job.extraction_result = {
            "banned_geometry_hashes": [bad["geometry_hash"]]}
        job.save(update_fields=["extraction_result"])
        ss.save_structure_record(job, bad)
        user = User.objects.create_superuser("wd", "w@w.com", "pw")
        with self.assertRaises(ss.StructureError) as ctx:
            ss.confirm_structure(job, user)
        assert "PERMANENTLY_INVALIDATED" in ctx.exception.code
        # the correct structure confirmed only once a physical FIT_PASS
        # existed for exactly that geometry (2A-9 §7 gate) — [§BH70(3): "A physical sample is never required to
        # finish a design"; it is confirmed without one, the rejected geometry still refused above]
        ss.save_structure_record(job, good)
        rec = ss.confirm_structure(job, user)
        assert rec["confirmed_at"]
        record_physical_validation(
            job, user, template_key="ecma_a20_20_01_01_ste_carton/0.1",
            geometry_hash=good["geometry_hash"], outcome="FIT_PASS",
            sample_printed_at_100pct=True)


class GateAndPromotionTests(TestCase):
    def test_provisional_structure_cannot_pass_gate2(self):
        defn = registry.resolve("ecma_a20_20_01_01_ste_carton", "0.1")
        assert defn.production_ready is False
        assert defn.ineligibility_code == "PHYSICAL_SAMPLE_VALIDATION_REQUIRED"
        assert defn.provisional is True

    def test_physical_fit_pass_is_required_for_promotion(self):
        job = DielineJob.objects.create(
            template_type="ecma_a20_20_01_01_ste_carton", scenario="B",
            input_json={}, extraction_result={})
        user = User.objects.create_superuser("pv", "p@p.com", "pw")
        key, ghash = "ecma_a20_20_01_01_ste_carton/0.1", "abc123"
        blockers = promotion_blockers(job, template_key=key,
                                      geometry_hash=ghash)
        assert blockers and "PHYSICAL_SAMPLE_VALIDATION_REQUIRED" in \
            blockers[0]
        # a visual review can NEVER be a FIT_PASS
        with self.assertRaises(PhysicalValidationError):
            record_physical_validation(
                job, user, template_key=key, geometry_hash=ghash,
                outcome="FIT_PASS", sample_printed_at_100pct=False)
        # bounded vocabulary only
        with self.assertRaises(PhysicalValidationError):
            record_physical_validation(
                job, user, template_key=key, geometry_hash=ghash,
                outcome="LOOKS_FINE", sample_printed_at_100pct=True)
        record_physical_validation(
            job, user, template_key=key, geometry_hash=ghash,
            outcome="FIT_TOO_TIGHT", sample_printed_at_100pct=True,
            measured_corrections_mm={"depth": 0.4})
        assert promotion_blockers(job, template_key=key,
                                  geometry_hash=ghash)
        record_physical_validation(
            job, user, template_key=key, geometry_hash=ghash,
            outcome="FIT_PASS", sample_printed_at_100pct=True,
            board_thickness_mm=0.5)
        assert promotion_blockers(job, template_key=key,
                                  geometry_hash=ghash) == []
        assert "FIT_PASS" in ALLOWED_OUTCOMES


class SupplierOverrideTests(TestCase):
    def test_supplier_dieline_overrides_the_archetype(self):
        from apps.core.models import Brand
        from apps.dielines.services.customer_dieline import (
            SOURCE_SUPPLIER,
            archetype_difference_report,
            customer_dieline_record,
            register_customer_dieline,
        )
        from apps.dielines.tests.test_customer_dieline import _reference_pdf
        from apps.pipeline.models import (
            DesignTask,
            GeneratedImage,
            PackagingOutput,
        )
        from apps.pipeline.services.template_selection import select_template
        user = User.objects.create_superuser("so", "s@o.com", "pw")
        brand = Brand.objects.create(name="B", master_brief="x")
        task = DesignTask.objects.create(
            brand=brand, task_text="x",
            status="awaiting_structure_confirmation")
        job = DielineJob.objects.create(
            template_type="ecma_a20_20_01_01_ste_carton", scenario="B",
            input_json={}, extraction_result={})
        image = GeneratedImage.objects.create(
            task=task, direction_name="d", prompt_used="p",
            variation_number=1)
        PackagingOutput.objects.create(task=task, spec_sheet={},
                                       approved_image=image,
                                       dieline_job=job)
        reference = Path(tempfile.mkdtemp()) / "supplier_die.pdf"
        self.addCleanup(shutil.rmtree, reference.parent, True)
        _reference_pdf(reference)
        register_customer_dieline(job, str(reference), user,
                                  source_type=SOURCE_SUPPLIER,
                                  provenance="manufacturer die")
        record = customer_dieline_record(job)
        assert record["source"] == \
            "CUSTOMER_OR_MANUFACTURER_SUPPLIED_DIELINE"
        selection = select_template(
            task, dimensions={"width_mm": 90, "depth_mm": 32,
                              "height_mm": 92},
            user_template="ecma_a20_20_01_01_ste_carton")
        assert selection.resolved is False
        assert selection.source == \
            "CUSTOMER_OR_MANUFACTURER_SUPPLIED_DIELINE"
        assert selection.code == "CUSTOMER_DIELINE_IMPORT_REQUIRED"
        # difference report is preserved, authority stated
        coords = calculate_dieline(_params())
        report = archetype_difference_report(record, coords)
        assert report["authority"].startswith("the supplied die outranks")
        assert "archetype_panel_widths_mm" in report

    def test_unknown_source_type_is_refused(self):
        from apps.dielines.services.customer_dieline import (
            CustomerDielineError,
            register_customer_dieline,
        )
        job = DielineJob.objects.create(
            template_type="x", scenario="B", input_json={},
            extraction_result={})
        with self.assertRaises(CustomerDielineError):
            register_customer_dieline(
                job, "/nonexistent.pdf",
                User.objects.create_superuser("u3", "u@3.com", "pw"),
                source_type="SOMEONE_SAID_SO")


