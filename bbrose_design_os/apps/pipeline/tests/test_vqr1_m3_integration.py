"""VQR-1 — the owner-accepted M3 backbone in production (server).

The rejection's first divergence was geometry: the accepted M3 fit
(identity 4ecc8e9df1d1…) sat unused while production drew rounded
rectangles with a generic cap block on a hardcoded A4 artboard. These
tests hold the integration: exact structural agreement with the frozen
fit, the real dropper assembly, a product-derived artboard, honest
provenance in the design graph, fail-closed drift detection, and an
untouched parametric path for everything M3 does not cover.
"""
import re

from django.test import SimpleTestCase, override_settings

from apps.ire.compose_container import (
    _PAGE_FACTOR_H,
    _PAGE_FACTOR_W,
    compose_container_graph,
)
from apps.pipeline.services.visual_quality_gate import (
    THRESHOLDS,
    _artboard_axis,
    _closure_axis,
    _silhouette_axis,
)
from apps.pipeline.targets.container import m3_backbone as m3
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)

TASK53_PROFILE = dict(archetype="bottle", variant="cylindrical",
                      height_mm=95.0, width_mm=35.0, neck_ratio=0.34,
                      cap_style="dropper")


def _profile(**kw):
    return ContainerProfile(**{**TASK53_PROFILE, **kw})


class M3SelectionTests(SimpleTestCase):
    def test_bottle_dropper_uses_the_accepted_m3_assembly(self):
        backbone, record = m3.build_container_backbone(_profile())
        assert record["backbone_source"] == m3.M3_SOURCE
        assert record["identity_sha256_png"] == "4ecc8e9df1d1"
        assert record["geometry_authority"] == \
            "CONCEPT_VISUAL_GEOMETRY_ONLY"
        ca = record["closure_assembly"]
        assert ca["family"] == "dropper"
        assert ca["components"] == ["collar", "bulb"]
        assert ca["source"] == m3.M3_SOURCE
        # owner correction: honest scope language, never over-claimed
        assert ca["assembly_scope"] == "M3_VISIBLE_DROPPER_ASSEMBLY"
        assert any("no internal pipette" in n for n in ca["scope_notes"])
        assert any("GLASS contour" in n for n in ca["scope_notes"])
        assert backbone.bulb_region is not None
        assert backbone.collar_region is not None

    def test_non_dropper_and_other_archetypes_stay_parametric(self):
        for kw in ({"cap_style": "screw"}, {"archetype": "jar"},
                   {"archetype": "tube"}):
            _, record = m3.build_container_backbone(_profile(**kw))
            assert record["backbone_source"] == "parametric", kw
            assert record["closure_assembly"] is None, kw

    @override_settings(CONTAINER_STRUCTURAL_BACKBONE="parametric")
    def test_the_rollback_setting_is_ignored_and_the_dropper_draws_m3(self):
        # his Q8 of 2026-10-03: the dropper's rollback switch is removed — M3 is its one engine; a deployment
        # that still sets the old setting draws the dropper on M3 all the same
        backbone, record = m3.build_container_backbone(_profile())
        assert record["backbone_source"] == m3.M3_SOURCE
        assert record["closure_assembly"]["source"] == m3.M3_SOURCE
        assert backbone.bulb_region is not None and backbone.collar_region is not None

    def test_jar_and_tube_geometry_byte_identical_to_legacy(self):
        for arch in ("jar", "tube"):
            profile = _profile(archetype=arch, cap_style="screw")
            selected, _ = m3.build_container_backbone(profile)
            legacy = build_backbone(profile)
            assert [s.model_dump() for s in selected.silhouette] == \
                [s.model_dump() for s in legacy.silhouette], arch


class M3StructuralGoldenTests(SimpleTestCase):
    """The emitted geometry must agree EXACTLY with the frozen fit under
    the documented linear transform — the accepted curves survive."""

    def test_frozen_fit_hash_verified(self):
        fit = m3.load_m3_fit()
        assert fit["schema_version"] == "vq1_master_structural_fit/1.0"
        assert set(fit["fits"]) == {"DARK_CLOSURE", "COLLAR", "GLASS"}

    def test_drift_fails_closed(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        fit = m3.load_m3_fit()
        tampered = dict(fit)
        tampered["centerline_px"] = 600.0
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as fh:
            json.dump(tampered, fh)
        try:
            with patch.object(m3, "M3_FIT_PATH", Path(fh.name)), \
                    patch.dict(m3._FIT_CACHE, {}, clear=True):
                with self.assertRaises(m3.M3GeometryDrift):
                    m3.load_m3_fit()
        finally:
            Path(fh.name).unlink()

    def test_transform_is_exact_against_the_fit(self):
        fit = m3.load_m3_fit()
        profile = _profile()
        backbone = m3.build_m3_dropper_backbone(profile)
        glass = fit["fits"]["GLASS"]
        span0, span1 = fit["assembly_span_px"]
        sy = profile.height_mm / (span1 - span0)
        max_hw = max([glass["start"][0]]
                     + [pt[0] for seg in glass["segments"] for pt in seg])
        sx = (profile.width_mm / 2.0) / max_hw
        cx = profile.width_mm / 2.0
        # the silhouette's first MoveTo is exactly the transformed start
        move = backbone.silhouette[0]
        assert abs(move.x - (cx + glass["start"][0] * sx)) < 1e-9
        assert abs(move.y - (glass["start"][1] - span0) * sy) < 1e-9
        # every right-side cubic endpoint matches its fit point exactly
        n = len(glass["segments"])
        for seg, (c1, c2, p3) in zip(backbone.silhouette[1:1 + n],
                                     glass["segments"]):
            assert abs(seg.x - (cx + p3[0] * sx)) < 1e-9
            assert abs(seg.x1 - (cx + c1[0] * sx)) < 1e-9
            assert abs(seg.x2 - (cx + c2[0] * sx)) < 1e-9
        # segment budget: right cubics + base edge + mirrored cubics + close
        assert len(backbone.silhouette) == 2 * n + 3

    def test_body_spans_exactly_the_confirmed_width(self):
        backbone = m3.build_m3_dropper_backbone(_profile())
        xs = []
        for seg in backbone.silhouette:
            for attr in ("x", "x1", "x2"):
                v = getattr(seg, attr, None)
                if v is not None:
                    xs.append(v)
        assert abs((max(xs) - min(xs)) - 35.0) < 1e-6
        ys = [getattr(seg, a) for seg in
              (backbone.bulb_region + backbone.silhouette)
              for a in ("y",) if getattr(seg, a, None) is not None]
        assert abs(max(ys) - 95.0) < 0.5      # assembly spans the height


class ProductArtboardTests(SimpleTestCase):
    def test_page_factors_stay_below_the_gate_threshold(self):
        assert _PAGE_FACTOR_W < THRESHOLDS["artboard_max_product_factor"]
        assert _PAGE_FACTOR_H < THRESHOLDS["artboard_max_product_factor"]

    def _doc(self, **kw):
        backbone, _ = m3.build_container_backbone(_profile(**kw))
        return compose_container_graph(
            backbone, product_name="Rose Nectar Serum", native=True,
            zones=[])

    def test_artboard_is_product_derived_never_a_fixed_page(self):
        doc = self._doc()
        w_pt = doc.page_w * 72 / 25.4
        h_pt = doc.page_h * 72 / 25.4
        tol = THRESHOLDS["artboard_match_tolerance_pt"]
        for name, (pw, ph) in THRESHOLDS["fixed_page_artboards_pt"].items():
            assert not ((abs(w_pt - pw) <= tol and abs(h_pt - ph) <= tol)
                        or (abs(w_pt - ph) <= tol
                            and abs(h_pt - pw) <= tol)), name
        factor = THRESHOLDS["artboard_max_product_factor"]
        assert w_pt <= 35.0 * 72 / 25.4 * factor
        assert h_pt <= 95.0 * 72 / 25.4 * factor
        assert doc.metadata["artboard_policy"] == \
            "PRODUCT_DERIVED_FROM_CONFIRMED_PROFILE"

    def test_emitted_mediabox_matches_the_derived_page(self):
        import os
        import shutil
        import tempfile

        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        doc = self._doc()
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        out = os.path.join(folder, "page.ai")
        try:
            emit_pdf_ai(doc, out)
            data = open(out, "rb").read()
            m = re.search(rb"/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)", data)
            assert m, "MediaBox missing"
            assert abs(float(m.group(1)) - doc.page_w * 72 / 25.4) < 0.01
            assert abs(float(m.group(2)) - doc.page_h * 72 / 25.4) < 0.01
        finally:
            if os.path.exists(out):
                os.unlink(out)

    def test_hero_draws_at_true_product_scale_with_real_assembly(self):
        doc = self._doc()
        names = []

        def walk(node):
            names.append(getattr(node, "name", ""))
            for child in getattr(node, "children", []) or []:
                walk(child)
        walk(doc.root)
        assert "closure-bulb" in names            # the real dropper bulb
        assert "body" in names and "cap" in names
        bw, bh = doc.metadata["product_bounds_mm"]
        assert abs(bw - 35.0) < 0.01              # 1:1 product scale
        assert abs(bh - 95.0) < 0.6


class QualityAxisFlipTests(SimpleTestCase):
    """§exit: the gate axes VQR-1 unblocks measure and PASS on the new
    geometry — silhouette + closure from the graph facts, artboard from the
    emitted document."""

    def _graph_and_profile(self):
        backbone, record = m3.build_container_backbone(_profile())
        doc = compose_container_graph(
            backbone, product_name="Rose", native=True, zones=[])
        bw, bh = doc.metadata["product_bounds_mm"]
        graph = {"closure_assembly": record["closure_assembly"],
                 "product_bounds": {"width_pt": bw * 72 / 25.4,
                                    "height_pt": bh * 72 / 25.4}}
        profile = {"width_mm": 35.0, "height_mm": 95.0,
                   "cap_style": "dropper"}
        return graph, profile

    def test_silhouette_axis_records_structural_conformance_only(self):
        # §1 owner correction: 0.003 deviation is STRUCTURAL conformance
        # against the confirmed profile — concept fidelity stays
        # UNMEASURED (blocking) until VQR-2B
        graph, profile = self._graph_and_profile()
        axis = _silhouette_axis(graph, profile)
        assert axis["state"] == "UNMEASURED"
        assert axis["measured"]["structural_silhouette_conformance"] == \
            "PASS"
        assert axis["measured"]["relative_deviation"] <= \
            THRESHOLDS["silhouette_max_aspect_deviation"]

    def test_closure_axis_passes_on_the_recorded_assembly(self):
        graph, profile = self._graph_and_profile()
        assert _closure_axis(graph, profile)["state"] == "PASS"

    def test_parametric_paths_stay_honestly_unmeasured(self):
        _, record = m3.build_container_backbone(_profile(cap_style="screw"))
        graph = {"closure_assembly": record["closure_assembly"]}
        axis = _closure_axis(graph, {"cap_style": "screw",
                                     "width_mm": 35, "height_mm": 95})
        assert axis["state"] == "UNMEASURED"

    def test_artboard_axis_passes_on_the_emitted_ai(self):
        import tempfile
        from pathlib import Path

        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        backbone, _ = m3.build_container_backbone(_profile())
        doc = compose_container_graph(backbone, product_name="Rose",
                                      native=True, zones=[])
        out = tempfile.NamedTemporaryFile(suffix=".ai", delete=False)
        self.addCleanup(Path(out.name).unlink, missing_ok=True)
        emit_pdf_ai(doc, out.name)

        class _FF:
            def open(self, mode):
                return open(out.name, "rb")

        class _Out:
            design_preview_ai = _FF()
        axis = _artboard_axis(_Out(), {"width_mm": 35.0, "height_mm": 95.0})
        assert axis["state"] == "PASS", axis
        import os
        os.unlink(out.name)

    def test_w5_a_tubes_sheet_is_read_against_the_width_it_is_drawn_at(self):
        """[His answer of 2026-10-05, W5: "fix the artboard check so tubes pass; a check that refuses every tube is
        wrong".] A 150 × 40 mm tube composed and emitted as production does it: it is drawn flat, π/2 of its confirmed
        width, so its sheet is 3.85 × the round 40 mm and 2.45 × its drawn flat end. Read against the width it is drawn
        at it passes; read against its round width (no archetype: the reading before the fix) it is refused — the
        control that the sheet measured is the one that failed every tube."""
        import tempfile
        from pathlib import Path

        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        from apps.pipeline.services.visual_quality_gate import VQ_ARTBOARD_UNRELATED_TO_PRODUCT
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        backbone = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="screw",
                                                   height_mm=150.0, width_mm=40.0))
        doc = compose_container_graph(backbone, product_name="Rose", native=True, zones=[])
        out = tempfile.NamedTemporaryFile(suffix=".ai", delete=False)
        self.addCleanup(Path(out.name).unlink, missing_ok=True)
        emit_pdf_ai(doc, out.name)

        class _FF:
            def open(self, mode):
                return open(out.name, "rb")

        class _Out:
            design_preview_ai = _FF()
        drawn = _artboard_axis(_Out(), {"archetype": "tube", "width_mm": 40.0, "height_mm": 150.0})
        assert drawn["state"] == "PASS", drawn
        assert drawn["measured"]["product_extent_pt"][0] == round(40.0 * 3.141592653589793 / 2 * 72 / 25.4, 2), drawn
        round_width = _artboard_axis(_Out(), {"width_mm": 40.0, "height_mm": 150.0})
        assert (round_width["state"], round_width["code"]) == ("FAIL", VQ_ARTBOARD_UNRELATED_TO_PRODUCT), round_width


class ReconstructEndToEndTests(__import__("django.test",
                                          fromlist=["TestCase"]).TestCase):
    """The REAL reconstruct flow for the rejected shape (bottle + dropper):
    the emitted output carries M3 provenance, a product-derived artboard,
    and the VQR-2A gate now MEASURES three previously blocked axes — while
    the placeholder front artwork still honestly fails (that is VQR-3)."""

    def setUp(self):
        from django.core.files.base import ContentFile

        from apps.core.models import Brand, Product
        from apps.pipeline.models import DesignTask, GeneratedImage
        from apps.pipeline.targets import DesignTarget

        from .test_container_target import _PNG as png
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-411", name="Rose Nectar Serum",
            category="CO", year=2026, product_type="serum",
            width_mm=35, depth_mm=25, height_mm=95)
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="a serum",
            status="gate_1_approved",
            design_target=DesignTarget.PRODUCT_CONTAINER.value)
        self.img = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used="p",
            variation_number=1)
        self.img.image_file.save("c.png", ContentFile(png), save=True)

    @override_settings(OPENAI_API_KEY="")
    def test_dropper_reconstruction_flips_the_gate_axes(self):
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.targets.container import ProductContainerTarget
        aria = ARIAAgent(self.task.id)
        ProductContainerTarget().begin_output(aria, self.img)
        out = self.task.packaging_outputs.first()
        # [§BH71 (0b): the proposal offers a code place, optional; this test proves every axis DECIDES on a real
        # document, and a confirmed code place's depiction leaves the size floor unmeasured (test_wif_reconstruct_
        # container.py, test_bh71_a_confirmed_code_place_leaves_its_depiction_unmeasured), so it is skipped here]
        _spec = out.spec_sheet
        _spec["container_decoration_zones/1.0"]["zones"] = [
            z for z in _spec["container_decoration_zones/1.0"]["zones"] if z["zone_type"] != "BOTTOM_CODE_ZONE"]
        out.spec_sheet = _spec
        out.save()
        aria.resume_after_container_profile(
            out.id, {"archetype": "bottle", "variant": "cylindrical",
                     "height_mm": 95, "width_mm": 35,
                     "cap_style": "dropper"})
        self.task.refresh_from_db()
        out.refresh_from_db()
        assert self.task.status == "awaiting_gate_2"
        spec = out.spec_sheet
        graph = spec["container_design_graph/1.1"]
        # provenance: the accepted assembly, honestly recorded
        assert graph["backbone_source"] == m3.M3_SOURCE
        assert graph["closure_assembly"]["family"] == "dropper"
        assert set(graph["closure_assembly"]["components"]) == \
            {"collar", "bulb"}
        assert graph["product_bounds"]["width_pt"] > 0
        assert graph["artboard_policy"] == \
            "PRODUCT_DERIVED_FROM_CONFIRMED_PROFILE"

        # WI1 END-TO-END: a REAL emitted document now produces a Design
        # Graph 2.0 record, not just a 1.1 census. Asserted here rather
        # than against a synthetic dict, because the wiring is the claim.
        from apps.ire import design_graph_v2 as dg2
        from apps.pipeline.services import visual_quality_gate as vqg
        assert graph["schema_version"] == dg2.SCHEMA
        assert graph["extends"] == "container_design_graph/1.1"
        assert spec[dg2.SCHEMA] is not None
        # the 1.1 census survives inside the superset
        assert graph["census"]["mode"] == "native"
        assert graph["primitives"]["live_text"] >= 1
        # every component carries provenance — there is no unknown origin
        for comp in graph["components"]:
            assert comp["provenance"]["origin"] in dg2.ORIGINS
            assert comp["role"] in dg2.ROLES
        # BOTH gate paths still resolve off the REAL record
        axis = vqg._silhouette_axis(graph, spec.get("container_profile") or {})
        assert axis["state"] in (vqg.PASS, vqg.FAIL, vqg.UNMEASURED)
        assert "structural_silhouette_conformance" in axis["measured"]
        # and no component invented a bound nobody measured. VQR-3 fed the
        # ones that ARE measurable — an emitted image states its own box —
        # so the property is now checked as the property: a recorded bound
        # names where it was measured AND equals the metrics taken off the
        # same document; everything unmeasured is still absent.
        from apps.ire import container_logo_metrics as clm
        placed = {p["node_name"]: p["placed_mm"]
                  for p in (spec.get(clm.SCHEMA) or {}).get("placements", [])}
        for comp in graph["components"]:
            bounds = comp["bounds_mm"]
            if bounds is None:
                assert "bounds_measured_from" not in comp["provenance"]
                continue
            assert comp["provenance"]["bounds_measured_from"] == \
                "emitted image node box"
            box = placed.get(comp["component_id"])
            if box is not None:
                assert bounds == {"width_mm": box[2], "height_mm": box[3]}
        # the emitted .ai is NOT on a fixed page standard
        data = out.design_preview_ai.open("rb").read()
        m = re.search(rb"/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)", data)
        assert m
        w_pt, h_pt = float(m.group(1)), float(m.group(2))
        assert abs(w_pt - 595.276) > 1 and abs(h_pt - 841.89) > 1
        # gate axes on the REAL persisted record
        axis_sil = _silhouette_axis(graph, spec["container_profile"])
        axis_clo = _closure_axis(graph, spec["container_profile"])
        axis_art = _artboard_axis(out, spec["container_profile"])
        # §1: structural conformance PASS; concept fidelity honestly
        # UNMEASURED until VQR-2B
        assert axis_sil["state"] == "UNMEASURED", axis_sil
        assert axis_sil["measured"][
            "structural_silhouette_conformance"] == "PASS"
        assert axis_clo["state"] == "PASS", axis_clo
        assert axis_art["state"] == "PASS", axis_art
        # honesty: the placeholder front artwork still fails — VQR-1 fixed
        # geometry, not artwork; the gate stays closed until VQR-3
        from apps.pipeline.services.visual_quality_gate import (
            _front_artwork_axis)
        art = _front_artwork_axis(graph)
        assert art["state"] in ("FAIL", "PASS")   # measured either way

        # VQR-3: the logo axis was UNMEASURED — blocking — because nothing
        # produced container_logo_metrics/1.0. The target now persists it
        # from the REAL emitted document, and every placement on that
        # document is undistorted because the composers read each asset's
        # own aspect instead of asserting one. The axis PASSES on measured
        # geometry, at a floor that was never moved.
        from apps.pipeline.services.visual_quality_gate import _logo_axis
        assert _logo_axis({}, graph)["state"] == "UNMEASURED"
        logo_axis = _logo_axis(spec, graph)
        metrics = spec[clm.SCHEMA]
        assert metrics["placement_count"] >= 1
        assert logo_axis["measured"]["rendered_extent_pt"] == \
            metrics["rendered_extent_pt"]
        assert logo_axis["state"] == "PASS", (logo_axis, metrics)
        assert THRESHOLDS["logo_min_extent_pt"] == 8.0
        for placement in metrics["placements"]:
            assert placement["aspect_deviation"] == 0.0, placement
            assert placement["clipped"] is False, placement

        # VQR-3: the composition axis had no producer either. The target
        # persists container_composition_metrics/1.0 from the same emitted
        # document, and since §W3 (WI-B) all three fields the gate reads are
        # measured — so this axis DECIDES on a real container for the first
        # time. The zero below is the part worth checking: it discriminated.
        # This document really does set type over the body, the decoration
        # field, the keyline and the silhouette outline, and §W3(b) rules
        # every one of those non-blocking. A naive any-two-elements rule
        # would have failed a correct container on them.
        from apps.ire import container_composition_metrics as ccm
        from apps.pipeline.services.visual_quality_gate import (
            _composition_axis)
        comp_metrics = spec[ccm.SCHEMA]
        assert comp_metrics["blocking_overlaps"] == 0
        assert comp_metrics["unmeasured"] == []
        assert comp_metrics["overlaps_over_artwork_not_blocking"], (
            "the zero came from a reader that found no overlaps at all, so "
            "this document proves nothing about §W3(b)")
        assert comp_metrics["overlap_unmeasurable_runs"] == []
        assert comp_metrics["element_count"] >= 1
        # the FRONT hierarchy is the front's. The first version of this record
        # counted every artwork run in the document, so a real emitted
        # container reported its back panel's copy as front type; asserted on
        # the emitted document because the surface groups are what carry it.
        assert comp_metrics["front_hierarchy"], comp_metrics
        for name in comp_metrics["front_hierarchy"]:
            assert "BODY_BACK" not in name and "back-section" not in name, name
        comp_axis = _composition_axis(spec)
        assert comp_axis["state"] == "PASS", comp_axis
        assert comp_axis["measured"]["elements_outside_artboard"] == \
            comp_metrics["elements_outside_artboard"]
        assert comp_axis["measured"]["front_hierarchy_nonempty"] == \
            comp_metrics["front_hierarchy_nonempty"]
        # the PASS is not vacuous: take the ruled field back out and the axis
        # returns to UNMEASURED. Without this, a producer that had silently
        # stopped emitting the field would look like a green axis.
        withheld = {k: v for k, v in comp_metrics.items()
                    if k != "blocking_overlaps"}
        assert _composition_axis({**spec, ccm.SCHEMA: withheld})["state"] == \
            "UNMEASURED"
        # with NO record the axis has only the containment flag to quote —
        # the "empty hands" state this record replaces.
        assert _composition_axis({})["measured"] == {"zone_containment": None}

        # VQR-4: the last unproduced contract, and the only axis that was
        # worse than unmeasured — a record carrying min_text_pt alone PASSED
        # it, because three absent defect flags read as False. The target now
        # persists container_typography_metrics/1.0 from the same emitted
        # document. Both withheld fields have since been ruled — §W5 supplied
        # the placeholder allow-list (WI-A) and §W3 the overlap rule (WI-B) —
        # so this axis decides too. §W3 ruled ONE rule for both axes, which is
        # why the flag below and blocking_overlaps above must always agree.
        from apps.ire import container_typography_metrics as ctm
        from apps.pipeline.services.visual_quality_gate import (
            _typography_axis)
        typo_metrics = spec[ctm.SCHEMA]
        assert typo_metrics["materially_overlapping"] is False
        assert typo_metrics["materially_overlapping"] is (
            comp_metrics["blocking_overlaps"] > 0), (
            "the two axes gave different answers to the same §W3 question")
        # §BH50(f)(2): placeholder copy is its own blocker, not a typography
        # field — these three lines asserted the record's placeholder fields
        # until the ruling; the placeholder record carries the finding now
        assert "placeholder_text_present" not in typo_metrics
        assert not any(k.startswith("placeholder_") for k in typo_metrics)
        placeholder_copy = spec["container_placeholder_copy/1.0"]
        assert placeholder_copy["codes"] == \
            spec["container_production_readiness_codes"]["content"]
        assert typo_metrics["unmeasured"] == []
        assert typo_metrics["container_view_text_runs"] >= 1
        # the emitted document taught this module its scope. Measuring every
        # surface read min_text_pt 1.5 off panel-BODY_BACK-label — the
        # SURFACE STRIP's caption of its own panel, at diagram scale — and
        # failed the container on the legibility of its own thumbnail. The
        # strip is excluded and COUNTED, so the back panel's copy being
        # emitted only there stays visible rather than silently unmeasured.
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (8): "No empty grey blocks"] a strip panel that would hold
        # only a placeholder is not drawn at all now; what strip is drawn stays excluded and counted (its own tests:
        # test_container_typography_metrics)
        assert typo_metrics["surface_strip_runs_excluded"] >= 0
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL ... Every back label carries the
        # full set"] the back now prints its whole standard copy where the brief gave none, shrunk evenly — his
        # correction of 2026-10-07 — never below the label floor; 5.0 was the sparse back's own size
        from apps.ire.back_panel import LABEL_FLOOR_PT
        assert typo_metrics["min_text_pt"] >= LABEL_FLOOR_PT, typo_metrics["smallest_runs"]
        typo_axis = _typography_axis(spec, graph)
        assert typo_axis["state"] == "PASS", typo_axis
        assert typo_axis["measured"]["min_text_pt"] == \
            typo_metrics["min_text_pt"]
        assert typo_axis["measured"]["clipped"] == typo_metrics["clipped"]
        # the defect this work item closed, still pinned on the real record:
        # the axis reached PASS on four fields it holds, and takes any one of
        # them away it goes back to UNMEASURED rather than defaulting to a
        # clean bill of health. That was the original bug.
        # §BH50(f)(2): the fourth field, placeholder_text_present, left the
        # axis with the ruling — its finding is the placeholder record's own
        # code now — so the axis holds three flags and the size
        for field in ("min_text_pt", "clipped", "materially_overlapping",
                      "below_size_floor"):
            withheld = {k: v for k, v in typo_metrics.items() if k != field}
            assert _typography_axis({**spec, ctm.SCHEMA: withheld},
                                    graph)["state"] == "UNMEASURED", field


class M3DrawsTests(SimpleTestCase):
    """§BH48(b)(ii) — M3 DRAWS: the accepted fit as the drawing source, the profile derived from it."""

    RETAINED = {"base_thickness_mm": 3.5, "shoulder_radius_mm": 3.0, "frost_intensity": 0.7, "translucency": 0.35}

    def test_bh70_the_dropper_path_assumes_no_form_and_the_design_loop_refuses_one_it_does_not_serve(self):
        """§BH70(1), item 10 of the list sent to him: `m3_profile_geometry` defaulted its form to "bottle" and the design
        loop called it without one, so a record that said compact but carried a dropper's numbers was drawn as the
        dropper, with no refusal. The form is now required, and the loop passes the form its record names."""
        import inspect
        from types import SimpleNamespace

        from apps.dashboard import exploration_render as er
        from apps.pipeline.services import selected_concept_contract as scc
        from apps.pipeline.targets.container import archetypes as A
        self.assertIs(inspect.signature(m3.m3_profile_geometry).parameters["archetype"].default,
                      inspect.Parameter.empty)
        with self.assertRaises(A.ArchetypeOutOfScope):
            m3.m3_profile_geometry(31.5, self.RETAINED, "compact")
        fields = {n: {"value": v} for n, v in (("total_height", 96.3), ("body_height", 68.0), ("body_diameter", 33.0),
                                              ("collar_height", 12.0), ("bulb_height", 16.3))}
        spec = {"container_profile/1.0": {"archetype": "compact", "fields": {}},
                scc.EXTENSIONS_SCHEMA: {"confirmation_state": scc.HUMAN_CONFIRMED, "fields": fields}}

        class _Outputs:
            def exclude(self, **_kw):
                return self

            def order_by(self, *_a):
                return self

            def first(self):
                return SimpleNamespace(pk=0, spec_sheet=spec, approved_image=None)
        with self.assertRaises(A.ArchetypeOutOfScope) as refused:
            er.frozen_inputs(SimpleNamespace(pk=0, design_target="product_container", packaging_outputs=_Outputs()))
        self.assertIn("compact", str(refused.exception))

    def test_the_profile_is_derived_from_the_fit_on_one_isotropic_anchor(self):
        fit = m3.load_m3_fit()
        profile, g, der = m3.m3_profile_geometry(31.5, self.RETAINED, "bottle")
        span0, span1 = fit["assembly_span_px"]
        body_hw = max([fit["fits"]["GLASS"]["start"][0]] + [pt[0] for seg in fit["fits"]["GLASS"]["segments"] for pt in seg])
        scale = 31.5 / (2.0 * body_hw)
        self.assertEqual(profile.width_mm, 31.5)
        self.assertAlmostEqual(profile.height_mm, (span1 - span0) * scale, places=3)
        self.assertAlmostEqual(g["bulb_height_mm"], (fit["fits"]["DARK_CLOSURE"]["band_px"][1] - fit["fits"]["DARK_CLOSURE"]["band_px"][0]) * scale, places=3)
        self.assertAlmostEqual(g["collar_height_mm"], (fit["fits"]["COLLAR"]["band_px"][1] - fit["fits"]["COLLAR"]["band_px"][0]) * scale, places=3)
        self.assertEqual(g["base_thickness_mm"], 3.5)                       # retained, never invented
        self.assertEqual(der["source"], m3.DRAWING_M3_FIT)
        self.assertTrue(der["isotropic"])
        self.assertEqual(der["field_sources"]["body_diameter_mm"], "ANCHOR")
        self.assertEqual(der["field_sources"]["total_height_mm"], "M3_FIT")
        self.assertEqual(der["field_sources"]["frost_intensity"], "RETAINED_FROM_CONFIRMED")
        # the backbone built from the derived profile fills the box isotropically: sx == sy
        bb = m3.build_m3_dropper_backbone(profile)
        # the drawn curve lies inside its control polygon; the builder normalises the outline's
        # CONTROL-POINT extent to the box (build_m3_dropper_backbone), so that is what is measured —
        # end points alone read 31.46, the fit's sub-pixel residual against the box, not a scale error
        xs = [getattr(s, a) for s in bb.silhouette for a in ("x", "x1", "x2") if hasattr(s, a)]
        ys = [getattr(s, a) for s in bb.silhouette for a in ("y", "y1", "y2") if hasattr(s, a)]
        self.assertAlmostEqual(max(xs) - min(xs), 31.5, places=6)
        self.assertAlmostEqual(max(ys), profile.height_mm, places=6)
        # sx == sy to the profile's own 3-decimal rounding of its height (<= 5e-7 mm/px over the span)
        self.assertAlmostEqual(profile.height_mm / (span1 - span0), (31.5 / 2.0) / body_hw, places=6)

    def test_the_m3_drawing_emits_every_required_material_object(self):
        from apps.ire.compose_dropper import _bottle_group_m3
        from apps.ire.container_concept_fidelity import REQUIRED_MATERIAL_OBJECTS
        profile, g, _ = m3.m3_profile_geometry(31.5, self.RETAINED, "bottle")
        bb = m3.build_m3_dropper_backbone(profile)
        group = _bottle_group_m3(bb, g, 10.0, 10.0, 1.0)
        names = {c.name for c in group.children}
        missing = [n for n in REQUIRED_MATERIAL_OBJECTS if n not in names]
        self.assertEqual(missing, [])
        self.assertIn("silhouette-outline", names)
        self.assertEqual(group.role, "product")

    def test_the_dispatcher_keeps_the_parametric_group_byte_identical_and_draws_the_fit_on_request(self):
        from apps.ire.compose_dropper import _bottle_group, _draw_bottle
        profile, g, _ = m3.m3_profile_geometry(31.5, self.RETAINED, "bottle")
        bb = m3.build_m3_dropper_backbone(profile)
        a = _bottle_group(g, 5.0, 5.0, 1.2, name="Bottle")
        b = _draw_bottle(g, 5.0, 5.0, 1.2, name="Bottle", drawing_source=m3.DRAWING_PARAMETRIC)   # §BH49(a): by declaration
        self.assertEqual(a.model_dump(), b.model_dump())
        with self.assertRaises(ValueError) as ctx:                                  # no source named = M3_FIT, which needs its backbone
            _draw_bottle(g, 5.0, 5.0, 1.2, name="Bottle")
        self.assertTrue(str(ctx.exception).startswith("M3_FIT_BACKBONE_REQUIRED"))
        c = _draw_bottle(g, 5.0, 5.0, 1.2, name="Bottle", drawing_source=m3.DRAWING_M3_FIT, backbone=bb)
        self.assertNotEqual(a.model_dump(), c.model_dump())
        glass = next(ch for ch in c.children if ch.name == "GLASS_OUTER_WALL")
        # the fit's glass outline, mapped: its extent is the derived box at the panel's scale
        xs = [getattr(s, a) for s in glass.segments for a in ("x", "x1", "x2") if hasattr(s, a)]
        self.assertAlmostEqual(max(xs) - min(xs), 31.5 * 1.2, places=6)

    def test_the_product_path_resolves_to_m3_by_construction_and_the_others_only_by_declaration(self):
        """§BH49(a): no record, or a record that names no source, is M3_FIT; PARAMETRIC only by declaration;
        a declaration naming anything else is refused by name — never read as a source. REFIT is one of those
        since the clean-up of 2026-10-04 removed it."""
        self.assertEqual(m3.drawing_source_of({}), m3.DRAWING_M3_FIT)
        self.assertEqual(m3.drawing_source_of({m3.DRAWING_SOURCE_SCHEMA: {"note": "no source key"}}), m3.DRAWING_M3_FIT)
        self.assertEqual(m3.drawing_source_of({m3.DRAWING_SOURCE_SCHEMA: {"source": m3.DRAWING_M3_FIT}}), m3.DRAWING_M3_FIT)
        self.assertEqual(m3.drawing_source_of({m3.DRAWING_SOURCE_SCHEMA: {"source": m3.DRAWING_PARAMETRIC}}), m3.DRAWING_PARAMETRIC)
        self.assertFalse(hasattr(m3, "DRAWING_REFIT"))
        with self.assertRaises(ValueError) as gone:                   # REFIT, removed 2026-10-04: refused by name
            m3.drawing_source_of({m3.DRAWING_SOURCE_SCHEMA: {"source": "REFIT"}})
        self.assertTrue(str(gone.exception).startswith(m3.DRAWING_SOURCE_UNKNOWN))
        with self.assertRaises(ValueError) as ctx:
            m3.drawing_source_of({m3.DRAWING_SOURCE_SCHEMA: {"source": "SOMETHING_ELSE"}})
        self.assertTrue(str(ctx.exception).startswith(m3.DRAWING_SOURCE_UNKNOWN))
        # §BH50(a) retired the status §BH49(b) held an M3 render at while the five rules waited for the owner
        self.assertFalse(hasattr(m3, "REFUSED_PENDING_RULING") or hasattr(m3, "PENDING_RULING_CODES"))

    def test_the_sheet_composes_with_the_fit_when_asked(self):
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.tests.test_wiv_leading_comparison import _BACK_ZONE, _FRONT_ZONE
        profile, g, _ = m3.m3_profile_geometry(31.5, self.RETAINED, "bottle")
        bb = m3.build_m3_dropper_backbone(profile)
        kw = dict(zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None, logo_path=None, product_name="Rose Damascena",
                  sku="X", back_sections=[{"heading": "P", "text": "x"}], revision_status="TEST")
        doc_p = compose_dropper_sheet(g, drawing_source=m3.DRAWING_PARAMETRIC, **kw)   # §BH49(a): by declaration
        doc_m = compose_dropper_sheet(g, drawing_source=m3.DRAWING_M3_FIT, backbone=bb, **kw)
        doc_d = compose_dropper_sheet(g, **kw)                                            # nothing named: the product's
        def hero(doc):
            for node, _ in doc.walk():
                if getattr(node, "type", "") == "group" and node.name == "Bottle":
                    return node
        hp, hm = hero(doc_p), hero(doc_m)
        self.assertIsNotNone(hp)
        self.assertIsNotNone(hm)
        self.assertNotEqual(hp.model_dump(), hm.model_dump())
        self.assertEqual({c.name for c in hp.children if c.type == "path"} <= {c.name for c in hm.children}, True)
        # §BH49(a): the composers draw from the accepted M3 concept by construction — the undeclared sheet IS the M3 sheet
        self.assertEqual(hero(doc_d).model_dump(), hm.model_dump())
        # §BH50(a): THE M3 RENDER PASSES THE FIVE RE-RULED GEOMETRY RULES, measured against the derived geometry as the
        # live path measures it -- and passes every other concept-fidelity axis, so nothing blocks it
        from apps.ire import container_concept_fidelity as ccf
        self.assertEqual(ccf.measure_concept_fidelity(doc_m, g)["failures"], [])
        # ...and the bands describe the M3 DRAWING, not the numbers: the same derived numbers drawn by the parametric
        # group read collar w/h 1.09 and bulb aspect 1.26, outside two bands -- the ruling's first caveat, pinned;
        # §BH50(f)(8) line 7: its glass, drawn parametric, reads a waist of 0.6225 x body, 0.0265 outside the
        # visible-waist band, so NECK joins the set (measured, the reading's prediction confirmed)
        self.assertEqual(set(ccf.measure_concept_fidelity(doc_p, g)["failures"]),
                         {ccf.COLLAR_GEOMETRY_FAILED, ccf.BULB_GEOMETRY_FAILED, ccf.NECK_GEOMETRY_MISSING})

    def test_the_band_widths_are_owner_calibrated_by_the_list(self):
        """§BH50(f)(8), line 6: the widths move from PROVISIONAL_PENDING_OWNER_CALIBRATION to
        OWNER_CALIBRATED with a provenance naming the ruling and the register; at this commit the five
        tuples are the landed ones to the last digit — no width tightens, none is widened by the executor
        — and every centre stays MEASURED. Pinned exactly, so a vetoed line moves this test and not a
        reader.

        §BH50(f)(8) line 7, annotated at its own commit: lines 1, 3, 4 and 5 are unmoved; line 7 replaced
        rule 3's band with the visible waist's, its centre set by the waist reader on the M3 sheet and its
        ±0.01 the list's, and the visible_neck axis carries its own note; the §BH50(a) box band is kept in
        the module as history.

        §BH50(f)(8) line 8, annotated at its own commit: line 8 adds two tuples, SHAFT_TO_COLLAR_BAND and
        BULB_SLENDERNESS_BAND, their centres set by the dome reader on the M3 sheet and their widths the
        list's; bulb_slim_dome carries a note naming both sources."""
        from apps.ire import container_concept_fidelity as ccf
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.tests.test_wiv_leading_comparison import _BACK_ZONE, _FRONT_ZONE
        self.assertEqual(ccf.GEOMETRY_BAND_WIDTH_STATUS, "OWNER_CALIBRATED")
        for phrase in ("§BH50(f)(8)", "OWNER_BLOCKER_CLEARANCE.md", "until a line is vetoed", "centres MEASURED"):
            self.assertIn(phrase, ccf.GEOMETRY_BAND_PROVENANCE)
        self.assertIn("width OWNER_CALIBRATED (§BH50(f)(8))", ccf.GEOMETRY_BAND_NOTE)
        self.assertEqual(ccf.TOP_TO_BODY_BAND, (0.6224667052692532, 0.03))
        # §BH50(f)(8) line 7: rule 3's centre is the visible waist the reader sets on the M3 sheet, ±0.01
        self.assertEqual(ccf.NECK_TO_BODY_BAND, (0.5859757644664311, 0.01))
        self.assertEqual(ccf.COLLAR_WIDTH_TO_HEIGHT_BAND, (1.185789055868289, 0.04))
        self.assertEqual(ccf.BULB_WIDTH_TO_COLLAR_BAND, (0.7788018433179724, 0.03))
        self.assertEqual(ccf.BULB_ASPECT_BAND, (1.189352416173569, 0.06))     # §BH54(c): its own method's value
        # §BH50(f)(8) line 8: the dome's two legs, centres set by the reader on the M3 sheet
        self.assertEqual(ccf.SHAFT_TO_COLLAR_BAND, (0.5023041474654419, 0.01))
        self.assertEqual(ccf.BULB_SLENDERNESS_BAND, (1.8440418195718484, 0.05))
        # the persisted note travels on every re-ruled axis of the M3 sheet, and the sheet still passes all five
        profile, g, _ = m3.m3_profile_geometry(31.5, self.RETAINED, "bottle")
        doc_m = compose_dropper_sheet(g, drawing_source=m3.DRAWING_M3_FIT, backbone=m3.build_m3_dropper_backbone(profile),
                                      zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None, logo_path=None,
                                      product_name="Rose Damascena", sku="X", back_sections=[{"heading": "P", "text": "x"}],
                                      revision_status="TEST")
        report = ccf.measure_concept_fidelity(doc_m, g)
        self.assertEqual(report["failures"], [])
        noted = {a["axis"] for a in report["axes"] if a.get("note") == ccf.GEOMETRY_BAND_NOTE}
        # §BH50(f)(8) line 7: visible_neck carries the waist band's own note and names its section in its target
        # §BH50(f)(8) line 8: bulb_slim_dome carries the note naming both of its sources
        self.assertEqual(noted, {"cylindrical_form", "shoulder_geometry", "collar_cylindrical_geometry"})
        bulb = {a["axis"]: a for a in report["axes"]}["bulb_slim_dome"]
        self.assertEqual(bulb["note"], ccf.DOME_BAND_NOTE)
        self.assertIn("§BH50(f)(8) line 8", bulb["target"])
        self.assertIn("line 8", ccf.GEOMETRY_BAND_PROVENANCE)
        neck = {a["axis"]: a for a in report["axes"]}["visible_neck"]
        self.assertEqual(neck["note"], ccf.WAIST_BAND_NOTE)
        self.assertIn("§BH50(f)(8) line 7", neck["target"])
        self.assertIn("line 7", ccf.GEOMETRY_BAND_PROVENANCE)

    def test_every_band_line_carries_where_its_width_came_from(self):
        """§BH50(g)(3), re-typed §BH53(a): "A BAND WITHOUT A DERIVATION IS NOT EVIDENCE. Every band line carries where
        its width came from — measured variation, a physical tolerance, or my typed word. The waist and shaft ±0.01
        have none: derive or widen them to what measurement supports, and say which." DERIVED, not widened: the seven
        lines each carry a saved width source; the waist and the shaft record the measured figure (the list's one
        method on the HEAD fit record) apart from the round-up to the printed 0.01; a derivation never tightens a
        landed width; line 5 says plainly that its width sits below its own method's range; and the source travels on
        every re-ruled axis of the M3 sheet as `tolerance_source`. [§BH54(c), 2026-09-18: line 5 is WIDENED to its own
        method's value — ±0.06, the measured 0.0567191 and the round-up apart; no line sits below its method now.]"""
        from apps.ire import container_concept_fidelity as ccf
        S = ccf.GEOMETRY_BAND_WIDTH_SOURCES
        bands = {"TOP_TO_BODY_BAND": ccf.TOP_TO_BODY_BAND, "NECK_TO_BODY_BAND": ccf.NECK_TO_BODY_BAND,
                 "COLLAR_WIDTH_TO_HEIGHT_BAND": ccf.COLLAR_WIDTH_TO_HEIGHT_BAND,
                 "BULB_WIDTH_TO_COLLAR_BAND": ccf.BULB_WIDTH_TO_COLLAR_BAND, "BULB_ASPECT_BAND": ccf.BULB_ASPECT_BAND,
                 "SHAFT_TO_COLLAR_BAND": ccf.SHAFT_TO_COLLAR_BAND, "BULB_SLENDERNESS_BAND": ccf.BULB_SLENDERNESS_BAND}
        self.assertEqual(set(S), set(bands))
        for name, (_centre, half) in bands.items():
            src = S[name]
            self.assertIn(src["class"], ("MEASURED_VARIATION", "PHYSICAL_TOLERANCE", "OWNER_TYPED", "BELOW_METHOD"), name)
            self.assertEqual(src["half"], half, name)
            self.assertIn("§BH50(g)(3)", src["ruling"], name)
            self.assertTrue(src["derivation"] and src["line"], name)
        # the two he named: DERIVED — the measured figure below the landed width, the round-up stated, the numbers unchanged
        waist, shaft = S["NECK_TO_BODY_BAND"], S["SHAFT_TO_COLLAR_BAND"]
        self.assertEqual((waist["decision"], shaft["decision"]), ("DERIVED", "DERIVED"))
        self.assertAlmostEqual(waist["measured_half"], 0.0079, places=5)
        self.assertAlmostEqual(shaft["measured_half"], 0.00696, places=5)
        self.assertLess(waist["measured_half"], waist["half"])
        self.assertLess(shaft["measured_half"], shaft["half"])
        self.assertEqual((waist["rounded_to"], shaft["rounded_to"]), (0.01, 0.01))
        self.assertEqual((ccf.NECK_TO_BODY_BAND, ccf.SHAFT_TO_COLLAR_BAND),
                         ((0.5859757644664311, 0.01), (0.5023041474654419, 0.01)))
        # a derivation never tightens: every measured figure or range floor sits at or below the landed width —
        # line 5 included since §BH54(c) widened it (until 2026-09-18 it said BELOW_METHOD by class and was not moved)
        for name, src in S.items():
            floor = src.get("measured_half") if src.get("measured_half") is not None else src["method_range"][0]
            self.assertLessEqual(round(floor, 6), src["half"], name)
        five = S["BULB_ASPECT_BAND"]
        self.assertEqual((five["class"], five["decision"], five["rounded_to"]), ("MEASURED_VARIATION", "WIDENED", 0.06))
        self.assertAlmostEqual(five["measured_half"], 0.0567191, places=6)
        self.assertLess(five["measured_half"], five["half"])
        self.assertIn("§BH54(c)", five["ruling"])
        self.assertIn("±0.04", five["history"])
        for phrase in ("§BH50(g)(3)", "DERIVED", "tolerance_source"):
            self.assertIn(phrase, ccf.GEOMETRY_BAND_PROVENANCE)
        self.assertIn("§BH50(g)(3): width DERIVED", ccf.WAIST_BAND_NOTE)
        self.assertIn("§BH50(g)(3): the shaft's ±0.01 DERIVED", ccf.DOME_BAND_NOTE)
        # the source travels on the record: every re-ruled axis of the M3 sheet carries tolerance_source
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.tests.test_wiv_leading_comparison import _BACK_ZONE, _FRONT_ZONE
        profile, g, _ = m3.m3_profile_geometry(31.5, self.RETAINED, "bottle")
        doc_m = compose_dropper_sheet(g, drawing_source=m3.DRAWING_M3_FIT, backbone=m3.build_m3_dropper_backbone(profile),
                                      zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None, logo_path=None,
                                      product_name="Rose Damascena", sku="X", back_sections=[{"heading": "P", "text": "x"}],
                                      revision_status="TEST")
        axes = {a["axis"]: a for a in ccf.measure_concept_fidelity(doc_m, g)["axes"]}
        self.assertEqual(axes["visible_neck"]["tolerance_source"], S["NECK_TO_BODY_BAND"])
        self.assertEqual(axes["cylindrical_form"]["tolerance_source"], S["TOP_TO_BODY_BAND"])
        self.assertEqual(axes["shoulder_geometry"]["tolerance_source"], S["TOP_TO_BODY_BAND"])
        self.assertEqual(axes["collar_cylindrical_geometry"]["tolerance_source"], S["COLLAR_WIDTH_TO_HEIGHT_BAND"])
        self.assertEqual(axes["bulb_slim_dome"]["tolerance_source"],
                         {"width_vs_collar": S["BULB_WIDTH_TO_COLLAR_BAND"], "aspect": S["BULB_ASPECT_BAND"],
                          "shaft_vs_collar": S["SHAFT_TO_COLLAR_BAND"], "slenderness": S["BULB_SLENDERNESS_BAND"]})
        # and an axis the list did not re-rule carries none: the source is said where a band decides, nowhere else
        self.assertNotIn("tolerance_source", axes["collar_metallic_material"])

    def test_the_nineteen_inline_limits_are_recorded_and_four_are_applied_and_five_held_at_their_literals(self):
        """§BH54(c): "The nineteen inline literals: recompute each under its own method and take the result, recording
        the measured figure and any round-up apart, as (g)(3) did. A band tighter than the measurement that made it is
        not evidence." Nineteen entries, each with its class, origin, M3 measurement, method and method value; no
        method value is WIDER than its literal; the eight readings (nine literals) whose value is tighter are RECORDED
        and NOT APPLIED — his (c) against the list he ratified, "NO landed width tightens" (§BH50(f)(8)) — so no
        literal moved: every axis still prints the limit the table records, and carries the table's entry.

        [§BH54(b) (m), 2026-09-19 — "THE EIGHT TIGHTENINGS: APPLY, with one check … if a tightened band would refuse a
        render I have accepted or am being shown, do not apply that one: report the pair and leave its literal,
        because a rule that refuses my own chosen design is describing something other than my design"; hard
        stop: "a band applied that refuses a design I have been shown". The check, over every stored record of a
        render he has been shown, in exact arithmetic against this module's own rounding: FOUR literals are refused
        by none and are APPLIED — the limit IS the method's value, the literal it was kept beside it; FIVE are
        HELD_AT_ITS_LITERAL, each naming its pairs — REFIT, July's, PARAMETRIC, none a render he chose — on the
        wider reading of his hard stop, until he says which renders count; still tighter on the record than the
        literal that stands. The paragraph above is 37ba1bb's, kept as the history it is.]"""
        from apps.ire import container_concept_fidelity as ccf
        L = ccf.INLINE_LIMIT_SOURCES
        self.assertEqual(len(L), 19)
        for name, e in L.items():
            self.assertIn(e["class"], ccf.INLINE_LIMIT_CLASSES, name)
            self.assertIn(e["decision"], ccf.INLINE_LIMIT_DECISIONS, name)
            self.assertIn(e["ruling"], ("§BH54(c)", "§BH54(b) (m)", "§BH54(b) (o)", "§BH54(b) (p)"), name)
            self.assertTrue(e["origin"] and e["method"] and e["why"] and e["measured_m3"], name)
        applied = {n for n, e in L.items() if e["decision"] == "APPLIED"}
        held = {n for n, e in L.items() if e["decision"] == "HELD_AT_ITS_LITERAL"}
        self.assertEqual(applied, {"bottle_aspect_ratio", "collar_diameter_rel_body", "collar_scale_width",
                                   "bulb_width_vs_collar"})
        self.assertEqual(held, {"body_silhouette_proportion", "body_squat_floor", "visible_base_thickness",
                                "bulb_to_collar_proportion", "collar_scale_height"})
        self.assertNotIn("RECORDED_NOT_APPLIED", {e["decision"] for e in L.values()})
        self.assertEqual(len({L[n]["reading"] for n in applied | held}), 8)  # the collar width is decided twice
        for n in applied | held:
            self.assertEqual((L[n]["class"], L[n]["ruling"], L[n]["recorded_under"]),
                             ("MEASURED_VARIATION", "§BH54(b) (m)", "§BH54(c) (37ba1bb)"), n)
        for n in held:                                                      # a held band names the renders that hold it
            self.assertTrue(L[n]["why"].startswith(ccf._HELD_RULE) and L[n]["why"].endswith(ccf._HELD_BY[n]), n)
            self.assertTrue("REFIT" in L[n]["why"] or "July" in L[n]["why"], n)
            self.assertNotIn("was", L[n])                                   # its literal is what it was
        self.assertEqual({n for n, e in L.items() if e["ruling"] == "§BH54(c)"},
                         set(L) - applied - held - {"hero_leading_ceiling", "front_print_share_ceiling"})
        # §BH54(b) (o): the hero-leading ceiling compares like with like — em with em — against the composer's ruled
        # constant; the literal it was, and the units it was compared in, stay on the record
        from apps.ire import compose_dropper
        lead = L["hero_leading_ceiling"]
        self.assertEqual((lead["decision"], lead["class"], lead["ruling"], lead["recorded_under"]),
                         ("UNITS_CORRECTED", "COMPOSER_CONSTANT", "§BH54(b) (o)", "§BH54(c) (37ba1bb)"))
        self.assertEqual(lead["limit"], compose_dropper.NAME_LEADING_EM)
        self.assertEqual((lead["was"], lead["was_class"]), (1.45, "EDITORIAL"))
        self.assertIn("MILLIMETRES against POINTS", lead["was_units"])
        # §BH54(b) (p): the front-share ceiling keeps its one number and judges the PRINT, not the zone
        share = L["front_print_share_ceiling"]
        self.assertEqual((share["decision"], share["limit"], share["ruling"], share["recorded_under"]),
                         ("QUANTITY_RE_RULED", 0.60, "§BH54(b) (p)", "§BH54(c) (37ba1bb)"))
        self.assertIn("PRINT", share["quantity"])
        self.assertIn("ZONE", share["was_quantity"])
        # the method never gives a WIDER value than the literal (so widening was never owed), and rounding never tightens
        for n in ("bottle_aspect_ratio", "body_silhouette_proportion", "bulb_to_collar_proportion",
                  "collar_diameter_rel_body", "collar_scale_width", "collar_scale_height", "bulb_width_vs_collar"):
            mv = L[n]["method_value"]
            self.assertLessEqual(mv["measured"], mv["rounded"], n)          # the round-up, apart, and never down
            if n in applied:                                                # the limit IS the method's value, and the
                self.assertEqual(L[n]["limit"], mv[L[n].get("limit_takes", "rounded")], n)   # literal it was is wider
                self.assertLess(L[n]["limit"], L[n]["was"], n)
            else:
                self.assertLess(mv["rounded"], L[n]["limit"], n)            # held: still tighter than what stands
        floor = L["body_squat_floor"]
        self.assertLessEqual(floor["method_value"]["rounded"], floor["method_value"]["floor_grid"])      # a floor rounds DOWN
        self.assertGreater(floor["method_value"]["rounded"], floor["limit"])
        base = L["visible_base_thickness"]
        self.assertLessEqual(base["method_value"]["rounded"][0], base["method_value"]["range_grid"][0])  # a range rounds outward
        self.assertGreaterEqual(base["method_value"]["rounded"][1], base["method_value"]["range_grid"][1])
        self.assertTrue(base["limit"][0] < base["method_value"]["rounded"][0] < base["method_value"]["rounded"][1] < base["limit"][1])
        self.assertEqual(L["logo_zone_share_ceiling"]["limit"], ccf.LOGO_ZONE_SHARE_CEILING)
        # on the M3 sheet: the axes the literals decide carry the entries, print the recorded limits, and still pass
        doc, g = self._m3_sheet()
        report = ccf.measure_concept_fidelity(doc, g)
        self.assertEqual(report["failures"], [])
        axes = {a["axis"]: a for a in report["axes"]}
        carried = {
            "bottle_aspect_ratio": L["bottle_aspect_ratio"],
            "body_silhouette_proportion": {"proportion": L["body_silhouette_proportion"], "squat_floor": L["body_squat_floor"]},
            "visible_base_thickness": L["visible_base_thickness"],
            "bulb_to_collar_proportion": L["bulb_to_collar_proportion"],
            "collar_diameter_rel_body": L["collar_diameter_rel_body"],
            "transparency_relationship": {"wall": L["glass_wall_opacity_ceiling"], "fill": L["product_fill_opacity_range"],
                                          "frost": L["frost_opacity_ceiling"]},
            "generic_label_fallback": L["label_rect_opacity_floor"],
            "front_print_share_of_body": L["front_print_share_ceiling"],
            "collar_scale_vs_body": {"width_ratio": L["collar_scale_width"], "height_ratio": L["collar_scale_height"]},
            "bulb_width_vs_collar": L["bulb_width_vs_collar"],
            "closure_assembly_connection": L["closure_connection_slack_mm"],
            "product_name_unified_block": L["hero_leading_ceiling"],
            "frosted_glass_visualization": L["glass_base_opacity_ceiling"],
            "logo_restraint": L["logo_zone_share_ceiling"],
        }
        present = set(carried) & set(axes)
        self.assertGreaterEqual(len(present), 13, sorted(set(carried) - set(axes)))   # the logo axis needs a logo file
        for axis in present:
            self.assertEqual(axes[axis]["tolerance_source"], carried[axis], axis)
            entries = carried[axis].values() if "limit" not in carried[axis] else [carried[axis]]
            printed = str(axes[axis].get("tolerance") or "") + " " + str(axes[axis].get("target") or "")
            for e in entries:
                if e["limit_text"] is not None:
                    self.assertIn(e["limit_text"], printed, axis)
        # the top-edge window is recorded and carried on no axis of its own; an axis no literal decides carries none
        self.assertEqual(L["top_edge_window_mm"]["decision"], "READER_PARAMETER_RECORDED")
        self.assertEqual(axes["cylindrical_form"]["tolerance_source"], ccf.GEOMETRY_BAND_WIDTH_SOURCES["TOP_TO_BODY_BAND"])
        self.assertNotIn("tolerance_source", axes["collar_metallic_material"])

    def test_the_front_share_judges_the_print_and_a_widened_zone_alone_is_not_a_label(self):
        """§BH54(b) (p): "measure what it was protecting and what it reads on the chosen design. If it describes July's
        bottle rather than mine, re-rule it". The axis is named front PRINT share and measured the ZONE — the area he
        permits. Widening the zone to hold his own product's name (§BH54(f)) moved it from 0.45 to 0.56 with no mark
        added; past 29.47 mm it would have refused bare glass as a "generic label". It judges the PRINT now — the
        composer's own scale-free placements — and the zone's share is recorded and rules nothing."""
        import copy

        from apps.ire import container_concept_fidelity as ccf
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.tests.test_back_panel import _FRONT_RECORD
        from apps.ire.tests.test_wiv_leading_comparison import _BACK_ZONE, _FRONT_ZONE

        def axis_of(doc, g):
            report = ccf.measure_concept_fidelity(doc, g)
            return next(a for a in report["axes"] if a["axis"] == "front_print_share_of_body"), report["failures"]

        doc, g = self._m3_sheet()
        axis, failures = axis_of(doc, g)
        placed = [p for p in doc.metadata["placements"] if p["zone_id"] == doc.metadata["front_zone_id"]]
        of_zone = sum(p["nw"] * p["nh"] for p in placed)
        self.assertEqual(axis["state"], "MEASURED_PASS")
        self.assertEqual(axis["value"]["zone_of_glass"], 0.47)                     # what the axis used to judge
        self.assertEqual(axis["value"]["print_of_zone"], round(of_zone, 3))
        self.assertAlmostEqual(axis["value"]["print_of_glass"], 0.4736 * of_zone, places=2)
        self.assertEqual((axis["value"]["placements"], axis["target"]), (len(placed), "print ≤0.60 of the glass"))
        # a WIDER ZONE alone — 30 mm, 0.65 of the glass, no mark added — was a "generic label"; it is not one
        profile, g2, _ = m3.m3_profile_geometry(31.5, self.RETAINED, "bottle")
        wide = compose_dropper_sheet(g2, drawing_source=m3.DRAWING_M3_FIT, backbone=m3.build_m3_dropper_backbone(profile),
                                     zones=[{**_FRONT_ZONE, "x": 0.8, "width": 30.0}, _BACK_ZONE], reference_path=None,
                                     logo_path=None, product_name="Rose Damascena", sku="X",
                                     back_sections=[{"heading": "P", "text": "x"}], revision_status="TEST",
                                     **_FRONT_RECORD)      # §BH67(c)2: the record's two lines, as measured
        axis, failures = axis_of(wide, g2)
        self.assertGreater(axis["value"]["zone_of_glass"], 0.60)                   # the old rule's failing case
        self.assertEqual(axis["state"], "MEASURED_PASS")
        self.assertNotIn(ccf.GENERIC_LABEL_FALLBACK_USED, failures)
        # a front that PRINTS more than 0.60 of the glass is still refused, by the code the axis has always named
        inked = copy.deepcopy(wide)
        inked.metadata["placements"] = [{**p, "nx": 0.0, "nw": 1.0, "nh": 0.2} for p in placed]      # five bands, 1.0 of the zone
        axis, failures = axis_of(inked, g2)
        self.assertEqual(axis["state"], "MEASURED_FAIL")
        self.assertIn(ccf.GENERIC_LABEL_FALLBACK_USED, failures)
        # a document that records no front placement has no print to measure: UNMEASURED, never a pass
        bare = copy.deepcopy(doc)
        bare.metadata["placements"] = []
        axis, failures = axis_of(bare, g)
        self.assertEqual((axis["state"], axis["value"]), ("UNMEASURED", {"zone_of_glass": 0.47, "placements": 0}))
        self.assertNotIn(ccf.GENERIC_LABEL_FALLBACK_USED, failures)

    def _m3_sheet(self):
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.tests.test_back_panel import _FRONT_RECORD
        from apps.ire.tests.test_wiv_leading_comparison import _BACK_ZONE, _FRONT_ZONE
        profile, g, _ = m3.m3_profile_geometry(31.5, self.RETAINED, "bottle")
        # §BH67(c)2: the front's two record lines handed in — the five placements these axes were measured on
        doc = compose_dropper_sheet(g, drawing_source=m3.DRAWING_M3_FIT, backbone=m3.build_m3_dropper_backbone(profile),
                                    zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None, logo_path=None,
                                    product_name="Rose Damascena", sku="X", back_sections=[{"heading": "P", "text": "x"}],
                                    revision_status="TEST", **_FRONT_RECORD)
        return doc, g

    def test_rule_3_reads_the_visible_waist_and_a_pinched_waist_fails_it(self):
        """§BH50(f)(8) line 7, red before this commit. The M3 sheet's waist reads the band's centre by the reader
        that set it; the glass outline narrowed by 1.64 mm a side across the waist interval — a visibly pinched
        neck, the NECK_GLASS rectangle untouched — fails the band, where the rectangle reading passed it."""
        from apps.ire import container_concept_fidelity as ccf
        doc, g = self._m3_sheet()
        axis = {a["axis"]: a for a in ccf.measure_concept_fidelity(doc, g)["axes"]}["visible_neck"]
        self.assertEqual(axis["state"], "MEASURED_PASS")
        self.assertEqual(axis["value"]["waist_over_body"], round(ccf.NECK_TO_BODY_BAND[0], 4))
        self.assertTrue(axis["target"].startswith("waist proportion"))
        nodes = ccf._nodes_by_name(doc)
        wall = nodes["GLASS_OUTER_WALL"]
        box = ccf._node_bbox(wall)
        cx = box[0] + box[2] / 2.0
        y_lo, y_hi = ccf._visible_waist(nodes)["between_mm"]
        for s in wall.segments:
            for ax, ay in (("x", "y"), ("x1", "y1"), ("x2", "y2")):
                if hasattr(s, ax) and y_lo <= float(getattr(s, ay)) <= y_hi:
                    x = float(getattr(s, ax))
                    setattr(s, ax, x - 1.64 if x > cx else x + 1.64)
        report = ccf.measure_concept_fidelity(doc, g)
        self.assertIn(ccf.NECK_GEOMETRY_MISSING, report["failures"])
        pinched = {a["axis"]: a for a in report["axes"]}["visible_neck"]["value"]["waist_over_body"]
        self.assertLess(pinched, ccf.NECK_TO_BODY_BAND[0] - ccf.NECK_TO_BODY_BAND[1])

    def test_rule_3_reads_the_glass_outline_not_the_neck_rectangle(self):
        """Red before this commit: narrowing the NECK_GLASS rectangle by 1.6 mm, 0.8 mm a side, inside the collar
        that covers it — the glass outline untouched — moved the rectangle reading by 0.0416, to 0.5618, 0.0116
        below its ±0.03 band, and refused the drawing (whether the edit shows at all is unverified as a render: the
        rectangle's bottom edge meets the collar's). The waist reader reads the outline, so the same edit leaves
        rule 3 exactly where it was."""
        from apps.ire import container_concept_fidelity as ccf
        doc, g = self._m3_sheet()
        before = {a["axis"]: a for a in ccf.measure_concept_fidelity(doc, g)["axes"]}["visible_neck"]["value"]
        rect = ccf._nodes_by_name(doc)["NECK_GLASS"]
        rect.x = float(rect.x) + 0.8
        rect.w = float(rect.w) - 1.6
        report = ccf.measure_concept_fidelity(doc, g)
        self.assertNotIn(ccf.NECK_GEOMETRY_MISSING, report["failures"])
        self.assertEqual({a["axis"]: a for a in report["axes"]}["visible_neck"]["value"], before)

    def test_an_absent_waist_reads_measured_fail_never_a_pass(self):
        """An empty interval (the shoulder ellipse's centre at or above the collar's bottom) and a segment-less
        outline each read MEASURED_FAIL with the waist reader's own reason — the rule fails closed, red before this
        commit on both halves (the rectangle reading gave a bare "absent" or a number)."""
        from apps.ire import container_concept_fidelity as ccf
        doc, g = self._m3_sheet()
        nodes = ccf._nodes_by_name(doc)
        ell = nodes["SHOULDER_ELLIPSE"]
        ell_box = ccf._node_bbox(ell)
        collar_box = ccf._node_bbox(nodes["COLLAR_ROSE_GOLD_BASE"])
        shift = (collar_box[1] + collar_box[3]) - (ell_box[1] + ell_box[3]) - 0.5
        for s in ell.segments:
            for ay in ("y", "y1", "y2"):
                if hasattr(s, ay):
                    setattr(s, ay, float(getattr(s, ay)) + shift)
        report = ccf.measure_concept_fidelity(doc, g)
        axis = {a["axis"]: a for a in report["axes"]}["visible_neck"]
        self.assertEqual(axis["state"], "MEASURED_FAIL")
        self.assertTrue(str(axis["value"]).startswith("absent: empty interval"))
        self.assertIn(ccf.NECK_GEOMETRY_MISSING, report["failures"])
        doc2, g2 = self._m3_sheet()
        ccf._nodes_by_name(doc2)["GLASS_OUTER_WALL"].segments = []
        axis2 = {a["axis"]: a for a in ccf.measure_concept_fidelity(doc2, g2)["axes"]}["visible_neck"]
        self.assertEqual(axis2["state"], "MEASURED_FAIL")
        self.assertTrue(str(axis2["value"]).startswith(
            "absent: GLASS_OUTER_WALL, COLLAR_ROSE_GOLD_BASE or SHOULDER_ELLIPSE"))

    def test_rule_5_reads_the_dome_and_a_paddle_with_the_same_box_fails_it(self):
        """§BH50(f)(8) line 8, red before this commit. The M3 sheet's shaft and slenderness read the bands' centres
        by the reader that set them; the bulb outline widened 1.2× over the middle third of its box — a paddle whose
        box the skirt still sets — fails the dome legs while the bulb's box is exactly what it was, where the
        box-only rule passed it."""
        from apps.ire import container_concept_fidelity as ccf
        doc, g = self._m3_sheet()
        before = {a["axis"]: a for a in ccf.measure_concept_fidelity(doc, g)["axes"]}["bulb_slim_dome"]["value"]
        self.assertEqual(before["shaft_vs_collar"], round(ccf.SHAFT_TO_COLLAR_BAND[0], 4))
        self.assertEqual(before["slenderness"], round(ccf.BULB_SLENDERNESS_BAND[0], 4))
        nodes = ccf._nodes_by_name(doc)
        bulb = nodes["BULB_DARK_PLUM"]
        box_before = ccf._node_bbox(bulb)
        cx = box_before[0] + box_before[2] / 2.0
        y_lo, y_hi = ccf._dome(nodes)["between_mm"]
        for s in bulb.segments:
            for ax, ay in (("x", "y"), ("x1", "y1"), ("x2", "y2")):
                if hasattr(s, ax) and y_lo <= float(getattr(s, ay)) <= y_hi:
                    setattr(s, ax, cx + (float(getattr(s, ax)) - cx) * 1.2)
        self.assertEqual(ccf._node_bbox(bulb), box_before)          # the box, unrounded, is the same box
        report = ccf.measure_concept_fidelity(doc, g)
        after = {a["axis"]: a for a in report["axes"]}["bulb_slim_dome"]["value"]
        self.assertIn(ccf.BULB_GEOMETRY_FAILED, report["failures"])
        self.assertEqual(after["curves"], before["curves"])
        self.assertGreater(after["shaft_vs_collar"], ccf.SHAFT_TO_COLLAR_BAND[0] + ccf.SHAFT_TO_COLLAR_BAND[1])
        self.assertLess(after["slenderness"], ccf.BULB_SLENDERNESS_BAND[0] - ccf.BULB_SLENDERNESS_BAND[1])

    def test_an_absent_dome_fails_rule_5_never_passes_it(self):
        """Red before this commit (there was no dome reader). The reader reads "absent" for a missing bulb or a
        segment-less outline; and where the reader is absent on an otherwise passing sheet, rule 5 fails with the
        reason in its value — the one pin that catches a dome leg failing open."""
        from unittest import mock
        from apps.ire import container_concept_fidelity as ccf
        doc, g = self._m3_sheet()
        nodes = ccf._nodes_by_name(doc)
        self.assertEqual(ccf._dome({k: v for k, v in nodes.items() if k != "BULB_DARK_PLUM"})["state"], "absent")
        with mock.patch.object(nodes["BULB_DARK_PLUM"], "segments", []):
            self.assertEqual(ccf._dome(nodes)["state"], "absent")
        with mock.patch.object(ccf, "_dome", return_value={"state": "absent", "reason": "pinned"}):
            report = ccf.measure_concept_fidelity(doc, g)
        axis = {a["axis"]: a for a in report["axes"]}["bulb_slim_dome"]
        self.assertIn(ccf.BULB_GEOMETRY_FAILED, report["failures"])
        self.assertEqual(axis["state"], "MEASURED_FAIL")
        self.assertEqual(axis["value"]["shaft_vs_collar"], "absent: pinned")
        self.assertEqual(axis["value"]["slenderness"], "absent")


def test_his_round_a_tube_s_outline_is_checked_at_the_width_it_is_drawn():
    """His answer after test day finding 3 (2026-09-30), (4) "round": a tube's confirmed width is its round diameter, and
    it is drawn as wide as its flat end, π/2 of it. 117's re-confirmed drawing (product bounds 222.633 × 510.236 pt, 78.5
    by 180 mm) was failed by the outline check against 180 ÷ 50 = 3.6, at 0.363 — "This check fails, so the design cannot
    move on". Read at the width it is drawn it passes its structural half, the bar unchanged at 0.15; a bottle the same
    size is read at its confirmed width as before, and fails."""
    import math
    graph = {"product_bounds": {"width_pt": 222.633, "height_pt": 510.236}}
    tube = {"archetype": "tube", "width_mm": 50.0, "height_mm": 180.0, "cap_style": "flip"}
    axis = _silhouette_axis(graph, tube)
    assert axis["measured"]["structural_silhouette_conformance"] == "PASS", axis
    assert axis["measured"]["expected_aspect"] == round(180.0 / (50.0 * math.pi / 2.0), 3)
    assert axis["measured"]["relative_deviation"] == 0.0
    bottle = _silhouette_axis(graph, dict(tube, archetype="bottle"))
    assert bottle["state"] == "FAIL" and bottle["measured"]["expected_aspect"] == 3.6, bottle
    assert THRESHOLDS["silhouette_max_aspect_deviation"] == 0.15
