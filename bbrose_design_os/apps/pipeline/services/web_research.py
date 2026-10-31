"""AriaWebResearchGateway (Phase 2C-2A-CORR-2).

Controlled, provenance-first Web Research: search-first, policy-checked,
bounded retrieval into quarantine, rights DEFAULT-DENY, everything presented
for human review. Never an unrestricted scraper; never silently converts web
content into verified data, provider input, artwork reuse or design memory.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from django.conf import settings

SESSION_SCHEMA = "aria_web_research_session/1.0"
SOURCE_SCHEMA = "web_source_record/1.0"
FACT_SCHEMA = "web_product_fact_candidate/1.0"
CONTEXT_SCHEMA = "web_reference_context/1.0"

# §2 discovery modes
EXACT_PRODUCT_DISCOVERY = "EXACT_PRODUCT_DISCOVERY"
CATEGORY_ANALOG_DISCOVERY = "CATEGORY_ANALOG_DISCOVERY"
VISUAL_INSPIRATION_DISCOVERY = "VISUAL_INSPIRATION_DISCOVERY"
MODES = (EXACT_PRODUCT_DISCOVERY, CATEGORY_ANALOG_DISCOVERY,
         VISUAL_INSPIRATION_DISCOVERY)

# §25 stable codes
WEB_RESEARCH_NOT_CONFIGURED = "WEB_RESEARCH_NOT_CONFIGURED"
WEB_SEARCH_PROVIDER_UNAVAILABLE = "WEB_SEARCH_PROVIDER_UNAVAILABLE"
WEB_SOURCE_ACCESS_DENIED = "WEB_SOURCE_ACCESS_DENIED"
WEB_ROBOTS_DISALLOWED = "WEB_ROBOTS_DISALLOWED"
#: §BH71 PART 2: a robots.txt that could not be read is a refusal (RFC 9309 §2.3.1.4: assume complete disallow)
WEB_ROBOTS_UNREADABLE = "WEB_ROBOTS_UNREADABLE"
#: §BH71 PART 2: a host whose declared Crawl-delay is longer than the session waits for one host is not fetched
WEB_CRAWL_DELAY_DEFERRED = "WEB_CRAWL_DELAY_DEFERRED"
WEB_UNSUPPORTED_CONTENT_TYPE = "WEB_UNSUPPORTED_CONTENT_TYPE"
WEB_FETCH_SIZE_LIMIT = "WEB_FETCH_SIZE_LIMIT"
WEB_SECURITY_POLICY_BLOCKED = "WEB_SECURITY_POLICY_BLOCKED"
WEB_EXACT_PRODUCT_NOT_FOUND = "WEB_EXACT_PRODUCT_NOT_FOUND"
WEB_REFERENCE_REVIEW_REQUIRED = "WEB_REFERENCE_REVIEW_REQUIRED"

#: §13 mandatory styling default (the task-#51 lesson)
STYLING_DEFAULT = "PHOTOGRAPHIC_STYLING_UNLESS_EVIDENCE_PROVES_PRINTED_ARTWORK"
STYLING_ELEMENTS = ("condensation", "water droplets", "shadows",
                    "reflections", "lighting")

ALLOWED_MIME = ("text/html", "application/pdf", "image/jpeg", "image/png",
                "image/webp")
ALLOWED_SCHEMES = ("http", "https")

#: §8 conservative session limits (a human may approve larger separately)
DEFAULT_LIMITS = {
    "max_queries": 12, "max_results": 30, "max_pages": 12, "max_pdfs": 5,
    "max_images": 20, "max_images_per_domain": 5, "max_redirects": 5,
    "per_domain_delay_s": 2.0, "total_byte_ceiling": 50 * 1024 * 1024,
    "per_fetch_byte_limit": 8 * 1024 * 1024, "timeout_s": 20,
    # §BH71 PART 2: the longest Crawl-delay a session waits for between two requests to one host
    "max_crawl_delay_s": 60.0,
}

#: §3 source-tier heuristics by domain role (never rights authority)
TIER_LABELS = {1: "official brand/manufacturer", 2: "official catalogue/spec",
               3: "authorized retailer", 4: "marketplace listing",
               5: "editorial/UGC", 6: "unverified image-only"}


class WebPolicyError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code


def gateway_config() -> dict:
    """§26 environment configuration; credentials never persisted."""
    return {
        "search_provider": str(getattr(settings, "WEB_SEARCH_PROVIDER", "")
                               or "").strip(),
        "search_key_present": bool(getattr(settings, "WEB_SEARCH_API_KEY", "")),
        "user_agent": str(getattr(settings, "WEB_RESEARCH_USER_AGENT", "")
                          or "BBROSE-DesignOS-ResearchBot/1.0 "
                             "(+contact: bbrosedesign07@gmail.com)"),
        "quarantine_root": str(getattr(settings, "WEB_QUARANTINE_ROOT", "")
                               or Path(settings.MEDIA_ROOT) / "web_quarantine"),
        "limits": dict(DEFAULT_LIMITS),
    }


# --- §5 security boundary ------------------------------------------------------

def check_url_policy(url: str) -> None:
    """SSRF / scheme / private-network guard. Raises WebPolicyError."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise WebPolicyError(WEB_SECURITY_POLICY_BLOCKED,
                             f"scheme {parsed.scheme!r} not allowed")
    host = parsed.hostname or ""
    if not host or host in ("localhost",):
        raise WebPolicyError(WEB_SECURITY_POLICY_BLOCKED, "host not allowed")
    if host.endswith((".local", ".internal")) or host == "metadata.google.internal":
        raise WebPolicyError(WEB_SECURITY_POLICY_BLOCKED,
                             "internal hostname blocked")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise WebPolicyError(WEB_SOURCE_ACCESS_DENIED,
                             f"DNS resolution failed: {exc}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast):
            raise WebPolicyError(WEB_SECURITY_POLICY_BLOCKED,
                                 f"private/reserved address {ip} blocked")


def _robots_groups(text: str) -> list:
    """§BH71 PART 2: the file's groups as RFC 9309 §2.1 reads them — ``[(user-agent tokens, [(rule, value)])]``:
    consecutive user-agent lines open one group, whose rules run until a user-agent line follows a rule."""
    groups, agents, rules, in_rules = [], [], [], False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if in_rules:
                groups.append((agents, rules))
                agents, rules, in_rules = [], [], False
            agents.append(value.lower())
        elif key in ("allow", "disallow", "crawl-delay") and agents:
            rules.append((key, value))
            in_rules = True
    if agents:
        groups.append((agents, rules))
    return groups


def _robots_path_regex(pattern: str):
    """A rule's path as RFC 9309 §2.2.3 matches it: ``*`` any run of characters, a trailing ``$`` the path's end."""
    anchored = pattern.endswith("$")
    body = pattern
    if anchored:
        body = pattern[:-1]
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    if anchored:
        regex += "$"
    return re.compile(regex)


def robots_rules(text: str, user_agent: str, path: str) -> dict:
    """§BH71 PART 2 — ``{"allowed", "crawl_delay", "rule"}`` for ``path`` (its query included) as RFC 9309 reads a
    robots.txt: the groups naming the crawler's own product token (case-insensitively), else the ``*`` groups,
    combined (§2.2.1); among their rules the longest pattern that matches wins, an Allow winning a tie, and no
    matching rule allows (§2.2.2); ``/robots.txt`` itself is always allowed. Crawl-delay (a site's own request, not
    in the RFC) is read from the same groups. The standard library's parser matched rules as plain prefixes, so
    Behance's ``/search/*?*sort=*``, Dribbble's ``/shots/*/comments`` and ``/log$`` all read as allowed."""
    token = user_agent.split("/", 1)[0].strip().lower()
    groups = _robots_groups(text)
    chosen = [rules for agents, rules in groups if token in agents]
    if not chosen:
        chosen = [rules for agents, rules in groups if "*" in agents]
    best, delay = None, None
    for key, value in (r for rules in chosen for r in rules):
        if key == "crawl-delay":
            if re.fullmatch(r"\d+(?:\.\d+)?", value):
                delay = float(value)
            continue
        if not value or not _robots_path_regex(value).match(path):
            continue
        candidate = (len(value), key == "allow", "%s: %s" % (key.capitalize(), value))
        if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and candidate[1]):
            best = candidate
    allowed = best is None or best[1] or path == "/robots.txt"
    rule = None
    if best is not None:
        rule = best[2]
    return {"allowed": allowed, "crawl_delay": delay, "rule": rule}


#: §BH71 PART 2: how many redirects a robots.txt fetch follows (RFC 9309 §2.3.1.2: at least five)
ROBOTS_MAX_REDIRECTS = 5


def robots_origin(url: str) -> str:
    """The authority a robots.txt speaks for (RFC 9309 §2.3): the URL's scheme, host and port."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def robots_file(url: str, user_agent: str, *, http_get=None) -> dict:
    """§BH71 PART 2 — the robots.txt of ``url``'s authority, fetched once with an explicit timeout and our declared
    user agent: ``{"state": 'read' | 'absent' | 'unavailable', "text"}``. Redirects are followed, each hop through the
    same address policy, up to ``ROBOTS_MAX_REDIRECTS`` (RFC 9309 §2.3.1.2) — the single-hop getter read a redirect's
    own body as the file, and an empty file allows everything. A 4xx is no robots.txt ('absent': no restriction,
    §2.3.1.3) — but a 429 asks us to slow down and is read as a server failure; a 5xx, a failure, or a chain of
    redirects too long is 'unavailable', and every fetch path refuses it (§2.3.1.4: assume complete disallow)."""
    get = http_get or _default_http_get
    current = robots_origin(url) + "/robots.txt"
    try:
        for _hop in range(ROBOTS_MAX_REDIRECTS + 1):
            check_url_policy(current)
            resp = get(current, headers={"User-Agent": user_agent}, timeout=10)
            try:
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        return {"state": "unavailable", "text": ""}
                    current = urljoin(current, location)
                    continue
                if resp.status_code >= 500 or resp.status_code == 429:
                    return {"state": "unavailable", "text": ""}        # a server failing or asking us to slow down
                if resp.status_code >= 400:
                    return {"state": "absent", "text": ""}
                body = b"".join(resp.iter_content(chunk_size=65536))[:512 * 1024]
            finally:
                resp.close()
            # utf-8-sig: a byte-order mark would otherwise glue itself to the first key and lose the first group
            return {"state": "read", "text": body.decode("utf-8-sig", errors="replace")}
    except Exception:  # noqa: BLE001 — unreadable robots → conservative
        return {"state": "unavailable", "text": ""}
    return {"state": "unavailable", "text": ""}


def robots_verdict(robots: dict, user_agent: str, url: str) -> dict:
    """§BH71 PART 2 — ``{"verdict": 'allowed' | 'disallowed' | 'unavailable', "crawl_delay": seconds or None,
    "rule"}`` for ONE url, from its authority's ``robots_file``: rules are matched against each URL's own path and
    query, so a verdict is never carried from one page of a host to another."""
    if robots["state"] == "unavailable":
        return {"verdict": "unavailable", "crawl_delay": None, "rule": None}
    if robots["state"] == "absent":
        return {"verdict": "allowed", "crawl_delay": None, "rule": None}
    parsed = urlparse(url)
    path = parsed.path
    if not path:
        path = "/"                     # an empty path is the root (RFC 3986 §6.2.3)
    if parsed.query:
        path += "?" + parsed.query
    read = robots_rules(robots["text"], user_agent, path)
    verdict = "disallowed"
    if read["allowed"]:
        verdict = "allowed"
    return {"verdict": verdict, "crawl_delay": read["crawl_delay"], "rule": read["rule"]}


def robots_check(url: str, user_agent: str, *, http_get=None) -> dict:
    """§BH71 PART 2 — ``robots_verdict`` for ``url`` from a fresh ``robots_file``: one URL, one fetch of its
    authority's file. A session asking many URLs of one host reads the file once and asks ``robots_verdict``."""
    return robots_verdict(robots_file(url, user_agent, http_get=http_get), user_agent, url)


def check_robots(url: str, user_agent: str, *, http_get=None) -> str:
    """robots.txt verdict: 'allowed' | 'disallowed' | 'unavailable'.
    Fetched with an explicit timeout + our declared user agent — the stdlib
    RobotFileParser.read() has no timeout and could hang a session.
    [§BH71 PART 2: read as RFC 9309 reads it, ``robots_check`` — the stdlib parser is no longer used]"""
    return robots_check(url, user_agent, http_get=http_get)["verdict"]


def check_mime(content_type: str) -> None:
    base = (content_type or "").split(";")[0].strip().lower()
    if base not in ALLOWED_MIME:
        raise WebPolicyError(WEB_UNSUPPORTED_CONTENT_TYPE, base)


def quarantine_write(root: str, session_id: int, name: str,
                     data: bytes) -> str:
    """Root-bounded quarantine write; returns the stored path."""
    base = Path(root).resolve()
    target = (base / str(session_id) / Path(name).name).resolve()
    if not str(target).startswith(str(base)):
        raise WebPolicyError(WEB_SECURITY_POLICY_BLOCKED,
                             "quarantine path escape")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return str(target)


# --- §6 governed fetch (2C-2A-CORR-3V) -------------------------------------------

_TRACKING_PARAMS = ("utm_source", "utm_medium", "utm_campaign", "utm_term",
                    "utm_content", "gclid", "fbclid", "mc_cid", "mc_eid")


def normalize_url(url: str) -> str:
    """Canonical URL for §13 duplicate control: lowercase scheme+host, drop
    fragments + tracking params + trailing slash. Never used for fetching."""
    p = urlparse(url or "")
    query = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                       if k.lower() not in _TRACKING_PARAMS])
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), (p.netloc or "").lower(), path,
                       "", query, ""))


def _default_http_get(url: str, *, headers: dict, timeout: int):
    """Single-hop HTTP GET (redirects handled by the caller so every hop is
    policy-checked). Streamed so byte ceilings apply before full download."""
    return requests.get(url, headers=headers, timeout=timeout,
                        stream=True, allow_redirects=False)


def governed_fetch(url: str, config: dict, *, http_get=None,
                   byte_limit: int | None = None, robots=None) -> dict:
    """§6 fetch of ONE already-retained URL through the full access policy:
    scheme/SSRF check per redirect hop (≤ max_redirects), MIME allowlist,
    streamed byte ceiling. Returns bounded fetch facts; raises WebPolicyError.
    Never executes page scripts; never bypasses auth/paywall/CAPTCHA (a 401/
    403/402/429 is recorded as denial, never retried around)."""
    get = http_get or _default_http_get
    limits = config["limits"]
    byte_limit = byte_limit or limits["per_fetch_byte_limit"]
    headers = {"User-Agent": config["user_agent"],
               "Accept": ",".join(ALLOWED_MIME)}
    current, hops = url, 0
    while True:
        check_url_policy(current)
        resp = get(current, headers=headers, timeout=limits["timeout_s"])
        try:
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location") or ""
                hops += 1
                if not location or hops > limits["max_redirects"]:
                    raise WebPolicyError(WEB_SECURITY_POLICY_BLOCKED,
                                         f"redirect limit ({hops} hops)")
                current = urljoin(current, location)
                if robots is not None:
                    # [§BH71 PART 2: every hop's new url is asked of its host's robots.txt, and only 'allowed'
                    # passes — a redirect was followed unasked, onto another host or another path of the same one;
                    # the address policy first, so a private target is refused as that, never asked]
                    check_url_policy(current)
                    verdict = robots(current)
                    if verdict != "allowed":
                        code = WEB_ROBOTS_UNREADABLE
                        if verdict == "disallowed":
                            code = WEB_ROBOTS_DISALLOWED
                        elif verdict == "deferred":             # its host asks a Crawl-delay longer than we wait
                            code = WEB_CRAWL_DELAY_DEFERRED
                        raise WebPolicyError(
                            code, f"redirect to {current}, whose robots.txt answers {verdict}"[:300])
                continue
            if resp.status_code in (401, 402, 403, 407, 429, 451):
                raise WebPolicyError(
                    WEB_SOURCE_ACCESS_DENIED,
                    f"HTTP {resp.status_code} — source denial respected, "
                    "no bypass attempted")
            if resp.status_code != 200:
                raise WebPolicyError(WEB_SOURCE_ACCESS_DENIED,
                                     f"HTTP {resp.status_code}")
            content_type = resp.headers.get("content-type", "")
            check_mime(content_type)
            chunks, total = [], 0
            for chunk in resp.iter_content(chunk_size=65536):
                total += len(chunk)
                if total > byte_limit:
                    raise WebPolicyError(WEB_FETCH_SIZE_LIMIT,
                                         f"body exceeds {byte_limit} bytes")
                chunks.append(chunk)
            body = b"".join(chunks)
            return {"resolved_url": current, "http_status": resp.status_code,
                    "mime_type": content_type.split(";")[0].strip().lower(),
                    "byte_count": len(body),
                    "content_sha256": hashlib.sha256(body).hexdigest(),
                    "redirect_hops": hops, "body": body}
        finally:
            resp.close()


_TAG_STRIP_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>|<[^>]+>", re.IGNORECASE | re.DOTALL)


def html_to_text(body: bytes, limit: int = 6000) -> str:
    """Bounded visible-text extraction for fact mining. Scripts and styles
    are stripped, NEVER executed."""
    text = _TAG_STRIP_RE.sub(" ", body.decode("utf-8", errors="replace"))
    return re.sub(r"\s+", " ", text).strip()[:limit]


# --- §3 tiers + §14 rights ------------------------------------------------------

def classify_tier(domain: str, brand_domains: tuple = ()) -> int:
    d = (domain or "").lower()
    if any(d == b or d.endswith("." + b) for b in brand_domains):
        return 1
    if any(k in d for k in ("sephora", "ulta", "douglas", "boots",
                            "lookfantastic")):
        return 3
    if any(k in d for k in ("amazon", "ebay", "aliexpress", "alibaba",
                            "temu", "etsy")):
        return 4
    if any(k in d for k in ("wikipedia", "vogue", "allure", "byrdie",
                            "reddit", "instagram", "pinterest", "blog")):
        return 5
    return 6


def fact_authority_for_tier(tier: int) -> str:
    return ("high-confidence candidate fact" if tier <= 2 else
            "medium-confidence candidate fact" if tier == 3 else
            "low-confidence candidate fact" if tier == 4 else
            "inferred relationship only")


def default_permissions() -> dict:
    """§14 — everything denied except bounded retrieval-after-policy."""
    return {"retrieval_permission": True,
            "reference_view_permission": False,
            "fact_source_permission": False,
            "provider_input_permission": False,
            "artwork_reuse_permission": False,
            "design_memory_permission": False}


# --- §7 query planner -----------------------------------------------------------

def plan_queries(product, *, modes=MODES, confirmed_capacity: str = "") -> dict:
    """Deterministic bounded queries per mode. Unconfirmed dimensions or
    capacity are NEVER injected into exact-product queries."""
    brand = getattr(product.brand, "name", "") or ""
    name = product.name or ""
    sku = product.product_id or ""
    ptype = (product.product_type or "").strip()
    exact = [q for q in (
        f"{brand} {name}", f'"{sku}"', f"{brand} {name} {ptype}".strip(),
        f"{brand} {sku} {name}") if q.strip()][:4]
    if confirmed_capacity:
        exact.append(f"{brand} {name} {confirmed_capacity}")
    analog = [f"{ptype} bottle packaging dimensions",
              f"cosmetic {ptype} container specifications",
              f"{ptype} glass bottle 30ml 50ml capacity",
              f"{ptype} bottle closure dropper pump"][:4]
    inspiration = [f"luxury {ptype} packaging design",
                   f"{ptype} bottle label typography design",
                   "rose skincare packaging color palette",
                   "premium serum carton design"][:4]
    plan = {}
    if EXACT_PRODUCT_DISCOVERY in modes:
        plan[EXACT_PRODUCT_DISCOVERY] = exact
    if CATEGORY_ANALOG_DISCOVERY in modes:
        plan[CATEGORY_ANALOG_DISCOVERY] = analog
    if VISUAL_INSPIRATION_DISCOVERY in modes:
        plan[VISUAL_INSPIRATION_DISCOVERY] = inspiration
    total = sum(len(v) for v in plan.values())
    limit = DEFAULT_LIMITS["max_queries"]
    if total > limit:                      # §8 bound, exact-first priority
        for mode in (VISUAL_INSPIRATION_DISCOVERY,
                     CATEGORY_ANALOG_DISCOVERY):
            while total > limit and plan.get(mode):
                plan[mode].pop()
                total -= 1
    return plan


# --- §6 search connector (search-first; no SERP scraping fallback) --------------

def run_search(query: str, config: dict) -> list[dict]:
    """Governed search via the configured provider. No provider configured →
    WebPolicyError(WEB_RESEARCH_NOT_CONFIGURED); never a silent fallback."""
    provider = config.get("search_provider")
    if not provider or not config.get("search_key_present"):
        raise WebPolicyError(WEB_RESEARCH_NOT_CONFIGURED,
                             "no search provider configured "
                             "(WEB_SEARCH_PROVIDER / WEB_SEARCH_API_KEY)")
    raise WebPolicyError(WEB_SEARCH_PROVIDER_UNAVAILABLE,
                         f"search provider {provider!r} has no connector")


# --- §10 session runner -----------------------------------------------------------

def run_research_session(product, *, modes=MODES, user=None) -> "object":
    """One bounded research session. Creates the session row, plans queries,
    runs search+fetch under policy, quarantines, and STOPS at human review.
    Never calls an image provider; never creates a DesignProject/task."""
    from apps.pipeline.models import WebAccessRecord, WebResearchSession

    config = gateway_config()
    session = WebResearchSession.objects.create(
        product_identity=f"{product.product_id} — {product.name}",
        candidate_id=product.product_id, modes=list(modes),
        status="PLANNED", created_by=user)
    plan = plan_queries(product, modes=modes)
    session.queries = plan
    session.status = "SEARCHING"
    session.save(update_fields=["queries", "status", "updated_at"])

    summary: dict = {"schema_version": SESSION_SCHEMA,
                     "source_counts": {m: 0 for m in modes},
                     "exact_match_findings": [], "analog_findings": [],
                     "inspiration_findings": [], "extracted_facts": [],
                     "conflicting_facts": [], "blocked_sources": [],
                     "rights_summary": "all sources default RIGHTS_UNKNOWN; "
                                       "every use permission default-deny",
                     "confidence_summary": ""}
    try:
        for mode, queries in plan.items():
            for q in queries:
                WebAccessRecord.objects.create(
                    session=session, kind="search", url="", domain="",
                    outcome="attempted", detail=f"{mode}: {q}"[:300])
                run_search(q, config)     # raises when unconfigured
    except WebPolicyError as exc:
        WebAccessRecord.objects.create(
            session=session, kind="policy_block", outcome=exc.code,
            detail=str(exc)[:300])
        summary["blocked_sources"].append(
            {"code": exc.code, "detail": str(exc)[:200]})
        summary["confidence_summary"] = (
            "session blocked before retrieval — no facts, no images, "
            "nothing to review")
        session.summary = summary
        session.status = "BLOCKED"
        session.human_review_status = "UNREVIEWED"
        session.session_hash = hashlib.sha256(json.dumps(
            {"q": plan, "s": summary}, sort_keys=True,
            default=str).encode()).hexdigest()
        session.save(update_fields=["summary", "status",
                                    "human_review_status", "session_hash",
                                    "updated_at"])
        return session

    session.summary = summary
    session.status = "AWAITING_HUMAN_REVIEW"
    session.session_hash = hashlib.sha256(json.dumps(
        {"q": plan, "s": summary}, sort_keys=True,
        default=str).encode()).hexdigest()
    session.save(update_fields=["summary", "status", "session_hash",
                                "updated_at"])
    return session


# --- §13 image-element classification ----------------------------------------------

def classify_image_elements(described_elements: list[str]) -> dict:
    """Deterministic default classification. Water/condensation/shadow/
    reflection/lighting default to PHOTOGRAPHIC STYLING — never printed
    artwork without explicit evidence (the task-#51 lesson)."""
    out = {}
    for el in described_elements:
        key = el.strip().lower()
        if any(s in key for s in STYLING_ELEMENTS):
            out[el] = "photographic_styling"
        elif any(s in key for s in ("label", "printed", "typography", "logo")):
            out[el] = "printed_artwork_candidate"
        elif any(s in key for s in ("bottle", "cap", "wall", "silhouette",
                                    "geometry")):
            out[el] = "physical_geometry"
        elif any(s in key for s in ("fill", "liquid", "product colour",
                                    "product color")):
            out[el] = "product_fill"
        else:
            out[el] = "uncertain"
    out["_policy"] = STYLING_DEFAULT
    return out


# --- §22 bounded design-reasoning context -------------------------------------------

def build_web_reference_context(session) -> dict:
    """web_reference_context/1.0 — ONLY human-approved sources, bounded fields,
    never raw page content. The CD/PE receive nothing else."""
    approved = session.sources.filter(
        human_review_state__in=("APPROVED_EXACT", "APPROVED_ANALOG",
                                "APPROVED_INSPIRATION", "APPROVED_FACT_SOURCE"))
    return {
        "schema_version": CONTEXT_SCHEMA,
        "session_id": session.id,
        "sources": [{
            "source_id": s.id,
            "classification": s.classification,
            "human_review_state": s.human_review_state,
            "source_tier": s.source_tier,
            "fact_authority": fact_authority_for_tier(s.source_tier),
            "rights_state": s.rights_state,
            "provider_input_permission": s.provider_input_permission,
            "content_sha256": s.content_sha256,
            "prohibited_uses": [
                "copying layouts/artwork", "exact-product fidelity claims"
                if s.classification != "exact" else "none-beyond-rights",
                "production authority", "design-memory ingestion"],
        } for s in approved],
    }


__all__ = [
    "SESSION_SCHEMA", "SOURCE_SCHEMA", "FACT_SCHEMA", "CONTEXT_SCHEMA",
    "MODES", "EXACT_PRODUCT_DISCOVERY", "CATEGORY_ANALOG_DISCOVERY",
    "VISUAL_INSPIRATION_DISCOVERY", "DEFAULT_LIMITS", "TIER_LABELS",
    "WebPolicyError", "gateway_config", "check_url_policy", "check_robots",
    "check_mime", "quarantine_write", "normalize_url", "governed_fetch",
    "html_to_text", "classify_tier",
    "fact_authority_for_tier", "default_permissions", "plan_queries",
    "run_search", "run_research_session", "classify_image_elements",
    "build_web_reference_context", "STYLING_DEFAULT",
    "WEB_RESEARCH_NOT_CONFIGURED", "WEB_SECURITY_POLICY_BLOCKED",
    "WEB_ROBOTS_DISALLOWED", "WEB_UNSUPPORTED_CONTENT_TYPE",
    "WEB_FETCH_SIZE_LIMIT", "WEB_EXACT_PRODUCT_NOT_FOUND",
]
