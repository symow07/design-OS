# LAUNCHER — D5j, THE CENSUS DID NOT CONTAIN THEM

Follows `b92521f`. One correction, one bound to record, one sweep, and a
statement of what actually gates M7 now. No renders.

---

## WHAT b92521f GOT RIGHT

The authorization reasoning is sound: REVISABLE + A375 is the record-binding
route, A578 ruled it authorization-free, and the hashed-amendment route is for
law blocks. Landing the ruling rather than stopping was correct, and the
verification that zero other shades carry the correction key is the right
check for a per-shade-stamped record.

**Step 3 is the best piece of adjudication in this arc.** Given a table that
appeared to fail Old Rose, it declined both to certify and to refute, because
it noticed that the committed verdict rests on `GRANULARITY_INDEX` — an axis
on a different rig, which this table never measured. That is exactly right,
and `palette_powder_texture_axes.py:70-72` confirms it: `GRANULARITY_INDEX`'s
`serves` list carries `PRESSED_vs_MATTE`. NEITHER was the honest answer and it
was reached against the grain of the brief, which had framed it as a probable
NO.

The independence reading is also exact. The matrix gives PEAK under the 0.80
ceiling against all four others — 0.60, 0.4286, 0.4857, 0.60 — while FWHM,
SPECULAR, GRAZING and SHEEN are mutually 0.8286 to 1.0000. PEAK plus exactly
one is the only passing shape.

---

## THE CORRECTION

The Step 3 reasoning was applied to one family and stopped there. It covers
three more, and those three are now carrying a published FAIL they do not
deserve.

**MARBLED, GLITTER and BAKED should read NEITHER, for the same reason and
then for a second, harder one.**

**First — chroma is not in that table.** `axes_from` returns HIGHLIGHT_FWHM,
HIGHLIGHT_PEAK, SPECULAR_TO_DIFFUSE_RATIO, GRAZING_RESPONSE,
SHEEN_REGION_RESPONSE and EDGE_HIGHLIGHT_RESPONSE. Not one is chromatic.
MARBLED's 9.8× and GLITTER's 19.2× were measured by a different instrument on
a different quantity — precisely the relationship `GRANULARITY_INDEX` has to
PRESSED. Failing a family on six axes blind to its declared distinction is
D5h Finding 2 in mirror image, and this arc has now made that error in both
directions.

**Second — the matrix's own population excludes them.**
`axis_independence_matrix_n6.json:3-10`:

```
"census_families": ["CREAM", "POWDER_MATTE", "POWDER_METALLIC",
                    "POWDER_SATIN", "PRESSED_POWDER", "SHIMMER"]
```

Six families. **MARBLED, GLITTER and BAKED are not among them.** The R5
constraint that decided which axes may co-count is a rank correlation over a
population that excludes the three families it was just used to fail. And the
two families that PASSED — POWDER_METALLIC and SHIMMER — are both inside the
census, while all three outside it FAILED. That may be substantive or it may
be an artifact of applying a fitted rule beyond its fit. Either way it was not
declared, and 3aa says a derived quantity carries the identity of every input
it read. The R5 verdict read a six-family correlation matrix, and the record
did not say so.

**Why this needs correcting rather than noting.** `b92521f` records the Moss
Garden ruling — which cites 9.8× as what the pan honestly delivers — and in
the same commit publishes a table in which MARBLED reads FAIL. Read cold, the
commit contradicts itself. That is the id/body class you opened D11 for,
occurring at commit scale between two records rather than inside one.

---

## WHAT THIS DOES NOT CHANGE

`M6_PRESSED_VS_MATTE` remains `PASS_GRANULARITY_PLUS_SHEEN`. It was not
overturned, and Old Rose stays PRESSED_POWDER unless the owner chooses to
spend the 10–16 renders on a measurement that may not converge below the 0.35
SUBJECT_WINDOW floor.

Moss Garden's ruling stands. POWDER_METALLIC and SHIMMER's PASS stands — both
are inside the census and both clear on eligible, co-countable axes.

**And nothing engineering-side gates M7's artwork.** Two standing blockers,
both owner-side: supplier data, already deferred by owner decision, and ES3083
dimensions, which need calipers. Neither touches artwork.

---

## THE PROMPT

```
GOAL — correct three verdicts that were reached by applying a rule outside the
population it was fitted on, record that bound where it cannot be missed
again, sweep for other instances, and state plainly what gates M7. No renders.
No new instruments. No design decisions.

CONTEXT
  docs/roadmap/palt_m6/axis_independence_matrix_n6.json:3-10  (census_families — SIX)
  docs/roadmap/palt_m6/M6_SEQUENCING_AND_SUBSTITUTION_RULING.md:31-40
  apps/pipeline/services/palette_characterization_rig.py:258-290  (axes_from — no chroma axis)
  apps/pipeline/services/palette_powder_texture_axes.py:10-14, 68-75
  apps/pipeline/services/palette_axis_eligibility.py
  docs/roadmap/palt_m6/family_candidates/
  docs/roadmap/palt_m4c/palette_roadmap_continuation_state.json

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa. A564.

STEP 1 — VERIFY THE PREMISE BEFORE ACTING ON IT

  Read axis_independence_matrix_n6.json and confirm or refute two things:

    a. its census_families are CREAM, POWDER_MATTE, POWDER_METALLIC,
       POWDER_SATIN, PRESSED_POWDER and SHIMMER — six — and MARBLED, GLITTER
       and BAKED are absent from the population the correlations were
       computed over.
    b. axes_from returns no chromatic axis, so chroma spread — the quantity
       MARBLED's 9.8x and GLITTER's 19.2x were measured on — is not among the
       six the R5 adjudication ranged over.

  If either is wrong, say so and STOP. The whole of this brief rests on them.

STEP 2 — CORRECT THE THREE VERDICTS

  If Step 1 holds, MARBLED, GLITTER and BAKED read NEITHER, not FAIL — for
  the same reason Old Rose does, plus the population bound.

  Correct the b92521f table wherever it was committed. Each of the three must
  carry:
    - NEITHER, not FAIL
    - that the six adjudicated axes do not measure the family's declared
      distinction, naming which instrument does and what it measured
    - that the R5 constraint was fitted on a six-family census that excludes
      this family, per 3aa
    - what WOULD settle it, and roughly what that costs

  Do NOT re-run R5 on an expanded census to rescue the FAILs. Do not compute a
  new matrix. Do not move or substitute a bar. The correction is that the
  verdict was not the instrument's to give, not that the number was wrong.

  State explicitly whether POWDER_METALLIC's and SHIMMER's PASS survives. My
  reading is that it does — both are inside the census and clear on eligible
  co-countable axes — but say so from the record, not from my say-so.

STEP 3 — RECORD THE BOUND WHERE IT CANNOT BE MISSED

  The matrix carries its census_families but nothing stops a later reader
  applying it to a family outside them. Make the bound explicit in the record
  itself: state that its correlations are valid only over the six listed
  families and that applying R5 to a family outside the census is an
  extrapolation that must be declared.

  Then judge, in two sentences, whether this is a NEW defect class or an
  instance of one already open. My reading: D9 is a claim going stale, D10 is
  an undeclared choice of measure, D11 is a record whose halves disagree —
  this is a rule applied outside its fitted population, which is none of the
  three. But it may be D10's, since choosing to apply a bounded rule IS a
  choice of measure. Decide, and open or extend ONCE.

STEP 4 — SWEEP

  Has the eligibility / R5 apparatus been applied anywhere else to a family,
  pair or condition outside the census it was fitted on? Check every committed
  verdict that cites eligibility, R5, a noise floor or the 0.25 bar, and say
  whether its subject was inside the population the rule came from.

  State your search extent. If the answer is that this is the only instance,
  say that plainly — a clean sweep is a real result and should not be padded.

STEP 5 — WHAT GATES M7

  State, from the records rather than from memory, exactly what now stands
  between the programme and M7's artwork deliverable — ES3083 artwork + shade
  labels + editable .AI.

  For each item say: whether it is engineering, evidence or owner judgment;
  whether it blocks the artwork specifically or only the pilots that follow
  it; and what would discharge it.

  If nothing engineering-side blocks the artwork, say so in one sentence at
  the top. If something does, name it — do not soften it because the previous
  paragraph reads well.

DO NOT
  - re-run or expand the independence matrix
  - reclassify any pan
  - change Moss Garden's ruling or its record
  - move, substitute or soften any bar
  - overturn M6_PRESSED_VS_MATTE
  - open more than one defect entry
  - close D5

REPORT BACK
  - Step 1: confirmed or refuted, both parts
  - the three corrected verdicts and whether METALLIC/SHIMMER's PASS survives
  - where the population bound was recorded
  - Step 3's two sentences and what was opened or extended
  - the sweep's extent and result
  - Step 5's list, with the one-sentence answer at the top
  - anything in this brief that was wrong about the code
```

---

## WHAT COMES BACK TO YOU

**A record that does not contradict itself.** Moss Garden's ruling and the
family table currently sit in one commit saying different things about the
same pan. After this they agree, and the three families that were failed by a
rule that never contained them will say so.

**And a straight answer on what is left.** My reading is that nothing
engineering-side stands between you and the artwork — two blockers, both
yours, neither touching artwork. Step 5 exists to test that rather than let me
assert it.

**Then M7, which is the thing this programme was built to produce.** It will
need two decisions from you that no measurement can supply: the typeface for
BBROSE's own lettering, and the lid layout. Neither is blocked and neither is
urgent this minute, but they are the next two questions and they are yours.
