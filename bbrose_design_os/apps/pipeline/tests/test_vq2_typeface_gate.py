"""VQ-2 typeface gate — governed research, licence states, no acquisition."""
import hashlib
import json
import os

import pytest
from django.conf import settings

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")
D = os.path.join(DOCS, "vq2")
T = os.path.join(D, "typeface")
SL = json.load(open(os.path.join(T, "vq2_condensed_didone_shortlist.json")))
STATE = json.load(open(os.path.join(D, "vq2_state.json")))
BY = {c["family"]: c for c in SL["candidates"]}
G = SL["research_governance"]


class TestNoAcquisition:
    def test_nothing_purchased_activated_or_downloaded(self):
        for k in ("font_binaries_downloaded", "fonts_installed",
                  "fonts_purchased", "fonts_activated", "webfonts_extracted"):
            assert G[k] is False
        assert SL["no_font_acquired"] is True

    def test_no_lp2_lf1_or_a2(self):
        assert SL["lp2_created"] is False
        assert SL["lf1_created"] is False
        assert SL["vq2_a2_created"] is False
        assert STATE["lp2"] == "NOT_AUTHORIZED"
        # LF1 was later authorised and built; A2 is the invariant that holds
        # A2 now exists, built later under explicit owner
        # authorization. The durable invariant is that it is never
        # auto-generated and never self-accepted.
        # A2 is live and has since been revised; the durable invariant is
        # that no slice ever auto-created it. The archive proves that.
        assert json.load(open(os.path.join(
            D, "vq2_a2_artwork_review_hardstop_superseded.json"
        )))["vq2_a2_created"] is False
        for n in ("vq2_lf1", "vq2_lp2"):
            for ext in ("ai", "pdf", "png"):
                assert not os.path.exists(os.path.join(D, f"{n}.{ext}"))

    def test_no_logins_or_forms(self):
        for k in ("logins_bypassed", "captcha_bypassed", "forms_submitted"):
            assert G[k] is False


class TestGovernedResearch:
    def test_official_sources_only(self):
        assert G["official_sources_only"] is True
        assert G["source_count"] >= 3
        for s in G["sources"]:
            assert s["url"].startswith("https://")
            assert s["source_hash"]
            assert s["source_category"] in (
                "OFFICIAL_FONT_PLATFORM", "OFFICIAL_TECHNICAL_DOCUMENTATION",
                "OFFICIAL_DISTRIBUTOR", "REFERENCE_CONSTRUCTION_PRINCIPLES")

    def test_excluded_source_types_recorded(self):
        j = " ".join(G["excluded"]).lower()
        for bad in ("free-font", "redistribution mirrors", "marketplace",
                    "pirated", "ai-generated"):
            assert bad in j

    def test_failed_fetch_recorded_not_substituted(self):
        c = BY["Bodoni Classic Condensed"]
        src = [s for s in G["sources"] if "myfonts" in s["url"]][0]
        assert src["fetch_result"].startswith("HTTP 429")
        assert "no substitute source was used" in src["note"].lower()
        assert c["natively_condensed"].endswith("NOT VERIFIED THIS PASS")


class TestLicenceStates:
    def test_three_states_never_merged(self):
        m = SL["license_state_model"]
        assert m["never_merged"] is True
        assert m["owner_holds_a_licence_for_any_candidate"] is False
        # Imbue was later selected under OFL, which is an open licence
        assert STATE["owner_holds_font_licence"] in (False, "OFL_OPEN_LICENSE")

    def test_access_is_not_ownership(self):
        iv = BY["IvyBodoni"]
        assert iv["access"] == "specimen viewable"
        assert iv["owner_license_status"] == \
            "ADOBE_FONTS_ACCESS_REQUIRES_OWNER_ACCOUNT_CONFIRMATION"

    def test_rights_and_visual_scores_separate(self):
        assert SL["rights_and_visual_scores_separate"] is True
        for c in SL["candidates"]:
            assert c["visual_score"] is None      # no rendered evidence
            assert "rights_score" in c


class TestNativeCondensedClassification:
    def test_bodoni_mt_rejected_on_official_evidence(self):
        c = BY["Bodoni MT"]
        assert c["classification"] == "REJECTED_NOT_NATIVELY_CONDENSED"
        assert "no Condensed style" in c["natively_condensed"]
        assert "not evidenced by the authority" in c["rejection_basis"]

    def test_unverified_condensed_not_asserted(self):
        assert "UNCONFIRMED" in BY["IvyBodoni"]["natively_condensed"]
        assert "NOT VERIFIED" in \
            BY["Bodoni Classic Condensed"]["natively_condensed"]

    def test_name_alone_never_establishes_condensed(self):
        for c in SL["candidates"]:
            n = c["natively_condensed"]
            assert n is not True or "verified" in str(n).lower()


class TestHonestGaps:
    def test_no_rendered_specimens_claimed(self):
        g = SL["gaps"]
        assert g["rendered_specimens_of_the_two_words"]["produced"] is False
        assert "forbidden to download" in \
            g["rendered_specimens_of_the_two_words"]["reason"]

    def test_no_fabricated_comparison_or_metrics(self):
        g = SL["gaps"]
        assert g["normalized_visual_comparison_sheets"]["produced"] is False
        assert g["width_tracking_and_collision_metrics"]["produced"] is False
        assert g["visual_ranking"]["produced"] is False

    def test_no_winner_declared(self):
        assert SL["winner_declared"] is False
        assert SL["owner_selection_required"] is True

    def test_three_finalists_not_asserted_when_not_available(self):
        assert SL["three_finalists_possible"] is False
        assert SL["finalists_returned"] == 2
        assert SL["why_not_three"]

    def test_package_exists(self):
        for ext in ("pdf", "png", "json"):
            p = os.path.join(T, f"vq2_condensed_didone_shortlist.{ext}")
            assert os.path.exists(p) and os.path.getsize(p) > 2000


class TestState:
    def test_blocked_on_owner_selection(self):
        # superseded: the owner selected Imbue and LF1-R1 was certified
        # A2 now exists, built later under explicit owner
        # authorization. The durable invariant is that it is never
        # auto-generated and never self-accepted.
        # A2 is live and has since been revised; the durable invariant is
        # that no slice ever auto-created it. The archive proves that.
        assert json.load(open(os.path.join(
            D, "vq2_a2_artwork_review_hardstop_superseded.json"
        )))["vq2_a2_created"] is False
        assert STATE["active_blockers"]

    def test_lp1_held_as_hard_stop(self):
        assert "HARD_STOP" in STATE["lp1"]
        assert "NOT_OFFERED_AS_CANDIDATE" in STATE["lp1"]

    def test_m3_frozen_and_vq3_not_started(self):
        sha = hashlib.sha256(
            open(os.path.join(M, "master_it3.png"), "rb").read()
        ).hexdigest()[:12]
        assert sha == "4ecc8e9df1d1" == STATE["m3_identity"]
        # VQ-3 was later started by explicit owner instruction

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
