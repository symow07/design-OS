# DIP-1C-4A — Discriminative semantic documents and search-status performance

**Status:** implemented and verified. **No external provider call was made in this slice.**
No migration. Held for review and a new explicit transfer decision.

Two bounded objectives, both answering failures the DIP-1C-3 pilot measured:

1. produce embedding text that carries distinguishing evidence rather than repeated schema
   and workflow boilerplate;
2. remove the ~3.6-second full-corpus rebuild from every search-status check.

Nothing here proves semantic *quality* — no re-embed is authorized. This slice changes
document text/structure and search-status performance; whether embeddings actually separate
lip-colour from concealer is a claim only the next authorized pilot can make.

---

## 1. Why 1.1 failed — profile of the pilot documents

Deterministic profile of the 176 schema-1.1 embedding texts and the stored pilot vectors
(diagnostic use of existing vectors; no new calls):

* **~6.7 unique tokens per document** (median 6); **145 of 176 had ≤1 distinctive token**.
* **19 documents shared byte-identical embedding text** — 9 brand assets identical.
* Boilerplate: `DESIGN_ASSET` in 57% of documents; every historical document carried the
  same `HISTORICAL_DESIGN … CURATED_HISTORICAL_REFERENCE … READY_FOR_CLASSIFICATION` frame.
* Cosine within kind vs across kinds (stored pilot vectors):

  | kind | n | mean | max |
  |---|---:|---:|---:|
  | BRAND_ASSET | 21 | 0.877 | 1.000 |
  | DESIGN_ASSET | 100 | 0.846 | 0.999 |
  | FONT | 34 | 0.729 | 0.992 |
  | HISTORICAL_DESIGN | 20 | 0.695 | 0.976 |
  | **across all kinds** | 176 | **0.595** | 1.000 |

**The vectors encoded item *kind*, not topic.** Within-kind similarity (0.70–0.88) far
exceeds across-kind (0.595), and `max = 1.000` is the 9 identical brand texts. A query could
separate FONT from HISTORICAL but never lip-colour from concealer, because the shared
scaffolding dominated every vector and drowned the one distinguishing token. This is a
document-representation failure, and no ranker weight can fix near-identical vectors.

## 2. Schema `intelligence_semantic_document/1.2`

Schemas 1.0 and 1.1 are **left literally unchanged** (`semantic_document.py`); 1.2 is a new
module (`semantic_document_v12.py`). The contract separates two things 1.1 conflated:

* **Identity/filter metadata** — `corpus_item_id`, `external_key`, `item_kind`,
  `dataset_identifier`. For filtering, joining and audit. **Never enters the embedding
  text.**
* **Embedding text** — topical, differentiating evidence only, rendered from existing
  bounded facts through a frozen phrase vocabulary, plus per-term provenance in `channels`.

Fields: `metadata`, `channels`, `embedding_text`, `embedding_text_hash`.

## 3. Boilerplate removed from embedding text

Not encoded, though still available as metadata/filters elsewhere: schema identifier, stable
external key, UUID, dataset identifier, readiness state, blocker codes, permission state,
campaign wave, generic workflow vocabulary, and any phrase shared by most items. These are
identity and workflow, not topic, and they must not dominate vector similarity.

## 4. Controlled phrase vocabulary (frozen)

A presentation of existing facts, never new facts. Item kinds → e.g. `HISTORICAL_DESIGN` →
"historical cosmetics packaging design". Product families (machine-labelled) → e.g.
`LIP_COLOUR` → "lip color, lipstick, or lip gloss packaging". Scripts → e.g. `ARABIC` →
"font with Arabic script coverage". Asset categories, brand kinds, and a curated subset of
machine labels likewise. `UNKNOWN` asset kind yields **no** phrase — an unknown asset has no
topical evidence and inventing one would be fabrication. No phrase is derived from a
filename, path, directory, or archive name.

## 5. Embedding channels

`item_type_terms` · `product_family_terms` · `asset_category_terms` · `design_style_terms` ·
`font_family_terms` · `font_style_terms` · `script_coverage_terms` · `verified_human_terms` ·
`bounded_machine_terms`. Each term keeps a local provenance marker
(`TECHNICAL_OBSERVATION` / `MACHINE_CLASSIFICATION` / `VERIFIED_HUMAN_ASSERTION`) — machine
and human terms never share an unlabelled source. The transmitted embedding text is the
rendered phrases; the channel structure preserves provenance locally.

**Font style is read from actual recorded fields (`weight`, `italic`), not inferred from the
family name.** An early version matched name tokens and asserted "bold weight typeface" from
the brand name *gobold* — a claim the font never made. The corpus does not record serif vs
sans (DIP-0C4a: style tags are heuristic and human-reviewable), so anatomy is not asserted;
the family name itself lives in `font_family_terms`, so a serif-named face still matches by
its name without us claiming its shape. Demo/trial is matched on a word boundary and rendered
as a licensing *suspicion*, never a finding.

## 6. Deduplication and ordering

Fixed channel order; phrases deduplicated across the whole text; whitespace normalized;
empty channels omitted; stable text hash. No term is repeated to simulate weighting, and no
prompt-like prose or marketing copy is added.

## 7. Unsupported-concept honesty

The pilot showed semantic similarity manufacturing `luxury`/`minimal`/`geometric` over a
corpus that records none of them. A test asserts **our controlled vocabularies never
introduce** any of luxury, elegant, minimal, floral, feminine, geometric, premium, delicate.
The invariant is about what *we* assert: a font whose recorded family name is `gobold bold`
carries "bold" through `font_family_terms` — that is the item's own name, an existing fact,
not a claim we manufactured. No design is enriched with generic cosmetics adjectives to lift
a benchmark score.

## 8. Exact-identity search planner — `intelligence_search_planner/1.0`

Exact stable-key and exact safe-display-label matches are **identity operations, not
similarity**. The planner resolves them deterministically and **pins** the match to rank 1
in every mode (lexical, semantic, hybrid), with the reason `EXACT_IDENTITY_MATCH`. A pin is
an answer, not a weight a strong enough cosine can outvote — a test proves an item with
`match_score=1` is pinned ahead of one with `match_score=999999`, and **its score is not
inflated**. This fixes the pilot's Q29 failure without a hidden weight. Separately versioned;
`intelligence_hybrid_ranker/1.1` is untouched.

## 9. Semantic abstention gate — `semantic_evidence_gate/1.0`

Because every query has a vector and cosine ranks all 176 items, the pilot's semantic search
*always* returned ten confident results — including for concepts the corpus records nothing
about. The gate lets semantic return `SEMANTIC_NO_EVIDENTIAL_BASIS` with zero results
instead. It considers transparent measures (top score, median, spread, top-to-median and
top-to-second margins, item-kind/facet consistency) and **hard-codes no query id or benchmark
phrase** — structurally, its signature receives only scores and kinds, never the query text,
so it *cannot* special-case a phrase.

**Thresholds are DEFINED and MEASURED, NOT ACTIVATED.** `assess_semantic_evidence(...,
activate=False)` is the default: it measures without changing behaviour. Tuning cut-offs
against the same 30 benchmark queries they would be judged on is overfitting (§9), so
`DEFAULT_THRESHOLDS` are candidates for the next authorized pilot to evaluate and approve.

**Measured candidate behaviour on the stored pilot vectors** (illustrative, unactivated):
with `min_top_score=0.50`, `min_top_to_median_margin=0.08`, the candidate thresholds would
abstain on all 6 `expects_no_evidential_basis` queries — but also on ~23 of 30 overall,
including Q01's genuine rescue. That over-abstention is itself a finding: the margin was
computed against the median of the stored top-5 scores rather than the full 176-item
distribution, which understates it. This is exactly why the thresholds must be evaluated
against the full distribution in a real pilot before activation, not fitted here.

## 10. Search-status performance

Per §10, the ~3.6 s was `index_status()` rebuilding all 176 documents per request, each item
issuing its own readiness/governance/assertion queries — an N+1 defect, not a provider cost.

`semantic_corpus.CorpusSnapshot` builds the whole corpus in **one deterministic batch** with
bulk-loaded facts, classifications, family and script data: a **bounded query count
independent of corpus size** (pinned by `assertNumQueries` — same count at 3 items and at
12), constructed once per request, reused for hashing (0 further queries).

| | 1.1 per-request build | 1.2 snapshot |
|---|---:|---:|
| Build time (176 items) | **3.36 s** | **0.019 s** |
| Query growth per item | N+1 | none (bounded) |

Well under the §11 targets (status/hash < 500 ms; scan < 100 ms). No pgvector, no cache, no
migration, no approximate or time-based stale check.

**Staleness is corrected, not weakened.** The manifest now hashes the canonical id set plus
each document's **embedding-text hash**. That is exact with respect to what is actually
embedded: membership changes flip the id set, embedded-content changes flip the text hash.
A readiness/workflow transition correctly does *not* mark the index stale — none of it is
embedded in 1.2. Three tests pin this contract (membership → stale; embedded content →
stale; workflow churn → not stale).

## 11. Preview comparison (no external call)

| metric | 1.1 | 1.2 |
|---|---:|---:|
| documents | 176 | 176 |
| distinct embedding texts | 162 | **63** |
| documents in a duplicate group | 19 | **125** |
| mean / median / max text length | 126.9 / 118 / 204 | **58.2 / 49 / 186** |
| prohibited field / value findings | 0 / 0 | 0 / 0 |
| expected requests / ~tokens (if authorized) | 176 / ~5,600 | 176 / **~2,562** |

**Exact-duplicate text rose (19 → 125), and that is the honest, intended result.** Once the
hex `external_key` and SKU `display_label` leave the embedding text, items whose only
differentiator was an identifier become byte-identical — because, given the metadata that
exists, they *are* topically identical. The alternatives (re-adding the hash "for
uniqueness", or padding with generic adjectives) would reintroduce exactly the noise this
slice removes, and §7 forbids the adjectives. Topical duplication costs nothing for
retrieval because exact-identity lookup is handled by the planner (§8), not the embedding.
The manifest changed (`cde0f207…`), which correctly requires a new generation before any
re-embed.

## 12. Lexical and structural benchmark (no OpenAI)

Lexical unchanged: precision@10 **0.738**, 4 honest empties, exact-identity controls first,
RETRIEVAL/AUTOMATIC_USE **0**. Schema changes did not alter lexical search; unsupported-
concept queries remain honest lexical empties; campaign and permission state unchanged. The
stored 1.1 pilot vectors were used only for diagnostic comparison, never as evidence that 1.2
embeddings improved.

## 13. Ranker unchanged

`intelligence_hybrid_ranker/1.1` weights are untouched (asserted by test). A future explicit
`1.2` may be proposed after the next pilot measures schema-1.2 embeddings. The identity
planner and abstention gate are separately versioned and are not weight changes in disguise.

## 14. Pilot generation preserved

Generation `f88bd738-7d0f-4c5e-bc83-25e04482231a` is preserved (PUBLISHED, 176 embeddings) for
audit, reproducibility and before/after comparison. It is **not** re-embedded, deleted, or
rewritten. It remains explicitly experimental (`NEEDS_DOCUMENT_SCHEMA_TUNING`); lexical search
remains the default; operational retrieval and automatic use remain empty.

## 15. Verification

Schema-1.2 suite 38 · full Django **1228 passed**/1 skipped · tooling **1014** (repo root) ·
ruff clean (`apps/` + `tools/`) · **migration drift zero — no migration** · frozen dip0c
clean · materials unchanged · pilot generation preserved · **0 external requests** ·
DecisionEvent/Human/Governance/ALLOWED all **0** · campaign hash `cf178a…150bf` and partition
20/14/24/10/22 intact.

## Next transfer checkpoint

A schema-1.2 re-embed is **not** authorized. When proposed, the standard gate applies: fresh
dry-run preview, exact corpus/manifest hash confirmation, 0 prohibited field and 0 prohibited
value findings, and explicit `--apply --provider openai --confirm-external-data-transfer`
authorization. The next pilot should also evaluate and approve the abstention thresholds
against the full score distribution — not the fitted subset measured here.
