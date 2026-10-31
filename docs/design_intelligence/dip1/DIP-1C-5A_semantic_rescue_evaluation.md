# DIP-1C-5A — Confidence-gated semantic rescue and abstention evaluation

**Status:** evaluated, held for review. **Nothing activated.**

**Outcome: `NEEDS_MORE_HUMAN_METADATA`.** The confidence-gated rescue *architecture* passed
its predeclared holdout safety criteria — it is strictly safer than hybrid 1.1 — but it
delivered **no discovery lift over lexical** on this corpus, because the documents carry no
descriptive or verified-human content for semantics to exploit. A search-quality evaluation
only: nothing approved, nothing granted, retrieval/automatic-use remain 0.

---

## 1. DIP-1C-4B findings that motivated this slice

Universal hybrid weighting (`_SEMANTIC_WEIGHT=300`) improved p@1 but **diluted** strong
lexical results at p@5/@10 and **manufactured** confident answers for all six
no-evidential-basis queries. The design decision here: treat semantic as a *rescue* channel
for weak lexical queries, gated by transparent evidence — never a universal additive boost.

## 2. Evaluation split — frozen before the query transfer

`intelligence_semantic_rescue_evaluation/1.0`. Deterministic from stable query IDs (even
position within each stratum → DEVELOPMENT, odd → HOLDOUT), so it **cannot be retro-tuned**;
the definition (`DIP-1C-5A_evaluation_split.json`) was written before the full-distribution
results were obtained.

| Subset | Supported | No-basis | Total |
|---|---:|---:|---:|
| DEVELOPMENT | 11 | 3 | 14 |
| HOLDOUT | 11 | 3 | 14 |
| CONTROLS (Q29, Q30) | — | — | 2 |

Controls are excluded from **both** tuning subsets — exact identity is the planner's job and
must never tune a semantic threshold.

## 3. Query transfer

One authorized 30-query embed against generation `e88b1468` (schema 1.2, openai,
text-embedding-3-small, CURRENT), capturing the **full 176-item score distribution** per
query — the data DIP-1C-4B lacked for threshold selection. 30 requests, 49.6 s. Raw query
text and vectors were never persisted; DecisionEvents stayed 0. **No corpus document was
retransmitted; no document rebuild.**

## 4. Contracts (all evaluation-only; nothing wired into the default path)

* **`lexical_evidence_profile/1.0`** — classifies a query's lexical strength
  (EXACT_IDENTITY / STRONG_LEXICAL / WEAK_LEXICAL / NO_LEXICAL_EVIDENCE) from lexical signals
  only, using the **same** signals production lexical search uses (external key, safe label,
  observed-fact and machine-classification labels). It never inspects semantic scores.
* **`semantic_evidence_gate/1.1`** — judges the **full corpus distribution** (top score,
  median, top-to-median margin, corpus percentile, spread, facet consistency, tied-group
  size) → PASS / ABSTAIN / REVIEW_REQUIRED. It never receives the query text, id, expected
  answer, human label, lexical identity, permission, or legacy state.
* **`intelligence_hybrid_ranker/1.2`** — a confidence-gated rescue plan, not a weighted sum:
  exact identity → planner pin; strong lexical → lexical order preserved (semantic never
  reorders it); weak/absent lexical + gate PASS → semantic (or a fixed-constant fusion);
  gate ABSTAIN → honest lexical or empty, **never a manufactured neighbour**; REVIEW_REQUIRED
  → lexical, uncertainty exposed. No score bonus; `_SEMANTIC_WEIGHT` is not carried over.

Ranker 1.1 and gate 1.0 remain frozen and reproducible.

## 5. Candidate strategies and DEVELOPMENT selection

Three declared strategies — `SEMANTIC_RESCUE_ONLY`, `GATED_RECIPROCAL_RANK_FUSION`,
`GATED_NORMALIZED_BLEND` — evaluated on DEVELOPMENT with the predeclared
`DEFAULT_GATE_THRESHOLDS` (not tuned on dev). All three **tied** (supported p@1 0.545, MRR
0.619, hit@1 6/11, no-basis abstention 1.0, false-abstention 0.0): the queries where they
differ (weak/absent lexical + gate PASS) are too few to separate them. Per the design
principle, the tie was broken toward the **simplest, most transparent**:
**`SEMANTIC_RESCUE_ONLY`**. Thresholds were **not** fitted on dev — the declared defaults
were confirmed to behave (no-basis abstained, no false-abstention) and frozen.

**Frozen config: `SEMANTIC_RESCUE_ONLY` + `DEFAULT_GATE_THRESHOLDS`.**

## 6. HOLDOUT — evaluated once

| Metric (supported, n=11) | Value |
|---|---:|
| precision@1 | **0.909** |
| mean reciprocal rank | 0.909 |
| hit@1 | 10 / 11 |
| no-basis abstention accuracy | **1.0** (0/3 manufactured) |
| no-basis false-positive rate | **0.0** |
| supported false-abstention rate | **0.0** |
| exact-identity controls first (planner) | **2/2** |
| RETRIEVAL / AUTOMATIC_USE allowed | 0 / 0 |

The frozen config was **not** revised after seeing holdout.

## 7. The honest comparison — rescue equals lexical, does not beat it

Pure LEXICAL on the same 11 holdout-supported queries also scores **p@1 = 0.909, hit@1
10/11** — identical to the rescue. The rescue routed two weak-lexical queries (Q02 skincare,
Q06 makeup-compact) to semantic and got them right, but **lexical already got them right at
rank 1** via machine labels, so semantic added no lift. The one supported miss (Q04 eye
colour) is classified STRONG_LEXICAL with a wrong lexical top, so the rescue-only strategy
(correctly, by design) does not consult semantic for it.

**What the rescue bought is defensive, not additive:**
* it does **not** dilute strong lexical (unlike hybrid 1.1's p@10 drop to 0.590);
* it does **not** manufacture on no-basis queries (hybrid 1.1 manufactured on all six; the
  rescue abstained or returned honest lexical on all three holdout no-basis queries — Q10
  correctly EMPTY);
* it preserves exact identity through the planner (2/2).

So on this corpus the gated rescue **strictly dominates hybrid 1.1** (same identity, no
dilution, no manufacturing) while **matching, not beating, lexical** on discovery.

## 8. Duplicate semantic-text groups

Schema 1.2 has 63 distinct embedding texts across 176 items. Group-level metrics are
reported alongside item-level; within-group order is the canonical-UUID tie-break only, never
a semantic preference; each CorpusItem keeps its own blockers, provenance and readiness. The
rescue ranker does not pretend to distinguish members with identical embedding texts.

## 9. Performance

CorpusSnapshot 59 ms · corpus-hash 23 ms · index-status 27 ms · local vector scan 93 ms —
all under target; no N+1; corpus built once per request; exact staleness preserved. Provider
query-embedding latency (~0.5–6 s) is reported separately and is the dominant, irreducible
cost of any interactive semantic path.

## 10. Outcome and recommendation

Against the **predeclared** acceptance criteria the holdout **passes** — supported p@1 is at
least lexical (0.909 = 0.909), rescue fires for weak-lexical queries, no-basis false-positive
rate is materially reduced (to 0), strong lexical is not diluted, controls hold, permissions
stay 0, behaviour is deterministic, and abstention is a valid success. But "at least lexical"
is exactly what happened — **no meaningful topical improvement over lexical**, because the
documents are enum-shaped with no descriptive or verified-human content. Zero empty results
was not treated as success.

**Primary outcome: `NEEDS_MORE_HUMAN_METADATA`.** The binding constraint is the corpus, not
the ranker or the encoder: semantic cannot out-discover lexical while both read the same thin
labels. The gated-rescue architecture is **validated and accepted as the safe design** for
incorporating semantic — it is the correct replacement for hybrid 1.1 whenever semantic is
used — but it earns no activation now.

**Recommended activation decision: do NOT activate ranker 1.2 or gate 1.1 as the default.**
Lexical remains the default. There is no discovery lift to justify the added complexity or
the per-query external-embedding cost (which DIP-1C-2 forbids in the browser path anyway).
The higher-value next step is acquiring verified human labels / descriptive metadata, then
re-running this frozen evaluation. Any future activation is a separate versioned decision.

**Per the stop condition, nothing was activated.**

## 11. Human evaluation artifact

`var/design_intelligence/dip1c5a/` (git-ignored) — bounded per-query rescue decisions and
holdout rows for reviewer inspection; unfilled ratings vocabulary
`HIGHLY_RELEVANT`/`RELEVANT`/`PARTIALLY_RELEVANT`/`NOT_RELEVANT`/`CANNOT_JUDGE`. Feedback
only: no DecisionEvent, assertion, governance decision, or permission; no model, no
migration.

## 12. Verification

Rescue-contract suite 18 · full Django **1265 passed**/1 skipped · tooling **1014** (repo
root) · ruff clean · **migration drift zero — no migration** · frozen dip0c clean · materials
unchanged · generation `e88b1468` CURRENT, pilot `f88bd738` preserved · DecisionEvent/Human/
Governance/ALLOWED all **0** before and after · campaign hash `cf178a…150bf` and partition
20/14/24/10/22 intact · no vectors/DB/keys/query-text/query-vectors committed.

## 13. Exclusions

No ranker-1.2 or gate-1.1 activation; no default change; no document rebuild; no provider or
model change; no new benchmark queries; no changed expectations; no permission grant; no
automatic selection; no design generation; no legacy cutover; no tuning table / query-score /
search-history / analytics / threshold table; no migration.
