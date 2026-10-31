"""Phase 2C-2A-CORR-2 — AriaWebResearchGateway.

Security boundary, policy refusal, default-deny rights, deterministic
sessions, the task-#51 styling lesson, and the bounded BBR-SK-201-shaped
session. No image-provider calls, no project/task creation anywhere."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from apps.core.models import Brand, Product
from apps.pipeline.models import (
    DesignProject,
    DesignTask,
    WebAccessRecord,
    WebResearchSession,
)
from apps.pipeline.services import web_research as wr


class SecurityBoundaryTests(TestCase):
    def test_non_http_schemes_blocked(self):
        for url in ("file:///etc/passwd", "data:text/html;base64,AAAA",
                    "javascript:alert(1)", "ftp://x/y", "gopher://x"):
            with pytest.raises(wr.WebPolicyError) as exc:
                wr.check_url_policy(url)
            assert exc.value.code == wr.WEB_SECURITY_POLICY_BLOCKED

    def test_private_and_loopback_addresses_blocked(self):
        for url in ("http://127.0.0.1/", "http://localhost/x",
                    "http://169.254.169.254/latest/meta-data",
                    "http://10.0.0.5/", "http://192.168.1.1/",
                    "http://metadata.google.internal/"):
            with pytest.raises(wr.WebPolicyError):
                wr.check_url_policy(url)

    def test_mime_allowlist(self):
        for good in ("text/html; charset=utf-8", "image/png",
                     "application/pdf"):
            wr.check_mime(good)
        for bad in ("application/octet-stream", "application/zip",
                    "text/javascript", "image/svg+xml"):
            with pytest.raises(wr.WebPolicyError) as exc:
                wr.check_mime(bad)
            assert exc.value.code == wr.WEB_UNSUPPORTED_CONTENT_TYPE

    def test_quarantine_is_root_bounded(self):
        import shutil
        import tempfile
        from pathlib import Path
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        resolved_root = str(Path(root).resolve())
        p = wr.quarantine_write(root, 1, "ok.html", b"x")
        assert p.startswith(resolved_root)
        # traversal names are NEUTRALIZED (basename + resolve check): the file
        # lands INSIDE the quarantine root, never outside it
        p2 = wr.quarantine_write(root, 1, "../../escape.html", b"x")
        assert p2.startswith(resolved_root)
        assert Path(p2).name == "escape.html"


class PolicyAndRightsTests(TestCase):
    def test_search_without_provider_refuses_not_configured(self):
        with override_settings(WEB_SEARCH_PROVIDER="", WEB_SEARCH_API_KEY=""):
            with pytest.raises(wr.WebPolicyError) as exc:
                wr.run_search("q", wr.gateway_config())
            assert exc.value.code == wr.WEB_RESEARCH_NOT_CONFIGURED

    def test_default_permissions_deny_everything_but_retrieval(self):
        perms = wr.default_permissions()
        assert perms.pop("retrieval_permission") is True
        assert not any(perms.values())          # provider/artwork/memory/etc

    def test_tier_ranking_and_fact_authority(self):
        assert wr.classify_tier("bbrose.com", ("bbrose.com",)) == 1
        assert wr.classify_tier("www.sephora.com") == 3
        assert wr.classify_tier("amazon.de") == 4
        assert wr.classify_tier("byrdie.com") == 5
        assert wr.classify_tier("random-images.example") == 6
        assert "high" in wr.fact_authority_for_tier(1)
        assert "low" in wr.fact_authority_for_tier(4)
        assert wr.fact_authority_for_tier(6) == "inferred relationship only"

    def test_condensation_defaults_to_photographic_styling(self):
        cls = wr.classify_image_elements(
            ["water droplets on bottle", "condensation", "shadows",
             "printed logo", "bottle silhouette", "liquid fill"])
        assert cls["water droplets on bottle"] == "photographic_styling"
        assert cls["condensation"] == "photographic_styling"
        assert cls["shadows"] == "photographic_styling"
        assert cls["printed logo"] == "printed_artwork_candidate"
        assert cls["bottle silhouette"] == "physical_geometry"
        assert cls["_policy"] == wr.STYLING_DEFAULT


class QueryPlannerTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=brand, product_id="BBR-SK-201",
            name="Rose Damascena Night Repair", category="SK", year=2026,
            product_type="serum bottle", width_mm=40, depth_mm=40,
            height_mm=110)

    def test_exact_queries_never_carry_unconfirmed_dimensions(self):
        plan = wr.plan_queries(self.product)
        exact = " ".join(plan[wr.EXACT_PRODUCT_DISCOVERY])
        assert "40" not in exact and "110" not in exact
        assert "BBR-SK-201" in exact
        assert list(plan)[0] == wr.EXACT_PRODUCT_DISCOVERY   # exact-first

    def test_query_budget_bounded(self):
        plan = wr.plan_queries(self.product)
        assert sum(len(v) for v in plan.values()) <= \
            wr.DEFAULT_LIMITS["max_queries"]


class SessionTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=brand, product_id="BBR-SK-201",
            name="Rose Damascena Night Repair", category="SK", year=2026,
            product_type="serum bottle")

    @override_settings(WEB_SEARCH_PROVIDER="", WEB_SEARCH_API_KEY="")
    def test_unconfigured_session_blocks_reviewably_and_creates_nothing(self):
        before_p = DesignProject.objects.count()
        before_t = DesignTask.objects.count()
        with patch("apps.pipeline.agents.image_producer.openai.images"
                   ".edit") as ie, \
                patch("apps.pipeline.agents.image_producer.openai.images"
                      ".generate") as ig:
            session = wr.run_research_session(self.product)
        ie.assert_not_called()
        ig.assert_not_called()
        assert session.status == "BLOCKED"
        assert session.summary["blocked_sources"][0]["code"] == \
            wr.WEB_RESEARCH_NOT_CONFIGURED
        assert session.session_hash
        assert WebAccessRecord.objects.filter(
            session=session, kind="policy_block").count() == 1
        assert DesignProject.objects.count() == before_p
        assert DesignTask.objects.count() == before_t

    @override_settings(WEB_SEARCH_PROVIDER="", WEB_SEARCH_API_KEY="")
    def test_session_summary_deterministic_shape(self):
        s1 = wr.run_research_session(self.product)
        s2 = wr.run_research_session(self.product)
        assert s1.queries == s2.queries
        assert s1.summary["rights_summary"] == s2.summary["rights_summary"]

    def test_web_reference_context_only_approved_sources(self):
        session = WebResearchSession.objects.create(
            product_identity="x", modes=[], status="AWAITING_HUMAN_REVIEW")
        session.sources.create(original_url="https://a.example/1",
                               classification="exact",
                               human_review_state="APPROVED_EXACT",
                               source_tier=2, content_sha256="s1")
        session.sources.create(original_url="https://b.example/2",
                               classification="inspiration",
                               human_review_state="UNREVIEWED",
                               source_tier=5, content_sha256="s2")
        ctx = wr.build_web_reference_context(session)
        assert len(ctx["sources"]) == 1
        src = ctx["sources"][0]
        assert src["content_sha256"] == "s1"
        assert src["provider_input_permission"] is False   # default deny
        assert "production authority" in src["prohibited_uses"]
