"""2A-9-CORR-2 — reference-matched opposing-tuck archetype (§7).

The first 2A-9 archetype hung both major tucks from the same main panel;
the reference opposes them. These pin: opposing attachment preserved; the
old same-panel structure fails the reference comparison; dimensions and
side panels unchanged; dust flaps stay on the side panels; slits and
crease interruptions valid; the folded diagnostic covers the closure
components; a rejected geometry can never receive FIT_PASS; and the
correction path touches no artwork and no provider.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase

from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.geometry.opposed_tuck import (
    REFERENCE_ATTACHMENT_MAP,
    collision_report,
    geometry_content_hashes,
    validate_against_attachment_map,
)
from apps.dielines.models import DielineJob
from apps.dielines.tests import provider_tripwire as tripwire
from apps.dielines.validators.schema import DielineInputJSON

INNER = (90.0, 32.0, 92.0)


def _params(template="reference_opposed_tuck_carton"):
    return DielineInputJSON(
        template=template, template_version="0.1", unit="mm",
        dimensions={"width_mm": INNER[0], "depth_mm": INNER[1],
                    "height_mm": INNER[2]},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": 12.0, "board_thickness_mm": 0.5,
                      "thickness_compensation": True},
        metadata={"product_name": "T", "product_type": "carton"},
    )


class OpposedTuckGeometryTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.coords = calculate_dieline(_params())

    def test_major_tucks_attach_to_different_main_panels(self):
        d = self.coords.derived
        assert d["top_tuck_panel"] == "main_a"
        assert d["bottom_tuck_panel"] == "main_b"
        assert d["top_tuck_panel"] != d["bottom_tuck_panel"]
        assert validate_against_attachment_map(d) == []
        # and the flap polygons really hinge on different panels
        panels = {p.name: p for p in self.coords.panels}
        top_tuck, bottom_tuck = self.coords.tuck_flap_polygons
        top_minx, _, top_maxx, _ = top_tuck.bounds
        bot_minx, _, bot_maxx, _ = bottom_tuck.bounds
        a, b = panels["main_a"], panels["main_b"]
        assert a.x - 0.01 <= top_minx and top_maxx <= a.right + 0.01
        assert b.x - 0.01 <= bot_minx and bot_maxx <= b.right + 0.01

    def test_old_same_panel_structure_fails_reference_comparison(self):
        old = calculate_dieline(_params("ecma_a20_20_01_01_ste_carton"))
        codes = validate_against_attachment_map(old.derived)
        joined = " ".join(codes)
        assert "PROVISIONAL_CLOSURE_TOPOLOGY_MISMATCH" in joined
        assert "REFERENCE_OPPOSING_TUCK_NOT_PRESERVED" in joined
        assert "MAJOR_TUCK_PANEL_ASSIGNMENT_MISMATCH" in joined

    def test_dimensions_and_side_panels_preserved(self):
        assert self.coords.dimensions.inner == INNER
        assert self.coords.board_thickness_mm == 0.5
        P = self.coords.dimensions.manufacture[1]
        assert abs((P - 2 * 0.5) - 32.0) < 1e-6      # closure face = 32
        assert abs((self.coords.body_bottom_y - self.coords.body_top_y)
                   - 92.0) < 1e-6

    def test_dust_flaps_remain_on_side_panels(self):
        panels = {p.name: p for p in self.coords.panels}
        names = [cid for cid, _ in self.coords.components]
        assert "top-side-a-dust" in names and "bottom-side-b-dust" in names
        for polygon, side in zip(self.coords.dust_flap_polygons,
                                 ("side_a", "side_b", "side_a", "side_b")):
            minx, _, maxx, _ = polygon.bounds
            panel = panels[side]
            assert panel.x - 0.01 <= minx and maxx <= panel.right + 0.01, (
                f"dust flap escapes {side}")

    def test_slits_and_crease_interruptions_remain_valid(self):
        assert len(self.coords.slit_lines) == 8
        from apps.dielines.exporters.structural_comparison import (
            geometry_integrity,
        )
        integ = geometry_integrity(self.coords)
        assert integ["cut_fold_conflict"] is False
        assert integ["self_intersecting"] is False
        assert integ["open_contour"] is False
        # both tuck folds shortened by the slit length at each end
        d = self.coords.derived
        panels = {p.name: p for p in self.coords.panels}
        spans = sorted(abs(x2 - x1)
                       for (x1, _, x2, _) in self.coords.fold_lines)
        for main in ("main_a", "main_b"):
            expected = panels[main].width - 2 * d["entry_slit_mm"] + (
                0.5 if main == "main_a" else 0.0)
            assert any(abs(sp - expected) < 0.51 for sp in spans), (
                f"no shortened fold for {main} (~{expected})")

    def test_folded_diagnostic_includes_closure_components(self):
        from apps.dielines.exporters.folded_diagnostic import (
            export_folded_diagnostic,
        )
        out = Path(tempfile.mkdtemp()) / "fold.png"
        self.addCleanup(shutil.rmtree, out.parent, True)
        result = export_folded_diagnostic(
            self.coords, str(out), collision=collision_report(self.coords))
        assert result and out.exists() and out.stat().st_size > 10000
        # collision checks operate on actual flap geometry
        rep = collision_report(self.coords)
        names = {c["name"] for c in rep["checks"]}
        assert {"opposing_attachment_preserved",
                "folded_dust_flap_pair_clearance",
                "closure_face_spans_opening",
                "lock_ear_engages_slit"} <= names
        assert rep["all_ok"], rep

    def test_deterministic(self):
        assert geometry_content_hashes(self.coords) == \
            geometry_content_hashes(calculate_dieline(_params()))


class RejectedGeometryTests(TestCase):
    def test_banned_geometry_cannot_receive_fit_pass(self):
        """§5/§7: the rejected same-panel physical-test sheet can never be
        recorded as FIT_PASS (or any physical result)."""
        from apps.dielines.services.physical_validation import (
            PhysicalValidationError,
            record_physical_validation,
        )
        job = DielineJob.objects.create(
            template_type="reference_opposed_tuck_carton", scenario="B",
            input_json={},
            extraction_result={"banned_geometry_hashes": ["deadbeef" * 4]})
        user = User.objects.create_superuser("bg", "b@g.com", "pw")
        with self.assertRaises(PhysicalValidationError) as ctx:
            record_physical_validation(
                job, user, template_key="ecma_a20_20_01_01_ste_carton/0.1",
                geometry_hash="deadbeef" * 4, outcome="FIT_PASS",
                sample_printed_at_100pct=True)
        assert ctx.exception.code == \
            "PHYSICAL_RESULT_FOR_INVALIDATED_GEOMETRY"

    def test_attachment_map_is_independent_of_the_archetype(self):
        assert REFERENCE_ATTACHMENT_MAP["upper_major_tuck"] == "main_panel_a"
        assert REFERENCE_ATTACHMENT_MAP["lower_major_tuck"] == "main_panel_b"
        assert REFERENCE_ATTACHMENT_MAP["closure"] == "OPPOSING_TUCK"
        assert "reference_opposed_tuck_carton" not in str(
            REFERENCE_ATTACHMENT_MAP)

    def test_the_correction_path_makes_no_artwork_or_provider_call(self):
        """WI-S — converted from a §Y2-registered source-string guard.

        Was: five words are absent from three files. Now the correction path
        is actually run — the rejected same-panel geometry and the corrected
        opposing one are both generated, the folded diagnostic and the
        three-way attachment overlay are both rendered to real PNGs — with
        every provider boundary and the vector-artwork composer armed to
        raise, and all three modules have to have executed.

        `compose_vector_art_graph` is armed here rather than merely absent
        from a file, which is the substantive upgrade: the claim these
        exporters exist to support is that a REJECTED structure never
        acquires artwork, and that is a claim about what the run does.
        """
        import apps.dielines.exporters.attachment_overlay as overlay
        import apps.dielines.exporters.folded_diagnostic as fold
        import apps.dielines.geometry.opposed_tuck as mod
        out = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out, True)
        with tripwire.armed(mod, fold, overlay) as watch:
            corrected = calculate_dieline(_params())
            rejected = calculate_dieline(
                _params("ecma_a20_20_01_01_ste_carton"))
            fold_png = fold.export_folded_diagnostic(
                corrected, str(out / "fold.png"),
                collision=collision_report(corrected))
            overlay_png = overlay.export_attachment_overlay(
                rejected, corrected, corrected.derived["attachment_map"],
                str(out / "overlay.png"))
        assert fold_png and Path(fold_png).exists()
        assert overlay_png and Path(overlay_png).exists()
        assert validate_against_attachment_map(rejected.derived) != []
        tripwire.assert_clean(watch, mod, fold, overlay)


class LiveTask50OpposedGuard(TestCase):
    def test_task50_shows_the_opposed_structure(self):
        """Live-DB guard (returns early on the test DB)."""
        from apps.pipeline.models import DesignTask
        task = DesignTask.objects.filter(pk=50).first()
        if task is None:
            return
        output = task.packaging_outputs.filter(
            dieline_job__isnull=False).first()
        spec = output.spec_sheet or {}
        pres = spec.get("structure_presentation") or {}
        assert pres.get("template_id") == "reference_opposed_tuck_carton"
        assert pres.get("tuck_attachment", {}).get("opposing") is True
        assert pres.get("confirmable") is False
        banned = (output.dieline_job.extraction_result or {}).get(
            "banned_geometry_hashes", [])
        assert "43153352fdbccac60b1b902d4cd529d4" in banned   # 90x25x92
        assert "dc9d799dea50a7441979ea9b2b505241" in banned   # same-panel
        labels = [e.get("label", "") for e in spec.get("rejected_outputs", [])]
        assert any("PROVISIONAL_CLOSURE_TOPOLOGY_MISMATCH" in lb
                   for lb in labels)
        assert task.status == "awaiting_structure_confirmation"
