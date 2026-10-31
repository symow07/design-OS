# Why Does Print Not Match the Screen? CMYK vs RGB (Pro Printers)

## Source

- Title: Why Does Print not Match the Screen? The CMYK vs RGB Issue!
- Channel: Pro Printers Print School | Print Made Easy (51 subs; Feb 2025
  screen-share of a demo PDF, 673 views)
- URL: https://www.youtube.com/watch?v=j9E9uxezyFc
- Duration: 1:56 · Watched: 2026-08-24
- Transcript source: none usable — stuck-spinner panel
  (PAmodern_transcript_view:169 signature) across two page loads; video
  autoplayed to an unrelated video mid-attempt
- Detail mode: FRAMES-ONLY — 2 frames (~0:50, ~1:25); whole video narrates ONE
  demo-PDF slide, both frames show it fully

## Claims

1. `t≈0:50` (frame, slide text) **RGB = additive** (Red/Green/Blue), "used by
   displays & screens"; **CMYK = subtractive** (Cyan/Magenta/Yellow/Black),
   "used in print" — shown as light-mixing vs ink-mixing Venn diagrams.
2. `t≈0:50` (frame) Side-by-side swatch pairs, "RGB On Screen/Display" →
   "CMYK Printed Output": orange survives nearly intact; **hot magenta dulls
   to mauve; neon green darkens to leaf green; pure RGB blue shifts to slate
   blue** — saturated screen colors are the casualties.
3. `t≈0:50` (frame, slide text) Stated solutions: "**Compromise = Closest
   Match**" or "**Pantone Colors = More Cost**."
4. Description text: conversation "applies to all document layout and
   photographic programs when printing is required, including Adobe InDesign,
   Illustrator and Photoshop."

## Engine hooks

- Claim 2 gives the engine a GAMUT-RISK LIST: magenta/fuchsia, neon green,
  pure blue are the screen colors that collapse in CMYK. Preflight should
  flag out-of-gamut brand colors specifically, not warn generically —
  BBROSE palette entries near these hues get a "will shift in CMYK; spot or
  reformulate" warning.
- Claim 3 is the same two-path fork the corpus keeps converging on: accept
  CMYK compromise OR pay for a spot plate (INNORHINO economics, PAPP
  spot-swatch-equals-plate, Domino's gamut-simulation third path). Now stated
  as the client-facing explanation slide.
- Pairs with eguru_delta_e: "closest match" is quantifiable — the compromise
  path should carry a ΔE expectation instead of a vibe.
- Client-communication artifact: a one-slide screen-vs-print comparison PDF is
  an effective owner-review tool — engine could emit one per palette showing
  sRGB swatch vs CMYK-converted swatch.

## Limits

- FRAMES-ONLY; narration (the "why," any numbers) lost. Slide text is the
  entire evidence base.
- 51-subscriber channel, single demo PDF; swatch shifts are illustrative
  renderings, not measured conversions.
- No mention of color profiles/rendering intents — the actual conversion
  machinery is absent.
- Conflicts: none; restates wave-6 ink_color_systems fundamentals in
  client-facing form.
