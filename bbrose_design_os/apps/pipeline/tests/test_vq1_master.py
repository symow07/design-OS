"""VQ-1-MASTER — reference-contour-driven fit and the honest hard stop."""
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq1_master as vm

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")
STOP = json.load(open(os.path.join(M, "vq1_master_hard_stop.json")))
M3 = json.load(open(os.path.join(M, "master_it3_metrics.json")))
CROPS = json.load(open(os.path.join(M, "reference_crops.json")))


class TestReferenceDrivesTheGeometry:
    def test_crops_meet_the_resolution_minimums(self):
        c = CROPS["crops"]
        assert c["complete_closure"]["output_size"][1] >= 900
        assert c["dark_closure"]["output_size"][1] >= 500
        assert c["collar"]["output_size"][1] >= 300
        assert c["collar_neck_junction"]["output_size"][1] >= 300
        assert c["complete_assembly"]["output_size"][1] >= 900
        assert c["shoulder_neck"]["output_size"][0] >= 500

    def test_measurement_happens_in_source_pixel_space(self):
        fit = json.load(open(os.path.join(M, "master_fit_m3.json")))
        assert fit["measurement_space"] == "SOURCE_IMAGE_PIXELS"
        assert "never on the upscaled copy" in CROPS["scaling_method"]

    def test_reference_comparison_is_the_fidelity_authority(self):
        fit = json.load(open(os.path.join(M, "master_fit_m3.json")))
        assert fit["fidelity_authority"] == \
            "REFERENCE_COMPARISON_NOT_PARAMETER_MODEL"
        assert fit["is_physical_dimension"] is False

    def test_contours_are_fitted_with_measured_residuals(self):
        fit = json.load(open(os.path.join(M, "master_fit_m3.json")))
        for name, f in fit["fits"].items():
            assert f["segment_count"] > 0, name
            assert f["sample_count"] > f["segment_count"], name
            assert f["residual_max"] < 6.0, name
            assert f["samples_px"], name

    def test_occlusion_recorded_and_symmetry_is_concept_only(self):
        o = CROPS["occlusion_map"]
        assert o["code"] == "LEFT_CONTOUR_PARTIALLY_OCCLUDED"
        assert o["primary_contour_authority"] == "VISIBLE_RIGHT_CONTOUR"
        assert o["physical_symmetry_claimed"] is False
        assert o["false_left_contour_from_carton_extracted"] is False


class TestVisibleObjectContract:
    def test_exactly_four_visible_objects(self):
        assert len(vm.VISIBLE_OBJECTS) == 4
        assert vm.GATES["visible_object_count"] == 4
        assert M3["gates"]["visible_object_count"] is True

    def test_no_forbidden_visible_object_is_drawn(self):
        assert set(vm.DRAW_ORDER) == {"GLASS", "COLLAR", "DARK_CLOSURE"}
        for bad in ("spacer", "washer", "adapter", "thread", "tier",
                    "ledge"):
            assert bad not in " ".join(vm.DRAW_ORDER).lower()
        assert len(vm.FORBIDDEN_VISIBLE) >= 11

    def test_hidden_mechanism_is_never_rendered(self):
        assert vm.INTERNAL_MECHANISM == "UNRESOLVED / HIDDEN"
        for n in vm.NONPRINTING_TECHNICAL_INTERNALS:
            assert n not in vm.DRAW_ORDER

    def test_no_gap_can_open_between_components(self):
        """M1 left a gap and the silhouette dipped. M4 replaced the
        dark/collar overlap with an exact shared contact row, so that
        interface must MEET; the collar/glass interface still overlaps."""
        d, c, g = (vm.BANDS["DARK_CLOSURE"], vm.BANDS["COLLAR"],
                   vm.BANDS["GLASS"])
        assert d[1] == c[0] == vm.CONTACT_ROW_PX, "one shared contact row"
        assert c[1] > g[0], "collar must overlap the glass"


class TestDeterministicResults:
    def test_collar_gates_all_pass(self):
        for k in ("collar_iou", "collar_mean", "collar_p95", "collar_max"):
            assert M3["gates"][k] is True, k
        r = M3["regions"]["collar"]
        assert r["iou"] >= 0.97 and r["mean"] <= 0.010

    def test_shoulder_and_body_follow_the_reference(self):
        assert M3["gates"]["shoulder_iou"] is True
        assert M3["regions"]["shoulder"]["iou"] >= 0.95
        assert M3["regions"]["body"]["iou"] >= 0.99

    def test_junction_gate_still_fails_and_is_reported(self):
        assert M3["gates"]["junction_max"] is False
        assert M3["gates_pass"] is False
        b = STOP["unresolved_blockers"][0]
        assert b["code"] == "VQ_DARK_CLOSURE_LOWER_INTERFACE_FAILED"
        assert b["passes"] is False
        assert b["value"] > b["gate"]


class TestHonestHardStop:
    def test_hard_stop_is_declared_not_success(self):
        assert STOP["status"] == "VQ1_MASTER_HARD_STOP_REVIEW_REQUIRED"
        assert STOP["vq1_state"] == "REVISION_REQUIRED"
        assert STOP["final_status_never"] == "HUMAN_ACCEPTED"

    def test_no_scorecard_is_claimed_without_dual_inspection(self):
        assert STOP["scorecard_reported"].startswith("NOT_SCORED")
        assert "self-certification" in STOP["scorecard_reported"]
        assert STOP["multimodal_calls_this_slice"] == 0
        assert any("NOT RUN" in x for x in STOP["what_was_NOT_completed"])

    def test_incomplete_work_is_enumerated(self):
        assert len(STOP["what_was_NOT_completed"]) >= 5
        joined = " ".join(STOP["what_was_NOT_completed"])
        for missing in ("two independent multimodal inspections",
                        "twenty-panel review package", "six-iteration"):
            assert missing in joined

    def test_iterations_preserved(self):
        for n in (1, 2, 3):
            assert os.path.exists(os.path.join(M, f"master_it{n}.png")) or \
                os.path.exists(os.path.join(M, f"master_fit_m{n}.json"))

    def test_prior_fixtures_preserved_and_rejected(self):
        assert "preserved" in STOP["prior_fixtures"]
        for p in ("vq1_corr5/vq1_corr5_fixture.json",
                  "vq1_reset2/iteration_6.png",
                  "vq1/vq1_human_structural_review.json"):
            assert os.path.exists(os.path.join(DOCS, p)), p

    def test_production_and_supplier_state_unchanged(self):
        assert STOP["production_geometry"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert STOP["supplier_requests_sent"] is False
        out = json.load(open(os.path.join(
            DOCS, "vq1_reset2", "vq1_supplier_specification_outreach.json")))
        for s in out["suppliers"]:
            assert s["sent"] is False

    def test_no_image_generation_and_no_it7(self):
        assert STOP["image_generation_calls"] == 0
        assert STOP["it7_generated"] is False
        src = open(vm.__file__).read().lower()
        for banned in ("images.generate", "dall-e", "generate_image"):
            assert banned not in src

    @pytest.mark.django_db
    def test_live_pilot_records_untouched(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for tid, status in ((52, "container_stage_visually_rejected"),
                            (51, "awaiting_gate_2")):
            t = DesignTask.objects.filter(id=tid).first()
            assert t is None or t.status == status
        p = DesignProject.objects.filter(id=7).first()
        assert p is None or p.status == "container_rejected"


class TestContinuation1HardStop:
    """M4 contact-manifold attempt and its honest regression stop."""

    STOP = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_master_cont1_hard_stop.json")))
    M4 = json.load(open(os.path.join(
        DOCS, "vq1_master", "master_it4_metrics.json")))

    def test_protected_geometry_stayed_byte_identical(self):
        for k, v in self.M4["protected_geometry"].items():
            assert v is True, k
        assert self.STOP["protected_geometry_verified_byte_identical"]

    def test_only_the_contact_manifold_changed(self):
        m3 = json.load(open(os.path.join(
            DOCS, "vq1_master", "master_fit_m3.json")))
        m4 = json.load(open(os.path.join(
            DOCS, "vq1_master", "master_fit_m4.json")))
        assert m3["fits"]["GLASS"]["samples_px"] == \
            m4["fits"]["GLASS"]["samples_px"]
        assert [s for s in m3["fits"]["DARK_CLOSURE"]["samples_px"]
                if s[1] <= 488] == \
            [s for s in m4["fits"]["DARK_CLOSURE"]["samples_px"]
             if s[1] <= 488]

    def test_m4_regressed_and_the_record_says_so(self):
        assert self.M4["gates"]["junction_max"] is False
        assert self.M4["gates_pass"] is False
        p = self.STOP["metric_progression_junction_max"]
        assert p["M4"] > p["M3"], "M4 is worse; that is the stop reason"
        assert self.STOP["hard_stop_condition"].startswith(
            "candidate became worse than M3")
        assert self.STOP["best_candidate_remains"] == "M3"

    def test_global_regions_did_not_regress(self):
        for k in ("collar", "body", "shoulder", "dark_closure"):
            assert self.M4["gates"][f"nonregress_{k}"] is True, k

    def test_no_scorecard_or_release_is_claimed(self):
        assert self.STOP["scorecard_reported"] == "NOT_SCORED"
        assert self.STOP["release_status"].startswith("NOT ")
        assert self.STOP["multimodal_calls_this_slice"] == 0
        assert self.STOP["final_status_never"] == "HUMAN_ACCEPTED"

    def test_incomplete_work_enumerated(self):
        joined = " ".join(self.STOP["what_was_NOT_done"])
        for missing in ("two independent visual inspections",
                        "dual 10/10 scorecards", "22-section",
                        "technical-reference web pass"):
            assert missing in joined

    def test_no_m5_m6_m7_created(self):
        assert self.STOP["m7_generated"] is False
        for n in (5, 6, 7):
            assert not os.path.exists(os.path.join(
                DOCS, "vq1_master", f"master_it{n}.png"))

    def test_root_cause_and_next_model_recorded(self):
        assert "ramp" in self.STOP["root_cause_found"]
        assert self.STOP["unresolved_local_rows"]["source_rows"] == \
            "y=495..508"
        assert len(self.STOP["unresolved_local_rows"][
            "reference_half_widths"]) >= 10
        assert "needs authorization" in self.STOP["suggested_next_model"]

    def test_boundaries_held(self):
        assert self.STOP["image_generation_calls"] == 0
        assert self.STOP["supplier_requests_sent"] is False
        assert self.STOP["production_geometry"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"


class TestModel2RimHardStop:
    """Three-surface rim model (RIM1) and its regression stop."""

    STOP = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_master_model2_hard_stop.json")))
    R1 = json.load(open(os.path.join(
        DOCS, "vq1_master", "rim1_metrics.json")))

    def test_rim_is_a_collar_surface_not_a_fifth_object(self):
        fit = json.load(open(os.path.join(
            DOCS, "vq1_master", "rim_fit_rim1.json")))
        assert fit["rim_is_fifth_mechanical_object"] is False
        assert fit["visible_mechanical_object_count"] == 4
        assert fit["rim_surface_owner"] == "SINGLE_METAL_COLLAR_ASSEMBLY"
        assert "COLLAR_TOP_RIM_TRANSITION_SURFACE" in \
            fit["collar_assembly_surfaces"]
        assert self.STOP["rim_was_not_a_fifth_object"] is True

    def test_two_exact_seams_no_overlap_no_gap(self):
        assert vm.RIM_BANDS["DARK_CLOSURE"][1] == vm.SEAM_A_PX
        assert vm.RIM_BANDS["COLLAR_TOP_RIM"][0] == vm.SEAM_A_PX
        assert vm.RIM_BANDS["COLLAR_TOP_RIM"][1] == vm.SEAM_B_PX
        assert vm.RIM_BANDS["COLLAR"][0] == vm.SEAM_B_PX
        assert vm.SEAM_B_PX > vm.SEAM_A_PX

    def test_rim_patch_fitted_to_actual_source_rows(self):
        p = self.STOP["rim_patch_fit"]
        assert p["sample_count"] >= 13
        assert p["residual_max"] <= 2.0
        assert p["segment_count"] >= 1

    def test_protected_geometry_identical_by_value(self):
        for k, v in self.STOP["protected_geometry_verified"].items():
            assert v["values_identical"] is True, k
        assert "sampling-phase shift" in \
            self.STOP["protected_check_correction"]

    def test_global_non_regression_held(self):
        for k, v in self.STOP["global_non_regression"].items():
            assert v is True, k

    def test_rim1_regressed_and_stopped(self):
        assert all(v is False for v in self.STOP["local_gates"].values())
        p = self.STOP["metric_progression_junction_max"]
        assert p["RIM1"] > p["M3"]
        assert self.STOP["hard_stop_condition"].startswith(
            "RIM1 is worse than M3")
        assert self.STOP["rim2_rim3_authorized"] is False
        assert self.STOP["best_candidate_remains"] == "M3"

    def test_identical_residual_across_models_is_recorded(self):
        p = self.STOP["metric_progression_junction_max"]
        assert abs(p["RIM1"] - p["M4"]) < 1e-9,             "the identical value across two different models IS the finding"
        assert "IDENTICAL junction maximum" in self.STOP["key_observation"]
        assert "not the junction partition" in \
            self.STOP["key_observation"].lower()

    def test_no_scorecard_no_release_no_rim4(self):
        assert self.STOP["scorecard_reported"] == "NOT_SCORED"
        assert self.STOP["release_status"].startswith("NOT ")
        assert self.STOP["rim4_generated"] is False
        assert self.STOP["multimodal_calls_this_slice"] == 0
        for n in (2, 3, 4):
            assert not os.path.exists(os.path.join(
                DOCS, "vq1_master", f"rim{n}.png"))

    def test_boundaries_held(self):
        assert self.STOP["image_generation_calls"] == 0
        assert self.STOP["supplier_requests_sent"] is False
        assert self.STOP["manufacturable"] is False
        assert self.STOP["concept_visual_geometry_only"] is True


class TestJunctionResidualForensics:
    """DIAG-1 — evidence-backed root cause, no geometry generated."""

    F = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_junction_residual_forensics.json")))

    def test_no_candidate_was_generated(self):
        assert self.F["geometry_generated"] is False
        assert self.F["new_candidate_generated"] is False
        assert self.F["candidates_read_only"] == ["M3", "M4", "RIM1"]
        for n in ("rim2", "rim3", "master_it5"):
            assert not os.path.exists(os.path.join(
                DOCS, "vq1_master", f"{n}.png"))

    def test_exact_maximum_rows_persisted(self):
        m = self.F["maximum_rows"]
        assert m["M3"]["source_row"] in (494, 495)
        assert m["M4"]["source_row"] in (490, 491)
        assert m["RIM1"]["source_row"] == m["M4"]["source_row"]
        for v in m.values():
            assert "ref_half_width_norm" in v
            assert "cand_half_width_norm" in v
            assert "signed_deviation" in v

    def test_row_by_row_evidence_exists(self):
        t = self.F["row_table_488_516"]
        assert len(t) >= 25
        for r in t:
            for k in ("source_row", "ref", "M3", "M4", "RIM1",
                      "d_M3", "d_M4", "d_RIM1"):
                assert k in r, k

    def test_m4_and_rim1_share_the_terminal_collapse(self):
        c = [x for x in self.F["causes"] if x["candidate"] == "M4/RIM1"][0]
        assert c["sub_type"] == "CLOSED_CONTOUR_TERMINAL_END_EFFECT"
        assert "too NARROW" in c["evidence"]
        assert "identical to five decimals" in c["why_m4_and_rim1_converge"]

    def test_y_offset_analysis_is_deterministic_and_not_adopted(self):
        c = [x for x in self.F["causes"]
             if x["classification"] == "LOCAL_Y_ALIGNMENT_ERROR"][0]
        s = c["offset_sweep_m3"]
        assert set(s) == {"-2", "-1", "-0.5", "0", "+0.5", "+1", "+2"}
        assert s["-2"] < 0.045 < s["0"], "the offset dissolves M3's maximum"
        assert c["offset_sweep_rim1"]["-2"] > 0.12, "but not RIM1's"
        # the sweep is read-only: production metrics still use offset 0
        assert self.F["correspondence_audit"][
            "production_metric_changed"] is False

    def test_correspondence_method_is_audited_not_swapped(self):
        a = self.F["correspondence_audit"]
        assert a["method_in_use"] == "NEAREST_NORMALIZED_ROW"
        assert a["code"] == "VQ_SAME_ROW_METRIC_INVALID_AT_STEEP_TRANSITION"
        assert a["production_metric_changed"] is False

    def test_no_row_excluded_and_no_threshold_lowered(self):
        assert self.F["rows_excluded_from_metrics"] == 0
        assert self.F["threshold_lowered"] is False

    def test_reference_contour_judged_valid_with_reason(self):
        assert self.F["reference_contour_valid"] is True
        assert "no spike or discontinuity" in \
            self.F["reference_contour_note"]

    def test_no_further_geometry_model_is_justified(self):
        assert self.F["is_another_geometry_model_justified"] is False
        assert "not about partition" in self.F["reason"]

    def test_next_actions_are_ordered_and_not_combined(self):
        n = self.F["next_action_contract"]
        assert [x["order"] for x in n] == [1, 2]
        assert n[0]["geometry_change"] is False
        assert n[1]["geometry_change"] == "FITTER_ONLY"
        assert self.F["speculative_fixes_combined"] is False

    def test_boundaries_held(self):
        assert self.F["image_generation_calls"] == 0
        assert self.F["multimodal_calls"] == 0
        assert self.F["supplier_requests_sent"] is False


class TestMetricCorrectionV2:
    """CONT-2 — anchor alignment, corrected correspondence, no geometry."""

    V2 = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_contour_metric_v2.json")))
    STOP = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_master_cont2_stop.json")))

    def test_candidates_byte_identical(self):
        import hashlib
        for f, h in self.V2["candidate_hashes_unchanged"].items():
            p = os.path.join(DOCS, "vq1_master", f)
            assert hashlib.sha256(
                open(p, "rb").read()).hexdigest()[:12] == h, f
        assert self.V2["geometry_generated"] is False
        for n in self.V2["candidates"].values():
            assert n["geometry_changed"] is False

    def test_alignment_comes_from_independent_anchors(self):
        a = self.V2["alignment"]
        assert a["derived_from"] == ["apex", "base"]
        assert a["validation_anchor"] == "body_wall"
        assert a["optimized_on_failing_row"] is False
        assert a["cherry_picked_offset"] is False
        assert a["identical_procedure_for_all_candidates"] is True

    def test_the_same_transform_applies_to_every_candidate(self):
        per = self.V2["alignment"]["per_candidate"]
        scales = {v["scale"] for v in per.values()}
        assert len(scales) == 1, "one transform, not per-candidate tuning"
        for v in per.values():
            assert abs(v["anchor_residual_px"]["body_wall"]) < 1.0

    def test_candidate_specific_offset_optimization_is_rejected(self):
        for v in self.V2["alignment"]["per_candidate"].values():
            assert v["optimized_on_failing_row"] is False
        assert "was not used as an input" in \
            self.V2["alignment"]["independence_evidence"]

    def test_same_row_stays_diagnostic_at_steep_transitions(self):
        c = self.V2["correspondence"]
        assert c["canonical_method"] == "LOCAL_NORMAL_DIRECTION"
        assert "SAME_ROW" in c["retained_as_diagnostic"]
        for n in self.V2["candidates"].values():
            assert "same_row_diagnostic" in n

    def test_metric_discriminates_rather_than_passing_everything(self):
        c = self.V2["candidates"]
        assert c["M3"]["junction_gates_pass"] is True
        assert c["M4"]["junction_gates_pass"] is False
        assert c["RIM1"]["junction_gates_pass"] is False
        assert c["M4"]["local_normal"]["p95"] > 0.025
        assert self.V2["correspondence"][
            "not_selected_because_lowest_for_m3"] is True

    def test_historical_metrics_remain_immutable(self):
        assert self.V2["version"] == "2.0"
        assert self.V2["historical_metrics_immutable_under"] == "version 1.0"
        old = json.load(open(os.path.join(
            DOCS, "vq1_master", "master_it3_metrics.json")))
        assert old["regions"]["junction"]["max"] == 0.06539, \
            "the v1 result must not be rewritten"

    def test_m3_passes_only_through_the_canonical_contract(self):
        assert self.V2["m3_global_gates_pass"] is True
        assert self.V2["m3_classification"] == \
            "DETERMINISTIC_GATES_PASSED_PENDING_VISUAL_INSPECTION"
        ln = self.V2["candidates"]["M3"]["local_normal"]
        assert ln["mean"] <= 0.008 and ln["p95"] <= 0.025
        assert ln["max"] <= 0.045

    def test_terminal_repair_not_executed_when_m3_passes(self):
        assert self.V2["terminal_fitter_repair_executed"] is False
        assert self.V2["m5_m6_created"] is False
        assert "§12 forbids it" in self.V2["terminal_repair_reason"]
        for n in ("master_it5", "master_it6"):
            assert not os.path.exists(os.path.join(
                DOCS, "vq1_master", f"{n}.png"))

    def test_no_release_without_dual_inspection(self):
        assert self.STOP["status"] == "VQ1_MASTER_HARD_STOP_REVIEW_REQUIRED"
        assert self.STOP["release_status"].startswith("NOT ")
        assert self.STOP["scorecard_reported"] == "NOT_SCORED"
        assert self.V2["multimodal_calls"] == 0
        joined = " ".join(self.STOP["what_was_NOT_completed"])
        assert "two independent visual inspections" in joined

    def test_boundaries_held(self):
        assert self.V2["image_generation_calls"] == 0
        assert self.V2["supplier_requests_sent"] is False
        assert self.V2["production_geometry"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"


class TestVis1RasterGateStop:
    """VIS-1 — the raster gate blocked the inspections, and the first
    sweep's false PASS is recorded rather than quietly dropped."""

    S = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_master_vis1_stop.json")))
    R = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_raster_stability_report_invalid.json")))

    def test_m3_geometry_untouched(self):
        import hashlib
        p = os.path.join(DOCS, "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(p, "rb").read()).hexdigest()[:12] == "4ecc8e9df1d1"
        assert self.S["m3_geometry_changed"] is False
        assert self.S["new_candidate_generated"] is False

    def test_false_pass_is_recorded_not_hidden(self):
        assert self.R["first_attempt_invalid"] is True
        assert "BYTE-IDENTICAL" in self.R["first_attempt_defect"]
        assert self.R["finding"] == "VQ_RASTER_SWEEP_RESOLUTION_NOT_APPLIED"
        assert "withdrawn" in self.S["self_reported_defect"]

    def test_raster_sweep_did_not_actually_vary_resolution(self):
        assert self.R["distinct_resolutions_rendered"] is False
        assert self.R["rasterizer_honouring_dpi_available"] is False
        assert self.R["gates_pass"] is False

    def test_failed_raster_gate_blocked_the_inspections(self):
        assert self.S["inspections_run"] == 0
        assert self.S["multimodal_calls"] == 0
        assert "§5 forbids" in self.S["consequence"]
        assert self.S["scorecard_reported"] == "NOT_SCORED"

    def test_release_is_prohibited(self):
        assert self.S["status"] == "VQ1_MASTER_HARD_STOP_REVIEW_REQUIRED"
        assert self.S["release_status"].startswith("NOT ")
        assert "mandatory for release" in self.S["why_release_prohibited"]

    def test_correction_proposed_but_not_implemented(self):
        p = self.S["proposed_unimplemented_action"]
        assert p["component"] == "tooling, not geometry"
        assert "Not implemented here" in p["proposed_next_action"]
        assert p["protected_geometry"] == "M3 untouched"

    def test_deterministic_status_unchanged(self):
        assert self.S["m3_deterministic_status"].startswith(
            "DETERMINISTIC_GATES_PASSED_PENDING_VISUAL_INSPECTION")

    def test_boundaries_held(self):
        assert self.S["image_generation_calls"] == 0
        assert self.S["supplier_requests_sent"] is False
        assert self.S["production_geometry"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"


class TestToolingFixAndDualInspection:
    """TOOLING-FIX-1 — DPI-capable rasterizer, valid sweep, two inspections."""

    CAP = json.load(open(os.path.join(
        DOCS, "vq1_master", "pdf_rasterizer_capability.json")))
    RS = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_raster_stability_report_v2.json")))
    DI = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_dual_inspection.json")))
    CO = json.load(open(os.path.join(
        DOCS, "vq1_master", "visual_scorecard_consistency.json")))
    ST = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_tooling_fix1_stop.json")))

    def test_sips_is_not_treated_as_dpi_capable(self):
        from apps.ire import pdf_raster as pr
        sips = [b for b in pr.probe_backends() if b["backend"] == "sips"][0]
        assert sips["explicit_dpi_claimed"] is False
        assert "silently renders at its own default" in \
            sips["rejection_reason"]

    def test_backend_certified_only_by_capability_test(self):
        assert self.CAP["dpi_capable"] is True
        assert self.CAP["distinct_dimensions_per_dpi"] is True
        assert self.CAP["all_dimensions_match_prediction"] is True
        assert "identical hashes alone can never certify" in self.CAP["note"]
        assert [r["dpi"] for r in self.CAP["renders"]] == [72, 144, 288, 576]

    def test_expected_dimensions_account_for_rotation(self):
        from apps.ire import pdf_raster as pr
        g = {"page_width_pt": 100.0, "page_height_pt": 200.0, "rotation": 0}
        assert pr.expected_dimensions(g, 72) == (100, 200)
        assert pr.expected_dimensions(g, 144) == (200, 400)
        assert pr.expected_dimensions({**g, "rotation": 90}, 72) == (200, 100)

    def test_non_dpi_capable_backend_fails_closed(self):
        from apps.ire import pdf_raster as pr
        try:
            pr._render("sips", "x.pdf", 300)
        except pr.RasterError as e:
            assert e.code == pr.DPI_CAPABILITY_UNAVAILABLE
        else:
            raise AssertionError("must fail closed")

    def test_valid_sweep_rendered_distinct_resolutions(self):
        assert self.RS["gates"]["distinct_resolutions"] is True
        assert self.RS["gates"]["all_manifests_verified"] is True
        assert self.RS["gates"]["source_geometry_identical"] is True
        dims = {tuple(v["manifest"]["actual_dimensions"])
                for v in self.RS["sweep"].values()}
        assert len(dims) == 4
        hashes = {v["manifest"]["output_sha256"]
                  for v in self.RS["sweep"].values()}
        assert len(hashes) == 4, "the invalid sweep had one hash for all four"

    def test_every_raster_carries_a_verified_manifest(self):
        for v in self.RS["sweep"].values():
            m = v["manifest"]
            assert m["dimension_verification"] == "PASSED"
            assert abs(m["width_error_px"]) <= 1
            assert abs(m["effective_dpi_x"] - m["requested_dpi"]) < 1.0
            assert m["backend"] and m["source_sha256"]

    def test_raster_gate_passed_and_metrics_stable(self):
        assert self.RS["gates_pass"] is True
        for k, v in self.RS["high_res_variation"].items():
            assert v <= 0.010, k

    def test_invalid_sweep_preserved_and_withdrawn(self):
        old = json.load(open(os.path.join(
            DOCS, "vq1_master", "vq1_raster_stability_report_invalid.json")))
        assert old["first_attempt_invalid"] is True
        assert old["gates_pass"] is False

    def test_two_independent_inspections_ran_under_a_passed_gate(self):
        assert self.DI["calls"] == 2
        assert self.DI["input_quality"]["quality_gate"] == "PASSED"
        assert set(self.DI["inspections"]) == {
            "A_REFERENCE_FIDELITY_CRITIC",
            "B_ADVERSARIAL_STRUCTURAL_DEFECT_FINDER"}

    def test_any_score_below_ten_blocks_release(self):
        for role, c in self.CO["inspectors"].items():
            assert c["all_ten"] is False, role
            assert c["categories_below_ten"], role
        assert self.CO["release_blocked_because"].startswith("no category")
        assert self.ST["release_status"].startswith("NOT ")

    def test_inspectors_agreed_so_disagreement_is_not_the_blocker(self):
        assert self.CO["inspectors_agree"] is True
        assert set(self.CO["both_returned"]) == {
            "VISUALLY_IMPROVED_BUT_INSUFFICIENT"}

    def test_material_domination_is_surfaced_not_hidden(self):
        assert "rose-gold metallic" in self.CO["dominant_finding"]
        assert "0.992" in self.CO["dominant_finding"]
        assert self.CO["genuine_structural_findings"]

    def test_no_geometry_correction_or_new_candidate(self):
        assert self.CO["no_geometry_correction_implemented"] is True
        assert self.ST["m3_geometry_changed"] is False
        assert self.ST["new_candidate_generated"] is False
        import hashlib
        p = os.path.join(DOCS, "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(p, "rb").read()).hexdigest()[:12] == "4ecc8e9df1d1"

    def test_boundaries_held(self):
        assert self.ST["image_generation_calls"] == 0
        assert self.ST["supplier_requests_sent"] is False


class TestStructuralScopeNormalization:
    """STRUCT-1 — material contamination removed; M3 rescored unchanged."""

    SC = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_structural_inspection_scope.json")))
    RS = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_structural_rescore.json")))
    CO = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_structural_scorecard_consistency.json")))
    LG = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq3_deferred_material_observations.json")))
    ST = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_struct1_stop.json")))

    def test_scope_excludes_material_judgement(self):
        for banned in ("metallic appearance", "rose-gold colour", "gloss",
                       "specular reflection", "polished finish", "texture",
                       "material realism"):
            assert banned in self.SC["may_not_judge"], banned
        for allowed in ("outer silhouette", "neck transition",
                        "shoulder transition"):
            assert allowed in self.SC["may_judge"], allowed

    def test_structural_evidence_has_no_simulated_metal(self):
        assert self.SC["no_simulated_metal"] is True
        assert self.SC["masks_are_flat_diagnostic_values"] is True
        assert self.SC["no_gradient_no_texture_no_shadow_no_reflection"] \
            is True

    def test_reference_contour_uses_validated_edge_evidence(self):
        assert "not colour thresholding" in \
            self.SC["reference_contour_source"]

    def test_material_comments_were_excluded_not_scored(self):
        assert self.CO["contamination_removed"] is True
        for role in ("A", "B"):
            assert self.CO[role]["scores"]["collar_sleeve"] >= 8, \
                "collar was 2/10 only because of material contamination"
        assert self.CO["material_excluded_by_A"] or \
            self.CO["material_excluded_by_B"]

    def test_scores_rose_once_scope_was_enforced(self):
        s = self.CO["score_shift_after_scope_normalization"]
        assert s["collar_sleeve"]["before_A"] < s["collar_sleeve"]["after_A"]
        assert s["collar_sleeve"]["before_B"] < s["collar_sleeve"]["after_B"]

    def test_original_inspections_preserved(self):
        old = json.load(open(os.path.join(
            DOCS, "vq1_master", "vq1_dual_inspection.json")))
        assert old["calls"] == 2
        assert len(old["inspections"]) == 2

    def test_m3_rescored_byte_identical(self):
        import hashlib
        p = os.path.join(DOCS, "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(p, "rb").read()).hexdigest()[:12] == "4ecc8e9df1d1"
        assert self.ST["m3_rescored_byte_identical"] is True

    def test_both_inspectors_rank_neck_and_shoulder_lowest(self):
        lo = self.ST["lowest_categories"]
        assert max(lo["neck_transition"]) <= 8
        assert max(lo["shoulder_transition"]) <= 8
        assert self.CO["convergent_lowest_categories"] == [
            "neck_transition", "shoulder_transition"]

    def test_any_score_below_ten_and_disagreement_block_release(self):
        assert self.CO["A"]["all_ten"] is False
        assert self.CO["B"]["all_ten"] is False
        assert self.CO["inspectors_agree"] is False
        assert len(self.CO["release_blocked_because"]) == 2
        assert self.ST["release_status"].startswith("NOT ")

    def test_no_correction_and_no_third_candidate(self):
        assert self.CO["no_geometry_correction_implemented"] is True
        assert self.ST["m3s1_created"] is False
        for n in ("m3s1", "m3s2", "m3s3"):
            assert not os.path.exists(os.path.join(
                DOCS, "vq1_master", f"{n}.png"))

    def test_deferred_material_cannot_start_vq3(self):
        assert self.LG["classification"] == "DEFERRED_TO_VQ3"
        assert self.LG["relevance"] == "NONBLOCKING_FOR_VQ1"
        assert self.LG["vq3_may_not_begin_before_vq1_human_acceptance"] \
            is True
        assert self.LG["implemented_in_this_execution"] is False

    def test_boundaries_held(self):
        assert self.ST["metallic_material_added"] is False
        assert self.ST["image_generation_calls"] == 0
        assert self.ST["supplier_requests_sent"] is False


class TestM3S1JustificationReview:
    """STRUCT-2 — M3S1 was not built because measurement contradicts it."""

    J = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_m3s1_justification_review.json")))
    IA = json.load(open(os.path.join(
        DOCS, "vq1_master", "vq1_inspector_a_verdict_invalidation.json")))

    def test_neck_and_shoulder_already_match_the_reference(self):
        hw = {int(k): v for k, v in json.load(open(os.path.join(
            DOCS, "vq1_master", "reference_halfwidth_px.json"))).items()}
        fit = json.load(open(os.path.join(
            DOCS, "vq1_master", "master_fit_m3.json")))
        gs = {int(b): a for a, b in fit["fits"]["GLASS"]["samples_px"]}
        band = [y for y in range(664, 741) if y in gs and y in hw]
        assert len(band) >= 20
        for y in band:
            assert abs(gs[y] - hw[y]) < 1e-9, y
        assert self.J["evidence"][
            "neck_shoulder_samples_identical_to_reference"] is True

    def test_m3_already_passes_the_m3s1_gates(self):
        e = self.J["evidence"]
        assert e["m3_neck_error"]["mean"] <= e["m3_neck_gates"]["mean_limit"]
        assert e["m3_neck_error"]["max"] <= e["m3_neck_gates"]["max_limit"]
        assert e["m3_shoulder_error"]["mean"] <= \
            e["m3_shoulder_gates"]["mean_limit"]
        assert e["m3_shoulder_error"]["max"] <= \
            e["m3_shoulder_gates"]["max_limit"]

    def test_no_candidate_was_generated(self):
        assert self.J["m3s1_created"] is False
        assert self.J["protected_geometry_untouched"] is True
        for n in ("m3s1", "m3s2"):
            assert not os.path.exists(os.path.join(
                DOCS, "vq1_master", f"{n}.png"))

    def test_exaggerating_the_inset_is_explicitly_rejected(self):
        c = [o for o in self.J["proposed_unimplemented_options"]
             if o["option"] == "C"][0]
        assert c["geometry_change"] is True
        assert c["recommendation"].startswith("REJECT")
        assert "optimizes for the inspector" in c["recommendation"]
        assert self.J["recommended"].startswith("A or B")

    def test_perceptual_cause_is_recorded_not_assumed_geometric(self):
        assert self.J["code"] == "VQ1_NECK_UNDERCUT_LEGIBILITY_NOT_GEOMETRY"
        assert self.J["evidence"]["reference_inset_px_per_side"] == 8.0
        assert self.J["evidence"][
            "inset_as_fraction_of_body_width"] < 0.03

    def test_inspector_a_verdict_invalidated_but_findings_kept(self):
        assert "VQ1_INSPECTOR_A_PASS_VERDICT_INVALIDATED" in self.IA["codes"]
        assert self.IA["pass_verdict_usable"] is False
        assert self.IA["findings_remain_usable"] is True
        assert self.IA["contradicted_by"]["categories_at_ten"] == 0
        assert os.path.exists(os.path.join(
            DOCS, "vq1_master", self.IA["original_response_preserved"]))

    def test_boundaries_held(self):
        assert self.J["metallic_material_added"] is False
        assert self.J["image_generation_calls"] == 0
        assert self.J["supplier_requests_sent"] is False
