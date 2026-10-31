"""Raster quality (DIP-0C2b).

The decisive signal is **effective resolution measured on the candidate crop** —
a sticker cropped out of a 2000² sheet is far smaller than its parent, and it is
the crop that would be reused.

Two rules the scope makes binding:

* **DPI metadata is never decisive.** Low or absent DPI must never reject a
  high-resolution file. DPI is recorded as metadata only; an 8333×8333 file with
  no DPI tag is a `HIGH_RES_CANDIDATE`.
* **Nothing is called print-ready from pixels alone.** Print suitability needs an
  intended physical size and the resulting effective PPI, which we do not have for
  rasters — so `print_suitability` is `UNDETERMINED_REQUIRES_PHYSICAL_SIZE`.
  (Vector candidates DO carry real mm bounds, recorded as evidence, still never a
  print grant.)
"""
from __future__ import annotations

from . import config as C

PARSER = f"{C.TOOL_NAME}.quality/{C.TOOL_VERSION}"


def resolution_band(long_edge_px: int) -> str:
    if long_edge_px >= C.RES_THRESHOLDS[C.RES_HIGH_RES_CANDIDATE]:
        return C.RES_HIGH_RES_CANDIDATE
    if long_edge_px >= C.RES_THRESHOLDS[C.RES_SCREEN_READY]:
        return C.RES_SCREEN_READY
    if long_edge_px >= C.RES_THRESHOLDS[C.RES_LOW_RES_REFERENCE]:
        return C.RES_LOW_RES_REFERENCE
    return C.RES_TOO_LOW


def effective_resolution(bbox_px) -> tuple[int, int, int]:
    """Pixel extent of the CANDIDATE crop -> (w, h, long_edge)."""
    if not bbox_px:
        return 0, 0, 0
    x0, y0, x1, y1 = bbox_px
    w, h = max(0, int(x1 - x0)), max(0, int(y1 - y0))
    return w, h, max(w, h)


def assess_raster(*, bbox_px, source_facts: dict) -> dict:
    """source_facts comes from the C1 raster audit (dims, dpi, mode, alpha)."""
    w, h, long_edge = effective_resolution(bbox_px)
    band = resolution_band(long_edge)
    dpi = source_facts.get("dpi")
    dims = source_facts.get("dimensions") or {}
    alpha = bool(source_facts.get("alpha"))
    mode = source_facts.get("color_mode")

    # THE rule: DPI never decides. Record it, and say so explicitly when a
    # high-resolution file carries no/low DPI metadata.
    dpi_note = ("DPI metadata absent or low; NOT used to judge quality — the "
                "effective pixel extent decides"
                if (dpi in (None, 0) or (isinstance(dpi, int) and dpi < 150))
                else f"DPI metadata {dpi} (recorded, not decisive)")

    return {
        "parser": PARSER,
        "source_dimensions": dims,
        "effective_resolution": {"w": w, "h": h, "long_edge": long_edge},
        "resolution_band": band,
        "dpi_metadata": dpi,
        "dpi_is_decisive": False,
        "dpi_note": dpi_note,
        "print_suitability": C.PRINT_SUITABILITY_UNDETERMINED,
        "alpha": alpha,
        "color_mode": mode,
        "compression": source_facts.get("encoded_format"),
        "crop_flexibility": _crop_flexibility(long_edge, band),
        "upscaling_suitability": _upscaling(band),
        "low_resolution_risk": band in (C.RES_LOW_RES_REFERENCE, C.RES_TOO_LOW),
        "role_guess": _role(w, h, alpha, source_facts),
    }


def _crop_flexibility(long_edge: int, band: str) -> str:
    if band == C.RES_HIGH_RES_CANDIDATE:
        return "high — crops retain usable resolution"
    if band == C.RES_SCREEN_READY:
        return "moderate — cropping quickly drops below screen resolution"
    return "low — already at or below reference resolution"


def _upscaling(band: str) -> str:
    return {
        C.RES_HIGH_RES_CANDIDATE: "not needed",
        C.RES_SCREEN_READY: "modest upscaling plausible",
        C.RES_LOW_RES_REFERENCE: "upscaling would be lossy; reference use",
        C.RES_TOO_LOW: "unsuitable for upscaling",
    }[band]


def _role(w: int, h: int, alpha: bool, facts: dict) -> dict:
    """HEURISTIC, human-reviewable. Never a rights or reuse decision."""
    ratio = (max(w, h) / min(w, h)) if w and h else 1.0
    if alpha:
        role, why = C.ROLE_ILLUSTRATION, "transparent background — isolated subject"
    elif ratio < 1.15 and max(w, h) >= 1500:
        role, why = C.ROLE_BACKGROUND, "large and near-square — background/canvas"
    elif facts.get("encoded_format") == "JPEG" and ratio > 1.2:
        role, why = C.ROLE_PHOTO, "JPEG with photographic aspect"
    else:
        role, why = C.ROLE_UNKNOWN, "no decisive role signal"
    return {"value": role, "tier": C.TIER_HEURISTIC, "evidence": [why],
            "confidence": 0.4}
