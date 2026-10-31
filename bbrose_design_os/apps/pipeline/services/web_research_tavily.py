"""TavilySearchConnector + the governed BBR-SK-201 session pipeline
(2C-2A-CORR-3). Tavily is DISCOVERY ONLY — every retained URL still passes
ARIA's own access policy before any fetch, and all rights stay default-deny.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.conf import settings

from apps.pipeline.services import web_research as wr
from apps.pipeline.services.round_designer import CONNECTOR_VERSION, TAVILY_ENDPOINT, TavilySearchConnector

PLANNER_VERSION = "tavily_query_planner/1.1"
ADVANCED_ESCALATION_REASON = \
    "TAVILY_ADVANCED_SEARCH_ESCALATED_EXACT_PRODUCT_NOT_FOUND"
QUERY_WARNING_SOURCE_TYPE = "SOURCE_PRODUCT_TYPE_NOT_CONTAINER_ARCHETYPE"

#: 2C-2A-CORR-3V — per-mode retention budgets (sum ≤ DEFAULT_LIMITS
#: max_results) so exact-mode noise can never starve analog/inspiration.
MODE_RETENTION_CAPS = {"exact": 10, "analog": 10, "inspiration": 10}
#: WRONG_PRODUCT rows stay reviewable provenance but may only occupy the
#: first half of the exact budget — they never crowd out credible matches.
WRONG_PRODUCT_RETENTION_CAP = 5

PACKET_PATH = "docs/complete_product/pilot_authorization_packet.json"

#: §11 exact-product classification states
EXACT_CONFIRMED = "EXACT_PRODUCT_CONFIRMED_CANDIDATE"
EXACT_PROBABLE = "EXACT_PRODUCT_PROBABLE_CANDIDATE"
NAME_MATCH_ONLY = "NAME_MATCH_ONLY"
WRONG_PRODUCT = "WRONG_PRODUCT"
ANALOG_ONLY = "ANALOG_ONLY"
INSPIRATION_ONLY = "INSPIRATION_ONLY"

#: packaging words that must never masquerade as container archetypes (§7)
_PACKAGING_WORDS = ("carton", "box", "case", "sleeve")


def research_target(product) -> tuple[str, list[str]]:
    """(container research target, warnings) — the outer-packaging record
    never pollutes container queries; the source record is not mutated."""
    ptype = (product.product_type or "").strip().lower()
    warnings = []
    if any(w in ptype for w in _PACKAGING_WORDS) or not ptype:
        warnings.append(QUERY_WARNING_SOURCE_TYPE)
        category = (product.category or "").upper()
        target = ("cosmetic night serum container" if category == "SK"
                  else "cosmetic container")
    else:
        target = f"cosmetic {ptype} container"
    return target, warnings


def plan_queries_v2(product) -> tuple[dict, list[str]]:
    """§8 bounded query plan with the §7 pollution fix. Exact-first; no
    unconfirmed capacity/dimensions in exact queries; ≤12 total."""
    brand = getattr(product.brand, "name", "") or ""
    name = product.name or ""
    sku = product.product_id or ""
    target, warnings = research_target(product)
    exact = [f"{brand} {name}", f'"{name}" {brand}', f'"{sku}"',
             f"{brand} night repair serum"][:4]
    # §8 archetype-diverse analog discovery (dropper / pump / airless +
    # generic) — discovery only, never an archetype assumption for BBR-SK-201
    analog = ["night repair serum bottle",
              "serum dropper bottle specifications",
              "treatment pump serum bottle supplier",
              "airless serum bottle"][:4]
    inspiration = ["rose night serum packaging design",
                   "premium rose skincare packaging",
                   "damask rose cosmetic packaging",
                   "luxury night repair serum carton design"][:4]
    plan = {wr.EXACT_PRODUCT_DISCOVERY: exact,
            wr.CATEGORY_ANALOG_DISCOVERY: analog,
            wr.VISUAL_INSPIRATION_DISCOVERY: inspiration}
    assert sum(len(v) for v in plan.values()) <= \
        wr.DEFAULT_LIMITS["max_queries"]
    for queries in plan.values():
        for q in queries:
            assert not any(w in q.lower() for w in _PACKAGING_WORDS
                           if w != "carton" or "carton design" not in q), q
    return plan, warnings


def classify_exact_match(result: dict, product) -> str:
    """§11 evidence-based classification — never loose keyword promotion."""
    text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
    brand = (getattr(product.brand, "name", "") or "").lower()
    name_tokens = [t for t in (product.name or "").lower().split()
                   if len(t) > 3]
    sku = (product.product_id or "").lower()
    brand_hit = brand and brand in text
    name_hits = sum(1 for t in name_tokens if t in text)
    sku_hit = sku and sku in text
    if sku_hit and brand_hit:
        return EXACT_CONFIRMED
    if brand_hit and name_hits >= max(2, len(name_tokens) - 1):
        return EXACT_PROBABLE
    if name_hits >= 2:
        return NAME_MATCH_ONLY
    return WRONG_PRODUCT


_CAPACITY_RE = re.compile(r"\b(\d{1,4})\s?(ml|mL|ML)\b")
_DIM_RE = re.compile(r"\b(\d{1,3}(?:\.\d)?)\s?(mm|cm)\b")


def extract_fact_candidates(text: str, source_id, tier: int,
                            namespace: str) -> list[dict]:
    """Bounded regex fact candidates (capacity/dimensions) — always
    UNREVIEWED, tier-bound authority, namespaced exact vs analog (§14)."""
    facts = []
    for m in list(_CAPACITY_RE.finditer(text or ""))[:3]:
        facts.append({"schema_version": wr.FACT_SCHEMA, "namespace": namespace,
                      "fact": "capacity", "raw": m.group(0),
                      "normalized": float(m.group(1)), "units": "ml",
                      "source_id": source_id, "source_tier": tier,
                      "authority": wr.fact_authority_for_tier(tier),
                      "extraction_method": "regex",
                      "verification_state": "UNREVIEWED",
                      "conflict_state": "", "human_decision": ""})
    for m in list(_DIM_RE.finditer(text or ""))[:4]:
        value = float(m.group(1)) * (10 if m.group(2) == "cm" else 1)
        facts.append({"schema_version": wr.FACT_SCHEMA, "namespace": namespace,
                      "fact": "dimension", "raw": m.group(0),
                      "normalized": value, "units": "mm",
                      "source_id": source_id, "source_tier": tier,
                      "authority": wr.fact_authority_for_tier(tier),
                      "extraction_method": "regex",
                      "verification_state": "UNREVIEWED",
                      "conflict_state": "", "human_decision": ""})
    return facts


def _replacement_linkage(product) -> dict:
    """§2 (3V) — explicit linkage to prior BLOCKED sessions for the same
    candidate. Blocked sessions are never mutated; the new session records
    what it replaces."""
    from apps.pipeline.models import WebResearchSession
    prior = list(WebResearchSession.objects.filter(
        candidate_id=product.product_id,
        status__in=("BLOCKED", "FAILED_REVIEWABLE"))
        .order_by("id").values_list("id", flat=True))
    packet_status = "PACKET_UNAVAILABLE"
    try:
        with open(PACKET_PATH, encoding="utf-8") as fh:
            packet_status = json.load(fh).get("authorization_status", "")
    except OSError:
        pass
    return {"prior_blocked_session_ids": prior,
            "relationship": ("REPLACEMENT_OF_BLOCKED_SESSION" if prior
                             else "FIRST_SESSION_FOR_CANDIDATE"),
            "connector_version": CONNECTOR_VERSION,
            "query_planner_version": PLANNER_VERSION,
            "limits": dict(wr.DEFAULT_LIMITS),
            "mode_retention_caps": dict(MODE_RETENTION_CAPS),
            "authorization_packet": {"path": PACKET_PATH,
                                     "status_at_run": packet_status}}


def run_tavily_session(product, *, user=None,
                       connector: TavilySearchConnector | None = None,
                       fetch: bool = False, http_get=None, robots=None,
                       delay_s: float | None = None, plan: dict | None = None):
    """§8/§10 the bounded session. Tavily discovers; ARIA's own policy
    governs retention. `fetch=True` (an explicit, governed decision —
    never the default) additionally pulls retained sources + candidate
    images through the §6 access-policy pipeline into quarantine.
    Everything ends AWAITING_HUMAN_REVIEW (or a reviewable BLOCKED).
    Never creates projects/tasks; never calls an image provider.

    §BH57(a)5 — `plan` lets a caller narrow the modes. Default None keeps
    `plan_queries_v2`'s three, so every existing caller is unchanged. It
    exists because EXACT mode puts the brand, the product NAME and the SKU
    into a third-party query, which is right when a person opens the
    research screen for a product that already exists in the world, and
    wrong when a design run does it automatically for an unreleased one.
    A narrowed plan is the caller's whole leak surface, so it is passed in
    rather than derived here."""
    from apps.pipeline.models import WebAccessRecord, WebResearchSession
    from apps.pipeline.services.cost_ledger import BudgetExceededError

    config = wr.gateway_config()
    connector = connector or TavilySearchConnector()
    if plan is None:
        plan, warnings = plan_queries_v2(product)
    else:
        plan, warnings = dict(plan), []
    session = WebResearchSession.objects.create(
        product_identity=f"{product.product_id} — {product.name}",
        candidate_id=product.product_id, modes=list(plan),
        queries=plan, status="PLANNED", created_by=user)
    summary: dict = {"schema_version": wr.SESSION_SCHEMA,
                     "planner_warnings": warnings,
                     "replacement_of": _replacement_linkage(product),
                     "state_trail": ["PLANNED"],
                     "source_counts": {}, "exact_match_findings": [],
                     "analog_findings": [], "inspiration_findings": [],
                     "extracted_facts": [], "conflicting_facts": [],
                     "blocked_sources": [], "advanced_searches": [],
                     "tavily_usage": [], "duplicate_groups": [],
                     "search_calls": {"basic": 0, "advanced": 0},
                     "queries_executed": {m: [] for m in plan},
                     "queries_skipped_by_limit": [],
                     "dropped_by_retention_cap": 0,
                     "image_candidates_discovered": 0,
                     "fetches": {"pages_attempted": 0, "pages_fetched": 0,
                                 "pdfs_fetched": 0, "images_fetched": 0,
                                 "denied": 0, "bytes_total": 0},
                     "rights_summary": "all sources RIGHTS_UNKNOWN; every "
                                       "use permission default-deny"}
    session.status = "SEARCHING"
    summary["state_trail"].append("SEARCHING")
    session.save(update_fields=["status", "updated_at"])

    dedup_index: dict = {}          # normalized URL → source_id (§13)
    image_pool: list = []           # bounded candidate images (§4/§10)
    queries_spent = 0
    budget_stop = None
    try:
        for mode, queries in plan.items():
            for q in queries:
                if queries_spent >= wr.DEFAULT_LIMITS["max_queries"]:
                    summary["queries_skipped_by_limit"].append(q)
                    continue
                queries_spent += 1
                result = connector.search(q, depth="basic")
                summary["search_calls"]["basic"] += 1
                summary["queries_executed"][mode].append(q)
                WebAccessRecord.objects.create(
                    session=session, kind="search", url=TAVILY_ENDPOINT,
                    domain="api.tavily.com", outcome="ok",
                    detail=f"{mode}: {q} · latency {result['latency_ms']}ms"[:300])
                if result.get("usage"):
                    summary["tavily_usage"].append(result["usage"])
                _retain_results(session, mode, result, product, summary,
                                dedup_index)
                _pool_images(image_pool, mode, result)
            # §4 bounded advanced escalation — exact mode only, max 2
            if mode == wr.EXACT_PRODUCT_DISCOVERY:
                exact_credible = any(
                    f["classification"] in (EXACT_CONFIRMED, EXACT_PROBABLE)
                    for f in summary["exact_match_findings"])
                if not exact_credible:
                    for q in queries[:2]:
                        if queries_spent >= wr.DEFAULT_LIMITS["max_queries"]:
                            break
                        queries_spent += 1
                        summary["advanced_searches"].append(
                            {"query": q,
                             "reason": ADVANCED_ESCALATION_REASON})
                        result = connector.search(q, depth="advanced")
                        summary["search_calls"]["advanced"] += 1
                        WebAccessRecord.objects.create(
                            session=session, kind="search",
                            url=TAVILY_ENDPOINT, domain="api.tavily.com",
                            outcome="ok",
                            detail=f"ADVANCED {q}"[:300])
                        if result.get("usage"):
                            summary["tavily_usage"].append(result["usage"])
                        _retain_results(session, mode, result, product,
                                        summary, dedup_index)
                        _pool_images(image_pool, mode, result)
        # §BH57(a)5: only when exact discovery was actually ASKED FOR. This
        # append was unconditional, so a plan that never ran an exact query
        # still recorded a blocked source for it — a person reviewing the
        # session would read a refusal for a search that never happened.
        if wr.EXACT_PRODUCT_DISCOVERY in plan and not any(
                f["classification"] in (EXACT_CONFIRMED, EXACT_PROBABLE)
                for f in summary["exact_match_findings"]):
            summary["blocked_sources"].append(
                {"code": wr.WEB_EXACT_PRODUCT_NOT_FOUND,
                 "detail": "no credible exact-product candidate"})
        summary["image_candidates_discovered"] = len(image_pool)

        if fetch:                                   # §6 governed acquisition
            session.status = "FETCHING"
            summary["state_trail"].append("FETCHING")
            session.save(update_fields=["status", "updated_at"])
            _fetch_phase(session, summary, config, image_pool,
                         http_get=http_get, robots=robots, delay_s=delay_s)
            mark_exact_fact_conflicts(session, summary)
        session.status = "AWAITING_HUMAN_REVIEW"
        summary["state_trail"].append("AWAITING_HUMAN_REVIEW")
    except wr.WebPolicyError as exc:
        WebAccessRecord.objects.create(
            session=session, kind="policy_block", outcome=exc.code,
            detail=str(exc)[:300])
        summary["blocked_sources"].append({"code": exc.code,
                                           "detail": str(exc)[:200]})
        session.status = "BLOCKED"
        summary["state_trail"].append("BLOCKED")
    except BudgetExceededError as exc:
        # [§BH71 PART 2: a search is a ledger row now, so the design's spend cap can stop a session. It is closed
        # BLOCKED like every other exit, and the cap's error is raised on once the row is saved, as every paid call
        # raises it — the catch-all below turned it into "session aborted" and the design went on spending]
        WebAccessRecord.objects.create(
            session=session, kind="policy_block", outcome="BUDGET_EXCEEDED",
            detail="the design's spend cap stopped the session")
        summary["blocked_sources"].append(
            {"code": "BUDGET_EXCEEDED", "detail": "the design's spend cap stopped the session"})
        session.status = "BLOCKED"
        summary["state_trail"].append("BLOCKED")
        budget_stop = exc
    except Exception as exc:                      # noqa: BLE001
        # §BH57(a)5 — EVERY exit is a terminal, reviewable state. Only
        # WebPolicyError was caught, so a refused socket, a DNS failure, a
        # timeout or a provider error escaped the function and left the row
        # it had already created frozen in SEARCHING: no summary, no hash,
        # absent from a review screen that lists AWAITING_HUMAN_REVIEW and
        # BLOCKED, and nothing to ever move it. Measured with the §AY1
        # outbound guard, which refuses the connection exactly as an
        # offline machine would. The TYPE is recorded and the message is
        # not: a provider error can echo the request back, and the request
        # carries the key.
        WebAccessRecord.objects.create(
            session=session, kind="policy_block",
            outcome=wr.WEB_SEARCH_PROVIDER_UNAVAILABLE,
            detail=f"session aborted: {type(exc).__name__}")
        summary["blocked_sources"].append(
            {"code": wr.WEB_SEARCH_PROVIDER_UNAVAILABLE,
             "detail": f"session aborted: {type(exc).__name__}"})
        session.status = "BLOCKED"
        summary["state_trail"].append("BLOCKED")

    summary["source_counts"] = {
        m: session.sources.filter(source_type=m).count() for m in plan}
    session.summary = summary
    session.session_hash = hashlib.sha256(json.dumps(
        {"q": plan, "counts": summary["source_counts"],
         "blocked": summary["blocked_sources"]},
        sort_keys=True, default=str).encode()).hexdigest()
    session.save(update_fields=["summary", "status", "session_hash",
                                "updated_at"])
    if budget_stop is not None:
        raise budget_stop
    return session


def _retain_results(session, mode, result, product, summary,
                    dedup_index: dict) -> int:
    """Persist normalized results as default-deny source records, bounded by
    the global cap, per-mode caps (§9) and §13 canonical-URL dedup."""
    kept = 0
    max_results = wr.DEFAULT_LIMITS["max_results"]
    classification = ("inspiration" if mode == wr.VISUAL_INSPIRATION_DISCOVERY
                      else "analog" if mode == wr.CATEGORY_ANALOG_DISCOVERY
                      else "exact")
    for r in result["results"]:
        if session.sources.count() >= max_results:
            break
        in_mode = session.sources.filter(classification=classification).count()
        if in_mode >= MODE_RETENTION_CAPS[classification]:
            summary["dropped_by_retention_cap"] += 1
            continue
        match_state = (classify_exact_match(r, product)
                       if classification == "exact" else
                       ANALOG_ONLY if classification == "analog"
                       else INSPIRATION_ONLY)
        if match_state == WRONG_PRODUCT and \
                in_mode >= WRONG_PRODUCT_RETENTION_CAP:
            summary["dropped_by_retention_cap"] += 1
            continue
        canonical = wr.normalize_url(r["url"])
        if canonical in dedup_index:                       # §13 mirrors
            _record_duplicate(summary, dedup_index[canonical],
                              {"url": r["url"], "query": r["query"],
                               "mode": mode}, method="normalized_url")
            continue
        tier = wr.classify_tier(r["domain"], brand_domains=("bbrose.com",))
        src = session.sources.create(
            original_url=r["url"], resolved_url="", domain=r["domain"],
            title=r["title"], source_tier=tier, source_type=mode,
            classification=classification,
            access_policy_result="search_result_only_not_fetched",
            match_score=float(r.get("relevance_score") or 0.0),
            rights_state="RIGHTS_UNKNOWN",
            extraction_warnings=[{"kind": "match_state",
                                  "value": match_state}],
            facts=extract_fact_candidates(
                r.get("snippet", ""), None, tier,
                "exact" if classification == "exact" else "analog_feasibility"
                if classification == "analog" else "inspiration"))
        for f in src.facts:                     # snippet facts get their id
            f["source_id"] = src.id
            f["supporting_location"] = "search_result_snippet"
        src.save(update_fields=["facts"])
        dedup_index[canonical] = src.id
        entry = {"source_id": src.id, "title": r["title"][:80],
                 "domain": r["domain"], "tier": tier,
                 "classification": match_state,
                 "note": ("" if classification == "exact"
                          else "NOT THE EXACT BBR-SK-201 PRODUCT")}
        key = {"exact": "exact_match_findings", "analog": "analog_findings",
               "inspiration": "inspiration_findings"}[classification]
        summary[key].append(entry)
        for f in src.facts:
            summary["extracted_facts"].append(
                {**{k: f[k] for k in ("namespace", "fact", "raw",
                                      "normalized", "units", "authority")},
                 "source_id": src.id})
        kept += 1
    return kept


def _pool_images(image_pool: list, mode: str, result: dict,
                 pool_ceiling: int = 60) -> None:
    """Collect candidate images from a search response (discovery only —
    retention/fetch limits are enforced later in the governed fetch phase)."""
    seen = {wr.normalize_url(i["url"]) for i in image_pool}
    for img in result.get("images") or []:
        if len(image_pool) >= pool_ceiling:
            return
        url = img.get("url") or ""
        canonical = wr.normalize_url(url)
        if not url or canonical in seen:
            continue
        seen.add(canonical)
        image_pool.append({"mode": mode, "url": url,
                           "description": img.get("description") or ""})


def _record_duplicate(summary, canonical_source_id, member: dict,
                      method: str) -> None:
    for group in summary["duplicate_groups"]:
        if group["canonical_source_id"] == canonical_source_id and \
                group["method"] == method:
            group["members"].append(member)
            return
    summary["duplicate_groups"].append(
        {"canonical_source_id": canonical_source_id, "method": method,
         "members": [member]})


# --- §6/§10 governed fetch phase (2C-2A-CORR-3V) --------------------------------

class HostManners:
    """§BH71 PART 2 — how a session behaves toward each host, one object for every fetch path (the research session's
    fetch phase and the trend board's): each authority's robots.txt read once and each url judged on its own path,
    only 'allowed' allowing; the spacing between two requests to one host the longer of the session's and the host's
    own Crawl-delay; a Crawl-delay longer than the session waits refusing the host, by name. ``robots`` injects a
    checker asked per url, answering a verdict or ``{"verdict", "crawl_delay"}``."""

    def __init__(self, config: dict, *, delay: float, robots=None):
        self.config = config
        self.delay = delay
        self.robots = robots
        self.files: dict = {}
        self.last_access: dict = {}
        self.crawl_delay: dict = {}

    def delay_of(self, domain) -> float:
        """The spacing two requests to ``domain`` keep: the session's, or the host's own Crawl-delay when longer."""
        if domain in self.crawl_delay:
            return max(self.delay, self.crawl_delay[domain])
        return self.delay

    def wait_for(self, domain) -> float:
        """Seconds before the next request to ``domain`` may go — none before the first."""
        if domain not in self.last_access:
            return 0.0
        return max(0.0, self.delay_of(domain) - (time.monotonic() - self.last_access[domain]))

    def polite(self, domain) -> None:
        """Wait out the host's spacing, then count this request as its last."""
        wait = self.wait_for(domain)
        if wait > 0:
            time.sleep(wait)
        self.last_access[domain] = time.monotonic()

    def verdict(self, url: str, domain) -> str:
        """The verdict for THIS url — its authority's robots.txt read once per session (a request to the host, so
        its spacing first), its rules matched against the url's own path; a Crawl-delay the file asks is kept."""
        if self.robots is not None:               # an injected checker, asked per url
            read = self.robots(url, self.config["user_agent"])
            if isinstance(read, str):             # a checker that answers the verdict alone
                read = {"verdict": read, "crawl_delay": None}
        else:
            origin = wr.robots_origin(url)
            if origin not in self.files:
                self.polite(domain)
                self.files[origin] = wr.robots_file(url, self.config["user_agent"])
            read = wr.robots_verdict(self.files[origin], self.config["user_agent"], url)
        if read.get("crawl_delay"):
            self.crawl_delay[domain] = float(read["crawl_delay"])
        return read["verdict"]

    def refused(self, url: str, domain) -> str | None:
        """Why this url is not fetched — its host's robots.txt answering anything but 'allowed' ('unavailable' is a
        refusal: RFC 9309 §2.3.1.4), or a Crawl-delay longer than the session waits — else None."""
        verdict = self.verdict(url, domain)
        if verdict == "disallowed":
            return wr.WEB_ROBOTS_DISALLOWED
        if verdict != "allowed":
            return wr.WEB_ROBOTS_UNREADABLE
        if domain in self.crawl_delay and self.crawl_delay[domain] > self.config["limits"]["max_crawl_delay_s"]:
            return wr.WEB_CRAWL_DELAY_DEFERRED
        return None

    def robots_of(self, url: str) -> str:
        """A redirect hop's verdict for ``governed_fetch``: refused as a page is; allowed, the hop is a request to its
        host, so its spacing first."""
        host = urlparse(url).hostname
        if host is None:
            return "unavailable"
        why = self.refused(url, host)
        if why is None:
            self.polite(host)
            return "allowed"
        if why == wr.WEB_ROBOTS_DISALLOWED:
            return "disallowed"
        if why == wr.WEB_CRAWL_DELAY_DEFERRED:
            return "deferred"
        return "unavailable"


def _fetch_priority(src, summary) -> tuple:
    """Exact credible candidates first, then analogs by tier, then
    inspiration — within the hard page budget."""
    class_rank = {"exact": 0, "analog": 1, "inspiration": 2}.get(
        src.classification, 3)
    match_rank = 2
    for w in src.extraction_warnings:
        if isinstance(w, dict) and w.get("kind") == "match_state":
            match_rank = {EXACT_CONFIRMED: 0, EXACT_PROBABLE: 0,
                          NAME_MATCH_ONLY: 1}.get(w.get("value"), 2)
    return (class_rank, match_rank, src.source_tier, -src.match_score)


def _fetch_phase(session, summary, config, image_pool, *, http_get=None,
                 robots=None, delay_s: float | None = None) -> None:
    """Fetch retained sources + candidate images through the §6 pipeline:
    per-hop policy, robots, MIME allowlist, byte ceilings, quarantine,
    ledger. Denials are preserved as reviewable provenance, never bypassed."""
    from apps.pipeline.models import WebAccessRecord

    limits = config["limits"]
    delay = limits["per_domain_delay_s"] if delay_s is None else delay_s
    fetches = summary["fetches"]
    # [§BH71 PART 2: the manners are one object, shared with the trend board's fetch — they were closures here]
    manners = HostManners(config, delay=delay, robots=robots)
    _polite, _robots, _refused, _robots_of = manners.polite, manners.verdict, manners.refused, manners.robots_of

    sources = sorted(session.sources.all(),
                     key=lambda s: _fetch_priority(s, summary))
    for src in sources:
        if fetches["pages_attempted"] >= limits["max_pages"]:
            break
        if fetches["bytes_total"] >= limits["total_byte_ceiling"]:
            break
        fetches["pages_attempted"] += 1
        try:
            wr.check_url_policy(src.original_url)
            verdict = _robots(src.original_url, src.domain)
            src.robots_result = verdict
            refused = _refused(src.original_url, src.domain)
            if refused is not None:
                # [§BH71 PART 2: only 'allowed' allows — an unreadable robots.txt and a Crawl-delay longer than
                # the session waits refuse too, each by name; it refused 'disallowed' alone]
                src.access_policy_result = "robots_disallowed"
                if refused == wr.WEB_ROBOTS_UNREADABLE:
                    src.access_policy_result = "robots_unreadable"
                elif refused == wr.WEB_CRAWL_DELAY_DEFERRED:
                    src.access_policy_result = "crawl_delay_deferred"
                src.save(update_fields=["robots_result",
                                        "access_policy_result"])
                WebAccessRecord.objects.create(
                    session=session, kind="policy_block",
                    url=src.original_url, domain=src.domain,
                    outcome=refused, detail=_REFUSED_WORDS[refused])
                fetches["denied"] += 1
                continue
            _polite(src.domain)
            fetched = wr.governed_fetch(src.original_url, config,
                                        http_get=http_get, robots=_robots_of)
            if fetched["mime_type"] == "application/pdf" and \
                    fetches["pdfs_fetched"] >= limits["max_pdfs"]:
                src.access_policy_result = "pdf_cap_reached_not_stored"
                src.save(update_fields=["robots_result",
                                        "access_policy_result"])
                fetches["denied"] += 1
                continue
            name = f"src_{src.id}_{Path(urlparse(fetched['resolved_url']).path).name or 'page.html'}"
            src.quarantine_path = wr.quarantine_write(
                config["quarantine_root"], session.id, name, fetched["body"])
            src.resolved_url = fetched["resolved_url"]
            src.http_status = fetched["http_status"]
            src.mime_type = fetched["mime_type"]
            src.byte_count = fetched["byte_count"]
            src.content_sha256 = fetched["content_sha256"]
            src.access_policy_result = "fetched_quarantined"
            fetches["bytes_total"] += fetched["byte_count"]
            fetches["pages_fetched"] += 1
            if fetched["mime_type"] == "application/pdf":
                fetches["pdfs_fetched"] += 1
            elif fetched["mime_type"] == "text/html" and \
                    src.classification in ("exact", "analog"):
                text = wr.html_to_text(fetched["body"])
                namespace = ("exact" if src.classification == "exact"
                             else "analog_feasibility")
                known = {(f.get("fact"), f.get("raw")) for f in src.facts}
                for f in extract_fact_candidates(text, src.id,
                                                 src.source_tier, namespace):
                    if (f["fact"], f["raw"]) in known:
                        continue
                    f["supporting_location"] = "fetched_page_text"
                    src.facts.append(f)
                    summary["extracted_facts"].append(
                        {**{k: f[k] for k in ("namespace", "fact", "raw",
                                              "normalized", "units",
                                              "authority")},
                         "source_id": src.id})
            src.save()
            WebAccessRecord.objects.create(
                session=session, kind="page_fetch", url=src.original_url,
                domain=src.domain, outcome="ok",
                http_status=fetched["http_status"],
                byte_count=fetched["byte_count"],
                detail=f"quarantined · {fetched['mime_type']} · "
                       f"{fetched['redirect_hops']} redirects"[:300])
        except wr.WebPolicyError as exc:
            src.access_policy_result = f"fetch_blocked:{exc.code}"[:60]
            src.save(update_fields=["robots_result", "access_policy_result"])
            WebAccessRecord.objects.create(
                session=session, kind="page_fetch", url=src.original_url,
                domain=src.domain, outcome=exc.code, detail=str(exc)[:300])
            fetches["denied"] += 1
        except Exception as exc:  # noqa: BLE001 — network faults stay rows
            src.access_policy_result = "fetch_blocked:NETWORK_ERROR"
            src.save(update_fields=["access_policy_result"])
            WebAccessRecord.objects.create(
                session=session, kind="page_fetch", url=src.original_url,
                domain=src.domain, outcome="NETWORK_ERROR",
                detail=str(exc)[:300])
            fetches["denied"] += 1

    _dedup_by_content_hash(session, summary)
    _fetch_images(session, summary, config, image_pool, http_get=http_get,
                  polite=_polite, refused=_refused, robots=_robots_of)


#: §BH71 PART 2: what a fetch refused on a host's own word says, by its code
_REFUSED_WORDS = {
    wr.WEB_ROBOTS_DISALLOWED: "robots.txt disallows fetch — respected",
    wr.WEB_ROBOTS_UNREADABLE: "robots.txt could not be read — assumed complete disallow (RFC 9309 §2.3.1.4)",
    wr.WEB_CRAWL_DELAY_DEFERRED: "the host asks a Crawl-delay longer than the session waits for one host — "
                                 "deferred, not fetched",
}


def _fetch_images(session, summary, config, image_pool, *, http_get=None,
                  polite=None, refused=None, robots=None) -> None:
    """§4/§10 bounded candidate-image acquisition. Every element description
    is classified with the styling default (condensation/droplets/props are
    NEVER printed artwork without proof). Images are never fact sources."""
    from apps.pipeline.models import WebAccessRecord

    limits = config["limits"]
    fetches = summary["fetches"]
    per_domain: dict = {}
    phash_index: dict = {}
    for idx, img in enumerate(image_pool):
        if fetches["images_fetched"] >= limits["max_images"]:
            break
        if fetches["bytes_total"] >= limits["total_byte_ceiling"]:
            break
        domain = urlparse(img["url"]).hostname or ""
        if per_domain.get(domain, 0) >= limits["max_images_per_domain"]:
            continue
        try:
            wr.check_url_policy(img["url"])
            if refused is not None:
                # [§BH71 PART 2: the IMAGE host's own robots.txt, asked as a page's is — it was never asked]
                why = refused(img["url"], domain)
                if why is not None:
                    WebAccessRecord.objects.create(
                        session=session, kind="policy_block", url=img["url"], domain=domain,
                        outcome=why, detail=_REFUSED_WORDS[why])
                    fetches["denied"] += 1
                    continue
            if polite:
                polite(domain)
            fetched = wr.governed_fetch(img["url"], config, http_get=http_get, robots=robots)
            if not fetched["mime_type"].startswith("image/"):
                raise wr.WebPolicyError(wr.WEB_UNSUPPORTED_CONTENT_TYPE,
                                        fetched["mime_type"])
            phash = _perceptual_hash(fetched["body"])
            if phash and phash in phash_index:                 # §13
                _record_duplicate(summary, phash_index[phash],
                                  {"url": img["url"], "mode": img["mode"]},
                                  method="image_phash")
                continue
            name = f"img_{idx:02d}_{Path(urlparse(fetched['resolved_url']).path).name or 'image'}"
            path = wr.quarantine_write(config["quarantine_root"], session.id,
                                       name, fetched["body"])
            elements = wr.classify_image_elements(
                [img["description"]] if img["description"] else [])
            src = session.sources.create(
                original_url=img["url"], resolved_url=fetched["resolved_url"],
                domain=domain, title=(img["description"] or "candidate image")[:300],
                source_tier=wr.classify_tier(domain,
                                             brand_domains=("bbrose.com",)),
                source_type=img["mode"], classification="image",
                access_policy_result="fetched_quarantined",
                http_status=fetched["http_status"],
                mime_type=fetched["mime_type"],
                byte_count=fetched["byte_count"],
                content_sha256=fetched["content_sha256"],
                quarantine_path=path, rights_state="RIGHTS_UNKNOWN",
                extraction_warnings=[
                    {"kind": "image_element_classification",
                     "elements": elements},
                    {"kind": "phash", "value": phash},
                    {"kind": "note",
                     "value": "image inference NEVER becomes exact "
                              "dimensional or material data"}],
                facts=[])
            if phash:
                phash_index[phash] = src.id
            per_domain[domain] = per_domain.get(domain, 0) + 1
            fetches["images_fetched"] += 1
            fetches["bytes_total"] += fetched["byte_count"]
            WebAccessRecord.objects.create(
                session=session, kind="image_fetch", url=img["url"],
                domain=domain, outcome="ok",
                http_status=fetched["http_status"],
                byte_count=fetched["byte_count"],
                detail=f"quarantined image · {img['mode']}"[:300])
        except wr.WebPolicyError as exc:
            WebAccessRecord.objects.create(
                session=session, kind="image_fetch", url=img["url"],
                domain=domain, outcome=exc.code, detail=str(exc)[:300])
            fetches["denied"] += 1
        except Exception as exc:  # noqa: BLE001
            WebAccessRecord.objects.create(
                session=session, kind="image_fetch", url=img["url"],
                domain=domain, outcome="NETWORK_ERROR",
                detail=str(exc)[:300])
            fetches["denied"] += 1


def _perceptual_hash(body: bytes) -> str:
    """8×8 average-hash for §13 near-duplicate image grouping. Failure is a
    warning, never a session failure."""
    try:
        from io import BytesIO

        from PIL import Image
        img = Image.open(BytesIO(body)).convert("L").resize((8, 8))
        pixels = list(img.tobytes())
        avg = sum(pixels) / len(pixels)
        return f"{int(''.join('1' if p > avg else '0' for p in pixels), 2):016x}"
    except Exception:  # noqa: BLE001
        return ""


def _dedup_by_content_hash(session, summary) -> None:
    """§13 — identical fetched bodies (marketplace mirrors) group under the
    first-retained canonical record; members are marked, never deleted."""
    seen: dict = {}
    for src in session.sources.exclude(content_sha256="").order_by("id"):
        if src.content_sha256 in seen:
            _record_duplicate(summary, seen[src.content_sha256],
                              {"source_id": src.id, "url": src.original_url},
                              method="content_sha256")
            src.extraction_warnings.append(
                {"kind": "duplicate_of",
                 "value": seen[src.content_sha256]})
            src.save(update_fields=["extraction_warnings"])
        else:
            seen[src.content_sha256] = src.id


def mark_exact_fact_conflicts(session, summary) -> None:
    """§11 — conflicting values for the SAME exact-product fact stay
    CONFLICTED (never averaged). Analog-namespace values describe different
    physical products and are never treated as competing claims. Same-value
    corroboration counts only distinct domains (mirrors don't corroborate)."""
    by_fact: dict = {}
    for src in session.sources.filter(classification="exact"):
        for f in src.facts:
            if f.get("namespace") != "exact":
                continue
            by_fact.setdefault(f["fact"], []).append((src, f))
    for fact_name, entries in by_fact.items():
        values = {f["normalized"] for _, f in entries}
        domains_by_value: dict = {}
        for src, f in entries:
            domains_by_value.setdefault(f["normalized"], set()).add(src.domain)
            f["corroboration_count"] = len(domains_by_value[f["normalized"]])
        if len(values) > 1:
            for src, f in entries:
                f["conflict_state"] = "CONFLICTED"
            summary["conflicting_facts"].append(
                {"fact": fact_name, "namespace": "exact",
                 "values": sorted(values),
                 "source_ids": sorted({src.id for src, _ in entries}),
                 "resolution": "human confirmation required — "
                               "contradictions are never averaged"})
    touched = {src.id: src for entries in by_fact.values()
               for src, _ in entries}
    for src in touched.values():
        src.save(update_fields=["facts"])


def update_packet_after_session(session, path: str = PACKET_PATH) -> dict:
    """§15/§18 — record the live session in the authorization packet WITHOUT
    changing its authorization state. Review availability is a fact about
    reviewable sources, never an approval."""
    from django.utils import timezone

    from apps.pipeline.models import WebAccessRecord

    with open(path, encoding="utf-8") as fh:
        packet = json.load(fh)
    sources = session.sources.all()
    ledger = WebAccessRecord.objects.filter(session=session).order_by("id")
    ids = list(ledger.values_list("id", flat=True))

    def _ids(**flt):
        return list(sources.filter(**flt).values_list("id", flat=True))

    usage_credits = 0
    for u in session.summary.get("tavily_usage", []):
        try:
            usage_credits += int(u.get("credits") or 0)
        except (TypeError, ValueError):
            pass
    packet["web_reference_review_available"] = sources.exists()
    packet["web_research"]["tavily"]["live_session"] = {
        "session_id": session.id,
        "session_hash_prefix": session.session_hash[:16],
        "status": session.status,
        "replacement_of": session.summary.get(
            "replacement_of", {}).get("prior_blocked_session_ids", []),
        "source_counts": session.summary.get("source_counts", {}),
        "exact_candidate_source_ids": _ids(classification="exact"),
        "analog_candidate_source_ids": _ids(classification="analog"),
        "inspiration_candidate_source_ids": _ids(
            classification="inspiration"),
        "image_candidate_source_ids": _ids(classification="image"),
        "fact_candidate_count": len(session.summary.get(
            "extracted_facts", [])),
        "conflicts": session.summary.get("conflicting_facts", []),
        "blocked_source_codes": [b.get("code") for b in
                                 session.summary.get("blocked_sources", [])],
        "duplicate_groups": len(session.summary.get("duplicate_groups", [])),
        "tavily_credits_reported": usage_credits,
        "web_access_record_range": ([ids[0], ids[-1]] if ids else []),
        "rights_summary": session.summary.get("rights_summary", ""),
        "review_endpoints": [
            f"GET /api/web-research/sessions/{session.id}/",
            "POST /api/web-research/sources/<id>/decision/"],
    }
    packet["updated_at"] = timezone.now().isoformat()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(packet, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    return packet


__all__ = ["TavilySearchConnector", "CONNECTOR_VERSION", "PLANNER_VERSION",
           "plan_queries_v2", "research_target", "classify_exact_match",
           "extract_fact_candidates", "run_tavily_session",
           "mark_exact_fact_conflicts", "update_packet_after_session",
           "ADVANCED_ESCALATION_REASON", "QUERY_WARNING_SOURCE_TYPE",
           "MODE_RETENTION_CAPS", "PACKET_PATH",
           "EXACT_CONFIRMED", "EXACT_PROBABLE", "NAME_MATCH_ONLY",
           "WRONG_PRODUCT", "ANALOG_ONLY", "INSPIRATION_ONLY"]
