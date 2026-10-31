# Blender Mockup from a Dieline — fold-the-flat-artwork workflow

## Source

- Title: How to Make a Packaging Mockup from Your Dieline in Blender
- Channel: (packaging-design Blender tutorial; Blender 4.3 UI visible)
- URL: https://www.youtube.com/watch?v=hbiLBIQmzAs
- Duration: 5:37 · Watched: 2026-08-24 · Transcript: NONE (no captions) · Frames:
  11 @ 1 frame/30s (b1_01–b1_11) — all timestamps approximate, ±30s

## Claims

1. [frame b1_01, ≈0:00–0:30] Start state: the complete flat dieline WITH final
   artwork (a "nourish" carton — panels, glue flap, top/bottom flaps all
   visible) imported into Blender as a textured plane in orthographic view —
   the print file itself is the 3D source.
2. [frames b1_03, b1_05, ≈1:00–2:00] Edit-mode surgery: the plane's mesh is cut
   along panel boundaries (edge loops placed at fold lines, corner-radius
   curves traced around flap contours) — the mesh topology is made to match
   the dieline's fold geometry before any folding.
3. [frame b1_05, ≈2:00] Artwork detail visible: regulatory panel (MADE IN
   EGYPT / BATCH NO / MNF DATE / EXP DATE / EDA Notification No) — real
   carton artwork with mandatory furniture used as the working file.
4. [frame b1_07, ≈3:00] Folding: panels and flaps rotated up around fold-line
   edges into the erected carton — a partially folded state shows side panels
   up, top flaps still open (the digital twin of hand-folding a sample).
5. [frames b1_09, b1_11, ≈4:00–5:00] Result inspection: close-up perspective
   views of folded edges — artwork continuity across the fold and edge
   thinness are what get checked; the model reads as a thin single-surface
   shell.

## Engine hooks

- Claims 1, 2, 4 → the fold-transform pipeline in reverse: this manual Blender
  workflow (cut mesh at fold lines → rotate panels) is EXACTLY what the OS's
  dieline engine can automate — the dieline's fold-line data already encodes
  the mesh cuts and rotation axes. A generated dieline + artwork could emit a
  folded 3D preview mechanically (same family as the folded-orientation
  transforms: design verified in the assembled state).
- Claim 5 → mockup QA checks: artwork continuity across folds and correct
  panel adjacency are the visible failure modes a folded preview catches
  before print.
- Claim 3 → corroborates the mandatory-furniture zones (batch/expiry/
  notification fields) appearing on a real cosmetics carton's back panel.

## Limits

- Frames-only note (no captions): timestamps ±30s; narrated tips, exact
  modifier names, and shortcut workflow are lost — only on-screen actions are
  claimed. Single tuck-end carton example; no render/lighting stage shown in
  sampled frames.
- No conflict with committed authorities.
