"""VQ-2 final front artwork — owner approval, freeze, workstream closure.

Approval is a human act recorded ALONGSIDE the build-time review, never a
rewrite of it: the review record still says human_accepted False because that
was true when it was built. What these tests mostly guard is what approval does
NOT do — it does not touch the artwork, does not confer production authority,
and does not start anything downstream.
"""
import hashlib
import json
import os

import pytest
from django.conf import settings


D = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
J = lambda n: json.load(open(os.path.join(D, n)))                     # noqa
APP = J("vq2_final_front_artwork_owner_approval.json")
REV = J("vq2_a2_r2_final_review.json")
AUD = J("vq2_a2_r2_final_audit.json")
HAND = J("vq2_complete_product_handoff.json")
ST = J("vq2_state.json")


class TestApprovalRecorded:

    def test_decision_and_codes(self):
        assert APP["decided_by"] == "PROJECT_OWNER"
        assert APP["decision"] == "APPROVED"
        for c in ("VQ2_FINAL_FRONT_ARTWORK_OWNER_APPROVED",
                  "VQ2_FINAL_FRONT_ARTWORK_ACCEPTED",
                  "VQ2_WORKSTREAM_CLOSED_IF_NO_FURTHER_VQ2_TASKS_REMAIN"):
            assert c in APP["codes"], c

    def test_approval_names_what_was_actually_looked_at(self):
        art = APP["reviewed_artefact"]
        assert art["path"].endswith("vq2_a2_r2_final_clean.png")
        live = hashlib.sha256(
            open(os.path.join(D, "vq2_a2_r2_final_clean.png"),
                 "rb").read()).hexdigest()[:16]
        assert art["sha256_16"] == live
        assert APP["approval_basis"].startswith("direct owner visual review")

    def test_scope_is_the_composition_only(self):
        assert "COMPOSITION" in APP["scope"]
        for excl in ("Complete Product Review", "packaging integration",
                     "VQ-3 material realization", "production authority",
                     "manufacturability"):
            assert excl in APP["scope_excludes"], excl

    def test_state_updated(self):
        assert ST["VQ_2"] == "VQ2_FINAL_FRONT_ARTWORK_OWNER_APPROVED"
        assert ST["vq2_a2_r2_final"] == "OWNER_APPROVED_AND_FROZEN"
        assert ST["VQ2_FINAL_PREFLIGHT"] == \
            "VQ2_FINAL_PREFLIGHT_TECHNICALLY_PASSED"


class TestAdvisoryNotesPreserved:

    def test_all_three_notes_kept_and_marked_nonblocking(self):
        notes = APP["advisory_notes_nonblocking"]
        assert len(notes) == 3
        for n in notes:
            assert n["blocking"] is False
            assert n["artwork_changed_in_response"] is False
        assert APP["advisory_notes_preserved_verbatim"] is True

    def test_notes_say_what_the_owner_said(self):
        blob = " ".join(n["note"] for n in APP["advisory_notes_nonblocking"])
        assert "schematic" in blob
        assert "collar/body contrast" in blob
        assert "weakest typographic line" in blob


class TestArtworkFrozenNotModified:

    def test_approval_changed_no_artwork(self):
        assert APP["artwork_modified_by_this_approval"] is False

    def test_frozen_identities_still_live(self):
        fi = APP["frozen_identities"]
        assert fi["m3"] == "4ecc8e9df1d1"
        assert fi["lf1_r1"] == "fcd8003994d52028"
        assert fi["font_unit_contour_hash"] == "5db4403984ba6f75"
        m = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                         "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(m, "rb").read()).hexdigest()[:12] == fi["m3"]
        p = os.path.join(D, "lf1_r1", "vq2_rose_damascena_lf1_r1.ai")
        assert hashlib.sha256(
            open(p, "rb").read()).hexdigest()[:16] == fi["lf1_r1"]

    def test_every_frozen_output_matches_its_recorded_hash(self):
        assert len(APP["frozen_outputs"]) == 9
        for name, want in APP["frozen_outputs"].items():
            path = os.path.join(D, name)
            assert os.path.exists(path), name
            got = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
            assert got == want, name

    def test_preserved_properties_recorded(self):
        pp = APP["preserved_properties"]
        assert all(v == 0.0 for v in pp["symmetry_mirror_mm"].values())
        assert pp["cubic_segments"] == {"GLASS": 114, "COLLAR": 36,
                                        "DARK_CLOSURE": 36}
        assert pp["supporting_face"].startswith("Jost 300")
        assert pp["flat_colours"]["body"] == "#D9BDB5"


class TestBuildRecordNotRewritten:
    """Acceptance is recorded beside history, never over it."""

    def test_review_record_still_reflects_build_time_truth(self):
        assert REV["human_accepted"] is False
        assert REV["owner_decision_required"] is True

    def test_approval_lives_in_its_own_record(self):
        assert APP["record_type"].startswith(
            "vq2_final_front_artwork_owner_approval/")


class TestWorkstreamClosure:

    def test_condition_was_evaluated_not_assumed(self):
        ev = APP["workstream_closure_evaluation"]
        assert ev["further_vq2_build_tasks_remaining"] == 0
        assert ev["result"] == "VQ2_WORKSTREAM_CLOSED"
        assert len(ev["carried_items_assessed"]) == 3
        for item in ev["carried_items_assessed"]:
            assert item["is_vq2_build_task"] is False
            assert item["why"]

    def test_closure_is_not_production_authority(self):
        ev = APP["workstream_closure_evaluation"]
        for phrase in ("production authority", "Gate-2", "manufacturability"):
            assert phrase in ev["closure_is_not"]
        assert ST["VQ_2_WORKSTREAM"] == "VQ2_WORKSTREAM_CLOSED"


class TestNothingStarted:

    def test_downstream_states_unchanged(self):
        # Complete Product Review has since been explicitly started; the
        # durable invariant is that packaging and VQ-3 still have not
        assert ST["PACKAGING"] == "NOT_STARTED"
        # VQ-3 was later STARTED by explicit owner instruction. The
        # durable invariant is that THIS slice did not start it.
        assert APP["downstream_unchanged"]["VQ_3"] == "NOT_STARTED"
        assert APP["starts_nothing_automatically"] is True

    def test_handoff_was_prepared_not_self_started(self):
        """The v1 handoff is history: it never started anything itself."""
        assert HAND["complete_product_review_started"] is False
        assert HAND["state"] == "PREPARED_NOT_STARTED"
        assert HAND["starts_only_on"] == "EXPLICIT_OWNER_APPROVAL"

    def test_production_gates_still_blocked(self):
        assert ST["PRODUCTION_COLOR_SEPARATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        # Illustrator verification has since PASSED on a human round trip.
        # What this slice guards is that VQ-2 approval did not confer it and
        # that the production states below are still blocked.
        assert ST["ILLUSTRATOR_EXECUTION_VERIFICATION"] == "PASSED"
        assert APP["starts_nothing_automatically"] is True
        assert ST["PRODUCTION_FLAT_ARTWORK"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert AUD["readiness"]["production_colour_separation"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"

    def test_approval_never_claims_production_readiness(self):
        blob = json.dumps(APP)
        for f in ("MANUFACTURABLE", "PRODUCTION_READY", "GATE_2_APPROVED"):
            assert f not in blob


@pytest.mark.django_db
class TestBoardShowsApproval:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "vq2apptester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_reports_approval_and_closure(self, client_in):
        v = client_in.get("/api/visual-quality/vq1/").json()["vq2"]
        a = v["owner_approval"]
        assert a["decision"] == "APPROVED"
        assert a["workstream"] == "VQ2_WORKSTREAM_CLOSED"
        assert len(a["advisory_notes_nonblocking"]) == 3
        assert a["downstream_unchanged"]["VQ_3"] == "NOT_STARTED"
        assert v["a2"]["human_accepted"] is True
        # the build-time record is still surfaced unaltered
        assert v["a2"]["build_time_human_accepted"] is False

    def test_approval_record_serves(self, client_in):
        assert client_in.get(
            "/api/visual-quality/vq1/vq2-final-approval/").status_code == 200
