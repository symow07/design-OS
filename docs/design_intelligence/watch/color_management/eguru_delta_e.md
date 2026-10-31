# What is Delta E (E-GURU)

## Source

- Title: Color theory - What is Delta E value (How to get and what is color
  difference reading)
- Channel: E-GURU (1.49k subs; Jun 2022 slide explainer, 24k views)
- URL: https://www.youtube.com/watch?v=HsnOqqb3jtQ
- Duration: 2:21 · Watched: 2026-08-24
- Transcript source: auto captions (panel stuck 5 attempts, then populated —
  third video this wave with delayed-populate; slides also read as frames)
- Detail mode: transcript + 2 frames (~0:30 slide, ~1:05 formula)

## Claims

1. `t=0:15`–`t=0:29` **ΔE (Delta E / dE)** = mathematical measure of visible
   difference/error between two colors; used to sort "closeness" against a
   scanned sample; standard tool of industrial/commercial color QC.
2. `t=0:31`–`t=0:44` Smaller ΔE = closer match; **ΔE 0 = mathematically
   identical**; no negative values; range **0–100**.
3. `t=0:56`–`t=1:00` ΔE is defined **in L\*a\*b\* color space**; frame at
   ~1:05 shows the (CIE76) formula: **ΔE = √(ΔL² + Δa² + Δb²)**.
4. `t=1:39`–`t=1:42` Perception threshold claim: below **ΔE 0.3** the human
   eye can't recognize the change.
5. `t=1:26`–`t=1:50` Visual judgment is unreliable: surface finish, texture,
   gloss, plus the viewer's physical/mental condition all skew color reading.
6. `t=1:52`–`t=2:11` Therefore: **instrumental reading** — any
   spectrophotometer gives a ΔE reading **against a standard color**; ΔE (Lab)
   is more accurate than judging in non-uniform systems "such as RGB or CMYK."

## Engine hooks

- ΔE is the missing NUMBER for the corpus's color-accuracy talk: printers'
  "97% match" sales heuristics (wave-6 ink_color_systems) and drawdown
  approvals (labeltech) can now be specified as a tolerance — engine color spec
  should carry `delta_e_tolerance` against the declared PMS standard, not a
  percentage.
- Claim 6's "against a standard color" is the same shape as drawdown-vs-
  approved-standard QC: instrument + standard = the objective check; owner
  eyeballing proofs (Ryonet guidance) is the subjective layer on top.
- Claim 3 grounds why prepress works in Lab for brand colors: ΔE only exists
  in Lab — engine should store brand colors as Lab (or PMS→Lab) values, with
  CMYK/RGB as derived outputs.
- Practical band for specs (industry convention, NOT from this video —
  video only evidences the 0.3 imperceptibility claim): tolerance contracts
  commonly use ΔE ≤ 2 for brand-critical colors. Engine may propose but must
  cite it as convention, not this source.

## Limits

- Tiny channel slide-deck explainer; formula shown is CIE76 — newer ΔE2000
  weighting is not mentioned (the 0–100 range and 0.3 threshold are
  CIE76-era statements).
- "e stands for m fine dung german 4 sensation" = caption garble of
  "Empfindung, German for sensation" — interpreted.
- "0.3" threshold is one source's round number; other references say 1.0 JND.
- No packaging context; general color theory.
- Conflicts: none; opens color_management with the measurement unit.
