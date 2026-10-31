# Building a Rigid Box — Part 1 — Gluing Up the Box (eric otoole)

## Source

- Title: Building a Rigid Box - Part 1 - Gluing Up the Box
- Channel: eric otoole (415 subs; hobbyist/craft bookbinding-style build, Mar 2021)
- URL: https://www.youtube.com/watch?v=mgexhPVmogo
- Duration: 8:35 · Watched: 2026-08-24
- Transcript source: none — the "Show transcript" button exists but the panel
  refused to populate through every route tried this session (DOM click, trusted
  click, forced visibility, innertube get_transcript → FAILED_PRECONDITION,
  timedtext → empty/POT). Claims rest on frames + the video description.
- Detail mode: FRAMES-ONLY — 7 frames at ~0:42, 1:38, 2:52, 4:21, 5:46, 7:06, 8:16
- Description text (verbatim, on-page): "This video describes how to build a rigid
  cardboard box with a hinged lid. The final box will have a paper wrap and lining.
  The first step is cutting the walls of the box to size, squaring them off, and
  gluing them up."

## Claims

1. `description` Set-up rigid box sequence: cut walls to size → square them off →
   glue up; wrap and lining come AFTER the carcass is built (Part 1 of a series).
2. `t=0:42` (frame) Walls are cut individually from chipboard/greyboard on a
   cutting mat with a knife; a sanding block sits on the bench for squaring edges.
3. `t=1:38` (frame) Assembly glue is PVA (Elmer's Glue-All bottle), applied along
   the EDGE of a wall piece by hand.
4. `t=2:52`–`t=4:21` (frames) Construction is base-plus-walls: walls stand on the
   base panel's face/perimeter and are butt-jointed at corners — the long wall
   overlaps the end grain of the short wall.
5. `t=5:46` (frame) White tape tabs are placed on wall faces at the joints —
   holding/reinforcing joints while the PVA dries.
6. `t=7:06`–`t=8:16` (frame) Result of Part 1 is a bare glued tray (four walls on
   a base, no wrap); a further panel is fit-checked against the finished tray.

## Engine hooks

- This is the `rigid_setup` archetype counterpart to the ZY Pack
  `rigid_collapsible` note: carcass built first as a permanent 3D tray, wrap and
  lining applied AFTER — decoration is a separate layer over a structural core.
  Directly opposite the collapsible flow, where the wrap is the hinge and comes
  first.
- Claim 4's butt-joint geometry is why set-up box walls have a caliper story:
  internal dimensions = base minus 2× board caliper on the long axis where walls
  overlap. Any engine internal-dimension math for rigid boxes must state which
  walls overlap which.
- Claim 1's order (carcass → wrap → lining) is the hand-craft version of the same
  separation the luxury_teardowns notes show industrially: structure, wrap, and
  fitment are independent spec lines in a rigid-box package.

## Limits

- Hobbyist single build, hand tools, no dimensions or board caliper stated in
  evidence; industrial set-up box lines use corner-staying machines, not tape tabs.
- Frames-only; no narration captured — anything said aloud about tolerances or
  measurements is not in evidence. Part 2 (lid) not watched.
- The tape-tab interpretation (claim 5) is visual inference from placement at
  joints; low stakes but marked accordingly.
- Conflicts: none; complements ZY Pack note via the setup/collapsible split.
