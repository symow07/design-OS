# DIP-1C-2 — Controlled query embedding and interactive reviewer semantic search

**Status:** implemented and verified. Held for review.

Makes semantic search genuinely usable to an authenticated reviewer, without introducing
automatic external calls or any operational-use authority. **No migration** — interactive
query embeddings are transient and are never persisted.

> **SEMANTIC SIMILARITY DOES NOT AUTHORIZE OPERATIONAL USE.**
> Similarity is ordering. Permission is authority. Retrieval and automatic use remain **0**.

This is the first outbound call in the intelligence line that originates from a web request,
so the whole slice is built around one seam: **embedding is separated from ranking.**
`encode_semantic_query` is the only code that can call out, and it is POST-only and
consent-gated; `execute_search` stays a pure function that merely accepts a vector. Every
GET therefore behaves exactly as in DIP-1C-1.

---

## 1. Query contract — `intelligence_semantic_query/1.0`

`apps/intelligence/semantic_query.py`. A closed vocabulary; anything unrecognised is refused,
never approximated.

**Allowed fields:** `query_text` · `facet` · `item_kinds` · `dataset_identifiers` · `scope` ·
`limit` · `generation_id` · `expected_corpus_hash` · `confirm_external_query_transfer`.

**Query constraints:** non-empty after NFKC normalization · ≤200 characters · ≤40 tokens · no
control characters · **no filesystem paths** (a path is never a legitimate semantic phrase) ·
no arbitrary JSON · no executable filter expressions · no unknown fields.

A subtle bug found and fixed during verification: `raw.get("limit") or 25` silently turned an
invalid `limit=0` into the default, because `0` is falsy. It now uses an explicit `None`/`""`
check, so an invalid limit is **refused** rather than quietly replaced.

## 2. Exactly what is transmitted

`SemanticQuery.transmitted_payload()` is the whole external surface:

```
{"query_text": "<the reviewer's normalized phrase>", "facet": "<bounded facet label>"}
```

sent as `"<FACET>: <phrase>"`. Nothing else. **Corpus records are not re-sent per query** —
those were embedded once, offline, in DIP-1C-1.

**Never sent:** source binaries · images · Illustrator files · fonts · archive contents ·
absolute or relative paths · source-location observations · EvidenceReference locators ·
secrets · API keys · HMAC material · DecisionEvent payloads · authorization snapshots ·
reviewer identity or usernames · licence text · acquisition documents · unrestricted raw
values · personal information · legacy authority signals.

## 3. Consent — explicit, and per request

`confirm_external_query_transfer` must be true on **every** semantic request. It is unchecked
by default, cannot be inferred from a prior GET, and has no hidden default. Accepting the
offline document-index build is **not** standing consent for arbitrary future queries — a
test asserts a second query without confirmation is refused even immediately after a
confirmed one.

The UI states verbatim: *"This query text will be sent to OpenAI to calculate an embedding.
No source files, images, evidence documents, paths, secrets, reviewer identity, or
DecisionEvent data will be sent."*

Defence is layered: the contract records consent, `encode_semantic_query` refuses without it
**before constructing an encoder**, and `OpenAIEncoder` itself cannot be constructed without
the confirmation flag.

## 4. HTTP, CSRF, and actor identity

| Route | Method | External call |
|---|---|---|
| `/intelligence/search/` | GET | **never** |
| `/intelligence/search/semantic/` | POST | only after all gates pass |

A **separate POST endpoint** keeps `/search/` strictly GET-only, so loading a page or applying
filters can never transmit anything. The POST view requires the canonical
`VIEW_INTELLIGENCE_REVIEW_QUEUE` action (no second identity system), enforces CSRF, and derives
the actor **server-side from the session** — a role, actor, or authority claim in the request
body is never read (tested: an OBSERVER claiming `SYSTEM_ADMIN` in the body is still denied).

## 5. Pre-call gates — each a distinct bounded code

Checked in order, all **before** any external call, so a rejected request never reaches the
provider:

| Code | Meaning |
|---|---|
| `SEMANTIC_INDEX_UNAVAILABLE` | no published production index |
| `SEMANTIC_INDEX_STALE` | index no longer matches the corpus — fails closed **before** embedding, never ranks a fresh query against stale documents |
| `MODEL_MISMATCH` | published index built with a different provider/model, so vectors would not be comparable |
| `GENERATION_MISMATCH` / `CORPUS_HASH_MISMATCH` | caller's expectations disagree with the live index |
| `EXTERNAL_TRANSFER_NOT_CONFIRMED` | per-request consent absent |
| `PROVIDER_CONFIGURATION_MISSING` | key absent — fails closed without inspecting or printing it |
| `PROVIDER_ERROR` | provider call failed; bounded code only, raw response never surfaced |
| `DIMENSION_MISMATCH` | returned embedding had the wrong dimension and was discarded |

A provider failure leaves the published index untouched, creates no partial generation, and
never degrades into semantic-looking lexical results.

## 6. Query encoder service

`encode_semantic_query(query) -> QueryEmbeddingResult` validates the contract, verifies the
published index and provider/model/dimension compatibility, requires consent, embeds via
`text-embedding-3-small`, validates finiteness and exact dimension, and returns the vector for
immediate use. The model and provider are never silently changed; a published index built with
another provider/model refuses the query vector.

## 7. Query retention — nothing is kept

**Not persisted:** raw query text · query embedding · search history · analytics ·
DecisionEvent. There is no query-history, consent-history, or query-vector table, and §16's
"prefer no migration" is satisfied — `makemigrations --check` reports no changes.

`QueryEmbeddingResult` carries only bounded, non-sensitive metadata: provider, model,
generation id, dimension, `query_char_count`, and a failure category. **Never logged:** raw
query text, query vector, API key, full provider response, reviewer session identifiers, or
complete result documents.

## 8. Hybrid ranker — `intelligence_hybrid_ranker/1.1`

The version advances because scoring behaviour changed, and **1.0's meaning is not mutated
silently**.

| Mode | Ordering |
|---|---|
| `LEXICAL` | lexical score alone (DIP-1B-6, unchanged) |
| `HYBRID` | `1.0 × lexical + 300.0 × semantic` — **numerically identical to 1.0**, so hybrid ordering keeps its frozen meaning |
| `SEMANTIC` | `300.0 × semantic` **alone** — this is the 1.1 change |

In 1.0, semantic-engaged results were always blended, so a "semantic" ranking quietly carried
lexical weight — which §8 forbids for semantic-only ordering. In 1.1 the lexical score is still
**reported** for semantic requests as a diagnostic, but does not influence the ordering.

Scores are always separately visible: `lexical_score`, `semantic_score`, `final_hybrid_score`.
Ranking never uses generative reranking, hidden LLM judgement, randomization, wall-clock,
legacy approval state, or permission/governance as a relevance boost. Ties break on canonical
CorpusItem UUID. With no index, HYBRID degrades to exactly the lexical score.

## 9. Facets

`GENERAL_CONCEPT` · `PRODUCT_CATEGORY` · `DESIGN_STYLE` · `ASSET_METADATA` · `FONT_METADATA`.
Only the bounded phrase and the facet label are sent — never facet-specific source data.

**Not claimed:** image or visual pixel similarity (no image embeddings) · layout-geometry
similarity · rights suitability inference · brand approval inference.

## 10. Modes and the permission gate

Reviewer candidate mode may show blocked candidates **with** their warnings. Operational
retrieval and automatic use still filter through the canonical permission gateway and return
**0** locally. The mode gate is applied *after* scoring, so semantic similarity can never
smuggle a denied item through — tested on the POST path specifically.

## 11. Offline index build (not executed)

**No real OpenAI document index was built, and no real semantic query was ever sent.** All
tests mock the client inside `OpenAIEncoder.encode`. The exact human-run command to build the
first production index, when explicitly authorized in that environment:

```
python manage.py rebuild_intelligence_semantic_index \
    --apply --provider openai --confirm-external-data-transfer --publish
```

Run it without `--apply` first to print the bounded document-boundary preview. It is not run
during tests or deployment.

## 12. A guard that had to be corrected

`test_source_foundation.py` forbade the literal token `semantic_search` anywhere in the
intelligence package — a DIP-1B-era scope constraint from when semantic retrieval was out of
scope. That premise was superseded by explicit approval (DIP-1C-1 `a748f7a`, and this slice).
Only that one token was removed; `recommendation_rank`, `vector_search`, and
`retrieve_assets_for_generation` remain forbidden because they guard capabilities that are
**still** excluded, and the security-critical half of the test — no seeded ALLOWED projection —
is untouched.

## 13. Exclusions

No query history · search analytics · saved searches · background query embedding · automatic
index rebuild · local embedding model · pgvector · permission grants · automatic-use / export /
production activation · generative reranking · image embeddings · automatic asset or font
selection · design generation · legacy cutover.

## Verification — all green

| Check | Result |
|---|---|
| new query tests (`test_semantic_query.py`) | **32 passed** |
| new browser tests (`test_semantic_query_browser.py`) | **14 passed** |
| complete apps suite | **1109 passed, 1 skipped** |
| accounts suite | **258 passed** |
| intelligence suite | **314 passed** |
| CI-equivalent (`-m "not pacdora"`) | **1108 passed, 1 skipped, 1 deselected** |
| DIP-0 tooling (**repo root**) | **1014 passed** |
| policy parity | **6 passed** |
| Ruff (`apps/` + `tools/`) | clean |
| migration drift | *No changes detected* — **no migration** |
| Django system checks | no issues |
| deploy checks (`DEBUG=false`) | only `W009` (throwaway test SECRET_KEY) |
| frozen `docs/…/dip0c/` | clean |
| materials | unchanged |

Live state: semantic index `UNAVAILABLE` · 0 generations · 0 embeddings · DecisionEvent **0** ·
HumanAssertionProjection **0** · GovernanceDecisionProjection **0** · ALLOWED permissions **0**
· campaign hash `cf178a…150bf` and partition 20/14/24/10/22 intact.
