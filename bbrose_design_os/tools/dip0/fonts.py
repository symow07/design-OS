"""Slice 2 — inventory-level font inspection (fontTools, lazy).

Metadata only. Fonts are NOT installed, embedded, exposed or recommended.
`fsType` embedding bits and any bundled license text are recorded as EVIDENCE;
possession of a file never implies a right to embed, redistribute or use it —
`license_status` stays UNVERIFIED until a human confirms it (slice 3).
"""
from __future__ import annotations

from pathlib import Path

from . import config as C

try:
    import fontTools
    from fontTools.ttLib import TTCollection, TTFont
    FONTTOOLS_VERSION = fontTools.version
except ImportError:                                   # pragma: no cover
    TTFont = TTCollection = None
    FONTTOOLS_VERSION = None

PARSER = f"fontTools/{FONTTOOLS_VERSION}" if FONTTOOLS_VERSION else None

# nameID → field
_NAME_IDS = {
    1: "family", 2: "subfamily", 4: "full_name", 5: "version",
    6: "postscript_name", 13: "license_description", 14: "license_url",
    16: "typographic_family", 17: "typographic_subfamily",
}

# fsType is a PERMISSION HINT from the foundry, not a licence grant.
_FSTYPE = {
    0: "installable_embedding",
    2: "restricted_license_embedding",
    4: "preview_and_print_embedding",
    8: "editable_embedding",
}

_SCRIPT_RANGES = (
    ("latin", 0x0041, 0x024F), ("greek", 0x0370, 0x03FF),
    ("cyrillic", 0x0400, 0x04FF), ("hebrew", 0x0590, 0x05FF),
    ("arabic", 0x0600, 0x06FF), ("devanagari", 0x0900, 0x097F),
    ("thai", 0x0E00, 0x0E7F), ("hangul", 0xAC00, 0xD7AF),
    ("cjk", 0x4E00, 0x9FFF), ("kana", 0x3040, 0x30FF),
)


def _safe_str(v) -> str | None:
    """Malformed fonts hand back raw bytes where the spec promises a string
    (e.g. OS/2.achVendID). Preserve the value instead of dropping it."""
    if v is None:
        return None
    if isinstance(v, bytes):
        return v.decode("latin-1", "replace").strip("\x00").strip() or None
    return str(v).strip() or None


def _scripts(cmap_chars: set[int]) -> list[str]:
    found = []
    for name, lo, hi in _SCRIPT_RANGES:
        # a handful of codepoints in range = real coverage, not an accident
        hits = sum(1 for c in cmap_chars if lo <= c <= hi)
        if hits >= 8:
            found.append(name)
    return found


def _from_ttfont(font, warnings: list[str]) -> dict:
    d: dict = {}
    try:
        name = font["name"]
        for nid, field in _NAME_IDS.items():
            try:
                v = name.getDebugName(nid)
            except Exception:                          # noqa: BLE001
                v = None
            v = _safe_str(v)
            if v:
                d[field] = v
    except (KeyError, AttributeError) as e:
        warnings.append(f"font_name_table: {e}")

    try:
        os2 = font["OS/2"]
        d["weight_class"] = getattr(os2, "usWeightClass", None)
        d["width_class"] = getattr(os2, "usWidthClass", None)
        d["vendor_id"] = _safe_str(getattr(os2, "achVendID", None))
        fs = int(getattr(os2, "fsType", 0))
        d["fs_type_raw"] = fs
        d["fs_type_meaning"] = _FSTYPE.get(fs & 0xF, f"reserved({fs & 0xF})")
        d["no_subsetting"] = bool(fs & 0x100)
        d["bitmap_embed_only"] = bool(fs & 0x200)
        d["italic"] = bool(getattr(os2, "fsSelection", 0) & 0x1)
    except (KeyError, AttributeError, ValueError) as e:
        warnings.append(f"font_os2: {e}")

    try:
        d["italic"] = d.get("italic") or bool(font["head"].macStyle & 0x2)
        d["units_per_em"] = font["head"].unitsPerEm
    except (KeyError, AttributeError) as e:
        warnings.append(f"font_head: {e}")

    try:
        if "fvar" in font:
            d["variable"] = True
            d["variable_axes"] = [
                {"tag": a.axisTag, "min": a.minValue,
                 "default": a.defaultValue, "max": a.maxValue}
                for a in font["fvar"].axes
            ]
        else:
            d["variable"] = False
            d["variable_axes"] = []
    except Exception as e:                             # noqa: BLE001
        warnings.append(f"font_fvar: {e}")

    try:
        chars = set(font.getBestCmap().keys())
        d["glyph_count"] = len(font.getGlyphOrder())
        d["scripts"] = _scripts(chars)
    except Exception as e:                             # noqa: BLE001
        warnings.append(f"font_cmap: {e}")
        d["scripts"] = []
    return d


def inspect_font(path: Path, ext: str) -> dict:
    """Inventory-level metadata. Never raises: failures land in `warnings`."""
    warnings: list[str] = []
    result: dict = {"parsed": False, "parser": PARSER, "faces": [],
                    "warnings": warnings}

    if ext == ".fon":
        warnings.append("font_unsupported_format: legacy Windows .fon")
        return result
    if TTFont is None:
        warnings.append("fontTools_unavailable")
        return result

    try:
        if ext == ".ttc":
            with TTCollection(str(path), lazy=True) as coll:
                for f in coll.fonts:
                    result["faces"].append(_from_ttfont(f, warnings))
        else:
            with TTFont(str(path), lazy=True, fontNumber=0) as f:
                result["faces"].append(_from_ttfont(f, warnings))
    except Exception as e:                             # noqa: BLE001 — never fatal
        warnings.append(f"font_parse_failed: {type(e).__name__}: {e}")
        return result

    # `lazy=True` defers table loading, so a malformed file constructs cleanly
    # and only fails when tables are touched (those failures land in warnings).
    # "Parsed" therefore means a usable IDENTITY was recovered — not merely that
    # the constructor returned.
    usable = [f for f in result["faces"]
              if f.get("family") or f.get("postscript_name") or f.get("full_name")]
    result["parsed"] = bool(usable)
    if result["faces"] and not usable:
        warnings.append("font_parse_failed: no readable name table (no identity)")
    return result


def build_font_report(records: list[dict], root: Path | None = None) -> dict:
    """Inspect every font record and summarise the quarantine posture."""
    root = Path(root or C.REPO_ROOT)
    fonts = [r for r in records if r["extension"] in C.FONT_EXT]

    families: dict[str, list[str]] = {}
    parsed = failed = 0
    for r in fonts:
        info = inspect_font(root / r["relative_path"], r["extension"])
        r["font"] = {k: v for k, v in info.items() if k != "warnings"}
        r["warnings"].extend(info["warnings"])
        if info["parsed"]:
            parsed += 1
            r["parser_support"] = {"status": "supported", "parser": PARSER}
            for face in info["faces"]:
                fam = face.get("typographic_family") or face.get("family")
                if fam:
                    families.setdefault(fam, []).append(r["relative_path"])
        else:
            failed += 1
            if r["extension"] == ".fon":
                r["parser_support"] = {"status": "unsupported", "parser": None}

    quarantined = [r["relative_path"] for r in fonts
                   if r["relative_path"].startswith(C.FONT_QUARANTINE_DIR + "/")]
    multi = {f: sorted(set(p)) for f, p in families.items() if len(set(p)) > 1}
    return {
        "font_file_count": len(fonts),
        "parsed": parsed,
        "parse_failed": failed,
        "distinct_families": len(families),
        "families_with_multiple_files": len(multi),
        "duplicate_family_map": dict(sorted(multi.items())[:200]),
        "quarantined_count": len(quarantined),
        "quarantine_branch": C.FONT_QUARANTINE_DIR,
        "policy": ("All fonts start license_status=UNVERIFIED. Bundled licence "
                   "text and fsType bits are recorded as EVIDENCE only and never "
                   "grant embedding, redistribution or commercial-output rights. "
                   "No font is installed, embedded or auto-used by DIP-0A."),
    }
