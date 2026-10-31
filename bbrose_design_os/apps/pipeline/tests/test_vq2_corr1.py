"""VQ-2-CORR-1 — brand authority, vectorization feasibility, hard stop (§21)."""
import hashlib
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq2_artwork as V
from apps.ire import vq2_vectorize as VZ

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")
D = os.path.join(DOCS, "vq2")
J = lambda f: json.load(open(os.path.join(D, f)))            # noqa: E731

FEAS = J("vq2_vectorization_feasibility.json")
RULE = J("vq2_brand_authority_ruling.json")
AUTH = J("vq2_artwork_authorities.json")
FRZ = J("vq2_a2_m3_freeze.json")
# The hard-stop slice this file documents is preserved verbatim; the
# live vq2_a2_artwork_review.json has since advanced to 2.0 (A2 built
# under owner authorization), so these assertions read the archive.
A2 = J("vq2_a2_artwork_review_hardstop_superseded.json")
A1 = J("vq2_artwork_review.json")
ACC = json.load(open(os.path.join(M, "vq1_owner_acceptance.json")))

M3_SHA = "4ecc8e9df1d1"


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]


class TestVQ1AndM3Untouched:
    def test_vq1_remains_closed(self):
        assert "VQ1_WORKSTREAM_CLOSED" in ACC["codes"]
        assert ACC["candidate_loop_state"] == "PERMANENTLY_CLOSED"

    def test_m3_byte_identical(self):
        assert _sha(os.path.join(M, "master_it3.png")) == M3_SHA
        assert A2["m3_identity"] == M3_SHA
        assert A2["m3_modified"] is False

    def test_freeze_reverified_with_no_drift(self):
        assert FRZ["verification"]["drifted"] is False
        assert FRZ["verification"]["differing_fields"] == []
        assert V.verify_freeze(FRZ, M)["drifted"] is False

    def test_drift_would_fail_closed(self):
        t = json.loads(json.dumps(FRZ))
        t["centerline_px"] = 0.0
        assert V.verify_freeze(t, M)["drifted"] is True


class TestVQ2A1Preserved:
    def test_a1_records_and_assets_still_present(self):
        assert A2["vq2_a1_preserved"] is True
        for f in ("vq2_a1.ai", "vq2_a1.png", "vq2_artwork_review.json"):
            assert os.path.exists(os.path.join(D, f))
        assert A1["candidates_created"] == 1

    def test_a1_result_not_rewritten(self):
        assert A1["state"] == V.HARD_STOP
        assert A1["gates_all_pass"] is False


class TestBrandAuthority:
    def test_owner_selected_the_approved_mark(self):
        for c in ("VQ2_OWNER_SELECTED_APPROVED_BRAND_MARK",
                  "VQ2_CONCEPT_BRAND_MARK_NONAUTHORITATIVE",
                  "VQ2_INTENTIONAL_BRAND_CORRECTION_AGAINST_CONCEPT"):
            assert c in RULE["codes"]

    def test_concept_mark_is_nonprinting_and_never_emitted(self):
        assert RULE["concept_mark_state"] == "REFERENCE_CONFLICT_NONPRINTING"
        assert RULE["concept_mark_may_be_emitted_as_artwork"] is False
        assert RULE["geometric_sans_mark_reconstructed"] is False
        assert RULE["outlined_medallion_used_as_final_logo"] is False

    def test_registered_symbol_not_omitted(self):
        assert RULE["registered_symbol_omitted"] is False
        names = [c["component"] for c in FEAS["approved_logo"]["per_component"]]
        assert "REGISTERED_RING" in names and "REGISTERED_INNER" in names

    def test_authority_split_between_form_and_placement(self):
        assert "letterform identity" in RULE["approved_mark_controls"]
        assert "apparent scale" in RULE["concept_controls"]
        assert RULE["difference_classification"] == \
            "APPROVED_BRAND_IDENTITY_OVERRIDES_CONCEPT_RENDERING"
        assert RULE["difference_is_intentional_and_nonblocking"] is True


class TestHonestMethodLabelling:
    def test_never_claims_a_manual_redraw(self):
        assert FEAS["is_manual_redraw"] is False
        assert A2["is_manual_redraw"] is False
        assert "AUTOMATED" in FEAS["honest_label"]
        assert "no manual redraw was performed" in FEAS["important"].lower()

    def test_image_trace_not_used(self):
        assert FEAS["is_adobe_image_trace"] is False
        assert A2["image_trace_used"] is False

    def test_difference_from_image_trace_is_measured_not_asserted(self):
        assert VZ.NOT_IMAGE_TRACE_EVIDENCE
        for c in FEAS["approved_logo"]["per_component"]:
            assert "nodes" in c and "contours" in c
            assert c["nodes"] < 1000

    def test_module_docstring_states_the_limitation(self):
        assert "NOT a designer manually redrawing" in VZ.__doc__


class TestFeasibilityEvidence:
    def test_logo_measured_per_component(self):
        comps = FEAS["approved_logo"]["per_component"]
        assert len(comps) == 9
        for c in comps:
            assert 0.0 <= c["iou_vs_source"] <= 1.0
            assert isinstance(c["meets_0_95"], bool)

    def test_logo_shortfall_is_on_the_registered_mark(self):
        by = {c["component"]: c for c in FEAS["approved_logo"]["per_component"]}
        assert by["REGISTERED_RING"]["meets_0_95"] is False
        assert by["REGISTERED_RING"]["iou_vs_source"] < 0.8
        assert FEAS["approved_logo"]["components_meeting_0_95"] == 7

    def test_every_glyph_failed_the_gate(self):
        cl = FEAS["custom_lettering"]
        assert cl["glyphs"] == 13
        assert cl["glyphs_meeting_0_95"] == 0
        assert cl["worst"] < 0.7
        assert all(not g["meets_0_95"] for g in cl["per_glyph"])

    def test_root_causes_recorded(self):
        assert "40-75 px" in FEAS["root_cause_lettering"]
        assert "noise floor" in FEAS["root_cause_lettering"]
        assert "registered" in FEAS["root_cause_logo"].lower()

    def test_degenerate_glyph_is_disclosed(self):
        worst = max(FEAS["custom_lettering"]["per_glyph"],
                    key=lambda g: g["nodes"])
        assert worst["nodes"] > 150
        assert "20 contours" in FEAS["root_cause_lettering"]

    def test_vectorizer_produces_editable_components_not_one_blob(self):
        for c in FEAS["approved_logo"]["per_component"]:
            assert c["contours"] >= 1
        assert FEAS["approved_logo"]["components_found"] == 9


class TestProjectionAuthority:
    def test_two_authorities_recorded(self):
        assert AUTH["A_CONCEPT_FRONT_APPEARANCE_ARTWORK"]["state"] == "ACTIVE"
        assert AUTH["B_PRODUCTION_FLAT_ARTWORK"]["state"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"

    def test_flat_width_blocker_reassigned_not_deleted(self):
        a = AUTH["A_CONCEPT_FRONT_APPEARANCE_ARTWORK"]
        b = AUTH["B_PRODUCTION_FLAT_ARTWORK"]
        assert a["flat_width_blocker_applies"] is False
        assert b["flat_width_blocker_applies"] is True
        assert V.FLAT_WIDTH_UNRESOLVED in b["blockers"]

    def test_projected_widths_are_not_production_widths(self):
        assert AUTH["projected_widths_are_not_production_widths"] is True
        assert AUTH["vq2_is_supplier_ready_cylindrical_wrap"] is False
        for c in ("VQ2_REFERENCE_WIDTH_IS_PROJECTED",
                  "VQ2_FRONT_APPEARANCE_WIDTH_AUTHORITY",
                  "VQ2_PRODUCTION_FLAT_WIDTH_BLOCKED"):
            assert c in AUTH["codes"]

    def test_projection_not_baked_into_source_lettering(self):
        assert AUTH["curved_baseline_baked_into_source"] is False
        assert "straight canonical baseline" in AUTH["projection_rule"]


class TestHardStopAndBoundaries:
    def test_no_vq2_a2_candidate_was_emitted_by_that_slice(self):
        assert A2["vq2_a2_created"] is False
        assert A2["state"] == V.HARD_STOP
        # A2 exists now, built later under owner authorization: the files on disk are that later build's,
        # by the hashes its own record carries, and the live review says it superseded this hard stop
        live, built = J("vq2_a2_artwork_review.json"), J("vq2_a2.json")
        assert live["vq2_a2_created"] is True
        assert live["supersedes"].startswith("vq2_a2_artwork_review/1.0")
        for ext in ("ai", "png"):
            p = os.path.join(D, "vq2_a2." + ext)
            assert os.path.exists(p), ext
            assert hashlib.sha256(open(p, "rb").read()).hexdigest()[:16] == built[ext + "_sha256_16"], ext

    def test_no_vq2_a3(self):
        assert not os.path.exists(os.path.join(D, "vq2_a3.ai"))

    def test_stop_grounds_named(self):
        assert "VQ2_APPROVED_LOGO_MANUAL_RECONSTRUCTION_NOT_POSSIBLE" in \
            A2["stop_grounds"]
        assert "VQ2_CUSTOM_LETTERING_BELOW_FIDELITY_GATE" in A2["stop_grounds"]

    def test_inspections_not_run_without_a_candidate(self):
        assert A2["inspections_run"] == 0
        assert A2["provider_calls"] == 0
        assert A2["image_generation_calls"] == 0

    def test_no_material_realization(self):
        assert A2["material_realization_added"] is False

    def test_vq3_and_packaging_untouched(self):
        assert A2["vq3_started"] is False
        assert A2["packaging_modified"] is False
        # VQ-3 was later started by explicit owner instruction
        # VQ-1's own workstream record is immutable history and still reads
        # UNBLOCKED_PENDING_EXPLICIT_START; live state advanced elsewhere
        ws = json.load(open(os.path.join(M, "vq1_workstream_state.json")))
        assert ws["VQ_3"] == "UNBLOCKED_PENDING_EXPLICIT_START"

    def test_supplier_drafts_unsent(self):
        sup = json.load(open(os.path.join(
            DOCS, "vq1_reset2", "vq1_supplier_specification_outreach.json")))
        assert not any(s["sent"] for s in sup["suppliers"])
        assert A2["supplier_requests_sent"] is False

    def test_review_package_present(self):
        for ext in ("pdf", "png", "json"):
            p = os.path.join(
                D, f"vq2_a2_artwork_review_hardstop_superseded.{ext}")
            assert os.path.exists(p) and os.path.getsize(p) > 2000
        assert A2["sections"] >= 15

    def test_nothing_claims_production_readiness(self):
        assert A2["production_flat_artwork"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert A2["human_accepted"] is False

    @pytest.mark.django_db
    def test_tasks_and_project_unchanged(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for t in DesignTask.objects.filter(id__in=[51, 52]):
            assert t.status in ("awaiting_gate_2",
                                "container_stage_visually_rejected")
        p = DesignProject.objects.filter(id=7).first()
        if p is not None:
            assert p.status == "container_rejected"


class TestVectorizerUnit:
    def test_closed_smooth_contour_is_not_collapsed(self):
        """Regression: a counter with no sharp corners once collapsed to two
        nodes, silently destroying every bowl in the wordmark."""
        import math
        circle = [(50 + 40 * math.cos(t / 60 * 2 * math.pi),
                   50 + 40 * math.sin(t / 60 * 2 * math.pi))
                  for t in range(60)]
        segs = VZ.fit_closed(circle, corner_idx=set(), tol=0.5)
        assert len(segs) >= 8

    def test_rdp_reduces_nodes(self):
        pts = [(float(i), 0.0) for i in range(50)]
        assert len(VZ.rdp(pts, 0.5)) == 2

    def test_iou_is_symmetric_and_bounded(self):
        import numpy as np
        a = np.zeros((10, 10), bool)
        a[2:8, 2:8] = True
        assert VZ.iou(a, a) == 1.0
        b = np.zeros((10, 10), bool)
        assert VZ.iou(a, b) == 0.0
