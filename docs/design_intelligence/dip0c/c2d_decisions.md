# DIP-0C2d — Decisions

## 1. Five group types, and none of them is "families"

The word *family* was doing too much work. C2d keeps five **distinct** labels and
never collapses them:

| Type | Means | Are members substitutes? |
|---|---|---|
| `EXACT_DUPLICATE_GROUP` | byte-identical **files** | yes (a copy is a copy) |
| `VISUAL_FAMILY` | candidates that are **visually equivalent** | possibly — human decides |
| `COLLECTION_GROUP` | candidates segmented from **one surface** | **NO** |
| `CROSS_FORMAT_SOURCE_FAMILY` | one artwork in several **formats** | **NO** — different editability |
| `SOURCE_PACKAGE_FAMILY` | co-located files | **NO** — context only |

**A collection group is not a duplicate family.** A sticker sheet holds many
*independent* assets that are reviewed together and are in no way interchangeable.
All six components in this pilot are collection groups; **zero** are visual
families, and the manifest says so explicitly.

## 2. `UNKNOWN_RELATIONSHIP` is a review queue, not evidence

It means: *a comparison was generated, the available evidence was insufficient, a
human may clarify.* It is never positive family evidence, and no group is founded
on it.

The 49 edges are grouped **by shared reason** so a reviewer never inspects 49
unrelated pairs one at a time:

- `CONFLICTING_HASH_EVIDENCE` (24) — dHash and pHash disagree.
- `EPS_VISUAL_CAPABILITY_UNAVAILABLE` (24) — no hash could be computed.
- `CANDIDATE_VS_WHOLE_SHEET_MISMATCH` (1) — a whole-file candidate compared with a
  crop from a segmented sheet; the units are not comparable.

Each reason carries its own recommended action, and one decision may apply to the
whole reason-group.

## 3. An EPS without a hash is UNAVAILABLE, never "unrelated"

Absence of a hash is **not evidence of visual difference**. The six EPS candidates
are marked `VISUAL_COMPARISON_UNAVAILABLE` + `REQUIRES_TOOL`, their source/package
relationships still stand, and the queue action says in as many words: *do not read
these as visually unrelated*.

## 4. Machine and human blocks never share a key

Every row is `{"machine": {...}, "human": {...}}`. A reviewer writing
`relationship_confirmation: REJECTED` cannot alter a single machine field — the
sets of keys are disjoint, and a test asserts it. Machine inference is preserved
*after* human correction, so a wrong human call can be undone and a wrong machine
call is still visible.

## 5. No batch decision is ever applied automatically

A queue may say `one_decision_may_apply_to_group: true`. That is a *suggestion to
the reviewer*, and `batch_decision_applied` is always `false`. The system never
acts on a batch.

## 6. Priority always carries reasons

Nothing is HIGH without saying why. HIGH covers: exact duplicates needing a
canonical choice; conflicting hash evidence; candidate-vs-whole-sheet mismatch;
canonical nominations; **cross-format families whose members have different
readiness** (no member may inherit another's); and **technically strong assets
whose ownership is unconfirmed** — the most dangerous category, because they look
ready and are not usable.

## 7. The blocking limit is recorded, not hidden

Buckets above `MAX_BUCKET_MEMBERS` (400) are skipped. On this pilot none were, and
`coverage_note` says so. At library scale it will say the opposite, loudly. The
relationship search must **never** be described as complete when a bucket was
skipped. The fix is better candidate generation (see the DIP-1 recommendations),
**not** a return to naive all-pairs.

## 8. Nothing here activates anything

No group, queue, priority or nomination grants ownership, licence, retrieval,
automatic use, embedding, modification, redistribution or brand status. Every
member keeps its own rights record. Reuse posture stays `PENDING_REVIEW`.
