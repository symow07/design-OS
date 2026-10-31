# DIP-1C-3 — Production semantic index pilot and search-quality evaluation

**Status:** pilot executed and evaluated. Held for review.

**Outcome: `NEEDS_DOCUMENT_SCHEMA_TUNING`** (with ranker tuning required as a secondary
mitigation). **Semantic ranking did not improve reviewer discovery on this corpus.** The
frozen ranker was evaluated as-is and **not** tuned.

This was a bounded search-quality pilot. It approved nothing, authorized nothing, and
granted nothing. Operational retrieval and automatic use remain **0**.

---

## 1. Transfer boundary and authorization

One bounded document-index build was executed under explicit authorization, after a
**final pre-send check where all 10 conditions matched the approved values exactly**:

| Condition | Approved | Observed |
|---|---|---|
| Schema | `intelligence_semantic_document/1.1` | ✅ match |
| Provider / model | `openai` / `text-embedding-3-small` | ✅ match |
| Corpus hash | `913a8e32…bb82d5` | ✅ match |
| Documents | 176 | ✅ 176 |
| Exclusions | 0 | ✅ 0 |
| Prohibited **field** findings | 0 | ✅ 0 |
| Prohibited **value** findings | 0 | ✅ 0 |

Command executed, exactly as authorized:

```
python manage.py rebuild_intelligence_semantic_index \
    --apply --provider openai --confirm-external-data-transfer --publish
```

**External requests: 176** (document embeddings) **+ 30** (benchmark query embeddings) =
**206 total**. Only the bounded `intelligence_semantic_document/1.1` and, for queries, the
normalized phrase + facet were transmitted. No paths, filenames, locators, binaries,
secrets, reviewer identity, DecisionEvent content, or licence text. No document text,
vectors, keys, or raw provider responses were logged or committed.

## 2. Published generation

| Field | Value |
|---|---|
| Generation ID | `f88bd738-7d0f-4c5e-bc83-25e04482231a` |
| Provider / model | `openai` / `text-embedding-3-small` |
| Document schema | `intelligence_semantic_document/1.1` |
| Index schema | `intelligence_semantic_index/1.0` |
| Status | **PUBLISHED** · not stale (`CURRENT`) |
| Documents / embedded / requests | 176 / 176 / 176 |
| Vector dimension | 1536 (uniform) |
| Corpus hash | `913a8e32b79b8a3141a4bdaafd1f4f6415166c443a5eef4212813a79a9bb82d5` |
| Invoked by | `operator:authorized-dip1c3` |
| Failure summary | *(empty)* |

**Post-build validation: 19/19 PASS** — one current production generation; provider/model
exact; PUBLISHED; 176 embeddings; uniform 1536 dimension; all vectors finite; all document
and vector hashes present; corpus hash matches the approved value; publication current;
deprecated and test-only identities absent; campaign hash `cf178a…150bf` and partition
20/14/24/10/22 unchanged; DecisionEvent/Human/Governance **0**; ALLOWED permissions **0**.

## 3. Benchmark

`intelligence_semantic_benchmark/1.0` — 30 queries across all requested categories, plus two
exact-identity controls bound to live corpus evidence at run time. **Relevance labels are
category-level only**: no human has labelled this corpus, so per-item ground truth does not
exist and inventing it would fabricate evidence. Expectations were **not** changed after
seeing results.

## 4. Results — lexical vs semantic vs hybrid

| Channel | Empty rate | Mean category precision@10 | Exact-identity controls |
|---|---:|---:|---:|
| **LEXICAL** (baseline) | 13.3% (4/30) | **0.738** | **2 / 2** |
| **SEMANTIC** | 0% | **0.517** | **1 / 2** ❌ |
| **HYBRID** (`intelligence_hybrid_ranker/1.1`) | 0% | **0.533** | **2 / 2** |

**Semantic ranking is materially worse than lexical at surfacing the right category, and
semantic-only breaks an exact-identity control.**

### Exact-match preservation

**Q29 (exact stable key) fails under SEMANTIC** — the exact-key item is not ranked first.
Hybrid preserves it (lexical's `EXACT_STABLE_KEY_MATCH` weight of 1000 dominates the blend).
This is precisely the dilution risk hybrid exists to prevent, and it argues against ever
exposing semantic-only ranking for identity lookups.

### Genuine rescue

**Q01 "cosmetic packaging design": lexical 0 results → semantic returns 10, all
`HISTORICAL_DESIGN`** (cosine 0.42–0.48), with retrieval still `False`. This is the one real
rescue: historical designs carry Chinese/SKU titles, so English lexical overlap is nil, and
embeddings bridge that. It is worth something.

### The "rescues" that are not rescues

Q09 (`luxury elegant style`), Q10 (`minimal clean design`), Q12 (`modern geometric
packaging`) went from lexical-empty to 10 semantic results with precision 0.8/0.1/0.9 — but
these are the **`expects_no_evidential_basis`** queries. **Nothing in the corpus records that
anything is luxury, minimal, or geometric.** Cosine ranks all 176 items and always returns
the top 10, so semantic manufactures an answer where the honest answer is "nothing matches".
The apparent precision is an artifact of those queries expecting a broad item kind.

**Semantic's 0% empty rate is therefore not a virtue — it is the finding.** Lexical's four
honest empties are more truthful than ten confidently-ranked non-answers.

### Dilution

Semantic degraded precision on **10 of 30** queries, several severely:

| Query | Lexical | Semantic |
|---|---:|---:|
| Q16 reusable design asset | 1.0 | **0.0** |
| Q02 skincare packaging | 1.0 | 0.1 |
| Q05 concealer | 1.0 | 0.1 |
| Q06 makeup compact | 1.0 | 0.1 |
| Q26 historical design memory | 0.8 | 0.4 |
| Q13 seamless pattern | 1.0 | 0.7 |
| Q14 background texture | 1.0 | 0.8 |

Only Q15 (`illustration asset`, 0.2 → 0.4) improved. Fonts (Q18–Q22) scored 1.0 on every
channel — but that is non-discriminating: those queries expect item kind `FONT` and every
returned item is a font.

### Why — the root cause

Q03 `lip colour product` is diagnostic. Exactly one lip-colour item exists, and its entire
document is:

```
HISTORICAL_DESIGN LIP_COLOUR CURATED_HISTORICAL_REFERENCE lip-colour READY_FOR_CLASSIFICATION
```

All 20 historical documents share the `HISTORICAL_DESIGN … CURATED_HISTORICAL_REFERENCE …
READY_FOR_CLASSIFICATION` boilerplate. **The shared enum scaffolding dominates the embedding
and drowns the one distinguishing token.** Semantic precision on that query is 0.1 — it finds
the item, but nine near-identical siblings rank alongside it. This is a document-design
problem, not a weight problem: no ranker weight can separate vectors that are nearly
identical by construction.

Hybrid's degradation *is* partly a weight artifact — `_SEMANTIC_WEIGHT = 300` against a
cosine of ~0.4 yields ~120, which overwhelms typical lexical token scores of 40–200, so
semantic dominates every non-exact query. But lowering the weight would only limit the
damage; it would not make these vectors informative.

### Latency

| Step | Time |
|---|---|
| Query embed (incl. OpenAI round-trip) | ~0.5–6.3 s |
| `corpus_manifest_hash` (rebuilds all 176 documents) | **3.6 s** |
| Mean per-search, observed | **8.7 s** |

**Not acceptable for an interactive reviewer workflow.** The dominant cost is *not* the
provider: `index_status()` recomputes the corpus manifest — rebuilding all 176 semantic
documents — on **every search**. That is a fixable engineering defect, reported rather than
silently patched here.

### Safety behaviour (all held)

Blocked candidates stayed visibly blocked with their blockers; brand and palette candidates
remained identity/rights blocked; **RETRIEVAL and AUTOMATIC_USE returned 0 on every channel
across all 30 queries**; provider failures fail closed to a bounded code (tested).

**No statistical significance is claimed.** Thirty queries with category-level labels and no
human ground truth support directional observation only.

## 5. Acceptance criteria

| Criterion | Result |
|---|---|
| Semantic/hybrid improves precision on a majority of non-exact queries | ❌ **No** — degraded 10, improved 1 |
| Semantic rescues queries with weak lexical overlap | ⚠️ **Partially** — Q01 genuine; Q09/Q10/Q12 are false rescues on baseless queries |
| Exact stable-key and exact-label searches remain correct | ✅ lexical, ✅ hybrid, ❌ **semantic (Q29)** |
| Hybrid does not materially degrade exact-match precision | ✅ controls preserved, ❌ category precision 0.738 → 0.533 |
| Blocked candidates remain visibly blocked | ✅ |
| Permissions remain zero | ✅ |
| No prohibited data transferred | ✅ |
| Latency acceptable for internal reviewer workflow | ❌ **8.7 s/search** |
| Provider errors fail safely | ✅ |

## 6. Outcome — `NEEDS_DOCUMENT_SCHEMA_TUNING`

The encoder is not obviously at fault and is **not** rejected: `text-embedding-3-small`
behaved exactly as one would expect given near-identical enum-shaped inputs. The documents
are the binding constraint — shared boilerplate dominates the signal, and no descriptive
content exists to embed.

`NEEDS_RANKER_TUNING` is a real but **secondary** finding: weight 300 lets a weak semantic
signal overwhelm a strong lexical one. Fixing the weight would reduce harm without adding
value, so it should follow, not precede, document work.

**`intelligence_hybrid_ranker/1.1` was NOT modified.** Evidence for a future explicit `1.2`
(proposed, not implemented): lower `_SEMANTIC_WEIGHT` so semantic breaks ties rather than
dominating; validate against this frozen benchmark; preserve 1.1.

**Recommended before any re-run:** reduce per-document boilerplate so distinguishing tokens
carry weight; add descriptive content only from safe reviewed sources (never invented, never
from filenames); consider embedding a distinguishing-field subset rather than the whole flat
string; fix `index_status()` manifest recomputation. Then re-evaluate against the same frozen
benchmark.

## 7. Staleness

An index becomes stale when corpus membership changes, semantic-document content changes,
included human assertions change, provider/model changes, document schema changes, or
canonical identity changes — all captured by `corpus_manifest_hash` plus encoder and schema
identity. Status is `UNAVAILABLE` / `CURRENT` / `STALE`. **Never rebuilt automatically**, and
never during a browser request. Operational retrieval filters by permission regardless of
index freshness.

## 8. Human evaluation artifact

`var/design_intelligence/dip1c3/evaluation_sheet.{json,csv}` (git-ignored) — **412 rows**
(30 queries × 3 channels × top 5), rating vocabulary `HIGHLY_RELEVANT` / `RELEVANT` /
`PARTIALLY_RELEVANT` / `NOT_RELEVANT` / `CANNOT_JUDGE`, never pre-filled.

**Search-quality feedback only.** A rating judges whether *search* surfaced something
useful. It is not a CorpusItem assertion, not approval, not rights clearance, not a
governance selection, not a permission, and creates no DecisionEvent. It is a local
artifact **outside the authority database** — no model, no migration, no table.

## 9. Privacy boundary

Transmitted: the bounded 1.1 document (176) and the normalized query phrase + facet (30).
Never transmitted: source binaries, images, Illustrator files, fonts, archive contents,
paths, filenames, source-location observations, evidence locators, secrets, keys, HMAC
material, DecisionEvent payloads, authorization snapshots, reviewer identity, licence text.
Raw queries and query vectors are not persisted or logged. No vectors or transmitted
documents are committed to Git.

## 10. Authority — unchanged

DecisionEvent **0 → 0** · HumanAssertionProjection **0** · GovernanceDecisionProjection
**0** · ALLOWED OperationalPermissionProjection **0**. Campaign hash `cf178a…150bf` and
partition 20/14/24/10/22 intact.

## 11. Exclusions

No permission grants; no automatic-use/export/production activation; no learned or
personalized ranking; no saved queries; no query analytics or history; no generative
reranking; no image embeddings; no automatic asset/font selection; no design generation; no
legacy pipeline cutover; no ranker tuning; no migration.
