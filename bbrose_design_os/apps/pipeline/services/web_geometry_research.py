"""VQ-1-RESET-1 Part B — governed physical-geometry web research.

SUPERSEDED-BY §BH46: the system never contacts suppliers and acquires
nothing — the owners hand the product information to it. This module's queries name
supplier sites; it is reached from no view, command or target, and is kept as history.

Reuses the existing gateway wholesale: ``TavilySearchConnector`` for
search and ``web_research``'s SSRF/robots/MIME/byte-limit/quarantine
machinery for fetching. What is new here is the *target*: §10 asks for
physical feasibility evidence for a product CATEGORY, not discovery of a
named product, so the queries are the eight explicit specification
queries from §11 rather than the product-identity planner.

Dimensional authority is a separate axis from retention: a marketplace
page may be retained as context and still be barred from authorizing a
measurement (§12). Nothing here approves anything — every measurement is
a candidate awaiting human decision (§13/§15).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from apps.pipeline.services import web_research as wr

SESSION_SCHEMA = "web_container_geometry_research/1.0"
MEASUREMENT_SCHEMA = "web_geometry_measurement_candidate/1.0"

RESEARCH_TARGET = ("premium 30 ml frosted cylindrical cosmetic serum bottle "
                   "with rose-gold metallic dropper closure")
RESEARCH_PURPOSE = "PHYSICAL_FEASIBILITY_NOT_DESIGN_INSPIRATION"

#: §11 — specification queries, not visual-similarity queries
QUERIES = (
    "30ml frosted glass serum bottle rose gold dropper technical drawing",
    "30ml cylindrical serum bottle dimensions aluminum dropper collar",
    "30ml cosmetic glass bottle 18/415 dropper dimensions",
    "frosted glass serum bottle rose gold closure manufacturer specification",
    "30ml dropper bottle technical drawing PDF",
    "cosmetic dropper cap aluminum collar bulb dimensions",
    "30ml serum bottle neck finish closure specification",
    "premium serum bottle supplier CAD dimensions",
)

#: §10 — inspiration/gallery sources are never dimensional sources
EXCLUDED_AS_DIMENSIONAL_SOURCE = (
    "pinterest.", "dribbble.", "behance.", "instagram.", "shutterstock.",
    "istockphoto.", "gettyimages.", "freepik.", "adobe.com/stock",
    "unsplash.", "pexels.", "vecteezy.", "etsy.",
)
#: §12 — marketplace snippets are never sufficient dimensional authority
MARKETPLACE_DOMAINS = ("amazon.", "ebay.", "aliexpress.", "alibaba.",
                       "temu.", "made-in-china.", "dhgate.", "walmart.",
                       "wish.com", "indiamart.")

DIMENSIONAL_AUTHORITY_TIERS = {
    1: "MANUFACTURER_TECHNICAL_PAGE_OR_DRAWING",
    2: "OFFICIAL_SUPPLIER_CATALOGUE_OR_PDF",
    3: "ESTABLISHED_PACKAGING_DISTRIBUTOR_WITH_DIMENSIONS",
}
NO_AUTHORITY = "NOT_A_DIMENSIONAL_AUTHORITY"

#: §13 sufficiency
MIN_QUALIFIED_ANALOGS = 3
MIN_SOURCES_WITH_DIMENSIONS = 2
MIN_TECHNICAL_DRAWINGS = 1
MIN_DISTINCT_CLOSURE_CONSTRUCTIONS = 2

#: §12 the measurement referents that must never be merged
REFERENTS = ("bottle_diameter", "body_height", "total_height",
             "neck_finish", "neck_diameter", "collar_diameter",
             "collar_height", "bulb_width", "bulb_height", "pipette_length",
             "nominal_capacity", "brimful_capacity", "glass_weight",
             "bottle_material", "closure_material")

_SUPPLIER_HINTS = ("packaging", "bottle", "glass", "cosmetic", "closure",
                   "dropper", "vial", "container", "pack", "berlin",
                   "supplier", "manufactur")
_DRAWING_HINTS = ("technical drawing", "technical-drawing", "spec sheet",
                  "specification", "datasheet", "data sheet", "cad",
                  "drawing.pdf", "/drawings/", "dimension")

_MM = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*(mm|millimet(?:er|re)s?)\b",
                 re.I)
_ML = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*(ml|mL|millilit(?:er|re)s?)\b")
_NECK = re.compile(r"\b(\d{2}\s*/\s*\d{3})\b")


def _now():
    return datetime.now(timezone.utc).isoformat()


def dimensional_authority(domain: str) -> tuple[str, int | None]:
    """Separate from retention tier: may this source authorize a
    measurement at all, and at what tier?"""
    d = (domain or "").lower()
    if any(k in d for k in EXCLUDED_AS_DIMENSIONAL_SOURCE):
        return "EXCLUDED_INSPIRATION_OR_STOCK_SOURCE", None
    if any(k in d for k in MARKETPLACE_DOMAINS):
        return "MARKETPLACE_SNIPPET_INSUFFICIENT_AUTHORITY", None
    if any(k in d for k in _SUPPLIER_HINTS):
        return DIMENSIONAL_AUTHORITY_TIERS[2], 2
    return NO_AUTHORITY, None


def classify_source(result: dict) -> dict:
    domain = (result.get("domain") or
              urlparse(result.get("url", "")).hostname or "")
    text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
    url = (result.get("url") or "").lower()
    authority, tier = dimensional_authority(domain)
    has_drawing = any(h in text or h in url for h in _DRAWING_HINTS)
    if tier == 2 and has_drawing:
        tier, authority = 1, DIMENSIONAL_AUTHORITY_TIERS[1]
    return {"schema_version": wr.SOURCE_SCHEMA, "domain": domain,
            "url": result.get("url"), "title": result.get("title"),
            "snippet": result.get("snippet"),
            "query": result.get("query"),
            "retention_tier": wr.classify_tier(domain),
            "dimensional_authority": authority,
            "dimensional_authority_tier": tier,
            "may_authorize_measurements": tier is not None,
            "technical_drawing_indicated": has_drawing,
            "rights": wr.default_permissions(),
            "human_decision": "PENDING",
            "fetched": False}


def extract_measurements(source: dict, text: str) -> list[dict]:
    """Candidate measurements with their referent kept separate. Values
    are never averaged and never merged across sources (§13)."""
    out = []
    low = (text or "").lower()

    def add(referent, raw, unit, evidence):
        out.append({
            "schema_version": MEASUREMENT_SCHEMA,
            "component_referent": referent, "raw_value": raw, "unit": unit,
            "normalized_value_mm": (float(str(raw).replace(",", "."))
                                    if unit == "mm" else None),
            "total_height_includes_closure": (
                None if referent != "total_height" else "UNSTATED"),
            "source_url": source["url"], "source_domain": source["domain"],
            "source_tier": source["dimensional_authority_tier"],
            "source_authority": source["dimensional_authority"],
            "evidence_text": evidence[:200],
            "confidence": (0.6 if source["dimensional_authority_tier"] == 1
                           else 0.45 if source["dimensional_authority_tier"]
                           == 2 else 0.0),
            "verification_state": "UNVERIFIED",
            "may_authorize": source["may_authorize_measurements"],
            "human_decision": "PENDING",
        })

    for m in _NECK.finditer(text or ""):
        add("neck_finish", m.group(1).replace(" ", ""), "neck_finish_code",
            text[max(0, m.start() - 60):m.end() + 60])
    for m in _ML.finditer(text or ""):
        add("nominal_capacity", m.group(1), "ml",
            text[max(0, m.start() - 60):m.end() + 60])
    for m in _MM.finditer(text or ""):
        ctx = low[max(0, m.start() - 70):m.end() + 30]
        referent = ("collar_diameter" if "collar" in ctx or "ferrule" in ctx
                    else "neck_diameter" if "neck" in ctx
                    else "bulb_width" if "bulb" in ctx
                    else "pipette_length" if "pipette" in ctx
                    or "tube" in ctx
                    else "total_height" if "total" in ctx or "overall" in ctx
                    else "body_height" if "height" in ctx
                    else "bottle_diameter" if "diameter" in ctx
                    or "width" in ctx else "UNASSIGNED_DIMENSION")
        add(referent, m.group(1), "mm",
            text[max(0, m.start() - 70):m.end() + 30])
    return out


def sufficiency(sources: list, measurements: list) -> dict:
    qualified = [s for s in sources if s["may_authorize_measurements"]]
    with_dims = {m["source_url"] for m in measurements
                 if m["may_authorize"] and m["unit"] == "mm"}
    drawings = [s for s in qualified if s["technical_drawing_indicated"]]
    closures = {s["domain"] for s in qualified}
    checks = {
        "at_least_3_qualified_analogs": len(qualified) >= MIN_QUALIFIED_ANALOGS,
        "at_least_2_sources_with_dimensions":
            len(with_dims) >= MIN_SOURCES_WITH_DIMENSIONS,
        "at_least_1_technical_drawing": len(drawings) >= MIN_TECHNICAL_DRAWINGS,
        "at_least_2_closure_constructions":
            len(closures) >= MIN_DISTINCT_CLOSURE_CONSTRUCTIONS,
    }
    return {"checks": checks, "sufficient": all(checks.values()),
            "qualified_analogs": len(qualified),
            "sources_with_dimensions": len(with_dims),
            "technical_drawings": len(drawings),
            "distinct_domains": len(closures)}


def conflicts(measurements: list) -> list:
    """§13 — contradictory values are preserved side by side, never
    averaged."""
    by_ref: dict[str, list] = {}
    for m in measurements:
        if m["unit"] != "mm" or not m["may_authorize"]:
            continue
        by_ref.setdefault(m["component_referent"], []).append(m)
    out = []
    for ref, rows in by_ref.items():
        vals = {r["normalized_value_mm"] for r in rows}
        if len(vals) > 1:
            out.append({"component_referent": ref,
                        "values_mm": sorted(v for v in vals if v),
                        "sources": [r["source_url"] for r in rows],
                        "resolution": "PRESERVED_UNRESOLVED_HUMAN_DECISION",
                        "note": "contradictory values are never averaged"})
    return out


def run_geometry_session(*, connector=None, search_fn=None,
                         queries=QUERIES, max_results: int = 8) -> dict:
    """Bounded search-only session. Fetching is a separate governed step;
    this stage never downloads artwork and never approves anything."""
    from apps.pipeline.services.round_designer import \
        TavilySearchConnector
    conn = connector or TavilySearchConnector()
    fn = search_fn or (lambda q: conn.search(q, depth="basic",
                                             max_results=max_results))
    config = wr.gateway_config()
    session = {"schema_version": SESSION_SCHEMA, "created_at": _now(),
               "research_target": RESEARCH_TARGET,
               "purpose": RESEARCH_PURPOSE,
               "gateway": {k: v for k, v in config.items()
                           if k != "search_key_present"},
               "search_provider_configured": config["search_key_present"],
               "queries": list(queries), "searches": [], "sources": [],
               "measurements": [], "warnings": [], "provider_calls": 0}
    seen = set()
    for q in queries:
        try:
            payload = fn(q)
        except wr.WebPolicyError as e:
            session["warnings"].append({"query": q, "code": e.args[0],
                                        "detail": str(e.args[-1])[:200]})
            continue
        except Exception as e:                       # noqa: BLE001
            session["warnings"].append({"query": q, "code": "SEARCH_FAILED",
                                        "detail": f"{type(e).__name__}"})
            continue
        session["provider_calls"] += 1
        session["searches"].append({
            "query": q, "result_count": len(payload.get("results") or []),
            "latency_ms": payload.get("latency_ms"),
            "provider_request_id": payload.get("provider_request_id", "")})
        for r in payload.get("results") or []:
            url = wr.normalize_url(r.get("url") or "")
            if not url or url in seen:
                continue
            seen.add(url)
            src = classify_source({**r, "url": url})
            session["sources"].append(src)
            if src["may_authorize_measurements"]:
                session["measurements"].extend(
                    extract_measurements(src, f"{r.get('title', '')} "
                                              f"{r.get('snippet', '')}"))
    session["sufficiency"] = sufficiency(session["sources"],
                                         session["measurements"])
    session["conflicts"] = conflicts(session["measurements"])
    session["human_review"] = {
        "physical_analog": "PENDING", "fact_source": "PENDING",
        "component_semantic_relevance": "PENDING",
        "measurements_for_concept_geometry": "PENDING"}
    session["status"] = ("AWAITING_HUMAN_REVIEW"
                         if session["sources"] else "BLOCKED_NO_SOURCES")
    session["note"] = ("search-only; no artwork reuse; images remain "
                       "reference-only and provider input stays false "
                       "unless separately approved")
    return session
