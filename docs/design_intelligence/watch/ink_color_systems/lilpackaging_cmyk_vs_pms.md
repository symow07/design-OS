# What are CMYK Process Colours and What is a Pantone PMS Spot Colour? (Lil Packaging)

## Source

- Title: What are CMYK process colours and what is a pantone PMS spot colour? Lil packaging eCommerce FAQs
- Channel: Lil Packaging Ltd (799 subs; UK e-commerce packaging manufacturer's
  FAQ series, Sep 2020 — a printer talking with physical samples in hand)
- URL: https://www.youtube.com/watch?v=VLuYCBBqDT4
- Duration: 3:53 · Watched: 2026-08-24
- Transcript source: auto captions (tabbed panel, shadow-root scrape)
- Detail mode: transcript-only

## Claims

1. `t=0:14`–`t=0:29` CMYK (cyan/magenta/yellow/black) is how "basically all
   photographic visualized print" is printed — the print-side equivalent of
   RGB on screens.
2. `t=1:23`–`t=1:50` The PMS (Pantone Matching System) range is described as
   ~3,000 color references; CMYK can get "pretty near" a match to any of them.
3. `t=2:47`–`t=2:59` The printer's working rule of thumb: a CMYK simulation of
   a Pantone color gets "about **95 to 98% color accuracy**"; for an exact
   color, use an actual spot ink.
4. `t=2:00`–`t=2:27` Real-world hybrid example: a brand prints photographic
   imagery in CMYK but adds a **fifth ink station** — a spot red — solely to
   keep the logo color exact (brand-identity red too critical to trust to
   process build).
5. `t=3:09`–`t=3:29` Substrate shifts spot color too: the SAME purple spot ink
   printed on coated board vs uncoated tissue looks visibly paler on uncoated —
   "anything that isn't coated absorbs a lot of the ink."
6. `t=2:32`–`t=2:43` Why process builds vary: the color is an overlap of tiny
   dots of four inks, so there is inherent variation run to run.

## Engine hooks

- Claim 4 is the decision pattern the OS should encode: `CMYK + spot` is not
  either/or — the standard premium-brand build is process for imagery plus one
  spot for the brand color. For M7's palette, the brand color should carry a
  PMS reference in the spec even when artwork is emitted as CMYK.
- Claim 5 couples ink and substrate: a PMS number does NOT pin appearance —
  coated vs uncoated shifts it (this is why Pantone publishes C/U variants).
  Any engine color spec line must carry substrate context (pairs with the
  Label Apeel substrate note and glass in-melt vs applied color axis).
- Claim 3 gives a citable accuracy band (95–98%) for the "do we need a spot
  ink?" question — use as a printer's heuristic, not a measured ΔE.
- Claims 4+6 restate from the printer's side what PAPP/InDesignology said from
  prepress: each spot = a plate/station = cost; spots must be deliberate
  (spot-swatch-equals-plate preflight rule converges from a third source).

## Limits

- One printer's informal explainer; "3,000 colors" and "95–98%" are heuristics,
  not Pantone's official figures (PMS Formula Guide is ~2,390 colors as of the
  2023 edition — the order of magnitude matches, the number is loose).
- Corrugated/e-commerce packaging context, not cosmetics cartons; no ΔE or
  measurement evidence.
- Auto captions rough; physical samples he shows (penguin box, purple on
  coated vs tissue) are narrated but not frame-captured.
- Conflicts: none; opens the ink_color_systems domain.
