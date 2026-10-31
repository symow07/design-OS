"""Source packages, duplicated dumps, and licence-evidence association (DIP-0C4b).

## Proximity is not relevance

DIP-0A rated a licence file "strong" evidence when it sat in the same directory as a
font. On this corpus that is sometimes wrong in a way that matters:
`DOWNLOADS 12-2025/animal-bookmarks/License free.txt` opens

> *"This license only applies if you downloaded this **vector** as an unsubscribed
> user…"*

It is a **stock-vector licence**. It says nothing about the font sitting beside it. A
same-directory association is a fact about the *filesystem*; whether the document
governs the *font* is a fact about the *text*, and only reading the text can tell them
apart. So every association records **what the text actually is**, and an evidence file
that never mentions fonts has its confidence cut and is flagged
`EVIDENCE_MAY_NOT_COVER_FONTS`.

## The dump is not two packages

`materials/Fonts` is 92% byte-identical to `materials/Fonts/3333`. They are one dump,
twice. Treating them as two rights batches would let one folder's evidence "clear" the
other — so they are recorded as **one suspected duplicated dump**, both paths
preserved, and **neither clears the other**.
"""
from __future__ import annotations

import re
from collections import defaultdict

from . import config as C

PARSER = f"{C.TOOL_NAME}.font_packages/{C.TOOL_VERSION}"
SCHEMA_VERSION = "font_package/1.0"

# --- package kinds -------------------------------------------------------------
PKG_DOWNLOAD_PACKAGE = "DOWNLOAD_PACKAGE"          # a credible boundary
PKG_SUSPECTED_DUMP = "SUSPECTED_DUPLICATED_DUMP"   # not a rights batch
PKG_UNCLASSIFIED = "UNCLASSIFIED_LOCATION"
PKG_KINDS = (PKG_DOWNLOAD_PACKAGE, PKG_SUSPECTED_DUMP, PKG_UNCLASSIFIED)

# The two directories that are one dump.
DUMP_ROOTS = ("materials/Fonts", "materials/Fonts/3333")

# --- licence text classification ------------------------------------------------
LIC_OFL = "SIL_OPEN_FONT_LICENSE"
LIC_APACHE = "APACHE_LICENSE"
LIC_MIT = "MIT_LICENSE"
LIC_EULA = "EULA"
LIC_PERSONAL_USE = "PERSONAL_USE_ONLY"
LIC_DEMO = "DEMO_OR_TRIAL"
LIC_STOCK_ASSET = "STOCK_ASSET_LICENSE_NOT_FONT"
LIC_README = "README_OR_NOTES"
LIC_URL_ONLY = "VENDOR_URL_ONLY"
LIC_UNREADABLE = "UNREADABLE"
LIC_UNKNOWN = "UNKNOWN_LICENSE_TEXT"

TEXT_PATTERNS = (
    (LIC_OFL, re.compile(r"sil open font license|\bOFL\b", re.I)),
    (LIC_APACHE, re.compile(r"apache license", re.I)),
    (LIC_MIT, re.compile(r"\bMIT License\b", re.I)),
    (LIC_PERSONAL_USE, re.compile(r"personal use only|non[- ]commercial|"
                                  r"not for commercial", re.I)),
    (LIC_DEMO, re.compile(r"\bdemo\b|\btrial\b|free version", re.I)),
    (LIC_EULA, re.compile(r"end user license|\bEULA\b|license agreement", re.I)),
    (LIC_README, re.compile(r"read ?me|installation", re.I)),
)

# Does the document actually talk about FONTS at all?
FONT_MENTION = re.compile(r"\bfont|\btypeface|\bglyph|\bopentype|\btruetype", re.I)
# ...or is it a stock-asset licence that happens to sit next to one?
STOCK_MENTION = re.compile(r"\bvector\b|\bimage\b|\bphoto\b|\bfreepik\b|"
                           r"\bsubscribed user\b|\bpremium user\b", re.I)

# --- association methods --------------------------------------------------------
ASSOC_SAME_DIR = "SAME_DIRECTORY"
ASSOC_PACKAGE_ROOT = "PACKAGE_ROOT"
ASSOC_PARENT = "PARENT_DIRECTORY"
ASSOC_NONE = "NO_EVIDENCE_FOUND"

# --- association warnings -------------------------------------------------------
W_MAY_NOT_COVER_FONTS = "EVIDENCE_MAY_NOT_COVER_FONTS"
W_RESTRICTIVE = "RESTRICTIVE_TERMS_DETECTED"
W_UNREADABLE = "EVIDENCE_TEXT_UNREADABLE"

# Confidence in the ASSOCIATION — never in the permission.
CONF_SAME_DIR = 0.7
CONF_PACKAGE_ROOT = 0.5
CONF_PARENT = 0.3
CONF_PENALTY_NOT_FONT = 0.4        # subtracted when the text never mentions fonts


def classify_text(path: str, text: str | None) -> dict:
    """What IS this document? Read it — do not assume from its filename."""
    if text is None:
        return {"license_type": LIC_UNREADABLE, "mentions_fonts": False,
                "mentions_stock_assets": False, "restrictions": [],
                "warnings": [W_UNREADABLE], "excerpt": None}

    kinds = [k for k, rx in TEXT_PATTERNS if rx.search(text)]
    mentions_fonts = bool(FONT_MENTION.search(text))
    mentions_stock = bool(STOCK_MENTION.search(text))

    # A licence that talks about vectors and never mentions a font is a STOCK licence
    # that happens to sit in the same folder. That is a filesystem fact, not a legal one.
    if mentions_stock and not mentions_fonts:
        kind = LIC_STOCK_ASSET
    elif kinds:
        kind = kinds[0]
    elif path.lower().endswith(".url"):
        kind = LIC_URL_ONLY
    else:
        kind = LIC_UNKNOWN

    restrictions = []
    if LIC_PERSONAL_USE in kinds:
        restrictions.append("PERSONAL_USE_ONLY — commercial use appears excluded")
    if LIC_DEMO in kinds:
        restrictions.append("DEMO_OR_TRIAL — a full licence may be required")

    warnings = []
    if not mentions_fonts:
        warnings.append(W_MAY_NOT_COVER_FONTS)
    if restrictions:
        warnings.append(W_RESTRICTIVE)

    return {
        "license_type": kind,
        "all_matches": kinds,
        "mentions_fonts": mentions_fonts,
        "mentions_stock_assets": mentions_stock,
        "restrictions": restrictions,
        "warnings": warnings,
        "excerpt": (text[:200].replace("\n", " ").strip() or None),
    }


def read_evidence(path: str) -> str | None:
    p = C.SOURCE_ROOT.parent / path
    try:
        return p.read_text(errors="replace")[:20000]
    except (OSError, UnicodeDecodeError):
        return None


def associate(font_file: dict, evidence_rows: list[dict]) -> list[dict]:
    """Associate licence evidence with ONE font file — conservatively, and with the
    text actually read.

    `evidence_rows` is what DIP-0A already found (path, strength, scope, distance);
    C4b re-reads the document and records what it turns out to be.
    """
    out = []
    for ev in evidence_rows or []:
        scope = ev.get("scope")
        method = {"same_dir": ASSOC_SAME_DIR,
                  "package_root": ASSOC_PACKAGE_ROOT,
                  "parent": ASSOC_PARENT}.get(scope, ASSOC_PARENT)
        base = {ASSOC_SAME_DIR: CONF_SAME_DIR,
                ASSOC_PACKAGE_ROOT: CONF_PACKAGE_ROOT,
                ASSOC_PARENT: CONF_PARENT}[method]

        cls = classify_text(ev["path"], read_evidence(ev["path"]))
        conf = base
        if not cls["mentions_fonts"]:
            conf = max(0.0, conf - CONF_PENALTY_NOT_FONT)

        out.append({
            "evidence_file": ev["path"],
            "evidence_filename": ev.get("filename"),
            "association_method": method,
            "association_distance": ev.get("distance"),
            "dip0a_strength": ev.get("strength"),
            "association_confidence": round(conf, 3),
            "license_type": cls["license_type"],
            "mentions_fonts": cls["mentions_fonts"],
            "mentions_stock_assets": cls["mentions_stock_assets"],
            "restrictions_detected": cls["restrictions"],
            "text_extraction_status": ("READ" if cls["license_type"] != LIC_UNREADABLE
                                       else "UNREADABLE"),
            "warnings": cls["warnings"],
            "excerpt": cls["excerpt"],
            "expiry": None,
            "review_status": "NOT_REVIEWED",       # human only
            "grants_permission": False,
            "note": "EVIDENCE ONLY. The presence of an OFL, EULA, readme or vendor URL "
                    "does NOT set LICENSE_APPROVED, does not approve commercial use, "
                    "embedding or redistribution, and never will without a human.",
            "parser": PARSER,
        })
    return sorted(out, key=lambda e: e["evidence_file"])


def package_of(path: str) -> str:
    # Day 6 migration: a font now lives under materials/fonts/<family>/, but the package it CAME IN is its
    # original folder, which the migration manifest keeps as the file's identity (D-D6-4: rights provenance).
    from tools.dip0.config import APP_ROOT
    import sys
    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))
    from apps.ire.materials_paths import migration_row
    row = migration_row(path)
    origin = row["old_path"] if row else path
    return str(C.Path(origin).parent)


def classify_package(pkg: str) -> str:
    if pkg in DUMP_ROOTS:
        return PKG_SUSPECTED_DUMP
    if pkg.startswith("materials/DOWNLOADE 2026"):
        return PKG_DOWNLOAD_PACKAGE
    return PKG_UNCLASSIFIED


def build_packages(files: list[dict], faces_by_hash: dict,
                   evidence_by_path: dict) -> list[dict]:
    """Group files into source packages. The dump is ONE package, not two."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        pkg = package_of(f["relative_path"])
        kind = classify_package(pkg)
        key = "materials/Fonts[+3333]" if kind == PKG_SUSPECTED_DUMP else pkg
        buckets[key].append(f)

    out = []
    for key in sorted(buckets):
        members = buckets[key]
        kind = (PKG_SUSPECTED_DUMP if key == "materials/Fonts[+3333]"
                else classify_package(key))
        roots = sorted({package_of(m["relative_path"]) for m in members})

        faces = [fc for m in members
                 for fc in faces_by_hash.get(m["sha256"], [])]
        # dedupe faces by id (duplicate files share faces)
        seen, uniq = set(), []
        for fc in faces:
            if fc["face_id"] not in seen:
                seen.add(fc["face_id"])
                uniq.append(fc)

        ev = sorted({e["evidence_file"]
                     for m in members
                     for e in evidence_by_path.get(m["relative_path"], [])})
        ev_records = [e for m in members
                      for e in evidence_by_path.get(m["relative_path"], [])]
        by_file = {}
        for e in ev_records:
            by_file[e["evidence_file"]] = e

        out.append({
            "schema_version": SCHEMA_VERSION,
            "package_id": "pkg-" + C.Path(key).name.replace(" ", "_")[:40],
            "package_key": key,
            "package_name": C.Path(key).name,
            "package_kind": kind,
            "package_roots": roots,
            "file_count": len(members),
            "face_count": len(uniq),
            "families": sorted({fc.get("_family_key") for fc in uniq
                                if fc.get("_family_key")}),
            "formats": sorted({m["extension"] for m in members}),
            "license_evidence_files": ev,
            "license_evidence": sorted(by_file.values(),
                                       key=lambda e: e["evidence_file"]),
            "has_license_evidence": bool(ev),
            "restrictions_detected": sorted({r for e in by_file.values()
                                             for r in e["restrictions_detected"]}),
            "evidence_warnings": sorted({w for e in by_file.values()
                                         for w in e["warnings"]}),
            "is_credible_rights_batch": kind == PKG_DOWNLOAD_PACKAGE,
            "note": (
                "ONE dump, recorded twice on disk. materials/Fonts is 92% "
                "byte-identical to materials/Fonts/3333. Both paths are preserved, "
                "and NEITHER folder's evidence clears the other."
                if kind == PKG_SUSPECTED_DUMP else
                "a credible package boundary: a downloaded font package."
                if kind == PKG_DOWNLOAD_PACKAGE else
                "location only — not a credible rights batch"),
            "rights_review_status": "NOT_REVIEWED",      # human only
            "human_confirmation": None,
            "parser": PARSER,
        })
    return out


def dump_overlap(files: list[dict]) -> dict:
    """How much of `materials/Fonts` is literally the same bytes as `Fonts/3333`?"""
    a = {f["sha256"] for f in files
         if package_of(f["relative_path"]) == "materials/Fonts/3333"}
    b = {f["sha256"] for f in files
         if package_of(f["relative_path"]) == "materials/Fonts"}
    shared = a & b
    return {
        "fonts_3333_unique_hashes": len(a),
        "fonts_unique_hashes": len(b),
        "shared_hashes": len(shared),
        "overlap_pct_of_fonts": round(100 * len(shared) / max(1, len(b)), 1),
        "conclusion": "ONE suspected duplicated dump, not two rights batches",
        "neither_clears_the_other": True,
    }
