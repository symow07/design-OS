# Packaging Design in Illustrator — Dielines, Bleed Guide & Cut Lines

## Source

- Title: Packaging Design in Illustrator — Dielines, Bleed Guide & Cut Lines
- Channel: (Illustrator tutorial channel)
- URL: https://www.youtube.com/watch?v=HvTqMxI-MPI
- Duration: 8:43 · Watched: 2026-08-24 · Transcript: auto-captions (en) · Frames:
  none (procedural; dimensions stated verbally)

## Claims

1. [t=0:28–1:43] Same panel-derivation pattern as the other dieline sources, in
   inches: face 3.15 × 5.32 in, side 1.75 in wide, four-panel strip by alt-drag
   duplication with smart guides.
2. [t=1:43–2:13] Top/bottom enclosure panels: same width as face, depth 1.75 in
   (= side-panel depth — corroborates the lid-depth-equals-side-depth rule).
3. [t=2:13–2:55] Dust flaps: height 1.2 in, width = side-panel width; duplicated
   and mirrored to all four closure positions.
4. [t=2:55–4:17] Tuck flap: W × 0.65 in with corners rounded via direct-selection
   corner widgets; bottom copy made by Transform > Reflect (horizontal) — mirror,
   don't redraw. Flap edges chamfered by counted shift-arrow nudges on all four
   flaps [t=4:17–4:42].
5. [t=4:42–5:24] Glue/tuck edge strip 0.65 in wide, corners chamfered by
   shift-arrow nudges.
6. [t=5:24–6:32] Bleed as a derived layer: copy ALL panel outlines to a new layer,
   Pathfinder unite, then Object > Offset Path +0.125 in = the bleed guide —
   generated from geometry, not drawn.
7. [t=6:54–8:11] Line-role encoding by color + style: Pathfinder OUTLINE mode on
   the united shape gives the cut line (one color); interior fold lines selected
   panel-by-panel and set to RED DASHED via Stroke > Dashed Line — cut vs fold
   distinguished by both color and dash.

## Engine hooks

- Claims 1–2 → third independent confirmation of the parametric tuck-end pattern
  (panel strip from W/D/H, lid depth = side depth) — the carton archetype is now
  triangulated (PackMojo, Munes, this).
- Claim 6 → bleed offset differs across sources (0.125 in here vs 0.25 in Munes)
  → bleed must be a PARAMETER with printer-confirmed value, not a constant —
  candidate spec-sheet field, resolved per supplier.
- Claim 7 → export convention: cut/crease distinguished by color AND dash pattern
  (not dash alone) — adopt both channels in generated dielines for robustness.

## Limits

- Beginner tutorial; no board thickness, no glue-flap taper rationale, no
  manufacturing tolerances. Values in inches; unit consistency matters when
  merging with metric sources.
- No conflict with committed authorities; overlaps heavily with Munes note —
  value is in the corroboration and the differing bleed constant.
