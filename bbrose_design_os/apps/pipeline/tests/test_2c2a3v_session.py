"""2C-2A-CORR-3V — real-session machinery: replacement linkage, governed
fetch, retention caps, duplicate control, image safety, conflicts, packet.
All network I/O is stubbed; literal TEST-NET IPs avoid DNS entirely."""
from __future__ import annotations

import io
import json
import shutil
import tempfile
from pathlib import Path

import pytest
from django.test import TestCase, override_settings

from apps.core.models import Brand, Product
from apps.pipeline.models import (WebAccessRecord, WebResearchSession,
                                  WebSourceRecord)
from apps.pipeline.services import web_research as wr
from apps.pipeline.services import web_research_tavily as tv
from apps.pipeline.services import round_designer as rd


def _payload(results=None, images=None):
    return {"results": results or [], "images": images or [],
            "answer": "", "request_id": "resp-1", "usage": {"credits": 1}}


class _StubConnector(rd.TavilySearchConnector):
    def __init__(self, payloads=None):
        super().__init__()
        self.calls = []
        self.payloads = payloads or {}

    def search(self, query, *, depth="basic", max_results=8):
        self.calls.append((query, depth))
        return self.normalize(query, self.payloads.get(query, _payload()),
                              latency_ms=5, request_id="req-1")


class _FakeResponse:
    def __init__(self, status=200, headers=None, body=b""):
        self.status_code = status
        self.headers = headers or {}
        self._body = body

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        pass


def _stub_http_get(responses: dict, captured: list | None = None):
    def get(url, *, headers, timeout):
        if captured is not None:
            captured.append({"url": url, "headers": dict(headers)})
        resp = responses.get(url)
        if resp is None:
            raise AssertionError(f"unexpected fetch: {url}")
        return resp
    return get


def _png(seed=0) -> bytes:
    """Distinct seeds → distinct average-hashes (uniform fills would all
    hash identically, so vary WHERE the bright pixels sit)."""
    from PIL import Image
    img = Image.new("L", (8, 8), 0)
    for k in range(3):
        img.putpixel(((seed * 3 + k) % 8, (seed + 2 * k) % 8), 255)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _product():
    brand = Brand.objects.create(name="BBROSE", master_brief="x")
    return Product.objects.create(
        brand=brand, product_id="BBR-SK-201",
        name="Rose Damascena Night Repair Oil", category="SK", year=2026,
        product_type="carton", width_mm=40, depth_mm=40, height_mm=110)


class GovernedFetchUnitTests(TestCase):
    CONFIG = None

    def setUp(self):
        self.config = wr.gateway_config()

    def test_byte_ceiling_enforced(self):
        get = _stub_http_get({"http://93.184.216.34/big": _FakeResponse(
            headers={"content-type": "text/html"}, body=b"x" * 200)})
        with pytest.raises(wr.WebPolicyError) as exc:
            wr.governed_fetch("http://93.184.216.34/big", self.config,
                              http_get=get, byte_limit=100)
        assert exc.value.code == wr.WEB_FETCH_SIZE_LIMIT

    def test_mime_allowlist_enforced(self):
        get = _stub_http_get({"http://93.184.216.34/app.js": _FakeResponse(
            headers={"content-type": "application/javascript"},
            body=b"alert(1)")})
        with pytest.raises(wr.WebPolicyError) as exc:
            wr.governed_fetch("http://93.184.216.34/app.js", self.config,
                              http_get=get)
        assert exc.value.code == wr.WEB_UNSUPPORTED_CONTENT_TYPE

    def test_redirect_to_loopback_blocked_per_hop(self):
        get = _stub_http_get({"http://93.184.216.34/r": _FakeResponse(
            status=301, headers={"location": "http://127.0.0.1/x"})})
        with pytest.raises(wr.WebPolicyError) as exc:
            wr.governed_fetch("http://93.184.216.34/r", self.config,
                              http_get=get)
        assert exc.value.code == wr.WEB_SECURITY_POLICY_BLOCKED

    def test_redirect_hop_limit(self):
        get = _stub_http_get(
            {f"http://93.184.216.34/hop{i}": _FakeResponse(
                status=302,
                headers={"location": f"http://93.184.216.34/hop{i + 1}"})
             for i in range(0, 12)})
        with pytest.raises(wr.WebPolicyError) as exc:
            wr.governed_fetch("http://93.184.216.34/hop0", self.config,
                              http_get=get)
        assert exc.value.code == wr.WEB_SECURITY_POLICY_BLOCKED
        assert "redirect" in str(exc.value)

    def test_source_denial_respected_never_bypassed(self):
        get = _stub_http_get({"http://93.184.216.34/paywalled": _FakeResponse(
            status=403, headers={"content-type": "text/html"})})
        with pytest.raises(wr.WebPolicyError) as exc:
            wr.governed_fetch("http://93.184.216.34/paywalled", self.config,
                              http_get=get)
        assert exc.value.code == wr.WEB_SOURCE_ACCESS_DENIED
        assert "no bypass" in str(exc.value)

    def test_normalize_url_duplicate_canon(self):
        a = wr.normalize_url("https://Shop.Example/p/1/?utm_source=x&b=2#f")
        b = wr.normalize_url("https://shop.example/p/1?b=2")
        assert a == b


class SessionLinkageAndCapsTests(TestCase):
    def setUp(self):
        self.product = _product()

    def test_replacement_linkage_and_state_trail(self):
        b1 = WebResearchSession.objects.create(
            product_identity="x", candidate_id="BBR-SK-201",
            modes=[], status="BLOCKED")
        b2 = WebResearchSession.objects.create(
            product_identity="x", candidate_id="BBR-SK-201",
            modes=[], status="BLOCKED")
        session = tv.run_tavily_session(self.product,
                                        connector=_StubConnector())
        link = session.summary["replacement_of"]
        assert link["prior_blocked_session_ids"] == [b1.id, b2.id]
        assert link["relationship"] == "REPLACEMENT_OF_BLOCKED_SESSION"
        assert link["connector_version"] == rd.CONNECTOR_VERSION
        assert link["query_planner_version"] == tv.PLANNER_VERSION
        assert link["limits"]["max_queries"] == 12
        assert session.summary["state_trail"] == [
            "PLANNED", "SEARCHING", "AWAITING_HUMAN_REVIEW"]
        b1.refresh_from_db()
        b2.refresh_from_db()
        assert b1.status == "BLOCKED" and b2.status == "BLOCKED"

    def test_per_mode_retention_cap_and_wrong_product_cap(self):
        analog_results = [
            {"url": f"https://supplier{i}.example/bottle-{i}",
             "title": f"serum bottle {i}", "content": "30 ml", "score": 0.5}
            for i in range(15)]
        wrong_results = [
            {"url": f"https://wrong{i}.example/cream-{i}",
             "title": "vitamin C day cream", "content": "", "score": 0.9}
            for i in range(8)]
        stub = _StubConnector(payloads={
            "night repair serum bottle": _payload(results=analog_results),
            "BBROSE Rose Damascena Night Repair Oil":
                _payload(results=wrong_results)})
        session = tv.run_tavily_session(self.product, connector=stub)
        assert session.sources.filter(classification="analog").count() == \
            tv.MODE_RETENTION_CAPS["analog"]
        assert session.sources.filter(classification="exact").count() == \
            tv.WRONG_PRODUCT_RETENTION_CAP
        assert session.summary["dropped_by_retention_cap"] >= 8

    def test_url_dedup_across_queries(self):
        result = [{"url": "https://mirror.example/serum?utm_source=x",
                   "title": "30 ml serum bottle", "content": "", "score": 0.7}]
        result2 = [{"url": "https://mirror.example/serum",
                    "title": "30 ml serum bottle", "content": "",
                    "score": 0.7}]
        stub = _StubConnector(payloads={
            "night repair serum bottle": _payload(results=result),
            "airless serum bottle": _payload(results=result2)})
        session = tv.run_tavily_session(self.product, connector=stub)
        assert session.sources.filter(classification="analog").count() == 1
        groups = session.summary["duplicate_groups"]
        assert len(groups) == 1 and groups[0]["method"] == "normalized_url"

    def test_discovery_only_default_never_fetches(self):
        stub = _StubConnector(payloads={
            "night repair serum bottle": _payload(
                results=[{"url": "http://93.184.216.34/a", "title": "b",
                          "content": "", "score": 0.5}])})
        boom = _stub_http_get({})       # raises on ANY fetch
        session = tv.run_tavily_session(self.product, connector=stub,
                                        http_get=boom)   # fetch defaults off
        src = session.sources.get()
        assert src.access_policy_result == "search_result_only_not_fetched"
        assert session.summary["fetches"]["pages_fetched"] == 0


@override_settings(WEB_SEARCH_API_KEY="")
class FetchPhaseTests(TestCase):
    def setUp(self):
        self.product = _product()
        self.tmp = tempfile.mkdtemp(prefix="webq_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, payloads, responses, robots="allowed", captured=None):
        with override_settings(WEB_QUARANTINE_ROOT=self.tmp):
            return tv.run_tavily_session(
                self.product, connector=_StubConnector(payloads=payloads),
                fetch=True, http_get=_stub_http_get(responses, captured),
                robots=lambda url, ua: robots, delay_s=0)

    def test_fetch_quarantines_and_mines_page_facts(self):
        url = "http://93.184.216.34/serum-a"
        captured = []
        session = self._run(
            {"night repair serum bottle": _payload(
                results=[{"url": url, "title": "30 ml serum bottle",
                          "content": "", "score": 0.8}])},
            {url: _FakeResponse(headers={"content-type": "text/html"},
                                body=b"<html><script>x()</script>"
                                     b"<body>30 ml bottle 100mm tall"
                                     b"</body></html>")},
            captured=captured)
        src = session.sources.get(classification="analog")
        assert src.access_policy_result == "fetched_quarantined"
        assert src.http_status == 200 and src.mime_type == "text/html"
        assert src.content_sha256 and src.byte_count > 0
        assert Path(src.quarantine_path).exists()
        assert str(Path(src.quarantine_path).resolve()).startswith(
            str(Path(self.tmp).resolve()))
        page_facts = [f for f in src.facts
                      if f.get("supporting_location") == "fetched_page_text"]
        assert any(f["units"] == "mm" for f in page_facts)
        assert all(f["namespace"] == "analog_feasibility"
                   for f in src.facts)
        assert all(f["verification_state"] == "UNREVIEWED"
                   for f in src.facts)
        assert WebAccessRecord.objects.filter(
            session=session, kind="page_fetch", outcome="ok").count() == 1
        # §6 headers: our declared UA, no credential material
        declared_ua = wr.gateway_config()["user_agent"]
        for call in captured:
            assert call["headers"]["User-Agent"] == declared_ua
            assert "Authorization" not in call["headers"]
            assert not any("api_key" in k.lower() or "tavily" in
                           str(v).lower() for k, v in
                           call["headers"].items())
        assert session.status == "AWAITING_HUMAN_REVIEW"

    def test_robots_disallowed_respected_as_provenance(self):
        url = "http://93.184.216.34/serum-b"
        session = self._run(
            {"night repair serum bottle": _payload(
                results=[{"url": url, "title": "serum bottle", "content": "",
                          "score": 0.8}])},
            {}, robots="disallowed")
        src = session.sources.get(classification="analog")
        assert src.access_policy_result == "robots_disallowed"
        assert src.robots_result == "disallowed"
        assert WebAccessRecord.objects.filter(
            session=session, kind="policy_block",
            outcome=wr.WEB_ROBOTS_DISALLOWED).exists()
        assert session.summary["fetches"]["pages_fetched"] == 0
        assert session.summary["fetches"]["denied"] == 1

    def test_redirect_to_private_target_blocked(self):
        url = "http://93.184.216.34/serum-c"
        session = self._run(
            {"night repair serum bottle": _payload(
                results=[{"url": url, "title": "serum bottle", "content": "",
                          "score": 0.8}])},
            {url: _FakeResponse(status=301,
                                headers={"location": "http://127.0.0.1/x"})})
        src = session.sources.get(classification="analog")
        assert src.access_policy_result == \
            f"fetch_blocked:{wr.WEB_SECURITY_POLICY_BLOCKED}"
        assert session.summary["fetches"]["pages_fetched"] == 0

    def test_image_caps_styling_default_and_phash_dedup(self):
        # img0/img1 identical (phash dup); img2/img4/img5/img6 identical;
        # img3 unique; the second domain unique
        seeds = {0: 0, 1: 0, 2: 1, 3: 2, 4: 1, 5: 1, 6: 1}
        images = ([{"url": f"http://93.184.216.34/img{i}.png",
                    "description": "bottle with water droplets"}
                   for i in range(7)] +
                  [{"url": "http://93.184.216.35/other.png",
                    "description": "serum bottle on marble"}])
        responses = {f"http://93.184.216.34/img{i}.png": _FakeResponse(
            headers={"content-type": "image/png"}, body=_png(seeds[i]))
            for i in range(7)}
        responses["http://93.184.216.35/other.png"] = _FakeResponse(
            headers={"content-type": "image/png"}, body=_png(5))
        session = self._run(
            {"night repair serum bottle": _payload(images=images)},
            responses)
        image_sources = session.sources.filter(classification="image")
        # 7 same-domain candidates → ≤5 per domain; phash dedup collapses
        # identical bodies; the second domain always lands
        per_domain = image_sources.filter(domain="93.184.216.34").count()
        assert per_domain <= 5
        assert image_sources.filter(domain="93.184.216.35").count() == 1
        dup_methods = {g["method"] for g in
                       session.summary["duplicate_groups"]}
        assert "image_phash" in dup_methods
        src = image_sources.filter(domain="93.184.216.34").first()
        cls = [w for w in src.extraction_warnings
               if isinstance(w, dict)
               and w.get("kind") == "image_element_classification"][0]
        elements = cls["elements"]
        assert elements["_policy"] == wr.STYLING_DEFAULT
        assert elements["bottle with water droplets"] == \
            "photographic_styling"
        assert src.facts == []                       # never fact sources
        assert src.rights_state == "RIGHTS_UNKNOWN"
        assert not src.provider_input_permission
        assert not src.artwork_reuse_permission

    def test_exact_namespace_conflicts_marked_never_averaged(self):
        session = WebResearchSession.objects.create(
            product_identity="x", candidate_id="BBR-SK-201", modes=[],
            status="FETCHING")
        f = {"schema_version": wr.FACT_SCHEMA, "namespace": "exact",
             "fact": "capacity", "raw": "30 ml", "normalized": 30.0,
             "units": "ml", "source_tier": 3, "authority": "",
             "extraction_method": "regex",
             "verification_state": "UNREVIEWED", "conflict_state": "",
             "human_decision": ""}
        s1 = session.sources.create(
            original_url="https://a.example/1", domain="a.example",
            classification="exact", facts=[dict(f)])
        s2 = session.sources.create(
            original_url="https://b.example/2", domain="b.example",
            classification="exact",
            facts=[{**f, "raw": "50 ml", "normalized": 50.0}])
        s3 = session.sources.create(
            original_url="https://c.example/3", domain="c.example",
            classification="analog",
            facts=[{**f, "namespace": "analog_feasibility",
                    "raw": "100 ml", "normalized": 100.0}])
        summary = {"conflicting_facts": []}
        tv.mark_exact_fact_conflicts(session, summary)
        s1.refresh_from_db()
        s2.refresh_from_db()
        s3.refresh_from_db()
        assert s1.facts[0]["conflict_state"] == "CONFLICTED"
        assert s2.facts[0]["conflict_state"] == "CONFLICTED"
        assert s3.facts[0]["conflict_state"] == ""      # analogs never clash
        assert summary["conflicting_facts"][0]["values"] == [30.0, 50.0]
        assert "never averaged" in \
            summary["conflicting_facts"][0]["resolution"]


class RobotsReadAsRfc9309Tests(TestCase):
    """§BH71 PART 2, before a trend board fetches any picture: a robots.txt read as RFC 9309 reads it, and obeyed on
    every host a fetch touches. Measured by the research leaf: the standard library's parser answered "allowed" for
    Behance's `/search/*?*sort=*`, Dribbble's `/shots/*/comments` and `/log$`; an unreadable robots.txt let a fetch
    go ahead; an image's own host and a redirect's new host were never asked; a Crawl-delay was never read."""

    UA = "BBROSE-DesignOS-ResearchBot/1.0 (+contact: x)"

    def setUp(self):
        self.product = _product()
        self.tmp = tempfile.mkdtemp(prefix="webq_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_wildcards_an_end_anchor_the_longest_rule_and_the_crawlers_own_group(self):
        behance = "User-agent: *\nDisallow: /v2/\nDisallow: /search/*?*sort=*\n"
        assert not wr.robots_rules(behance, self.UA, "/search/projects?sort=appreciations")["allowed"]
        assert wr.robots_rules(behance, self.UA, "/gallery/123/Rose-Serum")["allowed"]
        dribbble = "User-agent: *\nDisallow: /shots/*/comments\n"
        assert not wr.robots_rules(dribbble, self.UA, "/shots/123-rose/comments")["allowed"]
        assert wr.robots_rules(dribbble, self.UA, "/shots/123-rose")["allowed"]
        log = "User-agent: *\nDisallow: /log$\n"
        assert not wr.robots_rules(log, self.UA, "/log")["allowed"] and wr.robots_rules(log, self.UA, "/logo.png")["allowed"]
        longest = "User-agent: *\nDisallow: /a\nAllow: /a/b\n"
        assert wr.robots_rules(longest, self.UA, "/a/b/c")["allowed"]
        assert not wr.robots_rules(longest, self.UA, "/a/c")["allowed"]
        assert wr.robots_rules("User-agent: *\nDisallow: /p\nAllow: /p\n", self.UA, "/p")["allowed"]   # a tie: Allow
        named = ("User-agent: GPTBot\nDisallow: /\n\nUser-agent: bbrose-designos-researchbot\nDisallow: /private\n\n"
                 "User-agent: *\nDisallow: /\n")
        assert wr.robots_rules(named, self.UA, "/shots/1")["allowed"]              # our own group, not the '*'
        assert not wr.robots_rules(named, self.UA, "/private/x")["allowed"]
        assert wr.robots_rules("User-agent: *\nDisallow: /\n", self.UA, "/robots.txt")["allowed"]
        assert wr.robots_rules("User-agent: *\nCrawl-delay: 60\n", self.UA, "/")["crawl_delay"] == 60.0
        assert wr.robots_rules("User-agent: *\nDisallow:\n", self.UA, "/anything")["allowed"]   # empty: nothing

    def test_an_unreadable_robots_file_is_a_refusal_never_a_permission(self):
        down = _stub_http_get({"http://93.184.216.34/robots.txt": _FakeResponse(status=503)})
        assert wr.robots_check("http://93.184.216.34/x", self.UA, http_get=down)["verdict"] == "unavailable"
        gone = _stub_http_get({"http://93.184.216.34/robots.txt": _FakeResponse(status=404)})
        assert wr.robots_check("http://93.184.216.34/x", self.UA, http_get=gone)["verdict"] == "allowed"
        url = "http://93.184.216.34/serum-u"
        with override_settings(WEB_QUARANTINE_ROOT=self.tmp):
            session = tv.run_tavily_session(
                self.product, connector=_StubConnector(payloads={"night repair serum bottle": _payload(
                    results=[{"url": url, "title": "serum bottle", "content": "", "score": 0.8}])}),
                fetch=True, http_get=_stub_http_get({}), robots=lambda u, ua: "unavailable", delay_s=0)
        src = session.sources.get(classification="analog")
        assert src.access_policy_result == "robots_unreadable" and session.summary["fetches"]["pages_fetched"] == 0
        assert WebAccessRecord.objects.filter(session=session, kind="policy_block",
                                              outcome=wr.WEB_ROBOTS_UNREADABLE).exists()

    def test_an_images_own_host_is_asked_and_its_refusal_kept(self):
        images = [{"url": "http://93.184.216.36/refused.png", "description": "serum bottle"},
                  {"url": "http://93.184.216.35/open.png", "description": "serum bottle"}]
        responses = {"http://93.184.216.35/open.png": _FakeResponse(headers={"content-type": "image/png"},
                                                                    body=_png(3))}

        def robots(u, ua):
            return "disallowed" if "93.184.216.36" in u else "allowed"
        with override_settings(WEB_QUARANTINE_ROOT=self.tmp):
            session = tv.run_tavily_session(
                self.product, connector=_StubConnector(payloads={"night repair serum bottle": _payload(
                    images=images)}), fetch=True, http_get=_stub_http_get(responses), robots=robots, delay_s=0)
        fetched = {s.domain for s in session.sources.filter(classification="image")}
        assert fetched == {"93.184.216.35"}, fetched                     # the refusing host never fetched
        assert WebAccessRecord.objects.filter(session=session, kind="policy_block", domain="93.184.216.36",
                                              outcome=wr.WEB_ROBOTS_DISALLOWED).exists()

    def test_a_redirect_onto_a_refusing_host_is_refused(self):
        get = _stub_http_get({"http://93.184.216.34/r": _FakeResponse(
            status=302, headers={"location": "http://93.184.216.37/elsewhere.png"})})
        with pytest.raises(wr.WebPolicyError) as exc:
            wr.governed_fetch("http://93.184.216.34/r", wr.gateway_config(), http_get=get,
                              robots=lambda u: "disallowed")
        assert exc.value.code == wr.WEB_ROBOTS_DISALLOWED and "93.184.216.37" in str(exc.value)
        same_host = _stub_http_get({"http://93.184.216.34/open": _FakeResponse(
            status=301, headers={"location": "/private/elsewhere"})})
        with pytest.raises(wr.WebPolicyError) as inward:                  # another path of the same host
            wr.governed_fetch("http://93.184.216.34/open", wr.gateway_config(), http_get=same_host,
                              robots=lambda u: "disallowed" if "/private/" in u else "allowed")
        assert inward.value.code == wr.WEB_ROBOTS_DISALLOWED
        asked = []
        private = _stub_http_get({"http://93.184.216.34/open": _FakeResponse(
            status=302, headers={"location": "http://127.0.0.1/x"})})
        with pytest.raises(wr.WebPolicyError) as inside:                  # refused as private, its robots never asked
            wr.governed_fetch("http://93.184.216.34/open", wr.gateway_config(), http_get=private,
                              robots=lambda u: asked.append(u) or "allowed")
        assert inside.value.code == wr.WEB_SECURITY_POLICY_BLOCKED and asked == []
        with pytest.raises(wr.WebPolicyError) as slow:                    # a host asking an hour between requests
            wr.governed_fetch("http://93.184.216.34/r", wr.gateway_config(), http_get=get,
                              robots=lambda u: "deferred")
        assert slow.value.code == wr.WEB_CRAWL_DELAY_DEFERRED
        with pytest.raises(wr.WebPolicyError) as unread:
            wr.governed_fetch("http://93.184.216.34/r", wr.gateway_config(), http_get=get,
                              robots=lambda u: "unavailable")
        assert unread.value.code == wr.WEB_ROBOTS_UNREADABLE

    def test_each_url_is_judged_on_its_own_path_and_the_file_read_once_per_host(self):
        from unittest import mock
        ok, private = "http://93.184.216.34/serum-ok", "http://93.184.216.34/private/serum"
        payloads = {"night repair serum bottle": _payload(results=[
            {"url": ok, "title": "serum bottle", "content": "", "score": 0.8},
            {"url": private, "title": "serum bottle two", "content": "", "score": 0.7}])}
        page = _FakeResponse(headers={"content-type": "text/html"}, body=b"<html><body>serum</body></html>")
        robots = {"state": "read", "text": "User-agent: *\nDisallow: /private\n"}
        with override_settings(WEB_QUARANTINE_ROOT=self.tmp), \
                mock.patch.object(wr, "robots_file", return_value=robots) as read:
            session = tv.run_tavily_session(
                self.product, connector=_StubConnector(payloads=payloads), fetch=True,
                http_get=_stub_http_get({ok: page}), delay_s=0)
        results = {s.original_url: s.access_policy_result for s in session.sources.filter(classification="analog")}
        assert results == {ok: "fetched_quarantined", private: "robots_disallowed"}, results
        assert read.call_count == 1                                       # one authority, one file

    def test_a_robots_file_behind_a_redirect_is_read_where_it_leads(self):
        moved = _stub_http_get({
            "http://93.184.216.34/robots.txt": _FakeResponse(
                status=301, headers={"location": "http://93.184.216.38/robots.txt"}),
            "http://93.184.216.38/robots.txt": _FakeResponse(body=b"User-agent: *\nDisallow: /private\n")})
        assert wr.robots_check("http://93.184.216.34/private/x", self.UA, http_get=moved)["verdict"] == "disallowed"
        assert wr.robots_check("http://93.184.216.34/open", self.UA, http_get=moved)["verdict"] == "allowed"
        loop = _stub_http_get({"http://93.184.216.34/robots.txt": _FakeResponse(
            status=302, headers={"location": "http://93.184.216.34/robots.txt"})})
        assert wr.robots_check("http://93.184.216.34/x", self.UA, http_get=loop)["verdict"] == "unavailable"
        slow_down = _stub_http_get({"http://93.184.216.34/robots.txt": _FakeResponse(status=429)})
        assert wr.robots_check("http://93.184.216.34/x", self.UA, http_get=slow_down)["verdict"] == "unavailable"
        marked = _stub_http_get({"http://93.184.216.34/robots.txt": _FakeResponse(
            body=b"\xef\xbb\xbfUser-agent: *\nDisallow: /private\n")})
        assert wr.robots_check("http://93.184.216.34/private/x", self.UA, http_get=marked)["verdict"] == "disallowed"

    def test_a_crawl_delay_is_waited_and_one_too_long_defers_the_host(self):
        from unittest import mock
        url = "http://93.184.216.34/serum-d"
        payloads = {"night repair serum bottle": _payload(
            results=[{"url": url, "title": "serum bottle", "content": "", "score": 0.8}])}
        page = _FakeResponse(headers={"content-type": "text/html"}, body=b"<html><body>serum</body></html>")
        waits = []
        asks_five = {"state": "read", "text": "User-agent: *\nCrawl-delay: 5\n"}
        with override_settings(WEB_QUARANTINE_ROOT=self.tmp), \
                mock.patch.object(wr, "robots_file", return_value=asks_five), \
                mock.patch.object(tv.time, "sleep", side_effect=lambda s: waits.append(s)):
            tv.run_tavily_session(
                self.product, connector=_StubConnector(payloads=payloads), fetch=True,
                http_get=_stub_http_get({url: page}), delay_s=0)
        # the robots.txt read is a request to the host: the page after it waits the host's own 5 s, not the 0 s spacing
        assert waits and max(waits) > 4.0, waits
        asks_an_hour = {"state": "read", "text": "User-agent: *\nCrawl-delay: 3600\n"}
        with override_settings(WEB_QUARANTINE_ROOT=self.tmp), \
                mock.patch.object(wr, "robots_file", return_value=asks_an_hour):
            session = tv.run_tavily_session(
                self.product, connector=_StubConnector(payloads=payloads), fetch=True,
                http_get=_stub_http_get({}), delay_s=0)
        src = session.sources.get(classification="analog")
        assert src.access_policy_result == "crawl_delay_deferred"
        assert WebAccessRecord.objects.filter(session=session, outcome=wr.WEB_CRAWL_DELAY_DEFERRED).exists()


class PacketUpdateTests(TestCase):
    def setUp(self):
        self.product = _product()
        self.tmp = tempfile.mkdtemp(prefix="packet_")
        self.path = str(Path(self.tmp) / "packet.json")
        shutil.copyfile(tv.PACKET_PATH, self.path)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_packet_gains_review_availability_not_approval(self):
        stub = _StubConnector(payloads={
            "night repair serum bottle": _payload(
                results=[{"url": "https://supplier.example/serum-30ml",
                          "title": "30 ml serum dropper bottle",
                          "content": "30 ml", "score": 0.8}])})
        session = tv.run_tavily_session(self.product, connector=stub)
        status_before = json.load(open(self.path))["authorization_status"]
        packet = tv.update_packet_after_session(session, path=self.path)
        assert packet["web_reference_review_available"] is True
        live = packet["web_research"]["tavily"]["live_session"]
        assert live["session_id"] == session.id
        assert live["status"] == "AWAITING_HUMAN_REVIEW"
        assert live["analog_candidate_source_ids"] == \
            [session.sources.get().id]
        # the session updater NEVER changes authorization state — whatever
        # status a human decision has set is preserved verbatim
        assert packet["authorization_status"] == status_before
        assert packet["human_decisions/2026-07-24"]["5_project_creation"] \
            == "NOT GRANTED"
        assert packet["preserved"]["api_call_ledger_baseline"] == 215
        on_disk = json.load(open(self.path))
        assert on_disk["web_reference_review_available"] is True


class ReviewUiGroupsTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group, User
        group, _ = Group.objects.get_or_create(name="Reviewer")
        self.user = User.objects.create_user("r3v", "r@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)
        self.session = WebResearchSession.objects.create(
            product_identity="x", modes=[], status="AWAITING_HUMAN_REVIEW",
            summary={"conflicting_facts": [{"fact": "capacity"}]})
        self.blocked = self.session.sources.create(
            original_url="https://a.example/1", classification="analog",
            title="blocked bottle", source_tier=4,
            access_policy_result="robots_disallowed")
        self.image = self.session.sources.create(
            original_url="https://a.example/i.png", classification="image",
            title="candidate image", source_tier=6, mime_type="image/png",
            quarantine_path="/q/i.png",
            facts=[])

    def test_payload_has_all_review_groups(self):
        resp = self.client.get(
            f"/api/web-research/sessions/{self.session.id}/")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body["groups"]) >= {"exact", "analog", "inspiration",
                                       "image"}
        assert body["conflicts"] == [{"fact": "capacity"}]
        assert body["blocked_or_rejected"][0]["reason"] == \
            "robots_disallowed"
        # quarantined image thumbnail stays unavailable until the human
        # grants reference-view permission
        image_card = body["groups"]["image"][0]
        assert image_card["thumbnail_available"] is False
        assert "api_key" not in str(body).lower()

    def test_decision_vocabulary_is_exact(self):
        url = f"/api/web-research/sources/{self.image.id}/decision/"
        allowed = self.client.post(url, {"decision": "nope"},
                                   content_type="application/json"
                                   ).json()["allowed"]
        # the seven independent decisions + reference-view-only (added by
        # the temporary web-review mandate §8); artwork reuse and Design
        # Memory deliberately have no decision here
        assert allowed == sorted(
            ["approve_exact", "approve_analog", "approve_inspiration",
             "approve_fact_source", "approve_provider_input",
             "approve_reference_view", "reject", "needs_verification"])


class SourceRecordDefaultTests(TestCase):
    def test_match_state_recorded_on_source_warnings(self):
        product = _product()
        stub = _StubConnector(payloads={
            "BBROSE Rose Damascena Night Repair Oil": _payload(
                results=[{"url": "https://bbrose.com/rose-oil",
                          "title": "BBROSE Rose Damascena Night Repair Oil "
                                   "BBR-SK-201", "content": "", "score": 1.0}])})
        session = tv.run_tavily_session(product, connector=stub)
        src = session.sources.get(classification="exact")
        states = [w["value"] for w in src.extraction_warnings
                  if isinstance(w, dict) and w.get("kind") == "match_state"]
        assert states == [tv.EXACT_CONFIRMED]
        assert src.source_tier == 1                  # bbrose.com = tier 1
        assert WebSourceRecord._meta.get_field(
            "retrieval_permission").default is False
