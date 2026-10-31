# Packaging Design Tutorial — Create Dieline Step by Step (Munes Studio)

## Source

- Title: Packaging Design Tutorial in Illustrator — Create Dieline Step by Step
- Channel: Munes Studio
- URL: https://www.youtube.com/watch?v=D6Q10DQwxDI
- Duration: 4:41 · Watched: 2026-08-24 · Transcript: auto-captions (en) · Frames:
  none (fully procedural; geometry stated verbally with dimensions)

## Claims

1. [t=0:21] Dimension convention: client box specs arrive as W × D × H — face
   width, side-panel depth, height (example 10 × 6.5 × 22.5 cm) — "the box
   dimension always works this way."
2. [t=0:21–1:02] Panel derivation: front/back = W × H; side panels = D × H; the
   four body panels are copies in a strip (front, side, back, side), built by
   alt-shift duplicate + width edit — all panel sizes derive from the three input
   dims, nothing is drawn free-hand.
3. [t=1:02–1:22] Top lid = W × D (lid depth equals the side-panel depth).
4. [t=1:22–1:43] Tuck edge: a 1.5 cm flap on the lid that goes INSIDE the box after
   closing; its outer corners are pulled in/rounded (direct-selection on anchor
   points) so it tucks.
5. [t=1:43–2:03] Glue flap: 1.5 cm wide strip on the strip's free edge, top and
   bottom corners chamfered inward (shift-arrow nudges) — angled so it doesn't
   foul the fold.
6. [t=2:03–2:24] Symmetry rule: bottom flap = copied top flap, FLIPPED; dust flaps
   (side flaps of the closures) ≈ half the tuck-flap depth (4 cm here); their
   corners chamfered by counted arrow-key nudges [t=2:45–3:25], then mirrored to
   bottom and left.
7. [t=3:25–3:46] Layer separation: dieline layer (cut) and a separate creasing
   layer — interior fold lines cut from the outline, pasted in front, made DOTTED
   and recolored. Third layer for bleed [t=3:46].
8. [t=3:46–4:08] Bleed construction: outer outline → fill → Object > Offset Path
   0.25 in, joins ROUND, expand, compound path — bleed is generated geometrically
   from the cut path, not drawn.

## Engine hooks

- Claims 2–6 → parametric carton generator: an entire tuck-end carton dieline is a
  deterministic function of (W, D, H) plus small constants (tuck 1.5 cm, glue
  1.5 cm, dust ≈ tuck/2, chamfer nudges) — direct blueprint for the OS's dieline
  engine archetype; matches the PackMojo one-piece claim.
- Claim 7 → layer/linetype convention: cut = solid, crease = dotted, separate
  layers — third independent source (PackMojo, full-process video) for this
  convention; safe to hard-code in exports.
- Claim 8 → bleed can be auto-generated as a round-join offset of the cut path —
  checkable rule for the export pipeline.

## Limits

- One studio's constants (1.5 cm tuck/glue, 0.25 in bleed) — proportions are
  starting defaults, not standards; no board-thickness compensation mentioned
  (the OS's compensation handling is stricter).
- Straight tuck-end box only; no lock-bottom/crash-bottom geometry.
- No conflict with committed authorities.
