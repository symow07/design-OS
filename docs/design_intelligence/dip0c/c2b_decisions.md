# DIP-0C2b — Decisions

Thresholds are machine-readable in [c2b_config.json](c2b_config.json)
(readiness fingerprint `1d8b92ce255f`); this file records *why*.

## 1. Axis A is scored; nothing else is

C2b scores **technical readiness only**. Rights (axis B), reuse posture (axis C)
and retrieval / automatic-use eligibility (D/E) are carried through from C2a
untouched and stay `unconfirmed` / `pending` / `false`. Invariants fail the run if
any of them moves.

## 2. The verdict is a precedence, not a score

Evidence carries an explicit `blocking` flag, and the verdict is the **first
matching blocking code** in a fixed order:

```
CORRUPTION                  -> REJECT_CANDIDATE
UNSAFE_SVG                  -> QUARANTINE
EPS_TOOL_LIMITATION         -> REQUIRES_TOOL | HEADER_ONLY_PARTIAL
EMBEDDED_RASTER_DEPENDENCE  -> NEEDS_VECTOR_RECONSTRUCTION
WATERMARK_SUSPICION         -> REFERENCE_ONLY
RASTER_RESOLUTION           -> REFERENCE_ONLY
COLLECTION_SHEET_AMBIGUITY  -> NEEDS_CLEANUP
VECTOR_RASTER_BALANCE       -> NEEDS_CLEANUP
UNSUPPORTED_FEATURES        -> NEEDS_CLEANUP
PATH_CLEANLINESS            -> NEEDS_CLEANUP
(otherwise)                 -> TECHNICALLY_READY | TECHNICALLY_USABLE_WITH_CAVEATS
```

No blending, so every verdict is traceable to the one evidence item that caused it
(`caused_by`), and the same artefact + config always yields the same verdict.

## 3. Source vs candidate readiness

Both are computed and both are kept. Three rules, and the third is the subtle one:

1. **Safety/tool blockers propagate** parent → candidate (`CORRUPTION`,
   `UNSAFE_SVG`, `EPS_TOOL_LIMITATION`). A candidate cannot be cleaner than a file
   we cannot safely or fully read.
2. **Quality judgments never propagate upward,** and a clean parent never rescues a
   poor candidate (a small crop off a pristine sheet is still a small crop).
3. **A page-level quality judgment binds only the candidate that IS that page.**
   "Raster covers 70 % of the *surface*" describes the whole surface. It rightly
   blocks a whole-file candidate (this is how the JPEG-shell verdict works — the
   candidate *is* the embedded raster). It must **not** block a clean pure-vector
   cluster cut out of that page: a cluster sitting away from the embedded image is
   not itself raster-heavy. So for **sub-candidates**, source geometry evidence is
   carried as **non-blocking context**, and the candidate is judged on its own.

Verified through the real `score_entry` pipeline (not just the merge helper): a
raster-heavy page with two clean vector clusters returns `NEEDS_CLEANUP` for the
**source** while its clusters return `TECHNICALLY_READY` /
`TECHNICALLY_USABLE_WITH_CAVEATS`, each keeping the parent's verdict visible but
not binding. The JPEG-shell whole-file case still returns
`NEEDS_VECTOR_RECONSTRUCTION`.

## 4. Resolution: pixels decide, DPI does not

Effective resolution is measured on the **candidate crop**, because the crop is
what would be reused. Bands: `HIGH_RES_CANDIDATE` ≥2000 px · `SCREEN_READY`
≥1000 · `LOW_RES_REFERENCE` ≥400 · `TOO_LOW` <400 (long edge).

- **Low or absent DPI metadata never rejects a high-resolution file.** DPI is
  recorded, never decisive.
- **Nothing is called print-ready from pixels alone.** Print suitability needs an
  intended physical size and the resulting PPI, which we do not have for rasters,
  so `print_suitability = UNDETERMINED_REQUIRES_PHYSICAL_SIZE`.

## 5. Pattern: the seam is measured against the local edge step

A seamless tile's last column becomes the neighbour of its first column, so the
wrap difference should be no bigger than **an ordinary one-pixel step at that
edge**. Normalising by the *mean* gradient instead fails a genuinely seamless tile
whose wrap lands on a steep part of the design (a perfect sinusoid scored 1.57
that way; against the local edge step it scores **1.01**, as theory predicts).

Two guards keep the verdict honest:

- **Flat-margin vacuity.** Artwork floating in white space "wraps" trivially — any
  flat margin matches any other. Such tiles return `REPEAT_TYPE_UNCERTAIN`, never
  `SEAMLESS_LIKELY`. Without this guard the pilot produced **12 false
  `SEAMLESS_LIKELY`** verdicts.
- **A crop is not a tile.** A repeat verdict describes a tile, so a crop out of a
  multi-asset source returns `REQUIRES_HUMAN` rather than a fabricated verdict.
  The tile verdict is therefore computed at **source** level — a pattern file that
  segments into motifs is still a tile as a whole.

Half-drop / brick is probed by comparing the last column against a **rolled copy
of the first column** (the neighbouring tile is offset). Rolling the tile itself
and re-measuring reproduces the same seam and proves nothing.

`SEAMLESS_LIKELY` may be machine-emitted but is **capped at 0.75 confidence** and
never implies reusability. Filename words (`seamless`, `pattern`, `tile`) are
**supporting evidence only** and can never determine the verdict.

## 6. Watermark: a positive signal is required

Suspicion needs a *positive* signal — stock-provider name, preview label, repeated
low-opacity overlay residual, or an edge text band. **Low resolution alone
contributes zero** and can never make a file suspected; it may only corroborate a
positive signal. Output is always `WATERMARK_SUSPECTED` + confidence + evidence +
a blank `human_confirmed` — never a statement of fact.

## 7. EPS

EPS contributes header facts only. C2b does **not** score path cleanliness, vector
complexity, segmentation quality, recolorability or seamlessness from an EPS
header. Every EPS candidate is `HEADER_ONLY_PARTIAL` (header data present) or
`REQUIRES_TOOL`, and an invariant asserts **no EPS candidate is ever
`TECHNICALLY_READY`**.
