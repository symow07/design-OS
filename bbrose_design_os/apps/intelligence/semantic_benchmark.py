"""Search-quality benchmark — DIP-1C-3 (`intelligence_semantic_benchmark/1.0`).

A bounded, versioned set of representative reviewer queries used to compare lexical,
semantic and hybrid ranking. It measures **search quality only**. It approves nothing,
asserts nothing about any CorpusItem, and produces no authority.

**Relevance labels are category-level, and deliberately so.** No human has labelled
relevance for this corpus, so per-item ground truth does not exist. Inventing it would
fabricate evidence. Each query therefore states which *categories* (item kind, and where
the repository actually records one, a machine label) a reasonable reviewer would expect —
and each carries an explicit note about what must NOT be inferred from a hit.

Two measured properties of the live corpus constrain what this benchmark can honestly
expect, and are the reason several queries expect little or nothing:

* **Display labels are mostly not natural language.** Design assets are keyed by hex digest
  (`027f8369ea6df36c`); historical designs carry Chinese/SKU titles (`ES3083吸塑 展盒刀线`,
  `BL-2050 STAND`). Only font families are human-readable words.
* **Descriptive content is thin.** The semantic document is assembled from stable keys,
  enum labels, schema names and fact *types* — not prose descriptions of what a design
  depicts. Nothing in the corpus records that a motif is "floral" or a palette "feminine".

A query about visual content (floral, luxury, feminine) therefore has no evidential basis
to match anything, in either ranker. That is a property of the corpus, not a ranking bug,
and this benchmark records it rather than hiding it.
"""
from __future__ import annotations

import dataclasses

from .models import CorpusItem
from .search_contract import CAMPAIGN_SCOPE, CORPUS_SCOPE
from .semantic_query import (
    ASSET_METADATA, DESIGN_STYLE, FONT_METADATA, GENERAL_CONCEPT, PRODUCT_CATEGORY,
)

BENCHMARK_SCHEMA = "intelligence_semantic_benchmark/1.0"

# what a hit may never be taken to mean, on any query
_UNIVERSAL_NOTE = ("A hit is a discovery aid only: it implies no approval, rights "
                   "clearance, ownership, canonical status, or operational permission.")
_NO_VISUAL_BASIS = ("The corpus records no description of visual content. Nothing here "
                    "can establish that an item is floral/luxury/feminine/etc.; a hit "
                    "reflects label and metadata overlap only.")
_MACHINE_LABEL_NOTE = ("Machine classification labels are machine guesses, not human "
                       "truth, and never establish identity or lineage.")


@dataclasses.dataclass(frozen=True)
class BenchmarkQuery:
    query_id: str
    query_text: str
    facet: str
    scope: str
    # category-level expectations — never fabricated per-item ground truth
    expected_item_kinds: tuple[str, ...]
    expected_machine_labels: tuple[str, ...]
    prohibited_inference_notes: tuple[str, ...]
    minimum_success_criteria: str
    # set only where the repository itself gives documentary evidence
    expected_external_key_prefixes: tuple[str, ...] = ()
    expects_no_evidential_basis: bool = False

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def _q(query_id, text, facet, kinds, labels, criteria, *, scope=CORPUS_SCOPE,
       notes=(), prefixes=(), no_basis=False):
    return BenchmarkQuery(
        query_id=query_id, query_text=text, facet=facet, scope=scope,
        expected_item_kinds=tuple(kinds), expected_machine_labels=tuple(labels),
        prohibited_inference_notes=(_UNIVERSAL_NOTE,) + tuple(notes),
        minimum_success_criteria=criteria,
        expected_external_key_prefixes=tuple(prefixes),
        expects_no_evidential_basis=no_basis)


# --- the benchmark ---------------------------------------------------------------
BENCHMARK_QUERIES = (
    # === product / packaging concepts ============================================
    # Historical designs are titled with SKU/Chinese strings, and 14 of 20 carry an EMPTY
    # product-family label, so these queries test whether ANY channel can reach them.
    _q("Q01", "cosmetic packaging design", GENERAL_CONCEPT,
       ("HISTORICAL_DESIGN",), ("SURFACE_ARTWORK", "DIELINE_CANDIDATE"),
       "Returns historical design items; a hit must expose the item's readiness/blockers."),
    _q("Q02", "skincare packaging", PRODUCT_CATEGORY,
       ("HISTORICAL_DESIGN",), ("primer-skincare",),
       "At most one historical item carries a skincare machine label; expectation is "
       "category-level, not a count.",
       notes=(_MACHINE_LABEL_NOTE,)),
    _q("Q03", "lip colour product", PRODUCT_CATEGORY,
       ("HISTORICAL_DESIGN",), ("lip-colour",),
       "The single lip-colour machine-labelled historical item is reachable, or the "
       "result is honestly empty."),
    _q("Q04", "eye colour product", PRODUCT_CATEGORY,
       ("HISTORICAL_DESIGN",), ("eye-colour",),
       "The single eye-colour machine-labelled item is reachable, or honestly empty."),
    _q("Q05", "concealer", PRODUCT_CATEGORY,
       ("HISTORICAL_DESIGN",), ("concealer",),
       "The single concealer-labelled item is reachable, or honestly empty."),
    _q("Q06", "makeup compact", PRODUCT_CATEGORY,
       ("HISTORICAL_DESIGN",), ("makeup-compact",),
       "The single makeup-compact-labelled item is reachable, or honestly empty."),

    # === visual-content concepts — NO evidential basis in this corpus =============
    _q("Q07", "floral motif", DESIGN_STYLE,
       ("DESIGN_ASSET",), ("MOTIF",),
       "MOTIF-labelled assets may surface, but NOTHING records that any motif is floral. "
       "A confident 'floral' answer would be a fabrication.",
       notes=(_NO_VISUAL_BASIS, _MACHINE_LABEL_NOTE), no_basis=True),
    _q("Q08", "leaf motif", DESIGN_STYLE,
       ("DESIGN_ASSET",), ("MOTIF",),
       "As Q07: no leaf/plant description exists in the corpus.",
       notes=(_NO_VISUAL_BASIS, _MACHINE_LABEL_NOTE), no_basis=True),
    _q("Q09", "luxury elegant style", DESIGN_STYLE,
       ("DESIGN_ASSET", "HISTORICAL_DESIGN"), (),
       "No style vocabulary exists in the corpus; an empty or label-only result is the "
       "honest outcome.",
       notes=(_NO_VISUAL_BASIS,), no_basis=True),
    _q("Q10", "minimal clean design", DESIGN_STYLE,
       ("DESIGN_ASSET", "HISTORICAL_DESIGN"), (),
       "As Q09 — no style descriptors are recorded.",
       notes=(_NO_VISUAL_BASIS,), no_basis=True),
    _q("Q11", "soft pink feminine palette", DESIGN_STYLE,
       ("BRAND_PALETTE",), ("COLOR_PALETTE_STRIP", "PALETTE"),
       "The single palette candidate may surface by label; colour/feeling is NOT recorded "
       "and must not be claimed.",
       notes=(_NO_VISUAL_BASIS,), no_basis=True),
    _q("Q12", "modern geometric packaging", DESIGN_STYLE,
       ("DESIGN_ASSET", "HISTORICAL_DESIGN"), (),
       "No geometry/style vocabulary is recorded.",
       notes=(_NO_VISUAL_BASIS,), no_basis=True),

    # === asset metadata — labels DO exist here ===================================
    _q("Q13", "seamless pattern", ASSET_METADATA,
       ("DESIGN_ASSET",), ("PATTERN",),
       "PATTERN-labelled assets (34 recorded) are reachable. 'Seamless' is not recorded "
       "and must not be inferred.",
       notes=(_MACHINE_LABEL_NOTE,)),
    _q("Q14", "background texture", ASSET_METADATA,
       ("DESIGN_ASSET",), ("BACKGROUND",),
       "BACKGROUND-labelled assets (11 recorded) are reachable."),
    _q("Q15", "illustration asset", ASSET_METADATA,
       ("DESIGN_ASSET",), ("ILLUSTRATION",),
       "ILLUSTRATION-labelled assets (4 recorded) are reachable."),
    _q("Q16", "reusable design asset", ASSET_METADATA,
       ("DESIGN_ASSET",), ("CURATED_STARTER_CANDIDATE", "UNKNOWN_ASSET_TYPE"),
       "Design assets surface AND every curated asset shows RIGHTS_UNREVIEWED.",
       notes=("Reusability is a human decision; a hit never implies an asset is reusable.",)),
    _q("Q17", "curated asset expansion", ASSET_METADATA,
       ("DESIGN_ASSET",), ("CURATED_STARTER_CANDIDATE",),
       "Curated-lineage assets are reachable and remain rights-blocked."),

    # === fonts — the only human-readable labels in the corpus =====================
    _q("Q18", "serif font", FONT_METADATA,
       ("FONT",), (),
       "Font items surface. Serif-ness is NOT recorded in the semantic document "
       "(font_metadata carries family name + technical state only).",
       notes=("Font style classification is not present in the indexed document; a hit "
              "does not establish that a face is serif.",)),
    _q("Q19", "sans serif font", FONT_METADATA,
       ("FONT",), (),
       "As Q18 — style is not indexed."),
    _q("Q20", "arabic compatible font", FONT_METADATA,
       ("FONT",), (),
       "Script coverage is NOT in the semantic document, so Arabic support cannot be "
       "answered from the index. A family-name hit (e.g. an Arabic family) is lexical "
       "coincidence, not evidence of coverage.",
       notes=("Script coverage is recorded as an observed fact but is not carried into "
              "the semantic document; do not infer script support from a hit.",)),
    _q("Q21", "cjk chinese japanese font", FONT_METADATA,
       ("FONT",), (),
       "As Q20 — script coverage is not indexed."),
    _q("Q22", "demo trial font", FONT_METADATA,
       ("FONT",), (),
       "Font families whose recorded name contains 'demo' are reachable lexically. "
       "Licence status is NOT established by a name.",
       notes=("Possession is not a licence; a 'demo' name is a suspicion, not a finding.",)),

    # === brand / palette candidates ==============================================
    _q("Q23", "bbrose brand logo", GENERAL_CONCEPT,
       ("BRAND_ASSET",), ("BBROSE", "LOGO"),
       "Brand candidates surface AND every one remains identity-blocked.",
       notes=("A BBROSE label is not confirmed BBROSE ownership; brand identity stays "
              "unconfirmed.",)),
    _q("Q24", "third party logo atc jojia", GENERAL_CONCEPT,
       ("BRAND_ASSET",), ("ATC", "JOJIA"),
       "Third-party-labelled brand candidates surface and remain rights/identity blocked.",
       notes=("These are third-party restricted candidates; a hit never implies any right "
              "to use them.",)),
    _q("Q25", "brand colour palette candidate", GENERAL_CONCEPT,
       ("BRAND_PALETTE",), ("PALETTE", "PARTIAL_PARSE"),
       "The palette candidate surfaces and remains blocked from primary-palette "
       "governance."),

    # === historical memory / campaign scope ======================================
    _q("Q26", "historical design memory reference", GENERAL_CONCEPT,
       ("HISTORICAL_DESIGN",), ("SURFACE_ARTWORK",),
       "Historical items surface with rights NOT_APPLICABLE (reference memory, not reuse)."),
    _q("Q27", "dieline structure", ASSET_METADATA,
       ("HISTORICAL_DESIGN",), ("DIELINE_CANDIDATE",),
       "Dieline-candidate labelled items are reachable.",
       notes=(_MACHINE_LABEL_NOTE,)),
    _q("Q28", "campaign review candidate", GENERAL_CONCEPT,
       ("HISTORICAL_DESIGN", "DESIGN_ASSET", "FONT", "BRAND_ASSET", "BRAND_PALETTE"), (),
       "Campaign-scope search returns only the frozen 90 and each shows its wave.",
       scope=CAMPAIGN_SCOPE),

    # === exact-identity control queries ==========================================
    # These MUST keep working: they are the lexical strengths a semantic channel could
    # dilute, and they are the reason hybrid must not degrade exact matching.
    _q("Q29", "EXACT_STABLE_KEY_CONTROL", GENERAL_CONCEPT,
       ("DESIGN_ASSET",), (),
       "An exact stable-key query must rank its item first in lexical AND hybrid.",
       notes=("Control query: the query_text is replaced at run time with a real external "
              "key drawn from the live corpus.",)),
    _q("Q30", "EXACT_DISPLAY_LABEL_CONTROL", FONT_METADATA,
       ("FONT",), (),
       "An exact font-family query must rank that family first in lexical AND hybrid.",
       notes=("Control query: the query_text is replaced at run time with a real font "
              "family name drawn from the live corpus.",)),
)

# control queries whose text is bound to live corpus evidence at run time, rather than
# hard-coded — so the benchmark never asserts an ID that may not exist
CONTROL_QUERY_IDS = ("Q29", "Q30")


def validate_benchmark(queries=BENCHMARK_QUERIES):
    """The benchmark is itself a bounded contract: unique IDs, bounded facets/scopes."""
    from .search_contract import SEARCH_SCOPES
    from .semantic_query import SEMANTIC_FACETS
    ids = [q.query_id for q in queries]
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark query IDs must be unique")
    kinds = set(CorpusItem.Kind.values)
    for q in queries:
        if q.facet not in SEMANTIC_FACETS:
            raise ValueError(f"{q.query_id}: unbounded facet {q.facet!r}")
        if q.scope not in SEARCH_SCOPES:
            raise ValueError(f"{q.query_id}: unbounded scope {q.scope!r}")
        for kind in q.expected_item_kinds:
            if kind not in kinds:
                raise ValueError(f"{q.query_id}: unknown item kind {kind!r}")
        if not q.minimum_success_criteria.strip():
            raise ValueError(f"{q.query_id}: missing success criteria")
        if not q.prohibited_inference_notes:
            raise ValueError(f"{q.query_id}: missing prohibited-inference notes")
    return True


def benchmark_document():
    return {
        "schema_version": BENCHMARK_SCHEMA,
        "query_count": len(BENCHMARK_QUERIES),
        "relevance_labelling": "CATEGORY_LEVEL_ONLY_NO_HUMAN_GROUND_TRUTH",
        "queries": [q.as_dict() for q in BENCHMARK_QUERIES],
    }
