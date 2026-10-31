"""Deterministic variation-diversity gate (Phase 2A-6E §7).

Task #50's Gate-1 set was three cosmetic variations of one layout: same
ivory field, same oversized stacked name, same single hairline + dots, same
logo/copy placement. QA scores each render alone, so nothing measured the
SET. This gate reads the three variation prompts BEFORE any image spend and
fails closed when they do not differ materially.

Features per prompt (all deterministic keyword extraction):
    logo_zone        where the BBROSE mark sits
    name_zone        where the product name sits
    motif_family     direction_signature's scored motif classification
    field_structure  the color-field devices used (band/panel/gradient/...)

Rule: every pair must differ in at least 2 of the 4 features, and the three
prompts must not share one identical (motif, logo_zone, name_zone) triple.
Applied on the material-influenced regeneration path — the path this phase
introduces — so legacy flows are byte-identical.
"""
from __future__ import annotations

import re

from .direction_signature import classify

VARIATION_PROMPTS_NOT_DISTINCT = "VARIATION_PROMPTS_NOT_DISTINCT"
VARIATION_DIVERSITY_UNREADABLE = "VARIATION_DIVERSITY_UNREADABLE"
MIN_FEATURE_DIFFERENCES = 2

_ZONES = (
    ("upper-left", ("upper-left", "upper left", "top-left", "top left")),
    ("upper-right", ("upper-right", "upper right", "top-right", "top right")),
    ("upper-center", ("upper-center", "upper center", "top center",
                      "top-center", "upper-centre", "top centre")),
    ("lower-left", ("lower-left", "lower left", "bottom-left", "bottom left")),
    ("lower-right", ("lower-right", "lower right", "bottom-right",
                     "bottom right")),
    ("lower-center", ("lower-center", "lower center", "bottom center",
                      "lower third", "lower quarter")),
    ("center", ("centered", "panel center", "central field", "center of",
                "middle of the panel", "central")),
    ("offset-right", ("offset to the right", "right side of the panel",
                      "right-aligned column", "toward the right edge")),
    ("offset-left", ("offset to the left", "left side of the panel",
                     "left-aligned column", "toward the left edge")),
)

_FIELD_DEVICES = (
    "band", "panel", "block", "gradient", "wash", "column", "frame",
    "stripe", "field of", "color field", "colour field", "tonal",
)


def _zone_near(text: str, subject_patterns) -> str:
    """The placement zone stated within a window after a subject mention."""
    for pattern in subject_patterns:
        for match in re.finditer(pattern, text):
            window = text[match.start():match.start() + 160]
            for zone, cues in _ZONES:
                if any(cue in window for cue in cues):
                    return zone
    return ""


def prompt_features(prompt_text: str, product_name: str = "") -> dict:
    text = " ".join(str(prompt_text or "").lower().split())
    name_patterns = [re.escape(product_name.lower())] if product_name else []
    name_patterns += [r"product name", r"stacked lines of", r"headline"]
    return {
        "logo_zone": _zone_near(text, [r"bbrose (?:logo|wordmark|lockup)",
                                       r"official .{0,20}logo"]),
        "name_zone": _zone_near(text, name_patterns),
        "motif_family": classify(text, "motif_family"),
        "field_structure": frozenset(
            device for device in _FIELD_DEVICES if device in text),
    }


def validate_variation_prompts(prompts, product_name: str = ""):
    """``(codes, features)`` for a three-prompt variation set."""
    features = [prompt_features(p.get("full_prompt", ""), product_name)
                for p in prompts]
    codes = []
    if len(features) != 3:
        return [VARIATION_DIVERSITY_UNREADABLE], features

    comparable_keys = ("logo_zone", "name_zone", "motif_family",
                       "field_structure")
    readable = [f for f in features
                if sum(1 for k in comparable_keys
                       if f[k] not in ("", "UNCLASSIFIED", frozenset())) >= 2]
    if len(readable) < 3:
        # a validator that cannot read the prompts cannot vouch for the set
        return [VARIATION_DIVERSITY_UNREADABLE], features

    for first in range(3):
        for second in range(first + 1, 3):
            differences = 0
            for key in comparable_keys:
                left, right = features[first][key], features[second][key]
                if "" in (left, right) or "UNCLASSIFIED" in (left, right):
                    continue
                if left != right:
                    differences += 1
            if differences < MIN_FEATURE_DIFFERENCES:
                codes.append(VARIATION_PROMPTS_NOT_DISTINCT)

    triples = {(f["motif_family"], f["logo_zone"], f["name_zone"])
               for f in features}
    if len(triples) == 1:
        codes.append(VARIATION_PROMPTS_NOT_DISTINCT)
    return sorted(set(codes)), features


__all__ = ["validate_variation_prompts", "prompt_features",
           "VARIATION_PROMPTS_NOT_DISTINCT", "VARIATION_DIVERSITY_UNREADABLE",
           "MIN_FEATURE_DIFFERENCES"]
