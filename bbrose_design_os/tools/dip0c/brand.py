"""Brand / logo technical audit and brand-name detection (DIP-0C3a).

C3a audits **technique and relationships only**. It infers **no** ownership, no
licence, no canonical status and no permission — those are C3b/C3d, and the
confirmed values are human-only and guarded in `config`.

Two rules the probe forced into the design:

1. **A filename or folder proves nothing.** Three of the five vector logos in the
   BBROSE office folder are third-party (ATC ×2, JOJIA ×1), and the two biggest,
   most BBROSE-named files are the *worst* master candidates. Name and location are
   recorded as *supporting evidence only*.
2. **Brand name comes from LIVE TEXT or from nobody.** PyMuPDF reads a live
   wordmark (`DIRECT`). An **outlined** wordmark carries no readable text, so the
   brand name is `null` / `REQUIRES_HUMAN` — never guessed from the filename, never
   OCR'd (OCR stays deferred to DIP-0E).
"""
from __future__ import annotations

import re
from pathlib import Path

import fitz

from tools.dip0.provenance import human_block
from tools.dip0b.limits import Budget
from tools.dip0b import config as BC

from . import config as C
from . import pdf_vector

PARSER = f"{C.TOOL_NAME}.brand/{C.TOOL_VERSION}"

# A composition, not a mark: mostly raster, many placed images, page-scale.
COMPOSITION_RASTER_COVERAGE = 0.60
COMPOSITION_MIN_IMAGES = 5
# An isolated logo: little geometry, no raster dependency.
ISOLATED_LOGO_MAX_PATHS = 400
_THIRD_PARTY_RE = re.compile(r"\b(ATC|JOJIA|JOJIIA)\b", re.I)


def _tier(v, tier, evidence, confidence=0.0):
    return {"value": v, "tier": tier, "evidence": list(evidence),
            "confidence": round(float(confidence), 3), "parser": PARSER}


# --- brand name: live text, or nobody ---------------------------------------
def detect_brand_name(rel_path: str) -> dict:
    """DIRECT from live text. Outlined wordmark -> REQUIRES_HUMAN, never guessed."""
    full = C.physical_path(rel_path, C.REPO_ROOT)
    try:
        doc = fitz.open(full)
    except Exception as e:  # noqa: BLE001
        return _tier(None, C.TIER_REQUIRES_HUMAN,
                     [f"not readable as a PDF-backed file: {type(e).__name__}"])
    try:
        spans = []
        for pno in range(min(doc.page_count, 3)):
            td = doc[pno].get_text("dict")
            for b in td["blocks"]:
                if b["type"] != 0:
                    continue
                for ln in b["lines"]:
                    for sp in ln["spans"]:
                        t = (sp.get("text") or "").strip()
                        if t:
                            spans.append({"text": t, "page": pno,
                                          "font": sp.get("font"),
                                          "size": round(sp.get("size", 0), 1),
                                          "bbox": [round(v, 1)
                                                   for v in sp.get("bbox", [])]})
        if not spans:
            out = _tier(
                None, C.TIER_REQUIRES_HUMAN,
                ["0 live-text spans: the wordmark is OUTLINED geometry",
                 "the brand name is NOT machine-readable — no OCR in C3 (deferred "
                 "to DIP-0E), and the filename is never used to assert a name"],
                confidence=0.0)
            out["live_text_spans"] = []
            return out

        # A brand name is asserted ONLY when the live text contains a KNOWN brand
        # token. Otherwise the extracted text is EVIDENCE, not a brand name: the
        # largest span in a design composition is a headline, not a wordmark
        # (BBROSE.pdf's biggest span is "OIL"). The machine hands the text to the
        # human and declines to say which of it — if any — is the brand.
        joined = " | ".join(s["text"] for s in spans)
        known = _known_brand_in(joined)
        sample = sorted(spans, key=lambda s: -s["size"])[:6]
        prov = [{"text": s["text"], "page": s["page"], "font": s["font"],
                 "size": s["size"], "bbox": s["bbox"]} for s in sample]

        if known:
            out = _tier(
                known, C.TIER_DIRECT,
                [f"known brand token {known!r} read DIRECTLY from live text",
                 f"{len(spans)} live-text span(s); largest: "
                 f"{sample[0]['text']!r}"],
                confidence=0.85)
        else:
            out = _tier(
                None, C.TIER_REQUIRES_HUMAN,
                [f"{len(spans)} live-text span(s) extracted, but NONE matches a "
                 "known brand token",
                 f"largest span is {sample[0]['text']!r} — a headline is not a "
                 "wordmark, so the machine does NOT assert it as the brand name",
                 "the extracted text is offered to the reviewer as evidence"],
                confidence=0.0)
        out["live_text_spans"] = prov
        return out
    finally:
        doc.close()


KNOWN_BRANDS = ("BBROSE", "BBROSE®", "BB ROSE") + C.THIRD_PARTY_BRANDS
_KNOWN_RE = re.compile(r"\b(BBROSE|BB\s*ROSE|ATC|JOJI+A)\b", re.I)


def _known_brand_in(text: str) -> str | None:
    m = _KNOWN_RE.search(text or "")
    if not m:
        return None
    tok = m.group(1).upper().replace(" ", "")
    if tok.startswith("JOJI"):
        return "JOJIA"
    if tok.startswith("BB"):
        return "BBROSE"
    return tok


def third_party_brand_in(text: str | None) -> str | None:
    m = _THIRD_PARTY_RE.search(text or "")
    return m.group(1).upper() if m else None


# --- the technical audit ----------------------------------------------------
def audit(entry: dict) -> dict:
    rel = entry["relative_path"]
    ext = Path(rel).suffix.lower()
    name = Path(rel).name
    folder = str(Path(rel).parent)

    rec = {
        "relative_path": rel,
        "filename": name,
        "source_package": folder,
        "format": ext,
        "dip0a_classification": entry["dip0a_classification"],
        "c3_test_role": entry["c3_test_role"],
        "queue_i_membership": entry["queue_i_membership"],
        "parser": PARSER,
        # C3a decides NONE of these — they are C3b/C3d and human-gated.
        "ownership": _not_assessed("ownership is a C3b question; C3a audits "
                                   "technique only"),
        "license": _not_assessed("licence is a C3b question; evidence is never "
                                 "approval"),
        "canonical_brand_master": None,
        "permissions": C.permission_matrix(),
        "human": human_block(),
    }

    if ext not in (".ai", ".pdf"):
        rec["vector_or_raster"] = "raster" if ext in (
            ".png", ".jpg", ".jpeg", ".psd") else "other"
        rec["brand_name"] = _tier(
            None, C.TIER_REQUIRES_HUMAN,
            [f"{ext} has no live-text layer to read a brand name from"])
        rec["isolated_logo_likelihood"] = _tier(
            False, C.TIER_DIRECT,
            ["a raster render can never be a canonical vector master "
             "(DIP-0A rule: a BBROSE-named raster is PRODUCT_REFERENCE)"], 0.9)
        rec["brand_master_candidate"] = C.machine_brand_master(None)
        rec["capability_limitations"] = [
            f"no vector geometry available for {ext}"]
        rec["name_and_folder_evidence"] = _name_folder_evidence(name, folder)
        rec["classification_override"] = None
        return rec

    a = pdf_vector.audit(rel, Budget(BC.DEFAULT_LIMITS))
    paths = a["path_count"]["value"]
    cov = a["raster"]["coverage_fraction"]["value"]
    imgs = a["raster"]["image_count"]
    spans = a["live_text_spans"]
    fonts = a["embedded_fonts"]
    seps = a["separations"]
    gmt = a["gradients_masks_transparency"]["value"]

    brand = detect_brand_name(rel)
    tp = third_party_brand_in(brand["value"]) or third_party_brand_in(name)

    composition = (cov >= COMPOSITION_RASTER_COVERAGE
                   and imgs >= COMPOSITION_MIN_IMAGES)
    isolated = (not composition and cov < 0.05 and 0 < paths
                <= ISOLATED_LOGO_MAX_PATHS)

    rec.update({
        "vector_or_raster": "vector",
        "page_count": a["page_count"],
        "bounding_box_mm": a["boxes"]["surface_mm"],
        "path_count": paths,
        "raster_coverage": cov,
        "embedded_image_count": imgs,
        "live_text_present": spans > 0,
        "live_text_spans": spans,
        "outlined_wordmark_likelihood": _tier(
            spans == 0, C.TIER_DIRECT,
            ["0 live-text spans: any wordmark must be outlined geometry"
             if spans == 0 else
             f"{spans} live-text span(s): the wordmark is live, not outlined"],
            0.85),
        "fonts_detected": fonts,
        "transparency": {"soft_masks": gmt["soft_masks"],
                         "transparency_groups": gmt["transparency_groups"]},
        "gradients": gmt["shadings"],
        "spot_colors": seps["spot_names"],
        "process_colors_count": seps["count"],
        "editability": a["editability_score"],
        "technical_readiness": a["technical_readiness"],
        "brand_name": brand,
        "detected_third_party_brand": _tier(
            tp, C.TIER_DIRECT if (tp and brand["value"]) else C.TIER_HEURISTIC,
            ([f"third-party brand {tp!r} read from LIVE TEXT — the contamination "
              "is directly readable"] if (tp and third_party_brand_in(brand["value"]))
             else [f"third-party brand {tp!r} appears in the FILENAME — supporting "
                   "evidence only, it does not by itself establish ownership"]
             if tp else ["no third-party brand token detected"]),
            0.85 if tp and third_party_brand_in(brand["value"]) else
            0.5 if tp else 0.0),
        "isolated_logo_likelihood": _tier(
            isolated, C.TIER_HEURISTIC,
            [f"{paths} paths, {cov:.0%} raster coverage, {imgs} embedded image(s)"],
            0.7 if isolated else 0.6),
        "raster_heavy_composition": _tier(
            composition, C.TIER_DIRECT,
            [f"{cov:.0%} raster coverage over {imgs} embedded images — a design "
             "composition, not isolated logo geometry" if composition
             else f"{cov:.0%} raster coverage, {imgs} image(s)"],
            0.85 if composition else 0.6),
        "name_and_folder_evidence": _name_folder_evidence(name, folder),
        "capability_limitations": _limits(spans, ext),
    })

    rec["classification_override"] = _override(rec, entry, composition)
    rec["brand_master_candidate"] = _nominate(rec, entry, composition,
                                              isolated, tp)
    return rec


def _not_assessed(why: str) -> dict:
    return {"value": None, "status": "NOT_ASSESSED_IN_C3A", "note": why}


def _name_folder_evidence(name: str, folder: str) -> dict:
    """SUPPORTING evidence only. It can never establish brand identity."""
    return {
        "filename": name,
        "folder": folder,
        "filename_mentions_bbrose": "bbrose" in name.lower(),
        "folder_is_bbrose_office": "محفوظات" in folder,
        "is_decisive": False,
        "note": "filename and folder are SUPPORTING evidence only. Three of the "
                "five vector logos in this office folder are third-party, so "
                "location proves neither ownership nor brand identity.",
    }


def _limits(spans: int, ext: str) -> list[str]:
    out = []
    if spans == 0:
        out.append("brand name REQUIRES_HUMAN: the wordmark is outlined and no OCR "
                   "runs in C3 (deferred to DIP-0E)")
    out.append("C3a assesses NO ownership, licence, canonical status or permission")
    return out


def _override(rec: dict, entry: dict, composition: bool) -> dict | None:
    """The C1 pattern: DIP-0A is never rewritten; the correction lives here."""
    if not composition or entry["dip0a_classification"] != "BRAND_MASTER":
        return None
    return {
        "inventory_category_original": entry["dip0a_classification"],
        "audit_category_override": C.OVERRIDE_DESIGN_COMPOSITION,
        "reuse_posture": C.machine_posture(C.POSTURE_REFERENCE_ONLY),
        "override_reason": "labelled BRAND_MASTER but the evidence says design "
                           "composition, not isolated logo geometry",
        "override_evidence": [
            f"~{rec['raster_coverage']:.0%} raster coverage",
            f"{rec['embedded_image_count']} embedded images",
            f"{rec['live_text_spans']} live-text spans across "
            f"{rec['fonts_detected']} fonts",
            "large composition-style file",
            "NOT isolated logo geometry",
        ],
        "override_confidence": 0.85,
        "human_confirmed_category": None,
        "cannot_be_canonical_master": True,
        "note": "DIP-0A keeps the original BRAND_MASTER label as the historical "
                "record. Both the original label and this contradictory evidence "
                "go to the human-review queue.",
    }


# Only these roles are BRAND candidates at all. A background, a sticker sheet or a
# baby-pattern is clean vector geometry — and is still not a candidate to be the
# BBROSE brand master. Being isolated vector art is necessary, never sufficient.
BRAND_ROLES = ("brand_master_mislabelled", "logo_candidate_outlined",
               "logo_candidate_live_text", "third_party_logo",
               "third_party_logo_live_text", "third_party_logo_misshelved",
               "third_party_deck", "bbrose_product_render",
               "bbrose_palette_raster")


def _nominate(rec: dict, entry: dict, composition: bool, isolated: bool,
              tp) -> str | None:
    """Machine may NOMINATE a BRAND_MASTER_CANDIDATE. It may never declare the
    canonical master, never nominates a composition or a third-party mark, and
    never nominates a file that is not a brand asset in the first place."""
    if entry["c3_test_role"] not in BRAND_ROLES:
        return C.machine_brand_master(None)
    if composition or tp or not isolated:
        return C.machine_brand_master(None)
    return C.machine_brand_master(C.BRAND_MASTER_CANDIDATE)


def load_pilot() -> list[dict]:
    import json
    return json.loads(
        Path(C.C3_PILOT_MANIFEST).read_text(encoding="utf-8"))["entries"]
