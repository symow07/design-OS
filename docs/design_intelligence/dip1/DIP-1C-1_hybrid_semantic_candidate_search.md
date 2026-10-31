# DIP-1C-1 — Hybrid semantic candidate search MVP

**Status:** implemented and verified. Held for review.

Adds a bounded semantic similarity channel alongside the deterministic lexical search from
DIP-1B-6. It introduces the **first migration** in the 1B/1C line — three additive tables
holding derived, rebuildable search data.

> **SEMANTIC SIMILARITY DOES NOT AUTHORIZE OPERATIONAL USE.**
> Similarity is *ordering*. Permission is *authority*. Semantic ranking never makes a denied
> item retrievable, and never bypasses the permission gate.

**Current local state:** no semantic index is published (no OpenAI apply has been run), so
semantic search is `UNAVAILABLE` and reviewer search falls back to lexical, labelled
`LEXICAL_ONLY`. Operational retrieval and automatic use remain **0**. This is correct
fail-closed behaviour, not a defect.

---

## 1. Architecture selected, and why

Preflight found: **no pgvector** (0 rows in `pg_available_extensions` for `vector` on this
Homebrew PostgreSQL 16.14); OpenAI SDK 2.37.0 installed with keys in `.env` but absent from
the runtime env; numpy 2.4.6 present; no local embedding model; **no embeddings usage
anywhere** in the repo (the only prior "vector" is Postgres full-text `SearchVector`).

Per the §2 preference order, option 1 (provider + pgvector) was unavailable and option 3
(local model) would require a large new dependency (torch). **Option 2 was selected:** an
existing provider plus bounded vector storage already supported by the current stack —
embeddings stored as a numeric JSON array, cosine similarity computed exactly in numpy.

> **This is the bounded Phase-1 MVP implementation, not the final large-scale vector
> architecture.** At ~176 items an exact in-memory scan is instantaneous and fully
> deterministic. `semantic_similarity.RECONSIDER_INDEXED_STORE_ABOVE = 50_000` documents the
> threshold at which pgvector or another indexed store must be reconsidered. No ANN
> approximation exists in this slice.

The encoder interface is deliberately clean so storage can later migrate to pgvector without
changing the semantic-document contract, generation identities, document hashes,
provider/model identities, hybrid-search contracts, or permission boundaries.

## 2. Migration and models

Migration `0007_semanticdocumentembedding_semanticindexgeneration_and_more` — verified
**additive**: `CreateModel`/`AddField`/`AddConstraint`/`AddIndex` only, and every operation
targets one of the three new tables. **No existing table is altered.** `makemigrations
--check` reports no changes; the frozen campaign scope hash `cf178a…150bf` and partition
20/14/24/10/22 are unaffected.

* **`SemanticIndexGeneration`** — encoder/provider/model identity, document + index schema
  versions, vector dimension, corpus manifest hash, status
  (BUILDING/BUILT/PUBLISHED/FAILED/SUPERSEDED), `is_test_encoder`, counts, `invoked_by`,
  timestamps, failure summary.
* **`SemanticDocumentEmbedding`** — generation, canonical CorpusItem, document hash, vector
  hash, dimension, the vector, provider/model/encoder version.
* **`SemanticIndexPublicationState`** — singleton (pk=1) naming the one currently published
  generation.

**Embeddings are derived, rebuildable search data. They grant no authority.** They are
deliberately kept out of `OperationalPermissionProjection` and `CorpusItem`. Building creates
zero DecisionEvents, zero projections, zero permissions, and appends no DecisionEvent merely
because embeddings were generated.

**Stored-vector contract** (validated before persistence, in `_validate_embedding_vector`):
numeric array only · exact dimension · finite values only · no NaN · no Infinity · plus
provider, model, encoder version, document hash, vector hash, generation identity. Vectors
are never accepted from a public endpoint.

## 3. Semantic document — `intelligence_semantic_document/1.0`

`apps/intelligence/semantic_document.py`. A strict **allow-list**, and the only thing that
may ever be transmitted externally.

**Included:** stable external key · item kind · non-secret display label · dataset lineage ·
bounded product/category label · bounded style/design labels · bounded technical font
metadata · observed-fact labels and normalized bounded values · machine-classification
labels (marked machine) · verified human-assertion labels (marked human) · readiness
vocabulary · blocker vocabulary.

**Excluded by construction and asserted absent before any send:** source binaries, images,
Illustrator files, fonts, archive contents, absolute or relative filesystem paths,
source-location observations, evidence locators, secrets, API keys, HMAC material, complete
DecisionEvent payloads, authorization snapshots, usernames/reviewer identity, licence text,
acquisition documents, unrestricted raw values, personal information, and legacy approval or
authority signals.

`_assert_within_boundary()` fails closed on any unexpected key or prohibited field — a
document that cannot be built within the boundary is refused, never trimmed into something
that leaks. Machine and human labels stay in separate, differently-named keys so an encoder
cannot launder a machine guess into a human conclusion. Documents are deterministic and
SHA-256 hashed, which is what makes rebuilds idempotent.

## 4. Encoders

`apps/intelligence/semantic_encoder.py`. One interface, two implementations.

| Encoder | Provider | Use |
|---|---|---|
| `DeterministicStubEncoder` | `TEST_ENCODER_NON_PRODUCTION` | tests, dry-run, architecture verification **only** |
| `OpenAIEncoder` | `openai` / `text-embedding-3-small` | the production-capable path, explicit apply only |

The stub is deterministic (same document → same vector, so rebuilds are idempotent) **and**
content-discriminating (different documents → different vectors, so ranking is meaningfully
testable). It never calls out. Its generations are marked `is_test_encoder=True` and are
**barred from becoming the production publication** — enforced in `publish_generation`, not
by convention. It is never presented as production semantic quality.

Provider/model identity is pinned per generation. Vectors from different providers, models,
dimensions, document schemas, or encoder versions never mix; a model change requires a new
generation.

## 5. External data boundary

The OpenAI path is reachable **only** through an explicit human-run command with **three**
independent flags:

```
python manage.py rebuild_intelligence_semantic_index \
    --apply --provider openai --confirm-external-data-transfer
```

Nothing is sent during application startup, migrations, browser requests, normal lexical
search, tests, default dry-run, Django checks, CI, or any automatic background execution.
**There is no implicit provider fallback** — `get_encoder` refuses an unnamed or unknown
provider, and `OpenAIEncoder` cannot even be *constructed* without the confirmation flag, so
no code path can call out by accident. A missing key on an explicit apply fails closed
without inspecting or printing the key.

**Preview + consent:** the default dry-run prints provider, model, document count, bounded
character estimate, document-schema version, corpus hash, included fields, prohibited fields
confirmed absent, estimated API request count, and an explicit statement that no data was
sent. The acknowledgement is a flag, not an interactive prompt, because the command may run
non-interactively.

**Key handling:** read only from the established secure runtime config; never committed,
never copied into a row, never in command output, logs, failure summaries, or documents.

**A consequence worth stating plainly:** because a browser request never carries the
external-transfer confirmation, a semantic query against a *published OpenAI* index cannot
embed the query in-request — it reports the index unusable-for-query and falls back to
lexical, labelled. Query-time embedding through an approved in-request boundary is a future
slice. This is a deliberate MVP limitation that keeps "no browser-triggered external calls"
absolute.

## 6. Index lifecycle

Builds run in **shadow**: a new generation is created, embeddings written under it, and only
a fully validated build is published atomically into the singleton state. Publication
requires: OpenAI provider · the approved model · every document passing boundary validation ·
all items reconciled (`embedded_count == document_count`) · uniform dimensions · finite
vectors · complete hashes · corpus hash matching the live corpus. A **test-encoder
generation can never publish**; a **failed or partial build never replaces a valid published
generation**; the previous generation is marked SUPERSEDED and remains identifiable.

**Staleness** is tracked by `corpus_manifest_hash` (a hash over each indexable item and its
semantic document hash), plus encoder identity/version and document schema version. Status is
`UNAVAILABLE` / `CURRENT` / `STALE`. The index is never rebuilt during a browser request.
Operational retrieval filters by permission **regardless of index freshness** — permission is
the authority, semantic is only ordering; a stale index affects reviewer ordering only.

## 7. Hybrid ranker — `intelligence_hybrid_ranker/1.0`

`apps/intelligence/hybrid_ranker.py`. Blends the lexical score
(`intelligence_lexical_ranker/1.0`, unchanged) with cosine similarity. **Lexical and semantic
scores are always reported separately** (`lexical_score`, `semantic_score`); the blend is only
for ordering. Weights are fixed and documented, never learned or tuned at runtime.

Ranking may use: lexical score, semantic similarity, exact-identity bonus, filter matches.
It must never use: legacy approval state, operational permission as a relevance boost,
randomness, wall-clock time, or generative-model judgement. Ties break on canonical CorpusItem
UUID. Reason codes: `EXACT_STABLE_KEY_MATCH`, `EXACT_DISPLAY_LABEL_MATCH`,
`STABLE_KEY_PREFIX_MATCH`, `DISPLAY_LABEL_PREFIX_MATCH`, `TOKEN_OVERLAP`,
`OBSERVED_FACT_LABEL_MATCH`, `MACHINE_CLASSIFICATION_LABEL_MATCH`,
`VERIFIED_HUMAN_ASSERTION_LABEL_MATCH`, `SEMANTIC_SIMILARITY`, `FILTER_MATCH_ONLY`.

With no index, `blended_score` degrades to exactly the lexical score — **HYBRID with no index
is bit-identical to DIP-1B-6 LEXICAL**, with no drift.

## 8. Modes (unchanged authority)

`REVIEWER_CANDIDATE_SEARCH` may use lexical and semantic ranking over candidate-visible
items; blocked items stay visible **with** their blockers. `OPERATIONAL_RETRIEVAL` and
`AUTOMATIC_USE` still filter through `evaluate_retrieval_readiness` → the canonical permission
gate, exactly as in DIP-1B-6, and are expected to return **0** locally. The mode gate is
applied *after* scoring, so semantic ranking can never smuggle a denied item through. No new
internal-service identity was created in this slice.

## 9. Fallback and honesty

Contract fields: `ranking` (`LEXICAL` default / `SEMANTIC` / `HYBRID`) and
`allow_lexical_fallback` (default true). Until a valid OpenAI generation is explicitly built
and published, the index status is `UNAVAILABLE`; a semantic-only request with fallback
disabled returns `SEMANTIC_UNAVAILABLE` with zero results rather than lexical results dressed
as semantic; hybrid requests fall back to lexical only when the contract permits it, and the
result is labelled `LEXICAL_ONLY` in both the payload and the UI. `ranking_is_semantic` is
true only when a real semantic channel actually engaged. **DIP-1B-6 lexical search remains
fully operational and is the fail-safe.**

## 10. UI

`/intelligence/search/` gains a ranking selector, semantic index status/version display,
per-result lexical and semantic scores, match explanations, and honest stale/unavailable
labelling. Banners: `CANDIDATE SEARCH DOES NOT AUTHORIZE OPERATIONAL USE.` and
`SEMANTIC SIMILARITY DOES NOT AUTHORIZE OPERATIONAL USE.` GET-only; writes nothing; no
operational-use or permission-grant controls.

## 11. Similarity facets

Supported from indexed metadata only: general concept, product/category, design/style, asset
metadata, and font technical/style similarity. **Not claimed:** image similarity (no image
embeddings), layout similarity (no validated layout features), visual identity from filenames,
rights suitability from similarity, or brand approval from similarity.

## 12. Auditable metadata

Recorded locally per generation: `invoked_by` (where an operator identity is supplied),
provider/model, generation id, document count, request count, corpus hash, per-document
hashes, start/end time, status. Complete transmitted documents are not logged by default, and
no DecisionEvent is appended merely because embeddings were generated.

## 13. Exclusions

No permission grants; no automatic-use/export/production activation; no learned
personalization; no generative reranking; no image embeddings; no automatic asset/font
selection; no design generation; no legacy pipeline cutover; no external search analytics; no
source-binary serving; no pgvector; no silent extensions; no automatic external calls.

## Verification — full 22-check sequence, all green

| # | Check | Result |
|---|---|---|
| 1 | previously failing DIP-1B-6 assertion | **1 passed** |
| 2 | complete apps suite (`pytest apps/ -q`) | **1064 passed, 1 skipped** |
| 3 | focused semantic tests | **37 passed** |
| 4 | accounts suite | **258 passed** |
| 5 | intelligence suite | **269 passed** |
| 6 | CI-equivalent (`-m "not pacdora"`) | **1063 passed, 1 skipped, 1 deselected** |
| 7 | DIP-0 tooling suite (**repo root**) | **1014 passed** |
| 8 | policy/parity (authz decoupling) | **6 passed** |
| 9 | Ruff (`apps/` + `tools/`) | clean |
| 10 | compilation + module imports | OK |
| 11 | migration drift | *No changes detected* |
| 12 | `sqlmigrate intelligence 0007` | 3 `CREATE TABLE` (new tables only); no `DROP`; no alter of any existing table |
| 13 | migration forward / rollback / reapply ×2 | clean; drift zero after |
| 14 | Django system checks | **no issues** (with signing key configured) |
| 15 | Django deploy checks | only `W009` (throwaway test SECRET_KEY) / `W018` (local DEBUG) |
| 16 | frozen-artifact clean-tree guard | `docs/design_intelligence/dip0c/` **clean** |
| 17 | materials/source diff guard | **unchanged** |
| 18 | live semantic-index reconciliation | `UNAVAILABLE`; 0 generations; 0 embeddings; 176 indexable |
| 19 | DecisionEvent count | **0** |
| 20 | HumanAssertionProjection count | **0** |
| 21 | GovernanceDecisionProjection count | **0** |
| 22 | ALLOWED OperationalPermissionProjection count | **0** |

Campaign scope hash `cf178a337ec0350d8facf093bae8155aa1d2a039c46358102a93a011920150bf` and
partition 20/14/24/10/22 both intact.

**Note on check 14:** run *without* `DECISION_EVENT_HMAC_KEYS`, Django reports
`accounts.security.W001` — decision-event signing unconfigured. That is a **warning**, is the
system's own fail-closed signal ("the correct failure mode, not a bug"), and is unrelated to
this slice; with the key configured, system checks report no issues.

**One assertion was corrected during verification.** The DIP-1B-6 test
`test_page_states_search_is_not_authorization` asserted the literal `"NOT SEMANTIC SEARCH"`;
the DIP-1C-1 banner now reads `"…NOT SEMANTIC."` with per-status labelling. It was updated to
assert `"NOT SEMANTIC"` in the body **plus** `ranking_is_semantic is False` in the payload —
strengthening the behavioural claim rather than weakening it. No production code changed for
it.

**Note on check 7:** the tooling suite must run from the **repository root** — the Django
suite runs from `bbrose_design_os/`. Two test roots, two cwd contracts (see
`DIP-0C4-TEST-CORR-1`, `96eeb9f`).
