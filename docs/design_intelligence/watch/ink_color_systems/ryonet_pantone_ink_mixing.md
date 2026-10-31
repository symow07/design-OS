# Mastering Pantone Color Mixing in Screen Printing (Ryonet)

## Source

- Title: Mastering Pantone Color Mixing in Screen Printing
- Channel: Ryonet (111k subs; screen-printing equipment/education house, Nov 2023)
- URL: https://www.youtube.com/watch?v=E8OfaUT2J9s
- Duration: 2:55 · Watched: 2026-08-24
- Transcript source: auto captions (tabbed panel, shadow-root scrape) + 1 frame
  (~0:20, formula software UI)
- Detail mode: transcript + frame

## Claims

1. `t=0:12`–`t=0:29` A Pantone spot ink is mixed from a **published formula**:
   pick the PMS number (2995 C here) in the ink system's software (FN-INK),
   choose batch size (1,000 g production / 100–200 g testers), click "load
   formula" — the recipe is looked up, not eyeballed.
2. `t=0:20` (frame) Formula card example: PANTONE 0131 @ 100 g = Mixing White
   94.60 g + Light Blue 0.63 g + Lemon Yellow 4.77 g — recipes are weighed to
   the hundredth of a gram, and one component can dominate (94.6%).
3. `t=0:49`–`t=0:55` Mixing is done on a scale reading to 0.01 g — precision
   is by weight, not volume.
4. `t=0:58`–`t=1:03` Procedure: add the largest-quantity ink first; zero the
   scale between components.
5. `t=1:44`–`t=2:00` Reason for largest-first: you can never scrape 100% off
   the container walls — losing a bit of the dominant component matters less
   than losing the smallest one (small components carry the color identity).
6. `t=2:02`–`t=2:21` The mixed color can still shift on the substrate: inks
   are partly translucent, so a dark shirt behind the ink changes it —
   printing an **under base** (white) prevents the shift.
7. `t=2:23`–`t=2:30` Pragmatic tolerance rule: if the mixed color doesn't look
   right, go one PMS shade darker or lighter in the book rather than fighting
   the mix.

## Claims → Engine hooks

- Claim 6 is the same physics as bottle decoration: spot ink over a dark or
  colored substrate needs an under base — directly relevant to silkscreen on
  amber/colored glass (cross-link bottle_decoration silkscreen note). Engine
  rule: any spot color spec over non-white substrate carries an implicit
  white-underbase line, which is an EXTRA print pass/plate (cost).
- Claims 1–3 show what a PMS number IS operationally: a weighed recipe. This
  grounds the ink_color_systems domain — "Pantone 2995 C" resolves to grams of
  base inks, which is why the INNORHINO press-prep/cleanup cost exists.
- Claim 7 is a designer-usable tolerance heuristic: adjacent PMS shades are
  the sanctioned fallback, not custom tweaking — worth carrying in any
  owner-review guidance about approving physical color samples.
- Claim 2's dominance structure (94.6% white) explains why pastels are
  mix-sensitive: tiny tint components carry identity (claim 5) — pastel brand
  colors are higher-risk spots; flag in palette-to-ink guidance.

## Limits

- Screen printing on garments, not offset/flexo on board — mixing logic and
  under-base physics transfer, press specifics don't.
- FN-INK is one plastisol mixing system; formulas differ per ink system
  (frame's 0131 formula is an example card shown, dated 3/10/2023).
- The 2995 C mix components (white + light blue) are from narration; exact
  gram amounts for THAT mix were only partially narrated (31.3 g white heard
  mid-mix — batch size unstated at that moment).
- Conflicts: none; completes the ink_color_systems triad (what CMYK/PMS are →
  when to use which → how a spot ink is physically made).
