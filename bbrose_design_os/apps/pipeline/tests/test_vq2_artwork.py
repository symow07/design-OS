"""VQ-2 — surface artwork, flat colour and Level-A typography (§23)."""
import hashlib
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq2_artwork as V

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")
D = os.path.join(DOCS, "vq2")
J = lambda f: json.load(open(os.path.join(D, f)))            # noqa: E731

COPY = J("vq2_visible_copy_inventory.json")
ZONE = J("vq2_artwork_zone_reference.json")
PZ = J("vq2_print_zone_model.json")
PAL = J("vq2_flat_colour_palette.json")
TYPO = J("vq2_typography_manifest.json")
GATES = J("vq2_deterministic_artwork_gates.json")
LAY = J("vq2_layer_manifest.json")
NONREG = J("vq2_structural_non_regression.json")
BRAND = J("vq2_brand_mark_finding.json")
FREEZE = J("vq2_m3_geometry_freeze.json")
REVIEW = J("vq2_artwork_review.json")
ACC = json.load(open(os.path.join(M, "vq1_owner_acceptance.json")))

M3_SHA = "4ecc8e9df1d1"


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]


class TestVQ1RemainsClosed:
    def test_vq1_still_owner_accepted_and_closed(self):
        assert "VQ1_WORKSTREAM_CLOSED" in ACC["codes"]
        assert ACC["candidate_loop_state"] == "PERMANENTLY_CLOSED"

    def test_m3_byte_identical(self):
        assert _sha(os.path.join(M, "master_it3.png")) == M3_SHA
        assert FREEZE["m3_png_sha256"].startswith(M3_SHA)
        assert REVIEW["m3_identity"] == M3_SHA
        assert REVIEW["m3_modified"] is False

    def test_no_new_vq1_candidate_appeared(self):
        for f in os.listdir(M):
            assert not any(t in f.lower()
                           for t in ("m3s1.", "m3s2.", "rim2.", "master_m5",
                                     "master_m6"))


class TestGeometryFreeze:
    def test_freeze_covers_every_protected_value(self):
        for k in ("m3_png_sha256", "m3_ai_sha256", "m3_fit_sha256",
                  "components", "reference_halfwidth_sha256", "centerline_px",
                  "assembly_span_px", "body_width_px", "aspect_w_over_h",
                  "transform"):
            assert k in FREEZE
        assert set(FREEZE["components"]) == {"DARK_CLOSURE", "COLLAR", "GLASS"}

    def test_freeze_verification_reports_no_drift(self):
        v = V.verify_freeze(FREEZE, M)
        assert v["drifted"] is False
        assert v["differing_fields"] == []
        assert NONREG["m3_hashes_unchanged"] is True

    def test_drift_fails_closed(self):
        tampered = dict(FREEZE)
        tampered["m3_png_sha256"] = "0" * 64
        v = V.verify_freeze(tampered, M)
        assert v["drifted"] is True
        assert v["code"] == V.M3_DRIFT

    def test_component_change_is_detected(self):
        tampered = json.loads(json.dumps(FREEZE))
        tampered["components"]["GLASS"] = "deadbeef"
        v = V.verify_freeze(tampered, M)
        assert "component:GLASS" in v["differing_fields"]

    def test_artwork_may_not_rewrite_geometry(self):
        assert FREEZE["artwork_may_rewrite_geometry"] is False
        assert NONREG["mask_modifies_contour"] is False
        assert NONREG["artwork_in_structural_silhouette"] is False
        assert NONREG["material_cue_changes_geometry"] is False


class TestCopyCannotBeInvented:
    def test_every_string_came_from_the_reference(self):
        assert COPY["wording_invented"] is False
        assert "READ DIRECTLY" in COPY["wording_source"]
        strings = {e["display"] for e in COPY["elements"]}
        assert {"BBROSE", "Rose", "Damascena",
                "NIGHT REPAIR OIL"} <= strings

    def test_nothing_regulatory_or_promotional_was_added(self):
        for k in ("no_regulatory_claims_added", "no_ingredients_added",
                  "no_volume_or_weight_added",
                  "no_certification_icons_added", "no_slogans_added"):
            assert COPY[k] is True

    def test_unresolved_copy_is_recorded_not_guessed(self):
        assert COPY["unresolved_count"] == 1
        assert COPY["unresolved"][0]["code"] == V.MEDALLION_UNRESOLVED

    def test_unresolved_element_blocks_release(self):
        assert REVIEW["state"] == V.HARD_STOP
        assert "VQ2_BRAND_MARK_SOURCE_CONFLICT" in REVIEW["stop_grounds"]

    def test_medallion_was_not_drawn_as_artwork(self):
        assert BRAND["logo_redesigned"] is False
        assert BRAND["image_trace_used"] is False
        assert BRAND["raster_logo_placed_in_artwork"] is False
        assert BRAND["raster_logo_state"] == V.REFERENCE_ONLY
        brand_line = [ln for ln in TYPO["lines"]
                      if ln["role"] == "BRAND_MARK"][0]
        undrawn = [g for g in brand_line["glyphs"] if not g["drawn"]]
        assert len(undrawn) == 1 and undrawn[0]["char"] == "○"

    def test_medallion_advance_is_still_consumed(self):
        brand_line = [ln for ln in TYPO["lines"]
                      if ln["role"] == "BRAND_MARK"][0]
        med = [g for g in brand_line["glyphs"] if not g["drawn"]][0]
        assert med["advance_px"] > 0


class TestTypography:
    def test_exact_typeface_is_unresolved_not_silently_substituted(self):
        assert TYPO["exact_typeface_state"] == V.TYPEFACE_UNRESOLVED
        assert TYPO["silent_substitution"] is False
        assert "CONTAINER_FONT_FALLBACK_DETECTED" in TYPO["fallback_codes"]

    def test_relationship_to_original_is_documented(self):
        r = TYPO["relationship_to_original"]
        for k in ("method", "serif_character_delta", "sans_character_delta",
                  "what_is_faithful", "what_is_not_faithful"):
            assert r[k]
        assert "exact letterform character" in r["what_is_not_faithful"]

    def test_licence_state_is_never_inferred(self):
        for face in TYPO["faces_used"].values():
            assert face["licence_state"] == "LICENCE_REVIEW_REQUIRED"
            assert face["production_use_status"] == "UNVERIFIED"
            assert "NOT licence permission" in face["fs_type_meaning"]

    def test_outlining_is_not_claimed_as_a_licence_workaround(self):
        assert "does not resolve the licence" in TYPO["licence_position"]

    def test_no_raster_text_and_no_image_trace(self):
        assert TYPO["raster_text_objects"] == 0
        assert TYPO["image_trace_used"] is False
        assert LAY["image_trace_used"] is False
        assert LAY["raster_typography"] == 0
        assert GATES["counts"]["raster_typography_objects"] == 0

    def test_glyphs_are_individually_editable_vectors(self):
        for ln in TYPO["lines"]:
            assert ln["outlined_vector"] is True
            assert ln["raster"] is False
            assert ln["glyph_count"] >= 1

    def test_negative_tracking_is_refused_not_applied(self):
        for t in GATES["tracking_solutions"]:
            assert t["tracking"] >= 0.0
            if t["clamped"]:
                assert t["code"] == V.NEGATIVE_TRACKING_REFUSED

    def test_condensed_face_finding_is_recorded(self):
        f = GATES["condensed_face_finding"]
        assert f["code"] == V.CONDENSED_UNAVAILABLE
        assert "negative tracking (collides glyphs)" in \
            f["rejected_alternatives"]
        assert "horizontal scaling (stretched glyphs)" in \
            f["rejected_alternatives"]

    def test_quadratic_outlines_are_converted_not_straightened(self):
        """A TrueType glyph must yield curves, never a polygon through its
        off-curve control points."""
        from apps.ire.graph import Color
        face = V.load_face("/System/Library/Fonts/Supplemental/Bodoni 72.ttc",
                           0)
        segs = V.glyph_segments(face, "R", 0.02, 0.0, 0.0)
        assert segs
        assert any(getattr(s, "op", "") == "C" for s in segs)

    def test_tracking_solves_against_ink_width(self):
        from apps.ire.graph import Color
        face = V.load_face("static/fonts/NotoSans-Regular.ttf")
        sol = V.solve_tracking(face, "ABC", 10.0, 40.0)
        paths, _, _ = V.text_glyph_paths(
            face, "ABC", cap_px=10.0, x=0.0, y=0.0,
            tracking_px=sol["tracking"], fill=Color.from_hex("#000000"),
            name="t")
        x0, _, x1, _ = V.line_bbox(paths)
        assert abs((x1 - x0) - 40.0) < 0.05


class TestPrintZone:
    def test_single_front_zone_on_the_centerline(self):
        assert PZ["centered_on_centerline_px"] == V.CENTERLINE_PX
        assert PZ["rear_artwork_present"] is False
        assert PZ["wraparound_assumed"] is False

    def test_zone_clears_shoulder_collar_and_base(self):
        assert PZ["clear_of_shoulder"] is True
        assert PZ["clear_of_base"] is True
        assert PZ["crosses_collar_or_neck"] is False

    def test_zone_is_conceptual_not_production(self):
        assert PZ["conceptual_until_supplier_confirmation"] is True
        assert PZ["is_production_print_dimension"] is False

    def test_containment_violations_are_reported_not_hidden(self):
        assert GATES["counts"]["print_zone_violations"] == 1
        assert GATES["print_zone_violations_detail"]
        assert any(f["gate"] == "print_zone_violations"
                   for f in GATES["failures"])


class TestFlatColour:
    def test_only_artwork_ink_is_implemented(self):
        for c in PAL["colours"]:
            if c["colour_class"] == "ARTWORK_INK":
                assert c["implemented_in_vq2"] is True
            else:
                assert c["implemented_in_vq2"] is False

    def test_material_colour_is_recorded_but_deferred(self):
        mats = [c for c in PAL["colours"]
                if c["colour_class"] == "MATERIAL_BASE_COLOUR"]
        assert mats and all(not c["implemented_in_vq2"] for c in mats)
        assert "VQ-3" in PAL["separation_rule"]["B_MATERIAL_BASE_COLOUR"]

    def test_no_lighting_colour_was_sampled_as_artwork(self):
        assert not [c for c in PAL["colours"]
                    if c["colour_class"] == "LIGHTING_OR_REFLECTION_COLOUR"]

    def test_no_material_effects(self):
        assert PAL["gradients_used"] == 0
        assert PAL["material_effects_used"] == 0
        assert REVIEW["material_realization_added"] is False


class TestLayersAndGates:
    def test_all_eleven_layers_present_in_order(self):
        assert LAY["layers"] == list(V.LAYERS)
        assert len(V.LAYERS) == 11

    def test_nonprinting_counted_separately_from_artwork(self):
        c = LAY["object_counts"]
        assert c["nonprinting_objects"] >= 1
        assert c["artwork_objects"] >= 1
        assert c["unsupported_visible_objects"] == 0

    def test_document_is_not_flattened(self):
        assert LAY["flattened"] is False
        assert LAY["all_objects_named"] is True
        assert LAY["destructive_clipping_of_m3"] is False

    def test_gates_are_per_line_not_aggregated(self):
        assert "per_line_not_aggregated" in GATES
        roles = {c["role"] for c in GATES["per_line"]}
        assert {"BRAND_MARK", "PRODUCT_NAME_LINE_1", "PRODUCT_NAME_LINE_2",
                "SUPPORTING_COPY"} <= roles

    def test_gate_failures_are_reported_honestly(self):
        assert GATES["all_pass"] is False
        assert REVIEW["gates_all_pass"] is False
        assert len(REVIEW["gate_failures"]) == len(GATES["failures"])

    def test_measurement_space_is_declared_everywhere(self):
        assert GATES["measurement_space"] == V.MEASUREMENT_SPACE
        assert "APPARENT" in V.PROJECTION_NOTE
        assert ZONE["flat_artwork_width_state"] == V.FLAT_WIDTH_UNRESOLVED
        assert ZONE["flat_artwork_width"] is None

    def test_projection_curvature_is_recorded_not_reproduced(self):
        v = ZONE["visible_curvature_effect"]
        assert v["detected"] is True
        assert v["code"] == "VQ2_BASELINE_ARC_FROM_CYLINDRICAL_PROJECTION"
        assert v["apparent_baseline_max_residual_px"] > 1.0


class TestScopeAndBoundaries:
    def test_only_one_candidate(self):
        assert REVIEW["candidates_created"] == 1
        # scoped to the A1 slice, whose review record is the archive
        old = json.load(open(os.path.join(
            D, "vq2_a2_artwork_review_hardstop_superseded.json")))
        assert old["vq2_a2_created"] is False

    def test_inspections_skipped_because_gates_failed(self):
        assert REVIEW["inspections_run"] == 0
        assert "ONLY after the deterministic gates pass" in \
            REVIEW["inspections_skipped_reason"]

    def test_no_provider_or_image_generation_call(self):
        assert REVIEW["provider_calls"] == 0
        assert REVIEW["image_generation_calls"] == 0

    def test_vq3_and_packaging_not_started(self):
        assert REVIEW["vq3_started"] is False
        assert REVIEW["packaging_started"] is False
        # VQ-3 was later started by explicit owner instruction

    def test_production_stays_blocked(self):
        assert REVIEW["production_geometry"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert REVIEW["is_production_artwork"] is False
        assert REVIEW["human_accepted"] is False

    def test_supplier_drafts_unsent(self):
        sup = json.load(open(os.path.join(
            DOCS, "vq1_reset2", "vq1_supplier_specification_outreach.json")))
        assert not any(s["sent"] for s in sup["suppliers"])
        assert REVIEW["supplier_requests_sent"] is False

    def test_output_package_present(self):
        for ext in ("pdf", "png", "json"):
            p = os.path.join(D, f"vq2_artwork_review.{ext}")
            assert os.path.exists(p) and os.path.getsize(p) > 2000
        for f in ("vq2_a1.ai", "vq2_a1.png"):
            assert os.path.getsize(os.path.join(D, f)) > 1000

    @pytest.mark.django_db
    def test_tasks_and_project_unchanged(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for t in DesignTask.objects.filter(id__in=[51, 52]):
            assert t.status in ("awaiting_gate_2",
                                "container_stage_visually_rejected")
        p = DesignProject.objects.filter(id=7).first()
        if p is not None:
            assert p.status == "container_rejected"
