# Prepress Checklist & PDF/X-1a Export (InDesignology)

## Source

- Title: Prepress checklist / press-ready PDF walkthrough
- Channel: InDesignology
- URL: https://www.youtube.com/watch?v=Md3QezpXYQU
- Duration: 4:09 · Watched: 2026-08-24
- Transcript source: captions (scraped via transcript panel)
- Detail mode: transcript-only
- Queue note: replaces 3C9vdr1kD6s (spot-colour separation video) which has no
  captions at all — swap recorded in WATCH_QUEUE.md.

## Claims

1. `t=0:12` Use "package" to collect the document with all links and fonts before
   handoff.
2. `t=0:34` Run spellcheck as an explicit prepress step — cheap, catches expensive
   mistakes.
3. `t=0:59` Trim / bleed / live-area trio; bleed extension stated as **1/8 inch
   (0.125 in)** beyond trim.
4. `t=1:37`–`t=2:41` Kill unused PMS/spot swatches; convert remaining spot swatches
   to process unless the job actually prints spot ink.
5. `t=2:04`–`t=2:24` Image requirements: 300 dpi effective resolution, placed at no
   more than ~125% scale, CMYK color mode, flattened, TIFF preferred.
6. `t=2:44` Outline type (convert to paths) for press-ready files when fonts won't
   travel.
7. `t=3:40`–`t=3:56` Export preset: **PDF/X-1a:2001** with crop marks, registration
   marks, and document bleed settings included.

## Engine hooks

- Claim 3 is the first explicit numeric bleed value in the WATCH corpus (0.125 in ≈
  3.175 mm): usable as a default for US-printed cartons in the M7 emitter, but
  carry it as a per-printer parameter, not a constant — European houses commonly
  spec 3 mm.
- Claims 4 + PAPP claim 8 converge from two independent sources: spot swatches left
  in a file are the canonical prepress error. Emitter preflight: enumerate swatches,
  assert every one maps to a declared ink.
- Claim 7 gives a concrete deliverable spec for the artwork package:
  PDF/X-1a:2001 + marks + bleed is a safe default ask when a printer supplies no
  preset (pairs with PAPP claim 4: printer's own preset wins when it exists).
- Claims 5–6 belong in the handoff checklist doc alongside Lumi's fold-test
  (claim 6 there): image effective-dpi and outlined type are machine-checkable.

## Limits

- InDesign-centric workflow; the OS emits from Illustrator-shaped pipelines — the
  checks transfer, the menu paths don't.
- PDF/X-1a:2001 is a conservative legacy standard (flattens transparency, no RGB);
  many modern printers accept PDF/X-4. Treat as safe default, not the only answer.
- Bleed value is one US instructor's number; do not encode as universal (see hook).
- Transcript-only; no frames captured.
- Conflicts: none with committed authorities.
