"""Round trip 1 — the artwork survived Illustrator, the page did not.

Two things went wrong and the tests keep them apart. The artboard drift is a
defect in the automation script. The aborted run that destroyed the result JSON
is a different defect in the same script. Neither is a defect in the artwork,
and nothing here lets either read as progress toward Gate A.

The measurements are taken from the returned file, not from the report.
"""
import json
import os

import pytest
from django.conf import settings

from apps.pipeline.services import gate_a_corr2 as G2
from apps.pipeline.services import gate_a_roundtrip1 as R

from .gate_a_states import (assert_only_gate_a_passed,
                            not_passed)

VQ2 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
PA = os.path.join(settings.BASE_DIR, "docs", "production_authority")
J = lambda d, n: json.load(open(os.path.join(d, n)))                  # noqa

REC = J(VQ2, "gate_a_roundtrip_1_artboard_drift.json")
ABORT = J(PA, "illustrator_execution_verification_result_aborted_run.json")
FINAL = J(PA, "gate_a_roundtrip_final_gates.json")
GATES = J(PA, "production_authority_gate.json")
RCP = J(PA, "illustrator_execution_verification_receipts.json")
IEV = J(PA, "illustrator_execution_verification_checklist.json")
PRE = J(PA, "production_authority_preflight.json")
ST = J(VQ2, "vq2_state.json")

DRIFT_SHA = \
    "547f55b8f6a71e9b85236d185b0fdc977497374ebf96fc50339388c8660967c0"
R2_SHA = "6ae00f726ddefda4adad93325735c489e3fe987452f9c1a2f603236c73e4c49a"
APPROVED = {"#D9BDB5", "#705242", "#493034", "#502525"}


class TestTheRoundTripWasGenuine:
    """For the first time the returned file is not the source re-uploaded."""

    def test_the_returned_hash_matches_what_was_reported(self):
        assert G2.sha256_file(R.DRIFT_AI) == DRIFT_SHA
        assert REC["roundtrip_is_genuine"]["matches_owner_report"] is True

    def test_it_differs_from_the_r2_source(self):
        assert DRIFT_SHA != R2_SHA
        assert REC["roundtrip_is_genuine"]["differs_from_r2_source"] is True
        assert G2.sha256_file(G2.OUT_AI) == R2_SHA

    def test_it_is_a_native_illustrator_document_not_our_eps(self):
        head = open(R.DRIFT_AI, "rb").read(16)
        assert head.startswith(b"%PDF"), head
        assert REC["roundtrip_is_genuine"][
            "is_native_illustrator_document"] is True

    def test_all_three_exports_came_back(self):
        for p in (R.DRIFT_AI, R.DRIFT_PDF, R.DRIFT_PNG):
            assert os.path.exists(p), p
            assert os.path.getsize(p) > 1000, p


class TestArtworkVerifiedFromTheFile:
    """Measured here, not taken on trust."""

    @pytest.fixture(scope="class")
    def measured(self):
        return R.inspect_drift_copy()

    def test_forty_vector_objects(self, measured):
        assert measured["drawing_objects"] == 40
        assert measured["filled_objects"] == 39
        assert measured["stroked_objects"] == 1
        assert REC["artwork_verified_here"]["object_count_preserved"] is True

    def test_only_the_four_approved_colours(self, measured):
        seen = set(measured["fill_colours"]) | set(measured["stroke_colours"])
        assert seen == APPROVED
        assert measured["fill_colours"]["#502525"] == 36
        assert measured["stroke_colours"] == {"#502525": 1}

    def test_no_raster_and_no_live_text(self, measured):
        assert measured["raster_images"] == 0
        assert measured["live_text_characters"] == 0

    def test_the_artwork_verdict_is_pass(self):
        assert REC["artwork_verified_here"]["passed"] is True
        assert REC["pass_codes"] == [
            "ILLUSTRATOR_R2_SAVE_COMPLETED",
            "ILLUSTRATOR_R2_FULL_ARTWORK_PRESERVED",
            "ILLUSTRATOR_R2_COLOURS_PRESERVED",
            "ILLUSTRATOR_R2_VECTOR_OBJECTS_PRESERVED"]


class TestArtboardFailed:

    def test_the_page_is_the_wrong_size(self):
        a = REC["artboard_failure"]
        assert a["actual_page_pt"] == [763.654, 983.225]
        assert a["expected_page_pt"] == [207.1627, 493.2283]
        assert a["page_size_drift"] is True

    def test_the_artwork_was_translated_not_rescaled(self):
        """A resize would be an artwork defect. A translation is not."""
        a = REC["artboard_failure"]
        assert a["artwork_translated"] is True
        assert a["artwork_rescaled"] is False
        assert abs(a["ink_size_pt"][1] - 423.989) < 0.01

    def test_the_four_failure_codes_are_recorded(self):
        assert REC["fail_codes"] == [
            "ILLUSTRATOR_GATE_A_PAGE_SIZE_DRIFT",
            "ILLUSTRATOR_GATE_A_ARTBOARD_NOT_PRESERVED",
            "ILLUSTRATOR_ROUNDTRIP_PARTIAL_PASS",
            "ILLUSTRATOR_EXECUTION_VERIFICATION_INCOMPLETE"]

    def test_it_is_named_a_script_defect_not_an_artwork_defect(self):
        rc = REC["root_cause"]
        assert rc["is_an_automation_script_defect"] is True
        assert rc["is_an_artwork_defect"] is False
        assert rc["artwork_untouched_by_the_fix"] is True
        assert REC["accepted_artwork_modified"] is False
        assert REC["r2_source_modified"] is False


class TestTheAbortedRunIsSeparated:
    """The result JSON on disk does not describe the files on disk."""

    def test_the_json_records_a_failed_aborted_run(self):
        assert ABORT["human_result"] == "FAIL"
        assert ABORT["save_completed"] is False
        assert ABORT["reopen_completed"] is False
        assert ABORT["pdf_export_completed"] is False
        assert ABORT["png_export_completed"] is False

    def test_it_was_the_wrong_file_that_was_selected(self):
        joined = " ".join(ABORT["notes"])
        assert "illustrator_gate_a_roundtrip.jsx" in joined
        assert "could not open" in joined

    def test_the_finding_says_it_belongs_to_a_different_run(self):
        s = REC["second_finding_aborted_run"]
        assert s["recorded_result"] == "FAIL"
        assert s["the_returned_files_are_still_genuine"] is True
        assert s["but_provenance_is_not_established_by_the_json"] is True

    def test_a_failed_run_did_not_pretend_to_be_a_pass(self):
        """The script defaulted to FAIL and stayed there, which is the one
        thing it got right."""
        assert ABORT["human_result"] == "FAIL"
        assert ABORT["verified_filename"] is None


class TestScriptCorrected:

    @pytest.fixture(scope="class")
    def jsx(self):
        return open(R.JSX).read()

    def test_it_is_still_ascii(self):
        assert not [b for b in open(R.JSX, "rb").read() if b > 127]

    def test_the_source_page_is_declared(self, jsx):
        assert "var PAGE_W = 207.1627;" in jsx
        assert "var PAGE_H = 493.2283;" in jsx
        assert "var MARGIN_LEFT = 34.109999;" in jsx
        assert "var MARGIN_BOTTOM = 34.001999;" in jsx

    def test_the_artboard_is_restored_before_saving(self, jsx):
        assert "function restoreArtboard(doc)" in jsx
        assert jsx.index("rec.artboard_restore = restoreArtboard(doc)") < \
            jsx.index("doc.saveAs(aiOut, aiOpts)")

    def test_it_anchors_at_left_bottom_and_takes_the_exact_page_size(self,
                                                                    jsx):
        """Deriving right/top from margins would let a measurement difference
        become a wrong page size. Anchoring makes the size exact."""
        assert "var right = left + PAGE_W;" in jsx
        assert "var top = bottom + PAGE_H;" in jsx
        assert "artboardRect = [left, top, right, bottom]" in jsx

    def test_it_refuses_to_save_a_wrong_sized_artboard(self, jsx):
        assert "refusing to save a document whose page size" in jsx
        assert "ARTBOARD_RESTORE_FAILED" in jsx

    def test_it_rechecks_the_artboard_after_reopen(self, jsx):
        assert "rec.artboard_after_reopen = artboardSize(reopened)" in jsx
        assert "ARTBOARD_DRIFT_AFTER_REOPEN" in jsx

    def test_pass_now_requires_the_artboard(self, jsx):
        assert "rec.artboard_restore.passed" in jsx
        assert "rec.artboard_after_reopen.width_ok" in jsx
        assert "rec.artboard_after_reopen.height_ok" in jsx

    def test_a_wrong_file_selection_now_stops_the_run(self, jsx):
        """It previously warned and carried on into a failed open."""
        assert "WRONG_FILE_SELECTED" in jsx
        assert "Stopped without opening anything." in jsx
        assert "Continuing, but the subject of" not in jsx

    def test_a_later_run_cannot_destroy_an_earlier_record(self, jsx):
        assert "_previous_" in jsx
        assert "f.copy(keep.fsName)" in jsx

    def test_it_does_not_move_or_scale_the_artwork(self, jsx):
        assert '"artwork_translated": false' in jsx
        assert '"artwork_rescaled": false' in jsx
        for op in ("resize(", "translate(", "scale("):
            assert op not in jsx, op

    def test_it_removes_extra_artboards(self, jsx):
        assert "while (doc.artboards.length > 1)" in jsx


class TestFinalGatesDeclaredBeforeTheRun:
    """The bar is set now so it cannot be lowered after seeing the result."""

    def test_every_requirement_is_declared_and_unanswered(self):
        assert FINAL["evaluated"] is False
        assert len(FINAL["requirements"]) == 20
        for k, v in FINAL["requirements"].items():
            assert v is None, k
        assert FINAL["a_null_requirement_is_not_a_pass"] is True

    def test_it_names_the_hashes_that_must_not_recur(self):
        h = FINAL["known_hashes_that_must_not_recur"]
        assert h["r2_source"] == R2_SHA
        assert h["artboard_drift_copy"] == DRIFT_SHA

    def test_the_page_size_requirement_is_explicit(self):
        assert FINAL["expected_page_pt"] == [207.1627, 493.2283]
        assert "page_width_pt_is_207_1627" in FINAL["requirements"]
        assert "page_height_pt_is_493_2283" in FINAL["requirements"]


class TestEvidencePreserved:

    def test_the_drift_copy_is_kept_under_its_own_name(self):
        for p in (R.DRIFT_AI, R.DRIFT_PDF, R.DRIFT_PNG):
            assert os.path.exists(p), p
        assert G2.sha256_file(R.DRIFT_AI) == DRIFT_SHA
        assert REC["preserved_evidence"]["overwritten"] is False
        assert REC["preserved_evidence"]["classification"] == [
            "ILLUSTRATOR_ARTWORK_PASSED_ARTBOARD_FAILED",
            "PRESERVED_FOR_AUDIT",
            "NOT_PRODUCTION_AUTHORITY"]

    def test_freeing_the_canonical_names_protected_the_evidence(self):
        """The next run wrote to those names. Had the drift copy still been
        sitting there, this evidence would have been overwritten."""
        for name in ("vq2_a2_r2_final_illustrator_verified.ai",
                     "vq2_a2_r2_final_illustrator_verified.pdf",
                     "vq2_a2_r2_final_illustrator_verified.png"):
            assert os.path.exists(os.path.join(VQ2, name)), name
        assert G2.sha256_file(R.DRIFT_AI) == DRIFT_SHA

    def test_every_earlier_source_is_still_intact(self):
        assert G2.sha256_file(G2.DEFECTIVE)[:16] == "f3707618edf98c87"
        assert G2.sha256_file(G2.R1_AI)[:16] == "0555c9f68d10bbd0"
        assert G2.sha256_file(G2.OUT_AI) == R2_SHA


class TestGateAStillBlocked:

    def test_this_round_trips_own_verdict_still_stands(self):
        """A later round trip passed. This one's failure is not rewritten."""
        assert ST["GATE_A_ROUNDTRIP_1"] == "ARTWORK_PASSED_ARTBOARD_FAILED"
        assert ST["PACKAGING"] == "NOT_STARTED"
        assert REC["gate_a_effect"].startswith("NONE")

    def test_only_gate_a_ever_passed(self):
        assert_only_gate_a_passed(GATES)

    def test_this_partial_pass_was_not_treated_as_evidence(self):
        hist = GATES["gates"]["A_illustrator_execution"]["attempt_history"]
        mine = [h for h in hist if h["n"] == 4][0]
        assert mine["result"] == "ARTWORK_PASSED_ARTBOARD_FAILED"
        assert mine["gate_a_effect"].startswith("NONE")
        assert REC["gate_a_effect"].startswith("NONE")

    def test_the_full_attempt_history_survives(self):
        hist = GATES["gates"]["A_illustrator_execution"]["attempt_history"]
        assert len(hist) == 5
        assert hist[3]["result"] == "ARTWORK_PASSED_ARTBOARD_FAILED"
        for h in hist[:4]:
            assert "PASSED" not in h.get("gate_a_effect", "NONE")

    def test_the_checklist_was_not_ticked_by_this_partial_pass(self):
        """It was answered only after the round trip that actually passed."""
        assert REC["result"] == "ARTWORK_PASSED_ARTBOARD_FAILED"
        assert REC["artboard_failure"]["page_size_drift"] is True

    def test_the_four_artefacts_were_delivered_by_the_next_run(self):
        assert RCP["awaiting"] == []
        assert RCP["roundtrip_passed"] is True

    def test_the_rules_now_exclude_the_drift_copy_and_a_wrong_page(self):
        joined = " ".join(RCP["acceptance_rules"])
        assert DRIFT_SHA in joined
        assert "207.1627 x 493.2283 pt" in joined
        assert "aborted run's record is not provenance" in joined

    def test_nothing_downstream_started(self):
        assert PRE["supplier_requests_sent"] == 0
        assert PRE["packaging_started"] == False   # noqa: E712
        assert PRE["provider_calls"] == 0
        assert PRE["image_generation_calls"] == 0
        assert PRE["accepted_assets_changed"] is False

    def test_this_slice_makes_no_provider_call(self):
        import inspect
        src = inspect.getsource(R)
        for forbidden in ("anthropic", "openai", "requests.post", "httpx",
                          "claude_service", "generate_image", "tavily"):
            assert forbidden not in src, forbidden


class TestBoardShowsBothFindings:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "gatert1", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_artefacts_download(self, client_in):
        for n in ("gate-a-roundtrip1-record", "gate-a-drift-ai",
                  "gate-a-drift-pdf", "gate-a-drift-png",
                  "gate-a-aborted-run", "gate-a-final-gates",
                  "gate-a-roundtrip-jsx"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{n}/").status_code == 200, n

    def test_the_served_script_is_the_corrected_one(self, client_in):
        r = client_in.get("/api/visual-quality/vq1/gate-a-roundtrip-jsx/")
        served = (b"".join(r.streaming_content) if r.streaming else r.content)
        assert served == open(R.JSX, "rb").read()
        assert b"restoreArtboard" in served

    def test_the_page_reports_artwork_passed_and_artboard_failed(
            self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        assert "ARTWORK PASSED, ARTBOARD FAILED" in html
        assert "763.654" in html and "207.1627" in html
        assert "translated, never resized" in html
        assert "defect in the automation" in html

    def test_the_page_reports_the_aborted_run_separately(self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        assert "aborted run" in html
        assert "select the .ai, not the .jsx" in html

    def test_the_page_never_claims_a_supplier_gate_passed(self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        for claim in ("GATE B PASSED", "GATE C PASSED", "GATE D PASSED",
                      "GATE E PASSED", "PRODUCTION_AUTHORITY_GRANTED"):
            assert claim not in html, claim
