# The mark at true scale, on every ground it is actually composed on

Produced at **§BA-4, 2026-08-22**, under the tranche brief's explicit
sanction: *"a rendered comparison at true scale … is a legitimate deliverable
of this tranche and it is not a §AE2(c) decision to produce one."*

**Print `mark_on_every_ground_TRUE_SCALE.pdf` at 100%.** A4. Every panel on it
is 1:1 in millimetres. If your viewer says "fit to page", the sheet is lying to
you and none of the rest of this file applies.

---

## What question this answers

`evaluate_brand_usage(doc, background=...)` takes the background as an
**argument** and believes whatever it is told. Until this tranche, the live
container front declared `background="pure_white"`.

Nothing in the repository had ever looked at what the mark is actually printed
on. This sheet is that look, and it disagrees with the declaration on all four
composed states.

> **THE SENTENCE ABOVE IS NOW FALSE, AND IT IS THIS TRANCHE THAT MADE IT SO.**
> Corrected 2026-08-25 at §BB, in place rather than overwritten, because it was
> true on the day it was written and the change is the whole point.
>
> `evaluate_brand_usage` no longer believes what it is told. It **computes** the
> ground out of the document by paint order — C13/BB1, ruled and committed at
> `68eb962` before the code — and reports `ground_node`, `ground_hex`,
> `ground_resolved` and `ground_permitted` alongside the declared axis. The
> declared `background` argument is still read and still judged, untouched, on
> its own axis; BB1(e)(3) required that, in its own words: *"churning them would
> destroy the axis they measure."* **Two axes now, and neither can lie for the
> other.**
>
> **THE PANELS AND THE TABLE BELOW ARE UNCHANGED AND WERE RE-MEASURED, NOT
> ASSUMED.** Every row of that table was measured again against the live
> composer this session and reproduces exactly — same nodes, same hex, all
> four states. **The panels were deliberately NOT re-rendered.** Emitting
> byte-different files that say the same thing would be churn dressed as work,
> and it would break the one property these panels have that matters: they are
> the artefacts the §BA-4 ruling was actually read against.
>
> **WHAT THE NEW MEASUREMENT FOUND THAT THIS SHEET COULD NOT SHOW.** These
> panels answer *what is under the mark*. C12/BB2, ruled the same morning at
> `f009a83`, asks what crosses **over** it — and the live front fails that rule.
> Three ribbons filled `#F7EFE4` cross the mark's ink box at **CIE76 ΔE 4.6305**
> against this sheet's own `#F6EDEB`, threshold 2.3, permitted count zero. Panel
> 3 shows those ribbons; nothing on this sheet says they are a violation,
> because when it was drawn there was no rule for them to violate.

| # | state | what the ink lands on | hex |
|---|---|---|---|
| 1 | `pure_white` — **declared** | *nothing at all — and no composer produces this state* | — |
| 2 | NOW, no motif | `decoration-field` | `#F6EDEB` |
| 3 | NOW, motif field — **the live call site** | `decoration-field` | `#F6EDEB` |
| 4 | FUTURE, direct print, no motif | `body` | `#EAD7D2` |
| 5 | FUTURE, direct print + motif | `body` | `#EAD7D2` |

The two findings the picture is here to carry:

1. **No composed state puts the mark on white.** Row 1 is not a state the
   machine can produce; it is a sentence the machine was told to believe.
2. **The motif does not change the answer.** Panels 2 and 3 differ only in
   what surrounds the mark. What is *under* it is `#F6EDEB` in both. The
   variable that moves the ground is `direct_print and hierarchy` at
   `apps/ire/compose_container.py:257` — that branch returns early without
   emitting a `decoration-field` rect at all, which is why rows 4 and 5 land
   on the substrate instead. (This said `:241` until 2026-08-22. Line 241 is
   the `def _native_decoration(...)` signature; the branch is sixteen lines
   further down.

   **This parenthesis first read "Four documents had copied the number from
   each other", and that was itself an understatement — caught by grepping
   the tree instead of trusting the sweep that had just run.** Seven sites
   carried a wrong line number for this one branch, in **two different wrong
   values**: four said `:241` (this file, `OWNER_INPUT_MANIFEST.md`,
   `test_au3_brand_usage.py`, `progress_tracker.json` node 35) and three said
   `:202` (`progress_tracker.json` Sprint-6, `OWNER_INPUT_MANIFEST.md` row
   **C8**, `OWNER_REVIEW_QUEUE.md`). The first correction pass fixed four of
   the seven and then wrote a note claiming the defect was four wide. All
   seven now read `:257` and each says what it used to say.

   *This sentence said "row C6" for about ninety seconds. The heading above
   the line is C8. It was caught by `awk`-ing for the nearest heading rather
   than recalling it — while writing the note whose entire subject is a
   number that four documents recalled instead of checking.*)

`#F6EDEB` is not a constant anyone chose. It is `_tint(#EAD7D2, 0.55)`, derived
at composition time. That is the value the owner is asked to rule on in
**OWNER_INPUT_MANIFEST.md → C13**.

---

## What each panel is

**All four images are crops of real emitted `.ai` files** — produced by the
same `emit_pdf_ai` the repository ships through, rasterised at 600 dpi and cut.
The `.ai` files sit beside the PNGs in this directory so every crop can be
checked against its source. Nothing was re-drawn for the picture, so **a panel
cannot flatter the artefact**.

**Panels 2, 3 and 4 are also real DOCUMENTS** — the exact graphs the composer
produces for those states.

**Panel 1 is not, and it is labelled as such on the sheet.** `panel1_pure_white_
DECLARED.ai` exists and is a real emitted file, but the *document* behind it is
synthetic: no composer produces it. It was built by deleting every node except
the mark from a real document, so the mark's own bytes are identical across all
panels and the ground is the only variable. The distinction matters — the
emitter is honest in all four cases; it is the input to it that panel 1
fabricates, on purpose, because the declaration under audit describes a state
nothing composes.

**Panel 5 has no image, and that is a result, not a gap.** The emitter refused
to write it:

```
BrandStringRefusal: BRAND_STRING_ARTEFACT_WITHHELD: refusing to write
panel5_future_direct_print_motif.ai — the composed document carries
provisional brand copy: BRAND_STRING_PROVISIONAL: descriptor
```

That is **§AV3** (`apps/ire/brand_string_runtime.py`), the runtime half of the
§AE2(c) brand-string remedy, enforcing §AU5(4)/§AU8(e). State 5 carries the
`⟪PROVISIONAL⟫` descriptor line that is owner row **C9**. The guard fired on
real work, unprompted, and the refusal text is printed on the sheet verbatim
rather than being quietly omitted (§AY0(d) — an absence must carry its extent).

Row 5's ground in the table above is read from the **graph**, which needs no
emitted file. Only the *image* is missing.

---

## The crop

```
crop = mark + one cap height on every side
     = (17.280 + 2 × 3.0861) × (3.603 + 2 × 3.0861)
     = 23.4522 × 9.7752 mm   @ 600 dpi
```

One cap height is not an arbitrary margin — it is **§AU3's clear-space rule**.
The panel therefore shows exactly the region that rule governs, at the size it
prints. Both numbers come from the gate's own record (`placed_mm` and
`logo_cap_height_mm`), not from a measurement taken for this picture.

---

## Regenerating it

```sh
cd bbrose_design_os
venv/bin/python docs/visual_quality/ba4_grounds/render.py [outdir]
```

Defaults to writing back into this directory. Requires `PyMuPDF` (in the venv;
the repo's own `pdf_to_png` uses `sips`, which only rasterises at 72 dpi and
cannot produce a true-scale crop).

The script prints the measured ground for every state before it draws anything.
If those printed values ever stop matching the table above, **the table is
wrong and the composer changed** — which is the whole point of shipping the
script next to the pictures.

---

## What this does not claim

- **Not an approval of anything.** No gate moved, no bar moved, no acceptance
  state changed. C13 is open and BLOCKING.
- **Not a claim that `#F6EDEB` or `#EAD7D2` is acceptable.** Whether either is
  a permitted ground is §AE2(c) reserved and is the owner's alone. This sheet
  exists so that decision is made looking at the thing rather than at a hex
  code.
- **Not colour-managed.** These are RGB rasters on an uncalibrated path. Use
  them for *size and relationship*, not for matching a printed swatch.
- **Extent is `compose_container.py` and those five states only.** The dropper
  composer (C10) was not read for this and its substrate is **not** measured
  here.
