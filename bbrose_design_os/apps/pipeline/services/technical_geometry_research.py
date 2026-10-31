"""VQ-1-RESET-1B — targeted technical-document and product-variant research.

SUPERSEDED-BY §BH46: the system never contacts suppliers and acquires
nothing — the owners hand the product information to it. This module's queries name
supplier sites; it is reached from no view, command or target, and is kept as history.

RESET-1A failed on evidence QUALITY, not source count: the pages found
were category and marketing pages with no dimension tables. This session
therefore searches only for technical documents and exact product
variants, and enforces two rules the previous pass lacked:

* a generic marketing or category page can never authorize a dimension,
  however reputable its domain — only an exact product-variant page, a
  dimension table or a technical drawing can (``VQ_PRODUCT_VARIANT_PAGE_
  REQUIRED``);
* a measurement whose referent is not stated explicitly in the source
  text is REJECTED rather than guessed (``REFERENT_UNRESOLVED``), and
  bottle facts are never merged with closure facts.

Four tracks run separately (bottle / closure / compatibility / component
semantics) so an unrelated product's closure can never silently supply a
bottle dimension. Everything ends awaiting human decisions; this module
generates no geometry.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from apps.pipeline.services import geometry_evidence as ge
from apps.pipeline.services import web_research as wr

SESSION_SCHEMA = "technical_geometry_research/2.0"
PACKET_SCHEMA = "vq1_technical_geometry_evidence/2.0"
DRAWING_SCHEMA = "technical_drawing_record/1.0"
MEASUREMENT_SCHEMA = "exact_referent_measurement/2.0"

# §1 stable findings carried forward
VQ_DIMENSIONAL_EVIDENCE_INSUFFICIENT = "VQ_DIMENSIONAL_EVIDENCE_INSUFFICIENT"
VQ_SNIPPET_MEASUREMENTS_REJECTED = "VQ_SNIPPET_MEASUREMENTS_REJECTED"
VQ_TECHNICAL_DRAWING_COVERAGE_INSUFFICIENT = \
    "VQ_TECHNICAL_DRAWING_COVERAGE_INSUFFICIENT"
VQ_COMPONENT_SEMANTICS_UNRESOLVED = "VQ_COMPONENT_SEMANTICS_UNRESOLVED"
VQ_STRUCTURAL_GENERATION_BLOCKED = "VQ_STRUCTURAL_GENERATION_BLOCKED"
VQ_PRODUCT_VARIANT_PAGE_REQUIRED = "VQ_PRODUCT_VARIANT_PAGE_REQUIRED"
VQ_MANUFACTURER_SPECIFICATION_REQUIRED = \
    "VQ_MANUFACTURER_SPECIFICATION_REQUIRED"
VQ_PHYSICAL_GEOMETRY_EVIDENCE_INCOMPLETE = \
    "VQ_PHYSICAL_GEOMETRY_EVIDENCE_INCOMPLETE"
READY = "READY_FOR_GEOMETRY_REVIEW"

#: §14 bounded session
LIMITS = {"max_searches": 16, "max_retained_results": 40,
          "max_fetched_pages": 20, "max_pdfs": 10,
          "max_retained_images": 30, "max_results_per_domain": 5}

#: §7/§8 four separate tracks
TRACKS = {
    "A_bottle": (
        "30 ml glass serum bottle technical drawing pdf",
        "30ml cylindrical dropper bottle dimensions 18/415",
        "30 ml cosmetic glass bottle CAD drawing",
        "30 ml serum bottle product specification diameter height",
        "filetype:pdf 30ml serum bottle dimensions",
        "site:liquidbottles.com 30 ml glass bottle dimensions",
    ),
    "B_closure": (
        "18/415 aluminum dropper closure technical drawing",
        "18/415 rubber bulb aluminum collar dimensions",
        "cosmetic dropper assembly exploded drawing",
        "filetype:pdf 18/415 dropper closure drawing",
        "site:panyuepacking.com dropper closure technical drawing",
    ),
    "C_compatibility": (
        "30 ml bottle compatible dropper closure specification",
        "30 ml glass bottle 18/410 technical data sheet",
        "site:nicerpackaging.com 30ml dropper bottle dimensions",
    ),
    "D_semantics": (
        "dropper closure decorative outer cover versus exposed rubber bulb",
        "rubber dropper bulb with molded flared skirt specification",
    ),
}

#: §3/§4 carried-forward decisions
CARRIED_DECISIONS = {
    "NOMINAL_CAPACITY": {"value": "30", "unit": "ml",
                         "authority": "PRODUCT_CONCEPT_REQUIREMENT",
                         "is_physical_geometry_approval": False,
                         "note": "bottle dimensions may NOT be derived from "
                                 "nominal capacity alone"},
    "NECK_FINISH_CANDIDATES": {
        "values": ["18/415", "18/410", "20/410", "24/410"],
        "selected": None, "state": "UNRESOLVED",
        "selection_requires": ["exact bottle product variant",
                               "exact compatible closure",
                               "manufacturer or official supplier "
                               "documentation",
                               "explicit diameter/thread referents"]},
    "WS-20": {"classification": "NECK_FINISH_REFERENCE_ONLY",
              "state": "NEEDS_VERIFICATION",
              "may_support": ["neck-finish terminology", "thread families"],
              "does_not_authorize": [
                  "bottle diameter", "bottle height", "collar diameter",
                  "collar height", "bulb geometry", "closure construction",
                  "total assembled height",
                  "structural backbone generation"],
              "is_sufficient_complete_drawing": False},
}

#: §10 referent vocabulary, split by component so the two never merge
BOTTLE_REFERENTS = ("BODY_OUTSIDE_DIAMETER", "BOTTLE_HEIGHT_WITHOUT_CLOSURE",
                    "SHOULDER_HEIGHT", "NECK_FINISH", "NECK_OUTSIDE_DIAMETER",
                    "NOMINAL_CAPACITY", "OVERFLOW_CAPACITY", "GLASS_WEIGHT",
                    "BOTTLE_MATERIAL")
CLOSURE_REFERENTS = ("COLLAR_OUTSIDE_DIAMETER", "COLLAR_VISIBLE_HEIGHT",
                     "DARK_COMPONENT_MAXIMUM_WIDTH",
                     "DARK_COMPONENT_VISIBLE_HEIGHT", "PIPETTE_LENGTH",
                     "CLOSURE_MATERIAL", "CLOSURE_NECK_FINISH")
ASSEMBLY_REFERENTS = ("TOTAL_HEIGHT_WITH_CLOSURE", "NECK_OVERLAP")

#: relevance screen — the bottle queries also surface laboratory and
#: chromatography glassware, which is dimensionally irrelevant here
COSMETIC_CONTEXT = ("serum", "cosmetic", "dropper", "essential oil",
                    "skincare", "beauty", "boston round", "euro", "essence",
                    "perfume", "packaging", "bottle")
LAB_SUPPLY_DOMAINS = ("thermofisher", "glenresearch", "wheaton", "sigma",
                      "fishersci", "vwr", "corning", "labdepot",
                      "chromatography", "restek", "agilent")


def relevance(track: str, domain: str, title: str, url: str) -> dict:
    """A dimensionally-precise document about the wrong product family is
    still the wrong evidence."""
    d, t = (domain or "").lower(), f"{title} {url}".lower()
    if any(k in d for k in LAB_SUPPLY_DOMAINS):
        return {"relevant": False,
                "relevance_note": "laboratory / chromatography supplier — "
                                  "wrong product family for a cosmetic "
                                  "serum bottle"}
    if track in ("A_bottle", "B_closure", "C_compatibility") and \
            not any(k in t for k in COSMETIC_CONTEXT):
        return {"relevant": False,
                "relevance_note": "no cosmetic/packaging context in the "
                                  "title or URL"}
    return {"relevant": True, "relevance_note": None}


#: §6 page classes that may never authorize a dimension
GENERIC_PAGE_MARKERS = ("category", "collection", "blog", "guide", "news",
                        "about", "wholesale", "manufacturers", "solutions",
                        "services", "index", "sitemap", "how-to", "buyers")
DISALLOWED_DOMAINS = ("pinterest", "dribbble", "behance", "instagram",
                      "shutterstock", "istockphoto", "gettyimages",
                      "freepik", "unsplash", "pexels", "amazon", "ebay",
                      "aliexpress", "alibaba", "temu", "etsy", "dhgate",
                      "made-in-china", "wikipedia", "reddit")

_SKU = re.compile(
    r"(?:\b|/)(?:sku|item|product|p)[-_/]([a-z0-9][a-z0-9-]{2,}\d[a-z0-9-]*)",
    re.I)
_CODE = re.compile(r"\b([A-Z]{2,5}[-_]?\d{3,6})\b")
_TABLE_HINT = ("dimension", "specification", "spec table", "technical data",
               "measurements", "height", "diameter", "capacity")


def _now():
    return datetime.now(timezone.utc).isoformat()


# --- §6 page classification ---------------------------------------------------

def page_class(url: str, title: str, text: str = "") -> dict:
    """Only an exact product variant, a dimension table or a technical
    document may authorize a dimension."""
    u, t = (url or "").lower(), (title or "").lower()
    body = (text or "").lower()
    domain = urlparse(url or "").hostname or ""
    if any(k in domain for k in DISALLOWED_DOMAINS):
        return {"page_class": "DISALLOWED_SOURCE_TYPE",
                "may_authorize_dimensions": False,
                "reason": "marketplace / stock / gallery / editorial"}
    is_pdf = u.endswith(".pdf") or "filetype=pdf" in u
    drawing = any(k in t or k in u for k in
                  ("technical drawing", "drawing", "cad", "spec sheet",
                   "datasheet", "data sheet", "specification"))
    sku = bool(_SKU.search(u)) or bool(_CODE.search(title or ""))
    has_table = sum(1 for k in _TABLE_HINT if k in body) >= 3 and \
        len(re.findall(r"\d{1,3}(?:\.\d)?\s*mm", body)) >= 3
    generic = any(k in u or k in t for k in GENERIC_PAGE_MARKERS)
    if is_pdf or drawing:
        cls, ok = "TECHNICAL_DOCUMENT", True
    elif has_table:
        cls, ok = "DIMENSION_TABLE_PAGE", True
    elif sku and not generic:
        cls, ok = "PRODUCT_VARIANT_PAGE", True
    elif generic:
        cls, ok = "GENERIC_MARKETING_OR_CATEGORY_PAGE", False
    else:
        cls, ok = "UNCLASSIFIED_PAGE", False
    return {"page_class": cls, "may_authorize_dimensions": ok,
            "is_pdf": is_pdf, "drawing_indicated": drawing,
            "sku_indicated": sku, "dimension_table_detected": has_table,
            "reason": (None if ok else VQ_PRODUCT_VARIANT_PAGE_REQUIRED)}


# --- §10 exact-referent extraction -------------------------------------------

_REFERENT_WORDS = (
    (("body diameter", "bottle diameter", "outside diameter", "outer "
      "diameter", "od "), "BODY_OUTSIDE_DIAMETER", "bottle"),
    (("bottle height", "body height", "height without cap",
      "height w/o cap"), "BOTTLE_HEIGHT_WITHOUT_CLOSURE", "bottle"),
    (("shoulder height", "shoulder rise"), "SHOULDER_HEIGHT", "bottle"),
    (("neck diameter", "neck od"), "NECK_OUTSIDE_DIAMETER", "bottle"),
    (("overflow capacity", "brimful", "brim full"), "OVERFLOW_CAPACITY",
     "bottle"),
    (("glass weight", "bottle weight"), "GLASS_WEIGHT", "bottle"),
    (("collar diameter", "ferrule diameter", "collar od"),
     "COLLAR_OUTSIDE_DIAMETER", "closure"),
    (("collar height", "ferrule height"), "COLLAR_VISIBLE_HEIGHT",
     "closure"),
    (("bulb width", "bulb diameter", "teat diameter"),
     "DARK_COMPONENT_MAXIMUM_WIDTH", "closure"),
    (("bulb height", "teat height"), "DARK_COMPONENT_VISIBLE_HEIGHT",
     "closure"),
    (("pipette length", "tube length", "dropper length", "stem length"),
     "PIPETTE_LENGTH", "closure"),
    (("total height", "overall height", "assembled height",
      "height with cap", "height with closure"),
     "TOTAL_HEIGHT_WITH_CLOSURE", "assembly"),
)
_VALUE = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*(mm|cm|in|ml|g)\b", re.I)
#: a referent implies a dimension family; a value in the wrong family is a
#: mis-parse, not a measurement (e.g. "PIPETTE_LENGTH 30 ml")
_LENGTH_UNITS = ("mm", "cm", "in")
_REFERENT_UNITS = {
    "BODY_OUTSIDE_DIAMETER": _LENGTH_UNITS,
    "BOTTLE_HEIGHT_WITHOUT_CLOSURE": _LENGTH_UNITS,
    "SHOULDER_HEIGHT": _LENGTH_UNITS,
    "NECK_OUTSIDE_DIAMETER": _LENGTH_UNITS,
    "COLLAR_OUTSIDE_DIAMETER": _LENGTH_UNITS,
    "COLLAR_VISIBLE_HEIGHT": _LENGTH_UNITS,
    "DARK_COMPONENT_MAXIMUM_WIDTH": _LENGTH_UNITS,
    "DARK_COMPONENT_VISIBLE_HEIGHT": _LENGTH_UNITS,
    "PIPETTE_LENGTH": _LENGTH_UNITS,
    "TOTAL_HEIGHT_WITH_CLOSURE": _LENGTH_UNITS,
    "OVERFLOW_CAPACITY": ("ml",),
    "GLASS_WEIGHT": ("g",),
}


def unit_matches_referent(referent: str, unit: str) -> bool:
    allowed = _REFERENT_UNITS.get(referent)
    return bool(allowed) and unit in allowed
_CLOSURE_INCLUDED = ("with cap", "with closure", "assembled", "with dropper",
                     "including cap")
_CLOSURE_EXCLUDED = ("without cap", "w/o cap", "without closure",
                     "bottle only", "excluding cap")


def extract_exact(text: str, source: dict, track: str) -> list[dict]:
    """A measurement is kept ONLY when the source text names its referent
    explicitly within the same clause. Anything else is rejected."""
    out, low = [], (text or "").lower()
    for m in _VALUE.finditer(low):
        raw, unit = m.group(1).replace(",", "."), m.group(2).lower()
        window = low[max(0, m.start() - 90):m.start()]
        # the NEAREST preceding referent word wins — scanning the list in
        # declaration order would let an earlier sentence's "body diameter"
        # capture the next sentence's "collar diameter" value
        referent = component = None
        best = -1
        for words, ref, comp in _REFERENT_WORDS:
            pos = max(window.rfind(w) for w in words)
            if pos > best:
                best, referent, component = pos, ref, comp
        if best < 0:
            referent = component = None
        if referent is None:
            continue                       # §10 no guessing from proximity
        if not unit_matches_referent(referent, unit):
            continue                       # wrong dimension family = mis-parse
        ctx = low[max(0, m.start() - 120):m.end() + 40]
        if referent == "TOTAL_HEIGHT_WITH_CLOSURE":
            incl = True
        elif any(w in ctx for w in _CLOSURE_INCLUDED):
            incl = True
        elif any(w in ctx for w in _CLOSURE_EXCLUDED):
            incl = False
        else:
            incl = "UNSTATED"
        norm = (float(raw) if unit == "mm" else float(raw) * 10
                if unit == "cm" else round(float(raw) * 25.4, 2)
                if unit == "in" else None)
        out.append({
            "schema_version": MEASUREMENT_SCHEMA,
            "raw_source_text": ctx.strip()[:200],
            "raw_value": raw, "original_unit": unit,
            "normalized_value": norm,
            "normalized_unit": "mm" if norm is not None else unit,
            "component_referent": referent, "component": component,
            "source_id": source["source_id"], "source_url": source["url"],
            "product_code": source.get("product_code"),
            "variant_identity": source.get("variant_identity"),
            "closure_included": incl,
            "source_tier": source["authority_tier"],
            "page_class": source["page_class"],
            "extraction_method": "GOVERNED_FETCH_EXPLICIT_REFERENT",
            "track": track,
            "confidence": 0.75 if source["page_class"] in (
                "TECHNICAL_DOCUMENT", "DIMENSION_TABLE_PAGE") else 0.55,
            "verification_state": "UNVERIFIED", "conflict_state": "NONE",
            "human_decision": "PENDING"})
    return out


def product_code(url: str, title: str) -> str | None:
    for pat in (_CODE.search(title or ""), _SKU.search(url or "")):
        if pat:
            return pat.group(1).upper()
    return None


# --- §11 PDF handling ---------------------------------------------------------

def record_pdf(body: bytes, source: dict, out_dir: str,
              max_pages: int = 3) -> dict:
    """Preserve the complete original document and render its pages whole
    — never cropped, so the title block and dimensional legend survive."""
    import fitz
    os.makedirs(out_dir, exist_ok=True)
    sha = hashlib.sha256(body).hexdigest()[:16]
    raw = os.path.join(out_dir, f"{source['source_id']}_{sha}.pdf")
    with open(raw, "wb") as f:
        f.write(body)
    rec = {"schema_version": DRAWING_SCHEMA,
           "source_id": source["source_id"], "url": source["url"],
           "domain": source["domain"], "title": source.get("title"),
           "product_code": source.get("product_code"),
           "original_document": raw, "sha256_16": sha,
           "byte_count": len(body), "pages": [],
           "crop_policy": "FULL_PAGE_RENDER_TITLE_BLOCK_PRESERVED",
           "component_class": source.get("component_class", "UNCLASSIFIED"),
           "variant_specific": bool(source.get("product_code")),
           "revision_or_date": None, "rights": ge.rights_default(),
           "human_decision": "PENDING"}
    try:
        doc = fitz.open(raw)
        rec["page_count"] = doc.page_count
        rec["revision_or_date"] = (doc.metadata or {}).get("modDate") or None
        for i in range(min(max_pages, doc.page_count)):
            page = doc[i]
            png = os.path.join(out_dir,
                               f"{source['source_id']}_{sha}_p{i + 1}.png")
            page.get_pixmap(dpi=150).save(png)
            txt = page.get_text()
            rec["pages"].append({
                "page_number": i + 1, "render": png,
                "render_dpi": 150,
                "mm_callouts": len(re.findall(r"\d+(?:\.\d)?\s*mm", txt)),
                "text_chars": len(txt)})
        doc.close()
    except Exception as e:                                  # noqa: BLE001
        rec["render_error"] = f"{type(e).__name__}"
    return rec


# --- §9 sufficiency -----------------------------------------------------------

def sufficiency(session: dict) -> dict:
    b_variants = [s for s in session["sources"]
                  if s["track"] == "A_bottle" and
                  s["may_authorize_dimensions"]]
    c_variants = [s for s in session["sources"]
                  if s["track"] == "B_closure" and
                  s["may_authorize_dimensions"]]
    tables = {s["source_id"] for s in b_variants
              if s["page_class"] in ("DIMENSION_TABLE_PAGE",
                                     "TECHNICAL_DOCUMENT")}
    b_draw = [d for d in session["drawings"]
              if d["component_class"] == "bottle"]
    c_draw = [d for d in session["drawings"]
              if d["component_class"] == "closure"]
    compat = [s for s in session["sources"]
              if s["track"] == "C_compatibility" and
              s["may_authorize_dimensions"]]
    sem = [s for s in session["sources"] if s["track"] == "D_semantics"]
    meas = session["measurements"]
    dim = [m for m in meas if m["normalized_unit"] == "mm"]
    checks = {
        "at_least_3_bottle_variants": len(b_variants) >= 3,
        "at_least_2_bottle_dimension_tables": len(tables) >= 2,
        "at_least_1_bottle_technical_drawing": len(b_draw) >= 1,
        "at_least_2_closure_variants": len(c_variants) >= 2,
        "at_least_1_closure_drawing_or_exploded_view": len(c_draw) >= 1,
        "at_least_1_compatibility_source": len(compat) >= 1,
        "at_least_2_semantic_supporting_sources": len(sem) >= 2,
        # an empty list satisfies all() vacuously — a checklist that can
        # pass with no evidence is the self-certification failure mode this
        # whole workstream exists to remove, so require evidence first
        "at_least_1_dimensional_measurement": len(dim) >= 1,
        "every_measurement_has_exact_referent": bool(meas) and all(
            m["component_referent"] != "REFERENT_UNRESOLVED" for m in meas),
        "every_total_height_states_closure_inclusion": bool(meas) and all(
            m["closure_included"] is not None for m in meas
            if m["component_referent"] == "TOTAL_HEIGHT_WITH_CLOSURE"),
    }
    ok = all(checks.values())
    return {"checks": checks, "sufficient": ok,
            "state": READY if ok else VQ_PHYSICAL_GEOMETRY_EVIDENCE_INCOMPLETE,
            "counts": {"bottle_variants": len(b_variants),
                       "bottle_dimension_tables": len(tables),
                       "bottle_drawings": len(b_draw),
                       "closure_variants": len(c_variants),
                       "closure_drawings": len(c_draw),
                       "compatibility_sources": len(compat),
                       "semantic_sources": len(sem),
                       "measurements": len(meas),
                       "dimensional_measurements": len(dim)}}


def conflicts_by_referent(measurements: list) -> list:
    """Bottle and closure facts are compared only within their own
    component, and contradictions are preserved."""
    buckets: dict = {}
    for m in measurements:
        if m["normalized_value"] is None:
            continue
        buckets.setdefault((m["component"], m["component_referent"]),
                           []).append(m)
    out = []
    for (comp, ref), rows in buckets.items():
        vals = sorted({r["normalized_value"] for r in rows})
        if len(vals) > 1:
            out.append({
                "component": comp, "component_referent": ref,
                "values_mm": vals,
                "variants": sorted({str(r.get("variant_identity")
                                        or r["source_id"]) for r in rows}),
                "closure_inclusion_states": sorted(
                    {str(r["closure_included"]) for r in rows}),
                "resolution": "PRESERVED_UNRESOLVED_HUMAN_DECISION",
                "auto_resolved": False,
                "allowed_actions": list(ge.CONFLICT_ACTIONS),
                "required_human_action": "PENDING"})
    return out


# --- bounded session runner ---------------------------------------------------

def _ledger(session_row, kind, url="", domain="", outcome="", status=None,
            byte_count=0, detail=""):
    """§14 every search and fetch lands in WebAccessRecord. ApiCallRecord
    is deliberately untouched — it is the LLM/image ledger."""
    from apps.pipeline.models import WebAccessRecord
    return WebAccessRecord.objects.create(
        session=session_row, kind=kind, url=url[:2000], domain=domain[:200],
        outcome=outcome[:60], http_status=status, byte_count=byte_count,
        detail=detail[:300])


def run_session(*, user=None, connector=None, search_fn=None,
                fetch_fn=None, out_dir="docs/visual_quality/vq1_reset1b",
                limits=None) -> dict:
    from apps.pipeline.models import WebResearchSession
    from apps.pipeline.services.round_designer import \
        TavilySearchConnector

    lim = {**LIMITS, **(limits or {})}
    conn = connector or TavilySearchConnector()
    cfg = wr.gateway_config()
    row = WebResearchSession.objects.create(
        product_identity="VQ-1 RESET-1B — 30 ml cylindrical serum bottle "
                         "+ dropper closure (technical documents)",
        candidate_id="VQ1-RESET-1B",
        modes=list(TRACKS), queries={k: list(v) for k, v in TRACKS.items()},
        status="SEARCHING", created_by=user)
    session = {"schema_version": SESSION_SCHEMA, "session_id": row.id,
               "created_at": _now(), "limits": lim, "tracks": {},
               "sources": [], "measurements": [], "drawings": [],
               "images": [], "warnings": [], "provider_calls": 0,
               "fetches": 0, "pdfs": 0,
               "carried_decisions": CARRIED_DECISIONS}
    searched = 0
    per_domain: dict = {}
    seen = set()
    # each track gets its own slice of the retention budget, otherwise the
    # first track consumes it all and the closure/compatibility/semantics
    # tracks starve — which is exactly what the first run did
    per_track_cap = max(1, lim["max_retained_results"] // len(TRACKS))
    # the planned queries total exactly max_searches, so each track may run
    # all of its own; the global cap is what bounds the session
    per_track_searches = lim["max_searches"]
    for track, queries in TRACKS.items():
        session["tracks"][track] = {"queries": list(queries), "retained": 0,
                                    "retention_cap": per_track_cap}
        track_searches = 0
        for q in queries:
            if (searched >= lim["max_searches"]
                    or track_searches >= per_track_searches
                    or session["tracks"][track]["retained"] >= per_track_cap):
                break
            try:
                payload = (search_fn(q) if search_fn else
                           conn.search(q, depth="advanced", max_results=8))
                searched += 1
                track_searches += 1
                session["provider_calls"] += 1
                _ledger(row, "search", url="", domain="tavily",
                        outcome="OK", detail=f"{track}: {q[:120]}")
            except Exception as e:                          # noqa: BLE001
                session["warnings"].append(
                    {"track": track, "query": q,
                     "code": getattr(e, "args", ["SEARCH_FAILED"])[0]})
                _ledger(row, "search", domain="tavily", outcome="FAILED",
                        detail=f"{track}: {type(e).__name__}")
                continue
            for r in payload.get("results") or []:
                url = wr.normalize_url(r.get("url") or "")
                dom = (r.get("domain") or urlparse(url).hostname or "")
                if not url or url in seen:
                    continue
                if per_domain.get(dom, 0) >= lim["max_results_per_domain"]:
                    continue
                if session["tracks"][track]["retained"] >= per_track_cap:
                    break
                seen.add(url)
                per_domain[dom] = per_domain.get(dom, 0) + 1
                cls = page_class(url, r.get("title", ""))
                rel = relevance(track, dom, r.get("title", ""), url)
                if not rel["relevant"]:
                    cls = {**cls, "may_authorize_dimensions": False,
                           "reason": "OUT_OF_PRODUCT_FAMILY"}
                session["sources"].append({
                    "source_id": f"TS-{len(session['sources']) + 1:02d}",
                    "track": track, "url": url, "domain": dom,
                    "title": (r.get("title") or "")[:220],
                    "snippet_not_evidence": True,
                    "authority_tier": ge.authority_tier(
                        dom, r.get("title", ""), url),
                    "product_code": product_code(url, r.get("title", "")),
                    "variant_identity": None,
                    "component_class": ("bottle" if track == "A_bottle"
                                        else "closure" if track == "B_closure"
                                        else "assembly" if track ==
                                        "C_compatibility" else "semantics"),
                    **rel,
                    "rights": ge.rights_default(),
                    "human_decision": {a: "PENDING"
                                       for a in ge.SOURCE_ACTIONS[:4]},
                    "fetched": False, **cls})
                session["tracks"][track]["retained"] += 1
    row.status = "FETCHING"
    row.save(update_fields=["status"])

    # fetch phase — technical documents and variant pages first
    order = sorted(session["sources"],
                   key=lambda s: (not s["may_authorize_dimensions"],
                                  not s.get("is_pdf"),
                                  s["authority_tier"]))
    for s in order:
        if session["fetches"] >= lim["max_fetched_pages"]:
            break
        if s.get("is_pdf") and session["pdfs"] >= lim["max_pdfs"]:
            continue
        try:
            resp = (fetch_fn(s["url"]) if fetch_fn
                    else wr.governed_fetch(s["url"], cfg))
            body = resp.get("body") or b""
            session["fetches"] += 1
            s["fetched"] = True
            s["byte_count"] = len(body)
            s["mime_type"] = resp.get("mime_type")
            _ledger(row, "page_fetch", url=s["url"], domain=s["domain"],
                    outcome="FETCHED", status=resp.get("status_code"),
                    byte_count=len(body))
            if (resp.get("mime_type") or "").endswith("pdf"):
                session["pdfs"] += 1
                d = record_pdf(body, s, os.path.join(out_dir, "drawings"))
                session["drawings"].append(d)
                text = " ".join(p.get("render", "") for p in d["pages"])
                try:
                    import fitz
                    doc = fitz.open(d["original_document"])
                    text = "\n".join(p.get_text() for p in doc)
                    doc.close()
                except Exception:                            # noqa: BLE001
                    text = ""
            else:
                text = wr.html_to_text(body, limit=40000)
            recls = page_class(s["url"], s["title"], text)
            s.update(recls)
            s["variant_identity"] = s.get("product_code") or None
            if s["may_authorize_dimensions"]:
                session["measurements"].extend(
                    extract_exact(text, s, s["track"]))
        except Exception as e:                               # noqa: BLE001
            code = getattr(e, "args", ["FETCH_FAILED"])[0]
            s["fetch_blocked"] = str(code)
            _ledger(row, "policy_block", url=s["url"], domain=s["domain"],
                    outcome=str(code)[:60], detail=type(e).__name__)
    session["conflicts"] = conflicts_by_referent(session["measurements"])
    session["sufficiency"] = sufficiency(session)
    session["findings"] = [VQ_STRUCTURAL_GENERATION_BLOCKED,
                           VQ_COMPONENT_SEMANTICS_UNRESOLVED]
    if not session["sufficiency"]["sufficient"]:
        session["findings"] += [VQ_PHYSICAL_GEOMETRY_EVIDENCE_INCOMPLETE,
                                VQ_DIMENSIONAL_EVIDENCE_INSUFFICIENT]
    if session["sufficiency"]["counts"]["bottle_drawings"] == 0 or \
            session["sufficiency"]["counts"]["closure_drawings"] == 0:
        session["findings"].append(
            VQ_TECHNICAL_DRAWING_COVERAGE_INSUFFICIENT)
    session["geometry_generated"] = False
    session["image_generation_calls"] = 0
    session["status"] = "AWAITING_HUMAN_TECHNICAL_EVIDENCE_REVIEW"
    row.status = "AWAITING_HUMAN_REVIEW"
    row.summary = {k: v for k, v in session.items()
                   if k in ("schema_version", "sufficiency", "findings",
                            "provider_calls", "fetches", "pdfs")}
    row.save()
    return session
