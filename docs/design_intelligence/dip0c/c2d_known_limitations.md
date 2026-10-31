# DIP-0C2d — Known limitations

## 1. Relationship search is NOT exhaustive at library scale

Blocking buckets above **400 members** are **skipped** rather than expanded into
O(n²) pairs. The skip is recorded (`skipped_buckets`, member counts, pairs not
generated, `coverage_note`), never silent.

- **On this pilot:** no bucket exceeded the limit → coverage is complete, and the
  reconciliation says so.
- **At full-library scale (7,586 files):** a large folder, package or format bucket
  *will* exceed it. Its members would then be compared **only** via the pHash bands,
  not via that bucket. **The relationship search must not be described as complete
  under those conditions.**
- **Affected categories:** the biggest download packages and the largest
  format/aspect buckets — in this library, the `Fonts/` tree and the bulk stock
  folders are the obvious risks.
- **Estimated missed-pair risk:** every skipped bucket reports exactly how many
  pairs it did not generate, so the risk is quantified rather than guessed.

This is **not** fixed by returning to naive all-pairs. See the DIP-1
recommendations for the scalable candidate-generation approach.

## 2. Zero visual families is a pilot fact, not a general one

All six components are **collection groups**. There is no `VISUAL_FAMILY` in this
pilot because there is no visually-equivalent candidate pair in it. A larger run
will produce visual families, and the review workload will shift accordingly.

## 3. EPS is invisible to every visual signal

Six candidates have no perceptual hash. They can never enter a visual family,
never be confirmed as a duplicate, and never be ruled out as one. Their entire
relationship story rests on SHA / filename / folder / package evidence until
Ghostscript lands.

## 4. Priority is a heuristic

The ordering encodes judgement (a technically-strong-but-rights-unverified asset is
HIGH because it *looks* usable and is not). It is a starting point for a reviewer,
not a measurement.

## 5. The workload estimate assumes batching works

"38 decisions batched vs 88 one-by-one" assumes a reviewer accepts one decision for
a whole reason-group. Where they cannot, the real number approaches the
one-by-one figure.

## 6. Nothing has been reviewed

Every human field is blank. No relationship is confirmed, no family is confirmed,
no canonical asset is selected, no asset is approved for reuse. **The library is
not active**, and nothing in DIP-0C2 makes it so.
