"""Palette records: raw source values and derivative previews (DIP-0C3c).

**Raw values are authoritative. A converted preview is a derivative and never replaces
the source representation.** The two live under separate keys and are never merged,
for the same reason machine inference and human confirmation never share a key: once
they are mixed, nobody can tell which one they are looking at.

RGB, CMYK, Lab and GRAY are **not interchangeable**:

- **CMYK** — no print-accurate RGB is claimed without a declared ICC profile. A
  converted sRGB is a *preview only*, produced by a naive formula that is explicitly
  labelled as such, and the original CMYK is preserved untouched.
- **Lab** — the illuminant assumption is recorded, not assumed away. Out-of-gamut
  results are flagged rather than clipped in silence.
- **Spot** — spot *identity* and its alternate preview colour are separate facts. A
  spot's real colour lives in a physical ink book, not in this file.

**No Pantone conversion is ever fabricated from a generic formula.** Where a swatch
merely *names* a Pantone, the name is evidence about naming — not a colour definition.
"""
from __future__ import annotations

from tools.dip0b.color import srgb_to_lab

from . import ase
from . import config as C

PARSER = f"{C.TOOL_NAME}.palette/{C.TOOL_VERSION}"
SCHEMA_VERSION = "palette/1.0"

# --- conversion methods (named, so a reader knows what produced a number) -------
CONV_DIRECT = "DIRECT_SOURCE_VALUE"
CONV_SRGB_D65 = "sRGB_to_LAB_D65"                 # dip0b color.srgb_to_lab
CONV_NAIVE_CMYK = "NAIVE_CMYK_TO_SRGB_NO_ICC"     # a preview. Not colour management.
CONV_GRAY = "GRAY_TO_SRGB_LINEARLESS"
CONV_NONE = "NO_SAFE_CONVERSION"

# --- warnings ------------------------------------------------------------------
W_NO_ICC = "NO_ICC_PROFILE_DECLARED"
W_PREVIEW_ONLY = "PREVIEW_ONLY_NOT_PRINT_ACCURATE"
W_OUT_OF_GAMUT = "OUT_OF_GAMUT"
W_CLIPPED = "CHANNEL_VALUE_CLIPPED"
W_SPOT_ALTERNATE = "SPOT_ALTERNATE_COLOR_IS_NOT_THE_SPOT"
W_LAB_ILLUMINANT_ASSUMED = "LAB_ILLUMINANT_ASSUMED_D50"
W_OUT_OF_RANGE = "CHANNEL_VALUE_OUT_OF_DECLARED_RANGE"

# Confidence is CAPPED for anything that is not a direct source read.
CONF_DIRECT = 1.0
CONF_PREVIEW = 0.5
CONF_UNSAFE = 0.0


def _clip01(v: float) -> tuple[float, bool]:
    if v < 0.0:
        return 0.0, True
    if v > 1.0:
        return 1.0, True
    return v, False


def normalize(swatch: dict) -> dict:
    """Derive analytical values from a raw swatch. NEVER mutates the raw record."""
    model, ch = swatch["model"], list(swatch["channels"])
    warnings: list[str] = []
    srgb = None
    lab = None
    method = CONV_NONE
    conf = CONF_UNSAFE

    if model == "RGB":
        vals, clipped = zip(*(_clip01(v) for v in ch))
        if any(clipped):
            warnings += [W_CLIPPED, W_OUT_OF_RANGE]
        srgb = [round(v, 6) for v in vals]
        lab = [round(x, 3) for x in srgb_to_lab(tuple(vals))]
        method = CONV_SRGB_D65
        conf = CONF_DIRECT          # RGB->sRGB is the identity; Lab is well-defined

    elif model == "GRAY":
        g, clipped = _clip01(ch[0])
        if clipped:
            warnings += [W_CLIPPED, W_OUT_OF_RANGE]
        # ASE GRAY: 0 = white, 1 = black (ink coverage), so it inverts.
        v = 1.0 - g
        srgb = [round(v, 6)] * 3
        lab = [round(x, 3) for x in srgb_to_lab((v, v, v))]
        method = CONV_GRAY
        conf = CONF_PREVIEW
        warnings.append(W_PREVIEW_ONLY)

    elif model == "CMYK":
        vals, clipped = zip(*(_clip01(v) for v in ch))
        if any(clipped):
            warnings += [W_CLIPPED, W_OUT_OF_RANGE]
        c, m, y, k = vals
        # A NAIVE formula, and labelled as one. Real CMYK->RGB needs an ICC profile
        # and a rendering intent; without them this is an approximation for the eye,
        # never a colour-managed value. The CMYK below stays authoritative.
        r, g, b = ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
        srgb = [round(r, 6), round(g, 6), round(b, 6)]
        lab = [round(x, 3) for x in srgb_to_lab((r, g, b))]
        method = CONV_NAIVE_CMYK
        conf = CONF_PREVIEW
        warnings += [W_NO_ICC, W_PREVIEW_ONLY]

    elif model == "LAB":
        # Preserved as-is. ASE Lab is L in 0..1 (x100), a/b in -128..127.
        lab = [round(ch[0] * 100.0, 3), round(ch[1], 3), round(ch[2], 3)]
        method = CONV_DIRECT
        conf = CONF_DIRECT
        warnings.append(W_LAB_ILLUMINANT_ASSUMED)
        if not (0.0 <= lab[0] <= 100.0) or not all(-128 <= x <= 127
                                                   for x in lab[1:]):
            warnings.append(W_OUT_OF_GAMUT)
        # Lab -> sRGB is deliberately NOT done: it needs a gamut decision, and a
        # silently clipped preview would be worse than no preview at all.

    if swatch["color_type"] == "SPOT":
        warnings.append(W_SPOT_ALTERNATE)
        conf = min(conf, CONF_PREVIEW)

    return {
        "srgb_preview": srgb,
        "srgb_8bit_preview": ([round(v * 255) for v in srgb] if srgb else None),
        "lab": lab,
        "channel_range": "0.0..1.0" if model != "LAB" else "L 0..100, a/b -128..127",
        "conversion_method": method,
        "conversion_library": f"tools.dip0b.color/{C.TOOL_VERSION}",
        "gamut_warning": W_OUT_OF_GAMUT in warnings,
        "clipping_warning": W_CLIPPED in warnings,
        "warnings": sorted(set(warnings)),
        "confidence": conf,
        "note": "DERIVATIVE. The raw source values are authoritative; these are "
                "analytical previews and never replace the source representation.",
    }


def swatch_record(s: dict) -> dict:
    """Raw and normalized, side by side and clearly separated."""
    return {
        "raw": {
            "name": s["name"],
            "model": s["model"],
            "channels": s["channels"],
            "color_type": s["color_type"],
            "color_type_raw": s["color_type_raw"],
            "source_block_index": s["block_index"],
            "source_offset": s["source_offset"],
            "source_end": s["source_end"],
            "declared_block_length": s["declared_block_length"],
            "body_sha256": s["body_sha256"],
            "bytes_consumed": s["bytes_consumed"],
            "unexplained_bytes": s["unexplained_bytes"],
            "layout": s["layout"],
            "fallback_used": s["fallback_used"],
            "standard_failure_reason": s["standard_failure_reason"],
            "group": s.get("group"),
            "authoritative": True,
        },
        "normalized": normalize(s),
    }


def palette_record(parsed: dict) -> dict:
    """The palette, as four separate things: file, palette, groups, swatches."""
    swatches = [swatch_record(s) for s in parsed["swatches"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "source_file": {
            "path": parsed["source"],
            "sha256": parsed["source_sha256"],
            "bytes": parsed["source_bytes"],
        },
        "palette": {
            "format": "ASE",
            "signature": parsed["signature"],
            "version": parsed["version"],
            "declared_block_count": parsed["declared_block_count"],
            "parsed_block_count": parsed["parsed_block_count"],
            "group_count": len(parsed["groups"]),
            "swatch_count": len(swatches),
            "color_models": sorted({s["raw"]["model"] for s in swatches}),
            "color_types": sorted({s["raw"]["color_type"] for s in swatches}),
            "parse_status": parsed["parse_status"],
            "capability": parsed["capability"],
            "layouts_seen": parsed["layouts_seen"],
            "fallback_used": parsed["fallback_used"],
            "trailing_bytes": parsed["trailing_bytes"],
            "parser_warnings": parsed["warnings"],
        },
        "groups": parsed["groups"],
        "swatches": swatches,
        "conversion_warnings": sorted({w for s in swatches
                                       for w in s["normalized"]["warnings"]}),
        "parser": PARSER,
    }


def machine_parse_status(value: str) -> str:
    """A file that needed the fallback can NEVER be TECHNICALLY_PARSED."""
    if value not in ase.STATUSES:
        raise ValueError(f"{value!r} is not an ASE parse status")
    return value
