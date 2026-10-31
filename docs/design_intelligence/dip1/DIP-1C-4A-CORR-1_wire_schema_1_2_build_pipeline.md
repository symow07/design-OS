# DIP-1C-4A-CORR-1 — Wire the executable semantic-build pipeline to a declared schema

**Status:** implemented and verified. **No OpenAI document or query transfer occurred.** No
migration. Held for review and a **new** explicit transfer authorization.

---

## 1. The defect

DIP-1C-4A built the schema-1.2 machinery (`semantic_document_v12.py`,
`semantic_corpus.CorpusSnapshot`) and profiled it by calling the snapshot **directly**, but
never connected it to the executable build pipeline. The command reached its builder by an
**accidental import**:

```
rebuild_intelligence_semantic_index → build_generation → build_semantic_documents
→ build_semantic_document        (from semantic_document.py → schema 1.1)
```

So the committed `bc5ee1c` command's dry-run produced schema **1.1**, corpus hash
`913a8e32…` — not the authorized schema **1.2**, `cde0f207…`. Running the authorized
`--apply` would have re-embedded the old boilerplate documents under a schema-1.2
authorization. The mandatory preflight caught it; nothing was sent, and authority was
unchanged.

## 2. Correction principle

Schema 1.1 is **not** replaced or deleted. 1.0, 1.1, and the schema-1.1 pilot generation
`f88bd738-7d0f-4c5e-bc83-25e04482231a` remain fully supported for historical inspection. The
fix introduces an explicit **versioned builder registry** so the executable pipeline selects
a *declared* schema instead of depending on an import.

## 3. Builder registry — `semantic_builders.py`

`build_semantic_corpus(*, document_schema_version)` resolves a declared schema to its one
canonical frozen builder:

* **1.1** → the frozen `semantic_index` document functions (unchanged).
* **1.2** → the committed `semantic_corpus.CorpusSnapshot` / `build_semantic_document_v12`
  **verbatim**, reusing its single bulk batch (so the DIP-1C-4A bounded-query win is kept).
* **unknown** → `SemanticBuilderError`, fail closed.

There is exactly one builder per schema; neither is reimplemented in the registry or the
command.

## 4. Explicit build-schema selection

`build_generation`, the dry-run preview, the apply build, generation-manifest creation,
command output, and publication validation all take an explicit
`document_schema_version`. The command adds `--document-schema`:

* **`--apply --provider openai` requires `--document-schema`** — omitted, it fails closed
  **before encoder construction**. A schema-1.2 authorization can never silently transmit
  schema-1.1 documents.
* A dry-run defaults to 1.1 for back-compat but **states** the selected schema in its output.
* An unsupported schema is refused.

The global default was **not** flipped to 1.2 — DIP-1C-1/2/3 callers and the f88bd738 path
stay green.

## 5. Manifest contract — `intelligence_semantic_manifest/1.0`

`build_manifest(...)` produces a deterministic, non-sensitive manifest from the **same
service path the command uses**, with full 64-char hashes and, per §4, one meaning per hash:

* **`corpus_hash`** — the staleness/authorization value. Schema-specific, matching what is
  stored: 1.2 = `sha(schema ‖ Σ sorted(id, embedding_text_hash))`; 1.1 =
  `Σ sorted(id, document_content_hash)`.
* **`embedding_text_manifest_hash`** — `Σ sorted(id, embedding_text_hash)`, **without** the
  schema prefix. For 1.2 this is `corpus_hash`'s pre-namespacing input — a genuinely
  distinct value, reported separately with the relationship stated
  (`CORPUS_HASH_IS_SCHEMA_PREFIXED_OVER_THIS`), never conflated.
* **`document_content_manifest_hash`** — `Σ sorted(id, full-document-content-hash)`; the
  whole document (metadata + channels), not just the transmitted text.
* **`generation_config_hash`** — over schema, provider, model, dimension, index schema.
* Per-document full hashes (content + embedding-text), sorted by canonical UUID.

Excluded: embedding texts, paths, filenames, locators, vectors, secrets, provider
responses.

### Committed artifact

`docs/design_intelligence/dip1/DIP-1C-4A-CORR-1_schema_1_2_manifest.json` — the full-hash
schema-1.2 manifest for the live 176-item corpus, for the authorization gate:

| Hash | Value |
|---|---|
| corpus_hash | `cde0f207e13979da8610a481538a8b2a387bb647f6273f3c095f75db74af5e0a` |
| embedding_text_manifest_hash | `3c42dfcd58dc32dc64cba8932070de495c7f058c9e976fe773ddacb07d9e10d3` |
| document_content_manifest_hash | `7570c7ecd990e941f5114bab9508d4715d242babd07978fc50952dd28419f85b` |
| generation_config_hash | `91c24c4215f9db47af58bba5368d209984914cb5812ca580d74f96fd0abf90ff` |

The `bc5ee1c` doc recorded only an abbreviated `cde0f207…`; the full 64-char set is now
committed.

## 6. Hash semantics (§4)

Distinct meanings, tested separately: document-content hash (per doc) vs embedding-text
hash (per doc) vs the three aggregates above. The same DB state + schema yields identical
hashes (deterministic); changing an embedded phrase changes the document, manifest and
corpus hashes; a workflow-only change excluded from schema 1.2 does **not** change the
schema-1.2 corpus hash (verified in DIP-1C-4A's staleness tests).

## 7. Generation / vector reconciliation

At schema 1.2, each `SemanticDocumentEmbedding` row binds to the **1.2** document-content
hash from the canonical builder (which transitively commits the embedding-text hash the v12
document embeds), plus generation id, provider, model, encoder version, dimension, and
vector hash. Publication validates against the **generation's own schema's** recompute.
Rejected: a 1.2 vector on a 1.1 document hash, mixed schemas, mixed dimensions, mixed
provider/model. A test-encoder generation still cannot publish; a partial build never
replaces the published generation.

**No migration.** The existing columns (`document_schema_version`, `corpus_manifest_hash`,
per-row `document_hash`/`vector_hash`) already carry schema identity and the required
hashes; the full manifest lives in the committed artifact, not the DB.

## 8. Staleness uses the generation's own schema

`index_status()` and `publish_generation()` now recompute via
`corpus_hash_for_schema(generation.document_schema_version)` — never a hardcoded builder. A
1.2 generation is validated against a 1.2 recompute; the schema-1.1 pilot is checked against
a 1.1 recompute and does **not** go false-stale. Pinned by test.

## 9. Old generation preserved

`f88bd738-7d0f-4c5e-bc83-25e04482231a` is untouched: still schema 1.1, PUBLISHED, 176
embeddings, original hashes and vectors. Not deleted, rewritten, relabelled, or recomputed
with the new builder. It remains the current published (experimental) generation; lexical
search remains the default.

## 10. Corrected preflight (real command path, dry-run, schema 1.2 — no external call)

| Field | Value |
|---|---|
| document_schema_version | `intelligence_semantic_document/1.2` |
| document_builder | `versioned_registry` |
| provider / model | `openai` / `text-embedding-3-small` |
| corpus_hash | `cde0f207e13979da8610a481538a8b2a387bb647f6273f3c095f75db74af5e0a` |
| embedding_text_manifest_hash | `3c42dfcd58dc32dc64cba8932070de495c7f058c9e976fe773ddacb07d9e10d3` |
| document_content_manifest_hash | `7570c7ecd990e941f5114bab9508d4715d242babd07978fc50952dd28419f85b` |
| document_count / excluded | 176 / 0 |
| prohibited field / value findings | 0 / 0 |
| estimated requests / chars | 176 / 10,250 (~2,562 tokens) |
| campaign_hash | `cf178a337ec0350d8facf093bae8155aa1d2a039c46358102a93a011920150bf` |
| campaign_partition | 20/14/24/10/22 |
| external requests | **0** (dry-run) |

Derived from the **same** command path a real build would use.

## 11. Verification

CORR-1 builder suite 19 · all semantic suites 209 · full Django **1247 passed**/1 skipped ·
tooling **1014** (repo root) · ruff clean (`apps/` + `tools/`) · **migration drift zero — no
migration** · system checks no issues · deploy only local `W009` · frozen dip0c clean ·
materials unchanged · pilot `f88bd738` preserved · **0 external requests** ·
DecisionEvent/Human/Governance/ALLOWED all **0**.

## 12. Proposed real-build command (NOT executed here)

```
python manage.py rebuild_intelligence_semantic_index \
    --document-schema intelligence_semantic_document/1.2 \
    --apply \
    --provider openai \
    --confirm-external-data-transfer \
    --publish
```

**Stopped for a new explicit transfer authorization**, to be issued against this correction
commit, the full corpus hash `cde0f207…`, the full embedding-text manifest hash `3c42dfcd…`,
and the corrected executable-command preview. Not run even on a clean match.
