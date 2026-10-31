# DIP-1C-3A — Safe semantic document enrichment (schema 1.1)

**Status:** implemented and verified. Held for explicit transfer authorization.
**No OpenAI request has occurred.** No migration.

A narrow schema-tuning gate before the external transfer. The second preview was
technically clean but the documents were too thin to measure *encoder* quality — running
the pilot then would have measured missing document semantics instead. This slice adds
usefulness from **existing bounded machine observations only**, without weakening the
corrected value boundary and without inventing a single human label.

---

## 1. Schema `intelligence_semantic_document/1.1`

Schema **1.0 is frozen** — its constant and field list are preserved and pinned by test, so
historical generations remain describable. 1.1 supersedes it and hashes differently, which
requires a new index generation.

| Change | Why |
|---|---|
| `display_label` becomes **optional** | an unsafe optional title is omitted instead of excluding the whole item |
| **+ `machine_product_family_labels`** | bounded, normalized, explicitly machine-derived |
| **+ `observed_script_coverage`** | bounded technical font observation |
| **− `product_family_label`** (removed) | see below |

**`product_family_label` is removed, not supplemented.** It was a raw unbounded passthrough
of a machine string — an unvalidated leak vector: a path-shaped machine label would have
been transmitted verbatim (a test proves it now cannot). It is superseded by
`machine_product_family_labels`, which normalizes through an explicit vocabulary, refuses
path-like values, and names itself machine-derived. A schema version may remove a field; it
may not redefine 1.0.

## 2. Optional unsafe field omission

Previously an item whose only title was a source filename was excluded entirely. Now each
candidate field is validated before inclusion, an unsafe **optional** field is omitted, and
the rest of the safe document survives — the item stays indexable.

* A local, **never-transmitted** diagnostic records the reason:
  `OPTIONAL_DISPLAY_LABEL_OMITTED_SOURCE_FILENAME`.
* The unsafe value never reaches the document, its bytes, its hash, the preview, or logs.
* **Never sanitized.** Stripping `.ai` off `LG5505唇彩.ai` and presenting `LG5505唇彩` as a
  title would manufacture semantic metadata no human approved. A test pins that the
  stripped stem is absent too.
* **Required** identity fields still fail closed — an item whose `external_key` carries a
  path is still excluded with a reason (tested), so omission does not weaken the boundary.

**Display-label precedence:** verified human label → safe imported descriptive title → safe
bounded non-filename label → omit. It never falls back to a filename, path, archive member,
absolute location, or directory-derived phrase. The stable external key remains identity
metadata and is not promoted into natural-language content.

## 3. Machine product family

Key: **`machine_product_family_labels`** — the name itself declares the labels machine-derived.

**Sources (existing observations only):** `HistoricalDesignProfile.product_family_machine_label`
and `MachineClassification(classification_type="HISTORICAL_PRODUCT_FAMILY")`. **Never**
inferred from a filename, directory, or title.

**Vocabulary:** `MAKEUP_COMPACT` · `COMPLEXION` · `LIP_COLOUR` · `PRIMER_SKINCARE` ·
`EYE_COLOUR` · `CONCEALER` · `OTHER` (unrecognised) — empty/unknown yields nothing. Sorted,
deterministic. Path-like values are refused outright and can never become a family.

**Conflicts stay visible.** Disagreeing machine observations both survive plus an explicit
`MACHINE_LABELS_CONFLICT` marker — never a silent pick. This is *not* verified product
family, and implies no governance or permission.

## 4. Observed script coverage

Key: **`observed_script_coverage`**, sourced from `FontFaceProfile.script_coverage`
(`{script: glyph_count}`, present on all 34 fonts).

**Vocabulary:** `LATIN` · `ARABIC` · `CYRILLIC` · `GREEK` · `HEBREW` · `CJK` · `HANGUL` ·
`DEVANAGARI` · `THAI` · `OTHER` · `UNKNOWN`. Arabic presentation forms map to `ARABIC`; CJK
extensions map to `CJK`. Sorted, deterministic; no raw ranges, paths, or filenames.

**`numerals` is excluded** as a documented character class, not a script. Mapping it to
`OTHER` would put 33 of 34 fonts in `OTHER` and destroy the field's discriminating value —
so it is excluded explicitly, not silently dropped.

A technical observation only: **not** a font recommendation, **not** licence evidence,
**not** production permission. Presence of a script means glyphs were observed in it — it is
not a guarantee of coverage depth (the DIP-0C4 lesson: presence is not coverage).

## 5. External boundary — unchanged and re-validated

The allow-list is not broadened. Omission diagnostics are local and never transmitted. No
filenames, paths, locators, evidence IDs, source artifact names, raw ObservedFact values,
human identity, DecisionEvent details, or licence text. The recursive value validator runs
on the **complete assembled 1.1 document** — nothing passes on the strength of an earlier
per-field check.

One classification improvement: the materials boundary set now includes `:` so an embedded
key like `asset:materials/x.ai` is classified `MATERIALS_PATH_VALUE` rather than falling
through to a vaguer code. It was already refused either way.

## 6. Document quality — before vs after

"**Meaningful semantic channel**" is fixed in code as: `display_label`,
`machine_product_family_labels`, `style_labels`, `observed_script_coverage`,
`observed_fact_values`, `machine_classification_labels`, `human_assertion_labels`. Identity
and schema plumbing (`external_key`, `item_kind`, `dataset_identifier`, `schema_version`)
**do not count** — they are how we name a thing, not what it is. The definition lives beside
the metric so it cannot be quietly widened to flatter coverage.

| Metric | 1.0 (2nd preview) | **1.1** |
|---|---:|---:|
| Indexable documents | 170 | **176** |
| Excluded | 6 | **0** |
| Safe display label | 170 | 170 |
| Display label omitted | — | 6 |
| **Product-family metadata** | **0** | **6** |
| Style/category metadata | 122 | 122 |
| **Font docs with script coverage** | **0 / 34** | **34 / 34** |
| Verified human labels | 0 | 0 |
| **Identity/enum-only documents** | **64** | **0** |
| ≥2 meaningful channels | — | **176** |
| Mean / median / max length | 126.6 / – / 204 | 126.9 / 118 / 204 |

Channel distribution: 20 documents with 2 channels, 156 with 3. Omitted optional fields:
6 × `display_label:OPTIONAL_DISPLAY_LABEL_OMITTED_SOURCE_FILENAME`.

**Still honest about what is missing:** verified human labels remain **0**, and no
descriptive content exists anywhere — nothing records that a motif is floral or a palette
feminine. Nothing was invented to fill those gaps.

## 7. Benchmark reconciliation (lexical only — no OpenAI call)

Expectations were **not** changed to suit the new documents.

| | Baseline (1.0) | **1.1** |
|---|---:|---:|
| Queries | 30 | 30 |
| Empty results | 4 (13.3%) | 4 (13.3%) |
| Mean category precision@10 | 0.738 | 0.738 |
| Exact-identity controls first | 2 / 2 | 2 / 2 |
| RETRIEVAL allowed | 0 | 0 |
| AUTOMATIC_USE allowed | 0 | 0 |

**The lexical baseline is identical, and that is expected, not a null result.** The lexical
ranker reads the database directly (display title, external key, fact and machine labels);
the semantic document feeds only the embedding index. Schema 1.1 therefore changes what
would be *embedded*, not what lexical search finds. The six formerly excluded historical
items were always reachable lexically (lexical reads their stored title) — what changed is
that they are now *indexable* semantically, carrying `LIP_COLOUR`, `CONCEALER`,
`EYE_COLOUR`, `COMPLEXION`, `MAKEUP_COMPACT`, `PRIMER_SKINCARE` instead of being dropped.

Product-category queries (Q02–Q06) now have an indexable target for the first time; font
script queries (Q20/Q21) now have `ARABIC` (4 fonts) and `CYRILLIC` (1) to match against.
Whether embeddings exploit that is exactly what the pilot must measure.

## 8. Verification

New enrichment suite 20 · value boundary 45 · full Django **1174 passed**/1 skipped ·
tooling **1014** (repo root) · ruff clean (`apps/` + `tools/`) · **migration drift zero — no
migration** · system checks no issues · deploy only local `W009` · frozen dip0c clean ·
materials unchanged · **no OpenAI call in any test** · DecisionEvent/Human/Governance/ALLOWED
all **0**.

## 9. Exclusions

No OpenAI call · no invented human labels · no weakened path/filename boundary · no
permissions or authority · no hybrid-weight tuning · no real semantic generation · no
migration.
