"""VQ-3 owner selection — M3 accepted, alternates preserved, closeout pending.

Selection is recorded beside the review, never over it: the rankings and both
inspectors' raw outputs stay byte-identical. The conditional the owner set was
evaluated rather than assumed, and it did not resolve to CLOSED — three §18
deliverables are still outstanding, so the state is PENDING_CLOSEOUT.
"""
import hashlib
import json
import os

import pytest
from django.conf import settings

VQ2 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
W3 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq3")
J = lambda d, n: json.load(open(os.path.join(d, n)))                  # noqa
SEL = J(W3, "vq3_owner_selection.json")
CO = J(W3, "vq3_closeout.json")
REV = J(W3, "vq3_material_review.json")
ST = J(VQ2, "vq2_state.json")


class TestSelection:

    def test_m3_selected_with_codes(self):
        assert SEL["decided_by"] == "PROJECT_OWNER"
        assert SEL["decision"] == "APPROVED"
        assert SEL["selected"] == "M3"
        for c in ("VQ3_OWNER_SELECTED_M3",
                  "VQ3_MATERIAL_CANDIDATE_M3_ACCEPTED", "VQ3_REVIEW_CLOSED",
                  "VQ3_MATERIAL_SELECTION_RESOLVED_BY_OWNER"):
            assert c in SEL["codes"], c
        assert ST["VQ3_SELECTED_CANDIDATE"] == "M3"

    def test_selected_render_hash_is_live(self):
        p = os.path.join(settings.BASE_DIR,
                         REV["candidates"]["M3"]["path"])
        assert hashlib.sha256(
            open(p, "rb").read()).hexdigest()[:16] == \
            SEL["selected_artefact"]["sha256_16"]

    def test_alternates_rejected_but_preserved(self):
        for k in ("M1", "M2"):
            a = SEL["alternates"][k]
            assert a["status"] == "REJECTED_AS_ALTERNATE"
            assert a["preserved_for_audit"] is True
            assert a["deleted"] is False
            p = os.path.join(settings.BASE_DIR, a["path"])
            assert os.path.exists(p), k
            assert hashlib.sha256(
                open(p, "rb").read()).hexdigest()[:16] == a["sha256_16"]

    def test_nothing_regenerated_and_no_m4(self):
        assert SEL["regenerated"] is False
        assert SEL["m4_created"] is False
        assert CO["nothing_regenerated"] is True
        assert not any(n.startswith("vq3_m4") for n in os.listdir(W3))

    def test_no_change_authorized(self):
        assert "NONE" in SEL["authorized_changes"]
        assert SEL["provider_calls"] == 0
        assert SEL["image_generation_calls"] == 0


class TestScopeAndAuthority:

    def test_concept_material_only(self):
        assert SEL["scope"] == "concept-material integration only"
        for x in ("production authority", "packaging", "supplier evidence",
                  "manufacturability", "Pantone", "CMYK"):
            assert x in SEL["scope_excludes"], x

    def test_no_production_authority_granted(self):
        assert SEL["grants_production_authority"] is False
        p = SEL["production_boundary"]
        assert p["PRODUCTION_MATERIAL_SPECIFICATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert p["ILLUSTRATOR_EXECUTION_VERIFICATION"] == \
            "REQUIRED_BEFORE_PRODUCTION_AUTHORITY"

    def test_packaging_and_suppliers_untouched(self):
        assert SEL["packaging_started"] is False
        assert SEL["supplier_requests_sent"] == 0
        assert ST["PACKAGING"] == "NOT_STARTED"
        assert "packaging" in CO["blocked_from"]


class TestInspectionsPreserved:

    def test_rankings_and_outputs_not_rewritten(self):
        ip = SEL["inspections_preserved"]
        assert ip["rewritten"] is False
        assert ip["rankings_rewritten"] is False
        assert ip["rank_order"] == REV["rank_order"]

    def test_raw_output_hashes_still_match(self):
        ip = SEL["inspections_preserved"]["raw_output_hashes"]
        for k in ("M1", "M2", "M3"):
            for s in ("A", "B"):
                raw = REV["inspections"][k][s]["raw_output"]
                assert hashlib.sha256(
                    raw.encode()).hexdigest()[:16] == ip[k][s], (k, s)

    def test_actionable_counts_unchanged(self):
        counts = SEL["inspections_preserved"]["actionable_by_candidate"]
        assert counts["M3"] == 0
        for k in ("M1", "M2", "M3"):
            assert counts[k] == sum(
                REV["inspections"][k][s]["result"]["actionable_defect_count"]
                for s in ("A", "B"))

    def test_selection_did_not_follow_rank_blindly(self):
        """M3 ranked first AND the owner chose it — but the record must show
        the choice was the owner's, not the score's."""
        assert SEL["decided_by"] == "PROJECT_OWNER"
        assert "VQ3_MATERIAL_SELECTION_RESOLVED_BY_OWNER" in SEL["codes"]


class TestCollarIntegration:

    def test_resolved_by_owner_selection(self):
        c = SEL["collar_body_integration"]
        assert c["code"] == "VQ3_COLLAR_BODY_MATERIAL_INTEGRATION_RESOLVED"
        assert c["resolved_by"] == "OWNER_SELECTION_OF_M3"
        assert c["machine_evidence"]


class TestFrozen:

    def test_upstream_hashes_still_live(self):
        f = SEL["frozen"]
        m = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                         "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(m, "rb").read()).hexdigest()[:12] == f["m3"] == "4ecc8e9df1d1"
        assert f["lf1_r1"] == "fcd8003994d52028"
        assert f["font_unit_contour_hash"] == "5db4403984ba6f75"
        assert f["approved_logo"] == "a2b2a82969389ac2"
        assert f["clean_preview"] == "94ec944326889c20"

    def test_vq3_artefacts_frozen_by_hash(self):
        f = SEL["frozen"]
        for rel, want in (("vq3_material_review.pdf", f["vq3_review_pdf"]),
                          ("vq3_material_review.json", f["vq3_review_json"]),
                          ("vq3_material_research.json", f["vq3_research"])):
            p = os.path.join(W3, rel)
            assert hashlib.sha256(
                open(p, "rb").read()).hexdigest()[:16] == want, rel

    def test_masks_frozen(self):
        for n, want in SEL["frozen"]["vq3_masks"].items():
            p = os.path.join(W3, "masks", f"mask_{n.lower()}.png")
            assert hashlib.sha256(
                open(p, "rb").read()).hexdigest()[:16] == want, n

    def test_upstream_workstreams_still_closed(self):
        assert SEL["upstream"] == {
            "VQ_1": "CLOSED", "VQ_2": "CLOSED",
            "COMPLETE_PRODUCT_REVIEW": "OWNER_ACCEPTED_AND_CLOSED"}
        assert ST["VQ_1_CLOSED"] is True
        assert ST["VQ_2_CLOSED"] is True
        assert ST["COMPLETE_PRODUCT_REVIEW"] == "OWNER_ACCEPTED_AND_CLOSED"


class TestCloseoutConditionEvaluated:

    def test_condition_was_evaluated_not_assumed(self):
        ev = SEL["closeout_evaluation"]
        assert ev["further_vq3_tasks_remaining"] == 3
        assert len(ev["items"]) == 3
        for i in ev["items"]:
            assert i["present"] is False
            assert i["missing"]
            assert i["have"]

    def test_state_is_pending_closeout_not_closed(self):
        assert SEL["closeout_evaluation"]["result"] == \
            "VQ3_OWNER_APPROVED_PENDING_CLOSEOUT"
        assert CO["state"] == "VQ3_OWNER_APPROVED_PENDING_CLOSEOUT"

    def test_remaining_items_need_no_regeneration(self):
        assert SEL["closeout_evaluation"]["none_require_regeneration"] is True
        for i in CO["remaining_technical_steps"]:
            assert i["is_regeneration"] is False
        assert "No re-render is needed" in CO["next_action"]

    def test_closeout_record_names_the_accepted_render(self):
        assert CO["selected"] == "M3"
        assert CO["accepted_render_frozen"]["sha256_16"] == \
            SEL["selected_artefact"]["sha256_16"]
        assert set(CO["alternates_preserved"]) == {"M1", "M2"}


@pytest.mark.django_db
class TestBoardShowsSelection:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "vq3seltester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_reports_selection(self, client_in):
        v = client_in.get("/api/visual-quality/vq1/").json()["vq2"]["vq3"]
        assert v["selected"] == "M3"
        # VQ-3 has since closed; this slice's own record holds the state it
        # set, and the outstanding-item count it evaluated
        assert v["human_accepted"] is True
        assert SEL["closeout_evaluation"]["result"] == \
            "VQ3_OWNER_APPROVED_PENDING_CLOSEOUT"
        assert SEL["closeout_evaluation"][
            "further_vq3_tasks_remaining"] == 3
        assert v["grants_production_authority"] is False

    def test_selection_record_serves(self, client_in):
        for n in ("vq3-selection", "vq3-closeout"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{n}/").status_code == 200, n
