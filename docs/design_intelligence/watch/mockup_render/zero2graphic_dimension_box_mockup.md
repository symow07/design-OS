# Basic Packaging Mockup in Adobe Dimension CC (Zero2Graphic)

## Source

- Title: How to Create Basic Packaging Mockup in Adobe Dimension CC
- Channel: Zero2Graphic (82.4k subs; Feb 2021 screen-recorded tutorial, 50k
  views)
- URL: https://www.youtube.com/watch?v=XAj8BBaQoYg
- Duration: 9:31 · Watched: 2026-08-24
- Transcript source: NONE — video has no captions at all (no "Show transcript"
  button; music-only tutorial)
- Detail mode: FRAMES-ONLY — 5 frames at ~0:20, 1:30, 3:30, 7:40, 8:55

## Claims

1. `t≈0:20` (frame) Dimension ships a **starter-asset packaging library**:
   Square/Round/Tall/Cube Box, Coffee Cup, Beverage cans, Drink Carton, Coffee
   Bag, Food Pouch, Food Bag, Takeout Box, Food Can, Tube, Gift Bag, Small
   Jar, Twist Jar, Twist Can, bags w/ handles — parametric packaging primitives,
   no modeling required.
2. `t≈1:30` (frame) Model surface = **Box Material** node with PBR properties:
   Base Color, Opacity, **Roughness (50% default)**, Metallic, Glow, Normal,
   Translucence, plus texture Offset/Repeat.
3. `t≈3:30` (frame) Artwork lands as imported flat images (jpg/png exports,
   one file per panel: PG2-01…PG2-04) — each import becomes a **Graphic layer**
   stacked on the material in the Scene tree, one per box face.
4. `t≈3:30` (frame) Graphic properties: **Placement: Decal**, Scale X/Y %,
   rotation, own Opacity/Roughness/Metallic — artwork is positioned as decals
   on faces, NOT wrapped via a UV dieline.
5. `t≈7:40` (frame) Scene composition in real units: selected box shows
   **Size X 5cm Y 10cm Z 10cm**, Position/Rotation/Scale fields, Pivot=Bottom;
   two dressed boxes tumbled mid-air with rotate gizmo (floating-product hero
   shot).
6. `t≈8:55` (frame) **Render tab**: Local vs Cloud (beta) render, Quality
   preset (Medium), export **PSD 16-bit/channel** or PNG; progressive
   ray-trace preview resolves from noise ("Estimating…" status).

## Engine hooks

- Third mockup route alongside the two Blender routes (wave 3): Dimension =
  the LOW-EFFORT route — starter primitive + per-face decal images + PBR
  sliders + cloud render. No dieline fold, no UV work. Tradeoff: decal
  placement means NO dieline fidelity — panel art is eyeballed onto faces, so
  it validates LOOK, not artwork geometry.
- Claim 3 defines the handoff format for this route: the prepress emitter's
  per-panel exports (one png/jpg per face) are directly consumable — engine
  should emit per-panel rasters in addition to the full dieline PDF.
- Claim 2+6: PBR Roughness/Metallic + 16-bit PSD export = the finish-preview
  hooks; matte vs gloss vs foil approximated by Roughness/Metallic before
  paying for physical proofs. Pairs with print_finishing notes.
- Claim 5's real-cm Size fields: the mockup can carry the M7 carton's true
  dimensions — engine mockup spec should pass physical dims, not just ratios.
- Route selection rule for the engine: Dimension for fast client-facing hero
  renders; Blender fold-the-dieline when dieline accuracy must be validated.

## Limits

- FRAMES-ONLY, no narration existed at all; parameter values (Roughness 50%,
  cm sizes) read from stills — defaults vs deliberate choices unknown.
- 2021 tutorial; Adobe has since deprecated/folded Dimension into Substance
  3D — UI may not match current tooling (unverified).
- Generic coffee-box demo; no cosmetics-specific geometry.
- Conflicts: none; complements (not contradicts) the Blender routes — different
  fidelity tier.
