"""VQR-2A — fail-closed visual quality gate (server).

The owner-rejected task 53 was structurally valid yet visually unusable, and
the old fidelity report called it MEASURED_PASS with 7/8 axes UNMEASURED.
These tests pin the fix: absence of evidence is never success, an available
AI alone is not Gate-2 readiness, and the current rejected reconstruction
shape FAILS this gate while its artifacts stay inspectable.
"""
import json
from unittest.mock import patch

from django.core.files.base import ContentFile

from apps.ire import container_fidelity as cf
from apps.pipeline.models import GateDecision
from apps.pipeline.services import visual_quality_gate as vq
from apps.pipeline.services.reconstruction_status import (
    build_container_gate2_readiness)

from .test_confirm_profile_ui2b1 import _DELAY, _StatusFixture

# a task-53-shaped .ai: PDF header with the exact rejected A4 MediaBox
AI_A4 = (b"%PDF-1.4\n%bbrose\n"
         b"1 0 obj << /Type /Page /MediaBox [0 0 595.2756 841.8898] >>\n"
         + b"x" * 600)
# a product-derived artboard (bottle 35x95mm -> ~99x269pt, small margin)
AI_PRODUCT = (b"%PDF-1.4\n%bbrose\n"
              b"1 0 obj << /Type /Page /MediaBox [0 0 120 300] >>\n"
              + b"x" * 600)

TASK53_GRAPH = {
    "schema_version": "container_design_graph/1.1",
    "archetype": "bottle",
    "primitives": {"live_text": 8, "logo_rasters": 1, "vector_paths": 8},
    "motif_groups": [],
    "decorative_raster_count": 0,
    "zones_consumed": ["z_front"],
}
PROFILE = {"archetype": "bottle", "variant": "cylindrical",
           "cap_style": "dropper", "width_mm": 35.0, "height_mm": 95.0}


def _passing_axes():
    return {name: vq._axis(vq.PASS) for name in vq.REQUIRED_AXES}


class CombineSemanticsTests(_StatusFixture):
    """§17 — the combiner is the ONLY place overall is decided."""

    def test_all_required_pass_produces_pass(self):
        combined = vq.combine_axes(_passing_axes())
        assert combined["overall"] == vq.PASS
        assert combined["blocking_findings"] == []

    def test_one_required_fail_produces_fail(self):
        axes = _passing_axes()
        axes["artboard_fitness"] = vq._axis(
            vq.FAIL, code=vq.VQ_ARTBOARD_NOT_PRODUCT_DERIVED, reason="A4")
        combined = vq.combine_axes(axes)
        assert combined["overall"] == vq.FAIL
        assert [f["code"] for f in combined["blocking_findings"]] == \
            [vq.VQ_ARTBOARD_NOT_PRODUCT_DERIVED]

    def test_one_required_unmeasured_produces_fail(self):
        axes = _passing_axes()
        axes["silhouette_fidelity"] = vq._axis(
            vq.UNMEASURED, code=vq.VQ_SILHOUETTE_COMPARISON_UNAVAILABLE)
        combined = vq.combine_axes(axes)
        # [§BH71 (0a), the owner's goal of 2026-09-28: "Unmeasured checks … show as a warning beside Approve, never a block." It read
        # overall FAIL with the axis a blocking finding: the overall reads UNMEASURED — never PASS — and the axis
        # is an acceptance warning]
        assert combined["overall"] == vq.UNMEASURED
        assert combined["blocking_findings"] == []
        assert combined["acceptance_warnings"][0]["axis"] == \
            "silhouette_fidelity"

    def test_many_unmeasured_axes_never_pass(self):
        # the exact rejected shape: one pass, seven unmeasured
        axes = {name: vq._axis(vq.UNMEASURED) for name in vq.REQUIRED_AXES}
        axes["artifact_authority"] = vq._axis(vq.PASS)
        combined = vq.combine_axes(axes)
        # [§BH71 (0a): it read overall FAIL with seven blocking findings — seven warnings, and still never PASS]
        assert combined["overall"] == vq.UNMEASURED
        assert combined["blocking_findings"] == []
        assert len(combined["acceptance_warnings"]) == 7
        assert "PASS" not in json.dumps(combined["acceptance_warnings"])

    def test_an_axis_with_no_evaluation_is_a_defect_and_still_refuses(self):
        # §BH71 (0a): an unmeasured axis is a warning beside Approve; an axis nobody evaluated at all is this
        # evaluator's own defect, and it refuses — never waived as a warning
        axes = _passing_axes()
        del axes["closure_fidelity"]
        combined = vq.combine_axes(axes)
        assert combined["overall"] == vq.FAIL
        assert [f["axis"] for f in combined["blocking_findings"]] == ["closure_fidelity"]
        assert axes["closure_fidelity"]["defect"] == "NO_AXIS_EVALUATION"
        assert combined["acceptance_warnings"] == []
        axes = _passing_axes()
        axes["logo_quality"] = {"state": "MAYBE"}
        assert vq.combine_axes(axes)["overall"] == vq.FAIL

    def test_not_applicable_does_not_block_only_when_declared(self):
        axes = _passing_axes()
        axes["closure_fidelity"] = vq._axis(vq.NOT_APPLICABLE)
        assert vq.combine_axes(axes)["overall"] == vq.PASS

    def test_missing_or_malformed_axis_data_becomes_unmeasured(self):
        axes = _passing_axes()
        del axes["composition_quality"]
        axes["logo_quality"] = {"state": "GREAT"}         # malformed
        combined = vq.combine_axes(axes)
        assert combined["overall"] == vq.FAIL
        codes = {f["code"] for f in combined["blocking_findings"]}
        assert "VQ_COMPOSITION_QUALITY_MISSING" in codes
        assert "VQ_LOGO_QUALITY_MISSING" in codes


class EvaluatorTests(_StatusFixture):
    """§18 — required-axis measurements on realistic record shapes."""

    def _quality_task(self, *, ai_bytes=AI_A4, graph=TASK53_GRAPH,
                      profile=PROFILE, spec_extra=None, png=True):
        task = self._task("completed")
        out = task.packaging_outputs.first()
        out.design_preview_ai.delete(save=True)
        out.design_preview_ai.save(f"container_task_{task.id}.ai",
                                   ContentFile(ai_bytes), save=True)
        if not png:
            out.design_preview.delete(save=True)
        spec = dict(out.spec_sheet)
        if graph is not None:
            spec["container_design_graph/1.1"] = graph
        if profile is not None:
            spec["container_profile"] = profile
        spec.update(spec_extra or {})
        out.spec_sheet = spec
        out.save(update_fields=["spec_sheet"])
        return task

    def _axes(self, task):
        report = vq.evaluate_container_visual_quality(task)
        assert report is not None
        return report, report["required_axes"]

    def test_task53_shape_fails_with_measured_and_unmeasured_axes(self):
        task = self._quality_task()
        report, axes = self._axes(task)
        assert report["overall"] == vq.FAIL
        assert report["status"] == vq.BLOCKED_VISUAL_QUALITY
        assert report["owner_review_ready"] is False
        assert report["gate2_ready"] is False
        assert report["handoff_ready"] is False
        assert axes["artifact_authority"]["state"] == vq.PASS
        assert axes["artboard_fitness"]["state"] == vq.FAIL
        assert axes["artboard_fitness"]["code"] == \
            vq.VQ_ARTBOARD_NOT_PRODUCT_DERIVED
        assert axes["artboard_fitness"]["measured"][
            "matched_page_standard"] == "A4"
        assert axes["front_artwork_resolution"]["state"] == vq.FAIL
        assert axes["front_artwork_resolution"]["code"] == \
            vq.VQ_FRONT_ARTWORK_UNRESOLVED_PLACEHOLDER
        for name in ("silhouette_fidelity", "closure_fidelity",
                     "logo_quality", "typography_quality",
                     "composition_quality"):
            assert axes[name]["state"] == vq.UNMEASURED, name

    def test_letter_artboard_fails_and_missing_artboard_is_unmeasured(self):
        letter = AI_A4.replace(b"595.2756 841.8898", b"612 792")
        _, axes = self._axes(self._quality_task(ai_bytes=letter))
        assert axes["artboard_fitness"]["state"] == vq.FAIL
        assert axes["artboard_fitness"]["measured"][
            "matched_page_standard"] == "LETTER"
        no_box = b"%PDF-1.4\n" + b"x" * 600
        _, axes = self._axes(self._quality_task(ai_bytes=no_box))
        assert axes["artboard_fitness"]["state"] == vq.UNMEASURED
        assert axes["artboard_fitness"]["code"] == vq.VQ_ARTBOARD_UNMEASURED

    def test_unrelated_oversize_artboard_fails_product_relation(self):
        huge = AI_A4.replace(b"595.2756 841.8898", b"2000 2000")
        _, axes = self._axes(self._quality_task(ai_bytes=huge))
        assert axes["artboard_fitness"]["state"] == vq.FAIL
        assert axes["artboard_fitness"]["code"] == \
            vq.VQ_ARTBOARD_UNRELATED_TO_PRODUCT

    def test_product_derived_artboard_passes(self):
        _, axes = self._axes(self._quality_task(ai_bytes=AI_PRODUCT))
        assert axes["artboard_fitness"]["state"] == vq.PASS

    def test_silhouette_divergence_fails_and_absence_is_unmeasured(self):
        # profile 95/35 => expected 2.714; recorded bounds aspect 1.44
        graph = {**TASK53_GRAPH,
                 "product_bounds": {"width_pt": 100, "height_pt": 144}}
        _, axes = self._axes(self._quality_task(graph=graph))
        assert axes["silhouette_fidelity"]["state"] == vq.FAIL
        assert axes["silhouette_fidelity"]["code"] == \
            vq.VQ_SILHOUETTE_DIVERGENT
        _, axes = self._axes(self._quality_task())
        assert axes["silhouette_fidelity"]["state"] == vq.UNMEASURED
        assert "missing_measurement" in axes["silhouette_fidelity"]

    def test_matching_silhouette_bounds_record_conformance_only(self):
        # VQR-1 owner correction: structural conformance PASS never claims
        # concept fidelity — the axis stays UNMEASURED (and blocking)
        # until VQR-2B compares against the selected concept
        graph = {**TASK53_GRAPH,
                 "product_bounds": {"width_pt": 100, "height_pt": 271}}
        report, axes = self._axes(self._quality_task(graph=graph))
        axis = axes["silhouette_fidelity"]
        assert axis["state"] == vq.UNMEASURED
        assert axis["measured"]["structural_silhouette_conformance"] == \
            vq.PASS
        assert report["structural_silhouette_conformance"] == vq.PASS
        assert report["selected_concept_silhouette_fidelity"] == \
            vq.UNMEASURED
        assert report["overall"] == vq.FAIL          # gate never weakened

    def test_closure_generic_block_and_mismatch_fail(self):
        # a generic cap block can never pass as the confirmed dropper
        graph = {**TASK53_GRAPH,
                 "closure_assembly": {"family": "cap", "components": []}}
        _, axes = self._axes(self._quality_task(graph=graph))
        assert axes["closure_fidelity"]["state"] == vq.FAIL
        assert axes["closure_fidelity"]["code"] == \
            vq.VQ_CLOSURE_FAMILY_MISMATCH
        # right family but missing required dropper structure
        graph = {**TASK53_GRAPH,
                 "closure_assembly": {"family": "dropper",
                                      "components": ["collar"]}}
        _, axes = self._axes(self._quality_task(graph=graph))
        assert axes["closure_fidelity"]["state"] == vq.FAIL
        # complete dropper assembly passes
        graph = {**TASK53_GRAPH,
                 "closure_assembly": {"family": "dropper",
                                      "components": ["collar", "bulb"]}}
        _, axes = self._axes(self._quality_task(graph=graph))
        assert axes["closure_fidelity"]["state"] == vq.PASS
        # no structural evidence at all -> UNMEASURED, blocking
        _, axes = self._axes(self._quality_task())
        assert axes["closure_fidelity"]["state"] == vq.UNMEASURED

    def test_placeholder_front_artwork_fails_and_content_passes(self):
        _, axes = self._axes(self._quality_task())
        assert axes["front_artwork_resolution"]["state"] == vq.FAIL
        graph = {**TASK53_GRAPH, "motif_groups": ["motif-front"]}
        _, axes = self._axes(self._quality_task(graph=graph))
        assert axes["front_artwork_resolution"]["state"] == vq.PASS
        _, axes = self._axes(self._quality_task(graph={}))
        assert axes["front_artwork_resolution"]["state"] == vq.UNMEASURED

    def test_logo_metrics_absent_unmeasured_defective_fails(self):
        _, axes = self._axes(self._quality_task())
        assert axes["logo_quality"]["state"] == vq.UNMEASURED
        extra = {"container_logo_metrics/1.0":
                 {"rendered_extent_pt": 4, "clipped": True}}
        _, axes = self._axes(self._quality_task(spec_extra=extra))
        assert axes["logo_quality"]["state"] == vq.FAIL
        extra = {"container_logo_metrics/1.0":
                 {"rendered_extent_pt": "garbage"}}
        _, axes = self._axes(self._quality_task(spec_extra=extra))
        assert axes["logo_quality"]["state"] == vq.UNMEASURED

    def test_text_run_count_alone_never_passes_typography(self):
        _, axes = self._axes(self._quality_task())
        assert axes["typography_quality"]["state"] == vq.UNMEASURED
        assert axes["typography_quality"]["measured"]["live_text_runs"] == 8
        # §W2: a bare small min_text_pt is no longer a finding — the gate does
        # not own the floor. The verdict the producer reached does fail.
        extra = {"container_typography_metrics/1.0":
                 {"min_text_pt": 3.0, "clipped": False}}
        _, axes = self._axes(self._quality_task(spec_extra=extra))
        assert axes["typography_quality"]["state"] == vq.UNMEASURED
        extra = {"container_typography_metrics/1.0":
                 {"min_text_pt": 3.0, "clipped": False,
                  "below_size_floor": True}}
        _, axes = self._axes(self._quality_task(spec_extra=extra))
        assert axes["typography_quality"]["state"] == vq.FAIL

    def test_composition_unresolved_is_unmeasured(self):
        _, axes = self._axes(self._quality_task())
        assert axes["composition_quality"]["state"] == vq.UNMEASURED
        extra = {"container_composition_metrics/1.0":
                 {"elements_outside_artboard": 0, "blocking_overlaps": 0,
                  "front_hierarchy_nonempty": True}}
        _, axes = self._axes(self._quality_task(spec_extra=extra))
        assert axes["composition_quality"]["state"] == vq.PASS

    def test_evaluation_is_deterministic_pure_and_offline(self):
        task = self._quality_task()
        out = task.packaging_outputs.first()
        spec_before = json.dumps(out.spec_sheet, sort_keys=True)
        with patch(_DELAY) as delay, \
                patch("apps.pipeline.services.claude_service."
                      "call_claude") as claude:
            first = vq.evaluate_container_visual_quality(task)
            second = vq.evaluate_container_visual_quality(task)
        assert json.dumps(first, sort_keys=True) == \
            json.dumps(second, sort_keys=True)
        out.refresh_from_db()
        assert json.dumps(out.spec_sheet, sort_keys=True) == spec_before
        delay.assert_not_called()
        claude.assert_not_called()

    def test_report_carries_no_paths_or_storage_keys(self):
        report = vq.evaluate_container_visual_quality(self._quality_task())
        dump = json.dumps(report)
        assert "/files/" not in dump and "/media/" not in dump
        assert "dielines/" not in dump and "/Users/" not in dump
        assert report["thresholds_version"] == vq.THRESHOLDS["version"]

    def test_incomplete_lifecycles_are_never_evaluated(self):
        for state in ("queued", "running", "failed", "dispatch_failed",
                      "inconsistent_no_ai"):
            assert vq.evaluate_container_visual_quality(
                self._task(state)) is None, state
        tampered = self._task("completed")
        out = tampered.packaging_outputs.first()
        out.design_preview_ai.name = "../../.env"
        out.save(update_fields=["design_preview_ai"])
        assert vq.evaluate_container_visual_quality(tampered) is None


class FidelityReportSemanticsTests(_StatusFixture):
    """§6 — the legacy report can no longer pass on absence of evidence."""

    def test_unmeasured_axes_block_instead_of_passing(self):
        axes = {"a": {"state": cf.MEASURED_PASS, "code": "", "detail": "",
                      "required": True},
                "b": {"state": cf.UNMEASURED, "code": "", "detail": "",
                      "required": True}}
        counts = {"measured_pass": 1, "measured_fail": 0, "unmeasured": 1}
        # exercise the real combination through measure_fidelity's shape by
        # replaying the rejected report: 1 pass + 7 unmeasured

        class _Doc:
            metadata = {}

            def walk(self):
                return iter(())

        report = cf.measure_fidelity(_Doc(), {"fields": {}}, name_lines=[])
        assert report["counts"]["unmeasured"] >= 7
        assert report["overall"] == cf.UNMEASURED_BLOCKING
        assert report["overall"] != cf.MEASURED_PASS
        assert report["blocking_unmeasured"]
        for axis in report["axes"].values():
            assert axis["required"] is True
        assert counts and axes  # silence linters: shapes documented above

    def test_measured_fail_still_wins(self):
        class _Doc:
            metadata = {}

            def walk(self):
                return iter(())

        report = cf.measure_fidelity(_Doc(), {"fields": {}},
                                     name_lines=["Rosé"])
        assert report["axes"]["product_name_presence"]["state"] == \
            cf.MEASURED_FAIL
        assert report["overall"] == cf.MEASURED_FAIL


class ReadinessIntegrationTests(_StatusFixture):
    """§7/§10/§19/§20 — precedence, enforcement, no side effects."""

    def _approve(self, task):
        out = task.packaging_outputs.first()
        return self.client.post(
            f"/api/tasks/{task.id}/gate2_approve/",
            {"packaging_output_id": out.id}, content_type="application/json")

    def _handoff(self, task):
        return self.client.post(
            f"/api/tasks/{task.id}/generate_handoff/", {},
            content_type="application/json")

    def _measured_fail(self, task):
        # [§BH71 (0a): the fixture alone measures nothing — a warning beside Approve now, not a failure — so a
        # quality FAILURE is the task-53 shape's measured one: its A4 artboard]
        out = task.packaging_outputs.first()
        out.design_preview_ai.delete(save=True)
        out.design_preview_ai.save(f"container_task_{task.id}.ai", ContentFile(AI_A4), save=True)
        spec = dict(out.spec_sheet)
        spec["container_profile"] = PROFILE
        out.spec_sheet = spec
        out.save(update_fields=["spec_sheet"])
        return task

    def test_quality_failed_is_never_what_refuses_gate2_and_still_holds_the_handoff(self):
        """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design"] a measured
        visual-quality failure no longer refuses Gate 2 — it is kept beside Approve in words; what refuses this design's
        approval is only his own acceptance, not given. The printer's package still waits on the quality check."""
        from apps.pipeline.gate2_problems import REFUSING
        task = self._measured_fail(self._task("completed"))      # [§BH71 (0a): a MEASURED failure — see above]
        out = task.packaging_outputs.first()
        spec_before = json.dumps(out.spec_sheet, sort_keys=True)
        decisions = GateDecision.objects.count()
        with patch(_DELAY) as delay:
            a = self._approve(task)
            h = self._handoff(task)
        assert a.status_code == 409
        assert a.json()["error"] != "GATE_2_NOT_READY"
        assert {str(c).split(":")[0] for c in a.json()["failures"]} <= set(REFUSING), a.json()
        body = self.client.get(f"/api/tasks/{task.id}/status/").json()
        assert body["gate2_problems"]["kept"] and all(k["words"] and "_" not in k["words"]
                                                      for k in body["gate2_problems"]["kept"])
        out.refresh_from_db()
        spec_before = json.dumps(out.spec_sheet, sort_keys=True)  # the verdict is persisted at the approval, as ever
        assert h.status_code == 409
        assert h.json()["reason_code"] == "VISUAL_QUALITY_GATE_FAILED"
        assert GateDecision.objects.count() == decisions
        out.refresh_from_db()
        assert json.dumps(out.spec_sheet, sort_keys=True) == spec_before
        task.refresh_from_db()
        assert task.status == "awaiting_gate_2"
        delay.assert_not_called()

    def test_technical_intervention_takes_precedence_over_quality(self):
        task = self._task("completed")
        out = task.packaging_outputs.first()
        out.design_preview_ai.name = "../../.env"
        out.save(update_fields=["design_preview_ai"])
        readiness = build_container_gate2_readiness(task)
        assert readiness["reason_code"] == "TECHNICAL_INTERVENTION_REQUIRED"
        assert readiness["visual_quality"] is None
        assert readiness["inspection_only"] is False

    def test_worker_failure_is_never_a_visual_result(self):
        readiness = build_container_gate2_readiness(self._task("failed"))
        assert readiness["reason_code"] == "FAILED"
        assert readiness["visual_quality"] is None

    def test_status_payload_carries_gate_and_quality_coherently(self):
        task = self._task("completed")
        body = self.client.get(f"/api/tasks/{task.id}/status/").json()
        gate = body["container_visual_quality_gate"]
        readiness = body["container_gate2_readiness"]
        assert gate["schema"] == vq.VQ_GATE_SCHEMA
        # [§BH71 (0a), the owner's goal of 2026-09-28: "Unmeasured checks … show as a warning beside Approve, never a block." This
        # fixture measures nothing: it read overall FAIL, VISUAL_QUALITY_GATE_FAILED, inspection only — the overall
        # reads UNMEASURED, never PASS, Gate 2 is ready, and every unmeasured axis is said in words beside Approve]
        assert gate["overall"] == "UNMEASURED"
        assert set(gate["required_axes"]) == set(vq.REQUIRED_AXES)
        assert readiness["ready"] is True and readiness["reason_code"] is None
        assert readiness["visual_quality"]["overall"] == "UNMEASURED"
        assert readiness["visual_quality"]["acceptance_warnings"] == [
            w["code"] for w in gate["acceptance_warnings"]]
        assert readiness["inspection_only"] is False
        rows = body["acceptance_warnings"]
        assert len(rows) == len(gate["acceptance_warnings"]) > 0
        assert all(r["words"].endswith("— not measured yet") for r in rows)
        assert "whether the outline matches the concept — not measured yet" in [r["words"] for r in rows]
        # a MEASURED failure still reads failed and inspection only (the task-53 shape)
        failed = self._measured_fail(self._task("completed"))
        fbody = self.client.get(f"/api/tasks/{failed.id}/status/").json()
        assert fbody["container_visual_quality_gate"]["overall"] == "FAIL"
        assert fbody["container_gate2_readiness"]["reason_code"] == "VISUAL_QUALITY_GATE_FAILED"
        assert fbody["container_gate2_readiness"]["inspection_only"] is True
        # §8: authorized artifact access is retained for inspection
        out = body["packaging_output"]
        assert out["design_preview_ai_url"] == \
            f"/api/tasks/{task.id}/reconstruction-artifact/ai/?download=1"
        # non-container tasks say nothing about visual quality
        pkg = self._task("queued", target="packaging")
        pkg_body = self.client.get(f"/api/tasks/{pkg.id}/status/").json()
        assert pkg_body["container_visual_quality_gate"] is None
        assert pkg_body["container_gate2_readiness"] is None

    def test_unmeasured_quality_leaves_gate_2_to_what_it_always_asked_and_is_kept_with_its_verdict(self):
        """§BH71 (0a), the owner's goal of 2026-09-28: "My approval overrides §BH50(f)(5). Unmeasured checks …
        show as a warning beside Approve, never a block." A drawing that measures nothing is past the
        visual-quality check; Gate 2 then asks what it always asked — here his acceptance, first of all — and
        the unmeasured axes are kept with the verdict it saves: the check is recalculated on every read and
        saved nowhere else. Nothing is decided, resumed or moved."""
        task = self._task("completed")
        out = task.packaging_outputs.first()
        spec = dict(out.spec_sheet)
        spec["container_reconstruction"] = {"status": "RECONSTRUCTED", "blockers": []}
        out.spec_sheet = spec
        out.save(update_fields=["spec_sheet"])
        quality = vq.evaluate_container_visual_quality(task)
        decisions = GateDecision.objects.count()
        with patch(_DELAY) as delay:
            a = self._approve(task)
        assert a.status_code == 409
        body = a.json()
        assert body["error"] != "GATE_2_NOT_READY"
        assert "HUMAN_VISUAL_ACCEPTANCE_REQUIRED" in body["failures"]
        assert any(c.startswith("CONTAINER_FRONT_COPY_FIT_UNMEASURED") for c in body["acceptance_warnings"])
        assert not any(c.startswith("CONTAINER_FRONT_COPY_FIT_UNMEASURED") for c in body["failures"])
        out.refresh_from_db()
        saved = out.spec_sheet["container_production_readiness/1.0"]
        assert saved["visual_quality_warnings"] == [w["code"] for w in quality["acceptance_warnings"]]
        assert saved["acceptance_warnings"] == body["acceptance_warnings"]
        assert GateDecision.objects.count() == decisions
        task.refresh_from_db()
        assert task.status == "awaiting_gate_2"
        delay.assert_not_called()

    def test_quality_pass_restores_readiness(self):
        task = self._task("completed")
        with patch("apps.pipeline.services.visual_quality_gate."
                   "evaluate_container_visual_quality",
                   return_value={"overall": "PASS",
                                 "status": "VISUAL_QUALITY_PASSED",
                                 "blocking_findings": []}):
            readiness = build_container_gate2_readiness(task)
        assert readiness["ready"] is True
        assert readiness["handoff_ready"] is True
        assert readiness["inspection_only"] is False


def test_w6_a_type_only_front_is_resolved_and_only_real_placeholder_text_is_refused():
    """[His answer of 2026-10-05, W6: "type-only is a real design style; refuse only real placeholder text".] A front with
    no motif and no picture that prints its own words is type-only and passes; the same front with a placeholder's
    words is refused by name; a front with no type either is still a zone-only fill; and a graph written before the
    census counted the front's type is read exactly as before."""
    base = {"motif_groups": [], "decorative_raster_count": 0, "zones_consumed": ["z_lid"]}
    typed = vq._front_artwork_axis(dict(base, front_type={"runs": 1, "lettering": 0, "placeholder_runs": []}))
    assert (typed["state"], typed["measured"]["front_style"]) == (vq.PASS, "type-only"), typed
    traced = vq._front_artwork_axis(dict(base, front_type={"runs": 0, "lettering": 1, "placeholder_runs": []}))
    assert traced["state"] == vq.PASS, traced
    held = vq._front_artwork_axis(dict(base, front_type={"runs": 1, "lettering": 0, "placeholder_runs": [
        {"node_name": "product-name", "text": "Lorem ipsum", "marker": "lorem ipsum"}]}))
    assert (held["state"], held["code"]) == (vq.FAIL, vq.VQ_FRONT_ARTWORK_UNRESOLVED_PLACEHOLDER), held
    assert "Lorem ipsum" in held["reason"]
    empty = vq._front_artwork_axis(dict(base, front_type={"runs": 0, "lettering": 0, "placeholder_runs": []}))
    assert (empty["state"], empty["code"]) == (vq.FAIL, vq.VQ_FRONT_ARTWORK_UNRESOLVED_PLACEHOLDER), empty
    before = vq._front_artwork_axis(dict(base))
    assert (before["state"], before["code"]) == (vq.FAIL, vq.VQ_FRONT_ARTWORK_UNRESOLVED_PLACEHOLDER), before


def test_w6_the_census_counts_the_fronts_own_type_and_reads_it_for_placeholders():
    """[His answer W6] The design graph's census counts the type a front prints where it prints it — never the sheet's
    own words — and names a run carrying a placeholder's words."""
    from apps.ire.compose_container import _front_type_census
    from apps.ire.graph import Color, Document, Group, TextRun
    ink = Color.from_hex("#2A2426")
    doc = Document(page_w=100, page_h=100, root=Group(name="Artwork", role="artwork", children=[
        Group(name="Container", role="product", children=[
            TextRun(name="product-name", text="Rose Velvet", x=10, y=10, size_pt=12, color=ink)]),
        TextRun(name="sheet-title", text="Rose Velvet — the container", x=10, y=90, size_pt=6, color=ink)]))
    assert _front_type_census(doc)["front_type"] == {"runs": 1, "lettering": 0, "placeholder_runs": []}
    doc.root.children[0].children.append(TextRun(name="front-descriptor", text="Sample text", x=10, y=20, size_pt=8,
                                            color=ink))
    got = _front_type_census(doc)["front_type"]
    assert got["runs"] == 2 and [p["node_name"] for p in got["placeholder_runs"]] == ["front-descriptor"], got
