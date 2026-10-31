# Quick 3D Packaging Mockup in Blender — UV-unwrap-a-cube workflow

## Source

- Title: Quickly Design 3D Packaging Mockup in Blender
- Channel: (Blender tutorial with on-screen caption text; "Sarina Feminine
  Body Scrub" carton example)
- URL: https://www.youtube.com/watch?v=P82jUJBr1p4
- Duration: 5:39 · Watched: 2026-08-24 · Transcript: NONE (no captions track) ·
  Frames: 11 @ 1 frame/30s (b2_01–b2_11) — timestamps approximate, ±30s;
  some guidance recovered from burned-in on-screen text

## Claims

1. [frame b2_01, ≈0:00–0:30] Workflow start: a default cube scaled to box
   proportions; on-screen text: "Firstly, mark the seams" — UV seams on the
   cube edges, not a dieline import, are the basis (opposite approach to the
   fold-the-dieline workflow).
2. [frame b2_03, ≈1:00–1:30] Per-face artwork files: the file browser shows
   the artwork exported as SEPARATE images per panel (body_side.png, artboard
   copies, body_scrub.png) — panel artwork mapped face-by-face rather than one
   full-dieline texture.
3. [frame b2_05, ≈2:00–2:30] Textured result: the box shows the full front
   design (brand, florals) via Principled BSDF material with image texture
   node; shader node editor open below the viewport.
4. [frame b2_07, ≈3:00–3:30] Backface problem + fix (on-screen text): "textures
   are appearing in the inner side of the package… use the backfacing or
   solidify modifier. I use solidify modifier to create more realistic" —
   SOLIDIFY gives the shell real thickness so the interior reads as board, not
   mirrored artwork.
5. [frames b2_09, b2_11, ≈4:00–5:00] Solidify modifier configured (thickness/
   offset visible in modifier panel) on the finished box; front orthographic
   check of the textured face with the node graph still live.

## Engine hooks

- Claims 1, 2 vs the fold-workflow note → TWO mockup routes for the OS:
  (a) fold-the-dieline (geometry-faithful, catches fold errors) and
  (b) UV-cube (fast, per-panel textures, good for concept renders). The engine
  should pick per purpose: preflight verification wants (a); concept
  presentation wants (b).
- Claim 4 → render-realism rule: give shells thickness (solidify) so open-box
  and edge shots read as board — matches the physical teardowns' attention to
  edge finishing (V-cut note: edges are where quality is read).
- Claim 2 → artwork export requirement: the artwork generator should be able to
  emit per-panel crops as well as the full dieline raster — two consumers, two
  formats.

## Limits

- Frames-only + burned-in text: timestamps ±30s; spoken detail lost. Claims 1
  and 4 quote on-screen captions directly (higher confidence than frame
  inference). No lighting/camera/render-settings stage in sampled frames.
- No conflict with committed authorities.
