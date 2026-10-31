# DIP-0C2b — Known limitations

Standing capability limits, recorded so no later stage mistakes them for results.

## 1. EPS is header-only (tooling limit)

Ghostscript is not installed and is **not** auto-installed. The Illustrator TIFF
previews in this library are a 2-samples-per-pixel palette subset PIL cannot
decode, and **no custom decoder was attempted** (explicitly out of scope for C2).

Consequence: for every real EPS asset, geometry, editability, path cleanliness,
clipping structure, vector/raster balance, recolorability and seamlessness are
**unknown, not absent**. EPS candidates are `HEADER_ONLY_PARTIAL` / `REQUIRES_TOOL`
and can never be `TECHNICALLY_READY`. Lifting this requires the deferred
Ghostscript validation (C1B pilot + fidelity gate), which remains a separate,
reviewed decision.

## 2. Raster multi-region segmentation is a proposal, not a fact

Connected components cannot distinguish a genuine sticker sheet from a decorative
background with disconnected regions (measured: a fluid background with 5 regions
and a real sticker sheet with 13 are statistically indistinguishable). Multi-region
raster stays `AUTO_LOW_CONFIDENCE`, which C2b turns into
`COLLECTION_SHEET_AMBIGUITY` → `NEEDS_CLEANUP`. **Human review is mandatory before
any split candidate enters an asset library.**

## 3. A repeat verdict describes a tile, not a crop

Seamlessness is measured at **source** level. Crops out of a multi-asset source
return `REQUIRES_HUMAN`; no seamlessness is inferred for them. Vector SVG has no
rasteriser in this toolchain, so SVG patterns are `REQUIRES_TOOL`.

## 4. Watermark detection is heuristic and conservative

It looks for stock-provider names, preview labels, a periodic low-opacity overlay
residual and edge text bands. It will **miss** subtle or novel watermarks, and it
deliberately refuses to suspect on low resolution alone. A `NOT_SUSPECTED` result
is **not** a clearance — it means no positive signal was found.

## 5. Print suitability is not determined

Nothing is called print-ready from pixels alone. Print suitability needs an
intended physical size and the resulting effective PPI, which we do not have for
rasters (`UNDETERMINED_REQUIRES_PHYSICAL_SIZE`). Vector candidates do carry real
mm bounds, recorded as evidence — still never a print grant.

## 6. Vector split granularity is dieline-tuned

`segment_page` (reused from DIP-0B) was tuned for dielines, not assets. Split
*counts* are provisional; the confidence states and human review carry the weight.

## 7. Nothing here grants anything

A `TECHNICALLY_READY` verdict says the artefact is technically sound. It says
nothing about ownership, licence, reuse posture, retrieval or automatic use — all
of which remain unconfirmed/false and human-gated.
