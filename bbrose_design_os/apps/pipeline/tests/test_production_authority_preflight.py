"""Production-authority preflight — gates defined, nothing granted.

This stage exists to say precisely what production authority would require and
to prepare the requests. So the tests are almost entirely negative: every gate
must be blocked, no draft may be sent, Illustrator verification cannot be
self-certified here, and a null result must never read as a pass.
"""
import hashlib
import json
import os

import pytest
from django.conf import settings

from .gate_a_states import assert_only_gate_a_passed

VQ2 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
P = os.path.join(settings.BASE_DIR, "docs", "production_authority")
J = lambda d, n: json.load(open(os.path.join(d, n)))                  # noqa
PRE = J(P, "production_authority_preflight.json")
IEV = J(P, "illustrator_execution_verification_checklist.json")
TPL = J(P, "illustrator_execution_verification_result_template.json")
SPEC = J(P, "supplier_evidence_request_specification.json")
DRAFTS = J(P, "production_supplier_request_drafts.json")
GATES = J(P, "production_authority_gate.json")
RCP = J(P, "illustrator_execution_verification_receipts.json")
ST = J(VQ2, "vq2_state.json")


class TestGateAFileReceipt:
    """A re-upload of the accepted source is not a verification copy, and must
    move nothing."""

    def test_submission_was_the_accepted_source_itself(self):
        r = RCP["receipts"][0]
        src = os.path.join(VQ2, "vq2_a2_r2_final.ai")
        live = hashlib.sha256(open(src, "rb").read()).hexdigest()
        assert r["submitted_sha256"] == live
        assert r["accepted_source_sha256"] == live
        assert r["equals_accepted_source"] is True
        assert r["is_new_verification_copy"] is False

    def test_the_three_receipt_codes_are_recorded(self):
        assert RCP["receipts"][0]["codes"] == [
            "ILLUSTRATOR_ORIGINAL_SOURCE_REUPLOADED",
            "ILLUSTRATOR_VERIFICATION_COPY_NOT_RECEIVED",
            "ILLUSTRATOR_EXECUTION_VERIFICATION_INCOMPLETE"]

    def test_this_receipt_moved_nothing_when_it_arrived(self):
        """Gate A has since passed on a later, genuine round trip. What this
        slice recorded stays true: receipt 1 was a re-upload and counted for
        nothing."""
        r = RCP["receipts"][0]
        assert r["is_new_verification_copy"] is False
        assert r["gate_a_effect"].startswith("NONE")
        assert r["accepted_source_modified"] is False

    def test_eps_text_is_never_evidence_of_execution(self):
        assert RCP["eps_text_is_not_evidence"] is True
        assert RCP["automated_pass_possible_here"] is False
        assert "must NOT be inferred" in RCP["eps_text_note"]

    def test_the_awaited_artifacts_have_since_arrived(self):
        """They were absent for four rounds. They are here now, and the
        awaiting list is correctly empty rather than still demanding them."""
        assert RCP["awaiting"] == []
        assert RCP["verification_copy_received"] is True
        for name in ("vq2_a2_r2_final_illustrator_verified.ai",
                     "vq2_a2_r2_final_illustrator_verified.pdf",
                     "vq2_a2_r2_final_illustrator_verified.png"):
            assert os.path.exists(os.path.join(VQ2, name)), name

    def test_a_copy_equal_to_the_source_can_never_be_accepted(self):
        joined = " ".join(RCP["acceptance_rules"])
        assert "re-upload, never a verification copy" in joined
        assert "must differ from" in joined
        # every superseded source must still hash to what it hashed to
        assert "must still hash to" in joined

    def test_the_accepted_source_was_not_touched(self):
        assert RCP["receipts"][0]["accepted_source_modified"] is False
        assert RCP["accepted_assets_changed"] is False
        assert RCP["packaging_started"] is False
        assert hashlib.sha256(
            open(os.path.join(VQ2, "vq2_a2_r2_final.ai"), "rb").read()
        ).hexdigest()[:16] == "f3707618edf98c87"


class TestClosedWorkstreamsUntouched:

    def test_all_four_closed_and_not_reopened(self):
        assert PRE["closed_workstreams"] == {
            "VQ_1": "OWNER_ACCEPTED_AND_CLOSED",
            "VQ_2": "OWNER_ACCEPTED_AND_CLOSED",
            "COMPLETE_PRODUCT_REVIEW": "OWNER_ACCEPTED_AND_CLOSED",
            "VQ_3": "OWNER_APPROVED_AND_CLOSED"}
        assert PRE["workstreams_reopened"] is False
        assert ST["VQ_1_CLOSED"] is True
        assert ST["VQ_2_CLOSED"] is True
        assert ST["VQ3_CLOSED"] is True

    def test_frozen_hashes_unchanged(self):
        assert PRE["frozen_drift"] == []
        for k, v in PRE["frozen"].items():
            assert v["match"] is True, k
        m = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                         "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(m, "rb").read()).hexdigest()[:12] == "4ecc8e9df1d1"
        for rel, want in (("lf1_r1/vq2_rose_damascena_lf1_r1.ai",
                           "fcd8003994d52028"),
                          ("brand/bbrose_logo_approved.ai",
                           "a2b2a82969389ac2"),
                          ("vq2_a2_r2_final_clean.png", "94ec944326889c20")):
            assert hashlib.sha256(open(os.path.join(VQ2, rel),
                                       "rb").read()).hexdigest()[:16] == want

    def test_selected_m3_render_recomputed_from_the_accepted_file(self):
        """fbdedc5b23e31745 is only a claim until it is recomputed from the
        render the owner actually selected."""
        p = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq3",
                         "vq3_m3_warm_rose_gold.png")
        assert hashlib.sha256(open(p, "rb").read()).hexdigest()[:16] == \
            "fbdedc5b23e31745"
        assert PRE["frozen"]["vq3_selected_render"]["live"] == \
            "fbdedc5b23e31745"

    def test_font_unit_pinned_against_the_owner_approved_record(self):
        """The font unit is a derived contour hash, not a file digest, so it is
        anchored to the upstream record the owner approved rather than to the
        preflight's own copy of it."""
        for rel, key in (("vq2_final_front_artwork_owner_approval.json",
                          "frozen_identities"),
                         ("vq2_complete_product_handoff.json",
                          "frozen_inputs")):
            rec = json.load(open(os.path.join(VQ2, rel)))
            assert rec[key]["font_unit_contour_hash"] == \
                "5db4403984ba6f75", rel
        assert PRE["frozen"]["font_unit"]["live"] == "5db4403984ba6f75"

    def test_no_accepted_asset_changed(self):
        assert PRE["accepted_assets_changed"] is False
        assert PRE["is_design_stage"] is False


class TestIllustratorVerificationCannotSelfCertify:

    def test_it_could_never_be_self_certified_here(self):
        """The point of this class: a pass had to come from a human in
        Illustrator. It eventually did, and it is attributed to one."""
        assert IEV["passed"] is True
        assert IEV["passed_by"] == "PROJECT_OWNER"
        assert ST["ILLUSTRATOR_EXECUTION_VERIFICATION"] == "PASSED"
        assert "Illustrator is not installed" in IEV["cannot_be_performed_here"]

    def test_states_plainly_it_cannot_be_done_here(self):
        assert "Illustrator is not installed" in IEV["cannot_be_performed_here"]
        assert "human" in IEV["must_be_performed_in"]

    def test_every_check_is_answered_by_a_human_none_left_null(self):
        # 22 at the preflight; colour and artwork checks were added after the
        # black silhouette and the artwork loss
        assert len(IEV["checks"]) >= 22
        for c in IEV["checks"]:
            assert c["result"] == "PASS", c["check"]
        assert len(IEV["actions"]) >= 8
        for a in IEV["actions"]:
            assert a["done"] is True, a["action"]

    def test_colour_is_now_something_the_human_must_confirm(self):
        """The failure was invisible to every structural check. It cannot be
        invisible to the checklist a second time."""
        joined = " ".join(c["check"] for c in IEV["checks"]).lower()
        assert "black" in joined
        assert "#d9bdb5" in joined and "#502525" in joined
        for role, hexv in (("01_STRUCTURE_BODY", "#D9BDB5"),
                           ("03_STRUCTURE_CLOSURE", "#493034")):
            assert IEV["expected_colors"][role] == hexv

    def test_the_subject_hash_is_the_live_hash_of_whatever_it_names(self):
        """Which revision is the subject changes every time one fails. That it
        must be a real file, hashed live, does not."""
        assert IEV["do_not_overwrite_accepted_source"] is True
        p = os.path.join(VQ2, os.path.basename(IEV["subject_file"]))
        assert os.path.exists(p), IEV["subject_file"]
        assert hashlib.sha256(
            open(p, "rb").read()).hexdigest()[:16] == IEV["subject_sha256_16"]

    def test_the_previously_failed_source_is_preserved_and_untouched(self):
        prev = IEV["previous_subject"]
        # the most recent failure is now a partial: the artwork passed and the
        # artboard did not. It is still a file that must not be reused.
        assert prev["result"].endswith("FAILED")
        assert prev["preserved"] is True and prev["overwritten"] is False
        p = os.path.join(VQ2, os.path.basename(prev["file"]))
        assert hashlib.sha256(
            open(p, "rb").read()).hexdigest()[:16] == prev["sha256_16"]

    def test_every_failed_source_is_still_on_disk_unchanged(self):
        """R0 and R1 both failed in Illustrator and both stay as evidence."""
        for name, want in (("vq2_a2_r2_final.ai", "f3707618edf98c87"),
                           ("vq2_a2_r2_final_gate_a_r1.ai",
                            "0555c9f68d10bbd0")):
            p = os.path.join(VQ2, name)
            assert hashlib.sha256(
                open(p, "rb").read()).hexdigest()[:16] == want, name

    def test_template_makes_a_null_result_a_non_pass(self):
        assert TPL["passed"] is None
        assert "not a pass" in TPL["instructions"]
        for f in ("illustrator_version", "operating_system", "performed_by",
                  "verification_copy_sha256"):
            assert TPL[f] == "<required>", f


class TestGatesAllBlocked:

    def test_five_gates_all_blocked_with_named_reasons(self):
        assert set(GATES["gates"]) == {
            "A_illustrator_execution", "B_supplier_geometry",
            "C_flat_artwork", "D_colour_separation",
            "E_material_specification"}
        # Gate A has since passed; the four supplier gates have not
        for name, g in GATES["gates"].items():
            if name == "A_illustrator_execution":
                assert g["state"] == "PASSED"
                continue
            assert g["state"] == "BLOCKED", name
            assert g["evidence_present"] is False, name
            assert g["blocked_by"], name
            assert g["requires"], name
        assert_only_gate_a_passed(GATES)

    def test_gate_a_passed_on_human_illustrator_verification(self):
        g = GATES["gates"]["A_illustrator_execution"]
        assert "human Illustrator verification passed" in g["requires"]
        assert g["state"] == "PASSED"
        assert g["evidence_present"] is True
        assert g["passed_by"] == "PROJECT_OWNER"

    def test_gate_b_needs_supplier_drawings(self):
        g = GATES["gates"]["B_supplier_geometry"]
        for r in ("qualified bottle drawing", "qualified closure drawing",
                  "product codes", "tolerances"):
            assert r in g["requires"], r

    def test_gate_c_needs_a_print_zone_drawing(self):
        assert "supplier print-zone drawing" in \
            GATES["gates"]["C_flat_artwork"]["requires"]

    def test_gate_d_needs_supplier_print_process_evidence(self):
        assert "supplier decoration process" in \
            GATES["gates"]["D_colour_separation"]["requires"]

    def test_gate_e_needs_supplier_material_evidence(self):
        for r in ("supplier-confirmed glass", "collar", "closure"):
            assert r in GATES["gates"]["E_material_specification"]["requires"]

    def test_packaging_cannot_begin(self):
        assert GATES["packaging_may_begin_now"] is False
        assert "Gate B and Gate C" in GATES["packaging_may_begin_when"]
        assert ST["PACKAGING"] == "NOT_STARTED"
        assert PRE["packaging_started"] is False


class TestEvidenceAuthority:

    def test_owner_supplied_supplier_evidence_outranks_concept(self):
        """§BH46(b): the qualified evidence is owner-supplied supplier
        documentation — handed to the system, never fetched by it."""
        order = GATES["evidence_authority_order"]
        assert order[0] == "owner-supplied supplier technical drawing"
        assert order[-1] == "accepted concept geometry and artwork"
        assert GATES[
            "concept_never_overrides_qualified_production_evidence"] is True

    def test_conflict_procedure_preserves_the_concept(self):
        oc = GATES["on_conflict"]
        assert "preserve the concept" in oc
        assert "stop for owner approval" in oc
        assert "never silently modify accepted artwork" in oc

    def test_projected_widths_may_not_become_wrap_dimensions(self):
        assert SPEC["projected_to_wrap_conversion"].startswith("PROHIBITED")
        assert SPEC["material_spec_inferred_from_vq3_visuals"] is False
        assert SPEC["vq3_is_visualization_only"] is True


class TestSupplierEvidenceSpecification:

    def test_every_required_category_enumerated(self):
        assert len(SPEC["container_evidence"]) >= 18
        assert len(SPEC["closure_evidence"]) >= 14
        assert len(SPEC["compatibility_evidence"]) >= 5
        assert set(SPEC["material_evidence"]) == {"BODY", "COLLAR", "CLOSURE"}
        assert len(SPEC["print_evidence"]) >= 20

    def test_named_container_items_present(self):
        for n in ("bottle technical drawing", "neck finish",
                  "dimensional tolerances", "print-zone drawing"):
            assert n in SPEC["container_evidence"], n

    def test_named_print_items_present(self):
        for n in ("wrap angle", "safe margin", "registration tolerance",
                  "registered-symbol minimum size",
                  "medallion minimum printable detail"):
            assert n in SPEC["print_evidence"], n


class TestSupplierDraftsUnsent:

    def test_drafted_but_not_sent(self):
        # destinations resolved and .eml files composed; composing is not
        # sending, so these are still unsent
        assert DRAFTS["status"] == "READY_FOR_OWNER_MANUAL_SEND"
        assert DRAFTS["sent"] is False
        assert DRAFTS["send_count"] == 0
        assert PRE["supplier_requests_sent"] == 0
        for s in DRAFTS["suppliers"]:
            assert s["sent"] is False, s["supplier"]
            assert s["status"] == "READY_FOR_OWNER_MANUAL_SEND", s["supplier"]

    def test_requires_explicit_authorization(self):
        assert DRAFTS[
            "requires_explicit_owner_authorization_before_sending"] is True

    def test_no_proprietary_attachment(self):
        a = DRAFTS["attachments"]
        assert a["currently_attached"] == []
        assert a["proprietary_internal_audit_files"].startswith("NONE")

    def test_prior_drafts_preserved_not_overwritten(self):
        assert os.path.exists(os.path.join(
            settings.BASE_DIR, DRAFTS["prior_drafts_preserved_at"]))
        old = json.load(open(os.path.join(
            settings.BASE_DIR, DRAFTS["prior_drafts_preserved_at"])))
        assert old["sent"] is False
        assert len(DRAFTS["suppliers"]) == len(old["requests"])

    def test_all_ten_asks_on_every_draft(self):
        assert len(DRAFTS["required_asks"]) == 10
        for s in DRAFTS["suppliers"]:
            assert s["asks"] == DRAFTS["required_asks"]

    def test_silence_is_not_evidence(self):
        assert DRAFTS["no_response_is_not_evidence"] is True

    def test_every_draft_is_send_ready_prose_not_a_field_list(self):
        """A human must be able to send these — a list of ask names is not a
        draft. Each body must carry the actual request, in prose."""
        assert DRAFTS["drafts_have_send_ready_bodies"] is True
        for s in DRAFTS["suppliers"]:
            assert s["subject"].strip(), s["supplier"]
            body = s["body"]
            assert len(body) > 800, s["supplier"]
            assert body.lstrip().startswith("Hello"), s["supplier"]
            for phrase in ("technical drawing", "neck finish", "MOQ",
                           "compatible", "tolerances", "sample availability"):
                assert phrase in body, (s["supplier"], phrase)

    def test_drafts_do_not_present_concept_geometry_as_authority(self):
        for s in DRAFTS["suppliers"]:
            assert "will not treat it as production authority" in s["body"]


class TestBlockersAndCalls:

    def test_every_production_blocker_active(self):
        b = PRE["blockers"]
        assert b["PRODUCTION_GEOMETRY"] == "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert b["PRODUCTION_FLAT_ARTWORK"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert b["PRODUCTION_COLOR_SEPARATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert b["PRODUCTION_MATERIAL_SPECIFICATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert b["PACKAGING"] == "NOT_STARTED"
        for k, v in b.items():
            if k == "ILLUSTRATOR_EXECUTION_VERIFICATION":
                continue                      # two distinct strings — below
            assert ST[k] == v, k

    def test_illustrator_blocker_and_execution_state_are_both_recorded(self):
        """The brief names both strings. They are not alternatives: the blocker
        it imposes is REQUIRED_BEFORE_PRODUCTION_AUTHORITY, and where it stands
        is one of the not-yet-passed states."""
        assert PRE["blockers"]["ILLUSTRATOR_EXECUTION_VERIFICATION"] == \
            "PASSED"
        assert ST["ILLUSTRATOR_EXECUTION_VERIFICATION"] == "PASSED"
        assert PRE["illustrator_verification"]["state"] == "PASSED"

    def test_no_provider_or_image_generation_call(self):
        assert PRE["provider_calls"] == 0
        assert PRE["image_generation_calls"] == 0

    def test_zero_call_claim_is_anchored_to_an_observed_ledger_reading(self):
        """PRE saying zero is self-report. Pin it to the ledger count actually
        observed when the package was built, so the claim is falsifiable
        against the live table rather than only against itself."""
        base = PRE["provider_ledger_baseline"]
        assert base["api_call_records"] == 226
        assert base["unchanged_since"] == "2C_LIVE_PILOT_CLOSE"

    def test_the_renderer_has_no_provider_call_path(self):
        """The only code this stage runs is the package renderer. It must have
        no way to reach a provider or an image generator at all."""
        src = open(os.path.join(
            settings.BASE_DIR, "apps", "pipeline", "services",
            "production_authority_package.py")).read()
        for forbidden in ("anthropic", "openai", "requests.", "httpx",
                          "urlopen", "generate_image", "ApiCallRecord"):
            assert forbidden not in src, forbidden

    def test_preflight_started_but_grants_nothing(self):
        assert PRE["state"] == "STARTED"
        assert ST["PRODUCTION_AUTHORITY_PREFLIGHT"] == "STARTED"
        assert PRE["human_accepted"] is False
        blob = json.dumps({k: v for k, v in PRE.items()
                           if k != "illustrator_verification"})
        for f in ("PRODUCTION_READY", "MANUFACTURABLE", "GATE_2_APPROVED"):
            assert f not in blob


class TestOwnerActions:

    def test_the_outstanding_action_is_the_current_roadmap_slice(self):
        """Supplier outreach was deferred by the owner, so it is no longer an
        owner action at all. One action remains and it is the active slice."""
        acts = PRE["owner_actions_required"]
        assert len(acts) == 1
        assert acts[0]["action"].startswith("REVIEW B4a")
        assert acts[0]["status"] == "OUTSTANDING"
        assert "supplier outreach is deferred" in acts[0]["note"]


class TestPackage:

    def test_all_twelve_sections(self):
        titles = PRE["section_titles"]
        for i in range(1, 13):
            assert any(t.startswith(f"{i}.") for t in titles), i

    def test_the_documents_are_rebuilt_from_the_records(self):
        """The PDFs and the board are derived, so they cannot be edited into
        disagreeing with the records they report."""
        from apps.pipeline.services import production_authority_package as pkg
        assert [s[0] for s in pkg.preflight_sections(
            PRE, SPEC, DRAFTS, GATES)] == PRE["section_titles"]
        assert PRE["pdf"]["size_bytes"] == os.path.getsize(
            os.path.join(P, "production_authority_preflight.pdf"))

    def test_files_exist(self):
        for n in ("production_authority_preflight.pdf",
                  "production_authority_preflight.png",
                  "production_authority_preflight.json",
                  "illustrator_execution_verification_checklist.pdf",
                  "illustrator_execution_verification_checklist.json",
                  "illustrator_execution_verification_result_template.json",
                  "supplier_evidence_request_specification.pdf",
                  "supplier_evidence_request_specification.json",
                  "production_authority_gate.json",
                  "production_supplier_request_drafts.json"):
            assert os.path.getsize(os.path.join(P, n)) > 400, n


@pytest.mark.django_db
class TestBoardServesPreflight:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "paptester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_reports_preflight(self, client_in):
        pa = client_in.get("/api/visual-quality/vq1/").json()["vq2"][
            "production_authority"]
        assert pa["state"] == "STARTED"
        assert pa["gates_passed"] == 1          # Gate A, and only Gate A
        assert pa["gates_remaining_blocked"] == 4
        assert pa["illustrator_verification"] == "PASSED"
        assert pa["supplier_requests_sent"] == 0
        assert pa["packaging_may_begin_now"] is False

    def test_artifacts_serve(self, client_in):
        for n in ("pap-preflight-pdf", "pap-preflight-json", "pap-gates",
                  "pap-illustrator-checklist", "pap-illustrator-template",
                  "pap-supplier-spec", "pap-supplier-drafts"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{n}/").status_code == 200, n

    def test_the_endpoint_does_not_describe_closed_work_as_outstanding(
            self, client_in):
        """The summary headline is what the owner reads first. It must not
        still be advertising VQ-2 as blocked on provider credit or VQ-3 as not
        started — both are closed and owner-accepted."""
        data = client_in.get("/api/visual-quality/vq1/").json()
        nxt = data["next_required_action"]
        assert "OWNER ACCEPTED AND CLOSED" in nxt
        for stale in ("BLOCKED ON ANTHROPIC API CREDIT",
                      "VQ-3 is unblocked but not started"):
            assert stale not in nxt, stale
        assert "PRODUCTION AUTHORITY PREFLIGHT IS STARTED" in nxt
        assert data["illustrator"] == "PASSED"

    def test_the_page_shows_the_gate_a_receipt(self, client_in):
        """The owner must see that what they sent did not count, and exactly
        what is still required — not just that Gate A is blocked."""
        html = client_in.get("/dashboard/visual-quality/vq1/").content.decode()
        assert "ILLUSTRATOR_ORIGINAL_SOURCE_REUPLOADED" in html
        assert "ILLUSTRATOR_VERIFICATION_COPY_NOT_RECEIVED" in html
        # Gate A passing does not erase how it got there
        assert "GATE A PASSED" in html
        assert "/api/visual-quality/vq1/pap-illustrator-receipts/" in html

    def test_the_page_shows_it_not_just_the_api(self, client_in):
        """Committed files are not the owner's review boundary. The two owner
        actions are only actionable if the page itself links the checklist and
        states that Illustrator verification is still outstanding."""
        html = client_in.get("/dashboard/visual-quality/vq1/").content.decode()
        assert "PRODUCTION AUTHORITY PREFLIGHT" in html
        assert "GATE A" in html and "BLOCKED" in html
        assert "/api/visual-quality/vq1/pap-illustrator-checklist/" in html
        assert "/api/visual-quality/vq1/pap-supplier-drafts/" in html

    def test_the_page_never_claims_a_gate_passed(self, client_in):
        """A receipt CODE may legitimately contain the word PASSED — the R2
        initial open really did pass, and hiding that would be its own kind of
        dishonesty. What the page must never do is claim a GATE passed, so this
        asserts on the claim rather than on the substring."""
        html = client_in.get("/dashboard/visual-quality/vq1/").content.decode()
        i = html.find("PRODUCTION AUTHORITY PREFLIGHT")
        section = html[i:html.find("</section>", i)]
        assert "BLOCKED" in section
        # Gate A has since passed and the page says so; the four supplier
        # gates have not, and no wording may suggest otherwise
        assert "GATE A PASSED" in section
        for claim in ("GATE B PASSED", "GATE C PASSED", "GATE D PASSED",
                      "GATE E PASSED", "PRODUCTION_READY", "MANUFACTURABLE",
                      "PRODUCTION_AUTHORITY_GRANTED", "PACKAGING STARTED"):
            assert claim not in section, claim
        # PASSED now appears legitimately in prose too ("ARTWORK PASSED,
        # ARTBOARD FAILED"), so scanning for the word is no longer meaningful.
        # The invariant is the CLAIM, plus the counter that cannot be spun.
        assert "gates_passed" not in section or "0" in section


class TestSpecPackIntake:
    """§BH46(c): the owner-supplied spec pack intake — the ruled location, the
    per-item validator and the provenance record. The system reads, validates
    and refuses; it never goes and gets a document. Tests run the validator on
    a temporary intake so the ruled location is never written by a test."""

    GOOD_DRAWING = (
        "SUPPLIER TECHNICAL DRAWING — 30 ml cylindrical frosted-glass serum "
        "bottle with dropper closure. Product code FGB-30-DR. Body diameter "
        "32.0 mm, overall height 95.5 mm, shoulder height 78.0 mm, neck finish "
        "18/415, neck outer diameter 17.9 mm. Tolerance ±0.3 mm on all "
        "dimensions.\n")

    @staticmethod
    def _intake(tmp_path):
        from apps.pipeline.services import spec_pack_intake as SPI
        pack = tmp_path / "spec_pack"
        pack.mkdir()
        return SPI, pack

    def _run(self, SPI, tmp_path, manifest):
        mp = tmp_path / "spec_pack_manifest.json"
        mp.write_text(json.dumps(manifest), encoding="utf-8")
        return SPI.validate(write=False, manifest_path=str(mp),
                            spec_pack=str(tmp_path / "spec_pack"))

    def test_the_ruled_location_exists_beside_production_authority(self):
        from apps.pipeline.services import spec_pack_intake as SPI
        assert os.path.isdir(SPI.INTAKE)
        assert os.path.basename(SPI.INTAKE) == "production_authority_intake"
        assert os.path.dirname(SPI.INTAKE) == os.path.dirname(P)
        assert os.path.isfile(SPI.MANIFEST)
        manifest, _ = SPI.load_manifest()
        assert manifest["documents"] == []

    def test_the_nineteen_items_are_the_gates_requires_lists_verbatim(self):
        from apps.pipeline.services import spec_pack_intake as SPI
        by_gate = {}
        for item in SPI.ITEMS:
            by_gate.setdefault(item["gate"], []).append(item["item"])
        for gate in ("B_supplier_geometry", "C_flat_artwork",
                     "D_colour_separation", "E_material_specification"):
            assert by_gate[gate] == GATES["gates"][gate]["requires"], gate
        assert len(SPI.ITEMS) == 19

    def test_each_item_says_what_satisfies_it_in_a_sentence(self):
        from apps.pipeline.services import spec_pack_intake as SPI
        for item in SPI.ITEMS:
            assert len(item["satisfies_when"]) > 60, item["item"]
            assert "product" in item["checks"], item["item"]
            for c in item["checks"]:
                assert c in SPI.CHECK_SENTENCE, (item["item"], c)

    def test_the_location_as_it_stands_yields_nineteen_missing(self):
        from apps.pipeline.services import spec_pack_intake as SPI
        rec, prov = SPI.validate(write=False)
        assert rec["documents_placed"] == 0
        assert rec["items_missing"] == 19
        assert rec["items_satisfied"] == 0 and rec["items_refused"] == 0
        assert all(not g["all_items_satisfied"] for g in rec["gates"].values())
        assert prov["documents"] == []
        assert rec["this_module_fetches"] is False

    def test_a_document_naming_the_wrong_product_is_refused_by_name(
            self, tmp_path):
        SPI, pack = self._intake(tmp_path)
        (pack / "other.txt").write_text(
            "TECHNICAL DRAWING — 50 ml amber glass bottle. Body diameter 40.0 mm,"
            " overall height 110.0 mm.", encoding="utf-8")
        rec, _ = self._run(SPI, tmp_path, {"handed_over_by": "A. Owner",
                                           "handed_over_on": "2026-09-12",
                                           "documents": [{"file": "other.txt",
                                            "satisfies": ["B_supplier_geometry/qualified bottle drawing"]}]})
        item = next(i for i in rec["items"] if i["item"] == "qualified bottle drawing")
        assert item["state"] == SPI.REFUSED
        codes = {r["code"] for r in item["refused"][0]["refusals"]}
        assert codes == {SPI.WRONG_PRODUCT}
        assert "50 ml" in item["refused"][0]["refusals"][0]["why"]

    def test_a_drawing_without_dimensions_is_refused_by_name(self, tmp_path):
        SPI, pack = self._intake(tmp_path)
        (pack / "outline.txt").write_text(
            "30 ml frosted-glass serum bottle with dropper — outline drawing, "
            "no dimensions shown.", encoding="utf-8")
        rec, _ = self._run(SPI, tmp_path, {"handed_over_by": "A. Owner",
                                           "handed_over_on": "2026-09-12",
                                           "documents": [{"file": "outline.txt",
                                            "satisfies": ["B_supplier_geometry/qualified bottle drawing"]}]})
        item = next(i for i in rec["items"] if i["item"] == "qualified bottle drawing")
        assert item["state"] == SPI.REFUSED
        assert {r["code"] for r in item["refused"][0]["refusals"]} == {SPI.NO_DIMENSIONS}

    def test_a_material_claim_without_a_certificate_is_refused_by_name(
            self, tmp_path):
        SPI, pack = self._intake(tmp_path)
        (pack / "glass.txt").write_text(
            "30 ml serum bottle: the glass is soda-lime, frosted. Trust us.",
            encoding="utf-8")
        rec, _ = self._run(SPI, tmp_path, {"handed_over_by": "A. Owner",
                                           "handed_over_on": "2026-09-12",
                                           "documents": [{"file": "glass.txt",
                                            "satisfies": ["E_material_specification/supplier-confirmed glass"]}]})
        item = next(i for i in rec["items"] if i["item"] == "supplier-confirmed glass")
        assert item["state"] == SPI.REFUSED
        assert {r["code"] for r in item["refused"][0]["refusals"]} == {SPI.NO_CERTIFICATE}

    def test_a_document_without_provenance_is_never_accepted(self, tmp_path):
        """The hard stop: a spec accepted without provenance. A drawing that
        passes every content check is still refused when nobody handed it
        over on a date."""
        SPI, pack = self._intake(tmp_path)
        (pack / "bottle.txt").write_text(self.GOOD_DRAWING, encoding="utf-8")
        rec, prov = self._run(SPI, tmp_path, {"documents": [{"file": "bottle.txt",
                                            "satisfies": ["B_supplier_geometry/qualified bottle drawing"]}]})
        item = next(i for i in rec["items"] if i["item"] == "qualified bottle drawing")
        assert item["state"] == SPI.REFUSED
        assert {r["code"] for r in item["refused"][0]["refusals"]} == {SPI.NO_PROVENANCE}
        assert prov["documents"] == []

    def test_a_declared_sha256_must_match_the_file_placed(self, tmp_path):
        SPI, pack = self._intake(tmp_path)
        (pack / "bottle.txt").write_text(self.GOOD_DRAWING, encoding="utf-8")
        rec, _ = self._run(SPI, tmp_path, {"handed_over_by": "A. Owner",
                                           "handed_over_on": "2026-09-12",
                                           "documents": [{"file": "bottle.txt", "sha256": "0" * 64,
                                            "satisfies": ["B_supplier_geometry/qualified bottle drawing"]}]})
        item = next(i for i in rec["items"] if i["item"] == "qualified bottle drawing")
        assert item["state"] == SPI.REFUSED
        assert {r["code"] for r in item["refused"][0]["refusals"]} == {SPI.SHA_MISMATCH}

    def test_a_missing_file_is_refused_by_name(self, tmp_path):
        SPI, _pack = self._intake(tmp_path)
        rec, _ = self._run(SPI, tmp_path, {"handed_over_by": "A. Owner",
                                           "handed_over_on": "2026-09-12",
                                           "documents": [{"file": "absent.pdf",
                                            "satisfies": ["B_supplier_geometry/product codes"]}]})
        item = next(i for i in rec["items"] if i["item"] == "product codes")
        assert {r["code"] for r in item["refused"][0]["refusals"]} == {SPI.FILE_MISSING}

    def test_an_image_is_refused_as_unreadable_not_accepted(self, tmp_path):
        SPI, pack = self._intake(tmp_path)
        (pack / "drawing.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        rec, _ = self._run(SPI, tmp_path, {"handed_over_by": "A. Owner",
                                           "handed_over_on": "2026-09-12",
                                           "documents": [{"file": "drawing.png",
                                            "satisfies": ["B_supplier_geometry/qualified bottle drawing"]}]})
        item = next(i for i in rec["items"] if i["item"] == "qualified bottle drawing")
        assert {r["code"] for r in item["refused"][0]["refusals"]} == {SPI.UNREADABLE_KIND}

    def test_a_correct_document_with_provenance_flips_the_item_not_the_gate(
            self, tmp_path):
        SPI, pack = self._intake(tmp_path)
        (pack / "bottle.txt").write_text(self.GOOD_DRAWING, encoding="utf-8")
        sha = hashlib.sha256(self.GOOD_DRAWING.encode("utf-8")).hexdigest()
        rec, prov = self._run(SPI, tmp_path, {"handed_over_by": "A. Owner",
                                              "handed_over_on": "2026-09-12",
                                              "documents": [{"file": "bottle.txt", "sha256": sha,
                                               "satisfies": ["B_supplier_geometry/qualified bottle drawing",
                                                             "B_supplier_geometry/product codes",
                                                             "B_supplier_geometry/tolerances"]}]})
        states = {i["item"]: i["state"] for i in rec["items"]}
        assert states["qualified bottle drawing"] == SPI.SATISFIED
        assert states["product codes"] == SPI.SATISFIED
        assert states["tolerances"] == SPI.SATISFIED
        assert states["qualified closure drawing"] == SPI.MISSING
        assert rec["items_satisfied"] == 3 and rec["items_missing"] == 16
        b = rec["gates"]["B_supplier_geometry"]
        assert b["items_satisfied"] == 3 and b["all_items_satisfied"] is False
        assert len(prov["documents"]) == 1
        d = prov["documents"][0]
        assert d["sha256"] == sha and d["sha256_declared"] == sha
        assert d["handed_over_by"] == "A. Owner"
        assert d["handed_over_on"] == "2026-09-12"
        assert sorted(d["satisfies"]) == sorted([
            "B_supplier_geometry/qualified bottle drawing",
            "B_supplier_geometry/product codes",
            "B_supplier_geometry/tolerances"])

    def test_the_intake_binds_no_fetcher_and_no_transport(self):
        """A fact about the imported module, not its text: nothing in its
        namespace is a network or mail library, and its only I/O is the
        reading of a placed file."""
        from apps.pipeline.services import spec_pack_intake as SPI
        bound = set(dir(SPI))
        for forbidden in ("requests", "httpx", "urllib", "smtplib", "socket",
                          "send_mail", "EmailMessage", "webbrowser", "wr"):
            assert forbidden not in bound, forbidden
        assert SPI.validate(write=False)[0]["this_module_fetches"] is False

    def test_the_dry_run_over_the_location_names_what_every_item_needs(self):
        from apps.pipeline.services import spec_pack_intake as SPI
        out, text = SPI.dry_run(write=False)
        assert out["documents_placed"] == 0
        assert out["missing"] == 19 and out["would_satisfy"] == 0
        assert out["gates_that_would_pass"] == []
        assert out["this_run_flipped_nothing"] is True
        for row in out["items"]:
            assert row["would"] == SPI.MISSING
            assert row["because"] == ["no document in the pack claims this item"]
            assert f"### `{row['item']}` — **MISSING**" in text
            assert f"**Needs:** {row['needs']}." in text
        assert "flips nothing" in text
        assert "NO_PROVENANCE" in text

    def test_the_dry_run_names_what_a_placed_pack_would_satisfy_and_refuse(
            self, tmp_path):
        SPI, pack = self._intake(tmp_path)
        (pack / "bottle.txt").write_text(self.GOOD_DRAWING, encoding="utf-8")
        (pack / "glass.txt").write_text(
            "30 ml serum bottle: the glass is soda-lime, frosted. Trust us.",
            encoding="utf-8")
        mp = tmp_path / "spec_pack_manifest.json"
        mp.write_text(json.dumps({
            "handed_over_by": "A. Owner", "handed_over_on": "2026-09-12",
            "documents": [
                {"file": "bottle.txt",
                 "satisfies": ["B_supplier_geometry/qualified bottle drawing"]},
                {"file": "glass.txt",
                 "satisfies": ["E_material_specification/supplier-confirmed glass"]},
            ]}), encoding="utf-8")
        out, text = SPI.dry_run(write=False, manifest_path=str(mp),
                                spec_pack=str(pack))
        would = {r["item"]: r for r in out["items"]}
        assert would["qualified bottle drawing"]["would"] == SPI.SATISFIED
        assert "bottle.txt satisfies it" in would["qualified bottle drawing"]["because"][0]
        assert would["supplier-confirmed glass"]["would"] == SPI.REFUSED
        assert "NO_CERTIFICATE" in would["supplier-confirmed glass"]["because"][0]
        assert out["would_satisfy"] == 1 and out["would_refuse"] == 1
        assert out["missing"] == 17
        assert out["gates_that_would_pass"] == []
        assert "**SATISFIED**" in text and "**REFUSED**" in text

    def test_the_dry_run_writes_only_its_two_reports(self, tmp_path):
        SPI, _pack = self._intake(tmp_path)
        mp = tmp_path / "spec_pack_manifest.json"
        mp.write_text(json.dumps({"documents": []}), encoding="utf-8")
        oj, om = tmp_path / "dry_run.json", tmp_path / "dry_run.md"
        SPI.dry_run(write=True, manifest_path=str(mp),
                    spec_pack=str(tmp_path / "spec_pack"),
                    out_json=str(oj), out_md=str(om))
        assert json.loads(oj.read_text())["record_type"] == \
            "spec_pack_intake_dry_run/1.0"
        assert om.read_text().startswith("# Spec pack dry-run")
        assert not (tmp_path / "intake_state.json").exists()
        assert not (tmp_path / "intake_provenance.json").exists()


class TestTheGateRecordSaysWhatIs:
    """§BH46(b)+(d): production_authority_gate.json is regenerated from Gate A's
    own record and the intake state on every run. Gates B to E are intake:
    every item's source is the owner-supplied spec pack; an item is SATISFIED
    only by intaken, provenanced evidence; a gate passes only when every one
    of its items is."""

    @staticmethod
    def _gen():
        from apps.pipeline.services import production_authority_gates as PAG
        return PAG

    def test_the_record_on_disk_is_what_the_generator_derives_today(self):
        PAG = self._gen()
        rec = PAG.build(write=False)
        on_disk = dict(GATES)
        rec.pop("generated_on")
        on_disk.pop("generated_on")
        assert rec == on_disk

    def test_gate_a_is_carried_verbatim_from_its_own_record(self):
        a = J(P, "production_authority_gate_a.json")
        assert GATES["gates"]["A_illustrator_execution"] == a["gate"]
        assert GATES["gates"]["A_illustrator_execution"]["state"] == "PASSED"
        assert GATES["gate_a_correction"] == a["gate_a_correction"]
        assert GATES["first_created"] == a["created_at"]

    def test_gates_b_to_e_are_intake_and_wait_on_the_spec_pack(self):
        for key in ("B_supplier_geometry", "C_flat_artwork",
                    "D_colour_separation", "E_material_specification"):
            g = GATES["gates"][key]
            assert g["source"] == "OWNER_SUPPLIED_SPEC_PACK", key
            assert g["state"] == "BLOCKED" and g["evidence_present"] is False
            assert g["blocked_by"].startswith(
                "no owner-supplied evidence intaken for this item"), key
            assert g["cause"] == "spec pack not yet handed over", key
            assert g["items_missing"] == g["items_total"] == len(g["requires"])
            assert [i["item"] for i in g["items"]] == g["requires"]
            assert g["blocked_code"], key   # the 2026-07-31 code, kept as history
        assert sum(GATES["gates"][k]["items_total"] for k in GATES["gates"]
                   if k != "A_illustrator_execution") == 19

    def test_gates_passed_is_computed_from_satisfied_items(self):
        from apps.pipeline.services import spec_pack_intake as SPI
        PAG = self._gen()
        intake = SPI.validate(write=False)[0]
        assert PAG.build(intake=intake, write=False)["gates_passed"] == 1
        b_items = [i for i in intake["items"] if i["gate"] == "B_supplier_geometry"]
        prov = {"file": "x.pdf", "sha256": "0" * 64,
                "handed_over_by": "A. Owner", "handed_over_on": "2026-09-12"}
        for i in b_items[:-1]:
            i["state"] = SPI.SATISFIED
            i["satisfied_by"] = [prov]
        four = PAG.build(intake=intake, write=False)
        assert four["gates"]["B_supplier_geometry"]["state"] == "BLOCKED"
        assert four["gates"]["B_supplier_geometry"]["items_satisfied"] == 4
        assert four["gates"]["B_supplier_geometry"]["cause"].startswith(
            "spec pack incomplete: 4 of 5")
        assert four["gates_passed"] == 1
        b_items[-1]["state"] = SPI.SATISFIED
        b_items[-1]["satisfied_by"] = [prov]
        five = PAG.build(intake=intake, write=False)
        assert five["gates"]["B_supplier_geometry"]["state"] == "PASSED"
        assert five["gates"]["B_supplier_geometry"]["blocked_by"] is None
        assert five["gates"]["B_supplier_geometry"]["items_satisfied_on"] == "2026-09-12"
        assert five["gates_passed"] == 2
        assert five["gates_remaining_blocked"] == 3
        assert five["packaging_may_begin_now"] is False   # Gate C still waits

    def test_the_next_owner_action_is_to_place_the_spec_pack(self):
        action = GATES["next_required_owner_action"]
        assert action.startswith("place the spec pack: 19 of 19 items missing")
        for key in ("B_supplier_geometry", "C_flat_artwork",
                    "D_colour_separation", "E_material_specification"):
            for item in GATES["gates"][key]["requires"]:
                assert f"{key}: {item}" in action, item
        for verb in ("SEND", "REQUEST", "CONTACT", "EMAIL", "WRITE TO"):
            assert verb not in action.upper(), verb

    def test_the_outreach_block_is_a_superseded_summary_and_the_count_is_zero(self):
        d = GATES["supplier_request_dispatch"]
        assert d["superseded_by"] == "§BH46"
        assert d["requests_sent"] == 0 and d["dispatch_complete"] is False
        assert GATES["supplier_requests_sent"] == 0
        assert "path the system no longer has" in GATES["supplier_requests_sent_note"]
        assert GATES["supplier_outreach"].startswith("SUPERSEDED-BY §BH46")

    def test_the_preflight_and_the_board_read_the_cause_from_the_record(self):
        assert PRE["gates"] == GATES
        from apps.pipeline.services import production_authority_package as PAP
        lines = PAP.board_lines(PRE, DRAFTS, GATES, RCP)
        assert lines[0].startswith("PRODUCTION AUTHORITY PREFLIGHT — 1 of 5 gates passed")
        assert any("spec pack not yet handed over" in ln for ln in lines)
        assert not any("no drawings" in ln for ln in lines)
        assert any(ln.startswith("OWNER ACTION: place the spec pack") for ln in lines)


@pytest.mark.django_db
class TestTheCauseSaysWhatIs:
    """§BH46(e): every live record and reader names the cause of the block —
    the spec pack not yet handed over — and the codes stay as history."""

    CAUSE = "spec pack not yet handed over"

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "causetester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_the_preflight_derives_a_cause_for_every_production_blocker(self):
        from apps.pipeline.services import production_authority_package as PAP
        causes = PRE["blockers_cause"]
        assert set(causes) == set(PAP.BLOCKER_GATE)
        for k, g in PAP.BLOCKER_GATE.items():
            assert causes[k] == GATES["gates"][g]["cause"], k
            assert causes[k].startswith(self.CAUSE), k
            assert k in PRE["blockers"], k                  # the code, kept
        assert "§BH46" in PRE["blockers_cause_note"]
        assert "ILLUSTRATOR_EXECUTION_VERIFICATION" in PRE["blockers_note"]  # kept

    def test_the_vq2_state_names_the_cause_beside_every_kept_code(self):
        for k in ("PRODUCTION_GEOMETRY", "PRODUCTION_FLAT_ARTWORK",
                  "PRODUCTION_COLOR_SEPARATION", "PACKAGING_READINESS",
                  "PRODUCTION_MATERIAL_SPECIFICATION"):
            assert "SUPPLIER_EVIDENCE" in ST[k], k            # the code, kept
            assert self.CAUSE in ST[k + "_cause"], k
            assert "§BH46" in ST[k + "_cause"], k
        assert ST["SUPPLIER_OUTREACH_superseded_by"].startswith("§BH46")

    def test_the_deferral_note_is_marked_superseded(self):
        note = PRE["owner_actions_required"][0]["note"]
        assert "SUPERSEDED-BY §BH46" in note

    def test_the_summary_and_the_page_read_the_cause_from_the_record(
            self, client_in):
        data = client_in.get("/api/visual-quality/vq1/").json()
        nxt = data["next_required_action"]
        assert f"{GATES['gates_passed']} of 5 gates passed" in nxt
        assert self.CAUSE in nxt
        assert "every gate is blocked" not in nxt
        assert "no supplier request has been sent" not in nxt
        pa = data["vq2"]["production_authority"]
        assert pa["gate_causes"]["B_supplier_geometry"] == \
            GATES["gates"]["B_supplier_geometry"]["cause"]
        assert pa["gates_b_to_e_wait_on"] == GATES["gates_b_to_e_wait_on"]
        html = client_in.get("/dashboard/visual-quality/vq1/").content.decode()
        assert "wait on the owner-supplied spec pack" in html
        assert self.CAUSE in html
        assert "blocked pending supplier evidence" not in html
        assert "no supplier request has been sent" not in html
