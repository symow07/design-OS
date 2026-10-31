# DIP-0C2c — Decisions

Machine-readable thresholds: [c2c_config.json](c2c_config.json) (hash fingerprint
`5f31dc7c2e5b`). This file records *why*.

## 1. Edges are evidence, not verdicts

A pair may carry **several hypotheses at once** (a colorway is also a format
variant), each with its own evidence and confidence. `human_confirmed_relationship`
is always blank. Families are **derived** as connected components for review
convenience; the edges stay authoritative and are never collapsed away.

## 2. Source and candidate graphs are separate

A **candidate edge is never created from a source edge alone.** Shared filename,
folder, package, visual style or family membership are recorded *as evidence on*
an edge — they can support a hypothesis flagged for review, but they can never
produce a near-duplicate or visual-equivalence claim, which requires the hashes.
Tested: same folder + same stem + visually unrelated ⇒ no equivalence.

## 3. Both hashes must agree

`≤6` = strong, `7–12` = review, `>12` = unrelated — and **both dHash and pHash
must satisfy it**. This applies to geometric closeness too, not just to the strong
near-duplicate rule. Using `min()` there was a real bug: one agreeing hash carried
the pair while the other strongly disagreed, producing **24 spurious "colorways"**
between different stickers on one sheet. With `max()` they vanish.

## 4. Information content overrides hash distance

Two blank images have *identical* hashes. So an information score (grayscale
variance, entropy, alpha coverage) is computed **before any distance is trusted**;
a blank, near-uniform or mostly-transparent image is weak evidence and its
confidence is capped, so it can never reach "strong" no matter how close the hash.

**Variance is the real guard; entropy is not.** An early entropy floor of 2.0 bits
condemned flat vector artwork — a 3-colour logo is ~1.2 bits yet carries plenty of
shape information. The floor is now 0.5 bits (degenerate images only).

## 5. The silhouette rescues "same logo, different background"

The shape hash is taken over the **silhouette**: the alpha mask when there is one,
otherwise a background-difference mask (so it works for opaque images too). The
same logo on white and on black has nearly *inverted* grayscale hashes but an
*identical* silhouette. Such a pair stays on the graph as `UNKNOWN_RELATIONSHIP` /
review — **never promoted to a duplicate**, because the pixels genuinely differ.

A silhouette is only trusted when it is *informative*: an all-on or all-off mask
matches everything.

## 6. Palette is measured on the foreground

Colorway evidence compares palettes over the **silhouette**, not the whole frame.
A shared background otherwise dominates the histogram and drowns the difference —
red-vs-blue artwork on white scored only 0.22 apart (below the 0.25 threshold) and
would have been missed entirely.

`POSSIBLE_COLORWAY` needs converging evidence: similar geometry **and** materially
different palette **and** similar silhouette **and** similar dimensions **and**
package/naming evidence. Visual similarity alone is never enough.

## 7. Crops require positive visual containment — never folder + aspect

Perceptual hashes are **not crop-invariant**, so a genuine crop legitimately fails
the whole-image distance test. That does **not** license guessing a crop from
circumstantial facts.

A crop is proposed **only** from a positive **containment** signal: the crop's
whole-image hash matching one of the parent's **region hashes** (halves, quadrants,
centre). Both dHash *and* pHash must agree within `HAMMING_STRONG` for that match.

This replaced a real violation. The original rule was `not aspect_close and
(same_pkg or geom_close)`, which produced `POSSIBLE_CROP_VARIANT` from **shared
folder + different aspect and no visual evidence at all** — relating two unrelated
images that merely sat in the same download folder. It fired 3 times on the pilot,
on pairs measured at dHash 22–30 / pHash 24–30 (wildly unrelated). That is exactly
what "do not infer candidate equivalence from shared folders / same package"
forbids. With containment required, it drops to **0**.

Containment also demands *stronger* agreement than a whole-image match, not weaker:
a single lenient dHash is not enough, because on flat-background artwork most
gradient bits are zero and two **unrelated** white-ish regions collided at Hamming
8 and manufactured a crop claim.

## 8. Transforms are explicit

Every image is hashed under identity, mirror, 90°, 180° and 270°. A match that
holds *only* under a transform is reported as explicit `MIRRORED` / `ROTATED`
evidence with `transform_only_match: true` — **never as a silent duplicate**.

## 9. Weak bridges split components

Only edges ≥ `STRONG_EDGE_CONFIDENCE` (0.60) build components. An edge that is the
**sole connector** between two halves of a component (a bridge) with confidence
below `WEAK_BRIDGE_CONFIDENCE` (0.75) **splits** the component and is reported for
review. This is what stops `A~B~C` from silently fusing unrelated assets. A
reviewer can always merge two small families; un-fusing a wrongly fused one is far
harder.

## 10. Canonical: nominated, never selected

Rights/licence evidence is shown as **context** and contributes **exactly zero** to
the score (`rights_contribution: 0`, pinned by a test). A technically strong but
rights-unverified asset can be the technical canonical candidate while remaining
entirely unusable. `human_selected_canonical` is always blank.

## 11. No naive all-pairs

Pairs are generated by blocking: exact-SHA groups, pHash 4×16-bit bands (LSH),
filename-normalized stems, folder/package groups, and aspect+format buckets. The
reconciliation reports pairs-compared vs naive N² so the reduction is auditable.
No database and no vector index is built.

## 12. Family membership propagates nothing

Not readiness, ownership, licence, permissions, retrieval eligibility, automatic
use or brand status. Every member keeps its own record. Verified on the frozen
cross-format family, whose three members keep three **different** readiness values.
