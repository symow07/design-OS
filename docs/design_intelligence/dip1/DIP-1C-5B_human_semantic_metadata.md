# DIP-1C-5B — Signed Human Semantic Metadata Workflow

**Status:** built, tested, and held for review. **Not activated.** No reviewer has been
provisioned, no metadata has been recorded in the operational database, no embeddings were
rebuilt, and semantic search remains inactive. The published semantic generation is still
`e88b1468` (schema 1.2, 176 embeddings).

## Why this slice exists

DIP-1C-5A measured, and did not rescue, the ceiling. Confidence-gated semantic rescue could
not recover topical information because the documents never contained it: the corpus records
item *kind*, dataset identifiers and a handful of machine labels, and essentially nothing
about what a design looks like. Measured today over the real corpus:

| Schema-1.2 documents (state A, live) | Value |
|---|---|
| Documents | 176 |
| Distinct embedding texts | 63 |
| Byte-identical duplicate documents | 113 |
| Mean phrases per document | 2.44 |

No ranker separates vectors that are identical by construction. The missing content has to
arrive from a human who actually looked at the artwork — signed, bounded, and attributable.
That is what this slice builds. It builds the *workflow*; it does not invent the content.

## What was built

| Component | File | Contract |
|---|---|---|
| Metadata contract | [human_semantic_metadata.py](../../../bbrose_design_os/apps/intelligence/human_semantic_metadata.py) | `human_semantic_metadata/1.0`, vocabulary `human_semantic_vocabulary/1.0` |
| Bounded review scope | [semantic_metadata_scope.py](../../../bbrose_design_os/apps/intelligence/semantic_metadata_scope.py) | `dip1c_semantic_metadata_review_scope/1.0` |
| Signed service | [semantic_metadata_service.py](../../../bbrose_design_os/apps/intelligence/semantic_metadata_service.py) | record + correct, reusing DIP-1B-3 signing |
| Authorization | [authz_policy.py](../../../bbrose_design_os/apps/accounts/authz_policy.py) | `authz/1.3` (1.0–1.2 frozen) |
| Projection | [projection.py](../../../bbrose_design_os/apps/intelligence/projection.py) | domain `human_semantic_metadata`, no migration |
| Document schema | [semantic_document_v13.py](../../../bbrose_design_os/apps/intelligence/semantic_document_v13.py) | `intelligence_semantic_document/1.3` — **defined, not buildable** |
| Local preview | [semantic_metadata_preview.py](../../../bbrose_design_os/apps/intelligence/semantic_metadata_preview.py) | offline, fixture-based, zero embeddings |
| Reviewer surface | `views.py` · `templates/intelligence/review_detail.html` | HUMAN SEARCH METADATA section |

### The contract (`human_semantic_metadata/1.0`)

Nine frozen controlled vocabularies — product family, design style, motif, visual mood,
colour characteristics, layout/format, font style, script suitability, brand observation —
plus bounded `asset_categories`, at most 12 `search_synonyms` (≤40 chars each) and ≤2000
characters of `reviewer_notes`.

Refusals are total, never silent trimming: an unknown field, an unknown term, a value that
looks like a path or filename, a bundle with no descriptor at all, or **any authority claim**
(`OFFICIAL_LOGO`, `CANONICAL_MASTER`, `OWNED_BY_BBROSE`, `APPROVED`, `CANONICAL`, `LICENSED`,
`OFFICIAL`) is rejected with a reason code. Brand descriptors are observational by
construction — `BBROSE_LABEL_OBSERVED_UNCONFIRMED`, not "BBROSE logo". Ownership, licence and
canonical status remain unexpressible here; they live in governance.

`reviewer_notes` never enters embedding text (`bundle_embedding_terms` excludes it): notes are
context for humans, and free prose is exactly the surface where an unbounded claim would
otherwise leak into a vector.

The bundle is **idempotent** — re-validating a built bundle returns it unchanged. This is
load-bearing, not cosmetic: the projector defensively re-validates the signed payload it
reads, and `build_projection` fails closed for the entire chain, so a non-idempotent
validator would have turned one recorded bundle into an outage across every projection
domain.

### The bounded scope (`dip1c_semantic_metadata_review_scope/1.0`)

55 canonical items — 20 historical, 10 C2 assets, 10 curated assets, 10 fonts, 5
brand/palette — selected deterministically by `external_key`, excluding test-only and
non-active identities. The selection is a pure function of the corpus: it creates no
`CorpusItem` and no `ReviewCandidate`.

Measured scope hash (current corpus):
`8911b32131ee0f1121df7ca6a2b523ee124a7d6df28dbc4821a08251f5dcac78`.

### Authorization — `authz/1.3`

Two new actions: `record_human_semantic_metadata` and `correct_human_semantic_metadata`.

The spec also suggested `request_semantic_metadata_clarification`. It was added, then
**deliberately removed**: this slice builds no clarification workflow, and an authorized,
signable action with no service, view or projector handler is not a harmless placeholder —
the projector fails closed on any intelligence event it cannot project, so the first such
event would have bricked every projection domain. Reviewers raise metadata questions through
the existing evidence-clarification path until a real workflow is specified. A test asserts
that every intelligence action other than the two provably workflow-only ones (view queue,
claim review) has a projector branch.

Recording and correcting are permitted to
`BUSINESS_OWNER`, `BRAND_ADMIN`, `DESIGN_REVIEWER`, and are added to `SYSTEM_ADMIN_FORBIDDEN`
— infrastructure administration is not design judgement. Policies 1.0, 1.1 and 1.2 are
retained verbatim and a test asserts 1.2 does not contain the new actions.

### Signed events, and their deliberate separation from the campaign

The service reuses DIP-1B-3 wholesale — `authorize_actor`, `build_authorization_snapshot`,
`append_decision`, evidence-ownership validation, the reserved-field guard, signed
supersession. **No second signing or authorization framework was built.**

It is CorpusItem-centric and never reads or writes a `ReviewCandidate`. That is deliberate:
`record_intelligence_classification` requires a claimed candidate and flips it to `COMPLETED`,
so routing metadata through it would silently move the frozen 90-item campaign's completion
metric. A descriptor describes an item, so it attaches to the item.

Every bundle must cite at least one non-test evidence reference belonging to the same item.
Corrections supersede same-item, same-domain events only; the prior event is preserved and
appears as `SUPERSEDED` in the immutable history.

One change was required outside the slice: `decision_chain._supersession_action_compatible`
learned the metadata record/correct pair as a second bounded action family (the first being
DIP-1B-3 classification). No other cross-action supersession became possible.

### Projection

Metadata projects into the existing `HumanAssertionProjection` under
`assertion_domain="human_semantic_metadata"`, with the bundle in `normalized_value`.
**No migration was needed.** The supersession logic was generalized (`_classification_rows`
gained a `correction_action` parameter) rather than duplicated. Conflicting active bundles
produce `REVIEW_REQUIRED` exactly as classifications do, and the projector fails closed on an
invalid chain, an unverifiable signature, a bad authorization snapshot, unresolved evidence
integrity, or a bundle that no longer satisfies the contract.

### Schema 1.3 — defined, previewable, not built

`intelligence_semantic_document/1.3` reuses every 1.2 channel, phrase vocabulary and boundary
rule verbatim and adds one trailing channel, `human_semantic_metadata_terms`, marked
`VERIFIED_HUMAN_ASSERTION`. `UNKNOWN`-style non-answers are dropped rather than embedded.

With zero reviewed items a 1.3 document is byte-identical in embedding text to its 1.2
document — verified over the live corpus: **176 of 176 identical**. 1.3 is deliberately
absent from `SUPPORTED_BUILD_SCHEMAS` (listed in `DEFINED_NOT_BUILDABLE_SCHEMAS`); requesting
it from the build registry fails closed.

### Local quality preview (offline, fixtures only)

`build_preview(fixture_bundles=…)` compares state A (as-is) with state B (in-memory fixture
bundles). It computes no embeddings, contacts no provider, and writes nothing.

| Metric | State A (live, zero metadata) | State B (55 synthetic fixture bundles) |
|---|---|---|
| Documents | 176 | 176 |
| Distinct embedding texts | 63 | 90 |
| Duplicate documents | 113 | 86 |
| Mean phrases per document | 2.44 | 3.38 |
| Items carrying human terms | 0 | 55 |

**Read this honestly.** The state-B bundles are synthetic combinations invented for this
preview, not observations of the artwork. The numbers demonstrate that the mechanism carries
descriptive content into embedding text and reduces duplicate collapse; they are **not**
evidence that retrieval quality improves. That can only be measured after real reviewers
record real descriptors, and would require a separately authorized index build.

### Reviewer surface

The review-candidate detail page gains a HUMAN SEARCH METADATA section, shown only for
in-scope items, carrying the banner **"HUMAN DESCRIPTIVE METADATA IMPROVES SEARCH. IT DOES
NOT AUTHORIZE USE."** It posts with CSRF to a POST-only, authorization-decorated view; the
actor and role are derived server-side and can never be supplied by the form; every input is
a select bound to the frozen vocabulary, so an unlisted term is not offerable and is refused
anyway; evidence must be selected; and the immutable history (CURRENT / SUPERSEDED /
HISTORICAL) is displayed. No governance, approval or permission control appears in the
section.

## Manual review procedure (for the first real reviewer session)

1. **Provision** exactly one reviewer with `DESIGN_REVIEWER`, an enabled `ReviewerProfile`,
   and a bounded expiry. *(Not done — this slice stops here.)*
2. **Confirm the scope** is the intended 55 items: recompute `scope_hash()` and compare with
   the value recorded above. A different hash means the corpus moved; investigate before
   reviewing.
3. **Look at the artwork** for the item — the preview/evidence on the detail page — before
   selecting anything. Descriptors are observations, not guesses from a filename.
4. **Select only what you can see.** Leave a vocabulary empty rather than choosing `UNKNOWN`
   for completeness; `UNKNOWN` is dropped from embedding text and communicates nothing.
5. **Cite the evidence** you actually looked at. At least one reference is required.
6. **Never assert authority.** If an item looks like an official brand master, record
   `BBROSE_LABEL_OBSERVED_UNCONFIRMED` and raise it through governance — the form cannot
   express ownership and must not be worked around.
7. **Notes are for humans.** Put reasoning and uncertainty in `reviewer_notes`; it is stored
   and displayed but never embedded.
8. **Correct rather than re-record.** A correction supersedes the prior event and preserves
   it; recording twice creates a conflict and the projection turns `REVIEW_REQUIRED`.
9. **Rebuild the projection** (`rebuild_assertion_projections --apply`) and confirm the
   generation publishes and the item shows `CURRENT`.
10. **Do not build an index.** Schema-1.3 embedding requires separate explicit
    external-transfer authorization and its own preflight.

## Verification

* `pytest apps/accounts apps/intelligence -m "not pacdora"` — **739 passed** (18 new).
* Migration drift: none — this slice adds **no migration**.
* Authority counts unchanged: 0 governance decisions, 0 operational permissions, before and
  after.
* Published semantic generation unchanged: `e88b1468`, schema 1.2, 176 embeddings, CURRENT.
* Frozen campaign scope hash unchanged:
  `cf178a337ec0350d8facf093bae8155aa1d2a039c46358102a93a011920150bf`, partition 20/14/24/10/22.
* `materials/` untouched (read-only source; nothing in this slice reads it).
* Four existing tests that pinned `authz/1.2` were updated to `authz/1.3`; the 1.2 mapping
  itself is asserted frozen.

## Deliberately not done

No reviewer provisioning. No metadata recorded in the operational database. No schema-1.3
index build and no external data transfer of any kind. No embedding rebuild, no generation
publication, no activation of semantic search. No operational permission granted by anything
in this slice.
