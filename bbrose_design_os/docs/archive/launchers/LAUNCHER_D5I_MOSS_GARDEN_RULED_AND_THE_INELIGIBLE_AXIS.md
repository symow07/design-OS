# LAUNCHER — D5i, MOSS GARDEN RULED, AND THE AXIS THAT WAS ALREADY RETIRED

Follows `9de3457`. One owner ruling to record, one adjudication that was
skipped against rules that already exist, and a class of defect that has now
happened three times and still has no name.

No renders. Every number this needs is already measured.

---

## THE RULING

**Asked and answered 2026-08-13. Moss Garden stays MARBLED, and the note
loses the gold.**

Pan 11 remains `MARBLED` at `#48583F`. The shade note's "antique-gold" is
struck and replaced with restrained olive-on-olive vein structure, because
that is what the builder produces and "antique-gold veining over olive" is
unachievable at any lightness — MARBLED's components are per-channel
multiplicative of the base, `(R−B)/(R+G+B)` is scale-invariant, and the two
components are therefore chroma-identical by construction. Chroma separation
measured 0.119085 at authored depth and 0.119085 at 6.35× lighter. Darkness
was never the cause and no lightness change can fix it.

What the pan *does* deliver is real: chroma spread 0.015150 against a matte
control's 0.001547, **9.8×**, and `9de3457` confirmed that figure is untouched
by the region and scalar defects, because MARBLED is the one albedo-derived
family and chroma on PLANAR is the right measurement for it.

This corrects a note, not a family and not a colour. Eleven pans are
unaffected.

---

## THE ADJUDICATION THAT WAS SKIPPED

`9de3457` reported PRESSED_POWDER as *"not on GRAZING — but yes on the
family,"* clearing on **EDGE 0.357** and SHEEN 0.264, with the honest caveat
that 0.25 was shown as a reference bar and no eligibility or independence was
run.

The caveat understates it. The eligibility ruling is not un-run — it exists,
it is committed, and it retires the axis the result leads with.

`docs/roadmap/palt_m6/M6_SEQUENCING_AND_SUBSTITUTION_RULING.md:34`:

> **floor-eligible** — FWHM, PEAK, SPECULAR, GRAZING and SHEEN all are;
> **EDGE is not**.

And `palette_roadmap_continuation_state.json:456`:

> `"M6_EDGE_AXIS": "INELIGIBLE_NOISE_FLOOR_0.27991"`

Apply that and the table changes shape:

| | reported as clearing | on eligible axes only |
|---|---|---|
| **PRESSED_POWDER** | EDGE 0.357, SHEEN 0.264 | **SHEEN 0.264 alone**, +0.014 over bar |
| **attar_BAKED** | GRAZING 0.347, EDGE 0.275, SHEEN 0.262 | GRAZING 0.347, SHEEN 0.262 |
| **BAKED** (Moss depth) | GRAZING 0.271 | GRAZING 0.271, +0.021 over bar |

EDGE 0.357 is not merely uncertified — it sits on an axis already ruled
ineligible, and 0.357 is barely above that axis's own recorded noise floor of
0.27991. Attar's EDGE 0.275 is *below* it.

And R5 has not been applied. The same ruling at `:35-36` records that R5 bars
two above-ceiling axes from both counting toward one pair, and that FWHM is
barred from counting alongside SHEEN. Whether PRESSED's surviving axes may
both count is a question the programme's own rules answer and nobody asked.

So Old Rose is not cleared and not failed. It is unadjudicated, against rules
that were written down before the measurement was taken.

---

## THE CLASS WITH NO NAME

Three times now, a record's identifier and its body have described different
things:

1. `palettes.palt_m6_artwork_shades` titled *"powder & eyeshadow material
   engine"* — id from the founding plan, title from the work.
2. `MATERIALS_LIBRARY_ABSENT` → the id named a library, the surviving residue
   was a typeface.
3. `VQ1_HUMAN_STRUCTURAL_REVIEW` — id named the container/dropper structural
   review, detail named the M4C-4 intent panel. Two owner-judgment surfaces in
   one entry, which is why checking either never closed it.

`9de3457` spotted the third and correctly called it "the same shape as the M6
id/title drift." It did not open anything for it. Three instances of one
failure mode, diagnosed each time and named none of the times, is how a fourth
happens.

---

## THE PROMPT

```
GOAL — record an owner ruling on Moss Garden, adjudicate the D5h measurement
against eligibility and independence rules that already exist, and name a
defect class that has now recurred three times. No renders. No new
instruments. No design decisions beyond the ruling being recorded.

OWNER RULING — GRANTED AND RECORDED 2026-08-13. Moss Garden (pan 11, #48583F)
REMAINS MARBLED. Its shade note loses "antique-gold" and describes restrained
olive-on-olive vein structure instead. Recorded by PROJECT_OWNER.

CONTEXT
  docs/roadmap/palt_m6/M6_SEQUENCING_AND_SUBSTITUTION_RULING.md:31-40  (eligibility + R5)
  docs/roadmap/palt_m4c/palette_roadmap_continuation_state.json:456    (EDGE ineligible)
  docs/roadmap/palt_m6/es3083_shade_authority.json                     (the twelve, per-shade stamped)
  docs/roadmap/palt_m6/family_candidates/                              (the D5h re-measure)
  docs/roadmap/palt_m6/axis_independence_matrix_n6.json
  docs/roadmap/palt_m6/open_defect_inventory.md                        (D9, D10)
  apps/pipeline/services/palette_axis_eligibility.py

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa. A564.

STEP 1 — RECORD THE MOSS GARDEN RULING

  READ THE AUTHORIZATION ROUTE FOR es3083_shade_authority.json FIRST. It is at
  schema 1.2 and carries a sha256, so do not assume it edits freely the way
  the tracker did. If it is digest-bound and needs owner authorization, STOP
  and report the exact text you would land and what the authorization costs.

  The record must carry:
    - Moss Garden REMAINS MARBLED — family unchanged, colour unchanged
    - the note correction: "antique-gold" struck, replaced with restrained
      olive-on-olive vein structure
    - WHY, in terms of the builder rather than taste: MARBLED's components are
      per-channel multiplicative of the base, chroma is scale-invariant under
      that operation, the two components are chroma-identical by construction,
      and measurement confirmed 0.119085 at authored depth and 0.119085 at
      6.35x lighter. Gold requires a hue the builder never computes.
    - what the pan DOES deliver: chroma spread 0.015150 vs 0.001547 control,
      9.8x, confirmed at 9de3457 as unaffected by the region/scalar defects
    - that this is a NOTE correction, not a family or colour change, and that
      the other eleven shades are untouched

  The per-shade stamping exists precisely so one shade can move without the
  other eleven. Use it. Do not restamp the record wholesale.

STEP 2 — ADJUDICATE THE D5h TABLE UNDER THE RULES THAT ALREADY EXIST

  M6_SEQUENCING_AND_SUBSTITUTION_RULING.md:34 rules that FWHM, PEAK, SPECULAR,
  GRAZING and SHEEN are floor-eligible and EDGE is NOT. continuation_state:456
  records M6_EDGE_AXIS as INELIGIBLE_NOISE_FLOOR_0.27991.

  Re-adjudicate every family in the D5h table with EDGE excluded, and then
  apply R5 and whatever independence constraints axis_independence_matrix_n6
  and palette_axis_eligibility actually impose. Read them; do not infer them
  from my summary.

  Report per family: which axes are eligible, which clear, whether the
  clearing axes may both count, and what the verdict is on eligible axes
  alone.

  If applying eligibility changes a verdict reached at 9de3457, say which and
  say so plainly. Do not move the bar, do not substitute a different bar, and
  do not report an ineligible axis as supporting evidence with a footnote.

STEP 3 — OLD ROSE, PLAINLY

  Pan 9, Old Rose, PRESSED_POWDER. On eligible axes only its clearance is
  SHEEN 0.264 against a 0.25 bar — 0.014 of headroom, one axis.

  Answer directly: does PRESSED_POWDER clear as a distinguishable family at
  Old Rose's value, on eligible axes, under the programme's own independence
  rules? YES or NO before any explanation.

  If NO, do not reclassify the pan and do not tune anything. State what the
  owner's options are and what each would cost, and stop. The pan is the
  owner's decision; this step supplies evidence for it.

  If the honest answer is NEITHER — that one marginal eligible axis is not
  enough to certify and not enough to refute — say NEITHER and say what would
  settle it and what that would cost.

STEP 4 — NAME THE CLASS

  Three records have now had an identifier and a body describing different
  things: palettes.palt_m6_artwork_shades (id from the founding plan, title
  from the work), MATERIALS_LIBRARY_ABSENT (id named a library, residue was a
  typeface), and VQ1_HUMAN_STRUCTURAL_REVIEW (id named the container review,
  detail named the intent panel). You diagnosed the third at 9de3457 and
  correctly called it the same shape as the first. You opened nothing for it.

  Decide whether this is D9's hole, D10's, or its own, and act on that
  decision — extend or open, once. D9 is blockers whose premise nothing
  re-evaluates; D10 is an analyst's choice of measure that was never written
  down. This is neither: it is a record whose two halves disagree and no
  control compares them.

  Then answer one question in no more than two sentences: is there any control
  anywhere in the programme that reads a record's id and its body and asks
  whether they describe the same thing?

DO NOT
  - reclassify any pan, including Old Rose
  - change Moss Garden's colour or family
  - restamp the other eleven shades
  - edit the frozen builder
  - report EDGE as supporting evidence
  - move, substitute or soften the 0.25 bar
  - open more than one defect entry for Step 4
  - close D5

REPORT BACK
  - the authorization route for es3083_shade_authority.json, and whether you
    landed the ruling or stopped
  - the re-adjudicated table, EDGE excluded, independence applied
  - which 9de3457 verdicts changed
  - Old Rose: YES, NO or NEITHER, first word
  - what Step 4 decided, and the two-sentence answer
  - anything in this brief that was wrong about the code
```

---

## WHAT COMES BACK TO YOU

**Moss Garden closed.** Eleven of the twelve were never in question; the
twelfth now says what the engine actually does. That was the last shade
question standing between you and M7's artwork.

**And an honest answer on Old Rose**, which is the only pan whose evidence is
now thinner than it looked. If SHEEN alone carries it under the programme's
own rules, nothing moves. If it does not, you will hear NO or NEITHER as the
first word rather than after three paragraphs, and the options will be yours
rather than pre-decided.

Two standing blockers, both yours: calipers on an ES3083 if you hold one, and
supplier data you have already chosen to defer. Neither is engineering, and
neither blocks the artwork.
