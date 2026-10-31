# Why Don't Printed Colors Match the Screen? — 5 Things (Oppaca Tube)

## Source

- Title: Why don't printed colors match what I see on the screen? (5 things to
  consider)
- Channel: Oppaca Tube (7.68k subs; host "Stefan from label Oddo" [caption
  garble, likely Labelado]; May 2020 talking-head, 16.6k views)
- URL: https://www.youtube.com/watch?v=3FzkYe2sDQ8
- Duration: 7:36 · Watched: 2026-08-24
- Transcript source: auto captions (stuck spinner through 5 attempts; populated
  after Chapters→Transcript tab re-click + third play-kick)
- Detail mode: transcript-only

## Claims

1. `t=0:57`–`t=1:33` #1 Opposite base color models: monitors mix RGB light,
   printers mix CMYK ink — same hues, different production.
2. `t=1:33`–`t=2:44` #2 Monitor calibration: every screen in an electronics
   store shows the same content differently. Professional printers calibrate
   monitors in-house or via an external service — named tool: **i1Display Pro
   (X-Rite)** — optimizing contrast, brightness, **color temperature**.
3. `t=2:44`–`t=3:38` #3 Paper/substrate influence: papers differ in ink
   absorption. Mirrors the Pantone split — **coated** (smooth; glossy plastic
   or coated paper) prints brighter; **uncoated** "acts like a sponge,"
   absorbs more, dulls the same color.
4. `t=3:38`–`t=3:52` A professional printer changes their own SCREEN settings
   depending on whether the job prints coated or uncoated.
5. `t=3:55`–`t=4:47` #4 Choose the right printing partner: color-management
   settings in design software help, but the printer "knows where to touch a
   graphic file" — can even get brighter colors on uncoated. "Always trust
   your professional printers."
6. `t=5:00`–`t=5:13` #5 **Do a test print** — costs a small sum, "but at least
   you will print in the end what you really wanted."
7. `t=6:31`–`t=7:10` Bracketed test-print recipe: print the same artwork in
   the target PMS plus ADJACENT numbers (**199 / 200 / 201**) — on a weird
   substrate (e.g. pearlescent) the swatch that LOOKS like your intended 200
   may actually be the 201; pick by eye from the printed set, then run the
   job — "avoid reprinting hundreds and hundreds of labels."

## Engine hooks

- Claim 7 is the actionable one: BRACKETED PROOFING. The engine's proof-request
  emitter should offer a "±1 PMS bracket" option whenever substrate ≠ plain
  coated paper — direct extension of Ryonet's adjacent-PMS fallback and the
  proof-approval-is-contract rule (wave 5), now with the concrete N−1/N/N+1
  recipe.
- Claim 3 finally explains WHY every PMS number ships as C/U pairs (wave-6
  ink_color_systems recorded the split; this gives the absorption mechanism).
  Engine rule: a declared PMS without a C/U suffix is an incomplete spec —
  preflight should reject or ask.
- Claim 2 adds the monitor-side leg the corpus lacked: color QC has TWO
  instruments — spectrophotometer for output ΔE (eguru note), colorimeter
  (i1Display-class) for the screen. Engine's color workflow doc should state
  that unproofed on-screen approval is invalid unless the monitor is
  calibrated — one more reason owner approval binds on PHYSICAL samples.
- Claims 5+6 converge with the standing owner-review guidance: software
  color management < printer craft < physical test print. The hierarchy is
  now three-source convergent (Ryonet, Lumi/wave-5 prepress, here).

## Limits

- Label-industry marketing channel; "trust your printer" is also a pitch.
- 2020, hobbyist-level depth: no ICC profiles, rendering intents, or soft-
  proofing standards (the actual mechanism between the 5 factors is skipped).
- Captions garble: "peepers"=papers, "panettone"/"Pantone e"=Pantone,
  "monster"=monitor, "I 1 display Pro from X right"=i1Display Pro, X-Rite,
  "finished rating" likely "finished print" — interpreted.
- PMS 199/200/201 adjacency is illustrative, not a claim that all PMS numbers
  are perceptually sequential.
- Conflicts: none; completes color_management's screen→print chain.
