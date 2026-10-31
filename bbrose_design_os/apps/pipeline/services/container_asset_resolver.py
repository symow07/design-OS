"""Product-container asset resolution from existing design memory
(Phase 2B-3V-PRE).

The preflight looked only at ``Product.product_image`` /
``Product.packaging_image`` / ``TaskReference(kind='container')`` — far too
narrow. This resolver searches the COMPLETE local corpus (Product fields,
``DesignReference``, the DIP-0A file inventory, media directories) lexically for
a product's assets, classifies each candidate, and produces a
``product_container_asset_resolution/1.0`` record.

Disciplines:
* no provider / semantic / external call — pure lexical + bounded metadata;
* an EXACT classification requires a strong SKU / distinctive-name match — a
  similar lip-gloss box is SAME_FAMILY, never the exact product (§2);
* the resolver NEVER changes ownership / rights / permission state, and never
  auto-approves — it reports candidates for human approval (§5);
* a machine-proposed exact match is a CANDIDATE requiring human confirmation
  before it can become product evidence (§3).
"""
from __future__ import annotations

import hashlib
import json
from apps.pipeline.targets.container import archetypes as _declared
import re
from pathlib import Path

from django.conf import settings

SCHEMA = "product_container_asset_resolution/1.0"

# --- §2 classifications ------------------------------------------------------
EXACT_CONTAINER_IMAGE = "EXACT_PRODUCT_CONTAINER_IMAGE"
EXACT_PACKAGING_ARTWORK = "EXACT_PRODUCT_PACKAGING_ARTWORK"
EXACT_AI_REFERENCE = "EXACT_PRODUCT_AI_REFERENCE"
SAME_FAMILY = "SAME_PRODUCT_FAMILY_REFERENCE"
SAME_ARCHETYPE = "SAME_CONTAINER_ARCHETYPE_REFERENCE"
CATEGORY_STYLE = "CATEGORY_STYLE_REFERENCE"
DECORATIVE_ONLY = "DECORATIVE_MATERIAL_ONLY"
IRRELEVANT = "IRRELEVANT"

_EXACT = {EXACT_CONTAINER_IMAGE, EXACT_PACKAGING_ARTWORK, EXACT_AI_REFERENCE}

# --- pilot-mode outcomes (§6) ------------------------------------------------
PHOTO_GROUNDED = "PHOTO_GROUNDED"
LIBRARY_GROUNDED = "LIBRARY_GROUNDED"
NO_RELEVANT_ASSETS = "NO_RELEVANT_ASSETS_FOUND"

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# §BH61(a), ruled: ""compact" is removed from the jar word-list. It is its own form and mapping it into
# jar is wrong, not approximate." It now has its own row.
# §BH70(1): lipstick, mascara and pencil have their own rows, read BEFORE the tube's — the tube's held "mascara" and
# "liner", so a mascara and an eyeliner resolved as a squeeze tube, and a lipstick resolved as nothing at all. The
# compact is read first too, so a "gloss palette" is a palette. Substrings, as this reader has always matched.
_ARCHETYPE_WORDS = {"compact": ("compact", "palette", "pressed powder", "hinged case"),
                    "lipstick": ("lipstick", "lip stick", "balm stick"),
                    "mascara": ("mascara", "wand", "liquid liner", "liquid eyeliner"),
                    "pencil": ("pencil", "eyeliner", "eye liner", "lip liner", "kohl", "kajal"),
                    "tube": ("tube", "gloss", "lip gloss"),
                    "bottle": ("bottle", "dropper", "serum", "pump", "spray"),
                    "jar": ("jar", "pot", "balm")}


def _canonical(p) -> str:
    return json.dumps(p, sort_keys=True, separators=(",", ":"), default=str)


def _hash(p) -> str:
    return hashlib.sha256(_canonical(p).encode()).hexdigest()[:32]


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(str(text or "").lower()))


def _archetype_of(product) -> str:
    """§BH61(a): the product's form, or a REFUSAL naming what was missing and where it was looked for.

    This returned "bottle" for anything it did not recognise — one of the four places the owner's palette
    could become a bottle.
    """
    t = (getattr(product, "product_type", "") or getattr(product, "name", "") or "").lower()
    for arche, words in _ARCHETYPE_WORDS.items():
        if any(w in t for w in words):
            return arche
    raise _declared.ArchetypeUnresolved(
        ["product.product_type", "product.name", "_ARCHETYPE_WORDS"], value=t or None)


def _sku_terms(product) -> set[str]:
    """Distinctive SKU/name terms that would identify the EXACT product."""
    terms = set()
    for attr in ("product_id", "item_no", "barcode_ean"):
        v = str(getattr(product, attr, "") or "").lower().strip()
        if v:
            terms.add(v)
            terms.add(v.replace("-", "").replace(" ", ""))
    # distinctive (>=4-char, non-generic) name tokens
    generic = {"lip", "gloss", "the", "and", "with", "set", "box", "for",
               "cosmetic", "cosmetics", "product", "color", "colour"}
    for tok in _tokens(getattr(product, "name", "")):
        if len(tok) >= 4 and tok not in generic:
            terms.add(tok)
    return {t for t in terms if t}


def _classify(product, *, text, source_kind, brand_name):
    """(classification, confidence, matched_terms) for one candidate."""
    low = (text or "").lower()
    sku = _sku_terms(product)
    matched_sku = sorted(t for t in sku if t and t in low)
    ptype = (getattr(product, "product_type", "") or "").lower()
    category = (getattr(product, "category", "") or "").lower()
    arche = _archetype_of(product)
    brand = (brand_name or "").lower()

    same_brand = bool(brand) and brand in low
    same_family = bool(ptype) and ptype in low
    same_archetype = any(w in low for w in _ARCHETYPE_WORDS.get(arche, ()))
    same_category = bool(category) and (f" {category} " in f" {low} "
                                        or category in _tokens(low))

    if matched_sku:
        # a strong SKU / distinctive-name hit → EXACT, keyed by source kind
        cls = {"image": EXACT_CONTAINER_IMAGE, "packaging": EXACT_PACKAGING_ARTWORK,
               "ai": EXACT_AI_REFERENCE}.get(source_kind, EXACT_PACKAGING_ARTWORK)
        return cls, round(min(1.0, 0.6 + 0.1 * len(matched_sku)), 2), matched_sku
    if same_brand and same_family:
        return SAME_FAMILY, 0.5, sorted(t for t in (brand, ptype) if t in low)
    if same_archetype:
        return SAME_ARCHETYPE, 0.4, [w for w in _ARCHETYPE_WORDS.get(arche, ()) if w in low][:3]
    if same_category or same_family:
        return CATEGORY_STYLE, 0.3, [t for t in (category, ptype) if t and t in low]
    if source_kind == "material":
        return DECORATIVE_ONLY, 0.2, []
    return IRRELEVANT, 0.0, []


def _permitted_use(cls: str, confirmed: bool) -> dict:
    """What a candidate MAY be used for, before any human approval."""
    return {
        "product_evidence": cls in _EXACT and confirmed,
        "profile_evidence": cls in _EXACT and confirmed,
        "concept_reference": cls in (SAME_FAMILY, SAME_ARCHETYPE, CATEGORY_STYLE),
        "concept_analysis_only": cls in (CATEGORY_STYLE, DECORATIVE_ONLY),
        "production_artwork": False,      # never automatic
    }


def _search_design_references(product, brand_name):
    from apps.core.models import DesignReference
    media = Path(settings.MEDIA_ROOT)
    out = []
    for r in DesignReference.objects.filter(active=True):
        text = " ".join([r.name or "", r.summary or "", " ".join(r.tags or []),
                         r.product_type or "", r.category or "", r.image_path or ""])
        kind = "packaging" if "dieline" in text.lower() or "box" in text.lower() else "image"
        cls, conf, hits = _classify(product, text=text, source_kind=kind,
                                    brand_name=brand_name)
        if cls == IRRELEVANT:
            continue
        img = str(r.image_path or "")
        out.append({
            "asset_id": f"DesignReference:{r.pk}", "filename": r.name,
            "locator": img, "source_type": "DesignReference",
            "classification": cls, "confidence": conf, "matched_terms": hits,
            "container_archetype": _archetype_of(product),
            "apparent_dimensions": None,
            "file_present": bool(img) and (media / img).exists(),
            "ownership_status": "HOUSE_PRODUCTION_LINEAGE_UNCONFIRMED",
            "rights_status": "RIGHTS_UNREVIEWED",
            "permission_state": "CANDIDATE",
            "permitted_use": _permitted_use(cls, confirmed=False)})
    return out


def _search_inventory(product, brand_name, *, cap=25):
    inv = Path(getattr(settings, "DIP_INVENTORY_PATH",
                       Path(settings.BASE_DIR).parent / "var"
                       / "design_intelligence" / "audits" / "dip0" / "inventory"
                       / "inventory.jsonl"))
    out = []
    if not inv.exists():
        return out
    with open(inv, encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            rp = rec.get("relative_path") or ""
            cls, conf, hits = _classify(product, text=rp, source_kind="material",
                                        brand_name=brand_name)
            if cls in (IRRELEVANT,):
                continue
            cat = rec.get("category")
            cat = cat.get("value") if isinstance(cat, dict) else cat
            out.append({
                "asset_id": f"inventory:{(rec.get('sha256') or rp)[:32]}",
                "filename": Path(rp).name, "locator": rp,
                "source_type": "DIP_INVENTORY", "inventory_category": cat,
                "classification": cls, "confidence": conf, "matched_terms": hits,
                "container_archetype": _archetype_of(product),
                "ownership_status": "UNKNOWN", "rights_status": "UNVERIFIED",
                "permission_state": "CANDIDATE",
                "permitted_use": _permitted_use(cls, confirmed=False)})
            if len(out) >= cap:
                break
    return out


def resolve_product_assets(product) -> dict:
    """product_container_asset_resolution/1.0 for one product. No provider,
    no writes, no approvals — a candidate report for human review."""
    brand_name = getattr(getattr(product, "brand", None), "name", "") or ""

    # direct product image fields (the narrow preflight source)
    direct = []
    for attr, kind in (("product_image", "image"), ("packaging_image", "packaging")):
        f = getattr(product, attr, None)
        name = getattr(f, "name", "") if f else ""
        if name:
            direct.append({"asset_id": f"Product.{attr}", "filename": name,
                           "locator": name, "source_type": "Product",
                           "classification": EXACT_CONTAINER_IMAGE
                           if kind == "image" else EXACT_PACKAGING_ARTWORK,
                           "confidence": 1.0, "matched_terms": ["direct_field"],
                           "container_archetype": _archetype_of(product),
                           "permission_state": "PRODUCT_OWNED",
                           "permitted_use": _permitted_use(
                               EXACT_CONTAINER_IMAGE, confirmed=True)})

    candidates = direct + _search_design_references(product, brand_name) \
        + _search_inventory(product, brand_name)
    candidates.sort(key=lambda c: (-c["confidence"],
                                   c["classification"], c["asset_id"]))

    exact = [c for c in candidates if c["classification"] in _EXACT]
    same = [c for c in candidates if c["classification"] in (SAME_FAMILY, SAME_ARCHETYPE)]
    category = [c for c in candidates if c["classification"] in (CATEGORY_STYLE, DECORATIVE_ONLY)]

    if exact:
        mode = PHOTO_GROUNDED
        outcome = "EXACT_PRODUCT_ASSET_FOUND"
    elif same or category:
        mode = LIBRARY_GROUNDED
        outcome = "NO_EXACT_PRODUCT_ASSET_LIBRARY_GROUNDED_PILOT_AVAILABLE"
    else:
        mode = NO_RELEVANT_ASSETS
        outcome = "NO_RELEVANT_ASSETS_FOUND"

    record = {
        "schema_version": SCHEMA,
        "product_id": getattr(product, "product_id", None),
        "product_name": getattr(product, "name", None),
        "brand": brand_name,
        "container_archetype": _archetype_of(product),
        "recorded_dimensions_mm": {
            "w": getattr(product, "width_mm", None),
            "d": getattr(product, "depth_mm", None),
            "h": getattr(product, "height_mm", None),
            "source": "PRODUCT_RECORD", "verification": "AS_RECORDED"},
        "sources_searched": ["Product.product_image", "Product.packaging_image",
                             "DesignReference", "DIP_INVENTORY"],
        "exact_candidates": exact,
        "same_family_or_archetype_candidates": same,
        "category_or_decorative_candidates": category[:12],
        "exact_asset_found": bool(exact),
        "recommended_pilot_mode": mode,
        "outcome": outcome,
        "requires_human_confirmation": True,
        "photo_to_profile_validation": "APPLICABLE" if exact else "NOT_APPLICABLE",
    }
    record["resolution_hash"] = _hash({
        "product_id": record["product_id"], "outcome": outcome, "mode": mode,
        "exact": [c["asset_id"] for c in exact],
        "same": sorted(c["asset_id"] for c in same)})
    return record


__all__ = [
    "SCHEMA", "resolve_product_assets", "PHOTO_GROUNDED", "LIBRARY_GROUNDED",
    "NO_RELEVANT_ASSETS", "EXACT_CONTAINER_IMAGE", "EXACT_PACKAGING_ARTWORK",
    "EXACT_AI_REFERENCE", "SAME_FAMILY", "SAME_ARCHETYPE", "CATEGORY_STYLE",
    "DECORATIVE_ONLY", "IRRELEVANT",
]
