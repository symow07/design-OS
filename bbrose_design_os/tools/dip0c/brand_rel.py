"""Brand relationship hypotheses (DIP-0C3a).

Every hypothesis carries **positive evidence AND contradictory evidence** — because
the honest answer here is usually "these two files sit in one folder and that tells
us almost nothing". A shared folder or a similar filename **never** proves a brand
relationship; it is recorded as supporting evidence and explicitly marked
non-decisive.

Human confirmation is always blank.
"""
from __future__ import annotations

from . import config as C
from . import phash

PARSER = f"{C.TOOL_NAME}.brand_rel/{C.TOOL_VERSION}"


def hypothesis(rel: str, *, positive: list[str], contradictory: list[str],
               confidence: float, tier: str) -> dict:
    if rel not in C.BRAND_RELATIONSHIPS:
        raise ValueError(f"unknown brand relationship: {rel!r}")
    return {
        "relationship": rel,
        "positive_evidence": list(positive),
        "contradictory_evidence": list(contradictory),
        "confidence": round(float(confidence), 3),
        "capability_tier": tier,
        "human_confirmed": None,          # never machine-set
    }


def compare(a: dict, b: dict) -> dict | None:
    """`a`/`b` are brand.audit records. Returns an edge, or None."""
    hyps: list[dict] = []
    same_folder = a["source_package"] == b["source_package"]
    a_tp = a.get("detected_third_party_brand", {}).get("value")
    b_tp = b.get("detected_third_party_brand", {}).get("value")
    a_name = a.get("brand_name", {}).get("value")
    b_name = b.get("brand_name", {}).get("value")

    # NOTE: POSSIBLE_THIRD_PARTY_ASSET is a property of a FILE, not of a pair. It is
    # recorded once on the record (brand.audit) and is NOT emitted per pair — doing
    # so produced 119 near-identical "hypotheses" that said nothing about the pair.

    # --- same brand? only when BOTH names were read directly from live text ---
    if a_name and b_name:
        if a_name.strip().upper() == b_name.strip().upper():
            hyps.append(hypothesis(
                C.BR_SAME_BRAND_VARIANT,
                positive=[f"both wordmarks read DIRECTLY from live text as "
                          f"{a_name!r}"],
                contradictory=(["both are third-party — the shared brand is NOT "
                                "BBROSE"] if (a_tp and b_tp) else []),
                confidence=0.75, tier=C.TIER_DIRECT))
        else:
            hyps.append(hypothesis(
                C.BR_UNKNOWN,
                positive=["both wordmarks are directly readable"],
                contradictory=[f"and they DIFFER: {a_name!r} vs {b_name!r} — this "
                               "is evidence AGAINST a brand relationship"],
                confidence=0.3, tier=C.TIER_DIRECT))

    # --- lockup / colour variants: only between two ISOLATED LOGOS -----------
    a_iso = (a.get("isolated_logo_likelihood") or {}).get("value")
    b_iso = (b.get("isolated_logo_likelihood") or {}).get("value")
    if a_iso and b_iso:
        pa, pb = a.get("path_count", 0), b.get("path_count", 0)
        if pa and pb and max(pa, pb) / max(min(pa, pb), 1) >= 3:
            hyps.append(hypothesis(
                C.BR_POSSIBLE_LOCKUP_VARIANT,
                positive=[f"two isolated marks whose geometry differs sharply "
                          f"({pa} vs {pb} paths) — consistent with a symbol vs a "
                          "full lockup"],
                contradictory=["path count alone does not establish a lockup; the "
                               "marks were NOT visually matched, and they may "
                               "simply be different logos"],
                confidence=0.3, tier=C.TIER_HEURISTIC))
        spa, spb = set(a.get("spot_colors") or []), set(b.get("spot_colors") or [])
        if spa and spb and spa != spb:
            hyps.append(hypothesis(
                C.BR_POSSIBLE_COLOR_VARIANT,
                positive=[f"different named spot inks: {sorted(spa)} vs "
                          f"{sorted(spb)}"],
                contradictory=["different inks may equally mean different artwork"],
                confidence=0.3, tier=C.TIER_HEURISTIC))

    # --- product variant: a BBROSE-named render beside an isolated mark ------
    a_render = a["c3_test_role"] in ("bbrose_product_render",
                                     "bbrose_palette_raster")
    b_render = b["c3_test_role"] in ("bbrose_product_render",
                                     "bbrose_palette_raster")
    if a_render != b_render and (a_iso or b_iso):
        hyps.append(hypothesis(
            C.BR_POSSIBLE_PRODUCT_VARIANT,
            positive=["one side is a BBROSE-named raster render and the other is "
                      "an isolated vector mark — the render may DEPICT the mark"],
            contradictory=["no visual match was performed; a render is "
                           "PRODUCT_REFERENCE and can NEVER be a canonical master"],
            confidence=0.25, tier=C.TIER_HEURISTIC))

    if not hyps:
        if not same_folder:
            return None
        hyps.append(hypothesis(
            C.BR_UNKNOWN,
            positive=["the two files share a folder"],
            contradictory=[
                "a shared folder NEVER proves a brand relationship — three of the "
                "five vector logos in this folder are third-party"],
            confidence=0.1, tier=C.TIER_HEURISTIC))

    return {
        "a": a["relative_path"],
        "b": b["relative_path"],
        "hypotheses": hyps,
        "primary": max(hyps, key=lambda h: h["confidence"])["relationship"],
        "confidence": round(max(h["confidence"] for h in hyps), 3),
        "shared_folder": same_folder,
        "shared_folder_is_decisive": False,
        "human_confirmed_relationship": None,
        "parser": PARSER,
        "config_fingerprint": phash.CONFIG_FP,
    }


def build(records: list[dict]) -> list[dict]:
    """Brand relationships are proposed ONLY between BRAND assets.

    The Queue-I reusable assets (a baby-pattern, a background, a sticker sheet) are
    in the pilot because they are rights-blocked, not because they are brand
    material. Comparing a baby-pattern with a logo produced 184 edges of noise.
    """
    from .brand import BRAND_ROLES
    brand_records = [r for r in records if r["c3_test_role"] in BRAND_ROLES]
    edges = []
    for i, a in enumerate(brand_records):
        for b in brand_records[i + 1:]:
            e = compare(a, b)
            if e:
                edges.append(e)
    return edges
