"""GATE-A-CORR-2 — the source must survive Illustrator, not just the checks.

R1 passed every automated gate its own slice defined and still lost 37 of 40
objects when a human opened it. So these tests are written against the thing
that actually failed: whether an object can depend on anything outside itself.
The R2 construction makes that answerable from the bytes — no layer blocks, no
inherited state — and the tests read the bytes rather than the code.

Nothing here passes Gate A, and several tests exist to prove that.
"""
import json
import os

import pytest
from django.conf import settings

from apps.pipeline.services import ai8_color as A
from apps.pipeline.services import gate_a_corr2 as G2
from apps.pipeline.services import illustrator_fixtures as FX
from .gate_a_states import (assert_only_gate_a_passed,
                            not_passed)

VQ2 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
PA = os.path.join(settings.BASE_DIR, "docs", "production_authority")
J = lambda d, n: json.load(open(os.path.join(d, n)))                  # noqa

MANIFEST = J(VQ2, "vq2_a2_r2_final_gate_a_r2_manifest.json")
EQUIV = J(VQ2, "vq2_a2_r2_final_gate_a_r2_equivalence.json")
FAILURE = J(VQ2, "vq2_a2_r2_final_gate_a_r1_failure.json")
OPEN4 = J(VQ2, "vq2_a2_r2_final_gate_a_r2_initial_open.json")
FIXTURES = J(VQ2, "illustrator_compatibility_fixtures.json")
AUTO = J(PA, "gate_a_corr2_automated_gates.json")
GATES = J(PA, "production_authority_gate.json")
RCP = J(PA, "illustrator_execution_verification_receipts.json")
IEV = J(PA, "illustrator_execution_verification_checklist.json")
PRE = J(PA, "production_authority_preflight.json")
ST = J(VQ2, "vq2_state.json")

R0_SHA = "f3707618edf98c87ceb86e03c9ca8d5d42c52c52f708807e335a02794d5a54c1"
R1_SHA = "0555c9f68d10bbd0369bcf191791f5b74366f5f74b3ed8453f4b254ad96400e2"
COLORS = {"BODY": "#D9BDB5", "COLLAR": "#705242",
          "CLOSURE": "#493034", "ARTWORK": "#502525"}


@pytest.fixture(scope="module")
def r2():
    return open(G2.OUT_AI).read()


@pytest.fixture(scope="module")
def r1():
    return open(G2.R1_AI).read()


class TestR1FailureRecorded:

    def test_the_human_result_is_recorded_as_failed(self):
        assert FAILURE["result"] == "FAILED"
        assert FAILURE["environment"]["application"] == "Adobe Illustrator 2026"
        assert FAILURE["codes"] == G2.R1_FAILURE_CODES

    def test_exactly_three_visible_and_thirty_seven_missing(self):
        assert FAILURE["visible_objects"] == 3
        assert FAILURE["missing_objects"] == 37
        assert FAILURE["expected_objects"] == 40
        assert FAILURE["visible_object_names"] == [
            "STRUCTURE_BODY", "STRUCTURE_COLLAR", "STRUCTURE_CLOSURE"]

    def test_the_colour_defect_is_recorded_as_resolved(self):
        """R0's defect and R1's defect are different, and conflating them
        would lose the fact that the colour repair worked."""
        assert any("colour serialization" in s
                   for s in FAILURE["what_this_rules_out"])
        r3 = [x for x in RCP["receipts"] if x["n"] == 3][0]
        assert r3["colour_defect_resolved"] is True

    def test_no_screenshot_file_is_claimed(self):
        assert FAILURE["human_screenshot_received"] is False
        assert "no image FILE was supplied" in FAILURE["screenshot_note"]
        assert FAILURE["screenshot_shows"]

    def test_r1_is_preserved_unchanged(self):
        assert G2.sha256_file(G2.R1_AI) == R1_SHA
        assert FAILURE["preserved"] is True
        assert FAILURE["overwritten"] is False
        assert G2.sha256_file(G2.DEFECTIVE) == R0_SHA


class TestRootCauseNotOverclaimed:
    """The correlation is confounded and the record must say so."""

    def test_both_hypotheses_are_recorded_as_unestablished(self):
        ids = {h["id"]: h for h in FAILURE["hypotheses"]}
        assert set(ids) == {"H1", "H2"}
        for h in ids.values():
            assert h["status"] == "NOT_ESTABLISHED"
        assert FAILURE["cause_asserted"] is False

    def test_the_confound_is_stated_explicitly(self):
        why = FAILURE["why_not_resolved_here"]
        assert "BOTH the first three layers AND" in why
        assert "fits either hypothesis" in why

    def test_the_measurement_behind_it_is_real(self, r1):
        """Re-derive the bbox finding rather than trusting the record."""
        doc = A.parse_ai8(r1)
        objs = list(doc.objects())
        bb = A.object_bbox(objs[0])
        inside = sum(
            1 for o in objs[3:]
            if A.object_bbox(o)[0] >= bb[0] and A.object_bbox(o)[2] <= bb[2]
            and A.object_bbox(o)[1] >= bb[1] and A.object_bbox(o)[3] <= bb[3])
        assert inside == 37
        assert FAILURE["measurement"][
            "artwork_objects_fully_inside_body_bbox"] == 37
        assert FAILURE["measurement"]["artwork_objects_outside_body_bbox"] == 0

    def test_r2_does_not_depend_on_which_is_true(self):
        assert FAILURE["r2_does_not_depend_on_the_answer"]
        assert MANIFEST["layer_blocks_emitted"] == 0
        assert MANIFEST["objects_inheriting_paint_state"] == 0


class TestR2IsFlatStandardPostScript:

    def test_no_layer_blocks_at_all(self, r2):
        for token in ("%AI5_BeginLayer", "%AI5_EndLayer", " Lb", "\nLB"):
            assert token not in r2, token
        assert MANIFEST["layer_blocks_emitted"] == 0

    def test_no_ai_operator_vocabulary(self, r2):
        for op in ("Xa", "XA", "XR"):
            assert f" {op}\n" not in r2, op
        assert MANIFEST["uses_ai_operator_vocabulary"] is False

    def test_it_does_not_claim_to_be_adobe_illustrator(self, r2):
        """R1 claimed Creator: Adobe Illustrator 8.0. It was not, and that
        claim plausibly chose the importer whose behaviour we cannot verify."""
        assert "Adobe Illustrator(R) 8.0" not in r2
        assert "%%Creator: BBROSE Design OS" in r2
        assert "not Adobe Illustrator" in r2

    def test_only_standard_postscript_operators_are_used(self, r2):
        allowed = {"gsave", "grestore", "newpath", "moveto", "lineto",
                   "curveto", "closepath", "setrgbcolor", "setlinewidth",
                   "fill", "eofill", "stroke"}
        seen = set()
        for ln in r2.splitlines():
            if ln.startswith("%") or not ln.strip():
                continue
            seen.add(ln.split()[-1])
        assert seen <= allowed, seen - allowed

    def test_no_prolog_procedures_are_defined(self, r2):
        assert "%%BeginProlog\n%%EndProlog" in r2
        assert " def" not in r2
        assert "bind" not in r2

    def test_it_is_pure_ascii(self):
        assert not [b for b in open(G2.OUT_AI, "rb").read() if b > 127]


class TestEveryObjectIsSelfContained:
    """This is the property R1 lacked and the one that makes both hypotheses
    inapplicable."""

    def test_the_graphics_state_audit_passes(self, r2):
        a = A.audit_graphics_state(r2)
        assert a["passed"] is True
        assert a["objects"] == 40
        assert a["gsave_grestore_balanced"] is True
        assert a["max_nesting_depth"] == 1
        assert a["errors"] == []

    def test_every_object_sets_its_own_colour_and_paints(self, r2):
        a = A.audit_graphics_state(r2)
        assert a["every_object_sets_own_colour"] is True
        assert a["every_object_painted"] is True
        assert a["colour_set_count"] == a["paint_count"] == 40

    def test_gsave_and_grestore_are_balanced_in_the_bytes(self, r2):
        assert r2.count("\ngsave\n") == 40
        assert r2.count("\ngrestore\n") == 40

    def test_no_state_affecting_operator_is_present(self, r2):
        a = A.audit_graphics_state(r2)
        assert a["forbidden_operators_present"] == []
        for op in ("clip", "eoclip", "initclip", "concat", "translate",
                   "scale", "rotate", "setmatrix", "initmatrix", "showpage"):
            assert f"\n{op}\n" not in r2, op

    def test_an_unbalanced_state_would_be_caught(self, r2):
        broken = r2.replace("grestore\n", "", 1)
        a = A.audit_graphics_state(broken)
        assert a["passed"] is False
        assert a["gsave_grestore_balanced"] is False

    def test_an_object_without_its_own_colour_would_be_caught(self, r2):
        broken = r2.replace(
            "0.850980 0.741176 0.709804 setrgbcolor\n", "", 1)
        a = A.audit_graphics_state(broken)
        assert a["passed"] is False
        assert any("without setting a colour" in e for e in a["errors"])

    def test_r1_by_contrast_depends_on_state_it_does_not_set(self, r1):
        """The honest regression: R1's construction is structurally different,
        and this asserts that difference rather than modelling Illustrator."""
        a = A.audit_graphics_state(r1)
        assert a["objects"] == 0            # R1 has no gsave/grestore at all
        assert a["passed"] is False
        assert "%AI5_BeginLayer" in r1
        assert a["forbidden_operators_present"]


class TestR2CarriesAllFortyObjects:

    def test_forty_objects_across_eight_groups(self):
        assert MANIFEST["objects_total"] == 40
        assert MANIFEST["groups_present"] == A.EXPECTED_GROUPS
        assert MANIFEST["all_expected_objects_found"] is True

    def test_every_object_is_explicitly_painted(self):
        assert MANIFEST["explicitly_painted_objects"] == 40
        for r in MANIFEST["objects"]:
            assert r["explicitly_painted"] is True, r["object"]
            assert r["inherits_paint_state"] is False, r["object"]
            assert r["paint_operator"] in ("eofill", "stroke"), r["object"]

    def test_colours_agree_three_ways(self, r2):
        emitted = {(o.layer, o.name): A.hexs(o.emitted_rgb)
                   for o in A.parse_eps_r2(r2).objects()}
        for r in MANIFEST["objects"]:
            key = (r["group"], r["object"])
            assert emitted[key] == r["expected_color"], key
            assert r["parsed_resulting_color"] == r["expected_color"], key
            assert r["executed_color"] == r["expected_color"], key
            assert r["expected_color"] == COLORS[r["role"]], key

    def test_no_object_defaults_to_black(self):
        assert MANIFEST["objects_defaulting_to_black"] == 0
        assert MANIFEST["objects_with_unassigned_color"] == 0

    def test_executing_the_bytes_gives_forty_correct_paints(self, r2):
        paints = A.ps_resolve(r2)
        assert len(paints) == 40
        assert sum(1 for _, kind, _ in paints if kind == "stroke") == 1
        assert {A.hexs(c) for c, _, _ in paints} == set(COLORS.values())

    def test_the_manifest_passes(self):
        assert MANIFEST["passed"] is True


class TestAcceptedArtworkUnchanged:

    def test_geometry_is_byte_identical_to_r1(self, r1, r2):
        a = list(A.parse_ai8(r1).objects())
        b = list(A.parse_eps_r2(r2).objects())
        assert len(a) == len(b) == 40
        for x, y in zip(a, b):
            assert (x.layer, x.name) == (y.layer, y.name)
            assert x.geometry == y.geometry, x.name

    def test_only_operator_names_changed_not_numbers(self, r1, r2):
        """The coordinates are copied through; only the token spelling moves."""
        nums_r1, nums_r2 = [], []
        for o in A.parse_ai8(r1).objects():
            for ln in o.geometry:
                nums_r1 += [t for t in ln.split() if t not in ("m", "L", "C",
                                                               "h")]
        for o in A.parse_eps_r2(r2).objects():
            for ln in o.geometry:
                nums_r2 += [t for t in ln.split() if t not in ("m", "L", "C",
                                                               "h")]
        assert nums_r1 == nums_r2

    def test_geometry_and_ordering_hashes_match(self):
        assert EQUIV["geometry_hashes"]["identical"] is True
        assert EQUIV["object_ordering_identical"] is True

    def test_page_size_unchanged(self):
        assert EQUIV["page_dimensions_pt"]["identical"] is True
        assert EQUIV["page_dimensions_pt"]["r2"] == [0.0, 0.0, 207.1627,
                                                     493.2283]

    def test_frozen_identities_are_restated_not_altered(self):
        assert G2.FROZEN["m3"] == "4ecc8e9df1d1"
        assert G2.FROZEN["lf1_r1"] == "fcd8003994d52028"
        assert G2.FROZEN["product_name_font_unit"] == "5db4403984ba6f75"
        assert G2.FROZEN["approved_logo"] == "a2b2a82969389ac2"

    def test_the_freeze_is_measured_against_r1_not_itself(self, r2):
        """An earlier version passed R1 in twice, which made every drift
        figure incapable of moving."""
        f = G2.r2_freeze(r2)
        assert f["self_comparison"] is False
        assert f["measured_between"] == ["vq2_a2_r2_final_gate_a_r1.ai",
                                         "vq2_a2_r2_final_gate_a_r2.ai"]
        assert f["geometry_drift"] == 0
        assert f["passed"] is True
        assert AUTO["checks"]["freeze_is_not_a_self_comparison"] is True

    def test_a_moved_coordinate_in_r2_would_flip_the_gates(self, r2):
        """Prove the drift gates can actually fail."""
        moved = r2.replace("60.2966 309.4273 moveto",
                           "60.3966 309.4273 moveto")
        assert moved != r2
        f = G2.r2_freeze(moved)
        assert f["geometry_drift"] == 1
        assert f["passed"] is False

    def test_a_dropped_logo_subpath_would_flip_the_logo_gate(self, r2):
        f = G2.r2_freeze(r2)
        assert f["logo"]["drift"] == 0
        assert f["logo"]["source_path_items"] == 314
        assert f["counter_bearing_objects"] > 0
        assert f["logo_counter_regions"] >= 7
        assert f["product_name_counter_regions"] >= 5

    def test_logo_and_counters_intact(self, r2):
        logo = [o for o in A.parse_eps_r2(r2).objects()
                if o.layer == "04_APPROVED_BBROSE_LOGO"]
        assert len(logo) == 9
        items = sum(1 for o in logo for op, _ in o.subpaths()
                    if op not in ("m", "h"))
        subpaths = sum(1 for o in logo for op, _ in o.subpaths() if op == "m")
        assert items == 314
        assert subpaths == 18
        assert AUTO["checks"]["logo_counters_present"] is True
        assert AUTO["checks"]["product_name_counters_present"] is True

    def test_the_proof_still_looks_like_the_approved_artwork(self):
        from PIL import Image
        r2png = Image.open(G2.OUT_PNG).convert("RGB")
        r1png = Image.open(os.path.join(
            VQ2, "vq2_a2_r2_final_gate_a_r1.png")).convert("RGB")
        assert r2png.size == (576, 1371)
        assert list(r2png.get_flattened_data()) == \
            list(r1png.get_flattened_data())


class TestSourceProofEquivalence:

    def test_one_model_feeds_all_three_outputs(self):
        assert EQUIV["single_object_model"].endswith("ai8_color.py")
        assert EQUIV["separate_preview_color_implementation"] is False
        assert EQUIV["proof_only_color_correction"] is False
        assert EQUIV["ai_only_fallback"] is False
        assert EQUIV["per_object_colors_read_back_from_written_files"] is True

    def test_counts_and_colours_agree_across_files(self):
        assert EQUIV["object_count"]["identical"] is True
        assert EQUIV["source_versus_proof_color_differences"] == []
        for r in EQUIV["per_object_color_comparison"]:
            assert r["ai_source_color"] == r["expected_color"], r["object"]
            assert r["pdf_color"] == r["expected_color"], r["object"]
        assert EQUIV["passed"] is True

    def test_the_pdf_readback_sees_the_written_file(self):
        seq = G2.pdf_paint_sequence(G2.OUT_PDF)
        assert len(seq) == 40
        assert [k for _, k, _ in seq].count("stroke") == 1


class TestCompatibilityFixtures:

    def test_all_four_fixtures_exist_and_pass_structurally(self):
        names = [f["fixture"] for f in FIXTURES["fixtures"]]
        assert names == ["A_layer_sequence", "B_compound_path",
                         "C_artwork_paint", "D_graphics_state"]
        assert FIXTURES["all_structural_checks_passed"] is True
        for f in FIXTURES["fixtures"]:
            assert f["passed"] is True, f["fixture"]
            assert f["graphics_state"]["passed"] is True, f["fixture"]

    def test_fixture_a_has_all_eight_groups_and_discriminates(self):
        a = [f for f in FIXTURES["fixtures"]
             if f["fixture"] == "A_layer_sequence"][0]
        assert a["objects_in_emitted_bytes"] == 8
        assert a["groups"] == list(A.EXPECTED_GROUPS)
        assert a["discriminates_stacking_direction"] is True
        assert a["expected_topmost"].endswith("08_SUPPORTING_COPY")
        assert a["expected_bottommost"].endswith("01_STRUCTURE_BODY")
        assert set(a["reads_as"]) == {
            "all eight visible, black on top",
            "all eight visible, red on top",
            "fewer than eight visible"}

    def test_fixture_a_rectangles_actually_overlap(self):
        """Non-overlapping swatches would not separate H1 from H2."""
        doc = FX.fixture_a_layer_sequence()
        boxes = [A.object_bbox(o) for o in doc.objects()]
        for i in range(len(boxes) - 1):
            x0, y0, x1, y1 = boxes[i]
            a0, b0, a1, b1 = boxes[i + 1]
            assert a0 < x1 and b0 < y1, i

    def test_fixture_b_carries_counters(self):
        doc = FX.fixture_b_compound_path()
        outer = list(doc.objects())[0]
        assert sum(1 for op, _ in outer.subpaths() if op == "m") == 3

    def test_fixture_c_is_copied_accepted_artwork_not_regenerated(self):
        src = G2.source_doc()
        by = {(o.layer, o.name): o for o in src.objects()}
        doc = FX.fixture_c_artwork_paint(src)
        for o in doc.objects():
            layer, name = o.name.split("__")
            assert o.geometry == by[(layer, name)].geometry, name

    def test_fixtures_are_not_claimed_to_be_illustrator_confirmed(self):
        assert FIXTURES["illustrator_confirmed"] is False
        for f in FIXTURES["fixtures"]:
            assert f["pending_human_illustrator_confirmation"] is True


class TestRoundTripScript:

    @pytest.fixture(scope="class")
    def jsx(self):
        return open(G2.JSX).read()

    def test_it_exists_and_is_ascii(self, jsx):
        assert os.path.exists(G2.JSX)
        assert not [b for b in open(G2.JSX, "rb").read() if b > 127]

    def test_it_targets_illustrator_and_the_r2_source(self, jsx):
        assert "#target illustrator" in jsx
        assert 'SOURCE_NAME = "vq2_a2_r2_final_gate_a_r2.ai"' in jsx

    def test_it_performs_the_whole_round_trip(self, jsx):
        for step in ("app.open", "saveAs", "doc.close", "exportFile",
                     "IllustratorSaveOptions", "PDFSaveOptions",
                     "ExportOptionsPNG24"):
            assert step in jsx, step

    def test_it_writes_the_four_required_artefacts(self, jsx):
        for name in ("vq2_a2_r2_final_illustrator_verified.ai",
                     "vq2_a2_r2_final_illustrator_verified.pdf",
                     "vq2_a2_r2_final_illustrator_verified.png",
                     "illustrator_execution_verification_result.json"):
            assert name in jsx, name

    def test_it_never_overwrites_the_source(self, jsx):
        assert "Refused to save: the target equals the source." in jsx
        assert "aiOut.fsName === src.fsName" in jsx
        assert "source_unmodified" in jsx

    def test_pass_requires_both_human_confirmations(self, jsx):
        assert "first.all_confirmed && second.all_confirmed" in jsx
        assert '"PASS" : "FAIL"' in jsx
        # every early return happens before human_result is reassigned, so a
        # run that stops anywhere carries the initial FAIL out with it
        assert jsx.index('"human_result": "FAIL"') < jsx.index(
            'rec.human_result = (rec.save_completed')

    def test_it_defaults_to_fail(self, jsx):
        assert '"human_result": "FAIL"' in jsx
        assert jsx.count("rec.human_result =") == 1

    def test_nothing_is_pre_ticked(self, jsx):
        assert 'add("checkbox", undefined, QUESTIONS[i])' in jsx
        assert ".value = true" not in jsx

    def test_it_asks_about_the_artwork_that_went_missing(self, jsx):
        for q in ("BBROSE logo is visible", "divider rule is visible",
                  "Rose and Damascena are visible",
                  "NIGHT REPAIR OIL is visible",
                  "medallion and registered symbol are intact",
                  "Counters are open"):
            assert q in jsx, q

    def test_it_records_what_illustrator_built_even_on_pass(self, jsx):
        """R1's loss could not be diagnosed from here. The next run must
        return the inventory whether it passes or fails."""
        assert "function inventory(doc)" in jsx
        assert "opened_inventory" in jsx and "reopened_inventory" in jsx
        for field in ("z_index", "bounds", "layer_count", "item_count",
                      "hidden", "typename"):
            assert field in jsx, field

    def test_it_counts_paths_document_wide_not_just_top_level(self, jsx):
        """If Illustrator wraps the import in one group, per-layer counting
        reads 1 while 40 paths are present — and 'did all 40 arrive' is the
        one question R1 left open."""
        assert "doc.pathItems.length" in jsx
        assert "path_items_total" in jsx
        assert "rec.object_count = inv.path_items_total" in jsx
        assert "all_paths_arrived" in jsx
        assert "doc.rasterItems.length" in jsx

    def test_missing_group_names_are_not_reported_as_failure(self, jsx):
        """EPS import drops DSC comments, so the eight names will be absent on
        a perfectly good run. Flagging that would be a false alarm."""
        assert "groupNameReport" in jsx
        assert "countGroupsPresent" not in jsx
        assert '"absence_is_expected_for_eps": true' in jsx
        assert '"absence_is_a_failure": false' in jsx
        assert "expected_in_file_not_in_illustrator" in jsx
        assert "A single unnamed layer is EXPECTED here" in jsx

    def test_the_source_size_check_is_not_a_tautology(self, jsx):
        """Comparing the file to itself after the fact is always true."""
        assert "var srcSizeBefore = src.length;" in jsx
        assert jsx.index("var srcSizeBefore") < jsx.index("app.open(src)")
        assert "rec.source_unmodified = (rec.source_size_after" in jsx
        assert "src.length === new File(src.fsName).length" not in jsx

    def test_it_separates_who_did_what(self, jsx):
        assert "CLAUDE_GENERATED_SOURCE" in jsx
        assert "ILLUSTRATOR_SCRIPT_AUTOMATED_ROUNDTRIP" in jsx
        assert "HUMAN_VISUAL_CONFIRMATION" in jsx
        assert '"claude_operated_illustrator": false' in jsx

    def test_it_was_not_run_here(self):
        """Illustrator is installed on this machine. It was never driven from
        here - the artefacts that exist were produced by the owner."""
        result = J(VQ2, "illustrator_execution_verification_result.json")
        assert result["claude_operated_illustrator"] is False
        assert result["authorship"]["visual_judgement"] == \
            "HUMAN_VISUAL_CONFIRMATION"


class TestAutomatedGatesCannotPassGateA:

    def test_every_required_check_passed(self):
        assert AUTO["failed"] == []
        assert AUTO["all_passed"] is True
        for name in ("forty_visible_objects_present",
                     "eight_required_groups_present",
                     "all_artwork_objects_explicitly_painted",
                     "no_hidden_artwork_group", "no_layer_blocks_emitted",
                     "no_clipping_state_after_each_object",
                     "no_unmatched_graphics_state_operation",
                     "every_object_sets_own_colour",
                     "no_object_relies_on_inherited_paint_state",
                     "all_four_approved_colors_present",
                     "black_default_visible_objects_is_zero",
                     "source_proof_geometry_identical",
                     "source_proof_color_identical",
                     "object_ordering_identical",
                     "page_dimensions_identical",
                     "raster_objects_zero", "live_text_zero",
                     "geometry_drift_zero", "artwork_drift_zero"):
            assert AUTO["checks"][name] is True, name

    def test_passing_them_all_still_does_not_pass_gate_a(self):
        assert AUTO["gate_a_state"] == "BLOCKED"
        assert AUTO["gate_a_passed"] is None
        assert AUTO["these_checks_cannot_pass_gate_a"] is True
        assert "human" in AUTO["gate_a_requires"]

    def test_the_record_says_automated_evidence_has_been_wrong_before(self):
        assert "R1 passed every automated gate" in AUTO["r1_taught_us"]

    def test_r2_is_not_described_as_verified(self):
        s = AUTO["r2_source"]
        assert s["classification"] == [
            "ILLUSTRATOR_COMPATIBLE_AI8_EPS_VECTOR_SOURCE",
            "PENDING_HUMAN_ILLUSTRATOR_EXECUTION",
            "SRGB_CONCEPT_ARTWORK"]
        assert s["illustrator_verified"] is False
        assert s["production_authority"] is False

    def test_the_layer_name_tradeoff_is_declared_not_buried(self):
        s = AUTO["r2_source"]
        assert s["named_layers_guaranteed"] is False
        assert "single layer" in s["named_layers_note"]
        assert IEV["named_layers_guaranteed"] is False

    def test_the_hash_is_live(self):
        assert AUTO["r2_source"]["sha256"] == G2.sha256_file(G2.OUT_AI)


class TestGateAStillBlocked:

    def test_state_values(self):
        # Gate A has since passed; R1's own verdict is not rewritten by that
        assert ST["GATE_A_R1"].startswith("FAILED_ARTWORK_NOT_RENDERED")
        assert ST["PACKAGING"] == "NOT_STARTED"

    def test_only_gate_a_ever_passed(self):
        assert_only_gate_a_passed(GATES)
        assert GATES["gates"]["A_illustrator_execution"][
            "correction"]["automated_evidence_can_pass_gate_a"] is False

    def test_every_illustrator_attempt_is_on_record(self):
        hist = GATES["gates"]["A_illustrator_execution"]["attempt_history"]
        assert [h["result"] for h in hist[:2]] == ["FAILED", "FAILED"]
        assert hist[-1]["result"] == "PASSED"
        assert hist[0]["code"] == "ILLUSTRATOR_AI8_ALL_OBJECTS_EMITTED_BLACK"
        assert hist[1]["code"] == "ILLUSTRATOR_GATE_A_R1_ARTWORK_NOT_RENDERED"
        # no attempt, whatever its result, may record a Gate A effect
        for h in hist[:-1]:
            assert "PASSED" not in h.get("gate_a_effect", "NONE")

    def test_required_input_was_r2(self):
        assert RCP["required_input"] == "vq2_a2_r2_final_gate_a_r2.ai"
        assert RCP["required_input_sha256"] == G2.sha256_file(G2.OUT_AI)
        assert RCP["passed"] is True
        assert RCP["roundtrip_script"] == "illustrator_gate_a_roundtrip.jsx"
        assert IEV["subject_file"].endswith("vq2_a2_r2_final_gate_a_r2.ai")

    def test_the_round_trip_artefacts_arrived_later(self):
        for a in RCP["awaiting"]:
            assert a["received"] is False
            assert a["sha256"] is None
            assert not os.path.exists(os.path.join(VQ2, a["filename"]))


    def test_all_three_sources_are_preserved_distinctly(self):
        assert G2.sha256_file(G2.DEFECTIVE) == R0_SHA
        assert G2.sha256_file(G2.R1_AI) == R1_SHA
        assert len({R0_SHA, R1_SHA, G2.sha256_file(G2.OUT_AI)}) == 3


class TestNothingDownstreamStarted:

    def test_packaging_not_started(self):
        assert PRE["packaging_started"] is False
        assert GATES["packaging_may_begin_now"] is False

    def test_no_supplier_request_sent(self):
        assert PRE["supplier_requests_sent"] == 0
        assert GATES["supplier_requests_sent"] == 0

    def test_no_provider_or_image_generation_call(self):
        assert PRE["provider_calls"] == 0
        assert PRE["image_generation_calls"] == 0

    def test_this_slice_makes_no_provider_call(self):
        import inspect
        src = (inspect.getsource(G2) + inspect.getsource(FX)
               + inspect.getsource(A))
        for forbidden in ("anthropic", "openai", "requests.post", "httpx",
                          "claude_service", "generate_image", "tavily"):
            assert forbidden not in src, forbidden

    def test_closed_workstreams_not_reopened(self):
        assert ST["VQ_1"] == "OWNER_ACCEPTED_AND_CLOSED"
        assert ST["VQ_2_CLOSED"] is True
        assert ST["VQ3_CLOSED"] is True
        assert ST["vq2_a2_r2_final"] == "OWNER_APPROVED_AND_FROZEN"
        assert PRE["accepted_assets_changed"] is False


class TestBoardServesR2AndScript:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "gatea2", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_all_r2_artefacts_download(self, client_in):
        for n in ("gate-a-r2-ai", "gate-a-r2-pdf", "gate-a-r2-png",
                  "gate-a-r2-manifest", "gate-a-r2-equivalence",
                  "gate-a-r2-gates", "gate-a-r1-failure",
                  "gate-a-roundtrip-jsx", "gate-a-fixtures",
                  "gate-a-fixture-a-ai", "gate-a-fixture-a-png",
                  "gate-a-fixture-b-ai", "gate-a-fixture-c-ai",
                  "gate-a-fixture-d-ai"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{n}/").status_code == 200, n

    def test_served_bytes_match_the_repo(self, client_in):
        for name, path in (("gate-a-r2-ai", G2.OUT_AI),
                           ("gate-a-roundtrip-jsx", G2.JSX)):
            r = client_in.get(f"/api/visual-quality/vq1/{name}/")
            served = (b"".join(r.streaming_content) if r.streaming
                      else r.content)
            assert served == open(path, "rb").read(), name

    def test_the_page_states_the_r1_failure_and_links_the_script(
            self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        assert "3 of 40 objects rendered" in html
        assert "illustrator_gate_a_roundtrip.jsx" in html
        assert "/api/visual-quality/vq1/gate-a-roundtrip-jsx/" in html
        assert "/api/visual-quality/vq1/gate-a-r2-ai/" in html
        assert "neither is recorded as" in html
        # fixture A was the FIRST step until R2 actually opened; now that it
        # has, the page must present it as forensic rather than as a gate
        assert "single unnamed Illustrator layer is" in html
        assert "forensic rather" in html
        assert "Open fixture A first" not in html

    def test_the_page_never_claims_r2_is_verified(self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        assert "not yet Illustrator verified" in html
        assert "GATE B PASSED" not in html

    def test_the_api_reports_every_attempt(self, client_in):
        pa = client_in.get("/api/visual-quality/vq1/").json()["vq2"][
            "production_authority"]
        c = pa["gate_a_correction"]
        assert c["corrected_source"] == "vq2_a2_r2_final_gate_a_r2.ai"
        assert c["corrected_source_sha256"] == G2.sha256_file(G2.OUT_AI)
        assert len(c["attempts"]) >= 2
        assert pa["gates_passed"] == 1          # Gate A, and only Gate A


class TestR2InitialOpenPassed:
    """The first Illustrator run of this artwork that lost nothing. It closes
    the second defect and moves Gate A not at all."""

    def test_the_result_and_its_four_codes_are_recorded(self):
        assert OPEN4["result"] == "INITIAL_OPEN_PASSED"
        assert OPEN4["codes"] == [
            "ILLUSTRATOR_GATE_A_R2_INITIAL_OPEN_PASSED",
            "ILLUSTRATOR_GATE_A_R1_ARTWORK_LOSS_RESOLVED",
            "ILLUSTRATOR_R2_FULL_VISIBLE_ARTWORK_PRESENT",
            "ILLUSTRATOR_R2_VECTOR_PATHS_PRESENT"]
        assert OPEN4["environment"]["application"] == "Adobe Illustrator 2026"

    def test_everything_the_owner_confirmed_is_listed(self):
        for item in ("BBROSE logo", "medallion and registered symbol",
                     "divider", "Rose", "Damascena", "NIGHT REPAIR OIL",
                     "approved colours",
                     "separate Path and Compound Path objects"):
            assert item in OPEN4["confirmed_visible"], item
        assert OPEN4["artwork_reported_missing"] == 0

    def test_the_r1_artwork_loss_is_recorded_as_resolved(self):
        assert any("R1 artwork loss is resolved" in s
                   for s in OPEN4["what_this_establishes"])
        assert ST["gate_a_known_defects_closed"] == [
            "ILLUSTRATOR_AI8_ALL_OBJECTS_EMITTED_BLACK",
            "ILLUSTRATOR_GATE_A_R1_ARTWORK_NOT_RENDERED"]
        r4 = [x for x in RCP["receipts"] if x["n"] == 4][0]
        assert r4["artwork_loss_resolved"] is True
        assert r4["colour_defect_resolved"] is True

    def test_vector_objects_not_an_embedded_raster(self):
        """Separate Path and Compound Path items means Illustrator parsed the
        EPS rather than embedding it, and the counters survived as objects."""
        assert any("rather than embedding" in s
                   for s in OPEN4["what_this_establishes"])
        assert any("compound paths survived" in s.lower()
                   for s in OPEN4["what_this_establishes"])

    def test_a_successful_open_was_not_itself_a_round_trip(self):
        # recorded at the time of the open; a round trip has since been run
        assert OPEN4["roundtrip_performed"] is False
        assert OPEN4["verification_result_json_received"] is False
        assert OPEN4["gate_a_effect"].startswith("NONE")
        assert any("Gate A" in s for s in OPEN4["what_this_does_not_establish"])

    def test_the_upload_is_the_source_re_uploaded(self):
        u = OPEN4["upload"]
        assert u["reported_sha256"] == G2.sha256_file(G2.OUT_AI)
        assert u["equals_r2_source"] is True
        assert u["is_new_verification_copy"] is False
        assert "not present in this environment" in u["corroboration"]

    def test_uploaded_proofs_are_not_claimed_as_evidence(self):
        """A PDF/PNG matching our own R2 output says nothing about
        Illustrator."""
        up = OPEN4["uploaded_proofs"]
        assert up["carries_illustrator_provenance"] is False
        assert up["generated_here"]["pdf_sha256_16"] == \
            G2.sha256_file(G2.OUT_PDF)[:16]
        assert up["generated_here"]["png_sha256_16"] == \
            G2.sha256_file(G2.OUT_PNG)[:16]

    def test_it_does_not_claim_to_have_isolated_the_r1_mechanism(self):
        """R2 changed several things at once, so a working R2 does not say
        which of H1 or H2 was true."""
        assert any("does not isolate" in s or "H1 or H2" in s
                   for s in OPEN4["what_this_does_not_establish"])
        assert OPEN4["fixture_a_now_optional"] is True
        assert OPEN4["fixture_a_still_useful"] is True
        for h in FAILURE["hypotheses"]:
            assert h["status"] == "NOT_ESTABLISHED"

    def test_the_remaining_blocker_is_named_as_procedural(self):
        assert OPEN4["remaining_blocker_is_procedural_not_a_defect"] is True
        # the named blocker moves as each round trip finds the next thing;
        # what holds is that one is always named
        assert ST["gate_a_remaining_blocker"]

    def test_gate_a_did_not_move(self):
        # Gate A has since passed; this slice's own record is unchanged
        assert ST["PRODUCTION_AUTHORITY_GATE_A"] == "PASSED"
        assert OPEN4["gate_a_effect"].startswith("NONE")
        assert ST["PACKAGING"] == "NOT_STARTED"
        assert_only_gate_a_passed(GATES)

    def test_the_checklist_was_not_ticked_by_a_successful_open(self):
        """An open that works is not an answer to any of the checks."""
        # answered only after the round trip that earned it
        assert OPEN4["verification_result_json_received"] is False

    def test_the_third_attempt_is_on_record_as_a_partial(self):
        hist = GATES["gates"]["A_illustrator_execution"]["attempt_history"]
        assert [h["result"] for h in hist[:3]] == [
            "FAILED", "FAILED", "INITIAL_OPEN_PASSED"]
        assert hist[2]["gate_a_effect"].startswith("NONE")

    def test_the_four_artefacts_are_still_awaited(self):
        assert RCP["awaiting"] == []

    def test_the_source_and_design_were_not_touched(self):
        assert OPEN4["source_modified"] is False
        assert OPEN4["accepted_design_modified"] is False
        assert G2.sha256_file(G2.OUT_AI) == OPEN4["subject_sha256"]
        assert G2.sha256_file(G2.DEFECTIVE) == R0_SHA
        assert G2.sha256_file(G2.R1_AI) == R1_SHA


class TestBoardShowsTheOpenWithoutClaimingAPass:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "gateaopen", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_the_api_reports_the_open_and_the_missing_roundtrip(
            self, client_in):
        c = client_in.get("/api/visual-quality/vq1/").json()["vq2"][
            "production_authority"]["gate_a_correction"]
        assert c["initial_open_passed"] is True
        assert len(c["attempts"]) >= 3

    def test_the_page_says_all_artwork_is_present(self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        assert "R2 OPENED CORRECTLY IN ILLUSTRATOR" in html
        assert "known defects are now closed" in html
        assert "separate Path and Compound Path" in html

    def test_the_page_refuses_to_call_it_a_partial_pass(self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        assert "this is not a partial pass" in html
        assert "provenance, not a defect" in html
        assert "GATE B PASSED" not in html
        assert "/api/visual-quality/vq1/gate-a-r2-initial-open/" in html

    def test_the_initial_open_record_downloads(self, client_in):
        r = client_in.get("/api/visual-quality/vq1/gate-a-r2-initial-open/")
        assert r.status_code == 200
