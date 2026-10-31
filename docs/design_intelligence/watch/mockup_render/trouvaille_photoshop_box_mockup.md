# Realistic Box Mockup in Photoshop (Trouvaille Digital)

## Source

- Title: Realistic Box Mockup Photoshop Tutorial You'll EVER Need (2024 Update!)
- Channel: Trouvaille Digital (13.7k subs; May 2024 tutorial, 5.9k views)
- URL: https://www.youtube.com/watch?v=BophUdnrEok
- Duration: 3:50 · Watched: 2026-08-24
- Transcript source: auto captions (panel stuck on spinner through 4 attempts,
  populated after second play-kick — same "keep re-walking" behavior as Domino)
- Detail mode: transcript-only

## Claims

1. `t=0:15`–`t=0:26` Input = a PHOTO of a blank box + a flat design split into
   panels (front + sides handled as separate pieces).
2. `t=0:26`–`t=0:48` Core mechanic per panel: copy panel art into the doc →
   Cmd-click thumbnail to select → cut → **Filter → Vanishing Point** →
   create a perspective plane by clicking the 4 corners of the box face.
3. `t=0:58`–`t=1:19` Paste (Cmd+V) INSIDE Vanishing Point, then Cmd+T to
   transform/place the art on the defined plane — art inherits the photo's
   perspective.
4. `t=1:23`–`t=2:05` Repeat per face: each side gets its own Vanishing Point
   plane via the **Create Plane tool**; one layer per face.
5. `t=3:00`–`t=3:06` Realism step 1: select all art layers → blending mode
   **Multiply** (photo's shadows/texture show through the art).
6. `t=3:09`–`t=3:19` Realism step 2: per layer, Blending Options →
   **Blend-If**: drag the underlying-layer WHITE slider left, **Alt/Option-drag
   to split** the slider for a smooth transition — photo highlights punch
   through the art.
7. `t=3:33`–`t=3:38` Positioning claim: "with such an easy trick you can add
   any design to your mockups in no time."

## Engine hooks

- Fourth mockup route, cheapest of all: photo + Vanishing Point + Multiply +
  split Blend-If. No 3D at all. Route ladder for the engine is now:
  (1) Photoshop-on-photo (minutes, zero 3D, needs a good box photo),
  (2) Dimension starter-asset + decals (fast hero render),
  (3) Blender UV-cube, (4) Blender fold-the-dieline (dieline-faithful).
  Mockup spec should name which tier a deliverable needs.
- Claims 5+6 are the transferable craft: Multiply + split Blend-If is the
  standard recipe for keeping substrate shadows/highlights alive under
  flat art — applies to ANY photo-based mockup the engine emits, including
  smart-object template PSDs.
- Claim 1 reinforces the per-panel export rule from the Dimension note: this
  route also consumes per-face art pieces, not the full dieline — third
  consumer of per-panel rasters (Dimension decals, Vanishing Point panes).
- Limitation the engine must respect: photo-based route validates PERSPECTIVE
  and mood only — no geometry check, no real dimensions; never use it for
  dieline sign-off.

## Limits

- 3:50 quick tutorial; no color management, no lighting/reflection treatment
  beyond Multiply+Blend-If; assumes a usable blank-box photo exists.
- Small channel, generic box demo; "realistic" is their claim.
- Captions clean but sparse (long [Music] gaps where actions happen silently —
  plane-corner placement only evidenced by narration around it).
- Conflicts: none; adds the low-end tier to mockup_render.
