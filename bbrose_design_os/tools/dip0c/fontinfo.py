"""Per-FACE font audit (DIP-0C4a).

**A font file is not a font.** The 38 `.ttc` collections in `materials/` carry two or
three faces each, and each face has its own name table, its own family, its own weight
— and may belong to a different family group than its neighbours in the same file. So
the unit of everything here is the **face**, never the file. Counts are reported as
"N files / M faces" and mean it.

Two things fail closed rather than quietly disappearing:

* **`.fon`** — 38 legacy Windows bitmap fonts. fontTools raises `TTLibError: bad
  sfntVersion`; there is no sfnt to read. They become `UNSUPPORTED_FORMAT` /
  `REQUIRES_HUMAN` and stay in the corpus as unresolved, because a file we cannot read
  is a fact about our tooling, not a reason to pretend the file is not there.
* **anything corrupt** — `PARSE_FAILED`, with the error recorded verbatim.

`fsType` is read and recorded. It is **technical metadata about embedding, not a
licence and not permission** — the OpenType spec says so and so does every prior slice
of this project. Nothing here grants anything.
"""
from __future__ import annotations

import hashlib
import warnings

from tools.dip0.fonts import _safe_str

from . import config as C

# --- script ranges -------------------------------------------------------------
# DIP-0A's ranges cover the BMP only, and that is not enough here. `mingliub.ttc`
# carries 42,711 codepoints in CJK Extension B (U+20000–U+2A6DF, a SUPPLEMENTARY
# plane) and exactly ZERO in the BMP CJK block — so under BMP-only ranges it reports
# as "latin", on the strength of 165 Latin glyphs. A CJK font announcing itself as
# Latin is not a rounding error; it is the wrong answer.
#
# Presence is also not coverage. A font with 8 Greek glyphs and 40,000 CJK ones
# "supports" both only in the most useless sense, so every script carries its COUNT
# and the dominant script is reported explicitly.
SCRIPT_RANGES = (
    ("latin", 0x0041, 0x024F),
    ("greek", 0x0370, 0x03FF),
    ("cyrillic", 0x0400, 0x04FF),
    ("hebrew", 0x0590, 0x05FF),
    ("arabic", 0x0600, 0x06FF),
    ("arabic_supplement", 0x0750, 0x077F),
    ("arabic_extended", 0x08A0, 0x08FF),
    ("arabic_presentation_a", 0xFB50, 0xFDFF),
    ("arabic_presentation_b", 0xFE70, 0xFEFF),
    ("devanagari", 0x0900, 0x097F),
    ("thai", 0x0E00, 0x0E7F),
    ("hangul", 0xAC00, 0xD7AF),
    ("kana", 0x3040, 0x30FF),
    ("cjk", 0x4E00, 0x9FFF),
    ("cjk_ext_a", 0x3400, 0x4DBF),
    ("cjk_compat", 0xF900, 0xFAFF),
    ("cjk_ext_b", 0x20000, 0x2A6DF),
    ("cjk_ext_c", 0x2A700, 0x2B73F),
    ("cjk_ext_d", 0x2B740, 0x2B81F),
    ("cjk_ext_e", 0x2B820, 0x2CEAF),
    ("cjk_compat_supp", 0x2F800, 0x2FA1F),
    ("emoji", 0x1F300, 0x1FAFF),
    ("numerals", 0x0030, 0x0039),
)
MIN_SCRIPT_HITS = 8            # a handful in range is coverage, not an accident

PARSER = f"{C.TOOL_NAME}.fontinfo/{C.TOOL_VERSION}"
SCHEMA_VERSION = "fontface/1.0"

try:
    import fontTools
    from fontTools.ttLib import TTCollection, TTFont
    FONTTOOLS_VERSION = fontTools.version
except ImportError:                                   # pragma: no cover
    TTFont = TTCollection = None
    FONTTOOLS_VERSION = None

# --- parse status --------------------------------------------------------------
PARSED = "PARSED"
PARTIAL = "PARTIAL_PARSE"
UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
PARSE_FAILED = "PARSE_FAILED"
STATUSES = (PARSED, PARTIAL, UNSUPPORTED_FORMAT, PARSE_FAILED)

CAP_DIRECT = "DIRECT"
CAP_REQUIRES_HUMAN = "REQUIRES_HUMAN"

# fontTools cannot read these at all. Not a failure to try — a format it does not do.
UNSUPPORTED_EXTS = (".fon", ".pfb", ".pfm", ".suit", ".dfont", ".eot")
COLLECTION_EXTS = (".ttc", ".otc")

# --- the name IDs the business asked for ---------------------------------------
NAME_IDS = {
    0: "copyright",
    1: "family_legacy",            # name ID 1
    2: "subfamily_legacy",         # name ID 2
    4: "full_name",                # name ID 4
    6: "postscript_name",          # name ID 6
    7: "trademark",
    8: "manufacturer",
    9: "designer",
    13: "license_description",
    14: "license_url",
    16: "family_typographic",      # name ID 16 — the PREFERRED grouping key
    17: "subfamily_typographic",   # name ID 17
}

# OS/2 fsType bits. RECORDED, never obeyed as permission.
FSTYPE_BITS = {
    0: "INSTALLABLE_EMBEDDING",
    1: "RESTRICTED_LICENSE_EMBEDDING",
    2: "PREVIEW_AND_PRINT_EMBEDDING",
    3: "EDITABLE_EMBEDDING",
    8: "NO_SUBSETTING",
    9: "BITMAP_EMBEDDING_ONLY",
}

WIDTH_CLASS = {
    1: "ULTRA_CONDENSED", 2: "EXTRA_CONDENSED", 3: "CONDENSED",
    4: "SEMI_CONDENSED", 5: "NORMAL", 6: "SEMI_EXPANDED",
    7: "EXPANDED", 8: "EXTRA_EXPANDED", 9: "ULTRA_EXPANDED",
}


class FontError(RuntimeError):
    """The audit refuses to guess."""


def face_id(sha256: str, index: int, postscript: str | None) -> str:
    """A stable identity for ONE face.

    Derived from the file's content hash + its index inside the collection + the
    PostScript name where present. Content-derived, so it survives a move and is
    identical for two copies of the same file — which is exactly what the ~941
    duplicate groups need.
    """
    key = f"{sha256}:{index}:{postscript or ''}"
    return "face-" + hashlib.sha256(key.encode()).hexdigest()[:20]


def _fstype(os2, warnings_: list) -> dict:
    raw = getattr(os2, "fsType", None) if os2 else None
    if raw is None:
        return {"raw": None, "flags": [], "is_permission": False,
                "note": "no OS/2 fsType present"}
    flags = [name for bit, name in FSTYPE_BITS.items() if raw & (1 << bit)]
    if raw == 0:
        flags = ["INSTALLABLE_EMBEDDING"]
    return {
        "raw": int(raw),
        "flags": flags,
        "is_permission": False,
        "note": "fsType is TECHNICAL METADATA about embedding. It is NOT a licence, "
                "NOT a grant, and NOT evidence of commercial rights. A font whose "
                "fsType says INSTALLABLE may still be one BBROSE has no right to use.",
    }


def _axes(font) -> list[dict]:
    fvar = font.get("fvar")
    if not fvar:
        return []
    return sorted(
        [{"tag": _safe_str(a.axisTag), "min": a.minValue,
          "default": a.defaultValue, "max": a.maxValue}
         for a in fvar.axes],
        key=lambda a: a["tag"] or "")


def _scripts_and_cmap(font, warnings_: list) -> dict:
    try:
        chars = set(font.getBestCmap().keys())
    except Exception as e:                             # noqa: BLE001
        warnings_.append(f"cmap_unreadable: {type(e).__name__}")
        return {"scripts": [], "script_coverage": {}, "dominant_script": None,
                "cmap_codepoints": 0, "unicode_blocks": []}

    coverage = {}
    for name, lo, hi in SCRIPT_RANGES:
        hits = sum(1 for c in chars if lo <= c <= hi)
        if hits >= MIN_SCRIPT_HITS:
            coverage[name] = hits

    # The DOMINANT script, by codepoint count — not by whichever range happened to be
    # checked first. CJK families are the whole reason this exists.
    dominant = max(coverage, key=lambda k: coverage[k]) if coverage else None
    if dominant == "numerals" and len(coverage) > 1:
        coverage_wo = {k: v for k, v in coverage.items() if k != "numerals"}
        dominant = max(coverage_wo, key=lambda k: coverage_wo[k])

    return {
        "scripts": sorted(coverage),
        "script_coverage": dict(sorted(coverage.items(), key=lambda kv: -kv[1])),
        "dominant_script": dominant,
        "cmap_codepoints": len(chars),
        # a coarse fingerprint, for comparing glyph compatibility WITHIN a family
        "unicode_blocks": sorted({f"U+{(c >> 8) << 8:05X}" for c in chars}),
    }


def read_face(font, *, sha256: str, index: int, path: str, ext: str) -> dict:
    """Audit ONE face of an open font."""
    warns: list[str] = []
    names: dict[str, str | None] = {}
    try:
        nt = font["name"]
        for nid, field in NAME_IDS.items():
            try:
                names[field] = _safe_str(nt.getDebugName(nid))
            except Exception:                          # noqa: BLE001
                names[field] = None
                warns.append(f"name_id_{nid}_unreadable")
    except KeyError:
        warns.append("no_name_table")
        names = {f: None for f in NAME_IDS.values()}

    os2 = font.get("OS/2")
    head = font.get("head")
    cov = _scripts_and_cmap(font, warns)
    axes = _axes(font)

    try:
        glyphs = font["maxp"].numGlyphs
    except Exception:                                  # noqa: BLE001
        glyphs = None
        warns.append("maxp_unreadable")

    mac = getattr(head, "macStyle", 0) if head else 0
    rec = {
        "schema_version": SCHEMA_VERSION,
        "face_id": face_id(sha256, index, names.get("postscript_name")),
        "source_path": path,
        "source_sha256": sha256,
        "collection_index": index,
        "extension": ext,
        "names": names,
        "vendor_id": _safe_str(getattr(os2, "achVendID", None)) if os2 else None,
        "version": _safe_str(names.get("version")) or _version(font, warns),
        "weight_class": int(getattr(os2, "usWeightClass", 0)) if os2 else None,
        "width_class": WIDTH_CLASS.get(
            int(getattr(os2, "usWidthClass", 0)) if os2 else 0),
        "italic": bool(mac & 0b10) or bool(
            getattr(os2, "fsSelection", 0) & 0b1) if os2 else bool(mac & 0b10),
        "bold": bool(mac & 0b1),
        "is_variable": bool(axes),
        "variable_axes": axes,
        "scripts": cov["scripts"],
        "script_coverage": cov["script_coverage"],
        "dominant_script": cov["dominant_script"],
        "cmap_codepoints": cov["cmap_codepoints"],
        "unicode_blocks": cov["unicode_blocks"],
        "glyph_count": glyphs,
        "tables": sorted(font.keys()),
        "fstype": _fstype(os2, warns),
        "warnings": sorted(set(warns)),
        "parse_status": PARTIAL if warns else PARSED,
        "capability": CAP_REQUIRES_HUMAN if warns else CAP_DIRECT,
        "parser": PARSER,
        "fonttools_version": FONTTOOLS_VERSION,
    }
    return rec


def _version(font, warns: list) -> str | None:
    try:
        return f"{font['head'].fontRevision:.3f}"
    except Exception:                                  # noqa: BLE001
        return None


def audit_file(path, *, sha256: str = None) -> dict:
    """Audit ONE file → possibly MANY faces. Never raises on a bad font."""
    p = C.Path(path)
    ext = p.suffix.lower()
    rel = C.relpath(p)
    data_hash = sha256 or _sha256(p)

    base = {
        "schema_version": "fontfile/1.0",
        "source_path": rel,
        "source_sha256": data_hash,
        "extension": ext,
        "size_bytes": p.stat().st_size,
        "faces": [],
        "face_count": 0,
        "is_collection": ext in COLLECTION_EXTS,
        "parse_status": PARSE_FAILED,
        "capability": CAP_REQUIRES_HUMAN,
        "error": None,
        "parser": PARSER,
    }

    if ext in UNSUPPORTED_EXTS:
        base.update(
            parse_status=UNSUPPORTED_FORMAT,
            error=f"{ext} is not an sfnt format — fontTools cannot read it, and this "
                  "audit will not guess at its contents. The file is still here and "
                  "still needs a human.")
        return base

    if TTFont is None:                                 # pragma: no cover
        base["error"] = "fontTools unavailable"
        return base

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if ext in COLLECTION_EXTS:
                coll = TTCollection(str(p), lazy=True)
                faces = [read_face(f, sha256=data_hash, index=i, path=rel, ext=ext)
                         for i, f in enumerate(coll.fonts)]
                coll.close()
            else:
                f = TTFont(str(p), lazy=True, fontNumber=0)
                faces = [read_face(f, sha256=data_hash, index=0, path=rel, ext=ext)]
                f.close()
    except Exception as e:                             # noqa: BLE001
        base["error"] = f"{type(e).__name__}: {e}"
        return base

    base["faces"] = faces
    base["face_count"] = len(faces)
    base["parse_status"] = (PARTIAL if any(x["parse_status"] == PARTIAL
                                           for x in faces) else PARSED)
    base["capability"] = (CAP_REQUIRES_HUMAN
                          if base["parse_status"] != PARSED else CAP_DIRECT)
    return base


def _sha256(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
