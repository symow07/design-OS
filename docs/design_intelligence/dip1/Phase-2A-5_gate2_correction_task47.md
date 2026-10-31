# Phase 2A-5 — Gate-2 Production Correction (task #47)

Task #47 (BBROSE Skynte Foundation) reached `awaiting_gate_2` with two
critical production failures: a raster decorative background and a dieline
that did not match the supplied manufacturing reference. Both are corrected;
**the task remains stopped at `awaiting_gate_2` and is machine-gated** — the
Gate-2 approve endpoint now refuses this output until every production check
passes.

Commits: `DIE-1` side-seam parametric archetype · `DIE-2` dimensional
reconciliation + structural comparison · `DIE-3` native vector artwork +
CMYK emission · `DIE-4` Gate-2 readiness validation, enforced · `DIE-5`
3D mockup + regeneration command + task-#47 regeneration.

## Corrected dieline

`skynte_foundation_tuck_carton/1.0` — a frozen parameter preset of the new
**side-seam straight-tuck archetype** (`apps/dielines/geometry/side_seam.py`,
DECISION-018/019/020). Structural truth = the supplied dimensions:

- panel sequence **glue | 32 side | 42 main | 32 side | 42 main** (the STE
  engine's glue|main|side|main|side order could never match; the locked STE
  reference remains byte-identical, untouched)
- manufacturing 32 × 42 × 140 drawn exactly; ECMA allowances re-expressed
  for the side-seam order (front = W, sides = D + t, back = W + 2t, +4t flat)
- board **t = 0.30 mm**, inferred from the supplied inner cross-section
  (31.4/41.4 = manufacture − 2t exactly); the previous output drew t = 0.35
- closure system: cubic-shoulder rounded tucks top AND bottom, 2t lock
  notches, **tuck-base entry slits** (5 mm per end, cut segments published in
  `slit_lines` and drawn on the cut layer/plate), angled dust flaps (3 mm
  base notch, 6 mm chamfer), tapered glue flap, per-hinge creases — no
  crease over a cut edge
- tuck height model corrected: **D + lip** per end (DECISION-019); the
  measured W × 1.227 factor is square-reference-only

### Dimension reconciliation (assumptions REPORTED, values never altered)

| set | supplied | model | delta | status |
|---|---|---|---|---|
| inner W/D | 41.4 / 31.4 | manufacture − 2t | 0 | MATCH (fixes t = 0.3) |
| inner H | 138.9 | 139.4 | −0.5 | assumption: closure headspace |
| outer W/D | 42.4 / 32.4 | 42.6 / 32.6 | −0.2 | assumption: score compression |
| outer H | 140.9 | 140.6 | +0.3 | assumption: closed flap stack |

Published template assumptions (not customer dimensions): tuck lip 16 mm,
entry slit 5 mm, DECISION-016 shoulder/dust/slit ratios pending a measured
Skynte die. All six collision checks pass (opposing dust clearance 1.6 mm,
dust-below-tuck 27.8 mm, tuck-lip entry clearance, slit web, bleed contour).

## Corrected artwork (Liquid Veil, native vector)

`apps/ire/compose_vector_art.py` — deterministic, zero image-model calls, no
screenshot tracing, no watermark. Editable full-bleed nude→sand gradient
(#E8C9B3 → #F0DECB), engraved liquid-pour Bézier streams + translucent veil
ribbons per surface (clipped to real flap outlines), live editable
typography ("Skynte Foundation" / "Fundación facial" — the previous output
printed the first 60 characters of the BRIEF as the product name), rose-gold
foil accent group, quiet back panel carrying the trilingual regulatory
sticker. All ink CMYK (emitter, sticker renderer, barcodes upgraded).
Census: **155 vector objects, 2 live text runs, 1 raster** — the official
BBROSE logo lockup only (flagged, non-decorative, not panel-sized; pending
the approved vector brand master).

## Gate-2 machine gate

`validators/production_readiness.py`, enforced in `Gate2ApproveView` for
strict outputs (409 `PRODUCTION_NOT_READY`, no override). Codes:
TEMPLATE_MISMATCH · STRUCTURE_CHECKLIST_MISSING · MISSING_CLOSURE_DETAILS ·
DIMENSIONS_UNRECONCILED · CLOSURE_COLLISION · INCOMPLETE_BLEED ·
RASTER_DECORATIVE_BACKGROUND · ARTWORK_INVENTORY_MISSING · RGB_ARTWORK ·
FORBIDDEN_PANEL_TEXT (catches truncated brief-title fragments) ·
PLACEHOLDER_REGULATORY_INFO · TEXT_BELOW_MINIMUM_SIZE ·
PRODUCTION_PDF_MISSING. Missing artifacts fail closed.

## Deliverables (job `3b876c60-ef77-4d55-8ac1-0c65361dde9d`, media/dielines/)

1. structure-only preview — `*_structural_comparison.pdf` p.1 (generated and
   gate-checked BEFORE graphics)
2. parametric spec — `*_spec.json` + full parameter table in the checklist
3. corrected dieline — `dieline_task_47_corrected.{svg,ai}`
4. native-vector design — `design_preview_task_47_corrected.ai`
5. CMYK production PDF — `dieline_task_47_corrected_production.pdf`
   (CutContour/Crease spot plates, prepress checks clean)
6. folded 3D mockup — `*_mockup_3d.png` (preview-grade)
7. panel map — comparison p.1 labels + checklist `parameters`/`panel_order`
8. flap/notch/lock inventory — checklist `flap_inventory`
9. dimensional validation report — checklist `reconciliation` + comparison p.2
10. raster/vector inventory — `*_artwork_inventory.json`
11. layer/swatch inventory — same file (`swatches`, node counts, font note)
12. Gate-2 readiness report — printed by `manage.py correct_dieline_output`

## Status

Task #47: **`awaiting_gate_2`, unchanged.** Readiness: **NOT READY** with
exactly one open failure — `PLACEHOLDER_REGULATORY_INFO`: the `ingredients`
field reads "To be confirmed according to the approved product formulation".
Real INCI copy must come from the customer; approval is mechanically blocked
until it does. The defective job `d4f613e6…` is preserved for audit.
