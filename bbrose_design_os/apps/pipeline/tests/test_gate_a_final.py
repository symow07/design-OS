"""GATE A — the one gate that passed, and everything it still does not grant.

Gate A is the first pass in this arc, so these tests are deliberately harder
than the ones that recorded failures. Every figure is re-measured from the
returned files; the owner's report is compared against that measurement rather
than trusted as the source of it. The larger half of the file is about what a
Gate A pass must NOT move.
"""
import json
import os

import pytest
from django.conf import settings

from apps.pipeline.services import ai8_color as A
from apps.pipeline.services import gate_a_corr2 as G2
from apps.pipeline.services import gate_a_final as F

VQ2 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
PA = os.path.join(settings.BASE_DIR, "docs", "production_authority")
J = lambda d, n: json.load(open(os.path.join(d, n)))                  # noqa

REC = J(VQ2, "gate_a_final_verification.json")
RECON = J(VQ2, "illustrator_execution_verification_result_reconciliation.json")
RESULT = J(VQ2, "illustrator_execution_verification_result.json")
GATES = J(PA, "production_authority_gate.json")
RCP = J(PA, "illustrator_execution_verification_receipts.json")
IEV = J(PA, "illustrator_execution_verification_checklist.json")
PRE = J(PA, "production_authority_preflight.json")
ST = J(VQ2, "vq2_state.json")

R2_SHA = "6ae00f726ddefda4adad93325735c489e3fe987452f9c1a2f603236c73e4c49a"
DRIFT_SHA = \
    "547f55b8f6a71e9b85236d185b0fdc977497374ebf96fc50339388c8660967c0"
APPROVED = {"#D9BDB5", "#705242", "#493034", "#502525"}


@pytest.fixture(scope="module")
def measured():
    return F.measure_verified()


class TestVerifiedPackageIdentity:

    def test_all_four_hashes_match_the_owner_report(self):
        for key, path in (("ai", F.VERIFIED_AI), ("pdf", F.VERIFIED_PDF),
                          ("png", F.VERIFIED_PNG), ("json", F.RESULT_JSON)):
            assert G2.sha256_file(path) == F.REPORTED[key], key

    def test_the_verified_ai_differs_from_the_r2_source(self):
        assert G2.sha256_file(F.VERIFIED_AI) != R2_SHA
        assert REC["checks"]["differs_from_r2_source"] is True

    def test_the_verified_ai_differs_from_the_oversized_copy(self):
        assert G2.sha256_file(F.VERIFIED_AI) != DRIFT_SHA
        assert REC["checks"]["differs_from_artboard_drift_copy"] is True

    def test_the_r2_source_was_not_modified_by_the_run(self):
        assert G2.sha256_file(G2.OUT_AI) == R2_SHA
        assert RESULT["source_unmodified"] is True
        assert RESULT["source_size_before"] == RESULT["source_size_after"]

    def test_it_is_a_native_illustrator_document(self):
        assert open(F.VERIFIED_AI, "rb").read(4) == b"%PDF"


class TestArtboardPreserved:

    def test_the_artboard_is_the_accepted_page(self, measured):
        w, h = measured["artboard_pt"]
        assert abs(w - 207.1627) <= F.PAGE_TOLERANCE_PT, w
        assert abs(h - 493.2283) <= F.PAGE_TOLERANCE_PT, h

    def test_the_deviation_is_recorded_not_rounded_away(self):
        """The measured page is a few ten-thousandths off nominal. Reporting
        the nominal figure instead would be a small lie in the one record that
        certifies the gate."""
        a = REC["artboard"]
        assert a["measured_pt"] == [207.162994, 493.227997]
        assert a["nominal_pt"] == [207.1627, 493.2283]
        assert a["deviation_pt"] != [0.0, 0.0]
        assert a["within_tolerance"] is True

    def test_there_is_exactly_one_artboard(self, measured):
        assert measured["pages"] == 1
        assert REC["artboard"]["artboards"] == 1

    def test_no_oversized_white_margin_drift(self, measured):
        """The previous round trip returned 763.654 x 983.225."""
        w, h = measured["artboard_pt"]
        assert w < 300 and h < 600
        assert REC["artboard"]["no_oversized_white_margin_drift"] is True

    def test_the_script_recorded_the_artboard_surviving_the_reopen(self):
        ab = RESULT["artboard_after_reopen"]
        assert ab["width_ok"] is True and ab["height_ok"] is True
        assert RESULT["artboard_restore"]["passed"] is True


class TestStructureAndReconciliation:

    def test_forty_logical_vector_drawings(self, measured):
        assert measured["drawings"] == 40
        assert measured["filled"] == 39
        assert measured["stroked"] == 1

    def test_sixty_seven_path_items_are_not_missing_artwork(self):
        """Illustrator counts path items; a compound path is one drawing and
        several items. The two inventories reconcile exactly."""
        assert RESULT["object_count"] == 67
        assert RECON["path_items_reported_by_illustrator"] == 67
        assert RECON["logical_drawing_objects"] == 40
        assert RECON["reconciles_exactly"] is True

    def test_the_reconciliation_is_derived_from_the_source_not_asserted(self):
        doc = A.parse_eps_r2(open(G2.OUT_AI).read())
        objs = list(doc.objects())
        subpaths = sum(1 for o in objs for op, _ in o.subpaths() if op == "m")
        assert len(objs) == 40
        assert subpaths == 67
        assert RECON["extra_subpaths_beyond_one_each"] == 27
        assert RECON["compound_objects"] == 18

    def test_the_false_flag_is_owned_not_blamed_on_illustrator(self):
        assert RESULT["all_paths_arrived"] is False
        assert RECON["submitted_flag"]["value"] is False
        assert RECON["whose_defect"].startswith("mine")
        assert RECON["codes"] == [
            "ILLUSTRATOR_ALL_PATHS_ARRIVED_FALSE_COUNTING_MISMATCH",
            "ILLUSTRATOR_LOGICAL_OBJECTS_AND_PATH_ITEMS_RECONCILED"]

    def test_the_submitted_json_was_not_rewritten(self):
        """Human-run evidence is preserved; the correction sits beside it."""
        assert RECON["submitted_result_preserved_unchanged"] is True
        assert RECON["submitted_result_rewritten"] is False
        assert RECON["this_record_sits_beside_it_not_over_it"] is True
        assert G2.sha256_file(F.RESULT_JSON) == F.REPORTED["json"]
        assert RECON["submitted_result_sha256"] == F.REPORTED["json"]

    def test_the_corrected_semantic_result_is_recorded(self):
        c = RECON["corrected_semantic_result"]
        assert c["all_logical_objects_arrived"] is True
        assert c["no_missing_logo_glyph_divider_or_supporting_copy"] is True
        assert c["no_raster_substitution"] is True
        assert c["no_live_text"] is True

    def test_the_script_no_longer_makes_that_comparison(self):
        jsx = open(G2.JSX).read()
        assert "var EXPECTED_PATH_ITEMS = 67;" in jsx
        assert "all_paths_arrived = (inv.path_items_total === " \
               "EXPECTED_OBJECTS)" not in jsx
        assert "rec.all_logical_objects_arrived" in jsx


class TestColoursAndDivider:

    def test_only_the_four_approved_colours(self, measured):
        seen = set(measured["fill_colours"]) | set(measured["stroke_colours"])
        assert seen == APPROVED
        assert measured["fill_colours"] == {
            "#D9BDB5": 1, "#705242": 1, "#493034": 1, "#502525": 36}
        assert measured["stroke_colours"] == {"#502525": 1}

    def test_the_divider_width_survived(self, measured):
        assert any(abs(v - A.DIVIDER_WIDTH_PT) < 0.001
                   for v in measured["stroke_widths_pt"]), \
            measured["stroke_widths_pt"]

    def test_zero_rasters_and_zero_live_text(self, measured):
        assert measured["raster_images"] == 0
        assert measured["live_text_characters"] == 0


class TestHumanRunEvidence:

    def test_human_result_is_pass(self):
        assert RESULT["human_result"] == "PASS"

    def test_save_reopen_and_both_exports_completed(self):
        for k in ("save_completed", "reopen_completed",
                  "pdf_export_completed", "png_export_completed"):
            assert RESULT[k] is True, k

    def test_both_human_confirmations_were_fully_answered(self):
        for k in ("first_confirmation", "second_confirmation"):
            answers = RESULT[k]
            assert len(answers) == 9, k
            assert all(answers.values()), k

    def test_no_warning_or_repair_message(self):
        assert RESULT["warning_state"] == "NONE_REPORTED"
        assert RESULT["notes"] == []

    def test_it_was_the_right_subject(self):
        assert RESULT["source_filename"] == "vq2_a2_r2_final_gate_a_r2.ai"
        assert RESULT["verified_filename"] == \
            "vq2_a2_r2_final_illustrator_verified.ai"

    def test_illustrator_version_recorded(self):
        assert RESULT["illustrator_version"] == "30.0.0"
        assert "Macintosh" in RESULT["operating_system"]

    def test_claude_did_not_operate_illustrator(self):
        assert RESULT["claude_operated_illustrator"] is False
        assert RESULT["authorship"]["visual_judgement"] == \
            "HUMAN_VISUAL_CONFIRMATION"


class TestGateAPassed:

    def test_every_independent_check_passed(self):
        assert REC["failed_checks"] == []
        assert REC["all_checks_passed"] is True
        assert len(REC["checks"]) >= 25

    def test_the_ruling_and_its_five_codes(self):
        assert REC["ruling"] == "PASSED"
        assert REC["codes"] == [
            "ILLUSTRATOR_EXECUTION_VERIFICATION_PASSED",
            "PRODUCTION_AUTHORITY_GATE_A_PASSED",
            "ILLUSTRATOR_SAVE_REOPEN_EXPORT_CONFIRMED",
            "ILLUSTRATOR_ARTBOARD_PRESERVED",
            "ILLUSTRATOR_VECTOR_EDITABILITY_CONFIRMED"]

    def test_state_records_the_pass(self):
        assert ST["ILLUSTRATOR_EXECUTION_VERIFICATION"] == "PASSED"
        assert ST["PRODUCTION_AUTHORITY_GATE_A"] == "PASSED"
        assert GATES["gates"]["A_illustrator_execution"]["state"] == "PASSED"
        assert GATES["gates_passed"] == 1
        assert RCP["passed"] is True
        assert IEV["passed"] is True

    def test_the_checklist_is_answered_not_left_null(self):
        for c in IEV["checks"]:
            assert c["result"] == "PASS", c["check"]
        for a in IEV["actions"]:
            assert a["done"] is True, a["action"]

    def test_nothing_is_still_awaited(self):
        assert RCP["awaiting"] == []
        assert RCP["verification_complete"] is True


class TestGateAGrantsNothingElse:
    """The half of this that matters most."""

    def test_four_gates_remain_blocked_with_their_reasons(self):
        assert GATES["gates_remaining_blocked"] == 4
        for key, code in (
                ("B_supplier_geometry", "BLOCKED_PENDING_SUPPLIER_GEOMETRY"),
                ("C_flat_artwork",
                 "BLOCKED_PENDING_PRINT_ZONE_AND_WRAP_EVIDENCE"),
                ("D_colour_separation",
                 "BLOCKED_PENDING_DECORATION_PROCESS_AND_COLOUR_EVIDENCE"),
                ("E_material_specification",
                 "BLOCKED_PENDING_SUPPLIER_MATERIAL_EVIDENCE")):
            g = GATES["gates"][key]
            assert g["state"] == "BLOCKED", key
            assert g["blocked_code"] == code, key
            assert g["evidence_present"] is False, key

    def test_gate_a_does_not_imply_production_authority(self):
        for claim in ("production geometry authority", "supplier compatibility",
                      "print-wrap authority", "colour-separation authority",
                      "material specification", "manufacturability",
                      "packaging authorization"):
            assert claim in REC["gate_a_does_not_grant"], claim
            assert claim in GATES["gate_a_passing_does_not_imply"], claim
        assert REC["gate_a_grants"] == [
            "Illustrator execution verification only"]

    def test_packaging_did_not_start(self):
        assert ST["PACKAGING"] == "NOT_STARTED"
        assert PRE["packaging_started"] is False
        assert GATES["packaging_may_begin_now"] is False

    def test_no_supplier_request_was_sent(self):
        assert PRE["supplier_requests_sent"] == 0
        assert GATES["supplier_requests_sent"] == 0
        drafts = J(PA, "production_supplier_request_drafts.json")
        for d in drafts.get("drafts", []):
            assert d.get("sent") in (False, None), d.get("supplier")
            assert d.get("state") != "SENT", d.get("supplier")

    def test_no_provider_or_image_generation_call(self):
        assert PRE["provider_calls"] == 0
        assert PRE["image_generation_calls"] == 0

    def test_this_slice_makes_no_provider_call(self):
        import inspect
        src = inspect.getsource(F)
        for forbidden in ("anthropic", "openai", "requests.post", "httpx",
                          "claude_service", "generate_image", "tavily"):
            assert forbidden not in src, forbidden

    def test_production_states_still_blocked(self):
        assert ST["PRODUCTION_GEOMETRY"] == "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert ST["PRODUCTION_COLOR_SEPARATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert ST["PRODUCTION_MATERIAL_SPECIFICATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"

    def test_no_accepted_artwork_changed(self):
        assert REC["accepted_artwork_modified"] is False
        assert PRE["accepted_assets_changed"] is False
        assert ST["m3_identity"] == "4ecc8e9df1d1"
        assert ST["vq2_a2_r2_final"] == "OWNER_APPROVED_AND_FROZEN"

    def test_no_closed_workstream_reopened(self):
        assert REC["closed_workstreams_reopened"] is False
        assert ST["VQ_1"] == "OWNER_ACCEPTED_AND_CLOSED"
        assert ST["VQ_2_CLOSED"] is True
        assert ST["VQ3_CLOSED"] is True
        assert PRE["workstreams_reopened"] is False


class TestAuditHistoryPreserved:

    def test_every_failed_source_is_still_on_disk_at_its_own_hash(self):
        trail = F.audit_trail_intact()
        assert trail["all_present"] is True
        for row in trail["sources"]:
            assert row["exists"] is True, row["file"]
            assert row["unchanged"] is True, row["file"]

    def test_all_four_stages_are_represented(self):
        stages = [r["stage"] for r in F.audit_trail_intact()["sources"]]
        assert "R0 black-only emission" in stages
        assert "R1 artwork loss" in stages
        assert "round trip 1 oversized artboard" in stages

    def test_the_failure_records_survive_too(self):
        recs = F.audit_trail_intact()["records"]
        for k in ("aborted_run_json", "r1_failure_record",
                  "r2_initial_open_record", "roundtrip_1_record",
                  "drift_pdf", "drift_png"):
            assert recs[k] is True, k

    def test_the_oversized_copy_was_not_overwritten_by_the_good_one(self):
        assert G2.sha256_file(F.DRIFT_AI) == DRIFT_SHA
        assert G2.sha256_file(F.VERIFIED_AI) != DRIFT_SHA


class TestBoardShowsThePassAndTheLimits:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "gateafinal", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_the_api_reports_the_pass_and_the_remaining_gates(self, client_in):
        pa = client_in.get("/api/visual-quality/vq1/").json()["vq2"][
            "production_authority"]
        assert pa["gate_a_passed"] is True
        assert pa["gates_passed"] == 1
        assert pa["gates_remaining_blocked"] == 4
        assert pa["supplier_requests_sent"] == 0
        assert pa["packaging_may_begin_now"] is False
        # the outstanding action has moved on twice: authorize, then resolve
        # destinations, now send. It must never read as already sent.
        # supplier outreach is deferred; the roadmap has moved to B4a. What
        # must not change is that no gate passed on the back of it.
        # §BH46: the action names the spec pack's missing items, and those
        # items name supplier documents by their own requires text; what the
        # action may never carry is an outreach verb
        for verb in ("SEND", "REQUEST", "CONTACT", "EMAIL", "WRITE TO"):
            assert verb not in pa["next_required_owner_action"].upper(), verb
        assert pa["next_required_owner_action"].startswith("place the spec pack")
        assert pa["supplier_requests_sent"] == 0

    def test_the_page_states_the_pass(self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        assert "GATE A PASSED" in html
        assert "40 logical drawings / 67 path items" in html
        assert "207.162994" in html

    def test_the_page_states_what_gate_a_does_not_grant(self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        assert "remain BLOCKED" in html
        assert "manufacturability" in html
        assert "packaging authorization" in html
        assert "READY FOR YOU TO SEND" in html
        assert "0 of 5 sent" in html

    def test_the_verified_package_downloads(self, client_in):
        for n in ("gate-a-verified-ai", "gate-a-verified-pdf",
                  "gate-a-verified-png", "gate-a-verified-result",
                  "gate-a-final-verification", "gate-a-reconciliation"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{n}/").status_code == 200, n

    def test_served_bytes_match_the_repo(self, client_in):
        for name, path in (("gate-a-verified-ai", F.VERIFIED_AI),
                           ("gate-a-verified-result", F.RESULT_JSON)):
            r = client_in.get(f"/api/visual-quality/vq1/{name}/")
            served = (b"".join(r.streaming_content) if r.streaming
                      else r.content)
            assert served == open(path, "rb").read(), name

    def test_the_page_never_claims_a_later_gate_passed(self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        for claim in ("GATE B PASSED", "GATE C PASSED", "GATE D PASSED",
                      "GATE E PASSED", "PRODUCTION_AUTHORITY_GRANTED",
                      "PACKAGING STARTED"):
            assert claim not in html, claim


class TestTheRecordsForwardPointerIsHistory:
    """§BH46(e): the record keeps its own next action and says, beside it,
    where the live one is read."""

    def test_the_superseding_pointer_is_derived_and_on_disk(self):
        for r in (F.record(write=False), REC):
            assert r["next_required_owner_action"] == \
                "AUTHORIZE SUPPLIER EVIDENCE REQUESTS"          # history, kept
            after = r["next_required_owner_action_superseded_by"]
            assert after.startswith("§BH46")
            assert "place the spec pack" in after
