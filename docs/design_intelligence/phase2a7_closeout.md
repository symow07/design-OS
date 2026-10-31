# Phase 2A-7 — Selected-Concept Fidelity and Design-Memory Gate — CLOSEOUT

**Status: COMPLETE — accepted 2026-07-22.** Task #50 remains
`awaiting_gate_2`, unapproved.

## Accepted baseline

- Selected concept: GeneratedImage **#89**, variation **C_POWDER_CONSTELLATION**
  (direction d1, Editorial Soft Radiance).
- Geometry: **90 × 25 × 92 mm**, `straight_tuck_end_carton/1.1`
  (EXPLICIT_USER_CONFIRMATION, board compensation on).
- Font: **BarlowCondensed-Bold**
  (sha256 `79483069c602019259fd2215af033c60fb5c90f3071097839180337dc306223b`),
  status `APPROVED_FOR_TASK_CONCEPT_RECONSTRUCTION` —
  **FONT_LICENSE_EVIDENCE_REQUIRED_FOR_PRODUCTION stands.**

## Accepted commits

| Commit | Scope |
|---|---|
| `2534ddb` | CORR-7: selected-variation loader; powder_constellation language; declaration fidelity gate |
| `ff20e9e` | CORR-8: geometry-measured gate; .ai library + font intelligence; visual graph |
| `c00c003` | CORR-9: approvals recorded; live Barlow; browser-verified render fixes (prior iteration, preserved) |
| `a76f660` | CORR-10: metric-true sizing; shape-aware coverage; PDF-truth; 7-reference realization (ACCEPTED) |

## Final emitted measurements (accepted)

Product-name group 46% w × 46% h (BAKED 38.4 mm / POWDER 41.4 mm emitted
spans, PDF-verified) · logo/frame 38% w upper-left · 117 front particles ·
printed coverage 16.6% · centroid (0.69, 0.70) · lower-right share 77% ·
adjoining-side continuation 14 (12%) · opposite side 4 · flaps 0 ·
0 decorative rasters · 0 outlined text · 4 live text runs · vertical
POLVO HORNEADO live inside the right edge.

## Reference realizations (all seven)

Rasters #2/#7/#8/#10: REALIZED (palette incl. layered mint/ivory ground,
stacked hierarchy, particle density, grouped motif, separable finish
layers). `.ai` profiles #13 (YB-1022/BP6003), #11 (FB3093/FB3090),
#12 (FB-2060): REALIZED via whitespace discipline, panel organization and
density discipline descriptors; headline scale `NOT_DETECTABLE_IN_SOURCE`
(production `.ai` text is outlined). Concept-reference permission only —
no production use, no rights change.

## Tests and spend

Full suite **2,069 passed** at acceptance; golden fixture
`apps/pipeline/tests/test_phase2a7_golden_baseline.py` freezes the accepted
numbers (font hash, dominance, density, centroid, continuation, zero-raster
policy, PDF/measurement agreement). **Zero provider calls** across
CORR-7…10 (ApiCallRecord constant at 197).

## Frozen regression fixtures

Selected image #89 · stripe reconstruction and insufficient-fidelity
reconstruction under `media/rejected/` + `spec_sheet.rejected_outputs` ·
c00c003 iteration (git) · a76f660 accepted output on the PackagingOutput ·
material/AI approvals (ConceptReference rows) · selected-concept visual
graph, emitted-geometry report and realization map on the spec sheet.
**The accepted baseline is never rewritten silently.**

## Remaining Gate-2 production blockers (deliberate)

1. `FONT_LICENSE_EVIDENCE_REQUIRED_FOR_PRODUCTION` (Barlow licence evidence)
2. `MISSING_OUTPUT_INTENT` (printer's CMYK ICC profile)
3. Unverified regulatory/production data (INCI, confirmed net weight,
   shade, SKU/barcode confirmation, manufacturer/importer block)

Reopen task #50 only for: a baseline regression, verified production data,
the ICC profile, font licence evidence, or final Gate-2 preparation.
