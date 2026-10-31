"""Per-unit colour intelligence (DIP-0B4).

Six buckets, strictly separated. Nothing is forced into `artwork`:

  artwork · dieline_technical · embedded_raster · swatch_reference ·
  canvas_background · unresolved_or_ambiguous

Two rules the pilot forced on us:

* **A thin structural stroke is not technical ink.** A colour is excluded from
  artwork intelligence only when DIP-0B3 classified that specific path as a
  technical line (cut / fold / crease / registration / crop / dimension) — never
  because the stroke happens to be thin.

* **Registration is not black.** `/Separation /All` at full tint converts to
  sRGB (0,0,0), which is indistinguishable from process black, rich black and
  ordinary black artwork. Path-level spot association is UNAVAILABLE on this
  pilot, so an RGB-black path is never *mapped* to `/All`. Document-level `/All`
  presence must not silently strip black artwork from the palette: black fills
  inside artwork stay in `artwork`, flagged ambiguous with capped confidence;
  only genuinely unattributable paths go to `unresolved_or_ambiguous`.
"""
from __future__ import annotations

import math

from . import config as C
from .separation import D50, cmyk_to_srgb, lab_to_srgb

BUCKETS = (
    "artwork",
    "dieline_technical",
    "embedded_raster",
    "swatch_reference",
    "canvas_background",
    "unresolved_or_ambiguous",
)

# ΔE*ab (CIE76). Simple, symmetric and adequate for "is this ink plausibly that
# spot"; it is NOT perceptually uniform, so the tolerance is generous and every
# match records its own ΔE rather than a bare yes/no.
DELTA_E_TOLERANCE = 8.0
DELTA_E_AMBIGUOUS_MARGIN = 3.0     # two spots this close together = ambiguous
NEAR_BLACK_MAX = 0.12              # per-channel, on 0..1 sRGB
NEAR_WHITE_MIN = 0.94              # paper / unprinted
MIN_MATCH_TINT = 0.25              # a 10 % tint of a pale ink IS paper
SPOT_CONFIDENCE_CAP = 0.8


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb_to_lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """sRGB (0..1) → CIE Lab (D65)."""
    r, g, b = (_srgb_to_linear(max(0.0, min(1.0, c))) for c in rgb)
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    xn, yn, zn = 0.95047, 1.00000, 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)

    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e76(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def is_near_black(rgb) -> bool:
    return all(c <= NEAR_BLACK_MAX for c in rgb)


def is_near_white(rgb) -> bool:
    return all(c >= NEAR_WHITE_MIN for c in rgb)


# --------------------------------------------------------------------------


def build_spot_lab(separations: dict) -> list[dict]:
    """Spot inks with a usable full-strength sRGB, in Lab."""
    out = []
    for name, s in separations.get("separations", {}).items():
        srgb = s.get("srgb_full_strength")
        if not srgb:
            continue
        rgb01 = tuple(v / 255.0 for v in srgb)
        out.append({"name": name, "srgb": srgb, "lab": srgb_to_lab(rgb01),
                    "is_registration": s["is_registration"]})
    return sorted(out, key=lambda s: s["name"])


def _tint_to_srgb(comps, kind, wp):
    if kind == "lab" and len(comps) >= 3:
        return lab_to_srgb(comps[0], comps[1], comps[2], tuple(wp) if wp else D50)
    if kind == "cmyk" and len(comps) >= 4:
        return cmyk_to_srgb(*comps[:4])
    if kind == "rgb" and len(comps) >= 3:
        return tuple(int(round(max(0.0, min(1.0, v)) * 255)) for v in comps[:3])
    if kind == "gray" and len(comps) >= 1:
        g = int(round(max(0.0, min(1.0, comps[0])) * 255))
        return (g, g, g)
    return None


def build_spot_ramp(separations: dict, steps: int = 10) -> list[dict]:
    """Every ink sampled across its TINT ramp, not just at full strength.

    Artwork prints spot inks at tints (25 %, 50 %…). Matching an RGB-converted
    path only against the 100 % value found **zero** matches across the whole
    pilot. The tint transform is `C0 + t^N * (C1 - C0)` in the alternate space.
    """
    out = []
    for name, s in separations.get("separations", {}).items():
        c1 = s.get("tint_full")
        if not c1:
            continue
        c0 = s.get("tint_zero") or [0.0] * len(c1)
        kind = s.get("alternate_space")
        wp = s.get("alternate_whitepoint")
        n = s.get("exponent_N") or 1.0
        samples = []
        for i in range(1, steps + 1):
            t = i / steps
            comps = [a + (t ** n) * (b - a) for a, b in zip(c0, c1)]
            rgb = _tint_to_srgb(comps, kind, wp)
            if rgb:
                samples.append({"tint": round(t, 2), "srgb": list(rgb),
                                "lab": srgb_to_lab(tuple(v / 255.0 for v in rgb))})
        if samples:
            out.append({"name": name, "is_registration": s["is_registration"],
                        "samples": samples})
    return sorted(out, key=lambda s: s["name"])


def _spot_best(spot, lab) -> tuple[float, float | None]:
    """(min ΔE, tint at which it occurs).

    Tints below `MIN_MATCH_TINT` are excluded: a 10 % tint of a pale ink converts
    to something within ΔE 1.5 of paper white, so allowing them made plain white
    "match" PANTONE 621 C.
    """
    if "samples" in spot:
        usable = [x for x in spot["samples"] if x["tint"] >= MIN_MATCH_TINT]
        if not usable:
            usable = spot["samples"]
        best = min(usable, key=lambda x: delta_e76(lab, x["lab"]))
        return delta_e76(lab, best["lab"]), best["tint"]
    return delta_e76(lab, spot["lab"]), 1.0


def match_spot(rgb01, spots: list[dict],
               tol: float = DELTA_E_TOLERANCE) -> dict:
    """Nearest-ΔE spot candidates for an RGB-converted path colour.

    HEURISTIC by construction: `get_drawings()` discards the colourspace, so this
    is an inference from an already-converted colour. Every result carries its ΔE,
    the tolerance, all plausible candidate names, an ambiguity flag and a capped
    confidence.
    """
    if not spots:
        return {"matched": None, "delta_e": None, "tolerance": tol,
                "candidates": [], "ambiguous": False, "confidence": 0.0,
                "tier": C.TIER_HEURISTIC,
                "reason": "no separation inks defined in the document"}

    if is_near_white(rgb01):
        return {"matched": None, "matched_tint": None, "delta_e": None,
                "tolerance": tol, "candidates": [], "ambiguous": False,
                "confidence": 0.0, "tier": C.TIER_HEURISTIC,
                "reason": "near-white: indistinguishable from paper / unprinted"}

    lab = srgb_to_lab(rgb01)
    scored = []
    for s in spots:
        de, tint = _spot_best(s, lab)
        scored.append({"name": s["name"], "delta_e": round(de, 2), "tint": tint,
                       "is_registration": s["is_registration"]})
    scored.sort(key=lambda r: r["delta_e"])
    # Registration ink is technical, not an artwork colour. It converts to black
    # at full tint, so near-black artwork "matches" it — the decision-4 trap.
    # It may appear as a candidate for transparency, but is never the match.
    matchable = [r for r in scored if not r["is_registration"]]
    within = [r for r in matchable if r["delta_e"] <= tol]
    if not within:
        return {"matched": None, "delta_e": (matchable[0]["delta_e"] if matchable
                                             else scored[0]["delta_e"]),
                "tolerance": tol, "candidates": scored[:3], "ambiguous": False,
                "confidence": 0.0, "tier": C.TIER_HEURISTIC,
                "reason": (f"nearest non-registration ink is ΔE "
                           f"{matchable[0]['delta_e']} away" if matchable
                           else "only registration ink defined")}

    ambiguous = (len(within) > 1
                 and (within[1]["delta_e"] - within[0]["delta_e"])
                 < DELTA_E_AMBIGUOUS_MARGIN)
    # Closer match -> higher confidence, but never above the cap.
    conf = SPOT_CONFIDENCE_CAP * max(0.0, 1.0 - within[0]["delta_e"] / tol)
    if ambiguous:
        conf *= 0.5
    return {"matched": None if ambiguous else within[0]["name"],
            "matched_tint": None if ambiguous else within[0]["tint"],
            "delta_e": within[0]["delta_e"], "tolerance": tol,
            "candidates": within[:3], "ambiguous": ambiguous,
            "confidence": round(conf, 3), "tier": C.TIER_HEURISTIC,
            "reason": ("two inks within ΔE margin — ambiguous" if ambiguous
                       else "single ink within tolerance")}


def black_explanations(rgb01, registration_present: bool,
                       path_association: str, spots: list[dict]) -> dict:
    """Every plausible explanation for a near-black path, never a single fact."""
    lab = srgb_to_lab(rgb01)
    cands = [{"explanation": "artwork black (ordinary K or rich black)",
              "delta_e": round(delta_e76(lab, srgb_to_lab((0.0, 0.0, 0.0))), 2)}]
    for s in spots:
        de, tint = _spot_best(s, lab)
        dark = (min(x["lab"][0] for x in s["samples"]) if "samples" in s
                else s["lab"][0])
        if dark < 30:                            # any dark ink is a rival
            cands.append({"explanation": f"spot ink {s['name']}",
                          "delta_e": round(de, 2), "at_tint": tint,
                          "is_registration": s["is_registration"]})
    if registration_present:
        cands.append({"explanation": "registration ink /Separation /All",
                      "delta_e": round(delta_e76(lab, srgb_to_lab((0.0, 0.0, 0.0))), 2),
                      "is_registration": True})
    return {
        "ambiguous": True,
        "candidates": sorted(cands, key=lambda c: c["delta_e"]),
        "path_association": path_association,
        "confidence": 0.0 if path_association != "DIRECT" else SPOT_CONFIDENCE_CAP,
        "tier": C.TIER_HEURISTIC,
        "note": ("registration ink at full tint converts to sRGB(0,0,0) and is "
                 "indistinguishable from process/rich/artwork black; path-level "
                 "association is required to resolve this and is unavailable"),
    }


# --------------------------------------------------------------------------


def bucket_path(path: dict, *, technical_class: str | None,
                in_palette_strip: bool, is_canvas_background: bool,
                registration_present: bool, path_association: str,
                spots: list[dict]) -> tuple[str, dict]:
    """Assign one path's colour to exactly one bucket, with its evidence."""
    rgb = path.get("fill") or path.get("stroke")
    if rgb is None:
        return "unresolved_or_ambiguous", {"reason": "path has no colour"}

    if technical_class:
        return "dieline_technical", {
            "reason": f"DIP-0B3 classified this path as {technical_class}",
            "technical_class": technical_class, "tier": C.TIER_HEURISTIC}

    if in_palette_strip:
        return "swatch_reference", {"reason": "inside a COLOR_PALETTE_STRIP unit",
                                    "spot_match": match_spot(rgb, spots)}

    if is_canvas_background:
        return "canvas_background", {"reason": "page/ArtBox ground fill"}

    # Near-black with no technical classification: a *stroke* could be an
    # unclassified registration/crop mark; a *fill* is ordinary artwork black.
    if is_near_black(rgb):
        expl = black_explanations(rgb, registration_present, path_association, spots)
        if path["type"] == "s" and registration_present:
            return "unresolved_or_ambiguous", {
                "reason": ("near-black stroke on a page that uses registration "
                           "ink, with no path-level association"),
                "explanations": expl}
        # Black artwork is NOT stripped from the palette by /All presence.
        return "artwork", {"reason": "near-black artwork fill",
                           "ambiguity": expl,
                           "spot_match": match_spot(rgb, spots)}

    return "artwork", {"reason": "artwork colour", "spot_match": match_spot(rgb, spots)}


def _key(rgb) -> tuple:
    return tuple(round(c, 3) for c in rgb)


def summarise_palette(entries: list[dict], top: int = 6) -> dict:
    """Coverage-weighted dominant + supporting colours of one bucket."""
    by_colour: dict[tuple, dict] = {}
    total = 0.0
    for e in entries:
        k = _key(e["rgb"])
        rec = by_colour.setdefault(k, {"rgb": list(k), "area_pt2": 0.0, "paths": 0,
                                       "spot_match": e.get("spot_match")})
        rec["area_pt2"] += e["area"]
        rec["paths"] += 1
        total += e["area"]

    ranked = sorted(by_colour.values(), key=lambda r: -r["area_pt2"])
    for r in ranked:
        r["coverage"] = round(r["area_pt2"] / total, 4) if total else 0.0
        r["area_pt2"] = round(r["area_pt2"], 2)
        r["srgb_255"] = [int(round(c * 255)) for c in r["rgb"]]
    return {"distinct_colours": len(ranked),
            "dominant": ranked[:1],
            "supporting": ranked[1:top],
            "total_area_pt2": round(total, 2)}
