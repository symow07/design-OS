"""The colour-comparison GATE (DIP-0C3d).

This is not a matching engine. It is the thing that stands in front of one, and its job
is to **refuse** comparisons that would look rigorous and mean nothing.

A ΔE computed from a naive CMYK→RGB preview has all the trappings of a measurement —
a number, a unit, a threshold — and none of the validity. Without an ICC profile, those
RGB values are not a rendering of that ink; they are an arithmetic gesture. Comparing
them and reporting "ΔE 2.1, a close match" would be the single most confident-sounding
lie this system could tell.

So:

**Permitted.** Source RGB ↔ source RGB. Source Lab ↔ source Lab *under identical
documented assumptions*. CMYK ↔ CMYK where the profile context is explicitly known.

**Refused.** Naive CMYK→RGB comparison. ICC-less print comparison. A Pantone *name*
treated as an authoritative ID. ΔE from uncontrolled derived previews. Cross-model
comparison of any kind.

And specifically: `Pantone_3519C.ase` is **not** connected to Historical Design Memory.
Its existence does not establish that BBROSE ever used that colour, and its name is not
a match against anything.
"""
from __future__ import annotations

from tools.dip0b.color import delta_e76, srgb_to_lab

from . import config as C
from . import palette as PAL

PARSER = f"{C.TOOL_NAME}.color_compare/{C.TOOL_VERSION}"

COMPARABLE = "COMPARABLE"
UNAVAILABLE = "COMPARISON_UNAVAILABLE"

# Comparisons that are physically meaningful.
ALLOWED_PAIRS = {("RGB", "RGB"), ("LAB", "LAB"), ("CMYK", "CMYK")}

R_NO_ICC = "CMYK comparison requires an explicitly known ICC profile context"
R_CROSS_MODEL = "cross-model comparison is not meaningful without colour management"
R_DERIVED = "a derived preview is not a measurement — it may not ground a ΔE"
R_NAME = "a colour NAME is not an authoritative identifier"
R_LAB_ASSUMPTIONS = "Lab values compared under different documented assumptions"


class ComparisonRefused(RuntimeError):
    """The comparison would look rigorous and mean nothing."""


def _raw(sw: dict) -> dict:
    return sw["raw"] if "raw" in sw else sw


def can_compare(a: dict, b: dict, *, icc_profile: str = None,
                lab_assumption_a: str = None,
                lab_assumption_b: str = None) -> dict:
    """May these two swatches be compared at all? PURE — decides, never computes."""
    ra, rb = _raw(a), _raw(b)
    ma, mb = ra["model"], rb["model"]

    if (ma, mb) not in ALLOWED_PAIRS:
        return {"comparable": False, "status": UNAVAILABLE,
                "reason": f"{R_CROSS_MODEL} ({ma} vs {mb})",
                "models": [ma, mb]}

    if ma == "CMYK" and not icc_profile:
        return {"comparable": False, "status": UNAVAILABLE,
                "reason": R_NO_ICC, "models": [ma, mb]}

    if ma == "LAB" and lab_assumption_a != lab_assumption_b:
        return {"comparable": False, "status": UNAVAILABLE,
                "reason": (f"{R_LAB_ASSUMPTIONS}: {lab_assumption_a!r} vs "
                           f"{lab_assumption_b!r}"),
                "models": [ma, mb]}

    return {"comparable": True, "status": COMPARABLE,
            "reason": f"both are SOURCE {ma} values", "models": [ma, mb],
            "icc_profile": icc_profile}


def compare(a: dict, b: dict, *, icc_profile: str = None,
            lab_assumption_a: str = None, lab_assumption_b: str = None,
            allow_derived: bool = False) -> dict:
    """Compare two SOURCE swatches. Raises rather than return a meaningless number."""
    gate = can_compare(a, b, icc_profile=icc_profile,
                       lab_assumption_a=lab_assumption_a,
                       lab_assumption_b=lab_assumption_b)
    if not gate["comparable"]:
        raise ComparisonRefused(gate["reason"])

    ra, rb = _raw(a), _raw(b)
    if not allow_derived:
        for r in (ra, rb):
            if r.get("authoritative") is False:
                raise ComparisonRefused(R_DERIVED)

    model = ra["model"]
    if model == "RGB":
        la = srgb_to_lab(tuple(ra["channels"]))
        lb = srgb_to_lab(tuple(rb["channels"]))
    elif model == "LAB":
        la = (ra["channels"][0] * 100.0, ra["channels"][1], ra["channels"][2])
        lb = (rb["channels"][0] * 100.0, rb["channels"][1], rb["channels"][2])
    else:                                    # CMYK, with a declared profile
        raise ComparisonRefused(
            "CMYK ΔE requires a real profile transform, which this milestone does not "
            "ship. The profile context is recorded; the comparison is deferred rather "
            "than faked.")

    return {
        "status": COMPARABLE,
        "model": model,
        "delta_e76": round(delta_e76(la, lb), 3),
        "basis": "SOURCE values only",
        "icc_profile": icc_profile,
        "note": "ΔE76 between SOURCE values of the same model. No derived preview "
                "entered this number.",
        "parser": PARSER,
    }


def refuse_naive_preview(sw: dict) -> None:
    """A preview produced without colour management may never ground a comparison."""
    n = sw.get("normalized") or {}
    if n.get("conversion_method") == PAL.CONV_NAIVE_CMYK:
        raise ComparisonRefused(
            f"{R_DERIVED}: this sRGB was produced by {PAL.CONV_NAIVE_CMYK}. Without an "
            "ICC profile it is not a rendering of that ink, and a ΔE built on it would "
            "look like a measurement while being an arithmetic gesture.")


def name_is_not_an_identifier(name: str) -> dict:
    """A Pantone name is naming EVIDENCE. It is not a key you may match on."""
    return {
        "status": UNAVAILABLE,
        "reason": R_NAME,
        "name": name,
        "note": "Matching on a colour name would require the proprietary library that "
                "defines it — which we do not have, may not bundle, and will not "
                "approximate.",
        "parser": PARSER,
    }


def historical_link(asset: str) -> dict:
    """The real ASE is NOT connected to Historical Design Memory. Deliberately."""
    return {
        "asset": asset,
        "linked_to_historical_design_memory": False,
        "status": UNAVAILABLE,
        "reason": "the file's existence does not establish that BBROSE ever used this "
                  "colour. A palette sitting in a downloads folder is evidence of a "
                  "download.",
        "claims_not_made": [
            "BBROSE historically used Pantone 3519 C",
            "the swatch name is an official Pantone match",
            "this colour appears in historical BBROSE designs",
        ],
        "retrievable": False,
        "automatically_usable": False,
        "parser": PARSER,
    }
