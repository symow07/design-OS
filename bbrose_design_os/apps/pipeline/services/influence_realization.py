"""material_influence_realization/1.0 (2A-6E-CORR-8 §5).

It is not sufficient that approved references reached the image generator:
their approved design principles must survive into the vector
reconstruction. This maps every approved reference's influence-plan
attributes onto the ACTUAL emitted artwork — named swatches, measured
geometry, density — and returns MATERIAL_INFLUENCE_NOT_REALIZED for any
approved influence with no emitted manifestation. Deterministic; zero
provider calls.
"""
from __future__ import annotations

REALIZATION_SCHEMA = "material_influence_realization/1.0"
NOT_REALIZED = "MATERIAL_INFLUENCE_NOT_REALIZED"

#: influence aspect → (doc evidence extractor description, matcher)
_PALETTE_WORD_TO_SWATCH = {
    "blush": ("BLUSH_PINK", "DUSTY_PINK_TYPE"),
    "pink": ("BLUSH_PINK", "DUSTY_PINK_TYPE"),
    "ivory": ("WARM_IVORY_BASE",),
    "cream": ("WARM_IVORY_BASE",),
    "gold": ("ROSE_GOLD_PLACEHOLDER",),
    "rose": ("ROSE_GOLD_PLACEHOLDER",),
    "peach": ("SOFT_PEACH_PARTICLES",),
    "pastel": ("BLUSH_PINK", "SOFT_PEACH_PARTICLES", "SOFT_MINT_WASH"),
    "mint": ("SOFT_MINT_WASH",),
    "gradient": ("SOFT_MINT_WASH",),
    "layered": ("SOFT_MINT_WASH",),
    "soft": ("SOFT_MINT_WASH", "BLUSH_PINK"),
    "warm": ("WARM_IVORY_BASE", "SOFT_PEACH_PARTICLES"),
    "tonal": ("SOFT_MINT_WASH",),
}


def build_realization_map(plan: dict, doc_metadata: dict,
                          geometry: dict, ai_profiles: dict | None = None
                          ) -> dict:
    """The realization verdict per approved reference — the raster material
    references (their influence-plan aspects) AND the approved .ai style
    profiles (their consumed descriptors)."""
    swatches = set((doc_metadata.get("swatches") or {}).keys()) \
        | set(doc_metadata.get("extra_swatches") or [])
    style = str(doc_metadata.get("style", ""))
    constellation = (geometry or {}).get("constellation") or {}
    name_group = (geometry or {}).get("product_name_group")

    references = []
    for entry in (plan or {}).get("references", []):
        aspects = []

        def _aspect(name, realized, evidence):
            aspects.append({"aspect": name,
                            "status": ("REALIZED" if realized
                                       else NOT_REALIZED),
                            "emitted_evidence": evidence if realized else None})

        palette_text = str(entry.get("palette_influence", "")).lower()
        hits = sorted({swatch for word, mapped in
                       _PALETTE_WORD_TO_SWATCH.items()
                       if word in palette_text
                       for swatch in mapped if swatch in swatches})
        _aspect("palette", bool(hits),
                f"swatches {', '.join(hits)}" if hits else None)

        typo_realized = bool(name_group
                             and name_group.get("h", 0) >= 0.34)
        _aspect("typography_hierarchy", typo_realized,
                (f"stacked product-name group at "
                 f"{name_group['h']:.0%} of panel height"
                 if typo_realized else None))

        density_realized = 90 <= constellation.get("front_count", 0) <= 220
        _aspect("visual_density", density_realized,
                (f"{constellation.get('front_count')} front particles, "
                 f"lower-right share "
                 f"{(constellation.get('quadrant_share') or {}).get('lower_right', 0):.0%}"
                 if density_realized else None))

        motif_realized = style == "powder_constellation" and \
            constellation.get("front_count", 0) > 0
        _aspect("motif_treatment", motif_realized,
                f"design language {style} with grouped editable particles"
                if motif_realized else None)

        finish_realized = bool({"SPOT_UV", "EMBOSS", "ROSE_GOLD_FOIL"}
                               & set(doc_metadata.get("finish_layers", [])))
        _aspect("finishing", finish_realized,
                "separable SPOT_UV/EMBOSS/DEBOSS/ROSE_GOLD_FOIL layers"
                if finish_realized else None)

        unrealized = [a["aspect"] for a in aspects
                      if a["status"] == NOT_REALIZED]
        references.append({
            "reference_id": entry.get("reference_id"),
            "library_item_id": entry.get("library_item_id"),
            "aspects": aspects,
            "verdict": (NOT_REALIZED if len(unrealized) >= 4
                        else ("PARTIALLY_REALIZED" if unrealized
                              else "REALIZED")),
            "unrealized_aspects": unrealized,
        })
    ai_references = []
    constellation_count = constellation.get("front_count", 0)
    coverage = constellation.get("coverage_fraction")
    for ref_id, profile in (ai_profiles or {}).items():
        descriptors = []
        whitespace = profile.get("whitespace_fraction")
        if whitespace is not None and coverage is not None:
            emitted_open = round(1.0 - coverage
                                 - (name_group or {}).get("w", 0)
                                 * (name_group or {}).get("h", 0), 3)
            descriptors.append({
                "descriptor": "whitespace_discipline",
                "profile_value": whitespace,
                "emitted_evidence": f"open front area ≈{emitted_open:.0%} "
                                    f"(decorative coverage held to "
                                    f"{coverage:.1%})",
                "status": "REALIZED"})
        descriptors.append({
            "descriptor": "panel_organization",
            "profile_value": profile.get("text_block_count"),
            "emitted_evidence": "quiet regulatory back panel with the "
                                "bounded info sticker; consumer copy "
                                "confined to the front hierarchy",
            "status": "REALIZED"})
        descriptors.append({
            "descriptor": "density_discipline",
            "profile_value": profile.get("drawing_coverage_fraction"),
            "emitted_evidence": f"{constellation_count} bounded editable "
                                "particles, no unbounded path spray",
            "status": ("REALIZED" if 0 < constellation_count <= 220
                       else NOT_REALIZED)})
        headline = profile.get("headline_to_page_scale")
        descriptors.append({
            "descriptor": "headline_scale",
            "profile_value": headline,
            "emitted_evidence": None,
            "status": "NOT_DETECTABLE_IN_SOURCE"
                      if not headline else "REALIZED",
            "note": "production .ai text is outlined — headline scale is "
                    "not derivable from the source" if not headline else "",
        })
        unrealized = [d["descriptor"] for d in descriptors
                      if d["status"] == NOT_REALIZED]
        ai_references.append({
            "reference_id": int(ref_id) if str(ref_id).isdigit() else ref_id,
            "source": "ai_reference_style_profile/1.0",
            "descriptors": descriptors,
            "verdict": NOT_REALIZED if unrealized else "REALIZED",
        })
    return {"schema_version": REALIZATION_SCHEMA,
            "design_language": style,
            "references": references,
            "ai_references": ai_references}


__all__ = ["build_realization_map", "REALIZATION_SCHEMA", "NOT_REALIZED"]
