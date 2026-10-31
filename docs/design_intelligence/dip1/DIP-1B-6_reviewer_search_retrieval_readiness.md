# DIP-1B-6 — Reviewer search and retrieval-readiness API

**Status:** implemented, tested, held for review before the next Phase 1 slice.

A **read-only** search and retrieval-readiness layer over the curated intelligence corpus.
No migration, no new authority: every module writes nothing and grants nothing. The whole
slice exists to hold three things apart that a search tool naturally tempts you to merge:

> **CANDIDATE SEARCH DOES NOT AUTHORIZE OPERATIONAL USE.**
> Being findable for review is not being retrievable, and being retrievable is not being
> usable by a machine.

Current local result: **176 reviewer-searchable**, **0 retrievable**, **0 automatically
usable**, **0 exportable**, **0 production-eligible**. That zero is the correct fail-closed
state — no permission has been granted.

---

## 1. Search contract — `intelligence_search/1.0`

`apps/intelligence/search_contract.py`. A query is a **closed vocabulary**, not an
expression language. `build_search_query(raw)` validates an untrusted dict into a frozen
`SearchQuery` or raises `SearchContractError` — it never approximates.

Every field is validated against a bounded set **derived from the models and the readiness
contract** so it cannot drift. Refused: unknown field names, arbitrary SQL fragments,
JSON filter objects, executable/ordering expressions, unbounded limits (max 100),
unsupported modes, and unsupported enum values. Filter lists are normalised (stripped,
de-duplicated, sorted) so the same request always means the same query. Free-text labels
(`product_family_labels`, `candidate_labels`) are bounded text that is *matched*, never
interpreted as field names.

## 2. Lexical ranker — `intelligence_lexical_ranker/1.0`

`apps/intelligence/lexical_ranker.py`.

**This is lexical and metadata matching. It is not semantic search.** No embeddings, no
vector index, no learned weights, no model call. The response carries
`"ranking_is_semantic": false` and the UI says so. Calling it semantic would misdescribe
the capability; semantic retrieval is a future milestone (§Future).

Fixed, documented weights over stable evidence, strongest first: exact stable-key →
exact display-label → prefix → token overlap → observed-fact label → machine-classification
label → verified human-assertion label. A **verified human assertion outranks a machine
label** (60 vs 10) — machine output is not human truth. Ranking never depends on database
row order, mutable legacy fields, wall-clock time, randomness, or `candidate_kind` (a
machine label that must never influence rank or lineage). Ties break on the canonical
CorpusItem UUID, so the same corpus state always produces the same order. An empty query
matches everything at score 0 with reason `FILTER_MATCH_ONLY` — browsing by filter is
legitimate and must not fabricate relevance.

## 3. Search modes

`apps/intelligence/search_service.py`. Mode is a hard gate applied **after** matching, so
reviewer mode can still surface a blocked item with its blockers, while operational modes
exclude it entirely.

| Mode | Returns | Authority |
|---|---|---|
| `REVIEWER_CANDIDATE_SEARCH` | candidates a human may examine, incl. rights/identity/integrity-blocked (blockers shown) | canonical reviewer authorization; independent of RETRIEVAL |
| `OPERATIONAL_RETRIEVAL` | only items with a currently valid RETRIEVAL permission | the permission gate |
| `AUTOMATIC_USE` | only items with an independently valid AUTOMATIC_USE permission | the permission gate |

Every allow/deny comes from `evaluate_retrieval_readiness`, which wraps the canonical
`evaluate_operational_permission`. **Permission authority is never re-derived here.**

## 4. Reviewer visibility is not a permission

`candidate_review_visible` is corpus membership + resolved identity (active lifecycle,
stable external key, not test-only), gated by the caller's reviewer authorization. It is
deliberately **not** the `VISIBLE_IN_REVIEWER_SEARCH` permission. Decisive evidence: zero
permission projections exist in the corpus, so deriving visibility from that permission
would make the entire corpus unsearchable — yet reviewers browse it today. "A human may
examine this" and "a machine may use this" are different questions.

## 5. Retrieval-readiness service — `retrieval_readiness/1.0`

`apps/intelligence/retrieval_readiness.py`. `evaluate_retrieval_readiness(corpus_item,
at=None)` returns a structured, read-only result: the five separate eligibility booleans;
per-permission state, reason code, projection id, and source DecisionEvent id; the
projected vs current chain-head hash; `stale_projection` and `expired_projection` as
distinct facts; identity blockers; evidence-integrity blockers; governance state; and the
evaluation timestamp.

It **reuses** `evaluate_operational_permission`, canonical identity resolution,
`EvidenceIntegrityResolver`, and the governance projection reader — it does not duplicate
permission authority. The permission gate already enforces every §2.2 requirement
(projection present, state ALLOWED, not expired, source event valid and signed, whole chain
valid, projection checkpoint == current chain head, `AUTOMATIC_USE_REQUIRES_RETRIEVAL`).
Stale is read separately (projection checkpoint vs `DecisionChainHead`) only to make the
reason legible; allow/deny still comes solely from the gate.

## 6. Campaign vs corpus scope

Never blended. `CAMPAIGN_SCOPE` returns only the frozen 90-item campaign with wave metadata;
`CORPUS_SCOPE` returns all reviewer-browsable canonical items (176), including the 29 curated
assets and 24 fonts outside the campaign. Corpus search **creates no ReviewCandidate, adds
nothing to the campaign, and changes no campaign progress.** Each result is tagged
`IN_CAMPAIGN`, `OUTSIDE_CAMPAIGN`, `WITHHELD_IDENTITY` (unresolvable identity — withheld,
not guessed), or `TEST_ONLY_EXCLUDED`.

## 7. Result contract — `intelligence_search_result/1.0`

Each result carries: canonical UUID, external key, item kind, display label, dataset
lineage, match score, ordered match reasons, campaign membership, wave, readiness state,
blocker codes, rights/identity/integrity/technical state, human-assertion status,
governance status, separate `retrieval` and `automatic_use` results with reason codes, a
source-hash summary, a reversed `detail_url`, legacy-signal note, and prohibited-use
warnings. It **never** exposes absolute paths (reuses `_bounded_location` /
`REDACTED_UNRESTRICTED_PATH`), source binaries, secrets, signing material, or full event
payloads.

## 8. Legacy signals

Any legacy signal (`DesignReference.active`, legacy approved/canonical state,
`BRAND_LOGO_PATH`, legacy output reuse) is shown as a diagnostic only, labelled
`LEGACY_SIGNAL_NON_AUTHORITATIVE`, `grants: NOTHING`, `affects_ranking: false`. A test seeds
a real active `DesignReference` and confirms it makes no intelligence item retrievable and
does not affect rank. Legacy signals grant no access, retrieval, use, export, production,
canonical status, or BBROSE identity.

## 9. Authorization

The search view reuses the canonical `VIEW_INTELLIGENCE_REVIEW_QUEUE` action — **not** a
second reviewer identity system. Server-side denial for unauthenticated, inactive, missing
reviewer profile, disabled reviewer, and unauthorized role. Being able to browse candidates
does **not** unlock operational retrieval: the operational modes apply the permission gate
and locally return nothing. No request-body user id, role, permission result, or authority
mode is trusted.

**Deliberate deviation from §6 (named, not silent):** §6 envisions AUTOMATIC_USE behind
"an authorized internal service." No service identity exists, and "no second identity
system" (§6) plus "no automatic selection" (§17) plus "no automatic-use activation" (§12)
forbid inventing one in this slice. All three modes are therefore reachable by an authorized
reviewer as **evaluation lenses**; the operational modes apply the permission gate as a
filter and return empty locally. The fail-closed zero is identical with or without a
service gate. **Service-caller gating for AUTOMATIC_USE is explicitly deferred.**

## 10. UI

`/intelligence/search/` (`apps/intelligence/views.py::intelligence_search`,
`templates/intelligence/search.html`). GET-only. Query box; mode and campaign/corpus
selectors; item-kind, dataset-lineage, wave, readiness, blocker, rights, integrity, and
technical-state filters; deterministic result count; stable pagination; explicit
empty-state text for each mode. Every page states
`CANDIDATE SEARCH DOES NOT AUTHORIZE OPERATIONAL USE.` and `NOT SEMANTIC SEARCH`. Each
result shows `REVIEWER CANDIDATE`, `RETRIEVAL: DENIED/…`, `AUTOMATIC USE: DENIED/…`. No
operational-use buttons, no permission-grant controls. Unknown filters return 400.

## 11. Report — `retrieval_readiness_report/1.0`

`apps/intelligence/search_report.py`. Five **non-substitutable** populations in escalating
authority: discoverable for review → eligible for retrieval → automatic use → export →
production. There is **no combined readiness percentage** (`None` by design) — review
progress is not use eligibility.

`curated_rights_unreviewed_corpus_wide` counts every curated acquisition **by lineage**
(53), whether or not it has a review candidate; `rights_unreviewed_in_campaign` (46) is the
strictly smaller campaign figure, named so it can never be read as the corpus-wide number.
Also reported: reviewer-visible, campaign vs outside-campaign visible, withheld identity,
test-only excluded, blocked-by-integrity, governance-selected, stale/invalid permission
projections, and counts by item kind and dataset lineage.

## 12. No new authority / no writes

Search, ranking, readiness evaluation, report generation, and rendering create **zero**
DecisionEvents, HumanAssertionProjections, GovernanceDecisionProjections, and ALLOWED
OperationalPermissionProjections; they update no ReviewCandidate, change no campaign
progress, and write no access timestamp. No search analytics in this slice.

## 13. Migration decision

**No migration.** Deterministic queries over existing indexed metadata are sufficient at
this corpus size. No persistent search index or vector table was created.

## 14. Exclusions

No permission-grant workflow; no ALLOWED-permission creation; no semantic embeddings,
vector DB, similarity recommendations, or learned ranking; no automatic asset/font
selection or design generation; no legacy pipeline cutover; no source-binary serving; no
search analytics; no external ledger anchoring; no per-user asymmetric signing.

## Future — semantic / vector retrieval

A later milestone may add embeddings and vector similarity. It will be a separate,
independently validated capability with its own contract and its own name. Until then, the
ranker is lexical and says so.
