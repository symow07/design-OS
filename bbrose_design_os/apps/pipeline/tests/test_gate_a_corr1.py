"""GATE-A-CORR-1 — the AI8 source must carry the colours it was approved with.

The defect these tests exist to prevent is specific and was invisible to every
check that came before: the source's structure, object count and geometry were
all correct, and only its colour was wrong. So the assertions here read colour
three independent ways — from the bytes, by executing the bytes, and from
rendered pixels — and refuse to accept any single one of them alone.

Nothing here can pass Gate A. Several tests exist precisely to prove that.
"""
import hashlib
import json
import os

import pytest
from django.conf import settings

from apps.pipeline.services import ai8_color as A
from apps.pipeline.services import gate_a_corr1 as G
from .gate_a_states import (assert_only_gate_a_passed,
                            not_passed)

VQ2 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
PA = os.path.join(settings.BASE_DIR, "docs", "production_authority")
J = lambda d, n: json.load(open(os.path.join(d, n)))                  # noqa

MANIFEST = J(VQ2, "vq2_a2_r2_final_gate_a_r1_color_manifest.json")
EQUIV = J(VQ2, "vq2_a2_r2_final_gate_a_r1_equivalence.json")
PRESERVED = J(VQ2, "vq2_a2_r2_final_defective_source.json")
CAP = J(VQ2, "vq2_a8_color_capability_fixture.json")
AUTO = J(PA, "gate_a_corr1_automated_gates.json")
GATES = J(PA, "production_authority_gate.json")
RCP = J(PA, "illustrator_execution_verification_receipts.json")
IEV = J(PA, "illustrator_execution_verification_checklist.json")
PRE = J(PA, "production_authority_preflight.json")
ST = J(VQ2, "vq2_state.json")

DEFECTIVE_SHA = \
    "f3707618edf98c87ceb86e03c9ca8d5d42c52c52f708807e335a02794d5a54c1"
COLORS = {"BODY": "#D9BDB5", "COLLAR": "#705242",
          "CLOSURE": "#493034", "ARTWORK": "#502525"}


@pytest.fixture(scope="module")
def defective():
    return open(G.DEFECTIVE).read()


@pytest.fixture(scope="module")
def corrected():
    return open(G.OUT_AI).read()


class TestDefectiveSourcePreserved:
    """The failed source is evidence. It is not edited, renamed or replaced."""

    def test_it_still_hashes_to_what_the_owner_opened(self):
        assert G.sha256_file(G.DEFECTIVE) == DEFECTIVE_SHA
        assert PRESERVED["sha256"] == DEFECTIVE_SHA
        assert PRESERVED["sha256_unchanged_since_gate_a_receipt"] is True

    def test_it_is_not_overwritten_or_renamed(self):
        assert PRESERVED["overwritten"] is False
        assert PRESERVED["renamed"] is False
        assert os.path.exists(G.DEFECTIVE)

    def test_it_is_classified_as_failed_and_not_authority(self):
        assert PRESERVED["classification"] == [
            "ILLUSTRATOR_EXECUTION_FAILED_SOURCE",
            "BLACK_ONLY_AI8_EMISSION",
            "NOT_PRODUCTION_AUTHORITY",
            "PRESERVED_FOR_AUDIT"]
        assert PRESERVED["superseded_by_is_illustrator_verified"] is False

    def test_the_five_gate_a_failure_codes_are_recorded(self):
        assert PRESERVED["gate_a_failure_codes"] == [
            "ILLUSTRATOR_EXECUTION_VERIFICATION_FAILED",
            "ILLUSTRATOR_AI8_ALL_OBJECTS_EMITTED_BLACK",
            "ILLUSTRATOR_DOCUMENT_PROCESS_COLORS_BLACK_ONLY",
            "ILLUSTRATOR_SOURCE_PROOF_COLOR_DIVERGENCE",
            "ILLUSTRATOR_PRODUCTION_SOURCE_REGENERATION_REQUIRED"]

    def test_no_screenshot_is_claimed_that_was_not_received(self):
        """The brief asked for the black screenshot to be preserved. It was
        reported in writing but no file arrived, and saying otherwise would
        fabricate evidence."""
        assert PRESERVED["human_screenshot_received"] is False
        assert "no screenshot file was supplied" in PRESERVED["screenshot_note"]


class TestDefectiveSourceResolvesBlack:
    """The regression fixture. This is what must never be true again."""

    def test_every_visible_object_resolves_to_black(self, defective):
        assert A.all_black(defective) is True
        cols = A.resolve_visible_colors(defective)
        assert len(cols) == 40
        assert all(c == A.BLACK for _, _, c in cols)

    def test_it_declares_black_only_process_colour(self, defective):
        dc = A.document_colors(defective)
        assert dc["process"] == "Black"
        assert dc["rgb"] == []

    def test_none_of_the_approved_colours_appear_in_its_bytes(self, defective):
        for norm in ("0.850980 0.741176 0.709804",
                     "0.439216 0.321569 0.258824",
                     "0.286275 0.188235 0.203922",
                     "0.313725 0.145098 0.145098"):
            assert norm not in defective

    def test_the_corrected_source_fails_this_fixture(self, corrected):
        """The fixture must discriminate, not merely pass on the good file."""
        assert A.all_black(corrected) is False

    def test_the_defective_source_would_fail_the_corrected_gates(
            self, defective):
        """Run the real gate set against the old file: it must be rejected."""
        gates = G.automated_gates(
            defective,
            {"objects": [], "objects_defaulting_to_black": 40,
             "all_expected_objects_found": True,
             "objects_hidden_by_same_color_overlap": 0},
            {"passed": False},
            {"geometry_drift": 0, "glyph_drift": 0, "page_size_drift": 0,
             "logo": {"drift": 0}})
        assert gates["all_passed"] is False
        for expected in ("document_is_not_black_only",
                         "expected_colors_present_in_source_bytes",
                         "black_default_visible_objects_is_zero",
                         "body_color_is_D9BDB5"):
            assert expected in gates["failed"], expected


class TestCorrectedSourceCarriesItsColours:

    def test_all_four_approved_colours_are_in_the_bytes(self, corrected):
        for norm in ("0.850980 0.741176 0.709804",
                     "0.439216 0.321569 0.258824",
                     "0.286275 0.188235 0.203922",
                     "0.313725 0.145098 0.145098"):
            assert norm in corrected

    def test_no_visible_object_defaults_to_black(self, corrected):
        cols = A.resolve_visible_colors(corrected)
        assert len(cols) == 40
        assert not [c for _, _, c in cols if c == A.BLACK]
        assert MANIFEST["objects_defaulting_to_black"] == 0
        assert MANIFEST["objects_with_unassigned_color"] == 0

    def test_each_layer_carries_its_own_role_colour(self, corrected):
        for layer, name, rgb in A.resolve_visible_colors(corrected):
            assert A.hexs(rgb) == COLORS[A.LAYER_ROLE[layer]], (layer, name)

    def test_executing_the_bytes_gives_the_same_colours(self, corrected):
        """A byte scan cannot catch a prolog that pops r, g, b out of order —
        that would silently turn #D9BDB5 into #B5BDD9. Executing it can."""
        resolved = A.ps_resolve_in_order(corrected)
        assert len(resolved) == 40
        for layer, name, rgb, kind, _ in resolved:
            assert A.hexs(rgb) == COLORS[A.LAYER_ROLE[layer]], (layer, name)

    def test_the_emitted_source_is_pure_ascii(self):
        """DSC comments are conventionally 7-bit, and this is the one file
        whose Illustrator compatibility is the entire point of Gate A."""
        raw = open(G.OUT_AI, "rb").read()
        assert not [b for b in raw if b > 127]

    def test_the_rgb_colour_declaration_is_marked_informational(self,
                                                                corrected):
        """Hex is not a DSC numeric convention and no Adobe-authored AI8 EPS
        was available to check the key against, so it must not read as a
        conformance claim."""
        assert "%%DocumentRGBColors:" in corrected
        src = open(A.__file__).read()
        assert "not a claim" in src and "DSC conformance" in src

    def test_the_prolog_actually_defines_the_operators(self, corrected):
        """The defective source shipped an empty prolog, so nothing outside
        Illustrator could render or check it at all."""
        assert "%%BeginProlog\n%%EndProlog" not in corrected
        for op in ("/Xa {", "/XA {", "/f {", "/S {", "/m {", "/C {"):
            assert op in corrected, op
        assert "setrgbcolor" in corrected

    def test_an_object_with_no_role_refuses_to_be_emitted(self):
        """The whole point: an unassigned colour must raise, not default."""
        doc = A.capability_fixture()
        doc.layers[0][2][0]._role = None
        with pytest.raises(ValueError, match="no assigned colour"):
            A.serialize_ai8(doc)

    def test_a_swapped_prolog_is_caught_by_execution(self, corrected):
        """Prove the execution check has teeth by breaking the prolog."""
        broken = corrected.replace(
            "/Xa { /_fb exch def /_fg exch def /_fr exch def } bind def",
            "/Xa { /_fr exch def /_fg exch def /_fb exch def } bind def")
        assert broken != corrected
        rgb = A.ps_resolve_in_order(broken)[0][2]
        assert A.hexs(rgb) != COLORS["BODY"]
        assert A.hexs(rgb) == "#B5BDD9"          # exactly reversed


class TestDocumentColourDeclaration:

    def test_it_no_longer_claims_black_only(self, corrected):
        dc = A.document_colors(corrected)
        assert dc["process"] is None
        assert dc["usage"] == "Color"
        assert set(dc["rgb"]) == set(COLORS.values())

    def test_it_claims_no_production_colour_authority(self, corrected):
        head = corrected.split("%%EndComments")[0]
        assert "sRGB concept artwork" in head
        for forbidden in ("CMYK production", "Pantone 0821", "spot-colour "
                          "authority", "DocumentCustomColors"):
            assert forbidden not in corrected, forbidden
        assert "not CMYK" in head and "not Pantone" in head
        assert "no supplier ink authority" in head

    def test_the_record_keeps_it_srgb_concept_only(self):
        assert "SRGB_CONCEPT_ARTWORK" in \
            MANIFEST["corrected_source"]["classification"]
        assert MANIFEST["corrected_source"]["production_authority"] is False


class TestColourManifest:

    def test_every_expected_object_is_present(self):
        assert MANIFEST["groups_expected"] == A.EXPECTED_GROUPS
        assert MANIFEST["groups_present"] == A.EXPECTED_GROUPS
        assert MANIFEST["all_expected_objects_found"] is True
        assert MANIFEST["objects_total"] == 40
        assert MANIFEST["missing_groups"] == []
        assert MANIFEST["group_count_mismatches"] == {}

    def test_every_object_records_all_required_fields(self):
        for r in MANIFEST["objects"]:
            for k in ("layer", "object", "expected_color",
                      "emitted_color_operator", "emitted_numeric_values",
                      "parsed_resulting_color", "render_sampled_color",
                      "pass"):
                assert r[k] is not None, (r["object"], k)

    def test_the_manifest_matches_the_emitted_operators(self, corrected):
        """The record must be read out of the file, not asserted beside it."""
        emitted = {(la, nm): A.hexs(c)
                   for la, nm, c in A.resolve_visible_colors(corrected)}
        for r in MANIFEST["objects"]:
            key = (r["layer"], r["object"])
            assert emitted[key] == r["expected_color"], key
            assert emitted[key] == r["parsed_resulting_color"], key
            assert r["emitted_color_operator"].split()[:3] == \
                [f"{v:.6f}" for v in r["emitted_numeric_values"]], key

    def test_every_object_passes_and_none_inherits_a_prior_colour(self):
        assert MANIFEST["objects_inheriting_unintended_prior_color"] == 0
        assert [r["object"] for r in MANIFEST["objects"] if not r["pass"]] == []
        assert MANIFEST["passed"] is True

    def test_no_object_is_hidden_by_same_colour_overlap(self):
        assert MANIFEST["objects_hidden_by_same_color_overlap"] == 0
        for r in MANIFEST["objects"]:
            assert r["present_in_composite"] is True, r["object"]
            assert r["composite_pixels_changed_by_removal"] > 0, r["object"]

    def test_rendered_pixels_are_on_the_declared_colours_blend_line(self):
        """Small glyphs are all antialiasing at page scale, so the modal pixel
        is a blend. It still has to be a blend of the RIGHT colour."""
        for r in MANIFEST["objects"]:
            assert r["render_blend_residual_steps"] <= 2, r["object"]
            assert r["render_realised_flat_color"] is not None, r["object"]

    def test_the_realised_flat_colour_matches_the_declared_one(self):
        for r in MANIFEST["objects"]:
            got = tuple(int(r["render_realised_flat_color"][i:i + 2], 16)
                        for i in (1, 3, 5))
            exp = tuple(int(r["expected_color"][i:i + 2], 16)
                        for i in (1, 3, 5))
            assert all(0 <= e - g <= 1 for g, e in zip(got, exp)), r["object"]


class TestColourCapabilityFixture:

    def test_four_swatches_one_per_accepted_colour(self):
        assert [s["expected"] for s in CAP["swatches"]] == [
            "#D9BDB5", "#705242", "#493034", "#502525"]

    def test_each_swatch_records_operator_parse_render_and_expectation(self):
        for s in CAP["swatches"]:
            assert s["emitted_operator"].endswith(" Xa")
            assert s["scanned_from_bytes"] == s["expected"]
            assert s["executed_postscript"] == s["expected"]
            assert s["rendered_pixel"] is not None
            assert s["rendered_pixel_count"] > 0
            assert s["tolerance"] == 1
            assert s["pass"] is True

    def test_the_render_matches_the_accepted_proofs_own_quantisation(self):
        """The rasteriser lands one 8-bit step low. That is not a defect: the
        approved PNG carries exactly the same pixels."""
        for s in CAP["swatches"]:
            assert s["matches_accepted_proof_pixel"] is True

    def test_the_fixture_passes_and_names_its_failure_codes(self):
        assert CAP["passed"] is True
        assert CAP["failure_codes"] == []

    def test_it_is_computed_live_not_just_recorded(self):
        assert A.capability_report()["passed"] is True


class TestSourceProofEquivalence:

    def test_one_object_model_feeds_all_three_outputs(self):
        assert EQUIV["single_object_model"].endswith("ai8_color.py")
        assert EQUIV["separate_preview_color_implementation"] is False
        assert EQUIV["per_object_colors_read_back_from_written_files"] is True
        assert EQUIV["proof_only_color_correction"] is False
        assert EQUIV["ai_only_fallback"] is False

    def test_object_counts_and_ordering_agree(self):
        assert EQUIV["object_count"]["identical"] is True
        assert EQUIV["object_count"]["ai"] == 40
        assert EQUIV["object_ordering_identical"] is True

    def test_no_object_differs_between_source_and_proof(self):
        assert EQUIV["source_versus_proof_color_differences"] == []
        assert EQUIV["visual_diff"]["differing_objects"] == 0
        assert all(r["identical"] for r in
                   EQUIV["per_object_color_comparison"])
        assert EQUIV["passed"] is True

    def test_each_objects_colour_is_read_out_of_both_files(self):
        """Not the model compared with itself: the AI colour comes from the
        .ai bytes and the PDF colour from the written .pdf content stream."""
        rows = EQUIV["per_object_color_comparison"]
        assert len(rows) == 40
        for r in rows:
            assert r["ai_source_color"] == r["expected_color"], r["object"]
            assert r["pdf_color"] == r["expected_color"], r["object"]
            assert r["png_quantised_color_present"] is True, r["object"]
        assert [r["pdf_paint_kind"] for r in rows].count("stroke") == 1

    def test_the_pdf_readback_would_catch_a_wrong_pdf_colour(self):
        """Prove the read-back has teeth rather than trusting it."""
        seq = G.pdf_paint_sequence(G.OUT_PDF)
        assert len(seq) == 40
        assert seq[0][0] == "#D9BDB5"
        assert [k for _, k, _ in seq].count("stroke") == 1
        assert {op for _, kind, op in seq if kind == "fill"} == {"f*"}

    def test_page_dimensions_are_identical(self):
        assert EQUIV["page_dimensions_pt"]["identical"] is True
        assert EQUIV["page_dimensions_pt"]["corrected"] == \
            [0.0, 0.0, 207.1627, 493.2283]

    def test_the_pdf_carries_the_same_numbers_as_the_ai(self, corrected):
        """AI8 path operators map 1:1 onto PDF operators, so this is checkable
        rather than merely asserted."""
        doc = A.parse_ai8(corrected)
        stream = A.content_stream(doc)
        for want in ("0.850980 0.741176 0.709804 rg",
                     "0.313725 0.145098 0.145098 RG"):
            assert want in stream, want
        assert stream.count(" rg") == 39         # 40 objects, one is a stroke
        assert stream.count(" RG") == 1

    def test_the_proof_agrees_with_the_one_the_owner_approved(self):
        v = EQUIV["versus_accepted_proof"]
        assert v["pdf_fills_identical"] is True
        assert v["pdf_strokes_identical"] is True
        assert v["pdf_fill_operators_identical"] is True
        assert v["pdf_stroke_widths_identical"] is True
        assert v["page_size_identical"] is True
        assert v["png_size_identical"] is True
        assert v["flat_colors_identical"] is True

    def test_no_pixel_changed_from_one_flat_colour_to_another(self):
        """Antialiasing cannot do this; only a moved or recoloured shape can."""
        assert EQUIV["versus_accepted_proof"][
            "pixels_changing_between_two_flat_colors"] == 0

    def test_the_remaining_difference_is_attributed_to_the_rasteriser(self):
        """Rendering the owner's own accepted PDF through the same rasteriser
        separates the rasteriser from the content."""
        a = EQUIV["versus_accepted_proof"]["attribution"]
        assert a["attributable_to_rasteriser"] > 10000
        assert a["attributable_to_content"] < 100
        assert a["content_share"] < 0.0001


class TestAcceptedGeometryFrozen:

    def test_geometry_is_byte_identical_to_the_accepted_source(
            self, defective, corrected):
        dd, cd = A.parse_ai8(defective), A.parse_ai8(corrected)
        dob = {(o.layer, o.name): o.geometry for o in dd.objects()}
        cob = {(o.layer, o.name): o.geometry for o in cd.objects()}
        assert sorted(dob) == sorted(cob)
        for k in dob:
            assert dob[k] == cob[k], k

    def test_the_geometry_digest_is_unchanged(self):
        assert EQUIV["geometry_hashes"]["identical"] is True
        assert EQUIV["geometry_hashes"]["defective_source"] == \
            EQUIV["geometry_hashes"]["corrected_source"]

    def test_layer_and_object_names_are_unchanged(self, defective, corrected):
        dd, cd = A.parse_ai8(defective), A.parse_ai8(corrected)
        assert [n for _, n, _ in dd.layers] == [n for _, n, _ in cd.layers]
        assert [(o.layer, o.name) for o in dd.objects()] == \
               [(o.layer, o.name) for o in cd.objects()]

    def test_page_size_is_unchanged(self, defective, corrected):
        dd, cd = A.parse_ai8(defective), A.parse_ai8(corrected)
        assert dd.bbox == cd.bbox == [0.0, 0.0, 207.0, 493.0]
        assert dd.hires_bbox == cd.hires_bbox

    def test_the_frozen_identities_are_restated_not_altered(self):
        assert G.FROZEN == {
            "m3": "4ecc8e9df1d1",
            "lf1_r1": "fcd8003994d52028",
            "product_name_font_unit": "5db4403984ba6f75",
            "approved_logo": "a2b2a82969389ac2",
            "vq3_selected_m3_render": "fbdedc5b23e31745"}

    def test_only_colour_and_format_metadata_changed(self, defective,
                                                     corrected):
        """Whatever else moved, it must not be a coordinate."""
        freeze = G.freeze_verification(defective, corrected)
        assert freeze["geometry_drift"] == 0
        assert freeze["glyph_drift"] == 0
        assert freeze["page_size_drift"] == 0
        assert freeze["logo"]["drift"] == 0
        assert freeze["passed"] is True
        assert freeze["failure_code_if_drift"] == \
            "GATE_A_CORR_ACCEPTED_GEOMETRY_DRIFT"

    def test_a_moved_coordinate_would_be_caught(self, defective, corrected):
        moved = corrected.replace("60.2966 309.4273 m", "60.3966 309.4273 m")
        assert moved != corrected
        freeze = G.freeze_verification(defective, moved)
        assert freeze["geometry_drift"] == 1
        assert freeze["passed"] is False


class TestLogoAndCountersUnchanged:

    @pytest.fixture(scope="class")
    def logo(self, corrected):
        return [o for o in A.parse_ai8(corrected).objects()
                if o.layer == "04_APPROVED_BBROSE_LOGO"]

    def test_nine_components_three_hundred_fourteen_items(self, logo):
        assert len(logo) == 9
        items = subpaths = closes = 0
        for o in logo:
            for op, _ in o.subpaths():
                if op == "m":
                    subpaths += 1
                elif op == "h":
                    closes += 1
                else:
                    items += 1
        assert items == 314
        assert subpaths == 18
        assert closes == 18

    def test_every_logo_subpath_is_still_present(self, logo):
        assert [sum(1 for op, _ in o.subpaths() if op == "m") for o in logo] \
            == [3, 3, 1, 1, 1, 1, 4, 2, 2]

    def test_counters_and_medallion_are_open(self, defective, corrected):
        """Counted by flood fill from outside each glyph, not asserted: a
        closed counter is simply an enclosed region that isn't there."""
        freeze = G.freeze_verification(defective, corrected)
        assert freeze["counters_preserved"] is True
        assert freeze["counter_bearing_objects"] == 20
        assert freeze["logo_counter_regions"] >= 7
        assert freeze["product_name_counter_regions"] >= 5
        for c in freeze["counters"]:
            assert c["enclosed_regions_even_odd"] > 0, c["object"]

    def test_the_fill_rule_matches_the_accepted_proof(self, corrected):
        assert A.EVEN_ODD is True
        assert A.FILL_OP == "f*"
        assert "1 XR" in corrected
        assert "eofill" in corrected

    def test_the_fill_rule_is_load_bearing_and_says_so(self, defective,
                                                      corrected):
        """Nonzero winding CLOSES counters here. An earlier coarser check at
        page scale missed it, so the record states the measurement and does not
        claim the rule is harmless."""
        freeze = G.freeze_verification(defective, corrected)
        assert freeze["fill_rule"] == "evenodd"
        assert freeze["fill_rule_is_load_bearing"] is True
        losers = {o["object"]: (o["even_odd"], o["nonzero"])
                  for o in freeze["objects_losing_counters_under_nonzero"]}
        assert losers, "nonzero must be shown to close something"
        assert losers["SUPPORTING_03_H"] == (2, 0)
        for name in ("SUPPORTING_06_R", "SUPPORTING_09_A"):
            eo, nz = losers[name]
            assert eo - nz == 2, name

    def test_the_winding_risk_is_declared_not_assumed_away(self, defective,
                                                           corrected):
        """Illustrator is not installed, so whether it honours 1 XR is
        genuinely unknown. That must be stated, not smoothed over."""
        freeze = G.freeze_verification(defective, corrected)
        assert freeze["illustrator_winding_declaration_verified"] is False
        assert "cannot be verified here" in freeze["illustrator_winding_risk"]

    def test_the_human_checklist_asks_about_counters(self):
        joined = " ".join(c["check"] for c in IEV["checks"]).lower()
        assert "counters are open" in joined


class TestNoRasterAndNoLiveText:

    def test_no_raster_object(self, corrected):
        assert "%AI5_BeginRaster" not in corrected
        assert "BeginImage" not in corrected
        assert AUTO["checks"]["raster_object_count_is_zero"] is True

    def test_no_live_text(self, corrected):
        for t in ("/_Tx", " Tx ", "/Font"):
            assert t not in corrected, t
        assert AUTO["checks"]["live_text_count_is_zero"] is True


class TestAutomatedGatesCannotPassGateA:

    def test_every_required_check_passed(self):
        assert AUTO["failed"] == []
        assert AUTO["all_passed"] is True
        for name in ("document_is_not_black_only",
                     "expected_colors_present_in_source_bytes",
                     "body_color_is_D9BDB5", "collar_color_is_705242",
                     "closure_color_is_493034",
                     "all_artwork_color_is_502525",
                     "black_default_visible_objects_is_zero",
                     "object_count_matches_manifest",
                     "raster_object_count_is_zero",
                     "live_text_count_is_zero",
                     "geometry_drift_is_zero", "logo_drift_is_zero",
                     "glyph_drift_is_zero", "page_size_drift_is_zero",
                     "source_proof_color_equivalence"):
            assert AUTO["checks"][name] is True, name

    def test_passing_them_all_still_does_not_pass_gate_a(self):
        assert AUTO["gate_a_state"] == "BLOCKED"
        assert AUTO["gate_a_passed"] is None
        assert AUTO["these_checks_cannot_pass_gate_a"] is True
        assert "human" in AUTO["gate_a_requires"]

    def test_the_corrected_source_is_not_described_as_verified(self):
        cs = AUTO["corrected_source"]
        assert cs["classification"] == [
            "ILLUSTRATOR_COMPATIBLE_AI8_EPS_VECTOR_SOURCE",
            "PENDING_HUMAN_ILLUSTRATOR_EXECUTION",
            "SRGB_CONCEPT_ARTWORK"]
        assert cs["illustrator_verified"] is False
        assert cs["production_authority"] is False

    def test_the_corrected_source_hash_is_live(self):
        assert AUTO["corrected_source"]["sha256"] == \
            G.sha256_file(G.OUT_AI)


class TestOutputsExist:

    def test_all_five_named_outputs_were_written(self):
        for name in ("vq2_a2_r2_final_gate_a_r1.ai",
                     "vq2_a2_r2_final_gate_a_r1.pdf",
                     "vq2_a2_r2_final_gate_a_r1.png",
                     "vq2_a2_r2_final_gate_a_r1_color_manifest.json",
                     "vq2_a2_r2_final_gate_a_r1_equivalence.json"):
            p = os.path.join(VQ2, name)
            assert os.path.exists(p), name
            assert os.path.getsize(p) > 0, name

    def test_they_did_not_overwrite_the_defective_outputs(self):
        for name in ("vq2_a2_r2_final.ai", "vq2_a2_r2_final.pdf",
                     "vq2_a2_r2_final_clean.png"):
            assert os.path.exists(os.path.join(VQ2, name)), name
        assert G.sha256_file(G.DEFECTIVE) == DEFECTIVE_SHA

    def test_the_png_matches_the_accepted_proof_dimensions(self):
        from PIL import Image
        assert Image.open(G.OUT_PNG).size == (576, 1371)
        assert Image.open(G.ACCEPTED_PNG).size == (576, 1371)

    def test_the_owner_can_download_them_from_the_board(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "gateauser", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        for n in ("gate-a-r1-ai", "gate-a-r1-pdf", "gate-a-r1-png",
                  "gate-a-r1-manifest", "gate-a-r1-equivalence",
                  "gate-a-r1-gates", "gate-a-defective-source-record",
                  "gate-a-color-capability"):
            r = client.get(f"/api/visual-quality/vq1/{n}/")
            assert r.status_code == 200, n

    def test_what_the_browser_gets_is_byte_identical_to_the_repo(
            self, client, django_user_model):
        """Repo/browser parity. Status 200 says a file was served, not that it
        was THIS file — and serving a stale corrected source is exactly how the
        owner would verify the wrong bytes."""
        u = django_user_model.objects.create_user(
            "gateaparity", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        for name, path in (("gate-a-r1-ai", G.OUT_AI),
                           ("gate-a-r1-pdf", G.OUT_PDF),
                           ("gate-a-r1-png", G.OUT_PNG)):
            r = client.get(f"/api/visual-quality/vq1/{name}/")
            served = (b"".join(r.streaming_content) if r.streaming
                      else r.content)
            assert served == open(path, "rb").read(), name

    def test_r1s_own_records_still_pin_r1(self):
        """R1 is now a preserved failed source, not the pending subject, but
        its own evidence must still describe the file on disk."""
        live = G.sha256_file(G.OUT_AI)
        assert MANIFEST["corrected_source"]["sha256"] == live
        assert AUTO["corrected_source"]["sha256"] == live


class TestTheHumanFacingChecklistIsCurrent:
    """The checklist PDF is the instrument the owner actually opens. A stale
    one would send them back to the file that failed."""

    @pytest.fixture(scope="class")
    def text(self):
        import fitz
        p = os.path.join(PA,
                         "illustrator_execution_verification_checklist.pdf")
        with fitz.open(p) as d:
            return "".join(page.get_text() for page in d)

    def test_it_names_the_current_subject_and_its_live_hash(self, text):
        """Which revision is the subject moves each time one fails; that the
        PDF names the CURRENT one, with a hash matching disk, does not."""
        import os as _os
        name = _os.path.basename(IEV["subject_file"])
        assert name in text, name
        assert IEV["subject_sha256_16"] in text
        live = G.sha256_file(_os.path.join(VQ2, name))[:16]
        assert IEV["subject_sha256_16"] == live

    def test_it_tells_the_owner_not_to_use_the_failed_file(self, text):
        assert "previous attempt FAILED" in text
        assert "do not use that file" in text
        # whichever revision failed most recently, the PDF must name it and
        # its hash in the do-not-use section
        prev = IEV["previous_subject"]
        i = text.index("previous attempt FAILED")
        assert os.path.basename(prev["file"]) in text[i:]
        assert prev["sha256_16"] in text[i:]
        assert prev["result"].endswith("FAILED")

    def test_it_carries_the_colours_to_look_for(self, text):
        for hexv in COLORS.values():
            assert hexv in text, hexv
        assert "none may be black" in text

    def test_it_does_not_claim_production_colour_authority(self, text):
        assert "not CMYK, not Pantone, not spot" in text
        assert "no supplier ink authority" in text

    def test_the_first_action_never_pointed_at_a_failed_source(self):
        act = IEV["actions"][0]["action"]
        assert "NOT the preserved" in act
        assert RCP["required_input"] in act
        # all answered now that the round trip has completed
        assert all(a["done"] is True for a in IEV["actions"])

    def test_the_preflight_pdf_is_current_too(self):
        import fitz
        with fitz.open(os.path.join(
                PA, "production_authority_preflight.pdf")) as d:
            text = "".join(p.get_text() for p in d)
        assert "vq2_a2_r2_final_gate_a_r1.ai" in text
        assert "ILLUSTRATOR_EXECUTION_VERIFICATION_FAILED" in text
        assert "ILLUSTRATOR_AI8_ALL_OBJECTS_EMITTED_BLACK" in text


class TestRootCauseRecorded:

    def test_it_names_the_two_unshared_implementations(self):
        rc = PRESERVED["root_cause"]
        assert "two" in rc["finding"]
        assert rc["fix_is_post_emission_text_patch"] is False

    def test_it_is_evidenced_from_the_accepted_artefacts(self):
        rc = PRESERVED["root_cause"]
        fills = rc["accepted_pdf_colors"]["fills"]
        assert set(fills) == set(COLORS.values())
        assert fills["#502525"] == 36

    def test_the_divider_width_came_from_the_accepted_proof(self):
        sd = PRESERVED["root_cause"]["second_divergence"]
        assert sd["corrected_to_pt"] == 0.362384
        assert "accepted PDF proof" in sd["source_of_value"]

    def test_the_defective_prolog_was_empty(self):
        assert PRESERVED["empty_prolog"] is True

    def test_it_records_forty_black_objects(self):
        assert PRESERVED["visible_objects"] == 40
        assert PRESERVED["visible_objects_resolving_to_black"] == 40
        assert PRESERVED["all_visible_objects_black"] is True


class TestGateAStillBlocked:

    def test_this_slice_recorded_a_failure_that_still_stands(self):
        """Gate A has since passed; the failure this slice captured has not
        been rewritten to suit that."""
        g = GATES["gates"]["A_illustrator_execution"]
        assert g["previous_attempt"]["result"].endswith("FAILED")
        assert g["attempt_history"][0]["code"] == \
            "ILLUSTRATOR_AI8_ALL_OBJECTS_EMITTED_BLACK"
        # the correction state legitimately contains PASSED now — the R2
        # initial open really did pass. The invariant is that the ROUND TRIP
        # has not happened and the automated evidence cannot pass Gate A.
        assert g["attempt_history"][0]["result"] == "FAILED"
        assert g["correction"]["automated_evidence_can_pass_gate_a"] is False

    def test_only_gate_a_ever_passed(self):
        assert_only_gate_a_passed(GATES)

    def test_verification_only_passed_on_a_human_round_trip(self):
        """It took four failures. The pass is attributed to the run that
        earned it, not to any automated check in this slice."""
        assert ST["ILLUSTRATOR_EXECUTION_VERIFICATION"] == "PASSED"
        assert RCP["passed"] is True
        assert RCP["roundtrip_passed"] is True
        assert AUTO["these_checks_cannot_pass_gate_a"] is True

    def test_the_failure_receipt_is_recorded(self):
        r = [x for x in RCP["receipts"] if x["n"] == 2][0]
        assert r["result"] == "FAILED"
        assert r["is_source_emission_defect"] is True
        assert r["is_display_preference"] is False
        assert r["accepted_design_modified"] is False
        assert r["corroborated_in_repo"][
            "accepted_pdf_proof_carried_correct_colors"] is True

    def test_no_source_that_failed_was_ever_the_one_verified(self):
        assert RCP["required_input"] not in (
            "vq2_a2_r2_final.ai", "vq2_a2_r2_final_gate_a_r1.ai")
        verified = J(VQ2, "gate_a_final_verification.json")
        assert verified["identities"]["verified_ai_sha256"] != DEFECTIVE_SHA
        assert verified["identities"]["verified_ai_sha256"] != \
            G.sha256_file(G.OUT_AI)

    def test_the_round_trip_artefacts_eventually_arrived(self):
        assert RCP["awaiting"] == []
        assert RCP["verification_copy_received"] is True

    def test_eps_text_is_still_not_evidence_of_execution(self):
        assert RCP["eps_text_is_not_evidence"] is True
        assert RCP["automated_pass_possible_here"] is False

    def test_visual_confirmation_was_required_not_inferred(self):
        joined = " ".join(RCP["acceptance_rules"])
        assert "confirmed visually in Illustrator" in joined
        assert "automated checks on the bytes are not evidence" in joined


class TestNothingDownstreamStarted:

    def test_packaging_has_not_started(self):
        assert ST["PACKAGING"] == "NOT_STARTED"
        assert PRE["packaging_started"] is False
        assert GATES["packaging_may_begin_now"] is False
        assert RCP["packaging_started"] is False

    def test_no_supplier_request_was_sent(self):
        assert PRE["supplier_requests_sent"] == 0
        assert GATES["supplier_requests_sent"] == 0
        drafts = J(PA, "production_supplier_request_drafts.json")
        for d in drafts.get("drafts", []):
            assert d.get("sent") in (False, None), d.get("supplier")
            assert d.get("state") != "SENT", d.get("supplier")

    def test_no_provider_or_image_generation_call_occurred(self):
        assert PRE["provider_calls"] == 0
        assert PRE["image_generation_calls"] == 0

    def test_this_slice_makes_no_provider_call_at_all(self):
        """The build is pure local computation; there is no client to call."""
        import inspect
        src = inspect.getsource(G) + inspect.getsource(A)
        for forbidden in ("anthropic", "openai", "requests.post", "httpx",
                          "claude_service", "generate_image", "tavily"):
            assert forbidden not in src, forbidden

    def test_closed_creative_workstreams_were_not_reopened(self):
        assert ST["VQ_1"] == "OWNER_ACCEPTED_AND_CLOSED"
        assert ST["VQ_2"] == "VQ2_FINAL_FRONT_ARTWORK_OWNER_APPROVED"
        assert ST["VQ_2_CLOSED"] is True
        assert ST["VQ3_CLOSED"] is True
        assert ST["VQ_2_WORKSTREAM"] == "VQ2_WORKSTREAM_CLOSED"
        assert ST["COMPLETE_PRODUCT_REVIEW"] == "OWNER_ACCEPTED_AND_CLOSED"
        assert ST["vq2_a2_r2_final"] == "OWNER_APPROVED_AND_FROZEN"

    def test_the_accepted_design_is_still_the_accepted_design(self):
        assert PRE["accepted_assets_changed"] is False
        assert ST["m3_frozen"] is True
        assert ST["m3_identity"] == "4ecc8e9df1d1"


class TestBoardShowsTheFailureAndTheFix:
    """A corrected file in the repo is not the owner's review boundary."""

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "gateaboard", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_the_api_reports_the_correction(self, client_in):
        pa = client_in.get("/api/visual-quality/vq1/").json()["vq2"][
            "production_authority"]
        c = pa["gate_a_correction"]
        # the correction state moves as each revision is tried; what must hold
        # is that the round trip has not happened
        # the round trip has since passed; what this slice asserts is that
        # its own automated evidence could never have been what passed it
        assert c["automated_evidence_can_pass_gate_a"] is False
        assert pa["gates_passed"] == 1          # Gate A, and only Gate A
        assert pa["gates_remaining_blocked"] == 4
        # R1 is superseded, so the board now points at a later source; what
        # must not change is that it never claims a pass
        assert c["corrected_source"].startswith("vq2_a2_r2_final_gate_a_r")

    def test_the_page_states_the_failure_and_links_the_corrected_source(
            self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        assert "ILLUSTRATOR EXECUTION FAILED" in html
        assert "ILLUSTRATOR_AI8_ALL_OBJECTS_EMITTED_BLACK" in html
        assert "black silhouette" in html
        assert "vq2_a2_r2_final_gate_a_r1.ai" in html
        assert "/api/visual-quality/vq1/gate-a-r1-ai/" in html
        assert "#D9BDB5" in html
        # the colour defect is closed and the page says so
        assert "Fixed in R1" in html

    def test_the_page_never_claims_the_corrected_source_is_verified(
            self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        # R1 itself is still described as what it was: not the verified file
        assert "not yet Illustrator verified" in html
        assert "R1 ALSO FAILED IN ILLUSTRATOR" in html
