# How to Design on a Folding Carton Dieline — Packaging Design 101

## Source

- Title: How to Design on a Folding Carton Dieline | Packaging Design 101
- Channel: PackMojo
- URL: https://www.youtube.com/watch?v=Bf7XPpnwQrE
- Duration: 2:52 · Watched: 2026-08-24 · Transcript: captions (en) · Frames: 11 uniform @ ~15s, 640px

## Claims

1. [t=0:37] A folding carton is made from ONE piece of paperboard, folded and glued —
   the dieline is a single flat sheet, not per-panel artboards.
2. [t=0:46] Bleed rule: artwork at any panel edge must extend BEYOND the dieline cut line.
3. [t=0:52–1:18] Two valid front orientations. Option 1: tuck tab opens toward viewer
   (tab side = front). Option 2: tab opens away (tab side = back). Choice repositions
   the side panels AND — Option 1 only — requires the exterior TOP panel artwork to be
   inverted (rotated 180°).
4. [t=1:30 + frame ~1:00] Template ships as two spreads on one document: "Exterior" and
   "Interior" dielines stacked, header carries structure + dimensions
   ("Folding Carton (Snap Lock Bottom) 4" × 4" × 8" (outer)"). Interior printing is a
   first-class layer, not an afterthought.
5. [t=1:51–2:05 + frame ~2:00] Bottom-closure mechanisms hide flap areas when closed.
   Four shown: Snap Lock, Auto Bottom, Reverse Tuck End, Straight Tuck End — each hides
   DIFFERENT parts of the bottom flaps. Rule: no important design/detail on the base.
6. [t=2:10–2:21] Interior artwork: all panels same orientation, including top (no
   inversion), but avoid important design on interior bottom — overlap hides it.
7. [t=2:27] Final gate: re-check finished art against the dieline orientation guide
   before handoff.
8. [frame ~2:30] Production checklist (PackMojo): document in CMYK color mode; Pantone/
   spot colors converted to CMYK with the Pantone C code recorded.

## Engine hooks

- Claims 3, 5, 6 → dieline/carton generation and the carton archetype authority
  (`docs/qualification/`): panel orientation map should be a per-archetype,
  per-option (1/2) lookup, and each closure type should carry a "hidden zone" mask
  that artwork placement must avoid. Repo already uses `straight_tuck_end_carton/1.1`
  (Phase 2A-7 baseline) — claim 5 says its hidden-flap mask differs from snap lock.
- Claim 2 → label sheet / print-ready export: bleed as a hard preflight check.
- Claim 3 (top-panel inversion) → any render or VQR check that unfolds/refolds carton
  art must apply the 180° top rotation for Option-1 fronts or the fold preview lies.
- Claim 8 → export pipeline: CMYK mode + recorded Pantone C equivalents at handoff.

## Limits

- Vendor tutorial (PackMojo) for their own templates; panel naming and the two-spread
  layout are their convention, not an industry standard. Hidden-zone geometry is
  illustrated, not dimensioned — no numeric masks can be extracted from this video.
- Does not establish anything about bottle/jar labels, wrap geometry, or finishing.
- No conflict found with committed authorities; complements (does not amend) the
  carton archetype authority and the Phase 2A-7 accepted geometry.
