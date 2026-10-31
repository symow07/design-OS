# DIP-1C-4B — Evaluate the executable schema-1.2 semantic pilot

**Status:** build executed, benchmark evaluated, held for review.

**Outcome: `NEEDS_RANKER_TUNING`** (with abstention-gate activation as a required companion
decision). Schema-1.2 document tuning **worked** — it advanced the pilot past DIP-1C-3's
`NEEDS_DOCUMENT_SCHEMA_TUNING`: top-of-list relevance improved and previously buried items now
surface at rank 1. But hybrid still dilutes strong lexical results below rank 1, and semantic
still manufactures results for concepts the corpus lacks, so it is **not** accepted as the
default. A bounded search-quality pilot: it approved nothing and granted nothing. Operational
retrieval and automatic use remain **0**.

---

## 1. Authorized build

Executed exactly as authorized, after a **17/17 final pre-send check** matching the
authorized build identity (commit `7801328`, schema 1.2, provider openai, model
text-embedding-3-small, corpus hash `cde0f207…`, 176 docs, 0 excluded, 0/0 prohibited,
campaign `cf178a…150bf` + 20/14/24/10/22, no deprecated/test-only, pilot preserved,
command==service builder).

```
rebuild_intelligence_semantic_index --document-schema intelligence_semantic_document/1.2 \
    --apply --provider openai --confirm-external-data-transfer --publish
```

**External requests:** 176 document embeddings + 30 benchmark query embeddings = **206**.
Physical OpenAI requests: 176 (build, one input each) + 30 (queries) — no batching change.

## 2. Published generation

| Field | Value |
|---|---|
| Generation UUID | `e88b1468-00c5-436f-b6bd-6c972143fc46` |
| Provider / model / schema | openai / text-embedding-3-small / `intelligence_semantic_document/1.2` |
| Status / quality | **PUBLISHED** · not stale (`CURRENT`) · quality **PILOT_QUALITY_PENDING** |
| Documents / embedded | 176 / 176 |
| Vector dimension | 1536 (uniform), all finite |
| corpus_hash | `cde0f207e13979da8610a481538a8b2a387bb647f6273f3c095f75db74af5e0a` |
| embedding_text_manifest_hash | `3c42dfcd58dc32dc64cba8932070de495c7f058c9e976fe773ddacb07d9e10d3` |
| document_content_manifest_hash | `7570c7ecd990e941f5114bab9508d4715d242babd07978fc50952dd28419f85b` |

**Publication validation: 23/23 PASS** — every doc hash reconciles to the authorized
manifest; dimension uniform; finite; corpus hash matches; publication current.

**Prior pilot `f88bd738` (schema 1.1) is preserved and readable** — 176 embeddings, original
hashes/vectors, now **SUPERSEDED** (the normal publish lifecycle: publishing a new generation
supersedes the old). Not deleted, rewritten, relabelled, or recomputed with the new builder.

## 3. Results — lexical vs semantic vs hybrid

Frozen experiment: ranker `intelligence_hybrid_ranker/1.1` unchanged, planner
`intelligence_search_planner/1.0` applied to controls, evidence gate evaluation-only. No
setting was revised after seeing results.

| Metric | LEXICAL | SEMANTIC | HYBRID |
|---|---:|---:|---:|
| **precision@1** | 0.769 | **0.867** | **0.867** |
| precision@5 | **0.738** | 0.640 | 0.673 |
| precision@10 / category@k | **0.738** | 0.573 | 0.590 |
| semantic-group precision | **0.751** | 0.644 | 0.661 |
| empty / abstention rate | 13.3% | 0% | 0% |
| exact-identity controls first | 2/2 | **2/2** | **2/2** |
| controls via `EXACT_IDENTITY_MATCH` | 2/2 | **2/2** | **2/2** |
| RETRIEVAL / AUTOMATIC_USE allowed | 0 | 0 | 0 |

### The genuine advance (vs DIP-1C-3 schema 1.1)

**precision@1 rose 0.769 → 0.867**, and concretely, items that schema 1.1 buried now rank
**first**:

| Query | Lexical p@1 | Semantic p@1 (1.2) |
|---|---:|---:|
| Q03 lip colour product | 0.0 | **1.0** |
| Q04 eye colour product | 0.0 | **1.0** |
| Q15 illustration asset | 0.0 | **1.0** |

The single lip-colour and eye-colour historical designs — which schema 1.1 could not
distinguish from their 19 boilerplate-identical siblings — are now the **rank-1** result
under semantic. This is the discriminative-document work (DIP-1C-4A) paying off, and it is
the evidence that closes DIP-1C-3's `NEEDS_DOCUMENT_SCHEMA_TUNING`.

### The exact-identity planner fixed the DIP-1C-3 Q29 failure

In DIP-1C-3, semantic-only ranking failed Q29 (an exact stable key not returned first). Here
the planner pins both controls to rank 1 on **all three channels** with reason
`EXACT_IDENTITY_MATCH` — a pin, not an inflated score. Identity is preserved.

### The remaining defects

**Dilution below rank 1.** precision@5/@10 stay below lexical. Two contributors, separated
honestly:
* *Single-item-category ceiling.* Q03–Q06 target product families with **one** member each,
  so p@5 cannot exceed 0.2 by construction; semantic reaches p@1=1.0 and p@5=0.2 (the item is
  first, nothing else is relevant), while lexical returns fewer results and so scores a
  higher *ratio*. p@1 is the fair metric for these, and semantic wins it.
* *Genuine dilution.* Q02 (skincare) and the deeper ranks of the product-family queries pull
  in wrong-category siblings. Hybrid's `_SEMANTIC_WEIGHT=300` still lets a ~0.5 cosine
  outweigh lexical token scores, so hybrid tracks semantic rather than protecting lexical
  depth. This is the ranker-weighting limitation, addressable only by an explicit `1.2`.

**Manufacturing persists (gate needed).** All 6 `expects_no_evidential_basis` queries
returned 10 confident semantic results (0% abstention) — Q09/Q10/Q12 (luxury/minimal/
geometric) even scored p@1=1.0 against a corpus that records none of those concepts. Q11
(soft pink feminine palette) correctly stayed 0.0. The abstention gate is demonstrably needed
and demonstrably not yet safe to activate (below).

**No new rescue.** Q01 ("cosmetic packaging design") scored 0.0 on every channel here
(DIP-1C-3 saw a semantic rescue). The 1.2 historical documents lead with product-family and
item-type phrases, so the specific `SURFACE_ARTWORK`/`DIELINE_CANDIDATE`-labelled historicals
the query expects did not top the list — a benchmark-expectation nuance, not a regression in
capability.

## 4. Semantic-text groups

Schema 1.2 produces **63 distinct embedding texts across 176 items** (125 in duplicate-text
groups) — the honest consequence of removing identifiers, as accepted in DIP-1C-4A. Reported
at both levels: item precision and semantic-group precision (0.644 semantic / 0.661 hybrid).
Within a duplicate-text group the members share an identical vector and score; ordering among
them is the canonical-UUID **tie-break only** and is not a semantic preference. Blockers and
readiness remain per-CorpusItem; identities are never collapsed. The benchmark can reach the
correct semantic *group* even where it cannot rank members inside it — which is the ceiling
the group metric measures.

## 5. Evidence gate — evaluation-only, `INSUFFICIENT_THRESHOLD_EVIDENCE`

Candidate thresholds (`min_top_score=0.50`, `min_top_to_median_margin=0.08`) were assessed on
the returned top-10 score view captured during the authorized run: they would abstain on 4/6
no-basis queries **and** on 16 good queries (20/30 total) — over-abstaining, because a
top-10 margin understates the full-176-item margin. Assessing against the **full** score
distribution would require a separate embedding budget beyond the authorized 30, so it is not
done here.

**Gate conclusion: `INSUFFICIENT_THRESHOLD_EVIDENCE` — do NOT activate.** The next authorized
pilot should capture the full per-query distribution (within its embedding budget) and set
thresholds against it. The gate remains evaluation-only; no query id or phrase is
special-cased (structurally, it receives only scores).

## 6. Performance

| Step | Median |
|---|---:|
| CorpusSnapshot build (176) | **59 ms** (was 3.36 s in 1.1) |
| corpus-hash validation | 23 ms |
| index-status validation | 27 ms |
| local vector scan (176) | 93 ms |
| OpenAI query embedding | provider-bound, ~0.5–6 s (reported separately) |

All local steps are well under the DIP-1C-4A targets (status/hash < 500 ms; scan < 100 ms).
No N+1 (`assertNumQueries` pins a bounded count independent of corpus size); the semantic
corpus is built once per request; exact staleness verification is preserved. **Provider
latency is the dominant and irreducible cost and is reported separately, never hidden in an
aggregate.**

## 7. Acceptance outcome — `NEEDS_RANKER_TUNING`

Not accepted as default, and zero empty results is explicitly **not** treated as success. The
evidence:

* **Positive, real:** document-schema tuning worked — p@1 improved 0.769 → 0.867 and buried
  single-member categories now surface at rank 1; the planner preserves exact identity on all
  channels. This is a genuine advance over DIP-1C-3.
* **Blocking, real:** hybrid dilutes strong lexical results at p@5/@10 (ranker weighting), and
  semantic manufactures results for unsupported concepts (gate unactivated).

Both blockers have identified mechanisms that are **separate versioned decisions**, neither
taken here:
1. **Ranker `1.2`** — rebalance `_SEMANTIC_WEIGHT` so semantic breaks ties rather than
   dominating, validated before/after against this frozen benchmark. (`1.1` untouched.)
2. **Evidence-gate activation** — set and activate thresholds against the full score
   distribution, as its own implementation decision.

Recommended next action: **ACCEPT_WITH_ABSTENTION_GATE is the plausible destination**, but
only after (1) and (2) are evaluated with evidence. Until then the outcome is
`NEEDS_RANKER_TUNING` and lexical search remains the default.

## 8. Human evaluation artifact

`var/design_intelligence/dip1c4b/evaluation_sheet.{json,csv}` (git-ignored) — 412 rows
(30 queries × 3 channels × top 5), ratings `HIGHLY_RELEVANT`/`RELEVANT`/`PARTIALLY_RELEVANT`/
`NOT_RELEVANT`/`CANNOT_JUDGE`, never pre-filled. Search-quality feedback only: creates no
DecisionEvent, assertion, governance decision, or permission; outside the authority database;
no model, no migration.

## 9. Authority — unchanged

DecisionEvent **0 → 0** · HumanAssertionProjection **0** · GovernanceDecisionProjection **0** ·
ALLOWED OperationalPermissionProjection **0**. Campaign hash `cf178a…150bf` and partition
20/14/24/10/22 intact.

## 10. Verification

Full Django **1247 passed**/1 skipped · tooling **1014** (repo root) · ruff clean · **migration
drift zero — no migration** · system checks no issues · deploy only local `W009` · frozen
dip0c clean · materials unchanged · no vectors/DB/keys/texts committed (`var/` git-ignored).

## 11. Exclusions

No permission grant; no automatic-use/export/production activation; no ranker-weight change; no
gate activation; no benchmark-label change; no document-phrase tuning after results; no
learned/personalized ranking; no query history or analytics; no design generation; no legacy
cutover.
