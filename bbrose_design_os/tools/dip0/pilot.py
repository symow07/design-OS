"""Slice 4 — pilot manifest selection.

Selects representative subsets by EXACT relative path, and proves the
user-mandated diversity requirements are met rather than asserting it in prose.
Deterministic: identical inventory ⇒ identical manifest.
"""
from __future__ import annotations

import re

MB = 1 << 20
EASY_MAX = 10 * MB
MEDIUM_MAX = 30 * MB
MIXED_RASTER_PROXY = 20 * MB      # oversized vector ⇒ probably embedded rasters

CJK_RE = re.compile(r"[㐀-鿿]")
STAND_RE = re.compile(r"stand|展盒|吸塑", re.I)
DIELINE_RE = re.compile(r"刀线|dieline|die[-_ ]?line", re.I)
POOR_NAME_RE = re.compile(r"^\(|\s{2,}|\.\.|^\d+\.|[（）]|\.{2,}")


def _difficulty(size: int) -> str:
    if size < EASY_MAX:
        return "easy"
    if size < MEDIUM_MAX:
        return "medium"
    return "hard"


def _cat(r) -> str:
    return r["category"]["value"]


def _pick(records, n, *, key=None, reverse=False):
    out = sorted(records, key=key or (lambda r: r["relative_path"]), reverse=reverse)
    return out[:n]


# Coverage requirements, highest priority first. Each contributes at most
# PER_REASON_CAP exemplars, so a library with 9 CJK-named files does not swamp
# a 10–15 file pilot.
REASON_PRIORITY = (
    "display_or_stand_design",
    "dieline_annotation",
    "chinese_annotations",
    "poor_filename_hygiene",
    "high_complexity_vector",
    "mixed_raster_vector_proxy_by_size",
    "legacy_postscript_ai",
)
PER_REASON_CAP = 2


def _reason_pools(hist: list[dict]) -> dict[str, list[dict]]:
    pools: dict[str, list[dict]] = {k: [] for k in REASON_PRIORITY}
    biggest = {r["relative_path"] for r in
               _pick(hist, 2, key=lambda r: r["size_bytes"], reverse=True)}
    for r in hist:
        fn = r["filename"]
        if STAND_RE.search(fn):
            pools["display_or_stand_design"].append(r)
        if DIELINE_RE.search(fn):
            pools["dieline_annotation"].append(r)
        if CJK_RE.search(fn):
            pools["chinese_annotations"].append(r)
        if POOR_NAME_RE.search(fn):
            pools["poor_filename_hygiene"].append(r)
        if r["relative_path"] in biggest:
            pools["high_complexity_vector"].append(r)
        if r["size_bytes"] >= MIXED_RASTER_PROXY:
            pools["mixed_raster_vector_proxy_by_size"].append(r)
        if (r.get("signature_kind") or {}).get("value") == "postscript":
            pools["legacy_postscript_ai"].append(r)
    return pools


def _spread(pool: list[dict], k: int) -> list[dict]:
    """Pick k exemplars spanning the size range (smallest + largest)."""
    s = sorted(pool, key=lambda r: (r["size_bytes"], r["relative_path"]))
    if k >= 2 and len(s) >= 2:
        return [s[0], s[-1]]
    return s[:k]


def select_historical(records: list[dict], target: int = 14) -> list[dict]:
    hist = [r for r in records if _cat(r) == "HISTORICAL_DESIGN"]
    if not hist:
        return []
    chosen: dict[str, dict] = {}

    def take(r, reason):
        e = chosen.setdefault(r["relative_path"], {
            "relative_path": r["relative_path"], "size_bytes": r["size_bytes"],
            "difficulty": _difficulty(r["size_bytes"]),
            "signature": r.get("signature_kind", {}).get("value"),
            "reasons": [],
        })
        if reason not in e["reasons"]:
            e["reasons"].append(reason)

    pools = _reason_pools(hist)
    for reason in REASON_PRIORITY:
        for r in _spread(pools[reason], PER_REASON_CAP):
            take(r, reason)

    # fill the easy/medium/hard spread up to the target
    for level in ("easy", "medium", "hard"):
        have = sum(1 for c in chosen.values() if c["difficulty"] == level)
        if have or len(chosen) >= target:
            continue
        pool = [r for r in hist if _difficulty(r["size_bytes"]) == level
                and r["relative_path"] not in chosen]
        for r in _pick(pool, 1, key=lambda r: r["size_bytes"]):
            take(r, f"difficulty_spread_{level}")
    for r in sorted(hist, key=lambda r: r["size_bytes"]):
        if len(chosen) >= target:
            break
        if r["relative_path"] not in chosen:
            take(r, "difficulty_spread_fill")

    ordered = sorted(chosen.values(),
                     key=lambda c: (c["difficulty"], c["relative_path"]))
    return _trim_to_target(ordered, target)


def _trim_to_target(ordered: list[dict], target: int) -> list[dict]:
    """Drop only records that are neither the sole exemplar of a requirement nor
    the sole representative of their difficulty band."""
    def counts(items):
        rc: dict[str, int] = {}
        dc: dict[str, int] = {}
        for c in items:
            for x in c["reasons"]:
                rc[x] = rc.get(x, 0) + 1
            dc[c["difficulty"]] = dc.get(c["difficulty"], 0) + 1
        return rc, dc

    items = list(ordered)
    while len(items) > target:
        rc, dc = counts(items)
        # prefer dropping pure filler, then lowest-priority reasons
        def droppable(c):
            if dc[c["difficulty"]] <= 1:
                return False
            return all(rc[x] > 1 or x.startswith("difficulty_spread")
                       for x in c["reasons"])

        cands = [c for c in items if droppable(c)]
        if not cands:
            break
        def rank(c):
            filler = all(x.startswith("difficulty_spread") for x in c["reasons"])
            worst = max((REASON_PRIORITY.index(x) for x in c["reasons"]
                         if x in REASON_PRIORITY), default=-1)
            return (0 if filler else 1, -worst, c["relative_path"])
        items.remove(sorted(cands, key=rank)[0])
    return items


def select_group(records, cats, n, *, prefer_vector=True) -> list[dict]:
    from . import config as C
    pool = [r for r in records if _cat(r) in cats]
    pool.sort(key=lambda r: (
        0 if (prefer_vector and r["extension"] in C.VECTOR_EXT) else 1,
        r["relative_path"]))
    return [{"relative_path": r["relative_path"], "category": _cat(r),
             "size_bytes": r["size_bytes"]} for r in pool[:n]]


def select_fonts(records: list[dict], licensed_n: int = 10,
                 quarantined_n: int = 3) -> dict:
    fonts = [r for r in records if r.get("font_posture")]
    licensed, quarantined = [], []
    seen_family: set[str] = set()
    for r in sorted(fonts, key=lambda r: r["relative_path"]):
        faces = (r.get("font") or {}).get("faces") or []
        fam = (faces[0].get("typographic_family") or faces[0].get("family")
               if faces else None) or r["filename"]
        entry = {"relative_path": r["relative_path"], "family": fam,
                 "license_status": r["font_posture"]["license_status"],
                 "source_classification": r["font_posture"]["source_classification"],
                 "license_evidence": [e["path"] for e in r.get("license_evidence", [])]}
        if r["font_posture"]["quarantined"]:
            if len(quarantined) < quarantined_n:
                quarantined.append(entry)
        elif fam not in seen_family and len(licensed) < licensed_n:
            seen_family.add(fam)
            licensed.append(entry)
    return {"download_folder_fonts": licensed,
            "suspected_system_fonts": quarantined,
            "note": ("Both sets carry license_status=UNVERIFIED. They are paired "
                     "for contrast during DIP-0C, not because either is cleared.")}


def select_brand(records: list[dict]) -> dict:
    brand, third = [], []
    for r in records:
        if _cat(r) not in ("BRAND_MASTER", "LOGO"):
            continue
        e = {"relative_path": r["relative_path"],
             "ownership_status": r["ownership_status"]["value"],
             "category": _cat(r)}
        if r["ownership_status"]["value"] == "UNCONFIRMED_THIRD_PARTY":
            third.append(e)
        else:
            brand.append(e)
    return {"bbrose_candidates": sorted(brand, key=lambda e: e["relative_path"]),
            "unconfirmed_third_party": sorted(third, key=lambda e: e["relative_path"])}


def build_pilot(records: list[dict]) -> dict:
    hist = select_historical(records)
    reusable = select_group(records, {"REUSABLE_VECTOR_ASSET", "MOTIF",
                                      "PATTERN", "ICON"}, 25)
    backgrounds = select_group(records, {"BACKGROUND"}, 10)
    fonts = select_fonts(records)
    brand = select_brand(records)

    hist_reasons = {x for c in hist for x in c["reasons"]}
    requirements = {
        "display_or_stand_design": "display_or_stand_design" in hist_reasons,
        "chinese_annotations": "chinese_annotations" in hist_reasons,
        "high_complexity_vector": "high_complexity_vector" in hist_reasons,
        "poor_filename_hygiene": "poor_filename_hygiene" in hist_reasons,
        "mixed_raster_vector": "mixed_raster_vector_proxy_by_size" in hist_reasons,
        "easy_medium_hard_spread": {c["difficulty"] for c in hist} == {"easy", "medium", "hard"},
        "official_brand_candidate": bool(brand["bbrose_candidates"]),
        "unconfirmed_third_party_logo": bool(brand["unconfirmed_third_party"]),
        "licensed_download_fonts": bool(fonts["download_folder_fonts"]),
        "suspected_system_fonts": bool(fonts["suspected_system_fonts"]),
    }
    return {
        "historical_designs": hist,
        "reusable_assets": reusable,
        "backgrounds": backgrounds,
        "fonts": fonts,
        "brand_assets": brand,
        "counts": {
            "historical_designs": len(hist), "reusable_assets": len(reusable),
            "backgrounds": len(backgrounds),
            "fonts": len(fonts["download_folder_fonts"]) + len(fonts["suspected_system_fonts"]),
            "brand_assets": len(brand["bbrose_candidates"]) + len(brand["unconfirmed_third_party"]),
        },
        "requirements_met": requirements,
        "all_requirements_met": all(requirements.values()),
        "caveats": [
            "mixed_raster_vector is a SIZE PROXY in DIP-0A (>=20MB .ai); embedded "
            "raster content is confirmed only by the deep audit in DIP-0B.",
        ],
    }
