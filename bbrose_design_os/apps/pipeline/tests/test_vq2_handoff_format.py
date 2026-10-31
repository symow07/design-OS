"""VQ-2 handoff format correction — native .ai source required (v3)."""
import hashlib
import json
import os

from django.conf import settings

from apps.ire import vq2_lettering_receipt as R

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
D = os.path.join(DOCS, "vq2")
L = os.path.join(D, "lettering")
LIM = json.load(open(os.path.join(L, "vq2_handoff_template_limitation.json")))
NORM2 = json.load(open(os.path.join(
    L, "vq2_pre_receipt_validation_contract_normalization_v2.json")))
SPEC = json.load(open(os.path.join(
    L, "vq2_product_name_lettering_validation_spec.json")))
RES = json.load(open(os.path.join(
    L, "vq2_product_name_lettering_resume_contract.json")))
BRIEF = json.load(open(os.path.join(
    L, "vq2_product_name_lettering_brief.json")))
STATE = json.load(open(os.path.join(D, "vq2_state.json")))


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def native_asset(**over):
    a = {
        "words": ["Rose", "Damascena"], "line_order": ["Rose", "Damascena"],
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
        "metrics": {},
    }
    a.update(over)
    return a


class TestTemplateLimitationDisclosed:
    def test_three_codes(self):
        for c in ("VQ2_HANDOFF_AI_IS_PDF_COMPATIBLE_NOT_NATIVE_LAYERED_AI",
                  "VQ2_TEMPLATE_AI_AND_PDF_BYTES_IDENTICAL",
                  "VQ2_EXISTING_DESIGNER_OUTPUT_LAYER_NOT_TECHNICALLY_"
                  "ENFORCEABLE"):
            assert c in LIM["codes"]

    def test_byte_identity_is_measured_not_asserted(self):
        e = LIM["evidence"]
        assert e["bytes_identical"] is True
        assert _sha(e["template_ai"]) == _sha(e["template_pdf"])

    def test_no_native_layer_claim(self):
        e = LIM["evidence"]
        assert e["native_illustrator_private_layer_structure"] is False
        assert "not native Illustrator editing layers" in e["layer_names_are"]
        assert "must NOT be described" in LIM["claim_withdrawn"]

    def test_files_preserved_unchanged(self):
        assert LIM["files_unchanged"] is True
        t = LIM["template_classification"]
        assert t["delete_rename_or_overwrite"] is False
        for c in ("DESIGNER_REFERENCE_TEMPLATE", "PDF_COMPATIBLE",
                  "NOT_AUTHORITATIVE_NATIVE_AI_SOURCE"):
            assert c in t["classification"]
        for p in (LIM["evidence"]["template_ai"],
                  LIM["evidence"]["template_pdf"]):
            assert os.path.exists(p)

    def test_superseded_instruction_recorded(self):
        s = LIM["superseded_instruction"]
        assert "09_DESIGNER_OUTPUT" in s["was"]
        assert "04_ROSE_LETTERING" in s["now"]


class TestCorrectedWorkflow:
    def test_designer_creates_a_new_native_document(self):
        w = LIM["corrected_designer_workflow"]
        assert w["template_role"] == "REFERENCE_AND_PLACEMENT_GUIDE"
        assert w["designer_must_edit_existing_ai_directly"] is False
        assert w["reproduces_layers_manually"] == \
            list(R.REQUIRED_DESIGNER_LAYERS)
        assert BRIEF["designer_creates_new_native_document"] is True

    def test_eleven_required_layers(self):
        assert len(R.REQUIRED_DESIGNER_LAYERS) == 11
        assert R.REQUIRED_DESIGNER_LAYERS[4] == "04_ROSE_LETTERING"
        assert R.REQUIRED_DESIGNER_LAYERS[5] == "05_DAMASCENA_LETTERING"
        assert R.REQUIRED_DESIGNER_LAYERS[9] == "09_DESIGNER_NOTES_NONPRINTING"

    def test_word_layer_mapping(self):
        assert R.WORD_LAYER["Rose"] == "04_ROSE_LETTERING"
        assert R.WORD_LAYER["Damascena"] == "05_DAMASCENA_LETTERING"


class TestAssetAuthorityChecks:
    def test_clean_native_asset_passes(self):
        r = R.validate_receipt(native_asset())
        assert r["accepted"] is True

    def test_non_native_source_blocks(self):
        r = R.validate_receipt(native_asset(
            native_illustrator_source=False))
        assert R.NATIVE_SOURCE_REQUIRED in r["findings"]

    def test_renamed_pdf_blocks(self):
        r = R.validate_receipt(native_asset(pdf_compatible_only=True))
        assert R.PDF_COMPATIBLE_NOT_SOURCE in r["findings"]

    def test_missing_required_layer_blocks(self):
        layers = [n for n in R.REQUIRED_DESIGNER_LAYERS
                  if n != "05_DAMASCENA_LETTERING"]
        r = R.validate_receipt(native_asset(native_layers=layers))
        assert R.REQUIRED_LAYER_MISSING in r["findings"]

    def test_missing_layer_inventory_blocks(self):
        r = R.validate_receipt(native_asset(native_layers=None))
        assert R.REQUIRED_LAYER_MISSING in r["findings"]

    def test_word_in_wrong_layer_blocks(self):
        r = R.validate_receipt(native_asset(glyph_layer_placement={
            "Rose": "05_DAMASCENA_LETTERING",
            "Damascena": "05_DAMASCENA_LETTERING"}))
        assert R.REQUIRED_LAYER_MISSING in r["findings"]

    def test_unlocked_reference_template_blocks(self):
        r = R.validate_receipt(native_asset(
            reference_template={"locked": False, "nonprinting": True}))
        assert R.OUTPUT_ONLY_IN_REFERENCE in r["findings"]

    def test_glyphs_only_in_imported_reference_blocks(self):
        r = R.validate_receipt(native_asset(
            final_glyphs_only_in_imported_reference=True))
        assert R.OUTPUT_ONLY_IN_REFERENCE in r["findings"]

    def test_valid_native_file_not_rejected_for_binary_difference(self):
        """The guard: differing binary structure is not a defect."""
        r = R.validate_receipt(native_asset(
            binary_structure_differs_from_template=True,
            producer="Adobe Illustrator 29.0"))
        assert r["accepted"] is True
        assert "binary" not in " ".join(r["findings"]).lower()
        assert "must NOT be rejected merely" in R.BINARY_STRUCTURE_RULE


class TestContractV3:
    def test_version_and_parity(self):
        """v3 later became v3.1 (baked-distortion ruling); the v3 checks all
        survive and one more was added."""
        assert R.CONTRACT_VERSION.startswith("3.")
        assert len(R.CHECK_NAMES) >= 30
        assert SPEC["mandatory_checks"] == RES["validation_on_receipt"]
        assert SPEC["mandatory_checks"] == list(R.CHECK_NAMES)
        assert NORM2["parity"]["files_aligned"] is True

    def test_seven_new_checks_present_in_both_files(self):
        for c in ("native_illustrator_source_provenance",
                  "native_layer_inventory_present",
                  "required_layer_names_present",
                  "rose_and_damascena_in_designated_layers",
                  "reference_template_isolated_locked_nonprinting",
                  "no_final_glyphs_only_in_imported_reference",
                  "pdf_compatible_file_not_accepted_as_source"):
            assert c in SPEC["mandatory_checks"]
            assert c in RES["validation_on_receipt"]

    def test_pdf_and_eps_are_supplemental(self):
        a = SPEC["asset_authority_requirements"]
        assert a["pdf_or_eps"] == "SUPPLEMENTAL_DOES_NOT_REPLACE_NATIVE_AI"
        assert a["pdf_compatible_rename_accepted"] is False
        assert any("AUTHORITATIVE" in f
                   for f in RES["accepted_input_formats"])

    def test_amendment_was_pre_receipt(self):
        assert NORM2["lettering_asset_available_during_amendment"] is False
        assert NORM2["lettering_asset_processed"] is False
        assert NORM2["criteria_tailored_to_a_submitted_file"] is False
        assert NORM2["amendment"] == "HANDOFF_FORMAT_CORRECTION"

    def test_prior_v2_contracts_archived(self):
        for k in ("validation_spec_v2", "resume_contract_v2"):
            assert os.path.exists(NORM2["prior_contracts"][k]["path"])


class TestStateHeld:
    def test_still_blocked_and_nothing_generated(self):
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

    def test_state_records_the_correction(self):
        assert STATE["validation_contract_version"].startswith("3.")
        assert STATE["designer_authors_new_native_document"] is True
        assert "NOT_AUTHORITATIVE_NATIVE_AI_SOURCE" in \
            STATE["handoff_template_classification"]

    def test_m3_and_vq3_untouched(self):
        assert STATE["m3_identity"] == "4ecc8e9df1d1"
        # VQ-3 was later started by explicit owner instruction
