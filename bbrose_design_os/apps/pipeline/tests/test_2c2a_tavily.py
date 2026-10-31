"""2C-2A-CORR-3 — Tavily connector + BBR-SK-201 session (all mocked)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from apps.core.models import Brand, Product
from apps.pipeline.models import DesignProject, DesignTask, WebAccessRecord
from apps.pipeline.services import web_research as wr
from apps.pipeline.services import web_research_tavily as tv
from apps.pipeline.services import round_designer as rd


def _payload(results=None, images=None, answer=""):
    return {"results": results or [], "images": images or [],
            "answer": answer, "request_id": "resp-1",
            "usage": {"credits": 1}}


class _StubConnector(rd.TavilySearchConnector):
    def __init__(self, payloads=None):
        super().__init__()
        self.calls = []
        self.payloads = payloads or {}

    def search(self, query, *, depth="basic", max_results=8):
        self.calls.append((query, depth))
        return self.normalize(query, self.payloads.get(query, _payload()),
                              latency_ms=5, request_id="req-1")


class ConnectorTests(TestCase):
    def test_missing_key_refuses_without_leaking(self):
        with override_settings(WEB_SEARCH_API_KEY=""):
            with pytest.raises(wr.WebPolicyError) as exc:
                rd.TavilySearchConnector().search("q")
        assert exc.value.code == wr.WEB_RESEARCH_NOT_CONFIGURED
        assert "key" not in str(exc.value).lower() or \
            "absent" in str(exc.value).lower()      # message, never a value

    def test_normalization_discards_answers_and_bounds_fields(self):
        payload = _payload(
            results=[{"url": "https://shop.example/serum", "title": "T" * 500,
                      "content": "C" * 900, "score": 0.91,
                      "published_date": "2026-01-01"}],
            images=[{"url": "https://img.example/1.jpg",
                     "description": "bottle"}, "https://img.example/2.jpg"],
            answer="tavily says the bottle is 40mm wide")
        out = rd.TavilySearchConnector.normalize("q", payload, 7, "rid")
        assert out["answer_discarded"] is True
        assert "tavily says" not in str(out["results"])
        r = out["results"][0]
        assert len(r["title"]) == 300 and len(r["snippet"]) == 500
        assert r["domain"] == "shop.example" and r["rank"] == 1
        assert out["images"][1] == {"url": "https://img.example/2.jpg",
                                    "description": ""}
        assert out["provider_request_id"] == "rid"


class PlannerTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=brand, product_id="BBR-SK-201",
            name="Rose Damascena Night Repair", category="SK", year=2026,
            product_type="carton", width_mm=40, depth_mm=40, height_mm=110)

    def test_carton_product_type_never_pollutes_container_queries(self):
        plan, warnings = tv.plan_queries_v2(self.product)
        assert tv.QUERY_WARNING_SOURCE_TYPE in warnings
        joined = " ".join(q for qs in plan.values() for q in qs).lower()
        assert "carton bottle" not in joined
        assert "carton serum" not in joined
        assert "carton closure" not in joined
        exact = " ".join(plan[wr.EXACT_PRODUCT_DISCOVERY])
        assert "40" not in exact and "110" not in exact and "ml" not in exact

    def test_target_derivation(self):
        target, warnings = tv.research_target(self.product)
        assert target == "cosmetic night serum container"
        assert warnings == [tv.QUERY_WARNING_SOURCE_TYPE]


class MatchingTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=brand, product_id="BBR-SK-201",
            name="Rose Damascena Night Repair", category="SK", year=2026,
            product_type="serum")

    def test_thresholds(self):
        confirmed = {"title": "BBROSE Rose Damascena Night Repair BBR-SK-201",
                     "snippet": ""}
        probable = {"title": "BBROSE Rose Damascena Night Repair 30ml",
                    "snippet": "official"}
        name_only = {"title": "Rose Damascena night oil by another brand",
                     "snippet": "repair"}
        wrong = {"title": "vitamin C day cream", "snippet": ""}
        assert tv.classify_exact_match(confirmed, self.product) == \
            tv.EXACT_CONFIRMED
        assert tv.classify_exact_match(probable, self.product) == \
            tv.EXACT_PROBABLE
        assert tv.classify_exact_match(name_only, self.product) == \
            tv.NAME_MATCH_ONLY
        assert tv.classify_exact_match(wrong, self.product) == \
            tv.WRONG_PRODUCT

    def test_fact_namespaces_separate(self):
        facts = tv.extract_fact_candidates("30 ml bottle 100mm tall", 1, 4,
                                           "analog_feasibility")
        assert facts and all(f["namespace"] == "analog_feasibility"
                             for f in facts)
        assert all(f["verification_state"] == "UNREVIEWED" for f in facts)
        assert any(f["units"] == "ml" for f in facts)
        assert any(f["units"] == "mm" for f in facts)


class SessionTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=brand, product_id="BBR-SK-201",
            name="Rose Damascena Night Repair", category="SK", year=2026,
            product_type="carton")

    def test_bounded_session_defaults_deny_and_escalates_once(self):
        stub = _StubConnector(payloads={
            "night repair serum bottle": _payload(results=[
                {"url": "https://packaging-supplier.example/serum-30ml",
                 "title": "30 ml serum dropper bottle",
                 "content": "30 ml capacity, 100mm tall, dropper",
                 "score": 0.8}]),
        })
        before_p, before_t = (DesignProject.objects.count(),
                              DesignTask.objects.count())
        with patch("apps.pipeline.agents.image_producer.openai.images"
                   ".edit") as ie:
            session = tv.run_tavily_session(self.product, connector=stub)
        ie.assert_not_called()
        assert session.status == "AWAITING_HUMAN_REVIEW"
        # advanced escalation: exact not found → ≤2 advanced exact searches
        advanced = [c for c in stub.calls if c[1] == "advanced"]
        assert 1 <= len(advanced) <= 2
        assert all(any(c[0] == q for q in
                       session.queries[wr.EXACT_PRODUCT_DISCOVERY])
                   for c in advanced)
        assert session.summary["advanced_searches"][0]["reason"] == \
            tv.ADVANCED_ESCALATION_REASON
        # exact not found recorded
        codes = [b["code"] for b in session.summary["blocked_sources"]]
        assert wr.WEB_EXACT_PRODUCT_NOT_FOUND in codes
        # analog retained, default-deny, honestly labelled
        analog = session.sources.filter(source_type=
                                        wr.CATEGORY_ANALOG_DISCOVERY)
        assert analog.count() == 1
        s = analog.first()
        assert s.rights_state == "RIGHTS_UNKNOWN"
        assert not s.provider_input_permission
        assert not s.artwork_reuse_permission
        assert s.human_review_state == "UNREVIEWED"
        assert any(f["namespace"] == "analog_feasibility" for f in s.facts)
        assert session.summary["analog_findings"][0]["note"] == \
            "NOT THE EXACT BBR-SK-201 PRODUCT"
        # query cap respected; ledger rows exist; nothing created
        assert len(stub.calls) <= wr.DEFAULT_LIMITS["max_queries"]
        assert WebAccessRecord.objects.filter(session=session,
                                              kind="search").count() == \
            len(stub.calls)
        assert (DesignProject.objects.count(), DesignTask.objects.count()) \
            == (before_p, before_t)

    def test_session_deterministic_hash_shape(self):
        s1 = tv.run_tavily_session(self.product, connector=_StubConnector())
        s2 = tv.run_tavily_session(self.product, connector=_StubConnector())
        assert s1.queries == s2.queries
        assert s1.session_hash == s2.session_hash


class ReviewEndpointTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group, User
        from apps.pipeline.models import WebResearchSession
        group, _ = Group.objects.get_or_create(name="Reviewer")
        self.user = User.objects.create_user("r", "r@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)
        self.session = WebResearchSession.objects.create(
            product_identity="x", modes=[], status="AWAITING_HUMAN_REVIEW")
        self.source = self.session.sources.create(
            original_url="https://a.example/1", classification="analog",
            title="30ml serum bottle", source_tier=4)

    def test_session_payload_groups_and_no_credentials(self):
        resp = self.client.get(
            f"/api/web-research/sessions/{self.session.id}/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["groups"]["analog"][0]["rights_state"] == "RIGHTS_UNKNOWN"
        assert "api_key" not in str(body).lower()

    def test_provider_input_requires_prior_reference_approval(self):
        url = f"/api/web-research/sources/{self.source.id}/decision/"
        resp = self.client.post(url, {"decision": "approve_provider_input"},
                                content_type="application/json")
        assert resp.status_code == 409
        assert resp.json()["error"] == "WEB_PROVIDER_INPUT_APPROVAL_REQUIRED"
        # approve as analog first, then provider input separately
        assert self.client.post(url, {"decision": "approve_analog"},
                                content_type="application/json"
                                ).status_code == 200
        resp = self.client.post(url, {"decision": "approve_provider_input"},
                                content_type="application/json")
        assert resp.status_code == 200
        self.source.refresh_from_db()
        assert self.source.provider_input_permission is True
        assert self.source.artwork_reuse_permission is False   # never bulk


# ---------------------------------------------------------------------------
# §BH57(a)5 — THE DESIGN PATH MAY OPEN AN INSPIRATION SESSION, AND ONLY THAT.
#
# The owner: "inspiration that never runs is not inspiration". §BH56 measured
# that nothing under agents/ imported this module, so it had never run from a
# design. What stopped it from being a one-line call is `plan_queries_v2`'s
# EXACT list, which carries the brand, the product NAME and the SKU: right for
# a person researching a product that exists, wrong for a design run doing it
# automatically for an unreleased one.
# ---------------------------------------------------------------------------


class _TavilyResponse:
    """What requests.post answers for one Tavily search."""

    def __init__(self, payload, status=200):
        self.status_code = status
        self._payload = payload
        import json
        self.content = json.dumps(payload).encode()
        self.headers = {"x-request-id": "req-9"}

    def json(self):
        return self._payload


class SearchOnTheLedgerTests(TestCase):
    """§BH71 PART 2 — every Tavily search is a ledger row. Measured: ApiCallRecord knew only anthropic and openai,
    so search spend sat outside the design's cap, the day's cap and the "spent" figure; the connector never asked
    for usage, so no credit was ever counted; it could not scope a search by platform or by date; normalize()
    dropped each result's own pictures."""

    def setUp(self):
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(task_text="a compact", status="running", brand=brand)

    def _search(self, payload, *, status=200, depth="basic", **scope):
        from apps.pipeline.services import cost_ledger
        sent = []

        def post(url, *, json, headers, timeout):
            sent.append({"url": url, "json": json, "headers": headers})
            return _TavilyResponse(payload, status)
        with override_settings(WEB_SEARCH_API_KEY="tvly-test-key"), patch.object(tv.requests, "post", post), \
                cost_ledger.task_cost_context(self.task):
            result = rd.TavilySearchConnector(operation="trend_search").search(
                "compact powder case packaging", depth=depth, **scope)
        return result, sent

    def test_a_search_is_a_row_priced_by_its_own_credits_and_scoped_as_asked(self):
        from apps.pipeline.models import ApiCallRecord
        from apps.pipeline.services import cost_ledger
        _result, sent = self._search(_payload(), include_domains=["dribbble.com"],
                                     include_domains_mode="restrict", time_range="year")
        body, headers = sent[0]["json"], sent[0]["headers"]
        assert body["include_usage"] is True and body["time_range"] == "year"
        assert body["include_domains"] == ["dribbble.com"] and body["include_domains_mode"] == "restrict"
        assert "exclude_domains" not in body                              # only what was asked
        assert "api_key" not in body and headers["Authorization"] == "Bearer tvly-test-key"
        row = ApiCallRecord.objects.get(task=self.task)
        assert (row.provider, row.model, row.operation) == ("tavily", "search:basic", "trend_search")
        assert str(row.cost_usd) == "0.008000"
        assert row.metadata["credits"] == 1 and row.metadata["credits_from"] == "the response's own usage"
        assert row.metadata["query"] == "compact powder case packaging"
        assert row.metadata["scope"]["include_domains"] == ["dribbble.com"]
        assert "tvly-test-key" not in str(row.metadata)                   # the key is never on the row
        assert str(cost_ledger.task_cost_usd(self.task)) == "0.008000"

    def test_a_search_with_no_usage_is_priced_by_the_documented_credits_and_says_so(self):
        from apps.pipeline.models import ApiCallRecord
        payload = _payload()
        del payload["usage"]
        self._search(payload, depth="advanced")
        row = ApiCallRecord.objects.get(task=self.task)
        assert str(row.cost_usd) == "0.016000" and row.metadata["credits"] == 2
        assert "documented" in row.metadata["credits_from"] and "no usage" in row.metadata["credits_from"]

    def test_searches_share_the_rescue_calendar_day_reservation(self):
        from apps.pipeline.services import cost_ledger, spend_reservation
        from apps.pipeline.models import ApiCallRecord
        self._search(_payload())
        assert not cost_ledger.daily_budget_exceeded()
        spend_reservation.reserve('openai', 'other work', 'gpt-image-2', 24.992)
        assert cost_ledger.daily_budget_exceeded()
        with pytest.raises(cost_ledger.BudgetExceededError):
            self._search(_payload())
        assert ApiCallRecord.objects.filter(task=self.task).count() == 1

    def test_no_row_without_a_design_and_none_for_a_failed_search(self):
        from apps.pipeline.models import ApiCallRecord
        with override_settings(WEB_SEARCH_API_KEY="tvly-test-key"), \
                patch.object(tv.requests, "post", lambda url, *, json, headers, timeout: _TavilyResponse(_payload())):
            rd.TavilySearchConnector().search("q")                        # no design in scope
        assert ApiCallRecord.objects.count() == 0
        with pytest.raises(wr.WebPolicyError):
            self._search(_payload(), status=500)
        assert ApiCallRecord.objects.count() == 0

    def test_the_designs_cap_stopping_a_session_closes_it_and_stops_the_design(self):
        """The session's catch-all turned the cap's error into "session aborted" and the design went on spending."""
        from apps.pipeline.models import WebResearchSession
        from apps.pipeline.services import cost_ledger

        class _Capped(rd.TavilySearchConnector):
            def search(self, query, **kwargs):
                raise cost_ledger.BudgetExceededError("task budget exceeded: $5.01 spent, cap is $5.00")
        product = Product.objects.create(brand=Brand.objects.get(name="BBROSE"), product_id="BBR-CO-901",
                                         name="Cap", category="CO", year=2026, product_type="compact")
        with pytest.raises(cost_ledger.BudgetExceededError):
            tv.run_tavily_session(product, connector=_Capped(),
                                  plan={wr.VISUAL_INSPIRATION_DISCOVERY: ["compact packaging design"]})
        session = WebResearchSession.objects.get(candidate_id="BBR-CO-901")
        assert session.status == "BLOCKED"
        assert session.summary["blocked_sources"][-1]["code"] == "BUDGET_EXCEEDED"

    def test_an_answer_that_is_not_a_search_is_refused_and_a_missing_request_id_is_said(self):
        """Measured by the whole suite: a test that patches `requests.post` for another service answered this search
        with a non-string request id, and the ledger row could not be written."""
        from unittest.mock import MagicMock

        from apps.pipeline.models import ApiCallRecord
        from apps.pipeline.services import cost_ledger
        with pytest.raises(wr.WebPolicyError):
            self._search(["not", "a", "search"])
        odd = _TavilyResponse(_payload())
        odd.headers = MagicMock()                                        # its .get answers a mock, not a string
        with override_settings(WEB_SEARCH_API_KEY="tvly-test-key"), \
                patch.object(tv.requests, "post", lambda url, *, json, headers, timeout: odd), \
                cost_ledger.task_cost_context(self.task):
            rd.TavilySearchConnector().search("q")
        row = ApiCallRecord.objects.get(task=self.task)
        assert row.metadata["provider_request_id"] == cost_ledger.PROVIDER_REQUEST_ID_NOT_RETURNED

    def test_each_results_own_pictures_are_kept_with_their_page(self):
        payload = _payload(results=[
            {"url": "https://dribbble.com/shots/1-rose", "title": "Rose compact", "content": "", "score": 0.9,
             "images": ["https://cdn.dribbble.com/a.png",
                        {"url": "https://cdn.dribbble.com/b.png", "description": "a rose gold compact"}]},
            {"url": "https://example.com/p", "title": "no pictures", "content": "", "score": 0.5}])
        out = rd.TavilySearchConnector.normalize("q", payload, 5, "rid")
        first, second = out["results"]
        assert first["images"] == [{"url": "https://cdn.dribbble.com/a.png", "description": ""},
                                   {"url": "https://cdn.dribbble.com/b.png", "description": "a rose gold compact"}]
        assert first["url"] == "https://dribbble.com/shots/1-rose" and second["images"] == []


def _picture(seed: int, side: int = 200) -> bytes:
    """A PNG of a design's size (tens of kilobytes: noise does not compress), different for every seed."""
    import io as _io
    import random

    from PIL import Image
    img = Image.frombytes("RGB", (side, side * 3 // 4), random.Random(seed).randbytes(side * (side * 3 // 4) * 3))
    out = _io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def _page_declaring(picture_url: str):
    """A result page that declares its own picture, as a platform's page does (og:image)."""
    return _Served(('<html><head><meta property="og:image" content="%s"><title>t</title></head><body>'
                    '<img src="/avatar.png"></body></html>' % picture_url).encode(), "text/html")


class _Served:
    """What the governed fetch is answered for one picture."""

    def __init__(self, body, content_type="image/png", status=200):
        self.status_code = status
        self.headers = {"content-type": content_type}
        self._body = body

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        pass


class _TrendConnector(rd.TavilySearchConnector):
    """A provider that answers each platform's scoped search from a table, and records what it was asked."""

    def __init__(self, by_domain=None, open_web=None, fail_after=None, failure=None):
        super().__init__(operation="trend_search")
        self.calls = []
        self.by_domain = by_domain or {}
        self.open_web = open_web or _payload()
        self.fail_after, self.failure = fail_after, failure

    def search(self, query, *, depth="basic", max_results=8, include_domains=None, include_domains_mode=None,
               exclude_domains=None, time_range=None):
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise self.failure
        self.calls.append({"query": query, "include_domains": include_domains, "mode": include_domains_mode,
                           "exclude_domains": exclude_domains, "time_range": time_range})
        payload = self.open_web
        if include_domains:
            payload = self.by_domain.get(include_domains[0], _payload())
        return self.normalize(query, payload, 5, "req-t")


class _WorkerDied(BaseException):
    """What a worker killed mid-build looks like to the code it was running: nothing catches it."""


class TrendBoardTests(TestCase):
    """§BH71 PART 2 — THE TREND BOARD: every new design searched on the platforms he named for current trends in its
    product type, the pictures fetched under every guard and read into words, ticked by default, unticked in one click
    under one lock, their words — never the pictures — to the directions, and what it cost."""

    READING = {"layout": "one centred mark on a quiet field", "mood": "calm and warm", "finish": "soft gold foil",
               "type_style": "thin spaced capitals", "colour_words": "blush with warm gold",
               "take": "a single gold line on a soft ground", "seen_not_taken": ["ACME PARIS"],
               # [his test findings on design 121, item 5] what it shows, as the reader now says it
               "shows": "packaging design", "product_kind": "beauty or personal care",
               # [his goal of 2026-10-10, item 3] and the product it shows, in a shopper's words
               "product_form": "powder compact"}

    def setUp(self):
        import tempfile
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(brand=self.brand, product_id="BBR-CO-777", name="Rose Veil",
                                              category="CO", year=2026, product_type="compact", name_ar="وردة")
        self.task = DesignTask.objects.create(
            task_text="Rose Veil — a pressed powder compact finished in gold foil, BBR-CO-777", status="running",
            brand=self.brand, product=self.product, design_target="product_container")
        self.tmp = tempfile.mkdtemp(prefix="trend_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- [his test findings on design 121, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md), item 5: "The trend board picked
    # ---- market-size bar charts, a cropped logo and a coffee cup. Only show real packaging or product design pictures;
    # ---- filter out charts, infographics, logos, text pages and unrelated products."]

    #: the three market-report pages 121's board fetched, as the open web returned them
    REPORTS_121 = [
        {"url": "https://www.mordorintelligence.com/industry-reports/tube-packaging-market",
         "title": "Tube Packaging Market - Trends, Share & Size", "content": "", "score": 0.7,
         "images": ["https://s3.mordorintelligence.com/production/tube-packaging-market/market-snapshot.webp"]},
        {"url": "https://www.precedenceresearch.com/tube-packaging-market",
         "title": "Tube Packaging Market Companies, Size & Trends 2026-2034", "content": "", "score": 0.6,
         "images": ["https://www.precedenceresearch.com/insightimg/tube-packaging-market-size.webp"]},
        {"url": "https://straitsresearch.com/report/tube-packaging-market",
         "title": "Tube Packaging Market Size, Share, Growth, Analysis, Report, 2034", "content": "", "score": 0.5,
         "images": ["https://straitsresearch.com/uploads/reports/tube-packaging-market-2702.webp"]}]

    def test_his_test_findings_121_a_market_reports_chart_is_left_out_before_it_is_fetched(self):
        from apps.pipeline.models import TrendPick
        from apps.pipeline.services import trend_board
        connector = _TrendConnector(by_domain=self._platforms(),
                                    open_web=_payload(results=self.REPORTS_121 + self._open_web()["results"]))
        board, _ = self._build(connector=connector)          # the served table holds none of them: never fetched
        out = board.picks.filter(kind=TrendPick.PICTURE, unread_reason__startswith=trend_board.LEFT_OUT)
        self.assertEqual(sorted(p.page_url for p in out), sorted(r["url"] for r in self.REPORTS_121))
        self.assertTrue(all(p.sha256 == "" for p in out))
        shown = trend_board.payload(self.task)
        urls = [p["page_url"] for p in shown["pictures"]] + [l["page_url"] for l in shown["links"]]
        self.assertFalse(any("research" in u or "intelligence" in u for u in urls), urls)
        # [re-pinned by his goal of 2026-10-10, item 3: "show nothing rather than junk"] beside the market reports, the
        # links naming no powder compact are not shown either, counted with them
        self.assertEqual(shown["left_out"][0], {"words": "a market report's chart, not a design", "count": 3})
        # [re-pinned again by item 3: a link is judged by its title alone, so it names the product in full] the
        # Dribbble shot titled "gold compact", never fetched, names no powder compact: counted as never checked
        self.assertEqual([row["words"] for row in shown["left_out"][1:]],
                         ["not fetched, so never checked", "a link whose title names no powder compact"])

    def test_pitch_goal_a1_a_written_trend_brief_from_every_source_reaches_the_planner_without_a_brand(self):
        """[His goal for the pitch, 2026-10-15, A (1): "research current trends ... competitor cosmetic brand sites ...
        respecting each site's terms (read what's allowed; links where not). Write a short TREND BRIEF (what's new:
        colours, type, materials, illustration styles, layouts) and show it on the design page."]"""
        import json
        from apps.pipeline.services import trend_board
        searched = trend_board.plan(self.task)
        brands = [s for s in searched if s["platform"] == "beauty_brands"]
        self.assertEqual(len(brands), 1)
        self.assertIn("rarebeauty.com", brands[0]["scope"]["include_domains"])
        self.assertEqual(trend_board.mode_of("beauty_brands"), trend_board.LINK)      # never a brand's picture fetched
        board, _ = self._build()
        trend_board.confirm(self.task, trend_board.BY_HIS_CLICK)
        told = []

        def call(system, text):
            told.append(text)
            return json.dumps({"headline": "Chrome caps over soft-touch bodies", "whats_new": "Lacquer meets matte.",
                               "colours": ["butter yellow with cocoa [1]"], "type": ["wide grotesk capitals [2]"],
                               "materials": ["soft-touch body, chrome cap [1]"], "illustration": ["fine line botanicals [3]"],
                               "layouts": ["name stacked low [2]"], "sources_used": [1, 2, 3]})
        brief = trend_board.write_brief(self.task, call=call)
        self.assertEqual(brief["headline"], "Chrome caps over soft-touch bodies")
        self.assertEqual([s["n"] for s in brief["sources"]], [1, 2, 3])
        self.assertIn("[1]", told[0])                                  # every source numbered for the writer
        self.assertIsNone(trend_board.write_brief(self.task, call=lambda *a: self.fail("written twice")) and None)
        board.refresh_from_db()
        words = trend_board.words_block(self.task)
        self.assertIn("CURRENT TREND BRIEF", words)
        self.assertIn("butter yellow with cocoa", words)
        self.assertNotIn("http", words.split("CURRENT TRENDS, FOUND")[0])           # its sources stay on the page
        self.assertEqual(trend_board.payload(self.task)["brief"]["headline"], "Chrome caps over soft-touch bodies")

    def test_his_test_findings_121_what_the_reader_says_a_picture_shows_leaves_charts_logos_and_other_products_out(self):
        from apps.pipeline.services import trend_board
        kept = dict(self.READING)
        for shows, kind, why in (("chart or infographic", "none", "a chart or an infographic, not a design"),
                                 ("logo or lettering only", "none", "a logo, not a design"),
                                 ("page of text", "none", "a page of text, not a design"),
                                 ("packaging design", "food or drink",
                                  "a picture of another kind of product (food or drink)"),
                                 ("packaging design", "beauty or personal care", "")):
            self.assertEqual(trend_board.left_out_words(dict(kept, shows=shows, product_kind=kind)), why)
        self.assertEqual(trend_board.left_out_words({}), "not a packaging or product design")

    def test_his_test_findings_121_a_reading_made_before_is_read_once_more_for_what_it_shows(self):
        import json
        from unittest.mock import MagicMock

        from apps.pipeline.models import ApiCallRecord, InspirationReading
        from apps.pipeline.services import inspiration
        data = _picture(7)
        old = {k: v for k, v in self.READING.items() if k not in inspiration.KIND_FIELDS}
        InspirationReading.objects.create(sha256=inspiration.sha256_of(data), reading=old)
        reply = MagicMock(content=[MagicMock(type="text", text=json.dumps(self.READING))],
                          usage=MagicMock(input_tokens=1400, output_tokens=320))
        with override_settings(ANTHROPIC_API_KEY="k"), \
                patch("apps.pipeline.services.claude_service._get_client") as client:
            client.return_value.messages.create.return_value = reply
            row, spent = inspiration.read(data, task=self.task, operation="trend_read", require=inspiration.KIND_FIELDS)
            again, spent_again = inspiration.read(data, task=self.task, require=inspiration.KIND_FIELDS)
        self.assertTrue(spent)
        self.assertFalse(spent_again)
        self.assertEqual((row.reading["shows"], row.reading["product_kind"]),
                         ("packaging design", "beauty or personal care"))
        self.assertEqual(row.reading["layout"], old["layout"])                        # the reading kept, two fields added
        self.assertEqual(ApiCallRecord.objects.filter(task=self.task, operation="trend_read").count(), 1)

    # ---- [his goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), items 3 and 4: "WEB SEARCH MUST FILTER (I see too much
    # ---- generic junk)" — "Only keep trend pictures that actually show THIS product type (for 124: eyeshadow palettes)
    # ---- ... show nothing rather than junk." — "Search with the product's own words and the brief's style words (e.g.
    # ---- "illustrated eyeshadow palette fairytale"), not generic "packaging"."]

    BRIEF_124 = ("Enchanted Rose Palette (test)\n\nProduct: BBROSE Enchanted Rose eyeshadow palette (imaginary test "
                 "product).\nType: eyeshadow palette, a rectangular case with a magnetic lid, 18\nsquare pans in 3 rows of "
                 "6, each shade name printed under its pan.\nAudience: women 18–30, dreamy, magical, bold make-up "
                 "lovers.\n\nMood: a dreamy fairytale. Use the uploaded pictures for inspiration\nonly: a magical "
                 "illustrated scene on the lid, pastel pinks, lilacs and\nicy teal, an elegant script name over the "
                 "scene.\n\nLid front copy: BBROSE logo, \"Enchanted Rose\".\n\n[Container type: compact; Product "
                 "category: eyeshadow palette; Capacity: 18 pans, 27 g; Closure: magnetic]")
    BRIEF_123 = ("Rose Blossom Hand Cream (test)\n\nType: hand cream in a squeeze tube with a flip-top cap, plus its tall"
                 "\ncarton (reverse tuck end).\n\nMood: soft and romantic, one pink family with red line art. Combine "
                 "the\nuploaded pictures into OUR OWN design; never copy any of them:\n- The red line-art blossoms: the "
                 "illustration style.\n\nFront copy: BBROSE logo, \"Rose Blossom\".\n\n[Container type: tube; Product "
                 "category: hand cream; Capacity: 60 ml; Closure: flip-top cap]")

    def _designs(self):
        palette = DesignTask.objects.create(task_text=self.BRIEF_124, status="running", brand=self.brand,
                                            design_target="product_container")
        carton = DesignTask.objects.create(task_text=self.BRIEF_123, status="running", brand=self.brand,
                                           design_target="packaging")
        return palette, carton

    def test_goal_1010_item4_the_search_is_the_products_own_words_and_the_briefs_style_words(self):
        """124 searched as he wrote it — "illustrated eyeshadow palette fairytale" — and 123's carton in its own words
        and style; never "cosmetic", never "packaging", in any query; never the brand or the product's name."""
        from apps.pipeline.services import trend_board
        palette, carton = self._designs()
        self.assertEqual(trend_board.subject_of(palette), "illustrated eyeshadow palette fairytale")
        self.assertEqual(trend_board.subject_of(carton), "line art hand cream box floral")
        for task in (palette, carton, self.task):
            queries = " ".join(s["query"] for s in trend_board.plan(task)).lower()
            for word in ("packaging", "cosmetic", "bbrose", "enchanted rose", "rose blossom", "rose veil"):
                self.assertNotIn(word, queries, (task.task_text[:30], queries))

    def test_goal_1010_item3_a_picture_of_anything_but_the_product_is_left_out(self):
        """Each picture's reading checked against the design's own product before it is shown: another product, a mix,
        none, a display, a podium or people — left out by what it shows; a palette by any name of a palette kept."""
        from apps.pipeline.services import trend_board
        palette, carton = self._designs()
        terms = trend_board.product_terms(palette)
        self.assertEqual(terms, ("eyeshadow palette", "palette"))
        kept = dict(self.READING, product_form="eyeshadow palette")
        for form, shows, why in (("eyeshadow palette", "packaging design", ""), ("makeup palette", "product design", ""),
                                 ("lip gloss", "packaging design",
                                  "a picture of another product (lip gloss), not an eyeshadow palette"),
                                 ("cream jar", "product design",
                                  "a picture of another product (cream jar), not an eyeshadow palette"),
                                 ("carton box", "packaging design",
                                  "a picture of another product (carton box), not an eyeshadow palette"),
                                 ("several products", "product design", "a mix of products, not one eyeshadow palette"),
                                 ("none", "packaging design", "a picture that shows no eyeshadow palette"),
                                 ("eyeshadow palette", "display or podium", "a display or a podium, not a design"),
                                 ("eyeshadow palette", "people", "a picture of people, not a design")):
            self.assertEqual(trend_board.left_out_words(dict(kept, product_form=form, shows=shows), terms), why)
        box = trend_board.product_terms(carton)
        self.assertEqual(trend_board.left_out_words(dict(kept, product_form="hand cream box"), box), "")
        self.assertTrue(trend_board.left_out_words(dict(kept, product_form="hand cream tube"), box))

    def test_goal_1010_item3_nothing_unchecked_is_shown_and_its_thumbnail_is_never_served(self):
        """A board whose reader names no product for its pictures shows none of them — they are left out, counted, and
        their thumbnails refused at their own address; a picture never read is never shown either."""
        from django.contrib.auth.models import User

        from apps.pipeline.models import TrendPick
        from apps.pipeline.services import trend_board
        self.READING = {k: v for k, v in self.READING.items() if k != "product_form"}
        board, _ = self._build()
        shown = trend_board.payload(self.task)
        self.assertEqual(shown["pictures"], [])
        self.assertTrue(any("shows no" in row["words"] for row in shown["left_out"]), shown["left_out"])
        pick = board.picks.filter(kind=TrendPick.PICTURE).exclude(thumb_path="").first()
        self.assertIsNotNone(pick)
        self.client.force_login(User.objects.create_superuser("trend1010", "t@t.com", "x"))
        with override_settings(WEB_QUARANTINE_ROOT=self.tmp):
            r = self.client.get("/api/tasks/%d/trends/%d/thumbnail/" % (self.task.pk, pick.pk))
        self.assertEqual(r.status_code, 404)

    def _reply(self):
        import json
        from unittest.mock import MagicMock
        return MagicMock(content=[MagicMock(type="text", text=json.dumps(self.READING))],
                         usage=MagicMock(input_tokens=1400, output_tokens=320))

    def _platforms(self):
        return {
            "dribbble.com": _payload(results=[
                {"url": "https://dribbble.com/shots/101-rose-compact", "title": "ACME rose compact", "content": "",
                 "score": 0.9, "images": [{"url": "https://cdn.dribbble.com/userupload/1.png",
                                           "description": "a rose compact"}]},
                {"url": "https://dribbble.com/shots/102-gold", "title": "gold compact", "content": "", "score": 0.8,
                 "images": ["https://cdn.dribbble.com/blocked/2.png"]}],
                images=["https://cdn.dribbble.com/userupload/1.png", "https://cdn.dribbble.com/loose.png"]),
            "pinterest.com": _payload(results=[
                {"url": "https://www.pinterest.com/pin/1/", "title": "a pin", "content": "", "score": 0.7,
                 "images": ["https://i.pinimg.com/1.jpg"]}]),
            "behance.net": _payload(results=[
                {"url": "https://www.behance.net/gallery/1/Rose", "title": "Behance rose", "content": "",
                 "score": 0.7, "images": ["https://mir-s3-cdn-cf.behance.net/1.png"]}]),
        }

    def _open_web(self):
        return _payload(results=[
            {"url": "https://blog.example.org/compacts", "title": "the year's compacts", "content": "", "score": 0.6,
             "images": ["https://blog.example.org/img/a.png"]},
            {"url": "https://www.behance.net/gallery/2/Found", "title": "found on the open web", "content": "",
             "score": 0.5, "images": ["https://mir-s3-cdn-cf.behance.net/2.png"]}])

    def _served(self):
        return {"https://cdn.dribbble.com/userupload/1.png": _Served(_picture(1)),
                "https://blog.example.org/img/a.png": _Served(_picture(2))}

    def _build(self, connector=None, robots=None, served=None):
        from apps.pipeline.services import trend_board

        def get(url, *, headers, timeout):
            table = self._served() if served is None else served
            if url not in table:
                raise AssertionError("must not fetch %s" % url)
            return table[url]

        if connector is None:
            connector = _TrendConnector(by_domain=self._platforms(), open_web=self._open_web())
        if robots is None:
            def robots(url, ua):
                if "blocked" in url:
                    return "disallowed"
                return "allowed"
        with override_settings(WEB_QUARANTINE_ROOT=self.tmp, ANTHROPIC_API_KEY="k"), \
                patch("apps.pipeline.services.web_research.check_url_policy"), \
                patch("apps.pipeline.services.claude_service._get_client") as client:
            client.return_value.messages.create.return_value = self._reply()
            board = trend_board.build(self.task, connector=connector, http_get=get, robots=robots)
        return board, connector

    def test_the_subject_is_the_systems_own_words_and_the_query_never_names_the_product(self):
        from apps.pipeline.services import trend_board
        # [re-pinned by his goal of 2026-10-10, item 4: "Search with the product's own words and the brief's style
        # words (e.g. "illustrated eyeshadow palette fairytale"), not generic "packaging"."] the brief's "gold foil" the
        # style word, "powder compact" the product's own — never "cosmetic", never "packaging"
        self.assertEqual(trend_board.subject_of(self.task), "foil powder compact")
        searches = trend_board.plan(self.task)
        text = " ".join(s["query"] for s in searches)
        for identity in ("BBROSE", "Rose Veil", "BBR-CO-777", "وردة"):
            self.assertNotIn(identity, text)
        by_platform = {}
        for s in searches:
            by_platform.setdefault(s["platform"], []).append(s)
        for platform in trend_board.PLATFORMS:
            (search,) = by_platform[platform["key"]]
            self.assertEqual(search["scope"]["include_domains"], list(platform["domains"]))
            self.assertEqual((search["scope"]["include_domains_mode"], search["scope"]["time_range"]),
                             ("restrict", "year"))
        opens = [s for s in by_platform["open_web"] if "source" not in s]
        # [his goal for the pitch, 2026-10-15, A (1)] the year's trends, the season's trend pages, the finish, bilingual
        self.assertEqual(len(opens), 4)
        self.assertTrue(all(s["scope"]["exclude_domains"] == ["pinterest.com", "instagram.com"] for s in opens))
        # [Day 8 §2b] then the award and press sources, as the open web scoped to their own domains, last
        sources = by_platform["open_web"][4:]
        self.assertEqual([s["source"] for s in sources], [src["key"] for src in trend_board.OPEN_WEB_SOURCES])
        for search, src in zip(sources, trend_board.OPEN_WEB_SOURCES):
            self.assertEqual((search["scope"]["include_domains"], search["scope"]["include_domains_mode"]),
                             (list(src["domains"]), "restrict"))
        from django.utils import timezone
        self.assertEqual(opens[1]["query"], trend_board.TREND_PAGES_QUERY.format(year=timezone.now().year))
        self.assertIn("gold foil", opens[2]["query"])
        self.assertTrue(opens[3]["query"].startswith("Arabic bilingual"))
        self.task.design_target = "packaging"
        # [his goal of 2026-10-10, item 4] its carton searched as the product's box, in its brief's style word
        self.assertEqual(trend_board.subject_of(self.task), "foil compact box")
        blank = DesignTask.objects.create(task_text="something for spring", status="running", brand=self.brand,
                                          design_target="product_container")
        self.assertEqual(trend_board.subject_of(blank), "beauty product")

    @override_settings(TREND_PLATFORM_MODES={"pinterest": "SKIP", "behance": "LINK", "dribbble": "FETCH",
                                             "instagram": "LINK", "the_dieline": "LINK",
                                             "packaging_of_the_world": "FETCH", "open_web": "FETCH",
                                             "beauty_brands": "LINK"})
    def test_a_skipped_platform_is_not_searched(self):
        _board, connector = self._build()
        self.assertFalse(any(c["include_domains"] == ["pinterest.com"] for c in connector.calls))
        self.assertEqual(len(connector.calls), 12)                # 6 platforms (the brands' sites one), 4 open-web, 2 sources

    def test_a_board_fetches_under_every_guard_links_what_may_not_be_fetched_and_reads_what_it_fetched(self):
        from apps.pipeline.models import ApiCallRecord, TrendBoard, TrendPick, WebAccessRecord
        board, connector = self._build()
        self.assertEqual(board.status, TrendBoard.READY)
        self.assertEqual(len(connector.calls), 13)                # [Day 8 §2b] + the award and press sources
        pictures = {p.image_url: p for p in board.picks.filter(kind=TrendPick.PICTURE)}
        links = {p.page_url: p for p in board.picks.filter(kind=TrendPick.LINK)}
        self.assertEqual(set(pictures), {"https://cdn.dribbble.com/userupload/1.png",
                                         "https://cdn.dribbble.com/blocked/2.png",
                                         "https://blog.example.org/img/a.png"})
        self.assertEqual(set(links), {"https://www.pinterest.com/pin/1/", "https://www.behance.net/gallery/1/Rose",
                                      "https://www.behance.net/gallery/2/Found"})   # the platform serving it decides
        self.assertEqual(links["https://www.behance.net/gallery/2/Found"].platform, "behance")
        read = pictures["https://cdn.dribbble.com/userupload/1.png"]
        self.assertTrue(read.used and read.sha256 and read.unread_reason == "")
        self.assertEqual((read.platform, read.page_url), ("dribbble", "https://dribbble.com/shots/101-rose-compact"))
        self.assertLessEqual(max(read.thumb_width, read.thumb_height), 512)
        self.assertTrue(read.thumb_path.startswith(self.tmp) or self.tmp in read.thumb_path)
        source = read.source
        self.assertEqual((source.classification, source.rights_state), ("image", "RIGHTS_UNKNOWN"))
        self.assertFalse(source.provider_input_permission or source.artwork_reuse_permission)
        self.assertEqual(source.human_review_state, "UNREVIEWED")          # nothing approved on his behalf
        refused = pictures["https://cdn.dribbble.com/blocked/2.png"]
        self.assertFalse(refused.used)
        self.assertIn("robots.txt disallows", refused.unread_reason)
        self.assertTrue(WebAccessRecord.objects.filter(session=board.session, kind="policy_block",
                                                       url="https://cdn.dribbble.com/blocked/2.png",
                                                       outcome="WEB_ROBOTS_DISALLOWED").exists())
        self.assertFalse(any(link.used for link in links.values()))         # a link card feeds nothing
        self.assertIn("robots.txt", board.refusals["pinterest"]["words"])
        self.assertIn("terms", board.refusals["behance"]["words"])
        self.assertEqual(board.refusals["source_unknown"]["count"], 1)      # loose.png came with no page
        reads = ApiCallRecord.objects.filter(task=self.task, operation="trend_read")
        self.assertEqual(reads.count(), 2)
        self.assertEqual(WebAccessRecord.objects.filter(session=board.session, kind="search").count(), 13)

    def test_day8_new_sources_keep_fetch_link_skip_as_ruled(self):
        """[Day 8 §2b] the palette leaders and the Middle-East houses are brands' own sites — links; a page an award or
        press search finds is the open web's (fetched under every guard) unless its host is a declared platform's: The
        Dieline and Packaging of the World stay links (his ruling of 2026-09-29), whatever search found them."""
        from apps.pipeline.services import trend_board
        for url in ("https://www.natashadenona.com/products/x", "https://www.dior.com/en_us/beauty/makeup",
                    "https://www.yslbeautyus.com/makeup/eyes", "https://www.makeupbymario.com/products/x",
                    "https://asteribeauty.com/products/x", "https://www.patmcgrath.com/x", "https://hauslabs.com/x"):
            platform = trend_board.platform_of(url)
            self.assertEqual((platform["key"], trend_board.mode_of(platform["key"])), ("beauty_brands", "LINK"), url)
        for url in ("https://pentawards.com/live/en/winners/x", "https://competition.adesignaward.com/design.php?ID=1",
                    "https://www.worldbranddesign.com/x-packaging/", "https://www.allure.com/gallery/best-palettes"):
            platform = trend_board.platform_of(url)
            self.assertEqual((platform["key"], trend_board.mode_of(platform["key"])), ("open_web", "FETCH"), url)
        for url, key in (("https://thedieline.com/dieline-awards/x", "the_dieline"),
                         ("https://packagingoftheworld.com/2026/x.html", "packaging_of_the_world")):
            platform = trend_board.platform_of(url)
            self.assertEqual((platform["key"], trend_board.mode_of(platform["key"])), (key, "LINK"), url)
        for platform in trend_board.PLATFORMS + (trend_board.OPEN_WEB,):
            self.assertIn(trend_board.mode_of(platform["key"]), ("FETCH", "LINK", "SKIP"))

    def test_day8_a_host_that_cannot_be_reached_refuses_its_picture_and_the_board_goes_on(self):
        """[Day 8, measured] one host's SSL handshake failed and the whole board was recorded FAILED; now that picture
        is refused by name and the board is READY with the others."""
        import requests
        from apps.pipeline.models import TrendBoard, TrendPick

        class Unreachable(dict):
            def __getitem__(self, url):
                if url == "https://blog.example.org/img/a.png":
                    raise requests.exceptions.SSLError("handshake failed")
                return dict.__getitem__(self, url)
        board, _c = self._build(served=Unreachable(self._served()))
        self.assertEqual(board.status, TrendBoard.READY)
        refused = board.picks.get(kind=TrendPick.PICTURE, image_url="https://blog.example.org/img/a.png")
        self.assertIn("could not be reached (SSLError)", refused.unread_reason)
        self.assertFalse(refused.used)

    def test_day8_a_style_the_brief_negates_is_never_searched(self):
        """[Day 8] his look for the house — "editorial, not floral" — searched "floral" before; a negated style word is
        cut before the words are heard, and an unnegated one still is."""
        from apps.pipeline.services import trend_board
        self.task.task_text = ("Product category: eyeshadow palette\n\nLook: soft power, worn out loud; Rose without "
                               "being literal about it; editorial, not floral.\n")
        self.assertNotIn("floral", trend_board.style_words(self.task))
        self.task.task_text = "Product category: eyeshadow palette\n\nLook: dreamy floral, never minimal.\n"
        words = trend_board.style_words(self.task)
        self.assertIn("floral", words)
        self.assertNotIn("minimalist", words)

    def test_day8_a_mood_board_is_asked_for_by_the_task_and_a_design_board_keeps_its_caps(self):
        """[§BH62 (d) "forty to sixty retained, not ten"] only a task that asks for a mood board gets its caps."""
        from django.conf import settings as live
        from apps.pipeline.services import trend_board
        self.assertEqual(trend_board.caps_for(self.task)["pictures"], live.TREND_PICTURES_MAX)
        self.task.options = {"trend_scale": trend_board.MOOD_BOARD}
        caps = trend_board.caps_for(self.task)
        self.assertEqual(caps, dict(live.TREND_MOOD_BOARD_CAPS))
        self.assertGreaterEqual(caps["pictures"], 40)
        mood = [s for s in trend_board.plan(self.task) if s.get("source") == "mood_board"]
        self.assertEqual(len(mood), len(trend_board.MOOD_BOARD_QUERIES))
        self.assertTrue(all("packaging" not in s["query"] for s in mood))
        self.task.options = {}
        self.assertFalse([s for s in trend_board.plan(self.task) if s.get("source") == "mood_board"])

    def test_packaging_of_the_world_is_a_link_said_as_measured_and_a_pageless_picture_claims_no_host(self):
        """Measured 2026-09-28 on the one real board (research/trends/real_run.json): Packaging of the World answered
        the page request with a 307 and no Location — a challenge, not its page — and its robots.txt asks 60 s between
        two requests, so the board's pictures waited out its minute and got nothing. Its finds are links, said as
        measured, and nothing of it is fetched. A picture the searches gave without its page is said as that and no
        more: the real run's came as often from the searched platform's own hosts as from others."""
        from apps.pipeline.models import TrendBoard, TrendPick
        platforms = self._platforms()
        platforms["packagingoftheworld.com"] = _payload(results=[
            {"url": "https://packagingoftheworld.com/2026/07/denim-blossom.html", "title": "Denim Blossom",
             "content": "", "score": 0.9, "images": []}],
            images=["https://i0.wp.com/packagingoftheworld.com/wp-content/uploads/2026/07/1.jpg"])

        def robots(url, ua):
            if "packagingoftheworld" in url:
                return {"verdict": "allowed", "crawl_delay": 60.0}
            if "blocked" in url:
                return "disallowed"
            return "allowed"
        board, _c = self._build(connector=_TrendConnector(by_domain=platforms, open_web=self._open_web()),
                                robots=robots)            # its page is not served: fetching it fails the build
        self.assertEqual(board.status, TrendBoard.READY)
        (found,) = board.picks.filter(platform="packaging_of_the_world")
        self.assertEqual((found.kind, found.page_url, found.used),
                         (TrendPick.LINK, "https://packagingoftheworld.com/2026/07/denim-blossom.html", False))
        words = board.refusals["packaging_of_the_world"]["words"]
        for said in ("an empty redirect instead of its page", "a minute between requests", "links you can open"):
            self.assertIn(said, words)
        pageless = board.refusals["source_unknown"]
        self.assertEqual(pageless["count"], 2)            # loose.png, and the picture on Packaging of the World's CDN
        self.assertIn("came with no page it was found on", pageless["words"])
        self.assertNotIn("other than", pageless["words"])

    def test_the_dieline_and_behance_stay_links_their_terms_respected_and_the_board_no_longer_asks(self):
        """His answer of 2026-09-29 to the §BH71 report, (1): "The Dieline and Behance stay links. Respect their terms."
        The board said their pictures waited on his word; it says now that their terms are respected and their finds
        are links — and nothing of either is fetched."""
        from apps.pipeline.services import trend_board
        from django.conf import settings
        for key, terms in (("the_dieline", "terms forbid automated collection"),
                           ("behance", "forbid automated data gathering")):
            words = trend_board.LINK_WORDS[key]
            self.assertEqual(settings.TREND_PLATFORM_MODES[key], trend_board.LINK)
            for said in (terms, "they are respected", "links you can open"):
                self.assertIn(said, words)
            for asked in ("until you say", "may be fetched"):
                self.assertNotIn(asked, words)

    def test_a_picture_read_before_costs_nothing(self):
        from apps.pipeline.models import ApiCallRecord, InspirationReading
        from apps.pipeline.services import inspiration
        InspirationReading.objects.create(sha256=inspiration.sha256_of(_picture(1)), reading=self.READING)
        self._build()
        self.assertEqual(ApiCallRecord.objects.filter(task=self.task, operation="trend_read").count(), 1)

    def test_a_worker_killed_mid_build_resumes_without_repeating_a_search(self):
        from apps.pipeline.models import TrendBoard, WebAccessRecord
        dying = _TrendConnector(by_domain=self._platforms(), open_web=self._open_web(), fail_after=2,
                                failure=_WorkerDied())
        with pytest.raises(_WorkerDied):
            self._build(connector=dying)
        board = TrendBoard.objects.get(task=self.task)
        self.assertEqual((board.status, len(board.searches)), (TrendBoard.BUILDING, 2))
        board, again = self._build()
        self.assertEqual(board.status, TrendBoard.READY)
        self.assertEqual(len(again.calls), 11)                              # the other eleven, and only them
        self.assertEqual(WebAccessRecord.objects.filter(session=board.session, kind="search").count(), 13)

    def test_a_result_with_no_picture_of_its_own_gives_the_one_its_page_declares(self):
        """Measured 2026-09-28 (research/trends/probe_call.json): a Dribbble-scoped search returned every result's own
        picture list empty. The picture is the one the page declares for itself, read under every guard: the page's
        robots.txt, then the picture's host's."""
        from apps.pipeline.models import TrendPick, WebAccessRecord
        platforms = self._platforms()
        platforms["dribbble.com"] = _payload(results=[
            {"url": "https://dribbble.com/shots/201-rose", "title": "rose", "content": "", "score": 0.9,
             "images": []},
            {"url": "https://dribbble.com/shots/202-elsewhere", "title": "x", "content": "", "score": 0.8,
             "images": []},
            {"url": "https://dribbble.com/private/203", "title": "y", "content": "", "score": 0.7, "images": []}])
        served = {**self._served(),
                  "https://dribbble.com/shots/201-rose": _page_declaring("https://cdn.dribbble.com/userupload/201.png"),
                  "https://cdn.dribbble.com/userupload/201.png": _Served(_picture(7)),
                  "https://dribbble.com/shots/202-elsewhere": _page_declaring("https://blocked.example.com/202.png")}

        def robots(url, ua):
            if "blocked" in url or "/private/" in url:
                return "disallowed"
            return "allowed"
        board, _c = self._build(connector=_TrendConnector(by_domain=platforms, open_web=self._open_web()),
                                robots=robots, served=served)
        picks = {p.page_url: p for p in board.picks.filter(kind=TrendPick.PICTURE, platform="dribbble")}
        taken = picks["https://dribbble.com/shots/201-rose"]
        self.assertEqual(taken.image_url, "https://cdn.dribbble.com/userupload/201.png")   # never the avatar
        self.assertTrue(taken.sha256 and taken.used)
        refused = picks["https://dribbble.com/shots/202-elsewhere"]
        self.assertEqual(refused.image_url, "https://blocked.example.com/202.png")
        self.assertEqual(refused.sha256, "")
        self.assertIn("robots.txt disallows", refused.unread_reason)
        never = picks["https://dribbble.com/private/203"]
        self.assertEqual(never.image_url, "")                              # its page was never read
        self.assertIn("its page", never.unread_reason)
        self.assertTrue(WebAccessRecord.objects.filter(session=board.session, kind="policy_block",
                                                       url="https://dribbble.com/private/203").exists())
        self.assertTrue(WebAccessRecord.objects.filter(session=board.session, kind="page_fetch",
                                                       url="https://dribbble.com/shots/201-rose").exists())

    def test_a_logo_sized_picture_and_a_sites_default_picture_are_never_kept(self):
        from apps.pipeline.models import TrendPick
        platforms = self._platforms()
        platforms["dribbble.com"] = _payload(results=[
            {"url": "https://dribbble.com/tags/a", "title": "a", "content": "", "score": 0.9, "images": []},
            {"url": "https://dribbble.com/tags/b", "title": "b", "content": "", "score": 0.8, "images": []},
            {"url": "https://dribbble.com/tags/c", "title": "c", "content": "", "score": 0.7, "images": []}])
        served = {**self._served(),
                  "https://dribbble.com/tags/a": _page_declaring("https://cdn.dribbble.com/default.png"),
                  "https://dribbble.com/tags/b": _page_declaring("https://cdn.dribbble.com/default-again.png"),
                  "https://dribbble.com/tags/c": _page_declaring("https://cdn.dribbble.com/logo.png"),
                  "https://cdn.dribbble.com/default.png": _Served(_picture(9)),
                  "https://cdn.dribbble.com/default-again.png": _Served(_picture(9)),      # the same bytes
                  "https://cdn.dribbble.com/logo.png": _Served(_picture(3, side=8))}
        board, _c = self._build(connector=_TrendConnector(by_domain=platforms, open_web=self._open_web()),
                                served=served)
        picks = {p.page_url: p for p in board.picks.filter(kind=TrendPick.PICTURE, platform="dribbble")}
        self.assertTrue(picks["https://dribbble.com/tags/a"].sha256)
        self.assertIn("the same picture as number", picks["https://dribbble.com/tags/b"].unread_reason)
        self.assertIn("a logo", picks["https://dribbble.com/tags/c"].unread_reason)

    @override_settings(TREND_FETCH_BUDGET_S=10)
    def test_a_host_that_would_keep_the_board_waiting_past_its_time_is_deferred_by_name(self):
        from apps.pipeline.models import TrendPick
        platforms = self._platforms()
        platforms["dribbble.com"]["results"][1]["images"] = ["https://cdn.dribbble.com/userupload/3.png"]
        served = {**self._served(), "https://cdn.dribbble.com/userupload/3.png": _Served(_picture(3))}

        def slow_host(url, ua):
            if "dribbble" in url:
                return {"verdict": "allowed", "crawl_delay": 30.0}
            return "allowed"
        board, _c = self._build(connector=_TrendConnector(by_domain=platforms, open_web=self._open_web()),
                                robots=slow_host, served=served)
        dribbble = list(board.picks.filter(kind=TrendPick.PICTURE, platform="dribbble").order_by("number"))
        self.assertTrue(dribbble[0].sha256)                                 # the first request waits for nothing
        self.assertEqual(dribbble[1].sha256, "")
        self.assertIn("would pass the 10 s", dribbble[1].unread_reason)

    def _ready_board(self):
        from apps.pipeline.models import InspirationReading, TrendBoard, TrendPick
        board = TrendBoard.objects.create(task=self.task, status=TrendBoard.READY, subject="cosmetic compact")
        picks = []
        for n, platform in ((1, "dribbble"), (2, "open_web"), (3, "packaging_of_the_world")):
            sha = ("%d" % n) * 64
            reading = dict(self.READING, take="take number %d" % n)
            InspirationReading.objects.create(sha256=sha, reading=reading)
            picks.append(TrendPick.objects.create(board=board, number=n, kind=TrendPick.PICTURE, platform=platform,
                                                  page_url="https://example.org/%d" % n, title="ACME %d" % n,
                                                  image_url="https://example.org/%d.png" % n, sha256=sha,
                                                  used=True))
        picks.append(TrendPick.objects.create(board=board, number=4, kind=TrendPick.LINK, platform="pinterest",
                                              page_url="https://www.pinterest.com/pin/9/", title="a pin"))
        return board, picks

    def test_an_untick_counts_until_the_press_and_the_press_snapshots_the_ticks_once(self):
        from apps.pipeline.models import TrendBoard
        from apps.pipeline.services import trend_board
        board, picks = self._ready_board()
        trend_board.toggle(self.task, picks[1].pk, False)
        with self.assertRaises(trend_board.TrendBoardClosed) as link:
            trend_board.toggle(self.task, picks[3].pk, True)
        self.assertIn("link card", link.exception.words)
        self.assertTrue(trend_board.confirm(self.task, trend_board.BY_HIS_CLICK))
        board.refresh_from_db()
        self.assertEqual((board.status, board.confirmed_how), (TrendBoard.CONFIRMED, trend_board.BY_HIS_CLICK))
        self.assertEqual(board.used_at_confirm, [picks[0].pk, picks[2].pk])
        self.assertFalse(trend_board.confirm(self.task, trend_board.BY_THE_WINDOW))    # once
        with self.assertRaises(trend_board.TrendBoardClosed):
            trend_board.toggle(self.task, picks[0].pk, False)               # a tick now changes nothing

    def test_the_window_closes_on_the_worker_only_once_it_has_closed_and_one_move_wins(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.pipeline.models import TrendBoard
        from apps.pipeline.services import trend_board
        board, _picks = self._ready_board()
        now = timezone.now()
        board.review_deadline = now + timedelta(seconds=120)
        board.save()
        self.task.status = "awaiting_trend_review"
        self.task.save()
        with patch("apps.pipeline.tasks.run_aria_pipeline.delay") as run:
            self.assertFalse(trend_board.close_if_due(self.task.id, now=now))
            with self.captureOnCommitCallbacks(execute=True):
                self.assertTrue(trend_board.close_if_due(self.task.id, now=now + timedelta(seconds=121)))
            self.assertFalse(trend_board.proceed(self.task.id, trend_board.BY_HIS_CLICK))   # the close won
        run.assert_called_once_with(self.task.id)
        self.task.refresh_from_db()
        board.refresh_from_db()
        self.assertEqual(self.task.status, "queued")
        self.assertEqual((board.status, board.confirmed_how), (TrendBoard.CONFIRMED, trend_board.BY_THE_WINDOW))

    def test_a_concept_close_to_a_used_trend_picture_is_flagged_beside_it_and_nothing_is_removed(self):
        """§BH71 PART 2: "The pictures themselves are never placed, and never near-copied." Each new concept is
        compared with every picture its directions used, by the house's 8×8 average hash; one 10 bits or fewer apart
        is flagged beside the concept — an unticked picture is never compared, and no concept is removed."""
        from django.core.files.base import ContentFile

        from apps.pipeline.models import GeneratedImage, TrendBoard, WebResearchSession, WebSourceRecord
        from apps.pipeline.services import trend_board
        board, picks = self._ready_board()
        session = WebResearchSession.objects.create(product_identity="trend board", modes=["TREND_BOARD"])
        pictures = {}
        for pick, seed in zip(picks[:3], (11, 12, 13)):
            data = _picture(seed)
            path = __import__("pathlib").Path(self.tmp) / ("trend_%d.png" % pick.number)
            path.write_bytes(data)
            pick.source = WebSourceRecord.objects.create(session=session, original_url=pick.image_url,
                                                         classification="image", quarantine_path=str(path))
            pick.save()
            pictures[pick.number] = data
        trend_board.toggle(self.task, picks[2].pk, False)                  # picture 3 unticked
        trend_board.confirm(self.task, trend_board.BY_HIS_CLICK)
        concepts = []
        for n, data in ((1, pictures[1]), (2, _picture(99)), (3, pictures[3])):
            image = GeneratedImage.objects.create(task=self.task, direction_name="d", prompt_used="p",
                                                  variation_number=n)
            image.image_file.save("concept_%d.png" % n, ContentFile(data), save=True)
            concepts.append(image)
        self.assertEqual(trend_board.mark_near_copies(self.task, concepts), 1)
        near = [GeneratedImage.objects.get(pk=c.pk).reference_provenance["trend_near_copy"] for c in concepts]
        self.assertEqual(near[0]["close_to"], [{"number": 1, "platform": "Dribbble", "bits_apart": 0}])
        self.assertEqual(near[1]["close_to"], [])                         # far from both it was compared with
        self.assertEqual(near[2]["close_to"], [])                         # the same as an unticked one: not compared
        self.assertEqual([n["compared_with"] for n in near], [2, 2, 2])
        self.assertTrue(all(n["compared"] for n in near))
        self.assertEqual(GeneratedImage.objects.filter(task=self.task).count(), 3)   # nothing removed
        self.assertEqual(TrendBoard.objects.get(task=self.task).status, TrendBoard.CONFIRMED)

    def test_only_the_ticked_pictures_words_reach_the_directions_never_a_picture_title_or_link(self):
        from apps.pipeline.services import trend_board
        _board, picks = self._ready_board()
        self.assertEqual(trend_board.words_block(self.task), "")            # nothing before the press
        trend_board.toggle(self.task, picks[1].pk, False)
        trend_board.confirm(self.task, trend_board.BY_HIS_CLICK)
        block = trend_board.words_block(self.task)
        self.assertIn("<<trends>>", block)
        self.assertIn("Trend picture 1 (found on Dribbble)", block)
        self.assertIn("take number 1", block)
        self.assertIn("take number 3", block)
        self.assertNotIn("take number 2", block)                            # unticked: not a word of it
        for never in ("ACME", "http", "example.org", "pinterest.com"):
            self.assertNotIn(never, block)
        self.assertIn("copy the same layout", block)

    def test_a_failed_board_is_kept_by_its_type_and_the_spend_cap_still_stops_the_design(self):
        from apps.pipeline.models import TrendBoard
        from apps.pipeline.services.cost_ledger import BudgetExceededError
        board, _c = self._build(connector=_TrendConnector(fail_after=0, failure=RuntimeError("provider said x")))
        self.assertEqual((board.status, board.failure), (TrendBoard.FAILED, "RuntimeError"))
        TrendBoard.objects.all().delete()
        with pytest.raises(BudgetExceededError):
            self._build(connector=_TrendConnector(fail_after=0, failure=BudgetExceededError("cap")))
        self.assertEqual(TrendBoard.objects.get(task=self.task).failure, "BudgetExceededError")

    def test_what_a_board_cost_is_read_from_the_designs_own_ledger_rows(self):
        from decimal import Decimal

        from apps.pipeline.models import ApiCallRecord
        from apps.pipeline.services import trend_board
        for _n in range(3):
            ApiCallRecord.objects.create(task=self.task, provider="tavily", model="search:basic",
                                         operation="trend_search", cost_usd=Decimal("0.008"), metadata={"credits": 1})
        for _n in range(2):
            ApiCallRecord.objects.create(task=self.task, provider="anthropic", model="m", operation="trend_read",
                                         cost_usd=Decimal("0.0096"))
        ApiCallRecord.objects.create(task=self.task, provider="anthropic", model="m", operation="direction_planning",
                                     cost_usd=Decimal("0.05"))
        self.assertEqual(trend_board.cost_of(self.task),
                         {"searches": 3, "credits": 3, "search_usd": "0.024000", "reads": 2,
                          "read_usd": "0.019200", "total_usd": "0.043200"})


class InspirationOnlySessionTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=brand, product_id="BBR-CO-900",
            name="Rose Glow Palette", category="CO", year=2026,
            product_type="compact")

    def _inspiration_plan(self):
        return wr.plan_queries(self.product,
                               modes=[wr.VISUAL_INSPIRATION_DISCOVERY])

    def test_the_default_plan_would_send_an_unreleased_product_identity_and_this_one_does_not(self):
        """THE REASON THE `plan` KWARG EXISTS. Not a style preference — a measured leak.

        `plan_queries_v2` puts `brand`, `name` and `sku` into the EXACT queries. Sending those to a
        third-party search API is a person's decision about a product in the world; it is not something a
        design run should do by itself for a product that has not shipped. The inspiration plan carries the
        product TYPE and nothing that identifies the product.
        """
        default_plan, _ = tv.plan_queries_v2(self.product)
        default_text = " ".join(q for qs in default_plan.values() for q in qs)
        self.assertIn("BBROSE", default_text)
        self.assertIn("Rose Glow Palette", default_text)
        self.assertIn("BBR-CO-900", default_text)

        ours = " ".join(self._inspiration_plan()[wr.VISUAL_INSPIRATION_DISCOVERY])
        self.assertNotIn("BBROSE", ours)
        self.assertNotIn("Rose Glow Palette", ours)
        self.assertNotIn("BBR-CO-900", ours)
        self.assertIn("compact", ours)          # the product TYPE is the whole payload

    def test_a_narrowed_plan_runs_only_its_own_mode_and_never_escalates(self):
        stub = _StubConnector()
        session = tv.run_tavily_session(self.product, connector=stub,
                                        plan=self._inspiration_plan())
        self.assertEqual(session.status, "AWAITING_HUMAN_REVIEW")
        self.assertEqual(list(session.modes), [wr.VISUAL_INSPIRATION_DISCOVERY])
        # every query the connector saw came from the inspiration plan...
        planned = set(self._inspiration_plan()[wr.VISUAL_INSPIRATION_DISCOVERY])
        self.assertTrue(planned)
        self.assertEqual({q for q, _ in stub.calls}, planned)
        # ...and none was an advanced escalation, which is exact-mode only
        self.assertEqual([c for c in stub.calls if c[1] == "advanced"], [])
        self.assertEqual(session.summary["search_calls"]["advanced"], 0)

    def test_it_does_not_report_a_refusal_for_a_search_it_never_ran(self):
        """The unconditional WEB_EXACT_PRODUCT_NOT_FOUND append, corrected here.

        A person reviews this record. Before §BH57(a)5 an inspiration-only session ended carrying a blocked
        source saying no credible exact-product candidate was found — for an exact search that was never
        planned and never made. The three-mode session still reports it, because there it is true.
        """
        stub = _StubConnector()
        session = tv.run_tavily_session(self.product, connector=stub,
                                        plan=self._inspiration_plan())
        codes = [b["code"] for b in session.summary["blocked_sources"]]
        self.assertNotIn(wr.WEB_EXACT_PRODUCT_NOT_FOUND, codes)

        three_mode = tv.run_tavily_session(self.product, connector=_StubConnector())
        self.assertIn(wr.WEB_EXACT_PRODUCT_NOT_FOUND,
                      [b["code"] for b in three_mode.summary["blocked_sources"]])

    def test_what_reaches_the_planner_is_only_what_a_person_approved(self):
        """The module's own rule, and the honest answer about what this wire produces TODAY.

        Sources are retained for review with rights default-deny. `build_web_reference_context` returns only
        APPROVED ones, and the only writer of APPROVED_INSPIRATION is a reviewer-gated page action. So a
        freshly run session gives the planner NOTHING while leaving a real queue behind — and the run reports
        both numbers rather than reporting silence.
        """
        stub = _StubConnector(payloads={
            q: _payload(results=[
                {"url": "https://example.test/%s" % i,
                 "title": "inspiration %s" % i,
                 "content": "a soft cream compact", "score": 0.7}])
            for i, q in enumerate(
                self._inspiration_plan()[wr.VISUAL_INSPIRATION_DISCOVERY])})
        session = tv.run_tavily_session(self.product, connector=stub,
                                        plan=self._inspiration_plan())
        self.assertGreater(session.sources.count(), 0)
        for s in session.sources.all():
            self.assertEqual(s.rights_state, "RIGHTS_UNKNOWN")
            self.assertEqual(s.human_review_state, "UNREVIEWED")
            self.assertEqual(s.access_policy_result,
                             "search_result_only_not_fetched")   # fetch=False: nothing downloaded
        self.assertEqual(wr.build_web_reference_context(session)["sources"], [])

        # and once a person approves one, it is exactly that one the planner gets
        first = session.sources.first()
        first.human_review_state = "APPROVED_INSPIRATION"
        first.save(update_fields=["human_review_state"])
        approved = wr.build_web_reference_context(session)["sources"]
        self.assertEqual([s["source_id"] for s in approved], [first.id])

    def test_a_session_that_dies_on_a_network_error_still_ends_reviewable(self):
        """FOUND BY RUNNING IT, not by reading it. With the §AY1 outbound guard installed, the probe left
        `[(1, 'SEARCHING')]` behind: only `WebPolicyError` was caught, so a refused socket escaped the
        function and froze the row it had already created — no summary, no hash, and absent from a review
        screen that lists AWAITING_HUMAN_REVIEW and BLOCKED.

        The wire is what makes this matter: a design run now opens a session by itself, so a machine with no
        network would accumulate frozen rows silently. Every exit is terminal now.
        """
        class _Dead(_StubConnector):
            def search(self, query, *, depth="basic", max_results=8):
                raise ConnectionRefusedError("api.tavily.com:443")

        session = tv.run_tavily_session(self.product, connector=_Dead(),
                                        plan=self._inspiration_plan())
        self.assertEqual(session.status, "BLOCKED")
        self.assertIn("BLOCKED", session.summary["state_trail"])
        self.assertTrue(session.session_hash)
        blocked = session.summary["blocked_sources"]
        self.assertEqual([b["code"] for b in blocked],
                         [wr.WEB_SEARCH_PROVIDER_UNAVAILABLE])
        # the TYPE, never the message: a provider error can echo the request, and the request carries the key
        self.assertEqual(blocked[0]["detail"], "session aborted: ConnectionRefusedError")
        self.assertNotIn("api.tavily.com:443", str(session.summary))
        self.assertEqual(
            WebAccessRecord.objects.filter(session=session,
                                           kind="policy_block").count(), 1)


class TrendLinkTitleTests(TestCase):
    """[His goal of 2026-10-10, item 3: "Only keep trend pictures that actually show THIS product type ... Drop generic
    cosmetics shots, other products ..., charts, logos and text pages ... show nothing rather than junk."] A link is
    judged by its title alone, never seen: 124's board, searched again on the live code, kept "Pantone Announces
    AI-Powered Palette Generator" and a Dribbble search for "Pastel Colour Palette" as eyeshadow palettes — "palette"
    alone named them."""

    def test_goal_1010_item3_a_link_names_the_product_in_full_and_is_one_design_never_a_listing_or_a_page_gone(self):
        from apps.pipeline.models import TrendBoard, TrendPick
        from apps.pipeline.services import trend_board
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        palette = DesignTask.objects.create(task_text=TrendBoardTests.BRIEF_124, status="running", brand=brand,
                                            design_target="product_container")
        board = TrendBoard.objects.create(task=palette, status=TrendBoard.READY,
                                          subject="illustrated eyeshadow palette fairytale")
        rows = [  # (kind, address, title, why it was not fetched)
            (TrendPick.LINK, "https://thedieline.com/pantone-announces-ai-powered-palette-generator",
             "Pantone Announces AI-Powered Palette Generator - DIELINE", ""),
            (TrendPick.PICTURE, "https://dribbble.com/search/pastel-colour-palette",
             "Browse thousands of Pastel Colour Palette images for design inspiration | Dribbble",
             "not fetched — its page: HTTP 202"),
            (TrendPick.LINK, "https://www.pinterest.com/ideas/eyeshadow-palette-photography/944370740869",
             "Eyeshadow Palette Photography", ""),
            (TrendPick.LINK, "https://www.behance.net/search/projects/eyeshadow%20palette",
             "Eyeshadow Palette Projects :: Photos, videos, logos, illustrations and branding", ""),
            (TrendPick.PICTURE, "https://www.target.com/p/too-faced-life-39-s-a-fairytale-mini-eyeshadow-palette",
             "Too Faced Life's A Fairytale Mini Eyeshadow Palette - 0.2oz", "not fetched — its page: HTTP 404"),
            (TrendPick.PICTURE, "https://www.ebay.com/itm/156556027485",
             "OKALAN  Fairytale Land Eyeshadow Palette 30 Colors | eBay",
             "not fetched — its page: HTTP 403 — source denial respected, no bypass attempted"),
            (TrendPick.LINK, "https://www.instagram.com/p/Dd_nY5qoHt0", "A fairytale eye shadow palette, hand drawn", ""),
        ]
        for n, (kind, url, title, why) in enumerate(rows, 1):
            TrendPick.objects.create(board=board, number=n, kind=kind, platform="open_web", page_url=url, title=title,
                                     unread_reason=why)
        self.assertEqual(trend_board.title_terms(trend_board.product_terms(palette)), ("eyeshadow palette",))
        self.assertEqual(trend_board.title_terms(("box", "carton")), ("box", "carton"))
        shown = trend_board.payload(palette)
        self.assertEqual([link["title"][:12] for link in shown["links"]], ["OKALAN  Fair", "A fairytale "])
        left = {row["words"]: row["count"] for row in shown["left_out"]}
        self.assertEqual(left.get("a link whose title names no eyeshadow palette"), 1)              # Pantone's
        self.assertEqual(left.get("a search or a listing page, not one design"), 3)
        self.assertEqual(left.get("a page that is gone"), 1)
        # a picture's reader saw it: its own word for the product still keeps it ("makeup palette", "eye shadow
        # palette" run together or apart)
        terms = trend_board.product_terms(palette)
        self.assertTrue(trend_board.names_the_product("makeup palette", terms))
        self.assertTrue(trend_board.names_the_product("eye shadow palette", ("eyeshadow palette",)))
        self.assertFalse(trend_board.names_the_product("colour palette generator", ("eyeshadow palette",)))
