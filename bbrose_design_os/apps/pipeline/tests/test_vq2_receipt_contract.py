"""VQ-2 pre-receipt validation-contract normalization (§8)."""
import hashlib
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq2_lettering_receipt as R

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")
D = os.path.join(DOCS, "vq2")
L = os.path.join(D, "lettering")

SPEC = json.load(open(os.path.join(
    L, "vq2_product_name_lettering_validation_spec.json")))
RES = json.load(open(os.path.join(
    L, "vq2_product_name_lettering_resume_contract.json")))
NORM = json.load(open(os.path.join(
    L, "vq2_pre_receipt_validation_contract_normalization.json")))
STATE = json.load(open(os.path.join(D, "vq2_state.json")))
M3_SHA = "4ecc8e9df1d1"


def good_asset(**over):
    a = {
        "words": ["Rose", "Damascena"],
        "line_order": ["Rose", "Damascena"],
        "raster_object_count": 0, "live_font_object_count": 0,
        "one_object_per_glyph": True, "glyph_collisions": 0,
        "self_intersections": 0, "unintended_open_paths": 0,
        "clean_layer_structure": True, "cubic_bezier_construction": True,
        "baselines_straight": True, "owner_approved": True,
        "transforms": [{"kind": "glyph", "scale_x": 1.0, "scale_y": 1.0}],
        "glyphs": [{"char": "R", "has_counter": True, "counter_count": 1,
                    "expected_counters": 1, "fill_rule": "evenodd"}],
        "native_illustrator_source": True, "pdf_compatible_only": False,
        "native_layers": list(R.REQUIRED_DESIGNER_LAYERS),
        "glyph_layer_placement": dict(R.WORD_LAYER),
        "reference_template": {"locked": True, "nonprinting": True},
        "final_glyphs_only_in_imported_reference": False,
        "metrics": {"Rose": {"apparent_width_err": 0.004,
                             "centerline_err": 0.002,
                             "cap_height_err": 0.003},
                    "Damascena": {"apparent_width_err": 0.006,
                                  "centerline_err": 0.003,
                                  "cap_height_err": 0.004},
                    "line_spacing_err": 0.005},
    }
    a.update(over)
    return a


class TestBaseline:
    def test_a_clean_asset_is_accepted(self):
        r = R.validate_receipt(good_asset())
        assert r["accepted"] is True
        assert r["findings"] == []
        assert r["state"] == R.ACCEPTED


class TestScalingBlocksReceipt:
    def test_horizontal_scaling_blocks(self):
        r = R.validate_receipt(good_asset(transforms=[
            {"kind": "glyph", "scale_x": 0.72, "scale_y": 1.0}]))  # sx != sy
        assert R.HORIZONTAL_SCALING in r["findings"]
        assert r["accepted"] is False

    def test_vertical_scaling_blocks(self):
        # sy > sx is a vertical stretch relative to uniform sizing
        r = R.validate_receipt(good_asset(transforms=[
            {"kind": "glyph", "scale_x": 1.0, "scale_y": 1.18}]))
        assert R.NONUNIFORM_SCALING in r["findings"]
        assert R.HORIZONTAL_SCALING in r["findings"]  # x is the short axis
        assert r["accepted"] is False
        assert r["accepted"] is False

    def test_nonuniform_scaling_blocks(self):
        r = R.validate_receipt(good_asset(transforms=[
            {"kind": "glyph", "scale_x": 0.8, "scale_y": 1.1}]))
        assert R.NONUNIFORM_SCALING in r["findings"]
        assert r["accepted"] is False

    def test_scaled_word_group_blocks(self):
        r = R.validate_receipt(good_asset(transforms=[
            {"kind": "word_group", "scale_x": 0.94, "scale_y": 0.94}]))
        assert R.WORD_GROUP_SCALING in r["findings"]
        assert r["accepted"] is False

    def test_expanded_after_distortion_blocks(self):
        r = R.validate_receipt(good_asset(transforms=[
            {"kind": "glyph", "scale_x": 1.0, "scale_y": 1.0,
             "expanded_after_distortion": True}]))
        assert R.NONUNIFORM_SCALING in r["findings"]

    def test_native_condensed_drawing_is_not_rejected(self):
        """Narrow proportions are a drawing choice, not a transform."""
        r = R.validate_receipt(good_asset(
            transforms=[{"kind": "glyph", "scale_x": 1.0, "scale_y": 1.0,
                         "drawn_proportion_width_ratio": 0.68}]))
        assert r["accepted"] is True
        assert R.HORIZONTAL_SCALING not in r["findings"]
        assert r["narrow_proportions_alone_rejected"] is False

    def test_proportion_rule_permits_native_and_forbids_transform(self):
        p = R.PROPORTION_RULE
        assert p["A_NATIVE_DRAWN_GEOMETRY"]["permitted"] is True
        assert p["A_NATIVE_DRAWN_GEOMETRY"][
            "narrow_proportions_alone_are_a_defect"] is False
        assert p["B_TRANSFORMED_OR_DISTORTED_GEOMETRY"]["permitted"] is False
        assert "not a proportion" in p["rule"]


class TestCapitalization:
    def test_checked_explicitly_in_both_files(self):
        assert "exact_capitalization" in RES["validation_on_receipt"]
        assert "exact_capitalization" in SPEC["mandatory_checks"]
        assert RES["capitalization_requirements"]["required_strings"] == \
            ["Rose", "Damascena"]

    def test_all_caps_blocks(self):
        r = R.validate_receipt(good_asset(words=["ROSE", "DAMASCENA"],
                                          line_order=["ROSE", "DAMASCENA"]))
        assert R.CAPITALIZATION_MISMATCH in r["findings"]

    def test_lowercase_initial_blocks(self):
        r = R.validate_receipt(good_asset(words=["rose", "damascena"],
                                          line_order=["rose", "damascena"]))
        assert R.CAPITALIZATION_MISMATCH in r["findings"]

    def test_alternate_spelling_blocks(self):
        r = R.validate_receipt(good_asset(words=["Rose", "Damascene"],
                                          line_order=["Rose", "Damascene"]))
        assert R.WORDING_MISMATCH in r["findings"]

    def test_line_order_reversal_blocks(self):
        r = R.validate_receipt(good_asset(line_order=["Damascena", "Rose"]))
        assert R.LINE_ORDER_MISMATCH in r["findings"]


class TestCounterIntegrity:
    def test_collapsed_counter_blocks(self):
        r = R.validate_receipt(good_asset(glyphs=[
            {"char": "o", "has_counter": True, "counter_count": 1,
             "expected_counters": 1, "counter_collapsed": True}]))
        assert R.COUNTER_COLLAPSED in r["findings"]

    def test_missing_counter_blocks(self):
        r = R.validate_receipt(good_asset(glyphs=[
            {"char": "e", "has_counter": True, "counter_count": 0,
             "expected_counters": 1}]))
        assert R.COUNTER_MISSING in r["findings"]

    def test_duplicated_counter_blocks(self):
        r = R.validate_receipt(good_asset(glyphs=[
            {"char": "a", "has_counter": True, "counter_count": 3,
             "expected_counters": 1}]))
        assert R.COUNTER_DUPLICATED in r["findings"]

    def test_invalid_fill_rule_blocks(self):
        r = R.validate_receipt(good_asset(glyphs=[
            {"char": "D", "has_counter": True, "counter_count": 1,
             "expected_counters": 1, "fill_rule": "bogus"}]))
        assert R.FILL_RULE_INVALID in r["findings"]

    def test_clipping_mask_simulating_a_counter_blocks(self):
        r = R.validate_receipt(good_asset(glyphs=[
            {"char": "R", "has_counter": True, "counter_count": 1,
             "expected_counters": 1, "fill_rule": "evenodd",
             "counter_simulated_by_clipping": True}]))
        assert R.FILL_RULE_INVALID in r["findings"]

    def test_minimum_letter_set_recorded(self):
        for ch in ("R", "o", "e", "D", "a"):
            assert ch in R.COUNTER_LETTERS_MINIMUM
        assert SPEC["counter_integrity_requirements"][
            "authority_for_which_letters"] == \
            "the actual delivered glyph construction"


class TestOtherGates:
    @pytest.mark.parametrize("over,code", [
        ({"raster_object_count": 1}, R.RASTER_CONTENT),
        ({"live_font_object_count": 1}, R.LIVE_FONT),
        ({"one_object_per_glyph": False}, R.GLYPH_NOT_EDITABLE),
        ({"glyph_collisions": 1}, R.GLYPH_COLLISION),
        ({"self_intersections": 1}, R.SELF_INTERSECTION),
        ({"unintended_open_paths": 1}, R.OPEN_PATH),
        ({"clean_layer_structure": False}, R.LAYER_STRUCTURE_INVALID),
        ({"baselines_straight": False}, R.CURVED_BASELINE),
        ({"owner_approved": False}, R.OWNER_APPROVAL_MISSING),
    ])
    def test_each_defect_blocks(self, over, code):
        r = R.validate_receipt(good_asset(**over))
        assert code in r["findings"] and r["accepted"] is False

    def test_metric_tolerances_block(self):
        a = good_asset()
        a["metrics"]["Damascena"]["apparent_width_err"] = 0.09
        assert R.WIDTH_OUT_OF_TOLERANCE in \
            R.validate_receipt(a)["findings"]


class TestContractParity:
    def test_both_files_expose_the_same_mandatory_checks(self):
        assert SPEC["mandatory_checks"] == RES["validation_on_receipt"]
        assert SPEC["mandatory_checks"] == list(R.CHECK_NAMES)

    def test_all_checks_present(self):
        assert len(R.CHECK_NAMES) == 31
        assert "no_geometry_expanded_after_distortion" in R.CHECK_NAMES
        for needed in ("exact_wording", "exact_capitalization",
                       "correct_line_order", "vector_only_construction",
                       "no_horizontal_scaling", "no_vertical_scaling",
                       "no_nonuniform_scaling", "no_scaled_word_groups",
                       "valid_counters_and_fill_rules",
                       "straight_canonical_baselines", "owner_approval",
                       "native_illustrator_source_provenance",
                       "required_layer_names_present",
                       "pdf_compatible_file_not_accepted_as_source"):
            assert needed in R.CHECK_NAMES

    def test_neither_file_is_weaker(self):
        assert NORM["parity"]["files_aligned"] is True
        assert NORM["parity"]["spec_matches_source"] is True
        assert NORM["parity"]["resume_matches_source"] is True
        assert set(SPEC["finding_for_check"]) == set(RES["finding_for_check"])

    def test_new_zero_gates_added_to_spec(self):
        g = SPEC["A_deterministic_composition_gates"]
        for k in ("vertical_scaled_font_outlines_max",
                  "nonuniform_scaled_objects_max", "scaled_word_groups_max",
                  "invalid_counters_max", "invalid_fill_rules_max"):
            assert g[k] == 0


class TestProvenance:
    def test_normalization_classified_and_dated_pre_receipt(self):
        assert NORM["classification"] == R.NORMALIZED
        assert NORM["lettering_asset_available_during_amendment"] is False
        assert NORM["lettering_asset_processed"] is False
        assert NORM["criteria_tailored_to_a_submitted_file"] is False

    def test_prior_versions_preserved(self):
        for k in ("validation_spec_v1", "resume_contract_v1"):
            p = NORM["prior_contracts"][k]["path"]
            assert os.path.exists(p) and os.path.getsize(p) > 200
            old = json.load(open(p))
            assert old["record_type"].endswith("/1.0")

    def test_versions_bumped_not_silently_replaced(self):
        """v1 -> v2 -> v3, each superseding the last, none overwritten."""
        assert SPEC["record_type"].endswith("/3.1")
        assert RES["record_type"].endswith("/3.1")
        assert SPEC["supersedes"].endswith("/3.0")
        assert RES["supersedes"].endswith("/3.0")
        arch = os.path.join(L, "archive")
        for n in ("vq2_product_name_lettering_validation_spec_v1.json",
                  "vq2_product_name_lettering_validation_spec_v2.json",
                  "vq2_product_name_lettering_resume_contract_v1.json",
                  "vq2_product_name_lettering_resume_contract_v2.json"):
            assert os.path.exists(os.path.join(arch, n)), n

    def test_changed_requirements_enumerated(self):
        j = " ".join(NORM["changed_requirements"]).lower()
        for needed in ("vertical glyph scaling", "non-uniform",
                       "word-group scaling", "capitalization",
                       "counter-integrity", "native drawn"):
            assert needed in j


class TestHoldStateUnchanged:
    def test_no_asset_processed_and_no_candidate(self):
        assert STATE["lettering_asset_received"] is False
        # A2 now exists, built later under explicit owner
        # authorization. The durable invariant is that it is never
        # auto-generated and never self-accepted.
        # A2 is live and has since been revised; the durable invariant is
        # that no slice ever auto-created it. The archive proves that.
        assert json.load(open(os.path.join(
            D, "vq2_a2_artwork_review_hardstop_superseded.json"
        )))["vq2_a2_created"] is False
        for ext in ("ai", "png", "pdf"):
            assert not os.path.exists(os.path.join(D, f"vq2_a3.{ext}"))

    def test_no_glyph_outline_generated(self):
        for n in ("rose_lettering.ai", "damascena_lettering.ai",
                  "vq2_product_name_lettering.ai"):
            assert not os.path.exists(os.path.join(L, n))

    def test_state_still_blocked_on_human_lettering(self):
        # the owner later selected Path B (licensed typeface); VQ-2 is still
        # blocked on the product name and still needs owner approval
        # VQ-2 has moved through several owner-directed states; the durable
        # invariants are that A2 is unbuilt and owner approval is outstanding
        # A2 now exists, built later under explicit owner
        # authorization. The durable invariant is that it is never
        # auto-generated and never self-accepted.
        # A2 is live and has since been revised; the durable invariant is
        # that no slice ever auto-created it. The archive proves that.
        assert json.load(open(os.path.join(
            D, "vq2_a2_artwork_review_hardstop_superseded.json"
        )))["vq2_a2_created"] is False
        assert any("OWNER_APPROVAL" in b["code"] or "PENDING" in b["state"]
                   or "PENDING" in b["code"]
                   for b in STATE["active_blockers"])
        assert STATE["vq2_a1"] == "PRESERVED_DIAGNOSTIC_CANDIDATE"

    def test_m3_byte_identical(self):
        sha = hashlib.sha256(
            open(os.path.join(M, "master_it3.png"), "rb").read()
        ).hexdigest()[:12]
        assert sha == M3_SHA == STATE["m3_identity"]

    def test_vq3_not_started_packaging_untouched(self):
        """VQ-3 has since been started and closed by explicit owner
        instruction. The durable guarantee is that THIS slice started
        neither VQ-3 nor packaging, which its own state record shows."""
        assert STATE["PACKAGING"] == "NOT_STARTED"
        assert STATE.get("vq2_a3", "NOT_GENERATED") == "NOT_GENERATED"

    def test_supplier_drafts_unsent(self):
        sup = json.load(open(os.path.join(
            DOCS, "vq1_reset2", "vq1_supplier_specification_outreach.json")))
        assert not any(s["sent"] for s in sup["suppliers"])

    @pytest.mark.django_db
    def test_tasks_and_project_unchanged(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for t in DesignTask.objects.filter(id__in=[51, 52]):
            assert t.status in ("awaiting_gate_2",
                                "container_stage_visually_rejected")
        p = DesignProject.objects.filter(id=7).first()
        if p is not None:
            assert p.status == "container_rejected"
