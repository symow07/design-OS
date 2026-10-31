"""Slice 3 — classification, license evidence, ownership & quarantine posture.

Rules are an ORDERED table; the first match wins and records its own evidence.
Folder names are treated as HINTS, never as truth: nothing here promotes a file
to owned, licensed or approved. Every machine verdict is provisional and sits
beside an untouched `human_confirmed` block.
"""
from __future__ import annotations

import os
import re

from . import config as C
from .provenance import Inferred, human_block

# --- license evidence -------------------------------------------------------
# An anchored `^license` match missed the files that matter most: OFL.txt (the
# Open Font License), "Apache License.txt", "KGFonts-TOU.txt", "*-eula.txt",
# "Terms Of Use.URL". Search anywhere in the name, and grade the strength.
_STRONG_TOKENS = re.compile(
    r"licen[cs]e|\bofl\b|\beula\b|\btou\b|terms.of.use|\bterms\b|copyright"
    r"|apache|\bgpl\b|\bofl\b|permission|personal.use|commercial.use", re.I)
_WEAK_TOKENS = re.compile(
    r"read.?me|important.note|more.info|\bnote\b|\bfonts?\b|\bdemo\b|info", re.I)


def license_evidence_strength(filename: str, ext: str) -> str | None:
    """None | 'strong' | 'weak'.

    Any accompanying text/URL doc in an asset folder is documentation; only the
    named-licence forms are STRONG. Neither grants any right — strength only
    tells a reviewer where to look first.
    """
    if ext not in C.EVIDENCE_EXT:
        return None
    if _STRONG_TOKENS.search(filename):
        return "strong"
    if _WEAK_TOKENS.search(filename):
        return "weak"
    return "weak"          # a .txt/.url/.html beside assets is accompanying doc


def is_license_evidence(filename: str, ext: str) -> bool:
    return license_evidence_strength(filename, ext) is not None


def build_license_index(records: list[dict]) -> dict[str, list[dict]]:
    """dir -> [license evidence files in that dir]."""
    idx: dict[str, list[dict]] = {}
    for r in records:
        strength = license_evidence_strength(r["filename"], r["extension"])
        if strength:
            d = os.path.dirname(r["relative_path"])
            idx.setdefault(d, []).append(
                {"path": r["relative_path"], "filename": r["filename"],
                 "strength": strength})
    return idx


def attach_license_evidence(record: dict, index: dict[str, list[dict]]) -> None:
    """Nearest-ancestor folder association, bounded to the source root.

    Conservative by construction: presence of a licence file is EVIDENCE that
    terms accompany the asset — never proof of commercial-use, embedding or
    redistribution rights. `license_status` therefore never leaves PENDING.
    """
    evidence: list[dict] = []
    d = os.path.dirname(record["relative_path"])
    distance = 0
    while d and d.startswith("materials"):
        if d in index:
            for e in index[d]:
                if e["path"] == record["relative_path"]:
                    continue
                evidence.append({**e,
                                 "scope": "same_dir" if distance == 0 else "ancestor_dir",
                                 "distance": distance})
            if evidence:
                break          # nearest ancestor wins; do not keep climbing
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
        distance += 1

    record["license_evidence"] = evidence
    strengths = {e.get("strength") for e in evidence}
    record["license_status"] = Inferred(
        value="PENDING_HUMAN_CONFIRMATION" if evidence else "UNVERIFIED",
        source="folder_evidence" if evidence else "absent",
        evidence=[f"{e['path']} ({e.get('strength')})" for e in evidence]
        or ["no licence file in scope"],
        confidence=0.0,        # evidence is never a rights grant
        parser=f"{C.TOOL_NAME}.classify/{C.TOOL_VERSION}",
    ).to_dict()
    record["license_evidence_strength"] = (
        "strong" if "strong" in strengths else "weak" if strengths else "none")


# --- ownership --------------------------------------------------------------
BBROSE_RE = re.compile(r"bbrose", re.I)
THIRD_PARTY_LOGOS = {"ATC LOGO.ai", "JOJIA LOGO.ai"}
BRAND_CANDIDATE_NAMES = {"BBROSE.pdf", "BBROSE-1.pdf", "logo.pdf", "LOGO6.ai"}
# A brand MASTER is a vector/PDF original. A .png bearing the brand name is a
# render (often AI-generated marketing output) — never a master, and it must not
# slip into brand retrieval on the strength of its filename.
MASTER_EXT = {".ai", ".pdf", ".eps", ".svg"}


def ownership(record: dict) -> dict:
    """Ownership is NEVER established by folder location."""
    fn = record["filename"]
    if fn in THIRD_PARTY_LOGOS:
        return Inferred(
            value="UNCONFIRMED_THIRD_PARTY", source="filename_rule",
            evidence=[f"filename={fn}", "another company's mark"],
            confidence=0.8,
            parser=f"{C.TOOL_NAME}.classify/{C.TOOL_VERSION}").to_dict()
    if fn in BRAND_CANDIDATE_NAMES or BBROSE_RE.search(fn):
        return Inferred(
            value="LIKELY_BBROSE_UNCONFIRMED", source="filename_rule",
            evidence=[f"filename={fn}"], confidence=0.6,
            parser=f"{C.TOOL_NAME}.classify/{C.TOOL_VERSION}").to_dict()
    return Inferred(value="UNKNOWN", source="default", evidence=[],
                    confidence=0.0,
                    parser=f"{C.TOOL_NAME}.classify/{C.TOOL_VERSION}").to_dict()


# --- category rules ---------------------------------------------------------
# Folder-name hints (checked against the whole relative path, lowercased).
_HINTS = (
    ("PATTERN", (r"seamless[-_ ]?pattern", r"\bpattern\b")),
    ("BACKGROUND", (r"\bbackground\b", r"\bbg[-_]", r"gradient-background")),
    ("ICON", (r"\bicon\b", r"\bicons\b", r"\bsymbol\b")),
    ("MOTIF", (r"\bmotif\b", r"\bornament\b", r"\bfloral\b", r"\bdoodle\b",
               r"\bsticker", r"\bwreath\b", r"\bbadge")),
    ("DIELINE_REFERENCE", (r"\bdieline\b", r"\bdie[-_ ]?line\b", r"刀线", r"展盒")),
    ("PRODUCT_REFERENCE", (r"\bmockup\b", r"\bmock[-_ ]?up\b")),
)

_OUT_OF_SCOPE_PATH = (
    r"اكسسورز حمامات",            # bathroom fixtures
    r"\bbathroom\b",
    r"weixin videos",
    r"\breceipt\b", r"\binvoice\b", r"\bcargo\b",
)
_OUT_OF_SCOPE_EXT = {".xlsx", ".xls", ".mp4", ".mov"}

# "Unrelated commercial mockups": only excluded when the subject is clearly not
# cosmetics packaging AND the file is a mockup. A `paper-bag`/`shopping-bag`
# mockup is packaging-relevant and must survive this rule.
_MOCKUP_RE = re.compile(r"mock[-_ ]?up", re.I)
_UNRELATED_MOCKUP_SUBJECT = (
    r"\bapparel\b", r"\bshirt\b", r"\bt-?shirt\b", r"\boverall\b",
    r"work[-_ ]?suit\b", r"\bsafety\b", r"\bhoodie\b", r"\bgarment\b",
    r"\bclothing\b", r"\btub\b", r"\bsink\b", r"\bmechanic\b",
)


def _inf(value, source, evidence, conf) -> dict:
    return Inferred(value=value, source=source, evidence=evidence,
                    confidence=conf,
                    parser=f"{C.TOOL_NAME}.classify/{C.TOOL_VERSION}").to_dict()


def classify(record: dict) -> dict:
    """Assign a provisional category with evidence. First match wins."""
    rel = record["relative_path"]
    low = rel.lower()
    fn = record["filename"]
    ext = record["extension"]
    sig = (record.get("signature_kind") or {}).get("value")

    # 1. licence/readme material — evidence, not an asset
    strength = license_evidence_strength(fn, ext)
    if strength:
        return _inf("LICENSE_EVIDENCE", "filename_rule",
                    [f"filename={fn}", f"ext={ext}", f"strength={strength}"],
                    0.9 if strength == "strong" else 0.55)

    # 2. archives — understood, but contents unclassified (never UNKNOWN)
    if ext in C.ARCHIVE_EXT:
        return _inf("ARCHIVE", "extension_rule",
                    [f"ext={ext}", f"signature={sig}"], 0.95)

    # 3. deliberately excluded material
    if ext in _OUT_OF_SCOPE_EXT:
        return _inf("OUT_OF_SCOPE", "extension_rule",
                    [f"ext={ext}", "non-design format"], 0.85)
    for pat in _OUT_OF_SCOPE_PATH:
        if re.search(pat, low):
            return _inf("OUT_OF_SCOPE", "path_rule",
                        [f"path matches /{pat}/"], 0.75)
    if _MOCKUP_RE.search(low):
        for pat in _UNRELATED_MOCKUP_SUBJECT:
            if re.search(pat, low):
                return _inf("OUT_OF_SCOPE", "path_rule",
                            [f"mockup of unrelated subject /{pat}/"], 0.7)

    # 4. fonts — the quarantine branch first, so its evidence is explicit
    if ext in C.FONT_EXT:
        if rel.startswith(C.FONT_QUARANTINE_DIR + "/"):
            return _inf("FONT", "path_rule",
                        [f"under {C.FONT_QUARANTINE_DIR}",
                         "suspected system-font dump"], 0.9)
        return _inf("FONT", "extension_rule", [f"ext={ext}"], 0.95)

    # 4b. colour systems — extension-driven, so a swatch inside a
    # "*-background" folder is never stolen by a folder hint.
    if ext in C.PALETTE_EXT:
        return _inf("COLOR_PALETTE", "extension_rule",
                    [f"ext={ext}", "colour-system file",
                     "filename alone never confirms an official BBROSE palette"],
                    0.85)

    # 4c. management/provenance sidecars — inventoried, never assets.
    if ext in C.METADATA_EXT:
        return _inf("SUPPORTING_METADATA", "extension_rule",
                    [f"ext={ext}", "management/provenance sidecar"], 0.8)

    # 5. brand / third-party marks — filename evidence only
    if fn in THIRD_PARTY_LOGOS:
        return _inf("LOGO", "filename_rule",
                    [f"filename={fn}", "third-party mark"], 0.8)
    if fn in BRAND_CANDIDATE_NAMES or BBROSE_RE.search(fn):
        if ext not in MASTER_EXT:
            return _inf("PRODUCT_REFERENCE", "filename_rule",
                        [f"filename={fn}", f"raster ext={ext}",
                         "brand-named render, not a vector master"], 0.5)
        cat = "LOGO" if re.search(r"logo", fn, re.I) else "BRAND_MASTER"
        return _inf(cat, "filename_rule",
                    [f"filename={fn}", f"master ext={ext}"], 0.6)

    # 6. historical production designs (the one high-confidence branch)
    if rel.startswith(C.HISTORICAL_DIR + "/") and ext == ".ai":
        return _inf("HISTORICAL_DESIGN", "path_rule",
                    [f"under {C.HISTORICAL_DIR}", "ext=.ai"], 0.95)

    # 7. folder-name hints (hints, not truth → capped confidence)
    for cat, pats in _HINTS:
        for p in pats:
            if re.search(p, low):
                return _inf(cat, "folder_hint", [f"path matches /{p}/"], 0.55)

    # 8. structural fallbacks by media type
    if ext in C.VECTOR_EXT:
        return _inf("REUSABLE_VECTOR_ASSET", "extension_fallback",
                    [f"vector ext={ext}"], 0.4)
    if ext in C.RASTER_EXT:
        return _inf("RASTER_DESIGN_ASSET", "extension_fallback",
                    [f"raster ext={ext}"], 0.4)

    # 9. genuinely unclassifiable
    return _inf("UNKNOWN", "no_rule_matched", [f"ext={ext or '(none)'}"], 0.0)


# --- quarantine / review posture -------------------------------------------

def font_posture(record: dict) -> dict:
    """User-mandated posture for every font; stricter inside Fonts/3333."""
    rel = record["relative_path"]
    quarantined = rel.startswith(C.FONT_QUARANTINE_DIR + "/")
    return {
        "license_status": "UNVERIFIED",
        "source_classification": ("SUSPECTED_SYSTEM_FONT_DUMP" if quarantined
                                  else "DOWNLOAD_FOLDER"),
        "review_required": True,
        "automatic_use_allowed": False,
        "embedding_allowed": False,
        "redistribution_allowed": False,
        "quarantined": quarantined,
    }


def category_subtype(record: dict) -> tuple[str | None, str | None]:
    """(subtype, associated_branch) for categories that carry one."""
    rel = record["relative_path"]
    cat = record["category"]["value"]
    if cat == "SUPPORTING_METADATA":
        if rel.startswith(C.FONTS_DIR + "/"):
            return "FONT_METADATA", C.FONTS_DIR
        return "GENERAL_METADATA", None
    if cat == "COLOR_PALETTE":
        return "SWATCH_FILE", None
    return None, None


def needs_review(record: dict) -> tuple[bool, list[str]]:
    reasons = []
    cat = record["category"]["value"]
    conf = record["category"]["confidence"]
    if record["extension"] in C.FONT_EXT:
        reasons.append("font_license_unverified")
    if cat == "COLOR_PALETTE":
        # Never auto-used before it is parsed and a human approves it, and the
        # filename alone never proves it is an official BBROSE palette.
        reasons.append("palette_unparsed_and_ownership_unconfirmed")
    if cat == "ARCHIVE":
        reasons.append("archive_contents_unverified")
    if cat in ("UNKNOWN",):
        reasons.append("unclassified")
    if cat in ("BRAND_MASTER", "LOGO"):
        reasons.append("ownership_unconfirmed")
    if cat == "OUT_OF_SCOPE":
        reasons.append("confirm_exclusion")
    if conf < 0.6 and cat not in ("UNKNOWN",):
        reasons.append("low_confidence_classification")
    if record["warnings"]:
        reasons.append("has_warnings")
    if record["parser_support"]["status"] in ("unsupported", "partial"):
        reasons.append(f"parser_{record['parser_support']['status']}")
    return bool(reasons), reasons


def annotate(records: list[dict]) -> list[dict]:
    """Attach category, ownership, licence evidence, posture, review flags."""
    index = build_license_index(records)
    for r in records:
        r["category"] = classify(r)
        r["ownership_status"] = ownership(r)
        attach_license_evidence(r, index)
        subtype, branch = category_subtype(r)
        if subtype:
            r["category_subtype"] = subtype
        if branch:
            r["associated_branch"] = branch
        # Knowledge-class / retrieval posture for EVERY record: ARCHIVE,
        # LICENSE_EVIDENCE, SUPPORTING_METADATA, OUT_OF_SCOPE and UNKNOWN are
        # excluded from retrieval and generation by rule.
        r["posture"] = C.retrieval_posture(r["category"]["value"])
        if r["extension"] in C.FONT_EXT:
            r["font_posture"] = font_posture(r)
            r["license_status"]["value"] = "UNVERIFIED"   # fonts never PENDING-clear
        if r["category"]["value"] == "LOGO" and \
                r["ownership_status"]["value"] == "UNCONFIRMED_THIRD_PARTY":
            r["excluded_from_brand_retrieval"] = True
        r["review_required"], r["review_reasons"] = needs_review(r)
        r["human_confirmed"] = human_block()
    return records
