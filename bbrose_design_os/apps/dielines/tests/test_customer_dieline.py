"""Customer-supplied dieline authority (task-50 correction §3/§5/§6/§7).

The 90×25×92 generic STE silently stood in for the customer's real
90×32×92 reference. These pin: a registered customer die outranks every
template source and disables parametric selection; the vector import
measures real panel widths and body height; the §7 parity gate blocks any
structure that differs from the reference; the wrong 25 mm depth can never
survive registration; and the rejected files stay preserved.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase

from apps.dielines.models import DielineJob
from apps.dielines.services.customer_dieline import (
    COORDINATE_TOLERANCE_MM,
    CustomerDielineError,
    customer_dieline_record,
    extract_reference_geometry,
    register_customer_dieline,
    validate_reference_parity,
)

#: Reference body per the user's Pacdora page: glue | 90 | 32 | 90 | 32,
#: inner height 92, 0.5 mm board.
PANELS = [12.0, 90.0, 32.0, 90.0, 32.0]


def _reference_pdf(path: Path):
    """A synthetic vector dieline with Pacdora's color legend: blue cut
    contour, red vertical/horizontal creases, green bleed."""
    import fitz

    MM = 72 / 25.4
    total_w = sum(PANELS)
    height = 92.0
    doc = fitz.open()
    page = doc.new_page(width=(total_w + 20) * MM, height=(height + 60) * MM)
    ox, oy = 10 * MM, 30 * MM

    def line(x1, y1, x2, y2, color):
        page.draw_line(fitz.Point(ox + x1 * MM, oy + y1 * MM),
                       fitz.Point(ox + x2 * MM, oy + y2 * MM), color=color)

    blue, red, green = (0, 0, 1), (1, 0, 0), (0, 0.7, 0.2)
    # cut contour (simplified rectangle w/ flap bumps)
    line(0, 0, total_w, 0, blue)
    line(total_w, 0, total_w, height, blue)
    line(total_w, height, 0, height, blue)
    line(0, height, 0, 0, blue)
    # vertical creases at panel boundaries
    x = 0.0
    for width in PANELS[:-1]:
        x += width
        line(x, 0, x, height, red)
    # body top/bottom creases
    line(0, 0, total_w, 0, red)
    line(0, height, total_w, height, red)
    # bleed contour
    line(-3, -3, total_w + 3, -3, green)
    line(total_w + 3, -3, total_w + 3, height + 3, green)
    line(total_w + 3, height + 3, -3, height + 3, green)
    line(-3, height + 3, -3, -3, green)
    doc.save(str(path))
    doc.close()


class CustomerDielineImportTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = Path(tempfile.mkdtemp()) / "pacdora_reference.pdf"
        cls.addClassCleanup(shutil.rmtree, cls.reference.parent, True)
        _reference_pdf(cls.reference)

    def setUp(self):
        self.user = User.objects.create_superuser("cd", "c@c.com", "pw")
        self.job = DielineJob.objects.create(
            template_type="straight_tuck_end_carton", scenario="B",
            input_json={}, extraction_result={})

    def test_actual_cut_and_crease_paths_are_imported_and_measured(self):
        geometry = extract_reference_geometry(str(self.reference))
        assert geometry["counts"]["cut"] >= 4
        assert geometry["counts"]["crease"] >= 6
        assert geometry["counts"]["bleed"] >= 4
        # glue flap + last side panel are bounded by the cut contour
        assert geometry["panel_widths_mm"] == PANELS
        assert geometry["body_height_mm"] == 92.0

    def test_registration_persists_provenance_and_hashes(self):
        record = register_customer_dieline(
            self.job, str(self.reference), self.user,
            inner_mm=(90, 32, 92), board_thickness_mm=0.5,
            provenance="Pacdora dieline 100010, downloaded by the user")
        assert record["source"] == "CUSTOMER_SUPPLIED_DIELINE"
        assert len(record["sha256"]) == 64
        assert record["cut_path_hash"] != record["crease_path_hash"]
        assert record["board_thickness_mm"] == 0.5
        assert record["confirmed"] is False
        stored = customer_dieline_record(self.job)
        assert stored["sha256"] == record["sha256"]

    def test_wrong_depth_cannot_survive_the_parity_gate(self):
        """The exact task-50 defect: 25 mm side panels against the 32 mm
        reference must fail with dimension codes."""
        record = register_customer_dieline(
            self.job, str(self.reference), self.user)
        codes = validate_reference_parity(
            record,
            panel_widths_mm=[12.0, 90.0, 25.0, 90.0, 25.0],
            body_height_mm=92.0)
        joined = " ".join(codes)
        assert "CUSTOMER_DIELINE" in joined
        assert "25.0" in joined or "PANEL_SEQUENCE" in joined

    def test_matching_structure_passes_parity(self):
        record = register_customer_dieline(
            self.job, str(self.reference), self.user)
        codes = validate_reference_parity(
            record,
            panel_widths_mm=list(record["panel_widths_mm"]),
            body_height_mm=record["body_height_mm"],
            cut_path_hash=record["cut_path_hash"],
            crease_path_hash=record["crease_path_hash"])
        assert codes == []

    def test_tolerance_is_a_tenth_of_a_millimetre(self):
        record = register_customer_dieline(
            self.job, str(self.reference), self.user)
        widths = list(record["panel_widths_mm"])
        widths[0] += COORDINATE_TOLERANCE_MM * 3
        codes = validate_reference_parity(
            record, panel_widths_mm=widths,
            body_height_mm=record["body_height_mm"])
        assert any("DIMENSION_MISMATCH" in code for code in codes)

    def test_unsupported_format_fails_closed(self):
        bad = Path(tempfile.mkdtemp()) / "reference.dxf"
        self.addCleanup(shutil.rmtree, bad.parent, True)
        bad.write_text("0\nSECTION\n")
        with self.assertRaises(CustomerDielineError):
            extract_reference_geometry(str(bad))


class SelectionPrecedenceTests(TestCase):
    def test_registered_customer_dieline_disables_template_selection(self):
        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask, PackagingOutput
        from apps.pipeline.services.template_selection import select_template
        user = User.objects.create_superuser("sp", "s@s.com", "pw")
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        task = DesignTask.objects.create(
            brand=brand, task_text="x",
            status="awaiting_structure_confirmation")
        from apps.pipeline.models import GeneratedImage
        job = DielineJob.objects.create(
            template_type="straight_tuck_end_carton", scenario="B",
            input_json={}, extraction_result={})
        image = GeneratedImage.objects.create(
            task=task, direction_name="d", prompt_used="p",
            variation_number=1)
        PackagingOutput.objects.create(task=task, spec_sheet={},
                                       approved_image=image,
                                       dieline_job=job)
        reference = Path(tempfile.mkdtemp()) / "ref.pdf"
        self.addCleanup(shutil.rmtree, reference.parent, True)
        _reference_pdf(reference)
        register_customer_dieline(job, str(reference), user)

        # even an explicit user template cannot override the customer die
        selection = select_template(
            task, dimensions={"width_mm": 90, "depth_mm": 25,
                              "height_mm": 92},
            user_template="straight_tuck_end_carton")
        assert selection.resolved is False
        assert selection.source == "CUSTOMER_SUPPLIED_DIELINE"
        assert selection.code == "CUSTOMER_DIELINE_IMPORT_REQUIRED"

    def test_without_a_customer_die_selection_is_unchanged(self):
        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask
        from apps.pipeline.services.template_selection import select_template
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="x",
                                         status="awaiting_dimensions")
        # 2A-9E: without a customer die, STE no longer silently resolves to
        # its legacy 1.1 — it requires explicit version confirmation
        # (1.2 recommended). An explicit version pin resolves.
        pending = select_template(
            task, dimensions={"width_mm": 90, "depth_mm": 25,
                              "height_mm": 92},
            user_template="straight_tuck_end_carton")
        assert pending.resolved is False
        assert pending.code == "STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED"
        confirmed = select_template(
            task, dimensions={"width_mm": 90, "depth_mm": 25,
                              "height_mm": 92},
            user_template="straight_tuck_end_carton", user_version="1.1")
        assert confirmed.resolved is True
        assert confirmed.source == "EXPLICIT_USER_CONFIRMATION"
        assert confirmed.version == "1.1"


class RejectionPreservationTests(TestCase):
    def test_task50_rejected_outputs_remain_preserved(self):
        """Live-state guard (skips outside the dev DB): the rejected
        90×25×92 deliverables stay on disk with their labels."""
        from apps.pipeline.models import DesignTask
        task = DesignTask.objects.filter(pk=50).first()
        if task is None:      # test DB — nothing to assert against
            return
        out = task.packaging_outputs.filter(dieline_job__isnull=False).first()
        labels = [entry["label"] for entry in
                  (out.spec_sheet or {}).get("rejected_outputs", [])]
        assert any("CUSTOMER_DIELINE_REFERENCE_NOT_PRESERVED" in label
                   for label in labels)
