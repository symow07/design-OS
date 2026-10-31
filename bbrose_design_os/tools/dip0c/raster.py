"""Raster + PSD header audit (DIP-0C1).

Dimensions, resolution/DPI, colour mode, alpha and compression are DIRECT (read
straight from the header via Pillow, or the 8BPS header for PSD without decoding
layers). `WATERMARK_SUSPECTED` is strictly a HEURISTIC candidate with evidence
and a human-review flag — never stated as fact, and low resolution alone never
proves a watermark.

Only the header is read; pixels are not decoded (`Image.open` is lazy), so this
stays fast and memory-safe on 8k production art.
"""
from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image

from tools.dip0.provenance import Inferred

from . import config as C

PARSER = f"{C.TOOL_NAME}.raster/{C.TOOL_VERSION}+pillow"

# Pillow's decompression-bomb guard; production art here reaches 8333×8333.
Image.MAX_IMAGE_PIXELS = 200_000_000

LOW_DPI = 72
LOW_LONG_EDGE = 1000                 # px — below this, print reuse is doubtful
STOCK_HINT = ("shutterstock", "istock", "getty", "depositphotos", "123rf",
              "dreamstime", "adobestock", "watermark", "sample", "preview",
              "comp", "لوجو", "علامة مائية")
PSD_MODES = {0: "bitmap", 1: "grayscale", 2: "indexed", 3: "rgb", 4: "cmyk",
             7: "multichannel", 8: "duotone", 9: "lab"}


def _inf(value, tier, source, evidence, confidence):
    d = Inferred(value=value, source=source, evidence=list(evidence),
                 confidence=round(confidence, 3), parser=PARSER).to_dict()
    d["tier"] = tier
    return d


def audit(rel_path: str) -> dict:
    full = C.physical_path(rel_path, C.REPO_ROOT)
    ext = full.suffix.lower()
    if ext == ".psd":
        return _psd(full, rel_path)
    return _pillow(full, rel_path)


def _pillow(full: Path, rel_path: str) -> dict:
    size_bytes = full.stat().st_size
    try:
        im = Image.open(full)          # lazy — header only, pixels not decoded
        w, h = im.size
        mode = im.mode
        fmt = im.format
        dpi = im.info.get("dpi")
        dpi_x = round(dpi[0]) if dpi else None
        alpha = mode in ("RGBA", "LA", "PA") or "transparency" in im.info
        im.close()
    except Exception as e:  # noqa: BLE001
        return {"format": full.suffix.lower(), "parser": PARSER,
                "parse_status": "UNREADABLE",
                "error": f"{type(e).__name__}: {e}", "size_bytes": size_bytes,
                "technical_readiness": _inf(C.READY_REJECT_CANDIDATE,
                                            C.TIER_HEURISTIC, "unreadable",
                                            ["Pillow could not open the file"], 0.6)}
    long_edge = max(w, h)
    wm = _watermark(full.name, long_edge, dpi_x, alpha)
    return {
        "format": full.suffix.lower(),
        "parser": PARSER,
        "parse_status": "PARSED",
        "size_bytes": size_bytes,
        "dimensions": _inf({"w": w, "h": h}, C.TIER_DIRECT, "pillow_size",
                           [f"{w}x{h}px"], 1.0),
        "resolution_dpi": _inf(dpi_x, C.TIER_DIRECT, "pillow_dpi",
                               [f"{dpi_x} dpi" if dpi_x else "no DPI in header"],
                               1.0 if dpi_x else 0.3),
        "color_mode": _inf(mode, C.TIER_DIRECT, "pillow_mode", [f"mode={mode}"], 1.0),
        "encoded_format": fmt,
        "alpha": _inf(alpha, C.TIER_DIRECT, "pillow_alpha",
                      ["has alpha/transparency" if alpha else "no alpha"], 1.0),
        "watermark_suspected": wm,
        "technical_readiness": _readiness(long_edge, dpi_x, wm["value"]),
    }


def _psd(full: Path, rel_path: str) -> dict:
    size_bytes = full.stat().st_size
    with full.open("rb") as fh:
        head = fh.read(26)
    if head[:4] != b"8BPS":
        return {"format": ".psd", "parser": PARSER, "parse_status": "NOT_PSD",
                "size_bytes": size_bytes,
                "technical_readiness": _inf(C.READY_REJECT_CANDIDATE,
                                            C.TIER_HEURISTIC, "bad_magic",
                                            ["missing 8BPS signature"], 0.7)}
    ver = struct.unpack(">H", head[4:6])[0]
    channels = struct.unpack(">H", head[12:14])[0]
    h = struct.unpack(">I", head[14:18])[0]
    w = struct.unpack(">I", head[18:22])[0]
    depth = struct.unpack(">H", head[22:24])[0]
    mode = struct.unpack(">H", head[24:26])[0]
    mode_name = PSD_MODES.get(mode, f"unknown({mode})")
    spot_or_alpha = max(0, channels - _base_channels(mode))
    long_edge = max(w, h)
    wm = _watermark(full.name, long_edge, None, spot_or_alpha > 0)
    return {
        "format": ".psd",
        "parser": PARSER,
        "parse_status": "PARSED",
        "size_bytes": size_bytes,
        "psd_version": "PSB" if ver == 2 else "PSD",
        "dimensions": _inf({"w": w, "h": h}, C.TIER_DIRECT, "psd_header",
                           [f"{w}x{h}px"], 1.0),
        "channels": _inf(channels, C.TIER_DIRECT, "psd_header",
                         [f"{channels} channels ({spot_or_alpha} extra beyond "
                          f"{mode_name})"], 1.0),
        "bit_depth": depth,
        "color_mode": _inf(mode_name, C.TIER_DIRECT, "psd_header",
                           [f"mode={mode_name}"], 1.0),
        "extra_channels": spot_or_alpha,
        "watermark_suspected": wm,
        "technical_readiness": _readiness(long_edge, None, wm["value"],
                                          is_layered_source=True),
    }


def _base_channels(mode: int) -> int:
    return {0: 1, 1: 1, 2: 1, 3: 3, 4: 4, 7: 1, 8: 2, 9: 3}.get(mode, 3)


def _watermark(name: str, long_edge: int, dpi, has_alpha: bool) -> dict:
    """HEURISTIC only. Low-res never *proves* a watermark; a stock/preview
    filename hint plus low resolution raises suspicion for human review."""
    lname = name.lower()
    hints = [h for h in STOCK_HINT if h in lname]
    low_res = long_edge < LOW_LONG_EDGE
    suspected = bool(hints) and low_res
    ev = []
    if hints:
        ev.append(f"filename hint(s): {hints}")
    if low_res:
        ev.append(f"low resolution (long edge {long_edge}px)")
    if not ev:
        ev = ["no stock/preview hints; resolution adequate"]
    return _inf(suspected, C.TIER_HEURISTIC, "filename+resolution", ev,
                0.55 if suspected else 0.4)


def _readiness(long_edge, dpi, watermarked, is_layered_source: bool = False):
    if watermarked:
        return _inf(C.READY_REFERENCE_ONLY, C.TIER_HEURISTIC, "watermark_suspected",
                    ["possible stock/preview watermark; reference only until "
                     "cleared"], 0.55)
    low = long_edge < LOW_LONG_EDGE
    if low:
        return _inf(C.READY_REFERENCE_ONLY, C.TIER_HEURISTIC, "low_resolution",
                    [f"long edge {long_edge}px below print threshold"], 0.6)
    if is_layered_source:
        return _inf(C.readiness_value(C.READY_TECHNICALLY_USABLE_WITH_CAVEATS),
                    C.TIER_HEURISTIC, "layered_psd",
                    ["layered PSD source"], 0.55)
    return _inf(C.readiness_value(C.READY_TECHNICALLY_USABLE_WITH_CAVEATS),
                C.TIER_HEURISTIC, "raster_ok",
                [f"long edge {long_edge}px adequate"], 0.55)
