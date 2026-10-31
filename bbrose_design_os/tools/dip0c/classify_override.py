"""Classification overrides (DIP-0C) — never rewrite the DIP-0A inventory.

DIP-0A mis-shelved some files (EULA/ReadMe PDFs, third-party presentation decks)
as REUSABLE_VECTOR_ASSET. DIP-0C records a *deeper correction* as an override
alongside the original category; the DIP-0A inventory stays the historical record.

A PDF is NOT a reusable asset merely because it contains vector paths. Multi-page
decks, catalogs, guidelines and licence docs are reference/technical material.
"""
from __future__ import annotations

import re

from tools.dip0.provenance import Inferred

from . import config as C

PARSER = f"{C.TOOL_NAME}.classify_override/{C.TOOL_VERSION}"

_LICENCE_RE = re.compile(
    r"\beula\b|read\s*me|licen[cs]e|terms\s*of\s*use|\btou\b|copyright|"
    r"important.*read|please.*read", re.I)
_PRESENTATION_RE = re.compile(r"presentation|deck|catalog(ue)?|look\s*book|lookbook",
                              re.I)
_GUIDELINE_RE = re.compile(r"guideline|brand\s*book|brand\s*guide|style\s*guide", re.I)
_LOGO_SHEET_RE = re.compile(r"logo\s*sheet|logo\s*pack|logos?\b", re.I)
_COLLECTION_RE = re.compile(r"collection|stickers?|\bset\b|pack\b|bundle", re.I)

# Audit categories an override may assign (beyond DIP-0A's).
OVERRIDE_CATEGORIES = (
    "LICENSE_EVIDENCE", "THIRD_PARTY_RESTRICTED", "REFERENCE_ONLY",
    "COLLECTION_SHEET", "BRAND_GUIDELINE", "LOGO_SHEET", "PRESENTATION_DECK",
    "CATALOG",
)


def override_record(original_category: str, override: str | None, reason: str,
                    evidence: list[str], confidence: float) -> dict:
    """The override envelope. `human_confirmed_category` is never machine-set."""
    return {
        "inventory_category_original": original_category,
        "audit_category_override": override,
        "override_reason": reason,
        "override_evidence": evidence,
        "override_confidence": round(confidence, 3),
        "human_confirmed_category": None,
        "parser": PARSER,
    }


def classify_pdf(filename: str, *, page_count: int, first_page_text: str,
                 original_category: str, third_party: bool) -> dict:
    """Decide whether a PDF classified as a reusable vector asset is really a
    licence doc / deck / guideline / collection sheet / isolated asset."""
    fn = filename
    text = (first_page_text or "")[:2000]
    blob = f"{fn}\n{text}"

    if _LICENCE_RE.search(fn) or _LICENCE_RE.search(text):
        return override_record(
            original_category, "LICENSE_EVIDENCE",
            "filename/first-page text indicates a licence/readme document",
            [f"filename={fn!r}", "licence/readme markers"], 0.85)

    if _GUIDELINE_RE.search(blob):
        return override_record(
            original_category, "BRAND_GUIDELINE",
            "brand/style guideline document", [f"filename={fn!r}"], 0.6)

    if _PRESENTATION_RE.search(blob) or (page_count >= 3 and third_party):
        cat = "THIRD_PARTY_RESTRICTED" if third_party else "PRESENTATION_DECK"
        return override_record(
            original_category, cat,
            "multi-page presentation/deck — not an isolated reusable asset",
            [f"filename={fn!r}", f"pages={page_count}",
             f"third_party={third_party}"], 0.65)

    if page_count >= 3:
        return override_record(
            original_category, "REFERENCE_ONLY",
            f"{page_count}-page multi-page PDF; treat as reference, not one asset",
            [f"pages={page_count}"], 0.5)

    if _COLLECTION_RE.search(fn):
        return override_record(
            original_category, "COLLECTION_SHEET",
            "collection/set naming — multiple assets, resolve in DIP-0C2",
            [f"filename={fn!r}"], 0.45)

    # no override — the DIP-0A category stands
    return override_record(original_category, None,
                           "no reclassification indicated", [], 0.0)


def third_party_brand(filename: str) -> bool:
    return bool(re.search(r"\bATC\b|JOJI+A?", filename, re.I))


def posture_hint(override: dict, *, is_font_quarantine: bool = False) -> dict:
    """Map an override to a MACHINE reuse-posture candidate (never APPROVED)."""
    cat = override["audit_category_override"]
    mapping = {
        "LICENSE_EVIDENCE": C.POSTURE_OUT_OF_SCOPE,
        "THIRD_PARTY_RESTRICTED": C.POSTURE_THIRD_PARTY_RESTRICTED,
        "PRESENTATION_DECK": C.POSTURE_REFERENCE_ONLY,
        "BRAND_GUIDELINE": C.POSTURE_REFERENCE_ONLY,
        "CATALOG": C.POSTURE_REFERENCE_ONLY,
        "REFERENCE_ONLY": C.POSTURE_REFERENCE_ONLY,
        "LOGO_SHEET": C.POSTURE_REFERENCE_ONLY,
        "COLLECTION_SHEET": C.POSTURE_REUSABLE_AFTER_REVIEW,
    }
    posture = mapping.get(cat, C.POSTURE_REUSABLE_AFTER_REVIEW)
    if is_font_quarantine:
        posture = C.POSTURE_QUARANTINED
    inf = Inferred(value=C.machine_posture(posture), source="classification_override",
                   evidence=override["override_evidence"] or ["default posture"],
                   confidence=override["override_confidence"], parser=PARSER)
    return inf.to_dict()
